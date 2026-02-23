"""
手机操控统一库 — 远程弹性架构
==============================
零外部依赖(纯urllib)，封装ScreenStream 90+ HTTP API。
支持本地USB/WiFi直连/Tailscale/公网穿透全链路。
内建自动发现、心跳监控、断线重连、负面状态恢复。

使用:
  from phone_lib import Phone

  # 自动发现最优连接（USB→WiFi→Tailscale）
  p = Phone()                              # auto-discover
  p = Phone(host="192.168.31.100")          # WiFi直连
  p = Phone(host="100.100.1.5")             # Tailscale
  p = Phone(url="https://my.domain.com")    # 公网穿透

  # 五感操控
  p.open_app("com.eg.android.AlipayGphone")
  p.alipay("10000007")  # 扫一扫
  texts = p.read()
  p.click("我的")
  p.home()

  # 弹性特性
  p.health()                  # 完整健康检查
  p.ensure_alive()            # 确保连接+自动恢复
  p.senses()                  # 五感全采集
"""

import json, time, os, shutil, subprocess, threading, logging
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

log = logging.getLogger("phone_lib")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s [PhoneLib] %(message)s", "%H:%M:%S"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)

# ADB路径自动检测：PATH > 项目内SDK > 环境变量
_PROJECT_ADB = os.path.join(os.path.dirname(__file__), "..",
    "构建部署", "android-sdk", "platform-tools",
    "adb.exe" if os.name == "nt" else "adb")

def _find_adb():
    """查找ADB路径，找不到返回None（不再fallback到'adb'）"""
    return (shutil.which("adb")
            or (os.path.abspath(_PROJECT_ADB) if os.path.isfile(_PROJECT_ADB) else None)
            or os.environ.get("ADB_PATH")
            or None)

def _adb_available():
    """ADB二进制是否存在"""
    return _find_adb() is not None

def _get_usb_serial():
    """获取第一个USB连接的ADB设备序列号（排除WiFi设备）"""
    adb = _find_adb()
    if not adb:
        return None
    try:
        r = subprocess.run([adb, "devices"],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if "\tdevice" in line:
                serial = line.split("\t")[0]
                if ":" not in serial:  # WiFi设备格式为 IP:PORT
                    return serial
    except Exception:
        pass
    return None

# 缓存USB序列号，避免每次ADB调用都查询
_usb_serial_cache = None

def _adb(*args, timeout=10, serial=None):
    """执行ADB命令，返回(stdout, ok)。
    ADB二进制不存在时安全返回('', False)。
    多设备连接时自动指定USB设备。"""
    global _usb_serial_cache
    adb = _find_adb()
    if not adb:
        return "", False
    try:
        cmd = [adb]
        # 非devices命令时，检查是否需要指定设备
        if args and args[0] != "devices":
            target = serial
            if not target:
                if _usb_serial_cache is None:
                    _usb_serial_cache = _get_usb_serial() or ""
                target = _usb_serial_cache
            if target:
                cmd.extend(["-s", target])
        cmd.extend(args)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode == 0
    except Exception as e:
        return str(e), False


# ============================================================
# 连接发现器 — localhost→WiFi→Tailscale 三层探测
# ============================================================

def discover(port_range=range(8080, 8100), timeout=1.5, extra_hosts=None):
    """自动发现手机ScreenStream服务，返回最优URL或None。
    探测顺序：localhost(USB) → 手机WiFi IP → Tailscale IP → extra_hosts
    Args:
        extra_hosts: 额外探测IP列表，用于无ADB时手动指定候选地址
    """
    candidates = []

    # Layer 1: localhost (USB adb forward)
    for port in port_range:
        url = f"http://127.0.0.1:{port}"
        if _probe(url, timeout=0.5):
            candidates.append((url, "usb", 0))
            break

    # Layer 2: 手机WiFi IP（通过ADB获取）
    wifi_ip = _get_phone_wifi_ip()
    if wifi_ip:
        for port in port_range:
            url = f"http://{wifi_ip}:{port}"
            if _probe(url, timeout=timeout):
                candidates.append((url, "wifi", 1))
                break

    # Layer 3: Tailscale IP（通过ADB获取）
    ts_ip = _get_phone_tailscale_ip()
    if ts_ip:
        for port in port_range:
            url = f"http://{ts_ip}:{port}"
            if _probe(url, timeout=timeout):
                candidates.append((url, "tailscale", 2))
                break

    # Layer 4: 手动指定的候选地址（无ADB时的回退）
    for host in (extra_hosts or []):
        for port in port_range:
            url = f"http://{host}:{port}"
            if _probe(url, timeout=timeout):
                mode = "tailscale" if host.startswith("100.") else "wifi"
                candidates.append((url, mode, 3))
                break

    # Layer 5: 尝试从PC局域网搜索（同网段扫描前10个IP）
    if not candidates:
        local_subnet = _get_local_subnet()
        if local_subnet:
            for ip_suffix in range(1, 11):
                host = f"{local_subnet}.{ip_suffix}"
                for port in (8081, 8084, 8086):
                    url = f"http://{host}:{port}"
                    if _probe(url, timeout=0.8):
                        candidates.append((url, "wifi-scan", 4))
                        break
                if candidates:
                    break

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[2])
    best = candidates[0]
    log.info(f"发现: {best[0]} ({best[1]})")
    return best[0]


