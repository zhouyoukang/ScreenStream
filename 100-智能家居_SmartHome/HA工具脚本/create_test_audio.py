#!/usr/bin/env python3
"""
创建测试音频文件
"""
import wave
import numpy as np
import struct

def create_test_wav(filename, text_hint="测试音频"):
    """创建一个简单的测试WAV文件"""
    # 参数设置
    sample_rate = 16000  # Wyoming Whisper 推荐的采样率
    duration = 2  # 2秒
    frequency = 440  # A4音符
    
    # 生成正弦波
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave_data = np.sin(2 * np.pi * frequency * t)
    
    # 转换为16位整数
    wave_data = (wave_data * 32767).astype(np.int16)
    
    # 创建WAV文件
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # 单声道
        wav_file.setsampwidth(2)  # 16位
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(wave_data.tobytes())
    
    print(f"✅ 创建测试音频文件: {filename}")
    print(f"📋 文件信息: {duration}秒, {sample_rate}Hz, 单声道")
    return filename

def create_silence_wav(filename, duration=1):
    """创建静音WAV文件"""
    sample_rate = 16000
    frames = int(sample_rate * duration)
    
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        # 写入静音数据
        silent_data = b'\x00\x00' * frames
        wav_file.writeframes(silent_data)
    
    print(f"✅ 创建静音文件: {filename}")
    return filename

if __name__ == "__main__":
    # 创建测试文件
    create_test_wav("test_tone.wav", "音调测试")
    create_silence_wav("test_silence.wav", 2)
    print("🎵 测试音频文件创建完成")

