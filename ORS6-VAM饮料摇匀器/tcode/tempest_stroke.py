"""TempestStroke 运动模式引擎 — 移植自 ayvajs (33⭐)

原始项目: https://github.com/ayvasoftware/ayvajs
许可证: MIT
核心算法: Eccentric Parametric Oscillatory Motion™

3种运动公式:
  - tempest_motion: cos基础, 最自然的往复运动
  - parabolic_motion: 抛物线, 底部停顿更长
  - linear_motion: 线性三角波, 匀速往返

参数说明:
  - from/to: 运动范围 (0.0-1.0, 映射到TCode 0-9999)
  - phase: 相位偏移 (π/2的倍数, 0=同相, 1=90°超前, 2=反相)
  - ecc: 离心率 (0=对称正弦, >0=不对称, 模拟轨道运动)
  - bpm: 每分钟节拍数
  - shift: 额外相位偏移 (弧度)

42种预设模式来自 ayvajs tempest-stroke-library.js
"""

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class AxisParams:
    """单轴运动参数"""
    from_: float = 0.0
    to: float = 1.0
    phase: float = 0.0
    ecc: float = 0.0
    shift: float = 0.0
    motion: str = "tempest"  # tempest / parabolic / linear


def tempest_motion(angle: float, from_: float, to: float,
                   phase: float = 0, ecc: float = 0, shift: float = 0) -> float:
    """Eccentric Parametric Oscillatory Cosine Motion™ (ayvajs核心公式)

    position = midpoint - scale * cos(angle + ecc * sin(angle))
    """
    scale = 0.5 * (to - from_)
    midpoint = 0.5 * (to + from_)
    a = angle + (0.5 * math.pi * phase) + shift
    return midpoint - scale * math.cos(a + ecc * math.sin(a))


def parabolic_motion(angle: float, from_: float, to: float,
                     phase: float = 0, ecc: float = 0, shift: float = 0) -> float:
    """Eccentric Parametric Oscillatory Parabolic Motion™

    position = offset - scale * x², 底部停顿更长
    """
    scale = to - from_
    offset = to
    a = angle + (0.5 * math.pi * phase) + shift
    x = (((a % (2 * math.pi)) + (2 * math.pi)) % (2 * math.pi)) / math.pi - 1 + (ecc / math.pi) * math.sin(a)
    return offset - scale * x * x


def linear_motion(angle: float, from_: float, to: float,
                  phase: float = 0, ecc: float = 0, shift: float = 0) -> float:
    """Eccentric Parametric Oscillatory Linear Motion™

    position = offset - scale * |x|, 匀速三角波
    """
    scale = to - from_
    offset = to
    a = angle + (0.5 * math.pi * phase) + shift
    x = (((a % (2 * math.pi)) + (2 * math.pi)) % (2 * math.pi)) / math.pi - 1 + (ecc / math.pi) * math.sin(a)
    return offset - scale * abs(x)


MOTION_FN = {
    "tempest": tempest_motion,
    "parabolic": parabolic_motion,
    "linear": linear_motion,
}


