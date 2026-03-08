#!/usr/bin/env python3
"""
三电脑服务器 · 全景资源注册表
道生一(注册表) → 一生二(探测+API) → 二生三(三机协同) → 三生万物(全服务覆盖)

端口: 9000
启动: python resource_registry.py [--probe] [--port 9000]
"""

import json, os, sys, time, socket, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ══════════════════════════════════════════════════════════════
# 伏羲八卦 · 全景资源注册表
# ══════════════════════════════════════════════════════════════

REGISTRY = {
    # ──────────────── ☰乾 · 创造/算力 ────────────────
    "☰乾": {
        "desc": "天行健·创造与算力",
        "services": [
            {"name": "Ollama LLM",        "host": "127.0.0.1", "port": 11434, "path": "/api/tags",        "proto": "http", "loc": "台式机141", "cat": "AI"},
            {"name": "OpenWebUI",          "host": "127.0.0.1", "port": 18880, "path": "/",                "proto": "http", "loc": "台式机141", "cat": "AI"},
            {"name": "MaxKB",              "host": "127.0.0.1", "port": 18881, "path": "/",                "proto": "http", "loc": "台式机141", "cat": "AI"},
            {"name": "AGI Dashboard",      "host": "127.0.0.1", "port": 9090,  "path": "/",                "proto": "http", "loc": "台式机141", "cat": "AI"},
            {"name": "3D建模Agent",        "host": "127.0.0.1", "port": 0,     "path": "",                 "proto": "cli",  "loc": "台式机141", "cat": "3D",  "cmd": "python forge.py"},
        ],
    },
    # ──────────────── ☷坤 · 承载/基础设施 ────────────────
    "☷坤": {
        "desc": "地势坤·基础设施承载",
        "services": [
            {"name": "HomeAssistant",      "host": "127.0.0.1", "port": 8123,  "path": "/api/",            "proto": "http", "loc": "台式机141", "cat": "IoT"},
            {"name": "MQTT Mosquitto",     "host": "127.0.0.1", "port": 1883,  "path": "",                 "proto": "tcp",  "loc": "台式机141", "cat": "IoT"},
            {"name": "NodeRED",            "host": "127.0.0.1", "port": 1880,  "path": "/",                "proto": "http", "loc": "台式机141", "cat": "IoT"},
            {"name": "Grafana",            "host": "127.0.0.1", "port": 3000,  "path": "/api/health",      "proto": "http", "loc": "台式机141", "cat": "监控"},
            {"name": "PostgreSQL",         "host": "127.0.0.1", "port": 5432,  "path": "",                 "proto": "tcp",  "loc": "台式机141", "cat": "数据库"},
            {"name": "Redis",              "host": "127.0.0.1", "port": 6379,  "path": "",                 "proto": "tcp",  "loc": "台式机141", "cat": "数据库"},
            {"name": "Docker API",         "host": "127.0.0.1", "port": 2375,  "path": "",                 "proto": "tcp",  "loc": "台式机141", "cat": "容器"},
        ],
    },
    # ──────────────── ☲离 · 可视/投屏 ────────────────
    "☲离": {
        "desc": "离为火·照万物可见",
        "services": [
            {"name": "电脑投屏(desktop)",   "host": "127.0.0.1", "port": 9802,  "path": "/health",          "proto": "http", "loc": "台式机141", "cat": "投屏"},
            {"name": "ScreenStream投屏",    "host": "127.0.0.1", "port": 18080, "path": "/",                "proto": "http", "loc": "台式机141", "cat": "投屏", "note": "需手机"},
            {"name": "ScreenStream控制",    "host": "127.0.0.1", "port": 18084, "path": "/status",          "proto": "http", "loc": "台式机141", "cat": "投屏", "note": "需手机"},
            {"name": "P2P信令服务器",       "host": "127.0.0.1", "port": 9100,  "path": "/api/status",      "proto": "http", "loc": "台式机141", "cat": "投屏"},
            {"name": "WebSocket中继",       "host": "127.0.0.1", "port": 9800,  "path": "/api/status",      "proto": "http", "loc": "台式机141", "cat": "投屏"},
            {"name": "Sunshine远程",        "host": "127.0.0.1", "port": 47989, "path": "",                 "proto": "tcp",  "loc": "台式机141", "cat": "远程"},
        ],
    },
    # ──────────────── ☳震 · 控制/操控 ────────────────
    "☳震": {
        "desc": "震为雷·一触即发",
        "services": [
            {"name": "远程Agent",           "host": "127.0.0.1", "port": 9903,  "path": "/api/status",      "proto": "http", "loc": "台式机141", "cat": "远程"},
            {"name": "远程修复中枢",         "host": "127.0.0.1", "port": 3002,  "path": "/",                "proto": "http", "loc": "台式机141", "cat": "远程"},
            {"name": "万物中枢",             "host": "127.0.0.1", "port": 8808,  "path": "/api/status",      "proto": "http", "loc": "台式机141", "cat": "中枢"},
            {"name": "手机脑PhoneBrain",    "host": "127.0.0.1", "port": 8765,  "path": "/",                "proto": "http", "loc": "手机Termux","cat": "手机"},
            {"name": "RayNeo管理中枢",      "host": "127.0.0.1", "port": 8800,  "path": "/",                "proto": "http", "loc": "台式机141", "cat": "AR"},
            {"name": "RayNeo仿真器",        "host": "127.0.0.1", "port": 8768,  "path": "/",                "proto": "http", "loc": "台式机141", "cat": "AR"},
        ],
    },
    # ──────────────── ☴巽 · 网络/代理 ────────────────
    "☴巽": {
        "desc": "巽为风·无孔不入",
        "services": [
            {"name": "Clash代理",           "host": "127.0.0.1", "port": 7890,  "path": "",                 "proto": "tcp",  "loc": "台式机141", "cat": "代理"},
            {"name": "Clash API",           "host": "127.0.0.1", "port": 9097,  "path": "/configs",         "proto": "http", "loc": "台式机141", "cat": "代理"},
            {"name": "CFW授权代理",          "host": "127.0.0.1", "port": 443,   "path": "",                 "proto": "tcp",  "loc": "台式机141", "cat": "代理"},
            {"name": "CFW Relay",           "host": "0.0.0.0",   "port": 18443, "path": "",                 "proto": "tcp",  "loc": "台式机141", "cat": "代理"},
            {"name": "FRP控制台",            "host": "127.0.0.1", "port": 7500,  "path": "",                 "proto": "http", "loc": "台式机141", "cat": "隧道"},
            {"name": "公网CFW Hub",          "host": "aiotvr.xyz","port": 443,   "path": "/hub/api/health",  "proto": "https","loc": "阿里云",    "cat": "公网"},
            {"name": "公网Health",           "host": "aiotvr.xyz","port": 443,   "path": "/api/health",      "proto": "https","loc": "阿里云",    "cat": "公网"},
        ],
    },
    # ──────────────── ☵坎 · 数据/凭据 ────────────────
    "☵坎": {
        "desc": "坎为水·上善若水",
        "services": [
            {"name": "密码中枢",             "host": "127.0.0.1", "port": 9877,  "path": "/api/health",      "proto": "http", "loc": "台式机141", "cat": "凭据"},
            {"name": "手机数据中枢",          "host": "127.0.0.1", "port": 9878,  "path": "/api/status",      "proto": "http", "loc": "台式机141", "cat": "凭据"},
            {"name": "二手书API",            "host": "127.0.0.1", "port": 8088,  "path": "/api/health",      "proto": "http", "loc": "台式机141", "cat": "业务"},
            {"name": "端口服务管理",          "host": "127.0.0.1", "port": 9999,  "path": "/",                "proto": "http", "loc": "台式机141", "cat": "管理"},
        ],
    },
    # ──────────────── ☶艮 · 设备/硬件 ────────────────
    "☶艮": {
        "desc": "艮为山·稳固不移",
        "services": [
            {"name": "拓竹3D打印",           "host": "127.0.0.1", "port": 8870,  "path": "/api/health",      "proto": "http", "loc": "台式机141", "cat": "硬件", "device": "Bambu A1"},
            {"name": "EcoFlow电源",          "host": "127.0.0.1", "port": 8871,  "path": "/api/status",      "proto": "http", "loc": "台式机141", "cat": "硬件", "device": "Delta 2"},
            {"name": "Insta360相机",         "host": "127.0.0.1", "port": 8860,  "path": "/api/status",      "proto": "http", "loc": "台式机141", "cat": "硬件", "device": "X3"},
            {"name": "ORS6设备",             "host": "127.0.0.1", "port": 41927, "path": "/api/health",      "proto": "http", "loc": "台式机141", "cat": "硬件", "device": "ORS6-ESP32"},
            {"name": "Go1机器狗",            "host": "127.0.0.1", "port": 8087,  "path": "/status",          "proto": "http", "loc": "台式机141", "cat": "硬件", "device": "Unitree Go1"},
        ],
    },
    # ──────────────── ☱兑 · 感知/智能家居 ────────────────
    "☱兑": {
        "desc": "兑为泽·万物交通",
        "services": [
            {"name": "米家中枢",             "host": "127.0.0.1", "port": 8873,  "path": "/api/health",      "proto": "http", "loc": "台式机141", "cat": "智能家居"},
            {"name": "米家摄像头",            "host": "127.0.0.1", "port": 8874,  "path": "/api/health",      "proto": "http", "loc": "台式机141", "cat": "智能家居"},
            {"name": "智能家居网关",          "host": "127.0.0.1", "port": 8900,  "path": "/api/health",      "proto": "http", "loc": "台式机141", "cat": "智能家居"},
            {"name": "小米路由器",            "host": "192.168.31.1", "port": 80, "path": "/",                "proto": "http", "loc": "LAN",       "cat": "网络"},
        ],
    },
}

