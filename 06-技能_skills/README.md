# ScreenStream_v2 skills（可复用工作流入口）

> 这里的 skills 只做一件事：把高频、易漏项的推进套路固化为 Runbook/Checklist。

## 0) 目录约定

- 每个 skill 一个目录：`skills/<skill-name>/SKILL.md`
- `SKILL.md` 应包含：触发条件、目标、refs、护栏、步骤、输出与验收。

## 1) 当前 skills

- `skill-ssv2-input-unify`：输入链路收敛
- `skill-ssv2-merge-plan`：合并/归档清单维护
- `skill-ssv2-release-checklist`：构建/发布/验收清单

- `skill-ssv2-terminal-runbook`：终端命令执行 Runbook（命令分组/风险分级/一次性确认）

## 2) 新增 skill 的规则

- 先写 Markdown（先可用），后续再考虑脚本化。
- 涉及端口/入口/鉴权等架构级决策，必须先写 ADR。

## 3) 与 docs 的关系

- docs 权威入口：`docs/README.md`
- skills 总览：`docs/SKILLS.md`
