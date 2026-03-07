"""
VaM 日志监控 — VaM日志读取/错误检测

Voxta日志功能已迁移至 voxta/logs.py
"""
import re
from pathlib import Path
from datetime import datetime

from .config import VAM_CONFIG


# ── 日志读取 ──

def read_log(tail: int = 100) -> list:
    """读取VaM输出日志最后N行"""
    log_path = VAM_CONFIG.VAM_LOG
    if not log_path.exists():
        return []

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    return [line.rstrip() for line in lines[-tail:]]


def log_size() -> dict:
    """获取日志文件信息"""
    log_path = VAM_CONFIG.VAM_LOG
    if not log_path.exists():
        return {"exists": False}

    stat = log_path.stat()
    return {
        "exists": True,
        "path": str(log_path),
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }


# ── 错误检测 ──

ERROR_PATTERNS = [
    (r"NullReferenceException", "critical", "空引用异常"),
    (r"Exception:", "error", "异常"),
    (r"ERROR", "error", "错误"),
    (r"StackOverflowException", "critical", "栈溢出"),
    (r"OutOfMemoryException", "critical", "内存溢出"),
    (r"MissingMethodException", "error", "缺少方法"),
    (r"FileNotFoundException", "warning", "文件未找到"),
    (r"SocketException", "warning", "网络连接异常"),
    (r"TimeoutException", "warning", "超时"),
    (r"Could not load", "warning", "加载失败"),
    (r"Plugin error", "error", "插件错误"),
    (r"Failed to", "warning", "操作失败"),
]


def detect_errors(tail: int = 500) -> list:
    """检测日志中的错误"""
    lines = read_log(tail)
    errors = []

    for i, line in enumerate(lines):
        for pattern, level, desc in ERROR_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                errors.append({
                    "line": i + 1,
                    "level": level,
                    "type": desc,
                    "content": line[:300],
                })
                break

    return errors


def error_summary(tail: int = 1000) -> dict:
    """生成错误摘要"""
    errors = detect_errors(tail)
    summary = {"total": len(errors), "by_level": {}, "by_type": {}}

    for e in errors:
        level = e["level"]
        etype = e["type"]
        summary["by_level"][level] = summary["by_level"].get(level, 0) + 1
        summary["by_type"][etype] = summary["by_type"].get(etype, 0) + 1

    summary["recent"] = errors[-10:]
    return summary


# ── 插件日志 ──

def read_bepinex_log(tail: int = 50) -> list:
    """读取BepInEx日志"""
    log_path = VAM_CONFIG.BEPINEX_DIR / "LogOutput.log"
    if not log_path.exists():
        return []

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    return [line.rstrip() for line in lines[-tail:]]


# ── 搜索 ──

def search_log(keyword: str, tail: int = 2000) -> list:
    """在日志中搜索关键词"""
    lines = read_log(tail)
    kw = keyword.lower()
    results = []
    for i, line in enumerate(lines):
        if kw in line.lower():
            results.append({
                "line": i + 1,
                "content": line[:300],
            })
    return results


