"""
VaM 角色构建器 — 程序化角色创建/形态/服装/发型/表情/行为管理

从以下外部项目提取核心逻辑:
  - vam-story-builder: Girl/Guy atom templates, storable structure
  - wardrobe: 服装纹理管理, outfit application
  - vam-embody: 控制器常量 (head/hands/eyes)
  - vam-collider-editor: 物理碰撞体配置模型
  - via5/Cue: 身体部位类型/情绪系统/人格/兴奋度/凝视/语音状态/敏感度 (CC0)
  - via5/Synergy: 随机动画参数修饰器 (CC0)
  - FacialMotionCapture: ARKit面捕→VaM Morph默认映射 (MIT)
  - morphology: Morph区域分类和管理工具 (MIT)

架构:
  CharacterBuilder       — 角色构建主类
  MorphPreset            — 形态预设 (身体/面部)
  AppearanceManager      — 外观管理 (皮肤/纹理)
  WardrobeManager        — 服装管理 (衣物/鞋子/配饰)
  HairManager            — 发型管理
  ExpressionManager      — 表情管理
  BodyPartType           — 身体部位枚举 (from Cue)
  MoodSystem             — 情绪系统 (from Cue)
  PersonalitySystem      — 人格系统 (from Cue)
  SensitivitiesSystem    — 敏感度系统 (from Cue)
  ExcitementSystem       — 兴奋度系统 (from Cue)
  GazeSystem             — 凝视系统 (from Cue)
  VoiceState             — 语音状态机 (from Cue)
  FacialMocapDefaults    — ARKit面捕→VaM Morph默认映射表 (from FacialMotionCapture)
  WardrobeTextureSlots   — 服装纹理槽位常量 (from wardrobe)
"""
import json
import copy
from pathlib import Path
from typing import Optional

from .config import VAM_CONFIG


# ── VaM 控制器常量 (from vam-embody VamConstants.cs) ──

CONTROL_SUFFIXES = {
    "head": "headControl",
    "left_hand": "lHandControl",
    "right_hand": "rHandControl",
    "eyes": "eyeTargetControl",
    "hip": "hipControl",
    "chest": "chestControl",
    "neck": "neckControl",
    "left_foot": "lFootControl",
    "right_foot": "rFootControl",
    "left_knee": "lKneeControl",
    "right_knee": "rKneeControl",
    "left_elbow": "lElbowControl",
    "right_elbow": "rElbowControl",
    "left_shoulder": "lShoulderControl",
    "right_shoulder": "rShoulderControl",
    "abdomen": "abdomenControl",
    "abdomen2": "abdomen2Control",
    "pelvis": "pelvisControl",
    "left_thigh": "lThighControl",
    "right_thigh": "rThighControl",
}

# ── 骨骼名称 (from vam-devtools DAZBone inspection) ──

BONE_NAMES = [
    "hip", "pelvis", "spine1", "spine2", "spine3", "spine4",
    "neck", "head",
    "lCollar", "lShldr", "lForeArm", "lHand",
    "rCollar", "rShldr", "rForeArm", "rHand",
    "lThigh", "lShin", "lFoot", "lToe",
    "rThigh", "rShin", "rFoot", "rToe",
    "lThumb1", "lThumb2", "lThumb3",
    "lIndex1", "lIndex2", "lIndex3",
    "lMid1", "lMid2", "lMid3",
    "lRing1", "lRing2", "lRing3",
    "lPinky1", "lPinky2", "lPinky3",
    "rThumb1", "rThumb2", "rThumb3",
    "rIndex1", "rIndex2", "rIndex3",
    "rMid1", "rMid2", "rMid3",
    "rRing1", "rRing2", "rRing3",
    "rPinky1", "rPinky2", "rPinky3",
]


# ── 形态预设 ──

class MorphPreset:
    """形态预设管理 — 身体/面部morph值"""

    # 常用身体形态参数
    BODY_MORPHS = {
        "breast_size": "FBMHeavy",
        "waist_width": "FBMBodyTone",
        "hip_width": "PBMHipsWidth",
        "height": "FBMTall",
        "weight": "FBMHeavy",
        "muscle": "FBMMuscular",
        "belly": "PBMBelly",
        "butt_size": "GlutesSize",
    }

    # 常用面部形态参数
    FACE_MORPHS = {
        "eye_size": "EyesSize",
        "nose_width": "NoseWidth",
        "lip_fullness": "LipFullness",
        "jaw_width": "JawWidth",
        "cheek_bones": "CheekBones",
        "brow_height": "BrowHeight",
        "chin_depth": "ChinDepth",
        "forehead_height": "ForeheadHeight",
    }

    # 预定义角色模板
    TEMPLATES = {
        "athletic_female": {
            "FBMBodyTone": 0.6, "FBMMuscular": 0.3,
            "FBMTall": 0.1, "GlutesSize": 0.3,
        },
        "curvy_female": {
            "FBMHeavy": 0.3, "PBMHipsWidth": 0.4,
            "GlutesSize": 0.5, "FBMBodyTone": 0.2,
        },
        "slim_female": {
            "FBMBodyTone": 0.4, "FBMTall": 0.2,
            "FBMHeavy": -0.3, "PBMHipsWidth": -0.1,
        },
        "athletic_male": {
            "FBMMuscular": 0.6, "FBMBodyTone": 0.5,
            "FBMTall": 0.2, "PBMHipsWidth": -0.1,
        },
        "average_male": {
            "FBMMuscular": 0.2, "FBMBodyTone": 0.3,
            "FBMTall": 0.0,
        },
    }

    def __init__(self, name: str = "custom"):
        self.name = name
        self.morphs: dict[str, float] = {}

    def from_template(self, template_name: str) -> "MorphPreset":
        """从预定义模板加载"""
        if template_name in self.TEMPLATES:
            self.morphs = copy.deepcopy(self.TEMPLATES[template_name])
            self.name = template_name
        return self

    def set_morph(self, morph_id: str, value: float) -> "MorphPreset":
        """设置单个morph值 (-1.0 ~ 1.0+)"""
        self.morphs[morph_id] = value
        return self

    def set_body(self, **kwargs) -> "MorphPreset":
        """设置身体形态 (使用友好名称)"""
        for key, value in kwargs.items():
            if key in self.BODY_MORPHS:
                self.morphs[self.BODY_MORPHS[key]] = value
        return self

    def set_face(self, **kwargs) -> "MorphPreset":
        """设置面部形态 (使用友好名称)"""
        for key, value in kwargs.items():
            if key in self.FACE_MORPHS:
                self.morphs[self.FACE_MORPHS[key]] = value
        return self

    def to_storables(self) -> list[dict]:
        """转换为VaM storable格式 (morphs列表, 由CharacterBuilder合并到geometry)"""
        if not self.morphs:
            return []
        morphs_list = [
            {"uid": mid, "value": str(val)}
            for mid, val in self.morphs.items()
        ]
        return [{"morphs": morphs_list}]


# ── 外观管理 ──

class AppearanceManager:
    """外观管理 — 皮肤纹理/材质/全局外观"""

    SKIN_MATERIALS = [
        "defaultMat", "Lacrimals", "Pupils", "Lips",
        "Irises", "Cornea", "Nostrils", "EyeReflection",
        "Teeth", "Gums", "Tongue", "InnerMouth",
        "Fingernails", "Toenails", "Eyelashes",
    ]

    def __init__(self):
        self.skin_textures: dict[str, str] = {}
        self.skin_color: Optional[dict] = None
        self.eye_color: Optional[str] = None

    def set_skin_texture(self, material: str, texture_path: str) -> "AppearanceManager":
        """设置皮肤纹理路径"""
        self.skin_textures[material] = texture_path
        return self

    def set_skin_color(self, r: float, g: float, b: float) -> "AppearanceManager":
        """设置皮肤颜色 (0.0~1.0)"""
        self.skin_color = {"r": r, "g": g, "b": b}
        return self

    def set_eye_color(self, color_name: str) -> "AppearanceManager":
        """设置眼睛颜色 (blue/green/brown/hazel/gray)"""
        self.eye_color = color_name
        return self

    def list_appearances(self) -> list[dict]:
        """列出所有已保存的外观预设"""
        base = VAM_CONFIG.APPEARANCES_DIR
        if not base.exists():
            return []
        appearances = []
        for f in base.rglob("*.json"):
            appearances.append({
                "name": f.stem,
                "path": str(f),
                "size_kb": round(f.stat().st_size / 1024, 1),
            })
        for f in base.rglob("*.vap"):
            appearances.append({
                "name": f.stem,
                "path": str(f),
                "size_kb": round(f.stat().st_size / 1024, 1),
            })
        return appearances

    def load_appearance(self, path: str) -> dict:
        """加载外观预设JSON"""
        return json.loads(Path(path).read_text(encoding="utf-8", errors="ignore"))

    def to_storables(self) -> list[dict]:
        """转换为VaM storable格式"""
        storables = []
        if self.skin_textures:
            tex_storable = {"id": "textures"}
            for mat, path in self.skin_textures.items():
                tex_storable[f"{mat}_url"] = path
            storables.append(tex_storable)
        return storables


