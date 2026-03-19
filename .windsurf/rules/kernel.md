---
trigger: always_on
description: "项目执行内核：注意力锚点、持续推进执行协议、网络代理、凭据、硬约束。Agent执行任何任务时触发（代码/分析/哲学/整合/深度/感受）。"
---

# 内核 (Kernel)

> **法层** — Always-On。道层见 global_rules.md | 术层见 skills/ + workflows/

## 注意力锚点

| 用户信号 | Agent策略 |
|---------|----------|
| 改/加/修/建+具体文件 | 定位→修改→验证 |
| 分析/设计/规划/架构 | 先思考→再读→再设计 |
| 深度/解构/所有/一切 | 综合→洞见→创造 |
| 整合/统一/汇总 | 关键深读→连接→交付 |
| 感受/像水/哲学/审视 | 哲学感受→锚定具体目标→**执行**（分析是步骤非终点） |

**用户信号**：情绪=系统信号（焦虑→加快反馈，信任→自主推进）| 目标分层时先确认长目标不偏，再执行短目标

## 执行协议

- 只读先行(可并行)，写操作串行，同一文件用 `multi_edit`
- 一推到底：持续推进到系统限制 | **分析后必须执行** | 完成一目标后寻找下一可优化项
- 深度任务自主多轮推进。**哲学分析是步骤，代码/文件才是交付**。不提前终止
- **双输出**：A=任务结果 + B=系统进化(重大跨会话发现→写AGENT_GUIDE.md或封装Skill)
- **抗context rot**：长对话(10轮+)重读原始提示词防价值漂移 | 每3转检验是否偏离核心目标

### 网络请求

| 需求 | 工具 |
|------|------|
| 国外网页 | `IWR -Proxy "http://127.0.0.1:7890"` |
| 国内网页 | `IWR` 直连 |
| JS渲染SPA | Playwright `browser_run_code` |
| 库文档 | context7 `query-docs` |
| GitHub | github MCP / `IWR -Proxy` |
| pip/npm/git | 设代理后执行 |

**代理判断**: 需要→github.com/npmjs.org/pypi.org/google.com | 不需要→127.0.0.1/192.168.*/aiotvr.xyz/国内站点

### 故障恢复

工具直接→换方法→脚本委托(.ps1)→告知用户"请做X"

## 项目上下文

冷启动: `list_dir`根目录 → 找到子项目 → `read_file`该项目`AGENT_GUIDE.md` → 获得完整上下文
凭据: `凭据中心.md`(索引) + `secrets.env`(实际值,gitignored) → 使用后**不外泄**
文档入口: `核心架构.md` → `05-文档_docs/FEATURES.md` → `STATUS.md`
ADB: `D:\platform-tools\adb.exe` | 构建: `gradlew assembleFDroidDebug --no-configuration-cache`

## 硬约束

- Zone 0冻结: 禁修改 ~/.codeium/windsurf/ (hooks.json/mcp_config.json)，**唯一例外**: MCP故障修复
- 全局配置修改前: **评估影响→备份→验证**
- 构建串行 | 设备独占 | ADB install/uninstall需用户确认

## 进化律

- 重复模式(>=2次)→封装Skill | 项目知识缺失→写该项目AGENT_GUIDE.md | 工具缺口→建议MCP
- **渐进披露**：Skill=行为智慧(何时/如何)，具体知识(端口/API/配置)→项目AGENT_GUIDE.md
- **知识归AGENT_GUIDE，行为归Skill**——项目知识写该项目AGENT_GUIDE.md，重复行为模式封装Skill。道法术三层自足，无需外部记忆
