"""
OCR交互引擎 — 看到文字就能点击
===============================
对自定义渲染App（剪映/游戏/DirectX应用），UIA控件树为空。
本模块通过OCR定位文字在屏幕上的精确坐标，实现：
  - find_text(text) → 返回文字在屏幕上的bbox和中心坐标
  - click_text(text) → 找到文字并点击其中心
  - find_all_text() → 返回屏幕上所有可见文字及坐标
  - click_image(template) → 模板匹配+点击（可选）

类比浏览器Agent：
  浏览器: snapshot → 找到元素ref → click(ref)
  本模块: OCR扫描 → 找到文字坐标 → click(坐标)

单独测试:
  cd 认知代理
  python -m perception.ocr_interact
"""

import time
import ctypes
import logging
import json
import os
import sys

log = logging.getLogger("perception.ocr_interact")

user32 = ctypes.windll.user32

# 全局OCR实例缓存（避免重复加载模型）
_ocr_instance = None
_ocr_lock = None

def _get_ocr():
    """获取或创建OCR实例（单例，首次~3s，后续~0ms）"""
    global _ocr_instance
    if _ocr_instance is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_instance = RapidOCR()
        log.info("RapidOCR initialized")
    return _ocr_instance


def _capture_window(hwnd=None):
    """
    截取指定窗口（或前台窗口）的图像。
    如果指定hwnd的rect无效，自动降级到前台窗口。
    返回: (PIL.Image, window_rect_dict) 或 (None, None)
    """
    import mss
    from PIL import Image
    import ctypes.wintypes as wt

    # 启用DPI感知，确保坐标正确
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    def _get_rect(h):
        r = wt.RECT()
        user32.GetWindowRect(h, ctypes.byref(r))
        return {
            "x": r.left, "y": r.top,
            "w": r.right - r.left, "h": r.bottom - r.top,
        }

    # 尝试指定hwnd
    if hwnd:
        wrect = _get_rect(hwnd)
        # 无效rect（最小化/隐藏/负坐标）→降级到前台窗口
        if wrect["w"] < 50 or wrect["h"] < 50 or wrect["x"] < -1000:
            log.debug("hwnd %s has invalid rect %s, falling back to foreground", hwnd, wrect)
            hwnd = None

    if hwnd is None:
        hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, None

    wrect = _get_rect(hwnd)
    if wrect["w"] < 50 or wrect["h"] < 50:
        return None, None

    monitor = {
        "left": wrect["x"],
        "top": wrect["y"],
        "width": wrect["w"],
        "height": wrect["h"],
    }

    with mss.mss() as sct:
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)

    return img, wrect


def _bbox_center(bbox):
    """从四点bbox计算中心坐标"""
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _bbox_rect(bbox):
    """从四点bbox计算矩形 {x, y, w, h}"""
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    return {
        "x": min(xs), "y": min(ys),
        "w": max(xs) - min(xs),
        "h": max(ys) - min(ys),
    }


def _force_focus(hwnd):
    """强制聚焦窗口（ShowWindow+AttachThreadInput技巧）"""
    import ctypes.wintypes as wt
    SW_RESTORE = 9
    user32.ShowWindow(hwnd, SW_RESTORE)
    time.sleep(0.15)
    cur_fg = user32.GetForegroundWindow()
    if cur_fg != hwnd:
        cur_tid = user32.GetWindowThreadProcessId(cur_fg, None)
        target_tid = user32.GetWindowThreadProcessId(hwnd, None)
        user32.AttachThreadInput(cur_tid, target_tid, True)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(cur_tid, target_tid, False)
    time.sleep(0.3)
    return user32.GetForegroundWindow() == hwnd


def _capture_full_screen():
    """截取整个主屏幕。最可靠的方式，适用于任何应用。"""
    import mss
    from PIL import Image

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    with mss.mss() as sct:
        # monitors[0] is the combined virtual screen, monitors[1] is primary
        mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        shot = sct.grab(mon)
        img = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)
        wrect = {"x": mon["left"], "y": mon["top"], "w": mon["width"], "h": mon["height"]}
        return img, wrect


