"""找到所有Chrome窗口（包括最小化的）并将调试实例拉到主屏幕"""
import ctypes
import ctypes.wintypes as wt
import time
import pygetwindow as gw
import urllib.request
import json

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

SWP_SHOWWINDOW = 0x0040
SW_RESTORE = 9
SW_SHOW = 5

print("=== 1. 查找所有Chrome窗口(含最小化) ===")
all_wins = gw.getAllWindows()
chrome_wins = [w for w in all_wins if "Chrome" in w.title]
for w in chrome_wins:
    state = "最小化" if w.left < -10000 else f"({w.left},{w.top}) {w.width}x{w.height}"
    print(f"  {w.title[:55]} | {state}")

print(f"\n  共 {len(chrome_wins)} 个Chrome窗口")

# 找到包含'小程序'或调试实例的窗口
target = None
for w in chrome_wins:
    if "小程序" in w.title and w.left > -10000:
        target = w
        break

if not target:
    # 找最小化的小程序窗口
    for w in chrome_wins:
        if "小程序" in w.title:
            target = w
            break

if not target:
    # 找任何非最小化的大Chrome窗口
    for w in chrome_wins:
        if w.left > -10000 and w.width > 400:
            target = w
            break

if target:
    print(f"\n=== 2. 恢复并定位Chrome窗口 ===")
    print(f"  目标: {target.title[:55]}")
    hwnd = target._hWnd
    
    # 恢复窗口
    user32.ShowWindow(hwnd, SW_RESTORE)
    time.sleep(0.3)
    
    # 移动到主屏幕右侧
    user32.SetWindowPos(hwnd, 0, 1200, 0, 720, 1040, SWP_SHOWWINDOW)
    time.sleep(0.3)
    
    # 激活
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    
    # 验证位置
    target = gw.getWindowsWithTitle(target.title[:20])[0]
    print(f"  新位置: ({target.left},{target.top}) {target.width}x{target.height}")
    print("  ✅ Chrome已拉到主屏幕右侧")
else:
    print("  ⚠️ 没找到目标Chrome窗口，尝试通过调试端口恢复")
    try:
        resp = urllib.request.urlopen("http://localhost:9333/json")
        pages = json.loads(resp.read())
        print(f"  调试端口9333有 {len(pages)} 个页面:")
        for p in pages:
            print(f"    {p.get('title','')[:40]} | {p.get('url','')[:60]}")
    except Exception as e:
        print(f"  调试端口不可用: {e}")

# === 3. 检查手机状态 ===
print(f"\n=== 3. 检查手机状态(ScreenStream :8086) ===")
try:
    resp = urllib.request.urlopen("http://localhost:8086/api/v1/status", timeout=3)
    data = json.loads(resp.read())
    print(f"  状态: {json.dumps(data, ensure_ascii=False, indent=2)[:300]}")
except Exception as e:
    # 尝试其他端点
    try:
        resp = urllib.request.urlopen("http://localhost:8086/status", timeout=3)
        print(f"  /status: {resp.read().decode()[:200]}")
    except:
        try:
            resp = urllib.request.urlopen("http://localhost:8086/", timeout=3)
            ct = resp.headers.get("Content-Type", "")
            size = len(resp.read())
            print(f"  / 响应: Content-Type={ct}, size={size} bytes")
        except Exception as e2:
            print(f"  连接失败: {e2}")

# === 4. 截图确认 ===
print(f"\n=== 4. 截图确认主屏幕 ===")
import pyautogui
img = pyautogui.screenshot("E:/github/AIOT/ScreenStream_v2/main_final.png")
print(f"  截图已保存: {img.size}")
