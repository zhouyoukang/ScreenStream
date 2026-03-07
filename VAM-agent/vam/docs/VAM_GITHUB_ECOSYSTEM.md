# VaM GitHub 生态全景图

> GitHub上所有Virt-A-Mate相关优质开源项目的系统性整理与分析。
> 更新时间: 2026-03-04 | 数据来源: GitHub API搜索 + 开发者仓库遍历
> 本地克隆: `VAM-agent/external/` (20个仓库, ~241MB, .gitignore排除)
> 另见: `VAM_AI_ECOSYSTEM.md` (AI/LLM/TTS/STT生态)

## 一、生态概览

| 维度 | 数据 |
|------|------|
| VaM相关仓库总数 | 50+ |
| 核心开发者 | 9位 (acidbubbles/MewCo-AI/lfe999/via5/hazmhox/morph1sm/Playable2030/NaturalWhiteX/vaminator) |
| 最高星标 | 684 (MewCo-AI/ai_virtual_mate_comm) |
| 主要语言 | C# (VaM插件) / Python (自动化工具) |
| 许可证 | GPLv3为主, 部分MIT |

## 二、Tier 1 — 核心项目 (50+ stars)

### 2.1 MewCo-AI/ai_virtual_mate_comm (684 stars)
- **类型**: AI虚拟伙伴社区版
- **语言**: Python
- **更新**: 2026-03-02 (活跃)
- **核心价值**: 国产AI虚拟伴侣完整方案, 支持VaM集成, LLM对话+TTS+表情驱动
- **整合价值**: 高 — 可参考其AI驱动架构, 对话策略, 情感分析模块
- **URL**: https://github.com/MewCo-AI/ai_virtual_mate_comm

### 2.2 NaturalWhiteX/hello-vam-releases (344 stars)
- **类型**: VaM游戏启动器/管理器
- **更新**: 活跃
- **核心价值**: 国产VaM启动器, 游戏管理/依赖下载/附加包安装, 百度网盘分发
- **本地克隆**: `external/hello-vam-releases/`
- **整合价值**: 中 — 可参考其依赖检测和包安装逻辑
- **URL**: https://github.com/NaturalWhiteX/hello-vam-releases

