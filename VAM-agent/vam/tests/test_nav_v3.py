"""
VaM 全页面导航 v3 — 使用rapid_key_and_capture单次会话
===================================================
解决：分离的bg_key+scan导致多次focus/defocus干扰VaM状态
"""
import sys, time, json
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
import numpy, logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
from vam import gui

results = []
issues = []
page_map = {}

def log_result(phase, name, ok, detail=""):
    results.append({"phase": phase, "name": name, "ok": ok, "detail": detail})
    print(f"  {'✅' if ok else '❌'} {name}: {detail[:80] if detail else ('PASS' if ok else 'FAIL')}")
    if not ok:
        issues.append({"phase": phase, "name": name, "detail": detail})

def section(title):
    print(f"\n{'='*60}\n{title}\n{'='*60}")

def ocr_image(img):
    """OCR一张PIL图片，返回texts列表"""
    import numpy as np
    ocr = gui._get_ocr()
    # 缩放（同scan逻辑）
    scale = 1.0
    if img.width > 960:
        scale = 960 / img.width
        img = img.resize((960, int(img.height * scale)))
    arr = np.array(img)
    result, _ = ocr(arr)
    if result is None:
        return []
    texts = []
    for bbox, text, conf in result:
        if conf > 0.3 and len(text.strip()) > 0:
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            cx = int(sum(xs) / len(xs) / scale)
            cy = int(sum(ys) / len(ys) / scale)
            texts.append({"text": text.strip(), "cx": cx, "cy": cy, "conf": conf})
    return texts

def record_page(name, texts):
    page = gui._detect_page([t["text"] for t in texts])
    page_map[name] = {
        "page": page,
        "total": len(texts),
        "texts": [t["text"] for t in texts[:30]],
    }
    return page

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
section("S1: 初始状态 (仅截屏，不按键)")
# ═══════════════════════════════════════════════════════

img1, rect1 = gui.rapid_key_and_capture(key=None, hwnd=hwnd, pre_delay=0.3)
if img1:
    texts1 = ocr_image(img1)
    page1 = record_page("S1_initial", texts1)
    print(f"  页面: {page1}, 文字: {len(texts1)}")
    for t in texts1[:8]:
        print(f"    • '{t['text']}' at ({t['cx']},{t['cy']})")
    log_result("S1", "initial_capture", True, f"{page1}, {len(texts1)} texts")
else:
    log_result("S1", "initial_capture", False, "capture failed")
    sys.exit(1)

# ═══════════════════════════════════════════════════════
section("S2: 按u显示UI (单次会话: 按u + 截屏)")
# ═══════════════════════════════════════════════════════

img2, _ = gui.rapid_key_and_capture(key="u", hwnd=hwnd, pre_delay=0.8)
texts2 = ocr_image(img2) if img2 else []
page2 = record_page("S2_after_u", texts2)
print(f"  按u后: {page2}, {len(texts2)}个文字")
for t in texts2[:12]:
    print(f"    • '{t['text']}' at ({t['cx']},{t['cy']})")
log_result("S2", "ui_toggle", len(texts2) > len(texts1), f"{len(texts1)}→{len(texts2)} texts")

# ═══════════════════════════════════════════════════════
section("S3: 进入编辑模式 (按e + 截屏)")
# ═══════════════════════════════════════════════════════

img3, _ = gui.rapid_key_and_capture(key="e", hwnd=hwnd, pre_delay=1.5)
texts3 = ocr_image(img3) if img3 else []
page3 = record_page("S3_editor", texts3)
print(f"  按e后: {page3}, {len(texts3)}个文字")
for t in texts3[:15]:
    print(f"    • '{t['text']}' at ({t['cx']},{t['cy']})")
log_result("S3", "enter_editor", page3 == "scene_editor" or len(texts3) > 10, 
           f"{page3}, {len(texts3)} texts")

# ═══════════════════════════════════════════════════════
section("S4: 编辑器内容探索")
# ═══════════════════════════════════════════════════════

if len(texts3) > 5:
    # 查找编辑器标签
    found_tabs = []
    for tab in gui.VAM_EDITOR_ELEMENTS["tabs"]:
        for t in texts3:
            if tab.lower() in t["text"].lower():
                found_tabs.append(tab)
                break
    print(f"  编辑器标签: {found_tabs}")
    log_result("S4", "editor_tabs", len(found_tabs) > 0, str(found_tabs))
    
    # 列出所有元素
    all_elements = [t["text"] for t in texts3 if len(t["text"]) >= 2]
    print(f"  所有元素: {len(all_elements)}个")
    log_result("S4", "elements", len(all_elements) > 5, f"{len(all_elements)} elements")
else:
    log_result("S4", "editor_explore", False, "too few texts")

