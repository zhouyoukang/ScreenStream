#!/usr/bin/env python3
"""
dashboard.py — Multi-Agent Communication Dashboard

Web-based control console for managing multiple AI Agents. Features:
  - Request/response cards with long-polling
  - Agent status tracking (working/waiting/blocked/idle/offline)
  - Token-based authentication
  - Request persistence to JSON file
  - Sound + system notifications for new requests
  - Drag-and-drop file/image attachments
  - Broadcast commands to all agents
  - Instruction dispatch to specific agents

Usage:
  python dashboard.py                # Start on configured port (default 9901)
  python dashboard.py --port 9902    # Override port
"""

import http.server
import json
import threading
import tempfile
import base64
import time
import os
import sys
import uuid
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")


def _load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


CONFIG = _load_config()
PORT = CONFIG.get("dashboard", {}).get("port", 9901)
HOST = CONFIG.get("dashboard", {}).get("bind_host", None) or CONFIG.get("dashboard", {}).get("host", "0.0.0.0")
AUTH_TOKEN = CONFIG.get("dashboard", {}).get("auth_token", "")
PERSIST_ENABLED = CONFIG.get("persistence", {}).get("enabled", True)
REQUESTS_FILE = os.path.join(PROJECT_DIR, CONFIG.get("persistence", {}).get("requests_file", "data/requests.json"))
AGENTS_FILE = os.path.join(PROJECT_DIR, CONFIG.get("persistence", {}).get("agents_file", "data/agents.json"))
DATA_DIR = os.path.join(PROJECT_DIR, CONFIG.get("paths", {}).get("data_dir", "data"))
PID_FILE = os.path.join(tempfile.gettempdir(), "agent-comm-dashboard.pid")
STATUS_EXPIRY = 1800  # 30 minutes
MAX_POLL_TIMEOUT = CONFIG.get("dashboard", {}).get("max_poll_timeout", 300)


# ---------------------------------------------------------------------------
# Request Store (thread-safe, with persistence)
# ---------------------------------------------------------------------------

class RequestStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.pending = {}       # request_id -> {slot, project, message, options, timestamp}
        self.responses = {}     # request_id -> response JSON
        self.events = {}        # request_id -> threading.Event
        self.history = []       # recent completed interactions (last 50)
        self.statuses = {}      # agent_key -> status dict
        self.activities = []    # real-time activity feed (last 100)

    def add_request(self, request_id, data):
        with self.lock:
            self.pending[request_id] = {**data, "timestamp": time.time()}
            self.events[request_id] = threading.Event()
        self._persist()

    def get_pending(self):
        with self.lock:
            return dict(self.pending)

    def submit_response(self, request_id, response):
        with self.lock:
            req = self.pending.pop(request_id, None)
            self.responses[request_id] = response
            if req:
                self.history.append({
                    "request": req, "response": response,
                    "completed_at": time.time()
                })
                self.history = self.history[-50:]
            evt = self.events.get(request_id)
            if evt:
                evt.set()
        self._persist()

    def wait_for_response(self, request_id, timeout=600):
        evt = self.events.get(request_id)
        if not evt:
            return None
        evt.wait(timeout=timeout)
        with self.lock:
            resp = self.responses.get(request_id)
            if resp is not None:
                self.responses.pop(request_id, None)
                self.events.pop(request_id, None)
            return resp

    def cancel_request(self, request_id):
        with self.lock:
            self.pending.pop(request_id, None)
            self.responses[request_id] = {
                "user_input": None, "selected_options": [],
                "image_paths": [], "attached_files": [],
                "cancelled": True, "metadata": {"source": "dashboard-cancel"}
            }
            evt = self.events.get(request_id)
            if evt:
                evt.set()
        self._persist()

    def update_status(self, agent_key, data):
        with self.lock:
            self.statuses[agent_key] = {
                "project": data.get("project", "unknown"),
                "task": data.get("task", ""),
                "phase": data.get("phase", "working"),
                "progress": data.get("progress", ""),
                "level": data.get("level", "silent"),
                "last_update": time.time(),
            }
        self._save_agents()

    def get_statuses(self):
        now = time.time()
        with self.lock:
            for k, v in self.statuses.items():
                if now - v["last_update"] > STATUS_EXPIRY:
                    v["phase"] = "offline"
            return dict(self.statuses)

    def remove_status(self, agent_key):
        with self.lock:
            self.statuses.pop(agent_key, None)

    def get_history(self):
        with self.lock:
            return list(self.history)

    def add_activity(self, data):
        with self.lock:
            self.activities.append({
                "source": data.get("source", "unknown"),
                "type": data.get("type", "info"),
                "message": data.get("message", ""),
                "details": data.get("details", ""),
                "timestamp": time.time(),
            })
            self.activities = self.activities[-100:]

    def get_activities(self, since=0):
        with self.lock:
            if since:
                return [a for a in self.activities if a["timestamp"] > since]
            return list(self.activities[-50:])

    # --- Persistence ---

    def _persist(self):
        if not PERSIST_ENABLED:
            return
        try:
            os.makedirs(os.path.dirname(REQUESTS_FILE), exist_ok=True)
            with self.lock:
                data = {
                    "pending": {k: v for k, v in self.pending.items()},
                    "history": self.history[-50:],
                    "saved_at": time.time()
                }
            with open(REQUESTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _save_agents(self):
        try:
            os.makedirs(os.path.dirname(AGENTS_FILE), exist_ok=True)
            with self.lock:
                data = {"statuses": dict(self.statuses), "saved_at": time.time()}
            with open(AGENTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_from_disk(self):
        # Load agents
        if os.path.exists(AGENTS_FILE):
            try:
                with open(AGENTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                with self.lock:
                    for k, v in data.get("statuses", {}).items():
                        if k not in self.statuses:
                            v["phase"] = "offline"
                            self.statuses[k] = v
            except Exception:
                pass
        # Load history
        if os.path.exists(REQUESTS_FILE):
            try:
                with open(REQUESTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                with self.lock:
                    self.history = data.get("history", [])[-50:]
            except Exception:
                pass


store = RequestStore()


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------

def _check_auth(handler):
    """Returns True if request is authorized. Sends 401 if not."""
    if not AUTH_TOKEN:
        return True
    # Allow browser access (GET /) without token
    if handler.command == "GET" and urlparse(handler.path).path in ("/", "/index.html"):
        return True
    token = handler.headers.get("X-Auth-Token", "")
    if token == AUTH_TOKEN:
        return True
    # Also check query param for browser-originated API calls
    qs = parse_qs(urlparse(handler.path).query)
    if qs.get("token", [""])[0] == AUTH_TOKEN:
        return True
    handler.send_response(401)
    handler.send_header("Content-Type", "application/json")
    handler.end_headers()
    handler.wfile.write(json.dumps({"error": "unauthorized"}).encode("utf-8"))
    return False


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class DashboardHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length > 0 else b""

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Auth-Token")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path in ("/", "/index.html"):
            self._html(get_dashboard_html())
            return

        if not _check_auth(self):
            return

        if path == "/api/health":
            self._json({"status": "ok", "pending": len(store.pending), "version": "2.0"})

        elif path == "/api/pending":
            self._json(store.get_pending())

        elif path.startswith("/api/wait/"):
            request_id = path.split("/")[-1]
            qs = parse_qs(urlparse(self.path).query)
            timeout = min(int(qs.get("timeout", [str(MAX_POLL_TIMEOUT)])[0]), MAX_POLL_TIMEOUT)
            response = store.wait_for_response(request_id, timeout=timeout)
            if response:
                self._json(response)
            else:
                self._json({
                    "user_input": None, "selected_options": [],
                    "cancelled": True, "metadata": {"error": "timeout"}
                })

        elif path == "/api/statuses":
            self._json(store.get_statuses())

        elif path == "/api/history":
            self._json(store.get_history())

        elif path == "/api/activities":
            qs = parse_qs(urlparse(self.path).query)
            since = float(qs.get("since", ["0"])[0])
            self._json(store.get_activities(since))

        else:
            self.send_error(404)

    def do_POST(self):
        if not _check_auth(self):
            return

        path = urlparse(self.path).path
        body = self._body()

        if path == "/api/request":
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._json({"error": "invalid json"}, 400)
                return
            request_id = data.get("request_id") or str(uuid.uuid4())[:8]
            store.add_request(request_id, {
                "slot": data.get("slot", "1"),
                "project": data.get("project", "unknown"),
                "message": data.get("message", ""),
                "options": data.get("options", []),
            })
            self._json({"request_id": request_id, "status": "pending"})

        elif path.startswith("/api/respond/"):
            request_id = path.split("/")[-1]
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._json({"error": "invalid json"}, 400)
                return

            image_paths = []
            attached_files = []
            temp_dir = os.path.join(tempfile.gettempdir(), "agent-comm-uploads")
            os.makedirs(temp_dir, exist_ok=True)

            for i, img_b64 in enumerate(data.get("images", [])):
                try:
                    img_data = base64.b64decode(img_b64.split(",")[-1])
                    ext = ".png"
                    if img_b64.startswith("data:image/jpeg"):
                        ext = ".jpg"
                    fpath = os.path.join(temp_dir, f"img_{request_id}_{i}{ext}")
                    with open(fpath, "wb") as f:
                        f.write(img_data)
                    image_paths.append(fpath)
                except Exception:
                    pass

            for fobj in data.get("files", []):
                try:
                    fname = fobj.get("name", f"file_{request_id}")
                    fdata = base64.b64decode(fobj.get("data", "").split(",")[-1])
                    fpath = os.path.join(temp_dir, fname)
                    with open(fpath, "wb") as f:
                        f.write(fdata)
                    attached_files.append(fpath)
                except Exception:
                    pass

            response = {
                "user_input": data.get("user_input"),
                "selected_options": data.get("selected_options", []),
                "image_paths": image_paths,
                "attached_files": attached_files,
                "cancelled": False,
                "metadata": {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "source": "dashboard"
                }
            }
            store.submit_response(request_id, response)
            self._json({"status": "ok"})

        elif path.startswith("/api/cancel/"):
            request_id = path.split("/")[-1]
            store.cancel_request(request_id)
            self._json({"status": "cancelled"})

        elif path == "/api/status":
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._json({"error": "invalid json"}, 400)
                return
            agent_key = data.get("agent_key") or f"{data.get('project', '?')}_{data.get('slot', '0')}"
            store.update_status(agent_key, data)
            self._json({"status": "ok", "agent_key": agent_key})

        elif path == "/api/activity":
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._json({"error": "invalid json"}, 400)
                return
            store.add_activity(data)
            self._json({"status": "ok"})

        elif path == "/api/instruct":
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._json({"error": "invalid json"}, 400)
                return
            instruction = data.get("instruction", "")
            target = data.get("target", "agent")
            os.makedirs(DATA_DIR, exist_ok=True)
            fpath = os.path.join(DATA_DIR, f"{target}-input.txt")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(instruction)
            self._json({"status": "ok", "file": fpath, "length": len(instruction)})

        else:
            self.send_error(404)


# Frontend HTML (embedded for zero-dependency deployment)
# ---------------------------------------------------------------------------

def get_dashboard_html():
    html = '''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:#0a0a0f;color:#e0e0e0;height:100vh;display:flex;flex-direction:column}
.header{padding:12px 20px;background:#12121a;border-bottom:1px solid #1e1e2e;display:flex;justify-content:space-between;align-items:center;flex-shrink:0}
.header h1{font-size:15px;color:#888;font-weight:600;letter-spacing:.5px}
.header .right{display:flex;align-items:center;gap:12px}
.conn-dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.conn-dot.online{background:#4ade80;box-shadow:0 0 6px #4ade8066}
.conn-dot.offline{background:#f87171;animation:pulse 1s infinite}
.header .status{font-size:12px;color:#4a9eff}
.status-bar{padding:8px 12px;background:#0e0e14;border-bottom:1px solid #1a1a2a;flex-shrink:0;display:flex;flex-wrap:wrap;gap:6px;min-height:40px;align-items:center}
.status-bar .empty-hint{color:#2a2a3a;font-size:11px;font-style:italic}
.agent-pill{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:6px;font-size:11px;border:1px solid;transition:all .3s;max-width:400px;overflow:hidden;cursor:default}
.agent-pill .dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.agent-pill .name{font-weight:600;white-space:nowrap}
.agent-pill .task{opacity:.7;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.agent-pill .progress{opacity:.5;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px}
.agent-pill .ago{opacity:.4;font-size:10px;white-space:nowrap}
.agent-pill.working{background:#0a1a0a;border-color:#1a3a1a;color:#4ade80}
.agent-pill.working .dot{background:#4ade80;box-shadow:0 0 6px #4ade8066;animation:pulse 2s infinite}
.agent-pill.waiting{background:#1a1a0a;border-color:#3a3a1a;color:#fbbf24}
.agent-pill.waiting .dot{background:#fbbf24}
.agent-pill.blocked{background:#1a0a0a;border-color:#3a1a1a;color:#f87171}
.agent-pill.blocked .dot{background:#f87171;animation:pulse 1s infinite}
.agent-pill.idle{background:#0e0e14;border-color:#2a2a3a;color:#555}
.agent-pill.idle .dot{background:#555}
.agent-pill.offline{background:#0e0e11;border-color:#1a1a22;color:#333}
.agent-pill.offline .dot{background:#333}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.toolbar{padding:8px 12px;display:flex;gap:8px;align-items:center;background:#0e0e18;border-bottom:1px solid #1a1a2a;flex-shrink:0}
.toolbar button{padding:7px 14px;background:#2a3a5a;border:1px solid #3a4a6a;border-radius:7px;color:#a0c0ff;font-size:12px;cursor:pointer;white-space:nowrap}
.toolbar button:hover{background:#3a4a6a;color:#fff}
.toolbar button.primary{background:#4a9eff;border-color:#4a9eff;color:#fff}
.toolbar button.primary:hover{background:#3a8eef}
.toolbar input{flex:1;padding:7px 12px;background:#0c0c16;border:1px solid #2a2a3a;border-radius:7px;color:#e0e0e0;font-size:12px;outline:none}
.toolbar input:focus{border-color:#4a9eff}
.toolbar .sep{width:1px;height:20px;background:#2a2a3a}
.cards{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px}
.empty-state{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;margin-top:15vh;color:#333;font-size:13px;text-align:center;line-height:1.6}
.empty-state .icon{font-size:36px;opacity:.3}
.empty-state .hint{color:#444;font-size:11px}
.card{background:#14141f;border:1px solid #2a2a3a;border-radius:10px;padding:14px 16px;transition:border-color .3s,box-shadow .3s;animation:slideIn .25s ease-out}
@keyframes slideIn{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:translateY(0)}}
.card.active{border-color:#4a9eff;box-shadow:0 0 16px rgba(74,158,255,.12)}
.card-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.card-project{font-size:13px;font-weight:700;color:#4a9eff;background:#1a2540;padding:2px 10px;border-radius:4px}
.card-time{font-size:11px;color:#555}
.card-msg{font-size:14px;line-height:1.55;color:#bbb;white-space:pre-wrap;word-break:break-word;margin-bottom:10px}
.card-options{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:8px}
.opt-btn{padding:6px 16px;background:#1e2a4a;border:1px solid #3a4a6a;border-radius:7px;color:#a0c0ff;font-size:13px;cursor:pointer;transition:all .12s}
.opt-btn:hover{background:#2a3a5a;border-color:#4a9eff;color:#fff}
.card-input{display:flex;gap:7px}
.card-input input{flex:1;padding:8px 12px;background:#0c0c16;border:1px solid #2a2a3a;border-radius:7px;color:#e0e0e0;font-size:13px;outline:none}
.card-input input:focus{border-color:#4a9eff}
.card-input button{padding:8px 16px;background:#4a9eff;border:none;border-radius:7px;color:#fff;font-size:13px;font-weight:600;cursor:pointer}
.card-input button:hover{background:#3a8eef}
.card-attachments{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px}
.card-attachments .thumb{position:relative;width:48px;height:48px;border-radius:6px;overflow:hidden;border:1px solid #2a2a3a}
.card-attachments .thumb img{width:100%;height:100%;object-fit:cover}
.card-attachments .thumb .rm{position:absolute;top:-2px;right:-2px;width:16px;height:16px;background:#f44;color:#fff;border:none;border-radius:50%;font-size:10px;cursor:pointer;line-height:16px;text-align:center}
.card.dragover{border-color:#4a9eff;background:#1a1a30}
.activity-panel{flex-shrink:0;border-top:1px solid #1a1a2a;max-height:200px;overflow-y:auto;padding:8px 12px}
.activity-panel .title{font-size:11px;color:#444;font-weight:600;margin-bottom:4px;display:flex;justify-content:space-between}
.act-item{font-size:11px;padding:3px 8px;margin:2px 0;border-left:2px solid #2a2a3a;color:#555;display:flex;gap:8px;align-items:baseline}
.act-item .time{color:#333;flex-shrink:0;font-size:10px;min-width:55px}
.act-item .src{color:#4a9eff;font-weight:600;flex-shrink:0;min-width:100px}
.act-item .msg{color:#666;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.act-item .detail{color:#444;font-size:10px;opacity:.7}
.act-item.type-edit{border-color:#4ade80}
.act-item.type-command{border-color:#fbbf24}
.act-item.type-error{border-color:#f87171}
.act-item.type-build{border-color:#a78bfa}
.act-item.type-request{border-color:#4a9eff}
#log div{font-size:11px;padding:2px 8px;margin:1px 0;color:#555;border-left:2px solid #3a3a1a}
</style>
</head>
<body>
<div class="header">
  <h1>Agent Dashboard v2.0</h1>
  <div class="right">
    <span class="conn-dot" id="connDot"></span>
    <span class="status" id="status">connecting...</span>
  </div>
</div>
<div class="status-bar" id="statusBar"><span class="empty-hint">connecting...</span></div>
<div class="toolbar" id="toolbar">
  <button class="primary" onclick="respondAll('continue')">全部继续</button>
  <button onclick="respondAll('stop')">全部结束</button>
  <div class="sep"></div>
  <input id="broadcast" placeholder="广播: 输入后按Enter发送给全部Agent..." onkeydown="if(event.key==='Enter'){const v=this.value.trim();if(v){respondAll(v);this.value='';}}">
  <div class="sep"></div>
  <input id="instruct" placeholder="下发指令给Agent..." style="flex:1;" onkeydown="if(event.key==='Enter'){sendInstruction();}">
  <button onclick="sendInstruction()" style="background:#22c55e;border-color:#22c55e;color:#fff;">下发</button>
</div>
<div class="cards" id="cards">
  <div class="empty-state" id="emptyState">
    <div class="icon">&#x1F4E1;</div>
    <div>等待 Agent 连接...</div>
    <div class="hint">Agent 执行任务时会自动出现在这里</div>
  </div>
</div>
<div class="activity-panel" id="actPanel">
  <div class="title"><span>Activity Feed</span><span id="actCount">0 events</span></div>
  <div id="actList"></div>
</div>
<div class="activity-panel" id="logPanel" style="max-height:120px;">
  <div class="title"><span>Local Log</span></div>
  <div id="log"></div>
</div>
<script>
const AUTH_TOKEN = '%%TOKEN%%';
const POLL_INTERVAL = 800;
const STATUS_POLL = 2000;
let known = {};
let isOnline = false;
let lastSoundTime = 0;

function authHeaders() {
  const h = {'Content-Type': 'application/json'};
  if (AUTH_TOKEN) h['X-Auth-Token'] = AUTH_TOKEN;
  return h;
}
function authUrl(url) {
  if (!AUTH_TOKEN) return url;
  return url + (url.includes('?') ? '&' : '?') + 'token=' + AUTH_TOKEN;
}
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function setOnline(online) {
  isOnline = online;
  document.getElementById('connDot').className = 'conn-dot ' + (online ? 'online' : 'offline');
}
function updateEmpty() {
  document.getElementById('emptyState').style.display = Object.keys(known).length > 0 ? 'none' : 'flex';
}
function fmtAgo(s) {
  if (s < 0) s = 0;
  if (s < 60) return Math.round(s) + 's';
  if (s < 3600) return Math.round(s/60) + 'm';
  return Math.round(s/3600) + 'h';
}

function playSound() {
  const now = Date.now();
  if (now - lastSoundTime < 3000) return;
  lastSoundTime = now;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain); gain.connect(ctx.destination);
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.1);
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.3);
  } catch(e) {}
}
function sysNotify(title, body) {
  if (!('Notification' in window)) return;
  if (Notification.permission === 'granted') {
    const n = new Notification(title, {body, requireInteraction: true});
    n.onclick = () => { window.focus(); n.close(); };
  } else if (Notification.permission !== 'denied') {
    Notification.requestPermission();
  }
}
if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission();

let attachments = {};

function addCard(id, d) {
  attachments[id] = {images: [], files: []};
  const c = document.createElement('div');
  c.className = 'card active'; c.id = 'c-' + id;
  const ts = new Date(d.timestamp * 1000).toLocaleTimeString();
  const opts = (d.options||[]).map(o =>
    '<button class="opt-btn" data-rid="'+id+'" data-opt="'+esc(o)+'">'+esc(o)+'</button>'
  ).join('');
  c.innerHTML =
    '<div class="card-top"><span class="card-project">'+esc(d.project||'?')+'</span><span class="card-time">'+ts+'</span></div>' +
    '<div class="card-msg">'+esc(d.message||'')+'</div>' +
    (opts ? '<div class="card-options">'+opts+'</div>' : '') +
    '<div class="card-attachments" id="att-'+id+'"></div>' +
    '<div class="card-input"><input placeholder="输入/粘贴图片/拖拽文件..." id="in-'+id+'"><button id="btn-'+id+'">发送</button></div>';
  document.getElementById('cards').prepend(c);
  c.querySelectorAll('.opt-btn').forEach(b => b.onclick = function() { respond(this.dataset.rid, {selected_options:[this.dataset.opt]}); });
  document.getElementById('btn-'+id).onclick = () => submitCard(id);
  document.getElementById('in-'+id).onkeydown = (e) => { if(e.key==='Enter') submitCard(id); };
  c.ondragover = (e) => { e.preventDefault(); c.classList.add('dragover'); };
  c.ondragleave = () => c.classList.remove('dragover');
  c.ondrop = (e) => {
    e.preventDefault(); c.classList.remove('dragover');
    for (const file of e.dataTransfer.files) {
      const reader = new FileReader();
      if (file.type.startsWith('image/')) {
        reader.onload = () => { attachments[id].images.push(reader.result); renderAtt(id); };
      } else {
        reader.onload = () => { attachments[id].files.push({name: file.name, data: reader.result}); renderAtt(id); };
      }
      reader.readAsDataURL(file);
    }
  };
  setTimeout(() => document.getElementById('in-'+id)?.focus(), 50);
  updateEmpty();
  playSound();
  if (!document.hasFocus()) {
    document.title = '*** NEW REQUEST ***';
    sysNotify('Agent Request', d.message || 'New request from ' + (d.project||'Agent'));
  }
}

function renderAtt(id) {
  const el = document.getElementById('att-'+id);
  if (!el) return;
  const att = attachments[id];
  el.innerHTML = '';
  att.images.forEach((src, i) => {
    const d = document.createElement('div'); d.className = 'thumb';
    d.innerHTML = '<img src="'+src+'"><button class="rm" onclick="rmAtt(&#39;'+id+'&#39;,&#39;img&#39;,'+i+')">x</button>';
    el.appendChild(d);
  });
  att.files.forEach((f, i) => {
    const d = document.createElement('div'); d.className = 'thumb';
    d.innerHTML = '<span style="font-size:9px;color:#888;padding:2px">'+esc(f.name)+'</span><button class="rm" onclick="rmAtt(&#39;'+id+'&#39;,&#39;file&#39;,'+i+')">x</button>';
    d.style.background = '#1a1a2e';
    el.appendChild(d);
  });
}

function rmAtt(id, type, idx) {
  if (type === 'img') attachments[id].images.splice(idx, 1);
  else attachments[id].files.splice(idx, 1);
  renderAtt(id);
}

function submitCard(id) {
  const inp = document.getElementById('in-'+id);
  const text = inp?.value?.trim();
  const att = attachments[id] || {images:[], files:[]};
  if (!text && !att.images.length && !att.files.length) return;
  const data = {user_input: text || ''};
  if (att.images.length) data.images = att.images;
  if (att.files.length) data.files = att.files;
  respond(id, data);
}

function sendInstruction() {
  const inp = document.getElementById('instruct');
  const text = inp?.value?.trim();
  if (!text) return;
  inp.value = '';
  inp.style.borderColor = '#22c55e';
  setTimeout(() => inp.style.borderColor = '', 1500);
  fetch('/api/instruct', {method:'POST', headers:authHeaders(), body:JSON.stringify({instruction: text, target: 'agent'})})
  .then(r => r.json())
  .then(d => {
    if (d.status === 'ok') addLog('INSTRUCT: ' + text.substring(0,50));
  });
}

function respond(id, data) {
  fetch('/api/respond/'+id, {method:'POST', headers:authHeaders(), body:JSON.stringify(data)})
  .then(() => {
    const el = document.getElementById('c-'+id);
    if (el) el.remove();
    delete known[id]; delete attachments[id];
    const proj = data.user_input ? '-> '+data.user_input.substring(0,30) : '-> ['+((data.selected_options||[])[0]||'')+']';
    addLog(id + ' ' + proj);
    updateEmpty();
  });
}

function respondAll(text) {
  const ids = Object.keys(known);
  if (!ids.length) return;
  addLog('BROADCAST: ' + text.substring(0,40) + ' (' + ids.length + ' agents)');
  const snapshot = [...ids];
  snapshot.forEach(id => respond(id, {user_input: text}));
}

function addLog(msg) {
  const list = document.getElementById('actList');
  if (!list) return;
  const d = document.createElement('div');
  d.className = 'act-item type-info';
  const t = new Date().toLocaleTimeString();
  d.innerHTML = '<span class="time">' + t + '</span><span class="src">Dashboard</span><span class="msg">' + esc(msg) + '</span>';
  list.prepend(d);
  while (list.children.length > 50) list.lastChild.remove();
  const count = document.getElementById('actCount');
  if (count) count.textContent = list.children.length + ' events';
}

async function poll() {
  try {
    const r = await fetch(authUrl('/api/pending'));
    if (r.status === 401) {
      setOnline(false);
      document.getElementById('status').textContent = 'AUTH FAILED';
      document.getElementById('emptyState').innerHTML = '<div class="icon">&#x1F512;</div><div>Token认证失败</div><div class="hint">请检查 config.json 中的 auth_token</div>';
      return;
    }
    const pending = await r.json();
    if (pending.error) {
      setOnline(false);
      document.getElementById('status').textContent = 'error: ' + pending.error;
      return;
    }
    setOnline(true);
    const ids = new Set(Object.keys(pending));
    for (const [id, data] of Object.entries(pending)) {
      if (!known[id]) { known[id] = true; addCard(id, data); }
    }
    for (const id of Object.keys(known)) {
      if (!ids.has(id)) { const el = document.getElementById('c-'+id); if(el) el.remove(); delete known[id]; }
    }
    const n = ids.size;
    document.getElementById('status').textContent = n ? n + ' pending' : 'connected';
    if (n === 0 && document.title !== 'Agent Dashboard') document.title = 'Agent Dashboard';
    updateEmpty();
  } catch(e) {
    setOnline(false);
    document.getElementById('status').textContent = 'offline - ' + e.message;
  }
}

async function pollStatuses() {
  try {
    const r = await fetch(authUrl('/api/statuses'));
    const statuses = await r.json();
    const bar = document.getElementById('statusBar');
    const keys = Object.keys(statuses);
    if (!keys.length) {
      bar.innerHTML = '<span class="empty-hint">暂无 Agent 上报状态</span>';
      return;
    }
    const now = Date.now() / 1000;
    bar.innerHTML = keys.map(k => {
      const s = statuses[k];
      const phase = s.phase || 'idle';
      const ago = fmtAgo(Math.round(now - s.last_update));
      const prog = s.progress ? '<span class="progress">' + esc(s.progress) + '</span>' : '';
      return '<div class="agent-pill ' + esc(phase) + '" title="' + esc(s.task||'') + '">' +
        '<span class="dot"></span>' +
        '<span class="name">' + esc(s.project||k) + '</span>' +
        '<span class="task">' + esc(s.task||'') + '</span>' +
        prog +
        '<span class="ago">' + ago + '</span>' +
      '</div>';
    }).join('');
  } catch(e) {}
}

window.addEventListener('focus', () => { document.title = 'Agent Dashboard'; });

document.addEventListener('paste', (e) => {
  const items = e.clipboardData?.items;
  if (!items) return;
  const firstId = Object.keys(known)[0];
  if (!firstId) return;
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      e.preventDefault();
      const file = item.getAsFile();
      const reader = new FileReader();
      reader.onload = () => {
        if (!attachments[firstId]) attachments[firstId] = {images:[], files:[]};
        attachments[firstId].images.push(reader.result);
        renderAtt(firstId);
      };
      reader.readAsDataURL(file);
    }
  }
});

let lastActTime = 0;
async function pollActivities() {
  try {
    const r = await fetch(authUrl('/api/activities?since=' + lastActTime));
    if (r.status !== 200) return;
    const acts = await r.json();
    if (!acts.length) return;
    const list = document.getElementById('actList');
    const count = document.getElementById('actCount');
    acts.forEach(a => {
      if (a.timestamp > lastActTime) lastActTime = a.timestamp;
      const d = document.createElement('div');
      d.className = 'act-item type-' + (a.type || 'info');
      const t = new Date(a.timestamp * 1000).toLocaleTimeString();
      const detail = a.details ? ' <span class="detail">' + esc(a.details).substring(0,80) + '</span>' : '';
      d.innerHTML = '<span class="time">' + t + '</span><span class="src">' + esc(a.source) + '</span><span class="msg">' + esc(a.message) + detail + '</span>';
      list.prepend(d);
    });
    while (list.children.length > 50) list.lastChild.remove();
    count.textContent = list.children.length + ' events';
  } catch(e) {}
}

setInterval(poll, POLL_INTERVAL);
setInterval(pollStatuses, STATUS_POLL);
setInterval(pollActivities, 1500);
poll();
pollStatuses();
pollActivities();
</script>
</body>
</html>'''
    return html.replace('%%TOKEN%%', AUTH_TOKEN)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _write_pid():
    try:
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass


def _remove_pid():
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except OSError:
        pass


def _is_port_in_use(host, port):
    """Check if another Dashboard instance is already running."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect((host if host != "0.0.0.0" else "127.0.0.1", port))
            return True
    except (ConnectionRefusedError, OSError, socket.timeout):
        return False


def main():
    port = PORT
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    if _is_port_in_use(HOST, port):
        print(f"Dashboard already running on port {port}. Exiting.")
        sys.exit(0)

    _write_pid()
    store.load_from_disk()
    os.makedirs(DATA_DIR, exist_ok=True)

    server = ThreadingHTTPServer((HOST, port), DashboardHandler)
    auth_info = f" (auth: {'enabled' if AUTH_TOKEN else 'disabled'})"
    print(f"Agent Dashboard v2.0 running at http://{HOST}:{port}{auth_info}")
    print(f"Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
    finally:
        _remove_pid()


if __name__ == "__main__":
    main()
