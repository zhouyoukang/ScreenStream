"""
认知代理全量自测脚本
=====================
测试所有模块：感知/语义/工作流/API端点
直接通过HTTP API测试（server.py必须运行在:9070）
"""

import json
import time
import urllib.request
import urllib.error
import sys
import os

BASE = "http://localhost:9070"
PASS = 0
FAIL = 0
ERRORS = []


def _get(path):
    """GET请求（含错误响应体解析）"""
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except Exception:
            return {"_error": str(e), "_status": e.code}
    except Exception as e:
        return {"_error": str(e)}


def _post(path, data=None):
    """POST请求（含错误响应体解析）"""
    try:
        body = json.dumps(data or {}).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE}{path}", data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except Exception:
            return {"_error": str(e), "_status": e.code}
    except Exception as e:
        return {"_error": str(e)}


def check(name, condition, detail=""):
    """断言检查"""
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        msg = f"  ❌ {name}" + (f" — {detail}" if detail else "")
        print(msg)
        ERRORS.append(msg)


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# =====================================================================
# 1. 健康检查
# =====================================================================
section("1. 健康检查")
r = _get("/health")
check("GET /health 返回ok", r.get("status") == "ok", str(r))
check("service名称正确", r.get("service") == "cognitive-agent")
check("session初始为null", r.get("session") is None)

# =====================================================================
# 2. 屏幕快照
# =====================================================================
section("2. 屏幕语义快照")

# 轻量快照（无控件树）
r = _get("/snapshot?controls=false")
check("轻量快照有foreground", "foreground" in r and r["foreground"] is not None, str(r.get("foreground", {}).get("title", ""))[:60])
check("轻量快照control_count=0", r.get("control_count") == 0)
check("轻量快照<200ms", r.get("snapshot_ms", 9999) < 200, f"{r.get('snapshot_ms')}ms")
check("foreground有hwnd", r.get("foreground", {}).get("hwnd") is not None)
check("foreground有process", bool(r.get("foreground", {}).get("process")))

# 完整快照（含控件树）
r = _get("/snapshot?depth=4")
check("完整快照有controls", isinstance(r.get("controls"), list))
check("完整快照controls>0", r.get("control_count", 0) > 0, f"{r.get('control_count')} controls")
check("完整快照<3000ms", r.get("snapshot_ms", 9999) < 3000, f"{r.get('snapshot_ms')}ms")
check("有visible_text", isinstance(r.get("visible_text"), list))
check("sensitive字段存在", "sensitive" in r)

# =====================================================================
# 3. 会话管理（录制→采集→查询→停止）
# =====================================================================
section("3. 会话录制全周期")

# 启动录制
r = _post("/session/start")
check("session/start成功", r.get("ok") == True, str(r))
session_id = r.get("session_id", "")
check("返回session_id", bool(session_id), session_id)
check("perception同时启动", "perception" in r)
check("input已启动", r.get("perception", {}).get("input", {}).get("status") == "started")
check("window已启动", r.get("perception", {}).get("window", {}).get("status") == "started")
check("process已启动", r.get("perception", {}).get("process", {}).get("status") == "started")
check("files已启动", r.get("perception", {}).get("files", {}).get("status") == "started")

# 等待采集
print("  ⏳ 等待5秒采集数据...")
time.sleep(5)

# 感知状态
r = _get("/perception/status")
check("感知运行中", r.get("running") == True)
check("input模块running", r.get("input", {}).get("running") == True)
check("window模块running", r.get("window", {}).get("running") == True)
check("process模块running", r.get("process", {}).get("running") == True)
check("files模块running", r.get("files", {}).get("running") == True)
check("session_id一致", r.get("session") == session_id)

# 会话状态
r = _get("/session/status")
check("会话活跃", r.get("active") == True)
check("有事件", r.get("total_events", 0) > 0, f"{r.get('total_events')} events")
check("有字节数", r.get("total_bytes", 0) > 0)

# 查询事件
r = _get("/session/events?limit=10")
check("查询返回列表", isinstance(r, list))
check("事件有内容", len(r) > 0, f"{len(r)} events")
if r:
    evt = r[0]
    check("事件有timestamp", "timestamp" in evt)
    check("事件有event_type", "event_type" in evt)
    check("事件有data", "data" in evt)

# 按类型查询
r = _get("/session/events?type=screen_snapshot&limit=5")
check("按类型查询工作", isinstance(r, list))

# 输入事件
r = _get("/input/events?limit=10")
check("input/events返回列表", isinstance(r, list))

r = _get("/input/stats")
check("input/stats有running", "running" in r)

# 焦点
r = _get("/focus/current")
check("focus/current返回", r is not None and "_error" not in r)

r = _get("/focus/chain?limit=10")
check("focus/chain返回列表", isinstance(r, list))

r = _get("/focus/stats")
check("focus/stats有running", "running" in r)

# 进程
r = _get("/process/events?limit=10")
check("process/events返回列表", isinstance(r, list))
check("有进程事件", len(r) > 0, f"{len(r)} events")

r = _get("/process/stats")
check("process/stats有running", "running" in r)
check("process_count>0", r.get("current_process_count", 0) > 0)

# 文件
r = _get("/files/events?limit=10")
check("files/events返回列表", isinstance(r, list))

r = _get("/files/stats")
check("files/stats有running", "running" in r)
check("files/stats有watching", isinstance(r.get("watching"), list))

# 会话统计
r = _get("/session/stats")
check("session/stats有by_type", "by_type" in r)

