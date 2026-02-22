#!/usr/bin/env python3
"""
remote_agent.py — Remote Desktop Control Agent

Runs on a remote Windows machine, exposes HTTP API for:
  - Screenshot capture
  - Keyboard input (shortcuts, text)
  - Mouse click at coordinates
  - Window enumeration and management

Zero external dependencies beyond what's already installed (pyautogui, mss, Pillow).

Usage:
  python remote_agent.py                  # Start on port 9903
  python remote_agent.py --port 9904      # Custom port

API:
  GET  /health              Health check
  GET  /screenshot          Capture screen as JPEG (query: quality=70, monitor=0)
  GET  /windows             List visible windows with titles
  GET  /processes           List running processes (name, pid, mem_kb)
  GET  /clipboard           Get clipboard text
  GET  /sysinfo             System info (CPU/RAM/disk/uptime/screen)
  GET  /guard               MouseGuard status
  POST /key                 Send key: {"key": "enter"} or {"hotkey": ["ctrl","s"]}
  POST /click               Click: {"x": 500, "y": 300, "button": "left"}
  POST /type                Type text: {"text": "hello", "interval": 0.05}
  POST /move                Move mouse: {"x": 500, "y": 300}
  POST /drag                Drag: {"x1":0,"y1":0,"x2":100,"y2":100}
  POST /scroll              Scroll: {"x":0,"y":0,"clicks":3}
  POST /focus               Focus window: {"title": "Windsurf"} or {"hwnd": 12345}
  POST /window              Manage window: {"hwnd": 12345, "action": "maximize"}
  POST /clipboard           Set clipboard: {"text": "hello"}
  POST /shell               Execute command: {"cmd": "dir", "timeout": 15}
  POST /kill                Kill process: {"pid": 1234, "force": true}
  POST /volume              Volume: {"mute": true} or {"level": 50}
"""

import http.server
import json
import io
import sys
import os
import ctypes
import threading
import time
import subprocess
import struct
from ctypes import wintypes
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PORT = 9903
AUTH_TOKEN = None  # Set via --token flag


# ---------------------------------------------------------------------------
# MouseGuard — protect user from mouse/keyboard hijacking
# ---------------------------------------------------------------------------

class MouseGuard:
    """Monitors mouse position to detect user activity.
    When user is actively moving the mouse, automation actions are blocked
    for a cooldown period to prevent hijacking.

    API:
      guard.acquire() -> (bool, str)  — try to take control
      guard.release()                 — release after action
      guard.pause() / resume()        — manual toggle
      guard.status() -> dict          — current state
    """

    def __init__(self, cooldown=2.0):
        self.cooldown = cooldown
        self._paused = False           # True = guard disabled, automation always allowed
        self._enabled = True           # True = guard active, protects user
        self._last_user_activity = 0.0
        self._auto_acting = False
        self._prev_pos = (0, 0)
        self._lock = threading.Lock()
        self._blocked_count = 0
        self._total_requests = 0

    def start(self):
        """Start background mouse monitor thread."""
        t = threading.Thread(target=self._watch, daemon=True)
        t.start()
        print(f"  MouseGuard: ON (cooldown={self.cooldown}s)")

    def _watch(self):
        """Background: poll mouse position + keyboard activity via GetLastInputInfo."""
        try:
            import pyautogui
        except ImportError:
            return

        # Win32 GetLastInputInfo — detects ALL physical input (mouse + keyboard)
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        get_last_input = ctypes.windll.user32.GetLastInputInfo
        prev_input_tick = 0

        self._prev_pos = pyautogui.position()
        while True:
            time.sleep(0.1)
            try:
                pos = pyautogui.position()
                with self._lock:
                    user_active = False
                    # Check 1: mouse moved (not by automation)
                    if not self._auto_acting and pos != self._prev_pos:
                        user_active = True
                    # Check 2: any physical input (keyboard/mouse) via Win32
                    if not self._auto_acting and get_last_input(ctypes.byref(lii)):
                        if prev_input_tick and lii.dwTime != prev_input_tick:
                            user_active = True
                        prev_input_tick = lii.dwTime
                    if user_active:
                        self._last_user_activity = time.time()
                    self._prev_pos = pos
            except Exception:
                pass

    def acquire(self):
        """Try to acquire control for an automation action.
        Returns (allowed: bool, reason: str)."""
        with self._lock:
            self._total_requests += 1
            if not self._enabled:
                return True, "guard disabled"
            if self._paused:
                return True, "guard paused"
            elapsed = time.time() - self._last_user_activity
            if elapsed < self.cooldown:
                self._blocked_count += 1
                return False, f"user active {elapsed:.1f}s ago (cooldown {self.cooldown}s)"
            self._auto_acting = True
        return True, "ok"

    def release(self):
        """Release control after automation action completes."""
        try:
            import pyautogui
            with self._lock:
                self._prev_pos = pyautogui.position()
                self._auto_acting = False
        except Exception:
            with self._lock:
                self._auto_acting = False

    def pause(self):
        """Temporarily disable guard (allow all automation)."""
        self._paused = True

    def resume(self):
        """Re-enable guard protection."""
        self._paused = False

    def set_enabled(self, enabled):
        """Enable/disable guard entirely."""
        self._enabled = enabled

    def set_cooldown(self, seconds):
        """Update cooldown duration."""
        self.cooldown = max(0.5, min(seconds, 30.0))

    def status(self):
        with self._lock:
            elapsed = time.time() - self._last_user_activity
        return {
            "enabled": self._enabled,
            "paused": self._paused,
            "cooldown": self.cooldown,
            "user_idle_seconds": round(elapsed, 1),
            "can_automate": (elapsed >= self.cooldown or self._paused or not self._enabled),
            "blocked_count": self._blocked_count,
            "total_requests": self._total_requests,
        }


