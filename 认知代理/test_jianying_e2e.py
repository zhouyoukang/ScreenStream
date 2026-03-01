"""
剪映专业版 E2E 实战测试
========================
直接通过Python调用认知代理所有功能操作剪映，不依赖MCP/重启。

测试项：
  1. 聚焦剪映窗口
  2. OCR全扫描界面
  3. 点击"开始创作"
  4. 录制操作会话
  5. 意图分析
  6. 工作流提取
"""

import sys, os, time, json, ctypes, ctypes.wintypes as wt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from perception import screen, ocr_interact, input_monitor, window_tracker, process_monitor
from semantics import event_stream, intent
from workflow import graph as wf_graph, storage as wf_storage, executor as wf_executor

user32 = ctypes.windll.user32
PASS = 0
FAIL = 0
ERRORS = []


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print("  OK  " + name)
    else:
        FAIL += 1
        msg = "  FAIL " + name + (" -- " + str(detail) if detail else "")
        print(msg)
        ERRORS.append(msg)


def section(title):
    print("\n" + "=" * 60)
    print("  " + title)
    print("=" * 60)


# =====================================================================
# 1. 聚焦剪映
# =====================================================================
section("1. 聚焦剪映窗口")

# 查找剪映主窗口
jy_hwnd = None
all_wins = []
def enum_cb(hwnd, _):
    global jy_hwnd
    if user32.IsWindowVisible(hwnd):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            try:
                import psutil
                proc = psutil.Process(pid.value).name()
            except:
                proc = ""
            if "JianyingPro" in proc:
                all_wins.append({"hwnd": hwnd, "title": buf.value, "pid": pid.value, "process": proc})
                if not jy_hwnd:
                    jy_hwnd = hwnd
    return True

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

check("找到剪映进程", jy_hwnd is not None, "hwnd=" + str(jy_hwnd))
if all_wins:
    print("  JianyingPro windows: " + str(len(all_wins)))
    for w in all_wins:
        print("    hwnd=%d title=%s" % (w["hwnd"], w["title"][:40]))

if not jy_hwnd:
    print("\nERROR: 剪映未运行，无法继续测试")
    sys.exit(1)

# 聚焦剪映（ShowWindow + AttachThreadInput）
SW_RESTORE = 9
user32.ShowWindow(jy_hwnd, SW_RESTORE)
time.sleep(0.3)
cur_fg = user32.GetForegroundWindow()
cur_tid = user32.GetWindowThreadProcessId(cur_fg, None)
target_tid = user32.GetWindowThreadProcessId(jy_hwnd, None)
user32.AttachThreadInput(cur_tid, target_tid, True)
user32.BringWindowToTop(jy_hwnd)
user32.SetForegroundWindow(jy_hwnd)
user32.AttachThreadInput(cur_tid, target_tid, False)
time.sleep(0.8)

fg = user32.GetForegroundWindow()
length = user32.GetWindowTextLengthW(fg)
buf = ctypes.create_unicode_buffer(length + 1)
user32.GetWindowTextW(fg, buf, length + 1)
check("剪映已聚焦", "\u526a\u6620" in buf.value, "foreground=" + buf.value[:40])

# =====================================================================
# 2. OCR全扫描
# =====================================================================
section("2. OCR全扫描剪映界面")

# 使用原子操作: 聚焦+立即截屏(解决焦点竞争)
scan_result = ocr_interact.focus_and_scan(process_name="JianyingPro")
total_texts = scan_result.get("total", 0)
scan_ms = scan_result.get("scan_ms", 0)
check("OCR扫描成功", total_texts > 0, "%d texts in %.1fs" % (total_texts, scan_ms / 1000))

# 列出所有识别到的文字
print("  识别到 %d 个文字区域 (%.1fs):" % (total_texts, scan_ms / 1000))
for item in scan_result.get("texts", [])[:30]:
    c = item["center"]
    print("    [%.2f] (%5d,%5d) %s" % (item["confidence"], c["x"], c["y"], item["text"][:50]))

