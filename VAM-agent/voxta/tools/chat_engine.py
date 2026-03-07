#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VAM-agent 聊天引擎 — 脱离Voxta独立运行
重新实现Voxta全部核心逻辑:
  1. 角色人格注入 (system prompt construction)
  2. 记忆上下文窗口 (SimpleMemory equivalent)
  3. 对话历史管理 (DB read/write)
  4. LLM直调 (DashScope/OpenAI-compatible)
  5. TTS直调 (EdgeTTS)
  6. SignalR客户端 (Voxta连接模式)
  7. 动作推理 (action inference)
"""

import sqlite3
import json
import re
import sys
import os
import time
import uuid
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════

try:
    from voxta.config import VOXTA_CONFIG
    VOXTA_DB = VOXTA_CONFIG.VOXTA_DB
except ImportError:
    VOXTA_DB = Path(r"F:\vam1.22\Voxta\Active\Data\Voxta.sqlite.db")
EDGETTS_URL = "http://localhost:5050"
VOXTA_URL = "http://localhost:5384"
DASHSCOPE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEEPSEEK_URL = "https://api.deepseek.com/v1"
OLLAMA_URL = "http://localhost:11434/v1"
LMSTUDIO_URL = "http://localhost:1234/v1"

# SimpleMemory等效参数
MEMORY_WINDOW = 12       # 最近N轮对话作为上下文
MAX_SYSTEM_TOKENS = 2000 # system prompt最大长度(字符近似)
MAX_REPLY_TOKENS = 500   # LLM回复最大token


# ═══════════════════════════════════════════════════════
# 角色加载器
# ═══════════════════════════════════════════════════════

class CharacterLoader:
    """从Voxta DB加载角色完整数据"""

    def __init__(self, db_path=VOXTA_DB):
        self.db_path = db_path

    def _conn(self):
        db = sqlite3.connect(str(self.db_path))
        db.row_factory = sqlite3.Row
        return db

    def load(self, char_id_or_name):
        """通过ID前缀或名称加载角色"""
        db = self._conn()
        try:
            row = None
            # 先尝试ID前缀匹配
            if len(char_id_or_name) >= 4:
                rows = db.execute("SELECT * FROM Characters").fetchall()
                for r in rows:
                    if dict(r).get('LocalId', '').upper().startswith(char_id_or_name.upper()):
                        row = r
                        break
            # 再尝试名称匹配
            if not row:
                row = db.execute("SELECT * FROM Characters WHERE Name=?", (char_id_or_name,)).fetchone()
            if not row:
                return None

            d = dict(row)
            char = {
                'id': d.get('LocalId', ''),
                'name': d.get('Name', ''),
                'description': d.get('Description', ''),
                'personality': d.get('Personality', ''),
                'profile': d.get('Profile', ''),
                'culture': d.get('Culture', 'zh-CN'),
                'first_message': d.get('FirstMessage', ''),
                'message_examples': d.get('MessageExamples', ''),
                'tts': json.loads(d.get('TextToSpeech', '[]') or '[]'),
                'scripts': json.loads(d.get('Scripts', '[]') or '[]'),
                'use_memory': bool(d.get('UseMemory', 0)),
                'thinking_speech': bool(d.get('EnableThinkingSpeech', 0)),
                'explicit': bool(d.get('ExplicitContent', 0)),
                'max_tokens': d.get('MaxTokens', 0),
            }

            # 加载关联的记忆书
            char['memories'] = []
            if char['use_memory']:
                books = db.execute("SELECT * FROM MemoryBooks").fetchall()
                for b in books:
                    bd = dict(b)
                    owner = bd.get('Owner', '') or ''
                    if char['id'] in owner or char['name'] in bd.get('Name', ''):
                        items = json.loads(bd.get('Items', '[]') or '[]')
                        char['memories'].extend([
                            item.get('text', '') for item in items if item.get('text')
                        ])

            return char
        finally:
            db.close()

    def list_all(self):
        db = self._conn()
        try:
            rows = db.execute("SELECT LocalId, Name, Culture, Description FROM Characters").fetchall()
            return [dict(r) for r in rows]
        finally:
            db.close()


# ═══════════════════════════════════════════════════════
# 对话历史管理
# ═══════════════════════════════════════════════════════

class ConversationHistory:
    """对话历史 — 读写Voxta DB ChatMessages表"""

    def __init__(self, db_path=VOXTA_DB):
        self.db_path = db_path

    def _conn(self):
        db = sqlite3.connect(str(self.db_path))
        db.row_factory = sqlite3.Row
        return db

    def get_recent(self, chat_id=None, limit=MEMORY_WINDOW):
        """获取最近N条对话"""
        db = self._conn()
        try:
            if chat_id:
                rows = db.execute(
                    "SELECT * FROM ChatMessages WHERE ChatId=? ORDER BY rowid DESC LIMIT ?",
                    (chat_id, limit)
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM ChatMessages ORDER BY rowid DESC LIMIT ?",
                    (limit,)
                ).fetchall()
        finally:
            db.close()

        messages = []
        for r in reversed(rows):
            d = dict(r)
            role_map = {0: 'system', 1: 'user', 2: 'user', 3: 'assistant', 8: 'system'}
            role = role_map.get(d.get('Role', 0), 'user')
            text = d.get('Value', '') or ''
            if text:
                messages.append({'role': role, 'content': text})
        return messages

    def save_message(self, chat_id, role, text, sender_id='agent'):
        """保存消息到DB"""
        db = self._conn()
        try:
            role_num = {'system': 0, 'user': 2, 'assistant': 3}.get(role, 2)
            msg_id = str(uuid.uuid4()).upper()
            now = datetime.now().isoformat()

            # 获取当前最大index
            row = db.execute(
                "SELECT MAX([Index]) as mx FROM ChatMessages WHERE ChatId=?",
                (chat_id,)
            ).fetchone()
            idx = (dict(row).get('mx', 0) or 0) + 1

            user_id = self._get_user_id()
            db.execute("""INSERT INTO ChatMessages (
                UserId, LocalId, ChatId, SenderId, Timestamp, [Index],
                ConversationIndex, ChatTime, Role, Value, Tokens
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
                user_id, msg_id, chat_id, sender_id, now, idx,
                idx, 0, role_num, text, len(text) // 4
            ))
            db.commit()
            return msg_id
        finally:
            db.close()

    def get_or_create_chat(self, character_id):
        """获取角色最新chat,或创建新chat

        Chats表结构: Characters列是JSONB数组(如 ["UUID"]),不是单独的CharacterId列
        """
        user_id = self._get_user_id()
        db = self._conn()
        try:
            # Characters列是JSONB数组, 用LIKE搜索包含该角色ID的chat
            row = db.execute(
                "SELECT LocalId FROM Chats WHERE Characters LIKE ? ORDER BY rowid DESC LIMIT 1",
                ('%' + character_id + '%',)
            ).fetchone()
            if row:
                chat_id = dict(row)['LocalId']
            else:
                chat_id = str(uuid.uuid4()).upper()
                now = datetime.now().isoformat()
                chars_json = json.dumps([character_id])
                try:
                    db.execute(
                        """INSERT INTO Chats
                        (UserId, LocalId, Favorite, Characters, CreatedAt, Roles, State)
                        VALUES (?,?,0,?,?,'{}','{}')""",
                        (user_id, chat_id, chars_json, now)
                    )
                    db.commit()
                except Exception:
                    pass
            return chat_id
        finally:
            db.close()

    def _get_user_id(self):
        """获取Voxta DB中的UserId"""
        try:
            db = self._conn()
            try:
                row = db.execute("SELECT Id FROM Users LIMIT 1").fetchone()
                if row:
                    return dict(row)['Id']
            finally:
                db.close()
        except Exception:
            pass
        return 'default'


