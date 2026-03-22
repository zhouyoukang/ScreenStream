"""VP99 VNC连接器 — 验证VNC握手 + 通过VNC远程开启ADB"""
import socket
import time
import sys

def vnc_handshake(ip, port=5900):
    """VNC协议握手验证"""
    print(f"Connecting to {ip}:{port}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    s.connect((ip, port))

    # Step 1: 接收服务端版本
    banner = s.recv(1024)
    print(f"Server banner: {banner}")

    if b'RFB' not in banner:
        print(f"Not a VNC server: {banner[:50]}")
        s.close()
        return None

    version = banner.decode('ascii', errors='ignore').strip()
    print(f"VNC version: {version}")

    # Step 2: 发送客户端版本
    s.send(b'RFB 003.008\n')
    time.sleep(0.5)

    # Step 3: 接收安全类型
    sec = s.recv(1024)
    print(f"Security data: {sec.hex()} ({len(sec)} bytes)")

    if len(sec) > 0:
        num_types = sec[0]
        print(f"Security types available: {num_types}")
        sec_names = {0: 'Invalid', 1: 'None', 2: 'VNC Auth', 16: 'Tight', 30: 'Apple ARD'}
        types = []
        for i in range(1, min(num_types + 1, len(sec))):
            st = sec[i]
            name = sec_names.get(st, f'Unknown({st})')
            print(f"  Type {st}: {name}")
            types.append(st)

        # Step 4: 如果支持无密码认证(Type 1=None)，直接连接
        if 1 in types:
            print("\nNo authentication required! Selecting type 1...")
            s.send(bytes([1]))
            time.sleep(0.5)
            result = s.recv(1024)
            print(f"Auth result: {result.hex()}")
            if len(result) >= 4 and result[:4] == b'\x00\x00\x00\x00':
                print("Authentication SUCCESS!")

                # Step 5: 发送ClientInit (shared=1)
                s.send(bytes([1]))  # shared flag
                time.sleep(0.5)

                # Step 6: 接收ServerInit (屏幕尺寸等)
                server_init = s.recv(4096)
                if len(server_init) >= 24:
                    width = int.from_bytes(server_init[0:2], 'big')
                    height = int.from_bytes(server_init[2:4], 'big')
                    bpp = server_init[4]
                    depth = server_init[5]
                    name_len = int.from_bytes(server_init[20:24], 'big')
                    name = server_init[24:24+name_len].decode('utf-8', errors='ignore') if name_len > 0 else ''
                    print(f"\nVNC Server Info:")
                    print(f"  Screen: {width}x{height}")
                    print(f"  BPP: {bpp}, Depth: {depth}")
                    print(f"  Name: '{name}'")
                    s.close()
                    return {'width': width, 'height': height, 'bpp': bpp, 'name': name, 'ip': ip}
            else:
                print(f"Auth failed: {result.hex()}")
        elif 2 in types:
            print("\nVNC password required.")
            print("DroidVNC-NG default: no password or 'droidvnc'")
        else:
            print(f"\nUnknown auth types: {types}")

    s.close()
    return None


if __name__ == '__main__':
    ip = sys.argv[1] if len(sys.argv) > 1 else '192.168.31.41'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5900
    result = vnc_handshake(ip, port)
    if result:
        print(f"\n=== VP99 VNC Connected! ===")
        print(f"Screen: {result['width']}x{result['height']}")
        print(f"Name: {result['name']}")
        print(f"IP: {result['ip']}")
    else:
        print("\nVNC connection failed")
