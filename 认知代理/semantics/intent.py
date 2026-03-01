"""
意图提炼引擎 — 事件流 → 意图四元组
=====================================
将原始事件流提炼为结构化的意图记录:
  {intent, context, actions, result}

核心能力:
  1. 事件分组: 按时间窗口+应用上下文聚合相关事件
  2. 模式识别: 识别常见操作模式(保存/复制粘贴/搜索/切换应用等)
  3. 跨应用关联: 浏览器搜索→复制→粘贴到编辑器 = "查资料并引用"
  4. 意图推断: 从操作模式推断用户意图

单独测试:
  cd 认知代理
  python -m semantics.intent
"""

import re
import json
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict

log = logging.getLogger("semantics.intent")

# ---------------------------------------------------------------------------
# 操作模式库 (Pattern Library)
# ---------------------------------------------------------------------------

# 键盘快捷键 → 意图映射
HOTKEY_INTENTS = {
    # 文件操作
    frozenset(["ctrl", "s"]): "save_file",
    frozenset(["ctrl", "shift", "s"]): "save_as",
    frozenset(["ctrl", "n"]): "new_file",
    frozenset(["ctrl", "o"]): "open_file",
    frozenset(["ctrl", "w"]): "close_tab",
    frozenset(["ctrl", "shift", "t"]): "reopen_tab",

    # 编辑操作
    frozenset(["ctrl", "z"]): "undo",
    frozenset(["ctrl", "y"]): "redo",
    frozenset(["ctrl", "shift", "z"]): "redo",
    frozenset(["ctrl", "c"]): "copy",
    frozenset(["ctrl", "x"]): "cut",
    frozenset(["ctrl", "v"]): "paste",
    frozenset(["ctrl", "a"]): "select_all",
    frozenset(["ctrl", "f"]): "find",
    frozenset(["ctrl", "h"]): "find_replace",

    # 导航
    frozenset(["alt", "tab"]): "switch_app",
    frozenset(["ctrl", "tab"]): "switch_tab",
    frozenset(["ctrl", "shift", "tab"]): "switch_tab_back",
    frozenset(["alt", "f4"]): "close_app",
    frozenset(["win", "d"]): "show_desktop",
    frozenset(["win", "e"]): "open_explorer",
    frozenset(["win", "r"]): "run_dialog",

    # IDE特有
    frozenset(["ctrl", "shift", "p"]): "command_palette",
    frozenset(["ctrl", "p"]): "quick_open",
    frozenset(["ctrl", "`"]): "toggle_terminal",
    frozenset(["ctrl", "b"]): "toggle_sidebar",
    frozenset(["f5"]): "run_debug",
    frozenset(["ctrl", "shift", "f"]): "search_files",

    # 浏览器
    frozenset(["ctrl", "l"]): "focus_address_bar",
    frozenset(["ctrl", "t"]): "new_tab",
    frozenset(["f12"]): "devtools",
    frozenset(["ctrl", "shift", "i"]): "devtools",
    frozenset(["f5"]): "refresh",
    frozenset(["ctrl", "r"]): "refresh",
}

# 进程名 → 应用类别
APP_CATEGORIES = {
    "windsurf.exe": "ide",
    "code.exe": "ide",
    "cursor.exe": "ide",
    "chrome.exe": "browser",
    "msedge.exe": "browser",
    "firefox.exe": "browser",
    "explorer.exe": "file_manager",
    "notepad.exe": "text_editor",
    "notepad++.exe": "text_editor",
    "cmd.exe": "terminal",
    "powershell.exe": "terminal",
    "pwsh.exe": "terminal",
    "windowsterminal.exe": "terminal",
    "python.exe": "runtime",
    "node.exe": "runtime",
    "git.exe": "vcs",
}


# ---------------------------------------------------------------------------
# 事件分组器 (Event Grouper)
# ---------------------------------------------------------------------------

