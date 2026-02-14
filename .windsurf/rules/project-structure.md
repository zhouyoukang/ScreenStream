---
trigger: always_on
---

# ScreenStream_v2 项目认知

## Gradle 模块映射
```
:app    → 010-用户界面与交互_UI/
:common → 070-基础设施_Infrastructure/
:mjpeg  → 020-投屏链路_Streaming/010-MJPEG投屏_MJPEG/
:rtsp   → 020-投屏链路_Streaming/020-RTSP投屏_RTSP/
:webrtc → 020-投屏链路_Streaming/030-WebRTC投屏_WebRTC/
:input  → 040-反向控制_Input/
```

## API 端口分配（固定，禁止冲突）
- Gateway: 8080 | MJPEG: 8081 | RTSP: 8082 | WebRTC: 8083 | Input: 8084

## 权威文档入口
1. `05-文档_docs/README.md` → 2. `MODULES.md` → 3. `FEATURES.md` → 4. `PROCESS.md`

## 模块间依赖
- 向上依赖：应用层可依赖通用组件
- 平级隔离：流媒体模块间保持独立
- 接口优先：模块间通信使用明确接口
- 跨模块修改：必须评估影响面
