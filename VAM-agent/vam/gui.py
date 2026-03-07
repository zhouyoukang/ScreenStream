"""
VaM GUI 自动化模块 — 后台无感操作VaM软件
==============================================
VaM是Unity引擎渲染，Windows UIA控件树为空。
本模块通过 OCR定位文字 + 后台消息注入 实现完全后台GUI自动化。

架构类比浏览器MCP (DevTools Protocol):
  - 浏览器MCP: CDP协议 → DOM检查 + 事件派发 (用户无感)
  - VaM后台: PrintWindow截图 + PostMessage输入 (用户无感)

两种模式:
  - 后台模式 (background=True, 默认): 不抢焦点、不移鼠标、用户完全无感
  - 前台模式 (background=False): 聚焦窗口 + pyautogui (降级后备)

资源来源（已整合、自包含、不依赖外部项目）:
  - ghost_server.py → 后台PostMessage点击/按键/打字
  - 认知代理 → OCR扫描+文字点击
  - 远程桌面 → MouseGuard+DPI处理+PrintWindow截图

核心能力:
  - 窗口发现 (Win32 API, 无需聚焦)
  - 截屏 (PrintWindow, 后台截取不抢焦点)
  - OCR文字识别+定位 (RapidOCR)
  - 后台点击/按键/滚轮 (PostMessage, 不移动真实鼠标)
  - 状态验证 (截屏+OCR对比)
  - VaM专用UI地图 (按钮/菜单/快捷键)

依赖:
  pip install pyautogui mss Pillow numpy rapidocr-onnxruntime psutil

单独测试:
  cd VAM-agent
  python -m vam.gui
"""

import time
import ctypes
import ctypes.wintypes as wt
import logging
import json
import os
import sys
import io
import subprocess
import threading
from typing import Optional, List, Dict, Tuple, Any

log = logging.getLogger("vam.gui")

user32 = ctypes.windll.user32

# ═══════════════════════════════════════════════════════════════
# VaM UI 知识库 — VaM软件特有的UI结构和快捷键
# ═══════════════════════════════════════════════════════════════

VAM_PROCESS = "VaM.exe"
VAM_WINDOW_CLASS = "UnityWndClass"  # Unity默认窗口类名

# VaM主菜单按钮（从截图提取）
VAM_MAIN_MENU = {
    "hub":            {"text": "VaM Hub",         "alt": "HUB商城"},
    "scene_browser":  {"text": "Scene Browser",   "alt": "场景浏览器"},
    "create":         {"text": "Create",          "alt": "场景"},
    "teaser":         {"text": "Teaser",          "alt": None},
    "creator":        {"text": "Creator",         "alt": None},
}

# VaM快捷键映射
VAM_HOTKEYS = {
    # 视角控制
    "toggle_ui":       "u",           # 显示/隐藏UI
    "toggle_edit":     "e",           # 切换编辑模式
    "play_mode":       "p",           # 播放模式
    "screenshot":      "f9",          # VaM内部截图
    "fullscreen":      "f11",         # 全屏
    # 场景操作
    "save":            ["ctrl", "s"], # 保存场景
    "load":            ["ctrl", "l"], # 加载场景
    "new_scene":       ["ctrl", "n"], # 新建场景
    "undo":            ["ctrl", "z"], # 撤销
    "redo":            ["ctrl", "y"], # 重做
    # 选择
    "select_next":     "tab",         # 选择下一个Atom
    "deselect":        "escape",      # 取消选择
    # 相机
    "camera_1":        "f1",
    "camera_2":        "f2",
    "camera_3":        "f3",
    "reset_camera":    "f5",
    # 特殊
    "freeze_motion":   "f",           # 冻结物理
    "freeze_all":      ["shift", "f"],
}

# VaM场景编辑器UI元素（常见文字标签）
VAM_EDITOR_ELEMENTS = {
    "tabs": ["Control", "Clothing", "Hair", "Morphs", "Skin",
             "Plugins", "Animation", "Physics", "Misc"],
    "panels": ["Select", "Move", "Rotate", "Scale"],
    "common_buttons": ["Add Atom", "Remove", "Save Scene", "Load Scene",
                       "Merge Scene", "Open UI", "Close UI"],
}


# ═══════════════════════════════════════════════════════════════
# MouseGuard — 来自 远程桌面/remote_agent.py
# 用户正在操作鼠标/键盘时，自动阻止Agent动作，防止五感冲突
# ═══════════════════════════════════════════════════════════════

class MouseGuard:
    """Monitor user mouse/keyboard activity, block automation when user is active.
    Prevents Agent from hijacking user's five senses.

    Usage:
        guard.acquire() -> (bool, str)  # try to take control
        guard.release()                 # release after action
        guard.status() -> dict          # current state
    """

    def __init__(self, cooldown=2.0):
        self.cooldown = cooldown
        self._paused = False
        self._enabled = True
        self._last_user_activity = 0.0
        self._auto_acting = False
        self._prev_pos = (0, 0)
        self._lock = threading.Lock()
        self._blocked_count = 0
        self._total_requests = 0
        self._started = False

    def start(self):
        """Start background mouse/keyboard monitor thread."""
        if self._started:
            return
        self._started = True
        t = threading.Thread(target=self._watch, daemon=True)
        t.start()
        log.info("MouseGuard started (cooldown=%.1fs)", self.cooldown)

    def _watch(self):
        """Background: poll mouse position + keyboard via GetLastInputInfo."""
        try:
            import pyautogui
        except ImportError:
            log.warning("MouseGuard: pyautogui not available")
            return

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        get_last_input = ctypes.windll.user32.GetLastInputInfo
        prev_input_tick = 0

        self._prev_pos = pyautogui.position()
        while True:
            time.sleep(0.1)
            try:
                pos = pyautogui.position()
                with self._lock:
                    user_active = False
                    if not self._auto_acting and pos != self._prev_pos:
                        user_active = True
                    if not self._auto_acting and get_last_input(ctypes.byref(lii)):
                        if prev_input_tick and lii.dwTime != prev_input_tick:
                            user_active = True
                        prev_input_tick = lii.dwTime
                    if user_active:
                        self._last_user_activity = time.time()
                    self._prev_pos = pos
            except Exception:
                pass

    def acquire(self) -> Tuple[bool, str]:
        """Try to acquire control. Returns (allowed, reason)."""
        if not self._started:
            self.start()
        with self._lock:
            self._total_requests += 1
            if not self._enabled:
                return True, "guard disabled"
            if self._paused:
                return True, "guard paused"
            elapsed = time.time() - self._last_user_activity
            if elapsed < self.cooldown:
                self._blocked_count += 1
                return False, f"user active {elapsed:.1f}s ago (cooldown {self.cooldown}s)"
            self._auto_acting = True
        return True, "ok"

    def release(self):
        """Release control after automation action."""
        try:
            import pyautogui
            with self._lock:
                self._prev_pos = pyautogui.position()
                self._auto_acting = False
        except Exception:
            with self._lock:
                self._auto_acting = False

    def wait_and_acquire(self, timeout: float = 30.0,
                         poll: float = 0.5) -> Tuple[bool, str]:
        """Wait until user is idle, then acquire. Returns (acquired, reason)."""
        start = time.time()
        while time.time() - start < timeout:
            ok, reason = self.acquire()
            if ok:
                return True, reason
            time.sleep(poll)
        return False, f"timeout after {timeout}s waiting for user idle"

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def set_cooldown(self, seconds: float):
        self.cooldown = max(0.5, min(seconds, 30.0))

    def status(self) -> dict:
        with self._lock:
            elapsed = time.time() - self._last_user_activity
        return {
            "enabled": self._enabled,
            "paused": self._paused,
            "cooldown": self.cooldown,
            "user_idle_seconds": round(elapsed, 1),
            "can_automate": (elapsed >= self.cooldown or self._paused or not self._enabled),
            "blocked_count": self._blocked_count,
            "total_requests": self._total_requests,
        }


# Global MouseGuard instance
_guard = MouseGuard(cooldown=2.0)


def get_guard() -> MouseGuard:
    """Get the global MouseGuard instance."""
    return _guard


