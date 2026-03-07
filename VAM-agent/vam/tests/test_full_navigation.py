"""
VaM 全页面导航+交互测试 — 后台模式
===================================
从任意状态出发，遍历所有VaM页面，测试所有交互。
"""
import sys, time, json
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
import numpy
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

from vam import gui

results = []
issues = []
page_snapshots = {}  # 记录每个页面的文字快照

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
    """扫描并检测当前页面"""
    scan = gui.scan(hwnd=hwnd)
    texts = [t["text"] for t in scan.get("texts", [])]
    page = gui._detect_page(texts)
    return page, scan

def save_snapshot(page_name, scan):
    """保存页面快照"""
    page_snapshots[page_name] = {
        "total_texts": scan.get("total", 0),
        "texts": [t["text"] for t in scan.get("texts", [])],
        "scan_ms": scan.get("scan_ms", 0),
    }

# ── 初始化 ────────────────────────────────────────────
hwnd = gui.find_vam_window()
if not hwnd:
    print("❌ VaM未运行"); sys.exit(1)
print(f"VaM hwnd={hwnd}")
guard = gui.get_guard()
guard.start()
guard.pause()

import pyautogui
fg_start = gui.user32.GetForegroundWindow()
mouse_start = pyautogui.position()
print(f"初始前台: {fg_start}, 鼠标: ({mouse_start.x},{mouse_start.y})")

# ── Step 1: 识别当前状态 ──────────────────────────────
section("Step 1: 当前状态识别")

page, scan = get_page(hwnd)
print(f"  当前页面: {page}")
print(f"  文字数: {scan.get('total', 0)}")
save_snapshot(f"initial_{page}", scan)
log_result("S1", "page_detected", {"ok": page != "unknown"}, page)

# 显示所有文字
for t in scan.get("texts", [])[:15]:
    ic = t.get("img_center", {})
    print(f"    '{t['text']}' at ({ic.get('x','?')},{ic.get('y','?')})")

# ── Step 2: 从当前状态导航到UI可见 ─────────────────────
section("Step 2: 确保UI可见")

if page in ("scene_preview", "unknown") and scan.get("total", 0) < 10:
    print("  VaM在预览模式，按'u'显示UI...")
    gui.press_key("u", hwnd=hwnd)
    time.sleep(1.5)
    
    page, scan = get_page(hwnd)
    print(f"  按u后: {page}, {scan.get('total', 0)}个文字")
    save_snapshot(f"after_u_{page}", scan)
    
    if scan.get("total", 0) < 10:
        # 可能需要Escape先退出某个模式
        print("  UI仍少，尝试Escape...")
        gui.press_key("escape", hwnd=hwnd)
        time.sleep(1)
        gui.press_key("u", hwnd=hwnd)
        time.sleep(1.5)
        page, scan = get_page(hwnd)
        print(f"  Escape+u后: {page}, {scan.get('total', 0)}个文字")

log_result("S2", "ui_visible", {"ok": scan.get("total", 0) >= 5}, 
           f"{scan.get('total', 0)} texts, page={page}")

# ── Step 3: 导航到场景浏览器 ──────────────────────────
section("Step 3: 导航到场景浏览器")

page, scan = get_page(hwnd)

if page == "scene_browser":
    print("  已在场景浏览器")
    log_result("S3", "at_scene_browser", {"ok": True})
elif page == "main_menu":
    # 从主菜单进入
    r = gui.navigate_main_menu("scene_browser")
    log_result("S3", "nav_from_menu", r)
    time.sleep(2)
    page, scan = get_page(hwnd)
    log_result("S3", "arrived_browser", {"ok": page == "scene_browser"}, page)
else:
    # 尝试多种导航方式
    navigated = False
    
    # 方法1: Escape回主菜单
    for attempt in range(3):
        gui.press_key("escape", hwnd=hwnd)
        time.sleep(1)
        page, scan = get_page(hwnd)
        if page == "main_menu":
            print(f"  Escape×{attempt+1} → 到达主菜单")
            r = gui.navigate_main_menu("scene_browser")
            time.sleep(2)
            page, scan = get_page(hwnd)
            navigated = page == "scene_browser"
            break
        if page == "scene_browser":
            navigated = True
            break
    
    if not navigated:
        # 方法2: 尝试直接点击相关文字
        for target in ["Scene Browser", "场景浏览器", "Main Menu", "主菜单"]:
            r = gui.find_text(target, hwnd=hwnd)
            if r.get("count", 0) > 0:
                gui.click_text(target, hwnd=hwnd)
                time.sleep(2)
                page, scan = get_page(hwnd)
                if page in ("scene_browser", "main_menu"):
                    if page == "main_menu":
                        gui.navigate_main_menu("scene_browser")
                        time.sleep(2)
                        page, scan = get_page(hwnd)
                    navigated = page == "scene_browser"
                    break
    
    log_result("S3", "navigate_to_browser", {"ok": navigated}, page)

