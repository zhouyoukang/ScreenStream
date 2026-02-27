"""Fill WeChat test account URL/Token via Edge CDP, then click submit."""
import json, os, struct, socket, base64, sys, time
import urllib.request
from urllib.parse import urlparse

CDP_PORT = 9222
CF_URL = sys.argv[1] if len(sys.argv) > 1 else "https://like-printing-gen-just.trycloudflare.com/wx"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("WECHAT_TOKEN", "smarthome2026")

# Find WeChat tab
tabs = json.loads(urllib.request.urlopen("http://localhost:%d/json" % CDP_PORT).read())
tab = None
for t in tabs:
    url = t.get("url", "")
    if "weixin" in url or "mp.weixin" in url or "sandbox" in url:
        tab = t
        break
if not tab:
    # Fallback: find by title
    for t in tabs:
        if "测试号" in t.get("title", "") or "微信" in t.get("title", ""):
            tab = t
            break
if not tab:
    print("ERROR: No WeChat tab found. Open tabs:")
    for t in tabs:
        print("  %s -> %s" % (t.get("title", "")[:30], t.get("url", "")[:60]))
    sys.exit(1)

ws_url = tab["webSocketDebuggerUrl"]
print("Tab: %s" % tab.get("title", "?"))
print("URL: %s" % tab.get("url", "?")[:80])


# --- WebSocket helpers ---
def ws_connect(url):
    parsed = urlparse(url)
    sock = socket.create_connection((parsed.hostname, parsed.port or 80), timeout=10)
    key = base64.b64encode(os.urandom(16)).decode()
    hs = "GET %s HTTP/1.1\r\nHost: %s:%s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % (
        parsed.path, parsed.hostname, parsed.port, key)
    sock.sendall(hs.encode())
    resp = b""
    while b"\r\n\r\n" not in resp:
        resp += sock.recv(4096)
    if b"101" not in resp.split(b"\r\n")[0]:
        raise Exception("WS handshake failed")
    return sock


def ws_send(s, data):
    payload = data.encode("utf-8")
    frame = bytearray([0x81])
    mk = os.urandom(4)
    l = len(payload)
    if l < 126:
        frame.append(0x80 | l)
    elif l < 65536:
        frame.append(0x80 | 126)
        frame.extend(struct.pack(">H", l))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack(">Q", l))
    frame.extend(mk)
    frame.extend(bytearray(b ^ mk[i % 4] for i, b in enumerate(payload)))
    s.sendall(frame)


def ws_recv(s, timeout=10):
    s.settimeout(timeout)
    try:
        d = s.recv(2)
    except Exception:
        return None
    if len(d) < 2:
        return None
    masked = (d[1] & 0x80) != 0
    l = d[1] & 0x7F
    if l == 126:
        l = struct.unpack(">H", s.recv(2))[0]
    elif l == 127:
        l = struct.unpack(">Q", s.recv(8))[0]
    mk = s.recv(4) if masked else None
    p = bytearray()
    while len(p) < l:
        c = s.recv(l - len(p))
        if not c:
            break
        p.extend(c)
    if masked:
        p = bytearray(b ^ mk[i % 4] for i, b in enumerate(p))
    return p.decode("utf-8", errors="replace")


def cdp_eval(sock, expr, cid=1):
    cmd = json.dumps({"id": cid, "method": "Runtime.evaluate",
                       "params": {"expression": expr, "returnByValue": True}})
    ws_send(sock, cmd)
    for _ in range(30):
        raw = ws_recv(sock, 15)
        if not raw:
            continue
        try:
            r = json.loads(raw)
            if r.get("id") == cid:
                return r
        except json.JSONDecodeError:
            continue
    return None


# Connect
sock = ws_connect(ws_url)

# Check page title
r = cdp_eval(sock, "document.title", 10)
title = r.get("result", {}).get("result", {}).get("value", "?") if r else "?"
print("Page title: %s" % title)

