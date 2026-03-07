#!/usr/bin/env python3
"""
Go1 Agent 中枢大脑 v2.3 — AI五感统御·情感引擎·人机交互
AI Agent 直接接入控制机器狗所有高级行为，带入用户五感

架构:
  五感(Senses) → 情感(Emotion) → 决策(BehaviorEngine) → 执行(Backend)
  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │ 视听触嗅味 │→│ 情感状态机 │→│ 行为优先级 │→│ sim/real │
  └──────────┘  └──────────┘  └──────────┘  └──────────┘
       ↑              ↑              ↑              │
       └──────── 空间地图 ←── 健康监测 ←── 记忆系统 ←┘

五感系统:
  视(Vision)  — 深度感知·障碍物检测·空间映射
  听(Hearing) — 语音命令·环境声音·人机交互
  触(Touch)   — IMU姿态·足端接触·碰撞检测
  嗅(Smell)   — 环境感知·危险预判·地形分类
  味(Taste)   — 自我诊断·电量评估·性能品味

后端:
  SimBackend  — 基于go1_sim.py MuJoCo仿真 (无需真机)
  RealBackend — 基于go1_control.py MQTT真机控制

用法:
  python go1_brain.py                          # sim模式，自主站立
  python go1_brain.py --behavior patrol        # 自主巡逻
  python go1_brain.py --behavior dance         # 舞蹈序列
  python go1_brain.py --behavior play          # 互动玩耍
  python go1_brain.py --behavior greet         # 迎接问候
  python go1_brain.py --behavior guard         # 巡逻警戒
  python go1_brain.py --cmd "walk 0.3 2"       # 直接命令
  python go1_brain.py --cmd "say 你好"          # 语音交互
  python go1_brain.py --api                    # 启动HTTP API(:8085)
  python go1_brain.py --real --host 192.168.123.161  # 真机模式
  python go1_brain.py --json --status          # JSON感知快照
  python go1_brain.py --list                   # 列出所有行为

依赖: go1_sim.py, go1_control.py, numpy
"""

import os
import sys
import time
import math
import json
import argparse
import threading
import numpy as np
try:
    import mujoco
    import mujoco.viewer
except ImportError:
    mujoco = None
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ============================================================
# 感知数据结构
# ============================================================
class RobotPosture(Enum):
    STANDING = "standing"
    SITTING = "sitting"
    FALLEN_SIDE = "fallen_side"
    FALLEN_FRONT = "fallen_front"
    FALLEN_BACK = "fallen_back"
    MOVING = "moving"
    UNKNOWN = "unknown"


class EmotionalState(Enum):
    CALM = "calm"
    HAPPY = "happy"
    CURIOUS = "curious"
    ALERT = "alert"
    TIRED = "tired"
    SCARED = "scared"
    EXCITED = "excited"
    LONELY = "lonely"


EMOTION_LED = {
    EmotionalState.CALM: (0, 100, 255),
    EmotionalState.HAPPY: (0, 255, 0),
    EmotionalState.CURIOUS: (255, 255, 0),
    EmotionalState.ALERT: (255, 100, 0),
    EmotionalState.TIRED: (100, 50, 150),
    EmotionalState.SCARED: (255, 0, 0),
    EmotionalState.EXCITED: (255, 0, 255),
    EmotionalState.LONELY: (50, 50, 100),
}


@dataclass
class VisionData:
    """视觉感知 — 模拟深度传感器"""
    obstacles: List[Tuple[float, float, float]] = field(default_factory=list)
    clear_ahead: float = 5.0
    terrain_roughness: float = 0.0


@dataclass
class AudioEvent:
    """听觉事件"""
    event_type: str = ""
    content: str = ""
    confidence: float = 1.0
    timestamp: float = 0.0


@dataclass
class PerceptionState:
    """感知状态 — Agent的五感数据"""
    timestamp: float = 0.0

    # 姿态 (IMU)
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0
    roll_rate: float = 0.0
    pitch_rate: float = 0.0
    yaw_rate: float = 0.0

    # 位置
    height: float = 0.27
    pos_x: float = 0.0
    pos_y: float = 0.0
    vel_x: float = 0.0
    vel_y: float = 0.0

    # 足端
    foot_contacts: Dict[str, bool] = field(default_factory=lambda: {
        "FR": True, "FL": True, "RR": True, "RL": True
    })
    foot_forces: Dict[str, float] = field(default_factory=lambda: {
        "FR": 0.0, "FL": 0.0, "RR": 0.0, "RL": 0.0
    })

    # 稳定性指标
    posture: RobotPosture = RobotPosture.UNKNOWN
    stability: float = 1.0  # 0=不稳 1=稳定
    is_fallen: bool = False
    contact_count: int = 4

    # 关节
    joint_positions: List[float] = field(default_factory=list)  # 12 joint angles (rad)

    # 五感扩展
    vision: VisionData = field(default_factory=VisionData)
    audio_events: List[AudioEvent] = field(default_factory=list)
    terrain_type: str = "flat"
    battery_pct: float = 100.0
    temperature: float = 25.0
    emotional_state: str = "calm"

    def to_dict(self):
        d = {}
        for k, v in self.__dict__.items():
            if isinstance(v, RobotPosture):
                d[k] = v.value
            elif isinstance(v, VisionData):
                d[k] = {"obstacles": len(v.obstacles), "clear_ahead": v.clear_ahead,
                         "terrain_roughness": round(v.terrain_roughness, 3)}
            elif isinstance(v, list) and v and isinstance(v[0], AudioEvent):
                d[k] = [{"type": e.event_type, "content": e.content} for e in v[-3:]]
            elif isinstance(v, (dict, float, int, bool, str)):
                d[k] = v
            elif isinstance(v, list):
                d[k] = [round(x, 4) if isinstance(x, float) else x for x in v]
        return d


# ============================================================
# 情感引擎
# ============================================================
class EmotionEngine:
    """情感状态机 — 让机器狗有灵魂"""

    def __init__(self):
        self.state = EmotionalState.CALM
        self.intensity = 0.5
        self.energy = 1.0
        self.social_need = 0.0
        self._history: List[Tuple[float, EmotionalState]] = []

    def process_event(self, event: str, data: Any = None):
        prev = self.state
        if event == "fall":
            self.state, self.intensity = EmotionalState.SCARED, 0.9
        elif event == "recover":
            self.state, self.intensity = EmotionalState.ALERT, 0.6
        elif event == "pet" or event == "greet":
            self.state, self.intensity = EmotionalState.HAPPY, 0.8
            self.social_need = max(0, self.social_need - 0.3)
        elif event == "voice":
            self.state, self.intensity = EmotionalState.CURIOUS, 0.7
            self.social_need = max(0, self.social_need - 0.1)
        elif event == "obstacle":
            self.state, self.intensity = EmotionalState.ALERT, 0.7
        elif event == "play":
            self.state, self.intensity = EmotionalState.EXCITED, 0.8
            self.energy = max(0, self.energy - 0.05)
        elif event == "threat":
            self.state, self.intensity = EmotionalState.ALERT, 0.9
        elif event == "tired":
            self.state, self.intensity = EmotionalState.TIRED, 0.6
        elif event == "happy":
            self.state, self.intensity = EmotionalState.HAPPY, 0.8
        elif event == "alert":
            self.state, self.intensity = EmotionalState.ALERT, 0.7
        elif event == "curious":
            self.state, self.intensity = EmotionalState.CURIOUS, 0.7
        elif event == "excited":
            self.state, self.intensity = EmotionalState.EXCITED, 0.8
        elif event == "calm":
            self.state, self.intensity = EmotionalState.CALM, 0.3
        elif event == "scared":
            self.state, self.intensity = EmotionalState.SCARED, 0.8
        elif event == "lonely":
            self.state, self.intensity = EmotionalState.LONELY, 0.6
        elif event == "idle":
            if self.social_need > 0.7:
                self.state = EmotionalState.LONELY
            elif self.energy < 0.2:
                self.state = EmotionalState.TIRED
        if self.state != prev:
            self._history.append((time.time(), self.state))

    def tick(self, dt: float):
        self.intensity = max(0.1, self.intensity - 0.05 * dt)
        if self.intensity < 0.25 and self.state not in (EmotionalState.TIRED, EmotionalState.LONELY):
            self.state = EmotionalState.CALM
        self.energy = max(0, min(1.0, self.energy - 0.002 * dt))
        self.social_need = min(1.0, self.social_need + 0.003 * dt)

    def get_led(self) -> Tuple[int, int, int]:
        return EMOTION_LED.get(self.state, (100, 100, 100))

    def to_dict(self) -> Dict:
        return {
            "state": self.state.value, "intensity": round(self.intensity, 2),
            "energy": round(self.energy, 2), "social_need": round(self.social_need, 2),
            "led": self.get_led(),
            "history_len": len(self._history),
        }


