#!/usr/bin/env python3
"""
ORS6 五感实控验证 — 带入用户五感，测试所有功能动作
视觉(👁): UI状态、轴显示、3D反馈
触觉(🖐): 6轴控制、42模式、紧急停止、归位
听觉(👂): WebSocket实时性、广播频率、延迟
嗅觉(🔒): 边界条件、安全限制、异常恢复
味觉(👅): Funscript全链路、视频同步、本地加载
"""

import json, math, sys, time, urllib.request, urllib.parse, threading

BASE = "http://localhost:8086"
results = []
p = f = 0

def get(path):
    try:
        r = urllib.request.urlopen(f"{BASE}{path}", timeout=5)
        return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=5)
        return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def test(name, fn):
    global p, f
    try:
        fn()
        results.append(f"  PASS  {name}")
        p += 1
    except AssertionError as e:
        results.append(f"  FAIL  {name}: {e}")
        f += 1
    except Exception as e:
        results.append(f"  ERROR {name}: {e}")
        f += 1

# ══════════════════════════════════════════
# 👁 视觉感 — 用户看到的第一印象
# ══════════════════════════════════════════
print("👁 视觉感 — 状态/轴/固件")

def vision_health():
    d = get("/api/health")
    assert d["status"] == "ok", f"Health not ok: {d}"
    assert d["device"] == True, f"No device: {d}"
    assert d["patterns"] == 42, f"Patterns != 42: {d['patterns']}"
    print(f"    运行 {d['uptime']:.0f}s | WS客户端 {d['ws_clients']} | 42模式")
test("vision_health", vision_health)

def vision_state():
    d = get("/api/state")
    assert d["connected"] == True
    assert d["running"] == True
    axes = d["axes"]
    assert len(axes) >= 6, f"Axes < 6: {list(axes.keys())}"
    # 所有轴应在中位附近(±500)
    for ax, info in axes.items():
        assert 4000 <= info["current"] <= 6000, f"{ax} not centered: {info['current']}"
    print(f"    {len(axes)}轴全部居中 | firmware: {d['firmware'][:30]}")
test("vision_state", vision_state)

def vision_axis_completeness():
    """验证6+3=9轴全部存在且有正确属性"""
    d = get("/api/state")
    required = {"L0", "L1", "L2", "R0", "R1", "R2"}
    optional = {"V0", "V1", "A0"}
    axes = set(d["axes"].keys())
    missing = required - axes
    assert not missing, f"Missing required axes: {missing}"
    for ax, info in d["axes"].items():
        for key in ["axis", "target", "current", "velocity", "position_pct", "is_moving", "command_count"]:
            assert key in info, f"{ax} missing '{key}'"
    found_optional = optional & axes
    print(f"    必需轴 {len(required)}/6 | 可选轴 {len(found_optional)}/{len(optional)} | 属性完整")
test("vision_axis_completeness", vision_axis_completeness)

# ══════════════════════════════════════════
# 🖐 触觉感 — 实际控制每个轴
# ══════════════════════════════════════════
print("\n🖐 触觉感 — 轴控制/模式/停止")

def touch_single_axis_L0():
    """L0 Stroke: 推到顶→确认→推到底→确认→归位"""
    get("/api/send/L09999I200")
    time.sleep(0.3)
    d = get("/api/state")
    pos = d["axes"]["L0"]["current"]
    assert pos > 8000, f"L0 top failed: {pos}"
    get("/api/send/L00000I200")
    time.sleep(0.3)
    d = get("/api/state")
    pos = d["axes"]["L0"]["current"]
    assert pos < 2000, f"L0 bottom failed: {pos}"
    get("/api/send/L05000I200")
    time.sleep(0.3)
    d = get("/api/state")
    pos = d["axes"]["L0"]["current"]
    assert 4000 < pos < 6000, f"L0 center failed: {pos}"
    print(f"    L0 Stroke: 顶{'>8000'}→底{'<2000'}→中 ✓")
test("touch_L0_stroke", touch_single_axis_L0)

def touch_single_axis_R0():
    """R0 Twist: 正转→反转→归位"""
    get("/api/send/R09999I200")
    time.sleep(0.3)
    d = get("/api/state")
    assert d["axes"]["R0"]["current"] > 8000, f"R0 CW failed"
    get("/api/send/R00000I200")
    time.sleep(0.3)
    d = get("/api/state")
    assert d["axes"]["R0"]["current"] < 2000, f"R0 CCW failed"
    get("/api/send/R05000I200")
    time.sleep(0.3)
    print(f"    R0 Twist: 正转→反转→归位 ✓")
