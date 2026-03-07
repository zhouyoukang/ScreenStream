"""Save VaM screenshot + full OCR dump for visual analysis"""
import sys
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
from vam import gui

hwnd = gui.find_vam_window()
gui.focus_window(hwnd)

img, wrect = gui.capture_printwindow(hwnd)
img.save(r"d:\道\道生一\一生二\VAM-agent\vam\tests\vam_current.png")
print(f"Saved: {img.size}, wrect={wrect}")

scan = gui.scan(hwnd=hwnd)
total = scan.get("total", 0)
print(f"Total: {total} texts")
for t in scan.get("texts", []):
    c = t["center"]
    print(f"  [{t['confidence']:.2f}] ({c['x']:5d},{c['y']:4d}) {t['text'][:50]}")
