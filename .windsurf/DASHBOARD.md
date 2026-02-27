# Windsurf 智能体系仪表盘

> **用户之眼**：一文纵览所有AI配置，观之管之以至于无感。
> **Web仪表盘**: `python AGI/dashboard-server.py` → http://localhost:9090
> **最后更新**: 2026-02-27

---

## 〇、三层架构树（高层覆盖低层）

```
Zone 0 — 全局级（影响所有项目/所有窗口）
 ├── 全局规则    ~/.codeium/windsurf/memories/global_rules.md     88行  🔴极高
 ├── MCP配置     ~/.codeium/windsurf/mcp_config.json              5 Server  🔴极高
 ├── 全局Hooks   ~/.codeium/windsurf/hooks.json                   已清空{}  🔴极高
 ├── 全局Skills  ~/.codeium/windsurf/skills/                      13+1归档  🟡高
 └── IDE Settings AppData/Roaming/Windsurf/User/settings.json     allowlist  🟡高

Zone 1 — 项目级（影响当前工作区）
 ├── 项目根规则   .windsurfrules                                   始终加载
 ├── Always-On规则 .windsurf/rules/ (3)                            每次对话
 │    ├── soul.md                70行  AI思维内核
 │    ├── execution-engine.md   201行  执行引擎
 │    └── project-structure.md   44行  项目认知
 ├── Glob规则 (2)                                                  匹配文件时
 │    ├── kotlin-android.md      29行  *.kt
 │    └── frontend-html.md       20行  *.html/*.js/*.css
 ├── Model规则 (1)                                                 AI判断相关时
 │    └── build-deploy.md        35行  构建部署场景
 ├── 项目Hooks   .windsurf/hooks.json                              2 Python
 ├── 项目Skills  .windsurf/skills/ (13)                            按需调用
 └── Workflows   .windsurf/workflows/ (10)                         /命令触发

Zone 2 — 目录级（进入对应目录时加载）
 └── AGENTS.md × 17                                                含子目录继承
```

---

## 一、Zone 0 — 全局级

> **风险**：修改影响所有项目、所有窗口。操作前必须：评估影响→备份→验证。

### 1.1 全局规则 `~/.codeium/windsurf/memories/global_rules.md`
- **88行**，Agent行为的最高指令
- **内容**：核心原则(5条) / PREDICT决策框架 / 四层升级 / 权限自升级 / 执行引擎 / 代码准则 / 工作习惯
- **保护**：修改前必须展示旧→新对比，等用户确认
- **备份**：`.windsurf/backups/global/`

### 1.2 MCP配置 `~/.codeium/windsurf/mcp_config.json`

| Server | 状态 | 用途 |
|--------|------|------|
| **chrome-devtools** | ✅ 启用 `--isolated` | CDP连接Chrome调试 |
| **playwright** | ✅ 启用 `--headless --isolated` | 独立浏览器自动化 |
| **context7** | ✅ 启用 | 库文档查询 |
| **github** | ❌ 禁用 | GitHub API（需Clash代理） |
| **fetch** | ❌ 禁用 | HTTP请求（被IWR替代） |

**依赖**: npx代理(`AppData\Roaming\npm\npx.cmd` → pnpm dlx) | Clash `127.0.0.1:7897`(github需要)
**上下文税**: 活跃Server约占11-14%上下文窗口

### 1.3 全局Hooks `~/.codeium/windsurf/hooks.json`
```json
{"hooks": {}}
```
**状态**: ✅ 已清空（安全）
**铁律**: **绝对禁止PowerShell hooks**（2026-02-13事故：导致全窗口卡死）

### 1.4 全局Skills `~/.codeium/windsurf/skills/` (13个活跃 + 1归档)

| Skill | 用途 |
|-------|------|
| architecture-design | 架构设计与评估 |
| code-review | 代码审查 |
| conversation-distill | 长对话提炼 |
| doc-generator | 文档生成 |
| error-diagnosis | 错误诊断 |
| frontend-dev | 前端开发最佳实践 |
| git-smart-commit | 智能Git提交 |
| performance-optimize | 性能优化 |
| project-init | 新项目初始化 |
| refactor-code | 代码重构 |
| search-and-learn | 搜索学习 |
| security-check | 安全检查 |
| shell-scripting | Shell脚本 |
| _archived/ | 已归档旧Skills |

### 1.5 IDE Settings
- **路径**: `AppData/Roaming/Windsurf/User/settings.json`
- **关键配置**: allowlist(自动运行命令白名单)、MCP开关、Shell Integration

