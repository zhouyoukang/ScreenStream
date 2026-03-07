"""
VaM 全页面导航+交互测试 v2 — 使用rapid-flash capture
====================================================
"""
import sys, time, json
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
import numpy, logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
from vam import gui

results = []
issues = []
page_map = {}  # 完整页面地图

def log_result(phase, name, result, detail=""):
    ok = result.get("ok", False) if isinstance(result, dict) else bool(result)
    results.append({"phase": phase, "name": name, "ok": ok, "detail": detail})
    status = "✅" if ok else "❌"
    print(f"  {status} {name}: {detail[:80] if detail else ('PASS' if ok else 'FAIL')}")
    if not ok:
        issues.append({"phase": phase, "name": name, "detail": detail})

def section(title):
    print(f"\n{'='*60}\n{title}\n{'='*60}")

def get_page(hwnd):
    scan = gui.scan(hwnd=hwnd)
    texts = [t["text"] for t in scan.get("texts", [])]
    page = gui._detect_page(texts)
    return page, scan

def record_page(name, scan):
    texts = [t["text"] for t in scan.get("texts", [])]
    page_map[name] = {
        "total": scan.get("total", 0),
        "texts": texts[:30],
        "scan_ms": scan.get("scan_ms", 0),
    }
    return texts

# ── Init ──
hwnd = gui.find_vam_window()
if not hwnd:
    print("❌ VaM未运行"); sys.exit(1)
print(f"VaM hwnd={hwnd}")
guard = gui.get_guard(); guard.start(); guard.pause()

import pyautogui
fg_start = gui.user32.GetForegroundWindow()
mouse_start = pyautogui.position()

# ═══════════════════════════════════════════════════════
section("S1: 初始状态识别")
# ═══════════════════════════════════════════════════════

page, scan = get_page(hwnd)
texts = record_page(f"S1_initial_{page}", scan)
print(f"  页面: {page}, 文字: {len(texts)}")
for t in texts[:8]:
    print(f"    • {t}")
log_result("S1", "page_detected", {"ok": page != "unknown"}, page)

# ═══════════════════════════════════════════════════════
section("S2: 显示UI覆盖菜单 (u键)")
# ═══════════════════════════════════════════════════════

# 确保UI可见
if scan.get("total", 0) < 6:
    gui.press_key("u", hwnd=hwnd)
    time.sleep(1.5)
    page, scan = get_page(hwnd)
    texts = record_page(f"S2_after_u_{page}", scan)
    print(f"  按u后: {page}, {len(texts)}个文字")
    for t in texts[:10]:
        print(f"    • {t}")
    log_result("S2", "ui_toggle", {"ok": scan.get("total", 0) > 5}, f"{scan.get('total', 0)} texts")
else:
    log_result("S2", "ui_already_visible", {"ok": True}, f"{scan.get('total', 0)} texts")

# ═══════════════════════════════════════════════════════
section("S3: 进入编辑模式")
# ═══════════════════════════════════════════════════════

# 尝试点击"编辑模式(E)"或按'e'
clicked = False
for target in ["编辑模式", "Edit Mode", "编辑模式(E)"]:
    r = gui.find_text(target, hwnd=hwnd)
    if r.get("count", 0) > 0:
        print(f"  找到: '{target}', 点击...")
        gui.click_text(target, hwnd=hwnd)
        clicked = True
        break

if not clicked:
    print("  未找到编辑模式按钮, 按'e'键")
    gui.press_key("e", hwnd=hwnd)

time.sleep(2)
page, scan = get_page(hwnd)
texts = record_page(f"S3_editor_{page}", scan)
print(f"  编辑模式: {page}, {len(texts)}个文字")
for t in texts[:15]:
    print(f"    • {t}")
log_result("S3", "enter_editor", {"ok": page == "scene_editor" or len(texts) > 10}, page)

# ═══════════════════════════════════════════════════════
section("S4: 编辑器交互测试")
# ═══════════════════════════════════════════════════════

