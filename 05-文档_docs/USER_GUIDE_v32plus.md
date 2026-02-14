# ScreenStream v32+ 完整使用指南

> 本文档是一份自包含的综合指南，涵盖所有功能、使用方法、API 参考和一键命令。
> 更新日期：2026-02-13

---

## 一、快速开始（一键部署）

### 首次部署（编译+安装+启动）
```powershell
& "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\dev-deploy.ps1"
```

### 仅重新部署（跳过编译）
```powershell
& "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\dev-deploy.ps1" -SkipBuild
```

### 仅验证（跳过编译和安装）
```powershell
& "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\dev-deploy.ps1" -SkipBuild -SkipInstall
```

### 部署后需要做的一件事
> **解锁手机 → 打开 ScreenStream → 点击「开始」按钮**
> 这是 Android 系统要求：屏幕捕获需要用户确认一次（首次或重装后）。
> 之后所有 API 自动可用，无需再操作手机。

---

## 二、功能总览（v32+ · 59 个 API 端点 + 8 个前端工具 = 68 功能）

| 层级 | 功能 | 数量 | 版本 |
|------|------|------|------|
| 投屏 | MJPEG / H264 / H265 + 音频流 | 4 | v28+ |
| 基础控制 | 触控/滑动/键盘/导航/文本输入 | 10 | v28+ |
| 系统控制 | 音量/锁屏/通知栏/快捷设置 | 4 | v30 |
| 远程协助 | 唤醒/截屏/电源/亮度/长按/双击/滚动/捏合/打开APP/设备信息/剪贴板 | 14 | v31 |
| AI Brain | View树/语义点击/节点搜索/智能关弹窗/WebSocket触控 | 7 | v32 |
| 宏系统 | 宏CRUD/执行/内联/停止/日志 | 11 | v32+ |
| 前端增强 | 触控反馈/分类命令菜单/scrcpy快捷键/中键HOME | — | v32+ |

---

## 三、Web UI 使用指南

### 3.1 访问方式

**USB 连接（推荐）：**
```
http://127.0.0.1:8081/
```

**局域网：**
```
http://<手机IP>:8081/
```

### 3.2 底部导航栏（固定布局，无需切换模式）

| 按钮 | 功能 | 快捷键 |
|------|------|--------|
| ◀ | 返回 | Alt+B / 右键 / Esc |
| ● | 主页 | Alt+H / 中键 |
| ▢ | 最近任务 | Alt+S |
| ☰ | **命令菜单** | Alt+M |
| 📷 | 截图 | — |
| ⛶ | 全屏 | Alt+F |

### 3.2.1 命令菜单（分类面板）

点击 **☰ 菜单按钮** 或按 **Alt+M** 打开分类命令面板，所有功能按场景组织：

| 分类 | 包含功能 |
|------|----------|
| 📱 系统控制 | 音量±、锁屏、通知栏、快捷设置、电源 |
| 🖥️ 投屏设置 | 音频、画中画、VR 16:9 裁剪 |
| 🛠️ 远程工具 | 唤醒、截屏、剪贴板、应用列表、亮度、分屏、设备信息 |
| 🤖 AI 工具 | 语义点击、View树、关弹窗 |
| ⚡ 宏系统 | 宏管理、快速运行、停止全部 |
| ⌨️ 快捷键 | 内嵌快捷键速查卡 |

### 3.3 触控操作

| 操作 | 方式 | 视觉反馈 |
|------|------|----------|
| 点击 | 鼠标左键/触屏单击 | 蓝色波纹(ripple) + 触点(dot) |
| 拖拽/滑动 | 鼠标按住拖动/触屏滑动 | 跟随触点 + 轨迹(trail) |
| 右键 | 鼠标右键短按 | 发送返回键 |
| 右键+滚轮 | 鼠标右键按住+滚轮 | 精细水平滚动 |
| 摇杆 | Quest 手柄摇杆 | 方向滑动 |

### 3.4 键盘快捷键（scrcpy 兼容）

**文本输入**：在投屏画面上直接按键即可输入（字母/数字/符号/方向键/Backspace/Enter/Ctrl+A/C/V/X）

**系统快捷键（Alt = MOD）**：