class TempestStroke:
    """TempestStroke运动模式生成器

    用法:
        stroke = TempestStroke("orbit-tease", bpm=90)
        for t in range(600):  # 10秒 @ 60Hz
            positions = stroke.get_positions(t, frequency=60)
            # positions = {"L0": 0.72, "R0": 0.35, ...}  (0.0-1.0)
    """

    def __init__(self, config, bpm: float = 60.0):
        """
        Args:
            config: 预设名称(str)或轴参数字典
            bpm: 每分钟节拍数
        """
        if isinstance(config, str):
            if config not in PATTERN_LIBRARY:
                raise ValueError(f"未知模式: {config}. 可用: {list(PATTERN_LIBRARY.keys())}")
            config = PATTERN_LIBRARY[config]

        self.bpm = bpm
        self.axes = {}
        for axis, params in config.items():
            if isinstance(params, dict):
                self.axes[axis] = AxisParams(
                    from_=params.get("from", 0),
                    to=params.get("to", 1),
                    phase=params.get("phase", 0),
                    ecc=params.get("ecc", 0),
                    shift=params.get("shift", 0),
                    motion=params.get("motion", "tempest"),
                )

    def get_positions(self, index: int, frequency: float = 60.0) -> dict[str, float]:
        """获取给定帧的所有轴位置 (0.0-1.0)"""
        angular_velocity = (2 * math.pi * self.bpm) / 60
        angle = ((index + 1) * angular_velocity) / frequency
        result = {}
        for axis, p in self.axes.items():
            fn = MOTION_FN.get(p.motion, tempest_motion)
            result[axis] = max(0.0, min(1.0, fn(angle, p.from_, p.to, p.phase, p.ecc, p.shift)))
        return result

    def get_tcode_positions(self, index: int, frequency: float = 60.0) -> dict[str, int]:
        """获取TCode位置 (0-9999)"""
        positions = self.get_positions(index, frequency)
        return {axis: int(v * 9999) for axis, v in positions.items()}

    def generate_tcode(self, index: int, frequency: float = 60.0,
                       interval_ms: Optional[int] = None) -> str:
        """生成TCode命令字符串"""
        positions = self.get_tcode_positions(index, frequency)
        parts = []
        for axis, pos in positions.items():
            cmd = f"{axis}{pos:04d}"
            if interval_ms:
                cmd += f"I{interval_ms}"
            parts.append(cmd)
        return " ".join(parts)

    @staticmethod
    def list_patterns() -> list[str]:
        """列出所有可用模式名"""
        return list(PATTERN_LIBRARY.keys())

    @staticmethod
    def get_pattern(name: str) -> dict:
        """获取模式参数"""
        return PATTERN_LIBRARY.get(name, {})


# ═══════════════════════════════════════════════════════
# 42种预设模式 (完整移植自 ayvajs tempest-stroke-library.js)
# ═══════════════════════════════════════════════════════

