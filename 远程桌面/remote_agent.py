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
import sqlite3
import uuid
import socket
import hashlib
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

def capture_screen(quality=70, monitor=0, scale=50):
    """Capture screen as JPEG bytes. monitor=0 for primary, 1+ for others.
    scale=50 means half resolution (default), scale=100 means full res.
    Returns placeholder when screen is locked or capture fails."""
    try:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            mon_idx = min(monitor + 1, len(sct.monitors) - 1)
            img = sct.grab(sct.monitors[mon_idx])
            pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            # Detect all-black (locked screen produces black frame)
            if pil.getbbox() is None:
                return _locked_placeholder(pil.size)
            w, h = pil.size
            scale = max(10, min(100, scale))
            if scale < 100:
                nw, nh = int(w * scale / 100), int(h * scale / 100)
                pil = pil.resize((nw, nh), Image.LANCZOS)
            buf = io.BytesIO()
            pil.save(buf, "JPEG", quality=quality)
            return buf.getvalue(), pil.size
    except Exception:
        return _locked_placeholder((1920, 1080))


def _locked_placeholder(size):
    """Generate a placeholder JPEG for locked/unavailable screen."""
    from PIL import Image, ImageDraw
    w, h = size[0] // 2, size[1] // 2
    pil = Image.new("RGB", (w, h), (20, 20, 40))
    draw = ImageDraw.Draw(pil)
    draw.text((w // 2 - 60, h // 2 - 10), "SCREEN LOCKED", fill=(200, 200, 200))
    buf = io.BytesIO()
    pil.save(buf, "JPEG", quality=50)
    return buf.getvalue(), (w, h)


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

def wake_screen():
    """Wake the screen by simulating a key press (VK_SHIFT) via SendInput."""
    try:
        INPUT_KEYBOARD = 1
        VK_SHIFT = 0x10
        KEYEVENTF_KEYUP = 0x0002

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                        ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]
        class INPUT_KB(ctypes.Structure):
            _fields_ = [("type", ctypes.c_ulong), ("ki", KEYBDINPUT)]

        # Key down
        inp = INPUT_KB()
        inp.type = INPUT_KEYBOARD
        inp.ki.wVk = VK_SHIFT
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT_KB))
        # Key up
        inp2 = INPUT_KB()
        inp2.type = INPUT_KEYBOARD
        inp2.ki.wVk = VK_SHIFT
        inp2.ki.dwFlags = KEYEVENTF_KEYUP
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp2), ctypes.sizeof(INPUT_KB))
        return {"ok": True, "action": "wake", "method": "SendInput(VK_SHIFT)"}
    except Exception as e:
        return {"error": str(e)}


def get_screen_info():
    """Get combined screen info useful for mobile dashboard.
    Detects: interactive / disconnected / locked session states."""
    info = {"session_state": "unknown"}
    try:
        info["screen_w"] = user32.GetSystemMetrics(0)
        info["screen_h"] = user32.GetSystemMetrics(1)
    except: pass
    # Detect session state via WTS API
    try:
        wtsapi32 = ctypes.windll.wtsapi32
        kernel32 = ctypes.windll.kernel32
        import ctypes.wintypes as wt
        WTS_CURRENT_SERVER_HANDLE = 0
        WTSConnectState = 8
        pid = os.getpid()
        sid = wt.DWORD(0)
        kernel32.ProcessIdToSessionId(pid, ctypes.byref(sid))
        info["session_id"] = sid.value
        buf = ctypes.c_void_p()
        size = wt.DWORD(0)
        if wtsapi32.WTSQuerySessionInformationW(
            WTS_CURRENT_SERVER_HANDLE, sid.value, WTSConnectState,
            ctypes.byref(buf), ctypes.byref(size)
        ):
            state = ctypes.cast(buf, ctypes.POINTER(ctypes.c_int))[0]
            wtsapi32.WTSFreeMemory(buf)
            # WTS_CONNECTSTATE_CLASS: 0=Active, 1=Connected, 4=Disconnected, 5=Idle
            state_map = {0: "active", 1: "connected", 2: "connect_query",
                         3: "shadow", 4: "disconnected", 5: "idle",
                         6: "listen", 7: "reset", 8: "down", 9: "init"}
            info["session_state"] = state_map.get(state, f"unknown-{state}")
    except: pass
    # Lock detection
    try:
        hwnd = user32.GetForegroundWindow()
        info["is_locked"] = not bool(hwnd)
        if hwnd:
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            fg_title = buf.value
            info["active_window"] = fg_title
            info["active_hwnd"] = hwnd
            # Windows lock screen has specific window names
            if "LockApp" in fg_title or not fg_title:
                info["is_locked"] = True
    except: pass
    # If session is disconnected, mark as such
    if info.get("session_state") == "disconnected":
        info["is_locked"] = True
        info["disconnect_reason"] = "Session disconnected — use Wake or Reconnect"
    return info