| 快捷键 | 功能 | 快捷键 | 功能 |
|--------|------|--------|------|
| Alt+H | 主页 | Alt+B | 返回 |
| Alt+S | 最近任务 | Alt+F | 全屏 |
| Alt+↑ | 音量+ | Alt+↓ | 音量- |
| Alt+N | 通知栏 | Alt+NN(长按) | 快捷设置 |
| Alt+P | 电源 | Alt+O | 息屏 |
| Alt+Shift+O | 亮屏 | Alt+C | 查看剪贴板 |
| Alt+M | 命令菜单 | Esc | 返回 |
| 右键 | 返回 | 中键 | 主页 |

### 3.5 宏管理面板

打开**命令菜单(Alt+M)** → **⚡ 宏系统** → **宏管理**打开面板：

1. **查看宏列表**：显示所有已创建的宏，含步骤数和运行状态
2. **运行/停止宏**：每个宏旁有运行/停止按钮
3. **创建宏**：填写名称 + JSON 步骤数组 → 点击创建
4. **删除宏**：点击垃圾桶按钮

---

## 四、API 参考

> 所有 API 均可通过 `http://127.0.0.1:8081/` 或 `http://127.0.0.1:8084/` 访问。
> POST 请求体为 JSON，Content-Type: application/json。

### 4.1 基础控制

```bash
# 点击（归一化坐标 0~1）
curl -X POST http://127.0.0.1:8081/tap -d '{"nx":0.5,"ny":0.5}'

# 滑动
curl -X POST http://127.0.0.1:8081/swipe -d '{"nx1":0.5,"ny1":0.8,"nx2":0.5,"ny2":0.2,"duration":300}'

# 键盘事件
curl -X POST http://127.0.0.1:8081/key -d '{"keysym":65293,"down":true}'

# 文本输入
curl -X POST http://127.0.0.1:8081/text -d '{"text":"Hello World"}'

# 导航
curl -X POST http://127.0.0.1:8081/home
curl -X POST http://127.0.0.1:8081/back
curl -X POST http://127.0.0.1:8081/recents

# 状态查询
curl http://127.0.0.1:8081/status
```

### 4.2 系统控制（v30）

```bash
curl -X POST http://127.0.0.1:8081/volume/up
curl -X POST http://127.0.0.1:8081/volume/down
curl -X POST http://127.0.0.1:8081/lock
curl -X POST http://127.0.0.1:8081/quicksettings
curl -X POST http://127.0.0.1:8081/notifications
```

### 4.3 远程协助（v31）

```bash
curl -X POST http://127.0.0.1:8081/wake
curl -X POST http://127.0.0.1:8081/screenshot
curl -X POST http://127.0.0.1:8081/power
curl -X POST http://127.0.0.1:8081/brightness/128
curl -X POST http://127.0.0.1:8081/longpress -d '{"nx":0.5,"ny":0.5}'
curl -X POST http://127.0.0.1:8081/doubletap -d '{"nx":0.5,"ny":0.5}'
curl -X POST http://127.0.0.1:8081/scroll -d '{"nx":0.5,"ny":0.5,"dx":0,"dy":-300}'
curl -X POST http://127.0.0.1:8081/pinch -d '{"nx":0.5,"ny":0.5,"scale":2.0}'
curl -X POST http://127.0.0.1:8081/openapp -d '{"packageName":"com.android.settings"}'
curl -X POST http://127.0.0.1:8081/openurl -d '{"url":"https://www.baidu.com"}'
curl http://127.0.0.1:8081/deviceinfo
curl http://127.0.0.1:8081/apps
curl http://127.0.0.1:8081/clipboard
```

### 4.4 AI Brain（v32）

```bash
# 获取界面树（depth 控制深度）
curl "http://127.0.0.1:8081/viewtree?depth=8"

# 当前窗口信息
curl http://127.0.0.1:8081/windowinfo

# 按文本查找并点击
curl -X POST http://127.0.0.1:8081/findclick -d '{"text":"设置"}'

# 按ID查找并点击
curl -X POST http://127.0.0.1:8081/findclick -d '{"id":"com.example:id/btn_ok"}'

# 智能关闭弹窗
curl -X POST http://127.0.0.1:8081/dismiss

# 搜索节点
curl -X POST http://127.0.0.1:8081/findnodes -d '{"text":"确定"}'

# 设置节点文本
curl -X POST http://127.0.0.1:8081/settext -d '{"text":"搜索","value":"新内容"}'
```

