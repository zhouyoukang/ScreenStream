---
name: terminal-resilience
description: 终端卡死诊断与Agent五感降级恢复。当终端命令无响应、交互式prompt阻塞、或用户反馈"卡住了"时自动触发。
triggers:
  - 终端命令超时无响应
  - 用户取消命令或反馈卡顿
  - 交互式prompt阻塞（密码/确认/选择）
  - 命令输出异常（过多/过少/乱码）
---

# Agent 五感降级模型 & 终端韧性

> 从46次真实对话+12次终端事故中提炼。
> 核心洞察：**Agent的能力本质是五种感官，每种都有降级路径和恢复策略。**

## 一、Agent 五感定义

| 感官 | 能力 | 正常状态工具 | 降级信号 |
|------|------|-------------|---------|
| **👁 视觉** | 读取信息 | read_file, grep_search, list_dir, command_status | 终端无输出、文件被锁、输出截断 |
| **👂 听觉** | 接收反馈 | command_status, 终端返回码, 浏览器console | 命令不结束、无返回码、沉默超时 |
| **✋ 触觉** | 执行操作 | edit, write_to_file, run_command, MCP交互 | 终端阻塞、权限拒绝、文件锁 |
| **👃 嗅觉** | 预判风险 | Memory, rules, 模式识别, code_search | 上下文丢失、陌生系统、首次操作 |
| **👅 味觉** | 验证结果 | read_file验证, 浏览器E2E, grep确认 | 无法读输出、测试框架缺失 |

## 二、七类终端卡死模式（全量枚举）

### 🔴 C1: 交互式Prompt阻塞（Agent完全致盲）
**现象**：命令等待键盘输入，Agent无法输入 → 终端永久挂起
**感官影响**：👁视觉✗ 👂听觉✗ ✋触觉✗ = **三感丧失**

| 触发命令 | 阻塞原因 | 预防方案 |
|----------|---------|---------|
| `ssh git@host` | SSH passphrase/密码 | ssh-agent缓存 或 无密码密钥 |
| `git push` (SSH) | SSH passphrase | 同上 / 用HTTPS+token |
| `git pull/push` (HTTPS) | credential prompt | `git config credential.helper manager` |
| `sudo xxx` | 密码 | `-S` flag + echo pipe / 或避免sudo |
| `npm publish` | OTP/login | `--otp=xxx` flag |
| `rm -i`/`del /p` | 逐文件确认 | `-f`/`/q` 强制flag |
| `choco install` | UAC/y确认 | `-y` flag |
| `python input()` | 等stdin | 避免交互脚本 / 用参数替代 |
| `Read-Host` | PS等输入 | 用参数传入 / 避免交互 |
| `pause` | 按任意键 | 替换为 timeout 或 删除 |

**铁律**：任何可能弹出交互式prompt的命令，**必须加非交互flag**或**用文件工具替代**。

### 🔴 C2: Shell Integration失效（Agent失聪）
**现象**：命令已结束但Cascade认为仍在运行 → ⊙转圈不停 → 用户卡死
**感官影响**：👂听觉✗ = 无法知道命令是否结束

| 触发原因 | 预防方案 |
|----------|---------|
| PowerShell hooks (全局hooks.json) | 绝对禁止PS hooks |
| terminal profile未设置 | settings.json: defaultProfile = "PowerShell" |
| shellIntegration关闭 | settings.json: shellIntegration.enabled = true |
| 自定义PS1干扰检测 | 使用标准prompt |
| conda/venv activate改写prompt | 检查后恢复 |

**铁证**：2026-02-13事故，全局hooks.json的PS钩子导致所有窗口卡死。

### 🟠 C3: 无界递归扫描（Agent溺水）
**现象**：命令扫描超大目录，输出海量 → 终端卡顿 → IDE卡死
**感官影响**：👁视觉过载 👂听觉延迟 = 信息洪水

| 触发命令 | 替代方案 |
|----------|---------|
| `Get-ChildItem -Recurse` | `find_by_name`（50条上限） |
| `Select-String -Recurse` | `grep_search`（自动gitignore） |
| `dir -r` / `tree` | `list_dir` |
| `git log`（无限制） | `git log -n 20` |
| `git diff`（大变更） | `git diff --stat` |
| `find / -name "*.py"` | `find_by_name` + 指定子目录 |

### 🟠 C4: 网络超时挂起（Agent等待）
**现象**：命令等待网络响应 → 无限期挂起
**感官影响**：👂听觉✗ ✋触觉✗ = 等待中失去操作能力

