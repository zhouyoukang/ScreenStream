"""Diagnose click delivery to VaM — test multiple click methods"""
import sys, time, ctypes
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
from vam import gui

user32 = ctypes.windll.user32

hwnd = gui.find_vam_window()
if not hwnd:
    print("No VaM"); sys.exit(1)

# Focus
r = gui.focus_window(hwnd)
print(f"Focus: {r}")
time.sleep(0.5)

# Get window rect
wrect = gui.get_window_rect(hwnd)
print(f"Window rect: {wrect}")

# Get "返回场景预览" position from OCR
scan = gui.scan(hwnd=hwnd)
target = None
for t in scan.get("texts", []):
    if "返回" in t["text"]:
        target = t
        break

if not target:
    print("Target '返回场景预览' not found in OCR")
    print("Available texts:", [t["text"] for t in scan.get("texts", [])[:10]])
    sys.exit(1)

tx, ty = target["center"]["x"], target["center"]["y"]
print(f"\nTarget: '{target['text']}' at screen ({tx}, {ty})")
print(f"  In image: ({tx - wrect['x']}, {ty - wrect['y']})")

# Method 1: pyautogui.click(x, y)
print("\n--- Method 1: pyautogui.click(x, y) ---")
import pyautogui
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

gui.focus_window(hwnd)
time.sleep(0.5)
print(f"  Mouse before: {pyautogui.position()}")
pyautogui.click(tx, ty)
time.sleep(0.3)
print(f"  Mouse after: {pyautogui.position()}")
time.sleep(2)
page1 = gui.get_vam_state()["detected_page"]
print(f"  Page after: {page1}")

# Method 2: moveTo + delay + click
print("\n--- Method 2: moveTo + delay + click ---")
gui.focus_window(hwnd)
time.sleep(0.5)
pyautogui.moveTo(tx, ty)
time.sleep(0.3)
print(f"  Mouse at target: {pyautogui.position()}")
pyautogui.click()
time.sleep(2)
page2 = gui.get_vam_state()["detected_page"]
print(f"  Page after: {page2}")

# Method 3: Win32 SendInput (mouse_event)
print("\n--- Method 3: Win32 mouse_event ---")
gui.focus_window(hwnd)
time.sleep(0.5)

# Convert screen coords to normalized 0-65535 range
screen_w = user32.GetSystemMetrics(0)
screen_h = user32.GetSystemMetrics(1)
norm_x = int(tx * 65535 / screen_w)
norm_y = int(ty * 65535 / screen_h)
print(f"  Screen: {screen_w}x{screen_h}, normalized: ({norm_x}, {norm_y})")

MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

# Move
user32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE, norm_x, norm_y, 0, 0)
time.sleep(0.2)
print(f"  Mouse position: {pyautogui.position()}")
# Click
user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
time.sleep(0.05)
user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
time.sleep(2)
page3 = gui.get_vam_state()["detected_page"]
print(f"  Page after: {page3}")

# Method 4: SendMessage WM_LBUTTONDOWN/UP to window
print("\n--- Method 4: SendMessage to hwnd ---")
gui.focus_window(hwnd)
time.sleep(0.5)

# Client coordinates (relative to window)
client_x = tx - wrect["x"]
client_y = ty - wrect["y"]
# But need to account for title bar — GetClientRect vs GetWindowRect
client_rect = ctypes.wintypes.RECT()
user32.GetClientRect(hwnd, ctypes.byref(client_rect))
window_rect = ctypes.wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(window_rect))
border_x = (wrect["w"] - client_rect.right) // 2
title_h = wrect["h"] - client_rect.bottom - border_x
print(f"  Title bar height: {title_h}, border: {border_x}")
print(f"  Client rect: {client_rect.right}x{client_rect.bottom}")

# Adjust for title bar
adj_x = client_x - border_x
adj_y = client_y - title_h
print(f"  Client coords: ({adj_x}, {adj_y})")

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001
lparam = (adj_y << 16) | (adj_x & 0xFFFF)
user32.SendMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
time.sleep(0.05)
user32.SendMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
time.sleep(2)
page4 = gui.get_vam_state()["detected_page"]
print(f"  Page after: {page4}")

print(f"\n=== Summary ===")
print(f"  Method 1 (pyautogui.click): {page1}")
print(f"  Method 2 (moveTo+click):    {page2}")
print(f"  Method 3 (mouse_event):     {page3}")
print(f"  Method 4 (SendMessage):     {page4}")
