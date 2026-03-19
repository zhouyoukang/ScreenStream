# Windsurf 智能体系仪表盘

> **用户之眼**：一文纵览所有AI配置，观之管之以至于无感。
> **最后更新**: 2026-03-20 (v17.1: 全层数字深度校验——32 Skills/12 Workflows/60+ AGENT_GUIDE)

---

## 〇、道法术器四层架构（v17.1）

```
道 — 全局级 Always-On (L1权重，最高优先级，不可违反)
 └── global_rules.md  元规则·五感×器·八德·降级链·本能层9条·持续推进·反者道之动

法 — Always-On (每消息注入，长对话不衰退)
 ├── kernel.md              内核(注意力锚点+执行协议+网络+凭据+硬约束)
 └── protocol.md            协议(推理链+转法轮+涅槃门+元认知+铁律)

术 — 按需触发 (全中文命名)
 ├── skills/ (32)                  按YAML描述匹配触发
 └── workflows/ (12)               /中文命令触发

器 — 持久知识 (跨对话)
 ├── AGENT_GUIDE.md × 60+         目录级参考指南(Agent按需read_file，数量随项目增长)
 └── MCP (6 Server)                context7/github/gitee/playwright/tavily/chrome-devtools
```

---

## 一、Zone 0 — 全局级

> **风险**：修改影响所有项目、所有窗口。操作前必须：评估影响→备份→验证。

### 1.1 全局规则 `~/.codeium/windsurf/memories/global_rules.md`

- Agent行为的最高指令
- **内容**：元规则 / 五感×器 / 八德(一推到底=持续推进到系统限制) / 降级链L1-L4 / 本能层9条+终端安全4条 / 反者道之动
- **v17.1**: 深度数字校验(32 Skills/12 Workflows/60+ AGENT_GUIDE) | InputService实测3395行
- **保护**：修改前必须展示旧→新对比，等用户确认
- **备份**：`.windsurf/backups/global/`

### 1.2 MCP配置 `~/.codeium/windsurf/mcp_config.json`

| Server              | 状态                       | 用途               |
| ------------------- | -------------------------- | ------------------ |
| **chrome-devtools** | ✅ `--isolated`            | CDP连接Chrome调试  |
| **playwright**      | ✅ `--headless --isolated` | 独立浏览器自动化   |
| **context7**        | ✅ 启用                    | 库文档查询         |
| **github**          | ✅ 启用(需Clash)           | GitHub API+PAT     |
| **gitee**           | ✅ 国内直连                | GitHub替代(29工具) |
| **tavily**          | ✅ 国内直连                | Web搜索(1000次/月) |

**启动脚本**: `C:\temp\*.cmd` (6个wrapper) | **配置索引**: `.windsurf/mcp-config.md`
**上下文税**: 6个Server约占11-14%上下文窗口

### 1.3 全局Hooks `~/.codeium/windsurf/hooks.json`

```json
{ "hooks": {} }
```

**状态**: ✅ 已清空（安全）— 项目hooks在Zone 1
**铁律**: **绝对禁止PowerShell hooks**（2026-02-13事故：导致全窗口卡死）

### 1.4 全局Skills `~/.codeium/windsurf/skills/`

**状态**: ❗️ 目录不存在 — 全局Skills未启用
**说明**: 所有32个项目Skills在Zone 1 (`.windsurf/skills/`)，无需全局Skills。
如需全局Skills，手动创建目录并添加SKILL.md文件。

### 1.5 IDE Settings

- **路径**: `AppData/Roaming/Windsurf/User/settings.json`
- **关键配置**: allowlist(自动运行命令白名单)、MCP开关、Shell Integration

### Zone 0 管理操作

| 操作           | 命令                                                                                     |
| -------------- | ---------------------------------------------------------------------------------------- |
| 查看全局规则   | `run_command("Get-Content $env:USERPROFILE\.codeium\windsurf\memories\global_rules.md")` |
| 查看全局hooks  | `run_command("Get-Content $env:USERPROFILE\.codeium\windsurf\hooks.json")`               |
| 查看MCP配置    | Windsurf Settings → MCP Servers                                                          |
| 查看全局Skills | `run_command("Get-ChildItem $env:USERPROFILE\.codeium\windsurf\skills -Dir")`            |

