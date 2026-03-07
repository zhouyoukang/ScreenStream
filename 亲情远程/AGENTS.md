# AGENTS.md — 亲情远程

## 目录用途
远方子女通过浏览器实时看到并操控父母Android手机。
P2P直连 · TURN中继 · CloudRelay三级降级，用户无感切换。

## 技术栈
- **信令**: Node.js WebSocket (本地:9100, 生产:9101, systemd: `family-signaling.service`)
- **中继**: Node.js WebSocket (:9800)
- **前端**: 纯静态HTML (WebRTC + WebCodecs)
- **传输**: WebRTC DTLS-SRTP端到端加密 / CloudRelay H264帧中继

## 端口
- **9100** — P2P信令服务器 (本地开发默认端口)
- **9101** — P2P信令服务器 (生产环境, systemd管理, PORT=9101)
- **9800** — CloudRelay云中继 (WebSocket)

## 关键文件
| 文件 | 用途 | 修改风险 |
|------|------|---------|
| `signaling-server/server.js` | WebRTC信令 | 🟡中 |
| `relay-server/server.js` | CloudRelay中继 | 🟡中 |
| `viewer/index.html` | 子女端Viewer (P2P+CloudRelay) | 🟡中 |

## 公网入口
- `https://aiotvr.xyz/cast/` — Viewer
- `wss://aiotvr.xyz/signal/` — P2P信令
- `wss://aiotvr.xyz/relay/` — CloudRelay

## 与其他项目关系
- **上游依赖**: `反向控制/` (70+ API) + `投屏链路/` (WebRTC/H264)
- **共用基础设施**: 阿里云服务器 (FRP穿透)
- **端口共享**: 9800 CloudRelay与 `公网投屏/` 共用; 信令独立部署于9101

## Agent操作规则
- 修改viewer后需scp部署到阿里云
- 修改信令/中继需SSH重启服务
- 手机端代码在 `投屏链路/` 和 `反向控制/`，不在本目录