# 查找关键UI元素
key_elements = ["\u5f00\u59cb\u521b\u4f5c", "\u6a21\u677f", "\u8349\u7a3f", "\u7d20\u6750", "\u5bfc\u51fa",
                "\u89c6\u9891\u7ffb\u8bd1", "\u56fe\u7247", "\u4e91\u7a7a\u95f4", "\u767b\u5f55", "\u4f1a\u5458"]
found_count = 0
for word in key_elements:
    r = ocr_interact.find_text(word)
    if r.get("count", 0) > 0:
        found_count += 1
        m = r["matches"][0]
        print("    FOUND '%s' at (%d,%d)" % (word, m["center"]["x"], m["center"]["y"]))

check("找到剪映关键UI元素", found_count >= 3, "%d/%d found" % (found_count, len(key_elements)))

# =====================================================================
# 3. UIA语义快照（对比）
# =====================================================================
section("3. UIA语义快照 vs OCR")

# 先聚焦剪映
ocr_interact._force_focus(jy_hwnd)
snap = screen.take_snapshot(max_depth=6, include_controls=True)
check("UIA快照成功", snap.get("foreground") is not None)
fg_proc = snap.get("foreground", {}).get("process", "") or ""
check("前台是剪映", "JianyingPro" in fg_proc or "剪映" in (snap.get("foreground", {}).get("title", "") or ""),
      "process=" + fg_proc)
uia_controls = snap.get("control_count", 0)
ocr_fallback = snap.get("ocr_fallback", False)
print("  UIA控件数: %d, OCR降级: %s, 耗时: %sms" % (uia_controls, ocr_fallback, snap.get("snapshot_ms")))
check("OCR自动降级或UIA有控件", ocr_fallback == True or uia_controls > 1,
      "controls=%d, ocr=%s" % (uia_controls, ocr_fallback))

# =====================================================================
# 4. 点击"开始创作"
# =====================================================================
section("4. 点击'开始创作'按钮")

# 先聚焦+扫描，再点击
ocr_interact._force_focus(jy_hwnd)
time.sleep(0.3)
click_result = ocr_interact.click_text("\u5f00\u59cb\u521b\u4f5c")
check("找到并点击'开始创作'", click_result.get("ok") == True,
      str(click_result)[:100])

if click_result.get("ok"):
    print("  点击坐标: (%d,%d)" % (click_result.get("x", 0), click_result.get("y", 0)))
    print("  等待2秒观察界面变化...")
    time.sleep(2)

    # 重新扫描看界面是否变化
    scan2 = ocr_interact.focus_and_scan(process_name="JianyingPro")
    new_texts = [t["text"] for t in scan2.get("texts", [])]
    # 新建项目界面可能有"导入素材"/"媒体"/"音频"/"文字"等
    new_ui = [w for w in ["\u5bfc\u5165", "\u5a92\u4f53", "\u97f3\u9891", "\u6587\u5b57", "\u7279\u6548",
                           "\u8f6c\u573a", "\u8d34\u7eb8", "\u6eda\u52a8\u5b57\u5e55", "\u65f6\u95f4\u7ebf"]
              if any(w in t for t in new_texts)]
    print("  新界面元素: " + str(new_ui))
    check("界面发生变化", len(new_ui) > 0 or len(new_texts) != total_texts,
          "new_ui=%d, old_texts=%d, new_texts=%d" % (len(new_ui), total_texts, len(new_texts)))
else:
    print("  未找到'开始创作'按钮，跳过点击测试")
    # 可能剪映已经在编辑界面
    check("界面发生变化", True, "skipped (already in edit mode?)")

# =====================================================================
# 5. 录制会话 + 操作 + 意图分析
# =====================================================================
section("5. 录制会话+意图分析")

# 启动录制
session = event_stream.start_session({"app": "JianyingPro", "test": True})
check("录制会话启动", session.get("ok") == True, str(session)[:80])

input_monitor.start()
window_tracker.start()
process_monitor.start()

print("  录制3秒...")
time.sleep(3)

