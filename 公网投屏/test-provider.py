"""
ScreenStream Relay - 测试Provider（模拟手机推流）

用法:
    python test-provider.py [--server ws://localhost:9800] [--token xxx] [--room test]

功能:
    1. 连接到中继服务器作为provider
    2. 生成合成H264帧（含SPS/PPS + IDR + P帧）
    3. 按30fps推送，模拟真实投屏
    4. 接收并处理viewer的控制指令
"""

import asyncio
import json
import struct
import time
import sys
import os

# 使用标准库websockets（如无则降级到纯socket）
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

# ─── 合成H264帧（用于测试，真实场景从MediaCodec获取）───
# 最小合法的H264 SPS/PPS + IDR帧，能让WebCodecs解码器接受

# Baseline Profile, Level 3.0, 320x240
FAKE_SPS = bytes([
    0x00, 0x00, 0x00, 0x01,  # Start code
    0x67,  # NAL type 7 (SPS)
    0x42, 0x00, 0x1e,  # Baseline profile, level 3.0
    0xe9, 0x40, 0x14, 0x04, 0xb4, 0x20,  # SPS data (320x240)
])

FAKE_PPS = bytes([
    0x00, 0x00, 0x00, 0x01,  # Start code
    0x68,  # NAL type 8 (PPS)
    0xce, 0x38, 0x80,  # PPS data
])

def make_config_frame():
    """生成SPS/PPS配置帧（type=0）"""
    data = FAKE_SPS + FAKE_PPS
    ts = int(time.time() * 1000000)
    # 帧格式: 1B type + 8B timestamp + data
    return struct.pack('>B', 0) + struct.pack('>q', ts) + data

def make_video_frame(is_key=False, frame_num=0):
    """生成模拟视频帧（type=1或2）"""
    frame_type = 1 if is_key else 2
    ts = int(time.time() * 1000000)

    # 生成一个最小的模拟NALU
    if is_key:
        # IDR帧 (NAL type 5)
        nal_data = bytes([0x00, 0x00, 0x00, 0x01, 0x65]) + bytes([0x88] * 100 + [frame_num % 256])
    else:
        # P帧 (NAL type 1)
        nal_data = bytes([0x00, 0x00, 0x00, 0x01, 0x41]) + bytes([0x9a] * 50 + [frame_num % 256])

    return struct.pack('>B', frame_type) + struct.pack('>q', ts) + nal_data

# ─── WebSocket Provider（使用websockets库）───
async def run_provider_ws(server_url, token, room_id):
    """使用websockets库连接中继"""
    url = f"{server_url}?role=provider&token={token}&room={room_id}&type=phone"
    print(f"[Provider] 连接: {url}")

    async with websockets.connect(url) as ws:
        # 等待注册确认
        resp = await ws.recv()
        msg = json.loads(resp)
        print(f"[Provider] 注册成功: {json.dumps(msg, indent=2)}")

        # 发送设备信息
        await ws.send(json.dumps({
            "type": "device_info",
            "data": {
                "model": "Test-Device",
                "android": "14",
                "resolution": "320x240",
                "codec": "H264 Baseline"
            }
        }))

        # 发送Config帧（SPS/PPS）
        config = make_config_frame()
        await ws.send(config)
        print(f"[Provider] 发送Config帧: {len(config)} bytes")

        # 推流循环
        frame_num = 0
        fps = 30
        interval = 1.0 / fps

        async def send_frames():
            nonlocal frame_num
            while True:
                is_key = (frame_num % 30 == 0)  # 每30帧一个关键帧

                if is_key:
                    # 关键帧前先发Config
                    await ws.send(make_config_frame())

                frame = make_video_frame(is_key=is_key, frame_num=frame_num)
                await ws.send(frame)

                if frame_num % 30 == 0:
                    print(f"[Provider] 帧#{frame_num} ({'IDR' if is_key else 'P'}) {len(frame)}B")

                frame_num += 1
                await asyncio.sleep(interval)

        async def recv_controls():
            async for message in ws:
                if isinstance(message, str):
                    msg = json.loads(message)
                    print(f"[Provider] 收到控制: {msg}")

                    if msg.get('type') == 'touch':
                        d = msg['data']
                        x = d.get('x', d.get('fromX', '?'))
                        y = d.get('y', d.get('fromY', '?'))
                        try:
                            print(f"  → 触控: {d.get('action')} ({float(x):.2f}, {float(y):.2f})")
                        except (ValueError, TypeError):
                            print(f"  → 触控: {d.get('action')} ({x}, {y})")
                    elif msg.get('type') == 'control':
                        print(f"  → 按键: {msg['data'].get('action')}")
                    elif msg.get('type') == 'text':
                        print(f"  → 文字: {msg['data'].get('text')}")
                    elif msg.get('type') == 'request_keyframe':
                        print(f"  → 请求关键帧")
                        await ws.send(make_config_frame())
                        await ws.send(make_video_frame(is_key=True, frame_num=frame_num))

        # 并行：发送帧 + 接收控制
        await asyncio.gather(send_frames(), recv_controls())

