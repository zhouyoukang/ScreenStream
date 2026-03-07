# VaM Agent 全域控制手册

> Agent代替用户完成VaM内所有操作、配置、开发的完整参考。
> 生成时间: 2026-03-04 | 基于本地资产深度扫描 + Voxta插件逆向 + 训练知识

## 一、六大控制面

```
┌─────────────────────── IDE Agent (Windsurf) ───────────────────────┐
│                                                                      │
│  ①场景JSON      ②Voxta SignalR    ③C# Scripter    ④BepInEx       │
│  (文件操控)      (运行时通信)       (VaM内脚本)     (Unity注入)      │
│                                                                      │
│  ⑤文件系统       ⑥进程管理                                          │
│  (VAR/预设/资源)  (启停/健康/诊断)                                    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### ① 场景JSON操控 (Agent→文件→VaM加载)

**原理**: VaM场景是标准JSON文件，Agent可直接生成/修改/加载。

**能力矩阵**:

| 操作 | 方法 | Agent可做? | 示例 |
|------|------|-----------|------|
| 创建场景 | 写JSON到`Saves/scene/` | ✅ 完全 | 生成含Person+Camera+Light的场景 |
| 添加角色 | atoms数组添加Person对象 | ✅ 完全 | 设置geometry/clothing/hair |
| 配置插件 | storables中添加plugin配置 | ✅ 完全 | Voxta/Timeline/Scripter |
| 设置灯光 | InvisibleLight atom | ✅ 完全 | 三点布光/环境光 |
| 设置相机 | WindowCamera atom | ✅ 完全 | FOV/位置/景深 |
| 修改已有场景 | 读→改→写JSON | ✅ 完全 | 换角色/加插件/调参数 |
| 加载场景 | VaM菜单手动 / 命令行参数 | ⚠️ 需用户操作 | `VaM.exe -scene path` |

**场景JSON结构** (已验证):
```json
{
  "version": "1.22.0.3",
  "atoms": [
    {
      "id": "Person#1",
      "type": "Person",  // Person/InvisibleLight/WindowCamera/...
      "on": "true",
      "position": {"x":"0","y":"0","z":"0"},
      "rotation": {"x":"0","y":"0","z":"0"},
      "storables": [
        {"id": "geometry", "character": "Female"},
        {"id": "rescaleObject", "scale": "1.0"},
        {"id": "plugin#0_AcidBubbles.Voxta.83:/.../VoxtaClient.cslist",
         "enabled": "true",
         "host": "127.0.0.1:5384",
         "characterId": "575b8203-...",
         "enableLipSync": "true",
         "enableActions": "true"}
      ]
    }
  ]
}
```

**Atom类型全表**:
| 类型 | 用途 | 关键storables |
|------|------|-------------|
| Person | 角色 | geometry, plugin#N, rescaleObject, headControl/rHandControl... |
| InvisibleLight | 灯光 | Light(type/intensity/color/range) |
| WindowCamera | 相机 | CameraControl(FOV/depthOfField/focusDistance) |
| CustomUnityAsset | 道具 | AssetUrl |
| SubScene | 子场景 | SubSceneUrl |
| Empty | 空物体 | (标记/锚点) |
| AudioSource | 音频 | AudioSource(clip/volume) |
| UIText | 文本UI | Text(text/fontSize/color) |

### ② Voxta SignalR 通信 (Agent→Python→Voxta→VaM)

**原理**: Python chat_engine.py通过SignalR WebSocket控制Voxta，Voxta再通过插件控制VaM。

**能力矩阵**:

| 操作 | 方法 | 状态 |
|------|------|------|
| 连接Voxta | `VoxtaSignalR.connect()` | ✅ 已实现 |
| 加载角色列表 | `load_characters()` | ✅ 已实现 |
| 开始聊天 | `start_chat(char_id, scenario_id)` | ✅ 已实现 |
| 发送消息 | `send_message(text)` | ✅ 已实现 |
| 接收回复 | `receive_reply(timeout, action_wait)` | ✅ 已修复 |
| 动作推理 | `doCharacterActionInference: true` | ✅ 9/11 emotes |
| AppTrigger接收 | replyEnd后action_wait | ✅ 已修复 |
| 设置Flags | `set_flags('emotes')` | ✅ 已实现 |
| 更新上下文 | `update_context(ctx, actions)` | ✅ 已实现 |
| 停止聊天 | `stop_chat()` | ✅ 已实现 |
| TTS播放确认 | `acknowledge_playback(mid)` | ✅ 已实现 |

**VaM端接收AppTrigger后可执行**:
- `Emote(emoji, color)` → 播放表情动画
- `SelectView(view)` → 切换视角(portrait/talk/chat)
- `SetBackgroundFromScenario(bg)` → 切换背景
- Timeline动画播放 (通过Action Mapping)
- 自定义动作 (通过Scripter脚本)

### ③ C# Scripter 脚本 (Agent生成→VaM加载执行)

**原理**: Agent生成C#脚本文件，VaM通过Scripter插件编译执行。

**已有脚本** (16个):

| 脚本 | 功能 | 复用价值 |
|------|------|---------|
| `SimpleActionControl.cs` | 5种基础动作(挥手/点头/摇头/跳跃/舞蹈) | ★★★★★ |
| `DirectTimelineControl.cs` | Timeline动画创建(程序化关键帧) | ★★★★★ |
| `ScripterHelper.cs` | 文件加载+模板生成+剪贴板 | ★★★★ |
| `AddAnimationsToCurrentScene.cs` | 批量动画创建(22KB) | ★★★★ |
| `TimelineCodeController.cs` | Timeline完整控制(16KB) | ★★★★ |
| `AIAnimationFramework.cs` | AI动画框架(10KB) | ★★★ |
| `AIActionGenerator.cs` | AI动作生成器(14KB) | ★★★ |
| `GenerateVoxtaAnimations.cs` | Voxta专用动画生成 | ★★★ |
| `SimpleWaveAnimation.cs` | 简单挥手动画 | ★★ |
| `MotionCaptureIntegrator.cs` | 动捕集成(14KB) | ★★ |

**VaM C# API关键入口**:
```csharp
// 全局单例
SuperController.singleton.GetAtomByUid("Person#1")
SuperController.singleton.Load(scenePath)

