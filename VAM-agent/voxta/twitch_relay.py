"""
Voxta Twitch Relay — Twitch聊天→Voxta AI对话桥接

从以下外部项目提取核心逻辑:
  - dion-labs/voxta-twitch-relay: TwitchIO→Voxta Gateway relay (MIT)
  - 消息队列/健康检查/直播状态检测/优先级过滤

架构:
  TwitchRelayConfig  — Twitch连接配置
  MessageFilter      — 消息过滤器 (去重/速率限制/黑名单)
  TwitchRelay        — 主中继类 (Twitch消息→Voxta对话)
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable

logger = logging.getLogger("voxta.twitch_relay")


@dataclass
class TwitchRelayConfig:
    """Twitch连接配置"""
    token: str = ""
    client_id: str = ""
    client_secret: str = ""
    channel: str = ""
    bot_nick: str = "VoxtaBot"
    prefix: str = "!"
    ignored_users: list[str] = field(default_factory=lambda: ["nightbot", "streamelements", "moobot"])
    immediate_reply: bool = True
    max_queue_size: int = 50
    health_check_interval: float = 30.0
    stream_check_interval: float = 60.0
    rate_limit_per_user: float = 5.0
    min_message_length: int = 2
    max_message_length: int = 500


class MessageFilter:
    """消息过滤器 — 去重/速率限制/黑名单/长度检查"""

    def __init__(self, config: TwitchRelayConfig):
        self.config = config
        self.user_last_msg: dict[str, float] = {}
        self.recent_messages: list[str] = []
        self.blocked_words: list[str] = []

    def should_relay(self, author: str, text: str) -> tuple[bool, str]:
        """检查消息是否应该转发，返回 (是否通过, 原因)"""
        author_lower = author.lower()

        if author_lower in [u.lower() for u in self.config.ignored_users]:
            return False, "ignored_user"

        if len(text) < self.config.min_message_length:
            return False, "too_short"

        if len(text) > self.config.max_message_length:
            return False, "too_long"

        now = time.time()
        if author_lower in self.user_last_msg:
            elapsed = now - self.user_last_msg[author_lower]
            if elapsed < self.config.rate_limit_per_user:
                return False, "rate_limited"

        for word in self.blocked_words:
            if word.lower() in text.lower():
                return False, "blocked_word"

        if text in self.recent_messages[-10:]:
            return False, "duplicate"

        self.user_last_msg[author_lower] = now
        self.recent_messages.append(text)
        if len(self.recent_messages) > 100:
            self.recent_messages = self.recent_messages[-50:]

        return True, "ok"

    def add_blocked_word(self, word: str) -> None:
        if word not in self.blocked_words:
            self.blocked_words.append(word)

    def stats(self) -> dict:
        return {
            "tracked_users": len(self.user_last_msg),
            "recent_messages": len(self.recent_messages),
            "blocked_words": len(self.blocked_words),
        }


@dataclass
class RelayedMessage:
    """已转发的消息记录"""
    text: str
    author: str
    timestamp: float
    status: str = "pending"
    relayed_at: float = 0.0
    error: str = ""


class TwitchRelay:
    """
    Twitch→Voxta消息中继

    用法:
        config = TwitchRelayConfig(token="oauth:xxx", channel="my_channel")
        relay = TwitchRelay(config)
        relay.set_send_callback(my_voxta_send_fn)
        await relay.relay_message("user123", "Hello AI!")

    与Voxta SignalR集成:
        from voxta.signalr import VoxtaSignalR
        sr = VoxtaSignalR()
        relay.set_send_callback(
            lambda text, author: sr.send_user_message(f"[Twitch:{author}] {text}")
        )
    """

    def __init__(self, config: Optional[TwitchRelayConfig] = None):
        self.config = config or TwitchRelayConfig()
        self.filter = MessageFilter(self.config)
        self.message_queue: list[RelayedMessage] = []
        self.relayed_history: list[RelayedMessage] = []
        self.is_connected: bool = False
        self.chat_active: bool = False
        self.stream_live: bool = False
        self._send_callback: Optional[Callable] = None
        self._stats = {
            "total_received": 0,
            "total_relayed": 0,
            "total_filtered": 0,
            "total_errors": 0,
        }

    def set_send_callback(self, callback: Callable[..., Awaitable]) -> None:
        """设置消息发送回调 (async function)"""
        self._send_callback = callback

    async def relay_message(self, author: str, text: str,
                            source: str = "twitch") -> dict:
        """转发消息到Voxta"""
        self._stats["total_received"] += 1

        should_relay, reason = self.filter.should_relay(author, text)
        if not should_relay:
            self._stats["total_filtered"] += 1
            return {"status": "filtered", "reason": reason}

        msg = RelayedMessage(
            text=text, author=author, timestamp=time.time()
        )

        if not self.chat_active:
            if len(self.message_queue) < self.config.max_queue_size:
                self.message_queue.append(msg)
                return {"status": "queued", "queue_size": len(self.message_queue)}
            return {"status": "queue_full"}

        return await self._do_relay(msg, source)

    async def _do_relay(self, msg: RelayedMessage,
                        source: str = "twitch") -> dict:
        """执行实际转发"""
        if not self._send_callback:
            return {"status": "error", "reason": "no_callback"}

        try:
            formatted = f"[{source}:{msg.author}] {msg.text}"
            await self._send_callback(formatted, msg.author)
            msg.status = "relayed"
            msg.relayed_at = time.time()
            self._stats["total_relayed"] += 1
            self.relayed_history.append(msg)
            if len(self.relayed_history) > 100:
                self.relayed_history = self.relayed_history[-50:]
            return {"status": "relayed"}
        except Exception as e:
            msg.status = "error"
            msg.error = str(e)
            self._stats["total_errors"] += 1
            self.message_queue.append(msg)
            logger.error(f"Relay failed: {e}")
            return {"status": "error", "reason": str(e)}

    async def process_queue(self) -> int:
        """处理排队的消息"""
        if not self.message_queue or not self.chat_active:
            return 0

        processed = 0
        queue_copy = self.message_queue[:]
        self.message_queue.clear()

        for msg in queue_copy:
            result = await self._do_relay(msg)
            if result["status"] == "relayed":
                processed += 1

        return processed

    def set_chat_active(self, active: bool) -> None:
        self.chat_active = active

    def set_connected(self, connected: bool) -> None:
        self.is_connected = connected

    def summary(self) -> dict:
        return {
            "config": {
                "channel": self.config.channel,
                "bot_nick": self.config.bot_nick,
                "immediate_reply": self.config.immediate_reply,
            },
            "state": {
                "connected": self.is_connected,
                "chat_active": self.chat_active,
                "stream_live": self.stream_live,
                "queue_size": len(self.message_queue),
                "history_size": len(self.relayed_history),
            },
            "stats": self._stats.copy(),
            "filter": self.filter.stats(),
        }


# ── 便捷函数 ──

def create_twitch_relay(channel: str, token: str = "",
                        ignored_users: Optional[list[str]] = None) -> TwitchRelay:
    """快速创建Twitch中继"""
    config = TwitchRelayConfig(
        token=token,
        channel=channel,
        ignored_users=ignored_users or ["nightbot", "streamelements"],
    )
    return TwitchRelay(config)
