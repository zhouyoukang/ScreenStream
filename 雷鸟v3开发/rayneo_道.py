#!/usr/bin/env python3
"""
RayNeo V3 道感知层 — 以老庄统五感，至于无感

引自终点之道:
  得道 = 感知完整 + 无感觉醒 + 反向闭合
  失道 = 感官缺失 → 降级 → 坦诚告知

引自庄之神韵·心斋:
  以耳听 = 等触发词（被动）
  以心听 = 理解语义（主动）
  以气听 = 意图未出口，系统已知（无感）

引自老子第十一章:
  当其无，有车之用 — 眼镜最有用时，用户忘记了它

道感知层架构:
  DaoContext     — 持续上下文（头部姿态·使用历史·意图流）
  IntentEngine   — 以气听（多感合一推断意图）
  GuiGenManager  — 归根管理（佩戴检测→五感生死）
  WuganScore     — 物化评分（无感度0~100）
  DaoEngine      — 主调度（道统五感·归根·物化）

Device: 841571AC688C360 | XRGF50 | Android 12 userdebug
"""

import time
import threading
import math
import json
import re
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Callable

from rayneo_五感 import (
    RayNeoFiveSenses, TouchSense, ButtonSense, HearingSense,
    VisionSense, EnvSense, TTSFeedback,
    adb, adb_bg, device_online,
    ADB, DEVICE, SDK_DIR,
    DEV_HALL, DEV_BTN, TP_SLIDE_THRESH
)


# ─── 意图枚举 ─────────────────────────────────────────────
class Intent(Enum):
    """用户意图分类 — 以气听的产物"""
    VISUAL_CAPTURE   = auto()   # 视觉：想看/想记录
    VOICE_ASK        = auto()   # 听觉：想问/想说
    NAVIGATE_NEXT    = auto()   # 触觉：向前
    NAVIGATE_BACK    = auto()   # 触觉：向后
    CONFIRM          = auto()   # 空间：点头确认
    CANCEL           = auto()   # 空间：摇头取消
    STATUS_CHECK     = auto()   # 环境：想了解当前状态
    IDLE             = auto()   # 归根：无意图，待物
    UNKNOWN          = auto()   # 未知


# ─── 头部姿态状态 ─────────────────────────────────────────
class HeadPose(Enum):
    NEUTRAL  = "neutral"    # 中立
    DOWN     = "down"       # 低头 → 视觉意图
    UP       = "up"         # 抬头 → 语音意图
    NOD      = "nod"        # 点头 → 确认
    SHAKE    = "shake"      # 摇头 → 取消
    UNKNOWN  = "unknown"


# ─── 上下文快照 ───────────────────────────────────────────
@dataclass
class DaoContext:
    """
    道感知上下文 — 持续流动的「气」
    老子第十六章：归根曰静，是谓复命
    """
    # 佩戴状态
    is_worn: bool = False
    worn_since: float = 0.0
    unworn_since: float = 0.0

    # 头部姿态（IMU推断）
    head_pose: HeadPose = HeadPose.NEUTRAL
    pose_since: float = 0.0
    pose_duration: float = 0.0  # 当前姿态持续时间(秒)

    # 加速度/角速度缓冲（用于姿态推断）
    accel_history: deque = field(default_factory=lambda: deque(maxlen=50))
    gyro_history: deque = field(default_factory=lambda: deque(maxlen=50))

    # 意图历史
    intent_history: deque = field(default_factory=lambda: deque(maxlen=20))
    last_intent: Intent = Intent.IDLE
    last_intent_time: float = 0.0

    # 会话统计（物化评分）
    explicit_triggers: int = 0    # 用户主动触发次数
    implicit_handles: int = 0     # 系统预判处理次数
    tasks_completed: int = 0      # 完成任务总数

    # 连续失败计数（庖丁：重试2次=良庖→升级策略）
    consecutive_failures: int = 0

    # 最近静止时间
    last_motion_time: float = field(default_factory=time.time)
    last_action_time: float = field(default_factory=time.time)

    @property
    def stationary_seconds(self) -> float:
        """静止持续时间(秒)"""
        return time.time() - self.last_motion_time

    @property
    def idle_seconds(self) -> float:
        """无操作时间(秒)"""
        return time.time() - self.last_action_time

    @property
    def wugan_score(self) -> float:
        """
        物化评分（无感度）0.0~1.0
        庄子·物化: 1.0 = 用户已忘记在操作眼镜
        """
        total = self.explicit_triggers + self.implicit_handles
        if total == 0:
            return 0.5   # 初始状态，中立
        return self.implicit_handles / total

    def record_explicit(self):
        """记录显式触发（用户主动操作）"""
        self.explicit_triggers += 1
        self.tasks_completed += 1
        self.last_action_time = time.time()

    def record_implicit(self):
        """记录隐式处理（系统预判，用户无感知）"""
        self.implicit_handles += 1
        self.tasks_completed += 1
        self.last_action_time = time.time()


