#!/usr/bin/env python3
"""Live test: verify WeChat routes on running Gateway (port 8900)"""
import httpx
import time
import hashlib
import re

GW = "http://127.0.0.1:8900"
TOKEN = "smarthome2026"
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

def extract_reply(xml_text):
    m = re.search(r"<Content><!\[CDATA\[(.*?)\]\]></Content>", xml_text, re.DOTALL)
    return m.group(1) if m else xml_text[:200]

def make_msg(content):
    return (
        "<xml><ToUserName><![CDATA[gh_test]]></ToUserName>"
        "<FromUserName><![CDATA[u1]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{content}]]></Content>"
        "<MsgId>1</MsgId></xml>"
    ).encode("utf-8")

print("\n=== WeChat Live Tests ===\n")

# 1. /wx/status
try:
    r = httpx.get(f"{GW}/wx/status", timeout=5)
    d = r.json()
    ok = d.get("enabled") and d.get("router_ready")
    print(f"  [{PASS if ok else FAIL}] /wx/status: enabled={d.get('enabled')}, router={d.get('router_ready')}")
except Exception as e:
    print(f"  [{FAIL}] /wx/status: {e}")

# 2. GET /wx signature verify
try:
    ts = str(int(time.time()))
    nc = "test123"
    sig = hashlib.sha1("".join(sorted([TOKEN, ts, nc])).encode()).hexdigest()
    r = httpx.get(f"{GW}/wx", params={"signature": sig, "timestamp": ts, "nonce": nc, "echostr": "ECHO_OK"}, timeout=5)
    ok = r.text == "ECHO_OK"
    print(f"  [{PASS if ok else FAIL}] GET /wx verify: {r.status_code} -> '{r.text}'")
except Exception as e:
    print(f"  [{FAIL}] GET /wx: {e}")

# 3. POST /wx - help
try:
    r = httpx.post(f"{GW}/wx", content=make_msg("帮助"), headers={"Content-Type": "application/xml"}, timeout=10)
    reply = extract_reply(r.text)
    ok = "命令列表" in reply
    print(f"  [{PASS if ok else FAIL}] POST '帮助': {'命令列表 found' if ok else reply[:60]}")
except Exception as e:
    print(f"  [{FAIL}] POST help: {e}")

# 4. POST /wx - status
try:
    r = httpx.post(f"{GW}/wx", content=make_msg("状态"), headers={"Content-Type": "application/xml"}, timeout=10)
    reply = extract_reply(r.text)
    lines = [l for l in reply.split("\n") if "🟢" in l or "⚪" in l]
    print(f"  [{PASS if lines else FAIL}] POST '状态': {len(lines)} devices found")
    for l in lines[:5]:
        print(f"      {l.strip()}")
    if len(lines) > 5:
        print(f"      ... +{len(lines)-5} more")
except Exception as e:
    print(f"  [{FAIL}] POST status: {e}")

# 5. POST /wx - turn on light strip
try:
    r = httpx.post(f"{GW}/wx", content=make_msg("打开灯带"), headers={"Content-Type": "application/xml"}, timeout=15)
    reply = extract_reply(r.text)
    print(f"  [INFO] POST '打开灯带': {reply[:80]}")
except Exception as e:
    print(f"  [{FAIL}] POST light: {e}")

# 6. POST /wx - scene
try:
    r = httpx.post(f"{GW}/wx", content=make_msg("回家模式"), headers={"Content-Type": "application/xml"}, timeout=30)
    reply = extract_reply(r.text)
    print(f"  [INFO] POST '回家模式': {reply[:100]}")
except Exception as e:
    print(f"  [{FAIL}] POST scene: {e}")

# 7. POST /wx - TTS
try:
    r = httpx.post(f"{GW}/wx", content=make_msg("说 微信公众号测试成功"), headers={"Content-Type": "application/xml"}, timeout=15)
    reply = extract_reply(r.text)
    print(f"  [INFO] POST 'TTS': {reply[:80]}")
except Exception as e:
    print(f"  [{FAIL}] POST tts: {e}")

# 8. POST /wx - subscribe event
try:
    event_xml = (
        "<xml><ToUserName><![CDATA[gh_test]]></ToUserName>"
        "<FromUserName><![CDATA[u1]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[event]]></MsgType>"
        "<Event><![CDATA[subscribe]]></Event></xml>"
    ).encode("utf-8")
    r = httpx.post(f"{GW}/wx", content=event_xml, headers={"Content-Type": "application/xml"}, timeout=10)
    reply = extract_reply(r.text)
    ok = "欢迎" in reply
    print(f"  [{PASS if ok else FAIL}] POST subscribe event: {'欢迎 found' if ok else reply[:60]}")
except Exception as e:
    print(f"  [{FAIL}] POST event: {e}")

print("\n=== Done ===")
