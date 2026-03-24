"""
手机公网网关 — 道法自然·水到渠成
==========================================
三层穿透:  WiFi直连 → USB ADB forward → 手机直连FRP
公网入口:  https://aiotvr.xyz/phone/  (Nginx → FRP → 本网关)
认证方式:  Bearer Token (X-Gateway-Token)

使用:
  python phone_gateway.py                     # 启动网关 (:28084)
  python phone_gateway.py --token MY_SECRET   # 自定义Token
  python phone_gateway.py --probe             # 仅探测不启动
  python phone_gateway.py --setup-phone-frpc  # 配置手机端FRP直连

架构:
  Agent(公网) → 阿里云Nginx → FRP → 台式机:28084(本网关) → 手机:8084
  Agent(公网) → 阿里云Nginx → 手机FRP直连 → 手机:8084 (备用)
"""

import json, os, sys, time, logging, hashlib, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# ============================================================
# 配置
# ============================================================

PORT = 28084
PHONE_WIFI_IP = "192.168.31.40"
PHONE_SS_PORT = 8084
PHONE_GW_PORT = 8080
PHONE_SERIAL = "158377ff"

# 多路径探测顺序 (上善若水，水到渠成)
PATHS = [
    {"name": "WiFi直连",   "base": f"http://{PHONE_WIFI_IP}:{PHONE_SS_PORT}"},
    {"name": "USB转发",    "base": f"http://127.0.0.1:{PHONE_SS_PORT}"},
    {"name": "USB高端口",  "base": f"http://127.0.0.1:18084"},
]

# Token认证 (从环境变量或命令行获取)
DEFAULT_TOKEN = hashlib.sha256(
    f"phone-gateway-{PHONE_SERIAL}".encode()
).hexdigest()[:32]

log = logging.getLogger("gateway")
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s [GW] %(message)s", "%H:%M:%S"))
    log.addHandler(h)
    log.setLevel(logging.INFO)


# ============================================================
# 手机探测与连接管理
# ============================================================

