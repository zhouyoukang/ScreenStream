# Multi-Agent Communication System

> 让一个人通过一个网页，同时指挥多个 AI Agent 并行工作。

## 架构

```
Agent 回复 → bridge.bat --ask → POST /api/request → Dashboard (:9901)
                                                          ↓
                                    人在网页回复（选项/输入/粘贴图片/拖拽文件）
                                                          ↓
                              bridge 收到 JSON → Agent 继续执行
```

## 文件结构

```
agent-comm/
├── config.json                  ← 集中配置（端口/token/超时）
├── start.bat                    ← 一键启动 Dashboard
├── core/
│   ├── dashboard.py             ← HTTP服务 + Web UI（959行，零依赖）
│   ├── bridge_agent.py          ← CLI通信客户端（7种模式）
│   └── bridge.bat               ← 入口wrapper（自动检测Python）
└── config/
    └── agent_rules_template.md  ← Agent PRIORITY RULE 模板
```

## 快速启动

```powershell
# 1. 启动 Dashboard（双击 start.bat 或命令行）
python agent-comm/core/dashboard.py
# 浏览器打开 http://127.0.0.1:9901

# 2. 部署 Agent 规则
#    复制 config/agent_rules_template.md 内容
#    替换 <BRIDGE_PATH> 为实际路径
#    写入 ~/.codeium/windsurf/memories/global_rules.md

# 3. 重启 IDE，Agent 每次回复自动调用 bridge
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | Dashboard 网页 |
| GET | `/api/health` | 健康检查 |
| GET | `/api/pending` | 待处理请求 |
| GET | `/api/wait/{id}?timeout=N` | Long-poll 等待回复 |
| GET | `/api/statuses` | Agent 状态 |
| GET | `/api/history` | 历史记录 |
| GET | `/api/activities` | 活动流 |
| POST | `/api/request` | 提交请求 |
| POST | `/api/respond/{id}` | 回复请求 |
| POST | `/api/cancel/{id}` | 取消请求 |
| POST | `/api/status` | 上报状态 |
| POST | `/api/activity` | 上报活动 |
| POST | `/api/instruct` | 下发指令 |

## 认证

`config.json` 中 `auth_token` 非空时启用。CLI 自动附加 `X-Auth-Token` header，浏览器免认证。

## 远程 Agent 部署

1. 复制 `core/bridge_agent.py` + `core/bridge.bat` 到远程机器
2. 创建 `config.json`，`connect_host` 填 Dashboard 主机 IP
3. 按 `config/agent_rules_template.md` 部署规则
4. 重启远程 IDE

## config.json

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `dashboard.bind_host` | 服务监听地址 | `0.0.0.0` |
| `dashboard.connect_host` | 客户端连接地址 | `127.0.0.1` |
| `dashboard.port` | 端口 | `9901` |
| `dashboard.auth_token` | 认证token | `agent-comm-2026` |
| `bridge.timeout_seconds` | 等待超时 | `86400` (24h) |
| `bridge.auto_continue_message` | 超时自动回复 | `继续` |

## 与 windsurf-cunzhi 的关系

| | windsurf-cunzhi.exe | agent-comm |
|--|---------------------|------------|
| 场景 | 单Agent快速交互 | 多Agent集中管控 |
| 界面 | 原生GUI弹窗 | Web浏览器 |
| 网络 | 无需 | HTTP |
| 远程 | 不支持 | 支持跨机器 |

两者互补：单Agent用cunzhi，多Agent并行用agent-comm。

## 设计决策

| 决策 | 理由 |
|------|------|
| HTTP + Long-polling | 跨Session/跨机器，零依赖 |
| HTML 内嵌 Python | 单文件部署 |
| PRIORITY RULE 注入 | 无法改IDE源码，规则文件控制Agent |
| 超时自动继续 | Agent不因人离开而阻塞 |
| bind/connect 分离 | 服务端0.0.0.0，客户端连具体IP |