### 4.5 宏系统（v32+）

```bash
# 列出所有宏
curl http://127.0.0.1:8081/macro/list

# 创建宏
curl -X POST http://127.0.0.1:8081/macro/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "打开设置并返回",
    "actions": [
      {"type": "api", "endpoint": "/openapp", "params": {"packageName": "com.android.settings"}},
      {"type": "wait", "ms": 2000},
      {"type": "api", "endpoint": "/back"}
    ]
  }'

# 运行宏（id 从 /macro/list 获取）
curl -X POST http://127.0.0.1:8081/macro/run/<macro-id>

# 内联执行（不保存，一次性运行）
curl -X POST http://127.0.0.1:8081/macro/run-inline \
  -H "Content-Type: application/json" \
  -d '{
    "actions": [
      {"type": "api", "endpoint": "/home"},
      {"type": "wait", "ms": 500},
      {"type": "api", "endpoint": "/recents"}
    ],
    "loop": 3
  }'

# 停止运行中的宏
curl -X POST http://127.0.0.1:8081/macro/stop/<macro-id>

# 查看运行中的宏
curl http://127.0.0.1:8081/macro/running

# 查看宏详情
curl http://127.0.0.1:8081/macro/<macro-id>

# 查看执行日志
curl http://127.0.0.1:8081/macro/log/<macro-id>

# 更新宏
curl -X POST http://127.0.0.1:8081/macro/update/<macro-id> \
  -H "Content-Type: application/json" \
  -d '{"name": "新名字", "actions": [...]}'

# 删除宏
curl -X POST http://127.0.0.1:8081/macro/delete/<macro-id>
```

#### 宏 JSON 格式说明

```json
{
  "name": "宏名称",
  "actions": [
    {"type": "api", "endpoint": "/tap", "params": {"nx": 0.5, "ny": 0.5}},
    {"type": "api", "endpoint": "/text", "params": {"text": "Hello"}},
    {"type": "api", "endpoint": "/home"},
    {"type": "wait", "ms": 1000}
  ],
  "loop": 1
}
```

- **`type: "api"`**：调用任意 API 端点，`params` 为 JSON 请求体
- **`type: "wait"`**：等待指定毫秒
- **`loop`**：循环次数（0 = 无限循环，直到手动停止）

---

## 五、开发工作流

### 5.1 完整开发 → 部署 → 测试闭环

```
编写代码 → 编译验证 → 推送安装 → 启动应用 → API 验证
    ↑                                              |
    └──────── 发现问题修复 ←─────────────────────────┘
```

**一键命令：**
```powershell
# 完整流程（编译+部署+验证）
& "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\dev-deploy.ps1"

# 仅编译验证（不推送）
$env:JAVA_HOME = "C:\Program Files\Processing\app\resources\jdk"
$env:ANDROID_SDK_ROOT = "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\android-sdk"
& "e:\github\AIOT\ScreenStream_v2\gradlew.bat" assembleFDroidDebug --no-configuration-cache

# 仅验证 API
$ports = @(8080, 8081, 8084); foreach ($p in $ports) { curl.exe -s "http://127.0.0.1:${p}/status" }
```

### 5.2 项目结构

```
ScreenStream_v2/
├── 010-用户界面与交互_UI/     ← :app 模块（APK 产物）
├── 020-投屏链路_Streaming/
│   ├── 010-MJPEG投屏_MJPEG/  ← :mjpeg（Web UI + HttpServer + 投屏）
│   │   └── assets/index.html  ← 前端页面（5模式导航+宏面板+触控反馈）
│   ├── 020-RTSP投屏_RTSP/     ← :rtsp
│   └── 030-WebRTC投屏_WebRTC/ ← :webrtc
├── 040-反向控制_Input/        ← :input
│   ├── 010-输入路由_Routes/InputRoutes.kt  ← 59 个 API 端点
│   ├── 020-输入服务_Service/InputService.kt ← AccessibilityService
│   ├── 030-HTTP服务器_HttpServer/           ← 兼容端口 8084
│   └── 040-宏系统_Macro/MacroEngine.kt     ← 宏引擎
├── 070-基础设施_Infrastructure/ ← :common
├── 090-构建与部署_Build/
│   ├── dev-deploy.ps1          ← 一键部署脚本
│   └── android-sdk/            ← SDK + ADB
└── 05-文档_docs/
    ├── STATUS.md               ← 项目状态面板
    ├── FEATURES.md             ← 功能登记表（59条）
    ├── MODULES.md              ← 模块索引
    └── USER_GUIDE_v32plus.md   ← 本文档
```

