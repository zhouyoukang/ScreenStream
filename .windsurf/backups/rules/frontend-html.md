---
trigger: glob
globs: ["**/*.html", "**/*.js", "**/*.css"]
---

# 前端开发规则

## index.html (MJPEG 投屏页面)
- 键盘事件必须附带 shift/ctrl 修饰键状态
- keysym 映射遵循 X11/RFB 标准
- 滚轮/触摸事件使用归一化坐标 (0.0-1.0)
- VR 环境检测：`isVrEnv()` 判断是否 Quest 浏览器
- 隐藏输入框捕获中文输入法（compositionstart/compositionend）

## 通信协议
- 特殊按键: POST /key `{keysym, down, shift, ctrl}`
- 文本输入: POST /text `{text}`
- 触摸/滑动: POST /swipe, /tap, /scroll
- 导航: POST /back, /home, /recents
- 输入端口: 与 MJPEG 同端口(8081) 或独立端口(8084)