# ── 服装管理 (from wardrobe) ──

class WardrobeManager:
    """服装管理 — 衣物/鞋子/配饰 (逻辑源自 wardrobe plugin)"""

    CLOTHING_REGIONS = [
        "chest", "hip", "torso", "legs", "feet", "arms", "hands",
        "head", "neck", "full_body",
    ]

    def __init__(self):
        self.clothing_items: list[dict] = []
        self.outfit_name: Optional[str] = None

    def add_clothing(self, item_id: str, region: str = "full_body",
                     texture_path: Optional[str] = None) -> "WardrobeManager":
        """添加衣物"""
        item = {"id": item_id, "region": region}
        if texture_path:
            item["texture"] = texture_path
        self.clothing_items.append(item)
        return self

    def set_outfit(self, outfit_name: str) -> "WardrobeManager":
        """设置整套服装预设"""
        self.outfit_name = outfit_name
        return self

    def list_clothing(self) -> list[dict]:
        """列出所有可用服装"""
        base = VAM_CONFIG.CLOTHING_DIR
        if not base.exists():
            return []
        items = []
        for d in base.iterdir():
            if d.is_dir():
                files = list(d.rglob("*.vam"))
                json_files = list(d.rglob("*.json"))
                items.append({
                    "name": d.name,
                    "vam_count": len(files),
                    "json_count": len(json_files),
                    "path": str(d),
                })
        return items

    def to_storables(self) -> list[dict]:
        """转换为VaM storable格式"""
        if not self.clothing_items:
            return []
        items_data = []
        for item in self.clothing_items:
            entry = {"id": item["id"], "enabled": "true"}
            if "texture" in item:
                entry["texture_url"] = item["texture"]
            items_data.append(entry)
        return [{"id": "clothing", "items": items_data}]


# ── 发型管理 ──

class HairManager:
    """发型管理"""

    def __init__(self):
        self.hair_id: Optional[str] = None
        self.hair_color: Optional[dict] = None
        self.hair_style_params: dict = {}

    def set_hair(self, hair_id: str) -> "HairManager":
        """设置发型ID"""
        self.hair_id = hair_id
        return self

    def set_hair_color(self, r: float, g: float, b: float) -> "HairManager":
        """设置发色"""
        self.hair_color = {"r": r, "g": g, "b": b}
        return self

    def list_hair(self) -> list[dict]:
        """列出所有可用发型"""
        base = VAM_CONFIG.HAIR_DIR
        if not base.exists():
            return []
        items = []
        for d in base.iterdir():
            if d.is_dir():
                items.append({
                    "name": d.name,
                    "path": str(d),
                    "files": sum(1 for _ in d.rglob("*") if _.is_file()),
                })
        return items

    def to_storables(self) -> list[dict]:
        """转换为VaM storable格式"""
        if not self.hair_id:
            return []
        storable = {"id": "hair", "style": self.hair_id}
        if self.hair_color:
            storable["color"] = self.hair_color
        return [storable]


# ── 表情管理 ──

class ExpressionManager:
    """表情管理 — 表情动画/blendshape预设"""

    EXPRESSION_PRESETS = {
        "neutral": {},
        "smile": {"Smile_Open": 0.5, "BrowInnerUp": 0.2},
        "happy": {"Smile_Open": 0.8, "BrowInnerUp": 0.4, "CheekSquint": 0.3},
        "sad": {"MouthFrown": 0.5, "BrowDown": 0.3, "EyeSquint": 0.2},
        "angry": {"BrowDown": 0.7, "JawOpen": 0.2, "NoseSneer": 0.4},
        "surprise": {"BrowInnerUp": 0.8, "EyeWide": 0.6, "JawOpen": 0.4},
        "wink": {"EyeBlinkLeft": 0.9, "Smile_Open": 0.3},
        "pout": {"LipPucker": 0.6, "MouthFrown": 0.2},
        "laugh": {"Smile_Open": 1.0, "JawOpen": 0.6, "CheekSquint": 0.5},
    }

    def __init__(self):
        self.current_expression: dict[str, float] = {}

    def set_expression(self, preset_name: str) -> "ExpressionManager":
        """设置预定义表情"""
        if preset_name in self.EXPRESSION_PRESETS:
            self.current_expression = copy.deepcopy(
                self.EXPRESSION_PRESETS[preset_name]
            )
        return self

    def set_blendshape(self, name: str, value: float) -> "ExpressionManager":
        """设置单个表情blendshape"""
        self.current_expression[name] = value
        return self

    def to_storables(self) -> list[dict]:
        """转换为VaM storable格式"""
        if not self.current_expression:
            return []
        morphs = [
            {"uid": name, "value": str(val)}
            for name, val in self.current_expression.items()
        ]
        return [{"id": "expression", "morphs": morphs}]


# ── 角色构建器 (主类) ──

class CharacterBuilder:
    """
    角色构建器 — 程序化创建VaM角色

    集成: MorphPreset + AppearanceManager + WardrobeManager +
          HairManager + ExpressionManager

    用法:
        builder = CharacterBuilder("MyCharacter", gender="female")
        builder.morphs.from_template("athletic_female")
        builder.wardrobe.add_clothing("dress_01", "torso")
        builder.hair.set_hair("long_wavy")
        builder.expression.set_expression("smile")
        atom = builder.build()  # 输出VaM atom dict
    """

    ATOM_TEMPLATE = {
        "type": "Person",
        "on": "true",
        "position": {"x": "0", "y": "0", "z": "0"},
        "rotation": {"x": "0", "y": "0", "z": "0"},
        "storables": [],
    }

    def __init__(self, name: str, gender: str = "female"):
        self.name = name
        self.gender = gender
        self.morphs = MorphPreset(f"{name}_morphs")
        self.appearance = AppearanceManager()
        self.wardrobe = WardrobeManager()
        self.hair = HairManager()
        self.expression = ExpressionManager()
        self.position = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.rotation = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.plugins: list[dict] = []
        self.extra_storables: list[dict] = []

    def set_position(self, x: float, y: float, z: float) -> "CharacterBuilder":
        """设置角色位置"""
        self.position = {"x": x, "y": y, "z": z}
        return self

    def set_rotation(self, x: float, y: float, z: float) -> "CharacterBuilder":
        """设置角色旋转"""
        self.rotation = {"x": x, "y": y, "z": z}
        return self

    def add_plugin(self, plugin_id: str, plugin_path: str,
                   params: Optional[dict] = None) -> "CharacterBuilder":
        """添加插件到角色"""
        plugin = {"id": plugin_id, "pluginPath": plugin_path}
        if params:
            plugin.update(params)
        self.plugins.append(plugin)
        return self

    def add_storable(self, storable: dict) -> "CharacterBuilder":
        """添加自定义storable"""
        self.extra_storables.append(storable)
        return self

    def from_appearance_file(self, path: str) -> "CharacterBuilder":
        """从外观预设文件加载角色"""
        data = json.loads(Path(path).read_text(encoding="utf-8", errors="ignore"))
        if "storables" in data:
            self.extra_storables.extend(data["storables"])
        return self

    def build(self) -> dict:
        """构建完整的VaM角色atom (匹配真实VaM场景JSON格式)"""
        atom = copy.deepcopy(self.ATOM_TEMPLATE)
        atom["id"] = self.name

        # 位置/旋转 (atom级别, 非containerJSON)
        atom["position"] = {
            k: str(v) for k, v in self.position.items()
        }
        atom["rotation"] = {
            k: str(v) for k, v in self.rotation.items()
        }

        # geometry storable (匹配真实格式, morphs合并在内)
        character = "Male" if self.gender == "male" else "Female"
        geo_storable = {
            "id": "geometry",
            "character": character,
            "clothing": [],
            "hair": [],
        }
        # 合并morphs到geometry storable
        morph_data = self.morphs.to_storables()
        if morph_data and "morphs" in morph_data[0]:
            geo_storable["morphs"] = morph_data[0]["morphs"]
        atom["storables"].append(geo_storable)

        # rescaleObject storable
        atom["storables"].append({
            "id": "rescaleObject",
            "scale": "1.0",
        })

        # 外观
        atom["storables"].extend(self.appearance.to_storables())

        # 服装
        atom["storables"].extend(self.wardrobe.to_storables())

        # 发型
        atom["storables"].extend(self.hair.to_storables())

        # 表情
        atom["storables"].extend(self.expression.to_storables())

        # 插件
        if self.plugins:
            atom["storables"].append({
                "id": "PluginManager",
                "plugins": {
                    f"plugin#{i}": p["pluginPath"]
                    for i, p in enumerate(self.plugins)
                },
            })

        # 额外storables
        atom["storables"].extend(self.extra_storables)

        return atom

    def save_appearance(self, filename: Optional[str] = None) -> str:
        """保存角色外观为预设文件"""
        filename = filename or f"{self.name}.json"
        target = VAM_CONFIG.APPEARANCES_DIR / filename
        target.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "id": self.name,
            "storables": (
                self.morphs.to_storables()
                + self.appearance.to_storables()
                + self.wardrobe.to_storables()
                + self.hair.to_storables()
            ),
        }
        target.write_text(
            json.dumps(data, indent=3), encoding="utf-8"
        )
        return str(target)

    def summary(self) -> dict:
        """角色构建摘要"""
        return {
            "name": self.name,
            "gender": self.gender,
            "position": self.position,
            "rotation": self.rotation,
            "morph_count": len(self.morphs.morphs),
            "clothing_count": len(self.wardrobe.clothing_items),
            "has_hair": self.hair.hair_id is not None,
            "expression": bool(self.expression.current_expression),
            "plugin_count": len(self.plugins),
            "extra_storables": len(self.extra_storables),
        }


