"""环境全景检测：进程/端口/ADB/窗口"""
import subprocess
import socket
import pygetwindow as gw

print("=" * 60)
print("【关键进程】")
print("=" * 60)

for name in ["ffmpeg.exe", "python.exe", "adb.exe"]:
    try:
        out = subprocess.check_output(
            f'tasklist /FI "IMAGENAME eq {name}" /FO CSV /NH',
            shell=True
        ).decode("gbk", "ignore").strip()
        count = out.count(name)
        if count:
            print(f"  {name}: {count}个进程")
        else:
            print(f"  {name}: 无")
    except:
        print(f"  {name}: 检测失败")

# Chrome进程数
try:
    out = subprocess.check_output(
        'tasklist /FI "IMAGENAME eq chrome.exe" /FO CSV /NH',
        shell=True
    ).decode("gbk", "ignore").strip()
    print(f"  chrome.exe: {out.count('chrome.exe')}个进程")
except:
    pass

print("\n" + "=" * 60)
print("【端口状态】")
print("=" * 60)

ports = {
    8080: "Gateway",
    8081: "MJPEG",
    8086: "ScreenStream",
    8088: "二手书系统",
    8900: "智能家居",
    9333: "Chrome调试",
}
for port, name in ports.items():
    s = socket.socket()
    s.settimeout(0.3)
    try:
        s.connect(("127.0.0.1", port))
        print(f"  :{port} {name:12s} ✅ 在线")
        s.close()
    except:
        print(f"  :{port} {name:12s} ❌ 离线")

print("\n" + "=" * 60)
print("【ADB设备】")
print("=" * 60)
try:
    adb = subprocess.check_output("adb devices -l", shell=True).decode().strip()
    print(adb)
except Exception as e:
    print(f"ADB不可用: {e}")

print("\n" + "=" * 60)
print("【录屏状态】")
print("=" * 60)
import os
rec_dirs = [
    r"d:\屏幕录制\realtime_session",
    r"d:\屏幕录制\v4_session",
]
for d in rec_dirs:
    if os.path.exists(d):
        files = sorted(os.listdir(d), key=lambda f: os.path.getmtime(os.path.join(d, f)), reverse=True)[:5]
        print(f"\n  {d}:")
        for f in files:
            fp = os.path.join(d, f)
            size = os.path.getsize(fp) / 1024 / 1024
            print(f"    {f:40s} {size:8.1f} MB")
    else:
        print(f"  {d}: 不存在")

print("\n" + "=" * 60)
print("【用户五感体验分析】")
print("=" * 60)
print("""
  👁️ 视觉：
    - 主屏(笔记本1920x1080)在上方 → 核心操作区
    - 副屏(外接1440x900)在下方 → 辅助/参考区
    - 当前主屏只有Windsurf IDE和媒体播放器
    
  🖱️ 触觉/操作：
    - 鼠标从主屏底部穿越到副屏顶部
    - 笔记本键盘+触控板是主输入设备
    
  👂 听觉：
    - Senary Audio麦克风阵列
    - Logi C270摄像头自带麦克风
    - 3条Virtual Audio Cable虚拟音频线
    
  📹 摄像头：
    - Logi C270 HD WebCam (外置)
    - USB Camera (可能是手机/其他)
""")