# ══════════════════════════════════════════════════════════════
# 设备矩阵
# ══════════════════════════════════════════════════════════════

DEVICES = [
    {"name": "OnePlus NE2210",    "ip": "192.168.31.40",  "type": "手机",   "interface": "SS API :8084",    "adb": "158377ff"},
    {"name": "Samsung S23U",      "ip": "192.168.31.123", "type": "手机",   "interface": "ADB WiFi TLS",    "adb": "R5CW2221VGL"},
    {"name": "OPPO Reno4 SE",     "ip": "192.168.31.95",  "type": "手机",   "interface": "SS API :8084",    "adb": "WK555X5DF65PPR4L"},
    {"name": "Quest 3",           "ip": "192.168.31.136", "type": "VR",     "interface": "ADB",             "adb": "2G0YC5ZG8L08Z7"},
    {"name": "RayNeo V3",         "ip": "192.168.31.116", "type": "AR",     "interface": "WiFi ADB :5555",  "adb": "841571AC688C360"},
    {"name": "VP99手表",           "ip": "192.168.31.41",  "type": "手表",   "interface": "VNC :5900",       "adb": ""},
    {"name": "Go1机器狗",          "ip": "192.168.12.1",   "type": "机器人", "interface": "SSH/MQTT",        "adb": ""},
    {"name": "Bambu A1",          "ip": "192.168.31.134", "type": "3D打印", "interface": "MQTTS :8883",     "adb": ""},
    {"name": "EcoFlow Delta 2",   "ip": "192.168.31.134", "type": "电源",   "interface": "TCP :3000",       "adb": ""},
    {"name": "小米路由器AX3000T",  "ip": "192.168.31.1",   "type": "路由器", "interface": "HTTP :80",        "adb": ""},
    {"name": "米家中枢网关",       "ip": "192.168.31.53",  "type": "网关",   "interface": "WS/MQTT",         "adb": ""},
]

