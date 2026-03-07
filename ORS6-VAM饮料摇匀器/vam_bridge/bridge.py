"""VaM↔TCode实时桥接

两种模式:
1. AgentBridge模式: 通过HTTP API轮询VaM角色控制器位置 → 转TCode
2. TSC监听模式: 监听ToySerialController插件的UDP TCode输出 → 转发到设备
"""

import time
import json
import socket
import logging
import threading
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

from .config import BridgeConfig

logger = logging.getLogger(__name__)


class VaMTCodeBridge:
    """VaM角色运动 → TCode设备 实时桥接"""

    def __init__(self, config: Optional[BridgeConfig] = None, **kwargs):
        self.config = config or BridgeConfig(**kwargs)
        self._device = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_positions: dict[str, float] = {}

    def _create_device(self):
        """根据配置创建TCode设备连接"""
        mode = self.config.tcode_mode
        if mode == "serial":
            from tcode import TCodeSerial
            dev = TCodeSerial(
                port=self.config.tcode_serial_port,
                baudrate=self.config.tcode_serial_baud,
            )
        elif mode == "wifi":
            from tcode import TCodeWiFi
            dev = TCodeWiFi(
                host=self.config.tcode_wifi_host,
                port=self.config.tcode_wifi_port,
            )
        else:
            raise ValueError(f"不支持的TCode模式: {mode}")

        if not dev.connect():
            raise ConnectionError(f"TCode设备连接失败 (mode={mode})")
        return dev

    def _vam_api(self, path: str) -> Optional[dict]:
        """调用VaM AgentBridge HTTP API"""
        url = f"http://{self.config.vam_host}:{self.config.vam_port}{path}"
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=2) as resp:
                return json.loads(resp.read().decode())
        except (URLError, json.JSONDecodeError, OSError) as e:
            logger.debug(f"VaM API {path} 失败: {e}")
            return None

    def _get_controller_position(self, atom_name: str,
                                 controller: str) -> Optional[dict]:
        """获取VaM角色控制器位置和旋转"""
        data = self._vam_api(
            f"/api/v1/atoms/{atom_name}/controllers/{controller}"
        )
        if data and "position" in data:
            return data
        return None

    def _position_to_tcode(self, axis: str, raw_value: float) -> int:
        """将VaM位置值转为TCode位置(0-9999)"""
        scaled = raw_value * self.config.position_scale + self.config.position_offset

        if axis in self.config.invert_axes:
            scaled = -scaled

        # 归一化到0-1范围 (假设VaM值范围约-0.5到0.5)
        normalized = max(0.0, min(1.0, scaled + 0.5))
        return int(normalized * 9999)

    def _should_update(self, axis: str, new_value: float) -> bool:
        """检查是否需要更新（死区过滤）"""
        if axis not in self._last_positions:
            return True
        delta = abs(new_value - self._last_positions[axis])
        return delta > self.config.deadzone

    def _smooth(self, axis: str, new_value: float) -> float:
        """平滑处理"""
        if axis not in self._last_positions or self.config.smoothing <= 0:
            return new_value
        alpha = 1.0 - self.config.smoothing
        return self._last_positions[axis] * (1 - alpha) + new_value * alpha

    # ── 模式1: AgentBridge轮询 ──

    def _poll_loop(self, atom_name: str):
        """AgentBridge轮询循环"""
        interval = 1.0 / self.config.vam_poll_hz
        logger.info(f"开始AgentBridge轮询: atom={atom_name}, {self.config.vam_poll_hz}Hz")

        while self._running:
            try:
                # 获取hipControl控制器（主要运动源）
                data = self._get_controller_position(atom_name, "hipControl")
                if data is None:
                    time.sleep(interval)
                    continue

                pos = data.get("position", {})
                rot = data.get("rotation", {})

                # 构建TCode命令
                commands = []
                mapping = self.config.axis_mapping

                for vam_key, tcode_axis in mapping.items():
                    if "_position_" in vam_key:
                        component = vam_key.split("_")[-1]
                        raw = pos.get(component, 0.0)
                    elif "_rotation_" in vam_key:
                        component = vam_key.split("_")[-1]
                        raw = rot.get(component, 0.0) / 180.0  # 角度归一化
                    else:
                        continue

                    smoothed = self._smooth(tcode_axis, raw)
                    if self._should_update(tcode_axis, smoothed):
                        tcode_pos = self._position_to_tcode(tcode_axis, smoothed)
                        commands.append(f"{tcode_axis}{tcode_pos:04d}")
                        self._last_positions[tcode_axis] = smoothed

                if commands and self._device:
                    cmd_str = " ".join(commands)
                    self._device.send(cmd_str)

            except Exception as e:
                logger.error(f"轮询异常: {e}")

            time.sleep(interval)

    # ── 模式2: TSC UDP监听 ──

    def _tsc_listen_loop(self):
        """监听ToySerialController插件的UDP TCode输出并转发到设备"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", self.config.tsc_udp_listen_port))
        sock.settimeout(1.0)

        logger.info(f"监听TSC UDP端口: {self.config.tsc_udp_listen_port}")

        while self._running:
            try:
                data, addr = sock.recvfrom(1024)
                tcode_cmd = data.decode("ascii", errors="ignore").strip()
                if tcode_cmd and self._device:
                    self._device.send(tcode_cmd)
                    logger.debug(f"TSC→Device: {tcode_cmd}")
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"TSC监听异常: {e}")

        sock.close()

    # ── 公共API ──

    def start(self, atom_name: str = "Person", mode: str = "agent_bridge"):
        """启动桥接

        Args:
            atom_name: VaM角色Atom名称
            mode: "agent_bridge" (HTTP轮询) 或 "tsc" (TSC UDP监听)
        """
        if self._running:
            logger.warning("桥接已在运行")
            return

        self._device = self._create_device()
        self._running = True

        if mode == "tsc":
            target = self._tsc_listen_loop
            args = ()
        else:
            target = self._poll_loop
            args = (atom_name,)

        self._thread = threading.Thread(target=target, args=args, daemon=True)
        self._thread.start()
        logger.info(f"桥接已启动 (mode={mode})")

    def stop(self):
        """停止桥接"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._device:
            self._device.stop()
            self._device.disconnect()
        self._last_positions.clear()
        logger.info("桥接已停止")

    def is_running(self) -> bool:
        return self._running

    def status(self) -> dict:
        """获取桥接状态"""
        return {
            "running": self._running,
            "device": repr(self._device) if self._device else None,
            "vam_host": f"{self.config.vam_host}:{self.config.vam_port}",
            "tcode_mode": self.config.tcode_mode,
            "last_positions": dict(self._last_positions),
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()
