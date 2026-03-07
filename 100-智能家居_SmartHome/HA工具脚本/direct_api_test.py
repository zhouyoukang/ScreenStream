#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接API测试 - 使用不同方法测试连接
"""

import subprocess
import json
import sys

def test_with_curl():
    """使用curl命令测试"""
    print("🔧 使用curl测试API连接")
    print("=" * 40)
    
    # 测试Node-RED
    print("📡 测试Node-RED...")
    try:
        result = subprocess.run([
            'curl', '-s', 'http://localhost:1880/flows'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            flows = json.loads(result.stdout)
            flow_count = len([f for f in flows if f.get("type") == "tab"])
            print(f"   ✅ Node-RED连接成功 - {flow_count}个流程")
            
            # 显示流程详情
            for flow in flows:
                if flow.get("type") == "tab":
                    print(f"      📋 {flow.get('label', '未命名流程')}")
        else:
            print(f"   ❌ Node-RED连接失败: {result.stderr}")
    except Exception as e:
        print(f"   ❌ Node-RED测试错误: {e}")
    
    print()
    
    # 测试Rhasspy
    print("🎙️ 测试Rhasspy...")
    try:
        result = subprocess.run([
            'curl', '-s', 'http://localhost:12101/api/profile'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            config = json.loads(result.stdout)
            print("   ✅ Rhasspy连接成功")
            print(f"      🗣️ 语音识别: {config.get('speech_to_text', {}).get('recommended', '未知')}")
            print(f"      🔊 语音合成: {config.get('text_to_speech', {}).get('recommended', '未知')}")
            print(f"      🎯 意图识别: {config.get('intent', {}).get('recommended', '未知')}")
        else:
            print(f"   ❌ Rhasspy连接失败: {result.stderr}")
    except Exception as e:
        print(f"   ❌ Rhasspy测试错误: {e}")

def test_device_control():
    """测试设备控制功能（模拟）"""
    print("\n🏠 智能设备控制演示")
    print("=" * 40)
    
    devices = [
        {"name": "床底灯", "icon": "💡", "actions": ["开启", "关闭", "切换"]},
        {"name": "音乐播放器", "icon": "🎵", "actions": ["播放", "暂停", "停止"]},
        {"name": "豆包AI", "icon": "🤖", "actions": ["启动", "停止"]},
        {"name": "KimiAI", "icon": "🧠", "actions": ["启动", "停止"]},
        {"name": "功率监控", "icon": "⚡", "actions": ["查看状态", "节能模式"]}
    ]
    
    for device in devices:
        print(f"\n{device['icon']} {device['name']}:")
        for action in device['actions']:
            print(f"   ✅ {action} - 命令已发送")

def create_usage_examples():
    """创建使用示例"""
    print("\n📚 使用示例")
    print("=" * 40)
    
    examples = [
        {
            "场景": "早晨起床",
            "操作": [
                "开启床底灯 (柔和亮度)",
                "播放轻音乐",
                "启动AI助手",
                "语音提醒: 早上好"
            ]
        },
        {
            "场景": "晚间休息", 
            "操作": [
                "检查功率使用情况",
                "关闭非必要设备",
                "渐进调暗灯光",
                "播放白噪音"
            ]
        },
        {
            "场景": "语音控制",
            "操作": [
                "说: '开灯' → 床底灯开启",
                "说: '播放音乐' → 音乐开始播放", 
                "说: '晚安' → 执行睡眠模式",
                "说: '节能模式' → 关闭高功耗设备"
            ]
        }
    ]
    
    for example in examples:
        print(f"\n🎭 {example['场景']}:")
        for i, action in enumerate(example['操作'], 1):
            print(f"   {i}. {action}")

def show_api_endpoints():
    """显示可用的API端点"""
    print("\n🔌 可用API端点")
    print("=" * 40)
    
    endpoints = {
        "Node-RED": [
            "GET /flows - 获取所有流程",
            "POST /flows - 部署新流程",
            "GET /nodes - 获取已安装节点",
            "POST /nodes - 安装新节点"
        ],
        "Rhasspy": [
            "GET /api/profile - 获取配置",
            "POST /api/train - 训练模型",
            "POST /api/speech-to-text - 语音识别",
            "POST /api/text-to-speech - 语音合成",
            "POST /api/text-to-intent - 意图识别"
        ],
        "设备控制": [
            "床底灯: http://192.168.31.228:8080/{light_command}",
            "音乐播放: http://192.168.31.228:8080/{music_command}",
            "AI助手: http://192.168.31.228:8080/{ai_command}"
        ]
    }
    
    for service, apis in endpoints.items():
        print(f"\n📡 {service}:")
        for api in apis:
            print(f"   • {api}")

def main():
    """主函数"""
    print("🏠 智能家居系统API测试与演示")
    print("=" * 50)
    
    # 1. 测试API连接
    test_with_curl()
    
    # 2. 演示设备控制
    test_device_control()
    
    # 3. 显示使用示例
    create_usage_examples()
    
    # 4. 显示API端点
    show_api_endpoints()
    
    print("\n" + "=" * 50)
    print("🎉 演示完成！")
    print("\n💡 现在你可以:")
    print("   • 使用 python quick_control.py 进行命令行控制")
    print("   • 使用 python automation_examples.py demo 查看自动化场景")
    print("   • 直接调用API进行设备控制")
    print("   • 通过语音命令控制智能家居")

if __name__ == "__main__":
    main()

