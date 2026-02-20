"""
Desktop Automation MCP Server
=============================
Gives AI Agents "eyes + hands" for autonomous computer operation.

Eyes: screenshot, UI automation tree, screen info
Hands: mouse click/move/drag/scroll, keyboard type/hotkey, window management
Brain: composite actions (wait_and_click, screenshot_and_describe)

Protocol: MCP (Model Context Protocol) over stdio
Stack: FastMCP + pyautogui + pywinauto + mss + Pillow

Usage:
    python server.py                    # stdio mode (for MCP clients)
    python server.py --test             # quick self-test
"""

import base64
import ctypes
import io
import json
import os
import sys
import tempfile
import time
from typing import Optional

import mss
import pyautogui
from PIL import Image
from mcp.server.fastmcp import FastMCP

# === Config ===
pyautogui.FAILSAFE = False  # Agent needs full control, no corner-abort
pyautogui.PAUSE = 0.05      # Minimal inter-action delay

SCREENSHOT_DIR = os.path.join(tempfile.gettempdir(), "desktop-mcp")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

mcp_server = FastMCP(
    "desktop-automation",
    instructions=(
        "Desktop automation server. Use screenshot() to see the screen, "
        "get_ui_tree() to understand UI elements semantically, "
        "mouse/keyboard tools to interact. "
        "Typical workflow: screenshot → analyze → find_ui_element → click/type."
    ),
)


# ================================================================
# EYES: Screenshot & Screen Info
# ================================================================

@mcp_server.tool()
def screenshot(
    save_path: str = "",
    region: str = "",
    scale: float = 0.5,
    quality: int = 75,
) -> str:
    """
    Capture screenshot. Returns file path that Agent can view with read_file.

    Args:
        save_path: Where to save (auto-generated temp path if empty)
        region: Optional "x,y,width,height" for partial capture
        scale: Resize factor 0.1-1.0 (default 0.5, keeps size manageable)
        quality: JPEG quality 1-100 (default 75)
    """
    with mss.mss() as sct:
        if region:
            parts = [int(x.strip()) for x in region.split(",")]
            monitor = {"left": parts[0], "top": parts[1], "width": parts[2], "height": parts[3]}
        else:
            monitor = sct.monitors[0]

        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    orig_w, orig_h = img.size
    if 0 < scale < 1:
        img = img.resize((int(orig_w * scale), int(orig_h * scale)), Image.LANCZOS)

    if not save_path:
        save_path = os.path.join(SCREENSHOT_DIR, f"screen_{int(time.time() * 1000)}.jpg")

    img.save(save_path, format="JPEG", quality=quality)
    size_kb = round(os.path.getsize(save_path) / 1024, 1)

    return json.dumps({
        "path": save_path,
        "original_size": [orig_w, orig_h],
        "saved_size": [img.width, img.height],
        "file_size_kb": size_kb,
        "scale": scale,
    })


@mcp_server.tool()
def get_screen_size() -> str:
    """Get primary screen dimensions."""
    w, h = pyautogui.size()
    return json.dumps({"width": w, "height": h})


@mcp_server.tool()
def get_cursor_position() -> str:
    """Get current mouse cursor position."""
    x, y = pyautogui.position()
    return json.dumps({"x": x, "y": y})


# ================================================================
# HANDS: Mouse Control
# ================================================================

@mcp_server.tool()
def mouse_click(
    x: int,
    y: int,
    button: str = "left",
    clicks: int = 1,
) -> str:
    """
    Click at screen coordinates.

    Args:
        x, y: Screen coordinates
        button: "left", "right", or "middle"
        clicks: Number of clicks (2 = double-click)
    """
    pyautogui.click(x, y, clicks=clicks, button=button)
    return json.dumps({"action": "click", "x": x, "y": y, "button": button, "clicks": clicks})


@mcp_server.tool()
def mouse_move(x: int, y: int, duration: float = 0.2) -> str:
    """Move mouse cursor to coordinates."""
    pyautogui.moveTo(x, y, duration=duration)
    return json.dumps({"action": "move", "x": x, "y": y})


