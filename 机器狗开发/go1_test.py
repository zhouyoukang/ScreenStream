#!/usr/bin/env python3
"""
宇树Go1机器狗 — 一键全功能诊断与测试
用法: python go1_test.py [--host 192.168.123.161] [--skip-motor] [--skip-mqtt]
      python go1_test.py [--ip 192.168.12.1] [--skip-motor]  # WiFi模式

测试项:
  T1. 网络连通性 (ping + TCP端口扫描)
  T2. SSH连接
  T3. MQTT Broker连接 + 主题嗅探
  T4. MQTT动作控制 (standDown/standUp)
  T5. MQTT遥杆控制 (stick)
  T6. 摄像头UDP流检测
  T7. RS485电机直接通信 (可选, 需USB-RS485适配器)
"""

import sys
import time
import socket
import struct
import argparse
import platform
from datetime import datetime


GO1_IP = "192.168.12.1"
RESULTS = []


def log(test_id, name, status, detail=""):
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    line = f"  {icon} {test_id} {name}: {status}"
    if detail:
        line += f" — {detail}"
    print(line)
    RESULTS.append({"id": test_id, "name": name, "status": status, "detail": detail})


def test_ping(ip):
    """T1a: ICMP Ping"""
    import subprocess
    param = "-n" if platform.system() == "Windows" else "-c"
    try:
        r = subprocess.run(
            ["ping", param, "2", "-w", "2000", ip],
            capture_output=True, timeout=10
        )
        if r.returncode == 0:
            log("T1a", "Ping", "PASS", f"{ip} reachable")
            return True
        else:
            log("T1a", "Ping", "FAIL", f"{ip} unreachable")
            return False
    except Exception as e:
        log("T1a", "Ping", "FAIL", str(e))
        return False


def test_tcp_ports(ip):
    """T1b: TCP端口扫描"""
    ports = {
        22: "SSH",
        80: "HTTP/MQTT-WS",
        1883: "MQTT",
        8080: "WebUI",
        9800: "FileUpload",
        9801: "MQTT-WS-Alt",
    }
    open_ports = []
    for port, name in ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            result = sock.connect_ex((ip, port))
            if result == 0:
                open_ports.append(f"{port}({name})")
        except Exception:
            pass
        finally:
            sock.close()

    if open_ports:
        log("T1b", "TCP端口扫描", "PASS", ", ".join(open_ports))
    else:
        log("T1b", "TCP端口扫描", "FAIL", "所有端口关闭")
    return open_ports


