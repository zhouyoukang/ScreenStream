"""
VaM 环境构建器 — 程序化环境/灯光/相机/音频管理

从以下外部项目提取核心逻辑:
  - vam-story-builder: Environment/Light atom templates
  - vam-devtools: Unity GameObject/Component inspection
  - vam-collider-editor: CollisionTrigger for environment atoms

架构:
  EnvironmentBuilder — 环境构建主类 (CustomUnityAsset atoms)
  LightingRig        — 灯光方案 (预设+自定义)
  CameraRig          — 相机配置 (位置/FOV/动画)
  AudioManager       — 环境音频管理
"""
import json
import copy
from pathlib import Path
from typing import Optional

from .config import VAM_CONFIG


# ── 灯光 ──

class LightConfig:
    """单个灯光配置"""

    LIGHT_TYPES = ["InvisibleLight", "VisibleLight", "SpotLight"]
    SOURCE_TYPES = ["Directional", "Point", "Spot"]
    SHADOW_TYPES = ["Soft", "Hard", "None"]

    def __init__(self, name: str, light_type: str = "InvisibleLight"):
        self.name = name
        self.light_type = light_type
        self.source_type: str = "Directional"
        self.position = (0.0, 3.0, 0.0)
        self.rotation = (50.0, 0.0, 0.0)
        self.intensity: float = 1.0
        self.color = (1.0, 1.0, 1.0)
        self.range: float = 10.0
        self.spot_angle: float = 30.0
        self.shadow_type: str = "Soft"
        self.on: bool = True

    def set_position(self, x: float, y: float, z: float) -> "LightConfig":
        self.position = (x, y, z)
        return self

    def set_rotation(self, x: float, y: float, z: float) -> "LightConfig":
        self.rotation = (x, y, z)
        return self

    def set_color(self, r: float, g: float, b: float) -> "LightConfig":
        self.color = (r, g, b)
        return self

    def build_atom(self) -> dict:
        """构建灯光atom (匹配真实VaM场景JSON格式)"""
        light_storable = {
            "id": "Light",
            "type": self.source_type,
            "intensity": str(self.intensity),
            "color": {
                "r": str(self.color[0]),
                "g": str(self.color[1]),
                "b": str(self.color[2]),
            },
            "shadowType": self.shadow_type,
        }
        if self.source_type in ("Point", "Spot"):
            light_storable["range"] = str(self.range)
        if self.source_type == "Spot":
            light_storable["spotAngle"] = str(self.spot_angle)
        return {
            "id": self.name,
            "type": self.light_type,
            "on": "true" if self.on else "false",
            "position": {
                "x": str(self.position[0]),
                "y": str(self.position[1]),
                "z": str(self.position[2]),
            },
            "rotation": {
                "x": str(self.rotation[0]),
                "y": str(self.rotation[1]),
                "z": str(self.rotation[2]),
            },
            "storables": [light_storable],
        }