@mcp_server.tool()
def mouse_scroll(
    clicks: int,
    x: int = -1,
    y: int = -1,
) -> str:
    """
    Scroll mouse wheel. Positive = up, negative = down.

    Args:
        clicks: Scroll amount (positive=up, negative=down)
        x, y: Position to scroll at (-1 = current position)
    """
    if x >= 0 and y >= 0:
        pyautogui.scroll(clicks, x, y)
    else:
        pyautogui.scroll(clicks)
    return json.dumps({"action": "scroll", "clicks": clicks})


@mcp_server.tool()
def mouse_drag(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration: float = 0.5,
    button: str = "left",
) -> str:
    """Drag from start to end coordinates."""
    pyautogui.moveTo(start_x, start_y, duration=0.1)
    pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration, button=button)
    return json.dumps({"action": "drag", "from": [start_x, start_y], "to": [end_x, end_y]})


# ================================================================
# HANDS: Keyboard Control
# ================================================================

@mcp_server.tool()
def type_text(text: str, method: str = "auto") -> str:
    """
    Type text string.

    Args:
        text: Text to type
        method: "keyboard" (ASCII only, simulates keypresses),
                "clipboard" (any text, uses Ctrl+V),
                "auto" (keyboard for ASCII, clipboard for non-ASCII)
    """
    if method == "auto":
        method = "keyboard" if text.isascii() else "clipboard"

    if method == "keyboard":
        pyautogui.typewrite(text, interval=0.02)
    else:
        import pyperclip
        old_clip = pyperclip.paste()
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1)
        pyperclip.copy(old_clip)  # Restore clipboard

    return json.dumps({"action": "type", "method": method, "length": len(text)})


@mcp_server.tool()
def hotkey(keys: str) -> str:
    """
    Press a key combination.

    Args:
        keys: Keys joined by "+", e.g. "ctrl+s", "alt+tab", "ctrl+shift+p"
    """
    key_list = [k.strip() for k in keys.split("+")]
    pyautogui.hotkey(*key_list)
    return json.dumps({"action": "hotkey", "keys": key_list})


@mcp_server.tool()
def key_press(key: str, presses: int = 1) -> str:
    """
    Press a single key one or more times.
    Common keys: enter, tab, escape, space, backspace, delete,
                 up, down, left, right, home, end, pageup, pagedown,
                 f1-f12, insert, printscreen
    """
    pyautogui.press(key, presses=presses)
    return json.dumps({"action": "key_press", "key": key, "presses": presses})


# ================================================================
# WINDOW MANAGEMENT
# ================================================================

def _get_pywinauto_desktop():
    """Lazy import + create pywinauto Desktop."""
    from pywinauto import Desktop
    return Desktop(backend="uia")


def _get_foreground_window():
    """Get the foreground window as a pywinauto wrapper."""
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    from pywinauto import Application
    app = Application(backend="uia").connect(handle=hwnd)
    return app.window(handle=hwnd)


@mcp_server.tool()
def get_windows(include_rect: bool = True) -> str:
    """
    List all visible windows.

    Args:
        include_rect: Include window position/size (default True)
    """
    desktop = _get_pywinauto_desktop()
    windows = []
    for win in desktop.windows():
        try:
            title = win.window_text()
            if not title:
                continue
            entry = {"title": title, "handle": win.handle}
            if include_rect:
                r = win.rectangle()
                if r.width() > 0 and r.height() > 0:
                    entry["rect"] = {"x": r.left, "y": r.top, "w": r.width(), "h": r.height()}
                else:
                    continue
            windows.append(entry)
        except Exception:
            continue

    return json.dumps({"count": len(windows), "windows": windows[:50]}, ensure_ascii=False)


@mcp_server.tool()
def focus_window(title: str) -> str:
    """
    Bring a window to foreground by title (case-insensitive partial match).

    Args:
        title: Window title or substring
    """
    desktop = _get_pywinauto_desktop()
    for win in desktop.windows():
        try:
            wt = win.window_text()
            if title.lower() in wt.lower():
                win.set_focus()
                return json.dumps({"action": "focus", "title": wt, "success": True})
        except Exception:
            continue
    return json.dumps({"action": "focus", "title": title, "success": False, "error": "Not found"})


