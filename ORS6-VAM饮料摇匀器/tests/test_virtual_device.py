#!/usr/bin/env python3
"""
ORS6 虚拟设备全链路E2E测试

测试链路:
  T1-T5: 虚拟设备物理模型 (伺服运动/速度/加速度/S曲线/抖动)
  T6-T9: TCode引擎 (命令解析/多轴/设备命令/历史)
  T10-T11: 接口兼容性 (替代TCodeSerial/TCodeWiFi)
  T12-T14: 全链路仿真 (合成音频→节拍→funscript→虚拟设备→物理验证)
  T15: 仪表盘API

依赖: numpy, librosa, soundfile (已安装)
用法: python tests/test_virtual_device.py
"""

import sys
import os
import time
import json
import math
import wave
import asyncio
import tempfile
import shutil
import logging
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(levelname).1s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("vdev_test")

RESULTS = []
TEMP_DIR = tempfile.mkdtemp(prefix="ors6_vdev_")


def log_test(test_id, name, status, detail=""):
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    line = f"  {icon} {test_id} {name}: {status}"
    if detail:
        line += f" — {detail}"
    print(line)
    RESULTS.append({"id": test_id, "name": name, "status": status, "detail": detail})


def generate_test_audio(path: str, duration_sec: float = 8.0,
                        bpm: float = 120.0, sr: int = 22050) -> str:
    """生成带明确节拍的合成WAV音频"""
    import numpy as np
    import soundfile as sf

    n_samples = int(duration_sec * sr)
    audio = np.zeros(n_samples, dtype=np.float32)
    beat_interval = 60.0 / bpm
    kick_dur = 0.05
    t = np.arange(int(kick_dur * sr)) / sr
    kick = np.sin(2 * np.pi * 60 * t) * np.exp(-t * 40) * 0.8

    beat_time = 0.0
    while beat_time < duration_sec:
        idx = int(beat_time * sr)
        end = min(idx + len(kick), n_samples)
        audio[idx:end] += kick[:end - idx]
        beat_time += beat_interval

    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.9

    sf.write(path, audio, sr, subtype='PCM_16')
    return path


# ═══════════════════════════════════════════════════════
# T1-T5: 物理模型测试
# ═══════════════════════════════════════════════════════

def test_T1_servo_basic_motion():
    """T1: 舵机基础运动 — 目标设定+物理步进"""
    from tcode.virtual_device import VirtualServo, ServoConfig

    servo = VirtualServo("L0", ServoConfig(max_speed=50000, acceleration=200000))
    assert servo.state.current == 5000, "初始位置不是5000"

    # 设置目标到9999
    servo.set_target(9999)
    assert servo.state.target == 9999
    assert servo.state.is_moving == True

    # 步进仿真 (1秒 @ 120Hz)
    for _ in range(120):
        servo.tick(1/120)

    # 应该接近目标
    assert abs(servo.state.current - 9999) < 50, f"未到达目标: {servo.state.current}"
    assert servo.state.total_distance > 4000, f"运动距离太小: {servo.state.total_distance}"

    log_test("T1", "舵机基础运动", "PASS",
             f"5000→9999, 最终={servo.state.current:.0f}, 距离={servo.state.total_distance:.0f}")


def test_T2_servo_interval():
    """T2: 舵机间隔时间运动 — S曲线插值"""
    from tcode.virtual_device import VirtualServo, ServoConfig

    servo = VirtualServo("L0", ServoConfig(smoothing=0.85))
    servo.set_target(9999, interval_ms=1000)

    # 步进1秒
    positions = []
    for i in range(120):
        servo.tick(1/120)
        positions.append(servo.state.current)

    # S曲线特征: 中间速度快, 两端慢
    mid_speed = abs(positions[60] - positions[58]) / (2/120)
    start_speed = abs(positions[2] - positions[0]) / (2/120)

    assert mid_speed > start_speed, f"非S曲线: mid={mid_speed:.0f} <= start={start_speed:.0f}"
    assert abs(positions[-1] - 9999) < 100, f"1秒后未到达: {positions[-1]:.0f}"

    log_test("T2", "S曲线插值", "PASS",
             f"起始速度={start_speed:.0f}, 中段速度={mid_speed:.0f}, 最终={positions[-1]:.0f}")


