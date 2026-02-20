# 多Agent并行开发：冲突路径分析与隔离协议

> 版本: v2.0 | 日期: 2026-02-20
> 目标: 从顶层设计上解决多Agent并行开发的所有冲突路径，确保N个Cascade窗口同时工作时不会相互干扰、不会烧毁用户体验
> 适用范围: 所有使用 Windsurf + Cascade 的项目，不限于 ScreenStream_v2

---

## 一、Agent/组件全景图

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Zone 0: GLOBAL (全窗口生效)                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐  │
│  │ mcp_config   │ │ hooks.json   │ │  memories/   │ │  skills/  │  │
│  │  .json       │ │  (全局)      │ │  (Memory DB) │ │  (全局)   │  │
│  │ 7 MCP servers│ │ 2 Python     │ │              │ │  23个     │  │
│  └──────┬───────┘ └──────┬───────┘ └──────────────┘ └───────────┘  │
│         │                │                                          │
│  PATH: ~/.codeium/windsurf/                    风险: 🔴 极高         │
│  改动影响: 所有打开的Windsurf窗口 + 所有项目                           │
├─────────┼────────────────┼──────────────────────────────────────────┤
│         │    Zone 1: PROJECT (当前项目窗口)                           │
│         │                │                                          │
│  ┌──────┴───────┐ ┌──────┴───────┐ ┌───────────┐ ┌──────────────┐ │
│  │ MCP Server   │ │ hooks.json   │ │ .windsurf/ │ │  AGENTS.md   │ │
│  │ Processes    │ │  (项目级)    │ │ rules/ (7) │ │  (目录级)    │ │
│  │ (子进程)     │ │ 3 Python     │ │ workflows/ │ │              │ │
│  │              │ │ hooks        │ │ skills/ (8)│ │              │ │
│  └──────┬───────┘ └──────┬───────┘ └───────────┘ └──────────────┘ │
│         │                │                                          │
│  PATH: .windsurf/ + 项目根                      风险: 🟡 中          │
│  改动影响: 当前窗口 + 当前项目的所有Cascade会话                         │
├─────────┼────────────────┼──────────────────────────────────────────┤
│         │    Zone 2: SESSION (当前Cascade会话)                       │
│         │                │                                          │
│  ┌──────┴───────┐ ┌──────┴───────┐ ┌───────────┐ ┌──────────────┐ │
│  │ Terminal     │ │ File Edits   │ │ run_command│ │ Tool Calls   │ │
│  │ (PowerShell) │ │ (workspace)  │ │ (非阻塞)   │ │ (read/edit)  │ │
│  └──────┬───────┘ └──────────────┘ └───────────┘ └──────────────┘ │
│         │                                                           │
│  风险: 🟢 低（单会话，可回退）                                         │
├─────────┼───────────────────────────────────────────────────────────┤
│         │    Zone 3: EXTERNAL (IDE外部世界)                           │
│         │                                                           │
│  ┌──────┴───────┐ ┌──────────────┐ ┌───────────┐ ┌──────────────┐ │
│  │ desktop-     │ │ Android      │ │ cunzhi    │ │ network      │ │
│  │ automation   │ │ device (ADB) │ │ dashboard │ │ (fetch/github)│ │
│  │ 🔴 鼠标键盘  │ │ 🟡 设备状态   │ │ :9901     │ │ 🟢 只读      │ │
│  └──────────────┘ └──────────────┘ └───────────┘ └──────────────┘ │
│  风险: 🔴 不可逆物理操作 / 🟡 设备状态变更                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、共享可变状态矩阵

### 写入者 × 状态 交叉表