def group_events(events, time_window_s=3.0, app_boundary=True):
    """
    将事件按时间窗口和应用边界分组。

    规则:
      1. 同一应用内，时间间隔 < time_window_s 的事件归为一组
      2. 切换应用 = 强制分组边界
      3. 连续键盘输入合并为"typing"事件
    """
    if not events:
        return []

    groups = []
    current_group = {
        "events": [],
        "start_time": None,
        "end_time": None,
        "app": None,
        "app_category": None,
    }

    for evt in events:
        ts = evt.get("timestamp", "")
        evt_type = evt.get("event_type", "")
        data = evt.get("data", {})

        # 提取应用信息
        target = data.get("target", {})
        process = (target.get("process", "") or "").lower() if isinstance(target, dict) else ""
        app_cat = APP_CATEGORIES.get(process, "other")

        # 判断是否需要开始新组
        should_split = False

        if not current_group["events"]:
            should_split = False  # 第一个事件
        elif app_boundary and process and current_group["app"] and process != current_group["app"]:
            should_split = True  # 应用切换
        elif current_group["end_time"] and ts:
            try:
                t1 = datetime.fromisoformat(current_group["end_time"])
                t2 = datetime.fromisoformat(ts)
                if (t2 - t1).total_seconds() > time_window_s:
                    should_split = True  # 超时
            except (ValueError, TypeError):
                pass

        if should_split and current_group["events"]:
            groups.append(current_group)
            current_group = {
                "events": [],
                "start_time": None,
                "end_time": None,
                "app": None,
                "app_category": None,
            }

        current_group["events"].append(evt)
        if not current_group["start_time"]:
            current_group["start_time"] = ts
        current_group["end_time"] = ts
        if process:
            current_group["app"] = process
            current_group["app_category"] = app_cat

    if current_group["events"]:
        groups.append(current_group)

    return groups


# ---------------------------------------------------------------------------
# 模式识别器 (Pattern Recognizer)
# ---------------------------------------------------------------------------

def _detect_hotkey(events):
    """从key事件序列中检测快捷键"""
    # 收集按下的修饰键+普通键
    mods = set()
    keys = []
    for evt in events:
        data = evt.get("data", {})
        if isinstance(data, dict):
            name = data.get("name", "")
            event_type = data.get("event_type", "")
            modifiers = data.get("modifiers", [])
            if event_type == "down":
                if name in ("ctrl", "shift", "alt", "windows", "win"):
                    mods.add(name.replace("windows", "win"))
                else:
                    keys.append(name)
                if modifiers:
                    mods.update(m.lower() for m in modifiers)

    if mods and keys:
        combo = frozenset(mods | {keys[-1]})
        return HOTKEY_INTENTS.get(combo)
    elif keys:
        single = frozenset({keys[-1]})
        return HOTKEY_INTENTS.get(single)
    return None


def _detect_typing(events):
    """检测连续打字"""
    chars = []
    for evt in events:
        data = evt.get("data", {})
        if isinstance(data, dict):
            name = data.get("name", "")
            event_type = data.get("event_type", "")
            mods = data.get("modifiers", [])
            if event_type == "down" and len(name) == 1 and not mods:
                chars.append(name)
    if len(chars) >= 3:
        return "".join(chars)
    return None


def _detect_click_pattern(events):
    """检测鼠标点击模式"""
    clicks = [e for e in events if e.get("data", {}).get("action", "").endswith("_down")]
    if len(clicks) >= 2:
        # 快速双击检测
        try:
            t1 = datetime.fromisoformat(clicks[-2]["timestamp"])
            t2 = datetime.fromisoformat(clicks[-1]["timestamp"])
            if (t2 - t1).total_seconds() < 0.5:
                return "double_click"
        except (ValueError, TypeError, KeyError):
            pass
    if clicks:
        return "click"
    return None


def recognize_pattern(group):
    """
    识别一组事件的操作模式。
    返回: {"pattern": "...", "details": {...}}
    """
    events = group.get("events", [])
    if not events:
        return {"pattern": "unknown"}

    # 按事件类型分类
    key_events = [e for e in events if e.get("event_type") == "key"]
    mouse_events = [e for e in events if e.get("event_type") == "mouse"]
    focus_events = [e for e in events if e.get("event_type") == "focus_change"]
    file_events = [e for e in events if e.get("event_type") == "file_change"]
    screen_events = [e for e in events if e.get("event_type") == "screen_snapshot"]

    # 1. 快捷键检测（最高优先级）
    if key_events:
        hotkey = _detect_hotkey(key_events)
        if hotkey:
            return {"pattern": "hotkey", "intent": hotkey, "key_count": len(key_events)}

    # 2. 打字检测
    if key_events:
        typed = _detect_typing(key_events)
        if typed:
            return {"pattern": "typing", "text_length": len(typed), "preview": typed[:50]}

    # 3. 文件变化
    if file_events:
        actions = defaultdict(list)
        for e in file_events:
            d = e.get("data", {})
            actions[d.get("action", "unknown")].append(d.get("filename", ""))
        return {"pattern": "file_operation", "actions": dict(actions)}

    # 4. 鼠标操作
    if mouse_events:
        click_type = _detect_click_pattern(mouse_events)
        if click_type:
            return {"pattern": click_type, "mouse_events": len(mouse_events)}

    # 5. 焦点切换
    if focus_events:
        windows = [e.get("data", {}).get("next", "") for e in focus_events]
        return {"pattern": "app_switch", "windows": windows[:5]}

    return {"pattern": "mixed", "event_count": len(events)}


# ---------------------------------------------------------------------------
# 意图推断器 (Intent Inferrer)
# ---------------------------------------------------------------------------