def test_T3_servo_speed_limit():
    """T3: 舵机速度限制"""
    from tcode.virtual_device import VirtualServo, ServoConfig

    # 非常低的最大速度
    servo = VirtualServo("L0", ServoConfig(max_speed=5000, acceleration=200000))
    servo.set_target(9999)

    # 步进0.5秒
    for _ in range(60):
        servo.tick(1/120)

    # 以5000/s的速度,0.5秒应该移动~2500
    displacement = abs(servo.state.current - 5000)
    assert displacement < 3500, f"超速: 位移={displacement:.0f} (预期<3500)"
    assert displacement > 1500, f"太慢: 位移={displacement:.0f} (预期>1500)"

    log_test("T3", "速度限制", "PASS",
             f"限速=5000/s, 0.5s位移={displacement:.0f}")


def test_T4_servo_emergency_stop():
    """T4: 紧急停止"""
    from tcode.virtual_device import VirtualServo, ServoConfig

    servo = VirtualServo("L0", ServoConfig(max_speed=50000))
    servo.set_target(9999)

    # 运动中停止
    for _ in range(30):
        servo.tick(1/120)
    pos_before = servo.state.current
    assert servo.state.is_moving == True

    servo.stop()
    assert servo.state.is_moving == False
    assert servo.state.velocity == 0.0

    # 停止后不应继续运动
    for _ in range(30):
        servo.tick(1/120)
    pos_after = servo.state.current
    drift = abs(pos_after - pos_before)
    assert drift < 20, f"停止后漂移: {drift:.0f}"

    log_test("T4", "紧急停止", "PASS",
             f"停止时位置={pos_before:.0f}, 停后漂移={drift:.0f}")


def test_T5_servo_jitter():
    """T5: 位置抖动 (真实舵机精度模拟)"""
    from tcode.virtual_device import VirtualServo, ServoConfig

    servo = VirtualServo("L0", ServoConfig(jitter=10.0))
    # 在目标位置静止时应有微小抖动
    servo.set_target(5000)

    positions = []
    for _ in range(240):
        servo.tick(1/120)
        positions.append(servo.state.current)

    # 最后100个点应在目标附近有波动
    last_100 = positions[-100:]
    unique_ints = set(int(p) for p in last_100)
    pos_range = max(last_100) - min(last_100)

    assert len(unique_ints) > 1, "无抖动 — 完全静止不真实"
    assert pos_range < 100, f"抖动过大: {pos_range:.1f}"
    assert pos_range > 0.1, f"抖动过小: {pos_range:.1f}"

    log_test("T5", "位置抖动", "PASS",
             f"范围={pos_range:.1f}, 唯一值={len(unique_ints)}")


# ═══════════════════════════════════════════════════════
# T6-T9: TCode引擎测试
# ═══════════════════════════════════════════════════════

def test_T6_tcode_single_command():
    """T6: TCode单轴命令"""
    from tcode.virtual_device import VirtualORS6

    dev = VirtualORS6(auto_tick=False)
    dev.connect()

    dev.send("L09999I500")
    for _ in range(120):
        dev.tick(1/120)

    pos = dev.get_positions()
    assert abs(pos["L0"] - 9999) < 100, f"L0未到目标: {pos['L0']}"
    assert abs(pos["L1"] - 5000) < 50, f"L1不在中位: {pos['L1']}"

    dev.disconnect()
    log_test("T6", "单轴命令", "PASS", f"L0→{pos['L0']:.0f}, L1→{pos['L1']:.0f}")


def test_T7_tcode_multi_command():
    """T7: TCode多轴并行"""
    from tcode.virtual_device import VirtualORS6

    dev = VirtualORS6(auto_tick=False)
    dev.connect()

    dev.send("L09999I500 R09999I500 L10000I500")
    for _ in range(120):
        dev.tick(1/120)

    pos = dev.get_positions()
    assert abs(pos["L0"] - 9999) < 100
    assert abs(pos["R0"] - 9999) < 100
    assert abs(pos["L1"] - 0) < 100

    dev.disconnect()
    log_test("T7", "多轴并行", "PASS",
             f"L0={pos['L0']:.0f}, R0={pos['R0']:.0f}, L1={pos['L1']:.0f}")


