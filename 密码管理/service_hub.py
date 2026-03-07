"""
端口服务管理中枢 (Port/Service Management Hub)
==============================================
道生一(扫描)，一生二(注册+监控)，二生三(冲突检测+隔离)，三生万物(多Agent并行安全)

功能:
- 全景端口/服务/进程扫描
- 端口注册表 + 冲突检测
- 服务健康监控 (HTTP/TCP)
- 多Agent隔离 (Zone分区)
- 僵尸终端检测与清理
- Web Dashboard (五感可视化)

端口: 9999 (HTTP API + Dashboard)
"""

import ctypes
import ctypes.wintypes
import http.server
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# ═══════════════════════════════════════════════════════
# 端口注册表 — 所有已知端口的权威声明
# ═══════════════════════════════════════════════════════

PORT_REGISTRY = {
    # === Zone A: ScreenStream核心 ===
    8080: {"name": "SS Gateway / Docker", "zone": "A", "project": "ScreenStream", "protocol": "HTTP"},
    8081: {"name": "SS MJPEG / Docker", "zone": "A", "project": "ScreenStream", "protocol": "HTTP"},
    8082: {"name": "SS RTSP (reserved)", "zone": "A", "project": "ScreenStream", "protocol": "RTSP"},
    8083: {"name": "SS WebRTC (reserved)", "zone": "A", "project": "ScreenStream", "protocol": "HTTP"},
    8084: {"name": "SS Input / ADB fwd", "zone": "A", "project": "ScreenStream", "protocol": "HTTP"},
    18080: {"name": "SS Gateway (LDPlayer VM3)", "zone": "A", "project": "ScreenStream", "protocol": "ADB fwd"},
    18084: {"name": "SS Input (LDPlayer VM3)", "zone": "A", "project": "ScreenStream", "protocol": "ADB fwd"},

    # === Zone B: Python卫星服务 ===
    8085: {"name": "Go1 Brain API", "zone": "B", "project": "机器狗开发", "protocol": "HTTP"},
    8086: {"name": "ORS6 Hub", "zone": "B", "project": "ORS6-VAM", "protocol": "HTTP"},
    8088: {"name": "二手书 ModularSystem", "zone": "B", "project": "二手书", "protocol": "HTTP"},
    8089: {"name": "二手书 备用/测试", "zone": "B", "project": "二手书", "protocol": "HTTP"},
    8099: {"name": "二手书手机端 dev server", "zone": "B", "project": "二手书手机端", "protocol": "HTTP"},
    8765: {"name": "RayNeo PhoneBrain", "zone": "B", "project": "雷鸟v3开发", "protocol": "WS"},
    8767: {"name": "RayNeo SimWS", "zone": "B", "project": "雷鸟v3开发", "protocol": "WS"},
    8768: {"name": "RayNeo SimHTTP", "zone": "B", "project": "雷鸟v3开发", "protocol": "HTTP"},
    8800: {"name": "RayNeo Dashboard HTTP", "zone": "B", "project": "雷鸟v3开发", "protocol": "HTTP"},
    8801: {"name": "RayNeo Dashboard WS", "zone": "B", "project": "雷鸟v3开发", "protocol": "WS"},

    # === Zone C: 远程/投屏 ===
    8444: {"name": "XR Proxy (Quest 3)", "zone": "C", "project": "quest3开发", "protocol": "HTTP"},
    9100: {"name": "ScreenStreamWeb信令", "zone": "C", "project": "公网投屏", "protocol": "WS"},
    9101: {"name": "亲情远程信令", "zone": "C", "project": "亲情远程", "protocol": "WS"},
    9800: {"name": "CloudRelay", "zone": "C", "project": "公网投屏", "protocol": "WS"},
    9803: {"name": "P2P Desktop Cast", "zone": "C", "project": "电脑公网投屏手机", "protocol": "WS"},

    # === Zone D: 基础设施 ===
    443: {"name": "CFW Proxy (Windsurf)", "zone": "D", "project": "Windsurf无限额度", "protocol": "HTTPS"},
    5037: {"name": "ADB Server", "zone": "D", "project": "系统", "protocol": "TCP"},
    7890: {"name": "Clash Meta", "zone": "D", "project": "clash-agent", "protocol": "SOCKS/HTTP"},
    7897: {"name": "Clash Mixed (备用)", "zone": "D", "project": "clash-agent", "protocol": "SOCKS/HTTP"},
    9090: {"name": "AGI Dashboard", "zone": "D", "project": "AGI", "protocol": "HTTP"},
    9098: {"name": "VPN Manager", "zone": "D", "project": "手机软路由", "protocol": "HTTP"},

    # === Zone E: 管理中枢 ===
    9999: {"name": "端口服务管理中枢", "zone": "E", "project": "密码管理", "protocol": "HTTP"},

    # === Zone F: 外部/系统服务 ===
    1337: {"name": "Razer SDK Server", "zone": "F", "project": "系统", "protocol": "TCP"},
    1880: {"name": "Docker (Node-RED?)", "zone": "F", "project": "Docker", "protocol": "HTTP"},
    1883: {"name": "Docker MQTT", "zone": "F", "project": "Docker", "protocol": "MQTT"},
    3000: {"name": "Docker (Grafana?)", "zone": "F", "project": "Docker", "protocol": "HTTP"},
    3389: {"name": "RDP", "zone": "F", "project": "系统", "protocol": "RDP"},
    5432: {"name": "Docker PostgreSQL", "zone": "F", "project": "Docker", "protocol": "TCP"},
    6379: {"name": "Docker Redis", "zone": "F", "project": "Docker", "protocol": "TCP"},
    6742: {"name": "OpenRGB", "zone": "F", "project": "系统", "protocol": "TCP"},
    7250: {"name": "SpacedeskCast", "zone": "F", "project": "SpaceDesk", "protocol": "TCP"},
    7401: {"name": "FRP Client", "zone": "F", "project": "系统", "protocol": "TCP"},
    8123: {"name": "Docker HA", "zone": "F", "project": "智能家居", "protocol": "HTTP"},
    8888: {"name": "Docker (Jupyter?)", "zone": "F", "project": "Docker", "protocol": "HTTP"},
    11434: {"name": "Ollama LLM", "zone": "F", "project": "系统", "protocol": "HTTP"},
}