# ═══════════════════════════════════════════════════════
# Prompt构建器 (重新实现Voxta的人格注入逻辑)
# ═══════════════════════════════════════════════════════

class PromptBuilder:
    """
    重新实现Voxta的prompt构建管线:
    1. System prompt = profile + personality + memory context + scenario context
    2. Messages = 最近N轮对话 (SimpleMemory窗口)
    3. 格式 = OpenAI messages array (适配DashScope/qwen)
    """

    @staticmethod
    def build_system_prompt(char, user_name='User', memories=None):
        """构建system prompt — 等效于Voxta的personality injection"""
        parts = []

        # 角色Profile (核心设定)
        if char.get('profile'):
            parts.append(char['profile'])

        # 人格特质
        if char.get('personality'):
            parts.append(f"\nPersonality: {char['personality']}")

        # 角色描述
        if char.get('description'):
            parts.append(f"\nDescription: {char['description']}")

        # 记忆上下文 (等效SimpleMemory)
        if memories:
            mem_text = "\n".join(f"- {m}" for m in memories[:10])
            parts.append(f"\nRelevant memories:\n{mem_text}")

        # 消息示例 (few-shot)
        if char.get('message_examples'):
            parts.append(f"\nMessage examples:\n{char['message_examples']}")

        # 用户信息
        parts.append(f"\nThe user's name is {user_name}.")

        # 语言提示
        culture = char.get('culture', 'zh-CN')
        if culture.startswith('zh'):
            parts.append("\nAlways respond in Chinese (简体中文).")
        elif culture.startswith('en'):
            parts.append("\nAlways respond in English.")

        return "\n".join(parts)

    @staticmethod
    def build_messages(system_prompt, history, char_name='Assistant'):
        """构建OpenAI-compatible messages数组"""
        messages = [{"role": "system", "content": system_prompt}]

        for msg in history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role in ('user', 'assistant', 'system'):
                messages.append({"role": role, "content": content})

        return messages