def _probe(url, timeout=1.0):
    """探测URL是否为ScreenStream服务"""
    try:
        req = Request(url + "/status", method="GET")
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return "connected" in data
    except Exception:
        return False


def _get_phone_wifi_ip():
    """获取手机可达WiFi IP。三种来源：
    1. adb devices 中的WiFi ADB条目 (IP:PORT格式，最可靠)
    2. adb shell ip addr show wlan0 (WiFi接口IP)
    3. adb shell ip route (默认路由src IP，可能是移动数据)"""
    import re

    # 来源1: WiFi ADB设备列表 — 最可靠（已证明可达）
    out, ok = _adb("devices")
    if ok:
        for line in out.splitlines():
            if "\tdevice" in line:
                serial = line.split("\t")[0]
                if ":" in serial:  # WiFi ADB格式: IP:PORT
                    ip = serial.rsplit(":", 1)[0]
                    if not ip.startswith("127."):
                        return ip

    # 来源2: wlan0接口IP
    out, ok = _adb("shell", "ip", "addr", "show", "wlan0")
    if ok:
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out)
        if m and not m.group(1).startswith("127."):
            return m.group(1)

    # 来源3: 默认路由（可能是移动数据IP，不一定可从PC访问）
    out, ok = _adb("shell", "ip", "route")
    if ok:
        m = re.search(r"src (\d+\.\d+\.\d+\.\d+)", out)
        if m and not m.group(1).startswith("127."):
            return m.group(1)

    return None


def _get_phone_tailscale_ip():
    """通过ADB获取手机Tailscale IP (100.x.x.x)"""
    out, ok = _adb("shell", "ip", "addr", "show", "tailscale0")
    if ok:
        import re
        m = re.search(r"inet (100\.\d+\.\d+\.\d+)", out)
        if m:
            return m.group(1)
    return None


