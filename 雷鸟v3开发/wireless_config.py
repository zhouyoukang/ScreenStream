#!/usr/bin/env python3
"""
无线配置中枢 — 所有设备IP/端口/连接的唯一真相源

老子第二十五章: 人法地，地法天，天法道，道法自然
  自然 = 自动发现设备，无需手动配置
  道   = 配置集中管理，一处改全局生效
  天   = 连接健康监测，自动恢复
  地   = 可靠的降级策略，WiFi→USB→提示

所有文件 import wireless_config 获取设备地址，禁止硬编码IP。
"""

import subprocess
import os
import re
import json
import time
import threading
import urllib.request
from pathlib import Path

# ─── 常量（不变的设备标识） ────────────────────────────────
GLASS_USB_SERIAL = "841571AC688C360"     # XRGF50 USB序列号（物理不变）
GLASS_WIFI_PORT  = 5555                   # persist.adb.tcp.port（已固化）
PHONE_USB_SERIAL = "158377ff"             # NE2210 USB序列号
PHONE_BRAIN_PORT = 8765                   # phone_server.py 端口

# ─── 默认IP（DHCP可能变化，仅作fallback） ──────────────────
_DEFAULT_GLASS_IP = "192.168.31.116"
_DEFAULT_PHONE_IP = "192.168.31.40"

# ─── 配置文件（持久化发现结果） ─────────────────────────────
_CONFIG_DIR = Path(__file__).resolve().parent
_CONFIG_FILE = _CONFIG_DIR / ".wireless_config.json"

