# VaM + Voxta 五感深度逆向报告

> 顶级工程师五感逆向 · 控制面(VAM-agent) ↔ 数据面(F:\vam1.22) 全域解析
> 生成时间: 2026-06

---

## 一、系统全景 (鸟瞰)

```
┌─────────────────────────────────────────────────────────────────┐
│                    VAM-agent 统一控制面 (~5MB)                    │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐                 │
│  │  vam/    │  │  voxta/  │  │ browser_bridge│                 │
│  │ 11模块   │  │ 11模块   │  │  3模块        │                 │
│  │ VaM六感  │  │ Voxta五感│  │ 桌面浏览器化  │                 │
│  └────┬─────┘  └────┬─────┘  └──────┬────────┘                 │
│       │             │               │                           │
│  AgentBridge   SignalR WS      FastAPI+WS                      │
│  HTTP :8285    WS :5384        HTTP :9870                      │
└───────┼─────────────┼───────────────┼───────────────────────────┘
        │             │               │
        ▼             ▼               ▼
┌───────────────────────────────────────────────────────────────┐
│              F:\vam1.22 数据面 (~276GB)                        │
│                                                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────┐      │
│  │ VAM版本/        │  │ Voxta/Active/   │  │ 资源文件/ │      │
│  │ vam1.22.1.0/    │  │ 12.7GB          │  │ 99.8GB   │      │
│  │ 137GB           │  │ Voxta.Server.exe│  │ VAR包    │      │
│  │ VaM.exe(Unity)  │  │ SQLite DB       │  │ 人物/场景│      │
│  │ BepInEx/        │  │ 38个Module DLL  │  │ 服装/发型│      │
│  │ Custom/Scripts/ │  │ SignalR Hub     │  │          │      │
│  │ 1043个VAR包     │  │ Python 3.12     │  │          │      │
│  │ (37.3GB)        │  ├─────────────────┤  │          │      │
│  │                 │  │ EdgeTTS/ :5050  │  │          │      │
│  │                 │  │ TextGen/ :7860  │  │          │      │
│  └─────────────────┘  └─────────────────┘  └──────────┘      │
└───────────────────────────────────────────────────────────────┘
```

### 核心数据

| 维度 | 值 |
|------|-----|
| **VaM版本** | 1.22.1.0 (Unity引擎, Desktop Mode) |
| **Voxta** | Server+DesktopApp (165MB+125MB, .NET) |
| **控制面代码** | Python ~5MB, 25+源文件 |
| **数据面总量** | ~276GB (F盘) |
| **VAR资源包** | 1043个, 37.3GB |
| **BepInEx插件** | 13个(含AgentBridge.dll 45KB) |
| **Voxta模块DLL** | 38个 (LLM/TTS/STT/Memory/Vision/Processing) |
| **服务端口** | 5个活跃 (:5050 :5384 :7860 :8285 :9870) |

---

## 二、视 · Vision — 架构逆向

### 2.1 VaM 引擎核心架构

VaM (Virt-A-Mate) 是基于 **Unity 2018.x** 的3D角色模拟器。

