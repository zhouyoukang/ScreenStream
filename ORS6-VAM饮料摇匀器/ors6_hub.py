"""ORS6 全链路开发测试验证中枢 — HTTP + WebSocket + REST API

启动:
    python ors6_hub.py [--port 8086] [--no-browser]

功能:
    - 3D虚拟设备可视化 (Three.js)
    - 6轴实时状态监控
    - 42种TempestStroke运动模式
    - Funscript脚本解析播放
    - 协议/设备/集成测试套件
    - TCode命令发送与历史
"""

import os, sys, json, time, re, logging, threading, socket, hashlib, base64
from typing import Optional
from pathlib import Path
from urllib.parse import unquote

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from tcode.virtual_device import VirtualORS6, ServoConfig
from tcode.serial_conn import TCodeSerial
from tcode.tempest_stroke import TempestStroke, PATTERN_LIBRARY
from tcode.protocol import (
    TCodeCommand, parse_multi, encode_multi, is_device_command,
    AXES_SR6, encode_position, decode_position,
)

logger = logging.getLogger(__name__)


class SerialDeviceAdapter:
    """Wraps TCodeSerial to provide VirtualORS6-compatible interface for the Hub"""

    FIRMWARE_INFO = "TCodeESP32 (Real Device)"
    ALL_AXES = ["L0", "L1", "L2", "R0", "R1", "R2", "V0", "V1", "A0", "A1", "A2"]

    def __init__(self, port: str = None, baudrate: int = 115200, auto_detect: bool = False):
        self._serial = TCodeSerial(port=port, baudrate=baudrate, auto_detect=auto_detect)
        self._connected = False
        self._start_time = time.time()
        self._total_commands = 0
        self._history = []
        self._history_max = 500
        self._lock = threading.Lock()
        self.on_state_change = None
        # Track axis positions from commands we send
        self._positions = {ax: 5000 for ax in self.ALL_AXES}
        self._targets = {ax: 5000 for ax in self.ALL_AXES}
        self._moving = {ax: False for ax in self.ALL_AXES}
        self._cmd_counts = {ax: 0 for ax in self.ALL_AXES}
        self._broadcast_thread = None
        self._running = False

    @property
    def is_connected(self) -> bool:
        return self._serial.is_connected

    def connect(self) -> bool:
        ok = self._serial.connect()
        if ok:
            self._connected = True
            self._start_time = time.time()
            self._running = True
            self._broadcast_thread = threading.Thread(target=self._state_loop, daemon=True)
            self._broadcast_thread.start()
            logger.info(f"Real device connected: {self._serial.port}")
        return ok

    def disconnect(self):
        self._running = False
        if self._broadcast_thread:
            self._broadcast_thread.join(timeout=2)
        self._serial.disconnect()
        self._connected = False

    def send(self, command: str) -> Optional[str]:
        """Send TCode command to real device and track positions"""
        if not command:
            return None
        self._total_commands += 1
        self._record_command(command)

        # Parse command to track positions locally
        upper = command.strip().upper()
        if is_device_command(command):
            if upper == "D1":
                for ax in self.ALL_AXES:
                    self._targets[ax] = 5000
                    self._moving[ax] = True
            elif upper in ("D0", "DSTOP"):
                for ax in self.ALL_AXES:
                    self._targets[ax] = self._positions[ax]
                    self._moving[ax] = False
        else:
            try:
                cmds = parse_multi(command)
                for cmd in cmds:
                    if cmd.axis in self._targets:
                        self._targets[cmd.axis] = cmd.position
                        self._moving[cmd.axis] = True
                        self._cmd_counts[cmd.axis] = self._cmd_counts.get(cmd.axis, 0) + 1
            except Exception:
                pass

        result = self._serial.send(command)

        # Simulate position tracking (instant move for visualization)
        for ax in self.ALL_AXES:
            if self._moving[ax]:
                diff = self._targets[ax] - self._positions[ax]
                self._positions[ax] += diff * 0.6  # smooth approach
                if abs(self._targets[ax] - self._positions[ax]) < 10:
                    self._positions[ax] = self._targets[ax]
                    self._moving[ax] = False

        return result

    def stop(self):
        self._serial.stop()

    def get_state(self) -> dict:
        axes = {}
        for ax in self.ALL_AXES:
            cur = round(self._positions.get(ax, 5000))
            axes[ax] = {
                "axis": ax,
                "current": cur,
                "target": self._targets.get(ax, 5000),
                "is_moving": self._moving.get(ax, False),
                "velocity": 0,
                "position_pct": round(cur / 9999.0 * 100.0, 2),
                "command_count": self._cmd_counts.get(ax, 0),
                "total_distance": 0,
            }
        return {
            "connected": self._connected,
            "running": self._running,
            "axes": axes,
            "any_moving": any(self._moving.values()),
            "total_commands": self._total_commands,
            "tick_count": 0,
            "tick_hz": 0,
            "uptime_sec": round(time.time() - self._start_time, 1),
            "firmware": self.FIRMWARE_INFO,
            "connection": "serial",
            "port": self._serial.port,
        }

    def get_positions(self) -> dict:
        return {ax: round(self._positions[ax]) for ax in self.ALL_AXES}

    def get_history(self, last_n: int = 50) -> list:
        return self._history[-last_n:]

    def _record_command(self, command: str):
        entry = {"cmd": command, "time": time.time(), "seq": self._total_commands}
        self._history.append(entry)
        if len(self._history) > self._history_max:
            self._history = self._history[-self._history_max:]

    def _state_loop(self):
        """Broadcast state at ~30fps for 3D visualization"""
        while self._running:
            # Smooth position tracking
            for ax in self.ALL_AXES:
                if self._moving[ax]:
                    diff = self._targets[ax] - self._positions[ax]
                    self._positions[ax] += diff * 0.3
                    if abs(diff) < 5:
                        self._positions[ax] = self._targets[ax]
                        self._moving[ax] = False
            if self.on_state_change:
                try:
                    self.on_state_change(self.get_state())
                except Exception:
                    pass
            time.sleep(1.0 / 30)


