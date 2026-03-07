#!/usr/bin/env python3
"""
desktop.py — Desktop Screen Provider v2.3 (Ghost Shell Enhanced)
电脑公网投屏手机 — 桌面端屏幕采集与控制 (P2P + Relay双模式)

Modes:
  Relay: Connects to relay server, frames forwarded to viewers
  Direct: Built-in HTTP+WS server, phone connects directly (LAN P2P)

Usage:
  python desktop.py                                    # Relay mode (local)
  python desktop.py --relay wss://aiotvr.xyz/desktop/  # Relay mode (public)
  python desktop.py --direct                           # P2P direct mode (LAN)
  python desktop.py --direct --port 9803               # P2P on custom port
  python desktop.py --room MYCODE --fps 15 --quality 70
"""

# CRITICAL: Set DPI awareness BEFORE any other imports (from Ghost Shell)
# Fixes multi-monitor coordinate offset on high-DPI displays
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI Aware V2
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # Fallback
    except Exception:
        pass

import sys
import os
import io
import json
import time
import threading
import argparse
import asyncio
import platform
import subprocess
import socket as sock_mod
import http
import faulthandler
from urllib.parse import urlencode

faulthandler.enable()

import atexit
def _on_exit():
    try:
        with open(os.path.join(os.path.dirname(__file__), '_exit_marker.txt'), 'w') as f:
            f.write(f"Python atexit fired at {time.strftime('%H:%M:%S')}\n")
    except Exception:
        pass
atexit.register(_on_exit)

# ── Dependency check ──
_missing = []
try:
    import mss
except ImportError:
    _missing.append('mss')
try:
    from PIL import Image
except ImportError:
    _missing.append('Pillow')
try:
    import websocket
except ImportError:
    _missing.append('websocket-client')
try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0
except ImportError:
    pyautogui = None
    print("[WARN] pyautogui not installed — control commands disabled")
try:
    import websockets
    import websockets.exceptions
except ImportError:
    _missing.append('websockets')
    websockets = None
try:
    import pyperclip
except ImportError:
    pyperclip = None
    print("[WARN] pyperclip not installed — clipboard sync disabled")
try:
    import dxcam
    import numpy as np
except ImportError:
    dxcam = None

if _missing:
    print(f"ERROR: Missing packages: {', '.join(_missing)}")
    print(f"  pip install {' '.join(_missing)}")
    sys.exit(1)

# ── Constants ──
DEFAULT_RELAY = 'wss://aiotvr.xyz/desktop/'
DEFAULT_TOKEN = 'desktop_cast_2026'
DEFAULT_FPS = 10
DEFAULT_QUALITY = 60
DEFAULT_SCALE = 50


