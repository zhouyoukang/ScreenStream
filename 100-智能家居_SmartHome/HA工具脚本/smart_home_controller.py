#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能家居控制器 - 直接操作Node-RED和Rhasspy的API脚本
无需网页界面，直接通过代码控制所有智能家居设备
"""

import requests
import json
import time
from typing import Dict, Any, Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SmartHomeController:
    """智能家居控制器主类"""
    
    def __init__(self, nodered_url="http://localhost:1880", rhasspy_url="http://localhost:12101"):
        self.nodered_url = nodered_url
        self.rhasspy_url = rhasspy_url
        self.session = requests.Session()
        
    # ==================== Node-RED 控制方法 ====================
    
    def get_nodered_flows(self) -> Dict[str, Any]:
        """获取Node-RED所有流程"""
        try:
            response = self.session.get(f"{self.nodered_url}/flows")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取Node-RED流程失败: {e}")
            return {}
    
    def get_nodered_nodes(self) -> Dict[str, Any]:
        """获取Node-RED已安装节点"""
        try:
            response = self.session.get(f"{self.nodered_url}/nodes")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取Node-RED节点失败: {e}")
            return {}
    
    def deploy_nodered_flow(self, flow_data: Dict[str, Any]) -> bool:
        """部署新的Node-RED流程"""
        try:
            headers = {'Content-Type': 'application/json'}
            response = self.session.post(
                f"{self.nodered_url}/flows", 
                json=flow_data, 
                headers=headers
            )
            response.raise_for_status()
            logger.info("Node-RED流程部署成功")
            return True
        except Exception as e:
            logger.error(f"部署Node-RED流程失败: {e}")
            return False
    
    def install_nodered_node(self, module_name: str) -> bool:
        """安装Node-RED节点模块"""
        try:
            headers = {'Content-Type': 'application/json'}
            data = {"module": module_name}
            response = self.session.post(
                f"{self.nodered_url}/nodes", 
                json=data, 
                headers=headers
            )
            response.raise_for_status()
            logger.info(f"Node-RED节点 {module_name} 安装成功")
            return True
        except Exception as e:
            logger.error(f"安装Node-RED节点失败: {e}")
            return False
    
    # ==================== 智能设备控制 ====================
    
    def control_bedroom_light(self, action: str) -> bool:
        """
        控制床底灯
        :param action: "on" 开启, "off" 关闭, "toggle" 切换
        """
        try:
            # 这里可以直接发送HTTP请求到设备控制端点
            # 根据你的Node-RED流程，可能需要触发特定的HTTP端点
            logger.info(f"床底灯执行操作: {action}")
            
            # 示例：如果有HTTP端点可以直接控制
            # response = self.session.get(f"http://192.168.31.228:8080/bedroom_light_{action}")
            
            # 或者通过注入消息到Node-RED流程
            inject_data = {
                "payload": action,
                "topic": "bedroom_light_control"
            }
            
            # 这里需要根据实际的Node-RED流程ID来调整
            return self._inject_to_nodered_node("f418bed06a55c5fb", inject_data)
            
        except Exception as e:
            logger.error(f"控制床底灯失败: {e}")
            return False
    
    def control_music_player(self, action: str) -> bool:
        """
        控制三星网易云音乐播放
        :param action: "play", "pause", "stop"
        """
        try:
            logger.info(f"音乐播放器执行操作: {action}")
            
            # 根据你的Node-RED配置发送请求
            if action == "play":
                response = self.session.get("http://192.168.31.228:8080/trigger_that_fired")
            elif action == "pause":
                response = self.session.get("http://192.168.31.228:8080/trigger_that_fired")
            
            response.raise_for_status()
            logger.info("音乐播放器控制成功")
            return True
            
        except Exception as e:
            logger.error(f"控制音乐播放器失败: {e}")
            return False
    
    def control_ai_assistant(self, assistant: str, action: str) -> bool:
        """
        控制AI助手
        :param assistant: "doubao" 豆包, "kimi" kimi
        :param action: "start", "stop"
        """
        try:
            logger.info(f"AI助手 {assistant} 执行操作: {action}")
            
            if assistant == "doubao":
                response = self.session.get("http://192.168.31.228:8080/doubao")
            elif assistant == "kimi":
                response = self.session.get("http://192.168.31.228:8080/kimi")
            
            response.raise_for_status()
            logger.info(f"AI助手 {assistant} 控制成功")
            return True
            
        except Exception as e:
            logger.error(f"控制AI助手失败: {e}")
            return False
    
    def monitor_power_usage(self) -> Optional[float]:
        """监控功率使用情况"""
        try:
            # 这里需要通过Node-RED的API获取功率传感器数据
            # 或者直接访问Home Assistant的API
            flows = self.get_nodered_flows()
            
            # 查找功率监控节点的当前值
            for flow in flows:
                if flow.get("type") == "api-current-state" and "total_power_usage" in str(flow):
                    logger.info("正在获取功率使用情况...")
                    # 这里可以获取实际的功率数据
                    return 450.0  # 示例值
            
            return None
            
        except Exception as e:
            logger.error(f"监控功率使用失败: {e}")
            return None
    
    # ==================== Rhasspy 语音控制 ====================
    
    def get_rhasspy_config(self) -> Dict[str, Any]:
        """获取Rhasspy配置"""
        try:
            response = self.session.get(f"{self.rhasspy_url}/api/profile")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取Rhasspy配置失败: {e}")
            return {}
    
    def train_rhasspy(self) -> bool:
        """训练Rhasspy模型"""
        try:
            response = self.session.post(f"{self.rhasspy_url}/api/train")
            response.raise_for_status()
            logger.info("Rhasspy模型训练开始")
            return True
        except Exception as e:
            logger.error(f"训练Rhasspy模型失败: {e}")
            return False
    
    def speech_to_text(self, audio_file: str) -> Optional[str]:
        """语音转文字"""
        try:
            with open(audio_file, 'rb') as f:
                headers = {'Content-Type': 'audio/wav'}
                response = self.session.post(
                    f"{self.rhasspy_url}/api/speech-to-text",
                    data=f,
                    headers=headers
                )
                response.raise_for_status()
                result = response.json()
                return result.get('text', '')
        except Exception as e:
            logger.error(f"语音转文字失败: {e}")
            return None
    
    def text_to_intent(self, text: str) -> Optional[Dict[str, Any]]:
        """文字转意图识别"""
        try:
            response = self.session.post(
                f"{self.rhasspy_url}/api/text-to-intent",
                data=text,
                headers={'Content-Type': 'text/plain'}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"意图识别失败: {e}")
            return None
    
    def speak_text(self, text: str) -> bool:
        """文字转语音播放"""
        try:
            response = self.session.post(
                f"{self.rhasspy_url}/api/text-to-speech",
                data=text,
                headers={'Content-Type': 'text/plain'}
            )
            response.raise_for_status()
            logger.info(f"语音播放: {text}")
            return True
        except Exception as e:
            logger.error(f"文字转语音失败: {e}")
            return False
    
    # ==================== 辅助方法 ====================
    
    def _inject_to_nodered_node(self, node_id: str, data: Dict[str, Any]) -> bool:
        """向特定Node-RED节点注入数据"""
        try:
            # 这个方法需要根据Node-RED的具体API实现
            # 可能需要使用WebSocket或特定的注入端点
            logger.info(f"向节点 {node_id} 注入数据: {data}")
            return True
        except Exception as e:
            logger.error(f"注入数据到Node-RED节点失败: {e}")
            return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统整体状态"""
        status = {
            "nodered_connected": False,
            "rhasspy_connected": False,
            "flows_count": 0,
            "nodes_count": 0,
            "power_usage": None
        }
        
        try:
            # 检查Node-RED连接
            flows = self.get_nodered_flows()
            if flows:
                status["nodered_connected"] = True
                status["flows_count"] = len([f for f in flows if f.get("type") == "tab"])
            
            # 检查Rhasspy连接
            config = self.get_rhasspy_config()
            if config:
                status["rhasspy_connected"] = True
            
            # 获取功率使用情况
            status["power_usage"] = self.monitor_power_usage()
            
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
        
        return status

