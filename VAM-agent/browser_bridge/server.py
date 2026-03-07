"""
Desktop Browserization Server — 桌面应用浏览器化桥接服务器

☰乾·视觉捕获 + ☷坤·输入注入 + ☵坎·WebSocket传输 + ☲离·JPEG编码
☳震·Canvas渲染 + ☴巽·AI感知 + ☶艮·状态管理 + ☱兑·多客户端协同

道生一(捕获) → 一生二(编码+传输) → 二生三(渲染+输入+感知) → 三生万物(完全替代用户操作)

Architecture:
  Desktop App (VaM/Unity/Any)
      ↓ dxcam DXGI capture (GPU-accelerated, zero-impact)
      ↓ JPEG encode (OpenCV)
      ↓ WebSocket broadcast
  Browser (HTML5 Canvas)
      ↓ Playwright can see + interact
      ↓ Mouse/keyboard events → WebSocket → SendInput
  Desktop App receives input
"""

import asyncio
import ctypes
import ctypes.wintypes
import json
import logging
import threading
import time
import struct
from pathlib import Path
from typing import Dict, Set, Optional, Tuple

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# ── Windows API ──
user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

# SendInput structures
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001

SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
MOUSEEVENTF_VIRTUALDESK = 0x4000
SW_RESTORE = 9

EXTENDED_KEYS = {0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x24, 0x23, 0x21, 0x22,
                 0x5B, 0x5C, 0x6F, 0x90, 0x91}  # arrows,ins,del,home,end,pgup,pgdn,win,numpad/,numlock,scrolllock


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", INPUT_UNION)]


# ── Virtual Key Map ──
VK_MAP = {
    'enter': 0x0D, 'return': 0x0D, 'escape': 0x1B, 'esc': 0x1B,
    'tab': 0x09, 'space': 0x20, 'backspace': 0x08,
    'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
    'arrowleft': 0x25, 'arrowup': 0x26, 'arrowright': 0x27, 'arrowdown': 0x28,
    'delete': 0x2E, 'home': 0x24, 'end': 0x23,
    'pageup': 0x21, 'pagedown': 0x22, 'insert': 0x2D,
    'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
    'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
    'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
    'control': 0x11, 'ctrl': 0x11, 'shift': 0x10, 'alt': 0x12,
    'meta': 0x5B, 'capslock': 0x14, 'numlock': 0x90,
}

log = logging.getLogger("bridge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")


# ════════════════════════════════════════════════════════════════
#  ☰ 乾 · 视觉捕获 — Screen Capture Engine
# ════════════════════════════════════════════════════════════════