| 触发命令 | 预防方案 |
|----------|---------|
| `git push/pull`（代理失败） | `-c http.proxy=""` 绕过 / 加timeout |
| `curl`（无超时） | `curl.exe --connect-timeout 10 -m 30` |
| `npm install`（慢源） | `--registry https://registry.npmmirror.com` |
| `pip install`（慢源） | `-i https://pypi.tuna.tsinghua.edu.cn/simple` |
| `Invoke-WebRequest`（无超时） | `-TimeoutSec 15` |
| `ssh`（连接超时） | `-o ConnectTimeout=10` |

### 🟡 C5: 进程/资源冲突（Agent被阻）
**现象**：目标资源被占用 → 命令阻塞等待释放
**感官影响**：✋触觉✗ = 无法操作目标

| 冲突类型 | 检测方法 | 解决方案 |
|----------|---------|---------|
| 端口被占 | `netstat -ano \| findstr :PORT` | 换端口 / 杀进程 |
| SQLite锁 | `conn.close()` 遗漏 | 确保finally块关闭 |
| 文件被锁 | 打开句柄检查 | 等待 / 复制后操作 |
| Gradle daemon忙 | `--no-daemon` | 串行构建 |
| ADB设备占用 | `adb devices` | 设备独占规则 |

### 🟡 C6: 权限/安全拦截（Agent被拒）
**现象**：操作被系统/安全软件拦截 → 命令失败或挂起
**感官影响**：✋触觉✗ = 操作被拒

| 拦截类型 | 现象 | 绕过方案 |
|----------|------|---------|
| UAC提权 | 弹窗等待 | 创建管理员脚本 |
| .gitignore阻止 | read_file报错 | 编辑.gitignore |
| 杀软拦截 | 静默失败 | 白名单 / 改路径 |
| Vivo安装拦截 | INSTALL_FAILED | 手动安装 / 开开关 |
| OPPO自启动拦截 | 弹窗拦截intent | ADB appops |
| 系统保护路径 | 写入拒绝 | 创建.ps1脚本 |

### 🟢 C7: 长时任务误标阻塞（Agent误判）
**现象**：命令正常运行但耗时超预期 → Agent以为卡死
**感官影响**：👂听觉延迟 = 反馈太慢被误判

| 场景 | 正常耗时 | 处理方案 |
|------|---------|---------|
| Gradle首次构建 | 2-5min | 非阻塞 + WaitMs=5000 |
| PaddleOCR首次加载 | ~30s | 预热 / 异步 |
| npm install (大项目) | 1-3min | 非阻塞 + 定期检查 |
| APK安装 (大文件) | 10-30s | 非阻塞 |
| 数据库迁移 | 变化大 | 非阻塞 + 日志 |

## 三、五感降级恢复链

> 每种感官降级时，按序尝试恢复。第一个成功的即停。

### 👁 视觉降级恢复链
```
终端输出不可见
  → command_status 检查命令状态
    → 输出重定向到文件 + read_file
      → find_by_name/grep_search 搜索生成的文件
        → 请用户截图/描述终端状态
```

### 👂 听觉降级恢复链
```
命令是否结束不确定
  → command_status (WaitDurationSeconds=5)
    → 非阻塞命令：检查进程是否存在
      → 文件工具验证副作用（文件是否生成/修改）
        → 请用户确认终端⊙状态
```

### ✋ 触觉降级恢复链
```
终端无法发送新命令
  → 切换到文件工具（edit/write_to_file）
    → 创建.ps1脚本让用户执行
      → 使用MCP工具（Playwright/DevTools）
        → 请用户在终端手动输入
```

### 👃 嗅觉降级恢复链
```
无法预判当前操作风险
  → 搜索Memory中类似场景
    → search_web + context7查文档
      → 读取rules/中的已有规则
        → 先只读探测，再小步操作
```

### 👅 味觉降级恢复链
```
无法验证操作结果
  → read_file检查目标文件
    → grep_search搜索变更证据
      → Playwright浏览器验证
        → 请用户确认结果
```

## 四、即时诊断协议

当检测到终端卡死信号（用户取消/超时/无输出），执行：

```
Step 1: 分类 — 属于C1-C7哪类？
  ↓
Step 2: 评估 — 哪些感官受影响？
  ↓
Step 3: 恢复 — 按对应感官的恢复链执行
  ↓
Step 4: 切换 — 恢复失败→完全切换到文件工具模式
  ↓
Step 5: 记录 — Memory记录本次卡死模式+解法
```

### 快速判断表

| 用户信号 | 最可能的类型 | 第一反应 |
|---------|-------------|---------|
| 取消了run_command | C1交互prompt / C4网络超时 | 切换文件工具，不重试 |
| "终端在转圈" | C2 shell integration | 让用户Ctrl+C，检查hooks |
| "好慢" | C3递归 / C7长任务 | 改用文件工具 / 告知预期时间 |
| "报错了" | C5冲突 / C6权限 | 读错误信息，定位根因 |
| 长时间无反馈 | C4网络 / C7长任务 | command_status探测 |

