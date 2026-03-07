"""TCode串口连接 — USB Serial通信"""

import time
import logging
import threading
from typing import Optional

import serial
from serial.tools import list_ports

from .protocol import TCodeCommand, TCodeBuilder, AXES_SR6, encode_position

logger = logging.getLogger(__name__)


class TCodeSerial:
    """通过USB串口与OSR设备通信"""

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200,
                 timeout: float = 1.0, auto_detect: bool = True):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.auto_detect = auto_detect
        self._serial: Optional[serial.Serial] = None
        self._lock = threading.Lock()
        self._connected = False

    @staticmethod
    def list_ports() -> list[dict]:
        """列出所有可用串口"""
        ports = []
        for p in list_ports.comports():
            ports.append({
                "port": p.device,
                "description": p.description,
                "hwid": p.hwid,
                "vid": p.vid,
                "pid": p.pid,
            })
        return ports

    @staticmethod
    def detect_osr_port() -> Optional[str]:
        """自动检测OSR设备端口（ESP32常见VID/PID）"""
        esp32_vids = [0x10C4, 0x1A86, 0x303A, 0x0403]  # CP210x, CH340, ESP32-S3, FTDI
        for p in list_ports.comports():
            if p.vid in esp32_vids:
                logger.info(f"检测到ESP32设备: {p.device} ({p.description})")
                return p.device
        return None

    def connect(self) -> bool:
        """建立连接"""
        if self._connected:
            return True

        port = self.port
        if port is None and self.auto_detect:
            port = self.detect_osr_port()
            if port is None:
                logger.error("未检测到OSR设备，请指定端口")
                return False
            self.port = port

        if port is None:
            logger.error("未指定端口")
            return False

        try:
            self._serial = serial.Serial(
                port=port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout,
            )
            time.sleep(2)  # ESP32重启等待
            self._connected = True
            logger.info(f"已连接: {port} @ {self.baudrate}bps")

            # 查询设备信息
            info = self.device_info()
            if info:
                logger.info(f"设备信息: {info}")
            return True
        except serial.SerialException as e:
            logger.error(f"连接失败 {port}: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._connected = False
        logger.info("已断开")

    @property
    def is_connected(self) -> bool:
        return self._connected and self._serial is not None and self._serial.is_open

    def send(self, command: str) -> Optional[str]:
        """发送TCode命令"""
        if not self.is_connected:
            logger.warning("未连接，无法发送")
            return None

        with self._lock:
            try:
                cmd_bytes = (command.strip() + "\n").encode("ascii")
                self._serial.write(cmd_bytes)
                self._serial.flush()
                logger.debug(f"TX: {command}")

                # 读取响应（如果有）
                response = self._serial.readline().decode("ascii", errors="ignore").strip()
                if response:
                    logger.debug(f"RX: {response}")
                return response
            except serial.SerialException as e:
                logger.error(f"发送失败: {e}")
                self._connected = False
                return None

    def send_command(self, cmd: TCodeCommand) -> Optional[str]:
        """发送TCodeCommand对象"""
        return self.send(cmd.encode())

    def send_batch(self, commands: list[TCodeCommand]) -> Optional[str]:
        """发送多轴命令（空格分隔）"""
        encoded = " ".join(c.encode() for c in commands)
        return self.send(encoded)

    # ── 便捷方法 ──

    def move(self, axis: str, position: int,
             interval_ms: Optional[int] = None) -> Optional[str]:
        """移动指定轴"""
        cmd = TCodeCommand(axis=axis, position=position, interval_ms=interval_ms)
        return self.send_command(cmd)

    def move_float(self, axis: str, value: float,
                   interval_ms: Optional[int] = None) -> Optional[str]:
        """移动指定轴（0.0-1.0浮点值）"""
        return self.move(axis, encode_position(value), interval_ms)

    def home_all(self, interval_ms: int = 1000) -> Optional[str]:
        """全轴归中位"""
        builder = TCodeBuilder().home_all(interval_ms)
        return self.send(builder.encode())

    def stop(self) -> Optional[str]:
        """紧急停止"""
        return self.send("D0")

    def device_info(self) -> Optional[str]:
        """查询设备信息"""
        return self.send("D2")

    def stroke(self, position: int, interval_ms: int = 500) -> Optional[str]:
        return self.move("L0", position, interval_ms)

    def surge(self, position: int, interval_ms: int = 500) -> Optional[str]:
        return self.move("L1", position, interval_ms)

    def sway(self, position: int, interval_ms: int = 500) -> Optional[str]:
        return self.move("L2", position, interval_ms)

    def twist(self, position: int, interval_ms: int = 500) -> Optional[str]:
        return self.move("R0", position, interval_ms)

    def roll(self, position: int, interval_ms: int = 500) -> Optional[str]:
        return self.move("R1", position, interval_ms)

    def pitch(self, position: int, interval_ms: int = 500) -> Optional[str]:
        return self.move("R2", position, interval_ms)

    # ── 运动模式 ──

    def linear_oscillate(self, axis: str = "L0",
                         min_pos: int = 0, max_pos: int = 9999,
                         interval_ms: int = 500, cycles: int = 5):
        """线性往复运动"""
        for _ in range(cycles):
            self.move(axis, max_pos, interval_ms)
            time.sleep(interval_ms / 1000.0)
            self.move(axis, min_pos, interval_ms)
            time.sleep(interval_ms / 1000.0)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.stop()
        self.disconnect()

    def __repr__(self):
        status = "connected" if self.is_connected else "disconnected"
        return f"TCodeSerial(port={self.port}, {status})"