class CaptureEngine:
    """DXGI Desktop Duplication capture (dxcam) with fallback to mss."""

    def __init__(self):
        self._dxcam = None
        self._mss = None
        self._mode = None
        self._target_region = None  # (left, top, right, bottom)
        self._target_hwnd = None
        self._fps = 15
        self._quality = 70  # JPEG quality

    def init_dxcam(self, monitor_idx: int = 0):
        try:
            import dxcam
            self._dxcam = dxcam.create(output_idx=monitor_idx, output_color="BGR")
            self._mode = "dxcam"
            log.info("CaptureEngine: dxcam initialized (monitor %d)", monitor_idx)
            # Always init mss as fallback
            self._init_mss_fallback()
            return True
        except Exception as e:
            log.warning("CaptureEngine: dxcam failed: %s, falling back to mss", e)
            return False

    def _init_mss_fallback(self):
        if self._mss is None:
            import mss
            self._mss = mss.mss()

    def init_mss(self):
        import mss
        self._mss = mss.mss()
        self._mode = "mss"
        log.info("CaptureEngine: mss initialized")

    def set_target_window(self, hwnd: int):
        self._target_hwnd = hwnd
        self._update_region()

    def set_target_region(self, left: int, top: int, right: int, bottom: int):
        self._target_region = (left, top, right, bottom)
        self._target_hwnd = None

    def _update_region(self):
        if self._target_hwnd:
            # Auto-restore from minimized
            if user32.IsIconic(self._target_hwnd):
                user32.ShowWindow(self._target_hwnd, SW_RESTORE)
                time.sleep(0.3)
                log.info("Auto-restored minimized window (hwnd=%d)", self._target_hwnd)
            rect = ctypes.wintypes.RECT()
            if user32.GetWindowRect(self._target_hwnd, ctypes.byref(rect)):
                self._target_region = (rect.left, rect.top, rect.right, rect.bottom)

    def ensure_foreground(self):
        """Bring target window to foreground for input injection."""
        if self._target_hwnd:
            if user32.IsIconic(self._target_hwnd):
                user32.ShowWindow(self._target_hwnd, SW_RESTORE)
                time.sleep(0.3)
            # ALT key trick to bypass SetForegroundWindow restriction
            user32.keybd_event(0x12, 0, 0x0001, 0)  # ALT down
            user32.keybd_event(0x12, 0, 0x0003, 0)  # ALT up
            user32.SetForegroundWindow(self._target_hwnd)
            user32.BringWindowToTop(self._target_hwnd)
            time.sleep(0.2)
            log.info("ensure_foreground: hwnd=%d", self._target_hwnd)
            return True
        return False

    def capture(self) -> Optional[np.ndarray]:
        """Capture a frame. Returns BGR numpy array or None."""
        if self._target_hwnd:
            self._update_region()
            # Try PrintWindow for z-order independent capture
            frame = self._capture_printwindow()
            if frame is not None:
                # Verify frame is not all black (DirectX apps often return black)
                if np.mean(frame) > 5:
                    return frame
                else:
                    log.debug("PrintWindow returned black frame, falling back")

        # Multi-monitor: if region has negative coords, dxcam can't handle it
        use_dxcam = (self._mode == "dxcam" and self._dxcam and
                     (self._target_region is None or
                      min(self._target_region[0], self._target_region[1]) >= 0))

        frame = None
        if use_dxcam:
            frame = self._capture_dxcam()
        if frame is None:
            self._init_mss_fallback()
            frame = self._capture_mss()
        return frame

    def _capture_printwindow(self) -> Optional[np.ndarray]:
        """Capture window content using PrintWindow API (z-order independent)."""
        try:
            hwnd = self._target_hwnd
            if not hwnd or not user32.IsWindow(hwnd):
                return None

            # Get client area size
            rect = ctypes.wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            w, h = rect.right, rect.bottom
            if w < 10 or h < 10:
                return None

            gdi32 = ctypes.windll.gdi32

            # Create compatible DC and bitmap
            hwnd_dc = user32.GetDC(hwnd)
            mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
            bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
            gdi32.SelectObject(mem_dc, bitmap)

            # PrintWindow with PW_CLIENTONLY | PW_RENDERFULLCONTENT
            PW_CLIENTONLY = 0x1
            PW_RENDERFULLCONTENT = 0x2
            result = ctypes.windll.user32.PrintWindow(
                hwnd, mem_dc, PW_CLIENTONLY | PW_RENDERFULLCONTENT
            )

            if not result:
                # Fallback: try without PW_RENDERFULLCONTENT
                result = ctypes.windll.user32.PrintWindow(hwnd, mem_dc, PW_CLIENTONLY)

            if result:
                # Read bitmap data
                class BITMAPINFOHEADER(ctypes.Structure):
                    _fields_ = [
                        ('biSize', ctypes.c_ulong), ('biWidth', ctypes.c_long),
                        ('biHeight', ctypes.c_long), ('biPlanes', ctypes.c_ushort),
                        ('biBitCount', ctypes.c_ushort), ('biCompression', ctypes.c_ulong),
                        ('biSizeImage', ctypes.c_ulong), ('biXPelsPerMeter', ctypes.c_long),
                        ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', ctypes.c_ulong),
                        ('biClrImportant', ctypes.c_ulong),
                    ]

                bmi = BITMAPINFOHEADER()
                bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                bmi.biWidth = w
                bmi.biHeight = -h  # top-down
                bmi.biPlanes = 1
                bmi.biBitCount = 32
                bmi.biCompression = 0  # BI_RGB

                buf = ctypes.create_string_buffer(w * h * 4)
                gdi32.GetDIBits(mem_dc, bitmap, 0, h, buf, ctypes.byref(bmi), 0)

                frame = np.frombuffer(buf, dtype=np.uint8).reshape((h, w, 4))
                frame = frame[:, :, :3]  # BGRA → BGR

            # Cleanup GDI objects
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(hwnd, hwnd_dc)

            return frame if result else None

        except Exception as e:
            log.debug("PrintWindow capture failed: %s", e)
            return None

    def _capture_dxcam(self) -> Optional[np.ndarray]:
        try:
            if self._target_region:
                frame = self._dxcam.grab(region=self._target_region)
            else:
                frame = self._dxcam.grab()
            if frame is None:
                time.sleep(0.02)
                if self._target_region:
                    frame = self._dxcam.grab(region=self._target_region)
                else:
                    frame = self._dxcam.grab()
            return frame
        except Exception as e:
            log.debug("dxcam grab failed: %s", e)
            return None

    def _capture_mss(self) -> Optional[np.ndarray]:
        try:
            if self._mss is None:
                import mss
                self._mss = mss.mss()
            if self._target_region:
                l, t, r, b = self._target_region
                mon = {"left": l, "top": t, "width": r - l, "height": b - t}
            else:
                mon = self._mss.monitors[1]
            shot = self._mss.grab(mon)
            # mss .bgra returns raw BGRA bytes; drop alpha → BGR for OpenCV
            frame = np.frombuffer(shot.bgra, dtype=np.uint8)
            frame = frame.reshape((shot.height, shot.width, 4))
            frame = frame[:, :, :3]  # BGRA → BGR
            return frame
        except Exception as e:
            log.warning("mss grab failed: %s", e)
            return None

    def encode_jpeg(self, frame: np.ndarray, quality: int = None) -> bytes:
        """Encode BGR frame to JPEG bytes."""
        q = quality or self._quality
        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, q])
        return buf.tobytes()


