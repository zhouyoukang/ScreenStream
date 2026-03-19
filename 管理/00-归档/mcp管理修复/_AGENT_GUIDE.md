# mcp管理修复 · Agent操作指令

## 目录用途
MCP (Model Context Protocol) 服务器配置管理与故障修复。当前4个活跃MCP: chrome-devtools, context7, github, playwright。

## 关键文件
| 文件 | 用途 |
|------|------|
| `README.md` | 九祸根治知识库 + 标准配置v4 + 铁律 + 监测 |
| `MCP_MAINTENANCE.md` | 完整维护手册(处理流程/架构图/wrapper源码/诊断命令/踩坑记录) |
| `mcp-manager.py` | 运行时MCP管理器(12命令/12模板/九祸修复/无感刷新) |
| `mcp-auth-export.js` | Playwright auth state导出(登录态继承) |
| `github-fallback.ps1` | GitHub MCP降级方案(curl.exe+proxy直调REST API) |

## 配置位置
- `~/.codeium/windsurf/mcp_config.json` — 权威配置(Zone 0)
- `C:\temp\*.cmd` — 4个MCP wrapper脚本(运行时引用)
- `.windsurf\*.cmd` — wrapper脚本源码副本(git tracked)
- `C:\temp\github-proxy-bootstrap.js` — GitHub fetch代理补丁

## Changelog
- 2026-03-08: 伏羲全审计 → 6个问题修复 + github-fallback.ps1 + github-mcp.cmd v3(Clash预检) + 九祸检查完整化
- 2026-03-06: 第九祸(npx超时) → 全局安装+wrapper脚本，配置v3→v4，初始化105秒→<2秒
- 2026-03-05: 第八祸根治(代理干扰CDP)
- 2026-03-04: 第五祸(Playwright icu_util) + GitHub功能验证22/24

## Agent操作规则
- MCP配置属于Zone 0，修改需评估影响→备份→验证
- 优先用`mcp-manager.py`管理，自带无感刷新
- 每增1个MCP≈+3-5%上下文税，遵循☶艮·知止
- MCP包更新后需检查bin入口（见MCP_MAINTENANCE.md §4.4）
