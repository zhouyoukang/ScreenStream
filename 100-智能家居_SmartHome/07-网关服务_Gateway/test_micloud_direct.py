"""Test direct Xiaomi Cloud API control - using cached session tokens from HA."""
import json
from micloud import MiCloud

# Use cached session tokens from HA (bypasses 2FA login)
mc = MiCloud("REDACTED_PHONE", "REDACTED_PASSWORD")
mc.user_id = "REDACTED_USER_ID"
mc.service_token = "REDACTED_MICLOUD_SERVICE_TOKEN"
mc.ssecurity = "REDACTED_MICLOUD_SSECURITY"
mc.default_server = "cn"
print(f"Session restored. user_id={mc.user_id}")

# Get all devices
devices = mc.get_devices(country="cn")
if not devices:
    print("FAILED: No devices returned")
    exit(1)
print(f"\nTotal devices: {len(devices)}")
for d in devices:
    print(f"  {d.get('name','?'):30s} model={d.get('model','?'):30s} did={d.get('did','?')} ip={d.get('localip','?')}")

# Find controllable devices
switches = [d for d in devices if "switch" in d.get("model", "").lower() or "plug" in d.get("model", "").lower()]
fans = [d for d in devices if "fan" in d.get("model", "").lower()]
lights = [d for d in devices if "light" in d.get("model", "").lower() or "strip" in d.get("model", "").lower()]
print(f"\nSwitches: {len(switches)} | Fans: {len(fans)} | Lights: {len(lights)}")

# Test MIoT cloud RPC: get properties
if switches:
    target = switches[0]
    did = target["did"]
    print(f"\n--- RPC Test: {target['name']} (did={did}, model={target['model']}) ---")

    url = "https://api.io.mi.com/app/miotspec/prop/get"
    params = {"data": json.dumps({"params": [{"did": did, "siid": 2, "piid": 1}]})}
    try:
        resp = mc.request(url, params)
        result = json.loads(resp)
        print(f"GET prop: {json.dumps(result, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"GET prop failed: {e}")

# Test on fan
if fans:
    target = fans[0]
    did = target["did"]
    print(f"\n--- RPC Test: {target['name']} (did={did}) ---")
    url = "https://api.io.mi.com/app/miotspec/prop/get"
    params = {"data": json.dumps({"params": [
        {"did": did, "siid": 2, "piid": 1},  # on/off
        {"did": did, "siid": 2, "piid": 2},  # fan level
    ]})}
    try:
        resp = mc.request(url, params)
        result = json.loads(resp)
        print(f"GET props: {json.dumps(result, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"GET props failed: {e}")
