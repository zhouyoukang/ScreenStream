"""
太极中枢 v3.0 (原 Agent操作电脑·统一中枢)
一个入口控制万物：事件总线 + 统一告警 + 跨模块调度 + 本地操作 + 远程代理
端口: 9000
用法: python hub.py [--port 9000] [--no-browser]

v3.0 新增:
  - EventBus: 内存级发布/订阅, SSE实时推送 (/api/events/stream)
  - 健康监控: 30s周期自动探测, 状态变化自动告警
  - 跨模块调度: POST /api/dispatch → 路由到任意子系统
  - 统一告警: POST /api/alert → 微信/TTS推送
  - 事件历史: GET /api/events/history
"""

import http.server, json, socket, subprocess, sys, os, time, threading, io
import struct, platform, shutil
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
from urllib.parse import unquote, urlencode
from functools import partial
import base64, mimetypes, queue
from collections import deque

WORKSPACE = Path(__file__).parent.parent
HUB_PORT = 9000

# ═══════════════════════════════════════════════════════════
# Optional imports (graceful degradation)
# ═══════════════════════════════════════════════════════════
HAS_PSUTIL = HAS_PIL = HAS_PYAUTOGUI = HAS_OCR = False
try:
    import psutil; HAS_PSUTIL = True
except ImportError: pass
try:
    from PIL import ImageGrab; HAS_PIL = True
except ImportError: pass
try:
    import pyautogui; pyautogui.FAILSAFE = True; HAS_PYAUTOGUI = True
except ImportError: pass
try:
    from rapidocr_onnxruntime import RapidOCR; HAS_OCR = True; _ocr = RapidOCR()
except ImportError: pass

# ═══════════════════════════════════════════════════════════
# 太极·事件总线 (EventBus)
# ═══════════════════════════════════════════════════════════

class EventBus:
    """内存级发布/订阅事件总线，支持SSE实时推送。"""
    def __init__(self, maxlen=1000):
        self._events = deque(maxlen=maxlen)
        self._subscribers = []
        self._lock = threading.Lock()
        self._seq = 0

    def publish(self, source, event_type, data=None, level="info"):
        with self._lock:
            self._seq += 1
            event = {
                "seq": self._seq,
                "time": time.strftime('%Y-%m-%d %H:%M:%S'),
                "source": source,
                "type": event_type,
                "data": data or {},
                "level": level
            }
            self._events.append(event)
            dead = []
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                except:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)
            return event

    def subscribe(self):
        q = queue.Queue(maxsize=100)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def history(self, limit=50, source=None, event_type=None):
        with self._lock:
            events = list(self._events)
        if source:
            events = [e for e in events if e["source"] == source]
        if event_type:
            events = [e for e in events if e["type"] == event_type]
        return events[-limit:]

event_bus = EventBus()

# ═══════════════════════════════════════════════════════════
# 系统注册表
# ═══════════════════════════════════════════════════════════
SYSTEMS = [
    {"id": "laptop_agent", "name": "笔记本Agent(LAN)", "port": 9903, "host": "192.168.31.179",
     "health": "/health", "dir": "远程桌面", "icon": "💻",
     "public": "http://60.205.171.100:19903/health",
     "apis": ["/health", "/sysinfo", "/screenshot?scale=30", "/processes", "/clipboard",
              "/screen/info", "/windows", "/network/status", "/accounts", "/sessions",
              "/guard", "/watchdog", "/events", "/rules", "/remote/agents"]},
    {"id": "remote_desktop", "name": "远程桌面Agent(本机)", "port": 9903, "host": "127.0.0.1",
     "health": "/health", "dir": "远程桌面", "icon": "🖥️", "expected_stopped": True,
     "apis": ["/health", "/sysinfo", "/screenshot?scale=50", "/processes", "/clipboard",
              "/screen/info", "/windows", "/network/status"]},
    {"id": "remote_hub", "name": "远程中枢", "port": 3002, "host": "127.0.0.1",
     "health": "/health", "dir": "远程桌面/remote-hub", "icon": "🌐",
     "public": "https://aiotvr.xyz/agent/",
     "apis": ["/health", "/brain/state"]},
    {"id": "agi_dashboard", "name": "AGI仪表盘", "port": 9090, "host": "127.0.0.1",
     "health": "/", "dir": "AGI", "icon": "📊",
     "apis": ["/", "/api/health", "/api/credentials", "/api/system-status"]},
    {"id": "vpn", "name": "VPN管理", "port": 9098, "host": "127.0.0.1",
     "health": "/api/status", "dir": "clash-agent", "icon": "🔒",
     "alt_port": 7890,
     "apis": ["/api/status", "/api/version", "/api/connections"]},
    {"id": "smart_home", "name": "智能家居网关", "port": 8900, "host": "127.0.0.1",
     "health": "/", "dir": "智能家居/网关服务", "icon": "🏠", "expected_stopped": True,
     "apis": ["/"]},
    {"id": "cognitive", "name": "认知代理", "port": 9070, "host": "127.0.0.1",
     "health": "/health", "dir": "认知代理", "icon": "🧠", "expected_stopped": True,
     "apis": ["/health", "/status"]},
    {"id": "bookshop", "name": "二手书系统", "port": 8088, "host": "127.0.0.1",
     "health": "/", "icon": "📚",
     "apis": ["/"]},
    {"id": "voxta", "name": "Voxta对话", "port": 5384, "host": "127.0.0.1",
     "health": None, "dir": "VAM-agent/voxta", "icon": "💬",
     "apis": []},
    {"id": "phone", "name": "手机操控库", "port": None, "dir": "手机操控库", "icon": "📱",
     "health": None, "apis": []},
    {"id": "cast", "name": "公网投屏", "port": None, "dir": "公网投屏/cast", "icon": "📺",
     "health": None, "public": "https://aiotvr.xyz/cast/", "apis": []},
    # AI视频剪辑 — 已移除（目录从未创建，为计划项目）
    {"id": "three_realms", "name": "三界隔离", "port": None, "dir": "构建部署/三界隔离", "icon": "👤",
     "health": None, "apis": []},
    {"id": "guardian", "name": "桌面守护", "port": None, "dir": "远程桌面", "icon": "🛡️",
     "health": None, "apis": []},
    {"id": "dual_pc", "name": "双电脑互联", "port": None, "dir": "远程桌面/rdp", "icon": "🔗",
     "health": None, "apis": []},
]

# 笔记本散落资源目录（未注册为独立系统，但需感知）
LAPTOP_RESOURCE_DIRS = [
    {"name": "电脑管理", "path": "E:\\道\\电脑管理", "desc": "桌面自动化POC(B站/豆包/混元/UIA/MCP), 187+项", "icon": "🖱️"},
    {"name": "AI-操控手机", "path": "E:\\道\\AI-操控手机", "desc": "24个手机Agent框架研究(AppAgent/AgentDroid/MobileAgent等)", "icon": "📱"},
    {"name": "AI-浏览器自动化", "path": "E:\\道\\AI-浏览器自动化", "desc": "UFO-3.0/PaddleOCR/Playwright MCP/UIA监控, 39项", "icon": "🌐"},
    {"name": "AI-助手开发实验", "path": "E:\\道\\AI-助手开发实验", "desc": "Agent助手开发实验", "icon": "🧪"},
    {"name": "AI-初恋测试", "path": "E:\\道\\AI-初恋测试", "desc": "AI人格对话测试", "icon": "💬"},
]

