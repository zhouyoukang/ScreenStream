#!/usr/bin/env python3
"""
RayNeo V3 管理中枢 — 统一管理服务器
道生一，一生二，二生三，三生万物

HTTP端口: 8800 (Dashboard UI + REST API)
WS端口:   8801 (实时推送)

用法:
  python rayneo_dashboard.py          # 启动管理中枢
  python rayneo_dashboard.py --port 8800
"""

import asyncio
import json
import time
import threading
import os
import sys
import subprocess
import re
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import urllib.request

try:
    import websockets
    import websockets.server
except ImportError:
    print("❌ 需要安装 websockets: pip install websockets")
    sys.exit(1)

_PROJECT_DIR = Path(__file__).resolve().parent

# ─── ADB 工具（统一由wireless_config管理） ───────────────────
sys.path.insert(0, str(_PROJECT_DIR))
from wireless_config import wm, ADB
from wireless_config import PHONE_USB_SERIAL, _adb_device_state

def adb_cmd(device: str, *args) -> str:
    try:
        r = subprocess.run([ADB, "-s", device] + list(args),
                           capture_output=True, text=True, timeout=8)
        return r.stdout.strip()
    except Exception:
        return ""


# ─── 系统状态采集 ──────────────────────────────────────────
class SystemState:
    """全系统状态快照"""

    def __init__(self):
        self._lock = threading.Lock()
        self.glasses_id = ""
        self.glasses_online = False
        self.glasses_battery = -1
        self.glasses_worn = False
        self.glasses_light = 0.0
        self.glasses_model = "XRGF50"

        self.phone_id = ""
        self.phone_online = False
        self.phone_battery = -1
        self.phone_ip = wm.phone_ip
        self.phone_brain_online = False
        self.phone_fg_app = ""

        self.pc_name = os.environ.get("COMPUTERNAME", "PC")

        self.five_senses_running = False
        self.dao_engine_running = False
        self.san_lian_running = False

        self.events = []
        self.last_update = 0

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "glasses": {
                    "id": self.glasses_id,
                    "online": self.glasses_online,
                    "battery": self.glasses_battery,
                    "worn": self.glasses_worn,
                    "light": self.glasses_light,
                    "model": self.glasses_model,
                    "connection": "WiFi" if ":" in self.glasses_id else "USB" if self.glasses_id else "离线",
                },
                "phone": {
                    "id": self.phone_id,
                    "online": self.phone_online,
                    "battery": self.phone_battery,
                    "ip": self.phone_ip,
                    "brain_online": self.phone_brain_online,
                    "brain_url": wm.brain_url,
                    "fg_app": self.phone_fg_app,
                },
                "pc": {
                    "name": self.pc_name,
                },
                "engines": {
                    "five_senses": self.five_senses_running,
                    "dao": self.dao_engine_running,
                    "san_lian": self.san_lian_running,
                },
                "events": self.events[-50:],
                "last_update": self.last_update,
                "timestamp": time.time(),
            }

    def add_event(self, etype: str, data=None):
        with self._lock:
            ev = {"type": etype, "time": time.time(), "data": data}
            self.events.append(ev)
            if len(self.events) > 500:
                self.events = self.events[-200:]
            return ev

    def refresh(self):
        """从ADB采集最新状态（阻塞）"""
        # 眼镜 — 通过wireless_config自动发现
        wm_info = wm.detect()
        gid = wm.glass_addr if wm_info["glasses"]["online"] else ""
        with self._lock:
            self.glasses_id = gid
            self.glasses_online = wm_info["glasses"]["online"]
            self.phone_ip = wm.phone_ip

        if gid:
            # 电量
            batt_out = adb_cmd(gid, "shell", "dumpsys", "battery")
            batt_val = -1
            for line in batt_out.splitlines():
                if "level:" in line:
                    try:
                        batt_val = int(line.split(":")[1].strip())
                    except (ValueError, IndexError):
                        pass

            # 佩戴检测: Hall传感器是input设备，通过sysfs读取(需su)
            hall_out = adb_cmd(gid, "shell",
                "su 0 cat /sys/devices/virtual/hall_switch/soc:hall_1/hall_status 2>/dev/null")
            worn_val = False
            try:
                worn_val = int(hall_out.strip()) == 1
            except (ValueError, TypeError):
                pass
            # 光照: sensorservice无活跃客户端(RayNeo V3开发ROM)，暂无法读取
            light_val = -1.0

            with self._lock:
                self.glasses_battery = batt_val
                self.glasses_worn = worn_val
                self.glasses_light = light_val

        # 手机
        pid = PHONE_USB_SERIAL if _adb_device_state(PHONE_USB_SERIAL) else ""
        # 更新手机IP（可能DHCP变化）
        with self._lock:
            self.phone_id = pid
            self.phone_online = bool(pid)

        if pid:
            out = adb_cmd(pid, "shell", "dumpsys", "battery")
            pb = -1
            for line in out.splitlines():
                if "level:" in line:
                    try:
                        pb = int(line.split(":")[1].strip())
                    except (ValueError, IndexError):
                        pass
            with self._lock:
                self.phone_battery = pb

        # 手机脑 — 通过wireless_config检测
        brain_ok = wm_info["phone"]["brain_online"]
        with self._lock:
            self.phone_brain_online = brain_ok

        self.last_update = time.time()