// Atom操控
atom.GetStorableByID("rHandControl") as FreeControllerV3
atom.GetStorableIDs() → List<string>

// 控制器
ctrl.transform.position = new Vector3(x, y, z)
ctrl.transform.rotation = Quaternion.Euler(x, y, z)

// Timeline控制
timeline = atom.GetStorableByID("plugin#0_VamTimeline.AtomPlugin")
timeline.CallAction("Play.animation_name")
timeline.CallAction("AddAnimation.name")
timeline.SetFloatParamValue("scrubber", time)
timeline.CallAction("RecordFrame.controllerName")

// 参数系统
storable.GetFloatJSONParam("name").val = value
storable.GetBoolJSONParam("name").val = true
storable.CallAction("actionName")

// Morph(表情/体型)
dcs = atom.GetComponentInChildren<DAZCharacterSelector>()
morph = dcs.morphsControlUI.GetMorphByDisplayName("Brow Height")
morph.morphValue = 0.5f

// 文件IO
SuperController.singleton.savesDir
System.IO.File.ReadAllText/WriteAllText
```

### ④ BepInEx 插件 (Unity运行时注入)

**已安装插件**:

| 插件 | 功能 | Agent价值 |
|------|------|---------|
| **Console (IronPython)** | 🔴 运行时Python控制台 | ★★★★★ 潜在核心桥接 |
| FasterVaM | 性能优化 | ★ 自动 |
| MMDPlayer | MMD动画播放 | ★★ 可程序化调用 |
| DAZClothingMod | 服装修改 | ★ 自动 |
| SuperMode | 高级模式 | ★ 自动 |
| RenderToMovie | 视频录制 | ★★ 可程序化 |
| XUnity.AutoTranslator | 中文翻译 | ★★ 已配置 |

**⚠️ IronPython Console (VNGE) — 非VaM原生**

`BepInEx/plugins/Console/` 是 **VNGE (VN Game Engine)**，专为HoneySelect/AI Shoujo设计。
- 启动脚本引用`vngameengine`、`HSNeoOCIFolder`等HS专有API
- 53个Lib脚本全部面向HS/AI游戏引擎
- VaM的`SuperController` API与HS的`Studio` API完全不同

**理论可行但需大量改造**:
1. IronPython运行时本身可用(Unity通用)
2. 需要重写`Console.ini`的启动脚本，绑定VaM API
3. 需要开发VaM版的`vngameengine`等价模块
4. **更实际的方案**: 自建BepInEx HTTP Server插件，暴露VaM API

**当前最佳Agent→VaM运行时通道**:
- **方案A**: Voxta SignalR → Voxta插件 → VaM (已实现，最成熟)
- **方案B**: 生成C#脚本 → Scripter加载 → VaM执行 (已有模板)
- **方案C**: 自建BepInEx HTTP插件 (未来方向，需C#开发)

### ⑤ 文件系统操控

**目录结构**:
```
F:\vam1.22\VAM版本\vam1.22.1.0\
├── AddonPackages/          # VAR插件包 (1042个, 37GB)
├── Custom/
│   ├── Scripts/            # C#/JS脚本 (16个)
│   ├── Atom/               # 自定义Atom
│   ├── Clothing/           # 服装
│   ├── Hair/               # 发型
│   ├── Assets/             # 资源
│   ├── PluginData/         # 插件数据
│   ├── PluginPresets/      # 插件预设
│   └── SubScene/           # 子场景
├── Saves/
│   ├── scene/              # 场景文件
│   │   └── Generated/      # Agent生成的场景 (14个)
│   └── PluginData/         # 场景插件数据
├── BepInEx/plugins/        # Unity插件
└── Saves/scene/Generated/  # AI生成场景
```

**Agent可执行文件操作**:

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建场景 | 写JSON | `Saves/scene/Generated/*.json` |
| 创建C#脚本 | 写.cs文件 | `Custom/Scripts/*.cs` |
| 管理VAR包 | 文件操作 | `AddonPackages/*.var` |
| 外观预设 | 读写JSON | `Custom/Atom/Person/Appearance/` |
| 服装管理 | 读写JSON | `Custom/Clothing/` |
| 发型管理 | 读写JSON | `Custom/Hair/` |
| 插件预设 | 读写JSON | `Custom/PluginPresets/` |
| 配置文件 | 读写 | `prefs.json`, `config` |

### ⑥ 进程管理

**已实现工具**:

| 工具 | 功能 | 命令 |
|------|------|------|
| `vam_launcher.py` | 一键启动全套 | `python vam_launcher.py --full` |
| `vam_control.py` | 状态面板+诊断 | `python vam_control.py status` |
| `agent_hub.py` | 中枢v2 (18条CLI) | `python agent_hub.py status` |
| `health_check.py` | 五感健康检查 | `python health_check.py` |

**服务端口**:

| 服务 | 端口 | Agent管理 |
|------|------|---------|
| Voxta | :5384 | ✅ 启停/配置/DB直控 |
| EdgeTTS | :5050 | ✅ 启停 |
| TextGen | :7860 | ✅ 启停 |
| VaM | 进程 | ✅ 启动/检测 |

## 二、Agent操作流程图

### 完整E2E流程
```
Agent意图(如"创建一个含香草角色的场景")
  │
  ├─[1] 生成场景JSON → Custom/Scripts/ & Saves/scene/
  ├─[2] 启动服务链 → Voxta(:5384) + EdgeTTS(:5050)
  ├─[3] 启动VaM → 加载生成的场景
  ├─[4] SignalR连接 → start_chat(香草, Voxta_UI)
  ├─[5] set_flags('emotes') → 启用表情动作
  ├─[6] send_message → receive_reply(含action/appTrigger)
  ├─[7] AppTrigger → VaM执行动画/表情/视角切换
  └─[8] 持续对话循环 → update_context / flag管理
```

### Agent五感映射

| 感官 | 输入来源 | 工具 | 能力 |
|------|---------|------|------|
| **视** | 场景JSON / VaM日志 | read_file / grep | 理解场景结构、错误 |
| **听** | Voxta SignalR消息 | chat_engine.py | 实时监控AI对话状态 |
| **触** | 文件写入 / 进程启停 | write_file / run_command | 创建/修改场景和脚本 |
| **嗅** | 端口探测 / 健康检查 | health_check.py | 预判服务故障 |
| **味** | E2E测试结果 | _explore_actions.py | 评估系统整体质量 |

## 三、当前能力 vs 缺失能力

### ✅ 已具备

| # | 能力 | 实现 |
|---|------|------|
| 1 | 服务启停管理 | vam_launcher.py / vam_control.py |
| 2 | Voxta数据库直控 | agent_hub.py (角色CRUD/模块/记忆/预设) |
| 3 | 聊天引擎(双模式) | chat_engine.py (standalone + voxta) |
| 4 | 动作推理+AppTrigger | E2E验证 9/11 emotes |
| 5 | 场景JSON生成 | 14个Generated场景(基础) |
| 6 | C#脚本库 | 16个脚本(动作/动画/控制器) |
| 7 | SignalR协议完整逆向 | SIGNALR_PROTOCOL.md |
| 8 | 健康检查+诊断 | health_check.py / diagnose() |
| 9 | TavernCard V2导入 | agent_hub.py |
| 10 | LLM自动降级 | DashScope→DeepSeek→本地 |

### 🔴 缺失 (需实现)

| # | 能力 | 价值 | 难度 | 方案 |
|---|------|------|------|------|
| 1 | **场景JSON Builder** | ★★★★★ | 中 | Python类封装，参数化生成完整场景 |
| 2 | **VaM运行时桥接** | ★★★★★ | 高 | 探索BepInEx Console TCP接口 / 自建HTTP插件 |
| 3 | **外观预设管理** | ★★★★ | 低 | 解析Appearance JSON，Agent可选择/修改外观 |
| 4 | **VAR包智能索引** | ★★★ | 中 | 扫描1042个VAR，建立内容索引 |
| 5 | **VaM日志实时监控** | ★★★★ | 低 | tail output_log.txt + 错误解析 |
| 6 | **动画预设生成器** | ★★★ | 中 | 模板化C#脚本生成，覆盖常见动作 |
| 7 | **多角色场景编排** | ★★★★ | 中 | 多Person+多Voxta角色+对话编排 |
| 8 | **场景自动加载** | ★★★★★ | 高 | VaM命令行参数 / BepInEx热加载 |

## 四、优先实现路线

### Phase 1: 场景JSON Builder (2h)
```python
class VaMSceneBuilder:
    def __init__(self):
        self.atoms = []
    
    def add_person(self, id, position, voxta_char_id=None, ...)
    def add_camera(self, id, position, fov=60, ...)
    def add_light(self, id, position, type='Directional', ...)
    def add_plugin(self, atom_id, plugin_var, config={})
    def save(self, path)
    def load(self, path) → modify → save
```

### Phase 2: VaM运行时桥接探索 (4h)
1. 检查BepInEx Console插件配置(Console.ini)
2. 测试IronPython能否访问SuperController
3. 如有TCP端口，建立Agent→VaM实时控制
4. 备选: 自建BepInEx HTTP Server插件

### Phase 3: 外观+VAR管理 (2h)
1. 扫描所有Appearance预设
2. 建立VAR包内容索引
3. Agent可按描述选择外观/服装/发型

### Phase 4: 全流程自动化 (1天)
1. 从自然语言→场景生成→服务启动→VaM加载→对话→动作
2. 用户只说"创建一个猫娘和我聊天的场景"，Agent完成一切

## 五、关键ID和路径速查

### 角色
| 名称 | ID | 用途 |
|------|-----|------|
| 香草(工作) | `67e139a4-e30e-4603-a083-6e89719a9bb2` | ✅ 主力测试角色 |
| 香草(备用) | `575b8203-3d98-614a-9ef6-b1dcd4949cff` | 无限制版 |
| 小雅 | `d04c5d25-2788-4852-968b-8bb567d571c2` | ⚠️ 服务端无回复 |
| Catherine | `575b8203-3d98-614a-9ef6-b1dcd4949cfe` | ⚠️ 服务端无回复 |
| George | `6227dc38-f656-413f-bba8-773380bad9d9` | ⚠️ 服务端无回复 |

### 场景
| 名称 | ID |
|------|-----|
| Voxta UI | `53958F45-47BE-40D1-D2EB-DD5B476769FA` |

### 路径
| 资源 | 路径 |
|------|------|
| VaM主程序 | `F:\vam1.22\VAM版本\vam1.22.1.0\VaM.exe` |
| Voxta | `F:\vam1.22\Voxta\Active\` |
| Voxta DB | `F:\vam1.22\Voxta\Active\Data\Voxta.sqlite.db` |
| 场景目录 | `F:\vam1.22\VAM版本\vam1.22.1.0\Saves\scene\Generated\` |
| C#脚本 | `F:\vam1.22\VAM版本\vam1.22.1.0\Custom\Scripts\` |
| 插件包 | `F:\vam1.22\VAM版本\vam1.22.1.0\AddonPackages\` |
| BepInEx | `F:\vam1.22\VAM版本\vam1.22.1.0\BepInEx\plugins\` |
| Agent工具 | `d:\道\道生一\一生二\VAM-agent\tools\` |
| Console配置 | `BepInEx\plugins\Console\Console.ini` |

## 六、Voxta插件JSONStorable接口 (可从VaM外操控)

从Voxta.cs逆向提取的完整接口：

**可读写参数**:
| 参数名 | 类型 | 用途 |
|--------|------|------|
| Active | Bool | 激活/停用Voxta连接 |
| Character ID | StringChooser | 选择角色 |
| Scenario ID | StringChooser | 选择场景 |
| Chat ID | StringChooser | 选择聊天 |
| State | StringChooser | 状态(off/idle/listening/thinking/speaking) |
| LastUserMessage | String | 最后用户消息 |
| LastCharacterMessage | String | 最后角色消息 |
| SetFlags | String | 设置标志 |
| Flags | String | 当前标志 |
| Context | String | 上下文 |
| ActionsList | String | 动作列表 |
| TriggerMessage | String | 触发消息发送 |
| CurrentAction | String | 当前执行的动作 |
| AutoSendRecognizedSpeech | Bool | 自动发送识别的语音 |
| CharacterCanSpeak | Bool | 角色能否说话 |
| Enable Logs | Bool | 启用日志 |

**JSONStorableAction(可调用)**:
| 动作 | 用途 |
|------|------|
| DeleteCurrentChat | 删除当前聊天 |
| StartNewChat | 开始新聊天 |
| RevertLastSentMessage | 撤回最后消息 |
| ClearContext | 清除上下文 |
| EnableLipSync | 启用唇形同步 |

**关键洞察**: 这些JSONStorable参数可以从VaM内的其他插件(如Scripter)直接读写：
```csharp
var voxta = atom.GetStorableByID("plugin#0_AcidBubbles.Voxta.83:...");
voxta.SetStringParamValue("TriggerMessage", "你好！");
var reply = voxta.GetStringParamValue("LastCharacterMessage");
var action = voxta.GetStringParamValue("CurrentAction");
```
这意味着Agent可以通过生成C#脚本来直接操控VaM内的Voxta插件。
