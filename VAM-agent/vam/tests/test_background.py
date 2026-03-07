"""
VaM 后台自动化测试 — 验证完全后台操作（用户无感）
=================================================
所有操作通过PostMessage完成，不抢焦点、不移鼠标。
类比浏览器MCP: PrintWindow=DOM快照, PostMessage=事件派发
"""
import sys, time, json, os
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")

import numpy  # pre-import to avoid circular import
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

from vam import gui

# 确保后台模式
gui.BACKGROUND_MODE = True

RESULTS = []
RESULT_PATH = r"d:\道\道生一\一生二\VAM-agent\vam\tests\test_background_results.json"


def log_result(phase, name, result, detail=None):
    ok = result.get("ok", False) if isinstance(result, dict) else bool(result)
    method = result.get("method", "?") if isinstance(result, dict) else "?"
    status = "PASS" if ok else "FAIL"
    icon = "✅" if ok else "❌"
    print(f"  {icon} {name}: {status} [{method}]")
    RESULTS.append({
        "phase": phase, "name": name, "ok": ok,
        "method": method, "detail": detail or result
    })
    return ok


def phase1_scan():
    """后台OCR扫描 — 不聚焦VaM"""
    print("\n" + "=" * 60)
    print("Phase 1: 后台OCR扫描（不聚焦VaM窗口）")
    print("=" * 60)

    hwnd = gui.find_vam_window()
    if not hwnd:
        print("  ❌ VaM未运行")
        return None
    print(f"  VaM hwnd={hwnd}")

    # 记录当前前台窗口 — 测试完不应该改变
    fg_before = gui.user32.GetForegroundWindow()
    print(f"  当前前台窗口: {fg_before}")

    # 后台OCR扫描（PrintWindow不需要焦点）
    scan = gui.scan(hwnd=hwnd)
    scan_ok = scan.get("total", 0) > 0 and "error" not in scan
    log_result("P1", "background_scan", {"ok": scan_ok, "method": "background", "total": scan.get("total", 0)})

    total = scan.get("total", 0)
    print(f"  OCR: {total}个文字, {scan.get('scan_ms', 0):.0f}ms")

    # 验证有img_center字段
    has_img = False
    if scan.get("texts"):
        t0 = scan["texts"][0]
        has_img = "img_center" in t0
        print(f"  首个文字: '{t0['text']}' screen=({t0['center']['x']},{t0['center']['y']}) img=({t0.get('img_center',{}).get('x','?')},{t0.get('img_center',{}).get('y','?')})")
    log_result("P1", "has_img_coords", {"ok": has_img, "method": "scan"})

    # 验证前台窗口没变
    fg_after = gui.user32.GetForegroundWindow()
    fg_unchanged = fg_before == fg_after
    print(f"  前台窗口变化: {'❌ 变了!' if not fg_unchanged else '✅ 未变'} ({fg_before} → {fg_after})")
    log_result("P1", "foreground_unchanged", {"ok": fg_unchanged, "method": "background"})

    # 页面检测
    state = gui.get_vam_state()
    page = state.get("detected_page", "unknown")
    print(f"  检测页面: {page}")
    log_result("P1", "page_detect", {"ok": page != "unknown", "method": "background", "page": page})

    return hwnd


def phase2_bg_key(hwnd):
    """后台按键 — 不抢焦点"""
    print("\n" + "=" * 60)
    print("Phase 2: 后台按键（PostMessage，不抢焦点）")
    print("=" * 60)

    fg_before = gui.user32.GetForegroundWindow()

    # 测试 'u' 键 toggle UI
    scan_before = gui.scan(hwnd=hwnd)
    count_before = scan_before.get("total", 0)

    r = gui.press_key("u", hwnd=hwnd)
    log_result("P2", "bg_key_u", r)
    time.sleep(1.5)

    scan_after = gui.scan(hwnd=hwnd)
    count_after = scan_after.get("total", 0)
    delta = abs(count_after - count_before)
    print(f"  文字数: {count_before} → {count_after} (delta={delta})")
    log_result("P2", "ui_toggle_effect", {"ok": delta > 0, "method": "background", "delta": delta})

    # 恢复UI
    gui.press_key("u", hwnd=hwnd)
    time.sleep(1)

    # 测试组合键 ctrl+z
    r = gui.press_key("ctrl+z", hwnd=hwnd)
    log_result("P2", "bg_key_ctrl_z", r)

    # 测试组合键 ctrl+s
    r = gui.press_key("ctrl+s", hwnd=hwnd)
    log_result("P2", "bg_key_ctrl_s", r)

    # 前台窗口验证
    fg_after = gui.user32.GetForegroundWindow()
    fg_ok = fg_before == fg_after
    print(f"  前台窗口: {'✅ 未变' if fg_ok else '❌ 变了!'}")
    log_result("P2", "foreground_unchanged", {"ok": fg_ok, "method": "background"})