```
VaM.exe (Unity Runtime)
├── Assembly-CSharp.dll (5.6MB) ← VaM核心逻辑, 全在此DLL
│   ├── SuperController (单例) ← 全局控制器, 所有操作入口
│   │   ├── GetAtoms() → List<Atom>
│   │   ├── GetAtomByUid(id) → Atom
│   │   ├── SelectController(ctrl)
│   │   ├── Load(path) / Save(path) / NewScene()
│   │   ├── freezeAnimation (bool)
│   │   ├── motionAnimationMaster.StartPlayback()/StopPlayback()
│   │   ├── Undo() / Redo() (反射调用)
│   │   └── savesDir / version
│   │
│   ├── Atom (场景中的每个实体)
│   │   ├── uid / type / on / mainController
│   │   ├── freeControllers[] → FreeControllerV3
│   │   │   ├── transform.position / rotation
│   │   │   └── currentPositionState / currentRotationState
│   │   ├── GetStorableIDs() → List<string>
│   │   ├── GetStorableByID(id) → JSONStorable
│   │   └── GetComponentInChildren<DAZCharacterSelector>()
│   │
│   ├── JSONStorable (参数化组件基类)
│   │   ├── GetFloatJSONParam(name) → JSONStorableFloat (.val)
│   │   ├── GetBoolJSONParam(name) → JSONStorableBool (.val)
│   │   ├── GetStringJSONParam(name) → JSONStorableString (.val)
│   │   ├── GetStringChooserJSONParam(name) → (.val, .choices)
│   │   ├── GetFloatParamNames() / GetBoolParamNames()
│   │   ├── GetStringChooserParamNames() / GetActionNames()
│   │   ├── CallAction(name) ← 触发动作
│   │   └── SetFloatParamValue(name, val)
│   │
│   ├── DAZCharacterSelector (Person Atom专属)
│   │   └── morphsControlUI
│   │       ├── GetMorphDisplayNames() → List<string>
│   │       └── GetMorphByDisplayName(name) → DAZMorph
│   │           ├── morphValue / startValue / min / max
│   │           └── (直接赋值修改表情/体型)
│   │
│   └── FreeControllerV3 (骨骼控制器)
│       ├── transform.position (Vector3)
│       ├── transform.rotation (Quaternion)
│       └── name (headControl/rHandControl/lHandControl/...)
│
├── VaM_Data/Managed/ ← 70+ Unity模块DLL
├── BepInEx/ ← 模组加载框架 (doorstop注入)
│   ├── core/ (BepInEx运行时)
│   ├── plugins/ (13个插件)
│   │   ├── AgentBridge.dll (45KB) ← 我们的HTTP桥
│   │   ├── FasterVaM.dll (82KB) ← 性能优化
│   │   ├── MMDPlayer.dll (98KB) ← MMD动画
│   │   ├── SuperMode.dll (122KB) ← 超级模式
│   │   ├── XUnity.AutoTranslator/ ← 中文化
│   │   └── Console/ (VNGE IronPython)
│   └── config/BepInEx.cfg
│
└── doorstop_config.ini ← BepInEx注入配置 (enabled=true)
```

### 2.2 Atom 类型全表 (可创建)

| 类型 | 用途 |
|------|------|
| **Person** | 3D人物(含Morph/服装/发型/物理) |
| **Empty** | 空对象(挂脚本/插件载体) |
| **WindowCamera** | 摄像机(FOV/DOF/焦距) |
| **InvisibleLight** | 光源(平行/点/聚光) |
| **AudioSource** | 音频源 |
| **CustomUnityAsset** | 自定义Unity资源 |
| **SimpleSign/UIText/UIButton** | UI元素 |
| **UISlider/UIToggle/UIPopup** | UI控件 |
| **SubScene** | 子场景 |
| **Cube/Sphere** | 基础几何体 |
| **AnimationPattern** | 动画模式 |
| **CollisionTrigger** | 碰撞触发器 |
| **CoreControl** | 核心控制 |
| **NavigationPoint** | 导航点 |

### 2.3 场景JSON结构

```json
{
  "version": "1.22.0.3",
  "atoms": [
    {
      "id": "Person#1",
      "type": "Person",
      "on": "true",
      "position": {"x": "0", "y": "0", "z": "0"},
      "rotation": {"x": "0", "y": "0", "z": "0"},
      "storables": [
        {"id": "geometry", "character": "Female"},
        {"id": "rescaleObject", "scale": "1.0"},
        {"id": "plugin#0_AcidBubbles.Voxta.83:/.../VoxtaClient.cslist",
         "enabled": "true", "pluginLabel": "Voxta Client",
         "host": "127.0.0.1:5384", "characterId": "UUID...",
         "enableLipSync": "true", "enableActions": "true"}
      ]
    }
  ]
}
```

### 2.4 VaM 目录结构深度映射

