# 投屏链路模块 (Streaming)

包含三种投屏协议实现，平级隔离，互不依赖。

## 子模块
- `010-MJPEG投屏_MJPEG/` — MJPEG over HTTP，主力协议，InputRoutes 共享挂载于此
- `020-RTSP投屏_RTSP/` — RTSP 实时传输协议
- `030-WebRTC投屏_WebRTC/` — WebRTC 浏览器直连

## 关键约束
- 三个子模块平级隔离，禁止互相依赖
- 都依赖 `:common`（070-基础设施）
- 前台服务必须 ContextCompat.startForegroundService() + 立即 startForeground()
- 修改任一子模块时，评估是否需要同步修改其他两个
