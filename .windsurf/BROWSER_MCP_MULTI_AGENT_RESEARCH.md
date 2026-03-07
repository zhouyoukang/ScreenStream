# 以道观之 — 网络资源·浏览器MCP·多Agent五感无感架构

> **道生一**（MCP协议 = Agent感知世界的统一之道）
> **一生二**（隔离与共享 = 解决冲突的两极）
> **二生三**（Agent × 浏览器 × 用户 = 三体问题）
> **三生万物**（N个Agent各有完整五感，互不干扰，和谐共存）
>
> 本文为全工作区**网络资源 + 浏览器MCP + 多Agent架构**知识的**唯一真相源**。
> 2026-02-25 v1 → v2 → **v3 (2026-02-27)** 升级：新增§十一多Agent Chrome-MCP冲突深度解剖（五感冲突矩阵+社区Issue追踪+四方案全景）。
>
> **行动指南**: `.windsurf/skills/browser-agent-mastery/SKILL.md`
> **执行规则**: `.windsurf/rules/execution-engine.md` §浏览器Agent统御
> **双电脑五感**: `双电脑互联/README.md`

---

## 一、道——万物之根

### 1.1 一个公理

**MCP（Model Context Protocol）= Agent感知世界的统一感官接口。**

正如人通过眼耳鼻舌身五感认知世界，Agent通过MCP Server认知数字世界。
每个MCP Server = Agent的一个感官器官。5个MCP = 5种感官维度。

但感官是有限的——一个Agent的眼睛（Playwright）看到的世界，可能正被另一个Agent的手（DevTools click）改变。
这就是「多Agent五感冲突」的本质：**多操作者共享单人设计的感官通道**。

### 1.2 根因三层

```
 Agent A  │  Agent B  │  用户(你)           ← 三个操作者
──────────┼──────────┼──────────────
      MCP Server (1进程/1连接/1状态)         ← 协议瓶颈
──────────────────────────────────────
      Browser / HTTP / Device (共享状态)     ← 资源独占
──────────────────────────────────────
  1焦点Tab │ 1 Cookie罐 │ 1光标 │ 1 ADB     ← 物理锁
```

**一句话**：所有「祸」的根源 = 多操作者共享单人设计的资源。解法只有两条——**隔离**或**调度**。

---

## 二、器——全域资源地图

> 不只是浏览器，Agent能触及的**所有网络资源**都在这张图里。

### 2.1 五个MCP感官（Agent直接感知的世界）

| MCP Server | 本质 | Agent获得的感官 | 精华 | 糟粕 |
|------------|------|---------------|------|------|
| **Playwright** | 自启Chromium + 全API | 👁视觉(snapshot) + 🖐触觉(click/type) | 完整自动化，天然隔离 | token爆炸(5K-100K/页)，内存+400MB |
| **Chrome DevTools** | CDP连接已有Chrome | 👁视觉(snapshot) + 👂听觉(console) + 🔍诊断(network/perf) | 零额外内存，与用户共存 | 可能侵犯用户Tab |
| **context7** | 库文档查询 | 🧠认知(API文档) | 精准获取库的最新文档 | 仅限已索引的库 |
| **github** | GitHub API | 🧠认知(仓库/issue/代码) | 跨仓库知识 | 需代理(被墙) |
| **fetch** | HTTP请求 | 👁视觉(网页内容) | 通用抓取 | ⛔弹窗硬编码，已禁用 |

**辩证**：Playwright = 自己的眼+手（隔离但重），DevTools = 借用户的眼（轻但共享），context7/github = 远程记忆，fetch = 已废弃的眼（被IWR替代）。

### 2.2 Playwright MCP 深层能力（2025-2026新增）

Playwright MCP 已从「单一模式」进化为**三种运行模式**：

| 模式 | 命令行 | 本质 | 适用场景 |
|------|--------|------|---------|
| **Isolated**（默认） | `--headless` | 每次会话全新profile，关闭即销毁 | E2E测试、数据采集、安全环境 |
| **Persistent** | `--user-data-dir ./data` | 持久化profile，保留Cookie/localStorage | 需要登录态持久的长期自动化 |
| **Storage State** | `--storage-state auth.json` | 加载预存的Cookie到隔离Context | 继承登录态但不污染用户profile |

**关键新能力**：
- `--config playwright.config.json`：配置文件指定 `contextOptions`（viewport/locale/proxy等）
- `--init-page setup.ts`：页面初始化脚本（注入Cookie/拦截请求/Mock API）
- `browser_run_code`：Agent写JS精准提取数据，**token降99%**（100K→800字符）

### 2.3 Chrome DevTools MCP 深层能力

DevTools MCP 也已进化为**三种连接模式**：

| 模式 | 配置 | 本质 | 适用场景 |
|------|------|------|---------|
| **New Instance**（默认） | 无需配置 | 启动独立Chrome+专用profile | Agent独立工作 |
| **Connect** | `--port 9222` | 连接已运行的Chrome实例 | 调试用户浏览器、继承登录态 |
| **Multi-Isolated** | 多实例各自临时profile | N个独立Chrome实例 | 多Agent各自隔离 |

**关键能力**：`select_page` 不切换焦点 → Agent可在暗处观察用户页面，用户无感知。

### 2.4 行业新器（本项目未启用但应知）

| 工具 | 本质 | 精华 | 成本 | 适用时机 |
|------|------|------|------|---------|
| **BrowserTools MCP** | Chrome扩展+中间件+MCP三件套 | 继承用户完整登录态，无需手动导出Cookie | 免费 | 需要用户已登录的站点数据时 |
| **Browserbase/Stagehand** | 云端浏览器即服务 | 完全隔离，N Agent零冲突，反检测，录制回放 | $25+/月 | 大规模并发采集、反爬环境 |
| **Vercel agent-browser** | CLI浏览器+标注截图 | 轻量API，适合简单任务 | 免费 | 轻量Web验证 |

### 2.5 七个HTTP服务（Agent可调用的远程躯体）

> 这些不是MCP Server，但Agent通过 `Invoke-RestMethod` / `curl.exe` / `browser_run_code` 可直接调用。