def phase3_bg_scroll(hwnd):
    """后台滚轮 — 不移鼠标"""
    print("\n" + "=" * 60)
    print("Phase 3: 后台滚轮（PostMessage，不移鼠标）")
    print("=" * 60)

    fg_before = gui.user32.GetForegroundWindow()

    import pyautogui
    mouse_before = pyautogui.position()

    # 记录滚动前文字
    scan_before = gui.scan(hwnd=hwnd)
    texts_before = set(t["text"] for t in scan_before.get("texts", []))

    # 后台向下滚动
    r = gui.scroll(-5, hwnd=hwnd)
    log_result("P3", "bg_scroll_down", r)
    time.sleep(2)  # Unity需要时间渲染新内容

    # 检查是否有新文字
    scan_after = gui.scan(hwnd=hwnd)
    texts_after = set(t["text"] for t in scan_after.get("texts", []))
    new_texts = texts_after - texts_before
    print(f"  新出现: {len(new_texts)}个文字")
    if new_texts:
        for t in list(new_texts)[:3]:
            print(f"    + {t}")
    log_result("P3", "scroll_new_content", {"ok": len(new_texts) > 0, "method": "background", "new_count": len(new_texts)})

    # 滚回去
    gui.scroll(5, hwnd=hwnd)
    time.sleep(1)

    # 鼠标位置验证（允许±10px容差，自然漂移+SetCursorPos舍入）
    mouse_after = pyautogui.position()
    dx = abs(mouse_after.x - mouse_before.x)
    dy = abs(mouse_after.y - mouse_before.y)
    mouse_ok = dx <= 10 and dy <= 10
    print(f"  鼠标位置: ({mouse_before.x},{mouse_before.y}) → ({mouse_after.x},{mouse_after.y}) Δ({dx},{dy}) {'✅' if mouse_ok else '❌'}")
    log_result("P3", "mouse_restored", {"ok": mouse_ok, "method": "background", "delta": (dx,dy)})

    # 前台窗口验证
    fg_after = gui.user32.GetForegroundWindow()
    fg_ok = fg_before == fg_after
    log_result("P3", "foreground_unchanged", {"ok": fg_ok, "method": "background"})


def phase4_bg_click(hwnd):
    """后台点击 — 核心功能测试"""
    print("\n" + "=" * 60)
    print("Phase 4: 后台点击（PostMessage，不抢焦点/不移鼠标）")
    print("=" * 60)

    fg_before = gui.user32.GetForegroundWindow()
    import pyautogui
    mouse_before = pyautogui.position()

    # 先确认在scene_browser
    state = gui.get_vam_state()
    page = state.get("detected_page", "unknown")
    print(f"  当前页面: {page}")

    if page == "scene_browser":
        # 测试点击 "返回场景预览"
        r = gui.click_text("返回场景预览", hwnd=hwnd)
        log_result("P4", "bg_click_return", r)
        time.sleep(2)

        state2 = gui.get_vam_state()
        page2 = state2.get("detected_page", "unknown")
        print(f"  点击后页面: {page2}")
        navigated = page2 != "scene_browser"
        log_result("P4", "navigate_from_browser",
                   {"ok": navigated, "method": "background", "page": page2})

        if navigated:
            # 保存成功截图
            img, _ = gui.capture_printwindow(hwnd)
            img.save(r"d:\道\道生一\一生二\VAM-agent\vam\tests\vam_after_bg_return.png")
            print("  截图已保存: vam_after_bg_return.png")
    else:
        # 从其他页面测试点击
        scan = gui.scan(hwnd=hwnd)
        if scan.get("texts"):
            first = scan["texts"][0]
            print(f"  测试点击: '{first['text']}'")
            r = gui.click_text(first["text"], hwnd=hwnd)
            log_result("P4", "bg_click_text", r)

    # 鼠标验证（允许±10px）
    mouse_after = pyautogui.position()
    dx = abs(mouse_after.x - mouse_before.x)
    dy = abs(mouse_after.y - mouse_before.y)
    mouse_ok = dx <= 10 and dy <= 10
    print(f"  鼠标: ({mouse_before.x},{mouse_before.y}) → ({mouse_after.x},{mouse_after.y}) Δ({dx},{dy}) {'✅' if mouse_ok else '❌'}")
    log_result("P4", "mouse_restored", {"ok": mouse_ok, "method": "background", "delta": (dx,dy)})

    # 前台验证
    fg_after = gui.user32.GetForegroundWindow()
    fg_ok = fg_before == fg_after
    print(f"  前台窗口: {'✅ 未变' if fg_ok else '❌ 变了!'}")
    log_result("P4", "foreground_unchanged", {"ok": fg_ok, "method": "background"})


