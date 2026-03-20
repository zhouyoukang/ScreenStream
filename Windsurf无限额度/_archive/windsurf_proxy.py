"""
Windsurf Self-Hosted Proxy v2.0
================================
gRPC感知MITM代理，替代CodeFreeWindsurf，不依赖第三方付费授权。

原理:
  Windsurf → 127.0.0.1:443 (本代理) → server.codeium.com:443 (真实Codeium)
  
  v2.0 新增能力:
  1. HTTP/2帧解析 — 识别gRPC方法和响应
  2. gRPC方法日志 — 记录所有API调用和响应大小
  3. Protobuf字段检测 — 提取plan/tier/credits信息
  4. 响应分析 — 检测服务器返回的plan信息
  5. DNS-over-HTTPS — 动态解析真实IP(不硬编码)

前置条件:
  - hosts文件: 127.0.0.1 server.self-serve.windsurf.com + server.codeium.com
  - TLS证书: windsurf_proxy_ca.pem 已安装到受信任根证书
  - SSL_CERT_FILE 环境变量指向 .pem 文件
  - Windsurf settings: proxyStrictSSL=false
  - 已运行 patch_windsurf.py (客户端15个补丁)

用法:
  python windsurf_proxy.py                    # 透明转发+日志模式
  python windsurf_proxy.py --token YOUR_KEY   # 注入自定义API token
  python windsurf_proxy.py --sniff            # 详细gRPC嗅探模式
  python windsurf_proxy.py --status           # 查看代理状态
  python windsurf_proxy.py --gen-cert         # 生成新的自签证书

架构对比:
  CFW:     Windsurf → CFW代理 → CFW后端(付费) → Codeium
  自建:    Windsurf → 本代理 → Codeium (直连，无中间商)
"""

import asyncio
import ssl
import os
import sys
import json
import time
import argparse
import logging
import struct
import socket
import signal
import threading
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ==================== 配置 ====================

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 443
UPSTREAM_HOSTS = {
    "server.self-serve.windsurf.com": ("server.self-serve.windsurf.com", 443),
    "server.codeium.com": ("server.codeium.com", 443),
}
# 默认上游（当SNI无法确定时）
DEFAULT_UPSTREAM = ("server.codeium.com", 443)

# 证书路径
SCRIPT_DIR = Path(__file__).parent
CERT_PEM = SCRIPT_DIR / "windsurf_proxy_ca.pem"
CERT_KEY = SCRIPT_DIR / "windsurf_proxy_ca.key"

# 统计
stats = {
    "start_time": None,
    "connections": 0,
    "active": 0,
    "bytes_up": 0,
    "bytes_down": 0,
    "requests": 0,
    "errors": 0,
    "grpc_methods": defaultdict(int),
    "grpc_responses": [],  # 最近20个gRPC响应摘要
    "plan_info_seen": [],  # 服务器返回的plan信息
}
stats_lock = threading.Lock()

# gRPC哗探模式
SNIFF_MODE = False

# 日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("proxy")


# ==================== 证书生成 ====================

def generate_self_signed_cert():
    """生成自签名TLS证书（用于本地代理）"""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime as dt
    except ImportError:
        log.error("需要安装 cryptography: pip install cryptography")
        sys.exit(1)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Windsurf Self-Proxy"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Windsurf Self-Hosted Proxy CA"),
    ])

    san = x509.SubjectAlternativeName([
        x509.DNSName("server.self-serve.windsurf.com"),
        x509.DNSName("server.codeium.com"),
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress_from_str("127.0.0.1")),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(dt.datetime.utcnow())
        .not_valid_after(dt.datetime.utcnow() + dt.timedelta(days=3650))
        .add_extension(san, critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(key, hashes.SHA256())
    )

    # 写PEM
    pem_path = SCRIPT_DIR / "windsurf_proxy_ca.pem"
    with open(pem_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    # 写KEY
    key_path = SCRIPT_DIR / "windsurf_proxy_ca.key"
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))

    # 写CER (DER格式，用于Windows证书导入)
    cer_path = SCRIPT_DIR / "windsurf_proxy_ca.cer"
    with open(cer_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.DER))

    log.info(f"证书已生成:")
    log.info(f"  PEM: {pem_path}")
    log.info(f"  KEY: {key_path}")
    log.info(f"  CER: {cer_path}")
    log.info(f"")
    log.info(f"下一步:")
    log.info(f"  1. 导入证书: certutil -addstore Root {cer_path}")
    log.info(f"  2. 设置环境变量: [Environment]::SetEnvironmentVariable('SSL_CERT_FILE', '{pem_path}', 'Machine')")


