"""
Buttplug.io / Intiface Central 集成
通过WebSocket连接Intiface Central，实现设备发现和TCode命令发送

架构:
  本模块 → WebSocket → Intiface Central → Buttplug协议 → 设备
  
参考:
  - https://github.com/intiface/intiface-central (216⭐)
  - https://github.com/buttplugio/buttplug-rs-ffi (91⭐)
  - Buttplug协议: https://buttplug-spec.docs.buttplug.io/
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class ButtplugDevice:
    """Buttplug设备信息"""
    index: int
    name: str
    messages: dict = field(default_factory=dict)
    
    @property
    def supports_linear(self) -> bool:
        return "LinearCmd" in self.messages
    
    @property
    def supports_vibrate(self) -> bool:
        return "VibrateCmd" in self.messages
    
    @property
    def supports_rotate(self) -> bool:
        return "RotateCmd" in self.messages
    
    @property
    def linear_count(self) -> int:
        info = self.messages.get("LinearCmd", {})
        return info.get("FeatureCount", 0)
    
    @property
    def vibrate_count(self) -> int:
        info = self.messages.get("VibrateCmd", {})
        return info.get("FeatureCount", 0)


@dataclass 
class ButtplugConfig:
    """Buttplug连接配置"""
    host: str = "127.0.0.1"
    port: int = 12345
    client_name: str = "ORS6-TCode-Bridge"
    
    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.port}"


class ButtplugBridge:
    """Buttplug.io WebSocket桥接
    
    通过Intiface Central的WebSocket API控制设备。
    支持设备扫描、线性运动(LinearCmd)、振动(VibrateCmd)等。
    
    使用方法:
        bridge = ButtplugBridge()
        await bridge.connect()
        await bridge.scan()
        # 等待设备出现...
        await bridge.linear(device_index=0, position=0.8, duration_ms=500)
        await bridge.disconnect()
    """
    
    def __init__(self, config: Optional[ButtplugConfig] = None, **kwargs):
        self.config = config or ButtplugConfig(**kwargs)
        self._ws = None
        self._msg_id = 1
        self._devices: dict[int, ButtplugDevice] = {}
        self._connected = False
        self._on_device_added: Optional[Callable] = None
        self._on_device_removed: Optional[Callable] = None
        self._response_futures: dict[int, asyncio.Future] = {}
        self._recv_task: Optional[asyncio.Task] = None
    
    @property
    def devices(self) -> dict[int, ButtplugDevice]:
        return dict(self._devices)
    
    @property
    def connected(self) -> bool:
        return self._connected
    
    def on_device_added(self, callback: Callable):
        self._on_device_added = callback
    
    def on_device_removed(self, callback: Callable):
        self._on_device_removed = callback
    
    def _next_id(self) -> int:
        mid = self._msg_id
        self._msg_id += 1
        return mid
    
    async def _send(self, messages: list[dict]) -> Optional[dict]:
        """发送Buttplug消息并等待响应"""
        if not self._ws:
            raise ConnectionError("未连接到Intiface Central")
        
        try:
            import websockets
        except ImportError:
            raise ImportError("需要安装websockets: pip install websockets")
        
        msg_id = messages[0].get(list(messages[0].keys())[0], {}).get("Id", 0)
        future = asyncio.get_event_loop().create_future()
        self._response_futures[msg_id] = future
        
        await self._ws.send(json.dumps(messages))
        
        try:
            return await asyncio.wait_for(future, timeout=10.0)
        except asyncio.TimeoutError:
            self._response_futures.pop(msg_id, None)
            logger.warning(f"Buttplug消息超时: Id={msg_id}")
            return None
    
    async def _recv_loop(self):
        """接收消息循环"""
        try:
            async for raw in self._ws:
                try:
                    messages = json.loads(raw)
                    for msg in messages:
                        await self._handle_message(msg)
                except json.JSONDecodeError:
                    logger.warning(f"无效JSON: {raw[:100]}")
        except Exception as e:
            logger.error(f"接收循环错误: {e}")
            self._connected = False
    
    async def _handle_message(self, msg: dict):
        """处理接收到的Buttplug消息"""
        for msg_type, payload in msg.items():
            msg_id = payload.get("Id", 0)
            
            if msg_type == "DeviceAdded":
                dev = ButtplugDevice(
                    index=payload["DeviceIndex"],
                    name=payload["DeviceName"],
                    messages=payload.get("DeviceMessages", {})
                )
                self._devices[dev.index] = dev
                logger.info(f"设备添加: [{dev.index}] {dev.name}")
                if self._on_device_added:
                    self._on_device_added(dev)
            
            elif msg_type == "DeviceRemoved":
                idx = payload["DeviceIndex"]
                dev = self._devices.pop(idx, None)
                if dev:
                    logger.info(f"设备移除: [{idx}] {dev.name}")
                    if self._on_device_removed:
                        self._on_device_removed(dev)
            
            elif msg_type == "DeviceList":
                for dev_info in payload.get("Devices", []):
                    dev = ButtplugDevice(
                        index=dev_info["DeviceIndex"],
                        name=dev_info["DeviceName"],
                        messages=dev_info.get("DeviceMessages", {})
                    )
                    self._devices[dev.index] = dev
            
            elif msg_type == "ScanningFinished":
                logger.info("设备扫描完成")
            
            if msg_id in self._response_futures:
                self._response_futures.pop(msg_id).set_result(msg)
    
    async def connect(self) -> bool:
        """连接到Intiface Central WebSocket服务"""
        try:
            import websockets
        except ImportError:
            raise ImportError("需要安装websockets: pip install websockets")
        
        try:
            self._ws = await websockets.connect(self.config.ws_url)
            self._recv_task = asyncio.create_task(self._recv_loop())
            
            mid = self._next_id()
            handshake = [{"RequestServerInfo": {
                "Id": mid,
                "ClientName": self.config.client_name,
                "MessageVersion": 3
            }}]
            
            await self._ws.send(json.dumps(handshake))
            raw = await asyncio.wait_for(self._ws.recv(), timeout=5.0)
            resp = json.loads(raw)
            
            for msg in resp:
                if "ServerInfo" in msg:
                    info = msg["ServerInfo"]
                    logger.info(
                        f"已连接Intiface: {info.get('ServerName', '?')} "
                        f"v{info.get('MessageVersion', '?')}"
                    )
                    self._connected = True
                    return True
            
            logger.error(f"握手失败: {resp}")
            return False
            
        except Exception as e:
            logger.error(f"连接Intiface失败: {e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self._recv_task:
            self._recv_task.cancel()
        if self._ws:
            await self._ws.close()
        self._connected = False
        self._devices.clear()
        logger.info("已断开Intiface连接")
    
    async def scan(self, duration_sec: float = 5.0):
        """扫描设备"""
        mid = self._next_id()
        await self._send([{"StartScanning": {"Id": mid}}])
        await asyncio.sleep(duration_sec)
        mid2 = self._next_id()
        await self._send([{"StopScanning": {"Id": mid2}}])
        logger.info(f"扫描完成, 发现 {len(self._devices)} 个设备")
    
    async def request_device_list(self):
        """请求设备列表"""
        mid = self._next_id()
        await self._send([{"RequestDeviceList": {"Id": mid}}])
    
    async def linear(self, device_index: int, position: float,
                     duration_ms: int = 500, feature_index: int = 0):
        """LinearCmd — 线性运动（OSR/Handy等设备）
        
        Args:
            device_index: 设备索引
            position: 目标位置 0.0-1.0
            duration_ms: 运动时间毫秒
            feature_index: 特征索引（多轴设备用）
        """
        position = max(0.0, min(1.0, position))
        mid = self._next_id()
        await self._send([{"LinearCmd": {
            "Id": mid,
            "DeviceIndex": device_index,
            "Vectors": [{"Index": feature_index,
                         "Duration": duration_ms,
                         "Position": position}]
        }}])
    
    async def vibrate(self, device_index: int, speed: float,
                      feature_index: int = 0):
        """VibrateCmd — 振动控制
        
        Args:
            device_index: 设备索引
            speed: 振动强度 0.0-1.0
            feature_index: 特征索引
        """
        speed = max(0.0, min(1.0, speed))
        mid = self._next_id()
        await self._send([{"VibrateCmd": {
            "Id": mid,
            "DeviceIndex": device_index,
            "Speeds": [{"Index": feature_index, "Speed": speed}]
        }}])
    
    async def rotate(self, device_index: int, speed: float,
                     clockwise: bool = True, feature_index: int = 0):
        """RotateCmd — 旋转控制
        
        Args:
            device_index: 设备索引
            speed: 旋转速度 0.0-1.0
            clockwise: 顺时针方向
            feature_index: 特征索引
        """
        speed = max(0.0, min(1.0, speed))
        mid = self._next_id()
        await self._send([{"RotateCmd": {
            "Id": mid,
            "DeviceIndex": device_index,
            "Rotations": [{"Index": feature_index,
                           "Speed": speed,
                           "Clockwise": clockwise}]
        }}])
    
    async def stop_device(self, device_index: int):
        """停止单个设备"""
        mid = self._next_id()
        await self._send([{"StopDeviceCmd": {
            "Id": mid,
            "DeviceIndex": device_index
        }}])
    
    async def stop_all(self):
        """停止所有设备"""
        mid = self._next_id()
        await self._send([{"StopAllDevices": {"Id": mid}}])
    
    async def tcode_to_linear(self, device_index: int,
                               tcode_position: int,
                               interval_ms: int = 500):
        """将TCode位置值转换为Buttplug LinearCmd
        
        Args:
            device_index: 设备索引
            tcode_position: TCode位置 0-9999
            interval_ms: 运动时间
        """
        position = tcode_position / 9999.0
        await self.linear(device_index, position, interval_ms)
