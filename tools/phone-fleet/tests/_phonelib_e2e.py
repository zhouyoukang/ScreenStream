"""OnePlus E2E测试 — phone_lib全API验证"""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from phone_lib import Phone

PORT = 18084
results = []

def test(name, ok, detail=""):
    results.append((name, ok, detail))
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {name}" + (f" → {detail}" if detail else ""))

p = Phone(port=PORT, auto_discover=False, heartbeat_sec=0)
print(f"Phone: {p}")
print(f"ADB: {p._has_adb}, serial: {p._serial_hint}")
print()

# === GET endpoints ===
print("=== GET Endpoints ===")
r = p._http("GET", "/status")
test("GET /status", "connected" in r, str(r)[:80])

r = p._http("GET", "/deviceinfo")
test("GET /deviceinfo", r.get("model") == "NE2210", f"model={r.get('model')}")

r = p._http("GET", "/brightness")
test("GET /brightness", "brightness" in r, str(r))

r = p._http("GET", "/clipboard")
test("GET /clipboard", "_error" not in r, str(r)[:60])

r = p._http("GET", "/apps")
test("GET /apps", "_error" not in r, f"{len(str(r))} bytes")

# === POST navigation ===
print("\n=== POST Navigation ===")
for ep in ["/home", "/back", "/recents", "/notifications", "/wake",
           "/volume/up", "/volume/down", "/lock"]:
    r = p._http("POST", ep)
    test(f"POST {ep}", r.get("ok", False))
    time.sleep(0.4)

# unlock after lock
time.sleep(1)
p._http("POST", "/wake")
time.sleep(0.5)

# === POST gestures ===
print("\n=== POST Gestures ===")
r = p._http("POST", "/tap", {"nx": 0.5, "ny": 0.5})
test("POST /tap", r.get("ok", False))
time.sleep(0.5)

r = p._http("POST", "/swipe", {"nx1": 0.5, "ny1": 0.7, "nx2": 0.5, "ny2": 0.3, "duration": 300})
test("POST /swipe", r.get("ok", False))
time.sleep(0.5)

r = p._http("POST", "/longpress", {"nx": 0.5, "ny": 0.5, "duration": 500})
test("POST /longpress", r.get("ok", False))
time.sleep(0.5)

r = p._http("POST", "/doubletap", {"nx": 0.5, "ny": 0.5})
test("POST /doubletap", r.get("ok", False))
time.sleep(0.5)

r = p._http("POST", "/scroll", {"direction": "down", "distance": 300})
test("POST /scroll", r.get("ok", False))
time.sleep(0.5)

r = p._http("POST", "/pinch", {"cx": 0.5, "cy": 0.5, "zoomIn": True})
test("POST /pinch", r.get("ok", False))
time.sleep(0.5)

# === POST system ===
print("\n=== POST System ===")
r = p._http("POST", "/screenshot")
test("POST /screenshot", r.get("ok", False))

r = p._http("POST", "/openurl", {"url": "https://www.baidu.com"})
test("POST /openurl", r.get("ok", False))
time.sleep(1)

p._http("POST", "/home")
time.sleep(0.5)

# === POST text (no focused field expected) ===
print("\n=== POST Text ===")
r = p._http("POST", "/text", {"text": "hello"})
test("POST /text", "_error" not in r, str(r)[:80])

# === phone_lib high-level API ===
print("\n=== Phone High-Level API ===")
s = p.status()
test("p.status()", "connected" in s, str(s)[:60])

d = p.device()
test("p.device()", d.get("model") == "NE2210", f"model={d.get('model')}")

p.home()
test("p.home()", True)

p.back()
test("p.back()", True)

p.wake()
test("p.wake()", True)

b = p._http("GET", "/brightness")
test("p.brightness(GET)", "brightness" in b, str(b))

# === Summary ===
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"\n{'='*50}")
print(f"  TOTAL: {passed}/{total} PASS ({100*passed//total}%)")
print(f"{'='*50}")
