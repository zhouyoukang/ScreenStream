"""
输入事件感知 — 键盘/鼠标事件流 + 目标控件绑定
================================================
键盘: 使用 keyboard 库全局Hook
鼠标: 使用 Win32 SetWindowsHookEx 低级Hook (ctypes)

事件格式:
  {
    "type": "key" | "mouse",
    "timestamp": "...",
    "data": { ... },
    "target": { "title": "...", "process": "..." }
  }

单独测试:
  cd 认知代理
  python -m perception.input_monitor
"""

import time
import ctypes
import ctypes.wintypes as wt
import threading
import logging
import json
import collections
from datetime import datetime

log = logging.getLogger("perception.input_monitor")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ---------------------------------------------------------------------------
# 事件缓冲区
# ---------------------------------------------------------------------------
_events = collections.deque(maxlen=10000)
_running = False
_lock = threading.Lock()


def _get_target():
    """获取当前前台窗口信息（轻量版，用于标注事件目标）"""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"title": "", "process": ""}
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    proc = ""
    try:
        import psutil
        proc = psutil.Process(pid.value).name()
    except Exception:
        pass
    return {"title": buf.value[:100], "process": proc, "hwnd": hwnd, "pid": pid.value}


def _emit(event_type, data):
    """将事件推入缓冲区"""
    evt = {
        "type": event_type,
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        "data": data,
        "target": _get_target(),
    }
    with _lock:
        _events.append(evt)


# ---------------------------------------------------------------------------
# 键盘监听 (keyboard库)
# ---------------------------------------------------------------------------
_kb_thread = None


def _start_keyboard():
    """启动键盘监听"""
    global _kb_thread
    try:
        import keyboard as kb
    except ImportError:
        log.warning("keyboard package not installed, skipping keyboard monitor")
        return

    def on_key(event):
        if not _running:
            return
        _emit("key", {
            "name": event.name,
            "scan_code": event.scan_code,
            "event_type": event.event_type,  # "down" or "up"
            "modifiers": _get_modifiers(),
        })

    def _get_modifiers():
        mods = []
        if kb.is_pressed("ctrl"):
            mods.append("ctrl")
        if kb.is_pressed("shift"):
            mods.append("shift")
        if kb.is_pressed("alt"):
            mods.append("alt")
        if kb.is_pressed("windows"):
            mods.append("win")
        return mods

    kb.hook(on_key)
    log.info("Keyboard monitor started")


# ---------------------------------------------------------------------------
# 鼠标监听 (Win32 低级Hook)
# ---------------------------------------------------------------------------
WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_MOUSEMOVE = 0x0200

MOUSE_EVENTS = {
    WM_LBUTTONDOWN: "left_down",
    WM_LBUTTONUP: "left_up",
    WM_RBUTTONDOWN: "right_down",
    WM_RBUTTONUP: "right_up",
    WM_MBUTTONDOWN: "middle_down",
    WM_MBUTTONUP: "middle_up",
    WM_MOUSEWHEEL: "scroll",
}

# 鼠标移动节流
_last_move_time = 0
_MOVE_THROTTLE = 0.1  # 最多10fps记录鼠标移动


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wt.POINT),
        ("mouseData", wt.DWORD),
        ("flags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wt.WPARAM, wt.LPARAM)
_mouse_hook = None
_mouse_thread = None


def _mouse_callback(nCode, wParam, lParam):
    """低级鼠标Hook回调"""
    global _last_move_time

    if nCode >= 0 and _running:
        ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents

        if wParam == WM_MOUSEMOVE:
            # 节流鼠标移动事件
            now = time.time()
            if now - _last_move_time < _MOVE_THROTTLE:
                return user32.CallNextHookEx(_mouse_hook, nCode, wParam, lParam)
            _last_move_time = now
            _emit("mouse", {
                "action": "move",
                "x": ms.pt.x,
                "y": ms.pt.y,
            })
        elif wParam in MOUSE_EVENTS:
            data = {
                "action": MOUSE_EVENTS[wParam],
                "x": ms.pt.x,
                "y": ms.pt.y,
            }
            if wParam == WM_MOUSEWHEEL:
                # mouseData高16位是滚动量（有符号）
                delta = ctypes.c_short(ms.mouseData >> 16).value
                data["delta"] = delta
            _emit("mouse", data)

    return user32.CallNextHookEx(_mouse_hook, nCode, wParam, lParam)


# 保持回调引用防止GC
_mouse_proc = HOOKPROC(_mouse_callback)


def _start_mouse():
    """在独立线程中运行鼠标Hook消息循环"""
    global _mouse_hook, _mouse_thread

    def _run():
        global _mouse_hook
        _mouse_hook = user32.SetWindowsHookExW(
            WH_MOUSE_LL, _mouse_proc, kernel32.GetModuleHandleW(None), 0
        )
        if not _mouse_hook:
            # Win32 LL hooks require a thread with a message pump.
            # When called from a non-main thread (e.g. server background),
            # this can silently fail. Keyboard monitoring still works via keyboard package.
            log.warning("Mouse hook not installed (requires message pump thread). Keyboard-only mode.")
            return

        log.info("Mouse monitor started (hook=%d)", _mouse_hook)

        msg = wt.MSG()
        while _running:
            # PeekMessage + sleep避免100% CPU
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):  # PM_REMOVE=1
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.01)

        user32.UnhookWindowsHookEx(_mouse_hook)
        _mouse_hook = None
        log.info("Mouse monitor stopped")

    _mouse_thread = threading.Thread(target=_run, daemon=True, name="mouse-hook")
    _mouse_thread.start()


# ---------------------------------------------------------------------------
# 公共API
# ---------------------------------------------------------------------------

def start():
    """启动输入监听（键盘+鼠标）"""
    global _running
    if _running:
        return {"ok": True, "status": "already running"}
    _running = True
    _start_keyboard()
    _start_mouse()
    return {"ok": True, "status": "started"}


def stop():
    """停止输入监听"""
    global _running
    _running = False
    try:
        import keyboard as kb
        kb.unhook_all()
    except Exception:
        pass
    return {"ok": True, "status": "stopped"}


def get_events(limit=100, since=None, event_type=None):
    """
    获取最近的输入事件。
    since: ISO时间戳，只返回此时间之后的事件
    event_type: "key" | "mouse" 过滤
    """
    with _lock:
        events = list(_events)

    if event_type:
        events = [e for e in events if e["type"] == event_type]
    if since:
        events = [e for e in events if e["timestamp"] > since]

    return events[-limit:]


def get_stats():
    """返回输入监听统计"""
    with _lock:
        total = len(_events)
        keys = sum(1 for e in _events if e["type"] == "key")
        mouse = sum(1 for e in _events if e["type"] == "mouse")
    return {
        "running": _running,
        "total_events": total,
        "key_events": keys,
        "mouse_events": mouse,
        "buffer_capacity": _events.maxlen,
    }


def clear():
    """清空事件缓冲区"""
    with _lock:
        _events.clear()
    return {"ok": True}


# ---------------------------------------------------------------------------
# 独立测试
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("Starting input monitor... Press Ctrl+C to stop.")
    start()
    try:
        while True:
            time.sleep(2)
            stats = get_stats()
            events = get_events(limit=5)
            print(f"\n--- {stats['total_events']} events ({stats['key_events']} keys, {stats['mouse_events']} mouse) ---")
            for e in events:
                print(f"  {e['timestamp']} {e['type']}: {json.dumps(e['data'], ensure_ascii=False)}")
    except KeyboardInterrupt:
        stop()
        print("\nStopped.")
