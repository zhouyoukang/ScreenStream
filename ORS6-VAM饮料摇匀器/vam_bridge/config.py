"""VaM桥接配置"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class BridgeConfig:
    """VaM↔TCode桥接配置"""

    # ── VaM连接 ──
    vam_host: str = "127.0.0.1"
    vam_port: int = 8084         # AgentBridge HTTP API端口
    vam_poll_hz: int = 30        # 轮询频率(Hz)

    # ── TCode设备 ──
    tcode_mode: str = "serial"   # serial / wifi / ble
    tcode_serial_port: Optional[str] = None  # 自动检测
    tcode_serial_baud: int = 115200
    tcode_wifi_host: str = "192.168.1.100"
    tcode_wifi_port: int = 8000
    tcode_ble_name: str = "OSR"

    # ── 轴映射 ──
    # VaM控制器名 → TCode轴
    axis_mapping: dict = field(default_factory=lambda: {
        "hip_position_y":  "L0",   # 骨盆Y→行程
        "hip_position_z":  "L1",   # 骨盆Z→推进
        "hip_position_x":  "L2",   # 骨盆X→摆动
        "hip_rotation_y":  "R0",   # 骨盆旋转Y→扭转
        "hip_rotation_x":  "R1",   # 骨盆旋转X→横滚
        "hip_rotation_z":  "R2",   # 骨盆旋转Z→俯仰
    })

    # ── 运动参数 ──
    position_scale: float = 1.0    # 位置缩放
    position_offset: float = 0.0   # 位置偏移
    smoothing: float = 0.3         # 平滑系数 (0=不平滑, 1=最大平滑)
    deadzone: float = 0.02         # 死区 (忽略小于此值的变化)
    invert_axes: list = field(default_factory=list)  # 反转的轴列表

    # ── ToySerialController兼容 ──
    # ToySerialController VaM插件使用UDP向外部发送TCode
    tsc_udp_listen_port: int = 8001  # 监听TSC UDP输出

    @classmethod
    def load(cls, path: Path) -> "BridgeConfig":
        """从JSON文件加载配置"""
        import json
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items()
                         if k in cls.__dataclass_fields__})
        return cls()

    def save(self, path: Path):
        """保存配置到JSON文件"""
        import json
        from dataclasses import asdict
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
