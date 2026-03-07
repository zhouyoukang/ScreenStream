"""Test clicking various VaM elements to find which ones respond"""
import sys, time, ctypes
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
from vam import gui

user32 = ctypes.windll.user32

# Ensure DPI aware FIRST
gui._ensure_dpi_aware()

hwnd = gui.find_vam_window()
if not hwnd:
    print("No VaM"); sys.exit(1)

import pyautogui
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

def safe_click(x, y, label):
    """Move to position, verify, click, wait, check"""
    gui.focus_window(hwnd)
    time.sleep(0.3)
    
    pyautogui.moveTo(x, y)
    time.sleep(0.2)
    pos = pyautogui.position()
    print(f"  Mouse at: ({pos.x}, {pos.y}) — target: ({x}, {y}) — delta: ({pos.x-x}, {pos.y-y})")
    
    pyautogui.mouseDown()
    time.sleep(0.05)
    pyautogui.mouseUp()
    time.sleep(0.5)
    print(f"  Clicked: {label}")

# Get current state
gui.focus_window(hwnd)
time.sleep(0.5)

# Get physical window rect (DPI-aware)
rect = ctypes.wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
print(f"Physical window rect: ({rect.left}, {rect.top}) {rect.right-rect.left}x{rect.bottom-rect.top}")

# OCR scan
scan = gui.scan(hwnd=hwnd)
print(f"OCR: {scan.get('total', 0)} texts")
targets = {}
for t in scan.get("texts", []):
    name = t["text"]
    cx, cy = t["center"]["x"], t["center"]["y"]
    conf = t["confidence"]
    targets[name] = (cx, cy)
    if conf > 0.9:
        print(f"  [{conf:.2f}] ({cx:5d},{cy:4d}) {name[:40]}")

# Test 1: Click "显示隐藏" (filter button, should toggle something)
print("\n=== Test 1: Click '显示隐藏' ===")
if "显示隐藏" in targets:
    x, y = targets["显示隐藏"]
    print(f"  Target at ({x}, {y})")
    scan_before = gui.scan(hwnd=hwnd)
    before_count = scan_before.get("total", 0)
    safe_click(x, y, "显示隐藏")
    time.sleep(1)
    scan_after = gui.scan(hwnd=hwnd)
    after_count = scan_after.get("total", 0)
    print(f"  Text count: {before_count} → {after_count} (delta={after_count-before_count})")
else:
    print("  Not found")

# Test 2: Click "收藏夹" (favorites button)
print("\n=== Test 2: Click '收藏夹' ===")
if "收藏夹" in targets:
    x, y = targets["收藏夹"]
    print(f"  Target at ({x}, {y})")
    safe_click(x, y, "收藏夹")
    time.sleep(1)
    scan_after = gui.scan(hwnd=hwnd)
    print(f"  Text count after: {scan_after.get('total', 0)}")
else:
    print("  Not found")

# Test 3: Click "返回场景预览" with slight offset (try clicking 10px above text center)
print("\n=== Test 3: Click '返回场景预览' (offset -10y) ===")
if "返回场景预览" in targets:
    x, y = targets["返回场景预览"]
    y_adj = y - 10
    print(f"  Target at ({x}, {y}), clicking ({x}, {y_adj})")
    safe_click(x, y_adj, "返回场景预览 offset")
    time.sleep(2)
    page = gui.get_vam_state()["detected_page"]
    print(f"  Page after: {page}")
else:
    print("  Not found")

# Test 4: Click first scene thumbnail (should have some effect)
print("\n=== Test 4: Click first scene ===")
for name, (x, y) in targets.items():
    if "voxta" in name.lower() or "scene" in name.lower() or "dance" in name.lower():
        print(f"  Clicking scene: '{name}' at ({x}, {y})")
        safe_click(x, y, name)
        time.sleep(3)
        # Save screenshot
        img, wr = gui.capture_printwindow(hwnd)
        img.save(r"d:\道\道生一\一生二\VAM-agent\vam\tests\vam_after_scene_click.png")
        page = gui.get_vam_state()["detected_page"]
        print(f"  Page after: {page}")
        break

# Test 5: Click exact center of window (should do something or nothing)
print("\n=== Test 5: Click window center ===")
cx = rect.left + (rect.right - rect.left) // 2
cy = rect.top + (rect.bottom - rect.top) // 2
print(f"  Window center: ({cx}, {cy})")
safe_click(cx, cy, "window center")
time.sleep(1)
