"""ORS6 虚拟设备 — 完整6轴伺服物理仿真 + TCode引擎

物理模型:
  每个轴模拟真实MG996R舵机特性:
  - 位置插值 (线性/S曲线)
  - 速度限制 (舵机最大角速度 ~60°/0.15s)
  - 加速度/减速度 (惯性模型)
  - 机械约束 (行程限位)
  - 抖动噪声 (±0.1% 模拟真实舵机精度)

TCode引擎:
  完整解析TCode v0.3协议:
  - 轴命令 (L0-L2, R0-R2, V0-V1, A0-A2)
  - 间隔/速度修饰符
  - 设备命令 (D0停止, D1归位, D2信息)
  - 多命令并行 (空格分隔)

接口:
  - send(cmd) — 发送TCode命令 (兼容TCodeSerial/TCodeWiFi接口)
  - tick(dt) — 物理仿真步进
  - get_state() — 获取全轴状态快照
  - on_state_change — 回调, 状态变化时触发

用法:
  dev = VirtualORS6()
  dev.connect()
  dev.send("L09999I1000")  # L0轴1秒内移到顶部
  for _ in range(60):
      dev.tick(1/60)
      print(dev.get_state())
"""

import time
import math
import json
import random
import logging
import threading
from dataclasses import dataclass, field
from typing import Optional, Callable

from .protocol import TCodeCommand, parse_multi, is_device_command

logger = logging.getLogger(__name__)


@dataclass
class ServoConfig:
    """舵机物理参数 (MG996R默认值)"""
    max_speed: float = 66666.0      # 最大速度 (TCode位置单位/秒, ~60°/0.15s → 全行程0.15s)
    acceleration: float = 200000.0  # 加速度 (位置单位/秒²)
    deceleration: float = 250000.0  # 减速度 (大于加速度, 更快停下)
    jitter: float = 5.0             # 位置抖动 (±N TCode单位, 模拟舵机精度)
    deadband: float = 10.0          # 死区 (差值小于此值不运动)
    smoothing: float = 0.85         # S曲线平滑因子 (0=线性, 1=完全平滑)


@dataclass
class ServoState:
    """单个舵机的实时状态"""
    axis: str = "L0"
    # 目标与当前
    target: float = 5000.0          # 目标位置 (TCode 0-9999)
    current: float = 5000.0         # 当前位置 (含物理模拟)
    velocity: float = 0.0           # 当前速度 (位置/秒)
    # 运动参数
    interval_ms: Optional[int] = None   # 到达目标的时间
    speed_limit: Optional[float] = None  # 速度限制
    move_elapsed: float = 0.0      # 运动已用时间(秒)
    move_start_pos: float = 5000.0  # 运动开始位置
    # 统计
    total_distance: float = 0.0     # 累计运动距离
    command_count: int = 0          # 收到的命令数
    is_moving: bool = False         # 是否在运动中

    @property
    def position_pct(self) -> float:
        """当前位置百分比 (0-100)"""
        return self.current / 9999.0 * 100.0

    @property
    def position_normalized(self) -> float:
        """归一化位置 (0.0-1.0)"""
        return self.current / 9999.0