guard = MouseGuard()


def get_session_name():
    """Get session name, with WTS API fallback for scheduled task launches."""
    name = os.environ.get("SESSIONNAME", "")
    if name:
        return name
    try:
        kernel32 = ctypes.windll.kernel32
        wtsapi32 = ctypes.windll.wtsapi32
        WTS_CURRENT_SERVER_HANDLE = 0
        WTSWinStationName = 6
        session_id = kernel32.WTSGetActiveConsoleSessionId()
        # Try current process session ID instead
        pid = os.getpid()
        import ctypes.wintypes as wt
        process_id = wt.DWORD(0)
        kernel32.ProcessIdToSessionId(pid, ctypes.byref(process_id))
        sid = process_id.value
        buf = ctypes.c_wchar_p()
        size = wt.DWORD(0)
        if wtsapi32.WTSQuerySessionInformationW(
            WTS_CURRENT_SERVER_HANDLE, sid, WTSWinStationName,
            ctypes.byref(buf), ctypes.byref(size)
        ):
            result = buf.value
            wtsapi32.WTSFreeMemory(buf)
            return result or f"session-{sid}"
        return f"session-{sid}"
    except Exception:
        return "unknown"

# ---------------------------------------------------------------------------
# Screen capture (zero-dependency GDI + Pillow for JPEG)
# ---------------------------------------------------------------------------

