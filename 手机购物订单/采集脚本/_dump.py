"""极简dump工具 — 显示当前屏幕所有文本"""
import xml.etree.ElementTree as ET, re, os, sys
TMP = os.path.join(os.environ.get("TEMP", "/tmp"), "ui.xml")
ADB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "构建部署", "android-sdk", "platform-tools", "adb.exe")
SN = "158377ff"

import subprocess
def adb(*a):
    try: return subprocess.run([ADB,"-s",SN]+list(a), capture_output=True, text=True, timeout=10, encoding='utf-8', errors='replace').stdout.strip()
    except: return ""

# dump
adb("shell", "uiautomator dump /sdcard/ui.xml")
adb("pull", "/sdcard/ui.xml", TMP)
try: root = ET.parse(TMP).getroot()
except: print("DUMP FAILED"); sys.exit(1)

items = []
for n in root.iter("node"):
    t = n.get("text","").strip()
    d = n.get("content-desc","").strip()
    v = t or d
    if not v or len(v) < 2: continue
    b = n.get("bounds","")
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
    if not m: continue
    x1,y1,x2,y2 = int(m[1]),int(m[2]),int(m[3]),int(m[4])
    cy = (y1+y2)//2
    cx = (x1+x2)//2
    cl = n.get("clickable","false")=="true"
    h = y2-y1
    items.append((cy, cx, cl, h, v))

for cy, cx, cl, h, v in sorted(items):
    flag = "C" if cl else " "
    print("{:4d} x={:4d} {} h={:3d} {}".format(cy, cx, flag, h, v[:60]))
