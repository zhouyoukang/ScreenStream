"""
Voxta 聊天引擎 — 脱离Voxta独立运行 + Voxta SignalR代理 双模式

从 tools/chat_engine.py 整合至此，统一管理:
  1. 角色加载器 (CharacterLoader) — 从DB加载角色完整数据
  2. 对话历史 (ConversationHistory) — 读写ChatMessages表
  3. Prompt构建器 (PromptBuilder) — 重新实现Voxta人格注入
  4. LLM直调 (LLMClient) — DashScope/DeepSeek/本地 自动降级
  5. TTS直调 (TTSClient) — EdgeTTS
  6. 动作推理 (ActionInference) — 从回复提取动作标签
  7. 聊天引擎 (ChatEngine) — standalone/voxta双模式统一入口
"""
import json
import logging
import os
import re
import time
import uuid
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional

from .config import VOXTA_CONFIG
from .db import _db_conn

_log = logging.getLogger(__name__)


def _load_secrets_env():
    """Load API keys from secrets.env if present (fallback for os.environ)"""
    secrets_path = VOXTA_CONFIG.AGENT_ROOT.parent / 'secrets.env'
    if not secrets_path.exists():
        return
    try:
        for line in secrets_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, val = line.partition('=')
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and val and key not in os.environ:
                os.environ[key] = val
    except Exception as e:
        _log.debug("Failed to load secrets.env: %s", e)


_load_secrets_env()

# ── 常量 ──

MEMORY_WINDOW = 12       # 最近N轮对话作为上下文
MAX_SYSTEM_TOKENS = 2000 # system prompt最大长度(字符近似)
MAX_REPLY_TOKENS = 500   # LLM回复最大token

DASHSCOPE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEEPSEEK_URL = "https://api.deepseek.com/v1"
OLLAMA_URL = "http://localhost:11434/v1"
LMSTUDIO_URL = "http://localhost:1234/v1"

# ── Voxta脚本API常量 (from voxta_unoffical_docs) ──

VOXTA_SCRIPT_TRIGGERS = [
    'start', 'messageReceived', 'messageSent', 'replyReceived',
    'replyChunk', 'speechRecognitionStart', 'speechRecognitionEnd',
    'speechRecognitionPartial', 'actionInferred', 'contextUpdated',
]

VOXTA_KNOWN_ACTIONS = [
    'smile', 'laugh', 'frown', 'cry', 'angry', 'surprised',
    'blush', 'wink', 'nod', 'shake_head', 'wave', 'hug',
    'kiss', 'dance', 'sing', 'think', 'confused', 'excited',
    'sad', 'nervous', 'shy', 'proud', 'scared', 'sleepy',
    'idle', 'walk', 'sit', 'stand', 'point', 'clap',
]

VOXTA_MESSAGE_ROLES = {
    'User': 1, 'Assistant': 3, 'System': 0,
    'Summary': 4, 'Event': 5, 'Instructions': 6,
    'Note': 7, 'Secret': 8,
}


# ═══════════════════════════════════════════════════════
# 角色加载器
# ═══════════════════════════════════════════════════════

class CharacterLoader:
    """从Voxta DB加载角色完整数据"""

    def load(self, char_id_or_name: str) -> Optional[dict]:
        """通过ID前缀或名称加载角色"""
        with _db_conn() as db:
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
                row = db.execute("SELECT * FROM Characters WHERE Name=?",
                                 (char_id_or_name,)).fetchone()
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

    def list_all(self) -> list:
        with _db_conn() as db:
            rows = db.execute(
                "SELECT LocalId, Name, Culture, Description FROM Characters"
            ).fetchall()
            return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════
# 对话历史管理
# ═══════════════════════════════════════════════════════

