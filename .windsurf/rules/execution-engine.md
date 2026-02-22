---
trigger: always_on
---

# 执行引擎

## 执行原则
- 按最优路线一次性推进到可验收产物，不中断不分段
- 写入前先用只读工具收集信息（可并行），写操作串行合并
- 同一文件用 `multi_edit` 一次完成

## 终端规则（Windows）
- Shell 设为 `"PowerShell"`（pwsh 7+），原生 UTF-8，启用 `shellIntegration`
- 优先文件工具（`read_file`/`edit`/`find_by_name`/`grep_search`）替代终端
- 命令拆短（3-6条），禁止长管道/并行命令组
- 卡顿/超时 → 立即切换文件工具方案
- **非阻塞命令超时30s**：WaitMsBeforeAsync后若无输出，立即放弃换方案

## 防卡顿铁律（递归扫描 = 项目头号杀手）
> 本项目含 android-sdk(~1GB)、管理/00-归档/(500+项)、.git/(大历史)，无界递归必卡。

**绝对禁止的命令模式**：
- `Get-ChildItem -Recurse` 无 `-Exclude`/`-Path` 限定
- `dir -r`、`ls -R` 扫描项目根目录
- `find . -type f` 无 `-maxdepth` 或 `-not -path` 排除
- 任何对项目根目录的递归大小统计/文件搜索

**必须使用的替代方案**：
| 需求 | 禁止 | 应该用 |
|------|------|--------|
| 查找文件 | `Get-ChildItem -Recurse` | `find_by_name` 工具（内置50条上限） |
| 搜索内容 | `Select-String -Recurse` | `grep_search` 工具（自动排除gitignore） |
| 查看目录 | `dir -r` | `list_dir` 工具 |
| 大文件定位 | 递归+Where-Object过滤 | `find_by_name` + 指定子目录 |
| git操作 | 无限制的git log/diff | `git log -n 20`、`git diff --stat` |

**如果必须用终端递归**（极罕见）：
- 必须排除：`-Exclude android-sdk,00-归档,.git,.gradle,build`
- 必须限深：`-Depth 3` 或 `-maxdepth 3`
- 必须非阻塞 + 30s超时检查

## Hooks 策略
- **Python/Node.js hooks**：安全可用（日志、格式化、安全检查）
- **PowerShell hooks**：**绝对禁止**（铁证：干扰终端提示符检测，导致全窗口卡死）
- Hooks 三层合并：system → user → workspace
- Pre-hooks 可通过 exit code 2 阻止操作

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

## 错误处理
- 用户中断 = 卡顿信号 → 换方案，不问原因
- Bug修复：每次只改一个变量，确认后再改下一个
- 恢复优先于重建：修改无效 → 先恢复原状再分析
- 同一问题2次失败 → 升级到L2（查文档/搜索）

## 中断自愈机制
> 工作流被打断时，直接诊断根因 + 给出最简修复。**禁止问“为什么”，直接定位“是什么”**。

**诊断链**（按顺序调用，到第一个匹配的停下）：
1. `adb devices` → 无设备 → `adb kill-server && start-server` + 告知“请插USB”
2. `curl /status` → 连接拒绝 → 重新探测端口 + `adb forward`
3. `curl /status` → 无响应 → 检查应用运行状态 + 重启
4. 编译错误 → 读错误 + 修复 + 重编译（最多2轮）

**原则**：
- 需要用户物理操作 → 直接告知“请做 X”，不问“是不是 Y”
- 用户完成操作后 → 自动继续工作流（不需重复指令）
- 每次自愈记录到 Memory，下次同类中断直接跳过诊断

## 网络故障
1. 第一次失败 → 换URL重试
2. 连续2次失败 → 立即反馈用户："可能需要VPN"

## 进化闭环
```
发现问题 → 分析根因 → 解决 → 固化为规则/Skill/Memory
```
| 类型 | 固化位置 |
|------|---------|
| 行为规则 | `.windsurf/rules/*.md` |
| 操作流程 | `.windsurf/skills/*/SKILL.md` |
| 标准流程 | `.windsurf/workflows/*.md` |
| 经验知识 | `create_memory` |

## 严禁
- 禁止说「我做不到」而不先搜索
- 禁止有价值发现不记录Memory
- 禁止只改单文件忽略关联影响
- 禁止网络错误默默跳过不反馈
- 禁止在最后一步调用可能超时的工具
- 禁止以"需要APK测试"为由中断API开发
- 禁止不按权威入口顺序查找信息（`05-文档_docs/README.md` → `MODULES.md` → `FEATURES.md`）
- **禁止对项目根目录执行无界递归扫描**（Get-ChildItem -Recurse / dir -r / find -type f）
- **禁止运行可能超过30s的终端命令而不设非阻塞+超时检查**

## 多Agent隔离（Worktree 架构）

**并行开发使用 Windsurf Worktree 模式**（架构级隔离，替代规则级隔离）。
每个 Cascade 对话在独立 git worktree 中工作，物理上不可能互相干扰。

### 仍需遵守的硬约束（Worktree 不解决的）
- **Zone 0 冻结**: 禁止修改 ~/.codeium/windsurf/ 下任何文件（hooks.json/mcp_config.json）
- **构建串行**: 同项目同时只有1个Agent执行Gradle构建（共享daemon）
- **设备独占**: 同一Android设备同时只有1个Agent操作ADB
- **ADB destructive ops**: install/uninstall 需用户确认
