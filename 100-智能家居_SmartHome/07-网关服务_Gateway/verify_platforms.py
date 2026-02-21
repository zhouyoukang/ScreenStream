#!/usr/bin/env python3
"""
智能家居平台连通性验证脚本
验证: Gateway / Home Assistant / 涂鸦 / ScreenStream 智能家居路由
"""

import sys
import json
import time

try:
    import httpx
except ImportError:
    print("[!] httpx not installed. Run: pip install httpx")
    sys.exit(1)

# ============================================================
# Configuration — 按需修改
# ============================================================
GATEWAY_URL = "http://127.0.0.1:8900"
HA_URL = "http://192.168.31.228:8123"
HA_TOKEN = ""  # 填入你的 HA Long-Lived Token
SS_URL = ""    # ScreenStream API URL, e.g. http://192.168.31.100:8086

PASS = "\033[92m PASS \033[0m"
FAIL = "\033[91m FAIL \033[0m"
SKIP = "\033[93m SKIP \033[0m"

results = []


def test(name: str, fn):
    try:
        ok, detail = fn()
        status = PASS if ok else FAIL
        results.append((name, ok, detail))
        print(f"  [{status}] {name}: {detail}")
    except Exception as e:
        results.append((name, False, str(e)))
        print(f"  [{FAIL}] {name}: {e}")


def skip(name: str, reason: str):
    results.append((name, None, reason))
    print(f"  [{SKIP}] {name}: {reason}")


# ============================================================
# 1. Gateway Tests
# ============================================================
print("\n=== 1. Smart Home Gateway ===")


def test_gateway_status():
    r = httpx.get(f"{GATEWAY_URL}/", timeout=5)
    d = r.json()
    return r.status_code == 200 and "gateway" in d, f"status={r.status_code}, gateway={d.get('gateway','?')}"

test("Gateway status", test_gateway_status)


def test_gateway_devices():
    r = httpx.get(f"{GATEWAY_URL}/devices", timeout=10)
    d = r.json()
    count = d.get("count", 0)
    return r.status_code == 200, f"status={r.status_code}, devices={count}"

test("Gateway devices", test_gateway_devices)


def test_gateway_scenes():
    r = httpx.get(f"{GATEWAY_URL}/scenes", timeout=10)
    d = r.json()
    count = d.get("count", 0)
    return r.status_code == 200, f"status={r.status_code}, scenes={count}"

test("Gateway scenes", test_gateway_scenes)


def test_gateway_services():
    r = httpx.get(f"{GATEWAY_URL}/services", timeout=10)
    return r.status_code == 200, f"status={r.status_code}, services loaded"

test("Gateway services", test_gateway_services)


# ============================================================
# 2. Home Assistant Direct Tests
# ============================================================
print("\n=== 2. Home Assistant Direct ===")

if HA_TOKEN:
    ha_headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}

    def test_ha_api():
        r = httpx.get(f"{HA_URL}/api/", headers=ha_headers, timeout=5)
        return r.status_code == 200, f"status={r.status_code}"

    test("HA API health", test_ha_api)

    def test_ha_states():
        r = httpx.get(f"{HA_URL}/api/states", headers=ha_headers, timeout=10)
        entities = r.json()
        controllable = [e for e in entities if e["entity_id"].split(".")[0] in
                        ("switch", "light", "fan", "climate", "cover")]
        return r.status_code == 200, f"total={len(entities)}, controllable={len(controllable)}"

    test("HA states", test_ha_states)

    def test_ha_config():
        r = httpx.get(f"{HA_URL}/api/config", headers=ha_headers, timeout=5)
        d = r.json()
        return r.status_code == 200, f"location={d.get('location_name','?')}, version={d.get('version','?')}"

    test("HA config", test_ha_config)
else:
    skip("HA API health", "HA_TOKEN not set")
    skip("HA states", "HA_TOKEN not set")
    skip("HA config", "HA_TOKEN not set")


# ============================================================
# 3. Tuya Cloud Tests (via Gateway)
# ============================================================
print("\n=== 3. Tuya Cloud (via Gateway) ===")


def test_tuya_status():
    r = httpx.get(f"{GATEWAY_URL}/", timeout=5)
    d = r.json()
    tuya = d.get("tuya", {})
    enabled = tuya.get("enabled", False)
    return True, f"enabled={enabled}"

test("Tuya status", test_tuya_status)


def test_tuya_devices():
    r = httpx.get(f"{GATEWAY_URL}/tuya/devices", timeout=10)
    if r.status_code == 503:
        return True, "Tuya not configured (expected if no credentials)"
    d = r.json()
    success = d.get("success", False)
    devices = d.get("result", {}).get("list", []) if success else []
    return success, f"success={success}, devices={len(devices)}"

test("Tuya devices", test_tuya_devices)


# ============================================================
# 4. ScreenStream Smart Home Routes
# ============================================================
print("\n=== 4. ScreenStream Smart Home Routes ===")

if SS_URL:
    def test_ss_sh_status():
        r = httpx.get(f"{SS_URL}/smarthome/status", timeout=5)
        d = r.json()
        return r.status_code == 200, f"gateway_reachable={d.get('gateway_reachable', '?')}"

    test("SS /smarthome/status", test_ss_sh_status)

    def test_ss_sh_devices():
        r = httpx.get(f"{SS_URL}/smarthome/devices", timeout=10)
        return r.status_code == 200 or r.status_code == 503, f"status={r.status_code}"

    test("SS /smarthome/devices", test_ss_sh_devices)

    def test_ss_sh_scenes():
        r = httpx.get(f"{SS_URL}/smarthome/scenes", timeout=10)
        return r.status_code == 200 or r.status_code == 503, f"status={r.status_code}"

    test("SS /smarthome/scenes", test_ss_sh_scenes)
else:
    skip("SS /smarthome/status", "SS_URL not set (set to ScreenStream API base)")
    skip("SS /smarthome/devices", "SS_URL not set")
    skip("SS /smarthome/scenes", "SS_URL not set")


# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 50)
passed = sum(1 for _, ok, _ in results if ok is True)
failed = sum(1 for _, ok, _ in results if ok is False)
skipped = sum(1 for _, ok, _ in results if ok is None)
total = len(results)
print(f"  Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
if failed == 0:
    print(f"  \033[92mAll tests passed!\033[0m")
else:
    print(f"  \033[91m{failed} test(s) failed\033[0m")
print("=" * 50)
