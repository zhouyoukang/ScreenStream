"""
VP99 华强北手表统一接入层 (Watch Bridge)

道生一: VNC连接 → 手表控制
一生二: 双主控(用户触控 + Agent API)
二生三: 接入手机/PC/智能家居
三生万物: 全设备五感互联

架构:
  PC Agent ←→ WatchBridge(VNC) ←→ VP99手表
                  ↕                    ↕
  phone_lib ←→ 手机舰队          MacroDroid HTTP
                  ↕
  SmartHome ←→ HA/涂鸦/美的
"""

import socket
import struct
import time
import json
import threading
import os
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


class VP99Watch:
    """VP99手表统一控制接口 — 通过VNC协议实现完整远控"""

    def __init__(self, ip="192.168.31.41", vnc_port=5900):
        self.ip = ip
        self.vnc_port = vnc_port
        self.sock = None
        self.width = 0
        self.height = 0
        self.name = ""
        self.connected = False
        self._lock = threading.Lock()

    # ═══════════════════════════════════════
    # ☰乾 · 连接层
    # ═══════════════════════════════════════

    def connect(self):
        """连接VP99 VNC服务"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        self.sock.connect((self.ip, self.vnc_port))

        banner = self.sock.recv(1024)
        self.sock.send(b'RFB 003.008\n')
        time.sleep(0.3)

        sec = self.sock.recv(1024)
        types = list(sec[1:1+sec[0]])
        if 1 in types:
            self.sock.send(bytes([1]))
        else:
            raise Exception(f"VP99需要密码认证, 可用类型: {types}")

        time.sleep(0.3)
        result = self.sock.recv(1024)
        if result[:4] != b'\x00\x00\x00\x00':
            raise Exception("VNC认证失败")

        self.sock.send(bytes([1]))
        time.sleep(0.3)
        si = self.sock.recv(4096)
        self.width = struct.unpack('>H', si[0:2])[0]
        self.height = struct.unpack('>H', si[2:4])[0]
        name_len = struct.unpack('>I', si[20:24])[0]
        self.name = si[24:24+name_len].decode('utf-8', errors='ignore')
        self.connected = True
        return self

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.connected = False

    def status(self):
        """手表状态"""
        return {
            "connected": self.connected,
            "ip": self.ip,
            "vnc_port": self.vnc_port,
            "screen": f"{self.width}x{self.height}",
            "name": self.name,
            "device": "VP99",
            "android": "8.1",
            "ram": "3GB",
            "cpu": "4-core Unisoc",
            "imei": "860123401266076",
            "serial": "10109530162925",
            "firmware": "K15_V11B_DWQ_VP99_EN_ZX_HSC_4.4V700_20241127",
        }

    # ═══════════════════════════════════════
    # ☲离 · 视觉(截屏)
    # ═══════════════════════════════════════

    def screenshot(self, save_path=None):
        """截取手表屏幕 → PIL Image"""
        with self._lock:
            self.sock.send(struct.pack('>BBH', 2, 0, 1) + struct.pack('>i', 0))
            time.sleep(0.1)
            self.sock.send(struct.pack('>BBHHHH', 3, 0, 0, 0, self.width, self.height))

            header = self._recv(4)
            num_rects = struct.unpack('>H', header[2:4])[0]
            pixels = bytearray(self.width * self.height * 4)

            for _ in range(num_rects):
                rh = self._recv(12)
                rx, ry = struct.unpack('>HH', rh[0:4])
                rw, rh2 = struct.unpack('>HH', rh[4:8])
                enc = struct.unpack('>i', rh[8:12])[0]
                if enc == 0:
                    data = self._recv(rw * rh2 * 4)
                    for row in range(rh2):
                        so = row * rw * 4
                        do = ((ry + row) * self.width + rx) * 4
                        pixels[do:do + rw * 4] = data[so:so + rw * 4]

        try:
            from PIL import Image
            img = Image.frombytes('RGBX', (self.width, self.height), bytes(pixels)).convert('RGB')
            if save_path:
                img.save(save_path)
            return img
        except ImportError:
            if save_path:
                self._save_raw(save_path, pixels)
            return pixels

    # ═══════════════════════════════════════
    # ☳震 · 触觉(点击/滑动)
    # ═══════════════════════════════════════

    def tap(self, x, y):
        """点击屏幕坐标"""
        with self._lock:
            self.sock.send(struct.pack('>BBhh', 5, 1, x, y))
            time.sleep(0.05)
            self.sock.send(struct.pack('>BBhh', 5, 0, x, y))
        time.sleep(0.3)

    def swipe(self, x1, y1, x2, y2, duration=0.3):
        """滑动手势"""
        steps = max(10, int(duration * 50))
        with self._lock:
            for i in range(steps + 1):
                t = i / steps
                x = int(x1 + (x2 - x1) * t)
                y = int(y1 + (y2 - y1) * t)
                self.sock.send(struct.pack('>BBhh', 5, 1, x, y))
                time.sleep(duration / steps)
            self.sock.send(struct.pack('>BBhh', 5, 0, x2, y2))
        time.sleep(0.3)

    def swipe_up(self):
        """向上滑动(滚动列表)"""
        self.swipe(168, 300, 168, 100)

    def swipe_down(self):
        """向下滑动(下拉通知)"""
        self.swipe(168, 100, 168, 300)

    def swipe_left(self):
        """向左滑动"""
        self.swipe(280, 200, 50, 200)

    def swipe_right(self):
        """向右滑动(返回)"""
        self.swipe(50, 200, 280, 200)

    # ═══════════════════════════════════════
    # ☴巽 · 按键
    # ═══════════════════════════════════════

    def key(self, keycode):
        """发送按键"""
        with self._lock:
            self.sock.send(struct.pack('>BBxxI', 4, 1, keycode))
            time.sleep(0.05)
            self.sock.send(struct.pack('>BBxxI', 4, 0, keycode))
        time.sleep(0.3)

    def home(self):
        self.key(0xff50)

    def back(self):
        self.key(0xff1b)  # Escape

    def enter(self):
        self.key(0xff0d)

    def type_text(self, text):
        """输入文字"""
        with self._lock:
            for ch in text:
                code = ord(ch)
                self.sock.send(struct.pack('>BBxxI', 4, 1, code))
                time.sleep(0.02)
                self.sock.send(struct.pack('>BBxxI', 4, 0, code))
                time.sleep(0.02)

    # ═══════════════════════════════════════
    # ☵坎 · 导航(高级操作)
    # ═══════════════════════════════════════

    def open_settings(self):
        """打开设置"""
        self.home()
        time.sleep(1)
        self.tap(310, 385)  # 底栏设置图标
        time.sleep(2)

    def open_app_drawer(self):
        """打开应用抽屉"""
        self.home()
        time.sleep(0.5)
        self.swipe(168, 380, 168, 80, duration=0.4)
        time.sleep(1)

    def navigate_to(self, *menu_items):
        """导航设置菜单路径, 如 navigate_to('系统', '关于手表')"""
        self.open_settings()
        for item_y in menu_items:
            if isinstance(item_y, int):
                self.tap(168, item_y)
                time.sleep(1.5)
            elif isinstance(item_y, str):
                # 需要OCR或预定义坐标, 当前用默认y坐标
                self.tap(168, 200)
                time.sleep(1.5)

    # ═══════════════════════════════════════
    # ☶艮 · 五感采集
    # ═══════════════════════════════════════

    def senses(self):
        """采集手表五感数据(通过VNC截屏+分析)"""
        img = self.screenshot()
        return {
            "vision": f"{self.width}x{self.height} screen captured",
            "touch": "VNC tap/swipe available",
            "hearing": "microphone via camera app (manual)",
            "smell": f"WiFi: {self.ip}, BT: 85:78:11:18:42:22",
            "taste": self.status(),
        }

    # ═══════════════════════════════════════
    # ☱兑 · 设备互联
    # ═══════════════════════════════════════

    def get_integration_config(self):
        """获取与其他设备的集成配置"""
        return {
            "watch": {
                "ip": self.ip,
                "vnc": f"{self.ip}:{self.vnc_port}",
                "control": "VNC + MacroDroid HTTP",
                "capabilities": [
                    "screen_capture", "tap", "swipe", "key_input",
                    "text_input", "navigation", "app_launch",
                    "heart_rate_view", "step_count_view", "gps_view",
                    "camera_capture", "phone_call", "sms",
                ],
            },
            "phone_bridge": {
                "module": "tools/phone-fleet/phone_lib.py",
                "devices": ["OnePlus NE2210:8084", "OPPO PEAM00:8084"],
                "relay": "watch BLE ↔ phone ↔ PC",
            },
            "smart_home": {
                "module": "100-智能家居_SmartHome/",
                "gateway": "port 8900",
                "devices": "HA/涂鸦/美的/eWeLink",
                "watch_role": "遥控器 + 传感器源(心率/位置)",
            },
            "ar_glasses": {
                "module": "雷鸟v3开发/",
                "device": "RayNeo XRGF50",
                "relay": "watch ↔ phone ↔ glasses 三联道",
            },
            "desktop_cast": {
                "module": "电脑公网投屏手机/",
                "role": "手表作为PC投屏的迷你查看器",
            },
        }

    # ═══════════════════════════════════════
    # 内部方法
    # ═══════════════════════════════════════

    def _recv(self, n):
        data = bytearray()
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("VNC连接断开")
            data.extend(chunk)
        return bytes(data)

    def _save_raw(self, path, pixels):
        with open(path, 'wb') as f:
            f.write(bytes(pixels))

    def __enter__(self):
        return self.connect()

    def __exit__(self, *args):
        self.disconnect()

    def __repr__(self):
        state = "connected" if self.connected else "disconnected"
        return f"VP99Watch({self.ip}:{self.vnc_port}, {state}, {self.width}x{self.height})"


# ═══════════════════════════════════════════════
# 双主控接口: 用户(交互式) + Agent(自动化)
# ═══════════════════════════════════════════════

def demo():
    """演示: VP99手表接入全设备生态"""
    print("=" * 50)
    print("VP99 Watch Bridge — 道生万物")
    print("=" * 50)

    with VP99Watch() as watch:
        print(f"\n☰乾·连接: {watch}")
        print(f"  设备: {watch.name}")
        print(f"  屏幕: {watch.width}x{watch.height}")

        # 截屏
        ss_dir = DATA_DIR / "vp99_extracted" / "vnc_screenshots"
        ss_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        img = watch.screenshot(str(ss_dir / f"bridge_{ts}.png"))
        print(f"\n☲离·视觉: 截屏完成")

        # 五感
        senses = watch.senses()
        print(f"\n☶艮·五感:")
        for k, v in senses.items():
            print(f"  {k}: {v}")

        # 设备互联配置
        config = watch.get_integration_config()
        print(f"\n☱兑·互联:")
        for name, info in config.items():
            print(f"  {name}: {info.get('relay', info.get('control', info.get('role', '')))}")

        # 保存状态
        state_file = DATA_DIR / "watch_bridge_state.json"
        state = {
            "timestamp": datetime.now().isoformat(),
            "status": watch.status(),
            "senses": {k: str(v) for k, v in senses.items()},
            "integration": config,
        }
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print(f"\n状态已保存: {state_file}")


if __name__ == '__main__':
    demo()
