# -*- coding: utf-8 -*-
"""Agent Task 5 retry: Cross-app navigation with dialog handling"""
import requests, time, json, re
BASE = "http://127.0.0.1:8086"

def observe():
    r = requests.get(f"{BASE}/screen/text", timeout=5).json()
    return {
        "pkg": r.get("package",""),
        "texts": [t.get("text","") for t in r.get("texts",[])],
        "clickables": [c.get("text","") or c.get("label","") for c in r.get("clickables",[])],
        "n": r.get("textCount",0)
    }

def act(ep, data=None, method="GET"):
    try:
        if method == "POST":
            r = requests.post(f"{BASE}{ep}", json=data, timeout=10)
        else:
            r = requests.get(f"{BASE}{ep}", timeout=10)
        try:
            return r.json()
        except Exception:
            return {"ok": r.status_code < 400, "raw": r.text[:100]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def handle_permission_dialog():
    """Handle system permission dialog by finding and tapping the Open button"""
    vt = requests.get(f"{BASE}/viewtree", timeout=5).json()
    vt_str = json.dumps(vt)
    # Find button1 (打开) bounds
    m = re.search(r'"text":"打开".*?"b":"(\d+),(\d+),(\d+),(\d+)"', vt_str)
    if m:
        x = (int(m.group(1)) + int(m.group(3))) // 2
        y = (int(m.group(2)) + int(m.group(4))) // 2
        print(f"  >> Tapping button at ({x},{y})")
        act("/tap", {"x": x, "y": y}, "POST")
        time.sleep(3)
        return True
    return False

print("=== Task 5 retry: Cross-APP chain ===")
t0 = time.time()

# Go home first
act("/home")
time.sleep(1)

# === Part A: Open Alipay ===
print("\n[A] Opening Alipay...")
act("/command", {"command": "打开支付宝"}, "POST")
time.sleep(3)

s = observe()
print(f"  pkg: {s['pkg']} | n: {s['n']} | texts: {s['texts'][:3]}")

# Handle permission dialog
if "securitypermission" in s["pkg"] or any("允许" in t or "想要打开" in t for t in s["texts"]):
    print("  >> Permission dialog detected!")
    # Check "始终允许打开"
    act("/findclick", {"text": "始终允许打开"}, "POST")
    time.sleep(0.3)
    handled = handle_permission_dialog()
    if handled:
        s = observe()
        print(f"  After dialog: pkg: {s['pkg']} | n: {s['n']}")

alipay_ok = "alipay" in s["pkg"].lower() or "com.eg.android" in s["pkg"]
print(f"  Alipay: {'PASS' if alipay_ok else 'FAIL'}")
if alipay_ok:
    print(f"  Texts: {s['texts'][:6]}")

# Go home
act("/home")
time.sleep(1)

# === Part B: Open Calculator ===
print("\n[B] Opening Calculator...")
act("/command", {"command": "打开计算器"}, "POST")
time.sleep(2)

s2 = observe()
calc_ok = "calculator" in s2["pkg"].lower() or "calc" in s2["pkg"].lower()
print(f"  Calculator: {'PASS' if calc_ok else 'FAIL'} (pkg={s2['pkg']})")

# Go home
act("/home")
time.sleep(1)

# === Part C: Open Camera (bonus) ===
print("\n[C] Opening Camera...")
act("/intent", {
    "action": "android.media.action.STILL_IMAGE_CAMERA",
    "flags": ["FLAG_ACTIVITY_NEW_TASK"]
}, "POST")
time.sleep(2)

s3 = observe()
camera_ok = "camera" in s3["pkg"].lower()
print(f"  Camera: {'PASS' if camera_ok else 'FAIL'} (pkg={s3['pkg']})")

# Go home
act("/home")
time.sleep(1)

total_ms = int((time.time() - t0) * 1000)
all_ok = alipay_ok and calc_ok and camera_ok
passed = sum([alipay_ok, calc_ok, camera_ok])
print(f"\n=== Result: {passed}/3 apps opened | {total_ms}ms ===")
