# VAM-agent/vam — Agent操作指令

> 此目录是VaM域统一控制包。操作此目录时自动加载本指令。

## 架构

```
vam/
├── config.py      — 所有路径/常量/服务配置 (唯一真相源)
├── process.py     — 服务生命周期 (VaM/Voxta/EdgeTTS/TextGen)
├── scenes.py      — 场景CRUD + SceneBuilder参数化构建器
├── resources.py   — 资源管理 (VAR包/外观/服装/脚本/磁盘)
├── plugins.py     — 插件管理 (BepInEx/Custom Scripts/PluginData)
├── voxta.py       — Voxta桥接 (DB直控/模块/角色/记忆书/预设)
├── logs.py        — 日志监控 (VaM/Voxta/BepInEx + 错误检测)
├── signalr.py     — Voxta SignalR实时通信 (WebSocket)
├── agent.py       — 统一Agent (31个五感方法)
├── __main__.py    — CLI入口 (python -m vam <command>)
└── __init__.py    — 包入口 (exports: VAM_CONFIG, VaMAgent, signalr)
```

## 五感接口映射

| 感官 | 方法前缀 | 数量 | 功能 |
|------|---------|------|------|
| 视 | `see_*` | 8 | 文件/场景/日志/插件/Voxta状态感知 |
| 听 | `hear_*` | 4 | 服务端口/HTTP健康/SignalR实时监控 |
| 触 | `touch_*` | 10 | 进程启停/场景CRUD/脚本部署/SignalR对话 |
| 嗅 | `smell_*` | 5 | 风险预判/错误检测/磁盘预警/日志搜索 |
| 味 | `taste_*` | 3 | 全面健康检查/完整扫描/模块评估 |

## 使用方式

```python
from vam.agent import VaMAgent
agent = VaMAgent()

# 快速健康检查
report = agent.taste_health()

# 创建Voxta场景
path = agent.touch_create_scene("香草")

# 查看服务状态
status = agent.hear_services()

# 综合仪表板
dashboard = agent.dashboard()
```

## 约束

- **config.py 是唯一路径真相源** — 禁止在其他文件硬编码路径
- **写操作前必须备份** — `voxta.backup_db()` 在修改DB前自动调用
- **模块间无循环依赖** — 所有模块只依赖 config.py
- **tools/ 目录为遗留代码** — 新功能一律在 vam/ 包中实现

## CLI

```bash
python -m vam health      # 全面健康检查
python -m vam report      # 快速文本报告
python -m vam services    # 服务状态
python -m vam signalr     # SignalR连接测试
python -m vam dashboard   # 综合仪表板
python -m vam voxta       # Voxta仪表板
python -m vam scenes      # 场景列表
python -m vam plugins     # 插件概览
python -m vam errors      # 日志错误
python -m vam disk        # 磁盘空间
python -m vam scan        # 完整资源扫描
python -m vam modules     # Voxta模块评估
```

## 六大控制面

1. **Scene JSON** — `scenes.py` SceneBuilder
2. **Voxta SignalR** — `signalr.py` 实时WebSocket通信 (端口5384)
3. **C# Scripter** — `plugins.deploy_script()` 部署脚本
4. **BepInEx** — `plugins.list_bepinex_plugins()` 管理
5. **文件系统** — `resources.py` 全盘扫描
6. **进程管理** — `process.py` 服务启停
