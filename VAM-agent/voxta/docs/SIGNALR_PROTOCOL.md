# Voxta SignalR Protocol Reference

> 从 AcidBubbles.Voxta VaM插件源码 v1.0.0-beta.150 完整逆向 (16 C# files, ~4200 LOC)
> API版本: 2025-08 | 服务器版本: 1.0.0-beta.150

## 连接流程

```
1. WebSocket连接 ws://localhost:5384/hub
2. 发送握手: {"protocol":"json","version":1}\x1e
3. 收到确认: {}\x1e
4. 发送认证: {$type:"authenticate", client, clientVersion, scope, capabilities}
5. 收到: {$type:"welcome", voxtaServerVersion, apiVersion, user}
```

## 消息帧格式

所有消息用 `\x1e` (ASCII 30) 分隔，封装在SignalR Invocation帧中：
- 发送: `{"arguments":[MESSAGE],"target":"SendMessage","type":1}\x1e`
- 接收: `{"type":1,"target":"ReceiveMessage","arguments":[MESSAGE]}`
- Ping: `{"type":6}` → 原样回复

## Client → Server (14种)

| $type | 参数 | 说明 |
|-------|------|------|
| authenticate | client, clientVersion, scope:["role:app"], capabilities:{audioOutput:"Url"}, apiVersion | 认证 |
| loadCharactersList | - | 请求角色列表 |
| loadScenariosList | - | 请求场景列表 |
| loadChatsList | characterId, scenarioId? | 请求聊天列表 |
| startChat | **characterIds[]**, contextKey, scenarioId?, chatId?, contexts?, actions?, dependencies?, roles? | 开始聊天 (注意: characterIds是数组!) |
| stopChat | - | 停止聊天 |
| send | sessionId, text, doReply, doCharacterActionInference | 发送消息 |
| characterSpeechRequest | sessionId, text | 请求TTS |
| speechPlaybackStart | sessionId, messageId, startIndex, endIndex, duration, isNarration | 语音开始播放 |
| speechPlaybackComplete | sessionId, messageId | 语音播放完毕 |
| revert | sessionId | 撤销最后消息 |
| deleteChat | chatId | 删除聊天 |
| updateContext | sessionId, contexts?, actions?, contextKey?, setFlags? | 更新上下文/动作/标志 |
| deployResource | id, data{$type,name,base64Data} | 部署资源 |

## Server → Client (29种)

| $type | 关键字段 | 说明 |
|-------|---------|------|
| welcome | voxtaServerVersion, apiVersion, user | 连接成功 |
| charactersListLoaded | characters[] | 角色列表 |
| scenariosListLoaded | scenarios[] | 场景列表 |
| chatsListLoaded | chats[] | 聊天列表 |
| chatInProgress | - | 已有聊天进行中 |
| chatStarted | sessionId, chatId, context{characters[],flags[]}, services{textToSpeech,speechToText,actionInference} | 聊天开始 |
| chatConfiguration | - | 聊天配置 |
| chatClosed | chatId | 聊天关闭 |
| chatLoading | - | 聊天加载中 |
| replyGenerating | sessionId, messageId, senderId, thinkingSpeechUrl, isNarration | AI生成中(思考语音) |
| replyStart | sessionId, messageId, senderId | 回复开始 |
| replyChunk | sessionId, messageId, senderId, text, audioUrl, startIndex, endIndex, isNarration, audioGapMs | 回复文本+音频块 |
| replyEnd | sessionId, messageId, senderId | 回复结束 |
| replyCancelled | - | 回复取消 |
| speechRecognitionStart | - | STT开始 |
| speechRecognitionPartial | text | STT中间结果 |
| speechRecognitionEnd | text | STT最终结果 |
| action | value | 动作推理结果 |
| appTrigger | name, arguments[] | 应用触发器 |
| contextUpdated | flags[] | 上下文标志更新 |
| chatFlow | state | 聊天流程状态 |
| error / chatSessionError | message, code?, serviceName? | 错误 |
| missingResourcesError | resources[{id,kind,version,status}] | 缺失资源 |
| configuration | configurations[] / services{} | 服务配置 |
| update | text, role | 消息更新 |
| interruptSpeech | - | 中断语音 |
| memoryUpdated | - | 记忆更新 |
| recordingStatus | enabled | 录音状态 |
| moduleRuntimeInstances | - | 模块初始化 |
| deployResourceResult | success, error, id, version, status | 资源部署结果 |
| downloadProgress | - | 资源下载进度 |
| chatPaused | - | 聊天暂停 |
| audioFrame | - | 音频帧(忽略) |
| wakeWordStatus | - | 唤醒词状态(忽略) |
| listResourcesResult | - | 资源列表(忽略) |
| chatParticipantsUpdated | - | 参与者更新(忽略) |
| chatsSessionsUpdated | - | 会话更新(忽略) |
| inspectorEnabled | - | 调试面板(忽略) |
| recordingRequest | - | 录音请求(VaM不支持) |
| visionCaptureRequest | - | 视觉捕获(VaM不支持) |

## 聊天流水线 (重新实现)

```
用户输入 → send{text, doReply:true}
  ↓
replyGenerating{thinkingSpeechUrl}  ← 思考语音(可选)
  ↓
replyStart{messageId, senderId}
  ↓
replyChunk{text, audioUrl} × N     ← 流式文本+音频
  ↓
replyEnd{messageId}
  ↓
action{value}                       ← 动作推理(可选)
  ↓
speechPlaybackStart → Complete      ← 客户端报告播放状态
```

## Prompt构建管线 (Scriban模板)

Voxta使用Scriban模板引擎构建LLM prompt:
- **ChatML** (DashScope/qwen): `<|im_start|>system/user/assistant<|im_end|>`
- **Generic**: `role: message` 纯文本
- **Llama3**: `<|begin_of_text|><|start_header_id|>system<|end_header_id|>`

变量: `system_message`, `messages[]`, `char`, `prefix`

## 动作控制体系 (Actions / AppTrigger / Flags)

### 三层架构

```
┌─────────────────────────────────────────────────────┐
│ Layer 1: Action Inference (AI驱动)                   │
│   LLM分析回复 → 匹配Scenario中定义的Actions          │
│   需要: ActionInferencePresetId + doCharacterAction  │
│          InferenceMessage:true + flagsFilter匹配     │
├─────────────────────────────────────────────────────┤
│ Layer 2: Scenario Scripts (JS脚本)                   │
│   Action触发时执行effect.script → 可调用             │
│   chat.appTrigger(name, ...args)                     │
├─────────────────────────────────────────────────────┤
│ Layer 3: AppTrigger (远程控制)                       │
│   appTrigger消息发送到客户端 → VaM TriggerInvoker    │
└─────────────────────────────────────────────────────┘
```

### 动作触发流程 (已验证 2026-03-04)

```
1. Client → send{text, doReply:true, doCharacterActionInference:true}
2. Server → LLM生成回复 (replyChunk × N → replyEnd)
3. Server → ActionInference分析回复,匹配Scenario Actions
4. 匹配成功 → 运行action.effect.script (JS)
5. Script调用 chat.appTrigger("Emote", emoji, color)
6. Server → Client: action{value:"play_smile_emote"}
7. Server → Client: appTrigger{name:"Emote", arguments:["😊","rgb(...)"]} 
```

### 启用条件 (全部必须满足)

1. **LLM模块有ActionInferencePresetId** — DashScope(OpenAICompatible)已配置 ✅
2. **startChat指定scenarioId** — 使用含Actions的场景 (如 "Voxta UI")
3. **set_flags设置对应标志** — emote actions需要 `emotes` flag
4. **send消息带doCharacterActionInference:true**

### Scenario Actions (Voxta UI场景, 11个emote)

| Action | description | flagsFilter |
|--------|------------|-------------|
| play_hearts_emote | 角色感到强烈的爱 | emotes |
| play_unhappy_emote | 角色不满 | emotes |
| play_smile_emote | 角色开心 | emotes |
| play_laugh_emote | 角色大笑 | emotes |
| play_cry_emote | 角色哭泣/悲伤 | emotes |
| play_fear_emote | 角色害怕 | emotes |
| play_angry_emote | 角色生气 | emotes |
| play_horny_emote | 角色兴奋 | emotes |
| play_question_emote | 角色困惑 | emotes |
| play_surprise_emote | 角色惊讶 | emotes |
| play_neutral_emote | 情绪不明显 | emotes |

### AppTrigger 远程控制 (VaM TriggerInvoker)

服务器可通过 `appTrigger` 远程操控VaM:

| trigger.Name | arguments | 效果 |
|---|---|---|
| Action | [atom, storable, actionName] | 调用动作 |
| String | [atom, storable, param, value] | 设字符串参数 |
| StringChooser | [atom, storable, param, value] | 设选择器参数 |
| Bool | [atom, storable, param, "true"/"false"] | 设布尔参数 |
| Float | [atom, storable, param, value] | 设浮点参数 |
| Color | [atom, storable, param, "#RRGGBB"] | 设颜色参数 |
| Emote | [emoji, color] | 表情动画 (Voxta UI专用) |
| SelectView | [view] | 切换视图 (portrait/talk/chat) |
| SetBackgroundFromScenario | [path] | 设置背景图 |

### Flags 标志系统

```
Client → Server: updateContext{sessionId, setFlags:["emotes","custom"]}
Server → Client: contextUpdated{flags:["emotes","custom"]}
```

标志控制哪些Actions可触发 — action.flagsFilter中的标志必须在当前flags中存在。

### Actions DSL 格式

插件通过文本DSL定义动作,经 `ActionsParser` 解析为JSON:

```
action: wave
short: Waves hand
when: Greeting someone
layer: gesture
timing: during
effect: A friendly wave
trigger: wave_trigger
flags: happy,friendly
setFlags: greeted
activates: smile
cancelReply: false
finalLayer: false
```

支持字段: action, short, when, layer, finalLayer, timing, cancelReply, match/matchFilter, flags/flagsFilter, roleFilter, effect, note, secret, instructions, event, generate, trigger, setFlags, activates

## 语音播放同步协议

客户端必须在播放每个音频块后报告:
```
1. 收到 replyChunk{audioUrl, text, startIndex, endIndex}
2. 下载并播放音频
3. 发送 speechPlaybackStart{sessionId, messageId, startIndex, endIndex, duration, isNarration}
4. 等待音频播放完毕
5. 收到 replyEnd{messageId} 后发送 speechPlaybackComplete{sessionId, messageId}
```

**关键**: duration必须是实际音频时长(秒),否则Voxta的STT计时会错乱。

## Agent重新实现

`chat_engine.py` 重新实现了完整管线:
1. **CharacterLoader** — 从SQLite加载角色+记忆
2. **PromptBuilder** — system prompt构建(人格+记忆+示例)
3. **LLMClient** — 直调DashScope/DeepSeek/本地LLM(自动降级)
4. **TTSClient** — 直调EdgeTTS
5. **VoxtaSignalR** — 连接运行中Voxta的完整SignalR客户端
6. **ActionInference** — 从回复提取动作标签(*action*/[action])
7. **ConversationHistory** — DB读写对话历史
8. **set_flags / update_context** — 场景标志和上下文/动作更新

## 已知协议差异 (chat_engine.py vs C#插件)

| 差异 | C#插件 | Python | 影响 |
|---|---|---|---|
| startChat | characterIds[] | characterIds[] ✅ | 已修复 |
| scenario支持 | scenarioId + actions | scenarioId ✅ | 已支持 |
| set_flags | SendSetFlags | set_flags ✅ | 已实现 |
| update_context | UpdateContext(actions,context) | update_context ✅ | 已实现 |
| acknowledge_playback | 真实音频时长 | 固定1.0s | STT计时错乱 |
| contextKey | "VaM/Base" | "VAM-agent/Base" | OK |
| capabilities | audioOutput:"Url" | 同 | OK |
| 消息类型覆盖 | 30+ | ~25 | 基本完整 |
