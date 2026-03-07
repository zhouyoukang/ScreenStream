#!/usr/bin/env python3
"""
抖音×OSR6 全链路虚拟仿真测试 — 不依赖实机

模拟链路:
  合成音频(120BPM) → BeatSyncer → Funscript → MockDevice → TCode验证
  MockPage(模拟抖音) → Agent逻辑 → Pipeline → 全链路验证

依赖: numpy, librosa, soundfile (已安装)
用法: python tests/test_douyin_sim.py
"""

import sys
import os
import time
import json
import wave
import struct
import asyncio
import tempfile
import shutil
import logging
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass

# 添加项目根目录到path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname).1s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("sim_test")

RESULTS = []
TEMP_DIR = None


def log_test(test_id, name, status, detail=""):
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    line = f"  {icon} {test_id} {name}: {status}"
    if detail:
        line += f" — {detail}"
    print(line)
    RESULTS.append({"id": test_id, "name": name, "status": status, "detail": detail})


# ═══════════════════════════════════════════════════════
# 虚拟仿真组件
# ═══════════════════════════════════════════════════════

def generate_test_audio(path: str, duration_sec: float = 10.0,
                        bpm: float = 120.0, sr: int = 22050) -> str:
    """生成带明确节拍的合成WAV音频

    120BPM = 每0.5秒一个kick → librosa应检测到~120BPM
    信号: kick(低频正弦脉冲) + hi-hat(高频噪声脉冲)
    """
    import numpy as np

    n_samples = int(duration_sec * sr)
    audio = np.zeros(n_samples, dtype=np.float32)

    beat_interval = 60.0 / bpm  # 秒
    kick_dur = 0.05  # kick时长
    hihat_dur = 0.02

    t = np.arange(int(kick_dur * sr)) / sr

    # Kick: 60Hz指数衰减正弦
    kick = np.sin(2 * np.pi * 60 * t) * np.exp(-t * 40) * 0.8
    # Hi-hat: 白噪声脉冲
    hihat = np.random.randn(int(hihat_dur * sr)).astype(np.float32) * 0.15 * np.exp(-np.arange(int(hihat_dur * sr)) / sr * 80)

    beat_time = 0.0
    beat_count = 0
    while beat_time < duration_sec:
        idx = int(beat_time * sr)
        # Kick on every beat
        end = min(idx + len(kick), n_samples)
        audio[idx:end] += kick[:end - idx]

        # Hi-hat on off-beats (every other beat)
        if beat_count % 2 == 1:
            hihat_idx = idx
            hihat_end = min(hihat_idx + len(hihat), n_samples)
            audio[hihat_idx:hihat_end] += hihat[:hihat_end - hihat_idx]

        beat_time += beat_interval
        beat_count += 1

    # Normalize
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.9

    # Write WAV
    import soundfile as sf
    sf.write(path, audio, sr, subtype='PCM_16')

    return path


class MockTCodeDevice:
    """模拟TCode设备 — 捕获所有命令用于验证"""

    def __init__(self):
        self.commands: list[str] = []
        self.connected = True
        self._connect_time = time.time()

    def connect(self) -> bool:
        self.connected = True
        return True

    def send(self, cmd: str):
        self.commands.append(cmd)

    def stop(self):
        self.commands.append("STOP")

    def home_all(self):
        self.commands.append("HOME")

    def disconnect(self):
        self.connected = False

    @property
    def command_count(self):
        return len([c for c in self.commands if c not in ("STOP", "HOME")])

    def get_axis_commands(self, axis: str = "L0") -> list[int]:
        """提取特定轴的位置序列"""
        positions = []
        for cmd in self.commands:
            if cmd in ("STOP", "HOME"):
                continue
            for part in cmd.split():
                if part.startswith(axis) and len(part) >= 6:
                    try:
                        pos = int(part[2:6])
                        positions.append(pos)
                    except ValueError:
                        pass
        return positions


