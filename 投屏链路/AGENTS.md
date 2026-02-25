# 投屏链路模块 (Streaming)

包含三种投屏协议实现，平级隔离，互不依赖。

## 子模块
- `MJPEG投屏/` — MJPEG over HTTP，主力协议，InputRoutes 共享挂载于此
- `RTSP投屏/` — RTSP 实时传输协议
- `WebRTC投屏/` — WebRTC 浏览器直连

## 关键约束
- 三个子模块平级隔离，禁止互相依赖
- 都依赖 `:common`（070-基础设施）
- 前台服务必须 ContextCompat.startForegroundService() + 立即 startForeground()
- 修改任一子模块时，评估是否需要同步修改其他两个

## 对话结束选项

> 任务完成后调用 `ask_user_question`，从下表选 4 个最贴合的：

| label | description |
|-------|-------------|
| 装手机看画面 | 编译安装，打开浏览器验证投屏效果 |
| 三协议对齐 | 检查其他投屏协议是否需要同步 |
| 优化画面体验 | 继续改进帧率/延迟/画质 |
| 收工提交 | 记录成果 + git commit |
