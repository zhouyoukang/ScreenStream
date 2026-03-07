#!/usr/bin/env python3
"""
rdp_video_agent.py — 统一远程桌面视频剪辑Agent
================================================
整合所有RDP远程控制资源，以剪映(JianYing Pro)为例，
实现AI Agent远程操控电脑完成视频剪辑的全流程。

核心能力:
  1. 多目标管理 — 笔记本/台式机/云服务器统一探测和控制
  2. 屏幕解锁 — tscon自动解锁Windows锁屏(pyautogui无法操作安全桌面)
  3. 坐标校准 — 自动检测分辨率，截图→坐标映射
  4. 应用控制 — JianYing Pro启动/草稿管理/编辑操作
  5. 安全输入 — MouseGuard感知 + 焦点验证 + 剪贴板粘贴
  6. 五感审计 — 视/触/听/嗅/味完整评估

架构:
  本脚本(主控端) → rdp_agent.py(通用RDP控制) → remote_agent.py(:9903 目标端)

用法:
  python rdp_video_agent.py --target laptop                    # 连接笔记本
  python rdp_video_agent.py --target laptop --unlock           # 解锁并连接
  python rdp_video_agent.py --target laptop --app jianying     # 启动剪映
  python rdp_video_agent.py --target laptop --edit "2月5日"    # 打开草稿编辑
  python rdp_video_agent.py --probe                            # 探测所有目标
  python rdp_video_agent.py --demo                             # 完整演示流程
"""

import json
import time
import os
import sys
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any

# 导入基础RDP Agent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rdp_agent import RDPAgent, probe_all_targets, KNOWN_TARGETS, SCREENSHOT_DIR


# ============================================================
# 配置
# ============================================================

APPS = {
    "jianying": {
        "name": "剪映专业版",
        "exe": r"C:\Users\{user}\AppData\Local\JianyingPro\Apps\JianyingPro.exe",
        "window_title": "剪映专业版",
        "drafts_dir": r"E:\JianyingPro Drafts",
        "ffmpeg": r"C:\Users\{user}\AppData\Local\JianyingPro\Apps\7.6.0.12636\ffmpeg.exe",
    },
    "wps": {
        "name": "WPS Office",
        "exe": r"C:\Users\{user}\AppData\Local\Kingsoft\WPS Office\ksolaunch.exe",
        "window_title": "WPS",
    },
    "edge": {
        "name": "Microsoft Edge",
        "exe": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "window_title": "Edge",
    },
}

# 截图缩放因子 — remote_agent截图为屏幕分辨率的一半
# DPI坐标系统全景 (2026-03-03 破案):
#   物理面板原生: 2560x1600 (mss/pyautogui在独立Python进程中报告)
#   remote_agent进程: 1920x1200 (DPI-unaware, screen_info/pyautogui/mss均为此值)
#   截图(scale=50%): 960x600 = 1920x1200 × 0.5
#   WinForms: 1280x800 (System.Windows.Forms.Screen)
#   MonitorScale: 200% / SystemDPI: 100%
# 关键: remote_agent的pyautogui.click()使用1920x1200坐标空间
# 从截图像素×2 = pyautogui点击坐标 ✅已验证
SCREENSHOT_SCALE = 2

