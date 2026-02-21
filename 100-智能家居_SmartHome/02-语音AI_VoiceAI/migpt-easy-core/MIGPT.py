#!/usr/bin/env python3
import asyncio
import json
import os
from http.cookies import SimpleCookie
from pathlib import Path
import threading
import time
from aiohttp import ClientSession
from minaservice import MiNAService
from miaccount import MiAccount
from requests.utils import cookiejar_from_dict
from V3 import Chatbot
import traceback
# 导入配置
from config import config, LOG_LEVEL, MI_USER, MI_PASS, API_TYPE, API_KEY, API_BASE, MODEL_NAME, SOUND_TYPE, HARDWARE_COMMAND_DICT, LATEST_ASK_API, COOKIE_TEMPLATE, SWITCH, PROMPT

# 判断是否应该使用AI助手来回答
def should_use_ai(text):
    """
    判断是否应该使用AI助手来回答
    只有当用户输入包含特定关键词时，才使用AI助手回答
    """
    # 使用多个关键词作为触发词
    ai_keywords = config.get_keywords()
    return any(keyword in text for keyword in ai_keywords)

# 判断是否应该使用HomeAssistant来处理
def should_use_ha(text):
    """
    判断是否应该使用HomeAssistant来处理
    只有当用户输入包含特定关键词时，才使用HomeAssistant处理
    """
    # 从配置中获取HomeAssistant关键词
    ha_config = config.get("homeassistant", {})
    ha_ai_keywords = ha_config.get("ai_keywords", [])
    ha_text_keywords = ha_config.get("text_keywords", [])
    
    # 检查是否包含任何HomeAssistant关键词
    return any(keyword in text for keyword in ha_ai_keywords + ha_text_keywords)

# 去掉用户输入中的关键词
def get_cleaned_input(text, keywords=None):
    """
    去掉用户输入中的关键词
    """
    # 如果没有提供关键词，使用AI关键词
    if keywords is None:
        keywords = config.get_keywords()
    
    cleaned_text = text
    for keyword in keywords:
        cleaned_text = cleaned_text.replace(keyword, "").strip()
    return cleaned_text

# 优化AI回答，使其更自然
def optimize_answer(answer):
    """
    优化AI回答，使其更自然
    """
    # 去除可能的多余标点
    answer = answer.replace("。。", "。").replace("，，", "，")
    
    # 去除开头的客套话
    common_starts = ["我是AI助手，", "作为AI助手，", "作为人工智能，"]
    for start in common_starts:
        if answer.startswith(start):
            answer = answer[len(start):]
    
    return answer.strip()

# 事件循环
try:
    # Python 3.10及以上版本使用get_running_loop
    loop = asyncio.get_running_loop()
except RuntimeError:
    # 如果没有运行中的事件循环，则创建一个新的
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# 解析cookie字符串
def parse_cookie_string(cookie_string):
    cookie = SimpleCookie()
    cookie.load(cookie_string)
    cookies_dict = {}
    cookiejar = None
    for k, m in cookie.items():
        cookies_dict[k] = m.value
        cookiejar = cookiejar_from_dict(cookies_dict, cookiejar=None, overwrite=True)
    return cookiejar