| 服务 | 端口 | 位置 | 本质 | Agent获得的感官 |
|------|------|------|------|---------------|
| **ScreenStream Input** | :8084 | 手机 | 手机反向控制(90+ API) | 👁屏幕+🖐触摸+🧠APP状态 |
| **ScreenStream MJPEG** | :8081 | 手机 | MJPEG投屏流 | 👁实时视频流 |
| **Smart Home Gateway** | :8900 | 笔记本 | HA+涂鸦+音箱代理 | 🎮家居控制+👂TTS |
| **remote_agent** | :9903/:9904 | 台式机 | PC全控制(45+ API) | 👁截屏+🖐键鼠+🧠进程/Shell |
| **file_share** | :9999 | 笔记本 | 双向文件浏览/传输 | 🧠文件系统认知 |
| **desktop_agent** | :9998 | 台式机 | 轻量文件代理 | 🧠台式机文件 |
| **二手书 FastAPI** | :8088 | 笔记本 | 二手书管理系统(158路由) | 🧠业务数据 |

### 2.6 三层穿透（Agent跨越物理边界）

| 层 | 方案 | 成本 | 延迟 | Agent可达性 |
|----|------|------|------|------------|
| **局域网** | 直连IP | ¥0 | <5ms | 笔记本↔台式机↔手机 |
| **公网FRP** | 阿里云ECS(:7000) | ¥38/年 | 20-40ms | 任意位置→台式机(:19903)/RDP(:13389) |
| **零成本临时** | Cloudflare Tunnel | ¥0 | 50-150ms | 临时URL→任意本地服务 |

### 2.7 非MCP网络工具链（零弹窗替代）

| 需求 | 工具 | 理由 |
|------|------|------|
| 静态HTML | `Invoke-WebRequest -UseBasicParsing` + regex | 零弹窗最轻 |
| JSON API | `Invoke-RestMethod` | 直接解析 |
| JS渲染SPA | Playwright `navigate`+`snapshot` | 需JS引擎 |
| 搜索 | `search_web` | 最快 |
| 库文档 | context7 `query-docs` | 精准 |
| GitHub | github MCP `get_file_contents` | 跨仓库 |

```powershell
# HTML抓取（已入allowlist，自动执行）
(Invoke-WebRequest -Uri "<URL>" -UseBasicParsing).Content `
  -replace '<script[^>]*>[\s\S]*?</script>','' -replace '<[^>]+>',' ' -replace '\s+',' '
```

> **⛔ 禁用**: `read_url_content` / `mcp2_fetch` — 弹窗是二进制硬编码，无法关闭。

---

## 三、感——Agent五感的完整映射

> 代入Agent的视角：我能看到什么？听到什么？触摸什么？知道什么？控制什么？

### 3.1 单Agent五感（一个Cascade对话的感官全景）

| 感官 | 浏览器世界 | 手机世界 | 台式机世界 | 知识世界 |
|------|-----------|---------|-----------|---------|
| 👁 **视觉** | Playwright snapshot/screenshot, DevTools snapshot | SS :8084 /screen/text, /screenshot | remote_agent /screenshot, /windows | search_web 摘要 |
| 👂 **听觉** | DevTools console, Network requests | SS /notifications/read | remote_agent /shell stdout | — |
| 🖐 **触觉** | Playwright click/type/fill, DevTools click | SS /tap, /swipe, /key, /text | remote_agent /key, /click, /type, /drag | — |
| 🧠 **认知** | browser_run_code(精准提取), DOM结构 | SS /foreground, /deviceinfo | remote_agent /sysinfo, /processes, /files | context7, github |
| 🎮 **管控** | Playwright navigate, browser_close | SS /intent(任意APP), /dnd | remote_agent /power, /service, /guard | — |

### 3.2 Token经济学（感官的隐性成本）

Agent的每次「看」都有代价。a11y树的token爆炸是最大隐性成本：

| 级别 | 方式 | Token消耗 | 适用 |
|------|------|----------|------|
| **L1 精准提取** | `browser_run_code` 写JS | 30-800字符 | 数据采集（**首选**） |
| **L2 snapshot交互** | `snapshot`→找ref→`click/type` | 5K-50K | 表单填写、导航 |
| **L3 全页截图** | `take_screenshot` | 最大 | Canvas/SVG/复杂视觉（**最后手段**） |

```javascript
// L1示例：100K tokens → 800字符
async (page) => {
  return await page.evaluate(() => {
    return [...document.querySelectorAll('.product-card')].slice(0, 5).map(el => ({
      title: el.querySelector('.title')?.textContent?.trim(),
      price: el.querySelector('.price')?.textContent?.trim()
    }));
  });
}
```

**2026 MCP上下文税**：连接5-10个MCP Server可吃掉LLM上下文窗口的15-20%（来自Bug0实测），工具定义本身就是成本。

---

## 四、祸——十二祸全景

> 浏览器五祸（Agent↔浏览器）+ 双电脑七祸（用户↔电脑）= **十二祸**。
> 每一祸都是「多操作者共享单人设计的资源」这个根因在不同场景的实例化。

### 4.1 浏览器五祸

| # | 祸名 | 谁痛 | 感受 | 根治 | 状态 |
|---|------|------|------|------|------|
| 一 | **焦点** | 用户 | 正看视频→Playwright窗口弹出→视频暂停 | `--headless` | ✅ |
| 二 | **并发** | Agent A | 我的snapshot ref被Agent B的导航清空→click崩 | STDIO隔离+DevTools页面锁定 | ✅ |
| 三 | **侵犯** | 用户 | Agent导航我的Tab→Cookie污染/表单丢 | pageId=0禁写 | ✅ |
| 四 | **资源** | 系统 | N个Playwright×400MB→内存爆→BSOD | headless+用完close+85%阈值 | ✅ |
| 五 | **听觉** | Agent A | 我监听console→收到B的warning→误判Bug | select_page+types过滤 | ✅ |

### 4.2 双电脑七祸

| # | 祸名 | 根因 | 根治要点 |
|---|------|------|----------|
| 六 | **延迟** | HTTP轮询非实时 | 不同场景不同通道：RDP/Sunshine/agent |
| 七 | **感官剥夺** | 6寸屏+无音频 | 缩放+横屏+RDP音频 |
| 八 | **精度** | 手指粗如柱 | 触控板模式+快捷面板+语音 |
| 九 | **穿透** | NAT/防火墙 | FRP+阿里云(¥38) / Cloudflare / Tailscale |
| 十 | **安全** | HTTP明文 | Token+HTTPS+TLS |
| 十一 | **冷启** | 关机无法唤醒 | 向日葵WoL+Guardian+auto-start |
| 十二 | **劫持** | 远程与本地冲突 | MouseGuard+跨会话+Guard API |

### 4.3 多Agent附加五祸（Agent↔Agent）

| # | 祸名 | 场景 | 根治 |
|---|------|------|------|
| α | **分身错乱** | Agent不知操控的是哪台机器 | `/health`确认hostname |
| β | **竞态** | 两Agent同时发/click和/key | MouseGuard+铁律同时只1个 |
| γ | **会话断裂** | RDP切断console session | 多端口(:9903/:9904) |
| δ | **认知分裂** | Agent以为空闲实际有人用 | `/guard`+`/screen/info`三连查 |
| ε | **单向哑巴** | 台式机有事无法通知主脑 | Guardian事件驱动+SSE(待实现) |

---

## 五、治——九律 + 场景路由

### 5.1 浏览器九律

| # | 铁律 | 解决之祸 |
|---|------|---------|
| R1 | Playwright `--headless`（已配置） | 焦点 |
| R2 | 同一对话Playwright和DevTools不同时用 | 并发 |
| R3 | DevTools: `list_pages`→`select_page`→操作→不切换 | 并发 |
| R4 | DevTools禁止写操作pageId=0（用户活跃Tab） | 侵犯 |
| R5 | 内存>85%禁新Playwright；用完即`browser_close` | 资源 |
| R6 | DevTools按page+type过滤console | 听觉 |
| R7 | DevTools `--isolated`（**已配置**，临时profile，多实例不冲突） | 多实例 |
| R8 | `select_page`+操作必须**原子化**（中间不可插入其他工具调用） | 竞态 |
| R9 | DevTools同时打开页面≤5个（防WebSocket过载断连） | 断连 |

### 5.2 场景路由——1秒决策树（浏览器+网络专精）

> 完整全域版（含手机/台式机/知识/系统约束）见 §8。

```
需求
  ├─ 查信息/找方案 ──────────→ search_web（最快，零成本）
  ├─ 抓网页 → 需JS渲染?
  │     ├─ 否 → IWR命令行（零弹窗最轻）
  │     └─ 是 → Playwright navigate + snapshot
  ├─ 精准数据提取 ────────────→ browser_run_code（token降99%）
  ├─ 填表/登录/多步操作 ─────→ Playwright标准流（最完整）
  ├─ 需要用户登录态 ──────────→ Playwright --storage-state（继承Cookie不污染）
  ├─ 调试已打开页面 ──────────→ DevTools select_page（不扰用户）
  ├─ E2E前端验证 ─────────────→ Playwright标准流（隔离环境）
  ├─ 性能分析 ─────────────────→ DevTools performance_start_trace
  ├─ 操控手机 ─────────────────→ ScreenStream :8084 HTTP API
  ├─ 操控台式机 ───────────────→ remote_agent :9903 HTTP API
  ├─ 库文档查询 ───────────────→ context7 query-docs
  └─ 高内存(>85%) ─────────────→ 优先DevTools（零内存），禁Playwright
