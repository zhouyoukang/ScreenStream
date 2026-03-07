# VAM-AI 生态全景图

> 市面所有与VaM+AI相关的项目、工具、资源汇总。去杂留精。
> 生成时间: 2026-03-09 | 来源: 本地资产扫描 + 训练知识 + 已有文档

## 一、对话引擎 (核心中枢)

### 1.1 Voxta ⭐ (当前使用)

| 项目 | 值 |
|------|---|
| 官网 | voxta.ai |
| 类型 | 闭源商业 (Patreon付费) |
| 作者 | AcidBubbles |
| 本地版本 | v1.0.0-beta.104 |
| 本地路径 | `F:\vam1.22\Voxta\Active\` |
| VaM插件 | AcidBubbles.Voxta.83.var |
| 特色 | 38个模块DLL, SignalR协议, Scriban模板, SQLite DB, 内嵌Python |
| 支持 | LLM(15+后端) + TTS(8+引擎) + STT(5+引擎) + 记忆 + 动作推理 + 视觉 |
| 缺点 | 闭源, 无法深度定制, UI较重, 更新依赖作者 |

**本地资产:**
- 源码逆向: `Archives/SourceCode/VoxtaReversedComplete/`
- 旧版备份: `Archives/Versions/Voxta.Server.Win.v1.0.0-beta.104/`
- VaM插件源码: `configs/voxta_plugin_src/` (16个C#文件)
- SignalR协议: `docs/SIGNALR_PROTOCOL.md` (完整逆向)

### 1.2 AICU (AI Character Universe)

| 项目 | 值 |
|------|---|
| 官网 | aicu.ai |
| GitHub | github.com/aicu-ai |
| 类型 | 开源 |
| 特色 | 角色AI平台, 支持VaM集成, 社区角色卡 |
| 状态 | 活跃开发中 |
| 价值 | 🟡 中 — Voxta的开源替代方案, 但生态较小 |

### 1.3 SillyTavern ⭐

| 项目 | 值 |
|------|---|
| GitHub | github.com/SillyTavern/SillyTavern (15K+⭐) |
| 类型 | 开源 (AGPL) |
| 特色 | 最流行的AI角色扮演前端, 角色卡生态, 世界信息, 记忆, 多后端 |
| 后端 | OpenAI/Claude/本地LLM/KoboldAI/Oobabooga/Ollama |
| 扩展 | TTS/STT/图像生成/翻译/向量记忆 |
| VaM集成 | 无原生集成, 需自建桥接 (HTTP API) |
| 价值 | 🔴 极高 — 角色卡格式(TavernCard V2)是事实标准, 可导入角色到我们的chat_engine |

### 1.4 KoboldAI / KoboldCpp

| 项目 | 值 |
|------|---|
| GitHub | github.com/LostRuins/koboldcpp (5K+⭐) |
| 类型 | 开源 |
| 特色 | 轻量本地LLM推理, 针对角色扮演优化, GGUF模型支持 |
| Voxta集成 | ✅ 已有模块 (Voxta.Modules.KoboldAI.dll) |
| 价值 | 🟡 高 — 离线LLM方案, CPU也能跑 |

### 1.5 TavernAI

| 项目 | 值 |
|------|---|
| GitHub | github.com/TavernAI/TavernAI |
| 类型 | 开源 |
| 状态 | 已被SillyTavern取代, 不再活跃 |
| 价值 | 🟢 低 — 历史参考, 角色卡格式起源 |

## 二、LLM 后端

### 2.1 云端 LLM

| 服务 | 模型 | 中文 | 费用 | 状态 |
|------|------|------|------|------|
| **DashScope** (阿里) ⭐ | qwen-plus/qwen-max | ✅ 极好 | 低 | ✅ 当前使用 |
| DeepSeek | deepseek-chat/coder | ✅ 极好 | 极低 | 可选替代 |
| OpenRouter | GPT-4/Claude/Llama | ✅ | 按模型 | Voxta已有模块 |
| OpenAI | GPT-4o/4o-mini | ✅ | 中 | Voxta已有模块(已禁用) |
| SiliconFlow | Qwen/DeepSeek/Yi | ✅ | 低 | OpenAI兼容, 可直接用 |
| 智谱AI | GLM-4 | ✅ 极好 | 低 | OpenAI兼容 |
| 百度文心 | ERNIE-4 | ✅ 极好 | 低 | 需适配SDK |

**推荐:** DashScope(已用) + DeepSeek(备用, 极便宜) + SiliconFlow(聚合)

### 2.2 本地 LLM

| 工具 | 特色 | 状态 |
|------|------|------|
| **text-generation-webui** (oobabooga) | 全能本地LLM, 支持GPTQ/GGUF/AWQ | ✅ 已安装 `F:\vam1.22\text-generation-webui\` |
| **Ollama** | 一键部署本地LLM, 最简单 | 可选安装 |
| **LM Studio** | GUI本地LLM, 支持GGUF | 可选安装 |
| **vLLM** | 高性能LLM serving | 适合GPU强的场景 |
| **llama.cpp** | CPU推理, GGUF格式 | Voxta已有模块(LlamaCpp) |
| **ExLlamaV2** | GPU推理, EXL2格式 | Voxta已有模块(ExLlamaV2) |

**推荐:** text-gen-webui(已有) + Ollama(简单备用)

### 2.3 推荐本地模型 (中文角色扮演)

| 模型 | 参数 | 显存 | 中文 | 角色扮演 |
|------|------|------|------|---------|
| Qwen2.5-7B-Instruct | 7B | 6GB | ✅✅ | ✅ |
| Qwen2.5-14B-Instruct | 14B | 12GB | ✅✅ | ✅✅ |
| DeepSeek-V2-Lite | 16B | 12GB | ✅✅ | ✅ |
| Yi-1.5-9B-Chat | 9B | 8GB | ✅✅ | ✅ |
| Mistral-7B-Instruct | 7B | 6GB | ✅ | ✅ |
| Llama-3.1-8B-Instruct | 8B | 8GB | ✅ | ✅✅ |

## 三、TTS (语音合成)

| 引擎 | 开源 | 中文 | 质量 | 延迟 | 克隆 | 状态 |
|------|------|------|------|------|------|------|
| **Edge-TTS** ⭐ | 免费API | ✅✅ | ★★★★ | 低 | ❌ | ✅ 主力使用 |
| **GPT-SoVITS** | ✅ | ✅✅ | ★★★★★ | 中 | ✅✅ | 🔴 强烈推荐 |
| **CosyVoice** (阿里) | ✅ | ✅✅ | ★★★★★ | 中 | ✅ | 可选 |
| **Fish Speech** | ✅ | ✅✅ | ★★★★ | 低 | ✅ | 可选 |
| **ChatTTS** | ✅ | ✅✅ | ★★★★ | 低 | ❌ | 可选(对话风格) |
| **F5-TTS** | ✅ | ✅ | ★★★★ | 中 | ✅ | ✅ Voxta内置 |
| **Kokoro TTS** | ✅ | ✅ | ★★★ | 低 | ❌ | Voxta内置(已禁用) |
| **Silero TTS** | ✅ | ❌ | ★★★ | 极低 | ❌ | ✅ Voxta内置(英文) |
| **XTTS v2** (Coqui) | ✅ | ✅ | ★★★★ | 中 | ✅ | Voxta已有模块 |
| **Piper TTS** | ✅ | ❌ | ★★★ | 极低 | ❌ | 轻量备选 |
| ElevenLabs | 付费 | ✅ | ★★★★★ | 低 | ✅ | Voxta已有模块 |
| Azure TTS | 付费 | ✅✅ | ★★★★★ | 低 | ❌ | Voxta已有模块 |

**推荐升级:** GPT-SoVITS — 可用角色真人语音克隆, 中文质量顶级, 开源免费

### GPT-SoVITS 集成方案
```
1. 安装 GPT-SoVITS (github.com/RVC-Boss/GPT-SoVITS, 30K+⭐)
2. 录制角色参考音频 (3-10秒)
3. 训练微调模型 (可选, 提升质量)
4. 启动API服务 (默认 :9880)
5. 修改 chat_engine.py TTSClient 指向 GPT-SoVITS API
6. 或通过 Voxta TextToSpeechHttpApi 模块接入
```

## 四、STT (语音识别)

| 引擎 | 开源 | 中文 | 准确率 | 延迟 | 状态 |
|------|------|------|--------|------|------|
| **Vosk** ⭐ | ✅ | ✅✅ | ★★★ | 极低 | ✅ 当前使用 |
| **faster-whisper** | ✅ | ✅✅ | ★★★★★ | 中 | 推荐升级 |
| **FunASR** (阿里) | ✅ | ✅✅✅ | ★★★★★ | 低 | 🔴 中文最佳 |
| **SenseVoice** | ✅ | ✅✅✅ | ★★★★★ | 低 | 可选 |
| Whisper (OpenAI) | ✅ | ✅✅ | ★★★★★ | 高 | Voxta有WhisperLive模块 |
| Deepgram | 付费 | ✅ | ★★★★★ | 极低 | Voxta已有模块(已禁用) |
| Windows Speech | 内置 | ✅ | ★★ | 低 | Voxta已有模块 |

**推荐升级:** FunASR — 阿里开源, 中文识别率最高, 支持实时流式

## 五、记忆与知识 (RAG)

| 工具 | 特色 | 状态 |
|------|------|------|
| **SimpleMemory** | 12条滑动窗口, 基于关键词 | ✅ 当前使用 |
| **ChromaDB** ⭐ | 向量数据库, 语义搜索 | ⚠️ Voxta有模块, 未启用 |
| **Qdrant** | 高性能向量数据库 | 可选替代ChromaDB |
| **LangChain** | LLM框架, 丰富的记忆策略 | chat_engine可集成 |
| **LlamaIndex** | 知识索引+RAG | 适合大量背景知识 |
| **mem0** | 个性化AI记忆层 | 轻量, 适合角色记忆 |

**推荐:** 启用ChromaDB(零成本, DLL已存在) → 长期记忆质的飞跃

## 六、VaM 插件生态 (AI相关)

### 已安装

| 插件 | 版本 | 功能 |
|------|------|------|
| AcidBubbles.Voxta | v83 | Voxta对话引擎VaM端 |
| AcidBubbles.Scripter | v1.21 | C#脚本引擎 |
| JayJayWon.BrowserAssist | v45 | VaM内嵌浏览器 |
| MacGruber.SpeechRecognition | v3 | VaM内语音识别 |

### 社区重要插件

| 插件 | 功能 | 价值 |
|------|------|------|
| **VN系列** (vnactor/vnframe/vnscenescript) | 视觉小说引擎 | ✅ 已有BepInEx插件 |
| **Timeline** (AcidBubbles) | 动画时间线编辑器 | ★★★★★ |
| **Embody** (AcidBubbles) | VR沉浸模式 | ★★★★ |
| **Life** (AcidBubbles) | 角色自主行为 | ★★★★★ |
| **Glance** (AcidBubbles) | 眼球追踪 | ★★★ |
| **ExpressionBlendShapes** | 表情混合变形 | ★★★★ |
| **AutoBlink** | 自动眨眼 | ★★★ |
| **LipSync** | 口型同步 | ★★★★ |

### VaM开发工具

| 工具 | 功能 |
|------|------|
| **Scripter** | C#脚本(已有API文档: `docs/scripting-api.md`) |
| **VaM Box** | 包管理器(已有v0.7.3/v0.8.0/v0.9.2) |
| **BepInEx** | Unity mod框架(已安装) |
| **XUnity.AutoTranslator** | 自动翻译(已安装) |

## 七、动画与口型同步

| 工具 | 特色 | VaM集成 |
|------|------|---------|
| **NVIDIA Audio2Face** | 音频驱动面部动画 | 需桥接 |
| **SadTalker** | 说话头像生成 | 图像级, 非3D |
| **MuseTalk** | 实时口型同步 | 图像级 |
| **LivePortrait** | 肖像动画 | 图像级 |
| **VaM内置口型** | Viseme驱动 | ✅ 原生支持 |

**现状:** VaM内置口型足够, Voxta的SpeechPlayback已处理Viseme同步

## 八、角色卡生态

### 格式标准

| 格式 | 来源 | 字段 | 兼容性 |
|------|------|------|--------|
| **TavernCard V2** (PNG) | SillyTavern | name/description/personality/first_mes/mes_example/scenario/system_prompt | 事实标准, 最广泛 |
| **Voxta Character** (SQLite) | Voxta | Name/Description/Personality/Profile/Culture/Scripts | 本地私有 |
| **CharacterAI** (API) | Character.AI | 云端, 不可导出 | 封闭 |
| **AICU Card** | AICU | 类TavernCard | 部分兼容 |

**推荐:** 在chat_engine.py中添加TavernCard V2导入功能 → 接入海量社区角色

### 角色卡资源站

| 站点 | 角色数 | 特色 |
|------|--------|------|
| **chub.ai** | 100K+ | 最大的角色卡社区 |
| **characterhub.org** | 10K+ | 开源角色集合 |
| **janitorai.com** | 50K+ | AI角色平台 |
| **VaM Hub** | 1000+ | VaM专属场景/角色 |

## 九、已有资产清单

### 本地安装 (F:\vam1.22\)

| 组件 | 大小 | 文件数 |
|------|------|--------|
| VaM 1.22主程序 | 137GB | 23,960 |
| Voxta AI引擎 | 21GB | 37,433 |
| text-gen-webui | 10.5GB | 53,525 |
| VAR资源包 | 37GB | 1,042个 |
| VaM Box | 1GB | 3个版本 |
| Scripter源码 | 5MB | 325 |
| EdgeTTS服务 | <1MB | 1 |
| AI模型资产 | ~5GB | Vosk/Whisper/F5/Kokoro/Tiktoken |

### Agent工具链 (VAM-agent/)

| 工具 | 大小 | 功能 |
|------|------|------|
| agent_hub.py | 31KB | 中枢控制(18条CLI) |
| chat_engine.py | 30KB | 独立聊天引擎 |
| vam_control.py | 12KB | 轻量状态面板 |
| health_check.py | - | 五感健康检查 |
| SIGNALR_PROTOCOL.md | 4KB | 协议文档 |
| ARCHITECTURE.md | 7KB | 架构文档 |

## 十、发现的问题与优先改进

### 🔴 高优先 (投入小, 收益大)

| # | 改进 | 投入 | 收益 | 方案 |
|---|------|------|------|------|
| 1 | **启用ChromaDB** | 10min | 长期语义记忆 | Voxta Web UI启用模块 |
| 2 | **TavernCard导入** | 2h | 接入10万+社区角色 | chat_engine.py添加PNG解析 |
| 3 | **DeepSeek备用LLM** | 30min | 超低成本备用 | chat_engine.py添加endpoint |
| 4 | **启用ChainOfThought** | 10min | 回复质量提升 | Voxta Web UI启用模块 |

### 🟡 中优先 (有价值但需投入)

| # | 改进 | 投入 | 收益 |
|---|------|------|------|
| 5 | GPT-SoVITS语音克隆 | 1天 | 角色专属真人音色 |
| 6 | FunASR替换Vosk | 2h | 中文识别率大幅提升 |
| 7 | SillyTavern桥接 | 4h | 复用其UI+角色生态 |
| 8 | Ollama本地LLM | 1h | 完全离线方案 |

### 🟢 低优先 (远期)

| # | 改进 | 说明 |
|---|------|------|
| 9 | Florence2视觉 | 角色能"看"画面 |
| 10 | VaM自动化场景脚本 | Agent控制VaM场景 |
| 11 | 多角色同场对话 | Scenario模式 |
| 12 | 语音唤醒 (Wake Word) | 免键盘触发 |

## 十一、技术路线图

```
当前状态 (v3)
├── Voxta引擎 (闭源, 38模块)
├── chat_engine.py (独立聊天)
├── DashScope qwen-plus (云LLM)
├── EdgeTTS (免费TTS)
├── Vosk (免费STT)
└── SimpleMemory (12条窗口)

