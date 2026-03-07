"""Funscript文件解析器

Funscript格式(.funscript):
{
  "version": "1.0",
  "inverted": false,
  "range": 100,
  "actions": [
    {"at": 0, "pos": 50},
    {"at": 500, "pos": 100},
    {"at": 1000, "pos": 0}
  ]
}

多轴命名约定:
  video.funscript     → L0 (主轴/行程)
  video.surge.funscript → L1 (推进)
  video.sway.funscript  → L2 (摆动)
  video.twist.funscript → R0 (扭转)
  video.roll.funscript  → R1 (横滚)
  video.pitch.funscript → R2 (俯仰)
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 多轴文件后缀 → TCode轴 映射
AXIS_SUFFIX_MAP = {
    "": "L0",           # 主文件 = 行程
    ".surge": "L1",
    ".sway": "L2",
    ".twist": "R0",
    ".roll": "R1",
    ".pitch": "R2",
}


@dataclass
class FunscriptAction:
    """单个动作点"""
    at: int      # 时间点(ms)
    pos: int     # 位置(0-100)

    @property
    def time_sec(self) -> float:
        return self.at / 1000.0

    @property
    def tcode_pos(self) -> int:
        """转为TCode位置(0-9999)"""
        return int(max(0, min(100, self.pos)) / 100.0 * 9999)


@dataclass
class Funscript:
    """Funscript文件数据"""
    actions: list[FunscriptAction] = field(default_factory=list)
    version: str = "1.0"
    inverted: bool = False
    range: int = 100
    axis: str = "L0"
    source_path: Optional[Path] = None

    @classmethod
    def load(cls, path: str | Path) -> "Funscript":
        """加载.funscript文件"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Funscript不存在: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        actions = [
            FunscriptAction(at=a["at"], pos=a["pos"])
            for a in data.get("actions", [])
        ]
        actions.sort(key=lambda a: a.at)

        # 根据文件名推断轴
        stem = path.stem
        axis = "L0"
        for suffix, ax in AXIS_SUFFIX_MAP.items():
            if suffix and stem.endswith(suffix.lstrip(".")):
                axis = ax
                break

        fs = cls(
            actions=actions,
            version=data.get("version", "1.0"),
            inverted=data.get("inverted", False),
            range=data.get("range", 100),
            axis=axis,
            source_path=path,
        )

        if fs.inverted:
            for a in fs.actions:
                a.pos = 100 - a.pos

        logger.info(f"加载Funscript: {path.name} → 轴{axis}, {len(actions)}个动作点, "
                     f"时长{fs.duration_sec:.1f}s")
        return fs

    @classmethod
    def load_multi_axis(cls, base_path: str | Path) -> dict[str, "Funscript"]:
        """加载多轴Funscript文件集

        Args:
            base_path: 主funscript路径 (如 video.funscript)

        Returns:
            {"L0": funscript, "L1": funscript, ...}
        """
        base_path = Path(base_path)
        stem = base_path.stem
        parent = base_path.parent

        results = {}

        # 主文件
        if base_path.exists():
            results["L0"] = cls.load(base_path)

        # 查找多轴文件
        for suffix, axis in AXIS_SUFFIX_MAP.items():
            if not suffix:
                continue
            multi_path = parent / f"{stem}{suffix}.funscript"
            if multi_path.exists():
                fs = cls.load(multi_path)
                fs.axis = axis
                results[axis] = fs

        logger.info(f"多轴加载: {len(results)}个轴 ({', '.join(results.keys())})")
        return results

    @property
    def duration_ms(self) -> int:
        """总时长(ms)"""
        if not self.actions:
            return 0
        return self.actions[-1].at

    @property
    def duration_sec(self) -> float:
        return self.duration_ms / 1000.0

    def get_position_at(self, time_ms: int) -> int:
        """获取指定时间点的插值位置(0-100)"""
        if not self.actions:
            return 50

        if time_ms <= self.actions[0].at:
            return self.actions[0].pos
        if time_ms >= self.actions[-1].at:
            return self.actions[-1].pos

        # 二分查找
        lo, hi = 0, len(self.actions) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if self.actions[mid].at <= time_ms:
                lo = mid
            else:
                hi = mid

        a1 = self.actions[lo]
        a2 = self.actions[hi]

        # 线性插值
        if a2.at == a1.at:
            return a2.pos
        t = (time_ms - a1.at) / (a2.at - a1.at)
        return int(a1.pos + (a2.pos - a1.pos) * t)

    def get_tcode_at(self, time_ms: int) -> int:
        """获取指定时间的TCode位置(0-9999)"""
        pos = self.get_position_at(time_ms)
        return int(max(0, min(100, pos)) / 100.0 * 9999)

    def __len__(self) -> int:
        return len(self.actions)

    def __repr__(self) -> str:
        return (f"Funscript(axis={self.axis}, actions={len(self.actions)}, "
                f"duration={self.duration_sec:.1f}s)")
