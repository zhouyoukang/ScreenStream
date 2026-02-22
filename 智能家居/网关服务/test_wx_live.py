#!/usr/bin/env python3
"""
WeChat live tests — verify /wx routes on running Gateway.

Usage:
  python test_wx_live.py                           # local (127.0.0.1:8900)
  python test_wx_live.py https://xxx.trycloudflare.com   # public URL
  WX_PUBLIC_URL=https://... python test_wx_live.py       # env var
"""
import httpx, time, hashlib, re, sys, os

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")

TOKEN = "smarthome2026"
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

def _detect_base_url() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1].rstrip("/")
    env = os.getenv("WX_PUBLIC_URL", "")
    if env:
        return env.rstrip("/")
    return "http://127.0.0.1:8900"

BASE = _detect_base_url()
TIMEOUT = 15 if BASE.startswith("https") else 5
# Bypass system proxy (127.0.0.1:7897) for local requests
client = httpx.Client(proxy=None, timeout=TIMEOUT)
results = []

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

def test(name, fn):
    try:
        ok, detail = fn()
        results.append((name, ok))
        print(f"  [{PASS if ok else FAIL}] {name}: {detail}")
    except Exception as e:
        results.append((name, False))
        print(f"  [{FAIL}] {name}: {e}")

mode = "PUBLIC" if BASE.startswith("https") else "LOCAL"
print(f"\n=== WeChat Live Tests ({mode}: {BASE}) ===\n")

# 1. /wx/status
def t_status():
    r = client.get(f"{BASE}/wx/status")
    d = r.json()
    ok = d.get("enabled") and d.get("router_ready")
    return ok, f"enabled={d.get('enabled')}, router={d.get('router_ready')}"
test("/wx/status", t_status)

# 2. GET /wx signature verify
def t_verify():
    ts = str(int(time.time()))
    nc = "test123"
    sig = hashlib.sha1("".join(sorted([TOKEN, ts, nc])).encode()).hexdigest()
    r = client.get(f"{BASE}/wx", params={"signature": sig, "timestamp": ts, "nonce": nc, "echostr": "ECHO_OK"})
    return r.text == "ECHO_OK", f"{r.status_code} -> '{r.text}'"
test("Token验证(GET /wx)", t_verify)

# 3. POST /wx - help
def t_help():
    r = client.post(f"{BASE}/wx", content=make_msg("帮助"), headers={"Content-Type": "application/xml"})
    reply = extract_reply(r.text)
    return "智能家居" in reply, f"len={len(reply)}"
test("帮助命令", t_help)

# 4. POST /wx - status
def t_device_status():
    r = client.post(f"{BASE}/wx", content=make_msg("状态"), headers={"Content-Type": "application/xml"})
    reply = extract_reply(r.text)
    has_info = "台设备" in reply or "暂无" in reply
    return has_info, f"{len(reply)} chars"
test("设备状态", t_device_status)

# 5. POST /wx - turn on light strip
def t_light():
    r = client.post(f"{BASE}/wx", content=make_msg("打开灯带"), headers={"Content-Type": "application/xml"})
    reply = extract_reply(r.text)
    return bool(reply), reply[:80]
test("设备控制(灯带)", t_light)

# 6. POST /wx - scene macro
def t_scene():
    r = client.post(f"{BASE}/wx", content=make_msg("回家模式"), headers={"Content-Type": "application/xml"})
    reply = extract_reply(r.text)
    return bool(reply), reply[:80]
test("场景宏(回家)", t_scene)

# 7. POST /wx - TTS
def t_tts():
    r = client.post(f"{BASE}/wx", content=make_msg("说 测试成功"), headers={"Content-Type": "application/xml"}, timeout=30)
    reply = extract_reply(r.text)
    return "已播报" in reply or "不可用" in reply or "没有" in reply, reply[:60]
test("TTS播报", t_tts)

# 8. POST /wx - subscribe event
def t_subscribe():
    event_xml = (
        "<xml><ToUserName><![CDATA[gh_test]]></ToUserName>"
        "<FromUserName><![CDATA[u1]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[event]]></MsgType>"
        "<Event><![CDATA[subscribe]]></Event></xml>"
    ).encode("utf-8")
    r = client.post(f"{BASE}/wx", content=event_xml, headers={"Content-Type": "application/xml"})
    reply = extract_reply(r.text)
    return "欢迎" in reply, f"{'欢迎 found' if '欢迎' in reply else reply[:60]}"
test("关注事件", t_subscribe)

# Summary
print(f"\n{'='*50}")
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"  {passed}/{total} passed ({mode}: {BASE})")
if passed == total:
    print(f"  \033[92m全部通过!\033[0m")
    if mode == "PUBLIC":
        print(f"\n  微信测试号配置:")
        print(f"    URL:   {BASE}/wx")
        print(f"    Token: {TOKEN}")
else:
    failed = [n for n, ok in results if not ok]
    print(f"  \033[91m失败: {', '.join(failed)}\033[0m")
print(f"{'='*50}")