### 2.3 NaturalWhiteX/vambox-release (157 stars)
- **类型**: VaM Box 发布主页
- **更新**: 2026-03-03 (活跃)
- **核心价值**: VaM包管理器/资源浏览器, 简化VAR包安装和管理
- **本地状态**: 已安装 v0.9.2 (`E:\浏览器下载\vambox-v0.9.2\`)
- **整合价值**: 中 — 已在使用, 可参考其VAR包解析逻辑
- **URL**: https://github.com/NaturalWhiteX/vambox-release

### 2.4 MewCo-AI/ai_virtual_mate_linux (124 stars)
- **类型**: AI虚拟伙伴Linux版
- **语言**: Python
- **核心价值**: Linux平台VaM+AI方案, 跨平台参考
- **URL**: https://github.com/MewCo-AI/ai_virtual_mate_linux

### 2.5 acidbubbles/vam-timeline (91 stars)
- **类型**: 动画时间线编辑器
- **语言**: C#
- **许可证**: GPLv3
- **核心价值**: VaM最重要的动画插件, 关键帧动画编辑, 曲线控制
- **本地状态**: 已通过VAR包安装
- **整合价值**: 高 — Bridge已支持Timeline控制 (runtime_timeline_play/stop/scrub/speed)
- **URL**: https://github.com/acidbubbles/vam-timeline
- **Wiki**: https://github.com/acidbubbles/vam-timeline/wiki

### 2.6 acidbubbles/vam-plugin-template (56 stars)
- **类型**: VSCode插件开发模板
- **语言**: C#
- **核心价值**: VaM C#插件标准开发模板, GitHub Actions自动构建VAR
- **整合价值**: 高 — Agent可用此模板自动生成新插件项目
- **URL**: https://github.com/acidbubbles/vam-plugin-template

## 三、Tier 2 — 重要项目 (10-49 stars)

### 3.1 acidbubbles/vam-embody (34 stars)
- **类型**: VR沉浸体验 (Improved PoV + Passenger + Snug)
- **核心价值**: 改善VR第一人称视角, 摄像机放在眼球位置, 消除视觉伪影
- **整合价值**: 中 — VR体验优化, Bridge可控制PoV参数
- **URL**: https://github.com/acidbubbles/vam-embody

### 3.2 acidbubbles/vam-collider-editor (29 stars)
- **类型**: 碰撞体编辑器
- **许可证**: MIT
- **核心价值**: 精细控制VaM人物碰撞体/刚体参数, 胸部/臀部物理调优
- **URL**: https://github.com/acidbubbles/vam-collider-editor

### 3.3 acidbubbles/vam-varbsorb (25 stars)
- **类型**: VAR包清理工具
- **核心价值**: 扫描VaM目录, 找到VAR包中已有的松散文件并删除, 节省磁盘
- **整合价值**: 高 — 可集成到 resources.py 的磁盘清理功能
- **URL**: https://github.com/acidbubbles/vam-varbsorb

### 3.4 lfe999/FacialMotionCapture (22 stars)
- **类型**: 面部动作捕捉
- **语言**: C#
- **核心价值**: 实时面部动捕驱动VaM角色表情
- **整合价值**: 中 — 可与Bridge的expression API联动
- **URL**: https://github.com/lfe999/FacialMotionCapture

### 3.5 acidbubbles/vam-scripter (21 stars)
- **类型**: VaM内脚本语言
- **核心价值**: 在VaM插件中编写代码, 脚本化场景逻辑
- **本地状态**: 已安装 v1.21 (Scripter VAR)
- **整合价值**: 高 — Agent可通过Scripter API动态注入代码到VaM
- **URL**: https://github.com/acidbubbles/vam-scripter

### 3.6 acidbubbles/vam-keybindings (20 stars)
- **类型**: VIM风格键绑定
- **核心价值**: 自定义VaM快捷键, 提高操作效率
- **整合价值**: 中 — Agent的GUI自动化可利用键绑定
- **URL**: https://github.com/acidbubbles/vam-keybindings

### 3.7 acidbubbles/vam-improved-pov (19 stars)
- **类型**: 改进第一人称视角
- **核心价值**: 已合并入vam-embody, 独立版仍可用
- **URL**: https://github.com/acidbubbles/vam-improved-pov

### 3.8 vam-community/vam-party (18 stars)
- **类型**: VaM包管理器
- **语言**: C#
- **核心价值**: 社区驱动的VaM资源发现/安装工具
- **整合价值**: 中 — 可参考其包索引API设计
- **URL**: https://github.com/vam-community/vam-party

### 3.9 acidbubbles/vam-glance (16 stars)
- **类型**: 头部驱动眼球追踪
- **核心价值**: 动捕时自然的眼球跟踪, 增强角色真实感
- **URL**: https://github.com/acidbubbles/vam-glance

### 3.10 acidbubbles/vam-devtools (16 stars)
- **类型**: VaM开发工具集
- **核心价值**: 插件开发辅助工具, 调试/检查/性能分析
- **整合价值**: 高 — 可参考其调试API用于Agent的runtime诊断
- **URL**: https://github.com/acidbubbles/vam-devtools

### 3.11 acidbubbles/vam-acidbubbles-home (14 stars)
- **类型**: AcidBubbles插件主页
- **核心价值**: 所有AcidBubbles插件的索引和文档入口
- **URL**: https://github.com/acidbubbles/vam-acidbubbles-home

### 3.12 acidbubbles/vam-utilities (13 stars)
- **类型**: 小工具合集
- **核心价值**: 各种小型VaM脚本工具
- **URL**: https://github.com/acidbubbles/vam-utilities

### 3.13 lfe999/KeyboardShortcuts (13 stars)
- **类型**: 键盘/手柄快捷键
- **核心价值**: 用键盘或游戏手柄控制VaM, 支持自定义映射
- **整合价值**: 中 — Agent GUI自动化的参考
- **URL**: https://github.com/lfe999/KeyboardShortcuts

### 3.14 BoominBobbyBo/iHV (13 stars)
- **类型**: VAR文件管理器
- **核心价值**: 非官方VAR包管理工具, 版本管理/依赖追踪
- **整合价值**: 中 — 可参考其VAR解析算法用于resources.py
- **URL**: https://github.com/BoominBobbyBo/iHV

### 3.15 morph1sm/morphology (10 stars)
- **类型**: Morph整理工具
- **语言**: C#
- **核心价值**: 管理和组织VaM自定义Morph文件
- **整合价值**: 中 — Bridge已有morph API, 可参考其分类逻辑
- **URL**: https://github.com/morph1sm/morphology

## 四、Tier 3 — 实用项目 (2-9 stars)

### 新发现项目 (2026-03更新)

| Stars | 项目 | 类型 | 核心功能 | 本地克隆 |
|-------|------|------|----------|----------|
| 7 | vaminator/vamtb | Python | VAR工具箱(DB索引/依赖追踪/校验和/GUI) | ✅ external/vamtb/ |
| 5 | OnePunchVAM/vam-story-builder | Python | 场景脚手架(merge-load兼容/对话树/Twine集成) | ✅ external/vam-story-builder/ |
| 0 | honda78902/VAM-VarHandler | PS1 | VAR包处理(打包/解包/统一/清理/修复/查看) | ✅ external/VAM-VarHandler/ |
| 0 | onlyxy1986/VarBundler | Rust | VAR依赖打包(所有依赖合并为单文件) | — |
| 0 | vega-holdings/Voxta.VamProxy | C# | Voxta远程代理(WebSocket+音频转发+麦克风流) | ✅ external/Voxta.VamProxy/ |
| 1 | vega-holdings/voxta_unoffical_docs | TS | Voxta非官方文档(160+故障排除/legacy/API) | ✅ external/voxta_unoffical_docs/ |
| 0 | NaturalWhiteX/vam-text-dump | C# | BepInEx UI文本导出插件 | — |
| 1 | lfe999/VamMorphTimelineRecorder | C# | Morph录制到Timeline | — |
| 0 | mjanek20/VamTimelineTool | Python | Timeline辅助工具 | — |
| 12 | lfe999/VamFreeMMD | C# | MMD动画播放器 | ✅ external/VamFreeMMD/ |

### 原有项目

| Stars | 项目 | 类型 | 核心功能 |
|-------|------|------|----------|
| 9 | yunidatsu/Eosin_VRRenderer | C# | VR180/VR360/2D视频渲染器 + BVH动画 |
| 9 | acidbubbles/vam-snug | C# | VR控制器偏移校准 |
| 8 | acidbubbles/vam-passenger | C# | 跟随模型头部(非控制模型) |
| 7 | acidbubbles/vambooru | C# | VaM资源分享站 (ASP.NET) |
| 7 | acidbubbles/vam-body-shader | C# | 自定义皮肤着色器 |
| 7 | acidbubbles/vam-desktopleap | C# | 桌面模式Leap Motion支持 |
| 7 | acidbubbles/vam-director | C# | 摄像机角度序列编排 |
| 7 | Playable2030/VaM_PerformancePlugin | C# | 性能优化插件 |
| 6 | acidbubbles/vam-spawnpoint | C# | 玩家位置传送 |
| 6 | acidbubbles/vam-jiggle | C# | 骨骼抖动物理 |
| 6 | acidbubbles/vam-cornwall | C# | 音频呼吸效果 |
| 6 | acidbubbles/vam-keyboard-triggers | C# | 按键触发器 |
| 6 | acidbubbles/vam-leap-possess | C# | Leap Motion手部附身 |
| 6 | morph1sm/vam-scenery | Python | 场景画廊浏览器 |
| 5 | via5/Vamos | C# | BepInEx工具插件 |
| 4 | lfe999/VamLightTexture | C# | 灯光纹理Cookie |
| 4 | imakeboobies/VAM-MapLoader | C# | Unity地图加载器 |
| 3 | hazmhox/vam-overlays | C# | 屏幕覆盖层 |
| 2 | hazmhox/crowd-generator | C# | 群体角色生成器 |
| 2 | mrmr32/vam-facetracking | C# | 面部+眼球追踪导入 |
| 0 | PennAtHome/VaMToolBox | Python | VaM工具集 |

## 五、核心开发者画像

### AcidBubbles (acidbubbles) — VaM生态最重要的贡献者
- **仓库数**: 25+ 个VaM相关项目
- **总星标**: 400+
- **代表作**: Timeline(91) / Plugin-Template(56) / Embody(34) / Scripter(21) / Keybindings(20)
- **也是**: Voxta AI对话引擎的作者
- **风格**: 高质量C#代码, GPLv3许可, 完善文档和Wiki

### MewCo-AI — 国产AI虚拟伙伴
- **仓库数**: 2个
- **总星标**: 808
- **代表作**: ai_virtual_mate_comm(684) / ai_virtual_mate_linux(124)
- **特色**: 中文社区, Python实现, 支持多种AI后端

### lfe999 — VaM交互增强
- **代表作**: FacialMotionCapture(22) / KeyboardShortcuts(13) / VamLightTexture(4)
- **特色**: 专注用户交互和输入增强

### via5 — BepInEx工具链
- **代表作**: Vamos(5)
- **特色**: BepInEx底层工具开发

### hazmhox — 视觉效果
- **代表作**: vam-overlays(3) / crowd-generator(2)
- **特色**: 视觉增强和群体效果

### morph1sm — 资源管理
- **代表作**: morphology(10) / vam-scenery(6)
- **特色**: Morph和场景的管理工具

### Playable2030 — 性能优化
- **代表作**: VaM_PerformancePlugin(7)
- **特色**: 运行时性能优化

## 六、整合价值矩阵

### 与VAM-agent已有能力的映射

| GitHub项目 | VAM-agent对应模块 | 整合方向 |
|------------|-------------------|----------|
| vam-timeline | bridge.timeline_* | 已整合: Bridge支持Timeline控制 |
| vam-scripter | plugins.deploy_script | 已整合: Agent可部署脚本 |
| vam-embody | bridge.set_controller | 可通过Bridge控制PoV参数 |
| vam-varbsorb | resources.py | 可整合: 添加VAR清理功能 |
| vam-plugin-template | plugins.py | 可整合: 自动生成插件项目 |
| vam-devtools | bridge.health_report | 可参考: 运行时诊断增强 |
| iHV | resources.list_var_packages | 可参考: VAR依赖分析 |
| morphology | bridge.list_morphs | 已整合: Bridge支持Morph操作 |
| FacialMotionCapture | bridge.set_expression | 可联动: 表情API |
| vam-scenery | scenes.list_scenes | 类似功能已有 |
| ai_virtual_mate_comm | agent.py | 可参考: AI驱动架构 |
| VaM_PerformancePlugin | config.BEPINEX_KNOWN | 已记录: FasterVaM.dll |

### 推荐新增整合 (按优先级)

| 优先级 | 整合项 | 来源项目 | 投入 | 收益 |
|--------|--------|----------|------|------|
| P1 | VAR包依赖分析 | varbsorb/iHV | 4h | 资源清理, 节省磁盘 |
| P1 | 插件项目生成器 | plugin-template | 2h | Agent自动创建C#插件 |
| P2 | MewCo-AI对话策略参考 | ai_virtual_mate_comm | 研究 | 改进chat_engine |
| P2 | 性能监控集成 | VaM_PerformancePlugin | 2h | 运行时性能指标 |
| P3 | 场景画廊UI | vam-scenery | 4h | 可视化场景浏览 |
| P3 | 群体角色批量操作 | crowd-generator | 研究 | 多角色场景自动化 |

## 七、本地克隆清单

> 路径: `VAM-agent/external/` | 总计: 20仓库 ~241MB | `.gitignore`已排除

| 大小 | 仓库 | 类型 | 整合价值 |
|------|------|------|----------|
| 127MB | vamtb | Python VAR工具箱 | ★★★ VAR数据库/依赖追踪 |
| 81MB | ai_virtual_mate_comm | Python AI伴侣 | ★★ 对话策略参考 |
| 10MB | KeyboardShortcuts | C# 快捷键 | ★ 输入参考 |
| 6MB | FacialMotionCapture | C# 面捕 | ★ 表情API联动 |
| 6MB | VaM_PerformancePlugin | C# 性能优化 | ★ 性能监控 |
| 5MB | voxta_unoffical_docs | Voxta文档 | ★★★ 160+知识库 |
| 2MB | vam-timeline | C# 动画 | ★★ Bridge已集成 |
| 1MB | vam-story-builder | Python 场景 | ★★ 场景自动化 |
| <1MB | vam-embody/scripter/collider-editor/devtools/varbsorb/plugin-template/VamFreeMMD/VAM-VarHandler/Voxta.VamProxy/vam-party/hello-vam-releases/vambox-release | 各类工具插件 | ★~★★ |

## 八、VaM Box 生态

### 项目信息
- **GitHub**: NaturalWhiteX/vambox-release (157 stars)
- **本地版本**: v0.9.2
- **本地路径**: `E:\浏览器下载\vambox-v0.9.2\vambox-win32-x64\`
- **功能**: Electron桌面应用, VAR包管理/浏览/安装/更新

### 与VAM-agent的关系
- VaM Box专注于**用户UI层**的包管理
- VAM-agent专注于**程序化/Agent层**的自动化控制
- 互补关系: Agent可调用VaM Box的包索引, VaM Box可用Agent的API

## 九、社区资源站

| 站点 | 类型 | URL |
|------|------|-----|
| VaM Hub | 官方资源中心 | hub.virtamate.com |
| VaMBooru | 社区分享站 (acidbubbles) | github.com/acidbubbles/vambooru |
| VaM Party | 社区包管理 | github.com/vam-community/vam-party |
| Reddit r/VAMscenes | Reddit社区 | reddit.com/r/VAMscenes |

## 十、关键发现与问题

### 发现
1. **AcidBubbles是VaM+Voxta双生态核心**: Timeline/Scripter/Embody/DevTools + Voxta引擎, 一人撑起半个生态
2. **MewCo-AI是国产VaM-AI最大项目**: 684星, 完整的AI虚拟伴侣方案, Python实现
3. **Hello VaM是第二大VaM项目**: 344星, 国产启动器/包管理器 (2026-03新发现)
4. **VaM Box是唯一GUI包管理器**: 157星, Electron应用, 活跃更新
5. **vamtb是最完整的Python VAR工具**: 7星但代码质量高, SQLite索引/依赖追踪/校验和
6. **Voxta.VamProxy解决远程连接**: WebSocket代理+音频转发, 使VaM可连接远程Voxta
7. **voxta_unoffical_docs是Voxta知识金矿**: 160+故障排除文档, legacy API文档, 实现计划
8. **C#插件生态成熟**: 30+个高质量插件项目, GPLv3为主
9. **Python工具增多**: vamtb/story-builder/MewCo-AI + VAM-agent共4个Python项目
10. **社区包管理分散**: VaM Party/iHV/VaM Box/Hello VaM各自为战
11. **VPM是最完整的C#包管理器**: 11星, WPF应用, 51个服务文件, DependencyGraph/OptimizedVarScanner
12. **vam-keybindings是VaM命令完整参考**: 20星, 696行GlobalCommands.cs, 46种Atom类型/31个Controller

## 七、第二批克隆 (2026-03-04, +6个仓库, 共26个)

| 星标 | 仓库 | 语言 | 整合价值 | 整合状态 |
|------|------|------|----------|---------|
| 20 | acidbubbles/vam-keybindings | C# | ★★★ VaM完整命令参考(46 atom types, 31 controllers) | ✅ → scenes.py常量 |
| 19 | acidbubbles/vam-improved-pov | C# | ★ POV相机参考 | 参考 |
| 13 | acidbubbles/vam-utilities | C# | ★ 小工具集(BlendShapes/FOV/TimeScale) | 参考 |
| 11 | gicstin/VPM | C# | ★★★ 包管理器(DependencyGraph/OptimizedVarScanner/ContentTagScanner) | ✅ → resources.py |
| 11 | VamDazzler/wardrobe | C# | ★★ 服装纹理管理 | 参考 |
| 5 | vam-community/vam-registry | JSON | ★★ 社区脚本注册表(96KB index.json) | 参考 |

### 已完成整合

| 来源 | 目标 | 整合内容 |
|------|------|----------|
| vamtb | resources.py | VAR解析/元数据/依赖追踪/CRC32 |
| varbsorb | resources.py | 场景引用扫描/遗留路径迁移/完整性检查 |
| VPM | resources.py | VarDependencyGraph(双向依赖/孤儿/关键包/重复/缺失检测)/内容分类/深度扫描 |
| vam-keybindings | scenes.py | 46 Atom类型/31 Controller/12 Person Tabs/13 Main Tabs |
| vam-story-builder | scenes.py | DialogTree对话树/merge_scenes场景合并/SceneTemplates模板 |
| ai_virtual_mate_comm | chat.py | Ollama/LMStudio后端/DeepSeek R1 think filter |
| voxta_unoffical_docs | chat.py + hub.py | Voxta脚本API常量/VoxtaScriptGenerator |
| **via5/Cue** | **characters.py** | **BodyPartType/MoodSystem/PersonalitySystem/ExcitementSystem/GazeSystem/VoiceState/CharacterBehavior** |
| **via5/Cue** | **animations.py** | **Easing(12函数)/BVHParser(BVH导入→Timeline)/ProceduralAnimation(力/扭矩/Morph程序化动画)** |
| **via5/Synergy** | **animations.py** | **SynergyStepAnimation(步骤/修饰器随机动画系统)** |
| **acidbubbles/vam-director** | **animations.py** | **CameraDirector(相机角度序列编排, 7个预设角度)** |
| **dion-labs/voxta-twitch-relay** | **voxta/twitch_relay.py** | **TwitchRelay(消息队列/过滤器/速率限制/健康检查)** |
| **VamFreeMMD** | **animations.py** | **VMDBoneMap(56骨骼映射+20依赖链) + VMDParser(VMD二进制解析→Timeline)** |
| **FacialMotionCapture** | **characters.py** | **ARKitBlendShape(52面捕→VaM Morph映射, 8组)** |
| **morphology** | **characters.py** | **MorphRegion(28 shape+18 pose区域分类 + 坏morph检测)** |
| **Voxta.VamProxy** | **voxta/remote_proxy.py** | **VoxtaRemoteProxy(SignalR WebSocket代理+音频下载+会话追踪)** |
| **vam-timeline** | **animations.py** | **TimelineAPI(27个storable参数+队列系统+速度控制)** |
| **vam-keybindings** | **characters.py** | **VaMRegistry(46 atom types/31 controllers/13 tabs/对称+上下体分组)** |

## 八、第三批发现 (2026-03-06, 新搜索)

### 新发现高价值项目

| 星标 | 仓库 | 语言 | 许可证 | 整合价值 | 整合状态 |
|------|------|------|--------|----------|---------|
| ~10 | via5/Cue | C# | CC0 | ⭐⭐⭐ 170+文件AI行为系统(情绪/人格/兴奋度/凝视/语音/BVH/程序化动画) | ✅ → characters.py + animations.py |
| ~5 | via5/Synergy | C# | CC0 | ⭐⭐ 步骤/修饰器随机动画(力/Morph/持续时间同步) | ✅ → animations.py |
| ~1 | dion-labs/voxta-twitch-relay | Python | MIT | ⭐⭐ Twitch→Voxta对话桥接(TwitchIO/消息队列/直播检测) | ✅ → voxta/twitch_relay.py |
| ~5 | acidbubbles/vam-director | C# | MIT | ⭐ 相机角度序列编排(动画模式切换) | ✅ → animations.py |
| 7 | Playable2030/VaM_PerformancePlugin | C# | - | ⭐ 性能监控插件(FPS/内存/渲染时间) | 参考 |
| ~3 | morph1sm/vam-hud | C# | - | ⭐ 可配置HUD(状态叠加显示) | 参考 |
| ~5 | vam-community/vam-party | C#/.NET | MIT | ⭐ 社区包管理器(注册/搜索/安装) | 参考 |
| ~3 | mjanek20/vam-timeline-all | C# | - | ★ Timeline完整分支(PeerManager多实例同步) | 参考 |
| ~2 | everlasterVR/SoundFromAssetBundle | C# | - | ★ AssetBundle音频加载 | 参考 |

### via5/Cue 深度分析 (最高价值项目)

170+ C#源文件, 覆盖VaM自动化全栈:
- **AI行为**: AI事件系统(Grab/Kiss/Thrust等), 自主行为决策
- **动画**: BVH导入, 程序化动画(力/扭矩/Morph目标), Timeline/Synergy集成
- **角色**: 身体部位类型, 表情(情绪驱动+兴奋度+自动微动), 人格特质, 凝视系统
- **语音**: 状态机(Normal/Kiss/Orgasm/Choked/BJ), 兴奋度驱动
- **集成**: Embody/MacGruber/DiviningRod/ClockwiseBJ等插件互操作
- **UI**: VUI自定义界面框架(桌面+VR菜单)
- **系统**: VamAtom/VamBody/VamMorphs/VamParameter完整封装

---

## 九、第六批整合 (2026-03-07, +5个仓库, 共38个)

### 新克隆仓库

| 星标 | 仓库 | 语言 | 大小 | 整合价值 | 整合状态 |
|------|------|------|------|----------|---------|
| 35 | sFisherE/vam_plugin_release | C# | 4.5MB | ★★ VarBrowser插件(会话级VAR浏览) | 参考 |
| 21 | sFisherE/mmd2timeline | C# | 2.6MB | ★★★ MMD→Timeline完整转换(112 .cs, LibMmd库+面部/手指Morph+DAZ骨骼映射) | ✅ → animations.py |
| 18 | CraftyMoment/mmd_vam_import | Python | 66KB | ★★★ VMD→VaM场景JSON转换(Python原生, 四元数插值+IK检测) | ✅ → animations.py |
| 26 | ZengineerVAM/VAMLaunch | C# | 8.9MB | ★★ Buttplug/Launch触觉设备集成(运动源: 振荡/模式/区域) | ✅ → animations.py |
| 4 | FivelSystems/YAVAM | TypeScript | 4.4MB | ★ 多库内容大脑(跨VaM安装组织包) | 参考 |

### 已完成整合 (第六批)

| 来源 | 目标 | 整合内容 |
|------|------|----------|
| mmd2timeline/FaceMorph.cs | animations.py | **MMDFaceMorphMap** — 33个MMD日文面部Morph→VaM DAZ Morph映射(眉8/目11/口14), 带min/max权重缩放 |
| mmd2timeline/FingerMorph.cs | animations.py | **FingerMorphMap** — 25个手指控制参数 + 10个弯曲公式(左右手×5指, 含骨骼旋转角度) |
| mmd2timeline/DazBoneMapping.cs | animations.py | **DazBoneMap** — 23个DAZ Genesis→MMD骨骼映射 + 18个IK别名 + DAZ骨骼层级 + 手指层级 |
| mmd_vam_import/vmd.py | animations.py | **VMDSceneImporter** — VMD二进制解析→VaM场景JSON(41个JP→EN翻译, IK/FK自动检测, 四元数旋转, 手臂补偿) |
| VAMLaunch/MotionSources/ | animations.py | **LaunchMotionSource** — 3种触觉设备运动源(振荡/模式/区域), Buttplug.io协议 |

### 第六批GitHub搜索覆盖

| 搜索词 | 结果数 | 新发现 |
|--------|--------|--------|
| virt-a-mate OR virtamate | 50+ | sFisherE(35★), YAVAM(4★), jy03018013(中文翻译4★) |
| vam scene/character/animation/plugin (C#) | 30 | sFisherE/mmd2timeline(21★), VAMLaunch(26★), ChrisTopherTa54321(9★) |
| vam morph/pose/clothes/hair/asset | 20 | 多为非VaM项目, imb101/VAM-IK-CUA(3★) |
| vam blender/unity/texture/shader/import | 15 | CraftyMoment/mmd_vam_import(18★), my12doom/import_vab(4★) |
| vam mmd/bvh/motion capture/launch | 20 | 覆盖确认 |

### 累计整合统计 (v2.4.0)

| 批次 | 来源 | 目标 | 整合类型 |
|------|------|------|----------|
| 1 | vamtb/varbsorb/VPM | resources.py | VAR解析/依赖图/清理 |
| 1 | vam-keybindings/vam-story-builder | scenes.py | Atom类型/对话树/场景模板 |
| 1 | ai_virtual_mate_comm/voxta_docs | chat.py+hub.py | Ollama后端/Voxta脚本API |
| 3 | via5/Cue | characters.py+animations.py | 7类AI行为+5类动画 |
| 3 | via5/Synergy | animations.py | SynergyStepAnimation |
| 3 | acidbubbles/vam-director | animations.py | CameraDirector |
| 3 | dion-labs/voxta-twitch-relay | voxta/twitch_relay.py | TwitchRelay |
| 4 | VamFreeMMD | animations.py | VMDBoneMap+VMDParser |
| 4 | FacialMotionCapture | characters.py | ARKitBlendShape |
| 4 | morphology | characters.py | MorphRegion |
| 4 | Voxta.VamProxy | voxta/remote_proxy.py | VoxtaRemoteProxy |
| 5 | vam-timeline | animations.py | TimelineAPI |
| 5 | vam-keybindings | characters.py | VaMRegistry |
| **6** | **mmd2timeline** | **animations.py** | **MMDFaceMorphMap+FingerMorphMap+DazBoneMap** |
| **6** | **mmd_vam_import** | **animations.py** | **VMDSceneImporter** |
| **6** | **VAMLaunch** | **animations.py** | **LaunchMotionSource** |

---

*本文档由Agent自动维护。上次更新: 2026-03-07。本地克隆: 38个仓库。整合: 23条记录(6批)。五感审计: 5/5 PASS。*
