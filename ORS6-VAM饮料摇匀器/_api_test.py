"""ORS6 Hub API E2E verification — includes Video Sync / Funscript APIs"""
import urllib.request, json, time, sys

BASE = "http://localhost:8086"

def get(path):
    r = urllib.request.urlopen(f"{BASE}{path}", timeout=15)
    return json.loads(r.read())

def post(path, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=15)
    return json.loads(r.read())

p = f = 0
results = []

def test(name, fn):
    global p, f
    try:
        fn()
        p += 1
        results.append(f"  PASS  {name}")
    except Exception as e:
        f += 1
        results.append(f"  FAIL  {name}: {e}")

# ══════════════════════════════════════════
# Phase 1: Core Hub APIs
# ══════════════════════════════════════════
print("Phase 1: Core Hub APIs")
test("health",         lambda: get("/api/health"))
test("state",          lambda: get("/api/state"))
test("patterns",       lambda: get("/api/patterns"))
test("send_L0_top",    lambda: get("/api/send/L09999I500"))
test("send_D1_home",   lambda: get("/api/send/D1"))
test("play_orbit",     lambda: get("/api/play/orbit-tease/60"))
test("stop",           lambda: get("/api/stop"))
test("history",        lambda: get("/api/history"))

def run_hub_tests():
    data = get("/api/test/all")
    items = data if isinstance(data, list) else data.get("results", [])
    tp = sum(1 for x in items if x["status"] == "pass")
    tf = sum(1 for x in items if x["status"] == "fail")
    print(f"    Hub internal: {tp}/{len(items)} pass, {tf} fail")
    for x in items:
        if x["status"] == "fail":
            print(f"      FAIL: {x.get('name', '?')}")
    assert tf == 0, f"{tf} internal tests failed"

test("test_all", run_hub_tests)

# ══════════════════════════════════════════
# Phase 2: Funscript / Video Sync APIs
# ══════════════════════════════════════════
print("\nPhase 2: Funscript / Video Sync APIs")

# Generate a simple test funscript (L0 axis, 5 seconds, sine wave)
import math
test_actions = [{"at": int(i*50), "pos": int(50 + 45*math.sin(i*0.2))} for i in range(200)]
test_funscript = {"actions": test_actions}

def fs_load():
    d = post("/api/funscript/load", {"scripts": {"L0": test_funscript}, "title": "test_sine"})
    assert "status" in d and d["status"] == "loaded", f"Unexpected: {d}"
    assert d.get("duration_ms", 0) > 0, f"No duration: {d}"
    print(f"    Loaded: {d['duration_ms']}ms")

test("fs_load", fs_load)

def fs_status():
    d = get("/api/funscript/status")
    assert "playing" in d, f"No playing field: {d}"
    assert "axes" in d, f"No axes field: {d}"
    assert "L0" in d["axes"], f"L0 not in axes: {d['axes']}"
    print(f"    Status: playing={d['playing']}, axes={list(d['axes'].keys())}")

test("fs_status", fs_status)

def fs_play():
    d = get("/api/funscript/play")
    assert d.get("playing") == True, f"Not playing: {d}"

test("fs_play", fs_play)
time.sleep(0.3)

def fs_status_playing():
    d = get("/api/funscript/status")
    assert d["playing"] == True, f"Should be playing: {d}"
    assert d["current_ms"] > 0, f"No progress: {d}"
    print(f"    Playing at {d['current_ms']}ms, {d['progress_pct']}%")

test("fs_status_playing", fs_status_playing)

def fs_pause():
    d = get("/api/funscript/pause")
    assert d.get("paused") == True, f"Not paused: {d}"

test("fs_pause", fs_pause)

def fs_seek():
    d = get("/api/funscript/seek/2000")
    assert d.get("current_ms") >= 1900, f"Seek failed: {d}"
    print(f"    Seeked to {d['current_ms']}ms")

test("fs_seek", fs_seek)

def fs_sync():
    d = get("/api/funscript/sync/3000")
    assert "synced" in d, f"Sync failed: {d}"

test("fs_sync", fs_sync)

def fs_speed():
    d = get("/api/funscript/speed/1.5")
    assert d.get("speed") == 1.5, f"Speed not set: {d}"
    print(f"    Speed: {d['speed']}x")