# ── 便捷函数 ──

def quick_character(name: str, gender: str = "female",
                    template: str = "athletic_female",
                    expression: str = "smile",
                    position: tuple = (0, 0, 0)) -> dict:
    """快速创建角色atom"""
    builder = CharacterBuilder(name, gender)
    builder.morphs.from_template(template)
    builder.expression.set_expression(expression)
    builder.set_position(*position)
    return builder.build()


def list_all_character_assets() -> dict:
    """列出所有角色相关资产"""
    appearance_mgr = AppearanceManager()
    wardrobe_mgr = WardrobeManager()
    hair_mgr = HairManager()
    return {
        "appearances": appearance_mgr.list_appearances(),
        "clothing": wardrobe_mgr.list_clothing(),
        "hair": hair_mgr.list_hair(),
        "morph_templates": list(MorphPreset.TEMPLATES.keys()),
        "expression_presets": list(ExpressionManager.EXPRESSION_PRESETS.keys()),
        "mood_types": MoodSystem.MOOD_TYPES,
        "personality_traits": list(PersonalitySystem.TRAITS.keys()),
        "gaze_events": GazeSystem.EVENTS,
        "voice_states": VoiceState.STATES,
    }


# ═══════════════════════════════════════════════════════════════════
# 以下系统从 via5/Cue (CC0 Public Domain) 提取核心逻辑并Python化
# 源码: https://github.com/via5/Cue
# ═══════════════════════════════════════════════════════════════════


# ── 身体部位类型 (from Cue Person/Body/BodyParts.cs + Enums/BodyPartsEnum.cs) ──

class BodyPartType:
    """VaM角色身体部位枚举 — 用于碰撞检测/凝视/表情/交互"""

    HEAD = "head"
    EYES = "eyes"
    LIPS = "lips"
    MOUTH = "mouth"
    NECK = "neck"
    CHEST = "chest"
    LEFT_SHOULDER = "leftShoulder"
    RIGHT_SHOULDER = "rightShoulder"
    LEFT_ARM = "leftArm"
    RIGHT_ARM = "rightArm"
    LEFT_ELBOW = "leftElbow"
    RIGHT_ELBOW = "rightElbow"
    LEFT_FOREARM = "leftForearm"
    RIGHT_FOREARM = "rightForearm"
    LEFT_HAND = "leftHand"
    RIGHT_HAND = "rightHand"
    HIPS = "hips"
    PELVIS = "pelvis"
    LEFT_THIGH = "leftThigh"
    RIGHT_THIGH = "rightThigh"
    LEFT_KNEE = "leftKnee"
    RIGHT_KNEE = "rightKnee"
    LEFT_SHIN = "leftShin"
    RIGHT_SHIN = "rightShin"
    LEFT_FOOT = "leftFoot"
    RIGHT_FOOT = "rightFoot"
    ABDOMEN = "abdomen"
    BACK = "back"

    FULL_LEFT_ARM = [LEFT_SHOULDER, LEFT_ARM, LEFT_ELBOW, LEFT_FOREARM, LEFT_HAND]
    FULL_RIGHT_ARM = [RIGHT_SHOULDER, RIGHT_ARM, RIGHT_ELBOW, RIGHT_FOREARM, RIGHT_HAND]
    FULL_LEFT_LEG = [LEFT_THIGH, LEFT_KNEE, LEFT_SHIN, LEFT_FOOT]
    FULL_RIGHT_LEG = [RIGHT_THIGH, RIGHT_KNEE, RIGHT_SHIN, RIGHT_FOOT]
    PERSONAL_SPACE_PARTS = [LEFT_HAND, RIGHT_HAND, HEAD, CHEST, HIPS, LEFT_FOOT, RIGHT_FOOT]
    GROPING_PARTS = [LEFT_HAND, RIGHT_HAND, LEFT_FOOT, RIGHT_FOOT]
    PERSONAL_SPACE_DISTANCE = 0.25

    CONTROLLER_MAP = {
        HEAD: "headControl",
        CHEST: "chestControl",
        HIPS: "hipControl",
        LEFT_HAND: "lHandControl",
        RIGHT_HAND: "rHandControl",
        LEFT_FOOT: "lFootControl",
        RIGHT_FOOT: "rFootControl",
        LEFT_KNEE: "lKneeControl",
        RIGHT_KNEE: "rKneeControl",
        LEFT_ELBOW: "lElbowControl",
        RIGHT_ELBOW: "rElbowControl",
        PELVIS: "pelvisControl",
        NECK: "neckControl",
        ABDOMEN: "abdomenControl",
    }

    @classmethod
    def get_controller(cls, part: str) -> Optional[str]:
        return cls.CONTROLLER_MAP.get(part)

    @classmethod
    def all_parts(cls) -> list[str]:
        return [v for k, v in vars(cls).items()
                if isinstance(v, str) and not k.startswith("_")
                and k == k.upper() and k not in ("PERSONAL_SPACE_DISTANCE",)]


# ── 情绪系统 (from Cue Person/Mood.cs + Enums/Moods.cs) ──

class MoodSystem:
    """角色情绪状态机 — 驱动表情/声音/行为"""

    MOOD_TYPES = [
        "idle", "happy", "playful", "excited", "angry",
        "surprised", "sad", "tired", "shy", "confident",
        "flirty", "orgasm", "post_orgasm",
    ]

    MOOD_MORPH_MAP = {
        "idle": {"Smile_Open": 0.0},
        "happy": {"Smile_Open": 0.6, "BrowInnerUp": 0.3, "CheekSquint": 0.2},
        "playful": {"Smile_Open": 0.4, "BrowInnerUp": 0.2, "TongueOut": 0.1},
        "excited": {"EyeWide": 0.3, "JawOpen": 0.2, "Smile_Open": 0.5},
        "angry": {"BrowDown": 0.7, "NoseSneer": 0.4, "JawOpen": 0.15},
        "surprised": {"BrowInnerUp": 0.8, "EyeWide": 0.6, "JawOpen": 0.4},
        "sad": {"MouthFrown": 0.5, "BrowDown": 0.3, "EyeSquint": 0.2},
        "tired": {"EyeSquint": 0.4, "BrowDown": 0.1, "JawOpen": 0.1},
        "shy": {"EyeSquint": 0.2, "Smile_Open": 0.2, "BrowInnerUp": 0.3},
        "confident": {"Smile_Open": 0.3, "BrowDown": -0.1, "CheekSquint": 0.1},
        "flirty": {"Smile_Open": 0.4, "EyeBlinkLeft": 0.3, "LipPucker": 0.2},
        "orgasm": {"EyeSquint": 0.7, "JawOpen": 0.6, "BrowInnerUp": 0.5},
        "post_orgasm": {"EyeSquint": 0.3, "Smile_Open": 0.4, "JawOpen": 0.1},
    }

    MOOD_TRANSITIONS = {
        "idle": {"happy": 0.3, "playful": 0.2, "shy": 0.1},
        "happy": {"playful": 0.4, "excited": 0.3, "flirty": 0.2},
        "playful": {"excited": 0.4, "happy": 0.3, "flirty": 0.3},
        "excited": {"orgasm": 0.2, "happy": 0.3, "playful": 0.2},
        "angry": {"idle": 0.3, "sad": 0.2},
        "sad": {"idle": 0.4, "tired": 0.2},
        "shy": {"happy": 0.3, "playful": 0.2, "idle": 0.3},
    }

    def __init__(self, initial_mood: str = "idle"):
        self.current_mood = initial_mood
        self.mood_intensity: float = 0.5
        self.mood_duration: float = 0.0
        self.transition_speed: float = 1.0

    def set_mood(self, mood: str, intensity: float = 0.5) -> "MoodSystem":
        if mood in self.MOOD_TYPES:
            self.current_mood = mood
            self.mood_intensity = max(0.0, min(1.0, intensity))
            self.mood_duration = 0.0
        return self

    def get_morphs(self) -> dict[str, float]:
        base = self.MOOD_MORPH_MAP.get(self.current_mood, {})
        return {k: v * self.mood_intensity for k, v in base.items()}

    def get_possible_transitions(self) -> dict[str, float]:
        return self.MOOD_TRANSITIONS.get(self.current_mood, {})

    def to_expression_storables(self) -> list[dict]:
        morphs = self.get_morphs()
        if not morphs:
            return []
        return [{"id": "expression", "morphs": [
            {"uid": k, "value": str(v)} for k, v in morphs.items()
        ]}]

    def summary(self) -> dict:
        return {
            "mood": self.current_mood,
            "intensity": self.mood_intensity,
            "duration": self.mood_duration,
            "possible_transitions": self.get_possible_transitions(),
        }


