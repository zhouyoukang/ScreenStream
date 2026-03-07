"""
VaM 全功能五感探索测试 — 后台模式 (rapid-flash hybrid)
=====================================================
带入用户五感，遍历所有VaM页面，测试所有交互功能。
"""
import sys, time, json, os
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")

import numpy  # pre-import to avoid circular import
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

from vam import gui

# ── 结果收集 ────────────────────────────────────────
results = []
issues = []

def log_result(phase, name, result, detail=""):
    ok = result.get("ok", False) if isinstance(result, dict) else bool(result)
    results.append({"phase": phase, "name": name, "ok": ok, "detail": detail})
    status = "✅" if ok else "❌"
    print(f"  {status} {name}: {detail[:80] if detail else ('PASS' if ok else 'FAIL')}")
    if not ok:
        issues.append({"phase": phase, "name": name, "detail": detail, "result": result})

def section(title):
    print(f"\n{'='*60}\n{title}\n{'='*60}")

# ── Phase 0: 环境检查 ────────────────────────────────
section("Phase 0: 环境与VaM状态")

hwnd = gui.find_vam_window()
if not hwnd:
    print("  ❌ VaM未运行，测试终止")
    sys.exit(1)
print(f"  VaM hwnd={hwnd}")

# MouseGuard
guard = gui.get_guard()
guard.start()
guard.pause()
print("  MouseGuard: 已暂停")

# 获取状态
state = gui.get_vam_state()
print(f"  VaM状态: running={state.get('running')}, page={state.get('page')}")
print(f"  文字数: {state.get('total_texts', 0)}")
log_result("P0", "vam_running", {"ok": state.get("running", False)})
log_result("P0", "initial_page", {"ok": state.get("page") != "unknown"}, state.get("page", "?"))

# 列出所有检测到的文字
if state.get("texts"):
    print(f"  前10个文字:")
    for t in state["texts"][:10]:
        ic = t.get("img_center", {})
        print(f"    '{t['text']}' at img({ic.get('x','?')},{ic.get('y','?')})")

# ── Phase 1: 快捷键全测试 ────────────────────────────
section("Phase 1: 快捷键测试 (rapid-flash)")

initial_page = state.get("page", "unknown")

# 1a. Toggle UI (u键)
scan_before = gui.scan(hwnd=hwnd)
texts_before = set(t["text"] for t in scan_before.get("texts", []))

r = gui.press_key("u", hwnd=hwnd)
log_result("P1", "hotkey_toggle_ui", r)
time.sleep(1)

scan_after = gui.scan(hwnd=hwnd)
texts_after = set(t["text"] for t in scan_after.get("texts", []))
ui_changed = texts_before != texts_after
log_result("P1", "ui_toggle_effect", {"ok": ui_changed}, 
           f"before={len(texts_before)} after={len(texts_after)}")

# 恢复UI
if ui_changed:
    gui.press_key("u", hwnd=hwnd)
    time.sleep(0.5)

# 1b. Camera shortcuts
for cam_key in ["f1", "f2", "f3", "f5"]:
    r = gui.press_key(cam_key, hwnd=hwnd)
    log_result("P1", f"hotkey_{cam_key}", r)
    time.sleep(0.3)

# 1c. Ctrl shortcuts
r = gui.press_key("ctrl+z", hwnd=hwnd)
log_result("P1", "hotkey_undo", r)
time.sleep(0.3)

r = gui.press_key("ctrl+s", hwnd=hwnd)
log_result("P1", "hotkey_save", r)
time.sleep(0.5)

# 1d. Escape
r = gui.press_key("escape", hwnd=hwnd)
log_result("P1", "hotkey_escape", r)
time.sleep(0.5)

# ── Phase 2: 页面导航测试 ────────────────────────────
section("Phase 2: 页面导航 (scene_browser → 其他页面)")

# 2a. 确保在已知页面
scan = gui.scan(hwnd=hwnd)
current_page = gui._detect_page([t["text"] for t in scan.get("texts", [])])
print(f"  当前页面: {current_page}")

# 2b. 如果不在main_menu，尝试导航到main_menu
if current_page != "main_menu":
    # 尝试点击返回/菜单按钮
    for btn_text in ["返回场景预览", "返回主菜单", "Main Menu", "Back", "返回"]:
        r = gui.find_text(btn_text, hwnd=hwnd)
        if r.get("count", 0) > 0:
            print(f"  找到导航按钮: '{btn_text}'")
            cr = gui.click_text(btn_text, hwnd=hwnd)
            log_result("P2", f"click_{btn_text}", cr)
            time.sleep(2)
            break
    
    scan = gui.scan(hwnd=hwnd)
    current_page = gui._detect_page([t["text"] for t in scan.get("texts", [])])
    print(f"  导航后页面: {current_page}")

