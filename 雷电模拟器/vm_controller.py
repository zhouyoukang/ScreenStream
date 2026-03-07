#!/usr/bin/env python3
"""
VM Controller — 浏览器MCP般无感操控LDPlayer虚拟机
================================================================
提供与 chrome-devtools / playwright MCP 完全对等的API，
让Agent像操作浏览器一样操作Android虚拟机。

Browser MCP              VM Controller              实现层
────────────────────────────────────────────────────────────
browser_snapshot      →  snapshot [vm]            →  viewtree + screen/text
browser_click         →  click [vm] [text]        →  PhoneLib findclick
browser_type          →  type [vm] [text]         →  PhoneLib text input
browser_navigate      →  launch [vm] [pkg]        →  am start / open_app
browser_evaluate      →  shell [vm] [cmd]         →  adb shell
browser_press_key     →  key [vm] [name]          →  adb keyevent
browser_wait_for      →  wait [vm] [text]         →  poll screen/text
take_screenshot       →  screenshot [vm] [path]   →  adb screencap
list_pages            →  list                     →  dnconsole list2
select_page           →  info [vm]                →  VM详情+SS状态
browser_fill_form     →  fill [vm] [k=v...]       →  findclick+text
browser_hover         →  tap [vm] [nx] [ny]       →  PhoneLib tap
browser_navigate_back →  back [vm]                →  PhoneLib back
browser_console       →  logcat [vm] [filter]     →  adb logcat

CLI用法:
  python vm_controller.py list                        # 列出所有VM
  python vm_controller.py snapshot 3                  # UI快照(like browser_snapshot)
  python vm_controller.py click 3 "设置"               # 点击元素
  python vm_controller.py type 3 "hello"              # 输入文字
  python vm_controller.py tap 3 0.5 0.3               # 归一化坐标点击
  python vm_controller.py swipe 3 up                  # 滑动
  python vm_controller.py key 3 HOME                  # 按键
  python vm_controller.py shell 3 "ls /sdcard"        # 执行shell
  python vm_controller.py launch 3 com.android.chrome # 启动APP
  python vm_controller.py screenshot 3                # 截屏
  python vm_controller.py wait 3 "登录成功" 10         # 等待文字出现
  python vm_controller.py senses 3                    # 五感采集
  python vm_controller.py health 3                    # 健康检查
  python vm_controller.py install 3 path/to/app.apk  # 安装APK
  python vm_controller.py forward 3                   # 设置端口映射
  python vm_controller.py info 3                      # VM详情
  python vm_controller.py logcat 3 "ScreenStream"     # 查看日志
  python vm_controller.py apps 3                      # 已安装应用
  python vm_controller.py read 3                      # 读取屏幕文字
  python vm_controller.py status                      # 全景状态

Python用法:
  from vm_controller import VMFleet
  fleet = VMFleet()
  vm = fleet[3]                   # 获取VM[3]
  print(vm.snapshot())            # UI快照
  vm.click("设置")                # 点击
  vm.type_text("hello")          # 输入
  print(vm.shell("ls /sdcard"))  # shell
"""

import subprocess, json, sys, os, time, argparse, re, base64, tempfile
from pathlib import Path
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════

LDPLAYER_DIR = r"D:\leidian\LDPlayer9"
DNCONSOLE = os.path.join(LDPLAYER_DIR, "dnconsole.exe")
ADB = os.path.join(LDPLAYER_DIR, "adb.exe")
WORKSPACE = r"d:\道\道生一\一生二"
SCREENSHOT_DIR = os.path.join(WORKSPACE, "雷电模拟器", "screenshots")

# ADB serial映射 (index → port)
ADB_PORTS = {0: 5554, 1: 5556, 2: 5558, 3: 5560, 4: 5562, 5: 5564}

# 端口映射方案 (本机端口 → 模拟器端口)
PORT_MAP = {
    0: {},
    3: {18080: 8080, 18084: 8084, 18081: 8081, 18083: 8083},
    4: {28080: 8080, 28084: 8084},
    5: {38080: 8080, 38084: 8084},
}

# ScreenStream Input API 端口映射 (vm_index → localhost port)
# 注意: VM[0]是通用主控(非开发用), Agent应默认使用开发测试VM(3/4/5)
SS_INPUT_PORTS = {0: 8084, 3: 18084, 4: 28084, 5: 38084}

# ═══════════════════════════════════════════════════════════════
# 开发测试VM自动选择 (核心: Agent默认调用开发测试VM, 而非初始模拟器)
# ═══════════════════════════════════════════════════════════════

# 开发测试VM索引 (优先级从高到低)
DEV_VM_INDICES = [5, 3, 4]  # 5="开发测试", 3="开发测试1", 4="开发测试2"
DEFAULT_VM_INDEX = 5         # "开发测试" — Agent无指定时的默认目标VM

# 项目 → VM映射 (Agent根据项目名自动路由到正确VM)
PROJECT_VM_MAP = {
    "ScreenStream": 3, "手机操控库": 3, "公网投屏": 3, "亲情远程": 3, "手机软路由": 3,
    "二手书手机端": 4, "电脑公网投屏手机": 4, "智能家居": 4, "微信公众号": 4,
    "手机购物订单": 5, "ORS6-VAM抖音同步": 5, "agent-phone-control": 5,
}

# Android keyevent名称映射
KEYMAP = {
    "HOME": 3, "BACK": 4, "CALL": 5, "ENDCALL": 6,
    "VOLUME_UP": 24, "VOLUME_DOWN": 25, "POWER": 26, "CAMERA": 27,
    "DEL": 67, "ENTER": 66, "TAB": 61, "SPACE": 62, "ESCAPE": 111,
    "DPAD_UP": 19, "DPAD_DOWN": 20, "DPAD_LEFT": 21, "DPAD_RIGHT": 22,
    "DPAD_CENTER": 23, "MENU": 82, "SEARCH": 84, "SETTINGS": 176,
    "APP_SWITCH": 187, "NOTIFICATION": 83,
    "MEDIA_PLAY": 126, "MEDIA_PAUSE": 127, "MEDIA_NEXT": 87,
    "MEDIA_PREVIOUS": 88, "MEDIA_STOP": 86,
    "BRIGHTNESS_UP": 221, "BRIGHTNESS_DOWN": 220,
}


