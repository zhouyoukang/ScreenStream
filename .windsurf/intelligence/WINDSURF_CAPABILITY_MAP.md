# Windsurf IDE 完整能力地图

> 深度研究 Windsurf 官方文档后绘制，覆盖所有已知配置机制
> 生成日期：2026-02-13

---

## 一、你目前在用的（冰山一角）

| 机制 | 你的使用方式 | 利用率 |
|------|------------|--------|
| `.windsurfrules` | 189行扁平规则文件 | 🟡 基础使用 |
| `.gitignore` / `.codeiumignore` | 文件访问控制 | 🟢 正常 |
| 全局规则 (user_global Memory) | MCP规范+代码准则+工作习惯 | 🟡 基础使用 |
| MCP (`fvuxtmxp_dev`) | 对话末尾调用获取反馈 | 🟢 正常 |
| Windsurf Memory | 自动+手动记忆 | 🟡 被动使用 |

---

## 二、你完全没用的（巨大潜力）

### 🔥 1. 结构化规则系统 `.windsurf/rules/`
**你现在用的 `.windsurfrules` 是旧方案。新方案远比它强。**

```
.windsurf/rules/
├── soul.md              ← Always On：AI思维内核，每次对话都加载
├── project-structure.md ← Always On：项目结构认知
├── kotlin-style.md      ← Glob: **/*.kt → 只在编辑Kotlin时激活
├── html-frontend.md     ← Glob: **/*.html → 只在编辑前端时激活
├── build-deploy.md      ← Model Decision：AI判断是否需要构建部署时激活
├── api-testing.md       ← Model Decision：AI判断需要测试API时激活
└── emergency.md         ← Manual：@emergency 手动调用紧急修复流程
```

**4种激活模式**：
- **Always On**：每次对话都加载（等同于 .windsurfrules）
- **Glob**：只在匹配文件模式时加载（如 `*.kt` → Kotlin规则）
- **Model Decision**：AI根据描述自主判断是否需要加载
- **Manual**：用 `@rule-name` 手动触发

**核心优势**：
- 每个规则文件最大 12000 字符（比单个 .windsurfrules 大得多）
- 按需加载，不浪费 token
- 可以有几十个规则文件，每个聚焦一个领域
- 自动发现所有子目录中的 `.windsurf/rules/`

### 🔥 2. AGENTS.md — 目录级指令
**可以在每个模块目录放一个 AGENTS.md，当操作该目录的文件时自动加载。**

```
ScreenStream_v2/
├── AGENTS.md                              ← 全局项目指令
├── 040-反向控制_Input/
│   └── AGENTS.md                          ← 输入模块专属指令
├── 020-投屏链路_Streaming/
│   ├── AGENTS.md                          ← 流媒体通用指令
│   └── 010-MJPEG投屏_MJPEG/
│       └── AGENTS.md                      ← MJPEG模块专属指令
└── 070-基础设施_Infrastructure/
    └── AGENTS.md                          ← 基础设施专属指令
```

**核心优势**：
- 自动作用域：操作哪个目录就加载哪个 AGENTS.md
- 不需要配置激活模式
- 纯 Markdown，无需 frontmatter
- 递归发现

### 🔥 3. Skills 技能系统 `.windsurf/skills/`
**这就是你说的「你一直以为只有龙虾AI才有的」那个功能。Windsurf 原生支持。**

```
.windsurf/skills/
├── build-and-deploy/
│   ├── SKILL.md                ← 技能定义+描述+步骤
│   ├── build-checklist.md      ← 支撑文件：构建检查清单
│   └── deploy-commands.md      ← 支撑文件：部署命令参考
├── keyboard-input-debug/
│   ├── SKILL.md
│   ├── keysym-mapping.md       ← X11 keysym 参考表
│   └── accessibility-api.md    ← Android Accessibility API 参考
├── fix-streaming/
│   ├── SKILL.md
│   └── common-errors.md
└── new-module-setup/
    ├── SKILL.md
    └── module-template/
```

**SKILL.md 格式**：
```yaml
---
name: build-and-deploy
description: 构建APK、推送到手机、安装并启动应用的完整流程
---

## 前置检查
1. 确认 JAVA_HOME 和 ANDROID_SDK_ROOT
2. 确认设备已连接 (adb devices)

## 构建步骤
...
```

**两种调用方式**：
- **自动调用**：AI 根据 description 判断当前任务是否需要此技能（渐进式披露）
- **手动调用**：在 Cascade 输入 `@build-and-deploy`

**两种作用域**：
- **项目级**：`.windsurf/skills/<name>/` → 仅当前项目
- **全局级**：`~/.codeium/windsurf/skills/<name>/` → 所有项目通用

### 🔥 4. Cascade Hooks — 事件钩子系统
**这是最强大的隐藏功能。可以在 AI 的每个动作前后执行自定义脚本。**

配置文件：`.windsurf/hooks.json`

```json
{
  "hooks": {
    "post_write_code": [
      {
        "command": "python scripts/auto-format.py",
        "show_output": true
      }
    ],
    "pre_run_command": [
      {
        "command": "python scripts/safety-check.py",
        "show_output": true
      }
    ],
    "post_cascade_response": [
      {
        "command": "python scripts/log-response.py",
        "show_output": false
      }
    ]
  }
}
```