# ─── 以气听：意图推断引擎 ────────────────────────────────
class IntentEngine:
    """
    庄子·心斋：以气听，虚而待物

    不等用户开口（以耳），不分析用户说了什么（以心），
    感知整体情境，在意图涌现前就知道了（以气）。

    规则：
      低头 + 静止 > 0.5s → 视觉意图（想看/想记录）
      抬头 + 静止 > 1.0s → 语音意图（想问/想说）
      空闲 > 30s → 归根，主动报告状态
      连续失败 >= 2 → 升级到语音模式
      刚佩戴 < 5s → 初始化问候
    """

    # 姿态阈值
    TILT_DOWN_DEG = 25.0    # 低头角度阈值
    TILT_UP_DEG = 15.0      # 抬头角度阈值
    SHAKE_DPS = 120.0       # 摇头角速度阈值(°/s)
    NOD_DPS = 80.0          # 点头角速度阈值(°/s)

    def infer(self, ctx: DaoContext) -> Optional[Intent]:
        """
        从当前上下文推断意图
        返回 None 表示无明确意图（归根·静）
        """
        now = time.time()

        # ① 刚戴上眼镜（5秒内）→ 初始化问候
        if ctx.is_worn and (now - ctx.worn_since) < 5.0:
            if ctx.last_intent != Intent.STATUS_CHECK:
                return Intent.STATUS_CHECK

        # ② 低头 + 静止超过0.5秒 → 视觉意图
        if (ctx.head_pose == HeadPose.DOWN
                and ctx.pose_duration > 0.5
                and ctx.stationary_seconds > 0.3):
            return Intent.VISUAL_CAPTURE

        # ③ 抬头 + 静止超过1秒 → 语音意图
        if (ctx.head_pose == HeadPose.UP
                and ctx.pose_duration > 1.0):
            return Intent.VOICE_ASK

        # ④ 点头 → 确认
        if ctx.head_pose == HeadPose.NOD:
            return Intent.CONFIRM

        # ⑤ 摇头 → 取消
        if ctx.head_pose == HeadPose.SHAKE:
            return Intent.CANCEL

        # ⑥ 连续失败 ≥ 2 → 语音升级（庖丁：重试两次则换刀）
        if ctx.consecutive_failures >= 2:
            ctx.consecutive_failures = 0
            return Intent.VOICE_ASK

        # ⑦ 空闲 > 30s → 归根报告（老子第16章：归根曰静）
        if ctx.idle_seconds > 30.0 and ctx.is_worn:
            return Intent.STATUS_CHECK

        return None  # 无意图 → 归根静待

    def update_pose_from_logcat(self, ctx: DaoContext, line: str):
        """从 logcat 更新头部姿态（简化版，实际需要传感器事件解析）"""
        # 真实实现需要解析 SensorService 的加速度数据
        # 此处占位：实际数据通过 IMU getevent 解析
        pass

    def update_pose_from_accel(self, ctx: DaoContext, ax: float, ay: float, az: float):
        """
        从加速度计数据更新头部姿态
        ax, ay, az: 单位 m/s²

        坐标系（眼镜佩戴时）:
          x: 横向（左负右正）
          y: 纵向（前负后正）
          z: 竖向（下负上正）
        重力向量 g ≈ (0, 0, -9.8)
        """
        ctx.accel_history.append((ax, ay, az, time.time()))
        if len(ctx.accel_history) < 5:
            return

        # 计算倾斜角（相对于重力方向）
        # 低头：z分量减小，y分量变化
        gravity_z = az
        tilt_angle = math.degrees(math.acos(
            max(-1.0, min(1.0, -gravity_z / 9.8))
        ))

        prev_pose = ctx.head_pose
        now = time.time()

        if tilt_angle > self.TILT_DOWN_DEG:
            new_pose = HeadPose.DOWN
        elif tilt_angle < (90 - self.TILT_UP_DEG):
            new_pose = HeadPose.UP
        else:
            new_pose = HeadPose.NEUTRAL

        if new_pose != prev_pose:
            ctx.head_pose = new_pose
            ctx.pose_since = now
            ctx.pose_duration = 0.0
        else:
            ctx.pose_duration = now - ctx.pose_since

    def update_pose_from_gyro(self, ctx: DaoContext, gx: float, gy: float, gz: float):
        """
        从陀螺仪检测点头/摇头
        gx, gy, gz: 角速度 (°/s 或 rad/s)
        """
        ctx.gyro_history.append((gx, gy, gz, time.time()))

        angular_speed = math.sqrt(gx**2 + gy**2 + gz**2)
        # gy 主导 → 点头（垂直轴旋转）
        # gz 主导 → 摇头（水平轴旋转）
        if angular_speed > self.NOD_DPS:
            if abs(gy) > abs(gz) * 1.5:
                ctx.head_pose = HeadPose.NOD
                ctx.pose_since = time.time()
            elif abs(gz) > abs(gy) * 1.5 and angular_speed > self.SHAKE_DPS:
                ctx.head_pose = HeadPose.SHAKE
                ctx.pose_since = time.time()
        else:
            ctx.last_motion_time = time.time()