# ─── 全局状态 ─────────────────────────────────────────────
state = SystemState()
ws_clients = set()

# ─── 后台状态刷新 ─────────────────────────────────────────
def _refresh_loop():
    while True:
        try:
            state.refresh()
        except Exception as e:
            print(f"  [刷新异常] {e}")
        time.sleep(10)

# ─── WebSocket ────────────────────────────────────────────
async def ws_broadcast(msg: dict):
    if ws_clients:
        data = json.dumps(msg, ensure_ascii=False)
        results = await asyncio.gather(
            *[c.send(data) for c in ws_clients],
            return_exceptions=True
        )
        # 清理已断开的客户端
        dead = {c for c, r in zip(ws_clients, results) if isinstance(r, Exception)}
        if dead:
            ws_clients.difference_update(dead)

async def ws_handle(websocket):
    ws_clients.add(websocket)
    addr = websocket.remote_address
    print(f"  [WS] 连接: {addr}")
    await websocket.send(json.dumps({"type": "state", "data": state.to_dict()}, ensure_ascii=False))
    try:
        async for message in websocket:
            try:
                msg = json.loads(message)
                await ws_process(msg, websocket)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"type": "error", "msg": "Invalid JSON"}))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        ws_clients.discard(websocket)
        print(f"  [WS] 断开: {addr}")

async def ws_process(msg: dict, ws):
    mtype = msg.get("type", "")

    if mtype == "get_state":
        await ws.send(json.dumps({"type": "state", "data": state.to_dict()}, ensure_ascii=False))

    elif mtype == "refresh":
        threading.Thread(target=state.refresh, daemon=True).start()
        state.add_event("refresh", {"source": "dashboard"})
        await ws.send(json.dumps({"type": "info", "msg": "正在刷新..."}, ensure_ascii=False))

    elif mtype == "tts":
        text = msg.get("text", "")
        gid = state.glasses_id
        if gid and text:
            threading.Thread(target=_do_tts, args=(gid, text), daemon=True).start()
            state.add_event("tts", {"text": text})
            await ws_broadcast({"type": "tts", "text": text})

    elif mtype == "gesture":
        gesture = msg.get("gesture", "tap")
        ev = state.add_event("gesture", {"gesture": gesture, "source": "dashboard"})
        await ws_broadcast({"type": "event", "event": ev})

    elif mtype == "adb_cmd":
        device = msg.get("device", "glasses")
        cmd = msg.get("cmd", [])
        did = state.glasses_id if device == "glasses" else state.phone_id
        if did and cmd:
            result = adb_cmd(did, *cmd)
            await ws.send(json.dumps({"type": "adb_result", "device": device,
                                      "cmd": cmd, "result": result}, ensure_ascii=False))

    elif mtype == "reconnect":
        ok = wm.reconnect_glasses()
        threading.Thread(target=state.refresh, daemon=True).start()
        await ws.send(json.dumps({"type": "info",
            "msg": f"重连{'成功' if ok else '失败'}: {wm.glass_addr} ({wm.glass_connection or '离线'})"
        }, ensure_ascii=False))

    elif mtype == "capture":
        gid = state.glasses_id
        if gid:
            threading.Thread(target=_do_capture, args=(gid,), daemon=True).start()
            await ws.send(json.dumps({"type": "info", "msg": "正在拍照..."}, ensure_ascii=False))
        else:
            await ws.send(json.dumps({"type": "error", "msg": "眼镜离线"}, ensure_ascii=False))

    elif mtype == "phone_brain":
        action = msg.get("action", "status")
        threading.Thread(target=_phone_brain_action, args=(action, msg), daemon=True).start()

