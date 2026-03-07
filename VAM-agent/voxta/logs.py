"""
Voxta 日志监控 — Voxta日志读取/错误检测/关键词搜索
"""
import re
from pathlib import Path
from typing import Optional

from .config import VOXTA_CONFIG

_ERROR_PATTERNS = re.compile(
    r'(?i)\b(error|exception|fail|fatal|crash|unhandled|traceback|critical)\b'
)

_WARNING_PATTERNS = re.compile(
    r'(?i)\b(warn|warning|timeout|refused|denied|missing|not found)\b'
)


def _get_log_dir() -> Path:
    return VOXTA_CONFIG.VOXTA_DIR / "Logs"


def _read_latest(log_dir: Path, tail: int = 50, pattern: str = "*.log") -> list:
    """Read tail lines from the most recent log file matching pattern"""
    if not log_dir.exists():
        return []
    log_files = sorted(log_dir.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    if not log_files:
        return []
    with open(log_files[0], "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    return [line.rstrip() for line in lines[-tail:]]


def read_voxta_log(tail: int = 50) -> list:
    """读取Voxta日志"""
    return _read_latest(_get_log_dir(), tail)


def detect_errors(tail: int = 200) -> list:
    """检测最近日志中的错误和警告，返回 [{level, line, text}]"""
    lines = read_voxta_log(tail)
    issues = []
    for i, line in enumerate(lines):
        if _ERROR_PATTERNS.search(line):
            issues.append({'level': 'ERROR', 'line': i + 1, 'text': line[:300]})
        elif _WARNING_PATTERNS.search(line):
            issues.append({'level': 'WARNING', 'line': i + 1, 'text': line[:300]})
    return issues


def search_log(keyword: str, tail: int = 500, case_sensitive: bool = False) -> list:
    """在日志中搜索关键词，返回匹配行"""
    lines = read_voxta_log(tail)
    if not case_sensitive:
        keyword = keyword.lower()
    results = []
    for i, line in enumerate(lines):
        target = line if case_sensitive else line.lower()
        if keyword in target:
            results.append({'line': i + 1, 'text': line[:300]})
    return results


def log_summary(tail: int = 200) -> dict:
    """日志摘要：总行数、错误数、警告数、最后活动时间"""
    log_dir = _get_log_dir()
    if not log_dir.exists():
        return {'exists': False}

    log_files = sorted(log_dir.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not log_files:
        return {'exists': True, 'files': 0}

    latest = log_files[0]
    lines = read_voxta_log(tail)
    issues = detect_errors(tail)

    return {
        'exists': True,
        'files': len(log_files),
        'latest_file': latest.name,
        'latest_size_kb': round(latest.stat().st_size / 1024, 1),
        'lines_read': len(lines),
        'errors': sum(1 for i in issues if i['level'] == 'ERROR'),
        'warnings': sum(1 for i in issues if i['level'] == 'WARNING'),
    }
