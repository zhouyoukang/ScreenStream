---
trigger: always_on
---

# ScreenStream_v2 项目认知

## Gradle 模块映射
```
:app    → 用户界面/
:common → 基础设施/
:mjpeg  → 投屏链路/MJPEG投屏/
:rtsp   → 投屏链路/RTSP投屏/
:webrtc → 投屏链路/WebRTC投屏/
:input  → 反向控制/
```

## API 端口分配（固定，禁止冲突）
- Gateway: 8080 | MJPEG: 8081 | RTSP: 8082 | WebRTC: 8083 | Input: 8084

## 权威文档入口
1. `核心架构.md` → 2. `文档/FEATURES.md` → 3. `STATUS.md` → 4. `MODULES.md`

## Python 卫星项目（顶层目录）
- `智能家居/` → Python :8900 (HA代理+涂鸦+微信)
- `手机操控库/` → Python (PhoneLib, SS API封装)
- `远程桌面/` → Python :9903 (跨Windows账号控制)

## 外部项目（Junction链接，各自独立）
- C.学业: `二手书项目/` `三创赛项目/` `复习考试/`
- D.AI: `浏览器自动化/` `AI操控研究/` `AI规则体系/` `MIGPT/` `Dify/` `MaxKB/`
- E.硬件: `3D打印/` `PCB设计/` `OpenSCAD/` `轮毂电机/`
- F.工具: `N8N/` `RSS/` `视频制作/` `微信公众号/` `电脑管理/` `SpaceDesk/`

## 模块间依赖
- 向上依赖：应用层可依赖通用组件
- 平级隔离：流媒体模块间保持独立
- 接口优先：模块间通信使用明确接口
- 跨模块修改：必须评估影响面
- 外部项目：完全独立，无需协调
