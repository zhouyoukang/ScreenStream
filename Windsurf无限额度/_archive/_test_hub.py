#!/usr/bin/env python3
"""Hub API full test suite + stress test"""
import http.client, json, ssl, socket, time, sys, threading

HOST = "127.0.0.1"
PORT = 18800
PREFIX = "/hub"

def req(method, path, body=None):
    try:
        conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
        headers = {"Content-Type": "application/json"} if body else {}
        data = json.dumps(body).encode() if body else None
        conn.request(method, PREFIX + path, body=data, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode()
        conn.close()
        try:
            return resp.status, json.loads(raw)
        except:
            return resp.status, raw[:200]
    except Exception as e:
        return 0, str(e)

print("=== Hub API Test Suite ===")

# 1. Health
s, d = req("GET", "/api/health")
hub_ok = isinstance(d, dict) and d.get("hub") == "online"
print("1. GET /health:", s, "OK" if hub_ok else "FAIL")

# 2. Register
s, d = req("POST", "/api/register", {"hostname": "TEST-PC", "version": "5.0", "os": "Win10"})
print("2. POST /register:", s, d)

# 3. Heartbeat
s, d = req("POST", "/api/heartbeat", {"hostname": "TEST-PC"})
print("3. POST /heartbeat:", s, d)

# 4. CFW state
s, d = req("POST", "/api/cfw-state", {"proxy_mode": "relay", "running": True, "request_count": 999})
print("4. POST /cfw-state:", s, d)

# 5. Diagnose
s, d = req("GET", "/api/diagnose")
if isinstance(d, dict):
    r = {k: ("OK" if v.get("ok") else "FAIL") for k, v in d.items()}
    print("5. GET /diagnose:", s, r)
else:
    print("5. GET /diagnose:", s, d)

# 6. Client visible
s, d = req("GET", "/api/health")
if isinstance(d, dict):
    print("6. Clients:", list(d.get("clients", {}).keys()))
else:
    print("6. Clients:", s, d)

# 7. Deploy script
s, d = req("GET", "/deploy.ps1")
print("7. GET /deploy.ps1:", s, len(str(d)), "chars")

# 8. Static files (Nginx HTTPS)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
for f in ["windsurf_proxy_ca.cer", "windsurf_proxy_ca.pem", "deploy_vm.ps1"]:
    try:
        c = http.client.HTTPSConnection("127.0.0.1", 443, timeout=5, context=ctx)
        c.request("GET", "/agent/" + f)
        r = c.getresponse()
        print("8. /agent/" + f + ":", r.status, len(r.read()), "B")
        c.close()
    except Exception as e:
        print("8. /agent/" + f + ": FAIL", e)

# 9. TLS tunnel
try:
    s = socket.create_connection(("127.0.0.1", 18443), timeout=5)
    ss = ctx.wrap_socket(s, server_hostname="server.self-serve.windsurf.com")
    print("9. TLS :18443: OK", ss.cipher()[0])
    ss.close()
except Exception as e:
    print("9. TLS :18443: FAIL", e)

# 10. Stress test - concurrent requests (deadlock detection)
print("\n=== Stress Test (20 concurrent) ===")
results = []
def stress_req(i):
    s, d = req("GET", "/api/health")
    results.append(s)
    if i % 5 == 0:
        req("POST", "/api/register", {"hostname": "STRESS-" + str(i)})

threads = [threading.Thread(target=stress_req, args=(i,)) for i in range(20)]
t0 = time.time()
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=10)
elapsed = time.time() - t0
ok = sum(1 for r in results if r == 200)
print("10. Stress:", ok, "/", len(results), "OK in", round(elapsed, 2), "s")

# 11. Post-stress health check
time.sleep(1)
s, d = req("GET", "/api/health")
alive = isinstance(d, dict) and d.get("hub") == "online"
print("11. Post-stress health:", s, "ALIVE" if alive else "DEAD")

print("\n=== Done ===")