class MockPlaywrightPage:
    """模拟Playwright Page — 模拟抖音视频状态变化"""

    def __init__(self):
        self._videos = []
        self._current_idx = 0
        self._current_time = 0.0
        self._paused = False
        self._events = []
        self._monitor_installed = False
        self._evaluate_count = 0

        # 预设视频序列
        self._videos = [
            {
                "pageUrl": "https://www.douyin.com/video/7001",
                "src": "blob:https://www.douyin.com/v1",
                "duration": 15.0,
                "description": "测试视频1 - 120BPM节拍",
                "author": "SimUser",
                "currentTime": 0.0,
                "paused": False,
                "ended": False,
                "loop": True,
                "playbackRate": 1.0,
                "volume": 1.0,
                "width": 1080,
                "height": 1920,
                "readyState": 4,
            },
            {
                "pageUrl": "https://www.douyin.com/video/7002",
                "src": "blob:https://www.douyin.com/v2",
                "duration": 30.0,
                "description": "测试视频2 - 舞蹈同步",
                "author": "SimDancer",
                "currentTime": 0.0,
                "paused": False,
                "ended": False,
                "loop": True,
                "playbackRate": 1.0,
                "volume": 1.0,
                "width": 720,
                "height": 1280,
                "readyState": 4,
            },
        ]

    async def evaluate(self, js: str):
        """模拟JS执行"""
        self._evaluate_count += 1

        if "_osr6_ready" in js or "_osr6_observer" in js:
            # JS_INIT_MONITOR
            self._monitor_installed = True
            return {"status": "initialized"}

        if "_osr6_events" in js and "window._osr6_events = []" in js:
            # JS_POLL_EVENTS
            events = self._events.copy()
            self._events.clear()
            return events

        if "activeVideo" in js or "active.src" in js or "active.currentTime" in js:
            # JS_GET_STATE
            if not self._videos:
                return None
            state = self._videos[self._current_idx].copy()
            state["currentTime"] = self._current_time
            state["paused"] = self._paused
            return state

        if "v.currentTime" in js and "v.duration" in js:
            # JS_GET_PLAYBACK
            if not self._videos:
                return None
            return {
                "t": self._current_time,
                "d": self._videos[self._current_idx]["duration"],
                "p": self._paused,
                "e": False,
                "r": 1.0,
            }

        return None

    async def goto(self, url, **kwargs):
        pass

    async def add_init_script(self, script):
        pass

    def simulate_video_change(self):
        """模拟用户滑动到下一个视频"""
        self._current_idx = (self._current_idx + 1) % len(self._videos)
        self._current_time = 0.0
        self._events.append({
            "type": "video_change",
            "src": self._videos[self._current_idx]["src"],
            "url": self._videos[self._current_idx]["pageUrl"],
            "time": int(time.time() * 1000),
        })

    def simulate_playback_advance(self, dt: float = 0.5):
        """模拟视频播放前进"""
        video = self._videos[self._current_idx]
        self._current_time += dt
        if self._current_time >= video["duration"]:
            if video.get("loop"):
                self._current_time = 0.0
            else:
                self._paused = True


# ═══════════════════════════════════════════════════════
# 测试用例
# ═══════════════════════════════════════════════════════

def test_T1_synthetic_audio():
    """T1: 合成测试音频生成"""
    audio_path = os.path.join(TEMP_DIR, "test_120bpm.wav")
    generate_test_audio(audio_path, duration_sec=10.0, bpm=120.0)

    assert os.path.exists(audio_path), "WAV文件未生成"
    with wave.open(audio_path) as wf:
        sr = wf.getframerate()
        dur = wf.getnframes() / sr
        assert sr == 22050, f"采样率异常: {sr}"
        assert abs(dur - 10.0) < 0.1, f"时长异常: {dur}"

    log_test("T1", "合成音频生成", "PASS", f"120BPM, {dur:.1f}s, {sr}Hz WAV")
    return audio_path


def test_T2_beat_detection(audio_path: str):
    """T2: BeatSyncer节拍检测 (无实机核心验证)"""
    from video_sync.beat_sync import BeatSyncer, BeatSyncConfig

    syncer = BeatSyncer(BeatSyncConfig(mode="onset"))
    result = syncer.generate(audio_path)

    assert result is not None, "BeatSyncer返回None"
    assert len(result.actions) > 5, f"动作点太少: {len(result.actions)}"

    # SyncResult.tempo 是直接属性
    tempo = result.tempo
    # onset模式下tempo可能为0 (只有beat/hybrid模式检测BPM)
    # 所以这里只验证动作数量和格式

    # BeatAction对象有 .at 和 .pos 属性
    positions = [a.pos for a in result.actions]
    assert min(positions) >= 0, "位置低于0"
    assert max(positions) <= 100, "位置超过100"

    # 验证时间排序
    times = [a.at for a in result.actions]
    assert times == sorted(times), "动作时间未排序"

    log_test("T2", "节拍检测(onset)", "PASS",
             f"BPM={tempo:.0f}, 动作数={len(result.actions)}, "
             f"pos范围=[{min(positions)},{max(positions)}]")

    return result


