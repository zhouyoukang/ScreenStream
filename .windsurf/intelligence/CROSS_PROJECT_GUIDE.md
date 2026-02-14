# 跨项目配置指南：新项目如何复用智能体系

> 当你开一个新的 Windsurf 项目窗口时，需要知道哪些是自动共享的，哪些需要手动配置

---

## 一、自动共享（无需任何操作）

| 配置 | 位置 | 说明 |
|------|------|------|
| **全局规则** | Windsurf Settings → AI Rules → Global | 所有项目自动加载 |
| **全局 Skills** | `~/.codeium/windsurf/skills/` | 所有项目可用 |
| **用户级 Hooks** | `~/.codeium/windsurf/hooks.json` | 所有项目触发 |
| **Windsurf Memory** | 内置系统 | 跨项目自动检索相关记忆 |

### 当前已配置的全局 Skills（跨项目可用）
```
C:\Users\zhouyoukang\.codeium\windsurf\skills\
├── git-smart-commit/    → 智能Git提交
├── project-init/        → 新项目Windsurf配置初始化
└── search-and-learn/    → 搜索外部资源学习新技术
```

---

## 二、每个项目需要手动配置

| 配置 | 位置 | 说明 |
|------|------|------|
| `.windsurf/rules/` | 项目根目录 | 项目特定规则 |
| `AGENTS.md` | 各模块目录 | 模块级指令 |
| `.windsurf/skills/` | 项目根目录 | 项目特定技能 |
| `.windsurf/hooks.json` | 项目根目录 | 项目特定钩子 |
| `.windsurf/workflows/` | 项目根目录 | 项目特定工作流 |

### 新项目最小配置清单
1. 在 Cascade 中输入 `@project-init` 触发全局技能，自动引导配置
2. 或手动创建：
   ```
   .windsurf/rules/
   ├── project-structure.md  ← Always On：项目结构认知（必须）
   └── execution-engine.md   ← Always On：执行规则（可从模板复制）
   AGENTS.md                 ← 根目录项目指令（必须）
   ```

---

## 三、全局规则 vs 项目规则 分工

| 维度 | 全局规则（跨项目） | 项目规则（项目内） |
|------|------------------|------------------|
| AI身份/思维 | ✅ SOUL + PREDICT | ❌ |
| MCP调用规范 | ✅ | ❌ |
| 代码风格 | ✅ 通用准则 | ✅ 项目特定风格 |
| 项目结构 | ❌ | ✅ |
| 构建部署 | ❌ | ✅ |
| 语言规范 | ❌ | ✅ Glob规则 |

---

## 四、你需要手动做的唯一操作

### 应用全局规则（一次性，所有项目生效）

1. 打开 Windsurf
2. 点击右上角 Cascade 面板的 `⋯` → `Customizations`
3. 切换到 `Rules` 标签
4. 点击 `+ Global` 创建全局规则
5. 将 `.windsurf/intelligence/NEW_GLOBAL_RULES.md` 中 `---BEGIN---` 到 `---END---` 之间的内容粘贴进去
6. 保存

完成后，所有项目窗口都会自动加载这套全局规则。
