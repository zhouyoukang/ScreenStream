"""
Samsung Galaxy Watch4 Classic - 全量数据采集器
通过ADB采集手表系统/软件/传感器/健康/硬件全部数据

用法:
    python watch_data_collector.py                    # 自动检测手表
    python watch_data_collector.py -s <serial>        # 指定设备
    python watch_data_collector.py --ip 192.168.31.X  # WiFi连接
"""

import subprocess
import json
import os
import sys
import re
from datetime import datetime
from pathlib import Path

ADB = r"D:\platform-tools\adb.exe"
DATA_DIR = Path(__file__).parent.parent / "data"


def run_adb(cmd, serial=None, timeout=15):
    """执行ADB命令并返回输出"""
    args = [ADB]
    if serial:
        args += ["-s", serial]
    args += cmd.split()
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT after {timeout}s]"
    except Exception as e:
        return f"[ERROR: {e}]"


def find_watch():
    """自动检测Galaxy Watch设备"""
    output = run_adb("devices -l")
    for line in output.splitlines():
        if "device " in line and ("SM-R8" in line or "watch" in line.lower()):
            return line.split()[0]
    # 尝试所有设备,检查model
    for line in output.splitlines():
        if line.strip() and "List of" not in line and "attached" not in line:
            serial = line.split()[0]
            model = run_adb(f"-s {serial} shell getprop ro.product.model")
            if model.startswith("SM-R8") or "watch" in model.lower():
                return serial
    return None


def collect_system_info(serial):
    """采集系统信息"""
    props = {}
    keys = [
        ("model", "ro.product.model"),
        ("brand", "ro.product.brand"),
        ("device", "ro.product.device"),
        ("board", "ro.product.board"),
        ("hardware", "ro.hardware"),
        ("android_version", "ro.build.version.release"),
        ("sdk_version", "ro.build.version.sdk"),
        ("build_id", "ro.build.display.id"),
        ("build_type", "ro.build.type"),
        ("build_date", "ro.build.date"),
        ("serial", "ro.serialno"),
        ("bootloader", "ro.bootloader"),
        ("security_patch", "ro.build.version.security_patch"),
        ("wear_os_version", "ro.build.version.release"),
        ("one_ui_watch_version", "ro.build.version.oneui"),
        ("cpu_abi", "ro.product.cpu.abi"),
        ("soc_model", "ro.hardware.chipname"),
        ("bluetooth_name", "persist.bluetooth.name"),
        ("wifi_mac", "ro.boot.wifimacaddr"),
    ]
    for name, key in keys:
        props[name] = run_adb(f"shell getprop {key}", serial)

    # 电池
    battery_raw = run_adb("shell dumpsys battery", serial)
    battery = {}
    for line in battery_raw.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            battery[k.strip()] = v.strip()
    props["battery"] = battery

    # 屏幕
    props["screen_size"] = run_adb("shell wm size", serial)
    props["screen_density"] = run_adb("shell wm density", serial)

    # 存储
    props["storage"] = run_adb("shell df -h /data", serial)

    # 内存
    meminfo = run_adb("shell cat /proc/meminfo", serial)
    mem = {}
    for line in meminfo.splitlines()[:5]:
        if ":" in line:
            k, v = line.split(":", 1)
            mem[k.strip()] = v.strip()
    props["memory"] = mem

    # 运行时间
    props["uptime"] = run_adb("shell uptime", serial)

    # WiFi
    props["wifi_info"] = run_adb("shell dumpsys wifi | head -20", serial)

    return props


def collect_installed_apps(serial):
    """采集所有已安装应用"""
    apps = {"system": [], "third_party": [], "total": 0}

    # 系统应用
    sys_apps = run_adb("shell pm list packages -s", serial)
    for line in sys_apps.splitlines():
        if line.startswith("package:"):
            apps["system"].append(line.replace("package:", ""))

    # 第三方应用
    tp_apps = run_adb("shell pm list packages -3", serial)
    for line in tp_apps.splitlines():
        if line.startswith("package:"):
            pkg = line.replace("package:", "")
            apps["third_party"].append(pkg)

    apps["total"] = len(apps["system"]) + len(apps["third_party"])

    # 详细信息 (第三方)
    apps["third_party_details"] = []
    for pkg in apps["third_party"][:50]:  # 限制50个防超时
        info = run_adb(f"shell dumpsys package {pkg} | head -30", serial, timeout=5)
        version = ""
        for line in info.splitlines():
            if "versionName" in line:
                version = line.split("=")[-1].strip()
                break
        apps["third_party_details"].append({"package": pkg, "version": version})

    return apps


def collect_sensors(serial):
    """采集传感器信息"""
    raw = run_adb("shell dumpsys sensorservice", serial, timeout=20)
    sensors = {"raw_count": 0, "sensors": []}

    for line in raw.splitlines():
        if "| " in line and ("Sensor" in line or "sensor" in line):
            sensors["sensors"].append(line.strip())
            sensors["raw_count"] += 1

    # 传感器列表
    sensor_list = run_adb("shell dumpsys sensorservice | grep -E 'name='", serial, timeout=10)
    sensors["named_sensors"] = [s.strip() for s in sensor_list.splitlines() if s.strip()]

    return sensors


