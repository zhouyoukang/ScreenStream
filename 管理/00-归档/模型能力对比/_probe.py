"""探测语言服务器端口 + HuggingFace API"""
import http.client, json, urllib.request, os, time

# === 1. 语言服务器端口探测 ===
print("=" * 50)
print("语言服务器端口探测")
print("=" * 50)

ports = [62877, 61695, 58066, 56301, 55443]
paths = [
    "/exa.language_server_pb.LanguageServerService/Heartbeat",
    "/exa.language_server_pb.LanguageServerService/GetProcesses",
    "/health",
    "/",
]

for port in ports:
    print(f"\n--- Port {port} ---")
    for path in paths:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            hdrs = {"Content-Type": "application/json", "connect-protocol-version": "1"}
            conn.request("POST", path, body=b"{}", headers=hdrs)
            r = conn.getresponse()
            ct = r.getheader("content-type", "?")
            body = r.read(200)
            print(f"  POST {path}: {r.status} ct={ct} body={body[:80]}")
            conn.close()
        except Exception as e:
            print(f"  POST {path}: {type(e).__name__}")
            break

# === 2. HuggingFace 推理API ===
print("\n" + "=" * 50)
print("HuggingFace 推理API测试")
print("=" * 50)

hf_token = ""
secrets_path = r"d:\道\道生一\一生二\secrets.env"
if os.path.exists(secrets_path):
    with open(secrets_path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("HF_TOKEN="):
                hf_token = line.split("=", 1)[1].strip()

if not hf_token:
    print("No HF_TOKEN found")
else:
    print(f"Token: {hf_token[:6]}...{hf_token[-4:]}")

    proxy = urllib.request.ProxyHandler({"https": "http://127.0.0.1:7890"})
    opener = urllib.request.build_opener(proxy)

    models = [
        "microsoft/Phi-3-mini-4k-instruct",
        "Qwen/Qwen2.5-Coder-32B-Instruct",
        "meta-llama/Llama-3.1-8B-Instruct",
    ]

    for model in models:
        url = f"https://api-inference.huggingface.co/models/{model}/v1/chat/completions"
        data = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "Say hi in one word"}],
            "max_tokens": 10,
        }).encode()

        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {hf_token}")

        t0 = time.time()
        try:
            with opener.open(req, timeout=30) as resp:
                body = json.loads(resp.read())
                content = body.get("choices", [{}])[0].get("message", {}).get("content", "?")
                ms = int((time.time() - t0) * 1000)
                print(f"  {model}: OK {ms}ms -> {content[:60]}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()[:200]
            print(f"  {model}: HTTP {e.code} -> {err_body}")
        except Exception as e:
            print(f"  {model}: {type(e).__name__}: {str(e)[:100]}")

# === 3. 尝试获取Windsurf API key ===
print("\n" + "=" * 50)
print("Windsurf API Key探测")
print("=" * 50)

# 检查VS Code/Windsurf存储
storage_paths = [
    os.path.expandvars(r"%APPDATA%\Windsurf\User\globalStorage"),
    os.path.expandvars(r"%APPDATA%\Windsurf\User\settings.json"),
    os.path.expanduser(r"~\.codeium\windsurf\config.json"),
    os.path.expanduser(r"~\.codeium\config.json"),
]
for p in storage_paths:
    exists = os.path.exists(p)
    if exists and os.path.isfile(p):
        size = os.path.getsize(p)
        print(f"  {p}: FILE {size}B")
        if p.endswith(".json") and size < 10000:
            try:
                with open(p, encoding="utf-8") as f:
                    content = f.read()
                # Look for API key patterns
                if "api_key" in content.lower() or "token" in content.lower():
                    print(f"    Contains key/token references!")
                    # Don't print actual keys
            except Exception:
                pass
    elif exists and os.path.isdir(p):
        items = os.listdir(p)
        print(f"  {p}: DIR ({len(items)} items): {items[:10]}")
    else:
        print(f"  {p}: NOT FOUND")

# Check Windsurf extension storage
ext_storage = os.path.expandvars(r"%APPDATA%\Windsurf\User\globalStorage\codeium.codeium")
if os.path.exists(ext_storage):
    print(f"\n  Codeium extension storage: {ext_storage}")
    for item in os.listdir(ext_storage):
        fp = os.path.join(ext_storage, item)
        sz = os.path.getsize(fp) if os.path.isfile(fp) else "DIR"
        print(f"    {item}: {sz}")