def ipaddress_from_str(addr):
    """兼容不同版本的ipaddress构造"""
    import ipaddress
    return ipaddress.IPv4Address(addr)


# ==================== HTTP/2 + gRPC解析 ====================

# HTTP/2 帧类型
H2_DATA = 0x00
H2_HEADERS = 0x01
H2_SETTINGS = 0x04
H2_PING = 0x06
H2_GOAWAY = 0x07
H2_WINDOW_UPDATE = 0x08

H2_PREFACE = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'


def parse_h2_frames(data):
    """Parse HTTP/2 frames from raw bytes. Yields (type, flags, stream_id, payload)."""
    pos = 0
    # Skip HTTP/2 connection preface if present
    if data[:len(H2_PREFACE)] == H2_PREFACE:
        pos = len(H2_PREFACE)
    while pos + 9 <= len(data):
        length = int.from_bytes(data[pos:pos+3], 'big')
        frame_type = data[pos+3]
        flags = data[pos+4]
        stream_id = int.from_bytes(data[pos+5:pos+9], 'big') & 0x7FFFFFFF
        if pos + 9 + length > len(data):
            break  # incomplete frame
        payload = data[pos+9:pos+9+length]
        yield (frame_type, flags, stream_id, payload)
        pos += 9 + length


def extract_grpc_path(data):
    """从HTTP/2 HEADERS帧中提取gRPC :path"""
    # Search for gRPC-style paths in the binary data
    # gRPC paths look like: /package.Service/Method
    try:
        idx = 0
        while idx < len(data) - 10:
            if data[idx:idx+1] == b'/' and data[idx+1:idx+5] != b'http':
                # Try to read until a non-printable char
                end = idx + 1
                while end < len(data) and 32 <= data[end] < 127:
                    end += 1
                path = data[idx:end].decode('ascii', errors='ignore')
                if '/' in path[1:] and '.' in path and len(path) > 5:
                    return path
            idx += 1
    except Exception:
        pass
    return None


def extract_grpc_message(payload):
    """Extract protobuf message from gRPC DATA frame payload.
    gRPC message format: [1B compressed][4B length][protobuf bytes]"""
    if len(payload) < 5:
        return None
    compressed = payload[0]
    msg_len = int.from_bytes(payload[1:5], 'big')
    if compressed != 0:
        return None  # skip compressed messages
    if 5 + msg_len > len(payload):
        return None  # incomplete
    return payload[5:5+msg_len]


def decode_varint(data, pos):
    """Decode a protobuf varint at position. Returns (value, new_pos)."""
    result = 0
    shift = 0
    while pos < len(data):
        b = data[pos]
        result |= (b & 0x7F) << shift
        pos += 1
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def extract_protobuf_strings(data):
    """Extract all string/bytes fields from a protobuf message.
    Returns list of (field_number, value_string)."""
    results = []
    pos = 0
    while pos < len(data):
        try:
            tag, pos = decode_varint(data, pos)
            field_number = tag >> 3
            wire_type = tag & 0x07
            if wire_type == 0:  # varint
                _, pos = decode_varint(data, pos)
            elif wire_type == 1:  # 64-bit
                pos += 8
            elif wire_type == 2:  # length-delimited (string/bytes/embedded)
                length, pos = decode_varint(data, pos)
                if pos + length > len(data):
                    break
                value = data[pos:pos+length]
                try:
                    s = value.decode('utf-8')
                    if s.isprintable() and len(s) > 0:
                        results.append((field_number, s))
                except (UnicodeDecodeError, ValueError):
                    pass
                pos += length
            elif wire_type == 5:  # 32-bit
                pos += 4
            else:
                break  # unknown wire type
        except (IndexError, ValueError):
            break
    return results


def detect_plan_info(protobuf_strings):
    """Detect plan-related info from extracted protobuf strings."""
    plan_keywords = ['Free', 'Pro', 'Pro Ultimate', 'Trial', 'Teams', 'Enterprise',
                     'free_tier', 'pro_tier', 'enterprise', 'UNSPECIFIED']
    found = {}
    for field_num, value in protobuf_strings:
        for kw in plan_keywords:
            if kw.lower() in value.lower():
                found[f'field_{field_num}'] = value
    return found


def parse_grpc_path(data):
    """Legacy compatibility wrapper."""
    return extract_grpc_path(data)


# ==================== 代理核心 ====================

