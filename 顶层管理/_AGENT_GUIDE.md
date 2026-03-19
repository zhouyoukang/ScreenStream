# 顶层管理 · Agent操作指令

> 道生一·一生二·二生三·三生万物。Windsurf配置+认知统一管理中枢 v3.0。

## 模块

| 文件 | 用途 | 路由 |
|------|------|------|
| `windsurf_manager.py` | 后端中枢v2.0(19+API+免疫系统+CLI) | :9999 |
| `windsurf_unified.html` | **统一SPA**(配置管理7Tab+认知架构6Tab+免疫系统，可折叠侧边栏) | :9999/ |
| `windsurf_dashboard.html` | 旧版配置管理Dashboard(保留兼容) | :9999/legacy |
| `agent_human_architecture.html` | 独立认知架构页面(保留兼容) | :9999/arch |
| `→Windsurf管理中枢.cmd` | 一键启动 | - |

## 快速命令

```bash
python 顶层管理/windsurf_manager.py              # 启动Hub :9999
python 顶层管理/windsurf_manager.py --status      # CLI全景状态
python 顶层管理/windsurf_manager.py --problems     # 仅显示问题
python 顶层管理/windsurf_manager.py --mcp-fix      # MCP热修复全部
python 顶层管理/windsurf_manager.py --mcp-fix gitee # 修复单个MCP
python 顶层管理/windsurf_manager.py --no-browser   # 不打开浏览器
```

## API端点 (HTTP :9999)

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/` | Dashboard HTML |
| GET | `/api/health` | 健康检查 |
| GET | `/api/overview` | 全景概览(所有配置层) |
| GET | `/api/rules` | Rules列表+内容 |
| GET | `/api/skills` | Skills列表+状态 |
| GET | `/api/workflows` | Workflows列表 |
| GET | `/api/memories` | Memory列表+统计 |
| GET | `/api/mcp` | MCP服务器状态+进程 |
| GET | `/api/hooks` | Hooks配置+验证 |
| GET | `/api/settings` | IDE设置 |
| GET | `/api/problems` | 问题检测 |
| GET | `/api/sync` | 同步检查 |
| GET | `/api/file?path=X` | 读取任意文件内容 |
| GET | `/api/immune` | 免疫系统状态 |
| GET | `/api/immune/cycle` | 触发免疫循环 |
| GET | `/api/immune/memory-health` | Memory健康扫描 |
| GET | `/api/immune/hashes` | 配置文件哈希快照 |
| POST | `/api/mcp/fix` | MCP热修复(toggle+SendKeys) |
| POST | `/api/mcp/refresh` | SendKeys无感刷新 |

## 管理范围 (三层八域)

### Zone 0 — 系统级 (`~/.codeium/windsurf/`)

- `global_rules.md` — 道层元规则(最高权重L1)
- `mcp_config.json` — 6个MCP服务器配置
- `hooks.json` — 系统级钩子(当前为空)
- `memories/` — Protobuf Memory条目（随对话增长）
- `cascade/` — 对话记录
- `user_settings.pb` — 用户设置(82KB Protobuf)

### Zone 1 — 项目级 (`.windsurf/`)

- `.windsurfrules` — 项目根规则入口(v17.1)
- `rules/` — 2个Always-On: kernel.md + protocol.md
- `skills/` — 32个技能(全中文命名)
- `workflows/` — 12个工作流(/命令触发)
- `hooks.json` — 2个Python钩子(conversation_capture)
- `DASHBOARD.md` — 仪表盘

### Zone IDE — 编辑器

- `settings.json` — VS Code设置(proxy/format/augment等)

## 修改规则

- Zone 0文件修改前必须**备份+用户确认**
- MCP热修复使用Python写入(禁PowerShell Set-Content加BOM)
- 禁止直接修改`user_settings.pb`(Protobuf二进制)
- hooks脚本路径变更需同步两处(Zone 0 + Zone 1)

## 变更历史

- v1.0 (2026-03-13): 全景概览/Rules/Skills/Workflows/Memory/MCP/Hooks/Settings
- v2.0: 免疫系统+统一SPA
- v3.0 (2026-03-20): 数字统一审计(32 Skills/12 Workflows)
- v3.1 (2026-03-20): AGENT_GUIDE实测校验(60+个，随项目增长)、DASHBOARD动态发现替代静态列表
