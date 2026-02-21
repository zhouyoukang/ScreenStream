# -*- coding: utf-8 -*-
"""Agent Demo: 5 complex multi-step tasks using Cascade as LLM brain"""
import time, json, sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "http://127.0.0.1:8086"
results = []

def _http(method, path, body=None, timeout=10):
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
    except: return {"_error": -1}

def observe():
    """Read current screen state"""
    r = _http("GET", "/screen/text")
    texts = [t.get("text","") for t in r.get("texts",[])]
    clickables = [c.get("text","") or c.get("label","") for c in r.get("clickables",[])]
    return {
        "pkg": r.get("package",""),
        "texts": texts,
        "clickables": clickables,
        "n": r.get("textCount",0)
    }

def act(endpoint, data=None, method="GET"):
    """Execute an action on the phone"""
    t0 = time.time()
    r = _http(method, endpoint, data)
    ms = int((time.time()-t0)*1000)
    ok = "_error" not in r
    return {"ok": ok, "ms": ms, "data": r}

def wait_ms(ms):
    time.sleep(ms/1000)

def task_report(name, steps, success, detail=""):
    results.append({"name": name, "steps": steps, "success": success, "detail": detail})
    icon = "✅" if success else "❌"
    print(f"  {icon} Task: {name} ({steps} steps) - {detail}")

print("=" * 60)
print("  Agent Demo: 5 Complex Multi-Step Tasks")
print("=" * 60)
t_start = time.time()

# ==================== TASK 1 ====================
# 打开设置 → 直接跳到关于手机 → 提取设备信息
print("\n📱 Task 1: 提取设备完整信息（Intent直跳）")
steps = 0

# Step 1: Intent直跳关于手机
steps += 1
act("/intent", {"action": "android.settings.DEVICE_INFO_SETTINGS",
    "flags": ["FLAG_ACTIVITY_NEW_TASK", "FLAG_ACTIVITY_CLEAR_TASK"]}, "POST")
wait_ms(2000)

# Step 2: 观察
steps += 1
s = observe()
info_texts = s["texts"]
detail = ""
if "关于本机" in " ".join(info_texts) or s["pkg"] == "com.android.settings":
    # 提取设备信息
    model = next((t for t in info_texts if "OnePlus" in t or "NE2210" in t), "?")
    android_ver = next((t for t in info_texts if t in ["15.0", "14", "15", "13"]), "?")
    storage = next((t for t in info_texts if "GB" in t and "/" in t), "?")
    cpu = next((t for t in info_texts if "骁龙" in t or "Snapdragon" in t), "?")
    battery = next((t for t in info_texts if "mAh" in t), "?")
    ram = next((t for t in info_texts if "12.0" in t or "GB" in t and "+" in t), "?")
    detail = f"型号:{model} | Android:{android_ver} | 存储:{storage} | CPU:{cpu} | 电池:{battery}"
    task_report("设备信息提取", steps, True, detail)
else:
    task_report("设备信息提取", steps, False, f"pkg={s['pkg']}, n={s['n']}")

# 回桌面
act("/home")
wait_ms(1500)

# ==================== TASK 2 ====================
# 打开WiFi设置 → 读取WiFi信息 → 返回
print("\n📡 Task 2: WiFi信息提取（Intent直跳）")
steps = 0

steps += 1
act("/intent", {"action": "android.settings.WIFI_SETTINGS",
    "flags": ["FLAG_ACTIVITY_NEW_TASK", "FLAG_ACTIVITY_CLEAR_TASK"]}, "POST")
wait_ms(2000)

steps += 1
s = observe()
wifi_texts = s["texts"]
if "WLAN" in " ".join(wifi_texts) or "Wi-Fi" in " ".join(wifi_texts):
    # 提取WiFi信息
    ssid = next((t for t in wifi_texts if "GHz" in t or "已连接" in t or "CMCC" in t or "WiFi" in t.lower()), "?")
    status = "已连接" if "已连接" in " ".join(wifi_texts) else "未连接"
    detail = f"SSID附近:{ssid} | 状态:{status} | 共{s['n']}项"
    task_report("WiFi信息提取", steps, True, detail)
else:
    task_report("WiFi信息提取", steps, False, f"pkg={s['pkg']}, texts={wifi_texts[:3]}")

act("/home")
wait_ms(1500)

# ==================== TASK 3 ====================
# 打开微信 → 读取最近聊天列表
print("\n💬 Task 3: 微信最近聊天（打开APP+读屏）")
steps = 0

steps += 1
r = act("/command", {"command": "打开微信"}, "POST")
wait_ms(3000)

steps += 1
s = observe()
if "tencent.mm" in s["pkg"]:
    # 提取聊天列表
    chats = [t for t in s["texts"] if len(t) > 1 and t not in ["微信","通讯录","发现","我","搜索"]][:8]
    detail = f"最近聊天: {' | '.join(chats[:5])} ({s['n']}项)"
    task_report("微信聊天列表", steps, True, detail)