def focus_and_scan(hwnd=None, process_name=None, title_keyword=None, min_confidence=0.5):
    """
    原子操作：聚焦窗口 + 立即截屏 + OCR。
    解决焦点竞争问题：聚焦后0.3s内截屏，不给其他窗口抢焦点机会。

    hwnd: 直接指定窗口句柄
    process_name: 按进程名查找(e.g. 'JianyingPro.exe')
    title_keyword: 按标题关键字查找(e.g. '剪映')
    """
    import ctypes.wintypes as wt

    # 查找目标窗口
    target = hwnd
    if not target and (process_name or title_keyword):
        found = []
        def _enum(h, _):
            if user32.IsWindowVisible(h):
                length = user32.GetWindowTextLengthW(h)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(h, buf, length + 1)
                    pid = wt.DWORD()
                    user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                    proc = ""
                    try:
                        import psutil
                        proc = psutil.Process(pid.value).name()
                    except: pass
                    if process_name and process_name.lower() in proc.lower():
                        found.append(h)
                    elif title_keyword and title_keyword in buf.value:
                        found.append(h)
            return True
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(_enum), 0)
        if found:
            target = found[0]

    if not target:
        return {"error": "window not found", "texts": [], "total": 0}

    # 聚焦
    focused = _force_focus(target)
    if not focused:
        log.warning("Could not focus hwnd=%s, capturing anyway", target)

    # 立即截屏 + OCR（不经HTTP，同步执行）
    return scan(full_screen=True, min_confidence=min_confidence)


# ---------------------------------------------------------------------------
# 核心API
# ---------------------------------------------------------------------------

def scan(hwnd=None, min_confidence=0.5, full_screen=False):
    """
    扫描窗口（或全屏）中所有可见文字及其屏幕坐标。

    full_screen: True=扫描整个主屏幕（最可靠，适用于任何应用）

    返回:
    {
        "texts": [
            {
                "text": "草稿 (17)",
                "confidence": 0.95,
                "bbox": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]],
                "center": {"x": 500, "y": 300},  # 屏幕绝对坐标
                "rect": {"x": 480, "y": 290, "w": 40, "h": 20},  # 屏幕绝对矩形
            },
            ...
        ],
        "window": {"x": 0, "y": 0, "w": 1920, "h": 1080},
        "scan_ms": 1234,
        "total": 42,
    }
    """
    start = time.perf_counter()
    import numpy as np

    if full_screen:
        img, wrect = _capture_full_screen()
    else:
        img, wrect = _capture_window(hwnd)
        # 窗口捕获失败 → 降级到全屏
        if img is None:
            log.info("Window capture failed, falling back to full screen")
            img, wrect = _capture_full_screen()

    if img is None:
        return {"error": "cannot capture screen", "texts": [], "total": 0}

    ocr = _get_ocr()

    # 缩放提升OCR速度（2560→960px ≈ 7x加速，UI文字仍可读）
    scale_factor = 1.0
    max_ocr_width = 960
    if img.width > max_ocr_width:
        scale_factor = max_ocr_width / img.width
        new_h = int(img.height * scale_factor)
        img = img.resize((max_ocr_width, new_h))

    arr = np.array(img)
    result, elapse = ocr(arr)

    texts = []
    if result:
        for bbox, text, conf in result:
            if conf < min_confidence:
                continue
            # 将OCR坐标还原到原始分辨率，再转为屏幕绝对坐标
            if scale_factor != 1.0:
                bbox = [[p[0] / scale_factor, p[1] / scale_factor] for p in bbox]
            center_img = _bbox_center(bbox)
            rect_img = _bbox_rect(bbox)

            screen_center = {
                "x": int(wrect["x"] + center_img[0]),
                "y": int(wrect["y"] + center_img[1]),
            }
            screen_rect = {
                "x": int(wrect["x"] + rect_img["x"]),
                "y": int(wrect["y"] + rect_img["y"]),
                "w": int(rect_img["w"]),
                "h": int(rect_img["h"]),
            }
            screen_bbox = [
                [int(wrect["x"] + p[0]), int(wrect["y"] + p[1])]
                for p in bbox
            ]

            texts.append({
                "text": text,
                "confidence": round(conf, 3),
                "bbox": screen_bbox,
                "center": screen_center,
                "rect": screen_rect,
            })

    elapsed = time.perf_counter() - start
    return {
        "texts": texts,
        "window": wrect,
        "scan_ms": round(elapsed * 1000, 1),
        "total": len(texts),
    }