ZONE_NAMES = {
    "A": "ScreenStream核心",
    "B": "Python卫星服务",
    "C": "远程/投屏",
    "D": "基础设施",
    "E": "管理中枢",
    "F": "外部/系统服务",
}

ZONE_COLORS = {
    "A": "#ef4444", "B": "#f59e0b", "C": "#10b981",
    "D": "#3b82f6", "E": "#8b5cf6", "F": "#6b7280",
}

# ═══════════════════════════════════════════════════════
# 系统扫描引擎
# ═══════════════════════════════════════════════════════

def _cmd_run(args, timeout=8):
    """运行CMD命令，返回stdout。零PowerShell，纯CMD极速。处理GBK/UTF-8编码。"""
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout,
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        # Windows CMD输出通常是GBK(CP936)编码
        try:
            return r.stdout.decode('gbk', errors='replace')
        except Exception:
            return r.stdout.decode('utf-8', errors='replace')
    except Exception:
        return ""


def _build_pid_name_map():
    """用tasklist构建PID→进程名映射 (~100ms)"""
    pid_map = {}
    out = _cmd_run(["tasklist", "/FO", "CSV", "/NH"])
    for line in out.splitlines():
        parts = line.strip().split('","')
        if len(parts) >= 2:
            name = parts[0].strip('"').replace('.exe', '')
            try:
                pid = int(parts[1].strip('"'))
                pid_map[pid] = name
            except ValueError:
                pass
    return pid_map


def scan_listening_ports():
    """扫描所有LISTENING端口 — 纯CMD，零PowerShell (<500ms)"""
    result = {}
    try:
        out = _cmd_run(["netstat", "-ano"])
        port_pid = {}
        for line in out.splitlines():
            m = re.search(r':(\d+)\s+[\d\.]+:0\s+LISTENING\s+(\d+)', line)
            if m:
                port, pid = int(m.group(1)), int(m.group(2))
                if 1024 < port < 65535:
                    port_pid[port] = pid

        pid_map = _build_pid_name_map()
        for port, pid in sorted(port_pid.items()):
            result[port] = {
                "pid": pid,
                "process": pid_map.get(pid, "unknown"),
                "cmdline": "N/A"  # cmdline需要WMI，首次不加载
            }
    except Exception as e:
        result[-1] = {"error": str(e)}
    return result