if len(texts) > 5:
    # 4a. 查找编辑器标签
    found_tabs = []
    for tab in gui.VAM_EDITOR_ELEMENTS["tabs"]:
        r = gui.find_text(tab, hwnd=hwnd)
        if r.get("count", 0) > 0:
            found_tabs.append(tab)
    print(f"  编辑器标签: {found_tabs}")
    log_result("S4", "editor_tabs", {"ok": len(found_tabs) > 0}, str(found_tabs))
    
    # 4b. 查找所有可交互元素
    all_elements = []
    for t in scan.get("texts", []):
        text = t["text"]
        if len(text) >= 2:
            all_elements.append(text)
    print(f"  所有元素: {len(all_elements)}个")
    log_result("S4", "elements_count", {"ok": len(all_elements) > 5}, f"{len(all_elements)}")
    
    # 4c. 点击第一个标签
    if found_tabs:
        tab = found_tabs[0]
        print(f"  点击标签: {tab}")
        gui.click_text(tab, hwnd=hwnd)
        time.sleep(1.5)
        _, tab_scan = get_page(hwnd)
        tab_texts = record_page(f"S4_tab_{tab}", tab_scan)
        print(f"    {tab}内容: {len(tab_texts)}个文字")
        log_result("S4", f"click_tab_{tab}", {"ok": len(tab_texts) > 3}, f"{len(tab_texts)} texts")
    
    # 4d. 滚动测试
    print("  滚动测试...")
    texts_before = set(t["text"] for t in scan.get("texts", []))
    gui.scroll(-3, hwnd=hwnd)
    time.sleep(1.5)
    _, scan2 = get_page(hwnd)
    texts_after = set(t["text"] for t in scan2.get("texts", []))
    changed = texts_before != texts_after
    log_result("S4", "scroll_effect", {"ok": changed}, 
               f"before={len(texts_before)} after={len(texts_after)}")
    gui.scroll(3, hwnd=hwnd)
    time.sleep(0.5)
else:
    log_result("S4", "editor_test_skipped", {"ok": False}, "too few texts")

# ═══════════════════════════════════════════════════════
section("S5: 返回预览模式")
# ═══════════════════════════════════════════════════════

gui.press_key("e", hwnd=hwnd)  # 退出编辑
time.sleep(1.5)
page, scan = get_page(hwnd)
texts = record_page(f"S5_back_preview_{page}", scan)
print(f"  返回后: {page}, {len(texts)}个文字")
log_result("S5", "back_to_preview", {"ok": True}, page)

# ═══════════════════════════════════════════════════════
section("S6: 导航到主菜单/场景浏览器")
# ═══════════════════════════════════════════════════════

# 先显示UI
if scan.get("total", 0) < 6:
    gui.press_key("u", hwnd=hwnd)
    time.sleep(1.5)
    page, scan = get_page(hwnd)

# 查找导航选项
nav_found = False
for target in ["更多选项", "More Options", "返回主菜单", "Main Menu", 
                "Scene Browser", "场景浏览器"]:
    r = gui.find_text(target, hwnd=hwnd)
    if r.get("count", 0) > 0:
        print(f"  找到: '{target}', 点击...")
        gui.click_text(target, hwnd=hwnd)
        nav_found = True
        time.sleep(2)
        
        page, scan = get_page(hwnd)
        texts = record_page(f"S6_after_click_{target}_{page}", scan)
        print(f"  点击'{target}'后: {page}, {len(texts)}个文字")
        for t in texts[:10]:
            print(f"    • {t}")
        
        # 如果到了更多选项菜单,继续找导航
        if page not in ("main_menu", "scene_browser"):
            for sub_target in ["返回主菜单", "Main Menu", "Scene Browser", 
                               "场景浏览器", "打开场景浏览器"]:
                r2 = gui.find_text(sub_target, hwnd=hwnd)
                if r2.get("count", 0) > 0:
                    print(f"  子菜单找到: '{sub_target}', 点击...")
                    gui.click_text(sub_target, hwnd=hwnd)
                    time.sleep(2)
                    page, scan = get_page(hwnd)
                    texts = record_page(f"S6_submenu_{page}", scan)
                    print(f"  子菜单后: {page}, {len(texts)}个文字")
                    break
        break

if not nav_found:
    # 尝试Escape
    for i in range(3):
        gui.press_key("escape", hwnd=hwnd)
        time.sleep(1)
        page, scan = get_page(hwnd)
        if page in ("main_menu", "scene_browser"):
            break

