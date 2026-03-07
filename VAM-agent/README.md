# VAM-agent — Virt-A-Mate 开发资源整合中枢

> AI Agent驱动的VAM开发、资源管理、自动化工具集

## 项目目标

1. **整合本机所有VAM资源** — 统一索引，消除散落
2. **汇集网络优质资源** — 插件/教程/社区/工具一站式导航
3. **AI Agent自动化** — 一键启动/资源扫描/Voxta管理/场景生成
4. **插件开发支持** — C# Scripting API参考 + 模板 + 最佳实践

## 目录结构

```
VAM-agent/
├── vam/                   # VaM 3D引擎自动化包 (31五感方法)
│   ├── config.py          # VaM路径/常量 (唯一真相源)
│   ├── agent.py           # VaM五感Agent
│   ├── gui.py             # VaM GUI自动化 (OCR+坐标点击+快捷键)
│   ├── scenes.py          # 场景CRUD + SceneBuilder
│   ├── resources.py       # VAR包/外观/服装/脚本
│   ├── plugins.py         # BepInEx/自定义脚本
│   ├── process.py         # VaM进程管理
│   ├── logs.py            # VaM日志监控
│   ├── docs/              # VaM开发文档 (4篇)
│   ├── tools/             # VaM遗留工具
│   ├── tests/             # VaM GUI测试脚本
│   └── configs/           # VaM场景预设/Voxta插件C#源码
├── voxta/                 # Voxta AI对话引擎包 (40+五感方法)
│   ├── config.py          # Voxta路径/端口/角色/模块
│   ├── agent.py           # Voxta五感Agent
│   ├── db.py              # Voxta DB操作
│   ├── signalr.py         # SignalR WebSocket通信
│   ├── process.py         # Voxta/EdgeTTS/TextGen服务
│   ├── logs.py            # Voxta日志读取
│   ├── chat.py            # 聊天引擎(独立/Voxta双模式)
│   ├── hub.py             # 中枢控制(角色CRUD/诊断/自动修复)
│   ├── docs/              # Voxta文档 (9篇含审计/协议/诊断报告)
│   ├── tools/             # Voxta遗留工具/测试脚本
│   └── configs/           # Voxta配置导出
├── browser_bridge/        # 桌面应用浏览器化 (屏幕捕获→Canvas→AI操控)
│   ├── server.py          # FastAPI服务 + 屏幕捕获 + 输入注入
│   ├── playwright_agent.py # Playwright AI Agent + OCR
│   ├── static/index.html  # Web客户端 (Canvas渲染)
│   └── test_*.py          # E2E测试
├── _screenshots/          # 测试截图归档 (gitignored)
├── _test_results/         # 测试结果JSON归档 (gitignored)
├── AGENTS.md              # Agent操作指令
└── ARCHITECTURE.md        # 架构文档
```

## 本机资源概览

| 组件 | 路径 | 状态 |
|------|------|------|
| VAM 1.22 主程序 | `F:\vam1.22\VAM版本\vam1.22.1.0\` | ✅ 已安装 |
| VAM2 Beta 1.0 | `F:\vam1.22\VAM版本\VAM2 Beta1.0\` | ✅ 可用 |
| Voxta AI引擎 | `F:\vam1.22\Voxta\` | ✅ 已配置 |
| Scripter 插件 | `F:\vam1.22\scripter.github\` | ✅ v1.5.1 |
| BrowserAssist | `F:\vam1.22\BrowserAssist付费版\` | ✅ v45付费版 |
| VaM Box | `E:\浏览器下载\vambox-v0.9.2\` | ✅ v0.9.2 |
| text-generation-webui | `F:\vam1.22\text-generation-webui\` | ✅ LLM后端 |
| 资源文件(人物/场景) | `F:\vam1.22\资源文件\` | ✅ 多套 |
| 自动化脚本 | `F:\vam1.22\Scripts\` | ✅ 三类 |
| EdgeTTS服务 | `F:\vam1.22\EdgeTTS\` | ✅ Python |

## 快速开始

```python
# VaM Agent
from vam import VaMAgent
vam = VaMAgent()
vam.taste_health()       # VaM健康检查
vam.see_scenes()         # 场景列表
vam.quick_report()       # 快速报告