# ═══════════════════════════════════════════════════════════════
# 窗口管理 (Win32 API) — 来自 认知代理/perception + 远程桌面
# ═══════════════════════════════════════════════════════════════

def find_vam_window() -> Optional[int]:
    """
    查找VaM窗口句柄。
    优先按进程名VaM.exe查找（精确匹配），
    降级按窗口类名UnityWndClass或标题以"VaM"开头查找。
    返回: hwnd 或 None
    """
    by_process = []
    by_title = []

    def _enum(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value

                # 窗口类名
                cls_buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, cls_buf, 256)
                cls_name = cls_buf.value

                # 进程名
                pid = wt.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                proc_name = ""
                try:
                    import psutil
                    proc_name = psutil.Process(pid.value).name()
                except Exception:
                    pass

                entry = (hwnd, title, proc_name, pid.value, cls_name)

                # 优先级1: 进程名精确匹配VaM.exe
                if proc_name.lower() == VAM_PROCESS.lower():
                    by_process.append(entry)
                # 优先级2: Unity窗口类 或 标题以"VaM"开头（排除路径中含vam的误匹配）
                elif cls_name == VAM_WINDOW_CLASS:
                    by_title.append(entry)
                elif title.lower().startswith("vam"):
                    by_title.append(entry)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(_enum), 0)

    candidates = by_process or by_title
    if candidates:
        hwnd, title, proc, pid, cls = candidates[0]
        log.info("VaM window found: hwnd=%s title='%s' proc=%s pid=%s class=%s",
                 hwnd, title, proc, pid, cls)
        return hwnd
    return None


def get_window_rect(hwnd: int) -> Dict[str, int]:
    """获取窗口矩形 {x, y, w, h}"""
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return {
        "x": rect.left, "y": rect.top,
        "w": rect.right - rect.left,
        "h": rect.bottom - rect.top,
    }


def get_window_info(hwnd: int) -> Dict[str, Any]:
    """获取窗口详细信息"""
    # 标题
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)

    # 类名
    cls_buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls_buf, 256)

    # PID
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    # 进程名
    proc_name = ""
    try:
        import psutil
        proc_name = psutil.Process(pid.value).name()
    except Exception:
        pass

    return {
        "hwnd": hwnd,
        "title": buf.value,
        "class": cls_buf.value,
        "pid": pid.value,
        "process": proc_name,
        "rect": get_window_rect(hwnd),
        "is_unity": cls_buf.value == VAM_WINDOW_CLASS,
    }


def _ensure_window_visible(hwnd: int):
    """确保窗口在屏幕可见区域内 — 防止focus_window把窗口移到屏幕外。"""
    _ensure_dpi_aware()
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top

    screen_w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    screen_h = user32.GetSystemMetrics(1)  # SM_CYSCREEN

    # 检查窗口是否大部分在屏幕外
    visible_x = max(0, min(rect.right, screen_w)) - max(0, rect.left)
    visible_y = max(0, min(rect.bottom, screen_h)) - max(0, rect.top)
    visible_area = max(0, visible_x) * max(0, visible_y)
    total_area = w * h

    if total_area > 0 and visible_area / total_area < 0.5:
        # 窗口超过50%在屏幕外 → 移到左上角
        SWP_NOZORDER = 0x0004
        SWP_NOSIZE = 0x0001
        new_x = max(0, min(screen_w - w, 0))
        new_y = 0
        user32.SetWindowPos(hwnd, 0, new_x, new_y, 0, 0, SWP_NOZORDER | SWP_NOSIZE)
        log.info("Window repositioned: (%d,%d) %dx%d → (%d,%d) (was %.0f%% offscreen)",
                 rect.left, rect.top, w, h, new_x, new_y,
                 (1 - visible_area / total_area) * 100)
        time.sleep(0.2)


def focus_window(hwnd: int) -> Dict:
    """
    强制聚焦窗口 — 多策略绕过Windows前台限制。
    策略: AttachThreadInput → Alt键技巧 → 最小化再恢复
    聚焦后检查窗口是否在屏幕可见区域内。
    """
    _ensure_dpi_aware()
    SW_MINIMIZE = 6
    SW_RESTORE = 9
    method = "all_failed"
    is_focused = False

    # 策略1: ShowWindow + AttachThreadInput
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
    time.sleep(0.2)

    if user32.GetForegroundWindow() == hwnd:
        method = "attach_thread"
        is_focused = True
    else:
        # 策略2: Alt键技巧 — 模拟Alt按下释放使SetForegroundWindow生效
        VK_MENU = 0x12
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.SetForegroundWindow(hwnd)
        user32.keybd_event(VK_MENU, 0, 2, 0)  # KEYEVENTF_KEYUP
        time.sleep(0.3)

        if user32.GetForegroundWindow() == hwnd:
            method = "alt_trick"
            is_focused = True
        else:
            # 策略3: 最小化再恢复 — 强制Windows刷新Z-order
            user32.ShowWindow(hwnd, SW_MINIMIZE)
            time.sleep(0.2)
            user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.3)

            is_focused = user32.GetForegroundWindow() == hwnd
            method = "minimize_restore" if is_focused else "all_failed"

    log.debug("focus_window hwnd=%s → %s (method=%s)", hwnd, is_focused, method)

    # 聚焦后确保窗口在屏幕可见区域（所有策略共用）
    _ensure_window_visible(hwnd)

    return {"ok": is_focused, "hwnd": hwnd, "method": method}


def is_vam_running() -> bool:
    """检查VaM进程是否运行"""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {VAM_PROCESS}"],
            capture_output=True, timeout=10
        )
        stdout = result.stdout.decode('gbk', errors='ignore')
        return VAM_PROCESS.lower() in stdout.lower()
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# 截屏引擎 — 来自 认知代理/perception/ocr_interact.py
# ═══════════════════════════════════════════════════════════════

