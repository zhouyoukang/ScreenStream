# 投屏链路 · MJPEG/RTSP/WebRTC三协议投屏引擎

## 身份
ScreenStream投屏核心。三子模块平级隔离：MJPEG(:8081)+RTSP(:8082)+WebRTC(:8083)。MJPEG是主力，InputRoutes共享挂载于此。

## 边界
- ✅ 三个子模块目录及其所有文件
- 🚫 三子模块互相隔离，禁止互相依赖
- 🚫 前台服务必须startForegroundService()+立即startForeground()

## 入口
- MJPEG核心: `010-MJPEG投屏_MJPEG/mjpeg/HttpServer.kt`(Ktor服务器+路由挂载)
- 前端: `010-MJPEG投屏_MJPEG/assets/index.html`(6400行，PC/手机/VR三端)
- 代码地图: `05-文档_docs/MJPEG_CORE_MAP.md`

## 铁律
1. 修改任一子模块时评估其他两个是否需同步
2. 都依赖`:common`(070-基础设施)，禁止引入跨协议依赖
3. index.html修改需同步测试PC/手机/VR三端

## 关联
| 方向 | 项目 | 说明 |
|---|---|---|
| 挂载 | 反向控制 | InputRoutes.kt挂载在MJPEG HttpServer上 |
| 依赖 | 基础设施 | `:common`模块 |
| 上游 | 公网投屏 | H264编码供公网中继 |

## 陷阱
- WebRTC需HTTPS环境(HTTP下navigator.mediaDevices为null)
- MJPEG带宽5-15Mbps仅适合局域网，公网用WebRTC