def collect_health_info(serial):
    """采集健康相关信息"""
    health = {}

    # Samsung Health状态
    health["samsung_health"] = run_adb(
        "shell dumpsys package com.samsung.android.wear.shealth | head -20", serial
    )

    # Health Services
    health["health_services"] = run_adb(
        "shell dumpsys package com.google.android.wearable.healthservices | head -20", serial
    )

    # 健康权限
    health["health_permissions"] = run_adb(
        "shell dumpsys package com.samsung.android.wear.shealth | grep -A5 'granted=true'", serial
    )

    return health


def collect_connectivity(serial):
    """采集连接信息"""
    conn = {}
    conn["bluetooth"] = run_adb("shell dumpsys bluetooth_manager | head -30", serial)
    conn["wifi"] = run_adb("shell dumpsys wifi | head -30", serial)
    conn["nfc"] = run_adb("shell dumpsys nfc | head -20", serial)
    conn["ip_addr"] = run_adb("shell ip addr show wlan0", serial)
    return conn


def collect_watch_faces(serial):
    """采集已安装表盘"""
    faces = run_adb(
        "shell pm list packages | grep -iE 'watchface|watch_face|wf_|face'", serial
    )
    return [f.replace("package:", "") for f in faces.splitlines() if f.strip()]


def take_screenshot(serial):
    """截取手表屏幕"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote = f"/sdcard/watch_screen_{ts}.png"
    local = DATA_DIR / f"screenshot_{ts}.png"
    run_adb(f"shell screencap {remote}", serial)
    run_adb(f"pull {remote} {local}", serial)
    run_adb(f"shell rm {remote}", serial)
    return str(local) if local.exists() else None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Galaxy Watch4 Classic Data Collector")
    parser.add_argument("-s", "--serial", help="Device serial number")
    parser.add_argument("--ip", help="WiFi ADB IP address")
    parser.add_argument("--screenshot", action="store_true", help="Take screenshot")
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)

    serial = args.serial
    if args.ip:
        print(f"Connecting to {args.ip}:5555...")
        run_adb(f"connect {args.ip}:5555")
        serial = f"{args.ip}:5555"

    if not serial:
        print("Auto-detecting Galaxy Watch...")
        serial = find_watch()

    if not serial:
        print("ERROR: No Galaxy Watch detected!")
        print("1. Enable Developer Options on watch")
        print("2. Enable ADB Debugging")
        print("3. Enable Wireless Debugging")
        print("4. Run: adb pair <IP>:<port>")
        sys.exit(1)

    print(f"Connected to: {serial}")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("\n[1/6] Collecting system info...")
    system = collect_system_info(serial)

    print("[2/6] Collecting installed apps...")
    apps = collect_installed_apps(serial)

    print("[3/6] Collecting sensors...")
    sensors = collect_sensors(serial)

    print("[4/6] Collecting health info...")
    health = collect_health_info(serial)

    print("[5/6] Collecting connectivity...")
    connectivity = collect_connectivity(serial)

    print("[6/6] Collecting watch faces...")
    watch_faces = collect_watch_faces(serial)

    # 汇总
    result = {
        "collected_at": ts,
        "device_serial": serial,
        "system": system,
        "apps": apps,
        "sensors": sensors,
        "health": health,
        "connectivity": connectivity,
        "watch_faces": watch_faces,
    }

    # 保存
    out_file = DATA_DIR / "watch_full_dump.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 分别保存
    for name in ["system", "apps", "sensors", "health", "connectivity"]:
        with open(DATA_DIR / f"{name}_info.json", "w", encoding="utf-8") as f:
            json.dump(result[name], f, ensure_ascii=False, indent=2)

    if args.screenshot:
        print("\nTaking screenshot...")
        ss = take_screenshot(serial)
        if ss:
            print(f"Screenshot saved: {ss}")

    # 打印摘要
    print(f"\n{'='*50}")
    print(f"Galaxy Watch4 Classic Data Collection Complete")
    print(f"{'='*50}")
    print(f"Model:        {system.get('model', 'N/A')}")
    print(f"Android:      {system.get('android_version', 'N/A')}")
    print(f"Build:        {system.get('build_id', 'N/A')}")
    print(f"Security:     {system.get('security_patch', 'N/A')}")
    print(f"Battery:      {system.get('battery', {}).get('level', 'N/A')}%")
    print(f"System Apps:  {len(apps.get('system', []))}")
    print(f"3rd Party:    {len(apps.get('third_party', []))}")
    print(f"Sensors:      {sensors.get('raw_count', 0)}")
    print(f"Watch Faces:  {len(watch_faces)}")
    print(f"\nData saved to: {DATA_DIR}")


if __name__ == "__main__":
    main()
