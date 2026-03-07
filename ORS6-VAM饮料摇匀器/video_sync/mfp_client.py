"""
MultiFunPlayer WebSocket API 客户端

MultiFunPlayer (226⭐) 是多轴同步的核心中枢，支持:
- 12种视频播放器 (DeoVR/HereSphere/VLC/MPV/Plex/Jellyfin等)
- 8种设备输出 (Serial/Buttplug/TCP/UDP/WebSocket/NamedPipe/File/Handy)
- XBVR/Stash 脚本库自动匹配
- TCode v0.2 + v0.3 全轴支持

本客户端通过WebSocket连接MultiFunPlayer，实现:
1. 播放状态监控 (播放/暂停/进度)
2. 脚本加载控制
3. 轴位置实时读取
4. 设备输出配置
"""

import json
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class PlaybackState:
    """MultiFunPlayer播放状态"""
    is_playing: bool = False
    position_ms: float = 0.0
    duration_ms: float = 0.0
    speed: float = 1.0
    media_path: str = ""
    
    @property
    def position_sec(self) -> float:
        return self.position_ms / 1000.0
    
    @property
    def duration_sec(self) -> float:
        return self.duration_ms / 1000.0
    
    @property
    def progress(self) -> float:
        if self.duration_ms <= 0:
            return 0.0
        return min(1.0, self.position_ms / self.duration_ms)


@dataclass 
class AxisState:
    """轴实时状态"""
    name: str = ""
    value: float = 0.5
    script_loaded: bool = False
    script_path: str = ""


@dataclass
class MFPConfig:
    """MultiFunPlayer连接配置"""
    host: str = "127.0.0.1"
    port: int = 8088
    reconnect_interval: float = 5.0
    on_playback_update: Optional[Callable] = None
    on_axis_update: Optional[Callable] = None
    on_connected: Optional[Callable] = None
    on_disconnected: Optional[Callable] = None


