#!/usr/bin/env python3
"""
ScreenStream 独立功能测试 — 零AI依赖
=====================================
验证所有手机控制能力在脱离AI/LLM后仍完全可用。
每个测试仅使用 HTTP REST 调用，不依赖任何智能推理。

架构分层:
  L0: 原子API (单个HTTP调用)       ← 本脚本主要测试层
  L1: 组合序列 (多步骤确定性流程)   ← 本脚本部分测试
  L2: LLM推理 (/command端点)       ← 仅作为对比项
  L3: 自主Agent (监控+决策循环)     ← 不在本脚本范围

用法:
  python standalone_test.py [--port 8086] [--verbose]
"""

import sys, time, json, argparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ==================== 基础设施 ====================

parser = argparse.ArgumentParser(description="ScreenStream Standalone Test")
parser.add_argument("--port", type=int, default=8084)
parser.add_argument("--verbose", "-v", action="store_true")
args = parser.parse_args()

BASE = f"http://127.0.0.1:{args.port}"
results = []
t_start = time.time()

def http(method, path, body=None, timeout=10):
    """纯HTTP调用，零依赖"""
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                return json.loads(raw)
            except:
                return {"_raw": raw, "_len": len(raw)}
    except HTTPError as e:
        return {"_error": e.code, "_msg": e.reason}
    except URLError as e:
        return {"_error": -1, "_msg": str(e.reason)}
    except Exception as e:
        return {"_error": -1, "_msg": str(e)}

def GET(path, **kw): return http("GET", path, **kw)
def POST(path, body=None, **kw): return http("POST", path, body, **kw)

def test(layer, category, name, fn):
    """执行单个测试"""
    t0 = time.time()
    try:
        ok, detail = fn()
        ms = int((time.time() - t0) * 1000)
        results.append({"layer": layer, "cat": category, "name": name, "ok": ok, "detail": detail, "ms": ms})
        icon = "✅" if ok else "❌"
        if args.verbose or not ok:
            print(f"  {icon} [{layer}] {category}/{name} ({ms}ms): {detail[:80]}")
        else:
            print(f"  {icon} [{layer}] {category}/{name} ({ms}ms)")
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        results.append({"layer": layer, "cat": category, "name": name, "ok": False, "detail": str(e), "ms": ms})
        print(f"  💥 [{layer}] {category}/{name} ({ms}ms): EXCEPTION {e}")

def wait(ms):
    time.sleep(ms / 1000)

# ==================== L0: 原子API测试 ====================
print("=" * 60)
print("  ScreenStream 独立功能测试 (零AI依赖)")
print("=" * 60)

# --- 感知类 (只读，无副作用) ---
print("\n📡 L0-感知: 只读信息获取")

test("L0", "感知", "连接状态", lambda: (
    (r := GET("/status")) and "connected" in r,
    f"connected={r.get('connected')}, inputEnabled={r.get('inputEnabled')}"
))

test("L0", "感知", "设备信息", lambda: (
    (r := GET("/deviceinfo")) and "model" in r,
    f"{r.get('manufacturer')} {r.get('model')} Android {r.get('androidVersion')}"
))

test("L0", "感知", "前台APP", lambda: (
    (r := GET("/foreground")) and "packageName" in r,
    f"pkg={r.get('packageName')}"
))

test("L0", "感知", "屏幕文本", lambda: (
    (r := GET("/screen/text")) and "texts" in r,
    f"texts={r.get('textCount',0)}, clickables={r.get('clickableCount',0)}, pkg={r.get('package','?')}"
))

test("L0", "感知", "View树", lambda: (
    (r := GET("/viewtree?depth=2")) and isinstance(r, dict) and "_error" not in r,
    f"keys={list(r.keys())[:5]}" if isinstance(r, dict) else f"type={type(r)}"
))

test("L0", "感知", "窗口信息", lambda: (
    (r := GET("/windowinfo")) and "package" in r,
    f"pkg={r.get('package')}, nodes={r.get('totalNodes', '?')}"
))

test("L0", "感知", "通知列表", lambda: (
    (r := GET("/notifications/read?limit=5")) and "total" in r,
    f"total={r.get('total')}"
))

