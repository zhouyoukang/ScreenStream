#!/usr/bin/env python3
"""
配置管理模块 - 负责加载、保存和管理MIGPT配置
"""
import json
import os
from pathlib import Path
import logging

# 设置日志
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_CONFIG = {
    # 日志控制
    "log_level": 1,  # 0=静默模式，1=基本信息，2=详细信息
    
    # 语言设置
    "language": "zh_CN",  # 可选: zh_CN(中文), en_US(英文), ja_JP(日文)
    
    # 多语言映射
    "language_map": {
        "zh_CN": {
            "ai_keywords": ["请", "帮我", "问一下", "AI"],
            "ui_texts": {
                "device_selection_title": "设备选择菜单",
                "device_selection_prompt": "请选择要使用的设备（输入设备编号，多个设备用逗号分隔，输入'all'选择所有设备）：",
                "device_selection_complete": "设备选择完成",
                "all_devices_selected": "已选择所有设备",
                "selected_devices": "已选择设备",
                "no_valid_devices": "未选择有效设备，使用默认设备",
                "input_format_error": "输入格式错误，使用默认设备",
                "command_prompt": "输入命令（回车继续，'选择设备'重新选择设备，'退出'结束程序）: ",
                "ai_mode_on": "AI回答模式已开启",
                "ai_mode_off": "AI回答模式已关闭",
                "ai_mode": "AI模式",
                "xiaomi_mode": "小爱模式",
                "ha_mode": "HomeAssistant模式",
                "error_timeout": "抱歉，AI回答超时，请稍后再试。",
                "error_general": "抱歉，AI回答出错，请稍后再试。"
            }
        },
        "en_US": {
            "ai_keywords": ["please", "help me", "ask", "AI"],
            "ui_texts": {
                "device_selection_title": "Device Selection Menu",
                "device_selection_prompt": "Select devices to use (enter device numbers separated by commas, or 'all' to select all devices):",
                "device_selection_complete": "Device selection completed",
                "all_devices_selected": "All devices selected",
                "selected_devices": "Selected devices",
                "no_valid_devices": "No valid devices selected, using default device",
                "input_format_error": "Input format error, using default device",
                "command_prompt": "Enter command (press Enter to continue, 'select' to choose devices, 'exit' to quit): ",
                "ai_mode_on": "AI response mode enabled",
                "ai_mode_off": "AI response mode disabled",
                "ai_mode": "AI mode",
                "xiaomi_mode": "Xiaomi mode",
                "ha_mode": "HomeAssistant mode",
                "error_timeout": "Sorry, AI response timed out. Please try again later.",
                "error_general": "Sorry, an error occurred with the AI response. Please try again later."
            }
        },
        "ja_JP": {
            "ai_keywords": ["お願い", "助けて", "質問", "AI"],
            "ui_texts": {
                "device_selection_title": "デバイス選択メニュー",
                "device_selection_prompt": "使用するデバイスを選択してください（デバイス番号をカンマ区切りで入力、または'all'ですべて選択）：",
                "device_selection_complete": "デバイス選択完了",
                "all_devices_selected": "すべてのデバイスが選択されました",
                "selected_devices": "選択されたデバイス",
                "no_valid_devices": "有効なデバイスが選択されていません、デフォルトのデバイスを使用します",
                "input_format_error": "入力形式エラー、デフォルトのデバイスを使用します",
                "command_prompt": "コマンドを入力（Enterで続行、'select'でデバイス選択、'exit'で終了）: ",
                "ai_mode_on": "AI応答モードが有効になりました",
                "ai_mode_off": "AI応答モードが無効になりました",
                "ai_mode": "AIモード",
                "xiaomi_mode": "Xiaomiモード",
                "ha_mode": "HomeAssistantモード",
                "error_timeout": "申し訳ありません、AI応答がタイムアウトしました。後でもう一度お試しください。",
                "error_general": "申し訳ありません、AI応答でエラーが発生しました。後でもう一度お試しください。"
            }
        }
    },
    
    # AI触发关键词
    "ai_keywords": ["请", "帮我", "问一下", "AI"],
    
    # API和配置常量
    "latest_ask_api": "https://userprofile.mina.mi.com/device_profile/v2/conversation?source=dialogu&hardware={hardware}&timestamp={timestamp}&limit=5",
    "cookie_template": "deviceId={device_id}; serviceToken={service_token}; userId={user_id}",
    
    # 音箱型号和命令映射
    "hardware_command_dict": {
        "LX06": "5-1",  # 小爱音箱Pro（黑色）
        "L05B": "5-3",  # 小爱音箱Play
        "S12A": "5-1",  # 小爱音箱
        "LX01": "5-1",  # 小爱音箱mini
        "L06A": "5-1",  # 小爱音箱
        "LX04": "5-1",  # 小爱触屏音箱
        "L05C": "5-3",  # 小爱音箱Play增强版
        "L17A": "7-3",  # 小爱音箱Sound Pro
        "X08E": "7-3",  # 红米小爱触屏音箱Pro
        "LX05A": "5-1",  # 小爱音箱遥控版（黑色）
        "LX5A": "5-1",  # 小爱音箱遥控版（黑色）
    },
    
    # 用户配置
    "mi_user": "",  # 小米账号（手机号）
    "mi_pass": "",  # 小米账号密码
    
    # ===== 通用AI API配置 =====
    # API类型选择："openai", "bigmodel", "custom"
    "api_type": "custom",  # 可选：openai, bigmodel, custom
    
    # 通用API配置
    "api_key": "",  # API密钥
    "api_base": "",  # API基础URL
    "model_name": "",  # 模型名称
    
    # 预设配置（可以快速切换）
    "api_presets": {
        "openai": {
            "api_type": "openai",
            "api_base": "https://api.openai.com/v1",
            "model": "gpt-3.5-turbo"
        },
        "bigmodel": {
            "api_type": "bigmodel", 
            "api_base": "https://open.bigmodel.cn/api/paas/v4",
            "model": "glm-4-flash"
        },
        "deepseek": {
            "api_type": "custom",
            "api_base": "https://api.deepseek.com/v1",
            "model": "deepseek-chat"
        },
        "moonshot": {
            "api_type": "custom",
            "api_base": "https://api.moonshot.cn/v1",
            "model": "moonshot-v1-8k"
        },
        "qwen": {
            "api_type": "custom",
            "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-turbo"
        },
        "claude": {
            "api_type": "custom",
            "api_base": "https://api.anthropic.com/v1",
            "model": "claude-3-haiku-20240307"
        },
        "volcengine": {
            "api_type": "custom",
            "api_base": "https://api.volcengine.com/v1",
            "model": "doubao-pro"
        },
        "siliconflow": {
            "api_type": "custom", 
            "api_base": "https://api.siliconflow.cn/v1",
            "model": "silicon-copilot-pro"
        },
        "qianfan": {
            "api_type": "custom",
            "api_base": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
            "model": "ernie-bot-4"
        }
    },
    
    # 音箱型号
    "sound_type": "LX06",
    
    # 是否跳过设备选择菜单
    "skip_device_selection": False,
    
    # 默认设备编号
    "device_numbers": "",
    
    # 全局变量
    "switch": True,  # 是否开启chatgpt回答
    "prompt": "请用自然、友好的语气回答，像朋友一样交流，避免过于机械的回复",  # 提示词
    
    # HomeAssistant配置
    "homeassistant": {
        "url": "",  # HomeAssistant服务器地址
        "token": "",  # HomeAssistant Token
        "text_entity_id": "",  # 文本指令实体ID
        "voice_agent_id": "",  # 语音API实体ID
        "ai_keywords": ["小周", "小洲", "小舟"],  # HAAI关键词
        "text_keywords": ["小爱"],  # HA文本指令关键词
        "api_server": {
            "enabled": "关闭",  # API服务器启用状态
            "port": "5001",  # API服务器端口
            "host": "0.0.0.0",  # API服务器主机
            "cors_enabled": "开启",  # CORS支持
            "rate_limit": "60"  # 速率限制
        }
    }
}