---

## 二、Zone 1 — 项目级

### 2.1 项目根规则 `.windsurfrules`

- **始终加载**，项目入口元文件
- 内容：组件计数索引 + 凭据中心指针

### 2.2 Rules（2 Always-On）

| 文件 | 触发 | 核心内容 |
|------|------|----------|
| `kernel.md` | always_on | 内核：注意力锚点+执行协议+网络代理+凭据+硬约束+进化律 |
| `protocol.md` | always_on | 协议：推理链+转法轮+涅槃门(持续推进)+反模式+元认知+铁律 |

### 2.3 技能库（32个，全中文命名）

> 详细索引见 `.windsurf/skills/README.md`

| 技能 | 用途 |
|------|------|
| 手机操控 | Agent远程操控手机 |
| 浏览器操控 | 多Agent浏览器操作 |
| 构建部署 | APK构建+部署 |
| 公网部署 | 阿里云/FRP/Nginx/SSL |
| 代码质量 | 代码分析·审查·重构三合一(含模型分层) |
| 深度逆向 | APK/DLL/协议/固件全量逆向 |
| 设备调试 | ADB设备调试+键盘映射 |
| 设备探测 | 新设备全量探测 |
| 功能开发 | ScreenStream新功能开发 |
| 中枢搭建 | Python Hub中枢搭建 |
| PWA框架 | PWA+WebView封装 |
| 远程中枢 | 远程中枢管理 |
| 资源整合 | 线上+本地资源全链路整合 |
| 智能家居 | 智能家居中枢 |
| 批量操作 | SWE低层操作 |
| 终端恢复 | 终端卡死诊断+恢复 |
| 验证测试 | E2E验证链 |
| 架构设计 | 软件架构设计 |
| 对话提炼 | 长对话深度提炼 |
| 文档生成 | 项目/API文档生成 |
| 错误诊断 | Bug系统化诊断 |
| 前端开发 | React/Vue/HTML/CSS/JS |
| 智能提交 | Git智能提交 |
| 性能优化 | 代码性能调优 |
| 项目初始化 | Windsurf配置初始化 |
| 搜索学习 | 新技术搜索学习 |
| 安全检查 | 安全漏洞检查 |
| 脚本编写 | PowerShell/Bash/批处理 |
| 学术文献 | WebVPN+开放API获取学术论文 |
| 工具策略 | 视/嗅/浏览器三域效率经验法则 |
| Windsurf账号 | 账号Farm+登录管理 |
| Windsurf配置 | MCP/Rules/Skills配置管理 |

### 2.4 工作流（12个，全中文命名）

| 命令 | 用途 |
|------|------|
| `/循环` | 转法轮·深度循环（2-3转螺旋迭代） |
| `/部署` | 公网部署全链路(阿里云/FRP/Nginx/SSL/Docker) |
| `/开发` | 全流程开发管线（分析→编码→构建→部署→验证→文档） |
| `/端到端` | 端到端全链路测试验证 |
| `/中枢` | Python Hub中枢搭建全链路 |
| `/论文` | 论文研究全链路 |
| `/电脑` | Agent完全操控电脑全链路 |
| `/手机` | Agent完全操控手机全链路 |
| `/资源` | 线上+本地资源全链路整合 |
| `/逆向` | 全量深度逆向全链路 |
| `/委派` | SWE委派管线（低消耗模型执行重复性操作） |
| `/review` | Review code changes (English) |

### 2.5 项目Hooks（2个Python）

| 钩子                  | 时机         | 脚本                    |
| --------------------- | ------------ | ----------------------- |
| pre_user_prompt       | 用户发消息前 | conversation_capture.py |
| post_cascade_response | AI回复后     | conversation_capture.py |

### Zone 1 管理操作

| 操作          | 命令                                            |
| ------------- | ----------------------------------------------- |
| 查看Rule      | `read_file(".windsurf/rules/<name>.md")`        |
| 查看Skill全景 | `read_file(".windsurf/skills/README.md")`       |
| 查看单个Skill | `read_file(".windsurf/skills/<name>/SKILL.md")` |
| 调用Workflow  | 对话中输入 `/dev` `/review` 等                  |
| 查看项目hooks | `read_file(".windsurf/hooks.json")`             |

