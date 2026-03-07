#!/usr/bin/env python3
"""
ScreenStream 画质设置工具

修改DataStore preferences设置编码参数，然后重启投屏。
支持被ss-bridge.py调用实现远程画质切换。

用法:
  python set_codec.py --device SERIAL [--scale 25|50|75] [--restart]
  python set_codec.py --device 192.168.31.40:40419 --scale 50
"""
import subprocess, base64, sys, argparse, time

PKG = "info.dvkr.screenstream.dev"

def encode_varint(value):
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)

def make_int_entry(key, value):
    key_bytes = key.encode('utf-8')
    key_field = b'\x0A' + bytes([len(key_bytes)]) + key_bytes
    val_varint = encode_varint(value)
    val_inner = b'\x18' + val_varint
    val_field = b'\x12' + bytes([len(val_inner)]) + val_inner
    entry = key_field + val_field
    return b'\x0A' + bytes([len(entry)]) + entry

def set_quality(device, scale=25, port=8080, codec=1, restart=True):
    """设置ScreenStream画质参数并可选重启"""
    data = (make_int_entry('SERVER_PORT', port) +
            make_int_entry('STREAM_CODEC', codec) +
            make_int_entry('RESIZE_FACTOR', scale))
    b64 = base64.b64encode(data).decode()

    cmd = f"run-as {PKG} sh -c 'echo {b64} | base64 -d > files/datastore/MJPEG_settings.preferences_pb'"
    r = subprocess.run(["adb", "-s", device, "shell", cmd], capture_output=True, text=True)

    # Verify
    r2 = subprocess.run(
        ["adb", "-s", device, "shell", f"run-as {PKG} cat files/datastore/MJPEG_settings.preferences_pb"],
        capture_output=True
    )
    verify = r2.stdout.replace(b'\r\n', b'\n')
    ok = verify == data
    print(f"[Quality] scale={scale}% codec={'H264' if codec==1 else 'H265' if codec==2 else 'MJPEG'} → {'OK' if ok else 'FAIL'}")

    if ok and restart:
        subprocess.run(["adb", "-s", device, "shell", "am", "force-stop", PKG],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        subprocess.run(["adb", "-s", device, "shell", "am", "start", "-n",
                       f"{PKG}/info.dvkr.screenstream.SingleActivity"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        # 自动点击"开始流"按钮 (坐标基于OnePlus NE2210)
        subprocess.run(["adb", "-s", device, "shell", "input", "tap", "540", "1944"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[Quality] ScreenStream已重启, 等待投屏启动...")
        time.sleep(3)
    return ok

if __name__ == '__main__':
    p = argparse.ArgumentParser(description='ScreenStream画质设置')
    p.add_argument('--device', '-d', required=True, help='ADB设备序列号')
    p.add_argument('--scale', '-s', type=int, default=25, choices=[25, 50, 75, 100], help='分辨率缩放百分比')
    p.add_argument('--no-restart', action='store_true', help='不重启ScreenStream')
    args = p.parse_args()
    set_quality(args.device, args.scale, restart=not args.no_restart)