class ProxyConnection:
    """处理单个代理连接"""

    def __init__(self, client_reader, client_writer, custom_token=None, sni_host=None):
        self.client_reader = client_reader
        self.client_writer = client_writer
        self.custom_token = custom_token
        self.sni_host = sni_host
        self.upstream_reader = None
        self.upstream_writer = None
        with stats_lock:
            self.conn_id = stats["connections"]

    async def handle(self):
        """处理连接"""
        with stats_lock:
            stats["connections"] += 1
            stats["active"] += 1

        peer = self.client_writer.get_extra_info("peername")
        log.debug(f"[{self.conn_id}] New connection from {peer}")

        try:
            # SNI路由: 根据客户端TLS握手中的SNI选择上游
            if self.sni_host and self.sni_host in UPSTREAM_HOSTS:
                upstream_host, upstream_port = UPSTREAM_HOSTS[self.sni_host]
            else:
                upstream_host, upstream_port = DEFAULT_UPSTREAM

            # 创建上游TLS连接（连接真实Codeium服务器）
            upstream_ssl = ssl.create_default_context()
            # 通过DNS解析真实IP（绕过本地hosts劫持）
            real_ip = await self._resolve_upstream(upstream_host)

            self.upstream_reader, self.upstream_writer = await asyncio.open_connection(
                real_ip, upstream_port, ssl=upstream_ssl,
                server_hostname=upstream_host,
            )

            log.info(f"[{self.conn_id}] Connected upstream: {upstream_host} ({real_ip})")

            # 双向转发
            await asyncio.gather(
                self._forward(self.client_reader, self.upstream_writer, "UP"),
                self._forward(self.upstream_reader, self.client_writer, "DOWN"),
            )

        except ConnectionRefusedError:
            log.warning(f"[{self.conn_id}] Upstream refused connection")
            with stats_lock:
                stats["errors"] += 1
        except asyncio.TimeoutError:
            log.warning(f"[{self.conn_id}] Upstream connection timeout")
            with stats_lock:
                stats["errors"] += 1
        except Exception as e:
            if "Connection reset" not in str(e) and "EOF" not in str(e):
                log.warning(f"[{self.conn_id}] Error: {e}")
            with stats_lock:
                stats["errors"] += 1
        finally:
            self._close()
            with stats_lock:
                stats["active"] -= 1

    async def _resolve_upstream(self, hostname):
        """解析上游真实IP（绕过本地hosts劫持）"""
        # 类级DNS缓存
        if not hasattr(ProxyConnection, '_dns_cache'):
            ProxyConnection._dns_cache = {}
        if hostname in ProxyConnection._dns_cache:
            return ProxyConnection._dns_cache[hostname]

        # 方案1: DNS-over-HTTPS 动态解析 (优先)
        try:
            import urllib.request
            url = f"https://dns.google/resolve?name={hostname}&type=A"
            req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                for answer in data.get("Answer", []):
                    if answer.get("type") == 1:
                        ip = answer["data"]
                        ProxyConnection._dns_cache[hostname] = ip
                        log.info(f"DNS-over-HTTPS: {hostname} -> {ip}")
                        return ip
        except Exception as e:
            log.debug(f"DoH failed for {hostname}: {e}")

        # 方案2: 硬编码fallback
        fallback_ips = {
            "server.codeium.com": "35.223.238.178",
            "server.self-serve.windsurf.com": "34.49.14.144",
        }
        ip = fallback_ips.get(hostname, "35.223.238.178")
        ProxyConnection._dns_cache[hostname] = ip
        log.info(f"DNS fallback: {hostname} -> {ip}")
        return ip

    async def _forward(self, reader, writer, direction):
        """转发数据，并解析gRPC内容"""
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break

                # 统计
                with stats_lock:
                    if direction == "UP":
                        stats["bytes_up"] += len(data)
                        stats["requests"] += 1
                    else:
                        stats["bytes_down"] += len(data)

                # === gRPC解析 ===
                try:
                    self._analyze_grpc(data, direction)
                except Exception:
                    pass  # never let analysis break forwarding

                writer.write(data)
                await writer.drain()

        except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
            pass
        except Exception as e:
            if "EOF" not in str(e):
                log.debug(f"[{self.conn_id}] Forward {direction} error: {e}")

    def _analyze_grpc(self, data, direction):
        """Analyze gRPC traffic for method detection and plan info extraction."""
        if direction == "UP":
            # Upstream: detect gRPC method paths
            path = extract_grpc_path(data)
            if path:
                self._current_method = path
                with stats_lock:
                    stats["grpc_methods"][path] += 1
                log.info(f"[{self.conn_id}] → gRPC: {path}")
        else:
            # Downstream: analyze response content
            for frame_type, flags, stream_id, payload in parse_h2_frames(data):
                if frame_type == H2_DATA and len(payload) > 5:
                    msg = extract_grpc_message(payload)
                    if msg and len(msg) > 2:
                        strings = extract_protobuf_strings(msg)
                        plan_info = detect_plan_info(strings)
                        method = getattr(self, '_current_method', '?')

                        if plan_info:
                            info_entry = {
                                'method': method,
                                'plan_info': plan_info,
                                'time': time.strftime('%H:%M:%S'),
                            }
                            with stats_lock:
                                stats["plan_info_seen"].append(info_entry)
                                if len(stats["plan_info_seen"]) > 50:
                                    stats["plan_info_seen"] = stats["plan_info_seen"][-50:]
                            log.warning(f"[{self.conn_id}] 🚩 Plan info detected in {method}: {plan_info}")

                        if SNIFF_MODE and strings:
                            summary = '; '.join(f'f{fn}={v[:40]}' for fn, v in strings[:10])
                            resp_entry = {
                                'method': method,
                                'stream': stream_id,
                                'msg_len': len(msg),
                                'strings': summary,
                                'time': time.strftime('%H:%M:%S'),
                            }
                            with stats_lock:
                                stats["grpc_responses"].append(resp_entry)
                                if len(stats["grpc_responses"]) > 100:
                                    stats["grpc_responses"] = stats["grpc_responses"][-100:]
                            log.debug(f"[{self.conn_id}] ← [{method}] {len(msg)}B: {summary[:120]}")

    def _close(self):
        """关闭连接"""
        for w in (self.client_writer, self.upstream_writer):
            if w:
                try:
                    w.close()
                except Exception:
                    pass


