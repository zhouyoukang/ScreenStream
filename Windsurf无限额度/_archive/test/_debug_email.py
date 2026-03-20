"""调试: 注册后检查GuerrillaMail收件箱内容"""
import json, base64, subprocess, time, sys

GUERRILLA_API = "https://api.guerrillamail.com/ajax.php"
PROXY = "http://127.0.0.1:7890"

def ps_http(url, timeout=15):
    ps = f'$ProgressPreference="SilentlyContinue"\n'
    ps += f'$r = (Invoke-WebRequest -Uri "{url}" -UseBasicParsing -TimeoutSec {timeout} -Proxy "{PROXY}").Content\n'
    ps += 'if($r -is [byte[]]){[System.Text.Encoding]::UTF8.GetString($r)}else{$r}'
    enc = base64.b64encode(ps.encode('utf-16-le')).decode()
    r = subprocess.run(["powershell","-NoProfile","-EncodedCommand",enc],
        capture_output=True, text=True, timeout=timeout+15, encoding='utf-8', errors='replace')
    out = r.stdout.strip()
    for i,ch in enumerate(out):
        if ch in ('{','['):
            try: return json.loads(out[i:])
            except: continue
    return out

# 获取新邮箱
print("[1] Getting email address...")
d = ps_http(f"{GUERRILLA_API}?f=get_email_address")
sid = d.get("sid_token","")
addr = d.get("email_addr","")
print(f"  Email: {addr}")
print(f"  SID: {sid[:20]}...")

# 检查收件箱
print(f"\n[2] Checking inbox...")
d2 = ps_http(f"{GUERRILLA_API}?f=check_email&seq=0&sid_token={sid}")
msgs = d2.get("list",[])
print(f"  Messages: {len(msgs)}")
for m in msgs[:5]:
    print(f"  - Subject: {m.get('mail_subject','')}")
    print(f"    From: {m.get('mail_from','')}")
    print(f"    ID: {m.get('mail_id','')}")
    
    # 获取完整邮件内容
    mid = m.get("mail_id","")
    if mid:
        full = ps_http(f"{GUERRILLA_API}?f=fetch_email&email_id={mid}&sid_token={sid}")
        body = full.get("mail_body","")
        print(f"    Body length: {len(str(body))}")
        print(f"    Body preview: {str(body)[:500]}")
        print(f"    Keys: {list(full.keys())}")
        
        # 查找所有URL
        import re, html
        content = html.unescape(str(body))
        urls = re.findall(r'https?://[^\s<>"\']+', content)
        print(f"    URLs found: {len(urls)}")
        for u in urls:
            print(f"      {u[:120]}")

# 也检查最近注册的邮箱
print(f"\n[3] Checking recent registration emails...")
recent_addrs = ["pblhdcph", "dmbaugez", "cyjgdfly"]
for prefix in recent_addrs:
    print(f"\n  Setting user to: {prefix}")
    d3 = ps_http(f"{GUERRILLA_API}?f=set_email_user&email_user={prefix}&sid_token={sid}")
    new_addr = d3.get("email_addr","")
    print(f"  Address: {new_addr}")
    sid = d3.get("sid_token", sid)
    
    time.sleep(1)
    d4 = ps_http(f"{GUERRILLA_API}?f=check_email&seq=0&sid_token={sid}")
    msgs2 = d4.get("list",[])
    print(f"  Messages: {len(msgs2)}")
    for m2 in msgs2[:3]:
        subj = m2.get("mail_subject","")
        frm = m2.get("mail_from","")
        print(f"  - [{frm}] {subj}")
        mid2 = m2.get("mail_id","")
        if mid2 and ("windsurf" in subj.lower() or "codeium" in subj.lower() or "verify" in subj.lower() or "confirm" in subj.lower()):
            full2 = ps_http(f"{GUERRILLA_API}?f=fetch_email&email_id={mid2}&sid_token={sid}")
            body2 = full2.get("mail_body","")
            content2 = html.unescape(str(body2))
            urls2 = re.findall(r'https?://[^\s<>"\']+', content2)
            print(f"    *** Windsurf email! URLs: {len(urls2)}")
            for u2 in urls2:
                print(f"      {u2[:150]}")