# ══════════════════════════════════════════════════════════════
# Dashboard 索引
# ══════════════════════════════════════════════════════════════

DASHBOARDS = [
    {"name": "拓竹3D打印",     "port": 8870,  "path": "/", "file": "拓竹AI 3D打印机/bambu_dashboard.html"},
    {"name": "EcoFlow电源",    "port": 8871,  "path": "/", "file": "正浩德2户外电源/ecoflow_dashboard.html"},
    {"name": "Insta360相机",   "port": 8860,  "path": "/", "file": "影石360 x3/insta360_dashboard.html"},
    {"name": "DJI Neo无人机",  "port": 0,     "path": "/", "file": "大疆所有体系整合/neo_dashboard.html"},
    {"name": "ORS6设备",       "port": 41927, "path": "/", "file": "ORS6-VAM饮料摇匀器/ors6_hub.py"},
    {"name": "Go1机器狗",      "port": 8087,  "path": "/", "file": "机器狗开发/dashboard.html"},
    {"name": "Go1仿真",        "port": 46173, "path": "/", "file": "虚拟仿真平台/go1/go1_web_sim.html"},
    {"name": "米家全景",       "port": 8873,  "path": "/", "file": "米家系统全整合/mijia_dashboard.html"},
    {"name": "米家摄像头",     "port": 8874,  "path": "/", "file": "米家系统全整合/camera_dashboard.html"},
    {"name": "小米路由器",     "port": 0,     "path": "/", "file": "米家系统全整合/router_dashboard.html"},
    {"name": "RayNeo AR",      "port": 8800,  "path": "/", "file": "雷鸟v3开发/rayneo_dashboard.html"},
    {"name": "万物中枢",       "port": 8808,  "path": "/", "file": "雷鸟v3开发/wan_wu_server.py"},
    {"name": "Quest 3 VR",     "port": 47387, "path": "/", "file": "quest3开发/quest3_v3_dashboard.html"},
    {"name": "AGI仪表盘",      "port": 9090,  "path": "/", "file": "AGI/dashboard-server.py"},
    {"name": "手机逆向",       "port": 8096,  "path": "/coloros_dashboard.html", "file": "手机现成app库/coloros_dashboard.html"},
    {"name": "PC软件全景",     "port": 8098,  "path": "/_ultimate_dashboard.html","file": "电脑现成项目app/_ultimate_dashboard.html"},
    {"name": "虚拟仿真门户",   "port": 48000, "path": "/portal.html",            "file": "虚拟仿真平台/portal.html"},
    {"name": "远程桌面",       "port": 9903,  "path": "/", "file": "远程桌面/remote_agent.py"},
    {"name": "二手书手机端",   "port": 8099,  "path": "/", "file": "二手书手机端/index.html"},
    {"name": "智能家居",       "port": 0,     "path": "/", "file": "100-智能家居_SmartHome/网关服务/dashboard.html"},
]

