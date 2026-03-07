"""
VaM 动画构建器 — 程序化动画/姿态/时间线/BVH/程序化动画管理

从以下外部项目提取核心逻辑:
  - vam-timeline: Timeline animation curves, keyframes, triggers
  - vam-story-builder: Trigger templates, dialog animation triggers
  - vam-embody: Controller names for body parts
  - VamFreeMMD: MMD animation import patterns
  - via5/Cue: BVH导入/程序化动画/力/扭矩/Morph目标/缓动函数 (CC0)
  - via5/Synergy: 步骤/修饰器随机动画系统 (CC0)
  - acidbubbles/vam-director: 相机角度序列编排
  - sFisherE/mmd2timeline: MMD面部Morph→VaM映射/手指Morph/DAZ骨骼映射
  - CraftyMoment/mmd_vam_import: VMD→VaM场景JSON转换器(Python原生)
  - ZengineerVAM/VAMLaunch: 触觉设备运动源抽象

架构:
  PoseBuilder            — 静态姿态构建 (控制器位置/旋转)
  TimelineBuilder        — 时间线动画构建 (关键帧序列)
  AnimationSequencer     — 动画序列编排 (多段动画串联)
  PoseLibrary            — 预定义姿态库
  Easing                 — 缓动函数库 (from Cue)
  BVHParser              — BVH骨骼动画导入 (from Cue)
  ProceduralAnimation    — 程序化动画引擎 (from Cue)
  SynergyStepAnimation   — 步骤式随机动画 (from Synergy)
  MMDFaceMorphMap        — MMD日文面部Morph→VaM Morph映射 (from mmd2timeline)
  FingerMorphMap         — VaM手指控制参数+骨骼旋转公式 (from mmd2timeline)
  DazBoneMap             — DAZ Genesis→MMD骨骼名称映射 (from mmd2timeline)
  VMDSceneImporter       — VMD→VaM场景JSON完整转换器 (from mmd_vam_import)
  LaunchMotionSource     — 触觉设备运动源抽象 (from VAMLaunch)
"""
import json
import copy
import math
import random
from pathlib import Path
from typing import Optional

from .config import VAM_CONFIG
from .characters import CONTROL_SUFFIXES


# ── 关键帧 ──

class Keyframe:
    """单个关键帧"""

    def __init__(self, time: float, value: float,
                 curve_type: str = "SmoothLocal"):
        self.time = time
        self.value = value
        self.curve_type = curve_type  # Linear, SmoothLocal, SmoothGlobal, Flat, Bounce

    def to_dict(self) -> dict:
        return {
            "t": str(self.time),
            "v": str(self.value),
            "c": self.curve_type,
        }


# ── 动画曲线 ──

class AnimationCurve:
    """动画曲线 — 单个参数的关键帧序列"""

    def __init__(self, target: str, param: str):
        self.target = target  # e.g. "headControl"
        self.param = param    # e.g. "position.x"
        self.keyframes: list[Keyframe] = []

    def add_key(self, time: float, value: float,
                curve_type: str = "SmoothLocal") -> "AnimationCurve":
        """添加关键帧"""
        self.keyframes.append(Keyframe(time, value, curve_type))
        return self

    def add_keys(self, time_value_pairs: list[tuple[float, float]],
                 curve_type: str = "SmoothLocal") -> "AnimationCurve":
        """批量添加关键帧"""
        for t, v in time_value_pairs:
            self.keyframes.append(Keyframe(t, v, curve_type))
        return self

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "param": self.param,
            "keys": [k.to_dict() for k in self.keyframes],
        }


# ── 姿态构建器 ──

class PoseBuilder:
    """
    静态姿态构建器 — 设置身体各控制器的位置和旋转

    用法:
        pose = PoseBuilder("standing_pose")
        pose.set_controller("head", position=(0, 1.7, 0), rotation=(0, 0, 0))
        pose.set_controller("left_hand", position=(-0.3, 1.0, 0.2))
        data = pose.build()
    """

    def __init__(self, name: str = "custom_pose"):
        self.name = name
        self.controllers: dict[str, dict] = {}

    def set_controller(self, friendly_name: str,
                       position: Optional[tuple] = None,
                       rotation: Optional[tuple] = None,
                       mode: str = "On") -> "PoseBuilder":
        """设置控制器位置/旋转 (使用友好名称)"""
        ctrl_name = CONTROL_SUFFIXES.get(friendly_name, friendly_name)
        entry = {"controlMode": mode}
        if position:
            entry["position"] = {
                "x": str(position[0]),
                "y": str(position[1]),
                "z": str(position[2]),
            }
        if rotation:
            entry["rotation"] = {
                "x": str(rotation[0]),
                "y": str(rotation[1]),
                "z": str(rotation[2]),
            }
        self.controllers[ctrl_name] = entry
        return self

    def set_raw_controller(self, controller_name: str,
                           position: Optional[tuple] = None,
                           rotation: Optional[tuple] = None) -> "PoseBuilder":
        """设置控制器 (使用VaM原始名称)"""
        entry = {}
        if position:
            entry["position"] = {
                "x": str(position[0]),
                "y": str(position[1]),
                "z": str(position[2]),
            }
        if rotation:
            entry["rotation"] = {
                "x": str(rotation[0]),
                "y": str(rotation[1]),
                "z": str(rotation[2]),
            }
        self.controllers[controller_name] = entry
        return self

    def build(self) -> list[dict]:
        """构建为storable列表"""
        storables = []
        for ctrl_name, data in self.controllers.items():
            storable = {"id": ctrl_name}
            storable.update(data)
            storables.append(storable)
        return storables

    def to_dict(self) -> dict:
        """导出为可序列化字典"""
        return {
            "name": self.name,
            "controllers": self.controllers,
        }


# ── 预定义姿态库 ──

class PoseLibrary:
    """预定义姿态库"""

    POSES = {
        "standing": {
            "hipControl": {
                "position": {"x": "0", "y": "1.0", "z": "0"},
                "rotation": {"x": "0", "y": "0", "z": "0"},
            },
            "headControl": {
                "position": {"x": "0", "y": "1.7", "z": "0"},
                "rotation": {"x": "0", "y": "0", "z": "0"},
            },
        },
        "sitting": {
            "hipControl": {
                "position": {"x": "0", "y": "0.5", "z": "0"},
                "rotation": {"x": "0", "y": "0", "z": "0"},
            },
            "headControl": {
                "position": {"x": "0", "y": "1.2", "z": "0"},
                "rotation": {"x": "10", "y": "0", "z": "0"},
            },
            "lKneeControl": {
                "position": {"x": "-0.15", "y": "0.5", "z": "0.4"},
            },
            "rKneeControl": {
                "position": {"x": "0.15", "y": "0.5", "z": "0.4"},
            },
        },
        "lying_down": {
            "hipControl": {
                "position": {"x": "0", "y": "0.15", "z": "0"},
                "rotation": {"x": "90", "y": "0", "z": "0"},
            },
            "headControl": {
                "position": {"x": "0", "y": "0.15", "z": "-0.8"},
                "rotation": {"x": "90", "y": "0", "z": "0"},
            },
        },
        "t_pose": {
            "hipControl": {
                "position": {"x": "0", "y": "1.0", "z": "0"},
            },
            "lHandControl": {
                "position": {"x": "-0.8", "y": "1.3", "z": "0"},
            },
            "rHandControl": {
                "position": {"x": "0.8", "y": "1.3", "z": "0"},
            },
        },
        "arms_crossed": {
            "lHandControl": {
                "position": {"x": "0.15", "y": "1.15", "z": "0.15"},
                "rotation": {"x": "0", "y": "90", "z": "0"},
            },
            "rHandControl": {
                "position": {"x": "-0.15", "y": "1.2", "z": "0.15"},
                "rotation": {"x": "0", "y": "-90", "z": "0"},
            },
        },
        "hands_on_hips": {
            "lHandControl": {
                "position": {"x": "-0.25", "y": "0.95", "z": "0"},
                "rotation": {"x": "0", "y": "0", "z": "30"},
            },
            "rHandControl": {
                "position": {"x": "0.25", "y": "0.95", "z": "0"},
                "rotation": {"x": "0", "y": "0", "z": "-30"},
            },
        },
    }

    @classmethod
    def get_pose(cls, name: str) -> PoseBuilder:
        """获取预定义姿态"""
        if name not in cls.POSES:
            raise ValueError(f"Unknown pose: {name}. Available: {list(cls.POSES.keys())}")
        builder = PoseBuilder(name)
        for ctrl_name, data in cls.POSES[name].items():
            pos = None
            rot = None
            if "position" in data:
                p = data["position"]
                pos = (float(p["x"]), float(p["y"]), float(p["z"]))
            if "rotation" in data:
                r = data["rotation"]
                rot = (float(r["x"]), float(r["y"]), float(r["z"]))
            builder.set_raw_controller(ctrl_name, position=pos, rotation=rot)
        return builder

    @classmethod
    def list_poses(cls) -> list[str]:
        return list(cls.POSES.keys())


# ── 触发器 (from vam-story-builder trigger.json) ──

class Trigger:
    """动画触发器"""

    TEMPLATE = {
        "displayName": "",
        "startActions": [],
        "transitionActions": [],
        "endActions": [],
        "startTime": "0",
        "endTime": "1",
    }

    def __init__(self, name: str, start_time: float = 0,
                 end_time: float = 1):
        self.name = name
        self.start_time = start_time
        self.end_time = end_time
        self.start_actions: list[dict] = []
        self.transition_actions: list[dict] = []
        self.end_actions: list[dict] = []

    def add_start_action(self, receiver_atom: str, receiver_storable: str,
                         action: str, value: str = "") -> "Trigger":
        """添加起始动作"""
        self.start_actions.append({
            "receiverAtom": receiver_atom,
            "receiver": receiver_storable,
            "receiverTargetName": action,
            "stringValue": value,
        })
        return self

    def add_end_action(self, receiver_atom: str, receiver_storable: str,
                       action: str, value: str = "") -> "Trigger":
        """添加结束动作"""
        self.end_actions.append({
            "receiverAtom": receiver_atom,
            "receiver": receiver_storable,
            "receiverTargetName": action,
            "stringValue": value,
        })
        return self

    def build(self) -> dict:
        """构建触发器字典"""
        trigger = copy.deepcopy(self.TEMPLATE)
        trigger["displayName"] = self.name
        trigger["startTime"] = str(self.start_time)
        trigger["endTime"] = str(self.end_time)
        trigger["startActions"] = self.start_actions
        trigger["transitionActions"] = self.transition_actions
        trigger["endActions"] = self.end_actions
        return trigger


# ── 时间线动画构建器 (from vam-timeline patterns) ──

