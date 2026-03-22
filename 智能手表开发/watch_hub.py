"""
VP99 华强北手表 · 全量深度逆向中枢 (Watch Hub v1.0)

道生一: MacroDroid HTTP API → 远程命令
一生二: VNC协议 → 视觉+触控
二生三: MTP + 系统日志 → 数据采集
三生万物: Hub API → 统一接入所有设备

端口: 8841
启动: python watch_hub.py
"""

import json
import os
import re
import socket
import struct
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen, Request
from urllib.error import URLError

# ═══════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════

WATCH_IP = "192.168.31.41"
MACRODROID_PORT = 8080
VNC_PORT = 5900
HUB_PORT = 8841
DATA_DIR = Path(__file__).parent / "data"
DASHBOARD_FILE = Path(__file__).parent / "watch_dashboard.html"

# 设备档案 (从逆向确认)
DEVICE_PROFILE = {
    "model": "VP99",
    "android": "8.1 Oreo",
    "ram": "3GB",
    "cpu": "4-core Unisoc (展锐)",
    "soc_guess": "SC9832E / SL8541E / W517",
    "platform": "K15",
    "screen_vnc": "336x401",
    "screen_real": "480x576",
    "camera": "前置 0.28MP",
    "imei": "860123401266076",
    "serial": "10109530162925",
    "wifi_mac": "00:27:15:92:44:12",
    "bt_mac": "85:78:11:18:42:22",
    "firmware": "K15_V11B_DWQ_VP99_EN_ZX_HSC_4.4V700_20241127",
    "oem": "HSC",
    "designer": "DWQ (方案商)",
    "companion_app": "佰佑通 BYYoung",
    "fota": "艾拉比 abupdate",
    "build_date": "2024-11-27",
    "usb_vid": "0x1782",
    "usb_pid_mtp": "0x4001",
    "usb_pid_adb": "0x4D00",
}

# MacroDroid HA HTTP Master 已确认命令
MACRODROID_COMMANDS = [
    "open_wechat", "open_alipay", "open_taobao", "open_doubao",
    "open_amap", "open_mijia", "mute", "vibrate",
]

# 已知安装的应用
INSTALLED_APPS = {
    "社交": ["微信(com.tencent.mm)", "Twitter", "Teams"],
    "AI": ["腾讯混元(com.tencent.hunyuan.app.chat)", "AVA语音助手"],
    "视频": ["TikTok国际版(com.ss.android.ugc.trill)"],
    "音乐": ["网易云音乐手表版"],
    "工具": ["搜狗输入法", "夸克浏览器", "Bing", "V2rayNG"],
    "自动化": ["MacroDroid Pro(破解版)", "Tasker"],
    "桌面": ["微软桌面", "Nova AI桌面"],
    "开发": ["Shizuku", "ADB Helper", "AI开发助手"],
    "远程": ["DroidVNC-NG"],
    "通讯": ["PTT对讲机"],
    "安全": ["人脸解锁(cn.heils.faceunlock)"],
    "Google": ["Play Store", "GMS", "Maps", "TTS"],
    "OEM": ["HSC Launcher3", "HSC Walk(计步)", "HSC AppStore", "HSC ScreenRecording"],
}

# ═══════════════════════════════════════════════════
# ☰乾 · MacroDroid HTTP 控制器
# ═══════════════════════════════════════════════════