class WSHandler:
    """WebSocket handler (zero dependencies)"""

    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.closed = False

    @staticmethod
    def handshake(request_text: str) -> bytes:
        # Extract key from headers line-by-line for maximum reliability
        key = ""
        for line in request_text.split("\r\n"):
            if line.lower().startswith("sec-websocket-key:"):
                key = line.split(":", 1)[1].strip()
                break
        if not key:
            # Fallback: try \n-only line endings
            for line in request_text.split("\n"):
                if line.lower().startswith("sec-websocket-key:"):
                    key = line.split(":", 1)[1].strip().rstrip("\r")
                    break
        logger.debug(f"WS key={key!r} len={len(key)}")
        magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        accept = base64.b64encode(
            hashlib.sha1((key + magic).encode("ascii")).digest()
        ).decode("ascii")
        logger.debug(f"WS accept={accept!r}")
        resp = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        )
        return resp.encode("ascii")

    def send(self, data: str):
        if self.closed:
            return
        try:
            payload = data.encode("utf-8")
            frame = bytearray([0x81])
            length = len(payload)
            if length < 126:
                frame.append(length)
            elif length < 65536:
                frame.append(126)
                frame.extend(length.to_bytes(2, "big"))
            else:
                frame.append(127)
                frame.extend(length.to_bytes(8, "big"))
            frame.extend(payload)
            self.conn.sendall(bytes(frame))
        except Exception:
            self.closed = True

    def recv(self) -> Optional[str]:
        try:
            data = self.conn.recv(2)
            if not data or len(data) < 2:
                self.closed = True
                return None
            opcode = data[0] & 0x0F
            if opcode == 0x8:
                self.closed = True
                return None
            masked = data[1] & 0x80
            length = data[1] & 0x7F
            if length == 126:
                length = int.from_bytes(self.conn.recv(2), "big")
            elif length == 127:
                length = int.from_bytes(self.conn.recv(8), "big")
            mask_key = self.conn.recv(4) if masked else None
            payload = bytearray()
            while len(payload) < length:
                chunk = self.conn.recv(min(4096, length - len(payload)))
                if not chunk:
                    self.closed = True
                    return None
                payload.extend(chunk)
            if mask_key:
                payload = bytearray(b ^ mask_key[i % 4] for i, b in enumerate(payload))
            return payload.decode("utf-8", errors="ignore")
        except socket.timeout:
            return ""  # No data but connection alive
        except Exception:
            self.closed = True
            return None

    def close(self):
        self.closed = True
        try:
            self.conn.close()
        except Exception:
            pass


