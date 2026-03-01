"""
事件流录制/查询 — SQLite持久化
================================
统一存储所有感知模块产生的事件，支持按时间/类型/会话查询。

会话模型:
  POST /session/start → 开始录制（创建session_id）
  POST /session/stop  → 停止录制
  GET  /session/events → 查询事件

单独测试:
  cd 认知代理
  python -m semantics.event_stream
"""

import sqlite3
import json
import time
import uuid
import threading
import logging
import os
import sys

log = logging.getLogger("semantics.event_stream")

# 延迟导入config避免路径问题
def _get_db_path():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import DB_PATH
    return str(DB_PATH)


_db_path = None
_lock = threading.Lock()
_current_session = None
_batch_buffer = []
_BATCH_SIZE = 50  # 批量写入阈值
_BATCH_INTERVAL = 2.0  # 秒


def _get_conn():
    """获取SQLite连接（线程本地）"""
    global _db_path
    if _db_path is None:
        _db_path = _get_db_path()
    conn = sqlite3.connect(_db_path, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    """初始化数据库表"""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            stopped_at TEXT,
            event_count INTEGER DEFAULT 0,
            size_bytes INTEGER DEFAULT 0,
            metadata TEXT
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            source TEXT NOT NULL,
            data TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp);
    """)
    conn.commit()
    conn.close()
    log.info("Database initialized: %s", _db_path)


# ---------------------------------------------------------------------------
# 会话管理
# ---------------------------------------------------------------------------

def start_session(metadata=None):
    """开始一个新的录制会话"""
    global _current_session
    if _current_session:
        return {"error": "session already active", "session_id": _current_session}

    sid = str(uuid.uuid4())[:8]
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    conn = _get_conn()
    conn.execute(
        "INSERT INTO sessions (id, started_at, metadata) VALUES (?, ?, ?)",
        (sid, now, json.dumps(metadata or {}))
    )
    conn.commit()
    conn.close()

    _current_session = sid
    log.info("Session started: %s", sid)
    return {"ok": True, "session_id": sid, "started_at": now}


def stop_session():
    """停止当前录制会话"""
    global _current_session
    if not _current_session:
        return {"error": "no active session"}

    # 刷新缓冲区
    _flush_batch()

    sid = _current_session
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    conn = _get_conn()
    # 更新会话统计
    row = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(LENGTH(data)), 0) FROM events WHERE session_id = ?",
        (sid,)
    ).fetchone()
    event_count = row[0]
    size_bytes = row[1]

    conn.execute(
        "UPDATE sessions SET stopped_at = ?, event_count = ?, size_bytes = ? WHERE id = ?",
        (now, event_count, size_bytes, sid)
    )
    conn.commit()
    conn.close()

    _current_session = None
    log.info("Session stopped: %s (%d events, %d bytes)", sid, event_count, size_bytes)
    return {"ok": True, "session_id": sid, "event_count": event_count, "size_bytes": size_bytes}


def get_current_session():
    """获取当前活跃会话"""
    return _current_session


# ---------------------------------------------------------------------------
# 事件录制
# ---------------------------------------------------------------------------

def record(event_type, source, data):
    """
    录制一个事件。
    event_type: "screen_snapshot" | "key" | "mouse" | "focus_change" | "file_change" | "process"
    source: 产生事件的模块名
    data: 事件数据（dict）
    """
    if not _current_session:
        return  # 未开始会话，静默丢弃

    evt = {
        "session_id": _current_session,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.") + f"{time.time() % 1:.3f}"[2:],
        "event_type": event_type,
        "source": source,
        "data": json.dumps(data, ensure_ascii=False),
    }

    with _lock:
        _batch_buffer.append(evt)
        if len(_batch_buffer) >= _BATCH_SIZE:
            _flush_batch_locked()


def _flush_batch():
    """刷新批量缓冲区"""
    with _lock:
        _flush_batch_locked()


def _flush_batch_locked():
    """刷新（需在锁内调用）"""
    global _batch_buffer
    if not _batch_buffer:
        return

    batch = _batch_buffer[:]
    _batch_buffer = []

    try:
        conn = _get_conn()
        conn.executemany(
            "INSERT INTO events (session_id, timestamp, event_type, source, data) VALUES (?, ?, ?, ?, ?)",
            [(e["session_id"], e["timestamp"], e["event_type"], e["source"], e["data"]) for e in batch]
        )
        conn.commit()
        conn.close()
    except Exception as ex:
        log.error("Failed to flush events: %s", ex)


# 后台定时刷新
def _periodic_flush():
    while True:
        time.sleep(_BATCH_INTERVAL)
        _flush_batch()


_flush_thread = threading.Thread(target=_periodic_flush, daemon=True, name="event-flush")
_flush_thread.start()


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------

def query_events(session_id=None, event_type=None, since=None, until=None, limit=100, offset=0):
    """查询事件"""
    conn = _get_conn()
    conditions = []
    params = []

    if session_id:
        conditions.append("session_id = ?")
        params.append(session_id)
    elif _current_session:
        conditions.append("session_id = ?")
        params.append(_current_session)

    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type)
    if since:
        conditions.append("timestamp >= ?")
        params.append(since)
    if until:
        conditions.append("timestamp <= ?")
        params.append(until)

    where = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT id, session_id, timestamp, event_type, source, data FROM events WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "session_id": r[1],
            "timestamp": r[2],
            "event_type": r[3],
            "source": r[4],
            "data": json.loads(r[5]),
        }
        for r in rows
    ]


def list_sessions(limit=20):
    """列出所有会话"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, started_at, stopped_at, event_count, size_bytes, metadata "
        "FROM sessions ORDER BY started_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "started_at": r[1],
            "stopped_at": r[2],
            "event_count": r[3],
            "size_bytes": r[4],
            "active": r[0] == _current_session,
        }
        for r in rows
    ]