# ── 人格系统 (from Cue Person/Personality.cs + Enums/PersonalityEnum.cs) ──

class PersonalitySystem:
    """角色人格特质 — 影响行为倾向和反应模式"""

    TRAITS = {
        "dominance": {"range": (-1.0, 1.0), "desc": "支配性 (-1被动, +1主导)"},
        "openness": {"range": (0.0, 1.0), "desc": "开放性"},
        "expressiveness": {"range": (0.0, 1.0), "desc": "表现力"},
        "energy": {"range": (0.0, 1.0), "desc": "活力"},
        "shyness": {"range": (0.0, 1.0), "desc": "害羞程度"},
        "playfulness": {"range": (0.0, 1.0), "desc": "玩乐倾向"},
        "sensitivity": {"range": (0.0, 1.0), "desc": "敏感度"},
        "patience": {"range": (0.0, 1.0), "desc": "耐心"},
    }

    PRESETS = {
        "default": {
            "dominance": 0.0, "openness": 0.5, "expressiveness": 0.5,
            "energy": 0.5, "shyness": 0.3, "playfulness": 0.5,
            "sensitivity": 0.5, "patience": 0.5,
        },
        "shy_girl": {
            "dominance": -0.5, "openness": 0.3, "expressiveness": 0.3,
            "energy": 0.4, "shyness": 0.8, "playfulness": 0.4,
            "sensitivity": 0.7, "patience": 0.6,
        },
        "confident_woman": {
            "dominance": 0.6, "openness": 0.7, "expressiveness": 0.8,
            "energy": 0.7, "shyness": 0.1, "playfulness": 0.6,
            "sensitivity": 0.4, "patience": 0.5,
        },
        "playful_girl": {
            "dominance": 0.1, "openness": 0.8, "expressiveness": 0.9,
            "energy": 0.9, "shyness": 0.2, "playfulness": 0.9,
            "sensitivity": 0.5, "patience": 0.3,
        },
        "calm_mature": {
            "dominance": 0.3, "openness": 0.6, "expressiveness": 0.4,
            "energy": 0.4, "shyness": 0.1, "playfulness": 0.3,
            "sensitivity": 0.6, "patience": 0.9,
        },
    }

    def __init__(self, preset: str = "default"):
        self.traits: dict[str, float] = copy.deepcopy(
            self.PRESETS.get(preset, self.PRESETS["default"])
        )

    def set_trait(self, trait: str, value: float) -> "PersonalitySystem":
        if trait in self.TRAITS:
            r = self.TRAITS[trait]["range"]
            self.traits[trait] = max(r[0], min(r[1], value))
        return self

    def get_trait(self, trait: str) -> float:
        return self.traits.get(trait, 0.0)

    def mood_bias(self) -> dict[str, float]:
        bias = {}
        if self.traits["shyness"] > 0.6:
            bias["shy"] = 0.3
        if self.traits["playfulness"] > 0.6:
            bias["playful"] = 0.3
        if self.traits["energy"] > 0.7:
            bias["excited"] = 0.2
        if self.traits["dominance"] > 0.5:
            bias["confident"] = 0.2
        if self.traits["dominance"] < -0.3:
            bias["shy"] = bias.get("shy", 0) + 0.2
        return bias

    def summary(self) -> dict:
        return {"traits": self.traits, "mood_bias": self.mood_bias()}


# ── 敏感度系统 (from Cue Enums/Sensitivities.cs) ──

class SensitivitiesSystem:
    """角色身体敏感区域 — 定义交互敏感点和强度

    Ported from via5/Cue Enums/Sensitivities.cs (CC0).
    Defines body zone types and their sensitivity levels for
    interaction-driven behavior (excitement, voice, animation).

    Usage:
        sens = SensitivitiesSystem()
        sens.set_sensitivity("breasts", 0.8)
        sens.set_sensitivity("mouth", 0.6)
        zone = sens.get_zone_type("breasts")  # → 2
        active = sens.active_zones()           # zones with sensitivity > 0
        storables = sens.to_storables()
    """

    ZONE_TYPES = {
        "none": -1,
        "penetration": 0,
        "mouth": 1,
        "breasts": 2,
        "genitals": 3,
        "others_excitement": 4,
    }

    ZONE_NAMES = {v: k for k, v in ZONE_TYPES.items()}

    ZONE_COUNT = 5

    # Default sensitivity presets
    PRESETS = {
        "default": {
            "penetration": 0.5,
            "mouth": 0.4,
            "breasts": 0.5,
            "genitals": 0.6,
            "others_excitement": 0.3,
        },
        "highly_sensitive": {
            "penetration": 0.8,
            "mouth": 0.7,
            "breasts": 0.8,
            "genitals": 0.9,
            "others_excitement": 0.5,
        },
        "low_sensitivity": {
            "penetration": 0.3,
            "mouth": 0.2,
            "breasts": 0.3,
            "genitals": 0.4,
            "others_excitement": 0.1,
        },
    }

    def __init__(self, preset: str = "default"):
        self.sensitivities: dict[str, float] = copy.deepcopy(
            self.PRESETS.get(preset, self.PRESETS["default"])
        )

    def set_sensitivity(self, zone: str, value: float) -> "SensitivitiesSystem":
        if zone in self.ZONE_TYPES and zone != "none":
            self.sensitivities[zone] = max(0.0, min(1.0, value))
        return self

    def get_sensitivity(self, zone: str) -> float:
        return self.sensitivities.get(zone, 0.0)

    def get_zone_type(self, zone: str) -> int:
        return self.ZONE_TYPES.get(zone, -1)

    def active_zones(self) -> list[str]:
        return [z for z, v in self.sensitivities.items() if v > 0.0]

    def excitement_contribution(self, zone: str, intensity: float = 1.0) -> float:
        """Calculate excitement delta from touching a zone."""
        base = self.get_sensitivity(zone)
        return base * intensity * 0.05

    def to_storables(self) -> list[dict]:
        return [{
            "id": "sensitivities",
            "zones": {z: str(round(v, 3)) for z, v in self.sensitivities.items()},
        }]

    @classmethod
    def zone_name(cls, zone_id: int) -> str:
        return cls.ZONE_NAMES.get(zone_id, "none")

    @classmethod
    def all_zones(cls) -> list[str]:
        return [z for z in cls.ZONE_TYPES if z != "none"]

    def summary(self) -> dict:
        return {
            "sensitivities": self.sensitivities,
            "active_zones": self.active_zones(),
        }


# ── 兴奋度系统 (from Cue Person/Excitement/Excitement.cs) ──