# ════════════════════════════════════════════════════════════════
#  ☷ 坤 · 输入注入 — Input Injection Engine
# ════════════════════════════════════════════════════════════════

class InputEngine:
    """Inject mouse/keyboard events into the target window (multi-monitor aware)."""

    def __init__(self):
        # Use virtual screen for multi-monitor support
        self._virt_x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        self._virt_y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        self._virt_w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        self._virt_h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        log.info("InputEngine: virtual screen (%d,%d) %dx%d",
                 self._virt_x, self._virt_y, self._virt_w, self._virt_h)

    def _send_input(self, *inputs):
        arr = (INPUT * len(inputs))(*inputs)
        user32.SendInput(len(inputs), ctypes.byref(arr), ctypes.sizeof(INPUT))

    def _abs_coords(self, screen_x: int, screen_y: int):
        """Convert screen coordinates to 0-65535 range over virtual desktop."""
        ax = int((screen_x - self._virt_x) * 65535 / self._virt_w)
        ay = int((screen_y - self._virt_y) * 65535 / self._virt_h)
        return ax, ay

    def mouse_move(self, screen_x: int, screen_y: int):
        ax, ay = self._abs_coords(screen_x, screen_y)
        inp = INPUT(type=INPUT_MOUSE)
        inp.ii.mi.dx = ax
        inp.ii.mi.dy = ay
        inp.ii.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        self._send_input(inp)

    def mouse_click(self, screen_x: int, screen_y: int,
                    button: str = "left", action: str = "click"):
        self.mouse_move(screen_x, screen_y)
        time.sleep(0.01)

        down_flag = {"left": MOUSEEVENTF_LEFTDOWN, "right": MOUSEEVENTF_RIGHTDOWN,
                     "middle": MOUSEEVENTF_MIDDLEDOWN}.get(button, MOUSEEVENTF_LEFTDOWN)
        up_flag = {"left": MOUSEEVENTF_LEFTUP, "right": MOUSEEVENTF_RIGHTUP,
                   "middle": MOUSEEVENTF_MIDDLEUP}.get(button, MOUSEEVENTF_LEFTUP)

        abs_x, abs_y = self._abs_coords(screen_x, screen_y)

        if action in ("click", "down", "dblclick"):
            inp = INPUT(type=INPUT_MOUSE)
            inp.ii.mi.dx = abs_x
            inp.ii.mi.dy = abs_y
            inp.ii.mi.dwFlags = down_flag | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
            self._send_input(inp)

        if action in ("click", "up", "dblclick"):
            time.sleep(0.02)
            inp = INPUT(type=INPUT_MOUSE)
            inp.ii.mi.dx = abs_x
            inp.ii.mi.dy = abs_y
            inp.ii.mi.dwFlags = up_flag | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
            self._send_input(inp)

        if action == "dblclick":
            time.sleep(0.05)
            for flag in (down_flag, up_flag):
                inp = INPUT(type=INPUT_MOUSE)
                inp.ii.mi.dx = abs_x
                inp.ii.mi.dy = abs_y
                inp.ii.mi.dwFlags = flag | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
                self._send_input(inp)
                time.sleep(0.02)

    def mouse_scroll(self, screen_x: int, screen_y: int, delta: int):
        self.mouse_move(screen_x, screen_y)
        time.sleep(0.01)
        ax, ay = self._abs_coords(screen_x, screen_y)
        inp = INPUT(type=INPUT_MOUSE)
        inp.ii.mi.dx = ax
        inp.ii.mi.dy = ay
        inp.ii.mi.mouseData = ctypes.c_ulong(delta * 120).value
        inp.ii.mi.dwFlags = MOUSEEVENTF_WHEEL | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        self._send_input(inp)

    def key_press(self, key: str, action: str = "press"):
        """Send key event. key can be 'a', 'enter', 'f1', etc."""
        vk = VK_MAP.get(key.lower())
        if vk is None and len(key) == 1:
            vk = ord(key.upper())
        if vk is None:
            log.warning("Unknown key: %s", key)
            return

        flags = KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_KEYS else 0

        if action in ("press", "down"):
            inp = INPUT(type=INPUT_KEYBOARD)
            inp.ii.ki.wVk = vk
            inp.ii.ki.dwFlags = flags
            self._send_input(inp)

        if action in ("press", "up"):
            time.sleep(0.02)
            inp = INPUT(type=INPUT_KEYBOARD)
            inp.ii.ki.wVk = vk
            inp.ii.ki.dwFlags = flags | KEYEVENTF_KEYUP
            self._send_input(inp)

    def key_combo(self, keys: list):
        """Send key combination like ['ctrl', 'z']."""
        for k in keys:
            self.key_press(k, action="down")
            time.sleep(0.02)
        for k in reversed(keys):
            self.key_press(k, action="up")
            time.sleep(0.02)


