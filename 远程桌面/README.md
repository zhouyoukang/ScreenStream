# 远程桌面控制 (Remote Desktop Control)

跨 Windows 账号远程全功能控制：截屏、键鼠、拖拽、窗口、进程、剪贴板、Shell、系统信息。

## 架构

```
remote_agent.py  ← 服务端（部署到目标机/目标会话，零框架依赖）
     ↕ HTTP API (20+ endpoints)
remote_desktop.html  ← 前端（6面板：窗口/快捷键/进程/剪贴板/Shell/系统）
```

## 快速启动

```powershell
pip install mss Pillow pyautogui
python remote_agent.py                  # 默认 :9903
python remote_agent.py --port 9904      # 自定义端口
python remote_agent.py --no-guard       # 禁用鼠标保护
python remote_agent.py --cooldown 3     # 自定义冷却时间
# 浏览器打开 http://127.0.0.1:9903/
```

## API（20+ 端点）

### 视觉感知
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/screenshot` | 截屏 JPEG（query: quality=70, monitor=0） |
| GET | `/windows` | 枚举可见窗口 |
| GET | `/sysinfo` | 系统信息（RAM/磁盘/分辨率/开机时长/锁屏状态） |

### 输入控制
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/key` | 按键：`{"key":"enter"}` 或 `{"hotkey":["ctrl","s"]}` |
| POST | `/click` | 点击：`{"x":500,"y":300,"button":"left","clicks":1}` |
| POST | `/type` | 打字：`{"text":"hello"}` — 非ASCII自动剪贴板+Ctrl+V |
| POST | `/move` | 鼠标移动：`{"x":500,"y":300}` — Win32 SendInput |
| POST | `/drag` | 拖拽：`{"x1":0,"y1":0,"x2":100,"y2":100,"duration":0.5}` |
| POST | `/scroll` | 滚轮：`{"x":0,"y":0,"clicks":3}` — 正=上,负=下 |

### 窗口/进程
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/focus` | 聚焦窗口：`{"title":"Windsurf"}` 或 `{"hwnd":12345}` |
| POST | `/window` | 窗口管理：`{"hwnd":12345,"action":"maximize/minimize/restore/close"}` |
| GET | `/processes` | 进程列表（name/pid/mem_kb） |
| POST | `/kill` | 结束进程：`{"pid":1234,"force":true}` |

### 数据通道
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/clipboard` | 读取远程剪贴板 |
| POST | `/clipboard` | 写入远程剪贴板：`{"text":"hello"}` |
| POST | `/shell` | 执行命令：`{"cmd":"dir","timeout":15}` |
| POST | `/volume` | 音量控制：`{"mute":true}` |

### Guard 保护
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/guard` | MouseGuard 状态 |
| POST | `/guard` | 配置：`{"enabled":true,"cooldown":2.0}` |
| POST | `/guard/pause` | 暂停保护 |
| POST | `/guard/resume` | 恢复保护 |

## 前端面板

| 面板 | 功能 |
|------|------|
| **Win** | 窗口列表 + 聚焦/最大化/最小化/关闭 |
| **Keys** | 快捷键：IDE/编辑/导航/系统/滚动/音量 |
| **Proc** | 进程管理器：搜索/排序/一键终止 |
| **Clip** | 剪贴板同步：读取/写入/PC→远程同步 |
| **Shell** | 远程终端：命令执行 + 历史(↑↓) |
| **Sys** | 系统仪表盘：RAM/磁盘/分辨率/开机时长 |

**交互增强**：拖拽模式(Drag按钮)、单击/双击防抖、右键菜单、滚轮转发、键盘捕获(Keys按钮)

## 跨会话部署

```powershell
# 本地会话
python remote_agent.py --port 9903

# 远程RDP会话 — 用计划任务启动
Register-ScheduledTask -TaskName "RemoteAgent9904" -Action (
  New-ScheduledTaskAction -Execute "python" -Argument "remote_agent.py --port 9904"
) -Principal (New-ScheduledTaskPrincipal -UserId "<RDP_USER_SID>" -LogonType Interactive)
```

## 测试

```powershell
python tests/test_remote.py                     # 默认 127.0.0.1:9905
python tests/test_remote.py --port 9903         # 自定义端口
python tests/test_remote.py --host 127.0.0.2    # 远程主机
# 19轮 / 45+ 项测试
```

## 文件结构

```
远程桌面/
├── remote_agent.py          ← 服务端（~870行，零框架，MouseGuard，20+API）
├── remote_desktop.html      ← Web前端（~720行，暗色主题，6面板，拖拽支持）
├── guard-toggle.ps1         ← 一键切换Guard状态
├── tests/
│   └── test_remote.py       ← 自动化测试（19轮，45+项）
└── README.md
```