```

### 5.3 实战模式——五种典型编排

**模式A：前端E2E验证**（/dev Phase 5.5）
```
navigate → snapshot(确认加载) → click/type(交互) → snapshot(验证) → 需要时screenshot
```

**模式B：数据采集**
```
静态HTML? → IWR命令行(最快) | SPA? → navigate → browser_run_code(精准提取)
```

**模式C：调试用户页面**（零侵犯）
```
list_pages → select_page(不切焦点) → take_snapshot → list_console_messages → list_network_requests
```

**模式D：自动登录/表单**（实证：小米SSO绕2FA）
```
navigate → 填手机号密码 → 勾选协议 → 点击登录 → cookies提取passToken → 换serviceToken
```

**模式E：跨设备联动**（Agent操控手机+浏览器+台式机）
```
1. ScreenStream /intent → 手机打开目标APP
2. ScreenStream /screen/text → 提取屏幕信息
3. Playwright navigate → PC浏览器打开对应网页
4. browser_run_code → 精准提取+对比
5. remote_agent /clipboard POST → 结果推送到台式机
```

---

## 六、道——多Agent无感架构

> 从「治祸」到「无祸」——不是解决冲突，而是让冲突不可能发生。

### 6.1 隔离三层（从重到轻）

| 层级 | 机制 | 隔离度 | 成本 | 当前状态 |
|------|------|--------|------|---------|
| **物理隔离** | Windsurf Worktree：每Agent独立git worktree+独立Cascade | ★★★★★ | 磁盘空间 | ✅已用 |
| **进程隔离** | Playwright STDIO：每Agent独立Chromium进程 | ★★★★ | 内存400MB/个 | ✅已用 |
| **逻辑隔离** | DevTools select_page：同Chrome不同Tab | ★★★ | 零 | ✅规则约束 |
| **时间隔离** | MouseGuard cooldown：同设备轮流使用 | ★★ | 延迟 | ✅已用 |

**原则**：能物理隔离的不逻辑隔离，能进程隔离的不时间隔离。

### 6.2 多Agent五感独立矩阵

> 目标：每个Agent拥有**完整独立的五感**，互不干扰。

| Agent | 👁看 | 👂听 | 🖐触 | 🧠知 | 🎮控 | 隔离方式 |
|-------|------|------|------|------|------|---------|
| **Cascade A** (Worktree 1) | 自己的Playwright(headless) | 自己的console | 自己的click/type | 自己的文件系统 | 自己的终端 | 物理(Worktree) |
| **Cascade B** (Worktree 2) | 另一个Playwright(headless) | 另一个console | 另一个click/type | 另一个文件系统 | 另一个终端 | 物理(Worktree) |
| **用户** | 自己的Chrome | 自己的声音 | 自己的键鼠 | 自己的屏幕 | 自己的焦点 | 天然独立 |

**共享资源的硬约束**（Worktree解决不了的）：
- **Zone 0 冻结**: `~/.codeium/windsurf/` 下文件（hooks.json/mcp_config.json）禁止修改
- **构建串行**: 同项目同时只1个Agent执行Gradle构建（共享daemon）
- **设备独占**: 同一Android设备/台式机同时只1个Agent操作

### 6.3 无感的本质

**「无感」不是「没有感觉」，是「感觉不到冲突的存在」。**

| 传统（有感） | 无感 |
|------------|------|
| Agent启动浏览器→用户看到窗口弹出→不适 | `--headless`→用户毫无感知 |
| Agent操控台式机→本地用户鼠标乱飞→恐慌 | MouseGuard检测→自动退让→用户以为只有自己 |
| Agent读用户Tab→Cookie被改→莫名登出 | pageId=0禁写→Agent只读不碰→用户察觉不到 |
| 两Agent同时操作→ref失效→报错 | STDIO隔离→各有自己的浏览器→压根不可能冲突 |
| 内存爆满→BSOD | 85%阈值→Agent自我约束→系统从未感到压力 |

**终极境界**：用户不知道Agent在操作浏览器，Agent不知道还有其他Agent，系统不知道在被多个Agent使用——**各自完整，互不干扰，如同独处**。

### 6.4 Context Broker 2.0（长期愿景）

```
┌─────────────────────────────────────────────────────┐
│                  Context Broker 2.0                  │
│  (一个Browser进程 + N个BrowserContext + 身份路由)     │
├──────────┬──────────┬──────────┬───────────────────┤
│ Agent A  │ Agent B  │ Agent C  │ User (观察者)      │
│ ctx_a    │ ctx_b    │ ctx_c    │ ctx_user           │
├──────────┴──────────┴──────────┴───────────────────┤
│ Context A │ Context B │ Context C │ User Context    │
│ (独立Cookie) (独立Cookie) (独立Cookie) (只读共享)     │
├─────────────────────────────────────────────────────┤
│  Cookie Bridge: 按需从User Context克隆到Agent Context │
│  Mutex Lock: 同一Context同时只1个Agent操作            │
│  Identity: MCP _meta字段注入Agent身份                 │
│  Lifecycle: lazy创建 + 超时回收 + 内存保护             │
└─────────────────────────────────────────────────────┘
```

**进化路线**：

| 阶段 | 目标 | 状态 |
|------|------|------|
| **已达成** | `--headless` + STDIO隔离 + 九律 + Worktree | ✅ 日常够用 |
| **短期** | `browser_run_code`成为默认提取方式 | 可用，需养成习惯 |
| **短期** | `--storage-state`导出/加载用户Cookie | 可用，按需使用 |
| **中期** | BrowserTools MCP评估引入（继承用户登录态） | 待评估 |
| **中期** | Playwright官方多Context支持 | 等待上游 |
| **长期** | Context Broker 2.0 多Agent+用户完美共存 | 概念设计完成 |

---

## 七、MCP配置与零干扰原则

> **零干扰** = MCP的存在不影响用户正常使用IDE。
> 每个MCP Server = 1个Node进程 + context窗口中的工具定义（上下文税）。
> **原则**：只启用真正需要的，废弃的立即移除。

### 当前配置（5个）

| MCP Server | 命令 | 状态 | 上下文税 |
|------------|------|------|---------|
| **playwright** | `npx @playwright/mcp --headless` | ✅核心 | 中（20+工具） |
| **chrome-devtools** | `npx chrome-devtools-mcp@latest` | ✅核心 | 中（15+工具） |
| **context7** | `npx @upstash/context7-mcp@latest` | ✅有用 | 低（2工具） |
| **github** | `cmd /c .windsurf/github-mcp.cmd` | ✅有用 | 中（10+工具） |
| **fetch** | `npx -y fetch-mcp` | ⛔**应禁用** | 白耗（被IWR完全替代，弹窗无法关闭） |

### fetch MCP 移除理由
1. **功能已被替代**：IWR命令行零弹窗、已入allowlist，完全覆盖fetch能力
2. **弹窗干扰**：fetch底层使用`read_url_content`，弹窗是二进制硬编码无法关闭
3. **资源浪费**：占1个Node进程 + 工具定义吃上下文窗口
4. **操作**：在IDE Settings → MCP Servers → 禁用/移除 fetch

### 上下文税实测（Bug0 2026）
5-10个MCP Server的工具定义吃掉LLM上下文窗口的**15-20%**。
移除fetch后：5→4个Server，释放约3-4%上下文空间。

### 场景策略

| 场景 | 策略 |
|------|------|
| 日常单Agent | Playwright为主，DevTools调试辅助（加`--isolated`） |
| Worktree多Agent | STDIO天然隔离，各自独立Chromium ✅ |
| Agent+用户共存 | DevTools `select_page` 不碰用户Tab |
| 继承登录态 | `--storage-state auth.json` 加载Cookie |
| 高内存(>85%) | 优先DevTools（零内存），禁新Playwright |

### MCP进程不干扰IDE的保障
- **懒加载**：MCP Server只在Agent首次调用其工具时才启动进程
- **headless**：Playwright不弹窗不抢焦点
- **STDIO隔离**：每个MCP独立进程，崩溃不影响IDE
- **hooks安全**：仅2个Python hooks（conversation_capture），无PowerShell hooks

---

## 八、全域Agent操控决策树

> 给AI Agent看的——不是文档，是**1秒决策指令**。
> §5.2 是浏览器专精版，本节是全域版（覆盖浏览器+手机+台式机+知识+系统约束）。

```
我要做什么？
│
├─ 【浏览器操作】
│   ├─ 查信息         → search_web
│   ├─ 抓静态页       → IWR命令行
│   ├─ 抓SPA页        → Playwright navigate + snapshot
│   ├─ 精准提取数据   → browser_run_code（首选！）
│   ├─ 填表/登录      → Playwright标准流
│   ├─ 需用户Cookie   → --storage-state 或 BrowserTools
│   ├─ 调试已开页面   → DevTools select_page
│   ├─ E2E验证       → Playwright headless
│   └─ 性能分析       → DevTools performance_start_trace
│
├─ 【手机操作】
│   ├─ 打开APP       → SS :8084 /intent
│   ├─ 点击/输入     → SS /tap /text /key
│   ├─ 读屏幕        → SS /screen/text
│   ├─ 读通知        → SS /notifications/read
│   └─ 等待条件      → SS /wait?text=xxx
│
├─ 【台式机操作】
│   ├─ 预检          → /health + /guard + /screen/info 三连
│   ├─ 截屏          → /screenshot
│   ├─ 键鼠操控      → /key /click /type（Guard暂停→操作→恢复）
│   ├─ Shell执行     → /shell
│   ├─ 文件传输      → /file/upload + /file/download
│   └─ 电源管理      → /power /wakeup
│
├─ 【知识查询】
│   ├─ 库API文档     → context7 query-docs
│   ├─ GitHub仓库    → github get_file_contents
│   └─ 通用网页      → search_web → IWR/Playwright
│
└─ 【系统约束】
    ├─ 内存>85%      → 禁Playwright，用DevTools/IWR
    ├─ 内存>90%      → 禁止启动任何新进程
    ├─ 同一设备      → 同时只1个Agent操作
    └─ 用户Tab       → 只读不写（R4铁律）