| 共享状态 | Cascade | Hooks (全局) | Hooks (项目) | MCP Servers | 用户 | 外部脚本 |
|----------|---------|-------------|-------------|-------------|------|---------|
| `mcp_config.json` | ✍️ 可写 | — | — | — | ✍️ 可写 | ✍️ 可写 |
| `hooks.json` (全局) | ✍️ **危险** | — | — | — | ✍️ 可写 | ✍️ 可写 |
| `hooks.json` (项目) | ✍️ 可写 | — | — | — | ✍️ 可写 | — |
| Terminal stdout | ✍️ 可写 | ✍️ **show_output** | ✍️ 可写 | — | ✍️ 可写 | — |
| Workspace 文件 | ✍️ 可写 | ✍️ 间接 | ✍️ 间接 | ✍️ desktop-auto | ✍️ 可写 | ✍️ git |
| Memory DB | ✍️ 可写 | — | — | — | — | — |
| 桌面(鼠标/键盘) | — | — | — | ✍️ **desktop-auto** | ✍️ 操作 | — |
| Android 设备 | ✍️ ADB | — | — | — | ✍️ 物理 | — |
| cunzhi dashboard | ✍️ HTTP | — | — | — | ✍️ Web UI | — |
| 对话捕获文件 | — | ✍️ capture | ✍️ capture | — | — | — |

### 关键发现

**3个🔴级冲突点**：
1. **`hooks.json` (全局)** — 任何写入立即影响所有窗口的所有命令执行
2. **Terminal stdout** — hooks的 `show_output:true` 与 Cascade 命令输出交错
3. **desktop-automation** — MCP服务器直接控制物理鼠标键盘，无窗口隔离

---

## 三、历史事故复盘

### 事故 #1: 全局 hooks.json PowerShell 灾难 (2026-02-13)

```
触发: AI 在 "智能升级" 中向全局 hooks.json 写入 pre_run_command PowerShell 钩子
传播: hooks.json → Windsurf 加载 → 每条命令前启动 PowerShell 子进程
症状: 终端提示符检测干扰 → 所有命令挂起 → IDE不可用
爆炸半径: 所有打开的 Windsurf 窗口（Zone 0 全域）
恢复: 4轮修复尝试 + IDE强制重启
根因: Zone 0 写入无防护门
```

### 事故 #2: Hook 过载 (2026-02-18 备份显示)

```
状态: 全局 hooks.json 累积了 5 个 pre_user_prompt hooks（4个 show_output:true）
风险: 每次用户输入触发 5 个 Python 进程 → stdin 竞争 + 输出交错
当前: 已精简为 1 个 hook（conversation_capture.py, show_output:false）
教训: Hook 数量必须有硬上限
```

### 事故 #3: MCP 配置乱码 (持续至今日修复)

```
触发: Windsurf IDE 自动生成随机名内部服务器 (ndoewvtl_dev, qymevwyc_dev)
症状: 用户无法理解/维护 MCP 配置
根因: IDE 内部机制 + PowerShell ConvertTo-Json 破坏格式
```

---

## 四、五条干扰模式 (Interference Patterns)

| 模式 | 名称 | 机制 | 已发生? |
|------|------|------|---------|
| A | **Hook Cascade** | Hook A 修改状态 → Hook B 读到脏数据 | ⚠️ 潜在 |
| B | **Terminal Contention** | 多 hook show_output:true → 输出交错 → 提示符检测失败 | ✅ 已发生 |
| C | **Config Mutation Cascade** | 修改全局配置 → 所有窗口行为变化 → 其他Cascade实例异常 | ✅ 已发生 |
| D | **Desktop Crossfire** | desktop-automation 发送按键 → 焦点窗口错误 → 误操作 | ⚠️ 潜在(高危) |
| E | **Resource Race** | 多MCP server 竞争同一资源(端口/文件/API限额) | ⚠️ 潜在 |

---

## 五、分层隔离架构 (Blast Radius Containment)

### 设计原则

```
越靠近 Zone 0，防护越严格
Zone 0 (全局): 禁写 + 需用户确认
Zone 1 (项目): 限写 + 自动备份
Zone 2 (会话): 自由 + 可回退
Zone 3 (外部): 确认 + 超时保护
```

### 5.1 Zone 0 防护: 全局配置保护墙

**硬性规则（不可覆盖）**：

| 路径 | 规则 |
|------|------|
| `~/.codeium/windsurf/hooks.json` | **Cascade禁止写入**。只有用户手动编辑 |
| `~/.codeium/windsurf/mcp_config.json` | 写入前必须: 展示diff → 创建.bak → 用户确认 |
| `~/.codeium/windsurf/memories/` | 仅通过 `create_memory` API 操作，禁止直接文件编辑 |
| `~/.codeium/windsurf/skills/` | 修改前展示变更，记录到 Memory |

**Hook 数量硬上限**：