```
F:\vam1.22\VAM版本\vam1.22.1.0\
├── VaM.exe (634KB, Unity启动器)
├── UnityPlayer.dll (21.7MB, Unity运行时)
├── VaM_Data/
│   └── Managed/ (70+ DLL, Unity模块)
│       └── Assembly-CSharp.dll (5.6MB) ← VaM全部逻辑
├── Custom/
│   ├── Scripts/ (C#/JS脚本, 30+文件)
│   │   ├── Agent/ (AI部署的脚本)
│   │   ├── MeshedVR/ (官方脚本)
│   │   ├── Chokaphi/ (社区脚本)
│   │   └── *.cs/*.js (根级脚本)
│   ├── Atom/Person/Appearance/ (外观预设 .json/.vap)
│   ├── Clothing/ (服装)
│   ├── Hair/ (发型)
│   ├── Assets/ (自定义资源)
│   ├── SubScene/ (子场景)
│   ├── PluginPresets/ (插件预设)
│   ├── Images/ (图片)
│   └── Sounds/ (音频)
├── Saves/
│   ├── scene/ (场景JSON, 25+文件)
│   │   └── Generated/ (Agent生成的场景)
│   └── PluginData/ (7个插件数据目录)
├── AddonPackages/ (1043个VAR包, 37.3GB)
├── BepInEx/ (插件框架)
├── Cache/ (缓存)
├── config (加密的许可证)
└── prefs.json (偏好设置, 100+参数)
```

### 2.5 Voxta 架构逆向

```
Voxta.Server.exe (165MB, .NET 单文件发布)
├── SignalR Hub (ws://localhost:5384/hub)
│   ├── 14种 Client→Server 消息
│   │   ├── authenticate (握手)
│   │   ├── loadCharactersList / loadScenariosList / loadChatsList
│   │   ├── startChat / sendMessage / speechRecognitionPartialResult
│   │   └── ...
│   └── 29种 Server→Client 消息
│       ├── welcome / charactersListLoaded / chatStarted
│       ├── replyGenerating / replyChunkGenerated / replySpeechReady
│       └── ...
│
├── SQLite Database (Voxta.sqlite.db, 684KB)
│   ├── Characters (角色表: Name/Personality/FirstMessage/TTS/Scripts)
│   ├── Modules (模块表: ServiceName/Label/Enabled/Configuration)
│   ├── Chats (对话会话表)
│   ├── ChatMessages (消息表: Role/Text/ChatId)
│   ├── Presets (LLM预设: Temperature/MaxTokens)
│   ├── MemoryBooks (记忆书: Items JSON数组)
│   ├── Scenarios (场景表)
│   ├── Users (用户表)
│   └── ProfileSettings (配置表)
│
├── Modules/ (38个模块DLL, 热插拔)
│   ├── LLM: OpenAICompatible, OpenAI, KoboldAI, Oobabooga,
│   │        LlamaCpp, ExLlamaV2, OpenRouter, NovelAI, TextGenInference
│   ├── TTS: F5TTS, Silero, Coqui, ElevenLabs, TextToSpeechHttpApi,
│   │        WindowsSpeech, Azure.SpeechService, Kokoro(disabled)
│   ├── STT: Vosk, WhisperLive, Deepgram, Azure.SpeechService, WindowsSpeech
│   ├── Memory: BuiltIn.SimpleMemory, ChromaDb
│   ├── Vision: BuiltIn.Vision, Florence2, FlashCap
│   ├── Processing: ReplyPrefixing, TextReplacements, ChainOfThought, Continuations
│   └── Audio: NAudio, BuiltIn.AudioRms
│
├── Data/
│   ├── Models/ (语音识别模型等)
│   ├── Python/ (内嵌Python 3.12.8)
│   ├── Logs/ (Serilog日志, 7天滚动)
│   ├── Audio/ (音频缓存)
│   └── .agent_backup/ (Agent自动备份)
│
├── Resources/ (Voxta资源)
└── appsettings.json (服务配置)
    ├── Host.Urls: ["http://localhost:5384"]
    ├── Settings.WarmupServicesOnStart: false
    ├── Python (Windows/Linux双平台配置)
    └── Serilog (日志配置)
```

---

## 三、听 · Audio — 通信协议逆向

### 3.1 AgentBridge HTTP API (完整端点表)

**端口**: 8285 | **认证**: X-Agent-Key (可选) | **CORS**: 全开