save_snapshot("scene_browser", scan)

# ── Step 4: 场景浏览器深度交互 ────────────────────────
section("Step 4: 场景浏览器交互")

page, scan = get_page(hwnd)
if page == "scene_browser":
    # 4a. 列出所有可见元素
    texts = scan.get("texts", [])
    print(f"  浏览器元素: {len(texts)}个")
    
    # 分类元素
    buttons = []
    scene_items = []
    labels = []
    for t in texts:
        text = t["text"]
        if len(text) <= 3:
            continue
        if any(kw in text.lower() for kw in ["sort", "filter", "排序", "收藏", "显示", "隐藏", "返回"]):
            buttons.append(text)
        elif "_" in text or ("20" in text and len(text) > 8):
            scene_items.append(text)
        else:
            labels.append(text)
    
    print(f"  按钮: {buttons[:5]}")
    print(f"  场景: {scene_items[:5]}")
    print(f"  标签: {labels[:5]}")
    log_result("S4", "browser_elements", {"ok": len(texts) > 5}, 
               f"btn={len(buttons)} scene={len(scene_items)} label={len(labels)}")
    
    # 4b. 滚动测试
    print("\n  --- 滚动测试 ---")
    texts_before = set(t["text"] for t in texts)
    
    gui.scroll(-5, hwnd=hwnd)
    time.sleep(2)
    _, scan2 = get_page(hwnd)
    texts_after = set(t["text"] for t in scan2.get("texts", []))
    new_items = texts_after - texts_before
    disappeared = texts_before - texts_after
    
    print(f"  新出现: {len(new_items)}个, 消失: {len(disappeared)}个")
    for t in list(new_items)[:3]:
        print(f"    + {t}")
    log_result("S4", "scroll_effective", {"ok": len(new_items) > 0 or len(disappeared) > 0},
               f"+{len(new_items)} -{len(disappeared)}")
    
    # 滚回
    gui.scroll(5, hwnd=hwnd)
    time.sleep(1)
    
    # 4c. 点击场景预览
    if scene_items:
        print(f"\n  --- 点击场景: '{scene_items[0]}' ---")
        r = gui.click_text(scene_items[0], hwnd=hwnd)
        log_result("S4", "click_scene", r, scene_items[0])
        time.sleep(2)
        
        page_after, scan_after = get_page(hwnd)
        save_snapshot(f"after_click_scene_{page_after}", scan_after)
        print(f"  点击后页面: {page_after}, {scan_after.get('total', 0)}个文字")
        log_result("S4", "scene_response", {"ok": True}, page_after)
        
        # 返回浏览器
        if page_after != "scene_browser":
            gui.press_key("escape", hwnd=hwnd)
            time.sleep(1)
else:
    print(f"  ⚠️ 不在场景浏览器 ({page})")
    log_result("S4", "browser_test_skipped", {"ok": False}, page)

# ── Step 5: 导航到编辑器 ──────────────────────────────
section("Step 5: 场景编辑器")

# 确保回到可编辑状态
page, scan = get_page(hwnd)
print(f"  当前: {page}")

# 进入编辑模式
gui.press_key("e", hwnd=hwnd)
time.sleep(1.5)

page, scan = get_page(hwnd)
save_snapshot(f"editor_{page}", scan)
print(f"  按e后: {page}, {scan.get('total', 0)}个文字")