# 跨应用意图模式
CROSS_APP_PATTERNS = [
    {
        "name": "research_and_cite",
        "description": "查资料并引用",
        "sequence": ["browser:*", "copy", "*:paste"],
    },
    {
        "name": "code_and_test",
        "description": "编码并测试",
        "sequence": ["ide:typing", "ide:save_file", "terminal:*"],
    },
    {
        "name": "file_organize",
        "description": "整理文件",
        "sequence": ["file_manager:*", "file_operation:*"],
    },
]


def extract_intents(groups):
    """
    从分组事件中提取意图四元组列表。

    返回:
    [
        {
            "intent": "保存文件",
            "context": {"app": "Windsurf.exe", "category": "ide", "window": "..."},
            "actions": [{"type": "hotkey", "key": "ctrl+s"}],
            "result": {"file_changed": true}
        },
        ...
    ]
    """
    intents = []

    for i, group in enumerate(groups):
        pattern = recognize_pattern(group)

        # 构建上下文
        context = {
            "app": group.get("app", ""),
            "category": group.get("app_category", ""),
            "start_time": group.get("start_time", ""),
            "end_time": group.get("end_time", ""),
            "event_count": len(group.get("events", [])),
        }

        # 构建动作列表
        actions = []
        for evt in group.get("events", [])[:10]:  # 限制输出大小
            actions.append({
                "type": evt.get("event_type", ""),
                "data": _compact_data(evt.get("data", {})),
            })

        # 推断意图名称
        intent_name = _infer_intent_name(pattern, context)

        # 检测结果（后续事件中的文件变化等）
        result = _detect_result(groups, i)

        intents.append({
            "intent": intent_name,
            "pattern": pattern.get("pattern", "unknown"),
            "context": context,
            "actions": actions,
            "result": result,
        })

    return intents


def _infer_intent_name(pattern, context):
    """根据模式和上下文推断人类可读的意图名称"""
    p = pattern.get("pattern", "")
    intent = pattern.get("intent", "")
    cat = context.get("category", "")

    INTENT_NAMES = {
        "save_file": "保存文件",
        "save_as": "另存为",
        "new_file": "新建文件",
        "open_file": "打开文件",
        "close_tab": "关闭标签页",
        "reopen_tab": "恢复标签页",
        "undo": "撤销",
        "redo": "重做",
        "copy": "复制",
        "cut": "剪切",
        "paste": "粘贴",
        "select_all": "全选",
        "find": "查找",
        "find_replace": "查找替换",
        "switch_app": "切换应用",
        "switch_tab": "切换标签页",
        "close_app": "关闭应用",
        "show_desktop": "显示桌面",
        "open_explorer": "打开资源管理器",
        "command_palette": "命令面板",
        "quick_open": "快速打开",
        "toggle_terminal": "切换终端",
        "run_debug": "运行/调试",
        "search_files": "搜索文件",
        "focus_address_bar": "聚焦地址栏",
        "new_tab": "新标签页",
        "devtools": "开发者工具",
        "refresh": "刷新页面",
    }

    if intent and intent in INTENT_NAMES:
        return INTENT_NAMES[intent]

    if p == "typing":
        if cat == "ide":
            return "编写代码"
        elif cat == "browser":
            return "输入搜索/URL"
        elif cat == "terminal":
            return "输入命令"
        return "输入文字"

    if p == "click":
        return "点击操作"
    if p == "double_click":
        return "双击操作"
    if p == "file_operation":
        return "文件操作"
    if p == "app_switch":
        return "切换应用"

    return "未知操作"


def _compact_data(data):
    """压缩事件数据（去噪）"""
    if not isinstance(data, dict):
        return data
    # 只保留关键字段
    keep_keys = {"name", "action", "x", "y", "key", "text", "filename", "path",
                 "event_type", "modifiers", "title", "process"}
    return {k: v for k, v in data.items() if k in keep_keys and v}


def _detect_result(groups, current_idx):
    """检测操作结果（查看后续事件中是否有文件变化等）"""
    result = {}
    # 查看后续1-2个组
    for j in range(current_idx + 1, min(current_idx + 3, len(groups))):
        next_group = groups[j]
        for evt in next_group.get("events", []):
            if evt.get("event_type") == "file_change":
                d = evt.get("data", {})
                result["file_changed"] = True
                result["file_action"] = d.get("action", "")
                result["file_path"] = d.get("filename", "")
                return result
    return result


# ---------------------------------------------------------------------------
# 高级分析 (High-level Analysis)
# ---------------------------------------------------------------------------