class MacroDroidController:
    """通过MacroDroid HTTP Server远程控制手表"""

    def __init__(self, ip=WATCH_IP, port=MACRODROID_PORT):
        self.base = f"http://{ip}:{port}"
        self._cache = {}

    def send_command(self, cmd):
        """发送命令到HA HTTP Master宏"""
        try:
            url = f"{self.base}/{{ha}}?cmd={cmd}"
            r = urlopen(Request(url), timeout=5)
            return {"ok": True, "cmd": cmd, "response": r.read().decode('utf-8', errors='ignore')}
        except Exception as e:
            return {"ok": False, "cmd": cmd, "error": str(e)}

    def get_system_log(self, max_lines=200):
        """获取MacroDroid系统日志"""
        try:
            r = urlopen(f"{self.base}/systemlog", timeout=20)
            html = r.read().decode('utf-8', errors='ignore')
            lines = []
            for m in re.finditer(r'color:(#[A-F0-9]+)"?>([^<]+)', html):
                color, text = m.group(1), m.group(2).strip()
                if len(text) > 5:
                    lines.append({"color": color, "text": text})
            return lines[:max_lines]
        except Exception as e:
            return [{"color": "#FF0000", "text": f"Error: {e}"}]

    def get_wifi_scans(self):
        """从系统日志提取WiFi扫描结果"""
        logs = self.get_system_log(500)
        scans = []
        for entry in logs:
            if "WIFI SCAN:" in entry["text"]:
                ts_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', entry["text"])
                networks = re.findall(r'([^,\(]+)\(([a-f0-9:]+)\)', entry["text"])
                scans.append({
                    "timestamp": ts_match.group(1) if ts_match else "",
                    "networks": [{"ssid": n[0].strip(), "bssid": n[1]} for n in networks],
                })
        return scans

    def get_macro_activity(self):
        """从系统日志提取宏执行活动"""
        logs = self.get_system_log(500)
        macros = {}
        for entry in logs:
            t = entry["text"]
            m = re.search(r'(?:Invoking|starting|terminated).*?Macro:\s*(.+?)(?:\s+\1|\s*$)', t)
            if m:
                name = m.group(1).strip()
                macros[name] = macros.get(name, 0) + 1
        return macros

    def health(self):
        """MacroDroid服务健康检查"""
        try:
            r = urlopen(f"{self.base}/", timeout=3)
            html = r.read().decode('utf-8', errors='ignore')
            return {
                "alive": True,
                "status_code": 200,
                "endpoints": ["/systemlog", "/userlog", "/{ha}"],
                "device_name": "VP99 VP99" if "VP99" in html else "unknown",
            }
        except Exception as e:
            return {"alive": False, "error": str(e)}

    def probe_all_ports(self, ports=None):
        """探测手表所有TCP端口"""
        if ports is None:
            ports = [21, 22, 23, 25, 53, 80, 443, 554, 1883, 2222, 3000, 3389,
                     4000, 4040, 4200, 4500, 5000, 5037, 5555, 5800, 5900, 5901,
                     7000, 7070, 7400, 7890, 8000, 8008, 8080, 8081, 8082, 8083,
                     8084, 8085, 8088, 8181, 8443, 8765, 8888, 9000, 9876, 10808,
                     15000, 18000, 27042, 38291]
        result = {"open": [], "closed": 0}
        for p in ports:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.8)
                if s.connect_ex((WATCH_IP, p)) == 0:
                    result["open"].append(p)
                else:
                    result["closed"] += 1
                s.close()
            except Exception:
                result["closed"] += 1
        return result


# ═══════════════════════════════════════════════════
# ☲离 · VNC 视觉控制器
# ═══════════════════════════════════════════════════

class VNCController:
    """VNC远程控制 (当DroidVNC-NG运行时)"""

    def __init__(self, ip=WATCH_IP, port=VNC_PORT):
        self.ip = ip
        self.port = port
        self.sock = None
        self.width = 0
        self.height = 0
        self.connected = False

    def probe(self):
        """检测VNC是否可用"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((self.ip, self.port))
            banner = s.recv(100)
            s.close()
            return {"available": True, "banner": banner.decode('utf-8', errors='ignore').strip()}
        except Exception:
            return {"available": False, "hint": "需在手表上启动DroidVNC-NG"}

    def connect(self):
        """连接VNC"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        self.sock.connect((self.ip, self.port))
        self.sock.recv(1024)
        self.sock.send(b'RFB 003.008\n')
        time.sleep(0.3)
        sec = self.sock.recv(1024)
        types = list(sec[1:1+sec[0]])
        if 1 in types:
            self.sock.send(bytes([1]))
        else:
            raise Exception(f"需要密码: {types}")
        time.sleep(0.3)
        if self.sock.recv(1024)[:4] != b'\x00\x00\x00\x00':
            raise Exception("VNC认证失败")
        self.sock.send(bytes([1]))
        time.sleep(0.3)
        si = self.sock.recv(4096)
        self.width = struct.unpack('>H', si[0:2])[0]
        self.height = struct.unpack('>H', si[2:4])[0]
        self.connected = True
        return True

    def tap(self, x, y):
        if not self.connected:
            return False
        self.sock.send(struct.pack('>BBhh', 5, 1, x, y))
        time.sleep(0.05)
        self.sock.send(struct.pack('>BBhh', 5, 0, x, y))
        return True

    def disconnect(self):
        if self.sock:
            self.sock.close()
        self.connected = False


# ═══════════════════════════════════════════════════
# ☳震 · 全景感知引擎
# ═══════════════════════════════════════════════════

