# 阿里云服务器 (AliyunECS)

> **基础设施目录** — 阿里云轻量服务器的部署脚本、配置模板、运维文档。

## 项目边界

| 维度 | 值 |
|------|-----|
| **目录** | `阿里云服务器/` |
| **性质** | 基础设施（部署脚本+配置+文档） |
| **核心入口** | `README.md`（唯一权威指南） |
| **服务器** | 60.205.171.100 (阿里云轻量2核2G) |

## 可修改文件

```
阿里云服务器/
├── README.md              ← 精华指南（一站式）
├── AGENTS.md              ← 本文件
├── frps-setup.sh          ← ECS上FRP Server安装
├── frpc.example.toml      ← FRP Client配置模板
├── install-frpc.ps1       ← FRP Client开机自启
├── xrdp-setup.sh          ← ECS上xrdp+XFCE桌面安装
├── deploy-xrdp.ps1        ← 从Windows远程部署xrdp
└── secrets.toml           ← 敏感信息（gitignored）
```

## 禁止修改

- ScreenStream 所有目录（用户界面/投屏链路/反向控制/基础设施/配置管理）
- `远程桌面/remote_agent.py`（被控端代码，归远程桌面目录管理）
- `远程桌面/remote_desktop.html`（前端代码）
- `.windsurf/` 配置文件

## 安全红线

- **secrets.toml 绝对不提交到git**（已gitignore）
- 脚本中不硬编码密码（用参数/环境变量/配置文件）
- 修改安全组规则前评估影响

## 与其他目录的关系

| 目录 | 关系 | 说明 |
|------|------|------|
| `远程桌面/` | 被控端代码 | remote_agent.py 通过FRP暴露到公网 |
| `远程桌面/frp/` | **已废弃** | 旧FRP配置，用本目录替代 |
| `构建部署/` | 部分废弃 | linux-remote-desktop-setup.sh 等已迁移到此 |
| `双电脑互联/` | 知识索引 | 全景文档含阿里云部分 |

## 运行位置标注

| 脚本 | 运行在 | 说明 |
|------|--------|------|
| `frps-setup.sh` | **阿里云ECS** | SSH到ECS后执行 |
| `xrdp-setup.sh` | **阿里云ECS** | SSH到ECS后执行 |
| `install-frpc.ps1` | **本地Windows** | 管理员运行一次 |
| `deploy-xrdp.ps1` | **本地Windows** | 自动SSH上传+执行 |

## 对话结束选项

> 任务完成后调用 `ask_user_question`，从下表选 4 个最贴合的：

| label | description |
|-------|-------------|
| SSH连上看看 | SSH到阿里云，检查服务状态 |
| 部署FRP | 执行frps-setup.sh安装FRP Server |
| 装Linux桌面 | 一键部署xrdp+XFCE到阿里云 |
| 测试穿透 | 验证FRP穿透是否正常工作 |
| 加固安全 | TLS+fail2ban+安全组限IP |
| 收工提交 | 记录成果 + git commit |