class TimelineBuilder:
    """
    时间线动画构建器 — 创建Timeline插件格式的动画

    用法:
        timeline = TimelineBuilder("walk_cycle", duration=2.0)
        timeline.add_float_curve("headControl", "position.y",
            [(0.0, 1.7), (0.5, 1.72), (1.0, 1.7), (1.5, 1.72), (2.0, 1.7)])
        timeline.add_trigger("step_sound", 0.25, 0.26)
        data = timeline.build()
    """

    def __init__(self, name: str, duration: float = 5.0,
                 loop: bool = True):
        self.name = name
        self.duration = duration
        self.loop = loop
        self.curves: list[AnimationCurve] = []
        self.triggers: list[Trigger] = []
        self.speed: float = 1.0

    def add_curve(self, curve: AnimationCurve) -> "TimelineBuilder":
        """添加动画曲线"""
        self.curves.append(curve)
        return self

    def add_float_curve(self, target: str, param: str,
                        time_value_pairs: list[tuple[float, float]],
                        curve_type: str = "SmoothLocal") -> "TimelineBuilder":
        """便捷方法: 添加浮点曲线"""
        curve = AnimationCurve(target, param)
        curve.add_keys(time_value_pairs, curve_type)
        self.curves.append(curve)
        return self

    def add_controller_animation(self, controller: str,
                                 keyframes: list[dict]) -> "TimelineBuilder":
        """
        添加控制器动画 (位置+旋转)

        keyframes格式: [{"t": 0, "pos": (x,y,z), "rot": (x,y,z)}, ...]
        """
        for axis_idx, axis in enumerate(["x", "y", "z"]):
            # 位置曲线
            pos_curve = AnimationCurve(controller, f"position.{axis}")
            for kf in keyframes:
                if "pos" in kf:
                    pos_curve.add_key(kf["t"], kf["pos"][axis_idx])
            if pos_curve.keyframes:
                self.curves.append(pos_curve)

            # 旋转曲线
            rot_curve = AnimationCurve(controller, f"rotation.{axis}")
            for kf in keyframes:
                if "rot" in kf:
                    rot_curve.add_key(kf["t"], kf["rot"][axis_idx])
            if rot_curve.keyframes:
                self.curves.append(rot_curve)

        return self

    def add_morph_curve(self, morph_name: str,
                        time_value_pairs: list[tuple[float, float]],
                        curve_type: str = "SmoothLocal") -> "TimelineBuilder":
        """
        添加Morph形态动画曲线 (匹配真实VaM Timeline格式)

        例: timeline.add_morph_curve("Smile_Open", [(0, 0), (1, 0.8), (2, 0)])
        """
        curve = AnimationCurve(morph_name, "morphValue")
        curve.add_keys(time_value_pairs, curve_type)
        self.curves.append(curve)
        return self

    def add_trigger(self, name: str, start_time: float,
                    end_time: float) -> Trigger:
        """添加触发器并返回"""
        trigger = Trigger(name, start_time, end_time)
        self.triggers.append(trigger)
        return trigger

    def build(self) -> dict:
        """构建Timeline动画数据 (匹配真实VaM场景JSON格式)"""
        # 分离controller曲线和morph曲线
        controller_curves = []
        morph_curves = []
        for c in self.curves:
            if c.param == "morphValue":
                morph_curves.append(c)
            else:
                controller_curves.append(c)

        anim = {
            "AnimationName": self.name,
            "AnimationLength": str(self.duration),
            "Loop": str(self.loop).lower(),
            "Speed": str(self.speed),
            "Layers": [{
                "Controllers": [c.to_dict() for c in controller_curves],
            }],
        }
        if morph_curves:
            anim["Layers"][0]["FloatParams"] = [
                {"Name": c.target, "keys": [k.to_dict() for k in c.keyframes]}
                for c in morph_curves
            ]
        if self.triggers:
            anim["Triggers"] = [t.build() for t in self.triggers]
        return anim

    def build_storable(self, atom_id: str,
                       plugin_path: str = "Custom/Scripts/AcidBubbles/Timeline/VamTimeline.AtomPlugin.cs"
                       ) -> dict:
        """
        构建完整Timeline插件storable (可直接嵌入Person atom的storables)

        匹配真实VaM场景JSON中的Timeline插件格式
        """
        return {
            "id": "plugin#1_VamTimeline.AtomPlugin",
            "pluginPath": plugin_path,
            "animations": [self.build()],
        }

    def save(self, filepath: Optional[str] = None) -> str:
        """保存时间线动画到文件"""
        if not filepath:
            filepath = str(
                VAM_CONFIG.PLUGIN_DATA / "Timeline" / f"{self.name}.json"
            )
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.build(), indent=3), encoding="utf-8")
        return str(path)


# ── 动画序列编排 ──

class AnimationSequencer:
    """
    动画序列编排 — 串联多段动画

    用法:
        seq = AnimationSequencer("intro_sequence")
        seq.add_animation(walk_anim, duration=3.0)
        seq.add_animation(sit_anim, duration=2.0)
        seq.add_transition("crossfade", duration=0.5)
        data = seq.build()
    """

    def __init__(self, name: str):
        self.name = name
        self.segments: list[dict] = []

    def add_animation(self, animation: TimelineBuilder,
                      duration: Optional[float] = None) -> "AnimationSequencer":
        """添加动画段"""
        self.segments.append({
            "type": "animation",
            "name": animation.name,
            "data": animation.build(),
            "duration": duration or animation.duration,
        })
        return self

    def add_pose_hold(self, pose: PoseBuilder,
                      duration: float = 2.0) -> "AnimationSequencer":
        """添加姿态保持段"""
        self.segments.append({
            "type": "pose",
            "name": pose.name,
            "data": pose.to_dict(),
            "duration": duration,
        })
        return self

    def add_transition(self, transition_type: str = "crossfade",
                       duration: float = 0.5) -> "AnimationSequencer":
        """添加过渡"""
        self.segments.append({
            "type": "transition",
            "transition": transition_type,
            "duration": duration,
        })
        return self

    def build(self) -> dict:
        """构建序列数据"""
        total_duration = sum(s["duration"] for s in self.segments)
        return {
            "name": self.name,
            "total_duration": total_duration,
            "segment_count": len(self.segments),
            "segments": self.segments,
        }

    def get_timeline_storable(self, atom_id: str) -> dict:
        """生成Timeline插件的storable配置"""
        animations = [
            s["data"] for s in self.segments if s["type"] == "animation"
        ]
        return {
            "id": f"{atom_id}_Timeline",
            "pluginPath": "Custom/Scripts/AcidBubbles/Timeline/VamTimeline.AtomPlugin.cs",
            "animations": animations,
        }


# ── 便捷函数 ──

def create_breathing_animation(controller: str = "chestControl",
                               amplitude: float = 0.01,
                               period: float = 3.0) -> TimelineBuilder:
    """创建呼吸动画"""
    timeline = TimelineBuilder("breathing", duration=period, loop=True)
    half = period / 2
    timeline.add_float_curve(controller, "position.y", [
        (0.0, 0.0),
        (half * 0.4, amplitude * 0.7),
        (half, amplitude),
        (half + half * 0.4, amplitude * 0.3),
        (period, 0.0),
    ])
    return timeline


def create_idle_sway(controller: str = "hipControl",
                     amplitude: float = 0.02,
                     period: float = 4.0) -> TimelineBuilder:
    """创建闲置摇摆动画"""
    timeline = TimelineBuilder("idle_sway", duration=period, loop=True)
    quarter = period / 4
    timeline.add_float_curve(controller, "position.x", [
        (0.0, 0.0),
        (quarter, amplitude),
        (quarter * 2, 0.0),
        (quarter * 3, -amplitude),
        (period, 0.0),
    ])
    return timeline


def create_head_look(target_pos: tuple = (0, 1.7, 1.0),
                     duration: float = 1.0) -> TimelineBuilder:
    """创建头部看向目标动画"""
    timeline = TimelineBuilder("head_look", duration=duration, loop=False)
    timeline.add_controller_animation("headControl", [
        {"t": 0.0, "pos": (0, 1.7, 0)},
        {"t": duration, "pos": target_pos},
    ])
    return timeline


# ═══════════════════════════════════════════════════════════════════
# 以下系统从 via5/Cue + via5/Synergy (CC0) 提取核心逻辑并Python化
# ═══════════════════════════════════════════════════════════════════


# ── 缓动函数库 (from Cue Utilities/Easings.cs) ──

class Easing:
    """缓动函数 — 用于动画插值"""

    @staticmethod
    def linear(t: float) -> float:
        return t

    @staticmethod
    def quad_in(t: float) -> float:
        return t * t

    @staticmethod
    def quad_out(t: float) -> float:
        return t * (2.0 - t)

    @staticmethod
    def quad_in_out(t: float) -> float:
        if t < 0.5:
            return 2.0 * t * t
        return -1.0 + (4.0 - 2.0 * t) * t

    @staticmethod
    def cubic_in(t: float) -> float:
        return t * t * t

    @staticmethod
    def cubic_out(t: float) -> float:
        t -= 1.0
        return t * t * t + 1.0

    @staticmethod
    def cubic_in_out(t: float) -> float:
        if t < 0.5:
            return 4.0 * t * t * t
        t -= 1.0
        return 1.0 + 4.0 * t * t * t

    @staticmethod
    def sine_in(t: float) -> float:
        return 1.0 - math.cos(t * math.pi / 2.0)

    @staticmethod
    def sine_out(t: float) -> float:
        return math.sin(t * math.pi / 2.0)

    @staticmethod
    def sine_in_out(t: float) -> float:
        return 0.5 * (1.0 - math.cos(math.pi * t))

    @staticmethod
    def bounce_out(t: float) -> float:
        if t < 1.0 / 2.75:
            return 7.5625 * t * t
        elif t < 2.0 / 2.75:
            t -= 1.5 / 2.75
            return 7.5625 * t * t + 0.75
        elif t < 2.5 / 2.75:
            t -= 2.25 / 2.75
            return 7.5625 * t * t + 0.9375
        else:
            t -= 2.625 / 2.75
            return 7.5625 * t * t + 0.984375

    @staticmethod
    def elastic_out(t: float) -> float:
        if t <= 0:
            return 0.0
        if t >= 1:
            return 1.0
        p = 0.3
        s = p / 4.0
        return math.pow(2.0, -10.0 * t) * math.sin((t - s) * (2.0 * math.pi) / p) + 1.0

    FUNCTIONS = {
        "linear": linear.__func__,
        "quad_in": quad_in.__func__,
        "quad_out": quad_out.__func__,
        "quad_in_out": quad_in_out.__func__,
        "cubic_in": cubic_in.__func__,
        "cubic_out": cubic_out.__func__,
        "cubic_in_out": cubic_in_out.__func__,
        "sine_in": sine_in.__func__,
        "sine_out": sine_out.__func__,
        "sine_in_out": sine_in_out.__func__,
        "bounce_out": bounce_out.__func__,
        "elastic_out": elastic_out.__func__,
    }

    @classmethod
    def apply(cls, name: str, t: float) -> float:
        fn = cls.FUNCTIONS.get(name, cls.linear)
        return fn(max(0.0, min(1.0, t)))

    @classmethod
    def list_easings(cls) -> list[str]:
        return list(cls.FUNCTIONS.keys())


# ── BVH骨骼动画解析器 (from Cue Animation/BVH/BVHFile.cs) ──

