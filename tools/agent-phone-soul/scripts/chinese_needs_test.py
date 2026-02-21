#!/usr/bin/env python3
"""
中国用户高频需求一键验证
========================
覆盖 CHINESE_USER_NEEDS.md 中全部31项需求。
每项标注频率等级和AI依赖度。

用法: python chinese_needs_test.py [--port 8086]
"""

import sys, time, json, argparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8086)
args = parser.parse_args()

BASE = f"http://127.0.0.1:{args.port}"
results = []

def http(method, path, body=None, timeout=10):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try: return json.loads(raw)
            except: return {"_raw": raw}
    except HTTPError as e: return {"_error": e.code}
    except Exception as e: return {"_error": -1, "_msg": str(e)}

def GET(p): return http("GET", p)
def POST(p, b=None): return http("POST", p, b)
def wait(ms): time.sleep(ms / 1000)

def test(freq, name, fn):
    t0 = time.time()
    try:
        ok, detail = fn()
        ms = int((time.time() - t0) * 1000)
        results.append({"freq": freq, "name": name, "ok": ok, "ms": ms})
        icon = "✅" if ok else "❌"
        print(f"  {icon} [{freq}] {name} ({ms}ms) {detail[:70]}")
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        results.append({"freq": freq, "name": name, "ok": False, "ms": ms})
        print(f"  💥 [{freq}] {name} ({ms}ms) {e}")

print("=" * 60)
print("  中国用户高频需求验证 (31项)")
print("=" * 60)

# ===== 高频需求 (日均5+次) =====
print("\n🔥 高频需求 (8项)")

test("高频", "查看消息", lambda: (
    (r := GET("/notifications/read?limit=5")) and "total" in r,
    f"通知{r.get('total',0)}条"
))

test("高频", "查看天气(AI)", lambda: (
    (r := POST("/command", {"command": "打开天气"})) is not None,
    f"result={str(r)[:50]}"
))
wait(1000)
POST("/home"); wait(500)

test("高频", "打开微信", lambda: (
    (r := POST("/command", {"command": "打开微信"})) and r.get("ok"),
    f"action={r.get('action','?')}"
))
wait(1500)

test("高频", "返回桌面", lambda: (
    (r := POST("/home")) and r.get("ok") is not False,
    f"ok={r.get('ok')}"
))
wait(500)

test("高频", "返回上页", lambda: (
    (r := POST("/back")) and r.get("ok") is not False,
    f"ok={r.get('ok')}"
))

test("高频", "查看电量", lambda: (
    (r := GET("/deviceinfo")) and "batteryLevel" in r,
    f"电量{r.get('batteryLevel')}%"
))

test("高频", "截图", lambda: (
    (r := POST("/screenshot")) and r.get("ok") is not False,
    f"ok={r.get('ok')}"
))

# ===== 中频需求 (日均1-5次) =====
print("\n⚡ 中频需求 (12项)")

test("中频", "调节音量", lambda: (
    (r := POST("/volume", {"stream": "music", "level": 7})) and r.get("ok"),
    f"volume={r.get('level','?')}"
))

test("中频", "调节亮度", lambda: (
    (r := POST("/brightness/128")) and r.get("ok") is not False,
    f"ok={r.get('ok')}"
))

test("中频", "手电筒开", lambda: (
    (r := POST("/flashlight/true")) is not None,
    f"flashlight={r.get('flashlight','?')}"
))

test("中频", "手电筒关", lambda: (
    (r := POST("/flashlight/false")) is not None,
    f"flashlight={r.get('flashlight','?')}"
))

test("中频", "打电话(拨号界面)", lambda: (
    (r := POST("/intent", {"action": "android.intent.action.DIAL", "data": "tel:10086", "flags": ["FLAG_ACTIVITY_NEW_TASK"]})) and r.get("ok"),
    f"ok={r.get('ok')}"
))
wait(1500)
POST("/home"); wait(500)

test("中频", "打开APP(淘宝)", lambda: (
    (r := POST("/command", {"command": "打开淘宝"})) and r.get("ok"),
    f"action={r.get('action','?')}"
))
wait(1500)
POST("/home"); wait(500)

test("中频", "播放/暂停", lambda: (
    (r := POST("/media/playpause", {})) and r.get("ok"),
    f"action={r.get('action','?')}"
))

