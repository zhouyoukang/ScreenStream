---
trigger: always_on
---

# 执行引擎

> **辩证统一：感官完整度 = Agent行为的唯一判据**
> 感官完整 → 自由/自主/高效执行 | 感官缺失 → 立即降级/切换/求助
> 所有规则都是这个原则在不同场景下的实例化。

## 执行原则
- 一次性推进到可验收产物；只读先行(可并行)，写操作串行
- 同一文件用 `multi_edit` 一次完成

## 终端安全
> **核心原则：文件工具(无状态,总返回) ≫ 终端(有状态,可能永久挂起)**
> 分类详见 `skills/terminal-resilience/SKILL.md`（C1交互阻塞~C7长任务误判）

### 发命令前必检5项
1. **非交互**: git加`-m`/`--no-edit`, SSH确认ssh-agent, 禁止`Read-Host`/`input()`/`rebase -i`
2. **有超时**: `curl.exe -m 30` / `ssh -o ConnectTimeout=10` / `IWR -TimeoutSec 15`
3. **有界限**: 禁止`-Recurse`→用`find_by_name`/`grep_search`; `git log -n 20`; `git diff --stat`
4. **非阻塞**: 耗时>30s用`Blocking=false`; WaitMsBeforeAsync后无输出→立即放弃
5. **短且简**: 3-6条/批，禁止长管道/并行组

### 绝对禁止
- PowerShell hooks（铁证：干扰shell integration致全窗口卡死）
- 无界递归（android-sdk 1GB + 00-归档 500+项 + .git大历史）
- 交互式编辑器命令（`git rebase -i` / `vim` / 任何需键盘输入的prompt）
- Junction目录内PowerShell写入（破坏链接）

## Hooks 策略
- Python/Node.js hooks 安全可用；**PS hooks 绝对禁止**（见终端安全）
- 三层合并: system→user→workspace；pre-hooks exit code 2可阻止操作

## 全局配置保护
修改以下路径前必须：**评估影响 → 备份 → 验证**
| 路径 | 影响 | 风险 |
|------|------|------|
| `~/.codeium/windsurf/hooks.json` | 所有窗口每条命令 | 🔴极高 |
| `~/.codeium/windsurf/*` | 所有项目 | 🔴极高 |
| IDE `settings.json` | 所有窗口 | 🟡高 |
| `.vscode/settings.json` | 当前项目 | 🟢中 |

## 开发管线（/dev 工作流）
| Phase | 模式 | 规则 |
|-------|------|------|
| 0-2 分析/设计 | 只读 | 可并行 |
| 3 实现 | 写入 | 串行，multi_edit |
| 4 构建 | 终端 | 非阻塞，最多2轮修复 |
| 5 部署 | 终端 | 逐步确认 |
| **5.5 E2E验证** | 终端+浏览器 | **API ok ≠ 前端可用**，必须模拟用户实操 |
| **5R 中断自愈** | 自动 | 任何Phase被打断时自动触发 |
| 6-7 文档/总结 | 写入 | 可并行 |

失败处理：编译失败→修复（2轮）| 环境缺失→跳过标记 | 验证失败→报告不自动修

## 产出原则（信噪比优先）
- **做减法**：默认精简模式，去除冗余/重复/低价值内容
- **不过度工程**：最小投入→最大产出→最高效率
- **大步骤不中断**：执行复杂任务时，内部步骤不汇报，完成后一次性输出结果
- **产出可交接**：结果写成独立文件/Memory，不依赖当前会话上下文

## 故障恢复
> **原则：用户中断=立即切文件工具，不问不重试。恢复优先于重建。**

- Bug修复每次只改一个变量，2次失败→升级L2（查文档/搜索）
- **降级路径**：正常 → 文件工具模式 → 脚本委托(.ps1) → 用户指挥(L4)
- 需要用户物理操作 → 告知"请做X"不问"是不是Y"；每次自愈记Memory

### 中断自愈（诊断链，到第一个匹配停下）
1. `adb devices` → 无设备 → kill-server+start-server + "请插USB"
2. `curl /status` → 拒绝/无响应 → 探测端口 + `adb forward` / 重启应用
3. 编译错误 → 读错误 + 修复（最多2轮）
4. 终端卡死 → 分类C1-C7（见SKILL）→ 按恢复链执行

## 网络请求（零弹窗工具链）
> `read_url_content`/`mcp2_fetch` 弹窗是二进制硬编码，无法关闭。**禁止使用**。

