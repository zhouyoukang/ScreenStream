"""最终布局：主屏三栏 + 投屏检测 + 截图确认"""
import ctypes
import time
import urllib.request
import pygetwindow as gw
import pyautogui

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()
SWP = 0x0040  # SWP_SHOWWINDOW
SW_RESTORE = 9

# === 主屏布局 (1920x1080) ===
# 左: Windsurf 640px | 中: Chrome注册 640px | 右: 投屏 640px
# 如果投屏窗口不可用就用左右分屏

print("=" * 50)
print("【整理主屏幕布局】")
print("=" * 50)

def find_and_place(keywords, x, y, w, h, label):
    for win in gw.getAllWindows():
        title = win.title.lower()
        for kw in keywords:
            if kw.lower() in title:
                hwnd = win._hWnd
                user32.ShowWindow(hwnd, SW_RESTORE)
                time.sleep(0.15)
                user32.SetWindowPos(hwnd, 0, x, y, w, h, SWP)
                print(f"  {label}: {win.title[:45]} → ({x},{y}) {w}x{h}")
                return True
    return False

# Windsurf → 左侧
find_and_place(["windsurf", "screenstream_v2 -"], 0, 0, 660, 1040, "左栏IDE")

# Chrome注册页 → 中间
found_chrome = False
for w in gw.getAllWindows():
    if "小程序" in w.title and "Chrome" in w.title:
        hwnd = w._hWnd
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.15)
        user32.SetWindowPos(hwnd, 0, 660, 0, 640, 1040, SWP)
        print(f"  中栏注册: {w.title[:45]} → (660,0) 640x1040")
        found_chrome = True
        break

# ScreenStream投屏 → 右侧
found_ss = False
for w in gw.getAllWindows():
    t = w.title.lower()
    if ("localhost" in t or "screenstream" in t or "8086" in t) and w.title != "" and w.width > 50:
        if "windsurf" not in t and "chrome" not in t:
            hwnd = w._hWnd
            user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.15)
            user32.SetWindowPos(hwnd, 0, 1300, 0, 620, 1040, SWP)
            print(f"  右栏投屏: {w.title[:45]} → (1300,0) 620x1040")
            found_ss = True
            break

if not found_ss:
    # 找app模式的窗口（标题可能是localhost:8086）
    for w in gw.getAllWindows():
        if w.left > -10000 and w.width > 300 and w.height > 600:
            if "chrome" not in w.title.lower() and "windsurf" not in w.title.lower():
                if "小程序" not in w.title:
                    hwnd = w._hWnd
                    user32.ShowWindow(hwnd, SW_RESTORE)
                    time.sleep(0.15)
                    user32.SetWindowPos(hwnd, 0, 1300, 0, 620, 1040, SWP)
                    print(f"  右栏(推测投屏): {w.title[:45]} → (1300,0) 620x1040")
                    found_ss = True
                    break

# === 检测投屏流 ===
print("\n" + "=" * 50)
print("【投屏流检测】")
print("=" * 50)

# 检查MJPEG流 (8081)
try:
    req = urllib.request.Request("http://localhost:8081", method="GET")
    resp = urllib.request.urlopen(req, timeout=3)
    ct = resp.headers.get("Content-Type", "")
    data = resp.read(1024)
    print(f"  :8081 MJPEG → Content-Type: {ct}, 首字节: {len(data)}")
    if "multipart" in ct or "image" in ct:
        print("  ✅ MJPEG流正常，可在浏览器直接打开 http://localhost:8081")
    else:
        print(f"  ⚠️ 响应类型非MJPEG: {ct}")
except Exception as e:
    print(f"  :8081 → {e}")

# 检查ScreenStream主页 (8086)
try:
    resp = urllib.request.urlopen("http://localhost:8086", timeout=3)
    ct = resp.headers.get("Content-Type", "")
    size = len(resp.read())
    print(f"  :8086 主页 → Content-Type: {ct}, size: {size}B")
except Exception as e:
    print(f"  :8086 → {e}")

# 状态
try:
    resp = urllib.request.urlopen("http://localhost:8086/status", timeout=3)
    print(f"  :8086/status → {resp.read().decode()[:200]}")
except:
    pass

# === 最终截图 ===
print("\n" + "=" * 50)
print("【截图确认】")
print("=" * 50)
time.sleep(0.5)
pyautogui.screenshot("E:/github/AIOT/ScreenStream_v2/main_final.png")
print("  主屏截图: main_final.png")

# 窗口最终状态
print("\n【最终窗口列表】")
for w in gw.getAllWindows():
    if w.title.strip() and w.width > 100 and w.height > 100 and w.left > -10000:
        cx = w.left + w.width // 2
        cy = w.top + w.height // 2
        if 0 <= cx < 1920 and 0 <= cy < 1080:
            zone = "主屏"
        elif -468 <= cx < 972 and 1080 <= cy < 1980:
            zone = "副屏"
        else:
            zone = "其他"
        print(f"  [{zone}] {w.title[:40]:40s} ({w.left},{w.top}) {w.width}x{w.height}")
