# VAM-agent AGENTS.md

> Agent操作本目录时自动加载此指令。v6 (2026-03-04)

## ⚠️ VaM vs Voxta 隔离边界（防混淆·必读）

> **VaM** = Virt-A-Mate，3D角色渲染引擎（Unity）
> **Voxta** = AI对话引擎（TTS/STT/LLM），通过SignalR与VaM通信
> 两者是**独立系统**，通过插件桥接。开发时严禁混淆。

| 维度 | VaM（3D渲染） | Voxta（AI对话） | 共享基础设施 |
|------|--------------|----------------|-------------|
| **进程** | VaM.exe | Voxta.Server.exe / DesktopApp.exe | EdgeTTS(:5050) |
| **磁盘** | `F:\vam1.22\VAM版本\` | `F:\vam1.22\Voxta\Active\` | `F:\vam1.22\EdgeTTS\` |
| **数据** | 场景JSON/VAR包/外观预设 | SQLite DB/角色/记忆书 | — |
| **脚本** | C# Scripter / BepInEx | SignalR协议 / Python CLI | — |
| **Python包** | `vam/` (config/agent/process/scenes/resources/plugins/logs) | `voxta/` (config/db/signalr/logs/process/agent/chat/hub) | — |
| **子目录** | `vam/tools/` + `vam/docs/` + `vam/tests/` + `vam/configs/` | `voxta/tools/` + `voxta/docs/` + `voxta/configs/` | — |

### Python包结构 (核心)

| 包 | 模块 | 职责 |
|----|------|------|
| **vam/** | `config.py` | VaM路径/常量配置 |
| **vam/** | `agent.py` | VaM五感Agent (22方法) |
| **vam/** | `process.py` | VaM进程管理 |
| **vam/** | `scenes.py` | 场景CRUD + SceneBuilder |
| **vam/** | `resources.py` | VAR包/外观/服装/脚本 |
| **vam/** | `plugins.py` | BepInEx/自定义脚本 |
| **vam/** | `logs.py` | VaM日志监控+错误检测 |
| **voxta/** | `config.py` | Voxta路径/端口/角色ID/模块分类 |
| **voxta/** | `agent.py` | Voxta五感Agent (40+方法) |
| **voxta/** | `db.py` | Voxta DB直控(角色/模块/记忆书/对话, _db_conn上下文管理器) |
| **voxta/** | `signalr.py` | SignalR实时WebSocket通信 |
| **voxta/** | `process.py` | Voxta/EdgeTTS/TextGen服务管理 |
| **voxta/** | `logs.py` | Voxta日志读取/错误检测/关键词搜索 |
| **voxta/** | `chat.py` | 聊天引擎(独立/Voxta双模式, LLM/TTS直调, secrets.env自动加载) |
| **voxta/** | `hub.py` | 中枢控制(DB高级CRUD/TavernCard/诊断/自动修复) |

### 遗留工具 (已迁入包内, 功能已整合)

| 位置 | 工具 | 职责 |
|----|------|------|
| **vam/tools/** | `vam_launcher.py` | VaM进程启动 |
| **vam/tools/** | `scene_builder.py` | 场景JSON生成 |
| **vam/tools/** | `resource_scanner.py` | 本机VaM资源扫描统计 |
| **voxta/tools/** | `agent_hub.py` | 中枢v2 (已整合至voxta/hub.py) |
| **voxta/tools/** | `chat_engine.py` | 聊天引擎 (已整合至voxta/chat.py) |
| **voxta/tools/** | `health_check.py` | 诊断 (已整合至voxta/hub.py Diagnostics) |

## 服务端口

| 服务 | 端口 | 域 |
| ---- | ---- | ---- |
| EdgeTTS | :5050 | Voxta TTS |
| Voxta | :5384 | Voxta 对话引擎 |
| TextGen | :7860 | Voxta LLM(可选) |

## 通信链路

```text
VaM ←SignalR/WS→ Voxta(:5384) → LLM: DashScope qwen-plus (云)
                               → TTS: WindowsSpeech(中文) / F5TTS+Silero(英文)
                               → STT: Vosk-cn-0.22 (本地)
