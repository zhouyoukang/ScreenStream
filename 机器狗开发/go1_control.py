#!/usr/bin/env python3
"""
Go1 统一控制入口 — MQTT + UDP 双模式，自动检测连接
用法:
  python go1_control.py                          # 自动检测Go1
  python go1_control.py --host 192.168.123.161   # 以太网模式
  python go1_control.py --host 192.168.12.1      # WiFi模式
  python go1_control.py --action standUp         # 直接执行动作
  python go1_control.py --interactive            # 交互式控制台
"""

import sys
import time
import json
import socket
import struct
import argparse
import threading
from datetime import datetime

# ============================================================
# 配置
# ============================================================
WIFI_IP = "192.168.12.1"
ETH_IP = "192.168.123.161"
MQTT_PORT = 1883
UDP_HIGH_PORT = 8086  # Go1 UDP高层端口 (避免与RTSP 8082冲突)
UDP_LOW_PORT = 8007
UDP_LISTEN_PORT = 8090

# MQTT主题
TOPIC_ACTION = "controller/action"
TOPIC_STICK = "controller/stick"
TOPIC_LED = "programming/code"

# 可用动作
ACTIONS = {
    "standUp": "站立",
    "standDown": "趴下",
    "walk": "行走模式",
    "run": "奔跑模式",
    "climb": "爬坡模式",
    "dance1": "舞蹈1",
    "dance2": "舞蹈2",
    "damping": "急停(阻尼模式)",
    "straightHand1": "握手1",
    "jumpYaw": "原地跳转",
    "hi": "打招呼",
    "backflip": "后空翻(危险!)",
}