---

## 三、Zone 2 — 目录级

> 目录级参考指南。已从AGENTS.md重命名为AGENT_GUIDE.md以避免Windsurf自动发现导致的context污染。Agent按需`read_file`加载。

### AGENT_GUIDE.md（目录级知识，Agent按需加载）

> 每个项目目录均可包含 `_AGENT_GUIDE.md`。Agent在需要时使用 `find_by_name(".""*AGENT_GUIDE*")` 发现，而非维护静态列表。

**典型内容**：端口/API入口/关键命令/架构决策/Agent操作规则

### Zone 2 管理操作

| 操作     | 命令                                         |
| -------- | -------------------------------------------- |
| 查看     | `read_file("<目录>/AGENT_GUIDE.md")`         |
| 新增     | 在目标目录创建 `AGENT_GUIDE.md`              |
| 全量清点 | `find_by_name(".", "*AGENT*", MaxDepth=2, Extensions=["md"])` |

---

## 四、知识体系 — 道法术三层自足

> v17.1: Memory=0。知识归AGENT_GUIDE，行为归Skill。道法术三层自足，无需外部记忆。

### 知识存储策略

| 类型 | 存储位置 | 加载方式 |
| ---- | -------- | -------- |
| 项目知识(端口/API/配置) | 该项目 `AGENT_GUIDE.md` | Agent按需 `read_file` |
| 行为模式(重复2+次的操作) | `skills/<name>/SKILL.md` | YAML描述匹配触发 |
| 凭据(密码/Token/Key) | `secrets.env` (gitignored) | Agent按需读取，不外泄 |
| 架构决策 | `05-文档_docs/adr/` | Agent按需读取 |

### 冷启动路径

```
list_dir 根目录 → 找到子项目 → read_file AGENT_GUIDE.md → 获得完整上下文
```

---

## 五、全景统计 (v17.1)

| 层 | 组件 | 数量 |
|----|------|------|
| **道** | 全局规则 + MCP(6) + Hooks + IDE Settings | ~9 |
| **法** | Always-On Rules (kernel + protocol) | 2 |
| **术** | Skills(32) + Workflows(12) | 44 |
| **器** | AGENT_GUIDE.md(60+) + MCP(6) | 66+ |

---

## 六、健康检查清单

定期执行（或运行 `/health-check`）：

### Zone 0

- [ ] 全局hooks.json 为空 `{"hooks": {}}`(禁止PS hooks)
- [ ] MCP 6个活跃Server正常(chrome-devtools/playwright/context7/github/gitee/tavily)
- [ ] 全局规则 global_rules.md 存在且可读

### Zone 1 (法+术)

- [ ] Rules 2个always_on协议文件存在 (kernel.md + protocol.md)
- [ ] Skills 32个 SKILL.md全部有YAML frontmatter
- [ ] Workflows 12个文件有description (+1 review英文)
- [ ] 项目hooks.json 仅含Python钩子(禁止PS)

### Zone 2

- [ ] AGENT_GUIDE.md 60+个文件存在 (`find_by_name(".", "*AGENT_GUIDE*", Extensions=["md"])`)

---

## 七、快捷操作

### 用户日常

| 需求         | 操作                                |
| ------------ | ----------------------------------- |
| 看全景       | 打开本文件 `.windsurf/DASHBOARD.md` |
| 查看技能全景 | `.windsurf/skills/README.md`        |
| 开发新功能   | `/开发`                             |
| 审查代码     | `/review`                           |
| 深度循环     | `/循环`                             |

### Agent自检

| Zone | 检查项        | 命令                                                                       |
| ---- | ------------- | -------------------------------------------------------------------------- |
| 0    | 全局hooks安全 | `run_command("Get-Content $env:USERPROFILE\.codeium\windsurf\hooks.json")` |
| 0    | MCP状态       | Windsurf Settings → MCP Servers                                            |
| 1    | Skills完整    | `find_by_name(".windsurf/skills", "SKILL.md")`                             |
| 1    | Rules完整     | `find_by_name(".windsurf/rules", "*.md")`                                  |
| 2    | AGENT_GUIDE   | `find_by_name(".", "*AGENT_GUIDE*", MaxDepth=2, Extensions=["md"])`        |