def _ensure_dpi_aware():
    """确保DPI感知，坐标才正确"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def _is_black_image(img, threshold: float = 15.0, skip_top: int = 50) -> bool:
    """检测图像是否基本全黑（跳过标题栏区域）。
    Unity DirectX 3D场景无法被PrintWindow捕获，返回全黑帧。
    threshold: 平均亮度低于此值视为黑屏。
    skip_top: 跳过标题栏像素行。"""
    import numpy as np
    arr = np.array(img)
    if arr.shape[0] <= skip_top:
        return arr.mean() < threshold
    body = arr[skip_top:, :, :]
    return body.mean() < threshold


def capture_rapid_flash(hwnd: int = None) -> Tuple[Any, Dict]:
    """极速闪焦截屏 — 短暂前置VaM窗口，mss截屏，立即恢复。
    用于Unity DirectX 3D场景无法被PrintWindow捕获的情况。
    使用多重Win32调用确保VaM真正到前台（SetWindowPos+BringWindowToTop+SetForegroundWindow）。
    总干扰时间 ~300ms。"""
    import mss
    from PIL import Image

    if hwnd is None:
        hwnd = find_vam_window()
    if hwnd is None:
        return None, {}

    wrect = get_window_rect(hwnd)
    if wrect["w"] < 50 or wrect["h"] < 50:
        return None, {}

    # 保存当前状态
    import pyautogui
    fg_before = user32.GetForegroundWindow()
    cursor_before = pyautogui.position()

    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_SHOWWINDOW = 0x0040

    # Step 1: HWND_TOPMOST强制VaM到所有窗口之上
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    # Step 2: 给予焦点 — Unity只在聚焦时渲染帧
    _rapid_focus(hwnd)
    # Step 3: 等待Unity渲染至少一帧（~300ms，Unity需要恢复渲染+产出1帧）
    time.sleep(0.35)

    # mss截屏（VaM应在前台）
    try:
        monitor = {
            "left": wrect["x"], "top": wrect["y"],
            "width": wrect["w"], "height": wrect["h"],
        }
        with mss.mss() as sct:
            shot = sct.grab(monitor)
            raw = bytes(shot.rgb)
            img = Image.frombytes("RGB", (shot.width, shot.height), raw)
    except Exception as e:
        # 移除置顶 + 恢复前台 + 恢复鼠标
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE)
        _rapid_restore(fg_before)
        user32.SetCursorPos(cursor_before[0], cursor_before[1])
        log.warning("Rapid-flash mss capture failed: %s", e)
        return None, {}

    # 移除置顶 + 恢复之前的前台窗口 + 恢复鼠标
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE)
    _rapid_restore(fg_before)
    user32.SetCursorPos(cursor_before[0], cursor_before[1])

    if img.getbbox() is None:
        return None, {}

    log.info("Rapid-flash capture: %dx%d [~300ms flash]", img.size[0], img.size[1])
    return img, wrect


def rapid_key_and_capture(key: str = None, hwnd: int = None,
                          pre_delay: float = 0.5) -> Tuple[Any, Dict]:
    """在单次rapid-flash会话中执行: 按键 → 等待渲染 → 截屏。
    避免分别做bg_key+scan导致的多次focus/defocus干扰VaM状态。

    key: 要按的键（None则只截屏）
    pre_delay: 按键后等待VaM渲染的秒数
    返回: (PIL.Image, window_rect)
    """
    import mss
    from PIL import Image

    if hwnd is None:
        hwnd = find_vam_window()
    if hwnd is None:
        return None, {}

    wrect = get_window_rect(hwnd)
    if wrect["w"] < 50 or wrect["h"] < 50:
        return None, {}

    import pyautogui
    fg_before = user32.GetForegroundWindow()
    cursor_before = pyautogui.position()

    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_SHOWWINDOW = 0x0040

    # 单次会话: TOPMOST + focus
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    _rapid_focus(hwnd)
    time.sleep(0.08)  # Unity处理焦点

    # 按键（如果有）
    if key:
        parts = key.lower().split("+")
        parts = [p.strip() for p in parts]
        inputs = []
        for p in parts[:-1]:
            if p in VK_MAP:
                inputs.append(_make_key_input(VK_MAP[p]))
        main = parts[-1]
        if main in VK_MAP:
            vk = VK_MAP[main]
        elif len(main) == 1:
            vk = ord(main.upper())
        else:
            vk = None
        if vk:
            inputs.append(_make_key_input(vk))
            inputs.append(_make_key_input(vk, up=True))
        for p in reversed(parts[:-1]):
            if p in VK_MAP:
                inputs.append(_make_key_input(VK_MAP[p], up=True))
        if inputs:
            _send_input(*inputs)

    # 等待VaM渲染
    time.sleep(pre_delay)

    # mss截屏
    try:
        monitor = {
            "left": wrect["x"], "top": wrect["y"],
            "width": wrect["w"], "height": wrect["h"],
        }
        with mss.mss() as sct:
            shot = sct.grab(monitor)
            raw = bytes(shot.rgb)
            img = Image.frombytes("RGB", (shot.width, shot.height), raw)
    except Exception as e:
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE)
        _rapid_restore(fg_before)
        user32.SetCursorPos(cursor_before[0], cursor_before[1])
        log.warning("rapid_key_and_capture failed: %s", e)
        return None, {}

    # 恢复
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE)
    _rapid_restore(fg_before)
    user32.SetCursorPos(cursor_before[0], cursor_before[1])

    log.info("rapid_key_and_capture key=%s capture=%dx%d", key, img.size[0], img.size[1])
    return img, wrect


def warm_key_and_capture(key: str = None, hwnd: int = None,
                         delay: float = 1.0) -> Tuple[Any, Dict]:
    """先warm-up再按键截屏。解决VaM首次focus后不立即渲染的问题。
    Unity在失去焦点后暂停渲染，首次focus需要额外时间恢复渲染管线。
    warm-up capture唤醒渲染 → 短暂间隔 → 正式按键+截屏。
    """
    if hwnd is None:
        hwnd = find_vam_window()
    if hwnd is None:
        return None, {}
    # warm-up: 短暂focus唤醒Unity渲染
    rapid_key_and_capture(key=None, hwnd=hwnd, pre_delay=0.15)
    time.sleep(0.1)
    return rapid_key_and_capture(key=key, hwnd=hwnd, pre_delay=delay)


def rapid_click_and_capture(img_x: int, img_y: int, hwnd: int = None,
                            wait: float = 1.5) -> Tuple[Any, Dict]:
    """单次TOPMOST会话: focus → 点击图像坐标 → 等待 → 截屏 → 恢复。
    用于点击VaM的UI按钮（如编辑模式、更多选项等）并截取结果。
    """
    import mss
    from PIL import Image

    if hwnd is None:
        hwnd = find_vam_window()
    if hwnd is None:
        return None, {}

    wrect = get_window_rect(hwnd)
    screen_x = wrect["x"] + img_x
    screen_y = wrect["y"] + img_y

    import pyautogui
    fg_before = user32.GetForegroundWindow()
    cursor_before = pyautogui.position()

    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_SHOWWINDOW = 0x0040

    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    _rapid_focus(hwnd)
    time.sleep(0.08)

    user32.SetCursorPos(screen_x, screen_y)
    time.sleep(0.03)
    _send_input(
        _make_mouse_input(screen_x, screen_y, MOUSEEVENTF_LEFTDOWN),
        _make_mouse_input(screen_x, screen_y, MOUSEEVENTF_LEFTUP),
    )
    time.sleep(wait)

    try:
        monitor = {
            "left": wrect["x"], "top": wrect["y"],
            "width": wrect["w"], "height": wrect["h"],
        }
        with mss.mss() as sct:
            shot = sct.grab(monitor)
            raw = bytes(shot.rgb)
            img = Image.frombytes("RGB", (shot.width, shot.height), raw)
    except Exception as e:
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE)
        _rapid_restore(fg_before)
        user32.SetCursorPos(cursor_before[0], cursor_before[1])
        log.warning("rapid_click_and_capture failed: %s", e)
        return None, {}

    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE)
    _rapid_restore(fg_before)
    user32.SetCursorPos(cursor_before[0], cursor_before[1])

    log.info("rapid_click_and_capture (%d,%d) capture=%dx%d",
             img_x, img_y, img.size[0], img.size[1])
    return img, wrect


def capture_window(hwnd: int = None) -> Tuple[Any, Dict]:
    """
    截取VaM窗口。优先PrintWindow（获取实际窗口内容，无论是否被遮挡），
    降级到rapid-flash（短暂前置+mss），再降级到mss直接，最后全屏。
    返回: (PIL.Image, window_rect)
    """
    _ensure_dpi_aware()

    if hwnd is None:
        hwnd = find_vam_window()
    if hwnd is None:
        return capture_full_screen()

    # 最小化窗口恢复（不抢焦点），确保可截取
    _ensure_capturable(hwnd)

    wrect = get_window_rect(hwnd)
    if wrect["w"] < 50 or wrect["h"] < 50:
        log.warning("VaM window too small (%dx%d), falling back to full screen",
                    wrect["w"], wrect["h"])
        return capture_full_screen()

    # Method 1: PrintWindow (captures actual window content, works even if behind other windows)
    try:
        pw_img, pw_rect = capture_printwindow(hwnd)
        if pw_img is not None:
            # 检测黑屏（Unity 3D场景DirectX渲染无法被PrintWindow捕获）
            if not _is_black_image(pw_img):
                return pw_img, pw_rect
            log.info("PrintWindow returned black image (DirectX 3D scene), trying rapid capture")
    except Exception as e:
        log.warning("PrintWindow failed: %s", e)

    # Method 2: Rapid-flash capture (briefly bring to front, mss capture, restore)
    try:
        rf_img, rf_rect = capture_rapid_flash(hwnd)
        if rf_img is not None:
            return rf_img, rf_rect
    except Exception as e:
        log.warning("Rapid-flash capture failed: %s", e)

    # Method 3: mss direct (only works if window is already topmost/visible)
    try:
        import mss
        from PIL import Image
        monitor = {
            "left": wrect["x"], "top": wrect["y"],
            "width": wrect["w"], "height": wrect["h"],
        }
        with mss.mss() as sct:
            shot = sct.grab(monitor)
            raw = bytes(shot.rgb)
            img = Image.frombytes("RGB", (shot.width, shot.height), raw)
            if img.getbbox() is None:
                raise RuntimeError("mss returned blank image")
        return img, wrect
    except Exception as e:
        log.warning("mss capture also failed: %s", e)

    # Method 4: full screen fallback
    return capture_full_screen()


def capture_full_screen() -> Tuple[Any, Dict]:
    """截取整个主屏幕"""
    import mss
    from PIL import Image

    _ensure_dpi_aware()

    with mss.mss() as sct:
        mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        shot = sct.grab(mon)
        img = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)
        wrect = {"x": mon["left"], "y": mon["top"],
                 "w": mon["width"], "h": mon["height"]}
        return img, wrect


def save_screenshot(path: str = None, hwnd: int = None) -> str:
    """截图保存到文件，返回路径"""
    img, wrect = capture_window(hwnd)
    if img is None:
        return ""
    if path is None:
        path = os.path.join(os.path.dirname(__file__),
                           f"_screenshot_{int(time.time())}.png")
    img.save(path)
    log.info("Screenshot saved: %s (%dx%d)", path, wrect["w"], wrect["h"])
    return path


# ═══════════════════════════════════════════════════════════════
# OCR引擎 — 来自 认知代理/perception/ocr_interact.py
# ═══════════════════════════════════════════════════════════════

_ocr_instance = None

def _get_ocr():
    """获取RapidOCR实例（单例，首次~3s，后续~0ms）"""
    global _ocr_instance
    if _ocr_instance is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_instance = RapidOCR()
        log.info("RapidOCR initialized")
    return _ocr_instance


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


def scan(hwnd: int = None, min_confidence: float = 0.5,
         full_screen: bool = False) -> Dict:
    """
    OCR扫描VaM窗口中所有可见文字及其屏幕坐标。

    返回:
    {
        "texts": [
            {
                "text": "Scene Browser",
                "confidence": 0.95,
                "center": {"x": 500, "y": 300},   # 屏幕绝对坐标
                "rect": {"x": 480, "y": 290, "w": 100, "h": 20},
            },
        ],
        "window": {"x": 0, "y": 0, "w": 1920, "h": 1080},
        "scan_ms": 1234,
        "total": 42,
    }
    """
    start = time.perf_counter()
    import numpy as np

    if full_screen:
        img, wrect = capture_full_screen()
    else:
        img, wrect = capture_window(hwnd)

    if img is None:
        return {"error": "cannot capture VaM window", "texts": [], "total": 0}

    ocr = _get_ocr()

    # 缩放提升OCR速度（>960px时缩放）
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
            # OCR坐标还原到原始分辨率 → 屏幕绝对坐标
            if scale_factor != 1.0:
                bbox = [[p[0] / scale_factor, p[1] / scale_factor] for p in bbox]
            center_img = _bbox_center(bbox)
            rect_img = _bbox_rect(bbox)

            texts.append({
                "text": text,
                "confidence": round(conf, 3),
                "center": {
                    "x": int(wrect["x"] + center_img[0]),
                    "y": int(wrect["y"] + center_img[1]),
                },
                "img_center": {
                    "x": int(center_img[0]),
                    "y": int(center_img[1]),
                },
                "rect": {
                    "x": int(wrect["x"] + rect_img["x"]),
                    "y": int(wrect["y"] + rect_img["y"]),
                    "w": int(rect_img["w"]),
                    "h": int(rect_img["h"]),
                },
            })

    elapsed = time.perf_counter() - start
    return {
        "texts": texts,
        "window": wrect,
        "scan_ms": round(elapsed * 1000, 1),
        "total": len(texts),
    }


# ═══════════════════════════════════════════════════════════════
# 后台交互引擎 — PostMessage注入（用户无感，类比浏览器MCP）
# PrintWindow截图 → OCR定位 → PostMessage点击/按键/滚轮
# 不抢焦点、不移鼠标、不干扰用户任何操作
# ═══════════════════════════════════════════════════════════════

# 默认使用后台模式（用户无感）
BACKGROUND_MODE = True


def _MAKELPARAM(x: int, y: int) -> int:
    """构造LPARAM: low-word=x, high-word=y"""
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def _get_client_offset(hwnd: int) -> Tuple[int, int]:
    """获取窗口客户区相对于窗口左上角的偏移（标题栏+边框）。
    PrintWindow图像包含标题栏，需要减去此偏移才能得到客户区坐标。"""
    _ensure_dpi_aware()
    wrect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(wrect))
    pt = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return (pt.x - wrect.left, pt.y - wrect.top)


def _img_to_client(hwnd: int, img_x: int, img_y: int) -> Tuple[int, int]:
    """PrintWindow图像坐标 → 窗口客户区坐标"""
    ox, oy = _get_client_offset(hwnd)
    return (img_x - ox, img_y - oy)


# ── SendInput 结构定义 (硬件级输入注入) ──────────────────────
class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]

class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", _INPUT_UNION)]

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
KEYEVENTF_KEYUP = 0x0002


def _send_input(*inputs):
    """调用Win32 SendInput注入硬件级输入事件。"""
    n = len(inputs)
    arr = (_INPUT * n)(*inputs)
    user32.SendInput(n, ctypes.byref(arr), ctypes.sizeof(_INPUT))


def _make_mouse_input(dx, dy, flags, data=0):
    """构造鼠标SendInput事件。dx/dy为绝对坐标(0-65535归一化)。"""
    inp = _INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi.dx = dx
    inp.union.mi.dy = dy
    inp.union.mi.dwFlags = flags
    inp.union.mi.mouseData = data
    return inp


def _make_key_input(vk, up=False):
    """构造键盘SendInput事件。"""
    inp = _INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki.wVk = vk
    inp.union.ki.dwFlags = KEYEVENTF_KEYUP if up else 0
    return inp


def _screen_to_normalized(x, y):
    """屏幕坐标 → SendInput绝对坐标(0-65535)。"""
    sm_cx = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    sm_cy = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    nx = int(x * 65536 / sm_cx)
    ny = int(y * 65536 / sm_cy)
    return nx, ny


def _rapid_focus(hwnd: int) -> int:
    """极速聚焦VaM — 返回之前的前台窗口hwnd，用于之后恢复。
    使用AttachThreadInput确保SetForegroundWindow成功。"""
    fg_before = user32.GetForegroundWindow()
    if fg_before == hwnd:
        return fg_before

    fg_tid = user32.GetWindowThreadProcessId(fg_before, None)
    my_tid = ctypes.windll.kernel32.GetCurrentThreadId()
    if fg_tid != my_tid:
        user32.AttachThreadInput(my_tid, fg_tid, True)
    user32.SetForegroundWindow(hwnd)
    if fg_tid != my_tid:
        user32.AttachThreadInput(my_tid, fg_tid, False)
    return fg_before


def _rapid_restore(fg_before: int):
    """极速恢复之前的前台窗口。"""
    if fg_before and user32.IsWindow(fg_before):
        fg_tid = user32.GetWindowThreadProcessId(fg_before, None)
        my_tid = ctypes.windll.kernel32.GetCurrentThreadId()
        if fg_tid != my_tid:
            user32.AttachThreadInput(my_tid, fg_tid, True)
        user32.SetForegroundWindow(fg_before)
        if fg_tid != my_tid:
            user32.AttachThreadInput(my_tid, fg_tid, False)


def _bg_click(hwnd: int, img_x: int, img_y: int,
              button: str = "left") -> Dict:
    """后台点击 — 极速闪焦hybrid模式。
    Unity用GetAsyncKeyState读硬件状态，PostMessage无效。
    方案: 保存状态 → 闪焦VaM(~50ms) → SendInput点击 → 恢复状态。
    总干扰时间 <200ms，用户几乎无感。
    """
    _ensure_dpi_aware()

    # PrintWindow图像坐标 → 屏幕坐标
    cx, cy = _img_to_client(hwnd, img_x, img_y)
    pt = wt.POINT(cx, cy)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    screen_x, screen_y = pt.x, pt.y
    nx, ny = _screen_to_normalized(screen_x, screen_y)

    # 保存当前状态
    import pyautogui
    cursor_before = pyautogui.position()
    fg_before = _rapid_focus(hwnd)
    time.sleep(0.08)  # Unity需要~80ms处理焦点激活

    # SendInput: 移动 + 点击
    if button == "right":
        down_flag = MOUSEEVENTF_RIGHTDOWN
        up_flag = MOUSEEVENTF_RIGHTUP
    else:
        down_flag = MOUSEEVENTF_LEFTDOWN
        up_flag = MOUSEEVENTF_LEFTUP

    _send_input(
        _make_mouse_input(nx, ny, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE),
    )
    time.sleep(0.05)  # Unity更新鼠标位置

    if button == "double":
        _send_input(
            _make_mouse_input(0, 0, MOUSEEVENTF_LEFTDOWN),
            _make_mouse_input(0, 0, MOUSEEVENTF_LEFTUP),
        )
        time.sleep(0.05)
        _send_input(
            _make_mouse_input(0, 0, MOUSEEVENTF_LEFTDOWN),
            _make_mouse_input(0, 0, MOUSEEVENTF_LEFTUP),
        )
    else:
        _send_input(
            _make_mouse_input(0, 0, down_flag),
            _make_mouse_input(0, 0, up_flag),
        )
    time.sleep(0.08)  # Unity处理点击事件

    # 极速恢复
    _rapid_restore(fg_before)
    user32.SetCursorPos(cursor_before[0], cursor_before[1])

    log.info("bg_click %s img(%d,%d) → screen(%d,%d) [rapid-flash]",
             button, img_x, img_y, screen_x, screen_y)
    return {"ok": True, "img_x": img_x, "img_y": img_y,
            "screen_x": screen_x, "screen_y": screen_y, "method": "background"}


VK_MAP = {
    'enter': 0x0D, 'return': 0x0D, 'escape': 0x1B, 'esc': 0x1B,
    'tab': 0x09, 'space': 0x20, 'backspace': 0x08,
    'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
    'delete': 0x2E, 'home': 0x24, 'end': 0x23,
    'pageup': 0x21, 'pagedown': 0x22,
    'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
    'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
    'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
    'ctrl': 0x11, 'control': 0x11, 'shift': 0x10, 'alt': 0x12,
}


def _bg_key(hwnd: int, key: str) -> Dict:
    """后台按键 — 极速闪焦hybrid。
    保存焦点 → 闪焦VaM → SendInput按键 → 恢复焦点。
    """
    parts = key.lower().split("+")
    parts = [p.strip() for p in parts]

    fg_before = _rapid_focus(hwnd)
    time.sleep(0.08)  # Unity需要~80ms处理焦点激活

    # 构造输入序列
    inputs = []
    # 修饰键按下
    for p in parts[:-1]:
        if p in VK_MAP:
            inputs.append(_make_key_input(VK_MAP[p]))

    # 主键按下+释放
    main = parts[-1]
    if main in VK_MAP:
        vk = VK_MAP[main]
    elif len(main) == 1:
        vk = ord(main.upper())
    else:
        vk = None

    if vk:
        inputs.append(_make_key_input(vk))
        inputs.append(_make_key_input(vk, up=True))

    # 修饰键释放（逆序）
    for p in reversed(parts[:-1]):
        if p in VK_MAP:
            inputs.append(_make_key_input(VK_MAP[p], up=True))

    if inputs:
        _send_input(*inputs)
    time.sleep(0.05)  # Unity处理按键

    _rapid_restore(fg_before)

    log.info("bg_key '%s' [rapid-flash]", key)
    return {"ok": True, "key": key, "method": "background"}


def _bg_scroll(hwnd: int, clicks: int,
               img_x: int = None, img_y: int = None) -> Dict:
    """后台滚轮 — 极速闪焦hybrid。
    clicks: 正数=向上, 负数=向下
    """
    _ensure_dpi_aware()

    # 计算屏幕坐标
    if img_x is None or img_y is None:
        crect = wt.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(crect))
        cx = crect.right // 2
        cy = crect.bottom // 2
    else:
        cx, cy = _img_to_client(hwnd, img_x, img_y)

    pt = wt.POINT(cx, cy)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    nx, ny = _screen_to_normalized(pt.x, pt.y)

    # 保存状态
    import pyautogui
    cursor_before = pyautogui.position()
    fg_before = _rapid_focus(hwnd)
    time.sleep(0.08)  # Unity需要~80ms处理焦点激活

    # 移动到位置 + 滚轮
    _send_input(
        _make_mouse_input(nx, ny, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE),
    )
    time.sleep(0.05)

    WHEEL_DELTA = 120
    delta = clicks * WHEEL_DELTA
    _send_input(
        _make_mouse_input(0, 0, MOUSEEVENTF_WHEEL, data=delta),
    )
    time.sleep(0.08)  # Unity处理滚轮

    # 恢复
    _rapid_restore(fg_before)
    user32.SetCursorPos(cursor_before[0], cursor_before[1])

    log.info("bg_scroll %d clicks [rapid-flash]", clicks)
    return {"ok": True, "clicks": clicks, "method": "background"}


def _bg_type(hwnd: int, text: str) -> Dict:
    """后台输入文字 — 极速闪焦 + SendInput WM_CHAR。"""
    fg_before = _rapid_focus(hwnd)
    time.sleep(0.03)

    for ch in text:
        inputs = []
        vk = ctypes.windll.user32.VkKeyScanW(ord(ch))
        if vk != -1:
            lo = vk & 0xFF
            inputs.append(_make_key_input(lo))
            inputs.append(_make_key_input(lo, up=True))
            _send_input(*inputs)
        time.sleep(0.01)

    _rapid_restore(fg_before)
    log.info("bg_type %d chars [rapid-flash]", len(text))
    return {"ok": True, "length": len(text), "method": "background"}


# ═══════════════════════════════════════════════════════════════
# 前台交互引擎 — pyautogui操作（降级后备）
# ═══════════════════════════════════════════════════════════════

def _guarded_action(func):
    """Decorator: acquire MouseGuard before action, release after.
    If user is active, waits up to 10s for idle."""
    def wrapper(*args, **kwargs):
        ok, reason = _guard.wait_and_acquire(timeout=10.0)
        if not ok:
            log.warning("MouseGuard blocked: %s", reason)
            return {"ok": False, "error": f"user is active: {reason}",
                    "guard_blocked": True}
        try:
            return func(*args, **kwargs)
        finally:
            _guard.release()
    return wrapper


def _init_pyautogui():
    """初始化pyautogui（关闭安全锁）"""
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.05
    return pyautogui


def find_text(target: str, hwnd: int = None, exact: bool = False,
              min_confidence: float = 0.5) -> Dict:
    """
    在VaM窗口中查找包含指定文字的UI元素。

    target: 要查找的文字（支持部分匹配）
    exact: True=精确匹配，False=包含匹配
    返回: {"matches": [...], "count": N}
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