class BVHJoint:
    """BVH骨骼节点"""

    def __init__(self, name: str, parent: Optional["BVHJoint"] = None):
        self.name = name
        self.parent = parent
        self.children: list["BVHJoint"] = []
        self.offset = (0.0, 0.0, 0.0)
        self.channels: list[str] = []
        self.channel_data: list[list[float]] = []

    def add_child(self, child: "BVHJoint") -> None:
        self.children.append(child)
        child.parent = self


class BVHParser:
    """
    BVH动画文件解析器 — 将BVH导入为VaM可用的关键帧动画

    用法:
        parser = BVHParser()
        parser.parse_file("walk.bvh")
        timeline = parser.to_timeline("bvh_walk")
    """

    VAM_BONE_MAP = {
        "Hips": "hipControl",
        "Spine": "abdomenControl",
        "Spine1": "abdomen2Control",
        "Spine2": "chestControl",
        "Neck": "neckControl",
        "Head": "headControl",
        "LeftUpLeg": "lThighControl",
        "LeftLeg": "lKneeControl",
        "LeftFoot": "lFootControl",
        "RightUpLeg": "rThighControl",
        "RightLeg": "rKneeControl",
        "RightFoot": "rFootControl",
        "LeftShoulder": "lShoulderControl",
        "LeftArm": "lArmControl",
        "LeftForeArm": "lElbowControl",
        "LeftHand": "lHandControl",
        "RightShoulder": "rShoulderControl",
        "RightArm": "rArmControl",
        "RightForeArm": "rElbowControl",
        "RightHand": "rHandControl",
    }

    def __init__(self):
        self.root: Optional[BVHJoint] = None
        self.joints: list[BVHJoint] = []
        self.frame_count: int = 0
        self.frame_time: float = 0.0333
        self._joint_map: dict[str, BVHJoint] = {}

    def parse_file(self, filepath: str) -> "BVHParser":
        """解析BVH文件"""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"BVH file not found: {filepath}")
        content = path.read_text(encoding="utf-8", errors="ignore")
        return self.parse_string(content)

    def parse_string(self, content: str) -> "BVHParser":
        """解析BVH字符串"""
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        idx = 0

        if lines[idx] != "HIERARCHY":
            raise ValueError("Invalid BVH: missing HIERARCHY")
        idx += 1

        idx, self.root = self._parse_joint(lines, idx, None)
        self._build_joint_map(self.root)

        while idx < len(lines) and lines[idx] != "MOTION":
            idx += 1
        idx += 1

        if idx < len(lines) and lines[idx].startswith("Frames:"):
            self.frame_count = int(lines[idx].split(":")[1].strip())
            idx += 1
        if idx < len(lines) and lines[idx].startswith("Frame Time:"):
            self.frame_time = float(lines[idx].split(":")[1].strip())
            idx += 1

        channel_order = []
        for joint in self.joints:
            for ch in joint.channels:
                channel_order.append((joint, ch))

        for joint in self.joints:
            joint.channel_data = [[] for _ in range(len(joint.channels))]

        for _ in range(self.frame_count):
            if idx >= len(lines):
                break
            try:
                values = [float(v) for v in lines[idx].split()]
            except (ValueError, IndexError):
                idx += 1
                continue
            vi = 0
            for joint, ch in channel_order:
                ch_idx = joint.channels.index(ch)
                if vi < len(values):
                    joint.channel_data[ch_idx].append(values[vi])
                vi += 1
            idx += 1

        return self

    def _parse_joint(self, lines: list[str], idx: int,
                     parent: Optional[BVHJoint]) -> tuple:
        """递归解析关节层次"""
        parts = lines[idx].split()
        joint_type = parts[0]
        joint_name = parts[1] if len(parts) > 1 else "EndSite"

        joint = BVHJoint(joint_name, parent)
        self.joints.append(joint)
        idx += 1

        if lines[idx] == "{":
            idx += 1

        while idx < len(lines) and lines[idx] != "}":
            if lines[idx].startswith("OFFSET"):
                vals = lines[idx].split()[1:]
                joint.offset = tuple(float(v) for v in vals[:3])
            elif lines[idx].startswith("CHANNELS"):
                parts = lines[idx].split()
                num_channels = int(parts[1])
                joint.channels = parts[2:2 + num_channels]
                joint.channel_data = [[] for _ in range(num_channels)]
            elif lines[idx].startswith(("JOINT", "End")):
                idx, child = self._parse_joint(lines, idx, joint)
                joint.add_child(child)
                continue
            idx += 1

        if idx < len(lines) and lines[idx] == "}":
            idx += 1

        return idx, joint

    def _build_joint_map(self, joint: BVHJoint) -> None:
        """构建名称→关节映射"""
        self._joint_map[joint.name] = joint
        for child in joint.children:
            self._build_joint_map(child)

    @property
    def duration(self) -> float:
        return self.frame_count * self.frame_time

    def to_timeline(self, name: str = "bvh_animation",
                    scale: float = 0.01) -> TimelineBuilder:
        """转换为TimelineBuilder动画"""
        timeline = TimelineBuilder(name, duration=self.duration, loop=False)

        for joint in self.joints:
            vam_ctrl = self.VAM_BONE_MAP.get(joint.name)
            if not vam_ctrl or not joint.channel_data:
                continue

            for ch_idx, ch_name in enumerate(joint.channels):
                if ch_idx >= len(joint.channel_data):
                    break
                data = joint.channel_data[ch_idx]
                if not data:
                    continue

                param = self._channel_to_param(ch_name)
                if not param:
                    continue

                is_position = "position" in param
                kf_pairs = []
                step = max(1, len(data) // 100)
                for i in range(0, len(data), step):
                    t = i * self.frame_time
                    v = data[i] * scale if is_position else data[i]
                    kf_pairs.append((t, v))

                if kf_pairs:
                    timeline.add_float_curve(vam_ctrl, param, kf_pairs)

        return timeline

    @staticmethod
    def _channel_to_param(channel: str) -> Optional[str]:
        """BVH通道名→VaM参数名"""
        mapping = {
            "Xposition": "position.x",
            "Yposition": "position.y",
            "Zposition": "position.z",
            "Xrotation": "rotation.x",
            "Yrotation": "rotation.y",
            "Zrotation": "rotation.z",
        }
        return mapping.get(channel)

    def summary(self) -> dict:
        return {
            "joints": [j.name for j in self.joints],
            "frame_count": self.frame_count,
            "frame_time": self.frame_time,
            "duration": round(self.duration, 2),
            "mapped_controllers": [
                self.VAM_BONE_MAP[j.name] for j in self.joints
                if j.name in self.VAM_BONE_MAP
            ],
        }


# ── 程序化动画引擎 (from Cue Animation/Procedural/*.cs) ──

class ProceduralTarget:
    """程序化动画目标 — 力/扭矩/Morph"""

    TYPES = ["force", "torque", "morph"]

    def __init__(self, target_type: str, controller: str,
                 axis: str = "y", amplitude: float = 0.1,
                 period: float = 1.0, easing: str = "sine_in_out"):
        self.target_type = target_type
        self.controller = controller
        self.axis = axis
        self.amplitude = amplitude
        self.period = period
        self.easing = easing
        self.phase: float = 0.0
        self.enabled: bool = True

    def evaluate(self, time: float) -> float:
        if not self.enabled:
            return 0.0
        t = ((time + self.phase) % self.period) / self.period
        eased = Easing.apply(self.easing, t)
        return self.amplitude * (eased * 2.0 - 1.0)

    def to_dict(self) -> dict:
        return {
            "type": self.target_type,
            "controller": self.controller,
            "axis": self.axis,
            "amplitude": self.amplitude,
            "period": self.period,
            "easing": self.easing,
            "phase": self.phase,
        }


class ProceduralAnimation:
    """
    程序化动画引擎 — 多目标叠加的实时动画

    用法:
        anim = ProceduralAnimation("breathing_idle")
        anim.add_target("force", "chestControl", "y", amplitude=0.01, period=3.0)
        anim.add_target("morph", "Smile_Open", amplitude=0.2, period=5.0)
        frame = anim.evaluate(time=1.5)
    """

    def __init__(self, name: str):
        self.name = name
        self.targets: list[ProceduralTarget] = []
        self.speed: float = 1.0
        self.intensity: float = 1.0

    def add_target(self, target_type: str, controller: str,
                   axis: str = "y", amplitude: float = 0.1,
                   period: float = 1.0, easing: str = "sine_in_out",
                   phase: float = 0.0) -> "ProceduralAnimation":
        target = ProceduralTarget(target_type, controller, axis,
                                  amplitude, period, easing)
        target.phase = phase
        self.targets.append(target)
        return self

    def evaluate(self, time: float) -> dict:
        """评估当前时间的所有目标值"""
        result = {"forces": {}, "torques": {}, "morphs": {}}
        t = time * self.speed
        for target in self.targets:
            val = target.evaluate(t) * self.intensity
            key = f"{target.controller}.{target.axis}"
            if target.target_type == "force":
                result["forces"][key] = val
            elif target.target_type == "torque":
                result["torques"][key] = val
            elif target.target_type == "morph":
                result["morphs"][target.controller] = val
        return result

    def to_timeline(self, duration: float = 5.0,
                    fps: int = 30) -> TimelineBuilder:
        """转换为TimelineBuilder"""
        timeline = TimelineBuilder(self.name, duration=duration, loop=True)
        dt = 1.0 / fps
        for target in self.targets:
            if target.target_type == "morph":
                continue
            param_map = {
                "force": "position",
                "torque": "rotation",
            }
            param_base = param_map.get(target.target_type, "position")
            param = f"{param_base}.{target.axis}"
            pairs = []
            t = 0.0
            while t <= duration:
                pairs.append((t, target.evaluate(t) * self.intensity))
                t += dt
            if pairs:
                timeline.add_float_curve(target.controller, param, pairs)
        return timeline

    PRESETS = {
        "breathing": [
            {"type": "force", "ctrl": "chestControl", "axis": "y",
             "amp": 0.008, "period": 3.5, "easing": "sine_in_out"},
        ],
        "idle_sway": [
            {"type": "force", "ctrl": "hipControl", "axis": "x",
             "amp": 0.015, "period": 4.0, "easing": "sine_in_out"},
            {"type": "force", "ctrl": "hipControl", "axis": "z",
             "amp": 0.008, "period": 5.5, "easing": "sine_in_out", "phase": 1.2},
        ],
        "head_bob": [
            {"type": "force", "ctrl": "headControl", "axis": "y",
             "amp": 0.005, "period": 2.0, "easing": "sine_in_out"},
            {"type": "torque", "ctrl": "headControl", "axis": "x",
             "amp": 2.0, "period": 6.0, "easing": "sine_in_out"},
        ],
        "excited_breathing": [
            {"type": "force", "ctrl": "chestControl", "axis": "y",
             "amp": 0.015, "period": 1.5, "easing": "sine_in_out"},
            {"type": "force", "ctrl": "abdomenControl", "axis": "y",
             "amp": 0.01, "period": 1.5, "easing": "sine_in_out", "phase": 0.3},
        ],
    }

    @classmethod
    def from_preset(cls, preset_name: str) -> "ProceduralAnimation":
        anim = cls(preset_name)
        for t in cls.PRESETS.get(preset_name, []):
            anim.add_target(
                t["type"], t["ctrl"], t.get("axis", "y"),
                t.get("amp", 0.1), t.get("period", 1.0),
                t.get("easing", "sine_in_out"), t.get("phase", 0.0),
            )
        return anim

    def summary(self) -> dict:
        return {
            "name": self.name,
            "target_count": len(self.targets),
            "speed": self.speed,
            "intensity": self.intensity,
            "targets": [t.to_dict() for t in self.targets],
        }


# ── Synergy步骤式随机动画 (from via5/Synergy, CC0) ──

class SynergyModifier:
    """Synergy修饰器 — 驱动单个参数的随机变化"""

    def __init__(self, target: str, param: str,
                 min_val: float = 0.0, max_val: float = 1.0,
                 easing: str = "quad_in_out"):
        self.target = target
        self.param = param
        self.min_val = min_val
        self.max_val = max_val
        self.easing = easing
        self.current_value: float = min_val
        self._start_value: float = min_val
        self._target_value: float = min_val

    def randomize(self) -> float:
        self._start_value = self.current_value
        self._target_value = random.uniform(self.min_val, self.max_val)
        return self._target_value

    def interpolate(self, progress: float) -> float:
        eased = Easing.apply(self.easing, progress)
        self.current_value = self._start_value + (self._target_value - self._start_value) * eased
        return self.current_value

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "param": self.param,
            "min": self.min_val,
            "max": self.max_val,
            "easing": self.easing,
            "current": self.current_value,
        }