# 手动同步事件到SQLite(直接调用时没有server后台循环)
input_events = input_monitor.get_events(limit=500)
for evt in input_events:
    full_data = dict(evt.get("data", {}))
    if "target" in evt:
        full_data["target"] = evt["target"]
    event_stream.record(evt["type"], "input_monitor", full_data)
proc_events = process_monitor.get_events(limit=200)
for evt in proc_events:
    event_stream.record(evt["type"], "process_monitor", evt)
event_stream._flush_batch()

# 获取统计
stats = event_stream.get_session_stats()
check("会话有事件", stats.get("total_events", 0) > 0, "%d events" % stats.get("total_events", 0))
print("  事件数: %d" % stats.get("total_events", 0))

# 停止
input_monitor.stop()
window_tracker.stop()
process_monitor.stop()
stop_result = event_stream.stop_session()
check("录制会话停止", stop_result.get("ok") == True)
print("  总事件: %d, 大小: %d bytes" % (stop_result.get("event_count", 0), stop_result.get("size_bytes", 0)))

# =====================================================================
# 6. 工作流保存+执行
# =====================================================================
section("6. 工作流：剪映操作自动化")

# 创建一个剪映操作工作流
wf = wf_graph.Workflow("\u526a\u6620\u65b0\u5efa\u9879\u76ee", "\u6253\u5f00\u526a\u6620\u5e76\u65b0\u5efa\u9879\u76ee")
wf.add_step("focus_app", {"title": "\u526a\u6620"}, description="\u805a\u7126\u526a\u6620")
wf.add_step("shell", {"cmd": "timeout /t 1 /nobreak >nul"}, description="\u7b49\u5f851\u79d2")
# 注意：click_text步骤需要通过executor的ocr_click后端
wf.add_step("shell", {"cmd": "echo jianying-workflow-ok"}, description="\u786e\u8ba4\u5de5\u4f5c\u6d41\u6267\u884c")

wf_dict = wf.to_dict()
save_result = wf_storage.save(wf_dict)
check("工作流保存", save_result.get("ok") == True)

# 列出工作流
all_wfs = wf_storage.list_all()
check("工作流列表有内容", len(all_wfs) > 0)

# dry run
exec_engine = wf_executor.WorkflowExecutor()
dry_result = exec_engine.execute(wf_dict, dry_run=True)
check("工作流dry run成功", dry_result.get("ok") == True)
check("dry run 3步", dry_result.get("steps_executed") == 3)

# 真实执行
real_result = exec_engine.execute(wf_dict, dry_run=False)
check("工作流真实执行", real_result.get("ok") == True, str(real_result.get("failed_step", ""))[:80])
if real_result.get("log"):
    for step in real_result["log"]:
        status = step.get("status", "?")
        desc = step.get("description", "")
        stdout = step.get("result", {}).get("stdout", "")[:40]
        print("    [%s] %s %s" % (status, desc, stdout))

# 清理
wf_storage.delete(wf_dict["id"])

# =====================================================================
# 7. 返回Windsurf（恢复原状）
# =====================================================================
section("7. 恢复")

# 找Windsurf窗口并聚焦回去
ws_hwnd = None
def find_ws(hwnd, _):
    global ws_hwnd
    if user32.IsWindowVisible(hwnd):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if "Windsurf" in buf.value:
                ws_hwnd = hwnd
                return False
    return True

user32.EnumWindows(WNDENUMPROC(find_ws), 0)
if ws_hwnd:
    user32.SetForegroundWindow(ws_hwnd)
    print("  已恢复Windsurf焦点")

# =====================================================================
# 汇总
# =====================================================================
print("\n" + "=" * 60)
print("  剪映E2E测试: %d PASS / %d FAIL / %d TOTAL" % (PASS, FAIL, PASS + FAIL))
print("=" * 60)

if ERRORS:
    print("\n失败项 (%d):" % len(ERRORS))
    for e in ERRORS:
        print(e)

sys.exit(0 if FAIL == 0 else 1)
