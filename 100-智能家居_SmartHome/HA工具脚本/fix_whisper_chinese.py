#!/usr/bin/env python3
"""
修复Whisper中文识别问题
"""
import subprocess
import time
import os

def run_docker_cmd(cmd):
    """执行Docker命令"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "命令超时", 1

def test_whisper_config(name, model, language, extra_args=""):
    """测试不同的Whisper配置"""
    print(f"\n🧪 测试配置: {name}")
    print(f"   模型: {model}, 语言: {language}")
    
    # 停止现有容器
    run_docker_cmd('docker stop wyoming-whisper-test 2>/dev/null')
    run_docker_cmd('docker rm wyoming-whisper-test 2>/dev/null')
    
    # 启动新配置
    cmd = f'''docker run -d --name wyoming-whisper-test -p 10300:10300 -v "D:\\homeassistant\\wyoming-data:/data" rhasspy/wyoming-whisper --model {model} --language {language} {extra_args}'''
    
    stdout, stderr, code = run_docker_cmd(cmd)
    if code != 0:
        print(f"❌ 启动失败: {stderr}")
        return False
    
    print("⏳ 等待服务启动...")
    time.sleep(20)
    
    # 检查日志
    stdout, stderr, code = run_docker_cmd('docker logs wyoming-whisper-test')
    if "Ready" in stdout:
        print("✅ 服务启动成功")
        print("📋 日志摘要:")
        lines = stdout.split('\n')
        for line in lines[-5:]:
            if line.strip():
                print(f"   {line}")
        return True
    else:
        print("❌ 服务启动失败")
        print(f"📋 错误日志: {stdout}")
        return False

def main():
    print("🔧 开始修复Whisper中文识别问题...")
    
    # 测试配置列表
    configs = [
        ("Small模型+中文", "small", "zh"),
        ("Medium模型+中文", "medium", "zh"), 
        ("Small模型+自动", "small", "auto"),
        ("Tiny模型+中文", "tiny", "zh"),
        ("Small模型+英文", "small", "en", "--temperature 0.0"),
    ]
    
    for name, model, lang, *extra in configs:
        extra_args = extra[0] if extra else ""
        success = test_whisper_config(name, model, lang, extra_args)
        
        if success:
            print(f"\n🎯 找到可能的解决方案: {name}")
            print("请在Home Assistant中测试语音识别...")
            
            choice = input("\n这个配置效果如何？(好/差/继续测试): ").lower()
            if choice in ['好', 'good', 'y', 'yes']:
                print("🎉 问题解决！保持当前配置。")
                return
            elif choice in ['继续', 'continue', 'c']:
                continue
        
        print("继续测试下一个配置...")
    
    print("\n😞 所有配置都测试完了，可能需要更深入的调试...")
    print("💡 建议尝试:")
    print("1. 使用更大的模型 (large)")
    print("2. 调整音频采样率")
    print("3. 检查音频输入质量")

if __name__ == "__main__":
    main()

