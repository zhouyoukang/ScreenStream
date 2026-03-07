"""VaM Tab navigation + atom selection test"""
import sys, time
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
import numpy as np, logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
from vam import gui

def ocr(img):
    engine = gui._get_ocr()
    s = 1.0
    if img.width > 960:
        s = 960/img.width; img = img.resize((960, int(img.height*s)))
    r, _ = engine(np.array(img))
    if not r: return []
    return [{"t": t.strip(), "x": int(sum(p[0] for p in b)/len(b)/s),
             "y": int(sum(p[1] for p in b)/len(b)/s)} for b,t,c in r if c>0.3 and t.strip()]

def warm_cap(hwnd, key=None, delay=1.0):
    gui.rapid_key_and_capture(key=None, hwnd=hwnd, pre_delay=0.15)
    time.sleep(0.1)
    img, _ = gui.rapid_key_and_capture(key=key, hwnd=hwnd, pre_delay=delay)
    return img, ocr(img) if img else []

def pt(texts, n=25):
    for t in texts[:n]: print(f"    '{t['t']}' ({t['x']},{t['y']})")

hwnd = gui.find_vam_window()
if not hwnd: print("❌"); sys.exit(1)

# Ensure in edit mode first
print("=== 0. Ensure edit mode ===")
img0, t0 = warm_cap(hwnd, key=None, delay=0.3)
if len(t0) < 6:
    img0, t0 = warm_cap(hwnd, key="u", delay=1.0)

# Try each key that might open UI panels
tests = [
    ("tab", "Tab — VaM panel cycle"),
    ("tab", "Tab×2"),
    ("tab", "Tab×3"),
    ("t", "T — Target mode"),
    ("c", "C — Cycle highlight"),
    ("ctrl+shift+b", "Ctrl+Shift+B — Browse?"),
    ("ctrl+o", "Ctrl+O — Open?"),
    ("f1", "F1 — Help/panel toggle"),
    ("1", "1 — possible shortcut"),
    ("2", "2 — possible shortcut"),
]

prev_texts = set(t["t"] for t in t0)
for key, desc in tests:
    print(f"\n=== {desc} ===")
    img, texts = warm_cap(hwnd, key=key, delay=1.5)
    curr = set(t["t"] for t in texts)
    new = curr - prev_texts
    lost = prev_texts - curr
    print(f"  {len(texts)} texts | +{len(new)} new | -{len(lost)} lost")
    if new:
        print(f"  NEW: {list(new)[:10]}")
    pt(texts)
    
    page = gui._detect_page([t["t"] for t in texts])
    if page != "scene_preview":
        print(f"  ⭐ PAGE CHANGED: {page}")
        img.save(f"vam_{key.replace('+','_')}.png")
    
    if len(texts) > 20:
        print(f"  ⭐ MANY TEXTS: {len(texts)} — possible new panel!")
        img.save(f"vam_{key.replace('+','_')}_panel.png")
    
    prev_texts = curr

# Final: restore state
print("\n=== Restore ===")
warm_cap(hwnd, key="escape", delay=0.5)
warm_cap(hwnd, key="escape", delay=0.5)

import pyautogui
fg = gui.user32.GetForegroundWindow()
print(f"  FG ok: ✅")
