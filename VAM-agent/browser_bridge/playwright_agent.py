"""
Playwright Desktop Agent — 通过浏览器桥接完全替代用户操作

☴ 巽 · AI感知层 — Playwright看到桌面应用的画面，像用户一样操作

道德经·上善若水: 适配任何桌面应用，无需了解内部API
释迦·中道: 不依赖脆弱的Win32 API，也不放弃精确控制

Usage:
    agent = DesktopAgent("http://localhost:9870")
    await agent.connect()
    await agent.click_text("编辑模式")    # OCR找到文字并点击
    await agent.press_key("tab")           # 发送按键
    await agent.screenshot("state.png")    # 截图保存
    texts = await agent.ocr_scan()         # OCR扫描所有文字
    await agent.close()
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("desktop_agent")


class DesktopAgent:
    """Control any desktop application through the Browser Bridge via Playwright."""

    def __init__(self, bridge_url: str = "http://localhost:9870",
                 headless: bool = True, ocr_engine=None):
        self.bridge_url = bridge_url
        self.headless = headless
        self._pw = None
        self._browser = None
        self._page = None
        self._ocr = ocr_engine  # External OCR engine (e.g., RapidOCR)
        self._canvas_selector = "#stream-canvas"

    async def connect(self, timeout: float = 15.0):
        """Launch browser and connect to the bridge."""
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.headless)
        self._page = await self._browser.new_page()

        await self._page.goto(self.bridge_url, timeout=int(timeout * 1000))
        # Wait for WebSocket connection
        await self._page.wait_for_function(
            "() => document.getElementById('dot').classList.contains('on')",
            timeout=int(timeout * 1000)
        )
        # Wait for first frame
        await asyncio.sleep(1.0)
        log.info("DesktopAgent connected to %s", self.bridge_url)

    async def close(self):
        """Clean up."""
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        log.info("DesktopAgent closed")

    # ── ☳ 震 · Actions ──

    async def click(self, x: float, y: float, button: str = "left"):
        """Click at relative position (0-1, 0-1) on the stream canvas."""
        canvas = self._page.locator(self._canvas_selector)
        box = await canvas.bounding_box()
        if not box:
            log.warning("Canvas not found")
            return
        px = box["x"] + x * box["width"]
        py = box["y"] + y * box["height"]
        await self._page.mouse.click(px, py, button=button)
        log.debug("click(%.3f, %.3f) → pixel(%d, %d)", x, y, px, py)

    async def click_pixel(self, px: int, py: int, button: str = "left"):
        """Click at pixel position on the stream canvas (in stream coordinates)."""
        canvas = self._page.locator(self._canvas_selector)
        box = await canvas.bounding_box()
        dims = await self._page.evaluate("""
            () => { const c = document.getElementById('stream-canvas');
                    return { w: c.width, h: c.height }; }
        """)
        if not box or not dims:
            return
        # Scale stream pixel to browser pixel
        scale_x = box["width"] / dims["w"]
        scale_y = box["height"] / dims["h"]
        bx = box["x"] + px * scale_x
        by = box["y"] + py * scale_y
        await self._page.mouse.click(bx, by, button=button)
        log.debug("click_pixel(%d, %d) → browser(%d, %d)", px, py, bx, by)

    async def double_click(self, x: float, y: float):
        """Double-click at relative position."""
        canvas = self._page.locator(self._canvas_selector)
        box = await canvas.bounding_box()
        if not box:
            return
        px = box["x"] + x * box["width"]
        py = box["y"] + y * box["height"]
        await self._page.mouse.dblclick(px, py)

    async def drag(self, x1: float, y1: float, x2: float, y2: float,
                   duration: float = 0.5):
        """Drag from (x1,y1) to (x2,y2) in relative coordinates."""
        canvas = self._page.locator(self._canvas_selector)
        box = await canvas.bounding_box()
        if not box:
            return
        sx = box["x"] + x1 * box["width"]
        sy = box["y"] + y1 * box["height"]
        ex = box["x"] + x2 * box["width"]
        ey = box["y"] + y2 * box["height"]

        await self._page.mouse.move(sx, sy)
        await self._page.mouse.down()
        steps = max(5, int(duration * 30))
        for i in range(1, steps + 1):
            t = i / steps
            mx = sx + (ex - sx) * t
            my = sy + (ey - sy) * t
            await self._page.mouse.move(mx, my)
            await asyncio.sleep(duration / steps)
        await self._page.mouse.up()

    async def scroll(self, x: float, y: float, delta: int):
        """Scroll at relative position. delta>0 = scroll up."""
        canvas = self._page.locator(self._canvas_selector)
        box = await canvas.bounding_box()
        if not box:
            return
        px = box["x"] + x * box["width"]
        py = box["y"] + y * box["height"]
        await self._page.mouse.move(px, py)
        await self._page.mouse.wheel(0, -delta * 40)

    # Playwright key name mapping (browser key names differ from our server VK names)
    _PW_KEY_MAP = {
        'f1': 'F1', 'f2': 'F2', 'f3': 'F3', 'f4': 'F4', 'f5': 'F5', 'f6': 'F6',
        'f7': 'F7', 'f8': 'F8', 'f9': 'F9', 'f10': 'F10', 'f11': 'F11', 'f12': 'F12',
        'enter': 'Enter', 'escape': 'Escape', 'tab': 'Tab', 'backspace': 'Backspace',
        'delete': 'Delete', 'home': 'Home', 'end': 'End', 'space': ' ',
        'pageup': 'PageUp', 'pagedown': 'PageDown', 'insert': 'Insert',
        'left': 'ArrowLeft', 'up': 'ArrowUp', 'right': 'ArrowRight', 'down': 'ArrowDown',
        'ctrl': 'Control', 'control': 'Control', 'shift': 'Shift', 'alt': 'Alt',
    }

    def _map_pw_key(self, key: str) -> str:
        """Map key names to Playwright format."""
        # Handle combos like "Control+z"
        if '+' in key:
            parts = key.split('+')
            return '+'.join(self._PW_KEY_MAP.get(p.lower(), p) for p in parts)
        return self._PW_KEY_MAP.get(key.lower(), key)

    async def press_key(self, key: str):
        """Press a key. Supports: 'a', 'Enter', 'F1', 'Control+z', etc."""
        # Focus canvas first
        await self._page.locator(self._canvas_selector).click()
        await asyncio.sleep(0.05)
        pw_key = self._map_pw_key(key)
        await self._page.keyboard.press(pw_key)
        log.debug("press_key('%s' → '%s')", key, pw_key)

    async def type_text(self, text: str, delay: float = 50):
        """Type text character by character."""
        await self._page.locator(self._canvas_selector).click()
        await asyncio.sleep(0.05)
        await self._page.keyboard.type(text, delay=delay)

    # ── ☴ 巽 · Perception (AI sensing) ──

    async def screenshot(self, path: str = None, full_page: bool = False) -> bytes:
        """Take a screenshot of the canvas (what the desktop app looks like)."""
        canvas = self._page.locator(self._canvas_selector)
        data = await canvas.screenshot(type="png")
        if path:
            Path(path).write_bytes(data)
            log.info("Screenshot saved: %s (%d bytes)", path, len(data))
        return data

    async def get_frame_as_numpy(self):
        """Get the current frame as a numpy array (BGR for OpenCV)."""
        import numpy as np
        from PIL import Image
        import io

        png_data = await self.screenshot()
        img = Image.open(io.BytesIO(png_data)).convert("RGB")
        arr = np.array(img)
        return arr[:, :, ::-1]  # RGB → BGR

    async def ocr_scan(self) -> List[Dict]:
        """OCR scan the current frame. Returns list of {text, x, y, confidence}."""
        import numpy as np

        if self._ocr is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._ocr = RapidOCR()
            except ImportError:
                log.error("RapidOCR not installed")
                return []

        frame = await self.get_frame_as_numpy()
        h, w = frame.shape[:2]

        # Downscale for speed
        scale = 1.0
        if w > 960 and cv2 is not None:
            scale = 960 / w
            frame = cv2.resize(frame, (960, int(h * scale)))

        result, _ = self._ocr(frame)
        if not result:
            return []

        texts = []
        for bbox, text, conf in result:
            if conf < 0.3 or not text.strip():
                continue
            cx = int(sum(p[0] for p in bbox) / len(bbox) / scale)
            cy = int(sum(p[1] for p in bbox) / len(bbox) / scale)
            texts.append({
                "text": text.strip(),
                "x": cx, "y": cy,
                "rx": cx / w, "ry": cy / h,  # relative coords for click
                "confidence": round(conf, 3),
            })
        return texts

    async def find_text(self, target: str, scan: List[Dict] = None) -> Optional[Dict]:
        """Find text matching target (case-insensitive substring)."""
        if scan is None:
            scan = await self.ocr_scan()
        target_lower = target.lower()
        for t in scan:
            if target_lower in t["text"].lower():
                return t
        return None

    async def click_text(self, target: str, wait: float = 1.0) -> bool:
        """Find text by OCR and click on it."""
        t = await self.find_text(target)
        if t:
            await self.click(t["rx"], t["ry"])
            log.info("click_text('%s') at (%.3f, %.3f)", target, t["rx"], t["ry"])
            await asyncio.sleep(wait)
            return True
        log.warning("click_text('%s') — not found", target)
        return False

    async def wait_for_text(self, target: str, timeout: float = 10.0,
                            interval: float = 0.5) -> Optional[Dict]:
        """Wait until target text appears on screen."""
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            t = await self.find_text(target)
            if t:
                return t
            await asyncio.sleep(interval)
        return None

    # ── ☶ 艮 · State Management ──

    async def get_status(self) -> dict:
        """Get bridge server status."""
        resp = await self._page.evaluate("""
            async () => {
                const r = await fetch('/api/status');
                return await r.json();
            }
        """)
        return resp

    async def set_target(self, hwnd: int = None, title: str = None,
                         class_name: str = None) -> dict:
        """Set the target window."""
        body = {}
        if hwnd:
            body["hwnd"] = hwnd
        if title:
            body["title"] = title
        if class_name:
            body["class"] = class_name

        resp = await self._page.evaluate("""
            async (body) => {
                const r = await fetch('/api/target', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body)
                });
                return await r.json();
            }
        """, body)
        return resp

    async def list_windows(self) -> list:
        """List available windows."""
        resp = await self._page.evaluate("""
            async () => {
                const r = await fetch('/api/windows');
                return await r.json();
            }
        """)
        return resp

    async def set_config(self, fps: int = None, quality: int = None):
        """Update stream configuration."""
        body = {}
        if fps is not None:
            body["fps"] = fps
        if quality is not None:
            body["quality"] = quality
        await self._page.evaluate("""
            async (body) => {
                await fetch('/api/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body)
                });
            }
        """, body)

    # ── ☰ 乾 · Window Management ──

    async def focus_target(self):
        """Bring VaM window to foreground."""
        return await self._api_post("/api/focus")

    async def restore_target(self):
        """Restore VaM from minimized."""
        return await self._api_post("/api/restore")

    async def _api_post(self, path: str, body: dict = None) -> dict:
        return await self._page.evaluate("""
            async ([path, body]) => {
                const r = await fetch(path, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: body ? JSON.stringify(body) : undefined
                });
                return await r.json();
            }
        """, [path, body or {}])

    # ── ☲ 离 · VaM Camera Control ──

    async def camera_orbit(self, dx: float, dy: float, duration: float = 0.3):
        """Orbit camera by right-click dragging. dx/dy in relative units (-1 to 1)."""
        cx, cy = 0.5, 0.5  # center of canvas
        canvas = self._page.locator(self._canvas_selector)
        box = await canvas.bounding_box()
        if not box:
            return
        sx = box["x"] + cx * box["width"]
        sy = box["y"] + cy * box["height"]
        ex = sx + dx * box["width"]
        ey = sy + dy * box["height"]

        await self._page.mouse.move(sx, sy)
        await self._page.mouse.down(button="right")
        steps = max(5, int(duration * 30))
        for i in range(1, steps + 1):
            t = i / steps
            await self._page.mouse.move(sx + (ex - sx) * t, sy + (ey - sy) * t)
            await asyncio.sleep(duration / steps)
        await self._page.mouse.up(button="right")
        log.debug("camera_orbit(dx=%.2f, dy=%.2f)", dx, dy)

    async def camera_pan(self, dx: float, dy: float, duration: float = 0.3):
        """Pan camera by middle-click dragging."""
        canvas = self._page.locator(self._canvas_selector)
        box = await canvas.bounding_box()
        if not box:
            return
        sx = box["x"] + 0.5 * box["width"]
        sy = box["y"] + 0.5 * box["height"]
        ex = sx + dx * box["width"]
        ey = sy + dy * box["height"]

        await self._page.mouse.move(sx, sy)
        await self._page.mouse.down(button="middle")
        steps = max(5, int(duration * 30))
        for i in range(1, steps + 1):
            t = i / steps
            await self._page.mouse.move(sx + (ex - sx) * t, sy + (ey - sy) * t)
            await asyncio.sleep(duration / steps)
        await self._page.mouse.up(button="middle")
        log.debug("camera_pan(dx=%.2f, dy=%.2f)", dx, dy)

    async def camera_zoom(self, delta: int):
        """Zoom camera. delta>0 = zoom in, delta<0 = zoom out."""
        await self.scroll(0.5, 0.5, delta)
        log.debug("camera_zoom(%d)", delta)

    # ── ☴ 巽 · VaM State Detection ──

    VAM_STATES = {
        "scene_preview": ["VaM"],
        "edit_mode": ["选择焦点", "重设焦点", "Select", "Motion"],
        "play_mode": ["游玩模式", "Play Mode"],
        "main_menu": ["SCENES", "场景"],
        "loading": ["Loading", "加载"],
    }

    async def detect_state(self, scan: List[Dict] = None) -> str:
        """Detect current VaM UI state from OCR results."""
        if scan is None:
            scan = await self.ocr_scan()
        texts_lower = {t["text"].lower() for t in scan}
        all_text = " ".join(texts_lower)

        if any(kw in all_text for kw in ["选择焦点", "重设焦点", "select focus", "reset focus"]):
            return "edit_mode"
        if any(kw in all_text for kw in ["loading", "加载"]):
            return "loading"
        if any(kw in all_text for kw in ["scenes", "场景浏览"]):
            return "main_menu"
        if any(kw in all_text for kw in ["游玩模式", "play mode"]):
            return "play_mode"
        if any(kw in all_text for kw in ["vam", "编辑模式", "edit mode"]):
            return "scene_preview"
        return "unknown"

    async def get_visible_texts(self) -> List[str]:
        """Get list of all visible text strings."""
        scan = await self.ocr_scan()
        return [t["text"] for t in scan]

    # ── ☳ 震 · VaM Actions ──

    async def toggle_ui(self, wait: float = 0.5):
        """Toggle VaM UI overlay (u key)."""
        await self.press_key("u")
        await asyncio.sleep(wait)

    async def enter_edit_mode(self, wait: float = 1.0):
        """Enter edit mode (e key or click)."""
        if await self.click_text("编辑模式", wait=wait):
            return True
        if await self.click_text("Edit Mode", wait=wait):
            return True
        await self.press_key("e")
        await asyncio.sleep(wait)
        return True

    async def enter_play_mode(self, wait: float = 1.0):
        """Enter play mode (p key or click)."""
        if await self.click_text("游玩模式", wait=wait):
            return True
        if await self.click_text("Play Mode", wait=wait):
            return True
        await self.press_key("p")
        await asyncio.sleep(wait)
        return True

    async def toggle_freeze(self):
        """Toggle freeze motion/sound (f key)."""
        await self.press_key("f")
        await asyncio.sleep(0.3)

    async def undo(self):
        """Undo (Ctrl+Z)."""
        await self.press_key("Control+z")
        await asyncio.sleep(0.3)

    async def redo(self):
        """Redo (Ctrl+Shift+Z)."""
        await self.press_key("Control+Shift+z")
        await asyncio.sleep(0.3)

    async def cycle_tab_focus(self, times: int = 1):
        """Cycle focus through atoms (Tab key)."""
        for _ in range(times):
            await self.press_key("Tab")
            await asyncio.sleep(0.3)

    async def escape(self):
        """Press Escape (back/cancel in VaM)."""
        await self.press_key("Escape")
        await asyncio.sleep(0.3)

    async def select_atom_by_click(self, x: float, y: float):
        """Click to select an atom at relative position."""
        await self.click(x, y)
        await asyncio.sleep(0.5)

    async def move_atom_drag(self, x1: float, y1: float, x2: float, y2: float):
        """Drag an atom from one position to another."""
        await self.drag(x1, y1, x2, y2, duration=0.5)
        await asyncio.sleep(0.3)

    # ── ☶ 艮 · Batch Operations ──

    async def full_scan(self) -> dict:
        """Complete scan: screenshot + OCR + state detection."""
        scan = await self.ocr_scan()
        state = await self.detect_state(scan)
        status = await self.get_status()
        return {
            "state": state,
            "texts": [t["text"] for t in scan],
            "text_count": len(scan),
            "scan": scan,
            "status": status,
        }

    async def wait_for_state(self, target_state: str, timeout: float = 30.0,
                              interval: float = 1.0) -> bool:
        """Wait until VaM reaches a specific state."""
        import time as _time
        deadline = _time.monotonic() + timeout
        while _time.monotonic() < deadline:
            state = await self.detect_state()
            if state == target_state:
                return True
            await asyncio.sleep(interval)
        return False


# ── Convenience for import cv2 at top level ──
try:
    import cv2
except ImportError:
    cv2 = None


# ════════════════════════════════════════════════════
#  Quick test
# ════════════════════════════════════════════════════

async def main():
    """Quick test: connect, screenshot, OCR scan."""
    logging.basicConfig(level=logging.INFO)
    agent = DesktopAgent(headless=False)  # Show browser for visual verification

    try:
        await agent.connect()
        print("✅ Connected")

        status = await agent.get_status()
        print(f"📊 Status: {json.dumps(status, indent=2)}")

        await asyncio.sleep(2)  # Let some frames arrive

        # OCR scan
        texts = await agent.ocr_scan()
        print(f"\n📝 OCR: {len(texts)} texts found")
        for t in texts[:20]:
            print(f"  '{t['text']}' ({t['x']},{t['y']}) conf={t['confidence']}")

        # Screenshot
        await agent.screenshot("bridge_test.png")
        print("\n📸 Screenshot saved: bridge_test.png")

        # Try clicking VaM edit mode
        if await agent.click_text("编辑模式"):
            print("✅ Clicked 编辑模式")
            await asyncio.sleep(2)
            texts2 = await agent.ocr_scan()
            print(f"📝 After edit: {len(texts2)} texts")
        else:
            print("⚠️ 编辑模式 not found")

        input("Press Enter to close...")

    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
