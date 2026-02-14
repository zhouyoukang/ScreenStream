# 反向控制模块 (Input) — v32+

## 核心文件
- `010-输入路由_Routes/InputRoutes.kt` — 59 个 API 端点（基础+系统+远程协助+AI Brain+宏系统）
- `020-输入服务_Service/InputService.kt` — AccessibilityService，执行所有输入/系统/AI 操作
- `030-HTTP服务器_HttpServer/InputHttpServer.kt` — 兼容端口（8084），由 autoStartHttp 控制
- `040-宏系统_Macro/MacroEngine.kt` — 宏定义存储+执行引擎，直接调用 InputService 方法

## 路由分层
- **基础**：/tap /swipe /key /text /pointer /home /back /recents /status /notifications
- **v30 系统**：/volume/up /volume/down /lock /quicksettings
- **v31 远程**：/wake /screenshot /power /splitscreen /brightness /longpress /doubletap /scroll /pinch /openapp /openurl /deviceinfo /apps /clipboard
- **v32 AI Brain**：/viewtree /windowinfo /findclick /dismiss /findnodes /settext /ws/touch
- **v32+ 宏系统**：/macro/list /macro/create /macro/run/{id} /macro/run-inline /macro/stop/{id} /macro/{id} /macro/update/{id} /macro/delete/{id} /macro/running /macro/log/{id}

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
