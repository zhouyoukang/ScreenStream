#!/usr/bin/env python3
"""
RayNeo V3 Hybrid Simulator v3.0
WebSocket server: 浏览器模拟器 ←→ 五感引擎 ←→ 实机ADB

双模式:
  SIM  — 纯虚拟仿真（无需眼镜）
  LIVE — 实机ADB数据实时流式传输

端口: WS=8767, HTTP=8768
协议: JSON over WebSocket
依赖: websockets (pip install websockets)

用法:
  python rayneo_sim_server.py              # 自动检测模式
  python rayneo_sim_server.py --mode sim   # 强制仿真模式
  python rayneo_sim_server.py --mode live  # 强制实机模式
"""

import asyncio
import json
import time
import threading
import os
import sys
import subprocess
import re
import random
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

try:
    import websockets
    import websockets.server
except ImportError:
    print("needs websockets: pip install websockets")
    sys.exit(1)

# ─── ADB/wireless_config 桥接 ─────────────────────────────
_PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_DIR))
try:
    from wireless_config import wm, ADB, GLASS_USB_SERIAL
    HAS_WIRELESS_CONFIG = True
except ImportError:
    HAS_WIRELESS_CONFIG = False
    ADB = "adb"
    GLASS_USB_SERIAL = "841571AC688C360"

def _adb(*args, timeout=5):
    # 优先使用wireless_config的动态地址（支持WiFi），回退USB序列号
    device = wm.glass_addr if HAS_WIRELESS_CONFIG else GLASS_USB_SERIAL
    try:
        r = subprocess.run([ADB, "-s", device] + list(args),
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""

def _glasses_online():
    try:
        out = subprocess.run([ADB, "devices"], capture_output=True, text=True, timeout=3).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and GLASS_USB_SERIAL in parts[0] and parts[1] == "device":
                return True
        if HAS_WIRELESS_CONFIG:
            addr = wm.glass_addr
            if addr != GLASS_USB_SERIAL:
                for line in out.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and addr in parts[0] and parts[1] == "device":
                        return True
    except Exception:
        pass
    return False

# ─── 虚拟设备状态 ────────────────────────────────────────
class VirtualGlasses:
    """虚拟RayNeo V3 (XRGF50) 完整硬件仿真"""
    DEVICE_INFO = {
        "model": "XRGF50", "product": "RayNeoV3", "device": "Mars",
        "soc": "Snapdragon AR1", "android": 12, "api": 31,
        "build": "SKQ1.240815.001 3D7I", "serial": "841571AC688C360",
        "camera": "Sony IMX681 12MP", "imu": "STM LSM6DSR 415Hz",
        "tp": "Cypress CYTTSP5 (1D X-axis)", "battery_cap": "159mAh",
        "wifi": "WCN7851 WiFi6E", "speaker": "Dual + AW88166",
        "mic": "3x MEMS", "sdk": "MarsAndroidSDK v1.0.1",
    }
    def __init__(self):
        self.online = True
        self.battery = 85
        self.is_worn = True
        self.light = 250.0
        self.proximity = 1.0        # 0=far 1=near (佩戴辅助)
        # IMU (LSM6DSR)
        self.accel = [0.0, 0.0, 9.8]   # x, y, z (m/s²)
        self.gyro = [0.0, 0.0, 0.0]     # x, y, z (rad/s)
        self.quaternion = [1.0, 0.0, 0.0, 0.0]  # w, x, y, z
        self.head_pose = "neutral"       # neutral/up/down/left/right/nod/shake
        # TP (cyttsp5_mt)
        self.tp_x = 640
        self.tp_touching = False
        # Audio
        self.volume = 80
        self.last_tts = ""
        self.tts_playing = False
        self.mic_recording = False
        self.wake_word_active = True
        # Camera (IMX681)
        self.last_photo = None
        self.camera_active = False
        self.last_ai_result = ""
        # System
        self.brightness = 128
        self.wifi_connected = True
        self.wifi_ssid = "HomeWiFi"
        self.wifi_rssi = -45
        self.charging = False
        self.screen_width = 1920
        self.screen_height = 1080
        # 事件日志
        self.events = []
        self._lock = threading.Lock()

    def to_dict(self):
        with self._lock:
            return {
                "online": self.online,
                "battery": self.battery,
                "is_worn": self.is_worn,
                "light": self.light,
                "proximity": self.proximity,
                "accel": self.accel,
                "gyro": self.gyro,
                "quaternion": self.quaternion,
                "head_pose": self.head_pose,
                "tp_x": self.tp_x,
                "tp_touching": self.tp_touching,
                "volume": self.volume,
                "brightness": self.brightness,
                "last_tts": self.last_tts,
                "tts_playing": self.tts_playing,
                "mic_recording": self.mic_recording,
                "camera_active": self.camera_active,
                "last_ai_result": self.last_ai_result,
                "wifi": {"connected": self.wifi_connected, "ssid": self.wifi_ssid, "rssi": self.wifi_rssi},
                "charging": self.charging,
                "screen": [self.screen_width, self.screen_height],
            }

    def add_event(self, event_type, data=None):
        with self._lock:
            ev = {"type": event_type, "time": time.time(), "data": data}
            self.events.append(ev)
            if len(self.events) > 200:
                self.events = self.events[-100:]
            return ev

# ─── 全局状态 ────────────────────────────────────────────
glasses = VirtualGlasses()
clients = set()
current_mode = "sim"   # "sim" | "live"
_live_poll_task = None

# ─── 传感器录制/回放 ──────────────────────────────────────
class SensorRecorder:
    def __init__(self):
        self.recording = False
        self.playing = False
        self.frames = []
        self._start_ts = 0
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            self.frames = []
            self._start_ts = time.time()
            self.recording = True

    def stop(self):
        with self._lock:
            self.recording = False
            return len(self.frames)

    def capture(self, state_dict):
        with self._lock:
            if not self.recording:
                return
            self.frames.append({
                "t": round(time.time() - self._start_ts, 3),
                "s": state_dict
            })

    def save(self, path):
        with self._lock:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.frames, f)
            return len(self.frames)

    def load(self, path):
        with self._lock:
            with open(path, "r", encoding="utf-8") as f:
                self.frames = json.load(f)
            return len(self.frames)

    def status(self):
        return {
            "recording": self.recording,
            "playing": self.playing,
            "frame_count": len(self.frames),
            "duration": self.frames[-1]["t"] if self.frames else 0
        }

