# RTSP 投屏模块

## 核心职责
RTSP 协议实现，支持实时视频流传输。

## 与其他模块的关系
- 与 MJPEG/WebRTC 平级隔离
- 共用 `:common` 基础设施
- 端口: 8082

## 对话结束选项

> 任务完成后调用 `ask_user_question`，从下表选 4 个最贴合的：

| label | description |
|-------|-------------|
| 装手机验证RTSP | 编译安装，连接客户端验证流效果 |
| 同步其他协议 | 检查MJPEG/WebRTC是否需要同步 |
| 继续优化RTSP | 改进协议实现或性能 |
| 收工提交 | 记录成果 + git commit |
