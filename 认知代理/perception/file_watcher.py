"""
文件系统感知 — 文件变化监控
============================
使用 Win32 ReadDirectoryChangesW 监控指定目录的文件变化。
不依赖 watchdog 包（未安装），纯 ctypes 实现。

单独测试:
  cd 认知代理
  python -m perception.file_watcher
"""

import ctypes
import ctypes.wintypes as wt
import threading
import logging
import collections
import os
import time
from datetime import datetime

log = logging.getLogger("perception.file_watcher")

kernel32 = ctypes.windll.kernel32

# Win32 constants
FILE_LIST_DIRECTORY = 0x0001
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000

FILE_NOTIFY_CHANGE_FILE_NAME = 0x00000001
FILE_NOTIFY_CHANGE_DIR_NAME = 0x00000002
FILE_NOTIFY_CHANGE_SIZE = 0x00000008
FILE_NOTIFY_CHANGE_LAST_WRITE = 0x00000010
FILE_NOTIFY_CHANGE_CREATION = 0x00000040

FILE_ACTION_ADDED = 1
FILE_ACTION_REMOVED = 2
FILE_ACTION_MODIFIED = 3
FILE_ACTION_RENAMED_OLD = 4
FILE_ACTION_RENAMED_NEW = 5

ACTION_MAP = {
    FILE_ACTION_ADDED: "created",
    FILE_ACTION_REMOVED: "deleted",
    FILE_ACTION_MODIFIED: "modified",
    FILE_ACTION_RENAMED_OLD: "renamed_from",
    FILE_ACTION_RENAMED_NEW: "renamed_to",
}

_events = collections.deque(maxlen=5000)
_running = False
_lock = threading.Lock()
_threads = []
_watch_dirs = []


class FILE_NOTIFY_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("NextEntryOffset", wt.DWORD),
        ("Action", wt.DWORD),
        ("FileNameLength", wt.DWORD),
        ("FileName", ctypes.c_wchar * 1),  # variable length
    ]


def _watch_directory(dir_path):
    """监控单个目录的文件变化"""
    handle = kernel32.CreateFileW(
        dir_path,
        FILE_LIST_DIRECTORY,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )

    if handle == -1 or handle == 0xFFFFFFFF:
        log.error("Cannot open directory: %s (error=%d)", dir_path, ctypes.get_last_error())
        return

    log.info("Watching: %s", dir_path)

    buf = ctypes.create_string_buffer(8192)
    bytes_returned = wt.DWORD()

    notify_filter = (
        FILE_NOTIFY_CHANGE_FILE_NAME |
        FILE_NOTIFY_CHANGE_DIR_NAME |
        FILE_NOTIFY_CHANGE_SIZE |
        FILE_NOTIFY_CHANGE_LAST_WRITE |
        FILE_NOTIFY_CHANGE_CREATION
    )

    while _running:
        result = kernel32.ReadDirectoryChangesW(
            handle,
            buf,
            len(buf),
            True,  # bWatchSubtree
            notify_filter,
            ctypes.byref(bytes_returned),
            None,  # lpOverlapped
            None,  # lpCompletionRoutine
        )

        if not result or not _running:
            break

        # 解析 FILE_NOTIFY_INFORMATION 链
        offset = 0
        while True:
            fni = ctypes.cast(
                ctypes.byref(buf, offset),
                ctypes.POINTER(FILE_NOTIFY_INFORMATION)
            ).contents

            # 提取文件名（变长字段）
            name_len = fni.FileNameLength // 2  # wchar = 2 bytes
            name_ptr = ctypes.cast(
                ctypes.byref(buf, offset + 12),  # 12 = 3 DWORDs
                ctypes.POINTER(ctypes.c_wchar * name_len)
            ).contents
            filename = name_ptr[:]

            action = ACTION_MAP.get(fni.Action, f"unknown({fni.Action})")

            evt = {
                "type": "file_change",
                "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                "action": action,
                "path": os.path.join(dir_path, filename),
                "filename": filename,
                "watch_dir": dir_path,
            }

            with _lock:
                _events.append(evt)

            if fni.NextEntryOffset == 0:
                break
            offset += fni.NextEntryOffset

    kernel32.CloseHandle(handle)
    log.info("Stopped watching: %s", dir_path)


def start(directories=None):
    """
    启动文件监控。
    directories: 要监控的目录列表。默认监控用户桌面和文档。
    """
    global _running, _watch_dirs

    if _running:
        return {"ok": True, "status": "already running"}

    if directories is None:
        # 默认监控几个常用目录
        home = os.path.expanduser("~")
        directories = [
            os.path.join(home, "Desktop"),
            os.path.join(home, "Documents"),
        ]

    _running = True
    _watch_dirs = [d for d in directories if os.path.isdir(d)]

    for d in _watch_dirs:
        t = threading.Thread(target=_watch_directory, args=(d,), daemon=True,
                             name=f"file-watcher-{os.path.basename(d)}")
        _threads.append(t)
        t.start()

    return {"ok": True, "status": "started", "watching": _watch_dirs}


def stop():
    """停止文件监控"""
    global _running
    _running = False
    return {"ok": True, "status": "stopped"}


def get_events(limit=50, action=None):
    """获取文件变化事件"""
    with _lock:
        events = list(_events)
    if action:
        events = [e for e in events if e["action"] == action]
    return events[-limit:]


def get_stats():
    """统计"""
    with _lock:
        total = len(_events)
        by_action = {}
        for e in _events:
            a = e["action"]
            by_action[a] = by_action.get(a, 0) + 1
    return {
        "running": _running,
        "watching": _watch_dirs,
        "total_events": total,
        "by_action": by_action,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    import sys
    dirs = sys.argv[1:] if len(sys.argv) > 1 else None
    print("Watching file changes... Press Ctrl+C to stop.")
    result = start(dirs)
    print(f"Watching: {result.get('watching', [])}")
    try:
        while True:
            time.sleep(2)
            events = get_events(limit=5)
            if events:
                for e in events:
                    print(f"  {e['timestamp']} {e['action']}: {e['filename']}")
    except KeyboardInterrupt:
        stop()
        print("\nStopped.")
