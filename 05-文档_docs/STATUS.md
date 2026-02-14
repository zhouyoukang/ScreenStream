# ScreenStream_v2 状态面板（STATUS）

> 本文件用于“现在到哪了 / 下一步做什么 / 风险在哪里”。
> 最后更新：2026-02-13

## 0) 权威入口

- docs 权威入口：`05-文档_docs/README.md`
- ADR 目录：`05-文档_docs/adr/`
- Windsurf 规则：`.windsurf/rules/`（6 个结构化规则）
- Windsurf Skills：`.windsurf/skills/`（5 个项目技能）
- 全局规则：`~/.codeium/windsurf/memories/global_rules.md`（AI 可自动编辑）

## 1) 当前主线目标（P0）

- **主线统一**：`ScreenStream_v2` 作为唯一主线，吸收 `ScreenStream_Quest` 与上游差异为可开关/配置。
- **入口收敛**：Input 与 MJPEG 的 HTTP Server 已统一端口标准（Input:8084）。
- **代码质量**：消除样板代码、修复端口不一致、统一 JSON 响应构建方式。

## 2) 已落地成果

### 基础设施
- **6 个 Gradle 模块**：app / common / mjpeg / rtsp / webrtc / input
- **端口标准**：Gateway:8080 MJPEG:8081 RTSP:8082 WebRTC:8083 Input:8084
- **API 服务化**：5 个独立 API 服务 + Docker Compose + CI/CD

### AI 配置体系（v4.0）
- **全局规则**：`global_rules.md` v4.0（PREDICT/ESCALATION/Context Engineering/MCP限制/Windsurf新功能/双输出原则）
- **项目规则**：`.windsurf/rules/` 6 个文件（soul v4.0 精简75% / execution-engine v4.0 精简69% / project-structure / kotlin-android / frontend-html / build-deploy）
- **AGENTS.md**：8 个目录级指令文件
- **Skills**：7 项目 + 23 全局
- **Hooks**：已清空（Python/Node.js可用，PowerShell绝对禁止）

### 文档体系
- `05-文档_docs/` 下 14 个权威文档
- ADR 目录 + 合并/归档清单

### 本轮代码改进（2026-02-13）

**Kotlin 后端**：
- **InputHttpServer 端口修复**：8086→8084，与 InputSettings.Default.API_PORT 一致
- **InputRoutes.kt 重构**：提取 `requireInputService` 消除 7 处重复 null-check，231→120 行
- **InputService.kt**：移除重复 Javadoc 注释
- **JSON 响应安全化**：手拼 JSON 字符串改为 JSONObject 构建（防注入）
- **MJPEG HttpServer**：移除重复 `exposeHeader(ContentType)`；提取 `handleVideoStream` 消除 H264/H265 约 40 行重复代码

**前端 HTML/JS**：
- **移除重复 `sendTap` 函数**（严格模式下会报错）
- **移除无用 `syncStatus` 轮询**（每秒 XHR 但 onload 为空，浪费带宽）
- **版本号统一** v28→v29
- **清理过时设计注释**

**文档/配置**：
- **过时引用修复**：MCP 工具名 igpnhdej_dev→abtiixvb_dev
- **全局规则 MCP 调用逻辑移除**（用户按需再启用）

### 鲁棒性体系（2026-02-13 建立）
- **`/health-check` 自检工作流**：25+ 关键文件存在性 + 内容完整性 + 恢复指引
- **备份冗余**：`.windsurf/backups/rules/`（6个）+ `.windsurf/backups/global/`（global_rules.md）
- **三级恢复**：项目备份 → 升级包 → Memory 搜索
- **全局规则 + soul.md** 均已加入自检指令
- **升级包同步**：INSTALLER.md 新增 Step 6.5 备份体系初始化

### 全流程开发管线（2026-02-13 建立+实战验证）
- **`/dev` 工作流**：需求理解→影响分析→方案设计→实现→构建→部署→测试→文档→总结（7 Phase）
- **`feature-development` 技能**：ScreenStream 专属的功能开发知识（模块映射、代码模式、文件速查）
- **`full-verification` 技能**：编译→推送→安装→启动→API验证→日志检查（已含实战经验）
- **`soul.md` 全流程思维**：用户给出开发需求时，AI 默认启动全流程管线
- **`execution-engine.md` 管线协议**：各阶段执行规则 + 失败处理 + 中断恢复
- **可分发通用模板**：升级包中 `workflows/dev.md` + `skills/feature-development/` + `skills/full-verification/`

