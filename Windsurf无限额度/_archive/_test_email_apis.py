"""测试所有临时邮箱API的可用性"""
import base64, subprocess, json, time, sys

PROXY = "http://127.0.0.1:7890"

def ps_http(method, url, body=None, proxy=None, timeout=15):
    ps_lines = ['$ProgressPreference="SilentlyContinue"']
    iwr = f'Invoke-WebRequest -Uri "{url}" -Method {method} -UseBasicParsing -TimeoutSec {timeout}'
    if proxy:
        iwr += f' -Proxy "{proxy}"'
    if body:
        escaped = body.replace('"', '`"')
        iwr += f' -Body "{escaped}" -ContentType "application/json"'
    ps_lines.append(f'try {{ $resp = ({iwr}).Content; if ($resp -is [byte[]]) {{ [System.Text.Encoding]::UTF8.GetString($resp) }} else {{ $resp }} }} catch {{ Write-Output ("ERROR:" + $_.Exception.Message) }}')
    ps_script = '\n'.join(ps_lines)
    encoded = base64.b64encode(ps_script.encode('utf-16-le')).decode('ascii')
    result = subprocess.run(
        ["powershell", "-NoProfile", "-EncodedCommand", encoded],
        capture_output=True, text=True, timeout=timeout + 15,
        encoding='utf-8', errors='replace'
    )
    out = result.stdout.strip()
    if not out:
        return {"_error": f"empty response, stderr={result.stderr[:300]}"}
    if out.startswith("ERROR:"):
        return {"_error": out}
    for i, ch in enumerate(out):
        if ch in ('{', '['):
            try:
                return json.loads(out[i:])
            except json.JSONDecodeError:
                continue
    return {"_raw": out[:500]}

def test_mail_tm():
    print("=" * 50)
    print("TEST 1: Mail.tm API")
    print("=" * 50)
    
    # Get domains
    print("[*] Getting domains...")
    domains = ps_http("GET", "https://api.mail.tm/domains", proxy=PROXY)
    if "_error" in domains:
        print(f"  FAIL: {domains['_error']}")
        return False
    
    if isinstance(domains, dict):
        members = domains.get("hydra:member", [])
    elif isinstance(domains, list):
        members = domains
    else:
        members = []
    
    active = [d["domain"] for d in members if isinstance(d, dict) and d.get("isActive")]
    print(f"  Active domains: {active}")
    
    if not active:
        print("  FAIL: No active domains")
        return False
    
    # Create inbox
    import random, string
    domain = active[0]
    prefix = "wstest" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    address = f"{prefix}@{domain}"
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    
    print(f"[*] Creating inbox: {address}")
    acct = ps_http("POST", "https://api.mail.tm/accounts", 
                   body=json.dumps({"address": address, "password": password}),
                   proxy=PROXY)
    if "_error" in acct:
        print(f"  FAIL: {acct['_error']}")
        return False
    print(f"  Account: {acct.get('id', '?')}")
    
    # Get token
    print("[*] Getting auth token...")
    tok = ps_http("POST", "https://api.mail.tm/token",
                  body=json.dumps({"address": address, "password": password}),
                  proxy=PROXY)
    if "_error" in tok:
        print(f"  FAIL: {tok['_error']}")
        return False
    token = tok.get("token", "")
    print(f"  Token: {token[:30]}...")
    
    print(f"  PASS: Mail.tm fully functional")
    return {"provider": "mail.tm", "address": address, "password": password, "token": token, "domains": active}

def test_guerrilla():
    print("\n" + "=" * 50)
    print("TEST 2: GuerrillaMail API")
    print("=" * 50)
    
    print("[*] Getting email address...")
    data = ps_http("GET", f"https://api.guerrillamail.com/ajax.php?f=get_email_address", proxy=PROXY)
    if "_error" in data:
        print(f"  FAIL: {data['_error']}")
        return False
    
    email = data.get("email_addr", "")
    sid = data.get("sid_token", "")
    print(f"  Email: {email}")
    print(f"  SID: {sid[:20]}...")
    
    # Check inbox
    print("[*] Checking inbox...")
    msgs = ps_http("GET", f"https://api.guerrillamail.com/ajax.php?f=check_email&seq=0&sid_token={sid}", proxy=PROXY)
    if "_error" in msgs:
        print(f"  Inbox check: {msgs['_error']}")
    else:
        count = len(msgs.get("list", []))
        print(f"  Messages: {count}")
    
    print(f"  PASS: GuerrillaMail functional")
    return {"provider": "guerrilla", "address": email, "sid": sid}

def test_1secmail():
    print("\n" + "=" * 50)
    print("TEST 3: 1secmail.com API (no proxy needed for API)")
    print("=" * 50)
    
    # Try with proxy first, then without
    for use_proxy in [PROXY, None]:
        proxy_label = "with proxy" if use_proxy else "direct"
        print(f"[*] Getting random address ({proxy_label})...")
        data = ps_http("GET", "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1", proxy=use_proxy)
        if "_error" not in data:
            break
    
    if "_error" in data:
        print(f"  FAIL: {data['_error']}")
        return False
    
    if isinstance(data, list) and data:
        email = data[0]
        print(f"  Email: {email}")
        login, domain = email.split("@")
        
        # Check inbox
        print("[*] Checking inbox...")
        msgs = ps_http("GET", f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}", proxy=use_proxy)
        if isinstance(msgs, list):
            print(f"  Messages: {len(msgs)}")
        print(f"  PASS: 1secmail functional (proxy={'yes' if use_proxy else 'no'})")
        return {"provider": "1secmail", "address": email, "login": login, "domain": domain, "needs_proxy": bool(use_proxy)}
    
    print(f"  FAIL: unexpected response: {data}")
    return False

def test_maildrop():
    print("\n" + "=" * 50)
    print("TEST 4: Maildrop.cc (public, no API key)")
    print("=" * 50)
    
    import random, string
    username = "wstest" + ''.join(random.choices(string.ascii_lowercase, k=6))
    email = f"{username}@maildrop.cc"
    print(f"[*] Testing inbox: {email}")
    
    # Maildrop uses GraphQL API
    graphql_body = json.dumps({"query": f'{{ inbox(mailbox: "{username}") {{ id headfrom subject date }} }}'})
    data = ps_http("POST", "https://api.maildrop.cc/graphql", body=graphql_body, proxy=PROXY)
    if "_error" in data:
        # Try without proxy
        data = ps_http("POST", "https://api.maildrop.cc/graphql", body=graphql_body, proxy=None)
    
    if "_error" in data:
        print(f"  FAIL: {data['_error']}")
        return False
    
    inbox = data.get("data", {}).get("inbox", [])
    print(f"  Messages: {len(inbox)}")
    print(f"  PASS: Maildrop functional")
    return {"provider": "maildrop", "address": email, "username": username}

if __name__ == "__main__":
    results = {}
    for test_fn in [test_mail_tm, test_guerrilla, test_1secmail, test_maildrop]:
        try:
            r = test_fn()
            name = test_fn.__name__.replace("test_", "")
            results[name] = r if r else "FAIL"
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            results[test_fn.__name__] = f"EXCEPTION: {e}"
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    for name, r in results.items():
        status = "PASS" if isinstance(r, dict) else "FAIL"
        addr = r.get("address", "") if isinstance(r, dict) else ""
        print(f"  {name}: {status} {addr}")
    
    # Save results
    with open("_email_api_test_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to _email_api_test_results.json")