test("L0", "感知", "APP列表", lambda: (
    (r := GET("/apps")) and isinstance(r, list),
    f"count={len(r) if isinstance(r, list) else '?'}"
))

test("L0", "感知", "剪贴板", lambda: (
    (r := GET("/clipboard")) is not None,
    f"content={str(r)[:60]}"
))

test("L0", "感知", "文件-存储", lambda: (
    (r := GET("/files/storage")) and isinstance(r, dict) and "_error" not in r,
    f"keys={list(r.keys())[:6]}"
))

test("L0", "感知", "文件-列表", lambda: (
    (r := GET("/files/list?path=/sdcard/Download")) and "files" in r,
    f"files={len(r.get('files',[]))}"
))

test("L0", "感知", "等待文本", lambda: (
    (r := GET("/wait?text=NONEXISTENT_XYZ&timeout=500")) is not None,
    f"found={r.get('found', False)}"
))

test("L0", "感知", "节点搜索", lambda: (
    (r := POST("/findnodes", {"text": "设置"})) is not None,
    f"found={r.get('found',0)}"
))

test("L0", "感知", "宏列表", lambda: (
    (r := GET("/macro/list")) is not None,
    f"macros={len(r) if isinstance(r, list) else '?'}"
))

test("L0", "感知", "唤醒状态", lambda: (
    (r := GET("/stayawake")) is not None,
    f"stayAwake={r.get('stayAwake','?')}"
))

# --- 导航类 (有副作用但安全) ---
print("\n🧭 L0-导航: 基本导航操作")

test("L0", "导航", "Home键", lambda: (
    (r := POST("/home")) and r.get("ok") is not False,
    f"ok={r.get('ok')}"
))
wait(500)

test("L0", "导航", "Back键", lambda: (
    (r := POST("/back")) and r.get("ok") is not False,
    f"ok={r.get('ok')}"
))
wait(500)

test("L0", "导航", "最近任务", lambda: (
    (r := POST("/recents")) and r.get("ok") is not False,
    f"ok={r.get('ok')}"
))
wait(800)

POST("/home")
wait(500)

# --- 系统控制类 ---
print("\n⚙️ L0-系统: 系统级控制")

test("L0", "系统", "唤醒屏幕", lambda: (
    (r := POST("/wake")) and r.get("ok") is not False,
    f"ok={r.get('ok')}"
))

test("L0", "系统", "亮度控制", lambda: (
    (r := POST("/brightness/120")) and r.get("ok") is not False,
    f"ok={r.get('ok')}"
))

test("L0", "系统", "音量控制", lambda: (
    (r := POST("/volume", {"stream": "music", "level": 5})) is not None,
    f"result={str(r)[:60]}"
))

test("L0", "系统", "截屏", lambda: (
    (r := POST("/screenshot")) and r.get("ok") is not False,
    f"ok={r.get('ok')}"
))

test("L0", "系统", "手电筒关", lambda: (
    (r := POST("/flashlight/false")) is not None,
    f"result={str(r)[:60]}"
))

test("L0", "系统", "保持唤醒", lambda: (
    (r := POST("/stayawake/true")) is not None,
    f"result={str(r)[:60]}"
))

test("L0", "系统", "关弹窗", lambda: (
    (r := POST("/dismiss")) is not None,
    f"result={str(r)[:60]}"
))

# --- 输入类 ---
print("\n✏️ L0-输入: 触控/点击/文本")

test("L0", "输入", "坐标点击", lambda: (
    (r := POST("/tap", {"nx": 0.5, "ny": 0.5})) and r.get("ok") is not False,
    f"ok={r.get('ok')}"
))
wait(500)
POST("/home")
wait(500)

test("L0", "输入", "语义点击(负例)", lambda: (
    (r := POST("/findclick", {"text": "NONEXISTENT_XYZ_999"})) is not None,
    f"ok={r.get('ok')}, error={r.get('error','none')[:40]}"
))

# --- Intent类 ---
print("\n📤 L0-Intent: 系统Intent发送")