recorder = SensorRecorder()

# ─── 场景预设 (无实机全流程测试) ─────────────────────────────
SCENARIOS = {
    "outdoor_walk": {"name": "户外行走", "steps": [
        {"t":0, "env":{"light":5000,"battery":90,"is_worn":True}},
        {"t":1, "imu":[0.5,0.2,9.6]}, {"t":2, "imu":[-0.3,0.1,9.9]},
        {"t":3, "voice":"小雷小雷 前面是什么路"},
        {"t":4, "ai":"前方是中山路，距地铁站约200米"},
        {"t":6, "imu":[0.2,0.5,9.5]}, {"t":8, "env":{"light":3000}},
    ]},
    "indoor_office": {"name": "室内办公", "steps": [
        {"t":0, "env":{"light":400,"battery":70}},
        {"t":2, "gesture":"tap"}, {"t":3, "ai":"下午3点有会议"},
        {"t":5, "gesture":"slide_forward"}, {"t":6, "ai":"邮件：进度报告已收到"},
    ]},
    "night_dark": {"name": "夜间暗光", "steps": [
        {"t":0, "env":{"light":10,"battery":25,"brightness":50}},
        {"t":2, "gesture":"tap"}, {"t":3, "ai":"夜间场景：路灯、行人"},
        {"t":5, "env":{"battery":23}},
    ]},
    "wear_cycle": {"name": "摘戴循环", "steps": [
        {"t":0, "env":{"is_worn":True}}, {"t":2, "env":{"is_worn":False}},
        {"t":4, "env":{"is_worn":True}}, {"t":6, "env":{"is_worn":False}},
        {"t":8, "env":{"is_worn":True}},
    ]},
    "battery_drain": {"name": "电量耗尽", "steps": [
        {"t":0, "env":{"battery":30}}, {"t":2, "env":{"battery":20}},
        {"t":3, "tts":"电量不足20%"}, {"t":5, "env":{"battery":10}},
        {"t":7, "env":{"battery":5}}, {"t":8, "tts":"电量严重不足"},
    ]},
    "full_gestures": {"name": "全手势测试", "steps": [
        {"t":0, "gesture":"tap"}, {"t":1.5, "gesture":"double_tap"},
        {"t":3, "gesture":"triple_click"}, {"t":4.5, "gesture":"long_press"},
        {"t":6, "gesture":"slide_forward"}, {"t":7.5, "gesture":"slide_back"},
    ]},
}
_scenario_task = None

async def _run_scenario(name):
    global _scenario_task
    sc = SCENARIOS.get(name)
    if not sc:
        return
    steps = sc["steps"]
    await broadcast({"type": "scenario", "action": "start", "name": name, "total": len(steps)})
    glasses.add_event("scenario", {"name": name, "action": "start"})
    prev_t = 0
    for i, step in enumerate(steps):
        dt = step["t"] - prev_t
        if dt > 0:
            await asyncio.sleep(dt)
        prev_t = step["t"]
        if "env" in step:
            for k, v in step["env"].items():
                if hasattr(glasses, k):
                    setattr(glasses, k, v)
            await broadcast({"type": "state", "data": glasses.to_dict()})
        if "imu" in step:
            glasses.accel = step["imu"]
            ax, ay = glasses.accel[0], glasses.accel[1]
            glasses.head_pose = "up" if ay>5 else "down" if ay<-5 else "right" if ax>5 else "left" if ax<-5 else "neutral"
            await broadcast({"type": "imu", "data": {"accel": glasses.accel, "gyro": glasses.gyro, "head_pose": glasses.head_pose}})
        if "gesture" in step:
            ev = glasses.add_event("gesture", {"gesture": step["gesture"]})
            await broadcast({"type": "event", "event": ev})
            await execute_gesture(step["gesture"])
        if "voice" in step:
            ev = glasses.add_event("voice_input", {"text": step["voice"]})
            await broadcast({"type": "event", "event": ev})
        if "tts" in step:
            glasses.last_tts = step["tts"]
            glasses.tts_playing = True
            await broadcast({"type": "tts_play", "text": step["tts"]})
            asyncio.get_running_loop().call_later(2, lambda: setattr(glasses, 'tts_playing', False))
        if "ai" in step:
            glasses.last_ai_result = step["ai"]
            await broadcast({"type": "ai_result", "text": step["ai"]})
        if recorder.recording:
            recorder.capture(glasses.to_dict())
        await broadcast({"type": "scenario", "action": "step", "index": i+1, "total": len(steps)})
    glasses.add_event("scenario", {"name": name, "action": "done"})
    await broadcast({"type": "scenario", "action": "done", "name": name})
    _scenario_task = None

