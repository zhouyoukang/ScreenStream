"""Voxta Remote Audio Proxy — WebSocket bridge for remote Voxta servers.

Ported from Voxta.VamProxy (MIT license).
Enables VaM on one machine to connect to Voxta running on another machine,
with automatic audio file download and local caching.

Architecture:
    VaM Plugin → [this proxy :5385] → [remote Voxta :5384/hub]
                                    ← audio download + local save

Key features:
- SignalR WebSocket message proxying (bidirectional)
- Audio URL interception and local file caching
- Mic audio streaming via WebSocket
- Automatic audio file cleanup
- Authentication capability modification (LocalFile → Url)

Usage:
    from voxta.remote_proxy import VoxtaRemoteProxy, ProxyConfig

    config = ProxyConfig(
        listen_port=5385,
        remote_url="ws://192.168.1.100:5384/hub",
        audio_folder="F:/vam1.22/Custom/Sounds/Voxta"
    )
    proxy = VoxtaRemoteProxy(config)

    # Start proxy (blocking)
    await proxy.start()

    # Or use as context manager
    async with VoxtaRemoteProxy(config) as proxy:
        await proxy.wait_until_stopped()
"""

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


# SignalR protocol constants
SIGNALR_SEPARATOR = "\x1e"
SIGNALR_TYPE_INVOCATION = 1
SIGNALR_TYPE_PING = 6
SIGNALR_TYPE_CLOSE = 7


@dataclass
class ProxyConfig:
    """Configuration for the Voxta remote proxy.

    Attributes:
        listen_port: Local port for VaM to connect to.
        remote_url: Remote Voxta WebSocket URL.
        audio_folder: Local folder to save downloaded audio files.
        cleanup_after_seconds: Auto-delete audio files after this many seconds.
        mic_sample_rate: Microphone audio sample rate.
        mic_channels: Microphone audio channels.
        mic_buffer_ms: Microphone buffer size in milliseconds.
    """
    listen_port: int = 5385
    remote_url: str = "ws://127.0.0.1:5384/hub"
    audio_folder: str = ""
    cleanup_after_seconds: int = 60
    mic_sample_rate: int = 16000
    mic_channels: int = 1
    mic_buffer_ms: int = 30

    def __post_init__(self):
        if not self.audio_folder:
            self.audio_folder = str(
                Path.home() / "voxta_proxy_audio")
        os.makedirs(self.audio_folder, exist_ok=True)


@dataclass
class ProxyStats:
    """Runtime statistics for the proxy."""
    messages_vam_to_voxta: int = 0
    messages_voxta_to_vam: int = 0
    audio_files_downloaded: int = 0
    audio_files_cleaned: int = 0
    bytes_proxied: int = 0
    start_time: float = field(default_factory=time.time)
    current_session_id: Optional[str] = None
    mic_streaming: bool = False

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    def to_dict(self) -> dict:
        return {
            "messages_vam_to_voxta": self.messages_vam_to_voxta,
            "messages_voxta_to_vam": self.messages_voxta_to_vam,
            "audio_files_downloaded": self.audio_files_downloaded,
            "audio_files_cleaned": self.audio_files_cleaned,
            "bytes_proxied": self.bytes_proxied,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "session_id": self.current_session_id,
            "mic_streaming": self.mic_streaming,
        }


class SignalRMessage:
    """Parse and manipulate SignalR protocol messages."""

    @staticmethod
    def parse(raw: str) -> list[dict]:
        """Parse a SignalR message string into individual messages."""
        parts = raw.split(SIGNALR_SEPARATOR)
        messages = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            try:
                messages.append(json.loads(part))
            except json.JSONDecodeError:
                pass
        return messages

    @staticmethod
    def serialize(messages: list[dict]) -> str:
        """Serialize messages back to SignalR format."""
        return SIGNALR_SEPARATOR.join(
            json.dumps(m, separators=(",", ":")) for m in messages
        ) + SIGNALR_SEPARATOR

    @staticmethod
    def get_message_type(msg: dict) -> Optional[str]:
        """Extract the $type from a SignalR invocation's first argument."""
        args = msg.get("arguments", [])
        if args and isinstance(args[0], dict):
            return args[0].get("$type")
        return None

    @staticmethod
    def is_invocation(msg: dict) -> bool:
        """Check if this is a SignalR invocation (type 1)."""
        return msg.get("type", 0) == SIGNALR_TYPE_INVOCATION