class DesktopProvider:
    def __init__(self, relay_url, token, room=None, fps=DEFAULT_FPS,
                 quality=DEFAULT_QUALITY, scale=DEFAULT_SCALE, monitor_idx=1):
        self.relay_url = relay_url
        self.token = token
        self.room = room
        self.fps = fps
        self.quality = quality
        self.scale = scale
        self.monitor_idx = monitor_idx
        self.ws = None
        self.running = False
        self.connected = False
        self.room_id = None
        self.screen_w = 0
        self.screen_h = 0
        self._lock = threading.Lock()
        self._frame_count = 0
        self._last_frame_size = 0

        # Get screen resolution (temporary mss instance for init only)
        with mss.mss() as sct:
            mon = sct.monitors[self.monitor_idx]
            self.screen_w = mon['width']
            self.screen_h = mon['height']

    def start(self):
        self.running = True
        print(f"╔══════════════════════════════════════╗")
        print(f"║  Desktop Cast Provider v2.3          ║")
        print(f"╠══════════════════════════════════════╣")
        print(f"║  Screen : {self.screen_w}x{self.screen_h:<24}║")
        print(f"║  FPS    : {self.fps:<27}║")
        print(f"║  Quality: {self.quality:<27}║")
        print(f"║  Scale  : {self.scale}%{' '*(25 - len(str(self.scale)))}║")
        print(f"║  Relay  : {self.relay_url[:26]:<27}║")
        print(f"╚══════════════════════════════════════╝")

        while self.running:
            try:
                self._connect()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[ERROR] {e}")

            if self.running:
                print("[INFO] Reconnecting in 3s...")
                time.sleep(3)

        print("[INFO] Provider stopped")

    def _connect(self):
        params = {'role': 'provider', 'token': self.token}
        if self.room:
            params['room'] = self.room

        url = f"{self.relay_url}?{urlencode(params)}"

        self.ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_close=self._on_close,
            on_error=self._on_error,
        )
        self.ws.run_forever(ping_interval=25, ping_timeout=10)

    def _on_open(self, ws):
        print("[CONNECTED] WebSocket connected to relay")
        self.connected = True
        self._frame_count = 0

        # Send device info
        try:
            hostname = sock_mod.gethostname()
        except Exception:
            hostname = 'unknown'

        ws.send(json.dumps({
            'type': 'device_info',
            'data': {
                'hostname': hostname,
                'os': f"{platform.system()} {platform.release()}",
                'screen_w': self.screen_w,
                'screen_h': self.screen_h,
                'python': platform.python_version(),
                'scale': self.scale,
                'quality': self.quality,
                'fps': self.fps,
            }
        }))

        # Start capture thread
        t = threading.Thread(target=self._capture_loop, daemon=True)
        t.start()

    def _on_message(self, ws, message):
        try:
            msg = json.loads(message)
        except Exception:
            return

        msg_type = msg.get('type', '')

        if msg_type == 'registered':
            self.room_id = msg.get('data', {}).get('roomId', '?')
            # Persist room code so reconnections reuse the same room
            if not self.room:
                self.room = self.room_id
            print(f"")
            print(f"  ┌─────────────────────────────┐")
            print(f"  │  Room Code: {self.room_id:<16}│")
            print(f"  │  Share with phone to connect │")
            print(f"  └─────────────────────────────┘")
            print(f"")

        elif msg_type == 'viewer_joined':
            count = msg.get('data', {}).get('count', 0)
            print(f"[VIEWER] +1 ({count} total)")

        elif msg_type == 'viewer_left':
            count = msg.get('data', {}).get('count', 0)
            print(f"[VIEWER] -1 ({count} remaining)")

        # Control commands from viewer (all types including Ghost Shell + ping)
        else:
            self._handle_control(msg)

    def _on_close(self, ws, close_status_code, close_msg):
        self.connected = False
        print(f"[DISCONNECTED] code={close_status_code} msg={close_msg}")

    def _on_error(self, ws, error):
        if self.connected:
            print(f"[ERROR] {error}")

    def _capture_loop(self):
        """Screen capture main loop — runs in a dedicated thread."""
        def send_frame(frame):
            if self.ws and self.connected:
                self.ws.send(frame, opcode=websocket.ABNF.OPCODE_BINARY)
        _capture_frames(self, send_frame, lambda: self.connected and self.running)

    def _handle_control(self, msg):
        _handle_control_cmd(self, msg)


def _type_via_clipboard(text):
    """Type text using clipboard paste — supports CJK characters."""
    try:
        # Escape for PowerShell
        escaped = text.replace("'", "''")
        subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             f"Set-Clipboard -Value '{escaped}'"],
            capture_output=True, timeout=3
        )
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.05)
    except Exception as e:
        # Fallback: direct typing (ASCII only)
        try:
            pyautogui.typewrite(text, interval=0.02)
        except Exception:
            print(f"[TYPE ERROR] {e}")


# ─── Shared Control & Capture Logic ───

_cmd_timestamps = []
_CMD_RATE_LIMIT = 60  # max commands per second