### 首次全流程实战验证（2026-02-13）
- ✅ 编译：通过（修复 Ktor `DefaultWebSocketServerSession` import 路径）
- ✅ 推送：16,792,671 bytes → 设备
- ✅ 安装：Success
- ✅ 启动：进程正常，MjpegStreamingService 运行中
- ✅ API：`/status` `/tap` `/back` `/home` 全部响应 `{"ok":true}`
- 📝 经验沉淀：PowerShell curl JSON 转义、adb forward 优先、端口监听时机
- 📝 技能更新：`api-testing` + `full-verification` 已根据实战完善

### 预测性开发首次实践（2026-02-13 v30）
- **新增后端**：`volumeUp()` `volumeDown()` `lockScreen()` + 4个新路由
- **新增前端**：第3导航模式「系统控制」 + 键盘音量键映射
- ✅ 编译+部署+API验证全部通过（v30）

### AI Brain 大版本（2026-02-13 v32）
- **WebSocket 实时触控流**：`/ws/touch` 端点，mouse/touch 事件通过 WebSocket 实时流传输（延迟从 ~100ms 降到 ~10ms）
- **View 树分析（7个新方法）**：`getViewTree()` `getActiveWindowInfo()` `findAndClickByText()` `findAndClickById()` `dismissTopDialog()` `findNodesByText()` `setNodeText()`
- **新路由（7个）**：`/viewtree` `/windowinfo` `/findclick` `/dismiss` `/findnodes` `/settext` `/ws/touch`
- **手机端查看器**：自动检测手机浏览器 → 全屏沉浸模式（导航栏自动隐藏，浮动☰按钮切换）
- **前端**：v32 (AI Brain)，WebSocket 触控流 + HTTP 自动降级
- **依赖**：Input 模块新增 `ktor-server-websockets`
- **架构文档**：`ARCHITECTURE_v32.md` 三层架构设计（宿主 + API + AI Brain）
- ✅ 编译通过（30s），部署成功（16,819,137 bytes）
- 📝 FEATURES.md 扩充到 42 条功能登记
- ✅ API 全部验证通过（端口8086）：`/windowinfo` `/viewtree` `/dismiss` `/findclick` `/findnodes` `/settext` `/wake` `/deviceinfo`
- 🔧 `dev-deploy.ps1` 一键部署脚本（Root自动启用AccessibilityService+编译+安装+端口转发+验证）
- 📝 `VISION.md` 超级AI助理愿景：5阶段演进路线（投屏→远程→自动化→AI Agent→超级助理）
- 📝 `DISTRIBUTION.md` 分发方案（F-Droid/GitHub/网盘 + Google API合规 + 品牌适配）

### 远程协助大版本（2026-02-13 v31）
- **系统动作（5个）**：`wakeScreen()` `showPowerDialog()` `takeScreenshot()` `toggleSplitScreen()` `setBrightness()`
- **增强手势（4个）**：`longPressNormalized()` `doubleTapNormalized()` `scrollNormalized()` `pinchZoom()`
- **应用管理（5个）**：`openApp()` `openUrl()` `getDeviceInfo()` `getInstalledApps()` `getClipboardText()`
- **新路由（16个）**：`/wake` `/power` `/screenshot` `/splitscreen` `/brightness` `/longpress` `/doubletap` `/scroll` `/pinch` `/openapp` `/openurl` `/deviceinfo` `/apps` `/clipboard` + brightness GET
- **前端**：第4导航模式「远程协助」（唤醒/截屏/电源/设备信息面板） + v31
- **权限**：新增 WAKE_LOCK（Input 模块 manifest）
- ✅ 编译+部署+全部16个新API实测验证通过（v31，16,806,480 bytes）
- 📝 实测设备：OnePlus NE2210, Android 15 (API 35), 1080×2412
- 📝 FEATURES.md 扩充到 34 条功能登记
- 📝 USER_GUIDE_v31.md 完整使用指南