class PhoneConnector:
    """多路径手机连接器 — 自动发现最优路径，断线自愈"""

    def __init__(self):
        self.active_base = None
        self.active_name = None
        self.last_ok = None
        self.fail_count = 0
        self._lock = threading.Lock()
        self._heartbeat_thread = None
        self._running = False
        self.stats = {
            "total_requests": 0,
            "success": 0,
            "errors": 0,
            "recoveries": 0,
            "uptime_start": datetime.now().isoformat(),
        }

    def probe_path(self, base, timeout=3):
        """探测单条路径是否可达"""
        try:
            url = f"{base}/status"
            req = Request(url, method="GET")
            with urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
                return data.get("connected", False), data
        except Exception:
            return False, {}

    def discover(self):
        """发现最优连接路径"""
        with self._lock:
            for p in PATHS:
                ok, data = self.probe_path(p["base"])
                if ok:
                    self.active_base = p["base"]
                    self.active_name = p["name"]
                    self.last_ok = datetime.now().isoformat()
                    log.info(f"✅ 连接: {p['name']} → {p['base']}")
                    return True
            self.active_base = None
            self.active_name = None
            log.warning("❌ 所有路径均不可达")
            return False

    def ensure_adb_forward(self):
        """确保ADB端口转发就绪"""
        try:
            import subprocess
            adb = self._find_adb()
            if not adb:
                return False
            # 检查设备
            r = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=5)
            if PHONE_SERIAL not in r.stdout:
                return False
            # 建立转发
            subprocess.run(
                [adb, "-s", PHONE_SERIAL, "forward", f"tcp:{PHONE_SS_PORT}", f"tcp:{PHONE_SS_PORT}"],
                capture_output=True, timeout=5
            )
            time.sleep(0.3)
            return True
        except Exception as e:
            log.debug(f"ADB forward failed: {e}")
            return False

    def _find_adb(self):
        """查找ADB路径"""
        for p in [r"D:\platform-tools\adb.exe", "adb", "adb.exe"]:
            try:
                import subprocess
                r = subprocess.run([p, "version"], capture_output=True, timeout=3)
                if r.returncode == 0:
                    return p
            except Exception:
                continue
        return None

    def recover(self):
        """自动恢复 — 尝试所有手段让手机重新可达"""
        log.info("🔄 开始自动恢复...")
        self.stats["recoveries"] += 1

        # 1. 先重试WiFi
        ok, _ = self.probe_path(PATHS[0]["base"], timeout=5)
        if ok:
            self.active_base = PATHS[0]["base"]
            self.active_name = PATHS[0]["name"]
            self.last_ok = datetime.now().isoformat()
            log.info("✅ WiFi恢复成功")
            return True

        # 2. 尝试ADB唤醒
        self.ensure_adb_forward()
        try:
            adb = self._find_adb()
            if adb:
                import subprocess
                # 唤醒屏幕
                subprocess.run(
                    [adb, "-s", PHONE_SERIAL, "shell", "input", "keyevent", "KEYCODE_WAKEUP"],
                    capture_output=True, timeout=5
                )
                time.sleep(1)
        except Exception:
            pass

        # 3. 重新发现
        return self.discover()

    def proxy(self, method, path, body=None, headers=None, timeout=15):
        """代理请求到手机"""
        self.stats["total_requests"] += 1

        if not self.active_base:
            if not self.discover():
                self.stats["errors"] += 1
                return 502, {"error": "Phone unreachable", "paths_tried": len(PATHS)}

        url = self.active_base + path
        data = body if body else None
        hdrs = headers or {}
        if data and "Content-Type" not in hdrs:
            hdrs["Content-Type"] = "application/json"

        try:
            req = Request(url, data=data, headers=hdrs, method=method)
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
                self.stats["success"] += 1
                self.fail_count = 0
                self.last_ok = datetime.now().isoformat()
                try:
                    return resp.status, json.loads(raw)
                except Exception:
                    return resp.status, {"_raw": raw}
        except HTTPError as e:
            self.stats["success"] += 1  # HTTP error is still reachable
            try:
                body_text = e.read().decode()
                return e.code, {"_error": e.code, "_body": body_text[:500]}
            except Exception:
                return e.code, {"_error": e.code}
        except (URLError, OSError, TimeoutError) as e:
            self.fail_count += 1
            self.stats["errors"] += 1
            if self.fail_count >= 2:
                log.warning(f"连续{self.fail_count}次失败，尝试恢复...")
                self.recover()
            return 502, {"error": str(e)}

    def health(self):
        """健康状态"""
        phone_ok = False
        phone_status = {}
        if self.active_base:
            phone_ok, phone_status = self.probe_path(self.active_base)

        return {
            "gateway": "running",
            "phone_reachable": phone_ok,
            "active_path": self.active_name,
            "active_base": self.active_base,
            "last_ok": self.last_ok,
            "fail_count": self.fail_count,
            "phone_status": phone_status,
            "stats": self.stats,
            "timestamp": datetime.now().isoformat(),
        }

    def start_heartbeat(self, interval=30):
        """启动心跳守护线程"""
        self._running = True
        def _loop():
            while self._running:
                time.sleep(interval)
                if not self.active_base:
                    self.discover()
                    continue
                ok, _ = self.probe_path(self.active_base, timeout=5)
                if not ok:
                    log.warning("💔 心跳丢失，自动恢复中...")
                    self.recover()
        self._heartbeat_thread = threading.Thread(target=_loop, daemon=True)
        self._heartbeat_thread.start()
        log.info(f"💓 心跳守护启动 (每{interval}秒)")

    def stop(self):
        self._running = False


# ============================================================
# HTTP网关服务
# ============================================================

connector = PhoneConnector()
GATEWAY_TOKEN = DEFAULT_TOKEN


class GatewayHandler(BaseHTTPRequestHandler):
    """公网网关HTTP处理器"""

    def log_message(self, format, *args):
        log.debug(f"{self.client_address[0]} {format % args}")

    def _auth(self):
        """Token认证"""
        token = self.headers.get("X-Gateway-Token") or ""
        if not token:
            # 从URL参数获取
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            token = qs.get("token", [""])[0]
        if token != GATEWAY_TOKEN:
            self._json(401, {"error": "Unauthorized", "hint": "Set X-Gateway-Token header"})
            return False
        return True

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Gateway-Token")
        self.end_headers()

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")

    def _handle(self, method):
        parsed = urlparse(self.path)
        path = parsed.path
        query = f"?{parsed.query}" if parsed.query else ""

        # 公开端点 (不需认证)
        if path == "/gw/health":
            self._json(200, connector.health())
            return
        if path == "/gw/ping":
            self._json(200, {"pong": True, "time": datetime.now().isoformat()})
            return

        # 认证
        if not self._auth():
            return

        # 网关管理端点
        if path == "/gw/discover":
            ok = connector.discover()
            self._json(200, {"ok": ok, **connector.health()})
            return
        if path == "/gw/recover":
            ok = connector.recover()
            self._json(200, {"ok": ok, **connector.health()})
            return
        if path == "/gw/stats":
            self._json(200, connector.stats)
            return
        if path == "/gw/token":
            self._json(200, {"token": GATEWAY_TOKEN})
            return

        # 代理到手机 — 去掉 /gw 前缀如果有
        phone_path = path
        if phone_path.startswith("/phone"):
            phone_path = phone_path[6:]  # strip /phone prefix
        phone_path = phone_path + query

        # 读取请求体
        body = None
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            body = self.rfile.read(content_length)

        # 转发请求头 (去除认证相关)
        fwd_headers = {}
        ct = self.headers.get("Content-Type")
        if ct:
            fwd_headers["Content-Type"] = ct

        code, data = connector.proxy(method, phone_path, body, fwd_headers)
        self._json(code, data)


class ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


# ============================================================
# 手机端FRP配置与部署
# ============================================================

def setup_phone_frpc():
    """在手机上配置并启动frpc直连阿里云"""
    import subprocess

    adb = connector._find_adb()
    if not adb:
        print("❌ ADB不可用")
        return False

    # 检查设备
    r = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=5)
    if PHONE_SERIAL not in r.stdout:
        print(f"❌ 设备 {PHONE_SERIAL} 未连接")
        return False

    print("📱 配置手机端FRP直连阿里云...")

    # frpc配置
    frpc_config = """serverAddr = "60.205.171.100"
serverPort = 7000
auth.method = "token"
auth.token = "NKLQyCrSavf1MmYOGtkFzbh0"
user = "oneplus"
loginFailExit = false

# ScreenStream Input API (8084)
[[proxies]]
name = "phone_input"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8084
remotePort = 28084

# ScreenStream Gateway (8080)
[[proxies]]
name = "phone_stream"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8080
remotePort = 28080
"""

    # 写入临时配置文件
    import tempfile
    config_path = os.path.join(tempfile.gettempdir(), "frpc_phone.toml")
    with open(config_path, "w") as f:
        f.write(frpc_config)

    # 推送到手机
    phone_config_dir = "/data/local/tmp/frpc"
    subprocess.run([adb, "-s", PHONE_SERIAL, "shell", f"su -c 'mkdir -p {phone_config_dir}'"],
                   capture_output=True, timeout=5)
    subprocess.run([adb, "-s", PHONE_SERIAL, "push", config_path, f"{phone_config_dir}/frpc.toml"],
                   capture_output=True, timeout=5)
    print(f"  ✅ 配置已推送: {phone_config_dir}/frpc.toml")

    # 检查手机上是否有frpc二进制
    r = subprocess.run(
        [adb, "-s", PHONE_SERIAL, "shell", "su -c 'which frpc 2>/dev/null || ls /data/local/tmp/frpc/frpc 2>/dev/null'"],
        capture_output=True, text=True, timeout=5
    )
    has_frpc = bool(r.stdout.strip())

    if not has_frpc:
        print("  ⚠️ 手机上未找到frpc二进制文件")
        print("  📋 需要手动安装:")
        print(f"     1. 下载 frpc ARM64: https://github.com/fatedier/frp/releases")
        print(f"     2. adb push frpc {phone_config_dir}/frpc")
        print(f"     3. adb shell \"su -c 'chmod +x {phone_config_dir}/frpc'\"")
        print(f"  📋 或者使用手机上的FRP应用(com.tools.frp)导入配置:")
        print(f"     配置文件: {phone_config_dir}/frpc.toml")

        # 尝试通过手机FRP应用 — 写入其配置目录
        frp_app_dir = "/data/data/com.tools.frp/files"
        subprocess.run(
            [adb, "-s", PHONE_SERIAL, "shell",
             f"su -c 'cp {phone_config_dir}/frpc.toml {frp_app_dir}/frpc.toml 2>/dev/null'"],
            capture_output=True, timeout=5
        )
        print(f"  📋 也已尝试复制到FRP App目录: {frp_app_dir}/")
        return False

    # 启动frpc
    print("  🚀 启动手机端frpc...")
    subprocess.run(
        [adb, "-s", PHONE_SERIAL, "shell",
         f"su -c 'nohup {phone_config_dir}/frpc -c {phone_config_dir}/frpc.toml > /dev/null 2>&1 &'"],
        capture_output=True, timeout=5
    )
    time.sleep(2)

    # 验证
    r = subprocess.run(
        [adb, "-s", PHONE_SERIAL, "shell", "su -c 'ps -A | grep frpc'"],
        capture_output=True, text=True, timeout=5
    )
    if "frpc" in r.stdout:
        print("  ✅ 手机frpc已启动")
        return True
    else:
        print("  ⚠️ frpc未能启动，请检查日志")
        return False


# ============================================================
# 探测与诊断
# ============================================================