# ══════════════════════════════════════════════════════════════
# 三机矩阵
# ══════════════════════════════════════════════════════════════

MACHINES = {
    "台式机141": {"ip": "192.168.31.141", "role": "算力引擎", "gua": "☷坤", "hours": "8-23", "os": "Win11", "cpu": "R7-9700X", "ram": "62GB", "gpu": "RTX 4070S"},
    "笔记本179": {"ip": "192.168.31.179", "role": "24h代理",  "gua": "☲离", "hours": "24h",  "os": "Win11", "cpu": "R7-7840HS","ram": "15GB", "gpu": "780M"},
    "阿里云":    {"ip": "60.205.171.100", "role": "公网门户",  "gua": "☰乾", "hours": "永驻", "os": "Ubuntu","cpu": "2C Xeon",  "ram": "1.6GB","gpu": "无"},
}

# ══════════════════════════════════════════════════════════════
# 探测引擎
# ══════════════════════════════════════════════════════════════

def probe_tcp(host, port, timeout=2):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def probe_http(host, port, path="/", proto="http", timeout=3):
    try:
        url = f"{proto}://{host}:{port}{path}"
        req = Request(url, headers={"User-Agent": "DaoProbe/1.0"})
        resp = urlopen(req, timeout=timeout)
        return resp.status < 500
    except Exception:
        return False

def probe_service(svc):
    start = time.time()
    if svc.get("proto") == "cli" or svc.get("port", 0) == 0:
        return {**svc, "online": None, "ms": 0, "note": svc.get("note", "非网络服务")}
    if svc["proto"] == "tcp":
        ok = probe_tcp(svc["host"], svc["port"])
    elif svc["proto"] in ("http", "https"):
        ok = probe_http(svc["host"], svc["port"], svc.get("path", "/"), svc["proto"])
    else:
        ok = False
    ms = round((time.time() - start) * 1000)
    return {**svc, "online": ok, "ms": ms}

def probe_device(dev):
    ok = probe_tcp(dev["ip"], 5555, timeout=1) or probe_tcp(dev["ip"], 80, timeout=1)
    return {**dev, "online": ok}

def probe_all():
    results = {"timestamp": datetime.now().isoformat(), "services": {}, "devices": [], "machines": {}}
    with ThreadPoolExecutor(max_workers=20) as pool:
        # Probe services
        futures = {}
        for gua, section in REGISTRY.items():
            for svc in section["services"]:
                f = pool.submit(probe_service, svc)
                futures[f] = (gua, svc["name"])
        for f in as_completed(futures):
            gua, name = futures[f]
            r = f.result()
            results["services"].setdefault(gua, []).append(r)
        # Probe devices
        dev_futures = {pool.submit(probe_device, d): d["name"] for d in DEVICES}
        for f in as_completed(dev_futures):
            results["devices"].append(f.result())
        # Probe machines
        for name, m in MACHINES.items():
            ok = probe_tcp(m["ip"], 3389, timeout=2) if m["ip"] != "60.205.171.100" else probe_tcp(m["ip"], 22, timeout=3)
            results["machines"][name] = {**m, "online": ok}
    # Stats
    total = online = offline = 0
    for gua, svcs in results["services"].items():
        for s in svcs:
            if s.get("online") is not None:
                total += 1
                if s["online"]: online += 1
                else: offline += 1
    results["stats"] = {"total": total, "online": online, "offline": offline,
                        "devices_total": len(DEVICES), "devices_online": sum(1 for d in results["devices"] if d.get("online")),
                        "dashboards": len(DASHBOARDS)}
    return results