# ─── Live模式ADB轮询 ──────────────────────────────────────
def _parse_sensor_nums(line):
    nums = re.findall(r'[-+]?\d*\.?\d+', line)
    return [float(x) for x in nums[:3]] if len(nums) >= 3 else None

async def _live_poll_loop():
    global current_mode
    while current_mode == "live":
        try:
            batt = _adb("shell", "dumpsys battery 2>/dev/null | grep level")
            m = re.search(r'(\d+)', batt)
            if m:
                glasses.battery = int(m.group(1))

            prox = _adb("shell", "dumpsys sensorservice 2>/dev/null | grep -A2 Proximity")
            if "1.0" in prox or "5.0" in prox:
                glasses.is_worn = True
            elif "0.0" in prox:
                glasses.is_worn = False

            light = _adb("shell", "dumpsys sensorservice 2>/dev/null | grep -A2 Light")
            lv = _parse_sensor_nums(light)
            if lv:
                glasses.light = lv[0]

            bright = _adb("shell", "settings get system screen_brightness")
            bm = re.search(r'(\d+)', bright)
            if bm:
                glasses.brightness = int(bm.group(1))

            glasses.online = True
            await broadcast({"type": "state", "data": glasses.to_dict()})
            if recorder.recording:
                recorder.capture(glasses.to_dict())
        except Exception:
            glasses.online = False
            await broadcast({"type": "state", "data": glasses.to_dict()})
        await asyncio.sleep(2)

async def switch_mode(mode):
    global current_mode, _live_poll_task
    if mode == current_mode:
        return
    old = current_mode
    current_mode = mode
    if _live_poll_task and not _live_poll_task.done():
        _live_poll_task.cancel()
        _live_poll_task = None
    if mode == "live":
        if _glasses_online():
            _live_poll_task = asyncio.ensure_future(_live_poll_loop())
            glasses.add_event("mode", {"mode": "live", "adb": True})
        else:
            current_mode = "sim"
            glasses.add_event("mode", {"mode": "sim", "reason": "glasses_offline"})
    else:
        glasses.add_event("mode", {"mode": "sim"})
    await broadcast({"type": "mode", "mode": current_mode, "prev": old})
    await broadcast({"type": "state", "data": glasses.to_dict()})

async def _playback_loop():
    if not recorder.frames:
        return
    recorder.playing = True
    await broadcast({"type": "rec_status", "data": recorder.status()})
    prev_t = 0
    for frame in recorder.frames:
        if not recorder.playing:
            break
        dt = frame["t"] - prev_t
        if dt > 0:
            await asyncio.sleep(dt)
        prev_t = frame["t"]
        for k, v in frame["s"].items():
            if hasattr(glasses, k):
                setattr(glasses, k, v)
        await broadcast({"type": "state", "data": glasses.to_dict()})
    recorder.playing = False
    await broadcast({"type": "rec_status", "data": recorder.status()})

# ─── WebSocket 广播 ──────────────────────────────────────
async def broadcast(msg):
    if clients:
        data = json.dumps(msg)
        await asyncio.gather(
            *[c.send(data) for c in clients],
            return_exceptions=True
        )

# ─── WebSocket 处理 ──────────────────────────────────────
async def handle_client(websocket):
    clients.add(websocket)
    addr = websocket.remote_address
    print(f"  [WS] 客户端连接: {addr}")
    # 发送初始状态 + 模式
    await websocket.send(json.dumps({
        "type": "state",
        "data": glasses.to_dict()
    }))
    await websocket.send(json.dumps({
        "type": "mode",
        "mode": current_mode
    }))
    try:
        async for message in websocket:
            try:
                msg = json.loads(message)
                await process_message(msg, websocket)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"type": "error", "msg": "Invalid JSON"}))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)
        print(f"  [WS] 客户端断开: {addr}")

