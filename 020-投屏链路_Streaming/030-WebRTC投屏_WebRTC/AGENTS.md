# WebRTC 投屏模块

## 核心职责
WebRTC 协议实现，支持浏览器端 P2P 直连投屏。

## 与其他模块的关系
- 与 MJPEG/RTSP 平级隔离
- 共用 `:common` 基础设施
- 端口: 8083

## 对话结束选项

> 任务完成后调用 `ask_user_question`，从下表选 4 个最贴合的：

| label | description |
|-------|-------------|
| 装手机验证连接 | 编译安装，浏览器WebRTC连接试试 |
| 同步其他协议 | 检查MJPEG/RTSP是否需要同步 |
| 继续优化WebRTC | 改进P2P连接/信令/编码 |
| 收工提交 | 记录成果 + git commit |