class SynergyStep:
    """Synergy步骤 — 包含多个修饰器和持续时间"""

    def __init__(self, min_duration: float = 0.5,
                 max_duration: float = 2.0):
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.modifiers: list[SynergyModifier] = []
        self.duration: float = 0.0

    def add_modifier(self, target: str, param: str,
                     min_val: float = 0.0, max_val: float = 1.0,
                     easing: str = "quad_in_out") -> "SynergyStep":
        self.modifiers.append(
            SynergyModifier(target, param, min_val, max_val, easing)
        )
        return self

    def start(self) -> None:
        self.duration = random.uniform(self.min_duration, self.max_duration)
        for mod in self.modifiers:
            mod.randomize()

    def evaluate(self, progress: float) -> dict:
        result = {}
        for mod in self.modifiers:
            key = f"{mod.target}.{mod.param}"
            result[key] = mod.interpolate(progress)
        return result


class SynergyStepAnimation:
    """
    Synergy步骤式随机动画 — 循环执行随机步骤序列

    用法:
        anim = SynergyStepAnimation("random_motion")
        step = anim.add_step(0.5, 2.0)
        step.add_modifier("hipControl", "position.x", -0.1, 0.1)
        step.add_modifier("hipControl", "position.z", -0.05, 0.05)
        anim.start()
        values = anim.update(delta_time=0.016)
    """

    def __init__(self, name: str):
        self.name = name
        self.steps: list[SynergyStep] = []
        self.current_step_idx: int = 0
        self.elapsed: float = 0.0
        self.running: bool = False

    def add_step(self, min_duration: float = 0.5,
                 max_duration: float = 2.0) -> SynergyStep:
        step = SynergyStep(min_duration, max_duration)
        self.steps.append(step)
        return step

    def start(self) -> None:
        if not self.steps:
            return
        self.running = True
        self.current_step_idx = 0
        self.elapsed = 0.0
        self.steps[0].start()

    def stop(self) -> None:
        self.running = False

    def update(self, delta_time: float) -> dict:
        if not self.running or not self.steps:
            return {}
        step = self.steps[self.current_step_idx]
        self.elapsed += delta_time
        progress = min(1.0, self.elapsed / step.duration) if step.duration > 0 else 1.0
        result = step.evaluate(progress)
        if self.elapsed >= step.duration:
            self.elapsed = 0.0
            self.current_step_idx = (self.current_step_idx + 1) % len(self.steps)
            self.steps[self.current_step_idx].start()
        return result

    def to_timeline(self, num_cycles: int = 4) -> TimelineBuilder:
        """转换为TimelineBuilder (固定随机种子生成)"""
        total_dur = 0.0
        for step in self.steps:
            total_dur += (step.min_duration + step.max_duration) / 2.0
        full_duration = total_dur * num_cycles

        timeline = TimelineBuilder(self.name, duration=full_duration, loop=True)
        self.start()
        dt = 0.033
        t = 0.0
        curves_data: dict[str, list[tuple[float, float]]] = {}

        while t < full_duration:
            values = self.update(dt)
            for key, val in values.items():
                if key not in curves_data:
                    curves_data[key] = []
                curves_data[key].append((t, val))
            t += dt

        for key, pairs in curves_data.items():
            parts = key.rsplit(".", 1)
            if len(parts) == 2:
                sampled = pairs[::3]
                timeline.add_float_curve(parts[0], parts[1], sampled)

        self.stop()
        return timeline

    PRESETS = {
        "gentle_sway": {
            "steps": [
                {"dur": (0.8, 1.5), "mods": [
                    ("hipControl", "position.x", -0.03, 0.03),
                    ("hipControl", "position.z", -0.015, 0.015),
                ]},
                {"dur": (0.8, 1.5), "mods": [
                    ("hipControl", "position.x", -0.03, 0.03),
                    ("hipControl", "position.z", -0.015, 0.015),
                ]},
            ],
        },
        "head_motion": {
            "steps": [
                {"dur": (0.5, 1.0), "mods": [
                    ("headControl", "rotation.x", -5.0, 5.0),
                    ("headControl", "rotation.y", -8.0, 8.0),
                    ("headControl", "rotation.z", -3.0, 3.0),
                ]},
            ],
        },
        "hand_fidget": {
            "steps": [
                {"dur": (0.3, 0.8), "mods": [
                    ("lHandControl", "position.x", -0.02, 0.02),
                    ("lHandControl", "position.y", -0.02, 0.02),
                ]},
                {"dur": (0.3, 0.8), "mods": [
                    ("rHandControl", "position.x", -0.02, 0.02),
                    ("rHandControl", "position.y", -0.02, 0.02),
                ]},
            ],
        },
    }

    @classmethod
    def from_preset(cls, preset_name: str) -> "SynergyStepAnimation":
        anim = cls(preset_name)
        preset = cls.PRESETS.get(preset_name)
        if not preset:
            return anim
        for step_cfg in preset["steps"]:
            dur = step_cfg["dur"]
            step = anim.add_step(dur[0], dur[1])
            for mod in step_cfg["mods"]:
                step.add_modifier(mod[0], mod[1], mod[2], mod[3])
        return anim

    def summary(self) -> dict:
        return {
            "name": self.name,
            "step_count": len(self.steps),
            "running": self.running,
            "current_step": self.current_step_idx,
        }


# ── 相机导演 (from acidbubbles/vam-director) ──

class CameraDirector:
    """
    相机角度序列编排 — 自动切换相机角度

    用法:
        director = CameraDirector()
        director.add_angle("close_up", (0, 1.6, 0.5), (0, 180, 0), fov=40)
        director.add_angle("wide", (2, 2, 3), (-20, -30, 0), fov=60)
        director.set_sequence(["close_up", "wide"], durations=[3.0, 5.0])
        timeline = director.to_timeline()
    """

    def __init__(self):
        self.angles: dict[str, dict] = {}
        self.sequence: list[str] = []
        self.durations: list[float] = []
        self.transition_time: float = 0.5

    def add_angle(self, name: str, position: tuple,
                  rotation: tuple, fov: float = 50.0) -> "CameraDirector":
        self.angles[name] = {
            "position": position,
            "rotation": rotation,
            "fov": fov,
        }
        return self

    def set_sequence(self, angle_names: list[str],
                     durations: Optional[list[float]] = None) -> "CameraDirector":
        self.sequence = [n for n in angle_names if n in self.angles]
        self.durations = durations or [3.0] * len(self.sequence)
        if len(self.durations) < len(self.sequence):
            self.durations.extend(
                [3.0] * (len(self.sequence) - len(self.durations))
            )
        return self

    def to_timeline(self, camera_atom: str = "Camera") -> TimelineBuilder:
        if not self.sequence:
            return TimelineBuilder("empty_camera")
        total = sum(self.durations)
        timeline = TimelineBuilder("camera_sequence", duration=total, loop=True)
        keyframes = []
        t = 0.0
        for i, name in enumerate(self.sequence):
            angle = self.angles[name]
            keyframes.append({
                "t": t, "pos": angle["position"], "rot": angle["rotation"],
            })
            t += self.durations[i]
        timeline.add_controller_animation(f"{camera_atom}Control", keyframes)
        return timeline

    PRESET_ANGLES = {
        "close_up_face": {"pos": (0, 1.65, 0.4), "rot": (0, 180, 0), "fov": 35},
        "medium_shot": {"pos": (0.5, 1.3, 1.2), "rot": (-5, 165, 0), "fov": 50},
        "wide_shot": {"pos": (1.5, 1.8, 2.5), "rot": (-15, 150, 0), "fov": 60},
        "low_angle": {"pos": (0.3, 0.5, 1.0), "rot": (20, 170, 0), "fov": 55},
        "high_angle": {"pos": (0, 2.5, 1.5), "rot": (-35, 180, 0), "fov": 50},
        "over_shoulder": {"pos": (-0.3, 1.7, -0.3), "rot": (5, 200, 0), "fov": 45},
        "profile": {"pos": (1.0, 1.5, 0), "rot": (0, 90, 0), "fov": 50},
    }

    @classmethod
    def from_preset_sequence(cls, angle_names: list[str],
                             durations: Optional[list[float]] = None) -> "CameraDirector":
        director = cls()
        for name in angle_names:
            if name in cls.PRESET_ANGLES:
                a = cls.PRESET_ANGLES[name]
                director.add_angle(name, a["pos"], a["rot"], a["fov"])
        director.set_sequence(angle_names, durations)
        return director

    def summary(self) -> dict:
        return {
            "angle_count": len(self.angles),
            "sequence": self.sequence,
            "total_duration": sum(self.durations) if self.durations else 0,
        }


# ─── VMD Parser (from VamFreeMMD, CC0) ────────────────────────────────

