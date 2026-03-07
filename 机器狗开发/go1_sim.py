#!/usr/bin/env python3
"""
Go1 MuJoCo 本地仿真环境 v2.2
基于 Google DeepMind mujoco_menagerie 官方Go1模型
物理参数参考 legged-mpc Go1配置

功能:
  - 3D可视化仿真（GUI模式）
  - 无头仿真（headless模式，用于测试/训练）
  - 18种预设步态：stand/sit/trot/pace/bound/wave/pushup/gallop/crawl/pronk/spin/sidestep/backflip/dance1/dance2/handshake/trot_run/climb
  - 交互式关节控制
  - IMU传感器模拟（加速度计+陀螺仪+欧拉角+四元数）
  - Gymnasium兼容RL训练接口 (Go1Env, 48维obs/12维action)
  - 地形生成器（flat/rough/stairs/slope）
  - 足端接触检测（布尔+3D力向量）
  - Agent适配：--json机器可读输出 / --quiet零冗余输出

用法:
  python go1_sim.py                    # GUI仿真，默认站立
  python go1_sim.py --action trot      # 小跑步态
  python go1_sim.py --action gallop     # 奔跑步态
  python go1_sim.py --action crawl      # 匍匐前进
  python go1_sim.py --action spin       # 原地旋转
  python go1_sim.py --action backflip   # 后空翻(弹跳)
  python go1_sim.py --action pace       # 踱步（同侧腿同步）
  python go1_sim.py --headless         # 无头模式（数据输出）
  python go1_sim.py --interactive      # 交互式控制
  python go1_sim.py --terrain rough    # 粗糙地形
  python go1_sim.py --gym              # Gymnasium RL训练演示
  python go1_sim.py --json -a trot     # JSON输出（Agent调用）
  python go1_sim.py --quiet --headless # 静默模式

依赖: pip install mujoco numpy
可选: pip install gymnasium (用于 Go1Env RL训练接口)
"""

import os
import sys
import time
import math
import json
import argparse
import numpy as np

try:
    import mujoco
    import mujoco.viewer
except ImportError:
    print("❌ 需要安装 mujoco: pip install mujoco")
    sys.exit(1)

# ============================================================
# 路径配置
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(SCRIPT_DIR, "refs", "mujoco-menagerie", "unitree_go1")
SCENE_XML = os.path.join(MODEL_DIR, "scene.xml")
GO1_XML = os.path.join(MODEL_DIR, "go1.xml")

# ============================================================
# Go1 物理参数 (来源: legged-mpc gazebo_go1_convex.yaml)
# ============================================================
GO1_PARAMS = {
    "mass": 12.74,  # kg (含电池)
    "body_height": 0.27,  # m 站立高度
    "max_height": 0.30,   # m
    "min_height": 0.03,   # m
    "foot_pos": {  # 默认足端位置 (body frame)
        "FL": [0.17, 0.13, -0.3],
        "FR": [0.17, -0.13, -0.3],
        "RL": [-0.17, 0.13, -0.3],
        "RR": [-0.17, -0.13, -0.3],
    },
    "gait_freq": 4.0,     # Hz 步态频率
    "max_vel_x": 2.5,     # m/s
    "max_vel_y": 0.4,     # m/s
    "max_yaw_rate": 0.8,  # rad/s
    "foot_sensor_range": [0.0, 300.0],  # 足端传感器范围
    "joint_torque_limit": {  # Nm
        "hip": 23.7,
        "thigh": 23.7,
        "calf": 35.55,
    },
}

# ============================================================
# Go1 官方MuJoCo物理参数 (来源: mujoco-menagerie/unitree_go1/go1.xml + GenLoco/go1.py)
# ============================================================
OFFICIAL_PHYSICS = {
    "source": "google-deepmind/mujoco_menagerie + HybridRobotics/GenLoco",
    "masses_kg": {
        "trunk": 5.204, "hip": 0.68, "thigh": 1.009, "calf": 0.196,
        "total_body": 5.204 + 4*(0.68+1.009+0.196),  # ~12.76 kg
    },
    "trunk_inertia": {"Ixx": 0.0168, "Iyy": 0.0630, "Izz": 0.0717},
    "joint_limits_rad": {
        "hip": [-0.863, 0.863],
        "thigh": [-0.686, 4.501],
        "knee": [-2.818, -0.888],
    },
    "force_limits_Nm": {"hip": 23.7, "thigh": 23.7, "knee": 35.55},
    "pd_gains": {
        "hip": {"kp": 100.0, "kd": 1.0},
        "thigh": {"kp": 100.0, "kd": 2.0},
        "knee": {"kp": 100.0, "kd": 2.0},
    },
    "link_lengths_m": {"thigh": 0.213, "calf": 0.213, "foot_radius": 0.023},
    "hip_positions": {  # 来源: go1.xml body pos
        "FR": [0.1881, -0.04675, 0], "FL": [0.1881, 0.04675, 0],
        "RR": [-0.1881, -0.04675, 0], "RL": [-0.1881, 0.04675, 0],
    },
    "hip_offset_y": 0.08,  # thigh body pos relative to hip
    "com_offset": [-0.012731, -0.002186, -0.000515],  # GenLoco
    "mpc_body_mass": 11.02,  # 108/9.8, GenLoco
    "mpc_body_height": 0.24,
    "home_pose": [0, 0.9, -1.8],  # per leg, from go1.xml keyframe
    "foot_friction": 0.8,
    "foot_condim": 6,
}