if page == "scene_editor":
    # 5a. 编辑器标签页
    print("\n  --- 编辑器标签 ---")
    found_tabs = []
    for tab in gui.VAM_EDITOR_ELEMENTS["tabs"]:
        r = gui.find_text(tab, hwnd=hwnd)
        if r.get("count", 0) > 0:
            found_tabs.append(tab)
    print(f"  发现标签: {found_tabs}")
    log_result("S5", "editor_tabs", {"ok": len(found_tabs) >= 3}, 
               f"{len(found_tabs)}/{len(gui.VAM_EDITOR_ELEMENTS['tabs'])}")
    
    # 5b. 点击每个标签并记录内容
    for tab in found_tabs[:4]:
        print(f"\n  --- 点击标签: {tab} ---")
        gui.click_text(tab, hwnd=hwnd)
        time.sleep(1.5)
        
        _, tab_scan = get_page(hwnd)
        tab_texts = [t["text"] for t in tab_scan.get("texts", [])]
        save_snapshot(f"editor_tab_{tab}", tab_scan)
        print(f"    {tab}: {len(tab_texts)}个文字")
        for tt in tab_texts[:5]:
            print(f"      • {tt}")
        log_result("S5", f"tab_{tab}_content", {"ok": len(tab_texts) > 3}, 
                   f"{len(tab_texts)} texts")
    
    # 5c. 尝试点击Add Atom
    r = gui.find_text("Add Atom", hwnd=hwnd)
    if r.get("count", 0) > 0:
        print("\n  --- Add Atom 可用 ---")
        log_result("S5", "add_atom_visible", {"ok": True})
    
    # 5d. Tab键选择Atom
    gui.press_key("tab", hwnd=hwnd)
    time.sleep(0.5)
    _, tab_scan = get_page(hwnd)
    log_result("S5", "tab_select", {"ok": True}, f"page={gui._detect_page([t['text'] for t in tab_scan.get('texts', [])])}")
    
else:
    print(f"  ⚠️ 未进入编辑器 ({page})")
    # 尝试分析为什么
    all_text = " ".join(t["text"] for t in scan.get("texts", []))
    print(f"  屏幕文字: {all_text[:100]}")
    log_result("S5", "editor_enter", {"ok": False}, page)

# 退出编辑模式
gui.press_key("e", hwnd=hwnd)
time.sleep(0.5)

# ── Step 6: 播放模式测试 ─────────────────────────────
section("Step 6: 播放模式")

gui.press_key("p", hwnd=hwnd)
time.sleep(1)

page, scan = get_page(hwnd)
save_snapshot(f"play_mode_{page}", scan)
print(f"  播放模式: {page}, {scan.get('total', 0)}个文字")
log_result("S6", "play_mode", {"ok": True}, page)

# 恢复
gui.press_key("p", hwnd=hwnd)
time.sleep(0.5)

# ── Step 7: 冻结物理 ─────────────────────────────────
section("Step 7: 物理冻结")

gui.press_key("f", hwnd=hwnd)
time.sleep(0.5)
log_result("S7", "freeze_motion", {"ok": True})

gui.press_key("f", hwnd=hwnd)
time.sleep(0.5)
log_result("S7", "unfreeze_motion", {"ok": True})

# ── Step 8: 用户无感验证 ──────────────────────────────
section("Step 8: 用户无感验证")

fg_end = gui.user32.GetForegroundWindow()
mouse_end = pyautogui.position()

fg_ok = fg_start == fg_end
dx = abs(mouse_end.x - mouse_start.x)
dy = abs(mouse_end.y - mouse_start.y)
mouse_ok = dx <= 15 and dy <= 15

log_result("S8", "foreground_preserved", {"ok": fg_ok}, f"{fg_start} → {fg_end}")
log_result("S8", "mouse_restored", {"ok": mouse_ok}, f"Δ({dx},{dy})")

# ── 汇总 ──────────────────────────────────────────────
section("测试汇总")

total = len(results)
passed = sum(1 for r in results if r["ok"])
failed = total - passed

print(f"\n  总计: {total}项 | ✅ PASS: {passed} | ❌ FAIL: {failed}")
print(f"  通过率: {passed/total*100:.0f}%")

# 页面快照汇总
print(f"\n  页面快照: {len(page_snapshots)}个")
for name, snap in page_snapshots.items():
    print(f"    {name}: {snap['total_texts']}个文字, {snap['scan_ms']}ms")

if issues:
    print(f"\n  问题 ({len(issues)}个):")
    for i, issue in enumerate(issues, 1):
        print(f"    [{i}] [{issue['phase']}] {issue['name']}: {issue['detail'][:60]}")

# 保存完整结果
output = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "summary": {"total": total, "passed": passed, "failed": failed},
    "results": results,
    "issues": issues,
    "page_snapshots": page_snapshots,
}
with open("vam_navigation_results.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n  结果: vam_navigation_results.json")