# Voxta Agent
from voxta import VoxtaAgent
voxta = VoxtaAgent()
voxta.taste_health()     # Voxta健康检查
voxta.see_dashboard()    # Voxta仪表盘
voxta.touch_chat_standalone("小雅", "你好")  # 独立对话
voxta.smell_diagnose_text()  # 全链路诊断
```

```bash
# CLI
python -m vam health       # VaM健康检查
python -m vam dashboard    # VaM综合仪表盘
python -m voxta dashboard  # Voxta综合仪表板
python -m voxta signalr    # 测试SignalR连接
python -m voxta chat 小雅   # 独立模式对话
python -m voxta diagnose   # 全链路诊断
python -m voxta help       # 查看全部30+命令
```

## 技术栈

- **VAM**: Virt-A-Mate 1.22 + VAM2 Beta (Unity引擎)
- **脚本**: C# (Scripter插件) + Python (自动化)
- **AI对话**: Voxta (TTS/STT/LLM集成)
- **TTS**: EdgeTTS / 火山引擎 / Azure Speech
- **STT**: Vosk (离线中文) / Whisper
- **LLM**: text-generation-webui / one-api / 阿里云千问

## 相关链接

- [VaM Hub](https://hub.virtamate.com/) — 官方资源中心
- [Timeline GitHub](https://github.com/acidbubbles/vam-timeline) — 动画时间线插件
- [Scripter GitHub](https://github.com/acidbubbles/vam-scripter) — 脚本编辑器
- [Embody GitHub](https://github.com/acidbubbles/vam-embody) — 第一人称沉浸插件 (PoV+Passenger+Snug)
- [Voxta](https://voxta.ai/) — AI对话引擎
- [MeshedVR](https://www.patreon.com/meshedvr) — VAM开发者Patreon

### GitHub 生态 (详见 `vam/docs/VAM_GITHUB_ECOSYSTEM.md`)

| 项目 | Stars | 核心功能 |
|------|-------|----------|
| [MewCo-AI/ai_virtual_mate_comm](https://github.com/MewCo-AI/ai_virtual_mate_comm) | 684 | AI虚拟伙伴社区版 (Python) |
| [NaturalWhiteX/vambox-release](https://github.com/NaturalWhiteX/vambox-release) | 157 | VaM Box 包管理器 |
| [acidbubbles/vam-timeline](https://github.com/acidbubbles/vam-timeline) | 91 | 动画时间线编辑器 |
| [acidbubbles/vam-plugin-template](https://github.com/acidbubbles/vam-plugin-template) | 56 | C#插件开发模板 |
| [acidbubbles/vam-embody](https://github.com/acidbubbles/vam-embody) | 34 | VR沉浸体验 |
| [acidbubbles/vam-varbsorb](https://github.com/acidbubbles/vam-varbsorb) | 25 | VAR包清理工具 |
| [lfe999/FacialMotionCapture](https://github.com/lfe999/FacialMotionCapture) | 22 | 面部动作捕捉 |
| [sFisherE/mmd2timeline](https://github.com/sFisherE/mmd2timeline) | 21 | MMD→Timeline转换 (面部/手指/骨骼映射) |
| [ZengineerVAM/VAMLaunch](https://github.com/ZengineerVAM/VAMLaunch) | 26 | 触觉设备集成 (Buttplug.io) |
| [CraftyMoment/mmd_vam_import](https://github.com/CraftyMoment/mmd_vam_import) | 18 | VMD→VaM场景JSON转换 |
| [acidbubbles/vam-devtools](https://github.com/acidbubbles/vam-devtools) | 16 | 开发工具集 |
| [vam-community/vam-party](https://github.com/vam-community/vam-party) | 18 | 社区包管理器 |
