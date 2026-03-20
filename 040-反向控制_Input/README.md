# 反向控制模块 (Input) — v33 Quest 3 Supreme

## 核心文件
- `输入路由/InputRoutes.kt` — **120+ API 端点**（输入+AI Brain+宏+文件+智能家居+Shell+VR+CDP+系统）
- `输入服务/InputService.kt` — AccessibilityService，执行所有输入/系统/AI 操作
- `HTTP服务器/InputHttpServer.kt` — 兼容端口（8084），由 autoStartHttp 控制
- `宏系统/MacroEngine.kt` — 宏定义存储+执行引擎+触发器(通知/APP切换/定时)

## 路由分层
- **基础**：/tap /swipe /key /text /pointer /home /back /recents /status /notifications
- **v30 系统**：/volume/up /volume/down /lock /quicksettings
- **v31 远程**：/wake /screenshot /power /splitscreen /brightness /longpress /doubletap /scroll /pinch /openapp /openurl /deviceinfo /apps /clipboard
- **v32 AI Brain**：/viewtree /windowinfo /findclick /dismiss /findnodes /settext /screen/text /ws/touch
- **v32 宏系统**：/macro/list /create /run/{id} /run-inline /stop/{id} /update/{id} /delete/{id} /running /log/{id} /triggers /trigger/{id}
- **v32 文件**：/files/storage /list /info /read /download /search /mkdir /delete /rename /move /copy /upload
- **v32 智能家居**：/smarthome/status /devices /control /control/direct /scenes /quick/{action}
- **v32 平台**：/command /command/stream /intent /wait /notifications/read
- **v32 投屏**：/stream/status /stream/start /stream/stop /agent/status /settings
- **v33 Shell**：/shell /system/info /system/processes /system/properties — **替代ADB**
- **v33 VR**：/vr/status /vr/services /vr/display /vr/controllers — **Quest 3专属**
- **v33 包管理**：/packages /packages/{pkg}
- **v33 CDP**：/cdp/pages /cdp/eval — **无需ADB forward**
- **v33 元信息**：/digest /capabilities /health /a11y/status /a11y/enable

## 键盘事件流
```
PC浏览器 keydown → sendInputJson("/key", {keysym, down, shift, ctrl})
  → InputRoutes /key → InputService.onKeyEvent(down, keysym, shift, ctrl)
    → 根据 keysym 执行: deleteBackward/moveCursor/selectAll/copy/paste/...
```

## 关键约束
- AccessibilityNodeInfo 用完必须 recycle()
- hint text 检测：API 26+ 用 isShowingHintText，低版本用光标位置判断
- 选择感知：Backspace/Delete 必须先检查是否有选中文本
- 修饰键：shift（扩展选择）、ctrl（词级移动）必须从前端传递
- WebSocket /ws/touch：实时触控流，延迟 ~10ms（替代 HTTP 轮询的 ~100ms）

## 修改此模块时
- 前端 `index.html` 的键盘/触控事件处理必须同步修改
- InputRoutes 的参数解析必须与前端发送的 JSON 结构匹配
- 新增路由 → 同步更新 `05-文档_docs/FEATURES.md`

## 对话结束选项

> 任务完成后调用 `ask_user_question`，从下表选 4 个最贴合的：

| label | description |
|-------|-------------|
| 装手机试试 | 编译安装到手机，打开浏览器体验操控效果 |
| 打磨操控手感 | 继续优化触控/键盘/手势的响应流畅度 |
| 同步前端体验 | 确保浏览器端面板与后端变更一致 |
| 试试宏功能 | 测试宏的创建/运行/循环是否顺畅 |
| 同步操控库 | phone_lib.py 跟进新API封装 |
| 收工提交 | 记录成果 + git commit |