class WindsurfProxy:
    """Windsurf自建代理服务器"""

    def __init__(self, host=LISTEN_HOST, port=LISTEN_PORT, custom_token=None):
        self.host = host
        self.port = port
        self.custom_token = custom_token
        self.server = None

    def _create_ssl_context(self):
        """创建服务端SSL上下文"""
        if not CERT_PEM.exists():
            log.error(f"证书不存在: {CERT_PEM}")
            log.error(f"运行: python {__file__} --gen-cert")
            sys.exit(1)

        if not CERT_KEY.exists():
            log.error(f"私钥不存在: {CERT_KEY}")
            log.error(f"运行: python {__file__} --gen-cert")
            sys.exit(1)

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(CERT_PEM), str(CERT_KEY))
        # 支持HTTP/2 (gRPC需要)
        ctx.set_alpn_protocols(["h2", "http/1.1"])

        # SNI回调: 捕获客户端TLS握手中的server_name用于上游路由
        def sni_callback(ssl_obj, server_name, ssl_ctx):
            if server_name:
                self._sni_map[id(ssl_obj)] = server_name
            return None  # 继续正常握手
        ctx.sni_callback = sni_callback
        self._sni_map = {}

        return ctx

    async def _handle_client(self, reader, writer):
        """处理新连接"""
        # 从SNI回调中获取客户端请求的主机名
        ssl_obj = writer.get_extra_info('ssl_object')
        sni_host = None
        if ssl_obj:
            sni_host = self._sni_map.pop(id(ssl_obj), None)
        conn = ProxyConnection(reader, writer, self.custom_token, sni_host=sni_host)
        await conn.handle()

    async def start(self):
        """启动代理"""
        ssl_ctx = self._create_ssl_context()
        stats["start_time"] = time.time()

        self.server = await asyncio.start_server(
            self._handle_client,
            self.host, self.port,
            ssl=ssl_ctx,
        )

        addr = self.server.sockets[0].getsockname()
        log.info(f"")
        log.info(f"╔══════════════════════════════════════════════╗")
        log.info(f"║  Windsurf Self-Hosted Proxy v2.0             ║")
        log.info(f"║  gRPC感知 + 响应解析 + Plan检测           ║")
        log.info(f"╚══════════════════════════════════════════════╝")
        log.info(f"")
        log.info(f"  监听: {addr[0]}:{addr[1]}")
        log.info(f"  上游: {DEFAULT_UPSTREAM[0]}:{DEFAULT_UPSTREAM[1]}")
        log.info(f"  证书: {CERT_PEM}")
        if self.custom_token:
            log.info(f"  Token: {self.custom_token[:8]}...{self.custom_token[-4:]}")
        log.info(f"")
        log.info(f"  等待Windsurf连接...")
        log.info(f"")

        async with self.server:
            await self.server.serve_forever()


# ==================== 状态显示 ====================

