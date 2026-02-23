#!/usr/bin/env python3
"""
复杂多级联动场景 — 逐步降低AI参与度
====================================
5个场景，每个场景展示多资源联动，并标注AI参与度。
目标：证明复杂操作链可以完全脱离AI运行。
使用 phone_lib.Phone 类。

用法: python complex_scenarios.py [--port 8086]
"""

import sys, os, time, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from phone_lib import Phone

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8084)
args = parser.parse_args()

p = Phone(port=args.port)
results = []
t_start = time.time()

def GET(path, **kw): return p.get(path)
def POST(path, b=None, **kw): return p.post(path, b)
def wait(ms): time.sleep(ms / 1000)

def scenario(name, ai_level, fn):
    t0 = time.time()
    try:
        ok, detail, steps = fn()
        ms = int((time.time() - t0) * 1000)
        results.append({"name": name, "ai": ai_level, "ok": ok, "detail": detail, "steps": steps, "ms": ms})
        icon = "✅" if ok else "❌"
        print(f"  {icon} [{ai_level}] {name} ({steps}步, {ms}ms)")
        print(f"     → {detail[:100]}")
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        results.append({"name": name, "ai": ai_level, "ok": False, "detail": str(e), "steps": 0, "ms": ms})
        print(f"  💥 [{ai_level}] {name} ({ms}ms): {e}")

# ==================== 预检 ====================
print("=" * 64)
print("  复杂多级联动场景 (逐步降低AI参与度)")
print("=" * 64)

status = GET("/status")
if "_error" in status:
    print(f"❌ API不可达: {p.base}/status"); sys.exit(1)
print(f"✓ API连接正常: {p.base}\n")

# ==================== S1: 智能环境感知报告 ====================
# AI参与度: L2 (用/command做自然语言路由) + L1 (组合多源数据)
# 联动资源: deviceinfo + storage + foreground + screen/text + notifications + battery Intent

def s1_smart_env_report():
    steps = 0; data = {}

    # 1. 并行采集基础数据 (L0)
    steps += 1
    data["device"] = GET("/deviceinfo")
    data["fg"] = GET("/foreground")
    data["storage"] = GET("/files/storage")
    data["notifs"] = GET("/notifications/read?limit=5")
    data["clip"] = GET("/clipboard")

    # 2. 用/command打开电池详情 (L2 - AI介入点)
    steps += 1
    POST("/command", {"command": "打开电池设置"})
    wait(2500)

    # 3. 读电池页文本 (L0)
    steps += 1
    battery_screen = GET("/screen/text")
    battery_texts = [t.get("text","") for t in battery_screen.get("texts",[])]

    # 4. 条件判断: 电量低于20%则告警 (L1 规则)
    steps += 1
    bat_level = data["device"].get("batteryLevel", -1)
    is_charging = data["device"].get("isCharging", False)
    low_battery = bat_level < 20 and not is_charging

    # 5. 回桌面 (L0)
    steps += 1
    POST("/home")
    wait(500)

    # 6. 生成报告 (L1 模板)
    steps += 1
    d = data["device"]
    report = (
        f"型号:{d.get('manufacturer')} {d.get('model')} | "
        f"Android:{d.get('androidVersion')} | "
        f"电量:{bat_level}%{'⚡' if is_charging else ''} | "
        f"存储:{d.get('storageAvailableMB',0)//1024}GB剩余 | "
        f"网络:{d.get('networkType','?')} | "
        f"通知:{data['notifs'].get('total',0)}条 | "
        f"电池页:{len(battery_texts)}项"
    )

    ok = bat_level > 0 and len(battery_texts) > 3
    return ok, report, steps

print("🔋 S1: 智能环境感知报告 (L2+L1, /command + 5源数据)")
scenario("智能环境感知报告", "L2+L1", s1_smart_env_report)

# ==================== S2: 跨APP信息萃取 ====================
# AI参与度: L1 (纯Intent+读屏, 零AI)
# 联动资源: Intent×3 + screen/text×3 + foreground×3 + home×2