class ExcitementSystem:
    """角色兴奋度 — 0.0~1.0连续值，驱动表情/声音/动画强度"""

    STAGES = {
        (0.0, 0.2): "calm",
        (0.2, 0.4): "interested",
        (0.4, 0.6): "aroused",
        (0.6, 0.8): "excited",
        (0.8, 0.95): "climax_building",
        (0.95, 1.0): "orgasm",
    }

    def __init__(self):
        self.value: float = 0.0
        self.rate: float = 0.01
        self.decay: float = 0.005
        self.min_value: float = 0.0
        self.max_value: float = 1.0

    def increase(self, amount: float = 0.0) -> "ExcitementSystem":
        amount = amount or self.rate
        self.value = min(self.max_value, self.value + amount)
        return self

    def decrease(self, amount: float = 0.0) -> "ExcitementSystem":
        amount = amount or self.decay
        self.value = max(self.min_value, self.value - amount)
        return self

    def set_value(self, v: float) -> "ExcitementSystem":
        self.value = max(self.min_value, min(self.max_value, v))
        return self

    @property
    def stage(self) -> str:
        for (lo, hi), name in self.STAGES.items():
            if lo <= self.value < hi:
                return name
        return "orgasm" if self.value >= 0.95 else "calm"

    @property
    def is_orgasm(self) -> bool:
        return self.value >= 0.95

    def get_intensity_multiplier(self) -> float:
        return 0.5 + self.value * 1.5

    def suggested_mood(self) -> str:
        stage = self.stage
        return {
            "calm": "idle", "interested": "happy", "aroused": "playful",
            "excited": "excited", "climax_building": "excited",
            "orgasm": "orgasm",
        }.get(stage, "idle")

    def summary(self) -> dict:
        return {
            "value": round(self.value, 3),
            "stage": self.stage,
            "suggested_mood": self.suggested_mood(),
            "intensity_multiplier": round(self.get_intensity_multiplier(), 2),
        }


# ── 凝视系统 (from Cue Person/Gaze/Gaze.cs + Events/*.cs) ──

class GazeSystem:
    """角色凝视方向控制 — 事件驱动的视线目标切换"""

    EVENTS = [
        "idle_random", "look_at_player", "look_at_person",
        "look_at_hands", "look_away", "look_down",
        "look_above", "look_at_front", "look_at_kiss",
        "look_at_mouth", "look_at_grabbed", "look_at_interaction",
        "eyes_closed",
    ]

    TARGET_PRIORITIES = {
        "look_at_grabbed": 10,
        "look_at_kiss": 9,
        "look_at_interaction": 8,
        "look_at_mouth": 7,
        "look_at_player": 6,
        "look_at_person": 5,
        "look_at_hands": 4,
        "look_at_front": 3,
        "look_above": 2,
        "look_down": 2,
        "look_away": 1,
        "idle_random": 0,
        "eyes_closed": 0,
    }

    EYE_TARGET_PRESETS = {
        "look_at_player": {"x": 0.0, "y": 1.7, "z": 1.0},
        "look_down": {"x": 0.0, "y": 0.5, "z": 0.5},
        "look_above": {"x": 0.0, "y": 2.5, "z": 0.5},
        "look_away": {"x": 1.5, "y": 1.7, "z": 0.0},
        "look_at_front": {"x": 0.0, "y": 1.7, "z": 2.0},
    }

    def __init__(self):
        self.current_event: str = "idle_random"
        self.target_position: Optional[dict] = None
        self.active_events: list[str] = []

    def trigger_event(self, event: str,
                      target_pos: Optional[dict] = None) -> "GazeSystem":
        if event in self.EVENTS:
            new_priority = self.TARGET_PRIORITIES.get(event, 0)
            cur_priority = self.TARGET_PRIORITIES.get(self.current_event, 0)
            if new_priority >= cur_priority:
                self.current_event = event
                self.target_position = target_pos or self.EYE_TARGET_PRESETS.get(event)
            if event not in self.active_events:
                self.active_events.append(event)
        return self

    def clear_event(self, event: str) -> "GazeSystem":
        if event in self.active_events:
            self.active_events.remove(event)
        if self.current_event == event:
            self.current_event = "idle_random"
            self.target_position = None
        return self

    def get_eye_target_storable(self, atom_id: str) -> Optional[dict]:
        if not self.target_position:
            return None
        return {
            "id": f"{atom_id}:eyeTargetControl",
            "position": {k: str(v) for k, v in self.target_position.items()},
        }

    def summary(self) -> dict:
        return {
            "current_event": self.current_event,
            "priority": self.TARGET_PRIORITIES.get(self.current_event, 0),
            "target_position": self.target_position,
            "active_events": self.active_events,
        }


# ── 语音状态机 (from Cue Person/Voice/Voice.cs + State*.cs) ──

class VoiceState:
    """角色语音状态 — 根据情绪/兴奋度切换语音模式"""

    STATES = ["normal", "kiss", "orgasm", "choked", "bj", "silent"]

    STATE_PARAMS = {
        "normal": {
            "pitch_range": (0.9, 1.1),
            "volume_range": (0.3, 0.7),
            "breath_rate": 1.0,
            "moan_chance": 0.0,
        },
        "kiss": {
            "pitch_range": (0.95, 1.05),
            "volume_range": (0.1, 0.3),
            "breath_rate": 1.2,
            "moan_chance": 0.1,
        },
        "orgasm": {
            "pitch_range": (1.1, 1.4),
            "volume_range": (0.7, 1.0),
            "breath_rate": 2.5,
            "moan_chance": 0.9,
        },
        "choked": {
            "pitch_range": (0.8, 1.0),
            "volume_range": (0.1, 0.4),
            "breath_rate": 0.5,
            "moan_chance": 0.0,
        },
        "bj": {
            "pitch_range": (0.9, 1.1),
            "volume_range": (0.2, 0.5),
            "breath_rate": 1.5,
            "moan_chance": 0.3,
        },
        "silent": {
            "pitch_range": (1.0, 1.0),
            "volume_range": (0.0, 0.0),
            "breath_rate": 1.0,
            "moan_chance": 0.0,
        },
    }

    EXCITEMENT_STATE_MAP = {
        "calm": "normal",
        "interested": "normal",
        "aroused": "normal",
        "excited": "normal",
        "climax_building": "normal",
        "orgasm": "orgasm",
    }

    def __init__(self, initial_state: str = "normal"):
        self.current_state = initial_state

    def set_state(self, state: str) -> "VoiceState":
        if state in self.STATES:
            self.current_state = state
        return self

    def from_excitement(self, excitement: ExcitementSystem) -> "VoiceState":
        self.current_state = self.EXCITEMENT_STATE_MAP.get(
            excitement.stage, "normal"
        )
        return self

    @property
    def params(self) -> dict:
        return self.STATE_PARAMS.get(self.current_state, self.STATE_PARAMS["normal"])

    def summary(self) -> dict:
        return {"state": self.current_state, "params": self.params}


# ── 角色行为容器 (整合所有子系统) ──

class CharacterBehavior:
    """
    角色行为容器 — 整合情绪/人格/兴奋度/凝视/语音

    用法:
        behavior = CharacterBehavior(personality="playful_girl")
        behavior.mood.set_mood("happy", 0.7)
        behavior.excitement.increase(0.1)
        behavior.gaze.trigger_event("look_at_player")
        storables = behavior.build_storables("Person")
    """

    def __init__(self, personality: str = "default"):
        self.personality = PersonalitySystem(personality)
        self.mood = MoodSystem()
        self.excitement = ExcitementSystem()
        self.gaze = GazeSystem()
        self.voice = VoiceState()

    def update(self) -> None:
        self.voice.from_excitement(self.excitement)
        suggested = self.excitement.suggested_mood()
        if suggested != self.mood.current_mood:
            self.mood.set_mood(suggested, self.excitement.value)

    def build_storables(self, atom_id: str) -> list[dict]:
        storables = []
        storables.extend(self.mood.to_expression_storables())
        eye_target = self.gaze.get_eye_target_storable(atom_id)
        if eye_target:
            storables.append(eye_target)
        return storables

    def summary(self) -> dict:
        return {
            "personality": self.personality.summary(),
            "mood": self.mood.summary(),
            "excitement": self.excitement.summary(),
            "gaze": self.gaze.summary(),
            "voice": self.voice.summary(),
        }


# ─── ARKit BlendShape Mapping (from FacialMotionCapture, MIT) ─────────

