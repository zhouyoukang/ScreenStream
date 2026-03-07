"""Edge CDP: poll for QR login → extract appsecret → fill URL/Token → submit"""
import time, json, sys, os, struct, socket, base64

CDP_PORT = 9222
TAB_ID = sys.argv[1] if len(sys.argv) > 1 else "76DB45D174BDDCD6D1E5C8ACCE1400F7"
TARGET_URL = os.environ.get("WX_URL", "https://aiotvr.xyz/wx")
TARGET_TOKEN = os.environ.get("WECHAT_TOKEN", "smarthome2026")

def websocket_connect(url):
    """Raw WebSocket connection (no external dependencies)"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or 80
    path = parsed.path

    sock = socket.create_connection((host, port), timeout=10)

    # WebSocket handshake
    key = base64.b64encode(os.urandom(16)).decode()
    handshake = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    )
    sock.sendall(handshake.encode())

    # Read response
    response = b""
    while b"\r\n\r\n" not in response:
        response += sock.recv(4096)

    if b"101" not in response.split(b"\r\n")[0]:
        raise Exception(f"WebSocket handshake failed: {response[:200]}")

    return sock

def ws_send(sock, data):
    """Send a WebSocket text frame"""
    payload = data.encode("utf-8")
    frame = bytearray()
    frame.append(0x81)  # text frame, FIN

    mask_key = os.urandom(4)
    length = len(payload)

    if length < 126:
        frame.append(0x80 | length)
    elif length < 65536:
        frame.append(0x80 | 126)
        frame.extend(struct.pack(">H", length))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack(">Q", length))

    frame.extend(mask_key)
    masked = bytearray(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    frame.extend(masked)
    sock.sendall(frame)

def ws_recv(sock, timeout=10):
    """Receive a WebSocket text frame"""
    sock.settimeout(timeout)
    data = sock.recv(2)
    if len(data) < 2:
        return None

    opcode = data[0] & 0x0F
    masked = (data[1] & 0x80) != 0
    length = data[1] & 0x7F

    if length == 126:
        length = struct.unpack(">H", sock.recv(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", sock.recv(8))[0]

    if masked:
        mask_key = sock.recv(4)

    payload = bytearray()
    while len(payload) < length:
        chunk = sock.recv(length - len(payload))
        if not chunk:
            break
        payload.extend(chunk)

    if masked:
        payload = bytearray(b ^ mask_key[i % 4] for i, b in enumerate(payload))

    return payload.decode("utf-8", errors="replace")

def cdp_eval(sock, expr, cmd_id=1):
    """Execute JavaScript via CDP and return result"""
    cmd = json.dumps({
        "id": cmd_id,
        "method": "Runtime.evaluate",
        "params": {
            "expression": expr,
            "returnByValue": True
        }
    })
    ws_send(sock, cmd)

    # Read responses until we get our result
    for _ in range(20):
        raw = ws_recv(sock, timeout=15)
        if not raw:
            continue
        try:
            result = json.loads(raw)
            if result.get("id") == cmd_id:
                return result
        except json.JSONDecodeError:
            continue
    return None

def main():
    ws_url = f"ws://localhost:{CDP_PORT}/devtools/page/{TAB_ID}"
    print(f"Edge CDP 微信自动配置 (tab={TAB_ID[:8]}...)")

    # Phase 1: Poll for QR login completion (up to 120s)
    print("[1/4] 等待扫码登录...", end="", flush=True)
    sock = websocket_connect(ws_url)

    logged_in = False
    for i in range(60):
        result = cdp_eval(sock, "window.location.href", cmd_id=100+i)
        if result:
            url = result.get("result", {}).get("result", {}).get("value", "")
            if "sandbox" in url and "qrconnect" not in url and "login" not in url:
                logged_in = True
                print(f" ✅ 登录成功")
                break
            if "sandboxinfo" in url or "showinfo" in url:
                logged_in = True
                print(f" ✅ 登录成功")
                break
        print(".", end="", flush=True)
        time.sleep(2)

    if not logged_in:
        print(" ❌ 超时")
        sock.close()
        sys.exit(1)

    time.sleep(2)  # Wait for page to fully load

    # Phase 2: Extract appID and appsecret
    print("[2/4] 提取 appID / appsecret...")
    result = cdp_eval(sock, """
    (function(){
        var tds = document.querySelectorAll('td');
        var info = {};
        for(var i = 0; i < tds.length; i++){
            var t = tds[i].textContent.trim();
            if(t === 'appID' && tds[i+1]) info.appid = tds[i+1].textContent.trim();
            if(t === 'appsecret' && tds[i+1]) info.appsecret = tds[i+1].textContent.trim();
        }
        return JSON.stringify(info);
    })()
    """, cmd_id=1)

    value = result.get("result", {}).get("result", {}).get("value", "{}")
    info = json.loads(value)
    appid = info.get("appid", "")
    appsecret = info.get("appsecret", "")

    if not appsecret:
        print("  ❌ 未找到 appsecret")
        sock.close()
        sys.exit(1)

    print(f"  appID:     {appid}")
    print(f"  appsecret: {appsecret}")

    # Phase 3: Fill URL and Token
    print(f"[3/4] 填写 URL={TARGET_URL} Token={TARGET_TOKEN}...")
    cdp_eval(sock, f"""
    (function(){{
        var inputs = document.querySelectorAll('input[type="text"]');
        for(var inp of inputs) {{
            var row = inp.closest('tr') || inp.closest('div') || inp.parentElement;
            var label = row ? row.textContent : '';
            if(label.includes('URL') && !label.includes('JS接口')) {{
                inp.value = '{TARGET_URL}';
                inp.dispatchEvent(new Event('input', {{bubbles:true}}));
            }}
            if(label.includes('Token') && !label.includes('EncodingAES')) {{
                inp.value = '{TARGET_TOKEN}';
                inp.dispatchEvent(new Event('input', {{bubbles:true}}));
            }}
        }}
    }})()
    """, cmd_id=2)
    print("  ✅ 已填入")

    # Phase 4: Click submit
    print("[4/4] 提交...")
    cdp_eval(sock, """
    (function(){
        var btns = document.querySelectorAll('input[type="submit"], button[type="submit"], .btn_primary');
        for(var b of btns){
            var ctx = b.closest('form') || b.closest('.sandbox_info') || b.parentElement;
            if(ctx && (ctx.textContent.includes('URL') || ctx.textContent.includes('Token') || ctx.textContent.includes('接口配置'))){
                b.click(); return;
            }
        }
        if(btns.length > 0) btns[0].click();
    })()
    """, cmd_id=3)

    time.sleep(2)
    # Check result
    result = cdp_eval(sock, "document.body.innerText.includes('配置成功') || document.body.innerText.includes('请求url超时')", cmd_id=4)
    check = result.get("result", {}).get("result", {}).get("value", False) if result else False
    print(f"  提交结果: {'✅ 成功' if check else '⚠️ 待确认 (Gateway需运行中)'}")

    sock.close()

    # Save credentials
    with open("_wechat_credentials.json", "w") as f:
        json.dump({"appid": appid, "appsecret": appsecret}, f)
    print(f"\n✅ 凭据已保存 → _wechat_credentials.json")

if __name__ == "__main__":
    main()