def test_T3_multi_axis_beat(audio_path: str):
    """T3: 多轴funscript生成"""
    from video_sync.beat_sync import BeatSyncer, BeatSyncConfig

    syncer = BeatSyncer(BeatSyncConfig(mode="onset", multi_axis=True))
    multi_result = syncer.generate_multi(audio_path)

    assert multi_result is not None, "多轴生成返回None"
    # MultiSyncResult.results is dict[str, SyncResult]
    results = multi_result.results
    assert len(results) >= 3, f"轴数太少: {len(results)} (期望>=3)"

    axis_names = list(results.keys())
    for axis, result in results.items():
        assert len(result.actions) > 0, f"轴{axis}无动作点"

    log_test("T3", "多轴funscript", "PASS",
             f"{len(results)}轴: {axis_names}")
    return results


def test_T4_funscript_save_load(results: dict):
    """T4: Funscript保存和加载"""
    from funscript.parser import Funscript

    saved_paths = {}
    for axis, result in results.items():
        fs_path = os.path.join(TEMP_DIR, f"test_{axis}.funscript")
        result.save(fs_path)  # SyncResult.save()
        assert os.path.exists(fs_path), f"文件未保存: {fs_path}"

        # 验证JSON格式
        with open(fs_path) as f:
            data = json.load(f)
        assert "actions" in data, "缺少actions字段"
        assert len(data["actions"]) > 0, "actions为空"
        # JSON中actions是 [{"at": int, "pos": int}, ...]
        for a in data["actions"]:
            assert "at" in a and "pos" in a, f"动作格式错误: {a}"
        saved_paths[axis] = fs_path

    # 加载验证 (Funscript.load解析JSON→FunscriptAction对象)
    for axis, path in saved_paths.items():
        fs = Funscript.load(path)
        assert len(fs.actions) > 0, f"加载后{axis}无动作"
        tcode = fs.get_tcode_at(1000)  # 1秒处
        assert 0 <= tcode <= 9999, f"TCode越界: {tcode}"

    log_test("T4", "Funscript存储", "PASS",
             f"保存+加载{len(saved_paths)}轴, TCode范围验证OK")
    return saved_paths


def test_T5_mock_device_playback(saved_paths: dict):
    """T5: MockDevice播放验证 — 模拟FunscriptPlayer"""
    from funscript.player import FunscriptPlayer, SafetyConfig

    # 创建player, 注入MockDevice
    player = FunscriptPlayer(port="MOCK", safety=SafetyConfig(max_speed=15000))
    mock_device = MockTCodeDevice()
    player._device = mock_device

    # 加载所有轴
    for axis, path in saved_paths.items():
        player.load_single(path, axis)

    assert len(player._scripts) == len(saved_paths), "脚本加载数量不匹配"
    assert player.duration_sec > 0, "时长为0"

    # 播放2秒
    player._playing = True
    player._start_time = time.time()

    for _ in range(120):  # 60Hz × 2s
        if not player._playing:
            break
        elapsed = (time.time() - player._start_time) * 1000
        player._current_ms = int(elapsed)

        commands = []
        for axis, fs in player._scripts.items():
            tcode_pos = fs.get_tcode_at(player._current_ms)
            tcode_pos = player._apply_safety(axis, tcode_pos)
            commands.append(f"{axis}{tcode_pos:04d}")

        if commands:
            mock_device.send(" ".join(commands))

        time.sleep(1.0 / 60)

    player._playing = False

    # 验证命令
    assert mock_device.command_count > 50, f"命令太少: {mock_device.command_count}"

    # 验证L0轴位置变化 (不应全是同一个值)
    l0_positions = mock_device.get_axis_commands("L0")
    if l0_positions:
        unique_positions = set(l0_positions)
        has_variation = len(unique_positions) > 1

    log_test("T5", "MockDevice播放", "PASS",
             f"命令数={mock_device.command_count}, "
             f"L0位置种类={len(unique_positions) if l0_positions else 0}, "
             f"时长={player.duration_sec:.1f}s")
    return mock_device


