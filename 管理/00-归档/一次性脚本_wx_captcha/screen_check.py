"""双屏布局检测 + 窗口分布盘点"""
import ctypes
import ctypes.wintypes as wt
import pygetwindow as gw

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

# === 1. 屏幕信息 ===
print("=" * 60)
print("【屏幕布局】")
print("=" * 60)

vs_w = user32.GetSystemMetrics(78)
vs_h = user32.GetSystemMetrics(79)
print(f"虚拟桌面总尺寸: {vs_w}x{vs_h}")

monitors = []

def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
    class MONITORINFOEX(ctypes.Structure):
        _fields_ = [
            ('cbSize', ctypes.c_ulong),
            ('rcMonitor', wt.RECT),
            ('rcWork', wt.RECT),
            ('dwFlags', ctypes.c_ulong),
            ('szDevice', ctypes.c_wchar * 32)
        ]
    mi = MONITORINFOEX()
    mi.cbSize = ctypes.sizeof(MONITORINFOEX)
    user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi))
    m = mi.rcMonitor
    w = mi.rcWork
    monitors.append({
        'device': mi.szDevice,
        'primary': bool(mi.dwFlags & 1),
        'left': m.left, 'top': m.top,
        'right': m.right, 'bottom': m.bottom,
        'w': m.right - m.left, 'h': m.bottom - m.top,
        'work_left': w.left, 'work_top': w.top,
        'work_right': w.right, 'work_bottom': w.bottom,
    })
    return True

MONITORENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
    ctypes.POINTER(wt.RECT), ctypes.c_double
)
user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(callback), 0)

for i, m in enumerate(monitors):
    tag = "★主屏(笔记本)" if m['primary'] else "副屏(外接)"
    print(f"\n  Monitor {i} [{tag}]: {m['device']}")
    print(f"    分辨率: {m['w']}x{m['h']}")
    print(f"    坐标范围: ({m['left']},{m['top']}) → ({m['right']},{m['bottom']})")
    print(f"    工作区: ({m['work_left']},{m['work_top']}) → ({m['work_right']},{m['work_bottom']})")

# 判断屏幕相对位置
if len(monitors) >= 2:
    m0, m1 = monitors[0], monitors[1]
    if m1['top'] >= m0['bottom'] - 50:
        layout = "上下排列(主屏在上)"
    elif m0['top'] >= m1['bottom'] - 50:
        layout = "上下排列(主屏在下)"
    elif m1['left'] >= m0['right'] - 50:
        layout = "左右排列(主屏在左)"
    elif m0['left'] >= m1['right'] - 50:
        layout = "左右排列(主屏在右)"
    else:
        layout = "重叠或其他"
    print(f"\n  布局关系: {layout}")

# === 2. 窗口分布 ===
print("\n" + "=" * 60)
print("【窗口分布】")
print("=" * 60)

def get_monitor_name(x, y, w, h):
    """判断窗口在哪个屏幕"""
    cx = x + w // 2  # 窗口中心
    cy = y + h // 2
    for i, m in enumerate(monitors):
        if m['left'] <= cx < m['right'] and m['top'] <= cy < m['bottom']:
            return f"Monitor{i}({'主屏' if m['primary'] else '副屏'})"
    return "屏幕外"

all_wins = gw.getAllWindows()
visible_wins = [w for w in all_wins if w.width > 50 and w.height > 50 and w.left > -10000 and w.title.strip()]

# 按屏幕分组
main_wins = []
sub_wins = []
offscreen_wins = []

for w in visible_wins:
    loc = get_monitor_name(w.left, w.top, w.width, w.height)
    entry = f"  {w.title[:55]:55s} | {w.width:4d}x{w.height:<4d} @ ({w.left},{w.top})"
    if "主屏" in loc:
        main_wins.append(entry)
    elif "副屏" in loc:
        sub_wins.append(entry)
    else:
        offscreen_wins.append(entry)

print(f"\n--- 主屏幕窗口 ({len(main_wins)}个) ---")
for w in main_wins:
    print(w)

print(f"\n--- 副屏幕窗口 ({len(sub_wins)}个) ---")
for w in sub_wins:
    print(w)

if offscreen_wins:
    print(f"\n--- 屏幕外窗口 ({len(offscreen_wins)}个) ---")
    for w in offscreen_wins:
        print(w)

# === 3. 核心窗口识别 ===
print("\n" + "=" * 60)
print("【核心窗口状态】")
print("=" * 60)

keywords = {
    '微信/小程序注册': ['小程序', '微信公众平台', 'WeChat', 'waregister'],
    '手机控制': ['ScreenStream', 'Phone', 'ADB'],
    '录屏/ffmpeg': ['录屏', 'ffmpeg', 'OBS', 'screen record'],
    '二手书系统': ['二手书', 'localhost:8088'],
    '智能家居': ['智能家居', 'localhost:8900'],
    'Windsurf IDE': ['ScreenStream_v2', 'FINDINGS', 'Windsurf'],
    'Chrome浏览器': ['Chrome'],
}

for category, kws in keywords.items():
    matches = []
    for w in visible_wins:
        title = w.title.lower()
        for kw in kws:
            if kw.lower() in title:
                loc = get_monitor_name(w.left, w.top, w.width, w.height)
                matches.append(f"{w.title[:50]} → {loc}")
                break
    if matches:
        print(f"\n  {category}:")
        for m in matches:
            print(f"    {m}")