### 文件清理
- **根目录 `docs/`**（6个旧文件）→ 归档到 `05-文档_docs/90-根目录零散资料/legacy-docs/`
- **`NEW_AI_HANDOVER_GUIDE.md`** → 归档到 `05-文档_docs/90-根目录零散资料/`

### 文档完善
- **FEATURES.md**：从 1 条扩充到 16 条功能登记（覆盖投屏+输入+认证+网关）

### DevCatalyst v5.0 开源发布（2026-02-13）
- 仓库：https://github.com/zhouyoukang/DevCatalyst
- 英文版 README + MIT License
- 包含：core(4) + global-skills(27) + workflows(9) + installer(2) + hooks(3) + settings(3) + project-templates(4) + scripts(1) + docs(2)
- v5.0 核心创新：规则预算制（≤6000字符）、变更协议、规则编译器、生命周期管理

### v32+ 增量成果（2026-02-13 下午）
- ✅ **Phase 2 宏系统 MVP**：MacroEngine + 11 个 API 路由（CRUD + 执行 + 内联 + 日志）
- ✅ **触控视觉反馈**：ripple 波纹 + touch dot + trail 轨迹，集成到 mouse/touch 事件
- ✅ **RTSP 命名 bug 修复**：`mjpegEvent` → `rtspEvent`（copy-paste 遗留）
- ✅ **文档体系刷新**：AGENTS.md(3个) + README.md + USER_GUIDE + 备份
- ✅ **全量编译通过**：assembleFDroidDebug 97 tasks 0 errors

### v32+ 功能整合（2026-02-13 晚）
- ✅ **前端 AI+工具箱**：剪贴板/应用列表/亮度/AI语义点击/View树/关弹窗/快捷设置/分屏
- ✅ **run-inline loop 修复**：支持 `"loop":3` 循环执行
- ✅ **部署脚本增强**：`ss` 探测替代 `netstat`，端口范围 8080-8099，完善 API 验证
- ✅ **api-verify.ps1**：独立自动验证脚本，22/22 端点全部通过

### v32+ UX 重设计（2026-02-13 晚）
- ✅ **导航栏重设计**：6模式循环 → 固定3键(返回/主页/最近) + 分类命令菜单
- ✅ **分类命令菜单**：5大类(系统控制/投屏设置/远程工具/AI工具/宏系统) + 快捷键速查卡
- ✅ **scrcpy兼容快捷键**：Alt+H/B/S/F/↑↓/N/P/O/C/M，匹配行业标准操作习惯
- ✅ **鼠标增强**：中键=HOME（scrcpy兼容）
- ✅ **showStatus修复**：display:none→flex切换，确保快捷键反馈可见
- ✅ **CSS现代化**：glassmorphism导航栏/菜单面板，backdrop-filter模糊，hover微动画
- ✅ **第6次编译+部署+验证通过**（端口8086，72个功能点）
- 📝 FEATURES.md 更新到72条（+4 UX特性）
- 📝 USER_GUIDE_v32plus.md 同步更新（固定导航+命令菜单+快捷键表）

### 移动触控与自动化增强（v33）
- ✅ **多点触控手势**：捏合缩放、双指滚动、长按(500ms)、双击(300ms) — `index.html` 手势状态机
- ✅ **移动端UX**：viewport-fit=cover(刘海屏适配)、overscroll-behavior:none(防误触)、首触自动全屏
- ✅ **开机自启动**：`BootReceiver.kt` + `RECEIVE_BOOT_COMPLETED` + 设置页开关(`StartOnBoot.kt`)
- ✅ **无障碍引导弹窗**：`ScreenStreamContent.kt` 启动1.5s检测 → 3步引导弹窗 + 一键跳转设置
- ✅ **Shizuku/自ADB研究**：方案已记录Memory，Phase 2待集成Shizuku API
- ✅ **竞品分析**：scrcpy/ToDesk/向日葵功能对比 + 优先整合清单已记录Memory
- 📝 FEATURES.md 更新到82条功能登记