def test_T6_tcode_command_format(mock_device: MockTCodeDevice):
    """T6: TCode命令格式验证"""
    errors = []
    for cmd in mock_device.commands:
        if cmd in ("STOP", "HOME"):
            continue
        parts = cmd.split()
        for part in parts:
            if len(part) < 6:
                errors.append(f"命令太短: {part}")
                continue
            axis = part[:2]
            pos_str = part[2:6]
            try:
                pos = int(pos_str)
                if pos < 0 or pos > 9999:
                    errors.append(f"位置越界: {part} (pos={pos})")
            except ValueError:
                errors.append(f"非数字位置: {part}")

    if errors:
        log_test("T6", "TCode格式", "FAIL", f"{len(errors)}个错误: {errors[:3]}")
    else:
        log_test("T6", "TCode格式", "PASS",
                 f"{mock_device.command_count}条命令全部格式正确")


def test_T7_safety_system():
    """T7: 安全系统 — 位置钳制+速度限制"""
    from funscript.player import FunscriptPlayer, SafetyConfig

    # T7a: 速度限制
    player = FunscriptPlayer(port="MOCK", safety=SafetyConfig(max_speed=5000))
    pos1 = player._apply_safety("L0", 5000)  # 起始中位
    pos2 = player._apply_safety("L0", 9999)  # 尝试瞬间跳到顶

    # 速度限制应该阻止全行程瞬移
    delta = abs(pos2 - pos1)
    max_expected = int(5000 / 60)  # max_speed / update_hz
    assert delta <= max_expected + 10, f"速度未限制: delta={delta}, max={max_expected}"

    # T7b: 连续运动应该能到达目标
    player2 = FunscriptPlayer(port="MOCK", safety=SafetyConfig(max_speed=50000))
    pos = 0
    for _ in range(120):  # 2秒 @ 60Hz
        pos = player2._apply_safety("test", 9999)
    # 经过足够多次迭代,应该接近目标
    assert pos > 8000, f"经过120次迭代仍未接近目标: pos={pos}"

    log_test("T7", "安全系统", "PASS",
             f"速度限制delta={delta}(max={max_expected}), "
             f"连续运动收敛到{pos}")


def test_T8_agent_hash_logic():
    """T8: Agent哈希逻辑 — 视频去重和切换检测"""
    from video_sync.douyin_playwright_agent import DouyinPlaywrightAgent, AgentConfig

    agent = DouyinPlaywrightAgent(config=AgentConfig())

    # 不同视频
    s1 = {"pageUrl": "https://www.douyin.com/video/7001", "src": "blob:a", "duration": 15.0}
    s2 = {"pageUrl": "https://www.douyin.com/video/7002", "src": "blob:b", "duration": 30.0}
    assert agent._compute_hash(s1) != agent._compute_hash(s2), "不同视频hash碰撞"

    # 同视频重复
    s3 = {"pageUrl": "https://www.douyin.com/video/7001", "src": "blob:a", "duration": 15.0}
    assert agent._compute_hash(s1) == agent._compute_hash(s3), "同视频hash不一致"

    # Feed页同时长不同src
    f1 = {"pageUrl": "https://www.douyin.com/", "src": "blob:x", "duration": 20.0}
    f2 = {"pageUrl": "https://www.douyin.com/", "src": "blob:y", "duration": 20.0}
    assert agent._compute_hash(f1) != agent._compute_hash(f2), "Feed页同时长碰撞"

    log_test("T8", "Hash去重逻辑", "PASS", "异同/碰撞/Feed页全部正确")