async def process_message(msg, ws):
    """处理来自浏览器模拟器的消息"""
    msg_type = msg.get("type", "")

    if msg_type == "get_state":
        await ws.send(json.dumps({"type": "state", "data": glasses.to_dict()}))

    elif msg_type == "tp_touch":
        # 触控板事件: {x: 0-1279, action: "down"|"move"|"up"}
        glasses.tp_x = msg.get("x", 640)
        action = msg.get("action", "move")
        glasses.tp_touching = action != "up"
        ev = glasses.add_event("tp", {"x": glasses.tp_x, "action": action})
        await broadcast({"type": "event", "event": ev})

    elif msg_type == "tp_gesture":
        # 手势: {gesture: "tap"|"double_tap"|"slide_fwd"|"slide_forward"|"slide_back"|"long_press"}
        gesture = msg.get("gesture", "tap")
        ev = glasses.add_event("gesture", {"gesture": gesture})
        await broadcast({"type": "event", "event": ev})
        # 执行对应动作
        await execute_gesture(gesture)

    elif msg_type == "button":
        # 按钮: {button: "action"|"vol_up"|"vol_down", action: "press"|"release"|"long_press"}
        ev = glasses.add_event("button", msg)
        await broadcast({"type": "event", "event": ev})

    elif msg_type == "imu":
        # IMU数据: {accel: [x,y,z], gyro: [x,y,z]}
        if "accel" in msg:
            glasses.accel = msg["accel"]
        if "gyro" in msg:
            glasses.gyro = msg["gyro"]
        # 推断头部姿态
        ax, ay, az = glasses.accel
        if ay > 5:
            glasses.head_pose = "up"
        elif ay < -5:
            glasses.head_pose = "down"
        elif ax > 5:
            glasses.head_pose = "right"
        elif ax < -5:
            glasses.head_pose = "left"
        else:
            glasses.head_pose = "neutral"
        await broadcast({"type": "imu", "data": {
            "accel": glasses.accel, "gyro": glasses.gyro,
            "head_pose": glasses.head_pose
        }})

    elif msg_type == "set_env":
        # 环境参数: {light, worn, battery, brightness, volume, charging, wifi_connected, wifi_rssi, proximity}
        env_keys = ["light", "brightness", "battery", "volume", "proximity", "wifi_rssi"]
        for k in env_keys:
            if k in msg:
                setattr(glasses, k, msg[k])
        if "worn" in msg:
            glasses.is_worn = msg["worn"]
            glasses.proximity = 1.0 if msg["worn"] else 0.0
        if "charging" in msg:
            glasses.charging = msg["charging"]
        if "wifi_connected" in msg:
            glasses.wifi_connected = msg["wifi_connected"]
        if "wifi_ssid" in msg:
            glasses.wifi_ssid = msg["wifi_ssid"]
        await broadcast({"type": "state", "data": glasses.to_dict()})

    elif msg_type == "tts":
        text = msg.get("text", "")
        glasses.last_tts = text
        glasses.tts_playing = True
        ev = glasses.add_event("tts", {"text": text})
        await broadcast({"type": "tts_play", "text": text})
        asyncio.get_running_loop().call_later(
            max(1, len(text) * 0.12),
            lambda: setattr(glasses, 'tts_playing', False)
        )

    elif msg_type == "speak":
        text = msg.get("text", "")
        ev = glasses.add_event("voice_input", {"text": text})
        await broadcast({"type": "event", "event": ev})
        # 模拟AI回复
        if text.startswith("小雷小雷"):
            query = text.replace("小雷小雷", "").strip()
            ai_resp = f"[SIM AI] 收到：{query}" if query else "[SIM AI] 语音唤醒成功"
            glasses.last_ai_result = ai_resp
            await asyncio.sleep(0.5)
            await broadcast({"type": "ai_result", "text": ai_resp})

    elif msg_type == "voice_wakeup":
        ev = glasses.add_event("voice_wakeup", {"keyword": "小雷小雷"})
        await broadcast({"type": "event", "event": ev})
        await broadcast({"type": "action", "action": "wakeup", "msg": "🎤 语音唤醒: 小雷小雷"})

    elif msg_type == "photo":
        glasses.camera_active = True
        ev = glasses.add_event("photo", {"status": "capturing"})
        await broadcast({"type": "event", "event": ev})
        await broadcast({"type": "state", "data": glasses.to_dict()})
        await asyncio.sleep(0.3)
        # 模拟AI识别
        scenes = ["室内办公桌：显示器、键盘、咖啡杯", "户外街道：行人、车辆、路牌",
                   "餐厅场景：菜单、餐具、食物", "自然风景：树木、天空、小路"]
        ai_result = random.choice(scenes)
        glasses.last_ai_result = ai_result
        glasses.camera_active = False
        await broadcast({"type": "photo_result", "status": "ok",
                         "msg": f"📸 拍照完成", "ai": ai_result})
        await broadcast({"type": "ai_result", "text": ai_result})
        await broadcast({"type": "state", "data": glasses.to_dict()})

    elif msg_type == "mic":
        action = msg.get("action", "toggle")
        if action == "start" or (action == "toggle" and not glasses.mic_recording):
            glasses.mic_recording = True
            glasses.add_event("mic", {"action": "start"})
        else:
            glasses.mic_recording = False
            glasses.add_event("mic", {"action": "stop"})
        await broadcast({"type": "state", "data": glasses.to_dict()})

    elif msg_type == "set_volume":
        glasses.volume = max(0, min(100, msg.get("volume", 80)))
        await broadcast({"type": "state", "data": glasses.to_dict()})

    elif msg_type == "scenario":
        global _scenario_task
        action = msg.get("action", "run")
        name = msg.get("name", "")
        if action == "run" and name in SCENARIOS:
            if _scenario_task and not _scenario_task.done():
                _scenario_task.cancel()
            _scenario_task = asyncio.ensure_future(_run_scenario(name))
        elif action == "stop" and _scenario_task and not _scenario_task.done():
            _scenario_task.cancel()
            _scenario_task = None
            await broadcast({"type": "scenario", "action": "stopped"})
        elif action == "list":
            listing = {k: {"name": v["name"], "steps": len(v["steps"])} for k, v in SCENARIOS.items()}
            await ws.send(json.dumps({"type": "scenarios", "data": listing}))

    elif msg_type == "adb_cmd":
        # LIVE模式ADB命令代理
        if current_mode == "live" and _glasses_online():
            cmd = msg.get("cmd", "")
            if cmd and len(cmd) < 200:
                result = _adb("shell", cmd, timeout=8)
                await ws.send(json.dumps({"type": "adb_result", "cmd": cmd, "output": result}))
            else:
                await ws.send(json.dumps({"type": "adb_result", "cmd": cmd, "output": "[error] invalid cmd"}))
        else:
            await ws.send(json.dumps({"type": "adb_result", "cmd": msg.get("cmd",""), "output": "[SIM mode] ADB not available"}))

    elif msg_type == "get_events":
        # 获取最近事件
        count = msg.get("count", 50)
        await ws.send(json.dumps({
            "type": "events",
            "data": glasses.events[-count:]
        }))

    elif msg_type == "set_mode":
        # 模式切换: {mode: "sim"|"live"}
        await switch_mode(msg.get("mode", "sim"))

    elif msg_type == "rec_start":
        recorder.start()
        await broadcast({"type": "rec_status", "data": recorder.status()})

    elif msg_type == "rec_stop":
        n = recorder.stop()
        await broadcast({"type": "rec_status", "data": recorder.status()})

    elif msg_type == "rec_play":
        asyncio.ensure_future(_playback_loop())

    elif msg_type == "rec_save":
        path = _PROJECT_DIR / "recordings" / f"rec_{int(time.time())}.json"
        path.parent.mkdir(exist_ok=True)
        n = recorder.save(str(path))
        await broadcast({"type": "rec_saved", "path": str(path), "frames": n})