### Zone 0 管理操作
| 操作 | 命令 |
|------|------|
| 查看全局规则 | `run_command("Get-Content $env:USERPROFILE\.codeium\windsurf\memories\global_rules.md")` |
| 查看全局hooks | `run_command("Get-Content $env:USERPROFILE\.codeium\windsurf\hooks.json")` |
| 查看MCP配置 | Windsurf Settings → MCP Servers |
| 查看全局Skills | `run_command("Get-ChildItem $env:USERPROFILE\.codeium\windsurf\skills -Dir")` |

---

## 二、Zone 1 — 项目级

### 2.1 项目根规则 `.windsurfrules`
- **始终加载**，项目入口元文件
- 内容：组件计数索引 + 凭据中心指针

### 2.2 Rules（6个）

#### Always On（每次对话自动加载）
| 文件 | 行数 | 核心内容 |
|------|------|---------|
| `soul.md` | 70 | AI思维内核：哲学公理/双输出/被动进化/用户DNA |
| `execution-engine.md` | 201 | 执行引擎：终端安全/故障恢复/浏览器统御/凭据/对话结束 |
| `project-structure.md` | 44 | 项目认知：模块映射/端口分配/权威文档入口 |

#### Glob（按文件类型触发）
| 文件 | 行数 | 触发 |
|------|------|------|
| `kotlin-android.md` | 29 | 编辑 `*.kt` 文件时 |
| `frontend-html.md` | 20 | 编辑 `*.html/*.js/*.css` 文件时 |

#### Model（按任务类型触发）
| 文件 | 行数 | 触发 |
|------|------|------|
| `build-deploy.md` | 35 | 构建APK/推送/安装/部署操作时 |

### 2.3 项目Skills（13个）

> 详细全景索引见 `.windsurf/skills/README.md`

| 领域 | Skills | 合计行数 |
|------|--------|---------|
| 🔧 构建 | build-and-deploy | 65 |
| 🐛 调试 | adb-device-debug, keyboard-input-debug, terminal-resilience | 484 |
| 🧪 测试 | api-testing, full-verification | 180 |
| 🚀 开发 | feature-development, new-module-setup, requirement-decompose | 267 |
| 🌐 前端 | pwa-framework, persona-chat-system | 753 |
| 📱 控制 | agent-phone-control | 124 |
| 🌍 浏览器 | browser-agent-mastery | 92 |

**总计**: 1,965行 | **全部13个有YAML frontmatter** ✅

### 2.4 Workflows（10个）

| 命令 | 用途 |
|------|------|
| `/dev` | 全流程开发管线（分析→编码→构建→部署→验证→文档） |
| `/doc` | 文档生成更新 |
| `/review` | 代码审查 |
| `/test` | 编写运行测试 |
| `/refactor` | 安全重构 |
| `/optimize` | 性能优化 |
| `/evolve` | 系统自我进化 |
| `/health-check` | 系统健康检查 |
| `/debug-escalation` | 逐层升级调试 |
| `/swe-pipeline` | SWE管线（弱模型优化） |

### 2.5 项目Hooks（2个Python）

| 钩子 | 时机 | 脚本 |
|------|------|------|
| pre_user_prompt | 用户发消息前 | conversation_capture.py |
| post_cascade_response | AI回复后 | conversation_capture.py |

### Zone 1 管理操作
| 操作 | 命令 |
|------|------|
| 查看Rule | `read_file(".windsurf/rules/<name>.md")` |
| 查看Skill全景 | `read_file(".windsurf/skills/README.md")` |
| 查看单个Skill | `read_file(".windsurf/skills/<name>/SKILL.md")` |
| 调用Workflow | 对话中输入 `/dev` `/review` 等 |
| 查看项目hooks | `read_file(".windsurf/hooks.json")` |

---

## 三、Zone 2 — 目录级

> Agent进入某个目录操作时，自动加载该目录的AGENTS.md。子目录继承父目录。

### AGENTS.md 全量清单（17个）

#### SS核心模块（8）
| 目录 | 职责 |
|------|------|
| `反向控制/` | Input API + AccessibilityService |
| `基础设施/` | 公共组件/DI/工具/日志 |
| `投屏链路/` | 流媒体总览 |
| `投屏链路/MJPEG投屏/` | MJPEG流+HttpServer+前端 |
| `投屏链路/RTSP投屏/` | RTSP流 |
| `投屏链路/WebRTC投屏/` | WebRTC P2P |
| `用户界面/` | Android UI + Compose |
| `配置管理/` | Settings接口+实现 |