@_guarded_action
def click_text(target: str, hwnd: int = None, exact: bool = False,
               button: str = "left", min_confidence: float = 0.5,
               index: int = 0, focus_first: bool = True,
               background: bool = None) -> Dict:
    """
    在VaM窗口中找到指定文字并点击。

    background=True (默认): 后台PostMessage点击，不抢焦点/不移鼠标
    background=False: 前台pyautogui点击，需聚焦窗口
    """
    bg = background if background is not None else BACKGROUND_MODE
    vam_hwnd = hwnd or find_vam_window()
    if not vam_hwnd:
        return {"ok": False, "error": "VaM window not found"}

    if not bg and focus_first:
        focus_window(vam_hwnd)

    result = find_text(target, hwnd=vam_hwnd, exact=exact, min_confidence=min_confidence)
    if "error" in result:
        return result

    matches = result["matches"]
    if not matches:
        return {
            "ok": False,
            "error": f"text not found in VaM: '{target}'",
            "scanned": result["total_scanned"],
        }

    if index >= len(matches):
        index = len(matches) - 1

    item = matches[index]

    if bg:
        # 后台模式: 用图像坐标 + PostMessage
        img_x = item["img_center"]["x"]
        img_y = item["img_center"]["y"]
        click_r = _bg_click(vam_hwnd, img_x, img_y, button=button)
        log.info("click_text '%s' → img(%d,%d) [background]", target, img_x, img_y)
        return {
            "ok": True,
            "clicked": item,
            "x": item["center"]["x"],
            "y": item["center"]["y"],
            "button": button,
            "scan_ms": result["scan_ms"],
            "method": "background",
            "client_x": click_r.get("client_x"),
            "client_y": click_r.get("client_y"),
        }
    else:
        # 前台模式: pyautogui
        x = item["center"]["x"]
        y = item["center"]["y"]
        pag = _init_pyautogui()
        pag.moveTo(x, y)
        time.sleep(0.15)
        if button == "right":
            pag.rightClick()
        elif button == "double":
            pag.doubleClick()
        else:
            pag.click()
        log.info("click_text '%s' → (%d, %d) [foreground]", target, x, y)
        return {
            "ok": True,
            "clicked": item,
            "x": x, "y": y,
            "button": button,
            "scan_ms": result["scan_ms"],
            "method": "foreground",
        }