class TestRunner:
    """ORS6 测试套件"""

    def __init__(self, device: VirtualORS6):
        self.device = device

    def run_all(self) -> list[dict]:
        results = []
        results.extend(self.test_protocol())
        results.extend(self.test_device())
        results.extend(self.test_tempest())
        return results

    def test_protocol(self) -> list[dict]:
        tests = []
        # 1: Parse basic command
        try:
            cmd = TCodeCommand.parse("L09999I1000")
            assert cmd.axis == "L0" and cmd.position == 9999 and cmd.interval_ms == 1000
            tests.append({"name": "协议: 基本命令解析", "status": "pass"})
        except Exception as e:
            tests.append({"name": "协议: 基本命令解析", "status": "fail", "error": str(e)})
        # 2: Parse multi command
        try:
            cmds = parse_multi("L09999I500 R05000I500 L15000")
            assert len(cmds) == 3
            tests.append({"name": "协议: 多轴命令解析", "status": "pass"})
        except Exception as e:
            tests.append({"name": "协议: 多轴命令解析", "status": "fail", "error": str(e)})
        # 3: Encode command
        try:
            cmd = TCodeCommand(axis="L0", position=9999, interval_ms=1000)
            assert cmd.encode() == "L09999I1000"
            tests.append({"name": "协议: 命令编码", "status": "pass"})
        except Exception as e:
            tests.append({"name": "协议: 命令编码", "status": "fail", "error": str(e)})
        # 4: Device command detection
        try:
            assert is_device_command("D0") and is_device_command("D1") and is_device_command("DSTOP")
            assert not is_device_command("L09999")
            tests.append({"name": "协议: 设备命令识别", "status": "pass"})
        except Exception as e:
            tests.append({"name": "协议: 设备命令识别", "status": "fail", "error": str(e)})
        # 5: Position encoding
        try:
            assert encode_position(0.0) == 0
            assert encode_position(1.0) == 9999
            assert encode_position(0.5) == 4999
            tests.append({"name": "协议: 位置编解码", "status": "pass"})
        except Exception as e:
            tests.append({"name": "协议: 位置编解码", "status": "fail", "error": str(e)})
        # 6: Position clamping
        try:
            cmd = TCodeCommand(axis="L0", position=99999)
            assert cmd.position == 9999
            cmd2 = TCodeCommand(axis="L0", position=-100)
            assert cmd2.position == 0
            tests.append({"name": "协议: 位置边界裁剪", "status": "pass"})
        except Exception as e:
            tests.append({"name": "协议: 位置边界裁剪", "status": "fail", "error": str(e)})
        # 7: Speed modifier
        try:
            cmd = TCodeCommand.parse("R05000S300")
            assert cmd.axis == "R0" and cmd.speed == 300
            tests.append({"name": "协议: 速度修饰符", "status": "pass"})
        except Exception as e:
            tests.append({"name": "协议: 速度修饰符", "status": "fail", "error": str(e)})
        # 8: Short format
        try:
            cmd = TCodeCommand.parse("L09")
            assert cmd.axis == "L0" and cmd.position == 9
            tests.append({"name": "协议: 短格式解析", "status": "pass"})
        except Exception as e:
            tests.append({"name": "协议: 短格式解析", "status": "fail", "error": str(e)})
        return tests

    def test_device(self) -> list[dict]:
        tests = []
        # 1: Connection
        try:
            assert self.device.is_connected
            tests.append({"name": "设备: 连接状态", "status": "pass"})
        except Exception as e:
            tests.append({"name": "设备: 连接状态", "status": "fail", "error": str(e)})
        # 2: Send command
        try:
            self.device.send("L05000I500")
            state = self.device.get_state()
            assert state["axes"]["L0"]["target"] == 5000
            tests.append({"name": "设备: 命令发送", "status": "pass"})
        except Exception as e:
            tests.append({"name": "设备: 命令发送", "status": "fail", "error": str(e)})
        # 3: Emergency stop
        try:
            self.device.send("D0")
            tests.append({"name": "设备: 紧急停止(D0)", "status": "pass"})
        except Exception as e:
            tests.append({"name": "设备: 紧急停止(D0)", "status": "fail", "error": str(e)})
        # 4: Home all
        try:
            self.device.send("D1")
            time.sleep(0.05)
            state = self.device.get_state()
            assert all(state["axes"][a]["target"] == 5000 for a in ["L0", "L1", "L2", "R0", "R1", "R2"])
            tests.append({"name": "设备: 全轴归位(D1)", "status": "pass"})
        except Exception as e:
            tests.append({"name": "设备: 全轴归位(D1)", "status": "fail", "error": str(e)})
        # 5: Device info
        try:
            info = self.device.send("D2")
            assert info is not None and len(info) > 0
            tests.append({"name": "设备: 固件信息(D2)", "status": "pass"})
        except Exception as e:
            tests.append({"name": "设备: 固件信息(D2)", "status": "fail", "error": str(e)})
        # 6: Multi-axis
        try:
            self.device.send("L09999I200 R09999I200 L15000I200")
            time.sleep(0.05)
            state = self.device.get_state()
            assert state["axes"]["L0"]["target"] == 9999
            assert state["axes"]["R0"]["target"] == 9999
            tests.append({"name": "设备: 多轴并行命令", "status": "pass"})
        except Exception as e:
            tests.append({"name": "设备: 多轴并行命令", "status": "fail", "error": str(e)})
        # 7: State snapshot
        try:
            state = self.device.get_state()
            for k in ["connected", "running", "axes", "total_commands", "tick_count", "firmware"]:
                assert k in state
            tests.append({"name": "设备: 状态快照完整性", "status": "pass"})
        except Exception as e:
            tests.append({"name": "设备: 状态快照完整性", "status": "fail", "error": str(e)})
        # 8: 6-axis completeness
        try:
            state = self.device.get_state()
            sr6 = [a for a in ["L0", "L1", "L2", "R0", "R1", "R2"] if a in state["axes"]]
            assert len(sr6) == 6
            tests.append({"name": "设备: 6轴完整性", "status": "pass"})
        except Exception as e:
            tests.append({"name": "设备: 6轴完整性", "status": "fail", "error": str(e)})
        self.device.send("D1")
        return tests

    def test_tempest(self) -> list[dict]:
        tests = []
        # 1: Pattern library
        try:
            patterns = TempestStroke.list_patterns()
            assert len(patterns) >= 40
            tests.append({"name": "TempestStroke: 模式库({0}种)".format(len(patterns)), "status": "pass"})
        except Exception as e:
            tests.append({"name": "TempestStroke: 模式库完整性", "status": "fail", "error": str(e)})
        # 2: Generate positions
        try:
            stroke = TempestStroke("orbit-tease", bpm=60)
            pos = stroke.get_positions(0, frequency=60)
            assert "L0" in pos and 0 <= pos["L0"] <= 1
            tests.append({"name": "TempestStroke: 位置生成", "status": "pass"})
        except Exception as e:
            tests.append({"name": "TempestStroke: 位置生成", "status": "fail", "error": str(e)})
        # 3: Generate TCode
        try:
            stroke = TempestStroke("long-stroke-1", bpm=90)
            cmd = stroke.generate_tcode(0, frequency=60, interval_ms=16)
            assert "L0" in cmd and "I16" in cmd
            tests.append({"name": "TempestStroke: TCode生成", "status": "pass"})
        except Exception as e:
            tests.append({"name": "TempestStroke: TCode生成", "status": "fail", "error": str(e)})
        # 4: All patterns loadable
        try:
            errors = []
            for name in TempestStroke.list_patterns():
                try:
                    s = TempestStroke(name)
                    s.get_positions(0)
                except Exception as e:
                    errors.append(f"{name}: {e}")
            if errors:
                tests.append({"name": "TempestStroke: 全模式可用", "status": "fail", "error": "; ".join(errors[:3])})
            else:
                tests.append({"name": "TempestStroke: 全模式可用", "status": "pass"})
        except Exception as e:
            tests.append({"name": "TempestStroke: 全模式可用", "status": "fail", "error": str(e)})
        return tests