# ─── 纯Socket Provider（无第三方库降级方案）───
def run_provider_socket(server_url, token, room_id):
    """使用纯socket + HTTP升级，无第三方依赖"""
    import socket
    import hashlib
    import base64
    from urllib.parse import urlparse

    parsed = urlparse(server_url)
    host = parsed.hostname or 'localhost'
    port = parsed.port or 9800
    path = f"/?role=provider&token={token}&room={room_id}&type=phone"

    print(f"[Provider] 连接 {host}:{port}{path}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    # WebSocket握手
    key = base64.b64encode(os.urandom(16)).decode()
    handshake = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    )
    sock.send(handshake.encode())

    resp = sock.recv(4096)
    if b'101' not in resp:
        print(f"[Provider] 握手失败: {resp[:200]}")
        return

    print("[Provider] WebSocket握手成功")

    def ws_send_text(data):
        payload = data.encode('utf-8')
        _ws_send_frame(sock, payload, opcode=0x01)

    def ws_send_binary(data):
        _ws_send_frame(sock, data, opcode=0x02)

    def _ws_send_frame(sock, data, opcode=0x02):
        mask = os.urandom(4)
        length = len(data)

        frame = bytes([0x80 | opcode])  # FIN + opcode
        if length < 126:
            frame += bytes([0x80 | length])  # MASK + length
        elif length < 65536:
            frame += bytes([0x80 | 126]) + struct.pack('>H', length)
        else:
            frame += bytes([0x80 | 127]) + struct.pack('>Q', length)

        frame += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        frame += masked
        sock.sendall(frame)

    # 接收第一条消息（注册确认）
    sock.settimeout(5.0)
    try:
        raw = sock.recv(4096)
        # 简单解析WebSocket帧
        if len(raw) > 2:
            payload_start = 2
            length = raw[1] & 0x7F
            if length == 126:
                payload_start = 4
            elif length == 127:
                payload_start = 10
            payload = raw[payload_start:payload_start+length] if length < 126 else raw[payload_start:]
            print(f"[Provider] 服务器响应: {payload.decode('utf-8', errors='ignore')[:200]}")
    except socket.timeout:
        print("[Provider] 等待响应超时")

    sock.settimeout(0.01)  # 非阻塞接收

    # 推流
    frame_num = 0
    print("[Provider] 开始推流 (Ctrl+C 停止)")

    try:
        while True:
            is_key = (frame_num % 30 == 0)

            if is_key:
                ws_send_binary(make_config_frame())

            frame = make_video_frame(is_key=is_key, frame_num=frame_num)
            ws_send_binary(frame)

            if frame_num % 30 == 0:
                print(f"[Provider] 帧#{frame_num}")

            # 尝试接收控制消息
            try:
                data = sock.recv(4096)
                if data:
                    print(f"[Provider] 收到: {len(data)}B")
            except socket.timeout:
                pass

            frame_num += 1
            time.sleep(1.0 / 30)
    except KeyboardInterrupt:
        print("\n[Provider] 停止")
    finally:
        sock.close()

# ─── 主入口 ───
if __name__ == '__main__':
    server = 'ws://localhost:9800'
    token = 'screenstream_2026'
    room = 'test'

    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '--server' and i < len(sys.argv) - 1: server = sys.argv[i+1]
        elif arg == '--token' and i < len(sys.argv) - 1: token = sys.argv[i+1]
        elif arg == '--room' and i < len(sys.argv) - 1: room = sys.argv[i+1]

    print(f"ScreenStream Test Provider")
    print(f"  Server: {server}")
    print(f"  Room: {room}")
    print(f"  Token: {token[:4]}...")
    print()

    if HAS_WEBSOCKETS:
        print("[使用 websockets 库]")
        asyncio.run(run_provider_ws(server, token, room))
    else:
        print("[websockets库未安装, 使用纯socket降级模式]")
        print("  提示: pip install websockets 可获得更好体验")
        run_provider_socket(server, token, room)