@_guarded_action
def click_at(x: int, y: int, button: str = "left",
             hwnd: int = None, focus_first: bool = True,
             background: bool = None, is_img_coords: bool = False) -> Dict:
    """
    点击VaM窗口中的指定坐标。

    background=True: x,y为图像坐标，用PostMessage
    background=False: x,y为屏幕坐标，用pyautogui
    is_img_coords: True时x,y为PrintWindow图像坐标
    """
    bg = background if background is not None else BACKGROUND_MODE
    vam_hwnd = hwnd or find_vam_window()

    if bg and vam_hwnd:
        img_x, img_y = x, y
        if not is_img_coords:
            # 屏幕坐标 → 图像坐标
            _ensure_dpi_aware()
            wrect = wt.RECT()
            user32.GetWindowRect(vam_hwnd, ctypes.byref(wrect))
            img_x = x - wrect.left
            img_y = y - wrect.top
        r = _bg_click(vam_hwnd, img_x, img_y, button=button)
        log.info("click_at img(%d,%d) button=%s [background]", img_x, img_y, button)
        return {"ok": True, "x": x, "y": y, "button": button, "method": "background",
                "client_x": r.get("client_x"), "client_y": r.get("client_y")}
    else:
        if focus_first and vam_hwnd:
            focus_window(vam_hwnd)
        pag = _init_pyautogui()
        pag.moveTo(x, y)
        time.sleep(0.15)
        if button == "right":
            pag.rightClick()
        elif button == "double":
            pag.doubleClick()
        else:
            pag.click()
        log.info("click_at (%d, %d) button=%s [foreground]", x, y, button)
        return {"ok": True, "x": x, "y": y, "button": button, "method": "foreground"}


