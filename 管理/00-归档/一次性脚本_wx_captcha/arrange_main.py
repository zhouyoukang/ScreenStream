"""将核心测试窗口全部拉到笔记本主屏幕(1920x1080, 坐标0,0)"""
import ctypes
import time
import subprocess
import pygetwindow as gw

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

# 主屏幕范围
MAIN = {'left': 0, 'top': 0, 'w': 1920, 'h': 1080}

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_SHOWWINDOW = 0x0040

def move_window(hwnd, x, y, w, h, topmost=False):
    """移动窗口到指定位置"""
    top_flag = HWND_TOPMOST if topmost else HWND_NOTOPMOST
    user32.SetWindowPos(hwnd, top_flag, x, y, w, h, SWP_SHOWWINDOW)

def find_window(keywords):
    """找包含关键词的窗口"""
    for w in gw.getAllWindows():
        title = w.title.lower()
        for kw in keywords:
            if kw.lower() in title:
                return w
    return None

print("=" * 50)
print("【主屏幕窗口布局方案】")
print("=" * 50)
print("""
  ┌─────────────────────────────────┐
  │  Windsurf IDE (左半屏)  │ 手机投屏  │
  │  1200 x 1080            │ 720x1080  │
  └─────────────────────────────────┘
  Chrome注册页 → Alt+Tab切换
""")

# === 1. 打开手机投屏页面到主屏幕 ===
print("\n[1] 打开手机投屏(ScreenStream :8086)...")
# 用已有的Chrome调试实例打开投屏页
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    opts.add_experimental_option("debuggerAddress", "127.0.0.1:9333")
    driver = webdriver.Chrome(options=opts)
    
    # 先检查当前页面
    current = driver.current_url
    print(f"  Chrome当前页: {current[:60]}")
    
    # 用JS在新标签打开投屏页
    driver.execute_script("window.open('http://localhost:8086', '_blank')")
    time.sleep(2)
    
    # 切到新标签
    handles = driver.window_handles
    if len(handles) > 1:
        driver.switch_to.window(handles[-1])
        print(f"  新标签: {driver.current_url}")
    
    print("  ✅ 投屏页已打开")
except Exception as e:
    print(f"  ⚠️ Selenium失败({e})，用subprocess打开")
    subprocess.Popen([
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--new-tab", "http://localhost:8086"
    ])
    time.sleep(2)

# === 2. 找到Chrome窗口并放到主屏幕右侧 ===
print("\n[2] 调整Chrome窗口到主屏幕...")
time.sleep(1)

# 找所有Chrome窗口
chrome_wins = [w for w in gw.getAllWindows() if "Chrome" in w.title and w.width > 100 and w.height > 100]
for w in chrome_wins:
    if w.left < -10000:
        continue
    print(f"  Chrome: {w.title[:50]} @ ({w.left},{w.top}) {w.width}x{w.height}")

# 找到最大的Chrome窗口（应该是我们的调试实例）
visible_chrome = [w for w in chrome_wins if w.left > -10000 and w.width > 400]
if visible_chrome:
    # 按面积排序
    visible_chrome.sort(key=lambda w: w.width * w.height, reverse=True)
    chrome = visible_chrome[0]
    hwnd = chrome._hWnd
    
    # 放到主屏幕右侧，作为手机投屏区 (720宽)
    move_window(hwnd, 1200, 0, 720, 1040)
    time.sleep(0.3)
    print(f"  ✅ Chrome移到主屏幕右侧: (1200,0) 720x1040")
else:
    print("  ⚠️ 没找到可见的Chrome窗口")

# === 3. Windsurf IDE放到主屏幕左侧 ===
print("\n[3] 调整Windsurf IDE到主屏幕左侧...")
ws = find_window(["windsurf", "screenstream_v2"])
if ws:
    hwnd = ws._hWnd
    move_window(hwnd, 0, 0, 1200, 1040)
    time.sleep(0.3)
    print(f"  ✅ Windsurf移到主屏幕左侧: (0,0) 1200x1040")
else:
    print("  ⚠️ 没找到Windsurf窗口")

# === 4. 其他窗口移到副屏 ===
print("\n[4] 非核心窗口移到副屏...")
SUB = {'left': -468, 'top': 1080}
other_wins = [w for w in gw.getAllWindows() 
              if w.title.strip() 
              and w.width > 100 and w.height > 100 
              and w.left > -10000
              and "windsurf" not in w.title.lower()
              and "chrome" not in w.title.lower()
              and "windows" not in w.title.lower()
              and "program manager" not in w.title.lower()
              and "rainmeter" not in w.title.lower()
              and "wv_" not in w.title.lower()]

for w in other_wins:
    if "媒体播放器" in w.title:
        # 媒体播放器移到副屏
        move_window(w._hWnd, SUB['left'] + 50, SUB['top'] + 50, 800, 600)
        print(f"  → 副屏: {w.title[:40]}")

# === 5. 最终状态检查 ===
print("\n" + "=" * 50)
print("【最终窗口布局】")
print("=" * 50)

time.sleep(0.5)
for w in gw.getAllWindows():
    if w.title.strip() and w.width > 100 and w.height > 100 and w.left > -10000:
        # 判断在哪个屏
        cx = w.left + w.width // 2
        cy = w.top + w.height // 2
        if 0 <= cx < 1920 and 0 <= cy < 1080:
            screen = "主屏"
        elif -468 <= cx < 972 and 1080 <= cy < 1980:
            screen = "副屏"
        else:
            screen = "其他"
        print(f"  [{screen}] {w.title[:45]:45s} ({w.left},{w.top}) {w.width}x{w.height}")

print("\n✅ 布局完成")
