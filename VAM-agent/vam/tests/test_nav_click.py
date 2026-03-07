"""
VaM 按钮点击导航测试 — 使用rapid_key_and_capture截屏 + 坐标点击
==============================================================
目标：通过点击底部菜单按钮导航到不同VaM页面
"""
import sys, time, json
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
import numpy as np, logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
from vam import gui

def ocr_image(img):
    ocr = gui._get_ocr()
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
            texts.append({"text": text.strip(), "cx": cx, "cy": cy})
    return texts

def print_texts(texts, limit=20):
    for t in texts[:limit]:
        print(f"    • '{t['text']}' at ({t['cx']},{t['cy']})")

def click_at(hwnd, x, y, label=""):
    """在VaM窗口的指定图像坐标处点击"""
    wrect = gui.get_window_rect(hwnd)
    screen_x = wrect["x"] + x
    screen_y = wrect["y"] + y
    
    import pyautogui
    fg_before = gui.user32.GetForegroundWindow()
    cursor_before = pyautogui.position()
    
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_SHOWWINDOW = 0x0040
    
    gui.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    gui._rapid_focus(hwnd)
    time.sleep(0.08)
    
    # 移动到目标 + 点击
    gui.user32.SetCursorPos(screen_x, screen_y)
    time.sleep(0.05)
    gui._send_input(
        gui._make_mouse_input(screen_x, screen_y, gui.MOUSEEVENTF_LEFTDOWN),
        gui._make_mouse_input(screen_x, screen_y, gui.MOUSEEVENTF_LEFTUP),
    )
    
    time.sleep(1.5)  # 等待VaM处理点击
    
    # 截屏（还在TOPMOST状态）
    import mss
    from PIL import Image
    monitor = {"left": wrect["x"], "top": wrect["y"],
               "width": wrect["w"], "height": wrect["h"]}
    with mss.mss() as sct:
        shot = sct.grab(monitor)
        raw = bytes(shot.rgb)
        img = Image.frombytes("RGB", (shot.width, shot.height), raw)
    
    # 恢复
    gui.user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE)
    gui._rapid_restore(fg_before)
    gui.user32.SetCursorPos(cursor_before[0], cursor_before[1])
    
    print(f"  → 点击 '{label}' at ({x},{y})")
    return img

# ── Init ──
hwnd = gui.find_vam_window()
if not hwnd:
    print("❌ VaM未运行"); sys.exit(1)
print(f"VaM hwnd={hwnd}")

import pyautogui
fg_start = gui.user32.GetForegroundWindow()
mouse_start = pyautogui.position()

# Step 1: 查看当前状态
print("\n=== Step 1: 当前状态 ===")
img0, _ = gui.rapid_key_and_capture(key=None, hwnd=hwnd, pre_delay=0.3)
texts0 = ocr_image(img0)
page0 = gui._detect_page([t["text"] for t in texts0])
print(f"  页面: {page0}, {len(texts0)}个文字")
print_texts(texts0)

# Step 2: 点击"编辑模式(E)"按钮
print("\n=== Step 2: 点击编辑模式(E) ===")
edit_btn = None
for t in texts0:
    if "编辑模式" in t["text"]:
        edit_btn = t
        break
if edit_btn:
    img2 = click_at(hwnd, edit_btn["cx"], edit_btn["cy"], "编辑模式(E)")
    texts2 = ocr_image(img2)
    page2 = gui._detect_page([t["text"] for t in texts2])
    print(f"  编辑模式后: {page2}, {len(texts2)}个文字")
    print_texts(texts2)
    img2.save("vam_after_edit_click.png")
else:
    print("  ⚠ 未找到编辑模式按钮")
    texts2 = texts0

# Step 3: 等2秒再截屏看看编辑器是否加载
print("\n=== Step 3: 等待编辑器加载 ===")
time.sleep(2)
img3, _ = gui.rapid_key_and_capture(key=None, hwnd=hwnd, pre_delay=0.5)
texts3 = ocr_image(img3)
page3 = gui._detect_page([t["text"] for t in texts3])
print(f"  等待后: {page3}, {len(texts3)}个文字")
print_texts(texts3)
img3.save("vam_editor_loaded.png")

# Step 4: 如果进了编辑器，尝试Ctrl+L打开场景加载
print("\n=== Step 4: 尝试更多导航 ===")
# 先查看有没有导航元素
nav_targets = ["更多选项", "Main Menu", "Scene Browser", "场景浏览器",
               "Select", "Control", "Motion", "Plugin"]
found_nav = {}
for nt in nav_targets:
    for t in texts3:
        if nt.lower() in t["text"].lower():
            found_nav[nt] = t
            break
print(f"  可导航元素: {list(found_nav.keys())}")

# 如果有更多选项，点它
if "更多选项" in found_nav:
    t = found_nav["更多选项"]
    img4 = click_at(hwnd, t["cx"], t["cy"], "更多选项")
    texts4 = ocr_image(img4)
    print(f"  更多选项后: {len(texts4)}个文字")
    print_texts(texts4)
    img4.save("vam_more_options.png")
elif any(k in found_nav for k in ["Select", "Control", "Motion", "Plugin"]):
    # 在编辑器中，尝试点击标签
    for tab_name in ["Select", "Control", "Motion", "Plugin"]:
        if tab_name in found_nav:
            t = found_nav[tab_name]
            img4 = click_at(hwnd, t["cx"], t["cy"], tab_name)
            texts4 = ocr_image(img4)
            page4 = gui._detect_page([t["text"] for t in texts4])
            print(f"  {tab_name}标签后: {page4}, {len(texts4)}个文字")
            print_texts(texts4, 15)
            break
else:
    # 尝试Ctrl+S或其他快捷键
    print("  尝试Ctrl+Shift+L (Load Scene)...")
    img4, _ = gui.rapid_key_and_capture(key="ctrl+shift+l", hwnd=hwnd, pre_delay=2.0)
    texts4 = ocr_image(img4)
    print(f"  Ctrl+Shift+L后: {len(texts4)}个文字")
    print_texts(texts4)

# Step 5: 最终验证
print("\n=== Step 5: 用户无感验证 ===")
fg_end = gui.user32.GetForegroundWindow()
mouse_end = pyautogui.position()
print(f"  前台: {fg_start}→{fg_end} {'✅' if fg_start == fg_end else '❌'}")
dx, dy = abs(mouse_end.x - mouse_start.x), abs(mouse_end.y - mouse_start.y)
print(f"  鼠标: Δ({dx},{dy}) {'✅' if dx <= 15 and dy <= 15 else '❌'}")