| Hook 类型 | 全局上限 | 项目上限 | show_output 上限 |
|-----------|---------|---------|-----------------|
| pre_user_prompt | 2 | 2 | 0 (全部 false) |
| post_cascade_response | 1 | 1 | 0 |
| post_mcp_tool_use | 1 | 1 | 0 |
| pre_run_command | **0 (绝对禁止)** | **0** | — |

**Hook 语言限制**：
- ✅ Python / Node.js — 安全，独立进程
- ❌ PowerShell / Bash — **绝对禁止**（干扰终端提示符检测）

### 5.2 Zone 1 防护: 项目配置隔离

| 组件 | 防护措施 |
|------|---------|
| `.windsurf/hooks.json` | 项目级 hooks 独立于全局。合并顺序: system → user → workspace |
| `.windsurf/rules/` | 规则总量 ≤ 6000 字符 (always-on)。条件规则按 glob/manual 触发 |
| `.windsurf/workflows/` | 只读引用，不自动修改 |
| `.windsurf/skills/` | 技能为只读模板，执行时不修改技能文件本身 |

### 5.3 Zone 2 防护: 会话级安全

| 风险点 | 防护措施 |
|--------|---------|
| Terminal 命令 | 不安全命令需用户确认 (SafeToAutoRun=false) |
| 文件编辑 | 优先 edit/multi_edit 而非 write_to_file (可追踪diff) |
| 长时间命令 | 非阻塞 + 超时检查，卡顿 → 换方案 |
| 多文件修改 | 先 read 收集 → 再串行 edit (原子性) |

### 5.4 Zone 3 防护: 外部世界隔离

| 组件 | 风险 | 防护措施 |
|------|------|---------|
| desktop-automation | 🔴 物理操作不可逆 | **默认 disabled**。仅在用户明确要求桌面操作时临时启用 |
| ADB (Android) | 🟡 设备状态变更 | install/uninstall 需确认; logcat/shell 安全 |
| cunzhi dashboard | 🟢 本地HTTP | 监听 127.0.0.1 only; 30min 超时自动清理 |
| fetch/github MCP | 🟢 网络只读 | 无写入能力; API rate limit 由服务端控制 |

---

## 六、12条冲突路径完整分析

> 基线数据 (2026-02-20): 单窗口已有 10 node + 6 python 进程, C: 仅 34.9GB 可用

### Level 1: 文件级冲突（数据丢失风险）

#### CP-01: 同文件编辑碰撞

```
场景: Agent A 编辑 InputRoutes.kt, Agent B 也需要编辑它
机制: A read → B read → A edit → B edit (基于过期快照) → A的修改被覆盖
严重度: 🔴 数据丢失
已发生: ⚠️ 尚未（因为之前从未并行）
```

**高危共享文件清单** (ScreenStream_v2):

| 文件 | 为什么共享 | 被哪些模块使用 |
|------|-----------|-------------|
| `build.gradle.kts` (root) | 全局依赖声明 | 所有模块 |
| `settings.gradle.kts` | 模块注册 | 所有模块 |
| `gradle/libs.versions.toml` | 版本统一管理 | 所有模块 |
| `InputRoutes.kt` | 路由注册 | Input + MJPEG + AI Brain |
| `HttpServer.kt` | HTTP入口 | MJPEG + Input |
| `index.html` (前端) | 用户界面 | Streaming + Input + AI Brain |
| `AppSettings.kt` | 全局配置项 | 所有模块 |

**解决方案: 模块所有权 + 共享文件协调**
- 每个Agent声明所有权模块（见第七章）
- 共享文件：编辑前必须 `read_file` 获取最新版本
- 禁止两个Agent同时编辑同一个文件

#### CP-02: Git 状态腐化

```
场景: Agent A 执行 git add + commit, Agent B 同时也在 staging
机制: git add 和 git commit 不是原子操作 → 交错执行 → 错误文件进入错误的commit
严重度: 🔴 仓库历史污染
已发生: ⚠️ 尚未
```

**解决方案: Branch 隔离**
- 每个Agent在自己的 feature branch 上工作
- **禁止**任何Agent直接 commit 到 `main`
- 合并由用户手动执行或在专门的合并会话中进行
- 当前已有 branch 模式: `feature/optimize-connectivity`, `feature/vr-*`