# ============================================================
# Go1 完整硬件规格 (1:1复刻参考)
# 来源: unitree官方 + free-dog-sdk + setup-guide + YushuTech
# ============================================================
GO1_HARDWARE_SPEC = {
    "model": "Unitree Go1 EDU",
    "dimensions": {"length": 0.588, "width": 0.290, "height": 0.400},  # m
    "weight": 12.0,  # kg (不含电池)
    "weight_with_battery": 12.74,
    "dof": 12,  # 4腿 × 3关节
    "motors": {
        "type": "GO-M8010-6",
        "count": 12,
        "max_torque": 23.7,  # Nm (hip/thigh), calf=35.55Nm
        "max_speed": 30.0,   # rad/s
        "gear_ratio": 6.33,
        "protocol": "RS485",
        "baudrate": 5000000,
    },
    "computers": {
        "pi": {"ip": "192.168.123.161", "role": "主控/WiFi AP", "user": "pi"},
        "nano_head": {"ip": "192.168.123.13", "role": "头部摄像头", "user": "unitree"},
        "nano_body": {"ip": "192.168.123.14", "role": "机身处理", "user": "unitree"},
        "xavier": {"ip": "192.168.123.15", "role": "推理计算", "user": "unitree"},
    },
    "sensors": {
        "imu": {"type": "BMI088", "accel_range": 24, "gyro_range": 2000},  # g, dps
        "foot_force": {"count": 4, "range": [0, 300]},  # N
        "cameras": [
            {"name": "head_front", "resolution": [1856, 800], "fps": 30, "type": "stereo_fisheye"},
            {"name": "chin_front", "resolution": [1856, 800], "fps": 30, "type": "stereo_fisheye"},
            {"name": "body_left", "resolution": [1856, 800], "fps": 30, "type": "stereo_fisheye"},
            {"name": "body_right", "resolution": [1856, 800], "fps": 30, "type": "stereo_fisheye"},
            {"name": "body_bottom", "resolution": [1856, 800], "fps": 30, "type": "stereo_fisheye"},
        ],
        "ultrasonic": {"count": 4, "range": [0.1, 4.0]},  # m
        "battery": {"voltage": 28.8, "capacity": 8000, "type": "Li-ion"},  # V, mAh
    },
    "communication": {
        "wifi": {"ssid_pattern": "Unitree_Go1XXXXX", "password": "00000000"},
        "ethernet": {"ip": "192.168.12.1", "mesh_ip": "192.168.123.161"},
        "mqtt": {"port": 1883, "ws_port": 80},
        "udp": {"high_port": 8082, "low_port": 8007, "listen_port": 8090},
    },
    # 来源: free-dog-sdk/ucl/enums.py
    "motor_modes_high": [
        "IDLE", "FORCE_STAND", "VEL_WALK", "POS_WALK", "PATH",
        "STAND_DOWN", "STAND_UP", "DAMPING", "RECOVERY",
        "BACKFLIP", "JUMPYAW", "STRAIGHTHAND", "DANCE1", "DANCE2",
    ],
    "gait_types": ["IDLE", "TROT", "TROT_RUNNING", "CLIMB_STAIR", "TROT_OBSTACLE"],
}

# ============================================================
# 关节映射 (与go1.xml actuator顺序一致)
# ============================================================
# 12个actuator: FR(hip,thigh,calf), FL(...), RR(...), RL(...)
JOINT_NAMES = [
    "FR_hip", "FR_thigh", "FR_calf",
    "FL_hip", "FL_thigh", "FL_calf",
    "RR_hip", "RR_thigh", "RR_calf",
    "RL_hip", "RL_thigh", "RL_calf",
]

# 站立姿态 (从go1.xml keyframe "home")
STAND_CTRL = np.array([0, 0.9, -1.8] * 4)

# 趴下姿态
SIT_CTRL = np.array([0, 1.5, -2.7] * 4)

# 低站姿态
LOW_STAND_CTRL = np.array([0, 1.2, -2.4] * 4)

# ============================================================
# 实机硬件档案 (2026-03-06 MCU LowState采集)
# ============================================================
REAL_HARDWARE = {
    "timestamp": "2026-03-06",
    "dead_motors": [3, 4, 11],  # FL_hip, FL_thigh, RL_calf (索引)
    "dead_motor_names": ["FL_hip", "FL_thigh", "RL_calf"],
    "real_joint_angles_rad": [
        1.21092,   # FR_hip   (+69.4°)
        -2.8035,   # FR_thigh (-160.6°)
        -0.17609,  # FR_calf  (-10.1°)
        0.0,       # FL_hip   (DEAD)
        0.0,       # FL_thigh (DEAD)
        -0.72157,  # FL_calf  (-41.3°, residual)
        1.46616,   # RR_hip   (+84.0°)
        -2.80943,  # RR_thigh (-161.0°)
        0.75137,   # RR_calf  (+43.1°)
        0.64739,   # RL_hip   (+37.1°)
        -2.81807,  # RL_thigh (-161.5°)
        0.0,       # RL_calf  (DEAD)
    ],
    "imu": {
        "quat": [0.976031, -0.015314, -0.003026, -0.217069],
        "rpy_deg": [-1.64, -0.72, -25.07],
        "accel_ms2": [0.13, -0.29, 9.63],
        "temp_C": 76,
    },
    "bms": {"soc": 67, "voltage_nominal": 28.8},
    "nano_temps_C": {"head(.13)": 49.5, "body(.14)": 47.5, "tail(.15)": 43.0},
    "motor_temps_C": {
        "FR_hip": 46, "FR_thigh": 43, "FR_calf": 52,
        "FL_calf": 47,
        "RR_hip": 46, "RR_thigh": 42, "RR_calf": 47,
        "RL_hip": 46, "RL_thigh": 43,
    },
}


# ============================================================
# 步态生成器
# ============================================================
class TrotGait:
    """小跑步态：对角腿同步"""
    def __init__(self, frequency=2.0, amplitude=0.3, speed=0.15):
        self.freq = frequency
        self.amp = amplitude
        self.speed = speed

    def get_ctrl(self, t):
        ctrl = STAND_CTRL.copy()
        phase = 2 * math.pi * self.freq * t

        # 对角腿: FR+RL 和 FL+RR 交替
        for i, leg_offset in enumerate([0, 3, 6, 9]):
            # FR=0, FL=3, RR=6, RL=9
            # 对角相位: FR&RL同相, FL&RR同相
            if i in (0, 3):  # FR, RL
                p = phase
            else:  # FL, RR
                p = phase + math.pi

            # hip: 前后摆动
            ctrl[leg_offset + 1] = 0.9 + self.amp * math.sin(p)
            # knee: 抬腿
            lift = max(0, math.sin(p)) * self.amp * 0.8
            ctrl[leg_offset + 2] = -1.8 + lift

        return ctrl


class WaveGait:
    """挥手动作：右前腿抬起挥动"""
    def __init__(self, frequency=1.5):
        self.freq = frequency

    def get_ctrl(self, t):
        ctrl = STAND_CTRL.copy()
        phase = 2 * math.pi * self.freq * t

        # FR leg: 抬起并挥动
        ctrl[0] = 0.3 * math.sin(phase)      # hip左右摆
        ctrl[1] = 0.3                          # thigh抬起
        ctrl[2] = -1.0 + 0.3 * math.sin(phase * 2)  # calf挥动

        # 其他三条腿微调保持平衡
        ctrl[3] = -0.05   # FL hip稍内收
        ctrl[6] = 0.05    # RR hip稍外展
        ctrl[9] = -0.05   # RL hip稍内收

        return ctrl


class PushupGait:
    """俯卧撑动作"""
    def __init__(self, frequency=0.5):
        self.freq = frequency

    def get_ctrl(self, t):
        phase = 2 * math.pi * self.freq * t
        blend = (math.sin(phase) + 1) / 2  # 0~1
        return STAND_CTRL * (1 - blend) + LOW_STAND_CTRL * blend


class PaceGait:
    """踱步: 同侧两腿同步"""
    def __init__(self, frequency=2.0, amplitude=0.3):
        self.freq = frequency
        self.amp = amplitude

    def get_ctrl(self, t):
        ctrl = STAND_CTRL.copy()
        phase = 2 * math.pi * self.freq * t
        for i, leg_offset in enumerate([0, 3, 6, 9]):
            if i in (0, 2):  # FR, RR (右侧)
                p = phase
            else:  # FL, RL (左侧)
                p = phase + math.pi
            ctrl[leg_offset + 1] = 0.9 + self.amp * math.sin(p)
            lift = max(0, math.sin(p)) * self.amp * 0.6
            ctrl[leg_offset + 2] = -1.8 + lift
        return ctrl