def get_session_stats(session_id=None):
    """获取会话统计"""
    sid = session_id or _current_session
    if not sid:
        return {"error": "no session specified"}

    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(LENGTH(data)), 0) FROM events WHERE session_id = ?",
        (sid,)
    ).fetchone()

    # 按类型统计
    type_rows = conn.execute(
        "SELECT event_type, COUNT(*) FROM events WHERE session_id = ? GROUP BY event_type",
        (sid,)
    ).fetchall()
    conn.close()

    return {
        "session_id": sid,
        "active": sid == _current_session,
        "total_events": row[0],
        "total_bytes": row[1],
        "by_type": {r[0]: r[1] for r in type_rows},
    }


def cleanup(max_age_hours=72):
    """清理过期会话"""
    import datetime as dt
    cutoff = (dt.datetime.now() - dt.timedelta(hours=max_age_hours)).isoformat()
    conn = _get_conn()
    conn.execute("DELETE FROM events WHERE session_id IN (SELECT id FROM sessions WHERE stopped_at < ?)", (cutoff,))
    conn.execute("DELETE FROM sessions WHERE stopped_at < ?", (cutoff,))
    conn.commit()
    conn.close()
    log.info("Cleaned up sessions older than %d hours", max_age_hours)
    return {"ok": True}


# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------
init_db()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("Event stream test...")

    # 创建测试会话
    result = start_session({"test": True})
    print(f"Session: {result}")

    # 录制一些测试事件
    for i in range(5):
        record("test", "event_stream", {"index": i, "message": f"test event {i}"})
        time.sleep(0.1)

    # 刷新并查询
    _flush_batch()
    events = query_events(limit=10)
    print(f"\nEvents ({len(events)}):")
    for e in events:
        print(f"  {e['timestamp']} [{e['event_type']}] {e['data']}")

    stats = get_session_stats()
    print(f"\nStats: {json.dumps(stats, indent=2)}")

    # 停止会话
    result = stop_session()
    print(f"\nStopped: {result}")