PUBLIC_ENDPOINTS = [
    ("健康检查", "https://aiotvr.xyz/api/health"),
    ("远程中枢", "https://aiotvr.xyz/agent/"),
    ("投屏控制", "https://aiotvr.xyz/cast/"),
    ("配置中心", "https://aiotvr.xyz/cast/setup.html"),
]

# ═══════════════════════════════════════════════════════════
# 太极·健康监控 + 统一告警 + 跨模块调度
# ═══════════════════════════════════════════════════════════

_prev_states = {}

def health_check_once():
    """Check all systems, emit events on state change."""
    global _prev_states
    states = {}
    for sys_info in SYSTEMS:
        sid = sys_info["id"]
        port = sys_info.get("port")
        if not port:
            states[sid] = "no_port"
            continue
        host = sys_info.get("host", "127.0.0.1")
        if host == "0.0.0.0": host = "127.0.0.1"
        try:
            with socket.create_connection((host, port), timeout=2):
                states[sid] = "running"
        except:
            states[sid] = "expected_stopped" if sys_info.get("expected_stopped") else "stopped"
    # Detect changes
    for sid, state in states.items():
        prev = _prev_states.get(sid)
        if prev and prev != state:
            sys_info = next((s for s in SYSTEMS if s["id"] == sid), {})
            name = sys_info.get("name", sid)
            if state == "stopped" and prev == "running":
                event_bus.publish("health_monitor", "service_down",
                    {"system": sid, "name": name, "port": sys_info.get("port")}, level="error")
                try_alert(f"⚠️ {name} 已停止 (端口:{sys_info.get('port')})")
            elif state == "running" and prev in ("stopped", "expected_stopped"):
                event_bus.publish("health_monitor", "service_up",
                    {"system": sid, "name": name, "port": sys_info.get("port")}, level="info")
    _prev_states = states
    return states

def try_alert(message):
    """Push alert via available channels."""
    event_bus.publish("alert", "notification", {"message": message}, level="warn")
    # Try WeChat via smart home gateway
    try:
        alert_data = json.dumps({"message": message}).encode('utf-8')
        req = Request("http://127.0.0.1:8900/api/notify",
                      data=alert_data,
                      headers={'Content-Type': 'application/json', 'User-Agent': 'TaichiHub/3.0'},
                      method='POST')
        urlopen(req, timeout=5)
    except:
        pass

def dispatch_action(target_system, action_path, method='GET', params=None):
    """Route an action to the correct subsystem."""
    sys_info = next((s for s in SYSTEMS if s["id"] == target_system), None)
    if not sys_info:
        return {"error": f"unknown system: {target_system}"}
    port = sys_info.get("port")
    if not port:
        return {"error": f"{sys_info['name']} has no port configured"}
    event_bus.publish("dispatch", "action",
        {"target": target_system, "action": action_path, "method": method}, level="info")
    result = proxy_request(target_system, action_path, timeout=15, method=method,
                           post_data=json.dumps(params) if params and method == 'POST' else None)
    event_bus.publish("dispatch", "result",
        {"target": target_system, "action": action_path, "success": "error" not in result}, level="info")
    return result

def _health_monitor_loop():
    """Background thread: check health every 30 seconds."""
    time.sleep(5)
    event_bus.publish("health_monitor", "started", {}, level="info")
    while True:
        try:
            health_check_once()
        except Exception as e:
            event_bus.publish("health_monitor", "error", {"message": str(e)}, level="error")
        time.sleep(30)

# ═══════════════════════════════════════════════════════════
# 太极·智能体系感知 (AGI Dashboard 轻量集成)
# ═══════════════════════════════════════════════════════════

WINDSURF_DIR = WORKSPACE / '.windsurf'
GLOBAL_WINDSURF = Path.home() / '.codeium' / 'windsurf'

def get_agi_summary():
    """Gather AI system metadata: rules, skills, workflows, AGENTS, MCP, health."""
    data = {"rules": [], "skills": [], "workflows": [], "agents_count": 0, "mcp": [], "health": [], "risks": []}
    # Rules
    rd = WINDSURF_DIR / 'rules'
    if rd.exists():
        for f in sorted(rd.glob('*.md')):
            trigger = 'always_on'
            if f.name in ('kotlin-android.md', 'frontend-html.md'): trigger = 'glob'
            elif f.name == 'build-deploy.md': trigger = 'model'
            data["rules"].append({"name": f.stem, "trigger": trigger})
    # Skills
    sd = WINDSURF_DIR / 'skills'
    if sd.exists():
        for d in sorted(sd.iterdir()):
            if d.is_dir() and (d / 'SKILL.md').exists():
                sf = d / 'SKILL.md'
                desc = ''
                try:
                    for line in sf.read_text(encoding='utf-8', errors='replace').splitlines()[:10]:
                        if line.startswith('description:'):
                            desc = line[12:].strip(); break
                except: pass
                data["skills"].append({"name": d.name, "description": desc})
    # Workflows
    wd = WINDSURF_DIR / 'workflows'
    if wd.exists():
        for f in sorted(wd.glob('*.md')):
            desc = ''
            try:
                for line in f.read_text(encoding='utf-8', errors='replace').splitlines()[:5]:
                    if line.startswith('description:'):
                        desc = line[12:].strip(); break
            except: pass
            data["workflows"].append({"name": f.stem, "description": desc})
    # AGENTS.md count (safe, no rglob)
    agent_dirs = ['', '反向控制', '基础设施', '投屏链路', '投屏链路/MJPEG投屏', '投屏链路/RTSP投屏',
                  '投屏链路/WebRTC投屏', '用户界面', '智能家居', '手机操控库', '远程桌面',
                  '构建部署', '构建部署/三界隔离', 'AGI', 'agent操作电脑', '公网投屏',
                  '机器狗开发', '认知代理', '台式机保护', '双电脑互联', '管理',
                  '亲情远程', '电脑公网投屏手机', '国创赛项目', '微信公众号', '手机购物订单',
                  'quest3开发', '3D建模Agent', 'VAM-agent', 'clash-agent', 'YAVAM',
                  'Windsurf无限额度', 'ORS6-VAM饮料摇匀器', '提示词升维', '文档']
    count = 0
    for d in agent_dirs:
        p = WORKSPACE / d / 'AGENTS.md' if d else WORKSPACE / 'AGENTS.md'
        if p.exists(): count += 1
    data["agents_count"] = count
    # MCP
    mc = GLOBAL_WINDSURF / 'mcp_config.json'
    if mc.exists():
        try:
            mj = json.loads(mc.read_text(encoding='utf-8', errors='replace'))
            for name, cfg in mj.get('mcpServers', {}).items():
                data["mcp"].append({"name": name, "disabled": cfg.get('disabled', False)})
        except: pass
    # Health checks
    def chk(name, ok, detail=''):
        data["health"].append({"name": name, "ok": ok, "detail": detail})
    chk("Rules", len(data["rules"]) >= 6, f"{len(data['rules'])}个")
    chk("Skills", len(data["skills"]) >= 15, f"{len(data['skills'])}个")
    chk("Workflows", len(data["workflows"]) >= 10, f"{len(data['workflows'])}个")
    chk("AGENTS.md", data["agents_count"] >= 17, f"{data['agents_count']}个")
    active_mcp = sum(1 for m in data["mcp"] if not m["disabled"])
    chk("MCP活跃", active_mcp >= 3, f"{active_mcp}/{len(data['mcp'])}")
    # Global hooks safety
    gh = GLOBAL_WINDSURF / 'hooks.json'
    if gh.exists():
        try:
            gc = gh.read_text(errors='replace')
            safe = '"hooks": {}' in gc or '"hooks":{}' in gc
            chk("全局Hooks安全", safe, "空(安全)" if safe else "非空!")
            if not safe: data["risks"].append("全局hooks非空！可能影响所有窗口")
        except: chk("全局Hooks安全", False, "读取失败")
    # Skills frontmatter check
    bad_skills = []
    for s in data["skills"]:
        sf = sd / s["name"] / 'SKILL.md'
        if sf.exists():
            try:
                if not sf.read_text(errors='replace').strip().startswith('---'):
                    bad_skills.append(s["name"])
            except: pass
    if bad_skills:
        data["risks"].append(f"Skills缺frontmatter: {', '.join(bad_skills)}")
    chk("Skills frontmatter", len(bad_skills) == 0, f"{len(data['skills'])-len(bad_skills)}/{len(data['skills'])}")
    return data