# ============================================================
# 网络探测
# ============================================================
def probe_host(ip, port, timeout=2):
    """探测主机端口是否可达"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def auto_detect():
    """自动检测Go1连接方式，返回(ip, mode)"""
    print("  自动检测Go1连接...")

    # 并行探测WiFi和以太网
    results = {}

    def _probe(name, ip):
        results[name] = probe_host(ip, MQTT_PORT, timeout=2)

    t1 = threading.Thread(target=_probe, args=("eth", ETH_IP))
    t2 = threading.Thread(target=_probe, args=("wifi", WIFI_IP))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    if results.get("eth"):
        print(f"  ✅ 以太网连接: {ETH_IP} (推荐)")
        return ETH_IP, "ethernet"
    elif results.get("wifi"):
        print(f"  ✅ WiFi连接: {WIFI_IP}")
        return WIFI_IP, "wifi"
    else:
        print("  ❌ Go1不可达 (WiFi和以太网均无响应)")
        print("     请检查Go1是否开机 + 网线/WiFi连接")
        return None, None


# ============================================================
# MQTT控制器
# ============================================================
class MQTTController:
    def __init__(self, host, port=MQTT_PORT):
        self.host = host
        self.port = port
        self.client = None
        self.connected = False
        self.state = {}

    def connect(self, timeout=5):
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            print("  ❌ paho-mqtt未安装: pip install paho-mqtt")
            return False

        self.client = mqtt.Client(client_id=f"go1_control_{int(time.time())}")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        try:
            self.client.connect(self.host, self.port, keepalive=60)
            self.client.loop_start()

            start = time.time()
            while not self.connected and (time.time() - start) < timeout:
                time.sleep(0.1)

            if self.connected:
                print(f"  ✅ MQTT已连接: {self.host}:{self.port}")
                return True
            else:
                print(f"  ❌ MQTT连接超时: {self.host}:{self.port}")
                return False
        except Exception as e:
            print(f"  ❌ MQTT连接失败: {e}")
            return False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            client.subscribe("bms/state")
            client.subscribe("firmware/version")

    def _on_message(self, client, userdata, msg):
        try:
            self.state[msg.topic] = msg.payload.decode("utf-8", errors="ignore")
        except Exception:
            self.state[msg.topic] = msg.payload.hex()

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False

    def action(self, cmd):
        """发送动作命令"""
        if not self.connected:
            print("  ❌ MQTT未连接")
            return False
        self.client.publish(TOPIC_ACTION, cmd, qos=1)
        desc = ACTIONS.get(cmd, cmd)
        print(f"  → 动作: {cmd} ({desc})")
        return True

    def stick(self, lx=0, ly=0, rx=0, ry=0):
        """发送遥杆命令 (各值范围 -1.0 ~ 1.0)"""
        if not self.connected:
            return False
        data = struct.pack('ffff',
                          max(-1, min(1, float(lx))),
                          max(-1, min(1, float(ly))),
                          max(-1, min(1, float(rx))),
                          max(-1, min(1, float(ry))))
        self.client.publish(TOPIC_STICK, data, qos=0)
        return True

    def led(self, r, g, b):
        """设置LED颜色"""
        if not self.connected:
            return False
        code = f"child_conn.send('change_light({r},{g},{b})')"
        self.client.publish(TOPIC_LED, code, qos=1)
        print(f"  → LED: ({r},{g},{b})")
        return True

    def walk(self, vx=0.3, vy=0, yaw=0, duration=2.0):
        """行走控制"""
        if not self.connected:
            return False
        self.action("walk")
        time.sleep(1)
        steps = int(duration / 0.1)
        for _ in range(steps):
            self.stick(lx=0, ly=vx, rx=yaw, ry=0)
            time.sleep(0.1)
        self.stick(0, 0, 0, 0)
        return True

    def get_state(self):
        """获取机器人状态"""
        return dict(self.state)

    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False


# ============================================================
# 交互式控制台
# ============================================================
def interactive_console(ctrl):
    """交互式控制台"""
    print(f"\n{'=' * 50}")
    print("  Go1 交互式控制台")
    print("  输入动作名称或命令，Ctrl+C退出")
    print(f"{'=' * 50}")
    print("\n可用动作:")
    for k, v in ACTIONS.items():
        print(f"  {k:<20} {v}")
    print(f"\n特殊命令:")
    print(f"  {'led R G B':<20} 设置LED颜色")
    print(f"  {'walk [速度] [时间]':<20} 前进行走")
    print(f"  {'turn [速度] [时间]':<20} 原地旋转")
    print(f"  {'state':<20} 查看机器人状态")
    print(f"  {'stop':<20} 急停")
    print(f"  {'quit/exit':<20} 退出")
    print()

    while True:
        try:
            cmd = input("Go1> ").strip()
            if not cmd:
                continue

            parts = cmd.split()
            action = parts[0].lower()

            if action in ("quit", "exit", "q"):
                break
            elif action == "stop":
                ctrl.action("damping")
            elif action == "state":
                state = ctrl.get_state()
                if state:
                    for k, v in state.items():
                        print(f"  {k}: {v[:100] if len(v) > 100 else v}")
                else:
                    print("  (无状态数据)")
            elif action == "led":
                if len(parts) >= 4:
                    ctrl.led(int(parts[1]), int(parts[2]), int(parts[3]))
                else:
                    print("  用法: led R G B (0-255)")
            elif action == "walk":
                speed = float(parts[1]) if len(parts) > 1 else 0.3
                duration = float(parts[2]) if len(parts) > 2 else 2.0
                ctrl.walk(vx=speed, duration=duration)
            elif action == "turn":
                speed = float(parts[1]) if len(parts) > 1 else 0.5
                duration = float(parts[2]) if len(parts) > 2 else 2.0
                ctrl.walk(vx=0, yaw=speed, duration=duration)
            elif action in ACTIONS or action[0].isupper():
                ctrl.action(action if action[0].isupper() else cmd)
            else:
                # 尝试作为原始动作发送
                ctrl.action(cmd)

        except KeyboardInterrupt:
            print("\n退出")
            break
        except Exception as e:
            print(f"  错误: {e}")


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Go1统一控制入口 (MQTT)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
可用动作:
  standUp, standDown, walk, run, climb,
  dance1, dance2, damping, straightHand1,
  jumpYaw, hi, backflip

示例:
  python go1_control.py --action standUp
  python go1_control.py --host 192.168.123.161 --interactive
  python go1_control.py --action walk --walk-speed 0.3 --walk-time 3
  python go1_control.py --led 255 0 0
        """)

    parser.add_argument("--host", "--ip", default=None,
                       help="Go1 IP (默认自动检测, 以太网192.168.123.161, WiFi192.168.12.1)")
    parser.add_argument("--action", "-a", default=None,
                       help="执行动作命令")
    parser.add_argument("--interactive", "-i", action="store_true",
                       help="进入交互式控制台")
    parser.add_argument("--led", nargs=3, type=int, metavar=("R", "G", "B"),
                       help="设置LED颜色 (0-255)")
    parser.add_argument("--walk-speed", type=float, default=0.3,
                       help="行走速度 (0.0-1.0, 默认0.3)")
    parser.add_argument("--walk-time", type=float, default=2.0,
                       help="行走时间(秒, 默认2.0)")
    parser.add_argument("--status", action="store_true",
                       help="显示机器人状态后退出")

    args = parser.parse_args()

    print(f"\n{'=' * 50}")
    print(f"  Go1 控制器 v1.0")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 50}\n")

    # 确定目标IP
    if args.host:
        host = args.host
        mode = "ethernet" if "123" in host else "wifi"
        print(f"  目标: {host} ({mode}模式)")
    else:
        host, mode = auto_detect()
        if not host:
            sys.exit(1)

    # 连接MQTT
    ctrl = MQTTController(host)
    if not ctrl.connect():
        sys.exit(1)

    try:
        time.sleep(0.5)  # 等待订阅消息

        if args.status:
            time.sleep(2)
            state = ctrl.get_state()
            print("\n  机器人状态:")
            for k, v in state.items():
                print(f"    {k}: {v[:200]}")
            if not state:
                print("    (无状态数据)")

        elif args.led:
            ctrl.led(*args.led)

        elif args.action:
            ctrl.action(args.action)
            if args.action == "walk":
                time.sleep(1)
                ctrl.walk(vx=args.walk_speed, duration=args.walk_time)
            else:
                time.sleep(2)

        elif args.interactive:
            interactive_console(ctrl)

        else:
            # 默认：显示状态
            time.sleep(2)
            print("\n  连接成功! 使用 --interactive 进入交互模式")
            print("  使用 --action standUp 执行动作")
            state = ctrl.get_state()
            if state:
                print("\n  收到状态:")
                for k, v in state.items():
                    print(f"    {k}: {v[:100]}")

    except KeyboardInterrupt:
        print("\n  中断")
    finally:
        ctrl.disconnect()
        print("  已断开连接")


if __name__ == "__main__":
    main()
