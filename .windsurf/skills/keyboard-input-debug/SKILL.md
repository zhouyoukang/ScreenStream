---
name: keyboard-input-debug
description: 调试和修复PC键盘到Android手机的输入映射问题。当涉及键盘事件、keysym映射、AccessibilityService输入、选择/删除/光标移动等问题时触发。
---

## 诊断流程

### 1. 确认事件链路
```
PC keydown → index.html sendInputJson("/key", {keysym, down, shift, ctrl})
  → InputRoutes.kt 解析JSON → InputService.kt onKeyEvent()
    → 执行具体操作（deleteBackward/moveCursor/selectAll/...）
```

### 2. 前端检查 (index.html)
- 文件位置: `020-投屏链路_Streaming/010-MJPEG投屏_MJPEG/assets/index.html`
- 确认 keysym 值正确（参考 X11 keysym 标准）
- 确认 shift/ctrl 修饰键已附带
- 确认 Ctrl 组合键在 switch 中正确处理

### 3. 路由检查 (InputRoutes.kt)
- 文件位置: `040-反向控制_Input/010-输入路由_Routes/InputRoutes.kt`
- 确认 JSON 字段解析与前端发送一致
- 确认 shift/ctrl 参数传递给 onKeyEvent

### 4. 服务检查 (InputService.kt)
- 文件位置: `040-反向控制_Input/020-输入服务_Service/InputService.kt`
- onKeyEvent: 修饰键状态 + keysym 分发
- 文本操作: getRealText() 过滤 hint text
- 选择感知: getSelection() 获取光标/选区

## 常见 Keysym 映射
| 按键 | Keysym | 说明 |
|------|--------|------|
| Backspace | 0xFF08 | 选择感知删除 |
| Delete | 0xFFFF | 前向删除 |
| Enter | 0xFF0D | IME回车/插入换行 |
| Tab | 0xFF09 | 焦点切换 |
| Escape | 0xFF1B | 返回 |
| Home | 0xFF50 | 行首/全局Home |
| End | 0xFF57 | 行尾/全局End |
| Left/Right | 0xFF51/0xFF53 | 光标移动 |
| Up/Down | 0xFF52/0xFF54 | 行级移动 |
| Ctrl+A | 0xFF6A | 全选 (XK_Select) |
| Ctrl+C | 0xFF63 | 复制 |
| Ctrl+V | 0xFF6D | 粘贴 |
| Ctrl+X | 0xFF6B | 剪切 |
| Ctrl+Z | 0xFF65 | 撤销 |