def probe_all():
    """全路径探测"""
    print("\n" + "=" * 60)
    print("  📡 手机公网网关 · 全路径探测")
    print("=" * 60)

    results = []
    for p in PATHS:
        ok, data = connector.probe_path(p["base"])
        status = "✅" if ok else "❌"
        detail = f"connected={data.get('connected')}, input={data.get('inputEnabled')}" if data else "不可达"
        results.append((p["name"], p["base"], ok, detail))
        print(f"  {status} {p['name']:12s} {p['base']:35s} {detail}")

    # 测试阿里云公网路径
    public_paths = [
        ("阿里云/input", "https://aiotvr.xyz/input"),
        ("阿里云/phone", f"http://60.205.171.100:28084"),
    ]
    print()
    for name, base in public_paths:
        try:
            req = Request(f"{base}/status", method="GET")
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                ok = data.get("connected", False)
                print(f"  {'✅' if ok else '⚠️'} {name:20s} {base}")
        except Exception as e:
            print(f"  ❌ {name:20s} {base:35s} {str(e)[:40]}")

    # 五感快速验证
    print(f"\n  🧠 五感快速验证 (via {connector.active_name or '未连接'}):")
    if connector.active_base:
        endpoints = [
            ("👁 视觉", "/screen/text", lambda d: f"texts={d.get('textCount',0)}"),
            ("👂 听觉", "/deviceinfo", lambda d: f"vol={d.get('volumeMusic','?')}"),
            ("🖐 触觉", "/status", lambda d: f"input={d.get('inputEnabled')}"),
            ("👃 嗅觉", "/notifications/read?limit=3", lambda d: f"total={d.get('total','?')}"),
            ("👅 味觉", "/deviceinfo", lambda d: f"bat={d.get('batteryLevel','?')}% net={d.get('networkType','?')}"),
        ]
        for icon_name, ep, fmt in endpoints:
            try:
                code, data = connector.proxy("GET", ep)
                ok = code == 200 and "_error" not in data
                detail = fmt(data) if ok else str(data)[:40]
                print(f"     {'✅' if ok else '❌'} {icon_name}: {detail}")
            except Exception as e:
                print(f"     ❌ {icon_name}: {e}")
    else:
        print("     ❌ 手机未连接")

    print("=" * 60)
    return results


# ============================================================
# 主入口
# ============================================================

def main():
    global GATEWAY_TOKEN

    import argparse
    parser = argparse.ArgumentParser(description="手机公网网关 · 道法自然")
    parser.add_argument("--port", type=int, default=PORT, help=f"网关端口 (默认{PORT})")
    parser.add_argument("--token", default=None, help="认证Token (默认自动生成)")
    parser.add_argument("--probe", action="store_true", help="仅探测不启动")
    parser.add_argument("--setup-phone-frpc", action="store_true", help="配置手机端FRP直连")
    parser.add_argument("--heartbeat", type=int, default=30, help="心跳间隔秒 (0=关闭)")
    parser.add_argument("--no-auth", action="store_true", help="关闭认证 (仅调试)")
    args = parser.parse_args()

    if args.token:
        GATEWAY_TOKEN = args.token
    elif os.environ.get("PHONE_GATEWAY_TOKEN"):
        GATEWAY_TOKEN = os.environ["PHONE_GATEWAY_TOKEN"]

    if args.no_auth:
        GATEWAY_TOKEN = ""

    # 配置手机FRP
    if args.setup_phone_frpc:
        setup_phone_frpc()
        return

    # 发现手机
    connector.discover()

    # 探测模式
    if args.probe:
        probe_all()
        return

    # 启动心跳
    if args.heartbeat > 0:
        connector.start_heartbeat(args.heartbeat)

    # 启动服务
    server = ThreadedServer(("0.0.0.0", args.port), GatewayHandler)
    print("\n" + "=" * 60)
    print("  📱 手机公网网关 · 已启动")
    print("=" * 60)
    print(f"  本地: http://127.0.0.1:{args.port}")
    print(f"  LAN:  http://192.168.31.141:{args.port}")
    print(f"  公网: https://aiotvr.xyz/phone/ (需配置FRP+Nginx)")
    print(f"\n  手机: {connector.active_name} → {connector.active_base}")
    print(f"  认证: {'关闭' if not GATEWAY_TOKEN else f'Token={GATEWAY_TOKEN[:8]}...'}")
    print(f"  心跳: {'关闭' if args.heartbeat <= 0 else f'每{args.heartbeat}秒'}")
    print(f"\n  使用:")
    print(f"     curl -H 'X-Gateway-Token: {GATEWAY_TOKEN}' http://127.0.0.1:{args.port}/status")
    print(f"     curl http://127.0.0.1:{args.port}/gw/health")
    print("=" * 60)

    try:
        while True:
            try:
                server.serve_forever()
                break  # clean shutdown
            except KeyboardInterrupt:
                break
            except Exception as e:
                log.error(f"💥 serve_forever异常，3s后重启: {e}")
                try:
                    server.server_close()
                except Exception:
                    pass
                time.sleep(3)
                server = ThreadedServer(("0.0.0.0", args.port), GatewayHandler)
                log.info("🔄 服务已重启")
    except KeyboardInterrupt:
        pass
    finally:
        connector.stop()
        print("\n  👋 网关已停止")


if __name__ == "__main__":
    main()