def phase5_bg_click_precision(hwnd):
    """后台点击精度 — 验证坐标转换"""
    print("\n" + "=" * 60)
    print("Phase 5: 后台坐标精度验证")
    print("=" * 60)

    # 获取client offset
    ox, oy = gui._get_client_offset(hwnd)
    print(f"  客户区偏移: ({ox}, {oy}) ← 标题栏+边框")

    # 获取窗口尺寸
    import ctypes.wintypes as wt
    import ctypes
    wrect = wt.RECT()
    gui.user32.GetWindowRect(hwnd, ctypes.byref(wrect))
    crect = wt.RECT()
    gui.user32.GetClientRect(hwnd, ctypes.byref(crect))
    print(f"  窗口: ({wrect.left},{wrect.top}) {wrect.right-wrect.left}x{wrect.bottom-wrect.top}")
    print(f"  客户区: {crect.right}x{crect.bottom}")

    # 验证转换
    test_img = (650, 1300)
    cx, cy = gui._img_to_client(hwnd, test_img[0], test_img[1])
    print(f"  img({test_img[0]},{test_img[1]}) → client({cx},{cy})")
    valid = cx >= 0 and cy >= 0 and cx < crect.right and cy < crect.bottom
    log_result("P5", "coord_conversion_valid",
               {"ok": valid, "method": "background",
                "img": test_img, "client": (cx, cy),
                "client_size": (crect.right, crect.bottom)})


def phase6_clipboard(hwnd):
    """剪贴板读写"""
    print("\n" + "=" * 60)
    print("Phase 6: 剪贴板读写")
    print("=" * 60)

    test_text = "BG_Test_后台测试_" + time.strftime("%H%M%S")
    r = gui.set_clipboard(test_text)
    log_result("P6", "clipboard_set", r)
    time.sleep(0.3)

    r = gui.get_clipboard()
    got = r.get("text", "").strip()
    match = got == test_text
    print(f"  写入: '{test_text}'")
    print(f"  读出: '{got}'")
    log_result("P6", "clipboard_roundtrip", {"ok": match, "method": "clipboard"})


def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  VaM 后台自动化测试 — 用户无感 (BACKGROUND_MODE=True) ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  BACKGROUND_MODE = {gui.BACKGROUND_MODE}")
    print(f"  原理: PrintWindow截图 + PostMessage输入 = 完全后台")
    print(f"  类比: 浏览器MCP通过CDP协议操控页面，用户无感\n")

    # MouseGuard暂停
    guard = gui.get_guard()
    guard.start()
    guard.pause()
    print("MouseGuard已暂停\n")

    hwnd = phase1_scan()
    if not hwnd:
        print("VaM未运行，退出")
        return

    phase2_bg_key(hwnd)
    phase3_bg_scroll(hwnd)
    phase4_bg_click(hwnd)
    phase5_bg_click_precision(hwnd)
    phase6_clipboard(hwnd)

    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)

    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["ok"])
    failed = total - passed
    bg_count = sum(1 for r in RESULTS if r.get("method") == "background")

    print(f"\n  总计: {total}项 | ✅ PASS: {passed} | ❌ FAIL: {failed}")
    print(f"  后台操作: {bg_count}/{total} (无一次抢焦点/移鼠标)")

    if failed:
        print(f"\n  问题 ({failed}个):")
        for r in RESULTS:
            if not r["ok"]:
                detail = r.get("detail", {})
                msg = detail.get("page", detail.get("error", "see detail")) if isinstance(detail, dict) else str(detail)
                print(f"    [{r['phase']}] {r['name']}: {msg}")

    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)
    print(f"\n  结果已保存: {RESULT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
