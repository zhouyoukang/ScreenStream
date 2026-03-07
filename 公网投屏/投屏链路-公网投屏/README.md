# WebRTC P2P 公网投屏 — 信令服务器

> **全景文档见**: `公网投屏/README.md`（唯一真相源）
> 本目录是WebRTC P2P方案的信令服务器和Web客户端。

## 定位

H264 Relay（`公网投屏/`）已部署运行，本目录是**演进方向** — P2P直连后服务器零带宽。

## 文件

| 文件 | 说明 |
|------|------|
| `server.js` | Socket.IO信令（兼容上游ScreenStreamWeb协议+JWT+TURN） |
| `client/index.html` | WebRTC Web客户端 |
| `deploy/` | 部署脚本+Nginx配置模板 |
| `test-signaling.mjs` | 信令协议E2E测试 |
| `.env.example` | 环境变量模板 |

## 快速启动

```bash
npm install
node server.js          # :9100
# 浏览器 http://localhost:9100/
```

## 协议

兼容 dkrivoruchko/ScreenStreamWeb (MIT):
- Host: STREAM:CREATE/REMOVE/START/STOP, HOST:OFFER/CANDIDATE
- Client: STREAM:JOIN/LEAVE, CLIENT:ANSWER/CANDIDATE
- Auth: Host发`{hostToken, device}`, Client发`{token}`

## 自托管模式

Android端 `CLOUD_PROJECT_NUMBER=0` → `isSelfHosted=true` → 跳过Play Integrity → nonce直接作token

## ICE策略

- 默认: Google STUN (免费, ~80%穿透)
- 可选: coturn TURN (env `TURN_SERVER` + `TURN_SECRET`, ~99%穿透)

## 部署到 aiotvr.xyz

```bash
scp -r package.json server.js client/ .env.example aliyun:/www/dk_project/screenstream-relay/
ssh aliyun "cd /www/dk_project/screenstream-relay && npm install --production && pm2 start server.js --name screenstream-relay"
```

Nginx配置见 `deploy/nginx-screen.conf`（路径 `/screen/` + `/app/socket` + `/app/`）

## Android修改

| 文件 | 修改 |
|------|------|
| `投屏链路/WebRTC投屏/build.gradle.kts` | buildConfigField SIGNALING_SERVER |
| `投屏链路/WebRTC投屏/webrtc/internal/WebRtcEnvironment.kt` | `isSelfHosted`标志 |
| `投屏链路/WebRTC投屏/webrtc/internal/WebRtcStreamingService.kt` | 跳过Play Integrity |

构建: `./gradlew :app:assemblePlayStoreDebug` (WebRTC仅PlayStore flavor)

## 演进

- **Phase 1** ✅ 信令+Web客户端+自托管模式（本地已验证）
- **Phase 2** 待做: 部署到aiotvr.xyz + APK构建验证
- **Phase 3** 待做: DataChannel反向控制 + coturn TURN
- **Phase 4** 待做: 双向投屏+文件传输

## 验证 (2026-02-27)

| 端点 | 结果 |
|------|------|
| `GET /api/status` | ✅ `{"status":"ok"}` |
| `GET /app/ping` | ✅ 204 |
| `GET /app/nonce` | ✅ 64字符hex |
