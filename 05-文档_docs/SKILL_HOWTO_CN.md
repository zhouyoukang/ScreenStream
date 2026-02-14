# ScreenStream_v2：Skill（技能/Runbook）怎么用（中文说明）

> 目标：让你在开发/排查/合并时，不再“想到哪做到哪”，而是按固定闭环输出可复查证据，并把经验沉淀成可复用的 skill。

## 1) Skill 是什么（你应该怎么理解）

- Skill = **仓库内的可复用工作流（Runbook/Checklist）**。
- Skill 不替代模块化。
  - **模块化（MODULES）**：回答“能力在哪里、入口在哪里”。
  - **Skill**：回答“下次遇到同类事，最稳最快的推进套路是什么”。
- Skill 的核心产物不是“执行动作”，而是：
  - **证据包**（可复查）
  - **验收步骤**（可复现）
  - **归档入口**（不混乱）

Refs：

- `docs/PROCESS.md`
- `docs/TERMINAL_RUNBOOK.md`
- `docs/SKILLS.md`
- `skills/README.md`

## 2) 什么时候用 Skill（触发条件）

优先用 skill 的场景：

- 你准备推进一个功能/改动，但担心漏项、返工、或者路径不清晰。
- 你准备跑终端命令收集证据（diff、日志、端口），不想中途补命令。
- 你在合并 Quest/上游差异，想把差异登记成可审计的清单。

## 3) “按 Skill 推进一次任务”的固定闭环（强制顺序）

对应 `docs/PROCESS.md` 的 6 步闭环：

1. **证据定位**
2. **差异/根因**
3. **方案/ADR（必要时）**
4. **实现**
5. **验收**
6. **归档**（更新 docs 索引 + 清单 + skill）

## 4) 任务包模板（你以后复制粘贴就能用）

把下面这段作为你每次提需求的标准输入（一次性给全）：

```text
【任务名】

【目标】
- 要实现什么（可验收结果）

【当前现象 / 已知信息】
- 你现在看到的行为、错误、截图、日志（原文）

【范围】
- 涉及模块：app/common/mjpeg/input/webrtc/rtsp
- 是否涉及端口/入口/鉴权（如果是：必须准备 ADR 或接受新增 ADR）

【权威入口（你已知的先写）】
- 代码入口：
- 配置入口：
- 文档入口：

【证据包需求】
- 你希望我收集哪些证据（例如：git diff --no-index --stat、端口监听、关键日志）

【终端命令策略】
- 只读命令：允许自动执行
- 写入/构建/联网：必须整组列出后一次确认

【验收】
- 至少 3 条验收步骤（本机/局域网/目标设备）

【归档】
- 需要更新的文档（默认：docs/STATUS + docs/MERGE_ARCHIVE_CHECKLIST，必要时 ADR）
```

## 5) “选哪个 Skill”的最小决策树

- 你要做**证据收集 + 命令分组**：
  - 用 `docs/TERMINAL_RUNBOOK.md`
  - 用 `skills/skill-ssv2-terminal-runbook/`
- 你要做**输入链路/端口/入口统一**：
  - 用 `skills/skill-ssv2-input-unify/`
  - 相关 ADR：`docs/adr/ADR-20260210-input-http-entrypoints.md`
- 你要做**Quest/上游差异合并与登记**：
  - 用 `skills/skill-ssv2-merge-plan/`
  - 清单：`docs/MERGE_ARCHIVE_CHECKLIST.md`
- 你要做**构建/发布/验收不漏项**：
  - 用 `skills/skill-ssv2-release-checklist/`

## 6) 如何从 0 搭建一个新 Skill（落地规则）

### 6.1 最小落地形态

- 新建目录：`ScreenStream_v2/skills/<skill-name>/`
- 新建文件：`SKILL.md`

`SKILL.md` 必备结构：

- 触发条件（triggers）
- 目标（goal）
- Refs（权威入口：docs/代码/配置）
- 护栏（哪些情况必须你确认）
- 步骤（steps）
- 输出与验收（outputs/acceptance）

### 6.2 收敛规则（防混乱）

- 同一类工作流只保留 **1 个权威 skill**；重复内容必须合并。
- Skill 负责“流程与验收”，不负责“偷偷执行高风险动作”。
- 只要涉及：端口/入口/鉴权/对外协议
  - **先写 ADR，再写 Skill**（Skill 引用 ADR）

## 7) 示例：用 Skill 推进一次“功能开发”（范式演示）

以“输入链路统一”为例（仅示范套路，不重复实现细节）：

- 选 skill：`skills/skill-ssv2-input-unify/`
- 证据包：
  - `mjpeg/.../HttpServer.kt`、`input/.../InputHttpServer.kt`、Web UI `index.html`
  - `git diff --no-index --stat -- ScreenStream_Quest/input/src ScreenStream_v2/input/src`
- 决策：端口/入口策略写 ADR：`docs/adr/ADR-20260210-input-http-entrypoints.md`
- 实现：统一路由（共享 `installInputRoutes()`）
- 验收：同源入口可用 + 兼容端口可选 + 行为一致
- 归档：更新 `docs/STATUS.md`、`docs/MERGE_ARCHIVE_CHECKLIST.md`，必要时补 skill 验收段落

---

如果你后续给我“某个功能要怎么做”，你只要按第 4 节的任务包模板把信息一次性填满，我就会按这个闭环推进，并把最终产物收敛回 docs/skills。
