"""
Voxta 数据库操作 — DB直控/模块管理/角色管理/配置管理

从 vam/voxta.py 迁移至此，统一管理Voxta数据库相关操作。
"""
import sqlite3
import json
import logging
import shutil
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
from typing import Optional

from .config import VOXTA_CONFIG

_log = logging.getLogger(__name__)


def _connect_db(readonly: bool = True):
    """连接Voxta数据库"""
    if not VOXTA_CONFIG.VOXTA_DB.exists():
        raise FileNotFoundError(f"Voxta DB not found: {VOXTA_CONFIG.VOXTA_DB}")
    uri = f"file:{VOXTA_CONFIG.VOXTA_DB}?mode={'ro' if readonly else 'rw'}"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _db_conn(readonly: bool = True):
    """Context manager for safe DB connections (auto-close on exit/exception)"""
    conn = _connect_db(readonly)
    try:
        yield conn
    finally:
        conn.close()


def backup_db() -> str:
    """备份Voxta数据库"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = VOXTA_CONFIG.VOXTA_DIR / "Data" / ".agent_backup"
    backup_dir.mkdir(exist_ok=True)
    dest = backup_dir / f"Voxta.sqlite.db.{ts}.bak"
    shutil.copy2(str(VOXTA_CONFIG.VOXTA_DB), str(dest))
    return str(dest)


# ── 统计 ──

_ALLOWED_TABLES = frozenset([
    "Characters", "ChatMessages", "Chats", "Modules", "Presets",
    "MemoryBooks", "Scenarios", "Users", "ProfileSettings",
])


def get_stats() -> dict:
    """获取数据库统计"""
    with _db_conn() as conn:
        cur = conn.cursor()
        stats = {}
        for table in _ALLOWED_TABLES:
            try:
                stats[table] = cur.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
            except Exception as e:
                _log.debug("get_stats: table %s error: %s", table, e)
        return stats


# ── 角色管理 ──

def list_characters() -> list:
    """列出所有角色"""
    with _db_conn() as conn:
        chars = []
        for r in conn.execute("SELECT * FROM Characters"):
            d = dict(r)
            chars.append({
                "id": d.get("LocalId", ""),
                "label": d.get("Label", ""),
                "name": d.get("Name", ""),
                "personality": (d.get("Personality", "") or "")[:200],
                "first_message": (d.get("FirstMessage", "") or "")[:200],
                "thinking_speech": bool(d.get("EnableThinkingSpeech", 0)),
                "memory_books": d.get("MemoryBooks", "[]"),
            })
        return chars


def get_character(char_id: str) -> Optional[dict]:
    """获取角色完整详情"""
    with _db_conn() as conn:
        r = conn.execute("SELECT * FROM Characters WHERE LocalId=?", (char_id,)).fetchone()
        if r is None:
            return None
        return dict(r)


_ALLOWED_CHAR_FIELDS = {
    "Name", "Label", "Personality", "Profile", "Description", "Culture",
    "FirstMessage", "MessageExamples", "SystemPrompt", "PostHistoryInstructions",
    "EnableThinkingSpeech", "MemoryBooks", "Tags", "Extensions",
}


def update_character_field(char_id: str, field: str, value) -> bool:
    """更新角色字段"""
    if field not in _ALLOWED_CHAR_FIELDS:
        raise ValueError(f"Disallowed field: {field}. Allowed: {_ALLOWED_CHAR_FIELDS}")
    backup_db()
    with _db_conn(readonly=False) as conn:
        try:
            conn.execute(f"UPDATE Characters SET [{field}]=? WHERE LocalId=?", (value, char_id))
            conn.commit()
            return True
        except Exception as e:
            _log.warning("update_character_field failed: %s", e)
            return False


# ── 模块管理 ──

def list_modules() -> list:
    """列出所有模块及其状态"""
    with _db_conn() as conn:
        modules = []
        for r in conn.execute("SELECT * FROM Modules"):
            d = dict(r)
            sn = d.get("ServiceName", "")
            category = "Other"
            for cat, services in VOXTA_CONFIG.MODULE_CATEGORIES.items():
                if any(s in sn for s in services):
                    category = cat
                    break

            cfg = {}
            try:
                cfg = json.loads(d.get("Configuration", "{}") or "{}")
            except Exception as e:
                _log.debug("list_modules: config parse error for %s: %s", sn, e)

            # 脱敏
            safe_cfg = {}
            for k, v in cfg.items():
                vs = str(v)
                if "AQAAANCMnd8" in vs:
                    safe_cfg[k] = "[DPAPI_ENCRYPTED]"
                elif len(vs) > 200:
                    safe_cfg[k] = vs[:200] + "..."
                else:
                    safe_cfg[k] = v

            modules.append({
                "id": d.get("LocalId", ""),
                "service": sn,
                "label": d.get("Label", ""),
                "enabled": bool(d.get("Enabled", 0)),
                "category": category,
                "config": safe_cfg,
            })
        return modules


def set_module_enabled(module_id: str, enabled: bool) -> bool:
    """启用/禁用模块"""
    backup_db()
    with _db_conn(readonly=False) as conn:
        try:
            conn.execute("UPDATE Modules SET Enabled=? WHERE LocalId=?",
                          (1 if enabled else 0, module_id))
            conn.commit()
            return True
        except Exception as e:
            _log.warning("set_module_enabled failed: %s", e)
            return False


def get_enabled_by_category() -> dict:
    """按类别获取已启用模块"""
    modules = list_modules()
    result = {}
    for m in modules:
        if m["enabled"]:
            cat = m["category"]
            if cat not in result:
                result[cat] = []
            result[cat].append({"service": m["service"], "label": m["label"]})
    return result


# ── 记忆书 ──

def list_memory_books() -> list:
    """列出所有记忆书"""
    with _db_conn() as conn:
        books = []
        for r in conn.execute("SELECT * FROM MemoryBooks"):
            d = dict(r)
            items = []
            try:
                items = json.loads(d.get("Items", "[]") or "[]")
            except Exception as e:
                _log.debug("list_memory_books: items parse error: %s", e)
            books.append({
                "id": d.get("LocalId", ""),
                "label": d.get("Label", ""),
                "owner": d.get("Owner", ""),
                "item_count": len(items),
            })
        return books


# ── 预设 ──

def list_presets() -> list:
    """列出所有LLM预设"""
    with _db_conn() as conn:
        presets = []
        for r in conn.execute("SELECT * FROM Presets"):
            d = dict(r)
            presets.append({
                "id": d.get("LocalId", ""),
                "label": d.get("Label", ""),
                "temperature": d.get("Temperature", ""),
                "max_tokens": d.get("MaxTokens", ""),
            })
        return presets


# ── 对话历史 ──

def list_chats(limit: int = 20) -> list:
    """列出最近对话"""
    with _db_conn() as conn:
        chats = []
        for r in conn.execute(
            "SELECT * FROM Chats ORDER BY ROWID DESC LIMIT ?", (limit,)
        ):
            chats.append(dict(r))
        return chats


def recent_messages(limit: int = 20) -> list:
    """获取最近消息"""
    with _db_conn() as conn:
        msgs = []
        for r in conn.execute(
            "SELECT * FROM ChatMessages ORDER BY ROWID DESC LIMIT ?", (limit,)
        ):
            d = dict(r)
            msgs.append({
                "role": d.get("Role", ""),
                "text": (d.get("Text", "") or "")[:300],
                "chat_id": d.get("ChatId", ""),
            })
        return msgs


# ── 场景 ──

def list_scenarios() -> list:
    """列出Voxta场景"""
    with _db_conn() as conn:
        scenarios = []
        for r in conn.execute("SELECT * FROM Scenarios"):
            d = dict(r)
            scenarios.append({
                "id": d.get("LocalId", ""),
                "name": d.get("Name", ""),
                "description": (d.get("Description", "") or "")[:200],
                "client": d.get("Client", ""),
            })
        return scenarios


# ── 配置文件 ──

def read_appsettings() -> dict:
    """读取Voxta appsettings.json"""
    path = VOXTA_CONFIG.VOXTA_SETTINGS
    if not path.exists():
        return {"error": "appsettings.json not found"}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 综合仪表板 ──

def dashboard() -> dict:
    """生成Voxta综合仪表板数据"""
    return {
        "stats": get_stats(),
        "characters": list_characters(),
        "enabled_modules": get_enabled_by_category(),
        "memory_books": list_memory_books(),
        "scenarios": list_scenarios(),
    }
