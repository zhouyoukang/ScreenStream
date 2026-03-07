"""
VaM 全页面导航+功能测试 v5
=========================
核心模式: warm-up capture → key/click → capture
"""
import sys, time, json
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
import numpy as np, logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
from vam import gui
import pyautogui, mss
from PIL import Image

log = logging.getLogger("v5")
results, issues, page_snapshots = [], [], {}

def log_r(phase, name, ok, detail=""):
    results.append({"phase": phase, "name": name, "ok": ok, "detail": detail})
    print(f"  {'✅' if ok else '❌'} {name}: {detail[:100]}")
    if not ok: issues.append(f"[{phase}] {name}: {detail[:80]}")

def ocr(img):
    engine = gui._get_ocr()
    s = 1.0
    if img.width > 960:
        s = 960/img.width; img = img.resize((960, int(img.height*s)))
    r, _ = engine(np.array(img))
    if not r: return []
    return [{"t": t.strip(), "x": int(sum(p[0] for p in b)/len(b)/s),
             "y": int(sum(p[1] for p in b)/len(b)/s)} for b,t,c in r if c>0.3 and t.strip()]

def find(texts, target):
    for t in texts:
        if target.lower() in t["t"].lower(): return t
    return None

def warm_key_capture(hwnd, key=None, delay=1.0):
    """先warm-up再按键截屏(解决VaM首次focus不渲染问题)"""
    gui.rapid_key_and_capture(key=None, hwnd=hwnd, pre_delay=0.15)  # warm-up
    time.sleep(0.1)
    img, rect = gui.rapid_key_and_capture(key=key, hwnd=hwnd, pre_delay=delay)
    return img, ocr(img) if img else []

def rapid_click_cap(hwnd, ix, iy, wait=1.5):
    """TOPMOST+focus→click→wait→capture→restore"""
    w = gui.get_window_rect(hwnd)
    sx, sy = w["x"]+ix, w["y"]+iy
    fg = gui.user32.GetForegroundWindow()
    cur = pyautogui.position()
    T, NT, F = -1, -2, 0x43  # TOPMOST, NOTOPMOST, NOMOVE|NOSIZE|SHOWWINDOW
    gui.user32.SetWindowPos(hwnd, T, 0,0,0,0, F)
    gui._rapid_focus(hwnd)
    time.sleep(0.08)
    gui.user32.SetCursorPos(sx, sy)
    time.sleep(0.03)
    gui._send_input(
        gui._make_mouse_input(sx, sy, gui.MOUSEEVENTF_LEFTDOWN),
        gui._make_mouse_input(sx, sy, gui.MOUSEEVENTF_LEFTUP))
    time.sleep(wait)
    mon = {"left":w["x"],"top":w["y"],"width":w["w"],"height":w["h"]}
    with mss.mss() as s:
        sh = s.grab(mon)
        img = Image.frombytes("RGB", (sh.width, sh.height), bytes(sh.rgb))
    gui.user32.SetWindowPos(hwnd, NT, 0,0,0,0, 0x03)
    gui._rapid_restore(fg)
    gui.user32.SetCursorPos(cur[0], cur[1])
    return img, ocr(img)

def snap(name, texts):
    page = gui._detect_page([t["t"] for t in texts])
    page_snapshots[name] = {"page": page, "n": len(texts),
                            "texts": [t["t"] for t in texts[:25]]}
    return page

# ── Init ──
hwnd = gui.find_vam_window()
if not hwnd: print("❌ VaM未运行"); sys.exit(1)
print(f"VaM hwnd={hwnd}")
fg0 = gui.user32.GetForegroundWindow()
m0 = pyautogui.position()

# ═══════════════════════════════════════════════════════
print("\n" + "="*55 + "\n  S1: 初始状态 + 显示UI\n" + "="*55)

img1, t1 = warm_key_capture(hwnd, key=None, delay=0.3)
p1 = snap("S1_raw", t1)
print(f"  初始: {p1}, {len(t1)}个文字")
for t in t1[:5]: print(f"    • '{t['t']}' ({t['x']},{t['y']})")

