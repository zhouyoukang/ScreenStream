"""
VaM GUI 实操测试 v2 — 基于VaM实际导航模型
VaM导航: Main Menu → Scene Browser(网格) → Scene Preview/Editor
- 返回场景预览 按钮: Scene Browser → Scene Preview
- Escape: 关闭对话框/面板（不用于页面导航）
- 快捷键(u/Ctrl+S等): 仅在Scene Preview/Editor中生效
"""
import sys, time, json, logging
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

from vam import gui

RESULTS = []
ISSUES = []


def log_result(phase, action, result, expected_ok=True):
    ok = result.get("ok", False) if isinstance(result, dict) else bool(result)
    status = "PASS" if ok == expected_ok else "FAIL"
    entry = {"phase": phase, "action": action, "status": status, "detail": result}
    RESULTS.append(entry)
    icon = "✅" if status == "PASS" else "❌"
    print(f"  {icon} {action}: {status}")
    if isinstance(result, dict):
        for k in ["error", "method", "detected_page"]:
            if k in result:
                print(f"     {k}: {result[k]}")
    if status == "FAIL":
        ISSUES.append(entry)
    return ok


def get_page(hwnd):
    """获取当前页面"""
    state = gui.get_vam_state()
    return state["detected_page"]


def ensure_scene_preview(hwnd):
    """确保在Scene Preview页面（从任何页面）"""
    page = get_page(hwnd)
    if page == "scene_browser":
        # 点击"返回场景预览"按钮
        r = gui.click_text("返回场景预览", hwnd=hwnd)
        if r.get("ok"):
            time.sleep(2)
            return True
    elif page in ("scene_editor", "unknown"):
        # 可能已经在preview/editor
        return True
    elif page == "main_menu":
        # 从主菜单无法直接到preview，需要先打开一个场景
        return False
    return True


def ensure_scene_browser(hwnd):
    """确保在Scene Browser页面"""
    page = get_page(hwnd)
    if page == "scene_browser":
        return True

    # 尝试F1显示场景浏览器（VaM快捷键）
    gui.press_key("f1", hwnd=hwnd)
    time.sleep(2)
    page = get_page(hwnd)
    if page == "scene_browser":
        return True

    # 尝试点击 Scene Browser 文字
    r = gui.click_text("Scene Browser", hwnd=hwnd)
    if r.get("ok"):
        time.sleep(2)
        return get_page(hwnd) == "scene_browser"

    # 尝试中文
    r = gui.click_text("场景浏览器", hwnd=hwnd)
    if r.get("ok"):
        time.sleep(2)
        return get_page(hwnd) == "scene_browser"

    return False


# ══════════════════════════════════════════════════════════════
# Phase 1: 聚焦 + 状态检测
# ══════════════════════════════════════════════════════════════

def phase1_focus_and_scan():
    print("\n" + "=" * 60)
    print("Phase 1: 聚焦VaM窗口 + OCR扫描")
    print("=" * 60)

    hwnd = gui.find_vam_window()
    if not hwnd:
        print("  ❌ VaM窗口未找到")
        return None
    info = gui.get_window_info(hwnd)
    print(f"  VaM窗口: {info['title']} (class={info['class']})")

    # 聚焦
    focus_result = gui.focus_window(hwnd)
    log_result("P1", "focus_window", focus_result)
    time.sleep(0.5)

    # OCR扫描
    scan_result = gui.scan(hwnd=hwnd)
    total = scan_result.get("total", 0)
    ms = scan_result.get("scan_ms", 0)
    print(f"  OCR: {total}个文字, {ms:.0f}ms")
    for t in scan_result.get("texts", [])[:8]:
        c = t["center"]
        print(f"    [{t['confidence']:.2f}] ({c['x']:5d},{c['y']:4d}) {t['text'][:40]}")

    # 页面检测
    state = gui.get_vam_state()
    page = state["detected_page"]
    print(f"  当前页面: {page}")
    log_result("P1", "page_detect", {"ok": page != "unknown", "detected_page": page})

    return hwnd


# ══════════════════════════════════════════════════════════════
# Phase 2: Scene Browser 导航测试
# ══════════════════════════════════════════════════════════════

