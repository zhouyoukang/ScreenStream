"""
TCode协议编解码器
参考: https://github.com/multiaxis/TCode-Specification

TCode格式:
  轴命令:  <axis><position>[I<interval>][S<speed>]
  示例:    L09999I1000   → L0轴移到9999位置，用时1000ms
           R05000S500    → R0轴移到5000位置，速度500/s
  设备命令: D0 (停止), D1 (全归位), D2 (查询信息)
  多命令:  用空格分隔: L09999I500 R05000I500
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AxisType(Enum):
    LINEAR = "L"
    ROTATION = "R"
    VIBRATION = "V"
    AUXILIARY = "A"


@dataclass(frozen=True)
class TCodeAxis:
    """TCode轴定义"""
    name: str
    code: str
    axis_type: AxisType
    description: str
    min_val: int = 0
    max_val: int = 9999
    default_val: int = 5000

    @property
    def channel(self) -> str:
        return self.code


# SR6 标准6轴定义
AXES_SR6 = {
    "stroke": TCodeAxis("Stroke",  "L0", AxisType.LINEAR,   "上下行程"),
    "surge":  TCodeAxis("Surge",   "L1", AxisType.LINEAR,   "前后推进"),
    "sway":   TCodeAxis("Sway",    "L2", AxisType.LINEAR,   "左右摆动"),
    "twist":  TCodeAxis("Twist",   "R0", AxisType.ROTATION, "旋转扭转"),
    "roll":   TCodeAxis("Roll",    "R1", AxisType.ROTATION, "横滚"),
    "pitch":  TCodeAxis("Pitch",   "R2", AxisType.ROTATION, "俯仰"),
}

# 振动轴定义 (TCode规范 V0-V9)
AXES_VIBRATION = {
    "vib0": TCodeAxis("Vibe1", "V0", AxisType.VIBRATION, "主振动"),
    "vib1": TCodeAxis("Vibe2", "V1", AxisType.VIBRATION, "辅振动"),
}

# 辅助轴定义 (TCode规范 A0-A9)
AXES_AUXILIARY = {
    "valve": TCodeAxis("Valve", "A0", AxisType.AUXILIARY, "气阀/吸力"),
    "lube":  TCodeAxis("Lube",  "A1", AxisType.AUXILIARY, "润滑泵"),
    "heat":  TCodeAxis("Heat",  "A2", AxisType.AUXILIARY, "加热器"),
}

# 全轴字典 (SR6 + 振动 + 辅助)
AXES_ALL = {**AXES_SR6, **AXES_VIBRATION, **AXES_AUXILIARY}

# 便捷别名
L0 = AXES_SR6["stroke"]
L1 = AXES_SR6["surge"]
L2 = AXES_SR6["sway"]
R0 = AXES_SR6["twist"]
R1 = AXES_SR6["roll"]
R2 = AXES_SR6["pitch"]
V0 = AXES_VIBRATION["vib0"]
V1 = AXES_VIBRATION["vib1"]
A0 = AXES_AUXILIARY["valve"]


@dataclass
class TCodeCommand:
    """单条TCode命令"""
    axis: str                          # 轴代码 (L0, R0, etc.)
    position: int                      # 目标位置 0-9999
    interval_ms: Optional[int] = None  # 运动时间(ms)
    speed: Optional[int] = None        # 运动速度(/s)

    def __post_init__(self):
        self.position = max(0, min(9999, self.position))
        if self.interval_ms is not None:
            self.interval_ms = max(0, self.interval_ms)
        if self.speed is not None:
            self.speed = max(0, self.speed)

    def encode(self) -> str:
        """编码为TCode字符串"""
        cmd = f"{self.axis}{self.position:04d}"
        if self.interval_ms is not None:
            cmd += f"I{self.interval_ms}"
        elif self.speed is not None:
            cmd += f"S{self.speed}"
        return cmd

    @classmethod
    def parse(cls, raw: str) -> "TCodeCommand":
        """解析TCode字符串（大小写不敏感，支持短格式如L09）"""
        raw = raw.strip().upper()
        if len(raw) < 3:
            raise ValueError(f"TCode命令太短: {raw}")

        axis = raw[:2]
        rest = raw[2:]

        interval_ms = None
        speed = None

        i_pos = rest.find("I")
        s_pos = rest.find("S")

        if i_pos >= 0:
            position = int(rest[:i_pos])
            interval_ms = int(rest[i_pos + 1:])
        elif s_pos >= 0:
            position = int(rest[:s_pos])
            speed = int(rest[s_pos + 1:])
        else:
            position = int(rest)

        return cls(axis=axis, position=position,
                   interval_ms=interval_ms, speed=speed)

    def __str__(self) -> str:
        return self.encode()


class TCodeBuilder:
    """TCode命令构建器 — 支持链式调用"""

    def __init__(self):
        self._commands: list[TCodeCommand] = []

    def move(self, axis: str | TCodeAxis, position: int,
             interval_ms: Optional[int] = None,
             speed: Optional[int] = None) -> "TCodeBuilder":
        """添加移动命令"""
        code = axis.code if isinstance(axis, TCodeAxis) else axis
        self._commands.append(TCodeCommand(
            axis=code, position=position,
            interval_ms=interval_ms, speed=speed
        ))
        return self

    def stroke(self, pos: int, interval_ms: int = 500) -> "TCodeBuilder":
        return self.move("L0", pos, interval_ms=interval_ms)

    def surge(self, pos: int, interval_ms: int = 500) -> "TCodeBuilder":
        return self.move("L1", pos, interval_ms=interval_ms)

    def sway(self, pos: int, interval_ms: int = 500) -> "TCodeBuilder":
        return self.move("L2", pos, interval_ms=interval_ms)

    def twist(self, pos: int, interval_ms: int = 500) -> "TCodeBuilder":
        return self.move("R0", pos, interval_ms=interval_ms)

    def roll(self, pos: int, interval_ms: int = 500) -> "TCodeBuilder":
        return self.move("R1", pos, interval_ms=interval_ms)

    def pitch(self, pos: int, interval_ms: int = 500) -> "TCodeBuilder":
        return self.move("R2", pos, interval_ms=interval_ms)

    def home_all(self, interval_ms: int = 1000) -> "TCodeBuilder":
        """全轴归中位"""
        for axis_def in AXES_SR6.values():
            self.move(axis_def, axis_def.default_val, interval_ms=interval_ms)
        return self

    def stop(self) -> "TCodeBuilder":
        """紧急停止"""
        self._commands.append(TCodeCommand(axis="D0", position=0))
        return self

    def encode(self) -> str:
        """编码所有命令为TCode字符串（空格分隔）"""
        return " ".join(cmd.encode() for cmd in self._commands)

    def clear(self) -> "TCodeBuilder":
        self._commands.clear()
        return self

    @property
    def commands(self) -> list[TCodeCommand]:
        return list(self._commands)


@dataclass
class DeviceCommand:
    """TCode设备命令 (D0-D2)
    
    D0 - 紧急停止所有轴
    D1 - 全轴归位到中间值
    D2 - 查询设备信息 (返回固件版本等)
    """
    code: str
    description: str
    
    def encode(self) -> str:
        return self.code
    
    def __str__(self) -> str:
        return self.code


DEVICE_STOP = DeviceCommand("D0", "紧急停止所有轴")
DEVICE_HOME = DeviceCommand("D1", "全轴归位")
DEVICE_INFO = DeviceCommand("D2", "查询设备信息")
DEVICE_DSTOP = DeviceCommand("DSTOP", "停止设备(新版TCode)")


def is_device_command(raw: str) -> bool:
    """检查是否为设备命令"""
    return raw.strip().upper() in ("D0", "D1", "D2", "DSTOP")


def encode_save_preference(axis: str, pref_min: int, pref_max: int) -> str:
    """编码设备偏好保存命令
    
    将用户偏好保存到ESP32 EEPROM，通过D2命令可读取。
    格式: $TX-YYYY-ZZZZ
    示例: $L0-1000-8000 → L0轴偏好范围[1000, 8000]
    
    Args:
        axis: 轴代码 (L0/R0/V0/A0等)
        pref_min: 偏好最小值 (0-9999)
        pref_max: 偏好最大值 (0-9999)
    """
    axis = axis.upper()
    pref_min = max(0, min(9999, pref_min))
    pref_max = max(0, min(9999, pref_max))
    if pref_min > pref_max:
        pref_min, pref_max = pref_max, pref_min
    return f"${axis}-{pref_min:04d}-{pref_max:04d}"


def parse_save_preference(raw: str) -> Optional[tuple[str, int, int]]:
    """解析设备偏好保存命令
    
    Args:
        raw: 原始命令字符串 (如 "$L0-1000-8000")
    
    Returns:
        (axis, pref_min, pref_max) 元组，或None
    """
    raw = raw.strip()
    if not raw.startswith("$") or raw.count("-") != 2:
        return None
    try:
        parts = raw[1:].split("-")
        axis = parts[0].upper()
        pref_min = int(parts[1])
        pref_max = int(parts[2])
        return (axis, pref_min, pref_max)
    except (ValueError, IndexError):
        return None


def encode_position(value: float) -> int:
    """将0.0-1.0浮点值转为TCode位置(0-9999)"""
    return int(max(0.0, min(1.0, value)) * 9999)


def decode_position(tcode_val: int) -> float:
    """将TCode位置(0-9999)转为0.0-1.0浮点值"""
    return max(0, min(9999, tcode_val)) / 9999.0


def magnitude_to_position(magnitude_str: str) -> int:
    """TCode规范: magnitude数字实际是0.xxxx的小数部分
    
    例: '77' → 0.77 → 7699
        '9' → 0.9 → 8999
        '17439' → 0.17439 → 1743
    """
    frac = float(f"0.{magnitude_str}")
    return int(frac * 9999)


def parse_multi(raw: str) -> list[TCodeCommand]:
    """解析空格分隔的多条TCode命令"""
    commands = []
    for part in raw.strip().split():
        part = part.strip()
        if not part:
            continue
        if is_device_command(part):
            continue
        try:
            commands.append(TCodeCommand.parse(part))
        except ValueError:
            pass
    return commands


def encode_multi(commands: list[TCodeCommand]) -> str:
    """编码多条命令为空格分隔字符串（加\n结尾）"""
    return " ".join(cmd.encode() for cmd in commands) + "\n"