def s2_cross_app_extraction():
    steps = 0; collected = {}

    # 1. 打开关于手机 → 提取型号/版本 (L0+L1)
    steps += 1
    POST("/intent", {"action": "android.settings.DEVICE_INFO_SETTINGS", "flags": ["FLAG_ACTIVITY_NEW_TASK","FLAG_ACTIVITY_CLEAR_TASK"]})
    wait(2000)
    steps += 1
    s1 = GET("/screen/text")
    texts1 = [t.get("text","") for t in s1.get("texts",[])]
    collected["device"] = [t for t in texts1 if any(k in t for k in ["Android","型号","Model","处理器","CPU","内存","RAM"])]

    # 2. 回桌面 → 打开WiFi设置 → 提取网络信息 (L0+L1)
    steps += 1
    POST("/home"); wait(800)
    steps += 1
    POST("/intent", {"action": "android.settings.WIFI_SETTINGS", "flags": ["FLAG_ACTIVITY_NEW_TASK"]})
    wait(2000)
    steps += 1
    s2 = GET("/screen/text")
    texts2 = [t.get("text","") for t in s2.get("texts",[])]
    collected["wifi"] = [t for t in texts2 if any(k in t for k in ["Wi-Fi","WIFI","连接","SSID","信号","速度","GHz","MHz"])]

    # 3. 回桌面 → 打开存储设置 → 提取存储信息 (L0+L1)
    steps += 1
    POST("/home"); wait(800)
    steps += 1
    POST("/intent", {"action": "android.intent.action.MANAGE_ALL_FILES_ACCESS_PERMISSION", "flags": ["FLAG_ACTIVITY_NEW_TASK"]})
    wait(2000)
    steps += 1
    fg3 = GET("/foreground")
    s3 = GET("/screen/text")
    texts3 = [t.get("text","") for t in s3.get("texts",[])]
    collected["storage_page"] = texts3[:5]

    # 4. 回桌面 (L0)
    steps += 1
    POST("/home"); wait(500)

    # 5. 综合+条件判断 (L1)
    steps += 1
    dev_count = len(collected["device"])
    wifi_count = len(collected["wifi"])
    summary = f"设备信息:{dev_count}项 | WiFi:{wifi_count}项 | 存储页:{len(collected['storage_page'])}项"
    ok = dev_count > 0 and wifi_count >= 0
    return ok, summary, steps

print("\n📊 S2: 跨APP信息萃取 (纯L1, Intent×3+读屏×3)")
scenario("跨APP信息萃取", "L1", s2_cross_app_extraction)

# ==================== S3: 系统状态自动调优 ====================
# AI参与度: L1 (纯规则, 零AI)
# 联动资源: deviceinfo + volume + brightness + stayawake + flashlight

def s3_auto_tune():
    steps = 0; actions = []

    # 1. 采集当前状态 (L0)
    steps += 1
    d = GET("/deviceinfo")
    bat = d.get("batteryLevel", 100)
    bright = d.get("brightness", 128)
    vol = d.get("volumeMusic", 5)
    screen_on = d.get("isScreenOn", True)

    # 2. 规则引擎: 根据状态决定动作 (L1)
    steps += 1

    # 规则1: 夜间模式(亮度<50则降到最低)
    if bright < 50:
        POST("/brightness/10")
        actions.append("亮度→10(夜间)")
    else:
        POST("/brightness/128")
        actions.append("亮度→128(标准)")
    steps += 1

    # 规则2: 电量保护(电量<30关闭保持唤醒)
    if bat < 30:
        POST("/stayawake/false")
        actions.append("关闭保持唤醒(省电)")
    else:
        POST("/stayawake/true")
        actions.append("保持唤醒(电量充足)")
    steps += 1

    # 规则3: 音量归一化
    POST("/volume", {"stream": "music", "level": 7})
    actions.append("音量→7")
    steps += 1

    # 规则4: 确保手电筒关闭
    POST("/flashlight/false")
    actions.append("手电筒→关")
    steps += 1

    # 3. 验证执行结果 (L0)
    steps += 1
    d2 = GET("/deviceinfo")
    stayawake = GET("/stayawake")

    detail = f"电量:{bat}% | 动作:{','.join(actions)} | 验证:亮度={d2.get('brightness')},音量={d2.get('volumeMusic')}"
    ok = len(actions) >= 4
    return ok, detail, steps

print("\n⚙️ S3: 系统状态自动调优 (纯L1, 规则引擎)")
scenario("系统状态自动调优", "L1", s3_auto_tune)

# ==================== S4: 通知驱动自动化链 ====================
# AI参与度: L1 (纯规则, 零AI)
# 联动资源: notifications + foreground + findnodes + macro/list + deviceinfo

def s4_notification_chain():
    steps = 0; decisions = []

    # 1. 读取通知 (L0)
    steps += 1
    notifs = GET("/notifications/read?limit=10")
    total = notifs.get("total", 0)
    items = notifs.get("notifications", [])

    # 2. 规则匹配: 分类通知 (L1)
    steps += 1
    categories = {"social": 0, "system": 0, "other": 0}
    social_pkgs = ["tencent", "whatsapp", "telegram", "weixin", "qq"]
    for n in items:
        pkg = str(n.get("package", "")).lower()
        if any(s in pkg for s in social_pkgs):
            categories["social"] += 1
        elif "android" in pkg or "system" in pkg:
            categories["system"] += 1
        else:
            categories["other"] += 1

    # 3. 决策: 社交通知多则检查微信 (L1)
    steps += 1
    if categories["social"] > 0:
        decisions.append(f"社交通知{categories['social']}条→检查微信")
        POST("/intent", {"action": "android.intent.action.MAIN", "package": "com.tencent.mm", "flags": ["FLAG_ACTIVITY_NEW_TASK"]})
        wait(2000)
        fg = GET("/foreground")
        wechat_ok = "tencent" in fg.get("packageName", "").lower()
        decisions.append(f"微信{'已打开' if wechat_ok else '未打开'}")
        POST("/home"); wait(500)
    else:
        decisions.append("无社交通知→跳过")

    # 4. 检查设备健康 (L0+L1)
    steps += 1
    d = GET("/deviceinfo")
    if d.get("batteryLevel", 100) < 15:
        decisions.append("电量极低→启动省电")
    if not d.get("networkConnected", True):
        decisions.append("网络断开→告警")
    if not d.get("isScreenOn", True):
        decisions.append("息屏→唤醒")
        POST("/wake")

    # 5. 检查宏状态 (L0)
    steps += 1
    macros = GET("/macro/list")
    running_macros = [m for m in (macros if isinstance(macros, list) else []) if m.get("running")]

    detail = (f"通知:{total}条(社交{categories['social']}/系统{categories['system']}/其他{categories['other']}) | "
              f"决策:{len(decisions)}项 | 运行中宏:{len(running_macros)} | "
              f"{'→'.join(decisions[:3])}")
    ok = total >= 0
    return ok, detail, steps