## 五、预防检查清单（发命令前）

每条 `run_command` 之前，Agent必须自检：

- [ ] **C1检查**：这条命令可能弹交互prompt吗？→ 加 `-y`/`-f`/`--no-input` flag
- [ ] **C2检查**：hooks.json是否安全？→ 禁止PS hooks
- [ ] **C3检查**：会递归扫描大目录吗？→ 改用文件工具
- [ ] **C4检查**：涉及网络吗？→ 加超时参数
- [ ] **C5检查**：目标资源可能被占用吗？→ 先检测再操作
- [ ] **C6检查**：需要特殊权限吗？→ 先评估再执行
- [ ] **C7检查**：耗时可能超30s吗？→ 用非阻塞模式

## 六、Git操作专项（高频卡死区）

Git是Agent终端卡死的**头号重灾区**，单独列出：

| 操作 | 风险 | 安全写法 |
|------|------|---------|
| `git push` (SSH) | C1: passphrase | 确保ssh-agent运行 或 用HTTPS |
| `git push` (HTTPS) | C1: credential | `credential.helper=manager` |
| `git push` (代理) | C4: 网络超时 | `-c http.proxy="" ` 绕过 |
| `git clone` (大仓库) | C7: 耗时长 | `--depth 1` 浅克隆 |
| `git log` | C3: 输出过多 | `-n 20` 限制 |
| `git diff` | C3: 大变更 | `--stat` 或 `--name-only` |
| `git stash pop` | C5: 冲突 | 先 `stash show` 检查 |
| `git merge` | C1: 编辑器 | `--no-edit` flag |
| `git rebase -i` | C1: 交互编辑器 | 避免在Agent中用 |
| `git commit` | C1: 编辑器 | `-m "msg"` 直接传消息 |

## 七、降级模式全景

```
正常模式（五感完整）
  │
  ├─ 视觉降级 → 文件工具模式（read_file/grep_search替代终端输出）
  │
  ├─ 听觉降级 → 轮询验证模式（command_status + 文件副作用检测）
  │
  ├─ 触觉降级 → 脚本委托模式（创建.ps1脚本让用户执行）
  │
  ├─ 嗅觉降级 → 谨慎探测模式（只读工具 + 搜索 + 小步执行）
  │
  ├─ 味觉降级 → 多源验证模式（文件+浏览器+用户确认三重验证）
  │
  └─ 全感降级 → 用户指挥模式（L4: 描述现状+已尝试+请求指导）
```

## 八、实战案例库

### 案例1: SSH Passphrase 卡死（2026-02-22）
- **类型**: C1 交互式Prompt
- **感官**: 👁✗ 👂✗ ✋✗（三感丧失）
- **根因**: id_ed25519有密码保护 + SSH config走代理
- **解法**: fix-ssh-agent.ps1（启动Windows ssh-agent服务 + 缓存密钥）
- **预防**: Agent发git push前检查ssh-agent状态

### 案例2: 全局Hooks导致所有窗口卡死（2026-02-13）
- **类型**: C2 Shell Integration失效
- **感官**: 👂✗（失聪——命令结束但检测不到）
- **根因**: hooks.json中PS钩子干扰提示符检测
- **解法**: 清空hooks.json
- **预防**: hooks.json铁律写入rules

### 案例3: android-sdk递归扫描IDE卡死
- **类型**: C3 无界递归
- **感官**: 👁过载 👂延迟
- **根因**: Get-ChildItem -Recurse 扫描1GB SDK目录
- **解法**: 改用find_by_name工具
- **预防**: 防卡顿铁律写入rules

### 案例4: Git Push代理超时
- **类型**: C4 网络超时
- **感官**: 👂✗ ✋✗
- **根因**: Clash代理对GitHub TLS不兼容
- **解法**: `-c http.proxy=""` 绕过
- **预防**: Git操作专项规则

### 案例5: Vivo安装拦截无限等待
- **类型**: C6 安全拦截
- **感官**: ✋✗ 👂✗
- **根因**: Vivo固件级USB安装拦截
- **解法**: 用户手动开开关 / 手动安装APK
- **预防**: 设备检测后提前告知

### 案例6: Junction目录PowerShell写入破坏
- **类型**: C6变体 — 操作副作用超预期
- **感官**: 👅✗（验证缺失——操作"成功"但实际破坏了junction）
- **根因**: Set-Content在junction中创建新文件而非原地更新
- **解法**: 使用edit/multi_edit工具替代
- **预防**: junction目录禁止PowerShell写入