# 已知问题和解决方案
KNOWN_ISSUES = {
    "screen_locked": {
        "symptom": "screenshot返回SCREEN LOCKED",
        "cause": "Windows安全桌面，pyautogui无法操作",
        "fix": "tscon {session_id} /dest:console",
    },
    "mouseguard_block": {
        "symptom": "click返回blocked=true",
        "cause": "用户鼠标活动触发MouseGuard冷却",
        "fix": "等待cooldown秒后重试，或暂停guard",
    },
    "coordinate_mismatch": {
        "symptom": "点击位置偏移",
        "cause": "remote_agent进程DPI-unaware→1920x1200; 独立Python进程→2560x1600; 截图960x600",
        "fix": "截图坐标×SCREENSHOT_SCALE(2)=pyautogui坐标; screen_info确认当前分辨率",
    },
    "uia_uwp_slow": {
        "symptom": "UI Automation深树遍历UWP应用超时",
        "cause": "FindAll(TreeScope_Descendants)在Settings等UWP窗口需>20s",
        "fix": "用TreeScope_Children逐层搜索; 或用screenshot+坐标方式",
    },
    "shell_gbk": {
        "symptom": "UnicodeDecodeError: gbk codec",
        "cause": "exec_shell默认GBK解码UTF-8输出",
        "fix": "encoding='utf-8', errors='replace' (已修复)",
    },
    "qt_doubleclick": {
        "symptom": "双击草稿缩略图不打开编辑界面",
        "cause": "JianYing Qt6框架不响应pyautogui的doubleClick事件",
        "fix": "使用'开始创作'按钮或命令行启动; 文件对话框用地址栏路径粘贴",
    },
    "focus_hijack": {
        "symptom": "输入内容打到错误窗口",
        "cause": "QQ等应用抢夺焦点",
        "fix": "使用safe_type/safe_hotkey + verify_focus",
    },
    "chinese_input": {
        "symptom": "中文输入乱码或丢字",
        "cause": "IME状态不确定",
        "fix": "clipboard_set + Ctrl+V粘贴",
    },
}


# ============================================================
# VideoAgent — 视频剪辑专用Agent
# ============================================================

