#!/usr/bin/env python3
"""
AI Vision Bridge Server v2.1
HTTP Bridge for cross-agent frame sharing & observability.
v2.1: File-based state persistence + auto-heartbeat + graceful shutdown.

Architecture:
  Browser (index.html)
    ├─ Path 1: MediaRecorder → .webm (B站素材)
    └─ Path 2: Canvas frames → POST /api/frame → server.py

  server.py (port 9902)
    ├─ GET  /                     → Dashboard (index.html)
    ├─ POST /api/frame            → Receive frame from browser
    ├─ GET  /api/frame/latest     → Serve latest frame (any agent)
    ├─ GET  /api/frame/latest.jpg → Raw JPEG (for AI vision APIs)
    ├─ POST /api/agent/heartbeat  → Agent check-in
    ├─ GET  /api/agents           → All agent statuses
    ├─ GET  /api/cunzhi           → Proxy cunzhi status (9901)
    └─ GET  /api/status           → Server health + stats

  Agent A (any process)
    └─ GET http://localhost:9902/api/frame/latest → sees user's screen
    └─ POST /api/agent/heartbeat → reports its status
"""

import http.server
import json
import time
import base64
import threading
import urllib.request
import urllib.error
import signal
import atexit
from pathlib import Path
import sys
import os

PORT = 9902
STATIC_DIR = Path(__file__).parent
MAX_FRAMES = 20
CUNZHI_URL = "http://127.0.0.1:9901"
STATE_FILE = STATIC_DIR / ".bridge-state.json"
AUTO_SAVE_INTERVAL = 10  # seconds
SERVER_HEARTBEAT_INTERVAL = 15  # seconds

# === State (persisted to disk) ===
state = {
    "frames": [],           # [{id, timestamp, data_b64, width, height, size}] — in-memory only
    "frame_count": 0,
    "agents": {},           # {name: {name, role, task, status, last_heartbeat, messages[]}}
    "start_time": time.time(),
    "last_frame_time": None,
}
state_lock = threading.Lock()
_shutdown_event = threading.Event()


def load_state():
    """Load persistent state from disk. Frames are NOT persisted (ephemeral)."""
    if not STATE_FILE.exists():
        return
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        with state_lock:
            state["agents"] = saved.get("agents", {})
            state["frame_count"] = saved.get("frame_count", 0)
            # Restore start_time only if it was saved
            if "start_time" in saved:
                state["start_time"] = saved["start_time"]
        print(f"[state] Loaded {len(state['agents'])} agents from {STATE_FILE.name}")
    except Exception as e:
        print(f"[state] Failed to load: {e}")


