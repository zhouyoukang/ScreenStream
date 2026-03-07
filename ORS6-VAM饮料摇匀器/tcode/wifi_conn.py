"""TCode WiFi连接 — UDP通信"""

import socket
import logging
import threading
from typing import Optional

from .protocol import TCodeCommand, TCodeBuilder, encode_position

logger = logging.getLogger(__name__)

DEFAULT_UDP_PORT = 8000


class TCodeWiFi:
    """通过WiFi UDP与OSR设备通信

    ESP32固件(TCodeESP32)默认监听UDP端口8000。
    设备IP需在ESP32固件Web配置页面中设置。
    """

    def __init__(self, host: str = "192.168.1.100",
                 port: int = DEFAULT_UDP_PORT,
                 timeout: float = 1.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._connected = False

    def connect(self) -> bool:
        """建立UDP连接"""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.settimeout(self.timeout)

            # UDP无连接验证，尝试发送设备查询
            self._send_raw("D2")
            try:
                data, addr = self._socket.recvfrom(1024)
                info = data.decode("ascii", errors="ignore").strip()
                logger.info(f"已连接WiFi: {self.host}:{self.port} — {info}")
            except socket.timeout:
                logger.warning(f"WiFi连接 {self.host}:{self.port} — 无响应(可能正常)")

            self._connected = True
            return True
        except OSError as e:
            logger.error(f"WiFi连接失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self._socket:
            self._socket.close()
            self._socket = None
        self._connected = False
        logger.info("WiFi已断开")

    @property
    def is_connected(self) -> bool:
        return self._connected and self._socket is not None

    def _send_raw(self, data: str):
        """底层UDP发送"""
        if self._socket:
            self._socket.sendto(
                (data.strip() + "\n").encode("ascii"),
                (self.host, self.port)
            )

    def send(self, command: str) -> Optional[str]:
        """发送TCode命令"""
        if not self.is_connected:
            logger.warning("WiFi未连接")
            return None

        with self._lock:
            try:
                self._send_raw(command)
                logger.debug(f"TX(UDP): {command}")

                try:
                    data, _ = self._socket.recvfrom(1024)
                    response = data.decode("ascii", errors="ignore").strip()
                    if response:
                        logger.debug(f"RX(UDP): {response}")
                    return response
                except socket.timeout:
                    return None
            except OSError as e:
                logger.error(f"UDP发送失败: {e}")
                return None

    def send_command(self, cmd: TCodeCommand) -> Optional[str]:
        return self.send(cmd.encode())

    def send_batch(self, commands: list[TCodeCommand]) -> Optional[str]:
        encoded = " ".join(c.encode() for c in commands)
        return self.send(encoded)

    def move(self, axis: str, position: int,
             interval_ms: Optional[int] = None) -> Optional[str]:
        cmd = TCodeCommand(axis=axis, position=position, interval_ms=interval_ms)
        return self.send_command(cmd)

    def home_all(self, interval_ms: int = 1000) -> Optional[str]:
        builder = TCodeBuilder().home_all(interval_ms)
        return self.send(builder.encode())

    def stop(self) -> Optional[str]:
        return self.send("D0")

    def device_info(self) -> Optional[str]:
        return self.send("D2")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.stop()
        self.disconnect()

    def __repr__(self):
        status = "connected" if self.is_connected else "disconnected"
        return f"TCodeWiFi(host={self.host}:{self.port}, {status})"