# ================================================================
# UI AUTOMATION TREE (Semantic Understanding)
# ================================================================

def _element_to_dict(elem, depth: int, max_depth: int, max_children: int):
    """Recursively convert UI element to dict."""
    if depth > max_depth:
        return None
    try:
        rect = elem.rectangle()
        node = {
            "name": elem.window_text()[:120],
            "type": elem.element_info.control_type,
            "rect": {"x": rect.left, "y": rect.top, "w": rect.width(), "h": rect.height()},
            "enabled": elem.is_enabled(),
        }
        aid = getattr(elem.element_info, "automation_id", "")
        if aid:
            node["id"] = aid[:60]

        children = []
        try:
            child_list = elem.children()
            for i, child in enumerate(child_list):
                if i >= max_children:
                    children.append({"_truncated": True, "remaining": len(child_list) - i})
                    break
                child_dict = _element_to_dict(child, depth + 1, max_depth, max_children)
                if child_dict:
                    children.append(child_dict)
        except Exception:
            pass

        if children:
            node["children"] = children
        return node
    except Exception:
        return None


@mcp_server.tool()
def get_ui_tree(
    window_title: str = "",
    max_depth: int = 3,
    max_children: int = 20,
) -> str:
    """
    Get UI Automation tree of a window. Returns hierarchical structure
    of UI elements with names, types, positions — like an accessibility tree.

    Args:
        window_title: Window to inspect (foreground window if empty)
        max_depth: Tree depth limit (default 3, max 6)
        max_children: Max children per node (default 20)
    """
    max_depth = min(max_depth, 6)

    try:
        if window_title:
            desktop = _get_pywinauto_desktop()
            target = None
            for win in desktop.windows():
                try:
                    if window_title.lower() in win.window_text().lower():
                        target = win
                        break
                except Exception:
                    continue
            if not target:
                return json.dumps({"error": f"Window '{window_title}' not found"})
        else:
            target = _get_foreground_window()

        tree = _element_to_dict(target, 0, max_depth, max_children)
        return json.dumps(
            {"window": target.window_text(), "tree": tree},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp_server.tool()
def find_ui_element(
    name: str = "",
    control_type: str = "",
    automation_id: str = "",
    window_title: str = "",
) -> str:
    """
    Search for UI elements matching criteria. Returns list with positions.

    Args:
        name: Element text (case-insensitive partial match)
        control_type: Element type: Button, Edit, TreeItem, TabItem, MenuItem, etc.
        automation_id: Automation ID (partial match)
        window_title: Window to search in (foreground if empty)
    """
    if not name and not control_type and not automation_id:
        return json.dumps({"error": "At least one search criterion required"})

    try:
        if window_title:
            desktop = _get_pywinauto_desktop()
            target = None
            for win in desktop.windows():
                try:
                    if window_title.lower() in win.window_text().lower():
                        target = win
                        break
                except Exception:
                    continue
            if not target:
                return json.dumps({"error": f"Window '{window_title}' not found"})
        else:
            target = _get_foreground_window()

        results = []

        def _search(elem, depth=0):
            if depth > 8 or len(results) >= 20:
                return
            try:
                text = elem.window_text()
                etype = elem.element_info.control_type
                aid = getattr(elem.element_info, "automation_id", "")

                match = True
                if name and name.lower() not in text.lower():
                    match = False
                if control_type and control_type.lower() != etype.lower():
                    match = False
                if automation_id and automation_id.lower() not in aid.lower():
                    match = False

                if match:
                    rect = elem.rectangle()
                    mid = rect.mid_point()
                    results.append({
                        "name": text[:120],
                        "type": etype,
                        "automation_id": aid[:60],
                        "rect": {"x": rect.left, "y": rect.top, "w": rect.width(), "h": rect.height()},
                        "center": {"x": mid.x, "y": mid.y},
                        "enabled": elem.is_enabled(),
                    })

                for child in elem.children():
                    _search(child, depth + 1)
            except Exception:
                pass

        _search(target)
        return json.dumps({"count": len(results), "elements": results}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp_server.tool()
def click_ui_element(
    name: str = "",
    control_type: str = "",
    automation_id: str = "",
    window_title: str = "",
) -> str:
    """
    Find a UI element by criteria and click its center.
    Same search logic as find_ui_element — clicks the first match.
    """
    result = json.loads(find_ui_element(name, control_type, automation_id, window_title))

    if "error" in result:
        return json.dumps(result)
    if result.get("count", 0) == 0:
        return json.dumps({"error": "Element not found", "criteria": {"name": name, "type": control_type}})

    elem = result["elements"][0]
    cx, cy = elem["center"]["x"], elem["center"]["y"]
    pyautogui.click(cx, cy)

    return json.dumps({
        "action": "click_element",
        "element": elem["name"],
        "type": elem["type"],
        "at": [cx, cy],
    })


# ================================================================
# COMPOSITE ACTIONS
# ================================================================

@mcp_server.tool()
def wait_and_click(
    name: str,
    timeout: int = 5,
    window_title: str = "",
) -> str:
    """
    Wait for a UI element to appear, then click it.

    Args:
        name: Element text to wait for
        timeout: Max seconds to wait (default 5)
        window_title: Window to search in
    """
    start = time.time()
    while time.time() - start < timeout:
        result = json.loads(find_ui_element(name=name, window_title=window_title))
        if result.get("count", 0) > 0:
            elem = result["elements"][0]
            cx, cy = elem["center"]["x"], elem["center"]["y"]
            pyautogui.click(cx, cy)
            return json.dumps({
                "action": "wait_and_click",
                "element": elem["name"],
                "at": [cx, cy],
                "waited_s": round(time.time() - start, 1),
            })
        time.sleep(0.5)

    return json.dumps({"error": f"Element '{name}' not found within {timeout}s"})


@mcp_server.tool()
def observe(
    window_title: str = "",
    screenshot_scale: float = 0.4,
) -> str:
    """
    Comprehensive observation: screenshot + UI tree + window info.
    The primary tool for Agent to understand current screen state.

    Returns: file path to screenshot + UI tree summary + foreground window info.
    """
    # Foreground window
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
    fg_title = buf.value

    # Screenshot
    shot = json.loads(screenshot(scale=screenshot_scale, quality=65))

    # UI tree (shallow for speed)
    tree = json.loads(get_ui_tree(
        window_title=window_title,
        max_depth=2,
        max_children=15,
    ))

    return json.dumps({
        "foreground_window": fg_title,
        "screenshot_path": shot["path"],
        "screenshot_size_kb": shot["file_size_kb"],
        "ui_tree": tree.get("tree", {}),
    }, ensure_ascii=False)


# ================================================================
# SELF-TEST
# ================================================================

def _self_test():
    """Quick self-test to verify all components work."""
    print("=== Desktop MCP Self-Test ===\n")

    # Screen size
    result = json.loads(get_screen_size())
    print(f"[OK] Screen: {result['width']}x{result['height']}")

    # Cursor
    result = json.loads(get_cursor_position())
    print(f"[OK] Cursor: ({result['x']}, {result['y']})")

    # Screenshot
    result = json.loads(screenshot(scale=0.3, quality=50))
    print(f"[OK] Screenshot: {result['path']} ({result['file_size_kb']} KB)")

    # Windows
    result = json.loads(get_windows())
    print(f"[OK] Windows: {result['count']} visible")
    for w in result["windows"][:5]:
        safe_title = w['title'][:60].encode('ascii', 'replace').decode()
        print(f"     - {safe_title}")

    # UI tree
    result = json.loads(get_ui_tree(max_depth=1, max_children=5))
    wt = result.get("window", "?")
    print(f"[OK] UI Tree: foreground = '{wt[:60]}'")

    print(f"\n=== All tests passed. Server ready. ===")
    print(f"Screenshot dir: {SCREENSHOT_DIR}")


# ================================================================
# ENTRY POINT
# ================================================================

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    else:
        mcp_server.run()