class BoundGait:
    """跳跃: 前后腿分组同步"""
    def __init__(self, frequency=1.5, amplitude=0.4):
        self.freq = frequency
        self.amp = amplitude

    def get_ctrl(self, t):
        ctrl = STAND_CTRL.copy()
        phase = 2 * math.pi * self.freq * t
        for i, leg_offset in enumerate([0, 3, 6, 9]):
            if i in (0, 1):  # FR, FL (前腿)
                p = phase
            else:  # RR, RL (后腿)
                p = phase + math.pi
            ctrl[leg_offset + 1] = 0.9 + self.amp * math.sin(p)
            lift = max(0, math.sin(p)) * self.amp * 0.7
            ctrl[leg_offset + 2] = -1.8 + lift
        return ctrl


class GallopGait:
    """奔跑: 真实Go1 TROT_RUNNING模式的高速步态
    前腿先着地，后腿紧随，飞行相明显
    来源: free-dog-sdk GaitType.TROT_RUNNING"""
    def __init__(self, frequency=3.0, amplitude=0.4, speed=0.3):
        self.freq = frequency
        self.amp = amplitude
        self.speed = speed

    def get_ctrl(self, t):
        ctrl = STAND_CTRL.copy()
        phase = 2 * math.pi * self.freq * t
        # 奔跑: 前腿微领先后腿, 有明显飞行相
        offsets = [0, 0.15, math.pi, math.pi + 0.15]  # FR, FL, RR, RL
        for i, leg_offset in enumerate([0, 3, 6, 9]):
            p = phase + offsets[i]
            # 更大的前后摆幅
            ctrl[leg_offset + 0] += math.sin(p) * 0.05  # hip微摆
            ctrl[leg_offset + 1] = 0.8 + self.amp * math.sin(p)
            # 高抬腿 + 飞行相
            lift = max(0, math.sin(p)) * self.amp * 1.0
            ctrl[leg_offset + 2] = -1.8 + lift
        return ctrl


class CrawlGait:
    """匍匐: 低姿态缓慢前进, 一次只移动一条腿
    来源: legged-mpc crawl模式"""
    def __init__(self, frequency=0.8, amplitude=0.15):
        self.freq = frequency
        self.amp = amplitude

    def get_ctrl(self, t):
        ctrl = LOW_STAND_CTRL.copy()  # 从低姿态开始
        phase = 2 * math.pi * self.freq * t
        # 四腿依次移动: FR→RL→FL→RR (对角顺序)
        leg_phases = [0, math.pi * 0.5, math.pi, math.pi * 1.5]
        leg_offsets = [0, 9, 3, 6]  # FR, RL, FL, RR
        for i, leg_offset in enumerate(leg_offsets):
            p = phase + leg_phases[i]
            # 只在正半周期抬腿
            lift = max(0, math.sin(p)) * self.amp
            ctrl[leg_offset + 1] = 1.2 + lift * 0.3
            ctrl[leg_offset + 2] = -2.4 + lift
        return ctrl


class PronkGait:
    """四足弹跳: 四条腿同步弹跳
    来源: GenLoco pronk模式"""
    def __init__(self, frequency=1.5, amplitude=0.5):
        self.freq = frequency
        self.amp = amplitude

    def get_ctrl(self, t):
        ctrl = STAND_CTRL.copy()
        phase = 2 * math.pi * self.freq * t
        # 所有腿同相位: 同时弯曲-伸展
        for leg_offset in [0, 3, 6, 9]:
            ctrl[leg_offset + 1] = 0.9 + self.amp * math.sin(phase)
            lift = max(0, math.sin(phase)) * self.amp * 0.8
            ctrl[leg_offset + 2] = -1.8 + lift
        return ctrl


class SpinGait:
    """原地旋转: 真实Go1 JUMPYAW模式
    来源: free-dog-sdk MotorModeHigh.JUMPYAW"""
    def __init__(self, frequency=1.0, yaw_speed=0.5):
        self.freq = frequency
        self.yaw_speed = yaw_speed

    def get_ctrl(self, t):
        ctrl = STAND_CTRL.copy()
        phase = 2 * math.pi * self.freq * t
        # 左右腿差动制造旋转力矩
        # 右侧腿(FR,RR)向前, 左侧腿(FL,RL)向后
        for i, leg_offset in enumerate([0, 3, 6, 9]):
            if i in (0, 2):  # FR, RR (右侧) — 向前
                ctrl[leg_offset + 1] = 0.9 + 0.2 * math.sin(phase)
                ctrl[leg_offset + 0] = -self.yaw_speed * 0.3
            else:  # FL, RL (左侧) — 向后
                ctrl[leg_offset + 1] = 0.9 + 0.2 * math.sin(phase + math.pi)
                ctrl[leg_offset + 0] = self.yaw_speed * 0.3
            lift = max(0, math.sin(phase + (0 if i in (0, 2) else math.pi))) * 0.15
            ctrl[leg_offset + 2] = -1.8 + lift
        return ctrl


class SidestepGait:
    """横移: 侧向步态, hip关节差动
    来源: go1pylib go_left/go_right"""
    def __init__(self, frequency=1.5, amplitude=0.2, direction=1.0):
        self.freq = frequency
        self.amp = amplitude
        self.dir = direction  # +1=左移, -1=右移

    def get_ctrl(self, t):
        ctrl = STAND_CTRL.copy()
        phase = 2 * math.pi * self.freq * t
        for i, leg_offset in enumerate([0, 3, 6, 9]):
            # 对角交替抬腿
            if i in (0, 3):  # FR, RL
                p = phase
            else:  # FL, RR
                p = phase + math.pi
            # hip关节横移偏移
            ctrl[leg_offset + 0] = self.dir * self.amp * 0.5
            ctrl[leg_offset + 1] = 0.9 + self.amp * 0.3 * math.sin(p)
            lift = max(0, math.sin(p)) * self.amp * 0.5
            ctrl[leg_offset + 2] = -1.8 + lift
        return ctrl


class BackflipGait:
    """后空翻准备+弹跳: 真实Go1 BACKFLIP模式的安全近似
    仿真中做蓄力弹跳, 真机才执行完整后空翻
    来源: free-dog-sdk MotorModeHigh.BACKFLIP"""
    def __init__(self, frequency=0.4):
        self.freq = frequency

    def get_ctrl(self, t):
        phase = 2 * math.pi * self.freq * t
        cycle = t * self.freq
        if cycle % 1.0 < 0.4:
            # 蓄力: 深蹲
            blend = math.sin(phase * 1.25) * 0.5 + 0.5
            ctrl = STAND_CTRL * (1 - blend) + SIT_CTRL * blend
        elif cycle % 1.0 < 0.6:
            # 弹跳: 快速伸展
            ctrl = STAND_CTRL.copy()
            extend = min(1.0, (cycle % 1.0 - 0.4) / 0.2)
            for leg_offset in [0, 3, 6, 9]:
                ctrl[leg_offset + 1] = 0.5 - extend * 0.3  # thigh快速伸展
                ctrl[leg_offset + 2] = -1.2 + extend * 0.4  # calf快速伸展
        else:
            # 落地恢复
            ctrl = STAND_CTRL.copy()
        return ctrl