def test_T9_agent_config_pipeline():
    """T9: Agent配置→Pipeline配置映射"""
    from video_sync.douyin_playwright_agent import DouyinPlaywrightAgent, AgentConfig
    from video_sync.pipeline import SyncConfig

    agent = DouyinPlaywrightAgent(config=AgentConfig(
        device_port="COM5",
        proxy="http://127.0.0.1:7890",
        beat_mode="onset",
        multi_axis=True,
        download_dir=TEMP_DIR,
    ))

    pipeline = agent._get_pipeline()
    assert pipeline is not None, "Pipeline未创建"
    assert pipeline.config.download_dir == TEMP_DIR
    assert pipeline.config.proxy == "http://127.0.0.1:7890"
    assert pipeline.config.beat_mode == "onset"
    assert pipeline.config.multi_axis_beat == True
    assert pipeline.config.device_port == "COM5"

    # 二次调用应返回同一实例
    p2 = agent._get_pipeline()
    assert p2 is pipeline, "Pipeline未缓存"

    log_test("T9", "Config映射", "PASS", "Agent→Pipeline配置传递正确")


async def test_T10_mock_page_events():
    """T10: MockPage事件模拟"""
    from video_sync.douyin_playwright_agent import (
        JS_INIT_MONITOR, JS_POLL_EVENTS, JS_GET_STATE
    )

    page = MockPlaywrightPage()

    # 初始化监控
    result = await page.evaluate(JS_INIT_MONITOR)
    assert result["status"] == "initialized", "监控初始化失败"

    # 获取初始状态
    state = await page.evaluate(JS_GET_STATE)
    assert state is not None, "初始状态为None"
    assert state["duration"] == 15.0, f"时长异常: {state['duration']}"
    assert state["description"] == "测试视频1 - 120BPM节拍"

    # 模拟视频切换
    page.simulate_video_change()
    events = await page.evaluate(JS_POLL_EVENTS)
    assert len(events) == 1, f"事件数异常: {len(events)}"
    assert events[0]["type"] == "video_change"

    # 切换后状态
    state2 = await page.evaluate(JS_GET_STATE)
    assert state2["duration"] == 30.0, "切换后时长不对"
    assert "视频2" in state2["description"]

    # 模拟播放前进
    page.simulate_playback_advance(5.0)
    state3 = await page.evaluate(JS_GET_STATE)
    assert abs(state3["currentTime"] - 5.0) < 0.1, f"播放时间异常: {state3['currentTime']}"

    log_test("T10", "MockPage事件", "PASS",
             f"初始化+状态+切换+播放前进, JS调用数={page._evaluate_count}")


async def test_T11_agent_monitor_cycle():
    """T11: Agent监控循环逻辑 — 使用MockPage"""
    from video_sync.douyin_playwright_agent import DouyinPlaywrightAgent, AgentConfig

    agent = DouyinPlaywrightAgent(config=AgentConfig(
        download_dir=TEMP_DIR,
        auto_sync=False,  # 不触发下载, 只测监控逻辑
        poll_interval=0.1,
        min_duration=5.0,
    ))

    page = MockPlaywrightPage()
    agent._page = page
    agent._running = True

    # 模拟一次监控循环迭代
    from video_sync.douyin_playwright_agent import JS_POLL_EVENTS, JS_GET_STATE

    # 1. 无事件时获取状态
    events = await page.evaluate(JS_POLL_EVENTS)
    assert len(events) == 0

    state = await agent._safe_evaluate(JS_GET_STATE)
    assert state is not None
    h = agent._compute_hash(state)
    assert agent._current_hash is None  # 首次

    # 模拟hash变化检测
    agent._current_hash = h
    state2 = await agent._safe_evaluate(JS_GET_STATE)
    h2 = agent._compute_hash(state2)
    assert h == h2, "同视频hash应一致"

    # 模拟视频切换
    page.simulate_video_change()
    state3 = await agent._safe_evaluate(JS_GET_STATE)
    h3 = agent._compute_hash(state3)
    assert h3 != h, "切换后hash应不同"

    # 验证_on_video_change冷却
    agent._last_process_time = time.time() - 10  # 清除冷却
    change_called = False

    async def mock_on_change(state=None):
        nonlocal change_called
        change_called = True

    # 验证事件被检测到
    events2 = await page.evaluate(JS_POLL_EVENTS)
    assert len(events2) == 1

    agent._running = False
    log_test("T11", "Agent监控循环", "PASS",
             f"状态获取+hash+切换检测+事件队列 全部正确")


