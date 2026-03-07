"""
VaM 场景开发管线 — 全链路编排: 概念→角色→环境→动画→对话→打包

集成所有新模块:
  characters.py   — 角色构建
  animations.py   — 动画/姿态
  environments.py — 环境/灯光/相机
  plugin_gen.py   — 插件生成
  packaging.py    — VAR打包
  scenes.py       — 场景构建 (已有)
  resources.py    — 资源管理 (已有)

架构:
  SceneDevPipeline — 全链路开发管线
  SceneRecipe      — 场景配方 (声明式场景定义)
  BatchBuilder     — 批量场景生成
"""
import json
import copy
from pathlib import Path
from typing import Optional
from datetime import datetime

from .config import VAM_CONFIG
from .characters import CharacterBuilder, quick_character
from .animations import (
    TimelineBuilder, PoseBuilder, PoseLibrary,
    AnimationSequencer, create_breathing_animation, create_idle_sway,
)
from .environments import (
    EnvironmentBuilder, LightingRig, CameraRig,
    EnvironmentAsset, AudioConfig,
)
from .plugin_gen import PluginGenerator, ScripterGenerator, MetaGenerator
from .packaging import VarBuilder, VarInspector, DependencyResolver
from .scenes import SceneBuilder


# ── 场景配方 (声明式场景定义) ──

