#!/usr/bin/env python3
"""通过公网URL模拟微信服务器回调，验证完整链路"""
import httpx, time, hashlib, re, sys

TOKEN = "smarthome2026"

# 自动检测公网URL
def detect_public_url():
    """从 cloudflared metrics 获取当前隧道URL"""
    try:
        r = httpx.get("http://127.0.0.1:20241/metrics", timeout=3)
        # 从 metrics 提取 URL 不现实，直接尝试常见端口
    except Exception:
        pass
    # 回退: 从命令行参数或环境变量获取
    if len(sys.argv) > 1:
        return sys.argv[1].rstrip("/")
    import os
    url = os.getenv("WX_PUBLIC_URL", "")
    if url:
        return url.rstrip("/")
    print("Usage: python test_wx_public.py <PUBLIC_URL>")
    print("Example: python test_wx_public.py https://xxx.trycloudflare.com")
    sys.exit(1)

URL = detect_public_url()
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results = []

def extract_reply(xml_text):
    m = re.search(r"<Content><!\[CDATA\[(.*?)\]\]></Content>", xml_text, re.DOTALL)
    return m.group(1) if m else ""

def make_msg(content, msg_type="text"):
    if msg_type == "text":
        return (
            "<xml><ToUserName><![CDATA[gh_smarthome]]></ToUserName>"
            "<FromUserName><![CDATA[test_user_openid]]></FromUserName>"
            f"<CreateTime>{int(time.time())}</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            f"<Content><![CDATA[{content}]]></Content>"
            "<MsgId>1</MsgId></xml>"
        ).encode("utf-8")
    elif msg_type == "event_subscribe":
        return (
            "<xml><ToUserName><![CDATA[gh_smarthome]]></ToUserName>"
            "<FromUserName><![CDATA[test_user_openid]]></FromUserName>"
            f"<CreateTime>{int(time.time())}</CreateTime>"
            "<MsgType><![CDATA[event]]></MsgType>"
            "<Event><![CDATA[subscribe]]></Event></xml>"
        ).encode("utf-8")

def test(name, fn):
    try:
        ok, detail = fn()
        results.append((name, ok))
        print(f"  [{PASS if ok else FAIL}] {name}: {detail}")
    except Exception as e:
        results.append((name, False))
        print(f"  [{FAIL}] {name}: {e}")

print(f"\n=== WeChat Public URL E2E Test ===")
print(f"  URL: {URL}\n")

# 1. Gateway reachable
def t_status():
    r = httpx.get(f"{URL}/wx/status", timeout=15)
    d = r.json()
    return d.get("enabled") and d.get("router_ready"), f"enabled={d.get('enabled')}, router={d.get('router_ready')}"
test("公网 /wx/status", t_status)

# 2. Token verification (模拟微信服务器验证)
def t_verify():
    ts = str(int(time.time()))
    nc = "wechat_server_nonce"
    sig = hashlib.sha1("".join(sorted([TOKEN, ts, nc])).encode()).hexdigest()
    r = httpx.get(f"{URL}/wx", params={"signature": sig, "timestamp": ts, "nonce": nc, "echostr": "wechat_verify_ok"}, timeout=15)
    return r.text == "wechat_verify_ok", f"echostr={'matched' if r.text == 'wechat_verify_ok' else 'MISMATCH: ' + r.text[:50]}"
test("Token验证(GET /wx)", t_verify)

# 3. Subscribe event
def t_subscribe():
    r = httpx.post(f"{URL}/wx", content=make_msg("", "event_subscribe"), headers={"Content-Type": "application/xml"}, timeout=15)
    reply = extract_reply(r.text)
    return "欢迎" in reply, f"reply={'欢迎...' if '欢迎' in reply else reply[:60]}"
test("关注事件", t_subscribe)

# 4. Help command
def t_help():
    r = httpx.post(f"{URL}/wx", content=make_msg("帮助"), headers={"Content-Type": "application/xml"}, timeout=15)
    reply = extract_reply(r.text)
    return "命令列表" in reply, f"len={len(reply)}"
test("帮助命令", t_help)

# 5. Device status
def t_status_cmd():
    r = httpx.post(f"{URL}/wx", content=make_msg("状态"), headers={"Content-Type": "application/xml"}, timeout=15)
    reply = extract_reply(r.text)
    lines = [l for l in reply.split("\n") if "🟢" in l or "⚪" in l]
    return len(lines) > 0, f"{len(lines)} devices"
test("设备状态", t_status_cmd)

# 6. TTS
def t_tts():
    r = httpx.post(f"{URL}/wx", content=make_msg("说 公网测试成功"), headers={"Content-Type": "application/xml"}, timeout=15)
    reply = extract_reply(r.text)
    return "已播报" in reply or "不可用" in reply or "没有" in reply, reply[:60]
test("TTS播报", t_tts)

# 7. Scene macro
def t_scene():
    r = httpx.post(f"{URL}/wx", content=make_msg("睡眠模式"), headers={"Content-Type": "application/xml"}, timeout=30)
    reply = extract_reply(r.text)
    return "睡眠" in reply or "不可用" in reply or "没有" in reply, reply[:80]
test("场景宏", t_scene)

# Summary
print(f"\n{'='*50}")
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"  {passed}/{total} passed")
if passed == total:
    print(f"  \033[92m全部通过! 微信公众号回调URL可用\033[0m")
    print(f"\n  下一步: 在微信测试号页面配置:")
    print(f"    URL:   {URL}/wx")
    print(f"    Token: {TOKEN}")
else:
    failed = [n for n, ok in results if not ok]
    print(f"  \033[91m失败: {', '.join(failed)}\033[0m")
print(f"{'='*50}")