#### CP-03: 构建冲突

```
场景: Agent A 和 Agent B 同时触发 Gradle build
机制: Gradle daemon 单实例 → 后发build等待或失败; APK输出路径相同 → 覆盖
严重度: 🟡 构建失败（不丢数据）
已发生: ⚠️ 尚未
```

**解决方案: 构建串行化**
- 同一项目：同一时间只有 1 个Agent执行构建
- 构建前检查: `./gradlew --status` 确认无活跃daemon任务
- 不同项目：可以并行（各自独立的 Gradle daemon）

### Level 2: 进程级冲突（服务中断风险）

#### CP-04: 端口争用

```
场景: Agent A 启动 dev server :3000, Agent B 也要 :3000
机制: EADDRINUSE → 第二个启动失败
严重度: 🟡 命令失败
已发生: ⚠️ 潜在（ADB forward 时尤其易发生）
```

**解决方案**: 端口已固定分配（见 AGENTS.md），不同服务使用不同端口段

#### CP-05: ADB 设备争用

```
场景: Agent A 执行 adb install, Agent B 同时 adb shell
机制: ADB USB传输单线程 → 命令队列/失败; install 过程中 shell 可能挂起
严重度: 🟡 命令失败 + 设备状态不确定
已发生: ⚠️ 尚未
```

**解决方案: 设备所有权**
- 同一时间只有 1 个Agent与Android设备交互
- 正在 build/deploy 的Agent "拥有"设备
- 其他Agent禁止执行 ADB 命令

#### CP-06: MCP 进程膨胀

```
场景: 3 个窗口各启动 7 个 MCP server = 21 个 node 进程
机制: 每个进程 ~50-150MB 内存 → 系统变慢; npx 缓存并发写入 → 安装失败
严重度: 🟡 系统卡顿 / 🔴 npx缓存损坏
实测: 当前1窗口已有 10 node 进程
```

**解决方案: 按需启用**
- 每个窗口只启用当前任务需要的 MCP server
- 建议每窗口最多 3 个 MCP server 活跃
- `playwright` 和 `desktop-automation` 平时保持 disabled

#### CP-07: Hook 跨窗口干扰

```
场景: 全局 hooks 在所有窗口同时触发
机制: 3 窗口 × 每窗口 pre_user_prompt hook → 3 个 Python 进程同时写文件
严重度: 🟡 文件锁竞争 / 日志交错
当前缓解: conversation_capture.py 已有 FileLock
```

**解决方案**: 当前架构已OK（FileLock + show_output:false），但需遵守 Hook 数量上限

### Level 3: 状态级冲突（数据不一致风险）

#### CP-08: Memory DB 跨Agent污染

```
场景: Agent A 更新 Memory "项目状态", Agent B 依赖旧版本
机制: Memory 是全局共享的 → A 的更新对 B 可见但 B 不知道内容变了
严重度: 🟢 行为偏差（不丢数据）
```

**解决方案**:
- Memory 以追加为主，避免频繁更新同一条
- 项目状态类 Memory 标注更新时间
- Agent 引用 Memory 时应意识到可能过期

#### CP-09: cunzhi Dashboard 槽位耗尽

```
场景: 4 个窗口已占满 4 个 cunzhi slot, 第 5 个窗口无法与用户沟通
机制: 槽位有限 (4), 锁文件管理
严重度: 🟢 降级（Agent仍可工作，只是无法主动请求用户输入）
当前缓解: cunzhi_positioned.py 已有 lock-based slot 管理
```

**解决方案**: 4 个槽位足够（>4个并行Agent属于过度并行）

### Level 4: 资源级冲突（系统级风险）

#### CP-10: 磁盘空间耗尽

```
场景: 多Agent并行构建 + 日志 + 对话捕获 → C: 用满
机制: Gradle build ~2-5GB, 对话捕获 ~500MB上限, 各种日志
严重度: 🔴 全系统故障
实测: C: 仅 34.9GB 可用
```

**解决方案**:
- `auto-cleanup.ps1` 已就绪（定期清理）
- conversation_capture.py 已有 500MB 总量上限
- Gradle: `./gradlew clean` 在构建前执行
- 监控: 剩余空间 < 20GB 时应报警