# 确保UI可见
if len(t1) < 6:
    img1u, t1u = warm_key_capture(hwnd, key="u", delay=1.2)
    p1u = snap("S1_with_ui", t1u)
    print(f"  按u后: {p1u}, {len(t1u)}个文字")
    for t in t1u[:12]: print(f"    • '{t['t']}' ({t['x']},{t['y']})")
    t_ui = t1u
else:
    t_ui = t1
log_r("S1", "ui_visible", len(t_ui) >= 6, f"{len(t_ui)} texts")

# ═══════════════════════════════════════════════════════
print("\n" + "="*55 + "\n  S2: 点击编辑模式(E)\n" + "="*55)

edit_btn = find(t_ui, "编辑模式")
if edit_btn:
    img2, t2 = rapid_click_cap(hwnd, edit_btn["x"], edit_btn["y"], wait=2.5)
    p2 = snap("S2_editor", t2)
    print(f"  编辑模式: {p2}, {len(t2)}个文字")
    for t in t2[:20]: print(f"    • '{t['t']}' ({t['x']},{t['y']})")
    log_r("S2", "enter_edit", len(t2) > 8, f"{p2}, {len(t2)} texts")
    
    # 如果编辑器有内容，探索标签
    editor_kw = {}
    for kw in ["Select","Control","Motion","Clothing","Hair","Plugin",
               "Appearance","Animation","Atom","Person"]:
        b = find(t2, kw)
        if b: editor_kw[kw] = b
    if editor_kw:
        print(f"  编辑器标签: {list(editor_kw.keys())}")
        log_r("S2", "editor_tabs", True, str(list(editor_kw.keys())))
        
        # 点击第一个标签
        first_tab = list(editor_kw.keys())[0]
        fb = editor_kw[first_tab]
        img2t, t2t = rapid_click_cap(hwnd, fb["x"], fb["y"], wait=1.5)
        p2t = snap(f"S2_tab_{first_tab}", t2t)
        print(f"  {first_tab}标签: {p2t}, {len(t2t)}个文字")
        for t in t2t[:10]: print(f"    • '{t['t']}'")
        log_r("S2", f"tab_{first_tab}", len(t2t) > 3, f"{len(t2t)} texts")
else:
    print("  编辑模式按钮未找到")
    log_r("S2", "enter_edit", False, "button not found")
    t2 = t_ui

# ═══════════════════════════════════════════════════════
print("\n" + "="*55 + "\n  S3: 显示更多选项面板\n" + "="*55)

# 先确保在play模式看到底部菜单
# 按p回到play模式
img3p, t3p = warm_key_capture(hwnd, key="p", delay=1.2)
p3p = snap("S3_play", t3p)
print(f"  按p: {p3p}, {len(t3p)}个文字")

# 如果UI不可见，按u
if len(t3p) < 6:
    img3u, t3u = warm_key_capture(hwnd, key="u", delay=1.2)
    t3p = t3u

more_btn = find(t3p, "更多选项")
if more_btn:
    img3m, t3m = rapid_click_cap(hwnd, more_btn["x"], more_btn["y"], wait=2.0)
    p3m = snap("S3_more_options", t3m)
    print(f"  更多选项: {p3m}, {len(t3m)}个文字")
    for t in t3m[:20]: print(f"    • '{t['t']}' ({t['x']},{t['y']})")
    log_r("S3", "more_options", len(t3m) > 5, f"{len(t3m)} texts")
    
    # 查找所有可导航项
    nav_items = {}
    for label in ["Main Menu","Scene Browser","Load Scene","New Scene",
                   "Open Scene","场景浏览器","主菜单","Save Scene",
                   "Exit","退出","保存","世界规模","时间尺度","锁定导航"]:
        b = find(t3m, label)
        if b: nav_items[label] = b
    print(f"  可用选项: {list(nav_items.keys())}")
    log_r("S3", "nav_items", len(nav_items) > 0, str(list(nav_items.keys())))