# ═══════════════════════════════════════════════════════════
# 本地操作能力 (直接在本机执行)
# ═══════════════════════════════════════════════════════════

def local_screenshot():
    if not HAS_PIL:
        return {"error": "PIL not installed (pip install Pillow)"}
    img = ImageGrab.grab()
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=60)
    return {
        "width": img.width, "height": img.height,
        "size_kb": round(buf.tell() / 1024, 1),
        "base64": base64.b64encode(buf.getvalue()).decode()
    }

def local_sysinfo():
    info = {
        "hostname": platform.node(),
        "os": f"{platform.system()} {platform.version()}",
        "arch": platform.machine(),
        "python": platform.python_version(),
        "cwd": str(Path.cwd()),
        "capabilities": {
            "psutil": HAS_PSUTIL, "PIL": HAS_PIL,
            "pyautogui": HAS_PYAUTOGUI, "OCR": HAS_OCR
        }
    }
    if HAS_PSUTIL:
        mem = psutil.virtual_memory()
        info["ram"] = {"total_gb": round(mem.total/1e9, 1), "used_pct": mem.percent,
                       "available_gb": round(mem.available/1e9, 1)}
        info["cpu_pct"] = psutil.cpu_percent(interval=0.5)
        info["disk"] = {}
        for p in psutil.disk_partitions():
            try:
                u = psutil.disk_usage(p.mountpoint)
                info["disk"][p.mountpoint] = {"total_gb": round(u.total/1e9,1),
                                              "free_gb": round(u.free/1e9,1), "pct": u.percent}
            except: pass
        info["boot_time"] = time.strftime('%Y-%m-%d %H:%M:%S',
                                          time.localtime(psutil.boot_time()))
    return info

def local_processes():
    if not HAS_PSUTIL:
        return {"error": "psutil not installed"}
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
        try:
            info = p.info
            procs.append({"pid": info['pid'], "name": info['name'],
                         "mem_mb": round(info['memory_info'].rss / 1e6, 1) if info['memory_info'] else 0,
                         "cpu": info['cpu_percent'] or 0})
        except: pass
    procs.sort(key=lambda x: x['mem_mb'], reverse=True)
    return {"count": len(procs), "top20": procs[:20]}

def local_shell(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          timeout=timeout, cwd=str(WORKSPACE))
        return {"exit_code": r.returncode, "stdout": r.stdout[:4000], "stderr": r.stderr[:2000]}
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}

def local_clipboard():
    try:
        r = subprocess.run(['powershell', '-c', 'Get-Clipboard'], capture_output=True,
                          text=True, timeout=5)
        return {"text": r.stdout.strip()}
    except:
        return {"error": "clipboard read failed"}

def local_windows():
    if not HAS_PSUTIL:
        return {"error": "psutil not installed"}
    try:
        import ctypes
        user32 = ctypes.windll.user32
        fg = user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(fg, buf, 256)
        return {"foreground_hwnd": fg, "foreground_title": buf.value}
    except:
        return {"error": "win32 API failed"}

def local_ports():
    results = {}
    for sys_info in SYSTEMS:
        port = sys_info.get("port")
        if not port: continue
        host = sys_info.get("host", "127.0.0.1")
        if host == "0.0.0.0": host = "127.0.0.1"
        try:
            with socket.create_connection((host, port), timeout=2):
                results[sys_info["id"]] = {"port": port, "status": "open"}
        except:
            results[sys_info["id"]] = {"port": port, "status": "closed",
                                        "expected": sys_info.get("expected_stopped", False)}
    return results

def local_click(x, y):
    if not HAS_PYAUTOGUI:
        return {"error": "pyautogui not installed"}
    pyautogui.click(x, y)
    return {"ok": True, "x": x, "y": y}

def local_key(key_str):
    if not HAS_PYAUTOGUI:
        return {"error": "pyautogui not installed"}
    if '+' in key_str:
        pyautogui.hotkey(*key_str.split('+'))
    else:
        pyautogui.press(key_str)
    return {"ok": True, "key": key_str}

def local_type_text(text):
    if not HAS_PYAUTOGUI:
        return {"error": "pyautogui not installed"}
    pyautogui.typewrite(text, interval=0.02) if text.isascii() else None
    if not text.isascii():
        import subprocess
        subprocess.run(['powershell', '-c', f'Set-Clipboard "{text}"; Add-Type -A System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("^v")'],
                      timeout=5, capture_output=True)
    return {"ok": True, "length": len(text)}

def local_scroll(x, y, clicks):
    if not HAS_PYAUTOGUI:
        return {"error": "pyautogui not installed"}
    pyautogui.scroll(clicks, x=x, y=y)
    return {"ok": True, "x": x, "y": y, "clicks": clicks}

def local_move(x, y):
    if not HAS_PYAUTOGUI:
        return {"error": "pyautogui not installed"}
    pyautogui.moveTo(x, y)
    return {"ok": True, "x": x, "y": y}

def local_drag(x1, y1, x2, y2, duration=0.5):
    if not HAS_PYAUTOGUI:
        return {"error": "pyautogui not installed"}
    pyautogui.moveTo(x1, y1)
    pyautogui.drag(x2 - x1, y2 - y1, duration=duration)
    return {"ok": True, "from": [x1, y1], "to": [x2, y2]}

def local_files(path=None):
    target = Path(path) if path else WORKSPACE
    if not target.exists():
        return {"error": f"path not found: {target}"}
    items = []
    try:
        for entry in sorted(target.iterdir()):
            try:
                st = entry.stat()
                items.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": st.st_size if entry.is_file() else 0,
                    "modified": time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime))
                })
            except (PermissionError, OSError):
                items.append({"name": entry.name, "is_dir": entry.is_dir(), "error": "access denied"})
    except PermissionError:
        return {"error": "permission denied"}
    return {"path": str(target), "count": len(items), "items": items}

def local_ocr():
    if not HAS_OCR or not HAS_PIL:
        return {"error": "OCR or PIL not installed"}
    img = ImageGrab.grab()
    result, _ = _ocr(img)
    texts = []
    if result:
        for line in result:
            texts.append({"text": line[1], "confidence": round(line[2], 3),
                         "box": line[0]})
    return {"count": len(texts), "texts": texts[:50]}

