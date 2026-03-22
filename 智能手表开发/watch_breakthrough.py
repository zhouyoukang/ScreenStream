"""
VP99 华强北手表 · 完全突破引擎
转法轮: 穷尽一切路径突破ADB封锁

用法:
  python watch_breakthrough.py          # 自动探测+尝试所有远程路径
  python watch_breakthrough.py --guide  # 输出完整物理操作指南
  python watch_breakthrough.py --monitor # 持续监控,ADB一开即自动连接
"""

import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

WATCH_IP = "192.168.31.41"
ADB = r"D:\platform-tools\adb.exe"
DATA_DIR = Path(__file__).parent / "data"
PC_IP = "192.168.31.141"

# ═══════════════════════════════════════════════════
# ☰乾 · 远程探测 (无需物理操作)
# ═══════════════════════════════════════════════════

def probe_all():
    """探测手表所有可用通道"""
    results = {}

    # MacroDroid HTTP
    try:
        r = urlopen(f"http://{WATCH_IP}:8080/", timeout=5)
        results["macrodroid"] = {"alive": True, "port": 8080}
    except:
        results["macrodroid"] = {"alive": False}

    # VNC
    try:
        s = socket.socket(); s.settimeout(2)
        s.connect((WATCH_IP, 5900)); s.close()
        results["vnc"] = {"alive": True, "port": 5900}
    except:
        results["vnc"] = {"alive": False}

    # ADB WiFi
    try:
        s = socket.socket(); s.settimeout(2)
        s.connect((WATCH_IP, 5555)); s.close()
        results["adb_wifi"] = {"alive": True, "port": 5555}
    except:
        results["adb_wifi"] = {"alive": False}

    # ADB USB
    r = subprocess.run([ADB, "devices"], capture_output=True, text=True, timeout=5)
    results["adb_usb"] = {"devices": r.stdout.strip()}

    # 扫描更多端口
    for p in [22, 23, 25, 80, 443, 2222, 4040, 5037, 7400, 8081, 8084, 8888, 9876]:
        try:
            s = socket.socket(); s.settimeout(0.8)
            if s.connect_ex((WATCH_IP, p)) == 0:
                results[f"port_{p}"] = {"alive": True}
            s.close()
        except:
            pass

    return results


def try_macrodroid_commands():
    """尝试所有MacroDroid命令"""
    results = {}
    cmds = ["open_wechat", "open_alipay", "open_taobao", "open_doubao",
            "open_amap", "open_mijia", "mute", "vibrate"]
    for cmd in cmds:
        try:
            r = urlopen(f"http://{WATCH_IP}:8080/{{ha}}?cmd={cmd}", timeout=5)
            resp = r.read().decode('utf-8', errors='ignore')
            results[cmd] = {"ok": True, "response": resp}
        except:
            results[cmd] = {"ok": False}
    return results


def check_adb_available():
    """检查ADB是否可用"""
    # WiFi ADB
    try:
        s = socket.socket(); s.settimeout(2)
        s.connect((WATCH_IP, 5555)); s.close()
        r = subprocess.run([ADB, "connect", f"{WATCH_IP}:5555"],
                          capture_output=True, text=True, timeout=10)
        if "connected" in r.stdout.lower():
            return {"available": True, "method": "wifi", "addr": f"{WATCH_IP}:5555"}
    except:
        pass

    # USB ADB (PID 4D00)
    r = subprocess.run([ADB, "devices", "-l"], capture_output=True, text=True, timeout=5)
    for line in r.stdout.split('\n'):
        if "10109530162925" in line or "VP99" in line:
            dev = line.split()[0]
            return {"available": True, "method": "usb", "addr": dev}

    return {"available": False}


# ═══════════════════════════════════════════════════
# ☳震 · ADB连接后自动配置
# ═══════════════════════════════════════════════════