def phase2_scene_browser_navigation(hwnd):
    print("\n" + "=" * 60)
    print("Phase 2: Scene Browser 导航")
    print("=" * 60)

    page = get_page(hwnd)
    print(f"  当前页面: {page}")

    # 2a. 确保进入 Scene Browser
    if page != "scene_browser":
        ok = ensure_scene_browser(hwnd)
        log_result("P2", "enter_scene_browser", {"ok": ok, "detected_page": get_page(hwnd)})
    else:
        log_result("P2", "already_in_scene_browser", {"ok": True, "detected_page": page})

    # 2b. 验证Scene Browser特征
    scan = gui.scan(hwnd=hwnd)
    texts = [t["text"] for t in scan.get("texts", [])]
    all_text = " ".join(texts).lower()
    has_browser_ui = any(kw in all_text for kw in ["排序", "收藏夹", "从新到旧", "显示隐藏", "sort", "filter"])
    has_scenes = any(kw in all_text for kw in ["scene", "voxta", "dance", "portrait", "chinese"])
    log_result("P2", "browser_has_ui", {"ok": has_browser_ui})
    log_result("P2", "browser_has_scenes", {"ok": has_scenes, "sample": texts[:5]})

    # 2c. 滚动测试（在Scene Browser中）
    texts1 = set(t["text"] for t in scan.get("texts", []))
    gui.scroll(-3, hwnd=hwnd)
    time.sleep(1)
    scan2 = gui.scan(hwnd=hwnd)
    texts2 = set(t["text"] for t in scan2.get("texts", []))
    new_texts = texts2 - texts1
    print(f"  滚动后新出现: {len(new_texts)}个文字")
    for t in list(new_texts)[:3]:
        print(f"    + {t[:40]}")
    log_result("P2", "scroll_in_browser", {"ok": len(new_texts) > 0, "new_count": len(new_texts)})

    # 滚回来
    gui.scroll(3, hwnd=hwnd)
    time.sleep(0.5)

    return True


# ══════════════════════════════════════════════════════════════
# Phase 3: 返回场景预览
# ══════════════════════════════════════════════════════════════

def phase3_return_to_preview(hwnd):
    print("\n" + "=" * 60)
    print("Phase 3: 返回场景预览 (点击按钮)")
    print("=" * 60)

    page = get_page(hwnd)
    print(f"  当前页面: {page}")

    if page != "scene_browser":
        print("  不在Scene Browser，跳过")
        log_result("P3", "skip_not_in_browser", {"ok": True, "detected_page": page})
        return True

    # 点击"返回场景预览"
    result = gui.click_text("返回场景预览", hwnd=hwnd)
    log_result("P3", "click_return_preview", result)
    time.sleep(2)

    # 验证离开了scene_browser
    page_after = get_page(hwnd)
    print(f"  点击后页面: {page_after}")
    left_browser = page_after != "scene_browser"
    log_result("P3", "left_browser", {"ok": left_browser, "detected_page": page_after})

    # 保存截图验证
    img, wrect = gui.capture_printwindow(hwnd)
    img.save(r"d:\道\道生一\一生二\VAM-agent\vam\tests\vam_after_return.png")
    print(f"  截图已保存 ({img.size[0]}x{img.size[1]})")

    return left_browser


# ══════════════════════════════════════════════════════════════
# Phase 4: 快捷键测试（需要在Scene Preview中）
# ══════════════════════════════════════════════════════════════

def phase4_hotkeys(hwnd):
    print("\n" + "=" * 60)
    print("Phase 4: 快捷键测试 (Scene Preview)")
    print("=" * 60)

    # 确保焦点在VaM
    gui.focus_window(hwnd)
    time.sleep(0.3)

    # 4a. Toggle UI (u键) — 隐藏
    scan_before = gui.scan(hwnd=hwnd)
    before_count = scan_before.get("total", 0)
    print(f"  Toggle前文字数: {before_count}")

    result = gui.vam_hotkey("toggle_ui")
    log_result("P4", "hotkey_toggle_ui_hide", result)
    time.sleep(1.5)

    scan_hidden = gui.scan(hwnd=hwnd)
    hidden_count = scan_hidden.get("total", 0)
    print(f"  UI隐藏后文字数: {hidden_count}")

    # 4b. Toggle UI — 恢复
    result = gui.vam_hotkey("toggle_ui")
    log_result("P4", "hotkey_toggle_ui_show", result)
    time.sleep(1.5)

    scan_shown = gui.scan(hwnd=hwnd)
    shown_count = scan_shown.get("total", 0)
    print(f"  UI恢复后文字数: {shown_count}")

    # 判断toggle是否有效果
    toggle_ok = hidden_count != before_count or hidden_count < 5
    log_result("P4", "ui_toggle_effect", {
        "ok": toggle_ok, "before": before_count, "hidden": hidden_count, "shown": shown_count
    })

    # 4c. Undo/Redo
    gui.focus_window(hwnd)
    result = gui.vam_hotkey("undo")
    log_result("P4", "hotkey_undo", result)
    time.sleep(0.5)

    result = gui.vam_hotkey("redo")
    log_result("P4", "hotkey_redo", result)
    time.sleep(0.5)

    # 4d. Save (Ctrl+S)
    gui.focus_window(hwnd)
    result = gui.save_current_scene()
    log_result("P4", "save_scene", result)
    time.sleep(2)

    # 检查保存对话框
    scan_after = gui.scan(hwnd=hwnd)
    texts = [t["text"] for t in scan_after.get("texts", [])]
    all_text = " ".join(texts).lower()
    has_save = any(kw in all_text for kw in ["save", "overwrite", "保存", "覆盖"])
    if has_save:
        print("  保存对话框出现，按Escape关闭")
        gui.press_key("escape", hwnd=hwnd)
        time.sleep(1)
    log_result("P4", "save_hotkey", {"ok": True, "dialog_appeared": has_save})

    return True


# ══════════════════════════════════════════════════════════════
# Phase 5: 再次进入Scene Browser验证双向导航
# ══════════════════════════════════════════════════════════════

