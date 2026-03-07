# VAM-agent 统一架构

> 控制面(工作区) ↔ 数据面(F:\vam1.22) 双面统一管理

## 核心原则

```
控制面 (VAM-agent/)              数据面 (F:\vam1.22/)
┌─────────────────────┐         ┌──────────────────────────┐
│ 代码/配置/文档/测试    │ ──引用→ │ 二进制/运行时/大型资源      │
│ ~5MB, git tracked     │         │ ~276GB, 不入git           │
│                       │         │                          │
│ vam/config.py         │ ──────→ │ VAM_ROOT = F:\vam1.22    │
│ voxta/config.py       │ ──────→ │ (独立定义,相同值)          │
│                       │         │                          │
│ AGENT_ROOT = 动态解析  │         │ VAM版本/vam1.22.1.0/     │
│ (Path(__file__))      │         │ Voxta/Active/            │
└─────────────────────┘         │ EdgeTTS/                 │
                                 │ text-generation-webui/   │
                                 │ 资源文件/ (99.8GB)        │
                                 └──────────────────────────┘
```

**路径唯一真相源**: `vam/config.py` (VaM) + `voxta/config.py` (Voxta)
**硬编码仅存在于**: 上述两个config文件 + `startup.bat`
**动态解析**: `AGENT_ROOT = Path(__file__).resolve().parent.parent`

## 控制面结构 (VAM-agent/)

```
VAM-agent/
├── vam/                    VaM 3D引擎 Agent (11 CLI命令)
│   ├── config.py           路径唯一真相源 (VAM_ROOT)
│   ├── agent.py            六感Agent中枢 (25+ runtime_*方法)
│   ├── bridge/             BepInEx HTTP插件 (:8285) + Python客户端
│   │   ├── AgentBridge.cs  C#插件 (部署到VaM BepInEx目录)
│   │   └── client.py       VaMBridge类 (15端点+4批量命令)
│   ├── scenes.py           场景CRUD + SceneBuilder
│   ├── resources.py        VAR/外观/脚本/资源管理
│   ├── characters.py       角色构建 + 行为系统 (Cue: Mood/Personality/Excitement/Gaze/Voice)
│   ├── animations.py       动画构建 + BVH/VMD/MMD/Synergy/CameraDirector/触觉设备
│   ├── environments.py     环境构建 (灯光/相机/音频)
│   ├── plugins.py          BepInEx插件管理
│   ├── process.py          进程启停
│   ├── gui.py              OCR+PostMessage GUI自动化
│   ├── logs.py             日志监控+错误检测
│   ├── signalr.py          VaM Hub SignalR通信
│   ├── configs/            配置文件 (voxta_plugin_src等)
│   ├── docs/               开发文档
│   └── tools/              遗留工具 (已归档.disabled)
│       └── startup.bat     统一启动器 (保留)
│
├── voxta/                  Voxta AI对话引擎 Agent (30+ CLI命令)
│   ├── config.py           路径唯一真相源 (VOXTA_DIR)
│   ├── agent.py            五感Agent中枢
│   ├── db.py               SQLite数据库直控
│   ├── signalr.py          SignalR WebSocket客户端
│   ├── chat.py             聊天引擎 (standalone/voxta双模式)
│   ├── hub.py              中枢CRUD+诊断+自动修复
│   ├── twitch_relay.py     Twitch→Voxta消息桥接 (from voxta-twitch-relay)
│   ├── process.py          服务生命周期管理
│   ├── logs.py             Voxta日志监控
│   ├── configs/            导出数据+配置快照
│   ├── docs/               审计报告/协议文档
│   └── tools/              保留: chat_engine.py + _test_*.py
│
├── browser_bridge/         桌面应用浏览器化 (Playwright)
├── ARCHITECTURE.md         本文件
├── AUDIT_REPORT.md         资源审计报告
└── README.md               项目概览
```

## 数据面结构 (F:\vam1.22/, ~276GB)