def scan_windsurf_terminals():
    """扫描Windsurf pwsh终端 — 用tasklist统计 (<200ms)"""
    terminals = []
    try:
        out = _cmd_run(["tasklist", "/FI", "IMAGENAME eq pwsh.exe", "/FO", "CSV", "/NH"])
        for line in out.splitlines():
            parts = line.strip().split('","')
            if len(parts) >= 5 and 'pwsh' in parts[0].lower():
                try:
                    pid = int(parts[1].strip('"'))
                    mem_str = parts[4].strip('"').replace(',', '').replace(' K', '').replace('\xa0', '')
                    mem_kb = int(re.sub(r'[^\d]', '', mem_str)) if mem_str else 0
                    terminals.append({
                        "pid": pid,
                        "mem_mb": mem_kb // 1024,
                        "children": 0,  # 轻量扫描不查子进程
                        "cpu_sec": 0,
                        "status": "active"  # 简化：活着就是active
                    })
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass
    return terminals


def scan_conhost():
    """扫描conhost数量 — 用tasklist (<100ms)"""
    try:
        out = _cmd_run(["tasklist", "/FI", "IMAGENAME eq conhost.exe", "/FO", "CSV", "/NH"])
        total = sum(1 for line in out.splitlines() if 'conhost' in line.lower())
        return {"total": total, "headless": 0, "regular": total}
    except Exception:
        return {"total": 0, "headless": 0, "regular": 0}


def scan_system_resources():
    """扫描系统资源 — 用Python ctypes Windows API (零subprocess, <10ms)"""
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.wintypes.DWORD),
                ("dwMemoryLoad", ctypes.wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]
        mem = MEMORYSTATUSEX()
        mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))

        total_gb = round(mem.ullTotalPhys / (1024**3), 1)
        free_gb = round(mem.ullAvailPhys / (1024**3), 1)
        used_pct = round((mem.ullTotalPhys - mem.ullAvailPhys) / mem.ullTotalPhys * 100, 1)

        return {
            "ram_total_gb": total_gb,
            "ram_free_gb": free_gb,
            "ram_used_pct": used_pct,
            "cpu_pct": mem.dwMemoryLoad  # Windows memory load percentage
        }
    except Exception:
        return {"ram_total_gb": 0, "ram_free_gb": 0, "ram_used_pct": 0, "cpu_pct": 0}


def check_port_health(port, protocol="HTTP", timeout=2):
    """检查端口健康状态"""
    if protocol in ("HTTP", "HTTPS"):
        try:
            scheme = "https" if protocol == "HTTPS" else "http"
            req = urllib.request.Request(f"{scheme}://127.0.0.1:{port}/", method="GET")
            resp = urllib.request.urlopen(req, timeout=timeout)
            return {"status": "up", "code": resp.status}
        except urllib.error.URLError as e:
            if hasattr(e, 'code'):
                return {"status": "up", "code": e.code}
            return {"status": "down", "error": str(e.reason)[:50]}
        except Exception as e:
            return {"status": "down", "error": str(e)[:50]}
    else:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(("127.0.0.1", port))
            s.close()
            return {"status": "up", "code": "TCP OK"}
        except Exception:
            return {"status": "down", "error": "TCP refused"}


def detect_conflicts(live_ports):
    """检测端口冲突"""
    conflicts = []
    for port, info in live_ports.items():
        if port in PORT_REGISTRY:
            reg = PORT_REGISTRY[port]
            actual_proc = info.get("process", "unknown")
            expected_proj = reg["project"]
            if actual_proc == "unknown" or actual_proc == "dead":
                conflicts.append({
                    "port": port, "type": "zombie",
                    "message": f"Port {port} ({reg['name']}) has dead process",
                    "severity": "warning"
                })
        else:
            conflicts.append({
                "port": port, "type": "unregistered",
                "message": f"Port {port} not in registry (process: {info.get('process', '?')})",
                "severity": "info"
            })

    # Check for registered ports not running
    for port, reg in PORT_REGISTRY.items():
        if port not in live_ports and reg["zone"] not in ("F",) and port != 9999:
            pass  # Not all registered ports need to be running

    return conflicts