| 方法 | 路径 | 功能 | 线程 |
|------|------|------|------|
| GET | `/api/health` | 健康检查 | 即时(无主线程) |
| GET | `/api/status` | VaM运行时状态 | 主线程 |
| GET | `/api/atom-types` | 可创建Atom类型列表 | 主线程 |
| GET | `/api/atoms` | 列出所有Atom | 主线程 |
| GET | `/api/atom/{id}` | Atom详情 | 主线程 |
| POST | `/api/atom` | 创建Atom | 主线程(协程) |
| DELETE | `/api/atom/{id}` | 删除Atom | 主线程 |
| GET | `/api/atom/{id}/storables` | 列出Storable | 主线程 |
| GET | `/api/atom/{id}/storable/{sid}/params` | 参数详情 | 主线程 |
| POST | `/api/atom/{id}/storable/{sid}/float` | 设Float | 主线程 |
| POST | `/api/atom/{id}/storable/{sid}/bool` | 设Bool | 主线程 |
| POST | `/api/atom/{id}/storable/{sid}/string` | 设String | 主线程 |
| GET | `/api/atom/{id}/storable/{sid}/choosers` | StringChooser列表 | 主线程 |
| POST | `/api/atom/{id}/storable/{sid}/chooser` | 设Chooser | 主线程 |
| GET | `/api/atom/{id}/storable/{sid}/actions` | Action列表 | 主线程 |
| POST | `/api/atom/{id}/storable/{sid}/action` | 调用Action | 主线程 |
| GET | `/api/atom/{id}/controllers` | 控制器列表 | 主线程 |
| POST | `/api/atom/{id}/controller/{name}` | 设位置/旋转 | 主线程 |
| GET | `/api/atom/{id}/morphs?filter=&modified=` | Morph列表(可过滤) | 主线程 |
| POST | `/api/atom/{id}/morphs` | 设Morph值 | 主线程 |
| GET | `/api/atom/{id}/plugins` | 插件列表 | 主线程 |
| POST | `/api/scene/load` | 加载场景 | 主线程 |
| POST | `/api/scene/save` | 保存场景 | 主线程 |
| POST | `/api/scene/clear` | 清空场景 | 主线程 |
| GET | `/api/scene/info` | 场景信息 | 主线程 |
| GET | `/api/scenes` | 场景文件浏览 | 主线程 |
| POST | `/api/freeze` | 冻结/解冻动画 | 主线程 |
| POST | `/api/navigate` | 导航到Atom | 主线程 |
| POST | `/api/screenshot` | 截图 | 主线程(协程) |
| GET | `/api/log` | 运行时日志(环形缓冲200条) | 即时 |
| GET | `/api/prefs` | 读取prefs.json | 主线程 |
| POST | `/api/prefs` | 更新prefs.json | 主线程 |
| POST | `/api/voxta/{id}/send` | Voxta发送消息 | 主线程 |
| GET | `/api/voxta/{id}/state` | Voxta状态 | 主线程 |
| POST | `/api/voxta/{id}/action` | Voxta动作 | 主线程 |
| POST | `/api/timeline/{id}` | Timeline控制 | 主线程 |
| POST | `/api/global/action` | 全局动作(play/stop/undo/redo) | 主线程 |
| POST | `/api/command` | 批量命令执行 | 主线程 |

**关键架构决策**:
- HTTP监听在**后台线程**(HttpListener)
- 所有VaM API调用通过**主线程队列**(Queue<Action>)编组到Unity Update()
- 协程用于异步操作(创建Atom/截图)
- 日志环形缓冲区(200条)无需主线程编组

### 3.2 SignalR 协议 (Voxta ↔ VaM)

```
连接: ws://localhost:5384/hub
握手: {"protocol":"json","version":1}\x1e → {}\x1e
认证: {$type:"authenticate", client:"VAM-agent", scope:["role:app"],
       capabilities:{audioOutput:"Url"}, apiVersion:"2025-08"}
响应: {$type:"welcome", ...}
```

| 方向 | 消息类型 | 用途 |
|------|---------|------|
| C→S | `authenticate` | 连接认证 |
| C→S | `loadCharactersList` | 请求角色列表 |
| C→S | `loadScenariosList` | 请求场景列表 |
| C→S | `loadChatsList` | 请求对话列表 |
| C→S | `startChat` | 启动聊天(characterIds+contextKey) |
| C→S | `sendMessage` | 发送用户消息 |
| S→C | `welcome` | 认证成功 |
| S→C | `charactersListLoaded` | 角色列表 |
| S→C | `chatStarted` | 聊天已启动 |
| S→C | `replyGenerating` | LLM开始生成 |
| S→C | `replyChunkGenerated` | 流式回复片段 |
| S→C | `replySpeechReady` | TTS音频URL就绪 |

### 3.3 VaM ↔ Voxta 插件桥接 (C# in VaM)

