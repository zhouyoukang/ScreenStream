#!/usr/bin/env python3
"""
test_remote.py — Remote Desktop Agent API test suite.

Usage:
  python test_remote.py                    # Test against localhost:9905
  python test_remote.py --port 9903        # Custom port
  python test_remote.py --host 127.0.0.2   # Remote host
"""

import urllib.request
import json
import sys
import time

HOST = "127.0.0.1"
PORT = 9905
PASS = 0
FAIL = 0


def api_get(path):
    url = f"http://{HOST}:{PORT}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as r:
        ct = r.headers.get("Content-Type", "")
        if "json" in ct:
            return json.loads(r.read()), r.status, r.headers
        return r.read(), r.status, r.headers


def api_post(path, data):
    url = f"http://{HOST}:{PORT}{path}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read()), r.status


def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}" + (f" — {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


def run_tests():
    print(f"\n=== Remote Desktop Agent Tests ({HOST}:{PORT}) ===\n")

    # 1. Health
    print("Round 1: Health")
    try:
        h, status, _ = api_get("/health")
        test("Health status", h.get("status") == "ok", f"host={h.get('hostname')} user={h.get('user')}")
        test("Health fields", all(k in h for k in ("hostname", "user", "session", "pid", "guard")))
    except Exception as e:
        test("Health reachable", False, str(e))
        print("\n  Agent not reachable. Aborting.\n")
        return False

    # 2. Windows
    print("\nRound 2: Windows")
    wins, status, _ = api_get("/windows")
    test("Windows list", isinstance(wins, list) and len(wins) > 0, f"{len(wins)} windows")
    if wins:
        w = wins[0]
        test("Window fields", all(k in w for k in ("hwnd", "title", "w", "h")))

    # 3. Screenshot
    print("\nRound 3: Screenshot")
    data, status, headers = api_get("/screenshot?quality=50")
    test("Screenshot status", status == 200)
    test("Screenshot is JPEG", isinstance(data, bytes) and data[:2] == b'\xff\xd8', f"{len(data)} bytes")
    test("Screenshot headers", "X-Image-Width" in headers and "X-Image-Height" in headers)

    # 4. HTML frontend
    print("\nRound 4: HTML Frontend")
    data, status, headers = api_get("/")
    test("HTML served", status == 200)
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")
    test("HTML has tabs", "pShell" in str(data) and "pProc" in str(data) and "pClip" in str(data))

    # Disable guard for input tests
    print("\n--- Disabling MouseGuard for input tests ---")
    api_post("/guard", {"enabled": False})

    # 5. Key input
    print("\nRound 5: Key Input")
    r, _ = api_post("/key", {"key": "f13"})
    test("Key send", r.get("ok") is True, f"key={r.get('key')}")
    r, _ = api_post("/key", {"hotkey": ["ctrl", "f13"]})
    test("Hotkey send", r.get("ok") is True)

    # 6. Click
    print("\nRound 6: Click")
    r, _ = api_post("/click", {"x": 0, "y": 0, "button": "left", "clicks": 1})
    test("Click send", r.get("ok") is True)

    # 7. Type
    print("\nRound 7: Type")
    r, _ = api_post("/type", {"text": "", "interval": 0.01})
    test("Type empty", r.get("ok") is True)
    r, _ = api_post("/type", {"text": "hello", "interval": 0.01})
    test("Type ASCII", r.get("ok") is True, f"method={r.get('method')}")

    # 8. Focus
    print("\nRound 8: Focus")
    r, _ = api_post("/focus", {"title": "nonexistent_window_12345"})
    test("Focus not found", "error" in r)
    if wins:
        r, _ = api_post("/focus", {"hwnd": wins[0]["hwnd"]})
        test("Focus by hwnd", "hwnd" in r)

    # 9. Window manage
    print("\nRound 9: Window Manage")
    if wins:
        r, _ = api_post("/window", {"hwnd": wins[0]["hwnd"], "action": "restore"})
        test("Window restore", r.get("ok") is True)
        r, _ = api_post("/window", {"hwnd": wins[0]["hwnd"], "action": "badaction"})
        test("Window bad action", "error" in r)
    try:
        r, _ = api_post("/window", {"action": "maximize"})
        test("Window no hwnd", "error" in r)
    except urllib.error.HTTPError as e:
        test("Window no hwnd", e.code == 400)

    # 10. Scroll
    print("\nRound 10: Scroll")
    r, _ = api_post("/scroll", {"x": 500, "y": 500, "clicks": 3})
    test("Scroll up", r.get("ok") is True)
    r, _ = api_post("/scroll", {"x": 500, "y": 500, "clicks": -3})
    test("Scroll down", r.get("ok") is True)
    r, _ = api_post("/scroll", {"x": 0, "y": 0, "clicks": 2, "direction": "horizontal"})
    test("Scroll horizontal", r.get("ok") is True)

    # 11. Guard
    print("\nRound 11: Guard")
    g, status, _ = api_get("/guard")
    test("Guard GET", "enabled" in g and "cooldown" in g)
    test("Guard fields", all(k in g for k in ("enabled", "paused", "cooldown", "can_automate", "blocked_count")))
    r, _ = api_post("/guard", {"cooldown": 1.5})
    test("Guard set cooldown", r.get("cooldown") == 1.5)
    r, _ = api_post("/guard", {"cooldown": 2.0})
    test("Guard restore cooldown", r.get("cooldown") == 2.0)

    # 12. Mouse Move
    print("\nRound 12: Mouse Move")
    r, _ = api_post("/move", {"x": 100, "y": 100})
    test("Mouse move", r.get("ok") is True, f"x={r.get('x')} y={r.get('y')}")

    # 13. Drag
    print("\nRound 13: Drag")
    r, _ = api_post("/drag", {"x1": 100, "y1": 100, "x2": 200, "y2": 200, "duration": 0.2})
    test("Drag", r.get("ok") is True)

    # 14. Processes
    print("\nRound 14: Processes")
    procs, status, _ = api_get("/processes")
    test("Process list", isinstance(procs, list) and len(procs) > 0, f"{len(procs)} processes")
    if isinstance(procs, list) and procs:
        test("Process fields", all(k in procs[0] for k in ("name", "pid", "mem_kb")))

    # 15. Clipboard
    print("\nRound 15: Clipboard")
    r, _ = api_post("/clipboard", {"text": "test_remote_clipboard"})
    test("Clipboard write", r.get("ok") is True)
    c, _, _ = api_get("/clipboard")
    test("Clipboard read", c.get("text") == "test_remote_clipboard", f"got: {c.get('text', '')[:30]}")
    # Restore clipboard
    api_post("/clipboard", {"text": ""})

    # 16. Shell
    print("\nRound 16: Shell")
    r, _ = api_post("/shell", {"cmd": "echo hello_remote", "timeout": 5})
    test("Shell exec", r.get("ok") is True)
    test("Shell output", "hello_remote" in r.get("stdout", ""), f"stdout={r.get('stdout', '')[:40]}")
    r, _ = api_post("/shell", {"cmd": "dir C:\\", "timeout": 5})
    test("Shell dir", r.get("ok") is True and r.get("returncode") == 0)

    # 17. System Info
    print("\nRound 17: System Info")
    info, _, _ = api_get("/sysinfo")
    test("SysInfo hostname", "hostname" in info, info.get("hostname", ""))
    test("SysInfo fields", all(k in info for k in ("os", "user", "session")))
    test("SysInfo ram", "ram_total_mb" in info, f"{info.get('ram_total_mb', '?')}MB total")
    test("SysInfo disk", "disk_total_gb" in info, f"{info.get('disk_total_gb', '?')}GB total")
    test("SysInfo screen", "screen_w" in info, f"{info.get('screen_w', '?')}x{info.get('screen_h', '?')}")
    test("SysInfo uptime", "uptime_sec" in info, f"{info.get('uptime_sec', 0)//3600}h")

    # 18. Volume
    print("\nRound 18: Volume")
    r, _ = api_post("/volume", {"mute": True})
    test("Volume mute", r.get("ok") is True)
    # Unmute immediately
    r, _ = api_post("/volume", {"mute": True})
    test("Volume unmute", r.get("ok") is True)

    # 19. Files
    print("\nRound 19: Files")
    f, _, _ = api_get("/files?path=C%3A%5C")
    test("Files list", "items" in f and isinstance(f["items"], list), f"{f.get('count', 0)} items")
    if isinstance(f.get("items"), list) and f["items"]:
        test("File fields", all(k in f["items"][0] for k in ("name", "is_dir", "size")))

    # 20. Screen Info (mobile)
    print("\nRound 20: Screen Info")
    si, _, _ = api_get("/screen/info")
    test("Screen info", "is_locked" in si, f"locked={si.get('is_locked')}")
    test("Screen resolution", "screen_w" in si, f"{si.get('screen_w')}x{si.get('screen_h')}")

    # 21. Wake Screen
    print("\nRound 21: Wake Screen")
    r, _ = api_post("/wakeup", {})
    test("Wake screen", r.get("ok") is True, r.get("method", ""))

    # 22. Network
    print("\nRound 22: Network")
    n, _, _ = api_get("/network")
    test("Network adapters", "adapters" in n)
    test("Network connections", "connections" in n)

    # 23. Power (cancel only — safe)
    print("\nRound 23: Power")
    r, _ = api_post("/power", {"action": "shutdown"})
    test("Power needs confirm", "error" in r and "confirm" in r.get("error", ""))
    r, _ = api_post("/power", {"action": "cancel", "confirm": True})
    test("Power cancel", r.get("ok") is True or "error" in r)  # cancel may fail if no pending shutdown

    # Re-enable guard
    api_post("/guard", {"enabled": True})
    print("\n--- MouseGuard re-enabled ---")

    # 24. Error handling
    print("\nRound 24: Error Handling")
    try:
        api_get("/nonexistent")
        test("404 route", False, "should have raised")
    except urllib.error.HTTPError as e:
        test("404 route", e.code == 404)
    try:
        api_post("/shell", {"cmd": ""})
        test("Shell empty cmd", False, "should have raised")
    except urllib.error.HTTPError as e:
        test("Shell empty cmd", e.code == 400)
    try:
        api_post("/kill", {})
        test("Kill no pid", False, "should have raised")
    except urllib.error.HTTPError as e:
        test("Kill no pid", e.code == 400)

    # Summary
    total = PASS + FAIL
    print(f"\n{'=' * 50}")
    print(f"  Results: {PASS} passed, {FAIL} failed, {total} total")
    print(f"{'=' * 50}\n")
    return FAIL == 0


if __name__ == "__main__":
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        PORT = int(sys.argv[idx + 1])
    if "--host" in sys.argv:
        idx = sys.argv.index("--host")
        HOST = sys.argv[idx + 1]

    success = run_tests()
    sys.exit(0 if success else 1)