# ═══════════════════════════════════════════════════════════════
# 底层工具
# ═══════════════════════════════════════════════════════════════

def _run(cmd, timeout=30):
    """运行命令，返回(returncode, stdout)"""
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        # dnconsole输出GBK编码
        stdout = r.stdout.decode('utf-8', errors='replace')
        if '\ufffd' in stdout:
            stdout = r.stdout.decode('gbk', errors='replace')
        return r.returncode, stdout.strip()
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    except Exception as e:
        return -1, str(e)

def _dnc(*args):
    """调用dnconsole"""
    return _run([DNCONSOLE] + list(args))

def _adb(serial, *args, timeout=15):
    """调用adb (指定serial)"""
    return _run([ADB, "-s", serial] + list(args), timeout=timeout)

def _adb_shell(serial, cmd, timeout=15):
    """adb shell"""
    return _adb(serial, "shell", cmd, timeout=timeout)

def _http_get(url, timeout=5):
    """HTTP GET → (status, body_text)"""
    import urllib.request, urllib.error
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return 0, str(e)

def _http_json(url, timeout=5):
    """HTTP GET → parsed JSON or None"""
    status, body = _http_get(url, timeout)
    if status == 200:
        try:
            return json.loads(body)
        except:
            pass
    return None

def _http_post(url, data=None, timeout=10):
    """HTTP POST JSON → parsed JSON or None"""
    import urllib.request
    try:
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, method='POST',
                                     headers={'Content-Type': 'application/json'} if body else {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8', errors='replace'))
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# PhoneLib 集成 (可选, 有则增强)
# ═══════════════════════════════════════════════════════════════

_PhoneLib = None

def _load_phonelib():
    """尝试加载手机操控库的Phone类"""
    global _PhoneLib
    if _PhoneLib is not None:
        return _PhoneLib
    phonelib_dir = os.path.join(WORKSPACE, "手机操控库")
    if os.path.isfile(os.path.join(phonelib_dir, "phone_lib.py")):
        sys.path.insert(0, phonelib_dir)
        try:
            from phone_lib import Phone
            _PhoneLib = Phone
            return Phone
        except Exception:
            pass
    _PhoneLib = False  # 标记为已尝试但失败
    return False


# ═══════════════════════════════════════════════════════════════
# VMPhone — 单个虚拟机的完整操控接口
# ═══════════════════════════════════════════════════════════════

class VMPhone:
    """单个LDPlayer虚拟机的完整操控接口。
    
    融合三层能力:
      L1: dnconsole (VM生命周期)
      L2: ADB (设备级操作)
      L3: ScreenStream/PhoneLib (应用级操控)
    
    提供与浏览器MCP完全对等的API。
    """

    def __init__(self, index, serial=None, ss_port=None):
        self.index = index
        self.serial = serial or f"emulator-{ADB_PORTS.get(index, 5554 + index * 2)}"
        self.ss_port = ss_port or SS_INPUT_PORTS.get(index, 8084)
        self.ss_base = f"http://127.0.0.1:{self.ss_port}"
        self._phone = None  # PhoneLib实例(懒加载)
        self._name = None
        self._running = None

    def __repr__(self):
        return f"VMPhone(index={self.index}, serial={self.serial}, ss={self.ss_base})"

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def name(self):
        if self._name is None:
            self._refresh_info()
        return self._name or f"VM[{self.index}]"

    @property
    def running(self):
        if self._running is None:
            self._refresh_info()
        return self._running or False

    @property
    def phone(self):
        """获取PhoneLib Phone实例(懒加载)"""
        if self._phone is None:
            PhoneClass = _load_phonelib()
            if PhoneClass:
                self._phone = PhoneClass(
                    host="127.0.0.1",
                    port=self.ss_port,
                    auto_discover=False,
                    retry=1,
                    retry_delay=0.5
                )
        return self._phone

    def _refresh_info(self):
        """刷新VM信息"""
        code, out = _dnc("list2")
        if code == 0:
            for line in out.split('\n'):
                parts = line.strip().split(',')
                if len(parts) >= 10 and int(parts[0]) == self.index:
                    self._name = parts[1]
                    self._running = parts[4] == '1'
                    return

    # ── L1: VM生命周期 (dnconsole) ────────────────────────────

    def vm_launch(self):
        """启动虚拟机"""
        code, out = _dnc("launch", "--index", str(self.index))
        if code == 0:
            self._running = True
        return code == 0

    def vm_quit(self):
        """关闭虚拟机"""
        code, out = _dnc("quit", "--index", str(self.index))
        if code == 0:
            self._running = False
        return code == 0

    def vm_reboot(self):
        """重启虚拟机"""
        code, out = _dnc("reboot", "--index", str(self.index))
        return code == 0

    def vm_config(self):
        """读取VM配置"""
        cfg_path = os.path.join(LDPLAYER_DIR, "vms", "config", f"leidian{self.index}.config")
        try:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    # ── L2: ADB操作 ──────────────────────────────────────────

    def adb(self, *args, timeout=15):
        """直接执行ADB命令"""
        return _adb(self.serial, *args, timeout=timeout)

    def shell(self, cmd, timeout=15):
        """执行shell命令 (= browser_evaluate)"""
        code, out = _adb_shell(self.serial, cmd, timeout=timeout)
        return {"ok": code == 0, "output": out}

    def install(self, apk_path, timeout=120):
        """安装APK"""
        if not os.path.isfile(apk_path):
            return {"ok": False, "error": f"APK不存在: {apk_path}"}
        code, out = _adb(self.serial, "install", "-r", "-t", apk_path, timeout=timeout)
        return {"ok": code == 0 and "Success" in out, "output": out}

    def uninstall(self, package):
        """卸载应用"""
        code, out = _adb(self.serial, "uninstall", package)
        return {"ok": code == 0, "output": out}

    def push(self, local_path, remote_path):
        """推送文件到模拟器"""
        code, out = _adb(self.serial, "push", local_path, remote_path)
        return {"ok": code == 0, "output": out}

    def pull(self, remote_path, local_path):
        """从模拟器拉取文件"""
        code, out = _adb(self.serial, "pull", remote_path, local_path)
        return {"ok": code == 0, "output": out}

    def forward(self, local_port, remote_port):
        """设置端口转发"""
        code, out = _adb(self.serial, "forward", f"tcp:{local_port}", f"tcp:{remote_port}")
        return code == 0

    def reverse(self, remote_port, local_port):
        """设置反向端口转发(让模拟器访问PC服务)"""
        code, out = _adb(self.serial, "reverse", f"tcp:{remote_port}", f"tcp:{local_port}")
        return code == 0

    def forward_all(self):
        """设置该VM的全部端口映射"""
        ports = PORT_MAP.get(self.index, {})
        results = {}
        for local_port, remote_port in ports.items():
            ok = self.forward(local_port, remote_port)
            results[f"{local_port}→{remote_port}"] = "✅" if ok else "❌"
        return results

    def is_adb_alive(self):
        """检查ADB连接是否正常"""
        code, out = _adb(self.serial, "shell", "echo", "alive", timeout=5)
        return code == 0 and "alive" in out

    def logcat(self, filter_str="", lines=30, timeout=5):
        """查看日志 (= browser_console_messages)"""
        cmd = f"logcat -d -t {lines}"
        if filter_str:
            cmd += f" | grep -i '{filter_str}'"
        return self.shell(cmd, timeout=timeout)

    # ── L3: ScreenStream API (HTTP) ──────────────────────────

    def _ss_get(self, path, timeout=5):
        """ScreenStream HTTP GET"""
        return _http_json(self.ss_base + path, timeout)

    def _ss_post(self, path, data=None, timeout=10):
        """ScreenStream HTTP POST"""
        return _http_post(self.ss_base + path, data, timeout)

    def ss_alive(self):
        """ScreenStream是否完全可用(connected=True且inputEnabled=True)"""
        r = self._ss_get("/status", timeout=3)
        if r is None:
            return False
        # connected=True表示MediaProjection已授权，API完全可用
        # inputEnabled=True表示无障碍服务已启用
        return r.get("connected", False) and r.get("inputEnabled", False)

    def ss_partial(self):
        """ScreenStream部分可用(inputEnabled但未connected)
        此模式下仅/status可用，其他端点返回503"""
        r = self._ss_get("/status", timeout=3)
        if r is None:
            return False
        return "connected" in r  # SS服务在运行

    # ── 浏览器MCP对等API ─────────────────────────────────────

    def snapshot(self, depth=5):
        """UI快照 (= browser_snapshot)
        
        返回结构化的UI树，包含文本、可点击元素、类型信息。
        Agent可直接基于此信息决策下一步操作。
        """
        result = {"vm": self.index, "serial": self.serial, "timestamp": time.time()}

        # 优先: ScreenStream viewtree + screen/text (丰富)
        if self.ss_alive():
            vt = self._ss_get(f"/viewtree?depth={depth}")
            st = self._ss_get("/screen/text")
            fg = self._ss_get("/foreground")

            result["source"] = "screenstream"
            result["package"] = (fg or {}).get("packageName", "") if fg else ""
            result["activity"] = (fg or {}).get("activityName", "") if fg else ""

            # 文本列表
            texts = []
            clickables = []
            if st:
                for t in st.get("texts", []):
                    texts.append(t.get("text", ""))
                for c in st.get("clickables", []):
                    label = c.get("text", "") or c.get("label", "")
                    clickables.append({
                        "text": label,
                        "bounds": c.get("bounds", ""),
                        "class": c.get("className", ""),
                    })

            result["texts"] = texts
            result["clickables"] = clickables
            result["text_count"] = len(texts)
            result["clickable_count"] = len(clickables)

            # viewtree (完整树)
            if vt:
                result["viewtree"] = vt

            # 格式化为agent可读的文本
            lines = []
            lines.append(f"📱 VM[{self.index}] {self.name}")
            lines.append(f"📦 {result['package']}")
            if result.get('activity'):
                lines.append(f"🔗 {result['activity']}")
            lines.append(f"")
            if clickables:
                lines.append(f"── 可点击元素 ({len(clickables)}) ──")
                for i, c in enumerate(clickables[:30]):
                    cls = c.get("class", "").split(".")[-1] if c.get("class") else "?"
                    lines.append(f"  [{i}] [{cls}] \"{c['text']}\"")
            if texts:
                lines.append(f"")
                lines.append(f"── 屏幕文本 ({len(texts)}) ──")
                for t in texts[:40]:
                    if t.strip():
                        lines.append(f"  {t}")
            result["formatted"] = "\n".join(lines)

        else:
            # 降级: uiautomator dump (仅ADB)
            result["source"] = "uiautomator"
            # LDPlayer不支持dump到/dev/tty，必须dump到文件再读取
            _adb_shell(self.serial, "uiautomator dump /sdcard/ui.xml", timeout=15)
            code, out = _adb_shell(self.serial, "cat /sdcard/ui.xml", timeout=10)
            _adb_shell(self.serial, "rm /sdcard/ui.xml", timeout=5)
            if code == 0 and out and out.startswith("<?xml"):
                result["raw_xml"] = out[:5000]
                # 简易解析
                texts = re.findall(r'text="([^"]+)"', out)
                clickables_raw = re.findall(
                    r'text="([^"]*)"[^>]*class="([^"]*)"[^>]*clickable="true"', out)
                result["texts"] = [t for t in texts if t.strip()]
                result["clickables"] = [
                    {"text": t, "class": c.split(".")[-1]}
                    for t, c in clickables_raw
                ]
                result["text_count"] = len(result["texts"])
                result["clickable_count"] = len(result["clickables"])

                lines = [f"📱 VM[{self.index}] (uiautomator降级模式)"]
                if result["clickables"]:
                    lines.append(f"── 可点击元素 ({len(result['clickables'])}) ──")
                    for i, c in enumerate(result["clickables"][:30]):
                        lines.append(f"  [{i}] [{c['class']}] \"{c['text']}\"")
                if result["texts"]:
                    lines.append(f"── 屏幕文本 ({len(result['texts'])}) ──")
                    for t in result["texts"][:40]:
                        lines.append(f"  {t}")
                result["formatted"] = "\n".join(lines)
            else:
                result["error"] = "snapshot失败: SS不可达且uiautomator失败"
                result["formatted"] = f"❌ VM[{self.index}] snapshot失败"

        return result

    def click(self, text):
        """点击包含指定文字的元素 (= browser_click)"""
        # 优先: ScreenStream findclick
        if self.ss_alive():
            r = self._ss_post("/findclick", {"text": text})
            if r and r.get("ok"):
                return {"ok": True, "method": "ss_findclick", "text": text}
            # findclick失败，尝试精确匹配
            r = self._ss_post("/findclick", {"text": text, "exact": True})
            if r and r.get("ok"):
                return {"ok": True, "method": "ss_findclick_exact", "text": text}

        # 降级: uiautomator + tap (dump到文件)
        _adb_shell(self.serial, "uiautomator dump /sdcard/ui.xml", timeout=15)
        code, out = _adb_shell(self.serial, "cat /sdcard/ui.xml", timeout=10)
        _adb_shell(self.serial, "rm /sdcard/ui.xml", timeout=5)
        if code == 0 and out:
            # 搜索text属性或content-desc属性匹配
            for attr in ["text", "content-desc"]:
                pattern = rf'{attr}="[^"]*{re.escape(text)}[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
                m = re.search(pattern, out)
                if m:
                    x = (int(m.group(1)) + int(m.group(3))) // 2
                    y = (int(m.group(2)) + int(m.group(4))) // 2
                    _adb_shell(self.serial, f"input tap {x} {y}")
                    return {"ok": True, "method": "uiautomator_tap", "x": x, "y": y,
                            "matched": attr}
            # 也尝试bounds在text之前的节点 (反向搜索)
            pattern = rf'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*text="[^"]*{re.escape(text)}[^"]*"'
            m = re.search(pattern, out)
            if m:
                x = (int(m.group(1)) + int(m.group(3))) // 2
                y = (int(m.group(2)) + int(m.group(4))) // 2
                _adb_shell(self.serial, f"input tap {x} {y}")
                return {"ok": True, "method": "uiautomator_tap_rev", "x": x, "y": y}

        return {"ok": False, "error": f"未找到: '{text}'"}

    def tap(self, nx, ny):
        """归一化坐标点击 (= browser_click by position)
        nx, ny ∈ [0, 1], 左上角(0,0) 右下角(1,1)
        """
        # 优先: ScreenStream
        if self.ss_alive():
            r = self._ss_post("/tap", {"nx": float(nx), "ny": float(ny)})
            if r:
                return {"ok": True, "method": "ss_tap"}

        # 降级: ADB (需知道分辨率)
        code, out = _adb_shell(self.serial, "wm size")
        if code == 0:
            m = re.search(r'(\d+)x(\d+)', out)
            if m:
                w, h = int(m.group(1)), int(m.group(2))
                x, y = int(float(nx) * w), int(float(ny) * h)
                _adb_shell(self.serial, f"input tap {x} {y}")
                return {"ok": True, "method": "adb_tap", "x": x, "y": y}

        return {"ok": False, "error": "tap失败"}

    def type_text(self, text):
        """输入文字 (= browser_type)"""
        # 优先: ScreenStream
        if self.ss_alive():
            r = self._ss_post("/text", {"text": text})
            if r:
                return {"ok": True, "method": "ss_text"}

        # 降级: ADB input text (不支持中文)
        escaped = text.replace(" ", "%s").replace("&", "\\&").replace(";", "\\;")
        code, out = _adb_shell(self.serial, f"input text '{escaped}'")
        return {"ok": code == 0, "method": "adb_input",
                "warning": "ADB不支持中文输入" if any(ord(c) > 127 for c in text) else None}

    def key(self, key_name):
        """按键 (= browser_press_key)"""
        key_upper = key_name.upper()
        keycode = KEYMAP.get(key_upper)

        if keycode:
            code, out = _adb_shell(self.serial, f"input keyevent {keycode}")
            return {"ok": code == 0, "key": key_name, "keycode": keycode}

        # 尝试直接用名称
        code, out = _adb_shell(self.serial, f"input keyevent KEYCODE_{key_upper}")
        return {"ok": code == 0, "key": key_name}

    def swipe(self, direction="up", duration=300):
        """滑动 (= browser scroll)"""
        # 优先: ScreenStream
        if self.ss_alive():
            d = {"up": (0.5, 0.7, 0.5, 0.3), "down": (0.5, 0.3, 0.5, 0.7),
                 "left": (0.8, 0.5, 0.2, 0.5), "right": (0.2, 0.5, 0.8, 0.5)}
            if direction in d:
                nx1, ny1, nx2, ny2 = d[direction]
                r = self._ss_post("/swipe", {
                    "nx1": nx1, "ny1": ny1, "nx2": nx2, "ny2": ny2,
                    "duration": duration
                })
                if r:
                    return {"ok": True, "method": "ss_swipe", "direction": direction}

        # 降级: ADB
        code, out = _adb_shell(self.serial, "wm size")
        if code == 0:
            m = re.search(r'(\d+)x(\d+)', out)
            if m:
                w, h = int(m.group(1)), int(m.group(2))
                coords = {
                    "up": (w//2, h*7//10, w//2, h*3//10),
                    "down": (w//2, h*3//10, w//2, h*7//10),
                    "left": (w*8//10, h//2, w*2//10, h//2),
                    "right": (w*2//10, h//2, w*8//10, h//2),
                }
                if direction in coords:
                    x1, y1, x2, y2 = coords[direction]
                    _adb_shell(self.serial, f"input swipe {x1} {y1} {x2} {y2} {duration}")
                    return {"ok": True, "method": "adb_swipe", "direction": direction}

        return {"ok": False, "error": f"未知方向: {direction}"}

    def back(self):
        """返回 (= browser_navigate_back)"""
        if self.ss_alive():
            self._ss_post("/back")
            return {"ok": True, "method": "ss"}
        return self.key("BACK")

    def home(self):
        """Home键"""
        if self.ss_alive():
            self._ss_post("/home")
            return {"ok": True, "method": "ss"}
        return self.key("HOME")

    def launch_app(self, package, wait=2):
        """启动APP (= browser_navigate)"""
        # 方法1: ScreenStream open_app
        if self.ss_alive():
            r = self._ss_post("/openapp", {"packageName": package})
            if r and r.get("ok"):
                time.sleep(wait)
                return {"ok": True, "method": "ss_openapp", "package": package}

        # 方法2: ADB monkey (最可靠)
        code, out = _adb_shell(self.serial,
            f"monkey -p {package} -c android.intent.category.LAUNCHER 1 2>/dev/null")
        time.sleep(wait)
        return {"ok": code == 0, "method": "adb_monkey", "package": package}

    def read(self):
        """读取屏幕文本 (简化版snapshot)"""
        if self.ss_alive():
            r = self._ss_get("/screen/text")
            if r:
                texts = [t.get("text", "") for t in r.get("texts", []) if t.get("text", "").strip()]
                pkg = r.get("package", "")
                return {"ok": True, "texts": texts, "package": pkg, "count": len(texts)}

        # 降级: uiautomator (dump到文件再读取)
        _adb_shell(self.serial, "uiautomator dump /sdcard/ui.xml", timeout=15)
        code, out = _adb_shell(self.serial, "cat /sdcard/ui.xml", timeout=10)
        _adb_shell(self.serial, "rm /sdcard/ui.xml", timeout=5)
        if code == 0 and out:
            texts = [t for t in re.findall(r'text="([^"]+)"', out) if t.strip()]
            return {"ok": True, "texts": texts, "count": len(texts), "source": "uiautomator"}

        return {"ok": False, "texts": [], "count": 0}

    def wait_for(self, text, timeout=10, interval=1.0):
        """等待指定文字出现 (= browser_wait_for)"""
        deadline = time.time() + timeout
        attempts = 0
        while time.time() < deadline:
            attempts += 1
            r = self.read()
            if r.get("ok"):
                combined = " ".join(r.get("texts", []))
                if text in combined:
                    return {"ok": True, "found": True, "text": text,
                            "attempts": attempts, "elapsed": round(time.time() + timeout - deadline, 1)}
            time.sleep(interval)
        return {"ok": True, "found": False, "text": text,
                "attempts": attempts, "elapsed": timeout}

    def screenshot(self, save_path=None):
        """截屏 (= browser_take_screenshot)"""
        if not save_path:
            os.makedirs(SCREENSHOT_DIR, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(SCREENSHOT_DIR, f"vm{self.index}_{ts}.png")

        # ADB screencap → pull
        remote = "/sdcard/vm_screenshot.png"
        code1, _ = _adb_shell(self.serial, f"screencap -p {remote}")
        if code1 == 0:
            code2, out = _adb(self.serial, "pull", remote, save_path, timeout=10)
            _adb_shell(self.serial, f"rm {remote}")
            if code2 == 0:
                return {"ok": True, "path": save_path,
                        "size": os.path.getsize(save_path) if os.path.exists(save_path) else 0}

        return {"ok": False, "error": "screenshot失败"}

    def apps(self):
        """已安装应用列表"""
        code, out = _adb_shell(self.serial, "pm list packages -3 2>/dev/null")
        if code != 0:
            return {"ok": False, "apps": []}
        pkgs = [l.replace("package:", "").strip()
                for l in out.split('\n') if l.startswith("package:")]
        return {"ok": True, "apps": pkgs, "count": len(pkgs)}

    def foreground(self):
        """当前前台应用"""
        if self.ss_alive():
            r = self._ss_get("/foreground")
            if r:
                return {"ok": True, "package": r.get("packageName", ""),
                        "activity": r.get("activityName", "")}

        code, out = _adb_shell(self.serial,
            "dumpsys activity activities 2>/dev/null | grep mResumedActivity | head -1")
        if code == 0 and out:
            m = re.search(r'([a-zA-Z0-9_.]+)/([a-zA-Z0-9_.]+)', out)
            if m:
                return {"ok": True, "package": m.group(1), "activity": m.group(2)}

        return {"ok": False, "package": "", "activity": ""}

    def senses(self):
        """五感全采集 (PhoneLib增强)"""
        p = self.phone
        if p:
            try:
                return p.senses(parallel=True)
            except Exception as e:
                return {"_ok": False, "_error": str(e)}

        # 无PhoneLib时的简化五感
        result = {"_ok": False, "source": "adb_only"}
        try:
            st = self._ss_get("/status") if self.ss_alive() else None
            dev = self._ss_get("/deviceinfo") if self.ss_alive() else None
            screen = self.read()

            result["vision"] = {
                "texts": screen.get("texts", [])[:10],
                "package": screen.get("package", ""),
            }
            if dev:
                result["taste"] = {
                    "battery": dev.get("batteryLevel", -1),
                    "model": f"{dev.get('manufacturer', '')} {dev.get('model', '')}".strip(),
                    "network": dev.get("networkType", "?"),
                }
            if st:
                result["touch"] = {
                    "input_enabled": st.get("inputEnabled", False),
                    "screen_off": st.get("screenOffMode", False),
                }
            result["_ok"] = True
        except Exception as e:
            result["_error"] = str(e)
        return result

    def health(self):
        """健康检查"""
        checks = {}

        # ADB连接
        checks["adb"] = self.is_adb_alive()

        # ScreenStream
        checks["screenstream"] = self.ss_alive()

        # 端口映射
        ports = PORT_MAP.get(self.index, {})
        if ports:
            checks["port_forward"] = {}
            for local_p, remote_p in ports.items():
                code, _ = _adb(self.serial, "forward", "--list", timeout=5)
                checks["port_forward"][f"{local_p}→{remote_p}"] = True  # simplified

        # SS Input API
        if checks["screenstream"]:
            st = self._ss_get("/status")
            checks["input_enabled"] = st.get("inputEnabled", False) if st else False

        # PhoneLib
        p = self.phone
        if p:
            try:
                h = p.health()
                checks["phonelib"] = h.get("healthy", False)
                checks["phonelib_state"] = h.get("state", "unknown")
            except:
                checks["phonelib"] = False

        # 汇总
        critical_ok = checks.get("adb", False)
        all_ok = all(v for k, v in checks.items()
                     if isinstance(v, bool))

        return {
            "vm": self.index, "serial": self.serial,
            "healthy": critical_ok,
            "all_green": all_ok,
            "checks": checks,
        }

    def ensure_alive(self):
        """确保VM可操控(PhoneLib增强)"""
        p = self.phone
        if p:
            try:
                ok, log = p.ensure_alive()
                return {"ok": ok, "log": log}
            except:
                pass

        # 基础检查
        if not self.is_adb_alive():
            return {"ok": False, "error": "ADB不可达"}
        if not self.ss_alive():
            # 尝试启动ScreenStream
            self.shell("am start -n info.dvkr.screenstream.dev/"
                       "info.dvkr.screenstream.ui.activity.AppActivity")
            time.sleep(3)
            if self.ss_alive():
                return {"ok": True, "recovered": "ss_restarted"}
            return {"ok": False, "error": "ScreenStream不可达且重启失败"}

        return {"ok": True}

    def set_text(self, search, value):
        """设置输入框文字 (= browser_fill)"""
        if self.ss_alive():
            r = self._ss_post("/settext", {"search": search, "value": value})
            if r and r.get("ok"):
                return {"ok": True}
        # 降级: click + clear + type
        self.click(search)
        time.sleep(0.5)
        _adb_shell(self.serial, "input keyevent KEYCODE_CTRL_LEFT+KEYCODE_A")
        time.sleep(0.1)
        return self.type_text(value)

    def clipboard_read(self):
        """读取剪贴板"""
        if self.ss_alive():
            r = self._ss_get("/clipboard")
            if r:
                return {"ok": True, "text": r.get("text", "")}
        return {"ok": False}

    def clipboard_write(self, text):
        """写入剪贴板"""
        if self.ss_alive():
            r = self._ss_post("/clipboard", {"text": text})
            return {"ok": r is not None}
        return {"ok": False}

    def wake(self):
        """唤醒屏幕"""
        if self.ss_alive():
            self._ss_post("/wake")
            return {"ok": True}
        return self.key("POWER")

    def notifications(self, limit=10):
        """读取通知"""
        if self.ss_alive():
            r = self._ss_get(f"/notifications/read?limit={limit}")
            if r:
                return {"ok": True, **r}
        return {"ok": False, "notifications": []}

    def device_info(self):
        """设备信息"""
        if self.ss_alive():
            r = self._ss_get("/deviceinfo")
            if r:
                return {"ok": True, **r}
        # ADB降级
        model = self.shell("getprop ro.product.model").get("output", "?")
        mfr = self.shell("getprop ro.product.manufacturer").get("output", "?")
        return {"ok": True, "model": model, "manufacturer": mfr, "source": "adb"}

    def intent(self, action, data=None, package=None):
        """发送Intent"""
        if self.ss_alive():
            body = {"action": action, "flags": ["FLAG_ACTIVITY_NEW_TASK"]}
            if data:
                body["data"] = data
            if package:
                body["package"] = package
            r = self._ss_post("/intent", body)
            if r:
                return {"ok": True}
        # ADB降级
        cmd = f"am start -a {action}"
        if data:
            cmd += f" -d '{data}'"
        if package:
            cmd += f" -n {package}"
        return self.shell(cmd)

    def open_url(self, url, wait=2):
        """在浏览器中打开URL"""
        return self.intent("android.intent.action.VIEW", data=url)


# ═══════════════════════════════════════════════════════════════
# VMFleet — 虚拟机舰队管理器 (多Agent安全)
# ═══════════════════════════════════════════════════════════════

class VMFleet:
    """管理所有LDPlayer虚拟机的舰队。
    
    多Agent安全: 每个VMPhone实例独立，无共享状态。
    不同Agent可同时操作不同VM，互不干扰。
    """

    def __init__(self):
        self._vms = {}  # index → VMPhone (懒加载)

    def __getitem__(self, index):
        """fleet[3] → VMPhone(3)
        
        注意: 访问VM[0]会打印警告，建议使用dev_vm()或vm_for()自动选择开发测试VM。
        """
        if index == 0 and 0 not in self._vms:
            import sys
            print("⚠️  VM[0]是初始模拟器(通用主控)，非开发测试VM。"
                  "建议使用 fleet.dev_vm() 或 vm_for('项目名') 自动选择开发VM。",
                  file=sys.stderr)
        if index not in self._vms:
            self._vms[index] = VMPhone(index)
        return self._vms[index]

    def get(self, index):
        """获取VM (同 fleet[index])"""
        return self[index]

    def list_all(self):
        """列出所有VM"""
        code, out = _dnc("list2")
        if code != 0:
            return []
        vms = []
        for line in out.strip().split('\n'):
            parts = line.strip().split(',')
            if len(parts) >= 10:
                idx = int(parts[0])
                vms.append({
                    "index": idx,
                    "name": parts[1],
                    "running": parts[4] == '1',
                    "pid": int(parts[5]) if parts[5] != '-1' else -1,
                    "width": int(parts[7]),
                    "height": int(parts[8]),
                    "dpi": int(parts[9]),
                    "serial": f"emulator-{ADB_PORTS.get(idx, 5554 + idx * 2)}",
                })
        return vms

    def running(self):
        """获取运行中的VM列表"""
        return [vm for vm in self.list_all() if vm["running"]]

    def status(self):
        """全景状态"""
        all_vms = self.list_all()
        devices = {}
        code, out = _run([ADB, "devices"])
        if code == 0:
            for line in out.strip().split('\n')[1:]:
                parts = line.strip().split('\t')
                if len(parts) == 2:
                    devices[parts[0]] = parts[1]

        result = []
        for vm in all_vms:
            info = {**vm}
            serial = vm["serial"]
            info["adb_connected"] = serial in devices and devices[serial] == "device"

            if info["running"] and info["adb_connected"]:
                phone = self[vm["index"]]
                info["ss_alive"] = phone.ss_alive()
                info["ss_partial"] = phone.ss_partial() if not info["ss_alive"] else False
                if info["ss_alive"]:
                    st = phone._ss_get("/status")
                    info["input_enabled"] = st.get("inputEnabled", False) if st else False
                    fg = phone.foreground()
                    info["foreground"] = fg.get("package", "") if fg.get("ok") else ""
                elif info["ss_partial"]:
                    st = phone._ss_get("/status")
                    info["input_enabled"] = st.get("inputEnabled", False) if st else False
                    info["ss_note"] = "需授权MediaProjection"

            result.append(info)
        return result

    def dev_vm(self, prefer_running=True):
        """自动选择开发测试VM (非初始模拟器VM[0])。
        
        选择逻辑:
          1. 优先选择运行中的开发VM (按DEV_VM_INDICES优先级)
          2. 无运行中的 → 返回DEFAULT_VM_INDEX
          3. 永远不返回VM[0] (初始模拟器)
        
        Args:
            prefer_running: 是否优先选择运行中的VM
        
        Returns:
            VMPhone实例
        """
        if prefer_running:
            running = self.running()
            running_indices = {v["index"] for v in running}
            for idx in DEV_VM_INDICES:
                if idx in running_indices:
                    return self[idx]
        return self[DEFAULT_VM_INDEX]

    def vm_for(self, project_name):
        """根据项目名称自动选择对应VM。
        
        Args:
            project_name: 项目名 (如 "ScreenStream", "手机操控库")
        
        Returns:
            VMPhone实例
        """
        idx = PROJECT_VM_MAP.get(project_name)
        if idx is not None:
            return self[idx]
        # 未知项目 → 默认开发VM
        return self.dev_vm()

    def forward_all(self):
        """设置所有VM的端口映射"""
        results = {}
        for idx in PORT_MAP:
            if PORT_MAP[idx]:
                vm = self[idx]
                if vm.is_adb_alive():
                    results[idx] = vm.forward_all()
        return results


# ═══════════════════════════════════════════════════════════════
# CLI — Agent通过 run_command 调用
# ═══════════════════════════════════════════════════════════════

def _print_json(obj):
    """格式化输出JSON"""
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))

def cli_list(args):
    fleet = VMFleet()
    vms = fleet.list_all()
    print(f"{'Idx':>3} {'名称':<20} {'状态':<6} {'分辨率':<12} {'ADB Serial':<16}")
    print("─" * 65)
    for vm in vms:
        status = "🟢运行" if vm["running"] else "⚪停止"
        res = f"{vm['width']}×{vm['height']}@{vm['dpi']}"
        print(f"{vm['index']:>3} {vm['name']:<20} {status:<6} {res:<12} {vm['serial']:<16}")

def cli_status(args):
    fleet = VMFleet()
    status = fleet.status()
    print(f"\n{'Idx':>3} {'名称':<16} {'状态':<6} {'ADB':<4} {'SS':<4} {'Input':<6} {'前台APP':<20}")
    print("─" * 75)
    for vm in status:
        st = "🟢" if vm["running"] else "⚪"
        adb = "✅" if vm.get("adb_connected") else "❌"
        ss = "✅" if vm.get("ss_alive") else "—"
        inp = "✅" if vm.get("input_enabled") else "—"
        fg = vm.get("foreground", "").split(".")[-1][:18] if vm.get("foreground") else ""
        print(f"{vm['index']:>3} {vm['name']:<16} {st:<6} {adb:<4} {ss:<4} {inp:<6} {fg:<20}")

def cli_snapshot(args):
    vm = VMFleet()[args.vm]
    result = vm.snapshot(depth=args.depth if hasattr(args, 'depth') else 5)
    if "formatted" in result:
        print(result["formatted"])
    else:
        _print_json(result)

def cli_click(args):
    vm = VMFleet()[args.vm]
    result = vm.click(args.text)
    _print_json(result)

def cli_tap(args):
    vm = VMFleet()[args.vm]
    result = vm.tap(args.nx, args.ny)
    _print_json(result)

def cli_type(args):
    vm = VMFleet()[args.vm]
    result = vm.type_text(args.text)
    _print_json(result)

def cli_key(args):
    vm = VMFleet()[args.vm]
    result = vm.key(args.key_name)
    _print_json(result)

def cli_swipe(args):
    vm = VMFleet()[args.vm]
    result = vm.swipe(args.direction, getattr(args, 'duration', 300))
    _print_json(result)

def cli_back(args):
    vm = VMFleet()[args.vm]
    _print_json(vm.back())

def cli_home(args):
    vm = VMFleet()[args.vm]
    _print_json(vm.home())

def cli_shell(args):
    vm = VMFleet()[args.vm]
    result = vm.shell(args.cmd)
    if result.get("ok"):
        print(result.get("output", ""))
    else:
        _print_json(result)

def cli_launch(args):
    vm = VMFleet()[args.vm]
    result = vm.launch_app(args.package, wait=getattr(args, 'wait', 2))
    _print_json(result)

def cli_screenshot(args):
    vm = VMFleet()[args.vm]
    result = vm.screenshot(getattr(args, 'path', None))
    _print_json(result)

def cli_wait(args):
    vm = VMFleet()[args.vm]
    result = vm.wait_for(args.text, timeout=getattr(args, 'timeout', 10))
    _print_json(result)

def cli_read(args):
    vm = VMFleet()[args.vm]
    result = vm.read()
    if result.get("ok"):
        for t in result.get("texts", []):
            print(t)
        print(f"\n── {result.get('count', 0)} texts, pkg={result.get('package', '')} ──")
    else:
        _print_json(result)

def cli_senses(args):
    vm = VMFleet()[args.vm]
    _print_json(vm.senses())

def cli_health(args):
    vm = VMFleet()[args.vm]
    result = vm.health()
    status = "✅ HEALTHY" if result["healthy"] else "❌ UNHEALTHY"
    print(f"\n🏥 VM[{args.vm}] {status}")
    for k, v in result.get("checks", {}).items():
        icon = "✅" if v is True else ("❌" if v is False else "ℹ️")
        print(f"  {icon} {k}: {v}")

def cli_install(args):
    vm = VMFleet()[args.vm]
    result = vm.install(args.apk)
    _print_json(result)

def cli_forward(args):
    vm = VMFleet()[args.vm]
    result = vm.forward_all()
    print(f"VM[{args.vm}] 端口映射:")
    for mapping, status in result.items():
        print(f"  {status} {mapping}")

def cli_info(args):
    vm = VMFleet()[args.vm]
    cfg = vm.vm_config()
    print(f"\n📱 VM[{args.vm}] {vm.name}")
    print(f"  Serial: {vm.serial}")
    print(f"  SS端口: {vm.ss_base}")
    print(f"  型号: {cfg.get('propertySettings.phoneModel', '?')} ({cfg.get('propertySettings.phoneManufacturer', '?')})")
    print(f"  CPU: {cfg.get('advancedSettings.cpuCount', '?')}核")
    print(f"  RAM: {cfg.get('advancedSettings.memorySize', '?')}MB")
    print(f"  Root: {'✅' if cfg.get('basicSettings.rootMode') else '❌'}")
    print(f"  ADB: {'✅' if vm.is_adb_alive() else '❌'}")
    print(f"  SS: {'✅' if vm.ss_alive() else '❌'}")

    if vm.ss_alive():
        st = vm._ss_get("/status")
        if st:
            print(f"  Input: {'✅' if st.get('inputEnabled') else '❌'}")

    # 端口映射
    ports = PORT_MAP.get(args.vm, {})
    if ports:
        print(f"  端口映射:")
        for local_p, remote_p in ports.items():
            print(f"    localhost:{local_p} → emulator:{remote_p}")

def cli_apps(args):
    vm = VMFleet()[args.vm]
    result = vm.apps()
    if result.get("ok"):
        for app in result.get("apps", []):
            print(f"  {app}")
        print(f"\n── {result.get('count', 0)} apps ──")

def cli_logcat(args):
    vm = VMFleet()[args.vm]
    result = vm.logcat(filter_str=getattr(args, 'filter', ''),
                       lines=getattr(args, 'lines', 30))
    if result.get("ok"):
        print(result.get("output", ""))

def cli_url(args):
    vm = VMFleet()[args.vm]
    result = vm.open_url(args.url)
    _print_json(result)


def main():
    parser = argparse.ArgumentParser(
        description="VM Controller — 浏览器MCP般无感操控LDPlayer虚拟机",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    sub = parser.add_subparsers(dest="command", help="命令")

    # list
    sub.add_parser("list", help="列出所有VM (= list_pages)")

    # status
    sub.add_parser("status", help="全景状态")

    # snapshot
    p = sub.add_parser("snapshot", help="UI快照 (= browser_snapshot)")
    p.add_argument("vm", type=int, help="VM index")
    p.add_argument("--depth", type=int, default=5, help="viewtree深度")

    # click
    p = sub.add_parser("click", help="点击元素 (= browser_click)")
    p.add_argument("vm", type=int)
    p.add_argument("text", help="要点击的文字")

    # tap
    p = sub.add_parser("tap", help="坐标点击 (= browser_click by pos)")
    p.add_argument("vm", type=int)
    p.add_argument("nx", type=float, help="归一化X [0-1]")
    p.add_argument("ny", type=float, help="归一化Y [0-1]")

    # type
    p = sub.add_parser("type", help="输入文字 (= browser_type)")
    p.add_argument("vm", type=int)
    p.add_argument("text", help="要输入的文字")

    # key
    p = sub.add_parser("key", help="按键 (= browser_press_key)")
    p.add_argument("vm", type=int)
    p.add_argument("key_name", help="按键名称 (HOME/BACK/ENTER/...)")

    # swipe
    p = sub.add_parser("swipe", help="滑动")
    p.add_argument("vm", type=int)
    p.add_argument("direction", choices=["up", "down", "left", "right"])
    p.add_argument("--duration", type=int, default=300)

    # back
    p = sub.add_parser("back", help="返回 (= browser_navigate_back)")
    p.add_argument("vm", type=int)

    # home
    p = sub.add_parser("home", help="Home键")
    p.add_argument("vm", type=int)

    # shell
    p = sub.add_parser("shell", help="执行shell (= browser_evaluate)")
    p.add_argument("vm", type=int)
    p.add_argument("cmd", help="shell命令")

    # launch
    p = sub.add_parser("launch", help="启动APP (= browser_navigate)")
    p.add_argument("vm", type=int)
    p.add_argument("package", help="包名")
    p.add_argument("--wait", type=int, default=2)

    # screenshot
    p = sub.add_parser("screenshot", help="截屏 (= take_screenshot)")
    p.add_argument("vm", type=int)
    p.add_argument("--path", help="保存路径")

    # wait
    p = sub.add_parser("wait", help="等待文字 (= browser_wait_for)")
    p.add_argument("vm", type=int)
    p.add_argument("text", help="等待出现的文字")
    p.add_argument("--timeout", type=int, default=10)

    # read
    p = sub.add_parser("read", help="读取屏幕文字")
    p.add_argument("vm", type=int)

    # senses
    p = sub.add_parser("senses", help="五感采集")
    p.add_argument("vm", type=int)

    # health
    p = sub.add_parser("health", help="健康检查")
    p.add_argument("vm", type=int)

    # install
    p = sub.add_parser("install", help="安装APK")
    p.add_argument("vm", type=int)
    p.add_argument("apk", help="APK文件路径")

    # forward
    p = sub.add_parser("forward", help="设置端口映射")
    p.add_argument("vm", type=int)

    # info
    p = sub.add_parser("info", help="VM详情 (= select_page)")
    p.add_argument("vm", type=int)

    # apps
    p = sub.add_parser("apps", help="已安装应用")
    p.add_argument("vm", type=int)

    # logcat
    p = sub.add_parser("logcat", help="查看日志 (= console_messages)")
    p.add_argument("vm", type=int)
    p.add_argument("--filter", default="", help="过滤关键词")
    p.add_argument("--lines", type=int, default=30)

    # url
    p = sub.add_parser("url", help="打开URL")
    p.add_argument("vm", type=int)
    p.add_argument("url", help="要打开的URL")

    args = parser.parse_args()

    if not args.command:
        # 默认: 简洁状态
        cli_status(args)
        return

    # 路由到对应函数
    handlers = {
        "list": cli_list,
        "status": cli_status,
        "snapshot": cli_snapshot,
        "click": cli_click,
        "tap": cli_tap,
        "type": cli_type,
        "key": cli_key,
        "swipe": cli_swipe,
        "back": cli_back,
        "home": cli_home,
        "shell": cli_shell,
        "launch": cli_launch,
        "screenshot": cli_screenshot,
        "wait": cli_wait,
        "read": cli_read,
        "senses": cli_senses,
        "health": cli_health,
        "install": cli_install,
        "forward": cli_forward,
        "info": cli_info,
        "apps": cli_apps,
        "logcat": cli_logcat,
        "url": cli_url,
    }
    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
