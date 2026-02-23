"""深度滚动采集 — 对已打开的订单页面持续滚动+dump"""
import subprocess, time, xml.etree.ElementTree as ET, os, re, sys
from datetime import datetime

ADB = r"e:\道\道生一\一生二\构建部署\android-sdk\platform-tools\adb.exe"
S = "158377ff"
LD = os.path.join(r"e:\道\道生一\一生二\手机操控库", "ui_dump.xml")

def a(*args, t=8):
    try:
        r = subprocess.run([ADB,"-s",S]+list(args), capture_output=True, text=True, timeout=t, encoding='utf-8', errors='replace')
        return r.stdout.strip()
    except: return ""

def get_texts():
    a("shell","uiautomator dump /sdcard/ui_dump.xml", t=5)
    a("pull", "/sdcard/ui_dump.xml", LD, t=3)
    try: root = ET.parse(LD).getroot()
    except: return []
    texts = []
    for n in root.iter("node"):
        for attr in ["text","content-desc"]:
            v = n.get(attr,"").strip()
            if v and len(v)>1: texts.append(v)
    return texts

def deep_scroll(name, max_scrolls=25, out_file=None):
    all_t, seen = [], set()
    empty_count = 0
    for i in range(max_scrolls+1):
        texts = get_texts()
        new = [t for t in texts if t not in seen and len(t)>1]
        seen.update(new)
        if new:
            all_t.append(f"\n--- {name} 第{i+1}屏 ({len(new)}条) ---")
            all_t.extend(new)
            print(f"[{i+1:2d}] +{len(new):3d}条 (总{len(all_t)})")
            empty_count = 0
        else:
            empty_count += 1
            print(f"[{i+1:2d}] 空屏 ({empty_count}/3)")
            if empty_count >= 3:
                print("连续3次无新内容，停止")
                break
        if i < max_scrolls:
            a("shell","input swipe 540 1800 540 600 400")
            time.sleep(1.5)
    
    if out_file:
        with open(out_file, "w", encoding="utf-8") as f:
            for l in all_t: f.write(f"{l}\n")
        print(f"💾 保存: {out_file} ({len(all_t)}行)")
    return all_t

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv)>1 else "订单"
    mx = int(sys.argv[2]) if len(sys.argv)>2 else 25
    out = os.path.join(r"e:\道\道生一\一生二\手机操控库", f"deep_{name}_{datetime.now().strftime('%H%M')}.txt")
    deep_scroll(name, mx, out)