def _do_tts(device_id: str, text: str):
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 160)
        tmp = str(_PROJECT_DIR / "_dashboard_tts.wav")
        engine.save_to_file(text, tmp)
        engine.runAndWait()
        engine.stop()
        if Path(tmp).exists():
            adb_cmd(device_id, "push", tmp, "/sdcard/_tts.wav")
            adb_cmd(device_id, "shell", "am", "start", "-a", "android.intent.action.VIEW",
                    "-d", "file:///sdcard/_tts.wav", "-t", "audio/wav",
                    "--grant-read-uri-permission")
    except Exception as e:
        print(f"  [TTS] {e}")

def _do_capture(device_id: str):
    """眼镜截屏（RayNeo V3无标准相机App，使用screencap）"""
    try:
        ts = int(time.time())
        remote = "/sdcard/_cap.png"
        adb_cmd(device_id, "shell", "screencap", "-p", remote)
        local = str(_PROJECT_DIR / f"cap_{ts}.png")
        # adb pull outputs to stderr, use subprocess directly
        r = subprocess.run([ADB, "-s", device_id, "pull", remote, local],
                           capture_output=True, text=True, timeout=15)
        output = (r.stdout + r.stderr).strip()
        if Path(local).exists() and Path(local).stat().st_size > 0:
            fsize = Path(local).stat().st_size
            state.add_event("capture", {"file": f"cap_{ts}.png", "local": local, "size": fsize})
            print(f"  [截屏] cap_{ts}.png ({fsize}B)")
        else:
            state.add_event("capture_fail", {"reason": f"pull: {output}"})
    except Exception as e:
        state.add_event("capture_fail", {"error": str(e)})

