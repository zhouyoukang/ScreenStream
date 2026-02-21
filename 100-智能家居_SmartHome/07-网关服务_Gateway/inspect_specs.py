"""Inspect MIoT spec files cached by HA to understand device capabilities."""
import json, glob, os

SPEC_DIR = r"E:\HassWP\config\.storage\xiaomi_miot"

for f in sorted(glob.glob(os.path.join(SPEC_DIR, "urn_miot-spec-v2_device_*.json"))):
    name = os.path.basename(f)
    with open(f, encoding="utf-8") as fh:
        raw = json.load(fh)
    d = raw.get("data", raw)  # HA wraps spec in {"data": ...}
    dtype = name.split("_")[5]
    print(f"\n=== {dtype} ({name[:60]}...) ===")
    for svc in d.get("services", [])[:5]:
        siid = svc["iid"]
        stype = svc["type"].split(":")[3] if ":" in svc["type"] else svc["type"]
        props = []
        for p in svc.get("properties", []):
            ptype = p["type"].split(":")[3] if ":" in p["type"] else p["type"]
            access = p.get("access", [])
            fmt = p.get("format", "?")
            props.append(f"piid={p['iid']}:{ptype}({fmt}){'RW' if 'write' in access else 'R'}")
        actions = []
        for a in svc.get("actions", []):
            atype = a["type"].split(":")[3] if ":" in a["type"] else a["type"]
            actions.append(f"aiid={a['iid']}:{atype}")
        print(f"  siid={siid} {stype}: {', '.join(props[:6])}")
        if actions:
            print(f"    actions: {', '.join(actions)}")