# ─── 归根管理器 ───────────────────────────────────────────
class GuiGenManager:
    """
    老子第十六章：归根曰静，是谓复命。
    Hall传感器监听佩戴状态 → 生死五感线程

    worn  → 复命（启动五感）
    unworn → 归根（关闭五感，降低轮询）
    """

    def __init__(self, on_wear: Callable, on_remove: Callable):
        self.on_wear = on_wear
        self.on_remove = on_remove
        self.running = False
        self._proc = None
        self._last_state = None

    def start(self):
        self.running = True
        t = threading.Thread(target=self._loop, daemon=True, name="GuiGen")
        t.start()
        print("[道] 归根管理器启动 (Hall传感器 event0)")

    def stop(self):
        self.running = False
        if self._proc:
            try:
                self._proc.kill()
            except OSError:
                pass
            self._proc = None

    def _loop(self):
        """
        轮询 Hall 传感器状态
        Hall事件: KEY 024a/024b = 磁场近/远 = 佩戴/取下
        """
        self._proc = adb_bg("shell", "getevent", "-l", DEV_HALL)
        for line in self._proc.stdout:
            if not self.running:
                break
            line = line.strip()
            if "024a" in line or "HALL_NEAR" in line.upper():
                # 佩戴（磁铁靠近 = 镜腿合拢 = 戴上）
                if self._last_state != "worn":
                    self._last_state = "worn"
                    print("[道·归] 佩戴检测 → 复命，五感激活")
                    self.on_wear()
            elif "024b" in line or "HALL_FAR" in line.upper():
                # 取下
                if self._last_state != "unworn":
                    self._last_state = "unworn"
                    print("[道·静] 取下检测 → 归根，五感休眠")
                    self.on_remove()
        if self._proc:
            self._proc.wait()
            self._proc = None


