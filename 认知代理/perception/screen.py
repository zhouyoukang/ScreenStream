"""
屏幕语义感知 — UIA控件树 → 结构化快照
=============================================
用 uiautomation 读取当前屏幕的UI Automation控件树，
输出语义化JSON（控件类型、名称、值、状态、位置），而非原始像素。

单独测试:
  cd 认知代理
  python -m perception.screen
"""

import time
import ctypes
import ctypes.wintypes as wt
import json
import logging
import os
import sys

log = logging.getLogger("perception.screen")

# ---------------------------------------------------------------------------
# Win32 constants
# ---------------------------------------------------------------------------
user32 = ctypes.windll.user32

def _get_foreground_info():
    """获取前台窗口基本信息（纯Win32，不依赖UIA）"""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    # 窗口标题
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value

    # 窗口类名
    cls_buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls_buf, 256)

    # 窗口矩形
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))

    # 进程ID
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    # 进程名
    proc_name = ""
    try:
        import psutil
        proc_name = psutil.Process(pid.value).name()
    except Exception:
        pass

    return {
        "hwnd": hwnd,
        "title": title,
        "class": cls_buf.value,
        "pid": pid.value,
        "process": proc_name,
        "rect": {
            "x": rect.left, "y": rect.top,
            "w": rect.right - rect.left,
            "h": rect.bottom - rect.top,
        },
    }


def _uia_snapshot(max_depth=6, min_size=5):
    """
    用 uiautomation 读取前台窗口的控件树。
    返回扁平化的控件列表（非递归嵌套，减少JSON体积）。
    """
    try:
        import uiautomation as auto
    except ImportError:
        return {"error": "uiautomation not installed"}

    controls = []
    start = time.perf_counter()

    try:
        # 获取前台窗口对应的UIA元素
        fg = auto.GetForegroundControl()
        if fg is None:
            return controls

        def _walk(ctrl, depth):
            if depth > max_depth:
                return
            if len(controls) > 500:  # 防止控件爆炸
                return

            try:
                rect = ctrl.BoundingRectangle
                w = rect.right - rect.left
                h = rect.bottom - rect.top

                # 跳过不可见/过小的控件
                if w < min_size or h < min_size:
                    return

                entry = {
                    "type": ctrl.ControlTypeName,
                    "depth": depth,
                    "rect": {"x": rect.left, "y": rect.top, "w": w, "h": h},
                }

                # 名称（非空才加）
                name = ctrl.Name
                if name:
                    entry["name"] = name[:200]  # 截断过长名称

                # 值（Edit/Document控件）
                try:
                    val = ctrl.GetValuePattern().Value
                    if val:
                        entry["value"] = val[:500]
                except Exception:
                    pass

                # 状态
                states = []
                try:
                    if ctrl.IsEnabled:
                        pass  # 默认enabled不标
                    else:
                        states.append("disabled")
                except Exception:
                    pass
                try:
                    if ctrl.HasKeyboardFocus:
                        states.append("focused")
                except Exception:
                    pass
                if states:
                    entry["states"] = states

                controls.append(entry)

                # 递归子控件
                children = ctrl.GetChildren()
                if children:
                    for child in children:
                        _walk(child, depth + 1)

            except Exception:
                pass  # UIA节点可能已失效

        _walk(fg, 0)

    except Exception as e:
        log.warning("UIA snapshot error: %s", e)

    elapsed = time.perf_counter() - start
    log.debug("UIA snapshot: %d controls in %.1fms", len(controls), elapsed * 1000)
    return controls


def _get_visible_text(controls, max_items=50):
    """从控件树中提取可见文本"""
    texts = []
    for c in controls:
        name = c.get("name", "")
        if name and len(name) > 2:  # 过滤噪声
            texts.append(name)
        val = c.get("value", "")
        if val and len(val) > 2:
            texts.append(val[:200])
        if len(texts) >= max_items:
            break
    return texts


def _is_sensitive(fg_info):
    """检测当前窗口是否涉及敏感信息"""
    if not fg_info:
        return False

    # 延迟导入避免循环
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import SENSITIVE_WINDOW_KEYWORDS, SENSITIVE_PROCESS_NAMES

    title = (fg_info.get("title", "") or "").lower()
    proc = (fg_info.get("process", "") or "").lower()

    for kw in SENSITIVE_WINDOW_KEYWORDS:
        if kw.lower() in title:
            return True
    for pn in SENSITIVE_PROCESS_NAMES:
        if pn.lower() in proc:
            return True
    return False


def take_snapshot(max_depth=6, include_controls=True):
    """
    获取一次完整的屏幕语义快照。

    返回:
    {
        "timestamp": "2026-03-01T10:52:00.123",
        "foreground": { ... },
        "controls": [ ... ],
        "visible_text": [ ... ],
        "sensitive": false,
        "control_count": 42,
        "snapshot_ms": 123
    }
    """
    start = time.perf_counter()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())

    fg = _get_foreground_info()
    sensitive = _is_sensitive(fg)

    result = {
        "timestamp": ts,
        "foreground": fg,
        "sensitive": sensitive,
    }

    if sensitive:
        result["controls"] = []
        result["visible_text"] = ["[REDACTED — sensitive window]"]
        result["control_count"] = 0
    elif include_controls:
        controls = _uia_snapshot(max_depth=max_depth)
        result["controls"] = controls
        result["visible_text"] = _get_visible_text(controls)
        result["control_count"] = len(controls)
    else:
        result["controls"] = []
        result["visible_text"] = []
        result["control_count"] = 0

    result["snapshot_ms"] = round((time.perf_counter() - start) * 1000, 1)
    return result


# ---------------------------------------------------------------------------
# 独立测试
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("Taking screen semantic snapshot...")
    snap = take_snapshot()
    print(json.dumps(snap, ensure_ascii=False, indent=2)[:3000])
    print(f"\n--- {snap['control_count']} controls, {snap['snapshot_ms']}ms ---")
