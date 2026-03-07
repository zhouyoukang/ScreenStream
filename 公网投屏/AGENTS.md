# AGENTS.md — 公网投屏

## 目录用途
手机屏幕通过公网实时投射到任何浏览器，支持触控反操控。
两套系统: H264 Relay(WS中继) + WebRTC P2P(信令+直连)。

## 技术栈
- **Relay服务器**: Node.js + ws (:9800)
- **桥接脚本**: Python + websockets
- **前端**: 纯静态HTML (WebCodecs + Canvas)
- **信令**: Node.js + Socket.IO (投屏链路/公网投屏/ :9100)

## 端口
- **9800** — H264 Relay中继服务器
- **9801** — ADB信令中继
- **9100** — WebRTC P2P信令 (在投屏链路/公网投屏/)

## 关键文件
| 文件 | 用途 | 修改风险 |
|------|------|---------|
| `relay-server/server.js` | WS中继(房间+帧转发+控制) | 🟡中 |
| `ss-bridge.py` | SS H264→Relay桥接 | 🟡中 |
| `adb-bridge.py` | ADB screenrecord→Relay | 🟡中 |
| `viewer/index.html` | 浏览器Viewer(WebCodecs) | 🟡中 |
| `cast/setup.html` | 7步配置向导+公网ADB | 🟢低 |
| `cast/adb-bridge.py` | ADB Bridge v2.0 双模式 | 🟡中 |

## 公网入口
- `https://aiotvr.xyz/relay/` — 落地页+Viewer
- `https://aiotvr.xyz/cast/setup.html` — 配置中心
- `wss://aiotvr.xyz/relay/` — H264中继WebSocket

## 与其他项目关系
- **上游依赖**: `反向控制/` (触控API) + `投屏链路/MJPEG投屏/` (H264编码)
- **共享端口**: 9100/9800 与 `亲情远程/` 共用
- **部署**: 阿里云服务器 FRP穿透

## Agent操作规则
- 修改relay-server后需重启node进程
- 修改viewer后需scp部署到阿里云
- Token: `screenstream_2026`，修改需同步server.js和bridge