### 竞品功能整合（v33+，scrcpy/ToDesk/AIYA 参考）
- ✅ **Ctrl+拖拽捏合缩放**：scrcpy 核心功能移植，桌面端 Ctrl+点击拖拽模拟双指缩放
- ✅ **快捷键帮助面板**：F1/? 一键查看所有快捷键，分类展示（导航/系统/视图/工具/触控）
- ✅ **FPS/延迟统计覆层**：Alt+I 切换实时 FPS 计数 + 延迟测量（连接质量可视化）
- ✅ **Gamepad 手柄支持**：Gamepad API 自动检测，A/B/X/Y=点击/返回/主页/任务，D-Pad=滑动，摇杆=连续滑动，L1/R1=音量
- ✅ **PiP 画中画模式**：Alt+Shift+P 进入浏览器画中画（H264/H265 流）
- ✅ **截屏到剪贴板**：Alt+K 截取当前画面，优先复制到剪贴板，回退为 PNG 下载
- ✅ **显示旋转**：Alt+←/→ 旋转画面 90°/180°/270°（CSS Transform）
- ✅ **1:1 像素模式**：Alt+G 切换原始像素显示（无缩放 object-fit）
- ✅ **Ctrl+↑↓ 音量**：scrcpy 兼容 Ctrl+Arrow 音量快捷键
- ✅ **保持唤醒 API**：`/stayawake` WakeLock 管理（scrcpy -w 风格）
- ✅ **显示触控点 API**：`/showtouches` 系统设置切换
- ✅ **屏幕旋转 API**：`/rotate/{degrees}` 支持 0/90/180/270
- ✅ **增强设备信息**：WiFi SSID/信号/速度、运行时间、stayAwake/showTouches/inputEnabled 状态
- 📝 FEATURES.md 更新到95条功能登记

### 全市场竞品功能大整合（v33++，12+竞品参考）
> 参考源：scrcpy v3.3.4 / TeamViewer / AnyDesk / KDE Connect / Phone Link / AirDroid Cast / Parsec / Moonlight / DroidCam / 向日葵 / 幕享 / 乐播 / SpaceDesk

**后端新增 11 个 API（InputService + InputRoutes）：**
- ✅ **媒体控制** `/media/{action}` — play/pause/next/prev/stop/rewind/forward（KDE Connect 风格）
- ✅ **找手机** `/findphone/{true|false}` — 最大音量响铃，30秒自动停止
- ✅ **振动设备** `/vibrate` — 自定义时长振动
- ✅ **手电筒** `/flashlight/{true|false}` — 闪光灯开关
- ✅ **免打扰** `/dnd/{true|false}` — Do Not Disturb 模式切换
- ✅ **精确音量** `/volume` — 指定stream(music/ring/alarm等)和级别
- ✅ **自动旋转** `/autorotate/{true|false}` — 陀螺仪自动旋转开关
- ✅ **前台应用** `/foreground` — 获取当前前台应用包名/类名
- ✅ **关闭应用** `/killapp` — back+back+home 退出前台应用
- ✅ **文件上传** `/upload` — Base64 编码文件上传到 Downloads
- ✅ **增强设备信息** `/deviceinfo` — WiFi SSID/信号/速度 + 运行时间 + stayAwake/showTouches/inputEnabled

**前端新增 12 项功能（index.html）：**
- ✅ **会话录制** — MediaRecorder API 录制投屏画面，WebM 格式自动下载
- ✅ **白板标注** — Canvas 覆层绘画，支持鼠标+触控，双击清除（AirDroid Cast / 教学场景）
- ✅ **拖放文件上传** — HTML5 Drag&Drop 拖拽文件到投屏区域直接上传到设备
- ✅ **QR 码连接** — 生成当前 URL 的 QR 码，手机扫码即连（向日葵/AirDroid 风格）
- ✅ **游戏模式** — 隐藏所有 UI 覆层，最大化画面（Parsec/Steam Link 风格）
- ✅ **主题切换** — 深色/浅色主题一键切换
- ✅ **会话计时器** — 命令菜单实时显示连接时长
- ✅ **电池小组件** — 右上角实时电量百分比 + 充电状态指示
- ✅ **连接历史** — localStorage 自动记录最近 20 次连接
- ✅ **命令菜单大扩展** — 新增"设备控制"分类（9个按钮）+ 投屏设置扩展（7个）+ 远程工具扩展（12个）
- ✅ **文件选择上传** — 菜单按钮选择本地文件上传到设备
- ✅ **快捷键帮助优化** — 菜单底部提示 F1 查看全部快捷键

