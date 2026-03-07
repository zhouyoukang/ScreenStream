"""
VaM 全页面导航 v4 — 可靠的单会话方案
=====================================
1. rapid_key_and_capture 按u显示UI
2. 从OCR结果获取按钮坐标
3. 用rapid_click_and_capture 点击按钮并截屏
"""
import sys, time, json
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
import numpy as np, logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
from vam import gui

results = []
issues = []
page_map = {}

def log_result(phase, name, ok, detail=""):
    results.append({"phase": phase, "name": name, "ok": ok, "detail": detail})
    print(f"  {'✅' if ok else '❌'} {name}: {detail[:100]}")
    if not ok:
        issues.append({"phase": phase, "name": name, "detail": detail})

def ocr_img(img):
    ocr = gui._get_ocr()
    scale = 1.0
    if img.width > 960:
        scale = 960 / img.width
        img = img.resize((960, int(img.height * scale)))
    result, _ = ocr(np.array(img))
    if not result:
        return []
    return [{"text": t.strip(), "cx": int(sum(p[0] for p in b)/len(b)/scale),
             "cy": int(sum(p[1] for p in b)/len(b)/scale), "conf": c}
            for b, t, c in result if c > 0.3 and t.strip()]

def find_text_in(texts, target):
    for t in texts:
        if target.lower() in t["text"].lower():
            return t
    return None

def rapid_click_and_capture(hwnd, img_x, img_y, label="", wait=1.5):
    """单次TOPMOST会话: 点击img坐标 → 等待 → 截屏 → 恢复"""
    import mss, pyautogui
    from PIL import Image
    
    wrect = gui.get_window_rect(hwnd)
    sx, sy = wrect["x"] + img_x, wrect["y"] + img_y
    
    fg = gui.user32.GetForegroundWindow()
    cur = pyautogui.position()
    
    T, NT = -1, -2
    F = 0x0002 | 0x0001 | 0x0040
    
    gui.user32.SetWindowPos(hwnd, T, 0, 0, 0, 0, F)
    gui._rapid_focus(hwnd)
    time.sleep(0.08)
    
    gui.user32.SetCursorPos(sx, sy)
    time.sleep(0.03)
    gui._send_input(
        gui._make_mouse_input(sx, sy, gui.MOUSEEVENTF_LEFTDOWN),
        gui._make_mouse_input(sx, sy, gui.MOUSEEVENTF_LEFTUP),
    )
    log.info("rapid_click at (%d,%d) → screen(%d,%d) '%s'", img_x, img_y, sx, sy, label)
    
    time.sleep(wait)
    
    monitor = {"left": wrect["x"], "top": wrect["y"],
               "width": wrect["w"], "height": wrect["h"]}
    with mss.mss() as sct:
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", (shot.width, shot.height), bytes(shot.rgb))
    
    gui.user32.SetWindowPos(hwnd, NT, 0, 0, 0, 0, 0x0002 | 0x0001)
    gui._rapid_restore(fg)
    gui.user32.SetCursorPos(cur[0], cur[1])
    
    return img

log = logging.getLogger("nav_v4")

# ── Init ──
hwnd = gui.find_vam_window()
if not hwnd:
    print("❌ VaM未运行"); sys.exit(1)
print(f"VaM hwnd={hwnd}")

import pyautogui
fg_start = gui.user32.GetForegroundWindow()
mouse_start = pyautogui.position()

# ═══════════════════════════════════════════════════════
print("\n" + "="*60 + "\nS1: 初始截屏\n" + "="*60)
img1, _ = gui.rapid_key_and_capture(key=None, hwnd=hwnd, pre_delay=0.3)
t1 = ocr_img(img1)
p1 = gui._detect_page([t["text"] for t in t1])
print(f"  页面: {p1}, {len(t1)}个文字")
for t in t1[:8]: print(f"    • '{t['text']}' ({t['cx']},{t['cy']})")

# ═══════════════════════════════════════════════════════
print("\n" + "="*60 + "\nS2: 按u显示UI覆盖菜单\n" + "="*60)

# 如果UI已隐藏（<6文字），按u显示
if len(t1) < 6:
    img2, _ = gui.rapid_key_and_capture(key="u", hwnd=hwnd, pre_delay=0.8)
    t2 = ocr_img(img2)
else:
    t2 = t1

p2 = gui._detect_page([t["text"] for t in t2])
print(f"  页面: {p2}, {len(t2)}个文字")
for t in t2[:15]: print(f"    • '{t['text']}' ({t['cx']},{t['cy']})")
log_result("S2", "show_ui", len(t2) > 5, f"{len(t2)} texts")

# ═══════════════════════════════════════════════════════
print("\n" + "="*60 + "\nS3: 点击'编辑模式(E)'进入编辑器\n" + "="*60)

edit_btn = find_text_in(t2, "编辑模式")
if edit_btn:
    img3 = rapid_click_and_capture(hwnd, edit_btn["cx"], edit_btn["cy"], "编辑模式(E)", wait=2.0)
    t3 = ocr_img(img3)
    p3 = gui._detect_page([t["text"] for t in t3])
    print(f"  点击后: {p3}, {len(t3)}个文字")
    for t in t3[:20]: print(f"    • '{t['text']}' ({t['cx']},{t['cy']})")
    log_result("S3", "click_edit", len(t3) > len(t2) or p3 != "scene_preview",
               f"{p2}→{p3}, {len(t2)}→{len(t3)} texts")
    img3.save("vam_s3_edit.png")
