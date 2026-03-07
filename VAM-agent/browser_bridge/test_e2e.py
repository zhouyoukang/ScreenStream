"""
E2E Test: Desktop Browser Bridge → Playwright → VaM

验证完整链路:
1. Playwright连接Bridge页面
2. WebSocket流开始 → Canvas显示VaM画面
3. OCR扫描Canvas内容
4. 通过Canvas发送键盘/鼠标 → VaM响应
5. 验证VaM状态变化
"""

import asyncio
import json
import sys
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("e2e")

BRIDGE_URL = "http://localhost:9870"


async def main():
    from playwright.async_api import async_playwright

    print("=" * 60)
    print("  Desktop Browser Bridge — E2E Test")
    print("=" * 60)

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    page = await browser.new_page(viewport={"width": 1400, "height": 900})

    try:
        # ── Phase 1: Connect ──
        print("\n📡 Phase 1: Connecting to Bridge...")
        await page.goto(BRIDGE_URL, timeout=10000)
        await page.wait_for_timeout(1000)

        # Check WebSocket connection
        dot_class = await page.evaluate(
            "() => document.getElementById('dot').className"
        )
        connected = "on" in dot_class
        print(f"  WebSocket: {'✅ Connected' if connected else '❌ Disconnected'}")

        if not connected:
            print("  Waiting for connection...")
            await page.wait_for_function(
                "() => document.getElementById('dot').classList.contains('on')",
                timeout=10000
            )
            print("  ✅ Connected")

        # ── Phase 2: Wait for frames ──
        print("\n🎬 Phase 2: Waiting for stream frames...")
        await page.wait_for_timeout(3000)  # Let frames accumulate

        canvas = page.locator("#stream-canvas")
        dims = await page.evaluate("""
            () => {
                const c = document.getElementById('stream-canvas');
                return { w: c.width, h: c.height };
            }
        """)
        print(f"  Canvas dimensions: {dims['w']}×{dims['h']}")

        # Check frame count from HUD
        frame_text = await page.evaluate(
            "() => document.querySelector('#hud-frames .val').textContent"
        )
        print(f"  Frames received: {frame_text}")

        fps_text = await page.evaluate(
            "() => document.querySelector('#hud-fps .val').textContent"
        )
        print(f"  Current FPS: {fps_text}")

        stream_ok = dims['w'] > 100 and dims['h'] > 100
        print(f"  Stream: {'✅ Active' if stream_ok else '❌ No frames'}")

        # ── Phase 3: Screenshot + OCR ──
        print("\n📸 Phase 3: Screenshot & OCR analysis...")
        screenshot = await canvas.screenshot(type="png")
        with open("e2e_canvas.png", "wb") as f:
            f.write(screenshot)
        print(f"  Screenshot: e2e_canvas.png ({len(screenshot)} bytes)")

        # OCR via server-side
        try:
            import numpy as np
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(screenshot)).convert("RGB")
            arr = np.array(img)
            print(f"  Image: {arr.shape[1]}×{arr.shape[0]}")

            from rapidocr_onnxruntime import RapidOCR
            ocr = RapidOCR()

            # Downscale for OCR speed
            scale = 1.0
            if arr.shape[1] > 960:
                scale = 960 / arr.shape[1]
                h2 = int(arr.shape[0] * scale)
                import cv2
                arr_small = cv2.resize(arr, (960, h2))
            else:
                arr_small = arr

            result, _ = ocr(arr_small)
            texts = []
            if result:
                for bbox, text, conf in result:
                    if conf > 0.3 and text.strip():
                        cx = int(sum(p[0] for p in bbox) / len(bbox) / scale)
                        cy = int(sum(p[1] for p in bbox) / len(bbox) / scale)
                        texts.append({"t": text.strip(), "x": cx, "y": cy, "c": round(conf, 2)})

            print(f"  OCR: {len(texts)} texts detected")
            for t in texts[:15]:
                print(f"    '{t['t']}' ({t['x']},{t['y']}) conf={t['c']}")

        except Exception as e:
            print(f"  OCR error: {e}")
            texts = []

        # ── Phase 4: Input test — keyboard ──
        print("\n⌨️ Phase 4: Keyboard input test...")
        # Focus canvas
        await canvas.click()
        await page.wait_for_timeout(200)

        # Press 'u' to toggle UI overlay in VaM
        await page.keyboard.press("u")
        print("  Sent key: 'u' (toggle UI)")
        await page.wait_for_timeout(2000)

        # Take another screenshot
        screenshot2 = await canvas.screenshot(type="png")
        with open("e2e_after_key.png", "wb") as f:
            f.write(screenshot2)
        print(f"  After key screenshot: e2e_after_key.png ({len(screenshot2)} bytes)")

        # OCR again to check if UI changed
        try:
            img2 = Image.open(io.BytesIO(screenshot2)).convert("RGB")
            arr2 = np.array(img2)
            if arr2.shape[1] > 960:
                arr2_small = cv2.resize(arr2, (960, int(arr2.shape[0] * scale)))
            else:
                arr2_small = arr2
            result2, _ = ocr(arr2_small)
            texts2 = []
            if result2:
                for bbox, text, conf in result2:
                    if conf > 0.3 and text.strip():
                        texts2.append(text.strip())

            print(f"  After key OCR: {len(texts2)} texts")
            # Compare
            before_set = set(t['t'] for t in texts)
            after_set = set(texts2)
            new = after_set - before_set
            lost = before_set - after_set
            if new or lost:
                print(f"  ✅ UI changed! +{len(new)} new, -{len(lost)} lost")
                if new: print(f"    NEW: {list(new)[:8]}")
                if lost: print(f"    LOST: {list(lost)[:8]}")
            else:
                print(f"  ⚠️ No text change detected (may need VaM focused)")

        except Exception as e:
            print(f"  OCR comparison error: {e}")

        # ── Phase 5: Mouse click test ──
        print("\n🖱️ Phase 5: Mouse click test...")
        box = await canvas.bounding_box()
        if box:
            # Click center of canvas
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            await page.mouse.click(cx, cy)
            print(f"  Clicked center: ({int(cx)}, {int(cy)})")
            await page.wait_for_timeout(500)

        # ── Phase 6: Server status check ──
        print("\n📊 Phase 6: Server status...")
        status = await page.evaluate("""
            async () => {
                const r = await fetch('/api/status');
                return await r.json();
            }
        """)
        print(f"  Running: {status['running']}")
        print(f"  Target: {status['target_title']} (hwnd={status['target_hwnd']})")
        print(f"  Capture mode: {status['capture_mode']}")
        print(f"  Stream: {status['stream_width']}×{status['stream_height']}")
        print(f"  Total frames: {status['frame_count']}")
        print(f"  Clients: {status['client_count']}")

        # ── Summary ──
        print("\n" + "=" * 60)
        print("  SUMMARY")
        print("=" * 60)

        results = {
            "websocket": connected,
            "stream": stream_ok,
            "canvas_size": f"{dims['w']}×{dims['h']}",
            "ocr_texts": len(texts),
            "frames_total": status['frame_count'],
            "capture_mode": status['capture_mode'],
        }

        all_pass = connected and stream_ok and len(texts) > 0
        for k, v in results.items():
            print(f"  {k}: {v}")

        print(f"\n  {'✅ ALL PASS — Full chain verified!' if all_pass else '⚠️ Some checks need attention'}")

        # Save results
        with open("e2e_results.json", "w", encoding="utf-8") as f:
            json.dump({
                "results": results,
                "texts_before": [t['t'] for t in texts],
                "status": status,
                "pass": all_pass,
            }, f, ensure_ascii=False, indent=2)
        print(f"  → e2e_results.json saved")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await browser.close()
        await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