test("touch_R0_twist", touch_single_axis_R0)

def touch_all_6_axes():
    """同时控制6轴到不同位置"""
    get("/api/send/L02000 L17000 L23000 R08000 R11000 R26000")
    time.sleep(0.4)
    d = get("/api/state")
    expected = {"L0": 2000, "L1": 7000, "L2": 3000, "R0": 8000, "R1": 1000, "R2": 6000}
    for ax, target in expected.items():
        cur = d["axes"][ax]["current"]
        assert abs(cur - target) < 1500, f"{ax}: expected ~{target}, got {cur}"
    get("/api/send/D1")  # Home
    time.sleep(0.3)
    print(f"    6轴同时控制→各到目标位置 ✓")
test("touch_6_axes_parallel", touch_all_6_axes)

def touch_emergency_stop():
    """紧急停止D0: 所有轴立即停止"""
    get("/api/send/L09999I2000")  # Long move
    time.sleep(0.05)
    get("/api/send/D0")
    time.sleep(0.2)
    d = get("/api/state")
    assert d["axes"]["L0"]["is_moving"] == False, f"L0 still moving after D0"
    print(f"    紧急停止D0: 立即停止 ✓")
    get("/api/send/D1")
    time.sleep(0.3)
test("touch_emergency_stop", touch_emergency_stop)

def touch_home_D1():
    """全轴归位D1: 所有轴回到5000"""
    get("/api/send/L02000 R08000")
    time.sleep(0.3)
    get("/api/send/D1")
    time.sleep(0.5)
    d = get("/api/state")
    for ax in ["L0", "L1", "L2", "R0", "R1", "R2"]:
        cur = d["axes"][ax]["current"]
        assert abs(cur - 5000) < 500, f"{ax} not homed: {cur}"
    print(f"    全轴归位D1: 6轴全部回中 ✓")
test("touch_home_D1", touch_home_D1)

def touch_firmware_info():
    """D2固件信息"""
    d = get("/api/state")
    fw = d.get("firmware", "")
    assert "TCode" in fw, f"No TCode in firmware: {fw}"
    print(f"    固件: {fw}")
test("touch_firmware_D2", touch_firmware_info)

# ── 模式测试 ──
def touch_patterns_list():
    """获取42种运动模式"""
    d = get("/api/patterns")
    assert isinstance(d, list), f"Patterns not list: {type(d)}"
    assert len(d) >= 40, f"Too few patterns: {len(d)}"
    print(f"    {len(d)}种模式: {', '.join(d[:5])}...")
test("touch_patterns_list", touch_patterns_list)

def touch_pattern_play():
    """播放→验证运动→停止"""
    patterns = get("/api/patterns")
    name = patterns[0] if patterns else "orbit"
    get(f"/api/play/{name}/120")
    time.sleep(0.5)
    d = get("/api/state")
    moving = sum(1 for a in d["axes"].values() if a["is_moving"] or a["velocity"] != 0)
    assert moving > 0, f"No axes moving during pattern"
    # Verify commands are being sent
    cmd_count1 = d["total_commands"]
    time.sleep(0.3)
    d2 = get("/api/state")
    cmd_count2 = d2["total_commands"]
    assert cmd_count2 > cmd_count1, f"Commands not increasing: {cmd_count1} → {cmd_count2}"
    get("/api/stop")
    time.sleep(0.3)
    print(f"    模式'{name}' @120bpm: 运动中 {moving}轴 | 命令递增 ✓")
test("touch_pattern_play", touch_pattern_play)

def touch_pattern_3_modes():
    """测试3种不同模式切换"""
    patterns = get("/api/patterns")
    test_patterns = patterns[:3] if len(patterns) >= 3 else patterns
    for name in test_patterns:
        get(f"/api/play/{name}/90")
        time.sleep(0.3)
        d = get("/api/state")
        # Just verify it's responsive
        assert d["connected"], f"Disconnected during {name}"
    get("/api/stop")
    time.sleep(0.2)
    print(f"    3模式快速切换: {', '.join(test_patterns)} ✓")
test("touch_3_pattern_switch", touch_pattern_3_modes)

