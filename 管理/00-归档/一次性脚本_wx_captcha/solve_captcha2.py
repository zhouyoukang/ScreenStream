"""强制Chrome置顶 + 像素定位滑块 + 原子拖拽"""
import ctypes
import time
import random
import pyautogui
import pygetwindow as gw
from PIL import Image

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

# === 1. 强制Chrome置顶 ===
user32 = ctypes.windll.user32

wins = gw.getWindowsWithTitle('小程序')
if not wins:
    wins = gw.getWindowsWithTitle('Chrome')
    
if not wins:
    print("ERROR: No Chrome window found")
    exit(1)

win = wins[0]
hwnd = win._hWnd

# 恢复+最大化+置顶
win.restore()
time.sleep(0.3)
win.maximize()
time.sleep(0.3)

# SetWindowPos with HWND_TOPMOST
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
time.sleep(0.3)

# Force foreground
user32.SetForegroundWindow(hwnd)
time.sleep(0.5)

print(f"Chrome TOPMOST + foreground: hwnd={hwnd}")

# === 2. 截屏并找蓝色滑块 ===
img = pyautogui.screenshot()
pixels = img.load()
w, h = img.size
print(f"Screen: {w}x{h}")

# 找蓝色滑块 - RGB大约(33,120,243)到(80,180,255)范围
blue_pixels = []
for y in range(h // 3, h * 2 // 3):  # 只搜索屏幕中间1/3区域
    for x in range(w // 4, w * 3 // 4):  # 只搜索屏幕中间区域
        r, g, b = pixels[x, y][:3]
        # 蓝色滑块特征：蓝色分量高，红色分量低
        if b > 200 and r < 100 and g < 180 and b - r > 120:
            blue_pixels.append((x, y))

if not blue_pixels:
    print("WARNING: No blue slider found! Trying broader search...")
    for y in range(100, h - 100):
        for x in range(100, w - 100):
            r, g, b = pixels[x, y][:3]
            if b > 180 and r < 120 and g < 200 and b - r > 100:
                blue_pixels.append((x, y))

if not blue_pixels:
    print("ERROR: Cannot find blue slider pixels")
    # 取消TOPMOST
    HWND_NOTOPMOST = -2
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    exit(1)

# 计算蓝色区域的中心（即滑块中心）
min_x = min(p[0] for p in blue_pixels)
max_x = max(p[0] for p in blue_pixels)
min_y = min(p[0] for p in blue_pixels)
max_y = max(p[0] for p in blue_pixels)
avg_x = sum(p[0] for p in blue_pixels) // len(blue_pixels)
avg_y = sum(p[1] for p in blue_pixels) // len(blue_pixels)
print(f"Blue slider: center=({avg_x},{avg_y}), x_range=[{min_x},{max_x}], count={len(blue_pixels)}")

# 滑块中心
slider_x = avg_x
slider_y = avg_y

# === 3. 估算拖拽距离 ===
# 从CDP截图分析：缺口在图片约55-60%处
# 滑块轨道宽度：从蓝色滑块左边缘到轨道右边缘
# 蓝色滑块宽度约40px，轨道从滑块左边缘开始
# 轨道宽度约为滑块右边到x=max_x + 一个估算值
# 简化：从当前位置拖100px（对应约55%的轨道位置）
drag_distance = 95  # 调整此值

print(f"Drag: from ({slider_x},{slider_y}) distance={drag_distance}px right")

# === 4. 点击Chrome确保焦点，然后拖拽 ===
# 先点击标题栏确保焦点
pyautogui.click(slider_x, slider_y - 50)
time.sleep(0.3)

# 原子拖拽操作
pyautogui.moveTo(slider_x, slider_y, duration=0.2)
time.sleep(0.15)
pyautogui.drag(drag_distance, 0, duration=0.8, 
               tween=pyautogui.easeOutQuad)
time.sleep(1.5)

# === 5. 截屏看结果 ===
result = pyautogui.screenshot('E:/github/AIOT/ScreenStream_v2/captcha_result2.png')
print("Result screenshot saved")

# === 6. 取消TOPMOST ===
HWND_NOTOPMOST = -2
user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
print("Done - Chrome un-topped")
