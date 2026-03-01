"""
认知代理 HTTP API Server
=========================
统一入口，暴露感知/事件流/会话管理的HTTP API。
供 IDE Agent (Cascade) 查询人机交互上下文。

启动:
  cd 认知代理
  python server.py                # :9070
  python server.py --port 9071    # 自定义端口

API:
  GET  /health                    健康检查
  GET  /snapshot                  屏幕语义快照（UIA控件树）
  GET  /snapshot?controls=false   仅前台窗口信息

  POST /session/start             开始录制会话
  POST /session/stop              停止录制会话
  GET  /session/status            当前会话状态
  GET  /session/list              历史会话列表
  GET  /session/events            查询事件 (?type=key&limit=50&since=...)
  GET  /session/stats             会话统计

  GET  /input/events              输入事件 (?limit=50&type=key)
  GET  /input/stats               输入统计

  GET  /focus/current             当前焦点窗口
  GET  /focus/chain               焦点切换链
  GET  /focus/stats               焦点统计

  GET  /process/events            进程事件
  GET  /process/stats             进程统计

  GET  /files/events              文件变化事件
  GET  /files/stats               文件监控统计

  POST /perception/start          启动所有感知模块
  POST /perception/stop           停止所有感知模块
  GET  /perception/status         感知模块状态

  POST /analyze                   分析当前会话事件→意图四元组
  GET  /analyze/summary           会话摘要(意图统计+跨应用流)

  GET  /workflows                 列出所有工作流
  GET  /workflow/{id}             获取工作流详情
  POST /workflow/save             保存工作流
  POST /workflow/delete           删除工作流
  POST /workflow/extract          从当前会话提取工作流
  POST /workflow/execute          执行工作流
  POST /workflow/execute/dry      干运行(验证不执行)
"""

import http.server
import json
import sys
import os
import time
import argparse
import logging
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SERVER_PORT, SCREEN_SNAPSHOT_INTERVAL
from perception import screen, input_monitor, window_tracker, process_monitor, file_watcher, ocr_interact
from semantics import event_stream, intent
from workflow import graph as wf_graph, storage as wf_storage, executor as wf_executor

log = logging.getLogger("server")

# ---------------------------------------------------------------------------
# 感知采集循环（后台线程，定期采集屏幕快照并录入事件流）
# ---------------------------------------------------------------------------
_perception_running = False
_perception_thread = None


def _perception_loop():
    """后台感知采集循环"""
    while _perception_running:
        try:
            # 屏幕语义快照（低频）
            if event_stream.get_current_session():
                # Background loop uses lightweight snapshot (no OCR, fast)
                snap = screen.take_snapshot(max_depth=4, include_controls=True, skip_ocr=True)
                event_stream.record("screen_snapshot", "screen", {
                    "foreground": snap.get("foreground"),
                    "control_count": snap.get("control_count", 0),
                    "visible_text": snap.get("visible_text", [])[:20],
                    "sensitive": snap.get("sensitive", False),
                })

                # 同步输入事件到事件流（保留完整结构含target）
                input_events = input_monitor.get_events(limit=500)
                for evt in input_events:
                    full_data = dict(evt.get("data", {}))
                    if "target" in evt:
                        full_data["target"] = evt["target"]
                    event_stream.record(evt["type"], "input_monitor", full_data)
                input_monitor.clear()  # 清空已同步的事件

                # 同步焦点事件
                focus_chain = window_tracker.get_focus_chain(limit=100)
                for entry in focus_chain:
                    event_stream.record("focus_change", "window_tracker", entry)

                # 同步进程事件
                proc_events = process_monitor.get_events(limit=200)
                for evt in proc_events:
                    event_stream.record(evt["type"], "process_monitor", evt)

                # 同步文件事件
                file_events = file_watcher.get_events(limit=200)
                for evt in file_events:
                    event_stream.record("file_change", "file_watcher", evt)

                # 强制刷新到SQLite
                event_stream._flush_batch()

        except Exception as e:
            log.warning("Perception loop error: %s", e)

        time.sleep(SCREEN_SNAPSHOT_INTERVAL)


def start_perception(watch_dirs=None):
    """启动所有感知模块"""
    global _perception_running, _perception_thread

    results = {}
    results["input"] = input_monitor.start()
    results["window"] = window_tracker.start()
    results["process"] = process_monitor.start()
    results["files"] = file_watcher.start(watch_dirs)

    if not _perception_running:
        _perception_running = True
        _perception_thread = threading.Thread(
            target=_perception_loop, daemon=True, name="perception-loop"
        )
        _perception_thread.start()
        results["loop"] = "started"
    else:
        results["loop"] = "already running"

    return results