VaM中的Voxta Client插件(`AcidBubbles.Voxta.83`)暴露以下参数:

| 参数类型 | 参数名 | 用途 |
|---------|--------|------|
| Bool | `Connected` | 连接状态 |
| Bool | `Active` | 激活状态 |
| Bool | `Ready` | 就绪状态 |
| Bool | `Error` | 错误状态 |
| String | `Status` | 状态文本 |
| StringChooser | `State` | 状态机(off/idle/listening/...) |
| String | `TriggerMessage` | 发送消息触发器(写入即发送) |
| String | `LastUserMessage` | 最后用户消息 |
| String | `LastCharacterMessage` | 最后角色回复 |
| String | `CurrentAction` | 当前动作标签 |
| String | `User Name` / `Character Name 1` | 用户/角色名 |
| String | `Flags` | 状态标志 |
| Action | `startNewChat` / `deleteCurrentChat` / `revertLastSentMessage` | 操作 |

### 3.4 Browser Bridge 协议 (桌面应用浏览器化)

```
server.py (:9870 FastAPI)
├── /ws (WebSocket, 双向)
│   ├── Server→Client: JPEG帧流(dxcam捕获→OpenCV编码)
│   └── Client→Server: 鼠标/键盘事件JSON
│       ├── {type:"mousemove", x, y}
│       ├── {type:"mousedown/up", button, x, y}
│       ├── {type:"keydown/up", key, code, modifiers}
│       └── {type:"wheel", deltaY, x, y}
├── /api/screenshot (截图)
├── /api/ocr (RapidOCR文字识别)
└── / (static/index.html Canvas客户端)
```

---

## 四、触 · Touch — 控制能力全表

### 4.1 VaMAgent 六感方法表 (25+方法)

| 感官 | 方法 | 功能 |
|------|------|------|
| **视** | `see_critical_paths()` | 文件完整性检查 |
| **视** | `see_scenes()` / `see_scene_detail()` | 场景列表/详情 |
| **视** | `see_scripts()` / `see_var_packages()` | 脚本/VAR包 |
| **视** | `see_plugins()` / `see_log()` | 插件/日志 |
| **听** | `hear_services()` / `hear_port()` | 服务/端口状态 |
| **触** | `touch_start_service()` / `touch_stop()` | 启停VaM |
| **触** | `touch_create_scene()` | 创建场景 |
| **触** | `touch_deploy_script()` | 部署C#脚本 |
| **嗅** | `smell_errors()` / `smell_error_summary()` | 错误检测 |
| **嗅** | `smell_disk()` / `smell_bepinex()` | 磁盘/配置预警 |
| **味** | `taste_health()` | 健康评分(0-100) |
| **味** | `taste_full_scan()` | 完整资源扫描 |
| **手** | `hand_scan()` / `hand_find()` | OCR扫描/文字定位 |
| **手** | `hand_click_text()` / `hand_click_at()` | 后台点击 |
| **手** | `hand_key()` / `hand_hotkey()` | 按键/快捷键 |
| **手** | `hand_type()` / `hand_paste()` | 输入/粘贴 |
| **手** | `hand_drag()` / `hand_scroll()` | 拖拽/滚轮 |
| **手** | `hand_screenshot()` | 截图 |
| **手** | `hand_navigate()` | 菜单导航 |
| **运行时** | `runtime_status()` / `runtime_atoms()` | Bridge状态 |
| **运行时** | `runtime_set_float/bool/string/chooser()` | 设参数 |
| **运行时** | `runtime_call_action()` | 调用动作 |
| **运行时** | `runtime_set_morph()` / `runtime_list_morphs()` | Morph控制 |
| **运行时** | `runtime_set_controller()` | 骨骼控制 |
| **运行时** | `runtime_load_scene()` / `runtime_save_scene()` | 场景加载/保存 |
| **运行时** | `runtime_voxta_send/state/new_chat()` | Voxta桥接 |
| **运行时** | `runtime_timeline_play/stop()` | Timeline动画 |
| **运行时** | `runtime_batch()` | 批量命令 |
| **运行时** | `runtime_global_action()` | 全局动作 |

### 4.2 VoxtaAgent 五感方法表 (40+方法)

