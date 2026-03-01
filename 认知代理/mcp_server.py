"""
认知代理 MCP Server — Cascade原生tool调用
==========================================
将认知代理的感知/语义/工作流能力封装为MCP Server，
使Cascade可以直接通过tool调用获取屏幕语义、录制会话、执行工作流。

启动方式(Windsurf MCP配置):
  command: "python"
  args: ["认知代理/mcp_server.py"]

或手动测试:
  cd 认知代理
  python mcp_server.py
"""

import sys
import os
import json
import logging

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

from config import SCREEN_SNAPSHOT_INTERVAL
from perception import screen, input_monitor, window_tracker, process_monitor, file_watcher
from semantics import event_stream, intent
from workflow import graph as wf_graph, storage as wf_storage, executor as wf_executor

log = logging.getLogger("mcp_server")

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP("CognitiveAgent", json_response=True)


# ===== 感知工具 =====

@mcp.tool()
def screen_snapshot(max_depth: int = 4, include_controls: bool = True) -> dict:
    """获取当前屏幕的语义快照：前台窗口信息+UIA控件树+可见文本。
    返回结构化JSON而非像素截图，Agent可直接理解屏幕内容。
    max_depth: UIA树最大深度(1-8)，越深越慢
    include_controls: false则只返回前台窗口基本信息(33ms)"""
    return screen.take_snapshot(max_depth=max_depth, include_controls=include_controls)


@mcp.tool()
def get_focus() -> dict:
    """获取当前焦点窗口信息：标题、进程名、停留时间。"""
    result = window_tracker.get_current()
    if not result:
        # fallback: 直接读取
        fg = screen._get_foreground_info()
        return {"window": fg, "since": None, "duration_s": 0}
    return result


@mcp.tool()
def get_focus_chain(limit: int = 20) -> list:
    """获取窗口焦点切换链：最近N次窗口切换记录（包含每个窗口的停留时间）。
    用于理解用户的应用切换模式和工作流。"""
    return window_tracker.get_focus_chain(limit)


@mcp.tool()
def get_input_events(limit: int = 50, event_type: str = "") -> list:
    """获取最近的输入事件（键盘/鼠标）。
    event_type: 'key'=仅键盘, 'mouse'=仅鼠标, ''=全部"""
    return input_monitor.get_events(limit=limit, event_type=event_type or None)


@mcp.tool()
def get_perception_status() -> dict:
    """获取所有感知模块的运行状态和统计数据。"""
    return {
        "input": input_monitor.get_stats(),
        "window": window_tracker.get_stats(),
        "process": process_monitor.get_stats(),
        "files": file_watcher.get_stats(),
        "session": event_stream.get_current_session(),
    }


# ===== 会话管理 =====

@mcp.tool()
def start_recording(watch_dirs: list = None) -> dict:
    """开始录制用户操作会话。启动五维感知（屏幕/键鼠/焦点/进程/文件），
    所有事件写入SQLite。返回session_id。
    watch_dirs: 可选，额外监控的文件目录列表"""
    session_result = event_stream.start_session()
    if "error" not in session_result:
        input_monitor.start()
        window_tracker.start()
        process_monitor.start()
        file_watcher.start(watch_dirs)
    return session_result


@mcp.tool()
def stop_recording() -> dict:
    """停止录制会话，返回事件总数和数据大小。"""
    input_monitor.stop()
    window_tracker.stop()
    process_monitor.stop()
    file_watcher.stop()
    return event_stream.stop_session()


@mcp.tool()
def get_session_events(event_type: str = "", limit: int = 100, since: str = "") -> list:
    """查询当前会话中的事件。
    event_type: 过滤类型(key/mouse/screen_snapshot/focus_change/process_start/file_change)
    since: ISO时间戳，只返回此时间之后的事件"""
    return event_stream.query_events(
        event_type=event_type or None,
        since=since or None,
        limit=limit,
    )


@mcp.tool()
def get_session_stats() -> dict:
    """获取当前录制会话的统计：总事件数、按类型分布、数据大小。"""
    sid = event_stream.get_current_session()
    if sid:
        return event_stream.get_session_stats(sid)
    return {"active": False, "session_id": None}


# ===== 语义分析 =====

@mcp.tool()
def analyze_intents(time_window: float = 3.0, limit: int = 2000) -> dict:
    """分析当前会话的事件流，提取意图四元组。
    返回：意图列表 + 会话摘要 + 跨应用操作流。
    time_window: 事件分组的时间窗口(秒)"""
    events = event_stream.query_events(limit=limit)
    if not events:
        return {"error": "no events in session"}
    return intent.analyze_session(events, time_window_s=time_window)


# ===== 工作流 =====

@mcp.tool()
def list_workflows() -> list:
    """列出所有已保存的工作流。"""
    return wf_storage.list_all()


@mcp.tool()
def save_workflow(workflow_json: str) -> dict:
    """保存工作流定义(JSON字符串)。"""
    try:
        wf_dict = json.loads(workflow_json)
        return wf_storage.save(wf_dict)
    except json.JSONDecodeError as e:
        return {"error": f"invalid JSON: {e}"}


@mcp.tool()
def extract_workflow(name: str = "", description: str = "") -> dict:
    """从当前录制会话中自动提取工作流。
    分析事件→识别意图→生成参数化工作流图谱→保存到磁盘。"""
    events = event_stream.query_events(limit=5000)
    if not events:
        return {"error": "no events in session"}

    analysis = intent.analyze_session(events)
    wf = wf_graph.extract_workflow_from_intents(
        analysis["intents"],
        name=name or None,
        description=description or None,
    )
    if wf:
        wf_dict = wf.to_dict()
        wf_storage.save(wf_dict)
        return wf_dict
    return {"error": "could not extract workflow"}


@mcp.tool()
def execute_workflow(workflow_id: str = "", params: dict = None, dry_run: bool = False) -> dict:
    """执行已保存的工作流。
    workflow_id: 工作流ID
    params: 参数值(替换工作流中的${param}变量)
    dry_run: true=只验证不执行"""
    wf_dict = wf_storage.load(workflow_id)
    if not wf_dict:
        return {"error": "workflow not found", "id": workflow_id}

    backend = wf_executor.LocalBackend()
    executor = wf_executor.WorkflowExecutor(backend=backend)
    return executor.execute(wf_dict, param_values=params or {}, dry_run=dry_run)


@mcp.tool()
def run_workflow_inline(steps_json: str, dry_run: bool = False) -> dict:
    """直接执行工作流步骤(无需先保存)。
    steps_json: JSON数组，每项{action, params, description}
    示例: [{"action":"shell","params":{"cmd":"echo hello"},"description":"test"}]"""
    try:
        steps = json.loads(steps_json)
    except json.JSONDecodeError as e:
        return {"error": f"invalid JSON: {e}"}

    wf_dict = {
        "id": "wf_inline",
        "name": "Inline Workflow",
        "steps": [
            {"id": f"s{i}", **step}
            for i, step in enumerate(steps)
        ],
    }
    backend = wf_executor.LocalBackend()
    executor = wf_executor.WorkflowExecutor(backend=backend)
    return executor.execute(wf_dict, dry_run=dry_run)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mcp.run()  # stdio transport (default for Windsurf)