# ==================== 使用示例和快捷功能 ====================

def main():
    """主函数 - 演示各种控制功能"""
    controller = SmartHomeController()
    
    print("🏠 智能家居控制器启动")
    print("=" * 50)
    
    # 获取系统状态
    status = controller.get_system_status()
    print(f"📊 系统状态:")
    print(f"  Node-RED: {'✅ 已连接' if status['nodered_connected'] else '❌ 未连接'}")
    print(f"  Rhasspy: {'✅ 已连接' if status['rhasspy_connected'] else '❌ 未连接'}")
    print(f"  流程数量: {status['flows_count']}")
    print(f"  功率使用: {status['power_usage']}W" if status['power_usage'] else "  功率使用: 未知")
    print()
    
    # 演示设备控制
    print("🔧 设备控制演示:")
    
    # 控制床底灯
    print("💡 控制床底灯...")
    controller.control_bedroom_light("on")
    time.sleep(2)
    controller.control_bedroom_light("off")
    
    # 控制音乐播放器
    print("🎵 控制音乐播放器...")
    controller.control_music_player("play")
    
    # 启动AI助手
    print("🤖 启动AI助手...")
    controller.control_ai_assistant("doubao", "start")
    
    # 语音功能演示
    print("🎙️ 语音功能演示:")
    controller.speak_text("智能家居系统启动完成")
    
    print("✅ 演示完成！")

if __name__ == "__main__":
    main()

