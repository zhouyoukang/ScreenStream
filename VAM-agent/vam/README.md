# VaM 统一控制包 v2.0

Agent代替用户管控VaM一切操作的Python包 — 从感知到创造的全链路自动化。

## 模块

### 核心模块 (v1.x)
| 模块 | 功能 |
|------|------|
| `config.py` | 路径/常量/服务配置中心 |
| `process.py` | 服务启停/状态检测/健康检查 |
| `scenes.py` | 场景CRUD + SceneBuilder参数化构建 |
| `resources.py` | VAR包/外观/服装/脚本/磁盘管理 |
| `plugins.py` | BepInEx/Custom Scripts/PluginData |
| `logs.py` | 日志监控/错误检测/关键词搜索 |
| `gui.py` | VaM GUI自动化 (OCR+坐标点击+快捷键) |
| `bridge/` | BepInEx HTTP Bridge 运行时直控 |

### 场景开发模块 (v2.0 新增)
| 模块 | 功能 | 来源 |
|------|------|------|
| `characters.py` | 角色构建 (形态/外观/服装/发型/表情) | vam-story-builder + wardrobe + vam-embody |
| `animations.py` | 动画构建 (姿态/时间线/序列/触发器) | vam-timeline + vam-story-builder |
| `environments.py` | 环境构建 (灯光方案/相机/资产/音频) | vam-story-builder templates |
| `plugin_gen.py` | 插件代码生成 (C#/Scripter/meta.json) | vam-plugin-template + vam-scripter |
| `packaging.py` | VAR包创建/检查/依赖解析 | vamtb VarFile |
| `pipeline.py` | 全链路开发管线 (配方→场景→VAR) | 全部集成 |

### Agent层
| 模块 | 功能 |
|------|------|
| `agent.py` | 七感统一Agent (视/听/触/嗅/味/手/造) |
| `__main__.py` | CLI入口 (`python -m vam <cmd>`) |

## 快速使用

```python
from vam import VaMAgent

agent = VaMAgent()

# ── 感知 ──
print(agent.quick_report())       # 快速报告
dashboard = agent.dashboard()     # 综合仪表板

# ── 创造 (v2.0) ──

# 从模板一键创建场景
result = agent.create_scene_from_template("portrait_studio")

# 自定义角色
char = agent.create_character("Alice", gender="female",
    morph_template="athletic_female", expression="smile")

# 环境 (灯光+相机)
env_atoms = agent.create_environment(lighting="three_point", camera="portrait")

# 声明式场景配方
recipe = agent.create_scene_recipe("my_scene")
recipe.add_character("Alice", gender="female", morph_template="curvy_female",
                     expression="happy", position=(0.5, 0, 0))
recipe.add_character("Bob", gender="male", morph_template="athletic_male",
                     position=(-0.5, 0, 0))
recipe.set_lighting("cinematic_warm")
recipe.set_camera("multi_angle")

# 执行管线
pipeline = agent.create_scene_pipeline(recipe)
result = pipeline.execute(save_scene=True)

# 生成C#插件
gen = agent.create_plugin("MyPlugin")
gen.add_bool("enabled", "Enable", True)
gen.add_float("speed", "Speed", 1.0, 0.0, 10.0)
path = gen.deploy()

# VAR打包
var_path = agent.create_var("MyCreator", "MyScene", scene_data)

# 开发仪表板
dev = agent.dev_dashboard()
```

## 预设库

- **形态模板**: athletic_female, curvy_female, slim_female, athletic_male, average_male
- **表情预设**: neutral, smile, happy, sad, angry, surprise, wink, pout, laugh
- **姿态预设**: standing, sitting, lying_down, t_pose, arms_crossed, hands_on_hips
- **灯光方案**: three_point, cinematic_warm, studio_soft, dramatic, night_mood
- **相机方案**: portrait, full_body, multi_angle, cinematic
- **场景模板**: portrait_studio, two_person_dialog, dramatic_single

## 七感架构

- **视(see)** — 场景/日志/插件/VAR包/角色资产/环境资产/预设列表
- **听(hear)** — 服务端口/进程状态
- **触(touch)** — 进程启停/场景CRUD/脚本部署/插件部署
- **嗅(smell)** — 风险预判/错误检测/磁盘预警/缺失依赖
- **味(taste)** — 健康检查/资源扫描/依赖图分析
- **手(hand)** — VaM GUI直接操控 (OCR+坐标+快捷键)
- **造(create)** — 角色/动画/环境/插件/VAR包/场景管线