# ════════════════════════════════════════════════════════════════
#  ☵ 坎 · WebSocket传输 + ☶ 艮 · 状态管理 — Bridge Server
# ════════════════════════════════════════════════════════════════

app = FastAPI(title="Desktop Browser Bridge", version="1.0")
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Global state
capture_engine = CaptureEngine()
input_engine = InputEngine()
clients: Set[WebSocket] = set()
server_state = {
    "running": False,
    "target_hwnd": 0,
    "target_title": "",
    "fps": 15,
    "quality": 70,
    "frame_count": 0,
    "client_count": 0,
    "capture_mode": "none",
    "stream_width": 0,
    "stream_height": 0,
}
_capture_task = None


def find_window_by_class(class_name: str) -> int:
    hwnd = user32.FindWindowW(class_name, None)
    return hwnd if hwnd else 0


def find_window_by_title(title: str) -> int:
    hwnd = user32.FindWindowW(None, title)
    return hwnd if hwnd else 0


def get_window_title(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def enum_windows() -> list:
    """List all visible top-level windows."""
    results = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            title = get_window_title(hwnd)
            if title and len(title) > 0:
                results.append({"hwnd": hwnd, "title": title})
        return True

    user32.EnumWindows(callback, 0)
    return results


# Shared frame buffer — capture thread writes, WebSocket reads
_latest_jpeg: Optional[bytes] = None
_jpeg_lock = threading.Lock()
_frame_event = threading.Event()


def _capture_thread_func():
    """Background thread: capture frames → encode JPEG → store in shared buffer."""
    import mss as mss_mod

    log.info("Capture thread started (fps=%d, region=%s)",
             server_state["fps"], capture_engine._target_region)

    # Create thread-local mss instance (mss is not thread-safe)
    local_mss = mss_mod.mss()
    first_logged = False

    while server_state["running"]:
        interval = 1.0 / max(1, server_state["fps"])
        t0 = time.monotonic()

        try:
            # Update target region
            if capture_engine._target_hwnd:
                capture_engine._update_region()

            region = capture_engine._target_region
            if not region:
                time.sleep(0.1)
                continue

            l, t, r, b = region
            mon = {"left": l, "top": t, "width": r - l, "height": b - t}

            shot = local_mss.grab(mon)
            frame = np.frombuffer(shot.bgra, dtype=np.uint8)
            frame = frame.reshape((shot.height, shot.width, 4))
            frame = frame[:, :, :3]  # BGRA → BGR

            jpeg = capture_engine.encode_jpeg(frame, server_state["quality"])

            global _latest_jpeg
            with _jpeg_lock:
                _latest_jpeg = jpeg

            server_state["stream_width"] = frame.shape[1]
            server_state["stream_height"] = frame.shape[0]
            server_state["frame_count"] += 1
            _frame_event.set()

            if not first_logged:
                first_logged = True
                log.info("First frame: %dx%d, %d bytes JPEG",
                         frame.shape[1], frame.shape[0], len(jpeg))

        except Exception as e:
            if not first_logged:
                log.error("Capture error: %s", e, exc_info=True)
                first_logged = True
            time.sleep(0.1)

        elapsed = time.monotonic() - t0
        sleep_time = max(0, interval - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)

    log.info("Capture thread stopped")


def process_input_event(event: dict):
    """Process input event from browser client."""
    etype = event.get("type")
    region = capture_engine._target_region

    if not region:
        return

    rl, rt, rr, rb = region
    rw, rh = rr - rl, rb - rt

    # Convert relative coordinates (0-1) to screen coordinates
    rx = event.get("x", 0)
    ry = event.get("y", 0)
    sx = int(rl + rx * rw)
    sy = int(rt + ry * rh)

    if etype == "mousemove":
        input_engine.mouse_move(sx, sy)

    elif etype == "mousedown":
        btn = event.get("button", "left")
        input_engine.mouse_click(sx, sy, button=btn, action="down")

    elif etype == "mouseup":
        btn = event.get("button", "left")
        input_engine.mouse_click(sx, sy, button=btn, action="up")

    elif etype == "click":
        btn = event.get("button", "left")
        input_engine.mouse_click(sx, sy, button=btn, action="click")

    elif etype == "dblclick":
        input_engine.mouse_click(sx, sy, action="dblclick")

    elif etype == "wheel":
        delta = event.get("delta", 0)
        input_engine.mouse_scroll(sx, sy, delta)

    elif etype == "keydown":
        key = event.get("key", "")
        if "+" in key:
            input_engine.key_combo(key.split("+"))
        else:
            input_engine.key_press(key, action="down")

    elif etype == "keyup":
        key = event.get("key", "")
        input_engine.key_press(key, action="up")

    elif etype == "keypress":
        key = event.get("key", "")
        if "+" in key:
            input_engine.key_combo(key.split("+"))
        else:
            input_engine.key_press(key, action="press")


# ── Routes ──

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    return html_path.read_text(encoding="utf-8")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    server_state["client_count"] = len(clients)
    log.info("Client connected (%d total)", len(clients))

    async def sender():
        """Send latest frames to this client."""
        last_count = 0
        while True:
            # Poll for new frames (capture thread updates frame_count)
            fc = server_state["frame_count"]
            if fc > last_count:
                last_count = fc
                with _jpeg_lock:
                    jpeg = _latest_jpeg
                if jpeg:
                    try:
                        await ws.send_bytes(jpeg)
                    except Exception:
                        break
            await asyncio.sleep(1.0 / max(1, server_state["fps"]))

    async def receiver():
        """Receive input events from this client."""
        try:
            while True:
                data = await ws.receive_text()
                try:
                    event = json.loads(data)
                    process_input_event(event)
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            pass

    send_task = asyncio.create_task(sender())
    try:
        await receiver()
    finally:
        send_task.cancel()
        clients.discard(ws)
        server_state["client_count"] = len(clients)
        log.info("Client disconnected (%d remaining)", len(clients))


@app.get("/api/status")
async def api_status():
    return JSONResponse(server_state)


@app.get("/api/windows")
async def api_windows():
    return JSONResponse(enum_windows())


@app.post("/api/target")
async def api_set_target(body: dict):
    hwnd = body.get("hwnd")
    title = body.get("title")
    class_name = body.get("class")

    if hwnd:
        hwnd = int(hwnd)
    elif class_name:
        hwnd = find_window_by_class(class_name)
    elif title:
        hwnd = find_window_by_title(title)

    if hwnd and user32.IsWindow(hwnd):
        capture_engine.set_target_window(hwnd)
        server_state["target_hwnd"] = hwnd
        server_state["target_title"] = get_window_title(hwnd)
        return JSONResponse({"ok": True, "hwnd": hwnd, "title": server_state["target_title"]})

    return JSONResponse({"ok": False, "error": "Window not found"}, status_code=404)


@app.post("/api/config")
async def api_config(body: dict):
    if "fps" in body:
        server_state["fps"] = max(1, min(60, int(body["fps"])))
    if "quality" in body:
        server_state["quality"] = max(10, min(100, int(body["quality"])))
        capture_engine._quality = server_state["quality"]
    return JSONResponse(server_state)


@app.post("/api/input")
async def api_input(body: dict):
    """REST endpoint for input injection (alternative to WebSocket)."""
    process_input_event(body)
    return JSONResponse({"ok": True})


@app.post("/api/focus")
async def api_focus():
    """Bring target window to foreground."""
    ok = capture_engine.ensure_foreground()
    return JSONResponse({"ok": ok, "hwnd": server_state["target_hwnd"]})


@app.post("/api/restore")
async def api_restore():
    """Restore target window from minimized."""
    hwnd = capture_engine._target_hwnd
    if hwnd and user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.3)
        capture_engine._update_region()
        return JSONResponse({"ok": True, "restored": True})
    return JSONResponse({"ok": True, "restored": False})


