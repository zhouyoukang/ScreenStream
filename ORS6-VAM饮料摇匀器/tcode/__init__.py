"""TCode通信库 — 支持Serial/WiFi/BLE/Buttplug四种连接方式控制OSR设备"""

from .protocol import (
    TCodeCommand, TCodeAxis, TCodeBuilder, DeviceCommand,
    AXES_SR6, AXES_VIBRATION, AXES_AUXILIARY, AXES_ALL,
    DEVICE_STOP, DEVICE_HOME, DEVICE_INFO, DEVICE_DSTOP,
    encode_position, decode_position, magnitude_to_position,
    parse_multi, encode_multi, is_device_command,
    encode_save_preference, parse_save_preference,
)
from .serial_conn import TCodeSerial
from .wifi_conn import TCodeWiFi

# BLE和Buttplug为可选依赖，延迟导入避免强制要求bleak/websockets
def __getattr__(name):
    if name == "TCodeBLE":
        from .ble_conn import TCodeBLE
        return TCodeBLE
    if name == "ButtplugBridge":
        from .buttplug_conn import ButtplugBridge
        return ButtplugBridge
    if name == "ButtplugConfig":
        from .buttplug_conn import ButtplugConfig
        return ButtplugConfig
    if name == "ButtplugDevice":
        from .buttplug_conn import ButtplugDevice
        return ButtplugDevice
    if name == "VirtualORS6":
        from .virtual_device import VirtualORS6
        return VirtualORS6
    if name == "ServoConfig":
        from .virtual_device import ServoConfig
        return ServoConfig
    if name == "DashboardServer":
        from .virtual_dashboard import DashboardServer
        return DashboardServer
    if name == "TempestStroke":
        from .tempest_stroke import TempestStroke
        return TempestStroke
    raise AttributeError(f"module 'tcode' has no attribute {name!r}")

__all__ = [
    "TCodeCommand", "TCodeAxis", "TCodeBuilder", "DeviceCommand",
    "AXES_SR6", "AXES_VIBRATION", "AXES_AUXILIARY", "AXES_ALL",
    "DEVICE_STOP", "DEVICE_HOME", "DEVICE_INFO", "DEVICE_DSTOP",
    "TCodeSerial", "TCodeWiFi", "TCodeBLE",
    "ButtplugBridge", "ButtplugConfig", "ButtplugDevice",
    "encode_position", "decode_position", "magnitude_to_position",
    "parse_multi", "encode_multi", "is_device_command",
    "encode_save_preference", "parse_save_preference",
    "VirtualORS6", "ServoConfig", "DashboardServer", "TempestStroke",
]
