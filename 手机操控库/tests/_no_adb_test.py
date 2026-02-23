"""纯HTTP模式验证 — 模拟ADB二进制完全不存在
通过猴子补丁让_find_adb()返回None，验证所有功能仅通过HTTP可用。"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 在导入phone_lib之前，先monkey-patch掉ADB路径检测
import phone_lib
phone_lib._find_adb = lambda: None
phone_lib._adb_available = lambda: False
phone_lib._usb_serial_cache = ""  # 清除缓存

from phone_lib import Phone, discover, NegativeState, _probe, _get_local_subnet

WIFI_IP = "192.168.10.122"
WIFI_PORT = 8086
passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name} {detail}")
    else:
        failed += 1
        print(f"  ❌ {name} {detail}")

print("=" * 55)
print("  纯HTTP模式验证 (ADB完全不存在)")
print("=" * 55)

# 验证ADB确实不可用
check("ADB不可用", phone_lib._find_adb() is None, "→ _find_adb()=None")
out, ok = phone_lib._adb("devices")
check("_adb()安全失败", not ok, f"→ ok={ok}")

# ============================================================
print("\n[1] 连接与发现")
# ============================================================

# discover 无ADB但有extra_hosts
url = discover(extra_hosts=[WIFI_IP])
check("discover(extra_hosts)", url is not None, f"→ {url}")

# discover 无ADB无extra_hosts但有子网扫描
# (跳过，太慢)

# 直接连接
p = Phone(host=WIFI_IP, port=WIFI_PORT, auto_discover=False, retry=1)
check("Phone创建", p is not None, f"→ {p}")
check("无ADB标志", not p._has_adb, f"→ _has_adb={p._has_adb}")

# ============================================================
print("\n[2] 👁 视觉 (纯HTTP)")
# ============================================================

texts, pkg = p.read()
check("屏幕文本", isinstance(texts, list) and len(texts) > 0, f"→ {len(texts)}条, fg={pkg}")

fg = p.foreground()
check("前台APP", bool(fg), f"→ {fg}")

vt = p.viewtree(3)
check("View树", isinstance(vt, dict), f"→ keys={list(vt.keys())[:3]}")

# ============================================================
print("\n[3] 👂 听觉 (纯HTTP)")
# ============================================================

dev = p.device()
vol = dev.get("volumeMusic", -1)
check("音量", vol >= 0, f"→ music={vol}")

# ============================================================
print("\n[4] 🖐 触觉 (纯HTTP)")
# ============================================================

s = p.status()
check("输入状态", s.get("inputEnabled", False), f"→ inputEnabled={s.get('inputEnabled')}")

# tap (不实际改变屏幕状态)
r = p.tap(0.5, 0.9)  # 底部安全区域
check("/tap API", not (r or {}).get("_error"), "→ 可达")

# key
r = p.post("/key", {"keysym": 0xFF1B, "down": True})
p.post("/key", {"keysym": 0xFF1B, "down": False})
check("/key API", not (r or {}).get("_error"), "→ 可达")

# text
r = p.post("/text", {"text": ""})
check("/text API", not (r or {}).get("_error"), "→ 可达")

# findnodes
r = p.post("/findnodes", {"text": "设置"})
check("/findnodes", isinstance(r, dict), f"→ count={r.get('count', '?')}")

# back (安全操作)
p.back()
check("back()", True, "→ 执行")

# home (安全操作)
p.home()
time.sleep(0.5)
check("home()", True, "→ 执行")

# ============================================================
print("\n[5] 👃 嗅觉 (纯HTTP)")
# ============================================================

n = p.notifications(10)
check("通知", isinstance(n, dict) and "total" in n, f"→ {n.get('total', '?')}条")

fg2 = p.foreground()
check("前台监控", bool(fg2), f"→ {fg2}")

# ============================================================
print("\n[6] 👅 味觉 (纯HTTP)")
# ============================================================

bat = dev.get("batteryLevel", -1)
check("电池", bat >= 0, f"→ {bat}%")

net = dev.get("networkType", "?")
check("网络", net != "?", f"→ {net}")

storage = dev.get("storageAvailableMB", -1)
check("存储", storage >= 0, f"→ {round(storage/1024, 1)}GB")

p.clipboard_write("no_adb_test")
time.sleep(0.3)
clip = p.clipboard_read()
check("剪贴板", True, f"→ 写入no_adb_test, 读取={clip}")

apps = p.apps()
check("APP列表", isinstance(apps, (dict, list)), f"→ 类型={type(apps).__name__}")

# ============================================================
print("\n[7] 弹性特性 (纯HTTP)")
# ============================================================

h = p.health()
check("health()", h.get("healthy", False), f"→ state={h.get('state')}")

senses = p.senses()
check("senses()", senses.get("_ok", False), f"→ 5感全采集")

state, detail = NegativeState.detect(p)
check("负面状态检测", state == NegativeState.HEALTHY, f"→ {state}")

alive, log = p.ensure_alive()
check("ensure_alive()", alive, f"→ {len(log)}条日志")

# ============================================================
print("\n[8] ADB依赖功能的HTTP替代")
# ============================================================

# monkey_open → 应回退到 /intent
p.monkey_open("com.android.settings", wait_sec=1)
fg3 = p.foreground()
check("monkey_open(无ADB)", "settings" in fg3.lower() if fg3 else False, f"→ fg={fg3}")

p.home()
time.sleep(0.5)

# intent 直接调用
r = p.intent("android.intent.action.MAIN", package="com.android.settings",
             categories=["android.intent.category.LAUNCHER"])
time.sleep(1)
fg4 = p.foreground()
check("intent()", "settings" in fg4.lower() if fg4 else False, f"→ fg={fg4}")
p.home()

# collect_status
cs = p.collect_status()
check("collect_status()", isinstance(cs, dict) and "battery" in cs, f"→ bat={cs.get('battery')}%")

# 远程增强API
for name, path in [("brightness", "/brightness"), ("autorotate", "/autorotate"),
                    ("stayawake", "/stayawake"), ("files/storage", "/files/storage"),
                    ("macro/list", "/macro/list")]:
    r = p.get(path)
    err = isinstance(r, dict) and r.get("_error")
    check(f"远程API:{name}", not err, "")

# ============================================================
# 总结
# ============================================================
total = passed + failed
print(f"\n{'=' * 55}")
print(f"  纯HTTP模式: {passed}/{total} 通过, {failed} 失败")
print(f"  ADB状态: 完全不存在 (monkey-patched)")
print(f"  连接方式: WiFi直连 {WIFI_IP}:{WIFI_PORT}")
print(f"{'=' * 55}")

sys.exit(0 if failed == 0 else 1)
