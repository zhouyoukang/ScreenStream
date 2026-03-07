#!/usr/bin/env python3
"""
简单的Wyoming语音识别测试
"""
import socket
import json
import wave
import sys
import os

def test_wyoming_transcription(audio_file, host="localhost", port=10300):
    """测试Wyoming语音转录功能"""
    print(f"🎵 测试音频文件: {audio_file}")
    
    if not os.path.exists(audio_file):
        print(f"❌ 文件不存在: {audio_file}")
        return False
    
    try:
        # 读取音频文件信息
        with wave.open(audio_file, 'rb') as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
            sample_rate = wav_file.getframerate()
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            
        print(f"📋 音频信息: {sample_rate}Hz, {channels}声道, {sample_width*8}位")
        print(f"📊 数据大小: {len(frames)} 字节")
        
        # 连接到Wyoming服务
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        print(f"✅ 连接到Wyoming服务 {host}:{port}")
        
        # 发送转录请求
        request = {
            "type": "transcribe", 
            "data": {
                "rate": sample_rate,
                "width": sample_width,
                "channels": channels
            }
        }
        
        message = json.dumps(request) + "\n"
        sock.send(message.encode())
        print("📤 发送转录请求")
        
        # 发送音频数据 (简化版本)
        chunk_size = 1024
        for i in range(0, len(frames), chunk_size):
            chunk = frames[i:i+chunk_size]
            sock.send(chunk)
        
        print("📤 音频数据发送完成")
        
        # 发送结束标记
        end_message = json.dumps({"type": "transcribe", "data": None}) + "\n"
        sock.send(end_message.encode())
        
        # 接收响应
        sock.settimeout(10)
        response_data = b""
        
        try:
            while True:
                data = sock.recv(1024)
                if not data:
                    break
                response_data += data
                
                # 尝试解析JSON响应
                try:
                    lines = response_data.decode().strip().split('\n')
                    for line in lines:
                        if line:
                            response = json.loads(line)
                            print(f"📥 服务响应: {response}")
                            if 'text' in response:
                                print(f"🗣️ 识别结果: '{response['text']}'")
                                return True
                except json.JSONDecodeError:
                    continue
                    
        except socket.timeout:
            print("⏰ 等待响应超时")
        
        sock.close()
        return False
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_wyoming_info(host="localhost", port=10300):
    """测试Wyoming服务信息"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        
        # 发送info请求
        request = {"type": "info"}
        message = json.dumps(request) + "\n"
        sock.send(message.encode())
        
        # 接收响应
        sock.settimeout(5)
        response = sock.recv(4096).decode()
        
        print(f"📋 服务信息响应: {response}")
        
        sock.close()
        return True
        
    except Exception as e:
        print(f"❌ 获取服务信息失败: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Wyoming 简单测试开始")
    print("=" * 40)
    
    print("\n1️⃣ 获取服务信息")
    test_wyoming_info()
    
    # 测试音频文件
    test_files = [
        "test_tone.wav",
        "test_silence.wav"
    ]
    
    for i, audio_file in enumerate(test_files, 2):
        print(f"\n{i}️⃣ 测试音频: {audio_file}")
        success = test_wyoming_transcription(audio_file)
        if success:
            print("✅ 测试成功")
        else:
            print("❌ 测试失败")
    
    print("\n🏁 测试完成")