def find_text(target, hwnd=None, exact=False, min_confidence=0.5):
    """
    查找包含指定文字的UI元素。

    target: 要查找的文字（支持部分匹配）
    exact: True=精确匹配，False=包含匹配
    返回: 匹配的元素列表（含屏幕坐标）
    """
    result = scan(hwnd=hwnd, min_confidence=min_confidence)
    if "error" in result:
        return result

    matches = []
    target_lower = target.lower()
    for item in result["texts"]:
        text = item["text"]
        if exact:
            if text == target:
                matches.append(item)
        else:
            if target_lower in text.lower():
                matches.append(item)

    return {
        "matches": matches,
        "count": len(matches),
        "target": target,
        "scan_ms": result["scan_ms"],
        "total_scanned": result["total"],
    }


def click_text(target, hwnd=None, exact=False, button="left",
               min_confidence=0.5, index=0):
    """
    找到指定文字并点击其中心。

    target: 要点击的文字
    index: 多个匹配时选择第几个（0=第一个）
    返回: {"ok": True, "clicked": {...}, "x": 500, "y": 300}
    """
    result = find_text(target, hwnd=hwnd, exact=exact, min_confidence=min_confidence)
    if "error" in result:
        return result

    matches = result["matches"]
    if not matches:
        return {
            "ok": False,
            "error": f"text not found: {target}",
            "scanned": result["total_scanned"],
        }

    if index >= len(matches):
        index = len(matches) - 1

    item = matches[index]
    x = item["center"]["x"]
    y = item["center"]["y"]

    # 执行点击
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        if button == "right":
            pyautogui.rightClick(x, y)
        elif button == "double":
            pyautogui.doubleClick(x, y)
        else:
            pyautogui.click(x, y)

        return {
            "ok": True,
            "clicked": item,
            "x": x,
            "y": y,
            "button": button,
            "scan_ms": result["scan_ms"],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def type_at(target, text, hwnd=None, clear_first=False, min_confidence=0.5):
    """
    找到指定文字位置，点击后输入文本。

    target: 要点击的输入框标识文字
    text: 要输入的内容
    clear_first: 输入前先全选清除
    """
    click_result = click_text(target, hwnd=hwnd, min_confidence=min_confidence)
    if not click_result.get("ok"):
        return click_result

    time.sleep(0.3)  # 等待焦点

    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        if clear_first:
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
        pyautogui.write(text, interval=0.02)
        return {
            "ok": True,
            "clicked": click_result["clicked"],
            "typed": text,
            "x": click_result["x"],
            "y": click_result["y"],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 独立测试
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== OCR Interact — 屏幕文字扫描 ===")
    print("扫描当前前台窗口的所有可见文字...\n")

    result = scan()
    print(f"窗口: {result.get('window')}")
    print(f"扫描耗时: {result.get('scan_ms')}ms")
    print(f"识别文字: {result.get('total')}个\n")

    for item in result.get("texts", [])[:20]:
        c = item["center"]
        print(f"  [{item['confidence']:.2f}] ({c['x']:4d},{c['y']:4d}) {item['text'][:60]}")

    # 测试查找
    print("\n=== 查找测试 ===")
    test_find = find_text("草稿")
    print(f"查找'草稿': {test_find.get('count')} matches")
    for m in test_find.get("matches", []):
        print(f"  ({m['center']['x']},{m['center']['y']}) {m['text']}")