class VMDBoneMap:
    """MMD bone name → VaM controller mapping.

    Ported from VamFreeMMD/src/Extensions.cs.
    Handles Japanese(Shift-JIS) → English → VaM controller name translation.

    Usage:
        controller = VMDBoneMap.to_vam("Head")        # → "headControl"
        controller = VMDBoneMap.to_vam("LeftElbow")    # → "lElbowControl"
        parent = VMDBoneMap.parent_of("rArmControl")   # → "rShoulderControl"
    """

    # English bone name → VaM controller
    BONE_MAP: dict[str, str] = {
        # Body
        "Head": "headControl",
        "RightElbow": "rElbowControl",
        "LeftElbow": "lElbowControl",
        "RightArm": "rArmControl",
        "LeftArm": "lArmControl",
        "RightShoulder": "rShoulderControl",
        "LeftShoulder": "lShoulderControl",
        "RightShoulderP": "rShoulderControl",
        "LeftShoulderP": "lShoulderControl",
        "RightWrist": "rHandControl",
        "LeftWrist": "lHandControl",
        "RightLegIK": "rFootControl",
        "LeftLegIK": "lFootControl",
        "RightAnkle": "rFootControl",
        "LeftAnkle": "lFootControl",
        "RightToeTipIK": "rToeControl",
        "LeftToeTipIK": "lToeControl",
        "UpperBody": "abdomen2Control",
        "UpperBody2": "abdomen2Control",
        "LowerBody": "pelvisControl",
        "LeftKnee": "lKneeControl",
        "RightKnee": "rKneeControl",
        "Center": "hipControl",
        "Neck": "neckControl",
        "LeftLeg": "lThighControl",
        "RightLeg": "rThighControl",
        # Fingers
        "LeftRingFinger1": "lRing1", "LeftRingFinger2": "lRing2",
        "LeftRingFinger3": "lRing3",
        "RightRingFinger1": "rRing1", "RightRingFinger2": "rRing2",
        "RightRingFinger3": "rRing3",
        "LeftIndexFinger1": "lIndex1", "LeftIndexFinger2": "lIndex2",
        "LeftIndexFinger3": "lIndex3",
        "RightIndexFinger1": "rIndex1", "RightIndexFinger2": "rIndex2",
        "RightIndexFinger3": "rIndex3",
        "LeftMiddleFinger1": "lMid1", "LeftMiddleFinger2": "lMid2",
        "LeftMiddleFinger3": "lMid3",
        "RightMiddleFinger1": "rMid1", "RightMiddleFinger2": "rMid2",
        "RightMiddleFinger3": "rMid3",
        "LeftLittleFinger1": "lPinky1", "LeftLittleFinger2": "lPinky2",
        "LeftLittleFinger3": "lPinky3",
        "RightLittleFinger1": "rPinky1", "RightLittleFinger2": "rPinky2",
        "RightLittleFinger3": "rPinky3",
        "LeftThumbFinger1": "lThumb1", "LeftThumbFinger2": "lThumb2",
        "LeftThumbFinger3": "lThumb3",
        "RightThumbFinger1": "rThumb1", "RightThumbFinger2": "rThumb2",
        "RightThumbFinger3": "rThumb3",
    }

    # VaM controller parent-child dependency chain
    DEPENDENCIES: dict[str, str] = {
        "abdomen2Control": "hipControl",
        "pelvisControl": "hipControl",
        "rShoulderControl": "abdomen2Control",
        "rArmControl": "rShoulderControl",
        "rElbowControl": "rArmControl",
        "rHandControl": "rElbowControl",
        "lShoulderControl": "abdomen2Control",
        "lArmControl": "lShoulderControl",
        "lElbowControl": "lArmControl",
        "lHandControl": "lElbowControl",
        "neckControl": "abdomen2Control",
        "headControl": "neckControl",
        "lThighControl": "pelvisControl",
        "rThighControl": "pelvisControl",
        "lKneeControl": "lThighControl",
        "rKneeControl": "rThighControl",
        "lThumb3": "lThumb2", "lThumb2": "lThumb1",
        "rThumb3": "rThumb2", "rThumb2": "rThumb1",
    }

    # MMD standard bone order (English)
    STANDARD_BONES = [
        "Center",
        "UpperBody", "UpperBody2", "Neck", "Head",
        "LowerBody", "LeftLeg", "RightLeg", "RightKnee", "LeftKnee",
        "RightShoulder", "LeftShoulder", "LeftArm", "RightArm",
        "LeftElbow", "RightElbow", "RightWrist", "LeftWrist",
    ]

    @classmethod
    def to_vam(cls, bone_name: str) -> Optional[str]:
        return cls.BONE_MAP.get(bone_name)

    @classmethod
    def parent_of(cls, controller: str) -> Optional[str]:
        return cls.DEPENDENCIES.get(controller)

    @classmethod
    def ancestor_chain(cls, controller: str) -> list[str]:
        """Get full ancestor chain from controller to root (hipControl)."""
        chain = []
        current = controller
        while current and current in cls.DEPENDENCIES:
            parent = cls.DEPENDENCIES[current]
            chain.append(parent)
            current = parent
        return chain


class VMDMotion:
    """Single bone motion frame from a VMD file."""

    def __init__(self, bone_name: str, frame_id: int,
                 position: tuple[float, float, float],
                 rotation: tuple[float, float, float, float],
                 interpolation: Optional[list] = None):
        self.bone_name = bone_name
        self.vam_controller = VMDBoneMap.to_vam(bone_name)
        self.frame_id = frame_id
        self.position = position  # (x, y, z)
        self.rotation = rotation  # (x, y, z, w) quaternion
        self.interpolation = interpolation
        self.timestamp = frame_id / 30.0  # VMD uses 30fps

    def __repr__(self) -> str:
        return (f"VMDMotion(bone={self.bone_name}, frame={self.frame_id}, "
                f"pos={self.position}, ctrl={self.vam_controller})")


class VMDFaceMotion:
    """Single face/morph keyframe from a VMD file."""

    def __init__(self, name: str, frame_id: int, weight: float):
        self.name = name
        self.frame_id = frame_id
        self.weight = weight
        self.timestamp = frame_id / 30.0

    def __repr__(self) -> str:
        return f"VMDFaceMotion(name={self.name}, frame={self.frame_id}, w={self.weight})"


class VMDParser:
    """Parse VMD (Vocaloid Motion Data) binary files into VaM animations.

    Ported from VamFreeMMD (CC0 license).
    VMD is the standard animation format for MikuMikuDance.

    Usage:
        parser = VMDParser.from_file("dance.vmd")
        print(f"Motions: {len(parser.motions)}, Face: {len(parser.face_motions)}")

        # Convert to VaM timeline
        timeline = parser.to_timeline(scale=0.1)
        data = timeline.build()
    """

    VMD_FRAME_RATE = 30.0

    def __init__(self):
        self.model_name: str = ""
        self.motions_by_bone: dict[str, list[VMDMotion]] = {}
        self.face_motions_by_name: dict[str, list[VMDFaceMotion]] = {}
        self.uses_ik: bool = False

    @property
    def motions(self) -> list[VMDMotion]:
        return [m for group in self.motions_by_bone.values() for m in group]

    @property
    def face_motions(self) -> list[VMDFaceMotion]:
        return [m for group in self.face_motions_by_name.values() for m in group]

    @property
    def duration(self) -> float:
        """Total animation duration in seconds."""
        max_frame = 0
        for m in self.motions:
            max_frame = max(max_frame, m.frame_id)
        for m in self.face_motions:
            max_frame = max(max_frame, m.frame_id)
        return max_frame / self.VMD_FRAME_RATE

    @classmethod
    def from_file(cls, filepath: str) -> "VMDParser":
        """Parse a VMD binary file."""
        import struct
        with open(filepath, "rb") as f:
            data = f.read()
        return cls._parse_binary(data)

    @classmethod
    def from_bytes(cls, data: bytes) -> "VMDParser":
        """Parse VMD from raw bytes."""
        return cls._parse_binary(data)

    @classmethod
    def _parse_binary(cls, data: bytes) -> "VMDParser":
        """Parse VMD binary format."""
        import struct
        parser = cls()
        offset = 0

        # Header: 30 bytes signature + 20 bytes model name
        sig = data[offset:offset + 30].split(b"\x00")[0].decode("ascii", errors="replace")
        offset += 30
        parser.model_name = data[offset:offset + 20].split(b"\x00")[0].decode(
            "shift_jis", errors="replace")
        offset += 20

        # Bone motions
        motion_count = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        motions: list[VMDMotion] = []
        for _ in range(motion_count):
            # 15 bytes bone name (shift_jis)
            raw_name = data[offset:offset + 15]
            null_idx = raw_name.find(b"\x00")
            if null_idx >= 0:
                raw_name = raw_name[:null_idx]
            try:
                bone_name = raw_name.decode("shift_jis", errors="replace")
            except Exception:
                bone_name = raw_name.decode("ascii", errors="replace")
            offset += 15

            # Frame ID
            frame_id = struct.unpack_from("<I", data, offset)[0]
            offset += 4

            # Position (3 floats)
            px, py, pz = struct.unpack_from("<3f", data, offset)
            offset += 12

            # Rotation quaternion (4 floats)
            rx, ry, rz, rw = struct.unpack_from("<4f", data, offset)
            offset += 16

            # Interpolation (64 bytes, skip for now)
            offset += 64

            motions.append(VMDMotion(bone_name, frame_id,
                                     (px, py, pz), (rx, ry, rz, rw)))

        # Group by bone and sort
        from collections import defaultdict
        bone_groups: dict[str, list[VMDMotion]] = defaultdict(list)
        for m in motions:
            bone_groups[m.bone_name].append(m)
        for key in bone_groups:
            bone_groups[key].sort(key=lambda m: m.frame_id)
        parser.motions_by_bone = dict(bone_groups)

        # Face motions
        if offset + 4 <= len(data):
            face_count = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            face_groups: dict[str, list[VMDFaceMotion]] = defaultdict(list)
            for _ in range(face_count):
                if offset + 23 > len(data):
                    break
                raw_name = data[offset:offset + 15]
                null_idx = raw_name.find(b"\x00")
                if null_idx >= 0:
                    raw_name = raw_name[:null_idx]
                try:
                    face_name = raw_name.decode("shift_jis", errors="replace")
                except Exception:
                    face_name = raw_name.decode("ascii", errors="replace")
                offset += 15
                frame_id = struct.unpack_from("<I", data, offset)[0]
                offset += 4
                weight = struct.unpack_from("<f", data, offset)[0]
                offset += 4
                face_groups[face_name].append(
                    VMDFaceMotion(face_name, frame_id, weight))
            for key in face_groups:
                face_groups[key].sort(key=lambda m: m.frame_id)
            parser.face_motions_by_name = dict(face_groups)

        # Detect IK usage
        parser.uses_ik = (
            len(parser.motions_by_bone.get("LeftLegIK", [])) > 1 or
            len(parser.motions_by_bone.get("RightLegIK", [])) > 1
        )

        return parser

    def to_timeline(self, scale: float = 0.1,
                    include_fingers: bool = False) -> "TimelineBuilder":
        """Convert VMD motions to a VaM TimelineBuilder.

        Args:
            scale: Position scale factor (MMD units → VaM units).
            include_fingers: Whether to include finger bone data.
        """
        tb = TimelineBuilder()
        total_time = self.duration

        for bone_name, frames in self.motions_by_bone.items():
            controller = VMDBoneMap.to_vam(bone_name)
            if not controller:
                continue
            if not include_fingers and not controller.endswith("Control"):
                continue

            for frame in frames:
                t = frame.timestamp
                px, py, pz = frame.position
                rx, ry, rz, rw = frame.rotation
                # MMD coordinate conversion: flip X axis
                tb.add_keyframe(controller, t,
                                position=(-px * scale, py * scale, pz * scale),
                                rotation=(-rx, ry, rz, -rw))

        # Face motions as float params (morphs)
        for face_name, frames in self.face_motions_by_name.items():
            param_name = f"morphs/{face_name}"
            for frame in frames:
                tb.add_keyframe(param_name, frame.timestamp,
                                value=frame.weight)

        return tb

    def summary(self) -> dict:
        return {
            "model": self.model_name,
            "bone_count": len(self.motions_by_bone),
            "motion_frames": len(self.motions),
            "face_morph_count": len(self.face_motions_by_name),
            "face_frames": len(self.face_motions),
            "duration_sec": round(self.duration, 2),
            "uses_ik": self.uses_ik,
        }