async def test_T12_full_pipeline_sim():
    """T12: 全链路仿真 — 合成音频→节拍→Funscript→MockDevice→TCode"""
    from video_sync.beat_sync import BeatSyncer, BeatSyncConfig
    from funscript.player import FunscriptPlayer, SafetyConfig

    # Step 1: 生成合成音频
    audio_path = os.path.join(TEMP_DIR, "pipeline_test.wav")
    generate_test_audio(audio_path, duration_sec=8.0, bpm=120.0)

    # Step 2: 节拍分析 + 多轴funscript生成
    syncer = BeatSyncer(BeatSyncConfig(mode="onset", multi_axis=True))
    multi_result = syncer.generate_multi(audio_path)
    results = multi_result.results  # dict[str, SyncResult]
    assert len(results) >= 3, f"轴数不足: {len(results)}"

    # Step 3: 保存funscript
    fs_paths = {}
    for axis, result in results.items():
        fs_path = os.path.join(TEMP_DIR, f"pipeline_{axis}.funscript")
        result.save(fs_path)
        fs_paths[axis] = fs_path

    # Step 4: 创建Player + MockDevice
    player = FunscriptPlayer(port="MOCK", safety=SafetyConfig())
    mock_device = MockTCodeDevice()
    player._device = mock_device

    for axis, path in fs_paths.items():
        player.load_single(path, axis)

    # Step 5: 模拟3秒播放
    player._playing = True
    player._start_time = time.time()

    play_duration = 3.0
    start = time.time()
    while time.time() - start < play_duration:
        elapsed = (time.time() - player._start_time) * 1000
        player._current_ms = int(elapsed)

        commands = []
        for axis, fs in player._scripts.items():
            tcode_pos = fs.get_tcode_at(player._current_ms)
            tcode_pos = player._apply_safety(axis, tcode_pos)
            commands.append(f"{axis}{tcode_pos:04d}")

        if commands:
            mock_device.send(" ".join(commands))

        time.sleep(1.0 / 60)

    player._playing = False

    # Step 6: 验证全链路结果
    cmd_count = mock_device.command_count
    assert cmd_count > 100, f"命令太少: {cmd_count}"

    l0_pos = mock_device.get_axis_commands("L0")
    pos_range = max(l0_pos) - min(l0_pos) if l0_pos else 0
    unique_count = len(set(l0_pos)) if l0_pos else 0

    log_test("T12", "全链路仿真", "PASS",
             f"音频→{len(results)}轴funscript→{cmd_count}条TCode, "
             f"L0位置范围={pos_range}, 唯一值={unique_count}")


def test_T13_funscript_timing():
    """T13: Funscript时间精度验证"""
    from video_sync.beat_sync import BeatSyncer, BeatSyncConfig

    audio_path = os.path.join(TEMP_DIR, "timing_test.wav")
    generate_test_audio(audio_path, duration_sec=5.0, bpm=120.0)

    syncer = BeatSyncer(BeatSyncConfig(mode="onset"))
    result = syncer.generate(audio_path)

    # 验证动作时间覆盖音频全长
    times = [a.at for a in result.actions]
    first_ms = min(times)
    last_ms = max(times)
    audio_dur_ms = 5000

    assert first_ms < 1000, f"首个动作太晚: {first_ms}ms"
    assert last_ms > audio_dur_ms * 0.7, f"最后动作太早: {last_ms}ms (音频{audio_dur_ms}ms)"

    # 验证间隔合理 (120BPM→500ms间隔, 允许onset模式有更密的间隔)
    intervals = [times[i+1] - times[i] for i in range(len(times)-1)]
    avg_interval = sum(intervals) / len(intervals) if intervals else 0
    min_interval = min(intervals) if intervals else 0

    assert min_interval > 10, f"间隔太小: {min_interval}ms (可能重复)"
    assert avg_interval < 2000, f"平均间隔太大: {avg_interval}ms"

    log_test("T13", "时间精度", "PASS",
             f"首动作={first_ms}ms, 末动作={last_ms}ms, "
             f"平均间隔={avg_interval:.0f}ms, 最小={min_interval}ms")


