#!/usr/bin/env python3
"""
Phase 2: 手机脑直连眼镜 — 撤除PC桥梁

老子第十一章: 当其无，有车之用
  PC = 梯（用后即撤）。此脚本在手机Termux运行，
  手机通过WiFi ADB直接连接眼镜，替代PC做ADB relay。

前置条件:
  1. 手机安装Termux + python + adb
     pkg install android-tools python
  2. 眼镜已连家庭WiFi (persist.adb.tcp.port=5555)
  3. phone_server.py 正在运行 (端口8765)

用法 (Termux):
  python phone_relay.py               # 自动发现+启动
  python phone_relay.py --glass-ip 192.168.31.116  # 指定IP
  python phone_relay.py --status       # 状态报告

Phase 1 (PC):   眼镜 ──USB ADB──→ PC ──HTTP──→ 手机脑
Phase 2 (此):   眼镜 ──WiFi ADB──→ 手机 (本机phone_server.py)
                 无需PC，无需USB线
"""

import subprocess
import os
import sys
import re
import time
import json
import threading
import signal
from pathlib import Path

# ─── 配置 ─────────────────────────────────────────────────
GLASS_WIFI_PORT  = 5555
GLASS_USB_SERIAL = "841571AC688C360"
DEFAULT_GLASS_IP = "192.168.31.116"
PHONE_BRAIN_PORT = 8765
PHONE_BRAIN_HOST = "127.0.0.1"  # phone_server在本机

# ─── ADB工具 ──────────────────────────────────────────────
def _find_adb() -> str:
    """查找ADB (Termux优先)"""
    import shutil
    found = shutil.which("adb")
    if found:
        return found
    termux_adb = "/data/data/com.termux/files/usr/bin/adb"
    if os.path.isfile(termux_adb):
        return termux_adb
    return "adb"

ADB = _find_adb()

def adb(*args, timeout=5) -> str:
    try:
        r = subprocess.run(
            [ADB] + list(args),
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        return f"ERROR: {e}"

def adb_glass(*args, glass_addr: str = "", timeout=5) -> str:
    return adb("-s", glass_addr, *args, timeout=timeout)

def shell(cmd: str):
    """本机shell命令"""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except Exception:
        return ""

# ─── 眼镜发现 ─────────────────────────────────────────────
def discover_glasses(hint_ip: str = "") -> str:
    """
    发现眼镜WiFi ADB地址。
    返回 "IP:5555" 或 空字符串。
    """
    candidates = []
    if hint_ip:
        candidates.append(hint_ip)
    candidates.append(DEFAULT_GLASS_IP)
    
    # 1. 扫描已连接的ADB设备
    out = adb("devices", "-l")
    for line in out.splitlines():
        if "XRGF50" in line or "Mars" in line or GLASS_USB_SERIAL in line:
            addr = line.split()[0]
            if ":" in addr:  # WiFi地址
                return addr
    
    # 2. 尝试候选IP
    for ip in candidates:
        addr = f"{ip}:{GLASS_WIFI_PORT}"
        out = adb("connect", addr, timeout=5)
        if "connected" in out or "already" in out:
            # 验证确实是眼镜
            model = adb("-s", addr, "shell", "getprop ro.product.model", timeout=3)
            if "XRGF50" in model or model == "":
                return addr
    
    # 3. 网络扫描 (慢，最后手段)
    my_ip = _get_my_ip()
    if my_ip:
        subnet = ".".join(my_ip.split(".")[:3])
        print(f"  扫描子网 {subnet}.0/24 的 ADB 端口...")
        for last_octet in range(1, 255):
            ip = f"{subnet}.{last_octet}"
            if ip == my_ip:
                continue
            # 快速TCP探测
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.2)
            try:
                if sock.connect_ex((ip, GLASS_WIFI_PORT)) == 0:
                    addr = f"{ip}:{GLASS_WIFI_PORT}"
                    out = adb("connect", addr, timeout=3)
                    if "connected" in out or "already" in out:
                        print(f"  发现设备: {addr}")
                        return addr
            except Exception:
                pass
            finally:
                sock.close()
    
    return ""

def _get_my_ip() -> str:
    """获取手机WiFi IP"""
    out = shell("ip addr show wlan0 2>/dev/null | grep 'inet '")
    m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', out)
    return m.group(1) if m else ""