# ═══════════════════════════════════════════════════════
# LLM直调 (DashScope OpenAI-compatible)
# ═══════════════════════════════════════════════════════

class LLMClient:
    """直接调用LLM API — 绕过Voxta，支持多后端自动降级"""

    # 后端配置: (name, url, model, env_key)
    BACKENDS = [
        ('dashscope', DASHSCOPE_URL, 'qwen-plus', 'DASHSCOPE_API_KEY'),
        ('deepseek', DEEPSEEK_URL, 'deepseek-chat', 'DEEPSEEK_API_KEY'),
        ('ollama', OLLAMA_URL, None, None),
        ('lmstudio', LMSTUDIO_URL, None, None),
        ('local', 'http://localhost:7860/v1', None, None),
    ]

    def __init__(self, api_key=None, base_url=None, model='qwen-plus', backend=None):
        self.api_key = api_key
        self.base_url = base_url or DASHSCOPE_URL
        self.model = model
        self.backend = backend  # None=auto, or 'dashscope'/'deepseek'/'local'

    @staticmethod
    def _filter_think(text: str) -> str:
        """过滤DeepSeek R1系列的<think>标签。

        从ai_virtual_mate_comm think_filter_switch()移植。
        """
        if '</think>' in text:
            text = text.split('</think>')[-1].strip()
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        return text

    def chat(self, messages, max_tokens=MAX_REPLY_TOKENS, temperature=0.7, stream=False):
        """发送聊天请求"""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        if self.api_key:
            req.add_header('Authorization', f'Bearer {self.api_key}')

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                choices = result.get('choices', [])
                if choices:
                    text = choices[0].get('message', {}).get('content', '')
                    text = self._filter_think(text)
                    return {
                        'text': text,
                        'usage': result.get('usage', {}),
                        'model': result.get('model', self.model),
                    }
                return {'text': '', 'usage': {}, 'model': self.model}
        except Exception as e:
            return {'text': '', 'error': str(e)}

    def chat_with_fallback(self, messages, max_tokens=MAX_REPLY_TOKENS, temperature=0.7):
        """自动降级调用: dashscope -> deepseek -> local"""
        backends = self.BACKENDS
        if self.backend:
            backends = [b for b in backends if b[0] == self.backend] or backends

        orig_url, orig_model, orig_key = self.base_url, self.model, self.api_key
        errors = []
        for name, url, model, env_key in backends:
            api_key = os.environ.get(env_key, '') if env_key else None
            if env_key and not api_key:
                continue  # skip backends without API key
            self.base_url = url
            self.model = model or 'default'
            self.api_key = api_key or self.api_key
            result = self.chat(messages, max_tokens, temperature)
            if result.get('text'):
                result['backend'] = name
                return result
            errors.append(f"{name}: {result.get('error', 'empty')}")

        self.base_url, self.model, self.api_key = orig_url, orig_model, orig_key
        return {'text': '', 'error': f"All backends failed: {'; '.join(errors)}"}

    def chat_local(self, messages, max_tokens=MAX_REPLY_TOKENS, temperature=0.7):
        """调用本地LLM (TextGen WebUI OpenAI-compatible)"""
        url = "http://localhost:7860/v1/chat/completions"
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                choices = result.get('choices', [])
                if choices:
                    return {
                        'text': choices[0].get('message', {}).get('content', ''),
                        'usage': result.get('usage', {}),
                    }
                return {'text': '', 'usage': {}}
        except Exception as e:
            return {'text': '', 'error': str(e)}