else:
    # 可能有权限弹窗
    if "允许" in " ".join(s["texts"]) or "打开" in " ".join(s["clickables"]):
        steps += 1
        # 尝试点击"打开"
        act("/findclick", {"text": "打开"}, "POST")
        wait_ms(2000)
        # 点击"始终允许打开"
        act("/findclick", {"text": "始终允许打开"}, "POST")
        wait_ms(500)
        act("/findclick", {"text": "打开"}, "POST")
        wait_ms(3000)
        s = observe()
        if "tencent.mm" in s["pkg"]:
            chats = [t for t in s["texts"] if len(t) > 1 and t not in ["微信","通讯录","发现","我","搜索"]][:8]
            detail = f"最近聊天: {' | '.join(chats[:5])} ({s['n']}项)"
            task_report("微信聊天列表", steps, True, detail + " [弹窗已处理]")
        else:
            task_report("微信聊天列表", steps, False, f"pkg={s['pkg']}")
    else:
        task_report("微信聊天列表", steps, False, f"pkg={s['pkg']}, n={s['n']}")

act("/home")
wait_ms(1500)

# ==================== TASK 4 ====================
# 电池信息 → 直接Intent
print("\n🔋 Task 4: 电池详情（Intent直跳）")
steps = 0

steps += 1
act("/intent", {"action": "android.intent.action.POWER_USAGE_SUMMARY",
    "flags": ["FLAG_ACTIVITY_NEW_TASK", "FLAG_ACTIVITY_CLEAR_TASK"]}, "POST")
wait_ms(2000)

steps += 1
s = observe()
bat_texts = s["texts"]
if s["pkg"] == "com.android.settings" or "电池" in " ".join(bat_texts):
    pct = next((t for t in bat_texts if "%" in t), "?")
    charging = "充电中" if "充电" in " ".join(bat_texts) else "未充电"
    detail = f"电量:{pct} | {charging} | 共{s['n']}项"
    task_report("电池详情", steps, True, detail)
else:
    task_report("电池详情", steps, False, f"pkg={s['pkg']}")

act("/home")
wait_ms(1500)

# ==================== TASK 5 ====================
# 复杂跨APP: 打开支付宝 → 读首页 → 返回 → 打开计算器 → 读首页 → 返回
print("\n🔄 Task 5: 跨APP串联（支付宝→计算器→桌面）")
steps = 0

def handle_oem_dialog(max_retries=3):
    """Handle OEM permission/battery dialogs (OPPO/OnePlus common)"""
    for i in range(max_retries):
        s = observe()
        pkg = s["pkg"].lower()
        texts_joined = " ".join(s["texts"])
        # Check if we're stuck in a system dialog
        if "battery" in pkg or "securitypermission" in pkg or "permissioncontroller" in pkg:
            # Try common dismiss buttons
            for btn in ["允许", "打开", "始终允许打开", "确定", "跳过"]:
                if btn in texts_joined:
                    act("/findclick", {"text": btn}, "POST")
                    wait_ms(1500)
                    break
            else:
                act("/back", method="POST")
                wait_ms(1000)
        else:
            return s
    return observe()

# 打开支付宝 (use /command which internally uses monkey - more reliable on OPPO/OnePlus)
steps += 1
act("/command", {"command": "打开支付宝"}, "POST")
wait_ms(4000)

steps += 1
s1 = observe()
alipay_ok = "alipay" in s1["pkg"].lower() or "com.eg.android" in s1["pkg"]
if not alipay_ok:
    # OEM may intercept with battery/permission dialog
    steps += 1
    s1 = handle_oem_dialog()
    alipay_ok = "alipay" in s1["pkg"].lower() or "com.eg.android" in s1["pkg"]

alipay_detail = f"pkg:{s1['pkg'].split('.')[-1]} | {s1['n']}项" if alipay_ok else f"pkg:{s1['pkg']}"

# 回桌面
steps += 1
act("/home")
wait_ms(1000)

# 打开计算器 (use /command)
steps += 1
act("/command", {"command": "打开计算器"}, "POST")
wait_ms(2000)

steps += 1
s2 = observe()
calc_ok = "calculator" in s2["pkg"].lower() or "calc" in s2["pkg"].lower() or "coloros" in s2["pkg"].lower()
calc_detail = f"pkg:{s2['pkg'].split('.')[-1]} | {s2['n']}项" if calc_ok else f"pkg:{s2['pkg']}"

# 回桌面
steps += 1
act("/home")
wait_ms(1000)

both_ok = alipay_ok and calc_ok
detail = f"支付宝:{alipay_detail} → 计算器:{calc_detail}"
task_report("跨APP串联", steps, both_ok, detail)

# ==================== SUMMARY ====================
total_time = int((time.time() - t_start) * 1000)
passed = sum(1 for r in results if r["success"])
total = len(results)

print("\n" + "=" * 60)
print(f"  结果: {passed}/{total} 通过 | 总耗时: {total_time}ms")
print("=" * 60)

for r in results:
    icon = "✅" if r["success"] else "❌"
    print(f"  {icon} {r['name']} ({r['steps']}步): {r['detail'][:80]}")

print("=" * 60)
sys.exit(0 if passed == total else 1)