def auto_setup_after_adb(device_addr):
    """ADB连接成功后自动完成所有配置"""
    print("\n" + "=" * 60)
    print("  ✅ ADB已连接! 自动配置开始...")
    print("=" * 60)

    def adb(*args):
        cmd = [ADB, "-s", device_addr] + list(args)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return r.stdout.strip()

    # 1. 基本信息
    model = adb("shell", "getprop", "ro.product.model")
    android = adb("shell", "getprop", "ro.build.version.release")
    sdk = adb("shell", "getprop", "ro.build.version.sdk")
    print(f"\n☰乾 设备: {model} Android {android} (SDK {sdk})")

    # 2. 启用无线ADB (持久化)
    adb("shell", "setprop", "service.adb.tcp.port", "5555")
    print("☷坤 WiFi ADB 端口设为 5555")

    # 3. 授权MacroDroid
    adb("shell", "pm", "grant", "com.arlosoft.macrodroid",
        "android.permission.WRITE_SECURE_SETTINGS")
    print("☲离 MacroDroid WRITE_SECURE_SETTINGS 已授权")

    # 4. 获取完整系统属性
    props = adb("shell", "getprop")
    props_file = DATA_DIR / "vp99_system_props.txt"
    props_file.write_text(props, encoding='utf-8')
    print(f"☳震 系统属性已保存: {props_file} ({len(props)} chars)")

    # 5. 获取已安装包列表
    packages = adb("shell", "pm", "list", "packages", "-f")
    pkgs_file = DATA_DIR / "vp99_packages.txt"
    pkgs_file.write_text(packages, encoding='utf-8')
    pkg_count = len([l for l in packages.split('\n') if l.strip()])
    print(f"☴巽 已安装包: {pkg_count}个, 已保存: {pkgs_file}")

    # 6. 获取传感器信息
    sensors = adb("shell", "dumpsys", "sensorservice")
    sensors_file = DATA_DIR / "vp99_sensors.txt"
    sensors_file.write_text(sensors[:50000], encoding='utf-8')
    print(f"☵坎 传感器信息已保存")

    # 7. 获取屏幕信息
    wm = adb("shell", "wm", "size")
    density = adb("shell", "wm", "density")
    print(f"☶艮 屏幕: {wm} | 密度: {density}")

    # 8. 启动DroidVNC-NG
    adb("shell", "am", "start", "-n",
        "net.christianbeier.droidvnc_ng/.MainActivity")
    print("☱兑 DroidVNC-NG 已启动")

    # 9. 设置永不休眠(充电时)
    adb("shell", "settings", "put", "global", "stay_on_while_plugged_in", "3")
    print("☯ 充电时屏幕常亮已设置")

    # 10. 保存完整报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "device": device_addr,
        "model": model,
        "android": android,
        "sdk": sdk,
        "screen": wm,
        "density": density,
        "packages": pkg_count,
        "macrodroid_granted": True,
        "vnc_started": True,
        "wifi_adb": "5555",
    }
    report_file = DATA_DIR / "vp99_adb_setup_report.json"
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n✅ 配置完成! 报告: {report_file}")
    return report


# ═══════════════════════════════════════════════════
# ☴巽 · 物理操作指南 (用户最少步骤)
# ═══════════════════════════════════════════════════

def print_guide():
    """输出完整的用户物理操作指南"""
    guide = """
╔══════════════════════════════════════════════════════════════╗
║           VP99 华强北手表 · ADB完全突破指南                  ║
║           转法轮 · 穷尽一切路径                              ║
╚══════════════════════════════════════════════════════════════╝

════════════════════════════════════════════════════════════════
 路径A: Activity Launcher (最简单, 3分钟)
════════════════════════════════════════════════════════════════

  手表上操作:
  1. 打开 Play 商店 (手表上已安装)
  2. 搜索: Activity Launcher
  3. 安装 Activity Launcher (by Adam Szalkowski, ~3MB)
  4. 打开 Activity Launcher
  5. 在列表中找到 "Settings" (com.android.settings)
  6. 展开 Settings, 找到:
     - "DevelopmentSettingsDashboardActivity" 或
     - "DevelopmentSettings" 或
     - "Development"
  7. 点击它 → 进入开发者选项
  8. 开启 "USB调试" 和 "无线调试"

  完成后在电脑运行:
  python watch_breakthrough.py --monitor

════════════════════════════════════════════════════════════════
 路径B: 浏览器Intent (2分钟)
════════════════════════════════════════════════════════════════

  电脑上: 已自动启动HTTP服务 (http://{pc}:8899)

  手表上操作:
  1. 打开 夸克浏览器
  2. 在地址栏输入: http://{pc}:8899/adb_unlock.html
  3. 点击页面上的各个链接, 尝试打开:
     - "开发者选项 (Intent)"
     - "展锐工程模式"
     - 等等...
  4. 如果有链接能打开开发者选项 → 开启USB调试

════════════════════════════════════════════════════════════════
 路径C: 启动DroidVNC-NG (30秒, 最快)
════════════════════════════════════════════════════════════════

  手表上操作:
  1. 找到并打开 DroidVNC-NG 应用
  2. 点击 "Start" 按钮
  3. 等待VNC服务启动

  完成后在电脑运行:
  python watch_breakthrough.py --monitor
  → VNC连接后, Agent可远程操控手表完成所有后续步骤

════════════════════════════════════════════════════════════════
 路径D: SPD深刷模式 (高级, 10分钟)
════════════════════════════════════════════════════════════════

  需要工具:
  - spd_dump (从 blog.huoiop.cn 或 Atlas华强北手表下载站获取)
  - FDL文件 (9832E/8541E平台)
  - 展锐USB驱动

  步骤:
  1. 安装展锐USB驱动
  2. 手表关机
  3. 按住侧键(非电源键) + 连接USB → 进入深刷模式
     单按键手表: 运行 spd_dump --kickto 2 --wait 300, 关机后连接
  4. spd_dump进入FDL2模式 → 提取vbmeta → 刷入TWRP
  5. TWRP中修改build.prop, 添加:
     ro.debuggable=1
     persist.service.adb.enable=1
     service.adb.tcp.port=5555
     persist.sys.usb.config=mtp,adb
  6. 重启 → ADB自动可用

  详细教程: https://blog.huoiop.cn/?p=333

════════════════════════════════════════════════════════════════
 路径E: 佰佑通APP BLE (5分钟)
════════════════════════════════════════════════════════════════

  需要: 手机一台 (Android)

  1. 在手机上安装佰佑通APK:
     data/vp99_extracted/ 目录下有 com.byyoung.setting.apk (9.77MB)
  2. 打开佰佑通 → BLE扫描 → 配对VP99
  3. 在"工具箱"中找到ADB调试开关 → 开启

════════════════════════════════════════════════════════════════
""".format(pc=PC_IP)
    print(guide)