class VideoAgent:
    """远程视频剪辑Agent — 封装RDPAgent + 应用级操作"""

    def __init__(self, target: str = "laptop"):
        if target in KNOWN_TARGETS:
            info = KNOWN_TARGETS[target]
            self.agent = RDPAgent(info["ip"], info["port"], info["name"])
        else:
            self.agent = RDPAgent(target)
        self.target_name = target
        self.screen_w = 0
        self.screen_h = 0
        self.user = ""
        self.session_id = -1
        self._issues_found: List[str] = []
        self._issues_fixed: List[str] = []

    # ── 连接与状态 ──

    def connect(self) -> bool:
        """连接目标并获取基本信息"""
        h = self.agent.health()
        if not h or h.get("status") != "ok":
            print(f"❌ 无法连接 {self.target_name}")
            return False

        self.user = h.get("user", "")
        self.session_id = -1
        print(f"✅ 已连接: {h.get('hostname')} | user={self.user} | session={h.get('session')}")

        # 检查屏幕状态
        si = self.agent.screen_info()
        if si:
            self.screen_w = si.get("screen_w", 0)
            self.screen_h = si.get("screen_h", 0)
            self.session_id = si.get("session_id", -1)

            if si.get("is_locked"):
                self._issues_found.append("screen_locked")
                print(f"⚠️ 屏幕已锁定 (session_id={self.session_id})")
                return True  # 连接成功但需要解锁

            print(f"📺 分辨率: {self.screen_w}x{self.screen_h} | 活跃窗口: {si.get('active_window')}")

        return True

    def unlock_screen(self) -> bool:
        """解锁Windows锁屏 — 使用tscon将RDP会话重连到控制台"""
        si = self.agent.screen_info()
        if not si or not si.get("is_locked"):
            print("ℹ️ 屏幕未锁定，无需解锁")
            return True

        session_id = si.get("session_id", self.session_id)
        if session_id < 0:
            # 尝试通过query session获取
            r = self.agent.shell("query session", timeout=5)
            if r and r.get("stdout"):
                for line in r["stdout"].split("\n"):
                    if "Active" in line:
                        parts = line.split()
                        for p in parts:
                            if p.isdigit():
                                session_id = int(p)
                                break

        if session_id < 0:
            print("❌ 无法确定session ID，无法解锁")
            return False

        print(f"🔓 正在解锁... tscon {session_id} /dest:console")
        r = self.agent.shell(f"tscon {session_id} /dest:console", timeout=10)

        time.sleep(3)  # 等待会话切换

        si2 = self.agent.screen_info()
        if si2 and not si2.get("is_locked"):
            self.screen_w = si2.get("screen_w", 0)
            self.screen_h = si2.get("screen_h", 0)
            print(f"✅ 解锁成功! 新分辨率: {self.screen_w}x{self.screen_h}")
            self._issues_fixed.append("screen_locked → tscon解锁")

            # 注意: tscon后分辨率可能变化(RDP→物理屏幕)
            if self.screen_w != 2560:
                self._issues_found.append("coordinate_mismatch")
                print(f"⚠️ 分辨率从RDP切换到物理屏幕 → 坐标需重新校准")
            return True

        print("❌ 解锁失败")
        return False

    def ensure_ready(self) -> bool:
        """确保目标可用 — 连接 + 解锁 + 验证"""
        if not self.connect():
            return False
        if "screen_locked" in self._issues_found:
            if not self.unlock_screen():
                return False
        return True

    # ── 坐标系统 ──

    def get_resolution(self) -> Tuple[int, int]:
        """获取当前实际分辨率"""
        si = self.agent.screen_info()
        if si:
            self.screen_w = si.get("screen_w", 0)
            self.screen_h = si.get("screen_h", 0)
        return self.screen_w, self.screen_h

    def screenshot_to_screen(self, ss_x: int, ss_y: int) -> Tuple[int, int]:
        """截图像素坐标 → 屏幕坐标
        
        remote_agent截图为半分辨率, 从截图上量出的像素位置需×2
        """
        return ss_x * SCREENSHOT_SCALE, ss_y * SCREENSHOT_SCALE

    def pct_to_px(self, pct_x: float, pct_y: float) -> Tuple[int, int]:
        """百分比坐标 → 像素坐标 (分辨率无关)
        
        用法: pct_to_px(0.5, 0.5) → 屏幕中心
              pct_to_px(0.1, 0.3) → 左侧30%高度处
        """
        if not self.screen_w:
            self.get_resolution()
        return int(self.screen_w * pct_x), int(self.screen_h * pct_y)

    def safe_click(self, pct_x: float, pct_y: float, clicks: int = 1,
                   button: str = "left", retry: int = 2) -> bool:
        """安全点击 — 百分比坐标 + MouseGuard重试"""
        x, y = self.pct_to_px(pct_x, pct_y)
        for attempt in range(retry + 1):
            ok = self.agent.click(x, y, button, clicks)
            if ok:
                return True
            # 检查是否被MouseGuard阻止
            time.sleep(3)  # 等待cooldown
        return False

    # ── 应用管理 ──

    def launch_app(self, app_key: str, wait_sec: int = 5) -> bool:
        """启动远程应用"""
        if app_key not in APPS:
            print(f"❌ 未知应用: {app_key}. 可选: {list(APPS.keys())}")
            return False

        app = APPS[app_key]
        exe = app["exe"].format(user=self.user)
        title = app["window_title"]

        # 检查是否已在运行
        w = self.agent.find_window(title)
        if w:
            print(f"ℹ️ {app['name']} 已在运行 (hwnd={w['hwnd']})")
            self.agent.focus(hwnd=w["hwnd"])
            time.sleep(0.5)
            return True

        print(f"🚀 启动 {app['name']}...")
        r = self.agent.shell(f'start "" "{exe}"', timeout=10)
        if not r or r.get("error"):
            print(f"❌ 启动失败: {r}")
            return False

        # 等待窗口出现
        w = self.agent.wait_for_window(title, timeout=wait_sec * 2)
        if w:
            print(f"✅ {app['name']} 已启动 (hwnd={w['hwnd']})")
            return True

        print(f"⚠️ {app['name']} 可能正在加载...")
        return True  # 可能还在加载中

    def maximize_app(self, app_key: str) -> bool:
        """最大化应用窗口"""
        app = APPS[app_key]
        w = self.agent.find_window(app["window_title"])
        if w:
            self.agent.window_action(w["hwnd"], "maximize")
            self.agent.focus(hwnd=w["hwnd"])
            time.sleep(0.5)
            return True
        return False

    def close_app(self, app_key: str) -> bool:
        """关闭应用"""
        app = APPS[app_key]
        w = self.agent.find_window(app["window_title"])
        if w:
            self.agent.window_action(w["hwnd"], "close")
            return True
        return False

    # ── 剪映专用操作 ──

    def jianying_list_drafts(self) -> List[Dict]:
        """列出剪映草稿项目"""
        drafts_dir = APPS["jianying"]["drafts_dir"]
        r = self.agent.shell(f'dir /b "{drafts_dir}"', timeout=5)
        if not r or not r.get("stdout"):
            return []

        drafts = []
        for name in r["stdout"].strip().split("\n"):
            name = name.strip()
            if not name:
                continue
            # 获取草稿大小
            r2 = self.agent.shell(
                f'powershell -c "(Get-ChildItem \'{drafts_dir}\\{name}\' -Recurse | '
                f'Measure-Object -Property Length -Sum).Sum"',
                timeout=8
            )
            size_bytes = 0
            if r2 and r2.get("stdout"):
                try:
                    size_bytes = int(r2["stdout"].strip())
                except ValueError:
                    pass

            drafts.append({
                "name": name,
                "path": f"{drafts_dir}\\{name}",
                "size_mb": round(size_bytes / 1024 / 1024, 1),
            })

        return drafts

    def jianying_open_draft(self, draft_name: str) -> bool:
        """通过命令行打开剪映草稿"""
        drafts_dir = APPS["jianying"]["drafts_dir"]
        draft_path = f"{drafts_dir}\\{draft_name}"

        # 检查草稿是否存在
        r = self.agent.shell(f'if exist "{draft_path}\\draft_content.json" echo EXISTS', timeout=5)
        if not r or "EXISTS" not in (r.get("stdout") or ""):
            print(f"❌ 草稿不存在: {draft_path}")
            return False

        # 方法1: 直接用JianYing打开草稿目录
        exe = APPS["jianying"]["exe"].format(user=self.user)
        self.agent.shell(f'start "" "{exe}" "{draft_path}"', timeout=5)
        time.sleep(5)

        # 验证是否打开了编辑界面
        si = self.agent.screen_info()
        if si:
            active = si.get("active_window", "")
            if "剪映" in active:
                print(f"✅ 草稿已打开: {draft_name}")
                return True

        # 方法2: 如果方法1失败，用键盘导航
        print("⚠️ 尝试键盘导航打开草稿...")
        return self._jianying_navigate_to_draft(draft_name)

    def _jianying_navigate_to_draft(self, draft_name: str) -> bool:
        """通过键盘导航在剪映中打开草稿"""
        # 确保剪映在前台
        self.maximize_app("jianying")
        time.sleep(1)

        # 使用Tab和方向键导航到草稿列表
        # Tab切换到草稿区域，Enter打开
        self.agent.key("tab")
        time.sleep(0.3)
        self.agent.key("tab")
        time.sleep(0.3)
        self.agent.key("enter")
        time.sleep(3)

        si = self.agent.screen_info()
        if si and "剪映" in si.get("active_window", ""):
            print(f"✅ 编辑界面已打开")
            return True

        return False

    def jianying_add_text(self, text: str) -> bool:
        """在剪映中添加文字 — 安全输入方式"""
        if not self.agent.verify_focus("剪映"):
            self.maximize_app("jianying")
            time.sleep(0.5)

        # 点击"文本"按钮 (编辑界面顶部工具栏)
        # 使用百分比坐标，分辨率无关
        self.safe_click(0.06, 0.04)  # 文本按钮大致位置
        time.sleep(1)

        # 使用剪贴板粘贴(最可靠的中文输入方式)
        self.agent.clipboard_set(text)
        self.agent.hotkey("ctrl", "v")
        time.sleep(0.5)
        self.agent.key("enter")

        print(f"✅ 已添加文字: {text[:30]}")
        return True

    def jianying_export(self, output_name: str = None) -> bool:
        """导出剪映项目"""
        if not self.agent.verify_focus("剪映"):
            self.maximize_app("jianying")

        # 点击"导出"按钮 (右上角)
        self.safe_click(0.89, 0.02)
        time.sleep(2)

        # 如果需要改名
        if output_name:
            self.agent.clipboard_set(output_name)
            self.agent.hotkey("ctrl", "a")
            time.sleep(0.2)
            self.agent.hotkey("ctrl", "v")
            time.sleep(0.3)

        # 点击导出确认
        self.safe_click(0.65, 0.85)
        time.sleep(1)

        print(f"📤 导出中... (文件名: {output_name or '默认'})")
        return True

    def jianying_screenshot_editing(self) -> Optional[str]:
        """截取剪映编辑界面"""
        path = self.agent.screenshot(quality=85)
        if path:
            print(f"📸 编辑界面截图: {path}")
        return path

    # ── 视频文件操作 ──

    def find_videos(self, search_dirs: List[str] = None, max_results: int = 20) -> List[Dict]:
        """搜索远程机器上的视频文件"""
        if not search_dirs:
            search_dirs = [
                f"C:\\Users\\{self.user}\\Videos",
                f"C:\\Users\\{self.user}\\Desktop",
                f"C:\\Users\\{self.user}\\Downloads",
            ]

        videos = []
        for d in search_dirs:
            r = self.agent.shell(
                f'powershell -c "Get-ChildItem \'{d}\' -Include *.mp4,*.mov,*.avi,*.mkv '
                f'-Recurse -Depth 2 -ErrorAction SilentlyContinue | '
                f'Select-Object -First {max_results} FullName,Length | ConvertTo-Json"',
                timeout=10
            )
            if r and r.get("stdout") and r["stdout"].strip():
                try:
                    items = json.loads(r["stdout"])
                    if isinstance(items, dict):
                        items = [items]
                    for item in items:
                        videos.append({
                            "path": item.get("FullName", ""),
                            "size_mb": round(item.get("Length", 0) / 1024 / 1024, 1),
                        })
                except json.JSONDecodeError:
                    pass

        return videos

    def create_test_video(self, output_path: str = None, duration: int = 5) -> Optional[str]:
        """用ffmpeg创建测试视频"""
        if not output_path:
            output_path = f"C:\\Users\\{self.user}\\Videos\\agent_test_{int(time.time())}.mp4"

        # 使用系统ffmpeg或JianYing的ffmpeg
        ffmpeg_paths = [
            "ffmpeg",  # 系统PATH
            APPS["jianying"]["ffmpeg"].format(user=self.user) if "jianying" in APPS else "",
        ]

        for ffmpeg in ffmpeg_paths:
            if not ffmpeg:
                continue
            cmd = (
                f'"{ffmpeg}" -y -f lavfi -i "color=c=blue:size=1920x1080:d={duration}" '
                f'-f lavfi -i "sine=frequency=440:duration={duration}" '
                f'-c:v libx264 -preset ultrafast -pix_fmt yuv420p -c:a aac '
                f'-shortest "{output_path}" 2>&1'
            )
            r = self.agent.shell(cmd, timeout=30)
            if r and r.get("returncode") == 0:
                print(f"✅ 测试视频已创建: {output_path}")
                return output_path

        print("❌ 无法创建测试视频 (ffmpeg不可用)")
        return None

    # ── 五感诊断 ──

    def diagnose(self) -> Dict:
        """完整五感诊断 — 发现并记录所有问题"""
        print("\n" + "=" * 60)
        print("🔍 远程视频剪辑Agent — 五感诊断")
        print("=" * 60)

        report = {
            "target": self.target_name,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "issues_found": [],
            "issues_fixed": [],
            "capabilities": {},
        }

        # 1. 连接检测
        print("\n📡 连接检测...")
        if not self.connect():
            report["issues_found"].append("无法连接目标")
            return report

        # 2. 屏幕状态
        print("\n📺 屏幕状态...")
        si = self.agent.screen_info()
        if si:
            if si.get("is_locked"):
                report["issues_found"].append(f"屏幕锁定 (session={si.get('session_id')})")
                print("  ⚠️ 屏幕锁定 → 自动解锁...")
                if self.unlock_screen():
                    report["issues_fixed"].append("屏幕锁定 → tscon解锁成功")
                else:
                    report["issues_found"].append("屏幕解锁失败")
            else:
                print(f"  ✅ 屏幕正常: {self.screen_w}x{self.screen_h}")
                report["capabilities"]["screen"] = f"{self.screen_w}x{self.screen_h}"

        # 3. MouseGuard状态
        print("\n🛡️ MouseGuard...")
        h = self.agent.health()
        if h and h.get("guard"):
            g = h["guard"]
            can_auto = g.get("can_automate", False)
            print(f"  Guard: enabled={g.get('enabled')} paused={g.get('paused')} can_automate={can_auto}")
            print(f"  用户空闲: {g.get('user_idle_seconds', 0):.0f}s | 被阻止: {g.get('blocked_count', 0)}次")
            if not can_auto:
                report["issues_found"].append(f"MouseGuard阻止自动化 (用户活跃)")
            report["capabilities"]["mouseguard"] = g

        # 4. 应用检测
        print("\n📱 应用检测...")
        for app_key, app_info in APPS.items():
            exe = app_info["exe"].format(user=self.user)
            r = self.agent.shell(f'if exist "{exe}" echo FOUND', timeout=5)
            installed = r and "FOUND" in (r.get("stdout") or "")

            w = self.agent.find_window(app_info["window_title"])
            running = w is not None

            status = "✅已安装" if installed else "❌未安装"
            if running:
                status += " + 🟢运行中"
            print(f"  {app_info['name']}: {status}")
            report["capabilities"][app_key] = {"installed": installed, "running": running}

        # 5. 剪映草稿
        print("\n📁 剪映草稿...")
        drafts = self.jianying_list_drafts()
        if drafts:
            print(f"  找到 {len(drafts)} 个草稿:")
            for d in drafts[:5]:
                print(f"    {d['name']} ({d['size_mb']}MB)")
            report["capabilities"]["jianying_drafts"] = len(drafts)
        else:
            print("  未找到剪映草稿")
            report["issues_found"].append("未找到剪映草稿目录")

        # 6. 视频素材
        print("\n🎬 视频素材...")
        videos = self.find_videos()
        if videos:
            print(f"  找到 {len(videos)} 个视频文件:")
            for v in videos[:5]:
                print(f"    {os.path.basename(v['path'])} ({v['size_mb']}MB)")
            report["capabilities"]["video_files"] = len(videos)
        else:
            print("  未找到视频文件 → 可用create_test_video()创建")

        # 7. 输入测试
        print("\n⌨️ 输入能力...")
        report["capabilities"]["click"] = self.agent.click(1, 1) is not False
        report["capabilities"]["clipboard"] = self.agent.clipboard_set("agent_test") is not False

        # 汇总
        print("\n" + "=" * 60)
        print(f"📊 诊断结果:")
        print(f"  发现问题: {len(report['issues_found'])}")
        for issue in report["issues_found"]:
            print(f"    ⚠️ {issue}")
        print(f"  已修复: {len(report['issues_fixed'])}")
        for fix in report["issues_fixed"]:
            print(f"    ✅ {fix}")
        print("=" * 60)

        return report

    # ── 完整工作流 ──

    def full_demo(self) -> Dict:
        """完整演示: 连接→解锁→启动剪映→打开草稿→截图→关闭"""
        print("\n" + "=" * 60)
        print("🎬 远程视频剪辑Agent — 完整演示")
        print("=" * 60)

        results = {"steps": [], "success": True}

        def step(name, func, *args, **kwargs):
            print(f"\n📌 Step: {name}")
            try:
                ok = func(*args, **kwargs)
                results["steps"].append({"name": name, "ok": bool(ok)})
                if not ok:
                    results["success"] = False
                return ok
            except Exception as e:
                print(f"  ❌ 异常: {e}")
                results["steps"].append({"name": name, "ok": False, "error": str(e)})
                results["success"] = False
                return False

        # Step 1: 连接 + 解锁
        if not step("连接目标", self.ensure_ready):
            return results

        # Step 2: 五感审计
        step("五感审计", lambda: bool(self.agent.five_senses_audit()))

        # Step 3: 启动剪映
        step("启动剪映", self.launch_app, "jianying", 8)

        # Step 4: 最大化
        time.sleep(3)
        step("最大化剪映", self.maximize_app, "jianying")

        # Step 5: 截图
        step("截取编辑界面", self.jianying_screenshot_editing)

        # Step 6: 列出草稿
        drafts = self.jianying_list_drafts()
        step("列出草稿", lambda: bool(drafts))

        # Step 7: 打开第一个有内容的草稿
        if drafts:
            # 找最大的草稿(可能有最多内容)
            biggest = max(drafts, key=lambda d: d["size_mb"])
            if biggest["size_mb"] > 1:
                step(f"打开草稿: {biggest['name']}", self.jianying_open_draft, biggest["name"])
                time.sleep(3)
                step("编辑界面截图", self.jianying_screenshot_editing)

        # 汇总
        print("\n" + "=" * 60)
        ok_count = sum(1 for s in results["steps"] if s["ok"])
        total = len(results["steps"])
        print(f"🏁 演示完成: {ok_count}/{total} 步骤成功")
        print("=" * 60)

        return results

    def issues_report(self) -> str:
        """生成问题报告"""
        lines = [
            "# 远程视频剪辑Agent — 问题与解决方案报告",
            f"\n日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"目标: {self.target_name}",
            "\n## 已发现问题",
        ]
        for i, issue in enumerate(self._issues_found, 1):
            info = KNOWN_ISSUES.get(issue, {})
            lines.append(f"\n### P{i}: {issue}")
            if info:
                lines.append(f"- **症状**: {info.get('symptom', 'N/A')}")
                lines.append(f"- **根因**: {info.get('cause', 'N/A')}")
                lines.append(f"- **修复**: {info.get('fix', 'N/A')}")

        lines.append("\n## 已修复问题")
        for fix in self._issues_fixed:
            lines.append(f"- ✅ {fix}")

        return "\n".join(lines)