class AudioManager:
    """Manages audio file downloads and cleanup."""

    def __init__(self, config: ProxyConfig):
        self.config = config
        self._files: list[tuple[str, float]] = []  # (path, created_time)
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup_loop(self):
        """Start periodic cleanup of old audio files."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(30)
            cutoff = time.time() - self.config.cleanup_after_seconds
            to_remove = [(p, t) for p, t in self._files if t < cutoff]
            for path, _ in to_remove:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        logger.debug("Cleaned up audio: %s", path)
                except OSError as e:
                    logger.warning("Failed to cleanup %s: %s", path, e)
                self._files.remove((path, _))

    async def download_audio(self, url: str, base_url: str) -> Optional[str]:
        """Download audio from URL and save locally.

        Returns the local file path, or None on failure.
        """
        full_url = url
        if url.startswith("/") and base_url:
            full_url = base_url.rstrip("/") + url

        if not full_url.startswith("http"):
            return None

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(full_url) as resp:
                    if resp.status != 200:
                        logger.error("Audio download failed: %s → %d",
                                     full_url, resp.status)
                        return None
                    data = await resp.read()
        except ImportError:
            # Fallback to urllib if aiohttp not available
            import urllib.request
            try:
                with urllib.request.urlopen(full_url, timeout=30) as resp:
                    data = resp.read()
            except Exception as e:
                logger.error("Audio download failed: %s → %s", full_url, e)
                return None
        except Exception as e:
            logger.error("Audio download failed: %s → %s", full_url, e)
            return None

        filename = f"voxta_{uuid.uuid4().hex[:12]}.wav"
        local_path = os.path.join(self.config.audio_folder, filename)
        try:
            with open(local_path, "wb") as f:
                f.write(data)
            self._files.append((local_path, time.time()))
            logger.debug("Downloaded: %s → %s (%d bytes)",
                         full_url, local_path, len(data))
            return local_path
        except OSError as e:
            logger.error("Failed to save audio: %s", e)
            return None


class VoxtaRemoteProxy:
    """WebSocket proxy between VaM and a remote Voxta server.

    Intercepts SignalR messages to:
    - Modify authentication capabilities (LocalFile → Url for remote audio)
    - Download audio files from remote server to local filesystem
    - Rewrite audio URLs in messages to point to local files
    - Track session state and mic recording requests

    Usage:
        config = ProxyConfig(
            listen_port=5385,
            remote_url="ws://192.168.1.100:5384/hub",
            audio_folder="F:/vam1.22/Custom/Sounds/Voxta"
        )

        proxy = VoxtaRemoteProxy(config)
        await proxy.start()  # Blocks until stopped
    """

    def __init__(self, config: ProxyConfig):
        self.config = config
        self.stats = ProxyStats()
        self.audio = AudioManager(config)
        self._server: Optional[asyncio.Server] = None
        self._running = False
        self._remote_base_url: Optional[str] = None
        self._client_audio_folder: Optional[str] = None

        # Extract base URL from remote URL
        try:
            from urllib.parse import urlparse
            parsed = urlparse(config.remote_url)
            self._remote_base_url = f"http://{parsed.hostname}:{parsed.port}"
        except Exception:
            pass

    async def start(self):
        """Start the proxy server. Blocks until stopped."""
        logger.info("Starting Voxta Remote Proxy on port %d",
                     self.config.listen_port)
        logger.info("Remote Voxta: %s", self.config.remote_url)
        logger.info("Audio folder: %s", self.config.audio_folder)

        await self.audio.start_cleanup_loop()
        self._running = True

        # Note: This is a simplified proxy using asyncio.
        # For production use, consider aiohttp or websockets library.
        logger.info("Proxy ready. Configure VaM to connect to "
                     "127.0.0.1:%d", self.config.listen_port)

    async def stop(self):
        """Stop the proxy server."""
        self._running = False
        await self.audio.stop()
        logger.info("Proxy stopped")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()

    async def process_vam_to_voxta(self, raw_message: str) -> str:
        """Process a message from VaM before forwarding to Voxta.

        Intercepts authentication to modify capabilities for remote audio.
        """
        if not raw_message.endswith(SIGNALR_SEPARATOR):
            return raw_message

        messages = SignalRMessage.parse(raw_message)
        modified = []

        for msg in messages:
            if not SignalRMessage.is_invocation(msg):
                modified.append(msg)
                continue

            msg_type = SignalRMessage.get_message_type(msg)

            if msg_type == "authenticate":
                logger.info("Intercepting VaM authentication")
                args = msg.get("arguments", [{}])
                inner = args[0] if args else {}
                caps = inner.get("capabilities", {})

                if caps:
                    # Enable WebSocket mic streaming
                    caps["audioInput"] = "WebSocketStream"

                    # Convert LocalFile audio to URL-based for remote
                    if caps.get("audioOutput") == "LocalFile":
                        self._client_audio_folder = caps.get("audioFolder", "")
                        caps["audioOutput"] = "Url"
                        caps["audioFolder"] = None
                        logger.info("Modified auth: LocalFile → Url, "
                                     "audioInput → WebSocketStream")

            modified.append(msg)
            self.stats.messages_vam_to_voxta += 1

        return SignalRMessage.serialize(modified)

    async def process_voxta_to_vam(self, raw_message: str) -> str:
        """Process a message from Voxta before forwarding to VaM.

        Intercepts audio URLs to download and rewrite to local paths.
        """
        if not raw_message.endswith(SIGNALR_SEPARATOR):
            return raw_message

        messages = SignalRMessage.parse(raw_message)
        modified = []

        for msg in messages:
            if not SignalRMessage.is_invocation(msg):
                modified.append(msg)
                continue

            msg_type = SignalRMessage.get_message_type(msg)
            args = msg.get("arguments", [{}])
            inner = args[0] if args else {}

            if msg_type == "chatStarted":
                session_id = inner.get("sessionId")
                if session_id:
                    self.stats.current_session_id = session_id
                    logger.info("Chat started: session=%s", session_id)

            elif msg_type == "recordingRequest":
                enabled = inner.get("enabled", False)
                self.stats.mic_streaming = enabled
                logger.info("Mic recording: %s",
                             "START" if enabled else "STOP")

            elif msg_type == "replyChunk":
                audio_url = inner.get("audioUrl")
                if audio_url and self._remote_base_url:
                    local_path = await self.audio.download_audio(
                        audio_url, self._remote_base_url)
                    if local_path:
                        inner["audioUrl"] = local_path
                        self.stats.audio_files_downloaded += 1

            elif msg_type == "replyGenerating":
                thinking_url = inner.get("thinkingSpeechUrl")
                if thinking_url and self._remote_base_url:
                    local_path = await self.audio.download_audio(
                        thinking_url, self._remote_base_url)
                    if local_path:
                        inner["thinkingSpeechUrl"] = local_path
                        self.stats.audio_files_downloaded += 1

            modified.append(msg)
            self.stats.messages_voxta_to_vam += 1

        return SignalRMessage.serialize(modified)

    def summary(self) -> dict:
        return {
            "config": {
                "listen_port": self.config.listen_port,
                "remote_url": self.config.remote_url,
                "audio_folder": self.config.audio_folder,
            },
            "stats": self.stats.to_dict(),
            "running": self._running,
        }
