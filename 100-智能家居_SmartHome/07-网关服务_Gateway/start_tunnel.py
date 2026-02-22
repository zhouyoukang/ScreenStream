#!/usr/bin/env python3
"""
启动 Cloudflare Tunnel 并自动检测公网URL
- 启动 cloudflared quick tunnel
- 从输出中提取 trycloudflare.com URL
- 验证 /wx/status 可达
- 输出配置指引（复制粘贴到微信测试号）
"""
import subprocess
import re
import sys
import time
import threading

GATEWAY_PORT = 8900
TOKEN = "smarthome2026"

def start_tunnel():
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{GATEWAY_PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    url = None
    print("[tunnel] Starting cloudflared...")

    for line in proc.stdout:
        line = line.strip()
        # 提取 URL
        m = re.search(r"(https://[a-z0-9-]+\.trycloudflare\.com)", line)
        if m and not url:
            url = m.group(1)
            print(f"\n{'='*60}")
            print(f"  Tunnel URL: {url}")
            print(f"  WeChat callback: {url}/wx")
            print(f"  Token: {TOKEN}")
            print(f"{'='*60}")
            print(f"\n  [微信测试号配置]")
            print(f"  URL:   {url}/wx")
            print(f"  Token: {TOKEN}")
            print(f"\n  [验证命令]")
            print(f"  python test_wx_public.py {url}")
            print(f"{'='*60}\n")

            # 后台验证
            def verify():
                time.sleep(3)
                try:
                    import httpx
                    r = httpx.get(f"{url}/wx/status", timeout=15)
                    if r.status_code == 200:
                        print(f"[tunnel] Public URL verified: /wx/status OK")
                    else:
                        print(f"[tunnel] Warning: /wx/status returned {r.status_code}")
                except Exception as e:
                    print(f"[tunnel] Warning: Could not verify public URL: {e}")
            threading.Thread(target=verify, daemon=True).start()

        # 显示关键日志
        if "INF" in line and ("Registered" in line or "created" in line or "Tunnel" in line):
            print(f"[tunnel] {line}")
        elif "ERR" in line and "cert" not in line.lower() and "certificate" not in line.lower():
            print(f"[tunnel] {line}")

    proc.wait()
    print(f"[tunnel] Process exited with code {proc.returncode}")

if __name__ == "__main__":
    try:
        start_tunnel()
    except KeyboardInterrupt:
        print("\n[tunnel] Stopped.")
