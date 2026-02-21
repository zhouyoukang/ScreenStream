# Multi-Agent Communication System

> 让一个人通过一个网页，同时指挥多个 AI Agent 并行工作。

## 架构

```
Agent 生成回复
    ↓ (PRIORITY RULE 强制)
bridge.bat --ask --message "摘要" --options "选项"
    ↓
bridge_agent.py → POST /api/request → Dashboard (:9901)
    ↓
Dashboard 显示请求卡片（声音+系统通知）
    ↓
人在 Dashboard 回复（点选项 / 输入 / 粘贴图片）
    ↓
bridge_agent.py 收到 JSON → 返回给 Agent → Agent 继续执行
```

## 文件结构

```
agent-comm/
├── README.md                    ← 本文件
├── config.json                  ← 集中配置（端口/token/超时）
├── .gitignore
├── start.bat                    ← 一键启动 Dashboard
├── setup_agent.bat              ← 一键为新 Agent 部署规则
├── core/
│   ├── dashboard.py             ← HTTP服务 + Web UI（零依赖）
│   ├── bridge_agent.py          ← CLI通信客户端（7种模式）
│   └── bridge.bat               ← 入口wrapper（自动检测Python）
└── config/
    └── agent_rules_template.md  ← Agent PRIORITY RULE 模板
```

## 快速启动

### 1. 配置
编辑 `config.json`，按需修改端口和 auth token。

### 2. 启动 Dashboard
```powershell
# 方式一：双击 start.bat
# 方式二：命令行
python agent-comm/core/dashboard.py
# 浏览器打开 http://127.0.0.1:9901
```

### 3. 部署 Agent 规则
1. 复制 `config/agent_rules_template.md` 的内容
2. 将 `<BRIDGE_PATH>` 替换为实际路径
3. 写入目标 Agent 的 `global_rules.md`（如 `~/.codeium/windsurf/memories/global_rules.md`）

### 4. 重启目标 Agent 的 IDE
Agent 将在每次回复时自动调用 bridge，请求出现在 Dashboard。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | Dashboard 网页 |
| GET | `/api/health` | 健康检查 |
| GET | `/api/pending` | 获取待处理请求 |
| GET | `/api/wait/{id}?timeout=N` | Long-poll 等待回复 |
| GET | `/api/statuses` | 所有 Agent 状态 |
| GET | `/api/history` | 历史交互记录 |
| POST | `/api/request` | 提交新请求 |
| POST | `/api/respond/{id}` | 回复请求 |
| POST | `/api/cancel/{id}` | 取消请求 |
| POST | `/api/status` | 上报 Agent 状态 |
| POST | `/api/activity` | 上报活动事件 |
| GET | `/api/activities` | 获取活动流 |
| POST | `/api/instruct` | 下发指令给 Agent |

## 认证

`config.json` 中的 `auth_token` 非空时启用 token 认证。
- CLI 客户端自动附加 `X-Auth-Token` header
- 浏览器 Dashboard 页面免认证访问
- API 调用需要 header 或 `?token=xxx` query param

## 远程 Agent 部署

将 `remote-deploy/` 文件夹复制到远程 Windows 机器，运行 `setup.bat` 即可连接到中央 Dashboard。

### 前置条件
- 远程机器已安装 Python 3.8+ 且在 PATH 中
- 网络可达 Dashboard 主机（默认 `192.168.10.219:9901`）

### 步骤
1. 复制 `remote-deploy/` 到远程机器
2. 编辑 `config.json` 中的 `connect_host` 为 Dashboard 主机 IP
3. 双击 `setup.bat`
4. 重启远程机器的 Windsurf IDE

### config.json 关键字段

| 字段 | 说明 |
|------|------|
| `bind_host` | Dashboard 服务监听地址（`0.0.0.0` = 所有接口） |
| `connect_host` | 客户端连接地址（填 Dashboard 主机的局域网 IP） |
| `auth_token` | API 认证 token（主机和远程必须一致） |

## 设计决策

| 决策 | 理由 |
|------|------|
| HTTP + Long-polling | 跨 Windows Session / 跨机器可达，零依赖 |
| HTML 内嵌 Python | 零文件部署，单命令启动 |
| PRIORITY RULE 注入 | 无法修改 IDE 源码，通过规则文件控制 Agent 行为 |
| 超时自动继续 | Agent 不会因为人不在而永久阻塞 |
| JSON 文件持久化 | 简单可靠，Dashboard 重启后恢复历史 |
| bind/connect 分离 | 服务端绑定 0.0.0.0，客户端连具体 IP |