def _handle_control_cmd(provider, msg, reply_ws=None):
    """Execute a control command from the viewer.
    `provider` must have screen_w, screen_h, quality, fps, scale attributes.
    `reply_ws` — if provided, used for unicast replies (e.g. pong) instead of broadcast."""
    if not pyautogui:
        return
    # Rate limiting: max 60 commands/sec (skip ping/pong from limit)
    t_type = msg.get('type', '')
    if t_type not in ('ping', 'set_quality', 'set_fps', 'set_scale'):
        now = time.monotonic()
        _cmd_timestamps[:] = [t for t in _cmd_timestamps if now - t < 1.0]
        if len(_cmd_timestamps) >= _CMD_RATE_LIMIT:
            return
        _cmd_timestamps.append(now)
    _BTN_MAP = {0: 'left', 1: 'middle', 2: 'right'}
    try:
        t = msg.get('type', '')
        data = msg.get('data', msg)

        if t == 'click':
            x = int(float(data.get('x', 0)) * provider.screen_w)
            y = int(float(data.get('y', 0)) * provider.screen_h)
            raw_btn = data.get('button', 'left')
            btn = _BTN_MAP.get(raw_btn, raw_btn) if isinstance(raw_btn, int) else raw_btn
            mods = data.get('modifiers', [])
            if mods:
                for m in mods:
                    pyautogui.keyDown(m)
                pyautogui.click(x, y, button=btn)
                for m in reversed(mods):
                    pyautogui.keyUp(m)
            else:
                pyautogui.click(x, y, button=btn)
        elif t == 'dblclick':
            x = int(float(data.get('x', 0)) * provider.screen_w)
            y = int(float(data.get('y', 0)) * provider.screen_h)
            pyautogui.doubleClick(x, y)
        elif t == 'rightclick':
            x = int(float(data.get('x', 0)) * provider.screen_w)
            y = int(float(data.get('y', 0)) * provider.screen_h)
            pyautogui.rightClick(x, y)
        elif t == 'move':
            x = int(float(data.get('x', 0)) * provider.screen_w)
            y = int(float(data.get('y', 0)) * provider.screen_h)
            pyautogui.moveTo(x, y)
        elif t == 'drag':
            x1 = int(float(data.get('x1', 0)) * provider.screen_w)
            y1 = int(float(data.get('y1', 0)) * provider.screen_h)
            x2 = int(float(data.get('x2', 0)) * provider.screen_w)
            y2 = int(float(data.get('y2', 0)) * provider.screen_h)
            dur = float(data.get('duration', 0.3))
            pyautogui.moveTo(x1, y1)
            pyautogui.drag(x2 - x1, y2 - y1, duration=dur)
        elif t == 'scroll':
            x = int(float(data.get('x', 0.5)) * provider.screen_w)
            y = int(float(data.get('y', 0.5)) * provider.screen_h)
            delta = int(data.get('delta', 0))
            pyautogui.moveTo(x, y)
            pyautogui.scroll(delta)
        elif t == 'key':
            key = data.get('key', '')
            if key:
                pyautogui.press(key)
        elif t == 'hotkey':
            keys = data.get('keys', [])
            if keys:
                pyautogui.hotkey(*keys)
        elif t in ('type', 'text'):
            text = data.get('text', '')
            if text:
                _type_via_clipboard(text)
        # ── Ping/Pong for RTT measurement ──
        elif t == 'ping':
            ts = data.get('ts', 0)
            pong_msg = json.dumps({'type': 'pong', 'data': {'ts': ts}})
            if reply_ws is not None:
                # P2P mode: unicast pong to the specific viewer
                loop = provider.server._loop if hasattr(provider, 'server') and provider.server else None
                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        reply_ws.send(pong_msg), loop)
            elif hasattr(provider, 'ws') and provider.ws:
                try: provider.ws.send(pong_msg)
                except Exception: pass
            elif hasattr(provider, 'server') and provider.server:
                loop = provider.server._loop
                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        provider.server._broadcast_json(pong_msg), loop)
        # ── Ghost Shell Enhanced Controls ──
        elif t == 'mousedown':
            x = int(float(data.get('x', 0)) * provider.screen_w)
            y = int(float(data.get('y', 0)) * provider.screen_h)
            btn = data.get('button', 'left')
            pyautogui.mouseDown(x, y, button=btn)
        elif t == 'mouseup':
            x = int(float(data.get('x', 0)) * provider.screen_w)
            y = int(float(data.get('y', 0)) * provider.screen_h)
            btn = data.get('button', 'left')
            pyautogui.mouseUp(x, y, button=btn)
        elif t == 'mousemove':
            x = int(float(data.get('x', 0)) * provider.screen_w)
            y = int(float(data.get('y', 0)) * provider.screen_h)
            pyautogui.moveTo(x, y, _pause=False)
        elif t == 'middleclick':
            x = int(float(data.get('x', 0)) * provider.screen_w)
            y = int(float(data.get('y', 0)) * provider.screen_h)
            pyautogui.click(x, y, button='middle')
        elif t == 'get_clipboard':
            try:
                if pyperclip is None:
                    print("[CLIPBOARD] pyperclip not installed")
                    return
                content = pyperclip.paste()
                clip_msg = json.dumps({
                    'type': 'clipboard', 'data': {'content': content or ''}
                })
                # Unicast clipboard to the requesting viewer (not broadcast)
                if reply_ws is not None:
                    loop = provider.server._loop if hasattr(provider, 'server') and provider.server else None
                    if loop and loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            reply_ws.send(clip_msg), loop)
                elif hasattr(provider, 'ws') and provider.ws:
                    provider.ws.send(clip_msg)
                elif hasattr(provider, 'server') and provider.server:
                    loop = provider.server._loop
                    if loop and loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            provider.server._broadcast_json(clip_msg), loop)
            except Exception as e:
                print(f"[CLIPBOARD] Error: {e}")
        elif t == 'open_app':
            app_name = data.get('name', '')
            if app_name:
                pyautogui.hotkey('win', 's')
                time.sleep(0.8)
                _type_via_clipboard(app_name)
                time.sleep(0.5)
                pyautogui.press('enter')
                print(f"[OPEN_APP] Opening: {app_name}")
        elif t == 'set_quality':
            v = int(data.get('value', provider.quality))
            provider.quality = max(10, min(100, v))
            print(f"[CONFIG] Quality → {provider.quality}")
        elif t == 'set_fps':
            v = int(data.get('value', provider.fps))
            provider.fps = max(1, min(30, v))
            print(f"[CONFIG] FPS → {provider.fps}")
        elif t == 'set_scale':
            v = int(data.get('value', provider.scale))
            provider.scale = max(10, min(100, v))
            print(f"[CONFIG] Scale → {provider.scale}%")
    except Exception as e:
        print(f"[CONTROL ERROR] {t}: {e}")