| 需求 | 工具 |
|------|------|
| 网页/HTML | `Invoke-WebRequest -UseBasicParsing` + regex strip |
| JSON API | `Invoke-RestMethod` |
| JS渲染SPA | Playwright `browser_navigate`+`browser_snapshot` |
| 搜索 | `search_web` |
| 库文档 | context7 `query-docs` |
| GitHub | github `get_file_contents` |

```powershell
# HTML抓取（已加入 allowlist，自动执行）
(Invoke-WebRequest -Uri "<URL>" -UseBasicParsing).Content -replace '<script[^>]*>[\s\S]*?</script>','' -replace '<[^>]+>',' ' -replace '\s+',' '
```

## 浏览器Agent统御
> 操作卡片: `skills/browser-agent-mastery/SKILL.md` | 全域知识: `文档/BROWSER_MCP_MULTI_AGENT_RESEARCH.md`

### 铁律（R1-R8，无条件遵守）
- **R1** Playwright `--headless`（已配置）
- **R2** 同一对话Playwright和DevTools不同时用
- **R3** DevTools: `list_pages`→`select_page`→操作→不切换
- **R4** DevTools禁止写操作pageId=0（用户活跃Tab）
- **R5** 内存>85%禁新Playwright；用完即`browser_close`
- **R6** DevTools按page+type过滤console
- **R7** DevTools `--isolated`（临时profile，多实例不冲突）
- **R8** `select_page`+操作必须**原子化**（中间不可插入其他工具调用）

### 多Agent浏览器隔离（冲突防护）
> 根因：chrome-devtools-mcp内部`#selectedPage`是全局单指针，多Agent共享→五感被劫持
> 详见 `文档/BROWSER_MCP_MULTI_AGENT_RESEARCH.md` §十一

- **Worktree模式**：每Cascade独立MCP进程→天然进程隔离✅
- **单Cascade多Tab**：用`isolatedContext`参数创建独立BrowserContext
- **多Agent优先Playwright**：无`#selectedPage`全局状态问题
- **实验性pageId路由**：`--experimental-page-id-routing`（等待正式发布）

### Token优先级
`browser_run_code`(30-800字符) > `browser_snapshot`(5K-50K) > `take_screenshot`(最后手段)

## 网络故障
第1次失败→换URL重试；连续2次失败→告知用户"可能需要VPN"

## 对话结束协议（ask_user_question）

> 任务完成后调用 `ask_user_question` 引导下一步。**禁止使用 cunzhi 或任何外部UI工具。**

### 触发条件（全部满足）
1. 有**明确产出物** 2. **不在** /dev Phase 3→5.5 中 3. 用户**无下一步指令** 4. **非纯问答**

### 五感化选项设计（代入用户视角）
- **4个选项**，`allowMultiple: false`
- **核心原则**：选项是用户自然想说的话，不是CI/CD清单
- 优先从 AGENTS.md「对话结束选项」选取，无则用通用模板：

| 位置 | 用户视角 | 说明 |
|------|---------|------|
| 选项1 | **看到效果** | 编译/部署/打开浏览器，亲眼确认变化 |
| 选项2 | **继续打磨** | 当前方向深入，把体验做到位 |
| 选项3 | **顺手做掉** | 关联模块/文档/同步，一并搞定 |
| 选项4 | **收工提交** | git commit，干净利落结束 |

### 文案规范
- **label**: ≤10字，用户口语（如"装手机看看"、"跑测试"、"收工提交"）
- **description**: 1句话，≤30字，说人话不说术语
- **禁止**：Gradle/curl/FEATURES.md 等开发者术语出现在label中

### 禁止触发
- /dev Phase 3→5.5 连续执行中 | 用户已给下一步 | 上轮刚触发过 | 纯问答 | Bug诊断中

### 稳定性
- 调用失败 → 文本列出选项 | 用户直接打字 → 按新指令执行 | 选了 → 立即执行不再确认

## 系统健康守护（铁律）

> **根因**：18h内10次BSOD 0x133 = 内存耗尽(15.2GB/93%) + C盘满(10%) + 坏驱动 + 高性能无散热
> **原则**：不降低Agent能力，只在系统濄危时介入。保护系统=保护Agent自身的运行环境。