class SceneRecipe:
    """
    场景配方 — 声明式定义场景内容

    用法:
        recipe = SceneRecipe("romantic_dinner")
        recipe.add_character("Alice", gender="female",
            morph_template="curvy_female", expression="smile",
            position=(0.5, 0, 0), rotation=(0, -30, 0))
        recipe.add_character("Bob", gender="male",
            morph_template="athletic_male",
            position=(-0.5, 0, 0), rotation=(0, 30, 0))
        recipe.set_lighting("cinematic_warm")
        recipe.set_camera("portrait")
        recipe.add_idle_animations()
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.characters: list[dict] = []
        self.lighting_preset: Optional[str] = None
        self.camera_preset: Optional[str] = None
        self.environment_assets: list[dict] = []
        self.audio_sources: list[dict] = []
        self.animations: list[dict] = []
        self.plugins: list[dict] = []
        self.dialog_tree: Optional[dict] = None
        self.auto_breathing: bool = True
        self.auto_idle: bool = True

    def add_character(self, name: str, gender: str = "female",
                      morph_template: str = "",
                      expression: str = "neutral",
                      position: tuple = (0, 0, 0),
                      rotation: tuple = (0, 0, 0),
                      clothing: Optional[list] = None,
                      hair: Optional[str] = None) -> "SceneRecipe":
        """添加角色定义"""
        self.characters.append({
            "name": name,
            "gender": gender,
            "morph_template": morph_template,
            "expression": expression,
            "position": position,
            "rotation": rotation,
            "clothing": clothing or [],
            "hair": hair,
        })
        return self

    def set_lighting(self, preset: str) -> "SceneRecipe":
        self.lighting_preset = preset
        return self

    def set_camera(self, preset: str) -> "SceneRecipe":
        self.camera_preset = preset
        return self

    def add_environment_asset(self, name: str,
                              asset_url: str = "",
                              position: tuple = (0, 0, 0)) -> "SceneRecipe":
        self.environment_assets.append({
            "name": name,
            "asset_url": asset_url,
            "position": position,
        })
        return self

    def add_audio(self, name: str, audio_path: str,
                  volume: float = 1.0) -> "SceneRecipe":
        self.audio_sources.append({
            "name": name,
            "path": audio_path,
            "volume": volume,
        })
        return self

    def add_animation(self, character: str, animation_name: str,
                      animation_data: Optional[dict] = None) -> "SceneRecipe":
        self.animations.append({
            "character": character,
            "name": animation_name,
            "data": animation_data,
        })
        return self

    def add_idle_animations(self) -> "SceneRecipe":
        """为所有角色添加呼吸和空闲动画"""
        self.auto_breathing = True
        self.auto_idle = True
        return self

    def set_dialog(self, dialog_tree: dict) -> "SceneRecipe":
        """设置对话树"""
        self.dialog_tree = dialog_tree
        return self

    def to_dict(self) -> dict:
        """序列化配方"""
        return {
            "name": self.name,
            "description": self.description,
            "characters": self.characters,
            "lighting": self.lighting_preset,
            "camera": self.camera_preset,
            "environment_assets": self.environment_assets,
            "audio": self.audio_sources,
            "animations": self.animations,
            "auto_breathing": self.auto_breathing,
            "auto_idle": self.auto_idle,
            "has_dialog": self.dialog_tree is not None,
        }

    def save(self, filepath: Optional[str] = None) -> str:
        """保存配方到文件"""
        if not filepath:
            filepath = str(
                VAM_CONFIG.AGENT_ROOT / "recipes" / f"{self.name}.json"
            )
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=3), encoding="utf-8")
        return str(path)

    @classmethod
    def load(cls, filepath: str) -> "SceneRecipe":
        """从文件加载配方"""
        data = json.loads(Path(filepath).read_text(encoding="utf-8"))
        recipe = cls(data["name"], data.get("description", ""))
        for char in data.get("characters", []):
            recipe.add_character(**char)
        if data.get("lighting"):
            recipe.set_lighting(data["lighting"])
        if data.get("camera"):
            recipe.set_camera(data["camera"])
        for asset in data.get("environment_assets", []):
            recipe.add_environment_asset(**asset)
        for audio in data.get("audio", []):
            recipe.add_audio(**audio)
        recipe.auto_breathing = data.get("auto_breathing", True)
        recipe.auto_idle = data.get("auto_idle", True)
        return recipe


# ── 场景开发管线 ──

class SceneDevPipeline:
    """
    全链路场景开发管线

    Phase 0: 配方定义 (SceneRecipe)
    Phase 1: 角色构建 (CharacterBuilder)
    Phase 2: 环境构建 (EnvironmentBuilder)
    Phase 3: 动画构建 (TimelineBuilder)
    Phase 4: 场景组装 (SceneBuilder)
    Phase 5: 验证检查
    Phase 6: 打包发布 (VarBuilder)

    用法:
        pipeline = SceneDevPipeline(recipe)
        result = pipeline.execute()
        # result包含: scene_path, var_path, summary
    """

    def __init__(self, recipe: SceneRecipe):
        self.recipe = recipe
        self.scene_builder = SceneBuilder(recipe.name)
        self.env_builder = EnvironmentBuilder(recipe.name)
        self.character_builders: list[CharacterBuilder] = []
        self.timelines: list[TimelineBuilder] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self._phase: int = 0

    def execute(self, save_scene: bool = True,
                create_var: bool = False,
                creator: str = "Agent") -> dict:
        """
        执行完整管线

        参数:
            save_scene: 是否保存场景JSON
            create_var: 是否创建VAR包
            creator: VAR包创建者名

        返回: 执行结果摘要
        """
        result = {
            "recipe": self.recipe.name,
            "phases": {},
            "errors": [],
            "warnings": [],
        }

        # Phase 1: 角色构建
        self._phase = 1
        char_result = self._build_characters()
        result["phases"]["characters"] = char_result

        # Phase 2: 环境构建
        self._phase = 2
        env_result = self._build_environment()
        result["phases"]["environment"] = env_result

        # Phase 3: 动画构建
        self._phase = 3
        anim_result = self._build_animations()
        result["phases"]["animations"] = anim_result

        # Phase 4: 场景组装
        self._phase = 4
        scene_data = self._assemble_scene()
        result["phases"]["assembly"] = {
            "atom_count": len(scene_data.get("atoms", [])),
        }

        # Phase 5: 验证
        self._phase = 5
        validation = self._validate(scene_data)
        result["phases"]["validation"] = validation

        # 保存场景
        scene_path = None
        if save_scene:
            scene_path = self._save_scene(scene_data)
            result["scene_path"] = scene_path

        # Phase 6: 打包
        var_path = None
        if create_var:
            self._phase = 6
            var_path = self._create_var(scene_data, creator)
            result["var_path"] = var_path

        result["errors"] = self.errors
        result["warnings"] = self.warnings
        result["success"] = len(self.errors) == 0

        return result

    def _build_characters(self) -> dict:
        """Phase 1: 构建所有角色"""
        count = 0
        for char_def in self.recipe.characters:
            try:
                builder = CharacterBuilder(
                    char_def["name"],
                    char_def["gender"],
                )
                if char_def.get("morph_template"):
                    builder.morphs.from_template(char_def["morph_template"])
                if char_def.get("expression"):
                    builder.expression.set_expression(char_def["expression"])
                builder.set_position(*char_def["position"])
                builder.set_rotation(*char_def["rotation"])
                if char_def.get("hair"):
                    builder.hair.set_hair(char_def["hair"])
                for clothing in char_def.get("clothing", []):
                    if isinstance(clothing, str):
                        builder.wardrobe.add_clothing(clothing)
                    elif isinstance(clothing, dict):
                        builder.wardrobe.add_clothing(**clothing)

                self.character_builders.append(builder)
                count += 1
            except Exception as e:
                self.errors.append(
                    f"Character '{char_def['name']}' build failed: {e}"
                )

        return {"built": count, "total": len(self.recipe.characters)}

    def _build_environment(self) -> dict:
        """Phase 2: 构建环境"""
        result = {}

        # 灯光
        if self.recipe.lighting_preset:
            try:
                self.env_builder.lighting.from_preset(
                    self.recipe.lighting_preset
                )
                result["lighting"] = self.recipe.lighting_preset
            except ValueError as e:
                self.warnings.append(f"Lighting: {e}")

        # 相机
        if self.recipe.camera_preset:
            try:
                self.env_builder.cameras.from_preset(
                    self.recipe.camera_preset
                )
                result["camera"] = self.recipe.camera_preset
            except ValueError as e:
                self.warnings.append(f"Camera: {e}")

        # 环境资产
        for asset_def in self.recipe.environment_assets:
            asset = EnvironmentAsset(
                asset_def["name"],
                asset_def.get("asset_url", ""),
            )
            asset.set_position(*asset_def.get("position", (0, 0, 0)))
            self.env_builder.add_asset(asset)

        # 音频
        for audio_def in self.recipe.audio_sources:
            audio = AudioConfig(audio_def["name"], audio_def.get("path", ""))
            audio.set_volume(audio_def.get("volume", 1.0))
            self.env_builder.add_audio(audio)

        result["assets"] = len(self.recipe.environment_assets)
        result["audio"] = len(self.recipe.audio_sources)
        return result

    def _build_animations(self) -> dict:
        """Phase 3: 构建动画"""
        count = 0

        # 自动呼吸动画
        if self.recipe.auto_breathing:
            for builder in self.character_builders:
                breathing = create_breathing_animation()
                breathing.name = f"{builder.name}_breathing"
                self.timelines.append(breathing)
                count += 1

        # 自动空闲动画
        if self.recipe.auto_idle:
            for builder in self.character_builders:
                idle = create_idle_sway()
                idle.name = f"{builder.name}_idle"
                self.timelines.append(idle)
                count += 1

        # 自定义动画
        for anim_def in self.recipe.animations:
            if anim_def.get("data"):
                timeline = TimelineBuilder(anim_def["name"])
                # 从数据重建
                self.timelines.append(timeline)
                count += 1

        return {"built": count}

    def _assemble_scene(self) -> dict:
        """Phase 4: 组装场景 (匹配真实VaM场景JSON格式)"""
        scene_data = {
            "version": "1.22",
            "playerHeightAdjust": "0",
            "atoms": [],
        }

        # 角色atoms + 嵌入Timeline动画
        for builder in self.character_builders:
            atom = builder.build()

            # 将对应角色的Timeline动画嵌入为storable
            char_timelines = [
                t for t in self.timelines
                if t.name.startswith(builder.name + "_")
            ]
            if char_timelines:
                plugin_path = "Custom/Scripts/AcidBubbles/Timeline/VamTimeline.AtomPlugin.cs"
                timeline_storable = {
                    "id": "plugin#1_VamTimeline.AtomPlugin",
                    "pluginPath": plugin_path,
                    "animations": [t.build() for t in char_timelines],
                }
                atom["storables"].append(timeline_storable)

                # PluginManager storable
                has_pm = any(
                    s.get("id") == "PluginManager"
                    for s in atom["storables"]
                )
                if not has_pm:
                    atom["storables"].append({
                        "id": "PluginManager",
                        "plugins": {
                            "plugin#1": plugin_path,
                        },
                    })

            scene_data["atoms"].append(atom)

        # 环境atoms
        env_atoms = self.env_builder.build_atoms()
        scene_data["atoms"].extend(env_atoms)

        return scene_data

    def _validate(self, scene_data: dict) -> dict:
        """Phase 5: 验证场景"""
        result = {"valid": True, "checks": []}

        # 检查是否有atom
        atom_count = len(scene_data.get("atoms", []))
        if atom_count == 0:
            result["valid"] = False
            result["checks"].append("No atoms in scene")
            self.errors.append("Scene has no atoms")
        else:
            result["checks"].append(f"Atom count: {atom_count}")

        # 检查atom ID唯一性
        atom_ids = [a.get("id", "") for a in scene_data.get("atoms", [])]
        duplicates = [x for x in set(atom_ids) if atom_ids.count(x) > 1]
        if duplicates:
            result["valid"] = False
            result["checks"].append(f"Duplicate atom IDs: {duplicates}")
            self.errors.append(f"Duplicate atom IDs: {duplicates}")

        # 检查Person类型atoms
        person_count = sum(
            1 for a in scene_data.get("atoms", [])
            if a.get("type") == "Person"
        )
        result["checks"].append(f"Person atoms: {person_count}")

        return result

    def _save_scene(self, scene_data: dict) -> str:
        """保存场景到文件"""
        target_dir = VAM_CONFIG.SCENES_GENERATED
        target_dir.mkdir(parents=True, exist_ok=True)
        filepath = target_dir / f"{self.recipe.name}.json"
        filepath.write_text(
            json.dumps(scene_data, indent=3), encoding="utf-8"
        )
        return str(filepath)

    def _create_var(self, scene_data: dict, creator: str) -> str:
        """Phase 6: 创建VAR包"""
        builder = VarBuilder(creator, self.recipe.name, version=1)
        builder.add_scene(scene_data, self.recipe.name)
        if self.recipe.description:
            builder.set_description(self.recipe.description)

        try:
            return builder.build()
        except Exception as e:
            self.errors.append(f"VAR build failed: {e}")
            return ""


# ── 批量构建器 ──

class BatchBuilder:
    """
    批量场景生成器

    用法:
        batch = BatchBuilder()
        batch.add_recipe(recipe1)
        batch.add_recipe(recipe2)
        results = batch.build_all()
    """

    def __init__(self, creator: str = "Agent"):
        self.recipes: list[SceneRecipe] = []
        self.creator = creator

    def add_recipe(self, recipe: SceneRecipe) -> "BatchBuilder":
        self.recipes.append(recipe)
        return self

    def build_all(self, save_scenes: bool = True,
                  create_vars: bool = False) -> list[dict]:
        """批量构建所有配方"""
        results = []
        for recipe in self.recipes:
            pipeline = SceneDevPipeline(recipe)
            result = pipeline.execute(
                save_scene=save_scenes,
                create_var=create_vars,
                creator=self.creator,
            )
            results.append(result)
        return results

    def summary(self) -> dict:
        return {
            "recipe_count": len(self.recipes),
            "recipes": [r.name for r in self.recipes],
        }


# ── 预定义场景模板 ──

SCENE_TEMPLATES = {
    "portrait_studio": {
        "description": "人像摄影棚 — 单人+三点布光+人像相机",
        "characters": [
            {"name": "Model", "gender": "female",
             "morph_template": "athletic_female",
             "expression": "smile", "position": (0, 0, 0),
             "rotation": (0, 0, 0)},
        ],
        "lighting": "three_point",
        "camera": "portrait",
    },
    "two_person_dialog": {
        "description": "双人对话场景 — 面对面+暖色灯光",
        "characters": [
            {"name": "CharA", "gender": "female",
             "morph_template": "slim_female",
             "expression": "neutral", "position": (0.5, 0, 0),
             "rotation": (0, -30, 0)},
            {"name": "CharB", "gender": "male",
             "morph_template": "average_male",
             "expression": "neutral", "position": (-0.5, 0, 0),
             "rotation": (0, 30, 0)},
        ],
        "lighting": "cinematic_warm",
        "camera": "multi_angle",
    },
    "dramatic_single": {
        "description": "戏剧性单人 — 高对比灯光+电影相机",
        "characters": [
            {"name": "Subject", "gender": "female",
             "morph_template": "curvy_female",
             "expression": "neutral", "position": (0, 0, 0),
             "rotation": (0, -15, 0)},
        ],
        "lighting": "dramatic",
        "camera": "cinematic",
    },
}


def create_from_template(template_name: str,
                         scene_name: Optional[str] = None) -> SceneRecipe:
    """从预定义模板创建场景配方"""
    if template_name not in SCENE_TEMPLATES:
        raise ValueError(
            f"Unknown template: {template_name}. "
            f"Available: {list(SCENE_TEMPLATES.keys())}"
        )
    tmpl = SCENE_TEMPLATES[template_name]
    recipe = SceneRecipe(
        scene_name or template_name,
        tmpl.get("description", ""),
    )
    for char in tmpl["characters"]:
        recipe.add_character(**char)
    if tmpl.get("lighting"):
        recipe.set_lighting(tmpl["lighting"])
    if tmpl.get("camera"):
        recipe.set_camera(tmpl["camera"])
    return recipe


def quick_scene(template_name: str,
                save: bool = True) -> dict:
    """快速创建场景 (从模板→管线→保存)"""
    recipe = create_from_template(template_name)
    pipeline = SceneDevPipeline(recipe)
    return pipeline.execute(save_scene=save)


def list_templates() -> list[dict]:
    """列出所有场景模板"""
    return [
        {"name": k, "description": v["description"],
         "character_count": len(v["characters"])}
        for k, v in SCENE_TEMPLATES.items()
    ]
