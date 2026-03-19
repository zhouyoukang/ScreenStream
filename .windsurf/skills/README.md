# 技能库索引（32个）

> v17.1: 目录名英文(Windsurf要求`[a-z0-9-]+`)，YAML description保持中文(用户可感知)。
> code-review + refactor-code 已合并入 code-quality（分析+审查+重构 三合一），不再有独立目录。

## 速查表（我要做X → 用哪个技能）

| 我要做... | 技能(slug) | 中文名 | 工作流 |
|-----------|------------|--------|--------|
| 逆向APK/DLL/设备/协议 | `deep-reverse` | 深度逆向 | /逆向 |
| 搭建Hub中枢+Dashboard | `hub-builder` | 中枢搭建 | /中枢 |
| 搜索下载整合开源资源 | `resource-pipeline` | 资源整合 | /资源 |
| 部署到阿里云/公网 | `cloud-deploy` | 公网部署 | /部署 |
| 探测新连接的设备 | `device-probe` | 设备探测 | /逆向 |
| 操控手机完成任务 | `phone-control` | 手机操控 | /手机 |
| 操控电脑/远程桌面 | `remote-hub` | 远程中枢 | /电脑 |
| 智能家居控制 | `smart-home` | 智能家居 | — |
| ScreenStream功能开发 | `feature-dev` | 功能开发 | /开发 |
| 构建APK部署到手机 | `build-deploy` | 构建部署 | /开发 |
| 代码审查/分析/重构 | `code-quality` | 代码质量 | /review |
| E2E端到端测试 | `verify-test` | 验证测试 | /端到端 |
| 浏览器自动化/E2E | `browser-control` | 浏览器操控 | /端到端 |
| 终端卡死恢复 | `terminal-recovery` | 终端恢复 | — |
| ADB设备调试 | `device-debug` | 设备调试 | — |
| 批量文件/Git/扫描 | `batch-ops` | 批量操作 | /委派 |
| PWA单文件应用 | `pwa-framework` | PWA框架 | — |
| 论文数据分析写作 | `academic-literature` | 学术文献获取 | /论文 |
| Windsurf账户管理 | `windsurf-account` | 账户管理 | — |
| Windsurf配置管理 | `windsurf-config` | 配置管理 | — |
| 深度循环优化 | — | — | /循环 |
| 工具选择策略 | `tool-strategy` | 工具策略 | — |

## 全景矩阵

### 逆向探测（3）

| slug | 中文名 | 用途 |
|------|--------|------|
| `deep-reverse` | 深度逆向 | APK/DLL/协议/固件/设备全量逆向 |
| `device-probe` | 设备探测 | USB/WiFi/BLE/串口/端口全量设备探测 |
| `resource-pipeline` | 资源整合 | 线上+本地资源搜索→下载→部署→集成 |

### 中枢部署（3）

| slug | 中文名 | 用途 |
|------|--------|------|
| `hub-builder` | 中枢搭建 | Python Hub中枢标准搭建(HTTPServer+Dashboard) |
| `cloud-deploy` | 公网部署 | 阿里云/FRP/Nginx/SSL/Docker公网部署 |
| `build-deploy` | 构建部署 | APK构建→推送→安装→启动 |

### 核心开发（3）

| slug | 中文名 | 用途 |
|------|--------|------|
| `feature-dev` | 功能开发 | ScreenStream新功能开发完整流程 |
| `code-quality` | 代码质量 | 代码分析+审查+重构三合一(含模型分层) |
| `frontend-dev` | 前端开发 | React/Vue/HTML/CSS/JavaScript |
| ~~`code-review`~~ | →已合并入code-quality | — |
| ~~`refactor-code`~~ | →已合并入code-quality | — |

### 质量保障（5）

| slug | 中文名 | 用途 |
|------|--------|------|
| `error-diagnosis` | 错误诊断 | Bug/异常/崩溃系统化诊断 |
| `performance-optimize` | 性能优化 | 代码性能分析与调优 |
| `security-check` | 安全检查 | 安全漏洞与风险检查 |
| `verify-test` | 验证测试 | API测试+E2E端到端验证链 |
| `terminal-recovery` | 终端恢复 | 终端卡死诊断与五感降级恢复 |

### 设备远程（4）

| slug | 中文名 | 用途 |
|------|--------|------|
| `phone-control` | 手机操控 | Agent远程操控手机(SS API+ADB) |
| `smart-home` | 智能家居 | 智能家居+手机+桌面统一控制 |
| `remote-hub` | 远程中枢 | 远程电脑管理与操作(WinRM+API) |
| `device-debug` | 设备调试 | ADB设备调试+键盘输入映射 |

### 工程辅助（5）

| slug | 中文名 | 用途 |
|------|--------|------|
| `architecture-design` | 架构设计 | 软件架构设计与技术选型 |
| `project-init` | 项目初始化 | Windsurf智能配置体系初始化 |
| `doc-generator` | 文档生成 | 项目文档/API文档/README生成 |
| `git-smart-commit` | 智能提交 | Git智能提交(分析变更+规范message) |
| `shell-scripting` | 脚本编写 | PowerShell/Bash/批处理自动化 |

### 知识工具（4）

| slug | 中文名 | 用途 |
|------|--------|------|
| `search-and-learn` | 搜索学习 | 新技术学习与外部资源搜索 |
| `conversation-distill` | 对话提炼 | 长对话深度提炼核心价值 |
| `browser-control` | 浏览器操控 | 浏览器Agent效率统御(run_code 30x效率)+多Agent冲突防护 |
| `pwa-framework` | PWA框架 | PWA单文件+WebView封装+五感UX |

### 系统配置（2）

| slug | 中文名 | 用途 |
|------|--------|------|
| `windsurf-account` | 账户管理 | Windsurf账户设置与配置 |
| `windsurf-config` | 配置管理 | Windsurf配置（MCP/Rules/Skills/Workflows）维护与安全管理中枢集成 |

### 底层操作（2）

| slug | 中文名 | 用途 |
|------|--------|------|
| `batch-ops` | 批量操作 | 批量文件/Git/健康检查/资源获取/逆向扫描 五合一 |
| `tool-strategy` | 工具策略 | 视/嗅/浏览器三域效率经验法则+器之图谱(v15.0新增) |

### 学术研究（1）

| slug | 中文名 | 用途 |
|------|--------|------|
| `academic-literature` | 学术文献获取 | WebVPN+开放API获取学术论文全文和元数据 |