def _phone_brain_action(action: str, msg: dict):
    try:
        if action == "status":
            req = urllib.request.Request(
                f"{wm.brain_url}/status",
                headers={"User-Agent": "dashboard"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                state.add_event("phone_status", data)
        elif action == "ask":
            payload = json.dumps({"query": msg.get("query", "你好")}).encode()
            req = urllib.request.Request(
                f"{wm.brain_url}/ask",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "dashboard"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                state.add_event("ai_answer", data)
    except Exception as e:
        state.add_event("phone_error", {"error": str(e)})


# ─── HTTP API + 静态服务 ──────────────────────────────────
class DashboardHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/dashboard":
            self._serve_file("rayneo_dashboard.html", "text/html")
        elif path == "/api/state":
            self._json(state.to_dict())
        elif path == "/api/status":
            # wireless_config集成状态（dashboard.html init使用）
            # 不调用wm.detect()避免阻塞，使用缓存数据
            sd = state.to_dict()
            sd["wireless"] = {
                "glasses": {"addr": wm.glass_addr, "ip": wm.glass_ip,
                            "connection": wm.glass_connection,
                            "online": wm.is_glass_online},
                "phone": {"ip": wm.phone_ip},
            }
            sd["phone"]["brain_url"] = wm.brain_url
            self._json(sd)
        elif path == "/api/refresh":
            threading.Thread(target=state.refresh, daemon=True).start()
            self._json({"ok": True, "msg": "refreshing"})
        elif path == "/api/reconnect":
            ok = wm.reconnect_glasses()
            threading.Thread(target=state.refresh, daemon=True).start()
            self._json({"ok": ok, "addr": wm.glass_addr, "conn": wm.glass_connection})
        elif path.endswith((".html", ".js", ".css", ".png", ".ico", ".svg")):
            ctype = {"html": "text/html", "js": "application/javascript",
                     "css": "text/css", "png": "image/png", "ico": "image/x-icon",
                     "svg": "image/svg+xml"}.get(path.rsplit(".", 1)[-1], "text/plain")
            self._serve_file(path.lstrip("/"), ctype)
        else:
            self._json({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = {}
        if length:
            try:
                body = json.loads(self.rfile.read(length))
            except Exception:
                pass

        if self.path == "/api/tts":
            text = body.get("text", "")
            gid = state.glasses_id
            if gid and text:
                threading.Thread(target=_do_tts, args=(gid, text), daemon=True).start()
                state.add_event("tts", {"text": text})
                self._json({"ok": True})
            else:
                self._json({"error": "no device or text"})

        elif self.path == "/api/capture":
            gid = state.glasses_id
            if gid:
                threading.Thread(target=_do_capture, args=(gid,), daemon=True).start()
                self._json({"ok": True, "msg": "capturing"})
            else:
                self._json({"error": "glasses offline"})

        elif self.path == "/api/adb":
            device = body.get("device", "glasses")
            cmd = body.get("cmd", [])
            did = state.glasses_id if device == "glasses" else state.phone_id
            if did and cmd:
                result = adb_cmd(did, *cmd)
                self._json({"result": result})
            else:
                self._json({"error": "no device or cmd"})
        else:
            self._json({"error": "not found"}, 404)

    def _serve_file(self, filename: str, content_type: str):
        fpath = (_PROJECT_DIR / filename).resolve()
        if not str(fpath).startswith(str(_PROJECT_DIR)):
            self.send_response(403)
            self.end_headers()
            return
        if fpath.exists():
            data = fpath.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def _json(self, data: dict, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # 静默


# ─── 定时推送 ─────────────────────────────────────────────
async def push_state_loop():
    """每10秒推送一次状态"""
    while True:
        await asyncio.sleep(10)
        if ws_clients:
            await ws_broadcast({"type": "state", "data": state.to_dict()})


# ─── 主入口 ───────────────────────────────────────────────
async def main(http_port=8800, ws_port=8801):
    print("\n╔══════════════════════════════════════╗")
    print("║  RayNeo V3 管理中枢 · 道统万物         ║")
    print("╚══════════════════════════════════════╝\n")

    # 初始刷新（后台执行，不阻塞服务器启动）
    def _initial_refresh():
        print("  [初始化] 采集设备状态...")
        try:
            state.refresh()
        except Exception as e:
            print(f"  [初始化] 采集异常(非致命): {e}")
        g = "✅ " + state.glasses_id if state.glasses_online else "❌ 离线"
        p = "✅ " + state.phone_id if state.phone_online else "❌ 离线"
        b = "✅" if state.phone_brain_online else "❌"
        print(f"  眼镜: {g}")
        print(f"  手机: {p} (脑:{b})")
    threading.Thread(target=_initial_refresh, daemon=True).start()

    # 后台刷新线程
    threading.Thread(target=_refresh_loop, daemon=True).start()

    # 健康监测（WiFi keepalive + 自动重连 + IP变化检测）
    def _on_health_event(event, detail):
        state.add_event("health", {"event": event, "detail": str(detail)})
        print(f"  [健康] {event}: {detail}")
        # 连接变化时立即刷新状态
        if event in ("glass_disconnected", "glass_reconnected", "glass_ip_changed"):
            threading.Thread(target=state.refresh, daemon=True).start()
    wm.start_health_monitor(interval=20, callback=_on_health_event)

    # HTTP
    httpd = HTTPServer(("0.0.0.0", http_port), DashboardHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    print(f"\n  [HTTP] Dashboard: http://localhost:{http_port}/")
    print(f"  [WS]   实时推送:  ws://localhost:{ws_port}")
    print(f"\n  按 Ctrl+C 退出\n")

    # WebSocket + 定时推送
    async with websockets.serve(ws_handle, "0.0.0.0", ws_port):
        await push_state_loop()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RayNeo V3 管理中枢")
    parser.add_argument("--http-port", type=int, default=8800)
    parser.add_argument("--ws-port", type=int, default=8801)
    args = parser.parse_args()
    try:
        asyncio.run(main(args.http_port, args.ws_port))
    except KeyboardInterrupt:
        print("\n[管理中枢关闭]")