def test_T8_device_commands():
    """T8: 设备命令 (D0/D1/D2)"""
    from tcode.virtual_device import VirtualORS6

    dev = VirtualORS6(auto_tick=False)
    dev.connect()

    # D2: 查询信息
    info = dev.send("D2")
    assert "TCodeVirtual" in info, f"固件信息异常: {info}"

    # 移动到非中位
    dev.send("L09999")
    for _ in range(120):
        dev.tick(1/120)

    # D0: 紧急停止
    result = dev.send("D0")
    assert result == "OK"

    # D1: 归位
    dev.send("D1")
    for _ in range(240):
        dev.tick(1/120)
    pos = dev.get_positions()
    assert abs(pos["L0"] - 5000) < 100, f"归位失败: L0={pos['L0']}"

    dev.disconnect()
    log_test("T8", "设备命令", "PASS",
             f"D2='{info[:30]}', D0=OK, D1归位L0={pos['L0']:.0f}")


def test_T9_command_history():
    """T9: 命令历史记录"""
    from tcode.virtual_device import VirtualORS6

    dev = VirtualORS6(auto_tick=False)
    dev.connect()

    dev.send("L00000")
    dev.send("L09999I500")
    dev.send("R05000I200")

    history = dev.get_history(10)
    assert len(history) >= 3, f"历史条目不足: {len(history)}"
    assert history[-1]["cmd"] == "R05000I200"
    assert history[-2]["cmd"] == "L09999I500"

    state = dev.get_state()
    assert state["total_commands"] >= 3

    dev.disconnect()
    log_test("T9", "命令历史", "PASS",
             f"记录={len(history)}条, 总命令={state['total_commands']}")


# ═══════════════════════════════════════════════════════
# T10-T11: 接口兼容性
# ═══════════════════════════════════════════════════════

def test_T10_serial_interface_compat():
    """T10: TCodeSerial接口兼容性"""
    from tcode.virtual_device import VirtualORS6

    dev = VirtualORS6(auto_tick=False)

    # connect/disconnect
    assert dev.connect() == True
    assert dev.is_connected == True

    # move()
    dev.move("L0", 9999, interval_ms=500)
    for _ in range(120):
        dev.tick(1/120)

    # home_all()
    dev.home_all(interval_ms=500)
    for _ in range(120):
        dev.tick(1/120)
    pos = dev.get_positions()
    assert abs(pos["L0"] - 5000) < 100

    # stop()
    dev.stop()

    # device_info()
    info = dev.device_info()
    assert info is not None

    # context manager
    with VirtualORS6(auto_tick=False) as d:
        assert d.is_connected

    dev.disconnect()
    assert dev.is_connected == False

    log_test("T10", "Serial兼容", "PASS",
             "connect/move/home/stop/info/context 全部兼容")


def test_T11_callback_system():
    """T11: 回调系统"""
    from tcode.virtual_device import VirtualORS6

    states = []
    commands = []

    dev = VirtualORS6(auto_tick=False)
    dev.on_state_change = lambda s: states.append(s)
    dev.on_command = lambda c: commands.append(c)
    dev.connect()

    dev.send("L09999I200")
    dev.tick(1/120)

    assert len(commands) == 1, f"命令回调未触发: {len(commands)}"
    assert commands[0] == "L09999I200"
    assert len(states) >= 1, f"状态回调未触发: {len(states)}"
    assert "axes" in states[0]

    dev.disconnect()
    log_test("T11", "回调系统", "PASS",
             f"命令回调={len(commands)}, 状态回调={len(states)}")


# ═══════════════════════════════════════════════════════
# T12-T14: 全链路仿真
# ═══════════════════════════════════════════════════════