def reconnect_session():
    """Try to reconnect a disconnected session to the console.
    Uses tscon to bring the session back to the physical console."""
    try:
        import ctypes.wintypes as wt
        kernel32 = ctypes.windll.kernel32
        pid = os.getpid()
        sid = wt.DWORD(0)
        kernel32.ProcessIdToSessionId(pid, ctypes.byref(sid))
        session_id = sid.value
        # tscon requires admin; try it
        result = subprocess.run(
            f'tscon {session_id} /dest:console',
            shell=True, capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return {"ok": True, "action": "reconnect", "session_id": session_id}
        else:
            return {"error": result.stderr.strip() or "tscon failed (need admin?)",
                    "session_id": session_id,
                    "hint": "Run agent as admin, or use RDP to reconnect"}
    except Exception as e:
        return {"error": str(e)}


def power_action(action, confirm=False):
    """Execute power action: shutdown/restart/sleep/lock/logoff.
    All destructive actions require confirm=True to prevent accidental disruption."""
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
    # Safety: all actions except cancel require explicit confirm
    if action != "cancel" and not confirm:
        return {"error": "confirm required", "action": action,
                "hint": "send confirm:true to execute"}
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
# Session Management & Cross-Account Control
# ---------------------------------------------------------------------------

def list_sessions():
    """List all Windows Terminal Server sessions."""
    try:
        # qwinsta is the same as 'query session' but more reliably in PATH
        try:
            raw = subprocess.check_output(['qwinsta'], timeout=5, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            raw = subprocess.check_output(
                [os.path.join(os.environ.get('SYSTEMROOT', 'C:\\Windows'), 'System32', 'qwinsta.exe')],
                timeout=5, stderr=subprocess.DEVNULL
            )
        out = raw.decode('gbk', errors='replace')
        sessions = []
        for line in out.strip().split('\n'):
            line_s = line.rstrip()
            if not line_s or '---' in line_s:
                continue
            active = line_s.startswith('>')
            line_s = line_s.lstrip('> ')
            # Parse columns: SESSIONNAME  USERNAME  ID  STATE  TYPE  DEVICE
            parts = line_s.split()
            if len(parts) < 3:
                continue
            # Find the state keyword to anchor parsing
            state_words = {'运行中', '断开', '侦听', 'Active', 'Disc', 'Listen', 'Conn'}
            state_idx = -1
            for i, p in enumerate(parts):
                if p in state_words:
                    state_idx = i
                    break
            if state_idx < 0:
                continue
            # ID is right before state
            try:
                sid = int(parts[state_idx - 1])
            except (ValueError, IndexError):
                continue
            name = parts[0]
            state = parts[state_idx]
            user = ' '.join(parts[1:state_idx - 1]) if state_idx > 2 else ''
            # Skip header row
            if name in ('会话名', 'SESSIONNAME'):
                continue
            sessions.append({
                "name": name,
                "user": user,
                "id": sid,
                "state": state,
                "active": active,
            })
        return sessions
    except Exception as e:
        return {"error": str(e)}


def remote_shell(computer, cmd, timeout=15):
    """Execute a command on a remote computer via PSRemoting."""
    try:
        # Escape single quotes in cmd for PowerShell
        safe_cmd = cmd.replace("'", "''")
        # Use Out-String to ensure text output is captured properly
        ps_cmd = f"Invoke-Command -ComputerName {computer} -ScriptBlock {{ {safe_cmd} }} | Out-String"
        result = subprocess.run(
            ['powershell', '-NoProfile', '-OutputFormat', 'Text', '-Command', ps_cmd],
            capture_output=True, timeout=timeout,
            encoding='utf-8', errors='replace'
        )
        return {
            "ok": True,
            "stdout": (result.stdout or "").rstrip()[-4000:],
            "stderr": (result.stderr or "").rstrip()[-2000:],
            "returncode": result.returncode,
            "computer": computer,
        }
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "timeout": timeout}
    except Exception as e:
        return {"error": str(e)}


def scan_agents(ports=None, hosts=None):
    """Scan for running remote_agent instances on LAN."""
    import urllib.request
    if ports is None:
        ports = [9903, 9904, 9905]
    if hosts is None:
        hosts = ['127.0.0.1', '127.0.0.2']
    agents = []
    for host in hosts:
        for port in ports:
            try:
                url = f'http://{host}:{port}/health'
                req = urllib.request.Request(url, method='GET')
                with urllib.request.urlopen(req, timeout=1) as resp:
                    data = json.loads(resp.read())
                    agents.append({
                        "host": host,
                        "port": port,
                        "url": f"http://{host}:{port}",
                        "status": "ok",
                        "user": data.get("user", "?"),
                        "hostname": data.get("hostname", "?"),
                        "session": data.get("session", "?"),
                    })
            except Exception:
                pass
    return agents


def deploy_agent_to_session(computer, port=9904):
    """Deploy and start remote_agent.py on another computer/session via PSRemoting."""
    agent_path = os.path.abspath(__file__).replace('\\', '\\\\')
    try:
        # Check if already running
        check_cmd = f'Invoke-Command -ComputerName {computer} -ScriptBlock {{ Get-Process python* -ErrorAction SilentlyContinue | ForEach-Object {{ (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine }} }}'
        check = subprocess.run(['powershell', '-NoProfile', '-Command', check_cmd],
                               capture_output=True, text=True, timeout=10)
        if f'--port {port}' in (check.stdout or '') and 'remote_agent' in (check.stdout or ''):
            return {"ok": True, "status": "already_running", "port": port, "computer": computer}

        # Start remote agent
        start_cmd = f'Invoke-Command -ComputerName {computer} -ScriptBlock {{ Start-Process python -ArgumentList \'"\'{agent_path}\'" --port {port} --no-guard\' -WindowStyle Hidden }}'
        result = subprocess.run(['powershell', '-NoProfile', '-Command', start_cmd],
                                capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            # Wait a moment and verify
            time.sleep(1)
            return {"ok": True, "port": port, "computer": computer, "status": "started"}
        else:
            return {"ok": False, "error": (result.stderr or result.stdout or 'unknown error')[:500],
                    "port": port, "computer": computer}
    except Exception as e:
        return {"error": str(e)}


def get_user_accounts():
    """List local Windows user accounts."""
    try:
        raw = subprocess.check_output(
            ['wmic', 'useraccount', 'where', 'LocalAccount=TRUE', 'get',
             'Name,SID,Status,Disabled', '/FORMAT:CSV'],
            timeout=10, stderr=subprocess.DEVNULL
        )
        out = raw.decode('gbk', errors='replace')
        accounts = []
        for line in out.strip().split('\n'):
            parts = line.strip().split(',')
            if len(parts) >= 5 and parts[0] != 'Node':
                accounts.append({
                    "name": parts[2] if len(parts) > 2 else '',
                    "disabled": parts[1].lower() == 'true' if len(parts) > 1 else False,
                    "sid": parts[3] if len(parts) > 3 else '',
                    "status": parts[4] if len(parts) > 4 else '',
                })
        return accounts
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Autonomous Guardian Engine — TaskQueue + Scheduler + Watchdog + Network
# Zero external dependencies: sqlite3 + threading + socket (all stdlib)
# ---------------------------------------------------------------------------

DB_PATH = None  # Set in main() to <script_dir>/guardian.db


def _db_path():
    global DB_PATH
    if DB_PATH is None:
        DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guardian.db")
    return DB_PATH


def _init_db():
    """Initialize SQLite tables for persistent task queue and rules."""
    conn = sqlite3.connect(_db_path())
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL DEFAULT 'immediate',
            action TEXT NOT NULL,
            params TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            priority INTEGER NOT NULL DEFAULT 5,
            created_at REAL NOT NULL,
            scheduled_at REAL,
            started_at REAL,
            finished_at REAL,
            result TEXT,
            error TEXT,
            retries INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 1,
            source TEXT DEFAULT 'api'
        );
        CREATE TABLE IF NOT EXISTS rules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            trigger_type TEXT NOT NULL,
            trigger_config TEXT NOT NULL DEFAULT '{}',
            action TEXT NOT NULL,
            params TEXT NOT NULL DEFAULT '{}',
            last_fired REAL,
            fire_count INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS event_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            source TEXT NOT NULL,
            event TEXT NOT NULL,
            detail TEXT
        );
        CREATE TABLE IF NOT EXISTS watched_processes (
            name TEXT PRIMARY KEY
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_scheduled ON tasks(scheduled_at);
        CREATE INDEX IF NOT EXISTS idx_rules_trigger ON rules(trigger_type);
        CREATE INDEX IF NOT EXISTS idx_event_log_ts ON event_log(ts);
    """)
    conn.close()


_log_event_counter = 0


def _log_event(source, event, detail=None):
    """Write to persistent event log (non-blocking, single connection)."""
    global _log_event_counter
    try:
        conn = sqlite3.connect(_db_path())
        conn.execute("INSERT INTO event_log (ts, source, event, detail) VALUES (?,?,?,?)",
                     (time.time(), source, event, detail))
        # Prune only every 50 writes to avoid overhead
        _log_event_counter += 1
        if _log_event_counter % 50 == 0:
            conn.execute("DELETE FROM event_log WHERE id NOT IN "
                         "(SELECT id FROM event_log ORDER BY ts DESC LIMIT 500)")
        conn.commit()
        conn.close()
    except Exception:
        pass


# --- Task Queue ---

class TaskQueue:
    """Persistent task queue backed by SQLite. Thread-safe."""

    def __init__(self):
        self._lock = threading.Lock()

    def add(self, action, params=None, task_type="immediate", priority=5,
            scheduled_at=None, max_retries=1, source="api"):
        """Add a task. Returns task ID."""
        tid = str(uuid.uuid4())[:8]
        now = time.time()
        with self._lock:
            conn = sqlite3.connect(_db_path())
            conn.execute(
                "INSERT INTO tasks (id,type,action,params,status,priority,created_at,scheduled_at,max_retries,source) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (tid, task_type, action, json.dumps(params or {}), "pending", priority,
                 now, scheduled_at, max_retries, source))
            conn.commit()
            conn.close()
        _log_event("taskqueue", "task_added", f"{tid}:{action}")
        return tid

    def get_pending(self, limit=10):
        """Get pending tasks ready to execute (immediate or past scheduled_at)."""
        now = time.time()
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status='pending' AND (scheduled_at IS NULL OR scheduled_at <= ?) "
            "ORDER BY priority ASC, created_at ASC LIMIT ?", (now, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_status(self, tid, status, result=None, error=None):
        """Update task status."""
        now = time.time()
        conn = sqlite3.connect(_db_path())
        if status == "running":
            conn.execute("UPDATE tasks SET status=?, started_at=? WHERE id=?", (status, now, tid))
        elif status in ("done", "failed"):
            conn.execute("UPDATE tasks SET status=?, finished_at=?, result=?, error=? WHERE id=?",
                         (status, now, result, error, tid))
        else:
            conn.execute("UPDATE tasks SET status=? WHERE id=?", (status, tid))
        conn.commit()
        conn.close()

    def retry_or_fail(self, tid, error_msg):
        """Retry task if retries left, otherwise mark failed."""
        conn = sqlite3.connect(_db_path())
        row = conn.execute("SELECT retries, max_retries FROM tasks WHERE id=?", (tid,)).fetchone()
        if row and row[0] < row[1]:
            conn.execute("UPDATE tasks SET status='pending', retries=retries+1, error=? WHERE id=?",
                         (error_msg, tid))
        else:
            conn.execute("UPDATE tasks SET status='failed', finished_at=?, error=? WHERE id=?",
                         (time.time(), error_msg, tid))
        conn.commit()
        conn.close()

    def list_all(self, status=None, limit=50):
        """List tasks, optionally filtered by status."""
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        if status:
            rows = conn.execute("SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC LIMIT ?",
                                (status, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                                (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def cancel(self, tid):
        """Cancel a pending task."""
        conn = sqlite3.connect(_db_path())
        r = conn.execute("UPDATE tasks SET status='cancelled' WHERE id=? AND status='pending'", (tid,))
        conn.commit()
        changed = r.rowcount
        conn.close()
        return changed > 0

    def clear_old(self, max_age_hours=24):
        """Remove completed/failed/cancelled tasks older than max_age."""
        cutoff = time.time() - max_age_hours * 3600
        conn = sqlite3.connect(_db_path())
        conn.execute("DELETE FROM tasks WHERE status IN ('done','failed','cancelled') AND created_at < ?", (cutoff,))
        conn.commit()
        conn.close()


task_queue = TaskQueue()


def execute_task(task):
    """Execute a single task. Returns (result_str, error_str)."""
    action = task["action"]
    params = json.loads(task["params"]) if isinstance(task["params"], str) else task["params"]

    try:
        if action == "shell":
            cmd = params.get("cmd", "")
            timeout = params.get("timeout", 30)
            cwd = params.get("cwd")
            r = exec_shell(cmd, timeout, cwd)
            if "error" in r:
                return None, r["error"]
            return json.dumps(r), None

        elif action == "key":
            return json.dumps(send_key(params.get("key"), params.get("hotkey"))), None

        elif action == "click":
            return json.dumps(send_click(params.get("x", 0), params.get("y", 0),
                                         params.get("button", "left"), params.get("clicks", 1))), None

        elif action == "type":
            return json.dumps(send_type(params.get("text", ""), params.get("interval", 0.05))), None

        elif action == "focus":
            return json.dumps(focus_window(params.get("hwnd"), params.get("title"))), None

        elif action == "power":
            return json.dumps(power_action(params.get("action", ""), confirm=True)), None

        elif action == "kill":
            return json.dumps(kill_process(params.get("pid"), params.get("force", False))), None

        elif action == "wakeup":
            return json.dumps(wake_screen()), None

        elif action == "service":
            return json.dumps(control_service(params.get("name", ""), params.get("action", ""))), None

        elif action == "remote_shell":
            return json.dumps(remote_shell(params.get("computer", "127.0.0.2"),
                                           params.get("cmd", ""), params.get("timeout", 15))), None

        elif action == "network_heal":
            return json.dumps(network_monitor.heal()), None

        else:
            return None, f"unknown action: {action}"

    except Exception as e:
        return None, str(e)


# --- Rule Engine ---

class RuleEngine:
    """Event-driven rule engine. Evaluates rules against triggers."""

    def add_rule(self, name, trigger_type, trigger_config, action, params):
        rid = str(uuid.uuid4())[:8]
        conn = sqlite3.connect(_db_path())
        conn.execute(
            "INSERT INTO rules (id,name,trigger_type,trigger_config,action,params,created_at) VALUES (?,?,?,?,?,?,?)",
            (rid, name, trigger_type, json.dumps(trigger_config), action, json.dumps(params), time.time()))
        conn.commit()
        conn.close()
        _log_event("rules", "rule_added", f"{rid}:{name}")
        return rid

    def remove_rule(self, rid):
        conn = sqlite3.connect(_db_path())
        r = conn.execute("DELETE FROM rules WHERE id=?", (rid,))
        conn.commit()
        changed = r.rowcount
        conn.close()
        return changed > 0

    def toggle_rule(self, rid, enabled):
        conn = sqlite3.connect(_db_path())
        conn.execute("UPDATE rules SET enabled=? WHERE id=?", (1 if enabled else 0, rid))
        conn.commit()
        conn.close()

    def list_rules(self):
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM rules ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def check_trigger(self, trigger_type, context=None):
        """Check all rules matching trigger_type and fire them."""
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        rules = conn.execute(
            "SELECT * FROM rules WHERE trigger_type=? AND enabled=1", (trigger_type,)).fetchall()
        conn.close()

        fired = []
        for rule in rules:
            rule = dict(rule)
            config = json.loads(rule["trigger_config"])
            # Cooldown check: don't fire more than once per minute
            if rule["last_fired"] and (time.time() - rule["last_fired"]) < config.get("cooldown", 60):
                continue
            if self._match(trigger_type, config, context):
                # Fire: create task
                params = json.loads(rule["params"])
                tid = task_queue.add(rule["action"], params, source=f"rule:{rule['id']}")
                # Update fire stats
                conn2 = sqlite3.connect(_db_path())
                conn2.execute("UPDATE rules SET last_fired=?, fire_count=fire_count+1 WHERE id=?",
                              (time.time(), rule["id"]))
                conn2.commit()
                conn2.close()
                fired.append({"rule_id": rule["id"], "rule_name": rule["name"], "task_id": tid})
                _log_event("rules", "rule_fired", f"{rule['id']}:{rule['name']}→{tid}")
        return fired

    def _match(self, trigger_type, config, context):
        """Check if trigger config matches context."""
        if trigger_type == "process_exit":
            return context and config.get("name", "").lower() in context.get("name", "").lower()
        elif trigger_type == "network_down":
            return True  # Fires whenever network goes down
        elif trigger_type == "network_up":
            return True  # Fires whenever network comes back
        elif trigger_type == "session_disconnect":
            return True
        elif trigger_type == "always":
            return True
        return False


rule_engine = RuleEngine()


# --- Network Monitor ---

class NetworkMonitor:
    """Monitors network connectivity, detects outages, auto-heals."""

    def __init__(self):
        self._state = "unknown"  # online / degraded / offline / unknown
        self._last_check = 0
        self._fail_count = 0
        self._heal_count = 0
        self._lock = threading.Lock()
        self._history = []  # last 20 state transitions

    def check(self):
        """Check network connectivity. Returns state dict."""
        targets = [
            ("8.8.8.8", 53, "google_dns"),
            ("223.5.5.5", 53, "alibaba_dns"),
            ("114.114.114.114", 53, "114_dns"),
        ]
        results = {}
        ok_count = 0
        for ip, port, name in targets:
            s = None
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                s.connect((ip, port))
                results[name] = True
                ok_count += 1
            except Exception:
                results[name] = False
            finally:
                if s:
                    try: s.close()
                    except Exception: pass

        # Also check default gateway (LAN) — use 'route print' (instant, no PowerShell)
        gateway_ok = False
        try:
            r = subprocess.run(['route', 'print', '0.0.0.0'],
                               capture_output=True, timeout=3,
                               encoding='gbk', errors='replace')
            gw = None
            for line in r.stdout.split('\n'):
                parts = line.split()
                # Route table: Destination Netmask Gateway Interface Metric
                if len(parts) >= 4 and parts[0] == '0.0.0.0' and parts[1] == '0.0.0.0':
                    candidate = parts[2]
                    # Validate it looks like an IPv4 address
                    if candidate.count('.') == 3 and candidate != '0.0.0.0':
                        gw = candidate
                        break
            if gw:
                p = subprocess.run(['ping', '-n', '1', '-w', '1500', gw],
                                   capture_output=True, timeout=5)
                gateway_ok = p.returncode == 0
                results["gateway"] = gateway_ok
                results["gateway_ip"] = gw
        except Exception:
            pass

        with self._lock:
            old_state = self._state
            self._last_check = time.time()
            if ok_count >= 2:
                self._state = "online"
                self._fail_count = 0
            elif ok_count == 1 or gateway_ok:
                self._state = "degraded"
                self._fail_count += 1
            else:
                self._fail_count += 1
                self._state = "offline" if self._fail_count >= 3 else "degraded"

            # State transition events
            if old_state != self._state:
                self._history.append({"from": old_state, "to": self._state, "ts": time.time()})
                if len(self._history) > 20:
                    self._history = self._history[-20:]
                _log_event("network", f"state_{self._state}", f"from={old_state} fails={self._fail_count}")
                # Fire rules
                if self._state == "offline":
                    rule_engine.check_trigger("network_down")
                elif self._state == "online" and old_state in ("offline", "degraded"):
                    rule_engine.check_trigger("network_up")

        return {
            "state": self._state,
            "checks": results,
            "fail_count": self._fail_count,
            "heal_count": self._heal_count,
            "last_check": self._last_check,
            "history": self._history[-5:],
        }

    def heal(self):
        """Attempt to restore network connectivity. Progressive escalation."""
        steps = []

        # Step 1: DHCP renew
        try:
            r = subprocess.run(['ipconfig', '/renew'], capture_output=True, text=True, timeout=15)
            steps.append({"step": "dhcp_renew", "ok": r.returncode == 0})
        except Exception as e:
            steps.append({"step": "dhcp_renew", "ok": False, "error": str(e)})

        # Quick re-check
        time.sleep(2)
        st = self.check()
        if st["state"] == "online":
            self._heal_count += 1
            _log_event("network", "healed", "dhcp_renew")
            return {"ok": True, "steps": steps, "state": "online"}

        # Step 2: WiFi reconnect
        try:
            # Get current WiFi profile
            r = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'],
                               capture_output=True, text=True, timeout=5)
            profile = None
            for line in r.stdout.split('\n'):
                if 'Profile' in line or '配置文件' in line:
                    # Handle both ASCII colon and Chinese full-width colon
                    profile = line.replace('：', ':').split(':')[-1].strip()
                    break
            if profile:
                subprocess.run(['netsh', 'wlan', 'disconnect'], capture_output=True, timeout=5)
                time.sleep(1)
                r2 = subprocess.run(['netsh', 'wlan', 'connect', f'name={profile}'],
                                    capture_output=True, text=True, timeout=10)
                steps.append({"step": "wifi_reconnect", "ok": r2.returncode == 0, "profile": profile})
                time.sleep(3)
            else:
                steps.append({"step": "wifi_reconnect", "ok": False, "error": "no wifi profile"})
        except Exception as e:
            steps.append({"step": "wifi_reconnect", "ok": False, "error": str(e)})

        st = self.check()
        if st["state"] == "online":
            self._heal_count += 1
            _log_event("network", "healed", "wifi_reconnect")
            return {"ok": True, "steps": steps, "state": "online"}

        # Step 3: Reset network adapter
        try:
            # Find active adapter
            r = subprocess.run(['powershell', '-NoProfile', '-Command',
                                'Get-NetAdapter | Where-Object {$_.Status -eq "Up"} | Select -First 1 -ExpandProperty Name'],
                               capture_output=True, text=True, timeout=10)
            adapter = r.stdout.strip()
            if adapter:
                subprocess.run(['powershell', '-NoProfile', '-Command',
                                f'Disable-NetAdapter -Name "{adapter}" -Confirm:$false'],
                               capture_output=True, timeout=10)
                time.sleep(2)
                subprocess.run(['powershell', '-NoProfile', '-Command',
                                f'Enable-NetAdapter -Name "{adapter}" -Confirm:$false'],
                               capture_output=True, timeout=10)
                steps.append({"step": "reset_adapter", "ok": True, "adapter": adapter})
                time.sleep(5)
            else:
                steps.append({"step": "reset_adapter", "ok": False, "error": "no active adapter"})
        except Exception as e:
            steps.append({"step": "reset_adapter", "ok": False, "error": str(e)})

        # Step 4: DNS flush
        try:
            subprocess.run(['ipconfig', '/flushdns'], capture_output=True, timeout=5)
            steps.append({"step": "dns_flush", "ok": True})
        except Exception as e:
            steps.append({"step": "dns_flush", "ok": False, "error": str(e)})

        st = self.check()
        self._heal_count += 1
        healed = st["state"] == "online"
        _log_event("network", "heal_attempt", f"healed={healed} steps={len(steps)}")
        return {"ok": healed, "steps": steps, "state": st["state"]}

    def status(self):
        return {
            "state": self._state,
            "fail_count": self._fail_count,
            "heal_count": self._heal_count,
            "last_check": self._last_check,
            "history": self._history[-5:],
        }


network_monitor = NetworkMonitor()


# --- Process Watchdog ---

class ProcessWatchdog:
    """Monitors critical processes, fires rules on exit. Watches persisted to DB."""

    def __init__(self):
        self._watched = {}  # name -> last_seen_pids
        self._lock = threading.Lock()
        # Restore watches from DB
        try:
            conn = sqlite3.connect(_db_path())
            rows = conn.execute("SELECT name FROM watched_processes").fetchall()
            conn.close()
            for (name,) in rows:
                self._watched[name] = set()
        except Exception:
            pass

    def check(self):
        """Scan processes, detect exits of watched processes."""
        if not self._watched:
            return {"ok": True, "watched": 0}
        try:
            current = {}
            out = subprocess.check_output(['tasklist', '/FO', 'CSV', '/NH'],
                                          text=True, timeout=5, stderr=subprocess.DEVNULL)
            for line in out.strip().split('\n'):
                parts = line.strip().strip('"').split('",')
                if len(parts) >= 2:
                    name = parts[0].lower()
                    pid = parts[1]
                    if name not in current:
                        current[name] = set()
                    current[name].add(pid)

            with self._lock:
                for name in list(self._watched.keys()):
                    if name in current:
                        # Still running — update PID set
                        self._watched[name] = current[name]
                    elif self._watched[name]:
                        # Was running (had PIDs), now gone → exited!
                        _log_event("watchdog", "process_exit", name)
                        rule_engine.check_trigger("process_exit", {"name": name})
                        self._watched[name] = set()  # Reset but keep watching
                    # else: never seen yet (empty set), skip
            return {"ok": True, "watched": len(self._watched)}
        except Exception as e:
            return {"error": str(e)}

    def watch(self, process_name):
        """Start watching a process by name (e.g. 'python.exe')."""
        name = process_name.lower()
        with self._lock:
            self._watched[name] = set()
        try:
            conn = sqlite3.connect(_db_path())
            conn.execute("INSERT OR IGNORE INTO watched_processes (name) VALUES (?)", (name,))
            conn.commit()
            conn.close()
        except Exception:
            pass
        return True

    def unwatch(self, process_name):
        name = process_name.lower()
        with self._lock:
            removed = self._watched.pop(name, None) is not None
        if removed:
            try:
                conn = sqlite3.connect(_db_path())
                conn.execute("DELETE FROM watched_processes WHERE name=?", (name,))
                conn.commit()
                conn.close()
            except Exception:
                pass
        return removed

    def list_watched(self):
        with self._lock:
            return list(self._watched.keys())


process_watchdog = ProcessWatchdog()


# --- Guardian Daemon (main loop) ---

class GuardianDaemon(threading.Thread):
    """Background daemon that runs the task executor, scheduler, and watchdogs."""

    def __init__(self):
        super().__init__(daemon=True, name="GuardianDaemon")
        self._running = True
        self._tick = 0
        self._stats = {"tasks_executed": 0, "tasks_failed": 0, "ticks": 0, "started_at": time.time()}

    def run(self):
        _log_event("guardian", "started", f"pid={os.getpid()}")
        while self._running:
            try:
                self._tick += 1
                self._stats["ticks"] = self._tick

                # Every tick (5s): execute pending tasks
                pending = task_queue.get_pending(limit=5)
                for task in pending:
                    task_queue.update_status(task["id"], "running")
                    result, error = execute_task(task)
                    if error:
                        task_queue.retry_or_fail(task["id"], error)
                        self._stats["tasks_failed"] += 1
                    else:
                        task_queue.update_status(task["id"], "done", result=result)
                        self._stats["tasks_executed"] += 1

                # Every 30s: network check
                if self._tick % 6 == 0:
                    net_status = network_monitor.check()
                    # Auto-heal if offline
                    if net_status["state"] == "offline":
                        _log_event("guardian", "auto_heal_triggered", "network offline")
                        network_monitor.heal()

                # Every 30s: process watchdog
                if self._tick % 6 == 1:
                    process_watchdog.check()

                # Every hour: clean old tasks
                if self._tick % 720 == 0:
                    task_queue.clear_old(24)

                # Every 5min: check cron rules
                if self._tick % 60 == 0:
                    self._check_cron_rules()

            except Exception as e:
                _log_event("guardian", "error", str(e))

            time.sleep(5)

    def _check_cron_rules(self):
        """Check time-based rules (simplified cron: hour:minute matching)."""
        now = time.localtime()
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        rules = conn.execute(
            "SELECT * FROM rules WHERE trigger_type='cron' AND enabled=1").fetchall()
        conn.close()
        for rule in rules:
            config = json.loads(rule["trigger_config"])
            hour = config.get("hour", "*")
            minute = config.get("minute", "*")
            if (hour == "*" or int(hour) == now.tm_hour) and \
               (minute == "*" or int(minute) == now.tm_min):
                # Check cooldown (don't fire same rule more than once per trigger window)
                cooldown = config.get("cooldown", 300)
                if rule["last_fired"] and (time.time() - rule["last_fired"]) < cooldown:
                    continue
                params = json.loads(rule["params"])
                tid = task_queue.add(rule["action"], params, source=f"cron:{rule['id']}")
                conn2 = sqlite3.connect(_db_path())
                conn2.execute("UPDATE rules SET last_fired=?, fire_count=fire_count+1 WHERE id=?",
                              (time.time(), rule["id"]))
                conn2.commit()
                conn2.close()
                _log_event("cron", "fired", f"{rule['id']}:{rule['name']}→{tid}")

    def stop(self):
        self._running = False
        _log_event("guardian", "stopped", "")

    def status(self):
        uptime = time.time() - self._stats["started_at"]
        return {
            **self._stats,
            "uptime_seconds": round(uptime),
            "uptime_human": f"{int(uptime//3600)}h{int((uptime%3600)//60)}m",
            "network": network_monitor.status(),
            "watched_processes": process_watchdog.list_watched(),
            "running": self._running,
        }


guardian = None  # Initialized in main()


def get_event_log(limit=30):
    """Get recent events from the guardian event log."""
    try:
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM event_log ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


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
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Auth-Token")
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
            scale = int(qs.get("scale", ["50"])[0])
            try:
                data, size = capture_screen(quality, monitor, scale)
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
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

        elif path == "/screen/info":
            self._json(get_screen_info())

        elif path == "/services":
            self._json(list_services())

        elif path == "/sessions":
            self._json(list_sessions())

        elif path == "/accounts":
            self._json(get_user_accounts())

        elif path == "/remote/agents":
            ports = [int(p) for p in qs.get("ports", ["9903,9904,9905"])[0].split(',')]
            hosts = qs.get("hosts", ["127.0.0.1,127.0.0.2"])[0].split(',')
            self._json(scan_agents(ports, hosts))

        # --- Guardian Engine GET endpoints ---
        elif path == "/guardian/status":
            self._json(guardian.status() if guardian else {"error": "guardian not started"})

        elif path == "/tasks":
            status_filter = qs.get("status", [None])[0]
            limit = int(qs.get("limit", ["50"])[0])
            self._json(task_queue.list_all(status=status_filter, limit=limit))

        elif path == "/rules":
            self._json(rule_engine.list_rules())

        elif path == "/network/status":
            self._json(network_monitor.check())

        elif path == "/watchdog":
            self._json({
                "watched": process_watchdog.list_watched(),
                "network": network_monitor.status(),
            })

        elif path == "/events":
            limit = int(qs.get("limit", ["30"])[0])
            self._json(get_event_log(limit=limit))

        elif path == "/manifest.json":
            mf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")
            if os.path.exists(mf_path):
                with open(mf_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/manifest+json")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
            else:
                self._json({"error": "manifest.json not found"}, 404)

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
            confirm = data.get("confirm", False)
            self._json(power_action(action, confirm=confirm))

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

        elif path == "/wakeup":
            self._json(wake_screen())

        elif path == "/session/reconnect":
            self._json(reconnect_session())

        elif path == "/remote/shell":
            computer = data.get("computer", "127.0.0.2")
            cmd = data.get("cmd", "")
            timeout = data.get("timeout", 15)
            if not cmd:
                self._json({"error": "provide cmd"}, 400)
            else:
                self._json(remote_shell(computer, cmd, timeout))

        elif path == "/remote/deploy":
            computer = data.get("computer", "127.0.0.2")
            port = data.get("port", 9904)
            self._json(deploy_agent_to_session(computer, port))

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

        # --- Guardian Engine POST endpoints ---
        elif path == "/tasks":
            action = data.get("action", "")
            if not action:
                self._json({"error": "provide action"}, 400)
            else:
                tid = task_queue.add(
                    action=action,
                    params=data.get("params", {}),
                    task_type=data.get("type", "immediate"),
                    priority=data.get("priority", 5),
                    scheduled_at=data.get("scheduled_at"),
                    max_retries=data.get("max_retries", 1),
                    source=data.get("source", "api"),
                )
                self._json({"ok": True, "task_id": tid})

        elif path == "/tasks/cancel":
            tid = data.get("id", "")
            if not tid:
                self._json({"error": "provide id"}, 400)
            else:
                self._json({"ok": task_queue.cancel(tid), "id": tid})

        elif path == "/tasks/clear":
            max_age = data.get("max_age_hours", 24)
            task_queue.clear_old(max_age)
            self._json({"ok": True})

        elif path == "/rules":
            name = data.get("name", "")
            trigger_type = data.get("trigger_type", "")
            action = data.get("action", "")
            if not name or not trigger_type or not action:
                self._json({"error": "provide name, trigger_type, action"}, 400)
            else:
                rid = rule_engine.add_rule(
                    name=name,
                    trigger_type=trigger_type,
                    trigger_config=data.get("trigger_config", {}),
                    action=action,
                    params=data.get("params", {}),
                )
                self._json({"ok": True, "rule_id": rid})

        elif path == "/rules/delete":
            rid = data.get("id", "")
            if not rid:
                self._json({"error": "provide id"}, 400)
            else:
                self._json({"ok": rule_engine.remove_rule(rid), "id": rid})

        elif path == "/rules/toggle":
            rid = data.get("id", "")
            enabled = data.get("enabled", True)
            if not rid:
                self._json({"error": "provide id"}, 400)
            else:
                rule_engine.toggle_rule(rid, enabled)
                self._json({"ok": True, "id": rid, "enabled": enabled})

        elif path == "/watchdog/watch":
            name = data.get("name", "")
            if not name:
                self._json({"error": "provide process name"}, 400)
            else:
                process_watchdog.watch(name)
                self._json({"ok": True, "watching": name})

        elif path == "/watchdog/unwatch":
            name = data.get("name", "")
            if not name:
                self._json({"error": "provide process name"}, 400)
            else:
                self._json({"ok": process_watchdog.unwatch(name), "name": name})

        elif path == "/network/heal":
            self._json(network_monitor.heal())

        elif path == "/network/check":
            self._json(network_monitor.check())

        elif path == "/events/clear":
            try:
                conn = sqlite3.connect(_db_path())
                conn.execute("DELETE FROM event_log")
                conn.commit()
                conn.close()
                _log_event("guardian", "events_cleared", "manual")
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)

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

    # Initialize Guardian Engine (SQLite + daemon thread)
    _init_db()
    global guardian
    guardian = GuardianDaemon()
    guardian.start()

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
    print(f"  Guardian: ACTIVE (TaskQueue + Scheduler + Watchdog + Network)")
    print(f"  DB: {_db_path()}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        guardian.stop()
        server.shutdown()


if __name__ == "__main__":
    main()
