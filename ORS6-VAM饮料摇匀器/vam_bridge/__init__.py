"""VaM↔TCode实时桥接 — 将VaM角色运动转为设备控制"""

from .bridge import VaMTCodeBridge
from .config import BridgeConfig

__all__ = ["VaMTCodeBridge", "BridgeConfig"]
