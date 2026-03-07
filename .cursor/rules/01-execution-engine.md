---
trigger: always_on
---

# 执行引擎 — Cursor

> 此文件为"法"层——释迦·中道之实例化。道层见 00-soul.md，术层见 project-structure.md + skills。

## 执行原则

- 一次性推进到可验收产物；只读先行(可并行)，写操作串行
- 同一文件用 `multi_edit` 一次完成
- **终端安全原则：文件工具(无状态,总返回) ≫ 终端(有状态,可能永久挂起)**

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

## 开发管线（Phase模型）

|| Phase | 模式 | 规则 |
|-------|------|------|
|| 0-2 分析/设计 | 只读 | 可并行 |
|| 3 实现 | 写入 | 串行，multi_edit |
|| 4 构建 | 终端 | 非阻塞，最多2轮修复 |
|| 5 部署 | 终端 | 逐步确认 |
|| **5.5 E2E验证** | 终端+浏览器 | **API ok ≠ 前端可用**，必须模拟用户实操 |
|| **5R 中断自愈** | 自动 | 任何Phase被打断时自动触发 |
|| 6-7 文档/总结 | 写入 | 可并行 |

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
4. 终端卡死 → 分类C1-C7 → 按恢复链执行

> **注意**: 公网/FRP/aiotvr.xyz 问题**不属于**中断自愈范围。仅当用户明确要求时才检查公网状态。

## 网络请求

> **代理感知**: `clash-agent/proxy_sense.py`

|| 需求 | 工具 | 代理 |
|------|------|------|
|| 国外网页/HTML | `IWR -Proxy "http://127.0.0.1:7890" -UseBasicParsing` | ✅ |
|| 国外JSON API | `IRM -Proxy "http://127.0.0.1:7890"` | ✅ |
|| 国内网页/API | `IWR`/`IRM` (直连) | ❌ |
|| JS渲染SPA | Playwright | 自动 |
|| 搜索 | `search_web` | 内置 |

### 代理判断规则

- **需要代理**: `github.com` `npmjs.org` `pypi.org` `docker.com` `google.com` `openai.com`
- **不需要代理**: `127.0.0.1` `localhost` `192.168.*` `aiotvr.xyz` 国内站点

## 严禁

- 禁止说"我做不到"而不先搜索
- 禁止有价值发现不记录Memory
- 禁止只改单文件忽略关联影响
- 禁止在最后一步调用可能超时的工具
- 禁止以"需要APK测试"为由中断API开发
- 禁止不按权威入口顺序查找信息

## 凭据中心

> **唯一真相源**: `凭据中心.md`（结构索引） + `secrets.env`（实际值，gitignored）

### 铁律

- **Memory禁止存储实际密码/Token值**（只存键名引用）
- **git tracked文件禁止明文凭据**（用`[见secrets.env]`替代）
- 新增凭据必须同时更新 secrets.env + 凭据中心.md
- 修改凭据只改secrets.env一处

## 与Windsurf的协作边界

> Cursor负责代码深度，Windsurf负责外设操作

| 任务类型 | 执行者 | 说明 |
|---------|--------|------|
| 代码编写/重构 | **Cursor** | 深度思考，安全可靠 |
| 代码审查 | **Cursor** | 多维度分析 |
| 浏览器操作 | Windsurf | Playwright MCP |
| ADB设备控制 | Windsurf | 手机操控 |
| 终端实时输出 | Windsurf | 长时任务 |

---

*此文件为Cursor执行引擎，始终加载。*
