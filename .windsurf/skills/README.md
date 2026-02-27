# Skills 全景索引

> **用户之眼**：一目了然看到所有Skill的覆盖范围、触发条件、质量状态
> **Agent之眼**：通过frontmatter自动匹配触发，无需人工指定

## 全景矩阵（13 Skills）

### 🔧 构建部署（1）
| Skill | 触发条件 | 行数 | 五感覆盖 |
|-------|---------|------|---------|
| **build-and-deploy** | APK构建/推送/安装/启动 | 65 | ✋执行 👅验证 |

### 🐛 调试诊断（3）
| Skill | 触发条件 | 行数 | 五感覆盖 |
|-------|---------|------|---------|
| **adb-device-debug** | 设备连接失败/ADB问题/WiFi ADB/OEM拦截 | 146 | 👁视觉 ✋触觉 👃嗅觉 |
| **keyboard-input-debug** | 键盘映射/keysym/光标移动问题 | 49 | 👁视觉 ✋触觉 |
| **terminal-resilience** | 终端卡死/交互阻塞/用户反馈"卡住了" | 289 | 👁👂✋👃👅全五感 |

### 🧪 测试验证（2）
| Skill | 触发条件 | 行数 | 五感覆盖 |
|-------|---------|------|---------|
| **api-testing** | API功能验证/健康检查/HTTP调试 | 78 | ✋触觉 👅验证 |
| **full-verification** | 代码修改后端到端验证链 | 102 | 👁👂✋👅四感 |

### 🚀 开发流程（3）
| Skill | 触发条件 | 行数 | 五感覆盖 |
|-------|---------|------|---------|
| **feature-development** | 新功能需求/API端点/前端交互/跨模块 | 129 | 👁视觉 ✋触觉 👅验证 |
| **new-module-setup** | 新模块/新协议/项目重组 | 51 | ✋触觉 👃嗅觉 |
| **requirement-decompose** | 一句话需求→结构化特性列表 | 87 | 👃嗅觉 🧠认知 |

### 🌐 前端/PWA（2）
| Skill | 触发条件 | 行数 | 五感覆盖 |
|-------|---------|------|---------|
| **pwa-framework** | 离线Web应用/单文件PWA/WebView封装 | 500 | 👁👂✋👃👅全五感 |
| **persona-chat-system** | 人格对话AI/角色扮演/记忆搜索 | 253 | 👁视觉 🧠认知 |

### 📱 手机控制（1）
| Skill | 触发条件 | 行数 | 五感覆盖 |
|-------|---------|------|---------|
| **agent-phone-control** | 多步手机操作/跨APP工作流/动态决策 | 124 | 👁👂✋👅四感 |

### 🌍 浏览器（1）
| Skill | 触发条件 | 行数 | 五感覆盖 |
|-------|---------|------|---------|
| **browser-agent-mastery** | 浏览器操控/多Agent并行/E2E验证 | 92 | 👁👂✋👃👅全五感 |

## 质量状态

| 状态 | 含义 | Skills |
|------|------|--------|
| ✅ 完善 | frontmatter+代码模板+实战案例+故障速查 | terminal-resilience, pwa-framework, browser-agent-mastery, agent-phone-control, feature-development |
| ✅ 可用 | frontmatter+代码模板+基本覆盖 | build-and-deploy, full-verification, api-testing, adb-device-debug, persona-chat-system, requirement-decompose |
| 🟡 基础 | frontmatter+基本流程 | keyboard-input-debug, new-module-setup |

## 格式规范

每个Skill必须包含：
```yaml
---
name: skill-name           # 唯一标识，与目录名一致
description: 一句话描述     # Agent匹配触发条件用
triggers:                  # 可选，细化触发场景
  - 触发条件1
  - 触发条件2
---
```

### Agent调用链
```
用户请求 → Windsurf匹配description → 加载SKILL.md → Agent按步骤执行
```

- `skill` 工具调用时，Windsurf读取SKILL.md全文注入上下文
- frontmatter的`description`用于模糊匹配触发
- `triggers`提供更精确的场景识别

## 维护原则

1. **路径必须是当前项目路径**：`e:\道\道生一\一生二\`（非旧路径`e:\github\AIOT\`）
2. **代码模板必须可直接执行**：复制到终端即可运行
3. **实战案例优先**：从真实对话中提炼，而非想象
4. **与rules/workflows不重叠**：Skill=怎么做，Rule=什么不能做，Workflow=什么顺序做

## 文件结构
```
.windsurf/skills/
├── README.md                    ← 本文件（全景索引）
├── adb-device-debug/SKILL.md    ← 146行 | 设备调试
├── agent-phone-control/SKILL.md ← 124行 | 手机操控
├── api-testing/SKILL.md         ← 78行  | API测试
├── browser-agent-mastery/SKILL.md ← 92行 | 浏览器控制
├── build-and-deploy/SKILL.md    ← 65行  | 构建部署
├── feature-development/SKILL.md ← 129行 | 功能开发
├── full-verification/SKILL.md   ← 102行 | 端到端验证
├── keyboard-input-debug/SKILL.md ← 49行 | 键盘调试
├── new-module-setup/SKILL.md    ← 51行  | 新模块
├── persona-chat-system/SKILL.md ← 253行 | 人格对话
├── pwa-framework/SKILL.md       ← 500行 | PWA框架
│   └── templates/               ← 模板文件
├── requirement-decompose/SKILL.md ← 87行 | 需求分解
└── terminal-resilience/SKILL.md ← 289行 | 终端韧性
```
