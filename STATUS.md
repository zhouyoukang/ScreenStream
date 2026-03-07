# ScreenStream_v2 状态面板（STATUS）

> 本文件用于“现在到哪了 / 下一步做什么 / 风险在哪里”。
> 最后更新：2026-03-06

## 0) 权威入口

- docs 权威入口：`核心架构.md` → `FEATURES.md` → `MODULES.md`
- ADR 文件：根目录 `ADR-*.md`
- Windsurf 规则：`.windsurf/rules/`（6 个结构化规则）
- Windsurf Skills：`.windsurf/skills/`（17 个项目技能）
- 全局规则：`~/.codeium/windsurf/memories/global_rules.md`（AI 可自动编辑）

## 1) 当前主线目标（P0）

- **主线统一**：`ScreenStream_v2` 作为唯一主线，吸收 `ScreenStream_Quest` 与上游差异为可开关/配置。
- **入口收敛**：Input 与 MJPEG 的 HTTP Server 已统一端口标准（Input:8084）。
- **代码质量**：消除样板代码、修复端口不一致、统一 JSON 响应构建方式。

## 2) 已落地成果

### 基础设施
- **6 个 Gradle 模块**：app / common / mjpeg / rtsp / webrtc / input
- **端口标准**：Gateway:8080 MJPEG:8081 RTSP:8082 WebRTC:8083 Input:8084

### AI 配置体系
- **项目规则**：`.windsurf/rules/` 6 个文件
- **Skills**：17 项目 | **Hooks**：2 个 Python（conversation_capture） | **AGENTS.md**：44 个目录级（全覆盖）

### 里程碑摘要

| 版本 | 日期 | 核心内容 | 功能数 |
|------|------|---------|--------|
| v30 | 2026-02-13 | 投屏+基础控制（触控/键盘/导航/音量/锁屏） | 16 |
| v31 | 2026-02-13 | 远程协助（手势/截屏/设备信息/应用管理，+16路由） | 34 |
| v32 | 2026-02-13 | AI Brain（View树/语义点击/WebSocket触控流，+7路由） | 42 |
| v32+ | 2026-02-13 | 宏系统MVP+UX重设计+命令菜单+scrcpy兼容快捷键 | 72 |
| v33 | 2026-02-13 | 移动触控手势+竞品功能大整合（12+竞品参考，+23项）| 95→119 |
| v34 | 2026-02-14 | S33文件管理器(12API)+10个平台面板(S34-S43)+小模块批量 | 150 |
| v34+ | 2026-02-15 | 宏持久化+触发器引擎+Platform层(Intent/Wait/Screen/Notif) | 150+ |
| S50 | 2026-02-20 | SmartHome Gateway v2: MiCloud MIoT直连(163实体/24设备) | — |
| S50+ | 2026-02-21 | SmartHome v3: eWeLink+Tuya+音箱回退表+语音代理+场景宏 | — |
| S51 | 2026-02-22 | WeChat公众号控制入口+凭据安全加固+项目归档整合(19→10目录) | — |

### 安全加固（已完成）
- 前端XSS：5轮修复，所有用户输入/API返回统一 `escapeHtml`
- 后端：路径穿越(3处)、坐标双重缩放、资源泄漏(3处)、PIN弱随机数
- MJPEG：异常堆栈信息泄露修复
- Docker：Redis密码+内部服务绑定127.0.0.1

### 架构清理（2026-02-20/21/22）
- 根目录 19→10 目录，文档 30→12
- 删除空占位/废弃目录、过时备份、JVM崩溃日志
- 全文档计数一致性修复
- 300+ 文件归档提交，`config.json` gitignore 保护
- hooks.json 断裂引用修复（移除已归档的 setup_worktree）
- 根目录 88 个 wx_* 一次性脚本+截图已归档清理
- 归档 工具库/{bookwk_client, showcase.html, wechat-setup} + docs/agi-research-path.html
- 删除 downloaded_files/（残留锁文件）
- .gitignore 新增 wx_*/downloaded_files/agent-comm/ 防护
- 文档计数一致性修复（核心架构.md 8→9文件夹, hooks 4→2, 涂鹦→涂鸦错别字）

## 3) 进行中

- ~~SmartHome 微信公众号接入~~：✅ wechat_handler.py + gateway.py /wx 路由已集成
- **AI控制手机**：phone_lib.py + 3个测试脚本，P1-P29 实测发现已归档
- **合并/归档差异清单**：Quest vs v2 逐目录对照 — app/ 已完成（9条）

## 4) 下一步（按优先级）

1. **Shizuku API集成**：自动启用无障碍服务（无需手动设置）
2. **OTG纯控模式**：无屏幕投射的纯键鼠控制模式
3. **Quest 日志移植**：AppLogger + CollectingLogsUi（需添加 ProcessPhoenix 依赖）
4. **评估 .so 动态库寄生方案**（长期研究项）

## 5) 风险与护栏

- 端口/入口/鉴权策略属于架构级决策：必须先落 ADR 再改代码
- 构建/签名/发布：禁止隐式改动除非任务明确要求
- **全局配置修改铁律**：影响评估 → 备份 → 验证（参见 execution-engine.md）