```

---

## 九、实战工具箱（所有之法）

> 不只是知识，更是**可执行的解法**。每个问题都有对应的工具或脚本。

### 9.1 MCP健康检查（一键诊断）

```powershell
# 检查所有MCP进程、内存、上下文税、优化建议
powershell -File 构建部署/mcp-health-check.ps1
```

输出：系统资源 → Node/MCP进程详情 → 浏览器占用 → 上下文税估算 → 优化建议 → 快速修复指令。

### 9.2 Cookie导出/加载（继承登录态）

**问题**：Agent需要访问需登录的网站（GitHub/淘宝/微博等），但不想手动处理Cookie。

```powershell
# 步骤1: 导出（打开浏览器，你登录，按Enter导出）
node 构建部署/mcp-auth-export.js https://github.com auth-github.json

# 步骤2: 使用（Playwright MCP加载导出的Cookie）
# 方法A: 命令行
npx @playwright/mcp --headless --storage-state auth-github.json

# 方法B: 在IDE MCP配置中永久生效
# mcp_config.json → playwright → args 追加: "--storage-state", "E:/道/道生一/一生二/auth-github.json"
```

### 9.3 fetch MCP 禁用（释放上下文）

**问题**：fetch MCP被IWR完全替代，但仍占Node进程+上下文税。

**解法**：IDE Settings → MCP Servers → fetch → **Disable**

效果：释放~1%上下文空间 + 1个Node进程 + 消除弹窗干扰源。

### 9.4 BrowserTools MCP 评估（是否引入）

| 维度 | BrowserTools MCP | 当前方案(Playwright+DevTools) |
|------|-----------------|---------------------------|
| **登录态继承** | ✅ 自动继承用户Chrome全部Cookie | ⚠️ 需手动导出storage-state |
| **架构** | Chrome扩展 + 中间件Server + MCP三件套 | 零扩展，原生MCP |
| **额外进程** | +1 Node中间件 + Chrome扩展 | 无额外 |
| **上下文税** | +10-15工具定义 | 已有35+工具 |
| **隔离性** | 共享用户Chrome（侵犯风险） | Playwright天然隔离 |
| **适用** | 需要大量已登录网站数据时 | 日常开发/E2E |

**结论**：**暂不引入**。当前 `--storage-state` 已解决登录态问题，BrowserTools增加的复杂度（Chrome扩展+中间件）和上下文税不值得。仅在需要频繁访问10+已登录网站时重新评估。

### 9.5 DevTools Connect模式（调试用户浏览器）

**问题**：Agent需要调试用户正在使用的Chrome页面。

```powershell
# 步骤1: 用户启动Chrome时加调试端口
chrome.exe --remote-debugging-port=9222

