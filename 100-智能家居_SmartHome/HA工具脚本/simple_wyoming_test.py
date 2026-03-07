#!/usr/bin/env python3
"""
最简单的Wyoming测试
"""
import socket
import json
import time

def simple_test():
    """最基础的连接测试"""
    print("🔧 基础Wyoming连接测试")
    
    try:
        # 创建连接
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(('localhost', 10300))
        print("✅ TCP连接成功")
        
        # 尝试发送最简单的消息
        simple_msg = '{"type": "ping"}\n'
        print(f"📤 发送: {simple_msg.strip()}")
        sock.send(simple_msg.encode())
        
        # 等待响应
        time.sleep(1)
        try:
            response = sock.recv(1024)
            if response:
                print(f"📥 收到原始数据: {response}")
                try:
                    text = response.decode()
                    print(f"📥 解码文本: {text}")
                except:
                    print("📥 无法解码为文本")
            else:
                print("📥 未收到任何数据")
        except socket.timeout:
            print("📥 接收超时")
        
        sock.close()
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")

def protocol_test():
    """测试不同的协议格式"""
    print("\n🧪 测试不同协议格式")
    
    messages = [
        '{"type": "describe"}\n',
        '{"type": "info"}\n', 
        '{"type": "version"}\n',
        'describe\n',
        'info\n'
    ]
    
    for msg in messages:
        try:
            print(f"\n📤 测试消息: {msg.strip()}")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect(('localhost', 10300))
            
            sock.send(msg.encode())
            time.sleep(0.5)
            
            try:
                response = sock.recv(1024)
                if response:
                    print(f"✅ 有响应: {response[:100]}")
                else:
                    print("❌ 无响应")
            except socket.timeout:
                print("❌ 超时")
            
            sock.close()
            
        except Exception as e:
            print(f"❌ 错误: {e}")

if __name__ == "__main__":
    simple_test()
    protocol_test()

