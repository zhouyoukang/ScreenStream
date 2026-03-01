"""
进程生命周期感知 — 进程启动/退出事件
=====================================
使用 psutil 轮询进程列表，检测新增/消失的进程。

单独测试:
  cd 认知代理
  python -m perception.process_monitor
"""

import time
import threading
import logging
import collections
from datetime import datetime

log = logging.getLogger("perception.process_monitor")

_events = collections.deque(maxlen=2000)
_running = False
_lock = threading.Lock()
_thread = None
_known_pids = {}  # pid -> {name, create_time}
_POLL_INTERVAL = 2.0  # 秒


def _scan():
    """扫描当前进程列表"""
    try:
        import psutil
    except ImportError:
        return {}
    procs = {}
    for p in psutil.process_iter(["pid", "name", "create_time"]):
        try:
            info = p.info
            procs[info["pid"]] = {
                "name": info["name"],
                "create_time": info.get("create_time", 0),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return procs


def _poll_loop():
    """轮询检测进程变化"""
    global _known_pids
    _known_pids = _scan()
    log.info("Process monitor started, initial: %d processes", len(_known_pids))

    while _running:
        time.sleep(_POLL_INTERVAL)
        if not _running:
            break

        current = _scan()
        now = datetime.now().isoformat(timespec="milliseconds")

        # 新增进程
        for pid, info in current.items():
            if pid not in _known_pids:
                evt = {
                    "type": "process_start",
                    "timestamp": now,
                    "pid": pid,
                    "name": info["name"],
                }
                with _lock:
                    _events.append(evt)

        # 消失进程
        for pid, info in _known_pids.items():
            if pid not in current:
                evt = {
                    "type": "process_exit",
                    "timestamp": now,
                    "pid": pid,
                    "name": info["name"],
                }
                with _lock:
                    _events.append(evt)

        _known_pids = current


def start():
    """启动进程监控"""
    global _running, _thread
    if _running:
        return {"ok": True, "status": "already running"}
    _running = True
    _thread = threading.Thread(target=_poll_loop, daemon=True, name="process-monitor")
    _thread.start()
    return {"ok": True, "status": "started"}


def stop():
    """停止进程监控"""
    global _running
    _running = False
    return {"ok": True, "status": "stopped"}


def get_events(limit=50, event_type=None):
    """获取进程事件"""
    with _lock:
        events = list(_events)
    if event_type:
        events = [e for e in events if e["type"] == event_type]
    return events[-limit:]


def get_stats():
    """统计"""
    with _lock:
        total = len(_events)
        starts = sum(1 for e in _events if e["type"] == "process_start")
        exits = sum(1 for e in _events if e["type"] == "process_exit")
    return {
        "running": _running,
        "total_events": total,
        "starts": starts,
        "exits": exits,
        "current_process_count": len(_known_pids),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("Monitoring process lifecycle... Press Ctrl+C to stop.")
    start()
    try:
        while True:
            time.sleep(3)
            stats = get_stats()
            events = get_events(limit=5)
            print(f"\n--- {stats['current_process_count']} procs, {stats['total_events']} events ---")
            for e in events:
                print(f"  {e['timestamp']} {e['type']}: {e['name']} (PID {e['pid']})")
    except KeyboardInterrupt:
        stop()
        print("\nStopped.")