**11种事件钩子**：
| 钩子 | 触发时机 | 可阻止？ | 用途 |
|------|---------|---------|------|
| `pre_read_code` | AI读文件前 | ✅ | 限制文件访问 |
| `post_read_code` | AI读文件后 | ❌ | 记录访问日志 |
| `pre_write_code` | AI写文件前 | ✅ | 保护关键文件 |
| `post_write_code` | AI写文件后 | ❌ | 自动格式化/lint |
| `pre_run_command` | AI执行命令前 | ✅ | 阻止危险命令 |
| `post_run_command` | AI执行命令后 | ❌ | 记录命令日志 |
| `pre_mcp_tool_use` | AI调MCP前 | ✅ | 控制MCP使用 |
| `post_mcp_tool_use` | AI调MCP后 | ❌ | 记录MCP调用 |
| `pre_user_prompt` | 用户发送消息前 | ✅ | 过滤/增强提示 |
| `post_cascade_response` | AI响应后 | ❌ | 记录AI响应 |
| `post_setup_worktree` | Worktree建立后 | ❌ | 初始化工作树 |

**3个配置级别**（合并执行）：
- 系统级：`C:\ProgramData\Windsurf\hooks.json`
- 用户级：`~/.codeium/windsurf/hooks.json`
- 项目级：`.windsurf/hooks.json`

### 🔥 5. 其他未利用的功能

| 功能 | 说明 | 潜在价值 |
|------|------|---------|
| **Worktrees** | Git工作树，多个AI会话隔离修改 | 并行开发不同模块 |
| **Simultaneous Cascades** | 多个AI会话同时运行 | 一个修代码、一个写文档 |
| **Plan Mode** | 专用规划模式 | 复杂任务先规划再执行 |
| **@-mention 对话** | 引用之前的对话 | 跨会话上下文传递 |
| **Auto-Continue** | 工具调用超限自动继续 | 长任务不中断 |
| **Codemaps (Beta)** | 可视化代码导航 | 理解项目结构 |
| **Voice Input** | 语音输入 | 你可以直接说话 |
| **全局Skills** | `~/.codeium/windsurf/skills/` | 跨项目通用技能 |

---

## 三、完整配置机制对照表

| 机制 | 位置 | 激活方式 | 最适合 |
|------|------|---------|--------|
| `.windsurfrules` | 项目根目录 | Always On | ⚠️ 旧方案，建议迁移 |
| `.windsurf/rules/*.md` | rules目录 | 4种模式 | **核心规则系统** |
| `AGENTS.md` | 任意目录 | 按目录自动 | **模块级指令** |
| `.windsurf/skills/` | skills目录 | 自动+手动 | **复杂多步任务** |
| `.windsurf/workflows/` | workflows目录 | /slash-command | **可复用流程** |
| `.windsurf/hooks.json` | 项目根目录 | 事件触发 | **自动化钩子** |
| `global_rules.md` | Windsurf设置 | Always On | **全局行为规则** |
| `~/.codeium/windsurf/skills/` | 用户目录 | 自动+手动 | **跨项目通用技能** |
| Windsurf Memory | 内置系统 | 自动检索 | **跨会话记忆** |
| MCP | mcp_config.json | 工具调用 | **外部能力扩展** |
| `.codeiumignore` | 项目根目录 | 文件匹配 | **文件访问控制** |

---

## 四、OpenCLAW → Windsurf 完美映射

| OpenCLAW 概念 | Windsurf 对应 | 实现方式 |
|--------------|-------------|---------|
| `SOUL.md` (身份/人格) | `.windsurf/rules/soul.md` | Always On 规则 |
| `USER.md` (用户画像) | Windsurf Memory | create_memory |
| `AGENTS.md` (操作规则) | `AGENTS.md` 各目录 | 目录级自动加载 |
| `TOOLS.md` (工具笔记) | `.windsurf/rules/tools.md` | Always On 或 Model Decision |
| `MEMORY.md` (长期记忆) | Windsurf Memory 系统 | 自动+手动记忆 |
| `skills/` (技能) | `.windsurf/skills/` | 原生支持！ |
| `HEARTBEAT.md` (心跳) | 无直接对应 | 可通过 Hooks + 外部脚本模拟 |
| `BOOTSTRAP.md` (初始化) | `.windsurf/rules/` + Memory | 首次对话触发 |
| 自我更新 | Hooks `post_cascade_response` | 可记录并分析AI行为 |

---

## 五、立即可做的升级清单

### Priority 1：从 .windsurfrules 迁移到 .windsurf/rules/
将189行大文件拆分为多个精准规则文件，按需加载

### Priority 2：创建 AGENTS.md 体系
每个主要模块目录放一个 AGENTS.md

### Priority 3：迁移技能包到 .windsurf/skills/
现有的 `06-技能_skills/` 概念迁移为原生 Skills

### Priority 4：创建核心全局 Skills
在 `~/.codeium/windsurf/skills/` 创建跨项目通用技能

### Priority 5：探索 Hooks 可能性
评估哪些自动化可以通过 Hooks 实现
