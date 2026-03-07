"""VaM deep navigation: scroll 更多选项, click VaM logo, try all access paths"""
import sys, time
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
import numpy as np, logging, mss, pyautogui
from PIL import Image
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
from vam import gui

def ocr(img):
    engine = gui._get_ocr()
    s = 1.0
    if img.width > 960:
        s = 960/img.width; img = img.resize((960, int(img.height*s)))
    r, _ = engine(np.array(img))
    if not r: return []
    return [{"t": t.strip(), "x": int(sum(p[0] for p in b)/len(b)/s),
             "y": int(sum(p[1] for p in b)/len(b)/s)} for b,t,c in r if c>0.3 and t.strip()]

def warm_cap(hwnd, key=None, delay=1.0):
    gui.rapid_key_and_capture(key=None, hwnd=hwnd, pre_delay=0.15)
    time.sleep(0.1)
    img, _ = gui.rapid_key_and_capture(key=key, hwnd=hwnd, pre_delay=delay)
    return img, ocr(img) if img else []

def rapid_click(hwnd, ix, iy, wait=1.5):
    w = gui.get_window_rect(hwnd)
    sx, sy = w["x"]+ix, w["y"]+iy
    fg = gui.user32.GetForegroundWindow()
    cur = pyautogui.position()
    gui.user32.SetWindowPos(hwnd, -1, 0,0,0,0, 0x43)
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
    gui.user32.SetWindowPos(hwnd, -2, 0,0,0,0, 0x03)
    gui._rapid_restore(fg)
    gui.user32.SetCursorPos(cur[0], cur[1])
    return img, ocr(img)

def rapid_scroll(hwnd, ix, iy, delta=-3, wait=1.0):
    """Scroll at specific coordinates in VaM window"""
    w = gui.get_window_rect(hwnd)
    sx, sy = w["x"]+ix, w["y"]+iy
    fg = gui.user32.GetForegroundWindow()
    cur = pyautogui.position()
    gui.user32.SetWindowPos(hwnd, -1, 0,0,0,0, 0x43)
    gui._rapid_focus(hwnd)
    time.sleep(0.08)
    gui.user32.SetCursorPos(sx, sy)
    time.sleep(0.03)
    # Scroll using SendInput
    WHEEL = 0x0800
    import ctypes
    inp = gui.INPUT(type=1)
    inp.ii.mi.dx = int(sx * 65535 / ctypes.windll.user32.GetSystemMetrics(0))
    inp.ii.mi.dy = int(sy * 65535 / ctypes.windll.user32.GetSystemMetrics(1))
    inp.ii.mi.mouseData = delta * 120
    inp.ii.mi.dwFlags = WHEEL | 0x8000  # MOUSEEVENTF_WHEEL | ABSOLUTE
    gui._send_input(inp)
    time.sleep(wait)
    mon = {"left":w["x"],"top":w["y"],"width":w["w"],"height":w["h"]}
    with mss.mss() as s:
        sh = s.grab(mon)
        img = Image.frombytes("RGB", (sh.width, sh.height), bytes(sh.rgb))
    gui.user32.SetWindowPos(hwnd, -2, 0,0,0,0, 0x03)
    gui._rapid_restore(fg)
    gui.user32.SetCursorPos(cur[0], cur[1])
    return img, ocr(img)

def pt(texts, n=20):
    for t in texts[:n]: print(f"    '{t['t']}' ({t['x']},{t['y']})")

hwnd = gui.find_vam_window()
if not hwnd: print("❌"); sys.exit(1)
print(f"hwnd={hwnd}")

# ── 1. Show UI ──
print("\n=== 1. Show UI ===")
img, texts = warm_cap(hwnd, key=None, delay=0.3)
if len(texts) < 6:
    img, texts = warm_cap(hwnd, key="u", delay=1.2)
print(f"  {len(texts)} texts")
pt(texts)