def _get_local_subnet():
    """获取PC本机局域网网段（用于同网段扫描）"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        parts = ip.split(".")
        if len(parts) == 4:
            return ".".join(parts[:3])
    except Exception:
        pass
    return None


# ============================================================
# 负面状态矩阵 — 每种故障的检测+恢复方法
# ============================================================

class NegativeState:
    """负面状态枚举与恢复策略"""
    HEALTHY = "healthy"
    SCREEN_OFF = "screen_off"         # 手机锁屏/息屏
    A11Y_DEAD = "a11y_dead"           # 无障碍服务断开
    APP_KILLED = "app_killed"         # ScreenStream被杀
    PORT_CHANGED = "port_changed"     # 端口漂移
    USB_LOST = "usb_lost"             # USB断开
    WIFI_LOST = "wifi_lost"           # WiFi断开
    PHONE_OFF = "phone_off"           # 手机关机/无响应
    BATTERY_LOW = "battery_low"       # 电量<10%
    DOZE_MODE = "doze_mode"           # Doze省电冻结

    @staticmethod
    def detect(phone):
        """诊断当前负面状态，返回(state, detail)"""
        # Step 1: HTTP可达？
        try:
            req = Request(phone.base + "/status", method="GET")
            with urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            # HTTP不可达 — 区分原因
            if phone._has_adb:
                adb_out, adb_ok = _adb("devices")
                if not adb_ok or phone._serial_hint not in adb_out:
                    return NegativeState.USB_LOST, "ADB不可达"
                return NegativeState.APP_KILLED, str(e)
            # 无ADB模式: 无法区分USB/APP，统一报网络不可达
            return NegativeState.WIFI_LOST, f"HTTP不可达: {e}"

        # Step 2: 无障碍服务？
        if not data.get("inputEnabled", False):
            return NegativeState.A11Y_DEAD, "inputEnabled=false"

        # Step 3: 屏幕状态？
        if data.get("screenOffMode", False):
            return NegativeState.SCREEN_OFF, "screenOffMode=true"

        # Step 4: 电量？
        try:
            dev = phone.device()
            battery = dev.get("batteryLevel", 100)
            if battery < 10:
                return NegativeState.BATTERY_LOW, f"battery={battery}%"
        except Exception:
            pass

        return NegativeState.HEALTHY, "ok"

    @staticmethod
    def detect_all(phone):
        """检测所有叠加的负面状态，返回list[(state, detail)]。
        用于多故障叠加时的完整诊断。"""
        issues = []
        try:
            req = Request(phone.base + "/status", method="GET")
            with urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            if phone._has_adb:
                adb_out, adb_ok = _adb("devices")
                if not adb_ok or phone._serial_hint not in adb_out:
                    issues.append((NegativeState.USB_LOST, "ADB不可达"))
                else:
                    issues.append((NegativeState.APP_KILLED, str(e)))
            else:
                issues.append((NegativeState.WIFI_LOST, f"HTTP不可达: {e}"))
            return issues  # 连接不通时无法检测其他状态

        if not data.get("inputEnabled", False):
            issues.append((NegativeState.A11Y_DEAD, "inputEnabled=false"))
        if data.get("screenOffMode", False):
            issues.append((NegativeState.SCREEN_OFF, "screenOffMode=true"))
        try:
            dev = phone.device()
            battery = dev.get("batteryLevel", 100)
            if battery < 10:
                issues.append((NegativeState.BATTERY_LOW, f"battery={battery}%"))
        except Exception:
            pass
        return issues

    # 恢复优先级（从高到低）— 多故障叠加时按此顺序恢复
    RECOVERY_PRIORITY = [
        "wifi_lost",      # 1. 网络不通 → 切换链路
        "usb_lost",       # 2. USB断开 → 切换WiFi/Tailscale
        "app_killed",     # 3. APP被杀 → 重启APP
        "screen_off",     # 4. 息屏 → 唤醒
        "a11y_dead",      # 5. 无障碍断 → 重新启用
        "doze_mode",      # 6. Doze → 取消冻结
        "battery_low",    # 7. 电量低 → 告警
    ]

    @staticmethod
    def recover(phone, state, detail=""):
        """执行恢复操作，返回(success, message)"""
        log.info(f"恢复: {state} ({detail})")
        try:
            if state == NegativeState.SCREEN_OFF:
                phone.post("/wake")
                time.sleep(1)
                return True, "已唤醒屏幕"

            elif state == NegativeState.A11Y_DEAD:
                # 尝试通过API自启（需root）
                r = phone.post("/a11y/enable")
                if r.get("ok"):
                    return True, "无障碍已重新启用(root)"
                # ADB方式（仅当ADB可用时）
                if phone._has_adb:
                    pkg = "info.dvkr.screenstream.dev"
                    comp = f"{pkg}/info.dvkr.screenstream.input.InputService"
                    _adb("shell", "settings", "put", "secure",
                         "enabled_accessibility_services", comp)
                    _adb("shell", "settings", "put", "secure",
                         "accessibility_enabled", "1")
                    time.sleep(2)
                    return True, "无障碍已通过ADB重新启用"
                return False, "无障碍断开且无ADB，需root API或手动重启"

            elif state == NegativeState.APP_KILLED:
                if phone._has_adb:
                    pkg = "info.dvkr.screenstream.dev"
                    _adb("shell", "monkey", "-p", pkg, "-c",
                         "android.intent.category.LAUNCHER", "1")
                    time.sleep(5)
                new_url = discover()
                if new_url:
                    phone.base = new_url
                    return True, f"APP已重启，新地址: {new_url}"
                return False, "APP重启后未能探测到服务"

            elif state == NegativeState.USB_LOST:
                new_url = discover()
                if new_url and "127.0.0.1" not in new_url:
                    phone.base = new_url
                    return True, f"USB断开，切换到: {new_url}"
                wifi_ip = _get_phone_wifi_ip()
                if wifi_ip:
                    _adb("connect", f"{wifi_ip}:5555")
                    time.sleep(2)
                    new_url = discover()
                    if new_url:
                        phone.base = new_url
                        return True, f"WiFi ADB重连: {new_url}"
                return False, "USB断开且无法通过WiFi重连"

            elif state == NegativeState.WIFI_LOST:
                # 纯远程模式: 重新发现所有可能的链路
                new_url = discover()
                if new_url:
                    phone.base = new_url
                    return True, f"网络恢复，切换到: {new_url}"
                return False, "所有网络链路不可达"

            elif state == NegativeState.BATTERY_LOW:
                return True, f"电量低({detail})，建议充电。功能仍可用"

            elif state == NegativeState.DOZE_MODE:
                if phone._has_adb:
                    _adb("shell", "dumpsys", "deviceidle", "unforce")
                phone.post("/wake")
                return True, "已退出Doze模式"

            elif state == NegativeState.PHONE_OFF:
                return False, "手机无响应，需物理操作"

        except Exception as e:
            return False, f"恢复失败: {e}"
        return False, f"未知状态: {state}"

    @staticmethod
    def recover_all(phone, max_rounds=3):
        """叠加恢复: 检测所有负面状态，按优先级链逐个恢复。
        返回(all_ok, recovery_log)"""
        recovery_log = []
        for round_num in range(max_rounds):
            issues = NegativeState.detect_all(phone)
            if not issues:
                if round_num > 0:
                    recovery_log.append(f"✅ 第{round_num+1}轮全部恢复")
                return True, recovery_log

            # 按优先级排序
            priority = NegativeState.RECOVERY_PRIORITY
            issues.sort(key=lambda x: priority.index(x[0]) if x[0] in priority else 99)

            recovery_log.append(f"--- 第{round_num+1}轮: 发现{len(issues)}个问题 ---")
            for state, detail in issues:
                recovery_log.append(f"  ⚠️ {state}: {detail}")
                ok, msg = NegativeState.recover(phone, state, detail)
                recovery_log.append(f"  → {'✅' if ok else '❌'} {msg}")
                if not ok and state in (NegativeState.WIFI_LOST, NegativeState.USB_LOST,
                                        NegativeState.PHONE_OFF):
                    recovery_log.append(f"  ❌ 致命故障无法恢复，停止")
                    return False, recovery_log
            time.sleep(1)

        issues = NegativeState.detect_all(phone)
        all_ok = len(issues) == 0
        if not all_ok:
            recovery_log.append(f"❌ {max_rounds}轮后仍有{len(issues)}个问题")
        return all_ok, recovery_log


class Phone:
    """远程弹性手机操控。支持自动发现、心跳、重试、负面状态恢复。"""

    def __init__(self, host=None, port=8084, url=None, auto_discover=True,
                 retry=2, retry_delay=1.0, heartbeat_sec=0):
        """
        Args:
            host: 手机IP (None=localhost/auto)。例: "192.168.31.100"
            port: ScreenStream端口 (默认8084，扫描8080-8099)
            url:  完整URL (优先级最高)。例: "https://my.domain.com"
            auto_discover: host为None时自动发现最优连接
            retry: HTTP失败重试次数
            retry_delay: 重试间隔(秒)
            heartbeat_sec: >0时启动后台心跳线程(秒)
        """
        self._retry = retry
        self._retry_delay = retry_delay
        self._serial_hint = ""  # ADB设备序列号提示
        self._last_health = time.time()
        self._heartbeat_thread = None
        self._heartbeat_stop = threading.Event()
        self._connection_mode = "unknown"  # usb/wifi/tailscale/url

        if url:
            self.base = url.rstrip("/")
            self._connection_mode = "url"
        elif host:
            self.base = f"http://{host}:{port}"
            self._connection_mode = "wifi" if not host.startswith("127.") else "usb"
        elif auto_discover:
            found = discover()
            if found:
                self.base = found
            else:
                self.base = f"http://127.0.0.1:{port}"
                log.warning(f"自动发现失败，回退到 {self.base}")
        else:
            self.base = f"http://127.0.0.1:{port}"
            self._connection_mode = "usb"

        # 尝试获取ADB序列号
        out, ok = _adb("devices")
        if ok:
            for line in out.splitlines():
                if "\tdevice" in line:
                    self._serial_hint = line.split("\t")[0]
                    break

        # ADB可用性检测（远程模式可能无ADB）
        self._has_adb = bool(self._serial_hint)

        if heartbeat_sec > 0:
            self._start_heartbeat(heartbeat_sec)

    def __repr__(self):
        return f"Phone({self.base}, mode={self._connection_mode})"

    def __del__(self):
        self._heartbeat_stop.set()

    def _http(self, method, path, body=None, timeout=15):
        url = self.base + path
        data = json.dumps(body).encode() if body else None
        headers = {"Content-Type": "application/json"} if data else {}
        last_err = None
        for attempt in range(1 + self._retry):
            req = Request(url, data=data, headers=headers, method=method)
            try:
                with urlopen(req, timeout=timeout) as resp:
                    raw = resp.read().decode()
                    try:
                        return json.loads(raw)
                    except Exception:
                        return {"_raw": raw}
            except HTTPError as e:
                return {"_error": e.code}
            except (URLError, OSError, TimeoutError) as e:
                last_err = e
                if attempt < self._retry:
                    time.sleep(self._retry_delay * (attempt + 1))
            except Exception as e:
                last_err = e
                break
        return {"_error": -1, "_msg": str(last_err)}

    # === 基础操作 ===
    def get(self, path): return self._http("GET", path)
    def post(self, path, body=None): return self._http("POST", path, body)
    def wait(self, sec): time.sleep(sec)
    def home(self): self.post("/home"); self.wait(0.8)
    def back(self): self.post("/back"); self.wait(0.3)

    # === 感知 ===
    def status(self): return self.get("/status")
    def device(self): return self.get("/deviceinfo")
    def foreground(self): return self.get("/foreground").get("packageName", "")
    def notifications(self, limit=10): return self.get(f"/notifications/read?limit={limit}")

    def read(self):
        """读取屏幕文本，返回(texts_list, package)"""
        r = self.get("/screen/text")
        return [t.get("text", "") for t in r.get("texts", [])], r.get("package", "")

    def read_count(self):
        """快速获取文本/可点击数量"""
        r = self.get("/screen/text")
        return r.get("textCount", 0), r.get("clickableCount", 0)

    # === 导航 ===
    def tap(self, nx, ny): return self.post("/tap", {"nx": nx, "ny": ny})
    def click(self, text): return self.post("/findclick", {"text": text})
    def swipe(self, direction="up", duration=300):
        d = {"up": (0.5,0.7,0.5,0.3), "down": (0.5,0.3,0.5,0.7),
             "left": (0.8,0.5,0.2,0.5), "right": (0.2,0.5,0.8,0.5)}
        if direction not in d:
            return {"_error": f"unknown direction: {direction}"}
        nx1, ny1, nx2, ny2 = d[direction]
        return self.post("/swipe", {"nx1":nx1,"ny1":ny1,"nx2":nx2,"ny2":ny2,"duration":duration})

    # === 系统 ===
    def wake(self): return self.post("/wake")
    def lock(self): return self.post("/lock")
    def screenshot(self): return self.post("/screenshot")
    def volume(self, level): return self.post("/volume", {"stream": "music", "level": level})
    def brightness(self, level): return self.post(f"/brightness/{level}")

    # === 剪贴板 ===
    def clipboard_read(self): return self.get("/clipboard").get("text")
    def clipboard_write(self, text): return self.post("/clipboard", {"text": text})

    # === APP启动 ===
    def open_app(self, pkg, wait_sec=2):
        """启动APP，自动处理OPPO弹窗"""
        self.post("/openapp", {"packageName": pkg})
        self.wait(wait_sec)
        self._dismiss_oppo()
        if pkg.split('.')[-1].lower() not in self.foreground().lower():
            self.intent("android.intent.action.MAIN", package=pkg,
                       categories=["android.intent.category.LAUNCHER"])
            self.wait(2)
            self._dismiss_oppo()

    def intent(self, action, data=None, package=None, categories=None, extras=None,
               flags=None):
        """发送Intent"""
        body = {"action": action, "flags": flags or ["FLAG_ACTIVITY_NEW_TASK", "FLAG_ACTIVITY_CLEAR_TASK"]}
        if data: body["data"] = data
        if package: body["package"] = package
        if categories: body["categories"] = categories
        if extras: body["extras"] = extras
        return self.post("/intent", body)

    def monkey_open(self, pkg, wait_sec=3):
        """用monkey命令启动APP（绕过OPPO弹窗拦截，最可靠）。
        优先ADB monkey，无ADB时回退到HTTP /intent。"""
        if self._has_adb:
            _adb("shell", "monkey", "-p", pkg, "-c",
                 "android.intent.category.LAUNCHER", "1")
        else:
            self.intent("android.intent.action.MAIN", package=pkg,
                       categories=["android.intent.category.LAUNCHER"])
        self.wait(wait_sec)

    def search_in_app(self, search_text, wait_sec=3):
        """APP内搜索：纯HTTP实现，无ADB依赖。
        策略1: findclick"搜索栏"(淘宝等)
        策略2: tap顶部搜索区域(京东/拼多多等)
        然后: 清空→输入→回车"""
        # 策略1: findclick"搜索栏"(仅尝试搜索栏，不尝试"搜索"避免误触底部Tab)
        r = self.click("搜索栏")
        if r.get("ok"):
            self.wait(1)
        else:
            # 策略2: tap顶部搜索区域(归一化坐标: x≈0.53, y≈0.07)
            self.tap(0.53, 0.07)
            self.wait(1)
        # 清空搜索框: /settext优先，回退到Ctrl+A → Delete
        r_clear = self.post("/settext", {"search": "", "value": ""})
        if not r_clear or not r_clear.get("ok"):
            # Ctrl+A 全选 → Backspace 删除（通过/key API发送keysym）
            self.post("/key", {"keysym": 0x61, "down": True, "ctrl": True})   # Ctrl+A
            self.post("/key", {"keysym": 0x61, "down": False, "ctrl": True})
            self.wait(0.1)
            self.post("/key", {"keysym": 0xFF08, "down": True})  # Backspace
            self.post("/key", {"keysym": 0xFF08, "down": False})
        self.wait(0.3)
        # 输入搜索文本
        self.post("/text", {"text": search_text})
        self.wait(0.5)
        # 回车搜索（keysym 0xFF0D = Return）
        self.post("/key", {"keysym": 0xFF0D, "down": True})
        self.post("/key", {"keysym": 0xFF0D, "down": False})
        self.wait(wait_sec)
        return self.read()

    def _dismiss_oppo(self):
        """处理OPPO安全弹窗"""
        for _ in range(2):
            if "permission" not in self.foreground().lower():
                return
            for btn in ["允许", "始终允许", "打开", "确定"]:
                self.click(btn); self.wait(0.2)
            self.back(); self.wait(0.5)

    # === Scheme快捷方式 ===
    def alipay(self, app_id, wait_sec=2.5):
        """支付宝scheme直跳"""
        self.intent("android.intent.action.VIEW",
                   data=f"alipays://platformapi/startapp?appId={app_id}")
        self.wait(wait_sec)

    def amap_navi(self, lat, lon):
        """高德导航"""
        self.intent("android.intent.action.VIEW",
                   data=f"androidamap://navi?sourceApplication=test&lat={lat}&lon={lon}&dev=0&style=2")
        self.wait(3)

    def amap_search(self, keyword):
        """高德POI搜索"""
        self.intent("android.intent.action.VIEW",
                   data=f"androidamap://poi?sourceApplication=test&keywords={keyword}&dev=0")
        self.wait(3)

    def bili(self, path, wait_sec=2.5):
        """B站scheme直跳"""
        self.intent("android.intent.action.VIEW", data=f"bilibili://{path}")
        self.wait(wait_sec)

    def baidumap(self, destination):
        """百度地图导航"""
        self.intent("android.intent.action.VIEW",
                   data=f"baidumap://map/direction?destination={destination}")
        self.wait(3)

    # === 验证 ===
    def is_app(self, keyword):
        """检查当前前台APP是否包含关键词"""
        return keyword.lower() in self.foreground().lower()

    def has_text(self, *keywords):
        """检查屏幕是否包含任一关键词"""
        texts, _ = self.read()
        combined = " ".join(texts)
        return any(k in combined for k in keywords)

    # === 高级组合 ===
    def collect_status(self):
        """一键采集设备全状态"""
        d = self.device()
        n = self.notifications(5)
        return {
            "battery": d.get("batteryLevel", -1),
            "charging": d.get("isCharging", False),
            "network": d.get("networkType", "?"),
            "net_ok": d.get("networkConnected", False),
            "model": f"{d.get('manufacturer','')} {d.get('model','')}",
            "storage_free_gb": round(d.get("storageAvailableMB", 0) / 1024, 1),
            "notif_count": n.get("total", 0),
            "fg_app": self.foreground().split(".")[-1],
        }

    def report_to_clipboard(self, prefix=""):
        """采集状态并写入剪贴板"""
        s = self.collect_status()
        text = (f"{prefix}"
                f"电量:{s['battery']}%{'⚡' if s['charging'] else ''} "
                f"网络:{s['network']} "
                f"存储:{s['storage_free_gb']}GB "
                f"通知:{s['notif_count']}条")
        self.clipboard_write(text)
        return text

    # === 高频日常场景（基于QuestMobile 2025数据） ===

    def check_notifications_smart(self):
        """智能通知检查：分类统计+识别重要通知"""
        n = self.notifications(20)
        items = n.get("notifications", [])
        cats = {"social": [], "shopping": [], "finance": [], "system": [], "other": []}
        social_keys = ["tencent", "weixin", "qq", "whatsapp", "telegram"]
        shop_keys = ["taobao", "jingdong", "pinduoduo", "meituan", "ele"]
        finance_keys = ["alipay", "bank", "wechat"]
        for item in items:
            pkg = str(item.get("package", "")).lower()
            title = str(item.get("title", ""))
            entry = {"title": title, "pkg": pkg.split(".")[-1]}
            if any(k in pkg for k in social_keys): cats["social"].append(entry)
            elif any(k in pkg for k in shop_keys): cats["shopping"].append(entry)
            elif any(k in pkg for k in finance_keys): cats["finance"].append(entry)
            elif "android" in pkg: cats["system"].append(entry)
            else: cats["other"].append(entry)
        return {"total": n.get("total", 0), "categories": cats}

    def quick_pay_scan(self):
        """一键支付宝扫码"""
        self.alipay("10000007")
        return self.is_app("alipay") or self.is_app("eg.android")

    def quick_pay_code(self):
        """一键出示付款码"""
        self.alipay("20000056")
        return self.is_app("alipay") or self.is_app("eg.android")

    def quick_express(self):
        """一键查快递"""
        self.alipay("20000754")
        return self.is_app("alipay") or self.is_app("eg.android")

    def quick_navigate(self, destination):
        """一键导航到目的地（高德）"""
        self.amap_search(destination)
        return self.is_app("autonavi")

    def quick_search_video(self, keyword):
        """一键搜索B站视频"""
        self.bili(f"search?keyword={keyword}")
        return self.is_app("bili") or self.is_app("danmaku")

    def quick_bill(self):
        """一键查看支付宝账单"""
        self.alipay("20000003")
        return self.is_app("alipay") or self.is_app("eg.android")

    def daily_check(self):
        """每日巡检：设备+通知+快递"""
        results = {}
        results["device"] = self.collect_status()
        results["notifications"] = self.check_notifications_smart()
        self.alipay("20000754"); self.wait(2)
        texts, _ = self.read()
        results["express"] = [t for t in texts if any(k in t for k in ["快递", "物流", "签收", "派送"])]
        self.home()
        return results

    # ============================================================
    # 弹性层 — 健康检查、自动恢复、五感采集、心跳
    # ============================================================

    def health(self):
        """完整健康检查，返回 {state, detail, connection, base_url, senses}"""
        state, detail = NegativeState.detect(self)
        result = {
            "state": state,
            "detail": detail,
            "connection": self._connection_mode,
            "base_url": self.base,
            "healthy": state == NegativeState.HEALTHY,
        }
        if state == NegativeState.HEALTHY:
            try:
                s = self.status()
                result["input_enabled"] = s.get("inputEnabled", False)
                result["screen_off"] = s.get("screenOffMode", False)
                d = self.device()
                result["battery"] = d.get("batteryLevel", -1)
                result["network"] = d.get("networkType", "?")
                result["net_ok"] = d.get("networkConnected", False)
            except Exception:
                pass
        self._last_health = time.time()
        return result

    def ensure_alive(self, max_attempts=3):
        """确保手机可操控。自动检测+恢复所有叠加负面状态。
        使用优先级链处理多故障同时发生的情况。
        返回 (alive: bool, recovery_log: list[str])"""
        return NegativeState.recover_all(self, max_rounds=max_attempts)

    def senses(self):
        """五感全采集 — 一次调用获取手机完整感知状态。
        返回 {vision, hearing, touch, smell, taste}"""
        result = {"_ok": False}
        try:
            # 👁 视觉：屏幕内容 + 前台APP + 可点击元素
            screen = self.get("/screen/text")
            texts = [t.get("text", "") for t in screen.get("texts", [])]
            clickables = [c.get("text", "") or c.get("label", "") for c in screen.get("clickables", [])]
            pkg = screen.get("package", "") or self.foreground()
            result["vision"] = {
                "foreground_app": pkg,
                "screen_texts": texts[:20],
                "text_count": len(texts),
                "clickables": clickables[:20],
                "clickable_count": len(clickables),
            }

            # 👂 听觉：媒体状态 + 音量
            dev = self.device()
            result["hearing"] = {
                "volume_music": dev.get("volumeMusic", -1),
                "volume_ring": dev.get("volumeRing", -1),
                "dnd": dev.get("dndEnabled", False),
            }

            # 🖐 触觉：输入状态 + 屏幕信息
            s = self.status()
            result["touch"] = {
                "input_enabled": s.get("inputEnabled", False),
                "screen_off": s.get("screenOffMode", False),
                "scaling": s.get("scaling", 1.0),
            }

            # 👃 嗅觉（通知）：最近通知
            n = self.notifications(10)
            result["smell"] = {
                "notification_count": n.get("total", 0),
                "recent": [
                    {"app": item.get("package", "").split(".")[-1],
                     "title": item.get("title", ""),
                     "time": item.get("time", "")}
                    for item in n.get("notifications", [])[:5]
                ],
            }

            # 👅 味觉（状态）：设备健康
            result["taste"] = {
                "battery": dev.get("batteryLevel", -1),
                "charging": dev.get("isCharging", False),
                "network": dev.get("networkType", "?"),
                "net_ok": dev.get("networkConnected", False),
                "storage_free_gb": round(dev.get("storageAvailableMB", 0) / 1024, 1),
                "model": f"{dev.get('manufacturer', '')} {dev.get('model', '')}".strip(),
                "uptime": dev.get("uptimeFormatted", "?"),
                "wifi_ssid": dev.get("wifiSSID", "?"),
            }

            # 数据质量校验：确保至少有基本数据
            has_fg = bool(result.get("vision", {}).get("foreground_app"))
            has_bat = result.get("taste", {}).get("battery", -1) >= 0
            has_input = "input_enabled" in result.get("touch", {})
            result["_ok"] = has_fg or has_bat or has_input
            result["_connection"] = self._connection_mode
            result["_base"] = self.base
        except Exception as e:
            result["_error"] = str(e)
        return result

    def reconnect(self):
        """强制重新发现并切换到最优连接。返回新的base URL或None"""
        old = self.base
        new_url = discover()
        if new_url:
            self.base = new_url
            if new_url != old:
                log.info(f"重连: {old} → {new_url}")
            return new_url
        return None

    def switch_to(self, host=None, port=None, url=None):
        """手动切换连接目标"""
        if url:
            self.base = url.rstrip("/")
            self._connection_mode = "url"
        elif host:
            p = port or urlparse(self.base).port or 8086
            self.base = f"http://{host}:{p}"
            self._connection_mode = "wifi" if not host.startswith("127.") else "usb"
        log.info(f"切换到: {self.base}")

    def _start_heartbeat(self, interval_sec):
        """启动后台心跳线程，自动检测+恢复"""
        def _beat():
            while not self._heartbeat_stop.is_set():
                try:
                    state, detail = NegativeState.detect(self)
                    if state != NegativeState.HEALTHY:
                        log.warning(f"心跳异常: {state} ({detail})")
                        ok, msg = NegativeState.recover(self, state, detail)
                        log.info(f"心跳恢复: {'✅' if ok else '❌'} {msg}")
                except Exception as e:
                    log.error(f"心跳错误: {e}")
                self._heartbeat_stop.wait(interval_sec)

        self._heartbeat_thread = threading.Thread(target=_beat, daemon=True,
                                                   name="PhoneLib-Heartbeat")
        self._heartbeat_thread.start()
        log.info(f"心跳启动: 每{interval_sec}秒")

    # === 远程增强API（纯HTTP，不依赖ADB） ===

    def media(self, action="play"):
        """媒体控制: play/pause/next/prev/stop"""
        return self.post(f"/media/{action}")

    def findphone(self, ring=True):
        """找手机（最大音量响铃30秒）"""
        return self.post(f"/findphone/{str(ring).lower()}")

    def vibrate(self, ms=500):
        """振动"""
        return self.post("/vibrate", {"duration": ms})

    def flashlight(self, on=True):
        """手电筒"""
        return self.post(f"/flashlight/{str(on).lower()}")

    def dnd(self, on=True):
        """免打扰模式"""
        return self.post(f"/dnd/{str(on).lower()}")

    def autorotate(self, on=True):
        """自动旋转"""
        return self.post(f"/autorotate/{str(on).lower()}")

    def stayawake(self, on=True):
        """保持唤醒"""
        return self.post(f"/stayawake/{str(on).lower()}")

    def killapp(self):
        """关闭前台应用"""
        return self.post("/killapp")

    def command(self, text):
        """自然语言命令"""
        return self.post("/command", {"command": text})

    def viewtree(self, depth=4):
        """View树"""
        return self.get(f"/viewtree?depth={depth}")

    def files(self, path="/sdcard"):
        """文件列表"""
        return self.get(f"/files/list?path={path}")

    def apps(self):
        """已安装APP列表"""
        return self.get("/apps")

    def smarthome_devices(self):
        """智能家居设备列表"""
        return self.get("/smarthome/devices")

    def smarthome_control(self, entity_id, action="toggle"):
        """智能家居设备控制"""
        return self.post("/smarthome/control", {"entity_id": entity_id, "action": action})

    def macro_run(self, macro_id):
        """运行宏"""
        return self.post(f"/macro/run/{macro_id}")

    def macro_inline(self, steps, loop=1):
        """内联执行宏步骤"""
        return self.post("/macro/run-inline", {"actions": steps, "loop": loop})