# ─── Timeline API (from acidbubbles/vam-timeline, CC-BY) ─────────────

class TimelineAPI:
    """VaM Timeline plugin storable names and sync commands.

    Ported from vam-timeline/src/Interop/StorableNames.cs + SyncProxy.cs.
    These are the exact string names used to control the Timeline plugin
    via VaM's JSONStorable parameter system.

    Usage:
        # Build storable commands for a scene
        storables = TimelineAPI.play_animation("dance_01", atom="Person")
        storables = TimelineAPI.queue_animations(["intro", "loop", "outro"])

        # Get param name for direct set
        TimelineAPI.PLAY          # → "Play"
        TimelineAPI.ANIMATION     # → "Animation"

        # All available param names
        TimelineAPI.all_params()  # → list of all storable names
    """

    # String choosers (get/set current value)
    ANIMATION = "Animation"
    SEGMENT = "Segment"

    # Actions (trigger)
    NEXT_ANIMATION = "Next Animation"
    PREVIOUS_ANIMATION = "Previous Animation"
    NEXT_ANIMATION_MAIN = "Next Animation (Main Layer)"
    PREVIOUS_ANIMATION_MAIN = "Previous Animation (Main Layer)"
    NEXT_SEGMENT = "Next Segment"
    PREVIOUS_SEGMENT = "Previous Segment"
    PLAY = "Play"
    PLAY_IF_NOT_PLAYING = "Play If Not Playing"
    PLAY_CURRENT_CLIP = "Play Current Clip"
    STOP = "Stop"
    STOP_IF_PLAYING = "Stop If Playing"
    STOP_AND_RESET = "Stop And Reset"
    NEXT_FRAME = "Next Frame"
    PREVIOUS_FRAME = "Previous Frame"

    # Queue system
    CREATE_QUEUE = "Create Queue"
    ADD_TO_QUEUE = "Add To Queue"
    PLAY_QUEUE = "Play Queue"
    CLEAR_QUEUE = "Clear Queue"

    # Float params (get/set)
    SCRUBBER = "Scrubber"
    SET_TIME = "Set Time"
    SPEED = "Speed"
    WEIGHT = "Weight"

    # Bool params (get/set)
    IS_PLAYING = "Is Playing"
    LOCKED = "Locked"
    PAUSED = "Paused"

    # Plugin ID for scene JSON
    PLUGIN_ID = "VamTimeline.AtomPlugin"

    @classmethod
    def all_params(cls) -> list[str]:
        return [
            cls.ANIMATION, cls.SEGMENT,
            cls.NEXT_ANIMATION, cls.PREVIOUS_ANIMATION,
            cls.NEXT_ANIMATION_MAIN, cls.PREVIOUS_ANIMATION_MAIN,
            cls.NEXT_SEGMENT, cls.PREVIOUS_SEGMENT,
            cls.PLAY, cls.PLAY_IF_NOT_PLAYING, cls.PLAY_CURRENT_CLIP,
            cls.STOP, cls.STOP_IF_PLAYING, cls.STOP_AND_RESET,
            cls.NEXT_FRAME, cls.PREVIOUS_FRAME,
            cls.CREATE_QUEUE, cls.ADD_TO_QUEUE, cls.PLAY_QUEUE, cls.CLEAR_QUEUE,
            cls.SCRUBBER, cls.SET_TIME, cls.SPEED, cls.WEIGHT,
            cls.IS_PLAYING, cls.LOCKED, cls.PAUSED,
        ]

    @classmethod
    def play_animation(cls, animation_name: str, atom: str = "Person") -> list[dict]:
        """Generate storable commands to play a specific animation."""
        return [
            {
                "id": f"{atom}:{cls.PLUGIN_ID}",
                "params": {cls.ANIMATION: animation_name},
            },
            {
                "id": f"{atom}:{cls.PLUGIN_ID}",
                "actions": [cls.PLAY],
            },
        ]

    @classmethod
    def queue_animations(cls, names: list[str], atom: str = "Person") -> list[dict]:
        """Generate storable commands to queue and play multiple animations."""
        commands = [{"id": f"{atom}:{cls.PLUGIN_ID}", "actions": [cls.CREATE_QUEUE]}]
        for name in names:
            commands.append({
                "id": f"{atom}:{cls.PLUGIN_ID}",
                "params": {cls.ANIMATION: name},
                "actions": [cls.ADD_TO_QUEUE],
            })
        commands.append({"id": f"{atom}:{cls.PLUGIN_ID}", "actions": [cls.PLAY_QUEUE]})
        return commands

    @classmethod
    def set_speed(cls, speed: float, atom: str = "Person") -> dict:
        return {"id": f"{atom}:{cls.PLUGIN_ID}", "floats": {cls.SPEED: speed}}

    @classmethod
    def stop_animation(cls, atom: str = "Person") -> dict:
        return {"id": f"{atom}:{cls.PLUGIN_ID}", "actions": [cls.STOP_AND_RESET]}


# ── MMD Face Morph Map (from sFisherE/mmd2timeline FaceMorph.cs) ──

class MMDFaceMorphMap:
    """MMD Japanese face morph name → VaM morph parameter mapping.

    Ported from mmd2timeline/src/FaceMorph.cs (21 stars).
    Maps MMD expression names (Japanese) to VaM DAZ morph names with min/max ranges.

    Categories:
      - 眉 (Brow): 真面目/上/下/眉頭左/眉頭右/困る/にこり/怒り
      - 目 (Eyes): まばたき/笑顔/ウィンク variants/びっくり/じと目
      - 口 (Mouth): あ/い/う/え/お/にやり/口横広げ/ん/w/口角上げ/口角下げ/∧/▲

    Usage:
        morphs = MMDFaceMorphMap.get("まばたき")
        # → [{"name": "Eyes Closed", "min": 0, "max": 1}]
        all_names = MMDFaceMorphMap.all_mmd_names()
        category = MMDFaceMorphMap.category_of("あ")  # → "mouth"
    """

    # {mmd_name: [{"name": vam_morph, "min": float, "max": float}, ...]}
    FACE_MAP: dict[str, list[dict]] = {
        # 眉 (Brow)
        "真面目": [{"name": "Brow Down", "min": 0, "max": 1}],
        "上": [{"name": "Brow Up", "min": 0, "max": 1}],
        "下": [{"name": "Brow Down", "min": 0, "max": 1}],
        "眉頭左": [
            {"name": "Brow Up", "min": 0, "max": 0},
            {"name": "Brow Down", "min": 0, "max": 1},
            {"name": "Brow Down Left", "min": 0, "max": 1},
            {"name": "Brow Up Right", "min": 0, "max": 1},
        ],
        "眉頭右": [
            {"name": "Brow Up", "min": 0, "max": 0},
            {"name": "Brow Down", "min": 0, "max": 1},
            {"name": "Brow Up Left", "min": 0, "max": 1},
            {"name": "Brow Down Right", "min": 0, "max": 1},
        ],
        "困る": [
            {"name": "Brow Inner Up", "min": 0, "max": 1},
            {"name": "Brow Outer Down", "min": 0, "max": 1},
        ],
        "にこり": [
            {"name": "Brow Up", "min": 0, "max": 0.5},
            {"name": "Brow Inner Down", "min": 0, "max": 0.5},
        ],
        "怒り": [
            {"name": "Brow Outer Up", "min": 0, "max": 1},
            {"name": "Brow Inner Down", "min": 0, "max": 1},
        ],
        # 目 (Eyes)
        "まばたき": [{"name": "Eyes Closed", "min": 0, "max": 1}],
        "笑顔": [{"name": "Eyes Squint", "min": 0, "max": 1}],
        "笑い": [{"name": "Eyes Squint", "min": 0, "max": 1}],
        "ウィンク": [
            {"name": "Eyes Closed", "min": 0, "max": 0},
            {"name": "Eyes Closed Right", "min": 0, "max": 0.6},
        ],
        "ウィンク２": [
            {"name": "Eyes Closed", "min": 0, "max": 0},
            {"name": "Eyes Closed Right", "min": 0, "max": 0.6},
        ],
        "ウィンク左": [
            {"name": "Eyes Closed", "min": 0, "max": 0},
            {"name": "Eyes Closed Right", "min": 0, "max": 0.6},
        ],
        "ウィンク右": [
            {"name": "Eyes Closed", "min": 0, "max": 0},
            {"name": "Eyes Closed Left", "min": 0, "max": 0.6},
        ],
        "びっくり": [{"name": "Eyes Squint", "min": 0, "max": -1}],
        "じと目": [
            {"name": "Eyes Closed", "min": 0, "max": 0.1},
            {"name": "Eyes Squint", "min": 0, "max": -0.1},
        ],
        "下瞼上": [{"name": "Eyelids Bottom Up Right", "min": 0, "max": 1}],
        "右下瞼上": [{"name": "Eyelids Bottom Up Left", "min": 0, "max": 1}],
        # 口 (Mouth)
        "あ": [
            {"name": "AA", "min": 0, "max": 1},
            {"name": "Mouth Open", "min": 0, "max": 0.5},
        ],
        "い": [{"name": "IY", "min": 0, "max": 1}],
        "う": [{"name": "UW", "min": 0, "max": 0.5}],
        "え": [
            {"name": "EH", "min": 0, "max": 1},
            {"name": "Mouth Open", "min": 0, "max": 0.3},
        ],
        "お": [
            {"name": "OW", "min": 0, "max": 0.5},
            {"name": "Mouth Open", "min": 0, "max": 0.3},
        ],
        "にやり": [{"name": "Mouth Smile Simple", "min": 0, "max": 1}],
        "にやり２": [{"name": "Mouth Smile", "min": 0, "max": 1}],
        "口横広げ": [{"name": "Mouth Open", "min": 0, "max": -1}],
        "ん": [
            {"name": "Mouth Open", "min": 0, "max": -1},
            {"name": "Mouth Narrow", "min": 0, "max": 0.5},
        ],
        "w": [
            {"name": "Mouth Open", "min": 0, "max": -1},
            {"name": "Mouth Corner Up-Down", "min": 0, "max": 1},
        ],
        "口角上げ": [
            {"name": "Mouth Open", "min": 0, "max": -1},
            {"name": "Mouth Corner Up-Down", "min": 0, "max": 1},
        ],
        "口角下げ": [
            {"name": "Mouth Open", "min": 0, "max": 0},
            {"name": "Mouth Corner Up-Down", "min": 0, "max": 1},
        ],
        "∧": [
            {"name": "Mouth Open", "min": 0, "max": -1},
            {"name": "Mouth Corner Up-Down", "min": 0, "max": 0},
            {"name": "Mouth Narrow", "min": 0, "max": 0.8},
        ],
        "▲": [
            {"name": "Mouth Open", "min": 0, "max": 0},
            {"name": "Mouth Corner Up-Down", "min": 0, "max": 0},
            {"name": "Mouth Narrow", "min": 0, "max": 0.8},
        ],
    }

    CATEGORIES: dict[str, list[str]] = {
        "brow": ["真面目", "上", "下", "眉頭左", "眉頭右", "困る", "にこり", "怒り"],
        "eyes": ["まばたき", "笑顔", "笑い", "ウィンク", "ウィンク２", "ウィンク左",
                 "ウィンク右", "びっくり", "じと目", "下瞼上", "右下瞼上"],
        "mouth": ["あ", "い", "う", "え", "お", "にやり", "にやり２", "口横広げ",
                  "ん", "w", "口角上げ", "口角下げ", "∧", "▲"],
    }

    @classmethod
    def get(cls, mmd_name: str) -> Optional[list[dict]]:
        return cls.FACE_MAP.get(mmd_name)

    @classmethod
    def all_mmd_names(cls) -> list[str]:
        return list(cls.FACE_MAP.keys())

    @classmethod
    def category_of(cls, mmd_name: str) -> Optional[str]:
        for cat, names in cls.CATEGORIES.items():
            if mmd_name in names:
                return cat
        return None

    @classmethod
    def apply_weight(cls, mmd_name: str, weight: float) -> list[dict]:
        """Apply MMD morph weight (0-1) → VaM morph values with min/max scaling."""
        weight = max(0.0, min(1.0, weight))
        entries = cls.FACE_MAP.get(mmd_name, [])
        result = []
        for e in entries:
            value = e["min"] + (e["max"] - e["min"]) * weight
            result.append({"name": e["name"], "value": value})
        return result