class LightingRig:
    """灯光方案 — 预设灯光组合"""

    PRESETS = {
        "three_point": {
            "description": "经典三点布光 (主光/辅光/背光)",
            "lights": [
                {"name": "KeyLight", "pos": (-2, 3, 2), "rot": (50, 30, 0),
                 "intensity": 1.2, "color": (1, 0.98, 0.95), "src": "Directional"},
                {"name": "FillLight", "pos": (2, 2.5, 1), "rot": (40, -30, 0),
                 "intensity": 0.6, "color": (0.85, 0.9, 1.0), "src": "Point"},
                {"name": "BackLight", "pos": (0, 3, -2), "rot": (60, 180, 0),
                 "intensity": 0.8, "color": (1, 1, 1), "src": "Point"},
            ],
        },
        "cinematic_warm": {
            "description": "电影暖色调灯光",
            "lights": [
                {"name": "MainLight", "pos": (-1.5, 4, 3), "rot": (45, 20, 0),
                 "intensity": 1.0, "color": (1, 0.92, 0.8), "src": "Directional"},
                {"name": "AccentLight", "pos": (2, 2, -1), "rot": (30, -60, 0),
                 "intensity": 0.4, "color": (1, 0.85, 0.7), "src": "Point"},
            ],
        },
        "studio_soft": {
            "description": "柔和摄影棚灯光",
            "lights": [
                {"name": "SoftLight1", "pos": (-3, 4, 0), "rot": (40, 90, 0),
                 "intensity": 0.8, "color": (1, 1, 1), "src": "Directional"},
                {"name": "SoftLight2", "pos": (3, 4, 0), "rot": (40, -90, 0),
                 "intensity": 0.8, "color": (1, 1, 1), "src": "Directional"},
                {"name": "TopLight", "pos": (0, 5, 0), "rot": (90, 0, 0),
                 "intensity": 0.5, "color": (1, 1, 1), "src": "Point"},
            ],
        },
        "dramatic": {
            "description": "戏剧性高对比灯光",
            "lights": [
                {"name": "HardLight", "pos": (-1, 3, 2), "rot": (60, 30, 0),
                 "intensity": 1.5, "color": (1, 0.95, 0.9), "src": "Directional"},
                {"name": "RimLight", "pos": (1, 2, -2), "rot": (30, -150, 0),
                 "intensity": 0.3, "color": (0.7, 0.8, 1.0), "src": "Point"},
            ],
        },
        "night_mood": {
            "description": "夜间氛围灯光",
            "lights": [
                {"name": "MoonLight", "pos": (2, 5, -3), "rot": (70, -45, 0),
                 "intensity": 0.3, "color": (0.6, 0.7, 1.0), "src": "Directional"},
                {"name": "AmbientLight", "pos": (0, 4, 0), "rot": (90, 0, 0),
                 "intensity": 0.15, "color": (0.4, 0.45, 0.6), "src": "Point"},
            ],
        },
    }

    def __init__(self):
        self.lights: list[LightConfig] = []

    def from_preset(self, preset_name: str) -> "LightingRig":
        """从预设加载灯光方案"""
        if preset_name not in self.PRESETS:
            raise ValueError(
                f"Unknown preset: {preset_name}. "
                f"Available: {list(self.PRESETS.keys())}"
            )
        preset = self.PRESETS[preset_name]
        self.lights = []
        for ld in preset["lights"]:
            light = LightConfig(ld["name"])
            light.set_position(*ld["pos"])
            light.set_rotation(*ld["rot"])
            light.intensity = ld["intensity"]
            light.set_color(*ld["color"])
            light.source_type = ld.get("src", "Directional")
            self.lights.append(light)
        return self

    def add_light(self, light: LightConfig) -> "LightingRig":
        """添加自定义灯光"""
        self.lights.append(light)
        return self

    def build_atoms(self) -> list[dict]:
        """构建所有灯光atoms"""
        return [l.build_atom() for l in self.lights]

    @classmethod
    def list_presets(cls) -> list[dict]:
        return [
            {"name": k, "description": v["description"],
             "light_count": len(v["lights"])}
            for k, v in cls.PRESETS.items()
        ]


# ── 相机 ──

class CameraConfig:
    """相机配置"""

    def __init__(self, name: str = "Camera"):
        self.name = name
        self.position = (0.0, 1.6, -1.5)
        self.rotation = (0.0, 0.0, 0.0)
        self.fov: float = 60.0
        self.dof_enabled: bool = False
        self.dof_focus_distance: float = 2.0
        self.dof_aperture: float = 5.6

    def set_position(self, x: float, y: float, z: float) -> "CameraConfig":
        self.position = (x, y, z)
        return self

    def set_rotation(self, x: float, y: float, z: float) -> "CameraConfig":
        self.rotation = (x, y, z)
        return self

    def set_fov(self, fov: float) -> "CameraConfig":
        self.fov = fov
        return self

    def enable_dof(self, focus_distance: float = 2.0,
                   aperture: float = 5.6) -> "CameraConfig":
        self.dof_enabled = True
        self.dof_focus_distance = focus_distance
        self.dof_aperture = aperture
        return self

    def build_atom(self) -> dict:
        """构建相机atom (匹配真实VaM场景JSON格式)"""
        cam_storable = {
            "id": "CameraControl",
            "FOV": str(self.fov),
        }
        if self.dof_enabled:
            cam_storable["depthOfField"] = "true"
            cam_storable["focusDistance"] = str(self.dof_focus_distance)
            cam_storable["aperture"] = str(self.dof_aperture)
        return {
            "id": self.name,
            "type": "WindowCamera",
            "on": "true",
            "position": {
                "x": str(self.position[0]),
                "y": str(self.position[1]),
                "z": str(self.position[2]),
            },
            "rotation": {
                "x": str(self.rotation[0]),
                "y": str(self.rotation[1]),
                "z": str(self.rotation[2]),
            },
            "storables": [cam_storable],
        }