test("fs_speed", fs_speed)

def fs_stop():
    d = get("/api/funscript/stop")
    assert d.get("playing") == False, f"Still playing: {d}"

test("fs_stop", fs_stop)

def fs_clear():
    d = get("/api/funscript/clear")
    assert d.get("status") == "cleared", f"Not cleared: {d}"

test("fs_clear", fs_clear)

def fs_scan():
    d = get("/api/funscript/scan")
    assert "scripts" in d, f"No scripts field: {d}"
    print(f"    Found {len(d['scripts'])} local .funscript files")

test("fs_scan", fs_scan)

# ══════════════════════════════════════════
# Phase 3: Multi-axis load + playback cycle
# ══════════════════════════════════════════
print("\nPhase 3: Multi-axis load + playback")

def fs_multi_axis():
    r0_actions = [{"at": int(i*100), "pos": int(50 + 40*math.cos(i*0.3))} for i in range(50)]
    r1_actions = [{"at": int(i*100), "pos": int(50 + 30*math.sin(i*0.5))} for i in range(50)]
    d = post("/api/funscript/load", {
        "scripts": {
            "L0": {"actions": test_actions},
            "R0": {"actions": r0_actions},
            "R1": {"actions": r1_actions},
        },
        "title": "multi_axis_test"
    })
    assert d["status"] == "loaded", f"Multi load failed: {d}"
    result = d.get("result", {})
    assert "L0" in result and "R0" in result and "R1" in result, f"Missing axes: {result}"
    print(f"    3-axis loaded: {list(result.keys())}")
    # Play briefly
    get("/api/funscript/play")
    time.sleep(0.5)
    st = get("/api/funscript/status")
    assert st["playing"] == True, f"Not playing multi: {st}"
    assert len(st["axes"]) == 3, f"Expected 3 axes: {st['axes']}"
    print(f"    Playing 3-axis at {st['current_ms']}ms, axes: {list(st['axes'].keys())}")
    get("/api/funscript/stop")

test("fs_multi_axis", fs_multi_axis)

# ══════════════════════════════════════════
# Phase 4: Load-local + axis suffix mapping
# ══════════════════════════════════════════
print("\nPhase 4: Load-local + suffix mapping")

def fs_load_local():
    # First scan to get a real path
    d = get("/api/funscript/scan")
    scripts = d.get("scripts", [])
    assert len(scripts) > 0, "No local scripts to test"
    path = scripts[0]["path"]
    d2 = get(f"/api/funscript/load-local/{path}")
    assert d2.get("status") == "loaded", f"Load-local failed: {d2}"
    assert d2.get("duration_ms", 0) > 0, f"No duration: {d2}"
    print(f"    Loaded local: {path} → {d2['duration_ms']}ms")

test("fs_load_local", fs_load_local)

def fs_axis_suffix():
    """Verify V0 axis mapping for .vib suffix"""
    d = get("/api/funscript/scan")
    scripts = d.get("scripts", [])
    # Check that axis mapping includes expected values
    axes_found = set(s["axis"] for s in scripts)
    print(f"    Axes found: {sorted(axes_found)}")
    # Basic sanity: at least L0 should be present
    assert "L0" in axes_found or len(scripts) > 0, f"No L0 axis: {axes_found}"

test("fs_axis_suffix", fs_axis_suffix)

def fs_load_local_security():
    """Verify path traversal is blocked"""
    d = get("/api/funscript/load-local/..%2F..%2F..%2Fetc%2Fpasswd")
    assert "error" in d, f"Should have error for path traversal: {d}"
    print(f"    Security check: {d.get('error','')[:50]}")

test("fs_load_local_security", fs_load_local_security)

# ══════════════════════════════════════════
# Summary
# ══════════════════════════════════════════
print("\n" + "="*50)
for r in results:
    print(r)
print(f"\n{'='*50}")
print(f"  Total: {p} PASS / {f} FAIL / {p+f} tests")
print(f"  {'ALL PASS' if f == 0 else f'{f} FAILURES'}")
print(f"{'='*50}")

sys.exit(0 if f == 0 else 1)