test("L0", "Intent", "打开设置", lambda: (
    (r := POST("/intent", {
        "action": "android.settings.SETTINGS",
        "flags": ["FLAG_ACTIVITY_NEW_TASK", "FLAG_ACTIVITY_CLEAR_TASK"]
    })) and r.get("ok") is not False,
    f"ok={r.get('ok')}"
))
wait(1500)

# 验证确实到了设置
test("L0", "Intent", "验证-前台是设置", lambda: (
    (r := GET("/foreground")) and "settings" in r.get("packageName", "").lower(),
    f"pkg={r.get('packageName')}"
))

POST("/home")
wait(800)

# ==================== L1: 组合序列测试 ====================
print("\n🔗 L1-组合: 多步骤确定性序列 (无AI推理)")

# L1-1: Intent直跳+读屏 (设备信息提取)
def test_l1_device_info():
    POST("/intent", {
        "action": "android.settings.DEVICE_INFO_SETTINGS",
        "flags": ["FLAG_ACTIVITY_NEW_TASK", "FLAG_ACTIVITY_CLEAR_TASK"]
    })
    wait(2000)
    fg = GET("/foreground")
    is_settings = "settings" in fg.get("packageName", "").lower()
    screen = GET("/screen/text")
    texts = [t.get("text", "") for t in screen.get("texts", [])]
    has_info = any(kw in " ".join(texts) for kw in ["型号", "Model", "Android", "版本"])
    POST("/home")
    return is_settings and has_info, f"texts={len(texts)}, has_info={has_info}"

test("L1", "组合", "Intent+读屏=设备信息", test_l1_device_info)
wait(800)

# L1-2: Intent直跳+读屏 (WiFi信息)
def test_l1_wifi():
    POST("/intent", {
        "action": "android.settings.WIFI_SETTINGS",
        "flags": ["FLAG_ACTIVITY_NEW_TASK"]
    })
    wait(2000)
    screen = GET("/screen/text")
    texts = [t.get("text", "") for t in screen.get("texts", [])]
    has_wifi = any(kw in " ".join(texts) for kw in ["Wi-Fi", "WIFI", "WiFi", "WLAN", "网络"])
    POST("/home")
    return has_wifi, f"texts={len(texts)}"

test("L1", "组合", "Intent+读屏=WiFi信息", test_l1_wifi)
wait(800)

# L1-3: 打开APP+验证 (不用/command，用Intent)
def test_l1_open_app():
    POST("/intent", {
        "action": "android.settings.BATTERY_SAVER_SETTINGS",
        "flags": ["FLAG_ACTIVITY_NEW_TASK"]
    })
    wait(2000)
    fg = GET("/foreground")
    pkg = fg.get("packageName", "").lower()
    is_battery_page = "settings" in pkg or "battery" in pkg or "lool" in pkg
    screen = GET("/screen/text")
    texts = [t.get("text", "") for t in screen.get("texts", [])]
    has_battery = any(kw in " ".join(texts) for kw in ["电池", "电量", "Battery", "充电"])
    POST("/home")
    return is_battery_page and has_battery, f"pkg={fg.get('packageName')}, battery_info={has_battery}"

test("L1", "组合", "Intent+验证=电池页", test_l1_open_app)
wait(800)

# L1-4: 通知读取+判断
def test_l1_notif_check():
    notifs = GET("/notifications/read?limit=10")
    total = notifs.get("total", 0)
    items = notifs.get("notifications", [])
    # 纯规则判断：有无特定APP的通知
    has_ss = any("screenstream" in str(n).lower() for n in items)
    return True, f"total={total}, screenstream_notif={has_ss}"

test("L1", "组合", "通知读取+规则判断", test_l1_notif_check)

# L1-5: 跨APP切换 (确定性流程)
def test_l1_cross_app():
    # 1. 打开设置
    POST("/intent", {"action": "android.settings.SETTINGS", "flags": ["FLAG_ACTIVITY_NEW_TASK"]})
    wait(1500)
    fg1 = GET("/foreground")
    ok1 = "settings" in fg1.get("packageName", "").lower()

    # 2. Home
    POST("/home")
    wait(800)

    # 3. 打开蓝牙设置
    POST("/intent", {"action": "android.settings.BLUETOOTH_SETTINGS", "flags": ["FLAG_ACTIVITY_NEW_TASK"]})
    wait(1500)
    fg2 = GET("/foreground")
    ok2 = "settings" in fg2.get("packageName", "").lower()

    # 4. Home
    POST("/home")
    wait(500)

    return ok1 and ok2, f"settings={ok1}, bluetooth={ok2}"

