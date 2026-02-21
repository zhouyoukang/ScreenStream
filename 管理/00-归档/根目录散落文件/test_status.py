import urllib.request
import json

agents = [
    {"agent_key": "ss_1", "project": "ScreenStream", "task": "implementing input routes", "phase": "working", "level": "silent"},
    {"agent_key": "devcat_2", "project": "DevCatalyst", "task": "writing documentation", "phase": "working", "level": "silent"},
    {"agent_key": "audio_3", "project": "AudioCenter", "task": "waiting for user review", "phase": "waiting", "level": "notify"},
    {"agent_key": "blocked_4", "project": "TestProject", "task": "stuck on auth issue", "phase": "blocked", "level": "block"},
]

for a in agents:
    payload = json.dumps(a).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:9901/api/status",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    r = urllib.request.urlopen(req, timeout=3)
    result = json.loads(r.read())
    print(f"  {a['project']}: {result}")

r = urllib.request.urlopen("http://127.0.0.1:9901/api/statuses", timeout=3)
statuses = json.loads(r.read())
print(f"\nAll statuses ({len(statuses)} agents):")
for k, v in statuses.items():
    phase = v["phase"]
    print(f"  {k}: {v['project']} - {v['task']} [{phase}]")

print("\nDashboard: http://127.0.0.1:9901")