class Dance1Gait:
    """舞蹈1: 真实Go1 DANCE1模式
    左右摇摆+抬腿序列
    来源: free-dog-sdk MotorModeHigh.DANCE1"""
    def __init__(self, frequency=1.0):
        self.freq = frequency

    def get_ctrl(self, t):
        ctrl = STAND_CTRL.copy()
        phase = 2 * math.pi * self.freq * t
        # 身体左右摇摆
        sway = math.sin(phase) * 0.15
        for leg_offset in [0, 6]:  # 右侧腿
            ctrl[leg_offset] += sway
        for leg_offset in [3, 9]:  # 左侧腿
            ctrl[leg_offset] -= sway
        # 交替抬前腿
        if math.sin(phase * 2) > 0:
            ctrl[1] = 0.4;  ctrl[2] = -1.2  # FR抬起
        else:
            ctrl[4] = 0.4;  ctrl[5] = -1.2  # FL抬起
        return ctrl


class Dance2Gait:
    """舞蹈2: 真实Go1 DANCE2模式
    全身扭动+步态混合
    来源: free-dog-sdk MotorModeHigh.DANCE2"""
    def __init__(self, frequency=0.8):
        self.freq = frequency

    def get_ctrl(self, t):
        ctrl = STAND_CTRL.copy()
        phase = 2 * math.pi * self.freq * t
        # 身体扭转: 前后腿反向hip偏移
        twist = math.sin(phase) * 0.2
        ctrl[0] += twist;  ctrl[3] += twist   # 前腿同向
        ctrl[6] -= twist;  ctrl[9] -= twist   # 后腿反向
        # 身体俯仰波动
        pitch = math.sin(phase * 2) * 0.15
        ctrl[1] += pitch;  ctrl[4] += pitch   # 前腿thigh
        ctrl[7] -= pitch;  ctrl[10] -= pitch  # 后腿thigh
        # 节奏性蹲起
        squat = (math.sin(phase * 3) + 1) * 0.1
        for leg_offset in [0, 3, 6, 9]:
            ctrl[leg_offset + 2] += squat
        return ctrl


class HandshakeGait:
    """握手: 真实Go1 STRAIGHTHAND模式
    右前腿伸出, 身体后倾保持平衡
    来源: free-dog-sdk MotorModeHigh.STRAIGHTHAND"""
    def __init__(self, frequency=0.5):
        self.freq = frequency

    def get_ctrl(self, t):
        ctrl = STAND_CTRL.copy()
        phase = 2 * math.pi * self.freq * t
        progress = min(1.0, t * 2)  # 0.5秒内完成伸手
        # 右前腿伸出
        ctrl[0] = 0.0                              # FR hip居中
        ctrl[1] = 0.3 * progress                   # FR thigh抬起
        ctrl[2] = -0.8 * progress                  # FR calf伸展
        # 身体后倾补偿
        for leg_offset in [6, 9]:  # 后腿
            ctrl[leg_offset + 1] = 0.9 - 0.15 * progress
        # FL hip内收补偿
        ctrl[3] = -0.1 * progress
        # 小幅挥动
        ctrl[2] += math.sin(phase * 3) * 0.15 * progress
        return ctrl


class TrotRunGait:
    """快跑小跑: 真实Go1 TROT_RUNNING步态
    比普通trot更快, 更高抬腿
    来源: free-dog-sdk GaitType.TROT_RUNNING"""
    def __init__(self, frequency=3.0, amplitude=0.35, foot_raise=0.1):
        self.freq = frequency
        self.amp = amplitude
        self.foot_raise = foot_raise

    def get_ctrl(self, t):
        ctrl = STAND_CTRL.copy()
        phase = 2 * math.pi * self.freq * t
        for i, leg_offset in enumerate([0, 3, 6, 9]):
            if i in (0, 3):  # FR, RL (对角)
                p = phase
            else:  # FL, RR
                p = phase + math.pi
            ctrl[leg_offset + 1] = 0.85 + self.amp * math.sin(p)
            lift = max(0, math.sin(p)) * self.amp * 1.2
            ctrl[leg_offset + 2] = -1.8 + lift
        return ctrl


class ClimbGait:
    """爬坡: 真实Go1 CLIMB_STAIR模式
    高抬腿+低重心, 适应台阶/斜坡
    来源: free-dog-sdk GaitType.CLIMB_STAIR"""
    def __init__(self, frequency=1.2, amplitude=0.3):
        self.freq = frequency
        self.amp = amplitude

    def get_ctrl(self, t):
        ctrl = LOW_STAND_CTRL.copy()  # 低重心
        phase = 2 * math.pi * self.freq * t
        for i, leg_offset in enumerate([0, 3, 6, 9]):
            if i in (0, 3):  # 对角
                p = phase
            else:
                p = phase + math.pi
            # 高抬腿
            ctrl[leg_offset + 1] = 1.1 + self.amp * math.sin(p)
            lift = max(0, math.sin(p)) * self.amp * 1.5
            ctrl[leg_offset + 2] = -2.2 + lift
        return ctrl


class CPGGait:
    """中枢模式发生器(CPG)步态: 神经振荡器耦合产生自然步态
    来源: ImDipsy/cpg_go1_simulation + 神经科学CPG理论
    CPG通过相位耦合的振荡器自动生成协调的四肢运动"""
    def __init__(self, frequency=2.0, amplitude=0.3, coupling=2.0, pattern="trot"):
        self.freq = frequency
        self.amp = amplitude
        self.coupling = coupling
        # 相位偏移定义步态模式
        self.patterns = {
            "trot": [0, math.pi, math.pi, 0],           # 对角同步
            "pace": [0, math.pi, 0, math.pi],            # 同侧同步
            "bound": [0, 0, math.pi, math.pi],           # 前后分组
            "walk": [0, math.pi/2, math.pi, 3*math.pi/2], # 依次迈步
            "gallop": [0, 0.15, math.pi, math.pi+0.15],  # 前微领先
        }
        self.phase_offsets = self.patterns.get(pattern, self.patterns["trot"])
        # 内部振荡器状态
        self.phases = [off for off in self.phase_offsets]

    def get_ctrl(self, t):
        ctrl = STAND_CTRL.copy()
        # 更新振荡器相位 (简化Kuramoto模型)
        dt = 0.002  # 仿真步长
        for i in range(4):
            # 基础频率驱动
            self.phases[i] = self.phase_offsets[i] + 2 * math.pi * self.freq * t
            # 耦合校正 (邻腿相互影响)
            for j in range(4):
                if i != j:
                    diff = self.phase_offsets[j] - self.phase_offsets[i]
                    self.phases[i] += self.coupling * dt * math.sin(
                        self.phases[j] - self.phases[i] - diff)

        for i, leg_offset in enumerate([0, 3, 6, 9]):
            p = self.phases[i]
            # 平滑的CPG输出: 正弦驱动thigh + 抬腿knee
            ctrl[leg_offset + 0] += math.sin(p * 0.5) * 0.03  # hip微摆
            ctrl[leg_offset + 1] = 0.9 + self.amp * math.sin(p)
            # 非对称抬腿(快抬慢放), 更自然
            swing = math.sin(p)
            lift = max(0, swing) ** 0.7 * self.amp * 0.9
            ctrl[leg_offset + 2] = -1.8 + lift
        return ctrl