def kill_stale_terminals():
    """清理僵尸终端 — 返回说明信息，不自动杀进程(安全)"""
    terminals = scan_windsurf_terminals()
    idle = [t for t in terminals if t.get("mem_mb", 0) < 50]  # <50MB likely idle
    return {
        "total": len(terminals),
        "idle_candidates": len(idle),
        "pids": [t["pid"] for t in idle],
        "message": f"Found {len(idle)} idle terminals. Use taskkill /F /PID <pid> to kill."
    }


# ═══════════════════════════════════════════════════════
# 状态缓存 (避免频繁扫描)
# ═══════════════════════════════════════════════════════

class StateCache:
    def __init__(self, ttl=10):
        self.ttl = ttl
        self._cache = {}
        self._lock = threading.Lock()

    def get(self, key, scanner_fn):
        with self._lock:
            now = time.time()
            if key in self._cache and now - self._cache[key]["ts"] < self.ttl:
                return self._cache[key]["data"]
        data = scanner_fn()
        with self._lock:
            self._cache[key] = {"data": data, "ts": time.time()}
        return data

    def invalidate(self, key=None):
        with self._lock:
            if key:
                self._cache.pop(key, None)
            else:
                self._cache.clear()


cache = StateCache(ttl=15)

# ═══════════════════════════════════════════════════════
# 事件日志
# ═══════════════════════════════════════════════════════

event_log = []
MAX_EVENTS = 200


def add_event(level, message, data=None):
    event = {
        "ts": datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "message": message,
        "data": data
    }
    event_log.append(event)
    if len(event_log) > MAX_EVENTS:
        event_log.pop(0)
    return event


# ═══════════════════════════════════════════════════════
# HTTP Server + API
# ═══════════════════════════════════════════════════════

class HubHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Suppress default logging

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache")

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def _html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self._cors()
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        query = parse_qs(urlparse(self.path).query)

        if path == "/" or path == "/dashboard":
            self._html(DASHBOARD_HTML)

        elif path == "/api/status":
            ports = cache.get("ports", scan_listening_ports)
            terminals = cache.get("terminals", scan_windsurf_terminals)
            conhost = cache.get("conhost", scan_conhost)
            resources = cache.get("resources", scan_system_resources)
            conflicts = detect_conflicts(ports)

            idle_terms = [t for t in terminals if isinstance(t, dict) and t.get("status") == "idle"]
            active_terms = [t for t in terminals if isinstance(t, dict) and t.get("status") == "active"]

            self._json({
                "ok": True,
                "ts": datetime.now().isoformat(),
                "ports": {
                    "registered": len(PORT_REGISTRY),
                    "live": len(ports),
                    "conflicts": len(conflicts),
                },
                "terminals": {
                    "total": len(terminals),
                    "active": len(active_terms),
                    "idle": len(idle_terms),
                },
                "conhost": conhost,
                "resources": resources,
                "health": "healthy" if len(idle_terms) < 5 and resources.get("ram_used_pct", 100) < 80 else "warning",
            })

        elif path == "/api/ports":
            ports = cache.get("ports", scan_listening_ports)
            enriched = {}
            for port, info in sorted(ports.items()):
                reg = PORT_REGISTRY.get(port, {})
                enriched[port] = {
                    **info,
                    "name": reg.get("name", "Unknown"),
                    "zone": reg.get("zone", "?"),
                    "project": reg.get("project", "Unknown"),
                    "protocol": reg.get("protocol", "?"),
                    "registered": port in PORT_REGISTRY,
                }
            self._json(enriched)

        elif path == "/api/registry":
            self._json(PORT_REGISTRY)

        elif path == "/api/terminals":
            terminals = cache.get("terminals", scan_windsurf_terminals)
            conhost = cache.get("conhost", scan_conhost)
            self._json({"terminals": terminals, "conhost": conhost})

        elif path == "/api/conflicts":
            ports = cache.get("ports", scan_listening_ports)
            conflicts = detect_conflicts(ports)
            self._json({"conflicts": conflicts, "count": len(conflicts)})

        elif path == "/api/resources":
            resources = cache.get("resources", scan_system_resources)
            self._json(resources)

        elif path == "/api/health":
            port = int(query.get("port", [0])[0])
            if port and port in PORT_REGISTRY:
                protocol = PORT_REGISTRY[port].get("protocol", "TCP")
                result = check_port_health(port, protocol)
                self._json({"port": port, **result})
            else:
                self._json({"error": "Specify ?port=XXXX"}, 400)

        elif path == "/api/zones":
            ports = cache.get("ports", scan_listening_ports)
            zones = defaultdict(list)
            for port, reg in PORT_REGISTRY.items():
                zones[reg["zone"]].append({
                    "port": port,
                    "name": reg["name"],
                    "project": reg["project"],
                    "live": port in ports,
                    "process": ports.get(port, {}).get("process", "—"),
                })
            self._json({z: {"name": ZONE_NAMES.get(z, z), "color": ZONE_COLORS.get(z, "#888"), "services": svcs} for z, svcs in sorted(zones.items())})

        elif path == "/api/events":
            n = int(query.get("n", [50])[0])
            self._json(event_log[-n:])

        elif path == "/api/scan":
            cache.invalidate()
            ports = cache.get("ports", scan_listening_ports)
            terminals = cache.get("terminals", scan_windsurf_terminals)
            add_event("info", f"Manual scan: {len(ports)} ports, {len(terminals)} terminals")
            self._json({"ok": True, "ports": len(ports), "terminals": len(terminals)})

        else:
            self._json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/cleanup":
            result = kill_stale_terminals()
            cache.invalidate()
            add_event("warning", f"Cleanup: killed {result.get('killed', 0)} stale terminals")
            self._json(result)

        elif path == "/api/refresh":
            cache.invalidate()
            self._json({"ok": True})

        else:
            self._json({"error": "Not found"}, 404)


