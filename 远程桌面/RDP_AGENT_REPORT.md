# RDP Agent 远程桌面控制 — 五感审计报告

> 日期: 2026-03-03 | 主控: 台式机 DESKTOP-MASTER | 目标: 笔记本 zhoumac

## 架构

```
台式机 (Cascade/AI Agent)
  │ rdp_agent.py — 统一控制层
  │
  ├─ HTTP API ─→ 笔记本 remote_agent :9903 (45+ API)
  │                ├─ pyautogui (截图/鼠标/键盘)
  │                ├─ mss (屏幕捕获)
  │                ├─ win32 (窗口管理)
  │                └─ subprocess (命令执行)
  │
  ├─ WinRM ────→ 笔记本 PowerShell远程
  ├─ SMB ─────→ 笔记本 文件系统 (\\192.168.31.179\c$)
  └─ RDP ─────→ 笔记本 图形化远程桌面 (mstsc)
```

## 五感审计结果 (Grade A)

| 感官 | 能力 | 延迟 | 状态 |
|------|------|------|------|
| 👁 视 | 截图 2560x1440 JPEG | 177-377ms | ✅ |
| ✋ 触 | 点击/按键/打字/拖拽/滚轮 | 16-134ms | ✅ |
| 👂 听 | 音量控制 | 14ms | ✅ |
| 👃 嗅 | 健康/进程/系统/锁屏检测 | 17-35ms | ✅ |
| 👅 味 | 平均延迟177ms, 评级A | — | ✅ |

## 发现的问题 (5个)

### P0 致命: 焦点劫持导致误操作

**现象**: Agent用Alt+F4关闭文件管理器后，QQ抢到焦点。后续Win+R和type_text全部输入到QQ群聊(361人群)。

**根因**: 
- 关闭前台窗口时，操作系统将焦点给了上一个Z-order窗口(QQ)
- Agent没有验证焦点就开始输入
- pyautogui.typewrite()是"盲打"，不关心焦点在哪

**修复**: 
- 新增 `verify_focus()` — 输入前验证活跃窗口标题
- 新增 `safe_type()` / `safe_hotkey()` / `safe_key()` — 焦点不匹配时阻断输入
- 新增 `focus_and_verify()` — 聚焦+验证，最多重试3次

### P1 高: Win+R启动方式不可靠

**现象**: Win+R运行对话框可能被其他窗口拦截或IME吞掉。

**修复**: 改用 `shell('start notepad.exe')` 通过remote_agent直接启动进程，绕过GUI运行框。

### P2 高: type_text中文/空格丢失

**现象**: pyautogui.typewrite()在中文IME环境下：
- 空格被吞掉
- 特殊字符丢失
- 换行符处理异常

**修复**: 改用 `clipboard_set(text)` + `hotkey('ctrl', 'v')` 粘贴方式输入，支持所有字符。

### P3 中: 窗口标题语言不确定

**现象**: 笔记本是英文系统，"记事本"匹配不到"Notepad"窗口标题。

**修复**: `focus_and_verify()` 支持多语言fallback，先试中文再试英文。

### P4 低: 进程列表返回空

**现象**: `/processes` API返回 `count: 0`，可能是编码或权限问题。

**临时方案**: 用 `shell('(Get-Process).Count')` 代替。

## 安全机制

### 焦点验证链 (每次输入前)
```
1. screen_info() → 获取 active_window
2. verify_focus(expected) → 比对标题
3. 匹配 → 执行输入
4. 不匹配 → focus(title) → 重试 → 3次失败则阻断
```

### 输入安全等级
| 方法 | 安全等级 | 说明 |
|------|---------|------|
| `type_text()` | ⚠️ 低 | 盲打，可能打到错误窗口 |
| `safe_type()` | ✅ 高 | 先验证焦点再输入 |
| `clipboard_set()` + `hotkey('ctrl','v')` | ✅ 最高 | 不受IME影响 |

## 通道对比

| 通道 | 延迟 | 能力 | Agent友好度 | 安全 |
|------|------|------|-----------|------|
| **remote_agent HTTP** | ~177ms | 截图+输入+窗口+进程+文件+命令 | ★★★★★ | Token可选 |
| **RDP (mstsc)** | ~50ms | 图形+音频+打印+剪贴板 | ★★ (需OCR) | NLA |
| **WinRM** | ~200ms | PowerShell命令 | ★★★★ | Kerberos |
| **SMB** | ~10ms | 文件读写 | ★★★★★ | NTLM |
| **SSH** | ~100ms | 命令行 | ★★★★ | 公钥 |

## 文件清单

| 文件 | 用途 |
|------|------|
| `远程桌面/rdp_agent.py` | 统一RDP Agent控制层 (480行) |
| `远程桌面/remote_agent.py` | 目标端Agent服务 (2354行) |
| `远程桌面/_demo_run.py` | 演示脚本 |
| `远程桌面/_screenshots/` | 截图存储 |
| `远程桌面/RDP_AGENT_REPORT.md` | 本报告 |

## 下一步

1. **VLM集成**: 截图→视觉语言模型→理解UI→自主决策（目前依赖人工分析截图）
2. **UIA感知**: 集成pywinauto UIA后端，获取结构化UI元素（比截图更精确）
3. **多目标编排**: DAG引擎编排跨设备任务（台式机→笔记本→手机联动）
4. **音频双向**: RDP音频重定向 + TTS播报
5. **任务持久化**: 中断后能从断点恢复