def analyze_session(events, time_window_s=3.0):
    """
    对一整个会话的事件进行完整分析。

    返回:
    {
        "intents": [...],           # 意图四元组列表
        "summary": {...},           # 会话摘要
        "cross_app_flows": [...],   # 跨应用流
    }
    """
    # 1. 分组
    groups = group_events(events, time_window_s=time_window_s)

    # 2. 提取意图
    intents = extract_intents(groups)

    # 3. 生成摘要
    intent_counts = defaultdict(int)
    app_time = defaultdict(float)
    for intent_rec in intents:
        intent_counts[intent_rec["intent"]] += 1
        app = intent_rec["context"].get("app", "unknown")
        try:
            t1 = datetime.fromisoformat(intent_rec["context"]["start_time"])
            t2 = datetime.fromisoformat(intent_rec["context"]["end_time"])
            app_time[app] += (t2 - t1).total_seconds()
        except (ValueError, TypeError, KeyError):
            pass

    summary = {
        "total_groups": len(groups),
        "total_intents": len(intents),
        "top_intents": sorted(intent_counts.items(), key=lambda x: -x[1])[:10],
        "app_time": sorted(app_time.items(), key=lambda x: -x[1])[:10],
    }

    # 4. 跨应用流检测
    cross_app_flows = _detect_cross_app_flows(intents)

    return {
        "intents": intents,
        "summary": summary,
        "cross_app_flows": cross_app_flows,
    }


def _detect_cross_app_flows(intents):
    """检测跨应用操作流"""
    flows = []

    # 检测 复制→粘贴 流
    for i in range(len(intents) - 1):
        if intents[i].get("pattern") == "hotkey" and intents[i]["context"].get("category") == "browser":
            intent_name = intents[i].get("intent", "")
            if "复制" in intent_name:
                # 检查后续是否有粘贴到其他应用
                for j in range(i + 1, min(i + 5, len(intents))):
                    if "粘贴" in intents[j].get("intent", ""):
                        if intents[j]["context"].get("app") != intents[i]["context"].get("app"):
                            flows.append({
                                "type": "cross_app_copy_paste",
                                "description": "跨应用复制粘贴",
                                "from_app": intents[i]["context"].get("app"),
                                "to_app": intents[j]["context"].get("app"),
                                "from_idx": i,
                                "to_idx": j,
                            })
                        break

    # 检测 编码→保存→切换终端 流
    for i in range(len(intents) - 2):
        if intents[i].get("intent") == "编写代码":
            if intents[i + 1].get("intent") == "保存文件":
                if intents[i + 2].get("intent") in ("切换终端", "输入命令"):
                    flows.append({
                        "type": "code_save_run",
                        "description": "编码→保存→运行",
                        "start_idx": i,
                        "end_idx": i + 2,
                    })

    return flows


# ---------------------------------------------------------------------------
# 独立测试
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # 模拟事件流
    mock_events = [
        {"event_type": "key", "timestamp": "2026-03-01T10:00:00.000",
         "data": {"name": "h", "event_type": "down", "modifiers": [], "target": {"process": "Windsurf.exe"}}},
        {"event_type": "key", "timestamp": "2026-03-01T10:00:00.100",
         "data": {"name": "e", "event_type": "down", "modifiers": [], "target": {"process": "Windsurf.exe"}}},
        {"event_type": "key", "timestamp": "2026-03-01T10:00:00.200",
         "data": {"name": "l", "event_type": "down", "modifiers": [], "target": {"process": "Windsurf.exe"}}},
        {"event_type": "key", "timestamp": "2026-03-01T10:00:00.300",
         "data": {"name": "l", "event_type": "down", "modifiers": [], "target": {"process": "Windsurf.exe"}}},
        {"event_type": "key", "timestamp": "2026-03-01T10:00:00.400",
         "data": {"name": "o", "event_type": "down", "modifiers": [], "target": {"process": "Windsurf.exe"}}},
        # Ctrl+S 保存
        {"event_type": "key", "timestamp": "2026-03-01T10:00:02.000",
         "data": {"name": "s", "event_type": "down", "modifiers": ["ctrl"], "target": {"process": "Windsurf.exe"}}},
        # 文件变化
        {"event_type": "file_change", "timestamp": "2026-03-01T10:00:02.500",
         "data": {"action": "modified", "filename": "test.py"}},
        # 切换到浏览器
        {"event_type": "focus_change", "timestamp": "2026-03-01T10:00:05.000",
         "data": {"next": "Google Chrome", "target": {"process": "chrome.exe"}}},
    ]

    result = analyze_session(mock_events, time_window_s=2.0)
    print("=== 意图分析 ===")
    for intent in result["intents"]:
        print(f"  [{intent['pattern']}] {intent['intent']} ({intent['context']['app']})")
    print(f"\n=== 摘要 ===")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    if result["cross_app_flows"]:
        print(f"\n=== 跨应用流 ===")
        for flow in result["cross_app_flows"]:
            print(f"  {flow['type']}: {flow['description']}")