@_guarded_action
def click_relative(rx: float, ry: float, button: str = "left",
                   hwnd: int = None) -> Dict:
    """
    点击VaM窗口中的相对位置。

    rx, ry: 0.0~1.0 相对于窗口的位置比例
    例: click_relative(0.5, 0.5) → 点击窗口正中心
    """
    vam_hwnd = hwnd or find_vam_window()
    if not vam_hwnd:
        return {"ok": False, "error": "VaM window not found"}

    focus_window(vam_hwnd)
    wrect = get_window_rect(vam_hwnd)
    abs_x = int(wrect["x"] + wrect["w"] * rx)
    abs_y = int(wrect["y"] + wrect["h"] * ry)

    return click_at(abs_x, abs_y, button=button, focus_first=False)


@_guarded_action
def press_key(key: str, hwnd: int = None, focus_first: bool = True,
              background: bool = None) -> Dict:
    """
    在VaM中按键。

    background=True: PostMessage发送键盘事件，不抢焦点
    key: 单键如"u"/"f9"，或组合如"ctrl+s"
    """
    bg = background if background is not None else BACKGROUND_MODE
    vam_hwnd = hwnd or find_vam_window()

    if bg and vam_hwnd:
        r = _bg_key(vam_hwnd, key)
        return {"ok": True, "key": key, "method": "background"}
    else:
        if focus_first and vam_hwnd:
            focus_window(vam_hwnd)
        pag = _init_pyautogui()
        parts = key.lower().split("+")
        if len(parts) > 1:
            pag.hotkey(*parts)
        else:
            pag.press(parts[0])
        log.info("press_key '%s' [foreground]", key)
        return {"ok": True, "key": key, "method": "foreground"}


@_guarded_action
def type_text(text: str, hwnd: int = None, interval: float = 0.02,
              focus_first: bool = True, background: bool = None) -> Dict:
    """在VaM中输入文本。background=True时用PostMessage逐字符发送。"""
    bg = background if background is not None else BACKGROUND_MODE
    vam_hwnd = hwnd or find_vam_window()

    if bg and vam_hwnd:
        return _bg_type(vam_hwnd, text)
    else:
        if focus_first and vam_hwnd:
            focus_window(vam_hwnd)
        pag = _init_pyautogui()
        pag.write(text, interval=interval)
        log.info("type_text '%s' [foreground]", text[:50])
        return {"ok": True, "text": text, "length": len(text), "method": "foreground"}


@_guarded_action
def drag(x1: int, y1: int, x2: int, y2: int,
         duration: float = 0.5, hwnd: int = None) -> Dict:
    """在VaM中拖拽（常用于滑块/3D视角旋转）— 仅前台模式"""
    vam_hwnd = hwnd or find_vam_window()
    if vam_hwnd:
        focus_window(vam_hwnd)

    pag = _init_pyautogui()
    pag.moveTo(x1, y1)
    time.sleep(0.1)
    pag.drag(x2 - x1, y2 - y1, duration=duration)

    log.info("drag (%d,%d) → (%d,%d)", x1, y1, x2, y2)
    return {"ok": True, "from": (x1, y1), "to": (x2, y2)}


@_guarded_action
def scroll(clicks: int = 3, x: int = None, y: int = None,
           hwnd: int = None, background: bool = None) -> Dict:
    """在VaM中滚轮。background=True时用PostMessage，不移动真实鼠标。"""
    bg = background if background is not None else BACKGROUND_MODE
    vam_hwnd = hwnd or find_vam_window()

    if bg and vam_hwnd:
        return _bg_scroll(vam_hwnd, clicks, img_x=x, img_y=y)
    else:
        if vam_hwnd:
            focus_window(vam_hwnd)
        pag = _init_pyautogui()
        if x is not None and y is not None:
            pag.moveTo(x, y)
            time.sleep(0.1)
            pag.scroll(clicks)
        else:
            if vam_hwnd:
                _ensure_dpi_aware()
                rect = ctypes.wintypes.RECT()
                user32.GetWindowRect(vam_hwnd, ctypes.byref(rect))
                cx = rect.left + (rect.right - rect.left) // 2
                cy = rect.top + (rect.bottom - rect.top) // 2
                pag.moveTo(cx, cy)
                time.sleep(0.1)
            pag.scroll(clicks)
        log.info("scroll %d clicks at (%s,%s) [foreground]", clicks, x, y)
        return {"ok": True, "clicks": clicks, "x": x, "y": y, "method": "foreground"}


# ═══════════════════════════════════════════════════════════════
# VaM专用操作 — 高层封装
# ═══════════════════════════════════════════════════════════════

def vam_hotkey(action: str) -> Dict:
    """
    执行VaM快捷键操作。

    action: VAM_HOTKEYS中的键名，如 "save", "toggle_ui", "screenshot"
    """
    key = VAM_HOTKEYS.get(action)
    if key is None:
        return {"ok": False, "error": f"unknown VaM hotkey: {action}",
                "available": list(VAM_HOTKEYS.keys())}

    if isinstance(key, list):
        return press_key("+".join(key))
    else:
        return press_key(key)