GAITS = {
    "stand": None,
    "sit": None,
    "trot": TrotGait,
    "wave": WaveGait,
    "pushup": PushupGait,
    "pace": PaceGait,
    "bound": BoundGait,
    # v2.2 新增步态 (来源: free-dog-sdk + go1pylib + GenLoco + legged-mpc)
    "gallop": GallopGait,
    "crawl": CrawlGait,
    "pronk": PronkGait,
    "spin": SpinGait,
    "sidestep": SidestepGait,
    "backflip": BackflipGait,
    "dance1": Dance1Gait,
    "dance2": Dance2Gait,
    "handshake": HandshakeGait,
    "trot_run": TrotRunGait,
    "climb": ClimbGait,
    # v2.3 CPG步态 (来源: cpg_go1_simulation + 神经振荡器理论)
    "cpg": CPGGait,
}


# ============================================================
# 地形生成器
# ============================================================
def generate_terrain_xml(terrain_type="flat", seed=42):
    """生成带地形的scene XML"""
    rng = np.random.RandomState(seed)

    terrain_geoms = ""
    if terrain_type == "rough":
        # 来源: unitree-mujoco/terrain_tool AddRoughGround
        for i in range(20):
            x = rng.uniform(-1.5, 1.5)
            y = rng.uniform(-1.5, 1.5)
            h = rng.uniform(0.005, 0.03)
            sx = rng.uniform(0.04, 0.15)
            sy = rng.uniform(0.04, 0.15)
            ex, ey, ez = rng.uniform(-0.1, 0.1, 3)
            terrain_geoms += f'    <geom type="box" pos="{x:.3f} {y:.3f} {h/2:.4f}" size="{sx:.3f} {sy:.3f} {h/2:.4f}" euler="{ex:.2f} {ey:.2f} {ez:.2f}" contype="0" conaffinity="1" rgba="0.4 0.35 0.3 1"/>\n'
    elif terrain_type == "stairs":
        # 来源: unitree-mujoco/terrain_tool AddStairs
        for i in range(10):
            x = 0.25 * i
            h = 0.02 * (i + 1)
            terrain_geoms += f'    <geom type="box" pos="{x:.2f} 0 {h/2:.3f}" size="0.12 0.6 {h/2:.3f}" contype="0" conaffinity="1" rgba="0.5 0.5 0.5 1"/>\n'
    elif terrain_type == "slope":
        terrain_geoms += '    <geom type="box" pos="1.0 0 0.1" size="1.0 0.5 0.01" euler="0 -0.15 0" contype="0" conaffinity="1" rgba="0.45 0.4 0.35 1"/>\n'
    elif terrain_type == "suspended_stairs":
        # 来源: unitree-mujoco/terrain_tool AddSuspendStairs — 悬空阶梯
        for i in range(8):
            x = 0.3 * i
            h = 0.025 * (i + 1)
            gap = 0.01  # 阶梯间隙
            terrain_geoms += f'    <geom type="box" pos="{x:.2f} 0 {h:.3f}" size="0.12 0.5 {max(0.005, 0.025-gap)/2:.4f}" contype="0" conaffinity="1" rgba="0.55 0.45 0.4 1"/>\n'
    elif terrain_type == "perlin":
        # 来源: unitree-mujoco/terrain_tool AddPerlinHeighField — Perlin噪声起伏
        grid = 12
        for ix in range(grid):
            for iy in range(grid):
                x = (ix - grid/2) * 0.25
                y = (iy - grid/2) * 0.25
                # 简化Perlin: 多频叠加
                h = 0.015 * math.sin(x*2.1 + 0.3) * math.cos(y*1.7 + 0.8)
                h += 0.008 * math.sin(x*5.3 + 1.2) * math.cos(y*4.1 + 2.1)
                h = max(0.001, abs(h))
                terrain_geoms += f'    <geom type="box" pos="{x:.2f} {y:.2f} {h/2:.4f}" size="0.12 0.12 {h/2:.4f}" contype="0" conaffinity="1" rgba="{0.3+h*5:.2f} {0.35+h*3:.2f} 0.25 1"/>\n'

    return f"""<mujoco model="go1 scene">
  <include file="go1.xml"/>
  <size nstack="2000000"/>
  <statistic center="0 0 0.1" extent="0.8"/>
  <visual>
    <headlight diffuse="0.6 0.6 0.6" ambient="0.3 0.3 0.3" specular="0 0 0"/>
    <rgba haze="0.15 0.25 0.35 1"/>
    <global azimuth="120" elevation="-20"/>
  </visual>
  <asset>
    <texture type="skybox" builtin="gradient" rgb1="0.3 0.5 0.7" rgb2="0 0 0" width="512" height="3072"/>
    <texture type="2d" name="groundplane" builtin="checker" mark="edge" rgb1="0.2 0.3 0.4" rgb2="0.1 0.2 0.3"
      markrgb="0.8 0.8 0.8" width="300" height="300"/>
    <material name="groundplane" texture="groundplane" texuniform="true" texrepeat="5 5" reflectance="0.2"/>
  </asset>
  <worldbody>
    <light pos="0 0 1.5" dir="0 0 -1" directional="true"/>
    <geom name="floor" size="0 0 0.05" type="plane" material="groundplane"/>
{terrain_geoms}  </worldbody>
</mujoco>
"""