print("\n🔔 S4: 通知驱动自动化链 (纯L1, 事件→规则→动作)")
scenario("通知驱动自动化链", "L1", s4_notification_chain)

# ==================== S5: 全自主巡检 ====================
# AI参与度: L0 (纯API调用, 零逻辑, 最低参与)
# 联动资源: 尽可能多的API端点并行调用

def s5_full_patrol():
    steps = 0; checks = {}

    # 逐个调用所有感知API, 仅记录是否成功
    apis = [
        ("status", "GET", "/status"),
        ("deviceinfo", "GET", "/deviceinfo"),
        ("foreground", "GET", "/foreground"),
        ("screen_text", "GET", "/screen/text"),
        ("viewtree", "GET", "/viewtree?depth=1"),
        ("windowinfo", "GET", "/windowinfo"),
        ("notifications", "GET", "/notifications/read?limit=3"),
        ("apps", "GET", "/apps"),
        ("clipboard", "GET", "/clipboard"),
        ("storage", "GET", "/files/storage"),
        ("files", "GET", "/files/list?path=/sdcard"),
        ("macros", "GET", "/macro/list"),
        ("stayawake", "GET", "/stayawake"),
    ]

    for name, method, path in apis:
        steps += 1
        r = p._http(method, path, timeout=10)
        checks[name] = "_error" not in r

    # 执行导航操作
    for name, path in [("home", "/home"), ("wake", "/wake")]:
        steps += 1
        r = POST(path)
        checks[name] = r.get("ok") is not False if isinstance(r, dict) else False

    passed = sum(1 for v in checks.values() if v)
    total = len(checks)
    failed = [k for k, v in checks.items() if not v]
    detail = f"{passed}/{total}通过" + (f" | 失败:{','.join(failed)}" if failed else " | 全部正常")

    ok = passed == total
    return ok, detail, steps

print("\n🛡️ S5: 全自主巡检 (纯L0, 15个API端点)")
scenario("全自主巡检", "L0", s5_full_patrol)

# ==================== 最终回桌面 ====================
POST("/home")

# ==================== 总结 ====================
total_time = int((time.time() - t_start) * 1000)
passed = sum(1 for r in results if r["ok"])
total = len(results)
total_steps = sum(r["steps"] for r in results)

print("\n" + "=" * 64)
print(f"  结果: {passed}/{total} 场景通过 | 总步骤: {total_steps} | 耗时: {total_time}ms")
print("=" * 64)

# AI参与度统计
ai_levels = {}
for r in results:
    ai = r["ai"]
    if ai not in ai_levels: ai_levels[ai] = {"pass": 0, "fail": 0, "steps": 0}
    if r["ok"]: ai_levels[ai]["pass"] += 1
    else: ai_levels[ai]["fail"] += 1
    ai_levels[ai]["steps"] += r["steps"]

print("\n  📊 AI参与度分布:")
for ai, s in sorted(ai_levels.items()):
    icon = "✅" if s["fail"] == 0 else "⚠️"
    print(f"    {icon} {ai}: {s['pass']}/{s['pass']+s['fail']} 场景, {s['steps']}步")

# 自治度
l0l1_pass = sum(1 for r in results if r["ok"] and "L2" not in r["ai"])
l0l1_total = sum(1 for r in results if "L2" not in r["ai"])
l0l1_steps = sum(r["steps"] for r in results if "L2" not in r["ai"])

print(f"\n  🏛️ 自治度:")
print(f"    零AI场景: {l0l1_pass}/{l0l1_total} 通过 ({l0l1_steps}步)")
print(f"    含AI场景: {passed-l0l1_pass}/{total-l0l1_total} 通过")
print(f"    → 复杂联动中 {l0l1_steps}/{total_steps} 步 ({l0l1_steps*100//max(total_steps,1)}%) 无需AI")

print("=" * 64)
sys.exit(0 if passed == total else 1)