else:
    print("  ⚠ 未找到编辑模式按钮，尝试按p进入play再按e")
    # 如果看不到编辑模式按钮，可能已经在编辑模式，试试其他
    t3 = t2
    p3 = p2
    log_result("S3", "edit_btn_missing", False, "编辑模式 not found")

# ═══════════════════════════════════════════════════════
print("\n" + "="*60 + "\nS4: 编辑器面板探索\n" + "="*60)

# 查找编辑器标准元素
editor_keywords = ["Select", "Control", "Motion", "Clothing", "Hair", 
                   "Skin", "Plugin", "Animation", "Morph", "Appearance",
                   "Pose", "General", "Auto", "Undo", "Redo",
                   "选择", "控制", "动作", "衣服", "头发", "皮肤",
                   "Atom", "Person", "Light", "Camera"]
found = {}
for kw in editor_keywords:
    btn = find_text_in(t3, kw)
    if btn:
        found[kw] = btn
if found:
    print(f"  编辑器元素: {list(found.keys())}")
    log_result("S4", "editor_elements", True, str(list(found.keys())))
    
    # 点击一个编辑器标签
    for tab in ["Select", "Control", "Motion", "选择"]:
        if tab in found:
            print(f"  点击标签: {tab}")
            img4 = rapid_click_and_capture(hwnd, found[tab]["cx"], found[tab]["cy"], tab, wait=1.5)
            t4 = ocr_img(img4)
            p4 = gui._detect_page([t["text"] for t in t4])
            print(f"  {tab}标签后: {p4}, {len(t4)}个文字")
            for t in t4[:15]: print(f"    • '{t['text']}'")
            log_result("S4", f"tab_{tab}", len(t4) > 5, f"{len(t4)} texts")
            break
else:
    print("  未找到编辑器标准元素，搜索所有文字...")
    for t in t3[:25]: print(f"    • '{t['text']}' ({t['cx']},{t['cy']})")
    log_result("S4", "editor_elements", False, "no editor keywords found")

# ═══════════════════════════════════════════════════════
print("\n" + "="*60 + "\nS5: 导航到更多选项/主菜单\n" + "="*60)

# 先确保UI可见
img5_pre, _ = gui.rapid_key_and_capture(key=None, hwnd=hwnd, pre_delay=0.3)
t5_pre = ocr_img(img5_pre)
if len(t5_pre) < 6:
    img5_pre, _ = gui.rapid_key_and_capture(key="u", hwnd=hwnd, pre_delay=0.8)
    t5_pre = ocr_img(img5_pre)

more_btn = find_text_in(t5_pre, "更多选项")
if more_btn:
    img5 = rapid_click_and_capture(hwnd, more_btn["cx"], more_btn["cy"], "更多选项", wait=2.0)
    t5 = ocr_img(img5)
    p5 = gui._detect_page([t["text"] for t in t5])
    print(f"  更多选项后: {p5}, {len(t5)}个文字")
    for t in t5[:25]: print(f"    • '{t['text']}' ({t['cx']},{t['cy']})")
    img5.save("vam_s5_more.png")
    log_result("S5", "more_options", len(t5) > len(t5_pre), f"{len(t5)} texts")
    
    # 查找子菜单项
    sub_items = ["Main Menu", "Scene Browser", "Load Scene", "New Scene",
                 "场景浏览器", "主菜单", "加载场景", "新建场景",
                 "Open Scene", "Browse"]
    for si in sub_items:
        btn = find_text_in(t5, si)
        if btn:
            print(f"\n  找到子菜单: '{si}'")
            img5b = rapid_click_and_capture(hwnd, btn["cx"], btn["cy"], si, wait=2.0)
            t5b = ocr_img(img5b)
            p5b = gui._detect_page([t["text"] for t in t5b])
            print(f"  '{si}'后: {p5b}, {len(t5b)}个文字")
            for t in t5b[:20]: print(f"    • '{t['text']}'")
            img5b.save("vam_s5_submenu.png")
            log_result("S5", f"submenu_{si}", True, f"{p5b}, {len(t5b)} texts")
            break
else:
    print("  未找到更多选项按钮")
    log_result("S5", "more_options", False, "更多选项 not found")

# ═══════════════════════════════════════════════════════
print("\n" + "="*60 + "\nS6: 用户无感验证\n" + "="*60)

fg_end = gui.user32.GetForegroundWindow()
mouse_end = pyautogui.position()
dx, dy = abs(mouse_end.x - mouse_start.x), abs(mouse_end.y - mouse_start.y)
log_result("S6", "fg_preserved", fg_start == fg_end, f"{fg_start}→{fg_end}")
log_result("S6", "mouse_restored", dx <= 15 and dy <= 15, f"Δ({dx},{dy})")

# ═══════════════════════════════════════════════════════
print("\n" + "="*60 + "\n汇总\n" + "="*60)

total = len(results)
passed = sum(1 for r in results if r["ok"])
print(f"\n  总计: {total}项 | ✅ {passed} | ❌ {total-passed} | 通过率: {passed/total*100:.0f}%")
if issues:
    print(f"\n  问题 ({len(issues)}个):")
    for i, iss in enumerate(issues, 1):
        print(f"    [{i}] {iss['phase']}/{iss['name']}: {iss['detail'][:60]}")

with open("vam_nav_v4_results.json", "w", encoding="utf-8") as f:
    json.dump({"results": results, "issues": issues, "page_map": page_map,
               "summary": {"total": total, "passed": passed}}, f, ensure_ascii=False, indent=2)
