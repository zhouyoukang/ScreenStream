#!/usr/bin/env python3
"""Query frps dashboard API for accurate proxy status."""
import json, urllib.request, base64, sys

FRPS_API = "http://127.0.0.1:7500/api/proxy/tcp"
CREDS = base64.b64encode(b"admin:frp_admin_2026").decode()

req = urllib.request.Request(FRPS_API)
req.add_header("Authorization", f"Basic {CREDS}")

try:
    data = json.loads(urllib.request.urlopen(req, timeout=5).read())
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)

# Output mode: --json for machine-readable, default for human
if "--json" in sys.argv:
    # Output port→status mapping for watchdog consumption
    result = {}
    for p in data.get("proxies", []):
        conf = p.get("conf")
        if conf and conf.get("remotePort"):
            port = conf["remotePort"]
            result[str(port)] = p["status"]
    print(json.dumps(result))
else:
    for p in data.get("proxies", []):
        name = p.get("name", "?")
        status = p.get("status", "?")
        conf = p.get("conf")
        port = conf.get("remotePort", "?") if conf else "?"
        conns = p.get("curConns", 0)
        print(f"{name:40s} {status:10s} port:{port:<6} conns:{conns}")