@app.get("/api/screenshot")
async def api_screenshot():
    """Get a single screenshot as JPEG."""
    frame = capture_engine.capture()
    if frame is None:
        return JSONResponse({"error": "No capture"}, status_code=500)
    jpeg = capture_engine.encode_jpeg(frame, 90)
    from fastapi.responses import Response
    return Response(content=jpeg, media_type="image/jpeg")


_capture_thread: Optional[threading.Thread] = None


@app.on_event("startup")
async def startup():
    global _capture_thread

    # Try dxcam first, fallback to mss
    if not capture_engine.init_dxcam():
        capture_engine.init_mss()
    server_state["capture_mode"] = capture_engine._mode

    # Auto-detect VaM window
    hwnd = find_window_by_class("UnityWndClass")
    if hwnd:
        capture_engine.set_target_window(hwnd)
        server_state["target_hwnd"] = hwnd
        server_state["target_title"] = get_window_title(hwnd)
        log.info("Auto-detected VaM: hwnd=%d title='%s'", hwnd, server_state["target_title"])
    else:
        log.info("No VaM window found. Use /api/target to set target.")

    server_state["running"] = True
    _capture_thread = threading.Thread(target=_capture_thread_func, daemon=True, name="capture")
    _capture_thread.start()


@app.on_event("shutdown")
async def shutdown():
    server_state["running"] = False
    if _capture_thread:
        _capture_thread.join(timeout=3)


# ── Main ──

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Desktop Browser Bridge")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=9870, help="Bind port")
    parser.add_argument("--fps", type=int, default=15, help="Target FPS")
    parser.add_argument("--quality", type=int, default=70, help="JPEG quality")
    parser.add_argument("--hwnd", type=int, default=0, help="Target window HWND")
    parser.add_argument("--title", default="", help="Target window title")
    args = parser.parse_args()

    server_state["fps"] = args.fps
    server_state["quality"] = args.quality
    capture_engine._quality = args.quality

    if args.hwnd:
        capture_engine.set_target_window(args.hwnd)
        server_state["target_hwnd"] = args.hwnd
        server_state["target_title"] = get_window_title(args.hwnd)
    elif args.title:
        hwnd = find_window_by_title(args.title)
        if hwnd:
            capture_engine.set_target_window(hwnd)
            server_state["target_hwnd"] = hwnd
            server_state["target_title"] = args.title

    log.info("Starting Desktop Browser Bridge on %s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
