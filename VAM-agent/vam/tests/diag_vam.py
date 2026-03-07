"""Quick VaM state diagnostic"""
import sys; sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
import numpy, logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
from vam import gui
import ctypes.wintypes as wt

hwnd = gui.find_vam_window()
print(f"hwnd={hwnd}")

# 1. Screenshot
img, rect = gui.capture_printwindow(hwnd)
if img:
    w, h = img.size
    print(f"Screenshot: {w}x{h}")
    img.save("vam_diag.png")
    arr = numpy.array(img)
    print(f"Mean brightness: {arr.mean():.1f}")
    print(f"Top 50px: {arr[:50,:,:].mean():.1f}")
    print(f"Bottom 50px: {arr[-50:,:,:].mean():.1f}")

# 2. OCR
scan = gui.scan(hwnd=hwnd)
print(f"\nOCR: {scan.get('total', 0)} texts")
for t in scan.get("texts", []):
    ic = t.get("img_center", {})
    conf = t.get("confidence", 0)
    print(f'  "{t["text"]}" at ({ic.get("x","?")},{ic.get("y","?")}) conf={conf:.2f}')

# 3. Window state
r = wt.RECT()
gui.user32.GetWindowRect(hwnd, gui.ctypes.byref(r))
print(f"\nWindow: ({r.left},{r.top}) to ({r.right},{r.bottom})")
print(f"IsIconic: {gui.user32.IsIconic(hwnd)}")
print(f"IsVisible: {gui.user32.IsWindowVisible(hwnd)}")
fg = gui.user32.GetForegroundWindow()
print(f"Foreground: {fg} (VaM={'yes' if fg==hwnd else 'no'})")

# 4. Try clicking center then pressing u
print("\n--- Try: click center → u ---")
cx, cy = rect["w"]//2, rect["h"]//2
print(f"Click center: img({cx},{cy})")
gui._bg_click(hwnd, cx, cy)
import time; time.sleep(0.5)

gui._bg_key(hwnd, "u")
time.sleep(1.5)

scan2 = gui.scan(hwnd=hwnd)
print(f"After click+u: {scan2.get('total', 0)} texts")
for t in scan2.get("texts", [])[:10]:
    print(f'  "{t["text"]}"')

# 5. Try u again to restore
gui._bg_key(hwnd, "u")
time.sleep(0.5)
scan3 = gui.scan(hwnd=hwnd)
print(f"After u again: {scan3.get('total', 0)} texts")