#### CP-11: CPU/内存耗尽

```
场景: 7 MCP × 3 窗口 = 21 node + hooks + Gradle = 系统 100% CPU
机制: IDE 变慢 → 命令超时 → Agent 重试 → 更多进程 → 恶性循环
严重度: 🔴 IDE 不可用
实测: 当前1窗口 = 16进程, 3窗口预估 = 48+ 进程
```

**解决方案: 资源预算**（见第八章）

#### CP-12: 全局配置连锁反应

```
场景: Agent A "优化" hooks.json → 所有窗口的 Agent B/C/D 行为异变
机制: Zone 0 写入 → 即时传播到所有窗口
严重度: 🔴 全IDE崩溃（已发生！见事故#1）
已发生: ✅ 2026-02-13 PowerShell hooks 灾难
```

**解决方案**: Zone 0 铁律（已在第五章固化）

---

## 七、并行开发协议 (Parallel Development Protocol)

### 核心原则: "能不共享就不共享，必须共享就加锁"

```
┌─────────────────────────────────────────────────────────┐
│             多Agent并行开发的6条铁律                       │
│                                                          │
│  1. 模块所有权：每个Agent声明负责的模块                      │
│  2. Branch隔离：每个Agent在自己的branch上工作               │
│  3. 构建串行：同一项目同时只有1个Agent构建                   │
│  4. 设备独占：同一设备同时只有1个Agent操作                   │
│  5. Zone 0冻结：并行期间禁止修改全局配置                     │
│  6. 资源预算：每窗口 ≤3 MCP + 限制进程总量                  │
└─────────────────────────────────────────────────────────┘
```

### 7.1 模块所有权图 (ScreenStream_v2)

```
┌──────────────────────────────────────────────────────┐
│  Module                        │  Owner Agent        │
├──────────────────────────────────────────────────────┤
│  010-用户界面与交互_UI/         │  UI Agent           │
│  020-投屏链路_Streaming/        │  Streaming Agent    │
│  040-反向控制_Input/            │  Input Agent        │
│  050-音频处理_Audio/            │  Audio Agent        │
│  070-基础设施_Infrastructure/   │  Infra Agent        │
│  080-配置管理_Settings/         │  Settings Agent     │
│  090-构建与部署_Build/          │  Build Agent        │
│  api-services/                 │  API Agent          │
│  tools/                        │  Tooling Agent      │
│  05-文档_docs/                 │  任何Agent（只追加） │
├──────────────────────────────────────────────────────┤
│  ⚠️ 共享文件（跨模块边界）                              │
│  build.gradle.kts (root)       │  协调后编辑          │
│  settings.gradle.kts           │  协调后编辑          │
│  gradle/libs.versions.toml     │  协调后编辑          │
│  InputRoutes.kt                │  Input Agent 主导    │
│  index.html (前端)             │  Streaming Agent主导 │
│  HttpServer.kt                 │  Streaming Agent主导 │
└──────────────────────────────────────────────────────┘
```

**所有权规则**:
- **只有 Owner** 可以 **写入** 该模块的文件
- **任何 Agent** 可以 **读取** 任何模块
- **共享文件**: 编辑前 read 最新版本 → 编辑 → 如有冲突通知用户
- **文档目录**: 所有 Agent 可追加，但不修改已有内容

### 7.2 新会话入场协议

每个新 Cascade 会话启动时，应当：

```
1. 阅读 AGENTS.md → 了解项目结构和约束
2. 声明自己负责的模块/任务范围
3. 确认当前 branch（如果不是自己的 → 创建新 branch）
4. 检查是否有其他 Agent 正在工作（通过 cunzhi dashboard）
5. 只启用本次任务需要的 MCP server
6. 开始工作
```

### 7.3 共享文件编辑协议

当 Agent 需要编辑共享文件时：

```
1. read_file → 获取最新内容
2. 确认修改不会破坏其他模块的功能
3. 最小化修改范围（只改必须改的行）
4. 如果修改影响多个模块 → 在 commit message 中标注
5. 如果两个 Agent 都需要改同一文件 → 通过用户协调
```

---

## 八、资源预算 (Resource Budget)

### 单窗口预算