# ─── IMU 道感知监听器 ─────────────────────────────────────
class IMUDaoListener:
    """
    从 sysfs IIO 读取 IMU 数据，更新 DaoContext (fallback: dumpsys sensorservice)
    这是「以气听」的数据来源：头部姿态 = 注意力方向
    """

    def __init__(self, ctx: DaoContext, intent_engine: IntentEngine):
        self.ctx = ctx
        self.ie = intent_engine
        self.running = False
        self._proc = None

    def start(self):
        self.running = True
        t = threading.Thread(target=self._loop, daemon=True, name="IMUDao")
        t.start()
        print("[道] IMU道感知启动 (加速度+陀螺仪)")

    def stop(self):
        self.running = False
        if self._proc:
            try:
                self._proc.kill()
            except OSError:
                pass
            self._proc = None

    def _find_imu_iio(self) -> str | None:
        """查找LSM6DSR的IIO sysfs设备路径"""
        out = adb("shell", "ls", "/sys/bus/iio/devices/", "2>/dev/null")
        if not out or "No such" in out or "ERROR" in out:
            return None
        for dev in out.split():
            path = f"/sys/bus/iio/devices/{dev}"
            name = adb("shell", "cat", f"{path}/name", "2>/dev/null")
            if name and "lsm6ds" in name.lower():
                return path
            # fallback: name不可读时检查是否有加速度计原始数据文件
            check = adb("shell", "ls", f"{path}/in_accel_x_raw", "2>/dev/null")
            if check and "No such" not in check:
                return path
        return None

    def _loop(self):
        """从sysfs IIO持续读取加速度+陀螺仪数据，更新DaoContext"""
        iio_path = self._find_imu_iio()
        if iio_path:
            print(f"  [道] IMU数据源: sysfs IIO ({iio_path})")
            self._loop_iio(iio_path)
        else:
            print("  [道] IMU数据源: dumpsys sensorservice (fallback)")
            self._loop_sensorservice()

    def _loop_iio(self, p: str):
        """通过sysfs IIO持续读取加速度计+陀螺仪"""
        ACCEL_SCALE = 0.000598  # LSM6DSR ±2g: 0.061 mg/LSB → m/s²
        GYRO_SCALE = 0.00875    # LSM6DSR ±250dps: 8.75 mdps/LSB → dps
        cmd = (f"while true; do "
               f"cat {p}/in_accel_x_raw {p}/in_accel_y_raw {p}/in_accel_z_raw "
               f"{p}/in_anglvel_x_raw {p}/in_anglvel_y_raw {p}/in_anglvel_z_raw "
               f"2>/dev/null; echo '---'; sleep 0.1; done")
        self._proc = adb_bg("shell", cmd)
        buf = []
        for line in self._proc.stdout:
            if not self.running:
                break
            line = line.strip()
            if line == '---':
                if len(buf) >= 6:
                    try:
                        ax = float(buf[0]) * ACCEL_SCALE
                        ay = float(buf[1]) * ACCEL_SCALE
                        az = float(buf[2]) * ACCEL_SCALE
                        gx = float(buf[3]) * GYRO_SCALE
                        gy = float(buf[4]) * GYRO_SCALE
                        gz = float(buf[5]) * GYRO_SCALE
                        self.ie.update_pose_from_accel(self.ctx, ax, ay, az)
                        self.ie.update_pose_from_gyro(self.ctx, gx, gy, gz)
                    except (ValueError, IndexError):
                        pass
                elif len(buf) >= 3:
                    try:
                        ax = float(buf[0]) * ACCEL_SCALE
                        ay = float(buf[1]) * ACCEL_SCALE
                        az = float(buf[2]) * ACCEL_SCALE
                        self.ie.update_pose_from_accel(self.ctx, ax, ay, az)
                    except (ValueError, IndexError):
                        pass
                buf = []
            elif line:
                buf.append(line)
        if self._proc:
            self._proc.wait()
            self._proc = None

    def _loop_sensorservice(self):
        """通过dumpsys sensorservice周期性采样 (fallback)
        注意: WiFi ADB下完整dumpsys输出100KB+会导致协议断连，
        在设备端用grep过滤，只传回accel相关行（~100B）"""
        while self.running:
            out = adb("shell",
                      "dumpsys sensorservice 2>/dev/null | grep -i 'accel.*last\\|accel.*value\\|last.*accel'",
                      timeout=5)
            for line in out.splitlines():
                ll = line.lower()
                if "accel" in ll and ("last" in ll or "value" in ll):
                    m = re.search(
                        r'[-+]?\d+\.?\d*\s*,\s*[-+]?\d+\.?\d*\s*,\s*'
                        r'[-+]?\d+\.?\d*', line)
                    if m:
                        try:
                            vals = [float(v.strip())
                                    for v in m.group().split(',')]
                            if len(vals) >= 3:
                                self.ie.update_pose_from_accel(
                                    self.ctx, *vals[:3])
                        except ValueError:
                            pass
                        break
            time.sleep(0.3)