PATTERN_LIBRARY = {
    "down-forward": {
        "L0": {"from": 0, "to": 1, "phase": 0, "ecc": 0.5},
        "L1": {"from": 0.8, "to": 0.2, "phase": 1, "ecc": 0.8},
        "R2": {"from": 0.2, "to": 0.8, "phase": 1, "ecc": 0.8},
    },
    "down-backward": {
        "L0": {"from": 0, "to": 1, "phase": 0, "ecc": 0.5},
        "L1": {"from": 0.2, "to": 0.8, "phase": 1, "ecc": 0.8},
        "R2": {"from": 0.8, "to": 0.2, "phase": 1, "ecc": 0.8},
    },
    "back-thrust-down": {
        "L0": {"from": 0, "to": 0.7, "phase": 0, "ecc": 0.5},
        "L1": {"from": 1, "to": 0, "phase": 0, "ecc": 0.5},
        "R2": {"from": 0.4, "to": 1, "phase": 0, "ecc": 0.5},
    },
    "back-thrust-down-swirl": {
        "L0": {"from": 0, "to": 0.7, "phase": 0, "ecc": 0.5},
        "L1": {"from": 0.9, "to": 0.1, "phase": 0, "ecc": 0.5},
        "L2": {"from": 0.8, "to": 0.2, "phase": 1, "ecc": 0.5},
        "R1": {"from": 0.8, "to": 0.2, "phase": 1, "ecc": 0.5},
        "R2": {"from": 0.5, "to": 1, "phase": 0, "ecc": 0.5},
    },
    "thrust-forward": {
        "L0": {"from": 0, "to": 0.5, "phase": 0, "ecc": 0.5},
        "L1": {"from": 0.2, "to": 1, "phase": 0, "ecc": 0.5},
        "R2": {"from": 0.5, "to": 1, "phase": 0, "ecc": 0.5},
    },
    "thrust-forward-swirl": {
        "L0": {"from": 0, "to": 0.5, "phase": 0, "ecc": 0.5},
        "L1": {"from": 0.2, "to": 1, "phase": 0, "ecc": 0.5},
        "L2": {"from": 0.8, "to": 0.2, "phase": 1, "ecc": 0},
        "R1": {"from": 0.8, "to": 0.2, "phase": 1, "ecc": 0},
        "R2": {"from": 0.5, "to": 1, "phase": 0, "ecc": 0.5},
    },
    "lean-forward-thrust-down": {
        "L0": {"from": 0, "to": 0.7, "phase": 0, "ecc": 0.5},
        "R2": {"from": 1, "to": 0, "phase": 0, "ecc": 0.5},
    },
    "lean-forward-thrust-down-swirl": {
        "L0": {"from": 0, "to": 0.7, "phase": 0, "ecc": 0.5},
        "L2": {"from": 0.8, "to": 0.2, "phase": 1, "ecc": 0.5},
        "R1": {"from": 0.8, "to": 0.2, "phase": 1, "ecc": 0.5},
        "R2": {"from": 1, "to": 0, "phase": 0, "ecc": 0.5},
    },
    "diagonal-down-back": {
        "L0": {"from": 0, "to": 0.5, "phase": 0, "ecc": 0.2},
        "L1": {"from": 1, "to": 0.2, "phase": 0, "ecc": 0.2},
        "R2": {"from": 1, "to": 0, "phase": 1, "ecc": 0.6},
    },
    "diagonal-down-forward": {
        "L0": {"from": 0, "to": 0.5, "phase": 0, "ecc": 0.2},
        "L1": {"from": 0, "to": 0.8, "phase": 0, "ecc": 0.2},
        "R2": {"from": 0, "to": 1, "phase": 1, "ecc": 0.6},
    },
    "orbit-tease": {
        "L0": {"from": 0.8, "to": 1, "phase": 0, "ecc": 0.3},
        "L1": {"from": 0.9, "to": 0.1, "phase": 0, "ecc": -0.3},
        "L2": {"from": 0.1, "to": 0.9, "phase": 1, "ecc": -0.3},
        "R1": {"from": 0.1, "to": 0.9, "phase": 1, "ecc": -0.3},
        "R2": {"from": 0.1, "to": 0.9, "phase": 0, "ecc": -0.3},
    },
    "left-right-tease": {
        "L0": {"from": 0.9, "to": 0.9, "phase": 0, "ecc": 0},
        "L2": {"from": 0, "to": 1, "phase": 0, "ecc": 0},
        "R1": {"from": 1, "to": 0, "phase": 1, "ecc": 0},
    },
    "forward-back-tease": {
        "L0": {"from": 0.9, "to": 0.9, "phase": 0, "ecc": 0},
        "L1": {"from": 0, "to": 1, "phase": 0, "ecc": 0},
        "R2": {"from": 0, "to": 1, "phase": 1, "ecc": 0},
    },
    "vortex-tease": {
        "L0": {"from": 0.8, "to": 1, "phase": 0, "ecc": 0.3},
        "L1": {"from": 0.6, "to": 0.4, "phase": 0, "ecc": 0},
        "L2": {"from": 0.4, "to": 0.6, "phase": 1, "ecc": 0},
        "R1": {"from": 0.9, "to": 0.1, "phase": 1, "ecc": 0},
        "R2": {"from": 0.9, "to": 0.1, "phase": 0, "ecc": 0},
    },
    "swirl-tease": {
        "L0": {"from": 0.5, "to": 1, "phase": 0, "ecc": 0},
        "L1": {"from": 1, "to": 0.3, "phase": 0, "ecc": 0},
        "L2": {"from": 1, "to": 0, "phase": 1, "ecc": 0},
        "R1": {"from": 0.9, "to": 0.1, "phase": 1, "ecc": 0},
        "R2": {"from": 0.4, "to": 1, "phase": 0, "ecc": 0},
    },
    "forward-back-grind": {
        "L0": {"from": 0, "to": 0, "phase": 0, "ecc": 0},
        "L1": {"from": 0.3, "to": 0.7, "phase": 0, "ecc": 0},
        "R2": {"from": 0, "to": 1, "phase": 0.5, "ecc": 0},
    },
    "orbit-grind": {
        "L0": {"from": 0, "to": 0.3, "phase": 0, "ecc": 0.3},
        "L1": {"from": 0, "to": 0.6, "phase": 0, "ecc": -0.3},
        "L2": {"from": 0.2, "to": 0.8, "phase": 1, "ecc": -0.3},
        "R1": {"from": 0.1, "to": 0.9, "phase": 1, "ecc": -0.3},
        "R2": {"from": 0.9, "to": 0.1, "phase": 0, "ecc": -0.3},
    },
    "short-low-roll-forward": {
        "L0": {"from": 0, "to": 0.5, "phase": 0, "ecc": 0.25},
        "R2": {"from": 0.4, "to": 0.6, "phase": 1, "ecc": 0},
    },
    "short-low-roll-backward": {
        "L0": {"from": 0, "to": 0.5, "phase": 0, "ecc": 0.25},
        "R2": {"from": 0.6, "to": 0.4, "phase": 1, "ecc": 0},
    },
    "short-mid-roll-forward": {
        "L0": {"from": 0.25, "to": 0.75, "phase": 0, "ecc": 0.25},
        "R2": {"from": 0.4, "to": 0.6, "phase": 1, "ecc": 0},
    },
    "short-mid-roll-backward": {
        "L0": {"from": 0.25, "to": 0.75, "phase": 0, "ecc": 0.25},
        "R2": {"from": 0.6, "to": 0.4, "phase": 1, "ecc": 0},
    },
    "short-high-roll-backward": {
        "L0": {"from": 0.5, "to": 1, "phase": 0, "ecc": 0.25},
        "R2": {"from": 0.4, "to": 0.6, "phase": 1, "ecc": 0},
    },
    "short-high-roll-forward": {
        "L0": {"from": 0.5, "to": 1, "phase": 0, "ecc": 0.25},
        "R2": {"from": 0.6, "to": 0.4, "phase": 1, "ecc": 0},
    },
    "long-stroke-1": {
        "L0": {"from": 0.1, "to": 0.9, "phase": 0, "ecc": 0.25},
        "L1": {"from": 0.8, "to": 0.2, "phase": 1, "ecc": 0.5},
        "R2": {"from": 0.3, "to": 0.7, "phase": 1, "ecc": 0.2},
    },
    "long-stroke-2": {
        "L0": {"from": 0.1, "to": 0.9, "phase": 0, "ecc": 0.25},
        "L1": {"from": 0.2, "to": 0.8, "phase": 1, "ecc": 0.5},
        "R2": {"from": 0.7, "to": 0.3, "phase": 1, "ecc": 0.2},
    },
    "long-stroke-3": {
        "L0": {"from": 0, "to": 0.7, "phase": 0, "ecc": 0},
        "L1": {"from": 0, "to": 1, "phase": 0, "ecc": 0},
        "R2": {"from": 1, "to": 0.3, "phase": 0, "ecc": 0.5},
    },
    "long-stroke-4": {
        "L0": {"from": 0, "to": 0.7, "phase": 0, "ecc": 0},
        "L1": {"from": 0.6, "to": 0.4, "phase": 0, "ecc": 0},
        "L2": {"from": 0.6, "to": 0.4, "phase": 1, "ecc": 0},
        "R1": {"from": 0.7, "to": 0.3, "phase": 1, "ecc": 0},
        "R2": {"from": 0.5, "to": 1, "phase": 0, "ecc": 0.25},
    },
    "long-stroke-5": {
        "L0": {"from": 0, "to": 0.8, "phase": 0, "ecc": 0},
        "L1": {"from": 0.4, "to": 0.6, "phase": 0, "ecc": 0},
        "L2": {"from": 0.4, "to": 0.6, "phase": 1, "ecc": 0},
        "R1": {"from": 0.3, "to": 0.7, "phase": 1, "ecc": 0},
        "R2": {"from": 0.5, "to": 1, "phase": 0, "ecc": 0.25},
    },
    "grind-circular": {
        "L0": {"from": 0, "to": 0, "phase": 0, "ecc": 0},
        "L1": {"from": 0.7, "to": 0.3, "phase": 0, "ecc": 0},
        "L2": {"from": 0.3, "to": 0.7, "phase": 1, "ecc": 0},
        "R1": {"from": 0.3, "to": 0.7, "phase": 1, "ecc": 0},
        "R2": {"from": 0.3, "to": 0.7, "phase": 0, "ecc": 0},
    },
    "grind-vortex": {
        "L0": {"from": 0, "to": 0, "phase": 0, "ecc": 0},
        "L1": {"from": 0.7, "to": 0.3, "phase": 0, "ecc": 0},
        "L2": {"from": 0.7, "to": 0.3, "phase": 1, "ecc": 0},
        "R1": {"from": 0.7, "to": 0.3, "phase": 1, "ecc": 0},
        "R2": {"from": 0.3, "to": 0.7, "phase": 0, "ecc": 0},
    },
    "grind-forward-back": {
        "L0": {"from": 0, "to": 0.1, "phase": 0, "ecc": 0},
        "L1": {"from": 0, "to": 1, "phase": 0, "ecc": 0},
        "R2": {"from": 0.6, "to": 0.4, "phase": 0, "ecc": 0},
    },
    "grind-forward-back-phased": {
        "L0": {"from": 0, "to": 0.1, "phase": 0, "ecc": 0},
        "L1": {"from": 0, "to": 1, "phase": 0, "ecc": 0},
        "R2": {"from": 0.3, "to": 0.7, "phase": 1, "ecc": 0},
    },
    "grind-forward-back-tilt": {
        "L0": {"from": 0, "to": 0.2, "phase": 0, "ecc": 0},
        "L1": {"from": 0.2, "to": 0.8, "phase": 0, "ecc": 0},
        "R2": {"from": 0.7, "to": 0, "phase": 0, "ecc": 0},
    },
    "grind-forward-tilt": {
        "L0": {"from": 0, "to": 0.2, "phase": 0, "ecc": 0},
        "L1": {"from": 0.3, "to": 0.3, "phase": 0, "ecc": 0},
        "R2": {"from": 0.1, "to": 0.7, "phase": 0, "ecc": 0},
    },
    "tease-orbit-right": {
        "L0": {"from": 0.9, "to": 0.9, "phase": 0, "ecc": 0},
        "L1": {"from": 0.7, "to": 0.3, "phase": 0, "ecc": 0},
        "L2": {"from": 0.3, "to": 0.7, "phase": 1, "ecc": 0},
        "R1": {"from": 0.1, "to": 0.9, "phase": 1, "ecc": 0},
        "R2": {"from": 0.1, "to": 0.9, "phase": 0, "ecc": 0},
    },
    "tease-orbit-left": {
        "L0": {"from": 0.9, "to": 0.9, "phase": 0, "ecc": 0},
        "L1": {"from": 0.7, "to": 0.3, "phase": 0, "ecc": 0},
        "L2": {"from": 0.7, "to": 0.3, "phase": 1, "ecc": 0},
        "R1": {"from": 0.9, "to": 0.1, "phase": 1, "ecc": 0},
        "R2": {"from": 0.1, "to": 0.9, "phase": 0, "ecc": 0},
    },
    "tease-left-right-rock": {
        "L0": {"from": 0.8, "to": 0.8, "phase": 0, "ecc": 0},
        "L2": {"from": 0.9, "to": 0.1, "phase": 0, "ecc": 0},
        "R1": {"from": 1, "to": 0, "phase": 0, "ecc": 0},
    },
    "tease-down-back": {
        "L0": {"from": 0.8, "to": 1, "phase": 0, "ecc": 0},
        "L1": {"from": 0.2, "to": 0.8, "phase": 1, "ecc": 0},
        "R2": {"from": 0.9, "to": 0.3, "phase": 1, "ecc": 0},
    },
    "tease-back-swirl-right": {
        "L0": {"from": 0.7, "to": 0.9, "phase": 0, "ecc": 0},
        "L1": {"from": 0.8, "to": 0.2, "phase": 0, "ecc": 0},
        "L2": {"from": 0.2, "to": 0.8, "phase": 1, "ecc": 0},
        "R1": {"from": 0.2, "to": 0.8, "phase": 1, "ecc": 0},
        "R2": {"from": 0.3, "to": 1, "phase": 0, "ecc": 0},
    },
    "tease-back-swirl-left": {
        "L0": {"from": 0.7, "to": 0.9, "phase": 0, "ecc": 0},
        "L1": {"from": 0.8, "to": 0.2, "phase": 0, "ecc": 0},
        "L2": {"from": 0.8, "to": 0.2, "phase": 1, "ecc": 0},
        "R1": {"from": 0.8, "to": 0.2, "phase": 1, "ecc": 0},
        "R2": {"from": 0.3, "to": 1, "phase": 0, "ecc": 0},
    },
    "tease-up-down-circle-right": {
        "L0": {"from": 0.7, "to": 1, "phase": 0, "ecc": 0},
        "L2": {"from": 0.3, "to": 0.7, "phase": 1, "ecc": 0},
        "R1": {"from": 0.3, "to": 0.7, "phase": 1, "ecc": 0},
        "R2": {"from": 0.8, "to": 0.8, "phase": 0, "ecc": 0},
    },
    "tease-up-down-circle-left": {
        "L0": {"from": 0.7, "to": 1, "phase": 0, "ecc": 0},
        "L2": {"from": 0.7, "to": 0.3, "phase": 1, "ecc": 0},
        "R1": {"from": 0.7, "to": 0.3, "phase": 1, "ecc": 0},
        "R2": {"from": 0.8, "to": 0.8, "phase": 0, "ecc": 0},
    },
}
