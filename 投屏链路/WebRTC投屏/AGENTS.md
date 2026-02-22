# WebRTC 投屏模块

## 核心职责
WebRTC 协议实现，支持浏览器端 P2P 直连投屏。

## 与其他模块的关系
- 与 MJPEG/RTSP 平级隔离
- 共用 `:common` 基础设施
- 端口: 8083

## 对话结束选项

> 任务完成后，AI 必须调用 `ask_user_question` 从以下选项中选取 4 个最相关的：

| label | description |
|-------|-------------|
| 编译部署测试 | Gradle构建→推送→安装→WebRTC连接验证 |
| 对齐其他协议 | 检查MJPEG/RTSP是否有同类改进需要同步 |
| 继续WebRTC开发 | 继续优化P2P连接/信令/编码 |
| 更新文档提交 | 更新FEATURES.md + git commit |
