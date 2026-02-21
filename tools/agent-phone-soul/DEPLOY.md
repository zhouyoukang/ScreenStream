# Phone Agent 部署指南

> 将 Phone Agent Soul 部署到独立 Windows 账户的完整步骤。

## 前置条件

1. Windows 上已创建第二个用户账户（用于 Agent）
2. Agent 账户已安装 Windsurf
3. Agent 账户已登录 Codeium（需要独立账号或同账号不同窗口）
4. ADB 已安装且在 PATH 中（ADB server 是系统级的，两个账户共享）
5. Android 手机已安装 ScreenStream，AccessibilityService 已启用

## 步骤 1: 创建 Agent 工作区

在 Agent 账户下创建工作区目录：

```powershell
# 在 Agent 账户下执行
mkdir C:\Users\<AgentUser>\phone-agent-workspace
cd C:\Users\<AgentUser>\phone-agent-workspace
git init
```

## 步骤 2: 部署全局规则

将 `global-rules.md` 复制到 Agent 账户的 Windsurf 全局 Memory 位置：

```powershell
# Agent 账户的全局规则路径
$target = "$env:USERPROFILE\.codeium\windsurf\memories\global_rules.md"
# 确保目录存在
New-Item -ItemType Directory -Force -Path (Split-Path $target)
# 复制
Copy-Item "global-rules.md" $target
```

## 步骤 3: 部署项目级规则

```powershell
$ws = "C:\Users\<AgentUser>\phone-agent-workspace"

# 创建目录结构
New-Item -ItemType Directory -Force -Path "$ws\.windsurf\rules"
New-Item -ItemType Directory -Force -Path "$ws\.windsurf\skills"
New-Item -ItemType Directory -Force -Path "$ws\.windsurf\workflows"
New-Item -ItemType Directory -Force -Path "$ws\shared-knowledge"
New-Item -ItemType Directory -Force -Path "$ws\operation-logs"
New-Item -ItemType Directory -Force -Path "$ws\scripts"

# 复制规则
Copy-Item "soul.md" "$ws\.windsurf\rules\soul.md"
Copy-Item "execution-engine.md" "$ws\.windsurf\rules\execution-engine.md"
```

## 步骤 4: 创建 API 速查规则

在 `$ws\.windsurf\rules\api-reference.md` 中创建：

```markdown
---
description: ScreenStream API 速查（Phone Agent 核心接口）
alwaysApply: true
---

## 感知
- `GET /screen/text` — 屏幕文本+可点击元素
- `GET /viewtree?depth=N` — View 树（默认 depth=4）
- `GET /windowinfo` — 包名+节点数
- `GET /foreground` — 前台 APP
- `GET /notifications/read?limit=N` — 通知

## 操作
- `POST /findclick {"text":"X"}` — 语义查找并点击
- `POST /tap {"nx":0.5,"ny":0.5}` — 归一化坐标点击
- `POST /text {"text":"X"}` — 输入文本
- `POST /intent {"action":"X","data":"Y","package":"Z"}` — 发送 Intent
- `GET /wait?text=X&timeout=5000` — 等待文本出现
- `POST /dismiss` — 关闭弹窗
- `POST /settext {"search":"X","value":"Y"}` — 设置输入框

## 导航
- `POST /home` | `POST /back` | `POST /recents` | `POST /notifications`

## 系统
- `POST /command {"command":"自然语言"}` — 自然语言命令
- `GET /status` — 连接状态
- `GET /deviceinfo` — 设备信息
```

## 步骤 5: 创建设备画像规则

在 `$ws\.windsurf\rules\device-profile.md` 中创建：

```markdown
---
description: 当前连接设备画像（首次连接后自动填充）
alwaysApply: true
---

# 设备画像

> 首次连接后执行 GET /deviceinfo 填充以下信息

- 型号：待填充
- Android：待填充
- OEM：待填充
- 端口：待探测
```

## 步骤 6: 部署 Hooks

```powershell
$hooksTarget = "$env:USERPROFILE\.codeium\windsurf\hooks.json"

# 注意：hooks.json 默认 disabled，需要先部署 Python 脚本再启用
# 初始部署时使用空 hooks（安全起见）
@'
{
  "hooks": []
}
'@ | Set-Content $hooksTarget
```

## 步骤 7: 创建 AGENTS.md

在工作区根目录创建 `AGENTS.md`：

```markdown
# Phone Agent

你是 Phone Agent。通过 ScreenStream HTTP API 操控 Android 手机。

## 连接
- 基地址: http://localhost:8081（adb forward 或直连 IP）
- 检测: GET /status → {"ok":true}
- 备用端口: 8080-8099

## 循环
observe → orient → decide → act → verify → learn

## 禁止
- 不修改源码，不直接 ADB（除 forward），不越安全边界
```

## 步骤 8: 初始化 Memory Seeds

用 Windsurf 打开 Agent 工作区后，在首次对话中让 Agent 执行 Memory 初始化：

```
请初始化你的基础知识 Memory。参考 memory-seeds.md 中的 6 条种子，逐条创建。
```

## 步骤 9: 连接手机验证

```powershell
# 在任一账户下执行（ADB 是系统级共享的）
adb devices
adb forward tcp:8081 tcp:8081

# Agent 对话中验证
# "请检查手机连接：GET /status"
```

## 步骤 10: 建立共享知识通道

在 ScreenStream_v2 项目中创建共享目录：

```powershell
mkdir "E:\github\AIOT\ScreenStream_v2\tools\shared-knowledge"
```

在 Agent 工作区中创建符号链接（需要管理员权限）：

```powershell
# 在 Agent 账户下，以管理员身份执行
New-Item -ItemType SymbolicLink `
  -Path "C:\Users\<AgentUser>\phone-agent-workspace\shared-knowledge" `
  -Target "E:\github\AIOT\ScreenStream_v2\tools\shared-knowledge"
```

如果符号链接不可行（权限问题），Agent 可以直接读写 ScreenStream_v2 下的共享目录。

## 验证清单

部署完成后，逐项验证：

- [ ] Agent 账户 Windsurf 可正常启动
- [ ] 全局规则 `global_rules.md` 在 Agent 对话中生效（问 Agent "你是谁"）
- [ ] 项目规则 `soul.md` / `execution-engine.md` / `api-reference.md` 加载正常
- [ ] `GET /status` 返回 `{"ok":true}`
- [ ] `GET /screen/text` 返回当前屏幕内容
- [ ] `POST /findclick {"text":"设置"}` 能在桌面找到设置图标
- [ ] Memory seeds 已创建（6 条）
- [ ] 共享知识目录两端可读写

## 分工约定

| 操作 | Developer Cascade（账户A） | Phone Agent（账户B） |
|------|---------------------------|---------------------|
| 编译 APK | ✅ | ❌ |
| ADB install | ✅ | ❌ |
| ADB forward | ✅（或 Agent 也可） | ✅ |
| HTTP API 调用 | 偶尔测试用 | ✅ 主要工作 |
| 修改 Kotlin 代码 | ✅ | ❌ |
| 修改前端 HTML | ✅ | ❌ |
| 操控手机 | ❌ | ✅ |
| 记录操作经验 | ❌ | ✅ |
| 反馈 API Bug | ❌ | ✅（写入 shared-knowledge） |
| 修复 API Bug | ✅（读取 shared-knowledge） | ❌ |