def capture_screen(quality=70, monitor=0):
    """Capture screen as JPEG bytes. monitor=0 for primary, 1+ for others."""
    import mss
    from PIL import Image

    with mss.mss() as sct:
        mon_idx = min(monitor + 1, len(sct.monitors) - 1)
        img = sct.grab(sct.monitors[mon_idx])
        pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
        w, h = pil.size
        pil = pil.resize((w // 2, h // 2), Image.LANCZOS)
        buf = io.BytesIO()
        pil.save(buf, "JPEG", quality=quality)
        return buf.getvalue(), pil.size


# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------

def list_processes():
    """List running processes with PID, name, memory."""
    try:
        out = subprocess.check_output(
            ['tasklist', '/FO', 'CSV', '/NH'], text=True, timeout=5
        )
        procs = []
        for line in out.strip().split('\n'):
            parts = line.strip().strip('"').split('","')
            if len(parts) >= 5:
                procs.append({
                    "name": parts[0],
                    "pid": int(parts[1]),
                    "mem_kb": int(parts[4].replace(',', '').replace(' K', '').replace('K', '') or 0),
                })
        return procs
    except Exception as e:
        return {"error": str(e)}


def kill_process(pid, force=False):
    """Kill a process by PID."""
    try:
        cmd = ['taskkill', '/PID', str(pid)]
        if force:
            cmd.append('/F')
        out = subprocess.check_output(cmd, text=True, timeout=5, stderr=subprocess.STDOUT)
        return {"ok": True, "pid": pid, "output": out.strip()}
    except subprocess.CalledProcessError as e:
        return {"error": e.output.strip(), "pid": pid}


# ---------------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------------

def get_clipboard():
    """Get clipboard text via PowerShell subprocess (thread-safe)."""
    try:
        r = subprocess.run(
            ['powershell', '-NoProfile', '-Command', 'Get-Clipboard -Raw'],
            capture_output=True, timeout=5, encoding='utf-8', errors='replace'
        )
        return {"text": (r.stdout or "").rstrip('\r\n'), "ok": True}
    except Exception as e:
        return {"text": "", "ok": False, "error": str(e)}


def set_clipboard(text):
    """Set clipboard text via clip.exe (reliable from any thread)."""
    try:
        proc = subprocess.Popen(['clip'], stdin=subprocess.PIPE)
        proc.communicate(text.encode('utf-16le'))
        return {"ok": True, "length": len(text)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Shell execution
# ---------------------------------------------------------------------------

def exec_shell(cmd, timeout=15, cwd=None):
    """Execute a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=cwd
        )
        return {
            "ok": True,
            "stdout": result.stdout[-4000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "timeout": timeout}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# System info
# ---------------------------------------------------------------------------

def get_system_info():
    """Get system information: CPU, RAM, disk, uptime, display."""
    import platform
    info = {
        "hostname": platform.node(),
        "os": platform.platform(),
        "user": os.environ.get("USERNAME", "unknown"),
        "session": get_session_name(),
    }
    # Uptime
    try:
        info["uptime_sec"] = int(ctypes.windll.kernel32.GetTickCount64() / 1000)
    except: pass
    # Screen resolution
    try:
        info["screen_w"] = user32.GetSystemMetrics(0)
        info["screen_h"] = user32.GetSystemMetrics(1)
    except: pass
    # Memory
    try:
        class MEMSTAT(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        mem = MEMSTAT()
        mem.dwLength = ctypes.sizeof(MEMSTAT)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
        info["ram_total_mb"] = round(mem.ullTotalPhys / 1048576)
        info["ram_avail_mb"] = round(mem.ullAvailPhys / 1048576)
        info["ram_percent"] = mem.dwMemoryLoad
    except: pass
    # Disk
    try:
        free = ctypes.c_ulonglong()
        total = ctypes.c_ulonglong()
        ctypes.windll.kernel32.GetDiskFreeSpaceExW("C:\\", None, ctypes.byref(total), ctypes.byref(free))
        info["disk_total_gb"] = round(total.value / 1073741824, 1)
        info["disk_free_gb"] = round(free.value / 1073741824, 1)
    except: pass
    # Is locked?
    try:
        info["is_locked"] = not user32.GetForegroundWindow()
    except: pass
    return info


# ---------------------------------------------------------------------------
# Mouse move / drag (stealth: use Win32 SendInput)
# ---------------------------------------------------------------------------

def send_mouse_move(x, y):
    """Move mouse cursor to absolute coordinates using Win32 SendInput."""
    allowed, reason = guard.acquire()
    if not allowed:
        return {"blocked": True, "reason": reason}
    try:
        sx = user32.GetSystemMetrics(0)
        sy = user32.GetSystemMetrics(1)
        # Normalize to 0-65535 range for absolute move
        abs_x = int(x * 65535 / sx)
        abs_y = int(y * 65535 / sy)
        INPUT_MOUSE = 0
        MOUSEEVENTF_MOVE = 0x0001
        MOUSEEVENTF_ABSOLUTE = 0x8000

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                        ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                        ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]
        class INPUT(ctypes.Structure):
            _fields_ = [("type", ctypes.c_ulong), ("mi", MOUSEINPUT)]

        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi.dx = abs_x
        inp.mi.dy = abs_y
        inp.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        return {"ok": True, "x": x, "y": y}
    finally:
        guard.release()


def send_drag(x1, y1, x2, y2, button="left", duration=0.5):
    """Drag from (x1,y1) to (x2,y2)."""
    allowed, reason = guard.acquire()
    if not allowed:
        return {"blocked": True, "reason": reason}
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        pyautogui.moveTo(x1, y1)
        pyautogui.mouseDown(button=button)
        time.sleep(0.05)
        pyautogui.moveTo(x2, y2, duration=duration)
        pyautogui.mouseUp(button=button)
        return {"ok": True, "from": [x1, y1], "to": [x2, y2]}
    finally:
        guard.release()


# ---------------------------------------------------------------------------
# Volume control
# ---------------------------------------------------------------------------

def set_volume(level=None, mute=None):
    """Set system volume or toggle mute via key simulation."""
    import pyautogui
    pyautogui.FAILSAFE = False
    results = {}
    if mute is not None:
        pyautogui.press('volumemute')
        results["mute_toggled"] = True
    if level is not None:
        level = max(0, min(100, int(level)))
        results["level"] = level
        results["note"] = "use /shell with PowerShell for precise volume"
    results["ok"] = True
    return results


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------

def list_directory(path):
    """List directory contents with name, size, modified, is_dir."""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return {"error": "path not found", "path": path}
    if not os.path.isdir(path):
        return {"error": "not a directory", "path": path}
    items = []
    try:
        for name in os.listdir(path):
            full = os.path.join(path, name)
            try:
                st = os.stat(full)
                items.append({
                    "name": name,
                    "is_dir": os.path.isdir(full),
                    "size": st.st_size if not os.path.isdir(full) else 0,
                    "modified": int(st.st_mtime),
                })
            except (PermissionError, OSError):
                items.append({"name": name, "is_dir": False, "size": 0, "modified": 0, "error": "access denied"})
    except PermissionError:
        return {"error": "permission denied", "path": path}
    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    return {"path": path, "items": items, "count": len(items)}


def read_file_bytes(path, max_size=50*1024*1024):
    """Read file as bytes. Returns (bytes, mime_type) or error dict."""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return {"error": "file not found"}, None
    if os.path.getsize(path) > max_size:
        return {"error": f"file too large ({os.path.getsize(path)} bytes, max {max_size})"}, None
    ext = os.path.splitext(path)[1].lower()
    mime_map = {
        '.txt': 'text/plain', '.log': 'text/plain', '.md': 'text/plain',
        '.json': 'application/json', '.xml': 'text/xml', '.csv': 'text/csv',
        '.html': 'text/html', '.py': 'text/plain', '.js': 'text/plain',
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.gif': 'image/gif', '.pdf': 'application/pdf',
        '.zip': 'application/zip', '.exe': 'application/octet-stream',
    }
    mime = mime_map.get(ext, 'application/octet-stream')
    with open(path, 'rb') as f:
        return f.read(), mime


def write_file_from_b64(path, b64data):
    """Write base64-encoded data to a file."""
    import base64
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = base64.b64decode(b64data)
    with open(path, 'wb') as f:
        f.write(data)
    return {"ok": True, "path": path, "size": len(data)}


def delete_path(path):
    """Delete a file or empty directory."""
    import shutil
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return {"error": "not found"}
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)
    return {"ok": True, "path": path}


# ---------------------------------------------------------------------------
# Power management
# ---------------------------------------------------------------------------

def power_action(action):
    """Execute power action: shutdown/restart/sleep/lock/logoff."""
    cmds = {
        "shutdown": "shutdown /s /t 5",
        "restart": "shutdown /r /t 5",
        "cancel": "shutdown /a",
        "sleep": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
        "lock": "rundll32.exe user32.dll,LockWorkStation",
        "logoff": "shutdown /l",
    }
    if action not in cmds:
        return {"error": "unknown action", "valid": list(cmds.keys())}
    try:
        subprocess.Popen(cmds[action], shell=True)
        return {"ok": True, "action": action}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Network info
# ---------------------------------------------------------------------------

def get_network_info():
    """Get network adapters and active connections."""
    info = {"adapters": [], "connections": []}
    # IP addresses via ipconfig
    try:
        raw = subprocess.check_output(['ipconfig'], timeout=5)
        out = raw.decode('gbk', errors='replace')
        current = None
        for line in out.split('\n'):
            line = line.rstrip()
            if line and not line.startswith(' '):
                current = {"name": line.rstrip(':'), "ipv4": [], "ipv6": []}
                info["adapters"].append(current)
            elif current and 'IPv4' in line:
                ip = line.split(':')[-1].strip()
                current["ipv4"].append(ip)
            elif current and 'IPv6' in line:
                ip = line.split(':',1)[-1].strip() if ':' in line else ''
                current["ipv6"].append(ip)
        info["adapters"] = [a for a in info["adapters"] if a.get("ipv4") or a.get("ipv6")]
    except: pass
    # Active connections (top 30)
    try:
        raw = subprocess.check_output(['netstat', '-n', '-o'], timeout=5)
        out = raw.decode('gbk', errors='replace')
        for line in out.strip().split('\n')[4:34]:
            parts = line.split()
            if len(parts) >= 5:
                info["connections"].append({
                    "proto": parts[0], "local": parts[1],
                    "remote": parts[2], "state": parts[3], "pid": int(parts[4])
                })
    except: pass
    return info


# ---------------------------------------------------------------------------
# Services management
# ---------------------------------------------------------------------------

def list_services():
    """List Windows services with name, display_name, status."""
    try:
        raw = subprocess.check_output(
            ['sc', 'query', 'type=', 'service', 'state=', 'all'],
            timeout=10
        )
        out = raw.decode('gbk', errors='replace')
        services = []
        current = {}
        for line in out.split('\n'):
            line = line.strip()
            if line.startswith('SERVICE_NAME:'):
                if current.get('name'):
                    services.append(current)
                current = {'name': line.split(':', 1)[1].strip()}
            elif line.startswith('DISPLAY_NAME:'):
                current['display'] = line.split(':', 1)[1].strip()
            elif line.startswith('STATE'):
                parts = line.split()
                for p in parts:
                    if p in ('RUNNING', 'STOPPED', 'START_PENDING', 'STOP_PENDING', 'PAUSED'):
                        current['status'] = p
                        break
        if current.get('name'):
            services.append(current)
        return services
    except Exception as e:
        return {"error": str(e)}


def control_service(name, action):
    """Start/stop/restart a Windows service."""
    if action == 'restart':
        subprocess.run(['sc', 'stop', name], capture_output=True, timeout=10)
        time.sleep(1)
        r = subprocess.run(['sc', 'start', name], capture_output=True, text=True, timeout=10)
    elif action in ('start', 'stop'):
        r = subprocess.run(['sc', action, name], capture_output=True, text=True, timeout=10)
    else:
        return {"error": "unknown action", "valid": ["start", "stop", "restart"]}
    return {"ok": r.returncode == 0, "output": r.stdout.strip()[:500], "name": name, "action": action}


# ---------------------------------------------------------------------------
# Window precise positioning
# ---------------------------------------------------------------------------

def move_window(hwnd, x=None, y=None, w=None, h=None):
    """Move/resize a window to exact coordinates."""
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    flags = SWP_NOZORDER
    # Get current rect
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    cx, cy, cw, ch = rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    nx = x if x is not None else cx
    ny = y if y is not None else cy
    nw = w if w is not None else cw
    nh = h if h is not None else ch
    user32.SetWindowPos(hwnd, 0, nx, ny, nw, nh, flags)
    return {"ok": True, "hwnd": hwnd, "x": nx, "y": ny, "w": nw, "h": nh}


# ---------------------------------------------------------------------------
# Window management (Win32 API)
# ---------------------------------------------------------------------------

user32 = ctypes.windll.user32


def list_windows():
    """List all visible windows with titles."""
    windows = []

    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                cls_buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, cls_buf, 256)
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                windows.append({
                    "hwnd": hwnd,
                    "title": buf.value,
                    "class": cls_buf.value,
                    "x": rect.left, "y": rect.top,
                    "w": rect.right - rect.left,
                    "h": rect.bottom - rect.top,
                })
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return windows


def focus_window(hwnd=None, title=None):
    """Focus a window by hwnd or title substring."""
    if hwnd:
        target = hwnd
    elif title:
        for w in list_windows():
            if title.lower() in w["title"].lower():
                target = w["hwnd"]
                break
        else:
            return {"error": "window not found", "title": title}
    else:
        return {"error": "provide hwnd or title"}

    # AttachThreadInput trick for reliable focus
    cur_fg = user32.GetForegroundWindow()
    cur_tid = user32.GetWindowThreadProcessId(cur_fg, None)
    target_tid = user32.GetWindowThreadProcessId(target, None)
    user32.AttachThreadInput(cur_tid, target_tid, True)
    user32.BringWindowToTop(target)
    user32.SetForegroundWindow(target)
    user32.AttachThreadInput(cur_tid, target_tid, False)

    fg = user32.GetForegroundWindow()
    return {"focused": fg == target, "hwnd": target}


def manage_window(hwnd, action):
    """Manage window: maximize, minimize, restore, close."""
    actions = {
        "maximize": lambda: user32.ShowWindow(hwnd, 3),
        "minimize": lambda: user32.ShowWindow(hwnd, 6),
        "restore": lambda: user32.ShowWindow(hwnd, 9),
        "close": lambda: user32.PostMessageW(hwnd, 0x0010, 0, 0),  # WM_CLOSE
    }
    if action not in actions:
        return {"error": "unknown action", "valid": list(actions.keys())}
    actions[action]()
    return {"ok": True, "hwnd": hwnd, "action": action}


# ---------------------------------------------------------------------------
# Input simulation
# ---------------------------------------------------------------------------

def send_key(key=None, hotkey=None):
    """Send a key press or hotkey combination."""
    allowed, reason = guard.acquire()
    if not allowed:
        return {"blocked": True, "reason": reason}
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        if hotkey:
            pyautogui.hotkey(*hotkey)
            return {"ok": True, "hotkey": hotkey}
        elif key:
            pyautogui.press(key)
            return {"ok": True, "key": key}
        return {"error": "provide key or hotkey"}
    finally:
        guard.release()


def send_click(x, y, button="left", clicks=1):
    """Click at screen coordinates."""
    allowed, reason = guard.acquire()
    if not allowed:
        return {"blocked": True, "reason": reason, "x": x, "y": y}
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        pyautogui.click(x, y, clicks=clicks, button=button)
        return {"ok": True, "x": x, "y": y, "button": button}
    finally:
        guard.release()


def send_type(text, interval=0.05):
    """Type text string. Uses clipboard for non-ASCII (Chinese etc)."""
    allowed, reason = guard.acquire()
    if not allowed:
        return {"blocked": True, "reason": reason}
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        if text and not text.isascii():
            # Non-ASCII: use clipboard + Ctrl+V
            import subprocess
            proc = subprocess.Popen(['clip'], stdin=subprocess.PIPE)
            proc.communicate(text.encode('utf-16le'))
            # clip.exe expects UTF-16LE for Unicode
            time.sleep(0.05)
            pyautogui.hotkey('ctrl', 'v')
            return {"ok": True, "length": len(text), "method": "clipboard"}
        else:
            pyautogui.typewrite(text, interval=interval)
            return {"ok": True, "length": len(text), "method": "typewrite"}
    finally:
        guard.release()


def send_scroll(x, y, clicks, direction="vertical"):
    """Scroll at coordinates. clicks>0=up, clicks<0=down."""
    allowed, reason = guard.acquire()
    if not allowed:
        return {"blocked": True, "reason": reason}
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        if direction == "horizontal":
            pyautogui.hscroll(clicks, x=x, y=y)
        else:
            pyautogui.scroll(clicks, x=x, y=y)
        return {"ok": True, "x": x, "y": y, "clicks": clicks, "direction": direction}
    finally:
        guard.release()


# ---------------------------------------------------------------------------
# HTTP Server
# ---------------------------------------------------------------------------

class RemoteAgentHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # Suppress logs

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length > 0 else {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _check_auth(self):
        """Check token auth if enabled. Returns True if authorized."""
        if not AUTH_TOKEN:
            return True
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        token = qs.get("token", [None])[0]
        if not token:
            token = self.headers.get("X-Auth-Token", "")
        if token == AUTH_TOKEN:
            return True
        self._json({"error": "unauthorized"}, 401)
        return False

    def do_GET(self):
        if not self._check_auth():
            return
        path = urlparse(self.path).path
        qs = parse_qs(urlparse(self.path).query)

        if path == "/health":
            import platform
            self._json({
                "status": "ok",
                "hostname": platform.node(),
                "user": os.environ.get("USERNAME", "unknown"),
                "session": get_session_name(),
                "pid": os.getpid(),
                "guard": guard.status(),
            })

        elif path == "/guard":
            self._json(guard.status())

        elif path == "/screenshot":
            quality = int(qs.get("quality", ["70"])[0])
            monitor = int(qs.get("monitor", ["0"])[0])
            try:
                data, size = capture_screen(quality, monitor)
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("X-Image-Width", str(size[0]))
                self.send_header("X-Image-Height", str(size[1]))
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self._json({"error": str(e)}, 500)

        elif path == "/windows":
            self._json(list_windows())

        elif path == "/processes":
            self._json(list_processes())

        elif path == "/clipboard":
            self._json(get_clipboard())

        elif path == "/sysinfo":
            self._json(get_system_info())

        elif path == "/files":
            dir_path = qs.get("path", ["C:\\"])[0]
            self._json(list_directory(dir_path))

        elif path == "/file/download":
            file_path = qs.get("path", [""])[0]
            if not file_path:
                self._json({"error": "provide path"}, 400)
            else:
                result, mime = read_file_bytes(file_path)
                if isinstance(result, dict):
                    self._json(result, 400)
                else:
                    fname = os.path.basename(file_path)
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Length", str(len(result)))
                    self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(result)

        elif path == "/network":
            self._json(get_network_info())

        elif path == "/services":
            self._json(list_services())

        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()

        elif path == "/" or path == "/index.html":
            html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "remote_desktop.html")
            if os.path.exists(html_path):
                with open(html_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self._json({"error": "remote_desktop.html not found"}, 404)

        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._check_auth():
            return
        path = urlparse(self.path).path

        # Guard control endpoints (no body required)
        if path == "/guard/pause":
            guard.pause()
            self._json({"ok": True, "guard": guard.status()})
            return
        elif path == "/guard/resume":
            guard.resume()
            self._json({"ok": True, "guard": guard.status()})
            return
        elif path == "/guard/enable":
            guard.set_enabled(True)
            self._json({"ok": True, "guard": guard.status()})
            return
        elif path == "/guard/disable":
            guard.set_enabled(False)
            self._json({"ok": True, "guard": guard.status()})
            return

        try:
            data = self._body()
        except Exception:
            self._json({"error": "invalid json"}, 400)
            return

        if path == "/guard/config":
            cooldown = data.get("cooldown")
            if cooldown is not None:
                guard.set_cooldown(float(cooldown))
            self._json({"ok": True, "guard": guard.status()})

        elif path == "/key":
            self._json(send_key(data.get("key"), data.get("hotkey")))

        elif path == "/click":
            x = data.get("x", 0)
            y = data.get("y", 0)
            btn = data.get("button", "left")
            clicks = data.get("clicks", 1)
            self._json(send_click(x, y, btn, clicks))

        elif path == "/type":
            text = data.get("text", "")
            interval = data.get("interval", 0.05)
            self._json(send_type(text, interval))

        elif path == "/focus":
            self._json(focus_window(data.get("hwnd"), data.get("title")))

        elif path == "/window":
            hwnd = data.get("hwnd")
            action = data.get("action", "")
            if not hwnd:
                self._json({"error": "provide hwnd"}, 400)
            else:
                self._json(manage_window(hwnd, action))

        elif path == "/scroll":
            x = data.get("x", 0)
            y = data.get("y", 0)
            clicks = data.get("clicks", 3)
            direction = data.get("direction", "vertical")
            self._json(send_scroll(x, y, clicks, direction))

        elif path == "/move":
            self._json(send_mouse_move(data.get("x", 0), data.get("y", 0)))

        elif path == "/drag":
            self._json(send_drag(
                data.get("x1", 0), data.get("y1", 0),
                data.get("x2", 0), data.get("y2", 0),
                data.get("button", "left"),
                data.get("duration", 0.5)
            ))

        elif path == "/clipboard":
            self._json(set_clipboard(data.get("text", "")))

        elif path == "/shell":
            cmd = data.get("cmd", "")
            timeout = data.get("timeout", 15)
            cwd = data.get("cwd")
            if not cmd:
                self._json({"error": "provide cmd"}, 400)
            else:
                self._json(exec_shell(cmd, timeout, cwd))

        elif path == "/kill":
            pid = data.get("pid")
            if not pid:
                self._json({"error": "provide pid"}, 400)
            else:
                self._json(kill_process(pid, data.get("force", False)))

        elif path == "/volume":
            self._json(set_volume(data.get("level"), data.get("mute")))

        elif path == "/file/upload":
            fpath = data.get("path", "")
            b64 = data.get("data", "")
            if not fpath or not b64:
                self._json({"error": "provide path and data (base64)"}, 400)
            else:
                self._json(write_file_from_b64(fpath, b64))

        elif path == "/file/delete":
            fpath = data.get("path", "")
            if not fpath:
                self._json({"error": "provide path"}, 400)
            else:
                self._json(delete_path(fpath))

        elif path == "/power":
            action = data.get("action", "")
            self._json(power_action(action))

        elif path == "/service":
            name = data.get("name", "")
            action = data.get("action", "")
            if not name or not action:
                self._json({"error": "provide name and action"}, 400)
            else:
                self._json(control_service(name, action))

        elif path == "/window/move":
            hwnd = data.get("hwnd")
            if not hwnd:
                self._json({"error": "provide hwnd"}, 400)
            else:
                self._json(move_window(hwnd, data.get("x"), data.get("y"), data.get("w"), data.get("h")))

        elif path == "/guard":
            # POST /guard — configure MouseGuard
            if "enabled" in data:
                guard.set_enabled(data["enabled"])
            if "paused" in data:
                if data["paused"]:
                    guard.pause()
                else:
                    guard.resume()
            if "cooldown" in data:
                guard.set_cooldown(data["cooldown"])
            self._json(guard.status())

        else:
            self._json({"error": "not found"}, 404)


def main():
    port = PORT
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    # --no-guard flag to disable mouse protection
    if "--no-guard" in sys.argv:
        guard.set_enabled(False)
        print("  MouseGuard: DISABLED (--no-guard)")

    # --cooldown flag to set custom cooldown
    if "--cooldown" in sys.argv:
        idx = sys.argv.index("--cooldown")
        if idx + 1 < len(sys.argv):
            guard.set_cooldown(float(sys.argv[idx + 1]))

    # --token flag for authentication
    global AUTH_TOKEN
    if "--token" in sys.argv:
        idx = sys.argv.index("--token")
        if idx + 1 < len(sys.argv):
            AUTH_TOKEN = sys.argv[idx + 1]

    # Pre-import pyautogui to avoid slow first request
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
    except ImportError:
        pass

    # Start mouse guard monitor
    guard.start()

    server = ThreadingHTTPServer(("0.0.0.0", port), RemoteAgentHandler)
    import platform
    print(f"Remote Agent running at http://0.0.0.0:{port}")
    if AUTH_TOKEN:
        print(f"  Auth: token required (--token)")
    print(f"  Host: {platform.node()}")
    print(f"  User: {os.environ.get('USERNAME', '?')}")
    print(f"  Session: {os.environ.get('SESSIONNAME', '?')}")
    print(f"  PID: {os.getpid()}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