def _capture_frames(provider, send_fn, is_running_fn):
    """Optimized screen capture loop with frame dedup & adaptive quality.
    send_fn(frame_bytes) — sends one JPEG/WebP frame.
    is_running_fn() — returns False to stop."""
    import hashlib

    # ── Try DXcam first (3x faster than mss for 4K capture) ──
    use_dxcam = False
    cam = None
    if dxcam is not None:
        try:
            cam = dxcam.create(output_idx=max(0, provider.monitor_idx - 1))
            cam.start(target_fps=min(30, provider.fps + 5))
            time.sleep(0.3)  # warm up
            test = cam.get_latest_frame()
            if test is not None:
                use_dxcam = True
                print(f"[CAPTURE] Using DXcam ({test.shape[1]}x{test.shape[0]})")
            else:
                cam.stop()
                del cam
                cam = None
        except Exception as e:
            print(f"[CAPTURE] DXcam init failed ({e}), falling back to mss")
            cam = None

    if not use_dxcam:
        print("[CAPTURE] Using mss")

    sct = None
    monitor = None
    if not use_dxcam:
        sct = mss.mss()
        monitor = sct.monitors[provider.monitor_idx]

    try:
      frame_count = 0
      skip_count = 0
      last_hash = None
      send_times = []  # Track send durations for adaptive quality
      adaptive_quality = provider.quality
      _last_user_quality = provider.quality  # Track user-initiated quality changes
      consecutive_skips = 0

      while is_running_fn():
          interval = 1.0 / provider.fps
          start = time.monotonic()
          try:
              t0 = time.monotonic()
              if use_dxcam:
                  np_frame = cam.get_latest_frame()
                  if np_frame is None:
                      time.sleep(0.01)
                      continue
                  raw = np_frame.tobytes()
                  grab_w, grab_h = np_frame.shape[1], np_frame.shape[0]
              else:
                  sct_img = sct.grab(monitor)
                  raw = sct_img.rgb
                  grab_w, grab_h = sct_img.width, sct_img.height
              t1 = time.monotonic()

              # ── Frame dedup: skip identical frames (saves ~30-60% bandwidth) ──
              frame_hash = hashlib.md5(raw[::1000]).digest()  # Sample every 1000th byte for speed
              if frame_hash == last_hash:
                  consecutive_skips += 1
                  skip_count += 1
                  # Still sleep to maintain timing
                  elapsed = time.monotonic() - start
                  sleep_time = interval - elapsed
                  if sleep_time > 0:
                      time.sleep(sleep_time)
                  continue
              last_hash = frame_hash
              consecutive_skips = 0

              t2 = time.monotonic()
              img = Image.frombytes('RGB', (grab_w, grab_h), raw)

              cur_scale = provider.scale
              if cur_scale < 100:
                  nw = int(img.width * cur_scale / 100)
                  nh = int(img.height * cur_scale / 100)
                  img = img.resize((nw, nh), Image.Resampling.BILINEAR)
              else:
                  nw, nh = img.width, img.height
              t3 = time.monotonic()

              # ── Adaptive quality: sync with user-initiated changes ──
              if provider.quality != _last_user_quality:
                  adaptive_quality = provider.quality
                  _last_user_quality = provider.quality
              elif adaptive_quality > provider.quality:
                  adaptive_quality = provider.quality
              q = adaptive_quality
              buf = io.BytesIO()
              # Use WebP if available (~30% smaller than JPEG at same quality)
              fmt = getattr(provider, '_img_format', None)
              if fmt is None:
                  try:
                      test_buf = io.BytesIO()
                      img.save(test_buf, 'WEBP', quality=q, method=0)
                      fmt = 'WEBP'
                  except Exception:
                      fmt = 'JPEG'
                  provider._img_format = fmt
              if fmt == 'JPEG':
                  img.save(buf, fmt, quality=q, optimize=False)
              else:
                  img.save(buf, fmt, quality=q, method=0)
              frame = buf.getvalue()
              t4 = time.monotonic()

              # Track send performance
              send_start = time.monotonic()
              send_fn(frame)
              send_dur = time.monotonic() - send_start

              # Timing log (every 50 frames)
              if frame_count % 50 == 0:
                  cap_name = 'dxcam' if use_dxcam else 'mss'
                  print(f"[TIMING] grab={int((t1-t0)*1000)}ms pil+resize={int((t3-t2)*1000)}ms "
                        f"encode={int((t4-t3)*1000)}ms send={int(send_dur*1000)}ms "
                        f"total={int((time.monotonic()-t0)*1000)}ms target={int(interval*1000)}ms [{cap_name}]")
              send_times.append(send_dur)
              if len(send_times) > 30:
                  send_times.pop(0)

              frame_count += 1

              # ── Adaptive quality adjustment (every 30 frames) ──
              if len(send_times) >= 30 and frame_count % 30 == 0:
                  avg_send = sum(send_times) / len(send_times)
                  # If sending takes >60% of frame interval, reduce quality
                  if avg_send > interval * 0.6 and adaptive_quality > 20:
                      adaptive_quality = max(20, adaptive_quality - 5)
                  # If sending is fast and quality is below target, increase
                  elif avg_send < interval * 0.2 and adaptive_quality < provider.quality:
                      adaptive_quality = min(provider.quality, adaptive_quality + 3)

              if frame_count % max(provider.fps * 10, 1) == 0:
                  skip_pct = round(skip_count / max(1, frame_count + skip_count) * 100)
                  print(f"[STATS] sent={frame_count} skip={skip_count}({skip_pct}%) "
                        f"size={len(frame) // 1024}KB q={adaptive_quality} "
                        f"fmt={fmt} res={nw}x{nh}")

          except KeyboardInterrupt:
              break
          except Exception as e:
              print(f"[CAPTURE ERROR] {e}")
              time.sleep(0.5)
              continue

          elapsed = time.monotonic() - start
          sleep_time = interval - elapsed
          if sleep_time > 0:
              time.sleep(sleep_time)
    finally:
      if cam is not None:
          try:
              cam.stop()
          except Exception:
              pass
      if sct is not None:
          try:
              sct.close()
          except Exception:
              pass