# ═══════════════════════════════════════════════════════
# TTS直调 (EdgeTTS)
# ═══════════════════════════════════════════════════════

class TTSClient:
    """直接调用EdgeTTS — 绕过Voxta"""

    def __init__(self, base_url=EDGETTS_URL):
        self.base_url = base_url

    def speak(self, text, voice='nova', output_path=None):
        """合成语音"""
        url = f"{self.base_url}/v1/audio/speech"
        payload = {
            "model": "tts-1",
            "input": text,
            "voice": voice,
        }
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                audio = resp.read()
                if output_path:
                    with open(output_path, 'wb') as f:
                        f.write(audio)
                    return {'ok': True, 'path': output_path, 'size': len(audio)}
                return {'ok': True, 'size': len(audio)}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def get_voice_for_char(self, char):
        """根据角色TTS配置获取voice参数"""
        tts = char.get('tts', [])
        if tts:
            first = tts[0]
            voice_params = first.get('voice', {}).get('parameters', {})
            return voice_params.get('voice_id', 'nova')
        # 按文化默认
        culture = char.get('culture', 'zh-CN')
        if culture.startswith('zh'):
            return 'nova'  # EdgeTTS中文女声
        return 'alloy'    # EdgeTTS英文


# ═══════════════════════════════════════════════════════
# SignalR客户端 (Voxta连接模式)
# ═══════════════════════════════════════════════════════