async def execute_gesture(gesture):
    """执行手势对应的五感动作"""
    if gesture == "tap":
        await broadcast({"type": "action", "action": "photo",
                         "msg": "📸 单击 → 拍照识别"})
    elif gesture == "double_tap":
        await broadcast({"type": "action", "action": "ask_ai",
                         "msg": "🤖 双击 → AI问答"})
    elif gesture in ("slide_fwd", "slide_forward"):
        await broadcast({"type": "action", "action": "next",
                         "msg": "➡️ 前滑 → 下一项"})
    elif gesture in ("slide_back",):
        await broadcast({"type": "action", "action": "prev",
                         "msg": "⬅️ 后滑 → 上一项"})
    elif gesture == "long_press":
        await broadcast({"type": "action", "action": "status",
                         "msg": "📊 长按 → 状态报告"})
        # 发送完整状态
        await broadcast({"type": "state", "data": glasses.to_dict()})

# ─── HTTP REST API + 静态文件服务 ─────────────────────────
_MIME = {
    ".html": "text/html", ".js": "application/javascript",
    ".css": "text/css", ".json": "application/json",
    ".png": "image/png", ".svg": "image/svg+xml",
    ".ico": "image/x-icon", ".woff2": "font/woff2",
}

class SimHandler(BaseHTTPRequestHandler):
    server_dir = str(_PROJECT_DIR)

    def log_message(self, fmt, *args):
        pass  # silent

    def _json_resp(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # REST API
        if path == "/api/status":
            self._json_resp({
                "mode": current_mode,
                "glasses": glasses.to_dict(),
                "ws_clients": len(clients),
                "recorder": recorder.status(),
                "glasses_adb": _glasses_online(),
            })
            return
        if path == "/api/mode":
            self._json_resp({"mode": current_mode})
            return
        if path == "/api/events":
            qs = parse_qs(parsed.query)
            n = int(qs.get("n", ["50"])[0])
            self._json_resp({"events": glasses.events[-n:]})
            return
        if path == "/api/health":
            self._json_resp({"ok": True, "version": "3.0", "mode": current_mode})
            return
        if path == "/api/device":
            self._json_resp(VirtualGlasses.DEVICE_INFO)
            return
        if path == "/api/scenarios":
            listing = {k: {"name": v["name"], "steps": len(v["steps"])} for k, v in SCENARIOS.items()}
            self._json_resp({"scenarios": listing})
            return
        if path == "/api/recordings":
            rec_dir = _PROJECT_DIR / "recordings"
            files = sorted(rec_dir.glob("*.json")) if rec_dir.exists() else []
            self._json_resp({"recordings": [f.name for f in files]})
            return
        if path == "/api/apps":
            cat = parse_qs(parsed.query).get("cat", [None])[0]
            apps = V3_APPS if not cat else [a for a in V3_APPS if cat in a["cat"]]
            out = []
            with _apps_lock:
                for a in apps:
                    entry = {**a, "score": _app_score(a), "installed": a["id"] in _installed_apps}
                    if a["id"] in _installed_apps:
                        entry["install_info"] = _installed_apps[a["id"]].copy()
                    out.append(entry)
                installed_count = len(_installed_apps)
            self._json_resp({"apps": out, "total": len(out),
                             "installed": installed_count,
                             "categories": sorted(set(a["cat"] for a in V3_APPS))})
            return
        if path.startswith("/api/apps/") and path.count("/") == 3:
            app_id = path.split("/")[-1]
            app = _get_app(app_id)
            if not app:
                self._json_resp({"error": "app not found"}, 404)
                return
            with _apps_lock:
                is_installed = app_id in _installed_apps
                install_info = _installed_apps.get(app_id, {}).copy() if is_installed else None
            self._json_resp({**app, "score": _app_score(app),
                             "installed": is_installed,
                             "install_info": install_info,
                             "test_results": _test_app_compat(app)})
            return

        # 静态文件
        if path == "/":
            path = "/rayneo_simulator.html"
        fpath = Path(self.server_dir) / path.lstrip("/")
        fpath = fpath.resolve()
        if not str(fpath).startswith(self.server_dir):
            self.send_error(403)
            return
        if fpath.is_file():
            ext = fpath.suffix.lower()
            ctype = _MIME.get(ext, "application/octet-stream")
            data = fpath.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", len(data))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        clen = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(clen)) if clen > 0 else {}

        if path == "/api/mode":
            mode = body.get("mode", "sim")
            loop = asyncio.new_event_loop()
            loop.run_until_complete(switch_mode(mode))
            loop.close()
            self._json_resp({"mode": current_mode})
        elif path == "/api/tts":
            text = body.get("text", "")
            glasses.last_tts = text
            glasses.add_event("tts", {"text": text, "source": "api"})
            self._json_resp({"ok": True})
        elif path == "/api/gesture":
            gesture = body.get("gesture", "tap")
            glasses.add_event("gesture", {"gesture": gesture, "source": "api"})
            self._json_resp({"ok": True})
        elif path == "/api/apps/install":
            app_id = body.get("id")
            app = _get_app(app_id)
            if not app:
                self._json_resp({"error": "app not found"}, 404)
                return
            with _apps_lock:
                _installed_apps[app_id] = {
                    "installed_at": time.time(), "launched_count": 0,
                    "last_test": None, "issues_found": len(app.get("issues", [])),
                    "fixes_applied": 0
                }
            glasses.add_event("app_install", {"app": app["name"], "pkg": app["pkg"], "score": _app_score(app)})
            self._json_resp({"ok": True, "app": app["name"], "score": _app_score(app)})
        elif path == "/api/apps/uninstall":
            app_id = body.get("id")
            with _apps_lock:
                removed = _installed_apps.pop(app_id, None)
            if removed:
                app = _get_app(app_id)
                glasses.add_event("app_uninstall", {"app": app["name"] if app else app_id})
            self._json_resp({"ok": True})
        elif path == "/api/apps/test":
            app_id = body.get("id")
            app = _get_app(app_id)
            if not app:
                self._json_resp({"error": "app not found"}, 404)
                return
            result = _test_app_compat(app)
            with _apps_lock:
                if app_id in _installed_apps:
                    _installed_apps[app_id]["last_test"] = time.time()
            glasses.add_event("app_test", {"app": app["name"], "score": result["score"]})
            self._json_resp(result)
        elif path == "/api/apps/launch":
            app_id = body.get("id")
            app = _get_app(app_id)
            if not app:
                self._json_resp({"error": "app not found"}, 404)
                return
            with _apps_lock:
                if app_id not in _installed_apps:
                    self._json_resp({"error": "app not installed"}, 400)
                    return
                _installed_apps[app_id]["launched_count"] += 1
                launch_count = _installed_apps[app_id]["launched_count"]
            glasses.add_event("app_launch", {"app": app["name"], "pkg": app["pkg"]})
            self._json_resp({"ok": True, "app": app["name"], "launch_count": launch_count})
        else:
            self._json_resp({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

def start_http_server(directory, port=8768):
    SimHandler.server_dir = str(directory)
    httpd = HTTPServer(("0.0.0.0", port), SimHandler)
    httpd.serve_forever()

# ─── V3 App Center ────────────────────────────────────────
V3_APPS = [
    # ☰乾·AI智能
    {"id": "ai_scene", "name": "AI场景识别", "pkg": "com.rayneo.aiscene", "cat": "☰AI智能", "icon": "🤖",
     "desc": "实时摄像头场景识别，叠加AR标注", "size": "28MB", "ver": "2.1.0",
     "compat": {"gesture": 95, "voice": 90, "display": 100, "camera": 100, "battery": 70},
     "issues": [], "native": True},
    {"id": "ai_translate", "name": "实时翻译", "pkg": "com.rayneo.translate", "cat": "☰AI智能", "icon": "🌐",
     "desc": "摄像头文字识别+实时翻译叠加", "size": "45MB", "ver": "1.8.0",
     "compat": {"gesture": 90, "voice": 95, "display": 95, "camera": 100, "battery": 60},
     "issues": ["长时间运行功耗偏高"], "native": True},
    {"id": "ai_assistant", "name": "小雷助手", "pkg": "com.rayneo.assistant", "cat": "☰AI智能", "icon": "🧠",
     "desc": "语音AI助手，支持多轮对话+知识问答", "size": "35MB", "ver": "3.0.0",
     "compat": {"gesture": 85, "voice": 100, "display": 90, "camera": 50, "battery": 65},
     "issues": [], "native": True},
    # ☵坎·导航交通
    {"id": "nav_ar", "name": "AR步行导航", "pkg": "com.rayneo.arnav", "cat": "☵导航", "icon": "🧭",
     "desc": "AR箭头叠加实景导航，语音播报转弯", "size": "52MB", "ver": "1.5.0",
     "compat": {"gesture": 80, "voice": 95, "display": 100, "camera": 90, "battery": 45},
     "issues": ["GPS定位需手机中继", "电池仅支持约40分钟导航"], "native": True},
    {"id": "nav_bike", "name": "骑行HUD", "pkg": "com.rayneo.bikehud", "cat": "☵导航", "icon": "🚴",
     "desc": "骑行速度/距离/导航HUD显示", "size": "18MB", "ver": "1.2.0",
     "compat": {"gesture": 70, "voice": 85, "display": 100, "camera": 60, "battery": 55},
     "issues": ["骑行中触控板操作不便"], "native": True},
    # ☲离·视觉媒体
    {"id": "teleprompter", "name": "提词器", "pkg": "com.rayneo.prompter", "cat": "☲视觉", "icon": "📜",
     "desc": "演讲/直播提词，文字自动滚动", "size": "8MB", "ver": "2.0.0",
     "compat": {"gesture": 95, "voice": 90, "display": 100, "camera": 30, "battery": 80},
     "issues": [], "native": True},
    {"id": "photo_viewer", "name": "照片查看", "pkg": "com.rayneo.gallery", "cat": "☲视觉", "icon": "🖼️",
     "desc": "浏览V3拍摄的照片，手势翻页", "size": "12MB", "ver": "1.3.0",
     "compat": {"gesture": 100, "voice": 60, "display": 100, "camera": 80, "battery": 85},
     "issues": [], "native": True},
    # ☳震·健康运动
    {"id": "step_counter", "name": "计步器", "pkg": "com.rayneo.steps", "cat": "☳健康", "icon": "👟",
     "desc": "IMU计步+卡路里+运动统计HUD", "size": "6MB", "ver": "1.1.0",
     "compat": {"gesture": 80, "voice": 70, "display": 95, "camera": 20, "battery": 90},
     "issues": [], "native": True},
    {"id": "workout", "name": "运动教练", "pkg": "com.rayneo.workout", "cat": "☳健康", "icon": "🏋️",
     "desc": "运动姿势AI检测+实时指导", "size": "65MB", "ver": "0.9.0",
     "compat": {"gesture": 60, "voice": 85, "display": 90, "camera": 95, "battery": 35},
     "issues": ["AI推理功耗高", "运动中触控不灵敏", "Beta版本稳定性待验证"], "native": True},
    # ☴巽·通讯社交
    {"id": "notify_hub", "name": "通知中心", "pkg": "com.rayneo.notify", "cat": "☴通讯", "icon": "🔔",
     "desc": "手机通知同步显示，手势快速回复", "size": "15MB", "ver": "2.5.0",
     "compat": {"gesture": 95, "voice": 90, "display": 100, "camera": 20, "battery": 75},
     "issues": [], "native": True},
    {"id": "wechat_lite", "name": "微信精简", "pkg": "com.tencent.mm.lite", "cat": "☴通讯", "icon": "💬",
     "desc": "微信消息语音回复+朋友圈浏览", "size": "85MB", "ver": "1.0.0",
     "compat": {"gesture": 50, "voice": 80, "display": 60, "camera": 40, "battery": 40},
     "issues": ["触摸屏UI不适配1D触控板", "字体过小需缩放", "部分功能需触屏操作", "功耗偏高"],
     "native": False, "adapted": True},
    # ☶艮·效率办公
    {"id": "calendar", "name": "日程提醒", "pkg": "com.rayneo.calendar", "cat": "☶效率", "icon": "📅",
     "desc": "日历事件HUD提醒+语音添加日程", "size": "10MB", "ver": "1.4.0",
     "compat": {"gesture": 90, "voice": 100, "display": 95, "camera": 20, "battery": 85},
     "issues": [], "native": True},
    {"id": "notes", "name": "语音笔记", "pkg": "com.rayneo.notes", "cat": "☶效率", "icon": "📝",
     "desc": "语音记录→文字转写→云端同步", "size": "20MB", "ver": "1.6.0",
     "compat": {"gesture": 85, "voice": 100, "display": 90, "camera": 30, "battery": 70},
     "issues": [], "native": True},
    # ☱兑·娱乐生活
    {"id": "music", "name": "音乐播放", "pkg": "com.rayneo.music", "cat": "☱娱乐", "icon": "🎵",
     "desc": "音乐播放+歌词HUD+手势切歌", "size": "22MB", "ver": "2.0.0",
     "compat": {"gesture": 100, "voice": 95, "display": 85, "camera": 10, "battery": 75},
     "issues": [], "native": True},
    {"id": "podcast", "name": "播客", "pkg": "com.rayneo.podcast", "cat": "☱娱乐", "icon": "🎙️",
     "desc": "播客订阅+语音控制+进度HUD", "size": "18MB", "ver": "1.2.0",
     "compat": {"gesture": 90, "voice": 100, "display": 80, "camera": 10, "battery": 80},
     "issues": [], "native": True},
    {"id": "weather", "name": "天气", "pkg": "com.rayneo.weather", "cat": "☱娱乐", "icon": "🌤️",
     "desc": "天气预报HUD+语音查询", "size": "5MB", "ver": "1.8.0",
     "compat": {"gesture": 85, "voice": 100, "display": 100, "camera": 10, "battery": 90},
     "issues": [], "native": True},
    # ☷坤·系统工具
    {"id": "settings", "name": "V3设置", "pkg": "com.rayneo.settings", "cat": "☷系统", "icon": "⚙️",
     "desc": "亮度/音量/WiFi/蓝牙管理", "size": "8MB", "ver": "3.0.0",
     "compat": {"gesture": 100, "voice": 90, "display": 100, "camera": 10, "battery": 95},
     "issues": [], "native": True},
    {"id": "ota", "name": "系统更新", "pkg": "com.rayneo.ota", "cat": "☷系统", "icon": "🔄",
     "desc": "OTA固件升级+版本管理", "size": "12MB", "ver": "1.5.0",
     "compat": {"gesture": 80, "voice": 60, "display": 90, "camera": 10, "battery": 30},
     "issues": ["更新过程需保持充电"], "native": True},
    # 第三方适配
    {"id": "amap", "name": "高德地图(适配版)", "pkg": "com.autonavi.minimap.glasses", "cat": "☵导航", "icon": "🗺️",
     "desc": "高德地图AR眼镜适配版", "size": "95MB", "ver": "0.5.0",
     "compat": {"gesture": 55, "voice": 75, "display": 50, "camera": 70, "battery": 35},
     "issues": ["地图渲染对GPU要求高", "触控板无法替代触屏滑动", "需要手机GPS中继", "UI元素过小"],
     "native": False, "adapted": True},
    {"id": "bilibili", "name": "哔哩哔哩(极简版)", "pkg": "com.bilibili.glasses", "cat": "☱娱乐", "icon": "📺",
     "desc": "B站视频浏览+弹幕+手势控制", "size": "45MB", "ver": "0.3.0",
     "compat": {"gesture": 65, "voice": 70, "display": 75, "camera": 10, "battery": 30},
     "issues": ["视频播放功耗极高", "触控板滑动精度不足", "弹幕显示需优化", "159mAh仅支持约25分钟"],
     "native": False, "adapted": True},
]

# App安装状态
_installed_apps = {}  # id -> {installed_at, launched_count, last_test, issues_found, fixes_applied}
_apps_lock = threading.Lock()

def _get_app(app_id):
    return next((a for a in V3_APPS if a["id"] == app_id), None)

def _app_score(app):
    c = app["compat"]
    return round((c["gesture"] * 0.25 + c["voice"] * 0.25 + c["display"] * 0.2 + c["camera"] * 0.15 + c["battery"] * 0.15))

def _test_app_compat(app):
    """虚拟兼容性测试 — 模拟V3硬件约束检查"""
    results = []
    c = app["compat"]
    # 手势兼容性
    if c["gesture"] < 60:
        results.append({"level": "error", "test": "gesture", "msg": "触控板兼容性不足：1D触控板无法替代触屏滑动",
                        "fix": "需重写导航为slide_fwd/slide_back/tap三手势模式"})
    elif c["gesture"] < 80:
        results.append({"level": "warn", "test": "gesture", "msg": "部分UI需要触屏操作",
                        "fix": "建议增加语音命令作为补充输入"})
    else:
        results.append({"level": "pass", "test": "gesture", "msg": "手势兼容性良好"})
    # 语音兼容性
    if c["voice"] < 60:
        results.append({"level": "warn", "test": "voice", "msg": "语音集成不完整",
                        "fix": "需接入RayNeoVoiceInteractionService"})
    else:
        results.append({"level": "pass", "test": "voice", "msg": "语音兼容性良好"})
    # 显示兼容性
    if c["display"] < 60:
        results.append({"level": "error", "test": "display", "msg": "UI未适配1920x1080微OLED",
                        "fix": "需重写UI为大字体/高对比度/简化布局"})
    elif c["display"] < 80:
        results.append({"level": "warn", "test": "display", "msg": "部分UI元素过小",
                        "fix": "建议缩放因子设为2.0x，简化信息密度"})
    else:
        results.append({"level": "pass", "test": "display", "msg": "显示兼容性良好"})
    # 摄像头兼容性
    if c["camera"] > 80:
        results.append({"level": "pass", "test": "camera", "msg": "摄像头功能完整"})
    elif c["camera"] > 40:
        results.append({"level": "info", "test": "camera", "msg": "部分摄像头功能可用"})
    else:
        results.append({"level": "info", "test": "camera", "msg": "不依赖摄像头"})
    # 电池兼容性
    if c["battery"] < 40:
        results.append({"level": "error", "test": "battery", "msg": f"功耗过高：159mAh电池预估续航<30分钟",
                        "fix": "需降低刷新率/关闭后台服务/优化渲染"})
    elif c["battery"] < 60:
        results.append({"level": "warn", "test": "battery", "msg": "功耗偏高：预估续航约40-60分钟",
                        "fix": "建议增加省电模式，降低传感器采样率"})
    else:
        results.append({"level": "pass", "test": "battery", "msg": "功耗可接受"})
    # 总体评分
    score = _app_score(app)
    if score >= 85:
        results.append({"level": "pass", "test": "overall", "msg": f"总评 {score}/100 — 完全适配V3"})
    elif score >= 65:
        results.append({"level": "warn", "test": "overall", "msg": f"总评 {score}/100 — 基本可用，部分功能受限"})
    else:
        results.append({"level": "error", "test": "overall", "msg": f"总评 {score}/100 — 需要大量适配工作"})
    return {"app_id": app["id"], "score": score, "results": results, "issues": app.get("issues", [])}

# ─── 主入口 ──────────────────────────────────────────────
async def main(ws_port=8767, http_port=8768, mode="auto"):
    global current_mode

    # 模式检测
    if mode == "auto":
        if _glasses_online():
            current_mode = "live"
        else:
            current_mode = "sim"
    else:
        current_mode = mode

    label = "LIVE (ADB)" if current_mode == "live" else "SIM (Virtual)"

    print(f"\n  RayNeo V3 Hybrid Simulator v3.0")
    print(f"  Mode: {label}")
    print(f"  WS:   ws://localhost:{ws_port}")
    print(f"  HTTP: http://localhost:{http_port}")
    print(f"  API:  http://localhost:{http_port}/api/status")
    print(f"  UI:   http://localhost:{http_port}/rayneo_simulator.html")
    print(f"  Ctrl+C to exit\n")

    project_dir = Path(__file__).resolve().parent

    http_thread = threading.Thread(
        target=start_http_server,
        args=(project_dir, http_port),
        daemon=True
    )
    http_thread.start()

    if current_mode == "live":
        global _live_poll_task
        _live_poll_task = asyncio.ensure_future(_live_poll_loop())

    async with websockets.serve(handle_client, "0.0.0.0", ws_port):
        await asyncio.Future()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RayNeo V3 Hybrid Simulator v3.0")
    parser.add_argument("--ws-port", type=int, default=8767)
    parser.add_argument("--http-port", type=int, default=8768)
    parser.add_argument("--mode", choices=["auto", "sim", "live"], default="auto")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.ws_port, args.http_port, args.mode))
    except KeyboardInterrupt:
        print("\n[Hybrid Simulator stopped]")