| 感官 | 核心方法 | 功能 |
|------|---------|------|
| **视** | `see_dashboard()` | 综合仪表板 |
| **视** | `see_characters()` / `see_character_detail()` | 角色管理 |
| **视** | `see_modules()` / `see_scenarios()` / `see_presets()` | 模块/场景/预设 |
| **视** | `see_memory_books()` / `see_chats()` / `see_messages()` | 记忆/对话/消息 |
| **听** | `hear_services()` / `hear_signalr()` | 服务/SignalR状态 |
| **触** | `touch_start/stop_*()` | 启停Voxta/EdgeTTS/TextGen |
| **触** | `touch_backup()` | 数据库备份 |
| **触** | `touch_module_enable/disable()` | 模块开关 |
| **触** | `touch_chat()` / `touch_chat_voxta()` | standalone/voxta对话 |
| **触** | `touch_create/edit/delete_character()` | 角色CRUD |
| **触** | `touch_import_tavern_card()` | TavernCard导入 |
| **触** | `touch_auto_fix()` | 自动修复 |
| **嗅** | `smell_diagnose()` | 全链路诊断 |
| **嗅** | `smell_security()` | 安全扫描 |
| **味** | `taste_health()` | 健康评分 |

### 4.3 SceneBuilder (场景参数化构建)

```python
# 快速创建Voxta场景
scene = SceneBuilder.quick_voxta("香草", with_lighting=True)
# → 自动添加Person+Voxta插件+Camera+三点光

# 手动构建
scene = SceneBuilder()
scene.add_person(voxta_char_id="UUID", enable_lip_sync=True)
scene.add_camera(position=(0, 1.5, 2.0), fov=60)
scene.add_three_point_lighting()
scene.add_timeline("Person#1")
scene.add_scripter("Person#1", "MyScript.cs")
scene.save("MyScene")
```

### 4.4 ChatEngine (独立聊天引擎)

```
standalone模式 (脱离Voxta运行):
  CharacterLoader → DB加载角色
  PromptBuilder → system prompt构建(人格/记忆/上下文)
  LLMClient → DashScope qwen-plus / DeepSeek / 本地 (自动降级)
  TTSClient → EdgeTTS (Flask :5050)
  ActionInference → 从回复提取动作标签
  ConversationHistory → DB读写ChatMessages

voxta模式 (SignalR代理):
  VoxtaSignalR.connect() → start_chat() → send_message()
  → 监听 replyChunkGenerated / replySpeechReady
```

---

## 五、嗅 · Scent — 风险与安全分析

### 5.1 安全发现

| 风险 | 级别 | 详情 |
|------|------|------|
| **DashScope API Key** | 🟢低 | DPAPI加密存储(Windows本机绑定) |
| **VaM许可证** | 🟢低 | `config`文件Base64编码, 非明文 |
| **HTTP无认证** | 🟡中 | AgentBridge :8285 默认无auth key |
| **CORS全开** | 🟡中 | Access-Control-Allow-Origin: * |
| **DB明文** | 🟡中 | SQLite无加密, 角色数据/对话可直读 |
| **进程管理** | 🟢低 | taskkill /F 可停止任何进程 |
| **脚本部署** | 🟡中 | deploy_script()可写任意C#到VaM |

### 5.2 架构风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| **主线程阻塞** | VaM卡顿 | Bridge用队列编组, 每帧处理 |
| **VAR包膨胀** | 磁盘满 | disk_usage()监控, 85%预警 |
| **Voxta DB损坏** | 数据丢失 | 操作前自动backup到.agent_backup |
| **BepInEx版本冲突** | 插件不加载 | doorstop_config.ini检查 |
| **Unity窗口无UIA** | 无法自动化 | OCR+PostMessage后台方案(gui.py) |

### 5.3 依赖链

```
VaM运行时控制:
  Python → HTTP → AgentBridge.dll → Unity C# API → VaM Runtime
  (任一环节断裂 → 运行时控制失效, 但离线控制仍可用)

Voxta对话链:
  用户语音 → Vosk STT → LLM(DashScope/本地) → TTS(EdgeTTS/F5TTS)
  → VaM Voxta Plugin → 口型同步 + 动作执行
  (LLM断裂 → 对话失败; TTS断裂 → 无语音但文字可用)

GUI自动化:
  PrintWindow截图 → RapidOCR → 文字坐标 → PostMessage点击
  (OCR精度依赖分辨率和UI文字大小)
```