# ============================================================
# 空间感知
# ============================================================
class SpatialMap:
    """2D占据栅格 — 机器狗的空间记忆"""

    def __init__(self, size: float = 10.0, resolution: float = 0.2):
        self.size = size
        self.resolution = resolution
        self.n = int(size / resolution)
        self.grid = np.zeros((self.n, self.n), dtype=np.int8)  # 0=unknown 1=free -1=obstacle
        self.robot_cell = (self.n // 2, self.n // 2)
        self._visited = set()

    def _world_to_grid(self, x: float, y: float) -> Tuple[int, int]:
        gx = int((x + self.size / 2) / self.resolution)
        gy = int((y + self.size / 2) / self.resolution)
        return max(0, min(self.n - 1, gx)), max(0, min(self.n - 1, gy))

    def update(self, robot_x: float, robot_y: float, obstacles: List[Tuple[float, float, float]] = None):
        gx, gy = self._world_to_grid(robot_x, robot_y)
        self.robot_cell = (gx, gy)
        self.grid[gx, gy] = 1
        self._visited.add((gx, gy))
        if obstacles:
            for ox, oy, _ in obstacles:
                ogx, ogy = self._world_to_grid(ox, oy)
                self.grid[ogx, ogy] = -1

    def is_clear(self, world_dx: float, world_dy: float) -> bool:
        gx = self.robot_cell[0] + int(world_dx / self.resolution)
        gy = self.robot_cell[1] + int(world_dy / self.resolution)
        if not (0 <= gx < self.n and 0 <= gy < self.n):
            return False
        return self.grid[gx, gy] >= 0

    def coverage_pct(self) -> float:
        return len(self._visited) / (self.n * self.n) * 100

    def obstacle_count(self) -> int:
        return int(np.sum(self.grid == -1))

    def summary(self) -> Dict:
        obstacle_cells = []
        for i in range(self.n):
            for j in range(self.n):
                if self.grid[i, j] == -1:
                    obstacle_cells.append([i, j])
        return {
            "size": self.size, "resolution": self.resolution,
            "grid_size": self.n,
            "robot_cell": self.robot_cell,
            "visited_cells": len(self._visited),
            "visited": [list(v) for v in list(self._visited)[-500:]],
            "coverage_pct": round(self.coverage_pct(), 2),
            "obstacles": self.obstacle_count(),
            "obstacle_cells": obstacle_cells,
        }


# ============================================================
# 健康监测
# ============================================================
class HealthMonitor:
    """自我诊断 — 电量·温度·里程·故障"""

    def __init__(self):
        self.battery = 100.0
        self.motor_temps: Dict[str, float] = {}
        self.total_distance = 0.0
        self.uptime = 0.0
        self.error_count = 0
        self._last_pos = (0.0, 0.0)

    def tick(self, ps: 'PerceptionState', dt: float):
        drain = 0.08 if ps.posture == RobotPosture.MOVING else 0.02
        self.battery = max(0, self.battery - drain * dt)
        dx = ps.pos_x - self._last_pos[0]
        dy = ps.pos_y - self._last_pos[1]
        self.total_distance += math.sqrt(dx * dx + dy * dy)
        self._last_pos = (ps.pos_x, ps.pos_y)
        self.uptime += dt

    def needs_charge(self) -> bool:
        return self.battery < 15

    def diagnosis(self) -> Dict:
        issues = []
        if self.battery < 15:
            issues.append("low_battery")
        if self.battery < 5:
            issues.append("critical_battery")
        return {
            "battery_pct": round(self.battery, 1),
            "distance_m": round(self.total_distance, 2),
            "uptime_s": round(self.uptime, 1),
            "error_count": self.error_count,
            "issues": issues,
            "healthy": len(issues) == 0,
        }


# ============================================================
# 记忆系统
# ============================================================
class DogMemory:
    """持久记忆 — 跨会话的经验积累"""

    def __init__(self, path: str = None):
        self.path = path or os.path.join(SCRIPT_DIR, ".go1_memory.json")
        self.interactions: List[Dict] = []
        self.places: Dict[str, Dict] = {}
        self.preferences = {"favorite_gait": "trot", "energy_policy": "balanced"}
        self.stats = {"total_runs": 0, "total_falls": 0, "total_interactions": 0,
                      "total_distance": 0.0}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    data = json.load(f)
                self.interactions = data.get("interactions", [])[-50:]
                self.places = data.get("places", {})
                self.preferences = {**self.preferences, **data.get("preferences", {})}
                self.stats = {**self.stats, **data.get("stats", {})}
            except Exception:
                pass

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({
                    "interactions": self.interactions[-50:],
                    "places": self.places,
                    "preferences": self.preferences,
                    "stats": self.stats,
                    "last_save": time.time(),
                }, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def record(self, cmd: str, ok: bool):
        self.interactions.append({"t": round(time.time(), 1), "cmd": cmd, "ok": ok})
        self.stats["total_interactions"] += 1

    def remember_place(self, name: str, x: float, y: float):
        self.places[name] = {"x": round(x, 2), "y": round(y, 2), "t": time.time()}

    def recall_place(self, name: str) -> Optional[Dict]:
        return self.places.get(name)

    def to_dict(self) -> Dict:
        return {"stats": self.stats, "places": self.places,
                "recent": self.interactions[-5:]}


# ============================================================
# 统一后端接口
# ============================================================
class Go1Backend(ABC):
    """统一后端 — sim和real共享接口"""

    @abstractmethod
    def get_perception(self) -> PerceptionState:
        """获取当前感知状态"""
        pass

    @abstractmethod
    def execute_gait(self, gait: str, duration: float) -> bool:
        """执行步态动作"""
        pass

    @abstractmethod
    def execute_velocity(self, vx: float, vy: float, yaw: float, duration: float) -> bool:
        """速度控制"""
        pass

    @abstractmethod
    def stand(self) -> bool:
        pass

    @abstractmethod
    def sit(self) -> bool:
        pass

    @abstractmethod
    def stop(self) -> bool:
        """急停"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        pass

    @abstractmethod
    def get_available_actions(self) -> List[str]:
        pass


class SimBackend(Go1Backend):
    """仿真后端 — 基于go1_sim.py"""

    def __init__(self, terrain="flat", quiet=True, viewer=False, damage=False):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from go1_sim import Go1Simulator, STAND_CTRL, SIT_CTRL, GAITS, GO1_PARAMS, generate_terrain_xml, MODEL_DIR, SCENE_XML, REAL_HARDWARE
        self._mods = {
            "Go1Simulator": Go1Simulator,
            "STAND_CTRL": STAND_CTRL,
            "SIT_CTRL": SIT_CTRL,
            "GAITS": GAITS,
            "GO1_PARAMS": GO1_PARAMS,
            "generate_terrain_xml": generate_terrain_xml,
            "MODEL_DIR": MODEL_DIR,
            "SCENE_XML": SCENE_XML,
            "REAL_HARDWARE": REAL_HARDWARE,
        }
        self._damage_profile = REAL_HARDWARE if damage else None

        self._terrain_path = None
        if terrain != "flat":
            xml_str = generate_terrain_xml(terrain)
            self._terrain_path = os.path.join(MODEL_DIR, f"_scene_{terrain}.xml")
            with open(self._terrain_path, "w") as f:
                f.write(xml_str)
            self.sim = Go1Simulator(self._terrain_path, quiet=quiet, damage_profile=self._damage_profile)
        else:
            self.sim = Go1Simulator(quiet=quiet, damage_profile=self._damage_profile)

        self.sim.set_ctrl(STAND_CTRL)
        self._quiet = quiet
        self._lock = threading.Lock()  # 保护MuJoCo数据并发访问 (参考unitree-mujoco)
        self._viewer = None
        if viewer:
            self._launch_viewer()
            for _ in range(200):
                self.sim.step()
                self._viewer_sync()
        else:
            for _ in range(200):
                self.sim.step()
        self._current_gait = None

    def _launch_viewer(self):
        """启动MuJoCo原生3D可视化窗口（复用go1_sim.py的viewer模式）"""
        try:
            self._viewer = mujoco.viewer.launch_passive(self.sim.model, self.sim.data)
            if not self._quiet:
                print("  ✅ MuJoCo 3D Viewer 已启动")
        except Exception as e:
            if not self._quiet:
                print(f"  ⚠️ MuJoCo Viewer 启动失败: {e}")
            self._viewer = None

    def _viewer_sync(self):
        """同步viewer显示（如果viewer存在且运行中）"""
        if self._viewer and self._viewer.is_running():
            self._viewer.sync()

    def get_perception(self) -> PerceptionState:
        with self._lock:
            state = self.sim.get_state()
        imu = state["imu"]

        ps = PerceptionState()
        ps.timestamp = state["time"]
        ps.roll_deg = math.degrees(imu["euler"][0])
        ps.pitch_deg = math.degrees(imu["euler"][1])
        ps.yaw_deg = math.degrees(imu["euler"][2])
        ps.roll_rate = imu["gyro"][0]
        ps.pitch_rate = imu["gyro"][1]
        ps.yaw_rate = imu["gyro"][2]
        ps.height = float(state["base_pos"][2])
        ps.pos_x = float(state["base_pos"][0])
        ps.pos_y = float(state["base_pos"][1])
        ps.vel_x = float(state["base_vel"][0])
        ps.vel_y = float(state["base_vel"][1])
        ps.foot_contacts = dict(state["foot_contacts"])
        ps.foot_forces = {k: round(float(np.linalg.norm(v)), 2)
                          for k, v in state["foot_forces"].items()}
        ps.contact_count = sum(1 for c in ps.foot_contacts.values() if c)
        ps.joint_positions = [round(float(x), 4) for x in state["joint_pos"]]

        # 姿态分类
        ps.posture = self._classify_posture(ps)
        ps.is_fallen = ps.posture in (
            RobotPosture.FALLEN_SIDE,
            RobotPosture.FALLEN_FRONT,
            RobotPosture.FALLEN_BACK,
        )
        ps.stability = self._compute_stability(ps)

        return ps

    def _classify_posture(self, ps: PerceptionState) -> RobotPosture:
        if ps.height < 0.08:
            if abs(ps.roll_deg) > 45:
                return RobotPosture.FALLEN_SIDE
            elif ps.pitch_deg > 30:
                return RobotPosture.FALLEN_FRONT
            elif ps.pitch_deg < -30:
                return RobotPosture.FALLEN_BACK
            return RobotPosture.SITTING
        if abs(ps.vel_x) > 0.05 or abs(ps.vel_y) > 0.05:
            return RobotPosture.MOVING
        if ps.height > 0.2:
            return RobotPosture.STANDING
        return RobotPosture.UNKNOWN

    def _compute_stability(self, ps: PerceptionState) -> float:
        angle_penalty = (abs(ps.roll_deg) + abs(ps.pitch_deg)) / 90.0
        height_penalty = max(0, (0.2 - ps.height) / 0.2) if ps.height < 0.2 else 0
        contact_bonus = ps.contact_count / 4.0
        stability = max(0.0, min(1.0,
            contact_bonus - angle_penalty * 0.5 - height_penalty * 0.5))
        return round(stability, 3)

    def execute_gait(self, gait: str, duration: float) -> bool:
        GAITS = self._mods["GAITS"]
        STAND_CTRL = self._mods["STAND_CTRL"]
        SIT_CTRL = self._mods["SIT_CTRL"]

        if gait == "stand":
            self.sim.set_ctrl(STAND_CTRL)
        elif gait == "sit":
            self.sim.set_ctrl(SIT_CTRL)
        elif gait in GAITS and GAITS[gait]:
            gait_obj = GAITS[gait]()
            sim_time = self.sim.data.time
            end_time = sim_time + duration
            while self.sim.data.time < end_time:
                with self._lock:
                    self.sim.set_ctrl(gait_obj.get_ctrl(self.sim.data.time))
                    self.sim.step(10)
                self._viewer_sync()
            return True
        else:
            return False

        # stand/sit: 运行一段时间让姿态稳定
        for _ in range(int(duration / self.sim.dt / 10)):
            with self._lock:
                self.sim.step(10)
            self._viewer_sync()
        return True

    def execute_velocity(self, vx: float, vy: float, yaw: float, duration: float) -> bool:
        # sim中用trot步态近似速度控制
        GAITS = self._mods["GAITS"]
        gait_obj = GAITS["trot"]()
        end_time = self.sim.data.time + duration
        while self.sim.data.time < end_time:
            ctrl = gait_obj.get_ctrl(self.sim.data.time)
            # 叠加方向偏移
            for i in range(4):
                ctrl[i * 3] += vy * 0.1  # hip左右
            with self._lock:
                self.sim.set_ctrl(ctrl)
                self.sim.step(10)
            self._viewer_sync()
        return True

    def execute_pose(self, lean: float = 0, twist: float = 0,
                     look: float = 0, extend: float = 0, duration: float = 1.0) -> bool:
        """姿态控制 — 来源: go1pylib pose() + free-dog-sdk euler控制
        lean:   -1~1 身体侧倾(左/右)  → hip差动
        twist:  -1~1 身体扭转(左/右)  → hip前后差动
        look:   -1~1 抬头/低头        → thigh前后差动
        extend: -1~1 蹲下/站高        → thigh+calf均匀
        """
        STAND = self._mods["STAND_CTRL"].copy()
        ctrl = STAND.copy()
        # FR=0,1,2  FL=3,4,5  RR=6,7,8  RL=9,10,11
        # lean: hip差动 (左腿+, 右腿-)
        ctrl[0] += lean * 0.3;  ctrl[3] -= lean * 0.3
        ctrl[6] += lean * 0.3;  ctrl[9] -= lean * 0.3
        # twist: 前腿hip vs 后腿hip
        ctrl[0] += twist * 0.2; ctrl[3] += twist * 0.2
        ctrl[6] -= twist * 0.2; ctrl[9] -= twist * 0.2
        # look: 前腿thigh vs 后腿thigh
        ctrl[1] += look * 0.3;  ctrl[4] += look * 0.3
        ctrl[7] -= look * 0.3;  ctrl[10] -= look * 0.3
        # extend: 所有thigh+calf
        ctrl[1] -= extend * 0.3; ctrl[4] -= extend * 0.3
        ctrl[7] -= extend * 0.3; ctrl[10] -= extend * 0.3
        ctrl[2] += extend * 0.5; ctrl[5] += extend * 0.5
        ctrl[8] += extend * 0.5; ctrl[11] += extend * 0.5

        self.sim.set_ctrl(ctrl)
        for _ in range(int(duration / self.sim.dt / 10)):
            with self._lock:
                self.sim.step(10)
            self._viewer_sync()
        return True

    def stand(self) -> bool:
        return self.execute_gait("stand", 0.5)

    def sit(self) -> bool:
        return self.execute_gait("sit", 0.5)

    def stop(self) -> bool:
        with self._lock:
            self.sim.set_ctrl(self._mods["STAND_CTRL"])
            self.sim.step(100)
        return True

    def switch_terrain(self, terrain: str) -> bool:
        """运行时切换地形"""
        generate_terrain_xml = self._mods["generate_terrain_xml"]
        MODEL_DIR = self._mods["MODEL_DIR"]
        Go1Simulator = self._mods["Go1Simulator"]
        STAND_CTRL = self._mods["STAND_CTRL"]

        old_sim = self.sim
        old_terrain = self._terrain_path

        try:
            if terrain != "flat":
                xml_str = generate_terrain_xml(terrain)
                new_path = os.path.join(MODEL_DIR, f"_scene_{terrain}.xml")
                with open(new_path, "w") as f:
                    f.write(xml_str)
                new_sim = Go1Simulator(new_path, quiet=self._quiet)
                self._terrain_path = new_path
            else:
                new_sim = Go1Simulator(quiet=self._quiet)
                self._terrain_path = None

            new_sim.set_ctrl(STAND_CTRL)
            for _ in range(200):
                new_sim.step()

            with self._lock:
                self.sim = new_sim

            if old_terrain and os.path.exists(old_terrain):
                try:
                    os.remove(old_terrain)
                except OSError:
                    pass
            return True
        except Exception as e:
            print(f"  [TERRAIN] 切换失败: {e}")
            self.sim = old_sim
            self._terrain_path = old_terrain
            return False

    def is_connected(self) -> bool:
        return True

    def get_available_actions(self) -> List[str]:
        return list(self._mods["GAITS"].keys()) + ["velocity"]

    def close(self):
        if self._viewer:
            try:
                self._viewer.close()
            except Exception:
                pass
            self._viewer = None
        if self._terrain_path and os.path.exists(self._terrain_path):
            try:
                os.remove(self._terrain_path)
            except OSError:
                pass


class RealBackend(Go1Backend):
    """真机后端 — 基于go1_control.py MQTT"""

    def __init__(self, host=None, quiet=False):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from go1_control import MQTTController, auto_detect, ACTIONS
        self._ACTIONS = ACTIONS

        if host is None:
            host, _ = auto_detect()
            if not host:
                raise ConnectionError("Go1不可达")

        self.ctrl = MQTTController(host)
        if not self.ctrl.connect():
            raise ConnectionError(f"MQTT连接失败: {host}")
        self._quiet = quiet

    def get_perception(self) -> PerceptionState:
        # 真机感知有限 — 仅MQTT状态
        ps = PerceptionState()
        ps.timestamp = time.time()
        state = self.ctrl.get_state()
        # 解析BMS电池等信息 (如有)
        ps.posture = RobotPosture.UNKNOWN
        ps.stability = 0.5  # 无IMU数据时默认
        return ps

    def execute_gait(self, gait: str, duration: float) -> bool:
        action_map = {
            "stand": "standUp",
            "sit": "standDown",
            "trot": "walk",
            "wave": "hi",
            "pushup": "dance1",
            "dance": "dance2",
        }
        mqtt_action = action_map.get(gait, gait)
        if mqtt_action in self._ACTIONS or gait in self._ACTIONS:
            return self.ctrl.action(mqtt_action if mqtt_action in self._ACTIONS else gait)
        return False

    def execute_velocity(self, vx: float, vy: float, yaw: float, duration: float) -> bool:
        return self.ctrl.walk(vx=vx, vy=vy, yaw=yaw, duration=duration)

    def stand(self) -> bool:
        return self.ctrl.action("standUp")

    def sit(self) -> bool:
        return self.ctrl.action("standDown")

    def stop(self) -> bool:
        return self.ctrl.action("damping")

    def is_connected(self) -> bool:
        return self.ctrl.connected

    def get_available_actions(self) -> List[str]:
        return list(self._ACTIONS.keys())

    def close(self):
        self.ctrl.disconnect()


# ============================================================
# 感知处理器
# ============================================================
class PerceptionProcessor:
    """感知管线 — 从原始数据到高级理解"""

    def __init__(self):
        self.history: List[PerceptionState] = []
        self.max_history = 100
        self._fall_count = 0
        self._stable_since = 0.0

    def update(self, state: PerceptionState) -> PerceptionState:
        """处理新的感知数据，添加高级分析"""
        self.history.append(state)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        # 跟踪摔倒次数
        if state.is_fallen:
            if len(self.history) >= 2 and not self.history[-2].is_fallen:
                self._fall_count += 1

        # 跟踪稳定持续时间
        if state.stability > 0.8:
            if self._stable_since == 0:
                self._stable_since = state.timestamp
        else:
            self._stable_since = 0.0

        return state

    @property
    def fall_count(self) -> int:
        return self._fall_count

    @property
    def stable_duration(self) -> float:
        if self._stable_since > 0 and self.history:
            return self.history[-1].timestamp - self._stable_since
        return 0.0

    @property
    def latest(self) -> Optional[PerceptionState]:
        return self.history[-1] if self.history else None

    def get_trend(self, attr: str, window: int = 10) -> float:
        """计算属性的变化趋势 (正=增长, 负=下降)"""
        if len(self.history) < 2:
            return 0.0
        recent = self.history[-min(window, len(self.history)):]
        vals = [getattr(s, attr, 0) for s in recent]
        if len(vals) < 2:
            return 0.0
        return vals[-1] - vals[0]

    def summary(self) -> Dict[str, Any]:
        """感知摘要"""
        s = self.latest
        if not s:
            return {"status": "no_data"}
        return {
            "posture": s.posture.value,
            "height": round(s.height, 3),
            "stability": s.stability,
            "roll": round(s.roll_deg, 1),
            "pitch": round(s.pitch_deg, 1),
            "yaw": round(s.yaw_deg, 1),
            "vel_x": round(s.vel_x, 3),
            "contacts": s.contact_count,
            "is_fallen": s.is_fallen,
            "fall_count": self._fall_count,
            "stable_duration": round(self.stable_duration, 2),
        }


# ============================================================
# 行为系统
# ============================================================
class BehaviorStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"


class Behavior(ABC):
    """行为基类"""
    name: str = "unknown"
    priority: int = 0  # 越高越优先

    @abstractmethod
    def should_activate(self, perception: PerceptionState) -> bool:
        pass

    @abstractmethod
    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        pass

    def on_enter(self, brain: 'Go1Brain'):
        pass

    def on_exit(self, brain: 'Go1Brain'):
        pass


class RecoverBehavior(Behavior):
    """跌倒恢复 — 最高优先级"""
    name = "recover"
    priority = 100

    def should_activate(self, perception: PerceptionState) -> bool:
        return perception.is_fallen

    def on_enter(self, brain: 'Go1Brain'):
        brain.log("RECOVER", "检测到跌倒，启动恢复")

    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        ps = brain.perception.latest
        if not ps or not ps.is_fallen:
            return BehaviorStatus.SUCCESS
        brain.backend.stand()
        time.sleep(0.1)
        ps2 = brain.sense()
        if not ps2.is_fallen:
            brain.log("RECOVER", f"恢复成功 h={ps2.height:.3f}")
            return BehaviorStatus.SUCCESS
        brain.log("RECOVER", f"恢复中... h={ps2.height:.3f}")
        return BehaviorStatus.RUNNING


class StandBehavior(Behavior):
    """稳定站立"""
    name = "stand"
    priority = 10

    def should_activate(self, perception: PerceptionState) -> bool:
        return True  # 默认行为

    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        brain.backend.stand()
        return BehaviorStatus.SUCCESS


class BalanceBehavior(Behavior):
    """平衡纠正 — 当倾斜过大时激活"""
    name = "balance"
    priority = 80

    def should_activate(self, perception: PerceptionState) -> bool:
        return (not perception.is_fallen and
                (abs(perception.roll_deg) > 15 or abs(perception.pitch_deg) > 15))

    def on_enter(self, brain: 'Go1Brain'):
        brain.log("BALANCE", f"倾斜过大 R={brain.perception.latest.roll_deg:.1f}° P={brain.perception.latest.pitch_deg:.1f}°")

    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        brain.backend.stand()
        time.sleep(0.05)
        ps = brain.sense()
        if abs(ps.roll_deg) < 10 and abs(ps.pitch_deg) < 10:
            brain.log("BALANCE", "平衡恢复")
            return BehaviorStatus.SUCCESS
        return BehaviorStatus.RUNNING


class PatrolBehavior(Behavior):
    """自主巡逻 — 按模式行走"""
    name = "patrol"
    priority = 20

    def __init__(self):
        self._phase = 0
        self._phase_start = 0
        self._pattern = [
            ("trot", 3.0),    # 前进3秒
            ("stand", 1.0),   # 停顿
            ("pace", 2.0),    # 踱步
            ("stand", 1.0),   # 停顿
            ("bound", 1.5),   # 跳跃
            ("stand", 1.5),   # 停顿
        ]

    def should_activate(self, perception: PerceptionState) -> bool:
        return False  # 需要手动激活

    def on_enter(self, brain: 'Go1Brain'):
        self._phase = 0
        self._phase_start = time.time()
        brain.log("PATROL", f"巡逻开始: {len(self._pattern)}阶段")

    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        if self._phase >= len(self._pattern):
            self._phase = 0  # 循环

        gait, duration = self._pattern[self._phase]
        elapsed = time.time() - self._phase_start

        if elapsed >= duration:
            self._phase += 1
            self._phase_start = time.time()
            if self._phase < len(self._pattern):
                next_gait, _ = self._pattern[self._phase]
                brain.log("PATROL", f"阶段{self._phase}: {next_gait}")
            return BehaviorStatus.RUNNING

        brain.backend.execute_gait(gait, 0.1)
        return BehaviorStatus.RUNNING


class DanceBehavior(Behavior):
    """舞蹈序列"""
    name = "dance"
    priority = 15

    def __init__(self):
        self._step = 0
        self._step_start = 0
        self._sequence = [
            ("wave", 3.0),
            ("pushup", 4.0),
            ("pace", 3.0),
            ("bound", 2.0),
            ("wave", 3.0),
            ("stand", 1.0),
        ]

    def should_activate(self, perception: PerceptionState) -> bool:
        return False

    def on_enter(self, brain: 'Go1Brain'):
        self._step = 0
        self._step_start = time.time()
        brain.log("DANCE", "舞蹈开始")

    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        if self._step >= len(self._sequence):
            brain.log("DANCE", "舞蹈完成")
            return BehaviorStatus.SUCCESS

        gait, duration = self._sequence[self._step]
        elapsed = time.time() - self._step_start

        if elapsed >= duration:
            self._step += 1
            self._step_start = time.time()
            if self._step < len(self._sequence):
                brain.log("DANCE", f"动作{self._step+1}/{len(self._sequence)}: {self._sequence[self._step][0]}")
            return BehaviorStatus.RUNNING

        brain.backend.execute_gait(gait, 0.1)
        return BehaviorStatus.RUNNING


class ExploreBehavior(Behavior):
    """随机探索"""
    name = "explore"
    priority = 15

    def __init__(self):
        self._action_end = 0
        self._current_gait = "stand"
        self._rng = np.random.RandomState(42)

    def should_activate(self, perception: PerceptionState) -> bool:
        return False

    def on_enter(self, brain: 'Go1Brain'):
        self._action_end = 0
        brain.log("EXPLORE", "开始探索")

    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        now = time.time()
        if now >= self._action_end:
            gaits = ["trot", "pace", "stand", "bound", "gallop", "crawl",
                     "sidestep", "pronk", "trot_run"]
            self._current_gait = self._rng.choice(gaits)
            duration = self._rng.uniform(1.5, 4.0)
            self._action_end = now + duration
            brain.log("EXPLORE", f"随机动作: {self._current_gait} ({duration:.1f}s)")

        brain.backend.execute_gait(self._current_gait, 0.1)
        return BehaviorStatus.RUNNING


class FollowBehavior(Behavior):
    """跟随目标"""
    name = "follow"
    priority = 30

    def __init__(self):
        self._target = (1.0, 0.0)
        self._tolerance = 0.3

    def should_activate(self, perception: PerceptionState) -> bool:
        return False

    def on_enter(self, brain: 'Go1Brain'):
        brain.log("FOLLOW", "开始跟随目标")
        brain.emotion.process_event("curious")

    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        ps = brain.perception.latest
        if not ps:
            return BehaviorStatus.RUNNING
        dx = self._target[0] - ps.pos_x
        dy = self._target[1] - ps.pos_y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < self._tolerance:
            brain.log("FOLLOW", f"已到达目标 d={dist:.2f}")
            brain.backend.stand()
            return BehaviorStatus.SUCCESS
        angle = math.atan2(dy, dx) - math.radians(ps.yaw_deg)
        angle = (angle + math.pi) % (2 * math.pi) - math.pi
        speed = min(0.5, dist) * 0.8
        vx = speed * math.cos(angle)
        vy = speed * math.sin(angle)
        yaw_rate = max(-0.6, min(0.6, angle * 1.5))
        brain.backend.execute_velocity(vx, vy, yaw_rate, 0.2)
        return BehaviorStatus.RUNNING


class GuardBehavior(Behavior):
    """巡逻警戒 — 路径点巡逻+异常检测"""
    name = "guard"
    priority = 25

    def __init__(self):
        self._phase = 0
        self._phase_start = 0
        self._pattern = [
            ("trot", 2.5), ("stand", 1.5), ("pace", 2.0),
            ("stand", 1.0), ("trot", 2.5), ("stand", 1.5),
        ]
        self._alert_count = 0

    def should_activate(self, perception: PerceptionState) -> bool:
        return False

    def on_enter(self, brain: 'Go1Brain'):
        self._phase = 0
        self._phase_start = time.time()
        self._alert_count = 0
        brain.log("GUARD", f"警戒巡逻启动: {len(self._pattern)}阶段")
        brain.emotion.process_event("alert")

    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        ps = brain.perception.latest
        if ps and (abs(ps.roll_deg) > 12 or abs(ps.pitch_deg) > 12):
            self._alert_count += 1
            brain.log("GUARD", f"异常! R={ps.roll_deg:.1f} P={ps.pitch_deg:.1f} (#{self._alert_count})")
            brain.emotion.process_event("threat")
            brain.backend.stand()
            return BehaviorStatus.RUNNING
        if self._phase >= len(self._pattern):
            self._phase = 0
        gait, duration = self._pattern[self._phase]
        if time.time() - self._phase_start >= duration:
            self._phase += 1
            self._phase_start = time.time()
            if self._phase < len(self._pattern):
                brain.log("GUARD", f"阶段{self._phase}: {self._pattern[self._phase][0]}")
            return BehaviorStatus.RUNNING
        brain.backend.execute_gait(gait, 0.1)
        return BehaviorStatus.RUNNING


class PlayBehavior(Behavior):
    """互动玩耍 — 展示各种有趣动作"""
    name = "play"
    priority = 15

    def __init__(self):
        self._moves = ["wave", "bound", "pushup", "dance1", "pronk",
                       "handshake", "spin", "dance2", "wave"]
        self._idx = 0
        self._move_start = 0
        self._move_dur = 2.5

    def should_activate(self, perception: PerceptionState) -> bool:
        return False

    def on_enter(self, brain: 'Go1Brain'):
        self._idx = 0
        self._move_start = time.time()
        brain.log("PLAY", "开始玩耍!")
        brain.emotion.process_event("play")

    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        if self._idx >= len(self._moves):
            brain.log("PLAY", "玩耍结束!")
            brain.emotion.process_event("pet")
            return BehaviorStatus.SUCCESS
        if time.time() - self._move_start >= self._move_dur:
            self._idx += 1
            self._move_start = time.time()
            if self._idx < len(self._moves):
                brain.log("PLAY", f"动作{self._idx+1}/{len(self._moves)}: {self._moves[self._idx]}")
            return BehaviorStatus.RUNNING
        brain.backend.execute_gait(self._moves[self._idx], 0.1)
        return BehaviorStatus.RUNNING


class GreetBehavior(Behavior):
    """迎接问候 — 接近+挥手+表达喜悦"""
    name = "greet"
    priority = 35

    def __init__(self):
        self._phase = 0
        self._phase_start = 0

    def should_activate(self, perception: PerceptionState) -> bool:
        return False

    def on_enter(self, brain: 'Go1Brain'):
        self._phase = 0
        self._phase_start = time.time()
        brain.log("GREET", "检测到人类，前往问候!")
        brain.emotion.process_event("greet")

    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        elapsed = time.time() - self._phase_start
        if self._phase == 0:
            if elapsed > 2.0:
                self._phase = 1
                self._phase_start = time.time()
                brain.log("GREET", "挥手打招呼!")
            else:
                brain.backend.execute_gait("trot", 0.2)
        elif self._phase == 1:
            if elapsed > 3.0:
                brain.log("GREET", "问候完成!")
                brain.emotion.process_event("happy")
                return BehaviorStatus.SUCCESS
            brain.backend.execute_gait("wave", 0.2)
        return BehaviorStatus.RUNNING


class RestBehavior(Behavior):
    """休息节能 — 电量不足时自动激活"""
    name = "rest"
    priority = 70

    def __init__(self):
        self._rest_start = 0

    def should_activate(self, perception: PerceptionState) -> bool:
        return perception.battery_pct < 10

    def on_enter(self, brain: 'Go1Brain'):
        self._rest_start = time.time()
        brain.log("REST", f"电量不足({brain.health.battery:.0f}%)，进入休息模式")
        brain.emotion.process_event("tired")

    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        brain.backend.sit()
        elapsed = time.time() - self._rest_start
        if elapsed > 10:
            brain.log("REST", "休息完成")
            return BehaviorStatus.SUCCESS
        return BehaviorStatus.RUNNING


class GaitBehavior(Behavior):
    """直接步态执行 — Agent命令触发"""
    name = "gait_cmd"
    priority = 50

    def __init__(self, gait: str, duration: float):
        self._gait = gait
        self._duration = duration
        self._start = 0

    def should_activate(self, perception: PerceptionState) -> bool:
        return False

    def on_enter(self, brain: 'Go1Brain'):
        self._start = time.time()
        brain.log("GAIT", f"执行: {self._gait} ({self._duration}s)")

    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        elapsed = time.time() - self._start
        if elapsed >= self._duration:
            brain.backend.stand()
            return BehaviorStatus.SUCCESS
        brain.backend.execute_gait(self._gait, 0.1)
        return BehaviorStatus.RUNNING


class PoseBehavior(Behavior):
    """姿态控制 — 来源: go1pylib pose() + free-dog-sdk euler控制"""
    name = "pose_cmd"
    priority = 50

    def __init__(self, lean=0, twist=0, look=0, extend=0, duration=1.5):
        self._lean = max(-1, min(1, lean))
        self._twist = max(-1, min(1, twist))
        self._look = max(-1, min(1, look))
        self._extend = max(-1, min(1, extend))
        self._duration = duration
        self._start = 0

    def should_activate(self, perception: PerceptionState) -> bool:
        return False

    def on_enter(self, brain: 'Go1Brain'):
        self._start = time.time()
        brain.log("POSE", f"lean={self._lean} twist={self._twist} look={self._look} ext={self._extend}")

    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        if time.time() - self._start >= self._duration:
            brain.backend.stand()
            return BehaviorStatus.SUCCESS
        if hasattr(brain.backend, 'execute_pose'):
            brain.backend.execute_pose(self._lean, self._twist, self._look, self._extend, 0.1)
        return BehaviorStatus.RUNNING


class DemoBehavior(Behavior):
    """预设动作序列 — 整合free-dog-sdk/go1pylib/unitree-mujoco动作库
    demo_walk:   free-dog-sdk walk.py 序列 (euler滚转+身高+步态)
    demo_dance:  go1pylib dance.py 序列 (抬头→低头→侧倾→扭转)
    demo_pushup: free-dog-sdk pushups.py (站起→蹲下循环)
    demo_square: go1pylib square.py (正方形路径: 前进→转弯×4)
    """
    name = "demo_cmd"
    priority = 50

    SEQUENCES = {
        "walk": [
            ("pose", {"lean": -0.5}, 1.0), ("pose", {"lean": 0.5}, 1.0),
            ("pose", {"look": -0.3}, 1.0), ("pose", {"look": 0.3}, 1.0),
            ("pose", {"extend": -0.4}, 1.0), ("pose", {"extend": 0.3}, 1.0),
            ("gait", "trot", 3.0), ("stand", None, 0.5),
        ],
        "dance": [
            ("pose", {"look": -0.8}, 1.0), ("pose", {"look": 0.8}, 1.0),
            ("pose", {"lean": -0.8}, 1.0), ("pose", {"lean": 0.8}, 1.0),
            ("pose", {"twist": -0.8}, 1.0), ("pose", {"twist": 0.8}, 1.0),
            ("pose", {"look": -0.5, "lean": -0.5}, 1.0),
            ("pose", {"look": 0.5, "lean": 0.5}, 1.0),
            ("stand", None, 0.5),
        ],
        "pushup": [
            ("sit", None, 1.5), ("stand", None, 1.5),
            ("sit", None, 1.5), ("stand", None, 1.5),
            ("sit", None, 1.5), ("stand", None, 1.5),
        ],
        "square": [
            ("gait", "trot", 2.0), ("velocity", {"vy": 0, "yr": 0.8}, 1.2),
            ("gait", "trot", 2.0), ("velocity", {"vy": 0, "yr": 0.8}, 1.2),
            ("gait", "trot", 2.0), ("velocity", {"vy": 0, "yr": 0.8}, 1.2),
            ("gait", "trot", 2.0), ("velocity", {"vy": 0, "yr": 0.8}, 1.2),
            ("stand", None, 0.5),
        ],
        "acrobat": [
            ("gait", "pronk", 2.0), ("gait", "spin", 2.0),
            ("gait", "backflip", 3.0), ("gait", "handshake", 2.0),
            ("gait", "pronk", 2.0), ("stand", None, 0.5),
        ],
        "party": [
            ("gait", "dance1", 3.0), ("gait", "dance2", 3.0),
            ("gait", "spin", 2.0), ("gait", "wave", 2.0),
            ("gait", "dance1", 3.0), ("stand", None, 0.5),
        ],
        "agility": [
            ("gait", "trot", 2.0), ("gait", "gallop", 3.0),
            ("gait", "trot_run", 2.0), ("gait", "sidestep", 2.0),
            ("gait", "crawl", 2.0), ("gait", "climb", 2.0),
            ("gait", "trot", 2.0), ("stand", None, 0.5),
        ],
    }

    def __init__(self, demo_name: str = "dance"):
        self._name = demo_name
        self._steps = list(self.SEQUENCES.get(demo_name, self.SEQUENCES["dance"]))
        self._idx = 0
        self._step_start = 0

    def should_activate(self, perception: PerceptionState) -> bool:
        return False

    def on_enter(self, brain: 'Go1Brain'):
        self._idx = 0
        self._step_start = time.time()
        brain.log("DEMO", f"开始演示: {self._name} ({len(self._steps)}步)")
        brain.emotion.process_event("play")

    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        if self._idx >= len(self._steps):
            brain.log("DEMO", f"{self._name} 演示完成!")
            brain.emotion.process_event("happy")
            brain.backend.stand()
            return BehaviorStatus.SUCCESS

        action, params, duration = self._steps[self._idx]
        elapsed = time.time() - self._step_start

        if elapsed >= duration:
            self._idx += 1
            self._step_start = time.time()
            return BehaviorStatus.RUNNING

        if action == "pose" and hasattr(brain.backend, 'execute_pose'):
            brain.backend.execute_pose(**params, duration=0.1)
        elif action == "gait":
            brain.backend.execute_gait(params, 0.1)
        elif action == "velocity":
            brain.backend.execute_velocity(0.3, params.get("vy", 0), params.get("yr", 0), 0.1)
        elif action == "stand":
            brain.backend.stand()
        elif action == "sit":
            brain.backend.sit()

        return BehaviorStatus.RUNNING


class RLBehavior(Behavior):
    """RL策略执行 — 加载预训练PPO策略控制机器人

    仅在SimBackend下可用。从go1_rl.py加载策略，
    每tick将仿真状态转为48维obs，策略输出12维action。
    """
    name = "rl_policy"
    priority = 45

    def __init__(self, model_path: str = "", duration: float = 10.0):
        self._model_path = model_path
        self._duration = duration
        self._start = 0
        self._policy = None
        self._prev_action = None
        self._step_count = 0

    def should_activate(self, perception: PerceptionState) -> bool:
        return False  # 仅通过force_behavior触发

    def on_enter(self, brain: 'Go1Brain'):
        self._step_count = 0
        self._prev_action = np.zeros(12)

        if not isinstance(brain.backend, SimBackend):
            brain.log("RL", "RL策略仅支持仿真模式")
            self._start = time.time()
            return

        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from go1_rl import RLPolicy, find_pretrained_models

            if self._model_path:
                self._policy = RLPolicy(self._model_path)
                brain.log("RL", f"加载策略: {self._model_path}")
            else:
                models = find_pretrained_models()
                sb3_models = [m for m in models if m["framework"] == "stable-baselines3"]
                if sb3_models:
                    self._policy = RLPolicy(sb3_models[0]["path"])
                    brain.log("RL", f"自动加载: {sb3_models[0]['name']}")
                else:
                    brain.log("RL", "未找到可用的PPO模型")
        except Exception as e:
            brain.log("RL", f"策略加载失败: {e}")
            self._policy = None

        self._start = time.time()

    def _sim_to_obs(self, sim) -> np.ndarray:
        """将仿真状态转为48维观测向量 (与Go1Env._get_obs一致)"""
        state = sim.get_state()
        imu = state["imu"]
        contacts = np.array([1.0 if state["foot_contacts"][n] else 0.0
                            for n in ["FR", "FL", "RR", "RL"]])
        obs = np.concatenate([
            imu["euler"],                    # 3
            imu["gyro"],                     # 3
            state["joint_pos"],              # 12
            state["joint_vel"],              # 12
            self._prev_action,               # 12
            contacts,                        # 4
            [state["base_pos"][2]],          # 1
            [state["base_vel"][0]],          # 1
        ])
        return obs.astype(np.float32)

    def tick(self, brain: 'Go1Brain') -> BehaviorStatus:
        elapsed = time.time() - self._start
        if elapsed >= self._duration:
            brain.backend.stand()
            brain.log("RL", f"策略执行完成: {self._step_count}步, {elapsed:.1f}s")
            return BehaviorStatus.SUCCESS

        if self._policy is None or not isinstance(brain.backend, SimBackend):
            return BehaviorStatus.FAILURE

        sim = brain.backend.sim
        STAND_CTRL = brain.backend._mods["STAND_CTRL"]

        obs = self._sim_to_obs(sim)
        action = self._policy.predict(obs, deterministic=True)
        action = np.clip(action, -0.5, 0.5)

        ctrl = STAND_CTRL + action
        sim.set_ctrl(ctrl)
        sim.step(10)

        self._prev_action = action.copy()
        self._step_count += 1

        return BehaviorStatus.RUNNING

    def on_exit(self, brain: 'Go1Brain'):
        if self._step_count > 0:
            brain.log("RL", f"RL行为退出: {self._step_count}步")


# ============================================================
# Agent 中枢大脑
# ============================================================
class Go1Brain:
    """Go1 Agent中枢 v2.0 — 五感→情感→决策→执行 闭环"""

    def __init__(self, backend: Go1Backend, quiet: bool = False):
        self.backend = backend
        self.perception = PerceptionProcessor()
        self.quiet = quiet
        self.logs: List[Dict] = []

        # v2.0 新系统
        self.emotion = EmotionEngine()
        self.spatial = SpatialMap()
        self.health = HealthMonitor()
        self.memory = DogMemory()
        self.memory.stats["total_runs"] += 1
        self._api_server: Optional['BrainAPIServer'] = None
        self._last_tick_time = time.time()

        # 注册行为 (按优先级排序)
        self._behaviors: List[Behavior] = [
            RecoverBehavior(),
            RestBehavior(),
            BalanceBehavior(),
            GreetBehavior(),
            FollowBehavior(),
            RLBehavior(),
            GuardBehavior(),
            PatrolBehavior(),
            DanceBehavior(),
            PlayBehavior(),
            ExploreBehavior(),
            StandBehavior(),
        ]
        self._active_behavior: Optional[Behavior] = None
        self._forced_behavior: Optional[Behavior] = None
        self._running = False

    def log(self, tag: str, msg: str):
        entry = {"t": round(time.time(), 3), "tag": tag, "msg": msg}
        self.logs.append(entry)
        if not self.quiet:
            print(f"  [{tag}] {msg}")

    def sense(self) -> PerceptionState:
        """五感感知一次 — 更新所有子系统"""
        raw = self.backend.get_perception()
        now = time.time()
        dt = now - self._last_tick_time
        self._last_tick_time = now

        # 注入五感扩展数据
        raw.battery_pct = self.health.battery
        raw.emotional_state = self.emotion.state.value
        raw.terrain_type = getattr(self, '_terrain_type', 'flat')

        ps = self.perception.update(raw)

        # 更新子系统
        self.emotion.tick(dt)
        self.health.tick(ps, dt)
        self.spatial.update(ps.pos_x, ps.pos_y,
                           ps.vision.obstacles if ps.vision.obstacles else None)

        # 情感自动触发 (只在状态变化时触发，避免每tick重复)
        prev_fall_count = getattr(self, '_prev_fall_count', 0)
        if self.perception.fall_count > prev_fall_count:
            self.emotion.process_event("fall")
            self.memory.stats["total_falls"] += (self.perception.fall_count - prev_fall_count)
            self._prev_fall_count = self.perception.fall_count
        elif ps.is_fallen and self.emotion.state != EmotionalState.SCARED:
            pass  # 已在跌倒中，情感已设置
        elif ps.stability < 0.4:
            self.emotion.process_event("obstacle")
        elif self.health.needs_charge():
            self.emotion.process_event("tired")

        return ps

    def decide(self) -> Optional[Behavior]:
        """决策 — 安全行为可中断任何强制行为"""
        ps = self.perception.latest
        if not ps:
            return None

        sorted_behaviors = sorted(self._behaviors, key=lambda b: b.priority, reverse=True)

        # 安全行为 (priority>=70) 可中断强制行为
        for b in sorted_behaviors:
            if b.priority >= 70 and b.should_activate(ps):
                if self._forced_behavior and b != self._forced_behavior:
                    self.log("SAFETY", f"{b.name}(p={b.priority}) 中断 {self._forced_behavior.name}")
                    self._forced_behavior = None
                return b

        # 强制行为次之
        if self._forced_behavior:
            return self._forced_behavior

        # 常规行为选择
        for b in sorted_behaviors:
            if b.should_activate(ps):
                return b

        return None

    def execute_tick(self):
        """执行一个决策周期"""
        ps = self.sense()
        behavior = self.decide()

        if behavior != self._active_behavior:
            if self._active_behavior:
                self._active_behavior.on_exit(self)
            self._active_behavior = behavior
            if behavior:
                behavior.on_enter(self)

        if behavior:
            status = behavior.tick(self)
            if status in (BehaviorStatus.SUCCESS, BehaviorStatus.FAILURE):
                if behavior == self._forced_behavior:
                    self._forced_behavior = None
                behavior.on_exit(self)
                self._active_behavior = None

    def run(self, duration: float = 10.0, tick_hz: float = 10.0):
        """运行主循环"""
        self._running = True
        self.log("BRAIN", f"启动 duration={duration}s hz={tick_hz} emotion={self.emotion.state.value}")

        start = time.time()
        tick_dt = 1.0 / tick_hz

        while self._running and (time.time() - start) < duration:
            tick_start = time.time()
            self.execute_tick()
            # Sync MuJoCo 3D viewer if present
            if hasattr(self.backend, '_viewer_sync'):
                self.backend._viewer_sync()
            elapsed = time.time() - tick_start
            if elapsed < tick_dt:
                time.sleep(tick_dt - elapsed)

        self.backend.stop()
        wall = time.time() - start
        self.memory.stats["total_distance"] = self.health.total_distance
        self.memory.save()
        self.log("BRAIN", f"结束 运行{wall:.1f}s 电量{self.health.battery:.0f}% 里程{self.health.total_distance:.2f}m")
        self._running = False

    def stop_running(self):
        self._running = False

    def force_behavior(self, behavior: Behavior):
        """强制执行指定行为"""
        self._forced_behavior = behavior

    def command(self, cmd_str: str) -> Dict[str, Any]:
        """解析并执行Agent命令，返回结果"""
        parts = cmd_str.strip().split()
        if not parts:
            return {"ok": False, "error": "空命令"}

        verb = parts[0].lower()

        if verb == "status":
            ps = self.sense()
            return {"ok": True, "perception": ps.to_dict(),
                    "summary": self.perception.summary(),
                    "active_behavior": self._active_behavior.name if self._active_behavior else None,
                    "fall_count": self.perception.fall_count}

        elif verb == "stand":
            self.force_behavior(GaitBehavior("stand", 0.5))
            return {"ok": True, "action": "stand"}

        elif verb == "sit":
            self.force_behavior(GaitBehavior("sit", 0.5))
            return {"ok": True, "action": "sit"}

        elif verb == "stop":
            self._forced_behavior = None
            self._active_behavior = None
            return {"ok": True, "action": "stop"}

        elif verb == "gait":
            if len(parts) < 2:
                return {"ok": False, "error": "用法: gait <name> [duration]"}
            gait = parts[1]
            dur = float(parts[2]) if len(parts) > 2 else 3.0
            avail = self.backend.get_available_actions()
            if gait not in avail:
                return {"ok": False, "error": f"未知步态: {gait}", "available": avail}
            self.force_behavior(GaitBehavior(gait, dur))
            return {"ok": True, "action": "gait", "gait": gait, "duration": dur}

        elif verb == "walk":
            vx = float(parts[1]) if len(parts) > 1 else 0.3
            dur = float(parts[2]) if len(parts) > 2 else 2.0
            self.backend.execute_velocity(vx, 0.0, 0.0, dur)
            return {"ok": True, "action": "walk", "vx": vx, "duration": dur}

        elif verb == "velocity":
            vx = float(parts[1]) if len(parts) > 1 else 0.0
            vy = float(parts[2]) if len(parts) > 2 else 0.0
            yr = float(parts[3]) if len(parts) > 3 else 0.0
            dur = float(parts[4]) if len(parts) > 4 else 0.3
            self.backend.execute_velocity(vx, vy, yr, dur)
            ps = self.sense()
            return {"ok": True, "action": "velocity", "vx": vx, "vy": vy,
                    "yaw": yr, "height": round(ps.height, 4)}

        elif verb == "pose":
            # pose lean twist look extend [duration]
            lean = float(parts[1]) if len(parts) > 1 else 0
            twist = float(parts[2]) if len(parts) > 2 else 0
            look = float(parts[3]) if len(parts) > 3 else 0
            extend = float(parts[4]) if len(parts) > 4 else 0
            dur = float(parts[5]) if len(parts) > 5 else 1.5
            self.force_behavior(PoseBehavior(lean, twist, look, extend, dur))
            return {"ok": True, "action": "pose",
                    "lean": lean, "twist": twist, "look": look, "extend": extend}

        elif verb == "demo":
            demos = list(DemoBehavior.SEQUENCES.keys())
            if len(parts) < 2:
                return {"ok": False, "error": "用法: demo <walk|dance|pushup|square|acrobat|party|agility>",
                        "available": demos}
            name = parts[1].lower()
            if name not in demos:
                return {"ok": False, "error": f"未知演示: {name}", "available": demos}
            self.force_behavior(DemoBehavior(name))
            return {"ok": True, "action": "demo", "demo": name,
                    "steps": len(DemoBehavior.SEQUENCES[name])}

        elif verb == "patrol":
            for b in self._behaviors:
                if b.name == "patrol":
                    self.force_behavior(b)
                    return {"ok": True, "action": "patrol"}
            return {"ok": False, "error": "patrol行为未注册"}

        elif verb == "dance":
            for b in self._behaviors:
                if b.name == "dance":
                    self.force_behavior(b)
                    return {"ok": True, "action": "dance"}
            return {"ok": False, "error": "dance行为未注册"}

        elif verb in ("explore", "play", "greet", "guard", "follow", "rest"):
            for b in self._behaviors:
                if b.name == verb:
                    self.force_behavior(b)
                    return {"ok": True, "action": verb}
            return {"ok": False, "error": f"{verb}行为未注册"}

        elif verb == "rl":
            model_path = parts[1] if len(parts) > 1 else ""
            dur = float(parts[2]) if len(parts) > 2 else 10.0
            rl_b = RLBehavior(model_path=model_path, duration=dur)
            self.force_behavior(rl_b)
            return {"ok": True, "action": "rl_policy",
                    "model": model_path or "auto", "duration": dur}

        elif verb == "emotion":
            if len(parts) > 1:
                self.emotion.process_event(parts[1])
            return {"ok": True, "emotion": self.emotion.to_dict()}

        elif verb == "health":
            return {"ok": True, "health": self.health.diagnosis()}

        elif verb == "map":
            return {"ok": True, "spatial": self.spatial.summary()}

        elif verb == "memory":
            return {"ok": True, "memory": self.memory.to_dict()}

        elif verb == "remember":
            if len(parts) < 2:
                return {"ok": False, "error": "用法: remember <place_name>"}
            ps = self.perception.latest or self.sense()
            self.memory.remember_place(parts[1], ps.pos_x, ps.pos_y)
            return {"ok": True, "place": parts[1], "pos": (ps.pos_x, ps.pos_y)}

        elif verb == "say":
            msg = " ".join(parts[1:]) if len(parts) > 1 else "..."
            self.emotion.process_event("voice")
            self.log("VOICE", f"听到: {msg}")
            responses = {
                "你好": "汪汪! (摇尾巴)", "hello": "Woof! (tail wag)",
                "坐下": "好的! (坐下)", "站起来": "站好了!",
                "过来": "来了来了! (小跑过来)",
                "乖": "嘿嘿~ (开心地蹭蹭)",
            }
            reply = responses.get(msg, f"汪? (歪头看着你)")
            self.log("VOICE", f"回应: {reply}")
            return {"ok": True, "action": "say", "heard": msg, "reply": reply,
                    "emotion": self.emotion.state.value}

        elif verb == "hardware":
            from go1_sim import OFFICIAL_PHYSICS, GO1_HARDWARE_SPEC
            return {"ok": True, "official_physics": OFFICIAL_PHYSICS,
                    "hardware_spec": GO1_HARDWARE_SPEC}

        elif verb == "terrain":
            terrains = ["flat", "rough", "stairs", "slope", "suspended_stairs", "perlin"]
            if len(parts) < 2:
                return {"ok": False, "error": "用法: terrain <flat|rough|stairs|slope|suspended_stairs|perlin>",
                        "current": getattr(self, '_terrain_type', 'flat')}
            t = parts[1].lower()
            if t not in terrains:
                return {"ok": False, "error": f"未知地形: {t}", "available": terrains}
            if hasattr(self.backend, 'switch_terrain'):
                success = self.backend.switch_terrain(t)
                if success:
                    self._terrain_type = t
                    return {"ok": True, "action": "terrain", "terrain": t}
                return {"ok": False, "error": f"地形切换失败: {t}"}
            return {"ok": False, "error": "当前后端不支持地形切换"}

        elif verb == "speed":
            if len(parts) < 2:
                return {"ok": False, "error": "用法: speed <0.25|0.5|1|2>"}
            try:
                spd = float(parts[1])
                if spd <= 0 or spd > 10:
                    return {"ok": False, "error": "速度倍率范围: 0.25~10"}
                if hasattr(self.backend, 'sim'):
                    self.backend.sim.model.opt.timestep = 0.002 / spd
                    self.backend.sim.dt = self.backend.sim.model.opt.timestep
                return {"ok": True, "action": "speed", "multiplier": spd}
            except ValueError:
                return {"ok": False, "error": "速度参数无效"}

        elif verb == "actions":
            return {"ok": True, "actions": self.backend.get_available_actions(),
                    "behaviors": [b.name for b in self._behaviors]}

        else:
            return {"ok": False, "error": f"未知命令: {verb}",
                    "help": "status|stand|sit|stop|gait|walk|velocity|pose|demo|"
                            "patrol|dance|explore|play|greet|guard|follow|rest|rl|"
                            "terrain|speed|emotion|health|map|memory|remember|say|actions|hardware"}

    def hear(self, text: str) -> Dict[str, Any]:
        """人机交互 — 自然语言入口"""
        text = text.strip().lower()
        cmd_map = {
            "站": "stand", "坐": "sit", "停": "stop", "走": "walk",
            "跑": "gait trot 3", "跳": "gait bound 2",
            "跳舞": "dance", "巡逻": "patrol", "探索": "explore",
            "cpg": "gait cpg 5", "神经": "gait cpg 5",
            "演示": "demo dance", "表演": "demo dance", "正方形": "demo square",
            "抬头": "pose 0 0 -0.8 0", "低头": "pose 0 0 0.8 0",
            "侧倾": "pose 0.8 0 0 0", "扭转": "pose 0 0.8 0 0",
            "蹲下": "pose 0 0 0 -0.8", "站高": "pose 0 0 0 0.8",
            "玩": "play", "过来": "follow", "警戒": "guard",
            "你好": "say 你好", "乖": "say 乖",
            "休息": "rest", "状态": "status",
            "感觉": "emotion", "健康": "health",
        }
        for keyword, cmd in cmd_map.items():
            if keyword in text:
                return self.command(cmd)
        return self.command(f"say {text}")

    def start_api(self, port: int = 8085):
        """启动HTTP API服务"""
        self._api_server = BrainAPIServer(self, port)
        self._api_server.start()
        self.log("API", f"HTTP API 启动: http://0.0.0.0:{port}")

    def stop_api(self):
        if self._api_server:
            self._api_server.stop()

    def get_report(self) -> Dict[str, Any]:
        """获取完整报告 — 五感+情感+健康+空间"""
        return {
            "version": "2.3",
            "perception": self.perception.summary(),
            "emotion": self.emotion.to_dict(),
            "health": self.health.diagnosis(),
            "spatial": self.spatial.summary(),
            "memory": self.memory.to_dict(),
            "active_behavior": self._active_behavior.name if self._active_behavior else None,
            "available_actions": self.backend.get_available_actions(),
            "behaviors": [b.name for b in self._behaviors],
            "fall_count": self.perception.fall_count,
            "log_count": len(self.logs),
            "logs_recent": self.logs[-10:] if self.logs else [],
        }


# ============================================================
# HTTP API 服务
# ============================================================
class BrainAPIServer:
    """HTTP API — Agent远程控制接口"""

    def __init__(self, brain: Go1Brain, port: int = 8085):
        self.brain = brain
        self.port = port
        self.server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        brain = self.brain

        dashboard_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
        assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "refs", "mujoco-menagerie", "unitree_go1", "assets")

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = self.path.split("?")[0]

                if path == "/" or path == "/dashboard":
                    try:
                        with open(dashboard_path, "r", encoding="utf-8") as f:
                            html = f.read()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.send_header("Cache-Control", "no-cache")
                        self.end_headers()
                        self.wfile.write(html.encode("utf-8"))
                        return
                    except FileNotFoundError:
                        pass

                if path.startswith("/assets/") and path.endswith(".stl"):
                    fname = os.path.basename(path)
                    fpath = os.path.join(assets_dir, fname)
                    if os.path.isfile(fpath):
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.send_header("Cache-Control", "public, max-age=86400")
                        self.end_headers()
                        with open(fpath, "rb") as f:
                            self.wfile.write(f.read())
                        return
                    else:
                        self.send_response(404)
                        self.end_headers()
                        return

                routes = {
                    "/status": lambda: brain.command("status"),
                    "/report": lambda: brain.get_report(),
                    "/health": lambda: brain.health.diagnosis(),
                    "/emotion": lambda: brain.emotion.to_dict(),
                    "/map": lambda: brain.spatial.summary(),
                    "/memory": lambda: brain.memory.to_dict(),
                    "/hardware": lambda: brain.command("hardware"),
                }
                handler = routes.get(path)
                try:
                    if handler:
                        result = handler()
                    else:
                        result = {"error": "unknown", "endpoints": list(routes.keys()) + ["POST /cmd", "POST /say"]}
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    result = {"ok": False, "error": str(e)}
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(result, ensure_ascii=False, default=str).encode())

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode() if length else ""
                if self.path == "/cmd":
                    result = brain.command(body.strip())
                elif self.path == "/say":
                    result = brain.hear(body.strip())
                else:
                    result = {"error": "POST to /cmd or /say"}
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(result, ensure_ascii=False, default=str).encode())

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def log_message(self, fmt, *args):
                pass

        self.server = HTTPServer(("0.0.0.0", self.port), Handler)
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self.server:
            self.server.shutdown()


# ============================================================
# 主入口
# ============================================================
BEHAVIORS_HELP = {
    "stand": "稳定站立 (默认)",
    "patrol": "自主巡逻 (trot→pace→bound循环)",
    "dance": "舞蹈序列 (wave→pushup→pace→bound)",
    "explore": "随机探索 (随机选择步态)",
    "play": "互动玩耍 (展示各种有趣动作)",
    "greet": "迎接问候 (接近+挥手+喜悦)",
    "guard": "巡逻警戒 (路径点巡逻+异常检测)",
    "follow": "跟随目标 (追踪前方目标)",
    "rest": "休息节能 (电量不足时自动激活)",
    "recover": "跌倒恢复 (自动激活)",
    "balance": "平衡纠正 (自动激活)",
}


def main():
    parser = argparse.ArgumentParser(
        description="Go1 Agent 中枢大脑 v2.3 — AI五感统御·情感引擎·人机交互",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
行为:
  stand    稳定站立 (默认)     play     互动玩耍
  patrol   自主巡逻          greet    迎接问候
  dance    舞蹈序列          guard    巡逻警戒
  explore  随机探索          follow   跟随目标
                           rest     休息节能

命令 (--cmd):
  status / stand / sit / stop     基础操作
  gait trot 3 / walk 0.3 2       运动控制
  say 你好 / emotion / health     交互与诊断
  map / memory / remember home   空间与记忆
  actions                        列出所有

示例:
  python go1_brain.py                          # sim自主站立
  python go1_brain.py --behavior patrol -d 30  # sim巡逻30s
  python go1_brain.py --behavior play -d 15    # 互动玩耍15s
  python go1_brain.py --cmd "say 你好"          # 语音交互
  python go1_brain.py --api -d 300             # 启动API服务器
  python go1_brain.py --json --status          # JSON感知快照
  python go1_brain.py --real --host 192.168.123.161 --behavior dance
        """)

    parser.add_argument("--behavior", "-b", default="stand",
                       choices=list(BEHAVIORS_HELP.keys()),
                       help="初始行为 (默认: stand)")
    parser.add_argument("--duration", "-d", type=float, default=10.0,
                       help="运行时长(秒, 默认10)")
    parser.add_argument("--cmd", "-c", default=None,
                       help="直接执行Agent命令")
    parser.add_argument("--status", action="store_true",
                       help="显示感知状态快照")
    parser.add_argument("--list", action="store_true",
                       help="列出所有行为和动作")
    parser.add_argument("--api", action="store_true",
                       help="启动HTTP API服务器(:8085)")
    parser.add_argument("--api-port", type=int, default=8085,
                       help="API端口(默认8085)")
    parser.add_argument("--real", action="store_true",
                       help="真机模式 (默认sim)")
    parser.add_argument("--host", default=None,
                       help="真机IP (--real时使用)")
    parser.add_argument("--terrain", "-t", default="flat",
                       choices=["flat", "rough", "stairs", "slope", "suspended_stairs", "perlin"],
                       help="地形类型 (sim模式)")
    parser.add_argument("--json", action="store_true",
                       help="JSON输出")
    parser.add_argument("--viewer", "-v", action="store_true",
                       help="启动MuJoCo 3D可视化窗口")
    parser.add_argument("--quiet", "-q", action="store_true",
                       help="安静模式")

    args = parser.parse_args()
    quiet = args.quiet or args.json

    if not quiet:
        print(f"\n{'='*50}")
        print(f"  Go1 Agent 中枢大脑 v2.3")
        print(f"  五感统御 · 情感引擎 · 人机交互")
        print(f"  模式: {'真机' if args.real else '仿真'}")
        print(f"{'='*50}\n")

    # 创建后端
    try:
        if args.real:
            backend = RealBackend(host=args.host, quiet=quiet)
        else:
            backend = SimBackend(terrain=args.terrain, quiet=quiet, viewer=args.viewer)
    except Exception as e:
        if args.json:
            print(json.dumps({"ok": False, "error": str(e)}))
        else:
            print(f"  ❌ 后端初始化失败: {e}")
        sys.exit(1)

    brain = Go1Brain(backend, quiet=quiet)

    try:
        # --list: 列出行为
        if args.list:
            result = brain.command("actions")
            if args.json:
                result["behaviors_help"] = BEHAVIORS_HELP
                print(json.dumps(result, ensure_ascii=False))
            else:
                print("  可用行为:")
                for name, desc in BEHAVIORS_HELP.items():
                    print(f"    {name:<12} {desc}")
                print(f"\n  可用动作:")
                for a in result["actions"]:
                    print(f"    {a}")
            return

        # --status: 感知快照
        if args.status:
            result = brain.command("status")
            if args.json:
                print(json.dumps(result, ensure_ascii=False, default=str))
            else:
                print("  感知状态:")
                for k, v in result.get("summary", {}).items():
                    print(f"    {k:<18}: {v}")
            return

        # --cmd: 直接命令
        if args.cmd:
            result = brain.command(args.cmd)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, default=str))
            else:
                if result.get("ok"):
                    print(f"  ✅ {result.get('action', 'done')}")
                    for k, v in result.items():
                        if k not in ("ok", "action"):
                            print(f"    {k}: {v}")
                else:
                    print(f"  ❌ {result.get('error', 'unknown')}")

            # 如果是持续行为，运行主循环
            if result.get("ok") and result.get("action") in (
                    "patrol", "dance", "explore", "play", "greet", "guard", "follow", "rest"):
                brain.run(duration=args.duration)
            return

        # 启动API服务器
        if args.api:
            brain.start_api(args.api_port)

        # 默认: 运行指定行为
        if args.behavior != "stand":
            brain.command(args.behavior)

        brain.run(duration=args.duration)

        # 输出报告
        report = brain.get_report()
        if args.json:
            print(json.dumps(report, ensure_ascii=False, default=str))
        elif not quiet:
            print(f"\n  报告 (v2.0):")
            print(f"    姿态: {report['perception'].get('posture', '?')}")
            print(f"    高度: {report['perception'].get('height', '?')}m")
            print(f"    稳定性: {report['perception'].get('stability', '?')}")
            em = report.get('emotion', {})
            print(f"    情感: {em.get('state', '?')} (E={em.get('energy', '?')})")
            hl = report.get('health', {})
            print(f"    电量: {hl.get('battery_pct', '?')}%")
            print(f"    里程: {hl.get('distance_m', '?')}m")
            sp = report.get('spatial', {})
            print(f"    覆盖: {sp.get('coverage_pct', '?')}%")
            print(f"    跌倒: {report['fall_count']} | 日志: {report['log_count']}")

    except KeyboardInterrupt:
        if not quiet:
            print("\n  中断")
    finally:
        brain.stop_api()
        brain.memory.save()
        if hasattr(backend, 'close'):
            backend.close()


if __name__ == "__main__":
    main()