# ============================================================
# CLI
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="远程视频剪辑Agent")
    parser.add_argument("--target", "-t", default="laptop", help="目标 (laptop/desktop/cloud/IP)")
    parser.add_argument("--probe", action="store_true", help="探测所有目标")
    parser.add_argument("--unlock", action="store_true", help="解锁目标屏幕")
    parser.add_argument("--app", help="启动应用 (jianying/wps/edge)")
    parser.add_argument("--edit", help="打开剪映草稿项目名称")
    parser.add_argument("--drafts", action="store_true", help="列出剪映草稿")
    parser.add_argument("--diagnose", action="store_true", help="五感诊断")
    parser.add_argument("--demo", action="store_true", help="完整演示")
    parser.add_argument("--screenshot", "-s", action="store_true", help="截图")
    args = parser.parse_args()

    if args.probe:
        probe_all_targets()
        return

    va = VideoAgent(args.target)

    if args.diagnose:
        va.diagnose()
    elif args.demo:
        va.full_demo()
    elif args.unlock:
        va.connect()
        va.unlock_screen()
    elif args.app:
        va.ensure_ready()
        va.launch_app(args.app)
    elif args.edit:
        va.ensure_ready()
        va.launch_app("jianying")
        time.sleep(3)
        va.jianying_open_draft(args.edit)
    elif args.drafts:
        va.connect()
        drafts = va.jianying_list_drafts()
        for d in drafts:
            print(f"  {d['name']:20s} {d['size_mb']:>8.1f}MB  {d['path']}")
    elif args.screenshot:
        va.connect()
        va.agent.screenshot()
    else:
        # 默认: 诊断
        va.diagnose()


if __name__ == "__main__":
    main()
