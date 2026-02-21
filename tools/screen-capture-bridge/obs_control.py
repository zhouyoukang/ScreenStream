"""
OBS WebSocket 控制工具
- 停止/开始录制
- 查询录制状态
- 配合 setup_obs_split.py 使用

OBS 28+ 内置 WebSocket Server (默认端口4455)
需要在 OBS → 工具 → WebSocket服务器设置 中启用
"""
import sys
import json
import time
import hashlib
import base64
import struct

try:
    import websocket
except ImportError:
    print("需要安装: pip install websocket-client")
    sys.exit(1)

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 4455


def connect_obs(host=DEFAULT_HOST, port=DEFAULT_PORT, password=None, timeout=5):
    """连接OBS WebSocket"""
    url = f"ws://{host}:{port}"
    try:
        ws = websocket.create_connection(url, timeout=timeout)
        # 接收Hello消息
        hello = json.loads(ws.recv())
        if hello.get('op') != 0:
            print(f"意外的握手消息: {hello}")
            return None
        
        hello_data = hello.get('d', {})
        auth = hello_data.get('authentication')
        
        # 构建Identify消息
        identify = {"op": 1, "d": {"rpcVersion": 1}}
        
        if auth and password:
            # 需要认证
            challenge = auth['challenge']
            salt = auth['salt']
            secret = base64.b64encode(
                hashlib.sha256((password + salt).encode()).digest()
            ).decode()
            auth_string = base64.b64encode(
                hashlib.sha256((secret + challenge).encode()).digest()
            ).decode()
            identify['d']['authentication'] = auth_string
        elif auth and not password:
            print("OBS WebSocket需要密码认证，请用 --password 参数指定")
            ws.close()
            return None
        
        ws.send(json.dumps(identify))
        identified = json.loads(ws.recv())
        
        if identified.get('op') == 2:
            print(f"✅ 已连接OBS WebSocket ({url})")
            return ws
        else:
            print(f"认证失败: {identified}")
            ws.close()
            return None
            
    except Exception as e:
        print(f"❌ 无法连接OBS WebSocket ({url}): {e}")
        print("请确认: OBS → 工具 → WebSocket服务器设置 → 启用WebSocket服务器")
        return None


def send_request(ws, request_type, request_data=None):
    """发送OBS WebSocket请求"""
    msg = {
        "op": 6,
        "d": {
            "requestType": request_type,
            "requestId": f"req_{int(time.time()*1000)}",
        }
    }
    if request_data:
        msg['d']['requestData'] = request_data
    
    ws.send(json.dumps(msg))
    resp = json.loads(ws.recv())
    
    if resp.get('op') == 7:
        status = resp['d'].get('requestStatus', {})
        if status.get('result'):
            return resp['d'].get('responseData', {}), True
        else:
            return status, False
    return resp, False


def get_record_status(ws):
    """获取录制状态"""
    data, ok = send_request(ws, "GetRecordStatus")
    if ok:
        active = data.get('outputActive', False)
        duration = data.get('outputTimecode', '00:00:00')
        bytes_val = data.get('outputBytes', 0)
        size_mb = bytes_val / (1024*1024) if bytes_val else 0
        return {
            'recording': active,
            'duration': duration,
            'size_mb': round(size_mb, 1),
        }
    return None


def stop_recording(ws):
    """停止录制"""
    _, ok = send_request(ws, "StopRecord")
    return ok


def start_recording(ws):
    """开始录制"""
    _, ok = send_request(ws, "StartRecord")
    return ok


def main():
    import argparse
    parser = argparse.ArgumentParser(description='OBS WebSocket控制')
    parser.add_argument('action', choices=['status', 'stop', 'start', 'restart'],
                        help='操作: status/stop/start/restart')
    parser.add_argument('--host', default=DEFAULT_HOST)
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--password', default=None, help='WebSocket密码')
    args = parser.parse_args()
    
    ws = connect_obs(args.host, args.port, args.password)
    if not ws:
        sys.exit(1)
    
    try:
        if args.action == 'status':
            status = get_record_status(ws)
            if status:
                icon = "🔴" if status['recording'] else "⬜"
                print(f"{icon} 录制状态: {'录制中' if status['recording'] else '未录制'}")
                if status['recording']:
                    print(f"   时长: {status['duration']}")
                    print(f"   大小: {status['size_mb']} MB")
            else:
                print("无法获取录制状态")
        
        elif args.action == 'stop':
            status = get_record_status(ws)
            if status and status['recording']:
                print(f"当前正在录制 ({status['duration']}, {status['size_mb']}MB)")
                if stop_recording(ws):
                    print("✅ 录制已停止")
                else:
                    print("❌ 停止录制失败")
            else:
                print("当前未在录制")
        
        elif args.action == 'start':
            status = get_record_status(ws)
            if status and not status['recording']:
                if start_recording(ws):
                    print("✅ 录制已开始")
                else:
                    print("❌ 开始录制失败")
            else:
                print("当前已在录制中")
        
        elif args.action == 'restart':
            status = get_record_status(ws)
            if status and status['recording']:
                print(f"停止当前录制 ({status['duration']})...")
                stop_recording(ws)
                time.sleep(1)
            print("开始新录制...")
            if start_recording(ws):
                print("✅ 录制已重启")
            else:
                print("❌ 重启失败")
    
    finally:
        ws.close()


if __name__ == '__main__':
    main()