class ARKitBlendShape:
    """Apple ARKit Face Tracking blendshape → VaM morph mapping.

    Ported from FacialMotionCapture/src/Models/CBlendShape.cs.
    Maps 52 ARKit facial blendshapes to VaM-compatible morph names,
    organized by facial region groups.

    Usage:
        name = ARKitBlendShape.name(0)           # → "Brow Inner Up"
        group = ARKitBlendShape.group(24)         # → "Jaw"
        ids = ARKitBlendShape.ids_in_group("Eyes") # → [13, 14, 15, 16, 17, 18]
        all_groups = ARKitBlendShape.all_groups()  # → ["Brows", "Eyes", ...]

        # Get VaM morph name for a blendshape
        morph = ARKitBlendShape.to_vam_morph(37)  # → "Mouth Smile Left"
    """

    # ARKit blendshape IDs
    BROW_INNER_UP = 0
    BROW_DOWN_LEFT = 1
    BROW_DOWN_RIGHT = 2
    BROW_OUTER_UP_LEFT = 3
    BROW_OUTER_UP_RIGHT = 4
    EYE_LOOK_UP_LEFT = 5
    EYE_LOOK_UP_RIGHT = 6
    EYE_LOOK_DOWN_LEFT = 7
    EYE_LOOK_DOWN_RIGHT = 8
    EYE_LOOK_IN_LEFT = 9
    EYE_LOOK_IN_RIGHT = 10
    EYE_LOOK_OUT_LEFT = 11
    EYE_LOOK_OUT_RIGHT = 12
    EYE_BLINK_LEFT = 13
    EYE_BLINK_RIGHT = 14
    EYE_SQUINT_LEFT = 15
    EYE_SQUINT_RIGHT = 16
    EYE_WIDE_LEFT = 17
    EYE_WIDE_RIGHT = 18
    CHEEK_PUFF = 19
    CHEEK_SQUINT_LEFT = 20
    CHEEK_SQUINT_RIGHT = 21
    NOSE_SNEER_LEFT = 22
    NOSE_SNEER_RIGHT = 23
    JAW_OPEN = 24
    JAW_FORWARD = 25
    JAW_LEFT = 26
    JAW_RIGHT = 27
    MOUTH_FUNNEL = 28
    MOUTH_PUCKER = 29
    MOUTH_LEFT = 30
    MOUTH_RIGHT = 31
    MOUTH_ROLL_UPPER = 32
    MOUTH_ROLL_LOWER = 33
    MOUTH_SHRUG_UPPER = 34
    MOUTH_SHRUG_LOWER = 35
    MOUTH_CLOSE = 36
    MOUTH_SMILE_LEFT = 37
    MOUTH_SMILE_RIGHT = 38
    MOUTH_FROWN_LEFT = 39
    MOUTH_FROWN_RIGHT = 40
    MOUTH_DIMPLE_LEFT = 41
    MOUTH_DIMPLE_RIGHT = 42
    MOUTH_UPPER_LEFT = 43
    MOUTH_UPPER_RIGHT = 44
    MOUTH_LOWER_DOWN_LEFT = 45
    MOUTH_LOWER_DOWN_RIGHT = 46
    MOUTH_PRESS_LEFT = 47
    MOUTH_PRESS_RIGHT = 48
    MOUTH_STRETCH_LEFT = 49
    MOUTH_STRETCH_RIGHT = 50
    MOUTH_TONGUE_OUT = 51

    MIN_ID = 0
    MAX_ID = 51

    # ID → human-readable name
    _ID_TO_NAME: dict[int, str] = {
        0: "Brow Inner Up", 1: "Brow Down Left", 2: "Brow Down Right",
        3: "Brow Outer Up Left", 4: "Brow Outer Up Right",
        5: "Eye Look Up Left", 6: "Eye Look Up Right",
        7: "Eye Look Down Left", 8: "Eye Look Down Right",
        9: "Eye Look In Left", 10: "Eye Look In Right",
        11: "Eye Look Out Left", 12: "Eye Look Out Right",
        13: "Eye Blink Left", 14: "Eye Blink Right",
        15: "Eye Squint Left", 16: "Eye Squint Right",
        17: "Eye Wide Left", 18: "Eye Wide Right",
        19: "Cheek Puff", 20: "Cheek Squint Left", 21: "Cheek Squint Right",
        22: "Nose Sneer Left", 23: "Nose Sneer Right",
        24: "Jaw Open", 25: "Jaw Forward", 26: "Jaw Left", 27: "Jaw Right",
        28: "Mouth Funnel", 29: "Mouth Pucker",
        30: "Mouth Left", 31: "Mouth Right",
        32: "Mouth Roll Upper", 33: "Mouth Roll Lower",
        34: "Mouth Shrug Upper", 35: "Mouth Shrug Lower",
        36: "Mouth Close",
        37: "Mouth Smile Left", 38: "Mouth Smile Right",
        39: "Mouth Frown Left", 40: "Mouth Frown Right",
        41: "Mouth Dimple Left", 42: "Mouth Dimple Right",
        43: "Mouth Upper Left", 44: "Mouth Upper Right",
        45: "Mouth Lower Down Left", 46: "Mouth Lower Down Right",
        47: "Mouth Press Left", 48: "Mouth Press Right",
        49: "Mouth Stretch Left", 50: "Mouth Stretch Right",
        51: "Mouth Tongue Out",
    }

    # ID → facial region group
    _ID_TO_GROUP: dict[int, str] = {
        0: "Brows", 1: "Brows", 2: "Brows", 3: "Brows", 4: "Brows",
        5: "Looking", 6: "Looking", 7: "Looking", 8: "Looking",
        9: "Looking", 10: "Looking", 11: "Looking", 12: "Looking",
        13: "Eyes", 14: "Eyes", 15: "Eyes", 16: "Eyes",
        17: "Eyes", 18: "Eyes",
        19: "Cheeks", 20: "Cheeks", 21: "Cheeks",
        22: "Nose", 23: "Nose",
        24: "Jaw", 25: "Jaw", 26: "Jaw", 27: "Jaw",
        28: "Mouth", 29: "Mouth", 30: "Mouth", 31: "Mouth",
        32: "Mouth", 33: "Mouth", 34: "Mouth", 35: "Mouth",
        36: "Mouth", 37: "Mouth", 38: "Mouth", 39: "Mouth",
        40: "Mouth", 41: "Mouth", 42: "Mouth", 43: "Mouth",
        44: "Mouth", 45: "Mouth", 46: "Mouth", 47: "Mouth",
        48: "Mouth", 49: "Mouth", 50: "Mouth",
        51: "Tongue",
    }

    @classmethod
    def name(cls, blendshape_id: int) -> str:
        return cls._ID_TO_NAME.get(blendshape_id, f"Blendshape {blendshape_id}")

    @classmethod
    def group(cls, blendshape_id: int) -> str:
        return cls._ID_TO_GROUP.get(blendshape_id, "Other")

    @classmethod
    def name_to_id(cls, name: str) -> Optional[int]:
        for k, v in cls._ID_TO_NAME.items():
            if v == name:
                return k
        return None

    @classmethod
    def ids_in_group(cls, group_name: str) -> list[int]:
        return [k for k, v in cls._ID_TO_GROUP.items() if v == group_name]

    @classmethod
    def all_groups(cls) -> list[str]:
        return sorted(set(cls._ID_TO_GROUP.values()))

    @classmethod
    def all_names(cls) -> list[str]:
        return list(cls._ID_TO_NAME.values())

    @classmethod
    def to_vam_morph(cls, blendshape_id: int) -> str:
        """Convert ARKit blendshape to VaM morph name (same name convention)."""
        return cls._ID_TO_NAME.get(blendshape_id, "")


# ─── VaM Morph Region Taxonomy (from morphology, MIT) ─────────────────