def stop_perception():
    """停止所有感知模块"""
    global _perception_running
    _perception_running = False

    results = {}
    results["input"] = input_monitor.stop()
    results["window"] = window_tracker.stop()
    results["process"] = process_monitor.stop()
    results["files"] = file_watcher.stop()
    return results


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class CognitiveAgentHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # 静默HTTP日志

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length > 0 else {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        def _q(key, default=None):
            return qs.get(key, [default])[0]

        # --- 健康检查 ---
        if path == "/health":
            self._json({
                "status": "ok",
                "service": "cognitive-agent",
                "perception_running": _perception_running,
                "session": event_stream.get_current_session(),
                "uptime_s": round(time.time() - _start_time, 1),
            })

        # --- 屏幕快照 ---
        elif path == "/snapshot":
            include_controls = _q("controls", "true").lower() != "false"
            max_depth = int(_q("depth", "6"))
            snap = screen.take_snapshot(max_depth=max_depth, include_controls=include_controls)
            self._json(snap)

        # --- 会话管理 ---
        elif path == "/session/status":
            sid = event_stream.get_current_session()
            if sid:
                self._json(event_stream.get_session_stats(sid))
            else:
                self._json({"active": False, "session_id": None})

        elif path == "/session/list":
            limit = int(_q("limit", "20"))
            self._json(event_stream.list_sessions(limit))

        elif path == "/session/events":
            self._json(event_stream.query_events(
                session_id=_q("session"),
                event_type=_q("type"),
                since=_q("since"),
                until=_q("until"),
                limit=int(_q("limit", "100")),
                offset=int(_q("offset", "0")),
            ))

        elif path == "/session/stats":
            self._json(event_stream.get_session_stats(_q("session")))

        # --- 输入事件 ---
        elif path == "/input/events":
            self._json(input_monitor.get_events(
                limit=int(_q("limit", "100")),
                event_type=_q("type"),
                since=_q("since"),
            ))

        elif path == "/input/stats":
            self._json(input_monitor.get_stats())

        # --- 窗口焦点 ---
        elif path == "/focus/current":
            self._json(window_tracker.get_current() or {"window": None})

        elif path == "/focus/chain":
            self._json(window_tracker.get_focus_chain(int(_q("limit", "50"))))

        elif path == "/focus/stats":
            self._json(window_tracker.get_stats())

        # --- 进程 ---
        elif path == "/process/events":
            self._json(process_monitor.get_events(
                limit=int(_q("limit", "50")),
                event_type=_q("type"),
            ))

        elif path == "/process/stats":
            self._json(process_monitor.get_stats())

        # --- 文件 ---
        elif path == "/files/events":
            self._json(file_watcher.get_events(
                limit=int(_q("limit", "50")),
                action=_q("action"),
            ))

        elif path == "/files/stats":
            self._json(file_watcher.get_stats())

        # --- 感知状态 ---
        elif path == "/perception/status":
            self._json({
                "running": _perception_running,
                "input": input_monitor.get_stats(),
                "window": window_tracker.get_stats(),
                "process": process_monitor.get_stats(),
                "files": file_watcher.get_stats(),
                "session": event_stream.get_current_session(),
            })

        # --- OCR交互 ---
        elif path == "/ocr/scan":
            self._json(ocr_interact.scan())

        elif path.startswith("/ocr/find/"):
            target = path[len("/ocr/find/"):]
            from urllib.parse import unquote
            target = unquote(target)
            self._json(ocr_interact.find_text(target))

        # --- 意图分析 ---
        elif path == "/analyze/summary":
            events = event_stream.query_events(limit=5000)
            if events:
                result = intent.analyze_session(events)
                self._json(result["summary"])
            else:
                self._json({"error": "no events in session"})

        # --- 工作流 ---
        elif path == "/workflows":
            self._json(wf_storage.list_all())

        elif path.startswith("/workflow/") and not path.startswith("/workflow/save") \
                and not path.startswith("/workflow/delete") \
                and not path.startswith("/workflow/extract") \
                and not path.startswith("/workflow/execute"):
            wf_id = path.split("/")[-1]
            wf = wf_storage.load(wf_id)
            if wf:
                self._json(wf)
            else:
                self._json({"error": "not found", "id": wf_id}, 404)

        else:
            self._json({"error": "not found", "path": path}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            data = self._body()
        except Exception:
            data = {}

        # --- 会话管理 ---
        if path == "/session/start":
            # 同时启动感知模块
            session_result = event_stream.start_session(data.get("metadata"))
            if "error" not in session_result:
                perception_result = start_perception(data.get("watch_dirs"))
                session_result["perception"] = perception_result
            self._json(session_result)

        elif path == "/session/stop":
            # 同时停止感知模块
            perception_result = stop_perception()
            session_result = event_stream.stop_session()
            session_result["perception"] = perception_result
            self._json(session_result)

        # --- 感知控制 ---
        elif path == "/perception/start":
            self._json(start_perception(data.get("watch_dirs")))

        elif path == "/perception/stop":
            self._json(stop_perception())

        # --- 输入控制 ---
        elif path == "/input/clear":
            self._json(input_monitor.clear())

        # --- OCR交互 ---
        elif path == "/ocr/click":
            target = data.get("text", "")
            if not target:
                self._json({"error": "provide text"}, 400)
            else:
                self._json(ocr_interact.click_text(
                    target,
                    exact=data.get("exact", False),
                    button=data.get("button", "left"),
                    index=data.get("index", 0),
                ))

        elif path == "/ocr/type":
            target = data.get("target", "")
            text = data.get("text", "")
            if not target or not text:
                self._json({"error": "provide target and text"}, 400)
            else:
                self._json(ocr_interact.type_at(
                    target, text,
                    clear_first=data.get("clear_first", False),
                ))

        # --- 意图分析 ---
        elif path == "/analyze":
            events = event_stream.query_events(
                event_type=data.get("type"),
                since=data.get("since"),
                until=data.get("until"),
                limit=int(data.get("limit", 5000)),
            )
            if events:
                result = intent.analyze_session(events, time_window_s=data.get("time_window", 3.0))
                self._json(result)
            else:
                self._json({"error": "no events"})

        # --- 工作流CRUD ---
        elif path == "/workflow/save":
            self._json(wf_storage.save(data))

        elif path == "/workflow/delete":
            wf_id = data.get("id", "")
            if not wf_id:
                self._json({"error": "provide id"}, 400)
            else:
                self._json(wf_storage.delete(wf_id))

        elif path == "/workflow/extract":
            # 从当前会话事件提取工作流
            events = event_stream.query_events(limit=5000)
            if not events:
                self._json({"error": "no events in session"})
            else:
                analysis = intent.analyze_session(events)
                wf = wf_graph.extract_workflow_from_intents(
                    analysis["intents"],
                    name=data.get("name"),
                    description=data.get("description"),
                )
                if wf:
                    wf_dict = wf.to_dict()
                    wf_storage.save(wf_dict)
                    self._json(wf_dict)
                else:
                    self._json({"error": "could not extract workflow"})

        elif path == "/workflow/execute":
            wf_id = data.get("id")
            wf_def = data.get("workflow")  # 也可以直接传入工作流定义
            params = data.get("params", {})
            dry_run = data.get("dry_run", False)
            backend_type = data.get("backend", "local")  # "local" or "remote_agent"

            if not wf_id and not wf_def:
                self._json({"error": "provide id or workflow"}, 400)
            else:
                wf_dict = wf_def or wf_storage.load(wf_id)
                if not wf_dict:
                    self._json({"error": "workflow not found", "id": wf_id}, 404)
                else:
                    if backend_type == "remote_agent":
                        backend = wf_executor.RemoteAgentBackend(data.get("url", "http://localhost:9903"))
                    else:
                        backend = wf_executor.LocalBackend()
                    executor = wf_executor.WorkflowExecutor(backend=backend)
                    result = executor.execute(wf_dict, param_values=params, dry_run=dry_run)
                    self._json(result)

        # --- 清理 ---
        elif path == "/cleanup":
            hours = data.get("max_age_hours", 72)
            self._json(event_stream.cleanup(hours))

        else:
            self._json({"error": "not found", "path": path}, 404)


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------
_start_time = time.time()


def main():
    parser = argparse.ArgumentParser(description="认知代理 HTTP API Server")
    parser.add_argument("--port", type=int, default=SERVER_PORT, help="HTTP端口")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    server = ThreadingHTTPServer(("0.0.0.0", args.port), CognitiveAgentHandler)
    log.info("Cognitive Agent started on http://localhost:%d", args.port)
    log.info("API: /health | /snapshot | /session/start | /perception/status")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down...")
        stop_perception()
        server.shutdown()


if __name__ == "__main__":
    main()