| 目录 | 大小 | 控制面引用 | 角色 |
|------|------|-----------|------|
| `VAM版本/vam1.22.1.0/` | 137GB | `VAM_CONFIG.VAM_INSTALL` | VaM主程序+资源 |
| `VAM版本/VAM2 Beta1.0/` | 1.8GB | `VAM_CONFIG.VAM2_INSTALL` | VAM2测试版 |
| `Voxta/Active/` | 12.7GB | `VOXTA_CONFIG.VOXTA_DIR` | AI对话引擎 |
| `text-generation-webui/` | 10.8GB | `VOXTA_CONFIG.TEXTGEN_DIR` | LLM后端 |
| `资源文件/` | 99.8GB | `VAM_CONFIG.RESOURCES_DIR` | 人物/场景资源包 |
| `EdgeTTS/` | <1MB | `VOXTA_CONFIG.EDGETTS_DIR` | TTS服务脚本 |
| `scripter.github/` | 5MB | `VAM_CONFIG.SCRIPTER_DIR` | Scripter插件源码 |
| `BrowserAssist付费版/` | 0.7MB | `VAM_CONFIG.BROWSER_ASSIST` | BA付费版 |

## 服务矩阵

| 服务 | 端口 | 类型 | 状态 |
|------|------|------|------|
| VaM AgentBridge | :8285 | HTTP | ✅ 运行时直控 |
| Voxta | :5384 | 对话引擎 | ✅ 核心 |
| EdgeTTS | :5050 | TTS | ✅ 主力TTS |
| DashScope | 云 | LLM | ✅ qwen-plus |
| Vosk | 内嵌 | STT | ✅ 中文语音识别 |
| F5TTS | 内嵌 | TTS | ✅ GPU英文TTS |
| TextGen-WebUI | :7860 | LLM | 可选 |

## CLI入口

### VaM (`python -m vam <cmd>`, CWD=VAM-agent父目录)

`health` `report` `services` `scenes` `scripts` `plugins` `errors` `disk` `paths` `dashboard` `scan`

### Voxta (`python -m voxta <cmd>`, 30+命令)

- **查看**: `dashboard` `characters` `char-detail` `modules` `chats` `messages` `scenarios` `presets` `memories` `stats` `tables` `logs`
- **连接**: `signalr` `services`
- **操作**: `backup` `start` `enable` `disable` `char-create` `char-edit` `tts`
- **聊天**: `chat` `chat-voxta` `list` `prompt` `test-llm` `test-tts`
- **诊断**: `health` `diagnose` `fix-dry` `fix` `json`

## 数据库直控 (绕过Voxta Web UI)

角色CRUD | 模块启禁+配置 | 记忆书 | 对话历史 | 预设管理 | 统计 | 自动备份

## 聊天引擎 (voxta/chat.py)

完全重新实现Voxta核心逻辑: 角色加载 → system prompt构建 → 记忆窗口(12轮) → LLM直调 → TTS直调 → 动作推理

- **standalone模式**: 脱离Voxta, 直接调LLM+TTS+DB
- **voxta模式**: SignalR连接运行中的Voxta

## SignalR协议

详见 `voxta/docs/SIGNALR_PROTOCOL.md` — 14种Client→Server + 29种Server→Client消息

## 安全

- DashScope API key: DPAPI加密 (Windows本机绑定, 安全)
- 火山引擎凭据明文: 已禁用模块中残留 (低风险)
- DB操作前: 自动备份到 `.agent_backup`

## 清理记录 (2026-03)

### 归档的遗留工具 (→.disabled)

| 文件 | 被谁取代 |
|------|---------|
| `vam/tools/vam_control.py` | `vam/agent.py` + `vam/__main__.py` |
| `vam/tools/scene_builder.py` | `vam/scenes.py` |
| `vam/tools/resource_scanner.py` | `vam/resources.py` |
| `vam/tools/vam_launcher.py` | `vam/process.py` |
| `voxta/tools/agent_hub.py` | `voxta/agent.py` + `voxta/__main__.py` |
| `voxta/tools/health_check.py` | 双Agent健康检查 |
| `voxta/tools/voxta_manager.py` | `voxta/db.py` + `voxta/process.py` |
| `voxta/tools/_audit*.py` | 一次性审计脚本 |

### 路径统一修复

| 修复 | 说明 |
|------|------|
| `AGENT_ROOT` 动态化 | `Path(__file__).resolve().parent.parent` 替代硬编码 |
| `chat_engine.py` 导入修复 | `from voxta.config import VOXTA_CONFIG` + fallback |
| `VAMBOX_EXE` 标注可选 | 磁盘不存在, 不影响功能 |