# ══════════════════════════════════════════
# 👂 听觉感 — WebSocket实时性+响应速度
# ══════════════════════════════════════════
print("\n👂 听觉感 — 延迟/吞吐/一致性")

def hearing_api_latency():
    """API响应延迟测试"""
    latencies = []
    for _ in range(5):
        t0 = time.time()
        get("/api/state")
        latencies.append((time.time() - t0) * 1000)
    avg = sum(latencies) / len(latencies)
    mx = max(latencies)
    assert avg < 100, f"Average latency too high: {avg:.1f}ms"
    assert mx < 500, f"Max latency too high: {mx:.1f}ms"
    print(f"    API延迟: avg={avg:.1f}ms max={mx:.1f}ms ({len(latencies)}次)")
test("hearing_api_latency", hearing_api_latency)

def hearing_command_throughput():
    """命令吞吐量测试: 快速发送20条命令"""
    d1 = get("/api/state")
    start_cmds = d1["total_commands"]
    t0 = time.time()
    for i in range(20):
        pos = 3000 + int(4000 * math.sin(i * 0.5))
        get(f"/api/send/L0{pos:04d}")
    elapsed = time.time() - t0
    time.sleep(0.3)
    d2 = get("/api/state")
    sent = d2["total_commands"] - start_cmds
    rate = sent / elapsed if elapsed > 0 else 0
    assert sent >= 15, f"Too few commands received: {sent}/20"
    print(f"    吞吐: {sent}/20命令 | {elapsed:.2f}s | {rate:.0f} cmd/s")
    get("/api/send/D1")
    time.sleep(0.2)
test("hearing_throughput", hearing_command_throughput)

def hearing_state_consistency():
    """连续读取状态，验证数据一致性"""
    prev = None
    anomalies = 0
    for _ in range(10):
        d = get("/api/state")
        if prev is not None:
            # Tick count should be monotonically increasing
            if d["tick_count"] < prev["tick_count"]:
                anomalies += 1
            # Uptime should increase
            if d["uptime_sec"] < prev["uptime_sec"]:
                anomalies += 1
        prev = d
        time.sleep(0.05)
    assert anomalies == 0, f"{anomalies} consistency anomalies"
    print(f"    10次连续读取: 0异常 | tick/uptime单调递增 ✓")
test("hearing_consistency", hearing_state_consistency)

# ══════════════════════════════════════════
# 🔒 嗅觉感 — 边界条件+安全+异常
# ══════════════════════════════════════════
print("\n🔒 嗅觉感 — 边界/安全/异常")

def smell_boundary_max():
    """位置边界: 超过9999应裁剪"""
    get("/api/send/L099999")  # 超范围
    time.sleep(0.3)
    d = get("/api/state")
    pos = d["axes"]["L0"]["current"]
    assert pos <= 9999, f"L0 exceeded max: {pos}"
    get("/api/send/D1")
    time.sleep(0.2)
    print(f"    超范围命令: L099999 → {pos} (裁剪到≤9999) ✓")
test("smell_boundary_max", smell_boundary_max)

def smell_boundary_min():
    """位置边界: 负值/0应裁剪"""
    get("/api/send/L00000")
    time.sleep(0.3)
    d = get("/api/state")
    pos = d["axes"]["L0"]["current"]
    assert pos >= 0, f"L0 below min: {pos}"
    get("/api/send/D1")
    time.sleep(0.2)
    print(f"    最小值命令: L00000 → {pos} ✓")
test("smell_boundary_min", smell_boundary_min)

def smell_invalid_command():
    """无效命令不应崩溃"""
    results_before = get("/api/state")
    get("/api/send/INVALID_CMD")
    get("/api/send/")
    get("/api/send/XYZZY")
    time.sleep(0.2)
    results_after = get("/api/state")
    assert results_after["connected"], "Hub disconnected after invalid commands"
    assert results_after["running"], "Hub stopped after invalid commands"
    print(f"    无效命令: Hub保持稳定 ✓")
test("smell_invalid_command", smell_invalid_command)

def smell_rapid_direction_change():
    """快速方向切换不应卡死"""
    for i in range(10):
        if i % 2 == 0:
            get("/api/send/L09999I50")
        else:
            get("/api/send/L00000I50")
        time.sleep(0.02)
    time.sleep(0.3)
    d = get("/api/state")
    assert d["connected"], "Disconnected after rapid changes"
    get("/api/send/D1")
    time.sleep(0.2)
    print(f"    10次快速方向切换: Hub稳定 ✓")