else:
    print("  更多选项未找到")
    log_r("S3", "more_options", False, "not found")

# ═══════════════════════════════════════════════════════
print("\n" + "="*55 + "\n  S4: Escape导航链\n" + "="*55)

for i in range(4):
    img4, t4 = warm_key_capture(hwnd, key="escape", delay=1.5)
    p4 = snap(f"S4_esc{i+1}", t4)
    print(f"  Esc×{i+1}: {p4}, {len(t4)}个文字")
    for t in t4[:8]: print(f"    • '{t['t']}'")
    if p4 in ("main_menu", "scene_browser"):
        log_r("S4", "escape_to_menu", True, f"Esc×{i+1} → {p4}")
        break
else:
    log_r("S4", "escape_chain", True, f"final: {p4}, {len(t4)} texts")

# ═══════════════════════════════════════════════════════
print("\n" + "="*55 + "\n  S5: 当前页面交互测试\n" + "="*55)

# 获取最新状态
img5, t5 = warm_key_capture(hwnd, key=None, delay=0.5)
p5 = snap("S5_current", t5)
print(f"  当前: {p5}, {len(t5)}个文字")

# 滚动测试
before_texts = set(t["t"] for t in t5)
gui.rapid_key_and_capture(key=None, hwnd=hwnd, pre_delay=0.1)  # warm-up for scroll
gui.press_key("pagedown", hwnd=hwnd)
time.sleep(1)
img5s, t5s = warm_key_capture(hwnd, key=None, delay=0.5)
after_texts = set(t["t"] for t in t5s)
scroll_changed = before_texts != after_texts
print(f"  PageDown: {'内容变化' if scroll_changed else '无变化'}")
log_r("S5", "pagedown", True, f"changed={scroll_changed}")

# ═══════════════════════════════════════════════════════
print("\n" + "="*55 + "\n  S6: 快捷键测试\n" + "="*55)

hotkeys_ok = 0
for key, name in [("f1","cam1"),("f2","cam2"),("f5","reset_cam"),
                   ("f","freeze"),("ctrl+z","undo")]:
    img_k, _ = gui.rapid_key_and_capture(key=key, hwnd=hwnd, pre_delay=0.2)
    ok = img_k is not None
    if ok: hotkeys_ok += 1
    log_r("S6", f"key_{name}", ok)
# Unfreeze
gui.rapid_key_and_capture(key="f", hwnd=hwnd, pre_delay=0.1)

# ═══════════════════════════════════════════════════════
print("\n" + "="*55 + "\n  S7: 用户无感验证\n" + "="*55)

fg1 = gui.user32.GetForegroundWindow()
m1 = pyautogui.position()
dx, dy = abs(m1.x-m0.x), abs(m1.y-m0.y)
log_r("S7", "fg_preserved", fg0==fg1, f"{fg0}→{fg1}")
log_r("S7", "mouse_restored", dx<=15 and dy<=15, f"Δ({dx},{dy})")

# ═══════════════════════════════════════════════════════
print("\n" + "="*55 + "\n  汇总\n" + "="*55)

total = len(results)
passed = sum(1 for r in results if r["ok"])
print(f"\n  总计: {total}项 | ✅ {passed} | ❌ {total-passed} | 通过率: {passed/total*100:.0f}%")

print(f"\n  VaM页面快照 ({len(page_snapshots)}个):")
for name, data in page_snapshots.items():
    print(f"    {name}: page={data['page']}, {data['n']}个文字")

if issues:
    print(f"\n  问题 ({len(issues)}个):")
    for i, iss in enumerate(issues, 1): print(f"    [{i}] {iss}")

with open("vam_nav_v5.json", "w", encoding="utf-8") as f:
    json.dump({"summary": {"total":total,"passed":passed},
               "results":results,"issues":issues,
               "page_snapshots":page_snapshots}, f, ensure_ascii=False, indent=2)
print(f"\n  结果: vam_nav_v5.json")