# ─── Direct P2P Server (websockets library) ───


class DirectServer:
    """Built-in HTTP+WebSocket server for LAN P2P direct mode.
    Phone connects directly to desktop — no relay needed.
    Uses `websockets` library for reliable WebSocket handling."""

    def __init__(self, port, viewer_html_path, device_info, control_handler):
        self.port = port
        self.device_info = device_info
        self.control_handler = control_handler
        self.clients = {}  # vid → websocket
        self.last_frame = None
        self._lock = threading.Lock()
        self.running = False
        self._loop = None
        self._server = None
        self._loop_alive = False

        # Load and patch viewer HTML for direct mode
        with open(viewer_html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        inject = "window.DIRECT_MODE = true; // ── P2P Direct (injected by desktop.py) ──\n"
        html = html.replace('<script>', '<script>\n' + inject, 1)
        self._viewer_bytes = html.encode('utf-8')

        # Load manifest.json for PWA support in P2P mode
        manifest_path = os.path.join(os.path.dirname(viewer_html_path), 'manifest.json')
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                self._manifest_bytes = f.read().encode('utf-8')
        except FileNotFoundError:
            self._manifest_bytes = None

    def start(self):
        self.running = True
        self._ready = threading.Event()
        self._bind_error = None
        # Kill any stale process holding our port (prevents EADDRINUSE)
        self._kill_port_holder(self.port)
        t = threading.Thread(target=self._run_loop, daemon=True)
        t.start()
        # Wait for event loop to be created in the daemon thread
        self._ready.wait(timeout=10)
        if self._bind_error:
            raise self._bind_error
        return t

    def _run_loop(self):
        # CRITICAL: Create event loop IN this thread (Windows ProactorEventLoop
        # uses IOCP which is thread-affine — creating in main thread but running
        # here causes I/O events to never be processed)
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop_alive = True
        try:
            self._loop.run_until_complete(self._serve())
        except OSError as e:
            self._bind_error = e
            print(f"[P2P-SERVER] Bind failed: {e}")
        except Exception as e:
            print(f"[P2P-SERVER] Event loop crashed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._loop_alive = False
            self.running = False
            self._ready.set()  # Unblock main thread even on failure

    @staticmethod
    def _kill_port_holder(port):
        """Kill any process holding the port (prevents EADDRINUSE on restart)."""
        try:
            result = subprocess.run(
                ['netstat', '-ano'], capture_output=True, timeout=5,
                text=True, encoding='gbk', errors='ignore')
            for line in result.stdout.splitlines():
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    pid = int(parts[-1])
                    if pid != os.getpid():
                        subprocess.run(['taskkill', '/PID', str(pid), '/F'],
                                       capture_output=True, timeout=5)
                        print(f"[P2P-SERVER] Killed stale process PID {pid} on port {port}")
                        time.sleep(1)
        except Exception as e:
            print(f"[P2P-SERVER] Port cleanup warning: {e}")

    async def _serve(self):
        self._server = await websockets.serve(
            self._ws_handler,
            '0.0.0.0', self.port,
            process_request=self._process_http,
            max_size=None,
            ping_interval=20,
            ping_timeout=10,
        )
        self._ready.set()  # Signal main thread: WS server is ready
        await self._server.wait_closed()

    async def _process_http(self, path, request_headers):
        """Intercept HTTP requests to serve viewer HTML and API endpoints.
        Return None to proceed with WebSocket upgrade."""
        if request_headers.get('Upgrade', '').lower() == 'websocket':
            return None

        if path in ('/', '/index.html') or path.startswith('/?'):
            return (http.HTTPStatus.OK,
                    [('Content-Type', 'text/html; charset=utf-8'),
                     ('Access-Control-Allow-Origin', '*')],
                    self._viewer_bytes)

        if path == '/manifest.json' and self._manifest_bytes:
            return (http.HTTPStatus.OK,
                    [('Content-Type', 'application/json'),
                     ('Access-Control-Allow-Origin', '*')],
                    self._manifest_bytes)

        if path == '/api/health':
            body = json.dumps({'ok': True, 'mode': 'p2p_direct',
                               'viewers': len(self.clients)}).encode()
            return (http.HTTPStatus.OK,
                    [('Content-Type', 'application/json'),
                     ('Access-Control-Allow-Origin', '*')],
                    body)

        if path == '/api/info':
            body = json.dumps(self.device_info).encode()
            return (http.HTTPStatus.OK,
                    [('Content-Type', 'application/json'),
                     ('Access-Control-Allow-Origin', '*')],
                    body)

        return (http.HTTPStatus.NOT_FOUND, [('Content-Type', 'text/plain')], b'Not Found')

    async def _ws_handler(self, websocket):
        """Handle a WebSocket viewer connection."""
        addr = websocket.remote_address
        vid = f'p2p-{addr[0]}-{addr[1]}'

        with self._lock:
            self.clients[vid] = websocket

        print(f"[P2P] Viewer connected: {addr[0]}:{addr[1]} ({len(self.clients)} total)")

        try:
            # Send join confirmation
            await websocket.send(json.dumps({
                'type': 'joined',
                'data': {
                    'roomId': 'P2P-DIRECT',
                    'viewerId': vid,
                    'deviceInfo': self.device_info,
                    'viewerCount': len(self.clients)
                }
            }))

            # Send cached frame for instant display
            if self.last_frame:
                try:
                    await websocket.send(self.last_frame)
                except Exception:
                    pass

            # Receive control commands
            async for message in websocket:
                if isinstance(message, str):
                    try:
                        cmd = json.loads(message)
                        self.control_handler(cmd, reply_ws=websocket)
                    except Exception:
                        pass
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            print(f"[P2P] Error: {e}")
        finally:
            with self._lock:
                self.clients.pop(vid, None)
            print(f"[P2P] Viewer disconnected: {addr[0]}:{addr[1]} ({len(self.clients)} remaining)")

    def broadcast_frame(self, frame_data):
        """Send frame to all connected P2P viewers (called from capture thread)."""
        self.last_frame = frame_data
        if not self._loop or not self._loop_alive or not self.clients:
            return
        # Schedule async sends from the sync capture thread
        try:
            asyncio.run_coroutine_threadsafe(self._async_broadcast(frame_data), self._loop)
        except RuntimeError:
            pass  # Event loop closed/stopped — ignore silently

    async def _async_broadcast(self, frame_data):
        with self._lock:
            clients = list(self.clients.items())
        dead = []
        for vid, ws in clients:
            try:
                # Backpressure: skip frame if viewer write buffer > 512KB
                if hasattr(ws, 'transport') and ws.transport:
                    buf_size = ws.transport.get_write_buffer_size()
                    if buf_size > 524288:
                        continue
                await ws.send(frame_data)
            except Exception:
                dead.append(vid)
        if dead:
            with self._lock:
                for vid in dead:
                    self.clients.pop(vid, None)

    async def _broadcast_json(self, msg):
        """Send JSON message to all connected P2P viewers (for clipboard sync etc)."""
        data = json.dumps(msg) if isinstance(msg, dict) else msg
        with self._lock:
            clients = list(self.clients.items())
        dead = []
        for vid, ws in clients:
            try:
                await ws.send(data)
            except Exception:
                dead.append(vid)
        if dead:
            with self._lock:
                for vid in dead:
                    self.clients.pop(vid, None)

    def stop(self):
        self.running = False
        if self._server:
            self._server.close()
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)


class LANDiscovery:
    """UDP broadcast beacon for P2P LAN auto-discovery.
    Phones can listen on UDP 9804 to find desktop cast servers."""
    DISCOVERY_PORT = 9804
    BEACON_INTERVAL = 3  # seconds

    def __init__(self, http_port, hostname, local_ip):
        self.http_port = http_port
        self.hostname = hostname
        self.local_ip = local_ip
        self.running = False
        self._thread = None

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._beacon_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def _beacon_loop(self):
        msg = json.dumps({
            'service': 'desktop-cast',
            'host': self.local_ip,
            'port': self.http_port,
            'name': self.hostname,
        }).encode('utf-8')
        try:
            s = sock_mod.socket(sock_mod.AF_INET, sock_mod.SOCK_DGRAM)
            s.setsockopt(sock_mod.SOL_SOCKET, sock_mod.SO_BROADCAST, 1)
            s.settimeout(1)
            while self.running:
                try:
                    s.sendto(msg, ('<broadcast>', self.DISCOVERY_PORT))
                except Exception:
                    pass
                time.sleep(self.BEACON_INTERVAL)
            s.close()
        except Exception as e:
            print(f"[DISCOVERY] Beacon error: {e}")


class DirectModeProvider:
    """Desktop provider in P2P direct mode — built-in server, no relay needed."""

    def __init__(self, port=9803, fps=DEFAULT_FPS, quality=DEFAULT_QUALITY,
                 scale=DEFAULT_SCALE, monitor_idx=1):
        self.port = port
        self.fps = fps
        self.quality = quality
        self.scale = scale
        self.monitor_idx = monitor_idx
        self.running = False

        with mss.mss() as sct:
            mon = sct.monitors[self.monitor_idx]
            self.screen_w = mon['width']
            self.screen_h = mon['height']

        try:
            hostname = sock_mod.gethostname()
        except Exception:
            hostname = 'unknown'

        self.device_info = {
            'hostname': hostname,
            'os': f"{platform.system()} {platform.release()}",
            'screen_w': self.screen_w,
            'screen_h': self.screen_h,
            'python': platform.python_version(),
            'scale': self.scale,
            'quality': self.quality,
            'fps': self.fps,
            'mode': 'p2p_direct',
        }

        viewer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'viewer', 'index.html')
        self.server = DirectServer(port, viewer_path, self.device_info, self._handle_control_with_ws)
        self._discovery = None

    def start(self):
        self.running = True
        local_ip = self._get_local_ip()

        # Start LAN discovery beacon
        try:
            hostname = self.device_info.get('hostname', 'unknown')
            self._discovery = LANDiscovery(self.port, hostname, local_ip)
            self._discovery.start()
            print(f"[DISCOVERY] LAN beacon active on UDP {LANDiscovery.DISCOVERY_PORT}")
        except Exception as e:
            print(f"[DISCOVERY] Beacon failed: {e}")

        print(f"╔══════════════════════════════════════╗")
        print(f"║  Desktop Cast P2P Direct v2.3        ║")
        print(f"╠══════════════════════════════════════╣")
        print(f"║  Mode  : P2P Direct (no relay)       ║")
        print(f"║  Screen: {self.screen_w}x{self.screen_h:<24}║")
        print(f"║  FPS   : {self.fps:<28}║")
        print(f"║  Quality: {self.quality:<27}║")
        print(f"║  Scale : {self.scale}%{' '*(26 - len(str(self.scale)))}║")
        print(f"╠══════════════════════════════════════╣")
        print(f"║  手机浏览器打开:                     ║")
        print(f"║  http://{local_ip}:{self.port}/")
        print(f"╚══════════════════════════════════════╝")
        print(f"")
        print(f"[INFO] 手机须与电脑在同一WiFi网络")

        try:
            self.server.start()
        except OSError as e:
            print(f"[FATAL] Cannot start P2P server: {e}")
            print(f"[HINT] Kill process using port {self.port}: netstat -ano | findstr :{self.port}")
            return
        self._capture_loop()

    def _capture_loop(self):
        """Screen capture loop — delegates to shared function."""
        _capture_frames(self, self.server.broadcast_frame,
                        lambda: self.running and getattr(self.server, '_loop_alive', True))
        if self._discovery:
            self._discovery.stop()
        self.server.stop()
        print("[INFO] P2P Direct provider stopped")

    def _handle_control_with_ws(self, msg, reply_ws=None):
        """Handle control command and sync device_info for P2P mode."""
        _handle_control_cmd(self, msg, reply_ws=reply_ws)
        # Sync device_info dict so new viewers get current settings
        for key in ('quality', 'fps', 'scale'):
            self.device_info[key] = getattr(self, key)

    def _get_local_ip(self):
        try:
            s = sock_mod.socket(sock_mod.AF_INET, sock_mod.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return '127.0.0.1'


def main():
    parser = argparse.ArgumentParser(
        description='Desktop Cast Provider v2.3 — 电脑公网投屏手机',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python desktop.py                                    # Relay mode (local)
  python desktop.py --relay wss://aiotvr.xyz/desktop/  # Relay mode (public)
  python desktop.py --direct                           # P2P direct (LAN)
  python desktop.py --direct --port 9803               # P2P custom port
  python desktop.py --room ABC123 --fps 15 --quality 70
  python desktop.py --scale 30 --monitor 2
        """)
    parser.add_argument('--direct', action='store_true', help='P2P direct mode (built-in server, no relay)')
    parser.add_argument('--port', type=int, default=9803, help='Port for P2P direct mode (default: 9803)')
    parser.add_argument('--relay', default=DEFAULT_RELAY, help='Relay server WebSocket URL')
    parser.add_argument('--token', default=DEFAULT_TOKEN, help='Auth token')
    parser.add_argument('--room', default=None, help='Room code (auto-generated if omitted)')
    parser.add_argument('--fps', type=int, default=DEFAULT_FPS, help='Target FPS (1-30)')
    parser.add_argument('--quality', type=int, default=DEFAULT_QUALITY, help='JPEG quality (10-100)')
    parser.add_argument('--scale', type=int, default=DEFAULT_SCALE, help='Scale percent (10-100)')
    parser.add_argument('--monitor', type=int, default=1, help='Monitor index (1=primary)')
    args = parser.parse_args()

    if args.direct:
        provider = DirectModeProvider(
            port=args.port,
            fps=max(1, min(30, args.fps)),
            quality=max(10, min(100, args.quality)),
            scale=max(10, min(100, args.scale)),
            monitor_idx=args.monitor,
        )
    else:
        provider = DesktopProvider(
            relay_url=args.relay,
            token=args.token,
            room=args.room,
            fps=max(1, min(30, args.fps)),
            quality=max(10, min(100, args.quality)),
            scale=max(10, min(100, args.scale)),
            monitor_idx=args.monitor,
        )
    t = provider.start()
    if t is not None:
        # DirectModeProvider returns a thread — block until it finishes
        t.join()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    except SystemExit as e:
        import traceback
        print(f"\n[FATAL-EXIT] SystemExit code={e.code}")
        traceback.print_exc()
    except Exception as e:
        import traceback
        print(f"\n[FATAL] {e}")
        traceback.print_exc()
        sys.exit(1)
