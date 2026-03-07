#!/usr/bin/env python3
"""
统一远程操控中枢 — 整合所有Agent资源，以剪映为例实现远程视频剪辑
=================================================================
不依赖传统路径(rdp_agent.py/rdp_video_agent.py)，直接HTTP API操控。
带入用户五感：视(截图)·触(键鼠)·听(音量)·嗅(监控)·味(评估)。

架构:
  本脚本(台式机) → HTTP API → remote_agent.py(笔记本:9903) → 笔记本桌面
"""

import json, time, os, sys, io
from urllib.request import urlopen, Request
from urllib.error import URLError
from datetime import datetime
from typing import Optional, Dict, List, Tuple

# ============================================================
# 配置
# ============================================================
LAPTOP = {"ip": "192.168.31.179", "port": 9903, "name": "笔记本 zhoumac"}
SS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_screenshots")
os.makedirs(SS_DIR, exist_ok=True)

# DPI坐标系统 (2026-03-03破案):
# remote_agent进程可能DPI-unaware(1920x1200)或DPI-aware(2560x1600)
# 截图为screen_w/2 × screen_h/2 (50%缩放)
# 点击坐标 = 截图像素 × 2 (当remote_agent为DPI-unaware时)
# 需要运行时动态检测

class RemoteHub:
    """统一远程操控中枢"""
    
    def __init__(self, target=None):
        t = target or LAPTOP
        self.ip = t["ip"]
        self.port = t["port"]
        self.name = t.get("name", self.ip)
        self.base = f"http://{self.ip}:{self.port}"
        self.screen_w = 0
        self.screen_h = 0
        self.user = ""
        self.log = []
        self.issues = []
        self.fixes = []
    
    # ── HTTP 工具 ──
    
    def _get(self, path, timeout=8):
        try:
            r = urlopen(f"{self.base}{path}", timeout=timeout)
            return json.loads(r.read())
        except Exception as e:
            return {"error": str(e)}
    
    def _get_binary(self, path, timeout=15):
        try:
            return urlopen(f"{self.base}{path}", timeout=timeout).read()
        except:
            return None
    
    def _post(self, path, data=None, timeout=10):
        try:
            body = json.dumps(data or {}).encode()
            req = Request(f"{self.base}{path}", data=body,
                         headers={"Content-Type": "application/json"})
            return json.loads(urlopen(req, timeout=timeout).read())
        except Exception as e:
            return {"error": str(e)}
    
    def _log(self, action, detail, ok, ms=0):
        entry = {"time": datetime.now().strftime("%H:%M:%S"), "action": action,
                 "detail": str(detail)[:80], "ok": ok, "ms": ms}
        self.log.append(entry)
        icon = "✅" if ok else "❌"
        print(f"  {icon} [{action}] {str(detail)[:60]}")
    
    # ── 五感: 视 (Vision) ──
    
    def screenshot(self, label="", quality=75):
        t0 = time.perf_counter()
        data = self._get_binary(f"/screenshot?quality={quality}")
        ms = int((time.perf_counter() - t0) * 1000)
        if data:
            name = f"hub_{label or datetime.now().strftime('%H%M%S')}.jpg"
            path = os.path.join(SS_DIR, name)
            with open(path, "wb") as f:
                f.write(data)
            self._log("screenshot", f"{name} ({len(data)//1024}KB) {ms}ms", True, ms)
            return path
        self._log("screenshot", "FAILED", False, ms)
        return None
    
    def screen_info(self):
        r = self._get("/screen/info")
        if "error" not in r:
            self.screen_w = r.get("screen_w", 0)
            self.screen_h = r.get("screen_h", 0)
        return r
    
    def windows(self):
        r = self._get("/windows")
        return r if isinstance(r, list) else []
    
    # ── 五感: 触 (Input) ──
    
    def click(self, x, y, button="left", clicks=1):
        r = self._post("/click", {"x": x, "y": y, "button": button, "clicks": clicks})
        ok = "error" not in r
        self._log("click", f"({x},{y}) {button} x{clicks}", ok)
        return ok
    
    def double_click(self, x, y):
        return self.click(x, y, clicks=2)
    
    def right_click(self, x, y):
        return self.click(x, y, button="right")
    
    def key(self, k):
        r = self._post("/key", {"key": k})
        ok = "error" not in r
        self._log("key", k, ok)
        return ok
    
    def hotkey(self, *keys):
        r = self._post("/key", {"hotkey": list(keys)})
        ok = "error" not in r
        self._log("hotkey", "+".join(keys), ok)
        return ok
    
    def type_text(self, text):
        r = self._post("/type", {"text": text})
        ok = "error" not in r
        self._log("type", text[:30], ok)
        return ok
    
    def move(self, x, y):
        return self._post("/move", {"x": x, "y": y})
    
    def drag(self, x1, y1, x2, y2, duration=0.5):
        r = self._post("/drag", {"x1":x1,"y1":y1,"x2":x2,"y2":y2,"duration":duration})
        ok = "error" not in r
        self._log("drag", f"({x1},{y1})→({x2},{y2})", ok)
        return ok
    
    def scroll(self, x, y, clicks=3):
        r = self._post("/scroll", {"x": x, "y": y, "clicks": clicks})
        ok = "error" not in r
        self._log("scroll", f"({x},{y}) {clicks}", ok)
        return ok
    
    # ── 五感: 听 (Audio) ──
    
    def volume(self, level=None, mute=None):
        data = {}
        if level is not None: data["level"] = level
        if mute is not None: data["mute"] = mute
        return self._post("/volume", data)
    
    # ── 五感: 嗅 (Monitoring) ──
    
    def health(self):
        return self._get("/health")
    
    def sysinfo(self):
        return self._get("/sysinfo")
    
    def shell(self, cmd, timeout=15):
        return self._post("/shell", {"cmd": cmd, "timeout": timeout})
    
    # ── 五感: 味 (Quality) ──
    
    def clipboard_get(self):
        r = self._get("/clipboard")
        return r.get("text", "") if "error" not in r else ""
    
    def clipboard_set(self, text):
        r = self._post("/clipboard", {"text": text})
        return "error" not in r
    
    # ── 窗口管理 ──
    
    def focus(self, title=None, hwnd=None):
        data = {}
        if title: data["title"] = title
        if hwnd: data["hwnd"] = hwnd
        r = self._post("/focus", data)
        ok = "error" not in r
        self._log("focus", title or str(hwnd), ok)
        return ok
    
    def window_action(self, hwnd, action):
        return self._post("/window", {"hwnd": hwnd, "action": action})
    
    def find_window(self, keyword):
        kw = keyword.lower()
        for w in self.windows():
            if kw in w.get("title", "").lower():
                return w
        return None
    
    def wait_window(self, keyword, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            w = self.find_window(keyword)
            if w:
                return w
            time.sleep(1)
        return None
    
    def active_window(self):
        si = self.screen_info()
        return si.get("active_window", "") if "error" not in si else ""
    
    # ── Guard 管理 ──
    
    def guard_pause(self):
        return self._post("/guard/pause")
    
    def guard_resume(self):
        return self._post("/guard/resume")
    
    # ── 坐标系统 ──
    
    def calibrate(self):
        """校准坐标系统 — 检测DPI模式"""
        si = self.screen_info()
        if "error" in si:
            return False
        
        # 获取截图实际尺寸
        data = self._get_binary("/screenshot?quality=30")
        if not data:
            return False
        
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(data))
            ss_w, ss_h = img.size
        except ImportError:
            # 没有PIL，从JPEG header提取尺寸
            ss_w, ss_h = self._jpeg_size(data)
        
        self.screen_w = si.get("screen_w", 0)
        self.screen_h = si.get("screen_h", 0)
        
        if ss_w > 0:
            self._scale_x = self.screen_w / ss_w
            self._scale_y = self.screen_h / ss_h
        else:
            self._scale_x = 2
            self._scale_y = 2
        
        print(f"  📐 校准: 屏幕={self.screen_w}x{self.screen_h} 截图={ss_w}x{ss_h} 缩放={self._scale_x:.1f}x")
        return True
    
    def _jpeg_size(self, data):
        """从JPEG二进制数据中提取图像尺寸"""
        i = 0
        while i < len(data) - 8:
            if data[i] == 0xFF:
                marker = data[i+1]
                if marker in (0xC0, 0xC1, 0xC2):
                    h = (data[i+5] << 8) | data[i+6]
                    w = (data[i+7] << 8) | data[i+8]
                    return w, h
                elif marker == 0xD8 or marker == 0xD9:
                    i += 2
                else:
                    seg_len = (data[i+2] << 8) | data[i+3]
                    i += 2 + seg_len
            else:
                i += 1
        return 0, 0
    
    def pct(self, px, py):
        """百分比坐标→屏幕像素 (分辨率无关)"""
        if not self.screen_w:
            self.screen_info()
        return int(self.screen_w * px), int(self.screen_h * py)
    
    # ═══════════════════════════════════════════════
    # 剪映专用操作
    # ═══════════════════════════════════════════════
    
    def jy_find_exe(self):
        """寻找剪映可执行文件路径"""
        paths = [
            f"C:\\Users\\{self.user}\\AppData\\Local\\JianyingPro\\Apps\\JianyingPro.exe",
            "C:\\Users\\zhouyoukang\\AppData\\Local\\JianyingPro\\Apps\\JianyingPro.exe",
        ]
        for p in paths:
            r = self.shell(f'if exist "{p}" echo FOUND', timeout=5)
            if r and "FOUND" in (r.get("stdout") or ""):
                return p
        
        # 搜索
        r = self.shell('where /r "C:\\Users\\zhouyoukang\\AppData\\Local" JianyingPro.exe 2>nul', timeout=10)
        if r and r.get("stdout", "").strip():
            return r["stdout"].strip().split("\n")[0].strip()
        return None
    
    def jy_launch(self, wait=10):
        """启动剪映"""
        # 检查是否已运行
        w = self.find_window("剪映")
        if w:
            print(f"  ℹ️ 剪映已运行 hwnd={w['hwnd']}")
            self.focus(hwnd=w["hwnd"])
            return True
        
        exe = self.jy_find_exe()
        if not exe:
            self._log("jy_launch", "❌ 找不到JianyingPro.exe", False)
            self.issues.append("剪映可执行文件未找到")
            return False
        
        print(f"  🚀 启动剪映: {exe}")
        self.shell(f'start "" "{exe}"', timeout=5)
        
        # 等待窗口出现
        w = self.wait_window("剪映", timeout=wait)
        if w:
            self._log("jy_launch", f"✅ 剪映已启动 hwnd={w['hwnd']}", True)
            time.sleep(2)  # 等待UI完全加载
            
            # 处理可能的弹窗
            self._jy_handle_popups()
            return True
        
        self._log("jy_launch", "超时，剪映可能仍在加载", False)
        self.issues.append("剪映启动超时")
        return False
    
    def _jy_handle_popups(self):
        """处理剪映启动时的弹窗"""
        time.sleep(2)
        active = self.active_window()
        
        # 版本更新弹窗
        if "版本更新" in active or "更新" in active:
            print("  🔄 关闭版本更新弹窗...")
            self.key("escape")
            time.sleep(1)
            self.fixes.append("关闭版本更新弹窗")
        
        # 登录弹窗
        if "登录" in active or "login" in active.lower():
            print("  🔐 关闭登录弹窗...")
            self.key("escape")
            time.sleep(1)
            self.fixes.append("关闭登录弹窗")
        
        # 广告/推广
        for _ in range(3):
            active = self.active_window()
            if "剪映" not in active:
                self.key("escape")
                time.sleep(0.5)
    
    def jy_maximize(self):
        """最大化剪映窗口"""
        w = self.find_window("剪映")
        if w:
            self.window_action(w["hwnd"], "maximize")
            self.focus(hwnd=w["hwnd"])
            time.sleep(0.5)
            return True
        return False
    
    def jy_drafts(self):
        """列出剪映草稿"""
        r = self.shell('dir /b "E:\\JianyingPro Drafts" 2>nul', timeout=5)
        if r and r.get("stdout"):
            return [d.strip() for d in r["stdout"].split("\n") if d.strip()]
        return []
    
    def jy_new_project(self):
        """新建剪映项目 Ctrl+N"""
        self.focus("剪映")
        time.sleep(0.3)
        self.hotkey("ctrl", "n")
        time.sleep(3)
        self.screenshot("jy_new_project")
        active = self.active_window()
        self._log("jy_new", f"新建项目后: {active[:50]}", "剪映" in active)
        return "剪映" in active
    
    def jy_import_media(self, file_path=None):
        """导入媒体素材 Ctrl+I"""
        self.focus("剪映")
        time.sleep(0.3)
        self.hotkey("ctrl", "i")
        time.sleep(2)
        
        active = self.active_window()
        if "打开" in active or "Open" in active or "选择" in active:
            if file_path:
                # 导航到文件
                self.hotkey("ctrl", "l")  # 聚焦地址栏
                time.sleep(0.5)
                self.clipboard_set(os.path.dirname(file_path))
                self.hotkey("ctrl", "v")
                time.sleep(0.5)
                self.key("enter")
                time.sleep(2)
                
                # 输入文件名
                fname = os.path.basename(file_path)
                self.clipboard_set(fname)
                # 点击文件名输入框
                self.hotkey("alt", "n")
                time.sleep(0.3)
                self.hotkey("ctrl", "v")
                time.sleep(0.3)
                self.key("enter")
                time.sleep(3)
                self._log("jy_import", f"导入: {file_path}", True)
            else:
                self.key("escape")
                self._log("jy_import", "打开了文件对话框但无文件路径", True)
        else:
            self._log("jy_import", f"未检测到文件对话框: {active[:40]}", False)
        
        self.screenshot("jy_import")
    
    def jy_add_text(self, text):
        """在剪映中添加文字"""
        self.focus("剪映")
        time.sleep(0.3)
        # 使用快捷键或点击文本按钮
        self.hotkey("ctrl", "t")  # 可能是添加文字的快捷键
        time.sleep(1)
        self.clipboard_set(text)
        self.hotkey("ctrl", "v")
        time.sleep(0.5)
        self.key("enter")
        self._log("jy_text", f"添加文字: {text[:20]}", True)
    
    def jy_export(self, name=None):
        """导出视频"""
        self.focus("剪映")
        time.sleep(0.3)
        self.hotkey("ctrl", "e")  # 导出快捷键
        time.sleep(2)
        
        if name:
            self.clipboard_set(name)
            self.hotkey("ctrl", "a")
            time.sleep(0.2)
            self.hotkey("ctrl", "v")
            time.sleep(0.3)
        
        self.screenshot("jy_export")
        self._log("jy_export", f"导出: {name or '默认'}", True)
    
    def jy_timeline_ops(self):
        """时间线基础操作"""
        self.focus("剪映")
        time.sleep(0.3)
        
        # 播放/暂停
        self.key("space")
        time.sleep(2)
        self.key("space")  # 暂停
        self._log("jy_play", "播放/暂停", True)
        
        # 时间线缩放
        self.hotkey("ctrl", "=")  # 放大
        time.sleep(0.5)
        self.hotkey("ctrl", "-")  # 缩小
        time.sleep(0.5)
        self._log("jy_zoom", "时间线缩放", True)
    
    # ═══════════════════════════════════════════════
    # 完整工作流
    # ═══════════════════════════════════════════════
    
    def connect(self):
        """连接并初始化"""
        print(f"\n{'='*60}")
        print(f"🔗 连接: {self.name} ({self.ip}:{self.port})")
        print(f"{'='*60}")
        
        h = self.health()
        if "error" in h or h.get("status") != "ok":
            print(f"❌ 连接失败: {h}")
            return False
        
        self.user = h.get("user", "")
        guard = h.get("guard", {})
        print(f"  ✅ 在线 | host={h.get('hostname')} user={self.user}")
        print(f"  🛡️ Guard: can_auto={guard.get('can_automate')} idle={guard.get('user_idle_seconds',0):.0f}s")
        
        si = self.screen_info()
        if "error" not in si:
            print(f"  📺 {self.screen_w}x{self.screen_h} | locked={si.get('is_locked')}")
            print(f"  🪟 活跃: {si.get('active_window','?')[:50]}")
            
            if si.get("is_locked"):
                self.issues.append("屏幕锁定")
                print("  ⚠️ 屏幕锁定 → 尝试解锁...")
                self.shell(f"tscon {si.get('session_id',2)} /dest:console", timeout=10)
                time.sleep(3)
                si2 = self.screen_info()
                if si2 and not si2.get("is_locked"):
                    self.fixes.append("tscon解锁成功")
                    print("  ✅ 解锁成功!")
        
        # 校准坐标
        self.calibrate()
        
        # 暂停Guard让我们自由操作
        if guard.get("enabled") and not guard.get("paused"):
            self.guard_pause()
            print("  🛡️ Guard已暂停")
        
        return True
    
    def full_jianying_workflow(self):
        """完整剪映远程视频剪辑工作流"""
        print(f"\n{'='*60}")
        print("🎬 远程视频剪辑工作流 — 剪映专业版")
        print(f"{'='*60}")
        
        results = {"steps": [], "success": True}
        
        def step(name, func, *a, **kw):
            print(f"\n📌 {name}")
            try:
                ok = func(*a, **kw)
                results["steps"].append({"name": name, "ok": bool(ok)})
                if not ok:
                    results["success"] = False
                return ok
            except Exception as e:
                print(f"  ❌ 异常: {e}")
                results["steps"].append({"name": name, "ok": False, "error": str(e)})
                results["success"] = False
                return False
        
        # Phase 1: 连接
        if not step("1. 连接笔记本", self.connect):
            return results
        
        # Phase 2: 系统状态截图
        step("2. 截取当前桌面", lambda: bool(self.screenshot("01_desktop")))
        
        # Phase 3: 启动剪映
        step("3. 启动剪映", self.jy_launch, 15)
        time.sleep(2)
        
        # Phase 4: 最大化
        step("4. 最大化剪映", self.jy_maximize)
        time.sleep(1)
        step("4b. 截取剪映首页", lambda: bool(self.screenshot("02_jy_home")))
        
        # Phase 5: 查看草稿
        drafts = self.jy_drafts()
        step("5. 获取草稿列表", lambda: bool(drafts))
        if drafts:
            print(f"  📁 {len(drafts)} 个草稿:")
            for d in drafts[:10]:
                print(f"    · {d}")
        
        # Phase 6: 新建项目
        step("6. 新建项目 (Ctrl+N)", self.jy_new_project)
        time.sleep(2)
        
        # Phase 7: 截图确认编辑界面
        step("7. 截取编辑界面", lambda: bool(self.screenshot("03_jy_editor")))
        
        # Phase 8: 搜索视频素材
        print("\n📌 8. 搜索视频素材")
        videos_r = self.shell(
            'powershell -c "Get-ChildItem C:\\Users\\zhouyoukang\\Videos,'
            'C:\\Users\\zhouyoukang\\Desktop,D:\\ -Include *.mp4,*.mov -Recurse '
            '-Depth 2 -EA SilentlyContinue | Select-Object -First 10 FullName | '
            'ForEach-Object { $_.FullName }"',
            timeout=15
        )
        videos = []
        if videos_r and videos_r.get("stdout"):
            videos = [v.strip() for v in videos_r["stdout"].split("\n") if v.strip() and v.strip().endswith(('.mp4','.mov','.avi'))]
            print(f"  🎥 找到 {len(videos)} 个视频:")
            for v in videos[:5]:
                print(f"    · {v}")
        
        if not videos:
            # 创建测试视频
            print("  ⚠️ 无视频素材 → 创建测试视频...")
            test_vid = f"C:\\Users\\{self.user}\\Videos\\agent_test.mp4"
            ffmpeg_r = self.shell(
                f'ffmpeg -y -f lavfi -i "color=c=blue:size=1920x1080:d=5" '
                f'-f lavfi -i "sine=frequency=440:duration=5" '
                f'-c:v libx264 -preset ultrafast -pix_fmt yuv420p -c:a aac '
                f'-shortest "{test_vid}" 2>&1',
                timeout=30
            )
            if ffmpeg_r and "error" not in ffmpeg_r:
                videos = [test_vid]
                self._log("create_test_video", test_vid, True)
        
        # Phase 9: 导入素材 (如果有视频)
        if videos:
            step("9. 导入视频素材", self.jy_import_media, videos[0])
            time.sleep(2)
        
        # Phase 10: 基础编辑操作
        step("10. 时间线操作(播放/缩放)", self.jy_timeline_ops)
        
        # Phase 11: 最终截图
        step("11. 最终状态截图", lambda: bool(self.screenshot("04_jy_final")))
        
        # 汇总
        print(f"\n{'='*60}")
        ok_count = sum(1 for s in results["steps"] if s["ok"])
        total = len(results["steps"])
        print(f"🏁 工作流完成: {ok_count}/{total} 步骤成功")
        
        if self.issues:
            print(f"\n⚠️ 发现问题 ({len(self.issues)}):")
            for i in self.issues:
                print(f"  · {i}")
        
        if self.fixes:
            print(f"\n✅ 已修复 ({len(self.fixes)}):")
            for f in self.fixes:
                print(f"  · {f}")
        
        print(f"\n📊 操作日志 ({len(self.log)} 条):")
        for entry in self.log:
            icon = "✅" if entry["ok"] else "❌"
            print(f"  {entry['time']} {icon} [{entry['action']}] {entry['detail']}")
        
        print(f"{'='*60}")
        return results
    
    def five_senses_audit(self):
        """完整五感审计"""
        print(f"\n{'='*60}")
        print("🔍 五感审计")
        print(f"{'='*60}")
        
        results = {}
        
        # 👁 视
        print("\n👁 视 (Vision)...")
        t0 = time.perf_counter()
        path = self.screenshot("audit_vision", 60)
        vis_ms = int((time.perf_counter() - t0) * 1000)
        results["vision"] = {"ok": bool(path), "latency_ms": vis_ms}
        
        si = self.screen_info()
        results["screen"] = f"{self.screen_w}x{self.screen_h}"
        results["active_window"] = si.get("active_window", "?") if "error" not in si else "?"
        
        # ✋ 触
        print("\n✋ 触 (Input)...")
        t0 = time.perf_counter()
        move_r = self._post("/move", {"x": 1, "y": 1})
        touch_ms = int((time.perf_counter() - t0) * 1000)
        results["touch"] = {"ok": "error" not in move_r, "latency_ms": touch_ms}
        
        # 👂 听
        print("\n👂 听 (Audio)...")
        vol_r = self.volume()
        results["audio"] = {"ok": "error" not in vol_r, "level": vol_r.get("level", -1) if isinstance(vol_r, dict) else -1}
        
        # 👃 嗅
        print("\n👃 嗅 (Monitor)...")
        sys_r = self.sysinfo()
        if "error" not in sys_r:
            results["monitor"] = {
                "ok": True,
                "ram_pct": sys_r.get("ram_percent", 0),
                "disk_gb": sys_r.get("disk_free_gb", 0),
            }
        
        # 👅 味
        print("\n👅 味 (Quality)...")
        latencies = [vis_ms, touch_ms]
        avg_ms = sum(latencies) // len(latencies) if latencies else 999
        grade = "A" if avg_ms < 200 else "B" if avg_ms < 500 else "C" if avg_ms < 1000 else "D"
        results["quality"] = {"avg_latency_ms": avg_ms, "grade": grade}
        
        # 打印汇总
        for sense, data in results.items():
            if isinstance(data, dict) and "ok" in data:
                icon = "✅" if data["ok"] else "❌"
                print(f"  {icon} {sense}: {data}")
            else:
                print(f"  📊 {sense}: {data}")
        
        print(f"\n🏆 评级: {grade} (平均延迟 {avg_ms}ms)")
        return results


# ============================================================
# CLI
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="统一远程操控中枢")
    parser.add_argument("--workflow", "-w", action="store_true", help="完整剪映工作流")
    parser.add_argument("--audit", "-a", action="store_true", help="五感审计")
    parser.add_argument("--screenshot", "-s", action="store_true", help="截图")
    parser.add_argument("--launch-jy", action="store_true", help="启动剪映")
    parser.add_argument("--drafts", action="store_true", help="列出草稿")
    parser.add_argument("--shell", help="远程执行命令")
    args = parser.parse_args()
    
    hub = RemoteHub()
    
    if args.workflow:
        hub.full_jianying_workflow()
    elif args.audit:
        hub.connect()
        hub.five_senses_audit()
    elif args.screenshot:
        hub.screenshot("manual")
    elif args.launch_jy:
        hub.connect()
        hub.jy_launch()
    elif args.drafts:
        hub.connect()
        for d in hub.jy_drafts():
            print(f"  · {d}")
    elif args.shell:
        r = hub.shell(args.shell)
        print(r.get("stdout", "") if r else "ERROR")
    else:
        hub.full_jianying_workflow()


if __name__ == "__main__":
    main()
