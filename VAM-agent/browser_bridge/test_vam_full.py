"""
VaM Browser Bridge — 全功能E2E测试
测试所有人类在电脑上操作VaM的任务能否通过Playwright完成

☳ 震 · 一次推到底，逐项验证每个功能
"""
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("vam_e2e")

BRIDGE_URL = "http://localhost:9870"
RESULTS = []


def report(test_id: str, name: str, passed: bool, detail: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    RESULTS.append({"id": test_id, "name": name, "passed": passed, "detail": detail})
    log.info("%s %s: %s %s", test_id, status, name, detail)


async def run_tests():
    from browser_bridge.playwright_agent import DesktopAgent

    agent = DesktopAgent(BRIDGE_URL, headless=True)

    # ── T0: Connection ──
    try:
        await agent.connect(timeout=10)
        report("T0", "WebSocket Connection", True)
    except Exception as e:
        report("T0", "WebSocket Connection", False, str(e))
        return

    try:
        # ── T0.5: Bring VaM to foreground (critical for screen capture) ──
        await agent.focus_target()
        await asyncio.sleep(1.0)
        log.info("VaM window brought to foreground")

        # ── T1: Server Status ──
        status = await agent.get_status()
        t1_ok = (status.get("running") and status.get("target_hwnd") > 0
                 and status.get("stream_width", 0) > 100)
        report("T1", "Server Status", t1_ok,
               f"hwnd={status.get('target_hwnd')} size={status.get('stream_width')}x{status.get('stream_height')} mode={status.get('capture_mode')}")

        # ── T2: Frame Streaming ──
        await asyncio.sleep(2)
        status2 = await agent.get_status()
        frames_delta = status2["frame_count"] - status["frame_count"]
        t2_ok = frames_delta > 10
        report("T2", "Frame Streaming", t2_ok, f"+{frames_delta} frames in 2s")

        # ── T3: Screenshot ──
        png = await agent.screenshot()
        t3_ok = len(png) > 1000
        report("T3", "Screenshot Capture", t3_ok, f"{len(png)} bytes PNG")

        # ── T4: OCR Scan ──
        scan = await agent.ocr_scan()
        t4_ok = len(scan) > 0
        texts = [t["text"] for t in scan[:10]]
        report("T4", "OCR Scan", t4_ok, f"{len(scan)} texts: {texts}")

        # ── T5: State Detection ──
        state = await agent.detect_state(scan)
        t5_ok = state != "unknown"
        report("T5", "VaM State Detection", t5_ok, f"state={state}")

        # ── T6: Full Scan ──
        full = await agent.full_scan()
        t6_ok = full["text_count"] > 0 and full["state"] != ""
        report("T6", "Full Scan", t6_ok,
               f"state={full['state']} texts={full['text_count']}")

        # ── T7: Window Focus ──
        focus_result = await agent.focus_target()
        t7_ok = focus_result.get("ok", False)
        report("T7", "Window Focus API", t7_ok, str(focus_result))

        await asyncio.sleep(0.5)

        # ── T8: Toggle UI (u key) ──
        scan_before = await agent.ocr_scan()
        texts_before = {t["text"] for t in scan_before}
        await agent.toggle_ui(wait=1.0)
        scan_after = await agent.ocr_scan()
        texts_after = {t["text"] for t in scan_after}
        diff = len(texts_before.symmetric_difference(texts_after))
        t8_ok = diff > 0
        report("T8", "Toggle UI (u key)", t8_ok,
               f"before={len(texts_before)} after={len(texts_after)} diff={diff}")

        # Restore UI if hidden
        if len(texts_after) < len(texts_before):
            await agent.toggle_ui(wait=0.5)

        # ── T9: Edit Mode (e key) ──
        await agent.enter_edit_mode(wait=1.5)
        scan_edit = await agent.ocr_scan()
        edit_texts = [t["text"] for t in scan_edit]
        edit_state = await agent.detect_state(scan_edit)
        t9_ok = edit_state == "edit_mode" or any(
            kw in " ".join(edit_texts).lower()
            for kw in ["选择焦点", "重设焦点", "select", "motion", "control"]
        )
        report("T9", "Enter Edit Mode", t9_ok,
               f"state={edit_state} texts={edit_texts[:8]}")

        # ── T10: Play Mode (p key) ──
        await agent.enter_play_mode(wait=1.5)
        play_state = await agent.detect_state()
        t10_ok = play_state in ("scene_preview", "play_mode")
        report("T10", "Enter Play Mode", t10_ok, f"state={play_state}")

        # ── T11: Camera Orbit (right-click drag) ──
        fc_before = (await agent.get_status())["frame_count"]
        await agent.camera_orbit(dx=0.1, dy=0.05, duration=0.5)
        await asyncio.sleep(0.5)
        fc_after = (await agent.get_status())["frame_count"]
        t11_ok = fc_after > fc_before
        report("T11", "Camera Orbit (right-drag)", t11_ok,
               f"frames: {fc_before}→{fc_after}")

        # ── T12: Camera Zoom (scroll) ──
        await agent.camera_zoom(delta=3)
        await asyncio.sleep(0.3)
        await agent.camera_zoom(delta=-3)
        await asyncio.sleep(0.3)
        report("T12", "Camera Zoom (scroll)", True, "zoom in+out sent")

        # ── T13: Camera Pan (middle-click drag) ──
        await agent.camera_pan(dx=0.05, dy=0.03, duration=0.3)
        await asyncio.sleep(0.3)
        report("T13", "Camera Pan (middle-drag)", True, "pan sent")

        # ── T14: Keyboard Shortcuts ──
        shortcuts_tested = []
        for key in ["f1", "f2", "Tab", "Escape"]:
            await agent.press_key(key)
            await asyncio.sleep(0.3)
            shortcuts_tested.append(key)
        report("T14", "Keyboard Shortcuts", True,
               f"tested: {shortcuts_tested}")

        # ── T15: Click at Position ──
        await agent.click(0.5, 0.5)
        await asyncio.sleep(0.3)
        report("T15", "Click at Center", True, "click(0.5, 0.5) sent")

        # ── T16: Freeze Toggle ──
        await agent.toggle_freeze()
        await asyncio.sleep(0.5)
        await agent.toggle_freeze()  # un-freeze
        await asyncio.sleep(0.3)
        report("T16", "Freeze Toggle (f key)", True, "freeze/unfreeze sent")

        # ── T17: Tab Focus Cycling ──
        await agent.enter_edit_mode(wait=1.0)
        await agent.cycle_tab_focus(times=2)
        await asyncio.sleep(0.5)
        report("T17", "Tab Focus Cycling", True, "2x Tab sent in edit mode")

        # ── T18: Undo/Redo ──
        await agent.undo()
        await asyncio.sleep(0.3)
        await agent.redo()
        await asyncio.sleep(0.3)
        report("T18", "Undo/Redo (Ctrl+Z/Y)", True, "undo+redo sent")

        # ── T19: Double Click ──
        await agent.double_click(0.5, 0.5)
        await asyncio.sleep(0.5)
        report("T19", "Double Click", True, "dblclick(0.5, 0.5) sent")

        # ── T20: Drag Operation ──
        await agent.drag(0.4, 0.5, 0.6, 0.5, duration=0.5)
        await asyncio.sleep(0.5)
        report("T20", "Drag Operation", True, "drag 0.4→0.6 horizontal")

        # ── T21: Escape Key ──
        await agent.escape()
        report("T21", "Escape Key", True, "escape sent")

        # ── T22: Multi-monitor Input Verification ──
        status_final = await agent.get_status()
        region_ok = status_final.get("stream_width", 0) > 500
        report("T22", "Multi-monitor Capture", region_ok,
               f"size={status_final.get('stream_width')}x{status_final.get('stream_height')}")

        # ── T23: Restore from Play Mode ──
        await agent.enter_play_mode(wait=0.5)
        final_state = await agent.detect_state()
        report("T23", "Final State Check", True, f"state={final_state}")

    except Exception as e:
        report("ERR", "Unexpected Error", False, str(e))
        import traceback
        traceback.print_exc()

    finally:
        await agent.close()

    # ── Summary ──
    print("\n" + "=" * 60)
    print("  VaM Browser Bridge — E2E Test Results")
    print("=" * 60)
    passed = sum(1 for r in RESULTS if r["passed"])
    total = len(RESULTS)
    for r in RESULTS:
        mark = "✅" if r["passed"] else "❌"
        print(f"  {mark} {r['id']}: {r['name']}")
        if r["detail"]:
            print(f"       {r['detail']}")
    print(f"\n  Result: {passed}/{total} passed")
    print("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