class VoxtaSignalR:
    """
    SignalR客户端 — 连接运行中的Voxta服务
    重新实现VaM插件的SignalR协议
    """

    SEPARATOR = '\x1e'
    CLIENT_NAME = 'VAM-agent.ChatEngine'

    def __init__(self, host='localhost', port=5384):
        self.host = host
        self.port = port
        self.ws = None
        self.session_id = None
        self.connected = False
        self._buffer = ''

    def connect(self):
        """建立SignalR连接"""
        import websocket
        url = f"ws://{self.host}:{self.port}/hub"
        self.ws = websocket.create_connection(url, timeout=10)

        # SignalR握手
        self.ws.send('{"protocol":"json","version":1}' + self.SEPARATOR)
        resp = self.ws.recv()
        if not resp.startswith('{}'):
            raise ConnectionError(f"SignalR handshake failed: {resp}")

        # 认证
        auth = {
            "$type": "authenticate",
            "client": self.CLIENT_NAME,
            "clientVersion": "1.0.0",
            "scope": ["role:app"],
            "capabilities": {
                "audioOutput": "Url"
            }
        }
        self._send(auth)
        self.connected = True

        # 等待welcome
        for msg in self._recv():
            if msg.get('$type') == 'welcome':
                return msg
        return None

    def load_characters(self):
        """请求角色列表"""
        self._send({"$type": "loadCharactersList"})
        return self._wait_for('charactersListLoaded', 'characters', [])

    def load_scenarios(self):
        """请求场景列表"""
        self._send({"$type": "loadScenariosList"})
        return self._wait_for('scenariosListLoaded', 'scenarios', [])

    def load_chats(self, character_id, scenario_id=None):
        """请求聊天列表"""
        msg = {"$type": "loadChatsList", "characterId": character_id}
        if scenario_id:
            msg["scenarioId"] = scenario_id
        self._send(msg)
        return self._wait_for('chatsListLoaded', 'chats', [])

    def start_chat(self, character_id, scenario_id=None, chat_id=None):
        """启动聊天会话"""
        msg = {
            "$type": "startChat",
            "characterIds": [character_id],
            "contextKey": "VAM-agent/Base",
        }
        if scenario_id:
            msg["scenarioId"] = scenario_id
        if chat_id:
            msg["chatId"] = chat_id
        self._send(msg)

        deadline = time.time() + 90
        while time.time() < deadline:
            remaining = max(0.5, deadline - time.time())
            for response in self._recv(timeout=min(5, remaining)):
                t = response.get('$type', '')
                if t in ('chatStarted', 'chatStarting'):
                    self.session_id = response.get('sessionId')
                    if t == 'chatStarted':
                        return response
                    continue
                elif t in ('chatLoading', 'chatLoadingMessage', 'chatConfiguration',
                           'moduleRuntimeInstances', 'configuration',
                           'contextUpdated', 'chatFlow', 'recordingStatus',
                           'memoryUpdated', 'chatParticipantsUpdated',
                           'chatsSessionsUpdated', 'downloadProgress',
                           'inspectorEnabled', 'chatInProgress'):
                    continue
                elif t in ('error', 'chatSessionError'):
                    return response
                elif t == 'replyChunk':
                    return response
        return None

    def acknowledge_playback(self, message_id):
        """确认语音播放完成 — Voxta在收到此消息前不处理新输入"""
        if not self.session_id or not message_id:
            return
        self._send({
            "$type": "speechPlaybackStart",
            "sessionId": self.session_id,
            "messageId": message_id,
            "startIndex": 0, "endIndex": 0,
            "duration": 1.0, "isNarration": False
        })
        time.sleep(0.3)
        self._send({
            "$type": "speechPlaybackComplete",
            "sessionId": self.session_id,
            "messageId": message_id
        })

    def set_flags(self, *flags):
        """设置场景标志 (如 'emotes') — 控制哪些动作可以触发"""
        if not self.session_id:
            return
        flag_list = []
        for f in flags:
            if isinstance(f, str):
                flag_list.extend([x.strip() for x in f.split(',') if x.strip()])
            else:
                flag_list.append(str(f))
        self._send({
            "$type": "updateContext",
            "sessionId": self.session_id,
            "setFlags": flag_list,
        })

    def update_context(self, context=None, actions=None, context_key="VAM-agent/Base"):
        """更新聊天上下文和/或动作列表"""
        if not self.session_id:
            return
        msg = {
            "$type": "updateContext",
            "sessionId": self.session_id,
            "contextKey": context_key,
        }
        if context is not None:
            msg["contexts"] = [{"text": context}] if context else []
        if actions is not None:
            msg["actions"] = actions
        self._send(msg)

    def drain(self, timeout=3):
        """消耗所有待处理消息,确保服务器就绪(等待STT周期完成)"""
        for _ in self._recv(timeout=timeout):
            pass

    def send_message(self, text, do_reply=True):
        """发送用户消息"""
        if not self.session_id:
            return None
        self.drain(timeout=3)
        self._send({
            "$type": "send",
            "sessionId": self.session_id,
            "text": text,
            "doReply": do_reply,
            "doCharacterActionInference": True,
        })

    def receive_reply(self, timeout=30, action_wait=5):
        """接收AI回复 (收集所有chunks + 等待尾随的action/appTrigger)"""
        chunks = []
        actions = []
        message_id = None
        start = time.time()
        reply_ended = False
        action_deadline = None

        while time.time() - start < timeout:
            if reply_ended and action_deadline and time.time() > action_deadline:
                break
            recv_timeout = min(3, action_deadline - time.time()) if action_deadline else 3
            for msg in self._recv(timeout=max(0.5, recv_timeout)):
                t = msg.get('$type', '')
                if t == 'replyChunk':
                    chunks.append(msg.get('text', ''))
                elif t == 'replyEnd':
                    message_id = msg.get('messageId')
                    reply_ended = True
                    action_deadline = time.time() + action_wait
                elif t == 'action':
                    actions.append(msg.get('value', ''))
                elif t == 'appTrigger':
                    args = [str(a) if a is not None else '' for a in msg.get('arguments', [])]
                    actions.append(f"{msg.get('name','')}({','.join(args)})")
                elif t in ('replyGenerating', 'replyStart', 'chatFlow',
                           'speechRecognitionStart', 'speechRecognitionEnd',
                           'speechPlaybackStart', 'speechPlaybackComplete',
                           'memoryUpdated', 'contextUpdated',
                           'replyCancelled', 'recordingStatus',
                           'chatConfiguration', 'configuration',
                           'moduleRuntimeInstances', 'downloadProgress',
                           'chatParticipantsUpdated', 'chatsSessionsUpdated',
                           'interruptSpeech', 'update',
                           'inspectorEnabled', 'inspectorScriptExecuted',
                           'inspectorActionExecuted', 'inspectorScenarioEventExecuted'):
                    continue
                elif t in ('error', 'chatSessionError'):
                    return {'text': '', 'error': msg.get('message', 'Unknown error')}

        return {
            'text': ''.join(chunks),
            'actions': actions,
            'message_id': message_id,
            'timeout': not reply_ended,
        }

    def stop_chat(self):
        """停止聊天"""
        self._send({"$type": "stopChat"})
        self.session_id = None

    def disconnect(self):
        """断开连接"""
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        self.connected = False

    def _wait_for(self, msg_type, key=None, default=None, timeout=10):
        """等待特定类型的消息,带超时"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = max(0.5, deadline - time.time())
            for msg in self._recv(timeout=min(3, remaining)):
                if msg.get('$type') == msg_type:
                    return msg.get(key, default) if key else msg
        return default

    def _send(self, obj):
        """发送SignalR消息"""
        payload = json.dumps({
            "arguments": [obj],
            "target": "SendMessage",
            "type": 1
        }) + self.SEPARATOR
        self.ws.send(payload)

    def _recv(self, timeout=5):
        """接收并解析SignalR消息(多帧循环,直到超时无新数据)"""
        deadline = time.time() + timeout
        while True:
            # Process leftover buffer data first (from abandoned generators)
            while self.SEPARATOR in self._buffer:
                idx = self._buffer.index(self.SEPARATOR)
                chunk = self._buffer[:idx]
                self._buffer = self._buffer[idx+1:]
                if not chunk or chunk == '{}':
                    continue
                try:
                    frame = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                if frame.get('type') == 6:
                    self.ws.send(chunk + self.SEPARATOR)
                    continue
                if frame.get('type') == 1:
                    args = frame.get('arguments', [])
                    if args:
                        yield args[0]

            remaining = deadline - time.time()
            if remaining <= 0:
                break
            self.ws.settimeout(min(remaining, 2.0))
            try:
                data = self.ws.recv()
            except Exception as e:
                # Socket timeout — check if overall deadline exceeded
                if 'timed out' in str(e).lower() or 'timeout' in type(e).__name__.lower():
                    if time.time() >= deadline:
                        break
                    continue
                break
            self._buffer += data


# ═══════════════════════════════════════════════════════
# 聊天引擎 (统一入口)
# ═══════════════════════════════════════════════════════

class ChatEngine:
    """
    统一聊天引擎 — 支持两种模式:
    1. standalone: 直接调LLM+TTS, 完全脱离Voxta
    2. voxta: 通过SignalR连接Voxta, 利用其管线
    """

    def __init__(self, mode='standalone', api_key=None):
        self.mode = mode
        self.char_loader = CharacterLoader()
        self.history = ConversationHistory()
        self.prompt_builder = PromptBuilder()
        self.tts = TTSClient()
        self.llm = LLMClient(api_key=api_key)
        self.voxta = None
        self.current_char = None
        self.chat_id = None

    def load_character(self, name_or_id):
        """加载角色"""
        self.current_char = self.char_loader.load(name_or_id)
        if self.current_char:
            self.chat_id = self.history.get_or_create_chat(self.current_char['id'])
        return self.current_char

    def chat(self, user_text, speak=False):
        """发送消息并获取回复"""
        if not self.current_char:
            return {'error': 'No character loaded'}

        if self.mode == 'voxta':
            return self._chat_voxta(user_text, speak)
        else:
            return self._chat_standalone(user_text, speak)

    def _chat_standalone(self, user_text, speak=False):
        """独立模式聊天 — 完全脱离Voxta"""
        char = self.current_char

        # 1. 获取对话历史 (SimpleMemory窗口)
        recent = self.history.get_recent(self.chat_id, MEMORY_WINDOW)

        # 2. 构建system prompt (人格注入)
        system_prompt = self.prompt_builder.build_system_prompt(
            char, user_name='User', memories=char.get('memories', [])
        )

        # 3. 构建messages数组
        messages = self.prompt_builder.build_messages(system_prompt, recent)
        messages.append({"role": "user", "content": user_text})

        # 4. 调用LLM (自动降级: dashscope -> deepseek -> local)
        result = self.llm.chat_with_fallback(messages, temperature=0.7)
        reply_text = result.get('text', '')

        if not reply_text:
            return {'error': result.get('error', 'Empty response'), 'messages_sent': len(messages)}

        # 5. 保存到DB
        self.history.save_message(self.chat_id, 'user', user_text)
        self.history.save_message(self.chat_id, 'assistant', reply_text, sender_id=char['id'])

        # 6. TTS (可选)
        tts_result = None
        if speak:
            voice = self.tts.get_voice_for_char(char)
            tts_result = self.tts.speak(reply_text, voice=voice)

        return {
            'text': reply_text,
            'character': char['name'],
            'usage': result.get('usage', {}),
            'model': result.get('model', ''),
            'tts': tts_result,
        }

    def _chat_voxta(self, user_text, speak=False):
        """Voxta连接模式 — 通过SignalR"""
        if not self.voxta or not self.voxta.connected:
            try:
                self.voxta = VoxtaSignalR()
                welcome = self.voxta.connect()
                if not welcome:
                    return {'error': 'Voxta connection failed'}
                # 启动聊天
                self.voxta.start_chat(self.current_char['id'])
            except Exception as e:
                return {'error': f'Voxta SignalR error: {e}'}

        self.voxta.send_message(user_text)
        reply = self.voxta.receive_reply()
        return reply

    def interactive(self):
        """交互式聊天循环"""
        if not self.current_char:
            print("请先加载角色: engine.load_character('角色名')")
            return

        char = self.current_char
        print(f"\n{'='*50}")
        print(f"  与 {char['name']} 对话 ({self.mode}模式)")
        print(f"  输入 /quit 退出, /speak 开启语音")
        print(f"{'='*50}\n")

        # 发送初始问候
        if char.get('first_message'):
            print(f"[{char['name']}] {char['first_message']}\n")

        speak = False
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue
            if user_input == '/quit':
                break
            if user_input == '/speak':
                speak = not speak
                print(f"  语音{'开启' if speak else '关闭'}")
                continue
            if user_input == '/status':
                print(f"  角色: {char['name']} | 模式: {self.mode}")
                print(f"  记忆: {len(char.get('memories', []))}条 | ChatID: {self.chat_id}")
                continue

            result = self.chat(user_input, speak=speak)
            if 'error' in result:
                print(f"  [ERROR] {result['error']}")
            else:
                text = result.get('text', '')
                print(f"\n[{char['name']}] {text}\n")

        if self.voxta:
            self.voxta.disconnect()
        print("对话结束")


# ═══════════════════════════════════════════════════════
# 动作推理 (Action Inference — 重新实现)
# ═══════════════════════════════════════════════════════

class ActionInference:
    """
    重新实现Voxta的动作推理:
    从AI回复中提取动作标签 [action] 或 *action*
    """

    KNOWN_ACTIONS = [
        'smile', 'laugh', 'frown', 'cry', 'angry', 'surprised',
        'blush', 'wink', 'nod', 'shake_head', 'wave', 'hug',
        'kiss', 'dance', 'sing', 'think', 'confused', 'excited',
        'sad', 'nervous', 'shy', 'proud', 'scared', 'sleepy',
    ]

    @staticmethod
    def extract_actions(text):
        """从回复文本中提取动作"""
        import re
        actions = []
        # 匹配 *action* 格式
        star_actions = re.findall(r'\*([^*]+)\*', text)
        for a in star_actions:
            actions.append({'type': 'emote', 'value': a.strip()})

        # 匹配 [action] 格式
        bracket_actions = re.findall(r'\[([^\]]+)\]', text)
        for a in bracket_actions:
            actions.append({'type': 'action', 'value': a.strip()})

        return actions

    @staticmethod
    def clean_text(text):
        """移除动作标签,返回纯文本"""
        import re
        text = re.sub(r'\*[^*]+\*', '', text)
        text = re.sub(r'\[[^\]]+\]', '', text)
        return text.strip()


# ═══════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════

def main():
    commands = {
        'chat': '与角色对话 (角色名/ID)',
        'chat-voxta': '通过Voxta对话 (角色名/ID)',
        'list': '列出所有角色',
        'info': '角色信息 (角色名/ID)',
        'prompt': '显示构建的system prompt (角色名/ID)',
        'test-llm': '测试LLM连接',
        'test-tts': '测试TTS (文本)',
    }

    if len(sys.argv) < 2:
        print("VAM-agent ChatEngine — 脱离Voxta独立运行的聊天引擎")
        print("\n命令:")
        for cmd, desc in commands.items():
            print(f"  {cmd:14s}  {desc}")
        return

    cmd = sys.argv[1]

    if cmd == 'list':
        loader = CharacterLoader()
        for c in loader.list_all():
            print(f"  {c['Name']:14s} [{c['Culture']}] {(c['Description'] or '')[:40]}")

    elif cmd == 'info' and len(sys.argv) > 2:
        loader = CharacterLoader()
        char = loader.load(sys.argv[2])
        if char:
            print(json.dumps({k: v for k, v in char.items() if k != 'memories'},
                           ensure_ascii=False, indent=2, default=str))
            print(f"\n记忆: {len(char.get('memories', []))}条")
        else:
            print(f"角色未找到: {sys.argv[2]}")

    elif cmd == 'prompt' and len(sys.argv) > 2:
        loader = CharacterLoader()
        char = loader.load(sys.argv[2])
        if char:
            prompt = PromptBuilder.build_system_prompt(char, memories=char.get('memories', []))
            print(f"=== System Prompt for {char['name']} ===")
            print(prompt)
            print(f"\n=== Length: {len(prompt)} chars ===")
        else:
            print(f"角色未找到: {sys.argv[2]}")

    elif cmd == 'test-llm':
        llm = LLMClient()
        result = llm.chat_local([{"role": "user", "content": "Hello, respond in one word."}])
        if result.get('error'):
            print(f"本地LLM: FAIL ({result['error']})")
        else:
            print(f"本地LLM: OK — {result.get('text', '')[:60]}")

    elif cmd == 'test-tts' and len(sys.argv) > 2:
        text = ' '.join(sys.argv[2:])
        tts = TTSClient()
        result = tts.speak(text)
        print(f"TTS: {'OK' if result.get('ok') else 'FAIL'} — {result}")

    elif cmd in ('chat', 'chat-voxta') and len(sys.argv) > 2:
        mode = 'voxta' if cmd == 'chat-voxta' else 'standalone'
        engine = ChatEngine(mode=mode)
        char = engine.load_character(sys.argv[2])
        if not char:
            print(f"角色未找到: {sys.argv[2]}")
            return
        engine.interactive()

    else:
        print(f"未知命令: {cmd}")


if __name__ == '__main__':
    main()
