"""VP99 VNC远程开启ADB — 通过VNC协议自动化操控手表开启开发者选项和ADB调试"""
import socket
import struct
import time
import sys
import os

class VNCClient:
    """最小VNC客户端 — 支持截屏+点击+滑动"""

    def __init__(self, ip, port=5900):
        self.ip = ip
        self.port = port
        self.sock = None
        self.width = 0
        self.height = 0
        self.bpp = 0
        self.name = ''

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        self.sock.connect((self.ip, self.port))

        # Server version
        banner = self.sock.recv(1024)
        print(f"Server: {banner.strip()}")
        self.sock.send(b'RFB 003.008\n')
        time.sleep(0.3)

        # Security
        sec = self.sock.recv(1024)
        num = sec[0]
        types = list(sec[1:1+num])
        print(f"Auth types: {types}")

        if 1 in types:
            self.sock.send(bytes([1]))  # None auth
        else:
            raise Exception(f"No supported auth type. Available: {types}")

        time.sleep(0.3)
        result = self.sock.recv(1024)
        if result[:4] != b'\x00\x00\x00\x00':
            raise Exception(f"Auth failed: {result.hex()}")

        # ClientInit (shared)
        self.sock.send(bytes([1]))
        time.sleep(0.3)

        # ServerInit
        si = self.sock.recv(4096)
        self.width = struct.unpack('>H', si[0:2])[0]
        self.height = struct.unpack('>H', si[2:4])[0]
        self.bpp = si[4]
        name_len = struct.unpack('>I', si[20:24])[0]
        self.name = si[24:24+name_len].decode('utf-8', errors='ignore')
        print(f"Connected: {self.name} {self.width}x{self.height} {self.bpp}bpp")
        return True

    def screenshot(self, filename=None):
        """请求帧缓冲更新并保存为BMP"""
        # 设置像素格式 (32bit BGRA)
        fmt = struct.pack('>BBBBHHHBBBxxx', 0, 0, 0, 0, 32, 24, 0, 255, 255, 255)
        # SetPixelFormat: msg_type=0
        msg = bytes([0, 0, 0, 0]) + struct.pack('>BBBBHHHBBBxxx', 32, 24, 0, 1, 255, 255, 255, 16, 8, 0)
        self.sock.send(msg)
        time.sleep(0.1)

        # SetEncodings: msg_type=2, Raw encoding=0
        msg = struct.pack('>BBH', 2, 0, 1) + struct.pack('>i', 0)
        self.sock.send(msg)
        time.sleep(0.1)

        # FramebufferUpdateRequest: msg_type=3, incremental=0
        msg = struct.pack('>BBHHHH', 3, 0, 0, 0, self.width, self.height)
        self.sock.send(msg)

        # 接收帧数据
        self.sock.settimeout(15)
        try:
            # 等待FramebufferUpdate消息 (type=0)
            header = self._recv_exact(4)
            if header[0] != 0:
                print(f"Unexpected msg type: {header[0]}")
                return None

            num_rects = struct.unpack('>H', header[2:4])[0]
            print(f"Receiving {num_rects} rectangles...")

            pixels = bytearray(self.width * self.height * 4)
            for _ in range(num_rects):
                rect_hdr = self._recv_exact(12)
                x = struct.unpack('>H', rect_hdr[0:2])[0]
                y = struct.unpack('>H', rect_hdr[2:4])[0]
                w = struct.unpack('>H', rect_hdr[4:6])[0]
                h = struct.unpack('>H', rect_hdr[6:8])[0]
                enc = struct.unpack('>i', rect_hdr[8:12])[0]

                if enc == 0:  # Raw
                    data_len = w * h * (self.bpp // 8)
                    data = self._recv_exact(data_len)
                    # Copy to pixel buffer
                    for row in range(h):
                        src_off = row * w * 4
                        dst_off = ((y + row) * self.width + x) * 4
                        pixels[dst_off:dst_off + w*4] = data[src_off:src_off + w*4]
                else:
                    print(f"Unsupported encoding: {enc}")
                    return None

            # 保存为BMP
            if filename:
                self._save_bmp(filename, pixels)
                print(f"Screenshot saved: {filename}")
            return pixels

        except socket.timeout:
            print("Timeout waiting for frame data")
            return None

    def _recv_exact(self, n):
        data = bytearray()
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data.extend(chunk)
        return bytes(data)

    def _save_bmp(self, filename, pixels):
        """保存BGRA像素为BMP文件"""
        w, h = self.width, self.height
        row_size = w * 3
        padding = (4 - row_size % 4) % 4
        img_size = (row_size + padding) * h
        file_size = 54 + img_size

        with open(filename, 'wb') as f:
            # BMP Header
            f.write(b'BM')
            f.write(struct.pack('<I', file_size))
            f.write(b'\x00\x00\x00\x00')
            f.write(struct.pack('<I', 54))
            # DIB Header
            f.write(struct.pack('<I', 40))
            f.write(struct.pack('<i', w))
            f.write(struct.pack('<i', -h))  # top-down
            f.write(struct.pack('<HH', 1, 24))
            f.write(struct.pack('<I', 0))
            f.write(struct.pack('<I', img_size))
            f.write(b'\x00' * 16)
            # Pixel data (BGRA -> BGR)
            for y in range(h):
                for x in range(w):
                    off = (y * w + x) * 4
                    f.write(bytes([pixels[off], pixels[off+1], pixels[off+2]]))
                f.write(b'\x00' * padding)

    def click(self, x, y):
        """VNC鼠标点击"""
        # PointerEvent: msg_type=5, button_mask, x, y
        self.sock.send(struct.pack('>BBhh', 5, 1, x, y))  # press
        time.sleep(0.05)
        self.sock.send(struct.pack('>BBhh', 5, 0, x, y))  # release
        time.sleep(0.3)
        print(f"Clicked: ({x}, {y})")

    def swipe(self, x1, y1, x2, y2, steps=10, delay=0.02):
        """VNC滑动"""
        for i in range(steps + 1):
            t = i / steps
            x = int(x1 + (x2 - x1) * t)
            y = int(y1 + (y2 - y1) * t)
            self.sock.send(struct.pack('>BBhh', 5, 1, x, y))
            time.sleep(delay)
        self.sock.send(struct.pack('>BBhh', 5, 0, x2, y2))
        time.sleep(0.3)
        print(f"Swiped: ({x1},{y1}) -> ({x2},{y2})")

    def close(self):
        if self.sock:
            self.sock.close()


def main():
    ip = sys.argv[1] if len(sys.argv) > 1 else '192.168.31.41'
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'vp99_extracted', 'vnc_screenshots')
    os.makedirs(data_dir, exist_ok=True)

    vnc = VNCClient(ip)
    vnc.connect()

    # Step 1: 截取当前屏幕
    ts = time.strftime('%Y%m%d_%H%M%S')
    screenshot_path = os.path.join(data_dir, f'vnc_screen_{ts}.bmp')
    vnc.screenshot(screenshot_path)

    print(f"\nVP99 VNC Info:")
    print(f"  IP: {ip}")
    print(f"  Screen: {vnc.width}x{vnc.height}")
    print(f"  Name: {vnc.name}")
    print(f"  Screenshot: {screenshot_path}")

    vnc.close()


if __name__ == '__main__':
    main()
