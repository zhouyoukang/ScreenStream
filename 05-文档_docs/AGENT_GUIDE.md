# 05-文档_docs Agent指令

**角色**: ScreenStream项目核心文档中心

## 文档入口顺序

1. `../核心架构.md` — 核心架构(顶层)
2. `FEATURES.md` — 功能清单(150+功能)
3. `../STATUS.md` — 项目状态
4. `MODULES.md` — 模块说明
5. `ARCHITECTURE_v32.md` — 架构文档v32

## 重要文档

| 文件 | 内容 |
|------|------|
| `FEATURES.md` | 150+功能 · 118+API · 10面板 |
| `ARCHITECTURE_v32.md` | 架构设计文档 |
| `COMPETITIVE_ANALYSIS.md` | 竞品分析 |
| `BROWSER_MCP_MULTI_AGENT_RESEARCH.md` | 浏览器MCP多Agent研究 |
| `TERMINAL_FREEZE_DEEP_DIVE_v2.md` | 终端冻结深度分析 |
| `TERMINAL_FREEZE_ULTIMATE_SOLUTION.md` | 终端冻结终极方案 |
| `MULTI_AGENT_TERMINAL_FREEZE_DIAGNOSIS.md` | 多Agent终端冻结诊断 |
| `WINDSURF_ARCHITECTURE_DEEP_DIVE.md` | Windsurf架构逆向 |
| `adr/` | 架构决策记录(ADR) |

## ADR (Architecture Decision Records)

| ADR | 决策 |
|-----|------|
| `ADR-20260210-input-http-entrypoints.md` | Input模块HTTP入口设计 |

## 约束

- 文档变更需同步更新关联文档(交叉引用)
- 权威入口顺序: `核心架构.md` → `FEATURES.md` → `STATUS.md` → `MODULES.md`
- 禁止在文档中写入实际凭据(用`[见secrets.env]`替代)