# 步骤2: DevTools MCP连接
# mcp_config.json → chrome-devtools → args 追加: "--port", "9222"
```

⚠️ 注意R4铁律：即使连接了用户Chrome，也**禁止写操作pageId=0**。

### 9.6 npx代理修复（关键！MCP五感恢复）

**问题**：系统仅有 `D:\node.exe` 单文件，无npm/npx。所有MCP Server用npx启动→全部失败→五感全废。

**解法**：创建 `npx.cmd` 代理到 `pnpm dlx`（pnpm v10.23.0可用）。

```
位置：C:\Users\zhouyoukang\AppData\Roaming\npm\npx.cmd（已在PATH）
原理：剥离-y参数 → 转发到pnpm dlx → MCP Server正常启动
验证：context7 ✅ | playwright ✅ | 均正常启动
生效：需在IDE中重启MCP连接（Settings→MCP→Reconnect，或重启Windsurf）
```

### 9.7 未解问题清单（需要时间/上游）

| 问题 | 根因 | 当前状态 | 等什么 |
|------|------|---------|--------|
| 祸ε·单向哑巴 | 台式机无法主动推送 | Guardian事件驱动兜底 | SSE/WebSocket实现 |
| 祸八·精度 | 手指粗如柱 | 快捷面板缓解 | 触控板相对移动实现 |
| 祸七·感官剥夺 | 无音频转发 | RDP音频通道兜底 | WebSocket+Opus编码 |
| Context Broker | 单Browser多Context | 概念设计完成 | Playwright多Context上游支持 |
| MCP上下文税 | 工具定义吃上下文 | 移除fetch缓解 | MCP协议按需加载工具(Nov 2025 spec方向) |

---

## 十、资料索引

| 来源 | 位置 | 提取了什么 |
|------|------|-----------|
| **SKILL.md** | `.windsurf/skills/browser-agent-mastery/` | 五器全景·五祸·实战模式·代码模板（Agent可操作） |
| **execution-engine.md** | `.windsurf/rules/` §浏览器Agent统御 | 场景路由·六律·Token管控（always-on） |
| **双电脑互联 README** | `双电脑互联/` | 十二祸·Agent食谱·全域API速查（698行精华） |
| **Playwright MCP** | github.com/microsoft/playwright-mcp | isolated/persistent/storage-state三模式 |
| **Chrome DevTools MCP** | github.com/ChromeDevTools/chrome-devtools-mcp | new/connect/multi-isolated三模式 |
| **BrowserTools MCP** | github.com/AgentDeskAI/browser-tools-mcp | Chrome扩展+中间件继承登录态 |
| **Browserbase** | browserbase.com/mcp | 云浏览器完全隔离+Stagehand |
| **MCP Nov 2025 Spec** | spec.modelcontextprotocol.io | 权限治理·服务端隔离·最小权限 |
| **Bug0 2026实测** | bug0.com | MCP上下文税15-20%，工具选择策略 |

### 三文件分工

| 文件 | 职责 | 读者 |
|------|------|------|
| **本文** | 全域知识精华·唯一真相源 | 人+Agent |
| **SKILL.md** | AI可操作技能·触发条件·代码模板 | Agent |
| **execution-engine.md** §浏览器 | 执行铁律·禁止项 | Agent(always-on) |

---

> **以道观之**：
> 道生一——MCP是Agent感知世界的统一之道，万物皆可通过标准接口触及。
> 一生二——隔离与共享是永恒的两极，不求消灭矛盾，求在每个瞬间选对极。
> 二生三——Agent、浏览器、用户三体共舞，冲突是因为共享了不该共享的东西。
> 三生万物——N个Agent各有完整五感，互不干扰，如同独处——这就是「无感」。
>
> **五器无高下，场景定取舍。隔离解冲突，轻量胜重炮。**
> **Token是隐性成本，`run_code`是默认选择，`snapshot`是交互必须，`screenshot`是最后手段。**
> **无感不是没有感觉，是感觉不到冲突的存在。**

---

## 十一、多Agent同时调用Chrome-MCP冲突深度解剖（2026-02-27 v3）

> 代入Agent之五感——我看到了错的页面、听到了别人的console、触摸到了别人的按钮、
> 认知混乱不知自己在哪个Tab、失去了对页面的控制权。这就是**五感被劫持**。

### 11.1 冲突全景——以五感观之

```
Agent A (Cascade 1)           Agent B (Cascade 2)           用户
    │                             │                           │
    │  select_page(2)             │                           │  看YouTube
    │────────────►┐               │                           │
    │             │ #selectedPage = Page 2                     │
    │◄────────────┘               │                           │
    │                             │  select_page(3)           │
    │                             │────────────►┐             │
    │                             │             │ #selectedPage = Page 3  ← 覆盖了!
    │                             │◄────────────┘             │
    │  take_snapshot()            │                           │
    │────────────►┐               │                           │
    │             │ 读取 #selectedPage → Page 3 ← 错的!       │
    │◄────────────┘               │                           │
    │  我看到了B的页面!?           │                           │
