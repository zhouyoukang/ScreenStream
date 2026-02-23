"""
实际操作手机 — 无ADB，纯WiFi HTTP
====================================
模拟真实远程用户：投屏观看 + 全功能操控 + 诊断
"""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 强制移除ADB
import phone_lib
phone_lib._find_adb = lambda: None
phone_lib._adb_available = lambda: False
phone_lib._usb_serial_cache = ""

from phone_lib import Phone, NegativeState

WIFI_IP = "192.168.10.122"
WIFI_PORT = 8086
p = Phone(host=WIFI_IP, port=WIFI_PORT, auto_discover=False, retry=1)

results = []

def step(name, fn, wait=0.5):
    """执行一步操作并记录"""
    try:
        r = fn()
        time.sleep(wait)
        results.append(("✅", name))
        return r
    except Exception as e:
        results.append(("❌", name, str(e)))
        print(f"  ❌ {name}: {e}")
        return None

def see():
    """看屏幕"""
    texts, pkg = p.read()
    fg_short = pkg.split(".")[-1] if pkg else "?"
    visible = [t for t in texts if t.strip()][:8]
    print(f"  👁 [{fg_short}] {', '.join(visible[:5])}")
    return texts, pkg

# ============================================================
print("=" * 55)
print("  实际操作手机 (无ADB, 纯WiFi HTTP)")
print(f"  目标: {WIFI_IP}:{WIFI_PORT}")
print("=" * 55)

# ============================================================
print("\n[0] 投屏与连接确认")
# ============================================================
s = p.status()
print(f"  连接: {'✅' if s.get('connected') else '❌'}")
print(f"  输入: {'✅' if s.get('inputEnabled') else '❌'}")
print(f"  MJPEG投屏流: http://{WIFI_IP}:8081")
print(f"  (在浏览器打开上述URL即可看到手机屏幕实时画面)")

dev = p.device()
print(f"  设备: {dev.get('manufacturer','')} {dev.get('model','')}")
print(f"  电量: {dev.get('batteryLevel',-1)}%")
print(f"  网络: {dev.get('networkType','?')}")

# ============================================================
print("\n[1] 回桌面 + 读取桌面信息")
# ============================================================
step("回桌面", lambda: p.home(), 1)
texts, pkg = see()
results.append(("✅", f"桌面: {pkg}"))

# ============================================================
print("\n[2] 打开设置")
# ============================================================
step("打开设置(intent)", lambda: p.intent(
    "android.intent.action.MAIN",
    package="com.android.settings",
    categories=["android.intent.category.LAUNCHER"]), 2)
texts, pkg = see()
in_settings = "settings" in (pkg or "").lower()
results.append(("✅" if in_settings else "❌", f"设置页: {pkg}"))

# ============================================================
print("\n[3] 在设置中导航 — 点击'关于手机'")
# ============================================================
# 先滑到底部
step("下滑", lambda: p.swipe("down"), 0.5)
step("下滑", lambda: p.swipe("down"), 0.5)
step("下滑", lambda: p.swipe("down"), 0.5)
texts, _ = see()

# 尝试点击关于手机
for kw in ["关于手机", "关于本机", "About phone", "About"]:
    r = p.click(kw)
    if r.get("ok"):
        print(f"  ✅ 点击了: {kw}")
        results.append(("✅", f"点击: {kw}"))
        time.sleep(1)
        break
else:
    print(f"  ⚠️ 未找到'关于手机'按钮")
    results.append(("⏭️", "关于手机未找到"))

see()

# ============================================================
print("\n[4] 返回桌面 + 打开浏览器")
# ============================================================
step("返回", lambda: p.back(), 0.5)
step("返回", lambda: p.back(), 0.5)
step("回桌面", lambda: p.home(), 1)

# 用intent打开浏览器
step("打开浏览器", lambda: p.intent(
    "android.intent.action.VIEW",
    data="https://www.baidu.com"), 3)
texts, pkg = see()
results.append(("✅", f"浏览器: {pkg}"))

# ============================================================
print("\n[5] 在浏览器中输入文本")
# ============================================================
# 点击搜索框
for kw in ["搜索", "搜索框", "Search", "百度一下"]:
    r = p.click(kw)
    if r.get("ok"):
        print(f"  ✅ 点击了: {kw}")
        time.sleep(1)
        break

# 输入文本
step("输入文本", lambda: p.post("/text", {"text": "远程操控测试"}), 0.5)
see()

# 按回车搜索
step("回车搜索", lambda: [
    p.post("/key", {"keysym": 0xFF0D, "down": True}),
    p.post("/key", {"keysym": 0xFF0D, "down": False})
], 2)
texts, pkg = see()