def navigate_main_menu(target: str) -> Dict:
    """
    导航VaM主菜单。

    target: "hub" | "scene_browser" | "create" | "teaser" | "creator"
    """
    menu_item = VAM_MAIN_MENU.get(target)
    if menu_item is None:
        return {"ok": False, "error": f"unknown menu: {target}",
                "available": list(VAM_MAIN_MENU.keys())}

    # 先尝试英文文字
    result = click_text(menu_item["text"])
    if result.get("ok"):
        return result

    # 降级尝试中文文字
    alt = menu_item.get("alt")
    if alt:
        result = click_text(alt)
        if result.get("ok"):
            return result

    return {"ok": False, "error": f"menu '{target}' not found on screen",
            "tried": [menu_item["text"], alt]}


def wait_for_text(target: str, timeout: float = 30.0,
                  interval: float = 2.0, hwnd: int = None) -> Dict:
    """
    等待VaM界面出现指定文字。

    target: 期待出现的文字
    timeout: 最大等待秒数
    interval: 扫描间隔
    返回: {"found": True/False, "elapsed": 5.2, "match": {...}}
    """
    start = time.time()
    while time.time() - start < timeout:
        result = find_text(target, hwnd=hwnd)
        if result.get("count", 0) > 0:
            return {
                "found": True,
                "elapsed": round(time.time() - start, 1),
                "match": result["matches"][0],
                "scan_ms": result["scan_ms"],
            }
        time.sleep(interval)

    return {
        "found": False,
        "elapsed": round(time.time() - start, 1),
        "target": target,
    }


def verify_screen(expected_texts: List[str], hwnd: int = None) -> Dict:
    """
    验证VaM当前界面是否包含预期文字。

    expected_texts: 期待出现的文字列表
    返回: {"all_found": True/False, "found": [...], "missing": [...]}
    """
    result = scan(hwnd=hwnd)
    if "error" in result:
        return result

    all_texts = " ".join([t["text"] for t in result["texts"]]).lower()

    found = []
    missing = []
    for exp in expected_texts:
        if exp.lower() in all_texts:
            found.append(exp)
        else:
            missing.append(exp)

    return {
        "all_found": len(missing) == 0,
        "found": found,
        "missing": missing,
        "total_scanned": result["total"],
        "scan_ms": result["scan_ms"],
    }


def get_vam_state() -> Dict:
    """
    获取VaM当前状态快照。

    返回: {
        "running": bool,
        "window": {...} or None,
        "focused": bool,
        "screen_texts": [...],
        "detected_page": "main_menu" | "scene_editor" | "scene_browser" | "unknown",
    }
    """
    running = is_vam_running()
    if not running:
        return {"running": False, "window": None, "focused": False,
                "screen_texts": [], "detected_page": "not_running"}

    hwnd = find_vam_window()
    if hwnd is None:
        return {"running": True, "window": None, "focused": False,
                "screen_texts": [], "detected_page": "window_not_found"}

    win_info = get_window_info(hwnd)
    is_focused = user32.GetForegroundWindow() == hwnd

    # OCR扫描当前界面
    scan_result = scan(hwnd=hwnd)
    texts = [t["text"] for t in scan_result.get("texts", [])]

    # 推断当前页面
    page = _detect_page(texts)

    return {
        "running": True,
        "window": win_info,
        "focused": is_focused,
        "screen_texts": texts[:30],
        "detected_page": page,
        "scan_ms": scan_result.get("scan_ms"),
    }


def _detect_page(texts: List[str]) -> str:
    """根据OCR文字推断VaM当前页面（支持中英文混合）"""
    all_text = " ".join(texts).lower()

    # 主菜单特征: 同时包含 Scene Browser + Create (或中文等价)
    main_menu_markers = [
        ("scene browser" in all_text and "create" in all_text),
        ("场景浏览器" in all_text and "场景" in all_text),
        ("vam hub" in all_text and "scene browser" in all_text),
        ("hub商城" in all_text and "场景浏览器" in all_text),
    ]
    if any(main_menu_markers):
        return "main_menu"

    # 场景浏览器特征: 排序/收藏/筛选等列表操作UI
    browser_markers = [
        "sort" in all_text or "filter" in all_text,
        "排序" in all_text or "收藏夹" in all_text,
        "从新到旧" in all_text or "从旧到新" in all_text,
        "显示隐藏" in all_text,
    ]
    if sum(browser_markers) >= 2:
        return "scene_browser"
    if ("scene browser" in all_text or "场景浏览器" in all_text) and sum(browser_markers) >= 1:
        return "scene_browser"

    # 场景编辑器特征
    editor_keywords = ["control", "clothing", "morphs", "plugins", "animation",
                       "physics", "female", "male", "pose", "select"]
    editor_count = sum(1 for kw in editor_keywords if kw in all_text)
    if editor_count >= 2:
        return "scene_editor"

    # Atom选择面板
    if "add atom" in all_text or ("person" in all_text and "empty" in all_text):
        return "atom_selector"

    # 加载/保存对话框
    if "save scene" in all_text or "load scene" in all_text:
        return "save_load_dialog"

    # Hub页面
    if "hub" in all_text and ("download" in all_text or "free" in all_text):
        return "hub"

    # 场景预览/播放模式（含UI覆盖菜单）
    if "编辑模式" in all_text or "游玩模式" in all_text or "edit mode" in all_text:
        return "scene_preview"
    if len(texts) <= 5 and ("vam" in all_text or "x vam" in all_text):
        return "scene_preview"

    return "unknown"


# ═══════════════════════════════════════════════════════════════
# 复合工作流 — VaM常见操作序列
# ═══════════════════════════════════════════════════════════════

def open_scene(scene_name: str = None) -> Dict:
    """打开场景浏览器并（可选）搜索指定场景"""
    steps = []

    # 1. 导航到场景浏览器
    result = navigate_main_menu("scene_browser")
    steps.append({"action": "navigate_scene_browser", "result": result})
    if not result.get("ok"):
        return {"ok": False, "steps": steps, "error": "cannot navigate to scene browser"}

    time.sleep(2)

    # 2. 如果指定了场景名，搜索它
    if scene_name:
        # 等待搜索框出现
        wait = wait_for_text("Search", timeout=10)
        if wait.get("found"):
            click_result = click_text("Search")
            steps.append({"action": "click_search", "result": click_result})
            time.sleep(0.5)
            type_result = type_text(scene_name, focus_first=False)
            steps.append({"action": "type_scene_name", "result": type_result})
        else:
            steps.append({"action": "search_not_found", "result": wait})

    return {"ok": True, "steps": steps}


def create_new_scene() -> Dict:
    """创建新场景"""
    steps = []

    # 1. 导航到Create
    result = navigate_main_menu("create")
    steps.append({"action": "navigate_create", "result": result})
    if not result.get("ok"):
        # 降级：尝试快捷键
        result = vam_hotkey("new_scene")
        steps.append({"action": "hotkey_new_scene", "result": result})

    time.sleep(2)

    # 2. 验证进入编辑器
    verify = verify_screen(["Control", "Plugins"])
    steps.append({"action": "verify_editor", "result": verify})

    return {"ok": True, "steps": steps}


def save_current_scene() -> Dict:
    """保存当前场景"""
    return vam_hotkey("save")


def toggle_ui() -> Dict:
    """显示/隐藏VaM UI"""
    return vam_hotkey("toggle_ui")


def take_vam_screenshot() -> Dict:
    """使用VaM内部截图功能"""
    return vam_hotkey("screenshot")


# ═══════════════════════════════════════════════════════════════
# 剪贴板操作 — 来自 远程桌面/remote_agent.py (Unicode安全)
# ═══════════════════════════════════════════════════════════════

def get_clipboard() -> Dict:
    """Get clipboard text (Unicode-safe via PowerShell)."""
    try:
        r = subprocess.run(
            ['powershell', '-NoProfile', '-Command', 'Get-Clipboard -Raw'],
            capture_output=True, timeout=5
        )
        raw = r.stdout
        if not raw:
            return {"text": "", "ok": True}
        for enc in ['utf-8', 'gbk', 'cp936']:
            try:
                text = raw.decode(enc)
                if '\ufffd' not in text:
                    return {"text": text.rstrip('\r\n'), "ok": True}
            except (UnicodeDecodeError, LookupError):
                continue
        return {"text": raw.decode('utf-8', errors='replace').rstrip('\r\n'), "ok": True}
    except Exception as e:
        return {"text": "", "ok": False, "error": str(e)}