def save_state():
    """Persist agents + counters to disk. Frames excluded (too large)."""
    try:
        with state_lock:
            to_save = {
                "agents": state["agents"],
                "frame_count": state["frame_count"],
                "start_time": state["start_time"],
                "saved_at": time.time(),
                "saved_at_human": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(to_save, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[state] Failed to save: {e}")


def _auto_save_loop():
    """Background thread: periodic save + server self-heartbeat."""
    tick = 0
    while not _shutdown_event.is_set():
        _shutdown_event.wait(1)
        tick += 1
        # Server self-heartbeat
        if tick % SERVER_HEARTBEAT_INTERVAL == 0:
            with state_lock:
                srv = state["agents"].get("VisionBridge-Server")
                if srv:
                    srv["last_heartbeat"] = time.time()
                    srv["status"] = "working"
        # Auto-save
        if tick % AUTO_SAVE_INTERVAL == 0:
            save_state()


class BridgeHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler with frame & agent APIs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self):
        # CORS headers for browser access
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/" or path == "/index.html":
            return super().do_GET()

        if path == "/api/status":
            return self._json_response(self._get_status())

        if path == "/api/frame/latest":
            return self._serve_latest_frame_json()

        if path == "/api/frame/latest.jpg":
            return self._serve_latest_frame_jpeg()

        if path == "/api/agents":
            return self._json_response(self._get_agents())

        if path == "/api/cunzhi":
            return self._proxy_cunzhi()

        # Static files
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?")[0]
        body = self._read_body()

        if path == "/api/frame":
            return self._receive_frame(body)

        if path == "/api/agent/heartbeat":
            return self._agent_heartbeat(body)

        self.send_error(404, "Not Found")

    # === Frame APIs ===

    def _receive_frame(self, body):
        """Receive a frame from browser or capture script."""
        try:
            data = json.loads(body)
            data_url = data.get("dataUrl", "")
            # Extract base64 from data URL
            if "," in data_url:
                b64 = data_url.split(",", 1)[1]
            else:
                b64 = data_url

            with state_lock:
                state["frame_count"] += 1
                frame = {
                    "id": state["frame_count"],
                    "timestamp": time.strftime("%H:%M:%S"),
                    "epoch": time.time(),
                    "data_b64": b64,
                    "width": data.get("width", 0),
                    "height": data.get("height", 0),
                    "size": len(b64) * 3 // 4,  # approximate decoded size
                }
                state["frames"].insert(0, frame)
                if len(state["frames"]) > MAX_FRAMES:
                    state["frames"].pop()
                state["last_frame_time"] = time.time()

            self._json_response({"ok": True, "id": frame["id"]})
        except Exception as e:
            self._json_response({"ok": False, "error": str(e)}, status=400)

    def _serve_latest_frame_json(self):
        """Return latest frame as JSON with base64 data."""
        with state_lock:
            if not state["frames"]:
                return self._json_response({"ok": False, "error": "No frames yet"}, status=404)
            frame = state["frames"][0]
            return self._json_response({
                "ok": True,
                "id": frame["id"],
                "timestamp": frame["timestamp"],
                "epoch": frame["epoch"],
                "width": frame["width"],
                "height": frame["height"],
                "size": frame["size"],
                "dataUrl": f"data:image/jpeg;base64,{frame['data_b64']}",
                "age_seconds": round(time.time() - frame["epoch"], 1),
            })

    def _serve_latest_frame_jpeg(self):
        """Return latest frame as raw JPEG binary (for vision APIs)."""
        with state_lock:
            if not state["frames"]:
                self.send_error(404, "No frames")
                return
            b64 = state["frames"][0]["data_b64"]

        try:
            img_bytes = base64.b64decode(b64)
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(img_bytes)))
            self.end_headers()
            self.wfile.write(img_bytes)
        except Exception as e:
            self.send_error(500, str(e))

    # === Agent APIs ===

    def _agent_heartbeat(self, body):
        """Register or update an agent's status."""
        try:
            data = json.loads(body)
            name = data.get("name", "unknown")
            with state_lock:
                if name not in state["agents"]:
                    state["agents"][name] = {
                        "name": name,
                        "start_time": time.time(),
                        "messages": [],
                    }
                agent = state["agents"][name]
                agent["role"] = data.get("role", agent.get("role", "agent"))
                agent["task"] = data.get("task", agent.get("task", ""))
                agent["status"] = data.get("status", "working")
                agent["last_heartbeat"] = time.time()
                # Append message if provided
                msg = data.get("message")
                if msg:
                    agent["messages"].append({
                        "time": time.strftime("%H:%M:%S"),
                        "epoch": time.time(),
                        "text": msg,
                        "type": data.get("msg_type", "info"),
                    })
                    if len(agent["messages"]) > 50:
                        agent["messages"] = agent["messages"][-50:]

            # Trigger save after agent change
            save_state()
            self._json_response({"ok": True})
        except Exception as e:
            self._json_response({"ok": False, "error": str(e)}, status=400)

    def _get_agents(self):
        """Return all agents with computed state."""
        with state_lock:
            result = {}
            now = time.time()
            for name, agent in state["agents"].items():
                elapsed = now - agent["last_heartbeat"]
                if elapsed < 30:
                    computed_state = "active"
                elif elapsed < 120:
                    computed_state = "stale"
                else:
                    computed_state = "dead"
                result[name] = {
                    **agent,
                    "elapsed_seconds": round(elapsed, 1),
                    "computed_state": computed_state,
                    "uptime": round(now - agent["start_time"], 1),
                }
            return {"ok": True, "agents": result, "count": len(result)}

    # === Cunzhi Proxy ===

    def _proxy_cunzhi(self):
        """Proxy cunzhi dashboard API to avoid CORS issues."""
        try:
            req = urllib.request.Request(
                f"{CUNZHI_URL}/api/status",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode())
                return self._json_response({"ok": True, "cunzhi": data})
        except urllib.error.URLError:
            return self._json_response({"ok": False, "error": "cunzhi not reachable"})
        except Exception as e:
            return self._json_response({"ok": False, "error": str(e)})

    # === Status ===

    def _get_status(self):
        with state_lock:
            now = time.time()
            return {
                "ok": True,
                "server": "AI Vision Bridge v2.1",
                "port": PORT,
                "uptime": round(now - state["start_time"], 1),
                "frame_count": state["frame_count"],
                "last_frame_age": round(now - state["last_frame_time"], 1) if state["last_frame_time"] else None,
                "agent_count": len(state["agents"]),
                "agents": list(state["agents"].keys()),
            }

    # === Helpers ===

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Quieter logging
        if "/api/frame" not in (args[0] if args else ""):
            super().log_message(format, *args)