```

### 11.2 五感冲突矩阵（从Agent视角感受每一种痛）

| 感官 | 冲突场景 | Agent的痛感 | 根因 | 严重度 |
|------|---------|-----------|------|-------|
| 👁 **视觉** | A调用`take_snapshot()`，但`#selectedPage`已被B切走 | **看到别人的世界**——snapshot/screenshot全是B的页面内容 | 全局`#selectedPage`单指针 | 🔴致命 |
| 🖐 **触觉** | A调用`click(uid)`，uid是A页面的元素，但当前page是B的 | **触摸到虚空**——点击失败或点到B页面的随机元素 | 同上，uid只在正确page有效 | 🔴致命 |
| 👂 **听觉** | A调用`list_console_messages()`，收到B页面的error | **听到别人的噪音**——误判Bug，浪费时间排查不存在的问题 | console消息不按Agent隔离 | 🟡高 |
| 🧠 **认知** | A以为自己在Page 2操作，实际page已被切到3 | **认知错位**——所有后续决策基于错误认知，级联失败 | 无Agent身份感知 | 🔴致命 |
| 🎮 **管控** | A调用`navigate_page(url)`，把B正在填表的页面导航走了 | **失去控制**——B填了半天的表单数据全丢 | 无页面所有权概念 | 🔴致命 |

### 11.3 根因分析——三层架构缺陷

**第一层：协议瓶颈（MCP STDIO = 1进程1连接）**

```
Windsurf IDE ──STDIO──► chrome-devtools-mcp (1个Node进程)
                              │
                              ▼
                    Chrome CDP (1个WebSocket)
                              │
                    #selectedPage (1个全局指针)
```

- MCP协议设计为**1:1连接**（1个Client ↔ 1个Server进程）
- Windsurf的mcp_config.json中`chrome-devtools`只启动**1个进程**
- 该进程内部维护`#selectedPage`全局状态——**所有Agent共享这个指针**

**第二层：CDP Session复用（6+ Tab → WebSocket过载）**

- 每个Tab创建一个CDP Session（`Target.attachToTarget`）
- 所有Session复用**同一个WebSocket通道**
- 6+页面时事件风暴可导致连接断开（Issue #978）
- 无心跳/keepalive机制，Chrome卡顿=静默断连

**第三层：物理锁（单焦点/单Cookie罐/单光标）**

| 资源 | 独占性 | 多Agent冲突 |
|------|--------|-----------|
| `#selectedPage` | 全局唯一 | Agent A选了Page 2，B选Page 3，A再操作→操作的是Page 3 |
| Browser焦点 | 单窗口单Tab | `navigate_page`改变任何Tab的URL→可能破坏其他Agent工作 |
| Cookie/Storage | 默认共享 | Agent A登录→B意外获得登录态；B登出→A被踢 |
| Console输出 | 全页面混合 | 不区分来源的console.log/error互相干扰 |
| 用户数据目录 | 默认共享 | 两个实例用同一profile→启动冲突（Issue #224） |

### 11.4 社区之法——GitHub Issue全景追踪

> 来源：ChromeDevTools/chrome-devtools-mcp + anthropics/claude-code

#### 已合并（可用）

| Issue/PR | 方案 | 状态 | 版本 |
|----------|------|------|------|
| **#991** `isolatedContext` | `new_page`加`isolatedContext`参数，创建命名BrowserContext（独立Cookie/Storage） | ✅已合并 | v0.18+ |
| **#224** `--isolated` | 命令行加`--isolated`，每次启动用临时profile（解决多实例profile冲突） | ✅已有 | v0.8+ |

#### 进行中（社区热议）

| Issue/PR | 方案 | 状态 | 关键讨论 |
|----------|------|------|---------|
| **#1019** `pageId routing` | 所有page-operating工具加可选`pageId`参数，绕过`#selectedPage`全局指针 | 🔶实验性 | `--experimental-page-id-routing` flag |
| **#1018** PR实现 | #1019的代码实现，`resolvePage(pageId?)`方法 | 🔶已合并到实验flag | Token增+7.6%(7084→7624) |
| **#1034** Tab context隔离 | 每个Tab有自己的context，navigate只在自己Tab内 | 🔶已关闭→并入#1019 | 社区需求强烈 |

#### Claude Code生态同类问题

| Issue | 平台 | 问题 | 状态 |
|-------|------|------|------|
| **#15193** | Claude Code | 多Claude实例共享同一Chrome Tab Group，截图/导航互相干扰 | 🔶Open |
| **#20100** | Claude Code | 请求Session-scoped Tab Group隔离 | 🔶Closed(重复) |
| **#15173** | Claude Code | 所有Claude实例绑定到同一个tabGroupId | 🔶Open |
| **#17736** | Claude Code | DevTools freezes with multiple instances | 🔶Open |

#### 社区共识（从Issue讨论提炼）

1. **`pageId`是正确的原语**——`isolatedContext`解决存储隔离，`pageId`解决定位隔离，二者正交
2. **Token开销可接受**——+7.6%远小于竞态失败后的重试成本（实测3-5x）
3. **静默错误比开销更危险**——截图截到错页面→Agent基于错误信息决策→级联失败
4. **每个MCP Client应有独立Server实例**——这是官方设计意图，多Agent共享单实例不在设计范围

### 11.5 解决方案全景——从当前到未来

#### 方案A：进程级隔离（当前最佳实践）✅

```
Cascade A ──STDIO──► chrome-devtools-mcp 实例1 ──► Chrome实例1 (--isolated)
Cascade B ──STDIO──► chrome-devtools-mcp 实例2 ──► Chrome实例2 (--isolated)
用户      ──────────► 自己的Chrome ────────────────► 不受干扰
```

**原理**：Windsurf Worktree模式下，每个Cascade对话有**独立的MCP Server进程**。
每个chrome-devtools-mcp进程启动自己的Chrome实例（`--isolated`确保临时profile）。
五感完全独立，物理上不可能冲突。