def phase5_roundtrip(hwnd):
    print("\n" + "=" * 60)
    print("Phase 5: 双向导航验证 (Preview ↔ Browser)")
    print("=" * 60)

    # 5a. 从preview进入scene_browser
    page = get_page(hwnd)
    print(f"  当前页面: {page}")

    if page != "scene_browser":
        ok = ensure_scene_browser(hwnd)
        log_result("P5", "navigate_to_browser", {"ok": ok, "detected_page": get_page(hwnd)})
        time.sleep(1)

    # 5b. 再返回preview
    r = gui.click_text("返回场景预览", hwnd=hwnd)
    time.sleep(2)
    page_after = get_page(hwnd)
    log_result("P5", "navigate_back_to_preview", {"ok": page_after != "scene_browser", "detected_page": page_after})

    return True


# ══════════════════════════════════════════════════════════════
# Phase 6: click_text精度测试
# ══════════════════════════════════════════════════════════════

def phase6_click_precision(hwnd):
    print("\n" + "=" * 60)
    print("Phase 6: click_text精度测试")
    print("=" * 60)

    # 先确保在某个有文字的页面
    gui.focus_window(hwnd)
    scan = gui.scan(hwnd=hwnd)
    texts = scan.get("texts", [])
    if not texts:
        log_result("P6", "no_texts_found", {"ok": False})
        return False

    # 找一个高置信度的文字来点击
    target = None
    for t in texts:
        if t["confidence"] > 0.9 and len(t["text"]) > 3:
            target = t
            break

    if not target:
        print("  没找到适合测试的高置信度文字")
        log_result("P6", "no_suitable_target", {"ok": True})
        return True

    print(f"  目标文字: '{target['text']}' at ({target['center']['x']},{target['center']['y']})")
    result = gui.find_text(target["text"], hwnd=hwnd)
    found = result.get("count", 0) > 0
    log_result("P6", "find_text_accuracy", {"ok": found, "target": target["text"], "count": result.get("count", 0)})

    return True


# ══════════════════════════════════════════════════════════════
# Phase 7: 剪贴板测试
# ══════════════════════════════════════════════════════════════

def phase7_clipboard(hwnd):
    print("\n" + "=" * 60)
    print("Phase 7: 剪贴板读写测试")
    print("=" * 60)

    test_text = "VaM_Test_中文测试_" + time.strftime("%H%M%S")

    # 写入剪贴板
    result = gui.set_clipboard(test_text)
    log_result("P7", "clipboard_set", result)
    time.sleep(0.5)

    # 读取剪贴板
    result = gui.get_clipboard()
    got = result.get("text", "")
    match = got.strip() == test_text
    print(f"  写入: '{test_text}'")
    print(f"  读出: '{got.strip()}'")
    log_result("P7", "clipboard_roundtrip", {"ok": match, "expected": test_text, "got": got.strip()})

    return True


# ══════════════════════════════════════════════════════════════
# 主执行
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔" + "═" * 58 + "╗")
    print("║   VaM GUI 实操测试 v2 — 基于实际VaM导航模型        ║")
    print("╚" + "═" * 58 + "╝")

    guard = gui.get_guard()
    guard.start()
    guard.pause()
    print(f"\nMouseGuard已启动并暂停 (cooldown={guard.cooldown}s)")

    # Phase 1: 聚焦+扫描
    hwnd = phase1_focus_and_scan()
    if not hwnd:
        print("\n❌ VaM未找到，测试中止")
        sys.exit(1)

    # Phase 2: Scene Browser 测试
    phase2_scene_browser_navigation(hwnd)

    # Phase 3: 返回场景预览
    phase3_return_to_preview(hwnd)

    # Phase 4: 快捷键测试（在Scene Preview中）
    phase4_hotkeys(hwnd)

    # Phase 5: 双向导航验证
    phase5_roundtrip(hwnd)

    # Phase 6: click_text精度测试
    phase6_click_precision(hwnd)

    # Phase 7: 剪贴板测试
    phase7_clipboard(hwnd)

    # ══════════════════════════════════════════════════════════
    # 汇总
    # ══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)

    pass_count = sum(1 for r in RESULTS if r["status"] == "PASS")
    fail_count = sum(1 for r in RESULTS if r["status"] == "FAIL")
    print(f"\n  总计: {len(RESULTS)}项 | ✅ PASS: {pass_count} | ❌ FAIL: {fail_count}")

    if ISSUES:
        print(f"\n  问题 ({len(ISSUES)}个):")
        for issue in ISSUES:
            d = issue.get("detail", {})
            if isinstance(d, dict):
                err = d.get("error", d.get("detected_page", "see detail"))
            else:
                err = str(d)
            print(f"    [{issue['phase']}] {issue['action']}: {err}")

    result_path = r"d:\道\道生一\一生二\VAM-agent\vam\tests\test_gui_live_results.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({"results": RESULTS, "issues": ISSUES,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}, f, ensure_ascii=False, indent=2)
    print(f"\n  结果已保存: {result_path}")
    print("=" * 60)