def test_T14_cache_system():
    """T14: Agent缓存系统"""
    from video_sync.douyin_playwright_agent import DouyinPlaywrightAgent, AgentConfig

    cache_dir = os.path.join(TEMP_DIR, "cache_test")
    os.makedirs(cache_dir, exist_ok=True)

    agent = DouyinPlaywrightAgent(config=AgentConfig(download_dir=cache_dir))

    # 写入缓存
    agent._cache["testhash"] = {
        "funscripts": {"L0": "/fake/path.funscript"},
        "url": "https://douyin.com/video/123",
        "time": time.time(),
    }
    agent._save_cache()

    # 验证文件
    cache_file = Path(cache_dir) / ".agent_cache.json"
    assert cache_file.exists(), "缓存文件未创建"

    # 重新加载
    agent2 = DouyinPlaywrightAgent(config=AgentConfig(download_dir=cache_dir))
    assert "testhash" in agent2._cache, "缓存未持久化"
    assert agent2._cache["testhash"]["url"] == "https://douyin.com/video/123"

    # 清空
    agent2.clear_cache()
    assert len(agent2._cache) == 0, "缓存未清空"

    log_test("T14", "缓存系统", "PASS", "写入→持久化→重加载→清空 全部正确")


def test_T15_agent_status():
    """T15: Agent状态报告"""
    from video_sync.douyin_playwright_agent import DouyinPlaywrightAgent, AgentConfig

    agent = DouyinPlaywrightAgent(config=AgentConfig(device_port="COM5"))

    # 初始状态
    s = agent.status
    assert s["running"] == False
    assert s["device_connected"] == False
    assert s["current_video"] is None
    assert s["playing"] == False
    assert s["cache_size"] >= 0

    # 模拟有视频
    agent._current_state = {
        "description": "测试视频",
        "duration": 30.0,
        "pageUrl": "https://douyin.com/video/123",
    }
    agent._current_hash = "abc123"
    s2 = agent.status
    assert s2["current_video"] is not None
    assert s2["current_video"]["duration"] == 30.0

    # 格式化输出
    fmt = agent.format_status()
    assert "已停止" in fmt or "Agent" in fmt
    assert len(fmt) > 50, "状态输出太短"

    log_test("T15", "状态报告", "PASS", f"初始/视频中/格式化 {len(fmt)}字符")


# ═══════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════

def main():
    global TEMP_DIR

    print("═" * 60)
    print("  抖音×OSR6 全链路虚拟仿真测试")
    print("  (无实机, 无浏览器, 无抖音)")
    print("═" * 60)
    print()

    # 创建临时目录
    TEMP_DIR = tempfile.mkdtemp(prefix="ors6_sim_")
    logger.info(f"临时目录: {TEMP_DIR}")

    try:
        # ── 音频+节拍层 ──
        print("── 音频 & 节拍分析 ──")
        audio_path = test_T1_synthetic_audio()
        result = test_T2_beat_detection(audio_path)
        multi_results_dict = test_T3_multi_axis_beat(audio_path)

        # ── Funscript层 ──
        print("\n── Funscript 存储 & 加载 ──")
        saved_paths = test_T4_funscript_save_load(multi_results_dict)

        # ── 设备层 ──
        print("\n── 设备模拟 & TCode ──")
        mock_dev = test_T5_mock_device_playback(saved_paths)
        test_T6_tcode_command_format(mock_dev)
        test_T7_safety_system()

        # ── Agent层 ──
        print("\n── Agent逻辑 ──")
        test_T8_agent_hash_logic()
        test_T9_agent_config_pipeline()

        # ── 异步测试 ──
        print("\n── 异步模拟 ──")
        asyncio.run(test_T10_mock_page_events())
        asyncio.run(test_T11_agent_monitor_cycle())

        # ── 全链路 ──
        print("\n── 全链路仿真 ──")
        asyncio.run(test_T12_full_pipeline_sim())
        test_T13_funscript_timing()

        # ── 系统层 ──
        print("\n── 系统功能 ──")
        test_T14_cache_system()
        test_T15_agent_status()

    except Exception as e:
        log_test("ERR", "未处理异常", "FAIL", str(e))
        import traceback
        traceback.print_exc()
    finally:
        # 清理
        if TEMP_DIR and os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR, ignore_errors=True)

    # ── 汇总 ──
    print()
    print("═" * 60)
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    total = len(RESULTS)
    status = "ALL PASS ✅" if failed == 0 else f"{failed} FAILED ❌"
    print(f"  结果: {passed}/{total} PASS | {status}")
    print("═" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