class CameraRig:
    """相机方案 — 预设相机组合"""

    PRESETS = {
        "portrait": {
            "description": "人像特写",
            "cameras": [
                {"name": "PortraitCam", "pos": (0, 1.6, -0.8),
                 "rot": (0, 0, 0), "fov": 50},
            ],
        },
        "full_body": {
            "description": "全身拍摄",
            "cameras": [
                {"name": "FullBodyCam", "pos": (0, 1.2, -2.5),
                 "rot": (5, 0, 0), "fov": 60},
            ],
        },
        "multi_angle": {
            "description": "多角度拍摄",
            "cameras": [
                {"name": "FrontCam", "pos": (0, 1.5, -1.5),
                 "rot": (0, 0, 0), "fov": 55},
                {"name": "SideCam", "pos": (-2, 1.5, 0),
                 "rot": (0, 90, 0), "fov": 55},
                {"name": "TopCam", "pos": (0, 3, -0.5),
                 "rot": (45, 0, 0), "fov": 60},
            ],
        },
        "cinematic": {
            "description": "电影风格",
            "cameras": [
                {"name": "CineCam", "pos": (0.5, 1.3, -1.2),
                 "rot": (2, -5, 0), "fov": 35,
                 "dof": {"focus": 1.2, "aperture": 2.8}},
            ],
        },
    }

    def __init__(self):
        self.cameras: list[CameraConfig] = []

    def from_preset(self, preset_name: str) -> "CameraRig":
        """从预设加载相机方案"""
        if preset_name not in self.PRESETS:
            raise ValueError(
                f"Unknown preset: {preset_name}. "
                f"Available: {list(self.PRESETS.keys())}"
            )
        preset = self.PRESETS[preset_name]
        self.cameras = []
        for cd in preset["cameras"]:
            cam = CameraConfig(cd["name"])
            cam.set_position(*cd["pos"])
            cam.set_rotation(*cd["rot"])
            cam.set_fov(cd["fov"])
            if "dof" in cd:
                cam.enable_dof(cd["dof"]["focus"], cd["dof"]["aperture"])
            self.cameras.append(cam)
        return self

    def add_camera(self, camera: CameraConfig) -> "CameraRig":
        self.cameras.append(camera)
        return self

    def build_atoms(self) -> list[dict]:
        return [c.build_atom() for c in self.cameras]

    @classmethod
    def list_presets(cls) -> list[dict]:
        return [
            {"name": k, "description": v["description"],
             "camera_count": len(v["cameras"])}
            for k, v in cls.PRESETS.items()
        ]


# ── 环境资产 (CustomUnityAsset) ──

class EnvironmentAsset:
    """
    环境资产 — CustomUnityAsset atom

    基于 vam-story-builder Environment.json 模板
    """

    def __init__(self, name: str, asset_url: str = ""):
        self.name = name
        self.asset_url = asset_url
        self.position = (0.0, 0.0, 0.0)
        self.rotation = (0.0, 0.0, 0.0)
        self.scale = (1.0, 1.0, 1.0)
        self.collision_enabled: bool = True

    def set_position(self, x: float, y: float, z: float) -> "EnvironmentAsset":
        self.position = (x, y, z)
        return self

    def set_rotation(self, x: float, y: float, z: float) -> "EnvironmentAsset":
        self.rotation = (x, y, z)
        return self

    def set_scale(self, x: float, y: float, z: float) -> "EnvironmentAsset":
        self.scale = (x, y, z)
        return self

    def build_atom(self) -> dict:
        """构建CustomUnityAsset atom"""
        storables = [
            {
                "id": "control",
                "position": {
                    "x": str(self.position[0]),
                    "y": str(self.position[1]),
                    "z": str(self.position[2]),
                },
                "rotation": {
                    "x": str(self.rotation[0]),
                    "y": str(self.rotation[1]),
                    "z": str(self.rotation[2]),
                },
            },
        ]
        if self.asset_url:
            storables.append({
                "id": "asset",
                "assetUrl": self.asset_url,
                "assetName": self.name,
            })
        if self.collision_enabled:
            storables.append({
                "id": "CollisionTrigger",
                "trigger": {
                    "startActions": [],
                    "endActions": [],
                },
            })
        return {
            "id": self.name,
            "type": "CustomUnityAsset",
            "on": "true",
            "position": {
                "x": str(self.position[0]),
                "y": str(self.position[1]),
                "z": str(self.position[2]),
            },
            "rotation": {
                "x": str(self.rotation[0]),
                "y": str(self.rotation[1]),
                "z": str(self.rotation[2]),
            },
            "storables": storables,
        }


