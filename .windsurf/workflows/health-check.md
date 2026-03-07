---
description: 系统健康检查：检测规则/配置/Skills是否完整，发现缺失自动恢复。IDE重启后、新对话开始时触发。
---

# 系统健康自检工作流

当用户说 /health-check 或 AI 怀疑配置可能不完整时，按以下步骤执行。

## Phase 1: 关键文件存在性检查

使用 `find_by_name` 和 `read_file` 验证以下文件是否存在且内容非空：

### 1.1 全局配置（跨所有项目）
// turbo
- `~/.codeium/windsurf/memories/global_rules.md` — 全局规则（AI 可直接编辑恢复）
- `~/.codeium/windsurf/hooks.json` — 必须为 `{"hooks": {}}` 或不存在（禁止含 PowerShell 钩子）

### 1.2 项目规则（.windsurf/rules/）
// turbo
检查以下 6 个规则文件是否存在：
- `.windsurf/rules/soul.md` — AI 思维内核
- `.windsurf/rules/project-structure.md` — 项目结构
- `.windsurf/rules/execution-engine.md` — 执行引擎
- `.windsurf/rules/kotlin-android.md` — Kotlin/Android 规则
- `.windsurf/rules/frontend-html.md` — 前端规则
- `.windsurf/rules/build-deploy.md` — 构建部署规则

### 1.3 项目 Skills（.windsurf/skills/）
// turbo
检查以下 5 个 Skill 是否存在：
- `.windsurf/skills/build-and-deploy/SKILL.md`
- `.windsurf/skills/keyboard-input-debug/SKILL.md`
- `.windsurf/skills/api-testing/SKILL.md`
- `.windsurf/skills/new-module-setup/SKILL.md`
- `.windsurf/skills/adb-device-debug/SKILL.md`

### 1.4 工作流（.windsurf/workflows/）
// turbo
- `.windsurf/workflows/debug-escalation.md`
- `.windsurf/workflows/review.md`
- `.windsurf/workflows/health-check.md`（本文件）

### 1.5 AGENTS.md（8 个目录）
// turbo
- 根目录 `AGENTS.md`
- `010-用户界面与交互_UI/AGENTS.md`
- `020-投屏链路_Streaming/AGENTS.md`
- `020-投屏链路_Streaming/010-MJPEG投屏_MJPEG/AGENTS.md`
- `020-投屏链路_Streaming/020-RTSP投屏_RTSP/AGENTS.md`
- `020-投屏链路_Streaming/030-WebRTC投屏_WebRTC/AGENTS.md`
- `040-反向控制_Input/AGENTS.md`
- `070-基础设施_Infrastructure/AGENTS.md`

### 1.6 关键代码文件
// turbo
- `.windsurf/hooks.json` — 必须为空 hooks（`{"hooks": {}}`)

## Phase 2: 内容完整性验证

对关键文件做内容抽检：

1. **global_rules.md** — 必须包含 `TASK_POOL_RULES_START` 标记和 `PREDICT` 框架
2. **soul.md** — 必须包含 `ESCALATION` 四层升级
3. **execution-engine.md** — 必须包含"禁止hooks.json中放PowerShell钩子"
4. **hooks.json（项目级）** — 必须为空 hooks，不含 `powershell` 或 `pre_run_command`

## Phase 3: 缺失文件恢复

如果发现缺失：

### 3.1 全局规则缺失
- 从 Memory 中搜索 `global_rules` 相关记忆获取路径和内容指引
- 从备份 `e:\windsurf-intelligence-pack\global-rules\GLOBAL_RULES.md` 恢复
- 直接写入 `~/.codeium/windsurf/memories/global_rules.md`

### 3.2 项目规则缺失
- 从备份 `.windsurf/backups/rules/` 恢复（如果备份存在）
- 从升级包 `e:\windsurf-intelligence-pack\project-templates/` 恢复
- 从 Memory 中搜索相关规则内容恢复

### 3.3 Skills 缺失
- 从全局 Skills 模板 `~/.codeium/windsurf/skills/project-init/templates/` 恢复
- 或从升级包恢复

### 3.4 hooks.json 被污染
- 立即清空为 `{"hooks": {}}`
- 用 `create_memory` 记录此事件

## Phase 4: 输出健康报告

以表格形式输出检查结果：

```
| 类别 | 文件数 | 状态 | 缺失项 |
|------|--------|------|--------|
| 全局规则 | 1/1 | ✅ | - |
| 项目规则 | 6/6 | ✅ | - |
| Skills | 5/5 | ✅ | - |
| 工作流 | 3/3 | ✅ | - |
| AGENTS.md | 8/8 | ✅ | - |
| hooks.json | 安全 | ✅ | - |
```

如果有任何 ❌，说明缺失项并提供恢复方案。