# ============================================================
# 仿真器
# ============================================================
class Go1Simulator:
    def __init__(self, model_path=SCENE_XML, quiet=False, damage_profile=None):
        model_dir = os.path.dirname(model_path)
        model_file = os.path.basename(model_path)
        self.quiet = quiet
        self.damage_profile = damage_profile  # dict with dead_motors list

        if not os.path.exists(model_path):
            if not quiet:
                print(f"❌ 模型文件不存在: {model_path}")
                print(f"   请确认 refs/mujoco-menagerie/unitree_go1/ 目录存在")
            sys.exit(1)

        # MuJoCo C库不支持Unicode路径，需要chdir到模型目录
        original_cwd = os.getcwd()
        try:
            os.chdir(model_dir)
            self.model = mujoco.MjModel.from_xml_path(model_file)
        finally:
            os.chdir(original_cwd)

        self.data = mujoco.MjData(self.model)
        self.dt = self.model.opt.timestep

        # 初始化到站立姿态
        mujoco.mj_resetDataKeyframe(self.model, self.data, 0)
        mujoco.mj_forward(self.model, self.data)

        # Apply damage profile (disable dead motors)
        self._dead_motors = []
        if damage_profile and "dead_motors" in damage_profile:
            self._dead_motors = damage_profile["dead_motors"]
            for mi in self._dead_motors:
                if mi < self.model.nu:
                    self.model.actuator_gainprm[mi, 0] = 0
                    self.model.actuator_biasprm[mi, 1] = 0
            if not quiet:
                names = [JOINT_NAMES[i] for i in self._dead_motors if i < len(JOINT_NAMES)]
                print(f"  ⚠️ 损伤模式: 禁用电机 {names}")

        if not quiet:
            print(f"  ✅ Go1模型加载成功")
            print(f"     关节数: {self.model.njnt}")
            print(f"     执行器: {self.model.nu}")
            print(f"     仿真步长: {self.dt}s")
            print(f"     体总质量: {sum(self.model.body_mass):.2f}kg")

    def get_imu(self):
        """获取IMU数据 (加速度计 + 陀螺仪)"""
        body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
        if body_id < 0:
            body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "base")

        quat = self.data.qpos[3:7]  # w,x,y,z
        # 旋转矩阵 (body→world)
        rot = np.zeros(9)
        mujoco.mju_quat2Mat(rot, quat)
        rot = rot.reshape(3, 3)

        # 体坐标系下的加速度 (world加速度 + 重力 → 旋转到body frame)
        world_acc = self.data.qacc[:3] if len(self.data.qacc) >= 3 else np.zeros(3)
        gravity_world = np.array([0, 0, -9.81])
        acc_body = rot.T @ (world_acc - gravity_world)

        # 体坐标系下的角速度
        omega_world = self.data.qvel[3:6]
        omega_body = rot.T @ omega_world

        # 欧拉角 (roll, pitch, yaw)
        euler = np.zeros(3)
        euler[0] = math.atan2(2*(quat[0]*quat[1] + quat[2]*quat[3]),
                              1 - 2*(quat[1]**2 + quat[2]**2))
        euler[1] = math.asin(np.clip(2*(quat[0]*quat[2] - quat[3]*quat[1]), -1, 1))
        euler[2] = math.atan2(2*(quat[0]*quat[3] + quat[1]*quat[2]),
                              1 - 2*(quat[2]**2 + quat[3]**2))

        return {
            "accel": acc_body,       # 加速度 (m/s², body frame)
            "gyro": omega_body,      # 角速度 (rad/s, body frame)
            "euler": euler,          # 欧拉角 [roll, pitch, yaw] (rad)
            "quat": quat.copy(),     # 四元数 [w, x, y, z]
        }

    def get_state(self):
        """获取机器人完整状态"""
        imu = self.get_imu()
        state = {
            "time": self.data.time,
            "qpos": self.data.qpos.copy(),
            "qvel": self.data.qvel.copy(),
            "base_pos": self.data.qpos[:3].copy(),
            "base_quat": self.data.qpos[3:7].copy(),
            "base_vel": self.data.qvel[:3].copy(),
            "base_omega": self.data.qvel[3:6].copy(),
            "joint_pos": self.data.qpos[7:19].copy(),
            "joint_vel": self.data.qvel[6:18].copy(),
            "ctrl": self.data.ctrl.copy(),
            "imu": imu,
            "dead_motors": self._dead_motors,
        }

        # 足端接触力
        foot_names = ["FR", "FL", "RR", "RL"]
        state["foot_forces"] = {}
        state["foot_contacts"] = {}
        for name in foot_names:
            force = np.zeros(3)
            in_contact = False
            for i in range(self.data.ncon):
                contact = self.data.contact[i]
                geom1 = self.model.geom(contact.geom1).name
                geom2 = self.model.geom(contact.geom2).name
                if name in (geom1, geom2):
                    c_force = np.zeros(6)
                    mujoco.mj_contactForce(self.model, self.data, i, c_force)
                    force += c_force[:3]
                    in_contact = True
            state["foot_forces"][name] = force
            state["foot_contacts"][name] = in_contact

        return state

    def set_ctrl(self, ctrl):
        """设置控制信号"""
        assert len(ctrl) == self.model.nu, f"ctrl长度应为{self.model.nu}, 实际{len(ctrl)}"
        self.data.ctrl[:] = ctrl

    def step(self, n=1):
        """推进仿真n步"""
        for _ in range(n):
            mujoco.mj_step(self.model, self.data)

    def run_headless(self, action="stand", duration=5.0, json_output=False):
        """无头仿真 + 数据输出"""
        gait = None
        if action == "sit":
            self.set_ctrl(SIT_CTRL)
        elif action in GAITS and GAITS[action]:
            gait = GAITS[action]()
        else:
            self.set_ctrl(STAND_CTRL)

        if not self.quiet and not json_output:
            print(f"\n  无头仿真: {action}, 时长: {duration}s")
            print(f"  {'时间':>6} | {'基座高度':>8} | {'FR力':>8} | {'FL力':>8} | {'RR力':>8} | {'RL力':>8}")
            print(f"  {'-'*6} | {'-'*8} | {'-'*8} | {'-'*8} | {'-'*8} | {'-'*8}")

        start = time.time()
        sim_time = 0
        last_print = -1
        snapshots = []

        while sim_time < duration:
            if gait:
                self.set_ctrl(gait.get_ctrl(sim_time))

            self.step(10)  # 10步一批
            sim_time = self.data.time

            # 每0.5秒记录
            t_int = int(sim_time * 2)
            if t_int > last_print:
                last_print = t_int
                state = self.get_state()
                h = state["base_pos"][2]
                forces = state["foot_forces"]
                fr_f = np.linalg.norm(forces["FR"])
                fl_f = np.linalg.norm(forces["FL"])
                rr_f = np.linalg.norm(forces["RR"])
                rl_f = np.linalg.norm(forces["RL"])

                if json_output:
                    snapshots.append({
                        "t": round(sim_time, 3),
                        "h": round(float(h), 4),
                        "forces": {"FR": round(fr_f, 2), "FL": round(fl_f, 2),
                                   "RR": round(rr_f, 2), "RL": round(rl_f, 2)},
                    })
                elif not self.quiet:
                    print(f"  {sim_time:6.2f} | {h:8.4f} | {fr_f:8.2f} | {fl_f:8.2f} | {rr_f:8.2f} | {rl_f:8.2f}")

        wall_time = time.time() - start

        if json_output:
            final = self.get_state()
            result = {
                "action": action, "duration": duration,
                "wall_time": round(wall_time, 3),
                "speedup": round(duration / wall_time, 1),
                "final_height": round(float(final["base_pos"][2]), 4),
                "final_euler_deg": [round(float(np.degrees(x)), 2) for x in final["imu"]["euler"]],
                "snapshots": snapshots,
            }
            print(json.dumps(result, ensure_ascii=False))
            return final

        if not self.quiet:
            print(f"\n  完成: 仿真{duration}s 实际{wall_time:.2f}s (加速比: {duration/wall_time:.1f}x)")
        return self.get_state()

    def run_gui(self, action="stand", duration=None):
        """GUI可视化仿真"""
        gait = None
        if action == "sit":
            self.set_ctrl(SIT_CTRL)
        elif action in GAITS and GAITS[action]:
            gait = GAITS[action]()
        else:
            self.set_ctrl(STAND_CTRL)

        print(f"\n  GUI仿真: {action}")
        print(f"  关闭窗口退出")

        try:
            with mujoco.viewer.launch_passive(self.model, self.data) as viewer:
                start = time.time()
                while viewer.is_running():
                    step_start = time.time()

                    if gait:
                        self.set_ctrl(gait.get_ctrl(self.data.time))

                    self.step(1)

                    if duration and self.data.time >= duration:
                        break

                    viewer.sync()

                    # 实时同步
                    elapsed = time.time() - step_start
                    if elapsed < self.dt:
                        time.sleep(self.dt - elapsed)

        except Exception as e:
            print(f"  GUI错误: {e}")
            print(f"  提示: 如果无法显示GUI, 使用 --headless 模式")

        print(f"  仿真结束: {self.data.time:.2f}s")