class VirtualServo:
    """单个虚拟舵机 — 物理仿真"""

    def __init__(self, axis: str, config: ServoConfig = None):
        self.axis = axis
        self.config = config or ServoConfig()
        self.state = ServoState(axis=axis)
        self._last_tick = time.time()

    def set_target(self, position: int,
                   interval_ms: Optional[int] = None,
                   speed: Optional[int] = None):
        """设置目标位置"""
        position = max(0, min(9999, position))
        self.state.target = float(position)
        self.state.move_elapsed = 0.0
        self.state.move_start_pos = self.state.current
        self.state.command_count += 1

        if interval_ms is not None and interval_ms > 0:
            self.state.interval_ms = interval_ms
            # 计算所需速度
            dist = abs(self.state.target - self.state.current)
            self.state.speed_limit = dist / (interval_ms / 1000.0) if dist > 0 else 0
        elif speed is not None and speed > 0:
            self.state.speed_limit = float(speed)
            self.state.interval_ms = None
        else:
            # 无修饰符: 以最大速度移动
            self.state.speed_limit = self.config.max_speed
            self.state.interval_ms = None

        self.state.is_moving = True

    def stop(self):
        """紧急停止"""
        self.state.target = self.state.current
        self.state.velocity = 0.0
        self.state.is_moving = False
        self.state.interval_ms = None
        self.state.speed_limit = None

    def home(self, interval_ms: int = 1000):
        """归中位"""
        self.set_target(5000, interval_ms=interval_ms)

    def tick(self, dt: float):
        """物理仿真步进

        Args:
            dt: 时间步长(秒)
        """
        if dt <= 0:
            return

        error = self.state.target - self.state.current

        # 死区检测
        if abs(error) < self.config.deadband:
            if self.state.is_moving:
                self.state.is_moving = False
                self.state.velocity = 0.0
            # 添加微小抖动 (模拟真实舵机)
            if self.config.jitter > 0:
                self.state.current += random.gauss(0, self.config.jitter * 0.3)
                self.state.current = max(0, min(9999, self.state.current))
            return

        # 计算目标速度
        max_speed = self.state.speed_limit or self.config.max_speed
        max_speed = min(max_speed, self.config.max_speed)

        # 如果有interval_ms, 使用S曲线插值
        if self.state.interval_ms and self.state.interval_ms > 0:
            self.state.move_elapsed += dt
            elapsed = self.state.move_elapsed
            duration = self.state.interval_ms / 1000.0
            if duration > 0:
                t = min(1.0, elapsed / duration)
                # S曲线: smoothstep
                t_smooth = t * t * (3 - 2 * t)
                t_blend = t * (1 - self.config.smoothing) + t_smooth * self.config.smoothing
                new_pos = self.state.move_start_pos + (self.state.target - self.state.move_start_pos) * t_blend
                distance = abs(new_pos - self.state.current)
                self.state.total_distance += distance
                self.state.velocity = distance / dt if dt > 0 else 0
                self.state.current = new_pos
                if t >= 1.0:
                    self.state.current = self.state.target
                    self.state.is_moving = False
                    self.state.velocity = 0.0
                return

        # 无interval: 加速度模型
        direction = 1.0 if error > 0 else -1.0

        # 减速距离 (v²/2a)
        decel_dist = (self.state.velocity ** 2) / (2 * self.config.deceleration) if self.config.deceleration > 0 else 0

        if abs(error) <= decel_dist + self.config.deadband:
            # 减速区
            accel = -direction * self.config.deceleration
        else:
            # 加速区
            if abs(self.state.velocity) < max_speed:
                accel = direction * self.config.acceleration
            else:
                accel = 0  # 已达最大速度

        # 更新速度
        self.state.velocity += accel * dt
        # 限速
        if abs(self.state.velocity) > max_speed:
            self.state.velocity = direction * max_speed

        # 更新位置
        displacement = self.state.velocity * dt
        old_pos = self.state.current
        self.state.current += displacement
        self.state.current = max(0, min(9999, self.state.current))

        # 到达检测
        new_error = self.state.target - self.state.current
        if (error > 0 and new_error <= 0) or (error < 0 and new_error >= 0):
            self.state.current = self.state.target
            self.state.velocity = 0.0
            self.state.is_moving = False

        self.state.total_distance += abs(self.state.current - old_pos)

    def to_dict(self) -> dict:
        """序列化状态"""
        return {
            "axis": self.axis,
            "target": round(self.state.target),
            "current": round(self.state.current),
            "velocity": round(self.state.velocity, 1),
            "position_pct": round(self.state.position_pct, 2),
            "is_moving": self.state.is_moving,
            "command_count": self.state.command_count,
            "total_distance": round(self.state.total_distance),
        }