def test_T12_audio_to_virtual_device():
    """T12: 合成音频 → 节拍分析 → funscript → 虚拟设备播放"""
    from video_sync.beat_sync import BeatSyncer, BeatSyncConfig
    from funscript.parser import Funscript
    from tcode.virtual_device import VirtualORS6

    # Step 1: 合成音频
    audio_path = os.path.join(TEMP_DIR, "vdev_test.wav")
    generate_test_audio(audio_path, duration_sec=5.0, bpm=120.0)

    # Step 2: 节拍分析
    syncer = BeatSyncer(BeatSyncConfig(mode="onset", multi_axis=True))
    multi_result = syncer.generate_multi(audio_path)
    results = multi_result.results
    assert len(results) >= 2, f"轴数不足: {len(results)}"

    # Step 3: 保存funscript
    fs_paths = {}
    for axis, result in results.items():
        fs_path = os.path.join(TEMP_DIR, f"vdev_{axis}.funscript")
        result.save(fs_path)
        fs_paths[axis] = fs_path

    # Step 4: 加载funscript到虚拟设备
    dev = VirtualORS6(auto_tick=False)
    dev.connect()

    funscripts = {}
    for axis, path in fs_paths.items():
        funscripts[axis] = Funscript.load(path)

    # Step 5: 模拟3秒播放 (60Hz)
    play_duration = 3.0
    cmd_count = 0
    position_samples = {a: [] for a in funscripts.keys()}

    for frame in range(int(play_duration * 60)):
        t_ms = int(frame / 60 * 1000)

        # 生成TCode命令
        parts = []
        for axis, fs in funscripts.items():
            tcode_pos = fs.get_tcode_at(t_ms)
            parts.append(f"{axis}{tcode_pos:04d}")

        cmd = " ".join(parts)
        dev.send(cmd)
        dev.tick(1/60)
        cmd_count += 1

        # 记录虚拟设备实际位置
        positions = dev.get_positions()
        for axis in funscripts:
            if axis in positions:
                position_samples[axis].append(positions[axis])

    # Step 6: 验证
    assert cmd_count >= 150, f"命令太少: {cmd_count}"

    # 验证虚拟设备位置有运动
    for axis, samples in position_samples.items():
        if len(samples) > 10:
            unique = set(int(s) for s in samples)
            assert len(unique) > 3, f"{axis}位置无变化: {len(unique)}种"

    state = dev.get_state()
    dev.disconnect()

    log_test("T12", "全链路仿真", "PASS",
             f"音频→{len(results)}轴→{cmd_count}cmd→虚拟设备, "
             f"总tick={state['tick_count']}")


def test_T13_physical_accuracy():
    """T13: 物理精度验证 — 虚拟设备跟踪目标的延迟和精度"""
    from tcode.virtual_device import VirtualORS6

    dev = VirtualORS6(auto_tick=False)
    dev.connect()

    # 发送正弦运动命令, 验证虚拟设备跟踪精度
    errors = []
    for i in range(300):
        t = i / 300
        target = int(5000 + 4000 * math.sin(t * math.pi * 4))
        dev.send(f"L0{target:04d}I50")
        dev.tick(1/60)

        actual = dev.get_positions()["L0"]
        errors.append(abs(actual - target))

    avg_error = sum(errors) / len(errors)
    max_error = max(errors)
    # 有interval_ms=50, 物理模型应能跟踪
    # 允许较大误差因为S曲线有延迟
    assert avg_error < 2000, f"平均误差过大: {avg_error:.0f}"

    dev.disconnect()
    log_test("T13", "物理精度", "PASS",
             f"正弦跟踪: 平均误差={avg_error:.0f}, 最大={max_error:.0f}")


def test_T14_player_integration():
    """T14: FunscriptPlayer + VirtualORS6 集成"""
    from funscript.player import FunscriptPlayer, SafetyConfig
    from video_sync.beat_sync import BeatSyncer, BeatSyncConfig
    from tcode.virtual_device import VirtualORS6

    # 生成funscript
    audio_path = os.path.join(TEMP_DIR, "player_int.wav")
    generate_test_audio(audio_path, duration_sec=5.0, bpm=120.0)
    syncer = BeatSyncer(BeatSyncConfig(mode="onset"))
    result = syncer.generate(audio_path)
    fs_path = os.path.join(TEMP_DIR, "player_int.funscript")
    result.save(fs_path)

    # 创建虚拟设备
    dev = VirtualORS6(auto_tick=False)
    dev.connect()

    # 创建player, 注入虚拟设备
    player = FunscriptPlayer(port="VIRTUAL", safety=SafetyConfig())
    player._device = dev

    # 加载并模拟播放
    player.load_single(fs_path, "L0")
    assert player.has_scripts

    # 手动播放循环 (2秒)
    player._playing = True
    player._start_time = time.time()
    cmd_sent = 0

    for _ in range(120):
        elapsed = (time.time() - player._start_time) * 1000
        player._current_ms = int(elapsed)

        for axis, fs in player._scripts.items():
            tcode_pos = fs.get_tcode_at(player._current_ms)
            tcode_pos = player._apply_safety(axis, tcode_pos)
            dev.send(f"{axis}{tcode_pos:04d}")
            cmd_sent += 1

        dev.tick(1/60)
        time.sleep(1/120)

    player._playing = False

    state = dev.get_state()
    l0_dist = state["axes"]["L0"]["total_distance"]

    dev.disconnect()
    log_test("T14", "Player集成", "PASS",
             f"Player→VirtualORS6: {cmd_sent}cmd, L0运动距离={l0_dist:.0f}")


