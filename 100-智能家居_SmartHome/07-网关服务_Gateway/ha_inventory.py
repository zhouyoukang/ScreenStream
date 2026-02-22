#!/usr/bin/env python3
"""Inventory HA entities from saved states file"""
import json, os

with open(os.path.join(os.environ["TEMP"], "ha_states.json"), encoding="utf-8") as f:
    states = json.load(f)

categories = {
    "SCENES": "scene.",
    "LIGHTS": "light.",
    "MEDIA PLAYERS": "media_player.",
    "CAMERAS": "camera.",
    "FANS": "fan.",
    "COVERS": "cover.",
    "SWITCHES": "switch.",
    "SENSORS": "sensor.",
    "INPUT BOOLEANS": "input_boolean.",
    "DEVICE TRACKERS": "device_tracker.",
    "REMOTES": "remote.",
}

for title, prefix in categories.items():
    items = [s for s in states if s["entity_id"].startswith(prefix)]
    if not items:
        continue
    print(f"\n=== {title} ({len(items)}) ===")
    for s in items:
        eid = s["entity_id"]
        name = s["attributes"].get("friendly_name", "")
        state = s["state"]
        unit = s["attributes"].get("unit_of_measurement", "")
        extra = ""
        if prefix == "sensor.":
            extra = f" {unit}" if unit else ""
        if prefix == "light.":
            br = s["attributes"].get("brightness", "")
            extra = f" brightness={br}" if br else ""
        print(f"  {state:15s} {eid:55s} {name}{extra}")

# Automations
print("\n=== AUTOMATIONS ===")
autos = [s for s in states if s["entity_id"].startswith("automation.")]
if autos:
    for s in autos:
        print(f"  {s['state']:6s} {s['entity_id']}  {s['attributes'].get('friendly_name','')}")
else:
    print("  (none)")

# Scripts
print("\n=== SCRIPTS ===")
scripts = [s for s in states if s["entity_id"].startswith("script.")]
if scripts:
    for s in scripts:
        print(f"  {s['entity_id']}  {s['attributes'].get('friendly_name','')}")
else:
    print("  (none)")

# Summary
print(f"\n=== SUMMARY: {len(states)} total entities ===")