# ============================================================
# Gymnasium 兼容 RL 环境
# ============================================================
class Go1Env:
    """类Gymnasium接口的Go1 RL训练环境 (轻量版, 仅依赖mujoco+numpy)

    注意: 正式RL训练请使用 go1_rl.py::Go1GymEnv, 它包装了完整的
    Gymnasium环境并支持预训练PPO模型加载。本类用于快速演示和原型开发。

    observation (48维):
      - base euler [3]: roll, pitch, yaw
      - base angular velocity [3]
      - joint positions [12]
      - joint velocities [12]
      - previous actions [12]
      - foot contacts [4]
      - base height [1]
      - base linear velocity [1] (forward)

    action (12维):
      - 关节目标位置偏移 (offset from STAND_CTRL)

    reward:
      - 前进速度 + 姿态稳定 + 能量惩罚 + 存活奖励
    """
    def __init__(self, terrain="flat", render=False, quiet=True, damage_profile=None):
        self._terrain_path = None
        if terrain != "flat":
            xml_str = generate_terrain_xml(terrain)
            self._terrain_path = os.path.join(MODEL_DIR, f"_scene_{terrain}.xml")
            with open(self._terrain_path, "w") as f:
                f.write(xml_str)
            self.sim = Go1Simulator(self._terrain_path, quiet=quiet, damage_profile=damage_profile)
        else:
            self.sim = Go1Simulator(quiet=quiet, damage_profile=damage_profile)
        self.render = render
        self.prev_action = np.zeros(12)
        self.step_count = 0
        self.max_steps = 1000

    @property
    def observation_space_shape(self):
        return (48,)

    @property
    def action_space_shape(self):
        return (12,)

    def _get_obs(self):
        state = self.sim.get_state()
        imu = state["imu"]
        contacts = np.array([1.0 if state["foot_contacts"][n] else 0.0
                            for n in ["FR", "FL", "RR", "RL"]])
        obs = np.concatenate([
            imu["euler"],                    # 3
            imu["gyro"],                     # 3
            state["joint_pos"],              # 12
            state["joint_vel"],              # 12
            self.prev_action,                # 12
            contacts,                        # 4
            [state["base_pos"][2]],          # 1  height
            [state["base_vel"][0]],          # 1  forward vel
        ])
        return obs.astype(np.float32)

    def _compute_reward(self, state):
        vel_x = state["base_vel"][0]
        euler = state["imu"]["euler"]
        height = state["base_pos"][2]
        ctrl = state["ctrl"]

        r_velocity = min(vel_x, GO1_PARAMS["max_vel_x"]) * 1.0
        r_orientation = -2.0 * (euler[0]**2 + euler[1]**2)
        r_height = -10.0 * max(0, 0.15 - height)
        r_energy = -0.001 * np.sum(ctrl**2)
        r_alive = 0.2

        return r_velocity + r_orientation + r_height + r_energy + r_alive

    def _is_terminated(self, state):
        euler = state["imu"]["euler"]
        height = state["base_pos"][2]
        if height < 0.1:
            return True
        if abs(euler[0]) > 1.0 or abs(euler[1]) > 1.0:
            return True
        return False

    def _is_truncated(self):
        return self.step_count >= self.max_steps

    def reset(self):
        mujoco.mj_resetDataKeyframe(self.sim.model, self.sim.data, 0)
        mujoco.mj_forward(self.sim.model, self.sim.data)
        self.sim.set_ctrl(STAND_CTRL)
        self.prev_action = np.zeros(12)
        self.step_count = 0
        for _ in range(100):
            self.sim.step()
        return self._get_obs(), {}

    def step(self, action):
        action = np.clip(action, -0.5, 0.5)
        ctrl = STAND_CTRL + action
        self.sim.set_ctrl(ctrl)
        for _ in range(10):
            self.sim.step()
        self.step_count += 1
        self.prev_action = action.copy()

        state = self.sim.get_state()
        obs = self._get_obs()
        reward = self._compute_reward(state)
        terminated = self._is_terminated(state)
        truncated = self._is_truncated()
        info = {"time": state["time"], "height": state["base_pos"][2]}

        return obs, reward, terminated, truncated, info

    def close(self):
        if self._terrain_path and os.path.exists(self._terrain_path):
            try:
                os.remove(self._terrain_path)
            except OSError:
                pass


def run_gym_demo(terrain="flat", episodes=3, max_steps=200, quiet=False):
    """随机策略演示 Gym 接口"""
    if not quiet:
        print(f"\n  Gym RL 演示: terrain={terrain}, episodes={episodes}")
    env = Go1Env(terrain=terrain, quiet=quiet)

    for ep in range(episodes):
        obs, _ = env.reset()
        total_reward = 0
        for step in range(max_steps):
            action = np.random.uniform(-0.2, 0.2, size=12).astype(np.float32)
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            if terminated or truncated:
                break

        if not quiet:
            print(f"  Episode {ep+1}: steps={step+1}, reward={total_reward:.2f}, "
                  f"height={info['height']:.3f}m, time={info['time']:.2f}s")

    env.close()
    if not quiet:
        print(f"\n  演示完成。可集成 stable-baselines3 等RL库进行训练。")