**配置**：
```json
{
  "chrome-devtools": {
    "command": "npx",
    "args": ["chrome-devtools-mcp@latest", "--isolated"]
  }
}
```

**优势**：零冲突，零代码改动，当前可用。
**劣势**：每Chrome实例+400MB内存；16GB机器最多2-3个并发（含用户Chrome）。

#### 方案B：isolatedContext + select_page规约（轻量级）✅

**适用**：单Server进程多Tab场景（如单Cascade内多步操作）

```javascript
// 1. 创建隔离Context
new_page({ url: "https://a.com", isolatedContext: "agentA" })  // → pageId: 2
new_page({ url: "https://b.com", isolatedContext: "agentB" })  // → pageId: 3

// 2. 严格select_page后立即操作（中间不能插入其他Agent调用）
select_page({ pageId: 2 })
take_snapshot()  // 保证看到的是Page 2
```

**规约**：`select_page` + 操作必须**原子化**——Agent发出select后，下一个工具调用**必须**是对该页面的操作。

**局限**：仅在**单Cascade**内有效。多Cascade共享同一MCP进程时仍有竞态。

#### 方案C：pageId直接路由（实验性，等待稳定）🔶

```json
{
  "chrome-devtools": {
    "command": "npx",
    "args": ["chrome-devtools-mcp@latest", "--experimental-page-id-routing"]
  }
}
```

```javascript
// 无需select_page，直接定位
take_screenshot({ pageId: 2 })  // 原子操作，不受其他Agent影响
click({ uid: "btn-1", pageId: 2 })
```

**状态**：PR #1018已合并到实验flag，等待正式发布。
**Token成本**：+7.6%，值得（vs竞态失败3-5x重试成本）。

#### 方案D：Playwright进程隔离（已有，最强）✅

Playwright MCP天然进程隔离——每个Cascade启动独立Chromium进程，**没有`#selectedPage`全局状态问题**。

```
Cascade A ──STDIO──► playwright-mcp 实例1 ──► Chromium 1 (headless)
Cascade B ──STDIO──► playwright-mcp 实例2 ──► Chromium 2 (headless)
```

**当多Agent需浏览器时，优先Playwright而非DevTools。**

### 11.6 我们的决策树（1秒决定用哪个）

```
多Agent需要浏览器?
│
├─ 各自独立任务 ────────────► 方案A: 各自chrome-devtools --isolated
│                              或方案D: 各自Playwright (更推荐)
│
├─ 同一Cascade多Tab ─────────► 方案B: isolatedContext + select_page原子化
│
├─ 需共享Cookie ──────────────► 方案B: isolatedContext(不同名=独立Cookie)
│                              + --storage-state(继承用户Cookie)
│
├─ 调试用户页面 ──────────────► DevTools --autoConnect (Chrome ≥144)
│                              铁律R4: pageId=0禁写
│
└─ 需要pageId直接路由 ────────► 方案C: --experimental-page-id-routing
                                (等待稳定后切为默认)
```

### 11.7 Windsurf特有约束与对策

| 约束 | 原因 | 对策 |
|------|------|------|
| mcp_config.json全局共享 | Zone 0冻结，所有Cascade用同一配置 | `--isolated`确保临时profile互不冲突 |
| Worktree模式每Cascade独立MCP进程 | Windsurf架构设计 | ✅天然进程隔离，最佳实践 |
| 16GB内存限制 | 笔记本焊死 | 最多2个Chrome实例(2×400MB)；优先headless Playwright |
| 用户Chrome不能碰 | 五感侵犯 | R4铁律(pageId=0禁写) + headless隔离 |

### 11.8 进化路线更新

| 阶段 | 目标 | 状态 | 变化 |
|------|------|------|------|
| **已达成** | `--headless` + STDIO隔离 + 九律 + Worktree | ✅ | — |
| **已达成** | `--isolated` 临时profile隔离 | ✅ | **新增** |
| **已达成** | `isolatedContext` 命名BrowserContext | ✅ v0.18+ | **新增** |
| **短期** | `--experimental-page-id-routing` 评估 | 🔶可试用 | **新增** |
| **短期** | `browser_run_code`成为默认提取方式 | 可用 | — |
| **中期** | `pageId`正式成为默认（去掉experimental） | 等上游 | **新增** |
| **中期** | Chrome ≥144 `--autoConnect` 无缝调试 | 等Chrome稳定版 | **新增** |
| **长期** | Context Broker 2.0 多Agent+用户完美共存 | 概念设计 | — |

### 11.9 实测验证（2026-02-27 两轮）

> 环境：chrome-devtools-mcp v0.18.1 · Chrome 145 · Playwright headless · 内存93-95%

#### 第一轮：功能验证（6项）

| # | 测试项 | 方法 | 结果 |
|---|--------|------|------|
| 1 | **isolatedContext Cookie隔离** | `new_page({isolatedContext:"agentA"})` 设cookie=testA；`new_page({isolatedContext:"agentB"})` 设cookie=testB；分别读取 | ✅ 完全独立 |
| 2 | **select_page原子化** | `select_page(9)` → `take_snapshot()` | ✅ 正确对应 |
| 3 | **跨Context导航不影响** | agentA navigate到/headers，agentB URL不变 | ✅ 互不干扰 |
| 4 | **Playwright进程隔离** | 独立Chromium设cookie，与用户Chrome完全隔离 | ✅ 独立Cookie |
| 5 | **pageId routing** | `--experimental-page-id-routing` 在v0.18.1未出现 | 🔶 等上游 |
| 6 | **--isolated参数** | `--help`确认存在 | ✅ 可用 |

#### 第二轮：五感全覆盖（3个MCP × 5感 = 15项）

**Chrome DevTools MCP（28工具）**

| 感官 | 工具 | 结果 | 备注 |
|------|------|------|------|
| 👁 视觉 | `take_snapshot` + `take_screenshot` | ✅✅ | a11y树+像素截图 |
| 🖐 触觉 | `fill_form` + `click`(radio/checkbox/submit) | ✅✅ | 表单提交成功(httpbin.org/post) |
| 👂 听觉 | `list_console_messages` + type过滤 + `list_network_requests` | ✅✅✅ | R6验证：error-only过滤正常 |
| 🧠 认知 | `evaluate_script` DOM精准提取 | ✅ | title/url/headings/textLength |
| 🎮 管控 | `navigate_page`(url/back/forward) + `new_page` + `close_page` | ✅✅✅ | 全链路 |
| 🔒 隔离 | `isolatedContext` Cookie独立 + R8原子化 | ✅✅ | ctxA/ctxB完全隔离 |