# ═══════════════════════════════════════════════════════════
# 远程代理转发
# ═══════════════════════════════════════════════════════════

def proxy_request(system_id, path, timeout=10, method='GET', post_data=None):
    sys_info = next((s for s in SYSTEMS if s["id"] == system_id), None)
    if not sys_info:
        return {"error": f"unknown system: {system_id}"}
    port = sys_info.get("port")
    if not port:
        return {"error": f"{sys_info['name']} has no port"}
    host = sys_info.get("host", "127.0.0.1")
    if host == "0.0.0.0": host = "127.0.0.1"
    url = f"http://{host}:{port}{path}"
    try:
        headers = {'User-Agent': 'AgentHub/2.0'}
        data_bytes = None
        if method == 'POST' and post_data:
            data_bytes = post_data.encode('utf-8') if isinstance(post_data, str) else post_data
            headers['Content-Type'] = 'application/json'
        req = Request(url, data=data_bytes, headers=headers, method=method)
        resp = urlopen(req, timeout=timeout)
        body = resp.read(65536).decode('utf-8', errors='replace')
        try:
            return json.loads(body)
        except:
            return {"raw": body[:4000], "status": resp.status}
    except URLError as e:
        return {"error": str(e), "url": url}
    except Exception as e:
        return {"error": str(e)}

# ═══════════════════════════════════════════════════════════
# 全系统探测
# ═══════════════════════════════════════════════════════════

def full_probe():
    results = {"timestamp": time.strftime('%Y-%m-%d %H:%M:%S'), "systems": [], "public": []}

    for sys_info in SYSTEMS:
        r = {"id": sys_info["id"], "name": sys_info["name"], "icon": sys_info.get("icon", ""),
             "port": sys_info.get("port"), "status": "unknown", "issues": []}

        # File check
        d = sys_info.get("dir")
        if d:
            base = WORKSPACE / d
            r["dir_exists"] = base.exists()
            if not base.exists():
                r["issues"].append(f"目录不存在: {d}")

        # Port check
        port = sys_info.get("port")
        if port:
            host = sys_info.get("host", "127.0.0.1")
            if host == "0.0.0.0": host = "127.0.0.1"
            try:
                with socket.create_connection((host, port), timeout=2):
                    r["status"] = "running"
            except:
                r["status"] = "expected_stopped" if sys_info.get("expected_stopped") else "stopped"
                if not sys_info.get("expected_stopped"):
                    r["issues"].append(f"端口 {port} 未监听")
        else:
            r["status"] = "no_port"

        # HTTP health
        health = sys_info.get("health")
        if health and port and r["status"] == "running":
            host = sys_info.get("host", "127.0.0.1")
            if host == "0.0.0.0": host = "127.0.0.1"
            try:
                req = Request(f"http://{host}:{port}{health}", headers={'User-Agent': 'AgentHub/1.0'})
                resp = urlopen(req, timeout=5)
                r["http"] = resp.status
            except Exception as e:
                r["http"] = 0
                r["issues"].append(f"HTTP健康检查失败: {e}")

        # Public URL
        pub = sys_info.get("public")
        if pub:
            try:
                req = Request(pub, headers={'User-Agent': 'AgentHub/1.0'})
                resp = urlopen(req, timeout=10)
                r["public_status"] = resp.status
            except:
                r["public_status"] = 0

        # API deep test
        if r["status"] == "running" and sys_info.get("apis"):
            r["api_results"] = {}
            host = sys_info.get("host", "127.0.0.1")
            if host == "0.0.0.0": host = "127.0.0.1"
            for api in sys_info["apis"][:5]:
                try:
                    req = Request(f"http://{host}:{port}{api}", headers={'User-Agent': 'AgentHub/1.0'})
                    resp = urlopen(req, timeout=5)
                    r["api_results"][api] = resp.status
                except Exception as e:
                    r["api_results"][api] = str(e)[:80]

        results["systems"].append(r)

    # Public endpoints
    for name, url in PUBLIC_ENDPOINTS:
        try:
            req = Request(url, headers={'User-Agent': 'AgentHub/1.0'})
            resp = urlopen(req, timeout=10)
            results["public"].append({"name": name, "url": url, "status": resp.status})
        except Exception as e:
            results["public"].append({"name": name, "url": url, "status": 0, "error": str(e)[:80]})

    # Local capabilities
    results["local"] = {
        "hostname": platform.node(),
        "capabilities": {"psutil": HAS_PSUTIL, "PIL": HAS_PIL,
                         "pyautogui": HAS_PYAUTOGUI, "OCR": HAS_OCR}
    }

    # Laptop resource directories (via remote agent API)
    laptop_sys = next((s for s in SYSTEMS if s["id"] == "laptop_agent"), None)
    if laptop_sys and any(s["id"] == "laptop_agent" and s.get("port") for s in SYSTEMS):
        host = laptop_sys.get("host", "192.168.31.179")
        port = laptop_sys.get("port", 9903)
        results["laptop_resources"] = []
        for rd in LAPTOP_RESOURCE_DIRS:
            entry = {"name": rd["name"], "path": rd["path"], "desc": rd["desc"], "icon": rd["icon"]}
            try:
                from urllib.parse import quote
                url = f"http://{host}:{port}/files?path={quote(rd['path'])}"
                req = Request(url, headers={'User-Agent': 'AgentHub/2.0'})
                resp = urlopen(req, timeout=3)
                data = json.loads(resp.read(8192).decode('utf-8', errors='replace'))
                entry["exists"] = True
                entry["count"] = data.get("count", 0)
            except:
                entry["exists"] = False
                entry["count"] = 0
            results["laptop_resources"].append(entry)

    return results

# ═══════════════════════════════════════════════════════════
# Web Dashboard HTML
# ═══════════════════════════════════════════════════════════