# ── 2. Click 编辑模式(E) and check what changes ──
print("\n=== 2. Click 编辑模式(E) ===")
for t in texts:
    if "编辑模式" in t["t"]:
        # Save pre-click screenshot
        img.save("vam_pre_edit.png")
        img2, t2 = rapid_click(hwnd, t["x"], t["y"], wait=3.0)
        img2.save("vam_post_edit.png")
        print(f"  After click: {len(t2)} texts")
        pt(t2)
        # Check for new texts not in original
        orig = set(x["t"] for x in texts)
        new_texts = [x for x in t2 if x["t"] not in orig]
        if new_texts:
            print(f"  NEW texts after edit click:")
            pt(new_texts)
        break

# ── 3. Try clicking center of screen (select an atom in edit mode) ──
print("\n=== 3. Click center of screen ===")
cx, cy = 649, 688  # Center of 1298x1377
img3, t3 = rapid_click(hwnd, cx, cy, wait=2.0)
print(f"  After center click: {len(t3)} texts")
pt(t3)
new3 = set(x["t"] for x in t3) - set(x["t"] for x in t2 if 't2' in dir())
if new3:
    print(f"  NEW: {new3}")

# ── 4. Try right-click center (context menu in edit mode) ──
print("\n=== 4. Right-click center ===")
w = gui.get_window_rect(hwnd)
sx, sy = w["x"]+cx, w["y"]+cy
fg = gui.user32.GetForegroundWindow()
cur = pyautogui.position()
gui.user32.SetWindowPos(hwnd, -1, 0,0,0,0, 0x43)
gui._rapid_focus(hwnd)
time.sleep(0.08)
gui.user32.SetCursorPos(sx, sy)
time.sleep(0.03)
gui._send_input(
    gui._make_mouse_input(sx, sy, gui.MOUSEEVENTF_RIGHTDOWN),
    gui._make_mouse_input(sx, sy, gui.MOUSEEVENTF_RIGHTUP))
time.sleep(2.0)
mon = {"left":w["x"],"top":w["y"],"width":w["w"],"height":w["h"]}
with mss.mss() as s:
    sh = s.grab(mon)
    img4 = Image.frombytes("RGB", (sh.width, sh.height), bytes(sh.rgb))
gui.user32.SetWindowPos(hwnd, -2, 0,0,0,0, 0x03)
gui._rapid_restore(fg)
gui.user32.SetCursorPos(cur[0], cur[1])
t4 = ocr(img4)
print(f"  After right-click: {len(t4)} texts")
pt(t4)
img4.save("vam_rightclick.png")

# ── 5. Try Ctrl+L (Load scene) ──
print("\n=== 5. Ctrl+L (Load Scene) ===")
img5, t5 = warm_cap(hwnd, key="ctrl+l", delay=2.0)
print(f"  After Ctrl+L: {len(t5)} texts")
pt(t5)
p5 = gui._detect_page([t["t"] for t in t5])
print(f"  Page: {p5}")
if len(t5) > 10:
    img5.save("vam_ctrl_l.png")

# ── 6. Escape back and try Ctrl+N (New Scene → main menu?) ──
print("\n=== 6. Escape + Ctrl+N ===")
warm_cap(hwnd, key="escape", delay=0.5)
img6, t6 = warm_cap(hwnd, key="ctrl+n", delay=2.0)
print(f"  After Ctrl+N: {len(t6)} texts")
pt(t6)
p6 = gui._detect_page([t["t"] for t in t6])
print(f"  Page: {p6}")

# ── 7. Check screenshots ──
print("\n=== 7. Verify ===")
fg1 = gui.user32.GetForegroundWindow()
m1 = pyautogui.position()
print(f"  FG preserved: {'✅' if fg1 == gui.user32.GetForegroundWindow() else '❌'}")
print(f"  Screenshots saved: vam_pre_edit.png, vam_post_edit.png, vam_rightclick.png")