Phase 1: 记忆+角色 (1天)
├── 启用ChromaDB → 语义长期记忆
├── TavernCard V2导入 → 社区角色
├── DeepSeek备用LLM
└── 启用ChainOfThought

Phase 2: 语音升级 (2-3天)
├── GPT-SoVITS → 角色克隆音色
├── FunASR → 中文STT升级
└── 流式TTS → 降低延迟

Phase 3: 独立运行 (1周)
├── 完全脱离Voxta
├── Ollama本地LLM
├── Web UI仪表板
└── Agent API服务化

Phase 4: 智能进化 (远期)
├── 视觉理解 (Florence2)
├── 多模态交互
├── 自主行为引擎
└── VaM场景自动化
```

## 十二、GitHub VaM插件生态交叉引用

> 详见 `VAM_GITHUB_ECOSYSTEM.md` 完整生态地图

### 核心开发者与AI相关项目

| 开发者 | 代表项目 | 与AI/Agent的关联 |
|--------|---------|-----------------|
| **AcidBubbles** | Timeline(91★) / Scripter(21★) / Embody(34★) / DevTools(16★) | Voxta作者, Bridge已整合Timeline+Scripter控制 |
| **MewCo-AI** | ai_virtual_mate_comm(684★) | 国产AI虚拟伴侣完整方案, 可参考对话策略 |
| **lfe999** | FacialMotionCapture(22★) / KeyboardShortcuts(13★) | 面捕可联动Bridge表情API |
| **via5** | Vamos(5★) | BepInEx底层工具 |
| **Playable2030** | VaM_PerformancePlugin(7★) | 运行时性能优化, config.py已记录 |

### Agent可整合的插件API

| 插件 | GitHub | Agent对应模块 | 整合状态 |
|------|--------|--------------|---------|
| Timeline | acidbubbles/vam-timeline | bridge.timeline_* | ✅ 已整合 |
| Scripter | acidbubbles/vam-scripter | plugins.deploy_script | ✅ 已整合 |
| Embody | acidbubbles/vam-embody | bridge.set_controller | 🟡 可扩展 |
| VARBsorb | acidbubbles/vam-varbsorb | resources.py | 🟡 可参考 |
| Plugin-Template | acidbubbles/vam-plugin-template | plugins.py | 🟡 可集成 |
| DevTools | acidbubbles/vam-devtools | bridge.health_report | 🟡 可参考 |
| Morphology | morph1sm/morphology | bridge.list_morphs | ✅ 已整合 |
| FacialMotionCapture | lfe999/FacialMotionCapture | bridge.set_expression | 🟡 可联动 |

## 十三、关键URL汇总

| 资源 | URL |
|------|-----|
| Voxta官网 | voxta.ai |
| VaM Hub | hub.virtamate.com |
| SillyTavern | github.com/SillyTavern/SillyTavern |
| KoboldCpp | github.com/LostRuins/koboldcpp |
| GPT-SoVITS | github.com/RVC-Boss/GPT-SoVITS |
| FunASR | github.com/modelscope/FunASR |
| CosyVoice | github.com/FunAudioLLM/CosyVoice |
| Fish Speech | github.com/fishaudio/fish-speech |
| ChatTTS | github.com/2noise/ChatTTS |
| Ollama | github.com/ollama/ollama |
| ChromaDB | github.com/chroma-core/chroma |
| Chub.ai | chub.ai |
| DashScope | dashscope.aliyuncs.com |
| DeepSeek | platform.deepseek.com |
| SiliconFlow | siliconflow.cn |