### 5.3 端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| Gateway | 8080 | 统一入口（转发到对应模块） |
| MJPEG Server | 8081 | 主入口（Web UI + 全部 API + 投屏） |
| RTSP Server | 8082 | RTSP 投屏 |
| WebRTC Server | 8083 | WebRTC 投屏 |
| InputHttpServer | 8084 | 兼容入口（仅 Input API） |

---

## 六、常见问题

### Q: 部署后 API 无响应？
**A:** 需要在手机上点击 ScreenStream 的「开始」按钮启动投屏。首次需要确认屏幕捕获权限。

### Q: 端口被占用？
**A:** 部署脚本会自动探测实际监听端口并转发。如果 8081 被占用，脚本会告诉你实际端口。

### Q: AccessibilityService 断开？
**A:** 部署脚本会自动通过 Root 重新启用。也可手动：
```powershell
$ADB = "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\android-sdk\platform-tools\adb.exe"
& $ADB shell "settings put secure enabled_accessibility_services info.dvkr.screenstream.dev/info.dvkr.screenstream.input.InputService"
& $ADB shell "settings put secure accessibility_enabled 1"
```

### Q: 宏执行失败？
**A:** 检查 `/macro/log/<id>` 查看执行日志，确认每个步骤的 endpoint 是否正确。

### Q: 手机锁屏后 API 还能用吗？
**A:** 投屏启动后，即使手机锁屏 API 仍然可用。但如果应用被系统杀死需要重新启动。

---

## 七、v32+ 新增功能详情

### 7.1 宏系统
- **后端**：`MacroEngine.kt` 单例，内存存储宏定义，支持 API 动作和等待步骤
- **前端**：导航栏第5模式（绿色），宏管理面板可创建/运行/停止/删除
- **特性**：循环执行、内联执行（不保存）、执行日志、并发运行

### 7.2 触控视觉反馈
- **Ripple 波纹**：触摸/点击时出现扩散波纹动画
- **Touch Dot**：触摸持续期间显示跟随光标的蓝色圆点
- **Trail 轨迹**：拖拽时留下淡出的轨迹点

### 7.3 RTSP 修复
- 修复了 `RtspModuleService.kt` 中的 copy-paste 命名 bug（`mjpegEvent` → `rtspEvent`）

---

## 八、实用宏示例

### 8.1 自动打开微信
```json
{
  "name": "打开微信",
  "actions": [
    {"type": "api", "endpoint": "/openapp", "params": {"packageName": "com.tencent.mm"}}
  ]
}
```

### 8.2 自动截屏并返回主页
```json
{
  "name": "截屏返回",
  "actions": [
    {"type": "api", "endpoint": "/screenshot"},
    {"type": "wait", "ms": 1000},
    {"type": "api", "endpoint": "/home"}
  ]
}
```

### 8.3 自动清理后台（循环）
```json
{
  "name": "清理后台",
  "actions": [
    {"type": "api", "endpoint": "/recents"},
    {"type": "wait", "ms": 800},
    {"type": "api", "endpoint": "/swipe", "params": {"nx1": 0.5, "ny1": 0.5, "nx2": 0.5, "ny2": 0.1, "duration": 200}},
    {"type": "wait", "ms": 500}
  ],
  "loop": 10
}
```

### 8.4 AI 自动关弹窗
```json
{
  "name": "智能关弹窗",
  "actions": [
    {"type": "api", "endpoint": "/dismiss"},
    {"type": "wait", "ms": 2000}
  ],
  "loop": 0
}
```

### 8.5 自动亮度调节+唤醒
```json
{
  "name": "唤醒亮屏",
  "actions": [
    {"type": "api", "endpoint": "/wake"},
    {"type": "wait", "ms": 500},
    {"type": "api", "endpoint": "/brightness/200"}
  ]
}
```
