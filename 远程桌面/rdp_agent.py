#!/usr/bin/env python3
"""
rdp_agent.py — 统一RDP远程桌面Agent
====================================
从台式机(或任意主控端)通过remote_agent HTTP API远程控制目标机器。
实现AI Agent的"五感"远程操控：视(截图)·触(输入)·听(音量)·嗅(监控)·味(质量)。

架构:
  主控端 (本脚本)
    ↓ HTTP API
  目标端 (remote_agent.py :9903)
    ↓ pyautogui/win32
  目标桌面应用

用法:
  python rdp_agent.py                           # 交互模式
  python rdp_agent.py --target 192.168.31.179   # 指定目标
  python rdp_agent.py --probe                   # 探测所有可达目标
  python rdp_agent.py --demo                    # 完整演示流程

API (作为模块导入):
  agent = RDPAgent("192.168.31.179")
  agent.screenshot("output.jpg")                # 截图
  agent.click(500, 300)                         # 点击
  agent.key("enter")                            # 按键
  agent.hotkey("ctrl", "s")                     # 组合键
  agent.type_text("hello")                      # 输入文字
  agent.focus("Windsurf")                       # 聚焦窗口
  agent.shell("dir")                            # 执行命令
  agent.five_senses_audit()                     # 五感审计
"""

import json
import time
import os
import sys
import io
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field, asdict


# ============================================================
# 配置
# ============================================================

KNOWN_TARGETS = {
    "laptop": {"ip": "192.168.31.179", "name": "笔记本 zhoumac", "port": 9903},
    "desktop": {"ip": "192.168.31.141", "name": "台式机 DESKTOP-MASTER", "port": 9903},
    "cloud": {"ip": "60.205.171.100", "name": "阿里云ECS", "port": 19903},
}

DEFAULT_PORT = 9903
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_screenshots")


# ============================================================
# 数据模型
# ============================================================

@dataclass
class SenseReport:
    """五感审计报告"""
    target: str
    timestamp: str = ""
    # 视 — Vision
    screenshot_ok: bool = False
    screenshot_latency_ms: int = 0
    screen_resolution: str = ""
    active_window: str = ""
    # 触 — Touch/Input
    click_ok: bool = False
    click_latency_ms: int = 0
    key_ok: bool = False
    key_latency_ms: int = 0
    type_ok: bool = False
    type_latency_ms: int = 0
    # 听 — Hearing
    volume_ok: bool = False
    volume_level: int = -1
    # 嗅 — Risk/Monitoring
    health_ok: bool = False
    ram_percent: float = 0
    disk_free_gb: float = 0
    process_count: int = 0
    is_locked: bool = False
    # 味 — Quality
    avg_latency_ms: int = 0
    issues: List[str] = field(default_factory=list)
    grade: str = "F"

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        lines = [
            f"═══ 五感审计: {self.target} ═══",
            f"时间: {self.timestamp}",
            f"",
            f"👁 视 (Vision):",
            f"  截图: {'✅' if self.screenshot_ok else '❌'} {self.screenshot_latency_ms}ms",
            f"  分辨率: {self.screen_resolution}",
            f"  活跃窗口: {self.active_window}",
            f"",
            f"✋ 触 (Input):",
            f"  点击: {'✅' if self.click_ok else '❌'} {self.click_latency_ms}ms",
            f"  按键: {'✅' if self.key_ok else '❌'} {self.key_latency_ms}ms",
            f"  打字: {'✅' if self.type_ok else '❌'} {self.type_latency_ms}ms",
            f"",
            f"👂 听 (Audio):",
            f"  音量控制: {'✅' if self.volume_ok else '❌'} Level={self.volume_level}",
            f"",
            f"👃 嗅 (Monitoring):",
            f"  健康: {'✅' if self.health_ok else '❌'}",
            f"  内存: {self.ram_percent:.0f}% | 磁盘剩余: {self.disk_free_gb:.1f}GB",
            f"  进程数: {self.process_count} | 锁屏: {self.is_locked}",
            f"",
            f"👅 味 (Quality):",
            f"  平均延迟: {self.avg_latency_ms}ms",
            f"  评级: {self.grade}",
        ]
        if self.issues:
            lines.append(f"  问题({len(self.issues)}):")
            for issue in self.issues:
                lines.append(f"    ⚠️ {issue}")
        return "\n".join(lines)


