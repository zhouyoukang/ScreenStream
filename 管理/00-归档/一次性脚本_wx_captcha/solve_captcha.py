"""物理拖拽腾讯滑块验证码"""
import time
import pyautogui
import pygetwindow as gw

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

# 1. 找到并激活Chrome窗口
wins = gw.getWindowsWithTitle('小程序')
if not wins:
    wins = gw.getWindowsWithTitle('Google Chrome')
if not wins:
    print("ERROR: Chrome window not found")
    exit(1)

win = wins[0]
print(f"Window: {win.title[:60]}")
print(f"Before activate: pos=({win.left},{win.top}) size=({win.width},{win.height})")

# 激活并最大化
win.restore()
time.sleep(0.5)
win.activate()
time.sleep(0.5)

# 刷新窗口信息
win = gw.getWindowsWithTitle('小程序')[0]
print(f"After activate: pos=({win.left},{win.top}) size=({win.width},{win.height})")

# 2. 截屏找滑块位置
# Chrome工具栏高度约130px（标签栏+地址栏+书签栏）
# 从CDP得知：iframe在viewport (325,174)，滑块handle在viewport约(393,467)
# viewport坐标 + 窗口客户区偏移 = 屏幕坐标

# Chrome客户区偏移（标题栏+工具栏）
chrome_toolbar_height = 138  # 典型值，含标签栏+地址栏+书签栏
chrome_left_border = 8

# 计算滑块屏幕坐标
slider_vp_x = 393  # 滑块在viewport中的x
slider_vp_y = 467  # 滑块在viewport中的y（注意页面滚动了432px，但截图显示滑块可见）

# 但页面滚动了432px，而截图显示滑块仍然可见
# 这说明验证码弹窗是fixed定位，viewport坐标直接可用
slider_screen_x = win.left + chrome_left_border + slider_vp_x
slider_screen_y = win.top + chrome_toolbar_height + slider_vp_y

print(f"Slider screen pos: ({slider_screen_x}, {slider_screen_y})")

# 3. 计算目标位置
# 从截图分析：右侧六边形缺口在图片约65%处
# 滑块轨道宽度约280px（从x=365到x=645在viewport中）
# 需要移动约 280*0.65 = 182px，但滑块已在393（轨道起点365+28）
# 所以还需移动约 182-28 = 154px
drag_distance = 160  # 略多一点容错

target_screen_x = slider_screen_x + drag_distance
target_screen_y = slider_screen_y

print(f"Target screen pos: ({target_screen_x}, {target_screen_y})")
print(f"Drag distance: {drag_distance}px")

# 4. 执行人类模式拖拽
print("Starting drag...")
pyautogui.moveTo(slider_screen_x, slider_screen_y, duration=0.3)
time.sleep(0.2)
pyautogui.mouseDown()
time.sleep(0.1)

# 分步移动模拟人类
import random
steps = 25
for i in range(1, steps + 1):
    progress = i / steps
    # 先快后慢的缓动
    eased = 1 - (1 - progress) ** 2
    x = slider_screen_x + drag_distance * eased
    y = slider_screen_y + random.uniform(-1, 1)
    pyautogui.moveTo(int(x), int(y), duration=0.02)

time.sleep(0.15)
pyautogui.mouseUp()
print("Drag completed!")
time.sleep(1)

# 5. 检查结果
print("Done. Check browser for result.")
