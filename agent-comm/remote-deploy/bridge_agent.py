#!/usr/bin/env python3
"""
bridge_agent.py — Multi-Agent Communication Client

Connects to the Dashboard HTTP API, enabling one Agent to interact with a
human operator (or another Agent) through a centralized web console.

Modes:
  --ask      : Post a request and block until a human responds (worker Agent)
  --poll     : Check for pending requests (supervisor Agent)
  --respond  : Reply to a pending request (supervisor Agent)
  --notify   : Non-blocking status report (fire-and-forget)
  --health   : Check dashboard availability
  --statuses : Get all agent statuses

Configuration is loaded from config.json next to this script's parent directory.
All requests include an auth token from config for basic security.
"""

import sys
import json
import os
import time
import subprocess
import urllib.request
import urllib.error
import uuid
import datetime
import argparse

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")

_config_cache = None


def _load_config():
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        _config_cache = {}
        _safe_output(f"[bridge] WARNING: config.json not found or invalid ({e}), using defaults")
    return _config_cache


def _cfg(section, key, default=None):
    cfg = _load_config()
    return cfg.get(section, {}).get(key, default)


def _dashboard_url():
    host = _cfg("dashboard", "connect_host", None) or _cfg("dashboard", "bind_host", None) or _cfg("dashboard", "host", "127.0.0.1")
    if host == "0.0.0.0":
        host = "127.0.0.1"
    port = _cfg("dashboard", "port", 9901)
    return f"http://{host}:{port}"


def _auth_token():
    return _cfg("dashboard", "auth_token", "")


def _timeout():
    return _cfg("bridge", "timeout_seconds", 86400)


def _auto_continue():
    return _cfg("bridge", "auto_continue_message", "继续")


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _safe_output(text):
    """UTF-8 safe output for Windows terminals."""
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
    except Exception:
        print(text)


def _auth_headers():
    """Return dict with auth token header if configured."""
    token = _auth_token()
    if token:
        return {"X-Auth-Token": token}
    return {}


