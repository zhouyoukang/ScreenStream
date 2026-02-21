# ScreenStream v32 使用指南

> 本文档说明 v32 版本的所有功能、操作方法和使用场景。包含远程协助 + AI Brain 能力。

## 快速开始

1. **手机端**：打开 ScreenStream 应用 → 授权 AccessibilityService → 点击"开始投屏"
2. **PC 端**：浏览器打开 `http://手机IP:8081`（或通过 Gateway `http://手机IP:8080`）
3. **远程控制**：在投屏画面上直接点击/滑动/打字

---

## 导航栏三模式切换

底部导航栏通过左侧「🔄 切换按钮」在 3 种模式之间循环切换：

### 模式 1：导航模式（默认）
| 按钮 | 功能 | 说明 |
|------|------|------|
| ▢ | 最近任务 | 显示多任务切换界面 |
| ○ | 主页 | 回到桌面 |
| ← | 返回 | 返回上一页 |

### 模式 2：控制模式（蓝色高亮）
| 按钮 | 功能 | 说明 |
|------|------|------|
| 画中画 | PiP 模式 | 将投屏画面缩小为浮窗 |
| 音频 | 音频开关 | 开启/关闭远程音频流 |
| 全屏 | 全屏切换 | 切换全屏显示 |

### 模式 3：系统控制模式（橙色高亮）
| 按钮 | 功能 | 说明 |
|------|------|------|
| 🔈 | 音量 - | 降低手机媒体音量 |
| 🔊 | 音量 + | 增大手机媒体音量 |
| 🔒 | 锁屏 | 远程锁定手机屏幕 |
| 🔔 | 通知栏 | 下拉手机通知栏 |

### 模式 4：远程协助模式（紫色高亮）🆕
| 按钮 | 功能 | 说明 |
|------|------|------|
| ☀️ | 唤醒屏幕 | 远程点亮手机屏幕（息屏时可用） |
| 📷 | 截屏 | 在手机上截取当前屏幕 |
| ⏻ | 电源菜单 | 显示手机电源对话框（关机/重启） |
| ℹ️ | 设备信息 | 显示设备详细信息面板 |

---

## 键盘快捷键

在投屏画面获得焦点后，PC 键盘的按键会映射到手机：

### 通用快捷键
| PC 键盘 | 手机动作 |
|---------|---------|
| Esc | 返回键 |
| Backspace | 删除字符 |
| Enter | 回车/确认 |
| Tab | Tab 切换焦点 |
| ↑↓←→ | 方向键/光标移动 |
| Home / End | 光标到行首/行尾 |
| Delete | 删除键 |

### 编辑快捷键
| PC 键盘 | 手机动作 |
|---------|---------|
| Ctrl+A | 全选 |
| Ctrl+C | 复制 |
| Ctrl+X | 剪切 |
| Ctrl+V | 粘贴（自动发送剪贴板文本） |
| Ctrl+Z | 撤销 |

### 系统快捷键 🆕
| PC 键盘 | 手机动作 |
|---------|---------|
| 音量+键 | 手机音量增大 |
| 音量-键 | 手机音量减小 |
| 音量静音键 | 手机音量减小 |

### 导航快捷键
| PC 键盘 | 手机动作 |
|---------|---------|
| 右键单击画面 | 返回键 |
| Ctrl+Shift+Esc | 最近任务 |

---

## 输入控制

### 触控操作
- **点击**：在画面上单击 → 手机对应位置点击
- **滑动**：在画面上拖动 → 手机对应方向滑动
- **右键**：右键单击 → 返回键

### 文本输入
1. 点击手机上的输入框（获取焦点）
2. 直接在 PC 键盘上打字
3. 支持中文（通过 Ctrl+V 粘贴）

---

## API 端点参考

所有 API 通过 HTTP POST 调用，端口 **8084**（独立 Input 端口）或 **8081**（MJPEG 共享端口）。

### 状态查询
```
GET /status
→ {"connected":true, "inputEnabled":true, "scaling":1, "screenOffMode":false}
```

### 触控
```
POST /tap         {"x":0.5, "y":0.5}        # 归一化坐标点击
POST /swipe       {"nx1":0.5, "ny1":0.8, "nx2":0.5, "ny2":0.2, "duration":300}
```

### 导航
```
POST /home        # 主页
POST /back        # 返回
POST /recents     # 最近任务
POST /notifications  # 通知栏
```

### 系统控制
```
POST /volume/up      # 音量增大
POST /volume/down    # 音量减小
POST /lock           # 锁屏（API 28+）
POST /quicksettings  # 快捷设置面板
```

### 远程协助 🆕
```
POST /wake           # 唤醒屏幕（息屏状态下点亮）
POST /screenshot     # 截屏（API 28+）
POST /power          # 电源对话框（关机/重启）
POST /splitscreen    # 分屏模式切换
```

### 亮度控制 🆕
```
GET  /brightness           # 获取当前亮度 → {"brightness":92}
POST /brightness/{level}   # 设置亮度 0-255（需 WRITE_SETTINGS 权限）
```

