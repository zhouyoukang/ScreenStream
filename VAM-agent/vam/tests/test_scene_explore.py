"""
VaM Scene Deep Exploration — enter edit mode, select atoms, explore editor panels
"""
import sys, time, json
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
import numpy as np, logging, pyautogui
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
from vam import gui

log = logging.getLogger("explore")

def ocr(img):
    engine = gui._get_ocr()
    s = 1.0
    if img.width > 960:
        s = 960/img.width; img = img.resize((960, int(img.height*s)))
    r, _ = engine(np.array(img))
    if not r: return []
    return [{"t": t.strip(), "x": int(sum(p[0] for p in b)/len(b)/s),
             "y": int(sum(p[1] for p in b)/len(b)/s), "c": round(c,2)}
            for b,t,c in r if c>0.3 and t.strip()]

def warm(hwnd, key=None, delay=1.0):
    return gui.warm_key_and_capture(key=key, hwnd=hwnd, delay=delay)

def click_cap(hwnd, ix, iy, wait=1.5):
    return gui.rapid_click_and_capture(ix, iy, hwnd=hwnd, wait=wait)

def pt(texts, n=30):
    for t in texts[:n]: print(f"    '{t['t']}' ({t['x']},{t['y']}) c={t['c']}")

def find(texts, target):
    for t in texts:
        if target.lower() in t["t"].lower(): return t
    return None

hwnd = gui.find_vam_window()
if not hwnd: print("❌ VaM not running"); sys.exit(1)
print(f"VaM hwnd={hwnd}")
fg0 = gui.user32.GetForegroundWindow()
m0 = pyautogui.position()

snapshots = {}

# ═══════════════════════════════════════════════════════
print("\n" + "="*55 + "\n  Phase 1: Current State Analysis\n" + "="*55)

img1, _ = warm(hwnd, delay=0.3)
t1 = ocr(img1)
print(f"  Raw: {len(t1)} texts")
pt(t1)
snapshots["P1_raw"] = [x["t"] for x in t1]

# Save screenshot for visual inspection
img1.save("vam_explore_p1_raw.png")
print("  → saved vam_explore_p1_raw.png")

# ═══════════════════════════════════════════════════════
print("\n" + "="*55 + "\n  Phase 2: Enter Edit Mode\n" + "="*55)

# Ensure UI visible
if len(t1) < 6:
    img_u, _ = warm(hwnd, key="u", delay=1.0)
    t_u = ocr(img_u)
    print(f"  After u: {len(t_u)} texts")
else:
    t_u = t1

# Click 编辑模式(E)
edit_btn = find(t_u, "编辑模式")
if edit_btn:
    print(f"  Clicking 编辑模式 at ({edit_btn['x']},{edit_btn['y']})")
    img2, _ = click_cap(hwnd, edit_btn["x"], edit_btn["y"], wait=2.0)
    t2 = ocr(img2)
    print(f"  After edit click: {len(t2)} texts")
    pt(t2)
    img2.save("vam_explore_p2_edit.png")
    snapshots["P2_edit"] = [x["t"] for x in t2]
else:
    print("  编辑模式 button not found, trying 'e' key")
    img2, _ = warm(hwnd, key="e", delay=2.0)
    t2 = ocr(img2)
    print(f"  After e: {len(t2)} texts")
    pt(t2)

# ═══════════════════════════════════════════════════════
print("\n" + "="*55 + "\n  Phase 3: Tab through atoms (cycle selection)\n" + "="*55)

prev_set = set(x["t"] for x in t2)
atom_snapshots = []

for i in range(6):  # Tab up to 6 times to cycle through atoms
    img_tab, _ = warm(hwnd, key="tab", delay=1.5)
    t_tab = ocr(img_tab)
    curr_set = set(x["t"] for x in t_tab)
    new = curr_set - prev_set
    lost = prev_set - curr_set
    
    print(f"\n  Tab×{i+1}: {len(t_tab)} texts | +{len(new)} new | -{len(lost)} lost")
    if new:
        print(f"    NEW: {list(new)[:8]}")
    pt(t_tab[:15])
    
    img_tab.save(f"vam_explore_p3_tab{i+1}.png")
    atom_snapshots.append({
        "tab": i+1, "total": len(t_tab),
        "texts": [x["t"] for x in t_tab[:30]],
        "new": list(new)[:10],
    })
    
    # If we find editor panels (Select/Control/etc.), we've selected an atom!
    found_panels = []
    for kw in ["Select", "Control", "Motion", "Clothing", "Hair", "Morph",
               "Plugin", "Animation", "Physics", "Appearance", "Skin",
               "Person", "Atom", "Light", "Camera",
               "选择", "控制", "动作", "外观"]:
        if find(t_tab, kw):
            found_panels.append(kw)
    
    if found_panels:
        print(f"    ⭐ EDITOR PANELS FOUND: {found_panels}")
        snapshots[f"P3_tab{i+1}_panels"] = [x["t"] for x in t_tab]
        break
    
    prev_set = curr_set