# ============================================================
# HTTP工具
# ============================================================

def _http_get(url: str, timeout: int = 10) -> Optional[dict]:
    try:
        req = Request(url, headers={"Accept": "application/json", "User-Agent": "RDPAgent/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _http_get_binary(url: str, timeout: int = 15) -> Optional[bytes]:
    try:
        req = Request(url, headers={"User-Agent": "RDPAgent/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


def _http_post(url: str, data: dict = None, timeout: int = 10) -> Optional[dict]:
    try:
        body = json.dumps(data or {}).encode()
        req = Request(url, data=body, headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "RDPAgent/1.0",
        })
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def _timed_call(func, *args, **kwargs) -> Tuple[Any, int]:
    """执行函数并计时，返回 (结果, 毫秒)"""
    t0 = time.perf_counter()
    result = func(*args, **kwargs)
    ms = int((time.perf_counter() - t0) * 1000)
    return result, ms


# ============================================================
# RDPAgent — 主控制类
# ============================================================

class RDPAgent:
    """统一RDP远程控制Agent"""

    def __init__(self, target_ip: str, port: int = DEFAULT_PORT, name: str = ""):
        self.ip = target_ip
        self.port = port
        self.name = name or target_ip
        self.base = f"http://{target_ip}:{port}"
        self._log: List[dict] = []

    def _log_action(self, action: str, detail: str, ok: bool, ms: int):
        entry = {
            "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "action": action,
            "detail": detail[:80],
            "ok": ok,
            "ms": ms,
        }
        self._log.append(entry)
        icon = "✅" if ok else "❌"
        print(f"  {icon} [{action}] {detail[:60]} ({ms}ms)")

    # ── 视 (Vision) ──

    def screenshot(self, save_path: str = None, quality: int = 70, monitor: int = 0) -> Optional[str]:
        """截取远程屏幕，返回保存路径"""
        url = f"{self.base}/screenshot?quality={quality}&monitor={monitor}"
        data, ms = _timed_call(_http_get_binary, url)
        if data:
            if not save_path:
                os.makedirs(SCREENSHOT_DIR, exist_ok=True)
                ts = datetime.now().strftime("%H%M%S")
                save_path = os.path.join(SCREENSHOT_DIR, f"{self.ip}_{ts}.jpg")
            with open(save_path, "wb") as f:
                f.write(data)
            self._log_action("screenshot", f"→ {os.path.basename(save_path)}", True, ms)
            return save_path
        self._log_action("screenshot", "FAILED", False, ms)
        return None

    def screen_info(self) -> Optional[dict]:
        """获取屏幕信息"""
        r, ms = _timed_call(_http_get, f"{self.base}/screen/info")
        ok = bool(r and not r.get("error"))
        self._log_action("screen_info", str(r) if r else "FAILED", ok, ms)
        return r

    def windows(self) -> List[dict]:
        """列出所有窗口"""
        r, ms = _timed_call(_http_get, f"{self.base}/windows")
        wins = (r or {}).get("windows", [])
        self._log_action("windows", f"{len(wins)} windows", bool(r), ms)
        return wins

    # ── 触 (Input) ──

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> bool:
        """在远程屏幕上点击"""
        data = {"x": x, "y": y, "button": button, "clicks": clicks}
        r, ms = _timed_call(_http_post, f"{self.base}/click", data)
        ok = bool(r and not r.get("error"))
        self._log_action("click", f"({x},{y}) {button}", ok, ms)
        return ok

    def double_click(self, x: int, y: int) -> bool:
        """双击"""
        return self.click(x, y, clicks=2)

    def right_click(self, x: int, y: int) -> bool:
        """右键点击"""
        return self.click(x, y, button="right")

    def key(self, key_name: str) -> bool:
        """发送单个按键"""
        data = {"key": key_name}
        r, ms = _timed_call(_http_post, f"{self.base}/key", data)
        ok = bool(r and not r.get("error"))
        self._log_action("key", key_name, ok, ms)
        return ok

    def hotkey(self, *keys) -> bool:
        """发送组合键 (e.g., hotkey('ctrl', 's'))"""
        data = {"hotkey": list(keys)}
        r, ms = _timed_call(_http_post, f"{self.base}/key", data)
        ok = bool(r and not r.get("error"))
        self._log_action("hotkey", "+".join(keys), ok, ms)
        return ok

    def type_text(self, text: str, interval: float = 0.02) -> bool:
        """输入文字"""
        data = {"text": text, "interval": interval}
        r, ms = _timed_call(_http_post, f"{self.base}/type", data)
        ok = bool(r and not r.get("error"))
        self._log_action("type", text[:30], ok, ms)
        return ok

    def move(self, x: int, y: int) -> bool:
        """移动鼠标"""
        data = {"x": x, "y": y}
        r, ms = _timed_call(_http_post, f"{self.base}/move", data)
        ok = bool(r and not r.get("error"))
        self._log_action("move", f"({x},{y})", ok, ms)
        return ok

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> bool:
        """拖拽"""
        data = {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration": duration}
        r, ms = _timed_call(_http_post, f"{self.base}/drag", data)
        ok = bool(r and not r.get("error"))
        self._log_action("drag", f"({x1},{y1})→({x2},{y2})", ok, ms)
        return ok

    def scroll(self, x: int, y: int, clicks: int = 3) -> bool:
        """滚轮"""
        data = {"x": x, "y": y, "clicks": clicks}
        r, ms = _timed_call(_http_post, f"{self.base}/scroll", data)
        ok = bool(r and not r.get("error"))
        self._log_action("scroll", f"({x},{y}) {clicks} clicks", ok, ms)
        return ok

    # ── 听 (Audio) ──

    def volume(self, level: int = None, mute: bool = None) -> Optional[dict]:
        """控制音量"""
        data = {}
        if level is not None:
            data["level"] = level
        if mute is not None:
            data["mute"] = mute
        r, ms = _timed_call(_http_post, f"{self.base}/volume", data)
        ok = bool(r and not r.get("error"))
        self._log_action("volume", str(data), ok, ms)
        return r

    # ── 嗅 (Monitoring) ──

    def health(self) -> Optional[dict]:
        """健康检查"""
        r, ms = _timed_call(_http_get, f"{self.base}/health")
        ok = bool(r and r.get("status") == "ok")
        self._log_action("health", "OK" if ok else "FAIL", ok, ms)
        return r

    def sysinfo(self) -> Optional[dict]:
        """系统信息"""
        r, ms = _timed_call(_http_get, f"{self.base}/sysinfo")
        ok = bool(r and not r.get("error"))
        self._log_action("sysinfo", f"RAM={r.get('ram_percent',0)}%" if r else "FAIL", ok, ms)
        return r

    def processes(self) -> List[dict]:
        """进程列表"""
        r, ms = _timed_call(_http_get, f"{self.base}/processes")
        procs = (r or {}).get("processes", [])
        self._log_action("processes", f"{len(procs)} processes", bool(r), ms)
        return procs

    def clipboard_get(self) -> Optional[str]:
        """获取剪贴板"""
        r, ms = _timed_call(_http_get, f"{self.base}/clipboard")
        ok = bool(r and not r.get("error"))
        text = (r or {}).get("text", "")
        self._log_action("clipboard_get", text[:30] if text else "(empty)", ok, ms)
        return text

    def clipboard_set(self, text: str) -> bool:
        """设置剪贴板"""
        r, ms = _timed_call(_http_post, f"{self.base}/clipboard", {"text": text})
        ok = bool(r and not r.get("error"))
        self._log_action("clipboard_set", text[:30], ok, ms)
        return ok

    # ── 窗口管理 ──

    def focus(self, title: str = None, hwnd: int = None) -> bool:
        """聚焦窗口"""
        data = {}
        if title:
            data["title"] = title
        if hwnd:
            data["hwnd"] = hwnd
        r, ms = _timed_call(_http_post, f"{self.base}/focus", data)
        ok = bool(r and not r.get("error"))
        self._log_action("focus", title or str(hwnd), ok, ms)
        return ok

    def window_action(self, hwnd: int, action: str) -> bool:
        """窗口操作: maximize/minimize/restore/close"""
        data = {"hwnd": hwnd, "action": action}
        r, ms = _timed_call(_http_post, f"{self.base}/window", data)
        ok = bool(r and not r.get("error"))
        self._log_action("window", f"{action} hwnd={hwnd}", ok, ms)
        return ok

    # ── 系统操作 ──

    def shell(self, cmd: str, timeout: int = 15) -> Optional[dict]:
        """在远程执行命令"""
        data = {"cmd": cmd, "timeout": timeout}
        r, ms = _timed_call(_http_post, f"{self.base}/shell", data)
        ok = bool(r and not r.get("error"))
        output = (r or {}).get("stdout", "")[:60]
        self._log_action("shell", f"{cmd[:40]} → {output}", ok, ms)
        return r

    def kill(self, pid: int = None, name: str = None, force: bool = False) -> bool:
        """杀死进程"""
        data = {"force": force}
        if pid:
            data["pid"] = pid
        if name:
            data["name"] = name
        r, ms = _timed_call(_http_post, f"{self.base}/kill", data)
        ok = bool(r and not r.get("error"))
        self._log_action("kill", f"pid={pid} name={name}", ok, ms)
        return ok

    # ── 安全输入 (防焦点劫持) ──

    def verify_focus(self, expected_title: str) -> bool:
        """验证当前活跃窗口是否匹配预期标题"""
        si = self.screen_info()
        if not si:
            return False
        active = si.get("active_window", "")
        expected_lower = expected_title.lower()
        active_lower = active.lower()
        match = expected_lower in active_lower or active_lower in expected_lower
        if not match:
            self._log_action("verify_focus", f"MISMATCH: expected='{expected_title}' actual='{active}'", False, 0)
        else:
            self._log_action("verify_focus", f"OK: '{active}'", True, 0)
        return match

    def safe_type(self, text: str, expected_window: str = None, interval: float = 0.02) -> bool:
        """安全输入文字 — 先验证焦点窗口，防止打字到错误窗口"""
        if expected_window:
            if not self.verify_focus(expected_window):
                print(f"  ⛔ BLOCKED: 焦点窗口不是 '{expected_window}'，拒绝输入")
                return False
        return self.type_text(text, interval)

    def safe_hotkey(self, *keys, expected_window: str = None) -> bool:
        """安全组合键 — 先验证焦点窗口"""
        if expected_window:
            if not self.verify_focus(expected_window):
                print(f"  ⛔ BLOCKED: 焦点窗口不是 '{expected_window}'，拒绝输入")
                return False
        return self.hotkey(*keys)

    def safe_key(self, key_name: str, expected_window: str = None) -> bool:
        """安全按键 — 先验证焦点窗口"""
        if expected_window:
            if not self.verify_focus(expected_window):
                print(f"  ⛔ BLOCKED: 焦点窗口不是 '{expected_window}'，拒绝输入")
                return False
        return self.key(key_name)

    def focus_and_verify(self, title: str, retries: int = 3) -> bool:
        """聚焦窗口并验证成功"""
        import time as _time
        for i in range(retries):
            self.focus(title)
            _time.sleep(0.5)
            if self.verify_focus(title):
                return True
            _time.sleep(0.5)
        return False

    # ── 高级操作 ──

    def launch_app(self, exe_path: str, wait_sec: int = 3) -> bool:
        """启动远程应用"""
        r = self.shell(f'start "" "{exe_path}"', timeout=10)
        if r and not r.get("error"):
            time.sleep(wait_sec)
            return True
        return False

    def find_window(self, keyword: str) -> Optional[dict]:
        """按关键词查找窗口"""
        wins = self.windows()
        keyword_lower = keyword.lower()
        for w in wins:
            if keyword_lower in str(w.get("title", "")).lower():
                return w
        return None

    def wait_for_window(self, keyword: str, timeout: int = 30, interval: float = 1.0) -> Optional[dict]:
        """等待窗口出现"""
        end_time = time.time() + timeout
        while time.time() < end_time:
            w = self.find_window(keyword)
            if w:
                return w
            time.sleep(interval)
        return None

    # ── 五感审计 ──

    def five_senses_audit(self) -> SenseReport:
        """完整五感审计"""
        report = SenseReport(target=f"{self.name} ({self.ip}:{self.port})")
        report.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        latencies = []

        print(f"\n{'='*50}")
        print(f"五感审计: {self.name} ({self.ip})")
        print(f"{'='*50}")

        # 👁 视 — Vision
        print("\n👁 视 (Vision)...")
        path = self.screenshot(quality=60)
        if path:
            report.screenshot_ok = True
            report.screenshot_latency_ms = self._log[-1]["ms"]
            latencies.append(report.screenshot_latency_ms)

        si = self.screen_info()
        if si:
            report.screen_resolution = f"{si.get('screen_w', 0)}x{si.get('screen_h', 0)}"
            report.active_window = si.get("active_window", "")

        # ✋ 触 — Input (安全测试: 移动到安全位置，不实际点击)
        print("\n✋ 触 (Input)...")
        # 测试move而非click，避免干扰用户
        move_r, move_ms = _timed_call(_http_post, f"{self.base}/move", {"x": 1, "y": 1})
        report.click_ok = bool(move_r and not (move_r or {}).get("error"))
        report.click_latency_ms = move_ms
        latencies.append(move_ms)
        self._log_action("input_test(move)", "safe position (1,1)", report.click_ok, move_ms)

        # 测试按键: 发送无害的键(VK_NONAME or just query)
        key_r, key_ms = _timed_call(_http_post, f"{self.base}/key", {"key": "shift"})
        report.key_ok = bool(key_r and not (key_r or {}).get("error"))
        report.key_latency_ms = key_ms
        latencies.append(key_ms)
        self._log_action("input_test(key)", "shift (harmless)", report.key_ok, key_ms)

        report.type_ok = report.key_ok  # 如果key能用, type也能用
        report.type_latency_ms = key_ms

        # 👂 听 — Audio
        print("\n👂 听 (Audio)...")
        vol_r = self.volume()
        if vol_r and not vol_r.get("error"):
            report.volume_ok = True
            report.volume_level = vol_r.get("level", -1)

        # 👃 嗅 — Monitoring
        print("\n👃 嗅 (Monitoring)...")
        h = self.health()
        report.health_ok = bool(h and h.get("status") == "ok")

        sys_r = self.sysinfo()
        if sys_r:
            report.ram_percent = sys_r.get("ram_percent", 0)
            report.disk_free_gb = sys_r.get("disk_free_gb", 0)
            report.is_locked = sys_r.get("is_locked", False)

        # 进程数通过shell获取（processes API可能有编码问题）
        ps_r = self.shell('(Get-Process).Count', timeout=5)
        if ps_r and ps_r.get("stdout"):
            try:
                report.process_count = int(ps_r["stdout"].strip())
            except ValueError:
                pass

        # 👅 味 — Quality Assessment
        print("\n👅 味 (Quality)...")
        if latencies:
            report.avg_latency_ms = sum(latencies) // len(latencies)

        # 问题检测
        if report.screenshot_latency_ms > 1000:
            report.issues.append(f"截图延迟过高: {report.screenshot_latency_ms}ms (>1000ms)")
        if report.ram_percent > 85:
            report.issues.append(f"内存使用率过高: {report.ram_percent:.0f}% (>85%)")
        if report.disk_free_gb < 10:
            report.issues.append(f"磁盘剩余不足: {report.disk_free_gb:.1f}GB (<10GB)")
        if report.is_locked:
            report.issues.append("屏幕已锁定: 无法看到桌面内容")
        if not report.screenshot_ok:
            report.issues.append("截图失败: 视觉感官断裂")
        if not report.click_ok:
            report.issues.append("输入失败: 触觉感官断裂")
        if not report.volume_ok:
            report.issues.append("音量控制失败: 听觉感官断裂")
        if report.avg_latency_ms > 500:
            report.issues.append(f"平均延迟偏高: {report.avg_latency_ms}ms (>500ms)")

        # 评级
        score = 0
        if report.screenshot_ok:
            score += 25
        if report.click_ok and report.key_ok:
            score += 25
        if report.volume_ok:
            score += 15
        if report.health_ok:
            score += 15
        if report.avg_latency_ms < 500:
            score += 10
        if not report.issues:
            score += 10

        if score >= 90:
            report.grade = "A"
        elif score >= 75:
            report.grade = "B"
        elif score >= 60:
            report.grade = "C"
        elif score >= 40:
            report.grade = "D"
        else:
            report.grade = "F"

        print(f"\n{report.summary()}")
        return report


# ============================================================
# 多目标探测
# ============================================================

def probe_all_targets() -> Dict[str, dict]:
    """探测所有已知目标的可达性"""
    results = {}
    print("\n🔍 探测所有已知目标...\n")
    for alias, info in KNOWN_TARGETS.items():
        ip = info["ip"]
        port = info["port"]
        name = info["name"]
        url = f"http://{ip}:{port}/health"
        try:
            r, ms = _timed_call(_http_get, url, 5)
            if r and r.get("status") == "ok":
                status = "✅ 在线"
                hostname = r.get("hostname", "?")
                user = r.get("user", "?")
                session = r.get("session", "?")
                print(f"  {status} {alias:10s} | {name} | {ip}:{port} | {ms}ms")
                print(f"         host={hostname} user={user} session={session}")
                results[alias] = {"ok": True, "ms": ms, "info": r}
            else:
                print(f"  ❌ 离线 {alias:10s} | {name} | {ip}:{port}")
                results[alias] = {"ok": False}
        except Exception:
            print(f"  ❌ 不可达 {alias:10s} | {name} | {ip}:{port}")
            results[alias] = {"ok": False}
    return results


# ============================================================
# 演示流程
# ============================================================

def demo_remote_control(target_ip: str = "192.168.31.179"):
    """完整演示: 远程控制目标机器"""
    agent = RDPAgent(target_ip, name="笔记本")

    print("=" * 60)
    print("🎬 RDP Agent 远程控制演示")
    print(f"   目标: {target_ip}")
    print("=" * 60)

    # Step 1: 五感审计
    print("\n📋 Step 1: 五感审计...")
    report = agent.five_senses_audit()

    if not report.health_ok:
        print("\n❌ 目标不可达，中止演示")
        return report

    # Step 2: 远程截图 — 看到远端桌面
    print("\n📸 Step 2: 获取远端桌面视野...")
    path = agent.screenshot(quality=80)
    if path:
        print(f"   桌面截图已保存: {path}")

    # Step 3: 查看远端窗口
    print("\n🪟 Step 3: 列举远端窗口...")
    si = agent.screen_info()
    if si:
        print(f"   分辨率: {si.get('screen_w')}x{si.get('screen_h')}")
        print(f"   活跃窗口: {si.get('active_window')}")

    # Step 4: 远程执行命令
    print("\n💻 Step 4: 远程执行命令...")
    r = agent.shell("hostname && whoami && echo %COMPUTERNAME%", timeout=5)
    if r:
        print(f"   输出: {r.get('stdout', '').strip()}")

    # Step 5: 获取远端剪贴板
    print("\n📋 Step 5: 远端剪贴板...")
    clip = agent.clipboard_get()
    if clip:
        print(f"   剪贴板内容: {clip[:50]}...")

    # Step 6: 总结
    print("\n" + "=" * 60)
    print(f"🏁 演示完成 | 总操作: {len(agent._log)}")
    print(f"   五感评级: {report.grade}")
    if report.issues:
        print(f"   发现问题: {len(report.issues)}")
        for issue in report.issues:
            print(f"     ⚠️ {issue}")
    print("=" * 60)

    return report


# ============================================================
# CLI
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RDP Agent — 统一远程桌面控制")
    parser.add_argument("--target", "-t", default="192.168.31.179", help="目标IP")
    parser.add_argument("--port", "-p", type=int, default=9903, help="目标端口")
    parser.add_argument("--probe", action="store_true", help="探测所有目标")
    parser.add_argument("--demo", action="store_true", help="完整演示流程")
    parser.add_argument("--audit", action="store_true", help="五感审计")
    parser.add_argument("--screenshot", "-s", action="store_true", help="截图")
    parser.add_argument("--shell", help="远程执行命令")
    args = parser.parse_args()

    if args.probe:
        probe_all_targets()
    elif args.demo:
        demo_remote_control(args.target)
    elif args.audit:
        agent = RDPAgent(args.target, args.port)
        agent.five_senses_audit()
    elif args.screenshot:
        agent = RDPAgent(args.target, args.port)
        path = agent.screenshot()
        if path:
            print(f"Saved: {path}")
    elif args.shell:
        agent = RDPAgent(args.target, args.port)
        r = agent.shell(args.shell)
        if r:
            print(r.get("stdout", ""))
            if r.get("stderr"):
                print(f"STDERR: {r['stderr']}", file=sys.stderr)
    else:
        # Default: probe + audit
        probe_all_targets()
        print()
        demo_remote_control(args.target)


if __name__ == "__main__":
    main()