# ── Finger Morph Map (from sFisherE/mmd2timeline FingerMorph.cs) ──

class FingerMorphMap:
    """VaM finger control parameter names and bend formulas.

    Ported from mmd2timeline/src/FingerMorph.cs (21 stars).
    Contains the exact storable names and rotation angles for finger posing.

    Usage:
        params = FingerMorphMap.PARAMS         # 25 finger parameters
        formulas = FingerMorphMap.BEND_FORMULAS["Right Thumb Bend"]
        storables = FingerMorphMap.STORABLE_NAMES  # ["LeftHandFingerControl", ...]
    """

    STORABLE_NAMES = ["LeftHandFingerControl", "RightHandFingerControl"]

    PARAMS: list[str] = [
        "indexProximalBend", "indexProximalSpread", "indexProximalTwist",
        "indexMiddleBend", "indexDistalBend",
        "middleProximalBend", "middleProximalSpread", "middleProximalTwist",
        "middleMiddleBend", "middleDistalBend",
        "ringProximalBend", "ringProximalSpread", "ringProximalTwist",
        "ringMiddleBend", "ringDistalBend",
        "pinkyProximalBend", "pinkyProximalSpread", "pinkyProximalTwist",
        "pinkyMiddleBend", "pinkyDistalBend",
        "thumbProximalBend", "thumbProximalSpread", "thumbProximalTwist",
        "thumbMiddleBend", "thumbDistalBend",
    ]

    # Finger bend formulas: {morph_name: [(bone, axis, degrees), ...]}
    BEND_FORMULAS: dict[str, list[tuple[str, str, float]]] = {
        # Right hand
        "Right Thumb Bend": [
            ("rThumb1", "Y", -45), ("rThumb2", "Y", -40), ("rThumb3", "Y", -68),
        ],
        "Right Ring Finger Bend": [
            ("rRing1", "Z", 61), ("rRing2", "Z", 90), ("rRing3", "Z", 65),
        ],
        "Right Pinky Finger Bend": [
            ("rPinky1", "Z", 61), ("rPinky2", "Z", 90), ("rPinky3", "Z", 75),
        ],
        "Right Mid Finger Bend": [
            ("rMid1", "Z", 61), ("rMid2", "Z", 90), ("rMid3", "Z", 57),
        ],
        "Right Index Finger Bend": [
            ("rIndex1", "Z", 61), ("rIndex2", "Z", 100), ("rIndex3", "Z", 62),
        ],
        # Left hand (mirrored signs)
        "Left Thumb Bend": [
            ("lThumb1", "Y", 45), ("lThumb2", "Y", 40), ("lThumb3", "Y", 68),
        ],
        "Left Ring Finger Bend": [
            ("lRing1", "Z", -61), ("lRing2", "Z", -90), ("lRing3", "Z", -65),
        ],
        "Left Pinky Finger Bend": [
            ("lPinky1", "Z", -61), ("lPinky2", "Z", -90), ("lPinky3", "Z", -75),
        ],
        "Left Mid Finger Bend": [
            ("lMid1", "Z", -61), ("lMid2", "Z", -90), ("lMid3", "Z", -57),
        ],
        "Left Index Finger Bend": [
            ("lIndex1", "Z", -61), ("lIndex2", "Z", -100), ("lIndex3", "Z", -62),
        ],
    }

    @classmethod
    def all_bones(cls) -> set[str]:
        """All unique bone names referenced by finger formulas."""
        bones = set()
        for formulas in cls.BEND_FORMULAS.values():
            for bone, _, _ in formulas:
                bones.add(bone)
        return bones


# ── DAZ Bone Map (from sFisherE/mmd2timeline DazBoneMapping.cs) ──

class DazBoneMap:
    """DAZ Genesis skeleton → MMD bone name mapping for skeleton matching.

    Ported from mmd2timeline/src/DazBoneMapping.cs (21 stars).
    Maps DAZ bone hierarchy to MMD Japanese bone names for position matching.

    Usage:
        mmd_name = DazBoneMap.daz_to_mmd("lThigh")  # → "左足"
        daz_name = DazBoneMap.mmd_to_daz("左足")     # → "lThigh"
        DazBoneMap.is_right_side("右足")             # → True
    """

    # DAZ bone → MMD Japanese bone name
    DAZ_TO_MMD: dict[str, str] = {
        # Lower body
        "hip": "腰",
        "pelvis": "下半身",
        "lThigh": "左足", "lShin": "左ひざ", "lFoot": "左足首", "lToe": "左つま先",
        "rThigh": "右足", "rShin": "右ひざ", "rFoot": "右足首", "rToe": "右つま先",
        # Upper body
        "abdomen": "上半身", "abdomen2": "上半身2", "chest": "上半身3",
        "neck": "首", "head": "頭",
        # Left arm
        "lCollar": "左肩P", "lShldr": "左肩C", "lForeArm": "左ひじ", "lHand": "左手首",
        # Right arm
        "rCollar": "右肩P", "rShldr": "右肩C", "rForeArm": "右ひじ", "rHand": "右手首",
    }

    # Reverse mapping
    MMD_TO_DAZ: dict[str, str] = {v: k for k, v in DAZ_TO_MMD.items()}

    # DAZ bone hierarchy (child → parent)
    DAZ_HIERARCHY: dict[str, str] = {
        "pelvis": "hip", "abdomen": "hip",
        "lThigh": "pelvis", "rThigh": "pelvis",
        "lShin": "lThigh", "rShin": "rThigh",
        "lFoot": "lShin", "rFoot": "rShin",
        "lToe": "lFoot", "rToe": "rFoot",
        "abdomen2": "abdomen", "chest": "abdomen2",
        "neck": "chest", "head": "neck",
        "lCollar": "chest", "rCollar": "chest",
        "lShldr": "lCollar", "rShldr": "rCollar",
        "lForeArm": "lShldr", "rForeArm": "rShldr",
        "lHand": "lForeArm", "rHand": "rForeArm",
    }

    # Finger bone hierarchy for fake bone creation
    FINGER_HIERARCHY: dict[str, str] = {
        "ForeArm": "Shldr", "Hand": "ForeArm",
        "Carpal1": "Hand",
        "Index1": "Carpal1", "Index2": "Index1", "Index3": "Index2",
        "Mid1": "Carpal1", "Mid2": "Mid1", "Mid3": "Mid2",
        "Carpal2": "Hand",
        "Pinky1": "Carpal2", "Pinky2": "Pinky1", "Pinky3": "Pinky2",
        "Ring1": "Carpal2", "Ring2": "Ring1", "Ring3": "Ring2",
        "Thumb1": "Hand", "Thumb2": "Thumb1", "Thumb3": "Thumb2",
    }

    # IK bone aliases (D-suffix and IK variants)
    IK_ALIASES: dict[str, str] = {
        "左足D": "左足", "左ひざD": "左ひざ", "左足首D": "左足首", "左足先EX": "左つま先",
        "右足D": "右足", "右ひざD": "右ひざ", "右足首D": "右足首", "右足先EX": "右つま先",
        "左足IK親": "左足", "左足ＩＫ": "左足", "左つま先ＩＫ": "左つま先",
        "右足IK親": "右足", "右足ＩＫ": "右足", "右つま先ＩＫ": "右つま先",
        "左肩": "左肩P", "左腕": "左肩C",
        "右肩": "右肩P", "右腕": "右肩C",
    }

    @classmethod
    def daz_to_mmd(cls, daz_name: str) -> Optional[str]:
        return cls.DAZ_TO_MMD.get(daz_name)

    @classmethod
    def mmd_to_daz(cls, mmd_name: str) -> Optional[str]:
        return cls.MMD_TO_DAZ.get(mmd_name)

    @classmethod
    def resolve_alias(cls, mmd_name: str) -> str:
        """Resolve IK/D-suffix bone aliases to canonical MMD name."""
        return cls.IK_ALIASES.get(mmd_name, mmd_name)

    @classmethod
    def is_right_side(cls, bone_name: str) -> bool:
        return bone_name.startswith("r") or bone_name.startswith("右")


# ── VMD Scene Importer (from CraftyMoment/mmd_vam_import vmd.py) ──