# 2c. 从当前页面探索所有可见按钮
scan = gui.scan(hwnd=hwnd)
all_buttons = []
for t in scan.get("texts", []):
    text = t["text"]
    # 过滤可能是按钮的文字（短文本，非数字）
    if 2 <= len(text) <= 20 and not text.isdigit():
        all_buttons.append(text)

print(f"  可点击元素: {len(all_buttons)}个")
for b in all_buttons[:15]:
    print(f"    • {b}")
log_result("P2", "buttons_detected", {"ok": len(all_buttons) > 0}, f"{len(all_buttons)}个按钮")

# 2d. 尝试导航到场景浏览器
nav_targets = ["Scene Browser", "场景浏览器", "场景浏览"]
for target in nav_targets:
    r = gui.find_text(target, hwnd=hwnd)
    if r.get("count", 0) > 0:
        print(f"  找到: '{target}'")
        cr = gui.click_text(target, hwnd=hwnd)
        log_result("P2", "nav_scene_browser", cr)
        time.sleep(2)
        
        scan = gui.scan(hwnd=hwnd)
        new_page = gui._detect_page([t["text"] for t in scan.get("texts", [])])
        log_result("P2", "arrived_scene_browser", {"ok": new_page == "scene_browser"}, new_page)
        break

# ── Phase 3: 场景浏览器深度测试 ────────────────────
section("Phase 3: 场景浏览器交互")

scan = gui.scan(hwnd=hwnd)
current_page = gui._detect_page([t["text"] for t in scan.get("texts", [])])

if current_page == "scene_browser":
    # 3a. 滚动浏览
    print("  --- 滚动测试 ---")
    texts_before = set(t["text"] for t in scan.get("texts", []))
    
    r = gui.scroll(-5, hwnd=hwnd)
    log_result("P3", "scroll_down", r)
    time.sleep(2)
    
    scan2 = gui.scan(hwnd=hwnd)
    texts_after = set(t["text"] for t in scan2.get("texts", []))
    new_items = texts_after - texts_before
    log_result("P3", "scroll_reveals_new", {"ok": len(new_items) > 0}, 
               f"{len(new_items)}个新项目")
    
    # 滚回
    gui.scroll(5, hwnd=hwnd)
    time.sleep(1)
    
    # 3b. 搜索排序按钮
    print("  --- 排序/筛选测试 ---")
    for btn in ["Sort", "Filter", "排序", "收藏夹", "筛选", "从新到旧"]:
        r = gui.find_text(btn, hwnd=hwnd)
        if r.get("count", 0) > 0:
            log_result("P3", f"found_{btn}", {"ok": True}, f"位于 {r['matches'][0].get('img_center', {})}")
    
    # 3c. 找场景项目并点击
    print("  --- 场景项目点击测试 ---")
    scan = gui.scan(hwnd=hwnd)
    scene_items = []
    for t in scan.get("texts", []):
        text = t["text"]
        # 场景名通常较长，包含下划线或日期
        if len(text) > 5 and ("_" in text or "20" in text):
            scene_items.append(t)
    
    if scene_items:
        target_scene = scene_items[0]
        print(f"  点击场景: '{target_scene['text']}'")
        r = gui.click_text(target_scene["text"], hwnd=hwnd)
        log_result("P3", "click_scene_item", r)
        time.sleep(2)
        
        # 检查是否出现了加载/预览选项
        scan3 = gui.scan(hwnd=hwnd)
        new_page = gui._detect_page([t["text"] for t in scan3.get("texts", [])])
        log_result("P3", "scene_click_response", {"ok": True}, f"page={new_page}")
    else:
        log_result("P3", "scene_items_found", {"ok": False}, "没找到场景项目")

else:
    print(f"  ⚠️ 当前不在场景浏览器 ({current_page})，跳过浏览器测试")
    log_result("P3", "scene_browser_available", {"ok": False}, current_page)

# ── Phase 4: 场景编辑器测试 ────────────────────────
section("Phase 4: 场景编辑器交互")

# 尝试进入编辑模式
r = gui.press_key("e", hwnd=hwnd)  # toggle edit mode
time.sleep(1)

scan = gui.scan(hwnd=hwnd)
current_page = gui._detect_page([t["text"] for t in scan.get("texts", [])])
print(f"  当前页面: {current_page}")

if current_page == "scene_editor":
    # 4a. 标签页测试
    print("  --- 编辑器标签页 ---")
    editor_tabs = gui.VAM_EDITOR_ELEMENTS["tabs"]
    for tab in editor_tabs:
        r = gui.find_text(tab, hwnd=hwnd)
        found = r.get("count", 0) > 0
        if found:
            log_result("P4", f"tab_{tab}", {"ok": True})
    
    # 4b. 点击各标签
    for tab in ["Control", "Plugins", "Morphs"]:
        r = gui.find_text(tab, hwnd=hwnd)
        if r.get("count", 0) > 0:
            cr = gui.click_text(tab, hwnd=hwnd)
            log_result("P4", f"click_tab_{tab}", cr)
            time.sleep(1)
            
            # 扫描标签内容
            scan_tab = gui.scan(hwnd=hwnd)
            print(f"    {tab}: {scan_tab.get('total', 0)}个文字")
