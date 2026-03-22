"""
Samsung Galaxy Watch4 Classic - 实时监控
持续采集电量/心率/步数等关键指标

用法:
    python watch_monitor.py                  # 自动检测
    python watch_monitor.py -s <serial>      # 指定设备
    python watch_monitor.py --interval 10    # 10秒间隔
"""

import subprocess
import json
import time
import sys
from datetime import datetime
from pathlib import Path

ADB = r"D:\platform-tools\adb.exe"
DATA_DIR = Path(__file__).parent.parent / "data"


def adb(cmd, serial=None, timeout=10):
    args = [ADB]
    if serial:
        args += ["-s", serial]
    args += cmd.split()
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def get_battery(serial):
    raw = adb("shell dumpsys battery", serial)
    info = {}
    for line in raw.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip()
            if k == "level":
                info["level"] = int(v)
            elif k == "temperature":
                info["temperature"] = int(v) / 10.0
            elif k == "status":
                info["charging"] = v == "2"  # 2=charging
    return info


def get_activity(serial):
    raw = adb("shell dumpsys activity activities | head -5", serial)
    for line in raw.splitlines():
        if "mResumedActivity" in line or "topActivity" in line:
            return line.strip()
    return "unknown"


def get_steps(serial):
    # 尝试通过sensor读取步数 (需要权限)
    raw = adb("shell dumpsys sensorservice | grep -i step", serial, timeout=5)
    return raw[:200] if raw else "N/A"


def monitor(serial, interval=30):
    print(f"Monitoring Galaxy Watch (serial={serial}, interval={interval}s)")
    print(f"{'Time':<20} {'Battery':>8} {'Temp':>6} {'Charging':>10} {'Top Activity'}")
    print("-" * 80)

    log_file = DATA_DIR / "monitor_log.jsonl"
    DATA_DIR.mkdir(exist_ok=True)

    try:
        while True:
            ts = datetime.now().strftime("%H:%M:%S")
            bat = get_battery(serial)
            act = get_activity(serial)

            level = bat.get("level", "?")
            temp = bat.get("temperature", "?")
            charging = "Yes" if bat.get("charging") else "No"

            # 截断activity显示
            act_short = act[-40:] if len(act) > 40 else act

            print(f"{ts:<20} {level:>7}% {temp:>5}C {charging:>10} {act_short}")

            # 写日志
            entry = {"ts": datetime.now().isoformat(), "battery": bat, "activity": act}
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Galaxy Watch Monitor")
    parser.add_argument("-s", "--serial", help="Device serial")
    parser.add_argument("--interval", type=int, default=30, help="Poll interval (seconds)")
    args = parser.parse_args()

    serial = args.serial
    if not serial:
        # 尝试检测
        devices = adb("devices")
        for line in devices.splitlines():
            if "device" in line and "List" not in line:
                s = line.split()[0]
                model = adb(f"-s {s} shell getprop ro.product.model")
                if "SM-R8" in model:
                    serial = s
                    break

    if not serial:
        print("No Galaxy Watch found. Use -s <serial> or connect first.")
        sys.exit(1)

    model = adb(f"-s {serial} shell getprop ro.product.model")
    print(f"Connected: {model} ({serial})")
    monitor(serial, args.interval)


if __name__ == "__main__":
    main()
