"""快速测试代理和邮箱API可用性"""
import subprocess, base64, json, sys

def ps_test(url, proxy=None, timeout=10):
    ps = f'$ProgressPreference="SilentlyContinue"\n'
    iwr = f'Invoke-WebRequest -Uri "{url}" -UseBasicParsing -TimeoutSec {timeout}'
    if proxy:
        iwr += f' -Proxy "{proxy}"'
    ps += f'try {{ ({iwr}).Content }} catch {{ "PS_ERROR: " + $_.Exception.Message }}'
    enc = base64.b64encode(ps.encode('utf-16-le')).decode()
    r = subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", enc],
        capture_output=True, text=True, timeout=timeout+15, encoding='utf-8', errors='replace')
    return r.stdout.strip()

print("=" * 50)
print("PROXY + EMAIL API TEST")
print("=" * 50)

# Test 1: Proxy connectivity
print("\n[1] Testing proxy 7890...")
r1 = ps_test("https://httpbin.org/ip", proxy="http://127.0.0.1:7890")
print(f"  Result: {r1[:200]}")

print("\n[2] Testing proxy 7897...")
r2 = ps_test("https://httpbin.org/ip", proxy="http://127.0.0.1:7897")
print(f"  Result: {r2[:200]}")

print("\n[3] Testing direct (no proxy)...")
r3 = ps_test("https://httpbin.org/ip")
print(f"  Result: {r3[:200]}")

# Test 2: GuerrillaMail
print("\n[4] GuerrillaMail via 7890...")
r4 = ps_test("https://api.guerrillamail.com/ajax.php?f=get_email_address", proxy="http://127.0.0.1:7890")
print(f"  Result: {r4[:300]}")

print("\n[5] GuerrillaMail direct...")
r5 = ps_test("https://api.guerrillamail.com/ajax.php?f=get_email_address")
print(f"  Result: {r5[:300]}")

# Test 3: Mail.tm
print("\n[6] Mail.tm domains via 7890...")
r6 = ps_test("https://api.mail.tm/domains", proxy="http://127.0.0.1:7890")
print(f"  Result: {r6[:300]}")

print("\n[7] Mail.tm domains direct...")
r7 = ps_test("https://api.mail.tm/domains")
print(f"  Result: {r7[:300]}")

print("\n" + "=" * 50)
print("DONE")