# ═══════════════════════════════════════════════════
# ☵坎 · 持续监控 (等待ADB/VNC激活)
# ═══════════════════════════════════════════════════

def monitor_mode():
    """持续监控手表状态, ADB/VNC一开即自动连接和配置"""
    print("=" * 60)
    print("  VP99 持续监控模式 — 等待ADB或VNC激活")
    print("  手表IP:", WATCH_IP)
    print("  按 Ctrl+C 退出")
    print("=" * 60)

    check_interval = 5
    while True:
        try:
            ts = datetime.now().strftime("%H:%M:%S")

            # 检查ADB WiFi
            try:
                s = socket.socket(); s.settimeout(1.5)
                s.connect((WATCH_IP, 5555)); s.close()
                print(f"\n[{ts}] ✅ ADB WiFi :5555 已开放!")
                r = subprocess.run([ADB, "connect", f"{WATCH_IP}:5555"],
                                  capture_output=True, text=True, timeout=10)
                if "connected" in r.stdout.lower():
                    auto_setup_after_adb(f"{WATCH_IP}:5555")
                    return True
            except:
                pass

            # 检查ADB USB
            r = subprocess.run([ADB, "devices"], capture_output=True, text=True, timeout=5)
            if "4D00" in r.stdout or "device" in r.stdout:
                for line in r.stdout.split('\n'):
                    if '\tdevice' in line and ('4D00' in line or WATCH_IP in line):
                        dev = line.split()[0]
                        print(f"\n[{ts}] ✅ ADB USB已连接: {dev}")
                        auto_setup_after_adb(dev)
                        return True

            # 检查VNC
            try:
                s = socket.socket(); s.settimeout(1.5)
                s.connect((WATCH_IP, 5900)); s.close()
                print(f"\n[{ts}] ✅ VNC :5900 已开放!")
                print("  可以使用 VNC Viewer 连接: 192.168.31.41:5900")
                print("  或运行: python tools/watch_bridge.py")
                return True
            except:
                pass

            # MacroDroid心跳
            try:
                r = urlopen(f"http://{WATCH_IP}:8080/", timeout=3)
                md_status = "✅"
            except:
                md_status = "❌"

            sys.stdout.write(f"\r[{ts}] MacroDroid:{md_status} | ADB:⏳ | VNC:⏳ | 等待中...")
            sys.stdout.flush()
            time.sleep(check_interval)

        except KeyboardInterrupt:
            print("\n\n监控已停止。")
            return False


# ═══════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════

def main():
    if "--guide" in sys.argv:
        print_guide()
        return

    if "--monitor" in sys.argv:
        monitor_mode()
        return

    print("=" * 60)
    print("  VP99 华强北手表 · 完全突破引擎")
    print("  转法轮 · 穷尽一切路径")
    print("=" * 60)

    # 第一转 · 观
    print("\n☲离 第一转·观: 探测所有通道...")
    probe = probe_all()
    for k, v in probe.items():
        status = "✅" if v.get("alive") else "❌"
        print(f"  {k}: {status}")

    # 检查ADB是否已经可用
    print("\n☳震 检查ADB...")
    adb = check_adb_available()
    if adb["available"]:
        print(f"  ✅ ADB已可用! ({adb['method']}: {adb['addr']})")
        auto_setup_after_adb(adb["addr"])
        return

    print("  ❌ ADB不可用 (开发者模式被HSC固件屏蔽)")

    # MacroDroid命令测试
    if probe.get("macrodroid", {}).get("alive"):
        print("\n☴巽 测试MacroDroid命令...")
        cmds = try_macrodroid_commands()
        ok = sum(1 for v in cmds.values() if v.get("ok"))
        print(f"  {ok}/{len(cmds)} 命令可用")

    # 输出指南
    print("\n" + "=" * 60)
    print("  ⚠️ 所有远程路径已穷尽 — 需要用户物理操作")
    print("  运行 python watch_breakthrough.py --guide 查看完整指南")
    print("  运行 python watch_breakthrough.py --monitor 等待ADB激活")
    print("=" * 60)

    # 自动进入监控模式
    print("\n是否进入监控模式? (等待ADB/VNC激活)")
    print("按 Enter 进入, Ctrl+C 退出...")
    try:
        input()
        monitor_mode()
    except (KeyboardInterrupt, EOFError):
        print("\n退出。")


if __name__ == "__main__":
    main()