#### Python卫星（3）
| 目录 | 职责 |
|------|------|
| `智能家居/` | HA代理+涂鸦+微信(:8900) |
| `手机操控库/` | phone_lib.py(SS API封装) |
| `远程桌面/` | remote_agent.py(:9903) |

#### 基础设施（3）
| 目录 | 职责 |
|------|------|
| `构建部署/` | Gradle/脚本/SDK/部署 |
| `构建部署/三界隔离/` | Git安全网+账号隔离 |
| `阿里云服务器/` | FRP/SSL/部署脚本 |

#### 特殊（3）
| 目录 | 职责 |
|------|------|
| `台式机保护/` | 远程台式机铁律13条 |
| `双电脑互联/` | 双机互联知识中枢 |
| `双电脑互联/道之AGENTS.md` | 道之统一专项指令 |

### Zone 2 管理操作
| 操作 | 命令 |
|------|------|
| 查看 | `read_file("<目录>/AGENTS.md")` |
| 新增 | 在目标目录创建 `AGENTS.md` |
| 全量清点 | `find_by_name(".", "AGENTS.md", MaxDepth=3)` |

---

## 四、Memory — Agent长期记忆

> Memory跨越三个Zone，是Agent的跨对话持久知识库。

### 分类分布（估计）
| 类型 | 数量 | 示例 |
|------|------|------|
| 🏗️ 项目配置 | ~5 | 配置索引/项目结构/凭据中心 |
| 🖥️ 双电脑 | ~8 | 台式机状态/远程通道/同步/保护 |
| 📱 手机/SS | ~6 | 设备信息/API端口/公网投屏/phone_lib |
| 🏠 智能家居 | ~4 | HA桥接/音箱/Mina/网关 |
| 🌐 浏览器MCP | ~3 | 多Agent研究/五感冲突/MCP全景 |
| 📦 二手书 | ~5 | 书市PWA/三鲜/采集/Session |
| 🔧 系统维护 | ~5 | 磁盘清理/诊断/崩溃修复 |
| 🎨 其他项目 | ~8 | AI初恋/3D打印/视频/论文/远控 |

### 管理原则
- **铁律**: Memory禁止存储实际密码/Token值
- **去重**: 更新优先于新建（`create_memory` Action=update）
- **过期**: 已完成的临时任务Memory应标注或删除
- **质量**: 结构化（标题+关键事实+文件位置）优于流水账

---

## 五、全景统计

| Zone | 组件 | 数量 | 合计 |
|------|------|------|------|
| **0 全局** | 全局规则 + MCP(5) + 全局Hooks + 全局Skills(13) + IDE Settings | 21 | |
| **1 项目** | Rules(6) + Skills(13) + Workflows(10) + Hooks(2) | 31 | |
| **2 目录** | AGENTS.md | 17 | |
| **跨层** | Memory | ~40+ | |
| | | **总计** | **~109+** |

---

## 六、健康检查清单

定期执行（或运行 `/health-check`）：

### Zone 0
- [ ] 全局hooks.json 为空 `{"hooks": {}}`
- [ ] MCP 3个活跃Server正常（chrome-devtools/playwright/context7）
- [ ] 全局规则 global_rules.md 存在且可读

### Zone 1
- [ ] Rules 6个文件存在
- [ ] Skills 13个SKILL.md全部有YAML frontmatter
- [ ] Skills ADB路径指向 `e:\道\道生一\一生二\`
- [ ] Workflows 10个文件有description
- [ ] 项目hooks.json 仅含Python钩子
- [ ] `.windsurfrules` 计数与实际一致

### Zone 2
- [ ] AGENTS.md 17个文件全部存在

---

## 七、快捷操作

### 用户日常
| 需求 | 操作 |
|------|------|
| 看全景 | 打开本文件 `.windsurf/DASHBOARD.md` |
| 看Skills详情 | `.windsurf/skills/README.md` |
| 开发新功能 | `/dev` |
| 审查代码 | `/review` |
| 系统体检 | `/health-check` |
| 进化升级 | `/evolve` |

### Agent自检
| Zone | 检查项 | 命令 |
|------|--------|------|
| 0 | 全局hooks安全 | `run_command("Get-Content $env:USERPROFILE\.codeium\windsurf\hooks.json")` |
| 0 | MCP状态 | Windsurf Settings → MCP Servers |
| 1 | Skills完整 | `find_by_name(".windsurf/skills", "SKILL.md")` |
| 1 | Rules完整 | `find_by_name(".windsurf/rules", "*.md")` |
| 2 | AGENTS.md | `find_by_name(".", "AGENTS.md", MaxDepth=3)` |