class ConversationHistory:
    """对话历史 — 读写Voxta DB ChatMessages表"""

    def get_recent(self, chat_id=None, limit=MEMORY_WINDOW) -> list:
        """获取最近N条对话"""
        with _db_conn() as db:
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

        messages = []
        for r in reversed(rows):
            d = dict(r)
            role_map = {0: 'system', 1: 'user', 2: 'user', 3: 'assistant', 8: 'system'}
            role = role_map.get(d.get('Role', 0), 'user')
            text = d.get('Value', '') or ''
            if text:
                messages.append({'role': role, 'content': text})
        return messages

    def save_message(self, chat_id: str, role: str, text: str,
                     sender_id: str = 'agent') -> str:
        """保存消息到DB"""
        with _db_conn(readonly=False) as db:
            role_num = {'system': 0, 'user': 2, 'assistant': 3}.get(role, 2)
            msg_id = str(uuid.uuid4()).upper()
            now = datetime.now().isoformat()

            row = db.execute(
                "SELECT MAX([Index]) as mx FROM ChatMessages WHERE ChatId=?",
                (chat_id,)
            ).fetchone()
            idx = (dict(row).get('mx', 0) or 0) + 1

            user_id = ConversationHistory._get_user_id()
            db.execute("""INSERT INTO ChatMessages (
                UserId, LocalId, ChatId, SenderId, Timestamp, [Index],
                ConversationIndex, ChatTime, Role, Value, Tokens
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
                user_id, msg_id, chat_id, sender_id, now, idx,
                idx, 0, role_num, text, len(text) // 4
            ))
            db.commit()
        return msg_id

    def get_or_create_chat(self, character_id: str) -> str:
        """获取角色最新chat,或创建新chat
        
        Chats表结构: Characters列是JSONB数组(如 ["UUID"]),不是单独的CharacterId列
        """
        user_id = self._get_user_id()
        with _db_conn(readonly=False) as db:
            # Characters列是JSONB数组, 用LIKE搜索包含该角色ID的chat
            rows = db.execute(
                "SELECT LocalId FROM Chats WHERE Characters LIKE ? ORDER BY rowid DESC LIMIT 1",
                ('%' + character_id + '%',)
            ).fetchall()
            if rows:
                chat_id = dict(rows[0])['LocalId']
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
                except Exception as e:
                    _log.warning("get_or_create_chat: insert failed: %s", e)
        return chat_id

    @staticmethod
    def _get_user_id() -> str:
        """获取Voxta DB中的UserId"""
        try:
            with _db_conn() as db:
                row = db.execute("SELECT Id FROM Users LIMIT 1").fetchone()
                if row:
                    return dict(row)['Id']
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
    def build_system_prompt(char: dict, user_name: str = 'User',
                            memories: list = None) -> str:
        """构建system prompt — 等效于Voxta的personality injection"""
        parts = []

        if char.get('profile'):
            parts.append(char['profile'])
        if char.get('personality'):
            parts.append(f"\nPersonality: {char['personality']}")
        if char.get('description'):
            parts.append(f"\nDescription: {char['description']}")
        if memories:
            mem_text = "\n".join(f"- {m}" for m in memories[:10])
            parts.append(f"\nRelevant memories:\n{mem_text}")
        if char.get('message_examples'):
            parts.append(f"\nMessage examples:\n{char['message_examples']}")

        parts.append(f"\nThe user's name is {user_name}.")

        culture = char.get('culture', 'zh-CN')
        if culture.startswith('zh'):
            parts.append("\nAlways respond in Chinese (简体中文).")
        elif culture.startswith('en'):
            parts.append("\nAlways respond in English.")

        return "\n".join(parts)

    @staticmethod
    def build_messages(system_prompt: str, history: list,
                       char_name: str = 'Assistant') -> list:
        """构建OpenAI-compatible messages数组"""
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role in ('user', 'assistant', 'system'):
                messages.append({"role": role, "content": content})
        return messages


# ═══════════════════════════════════════════════════════
# LLM直调 (多后端自动降级)
# ═══════════════════════════════════════════════════════

class LLMClient:
    """直接调用LLM API — 绕过Voxta，支持多后端自动降级"""

    BACKENDS = [
        ('dashscope', DASHSCOPE_URL, 'qwen-plus', 'DASHSCOPE_API_KEY'),
        ('deepseek', DEEPSEEK_URL, 'deepseek-chat', 'DEEPSEEK_API_KEY'),
        ('ollama', OLLAMA_URL, None, None),
        ('lmstudio', LMSTUDIO_URL, None, None),
        ('local', 'http://localhost:7860/v1', None, None),
    ]

    def __init__(self, api_key: str = None, base_url: str = None,
                 model: str = 'qwen-plus', backend: str = None):
        self.api_key = api_key
        self.base_url = base_url or DASHSCOPE_URL
        self.model = model
        self.backend = backend

    @staticmethod
    def _filter_think(text: str) -> str:
        """过滤DeepSeek R1系列的<think>标签。

        从ai_virtual_mate_comm think_filter_switch()移植。
        """
        if '</think>' in text:
            text = text.split('</think>')[-1].strip()
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        return text

    def chat(self, messages: list, max_tokens: int = MAX_REPLY_TOKENS,
             temperature: float = 0.7, stream: bool = False) -> dict:
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

    def chat_with_fallback(self, messages: list,
                           max_tokens: int = MAX_REPLY_TOKENS,
                           temperature: float = 0.7) -> dict:
        """自动降级调用: dashscope -> deepseek -> local"""
        backends = self.BACKENDS
        if self.backend:
            backends = [b for b in backends if b[0] == self.backend] or backends

        # Save original state to restore after iteration
        orig_url, orig_model, orig_key = self.base_url, self.model, self.api_key

        errors = []
        for name, url, model, env_key in backends:
            api_key = os.environ.get(env_key, '') if env_key else None
            if env_key and not api_key:
                continue
            self.base_url = url
            self.model = model or 'default'
            self.api_key = api_key or orig_key
            result = self.chat(messages, max_tokens, temperature)
            if result.get('text'):
                result['backend'] = name
                return result
            errors.append(f"{name}: {result.get('error', 'empty')}")

        # Restore original state on total failure
        self.base_url, self.model, self.api_key = orig_url, orig_model, orig_key
        return {'text': '', 'error': f"All backends failed: {'; '.join(errors)}"}

    def chat_local(self, messages: list,
                   max_tokens: int = MAX_REPLY_TOKENS,
                   temperature: float = 0.7) -> dict:
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

    def __init__(self, base_url: str = None):
        svc = VOXTA_CONFIG.SERVICES.get("edgetts", {})
        self.base_url = base_url or f"http://localhost:{svc.get('port', 5050)}"

    def speak(self, text: str, voice: str = 'nova',
              output_path: str = None) -> dict:
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

    def get_voice_for_char(self, char: dict) -> str:
        """根据角色TTS配置获取voice参数"""
        tts = char.get('tts', [])
        if tts:
            first = tts[0]
            voice_params = first.get('voice', {}).get('parameters', {})
            return voice_params.get('voice_id', 'nova')
        culture = char.get('culture', 'zh-CN')
        if culture.startswith('zh'):
            return 'nova'
        return 'alloy'


# ═══════════════════════════════════════════════════════
# 动作推理 (Action Inference)
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
    def extract_actions(text: str) -> list:
        """从回复文本中提取动作"""
        actions = []
        for a in re.findall(r'\*([^*]+)\*', text):
            actions.append({'type': 'emote', 'value': a.strip()})
        for a in re.findall(r'\[([^\]]+)\]', text):
            actions.append({'type': 'action', 'value': a.strip()})
        return actions

    @staticmethod
    def clean_text(text: str) -> str:
        """移除动作标签,返回纯文本"""
        text = re.sub(r'\*[^*]+\*', '', text)
        text = re.sub(r'\[[^\]]+\]', '', text)
        return text.strip()


# ═══════════════════════════════════════════════════════
# 聊天引擎 (统一入口)
# ═══════════════════════════════════════════════════════

class ChatEngine:
    """
    统一聊天引擎 — 支持两种模式:
    1. standalone: 直接调LLM+TTS, 完全脱离Voxta
    2. voxta: 通过SignalR连接Voxta, 利用其管线
    """

    def __init__(self, mode: str = 'standalone', api_key: str = None):
        self.mode = mode
        self.char_loader = CharacterLoader()
        self.history = ConversationHistory()
        self.prompt_builder = PromptBuilder()
        self.tts = TTSClient()
        self.llm = LLMClient(api_key=api_key)
        self.voxta = None
        self.current_char = None
        self.chat_id = None

    def load_character(self, name_or_id: str) -> Optional[dict]:
        """加载角色"""
        self.current_char = self.char_loader.load(name_or_id)
        if self.current_char:
            self.chat_id = self.history.get_or_create_chat(self.current_char['id'])
        return self.current_char

    def chat(self, user_text: str, speak: bool = False) -> dict:
        """发送消息并获取回复"""
        if not self.current_char:
            return {'error': 'No character loaded'}

        if self.mode == 'voxta':
            return self._chat_voxta(user_text, speak)
        else:
            return self._chat_standalone(user_text, speak)

    def _chat_standalone(self, user_text: str, speak: bool = False) -> dict:
        """独立模式聊天 — 完全脱离Voxta"""
        char = self.current_char

        recent = self.history.get_recent(self.chat_id, MEMORY_WINDOW)
        system_prompt = self.prompt_builder.build_system_prompt(
            char, user_name='User', memories=char.get('memories', [])
        )
        messages = self.prompt_builder.build_messages(system_prompt, recent)
        messages.append({"role": "user", "content": user_text})

        result = self.llm.chat_with_fallback(messages, temperature=0.7)
        reply_text = result.get('text', '')

        if not reply_text:
            return {'error': result.get('error', 'Empty response'),
                    'messages_sent': len(messages)}

        self.history.save_message(self.chat_id, 'user', user_text)
        self.history.save_message(self.chat_id, 'assistant', reply_text,
                                  sender_id=char['id'])

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

    def _chat_voxta(self, user_text: str, speak: bool = False) -> dict:
        """Voxta连接模式 — 通过SignalR"""
        from .signalr import VoxtaSignalR

        if not self.voxta or not self.voxta.connected:
            try:
                self.voxta = VoxtaSignalR()
                welcome = self.voxta.connect()
                if not welcome:
                    return {'error': 'Voxta connection failed'}
                started = self.voxta.start_chat(self.current_char['id'])
                if not started or started.get('$type') in ('error', 'chatSessionError'):
                    return {'error': f'Chat start failed: {started}'}
                greeting = self.voxta.handle_greeting()
            except Exception as e:
                return {'error': f'Voxta SignalR error: {e}'}

        self.voxta.send_message(user_text)
        reply = self.voxta.receive_reply()

        if reply.get('message_id'):
            self.voxta.acknowledge_playback(reply['message_id'])

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