### 增强手势 🆕
```
POST /longpress    {"nx":0.5, "ny":0.5}                    # 长按（归一化坐标）
POST /longpress    {"nx":0.5, "ny":0.5, "duration":2000}   # 自定义时长长按
POST /doubletap    {"nx":0.5, "ny":0.5}                    # 双击
POST /scroll       {"direction":"down", "distance":500}    # 向下滚动
POST /scroll       {"direction":"up", "nx":0.5, "ny":0.3}  # 指定位置向上滚动
POST /pinch        {"cx":0.5, "cy":0.5, "zoomIn":true}     # 放大（捏合缩放）
POST /pinch        {"cx":0.5, "cy":0.5, "zoomIn":false}    # 缩小
```

### 应用管理 🆕
```
POST /openapp      {"packageName":"com.android.settings"}  # 打开指定应用
POST /openurl      {"url":"https://google.com"}            # 打开网址
GET  /apps         # 获取已安装应用列表 → [{"packageName":"","appName":""}...]
GET  /deviceinfo   # 获取设备信息（电量/网络/存储/型号/音量等）
GET  /clipboard    # 获取剪贴板内容
```

### 输入
```
POST /key    {"keysym":65288, "down":true, "shift":false, "ctrl":false}
POST /text   {"text":"hello"}
```

### 配置
```
POST /scaling/{factor}     # 设置输入缩放（如 /scaling/2）
POST /enable/{enabled}     # 开启/关闭输入（如 /enable/true）
```

---

## 端口说明

| 端口 | 服务 | 何时监听 |
|------|------|---------|
| 8080 | Gateway 统一入口 | 应用启动后 |
| 8081 | MJPEG 投屏 + 输入路由 | 用户点击"开始投屏"后 |
| 8084 | Input 独立服务 | 应用启动后 |

> 💡 如果从 PC 直接访问手机 IP 不通，可能是防火墙拦截。使用 USB 连接 + `adb forward tcp:8084 tcp:8084` 通过 USB 转发端口。

---

## 版本历史

### v32（当前版本）— AI Brain
- ✅ **WebSocket 实时触控**：/ws/touch 端点，延迟从 ~100ms 降到 ~10ms
- ✅ **View 树分析**：/viewtree 获取完整界面层级结构
- ✅ **窗口信息**：/windowinfo 获取当前活动窗口详情
- ✅ **语义化点击**：/findclick 按文本或ID查找并点击元素
- ✅ **智能关闭弹窗**：/dismiss 自动识别并关闭对话框
- ✅ **节点搜索**：/findnodes 按文本搜索界面元素
- ✅ **语义化设置文本**：/settext 按搜索条件定位输入框并填入文本
- ✅ **手机端沉浸模式**：自动检测手机浏览器→全屏+浮动☰按钮

### v31
- ✅ **远程协助模式**：唤醒屏幕/截屏/电源菜单/设备信息面板
- ✅ **系统动作**：唤醒屏幕、截屏、电源对话框、分屏切换
- ✅ **亮度控制**：远程调节屏幕亮度 0-255
- ✅ **增强手势**：长按、双击、上下左右滚动、捏合缩放
- ✅ **应用管理**：打开指定 APP、打开 URL、应用列表
- ✅ **设备信息**：电量/网络/存储/型号/音量/亮度/分辨率
- ✅ **剪贴板**：远程读取手机剪贴板内容
- ✅ 导航栏升级为 4 模式切换（导航 → 控制 → 系统 → 远程协助）

### v30
- ✅ 音量控制（+/-）+ PC 键盘音量键映射
- ✅ 锁屏功能、快捷设置、通知栏
- ✅ 第3导航模式（系统控制）

### v29
- 截图功能
- VR 16:9 裁剪模式
- H264/H265 WebSocket 投屏
- 导航栏 2 模式切换

---

## 常见问题

### 输入无响应
1. 检查手机上 AccessibilityService 是否已授权给 ScreenStream
2. 检查 `/status` API 返回的 `connected` 是否为 `true`
3. 检查 `inputEnabled` 是否为 `true`

### 连接不上
1. 确认手机和 PC 在同一局域网
2. 尝试 `adb forward` 通过 USB 转发端口
3. 检查手机防火墙设置

### 音量控制不工作
- 需要 AccessibilityService 已连接（`/status` 返回 `connected:true`）
- 控制的是**媒体音量**（不是铃声音量）

### 锁屏不工作
- 需要 Android 9（API 28）及以上版本
- 需要 AccessibilityService 已连接

### 唤醒屏幕不工作
- WAKE_LOCK 权限已自动包含，无需手动授权
- 若手机设置了强制息屏策略，可能被拦截

### 亮度控制不工作
- 需要在手机设置中授权「修改系统设置」（WRITE_SETTINGS）
- 路径：设置 → 应用 → ScreenStream → 修改系统设置

### 设备信息显示不全
- 部分信息需要特定权限，缺少权限时对应字段会返回 -1 或缺失
