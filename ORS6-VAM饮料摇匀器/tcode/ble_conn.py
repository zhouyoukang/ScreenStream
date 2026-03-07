"""TCode BLE蓝牙连接 — 使用bleak库

需要: pip install bleak
参考: ayvasoftware/osr-esp32 BLE实现
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ESP32 BLE TCode服务UUID (来自osr-esp32固件)
TCODE_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"  # Nordic UART Service
TCODE_TX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # TX (write)
TCODE_RX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # RX (notify)


class TCodeBLE:
    """通过BLE蓝牙与OSR设备通信

    使用Nordic UART Service (NUS) 传输TCode命令。
    ESP32固件需启用BLE模式。

    用法:
        ble = TCodeBLE()
        await ble.scan()           # 扫描设备
        await ble.connect("OSR")   # 连接名为OSR的设备
        await ble.send("L09999I500")
        await ble.disconnect()
    """

    def __init__(self):
        self._client = None
        self._connected = False
        self._rx_buffer: list[str] = []

    async def scan(self, timeout: float = 5.0) -> list[dict]:
        """扫描BLE设备"""
        try:
            from bleak import BleakScanner
            devices = await BleakScanner.discover(timeout=timeout)
            results = []
            for d in devices:
                results.append({
                    "name": d.name or "Unknown",
                    "address": d.address,
                    "rssi": d.rssi,
                })
                if d.name and ("OSR" in d.name.upper() or "TCODE" in d.name.upper()):
                    logger.info(f"发现OSR设备: {d.name} ({d.address}) RSSI={d.rssi}")
            return results
        except ImportError:
            logger.error("需要安装bleak库: pip install bleak")
            return []

    async def connect(self, name_or_address: str) -> bool:
        """连接BLE设备"""
        try:
            from bleak import BleakClient, BleakScanner

            # 按名称或地址查找
            device = None
            devices = await BleakScanner.discover(timeout=5.0)
            for d in devices:
                if (d.address == name_or_address or
                        (d.name and name_or_address.lower() in d.name.lower())):
                    device = d
                    break

            if device is None:
                logger.error(f"未找到设备: {name_or_address}")
                return False

            self._client = BleakClient(device.address)
            await self._client.connect()

            # 订阅RX通知
            await self._client.start_notify(TCODE_RX_CHAR_UUID, self._rx_handler)

            self._connected = True
            logger.info(f"BLE已连接: {device.name} ({device.address})")
            return True
        except ImportError:
            logger.error("需要安装bleak库: pip install bleak")
            return False
        except Exception as e:
            logger.error(f"BLE连接失败: {e}")
            return False

    def _rx_handler(self, sender, data: bytearray):
        """BLE接收回调"""
        text = data.decode("ascii", errors="ignore").strip()
        if text:
            self._rx_buffer.append(text)
            logger.debug(f"RX(BLE): {text}")

    async def send(self, command: str) -> Optional[str]:
        """发送TCode命令"""
        if not self._connected or self._client is None:
            logger.warning("BLE未连接")
            return None

        try:
            cmd_bytes = (command.strip() + "\n").encode("ascii")
            # BLE MTU限制，分块发送
            chunk_size = 20
            for i in range(0, len(cmd_bytes), chunk_size):
                chunk = cmd_bytes[i:i + chunk_size]
                await self._client.write_gatt_char(TCODE_TX_CHAR_UUID, chunk)

            logger.debug(f"TX(BLE): {command}")

            # 等待响应
            await asyncio.sleep(0.1)
            if self._rx_buffer:
                response = self._rx_buffer.pop(0)
                return response
            return None
        except Exception as e:
            logger.error(f"BLE发送失败: {e}")
            return None

    async def disconnect(self):
        """断开BLE连接"""
        if self._client and self._connected:
            await self._client.disconnect()
        self._connected = False
        logger.info("BLE已断开")

    @property
    def is_connected(self) -> bool:
        return self._connected

    def __repr__(self):
        status = "connected" if self.is_connected else "disconnected"
        return f"TCodeBLE({status})"
