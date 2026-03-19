# 亲情远程

> 让远方子女通过浏览器，实时看到并操控父母的安卓手机。
> P2P直连 · CloudRelay降级 · 父母一键 · 子女零安装 · 端到端加密

## 快速使用

### 子女端（浏览器）

**打开网页，输入连接码即可：**
```
https://aiotvr.xyz/cast/
```

**自动连接（含连接码）：**
```
https://aiotvr.xyz/cast/?room=123456
```

### 父母端（手机APP）
1. 打开 **ScreenStream** → 点击 **开始投屏**
2. 屏幕显示6位连接码 → 告诉子女

## 连接策略（三级降级，用户无感）

```
P2P直连 ──12秒超时──→ TURN中继 ──ICE失败3次──→ CloudRelay云中继
 (零成本)              (metered.ca)              (aiotvr.xyz)
```

| 模式 | 延迟 | 成本 | 触发条件 |
|------|------|------|---------|
| **P2P直连** | 30-100ms | ¥0 | 默认首选 |
| **TURN中继** | 50-200ms | ¥0 (metered.ca免费额度) | P2P穿透失败 |
| **CloudRelay** | ~50ms | ¥38/年 (阿里云) | TURN也失败/12秒无连接 |

## 目录结构

```
亲情远程/
├── README.md              ← 你在这里
├── signaling-server/      ← WebRTC信令服务器 (Node.js, :9100)
│   ├── server.js          ← ws://localhost:9100/signal/
│   └── package.json
├── relay-server/          ← CloudRelay云中继 (Node.js, :9800)
│   ├── server.js          ← WebSocket视频帧中继 + 控制转发
│   └── package.json
├── viewer/                ← 子女端网页 (纯静态HTML)
│   └── index.html         ← P2P + CloudRelay + WebCodecs H264解码
├── docs/                  ← 详细文档
│   ├── 技术资料汇总.md
│   ├── 架构方案.md
│   ├── 测试报告.md
│   ├── 用户指南-父母版.md
│   ├── 用户指南-子女版.md
│   └── 品牌适配矩阵.md
├── 亲情远程_升维终稿v6.md ← 25条技术路径评估 + 决策树
└── 五感审计报告.md
```

## 技术栈

| 层 | 技术 | 说明 |
|---|------|------|
| 采集 | MediaProjection | Android 5.0+, 无root |
| 控制 | AccessibilityService | 118+ API, 无root |
| P2P传输 | WebRTC | STUN/TURN, DTLS-SRTP端到端加密 |
| 云中继 | CloudRelay WebSocket | H264帧中继, WebCodecs解码 |
| 信令 | Node.js WebSocket | 仅交换SDP/ICE, 不碰媒体流 |
| 穿透 | FRP → aiotvr.xyz | ¥38/年, 已部署 |

## Viewer功能清单

- **P2P + CloudRelay双模式**：自动降级，用户无感
- **WebCodecs H264解码**：CloudRelay模式下高效解码
- **触控操作**：点按/滑动/长按/滚轮，精确坐标映射
- **控制栏**：返回/主页/最近/音量/通知/键盘/更多
- **更多菜单**：锁屏/唤醒/截图/全屏/快设/电源/分屏/找手机
- **状态监控**：延迟/FPS/码率/分辨率/连接质量指示
- **画面冻结检测**：自动提示
- **触觉反馈**：振动+音效
- **自动重连**：指数退避
- **全屏自动隐藏UI**：3秒无操作隐藏控制栏
- **后台恢复**：标签页切回时自动恢复视频流
- **键盘快捷键**：Esc=返回, Home=主页, Ctrl+↑↓=音量

## 本地开发

```bash
# 启动信令服务器
cd signaling-server && npm install && npm start
# → ws://localhost:9100/signal/   (信令WebSocket)
# → http://localhost:9100/cast/   (viewer页面)
# → http://localhost:9100/api/status (健康检查)

# 启动CloudRelay（可选）
cd relay-server && npm install && npm start
# → ws://localhost:9800/          (中继WebSocket)
# → http://localhost:9800/api/status (状态)
```

## 生产部署

```bash
# SCP到阿里云
scp -r signaling-server/ relay-server/ viewer/ aliyun:/www/dk_project/family-remote/

# 信令服务 (systemd)
ssh aliyun "cd /www/dk_project/family-remote/signaling-server && PORT=9100 nohup node server.js &"

# 中继服务 (systemd)
ssh aliyun "cd /www/dk_project/family-remote/relay-server && PORT=9800 nohup node server.js &"

# Nginx反代:
#   /signal/ → :9100/signal/ (WebSocket)
#   /relay/  → :9800         (WebSocket)
#   /cast/   → 静态文件
```

## 公网入口

| URL | 功能 | 状态 |
|-----|------|------|
| `https://aiotvr.xyz/cast/` | 子女端Viewer | ✅ |
| `wss://aiotvr.xyz/signal/` | P2P信令 | ✅ |
| `wss://aiotvr.xyz/relay/` | CloudRelay中继 | ✅ |
| `https://aiotvr.xyz/signal/api/status` | 信令状态 | ✅ |

## 手机端代码

关键文件（已在ScreenStream中实现）：
- `投屏链路/MJPEG投屏/mjpeg/internal/WebRtcP2PClient.kt` — WebRTC P2P客户端 (626行)
- `反向控制/输入服务/InputService.kt` — AccessibilityService (3700+行)
- `反向控制/共享路由/InputRoutes.kt` — 118+ HTTP API路由
- `反向控制/HTTP服务器/InputHttpServer.kt` — 独立API服务器 (:8084)

## 安全

- **房间码隔离**: 6位随机码, 每次不同
- **传输加密**: WebRTC DTLS-SRTP 端到端加密
- **信令加密**: WSS (HTTPS)
- **CloudRelay鉴权**: Token验证
- **速率限制**: 每IP每分钟最多10次连接
