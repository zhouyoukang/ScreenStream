"""Test rapid-flash capture for DirectX 3D scenes"""
import sys; sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
import numpy, logging, time
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
from vam import gui

hwnd = gui.find_vam_window()
print(f"hwnd={hwnd}")

# 1. PrintWindow capture (expected: black for 3D scene)
print("\n--- PrintWindow capture ---")
pw_img, pw_rect = gui.capture_printwindow(hwnd)
if pw_img:
    arr = numpy.array(pw_img)
    is_black = gui._is_black_image(pw_img)
    print(f"  Size: {pw_img.size}, Mean: {arr.mean():.1f}, Black: {is_black}")
    pw_img.save("diag_printwindow.png")

# 2. Rapid-flash capture (expected: actual 3D scene content)
print("\n--- Rapid-flash capture ---")
rf_img, rf_rect = gui.capture_rapid_flash(hwnd)
if rf_img:
    arr = numpy.array(rf_img)
    is_black = gui._is_black_image(rf_img)
    print(f"  Size: {rf_img.size}, Mean: {arr.mean():.1f}, Black: {is_black}")
    rf_img.save("diag_rapid_flash.png")
else:
    print("  Failed!")

# 3. Auto capture_window (should auto-select best method)
print("\n--- Auto capture_window ---")
auto_img, auto_rect = gui.capture_window(hwnd)
if auto_img:
    arr = numpy.array(auto_img)
    is_black = gui._is_black_image(auto_img)
    print(f"  Size: {auto_img.size}, Mean: {arr.mean():.1f}, Black: {is_black}")
    auto_img.save("diag_auto_capture.png")

# 4. OCR on rapid-flash capture
print("\n--- OCR on rapid-flash ---")
scan = gui.scan(hwnd=hwnd)
print(f"  Texts: {scan.get('total', 0)}")
for t in scan.get("texts", [])[:15]:
    ic = t.get("img_center", {})
    print(f'    "{t["text"]}" at ({ic.get("x","?")},{ic.get("y","?")})')

page = gui._detect_page([t["text"] for t in scan.get("texts", [])])
print(f"  Page: {page}")

# 5. Try pressing 'u' and rescan
print("\n--- Press 'u' + rescan ---")
gui._bg_key(hwnd, "u")
time.sleep(1.5)
scan2 = gui.scan(hwnd=hwnd)
print(f"  After u: {scan2.get('total', 0)} texts")
for t in scan2.get("texts", [])[:10]:
    print(f'    "{t["text"]}"')
page2 = gui._detect_page([t["text"] for t in scan2.get("texts", [])])
print(f"  Page: {page2}")

# Restore
gui._bg_key(hwnd, "u")
time.sleep(0.5)