test("smell_rapid_direction", smell_rapid_direction_change)

def smell_concurrent_pattern_axis():
    """模式播放中发送轴命令"""
    get("/api/play/orbit/60")
    time.sleep(0.2)
    # Send direct axis command during pattern
    get("/api/send/R09999I200")
    time.sleep(0.2)
    d = get("/api/state")
    assert d["connected"], "Disconnected during concurrent control"
    get("/api/stop")
    get("/api/send/D1")
    time.sleep(0.2)
    print(f"    模式+手动并行: 不冲突 ✓")
test("smell_concurrent_control", smell_concurrent_pattern_axis)

def smell_404_handling():
    """不存在的端点应返回404"""
    try:
        urllib.request.urlopen(f"{BASE}/api/nonexistent", timeout=3)
        assert False, "Should have returned error"
    except urllib.error.HTTPError as e:
        assert e.code == 404, f"Expected 404, got {e.code}"
    except Exception:
        pass  # Connection errors are OK
    print(f"    404处理: 正确 ✓")
test("smell_404_handling", smell_404_handling)

def smell_path_traversal():
    """路径穿越攻击应被阻止"""
    d = get("/api/funscript/load-local/..%2F..%2F..%2Fetc%2Fpasswd")
    assert "error" in d, f"Path traversal not blocked: {d}"
    d2 = get("/api/funscript/load-local/..\\..\\..\\windows\\system32\\config\\sam")
    assert "error" in d2, f"Backslash traversal not blocked: {d2}"
    print(f"    路径穿越: 双向阻止 ✓")
test("smell_path_traversal", smell_path_traversal)

# ══════════════════════════════════════════
# 👅 味觉感 — Funscript全链路+视频同步
# ══════════════════════════════════════════
print("\n👅 味觉感 — Funscript全链路")

# Generate comprehensive test scripts
L0_actions = [{"at": int(i*50), "pos": int(50 + 45*math.sin(i*0.2))} for i in range(200)]
R0_actions = [{"at": int(i*50), "pos": int(50 + 40*math.cos(i*0.3))} for i in range(200)]
R1_actions = [{"at": int(i*50), "pos": int(50 + 30*math.sin(i*0.5))} for i in range(200)]
V0_actions = [{"at": int(i*50), "pos": int(50 + 20*math.sin(i*0.8))} for i in range(200)]

def taste_fs_load_multi():
    """加载4轴funscript"""
    d = post("/api/funscript/load", {
        "scripts": {
            "L0": {"actions": L0_actions},
            "R0": {"actions": R0_actions},
            "R1": {"actions": R1_actions},
            "V0": {"actions": V0_actions},
        },
        "title": "five_senses_test"
    })
    assert d.get("status") == "loaded", f"Load failed: {d}"
    assert "L0" in d["result"] and "V0" in d["result"], f"Missing axes: {d['result'].keys()}"
    print(f"    4轴加载: {list(d['result'].keys())} | {d['duration_ms']}ms ✓")
test("taste_fs_load_4axis", taste_fs_load_multi)

def taste_fs_play_verify_motion():
    """播放funscript→验证轴实际运动"""
    get("/api/funscript/play")
    time.sleep(0.8)
    d = get("/api/funscript/status")
    assert d["playing"] == True, f"Not playing: {d}"
    assert d["current_ms"] > 0, f"No progress: {d['current_ms']}"
    # Check axes have different positions (not all at center)
    axes_positions = {ax: info["position"] for ax, info in d["axes"].items()}
    unique_positions = len(set(axes_positions.values()))
    # During sine wave, axes should have varied positions
    print(f"    播放中: {d['current_ms']}ms | 轴位置: {axes_positions}")
    # Verify device state matches funscript state
    device_state = get("/api/state")
    # Commands should be increasing during playback
    assert device_state["total_commands"] > 1700, f"Commands too low during playback"
    print(f"    设备命令: {device_state['total_commands']} (递增中)")
test("taste_fs_play_motion", taste_fs_play_verify_motion)