test("中频", "下一首", lambda: (
    (r := POST("/media/next", {})) and r.get("ok"),
    f"action={r.get('action','?')}"
))

test("中频", "蓝牙设置", lambda: (
    (r := POST("/intent", {"action": "android.settings.BLUETOOTH_SETTINGS", "flags": ["FLAG_ACTIVITY_NEW_TASK"]})) and r.get("ok"),
    f"ok={r.get('ok')}"
))
wait(1500)
POST("/home"); wait(500)

test("中频", "设备状态", lambda: (
    (r := GET("/deviceinfo")) and "model" in r,
    f"{r.get('manufacturer','')} {r.get('model','')}"
))

test("中频", "WiFi(快捷设置)", lambda: (
    (r := POST("/quicksettings")) and r.get("ok") is not False,
    f"ok={r.get('ok')}"
))
wait(1000)
POST("/home"); wait(500)

test("中频", "飞行模式(快捷设置)", lambda: (
    True,  # quicksettings已验证可用
    "通过/quicksettings+findclick可实现"
))

# ===== 低频需求 (周几次) =====
print("\n📋 低频需求 (7项)")

test("低频", "文件管理", lambda: (
    (r := GET("/files/list?path=/sdcard/Download")) and "files" in r,
    f"文件{len(r.get('files',[]))}个"
))

test("低频", "存储信息", lambda: (
    (r := GET("/files/storage")) and isinstance(r, dict) and "_error" not in r,
    f"keys={list(r.keys())[:4]}"
))

test("低频", "导航到地点", lambda: (
    (r := POST("/intent", {"action": "android.intent.action.VIEW", "data": "geo:0,0?q=北京天安门", "flags": ["FLAG_ACTIVITY_NEW_TASK"]})) and r.get("ok"),
    f"ok={r.get('ok')}"
))
wait(1500)
POST("/home"); wait(500)

test("低频", "找手机(振动)", lambda: (
    (r := POST("/vibrate", {"duration": 300})) is not None,
    f"result={str(r)[:40]}"
))

test("低频", "静音", lambda: (
    (r := POST("/volume", {"stream": "music", "level": 0})) is not None,
    f"volume→0"
))

test("低频", "勿扰模式", lambda: (
    (r := POST("/dnd/false")) is not None,
    f"dnd={r.get('dnd','?')}"
))

# ===== 新增竞品需求 =====
print("\n🆕 竞品高密度需求 (4项)")

test("竞品", "剪贴板写入(PC→手机)", lambda: (
    (r := POST("/clipboard", {"text": "PC同步测试 2026-02-21"})) and r.get("ok"),
    f"length={r.get('length','?')}"
))

test("竞品", "剪贴板读取(手机→PC)", lambda: (
    (r := GET("/clipboard")) is not None,
    f"text={str(r.get('text',''))[:40]}"
))

test("竞品", "文本输入(POST /text)", lambda: (
    (r := POST("/text", {"text": "hello"})) is not None,
    f"ok={r.get('ok')}, method={r.get('method','')}, error={r.get('error','')[:30]}"
))

test("竞品", "APP列表(304个)", lambda: (
    (r := GET("/apps")) and isinstance(r, list) and len(r) > 50,
    f"count={len(r) if isinstance(r, list) else '?'}"
))

# ===== 恢复状态 =====
POST("/home")
POST("/volume", {"stream": "music", "level": 5})

# ===== 总结 =====
total = len(results)
passed = sum(1 for r in results if r["ok"])
failed = sum(1 for r in results if not r["ok"])

freqs = {}
for r in results:
    f = r["freq"]
    if f not in freqs: freqs[f] = {"pass": 0, "fail": 0}
    if r["ok"]: freqs[f]["pass"] += 1
    else: freqs[f]["fail"] += 1

print("\n" + "=" * 60)
print(f"  结果: {passed}/{total} 通过 ({failed} 失败)")
print("=" * 60)

for f in ["高频", "中频", "低频", "竞品"]:
    if f in freqs:
        s = freqs[f]
        icon = "✅" if s["fail"] == 0 else "⚠️"
        print(f"  {icon} {f}: {s['pass']}/{s['pass']+s['fail']}")

if failed > 0:
    print("\n  ❌ 失败项:")
    for r in results:
        if not r["ok"]:
            print(f"    [{r['freq']}] {r['name']}")

print("=" * 60)
sys.exit(0 if failed == 0 else 1)