EdgeTTS(:5050) — 独立Flask服务，当前未被Voxta模块引用
```

## 关键路径

| 域 | 路径 | 说明 |
|----|------|------|
| VaM | `F:\vam1.22\VAM版本\vam1.22.1.0\VaM.exe` | VaM主程序 |
| VaM | `F:\vam1.22\scripter.github\` | Scripter插件源码 |
| VaM | `F:\vam1.22\资源文件\` | 人物/场景/服装资源 |
| Voxta | `F:\vam1.22\Voxta\Active\` | Voxta运行目录 |
| Voxta | `F:\vam1.22\Voxta\Active\Data\Voxta.sqlite.db` | Voxta数据库 |
| Voxta | `F:\vam1.22\Voxta\Active\appsettings.json` | Voxta配置 |
| 共享 | `F:\vam1.22\EdgeTTS\voxta_edge_tts_server.py` | EdgeTTS服务器 |
| 桥接 | `vam/configs/voxta_plugin_src/` | VaM↔Voxta插件源码(C#) |

## Browser Bridge (桌面应用浏览器化)

| 维度 | 说明 |
|------|------|
| **包** | `browser_bridge/` |
| **功能** | 屏幕捕获→JPEG编码→WebSocket→Canvas渲染→输入注入 |
| **端口** | :9870 (FastAPI) |
| **依赖** | fastapi, uvicorn, mss, opencv-python, playwright, rapidocr-onnxruntime |
| **文件** | `server.py` (服务) / `playwright_agent.py` (AI Agent) / `static/index.html` (客户端) |

```bash
python -m browser_bridge.server --port 9870 --fps 15 --quality 70
```

## 文档索引

| 文档 | 域 | 内容 |
| ---- | ---- | ---- |
| `ARCHITECTURE.md` | 混合 | 架构v3(聊天引擎+SignalR+Voxta内部) |
| `FIVE_SENSES_AUDIT.md` | 混合 | 代码质量五感审计报告 |
| `requirements.txt` | 混合 | 核心Python依赖 |
| `requirements-bridge.txt` | 桥接 | Browser Bridge依赖 |
| `voxta/docs/AUDIT_REPORT.md` | Voxta | 五感审计报告 |
| `voxta/docs/REVIEW_REPORT.md` | 混合 | 全面审查报告(39文件逐一审查) |
| `vam/docs/VAM_AI_ECOSYSTEM.md` | 混合 | VAM-AI生态全景 |
| `voxta/docs/SIGNALR_PROTOCOL.md` | 桥接 | SignalR协议逆向 |
| `vam/docs/VAM_AGENT_CONTROL.md` | VaM | VaM Agent控制手册 |
| `vam/docs/scripting-api.md` | VaM | C# Scripter API速查 |
| `vam/docs/plugin-dev-guide.md` | VaM | VaM插件开发指南 |
| `voxta/docs/voxta-integration.md` | 桥接 | Voxta AI集成指南 |
| `browser_bridge/README.md` | 桥接 | Browser Bridge架构/API/使用指南 |

## Agent操作规则

- **推荐用新包**: `from vam import VaMAgent` + `from voxta import VoxtaAgent`
- **DB操作前必须备份**: `voxta_agent.touch_backup()` 或 `python -m voxta backup`
- **Voxta运行中修改DB**: commit后执行WAL checkpoint确保持久化
- 资源文件不要随意删除
- VaM Box解压密码: [见secrets.env VAM_BOX_PASS]
- API Key使用DPAPI加密存储（`AQAAANCMnd8...`前缀）

### CLI入口

```bash
python -m vam health      # VaM健康检查
python -m vam dashboard    # VaM综合仪表盘
python -m voxta dashboard  # Voxta综合仪表板
python -m voxta signalr    # 测试SignalR连接
python -m voxta backup     # 备份Voxta数据库
python -m voxta chat 小雅   # 独立模式对话
python -m voxta diagnose   # 全链路诊断
python -m voxta help       # 查看全部30+命令
```

## F:\vam1.22 目录隔离地图

```
F:\vam1.22\
├── VAM版本\            ← VaM域（3个版本，24K+文件）
├── scripter.github\    ← VaM域（Scripter插件源码）
├── BrowserAssist付费版\ ← VaM域（浏览器插件）
├── 资源文件\            ← VaM域（人物/场景/服装）
├── Voxta\              ← Voxta域（37K文件，13.2GB）
├── EdgeTTS\            ← 共享域（TTS服务）
├── text-generation-webui\ ← Voxta域（本地LLM，10.5GB）
├── one-api-data\       ← Voxta域（LLM网关）
├── _非VAM文件\          ← ⚠️ 杂项（非VaM内容，应清理）
├── _旧脚本归档\         ← 归档（历史脚本）
├── _AI报告归档\         ← 归档（71份旧AI报告，可删除）
└── Documentation\      ← 归档（46份文档）
```