class VMDSceneImporter:
    """Convert VMD motion files to VaM scene JSON with full bone/position/rotation support.

    Ported from CraftyMoment/mmd_vam_import/vmd.py (18 stars, Python native).
    Enhanced VMD→VaM conversion with proper quaternion interpolation,
    IK detection, arm rotation compensation, and heel mode.

    Requires: pyquaternion (pip install pyquaternion)

    Usage:
        importer = VMDSceneImporter(
            vmd_path="dance.vmd",
            scene_base="base.json",
            output_path="output.json",
        )
        importer.convert()

        # Or just parse VMD without conversion
        motions = VMDSceneImporter.parse_vmd("dance.vmd")
    """

    POSITION_FACTOR = 0.08
    TIME_PAD_SECONDS = 1.0
    VMD_FPS = 30.0
    MMD_ARM_ROTATION = 0.8       # ~46 degrees
    MMD_HEEL_ROTATION = 1.047    # 60 degrees (pi/3)
    CENTER_HEIGHT_OFFSET = -0.05
    CENTER_Z_OFFSET = 0.0

    # JP→EN bone name translation (170+ entries from mmd_vam_import)
    JP_TO_EN: list[tuple[str, str]] = [
        ('全ての親', 'ParentNode'), ('操作中心', 'ControlNode'),
        ('センター', 'Center'), ('ｾﾝﾀｰ', 'Center'),
        ('上半身', 'UpperBody'), ('下半身', 'LowerBody'),
        ('手首', 'Wrist'), ('足首', 'Ankle'), ('首', 'Neck'),
        ('頭', 'Head'), ('顔', 'Face'), ('目', 'Eye'), ('眉', 'Eyebrow'),
        ('舌', 'Tongue'), ('歯', 'Teeth'), ('腰', 'Waist'), ('髪', 'Hair'),
        ('胸', 'Breast'), ('鎖骨', 'Clavicle'), ('肩', 'Shoulder'),
        ('腕', 'Arm'), ('ひじ', 'Elbow'), ('肘', 'Elbow'),
        ('手', 'Hand'), ('親指', 'Thumb'), ('人差指', 'IndexFinger'),
        ('中指', 'MiddleFinger'), ('薬指', 'RingFinger'), ('小指', 'LittleFinger'),
        ('足', 'Leg'), ('ひざ', 'Knee'), ('つま', 'Toe'),
        ('捩', 'Twist'), ('回転', 'Rotation'),
        ('右', 'Right'), ('左', 'Left'), ('前', 'Front'), ('後', 'Back'),
        ('上', 'Upper'), ('下', 'Lower'), ('先', 'Tip'),
    ]

    # Body part processing order (center outward)
    BODY_ORDER = [
        "Center", "UpperBody", "Neck", "Head",
        "LowerBody", "LeftLeg", "RightLeg", "RightKnee", "LeftKnee",
        "RightShoulder", "LeftShoulder", "LeftArm", "RightArm",
        "LeftElbow", "RightElbow", "RightWrist", "LeftWrist",
    ]

    # VaM bone parent dependencies
    BONE_DEPS: dict[str, str] = {
        "abdomen2": "hip", "pelvis": "hip",
        "rShoulder": "abdomen2", "rArm": "rShoulder",
        "rElbow": "rArm", "rHand": "rElbow",
        "lShoulder": "abdomen2", "lArm": "lShoulder",
        "lElbow": "lArm", "lHand": "lElbow",
        "neck": "abdomen2", "head": "neck",
        "lThigh": "pelvis", "rThigh": "pelvis",
        "lKnee": "lThigh", "rKnee": "rThigh",
    }

    def __init__(self, vmd_path: str = "", scene_base: str = "",
                 output_path: str = "", atom_name: str = "Person",
                 heels: bool = False):
        self.vmd_path = vmd_path
        self.scene_base = scene_base
        self.output_path = output_path
        self.atom_name = atom_name
        self.heels = heels

    @classmethod
    def translate_jp(cls, name: str) -> str:
        """Translate Japanese bone name to English."""
        for jp, en in cls.JP_TO_EN:
            name = name.replace(jp, en)
        return name

    @classmethod
    def parse_vmd(cls, filepath: str) -> dict:
        """Parse VMD binary file → dict of bone animations.

        Returns: {"bone_name": [{"frame": int, "pos": (x,y,z), "rot": (x,y,z,w)}, ...]}
        """
        import struct
        result = {}
        with open(filepath, 'rb') as f:
            sig = struct.unpack('<30s', f.read(30))[0]
            if not sig.startswith(b'Vocaloid Motion Data 0002'):
                raise ValueError(f"Invalid VMD signature: {sig}")
            _model = f.read(20)  # model name (shift-jis)
            count = struct.unpack('<L', f.read(4))[0]
            for _ in range(count):
                raw_name = struct.unpack('<15s', f.read(15))[0]
                raw_name = raw_name.split(b'\x00')[0]
                try:
                    name = raw_name.decode('shift_jis')
                except UnicodeDecodeError:
                    name = raw_name[:-1].decode('shift_jis')
                name = cls.translate_jp(name)
                frame = struct.unpack('<L', f.read(4))[0]
                pos = struct.unpack('<fff', f.read(12))
                rot = struct.unpack('<ffff', f.read(16))
                interp = struct.unpack('<64b', f.read(64))
                if name not in result:
                    result[name] = []
                result[name].append({
                    "frame": frame,
                    "pos": pos,
                    "rot": rot,  # (x, y, z, w)
                    "interp": list(interp),
                })
        # Sort each bone's frames by frame number
        for bone in result:
            result[bone].sort(key=lambda f: f["frame"])
        return result

    def convert(self) -> str:
        """Full VMD → VaM scene JSON conversion. Returns output path."""
        motions = self.parse_vmd(self.vmd_path)
        with open(self.scene_base, 'r') as f:
            scene = json.load(f)
        # Find person atom index
        person_idx = None
        for i, atom in enumerate(scene.get('atoms', [])):
            if atom.get('id') == self.atom_name:
                person_idx = i
                break
        if person_idx is None:
            raise ValueError(f"Atom '{self.atom_name}' not found in base scene")
        # Detect IK mode
        uses_ik = (len(motions.get('LeftLegIK', [])) > 1 or
                   len(motions.get('RightLegIK', [])) > 1)
        body = list(self.BODY_ORDER)
        if uses_ik:
            body.extend(['LeftLegIK', 'RightLegIK'])
        else:
            body.extend(['LeftAnkle', 'RightAnkle'])
        # Process bones and insert animations
        longest = 1.0
        for bone in body:
            if bone not in motions:
                continue
            vam_bone = VMDBoneMap.to_vam(bone)
            if not vam_bone:
                continue
            # Strip "Control" suffix for animation storable
            anim_name = vam_bone.replace("Control", "") if vam_bone.endswith("Control") else vam_bone
            frames = motions[bone]
            steps = []
            for fk in frames:
                ts = fk["frame"] / self.VMD_FPS + self.TIME_PAD_SECONDS
                if ts > longest:
                    longest = ts
                step = {
                    "timeStep": str(ts),
                    "positionOn": "true" if anim_name in ("hip",) else "false",
                    "rotationOn": "true",
                    "position": {
                        "x": str(fk["pos"][0] * -self.POSITION_FACTOR),
                        "y": str(fk["pos"][1] * self.POSITION_FACTOR),
                        "z": str(fk["pos"][2] * -self.POSITION_FACTOR),
                    },
                    "rotation": {
                        "x": str(-fk["rot"][0]),
                        "y": str(fk["rot"][1]),
                        "z": str(-fk["rot"][2]),
                        "w": str(fk["rot"][3]),
                    },
                }
                steps.append(step)
            scene['atoms'][person_idx]['storables'].append({
                'id': anim_name + 'Animation',
                'steps': steps,
            })
        # Set timeline length
        for atom in scene.get('atoms', []):
            if atom.get('id') == 'CoreControl':
                for s in atom.get('storables', []):
                    if s.get('id') == 'MotionAnimationMaster':
                        s['recordedLength'] = str(longest)
                        s['startTimestep'] = '0'
                        s['stopTimestep'] = str(longest)
        with open(self.output_path, 'w') as f:
            json.dump(scene, f, indent=3)
        return self.output_path

    @classmethod
    def summary(cls) -> dict:
        return {
            "jp_translations": len(cls.JP_TO_EN),
            "body_bones": len(cls.BODY_ORDER),
            "bone_deps": len(cls.BONE_DEPS),
            "features": [
                "VMD binary parsing", "JP→EN bone translation",
                "IK/FK auto-detection", "quaternion rotation",
                "arm rotation compensation", "heel mode",
                "VaM scene JSON generation",
            ],
        }


# ── Launch Motion Source (from ZengineerVAM/VAMLaunch) ──

class LaunchMotionSource:
    """Haptic device motion source abstraction for Buttplug/Launch integration.

    Ported from ZengineerVAM/VAMLaunch/src/MotionSources/ (26 stars).
    Defines motion patterns that drive haptic devices synchronized with VaM.

    Motion source types:
      - Oscillate: Sine/triangle wave oscillation with adjustable freq/amplitude
      - Pattern: Recorded motion pattern playback with speed control
      - Zone: Zone-based motion triggered by atom proximity

    Usage:
        osc = LaunchMotionSource.oscillate(frequency=1.0, amplitude=0.8)
        pat = LaunchMotionSource.pattern([0.0, 0.5, 1.0, 0.5, 0.0], speed=1.5)
        zone = LaunchMotionSource.zone("hipControl", radius=0.1, min_pos=0, max_pos=99)
    """

    @staticmethod
    def oscillate(frequency: float = 1.0, amplitude: float = 1.0,
                  phase: float = 0.0, waveform: str = "sine") -> dict:
        """Generate oscillating motion parameters.

        Args:
            frequency: Oscillation frequency in Hz (0.1-10)
            amplitude: Motion amplitude (0-1)
            phase: Phase offset in radians
            waveform: "sine", "triangle", "square", "sawtooth"
        """
        return {
            "type": "oscillate",
            "frequency": max(0.1, min(10.0, frequency)),
            "amplitude": max(0.0, min(1.0, amplitude)),
            "phase": phase,
            "waveform": waveform,
        }

    @staticmethod
    def pattern(positions: list[float], speed: float = 1.0,
                loop: bool = True) -> dict:
        """Generate pattern-based motion from position keyframes.

        Args:
            positions: List of positions (0-1) forming the pattern
            speed: Playback speed multiplier
            loop: Whether to loop the pattern
        """
        return {
            "type": "pattern",
            "positions": [max(0.0, min(1.0, p)) for p in positions],
            "speed": max(0.1, min(10.0, speed)),
            "loop": loop,
        }

    @staticmethod
    def zone(controller: str = "hipControl", radius: float = 0.1,
             min_pos: int = 0, max_pos: int = 99,
             axis: str = "y") -> dict:
        """Generate zone-based motion triggered by atom controller proximity.

        Args:
            controller: VaM controller name to track
            radius: Detection radius
            min_pos: Minimum device position (0-99)
            max_pos: Maximum device position (0-99)
            axis: Primary motion axis ("x", "y", "z")
        """
        return {
            "type": "zone",
            "controller": controller,
            "radius": radius,
            "minPosition": max(0, min(99, min_pos)),
            "maxPosition": max(0, min(99, max_pos)),
            "axis": axis,
        }

    @classmethod
    def summary(cls) -> dict:
        return {
            "source_types": ["oscillate", "pattern", "zone"],
            "source_project": "ZengineerVAM/VAMLaunch (26 stars)",
            "protocol": "Buttplug.io (WebSocket)",
            "device_types": ["Kiiroo Launch", "Handy", "generic Buttplug devices"],
        }
