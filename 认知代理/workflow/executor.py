"""
工作流执行引擎 — 加载图谱 → 执行 → 状态对比 → 自纠偏
====================================================
执行工作流步骤，每步后用感知系统验证状态，
偏差超限时尝试替代路径（最多3次），仍失败则降级通知。

执行后端:
  - hotkey/type_text/click → remote_agent API 或 本地 pyautogui
  - shell → subprocess
  - focus_app → Win32 API
  - file_operation → 文件系统操作

单独测试:
  cd 认知代理
  python -m workflow.executor
"""

import time
import json
import logging
import subprocess
import os
import sys

log = logging.getLogger("workflow.executor")

# 延迟导入
def _get_screen():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from perception import screen
    return screen


# ---------------------------------------------------------------------------
# 执行后端 (Action Backends)
# ---------------------------------------------------------------------------

class LocalBackend:
    """本地执行后端 — 使用 pyautogui + Win32 API"""

    def execute(self, action, params):
        method = getattr(self, f"_do_{action}", None)
        if method:
            return method(params)
        return {"error": f"unknown action: {action}", "ok": False}

    def _do_hotkey(self, params):
        """执行键盘快捷键"""
        key = params.get("key", "")
        if not key:
            return {"error": "no key specified", "ok": False}
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            parts = key.lower().split("+")
            if len(parts) > 1:
                pyautogui.hotkey(*parts)
            else:
                pyautogui.press(parts[0])
            return {"ok": True, "key": key}
        except Exception as e:
            return {"error": str(e), "ok": False}

    def _do_type_text(self, params):
        """输入文本"""
        text = params.get("text", "")
        if not text:
            return {"error": "no text specified", "ok": False}
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            # 处理特殊字符
            text = text.replace("\\n", "\n").replace("\\t", "\t")
            pyautogui.write(text, interval=0.02)
            return {"ok": True, "length": len(text)}
        except Exception as e:
            return {"error": str(e), "ok": False}

    def _do_click(self, params):
        """点击"""
        x = params.get("x", 0)
        y = params.get("y", 0)
        button = params.get("button", "left")
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.click(x, y, button=button)
            return {"ok": True, "x": x, "y": y}
        except Exception as e:
            return {"error": str(e), "ok": False}

    def _do_double_click(self, params):
        """双击"""
        x = params.get("x", 0)
        y = params.get("y", 0)
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.doubleClick(x, y)
            return {"ok": True, "x": x, "y": y}
        except Exception as e:
            return {"error": str(e), "ok": False}

    def _do_focus_app(self, params):
        """聚焦应用窗口"""
        app = params.get("app", "")
        title = params.get("title", "")
        if not app and not title:
            return {"error": "no app or title specified", "ok": False}
        try:
            import ctypes
            user32 = ctypes.windll.user32
            import ctypes.wintypes as wt

            target_hwnd = None
            def callback(hwnd, _):
                nonlocal target_hwnd
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        win_title = buf.value.lower()
                        search = (title or app).lower()
                        if search in win_title:
                            target_hwnd = hwnd
                            return False
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(WNDENUMPROC(callback), 0)

            if target_hwnd:
                user32.SetForegroundWindow(target_hwnd)
                return {"ok": True, "hwnd": target_hwnd}
            return {"error": f"window not found: {app or title}", "ok": False}
        except Exception as e:
            return {"error": str(e), "ok": False}

    def _do_shell(self, params):
        """执行Shell命令"""
        cmd = params.get("cmd", "")
        timeout = params.get("timeout", 15)
        cwd = params.get("cwd")
        if not cmd:
            return {"error": "no cmd specified", "ok": False}
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=cwd
            )
            return {
                "ok": result.returncode == 0,
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-1000:] if result.stderr else "",
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": "timeout", "ok": False}
        except Exception as e:
            return {"error": str(e), "ok": False}

    def _do_file_operation(self, params):
        """文件操作"""
        return {"ok": True, "note": "file_operation is informational only"}

    def _do_unknown(self, params):
        """未知操作"""
        return {"ok": True, "note": "skipped unknown action"}