class Config:
    """配置管理类，处理配置的加载、保存和访问"""
    
    def __init__(self, config_file="config.json"):
        """
        初始化配置管理器
        
        Args:
            config_file (str): 配置文件名
        """
        self.config_file = config_file
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)
        self.config = self.load_config()
        
        # 应用预设配置
        self.apply_preset()
        
        # 验证配置
        self.validate_config()
    
    def load_config(self):
        """加载配置文件，如果不存在则创建默认配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # 递归合并配置（保留用户配置的同时确保所有默认配置字段存在）
                    merged_config = self._recursive_update(DEFAULT_CONFIG.copy(), user_config)
                    return merged_config
            else:
                # 创建默认配置文件
                self.save_config(DEFAULT_CONFIG)
                logger.info(f"已创建默认配置文件：{self.config_path}")
                return DEFAULT_CONFIG.copy()
        except Exception as e:
            logger.error(f"加载配置文件出错: {e}")
            return DEFAULT_CONFIG.copy()
    
    def _recursive_update(self, d, u):
        """递归更新字典，保持嵌套结构"""
        for k, v in u.items():
            if isinstance(v, dict) and isinstance(d.get(k), dict):
                d[k] = self._recursive_update(d[k], v)
            else:
                d[k] = v
        return d
    
    def save_config(self, config=None):
        """保存配置到文件"""
        if config is None:
            config = self.config
        
        try:
            # 确保配置文件目录存在
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            logger.info(f"配置已保存到 {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"保存配置文件出错: {e}")
            return False
    
    def apply_preset(self):
        """应用预设配置"""
        api_type = self.config.get("api_type")
        api_presets = self.config.get("api_presets", {})
        
        if api_type in api_presets:
            preset = api_presets[api_type]
            # 如果API配置为空或默认值，则使用预设值
            if not self.config.get("api_base") or self.config.get("api_base") == "your_api_base":
                self.config["api_base"] = preset["api_base"]
            if not self.config.get("model_name") or self.config.get("model_name") == "your_model_name":
                self.config["model_name"] = preset["model"]
    
    def validate_config(self):
        """验证配置是否有效"""
        # 检查音箱型号是否在列表中
        sound_type = self.config.get("sound_type")
        hardware_command_dict = self.config.get("hardware_command_dict", {})
        if sound_type and sound_type not in hardware_command_dict:
            logger.warning(f"{sound_type}不在支持的音箱型号列表中，请检查配置")
    
    def get(self, key, default=None):
        """获取配置项，支持多级键访问如'homeassistant.url'"""
        if '.' in key:
            parts = key.split('.')
            value = self.config
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            return value
        return self.config.get(key, default)
    
    def set(self, key, value):
        """设置配置项，支持多级键访问如'homeassistant.url'"""
        if '.' in key:
            parts = key.split('.')
            target = self.config
            for part in parts[:-1]:
                if part not in target:
                    target[part] = {}
                target = target[part]
            target[parts[-1]] = value
        else:
            self.config[key] = value
        return self.save_config()
    
    def __getitem__(self, key):
        """通过字典方式访问配置"""
        return self.get(key)
    
    def __setitem__(self, key, value):
        """通过字典方式设置配置"""
        self.set(key, value)
        
    def get_text(self, key, default=None):
        """
        获取当前语言的本地化文本
        
        Args:
            key (str): 文本键名
            default (str, optional): 默认值，如果找不到对应文本
            
        Returns:
            str: 本地化文本
        """
        language = self.get("language", "zh_CN")
        language_map = self.get("language_map", {})
        
        # 如果没有对应的语言映射，使用中文
        if language not in language_map:
            language = "zh_CN"
            
        # 获取当前语言的UI文本
        ui_texts = language_map.get(language, {}).get("ui_texts", {})
        
        # 返回对应的文本，如果没有则返回默认值
        return ui_texts.get(key, default if default is not None else key)
    
    def get_keywords(self):
        """
        获取当前语言的AI触发关键词
        
        Returns:
            list: 关键词列表
        """
        language = self.get("language", "zh_CN")
        language_map = self.get("language_map", {})
        
        # 如果有对应的语言映射，使用该语言的关键词
        if language in language_map:
            return language_map[language].get("ai_keywords", self.get("ai_keywords", []))
        
        # 否则使用默认关键词
        return self.get("ai_keywords", [])


# 创建全局配置实例
config = Config()

# 导出常用配置变量，方便直接导入使用
LOG_LEVEL = config.get("log_level")
MI_USER = config.get("mi_user")
MI_PASS = config.get("mi_pass")
API_TYPE = config.get("api_type")
API_KEY = config.get("api_key")
API_BASE = config.get("api_base")
MODEL_NAME = config.get("model_name")
SOUND_TYPE = config.get("sound_type")
HARDWARE_COMMAND_DICT = config.get("hardware_command_dict")
LATEST_ASK_API = config.get("latest_ask_api")
COOKIE_TEMPLATE = config.get("cookie_template")
SWITCH = config.get("switch")
PROMPT = config.get("prompt")