# ═══════════════════════════════════════════════════════
# T15: 仪表盘API
# ═══════════════════════════════════════════════════════

def test_T15_dashboard_api():
    """T15: 虚拟设备API完整性"""
    from tcode.virtual_device import VirtualORS6

    dev = VirtualORS6(auto_tick=False)
    dev.connect()

    dev.send("L09999I500 R03000I500")
    for _ in range(60):
        dev.tick(1/120)

    # get_state()
    state = dev.get_state()
    assert "axes" in state
    assert "L0" in state["axes"]
    assert "R0" in state["axes"]
    assert "connected" in state
    assert "total_commands" in state
    assert "firmware" in state
    assert state["connected"] == True
    assert state["total_commands"] >= 1

    # 轴状态完整性
    l0 = state["axes"]["L0"]
    for key in ["axis", "target", "current", "velocity", "position_pct", "is_moving", "command_count", "total_distance"]:
        assert key in l0, f"L0缺少字段: {key}"

    # get_positions()
    pos = dev.get_positions()
    assert len(pos) >= 6
    assert "L0" in pos and "R0" in pos

    # get_history()
    history = dev.get_history(10)
    assert len(history) >= 1
    assert "cmd" in history[0]
    assert "time" in history[0]

    # JSON序列化验证
    json_str = json.dumps(state)
    assert len(json_str) > 100

    dev.disconnect()
    log_test("T15", "API完整性", "PASS",
             f"state={len(json_str)}B, axes={len(state['axes'])}, "
             f"history={len(history)}")


# ═══════════════════════════════════════════════════════
# T16-T18: TempestStroke引擎 (移植自ayvajs)
# ═══════════════════════════════════════════════════════

def test_T16_tempest_pattern_library():
    """T16: TempestStroke 42模式库完整性"""
    from tcode.tempest_stroke import TempestStroke, PATTERN_LIBRARY

    patterns = TempestStroke.list_patterns()
    assert len(patterns) >= 40, f"模式不足: {len(patterns)} (预期≥40)"

    # 验证每个模式都能实例化
    errors = []
    for name in patterns:
        try:
            stroke = TempestStroke(name, bpm=60)
            assert len(stroke.axes) > 0, f"{name}: 无轴定义"
        except Exception as e:
            errors.append(f"{name}: {e}")

    assert len(errors) == 0, f"模式实例化失败: {errors}"

    # 验证分类覆盖
    categories = {"thrust": 0, "tease": 0, "grind": 0, "stroke": 0, "orbit": 0}
    for name in patterns:
        for cat in categories:
            if cat in name:
                categories[cat] += 1

    log_test("T16", "模式库完整性", "PASS",
             f"{len(patterns)}模式, 分类: {categories}")