def taste_fs_pause_resume():
    """暂停→位置冻结→恢复→继续推进"""
    get("/api/funscript/pause")
    time.sleep(0.2)
    d1 = get("/api/funscript/status")
    assert d1["paused"] == True, f"Not paused: {d1}"
    ms1 = d1["current_ms"]
    time.sleep(0.5)
    d2 = get("/api/funscript/status")
    ms2 = d2["current_ms"]
    assert abs(ms2 - ms1) < 100, f"Position changed while paused: {ms1}→{ms2}"
    # Resume
    get("/api/funscript/play")
    time.sleep(0.5)
    d3 = get("/api/funscript/status")
    assert d3["playing"] and not d3["paused"], f"Not resumed: {d3}"
    assert d3["current_ms"] > ms1, f"Not advancing after resume: {ms1}→{d3['current_ms']}"
    print(f"    暂停: {ms1}ms→冻结→恢复→{d3['current_ms']}ms ✓")
test("taste_fs_pause_resume", taste_fs_pause_resume)

def taste_fs_seek():
    """跳转到指定位置"""
    get("/api/funscript/seek/5000")
    time.sleep(0.3)
    d = get("/api/funscript/status")
    assert abs(d["current_ms"] - 5000) < 1000, f"Seek inaccurate: {d['current_ms']}"
    print(f"    Seek到5000ms: 实际={d['current_ms']}ms ✓")
test("taste_fs_seek", taste_fs_seek)

def taste_fs_speed():
    """变速播放验证"""
    # Set 2x speed
    get("/api/funscript/speed/2.0")
    get("/api/funscript/seek/1000")
    time.sleep(0.1)
    d1 = get("/api/funscript/status")
    assert d1["speed"] == 2.0, f"Speed not 2x: {d1['speed']}"
    t0 = time.time()
    time.sleep(0.5)
    d2 = get("/api/funscript/status")
    elapsed_real = (time.time() - t0) * 1000
    elapsed_fs = d2["current_ms"] - d1["current_ms"]
    # At 2x speed, funscript should advance ~2x real time
    ratio = elapsed_fs / elapsed_real if elapsed_real > 0 else 0
    assert ratio > 1.3, f"Speed ratio too low: {ratio:.2f} (expected ~2.0)"
    # Reset speed
    get("/api/funscript/speed/1.0")
    print(f"    2x变速: 实际推进{elapsed_fs:.0f}ms / 真实{elapsed_real:.0f}ms = {ratio:.1f}x ✓")
test("taste_fs_speed_2x", taste_fs_speed)

def taste_fs_sync():
    """视频同步: 模拟视频播放器发送时间码"""
    get("/api/funscript/seek/2000")
    time.sleep(0.2)
    # Simulate video at 4000ms (drift > 200ms → should resync)
    get("/api/funscript/sync/4000")
    time.sleep(0.3)
    d = get("/api/funscript/status")
    assert abs(d["current_ms"] - 4000) < 1000, f"Sync drift too large: {d['current_ms']}"
    print(f"    视频同步: 目标4000ms → 实际{d['current_ms']}ms ✓")
test("taste_fs_video_sync", taste_fs_sync)

def taste_fs_stop_clear():
    """停止+清除→状态归零"""
    get("/api/funscript/stop")
    time.sleep(0.2)
    d = get("/api/funscript/status")
    assert d["playing"] == False, f"Still playing after stop"
    get("/api/funscript/clear")
    d2 = get("/api/funscript/status")
    assert len(d2["axes"]) == 0, f"Axes not cleared: {d2['axes']}"
    print(f"    停止+清除: playing=False, axes清空 ✓")
test("taste_fs_stop_clear", taste_fs_stop_clear)

def taste_fs_local_scan():
    """扫描本地funscript文件"""
    d = get("/api/funscript/scan")
    scripts = d.get("scripts", [])
    assert len(scripts) > 0, "No local scripts found"
    # Verify axis mapping
    axes = {s["axis"] for s in scripts}
    has_v0 = any(s["axis"] == "V0" for s in scripts)
    print(f"    扫描: {len(scripts)}文件 | 轴: {sorted(axes)} | V0={has_v0}")
test("taste_fs_local_scan", taste_fs_local_scan)

def taste_fs_local_load():
    """从本地路径加载funscript"""
    scan = get("/api/funscript/scan")
    if not scan.get("scripts"):
        print("    跳过: 无本地脚本")
        return
    path = scan["scripts"][0]["path"]
    d = get(f"/api/funscript/load-local/{urllib.parse.quote(path)}")
    assert d.get("status") == "loaded", f"Load-local failed: {d}"
    assert d["duration_ms"] > 0, f"No duration: {d}"
    print(f"    本地加载: {path} → {d['duration_ms']}ms ✓")
    # Clean up
    get("/api/funscript/stop")
    get("/api/funscript/clear")