class MorphRegion:
    """VaM's standard morph region hierarchy.

    Ported from morphology/Morphology/Regions.cs.
    Defines the canonical region taxonomy used by VaM for organizing morphs.
    Useful for categorizing, filtering, and managing morphs programmatically.

    Usage:
        all_regions = MorphRegion.all_regions()
        body_regions = MorphRegion.shape_regions()
        face_regions = MorphRegion.face_regions()
        pose_regions = MorphRegion.pose_regions()
        is_valid = MorphRegion.is_standard("Morph/Head/Eyes")  # → True

        # Known problematic morphs
        bad = MorphRegion.KNOWN_BAD_MORPHS  # → list of names to avoid
    """

    # Complete VaM standard morph regions
    SHAPE_REGIONS = [
        "Morph/Anus",
        "Morph/Arms",
        "Morph/Back",
        "Morph/Body",
        "Morph/Chest/Areola",
        "Morph/Chest/Breasts",
        "Morph/Chest/Nipples",
        "Morph/Feet",
        "Morph/Genitalia",
        "Morph/Hands",
        "Morph/Head",
        "Morph/Head/Brow",
        "Morph/Head/Cheeks",
        "Morph/Head/Chin",
        "Morph/Head/Ears",
        "Morph/Head/Eyes",
        "Morph/Head/Face",
        "Morph/Head/Jaw",
        "Morph/Head/Mouth",
        "Morph/Head/Mouth/Teeth",
        "Morph/Head/Mouth/Tongue",
        "Morph/Head/Nose",
        "Morph/Head/Shape",
        "Morph/Hip",
        "Morph/Legs",
        "Morph/Neck",
        "Morph/UpperBody",
        "Morph/Waist",
    ]

    POSE_REGIONS = [
        "Pose/Arms",
        "Pose/Chest",
        "Pose/Feet/Left/Toes",
        "Pose/Feet/Right/Toes",
        "Pose/Hands/Left",
        "Pose/Hands/Left/Fingers",
        "Pose/Hands/Right",
        "Pose/Hands/Right/Fingers",
        "Pose/Head/Brow",
        "Pose/Head/Cheeks",
        "Pose/Head/Expressions",
        "Pose/Head/Eyes",
        "Pose/Head/Jaw",
        "Pose/Head/Mouth",
        "Pose/Head/Mouth/Lips",
        "Pose/Head/Mouth/Tongue",
        "Pose/Head/Nose",
        "Pose/Head/Visemes",
    ]

    # Morphs known to cause unintended side effects
    KNOWN_BAD_MORPHS = [
        "GXF_G2F_TransZUpJaw", "GXF_G2F_TransZLowJaw",
        "DollHead", "Lower head small", "Old", "Young", "Thin",
        "Face young", "MCMJulieFingersFistL", "MCMJulieFingersFistR",
        "MCMJulieThumbFistL", "MCMJulieThumbFistR", "AAdream",
        "Chest small X", "Chest small Y", "Chest small Z",
        "Hip line up", "Hip up", "Face thin",
    ]

    @classmethod
    def all_regions(cls) -> list[str]:
        return cls.SHAPE_REGIONS + cls.POSE_REGIONS

    @classmethod
    def shape_regions(cls) -> list[str]:
        return list(cls.SHAPE_REGIONS)

    @classmethod
    def pose_regions(cls) -> list[str]:
        return list(cls.POSE_REGIONS)

    @classmethod
    def face_regions(cls) -> list[str]:
        return [r for r in cls.all_regions() if "/Head" in r]

    @classmethod
    def is_standard(cls, region: str) -> bool:
        return region in cls.SHAPE_REGIONS or region in cls.POSE_REGIONS

    @classmethod
    def is_bad_morph(cls, morph_name: str) -> bool:
        return morph_name in cls.KNOWN_BAD_MORPHS

    @classmethod
    def morph_path(cls, vam_root: str, region: str = "") -> str:
        """Get filesystem path for morph files."""
        base = f"{vam_root}/Custom/Atom/Person/Morphs"
        if region:
            return f"{base}/{region.replace('/', '/')}"
        return base


# ─── VaM Registry (from acidbubbles/vam-keybindings, MIT) ────────────

class VaMRegistry:
    """Complete registry of VaM atom types, UI tabs, controllers, and settings.

    Ported from vam-keybindings/src/Keybindings/GlobalCommands.cs.
    This is the authoritative reference for all string identifiers used
    in VaM's internal API, essential for scene building and automation.

    Usage:
        # Check if a type is valid
        VaMRegistry.is_atom_type("Person")     # → True
        VaMRegistry.is_atom_type("Banana")     # → False

        # Get all atom types in a category
        VaMRegistry.atom_types_in("Shapes")    # → ["Cube", "Sphere", ...]

        # Get controller names for a Person atom
        VaMRegistry.PERSON_CONTROLLERS         # → list of 30 controllers

        # Get UI tab names
        VaMRegistry.PERSON_TABS                # → ["Clothing", "Hair", ...]
    """

    # ── Atom Types by Category ──
    ATOM_TYPES = {
        "People": ["Person"],
        "Shapes": [
            "Cube", "Sphere", "Capsule",
            "ISCube", "ISSphere", "ISCapsule", "ISCone", "ISCylinder", "ISTube",
        ],
        "FloorsAndWalls": ["Slate", "Wall", "WoodPanel"],
        "Reflective": ["Glass", "ReflectiveSlate", "ReflectiveWoodPanel"],
        "Light": ["InvisibleLight"],
        "Sound": ["AptSpeaker", "AudioSource", "RhythmAudioSource"],
        "Force": ["CycleForce", "GrabPoint", "RhythmForce", "SyncForce"],
        "Props": ["SimSheet"],
        "Toys": ["Dildo", "Paddle"],
        "Triggers": [
            "Button", "CollisionTrigger", "LookAtTrigger",
            "UIButton", "UIButtonImage", "UISlider", "UIToggle",
            "VariableTrigger",
        ],
        "Misc": [
            "AnimationPattern", "ClothGrabSphere", "CustomUnityAsset",
            "Empty", "ImagePanel", "SimpleSign", "SubScene",
            "UIText", "VaMLogo", "WebBrowser", "WebPanel",
        ],
    }

    # ── All Atom Types (flat) ──
    ALL_ATOM_TYPES = sorted(
        t for types in ATOM_TYPES.values() for t in types
    )

    # ── Person Controller Names ──
    PERSON_CONTROLLERS = [
        "control",          # root
        "headControl", "neckControl",
        "lShoulderControl", "rShoulderControl",
        "lArmControl", "rArmControl",
        "lElbowControl", "rElbowControl",
        "lHandControl", "rHandControl",
        "chestControl",
        "lNippleControl", "rNippleControl",
        "abdomen2Control", "abdomenControl",
        "hipControl", "pelvisControl",
        "testesControl",
        "penisBaseControl", "penisMidControl", "penisTipControl",
        "lThighControl", "rThighControl",
        "lKneeControl", "rKneeControl",
        "lFootControl", "rFootControl",
        "lToeControl", "rToeControl",
        "eyeTargetControl",
    ]

    # ── Common UI Tab Names ──
    COMMON_TABS = [
        "Control", "Preset", "Move", "Animation",
        "Physics Control", "Physics Object",
        "Collision Trigger", "Material", "Plugins",
    ]

    PERSON_TABS = [
        "ControlAndPhysics1",
        "Clothing", "Hair",
        "Appearance Presets", "General Presets", "Pose Presets",
        "Skin Presets", "Plugins Presets", "Morphs Presets",
        "Hair Presets", "Clothing Presets",
        "Male Morphs", "Female Morphs",
    ]

    MAIN_MENU_TABS = [
        "TabFile", "TabUserPrefs", "TabNavigation", "TabSelect",
        "TabSessionPluginPresets", "TabSessionPlugins",
        "TabScenePlugins", "TabScenePluginPresets",
        "TabSceneLighting", "TabSceneMisc", "TabAnimation",
        "TabAddAtom", "TabAudio",
    ]

    # ── Game Modes ──
    GAME_MODES = ["Play", "Edit"]

    # ── Physics Rates ──
    PHYSICS_RATES = ["Auto", "45", "90", "120"]

    # ── Time Scales ──
    TIME_SCALES = [1.0, 0.5, 0.25, 0.1]

    # ── Controller Position/Rotation States ──
    CONTROLLER_STATES = ["On", "Off"]

    @classmethod
    def is_atom_type(cls, type_name: str) -> bool:
        return type_name in cls.ALL_ATOM_TYPES

    @classmethod
    def atom_types_in(cls, category: str) -> list[str]:
        return cls.ATOM_TYPES.get(category, [])

    @classmethod
    def all_categories(cls) -> list[str]:
        return list(cls.ATOM_TYPES.keys())

    @classmethod
    def is_person_controller(cls, name: str) -> bool:
        return name in cls.PERSON_CONTROLLERS

    @classmethod
    def controller_side(cls, name: str) -> str:
        """Return 'left', 'right', or 'center' for a controller."""
        if name.startswith("l") and name[1].isupper():
            return "left"
        if name.startswith("r") and name[1].isupper():
            return "right"
        return "center"

    @classmethod
    def symmetric_pair(cls, name: str) -> str | None:
        """Get the symmetric counterpart of a controller (lHand↔rHand)."""
        side = cls.controller_side(name)
        if side == "left":
            pair = "r" + name[1:]
        elif side == "right":
            pair = "l" + name[1:]
        else:
            return None
        return pair if pair in cls.PERSON_CONTROLLERS else None

    @classmethod
    def upper_body_controllers(cls) -> list[str]:
        return [c for c in cls.PERSON_CONTROLLERS if any(
            k in c.lower() for k in
            ["head", "neck", "shoulder", "arm", "elbow", "hand", "chest", "nipple", "eye"]
        )]

    @classmethod
    def lower_body_controllers(cls) -> list[str]:
        return [c for c in cls.PERSON_CONTROLLERS if any(
            k in c.lower() for k in
            ["hip", "pelvis", "abdomen", "thigh", "knee", "foot", "toe", "testes", "penis"]
        )]

    @classmethod
    def summary(cls) -> dict:
        return {
            "atom_categories": len(cls.ATOM_TYPES),
            "total_atom_types": len(cls.ALL_ATOM_TYPES),
            "person_controllers": len(cls.PERSON_CONTROLLERS),
            "common_tabs": len(cls.COMMON_TABS),
            "person_tabs": len(cls.PERSON_TABS),
            "main_menu_tabs": len(cls.MAIN_MENU_TABS),
        }