# 在MiGPT类中添加日志函数
class MiGPT:
    def __init__(self, hardware=SOUND_TYPE, use_command=False):
        self.mi_token_home = os.path.join(Path.home(), "." + MI_USER + ".mi.token")
        self.hardware = hardware
        self.cookie_string = ""
        self.last_timestamps = {}  # 每个设备的最后时间戳
        self.session = None
        self.chatbot = None  # a little slow to init we move it after xiaomi init
        self.user_id = ""
        self.device_id = ""
        self.service_token = ""
        self.cookie = ""
        self.use_command = use_command
        self.tts_command = HARDWARE_COMMAND_DICT.get(hardware, "5-1")
        self.conversation_id = None
        self.parent_id = None
        self.miboy_account = None
        self.mina_service = None
        self.conversation_history = []  # 对话历史列表
        self.history_file = "data/conversation_history.json"  # 对话历史文件
        self.selected_devices = []  # 已选择的设备列表
        self.device_cookies = {}  # 每个设备的cookie
        self.command_queue = asyncio.Queue()  # 命令队列
        self.running = True  # 运行标志
        self.devices = []  # 设备列表
        self.auto_process = True  # 默认自动处理设备输入
        self.log_level = LOG_LEVEL  # 日志级别
        self.show_api_logs = False  # 是否显示API请求日志，默认不显示
        
        # 确保历史记录目录存在
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        
        # 尝试加载历史对话
        self.load_conversation_history()
        
    def log_debug(self, message):
        """输出调试级别日志"""
        if 'https://api2.mina.mi.com/remote/ubus' in message and not self.show_api_logs:
            return
        if self.log_level >= 2:
            print(message)
            
    def log_info(self, message):
        """输出信息级别日志"""
        if 'https://api2.mina.mi.com/remote/ubus' in message and not self.show_api_logs:
            return
        if self.log_level >= 1:
            print(message)
            
    def log_important(self, message):
        """输出重要信息（始终显示）"""
        print(message)

    async def init_all_data(self, session):
        """
        初始化所有必要的数据，包括小米账号、小爱服务和聊天机器人
        """
        self.session = session
        
        # 检查账号和密码是否为空
        if not MI_USER or not MI_PASS:
            self.log_important("⚠️ 未配置小米账号或密码，小爱音箱功能将不可用")
            self.log_important("请使用 'config' 命令或启动配置界面设置账号")
            self.devices = []  # 设置为空列表
            return  # 直接返回，不进行后续初始化
            
        # 初始化小米账号
        self.miboy_account = MiAccount(session, MI_USER, MI_PASS, self.mi_token_home)
        # 强制登录刷新token
        login_success = await self.miboy_account.login("micoapi")
        
        if not login_success:
            self.log_important("⚠️ 小米账号登录失败，请检查账号密码或稍后再试")
            self.log_important("请尝试以下解决方案:")
            self.log_important("1. 确保账号密码正确")
            self.log_important("2. 在浏览器中访问 https://account.xiaomi.com 手动登录一次")
            self.log_important("3. 删除token文件后重启程序")
            
            # 检查token文件是否存在，如果存在则尝试删除
            if os.path.exists(self.mi_token_home):
                try:
                    os.remove(self.mi_token_home)
                    self.log_important(f"已删除token文件: {self.mi_token_home}")
                    self.log_important("请重启程序重试")
                except Exception as e:
                    self.log_info(f"删除token文件失败: {e}")
                    self.log_important(f"请手动删除token文件: {self.mi_token_home}")
            else:
                self.log_important("未找到token文件，可能是首次登录或已被删除")
                
            self.devices = []  # 设置为空列表
            return  # 直接返回，不进行后续初始化
            
        # 初始化小爱服务
        self.mina_service = MiNAService(self.miboy_account)
        
        # 获取设备列表
        self.devices = await self.mina_service.device_list()
        if not self.devices:
            self.log_important("⚠️ 未找到小爱音箱设备，请检查账号和网络")
            self.log_important("可能的原因:")
            self.log_important("1. 账号中没有绑定小爱设备")
            self.log_important("2. 网络连接问题")
            self.log_important("3. 小爱服务器暂时不可用")
            return
            
        print(f"找到 {len(self.devices)} 个小爱设备")
        for i, device in enumerate(self.devices):
            print(f"设备 {i+1}: {device.get('name', '未命名')} ({device.get('deviceID', 'unknown')})")
        
        # 设置设备ID为第一个设备
        for device in self.devices:
            if device.get("hardware", "") == self.hardware:
                self.device_id = device.get("deviceID")
                break
        else:
            # 如果没有找到指定型号，使用第一个设备
            if self.devices:
                self.device_id = self.devices[0].get("deviceID")
                print(f"未找到型号为 {self.hardware} 的设备，使用第一个设备: {self.devices[0].get('name')}")
        
        # 默认选择第一个设备
        if self.devices:
            self.selected_devices = [0]  # 默认选择第一个设备（索引为0）
            print(f"默认选择设备: {self.devices[0].get('name')}")
        
        # 检查是否需要跳过设备选择菜单
        skip_device_selection = config.get("skip_device_selection", False)
        device_numbers = config.get("device_numbers", "")
        
        if skip_device_selection:
            # 如果设置了设备编号，则使用指定的设备编号
            if device_numbers:
                await self.show_device_selection_menu(device_numbers)
            else:
                # 如果没有设置设备编号，则选择所有设备
                await self.show_device_selection_menu("all")
        else:
            # 显示设备选择菜单
            await self.show_device_selection_menu()
        
        # 从token文件中获取用户ID和服务token
        try:
            with open(self.mi_token_home) as f:
                user_data = json.loads(f.read())
            
            # 确保userId是数字格式的字符串
            self.user_id = str(user_data.get("userId"))
            self.service_token = user_data.get("micoapi")[1]
        except Exception as e:
            self.log_important(f"读取token文件失败: {e}")
            self.log_important("将尝试重新登录...")
            login_success = await self.miboy_account.login("micoapi")
            if not login_success:
                self.log_important("重新登录失败，无法继续")
                self.devices = []
                return
            
            # 重新尝试读取token文件
            try:
                with open(self.mi_token_home) as f:
                    user_data = json.loads(f.read())
                
                # 确保userId是数字格式的字符串
                self.user_id = str(user_data.get("userId"))
                self.service_token = user_data.get("micoapi")[1]
            except Exception as e:
                self.log_important(f"再次读取token文件失败: {e}")
                self.log_important("无法继续，请重启程序")
                self.devices = []
                return
        
        # 为每个选中的设备初始化cookie和时间戳
        for device_idx in self.selected_devices:
            device = self.devices[device_idx]
            device_id = device.get("deviceID")
            hardware = device.get("hardware", "")
            
            # 初始化cookie
            cookie_string = COOKIE_TEMPLATE.format(
                device_id=device_id,
                service_token=self.service_token,
                user_id=self.user_id,
            )
            self.device_cookies[device_id] = parse_cookie_string(cookie_string)
            self.last_timestamps[device_id] = 0
            
            # 获取初始数据
            data = await self.get_latest_ask_from_xiaoai(device_id, hardware)
            if data:
                timestamp, _ = self.get_last_timestamp_and_record(data)
                self.last_timestamps[device_id] = timestamp
        
        # 初始化聊天机器人 - 支持所有第三方OpenAI格式API
        print(f"正在初始化AI聊天机器人...")
        print(f"API类型: {API_TYPE}")
        print(f"API地址: {API_BASE}")
        print(f"模型: {MODEL_NAME}")
        
        self.chatbot = Chatbot(
            api_key=API_KEY,
            engine=MODEL_NAME,
            api_base=API_BASE,
            api_type=API_TYPE,
        )
        
        print("AI聊天机器人初始化完成！")
        
        # 显示简洁的欢迎信息和使用说明
        self.log_important("MIGPT已启动 - 包含\"请\"、\"帮我\"、\"问一下\"、\"AI\"等关键词的问题将由AI回答")
        self.log_important("命令：help(帮助) | status(状态) | api_logs(切换API日志) | start/stop(启动/停止) | quiet/normal/debug(日志级别)")

    async def show_device_selection_menu(self, auto_selection=None):
        """
        显示设备选择菜单，让用户选择要使用的设备
        auto_selection: 如果提供，则自动选择指定的设备（可以是数字、逗号分隔的数字或'all'）
        """
        print(f"\n===== {config.get_text('device_selection_title')} =====")
        print(config.get_text('device_selection_prompt'))
        for i, device in enumerate(self.devices):
            selected = "✓" if i in self.selected_devices else " "
            print(f"[{selected}] {i+1}. {device.get('name', '未命名')}")
        
        # 处理自动选择或等待用户输入
        selection = auto_selection if auto_selection is not None else input(f"{config.get_text('device_selection_prompt')} ")
        
        # 处理用户输入
        if selection.lower() == 'all':
            # 选择所有设备
            self.selected_devices = list(range(len(self.devices)))
            print(config.get_text('all_devices_selected'))
        else:
            try:
                # 解析用户输入的设备编号
                device_indices = [int(idx.strip()) - 1 for idx in selection.split(',') if idx.strip()]
                # 验证设备编号是否有效
                valid_indices = [idx for idx in device_indices if 0 <= idx < len(self.devices)]
                if valid_indices:
                    self.selected_devices = valid_indices
                    selected_names = [self.devices[idx].get('name', '未命名') for idx in valid_indices]
                    print(f"{config.get_text('selected_devices')}: {', '.join(selected_names)}")
                else:
                    print(config.get_text('no_valid_devices'))
            except ValueError:
                print(config.get_text('input_format_error'))
        
        print(f"===== {config.get_text('device_selection_complete')} =====\n")
        
        # 重新初始化设备的cookie和时间戳
        self.device_cookies = {}
        self.last_timestamps = {}
        for device_idx in self.selected_devices:
            device = self.devices[device_idx]
            device_id = device.get("deviceID")
            hardware = device.get("hardware", "")
            
            # 初始化cookie
            cookie_string = COOKIE_TEMPLATE.format(
                device_id=device_id,
                service_token=self.service_token,
                user_id=self.user_id,
            )
            self.device_cookies[device_id] = parse_cookie_string(cookie_string)
            self.last_timestamps[device_id] = 0
            
            # 获取初始数据
            data = await self.get_latest_ask_from_xiaoai(device_id, hardware)
            if data:
                timestamp, _ = self.get_last_timestamp_and_record(data)
                self.last_timestamps[device_id] = timestamp
    
    async def do_tts(self, text, device_idx=None):
        """
        使用小爱音箱播放文本，支持指定设备
        """
        if not self.devices:
            self.log_info("没有可用设备")
            return False
        
        if device_idx is not None:
            # 向指定设备发送消息
            if 0 <= device_idx < len(self.devices):
                device = self.devices[device_idx]
                device_name = device.get('name', '未命名')
                self.log_debug(f"向设备 {device_name} 发送消息...")
                try:
                    # 设置重试次数
                    max_retries = 2
                    for retry in range(max_retries + 1):
                        try:
                            # 静默发送正常命令，只在日志级别>=2时输出详细信息
                            if self.log_level >= 2:
                                result = await self.mina_service.send_message([device], 1, text)
                            else:
                                # 使用静默版本，避免在控制台输出API请求信息
                                result = await self.mina_service.text_to_speech_silent(device.get("deviceID"), text)
                                
                            if result:
                                self.log_debug(f"设备 {device_name} 消息发送成功")
                                return True
                            else:
                                if retry < max_retries:
                                    self.log_debug(f"设备 {device_name} 消息发送失败，尝试重试 ({retry+1}/{max_retries})...")
                                    await asyncio.sleep(0.5)  # 短暂延迟后重试
                                else:
                                    self.log_info(f"设备 {device_name} 消息发送失败")
                                    return False
                        except Exception as retry_err:
                            if retry < max_retries and "ROM端未响应" in str(retry_err):
                                self.log_debug(f"设备 {device_name} ROM端未响应，尝试重试 ({retry+1}/{max_retries})...")
                                await asyncio.sleep(0.5)  # 短暂延迟后重试
                            else:
                                raise retry_err
                    return False
                except Exception as e:
                    self.log_info(f"设备 {device_name} 消息发送异常: {str(e)}")
                    if "ROM端未响应" in str(e) and "3012" in str(e):
                        self.log_info(f"设备 {device_name} 可能正忙，请稍后再试")
                    return False
            else:
                self.log_info(f"设备索引 {device_idx} 无效")
                return False
        else:
            # 向所有选中的设备发送消息
            if not self.selected_devices:
                self.log_info("没有选择设备，使用第一个设备")
                self.selected_devices = [0]
            
            success = False
            # 创建设备尝试列表副本，避免在迭代过程中修改原列表
            devices_to_try = self.selected_devices.copy()
            
            for device_idx in devices_to_try:
                if 0 <= device_idx < len(self.devices):
                    device = self.devices[device_idx]
                    device_name = device.get('name', '未命名')
                    self.log_debug(f"向设备 {device_name} 发送消息...")
                    try:
                        # 发送消息到指定设备，带重试机制
                        max_retries = 1
                        for retry in range(max_retries + 1):
                            try:
                                # 静默发送正常命令，只在日志级别>=2时输出详细信息
                                if self.log_level >= 2:
                                    result = await self.mina_service.send_message([device], 1, text)
                                else:
                                    # 使用静默版本，避免在控制台输出API请求信息
                                    result = await self.mina_service.text_to_speech_silent(device.get("deviceID"), text)
                                    
                                if result:
                                    success = True
                                    self.log_debug(f"设备 {device_name} 消息发送成功")
                                    break  # 成功发送后退出重试循环
                                elif retry < max_retries:
                                    self.log_debug(f"设备 {device_name} 消息发送失败，尝试重试...")
                                    await asyncio.sleep(0.5)  # 短暂延迟后重试
                            except Exception as retry_err:
                                if retry < max_retries and "ROM端未响应" in str(retry_err):
                                    self.log_debug(f"设备 {device_name} ROM端未响应，尝试重试...")
                                    await asyncio.sleep(0.5)  # 短暂延迟后重试
                                else:
                                    raise retry_err
                        
                        if not success and device_idx == devices_to_try[-1]:
                            self.log_info(f"设备 {device_name} 消息发送失败")
                    except Exception as e:
                        error_str = str(e)
                        self.log_info(f"设备 {device_name} 消息发送异常: {error_str}")
                        # 特殊处理ROM端未响应错误
                        if "ROM端未响应" in error_str and "3012" in error_str:
                            self.log_info(f"设备 {device_name} 可能正忙，将尝试其他设备")
                            # 继续尝试其他设备
                            continue
            
            return success

    async def get_latest_ask_from_xiaoai(self, device_id=None, hardware=None):
        """
        从小爱获取最新的用户提问，支持指定设备
        """
        try:
            if device_id is None:
                device_id = self.device_id
            if hardware is None:
                hardware = self.hardware
                
            url = LATEST_ASK_API.format(
                hardware=hardware, 
                timestamp=str(int(time.time() * 1000))
            )
            
            # 使用指定设备的cookie
            cookie = self.device_cookies.get(device_id, self.cookie)
            
            # 发送请求，设置超时时间
            r = await self.session.get(url, cookies=cookie, timeout=3.0)
            
            if r.status == 200:
                return await r.json()
            else:
                # 只在第一次错误时输出详细信息
                error_text = await r.text()
                if "cookie" in error_text.lower() or "userId" in error_text:
                    self.log_important("检测到cookie问题，尝试重新登录...")
                    await self.miboy_account.login("micoapi")
                    
                    # 更新token
                    with open(self.mi_token_home) as f:
                        user_data = json.loads(f.read())
                    
                    # 确保userId是数字格式的字符串
                    self.user_id = str(user_data.get("userId"))
                    self.service_token = user_data.get("micoapi")[1]
                    
                    # 重新生成cookie
                    cookie_string = COOKIE_TEMPLATE.format(
                        device_id=device_id,
                        service_token=self.service_token,
                        user_id=self.user_id
                    )
                    self.device_cookies[device_id] = parse_cookie_string(cookie_string)
                    self.log_important("已更新cookie")
                    
                    # 立即重试一次
                    try:
                        r2 = await self.session.get(url, cookies=self.device_cookies[device_id], timeout=3.0)
                        if r2.status == 200:
                            return await r2.json()
                    except Exception:
                        pass
                else:
                    self.log_info(f"获取用户提问失败: {r.status}, 错误信息: {error_text}")
                
                return None
        except asyncio.TimeoutError:
            self.log_info(f"获取设备 {device_id} 的用户提问超时")
            return None
        except Exception as e:
            self.log_info(f"获取用户提问时发生错误: {e}")
            return None
    
    def get_last_timestamp_and_record(self, data):
        """
        从API返回数据中获取最新的时间戳和记录
        """
        if not data or "data" not in data:
            return 0, None
            
        # 尝试解析data["data"]，它可能是JSON字符串
        try:
            if isinstance(data["data"], str):
                data_obj = json.loads(data["data"])
            else:
                data_obj = data["data"]
                
            # 调试输出完整的数据结构
            if self.log_level >= 2:
                print(f"完整的数据结构: {json.dumps(data_obj, ensure_ascii=False, indent=2)}")
                
            records = data_obj.get("records", [])
            if not records:
                return 0, None
                
            latest_record = records[0]
            timestamp = latest_record.get("time", 0)
            
            # 调试输出最新记录
            if self.log_level >= 2:
                print(f"最新记录: {json.dumps(latest_record, ensure_ascii=False, indent=2)}")
            
            # 尝试从多个可能的字段获取回复
            if "answer" not in latest_record or not latest_record.get("answer"):
                # 尝试从answers字段获取
                if "answers" in latest_record:
                    answers = latest_record.get("answers", [])
                    if answers and isinstance(answers, list):
                        for ans in answers:
                            # 处理LLM类型的回复
                            if ans.get("type") == "LLM" and "llm" in ans:
                                llm_data = ans.get("llm", {})
                                if "text" in llm_data:
                                    latest_record["answer"] = llm_data.get("text", "")
                                    if self.log_level >= 2:
                                        print(f"从llm.text中提取的回复: {latest_record['answer']}")
                                    break
                            
                            # 处理TTS类型的回复
                            if "tts" in ans and ans.get("tts"):
                                latest_record["answer"] = ans.get("tts", "")
                                if self.log_level >= 2:
                                    print(f"从answers.tts中提取的回复: {latest_record['answer']}")
                                break
                            elif "text" in ans and ans.get("text"):
                                latest_record["answer"] = ans.get("text", "")
                                if self.log_level >= 2:
                                    print(f"从answers.text中提取的回复: {latest_record['answer']}")
                                break
                
                # 尝试从response字段获取
                if not latest_record.get("answer") and "response" in latest_record:
                    latest_record["answer"] = latest_record.get("response", "")
                    if self.log_level >= 2:
                        print(f"从response中提取的回复: {latest_record['answer']}")
                
                # 尝试从result字段获取
                if not latest_record.get("answer") and "result" in latest_record:
                    result = latest_record.get("result", {})
                    if isinstance(result, dict) and "text" in result:
                        latest_record["answer"] = result.get("text", "")
                        if self.log_level >= 2:
                            print(f"从result.text中提取的回复: {latest_record['answer']}")
                            
                # 尝试从content字段获取
                if not latest_record.get("answer") and "content" in latest_record:
                    content = latest_record.get("content", "")
                    if content:
                        latest_record["answer"] = content
                        if self.log_level >= 2:
                            print(f"从content中提取的回复: {latest_record['answer']}")
            
            return timestamp, latest_record
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            print(f"解析数据时出错: {e}")
            print(f"原始数据: {data['data']}")
            return 0, None
    
    async def send_stop_command(self, device_idx):
        """发送停止命令打断小爱当前的播放/回复"""
        try:
            if 0 <= device_idx < len(self.devices):
                device = self.devices[device_idx]
                device_name = device.get('name', '未命名')
                self.log_debug(f"向设备 {device_name} 发送打断命令...")
                
                # 发送一个极短的停止指令
                stop_command = "."
                try:
                    # 静默发送停止命令，减少控制台输出
                    # 临时降低日志级别
                    original_log_level = self.log_level
                    self.log_level = 0  # 临时设为静默模式
                    
                    # 使用临时日志级别调用send_message
                    result = await self.mina_service.text_to_speech_silent(device.get("deviceID"), stop_command)
                    
                    # 恢复原有日志级别
                    self.log_level = original_log_level
                    
                    # 短暂延迟确保命令被处理，但减少延迟时间以提高响应速度
                    await asyncio.sleep(0.1)
                    return True
                except Exception as e:
                    self.log_debug(f"发送打断命令失败: {e}")
                    return False
            else:
                self.log_debug(f"无效的设备索引: {device_idx}")
                return False
        except Exception as e:
            self.log_debug(f"打断命令执行出错: {e}")
            return False

    async def process_device_input(self, device_idx):
        """
        处理指定设备的输入
        """
        try:
            device = self.devices[device_idx]
            device_id = device.get("deviceID")
            hardware = device.get("hardware", "")
            device_name = device.get("name", "未命名")
            
            # 获取用户输入 - 直接获取最新数据，不需要额外延迟
            data = await self.get_latest_ask_from_xiaoai(device_id, hardware)
            if not data:
                return
                
            timestamp, record = self.get_last_timestamp_and_record(data)
            
            # 检查时间戳是否更新
            last_timestamp = self.last_timestamps.get(device_id, 0)
            if timestamp <= last_timestamp:
                return
            
            # 更新时间戳
            self.last_timestamps[device_id] = timestamp
            
            if not record:
                return
                
            query = record.get("query", "")
            if not query:
                return
                
            # 获取小爱的原始回复
            xiaomi_answer = record.get("answer", "")
            
            # 调试输出
            if self.log_level >= 2:
                print(f"原始记录: {json.dumps(record, ensure_ascii=False, indent=2)}")
                print(f"提取的回复: {xiaomi_answer}")
            
            # 判断是否使用HomeAssistant处理
            if should_use_ha(query):
                if self.log_level >= 1:
                    print(f"HomeAssistant模式: {query}")  # 简化前缀
                # 处理用户输入，去掉可能的关键词
                ha_config = config.get("homeassistant", {})
                ha_keywords = ha_config.get("ai_keywords", []) + ha_config.get("text_keywords", [])
                cleaned_query = get_cleaned_input(query, ha_keywords)
                
                try:
                    # 立即发送打断命令，防止小爱自己回复
                    await self.send_stop_command(device_idx)
                    
                    # 导入api_server模块
                    import api_server
                    
                    # 判断是使用语音指令还是文本指令
                    if any(keyword in query for keyword in ha_config.get("ai_keywords", [])):
                        # 使用语音指令
                        answer = api_server.send_ha_voice_command(cleaned_query)
                    else:
                        # 使用文本指令
                        answer = api_server.send_ha_command(cleaned_query)
                    
                    # 只在日志级别>=1时输出回答，避免重复输出
                    if self.log_level >= 1:
                        print(f"HomeAssistant回答: {answer}")
                    
                    # 向发出请求的设备回复，捕获可能的错误
                    try:
                        await self.do_tts(answer, device_idx)
                    except Exception as e:
                        self.log_info(f"HomeAssistant回复发送失败: {e}")
                        # 尝试发送到其他设备
                        if device_idx in self.selected_devices and len(self.selected_devices) > 1:
                            other_devices = [idx for idx in self.selected_devices if idx != device_idx]
                            self.log_info(f"尝试发送到其他设备...")
                            for other_idx in other_devices:
                                try:
                                    if await self.do_tts(answer, other_idx):
                                        self.log_info(f"成功通过备用设备发送回复")
                                        break
                                except Exception:
                                    continue
                    
                    # 将AI回答添加到对话历史
                    self.conversation_history.append({"role": "assistant", "content": answer})
                    
                    # 保存对话历史
                    self.save_conversation_history()
                    
                    return  # 处理完成，返回
                except Exception as e:
                    self.log_info(f"HomeAssistant处理出错: {e}")
                    # 准备错误消息
                    error_message = "抱歉，HomeAssistant处理出错，请稍后再试。"
                    
                    # 尝试发送错误消息，但不再抛出异常
                    try:
                        await self.do_tts(error_message, device_idx)
                    except Exception as send_err:
                        self.log_info(f"无法发送错误消息: {send_err}")
                    
                    return  # 处理完成，返回
            
            # 判断是否使用AI助手回答
            if should_use_ai(query) and SWITCH:
                if self.log_level >= 1:
                    print(f"{config.get_text('ai_mode')}: {query}")
                # 处理用户输入，去掉可能的关键词
                cleaned_query = get_cleaned_input(query)
                
                # 立即发送打断命令，防止小爱自己回复
                await self.send_stop_command(device_idx)
                
                # 将用户问题添加到对话历史
                self.conversation_history.append({"role": "user", "content": cleaned_query})
                # 保持历史记录在合理范围内
                if len(self.conversation_history) > 10:
                    self.conversation_history = self.conversation_history[-10:]
                
                # 构建带有历史上下文的提示
                context_prompt = ""
                if len(self.conversation_history) > 1:
                    context_prompt = "请根据我们之前的对话回答以下问题。\n"
                
                try:
                    # 使用AI模型回答
                    lock = threading.Lock()
                    stop_event = threading.Event()
                    t = threading.Thread(
                        target=self.chatbot.ask_stream,
                        args=(
                            context_prompt + cleaned_query + f"\n{PROMPT}",
                            lock,
                            stop_event,
                        ),
                    )
                    t.start()
                    t.join(timeout=30)
                    
                    if t.is_alive():
                        self.log_info("AI回答超时")
                        stop_event.set()  # 通知线程停止
                        t.join()
                        answer = config.get_text('error_timeout')
                    else:
                        # 获取回答并发送
                        answer = self.chatbot.sentence
                        self.chatbot.sentence = ""
                        
                        # 对回答进行后处理，使其更自然
                        answer = optimize_answer(answer)
                    
                    # 将AI回答添加到对话历史
                    self.conversation_history.append({"role": "assistant", "content": answer})
                    
                    # 保存对话历史
                    self.save_conversation_history()
                    
                    # 只在日志级别>=1时输出回答，避免重复输出
                    if self.log_level >= 1:
                        print(f"AI回答: {answer}")
                    
                    # 向发出请求的设备回复，捕获可能的错误
                    try:
                        await self.do_tts(answer, device_idx)
                    except Exception as e:
                        self.log_info(f"AI回复发送失败: {e}")
                        # 尝试发送到其他设备
                        if device_idx in self.selected_devices and len(self.selected_devices) > 1:
                            other_devices = [idx for idx in self.selected_devices if idx != device_idx]
                            self.log_info(f"尝试发送到其他设备...")
                            for other_idx in other_devices:
                                try:
                                    if await self.do_tts(answer, other_idx):
                                        self.log_info(f"成功通过备用设备发送回复")
                                        break
                                except Exception:
                                    continue
                except Exception as e:
                    self.log_info(f"AI回答出错: {e}")
                    # 准备错误消息
                    error_message = "抱歉，AI回答出错，请稍后再试。"
                    
                    # 尝试发送错误消息，但不再抛出异常
                    try:
                        await self.do_tts(error_message, device_idx)
                    except Exception as send_err:
                        self.log_info(f"无法发送错误消息: {send_err}")
            else:
                # 显示小爱的原始回复
                if self.log_level >= 1:
                    print(f"小爱模式: {query}")  # 简化前缀
                    if xiaomi_answer:
                        # 检查回复是否为JSON格式
                        if isinstance(xiaomi_answer, dict) and "text" in xiaomi_answer:
                            print(f"小爱回复: {xiaomi_answer['text']}")  # 只显示text内容
                        else:
                            print(f"小爱回复: {xiaomi_answer}")  # 简化前缀
                    else:
                        print("小爱没有回复或无法获取回复")
        except Exception as e:
            self.log_info(f"处理设备输入时出错: {e}")
            # 提供更详细的错误信息但不打印完整堆栈
            error_type = type(e).__name__
            self.log_info(f"错误类型: {error_type}")
            # 对于特定类型的错误提供更多信息
            if "ROM端未响应" in str(e):
                self.log_info("设备可能暂时不可用，将在下次轮询时重试")
    
    async def process_all_devices(self):
        """
        处理所有选中设备的输入
        """
        # 静默处理，不输出任务创建信息
        tasks = []
        for device_idx in self.selected_devices:
            task = asyncio.create_task(self.process_device_input(device_idx))
            tasks.append(task)
        
        # 等待所有任务完成
        if tasks:
            await asyncio.gather(*tasks)
    
    def input_reader(self):
        """
        读取用户输入的线程函数
        """
        while self.running:
            try:
                command = input(config.get_text('command_prompt'))
                # 将命令放入队列
                asyncio.run_coroutine_threadsafe(self.command_queue.put(command), loop)
            except EOFError:
                # 处理EOF（如Ctrl+D）
                self.running = False
                break
            except Exception as e:
                print(f"读取输入时出错: {e}")
                time.sleep(1)
    
    async def command_handler(self):
        """
        处理用户命令
        """
        global SWITCH
        while self.running:
            try:
                # 从队列获取命令
                command = await self.command_queue.get()
                
                # 处理命令
                if command.lower() == 'exit' or command.lower() == '退出':
                    self.running = False
                    self.log_important("正在退出程序...")
                    break
                elif command.lower() == 'select' or command.lower() == '选择设备':
                    await self.show_device_selection_menu()
                elif command.lower() == 'status' or command.lower() == '状态':
                    self.log_important(f"当前状态: AI回答模式 {'开启' if SWITCH else '关闭'}")
                    self.log_important(f"已选择设备: {[self.devices[idx].get('name', '未命名') for idx in self.selected_devices]}")
                elif command.lower() == 'help' or command.lower() == '帮助':
                    self.log_important("可用命令:")
                    self.log_important("  help/帮助      - 显示帮助信息")
                    self.log_important("  status/状态    - 显示当前状态")
                    self.log_important("  select/选择设备 - 重新选择设备")
                    self.log_important("  on/开启ai      - 开启AI回答模式")
                    self.log_important("  off/关闭ai     - 关闭AI回答模式")
                    self.log_important("  exit/退出      - 退出程序")
                    self.log_important("  config/配置    - 打开配置界面")
                    self.log_important("  history/历史   - 显示对话历史")
                    self.log_important("  export/导出    - 导出对话历史")
                    self.log_important("  import/导入    - 导入对话历史")
                    self.log_important("  clear/清空     - 清空对话历史")
                elif command.lower() == 'on' or command.lower() == '开启ai':
                    SWITCH = True
                    self.log_important(config.get_text('ai_mode_on'))
                elif command.lower() == 'off' or command.lower() == '关闭ai':
                    SWITCH = False
                    self.log_important(config.get_text('ai_mode_off'))
                elif command.lower() == 'start' or command.lower() == '开始':
                    self.auto_process = True
                    self.log_important("已开始自动处理设备输入")
                elif command.lower() == 'stop' or command.lower() == '停止':
                    self.auto_process = False
                    self.log_important("已停止自动处理设备输入")
                elif command.lower() == 'config' or command.lower() == '配置':
                    self.log_important("正在打开配置界面...")
                    os.system('python config_gui.py')
                elif command.lower() == 'history' or command.lower() == '历史':
                    # 显示对话历史
                    if not self.conversation_history:
                        self.log_important("对话历史为空")
                    else:
                        self.log_important(f"对话历史 (共{len(self.conversation_history)}条):")
                        for i, msg in enumerate(self.conversation_history):
                            role = "用户" if msg["role"] == "user" else "AI"
                            content = msg["content"]
                            # 如果内容太长，截断显示
                            if len(content) > 50:
                                content = content[:50] + "..."
                            self.log_important(f"{i+1}. {role}: {content}")
                elif command.lower() == 'export' or command.lower() == '导出':
                    # 导出对话历史
                    if not self.conversation_history:
                        self.log_important("对话历史为空，无需导出")
                    else:
                        export_file = self.export_conversation_history()
                        if export_file:
                            self.log_important(f"对话历史已导出到: {export_file}")
                elif command.lower() == 'import' or command.lower() == '导入':
                    # 导入对话历史
                    self.log_important("请输入要导入的文件路径:")
                    # 等待用户输入文件路径
                    import_file = await self.command_queue.get()
                    if import_file.lower() in ['cancel', '取消']:
                        self.log_important("已取消导入")
                    else:
                        success = self.import_conversation_history(import_file)
                        if success:
                            self.log_important(f"成功导入对话历史，共{len(self.conversation_history)}条记录")
                        else:
                            self.log_important("导入失败，请检查文件路径和格式")
                elif command.lower() == 'clear' or command.lower() == '清空':
                    # 清空对话历史
                    self.log_important("确定要清空所有对话历史吗? (yes/no)")
                    confirm = await self.command_queue.get()
                    if confirm.lower() in ['yes', 'y', '是', '确定']:
                        self.clear_conversation_history()
                        self.log_important("对话历史已清空")
                    else:
                        self.log_important("已取消清空操作")
                elif command:
                    # 如果是其他命令，尝试向设备发送消息
                    if self.selected_devices:
                        # 判断是否使用AI助手回答
                        if should_use_ai(command) and SWITCH:
                            if self.log_level >= 1:
                                print(f"{config.get_text('ai_mode')}: {command}")
                            # 处理用户输入，去掉可能的关键词
                            cleaned_query = get_cleaned_input(command)
                            
                            # 将用户问题添加到对话历史
                            self.conversation_history.append({"role": "user", "content": cleaned_query})
                            
                            # 保持历史记录在合理范围内
                            if len(self.conversation_history) > 10:
                                self.conversation_history = self.conversation_history[-10:]
                            
                            # 构建带有历史上下文的提示
                            context_prompt = ""
                            if len(self.conversation_history) > 1:
                                context_prompt = "请根据我们之前的对话回答以下问题。\n"
                            
                            try:
                                # 使用AI回答
                                lock = threading.Lock()
                                stop_event = threading.Event()
                                t = threading.Thread(
                                    target=self.chatbot.ask_stream,
                                    args=(
                                        context_prompt + cleaned_query + f"\n{PROMPT}",
                                        lock,
                                        stop_event,
                                    ),
                                )
                                t.start()
                                t.join(timeout=30)
                                
                                if t.is_alive():
                                    self.log_info("AI回答超时")
                                    stop_event.set()
                                    t.join()
                                    answer = config.get_text('error_timeout')
                                else:
                                    answer = self.chatbot.sentence
                                    self.chatbot.sentence = ""
                                    
                                    # 对回答进行后处理
                                    answer = optimize_answer(answer)
                                
                                # 将AI回答添加到对话历史
                                self.conversation_history.append({"role": "assistant", "content": answer})
                                
                                # 保存对话历史
                                self.save_conversation_history()
                                
                                if self.log_level >= 1:
                                    print(f"以下是AI的回答: {answer}")
                                # 向所有选中的设备发送回复
                                for device_idx in self.selected_devices:
                                    await self.do_tts(answer, device_idx)
                            except Exception as e:
                                self.log_info(f"AI回答出错: {e}")
                                error_message = "抱歉，AI回答出错，请稍后再试。"
                                for device_idx in self.selected_devices:
                                    await self.do_tts(error_message, device_idx)
                        else:
                            # 小爱模式
                            if self.log_level >= 1:
                                print(f"小爱模式: {command}")
                            # 向所有选中的设备发送消息
                            for device_idx in self.selected_devices:
                                await self.do_tts(command, device_idx)
                    else:
                        self.log_info("未选择设备，请先选择设备")
                
                # 标记命令已处理完成
                self.command_queue.task_done()
            except Exception as e:
                self.log_info(f"处理命令时出错: {e}")
                await asyncio.sleep(0.1)
    
    async def run(self):
        """
        运行MiGPT，处理用户输入和设备输入
        """
        # 初始化数据
        try:
            await self.init_all_data(self.session)
        except Exception as e:
            self.log_important(f"初始化失败: {e}")
            traceback.print_exc()
            return

        # 如果没有设备可用，只处理命令输入
        if not self.devices or not self.selected_devices:
            self.log_important("⚠️ 没有可用的小爱设备，仅支持命令行操作")
            self.log_important("您可以使用 'config' 命令打开配置界面设置账号")
            # 创建命令处理线程
            input_thread = threading.Thread(target=self.input_reader)
            input_thread.daemon = True
            input_thread.start()
            
            # 处理命令
            while self.running:
                try:
                    await self.command_handler()
                except Exception as e:
                    self.log_important(f"命令处理错误: {e}")
                    traceback.print_exc()
                await asyncio.sleep(0.1)
            return

        # 启动输入读取线程
        input_thread = threading.Thread(target=self.input_reader)
        input_thread.daemon = True
        input_thread.start()
        
        # 启动命令处理任务
        command_task = asyncio.create_task(self.command_handler())
        
        # 定义轮询间隔（秒）
        polling_interval = 0.05  # 减少轮询间隔以提高响应速度
        
        # 记录上次处理时间，用于控制轮询频率
        last_process_time = time.time()
        
        # 主循环
        try:
            while self.running:
                current_time = time.time()
                
                # 如果启用了自动处理，则处理所有设备的输入
                if self.auto_process:
                    # 控制轮询频率
                    if current_time - last_process_time >= polling_interval:
                        await self.process_all_devices()
                        last_process_time = current_time
                
                # 短暂休眠，避免过于频繁的循环
                await asyncio.sleep(polling_interval)
        except KeyboardInterrupt:
            self.log_important("接收到中断信号，程序即将退出...")
            self.running = False
        except Exception as e:
            self.log_important(f"运行时出错: {e}")
            if self.log_level >= 2:
                import traceback
                traceback.print_exc()
        finally:
            # 等待命令处理任务完成
            command_task.cancel()
            try:
                await command_task
            except asyncio.CancelledError:
                pass
            
            # 关闭会话
            if self.session:
                await self.session.close()
            
            self.log_important("程序已退出")

    def save_conversation_history(self):
        """
        保存对话历史到文件
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            
            # 保存对话历史
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)
                
            self.log_info(f"对话历史已保存到 {self.history_file}")
            return True
        except Exception as e:
            self.log_important(f"保存对话历史失败: {e}")
            return False
    
    def load_conversation_history(self):
        """
        从文件加载对话历史
        """
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.conversation_history = json.load(f)
                self.log_info(f"已加载对话历史，共 {len(self.conversation_history)} 条记录")
                return True
            return False
        except Exception as e:
            self.log_important(f"加载对话历史失败: {e}")
            self.conversation_history = []
            return False
    
    def export_conversation_history(self, export_file=None):
        """
        导出对话历史到指定文件
        
        Args:
            export_file: 导出文件路径，如果为None则使用时间戳命名
        
        Returns:
            str: 导出文件路径
        """
        try:
            if not export_file:
                # 使用时间戳命名导出文件
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                export_file = f"data/exports/conversation_{timestamp}.json"
            
            # 确保目录存在
            os.makedirs(os.path.dirname(export_file), exist_ok=True)
            
            # 导出对话历史
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)
                
            self.log_important(f"对话历史已导出到 {export_file}")
            return export_file
        except Exception as e:
            self.log_important(f"导出对话历史失败: {e}")
            return None
    
    def import_conversation_history(self, import_file):
        """
        从文件导入对话历史
        
        Args:
            import_file: 导入文件路径
            
        Returns:
            bool: 是否导入成功
        """
        try:
            if not os.path.exists(import_file):
                self.log_important(f"导入文件不存在: {import_file}")
                return False
                
            with open(import_file, 'r', encoding='utf-8') as f:
                imported_history = json.load(f)
                
            # 验证导入的数据格式
            if not isinstance(imported_history, list):
                self.log_important("导入失败: 文件格式不正确")
                return False
                
            for item in imported_history:
                if not isinstance(item, dict) or 'role' not in item or 'content' not in item:
                    self.log_important("导入失败: 对话记录格式不正确")
                    return False
            
            # 导入对话历史
            self.conversation_history = imported_history
            
            # 保存到默认历史文件
            self.save_conversation_history()
            
            self.log_important(f"已导入对话历史，共 {len(self.conversation_history)} 条记录")
            return True
        except Exception as e:
            self.log_important(f"导入对话历史失败: {e}")
            return False
    
    def clear_conversation_history(self):
        """
        清空对话历史
        """
        self.conversation_history = []
        self.log_important("对话历史已清空")
        
        # 同时删除历史文件
        if os.path.exists(self.history_file):
            try:
                os.remove(self.history_file)
                self.log_info(f"已删除历史文件 {self.history_file}")
            except Exception as e:
                self.log_important(f"删除历史文件失败: {e}")
        
        return True

async def main():
    """
    主函数
    """
    print("正在初始化...")
    
    try:
        # 创建会话
        async with ClientSession() as session:
            # 创建MiGPT实例
            migpt = MiGPT()
            migpt.session = session  # 确保session被正确设置
            
            try:
                # 初始化数据并运行
                await migpt.run()
            except Exception as e:
                print(f"运行出错: {e}")
                import traceback
                traceback.print_exc()
    except Exception as e:
        print(f"初始化会话失败: {e}")
        import traceback
        traceback.print_exc()

# 在文件末尾使用统一的入口点
if __name__ == "__main__":
    # 创建事件循环
    loop = asyncio.get_event_loop()
    
    try:
        # 运行主函数
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("程序被用户中断")
    except Exception as e:
        print(f"程序出错: {e}")
        traceback.print_exc()
    finally:
        # 关闭事件循环
        loop.close()