# ═══════════════════════════════════════════════════════
# Dashboard HTML
# ═══════════════════════════════════════════════════════

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>端口服务管理中枢</title>
<style>
:root{--bg:#0f172a;--surface:#1e293b;--card:#334155;--border:#475569;--text:#e2e8f0;--muted:#94a3b8;--accent:#8b5cf6;--green:#10b981;--red:#ef4444;--yellow:#f59e0b;--blue:#3b82f6}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
.header{background:linear-gradient(135deg,#1e1b4b,#312e81);padding:16px 24px;display:flex;align-items:center;gap:16px;border-bottom:1px solid var(--border)}
.header h1{font-size:20px;font-weight:700}
.header .badge{background:var(--accent);color:#fff;padding:2px 10px;border-radius:12px;font-size:12px}
.header .actions{margin-left:auto;display:flex;gap:8px}
.btn{padding:6px 14px;border:1px solid var(--border);border-radius:6px;background:var(--surface);color:var(--text);cursor:pointer;font-size:13px;transition:all .15s}
.btn:hover{background:var(--card);border-color:var(--accent)}
.btn.danger{border-color:var(--red);color:var(--red)}
.btn.danger:hover{background:rgba(239,68,68,.15)}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;padding:16px 24px}
.metric{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.metric .label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.metric .value{font-size:28px;font-weight:700;margin-top:2px}
.metric .sub{font-size:11px;color:var(--muted);margin-top:2px}
.metric.healthy .value{color:var(--green)}
.metric.warning .value{color:var(--yellow)}
.metric.danger .value{color:var(--red)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 24px 24px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden}
.panel-title{padding:12px 16px;font-size:14px;font-weight:600;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px}
.panel-body{padding:12px 16px;max-height:400px;overflow-y:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--muted);font-weight:500;padding:6px 8px;border-bottom:1px solid var(--border)}
td{padding:6px 8px;border-bottom:1px solid rgba(71,85,105,.3)}
tr:hover td{background:rgba(139,92,246,.05)}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.dot.up{background:var(--green)}
.dot.down{background:var(--red)}
.dot.idle{background:var(--yellow)}
.zone-badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:11px;font-weight:600;color:#fff}
.zone-A{background:#ef4444}.zone-B{background:#f59e0b}.zone-C{background:#10b981}
.zone-D{background:#3b82f6}.zone-E{background:#8b5cf6}.zone-F{background:#6b7280}
.event{padding:6px 0;border-bottom:1px solid rgba(71,85,105,.2);font-size:12px}
.event .time{color:var(--muted);margin-right:8px;font-family:monospace}
.event.warning{color:var(--yellow)}
.event.error{color:var(--red)}
.full-width{grid-column:1/-1}
.terminal-bar{display:flex;align-items:center;gap:8px;padding:4px 0}
.terminal-bar .bar{flex:1;height:6px;background:var(--card);border-radius:3px;overflow:hidden}
.terminal-bar .fill{height:100%;border-radius:3px;transition:width .3s}
.fill.active{background:var(--green)}
.fill.idle{background:var(--yellow)}
.spinner{display:inline-block;width:14px;height:14px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .6s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div class="header">
  <h1>☯ 端口服务管理中枢</h1>
  <span class="badge" id="healthBadge">Loading...</span>
  <div class="actions">
    <button class="btn" onclick="doScan()">🔍 扫描</button>
    <button class="btn danger" onclick="doCleanup()">🧹 清理僵尸</button>
  </div>
</div>

<div class="metrics" id="metrics"></div>

<div class="grid">
  <div class="panel full-width">
    <div class="panel-title">☰ Zone分区 · 端口全景</div>
    <div class="panel-body" id="zoneTable"></div>
  </div>
  <div class="panel">
    <div class="panel-title">☷ Windsurf终端</div>
    <div class="panel-body" id="termPanel"></div>
  </div>
  <div class="panel">
    <div class="panel-title">☵ 冲突检测</div>
    <div class="panel-body" id="conflictPanel"></div>
  </div>
  <div class="panel full-width">
    <div class="panel-title">☲ 事件日志</div>
    <div class="panel-body" id="eventPanel" style="max-height:200px"></div>
  </div>
</div>

<script>
const API = '';
let refreshTimer;

async function fetchJSON(url) {
  const r = await fetch(API + url);
  return r.json();
}

async function refresh() {
  try {
    const [status, zones, terminals, conflicts, events] = await Promise.all([
      fetchJSON('/api/status'),
      fetchJSON('/api/zones'),
      fetchJSON('/api/terminals'),
      fetchJSON('/api/conflicts'),
      fetchJSON('/api/events?n=30'),
    ]);
    renderMetrics(status);
    renderZones(zones);
    renderTerminals(terminals);
    renderConflicts(conflicts);
    renderEvents(events);
  } catch(e) {
    document.getElementById('healthBadge').textContent = 'ERROR';
  }
}

function renderMetrics(s) {
  const hb = document.getElementById('healthBadge');
  hb.textContent = s.health === 'healthy' ? '✅ Healthy' : '⚠️ Warning';
  hb.style.background = s.health === 'healthy' ? '#10b981' : '#f59e0b';

  const m = document.getElementById('metrics');
  const ramClass = s.resources.ram_used_pct > 80 ? 'danger' : s.resources.ram_used_pct > 65 ? 'warning' : 'healthy';
  const termClass = s.terminals.idle > 4 ? 'danger' : s.terminals.idle > 2 ? 'warning' : 'healthy';
  m.innerHTML = `
    <div class="metric ${ramClass}"><div class="label">RAM使用</div><div class="value">${s.resources.ram_used_pct}%</div><div class="sub">${s.resources.ram_free_gb}GB 空闲 / ${s.resources.ram_total_gb}GB</div></div>
    <div class="metric healthy"><div class="label">活跃端口</div><div class="value">${s.ports.live}</div><div class="sub">${s.ports.registered} 已注册</div></div>
    <div class="metric ${termClass}"><div class="label">终端</div><div class="value">${s.terminals.active}/${s.terminals.total}</div><div class="sub">${s.terminals.idle} 空闲</div></div>
    <div class="metric ${s.ports.conflicts > 3 ? 'warning' : 'healthy'}"><div class="label">冲突</div><div class="value">${s.ports.conflicts}</div><div class="sub">conhost: ${s.conhost.total} (hl:${s.conhost.headless})</div></div>
    <div class="metric healthy"><div class="label">CPU</div><div class="value">${s.resources.cpu_pct||'—'}%</div><div class="sub">系统负载</div></div>
  `;
}

function renderZones(zones) {
  let html = '<table><tr><th>Zone</th><th>端口</th><th>服务</th><th>项目</th><th>状态</th><th>进程</th></tr>';
  for (const [z, data] of Object.entries(zones)) {
    for (const svc of data.services) {
      html += `<tr>
        <td><span class="zone-badge zone-${z}">${z}</span> ${data.name}</td>
        <td><b>${svc.port}</b></td>
        <td>${svc.name}</td>
        <td>${svc.project}</td>
        <td><span class="dot ${svc.live?'up':'down'}"></span>${svc.live?'运行':'离线'}</td>
        <td style="color:var(--muted);font-size:12px">${svc.process}</td>
      </tr>`;
    }
  }
  html += '</table>';
  document.getElementById('zoneTable').innerHTML = html;
}

function renderTerminals(data) {
  const terms = data.terminals || [];
  const ch = data.conhost || {};
  let html = `<div style="margin-bottom:12px;font-size:12px;color:var(--muted)">
    conhost: ${ch.total||0} (headless:${ch.headless||0} regular:${ch.regular||0})
  </div>`;
  if (terms.length === 0) { html += '<div style="color:var(--muted)">No terminals</div>'; }
  for (const t of terms) {
    if (t.error) { html += `<div style="color:var(--red)">${t.error}</div>`; continue; }
    const pct = t.children > 0 ? 100 : 0;
    const cls = t.status === 'active' ? 'active' : 'idle';
    html += `<div class="terminal-bar">
      <span class="dot ${t.status==='active'?'up':'idle'}"></span>
      <span style="font-size:12px;min-width:60px">PID ${t.pid}</span>
      <div class="bar"><div class="fill ${cls}" style="width:${pct}%"></div></div>
      <span style="font-size:11px;color:var(--muted)">${t.mem_mb}MB · ${t.children}ch · ${t.cpu_sec}s</span>
    </div>`;
  }
  document.getElementById('termPanel').innerHTML = html;
}

function renderConflicts(data) {
  const cl = data.conflicts || [];
  if (cl.length === 0) {
    document.getElementById('conflictPanel').innerHTML = '<div style="color:var(--green)">✅ 无冲突</div>';
    return;
  }
  let html = '';
  for (const c of cl) {
    const color = c.severity === 'warning' ? 'var(--yellow)' : c.severity === 'error' ? 'var(--red)' : 'var(--muted)';
    html += `<div style="padding:4px 0;font-size:12px;color:${color}">:${c.port} ${c.message}</div>`;
  }
  document.getElementById('conflictPanel').innerHTML = html;
}

function renderEvents(events) {
  let html = '';
  for (const e of events.reverse()) {
    html += `<div class="event ${e.level}"><span class="time">${e.ts}</span>${e.message}</div>`;
  }
  document.getElementById('eventPanel').innerHTML = html || '<div style="color:var(--muted)">No events</div>';
}

async function doScan() {
  document.getElementById('healthBadge').innerHTML = '<span class="spinner"></span> Scanning...';
  await fetchJSON('/api/scan');
  await refresh();
}

async function doCleanup() {
  if (!confirm('清理所有空闲终端？')) return;
  const r = await fetchJSON('/api/cleanup');
  alert(`Killed ${r.killed || 0} stale terminals`);
  await refresh();
}

// Auto-refresh
refresh();
refreshTimer = setInterval(refresh, 30000);
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════════════════

def main():
    port = 9999
    for arg in sys.argv[1:]:
        if arg.startswith("--port"):
            port = int(arg.split("=")[1]) if "=" in arg else int(sys.argv[sys.argv.index(arg)+1])

    # Pre-scan
    add_event("info", f"Hub starting on :{port}")
    ports = scan_listening_ports()
    add_event("info", f"Initial scan: {len(ports)} listening ports")

    conflicts = detect_conflicts(ports)
    if conflicts:
        for c in conflicts[:10]:
            add_event(c["severity"], c["message"])

    server = http.server.HTTPServer(("0.0.0.0", port), HubHandler)
    server.daemon_threads = True
    print(f"端口服务管理中枢 started on http://127.0.0.1:{port}")
    print(f"  Dashboard: http://127.0.0.1:{port}/dashboard")
    print(f"  API: http://127.0.0.1:{port}/api/status")
    print(f"  Ports: {len(ports)} live | Registry: {len(PORT_REGISTRY)} | Conflicts: {len(conflicts)}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown.")
        server.server_close()


if __name__ == "__main__":
    main()