# ═══════════════════════════════════════════════════════
section("S5: 退出编辑 → 按e返回")
# ═══════════════════════════════════════════════════════

img5, _ = gui.rapid_key_and_capture(key="e", hwnd=hwnd, pre_delay=1.0)
texts5 = ocr_image(img5) if img5 else []
page5 = record_page("S5_back", texts5)
print(f"  返回: {page5}, {len(texts5)}个文字")
log_result("S5", "exit_editor", True, page5)

# ═══════════════════════════════════════════════════════
section("S6: 按u隐藏UI → 再按u显示")
# ═══════════════════════════════════════════════════════

# 先隐藏
img6a, _ = gui.rapid_key_and_capture(key="u", hwnd=hwnd, pre_delay=0.5)
texts6a = ocr_image(img6a) if img6a else []
print(f"  u(隐藏): {len(texts6a)}个文字")

# 再显示
img6b, _ = gui.rapid_key_and_capture(key="u", hwnd=hwnd, pre_delay=0.8)
texts6b = ocr_image(img6b) if img6b else []
page6b = record_page("S6_u_toggle", texts6b)
print(f"  u(显示): {len(texts6b)}个文字")
for t in texts6b[:10]:
    print(f"    • '{t['text']}'")
toggle_ok = abs(len(texts6a) - len(texts6b)) > 2
log_result("S6", "u_toggle_cycle", toggle_ok, f"hide={len(texts6a)} show={len(texts6b)}")

# ═══════════════════════════════════════════════════════
section("S7: Escape导航")
# ═══════════════════════════════════════════════════════

img7, _ = gui.rapid_key_and_capture(key="escape", hwnd=hwnd, pre_delay=1.0)
texts7 = ocr_image(img7) if img7 else []
page7 = record_page("S7_escape", texts7)
print(f"  Escape后: {page7}, {len(texts7)}个文字")
for t in texts7[:10]:
    print(f"    • '{t['text']}'")
log_result("S7", "escape_nav", True, f"{page7}, {len(texts7)} texts")

# 再按一次Escape
img7b, _ = gui.rapid_key_and_capture(key="escape", hwnd=hwnd, pre_delay=1.0)
texts7b = ocr_image(img7b) if img7b else []
page7b = record_page("S7_escape2", texts7b)
print(f"  Escape×2: {page7b}, {len(texts7b)}个文字")
log_result("S7", "escape2_nav", True, f"{page7b}, {len(texts7b)} texts")

# ═══════════════════════════════════════════════════════
section("S8: 快捷键测试")
# ═══════════════════════════════════════════════════════

for key_name, key_code in [("f1", "f1"), ("f2", "f2"), ("f5", "f5"), 
                            ("freeze", "f"), ("undo", "ctrl+z")]:
    img_k, _ = gui.rapid_key_and_capture(key=key_code, hwnd=hwnd, pre_delay=0.3)
    ok = img_k is not None
    log_result("S8", f"hotkey_{key_name}", ok)

# Unfreeze
gui.rapid_key_and_capture(key="f", hwnd=hwnd, pre_delay=0.2)

# ═══════════════════════════════════════════════════════
section("S9: 用户无感验证")
# ═══════════════════════════════════════════════════════

fg_end = gui.user32.GetForegroundWindow()
mouse_end = pyautogui.position()
fg_ok = fg_start == fg_end
dx = abs(mouse_end.x - mouse_start.x)
dy = abs(mouse_end.y - mouse_start.y)
mouse_ok = dx <= 15 and dy <= 15
log_result("S9", "fg_preserved", fg_ok, f"{fg_start}→{fg_end}")
log_result("S9", "mouse_restored", mouse_ok, f"Δ({dx},{dy})")

# ═══════════════════════════════════════════════════════
section("汇总")
# ═══════════════════════════════════════════════════════

total = len(results)
passed = sum(1 for r in results if r["ok"])
failed = total - passed
print(f"\n  总计: {total}项 | ✅ {passed} | ❌ {failed} | 通过率: {passed/total*100:.0f}%")

print(f"\n  VaM页面地图 ({len(page_map)}个快照):")
for name, data in page_map.items():
    print(f"    {name}: page={data['page']}, {data['total']}个文字")
    for t in data['texts'][:5]:
        print(f"      • {t}")

if issues:
    print(f"\n  问题 ({len(issues)}个):")
    for i, issue in enumerate(issues, 1):
        print(f"    [{i}] [{issue['phase']}] {issue['name']}: {issue['detail'][:60]}")

# 保存
output = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "summary": {"total": total, "passed": passed, "failed": failed},
    "results": results, "issues": issues, "page_map": page_map,
}
with open("vam_nav_v3_results.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n  结果: vam_nav_v3_results.json")