def main():
    port = PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    # Load persisted state first
    load_state()

    # Register/update server as an agent (preserves history from loaded state)
    with state_lock:
        srv = state["agents"].get("VisionBridge-Server", {
            "name": "VisionBridge-Server",
            "start_time": time.time(),
            "messages": [],
        })
        srv["role"] = "infrastructure"
        srv["task"] = f"HTTP Bridge on port {port}"
        srv["status"] = "working"
        srv["last_heartbeat"] = time.time()
        srv["messages"].append({
            "time": time.strftime("%H:%M:%S"),
            "epoch": time.time(),
            "text": f"Server (re)started on port {port}",
            "type": "success",
        })
        if len(srv["messages"]) > 50:
            srv["messages"] = srv["messages"][-50:]
        state["agents"]["VisionBridge-Server"] = srv

    # Start background auto-save + self-heartbeat thread
    bg_thread = threading.Thread(target=_auto_save_loop, daemon=True)
    bg_thread.start()

    # Graceful shutdown: save state
    def _shutdown_handler(*args):
        print("\n[shutdown] Saving state...")
        with state_lock:
            srv = state["agents"].get("VisionBridge-Server")
            if srv:
                srv["status"] = "stopped"
                srv["last_heartbeat"] = time.time()
                srv["messages"].append({
                    "time": time.strftime("%H:%M:%S"),
                    "epoch": time.time(),
                    "text": "Server shutting down gracefully",
                    "type": "warn",
                })
        save_state()
        _shutdown_event.set()
        print("[shutdown] State saved. Goodbye.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)
    atexit.register(save_state)

    # Initial save
    save_state()

    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), BridgeHandler)
    print(f"""
╔══════════════════════════════════════════════════╗
║       AI Vision Bridge Server v2.1               ║
║       Persistent State + Auto-Heartbeat          ║
╠══════════════════════════════════════════════════╣
║  Dashboard:  http://localhost:{port}              ║
║  Frame API:  http://localhost:{port}/api/frame    ║
║  Agent API:  http://localhost:{port}/api/agents   ║
║  Raw JPEG:   http://localhost:{port}/api/frame/latest.jpg ║
║  State:      {STATE_FILE.name:40s}  ║
╚══════════════════════════════════════════════════╝
""")
    server.serve_forever()


if __name__ == "__main__":
    main()