# =====================================================================
# 4. 意图分析
# =====================================================================
section("4. 意图分析")

r = _post("/analyze", {"limit": 1000})
if "_error" in r or "error" in r:
    check("analyze返回结果", False, str(r))
else:
    check("analyze有intents", "intents" in r)
    check("analyze有summary", "summary" in r)
    check("analyze有cross_app_flows", "cross_app_flows" in r)
    check("summary有total_groups", "total_groups" in r.get("summary", {}))

r = _get("/analyze/summary")
check("analyze/summary返回", "_error" not in r)

# =====================================================================
# 5. 停止录制
# =====================================================================
section("5. 停止录制")

r = _post("/session/stop")
check("session/stop成功", r.get("ok") == True, str(r))
check("event_count>0", r.get("event_count", 0) > 0, f"{r.get('event_count')} events")
check("size_bytes>0", r.get("size_bytes", 0) > 0, f"{r.get('size_bytes')} bytes")
check("perception已停止", "perception" in r)

# 验证确实停止了
r = _get("/perception/status")
check("感知已停止", r.get("running") == False)

# 会话列表
r = _get("/session/list")
check("session/list返回列表", isinstance(r, list))
check("session/list有记录", len(r) > 0)

# =====================================================================
# 6. 工作流CRUD+执行
# =====================================================================
section("6. 工作流CRUD+执行")

# 保存工作流
wf = {
    "id": "wf_selftest",
    "name": "自测工作流",
    "description": "认知代理自测用",
    "version": 1,
    "parameters": {"msg": {"type": "string", "default": "hello-cognitive-agent"}},
    "steps": [
        {"id": "s1", "action": "shell", "params": {"cmd": "echo ${msg}"}, "description": "echo测试"},
        {"id": "s2", "action": "shell", "params": {"cmd": "python --version"}, "description": "Python版本"},
    ],
    "triggers": {"manual": True},
    "tags": ["test"],
}
r = _post("/workflow/save", wf)
check("workflow/save成功", r.get("ok") == True, str(r))

# 列出工作流
r = _get("/workflows")
check("workflows列表有内容", len(r) > 0)
check("包含selftest工作流", any(w.get("id") == "wf_selftest" for w in r))

# 获取工作流
r = _get("/workflow/wf_selftest")
check("workflow/id获取成功", r.get("name") == "自测工作流")
check("工作流有steps", len(r.get("steps", [])) == 2)

# 执行工作流（dry run）
r = _post("/workflow/execute", {"id": "wf_selftest", "dry_run": True})
check("dry_run成功", r.get("ok") == True)
check("dry_run steps=2", r.get("steps_executed") == 2)

# 执行工作流（真实执行）
r = _post("/workflow/execute", {"id": "wf_selftest", "params": {"msg": "selftest-ok"}})
check("真实执行成功", r.get("ok") == True, str(r.get("failed_step")))
check("真实执行steps=2", r.get("steps_executed") == 2)
# 验证echo输出
if r.get("log"):
    s1_result = r["log"][0].get("result", {})
    check("echo输出正确", "selftest-ok" in s1_result.get("stdout", ""), s1_result.get("stdout", "")[:50])
    s2_result = r["log"][1].get("result", {})
    check("python版本检测成功", "Python" in s2_result.get("stdout", ""), s2_result.get("stdout", "")[:50])

# 从会话提取工作流
r = _post("/workflow/extract", {"name": "提取测试"})
check("extract返回结果", "_error" not in r, str(r)[:100])
if "error" not in r:
    check("extract有steps", len(r.get("steps", [])) > 0, f"{len(r.get('steps', []))} steps")
    check("extract已保存", bool(r.get("id")))

# 删除工作流
r = _post("/workflow/delete", {"id": "wf_selftest"})
check("workflow/delete成功", r.get("ok") == True)

r = _get("/workflows")
check("删除后不存在", not any(w.get("id") == "wf_selftest" for w in r))

# 内联执行
r = _post("/workflow/execute", {
    "workflow": {
        "id": "wf_inline",
        "name": "Inline",
        "steps": [{"id": "s1", "action": "shell", "params": {"cmd": "echo inline-ok"}, "description": "inline echo"}]
    }
})
check("内联执行成功", r.get("ok") == True)
if r.get("log"):
    check("内联echo正确", "inline-ok" in r["log"][0].get("result", {}).get("stdout", ""))

# =====================================================================
# 7. 清理
# =====================================================================
section("7. 清理")

r = _post("/cleanup", {"max_age_hours": 0})
check("cleanup成功", r.get("ok") == True)

# =====================================================================
# 8. 边界/错误处理
# =====================================================================
section("8. 边界/错误处理")

r = _get("/nonexistent")
check("404处理", r.get("error") == "not found" or "not found" in str(r))

r = _post("/session/stop")
check("重复stop处理", "error" in r, str(r)[:80])

r = _post("/workflow/execute", {})
check("缺少参数处理", "error" in r)

r = _get("/workflow/wf_nonexistent")
check("不存在的工作流处理", "error" in r or "not found" in str(r).lower())

# =====================================================================
# 汇总
# =====================================================================
print(f"\n{'='*60}")
print(f"  测试完成: {PASS} PASS / {FAIL} FAIL / {PASS+FAIL} TOTAL")
print(f"{'='*60}")

if ERRORS:
    print(f"\n失败项 ({len(ERRORS)}):")
    for e in ERRORS:
        print(e)

sys.exit(0 if FAIL == 0 else 1)