# ─── 道引擎（主调度） ─────────────────────────────────────
class DaoEngine:
    """
    道感知层主引擎 — 老庄统五感

    架构（相忘于江湖·各自独立）:
      GuiGenManager → 佩戴检测 → 五感生死
      IntentEngine  → 以气听 → 意图前馈
      IMUDaoListener → 头部姿态 → 注意力方向
      RayNeoFiveSenses → 五感执行层
      WuganLoop → 每秒检查无感意图

    状态机（归根曰静）:
      ROOTED（归根）→ AWAKENED（复命）→ SENSING（感知）→ ACTING（行动）
      ACTING → SENSING（归静待物）
    """

    def __init__(self):
        self.ctx = DaoContext()
        self.ie = IntentEngine()
        self.tts = TTSFeedback()
        self.vision = VisionSense()
        self.env = EnvSense()

        # 五感触摸/语音（独立线程，相忘于江湖）
        self.touch = None     # 戴上时启动
        self.button = None    # 戴上时启动
        self.hearing = None   # 戴上时启动
        self.imu = None       # 戴上时启动

        # 归根管理器
        self.guigen = GuiGenManager(
            on_wear=self._on_wear,
            on_remove=self._on_remove
        )

        # 意图前馈循环
        self._wugan_thread = None
        self.running = False

        # 日志路径
        self.log_path = SDK_DIR / "dao_session.jsonl"

    # ─── 归根·复命 ────────────────────────────────────────
    def _on_wear(self):
        """
        复命：眼镜被戴上
        老子第16章：复命曰常，知常曰明
        """
        self.ctx.is_worn = True
        self.ctx.worn_since = time.time()
        self._start_five_senses()

    def _on_remove(self):
        """
        归根：眼镜被取下
        老子第16章：归根曰静，是谓复命
        """
        self.ctx.is_worn = False
        self.ctx.unworn_since = time.time()
        self._stop_five_senses()

    def _start_five_senses(self):
        """启动五感线程（相忘于江湖：各自独立，不串行）"""
        if self.touch is None:
            self.touch = TouchSense(self._on_touch)
            self.touch.start()

        if self.button is None:
            self.button = ButtonSense(self._on_button)
            self.button.start()

        if self.hearing is None:
            self.hearing = HearingSense(self._on_wakeup)
            self.hearing.start()

        if self.imu is None:
            self.imu = IMUDaoListener(self.ctx, self.ie)
            self.imu.start()

        print("[道] 五感全部激活 ✅")
        # 戴上5秒后问候（避免即时打扰）
        threading.Timer(2.0, self._welcome).start()

    def _stop_five_senses(self):
        """关闭五感线程（损之又损·归静）"""
        for sense in [self.touch, self.button, self.hearing, self.imu]:
            if sense and hasattr(sense, 'stop'):
                try:
                    sense.stop()
                except Exception:
                    pass
        self.touch = self.button = self.hearing = self.imu = None
        print("[道] 五感归根 🌙")

    # ─── 五感事件处理 ─────────────────────────────────────
    def _on_touch(self, gesture: str):
        """
        TP触控 → 庖丁之道：一触到位，不问确认
        """
        self.ctx.record_explicit()
        self.ctx.consecutive_failures = 0

        if gesture == "tap":
            self._execute_intent(Intent.VISUAL_CAPTURE, source="touch_tap")
        elif gesture == "double_tap":
            self._execute_intent(Intent.VOICE_ASK, source="touch_double")
        elif gesture == "slide_fwd":
            self._execute_intent(Intent.NAVIGATE_NEXT, source="touch_fwd")
        elif gesture == "slide_back":
            self._execute_intent(Intent.NAVIGATE_BACK, source="touch_back")
        elif gesture == "long_press":
            self._execute_intent(Intent.STATUS_CHECK, source="touch_long")

    def _on_button(self, action: str):
        """ActionButton 物理按键"""
        self.ctx.record_explicit()
        if action == "short":
            self._execute_intent(Intent.VISUAL_CAPTURE, source="btn_short")
        elif action == "long":
            self._execute_intent(Intent.STATUS_CHECK, source="btn_long")

    def _on_wakeup(self, detail: str):
        """语音唤醒"""
        self.ctx.record_explicit()
        self._execute_intent(Intent.VOICE_ASK, source="voice_wakeup")

    # ─── 意图执行 ─────────────────────────────────────────
    def _execute_intent(self, intent: Intent, source: str = "explicit"):
        """
        执行意图 — 庖丁之道
        依乎天理，批大郤，导大窾，一次到位
        """
        self.ctx.last_intent = intent
        self.ctx.last_intent_time = time.time()
        self.ctx.intent_history.append({
            "intent": intent.name,
            "source": source,
            "time": self.ctx.last_intent_time,
            "wugan": round(self.ctx.wugan_score, 3)
        })

        print(f"[道·{source}] 意图: {intent.name} (无感度: {self.ctx.wugan_score:.1%})")

        if intent == Intent.VISUAL_CAPTURE:
            self._do_capture()
        elif intent == Intent.VOICE_ASK:
            self.tts.speak("我在，请说")
        elif intent == Intent.NAVIGATE_NEXT:
            self.tts.beep()
            self.tts.speak("向前")
        elif intent == Intent.NAVIGATE_BACK:
            self.tts.beep()
            self.tts.speak("向后")
        elif intent == Intent.CONFIRM:
            self.tts.beep()
        elif intent == Intent.CANCEL:
            self.tts.speak("已取消")
        elif intent == Intent.STATUS_CHECK:
            self._do_status()

    def _do_capture(self):
        """视觉捕获 — 知人者智"""
        self.tts.beep()
        photo = self.vision.capture_photo()
        if photo:
            self.tts.speak("已记录")
        else:
            self.ctx.consecutive_failures += 1
            if self.ctx.consecutive_failures >= 2:
                self.tts.speak("拍照失败，请说出需要帮助的内容")
            else:
                self.tts.speak("稍等")

    def _do_status(self):
        """状态报告 — 自知者明"""
        battery = self._get_battery()
        score = self.ctx.wugan_score
        session_tasks = self.ctx.tasks_completed

        msg_parts = []
        if battery >= 0:
            msg_parts.append(f"电量{battery}%")
        if session_tasks > 0:
            pct = int(score * 100)
            msg_parts.append(f"无感度{pct}分")
        if not msg_parts:
            msg_parts.append("状态正常")

        self.tts.speak("，".join(msg_parts))

    def _welcome(self):
        """戴上问候"""
        if self.ctx.is_worn:
            battery = self._get_battery()
            if battery >= 0:
                self.tts.speak(f"已就绪，电量{battery}%")
            else:
                self.tts.speak("已就绪")
            self.ctx.record_implicit()  # 自动问候 = 无感处理

    # ─── 以气听循环（无感意图前馈）────────────────────────
    def _wugan_loop(self):
        """
        庄子·心斋：以气听
        每秒检查上下文，在用户开口之前推断意图并预备
        这是「无感」的核心：系统的反应先于用户的意识
        """
        while self.running:
            time.sleep(1.0)

            if not self.ctx.is_worn:
                continue

            predicted = self.ie.infer(self.ctx)
            if predicted is None:
                continue

            # 防重复触发（同一意图在5秒内不重复）
            if (predicted == self.ctx.last_intent
                    and time.time() - self.ctx.last_intent_time < 5.0):
                continue

            # 以气听触发 = 隐式处理（无感度+1）
            self.ctx.record_implicit()
            self._execute_intent(predicted, source="yi_qi_ting")

    # ─── 辅助函数 ─────────────────────────────────────────
    def _get_battery(self) -> int:
        out = adb("shell", "dumpsys", "battery")
        for line in out.splitlines():
            if "level:" in line:
                try:
                    return int(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass
        return -1

    def _save_session(self):
        """保存会话日志（死而不亡者寿·遗产传递）"""
        session = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tasks": self.ctx.tasks_completed,
            "explicit": self.ctx.explicit_triggers,
            "implicit": self.ctx.implicit_handles,
            "wugan_score": round(self.ctx.wugan_score * 100, 1),
            "intent_history": list(self.ctx.intent_history)[-10:]
        }
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(session, ensure_ascii=False) + "\n")
            print(f"[道] 会话已固化: 无感度 {session['wugan_score']}分")
        except Exception as e:
            print(f"[道] 日志保存失败: {e}")

    # ─── 主循环 ───────────────────────────────────────────
    def report(self):
        """道感知状态报告"""
        battery = self._get_battery()
        score = self.ctx.wugan_score
        print("\n╔════════════════════════════════════╗")
        print("║       道感知层 · 实时状态           ║")
        print("╚════════════════════════════════════╝")
        print(f"  设备在线: {device_online()}")
        print(f"  佩戴状态: {'✅ 已佩戴' if self.ctx.is_worn else '🌙 归根'}")
        print(f"  电量:     {battery}%")
        print(f"  头部姿态: {self.ctx.head_pose.value}")
        print(f"  静止时间: {self.ctx.stationary_seconds:.1f}s")
        print(f"  无感度:   {score:.1%} ({int(score*100)}/100)")
        print(f"  显式触发: {self.ctx.explicit_triggers}")
        print(f"  隐式处理: {self.ctx.implicit_handles}")
        print(f"  完成任务: {self.ctx.tasks_completed}")
        print(f"  最近意图: {self.ctx.last_intent.name}")

        # 老庄指引
        if score >= 0.8:
            print("\n  ✨ 物化之境 — 道乃久")
        elif score >= 0.5:
            print("\n  🌊 以心听 → 趋近以气听")
        else:
            print("\n  👂 以耳听 → 学习阶段")
        print()

    def run(self):
        """启动道感知引擎"""
        print("\n╔══════════════════════════════════════════╗")
        print("║  RayNeo V3 道感知层 · 以老庄统五感       ║")
        print("║  损之又损，以至于无为。无为而无不为。     ║")
        print("╚══════════════════════════════════════════╝\n")

        if not device_online():
            print("❌ 设备未连接，请检查ADB夹具")
            return

        self.running = True
        self.report()

        # 启动归根管理器（佩戴检测）
        self.guigen.start()

        # 以气听循环
        self._wugan_thread = threading.Thread(
            target=self._wugan_loop, daemon=True, name="YiQiTing"
        )
        self._wugan_thread.start()

        # 检测当前佩戴状态
        worn_now = self.env.is_worn()
        if worn_now:
            print("[道] 检测到眼镜已佩戴，直接复命")
            self._on_wear()

        print("✅ 道感知引擎运行中")
        print("[以气听] 意图前馈已启动 — 不需触发，系统已知")
        print("[归根]   取下眼镜 → 五感自动休眠")
        print("[物化]   无感度实时记录中")
        print("按 Ctrl+C 归根\n")

        try:
            while self.running:
                time.sleep(5)
                # 每5秒输出一次无感度（静默模式下不输出）
        except KeyboardInterrupt:
            print("\n[道·归] 道感知引擎归根")
            self.running = False
            self._stop_five_senses()
            self._save_session()
            self.report()


# ─── CLI 入口 ─────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RayNeo V3 道感知层")
    parser.add_argument("--run",    action="store_true", help="启动道感知引擎（完整）")
    parser.add_argument("--report", action="store_true", help="道感知状态报告")
    parser.add_argument("--speak",  type=str,            help="以道之音播报")
    parser.add_argument("--intent", type=str,            help="测试意图执行")
    args = parser.parse_args()

    dao = DaoEngine()

    if args.report:
        dao.report()
    elif args.speak:
        dao.tts.speak(args.speak)
    elif args.intent:
        intent_map = {name.lower(): i for name, i in Intent.__members__.items()}
        intent = intent_map.get(args.intent.lower(), Intent.UNKNOWN)
        dao._execute_intent(intent, source="cli_test")
    elif args.run:
        dao.run()
    else:
        dao.report()
        print("使用 --run 启动完整道感知引擎")