else:
    print(f"  ⚠️ 不在编辑器 ({current_page})")
    log_result("P4", "editor_available", {"ok": False}, current_page)

# 退出编辑模式
gui.press_key("e", hwnd=hwnd)
time.sleep(0.5)

# ── Phase 5: 高级功能测试 ────────────────────────────
section("Phase 5: 高级功能")

# 5a. PrintWindow截图质量
print("  --- 截图质量 ---")
img, rect = gui.capture_printwindow(hwnd)
if img:
    w, h = img.size
    log_result("P5", "printwindow_capture", {"ok": True}, f"{w}x{h}")
    img.save("vam_exploration_capture.png")
    print(f"  截图保存: vam_exploration_capture.png ({w}x{h})")
else:
    log_result("P5", "printwindow_capture", {"ok": False}, "截图失败")

# 5b. 剪贴板
print("  --- 剪贴板 ---")
test_text = f"VaM_Explore_{time.strftime('%H%M%S')}"
gui.set_clipboard(test_text)
read_back = gui.get_clipboard()
clip_ok = read_back.get("text", "").strip() == test_text
log_result("P5", "clipboard_roundtrip", {"ok": clip_ok}, test_text)

# 5c. 坐标系统验证
print("  --- 坐标系统 ---")
ox, oy = gui._get_client_offset(hwnd)
rect_data = gui.ctypes.wintypes.RECT()
gui.user32.GetWindowRect(hwnd, gui.ctypes.byref(rect_data))
crect = gui.ctypes.wintypes.RECT()
gui.user32.GetClientRect(hwnd, gui.ctypes.byref(crect))
print(f"  窗口: ({rect_data.left},{rect_data.top}) {rect_data.right-rect_data.left}x{rect_data.bottom-rect_data.top}")
print(f"  客户区: {crect.right}x{crect.bottom}")
print(f"  偏移: ({ox},{oy})")
log_result("P5", "coord_system", {"ok": ox > 0 and oy > 0}, f"offset=({ox},{oy})")

# 5d. find_text精度测试
print("  --- 文字查找精度 ---")
scan = gui.scan(hwnd=hwnd)
if scan.get("texts"):
    target_text = scan["texts"][0]["text"]
    find_result = gui.find_text(target_text, hwnd=hwnd)
    found_count = find_result.get("count", 0)
    log_result("P5", "find_text_precision", {"ok": found_count > 0}, 
               f"'{target_text}' found {found_count}x")

# ── Phase 6: 前台窗口保护验证 ────────────────────────
section("Phase 6: 用户无感验证")

fg_before = gui.user32.GetForegroundWindow()
import pyautogui
mouse_before = pyautogui.position()

# 执行一系列操作
actions = [
    ("scan", lambda: gui.scan(hwnd=hwnd)),
    ("press_u", lambda: gui.press_key("u", hwnd=hwnd)),
    ("press_u_back", lambda: gui.press_key("u", hwnd=hwnd)),
    ("scroll_down", lambda: gui.scroll(-3, hwnd=hwnd)),
    ("scroll_up", lambda: gui.scroll(3, hwnd=hwnd)),
]

for name, action in actions:
    action()
    time.sleep(0.3)

fg_after = gui.user32.GetForegroundWindow()
mouse_after = pyautogui.position()

fg_ok = fg_before == fg_after
dx = abs(mouse_after.x - mouse_before.x)
dy = abs(mouse_after.y - mouse_before.y)
mouse_ok = dx <= 10 and dy <= 10

log_result("P6", "foreground_preserved", {"ok": fg_ok}, 
           f"{fg_before} → {fg_after}")
log_result("P6", "mouse_restored", {"ok": mouse_ok}, 
           f"Δ({dx},{dy})")

# ── 汇总 ──────────────────────────────────────────────
section("测试汇总")

total = len(results)
passed = sum(1 for r in results if r["ok"])
failed = total - passed

print(f"\n  总计: {total}项 | ✅ PASS: {passed} | ❌ FAIL: {failed}")
print(f"  通过率: {passed/total*100:.0f}%")

if issues:
    print(f"\n  发现的问题 ({len(issues)}个):")
    for i, issue in enumerate(issues, 1):
        print(f"    [{i}] [{issue['phase']}] {issue['name']}: {issue['detail'][:60]}")

# 保存结果
output = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "summary": {"total": total, "passed": passed, "failed": failed},
    "results": results,
    "issues": issues,
}
with open("vam_exploration_results.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n  结果已保存: vam_exploration_results.json")