# ─── ADB路径发现 ──────────────────────────────────────────
def find_adb() -> str:
    """查找ADB可执行文件"""
    import shutil
    found = shutil.which("adb")
    if found:
        return found
    candidates = [
        r"D:\platform-tools\adb.exe",
        r"D:\scrcpy\scrcpy-win64-v3.1\adb.exe",
        r"C:\platform-tools\adb.exe",
        # Termux
        "/data/data/com.termux/files/usr/bin/adb",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return "adb"

ADB = find_adb()

# ─── 底层工具 ─────────────────────────────────────────────
def _run_adb(*args, timeout=5) -> str:
    """执行ADB命令，返回stdout，失败返回空字符串"""
    try:
        r = subprocess.run(
            [ADB] + list(args),
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip()
    except Exception:
        return ""

def _adb_device_state(addr: str) -> bool:
    """检查ADB设备是否在线"""
    out = _run_adb("-s", addr, "get-state", timeout=3)
    return "device" in out

def _adb_connect(addr: str) -> bool:
    """尝试ADB connect"""
    out = _run_adb("connect", addr, timeout=5)
    return "connected" in out or "already" in out

# ─── 设备发现 ─────────────────────────────────────────────
def _scan_adb_devices() -> dict:
    """扫描所有ADB设备，返回 {serial: type} 映射"""
    out = _run_adb("devices", "-l")
    devices = {}
    for line in out.splitlines():
        if "\tdevice" in line or " device " in line:
            parts = line.split()
            addr = parts[0]
            model = ""
            for p in parts:
                if p.startswith("model:"):
                    model = p.split(":")[1]
            devices[addr] = model
    return devices

def _find_phone_ip_from_adb() -> str:
    """通过ADB获取手机WiFi IP"""
    out = _run_adb("-s", PHONE_USB_SERIAL, "shell",
                   "ip addr show wlan0 2>/dev/null | grep 'inet '", timeout=3)
    if "inet" in out:
        m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', out)
        if m:
            return m.group(1)
    return ""

def _find_glass_ip_from_adb() -> str:
    """通过USB ADB获取眼镜WiFi IP"""
    out = _run_adb("-s", GLASS_USB_SERIAL, "shell",
                   "ip addr show wlan0 2>/dev/null | grep 'inet '", timeout=3)
    if "inet" in out:
        m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', out)
        if m:
            return m.group(1)
    return ""

def _check_http(ip: str, port: int, path: str = "/status", timeout: int = 3) -> bool:
    """检查HTTP端点是否可达"""
    try:
        url = f"http://{ip}:{port}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False

def _tcp_probe(ip: str, port: int, timeout: float = 0.3) -> bool:
    """快速TCP端口探测"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        return True
    except Exception:
        return False
    finally:
        s.close()

def _scan_subnet_for_glass(subnet: str = "192.168.31", port: int = GLASS_WIFI_PORT,
                           known_non_glass: set = None) -> str:
    """
    扫描子网寻找眼镜。返回眼镜IP或空串。
    通过TCP探测port后ADB connect验证model=XRGF50。
    """
    import socket
    if known_non_glass is None:
        known_non_glass = set()
    
    # 快速并行TCP扫描
    open_ips = []
    for i in range(2, 255):
        ip = f"{subnet}.{i}"
        if ip in known_non_glass:
            continue
        if _tcp_probe(ip, port, timeout=0.3):
            open_ips.append(ip)
    
    # 逐个验证ADB model
    for ip in open_ips:
        addr = f"{ip}:{port}"
        if _adb_connect(addr):
            model = _run_adb("-s", addr, "shell", "getprop", "ro.product.model", timeout=3)
            if "XRGF50" in model:
                return ip
            else:
                # 非眼镜设备，断开
                _run_adb("disconnect", addr)
    return ""

def _enable_wifi_via_usb(serial: str = GLASS_USB_SERIAL) -> bool:
    """
    通过USB ADB开启眼镜WiFi（解决重启后WiFi关闭问题）。
    返回获取到的WiFi IP或空串。
    """
    # 检查WiFi状态
    out = _run_adb("-s", serial, "shell", "dumpsys wifi | grep 'Wi-Fi is'", timeout=5)
    if "disabled" in out:
        _run_adb("-s", serial, "shell", "svc wifi enable", timeout=3)
        # 等待WiFi连接
        for _ in range(10):
            time.sleep(1)
            ip_out = _run_adb("-s", serial, "shell",
                              "ip addr show wlan0 2>/dev/null | grep 'inet '", timeout=3)
            if "inet" in ip_out:
                m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', ip_out)
                if m:
                    return m.group(1)
        return ""
    # WiFi已开启，返回当前IP（而非空串）
    ip_out = _run_adb("-s", serial, "shell",
                      "ip addr show wlan0 2>/dev/null | grep 'inet '", timeout=3)
    if "inet" in ip_out:
        m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', ip_out)
        if m:
            return m.group(1)
    return ""

# ─── 配置持久化 ────────────────────────────────────────────
def _load_config() -> dict:
    """加载上次发现的配置"""
    try:
        if _CONFIG_FILE.exists():
            with open(_CONFIG_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_config(cfg: dict):
    """保存发现的配置"""
    try:
        cfg["_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(_CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# ─── 核心：设备连接管理器 ──────────────────────────────────
class WirelessManager:
    """
    统一管理所有无线设备连接。
    
    用法:
        from wireless_config import wm
        glass_addr = wm.glass_addr   # WiFi或USB地址
        phone_ip   = wm.phone_ip     # 手机IP
        brain_url  = wm.brain_url    # http://手机IP:8765
    """
    
    def __init__(self):
        self._glass_ip = None     # WiFi IP (无端口)
        self._glass_conn = None   # "wifi" 或 "usb" 或 None
        self._phone_ip = None
        self._phone_conn = None   # "usb" 或 "wifi" 或 None
        self._lock = threading.Lock()
        self._last_check = 0
        self._health_thread = None
        self._running = False
        
        # 从缓存加载
        cfg = _load_config()
        self._glass_ip = cfg.get("glass_ip", _DEFAULT_GLASS_IP)
        self._phone_ip = cfg.get("phone_ip", _DEFAULT_PHONE_IP)
        self._glass_conn = cfg.get("glass_conn")
        self._phone_conn = cfg.get("phone_conn")
        # 始终有默认地址，避免property触发阻塞detect()
        self._glass_addr = f"{self._glass_ip}:{GLASS_WIFI_PORT}"
        
    def detect(self, verbose: bool = False) -> dict:
        """
        完整设备发现流程。返回状态字典。
        
        发现顺序:
          眼镜: WiFi ADB → USB ADB → 缓存IP
          手机: USB ADB查IP → HTTP探测 → 缓存IP
        """
        with self._lock:
            result = {"glasses": {}, "phone": {}, "pc": {}}
            
            # 重置连接状态（防止缓存误报）
            self._glass_conn = None
            self._phone_conn = None
            
            # ── 眼镜发现 ──
            glass_wifi = f"{self._glass_ip}:{GLASS_WIFI_PORT}"
            
            # 1. 尝试缓存的WiFi地址
            if _adb_device_state(glass_wifi):
                self._glass_addr = glass_wifi
                self._glass_conn = "wifi"
                if verbose:
                    print(f"  🕶️ 眼镜WiFi: {glass_wifi} ✅")
            # 2. 尝试WiFi connect
            elif _adb_connect(glass_wifi):
                self._glass_addr = glass_wifi
                self._glass_conn = "wifi"
                if verbose:
                    print(f"  🕶️ 眼镜WiFi重连: {glass_wifi} ✅")
            # 3. 尝试USB
            elif _adb_device_state(GLASS_USB_SERIAL):
                self._glass_addr = GLASS_USB_SERIAL
                self._glass_conn = "usb"
                # 顺便获取WiFi IP（下次可能WiFi连接）
                ip = _find_glass_ip_from_adb()
                if not ip:
                    # WiFi可能关闭，尝试自动开启
                    ip = _enable_wifi_via_usb()
                    if ip and verbose:
                        print(f"  🕶️ WiFi已自动开启!")
                if ip:
                    self._glass_ip = ip
                    # USB在线时顺便建立WiFi连接（双通道）
                    wifi_addr = f"{ip}:{GLASS_WIFI_PORT}"
                    _run_adb("-s", GLASS_USB_SERIAL, "tcpip", "5555", timeout=5)
                    time.sleep(1)
                    _adb_connect(wifi_addr)
                if verbose:
                    print(f"  🕶️ 眼镜USB: {GLASS_USB_SERIAL} ✅ (WiFi IP: {ip or '未知'})")
            # 4. 尝试默认IP
            elif self._glass_ip != _DEFAULT_GLASS_IP:
                default_wifi = f"{_DEFAULT_GLASS_IP}:{GLASS_WIFI_PORT}"
                if _adb_connect(default_wifi):
                    self._glass_addr = default_wifi
                    self._glass_ip = _DEFAULT_GLASS_IP
                    self._glass_conn = "wifi"
                    if verbose:
                        print(f"  🕶️ 眼镜WiFi(默认IP): {default_wifi} ✅")
            # 5. 子网扫描（最后手段，DHCP IP变化时）
            else:
                if verbose:
                    print(f"  🕶️ 子网扫描中...")
                found_ip = _scan_subnet_for_glass()
                if found_ip:
                    self._glass_ip = found_ip
                    self._glass_addr = f"{found_ip}:{GLASS_WIFI_PORT}"
                    self._glass_conn = "wifi"
                    if verbose:
                        print(f"  🕶️ 眼镜WiFi(扫描发现): {found_ip}:{GLASS_WIFI_PORT} ✅")
            
            if self._glass_conn is None:
                if verbose:
                    print(f"  🕶️ 眼镜: ❌ 离线")
            
            result["glasses"] = {
                "addr": self._glass_addr,
                "ip": self._glass_ip,
                "connection": self._glass_conn,
                "online": self._glass_conn is not None,
            }
            
            # ── 手机发现 ──
            # 1. 通过USB ADB获取手机IP
            usb_ip = _find_phone_ip_from_adb()
            if usb_ip:
                self._phone_ip = usb_ip
                self._phone_conn = "usb"
                if verbose:
                    print(f"  📱 手机USB: {PHONE_USB_SERIAL} → IP: {usb_ip}")
            
            # 2. HTTP探测手机脑
            phone_brain_ok = _check_http(self._phone_ip, PHONE_BRAIN_PORT)
            if phone_brain_ok:
                self._phone_conn = self._phone_conn or "wifi"
                if verbose:
                    print(f"  📱 手机脑: http://{self._phone_ip}:{PHONE_BRAIN_PORT} ✅")
            elif verbose:
                print(f"  📱 手机脑: http://{self._phone_ip}:{PHONE_BRAIN_PORT} ❌")
            
            result["phone"] = {
                "ip": self._phone_ip,
                "connection": self._phone_conn,
                "brain_online": phone_brain_ok,
                "brain_url": self.brain_url,
            }
            
            result["pc"] = {"role": "bridge" if self._glass_conn else "offline"}
            
            # 保存发现结果
            _save_config({
                "glass_ip": self._glass_ip,
                "phone_ip": self._phone_ip,
                "glass_conn": self._glass_conn,
                "phone_conn": self._phone_conn,
            })
            
            self._last_check = time.time()
            return result
    
    @property
    def glass_addr(self) -> str:
        """眼镜ADB地址（WiFi或USB），始终返回缓存值不阻塞"""
        return self._glass_addr
    
    @property
    def glass_ip(self) -> str:
        """眼镜WiFi IP（不含端口）"""
        return self._glass_ip or _DEFAULT_GLASS_IP
    
    @property
    def glass_wifi_addr(self) -> str:
        """眼镜WiFi ADB完整地址"""
        return f"{self.glass_ip}:{GLASS_WIFI_PORT}"
    
    @property
    def glass_connection(self) -> str:
        """当前眼镜连接方式: 'wifi' / 'usb' / None"""
        return self._glass_conn
    
    @property
    def phone_ip(self) -> str:
        """手机WiFi IP"""
        return self._phone_ip or _DEFAULT_PHONE_IP
    
    @property
    def brain_url(self) -> str:
        """手机脑HTTP地址"""
        return f"http://{self.phone_ip}:{PHONE_BRAIN_PORT}"
    
    @property
    def is_glass_online(self) -> bool:
        return self._glass_conn is not None
    
    @property
    def is_phone_brain_online(self) -> bool:
        return _check_http(self.phone_ip, PHONE_BRAIN_PORT)
    
    def reconnect_glasses(self) -> bool:
        """主动重连眼镜WiFi ADB（含子网扫描回退）"""
        addr = self.glass_wifi_addr
        if _adb_connect(addr) and _adb_device_state(addr):
            self._glass_addr = addr
            self._glass_conn = "wifi"
            return True
        # 回退USB
        if _adb_device_state(GLASS_USB_SERIAL):
            self._glass_addr = GLASS_USB_SERIAL
            self._glass_conn = "usb"
            # USB在线时尝试恢复WiFi
            ip = _find_glass_ip_from_adb()
            if not ip:
                ip = _enable_wifi_via_usb()
            if ip:
                self._glass_ip = ip
                wifi_addr = f"{ip}:{GLASS_WIFI_PORT}"
                _run_adb("-s", GLASS_USB_SERIAL, "tcpip", "5555", timeout=5)
                time.sleep(1)
                _adb_connect(wifi_addr)
            return True
        # 子网扫描（DHCP IP变化时的最后手段）
        found_ip = _scan_subnet_for_glass()
        if found_ip:
            self._glass_ip = found_ip
            self._glass_addr = f"{found_ip}:{GLASS_WIFI_PORT}"
            self._glass_conn = "wifi"
            _save_config({"glass_ip": found_ip, "phone_ip": self._phone_ip,
                          "glass_conn": "wifi", "phone_conn": self._phone_conn})
            return True
        self._glass_conn = None
        return False
    
    def keepalive(self) -> bool:
        """WiFi ADB keepalive — 发送轻量命令保持连接活跃"""
        if self._glass_conn == "wifi":
            out = _run_adb("-s", self._glass_addr, "shell", "echo", "ok", timeout=3)
            return "ok" in out
        elif self._glass_conn == "usb":
            out = _run_adb("-s", GLASS_USB_SERIAL, "shell", "echo", "ok", timeout=3)
            return "ok" in out
        return False

    def check_ip_change(self) -> str:
        """检测眼镜WiFi IP是否变化（DHCP续租），返回新IP或空串"""
        if self._glass_conn == "usb":
            new_ip = _find_glass_ip_from_adb()
            if new_ip and new_ip != self._glass_ip:
                old_ip = self._glass_ip
                self._glass_ip = new_ip
                self._glass_addr = f"{new_ip}:{GLASS_WIFI_PORT}"
                _save_config({"glass_ip": new_ip, "phone_ip": self._phone_ip,
                              "glass_conn": self._glass_conn, "phone_conn": self._phone_conn})
                return new_ip
        elif self._glass_conn == "wifi":
            # WiFi模式下通过shell获取IP验证
            out = _run_adb("-s", self._glass_addr, "shell",
                           "ip addr show wlan0 2>/dev/null | grep 'inet '", timeout=3)
            if "inet" in out:
                m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', out)
                if m:
                    new_ip = m.group(1)
                    if new_ip != self._glass_ip:
                        self._glass_ip = new_ip
                        new_addr = f"{new_ip}:{GLASS_WIFI_PORT}"
                        # 连接新地址
                        if _adb_connect(new_addr):
                            self._glass_addr = new_addr
                            _save_config({"glass_ip": new_ip, "phone_ip": self._phone_ip,
                                          "glass_conn": "wifi", "phone_conn": self._phone_conn})
                            return new_ip
        return ""

    def start_health_monitor(self, interval: int = 30, callback=None):
        """
        启动后台健康监测线程。
        interval: 检测间隔（秒）
        callback: 状态变化时回调 fn(event, detail)
        
        事件类型:
          glass_disconnected  — WiFi/USB断开且重连失败
          glass_reconnected   — 从离线恢复连接
          glass_ip_changed    — DHCP IP变化
          glass_keepalive     — keepalive成功（每次）
          phone_brain_down    — 手机脑HTTP不可达
          phone_brain_up      — 手机脑恢复
        """
        if self._health_thread and self._health_thread.is_alive():
            return
        self._running = True
        self._reconnect_fails = 0
        
        def _monitor():
            prev_glass = self._glass_conn
            prev_phone = self._phone_conn
            keepalive_count = 0
            while self._running:
                time.sleep(interval)
                if not self._running:
                    break
                
                # ── 眼镜健康检测 ──
                if self._glass_conn in ("wifi", "usb"):
                    if self.keepalive():
                        self._reconnect_fails = 0
                        keepalive_count += 1
                        # 每5次keepalive检测IP变化
                        if keepalive_count % 5 == 0:
                            new_ip = self.check_ip_change()
                            if new_ip and callback:
                                callback("glass_ip_changed", new_ip)
                    else:
                        # keepalive失败 → 尝试重连
                        if self.reconnect_glasses():
                            self._reconnect_fails = 0
                            if callback and prev_glass is None:
                                callback("glass_reconnected", self._glass_addr)
                        else:
                            self._reconnect_fails += 1
                            self._glass_conn = None
                            if callback:
                                callback("glass_disconnected",
                                         f"{self._glass_addr} (fails={self._reconnect_fails})")
                else:
                    # 离线 → 尝试重连（指数退避：前3次每轮，之后每3轮）
                    if self._reconnect_fails < 3 or keepalive_count % 3 == 0:
                        if self.reconnect_glasses():
                            self._reconnect_fails = 0
                            if callback:
                                callback("glass_reconnected", self._glass_addr)
                        else:
                            self._reconnect_fails += 1
                
                keepalive_count += 1
                
                # ── 手机脑健康检测 ──
                brain_ok = _check_http(self.phone_ip, PHONE_BRAIN_PORT)
                if not brain_ok and prev_phone:
                    if callback:
                        callback("phone_brain_down", self.phone_ip)
                elif brain_ok and not prev_phone:
                    if callback:
                        callback("phone_brain_up", self.phone_ip)
                
                prev_glass = self._glass_conn
                prev_phone = "online" if brain_ok else None
        
        self._health_thread = threading.Thread(target=_monitor, daemon=True)
        self._health_thread.start()
    
    def stop_health_monitor(self):
        self._running = False

    def status_report(self) -> str:
        """生成人类可读的连接状态报告"""
        info = self.detect(verbose=False)
        g = info["glasses"]
        p = info["phone"]
        lines = [
            "╔══════════════════════════════════════╗",
            "║  无线连接状态                          ║",
            "╚══════════════════════════════════════╝",
            "",
            f"  🕶️ 眼镜: {'✅ ' + (g['connection'] or '').upper() if g['online'] else '❌ 离线'}",
            f"     地址: {g['addr']}",
            f"     WiFi IP: {g['ip']}",
            "",
            f"  📱 手机: IP {p['ip']}",
            f"     手机脑: {'✅ 在线' if p['brain_online'] else '❌ 离线'}",
            f"     地址: {p['brain_url']}",
            "",
            f"  💻 PC: {info['pc']['role']}",
        ]
        return "\n".join(lines)


# ─── 全局单例 ─────────────────────────────────────────────
wm = WirelessManager()

# ─── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RayNeo V3 无线配置中枢")
    parser.add_argument("--detect", action="store_true", help="设备发现")
    parser.add_argument("--status", action="store_true", help="连接状态报告")
    parser.add_argument("--reconnect", action="store_true", help="重连眼镜")
    parser.add_argument("--monitor", action="store_true", help="启动健康监测")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    if args.detect or args.status:
        info = wm.detect(verbose=not args.json)
        if args.json:
            print(json.dumps(info, indent=2, ensure_ascii=False))
        elif args.status:
            print(wm.status_report())
    elif args.reconnect:
        ok = wm.reconnect_glasses()
        print(f"重连: {'✅ 成功' if ok else '❌ 失败'} → {wm.glass_addr}")
    elif args.monitor:
        def _on_event(event, detail):
            print(f"  [{time.strftime('%H:%M:%S')}] {event}: {detail}")
        print("启动健康监测 (Ctrl+C 退出)...")
        wm.detect(verbose=True)
        wm.start_health_monitor(interval=15, callback=_on_event)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            wm.stop_health_monitor()
            print("\n[监测已停止]")
    else:
        info = wm.detect(verbose=True)
        print()
        print(wm.status_report())
