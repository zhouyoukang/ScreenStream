#!/usr/bin/env python3
"""
直接测试Wyoming协议音频传输和识别
"""
import socket
import json
import wave
import struct
import numpy as np
import time

def create_test_audio():
    """创建一个简单的测试音频"""
    # 生成1秒的440Hz正弦波（A4音符）
    sample_rate = 16000
    duration = 1.0
    frequency = 440
    
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave_data = np.sin(2 * np.pi * frequency * t)
    
    # 转换为16位PCM
    wave_data = (wave_data * 32767).astype(np.int16)
    
    return wave_data.tobytes(), sample_rate

def create_speech_audio():
    """创建一个模拟语音的音频（多频率混合）"""
    sample_rate = 16000
    duration = 2.0
    
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # 混合多个频率模拟语音
    speech = (np.sin(2 * np.pi * 200 * t) * 0.3 +  # 基频
             np.sin(2 * np.pi * 400 * t) * 0.2 +   # 第一泛音
             np.sin(2 * np.pi * 600 * t) * 0.1 +   # 第二泛音
             np.random.normal(0, 0.05, len(t)))     # 噪音
    
    # 添加包络（模拟语音起伏）
    envelope = np.exp(-((t - duration/2) ** 2) / (2 * (duration/4) ** 2))
    speech = speech * envelope
    
    # 转换为16位PCM
    speech = (speech * 32767).astype(np.int16)
    
    return speech.tobytes(), sample_rate

def test_wyoming_protocol(audio_data, sample_rate, test_name):
    """测试Wyoming协议"""
    print(f"\n🧪 测试: {test_name}")
    print(f"📊 音频参数: {sample_rate}Hz, {len(audio_data)}字节")
    
    try:
        # 连接到Wyoming服务
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15)
        sock.connect(('localhost', 10300))
        print("✅ 连接成功")
        
        # 发送info请求
        info_request = {"type": "info"}
        sock.send((json.dumps(info_request) + "\n").encode())
        
        # 读取info响应
        try:
            response = sock.recv(4096).decode()
            print(f"📋 服务信息: {response.strip()}")
        except:
            print("⚠️ 未收到info响应")
        
        # 发送transcribe请求
        transcribe_request = {
            "type": "transcribe",
            "data": {
                "rate": sample_rate,
                "width": 2,  # 16位 = 2字节
                "channels": 1
            }
        }
        
        message = json.dumps(transcribe_request) + "\n"
        sock.send(message.encode())
        print("📤 发送transcribe请求")
        
        # 发送音频数据
        chunk_size = 1024
        bytes_sent = 0
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i+chunk_size]
            sock.send(chunk)
            bytes_sent += len(chunk)
        
        print(f"📤 音频数据发送完成: {bytes_sent}字节")
        
        # 发送结束标记
        end_request = {"type": "transcribe", "data": None}
        sock.send((json.dumps(end_request) + "\n").encode())
        print("📤 发送结束标记")
        
        # 等待响应
        print("⏳ 等待识别结果...")
        response_data = b""
        start_time = time.time()
        
        while time.time() - start_time < 10:  # 10秒超时
            try:
                data = sock.recv(1024)
                if not data:
                    break
                    
                response_data += data
                
                # 尝试解析响应
                try:
                    lines = response_data.decode().strip().split('\n')
                    for line in lines:
                        if line.strip():
                            response = json.loads(line)
                            print(f"📥 收到响应: {response}")
                            
                            if 'text' in response:
                                text = response['text']
                                if text:
                                    print(f"🗣️ 识别结果: '{text}'")
                                    return True
                                else:
                                    print("❌ 识别结果为空")
                                    return False
                            elif response.get('type') == 'transcript':
                                if 'text' in response:
                                    print(f"🗣️ 转录结果: '{response['text']}'")
                                    return True
                except json.JSONDecodeError:
                    continue
                except UnicodeDecodeError:
                    continue
                    
            except socket.timeout:
                continue
        
        print("⏰ 响应超时")
        return False
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False
    finally:
        try:
            sock.close()
        except:
            pass

def main():
    print("🔧 直接测试Wyoming协议音频识别")
    print("=" * 50)
    
    # 测试1: 简单音调
    audio1, rate1 = create_test_audio()
    result1 = test_wyoming_protocol(audio1, rate1, "440Hz音调测试")
    
    # 测试2: 模拟语音
    audio2, rate2 = create_speech_audio()
    result2 = test_wyoming_protocol(audio2, rate2, "模拟语音测试")
    
    # 测试3: 静音
    silence = b'\x00\x00' * 8000  # 1秒静音
    result3 = test_wyoming_protocol(silence, 16000, "静音测试")
    
    print("\n📊 测试结果总结:")
    print(f"   音调测试: {'✅ 成功' if result1 else '❌ 失败'}")
    print(f"   语音测试: {'✅ 成功' if result2 else '❌ 失败'}")
    print(f"   静音测试: {'✅ 成功' if result3 else '❌ 失败'}")
    
    if not any([result1, result2, result3]):
        print("\n🔍 所有测试都失败，可能的原因:")
        print("1. Wyoming协议实现问题")
        print("2. 音频格式不匹配") 
        print("3. Whisper模型内部错误")
        print("4. 服务配置问题")

if __name__ == "__main__":
    main()