# ─── Facial MoCap Default Mappings (from FacialMotionCapture, MIT) ────

class FacialMocapDefaults:
    """ARKit Face Tracking → VaM morph default mapping table.

    Ported from FacialMotionCapture/src/defaults.json (MIT license).
    Provides the default ARKit blendshape → VaM morph name + strength
    mappings used by the FacialMotionCapture VaM plugin.

    Usage:
        mapping = FacialMocapDefaults.get_mapping("Jaw Open")
        # → {"morph": "Mouth Open Wide 2", "strength": 1}

        all_mappings = FacialMocapDefaults.active_mappings()
        # → only mappings with non-empty morph names

        vam_morph = FacialMocapDefaults.vam_morph("Mouth Smile Left")
        # → "Mouth Smile Simple Left"
    """

    MAPPINGS: dict[str, dict] = {
        "Brow Down Left": {"morph": "Brow Down Left", "strength": 3.0},
        "Brow Down Right": {"morph": "Brow Down Right", "strength": 3.0},
        "Brow Inner Up": {"morph": "Brow Inner Up", "strength": 1.5},
        "Brow Outer Up Left": {"morph": "Brow Outer Up Left", "strength": 0.2},
        "Brow Outer Up Right": {"morph": "Brow Outer Up Right", "strength": 0.2},
        "Cheek Puff": {"morph": "Cheeks Balloon", "strength": 2.0},
        "Cheek Squint Left": {"morph": "Cheek Flex Left", "strength": 7.0},
        "Cheek Squint Right": {"morph": "Cheek Flex Right", "strength": 7.0},
        "Eye Blink Left": {"morph": "Eyes Closed Left", "strength": 1.0},
        "Eye Blink Right": {"morph": "Eyes Closed Right", "strength": 1.0},
        "Eye Squint Left": {"morph": "Eyes Squint Left", "strength": 1.0},
        "Eye Squint Right": {"morph": "Eyes Squint Right", "strength": 1.0},
        "Eye Wide Left": {"morph": "Eyes Open", "strength": 1.5},
        "Jaw Forward": {"morph": "Jaw In-Out", "strength": 1.0},
        "Jaw Open": {"morph": "Mouth Open Wide 2", "strength": 1.0},
        "Mouth Close": {"morph": "Mouth Open Wide 3", "strength": -0.7},
        "Mouth Dimple Left": {"morph": "Cheeks Dimple Crease Left", "strength": 3.0},
        "Mouth Dimple Right": {"morph": "Cheeks Dimple Crease Right", "strength": 3.0},
        "Mouth Frown Left": {"morph": "Mouth Frown", "strength": 0.5},
        "Mouth Funnel": {"morph": "OW", "strength": 1.0},
        "Mouth Left": {"morph": "Mouth Side-Side Left", "strength": 2.0},
        "Mouth Press Left": {"morph": "Mouth Narrow Left", "strength": -1.0},
        "Mouth Press Right": {"morph": "Mouth Narrow Right", "strength": -1.0},
        "Mouth Pucker": {"morph": "Lips Pucker", "strength": 1.0},
        "Mouth Right": {"morph": "Mouth Side-Side Right", "strength": 2.0},
        "Mouth Roll Lower": {"morph": "Lip Bottom In", "strength": 1.0},
        "Mouth Roll Upper": {"morph": "Lip Top Down", "strength": 1.0},
        "Mouth Shrug Lower": {"morph": "Lip Bottom Up", "strength": 0.5},
        "Mouth Shrug Upper": {"morph": "Lip Top Up", "strength": 1.0},
        "Mouth Smile Left": {"morph": "Mouth Smile Simple Left", "strength": 1.5},
        "Mouth Smile Right": {"morph": "Mouth Smile Simple Right", "strength": 1.5},
        "Mouth Tongue Out": {"morph": "Tongue Length", "strength": 0.15},
    }

    # Head rotation mappings (not morph-based, stored separately)
    HEAD_ROTATIONS: dict[str, float] = {
        "Head Left": 0.8,
        "Head Right": 0.8,
        "Head Up": 0.6,
        "Head Down": 1.5,
        "Head Tilt Left": 1.0,
        "Head Tilt Right": 1.0,
    }

    @classmethod
    def get_mapping(cls, arkit_name: str) -> Optional[dict]:
        return cls.MAPPINGS.get(arkit_name)

    @classmethod
    def vam_morph(cls, arkit_name: str) -> str:
        m = cls.MAPPINGS.get(arkit_name)
        return m["morph"] if m else ""

    @classmethod
    def strength(cls, arkit_name: str) -> float:
        m = cls.MAPPINGS.get(arkit_name)
        return m["strength"] if m else 1.0

    @classmethod
    def active_mappings(cls) -> dict[str, dict]:
        """Return only mappings with non-empty VaM morph names."""
        return {k: v for k, v in cls.MAPPINGS.items() if v["morph"]}

    @classmethod
    def all_arkit_names(cls) -> list[str]:
        return list(cls.MAPPINGS.keys())

    @classmethod
    def to_plugin_config(cls) -> dict:
        """Generate config dict compatible with FacialMotionCapture plugin."""
        return {
            "clientIp": "",
            "mappings": {
                name: {"morph": m["morph"], "strength": m["strength"]}
                for name, m in cls.MAPPINGS.items()
            },
        }

    @classmethod
    def summary(cls) -> dict:
        active = cls.active_mappings()
        return {
            "total_arkit_shapes": len(cls.MAPPINGS),
            "mapped_to_vam": len(active),
            "unmapped": len(cls.MAPPINGS) - len(active),
            "head_rotations": len(cls.HEAD_ROTATIONS),
        }


# ─── Wardrobe Texture Slots (from VamDazzler/wardrobe, CC BY 3.0) ────

class WardrobeTextureSlots:
    """VaM clothing texture property/slot constants.

    Ported from wardrobe/src/Wardrobe.cs (CC BY 3.0).
    Defines the shader property names for clothing material texture slots,
    plus naming conventions for texture file discovery.

    Usage:
        slots = WardrobeTextureSlots.ALL_SLOTS
        # → ["_MainTex", "_AlphaTex", "_BumpMap", "_GlossTex", "_SpecTex"]

        suffix = WardrobeTextureSlots.file_suffix("_BumpMap")
        # → "N"

        # Build texture search patterns for a material
        patterns = WardrobeTextureSlots.texture_patterns("MyMaterial")
        # → {"_MainTex": ["MyMaterialD", "defaultD"], ...}
    """

    DIFFUSE = "_MainTex"
    ALPHA = "_AlphaTex"
    NORMAL = "_BumpMap"
    GLOSS = "_GlossTex"
    SPECULAR = "_SpecTex"

    ALL_SLOTS = [DIFFUSE, ALPHA, NORMAL, GLOSS, SPECULAR]

    SLOT_SUFFIXES = {
        DIFFUSE: "D",
        ALPHA: "A",
        NORMAL: "N",
        GLOSS: "G",
        SPECULAR: "S",
    }

    # Texture type flags (for image loading)
    TYPE_DIFFUSE = 0
    TYPE_NORMAL = 1
    TYPE_SPECULAR = 2
    TYPE_GLOSS = 3

    SLOT_TYPES = {
        DIFFUSE: TYPE_DIFFUSE,
        ALPHA: TYPE_DIFFUSE,
        NORMAL: TYPE_NORMAL,
        SPECULAR: TYPE_SPECULAR,
        GLOSS: TYPE_GLOSS,
    }

    @classmethod
    def file_suffix(cls, slot: str) -> str:
        return cls.SLOT_SUFFIXES.get(slot, "")

    @classmethod
    def texture_type(cls, slot: str) -> int:
        return cls.SLOT_TYPES.get(slot, cls.TYPE_DIFFUSE)

    @classmethod
    def texture_patterns(cls, material_name: str) -> dict[str, list[str]]:
        """Generate texture filename search patterns per slot."""
        patterns = {}
        for slot, suffix in cls.SLOT_SUFFIXES.items():
            names = [f"{material_name}{suffix}", f"default{suffix}"]
            if slot in (cls.DIFFUSE, cls.ALPHA):
                names.append(material_name)
                names.append("default")
            patterns[slot] = names
        return patterns

    @classmethod
    def outfit_path(cls, base_dir: str, clothing_name: str,
                    outfit_name: str) -> str:
        """Construct wardrobe texture directory path."""
        return f"{base_dir}/Textures/Wardrobe/{clothing_name}/{outfit_name}"

    @classmethod
    def summary(cls) -> dict:
        return {
            "texture_slots": len(cls.ALL_SLOTS),
            "slot_names": cls.ALL_SLOTS,
        }
