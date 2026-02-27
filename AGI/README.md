# AGI — 智能体系管理中心

> **一处观之，一处管之，以至于无感。**

## 启动仪表盘

```powershell
python AGI/dashboard-server.py
# → http://localhost:9090
```

## 三层架构

```
Zone 0 — 全局级（~/.codeium/windsurf/）
 ├── 全局规则 (88行)        memories/global_rules.md
 ├── MCP配置 (5 Server)     mcp_config.json
 ├── 全局Hooks (已清空)     hooks.json
 ├── 全局Skills (13个)      skills/
 └── IDE Settings           Windsurf/User/settings.json

Zone 1 — 项目级（.windsurf/）
 ├── Rules (6)              rules/
 ├── Skills (13)            skills/
 ├── Workflows (10)         workflows/
 └── Hooks (2 Python)       hooks.json

Zone 2 — 目录级
 └── AGENTS.md × 17         各目录
```

## 快捷操作

| 需求 | 方式 |
|------|------|
| **看全景** | `python AGI/dashboard-server.py` → 浏览器 |
| **看Markdown版** | 打开 `.windsurf/DASHBOARD.md` |
| **看Skills详情** | 打开 `.windsurf/skills/README.md` |
| **开发新功能** | 对话中输入 `/dev` |
| **系统体检** | `/health-check` |
| **进化升级** | `/evolve` |

## 文件说明

| 文件 | 用途 |
|------|------|
| `dashboard-server.py` | Web仪表盘服务器（:9090） |
| `README.md` | 本文件（入口指南） |
| `AGENTS.md` | AGI目录级Agent指令 |