# ============================================================
# 交互式控制
# ============================================================
def interactive_mode(sim):
    """交互式关节控制"""
    print(f"\n{'='*50}")
    print(f"  Go1 交互式仿真控制")
    print(f"{'='*50}")
    print(f"\n可用命令:")
    print(f"  stand          站立")
    print(f"  sit            趴下")
    print(f"  trot           小跑")
    print(f"  pace           踱步")
    print(f"  bound          跳跃")
    print(f"  wave           挥手")
    print(f"  pushup         俯卧撑")
    print(f"  joint N VAL    设置关节N的角度")
    print(f"  state          打印当前状态")
    print(f"  imu            打印IMU数据")
    print(f"  params         显示Go1物理参数")
    print(f"  reset          重置到站立")
    print(f"  quit           退出")
    print(f"\n关节编号: {', '.join(f'{i}={n}' for i,n in enumerate(JOINT_NAMES))}")

    while True:
        try:
            cmd = input("\nGo1-Sim> ").strip()
            if not cmd:
                continue

            parts = cmd.split()
            action = parts[0].lower()

            if action in ("quit", "exit", "q"):
                break
            elif action == "stand":
                sim.set_ctrl(STAND_CTRL)
                sim.run_headless("stand", 2.0)
            elif action == "sit":
                sim.set_ctrl(SIT_CTRL)
                sim.run_headless("sit", 2.0)
            elif action in GAITS and GAITS[action]:
                sim.run_headless(action, 3.0)
            elif action == "joint" and len(parts) >= 3:
                idx = int(parts[1])
                val = float(parts[2])
                ctrl = sim.data.ctrl.copy()
                ctrl[idx] = val
                sim.set_ctrl(ctrl)
                sim.step(500)
                print(f"  关节{idx}({JOINT_NAMES[idx]}) = {val:.3f}")
            elif action == "state":
                state = sim.get_state()
                print(f"\n  时间: {state['time']:.3f}s")
                print(f"  基座位置: {state['base_pos']}")
                print(f"  基座速度: {state['base_vel']}")
                print(f"  关节角度:")
                for i, name in enumerate(JOINT_NAMES):
                    print(f"    {name:<12}: {state['joint_pos'][i]:7.4f} rad ({math.degrees(state['joint_pos'][i]):7.2f}°)")
                print(f"  足端力:")
                for name, f in state['foot_forces'].items():
                    contact = "█" if state['foot_contacts'][name] else "░"
                    print(f"    {name} {contact}: {np.linalg.norm(f):.2f}N")
            elif action == "imu":
                imu = sim.get_imu()
                print(f"\n  IMU数据:")
                print(f"  加速度(body): [{imu['accel'][0]:7.3f}, {imu['accel'][1]:7.3f}, {imu['accel'][2]:7.3f}] m/s²")
                print(f"  角速度(body): [{imu['gyro'][0]:7.4f}, {imu['gyro'][1]:7.4f}, {imu['gyro'][2]:7.4f}] rad/s")
                print(f"  欧拉角: R={math.degrees(imu['euler'][0]):6.2f}° P={math.degrees(imu['euler'][1]):6.2f}° Y={math.degrees(imu['euler'][2]):6.2f}°")
            elif action == "params":
                print(f"\n  Go1 物理参数:")
                for k, v in GO1_PARAMS.items():
                    print(f"    {k}: {v}")
            elif action == "reset":
                mujoco.mj_resetDataKeyframe(sim.model, sim.data, 0)
                mujoco.mj_forward(sim.model, sim.data)
                sim.set_ctrl(STAND_CTRL)
                print("  已重置")
            else:
                print(f"  未知命令: {cmd}")

        except KeyboardInterrupt:
            print("\n退出")
            break
        except Exception as e:
            print(f"  错误: {e}")


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Go1 MuJoCo 本地仿真",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
动作:
  stand      站立 (默认)       gallop     奔跑 (高速trot)
  sit        趴下             crawl      匍匐 (低姿慢行)
  trot       小跑 (对角同步)   pronk      弹跳 (四足同步)
  pace       踱步 (同侧同步)   spin       旋转 (原地转圈)
  bound      跳跃 (前后分组)   sidestep   横移 (侧向行走)
  wave       挥手             backflip   后空翻 (蓄力弹)
  pushup     俯卧撑           dance1     舞蹈1 (摇摆抬腿)
  trot_run   快跑小跑         dance2     舞蹈2 (扭动波动)
  climb      爬坡 (高抬腿)    handshake  握手 (伸右前腿)

示例:
  python go1_sim.py                     # GUI仿真，站立
  python go1_sim.py --action trot       # GUI小跑
  python go1_sim.py --headless -d 10    # 无头仿真10秒
  python go1_sim.py --interactive       # 交互式控制
  python go1_sim.py --terrain rough     # 粗糙地形
  python go1_sim.py --gym              # Gym RL演示
        """)

    parser.add_argument("--action", "-a", default="stand",
                       choices=list(GAITS.keys()),
                       help="动作 (默认: stand)")
    parser.add_argument("--headless", action="store_true",
                       help="无头模式 (无GUI，仅数据输出)")
    parser.add_argument("--interactive", "-i", action="store_true",
                       help="交互式控制模式")
    parser.add_argument("--duration", "-d", type=float, default=10.0,
                       help="仿真时长(秒, 默认10)")
    parser.add_argument("--model", default=SCENE_XML,
                       help="MuJoCo模型路径")
    parser.add_argument("--terrain", "-t", default="flat",
                       choices=["flat", "rough", "stairs", "slope"],
                       help="地形类型 (默认: flat)")
    parser.add_argument("--gym", action="store_true",
                       help="Gymnasium RL训练演示")
    parser.add_argument("--json", action="store_true",
                       help="JSON输出 (Agent/程序化调用)")
    parser.add_argument("--quiet", "-q", action="store_true",
                       help="安静模式 (抑制冗余输出)")
    parser.add_argument("--damage", action="store_true",
                       help="实机损伤模式 (禁用FL_hip/FL_thigh/RL_calf)")

    args = parser.parse_args()

    quiet = args.quiet or args.json

    if not quiet:
        print(f"\n{'='*50}")
        print(f"  Go1 MuJoCo 仿真器 v2.2")
        print(f"  MuJoCo {mujoco.__version__}")
        print(f"{'='*50}\n")

    if args.gym:
        run_gym_demo(terrain=args.terrain, quiet=quiet)
        return

    # 地形生成
    model_path = args.model
    if args.terrain != "flat":
        xml_str = generate_terrain_xml(args.terrain)
        terrain_path = os.path.join(MODEL_DIR, f"_scene_{args.terrain}.xml")
        with open(terrain_path, "w") as f:
            f.write(xml_str)
        model_path = terrain_path
        if not quiet:
            print(f"  地形: {args.terrain}")

    damage = REAL_HARDWARE if args.damage else None
    sim = Go1Simulator(model_path, quiet=quiet, damage_profile=damage)

    if args.interactive:
        interactive_mode(sim)
    elif args.headless or args.json:
        sim.run_headless(args.action, args.duration, json_output=args.json)
    else:
        sim.run_gui(args.action, args.duration)

    # 清理临时地形文件
    if args.terrain != "flat":
        try:
            os.remove(terrain_path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
