---
description: 管理和维护Windsurf配置（MCP/Rules/Skills/Workflows）。当需要检查、修复、优化Windsurf环境、诊断MCP问题、或管理凭据时自动触发。
---

# Windsurf配置管理 Skill

## 何时触发
- 用户提到MCP、Rules、Skills、Workflows配置问题
- 需要检查Windsurf环境健康状态
- MCP服务器异常（禁用/进程死亡/CMD缺失）
- 需要管理凭据（secrets.env）
- 需要创建/修改Skills或Workflows

## 核心工具：安全管理中枢 (:9877)

### 快速诊断
```python
# 全景健康
curl http://127.0.0.1:9877/api/health

# Windsurf配置全景（MCP+Rules+Skills+Workflows+Hooks+变更历史）
curl http://127.0.0.1:9877/api/windsurf

# 问题检测（MCP禁用/进程死亡/CMD缺失/Hook缺失/DASHBOARD过时）
curl http://127.0.0.1:9877/api/problems

# 配置变更历史（文件监视器实时检测）
curl http://127.0.0.1:9877/api/changes

# MCP状态（配置+进程PID）
curl http://127.0.0.1:9877/api/mcp
```

### 凭据操作
```python
# 获取单个凭据
curl http://127.0.0.1:9877/api/get?key=KEY_NAME

# 批量获取
curl http://127.0.0.1:9877/api/batch?keys=KEY1,KEY2

# 搜索
curl http://127.0.0.1:9877/api/search?q=password
```

## MCP修复流程
1. `GET /api/problems` 获取问题列表
2. 对于disabled MCP：在Windsurf MCP面板中toggle开关
3. 对于进程死亡：重启Windsurf或手动启动CMD
4. chrome-devtools始终需要用户UI toggle（Windsurf内部状态限制）

## 文件监视器
Hub自动监视5路配置文件变化（每5秒）：
- `secrets.env` → 自动重载+Toast通知
- `~/.codeium/windsurf/mcp_config.json` → Toast通知
- `.windsurf/rules/` → Toast通知
- `.windsurf/skills/` → 计数变化Toast
- `.windsurf/workflows/` → 计数变化Toast

## 关键路径
| 配置 | 路径 |
|------|------|
| 凭据 | `secrets.env` (项目根, gitignored) |
| 凭据索引 | `凭据中心.md` |
| MCP配置 | `~/.codeium/windsurf/mcp_config.json` |
| Global Rules | `~/.codeium/windsurf/memories/global_rules.md` |
| Rules | `.windsurf/rules/` (kernel.md, protocol.md) |
| Skills | `.windsurf/skills/` |
| Workflows | `.windsurf/workflows/` |
| Hooks | `.windsurf/hooks.json` |
| Hub | `安全管理/security_hub.py` (:9877) |
| Dashboard | http://127.0.0.1:9877/ |

## 硬约束
- **Zone 0冻结**: 禁修改 `~/.codeium/windsurf/` 中的 hooks.json/mcp_config.json，唯一例外=MCP故障修复
- Skills/Workflows创建在 `.windsurf/skills/` 和 `.windsurf/workflows/`
- 凭据永远不写入git tracked文件
