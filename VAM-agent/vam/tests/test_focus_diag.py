"""Quick diagnostic: focus + state detection"""
import sys, time
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
from vam import gui

hwnd = gui.find_vam_window()
if not hwnd:
    print("No VaM window"); sys.exit(1)

info = gui.get_window_info(hwnd)
print(f"hwnd={hwnd}, title={info['title']}, size={info['rect']['w']}x{info['rect']['h']}")

# Test focus with new multi-strategy approach
result = gui.focus_window(hwnd)
print(f"Focus: {result}")
time.sleep(0.5)

# Verify state
state = gui.get_vam_state()
page = state["detected_page"]
focused = state["focused"]
texts = state["screen_texts"][:8]
print(f"Page: {page}, Focused: {focused}")
print(f"Texts ({len(state['screen_texts'])}): {texts}")

# Try clicking "Create" if at main_menu, or navigate back first
if page == "scene_browser":
    print("\nIn scene_browser, trying to click 'Create' tab to go to editor...")
    r = gui.click_text("Create")
    if not r.get("ok"):
        r = gui.click_text("场景")
    print(f"Click result: {r}")
    time.sleep(2)
    state2 = gui.get_vam_state()
    print(f"After click: page={state2['detected_page']}")
    print(f"Texts: {state2['screen_texts'][:8]}")
elif page == "main_menu":
    print("\nAt main_menu, all good!")
