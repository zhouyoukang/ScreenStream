# ScreenStream_v2 功能管理（FEATURES）

> 目的：把“功能点→入口→配置→验收”建立映射，避免功能散落导致不可维护。

## 0) 功能登记表

| 功能 | 用户可见入口 | 代码入口 | 配置 | 验收方法 | 端口 |
|---|---|---|---|---|---|
| MJPEG 投屏 | Web UI 画面 | `HttpServer.kt` → `/stream/mjpeg` | `MjpegSettings` | 浏览器打开投屏地址 | 8081 |
| H264 投屏 | Web UI 画面 | `HttpServer.kt` → `/stream/h264` (WebSocket) | `MjpegSettings.streamCodec` | 浏览器自动切换编码 | 8081 |
| H265 投屏 | Web UI 画面 | `HttpServer.kt` → `/stream/h265` (WebSocket) | `MjpegSettings.streamCodec` | 浏览器自动切换编码 | 8081 |
| 触控输入（tap） | Web UI 点击 | `InputRoutes.kt` → `/tap` → `InputService` | `InputSettings` | `curl POST /tap` | 8081/8084 |
| 滑动输入（swipe） | Web UI 滑动 | `InputRoutes.kt` → `/swipe` → `InputService` | `InputSettings` | `curl POST /swipe` | 8081/8084 |
| 键盘输入（key） | Web UI 键盘 | `InputRoutes.kt` → `/key` → `InputService.onKeyEvent` | `InputSettings` | `curl POST /key` | 8081/8084 |
| 文本输入（text） | Web UI 输入 | `InputRoutes.kt` → `/text` → `InputService` | `InputSettings` | `curl POST /text` | 8081/8084 |
| 导航按钮（home/back/recents） | Web UI 导航栏 | `InputRoutes.kt` → `/home` `/back` `/recents` | — | `curl POST /back` | 8081/8084 |
| 通知栏 | Web UI 导航栏 | `InputRoutes.kt` → `/notifications` | — | `curl POST /notifications` | 8081/8084 |
| 输入缩放 | Web UI 设置 | `InputRoutes.kt` → `/scaling/{factor}` | `InputSettings.scaling` | `curl POST /scaling/2` | 8081/8084 |
| 输入开关 | Web UI 设置 | `InputRoutes.kt` → `/enable/{enabled}` | `InputSettings.inputEnabled` | `curl POST /enable/true` | 8081/8084 |
| 鼠标指针同步 | Web UI | `InputRoutes.kt` → `/pointer` (WebSocket) | `InputSettings` | WebSocket 连接 | 8081/8084 |
| PIN 码认证 | Web UI 弹窗 | `HttpServer.kt` → `/socket` WebSocket | `MjpegSettings.enablePin` | 输入 PIN 后获取流地址 | 8081 |
| 状态查询 | API | `InputRoutes.kt` → `/status` | — | `curl GET /status` | 8084 |
| 音量控制（+/-） | Web UI 系统模式 / 键盘音量键 | `InputRoutes.kt` → `/volume/up` `/volume/down` → `InputService.volumeUp/Down` | — | `curl POST /volume/up` | 8081/8084 |
| 锁屏 | Web UI 系统模式 | `InputRoutes.kt` → `/lock` → `InputService.lockScreen` | — | `curl POST /lock` | 8081/8084 |
| 快捷设置 | Web UI | `InputRoutes.kt` → `/quicksettings` → `InputService.showQuickSettings` | — | `curl POST /quicksettings` | 8081/8084 |
| 唤醒屏幕 | Web UI 远程协助模式 | `InputRoutes.kt` → `/wake` → `InputService.wakeScreen` | WAKE_LOCK | `curl POST /wake` | 8081/8084 |
| 截屏 | Web UI 远程协助模式 | `InputRoutes.kt` → `/screenshot` → `InputService.takeScreenshot` | — | `curl POST /screenshot` | 8081/8084 |
| 电源对话框 | Web UI 远程协助模式 | `InputRoutes.kt` → `/power` → `InputService.showPowerDialog` | — | `curl POST /power` | 8081/8084 |
| 分屏切换 | API | `InputRoutes.kt` → `/splitscreen` → `InputService.toggleSplitScreen` | — | `curl POST /splitscreen` | 8081/8084 |
| 亮度控制 | API | `InputRoutes.kt` → `/brightness/{level}` → `InputService.setBrightness` | WRITE_SETTINGS | `curl POST /brightness/128` | 8081/8084 |
| 长按 | API | `InputRoutes.kt` → `/longpress` → `InputService.longPressNormalized` | — | `curl POST /longpress` | 8081/8084 |
| 双击 | API | `InputRoutes.kt` → `/doubletap` → `InputService.doubleTapNormalized` | — | `curl POST /doubletap` | 8081/8084 |
| 滚动 | API | `InputRoutes.kt` → `/scroll` → `InputService.scrollNormalized` | — | `curl POST /scroll` | 8081/8084 |
| 捏合缩放 | API | `InputRoutes.kt` → `/pinch` → `InputService.pinchZoom` | — | `curl POST /pinch` | 8081/8084 |
| 打开应用 | API | `InputRoutes.kt` → `/openapp` → `InputService.openApp` | — | `curl POST /openapp` | 8081/8084 |
| 打开URL | API | `InputRoutes.kt` → `/openurl` → `InputService.openUrl` | — | `curl POST /openurl` | 8081/8084 |
| 设备信息 | Web UI 远程协助模式 | `InputRoutes.kt` → `/deviceinfo` → `InputService.getDeviceInfo` | — | `curl GET /deviceinfo` | 8081/8084 |
| 应用列表 | API | `InputRoutes.kt` → `/apps` → `InputService.getInstalledApps` | — | `curl GET /apps` | 8081/8084 |
| 剪贴板 | API | `InputRoutes.kt` → `/clipboard` → `InputService.getClipboardText` | — | `curl GET /clipboard` | 8081/8084 |
| 音频流 | Web UI | `HttpServer.kt` → `/stream/audio` (WebSocket) | `MjpegSettings` | 浏览器播放音频 | 8081 |
| Gateway 统一入口 | 浏览器地址栏 | `GatewayHttpServer` | `GatewaySettings` | 浏览器访问 :8080 | 8080 |
| WebSocket 实时触控流 | Web UI 触控 | `InputRoutes.kt` → `/ws/touch` → `InputService.onTouchStream*` | — | WebSocket 连接测试 | 8081/8084 |
| View 树分析 | AI/API | `InputRoutes.kt` → `/viewtree` → `InputService.getViewTree` | — | `curl GET /viewtree` | 8081/8084 |
| 当前窗口信息 | AI/API | `InputRoutes.kt` → `/windowinfo` → `InputService.getActiveWindowInfo` | — | `curl GET /windowinfo` | 8081/8084 |
| 语义化点击 | AI/API | `InputRoutes.kt` → `/findclick` → `InputService.findAndClickByText/Id` | — | `curl POST /findclick` | 8081/8084 |
| 智能关闭弹窗 | AI/API | `InputRoutes.kt` → `/dismiss` → `InputService.dismissTopDialog` | — | `curl POST /dismiss` | 8081/8084 |
| 节点搜索 | AI/API | `InputRoutes.kt` → `/findnodes` → `InputService.findNodesByText` | — | `curl POST /findnodes` | 8081/8084 |
| 语义化设置文本 | AI/API | `InputRoutes.kt` → `/settext` → `InputService.setNodeText` | — | `curl POST /settext` | 8081/8084 |
| 手机端全屏沉浸模式 | 手机浏览器 | `index.html` mobile-mode CSS + JS | — | 手机浏览器打开自动激活 | 8081 |
| 触控视觉反馈 | Web UI | `index.html` ripple + dot + trail CSS/JS | — | 触控时出现波纹和轨迹 | 8081 |
| 宏列表 | API | `InputRoutes.kt` → `/macro/list` → `MacroEngine` | — | `curl GET /macro/list` | 8081/8084 |
| 宏创建 | API | `InputRoutes.kt` → `/macro/create` → `MacroEngine` | — | `curl POST /macro/create` | 8081/8084 |
| 宏执行 | API | `InputRoutes.kt` → `/macro/run/{id}` → `MacroEngine` | — | `curl POST /macro/run/xxx` | 8081/8084 |
| 宏内联执行 | API | `InputRoutes.kt` → `/macro/run-inline` → `MacroEngine` | — | `curl POST /macro/run-inline` | 8081/8084 |
| 宏停止 | API | `InputRoutes.kt` → `/macro/stop/{id}` → `MacroEngine` | — | `curl POST /macro/stop/xxx` | 8081/8084 |
| 宏详情 | API | `InputRoutes.kt` → `/macro/{id}` → `MacroEngine` | — | `curl GET /macro/xxx` | 8081/8084 |
| 宏更新 | API | `InputRoutes.kt` → `/macro/update/{id}` → `MacroEngine` | — | `curl POST /macro/update/xxx` | 8081/8084 |
| 宏删除 | API | `InputRoutes.kt` → `/macro/delete/{id}` → `MacroEngine` | — | `curl POST /macro/delete/xxx` | 8081/8084 |
| 宏运行状态 | API | `InputRoutes.kt` → `/macro/running` → `MacroEngine` | — | `curl GET /macro/running` | 8081/8084 |
| 宏执行日志 | API | `InputRoutes.kt` → `/macro/log/{id}` → `MacroEngine` | — | `curl GET /macro/log/xxx` | 8081/8084 |
| 分类命令菜单 | Web UI 底部栏 | `index.html` toggleCommandMenu() | — | 点击☰按钮或Alt+M | 8081 |
| scrcpy兼容快捷键 | Web UI 键盘 | `index.html` keydown handler | — | Alt+H/B/S/F/↑↓/N/P/O/C/M | 8081 |
| 中键=HOME | Web UI 鼠标 | `index.html` mousedown button===1 | — | 中键点击投屏画面 | 8081 |
| 状态提示覆层 | Web UI | `index.html` showStatus() | — | 快捷键/操作反馈显示 | 8081 |
| 前端剪贴板查看 | Web UI 命令菜单 | `index.html` showClipboard() → `/clipboard` | — | 菜单→远程工具→剪贴板 | 8081 |
| 前端应用列表+启动 | Web UI 命令菜单 | `index.html` showAppList() → `/apps` + `/openapp` | — | 菜单→远程工具→应用 | 8081 |
| 前端亮度控制 | Web UI 命令菜单 | `index.html` setBrightness() → `/brightness/{level}` | WRITE_SETTINGS | 菜单→远程工具→亮度 | 8081 |
| 前端AI语义点击 | Web UI 命令菜单 | `index.html` aiFindClick() → `/findclick` | — | 菜单→AI工具→语义点击 | 8081 |
| 前端View树查看 | Web UI 命令菜单 | `index.html` showViewTree() → `/viewtree` | — | 菜单→AI工具→View树 | 8081 |
| 前端关弹窗 | Web UI 命令菜单 | `index.html` aiDismiss() → `/dismiss` | — | 菜单→AI工具→关弹窗 | 8081 |
| 前端分屏 | Web UI 命令菜单 | `index.html` → `/splitscreen` | — | 菜单→远程工具→分屏 | 8081 |
| 多点触控-捏合缩放 | 手机浏览器双指 | `index.html` pinch gesture → `/pinch` | — | 手机双指捏合/展开 | 8081 |
| 多点触控-双指滚动 | 手机浏览器双指 | `index.html` two-finger scroll → `/scroll` | — | 手机双指上下滑动 | 8081 |
| 多点触控-长按 | 手机浏览器长按 | `index.html` long press → `/longpress` | — | 手机长按500ms触发 | 8081 |
| 多点触控-双击 | 手机浏览器双击 | `index.html` double tap → `/doubletap` | — | 手机快速双击300ms内 | 8081 |
| 移动端安全视口 | 手机浏览器 | `index.html` viewport-fit=cover + safe-area | — | 刘海屏自动适配 | 8081 |
| 移动端防误触 | 手机浏览器 | `index.html` overscroll-behavior:none | — | 禁止浏览器手势干扰 | 8081 |
| 移动端自动全屏 | 手机浏览器 | `index.html` auto-fullscreen on first touch | — | 首次触控自动全屏 | 8081 |
| 开机自启动 | 设置页 | `BootReceiver.kt` + SharedPreferences | RECEIVE_BOOT_COMPLETED | 重启设备自动启动 | — |
| 无障碍引导弹窗 | 首次启动 | `ScreenStreamContent.kt` AlertDialog | — | 未开启时自动弹出引导 | — |
| Ctrl+拖拽捏合缩放 | Web UI 鼠标 | `index.html` Ctrl+mousedown pinchSim | — | Ctrl+点击拖拽=scrcpy风格缩放 | 8081 |
| 快捷键帮助面板 | Web UI | `index.html` toggleShortcutHelp() | — | F1或?键打开快捷键一览 | 8081 |
| FPS/延迟统计 | Web UI 覆层 | `index.html` perfOverlay + fetch latency | — | Alt+I切换显示 | 8081 |
| Gamepad手柄支持 | Web UI | `index.html` Gamepad API pollGamepad() | — | 手柄自动检测A/B/X/Y/摇杆映射 | 8081 |
| PiP画中画模式 | Web UI | `index.html` togglePiP() | — | Alt+Shift+P进入画中画 | 8081 |
| 截屏到剪贴板 | Web UI | `index.html` captureScreenshot() | — | Alt+K截屏复制/下载 | 8081 |
| 显示旋转 | Web UI CSS | `index.html` rotateDisplay() | — | Alt+←/→旋转90° | 8081 |
| 1:1像素模式 | Web UI | `index.html` togglePixelPerfect() | — | Alt+G切换原始像素显示 | 8081 |
| Ctrl+↑↓音量 | Web UI 键盘 | `index.html` Ctrl+Arrow handler | — | scrcpy兼容音量快捷键 | 8081 |
| 保持唤醒API | API | `InputRoutes.kt` → `/stayawake` → WakeLock | WAKE_LOCK | `POST /stayawake/true` | 8081/8084 |
| 显示触控点API | API | `InputRoutes.kt` → `/showtouches` → Settings | WRITE_SETTINGS | `POST /showtouches/true` | 8081/8084 |
| 屏幕旋转API | API | `InputRoutes.kt` → `/rotate/{degrees}` | WRITE_SETTINGS | `POST /rotate/90` | 8081/8084 |
| 增强设备信息 | API | `InputService.kt` getDeviceInfo() | — | WiFi/运行时间/stayAwake状态 | 8081/8084 |
| 媒体控制API | API | `InputRoutes.kt` → `/media/{action}` | — | play/pause/next/prev/stop/rewind/forward | 8081/8084 |
| 找手机API | API | `InputRoutes.kt` → `/findphone/{true\|false}` | — | 最大音量响铃30秒自动停止 | 8081/8084 |
| 振动设备API | API | `InputRoutes.kt` → `/vibrate` | VIBRATE | `POST /vibrate {duration:500}` | 8081/8084 |
| 手电筒API | API | `InputRoutes.kt` → `/flashlight/{true\|false}` | CAMERA | 闪光灯开关 | 8081/8084 |
| 免打扰API | API | `InputRoutes.kt` → `/dnd/{true\|false}` | NOTIFICATION_POLICY | DND模式切换 | 8081/8084 |
| 音量级别API | API | `InputRoutes.kt` → `/volume` | — | `POST {stream:"music",level:8}` 精确音量 | 8081/8084 |
| 自动旋转API | API | `InputRoutes.kt` → `/autorotate/{true\|false}` | WRITE_SETTINGS | 陀螺仪自动旋转开关 | 8081/8084 |
| 前台应用API | API | `InputRoutes.kt` → `/foreground` | — | 获取当前前台应用包名 | 8081/8084 |
| 关闭应用API | API | `InputRoutes.kt` → `/killapp` | — | back+back+home退出前台应用 | 8081/8084 |
| 文件上传API | API | `InputRoutes.kt` → `/upload` | STORAGE | Base64文件上传到Downloads | 8081/8084 |
| 会话录制 | Web UI | `index.html` toggleRecording() MediaRecorder | — | 菜单→录屏 WebM格式下载 | 8081 |
| 白板标注 | Web UI | `index.html` toggleAnnotation() Canvas | — | 菜单→标注 鼠标/触控绘画+双击清除 | 8081 |
| 拖放文件上传 | Web UI | `index.html` drag&drop → /upload | — | 拖拽文件到投屏区域直接上传 | 8081 |
| QR码连接 | Web UI | `index.html` showQrCode() | — | 菜单→QR码 扫码连接 | 8081 |
| 游戏模式 | Web UI | `index.html` toggleGameMode() | — | 隐藏所有UI覆层最大化画面 | 8081 |
| 主题切换 | Web UI | `index.html` toggleTheme() | — | 菜单→主题 深色/浅色切换 | 8081 |
| 会话计时器 | Web UI | `index.html` sessionTimer | — | 命令菜单实时显示连接时长 | 8081 |
| 电池小组件 | Web UI | `index.html` batteryWidget | — | 右上角实时电量+充电状态 | 8081 |
| 连接历史 | Web UI | `index.html` localStorage | — | 自动记录最近20次连接 | 8081 |
| 媒体控制面板 | Web UI 命令菜单 | `index.html` → /media/* | — | 播放/暂停/上一首/下一首 | 8081 |
| 找手机按钮 | Web UI 命令菜单 | `index.html` → /findphone | — | 一键响铃找手机 | 8081 |
| 手电筒按钮 | Web UI 命令菜单 | `index.html` → /flashlight | — | 一键手电筒开关 | 8081 |
| 免打扰按钮 | Web UI 命令菜单 | `index.html` → /dnd | — | 一键免打扰切换 | 8081 |
| 自动旋转按钮 | Web UI 命令菜单 | `index.html` → /autorotate | — | 一键自动旋转切换 | 8081 |
| 振动按钮 | Web UI 命令菜单 | `index.html` → /vibrate | — | 一键振动设备 | 8081 |
| 关闭应用按钮 | Web UI 命令菜单 | `index.html` → /killapp | — | 一键关闭前台应用 | 8081 |
| 画面镜像 | Web UI 画面工具 | `index.html` toggleMirror() | — | 水平翻转投屏画面 | 8081 |
| 画面滤镜(灰度/反色) | Web UI 画面工具 | `index.html` cycleFilter() | — | CSS滤镜切换 | 8081 |
| 画面缩放 | Web UI 画面工具 | `index.html` zoomStream() | — | 50%-300%缩放 | 8081 |
| 画面重置 | Web UI 画面工具 | `index.html` resetStreamView() | — | 重置所有画面变换 | 8081 |
| 快速文本片段 | Web UI 效率工具 | `index.html` showTextSnippets() | — | 预定义文本一键发送+自定义 | 8081 |
| 连接信息面板 | Web UI 效率工具 | `index.html` showConnectionInfo() | — | URL/协议/端口/UA/时长 | 8081 |
| 流量统计覆层 | Web UI 效率工具 | `index.html` toggleTrafficStats() | — | 实时流量MB/速率KB/s | 8081 |
| 宏导出 | Web UI 宏面板 | `index.html` exportAllMacros() | — | 导出全部宏为JSON文件 | 8081 |
| 宏导入 | Web UI 宏面板 | `index.html` handleMacroImport() | — | 从JSON文件导入宏 | 8081 |
| 截屏含标注 | Web UI 截屏增强 | `index.html` captureWithAnnotations() | — | 截屏包含Canvas标注层 | 8081 |
| 截屏时间水印 | Web UI 截屏增强 | `index.html` localStorage ss_screenshot_timestamp | — | 可选时间戳水印 | 8081 |
| 截屏计数器 | Web UI 截屏增强 | `index.html` screenshotCount | — | 显示截屏序号 | 8081 |
| 截屏ISO文件名 | Web UI 截屏增强 | `index.html` downloadBlob() | — | 文件名含ISO时间戳 | 8081 |
| **S33 远程文件管理器** | **完整模块** | **InputService + InputRoutes + index.html** | **12 API + 全屏面板** | **浏览/上传/下载/删除/重命名/移动/复制/搜索/预览** | **8081** |
| 文件列表 | S33 后端 | `InputService.kt` listFiles() | GET /files/list | 目录浏览+排序+隐藏文件+存储统计 | 8081 |
| 文件信息 | S33 后端 | `InputService.kt` getFileInfo() | GET /files/info | 文件详情+子项统计 | 8081 |
| 文件下载 | S33 后端 | `InputService.kt` readFileBase64() | GET /files/download | Base64编码下载(≤10MB) | 8081 |
| 文本预览 | S33 后端 | `InputService.kt` readTextFile() | GET /files/read | UTF-8文本读取(≤512KB) | 8081 |
| 文件搜索 | S33 后端 | `InputService.kt` searchFiles() | GET /files/search | 递归搜索(深度8/100结果) | 8081 |
| 存储信息 | S33 后端 | `InputService.kt` getStorageInfo() | GET /files/storage | 总量/可用/常用目录 | 8081 |
| 创建目录 | S33 后端 | `InputService.kt` createDirectory() | POST /files/mkdir | 递归创建 | 8081 |
| 删除文件 | S33 后端 | `InputService.kt` deleteFile() | POST /files/delete | 文件+目录递归删除 | 8081 |
| 重命名 | S33 后端 | `InputService.kt` renameFile() | POST /files/rename | 安全重命名 | 8081 |
| 移动文件 | S33 后端 | `InputService.kt` moveFile() | POST /files/move | 跨目录移动 | 8081 |
| 复制文件 | S33 后端 | `InputService.kt` copyFile() | POST /files/copy | 文件+目录递归复制 | 8081 |
| 文件上传 | S33 后端 | `InputRoutes.kt` /files/upload | POST /files/upload | Base64指定路径上传 | 8081 |
| 文件管理面板 | S33 前端 | `index.html` toggleFileManager() | Alt+E | 全屏浏览器+工具栏+面包屑 | 8081 |
| 快速访问 | S33 前端 | `index.html` fmRenderQuickAccess() | — | DCIM/Download等常用目录按钮 | 8081 |
| 文件预览 | S33 前端 | `index.html` fmPreviewFile() | — | 图片Base64预览+文本语法预览 | 8081 |
| 剪切/复制/粘贴 | S33 前端 | `index.html` fmCopy/fmCut/fmPaste | — | 文件剪贴板操作 | 8081 |
| 批量上传 | S33 前端 | `index.html` fmHandleUpload() | — | 多文件选择+进度显示 | 8081 |
| 网格/列表视图 | S33 前端 | `index.html` fmToggleView() | — | 列表↔网格切换，参考FileBrowser | 8081 |
| 多选+批量删除 | S33 前端 | `index.html` fmBatchDelete() | Ctrl+Click | 多文件选择+批量删除操作 | 8081 |
| 右键上下文菜单 | S33 前端 | `index.html` fmShowContext() | 右键 | 打开/预览/下载/重命名/复制/剪切/删除 | 8081 |
| 拖拽上传 | S33 前端 | `index.html` fmDrop() | 拖拽文件到面板 | 拖拽文件直接上传到当前目录 | 8081 |
| 视频/音频预览 | S33 前端 | `index.html` fmPreviewFile() | 双击 | 内联播放mp4/webm/mp3/wav等 | 8081 |
| **通用Intent** | **Platform** | `InputService.kt` sendIntent() | POST /intent | 发送任意Intent：ACTION_VIEW/SEND/DIAL+extras+component | 8081 |
| **屏幕文本提取** | **Platform** | `InputService.kt` extractScreenText() | GET /screen/text | 提取当前屏幕所有可见文本+可点击元素+坐标 | 8081 |
| **等待条件** | **Platform** | `InputService.kt` waitForCondition() | GET /wait | 轮询view tree等待指定文本出现(超时+间隔可配) | 8081 |
| **通知读取** | **Platform** | `InputService.kt` getNotifications() | GET /notifications/read | 读取最近50条通知(title/body/package/time) | 8081 |
| **S34 APP启动器** | Platform前端 | `index.html` toggleAppLauncher() | Alt+1 | 应用网格+搜索+一键启动，调用/intent | 8081 |
| **S35 通知中心** | Platform前端 | `index.html` toggleNotifCenter() | Alt+2 | 实时通知流+5s自动刷新+按APP分组 | 8081 |
| **S36 屏幕阅读器** | Platform前端 | `index.html` toggleScreenReader() | Alt+3 | 提取屏幕文本+可点击元素列表+一键点击 | 8081 |
| **S37 快捷指令** | Platform前端 | `index.html` toggleQuickActions() | Alt+4 | 12个预设(拨号/相机/设置/微信等)+自定义+URL | 8081 |
| **S38 设备仪表盘** | Platform前端 | `index.html` toggleDevDashboard() | Alt+5 | 电池/存储/网络/屏幕/系统/当前APP卡片 | 8081 |
| **S39 工作流编排** | Platform前端 | `index.html` toggleWorkflowBuilder() | Alt+6 | 可视化步骤链：打开APP→等待→点击→读取 | 8081 |
| **S40 应用监控** | Platform前端 | `index.html` toggleAppMonitor() | Alt+7 | 3s轮询前台应用+切换历史记录 | 8081 |
| **S41 远程浏览器** | Platform前端 | `index.html` toggleRemoteBrowser() | Alt+8 | URL输入→手机打开→提取页面内容 | 8081 |
| **S42 剪贴板历史** | Platform前端 | `index.html` toggleClipHistory() | Alt+9 | localStorage持久化历史+一键复制到PC | 8081 |
| **S43 批量执行** | Platform前端 | `index.html` toggleBatchRunner() | Alt+0 | 预设批量操作+自定义JSON+执行日志 | 8081 |

## 1) 当前重点功能（按收敛优先级）

- **输入链路统一（入口/端口/鉴权）**
  - 状态：ADR 已落地（Phase-2 待代码收敛）
  - refs：`docs/adr/ADR-20260210-input-http-entrypoints.md`
- **主线合并（Quest/上游差异开关化）**
  - 状态：清单已落地，待逐条登记
  - refs：`docs/MERGE_ARCHIVE_CHECKLIST.md`
- **发布验收（减少漏项）**
  - refs：`skills/skill-ssv2-release-checklist/`

## 2) 护栏

- 功能增加/迁移必须同步更新：
  - `docs/MODULES.md`
  - `docs/FEATURES.md`
  - 必要时 `docs/adr/`
