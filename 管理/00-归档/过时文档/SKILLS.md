# ScreenStream_v2 Skills（技能体系）

> 版本：v32+ | 更新：2026-02-21
> Skills = 可复用的标准化工作流，把经验固化为可重复执行的流程。

## 核心哲学

**技能三定律**：
1. **可复现** — 任何人按 SKILL.md 执行，结果一致
2. **不遗漏** — 关键步骤和验收条件完整列出，防止跳步
3. **可演进** — 每次执行后发现改进点，回写到 SKILL.md

**深层认知**：Skills 不是文档，而是**组织智慧的结晶体**——
把个人脑中的隐性知识转化为团队/AI可执行的显性流程。

## 与其他体系的关系

| 体系 | 回答的问题 | 产物 |
|------|-----------|------|
| **MODULES** | 能力在哪里？入口在哪里？ | 索引表 |
| **ADR** | 为什么这样选？ | 决策记录 |
| **Skills** | 下次怎么做最快最稳？ | 标准流程 |
| **Workflows** | IDE 工作流怎么触发？ | 斜杠命令 |

## 当前技能清单（9个）

| 技能 | 目录 | 触发场景 |
|------|------|---------|
| **build-and-deploy** | `.windsurf/skills/build-and-deploy/` | 构建APK→推送→安装→启动 |
| **keyboard-input-debug** | `.windsurf/skills/keyboard-input-debug/` | 键盘输入映射/keysym/Accessibility调试 |
| **api-testing** | `.windsurf/skills/api-testing/` | API端点验证/健康检查/HTTP调试 |
| **new-module-setup** | `.windsurf/skills/new-module-setup/` | 新模块/子功能目录创建 |
| **adb-device-debug** | `.windsurf/skills/adb-device-debug/` | 设备连接/ADB/日志调试 |
| **feature-development** | `.windsurf/skills/feature-development/` | 新功能完整开发流程 |
| **full-verification** | `.windsurf/skills/full-verification/` | 编译→推送→安装→启动→API→日志 |
| **agent-phone-control** | `.windsurf/skills/agent-phone-control/` | Agent手机控制 |
| **requirement-decompose** | `.windsurf/skills/requirement-decompose/` | 顶层需求→结构化特性列表 |

## 何时新增 Skill

触发条件（满足任意2条）：
- 同类操作重复 ≥ 2 次
- 步骤 > 5 步且容易遗漏
- 涉及跨模块协调
- 需要特定顺序执行

## 护栏

- Skills 只固化流程与验收，不做隐式高风险操作
- 涉及端口/入口/鉴权 → 先写 ADR，再写 Skill
- 同一类工作流只保留 1 个权威 Skill，禁止重复

## 参考

- 使用说明：`05-文档_docs/SKILL_HOWTO_CN.md`
- 标准流程：`05-文档_docs/PROCESS.md`
- IDE 工作流：`.windsurf/workflows/`（9个斜杠命令）