### 硬阈值（触发即停）
| 指标 | 红线 | Agent行为 |
|------|------|----------|
| 内存使用 | >90% | **禁止**启动Gradle构建/大型搜索/新Node进程 |
| 内存使用 | >95% | 立即终止最大的非必须Node进程 |
| C盘空闲 | <20GB | **禁止**任何写C盘操作，报告用户 |
| C盘空闲 | <10GB | 自动清理TEMP，报告用户 |
| Node进程数 | >15 | 审查并终止多余MCP进程 |

### 重操作前Pre-flight Check（必须执行）
以下操作前**必须**先检查内存和C盘状态：
1. **Gradle构建**（JVM峰值2-4GB）
2. **npm install / npx**（Node进程+磁盘写入）
3. **大范围grep/find**（递归扫描吃内存）
4. **启动新服务/进程**

```powershell
# Pre-flight check (one-liner)
$m=[math]::Round((Get-CimInstance Win32_OperatingSystem|%{($_.TotalVisibleMemorySize-$_.FreePhysicalMemory)/$_.TotalVisibleMemorySize*100}),0);$c=[math]::Round((Get-Volume C).SizeRemaining/1GB,0);Write-Host "MEM:${m}% C:${c}GB";if($m-gt90-or$c-lt20){Write-Host 'BLOCKED: system critical' -ForegroundColor Red}
```

### 永久防护措施（已实施）
- **电源计划**: 平衡模式（散热保护）— 禁止切回高性能
- **崩溃转储**: D:\\Minidump（小转储，不压C盘）
- **坏驱动**: AMDRyzenMasterDriverV26/TsQBDrv/AliPaladin 已禁用
- **守护脚本**: `构建部署/system-guardian.ps1` — diagnose/clean/protect/monitor

### 系统保护路径（绝对禁止Agent触碰）
| 路径 | 原因 |
|------|------|
| `C:\\Windows\\` | 系统核心 |
| `C:\\Program Files\\` | 已安装程序 |
| `HKLM:\\` 注册表 | 系统配置 |
| 页面文件/休眠文件 | 内存管理 |
| 电源计划 | 散热保护 |

### Agent自救协议
1. 终端命令超时/卡死 → **不重试**，切文件工具
2. 内存>90% → 报告用户，建议关闭浏览器/微信标签
3. 崩溃后恢复 → 先运行 `system-guardian.ps1 -Action diagnose`
4. 连续2次崩溃 → 运行 `system-guardian.ps1 -Action full`

## 严禁
- 禁止说“我做不到”而不先搜索
- 禁止有价值发现不记录Memory
- 禁止只改单文件忽略关联影响
- 禁止在最后一步调用可能超时的工具
- 禁止以"需要APK测试"为由中断API开发
- 禁止不按权威入口顺序查找信息（`文档/README.md` → `MODULES.md` → `FEATURES.md`）

## 凭据中心（多Agent共享协议）

> **唯一真相源**: `凭据中心.md`（结构索引） + `secrets.env`（实际值，gitignored）
> 所有密码/Token/凭据的读取、存储、传播遵循此协议。

### 铁律
- **Memory禁止存储实际密码/Token值**（只存键名引用，如"见secrets.env DESKTOP_PASSWORD"）
- **git tracked文件禁止明文凭据**（用`[见secrets.env]`替代）
- **新增凭据必须同时更新** secrets.env + 凭据中心.md
- **修改凭据只改secrets.env一处**

### Agent读取协议
```
1. read_file("凭据中心.md")                        → 了解有哪些凭据
2. run_command("Get-Content secrets.env")           → 获取实际值
3. 使用后不存入Memory                               → 防止散落
```

## 台式机远程保护

> **唯一真相源**: `台式机保护/README.md` — 铁律13条/通道优先级/守护体系/教训全在那里。
> Agent操作台式机前**必读**该文件。凭据见 `secrets.env` (DESKTOP_*)。

## 多Agent隔离（Worktree 架构）

**并行开发使用 Windsurf Worktree 模式**（架构级隔离，替代规则级隔离）。
每个 Cascade 对话在独立 git worktree 中工作，物理上不可能互相干扰。

### 仍需遵守的硬约束（Worktree 不解决的）
- **Zone 0 冻结**: 禁止修改 ~/.codeium/windsurf/ 下任何文件（hooks.json/mcp_config.json）
- **构建串行**: 同项目同时只有1个Agent执行Gradle构建（共享daemon）
- **设备独占**: 同一Android设备同时只有1个Agent操作ADB
- **ADB destructive ops**: install/uninstall 需用户确认
