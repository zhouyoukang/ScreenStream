"""
窗口焦点追踪 — 记录窗口切换链
================================
使用 Win32 SetWinEventHook 监听焦点变化事件，
记录完整的窗口焦点链（谁→谁，停留多久）。

单独测试:
  cd 认知代理
  python -m perception.window_tracker
"""

import time
import ctypes
import ctypes.wintypes as wt
import threading
import logging
import json
import collections
from datetime import datetime

log = logging.getLogger("perception.window_tracker")

user32 = ctypes.windll.user32

# ---------------------------------------------------------------------------
# 焦点链记录
# ---------------------------------------------------------------------------
_focus_chain = collections.deque(maxlen=1000)
_current_focus = None
_current_focus_since = None
_running = False
_lock = threading.Lock()
_thread = None

# WinEvent constants
EVENT_SYSTEM_FOREGROUND = 0x0003
EVENT_OBJECT_FOCUS = 0x8005
WINEVENT_OUTOFCONTEXT = 0x0000


def _get_window_info(hwnd):
    """获取窗口信息"""
    if not hwnd or not user32.IsWindow(hwnd):
        return None

    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)

    cls_buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls_buf, 256)

    pid = wt.DWORD()
    tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    proc = ""
    try:
        import psutil
        proc = psutil.Process(pid.value).name()
    except Exception:
        pass

    return {
        "hwnd": hwnd,
        "title": buf.value[:150],
        "class": cls_buf.value,
        "pid": pid.value,
        "process": proc,
    }


# Win32回调类型
WINEVENTPROC = ctypes.WINFUNCTYPE(
    None,
    ctypes.c_void_p,  # hWinEventHook
    wt.DWORD,          # event
    wt.HWND,           # hwnd
    ctypes.c_long,     # idObject
    ctypes.c_long,     # idChild
    wt.DWORD,          # idEventThread
    wt.DWORD,          # dwmsEventTime
)


def _on_focus_change(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
    """焦点变化回调"""
    global _current_focus, _current_focus_since

    if not _running:
        return

    # 只关注前台窗口变化
    if event != EVENT_SYSTEM_FOREGROUND:
        return

    now = datetime.now()
    info = _get_window_info(hwnd)
    if not info or not info["title"]:
        return

    with _lock:
        # 记录上一个焦点的停留时间
        if _current_focus and _current_focus_since:
            duration = (now - _current_focus_since).total_seconds()
            entry = {
                "timestamp": _current_focus_since.isoformat(timespec="milliseconds"),
                "window": _current_focus,
                "duration_s": round(duration, 2),
                "next": info["title"][:80],
            }
            _focus_chain.append(entry)

        _current_focus = info
        _current_focus_since = now


# 保持回调引用防止GC
_event_proc = WINEVENTPROC(_on_focus_change)
_hook_handle = None


def _run_hook():
    """在独立线程中运行WinEvent Hook消息循环"""
    global _hook_handle

    _hook_handle = user32.SetWinEventHook(
        EVENT_SYSTEM_FOREGROUND,  # eventMin
        EVENT_SYSTEM_FOREGROUND,  # eventMax
        None,                     # hmodWinEventProc
        _event_proc,
        0,                        # idProcess (0=all)
        0,                        # idThread (0=all)
        WINEVENT_OUTOFCONTEXT,
    )

    if not _hook_handle:
        log.error("Failed to set WinEvent hook")
        return

    log.info("Window focus tracker started (hook=%s)", _hook_handle)

    # 记录初始焦点
    global _current_focus, _current_focus_since
    fg = user32.GetForegroundWindow()
    if fg:
        _current_focus = _get_window_info(fg)
        _current_focus_since = datetime.now()

    msg = wt.MSG()
    while _running:
        if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        else:
            time.sleep(0.05)

    user32.UnhookWinEvent(_hook_handle)
    _hook_handle = None
    log.info("Window focus tracker stopped")


# ---------------------------------------------------------------------------
# 公共API
# ---------------------------------------------------------------------------

def start():
    """启动窗口焦点追踪"""
    global _running, _thread
    if _running:
        return {"ok": True, "status": "already running"}
    _running = True
    _thread = threading.Thread(target=_run_hook, daemon=True, name="window-tracker")
    _thread.start()
    return {"ok": True, "status": "started"}


def stop():
    """停止窗口焦点追踪"""
    global _running
    _running = False
    return {"ok": True, "status": "stopped"}


def get_focus_chain(limit=50):
    """获取焦点链"""
    with _lock:
        chain = list(_focus_chain)
    return chain[-limit:]


def get_current():
    """获取当前焦点窗口"""
    with _lock:
        if _current_focus:
            duration = 0
            if _current_focus_since:
                duration = (datetime.now() - _current_focus_since).total_seconds()
            return {
                "window": _current_focus,
                "since": _current_focus_since.isoformat(timespec="milliseconds") if _current_focus_since else None,
                "duration_s": round(duration, 2),
            }
    return None


def get_stats():
    """统计信息"""
    with _lock:
        chain = list(_focus_chain)
    # 统计每个应用的累计时间
    app_time = {}
    for entry in chain:
        proc = entry["window"].get("process", "unknown")
        app_time[proc] = app_time.get(proc, 0) + entry["duration_s"]

    # 排序
    top_apps = sorted(app_time.items(), key=lambda x: -x[1])[:10]

    return {
        "running": _running,
        "total_switches": len(chain),
        "top_apps": [{"process": p, "total_seconds": round(t, 1)} for p, t in top_apps],
    }


# ---------------------------------------------------------------------------
# 独立测试
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("Tracking window focus... Press Ctrl+C to stop.")
    start()
    try:
        while True:
            time.sleep(3)
            cur = get_current()
            stats = get_stats()
            if cur:
                w = cur["window"]
                print(f"  [{cur['duration_s']:.1f}s] {w.get('process','')} — {w.get('title','')[:60]}")
            print(f"  Switches: {stats['total_switches']}")
    except KeyboardInterrupt:
        stop()
        print("\nStopped.")
