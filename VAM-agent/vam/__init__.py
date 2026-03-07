"""
VaM Agent 控制包 — VaM 3D引擎软件自动化

七感架构:
  视(Vision)  — 场景JSON/日志/文件状态感知
  听(Audio)   — VaM进程状态/端口探测
  触(Touch)   — 文件写入/进程启停/场景创建修改
  嗅(Scent)   — 风险预判/依赖分析/健康检查
  味(Taste)   — E2E质量评估/资源扫描
  手(Hand)    — VaM GUI直接操控(OCR+坐标点击+快捷键)
  造(Create)  — 场景/角色/动画/环境/插件/VAR包程序化创建

模块:
  config       — VaM路径/常量配置
  process      — VaM进程管理
  scenes       — 场景CRUD + SceneBuilder
  resources    — 资源管理(VAR/外观/服装/脚本)
  plugins      — 插件管理(BepInEx/AddonPackages)
  logs         — VaM日志监控与错误检测
  gui          — VaM GUI自动化(OCR文字识别+模拟用户操作)
  characters   — 角色构建(形态/外观/服装/发型/表情)
  animations   — 动画构建(姿态/时间线/序列)
  environments — 环境构建(灯光/相机/资产/音频)
  plugin_gen   — 插件代码生成(C#/Scripter/meta.json)
  packaging    — VAR包创建/检查/依赖解析
  pipeline     — 全链路开发管线(配方→角色→环境→动画→场景→VAR)
  agent        — VaM统一Agent(七感集成)

Voxta相关功能已迁移至 voxta/ 包。
"""

__version__ = "2.4.0"

from .config import VAM_CONFIG
from .agent import VaMAgent
from . import gui
from .characters import (CharacterBuilder, MorphPreset, ExpressionManager,
                         BodyPartType, MoodSystem, PersonalitySystem,
                         SensitivitiesSystem, ExcitementSystem, GazeSystem,
                         VoiceState, CharacterBehavior, ARKitBlendShape,
                         MorphRegion, VaMRegistry, FacialMocapDefaults,
                         WardrobeTextureSlots)
from .animations import (TimelineBuilder, PoseBuilder, PoseLibrary, AnimationSequencer,
                          Easing, BVHParser, ProceduralAnimation, SynergyStepAnimation,
                          CameraDirector, VMDBoneMap, VMDParser, TimelineAPI,
                          MMDFaceMorphMap, FingerMorphMap, DazBoneMap,
                          VMDSceneImporter, LaunchMotionSource)
from .environments import EnvironmentBuilder, LightingRig, CameraRig
from .plugin_gen import PluginGenerator, ScripterGenerator, MetaGenerator
from .packaging import VarBuilder, VarInspector, DependencyResolver
from .pipeline import SceneDevPipeline, SceneRecipe, BatchBuilder
from .discovery import (ResourceIndex, VarScanner, AssetResolver, get_index,
                        quick_search, DepsScanner, VarCleaner)
