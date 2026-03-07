"""Funscript多轴同步播放器"""

import time
import logging
import threading
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from .parser import Funscript
from tcode.protocol import TCodeCommand

logger = logging.getLogger(__name__)


@dataclass
class SafetyConfig:
    """硬件安全限制配置
    
    防止funscript中极端运动损坏设备:
    - max_speed: 每秒最大位置变化量 (TCode单位/秒, 9999=全行程)
    - max_accel: 每帧最大加速度变化量
    - min_interval_ms: 相邻命令最小间隔
    - position_clamp: 位置限制范围 [min, max]
    """
    max_speed: int = 15000
    max_accel: int = 8000
    min_interval_ms: int = 10
    position_min: int = 0
    position_max: int = 9999
    enabled: bool = True


class FunscriptPlayer:
    """多轴Funscript同步播放器

    用法:
        player = FunscriptPlayer(port="COM5")
        player.load("video.funscript")       # 自动加载多轴
        player.play()
        player.pause()
        player.seek(30.0)                     # 跳到30秒
        player.stop()
        
        # 安全限制
        player.safety.max_speed = 12000       # 限制最大速度
        player.safety.position_min = 500      # 限制行程下限
        player.safety.position_max = 9500     # 限制行程上限
    """

    def __init__(self, port: Optional[str] = None,
                 wifi_host: Optional[str] = None,
                 wifi_port: int = 8000,
                 update_hz: int = 60,
                 safety: Optional[SafetyConfig] = None):
        self._port = port
        self._wifi_host = wifi_host
        self._wifi_port = wifi_port
        self._update_hz = update_hz
        self._device = None
        self._scripts: dict[str, Funscript] = {}
        self._playing = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._start_time: float = 0
        self._pause_offset: float = 0
        self._current_ms: int = 0
        self._speed: float = 1.0
        self.safety = safety or SafetyConfig()
        self._prev_positions: dict[str, int] = {}
        self._prev_velocities: dict[str, float] = {}

    def _create_device(self):
        """创建TCode设备"""
        if self._wifi_host:
            from tcode import TCodeWiFi
            dev = TCodeWiFi(host=self._wifi_host, port=self._wifi_port)
        else:
            from tcode import TCodeSerial
            dev = TCodeSerial(port=self._port)

        if not dev.connect():
            raise ConnectionError("设备连接失败")
        return dev

    def load(self, path: str | Path):
        """加载Funscript文件（自动检测多轴）"""
        path = Path(path)
        self._scripts = Funscript.load_multi_axis(path)
        if not self._scripts:
            # 单文件模式
            fs = Funscript.load(path)
            self._scripts = {fs.axis: fs}
        logger.info(f"已加载 {len(self._scripts)} 个轴: "
                     f"{', '.join(self._scripts.keys())}")

    def load_single(self, path: str | Path, axis: str = "L0"):
        """加载单个Funscript到指定轴"""
        fs = Funscript.load(path)
        fs.axis = axis
        self._scripts[axis] = fs

    @property
    def is_playing(self) -> bool:
        """是否正在播放"""
        return self._playing

    @property
    def is_paused(self) -> bool:
        """是否暂停中"""
        return self._paused

    @property
    def has_scripts(self) -> bool:
        """是否已加载脚本"""
        return bool(self._scripts)

    def clear_scripts(self):
        """清空所有已加载脚本"""
        self._scripts.clear()

    @property
    def duration_sec(self) -> float:
        """最长轴的时长"""
        if not self._scripts:
            return 0
        return max(fs.duration_sec for fs in self._scripts.values())

    @property
    def current_time_sec(self) -> float:
        return self._current_ms / 1000.0

    @property
    def speed(self) -> float:
        return self._speed

    @speed.setter
    def speed(self, value: float):
        self._speed = max(0.1, min(5.0, value))

    def _playback_loop(self):
        """播放循环"""
        interval = 1.0 / self._update_hz
        duration_ms = int(self.duration_sec * 1000)

        logger.info(f"开始播放: {self.duration_sec:.1f}s, {self._update_hz}Hz")

        while self._playing:
            if self._paused:
                time.sleep(0.05)
                continue

            elapsed = (time.time() - self._start_time) * self._speed * 1000
            self._current_ms = int(elapsed + self._pause_offset * 1000)

            if self._current_ms >= duration_ms:
                logger.info("播放完成")
                self._playing = False
                break

            # 生成所有轴的TCode命令 (经过安全限制)
            commands = []
            for axis, fs in self._scripts.items():
                tcode_pos = fs.get_tcode_at(self._current_ms)
                tcode_pos = self._apply_safety(axis, tcode_pos)
                commands.append(f"{axis}{tcode_pos:04d}")

            if commands and self._device:
                self._device.send(" ".join(commands))

            time.sleep(interval)

        # 播放结束归中位
        if self._device:
            self._device.home_all()

    def play(self):
        """开始/恢复播放"""
        if not self._scripts:
            logger.error("未加载Funscript")
            return

        if self._paused:
            self._paused = False
            self._start_time = time.time()
            logger.info(f"恢复播放: {self.current_time_sec:.1f}s")
            return

        if self._playing:
            return

        if self._device is None:
            self._device = self._create_device()

        self._playing = True
        self._paused = False
        self._start_time = time.time()
        self._pause_offset = 0

        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()

    def pause(self):
        """暂停播放"""
        if self._playing and not self._paused:
            self._paused = True
            self._pause_offset = self.current_time_sec
            logger.info(f"暂停: {self.current_time_sec:.1f}s")

    def stop(self):
        """停止播放"""
        self._playing = False
        self._paused = False
        if self._thread:
            self._thread.join(timeout=3)
        if self._device:
            self._device.stop()
            self._device.home_all()
        self._current_ms = 0
        self._pause_offset = 0
        logger.info("已停止")

    def seek(self, time_sec: float):
        """跳转到指定时间(秒)"""
        self._pause_offset = max(0, min(time_sec, self.duration_sec))
        self._start_time = time.time()
        self._current_ms = int(self._pause_offset * 1000)
        logger.info(f"跳转到: {time_sec:.1f}s")

    def _apply_safety(self, axis: str, position: int) -> int:
        """应用安全限制到位置值"""
        if not self.safety.enabled:
            return position
        
        # 位置钳制
        position = max(self.safety.position_min,
                       min(self.safety.position_max, position))
        
        # 速度限制
        prev = self._prev_positions.get(axis, 5000)
        dt = 1.0 / self._update_hz
        velocity = (position - prev) / dt if dt > 0 else 0
        
        if abs(velocity) > self.safety.max_speed:
            direction = 1 if velocity > 0 else -1
            max_delta = int(self.safety.max_speed * dt)
            position = prev + direction * max_delta
            position = max(self.safety.position_min,
                           min(self.safety.position_max, position))
        
        # 加速度限制
        prev_vel = self._prev_velocities.get(axis, 0.0)
        accel = (velocity - prev_vel) / dt if dt > 0 else 0
        if abs(accel) > self.safety.max_accel:
            direction = 1 if accel > 0 else -1
            velocity = prev_vel + direction * self.safety.max_accel * dt
            position = prev + int(velocity * dt)
            position = max(self.safety.position_min,
                           min(self.safety.position_max, position))
        
        self._prev_positions[axis] = position
        self._prev_velocities[axis] = velocity
        return position

    def status(self) -> dict:
        return {
            "playing": self._playing,
            "paused": self._paused,
            "current_time": self.current_time_sec,
            "duration": self.duration_sec,
            "speed": self._speed,
            "axes": list(self._scripts.keys()),
            "safety_enabled": self.safety.enabled,
        }

    def disconnect(self):
        """断开设备"""
        self.stop()
        if self._device:
            self._device.disconnect()
            self._device = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.disconnect()
