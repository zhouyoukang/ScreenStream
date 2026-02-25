# 远程桌面控制 (Remote Desktop Control)

跨 Windows 账号远程全功能控制：截屏、键鼠、拖拽、窗口、进程、剪贴板、Shell、系统信息。

**手机完整支持** — 触摸点击、长按右键、滑动滚屏、双指缩放、底部导航栏、响应式布局。

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

## API（30+ 端点）

### 视觉感知
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/screenshot` | 截屏 JPEG（query: quality=70, monitor=0） |
| GET | `/windows` | 枚举可见窗口 |
| GET | `/sysinfo` | 系统信息（RAM/磁盘/分辨率/开机时长/锁屏状态） |
| GET | `/screen/info` | 屏幕状态（锁屏检测+当前活动窗口，移动端状态栏用） |

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
| POST | `/wakeup` | 唤醒屏幕（模拟Shift键按下） |

## 前端面板

| 面板 | 功能 |
|------|------|
| **Win** | 窗口列表 + 聚焦/最大化/最小化/关闭 |
| **Keys** | 快捷键：IDE/编辑/导航/系统/滚动/音量 |
| **Files** | 文件浏览器：目录导航/下载/删除/面包屑 |
| **Proc** | 进程管理器：搜索/排序/一键终止 |
| **Clip** | 剪贴板同步：读取/写入/PC→远程同步 |
| **Shell** | 远程终端：命令执行 + 历史(↑↓) |
| **Sys** | 系统仪表盘：RAM/磁盘/电源/网络/服务管理 |

### 桌面端交互
拖拽模式(Drag按钮)、单击/双击防抖、右键菜单、滚轮转发、键盘捕获(Keys按钮)

### 手机端交互（触摸五感）
| 手势 | 效果 |
|------|------|
| **单指点按** | 左键单击 |
| **快速双击** | 左键双击 |
| **长按500ms** | 右键单击（带振动反馈） |
| **单指滑动** | 远程滚屏 |
| **双指捏合** | 缩放截图视图（1x-5x） |
| **双击空白** | 重置缩放至1x |

**移动端布局**：底部5键导航栏 → 全屏面板覆盖 → ✕关闭回到截屏

## 跨会话部署（手机控制另一Windows账号）

```powershell
# 1. 开放防火墙（管理员权限运行一次）
powershell -ExecutionPolicy Bypass -File setup-firewall.ps1

# 2. 在目标会话启动Agent
python remote_agent.py --port 9903         # 本地会话
python remote_agent.py --port 9904         # 远程RDP会话
python remote_agent.py --port 9903 --token mypass  # 带密码保护

# 3. 手机浏览器打开
http://192.168.x.x:9903/                  # 替换为电脑局域IP
```

### 手机使用技巧（OPPO/小米/华为等Android）
1. **添加到主屏幕** — Chrome菜单 → “添加到主屏幕”，以PWA全屏模式运行（去掉地址栏）
2. **横屏操作** — 横屏时截图几乎占满全屏，体验最佳
3. **关闭边缘手势** — 设置 → 便捷工具 → 关闭边缘滑动返回，避免触摸冲突
4. **剪贴板同步** — HTTP下无法自动读取手机剪贴板，手动粘贴到Clip面板然后点Write

## 测试

```powershell
python tests/test_remote.py                     # 默认 127.0.0.1:9905
python tests/test_remote.py --port 9903         # 自定义端口
python tests/test_remote.py --host 127.0.0.2    # 远程主机
# 24轮 / 55+ 项测试
```

### Guardian Engine（自治守护引擎）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/guardian/status` | 守护引擎状态（uptime/任务统计/网络/进程） |
| GET | `/tasks` | 任务队列（?status=pending&limit=20） |
| POST | `/tasks` | 提交任务：`{"action":"shell","params":{"cmd":"..."},"scheduled_at":1234}` |
| POST | `/tasks/cancel` | 取消任务：`{"id":"xxx"}` |
| POST | `/tasks/clear` | 清理旧任务：`{"max_age_hours":24}` |
| GET | `/rules` | 规则列表 |
| POST | `/rules` | 添加规则：`{"name":"..","trigger_type":"network_down","action":"shell","params":{}}` |
| POST | `/rules/delete` | 删除规则：`{"id":"xxx"}` |
| POST | `/rules/toggle` | 启停规则：`{"id":"xxx","enabled":true}` |
| GET | `/network/status` | 网络连通性检测（3DNS+网关） |
| POST | `/network/heal` | 网络自愈（DHCP→WiFi重连→网卡重置→DNS刷新） |
| POST | `/network/check` | 手动触发网络检查 |
| GET | `/watchdog` | 进程监控状态 |
| POST | `/watchdog/watch` | 监控进程：`{"name":"python.exe"}` |
| POST | `/watchdog/unwatch` | 取消监控 |
| GET | `/events` | 事件日志（?limit=30） |

#### 规则触发器类型
| trigger_type | 触发条件 | 示例trigger_config |
|---|---|---|
| `network_down` | 网络断开 | `{}` |
| `network_up` | 网络恢复 | `{}` |
| `process_exit` | 进程退出 | `{"name":"gateway.py"}` |
| `cron` | 定时触发 | `{"hour":"3","minute":"0","cooldown":300}` |
| `session_disconnect` | 会话断开 | `{}` |

#### 网络自愈链（逐级升级）
1. `ipconfig /renew` — DHCP续约
2. `netsh wlan disconnect + connect` — WiFi重连
3. `Disable-NetAdapter + Enable` — 网卡重置
4. `ipconfig /flushdns` — DNS刷新

## 文件结构

```
远程桌面/
├── remote_agent.py          ← 服务端（~2300行，零框架，45+API，Guardian引擎）
├── remote_desktop.html      ← Web前端（~2500行，PWA+触摸+9面板+Android适配）
├── guardian.db              ← SQLite运行时数据库（自动创建，gitignore）
├── manifest.json            ← PWA清单（添加到主屏幕全屏模式）
├── setup-firewall.ps1       ← 防火墙配置（允许手机访问）
├── guard-toggle.ps1         ← 一键切换Guard状态
├── auto-start.ps1           ← 开机自启配置（计划任务）
├── tests/
│   └── test_remote.py       ← 自动化测试（24轮，55+项）
└── README.md
```