# ── 音频管理 ──

class AudioConfig:
    """环境音频配置"""

    def __init__(self, name: str, audio_path: str = ""):
        self.name = name
        self.audio_path = audio_path
        self.volume: float = 1.0
        self.loop: bool = True
        self.spatial_blend: float = 0.0  # 0=2D, 1=3D
        self.position = (0.0, 0.0, 0.0)

    def set_volume(self, volume: float) -> "AudioConfig":
        self.volume = volume
        return self

    def build_atom(self) -> dict:
        """构建音频atom (匹配真实VaM场景JSON格式)"""
        return {
            "id": self.name,
            "type": "AudioSource",
            "on": "true",
            "position": {
                "x": str(self.position[0]),
                "y": str(self.position[1]),
                "z": str(self.position[2]),
            },
            "storables": [
                {
                    "id": "AudioSource",
                    "clip": self.audio_path,
                    "volume": str(self.volume),
                    "loop": str(self.loop).lower(),
                    "spatialBlend": str(self.spatial_blend),
                },
            ],
        }


# ── 环境构建器 (主类) ──

class EnvironmentBuilder:
    """
    环境构建器 — 组合环境/灯光/相机/音频

    用法:
        env = EnvironmentBuilder("studio_scene")
        env.lighting.from_preset("three_point")
        env.cameras.from_preset("portrait")
        env.add_asset(EnvironmentAsset("floor", "path/to/floor.assetbundle"))
        atoms = env.build_atoms()
    """

    def __init__(self, name: str = "environment"):
        self.name = name
        self.lighting = LightingRig()
        self.cameras = CameraRig()
        self.assets: list[EnvironmentAsset] = []
        self.audio: list[AudioConfig] = []

    def add_asset(self, asset: EnvironmentAsset) -> "EnvironmentBuilder":
        """添加环境资产"""
        self.assets.append(asset)
        return self

    def add_audio(self, audio: AudioConfig) -> "EnvironmentBuilder":
        """添加环境音频"""
        self.audio.append(audio)
        return self

    def build_atoms(self) -> list[dict]:
        """构建所有环境相关atoms"""
        atoms = []
        atoms.extend(self.lighting.build_atoms())
        atoms.extend(self.cameras.build_atoms())
        atoms.extend([a.build_atom() for a in self.assets])
        atoms.extend([a.build_atom() for a in self.audio])
        return atoms

    def list_available_assets(self) -> list[dict]:
        """列出所有可用的环境资产"""
        base = VAM_CONFIG.ASSETS_DIR
        if not base.exists():
            return []
        items = []
        for f in base.rglob("*.assetbundle"):
            items.append({
                "name": f.stem,
                "path": str(f),
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
            })
        return items

    def list_available_sounds(self) -> list[dict]:
        """列出所有可用的音频文件"""
        base = VAM_CONFIG.SOUNDS_DIR
        if not base.exists():
            return []
        items = []
        for ext in ("*.wav", "*.mp3", "*.ogg"):
            for f in base.rglob(ext):
                items.append({
                    "name": f.stem,
                    "format": f.suffix,
                    "path": str(f),
                    "size_kb": round(f.stat().st_size / 1024, 1),
                })
        return items

    def summary(self) -> dict:
        """环境构建摘要"""
        return {
            "name": self.name,
            "lights": len(self.lighting.lights),
            "cameras": len(self.cameras.cameras),
            "assets": len(self.assets),
            "audio": len(self.audio),
        }