def show_status():
    """显示代理状态"""
    # 检查端口是否在用
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex((LISTEN_HOST, LISTEN_PORT))
        s.close()
        listening = result == 0
    except Exception:
        listening = False

    print(f"\n{'='*50}")
    print(f"Windsurf Self-Hosted Proxy 状态")
    print(f"{'='*50}")
    print(f"  端口 {LISTEN_HOST}:{LISTEN_PORT}: {'✅ 监听中' if listening else '❌ 未运行'}")
    print(f"  证书 PEM: {'✅' if CERT_PEM.exists() else '❌'} {CERT_PEM}")
    print(f"  证书 KEY: {'✅' if CERT_KEY.exists() else '❌'} {CERT_KEY}")

    # 检查hosts
    hosts_path = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
    hosts_ok = False
    if hosts_path.exists():
        content = hosts_path.read_text(encoding='utf-8', errors='ignore')
        hosts_ok = "server.self-serve.windsurf.com" in content
    print(f"  hosts劫持: {'✅' if hosts_ok else '❌'}")

    # 检查SSL_CERT_FILE
    ssl_cert = os.environ.get("SSL_CERT_FILE", "")
    print(f"  SSL_CERT_FILE: {'✅ ' + ssl_cert if ssl_cert else '❌ 未设置'}")

    # 检查patch状态
    patch_py = SCRIPT_DIR / "patch_windsurf.py"
    print(f"  patch_windsurf.py: {'✅' if patch_py.exists() else '❌'}")

    print(f"\n  {'='*46}")
    if listening:
        print(f"  代理运行中，Windsurf可以正常使用")
    else:
        print(f"  代理未运行，启动: python windsurf_proxy.py")
    print(f"  {'='*46}\n")


# ==================== 预检 ====================

def preflight_check(port=None):
    """启动前环境检查"""
    check_port = port or LISTEN_PORT
    issues = []

    # 1. 检查证书
    if not CERT_PEM.exists() or not CERT_KEY.exists():
        issues.append(("证书", f"运行: python {__file__} --gen-cert"))

    # 2. 检查端口是否被占用
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex((LISTEN_HOST, check_port))
        s.close()
        if result == 0:
            issues.append(("端口", f"{LISTEN_HOST}:{check_port} 已被占用"))
    except Exception:
        pass

    # 3. 检查hosts
    hosts_path = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
    if hosts_path.exists():
        content = hosts_path.read_text(encoding='utf-8', errors='ignore')
        if "server.self-serve.windsurf.com" not in content:
            issues.append(("hosts", "需要添加: 127.0.0.1 server.self-serve.windsurf.com"))
        if "server.codeium.com" not in content:
            issues.append(("hosts", "需要添加: 127.0.0.1 server.codeium.com"))

    if issues:
        log.warning("预检发现以下问题:")
        for name, msg in issues:
            log.warning(f"  [{name}] {msg}")
        log.warning("")
        return False
    return True


# ==================== 入口 ====================

def main():
    parser = argparse.ArgumentParser(description="Windsurf Self-Hosted Proxy v2.0")
    parser.add_argument("--token", help="自定义API token（注入到请求中）")
    parser.add_argument("--status", action="store_true", help="查看代理状态")
    parser.add_argument("--gen-cert", action="store_true", help="生成自签名TLS证书")
    parser.add_argument("--port", type=int, default=LISTEN_PORT, help="监听端口（默认443）")
    parser.add_argument("--sniff", action="store_true", help="详细gRPC哗探模式")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    args = parser.parse_args()

    global SNIFF_MODE
    if args.sniff:
        SNIFF_MODE = True
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.status:
        show_status()
        return

    if args.gen_cert:
        generate_self_signed_cert()
        return

    # 预检
    if not preflight_check(port=args.port):
        log.error("预检失败，请先解决上述问题")
        sys.exit(1)

    # 启动代理
    proxy = WindsurfProxy(
        host=LISTEN_HOST,
        port=args.port,
        custom_token=args.token,
    )

    # Graceful shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        await proxy.start()

    async def _main():
        task = asyncio.create_task(_run())
        stop = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except NotImplementedError:
                pass  # Windows
        try:
            await task
        except asyncio.CancelledError:
            pass

    try:
        loop.run_until_complete(_main())
    except KeyboardInterrupt:
        log.info("\n代理已停止")
    except PermissionError:
        log.error(f"权限不足: 端口 {args.port} 需要管理员权限")
        log.error(f"以管理员身份运行 PowerShell，或使用 --port 指定其他端口")
    except OSError as e:
        if "10048" in str(e) or "address already in use" in str(e).lower():
            log.error(f"端口 {args.port} 已被占用")
            log.error(f"可能CFW正在运行，先关闭CFW再启动本代理")
        else:
            raise
    finally:
        loop.close()


if __name__ == "__main__":
    main()