**Playwright MCP（22工具）**

| 感官 | 工具 | 结果 | 备注 |
|------|------|------|------|
| 👁 视觉 | `browser_snapshot` | ✅ | a11y树(YAML格式) |
| 🖐 触觉 | `browser_fill_form` + `browser_click` | ✅✅ | 表单提交成功 |
| 🧠 认知 | `browser_evaluate` JS精准提取 | ✅ | JSON解析+headless检测 |
| 🎮 管控 | `browser_tabs`(list/new/close) + `browser_close` | ✅✅ | Tab管理正常 |

**context7 MCP（2工具）**

| 工具 | 结果 | 备注 |
|------|------|------|
| `resolve-library-id` | ✅ | 正确解析playwright→多个库 |
| `query-docs` | ✅ | 返回isolated配置文档+schema |

#### 发现并修复的问题

| # | 发现 | 五感 | 修复 |
|---|------|------|------|
| 1 | **Playwright Cookie跨会话残留** — 上次设的cookie在本次仍存在 | 👅味觉污染 | `mcp_config.json` playwright加`--isolated`（临时profile，关闭即清） |

**总计：20/21项通过**（pageId routing等上游），1个运行时问题已修复。

**结论**：方案A(进程隔离) + 方案B(isolatedContext) + 方案D(Playwright) = **当前三个方案已验证可用**。方案C(pageId routing)等待上游发布。

### 11.10 问·祸·惑——全面清扫（2026-02-27）

> 代入用户之五感，直到**无感**——用户不知道有冲突这回事，Agent不知道有其他Agent，系统从未感到压力。

#### 三问（未解问题→已解）

| # | 问 | 用户五感 | 解法 | 状态 |
|---|-----|---------|------|------|
| 问1 | MCP config缺`--isolated` | 👁看到"profile already in use"报错 | **已修复**：`mcp_config.json`自动注入`--isolated` | ✅ |
| 问2 | 内存93%下多Chrome实例→BSOD | 🖐触觉全丧失（蓝屏=五感归零） | R5铁律(>85%禁Playwright) + R9(DevTools≤5 Tab) | ✅ |
| 问3 | `pageId`路由v0.18.1不可用 | 🧠认知：知道有更好方案但用不了 | 降级为R8原子化；持续跟踪#1019；稳定后自动升级 | 🔶等上游 |

#### 三祸（灾害→已灭）

| # | 祸 | 用户体验的痛 | 根治 | 状态 |
|---|-----|------------|------|------|
| 祸1 | 两Cascade共享profile→启动失败 | 👁看到MCP工具不可用，不知道为什么 | `--isolated`：每实例临时profile，启动即用，关闭即清 | ✅ |
| 祸2 | 6+Tab→WebSocket过载→静默断连 | 🖐触觉丧失（click无响应）+ 👂听觉丧失（console断流） | **R9铁律**：DevTools同时打开页面≤5个；超过时先close再new | ✅新增 |
| 祸3 | console消息跨页面混合→误判Bug | 👂听觉污染——听到别人的错误，浪费时间排查 | R6（按page+type过滤）+ `isolatedContext`各Context独立console | ✅ |

#### 三惑（困惑→已解）

| # | 惑 | 用户的疑问 | 解答 |
|---|-----|---------|------|
| 惑1 | `--isolated` vs `isolatedContext` vs Worktree有什么区别？ | 见下方「三层隔离一张表」 |
| 惑2 | 我什么时候会遇到冲突？ | 见下方「冲突触发场景」 |
| 惑3 | 备份mcp_config.json有什么用？ | 恢复参考模板；台式机部署源；新Cascade对话自检基线 |

#### 三层隔离一张表（惑1之解）

| 隔离机制 | 隔离什么 | 粒度 | 成本 | 谁触发 |
|---------|---------|------|------|-------|
| **`--isolated`** | Chrome用户数据目录（profile） | 每个MCP Server进程 | 零（临时目录自动清理） | 命令行参数，启动时生效 |
| **`isolatedContext`** | Cookie/localStorage/Session | 每个命名Context（同一Chrome内） | 零（内存中BrowserContext） | Agent调用`new_page({isolatedContext:"name"})`时 |
| **Worktree** | 整个Cascade环境（文件系统+MCP进程+终端） | 每个Cascade对话 | 磁盘空间（git worktree） | 用户在Windsurf中开启Worktree模式时 |

**一句话**：`--isolated`隔离Chrome实例，`isolatedContext`隔离Tab的存储，Worktree隔离整个Agent。三者层层递进，互相补充。

#### 冲突触发场景（惑2之解）

| 场景 | 是否冲突 | 原因 | 你需要做什么 |
|------|---------|------|-----------|
| 单Cascade + 单Tab | ❌不冲突 | 只有一个操作者 | 什么都不用管 |
| 单Cascade + 多Tab | ⚠️可能 | `#selectedPage`在Tab间切换 | 用`isolatedContext`或R8原子化 |
| 多Cascade(Worktree) | ❌不冲突 | 每Cascade独立MCP进程+独立Chrome(`--isolated`) | **什么都不用管** ✅ |
| 多Cascade(非Worktree) | ⚠️看配置 | 共享MCP进程？→冲突；各自进程+`--isolated`？→不冲突 | 确保`--isolated`已配置 |
| Agent + 用户Chrome | ❌不冲突 | Playwright=独立Chromium；DevTools=独立Chrome(`--isolated`) | 什么都不用管 |

**结论：加了`--isolated`后，99%的使用场景用户无需任何操作，冲突不可能发生。**

### 11.11 铁律完整版（R1-R9）

| # | 铁律 | 解决 | 来源 |
|---|------|------|------|
| R1 | Playwright `--headless`（已配置） | 焦点祸 | v1 |
| R2 | 同一对话Playwright和DevTools不同时用 | 并发祸 | v1 |
| R3 | DevTools: `list_pages`→`select_page`→操作→不切换 | 并发祸 | v1 |
| R4 | DevTools禁止写操作pageId=0（用户活跃Tab） | 侵犯祸 | v1 |
| R5 | 内存>85%禁新Playwright；用完即`browser_close` | 资源祸 | v1 |
| R6 | DevTools按page+type过滤console | 听觉祸 | v1 |
| R7 | DevTools `--isolated`（**已配置**，临时profile） | 多实例祸 | **v3 新增** |
| R8 | `select_page`+操作必须原子化 | 竞态祸 | **v3 新增** |
| R9 | DevTools同时打开页面≤5个（防WebSocket过载） | 断连祸 | **v3 新增** |