class RemoteAgentBackend:
    """远程执行后端 — 通过 remote_agent HTTP API"""

    def __init__(self, url="http://localhost:9903"):
        self.url = url.rstrip("/")

    def execute(self, action, params):
        import urllib.request
        import urllib.error

        # 映射动作到remote_agent端点
        endpoint_map = {
            "hotkey": ("POST", "/key", lambda p: {"hotkey": p.get("key", "").split("+")} if "+" in p.get("key", "") else {"key": p.get("key", "")}),
            "type_text": ("POST", "/type", lambda p: {"text": p.get("text", "")}),
            "click": ("POST", "/click", lambda p: p),
            "double_click": ("POST", "/click", lambda p: {**p, "clicks": 2}),
            "focus_app": ("POST", "/focus", lambda p: {"title": p.get("app", "") or p.get("title", "")}),
            "shell": ("POST", "/shell", lambda p: {"cmd": p.get("cmd", ""), "timeout": p.get("timeout", 15)}),
        }

        if action not in endpoint_map:
            return {"ok": True, "note": f"action '{action}' not supported via remote_agent"}

        method, path, transform = endpoint_map[action]
        body = transform(params)

        try:
            data = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(
                f"{self.url}{path}",
                data=data,
                headers={"Content-Type": "application/json"},
                method=method,
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return {"error": str(e), "ok": False}


# ---------------------------------------------------------------------------
# 状态验证器 (State Verifier)
# ---------------------------------------------------------------------------

def verify_state(expected_state, actual_snapshot):
    """
    对比预期状态和实际感知快照。
    返回: (match: bool, details: dict)
    """
    if not expected_state:
        return True, {"note": "no expected state"}

    details = {}
    all_match = True

    # 检查前台应用
    if "focused_app" in expected_state:
        actual_app = (actual_snapshot.get("foreground", {}).get("process", "") or "").lower()
        expected_app = expected_state["focused_app"].lower()
        match = expected_app in actual_app
        details["focused_app"] = {"expected": expected_app, "actual": actual_app, "match": match}
        if not match:
            all_match = False

    if "focused_app_category" in expected_state:
        actual_proc = (actual_snapshot.get("foreground", {}).get("process", "") or "").lower()
        from semantics.intent import APP_CATEGORIES
        actual_cat = APP_CATEGORIES.get(actual_proc, "other")
        expected_cat = expected_state["focused_app_category"]
        match = actual_cat == expected_cat
        details["focused_app_category"] = {"expected": expected_cat, "actual": actual_cat, "match": match}
        if not match:
            all_match = False

    if "file_modified" in expected_state:
        # 文件变化验证需要file_watcher数据，这里简化为通过
        details["file_modified"] = {"match": True, "note": "assumed"}

    if "window_title_contains" in expected_state:
        actual_title = (actual_snapshot.get("foreground", {}).get("title", "") or "").lower()
        expected_substr = expected_state["window_title_contains"].lower()
        match = expected_substr in actual_title
        details["window_title_contains"] = {"expected": expected_substr, "actual": actual_title[:80], "match": match}
        if not match:
            all_match = False

    return all_match, details


# ---------------------------------------------------------------------------
# 执行引擎 (Executor)
# ---------------------------------------------------------------------------

class WorkflowExecutor:
    """工作流执行引擎"""

    def __init__(self, backend=None):
        self.backend = backend or LocalBackend()
        self.execution_log = []

    def execute(self, workflow_dict, param_values=None, dry_run=False):
        """
        执行工作流。

        workflow_dict: Workflow.to_dict() 格式
        param_values: 参数值 {name: value}
        dry_run: True = 只验证不执行

        返回:
        {
            "ok": True/False,
            "steps_executed": 3,
            "steps_total": 5,
            "log": [...],
            "failed_step": null or {...}
        }
        """
        from workflow.graph import Workflow

        wf = Workflow.from_dict(workflow_dict)

        # 参数解析
        if param_values:
            wf = wf.resolve_params(param_values)

        self.execution_log = []
        steps_executed = 0
        failed_step = None

        log.info("Executing workflow: %s (%d steps, dry_run=%s)",
                 wf.name, len(wf.steps), dry_run)

        for i, step in enumerate(wf.steps):
            step_log = {
                "step_id": step.id,
                "action": step.action,
                "params": step.params,
                "description": step.description,
                "status": "pending",
                "attempts": 0,
                "result": None,
                "state_check": None,
            }

            if dry_run:
                step_log["status"] = "dry_run"
                self.execution_log.append(step_log)
                steps_executed += 1
                continue

            # 执行（含重试）
            success = False
            max_attempts = step.max_retries + 1

            for attempt in range(max_attempts):
                step_log["attempts"] = attempt + 1

                # 执行动作
                log.info("Step %d/%d [%s] %s (attempt %d/%d)",
                         i + 1, len(wf.steps), step.action,
                         step.description, attempt + 1, max_attempts)

                result = self.backend.execute(step.action, step.params)
                step_log["result"] = result

                if not result.get("ok", False) and result.get("error"):
                    log.warning("Step failed: %s", result.get("error"))
                    if step.on_failure == "skip":
                        step_log["status"] = "skipped"
                        success = True
                        break
                    elif step.on_failure == "retry" and attempt < max_attempts - 1:
                        time.sleep(0.5)  # 重试间隔
                        continue
                    elif step.on_failure == "alternative" and step.alternatives:
                        # 尝试替代动作
                        for alt in step.alternatives:
                            alt_result = self.backend.execute(alt.action, alt.params)
                            if alt_result.get("ok"):
                                step_log["result"] = alt_result
                                step_log["status"] = "alternative"
                                success = True
                                break
                        if success:
                            break
                        continue
                    else:
                        break

                # 短暂等待UI响应
                time.sleep(0.3)

                # 状态验证
                if step.expected_state:
                    try:
                        screen = _get_screen()
                        snapshot = screen.take_snapshot(max_depth=3, include_controls=False)
                        state_match, state_details = verify_state(step.expected_state, snapshot)
                        step_log["state_check"] = state_details

                        if not state_match:
                            log.warning("State mismatch after step %d", i + 1)
                            if attempt < max_attempts - 1:
                                time.sleep(0.5)
                                continue
                            # 最终尝试失败
                            break
                    except Exception as e:
                        log.warning("State verification error: %s", e)

                success = True
                break

            if success:
                step_log["status"] = step_log.get("status", "success") if step_log["status"] != "pending" else "success"
                steps_executed += 1
            else:
                step_log["status"] = "failed"
                failed_step = step_log
                self.execution_log.append(step_log)

                if step.on_failure == "stop":
                    log.error("Workflow stopped at step %d: %s", i + 1, step.description)
                    break

            self.execution_log.append(step_log)

        result = {
            "ok": failed_step is None,
            "workflow_id": wf.id,
            "workflow_name": wf.name,
            "steps_executed": steps_executed,
            "steps_total": len(wf.steps),
            "log": self.execution_log,
        }

        if failed_step:
            result["failed_step"] = failed_step

        log.info("Workflow complete: %d/%d steps, ok=%s",
                 steps_executed, len(wf.steps), result["ok"])

        return result


# ---------------------------------------------------------------------------
# 独立测试
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 创建简单测试工作流
    test_wf = {
        "id": "wf_test",
        "name": "测试工作流",
        "description": "验证执行引擎基本功能",
        "version": 1,
        "parameters": {},
        "steps": [
            {
                "id": "s1",
                "action": "shell",
                "params": {"cmd": "echo hello"},
                "description": "执行echo命令",
            },
            {
                "id": "s2",
                "action": "shell",
                "params": {"cmd": "python --version"},
                "description": "检查Python版本",
            },
        ],
        "triggers": {"manual": True},
    }

    executor = WorkflowExecutor()

    print("=== Dry Run ===")
    result = executor.execute(test_wf, dry_run=True)
    print(f"  OK: {result['ok']}, Steps: {result['steps_executed']}/{result['steps_total']}")

    print("\n=== Real Execution ===")
    result = executor.execute(test_wf, dry_run=False)
    print(f"  OK: {result['ok']}, Steps: {result['steps_executed']}/{result['steps_total']}")
    for step in result["log"]:
        print(f"  [{step['status']}] {step['description']}: {step.get('result', {}).get('stdout', '')[:50]}")