# ─── 手机脑通信 ───────────────────────────────────────────
def brain_request(endpoint: str, data: dict = None, timeout: int = 10) -> dict:
    """向本机phone_server发请求"""
    import urllib.request
    url = f"http://{PHONE_BRAIN_HOST}:{PHONE_BRAIN_PORT}{endpoint}"
    try:
        if data:
            body = json.dumps(data).encode()
            req = urllib.request.Request(url, data=body,
                                        headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

def brain_online() -> bool:
    r = brain_request("/status", timeout=3)
    return "error" not in r

# ─── TTS (通过ADB直推眼镜) ────────────────────────────────
def glasses_tts(text: str, glass_addr: str):
    """直接ADB推送TTS到眼镜扬声器"""
    # 方式1: am broadcast (最快)
    safe_text = re.sub(r"""["'$`\\;|&<>(){}\[\]!#~]""", '', text)[:200]
    adb_glass("shell",
              f'am broadcast -a com.rayneo.tts.SPEAK --es text "{safe_text}"',
              glass_addr=glass_addr, timeout=5)

# ─── 事件监听 (眼镜触控+按钮) ─────────────────────────────
class GlassesListener:
    """
    监听眼镜TP触控和按钮事件，路由到本机phone_server。
    与shou_ji_nao.py的GlassesListener功能相同，但运行在手机上。
    """
    
    def __init__(self, glass_addr: str):
        self.glass_addr = glass_addr
        self._running = False
        self._tp_thread = None
        self._btn_thread = None
        # 手势识别状态
        self._tp_start_x = None
        self._tp_last_x = None
        self._tp_start_t = None
        self._tap_count = 0
        self._tap_timer = None
    
    def start(self):
        self._running = True
        self._tp_thread = threading.Thread(target=self._listen_tp, daemon=True)
        self._btn_thread = threading.Thread(target=self._listen_btn, daemon=True)
        self._tp_thread.start()
        self._btn_thread.start()
    
    def stop(self):
        self._running = False
    
    def _listen_tp(self):
        """监听触控板 getevent"""
        while self._running:
            try:
                proc = subprocess.Popen(
                    [ADB, "-s", self.glass_addr, "shell",
                     "getevent -lt /dev/input/event3"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                for line in proc.stdout:
                    if not self._running:
                        break
                    self._parse_tp_event(line.strip())
                proc.terminate()
            except Exception as e:
                if self._running:
                    print(f"  [TP] 重连: {e}")
                    time.sleep(2)
    
    def _listen_btn(self):
        """监听ActionButton"""
        while self._running:
            try:
                proc = subprocess.Popen(
                    [ADB, "-s", self.glass_addr, "shell",
                     "getevent -lt /dev/input/event1"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                for line in proc.stdout:
                    if not self._running:
                        break
                    if "KEY_POWER" in line or "KEY_CAMERA" in line:
                        if "DOWN" in line or "0001 " in line:
                            self._on_button("action_down")
                        elif "UP" in line:
                            self._on_button("action_up")
                proc.terminate()
            except Exception as e:
                if self._running:
                    print(f"  [BTN] 重连: {e}")
                    time.sleep(2)
    
    def _parse_tp_event(self, line: str):
        """解析触控板原始事件 → 手势"""
        if "ABS_MT_POSITION_X" in line:
            m = re.search(r'([0-9a-f]+)\s*$', line)
            if m:
                x = int(m.group(1), 16)
                if self._tp_start_x is None:
                    self._tp_start_x = x
                    self._tp_start_t = time.time()
                self._tp_last_x = x
        elif "BTN_TOUCH" in line and ("UP" in line or "00000000" in line):
            if self._tp_start_x is not None:
                self._process_touch_end()
    
    def _process_touch_end(self):
        """触摸结束 → 判定手势"""
        if self._tp_start_x is None:
            return
        dt = time.time() - (self._tp_start_t or time.time())
        dx = (self._tp_last_x or self._tp_start_x) - self._tp_start_x
        
        self._tp_start_x = None
        self._tp_start_t = None
        self._tp_last_x = None
        
        if abs(dx) > 300:
            self._dispatch_gesture("slide_fwd" if dx > 0 else "slide_back")
        elif dt > 1.0:
            self._dispatch_gesture("long_press")
        else:
            self._tap_count += 1
            if self._tap_timer:
                self._tap_timer.cancel()
            self._tap_timer = threading.Timer(0.35, self._flush_taps)
            self._tap_timer.start()
    
    def _flush_taps(self):
        count = self._tap_count
        self._tap_count = 0
        if count == 1:
            self._dispatch_gesture("tap")
        elif count == 2:
            self._dispatch_gesture("double_tap")
        elif count >= 3:
            self._dispatch_gesture("triple_tap")
    
    def _dispatch_gesture(self, gesture: str):
        """手势 → 路由到phone_server"""
        print(f"  [手势] {gesture}")
        r = brain_request("/glasses", {"event": gesture, "data": {}})
        if "error" in r:
            print(f"  [路由错误] {r['error']}")
        else:
            # 执行返回的TTS
            tts = r.get("tts") or r.get("speak") or r.get("answer")
            if tts:
                glasses_tts(tts, self.glass_addr)
    
    def _on_button(self, state: str):
        if state == "action_up":
            print(f"  [按钮] ActionButton")
            r = brain_request("/glasses", {"event": "status", "data": {}})
            if r.get("tts"):
                glasses_tts(r["tts"], self.glass_addr)

# ─── 主程序 ───────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Phase 2: 手机直连眼镜 (脱PC)")
    parser.add_argument("--glass-ip", type=str, default="",
                        help="眼镜WiFi IP (自动发现)")
    parser.add_argument("--status", action="store_true",
                        help="状态报告")
    parser.add_argument("--no-listen", action="store_true",
                        help="只连接不监听")
    args = parser.parse_args()
    
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║  Phase 2 · 手机直连眼镜 · 脱PC                      ║")
    print("║  道生一，一生二 → 手机=脑  眼镜=器  PC=撤            ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()
    
    # 检查手机脑
    print("[1/3] 检查手机脑 (phone_server.py)...")
    if brain_online():
        print(f"  ✅ 手机脑在线: http://{PHONE_BRAIN_HOST}:{PHONE_BRAIN_PORT}")
    else:
        print(f"  ❌ 手机脑离线! 请先启动:")
        print(f"     python ~/phone_server.py")
        sys.exit(1)
    
    # 发现眼镜
    print("\n[2/3] 发现眼镜WiFi ADB...")
    glass_addr = discover_glasses(args.glass_ip)
    if not glass_addr:
        print("  ❌ 未找到眼镜!")
        print("  确认: 1.眼镜已连WiFi  2.adb tcpip 5555已启用")
        sys.exit(1)
    
    # 验证连接
    model = adb_glass("shell", "getprop ro.product.model",
                       glass_addr=glass_addr, timeout=3)
    battery = adb_glass("shell", "dumpsys battery | grep level",
                         glass_addr=glass_addr, timeout=3)
    bat_pct = ""
    m = re.search(r'level:\s*(\d+)', battery)
    if m:
        bat_pct = m.group(1) + "%"
    
    print(f"  ✅ 眼镜已连接: {glass_addr}")
    print(f"     型号: {model or 'XRGF50'}")
    print(f"     电量: {bat_pct or '?'}")
    
    if args.status:
        print("\n[状态报告]")
        print(f"  手机脑: ✅ 127.0.0.1:{PHONE_BRAIN_PORT}")
        print(f"  眼镜:   ✅ {glass_addr} WiFi ADB")
        print(f"  PC:     不需要 ✅ (Phase 2)")
        return
    
    if args.no_listen:
        print("\n[完成] 连接已建立，未启动监听。")
        return
    
    # 启动监听
    print(f"\n[3/3] 启动眼镜事件监听...")
    listener = GlassesListener(glass_addr)
    listener.start()
    print(f"  ✅ 触控板 + ActionButton 监听中")
    print(f"  路由: 眼镜 ──WiFi ADB──→ 手机脑(本机:8765)")
    print(f"\n  [Ctrl+C 停止]")
    
    # 通知用户
    glasses_tts("手机直连模式已启动", glass_addr)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        listener.stop()
        print("\n[Phase 2 已停止]")


if __name__ == "__main__":
    main()
