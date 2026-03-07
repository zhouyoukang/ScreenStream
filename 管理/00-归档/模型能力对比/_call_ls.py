"""用CSRF Token调用Windsurf语言服务器 — 突破口！"""
import http.client
import json
import subprocess
import struct
import time
import sys

def get_csrf_tokens():
    """从语言服务器进程命令行提取CSRF Token"""
    result = subprocess.run(
        ["powershell", "-Command",
         "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'language_server' } | "
         "Select-Object ProcessId, CommandLine | ConvertTo-Json"],
        capture_output=True, text=True, timeout=10
    )
    tokens = []
    if result.returncode == 0 and result.stdout.strip():
        data = json.loads(result.stdout)
        if not isinstance(data, list):
            data = [data]
        for proc in data:
            cmd = proc.get("CommandLine", "")
            parts = cmd.split()
            for i, p in enumerate(parts):
                if p == "--csrf_token" and i + 1 < len(parts):
                    port = None
                    for j, q in enumerate(parts):
                        if q == "--extension_server_port" and j + 1 < len(parts):
                            port = parts[j + 1]
                    tokens.append({
                        "pid": proc["ProcessId"],
                        "csrf": parts[i + 1],
                        "ext_port": port,
                    })
    return tokens


def get_ls_ports():
    """获取语言服务器监听端口"""
    result = subprocess.run(
        ["powershell", "-Command",
         "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'language_server' } | "
         "ForEach-Object { $pid = $_.ProcessId; "
         "Get-NetTCPConnection -OwningProcess $pid -State Listen -ErrorAction SilentlyContinue | "
         "Select-Object @{N='PID';E={$pid}}, LocalPort } | ConvertTo-Json"],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0 and result.stdout.strip():
        data = json.loads(result.stdout)
        if not isinstance(data, list):
            data = [data]
        return data
    return []


def connect_call(host, port, path, csrf_token, body=None, content_type="application/json"):
    """通过Connect协议调用gRPC服务"""
    conn = http.client.HTTPConnection(host, port, timeout=10)
    headers = {
        "Content-Type": content_type,
        "connect-protocol-version": "1",
        "csrf-token": csrf_token,
    }
    payload = body if body else b"{}"
    conn.request("POST", path, body=payload, headers=headers)
    r = conn.getresponse()
    resp_body = r.read()
    ct = r.getheader("content-type", "?")
    return r.status, r.reason, ct, resp_body


def main():
    print("=" * 60)
    print("Windsurf 语言服务器直调 (CSRF Token认证)")
    print("=" * 60)

    # 1. 提取CSRF tokens
    tokens = get_csrf_tokens()
    print(f"\n找到 {len(tokens)} 个语言服务器进程:")
    for t in tokens:
        print(f"  PID={t['pid']} CSRF={t['csrf'][:8]}... ext_port={t['ext_port']}")

    # 2. 获取所有监听端口
    port_data = get_ls_ports()
    print(f"\n监听端口: {[d['LocalPort'] for d in port_data]}")

    # 3. 匹配PID → 找出哪个端口属于哪个进程
    pid_ports = {}
    for d in port_data:
        pid = d["PID"]
        if pid not in pid_ports:
            pid_ports[pid] = []
        pid_ports[pid].append(d["LocalPort"])

    print("\nPID → 端口映射:")
    for pid, ports in pid_ports.items():
        csrf = next((t["csrf"] for t in tokens if t["pid"] == pid), None)
        print(f"  PID {pid}: ports={ports} csrf={csrf[:8] if csrf else 'NONE'}...")

    # 4. 用CSRF token尝试每个端口
    print("\n" + "=" * 60)
    print("尝试用CSRF Token认证调用...")
    print("=" * 60)

    gRPC_methods = [
        "/exa.language_server_pb.LanguageServerService/Heartbeat",
        "/exa.language_server_pb.LanguageServerService/GetProcesses",
        "/exa.language_server_pb.LanguageServerService/GetCompletions",
        "/exa.seat_management_pb.SeatManagementService/GetUser",
    ]

    success_ports = []

    for pid, ports in pid_ports.items():
        csrf = next((t["csrf"] for t in tokens if t["pid"] == pid), None)
        if not csrf:
            print(f"\n  PID {pid}: 无CSRF token，跳过")
            continue

        for port in ports:
            print(f"\n  === PID {pid} Port {port} ===")
            for method in gRPC_methods:
                try:
                    status, reason, ct, body = connect_call("127.0.0.1", port, method, csrf)
                    body_preview = body[:120].decode(errors="replace") if body else ""
                    icon = "OK" if status == 200 else f"ERR({status})"
                    print(f"    {icon} {method.split('/')[-1]}: {status} ct={ct} body={body_preview[:80]}")
                    if status == 200:
                        success_ports.append((port, csrf, method))
                except Exception as e:
                    print(f"    ERR {method.split('/')[-1]}: {type(e).__name__}: {str(e)[:60]}")
                    break  # port not responding, skip other methods

    # 5. 如果找到成功端口，尝试更多调用
    if success_ports:
        print("\n" + "=" * 60)
        print(f"成功！找到 {len(success_ports)} 个可调用端点")
        print("=" * 60)

        port, csrf, _ = success_ports[0]
        print(f"\n使用 Port {port} 进行深度探测...")

        # 尝试获取聊天相关API
        chat_methods = [
            "/exa.language_server_pb.LanguageServerService/GetChatMessage",
            "/exa.language_server_pb.LanguageServerService/RecordEvent",
            "/exa.windsurf_pb.WindsurfService/GetChatMessage",
            "/exa.windsurf_pb.WindsurfService/CreateChatMessage",
            "/exa.windsurf_pb.WindsurfService/GetAvailableModels",
        ]
        for method in chat_methods:
            try:
                status, reason, ct, body = connect_call("127.0.0.1", port, method, csrf)
                body_str = body[:200].decode(errors="replace") if body else ""
                print(f"  {method.split('/')[-1]}: {status} {ct} -> {body_str[:100]}")
            except Exception as e:
                print(f"  {method.split('/')[-1]}: {type(e).__name__}")

        # 尝试发送实际聊天请求
        print("\n--- 尝试发送聊天请求 ---")
        chat_payload = json.dumps({
            "metadata": {
                "ide_name": "windsurf",
                "ide_version": "1.9566.11",
                "extension_version": "1.9566.11",
            },
            "chat_message": {
                "text": "Say hello",
                "source": "CHAT_MESSAGE_SOURCE_USER",
                "intent": {
                    "intent": "CHAT_MESSAGE_INTENT_CHAT",
                },
            },
        }).encode()
        try:
            status, reason, ct, body = connect_call("127.0.0.1", port,
                "/exa.language_server_pb.LanguageServerService/GetChatMessage",
                csrf, body=chat_payload)
            body_str = body[:500].decode(errors="replace") if body else ""
            print(f"  Chat Response: {status} {ct}")
            print(f"  Body: {body_str[:300]}")
        except Exception as e:
            print(f"  Chat Error: {type(e).__name__}: {e}")

    else:
        print("\n❌ 所有端口认证失败")
        print("可能原因: CSRF token不匹配端口, 或需要其他认证头")

    # 6. 总结
    print("\n" + "=" * 60)
    print("总结:")
    print(f"  语言服务器进程: {len(tokens)}")
    print(f"  总监听端口: {sum(len(p) for p in pid_ports.values())}")
    print(f"  成功端点: {len(success_ports)}")
    if success_ports:
        for port, csrf, method in success_ports[:5]:
            print(f"    Port {port}: {method.split('/')[-1]}")


if __name__ == "__main__":
    main()