---

## 六、味 · Taste — 质量评估

### 6.1 代码质量评分

| 维度 | 评分 | 说明 |
|------|------|------|
| **架构清晰度** | ⭐⭐⭐⭐⭐ | 控制面/数据面分离, 双Agent隔离, 六感/五感统一接口 |
| **API完整度** | ⭐⭐⭐⭐⭐ | AgentBridge v2.0 覆盖VaM全部运行时能力 |
| **安全性** | ⭐⭐⭐⭐ | DPAPI加密+DB备份, 但HTTP无默认auth |
| **容错性** | ⭐⭐⭐⭐ | 降级路径完整, 异常处理到位 |
| **文档** | ⭐⭐⭐⭐⭐ | ARCHITECTURE.md+AGENTS.md+模块docs全覆盖 |
| **可测试性** | ⭐⭐⭐⭐ | CLI入口40+命令, tests/目录完备 |
| **代码复用** | ⭐⭐⭐⭐ | 遗留工具已整合, .disabled归档 |

### 6.2 VaM插件生态分析

| 插件 | 用途 | 与Agent的交互 |
|------|------|-------------|
| **AgentBridge** | HTTP运行时控制 | 核心桥梁, Python直控 |
| **Voxta Client** | AI对话桥接 | SignalR→VaM, 口型/动作 |
| **Scripter** | C#脚本运行 | deploy_script()部署 |
| **VamTimeline** | 关键帧动画 | timeline_play/stop() |
| **FasterVaM** | 性能优化 | 无直接交互 |
| **MMDPlayer** | MMD舞蹈 | 可通过storable控制 |
| **SuperMode** | 功能增强 | 可通过storable控制 |
| **XUnity.AutoTranslator** | 中文化 | 无直接交互 |
| **BrowserAssist** | 内嵌浏览器 | 可通过GUI操作 |

### 6.3 数据规模

| 资源类型 | 数量 | 大小 |
|---------|------|------|
| VAR资源包 | 1,043个 | 37.3GB |
| 场景文件 | 25+ | - |
| C#脚本 | 30+ | - |
| BepInEx插件 | 13个 | - |
| Voxta角色 | 7个 | - |
| Voxta模块DLL | 38个 | - |
| Voxta对话历史 | DB中 | 684KB |
| 资源文件(人物/场景) | 目录级 | 99.8GB |
| 总磁盘占用 | - | ~276GB |

---

## 七、控制通道矩阵

```
┌──────────────┬────────────────────┬──────────────────────┬─────────────────┐
│  控制通道     │  技术手段          │  能力范围            │  非侵入性       │
├──────────────┼────────────────────┼──────────────────────┼─────────────────┤
│ ① Bridge    │ HTTP→BepInEx→C#   │ VaM运行时全控制      │ ✅ 完全后台    │
│   :8285     │ 主线程队列编组     │ Atom/Morph/Scene/... │ 不抢焦点       │
├──────────────┼────────────────────┼──────────────────────┼─────────────────┤
│ ② SignalR   │ WebSocket→Voxta   │ AI对话全流程         │ ✅ 完全后台    │
│   :5384     │ JSON协议          │ 角色/聊天/TTS/STT   │                │
├──────────────┼────────────────────┼──────────────────────┼─────────────────┤
│ ③ DB直控    │ SQLite读写        │ Voxta配置/数据全控制 │ ✅ 文件级      │
│             │ Python sqlite3    │ 绕过Voxta Web UI    │ 需重启生效     │
├──────────────┼────────────────────┼──────────────────────┼─────────────────┤
│ ④ GUI自动化  │ PrintWindow+OCR   │ VaM界面操作          │ ✅ 后台模式    │
│             │ +PostMessage      │ 菜单/按钮/输入      │ 不移动鼠标     │
├──────────────┼────────────────────┼──────────────────────┼─────────────────┤
│ ⑤ 文件系统   │ Path读写          │ 场景JSON/脚本/配置  │ ✅ 完全后台    │
│             │ Python pathlib    │ 离线可用             │                │
├──────────────┼────────────────────┼──────────────────────┼─────────────────┤
│ ⑥ 进程管理   │ tasklist/taskkill  │ 启停VaM/Voxta/TTS  │ ⚠️ 强制停止    │
│             │ subprocess.Popen  │                     │ 可能丢数据     │
├──────────────┼────────────────────┼──────────────────────┼─────────────────┤
│ ⑦ 浏览器化   │ dxcam+WS+Canvas   │ 远程查看+操作VaM    │ ⚠️ 前台捕获    │
│   :9870     │ SendInput注入     │ Playwright可交互    │ 需要焦点       │
└──────────────┴────────────────────┴──────────────────────┴─────────────────┘
```

