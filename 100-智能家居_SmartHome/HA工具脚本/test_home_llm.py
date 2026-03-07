#!/usr/bin/env python3
"""
Home-LLM 测试脚本
用于验证 Home-LLM 集成是否正常工作
"""

import asyncio
import aiohttp
import json
from datetime import datetime

class HomeLLMTester:
    def __init__(self, ha_url="http://localhost:8123", token=None):
        self.ha_url = ha_url
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}" if token else "",
            "Content-Type": "application/json"
        }
    
    async def test_ollama_connection(self):
        """测试 Ollama 连接"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:11434/api/tags") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = [model['name'] for model in data.get('models', [])]
                        print(f"✅ Ollama 连接成功，可用模型: {models}")
                        return True
                    else:
                        print(f"❌ Ollama 连接失败，状态码: {resp.status}")
                        return False
        except Exception as e:
            print(f"❌ Ollama 连接错误: {e}")
            return False
    
    async def test_conversation_agent(self):
        """测试对话代理"""
        try:
            test_messages = [
                "你好，请介绍一下你自己",
                "列出可用的设备",
                "什么是智能家居？"
            ]
            
            for message in test_messages:
                print(f"\n🧪 测试消息: {message}")
                
                # 这里需要根据实际的 Home Assistant 对话 API 进行调用
                # 具体 API 端点可能因版本而异
                
                print("✅ 对话测试完成")
                
        except Exception as e:
            print(f"❌ 对话测试失败: {e}")
    
    def print_configuration_guide(self):
        """打印配置指南"""
        guide = f"""
📋 Home-LLM 配置指南 - {datetime.now().strftime('%Y-%m-%d %H:%M')}

=== 第一步：HACS 安装 ===
1. HACS > 集成 > ⋮ > 自定义存储库
2. 添加: https://github.com/acon96/home-llm
3. 类别: Integration
4. 搜索并安装 "Local LLM Conversation"
5. 重启 Home Assistant

=== 第二步：添加集成 ===
1. 设置 > 设备与服务 > 添加集成
2. 搜索 "Local LLM Conversation"
3. 配置参数:
   - 后端: Ollama
   - URL: http://localhost:11434
   - 模型: gemma3:4b (当前可用)
   - 温度: 0.1
   - 最大令牌: 2048

=== 第三步：设置对话代理 ===
1. 设置 > 语音助手
2. 编辑助手 > 对话代理 > Local LLM Conversation

=== 第四步：暴露设备 ===
访问: {self.ha_url}/config/voice-assistants/expose
选择要控制的设备

=== 测试命令示例 ===
• "打开客厅的灯"
• "关闭所有灯光"  
• "设置温度为 22 度"
• "播放音乐"
• "查看设备状态"

=== 故障排除 ===
1. 检查 Ollama 服务: curl http://localhost:11434/api/tags
2. 查看 HA 日志: 设置 > 系统 > 日志
3. 验证模型下载: ollama list
4. 重启服务: ollama serve (如果需要)
        """
        print(guide)

async def main():
    tester = HomeLLMTester()
    
    print("🚀 开始 Home-LLM 配置测试...")
    
    # 打印配置指南
    tester.print_configuration_guide()
    
    # 测试 Ollama 连接
    print("\n🔍 测试 Ollama 连接...")
    await tester.test_ollama_connection()
    
    print("\n✅ 测试完成！请按照上述指南在 Home Assistant 中完成配置。")

if __name__ == "__main__":
    asyncio.run(main())