def _http_get(path, timeout=5):
    try:
        headers = {"Accept": "application/json", **_auth_headers()}
        req = urllib.request.Request(f"{_dashboard_url()}{path}", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def _http_post(path, data, timeout=None):
    try:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json", **_auth_headers()}
        req = urllib.request.Request(
            f"{_dashboard_url()}{path}", data=body, headers=headers, method="POST"
        )
        t = timeout or 5
        with urllib.request.urlopen(req, timeout=t) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def _log_call(action, message):
    """Write diagnostic log to data directory."""
    try:
        log_rel = _cfg("bridge", "log_file", "data/bridge-called.log")
        log_path = os.path.join(PROJECT_DIR, log_rel)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {action}: {message[:200]}\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Dashboard auto-start
# ---------------------------------------------------------------------------

def ensure_dashboard():
    """Ensure dashboard server is running. Auto-start if not."""
    health = _http_get("/api/health", timeout=2)
    if "error" not in health:
        return True

    _safe_output("[bridge] Dashboard not running, starting...")
    dashboard_rel = _cfg("paths", "dashboard_script", "core/dashboard.py")
    dashboard_path = os.path.join(PROJECT_DIR, dashboard_rel)

    if not os.path.exists(dashboard_path):
        _safe_output(f"[bridge] ERROR: Dashboard script not found: {dashboard_path}")
        return False

    try:
        if sys.platform == "win32":
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            DETACHED_PROCESS = 0x00000008
            subprocess.Popen(
                [sys.executable, dashboard_path],
                creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                [sys.executable, dashboard_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        for _ in range(20):
            time.sleep(0.5)
            health = _http_get("/api/health", timeout=2)
            if "error" not in health:
                _safe_output(f"[bridge] Dashboard started on {_dashboard_url()}")
                return True

        _safe_output("[bridge] ERROR: Dashboard failed to start within 10s")
        return False
    except Exception as e:
        _safe_output(f"[bridge] ERROR starting dashboard: {e}")
        return False


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_health():
    health = _http_get("/api/health")
    if "error" in health:
        _safe_output(json.dumps({"status": "offline", "error": health["error"]}))
    else:
        _safe_output(json.dumps(health))


def cmd_poll():
    pending = _http_get("/api/pending")
    if "error" in pending:
        _safe_output(json.dumps({"error": pending["error"], "hint": "Dashboard may not be running."}))
        return

    if not pending:
        _safe_output(json.dumps({"pending_count": 0, "requests": []}))
        return

    requests = []
    for req_id, data in pending.items():
        requests.append({
            "request_id": req_id,
            "source": data.get("project", "unknown"),
            "message": data.get("message", ""),
            "options": data.get("options", []),
            "age_seconds": int(time.time() - data.get("timestamp", time.time())),
        })

    _safe_output(json.dumps({"pending_count": len(requests), "requests": requests}, ensure_ascii=False))


def cmd_respond(request_id, message, selected_options=None):
    data = {"user_input": message, "selected_options": selected_options or []}
    result = _http_post(f"/api/respond/{request_id}", data)
    _safe_output(json.dumps(result))


def cmd_notify(message, source="unknown", phase="working", progress=""):
    _log_call("NOTIFY", message)
    if not ensure_dashboard():
        _safe_output(json.dumps({"status": "dashboard_unavailable"}))
        return
    result = _http_post("/api/status", {
        "project": source, "task": message, "phase": phase,
        "progress": progress, "level": "notify",
    })
    _safe_output(json.dumps({"status": "posted", **result}))


def cmd_ask(message, options=None, source="unknown", timeout=None):
    if timeout is None:
        timeout = _timeout()
    _log_call("ASK", message)

    if not ensure_dashboard():
        _safe_output(json.dumps({
            "user_input": None, "selected_options": [], "cancelled": True,
            "metadata": {"error": "dashboard_unavailable"}
        }))
        return

    # Auto-log this interaction to the activity feed
    _http_post("/api/activity", {
        "source": source, "type": "request",
        "message": f"Agent reply: {message[:200]}",
        "details": ", ".join(options or []),
    })

    request_id = str(uuid.uuid4())[:8]
    post_result = _http_post("/api/request", {
        "request_id": request_id, "project": source,
        "message": message, "options": options or [],
    })

    if "error" in post_result:
        _safe_output(json.dumps({
            "user_input": None, "selected_options": [], "cancelled": True,
            "metadata": {"error": post_result["error"]}
        }))
        return

    _safe_output(f"[bridge] Request {request_id} posted. Waiting up to {timeout}s...")
    headers = {"Accept": "application/json", **_auth_headers()}
    start_time = time.time()
    poll_chunk = 300  # Match server-side max_poll_timeout

    while True:
        elapsed = time.time() - start_time
        remaining = timeout - elapsed
        if remaining <= 0:
            break
        chunk = min(int(remaining), poll_chunk)
        try:
            req = urllib.request.Request(
                f"{_dashboard_url()}/api/wait/{request_id}?timeout={chunk}",
                headers=headers
            )
            with urllib.request.urlopen(req, timeout=chunk + 30) as resp:
                response = json.loads(resp.read().decode("utf-8"))
                if response.get("cancelled") and response.get("metadata", {}).get("error") == "timeout":
                    continue  # Server-side timeout, retry if total timeout not reached
                _safe_output(json.dumps(response, ensure_ascii=False))
                return
        except urllib.error.URLError:
            time.sleep(2)
            continue
        except Exception as e:
            _safe_output(json.dumps({
                "user_input": _auto_continue(), "selected_options": [],
                "cancelled": False,
                "metadata": {"source": "auto-continue", "error": str(e)}
            }))
            return

    _safe_output(json.dumps({
        "user_input": _auto_continue(), "selected_options": [],
        "cancelled": False,
        "metadata": {"source": "auto-continue", "timeout": timeout}
    }))


def cmd_statuses():
    statuses = _http_get("/api/statuses")
    _safe_output(json.dumps(statuses, ensure_ascii=False))


def cmd_activity(message, source="unknown", activity_type="info", details=""):
    _log_call("ACTIVITY", message)
    if not ensure_dashboard():
        return
    result = _http_post("/api/activity", {
        "source": source, "type": activity_type,
        "message": message, "details": details,
    })
    _safe_output(json.dumps(result))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Communication Client")
    parser.add_argument("--health", action="store_true", help="Check dashboard health")
    parser.add_argument("--poll", action="store_true", help="Poll for pending requests")
    parser.add_argument("--respond", metavar="REQ_ID", help="Respond to a pending request")
    parser.add_argument("--ask", action="store_true", help="Send request and wait for response")
    parser.add_argument("--notify", action="store_true", help="Non-blocking status report")
    parser.add_argument("--statuses", action="store_true", help="Get all agent statuses")
    parser.add_argument("--activity", action="store_true", help="Report activity (edit/command/build)")
    parser.add_argument("--type", default="info", help="Activity type: edit/command/build/error/info")
    parser.add_argument("--details", default="")
    parser.add_argument("--phase", default="working")
    parser.add_argument("--progress", default="")
    parser.add_argument("--message", "-m", default="")
    parser.add_argument("--options", "-o", default="")
    parser.add_argument("--source", "-s", default="unknown")
    parser.add_argument("--timeout", "-t", type=int, default=None)

    args = parser.parse_args()

    if args.health:
        cmd_health()
    elif args.notify:
        cmd_notify(args.message, args.source, args.phase, args.progress)
    elif args.poll:
        cmd_poll()
    elif args.respond:
        opts = [o.strip() for o in args.options.split(",") if o.strip()] if args.options else []
        cmd_respond(args.respond, args.message, opts)
    elif args.ask:
        opts = [o.strip() for o in args.options.split(",") if o.strip()] if args.options else []
        cmd_ask(args.message, opts, args.source, args.timeout)
    elif args.statuses:
        cmd_statuses()
    elif args.activity:
        cmd_activity(args.message, args.source, args.type, args.details)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