---

## 八、关键逆向发现总结

### 8.1 VaM内部API层级

```
SuperController.singleton (全局唯一入口)
  ├── GetAtoms() → 场景所有实体
  ├── Atom.GetStorableByID() → 组件参数系统
  │   ├── JSONStorableFloat/Bool/String → 简单参数
  │   ├── JSONStorableStringChooser → 枚举选择器
  │   └── CallAction() → 触发器系统
  ├── DAZCharacterSelector → 角色系统
  │   └── morphsControlUI → 10000+ Morph参数
  ├── FreeControllerV3 → 骨骼IK系统
  └── motionAnimationMaster → 动画播放系统
```

### 8.2 Voxta模块化架构

Voxta采用**DLL热插拔**模式, 38个模块DLL放在Modules/目录, 通过SQLite中的Modules表控制启禁。每个模块有独立的Configuration JSON。Agent可通过DB直控实现**零UI模块管理**。

### 8.3 双引擎协同流程

```
用户说话 → Vosk(STT) → 文本 → DashScope qwen-plus(LLM) → 回复文本
  → ActionInference(动作提取) → VaM Timeline/Morph(动作执行)
  → EdgeTTS/F5TTS(语音合成) → VaM AudioSource(播放)
  → Voxta LipSync(口型同步) → VaM DAZMorph(嘴型变化)
```

### 8.4 Agent独有能力 (超越原生UI)

| 能力 | 原生UI | Agent |
|------|--------|-------|
| 批量Morph设置 | 逐个手动 | `set_morphs()` 一次性 |
| 场景参数化生成 | 手动拖拽 | `SceneBuilder` 代码生成 |
| 脚本热部署 | 手动复制 | `deploy_script()` |
| Voxta DB直控 | Web UI操作 | SQLite直读写 |
| 角色批量导入 | 逐个创建 | TavernCard JSON导入 |
| 全链路诊断 | 手动检查 | `diagnose()` 自动 |
| 后台GUI操作 | 必须聚焦 | PostMessage无感 |
| 远程操控 | 不支持 | Browser Bridge :9870 |

---

## 九、附录

### A. VaM prefs.json 关键参数

| 参数 | 当前值 | 说明 |
|------|--------|------|
| `renderScale` | 1 | 渲染分辨率缩放 |
| `msaaLevel` | 4 | 抗锯齿级别 |
| `pixelLightCount` | 2 | 像素光源数 |
| `physicsRate` | Auto | 物理更新频率 |
| `softBodyPhysics` | true | 软体物理 |
| `enablePlugins` | true | 启用插件 |
| `allowPluginsNetworkAccess` | true | 允许插件网络访问 |
| `enableWebBrowser` | true | 启用内嵌浏览器 |
| `monitorUIScale` | 1.16 | UI缩放 |
| `enableCaching` | true | 启用缓存 |

### B. Voxta 角色表

| 名称 | ID | 用途 |
|------|-----|------|
| 香草 | 67e139a4-... | 主力中文角色 |
| 香草_备用 | 575b8203-... | 备用 |
| 小雅 | d04c5d25-... | 第二角色 |
| Catherine | 575b8203-... | 英文角色 |
| George | 6227dc38-... | 男性角色 |
| Voxta | 35c74d75-... | 系统角色 |
| Male Narrator | 397f9094-... | 旁白 |

### C. VaM快捷键映射

| 快捷键 | 功能 |
|--------|------|
| U | 显示/隐藏UI |
| E | 切换编辑模式 |
| P | 播放模式 |
| F | 冻结物理 |
| F9 | 截图 |
| F11 | 全屏 |
| Ctrl+S | 保存场景 |
| Ctrl+Z/Y | 撤销/重做 |
| Tab | 选择下一个Atom |
| Escape | 取消选择 |