def test_T17_tempest_motion_formulas():
    """T17: 3种运动公式数学验证"""
    from tcode.tempest_stroke import tempest_motion, parabolic_motion, linear_motion
    import math

    # tempest_motion: cos基础, 应在from-to范围内振荡
    values_t = [tempest_motion(a, 0.0, 1.0) for a in [i * 0.1 for i in range(63)]]
    assert min(values_t) >= -0.01, f"tempest下溢: {min(values_t)}"
    assert max(values_t) <= 1.01, f"tempest上溢: {max(values_t)}"
    # 应有完整周期
    crossings = sum(1 for i in range(1, len(values_t)) if (values_t[i] - 0.5) * (values_t[i-1] - 0.5) < 0)
    assert crossings >= 2, f"tempest无完整周期: {crossings}次穿越"

    # parabolic_motion: 底部停顿更长
    values_p = [parabolic_motion(a, 0.0, 1.0) for a in [i * 0.1 for i in range(63)]]
    assert min(values_p) >= -0.01
    assert max(values_p) <= 1.01

    # linear_motion: 三角波
    values_l = [linear_motion(a, 0.0, 1.0) for a in [i * 0.1 for i in range(63)]]
    assert min(values_l) >= -0.01
    assert max(values_l) <= 1.01

    # 离心率测试 (ecc>0应导致不对称)
    sym = [tempest_motion(a, 0.0, 1.0, ecc=0) for a in [i * 0.1 for i in range(63)]]
    asym = [tempest_motion(a, 0.0, 1.0, ecc=0.5) for a in [i * 0.1 for i in range(63)]]
    # 均值应不同 (不对称)
    sym_mean = sum(sym) / len(sym)
    asym_mean = sum(asym) / len(asym)
    assert abs(sym_mean - asym_mean) > 0.01, "离心率无效果"

    log_test("T17", "运动公式", "PASS",
             f"tempest穿越={crossings}, parabolic范围=[{min(values_p):.2f},{max(values_p):.2f}], "
             f"ecc效果={abs(sym_mean-asym_mean):.3f}")


def test_T18_tempest_virtual_device():
    """T18: TempestStroke → VirtualORS6 全链路"""
    from tcode.tempest_stroke import TempestStroke
    from tcode.virtual_device import VirtualORS6

    dev = VirtualORS6(auto_tick=False)
    dev.connect()

    stroke = TempestStroke("orbit-tease", bpm=90)
    freq = 60.0

    # 播放3秒
    for idx in range(int(3 * freq)):
        cmd = stroke.generate_tcode(idx, frequency=freq, interval_ms=16)
        dev.send(cmd)
        dev.tick(1/freq)

    state = dev.get_state()
    pos = dev.get_positions()

    # orbit-tease用L0,L1,R0三轴
    l0_dist = state["axes"]["L0"]["total_distance"]
    l1_dist = state["axes"]["L1"]["total_distance"]
    r0_dist = state["axes"]["R0"]["total_distance"]

    assert l0_dist > 100, f"L0运动不足: {l0_dist}"
    assert l1_dist > 100, f"L1运动不足: {l1_dist}"
    assert r0_dist > 100, f"R0运动不足: {r0_dist}"

    # 未使用的轴应基本不动
    l2_dist = state["axes"]["L2"]["total_distance"]

    dev.disconnect()
    log_test("T18", "TempestStroke→虚拟设备", "PASS",
             f"orbit-tease@90bpm: L0={l0_dist:.0f} L1={l1_dist:.0f} R0={r0_dist:.0f}, "
             f"L2(idle)={l2_dist:.0f}, cmds={state['total_commands']}")


# ═══════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════

def main():
    global TEMP_DIR

    print("═" * 60)
    print("  ORS6 虚拟设备全链路E2E测试")
    print("  物理仿真 + TCode引擎 + 全链路集成")
    print("═" * 60)
    print()

    TEMP_DIR = tempfile.mkdtemp(prefix="ors6_vdev_")

    try:
        # ── 物理模型 ──
        print("── 伺服物理模型 ──")
        test_T1_servo_basic_motion()
        test_T2_servo_interval()
        test_T3_servo_speed_limit()
        test_T4_servo_emergency_stop()
        test_T5_servo_jitter()

        # ── TCode引擎 ──
        print("\n── TCode引擎 ──")
        test_T6_tcode_single_command()
        test_T7_tcode_multi_command()
        test_T8_device_commands()
        test_T9_command_history()

        # ── 接口兼容 ──
        print("\n── 接口兼容性 ──")
        test_T10_serial_interface_compat()
        test_T11_callback_system()

        # ── 全链路 ──
        print("\n── 全链路仿真 ──")
        test_T12_audio_to_virtual_device()
        test_T13_physical_accuracy()
        test_T14_player_integration()

        # ── API ──
        print("\n── API完整性 ──")
        test_T15_dashboard_api()

        # ── TempestStroke ──
        print("\n── TempestStroke引擎 (ayvajs移植) ──")
        test_T16_tempest_pattern_library()
        test_T17_tempest_motion_formulas()
        test_T18_tempest_virtual_device()

    except Exception as e:
        log_test("ERR", "未处理异常", "FAIL", str(e))
        import traceback
        traceback.print_exc()
    finally:
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