# ═══════════════════════════════════════════════════════
print("\n" + "="*55 + "\n  Phase 4: Click different viewport areas\n" + "="*55)

# Try clicking in various areas of the 3D viewport to select atoms
# VaM atoms are usually in the center-lower area of the viewport
click_targets = [
    (649, 500, "center-upper"),
    (649, 700, "center-mid"),  
    (649, 900, "center-lower"),
    (400, 700, "left-mid"),
    (900, 700, "right-mid"),
]

for cx, cy, label in click_targets:
    img_c, _ = click_cap(hwnd, cx, cy, wait=1.5)
    t_c = ocr(img_c)
    print(f"\n  Click {label} ({cx},{cy}): {len(t_c)} texts")
    
    # Check for new UI panels
    found = []
    for kw in ["Select", "Control", "Motion", "Clothing", "Plugin",
               "Person", "Atom", "Remove", "Add"]:
        if find(t_c, kw): found.append(kw)
    
    if found:
        print(f"    ⭐ PANELS: {found}")
        pt(t_c[:20])
        img_c.save(f"vam_explore_p4_{label}.png")
        snapshots[f"P4_{label}"] = [x["t"] for x in t_c]
        break
    
    if len(t_c) > 20:
        print(f"    ⭐ MANY TEXTS — possible panel!")
        pt(t_c[:20])
        img_c.save(f"vam_explore_p4_{label}.png")

# ═══════════════════════════════════════════════════════
print("\n" + "="*55 + "\n  Phase 5: Try F2 (atom selector) & other shortcuts\n" + "="*55)

# F2 in VaM might open the atom/controller selector
for key, desc in [("f2", "F2-atom?"), ("f3", "F3"), ("f4", "F4"),
                  ("ctrl+a", "Ctrl+A-select-all?"), ("ctrl+e", "Ctrl+E-editor?")]:
    img_k, _ = warm(hwnd, key=key, delay=1.5)
    t_k = ocr(img_k)
    print(f"\n  {desc}: {len(t_k)} texts")
    
    if len(t_k) > 20:
        print(f"    ⭐ MANY TEXTS!")
        pt(t_k[:15])
        img_k.save(f"vam_explore_p5_{key.replace('+','_')}.png")
        snapshots[f"P5_{key}"] = [x["t"] for x in t_k]
    
    # Check for new panels
    found = []
    for kw in ["Select", "Add", "Remove", "Person", "Atom", "Light", "Camera",
               "Scene", "Browser", "Load", "Save"]:
        if find(t_k, kw): found.append(kw)
    if found:
        print(f"    PANELS: {found}")

# ═══════════════════════════════════════════════════════
print("\n" + "="*55 + "\n  Phase 6: Restore & Verify\n" + "="*55)

# Press escape a few times to restore
for _ in range(3):
    warm(hwnd, key="escape", delay=0.3)
# Press p to return to play mode
warm(hwnd, key="p", delay=0.5)

fg1 = gui.user32.GetForegroundWindow()
m1 = pyautogui.position()
dx, dy = abs(m1.x-m0.x), abs(m1.y-m0.y)
print(f"  FG: {fg0}→{fg1} {'✅' if fg0==fg1 else '❌'}")
print(f"  Mouse: Δ({dx},{dy}) {'✅' if dx<=15 and dy<=15 else '❌'}")

# ═══════════════════════════════════════════════════════
print("\n" + "="*55 + "\n  Summary\n" + "="*55)

print(f"\n  Snapshots: {len(snapshots)}")
for name, texts in snapshots.items():
    print(f"    {name}: {len(texts)} texts → {texts[:5]}")

print(f"\n  Tab cycle results:")
for snap in atom_snapshots:
    print(f"    Tab×{snap['tab']}: {snap['total']} texts, new={snap['new'][:5]}")

# Save results
with open("vam_explore_results.json", "w", encoding="utf-8") as f:
    json.dump({"snapshots": snapshots, "tabs": atom_snapshots}, f, ensure_ascii=False, indent=2)
print(f"\n  → vam_explore_results.json + PNG screenshots saved")