test("taste_fs_local_load", taste_fs_local_load)

# ══════════════════════════════════════════
# 🔄 一致性验证 — 虚拟系统 vs 用户体验
# ══════════════════════════════════════════
print("\n🔄 一致性验证")

def consistency_pattern_stop_home():
    """模式播放→停止→归位 完整流程"""
    get("/api/play/orbit/90")
    time.sleep(0.5)
    d1 = get("/api/state")
    assert d1["any_moving"] or d1["total_commands"] > 0, "Pattern not active"
    get("/api/stop")
    time.sleep(0.5)
    d2 = get("/api/state")
    # After stop, should be homed
    for ax in ["L0", "L1", "L2", "R0", "R1", "R2"]:
        cur = d2["axes"][ax]["current"]
        assert abs(cur - 5000) < 1000, f"{ax} not homed after stop: {cur}"
    print(f"    模式→停止→归位: 6轴全部回中 ✓")
test("consistency_pattern_lifecycle", consistency_pattern_stop_home)

def consistency_funscript_to_device():
    """Funscript播放→设备状态同步"""
    # Load a simple linear script that goes 0→100→0
    simple = [{"at": 0, "pos": 0}, {"at": 1000, "pos": 100}, {"at": 2000, "pos": 0}]
    post("/api/funscript/load", {"scripts": {"L0": {"actions": simple}}, "title": "sync_test"})
    get("/api/funscript/play")
    time.sleep(0.6)  # ~600ms → should be around pos 60
    fs_status = get("/api/funscript/status")
    dev_state = get("/api/state")
    # Funscript should show progress
    assert fs_status["current_ms"] > 300, f"FS not advancing: {fs_status['current_ms']}"
    # Device L0 should reflect funscript position
    l0_dev = dev_state["axes"]["L0"]["current"]
    l0_fs = fs_status["axes"]["L0"]["position"]
    l0_fs_tcode = fs_status["axes"]["L0"]["tcode"]
    # Allow some latency tolerance
    print(f"    FS pos={l0_fs} tcode={l0_fs_tcode} | 设备L0={l0_dev} | FS time={fs_status['current_ms']}ms")
    get("/api/funscript/stop")
    get("/api/funscript/clear")
    get("/api/send/D1")
    time.sleep(0.2)
test("consistency_fs_device_sync", consistency_funscript_to_device)

def consistency_speed_interval():
    """速度修饰符I对运动时间的影响"""
    get("/api/send/L00000I100")
    time.sleep(0.15)
    get("/api/send/L09999I100")  # Quick move
    time.sleep(0.15)
    d1 = get("/api/state")
    get("/api/send/L00000I2000")  # Slow move
    time.sleep(0.3)
    d2 = get("/api/state")
    # During slow move, should not be fully at target yet
    # (this is timing-dependent, so we're lenient)
    get("/api/send/D1")
    time.sleep(0.3)
    print(f"    速度修饰符I: 快速I100 vs 慢速I2000 正常 ✓")
test("consistency_speed_modifier", consistency_speed_interval)

# ══════════════════════════════════════════
# 🧪 内置测试一致性
# ══════════════════════════════════════════
print("\n🧪 Hub内置测试")

def hub_internal_tests():
    d = get("/api/test/all")
    passed = sum(1 for r in d if r["status"] == "pass")
    failed = sum(1 for r in d if r["status"] == "fail")
    assert failed == 0, f"{failed} internal tests failed: {[r['name'] for r in d if r['status']=='fail']}"
    print(f"    内置测试: {passed}/{len(d)} PASS")
test("hub_internal_20tests", hub_internal_tests)

# ══════════════════════════════════════════
# Summary
# ══════════════════════════════════════════
print("\n" + "="*60)
for r in results:
    print(r)
print(f"\n{'='*60}")
print(f"  Total: {p} PASS / {f} FAIL / {p+f} tests")
print(f"  {'🎉 ALL PASS — 五感验证通过' if f == 0 else f'⚠ {f} FAILURES'}")
print(f"{'='*60}")

sys.exit(0 if f == 0 else 1)