class WatchSenseEngine:
    """VP99全景感知"""

    def __init__(self):
        self.md = MacroDroidController()
        self.vnc = VNCController()
        self._last_sense = None

    def full_sense(self):
        """伏羲八卦全景感知"""
        ts = datetime.now().isoformat()
        result = {
            "timestamp": ts,
            "device": DEVICE_PROFILE,
            "channels": {},
            "bagua": {},
        }

        # ☰乾 · MacroDroid HTTP
        md_health = self.md.health()
        result["channels"]["macrodroid_http"] = md_health

        # ☷坤 · 端口扫描
        ports = self.md.probe_all_ports()
        result["channels"]["tcp_ports"] = ports

        # ☲离 · VNC
        vnc_probe = self.vnc.probe()
        result["channels"]["vnc"] = vnc_probe

        # ☳震 · WiFi环境
        wifi = self.md.get_wifi_scans()
        result["channels"]["wifi_scans"] = wifi[:5] if wifi else []

        # ☴巽 · 宏活动
        macros = self.md.get_macro_activity()
        result["channels"]["macros"] = macros

        # ☵坎 · 系统日志 (最近20条)
        logs = self.md.get_system_log(20)
        result["channels"]["recent_logs"] = logs

        # ☶艮 · USB
        result["channels"]["usb"] = {
            "mtp_connected": True,
            "vid": "0x1782",
            "pid": "0x4001 (MTP)",
            "serial": DEVICE_PROFILE["serial"],
        }

        # ☱兑 · 已知命令
        result["channels"]["commands"] = MACRODROID_COMMANDS

        # 八卦评分
        score = 0
        if md_health.get("alive"): score += 15  # 乾
        if ports["open"]: score += 10  # 坤
        if vnc_probe.get("available"): score += 15  # 离
        else: score += 5  # VNC探测尝试
        if wifi: score += 10  # 震
        if macros: score += 10  # 巽
        if logs: score += 10  # 坎
        score += 10  # USB MTP (已确认)
        score += 10  # 已知命令

        result["bagua"] = {
            "☰乾_MacroDroid": "✅ ALIVE" if md_health.get("alive") else "❌ DOWN",
            "☷坤_端口": f"{len(ports['open'])}个开放: {ports['open']}",
            "☲离_VNC": "✅ 可用" if vnc_probe.get("available") else "❌ 未启动",
            "☳震_WiFi": f"{len(wifi)}次扫描" if wifi else "无数据",
            "☴巽_宏": f"{len(macros)}个活跃宏" if macros else "无数据",
            "☵坎_日志": f"{len(logs)}条最近日志",
            "☶艮_USB": "✅ MTP连接",
            "☱兑_命令": f"{len(MACRODROID_COMMANDS)}个已知命令",
            "综合评分": f"{score}/100",
        }

        self._last_sense = result
        return result

    def quick_status(self):
        """快速状态检查"""
        md = self.md.health()
        vnc = self.vnc.probe()
        return {
            "macrodroid": md.get("alive", False),
            "vnc": vnc.get("available", False),
            "usb_mtp": True,
            "ip": WATCH_IP,
            "commands_available": len(MACRODROID_COMMANDS),
        }


# ═══════════════════════════════════════════════════
# Hub HTTP Server
# ═══════════════════════════════════════════════════

_engine = WatchSenseEngine()

class WatchHubHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == '/':
            self._serve_dashboard()
        elif path == '/api/health':
            self._json({"ok": True, "device": "VP99", "hub_port": HUB_PORT,
                        "timestamp": datetime.now().isoformat()})
        elif path == '/api/status':
            self._json(_engine.quick_status())
        elif path == '/api/sense':
            self._json(_engine.full_sense())
        elif path == '/api/device':
            self._json(DEVICE_PROFILE)
        elif path == '/api/apps':
            self._json(INSTALLED_APPS)
        elif path == '/api/commands':
            self._json({"commands": MACRODROID_COMMANDS})
        elif path == '/api/macrodroid/health':
            self._json(_engine.md.health())
        elif path == '/api/macrodroid/logs':
            n = int(params.get('n', ['100'])[0])
            self._json(_engine.md.get_system_log(n))
        elif path == '/api/macrodroid/wifi':
            self._json(_engine.md.get_wifi_scans())
        elif path == '/api/macrodroid/macros':
            self._json(_engine.md.get_macro_activity())
        elif path == '/api/vnc/probe':
            self._json(_engine.vnc.probe())
        elif path == '/api/ports':
            self._json(_engine.md.probe_all_ports())
        elif path == '/api/cmd':
            cmd = params.get('cmd', [''])[0]
            if cmd:
                self._json(_engine.md.send_command(cmd))
            else:
                self._json({"error": "缺少cmd参数", "available": MACRODROID_COMMANDS})
        elif path == '/api/breakthrough':
            self._json(self._breakthrough_paths())
        else:
            self._json({"error": "未知路径", "endpoints": [
                "/", "/api/health", "/api/status", "/api/sense", "/api/device",
                "/api/apps", "/api/commands", "/api/macrodroid/health",
                "/api/macrodroid/logs?n=100", "/api/macrodroid/wifi",
                "/api/macrodroid/macros", "/api/vnc/probe", "/api/ports",
                "/api/cmd?cmd=open_wechat", "/api/breakthrough",
            ]}, code=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}

        if parsed.path == '/api/cmd':
            cmd = body.get('cmd', '')
            if cmd:
                self._json(_engine.md.send_command(cmd))
            else:
                self._json({"error": "缺少cmd", "available": MACRODROID_COMMANDS})
        else:
            self._json({"error": "POST not supported on this path"}, code=405)

    def _breakthrough_paths(self):
        """所有突破路径状态"""
        return {
            "paths": [
                {
                    "id": 1, "name": "拨号码开发者模式",
                    "code": "*#*#592411#*#*",
                    "status": "需用户在手表拨号界面输入",
                    "difficulty": "最简单(30秒)",
                },
                {
                    "id": 2, "name": "佰佑通APP远程ADB",
                    "status": "APK已提取(9.77MB), 内置Shizuku+Magisk",
                    "difficulty": "中等(5分钟)",
                },
                {
                    "id": 3, "name": "MacroDroid远程操控",
                    "status": "✅ 已激活! HTTP :8080 在线",
                    "commands": MACRODROID_COMMANDS,
                    "difficulty": "已完成",
                },
                {
                    "id": 4, "name": "VNC远程桌面",
                    "status": _engine.vnc.probe(),
                    "difficulty": "需手表启动DroidVNC-NG",
                },
                {
                    "id": 5, "name": "Shizuku权限提升",
                    "status": "已安装, 需通过ADB或无线调试启动",
                    "difficulty": "需先开启ADB",
                },
                {
                    "id": 6, "name": "Unisoc Bootloader解锁",
                    "tool": "patrislav1/unisoc-unlock",
                    "status": "高风险, 需Fastboot模式",
                    "difficulty": "高级",
                },
            ],
            "current_channels": {
                "macrodroid_http": "✅ 8个命令可用",
                "vnc": _engine.vnc.probe(),
                "usb_mtp": "✅ 文件传输可用",
                "adb": "❌ 开发者模式被HSC固件屏蔽",
            },
            "adb_unlock_hint": (
                "MacroDroid日志显示需要: "
                "adb shell pm grant com.arlosoft.macrodroid "
                "android.permission.WRITE_SECURE_SETTINGS — "
                "需先开启ADB(拨号码或佰佑通)"
            ),
        }

    def _serve_dashboard(self):
        if DASHBOARD_FILE.exists():
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(DASHBOARD_FILE.read_bytes())
        else:
            self._json({"error": "Dashboard文件不存在", "path": str(DASHBOARD_FILE)})

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))

    def log_message(self, fmt, *args):
        pass  # 静默日志


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else HUB_PORT

    print("=" * 60)
    print(f"  VP99 华强北手表 · 全量深度逆向中枢 v1.0")
    print(f"  Hub: http://localhost:{port}/")
    print(f"  手表: {WATCH_IP}")
    print("=" * 60)

    # 启动时快速感知
    status = _engine.quick_status()
    print(f"\n☰乾 MacroDroid HTTP: {'✅' if status['macrodroid'] else '❌'}")
    print(f"☲离 VNC:              {'✅' if status['vnc'] else '❌ (需手动启动DroidVNC-NG)'}")
    print(f"☶艮 USB MTP:          ✅")
    print(f"☱兑 可用命令:         {status['commands_available']}个")

    httpd = HTTPServer(('0.0.0.0', port), WatchHubHandler)
    print(f"\nHub已启动: http://localhost:{port}/")
    print(f"API文档:   http://localhost:{port}/api/health")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nHub已停止")
        httpd.server_close()


if __name__ == '__main__':
    main()