**编译验证：BUILD SUCCESSFUL（53秒）**
- 📝 FEATURES.md 更新到 119+ 条功能登记

### 2.3) v34 — S33 远程文件管理器 + 小模块批量实施（2026-02-14）

**S33 远程文件管理器（大模块 · 评分25.0 · P0优先级）：**
- ✅ **后端 11 个方法** — `InputService.kt`: sanitizePath安全沙箱 + listFiles(排序/隐藏) + getFileInfo + createDirectory + deleteFile(递归) + renameFile + moveFile + copyFile(递归) + readTextFile(≤512KB) + readFileBase64(≤10MB) + searchFiles(深度8) + getStorageInfo
- ✅ **12 个 REST API** — `InputRoutes.kt`: GET /files/storage, /files/list, /files/info, /files/read, /files/download, /files/search + POST /files/mkdir, /files/delete, /files/rename, /files/move, /files/copy, /files/upload
- ✅ **全屏文件管理面板** — `index.html` 400+行：面包屑导航 + 工具栏(上级/刷新/新建/上传/隐藏/排序) + 快速访问(DCIM/Download等) + 文件列表(图标/大小/日期/操作) + 图片预览 + 文本预览 + 文件搜索 + 下载 + 批量上传 + 剪切/复制/粘贴 + 存储统计 + Alt+E快捷键
- ✅ **安全设计** — sanitizePath沙箱限制在ExternalStorage内，防止路径遍历攻击

**小模块批量实施（7个模块 · 20项新功能）：**
- ✅ M12 画面工具 — 镜像/灰度/反色滤镜/缩放(50%-300%)/重置
- ✅ M15 效率工具 — 文本片段(预定义+自定义)/连接信息/流量统计
- ✅ M16 宏导出导入 — JSON导出全部/文件导入
- ✅ M18 截屏增强 — 含标注截屏/时间水印/计数器/ISO文件名

- 📝 FEATURES.md 更新到 150 条功能登记
- 📝 评价体系建立: NEEDS_v2_评价体系.md（5维度加权打分 · 42大+22中模块全量排序）

### 宏持久化（2026-02-15）
- ✅ **MacroEngine 文件持久化** — `context.filesDir/macros.json`，原子写入（tmp+rename）
- ✅ **自动加载** — `InputService.onServiceConnected()` 调用 `MacroEngine.init(context)`
- ✅ **CRUD 自动保存** — create/update/delete 后自动 `saveToDisk()`
- ⏳ 待编译验证（当前机器无 JAVA_HOME）

### 宏系统触发器（Phase 2）✅
- MacroEngine 新增触发引擎：notification / app_switch / timer 三种触发类型
- InputService 集成：通知事件 + 前台应用切换自动喂入触发引擎
- 5秒冷却防止重复触发，定时器最小间隔10秒
- API 路由：GET /macro/triggers, POST /macro/trigger/{id}, POST /macro/trigger/{id}/remove
- 前端 UI：宏列表显示触发状态图标，点击打开触发器配置面板
- 触发器随宏 JSON 一起持久化到 macros.json
- ⏳ 待编译验证

### 前端安全与 Bug 修复 ✅
- 修复 3 处 XSS 漏洞（clipboard/appList/viewTree 加 escapeHtml）
- 修复 CSS transform 冲突（rotate + mirror/zoom 合并）
- 修复 batteryWidget 与 controlStatus 位置重叠
- 修复 GameMode 不恢复 perfOverlay 状态

## 3) 进行中

- **合并/归档差异清单**：Quest vs v2 逐目录对照 — app/ 已完成（9条）

## 4) 下一步（按优先级）

1. **Shizuku API集成**：自动启用无障碍服务（无需手动设置）
2. **OTG纯控模式**：无屏幕投射的纯键鼠控制模式
3. **Quest 日志移植**：AppLogger + CollectingLogsUi（需添加 ProcessPhoenix 依赖）
5. **评估 .so 动态库寄生方案**（长期研究项）

## 5) 风险与护栏

- 端口/入口/鉴权策略属于架构级决策：必须先落 ADR 再改代码
- 构建/签名/发布：禁止隐式改动除非任务明确要求
- **全局配置修改铁律**：影响评估 → 备份 → 验证（参见 execution-engine.md）
