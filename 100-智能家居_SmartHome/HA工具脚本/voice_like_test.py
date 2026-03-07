#!/usr/bin/env python3
"""
创建更接近真实语音的音频测试
"""
import socket
import json
import numpy as np
import time

def create_voice_like_audio():
    """创建更接近人声的音频"""
    sample_rate = 16000
    duration = 3.0  # 3秒
    
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # 创建类似语音的复合波形
    # 基频 (类似男性声音)
    f0 = 150  # Hz
    
    # 添加多个谐波 (模拟人声的复杂性)
    voice = (np.sin(2 * np.pi * f0 * t) * 0.6 +          # 基频
             np.sin(2 * np.pi * f0 * 2 * t) * 0.3 +       # 第二谐波
             np.sin(2 * np.pi * f0 * 3 * t) * 0.2 +       # 第三谐波
             np.sin(2 * np.pi * f0 * 4 * t) * 0.1)        # 第四谐波
    
    # 添加调制 (模拟语音的变化)
    modulation = 1 + 0.3 * np.sin(2 * np.pi * 3 * t)  # 3Hz调制
    voice = voice * modulation
    
    # 添加包络 (模拟语音的起伏)
    envelope = np.exp(-0.5 * ((t - duration/2) / (duration/3))**2)
    voice = voice * envelope
    
    # 添加少量噪音 (模拟自然语音)
    noise = np.random.normal(0, 0.05, len(t))
    voice = voice + noise
    
    # 归一化和转换为16位PCM
    voice = voice / np.max(np.abs(voice)) * 0.8  # 避免削波
    audio_data = (voice * 32767).astype(np.int16).tobytes()
    
    return audio_data, sample_rate

def create_whistle_audio():
    """创建口哨声音频"""
    sample_rate = 16000
    duration = 2.0
    
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # 创建变化的口哨声 (800-1200Hz)
    freq = 800 + 400 * np.sin(2 * np.pi * 0.5 * t)  # 频率变化
    whistle = np.sin(2 * np.pi * freq * t)
    
    # 添加包络
    envelope = np.exp(-((t - duration/2) / (duration/2))**2)
    whistle = whistle * envelope * 0.7
    
    audio_data = (whistle * 32767).astype(np.int16).tobytes()
    return audio_data, sample_rate

def test_audio_recognition(audio_data, sample_rate, test_name):
    """测试音频识别"""
    print(f"\n🧪 测试: {test_name}")
    print(f"📊 音频: {len(audio_data)}字节, {sample_rate}Hz, {len(audio_data)//2//sample_rate:.1f}秒")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15)  # 增加超时时间
        sock.connect(('localhost', 10300))
        
        # 发送转录请求
        transcribe_request = {
            "type": "transcribe",
            "data": {
                "rate": sample_rate,
                "width": 2,
                "channels": 1,
                "language": "auto"  # 添加语言参数
            }
        }
        
        sock.send((json.dumps(transcribe_request) + '\n').encode())
        print("📤 发送转录请求（包含语言参数）")
        
        # 分块发送音频数据
        chunk_size = 4096
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i+chunk_size]
            sock.send(chunk)
            time.sleep(0.01)  # 稍微延迟模拟实时传输
        
        print("📤 音频数据发送完成")
        
        # 发送结束标记
        sock.send(b'{"type": "transcribe", "data": null}\n')
        print("📤 发送结束标记")
        
        # 等待结果
        print("⏳ 等待识别结果...")
        response_buffer = b""
        start_time = time.time()
        
        while time.time() - start_time < 12:
            try:
                data = sock.recv(1024)
                if not data:
                    print("📥 连接关闭")
                    break
                    
                response_buffer += data
                
                # 处理可能的多行响应
                while b'\n' in response_buffer:
                    line, response_buffer = response_buffer.split(b'\n', 1)
                    if line.strip():
                        try:
                            response = json.loads(line.decode())
                            print(f"📥 收到响应: {response}")
                            
                            # 检查识别结果
                            if 'text' in response:
                                if response['text']:
                                    print(f"🗣️ 识别结果: '{response['text']}'")
                                    return True
                                else:
                                    print("❌ 文本字段为空")
                                    
                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            print(f"📥 解析错误: {e}")
                            print(f"📥 原始数据: {line}")
                            
            except socket.timeout:
                print("⏳ 继续等待...")
                continue
                
        print("⏰ 等待超时")
        sock.close()
        return False
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    print("🔧 测试不同类型的音频识别")
    print("=" * 50)
    
    # 测试1: 类人声音频
    voice_audio, rate = create_voice_like_audio()
    result1 = test_audio_recognition(voice_audio, rate, "类人声音频")
    
    # 测试2: 口哨声
    whistle_audio, rate = create_whistle_audio()
    result2 = test_audio_recognition(whistle_audio, rate, "口哨声音频")
    
    print(f"\n📊 测试结果:")
    print(f"   类人声: {'✅ 成功' if result1 else '❌ 失败'}")
    print(f"   口哨声: {'✅ 成功' if result2 else '❌ 失败'}")
    
    if not result1 and not result2:
        print("\n🔍 所有测试都没有识别结果，可能的原因:")
        print("1. 音频质量/内容不符合识别要求")
        print("2. 模型配置问题 (温度、阈值等)")
        print("3. Wyoming协议参数错误")
        print("4. 需要真实的人声录音才能识别")

if __name__ == "__main__":
    main()