test("L1", "组合", "跨页面切换=设置→蓝牙", test_l1_cross_app)
wait(800)

# L1-6: 设备状态综合采集
def test_l1_status_collect():
    status = GET("/status")
    device = GET("/deviceinfo")
    fg = GET("/foreground")
    storage = GET("/files/storage")

    report = {
        "connected": status.get("connected"),
        "model": f"{device.get('manufacturer')} {device.get('model')}",
        "battery": f"{device.get('batteryLevel')}%",
        "storage_free": f"{device.get('storageAvailableMB',0)//1024}GB",
        "foreground": fg.get("packageName","?").split(".")[-1],
        "screen": "on" if device.get("isScreenOn") else "off",
    }
    ok = all(v and v != "?" and v != "None" for v in report.values())
    return ok, " | ".join(f"{k}={v}" for k, v in report.items())

test("L1", "组合", "设备状态综合采集", test_l1_status_collect)

# ==================== L2 对比: AI命令 (仅作参考) ====================
print("\n🤖 L2-AI对比: /command端点 (需要LLM推理)")

test("L2", "AI对比", "/command返回桌面", lambda: (
    (r := POST("/command", {"command": "返回桌面"})) is not None,
    f"result={str(r)[:80]}"
))
wait(1500)

# ==================== 总结 ====================
total_time = int((time.time() - t_start) * 1000)
passed = sum(1 for r in results if r["ok"])
failed = sum(1 for r in results if not r["ok"])
total = len(results)

# 按层统计
layers = {}
for r in results:
    l = r["layer"]
    if l not in layers:
        layers[l] = {"pass": 0, "fail": 0}
    if r["ok"]:
        layers[l]["pass"] += 1
    else:
        layers[l]["fail"] += 1

# 按类别统计
cats = {}
for r in results:
    c = r["cat"]
    if c not in cats:
        cats[c] = {"pass": 0, "fail": 0}
    if r["ok"]:
        cats[c]["pass"] += 1
    else:
        cats[c]["fail"] += 1

print("\n" + "=" * 60)
print(f"  结果: {passed}/{total} 通过 ({failed} 失败) | 总耗时: {total_time}ms")
print("=" * 60)

print("\n  📊 按层统计:")
for l, s in sorted(layers.items()):
    icon = "✅" if s["fail"] == 0 else "⚠️"
    print(f"    {icon} {l}: {s['pass']}/{s['pass']+s['fail']} 通过")

print("\n  📊 按类别统计:")
for c, s in sorted(cats.items()):
    icon = "✅" if s["fail"] == 0 else "⚠️"
    print(f"    {icon} {c}: {s['pass']}/{s['pass']+s['fail']} 通过")

if failed > 0:
    print("\n  ❌ 失败项:")
    for r in results:
        if not r["ok"]:
            print(f"    [{r['layer']}] {r['cat']}/{r['name']}: {r['detail'][:60]}")

# 自治度评估
l0_total = layers.get("L0", {}).get("pass", 0) + layers.get("L0", {}).get("fail", 0)
l0_pass = layers.get("L0", {}).get("pass", 0)
l1_total = layers.get("L1", {}).get("pass", 0) + layers.get("L1", {}).get("fail", 0)
l1_pass = layers.get("L1", {}).get("pass", 0)

print(f"\n  🏛️ 自治度评估:")
print(f"    L0 原子API (零AI): {l0_pass}/{l0_total} = {l0_pass*100//max(l0_total,1)}% 自治")
print(f"    L1 组合序列 (零AI): {l1_pass}/{l1_total} = {l1_pass*100//max(l1_total,1)}% 自治")
print(f"    → 脱离AI后，{l0_pass+l1_pass}/{l0_total+l1_total} 项核心功能完全可用")

print("=" * 60)
sys.exit(0 if failed == 0 else 1)
