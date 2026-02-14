# ScreenStream_v2 Skills（研发工作流）

> Skills = 仓库内 Runbook/Checklist/可复用工作流（不引入平台、不进入 App 运行时）。

使用说明（中文）：`docs/SKILL_HOWTO_CN.md`

## 0) 与模块化的关系

- **模块（MODULES）**：回答“系统能力在哪里”。
- **ADR**：回答“为什么这样选”。
- **Skills**：回答“下次再做同类事，按什么步骤做最稳、最快、不漏项”。

## 1) 目录结构

- 入口：`ScreenStream_v2/skills/README.md`
- 规范：每个技能一个目录：
  - `skills/<skill-name>/SKILL.md`

## 2) 当前已落地的 skills

- `skills/skill-ssv2-input-unify/`：输入链路收敛（端口/入口/路由/兼容/验收）
- `skills/skill-ssv2-merge-plan/`：Quest/上游差异合并与归档清单维护
- `skills/skill-ssv2-release-checklist/`：构建/发布/验收 checklist

- `skills/skill-ssv2-terminal-runbook/`：终端命令执行 Runbook（命令分组/风险分级/一次性确认）

## 3) 什么时候新增一个 skill

- 你发现自己在重复做同一类事（入口定位、差异清单、发版漏项、端口冲突复盘）
- 你希望以后“只按文档跑一遍就能完成”，而不是每次重新思考

## 4) 护栏

- Skills 里只固化流程与验收，不做隐式高风险操作。
- 涉及端口/入口/鉴权的变更必须先 ADR。