def set_clipboard(text: str) -> Dict:
    """Set clipboard text (Unicode-safe via PowerShell)."""
    try:
        r = subprocess.run(
            ['powershell', '-NoProfile', '-Command', '$input | Set-Clipboard'],
            input=text, capture_output=True, timeout=5,
            encoding='utf-8', errors='replace'
        )
        return {"ok": r.returncode == 0, "length": len(text)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@_guarded_action
def paste_text(text: str, hwnd: int = None) -> Dict:
    """通过剪贴板粘贴文本到VaM（支持中文/Unicode，pyautogui.write不支持）。"""
    clip_result = set_clipboard(text)
    if not clip_result.get("ok"):
        return clip_result
    time.sleep(0.1)
    return press_key("ctrl+v", hwnd=hwnd)


# ═══════════════════════════════════════════════════════════════
# PrintWindow截屏 — 来自 远程桌面/remote_agent.py (RDP兼容)
# ═══════════════════════════════════════════════════════════════

class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


def _ensure_capturable(hwnd: int) -> bool:
    """确保窗口可被PrintWindow截取 — 最小化窗口恢复但不抢焦点。
    SW_SHOWNOACTIVATE(4): 显示窗口不激活，用户无感。
    返回True表示窗口已可截取。"""
    SW_SHOWNOACTIVATE = 4
    if user32.IsIconic(hwnd):
        log.info("Window minimized, restoring without activation (SW_SHOWNOACTIVATE)")
        user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        time.sleep(0.3)
        # 发送到Z-order底部，避免遮挡用户窗口
        HWND_BOTTOM = 1
        SWP_NOACTIVATE = 0x0010
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0,
                            SWP_NOACTIVATE | SWP_NOMOVE | SWP_NOSIZE)
        return not user32.IsIconic(hwnd)
    return True


def capture_printwindow(hwnd: int = None) -> Tuple[Any, Dict]:
    """Capture window via Win32 PrintWindow API.
    Works in RDP sessions where mss/ImageGrab fail.
    自动恢复最小化窗口（不抢焦点）。
    Returns (PIL.Image, rect_dict) or (None, {})."""
    from PIL import Image

    _ensure_dpi_aware()  # 确保GetWindowRect返回物理像素尺寸

    if hwnd is None:
        hwnd = find_vam_window()
    if hwnd is None:
        hwnd = user32.GetDesktopWindow()

    # 最小化窗口恢复（不抢焦点）
    _ensure_capturable(hwnd)

    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0:
        return None, {}

    gdi32 = ctypes.windll.gdi32
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 2)  # PW_RENDERFULLCONTENT

    bmi = _BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
    bmi.biWidth = w
    bmi.biHeight = -h  # top-down
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    buf = (ctypes.c_char * (w * h * 4))()
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)

    gdi32.SelectObject(mdc, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)

    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    if img.getbbox() is None:
        return None, {}

    wrect = {"x": rect.left, "y": rect.top, "w": w, "h": h}
    return img, wrect


# ═══════════════════════════════════════════════════════════════
# 独立测试 — 非侵入模式（不动鼠标键盘）
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")

    print("=" * 60)
    print("VaM GUI 自动化模块 — 非侵入测试")
    print("=" * 60)

    results = {}

    # T1. 模块导入验证
    print("\n[T1] 模块导入验证...")
    try:
        from vam import gui
        print(f"  vam.gui 导入成功, MouseGuard类: {hasattr(gui, 'MouseGuard')}")
        results["import"] = True
    except Exception as e:
        print(f"  导入失败: {e}")
        results["import"] = False

    # T2. DPI感知
    print("\n[T2] DPI感知...")
    try:
        dpi = ctypes.windll.shcore.GetScaleFactorForDevice(0)
        print(f"  DPI缩放: {dpi}%")
        results["dpi"] = dpi
    except Exception:
        results["dpi"] = "unknown"

    # T3. MouseGuard状态
    print("\n[T3] MouseGuard...")
    guard = get_guard()
    status = guard.status()
    print(f"  enabled={status['enabled']}, cooldown={status['cooldown']}s")
    print(f"  can_automate={status['can_automate']}, idle={status['user_idle_seconds']}s")
    results["guard"] = status

    # T4. VaM进程检测
    print("\n[T4] VaM进程检测...")
    running = is_vam_running()
    print(f"  VaM运行中: {running}")
    results["vam_running"] = running

    # T5. VaM窗口检测
    print("\n[T5] VaM窗口检测...")
    hwnd = find_vam_window()
    if hwnd:
        info = get_window_info(hwnd)
        print(f"  hwnd={hwnd}")
        print(f"  标题: {info['title']}")
        print(f"  大小: {info['rect']['w']}x{info['rect']['h']}")
        print(f"  Unity: {info['is_unity']}")
        results["window"] = info
    else:
        print(f"  {'VaM未运行' if not running else '窗口未找到'}")
        results["window"] = None

    # T6. 截屏测试（非侵入：不聚焦窗口，不动鼠标）
    if hwnd:
        print("\n[T6] 截屏测试(mss+PrintWindow级联)...")
        try:
            img, wrect = capture_window(hwnd)
            if img is not None:
                import numpy as np
                arr = np.array(img)
                print(f"  截屏成功: {img.size}, mean={arr.mean():.1f}")
                print(f"  窗口位置: {wrect}")
                results["capture_mss"] = True
            else:
                print(f"  截屏返回None")
                results["capture_mss"] = False
        except Exception as e:
            print(f"  截屏失败: {e}")
            results["capture_mss"] = False

        print("\n[T6b] 截屏测试(PrintWindow)...")
        try:
            pw_img, pw_rect = capture_printwindow(hwnd)
            if pw_img is not None:
                import numpy as np
                arr = np.array(pw_img)
                print(f"  PrintWindow成功: {pw_img.size}, mean={arr.mean():.1f}")
                results["capture_pw"] = True
            else:
                print(f"  PrintWindow返回空")
                results["capture_pw"] = False
        except Exception as e:
            print(f"  PrintWindow失败: {e}")
            results["capture_pw"] = False
    else:
        print("\n[T6] 截屏测试: 跳过(无VaM窗口)")

    # T7. OCR扫描（非侵入：只读截屏）
    if hwnd:
        print("\n[T7] OCR扫描...")
        try:
            scan_result = scan(hwnd=hwnd)
            n = scan_result.get("total", 0)
            ms = scan_result.get("scan_ms", 0)
            print(f"  耗时: {ms}ms, 识别: {n}个文字")
            for item in scan_result.get("texts", [])[:10]:
                c = item["center"]
                print(f"  [{item['confidence']:.2f}] ({c['x']:4d},{c['y']:4d}) {item['text'][:40]}")
            results["ocr"] = {"count": n, "ms": ms}
        except Exception as e:
            print(f"  OCR失败: {e}")
            results["ocr"] = {"error": str(e)}
    else:
        print("\n[T7] OCR扫描: 跳过(无VaM窗口)")

    # T8. 状态推断
    if hwnd:
        print("\n[T8] 状态推断...")
        state = get_vam_state()
        print(f"  当前页面: {state['detected_page']}")
        print(f"  已聚焦: {state['focused']}")
        results["state"] = state["detected_page"]
    else:
        print("\n[T8] 状态推断: 跳过")

    # T9. 剪贴板读取（非侵入：只读）
    print("\n[T9] 剪贴板读取...")
    clip = get_clipboard()
    print(f"  ok={clip['ok']}, length={len(clip.get('text', ''))}")
    results["clipboard"] = clip["ok"]

    # T10. VaM快捷键地图
    print("\n[T10] VaM快捷键地图:")
    for name, key in VAM_HOTKEYS.items():
        print(f"  {name:20s} → {key}")
    results["hotkeys"] = len(VAM_HOTKEYS)

    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总:")
    for k, v in results.items():
        icon = "PASS" if v not in (False, None) else "FAIL"
        print(f"  [{icon}] {k}: {v}")
    print("=" * 60)