DASHBOARD_HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>太极中枢 v3.0</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0f;color:#e0e0e0;min-height:100vh}
.header{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:20px 24px;border-bottom:1px solid #333;display:flex;justify-content:space-between;align-items:center}
.header h1{font-size:22px;background:linear-gradient(90deg,#00d2ff,#3a7bd5);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header .info{font-size:12px;color:#888}
.tabs{display:flex;gap:2px;background:#111;padding:4px 8px;border-bottom:1px solid #222}
.tab{padding:8px 16px;cursor:pointer;border-radius:6px 6px 0 0;font-size:13px;color:#888;transition:.2s}
.tab:hover{color:#ccc;background:#1a1a2e}
.tab.active{color:#00d2ff;background:#1a1a2e;border-bottom:2px solid #00d2ff}
.content{padding:16px 20px;max-width:1400px;margin:0 auto}
.panel{display:none}.panel.active{display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin:12px 0}
.card{background:#14141f;border:1px solid #222;border-radius:10px;padding:14px;transition:.2s}
.card:hover{border-color:#3a7bd5;transform:translateY(-1px)}
.card .title{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.card .title .icon{font-size:20px}
.card .title .name{font-weight:600;font-size:14px}
.card .status{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600}
.s-run{background:#0d3320;color:#22c55e;border:1px solid #166534}
.s-stop{background:#3b1010;color:#ef4444;border:1px solid #7f1d1d}
.s-pause{background:#3b2f10;color:#f59e0b;border:1px solid #78350f}
.s-file{background:#1a1a2e;color:#60a5fa;border:1px solid #1e3a5f}
.card .detail{font-size:12px;color:#777;margin-top:6px;line-height:1.6}
.card .apis{margin-top:8px;display:flex;flex-wrap:wrap;gap:4px}
.card .apis .api{font-size:10px;padding:2px 6px;background:#1a1a2e;border:1px solid #333;border-radius:4px;cursor:pointer;transition:.15s}
.card .apis .api:hover{border-color:#00d2ff;color:#00d2ff}
.card .apis .api.ok{border-color:#166534;color:#22c55e}
.card .apis .api.fail{border-color:#7f1d1d;color:#ef4444}
.btn{padding:8px 16px;border:1px solid #333;background:#1a1a2e;color:#e0e0e0;border-radius:6px;cursor:pointer;font-size:13px;transition:.2s}
.btn:hover{border-color:#3a7bd5;color:#00d2ff}
.btn.primary{background:#1e3a5f;border-color:#3a7bd5;color:#00d2ff}
.section{margin:16px 0}.section h3{font-size:15px;color:#aaa;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #222}
.log{background:#0a0a12;border:1px solid #222;border-radius:8px;padding:12px;font-family:'Cascadia Code',monospace;font-size:12px;max-height:400px;overflow-y:auto;white-space:pre-wrap;line-height:1.7}
.pub-row{display:flex;align-items:center;gap:12px;padding:6px 0;font-size:13px}
.pub-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.pub-dot.ok{background:#22c55e}.pub-dot.fail{background:#ef4444}
.local-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px}
.local-card{background:#14141f;border:1px solid #222;border-radius:8px;padding:10px;text-align:center;cursor:pointer;transition:.15s}
.local-card:hover{border-color:#3a7bd5;transform:scale(1.02)}
.local-card .licon{font-size:24px;margin-bottom:4px}
.local-card .lname{font-size:12px;color:#aaa}
.result-area{margin-top:12px;background:#0a0a12;border:1px solid #222;border-radius:8px;padding:12px;font-family:monospace;font-size:12px;max-height:500px;overflow:auto;display:none}
.stats{display:flex;gap:16px;flex-wrap:wrap;margin:12px 0}
.stat{background:#14141f;border:1px solid #222;border-radius:8px;padding:10px 16px;min-width:100px;text-align:center}
.stat .val{font-size:24px;font-weight:700;color:#00d2ff}.stat .lbl{font-size:11px;color:#777;margin-top:2px}
.shell-input{display:flex;gap:8px;margin:12px 0}
.shell-input input{flex:1;background:#0a0a12;border:1px solid #333;border-radius:6px;padding:8px 12px;color:#e0e0e0;font-family:monospace;font-size:13px}
.shell-input input:focus{outline:none;border-color:#3a7bd5}
@media(max-width:600px){.grid{grid-template-columns:1fr}.local-grid{grid-template-columns:repeat(3,1fr)}}
</style>
</head>
<body>
<div class="header">
  <h1>☯️ 太极中枢 v3.0</h1>
  <div class="info" id="headerInfo">加载中...</div>
</div>
<div class="tabs">
  <div class="tab active" onclick="switchTab('overview')">📊 总览</div>
  <div class="tab" onclick="switchTab('local')">🎮 本地操作</div>
  <div class="tab" onclick="switchTab('remote')">🌐 远程代理</div>
  <div class="tab" onclick="switchTab('public')">☁️ 公网</div>
  <div class="tab" onclick="switchTab('shell')">⌨️ Shell</div>
  <div class="tab" onclick="switchTab('events')">📡 事件</div>
  <div class="tab" onclick="switchTab('dispatch')">🎯 调度</div>
  <div class="tab" onclick="switchTab('agi')">☯ 道</div>
</div>
<div class="content">
  <!-- 总览 -->
  <div class="panel active" id="p-overview">
    <div class="stats" id="statsBar"></div>
    <div class="section"><h3>🔌 系统状态</h3><div class="grid" id="systemGrid"></div></div>
  </div>
  <!-- 本地操作 -->
  <div class="panel" id="p-local">
    <div class="section"><h3>🎮 本机能力 (直接执行)</h3>
    <div class="local-grid" id="localGrid"></div></div>
    <div class="result-area" id="localResult"></div>
  </div>
  <!-- 远程代理 -->
  <div class="panel" id="p-remote">
    <div class="section"><h3>🌐 远程API转发</h3>
    <p style="font-size:13px;color:#777;margin-bottom:12px">选择系统和API端点，转发请求并显示结果</p>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
      <select id="remoteSystem" class="btn" style="min-width:150px"></select>
      <select id="remoteApi" class="btn" style="min-width:200px"></select>
      <button class="btn primary" onclick="callRemoteApi()">发送</button>
    </div></div>
    <div class="result-area" id="remoteResult"></div>
  </div>
  <!-- 公网 -->
  <div class="panel" id="p-public">
    <div class="section"><h3>☁️ 公网端点状态</h3><div id="publicList"></div></div>
  </div>
  <!-- Shell -->
  <div class="panel" id="p-shell">
    <div class="section"><h3>⌨️ 本地Shell</h3>
    <div class="shell-input">
      <input type="text" id="shellInput" placeholder="输入命令..." onkeydown="if(event.key==='Enter')runShell()">
      <button class="btn primary" onclick="runShell()">执行</button>
    </div></div>
    <div class="log" id="shellLog">等待命令...</div>
  </div>
  <!-- 事件总线 -->
  <div class="panel" id="p-events">
    <div class="section"><h3>📡 事件总线 (EventBus)</h3>
    <div style="display:flex;gap:8px;margin-bottom:12px;align-items:center">
      <button class="btn primary" onclick="loadEvents()">刷新</button>
      <button class="btn" id="sseBtn" onclick="toggleSSE()">🟢 实时监听</button>
      <span id="sseStatus" style="font-size:12px;color:#777">未连接</span>
      <span style="flex:1"></span>
      <span id="eventCount" style="font-size:12px;color:#555"></span>
    </div></div>
    <div class="log" id="eventLog" style="display:block;max-height:600px">加载中...</div>
  </div>
  <!-- 跨模块调度 -->
  <div class="panel" id="p-dispatch">
    <div class="section"><h3>🎯 跨模块调度</h3>
    <p style="font-size:13px;color:#777;margin-bottom:12px">向任意子系统发送调度命令，结果通过事件总线记录</p>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
      <select id="dispSys" class="btn" style="min-width:160px"></select>
      <input type="text" id="dispPath" style="flex:1;min-width:180px;background:#0a0a12;border:1px solid #333;border-radius:6px;padding:8px 12px;color:#e0e0e0;font-family:monospace;font-size:13px" placeholder="/health" value="/">
      <select id="dispMethod" class="btn"><option>GET</option><option>POST</option></select>
      <button class="btn primary" onclick="runDispatch()">调度</button>
    </div>
    <textarea id="dispBody" style="width:100%;height:80px;background:#0a0a12;border:1px solid #333;border-radius:6px;padding:8px;color:#e0e0e0;font-family:monospace;font-size:12px;resize:vertical;display:none" placeholder='{"key":"value"}'></textarea>
    </div>
    <div class="result-area" id="dispResult"></div>
  </div>
  <!-- 智能体系 -->
  <div class="panel" id="p-agi">
    <div class="section"><h3>☯ 智能体系 (AI Config Overview)</h3>
    <div style="display:flex;gap:8px;margin-bottom:12px;align-items:center">
      <button class="btn primary" onclick="loadAgi()">刷新</button>
      <a href="http://localhost:9090" target="_blank" class="btn" style="text-decoration:none">🔗 完整仪表盘</a>
      <span id="agiStatus" style="font-size:12px;color:#777"></span>
    </div></div>
    <div class="stats" id="agiStats"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0" id="agiGrid"></div>
    <div class="section" id="agiHealthSection" style="display:none"><h3>🏥 健康检查</h3><div id="agiHealth"></div></div>
    <div class="section" id="agiRiskSection" style="display:none"><h3>⚠️ 风险</h3><div id="agiRisks"></div></div>
  </div>
</div>
<script>
let probeData = null;
const LOCAL_OPS = [
  {id:'screenshot',icon:'📸',name:'截屏'},
  {id:'sysinfo',icon:'💻',name:'系统信息'},
  {id:'processes',icon:'📋',name:'进程列表'},
  {id:'ports',icon:'🔌',name:'端口扫描'},
  {id:'clipboard',icon:'📌',name:'剪贴板'},
  {id:'windows',icon:'🪟',name:'活动窗口'},
  {id:'ocr',icon:'👁️',name:'屏幕OCR'},
];
function switchTab(id){
  const m={overview:'总览',local:'本地',remote:'远程',public:'公网',shell:'Shell',events:'事件',dispatch:'调度',agi:'道'};
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.textContent.includes(m[id])));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.getElementById('p-'+id).classList.add('active');
  if(id==='events')loadEvents();
  if(id==='agi')loadAgi();
}
async function api(path){
  const r=await fetch('/api'+path);return r.json();
}
async function loadProbe(){
  probeData=await api('/probe');
  renderOverview();renderRemoteSelects();renderPublic();
  document.getElementById('headerInfo').textContent=probeData.timestamp+' | '+probeData.local.hostname;
}
function renderOverview(){
  const d=probeData;
  let run=0,stop=0,pause=0,file=0;
  d.systems.forEach(s=>{
    if(s.status==='running')run++;
    else if(s.status==='stopped')stop++;
    else if(s.status==='expected_stopped')pause++;
    else file++;
  });
  document.getElementById('statsBar').innerHTML=
    `<div class="stat"><div class="val">${d.systems.length}</div><div class="lbl">总系统</div></div>`+
    `<div class="stat"><div class="val" style="color:#22c55e">${run}</div><div class="lbl">运行中</div></div>`+
    `<div class="stat"><div class="val" style="color:#f59e0b">${pause}</div><div class="lbl">待机</div></div>`+
    `<div class="stat"><div class="val" style="color:#ef4444">${stop}</div><div class="lbl">异常</div></div>`+
    `<div class="stat"><div class="val" style="color:#60a5fa">${file}</div><div class="lbl">仅文件</div></div>`+
    `<div class="stat"><div class="val">${d.local.capabilities.psutil?'✅':'❌'}</div><div class="lbl">psutil</div></div>`+
    `<div class="stat"><div class="val">${d.local.capabilities.PIL?'✅':'❌'}</div><div class="lbl">PIL</div></div>`+
    `<div class="stat"><div class="val">${d.local.capabilities.pyautogui?'✅':'❌'}</div><div class="lbl">pyautogui</div></div>`;
  let html='';
  d.systems.forEach(s=>{
    const sc = s.status==='running'?'s-run':s.status==='stopped'?'s-stop':s.status==='expected_stopped'?'s-pause':'s-file';
    const sl = {running:'运行中',stopped:'已停止',expected_stopped:'待机',no_port:'仅文件'}[s.status]||s.status;
    let apis='';
    if(s.api_results){Object.entries(s.api_results).forEach(([k,v])=>{
      apis+=`<span class="api ${typeof v==='number'&&v>=200&&v<400?'ok':'fail'}">${k} ${typeof v==='number'?v:'⚠️'}</span>`;
    });}
    let detail=s.port?`端口 :${s.port}`:'无端口';
    if(s.http)detail+=` | HTTP ${s.http}`;
    if(s.public_status)detail+=` | 公网 ${s.public_status>=200?'✅':'❌'}`;
    html+=`<div class="card"><div class="title"><span class="icon">${s.icon}</span><span class="name">${s.name}</span><span class="status ${sc}">${sl}</span></div><div class="detail">${detail}</div>${apis?`<div class="apis">${apis}</div>`:''}</div>`;
  });
  document.getElementById('systemGrid').innerHTML=html;
}
function renderLocalGrid(){
  let html='';
  LOCAL_OPS.forEach(op=>{
    html+=`<div class="local-card" onclick="runLocal('${op.id}')"><div class="licon">${op.icon}</div><div class="lname">${op.name}</div></div>`;
  });
  document.getElementById('localGrid').innerHTML=html;
}
async function runLocal(op){
  const ra=document.getElementById('localResult');
  ra.style.display='block';ra.textContent='执行中...';
  try{
    const d=await api('/local/'+op);
    if(op==='screenshot'&&d.base64){
      ra.innerHTML=`<p>📸 ${d.width}x${d.height} (${d.size_kb}KB)</p><img src="data:image/jpeg;base64,${d.base64}" style="max-width:100%;border-radius:8px;margin-top:8px">`;
    }else{
      ra.textContent=JSON.stringify(d,null,2);
    }
  }catch(e){ra.textContent='错误: '+e.message;}
}
function renderRemoteSelects(){
  const sel=document.getElementById('remoteSystem');
  sel.innerHTML='';
  probeData.systems.filter(s=>s.port&&s.status==='running').forEach(s=>{
    sel.innerHTML+=`<option value="${s.id}">${s.icon} ${s.name} :${s.port}</option>`;
  });
  sel.onchange=updateApiSelect;
  updateApiSelect();
}
function updateApiSelect(){
  const sid=document.getElementById('remoteSystem').value;
  const sys=SYSTEMS_JS.find(s=>s.id===sid);
  const sel=document.getElementById('remoteApi');
  sel.innerHTML='';
  if(sys&&sys.apis){sys.apis.forEach(a=>{sel.innerHTML+=`<option value="${a}">${a}</option>`;});}
}
async function callRemoteApi(){
  const sid=document.getElementById('remoteSystem').value;
  const path=document.getElementById('remoteApi').value;
  const ra=document.getElementById('remoteResult');
  ra.style.display='block';ra.textContent='请求中...';
  try{
    const d=await api(`/proxy/${sid}${path}`);
    ra.textContent=JSON.stringify(d,null,2);
  }catch(e){ra.textContent='错误: '+e.message;}
}
function renderPublic(){
  let html='';
  probeData.public.forEach(p=>{
    const ok=p.status>=200&&p.status<400;
    html+=`<div class="pub-row"><span class="pub-dot ${ok?'ok':'fail'}"></span><span style="min-width:120px">${p.name}</span><a href="${p.url}" target="_blank" style="color:#3a7bd5;text-decoration:none;font-size:12px">${p.url}</a><span style="color:${ok?'#22c55e':'#ef4444'};font-size:12px">${p.status||'N/A'}</span></div>`;
  });
  document.getElementById('publicList').innerHTML=html;
}
async function runShell(){
  const input=document.getElementById('shellInput');
  const log=document.getElementById('shellLog');
  const cmd=input.value.trim();if(!cmd)return;
  log.textContent+='\n> '+cmd+'\n执行中...\n';input.value='';
  try{
    const d=await api('/local/shell?cmd='+encodeURIComponent(cmd));
    log.textContent+=d.stdout||'';
    if(d.stderr)log.textContent+='[stderr] '+d.stderr;
    log.textContent+=`\n[exit: ${d.exit_code}]\n`;
  }catch(e){log.textContent+='错误: '+e.message+'\n';}
  log.scrollTop=log.scrollHeight;
}
const SYSTEMS_JS=''' + json.dumps([{"id":s["id"],"apis":s.get("apis",[])} for s in SYSTEMS], ensure_ascii=False) + r''';
// EventBus
let _sse=null;
async function loadEvents(){
  const el=document.getElementById('eventLog');
  try{
    const d=await api('/events/history?limit=100');
    const ct=document.getElementById('eventCount');
    ct.textContent=d.length+' events';
    el.textContent=d.map(e=>`[${e.time}] ${e.level.toUpperCase().padEnd(5)} ${e.source}/${e.type}: ${JSON.stringify(e.data)}`).join('\n')||'无事件';
    el.scrollTop=el.scrollHeight;
  }catch(e){el.textContent='加载失败: '+e.message;}
}
function toggleSSE(){
  if(_sse){stopSSE();return;}
  _sse=new EventSource('/api/events/stream');
  _sse.onmessage=e=>{
    const el=document.getElementById('eventLog');
    const ev=JSON.parse(e.data);
    el.textContent+=`\n[${ev.time}] ${ev.level.toUpperCase().padEnd(5)} ${ev.source}/${ev.type}: ${JSON.stringify(ev.data)}`;
    el.scrollTop=el.scrollHeight;
    const ct=document.getElementById('eventCount');
    ct.textContent=(parseInt(ct.textContent)||0)+1+' events (live)';
  };
  _sse.onopen=()=>{document.getElementById('sseStatus').textContent='🟢 已连接';document.getElementById('sseBtn').textContent='🔴 停止监听';};
  _sse.onerror=()=>{document.getElementById('sseStatus').textContent='🔴 断开';stopSSE();};
}
function stopSSE(){if(_sse){_sse.close();_sse=null;}document.getElementById('sseStatus').textContent='未连接';document.getElementById('sseBtn').textContent='🟢 实时监听';}
// Dispatch
function initDispatch(){
  const sel=document.getElementById('dispSys');sel.innerHTML='';
  SYSTEMS_JS.forEach(s=>{if(s.apis&&s.apis.length)sel.innerHTML+=`<option value="${s.id}">${s.id}</option>`;});
  document.getElementById('dispMethod').onchange=function(){document.getElementById('dispBody').style.display=this.value==='POST'?'block':'none';};
}
async function runDispatch(){
  const sys=document.getElementById('dispSys').value;
  const path=document.getElementById('dispPath').value||'/';
  const method=document.getElementById('dispMethod').value;
  const ra=document.getElementById('dispResult');
  ra.style.display='block';ra.textContent='调度中...';
  try{
    const body={target:sys,action:path,method:method};
    if(method==='POST'){try{body.params=JSON.parse(document.getElementById('dispBody').value||'{}');}catch(e){body.params={};}}
    const r=await fetch('/api/dispatch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d=await r.json();
    ra.textContent=JSON.stringify(d,null,2);
  }catch(e){ra.textContent='错误: '+e.message;}
}
// AGI
async function loadAgi(){
  const st=document.getElementById('agiStatus');
  st.textContent='加载中...';
  try{
    const d=await api('/agi');
    st.textContent=`${d.rules.length} rules · ${d.skills.length} skills · ${d.workflows.length} workflows · ${d.agents_count} AGENTS`;
    // Stats bar
    const active=d.mcp.filter(m=>!m.disabled).length;
    document.getElementById('agiStats').innerHTML=
      `<div class="stat"><div class="val">${d.rules.length}</div><div class="lbl">律·Rules</div></div>`+
      `<div class="stat"><div class="val">${d.skills.length}</div><div class="lbl">术·Skills</div></div>`+
      `<div class="stat"><div class="val">${d.workflows.length}</div><div class="lbl">法·Workflows</div></div>`+
      `<div class="stat"><div class="val">${d.agents_count}</div><div class="lbl">德·AGENTS</div></div>`+
      `<div class="stat"><div class="val">${active}/${d.mcp.length}</div><div class="lbl">器·MCP</div></div>`;
    // Grid: rules + skills + workflows + MCP
    let g='';
    g+='<div style="background:#14141f;border:1px solid #222;border-radius:10px;padding:14px"><h4 style="font-size:13px;color:#aaa;margin-bottom:8px">📜 Rules</h4>';
    d.rules.forEach(r=>{const c=r.trigger==='always_on'?'#22c55e':r.trigger==='glob'?'#f59e0b':'#60a5fa';g+=`<div style="font-size:12px;padding:3px 0"><span style="color:${c};font-size:10px">●</span> ${r.name} <span style="color:#555;font-size:10px">${r.trigger}</span></div>`;});
    g+='</div>';
    g+='<div style="background:#14141f;border:1px solid #222;border-radius:10px;padding:14px"><h4 style="font-size:13px;color:#aaa;margin-bottom:8px">🛠️ Skills</h4>';
    d.skills.forEach(s=>{g+=`<div style="font-size:12px;padding:2px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${s.description||''}"><span style="color:#22c55e;font-size:10px">●</span> ${s.name}</div>`;});
    g+='</div>';
    g+='<div style="background:#14141f;border:1px solid #222;border-radius:10px;padding:14px"><h4 style="font-size:13px;color:#aaa;margin-bottom:8px">⚡ Workflows</h4>';
    d.workflows.forEach(w=>{g+=`<div style="font-size:12px;padding:2px 0" title="${w.description||''}">/` +w.name+'</div>';});
    g+='</div>';
    g+='<div style="background:#14141f;border:1px solid #222;border-radius:10px;padding:14px"><h4 style="font-size:13px;color:#aaa;margin-bottom:8px">🔌 MCP Servers</h4>';
    d.mcp.forEach(m=>{g+=`<div style="font-size:12px;padding:3px 0"><span style="color:${m.disabled?'#ef4444':'#22c55e'};font-size:10px">●</span> ${m.name} <span style="color:#555;font-size:10px">${m.disabled?'disabled':'active'}</span></div>`;});
    g+='</div>';
    document.getElementById('agiGrid').innerHTML=g;
    // Health
    const hs=document.getElementById('agiHealthSection');
    hs.style.display='block';
    document.getElementById('agiHealth').innerHTML=d.health.map(h=>`<div style="font-size:13px;padding:4px 0"><span style="color:${h.ok?'#22c55e':'#ef4444'}">${h.ok?'✓':'✗'}</span> ${h.name} <span style="color:#555;font-size:11px">${h.detail}</span></div>`).join('');
    // Risks
    const rs=document.getElementById('agiRiskSection');
    if(d.risks.length){rs.style.display='block';document.getElementById('agiRisks').innerHTML=d.risks.map(r=>`<div style="font-size:12px;padding:4px 8px;margin:3px 0;border-left:2px solid #ef4444;background:rgba(239,68,68,.06);color:#ef4444">${r}</div>`).join('');}else{rs.style.display='none';}
  }catch(e){st.textContent='加载失败: '+e.message;}
}
renderLocalGrid();
initDispatch();
loadProbe();
setInterval(loadProbe,30000);
</script>
</body></html>'''

# ═══════════════════════════════════════════════════════════
# HTTP Server
# ═══════════════════════════════════════════════════════════

class HubHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress logs

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html):
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split('?')[0]
        params = {}
        if '?' in self.path:
            for p in self.path.split('?')[1].split('&'):
                if '=' in p:
                    k, v = p.split('=', 1)
                    params[k] = v

        # Dashboard
        if path == '/' or path == '/index.html':
            return self._html(DASHBOARD_HTML)

        # API: Full probe
        if path == '/api/probe':
            return self._json(full_probe())

        # API: Local operations
        if path == '/api/local/screenshot':
            return self._json(local_screenshot())
        if path == '/api/local/sysinfo':
            return self._json(local_sysinfo())
        if path == '/api/local/processes':
            return self._json(local_processes())
        if path == '/api/local/ports':
            return self._json(local_ports())
        if path == '/api/local/clipboard':
            return self._json(local_clipboard())
        if path == '/api/local/windows':
            return self._json(local_windows())
        if path == '/api/local/ocr':
            return self._json(local_ocr())
        if path == '/api/local/shell':
            cmd = params.get('cmd', '')
            if cmd:
                cmd = unquote(cmd)
            return self._json(local_shell(cmd) if cmd else {"error": "no cmd"})
        if path == '/api/local/click':
            x, y = int(params.get('x', 0)), int(params.get('y', 0))
            return self._json(local_click(x, y))
        if path == '/api/local/key':
            return self._json(local_key(params.get('key', '')))
        if path == '/api/local/scroll':
            x, y = int(params.get('x', 0)), int(params.get('y', 0))
            clicks = int(params.get('clicks', 3))
            return self._json(local_scroll(x, y, clicks))
        if path == '/api/local/move':
            x, y = int(params.get('x', 0)), int(params.get('y', 0))
            return self._json(local_move(x, y))
        if path == '/api/local/files':
            p = unquote(params.get('path', '')) if params.get('path') else None
            return self._json(local_files(p))

        # API: Laptop resource directories
        if path == '/api/laptop/resources':
            return self._json({"dirs": LAPTOP_RESOURCE_DIRS})

        # API: Remote proxy
        if path.startswith('/api/proxy/'):
            parts = path[len('/api/proxy/'):].split('/', 1)
            system_id = parts[0]
            api_path = '/' + parts[1] if len(parts) > 1 else '/'
            if '?' in self.path:
                api_path += '?' + self.path.split('?', 1)[1].split('/', 1)[-1] if '/' in self.path.split('?', 1)[1] else ''
            return self._json(proxy_request(system_id, api_path))

        # API: Systems list
        if path == '/api/systems':
            return self._json([{"id": s["id"], "name": s["name"], "port": s.get("port"),
                               "icon": s.get("icon", ""), "dir": s.get("dir")} for s in SYSTEMS])

        # API: AGI summary (智能体系感知)
        if path == '/api/agi':
            return self._json(get_agi_summary())

        # API: EventBus - history
        if path == '/api/events/history':
            limit = int(params.get('limit', 50))
            source = unquote(params['source']) if 'source' in params else None
            etype = unquote(params['type']) if 'type' in params else None
            return self._json(event_bus.history(limit, source, etype))

        # API: EventBus - SSE stream
        if path == '/api/events/stream':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            q = event_bus.subscribe()
            try:
                while True:
                    try:
                        event = q.get(timeout=30)
                        data = json.dumps(event, ensure_ascii=False)
                        self.wfile.write(f"data: {data}\n\n".encode('utf-8'))
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                event_bus.unsubscribe(q)
            return

        # API: Health check (quick)
        if path == '/api/health':
            states = health_check_once()
            running = sum(1 for v in states.values() if v == 'running')
            total = sum(1 for v in states.values() if v != 'no_port')
            return self._json({"status": "ok", "running": running, "total": total,
                               "states": states, "events": event_bus.history(10)})

        self._json({"error": "not found", "path": path}, 404)

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len).decode('utf-8') if content_len else '{}'
        try:
            data = json.loads(body)
        except:
            data = {}

        path = self.path.split('?')[0]

        if path == '/api/local/click':
            return self._json(local_click(data.get('x', 0), data.get('y', 0)))
        if path == '/api/local/key':
            return self._json(local_key(data.get('key', '')))
        if path == '/api/local/type':
            return self._json(local_type_text(data.get('text', '')))
        if path == '/api/local/shell':
            return self._json(local_shell(data.get('cmd', ''), data.get('timeout', 15)))
        if path == '/api/local/scroll':
            return self._json(local_scroll(data.get('x', 0), data.get('y', 0), data.get('clicks', 3)))
        if path == '/api/local/move':
            return self._json(local_move(data.get('x', 0), data.get('y', 0)))
        if path == '/api/local/drag':
            return self._json(local_drag(data.get('x1', 0), data.get('y1', 0),
                                         data.get('x2', 0), data.get('y2', 0),
                                         data.get('duration', 0.5)))

        # POST proxy (forward POST body to remote system)
        if path.startswith('/api/proxy/'):
            parts = path[len('/api/proxy/'):].split('/', 1)
            system_id = parts[0]
            api_path = '/' + parts[1] if len(parts) > 1 else '/'
            return self._json(proxy_request(system_id, api_path, timeout=10, method='POST', post_data=body))

        # POST: Publish event
        if path == '/api/events/publish':
            return self._json(event_bus.publish(
                data.get('source', 'external'),
                data.get('type', 'custom'),
                data.get('data', {}),
                data.get('level', 'info')))

        # POST: Dispatch action to subsystem
        if path == '/api/dispatch':
            return self._json(dispatch_action(
                data.get('target', ''),
                data.get('action', '/'),
                data.get('method', 'GET'),
                data.get('params')))

        # POST: Send alert
        if path == '/api/alert':
            msg = data.get('message', '')
            if msg:
                try_alert(msg)
                return self._json({"ok": True, "message": msg})
            return self._json({"error": "no message"}, 400)

        self._json({"error": "not found"}, 404)

def main():
    port = HUB_PORT
    for i, arg in enumerate(sys.argv):
        if arg == '--port' and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])

    class ThreadedServer(http.server.ThreadingHTTPServer):
        daemon_threads = True
    server = ThreadedServer(('127.0.0.1', port), HubHandler)

    # Start health monitor background thread
    monitor = threading.Thread(target=_health_monitor_loop, daemon=True)
    monitor.start()

    print(f"{'=' * 50}")
    print(f"  太极中枢 v3.0 (事件总线 + 统一告警 + 跨模块调度)")
    print(f"  http://127.0.0.1:{port}")
    print(f"  主机: {platform.node()}")
    print(f"  能力: psutil={HAS_PSUTIL} PIL={HAS_PIL} pyautogui={HAS_PYAUTOGUI} OCR={HAS_OCR}")
    print(f"  事件总线: /api/events/stream (SSE)")
    print(f"  健康监控: 30s周期, 状态变化自动告警")
    print(f"{'=' * 50}")

    if '--no-browser' not in sys.argv:
        import webbrowser
        webbrowser.open(f'http://127.0.0.1:{port}')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n中枢已停止")
        server.server_close()

if __name__ == '__main__':
    main()
