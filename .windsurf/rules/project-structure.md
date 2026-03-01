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

## 凭据管理
- **结构索引**: `凭据中心.md`（git tracked，键名+描述，无实际值）
- **实际凭据**: `secrets.env`（gitignored，Agent用 `run_command("Get-Content secrets.env")` 读取）
- **协议详见**: `execution-engine.md` §凭据中心

## Python 卫星项目（顶层目录）
- `智能家居/` → Python :8900 (HA代理+涂鸦+微信)
- `手机操控库/` → Python (PhoneLib, SS API封装)
- `远程桌面/` → Python :9903 (跨Windows账号控制)
- `认知代理/` → Python :9070 (五维感知+意图提炼+工作流引擎)

## 基础设施层（阿里云 aiotvr.xyz）
- **健康感知**: `curl https://aiotvr.xyz/api/health` → 实时JSON（服务/端口/隧道/SSL/资源）
- **服务器**: 60.205.171.100 / `ssh aliyun` / 2核2G Ubuntu 24.04
- **Nginx反代(443)**: / /book/ /cast/ /app/ /screen/ /input/ /wx /frp/ /api/*
- **FRP 7隧道**: agent:19903 rdp:13389 ss:18086 input:18084 gw:18900 book:18088 ghost:18000
- **本地服务**: relay:9100(systemd) HA:8123(Docker) frps:7000
- **SSL**: Let's Encrypt → 2026-05-26, certbot cron每月1日+15日
- **详情**: `阿里云服务器/README.md` | **Agent手册**: `阿里云服务器/AGENTS.md`

## 外部项目（Junction链接，各自独立）
- C.学业: `二手书项目/` `三创赛项目/` `复习考试/` + `ARGs论文/`(真实目录)
- D.AI: `浏览器自动化/` `AI初恋/` `AI规则体系/` `MIGPT/` `MIGPT-Easy/` `Dify/` `MaxKB/`
- E.硬件: `3D打印/` `PCB设计/` `OpenSCAD/` `轮毂电机/`
- F.工具: `视频制作/` `微信公众号/` `电脑管理/` `N8N/` `N8N工作流/` `RSS/` `HA卡片/` `SpaceDesk/` `VR网站/` `IPv6/` `旅行计划/`

## 模块间依赖
- 向上依赖：应用层可依赖通用组件
- 平级隔离：流媒体模块间保持独立
- 接口优先：模块间通信使用明确接口
- 跨模块修改：必须评估影响面
- 外部项目：完全独立，无需协调