class VirtualORS6:
    """ORS6 虚拟设备 — 6轴物理仿真 + TCode引擎

    接口兼容 TCodeSerial / TCodeWiFi, 可直接替换用于测试。
    """

    # 固件信息 (模拟TCodeESP32响应)
    FIRMWARE_INFO = "TCodeVirtual v1.0 | 6-Axis | Sim"

    # 标准轴定义
    AXIS_NAMES = {
        "L0": "Stroke", "L1": "Surge", "L2": "Sway",
        "R0": "Twist",  "R1": "Roll",  "R2": "Pitch",
        "V0": "Vibe1",  "V1": "Vibe2",
        "A0": "Valve",  "A1": "Lube",  "A2": "Heat",
    }

    def __init__(self, servo_config: ServoConfig = None,
                 tick_hz: float = 120.0,
                 auto_tick: bool = True):
        """
        Args:
            servo_config: 舵机物理参数 (所有轴共享)
            tick_hz: 物理仿真频率 (Hz)
            auto_tick: 是否自动启动物理仿真线程
        """
        self._config = servo_config or ServoConfig()
        self._tick_hz = tick_hz
        self._auto_tick = auto_tick

        # 创建6个标准轴 + 辅助轴
        self._servos: dict[str, VirtualServo] = {}
        for axis in ["L0", "L1", "L2", "R0", "R1", "R2", "V0", "V1", "A0"]:
            self._servos[axis] = VirtualServo(axis, ServoConfig(**vars(self._config)))

        self._connected = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # 命令历史 (环形缓冲)
        self._history: list[dict] = []
        self._history_max = 500
        self._total_commands = 0

        # 回调
        self.on_state_change: Optional[Callable[[dict], None]] = None
        self.on_command: Optional[Callable[[str], None]] = None

        # 性能统计
        self._start_time = 0.0
        self._tick_count = 0

    # ── 连接接口 (兼容TCodeSerial/TCodeWiFi) ──

    def connect(self) -> bool:
        """建立连接 (启动物理仿真)"""
        if self._connected:
            return True
        self._connected = True
        self._start_time = time.time()
        logger.info(f"VirtualORS6 已连接 ({len(self._servos)}轴, {self._tick_hz}Hz)")

        if self._auto_tick:
            self._start_sim()
        return True

    def disconnect(self):
        """断开连接"""
        self._stop_sim()
        self._connected = False
        logger.info("VirtualORS6 已断开")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── TCode命令接口 ──

    def send(self, command: str) -> Optional[str]:
        """发送TCode命令 (兼容TCodeSerial.send)"""
        if not self._connected:
            return None

        command = command.strip()
        if not command:
            return None

        self._total_commands += 1

        # 记录历史
        self._record_command(command)

        # 回调
        if self.on_command:
            try:
                self.on_command(command)
            except Exception:
                pass

        # 设备命令
        upper = command.upper()
        if upper == "D0" or upper == "DSTOP":
            self._emergency_stop()
            return "OK"
        if upper == "D1":
            self._home_all()
            return "OK"
        if upper == "D2":
            return self.FIRMWARE_INFO

        # 解析多轴命令
        with self._lock:
            try:
                commands = parse_multi(command)
                for cmd in commands:
                    servo = self._servos.get(cmd.axis)
                    if servo:
                        servo.set_target(cmd.position, cmd.interval_ms, cmd.speed)
            except Exception as e:
                logger.debug(f"命令解析失败: {command} — {e}")
                return None

        return None  # TCode设备通常不响应运动命令

    def send_command(self, cmd: TCodeCommand) -> Optional[str]:
        """发送TCodeCommand对象"""
        return self.send(cmd.encode())

    def send_batch(self, commands: list[TCodeCommand]) -> Optional[str]:
        """发送多轴命令"""
        encoded = " ".join(c.encode() for c in commands)
        return self.send(encoded)

    # ── 便捷方法 (兼容TCodeSerial) ──

    def move(self, axis: str, position: int,
             interval_ms: Optional[int] = None) -> Optional[str]:
        cmd = TCodeCommand(axis=axis, position=position, interval_ms=interval_ms)
        return self.send(cmd.encode())

    def home_all(self, interval_ms: int = 1000) -> Optional[str]:
        self._home_all(interval_ms)
        return "OK"

    def stop(self) -> Optional[str]:
        self._emergency_stop()
        return "OK"

    def device_info(self) -> Optional[str]:
        return self.FIRMWARE_INFO

    # ── 状态查询 ──

    def get_state(self) -> dict:
        """获取完整设备状态快照"""
        with self._lock:
            axes = {}
            any_moving = False
            for axis, servo in self._servos.items():
                axes[axis] = servo.to_dict()
                if servo.state.is_moving:
                    any_moving = True

        uptime = time.time() - self._start_time if self._start_time > 0 else 0

        return {
            "connected": self._connected,
            "running": self._running,
            "axes": axes,
            "any_moving": any_moving,
            "total_commands": self._total_commands,
            "tick_count": self._tick_count,
            "tick_hz": self._tick_hz,
            "uptime_sec": round(uptime, 1),
            "firmware": self.FIRMWARE_INFO,
        }

    def get_positions(self) -> dict[str, float]:
        """获取所有轴当前位置 {axis: 0-9999}"""
        with self._lock:
            return {a: round(s.state.current) for a, s in self._servos.items()}

    def get_history(self, last_n: int = 50) -> list[dict]:
        """获取最近N条命令历史"""
        return self._history[-last_n:]

    # ── 物理仿真 ──

    def tick(self, dt: float = None):
        """手动物理仿真步进 (auto_tick=False时使用)"""
        if dt is None:
            dt = 1.0 / self._tick_hz

        with self._lock:
            for servo in self._servos.values():
                servo.tick(dt)
        self._tick_count += 1

        # 状态变化回调
        if self.on_state_change:
            try:
                self.on_state_change(self.get_state())
            except Exception:
                pass

    def _start_sim(self):
        """启动物理仿真线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._sim_loop, daemon=True)
        self._thread.start()

    def _stop_sim(self):
        """停止物理仿真线程"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _sim_loop(self):
        """物理仿真主循环"""
        interval = 1.0 / self._tick_hz
        while self._running:
            self.tick(interval)
            time.sleep(interval)

    # ── 内部方法 ──

    def _emergency_stop(self):
        """紧急停止所有轴"""
        with self._lock:
            for servo in self._servos.values():
                servo.stop()
        logger.info("⚡ 紧急停止")

    def _home_all(self, interval_ms: int = 1000):
        """全轴归中位"""
        with self._lock:
            for servo in self._servos.values():
                servo.home(interval_ms)
        logger.info(f"🏠 全轴归位 ({interval_ms}ms)")

    def _record_command(self, command: str):
        """记录命令到历史"""
        entry = {
            "cmd": command,
            "time": time.time(),
            "seq": self._total_commands,
        }
        self._history.append(entry)
        if len(self._history) > self._history_max:
            self._history = self._history[-self._history_max:]

    # ── 上下文管理器 ──

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.stop()
        self.disconnect()

    def __repr__(self):
        status = "connected" if self._connected else "disconnected"
        return f"VirtualORS6({len(self._servos)}轴, {self._tick_hz}Hz, {status})"
