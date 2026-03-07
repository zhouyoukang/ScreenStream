#!/usr/bin/env python
"""
简易API服务器，提供与OpenAI兼容的API接口
支持与ha_openai集成，实现本地API服务
"""
import os
import sys
import json
import uuid
import time
import logging
import threading
import requests
import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('simple_api_server.log')
    ]
)
logger = logging.getLogger(__name__)

# 定义路径
MIGPT_EASY_PATH = Path("migpt-easy")
MIGPT_EASY_CONFIG = MIGPT_EASY_PATH / "config.json"
HA_CONFIG_PATH = Path("config") / "migpt" / "data" / "migpt_config.json"

# 默认配置
DEFAULT_CONFIG = {
    "api_server": {
        "enabled": "开启",
        "port": "5001",
        "host": "0.0.0.0",
        "cors_enabled": "开启",
        "rate_limit": "60"
    },
    "integrations": {
        "ha_openai": {
            "enabled": True,
            "endpoint": "http://localhost:5001/v1",
            "api_key": "sk-migpt-local-api-key"
        }
    }
}

# 全局变量
config = {}
ha_config = None
conversation_history = {}  # 用户ID到会话历史的映射
app = Flask(__name__)

def load_config() -> Dict:
    """从配置文件加载配置"""
    # 尝试从migpt-easy加载配置
    if MIGPT_EASY_CONFIG.exists():
        try:
            with open(MIGPT_EASY_CONFIG, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                logger.info("从migpt-easy加载配置成功")
                return config_data
        except Exception as e:
            logger.error(f"从migpt-easy加载配置失败: {e}")
    
    # 尝试从Home Assistant配置目录加载
    if HA_CONFIG_PATH.exists():
        try:
            with open(HA_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                logger.info("从Home Assistant配置目录加载配置成功")
                return config_data
        except Exception as e:
            logger.error(f"从Home Assistant配置目录加载配置失败: {e}")
    
    # 使用默认配置
    logger.warning("未找到配置文件，使用默认配置")
    return DEFAULT_CONFIG

def setup_cors(app):
    """设置CORS"""
    if config.get("homeassistant", {}).get("api_server", {}).get("cors_enabled", "开启") == "开启":
        CORS(app, resources={r"/*": {"origins": "*"}})
        logger.info("已启用CORS")

def send_ha_command(command, agent_id=None):
    """发送命令到Home Assistant"""
    if not ha_config or not ha_config.get("url") or not ha_config.get("token"):
        logger.error("Home Assistant配置不完整")
        return "Home Assistant配置不完整，无法执行命令"
    
    try:
        # 准备请求
        url = f"{ha_config['url']}/api/services/conversation/process"
        headers = {
            "Authorization": f"Bearer {ha_config['token']}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": command
        }
        
        # 如果指定了会话代理，则使用指定的代理
        if agent_id:
            payload["agent_id"] = agent_id
        # 否则使用配置中的默认代理
        elif ha_config.get("voice_agent_id"):
            payload["agent_id"] = ha_config["voice_agent_id"]
            
        logger.info(f"发送到Home Assistant的请求: {payload}")
        
        # 发送请求
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            logger.debug(f"Home Assistant响应: {result}")
            
            # 提取响应文本
            response_text = extract_response_text(result)
            if response_text:
                return response_text
            else:
                return "命令已执行，但Home Assistant没有返回响应文本"
        else:
            logger.error(f"Home Assistant返回错误: {response.status_code}, {response.text}")
            if response.status_code == 400:
                return f"命令格式不正确或无法被解析 ({response.status_code})"
            elif response.status_code == 401:
                return "Home Assistant令牌无效，请检查配置"
            else:
                return f"Home Assistant返回错误: {response.status_code}"
    except requests.exceptions.ConnectionError:
        logger.error("连接Home Assistant失败")
        return "无法连接到Home Assistant，请检查URL是否正确"
    except requests.exceptions.Timeout:
        logger.error("连接Home Assistant超时")
        return "连接Home Assistant超时，请检查网络"
    except Exception as e:
        logger.error(f"发送Home Assistant命令时出错: {e}")
        return f"发送命令时出错: {str(e)}"

def extract_response_text(response):
    """从Home Assistant的响应中提取文本"""
    try:
        if isinstance(response, list) and response:
            item = response[0]
            if isinstance(item, dict):
                if "speech" in item:
                    return item["speech"].get("plain", "")
                elif "response" in item:
                    return item["response"]
                else:
                    return str(item)
            else:
                return str(item)
        elif isinstance(response, dict):
            if "speech" in response:
                return response["speech"].get("plain", "")
            elif "response" in response:
                if isinstance(response["response"], dict) and "speech" in response["response"]:
                    return response["response"]["speech"].get("plain", "")
                else:
                    return str(response["response"])
            else:
                return str(response)
        else:
            return str(response)
    except Exception as e:
        logger.error(f"解析Home Assistant响应时出错: {e}")
        return str(response)

def send_tts_to_device(text, device_idx=0):
    """发送TTS到指定设备"""
    if not ha_config or not ha_config.get("url") or not ha_config.get("token"):
        logger.error("Home Assistant配置不完整")
        return False
        
    try:
        # 获取设备列表
        devices = get_device_list()
        
        if not devices or len(devices) <= device_idx:
            logger.error(f"设备索引无效: {device_idx}, 可用设备数: {len(devices)}")
            return False
            
        device = devices[device_idx]
        device_id = device.get("deviceID", "")
        
        if not device_id:
            logger.error("设备ID为空")
            return False
            
        # 确定设备类型并获取命令格式
        hardware = device.get("hardware", "")
        command = config.get("hardware_command_dict", {}).get(hardware, "5-1")
        
        # 准备TTS服务调用
        url = f"{ha_config['url']}/api/services/text_to_speech/xiaomi_tts"
        headers = {
            "Authorization": f"Bearer {ha_config['token']}",
            "Content-Type": "application/json"
        }
        payload = {
            "entity_id": f"text_to_speech.xiaomi_mina_tts",
            "message": text,
            "device": hardware,
            "method": command
        }
        
        logger.info(f"向设备 {device_id} ({hardware}) 发送TTS: '{text}'")
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info("TTS发送成功")
            return True
        else:
            logger.error(f"TTS发送失败: {response.status_code}, {response.text}")
            return False
    except Exception as e:
        logger.error(f"发送TTS时出错: {e}")
        return False

def get_device_list():
    """获取设备列表"""
    # 初始化一个虚拟设备列表，如果无法获取真实设备
    default_devices = [
        {"name": "小爱音箱Pro(虚拟)", "deviceID": "virtual_device_1", "hardware": "LX06"},
        {"name": "小爱音箱(虚拟)", "deviceID": "virtual_device_2", "hardware": "L05B"}
    ]
    
    try:
        if not ha_config or not ha_config.get("url") or not ha_config.get("token"):
            logger.warning("Home Assistant配置不完整，返回虚拟设备列表")
            return default_devices
            
        # 从Home Assistant获取设备列表
        url = f"{ha_config['url']}/api/states"
        headers = {
            "Authorization": f"Bearer {ha_config['token']}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"获取Home Assistant状态失败: {response.status_code}")
            return default_devices
            
        states = response.json()
        
        # 过滤Xiaomi TTS设备
        devices = []
        for state in states:
            entity_id = state.get("entity_id", "")
            if entity_id.startswith("text_to_speech.xiaomi_"):
                attributes = state.get("attributes", {})
                device_name = attributes.get("friendly_name", entity_id)
                device_id = entity_id.replace("text_to_speech.xiaomi_", "")
                
                # 尝试确定设备型号
                hardware = "LX06"  # 默认
                for key, value in config.get("hardware_command_dict", {}).items():
                    if key.lower() in device_id.lower():
                        hardware = key
                        break
                        
                devices.append({
                    "name": device_name,
                    "deviceID": device_id,
                    "hardware": hardware
                })
        
        # 如果找到设备，返回真实设备列表，否则返回默认列表
        return devices if devices else default_devices
    except Exception as e:
        logger.error(f"获取设备列表出错: {e}")
        return default_devices

def get_ai_response(text, user_id="default"):
    """获取AI回复"""
    if not config.get("api_key") or not config.get("api_base"):
        logger.error("API配置不完整")
        return "API配置不完整，无法获取AI回复"
    
    try:
        # 获取会话历史
        if user_id not in conversation_history:
            conversation_history[user_id] = []
        
        # 添加用户消息到会话历史
        conversation_history[user_id].append({"role": "user", "content": text})
        
        # 如果会话历史过长，保留最近的10轮对话
        if len(conversation_history[user_id]) > 20:
            conversation_history[user_id] = conversation_history[user_id][-20:]
        
        # 准备消息，包括系统提示
        messages = [{"role": "system", "content": config.get("prompt", "")}]
        messages.extend(conversation_history[user_id])
        
        # 根据API类型准备请求
        api_type = config.get("api_type", "openai")
        api_key = config.get("api_key", "")
        api_base = config.get("api_base", "")
        model_name = config.get("model_name", "")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 确定API端点
        if "/v1/chat/completions" in api_base:
            url = api_base
        else:
            url = f"{api_base.rstrip('/')}/v1/chat/completions"
        
        # 准备请求数据
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        logger.info(f"向{api_type}发送请求: '{text[:30]}...'")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"API返回错误: {response.status_code}, {response.text}")
            return f"API返回错误 ({response.status_code}): {response.text[:100]}"
            
        data = response.json()
        
        # 提取回复文本
        try:
            answer = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            logger.warning(f"无法从标准格式解析响应: {data}")
            
            # 尝试其他格式
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if isinstance(choice, dict):
                    for key in ["text", "content", "response"]:
                        if key in choice:
                            answer = choice[key]
                            break
                    else:
                        answer = str(choice)
                else:
                    answer = str(choice)
            else:
                return "API返回了无法解析的响应"
        
        # 添加AI回复到会话历史
        conversation_history[user_id].append({"role": "assistant", "content": answer})
        
        return answer
    except requests.exceptions.Timeout:
        logger.error("API请求超时")
        return "API请求超时，请稍后再试"
    except requests.exceptions.ConnectionError:
        logger.error("API连接错误")
        return "无法连接到API服务器，请检查网络和API基础URL"
    except Exception as e:
        logger.error(f"获取AI回复时出错: {e}")
        return f"获取AI回复时出错: {str(e)}"

@app.route('/', methods=['GET'])
def index():
    """API根路径"""
    return jsonify({
        "status": "online",
        "version": "1.0.0",
        "name": "MiGPT API Server",
        "description": "MiGPT API Server with OpenAI compatibility",
        "endpoints": [
            "/v1/chat/completions",
            "/v1/models",
            "/v1/health",
            "/v1/status"
        ],
        "integrations": {
            "ha_openai": config.get("integrations", {}).get("ha_openai", {}).get("enabled", False)
        }
    })

@app.route('/v1/models', methods=['GET'])
def models():
    """获取可用模型"""
    return jsonify({
        "object": "list",
        "data": [
            {
                "id": "gpt-3.5-turbo",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "migpt",
            },
            {
                "id": "gpt-4",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "migpt",
            }
        ]
    })

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    """处理聊天请求"""
    try:
        data = request.json
        
        # 提取请求参数
        model = data.get("model", "gpt-3.5-turbo")
        messages = data.get("messages", [])
        temperature = data.get("temperature", 0.7)
        max_tokens = data.get("max_tokens", 1000)
        stream = data.get("stream", False)
        
        # 验证消息
        if not messages:
            return jsonify({"error": "No messages provided"}), 400
        
        # 获取用户消息
        user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content")
                break
        
        if not user_message:
            return jsonify({"error": "No user message found"}), 400
        
        # 生成响应
        response_text = get_ai_response(user_message)
        
        # 处理流式响应
        if stream:
            def generate():
                msg_id = f"chatcmpl-{str(uuid.uuid4())[:8]}"
                created_time = int(time.time())
                
                # 发送开始事件
                yield f"data: {json.dumps({'id': msg_id, 'object': 'chat.completion.chunk', 'created': created_time, 'model': model, 'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"
                
                # 逐词发送
                words = response_text.split(' ')
                for i, word in enumerate(words):
                    chunk = {
                        'id': msg_id,
                        'object': 'chat.completion.chunk',
                        'created': created_time,
                        'model': model,
                        'choices': [{
                            'index': 0,
                            'delta': {'content': word + ' '},
                            'finish_reason': None if i < len(words) - 1 else 'stop'
                        }]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                    time.sleep(0.05)  # 添加延迟以模拟流式传输
                
                # 发送结束事件
                yield f"data: {json.dumps({'id': msg_id, 'object': 'chat.completion.chunk', 'created': created_time, 'model': model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
                yield "data: [DONE]\n\n"
            
            return Response(stream_with_context(generate()), content_type="text/event-stream")
        
        # 非流式响应
        resp = {
            "id": f"chatcmpl-{str(uuid.uuid4())[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(user_message) // 4,
                "completion_tokens": len(response_text) // 4,
                "total_tokens": (len(user_message) + len(response_text)) // 4
            }
        }
        return jsonify(resp)
    except Exception as e:
        logger.error(f"处理聊天请求时出错: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/v1/health', methods=['GET'])
def health():
    """健康检查端点"""
    return jsonify({"status": "ok"})

@app.route('/v1/status', methods=['GET'])
def status():
    """状态检查端点"""
    return jsonify({
        "status": "online",
        "uptime": int(time.time() - start_time),
        "version": "1.0.0",
        "requests": request_count,
        "integrations": {
            "ha_openai": config.get("integrations", {}).get("ha_openai", {}).get("enabled", False)
        }
    })

def start_server(host='0.0.0.0', port=5001):
    """启动服务器"""
    logger.info(f"正在启动API服务器，监听 {host}:{port}...")
    load_config()
    app.run(host=host, port=port, threaded=True)

def start_in_thread(host='0.0.0.0', port=5001):
    """在线程中启动服务器"""
    load_config()
    server_thread = threading.Thread(target=start_server, args=(host, port))
    server_thread.daemon = True
    server_thread.start()
    logger.info("API服务器已在后台线程中启动")
    return server_thread

def main():
    """主函数"""
    global config, start_time, request_count
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='简易API服务器')
    parser.add_argument('--host', type=str, help='监听主机')
    parser.add_argument('--port', type=int, help='监听端口')
    args = parser.parse_args()
    
    # 加载配置
    config = load_config()
    
    # 设置计数器和启动时间
    request_count = 0
    start_time = time.time()
    
    # 设置CORS
    setup_cors(app)
    
    # 获取主机和端口
    host = args.host or config.get("homeassistant", {}).get("api_server", {}).get("host", "0.0.0.0")
    port = args.port or int(config.get("homeassistant", {}).get("api_server", {}).get("port", 5001))
    
    # 启动服务器
    logger.info("====== MiGPT API服务器启动 ======")
    logger.info(f"正在启动API服务器，监听 {host}:{port}...")
    app.run(host=host, port=port)

if __name__ == "__main__":
    main() 