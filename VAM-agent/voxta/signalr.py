"""
Voxta SignalR 桥接 — 实时WebSocket通信

从 vam/signalr.py 迁移至此。
协议参考: voxta/docs/SIGNALR_PROTOCOL.md
"""
import json
import time
from typing import Optional

from .config import VOXTA_CONFIG


SEPARATOR = '\x1e'
CLIENT_NAME = 'VAM-agent.Unified'
API_VERSION = '2025-08'


class VoxtaSignalR:
    """Voxta SignalR 实时客户端"""

    def __init__(self, host: str = None, port: int = None):
        svc = VOXTA_CONFIG.SERVICES.get("voxta", {})
        self.host = host or "localhost"
        self.port = port or svc.get("port", 5384)
        self.ws = None
        self.session_id = None
        self.connected = False
        self._buffer = ''

    # ── 连接 ──

    def connect(self) -> Optional[dict]:
        """建立SignalR连接并认证"""
        try:
            import websocket
        except ImportError:
            raise ImportError("需要安装 websocket-client: pip install websocket-client")

        url = f"ws://{self.host}:{self.port}/hub"
        self.ws = websocket.create_connection(url, timeout=10)

        # 握手
        self.ws.send('{"protocol":"json","version":1}' + SEPARATOR)
        resp = self.ws.recv()
        if not resp.startswith('{}'):
            raise ConnectionError(f"SignalR handshake failed: {resp}")

        # 认证
        self._send({
            "$type": "authenticate",
            "client": CLIENT_NAME,
            "clientVersion": "1.0.0",
            "scope": ["role:app"],
            "capabilities": {"audioOutput": "Url"},
            "apiVersion": API_VERSION,
        })
        self.connected = True

        for msg in self._recv():
            if msg.get('$type') == 'welcome':
                return msg
        return None

    def disconnect(self):
        """断开连接"""
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        self.connected = False
        self.session_id = None

    # ── 角色/场景/聊天列表 ──

    def load_characters(self) -> list:
        self._send({"$type": "loadCharactersList"})
        return self._wait_for('charactersListLoaded', 'characters', [])

    def load_scenarios(self) -> list:
        self._send({"$type": "loadScenariosList"})
        return self._wait_for('scenariosListLoaded', 'scenarios', [])

    def load_chats(self, character_id: str, scenario_id: str = None) -> list:
        msg = {"$type": "loadChatsList", "characterId": character_id}
        if scenario_id:
            msg["scenarioId"] = scenario_id
        self._send(msg)
        return self._wait_for('chatsListLoaded', 'chats', [])

    # ── 聊天会话 ──

    def start_chat(self, character_id: str, scenario_id: str = None,
                   chat_id: str = None, _retry: bool = True) -> Optional[dict]:
        """启动聊天会话 (自动恢复zombie chat)"""
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

        SKIP_TYPES = {
            'chatLoading', 'chatLoadingMessage', 'chatConfiguration',
            'moduleRuntimeInstances', 'configuration', 'contextUpdated',
            'chatFlow', 'recordingStatus', 'memoryUpdated',
            'chatParticipantsUpdated', 'chatsSessionsUpdated',
            'downloadProgress', 'inspectorEnabled',
        }

        deadline = time.time() + 30
        while time.time() < deadline:
            remaining = max(0.5, deadline - time.time())
            for response in self._recv(timeout=min(5, remaining)):
                t = response.get('$type', '')
                if t in ('chatStarted', 'chatStarting'):
                    self.session_id = response.get('sessionId')
                    if t == 'chatStarted':
                        return response
                elif t in SKIP_TYPES:
                    continue
                elif t in ('error', 'chatSessionError', 'chatInProgress'):
                    # Auto-recover: any error during start_chat → stop + retry
                    if _retry:
                        self._send({"$type": "stopChat"})
                        self.drain(timeout=3)
                        return self.start_chat(character_id, scenario_id,
                                               chat_id, _retry=False)
                    return response
                elif t == 'replyChunk':
                    # greeting started — let handle_greeting() deal with it
                    return response
        return None

    def handle_greeting(self, timeout: int = 10) -> dict:
        """处理greeting: 收集文本 → 捕获messageId → acknowledge playback
        
        必须在start_chat()之后、send_message()之前调用。
        Voxta服务器在greeting playback未确认前会阻塞新输入。
        
        关键时序: replyEnd后不能立即ack，需等待服务器发送
        recordingStatus/chatFlow等状态消息，否则后续send无回复。
        """
        chunks = []
        greeting_msg_id = None
        
        for msg in self._recv(timeout=timeout):
            t = msg.get('$type', '')
            if t == 'replyChunk':
                chunks.append(msg.get('text', ''))
            elif t == 'replyEnd':
                greeting_msg_id = msg.get('messageId')
                break
        
        if greeting_msg_id:
            # Drain post-replyEnd state messages (recordingStatus, chatFlow)
            # Server needs these processed before ack
            for _ in self._recv(timeout=2):
                pass
            # Acknowledge playback (critical — server blocks without this)
            self.acknowledge_playback(greeting_msg_id)
            # Drain post-ack messages (STT cycle: ~3s of speechRecognitionPartial)
            for _ in self._recv(timeout=5):
                pass
        
        return {
            'text': ''.join(chunks),
            'message_id': greeting_msg_id,
            'acknowledged': greeting_msg_id is not None,
        }

    def stop_chat(self):
        """停止聊天"""
        self._send({"$type": "stopChat"})
        self.session_id = None

    # ── 消息收发 ──

    def send_message(self, text: str, do_reply: bool = True,
                     do_action: bool = True):
        """发送用户消息"""
        if not self.session_id:
            return
        self.drain(timeout=1)
        self._send({
            "$type": "send",
            "sessionId": self.session_id,
            "text": text,
            "doReply": do_reply,
            "doCharacterActionInference": do_action,
        })

    def receive_reply(self, timeout: int = 30, action_wait: int = 5) -> dict:
        """接收AI回复（收集所有chunks + 等待action/appTrigger）"""
        chunks = []
        actions = []
        message_id = None
        start = time.time()
        reply_ended = False
        action_deadline = None

        SKIP = {
            'replyGenerating', 'replyStart', 'chatFlow',
            'speechRecognitionStart', 'speechRecognitionEnd',
            'speechPlaybackStart', 'speechPlaybackComplete',
            'memoryUpdated', 'contextUpdated', 'replyCancelled',
            'recordingStatus', 'chatConfiguration', 'configuration',
            'moduleRuntimeInstances', 'downloadProgress',
            'chatParticipantsUpdated', 'chatsSessionsUpdated',
            'interruptSpeech', 'update', 'inspectorEnabled',
            'inspectorScriptExecuted', 'inspectorActionExecuted',
            'inspectorScenarioEventExecuted',
        }

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
                    args = [str(a) if a is not None else ''
                            for a in msg.get('arguments', [])]
                    actions.append(f"{msg.get('name', '')}({','.join(args)})")
                elif t in SKIP:
                    continue
                elif t in ('error', 'chatSessionError'):
                    return {'text': '', 'error': msg.get('message', 'Unknown error')}

        return {
            'text': ''.join(chunks),
            'actions': actions,
            'message_id': message_id,
            'timeout': not reply_ended,
        }

    def acknowledge_playback(self, message_id: str, duration: float = 1.0):
        """确认语音播放完成"""
        if not self.session_id or not message_id:
            return
        self._send({
            "$type": "speechPlaybackStart",
            "sessionId": self.session_id,
            "messageId": message_id,
            "startIndex": 0, "endIndex": 0,
            "duration": duration, "isNarration": False,
        })
        time.sleep(0.3)
        self._send({
            "$type": "speechPlaybackComplete",
            "sessionId": self.session_id,
            "messageId": message_id,
        })

    # ── 上下文/标志/动作 ──

    def set_flags(self, *flags):
        """设置场景标志（如 'emotes'）"""
        if not self.session_id:
            return
        flat = []
        for f in flags:
            if isinstance(f, str):
                flat.extend(x.strip() for x in f.split(',') if x.strip())
            else:
                flat.append(str(f))
        self._send({
            "$type": "updateContext",
            "sessionId": self.session_id,
            "setFlags": flat,
        })

    def update_context(self, context: str = None, actions: list = None,
                       context_key: str = "VAM-agent/Base"):
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

    def drain(self, timeout: int = 3):
        """消耗所有待处理消息"""
        for _ in self._recv(timeout=timeout):
            pass

    # ── 内部 ──

    def _wait_for(self, msg_type, key=None, default=None, timeout=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = max(0.5, deadline - time.time())
            for msg in self._recv(timeout=min(3, remaining)):
                if msg.get('$type') == msg_type:
                    return msg.get(key, default) if key else msg
        return default

    def _send(self, obj):
        payload = json.dumps({
            "arguments": [obj],
            "target": "SendMessage",
            "type": 1,
        }) + SEPARATOR
        self.ws.send(payload)

    def _recv(self, timeout=5):
        deadline = time.time() + timeout
        while True:
            while SEPARATOR in self._buffer:
                idx = self._buffer.index(SEPARATOR)
                chunk = self._buffer[:idx]
                self._buffer = self._buffer[idx + 1:]
                if not chunk or chunk == '{}':
                    continue
                try:
                    frame = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                if frame.get('type') == 6:
                    self.ws.send(chunk + SEPARATOR)
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
                # Socket timeout — retry until overall deadline
                if 'timed out' in str(e).lower() or 'timeout' in type(e).__name__.lower():
                    if time.time() >= deadline:
                        break
                    continue
                break  # Real errors (connection closed, etc.)
            self._buffer += data


# ── 便捷函数 ──

def quick_chat(character_id: str, text: str, scenario_id: str = None) -> dict:
    """快捷对话: 连接→开聊→处理greeting→发消息→收回复→断开"""
    client = VoxtaSignalR()
    try:
        welcome = client.connect()
        if not welcome:
            return {"error": "Voxta connection failed"}

        started = client.start_chat(character_id, scenario_id)
        if not started or started.get('$type') in ('error', 'chatSessionError'):
            return {"error": f"Chat start failed: {started}"}

        # 处理greeting (critical — 不ack则Voxta阻塞)
        greeting = client.handle_greeting()

        client.send_message(text)
        reply = client.receive_reply()

        if reply.get('message_id'):
            client.acknowledge_playback(reply['message_id'])

        reply['greeting'] = greeting.get('text', '')
        client.stop_chat()
        return reply
    except Exception as e:
        return {"error": str(e)}
    finally:
        client.disconnect()


def check_signalr() -> dict:
    """检测Voxta SignalR是否可连接"""
    client = VoxtaSignalR()
    try:
        welcome = client.connect()
        if welcome:
            version = welcome.get('voxtaServerVersion', 'unknown')
            api_ver = welcome.get('apiVersion', 'unknown')
            client.disconnect()
            return {
                "connected": True,
                "version": version,
                "api_version": api_ver,
            }
        return {"connected": False, "error": "No welcome message"}
    except Exception as e:
        return {"connected": False, "error": str(e)}