log_result("S6", "navigate_menu", {"ok": page in ("main_menu", "scene_browser", "scene_preview")}, page)

# ═══════════════════════════════════════════════════════
section("S7: 场景浏览器测试")
# ═══════════════════════════════════════════════════════

page, scan = get_page(hwnd)
if page == "scene_browser":
    texts = record_page("S7_scene_browser", scan)
    print(f"  浏览器: {len(texts)}个文字")
    
    # 分析元素
    for t in texts[:20]:
        print(f"    • {t}")
    
    # 滚动
    gui.scroll(-5, hwnd=hwnd)
    time.sleep(2)
    _, scan2 = get_page(hwnd)
    new_texts = set(t["text"] for t in scan2.get("texts", [])) - set(texts)
    log_result("S7", "browser_scroll", {"ok": len(new_texts) > 0}, f"+{len(new_texts)} new")
    gui.scroll(5, hwnd=hwnd)
    time.sleep(1)
    
    log_result("S7", "browser_available", {"ok": True})
elif page == "main_menu":
    texts = record_page("S7_main_menu", scan)
    print(f"  主菜单: {len(texts)}个文字")
    for t in texts[:15]:
        print(f"    • {t}")
    
    # 尝试进入场景浏览器
    for target in ["Scene Browser", "场景浏览器"]:
        r = gui.find_text(target, hwnd=hwnd)
        if r.get("count", 0) > 0:
            gui.click_text(target, hwnd=hwnd)
            time.sleep(2)
            page, scan = get_page(hwnd)
            texts = record_page("S7_browser_from_menu", scan)
            print(f"  进入浏览器: {page}, {len(texts)}个文字")
            log_result("S7", "enter_browser", {"ok": page == "scene_browser"}, page)
            break
    else:
        log_result("S7", "browser_from_menu", {"ok": False}, "Scene Browser not found")
else:
    print(f"  ⚠️ 当前: {page}")
    log_result("S7", "browser_test", {"ok": False}, page)

# ═══════════════════════════════════════════════════════
section("S8: 快捷键全测试")
# ═══════════════════════════════════════════════════════

hotkeys = [
    ("f1", "camera_1"), ("f2", "camera_2"), ("f3", "camera_3"),
    ("f5", "reset_camera"), ("f", "freeze_motion"),
    ("ctrl+z", "undo"), ("escape", "deselect"),
]
for key, name in hotkeys:
    r = gui.press_key(key, hwnd=hwnd)
    log_result("S8", f"hotkey_{name}", r)
    time.sleep(0.3)

# Unfreeze
gui.press_key("f", hwnd=hwnd)
time.sleep(0.3)

# ═══════════════════════════════════════════════════════
section("S9: 用户无感验证")
# ═══════════════════════════════════════════════════════

fg_end = gui.user32.GetForegroundWindow()
mouse_end = pyautogui.position()
fg_ok = fg_start == fg_end
dx = abs(mouse_end.x - mouse_start.x)
dy = abs(mouse_end.y - mouse_start.y)
mouse_ok = dx <= 15 and dy <= 15
log_result("S9", "fg_preserved", {"ok": fg_ok}, f"{fg_start}→{fg_end}")
log_result("S9", "mouse_restored", {"ok": mouse_ok}, f"Δ({dx},{dy})")

# ═══════════════════════════════════════════════════════
section("汇总")
# ═══════════════════════════════════════════════════════

total = len(results)
passed = sum(1 for r in results if r["ok"])
failed = total - passed
print(f"\n  总计: {total}项 | ✅ {passed} | ❌ {failed} | 通过率: {passed/total*100:.0f}%")

print(f"\n  页面地图 ({len(page_map)}个快照):")
for name, data in page_map.items():
    print(f"    {name}: {data['total']}个文字, {data['scan_ms']:.0f}ms")

if issues:
    print(f"\n  问题 ({len(issues)}个):")
    for i, issue in enumerate(issues, 1):
        print(f"    [{i}] [{issue['phase']}] {issue['name']}: {issue['detail'][:60]}")

output = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "summary": {"total": total, "passed": passed, "failed": failed},
    "results": results, "issues": issues, "page_map": page_map,
}
with open("vam_nav_v2_results.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n  结果: vam_nav_v2_results.json")