# ============================================================
print("\n[6] 回桌面 + monkey_open打开ScreenStream")
# ============================================================
step("回桌面", lambda: p.home(), 1)
step("monkey_open(无ADB→intent)", lambda: p.monkey_open(
    "info.dvkr.screenstream.dev", wait_sec=2), 1)
texts, pkg = see()
in_ss = "screenstream" in (pkg or "").lower()
results.append(("✅" if in_ss else "❌", f"ScreenStream: {pkg}"))

# ============================================================
print("\n[7] 剪贴板读写")
# ============================================================
step("剪贴板写入", lambda: p.clipboard_write("hello_from_remote"), 0.3)
clip = p.clipboard_read()
print(f"  剪贴板读取: {clip}")
results.append(("✅" if clip == "hello_from_remote" else "⚠️", f"剪贴板: {clip}"))

# ============================================================
print("\n[8] 通知读取")
# ============================================================
n = p.notifications(10)
total = n.get("total", 0)
items = n.get("notifications", [])
print(f"  通知总数: {total}")
for item in items[:5]:
    app = item.get("package", "").split(".")[-1]
    title = item.get("title", "")
    print(f"    [{app}] {title}")
results.append(("✅", f"通知: {total}条"))

# ============================================================
print("\n[9] 五感全采集")
# ============================================================
senses = p.senses()
if senses.get("_ok"):
    v = senses["vision"]
    h = senses["hearing"]
    t = senses["touch"]
    sm = senses["smell"]
    ta = senses["taste"]
    print(f"  👁 视觉: fg={v['foreground_app'].split('.')[-1]}, texts={v['text_count']}")
    print(f"  👂 听觉: vol={h['volume_music']}, dnd={h['dnd']}")
    print(f"  🖐 触觉: input={t['input_enabled']}, scale={t['scaling']}")
    print(f"  👃 嗅觉: notif={sm['notification_count']}")
    print(f"  👅 味觉: bat={ta['battery']}%, net={ta['network']}, free={ta['storage_free_gb']}GB")
    print(f"           model={ta['model']}, wifi={ta['wifi_ssid']}")
    results.append(("✅", "五感全采集"))
else:
    print(f"  ❌ 五感采集失败: {senses.get('_error','?')}")
    results.append(("❌", "五感采集失败"))

# ============================================================
print("\n[10] 设备诊断报告")
# ============================================================
health = p.health()
print(f"  健康: {health.get('state')} (healthy={health.get('healthy')})")
print(f"  ADB: {health.get('has_adb')} (我们已移除)")
if health.get("battery"):
    print(f"  电量: {health['battery']}%")
if health.get("network"):
    print(f"  网络: {health['network']}")
results.append(("✅", f"诊断: {health.get('state')}"))

# ============================================================
print("\n[11] 负面状态叠加检测")
# ============================================================
issues = NegativeState.detect_all(p)
print(f"  检测到: {len(issues)}个问题")
for state, detail in issues:
    print(f"    ⚠️ {state}: {detail}")
results.append(("✅", f"叠加检测: {len(issues)}问题"))

alive, log = p.ensure_alive()
print(f"  ensure_alive: {'✅' if alive else '❌'}")
results.append(("✅" if alive else "❌", "ensure_alive"))

# ============================================================
print("\n[12] 远程增强API")
# ============================================================
brightness = p.get("/brightness")
print(f"  亮度: {brightness.get('brightness', '?')}")

autorotate = p.get("/autorotate")
print(f"  自动旋转: {autorotate.get('autoRotate', '?')}")

stayawake = p.get("/stayawake")
print(f"  保持唤醒: {stayawake.get('stayAwake', '?')}")

storage = p.get("/files/storage")
print(f"  文件存储: {'✅ 可达' if not storage.get('_error') else '❌'}")

macros = p.get("/macro/list")
print(f"  宏列表: {'✅ 可达' if isinstance(macros, (dict, list)) else '❌'}")

results.append(("✅", "远程增强API"))

# ============================================================
print("\n[13] 回桌面收尾")
# ============================================================
step("回桌面", lambda: p.home(), 1)
see()

# ============================================================
# 总结
# ============================================================
ok_count = sum(1 for r in results if r[0] == "✅")
fail_count = sum(1 for r in results if r[0] == "❌")
skip_count = sum(1 for r in results if r[0] == "⏭️")
total = ok_count + fail_count + skip_count

print(f"\n{'=' * 55}")
print(f"  实操结果: {ok_count}/{total} 通过, {fail_count} 失败, {skip_count} 跳过")
print(f"  ADB状态: 完全移除")
print(f"  连接方式: WiFi直连 {WIFI_IP}:{WIFI_PORT}")
print(f"  MJPEG投屏: http://{WIFI_IP}:8081")
print(f"{'=' * 55}")

# 详细结果
print("\n详细结果:")
for r in results:
    print(f"  {r[0]} {r[1]}")

sys.exit(0 if fail_count == 0 else 1)