# ══════════════════════════════════════════════════════════════
# HTTP API 服务器
# ══════════════════════════════════════════════════════════════

_last_probe = {"data": None, "time": 0}
_portal_dir = Path(__file__).parent

class RegistryHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, path):
        try:
            content = path.read_bytes()
            self.send_response(200)
            ct = "text/html; charset=utf-8"
            if str(path).endswith(".js"): ct = "application/javascript"
            elif str(path).endswith(".css"): ct = "text/css"
            elif str(path).endswith(".json"): ct = "application/json"
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", len(content))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/" or p == "/portal" or p == "/portal.html":
            self._html(_portal_dir / "portal.html")
        elif p == "/api/registry":
            self._json({"registry": {g: {"desc": s["desc"], "services": s["services"]} for g, s in REGISTRY.items()},
                         "devices": DEVICES, "dashboards": DASHBOARDS, "machines": MACHINES})
        elif p == "/api/probe":
            now = time.time()
            if _last_probe["data"] is None or now - _last_probe["time"] > 30:
                _last_probe["data"] = probe_all()
                _last_probe["time"] = now
            self._json(_last_probe["data"])
        elif p == "/api/health":
            self._json({"status": "ok", "server": "resource_registry", "port": PORT,
                         "timestamp": datetime.now().isoformat(),
                         "services_registered": sum(len(s["services"]) for s in REGISTRY.values()),
                         "devices_registered": len(DEVICES), "dashboards_registered": len(DASHBOARDS)})
        elif p == "/api/machines":
            self._json(MACHINES)
        elif p == "/api/devices":
            self._json(DEVICES)
        elif p == "/api/dashboards":
            self._json(DASHBOARDS)
        else:
            # Try serving static files from portal dir
            fp = _portal_dir / p.lstrip("/")
            if fp.is_file() and fp.resolve().is_relative_to(_portal_dir.resolve()):
                self._html(fp)
            else:
                self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

PORT = 9000

def cli_probe():
    print("三电脑服务器 · 全景探测")
    print("=" * 60)
    results = probe_all()
    for gua in ["☰乾", "☷坤", "☲离", "☳震", "☴巽", "☵坎", "☶艮", "☱兑"]:
        svcs = results["services"].get(gua, [])
        if not svcs: continue
        desc = REGISTRY[gua]["desc"]
        print(f"\n{gua} {desc}")
        for s in svcs:
            if s.get("online") is None:
                icon = "⚪"
            elif s["online"]:
                icon = "🟢"
            else:
                icon = "🔴"
            print(f"  {icon} {s['name']:20s} :{s.get('port','—'):>5}  {s['ms']:>4}ms  [{s['loc']}]")
    print(f"\n{'='*60}")
    st = results["stats"]
    print(f"服务: {st['online']}/{st['total']} 在线 | 设备: {st['devices_online']}/{st['devices_total']} 在线 | Dashboard: {st['dashboards']}个")
    print(f"\n三机状态:")
    for name, m in results["machines"].items():
        icon = "🟢" if m["online"] else "🔴"
        print(f"  {icon} {name:12s} {m['ip']:18s} {m['role']}")

def main():
    global PORT
    args = sys.argv[1:]
    if "--port" in args:
        PORT = int(args[args.index("--port") + 1])
    if "--probe" in args:
        cli_probe()
        return
    print(f"三电脑服务器 · 资源注册表")
    print(f"  Portal:   http://localhost:{PORT}/")
    print(f"  Registry: http://localhost:{PORT}/api/registry")
    print(f"  Probe:    http://localhost:{PORT}/api/probe")
    print(f"  Health:   http://localhost:{PORT}/api/health")
    srv = HTTPServer(("0.0.0.0", PORT), RegistryHandler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n止。")

if __name__ == "__main__":
    main()