class FunscriptEngine:
    """Funscript播放引擎 — 集成到Hub，复用Hub的device.send()
    
    支持:
    - 多轴funscript加载 (L0/L1/L2/R0/R1/R2)
    - 视频同步播放 (前端HTML5 Video ↔ 后端TCode)
    - 播放/暂停/停止/跳转/变速
    - 安全限制 (速度/位置钳制)
    - 实时状态广播 (通过WebSocket)
    """

    AXIS_SUFFIX_MAP = {
        "": "L0", ".surge": "L1", ".sway": "L2",
        ".twist": "R0", ".roll": "R1", ".pitch": "R2",
        ".vib": "V0", ".suction": "A0",
    }

    def __init__(self, device_send_fn, broadcast_fn=None):
        self._send = device_send_fn
        self._broadcast = broadcast_fn
        self._scripts: dict[str, list[dict]] = {}  # axis → [{at, pos}, ...]
        self._playing = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._current_ms: int = 0
        self._start_time: float = 0
        self._pause_offset: float = 0
        self._speed: float = 1.0
        self._update_hz: int = 60
        self._lock = threading.Lock()
        # Safety
        self._max_speed: int = 15000
        self._pos_min: int = 0
        self._pos_max: int = 9999
        self._prev_positions: dict[str, int] = {}
        # Metadata
        self._title: str = ""
        self._video_file: str = ""

    def load_json(self, axis: str, data: dict) -> dict:
        """Load funscript JSON data for one axis"""
        self._speed = 1.0
        actions = data.get("actions", [])
        if not actions:
            return {"error": "No actions in funscript"}
        actions = sorted(actions, key=lambda a: a["at"])
        if data.get("inverted", False):
            actions = [{"at": a["at"], "pos": 100 - a["pos"]} for a in actions]
        with self._lock:
            self._scripts[axis] = actions
        dur = actions[-1]["at"] / 1000.0
        logger.info(f"Funscript loaded: {axis} → {len(actions)} actions, {dur:.1f}s")
        return {"axis": axis, "actions": len(actions), "duration_sec": dur}

    def load_multi(self, scripts_data: dict) -> dict:
        """Load multiple axes: {axis: {actions:[...]}, ...}"""
        results = {}
        for axis, data in scripts_data.items():
            results[axis] = self.load_json(axis, data)
        return results

    def clear(self):
        with self._lock:
            self._scripts.clear()
        self._prev_positions.clear()
        self._title = ""
        self._video_file = ""

    @property
    def duration_ms(self) -> int:
        if not self._scripts:
            return 0
        return max(
            (acts[-1]["at"] if acts else 0)
            for acts in self._scripts.values()
        )

    def _interpolate(self, actions: list[dict], time_ms: int) -> int:
        """Binary search + linear interpolation → position 0-100"""
        if not actions:
            return 50
        if time_ms <= actions[0]["at"]:
            return actions[0]["pos"]
        if time_ms >= actions[-1]["at"]:
            return actions[-1]["pos"]
        lo, hi = 0, len(actions) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if actions[mid]["at"] <= time_ms:
                lo = mid
            else:
                hi = mid
        a1, a2 = actions[lo], actions[hi]
        if a2["at"] == a1["at"]:
            return a2["pos"]
        t = (time_ms - a1["at"]) / (a2["at"] - a1["at"])
        return int(a1["pos"] + (a2["pos"] - a1["pos"]) * t)

    def _pos_to_tcode(self, pos: int) -> int:
        return int(max(0, min(100, pos)) / 100.0 * 9999)

    def _apply_safety(self, axis: str, tcode_pos: int) -> int:
        tcode_pos = max(self._pos_min, min(self._pos_max, tcode_pos))
        prev = self._prev_positions.get(axis, 5000)
        dt = 1.0 / self._update_hz
        velocity = abs(tcode_pos - prev) / dt if dt > 0 else 0
        if velocity > self._max_speed:
            direction = 1 if tcode_pos > prev else -1
            max_delta = int(self._max_speed * dt)
            tcode_pos = prev + direction * max_delta
            tcode_pos = max(self._pos_min, min(self._pos_max, tcode_pos))
        self._prev_positions[axis] = tcode_pos
        return tcode_pos

    def play(self):
        if not self._scripts:
            return
        if self._paused:
            self._paused = False
            self._start_time = time.time()
            return
        if self._playing:
            return
        self._playing = True
        self._paused = False
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def pause(self):
        if self._playing and not self._paused:
            self._paused = True
            self._pause_offset = self._current_ms / 1000.0

    def stop(self):
        self._playing = False
        self._paused = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self._current_ms = 0
        self._pause_offset = 0
        self._prev_positions.clear()
        try:
            self._send("D1")  # Home all
        except Exception:
            pass
        self._broadcast_status()

    def seek(self, time_ms: int):
        self._pause_offset = max(0, time_ms) / 1000.0
        self._start_time = time.time()
        self._current_ms = max(0, time_ms)

    def sync_time(self, video_time_ms: int):
        """Called by frontend to sync playback position with video"""
        drift = abs(self._current_ms - video_time_ms)
        if drift > 200:  # Re-sync if drift > 200ms
            self.seek(video_time_ms)

    def set_speed(self, speed: float):
        self._speed = max(0.1, min(5.0, speed))

    def _loop(self):
        interval = 1.0 / self._update_hz
        duration_ms = self.duration_ms
        broadcast_every = max(1, self._update_hz // 10)  # ~10fps broadcast
        frame = 0
        while self._playing:
            if self._paused:
                time.sleep(0.05)
                continue
            elapsed = (time.time() - self._start_time) * self._speed * 1000
            self._current_ms = int(elapsed + self._pause_offset * 1000)
            if self._current_ms >= duration_ms:
                self._playing = False
                self._broadcast_status()
                break
            # Generate TCode for all loaded axes
            commands = []
            with self._lock:
                for axis, actions in self._scripts.items():
                    pos = self._interpolate(actions, self._current_ms)
                    tcode_pos = self._pos_to_tcode(pos)
                    tcode_pos = self._apply_safety(axis, tcode_pos)
                    commands.append(f"{axis}{tcode_pos:04d}")
            if commands:
                self._send(" ".join(commands))
            frame += 1
            if frame % broadcast_every == 0:
                self._broadcast_status()
            time.sleep(interval)
        # Home when done
        try:
            self._send("D1")
        except Exception:
            pass

    def _broadcast_status(self):
        if self._broadcast:
            try:
                self._broadcast(self.status())
            except Exception:
                pass

    def status(self) -> dict:
        axes_info = {}
        with self._lock:
            for axis, actions in self._scripts.items():
                pos = self._interpolate(actions, self._current_ms) if actions else 50
                axes_info[axis] = {
                    "position": pos,
                    "tcode": self._pos_to_tcode(pos),
                    "actions": len(actions),
                }
        return {
            "playing": self._playing,
            "paused": self._paused,
            "current_ms": self._current_ms,
            "duration_ms": self.duration_ms,
            "progress_pct": round(self._current_ms / max(1, self.duration_ms) * 100, 1),
            "speed": self._speed,
            "axes": axes_info,
            "title": self._title,
            "video_file": self._video_file,
        }


class ORS6Hub:
    """ORS6 全链路开发中枢服务器"""

    def __init__(self, port: int = 8086):
        self.port = port
        self.device = VirtualORS6(tick_hz=120)
        self.test_runner = TestRunner(self.device)
        self._ws_clients: list[WSHandler] = []
        self._running = False
        self._lock = threading.Lock()
        self._pattern_thread = None
        self._pattern_running = False
        self._html_cache = None
        self._last_broadcast = 0
        self._broadcast_interval = 1.0 / 30  # 30fps max
        self.funscript_engine: Optional[FunscriptEngine] = None

    def _load_html(self) -> bytes:
        html_path = PROJECT_ROOT / "hub.html"
        if html_path.exists():
            return html_path.read_bytes()
        return b"<h1>hub.html not found</h1>"

    def _init_funscript_engine(self):
        """Initialize FunscriptEngine with Hub's device"""
        def broadcast_fs(status):
            msg = json.dumps({"type": "funscript_status", "data": status})
            with self._lock:
                for ws in self._ws_clients:
                    if not ws.closed:
                        ws.send(msg)
        self.funscript_engine = FunscriptEngine(
            device_send_fn=self.device.send,
            broadcast_fn=broadcast_fs,
        )

    def start(self, open_browser: bool = True):
        self.device.connect()
        self.device.on_state_change = self._broadcast_state
        self._init_funscript_engine()
        self._running = True

        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("0.0.0.0", self.port))
        server_sock.listen(5)
        server_sock.settimeout(1.0)

        url = f"http://localhost:{self.port}"
        print(f"\n  ORS6 Hub: {url}\n")

        if open_browser:
            import webbrowser
            threading.Timer(0.5, lambda: webbrowser.open(url)).start()

        threading.Thread(target=self._history_loop, daemon=True).start()

        try:
            while self._running:
                try:
                    conn, addr = server_sock.accept()
                    threading.Thread(target=self._handle, args=(conn, addr), daemon=True).start()
                except socket.timeout:
                    continue
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False
            server_sock.close()
            self.device.disconnect()

    def _handle(self, conn, addr):
        try:
            conn.settimeout(10)
            # Read until complete headers (double CRLF)
            raw = b""
            while b"\r\n\r\n" not in raw and len(raw) < 16384:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                raw += chunk
            data = raw.decode("utf-8", errors="ignore")
            if not data:
                conn.close()
                return

            first_line = data.split("\r\n")[0]

            # WebSocket upgrade
            if "upgrade: websocket" in data.lower():
                conn.sendall(WSHandler.handshake(data))
                conn.settimeout(5)
                ws = WSHandler(conn, addr)
                with self._lock:
                    self._ws_clients.append(ws)
                self._ws_loop(ws)
                return

            parts = first_line.split()
            path = parts[1] if len(parts) > 1 else "/"

            if path == "/" or path == "/index.html":
                self._send_bytes(conn, self._load_html(), "text/html; charset=utf-8")
            elif path == "/api/state":
                self._send_json(conn, self.device.get_state())
            elif path == "/api/history":
                self._send_json(conn, self.device.get_history(100))
            elif path == "/api/patterns":
                self._send_json(conn, {
                    "names": TempestStroke.list_patterns(),
                    "details": {n: self._pattern_detail(n) for n in TempestStroke.list_patterns()}
                })
            elif path.startswith("/api/pattern/"):
                name = path[len("/api/pattern/"):]
                self._send_json(conn, self._pattern_detail(name))
            elif path == "/api/health":
                self._send_json(conn, {
                    "status": "ok",
                    "uptime": round(time.time() - self.device._start_time, 1),
                    "device": self.device.is_connected,
                    "ws_clients": len(self._ws_clients),
                    "patterns": len(PATTERN_LIBRARY),
                    "port": self.port,
                })
            elif path == "/api/test/all":
                self._send_json(conn, self.test_runner.run_all())
            elif path == "/api/test/protocol":
                self._send_json(conn, self.test_runner.test_protocol())
            elif path == "/api/test/device":
                self._send_json(conn, self.test_runner.test_device())
            elif path == "/api/test/tempest":
                self._send_json(conn, self.test_runner.test_tempest())
            elif path.startswith("/api/send/"):
                cmd = unquote(path[len("/api/send/"):])
                result = self.device.send(cmd)
                self._send_json(conn, {"cmd": cmd, "result": result})
            elif path.startswith("/api/play/"):
                parts_p = unquote(path[len("/api/play/"):]).split('/')
                name = parts_p[0]
                bpm = int(parts_p[1]) if len(parts_p) > 1 else 60
                self._start_pattern(name, bpm)
                self._send_json(conn, {"status": "playing", "name": name, "bpm": bpm})
            elif path == "/api/stop":
                self._stop_pattern()
                self._send_json(conn, {"status": "stopped"})
            # ── Funscript API ──
            elif path == "/api/funscript/load" and first_line.startswith("POST"):
                body = self._read_post_body(raw, conn, data)
                if body:
                    try:
                        payload = json.loads(body)
                        fs_engine = self.funscript_engine
                        if "scripts" in payload:
                            result = fs_engine.load_multi(payload["scripts"])
                        else:
                            axis = payload.get("axis", "L0")
                            result = fs_engine.load_json(axis, payload)
                        fs_engine._title = payload.get("title", "")
                        fs_engine._video_file = payload.get("video_file", "")
                        self._send_json(conn, {"status": "loaded", "result": result,
                                               "duration_ms": fs_engine.duration_ms})
                    except Exception as e:
                        self._send_json(conn, {"error": str(e)})
                else:
                    self._send_json(conn, {"error": "No body"})
            elif path == "/api/funscript/play":
                self._stop_pattern(home=False)
                self.funscript_engine.play()
                self._send_json(conn, self.funscript_engine.status())
            elif path == "/api/funscript/pause":
                self.funscript_engine.pause()
                self._send_json(conn, self.funscript_engine.status())
            elif path == "/api/funscript/stop":
                self.funscript_engine.stop()
                self._send_json(conn, self.funscript_engine.status())
            elif path.startswith("/api/funscript/seek/"):
                ms = int(path.split("/")[-1])
                self.funscript_engine.seek(ms)
                self._send_json(conn, self.funscript_engine.status())
            elif path.startswith("/api/funscript/sync/"):
                ms = int(path.split("/")[-1])
                self.funscript_engine.sync_time(ms)
                self._send_json(conn, {"synced": ms})
            elif path.startswith("/api/funscript/speed/"):
                spd = float(path.split("/")[-1])
                self.funscript_engine.set_speed(spd)
                self._send_json(conn, self.funscript_engine.status())
            elif path == "/api/funscript/status":
                self._send_json(conn, self.funscript_engine.status())
            elif path == "/api/funscript/clear":
                self.funscript_engine.stop()
                self.funscript_engine.clear()
                self._send_json(conn, {"status": "cleared"})
            elif path == "/api/funscript/scan":
                scripts = self._scan_local_funscripts()
                self._send_json(conn, {"scripts": scripts})
            elif path.startswith("/api/funscript/load-local/"):
                rel_path = unquote(path[len("/api/funscript/load-local/"):])
                result = self._load_local_funscript(rel_path)
                self._send_json(conn, result)
            elif path == "/hip_sync" or path == "/hip_sync.html":
                hip_path = PROJECT_ROOT / "hip_sync.html"
                if hip_path.exists():
                    self._send_bytes(conn, hip_path.read_bytes(), "text/html; charset=utf-8")
                else:
                    self._send_404(conn)
            elif path.startswith("/video/"):
                fname = unquote(path[len("/video/"):])
                vpath = PROJECT_ROOT / "douyin_cache" / fname
                if vpath.exists() and vpath.suffix in ('.mp4','.webm','.mkv','.wav','.mp3'):
                    ct = {"mp4":"video/mp4","webm":"video/webm","mkv":"video/x-matroska",
                          "wav":"audio/wav","mp3":"audio/mpeg"}.get(vpath.suffix[1:], "application/octet-stream")
                    self._send_bytes(conn, vpath.read_bytes(), ct)
                else:
                    self._send_404(conn)
            elif "favicon" in path:
                self._send_empty(conn, 204)
            else:
                self._send_404(conn)
        except Exception as e:
            logger.debug(f"Connection error: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _pattern_detail(self, name: str) -> dict:
        params = PATTERN_LIBRARY.get(name, {})
        return {
            "name": name,
            "axes": list(params.keys()),
            "axis_count": len(params),
            "params": {
                axis: {
                    "from": p.get("from", 0), "to": p.get("to", 1),
                    "phase": p.get("phase", 0), "ecc": p.get("ecc", 0),
                    "motion": p.get("motion", "tempest"),
                } for axis, p in params.items()
            }
        }

    def _ws_loop(self, ws: WSHandler):
        ws.conn.settimeout(1)  # Short timeout for responsive shutdown
        try:
            while not ws.closed and self._running:
                msg = ws.recv()
                if msg is None:
                    break
                if not msg:
                    continue  # Timeout, no client message
                try:
                    data = json.loads(msg)
                    msg_type = data.get("type")
                    if msg_type == "command":
                        cmd = data.get("cmd", "")
                        if cmd:
                            self.device.send(cmd)
                    elif msg_type == "get_patterns":
                        names = TempestStroke.list_patterns()
                        ws.send(json.dumps({"type": "patterns", "data": names}))
                    elif msg_type == "pattern_play":
                        self._start_pattern(data.get("name", ""), data.get("bpm", 60))
                    elif msg_type == "pattern_stop":
                        self._stop_pattern()
                    elif msg_type == "run_tests":
                        scope = data.get("scope", "all")
                        if scope == "protocol":
                            results = self.test_runner.test_protocol()
                        elif scope == "device":
                            results = self.test_runner.test_device()
                        elif scope == "tempest":
                            results = self.test_runner.test_tempest()
                        else:
                            results = self.test_runner.run_all()
                        ws.send(json.dumps({"type": "test_results", "data": results}))
                    elif msg_type == "parse_funscript":
                        content = data.get("content", "")
                        try:
                            fs = json.loads(content)
                            actions = fs.get("actions", [])
                            result = {
                                "action_count": len(actions),
                                "duration_ms": actions[-1]["at"] if actions else 0,
                                "min_pos": min(a["pos"] for a in actions) if actions else 0,
                                "max_pos": max(a["pos"] for a in actions) if actions else 0,
                                "avg_pos": round(sum(a["pos"] for a in actions) / len(actions), 1) if actions else 0,
                            }
                            ws.send(json.dumps({"type": "funscript_parsed", "data": result}))
                        except Exception as e:
                            ws.send(json.dumps({"type": "funscript_error", "error": str(e)}))
                    # ── Funscript Engine WS commands ──
                    elif msg_type == "funscript_load":
                        fse = self.funscript_engine
                        if "scripts" in data:
                            result = fse.load_multi(data["scripts"])
                        else:
                            axis = data.get("axis", "L0")
                            result = fse.load_json(axis, data)
                        fse._title = data.get("title", "")
                        fse._video_file = data.get("video_file", "")
                        ws.send(json.dumps({"type": "funscript_loaded",
                                            "data": {"result": result, "duration_ms": fse.duration_ms}}))
                    elif msg_type == "funscript_play":
                        self._stop_pattern(home=False)
                        self.funscript_engine.play()
                        ws.send(json.dumps({"type": "funscript_status", "data": self.funscript_engine.status()}))
                    elif msg_type == "funscript_pause":
                        self.funscript_engine.pause()
                        ws.send(json.dumps({"type": "funscript_status", "data": self.funscript_engine.status()}))
                    elif msg_type == "funscript_stop":
                        self.funscript_engine.stop()
                        ws.send(json.dumps({"type": "funscript_status", "data": self.funscript_engine.status()}))
                    elif msg_type == "funscript_seek":
                        self.funscript_engine.seek(data.get("time_ms", 0))
                        ws.send(json.dumps({"type": "funscript_status", "data": self.funscript_engine.status()}))
                    elif msg_type == "funscript_sync":
                        self.funscript_engine.sync_time(data.get("time_ms", 0))
                    elif msg_type == "funscript_speed":
                        self.funscript_engine.set_speed(data.get("speed", 1.0))
                    elif msg_type == "funscript_clear":
                        self.funscript_engine.stop()
                        self.funscript_engine.clear()
                        ws.send(json.dumps({"type": "funscript_status", "data": self.funscript_engine.status()}))
                    elif msg_type == "funscript_get_status":
                        ws.send(json.dumps({"type": "funscript_status", "data": self.funscript_engine.status()}))
                except json.JSONDecodeError:
                    pass
        finally:
            with self._lock:
                if ws in self._ws_clients:
                    self._ws_clients.remove(ws)
            ws.close()

    def _broadcast_state(self, state: dict):
        now = time.monotonic()
        if now - self._last_broadcast < self._broadcast_interval:
            return  # Throttle to 30fps
        self._last_broadcast = now
        msg = json.dumps({"type": "state", "data": state})
        with self._lock:
            dead = []
            for ws in self._ws_clients:
                if ws.closed:
                    dead.append(ws)
                    continue
                try:
                    ws.send(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._ws_clients.remove(ws)

    def _history_loop(self):
        while self._running:
            time.sleep(1.0)
            history = self.device.get_history(50)
            if history:
                msg = json.dumps({"type": "history", "data": history})
                with self._lock:
                    for ws in self._ws_clients:
                        if not ws.closed:
                            ws.send(msg)

    def _start_pattern(self, name: str, bpm: float = 60):
        self._stop_pattern(home=False)
        try:
            stroke = TempestStroke(name, bpm=bpm)
        except ValueError:
            return
        self._pattern_running = True

        def loop():
            idx = 0
            freq = 60.0
            interval_ms = int(1000 / freq)
            while self._pattern_running and self._running:
                cmd = stroke.generate_tcode(idx, frequency=freq, interval_ms=interval_ms)
                self.device.send(cmd)
                idx += 1
                time.sleep(1.0 / freq)

        self._pattern_thread = threading.Thread(target=loop, daemon=True)
        self._pattern_thread.start()

    def _stop_pattern(self, home: bool = True):
        self._pattern_running = False
        if self._pattern_thread:
            self._pattern_thread.join(timeout=1)
            self._pattern_thread = None
        if home:
            self.device.send("D1")

    def _read_post_body(self, raw: bytes, conn, header_text: str) -> Optional[str]:
        """Read POST body from HTTP request"""
        content_length = 0
        for line in header_text.split("\r\n"):
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":", 1)[1].strip())
                break
        if content_length <= 0:
            return None
        # Body may already be partially in raw (after headers)
        header_end = raw.find(b"\r\n\r\n")
        if header_end < 0:
            return None
        body_start = header_end + 4
        body_so_far = raw[body_start:]
        while len(body_so_far) < content_length:
            try:
                chunk = conn.recv(min(8192, content_length - len(body_so_far)))
                if not chunk:
                    break
                body_so_far += chunk
            except Exception:
                break
        return body_so_far.decode("utf-8", errors="ignore")

    def _scan_local_funscripts(self) -> list[dict]:
        """Scan project directory for .funscript files"""
        results = []
        for fs_path in PROJECT_ROOT.rglob("*.funscript"):
            try:
                rel = str(fs_path.relative_to(PROJECT_ROOT))
                size = fs_path.stat().st_size
                # Quick parse for action count
                with open(fs_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                actions = data.get("actions", [])
                dur = actions[-1]["at"] / 1000.0 if actions else 0
                # Infer axis from filename
                # Infer axis: strip .funscript, then check known suffixes
                name_no_ext = fs_path.name.rsplit('.funscript', 1)[0] if '.funscript' in fs_path.name.lower() else fs_path.stem
                axis = "L0"
                for suffix, ax in FunscriptEngine.AXIS_SUFFIX_MAP.items():
                    if suffix and name_no_ext.endswith(suffix.lstrip(".")):
                        axis = ax
                        break
                results.append({
                    "path": rel, "axis": axis,
                    "actions": len(actions), "duration_sec": round(dur, 1),
                    "size": size,
                })
            except Exception:
                pass
        results.sort(key=lambda x: x["path"])
        return results

    def _load_local_funscript(self, rel_path: str) -> dict:
        """Load a local .funscript file by relative path"""
        try:
            fs_path = (PROJECT_ROOT / rel_path).resolve()
            # Security: ensure path is under project root
            if not str(fs_path).startswith(str(PROJECT_ROOT.resolve())):
                return {"error": "Path outside project"}
            if not fs_path.exists():
                return {"error": f"File not found: {rel_path}"}
            with open(fs_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Infer axis from filename
            name_no_ext = fs_path.name.rsplit('.funscript', 1)[0] if '.funscript' in fs_path.name.lower() else fs_path.stem
            axis = "L0"
            for suffix, ax in FunscriptEngine.AXIS_SUFFIX_MAP.items():
                if suffix and name_no_ext.endswith(suffix.lstrip(".")):
                    axis = ax
                    break
            result = self.funscript_engine.load_json(axis, data)
            return {"status": "loaded", "result": {axis: result},
                    "duration_ms": self.funscript_engine.duration_ms, "path": rel_path}
        except Exception as e:
            return {"error": str(e)}

    def _send_bytes(self, conn, body: bytes, content_type: str):
        header = (
            f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
        )
        conn.sendall(header.encode() + body)

    def _send_json(self, conn, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        header = (
            f"HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\nAccess-Control-Allow-Origin: *\r\n"
            f"Connection: close\r\n\r\n"
        )
        conn.sendall(header.encode() + body)

    def _send_empty(self, conn, status=204):
        conn.sendall(f"HTTP/1.1 {status} No Content\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode())

    def _send_404(self, conn):
        body = b"Not Found"
        conn.sendall(f"HTTP/1.1 404 Not Found\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode() + body)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ORS6 Hub")
    parser.add_argument("--port", type=int, default=8086)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--serial", type=str, default=None,
                        help="Connect to real device on serial port (e.g. COM6)")
    parser.add_argument("--baud", type=int, default=115200,
                        help="Serial baud rate (default: 115200)")
    parser.add_argument("--auto-detect", action="store_true",
                        help="Auto-detect ORS6 serial port")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname).1s] %(message)s")

    hub = ORS6Hub(port=args.port)

    if args.serial or args.auto_detect:
        adapter = SerialDeviceAdapter(
            port=args.serial, baudrate=args.baud,
            auto_detect=args.auto_detect
        )
        if adapter.connect():
            hub.device = adapter
            hub.test_runner = TestRunner(adapter)
            logger.info(f"Using real device: {adapter._serial.port} @ {args.baud}bps")
        else:
            logger.warning("Failed to connect to real device, falling back to virtual")
            # List available ports for debugging
            ports = TCodeSerial.list_ports()
            if ports:
                logger.info(f"Available ports: {', '.join(p['port'] + ' (' + p['description'] + ')' for p in ports)}")
            else:
                logger.info("No serial ports found")

    hub.start(open_browser=not args.no_browser)
