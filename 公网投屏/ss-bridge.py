#!/usr/bin/env python3
"""
ScreenStream H264 → Relay Server 桥接

从ScreenStream的 /stream/h264 WebSocket获取H264帧，
原样转发到中继服务器。帧格式完全一致，零转码。

同时将中继服务器收到的控制指令转发给ScreenStream的控制API。

用法: python ss-bridge.py [--phone IP:PORT] [--relay WS_URL] [--room ROOM] [--token TOKEN]
"""

import asyncio
import argparse
import json
import os
import struct
import subprocess
import sys
import time

try:
    import websockets
except ImportError:
    print("需要 websockets 库: pip install websockets")
    sys.exit(1)


# ─── ADB路径查找 ───
def _find_adb():
    """查找ADB可执行文件路径"""
    import shutil
    found = shutil.which("adb")
    if found:
        return found
    # 常见安装位置
    candidates = [
        os.path.join("D:\\platform-tools", "adb.exe"),
        os.path.join(os.environ.get("ANDROID_HOME", ""), "platform-tools", "adb.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk", "platform-tools", "adb.exe"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return "adb"  # fallback, hope it's in PATH

ADB = _find_adb()

# ─── 设备信息动态查询 ───
_device_resolution = (1080, 2412)  # fallback, updated by ADB query

def query_device_info(device):
    """通过ADB动态获取设备信息，替代硬编码"""
    global _device_resolution
    info = {"model": "Unknown", "manufacturer": "Unknown", "android": "?", "sdk": 0,
            "resolution": "1080x2412", "codec": "H264", "source": "ss-bridge"}
    props = {
        "model": "ro.product.model",
        "manufacturer": "ro.product.manufacturer",
        "android": "ro.build.version.release",
        "sdk": "ro.build.version.sdk",
    }
    for key, prop in props.items():
        try:
            r = subprocess.run([ADB, "-s", device, "shell", "getprop", prop],
                              capture_output=True, text=True, timeout=5)
            val = r.stdout.strip()
            if val:
                info[key] = int(val) if key == "sdk" else val
        except Exception:
            pass
    # 获取屏幕分辨率
    try:
        r = subprocess.run([ADB, "-s", device, "shell", "wm", "size"],
                          capture_output=True, text=True, timeout=5)
        # 输出格式: "Physical size: 1080x2412"
        for line in r.stdout.strip().splitlines():
            if 'size' in line.lower():
                res = line.split(':')[-1].strip()
                info["resolution"] = res
                w, h = res.split('x')
                _device_resolution = (int(w), int(h))
                break
    except Exception:
        pass
    return info


async def run_bridge(phone_host, relay_url, room, token, adb_device):
    relay_ws_url = f"{relay_url}?role=provider&token={token}&room={room}&type=phone"
    ss_ws_url = f"ws://{phone_host}/stream/h264"

    print(f"[Bridge] ScreenStream: {ss_ws_url}")
    print(f"[Bridge] Relay: {relay_ws_url}")

    # 动态查询设备信息
    print(f"[Bridge] 查询设备信息: {adb_device}")
    dev_info = query_device_info(adb_device)
    print(f"[Bridge] 设备: {dev_info['manufacturer']} {dev_info['model']} Android {dev_info['android']} {dev_info['resolution']}")

    # 连接中继服务器
    relay_ws = await websockets.connect(relay_ws_url, max_size=10*1024*1024)
    reg = await relay_ws.recv()
    print(f"[Bridge] 中继注册: {reg}")

    # 发送设备信息
    device_info = json.dumps({"type": "device_info", "data": dev_info})
    await relay_ws.send(device_info)

    # 连接ScreenStream H264流
    print(f"[Bridge] 连接ScreenStream...")
    ss_ws = await websockets.connect(ss_ws_url, max_size=10*1024*1024)
    print(f"[Bridge] ScreenStream已连接，开始转发")

    frame_count = 0
    total_bytes = 0
    start_time = time.time()

    async def forward_video():
        """ScreenStream → Relay（视频帧转发 + 流量整形）"""
        nonlocal frame_count, total_bytes
        # 流量整形: 控制发送速率，让ScreenStream ABR感知拥塞并自动降码率
        send_budget = 5_000_000  # 初始5MB预算,避免开头丢帧
        max_bytes_per_sec = 50_000_000  # 50MB/s - 270p帧极小,完全不限流
        last_budget_time = time.time()
        dropped_frames = 0

        async for message in ss_ws:
            if isinstance(message, bytes) and len(message) > 9:
                frame_type = message[0]

                # 更新发送预算
                now = time.time()
                elapsed = now - last_budget_time
                last_budget_time = now
                send_budget = min(send_budget + elapsed * max_bytes_per_sec, max_bytes_per_sec * 2)

                # Config和IDR帧始终发送（关键帧不能跳）
                if frame_type <= 1:
                    await relay_ws.send(message)
                    send_budget -= len(message)
                elif send_budget >= len(message):
                    # P帧：有预算才发
                    await relay_ws.send(message)
                    send_budget -= len(message)
                else:
                    # 预算不足，跳过P帧（让ScreenStream感知背压）
                    dropped_frames += 1
                    await asyncio.sleep(0.02)  # 20ms延迟让ScreenStream感知拥塞
                    continue

                frame_count += 1
                total_bytes += len(message)
                type_name = {0: 'Config', 1: 'IDR', 2: 'P'}.get(frame_type, '?')

                if frame_count <= 5 or frame_count % 100 == 0:
                    elapsed_total = time.time() - start_time
                    fps = frame_count / elapsed_total if elapsed_total > 0 else 0
                    drop_info = f" drop={dropped_frames}" if dropped_frames else ""
                    print(f"[Bridge] 帧#{frame_count} ({type_name}) {len(message)}B | "
                          f"总流量: {total_bytes//1024}KB | {fps:.1f}fps{drop_info}")
            elif isinstance(message, str):
                # ScreenStream发的JSON消息（如stats）
                try:
                    msg = json.loads(message)
                    if msg.get('type') != 'ping':
                        print(f"[Bridge] SS消息: {message[:100]}")
                except:
                    pass

    async def forward_control():
        """Relay → ADB（控制指令转为ADB命令）"""
        async for message in relay_ws:
            if isinstance(message, str):
                try:
                    msg = json.loads(message)
                    if msg.get('type') == 'set_quality':
                        # 画质切换: 修改DataStore + 重启ScreenStream
                        data = msg.get('data', {})
                        scale = data.get('scale', 25)
                        print(f"[Bridge] 画质切换: scale={scale}%")
                        from set_codec import set_quality
                        asyncio.get_event_loop().run_in_executor(
                            None, lambda: set_quality(adb_device, scale=scale, restart=True))
                    else:
                        handle_control(adb_device, msg)
                except Exception as e:
                    print(f"[Bridge] 控制错误: {e}")

    # 并行运行
    try:
        await asyncio.gather(forward_video(), forward_control())
    except websockets.ConnectionClosed as e:
        print(f"[Bridge] 连接关闭: {e}")
    except KeyboardInterrupt:
        print("\n[Bridge] 用户中断")
    finally:
        elapsed = time.time() - start_time
        print(f"[Bridge] 结束. {frame_count}帧 {total_bytes//1024}KB {elapsed:.0f}秒")
        await ss_ws.close()
        await relay_ws.close()


def handle_control(device, msg):
    """将中继服务器的控制指令转为ADB命令"""
    msg_type = msg.get('type', '')

    if msg_type == 'control':
        action = msg.get('data', {}).get('action', '')
        key_map = {
            'back': 'KEYCODE_BACK',
            'home': 'KEYCODE_HOME',
            'recents': 'KEYCODE_APP_SWITCH',
            'volume_up': 'KEYCODE_VOLUME_UP',
            'volume_down': 'KEYCODE_VOLUME_DOWN',
            'power': 'KEYCODE_POWER',
        }
        if action == 'notifications':
            subprocess.Popen([ADB, "-s", device, "shell", "cmd", "statusbar", "expand-notifications"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif action == 'quick_settings':
            subprocess.Popen([ADB, "-s", device, "shell", "cmd", "statusbar", "expand-settings"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif action == 'screenshot':
            # 截屏保存到手机
            subprocess.Popen([ADB, "-s", device, "shell", "screencap", "-p", "/sdcard/screenshot.png"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif action in key_map:
            subprocess.Popen([ADB, "-s", device, "shell", "input", "keyevent", key_map[action]],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  → 控制: {action}")

    elif msg_type == 'touch':
        data = msg.get('data', {})
        action = data.get('action', '')
        W, H = _device_resolution
        if action == 'tap':
            x, y = int(float(data.get('x', 0)) * W), int(float(data.get('y', 0)) * H)
            subprocess.Popen([ADB, "-s", device, "shell", "input", "tap", str(x), str(y)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"  → 点击: ({x}, {y})")
        elif action == 'swipe':
            x1 = int(float(data.get('fromX', 0)) * W)
            y1 = int(float(data.get('fromY', 0)) * H)
            x2 = int(float(data.get('toX', 0)) * W)
            y2 = int(float(data.get('toY', 0)) * H)
            dur = int(data.get('duration', 300))
            subprocess.Popen([ADB, "-s", device, "shell", "input", "swipe",
                            str(x1), str(y1), str(x2), str(y2), str(dur)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"  → 滑动: ({x1},{y1})→({x2},{y2}) {dur}ms")
        elif action == 'longpress':
            x, y = int(float(data.get('x', 0)) * W), int(float(data.get('y', 0)) * H)
            subprocess.Popen([ADB, "-s", device, "shell", "input", "swipe",
                            str(x), str(y), str(x), str(y), "800"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"  → 长按: ({x}, {y})")

    elif msg_type == 'text':
        text = msg.get('data', {}).get('text', '')
        if text:
            # ADB input text不支持中文，用广播发给ScreenStream的InputService
            subprocess.Popen([ADB, "-s", device, "shell", "am", "broadcast",
                            "-a", "ADB_INPUT_TEXT", "--es", "msg", text],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"  → 文字: {text}")

    elif msg_type == 'scroll':
        data = msg.get('data', {})
        x = int(float(data.get('x', 0.5)) * _device_resolution[0])
        y = int(float(data.get('y', 0.5)) * _device_resolution[1])
        dy = data.get('deltaY', 0)
        scroll_dist = 300 if dy > 0 else -300
        subprocess.Popen([ADB, "-s", device, "shell", "input", "swipe",
                        str(x), str(y), str(x), str(y + scroll_dist), "100"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  → 滚动: delta={dy}")

    elif msg_type == 'request_keyframe':
        pass  # ScreenStream自动发送IDR


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ScreenStream → Relay Bridge')
    parser.add_argument('--phone', '-p', default='localhost:8086', help='ScreenStream地址 (默认localhost:8086，需adb forward)')
    parser.add_argument('--relay', '-r', default='ws://localhost:9800', help='中继服务器')
    parser.add_argument('--room', default='phone', help='房间ID')
    parser.add_argument('--token', '-t', default='screenstream_2026', help='Token')
    parser.add_argument('--device', '-d', default='192.168.31.40:37501', help='ADB设备序列号')
    args = parser.parse_args()

    asyncio.run(run_bridge(args.phone, args.relay, args.room, args.token, args.device))