def test_ssh(ip):
    """T2: SSH连接测试"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    try:
        sock.connect((ip, 22))
        banner = sock.recv(256).decode("utf-8", errors="ignore").strip()
        log("T2", "SSH", "PASS", f"Banner: {banner}")
        return True
    except Exception as e:
        log("T2", "SSH", "FAIL", str(e))
        return False
    finally:
        sock.close()


def test_mqtt_connect(ip):
    """T3: MQTT Broker连接"""
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        log("T3", "MQTT连接", "FAIL", "paho-mqtt未安装: pip install paho-mqtt")
        return None

    connected = [False]
    topics_seen = []

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            connected[0] = True
            client.subscribe("#")  # 订阅所有主题
        else:
            connected[0] = False

    def on_message(client, userdata, msg):
        topic = msg.topic
        if topic not in topics_seen:
            topics_seen.append(topic)

    try:
        # 兼容paho-mqtt v1和v2
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "go1_test")
        except (AttributeError, TypeError):
            client = mqtt.Client("go1_test")

        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(ip, 1883, 60)
        client.loop_start()

        # 等待连接
        for _ in range(30):
            if connected[0]:
                break
            time.sleep(0.1)

        if not connected[0]:
            log("T3", "MQTT连接", "FAIL", f"无法连接 {ip}:1883")
            client.loop_stop()
            return None

        log("T3", "MQTT连接", "PASS", f"已连接 {ip}:1883")

        # 嗅探3秒
        print("    嗅探MQTT主题 (3秒)...")
        time.sleep(3)
        if topics_seen:
            log("T3b", "MQTT主题嗅探", "PASS", f"发现 {len(topics_seen)} 个主题: {', '.join(topics_seen[:10])}")
        else:
            log("T3b", "MQTT主题嗅探", "WARN", "3秒内未收到任何消息")

        return client

    except Exception as e:
        log("T3", "MQTT连接", "FAIL", str(e))
        return None


def test_mqtt_action(client, action="standDown"):
    """T4: MQTT动作控制"""
    if client is None:
        log("T4", f"MQTT动作({action})", "SKIP", "MQTT未连接")
        return False

    try:
        info = client.publish("controller/action", action, qos=2)
        info.wait_for_publish()
        log("T4", f"MQTT动作({action})", "PASS", f"已发送 controller/action={action}")
        return True
    except Exception as e:
        log("T4", f"MQTT动作({action})", "FAIL", str(e))
        return False


def test_mqtt_stick(client):
    """T5: MQTT遥杆控制 (发送零值=停止)"""
    if client is None:
        log("T5", "MQTT遥杆", "SKIP", "MQTT未连接")
        return False

    try:
        # 发送全零遥杆值 (停止)
        stick_data = struct.pack('ffff', 0.0, 0.0, 0.0, 0.0)
        info = client.publish("controller/stick", stick_data, qos=2)
        info.wait_for_publish()
        log("T5", "MQTT遥杆(停止)", "PASS", "已发送 controller/stick=[0,0,0,0]")
        return True
    except Exception as e:
        log("T5", "MQTT遥杆", "FAIL", str(e))
        return False


def test_camera_ports(ip):
    """T6: 摄像头UDP端口检测"""
    cam_ports = {9101: "前方", 9102: "下巴", 9103: "左侧", 9104: "右侧", 9105: "底部"}
    available = []

    for port, name in cam_ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        try:
            # 尝试绑定UDP端口接收数据
            sock.bind(("0.0.0.0", port))
            sock.settimeout(1)
            try:
                data, addr = sock.recvfrom(4096)
                if data:
                    available.append(f"{port}({name})")
            except socket.timeout:
                pass  # 没有数据不代表不可用
        except OSError:
            pass  # 端口被占用
        finally:
            sock.close()

    if available:
        log("T6", "摄像头UDP流", "PASS", ", ".join(available))
    else:
        log("T6", "摄像头UDP流", "WARN", "未检测到UDP视频流 (需Go1配置udpHost为本机IP)")
    return available


def test_motor_serial(port=None):
    """T7: RS485电机直接通信"""
    if port is None:
        port = "COM5" if platform.system() == "Windows" else "/dev/ttyUSB0"

    try:
        import serial
    except ImportError:
        log("T7", "RS485电机", "FAIL", "pyserial未安装")
        return False

    try:
        ser = serial.Serial(port, 5000000, timeout=0.1)
        log("T7a", f"串口({port})", "PASS", f"打开成功 @ 5Mbps")
    except Exception as e:
        log("T7a", f"串口({port})", "FAIL", str(e))
        return False

    try:
        sys.path.insert(0, "gooddawg")
        import build_a_packet as bp

        for motor_id in [0, 1, 2]:
            packet = bp.build_a_packet(id=motor_id, q=0, dq=0, Kp=0, Kd=0, tau=0)
            ser.reset_input_buffer()
            bp.send_packet(ser, packet)
            time.sleep(0.05)
            response = ser.read(256)
            if response:
                log(f"T7b", f"电机{motor_id}", "PASS", f"响应 {len(response)}B")
            else:
                log(f"T7b", f"电机{motor_id}", "FAIL", "无响应")
    except Exception as e:
        log("T7b", "电机通信", "FAIL", str(e))
    finally:
        ser.close()

    return True


def print_report():
    """打印测试报告"""
    print("\n" + "=" * 60)
    print("  Go1 测试报告")
    print("=" * 60)

    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    warned = sum(1 for r in RESULTS if r["status"] == "WARN")
    skipped = sum(1 for r in RESULTS if r["status"] == "SKIP")
    total = len(RESULTS)

    for r in RESULTS:
        icon = "✅" if r["status"] == "PASS" else "❌" if r["status"] == "FAIL" else "⚠️" if r["status"] == "WARN" else "⏭️"
        print(f"  {icon} {r['id']} {r['name']}: {r['detail']}")

    print(f"\n  总计: {total} | ✅通过: {passed} | ❌失败: {failed} | ⚠️警告: {warned} | ⏭️跳过: {skipped}")
    print("=" * 60)

    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="Go1机器狗全功能诊断")
    parser.add_argument("--ip", "--host", default=GO1_IP, help=f"Go1 IP地址 (默认: {GO1_IP}, 以太网用192.168.123.161)")
    parser.add_argument("--skip-motor", action="store_true", help="跳过RS485电机测试")
    parser.add_argument("--skip-mqtt", action="store_true", help="跳过MQTT测试")
    parser.add_argument("--serial-port", default=None, help="RS485串口 (默认: 自动检测)")
    parser.add_argument("--action", default=None, help="发送MQTT动作命令 (如: standUp, standDown, walk)")
    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print(f"  宇树Go1机器狗 全功能诊断")
    print(f"  目标: {args.ip}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}\n")

    # T1: 网络连通性
    print("[T1] 网络连通性...")
    reachable = test_ping(args.ip)
    open_ports = test_tcp_ports(args.ip) if reachable else []

    if not reachable:
        print("\n  ⚠️ Go1不可达。请检查:")
        print("    1. Go1是否已开机 (开机后约30秒网络就绪)")
        print("    2. 网线是否连接到Go1头部网口")
        print("    3. WiFi模式: 连接Go1 AP (SSID: Unitree_Go1XXXXX), 用 --ip 192.168.12.1")
        print("    4. 以太网模式: 网线连Go1头部, 配置IP 192.168.123.162/24, 用 --host 192.168.123.161")

        # 检查本机是否有192.168.12.x的IP
        try:
            import subprocess
            r = subprocess.run(["ipconfig"] if platform.system() == "Windows" else ["ip", "addr"],
                             capture_output=True, timeout=5)
            stdout_text = r.stdout.decode("gbk", errors="ignore") if platform.system() == "Windows" else r.stdout.decode("utf-8", errors="ignore")
            if "192.168.12" not in stdout_text and "192.168.123" not in stdout_text:
                print("\n  💡 建议: 本机无Go1子网IP")
                print("     以太网: .\\tools\\setup_ethernet.ps1 -Connect (推荐,WiFi不断连)")
                print("     WiFi: 连接Go1热点 Unitree_Go1XXXXX (密码 00000000)")
        except Exception:
            pass

        print_report()
        return

    # T2: SSH
    print("\n[T2] SSH连接...")
    test_ssh(args.ip)

    # T3-T5: MQTT
    mqtt_client = None
    if not args.skip_mqtt and any("1883" in p for p in open_ports):
        print("\n[T3] MQTT Broker...")
        mqtt_client = test_mqtt_connect(args.ip)

        if mqtt_client:
            if args.action:
                print(f"\n[T4] MQTT动作: {args.action}...")
                test_mqtt_action(mqtt_client, args.action)
                time.sleep(2)
            else:
                print("\n[T4] MQTT动作测试 (跳过, 使用 --action standUp 启用)")
                log("T4", "MQTT动作", "SKIP", "使用 --action 参数启用")

            print("\n[T5] MQTT遥杆...")
            test_mqtt_stick(mqtt_client)
    elif args.skip_mqtt:
        log("T3", "MQTT", "SKIP", "用户跳过")
    else:
        log("T3", "MQTT", "FAIL", "端口1883未开放")

    # T6: 摄像头
    print("\n[T6] 摄像头UDP流...")
    test_camera_ports(args.ip)

    # T7: RS485电机
    if not args.skip_motor:
        print("\n[T7] RS485电机...")
        test_motor_serial(args.serial_port)
    else:
        log("T7", "RS485电机", "SKIP", "用户跳过")

    # 清理
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

    # 报告
    success = print_report()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