class MultiFunPlayerClient:
    """MultiFunPlayer WebSocket API客户端
    
    通过WebSocket API连接MultiFunPlayer，获取播放状态和轴数据。
    
    用法:
        client = MultiFunPlayerClient(MFPConfig(port=8088))
        await client.connect()
        
        # 获取播放状态
        state = client.playback_state
        print(f"播放中: {state.is_playing}, 进度: {state.progress:.1%}")
        
        # 获取轴数据
        for axis in client.axes.values():
            print(f"{axis.name}: {axis.value:.4f}")
        
        await client.disconnect()
    """
    
    def __init__(self, config: MFPConfig = None):
        self.config = config or MFPConfig()
        self._ws = None
        self._connected = False
        self._running = False
        self._recv_task = None
        self.playback_state = PlaybackState()
        self.axes: dict[str, AxisState] = {}
    
    @property
    def url(self) -> str:
        return f"ws://{self.config.host}:{self.config.port}"
    
    @property
    def connected(self) -> bool:
        return self._connected
    
    async def connect(self) -> bool:
        """连接MultiFunPlayer WebSocket"""
        try:
            import websockets
        except ImportError:
            logger.error("需要安装 websockets: pip install websockets>=12.0")
            return False
        
        try:
            self._ws = await websockets.connect(
                self.url,
                ping_interval=20,
                ping_timeout=10,
            )
            self._connected = True
            self._running = True
            logger.info(f"已连接MultiFunPlayer: {self.url}")
            
            if self.config.on_connected:
                self.config.on_connected()
            
            self._recv_task = asyncio.create_task(self._receive_loop())
            return True
            
        except Exception as e:
            logger.error(f"连接MultiFunPlayer失败: {e}")
            self._connected = False
            return False
    
    async def disconnect(self):
        """断开连接"""
        self._running = False
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        
        if self._ws:
            await self._ws.close()
            self._ws = None
        
        self._connected = False
        logger.info("已断开MultiFunPlayer连接")
        
        if self.config.on_disconnected:
            self.config.on_disconnected()
    
    async def _receive_loop(self):
        """接收消息循环"""
        while self._running and self._ws:
            try:
                message = await self._ws.recv()
                data = json.loads(message)
                self._handle_message(data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    logger.warning(f"接收消息错误: {e}")
                    self._connected = False
                    if self.config.on_disconnected:
                        self.config.on_disconnected()
                    break
    
    def _handle_message(self, data: dict):
        """处理MFP消息"""
        msg_type = data.get("type", "")
        
        if msg_type == "playback":
            self.playback_state.is_playing = data.get("isPlaying", False)
            self.playback_state.position_ms = data.get("position", 0)
            self.playback_state.duration_ms = data.get("duration", 0)
            self.playback_state.speed = data.get("speed", 1.0)
            self.playback_state.media_path = data.get("mediaPath", "")
            
            if self.config.on_playback_update:
                self.config.on_playback_update(self.playback_state)
        
        elif msg_type == "axis":
            axis_name = data.get("name", "")
            if axis_name:
                if axis_name not in self.axes:
                    self.axes[axis_name] = AxisState(name=axis_name)
                self.axes[axis_name].value = data.get("value", 0.5)
                self.axes[axis_name].script_loaded = data.get("scriptLoaded", False)
                self.axes[axis_name].script_path = data.get("scriptPath", "")
                
                if self.config.on_axis_update:
                    self.config.on_axis_update(self.axes[axis_name])
    
    async def send_command(self, command: dict):
        """发送命令到MultiFunPlayer"""
        if not self._connected or not self._ws:
            logger.warning("未连接MultiFunPlayer")
            return
        
        try:
            await self._ws.send(json.dumps(command))
        except Exception as e:
            logger.error(f"发送命令失败: {e}")
    
    async def load_script(self, axis: str, script_path: str):
        """加载脚本到指定轴"""
        await self.send_command({
            "type": "loadScript",
            "axis": axis,
            "path": script_path,
        })
    
    async def play(self):
        """播放"""
        await self.send_command({"type": "play"})
    
    async def pause(self):
        """暂停"""
        await self.send_command({"type": "pause"})
    
    async def seek(self, position_ms: float):
        """跳转到指定位置(毫秒)"""
        await self.send_command({
            "type": "seek",
            "position": position_ms,
        })
    
    async def set_speed(self, speed: float):
        """设置播放速度"""
        await self.send_command({
            "type": "setSpeed",
            "speed": speed,
        })
    
    def get_axis_positions(self) -> dict[str, float]:
        """获取所有轴的当前位置 (0.0-1.0)"""
        return {name: ax.value for name, ax in self.axes.items()}
    
    def get_tcode_positions(self) -> dict[str, int]:
        """获取所有轴的TCode位置 (0-9999)"""
        return {
            name: int(ax.value * 9999)
            for name, ax in self.axes.items()
        }


class DeoVRMonitor:
    """DeoVR远程控制状态监控
    
    DeoVR通过HTTP API暴露播放状态，可直接读取。
    通常由MultiFunPlayer桥接，此类用于直接对接。
    
    DeoVR设置: Settings → Remote Control → Enable → Port 23554
    
    DeoVR API响应格式:
      playerState: 0=播放, 1=暂停
      currentTime: 秒 (float)
      duration: 秒 (float)
      playbackSpeed: 倍率
      path: 文件路径
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 23554):
        self.host = host
        self.port = port
        self.state = PlaybackState()
    
    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    def get_state(self) -> PlaybackState:
        """获取DeoVR当前播放状态 (同步调用)"""
        import urllib.request
        
        try:
            req = urllib.request.Request(self.url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                self.state.is_playing = data.get("playerState") == 0
                self.state.position_ms = data.get("currentTime", 0) * 1000
                self.state.duration_ms = data.get("duration", 0) * 1000
                self.state.speed = data.get("playbackSpeed", 1.0)
                self.state.media_path = data.get("path", "")
        except Exception as e:
            logger.debug(f"DeoVR状态获取失败: {e}")
        
        return self.state
    
    async def get_state_async(self) -> PlaybackState:
        """异步获取DeoVR状态 (线程池执行避免阻塞事件循环)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_state)


class HereSphereMonitor:
    """HereSphere远程控制状态监控
    
    HereSphere通过HTTP API暴露播放状态。
    HereSphere设置: Settings → External Control → Enable
    
    API端口默认23554, URL: http://host:port
    响应格式与DeoVR兼容(playerState/currentTime/duration等)
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 23554):
        self.host = host
        self.port = port
        self.state = PlaybackState()
    
    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    def get_state(self) -> PlaybackState:
        """获取HereSphere当前播放状态"""
        import urllib.request
        
        try:
            req = urllib.request.Request(self.url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                self.state.is_playing = data.get("playerState") == 0
                self.state.position_ms = data.get("currentTime", 0) * 1000
                self.state.duration_ms = data.get("duration", 0) * 1000
                self.state.speed = data.get("playbackSpeed", 1.0)
                self.state.media_path = data.get("path", "")
        except Exception as e:
            logger.debug(f"HereSphere状态获取失败: {e}")
        
        return self.state