| 资源 | 上限 | 当前实测 | 说明 |
|------|------|---------|------|
| MCP servers (活跃) | 3 | 5 (enabled) | 禁用不需要的 |
| node 进程 | ~8 | 10 | MCP + npx |
| python 进程 | ~4 | 6 | hooks + cunzhi |
| 终端并行命令 | 2 | — | 避免长时间阻塞 |
| Gradle build | 1 | — | 排他 |

### 系统总预算 (跨所有窗口)

| 资源 | 上限 | 说明 |
|------|------|------|
| 并行 Windsurf 窗口 | **3** | 超过3个 → 进程数爆炸 |
| 总 node 进程 | ~25 | 3窗口 × ~8 |
| 总 python 进程 | ~12 | 3窗口 × ~4 |
| C: 磁盘剩余 | > 20GB | 低于此值 → 暂停构建 |
| Gradle daemon | 1/项目 | 同项目多窗口共享 |
| ADB 连接 | 1 | 设备独占 |
| cunzhi slots | 4 | 足够3窗口 |

### 超预算应急

```
进程数 > 50  → 关闭最闲的窗口
C: < 20GB    → 执行 auto-cleanup.ps1
C: < 10GB    → 停止所有构建, 紧急清理
命令超时频繁  → 检查 CPU 占用, 减少并行
```

---

## 九、规则执行链路 (Enforcement Chain)

### 新 Cascade 会话如何自动继承这些规则？

```
会话启动
  │
  ├─ 1. 加载全局规则 (~/.codeium/windsurf/memories/global_rules.md)
  │     → 包含: Zone 0 铁律, PREDICT 框架, 权限自升级禁令
  │
  ├─ 2. 加载项目规则 (.windsurf/rules/*.md)
  │     → execution-engine.md: Zone 隔离 + 并行开发规则
  │     → project-structure.md: 模块映射 + 端口
  │     → soul.md: 思维框架
  │
  ├─ 3. 加载 AGENTS.md (项目根 + 各目录)
  │     → 项目概述 + 并行协议摘要
  │
  ├─ 4. 检索 Memory (按 corpus 过滤)
  │     → "多Agent影响区分层隔离设计" → Zone 规则
  │     → "MCP配置修复" → 配置现状
  │
  └─ 5. Agent 自动遵循规则开始工作
```

### 规则固化位置

| 规则内容 | 固化位置 | 覆盖范围 |
|---------|---------|---------|
| Zone 0-3 防护铁律 | `execution-engine.md` + Memory | 当前项目所有会话 |
| 模块所有权 | AGENTS.md + 本文档 | 当前项目 |
| Branch 隔离 | AGENTS.md | 当前项目 |
| 资源预算 | Memory (全局) | 所有项目 |
| Hook/MCP 配置约束 | Memory (全局) + `execution-engine.md` | 所有项目 |

---

## 十、防护规则速查 (Quick Reference)

```
═══════════════════════════════════════════════════════
ZONE 0 铁律 (全局配置 ~/.codeium/windsurf/):
├── hooks.json: Cascade 绝对禁止写入
├── mcp_config.json: 写入需 diff + backup + 确认
├── Hook 语言: 仅 Python/Node.js, 禁止 PowerShell
├── Hook 数量: pre_user_prompt ≤2, pre_run_command = 0
└── Hook 输出: 全部 show_output: false

ZONE 1 纪律 (项目配置 .windsurf/):
├── 规则总量: always-on ≤ 6000 字符
├── 配置修改: 先备份再改
└── skills/workflows: 只读引用

ZONE 2 自由 (会话操作):
├── 不安全命令: 用户确认
├── 文件修改: 优先 edit 而非 write
└── 卡顿: 立即切换方案

ZONE 3 谨慎 (外部世界):
├── desktop-automation: 默认 disabled
├── ADB destructive: 需确认
└── 网络请求: 超时保护

并行铁律:
├── 模块所有权: 只改自己的模块
├── Branch隔离: 不碰 main
├── 构建串行: 同项目同时 1 个 build
├── 设备独占: 同时 1 个 ADB agent
├── Zone 0 冻结: 并行期间禁改全局配置
└── 资源预算: 窗口 ≤3, 进程 ≤50
═══════════════════════════════════════════════════════
```
