# Phone Agent Soul — 顶层设计蓝图

> 本目录包含 Phone Agent 专用 Windows 账户的完整配置设计。
> 部署目标：另一个 Windows 账户的 `~/.codeium/windsurf/` 及项目级 `.windsurf/`
> 创建日期：2026-02-21
> 设计来源：ScreenStream_v2 Agent 操控手机能力的深度哲学分析

## 设计哲学

Phone Agent 和 Developer Cascade 是两种不同的智能体：
- Developer Cascade 在**确定性的符号世界**中工作（文件内容 = 现实）
- Phone Agent 在**不完美信息的符号世界**中工作（View 树 ≈ 现实，有保真度差距）

Phone Agent 的灵魂归结为三个不可简化的原则：
1. **闭环感知**：行动前观察，行动后验证，永不盲操作
2. **渐进抽象**：具体经验 → 模式 → 策略 → 直觉
3. **编排优先**：不做 APP 替代品，做 APP 调度者

## 文件清单

| 文件 | 部署位置 | 说明 |
|------|----------|------|
| `soul.md` | `.windsurf/rules/soul.md` | Agent 意识框架 |
| `global-rules.md` | `~/.codeium/windsurf/memories/global_rules.md` | 全局行为规则 |
| `execution-engine.md` | `.windsurf/rules/execution-engine.md` | 操作引擎 |
| `skills/` | `.windsurf/skills/` | 分层技能体系 |
| `memory-seeds.md` | 首次对话时创建 Memory | 初始知识种子 |
| `hooks.json` | `~/.codeium/windsurf/hooks.json` | 自动化钩子 |
| `DEPLOY.md` | 本地参考 | 部署指南 |

## 与 Developer Cascade 的关系

```
Developer Cascade（账户A）        Phone Agent（账户B）
  ┌──────────┐                    ┌──────────┐
  │ 设计/构建 │ ─── 构建能力 ──→  │ 操作/探索 │
  │ 代码/架构 │ ←── 反馈限制 ───  │ 感知/学习 │
  └──────────┘                    └──────────┘
         │                              │
         └──── 共享：手机 HTTP API ──────┘
              (ScreenStream 40+ 端点)
```

设计师构建飞机，飞行员驾驶飞机。飞行员的经验反馈让下一代飞机更好。