# Check if already on sandbox management page
r = cdp_eval(sock, "document.querySelector('.sandbox_info') !== null", 11)
on_mgmt = r.get("result", {}).get("result", {}).get("value", False) if r else False

if not on_mgmt:
    # Check URL
    r = cdp_eval(sock, "window.location.href", 12)
    page_url = r.get("result", {}).get("result", {}).get("value", "") if r else ""
    print("Current URL: %s" % page_url[:80])
    if "login" in page_url or "qrconnect" in page_url:
        print("ERROR: Not logged in. Please scan QR code first.")
        sock.close()
        sys.exit(1)

# Fill URL and Token
fill_js = """(function(){
    var inputs = document.querySelectorAll('input[type="text"]');
    var filled = 0;
    for(var i=0; i<inputs.length; i++) {
        var inp = inputs[i];
        var row = inp.closest('tr') || inp.closest('div') || inp.parentElement;
        var label = row ? row.textContent : '';
        if(label.indexOf('URL') >= 0 && label.indexOf('JS') < 0) {
            inp.value = '""" + CF_URL + """';
            inp.dispatchEvent(new Event('input', {bubbles:true}));
            inp.dispatchEvent(new Event('change', {bubbles:true}));
            filled++;
        }
        if(label.indexOf('Token') >= 0 && label.indexOf('EncodingAES') < 0) {
            inp.value = '""" + TOKEN + """';
            inp.dispatchEvent(new Event('input', {bubbles:true}));
            inp.dispatchEvent(new Event('change', {bubbles:true}));
            filled++;
        }
    }
    return filled;
})()"""

print("Filling URL: %s" % CF_URL)
print("Filling Token: %s" % TOKEN)
r = cdp_eval(sock, fill_js, 20)
filled = r.get("result", {}).get("result", {}).get("value", 0) if r else 0
print("Fields filled: %d" % filled)

# Read back values to verify
verify_js = """(function(){
    var inputs = document.querySelectorAll('input[type="text"]');
    var vals = [];
    for(var i=0; i<inputs.length; i++) vals.push(inputs[i].value);
    return JSON.stringify(vals);
})()"""
r = cdp_eval(sock, verify_js, 30)
vals = r.get("result", {}).get("result", {}).get("value", "[]") if r else "[]"
print("Verify values: %s" % vals)

if filled >= 2:
    # Click submit button
    print("Clicking submit...")
    submit_js = """(function(){
        var btns = document.querySelectorAll('input[type="submit"], button[type="submit"], .btn_primary, .btn_default');
        for(var i=0; i<btns.length; i++){
            var ctx = btns[i].closest('form') || btns[i].closest('.sandbox_info') || btns[i].parentElement;
            if(ctx && (ctx.textContent.indexOf('URL') >= 0 || ctx.textContent.indexOf('Token') >= 0 || ctx.textContent.indexOf('接口配置') >= 0)){
                btns[i].click();
                return 'clicked';
            }
        }
        // Fallback: click first green button
        var greens = document.querySelectorAll('.btn_primary');
        if(greens.length > 0) { greens[0].click(); return 'clicked_fallback'; }
        return 'no_button_found';
    })()"""
    r = cdp_eval(sock, submit_js, 40)
    result = r.get("result", {}).get("result", {}).get("value", "?") if r else "?"
    print("Submit: %s" % result)

    time.sleep(3)

    # Check result
    check_js = """(function(){
        var body = document.body.innerText;
        if(body.indexOf('配置成功') >= 0) return 'SUCCESS';
        if(body.indexOf('请求url超时') >= 0) return 'URL_TIMEOUT';
        if(body.indexOf('token验证失败') >= 0) return 'TOKEN_FAIL';
        return body.substring(0, 200);
    })()"""
    r = cdp_eval(sock, check_js, 50)
    check = r.get("result", {}).get("result", {}).get("value", "?") if r else "?"
    print("Result: %s" % check)
else:
    print("WARNING: Could not fill all fields. Manual intervention needed.")

sock.close()
print("DONE")
