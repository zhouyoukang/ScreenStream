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
PHONE_SS_PORT = 8084
PHONE_GW_PORT = 8080
PHONE_SERIAL = "158377ff"

# 路径探测顺序 (水到渠成)
PATHS = [
    {"name": "USB转发",    "base": f"http://127.0.0.1:{PHONE_SS_PORT}"},
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
        """自动恢复 — ADB forward + 重新发现"""
        log.info("🔄 开始自动恢复...")
        self.stats["recoveries"] += 1
        self.ensure_adb_forward()
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
# 主入口
# ============================================================

def _kill_port(port: int):
    """清理占用指定端口的进程，确保幂等启动"""
    import subprocess, signal
    try:
        if os.name == "nt":
            out = subprocess.check_output(
                f"netstat -ano | findstr \"LISTENING\" | findstr \":{port} \"",
                shell=True, text=True, stderr=subprocess.DEVNULL
            )
            pids = set()
            for line in out.strip().splitlines():
                parts = line.split()
                if parts:
                    pids.add(parts[-1])
            for pid in pids:
                try:
                    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                    log.info(f"🔪 终止占用 :{port} 的进程 PID={pid}")
                except Exception:
                    pass
        else:
            out = subprocess.check_output(
                ["lsof", "-ti", f"tcp:{port}"], text=True, stderr=subprocess.DEVNULL
            )
            for pid in out.strip().splitlines():
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    log.info(f"🔪 终止占用 :{port} 的进程 PID={pid}")
                except Exception:
                    pass
        if pids if os.name == "nt" else out.strip():
            time.sleep(1)
    except Exception:
        pass


def main():
    global GATEWAY_TOKEN

    import argparse
    parser = argparse.ArgumentParser(description="手机公网网关")
    parser.add_argument("--port", type=int, default=PORT, help=f"网关端口 (默认{PORT})")
    parser.add_argument("--token", default=None, help="认证Token")
    parser.add_argument("--heartbeat", type=int, default=30, help="心跳间隔秒 (0=关闭)")
    parser.add_argument("--no-auth", action="store_true", help="关闭认证")
    args = parser.parse_args()

    if args.token:
        GATEWAY_TOKEN = args.token
    elif os.environ.get("PHONE_GATEWAY_TOKEN"):
        GATEWAY_TOKEN = os.environ["PHONE_GATEWAY_TOKEN"]

    if args.no_auth:
        GATEWAY_TOKEN = ""

    _kill_port(args.port)
    connector.discover()

    if args.heartbeat > 0:
        connector.start_heartbeat(args.heartbeat)

    server = ThreadedServer(("0.0.0.0", args.port), GatewayHandler)
    log.info(f"📱 网关启动 :{args.port} | 手机: {connector.active_name} → {connector.active_base}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        connector.stop()
        log.info("网关已停止")


if __name__ == "__main__":
    main()
