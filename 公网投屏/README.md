# 公网投屏 — 唯一真相源

> 手机屏幕通过公网实时投射到任何浏览器，支持触控反操控。
> 本目录是公网投屏的**统一交付中心**，包含全部可运行代码和资产。

## 一、两套系统

| 系统 | 原理 | 服务器带宽 | 状态 | 端口 | 公网路径 |
|------|------|-----------|------|------|---------|
| **H264 Relay** (本目录) | WS二进制中继，逐帧转发 | ~1Mbps | ✅ 已部署 | :9800 | `/relay/` |
| **WebRTC Signaling** (`投屏链路/公网投屏/`) | Socket.IO信令+P2P直连 | 零 | 🔧 本地可用 | :9100 | `/screen/` |

**选型依据**: H264 Relay简单可靠，适合当前1对1场景；WebRTC是演进方向，P2P直连后服务器零带宽。

## 二、公网入口

| 用途 | URL |
|------|-----|
| **落地页** | https://aiotvr.xyz/relay/ |
| **观看页** | https://aiotvr.xyz/relay/?room=phone&token=screenstream_2026 |
| **APK下载** | https://aiotvr.xyz/relay/ScreenStream.apk |
| **服务状态** | https://aiotvr.xyz/relay/api/status |

## 三、文件清单

### 本目录 — H264 Relay系统
| 文件 | 说明 | 大小 |
|------|------|------|
| `relay-server/server.js` | WS中继服务器（房间+帧转发+控制代理+Welcome+APK下载） | 15KB |
| `viewer/index.html` | 浏览器端（WebCodecs解码+触控+控制面板+画质切换） | 44KB |
| `welcome.html` | 落地引导页（3步卡片+实时状态检测） | 5KB |
| `ss-bridge.py` | ScreenStream H264→Relay桥接 + ADB控制转发 | 10KB |
| `adb-bridge.py` | ADB screenrecord直出H264→Relay（不依赖SS HTTP） | 10KB |
| `set_codec.py` | 画质设置（修改DataStore resizeFactor/codec+重启SS） | 3KB |
| `start.ps1` | 交互式一键启动（ADB发现→SS检查→relay→bridge） | 4KB |
| `auto-start.ps1` | 计划任务自启版（开机登录自动运行） | 3KB |
| `test-provider.py` | 模拟推流测试工具（合成H264帧，验证全链路） | 9KB |
| `test_h264.py` | SS H264/H265端点连通性测试 | 2KB |
| `ScreenStream.apk` | PlayStoreDebug APK（含WebRTC模块） | 56MB |

### 投屏链路/公网投屏/ — WebRTC P2P信令系统
| 文件 | 说明 |
|------|------|
| `server.js` | Socket.IO信令（兼容上游ScreenStreamWeb协议+JWT解码+TURN） | 18KB |
| `client/index.html` | WebRTC Web客户端（P2P直连+触控） | 24KB |
| `deploy/deploy-relay.sh` | 一键部署脚本 |
| `deploy/nginx-screen.conf` | Nginx反代模板（/screen/ + /app/socket + /app/） |
| `test-signaling.mjs` | 信令协议E2E测试 |
| `.env.example` | 环境变量模板（PORT+TURN） |

### Android端修改（Kotlin）
| 文件 | 修改 |
|------|------|
| `投屏链路/MJPEG投屏/mjpeg/internal/MjpegStreamingService.kt` | H264编码器+resizeFactor+1Mbps码率 |
| `投屏链路/MJPEG投屏/mjpeg/internal/H264Encoder.kt` | IDR间隔3秒（公网优化） |
| `投屏链路/WebRTC投屏/build.gradle.kts` | 自托管信令服务器URL buildConfigField |
| `投屏链路/WebRTC投屏/webrtc/internal/WebRtcEnvironment.kt` | `isSelfHosted`标志 |
| `投屏链路/WebRTC投屏/webrtc/internal/WebRtcStreamingService.kt` | 自托管模式跳过Play Integrity |

### 服务器部署
| 配置 | 说明 |
|------|------|
| `阿里云服务器/frpc.toml` relay段 | FRP隧道 localPort=9800 → remotePort=19800 |
| Nginx `aiotvr.xyz.conf` | `location /relay/` 反代→FRP:19800（WSS+HTTPS） |
| 计划任务 `ScreenStream_PublicRelay` | 登录时自动运行 `auto-start.ps1` |

## 四、帧协议

```
WebSocket Binary Frame:
  Byte 0:     帧类型 (0=SPS/PPS配置, 1=关键帧IDR, 2=P帧)
  Bytes 1-8:  时间戳 (int64 big-endian, microseconds)
  Bytes 9+:   H264 NAL数据（含startcode）
```

## 五、快速启动

```powershell
# 方式1: 一键启动（自动发现手机+启动relay+启动bridge）
powershell -File 公网投屏\start.ps1

# 方式2: 手动三步
cd 公网投屏/relay-server && node server.js --dev                      # 1. 中继
cd 公网投屏 && python ss-bridge.py --phone 192.168.31.40:8086 --device SERIAL  # 2. 桥接
# 3. 浏览器打开 http://localhost:9800/?room=phone&token=screenstream_2026

# 方式3: WebRTC系统（本地测试）
cd 投屏链路/公网投屏 && node server.js                                 # 信令 :9100
# 手机安装PlayStoreDebug APK → 选择WebRTC模式 → 开始投屏 → 记下8位ID
# 浏览器打开 http://localhost:9100/?id=12345678
```

## 六、性能实测 (公网HTTPS)

| 指标 | 数值 |
|------|------|
| 动画帧率 | 21-44fps |
| 静止帧率 | 0-1fps (H264正确行为) |
| 编码 | avc1.640015 H264 High L2.1, 270×602, 1Mbps |
| IDR帧 | 1.6-29KB (3秒间隔) |
| P帧 | <1KB |
| 全链路延迟 | ~50ms (FRP TCP直连) |

## 七、依赖

| 组件 | 依赖 | 安装 |
|------|------|------|
| Relay服务器 | Node.js + ws | `cd relay-server && npm install` |
| 桥接脚本 | Python + websockets | `pip install websockets` |
| WebRTC信令 | Node.js + express + socket.io | `cd 投屏链路/公网投屏 && npm install` |

## 八、架构

```
┌─ H264 Relay (已部署) ────────────────────────────────────────┐
│                                                               │
│  手机ScreenStream ──H264 WS──→ ss-bridge.py ──WS──→ relay    │
│        :8086                        ↕                :9800    │
│                              ADB控制转发              ↕ FRP   │
│                                                    :19800     │
│  浏览器 ←──────── WSS ──────── Nginx ──────── aiotvr.xyz     │
│  WebCodecs解码+触控             /relay/       :443 (HTTPS)    │
└───────────────────────────────────────────────────────────────┘

┌─ WebRTC P2P (本地可用) ──────────────────────────────────────┐
│                                                               │
│  手机ScreenStream ──Socket.IO──→ 信令服务器 ←──Socket.IO──    │
│  WebRTC Host                       :9100        WebRTC Client │
│        ↕                                             ↕        │
│        └──────── WebRTC P2P 直连 (SRTP加密) ────────┘        │
│                   视频+音频端到端, 服务器零带宽                  │
└───────────────────────────────────────────────────────────────┘
```

## 九、验证状态 (2026-02-27)

| 测试项 | 结果 |
|--------|------|
| Relay本地 /api/status | ✅ `{"ok":true,"rooms":1}` |
| Relay公网 /relay/api/status | ✅ 同上 (FRP穿透正常) |
| Welcome落地页渲染 | ✅ 3步卡片+实时状态(绿灯) |
| APK公网下载 | ✅ 200 OK, 56MB |
| Viewer页面渲染 | ✅ 控制面板+画质选择+WebCodecs就绪 |
| WebRTC信令 /api/status | ✅ `{"status":"ok"}` |
| WebRTC /app/ping | ✅ 204 |
| WebRTC /app/nonce | ✅ 64字符hex |

## 十、零服务器P2P方案 (2026-02-27 验证)

> 不依赖aiotvr.xyz，纯P2P端到端，免费基础设施。

### 架构
```
手机ScreenStream(:8086) ──H264 WS──→ p2p-bridge.html(本地浏览器)
                                            ↕ PeerJS Cloud(免费信令)
                                            ↕ WebRTC DataChannel(P2P)
                                     p2p-viewer.html(远程浏览器) ←── 家人
```

### 文件
| 文件 | 说明 |
|------|------|
| `p2p-bridge.html` | 浏览器端桥接（老人家中电脑打开，连接手机+PeerJS信令+转发H264） |
| `p2p-viewer.html` | 远程观看器（家人打开，输入6位房间码即可看到+操控手机） |

### 使用流程
1. 老人家中电脑浏览器打开 `p2p-bridge.html` → 输入手机IP → 点"启动桥接" → 显示6位房间码
2. 家人在任何设备浏览器打开 `p2p-viewer.html` → 输入房间码 → 立即看到手机屏幕

### 免费基础设施
| 组件 | 服务 | 费用 |
|------|------|------|
| 信令 | PeerJS Cloud (0.peerjs.com) | 免费 |
| STUN | Google (stun.l.google.com) | 免费 |
| TURN | metered.ca OpenRelay | 免费 |
| 媒体 | WebRTC DataChannel P2P | 免费，零服务器带宽 |
| 托管 | 本地文件/GitHub Pages/任何静态托管 | 免费 |

### 验证结果 (2026-02-27)
| 测试项 | 结果 |
|--------|------|
| PeerJS信令注册 | ✅ `ss-bridge-888888` 注册成功 |
| Viewer→Bridge P2P连接 | ✅ DataChannel建立，观看人数=1 |
| Bridge自动重连ScreenStream | ✅ 5秒间隔持续重试 |

### 六种零服务器方案对比

| 方案 | 原理 | 国内可用 | 复杂度 | 推荐 |
|------|------|---------|--------|------|
| **PeerJS Cloud** | 免费信令+WebRTC P2P | ✅ | 低 | ⭐ 首选 |
| **P2PCF** | Cloudflare Workers信令 | ✅ | 中 | 备选(自建Worker更可靠) |
| **QR码交换SDP** | 扫码交换offer/answer | ✅ | 高(UX差) | 不推荐 |
| **Firebase Realtime** | 数据库做信令通道 | ⚠️ 部分blocked | 中 | 备选 |
| **Cloudflare Calls TURN** | 免费1000GB/月TURN | ✅ | 低 | 补充TURN |
| **ngrok/bore隧道** | 穿透本地服务器 | ⚠️ 需认证 | 低 | 应急 |

## 十二、手机自桥接方案 (2026-02-27 验证通过)

> **不依赖PC、不依赖服务器、零成本**。手机Chrome直接运行桥接，远程家人扫码即看。

### 架构
```
手机ScreenStream(:8086) ──H264 WS──→ 手机Chrome(phone-cast.html)
                                            ↕ PeerJS Cloud(免费信令)
                                            ↕ WebRTC DataChannel(P2P直连)
                                      cast-viewer.html(远程浏览器) ←── 家人/自己
```

### 公网入口
| 用途 | URL |
|------|-----|
| **手机桥接端** | https://aiotvr.xyz/phone-cast.html |
| **远程观看端** | https://aiotvr.xyz/cast-viewer.html?room=房间码 |

### 文件
| 文件 | 说明 |
|------|------|
| `phone-cast.html` | 手机端桥接（手机Chrome打开，连SS+PeerJS，生成房间码+QR码） |
| `cast-viewer.html` | 远程观看端（WebCodecs解码+触控+控制按钮，URL参数自动连接） |

### 使用流程
1. 手机开启ScreenStream投屏（端口8086）
2. 手机Chrome打开 `https://aiotvr.xyz/phone-cast.html` → 点"开始桥接" → 显示6位房间码+QR码
3. 远程设备扫QR码或打开 `https://aiotvr.xyz/cast-viewer.html?room=房间码` → 立即看到手机屏幕

### 免费基础设施（国内可用）
| 组件 | 服务 | 国内可用 | 费用 |
|------|------|---------|------|
| 信令 | PeerJS Cloud (0.peerjs.com) | ✅ 已验证 | 免费 |
| STUN | Google + 小米 + B站 | ✅ 多fallback | 免费 |
| TURN | metered.ca OpenRelay (全球CDN) | ✅ TCP+UDP | 免费 |
| CDN | cdnjs.cloudflare.com (PeerJS库) | ✅ + unpkg fallback | 免费 |
| 页面托管 | aiotvr.xyz (静态文件) | ✅ | 已有 |
| **总成本** | | | **¥0** |

### 验证结果 (2026-02-27)
| 测试项 | 结果 |
|--------|------|
| PeerJS信令注册 | ✅ `ss-bridge-698884` 1秒内连接 |
| ScreenStream H264流 | ✅ Config+IDR+P帧持续接收 |
| Wake Lock防息屏 | ✅ 已激活 |
| QR码+观看URL生成 | ✅ 自动生成 |
| Viewer P2P连接 | ✅ DataChannel建立 |
| WebCodecs解码播放 | ✅ 270×602 avc1.640015 |
| 触控/控制按钮 | ✅ 返回/主页/最近/音量/通知/电源 |
| 帧转发统计 | ✅ 150+帧, 612KB |

### vs 旧P2P方案对比
| 维度 | p2p-bridge.html (旧) | phone-cast.html (新) |
|------|---------------------|---------------------|
| PC依赖 | ⚠️ 需PC浏览器运行bridge | ✅ 手机自运行 |
| CDN | unpkg.com (国内偶尔慢) | cdnjs.cloudflare.com + fallback |
| ICE服务器 | Google + metered.ca | Google + 小米 + B站 + metered.ca |
| QR码 | ❌ 无 | ✅ 内嵌QR生成器 |
| Wake Lock | ❌ 无 | ✅ 防息屏 |
| URL参数自动连接 | ❌ 手动输入 | ✅ ?room=参数自动连接 |

## 十四、手机自主公网投屏 — CloudRelay (2026-02-28)

> **终极方案**：手机安装ScreenStream → 开始投屏 → 自动连接公网 → 任何浏览器打开URL即看+操控。
> 零PC、零配置、零注册、一键启动。

### 架构
```
手机ScreenStream
  ├── H264编码(MediaProjection) → h264SharedFlow
  ├── CloudRelayClient(OkHttp WS) ──WSS──→ aiotvr.xyz/relay ←──WSS── 浏览器
  │     ├── 发送: H264帧(二进制)                                  显示: WebCodecs
  │     └── 接收: 触控/控制JSON → POST localhost:8084             触控: Canvas事件
  └── 本地HTTP(:8081) 仍正常工作(局域网访问)
```

### 用户三步操作
1. **安装** — 手机安装 ScreenStream APK
2. **投屏** — 打开APP → 选H264模式 → 点"开始"
3. **观看** — 任何设备浏览器打开 `https://aiotvr.xyz/cast/?room=房间码`

### 新增文件
| 文件 | 说明 |
|------|------|
| `投屏链路/MJPEG投屏/mjpeg/internal/CloudRelayClient.kt` | Android WS客户端(OkHttp→relay, 帧转发+触控接收) |
| `公网投屏/cast/index.html` | 公网观看页(WebCodecs+触控+自动重连) |
| `公网投屏/deploy-cast.ps1` | 一键部署观看页到aiotvr.xyz |

### 修改文件
| 文件 | 修改 |
|------|------|
| `投屏链路/MJPEG投屏/build.gradle.kts` | +OkHttp依赖 |
| `投屏链路/MJPEG投屏/mjpeg/internal/MjpegStreamingService.kt` | H264流启动时自动启动CloudRelay |

### 技术要点
- **自有中继**: aiotvr.xyz relay server(已部署:9800), 非第三方服务
- **帧协议**: 1B type + 8B timestamp + H264 NAL (与现有relay完全兼容)
- **触控路由**: viewer → relay JSON → CloudRelay → POST /tap,/swipe,/back... → InputService(:8084)
- **自动重连**: 指数退避(2s→30s), 网络波动无感恢复
- **背压控制**: WS队列>512KB时丢弃P帧, 防止累积延迟
- **零配置**: 房间码自动生成(6位), relay URL硬编码在APK中

### vs 旧方案对比
| 维度 | ss-bridge.py (旧) | phone-cast.html (P2P) | CloudRelay (新) |
|------|-------------------|----------------------|-----------------|
| PC依赖 | ⚠️ 需PC运行bridge | ⚠️ 需手机开Chrome | ✅ 零依赖 |
| 第三方服务 | ❌ 无 | ⚠️ PeerJS Cloud | ✅ 自有relay |
| 用户操作 | 5步+ | 3步 | **2步** (安装+点投屏) |
| 操控 | ✅ ADB转发 | ✅ WS→HTTP | ✅ WS→HTTP |
| 国内可用 | ✅ | ⚠️ PeerJS偶尔不稳 | ✅ 阿里云国内节点 |

## 十五、配置中心 + 公网远程ADB v2.0 (2026-03-04)

> **一次配置，永久投屏**。用户打开网页 → 下载启动器 → 输入连接码 → 一键完成手机全部配置。
> Agent可通过WebSocket远程连接Bridge，代替用户执行所有ADB配置操作。

### 架构
```
网页(setup.html)                          电脑(ADB Bridge)
  adb-controller ←─WSS─→ 信令服务器 ←─WSS─→ adb-bridge
  输入连接码+点按钮       aiotvr.xyz:9801      USB连接手机
                         中继所有命令            执行ADB命令
```

### 公网入口
| 用途 | URL |
|------|-----|
| **配置中心** | https://aiotvr.xyz/cast/setup.html |
| **预填连接码** | https://aiotvr.xyz/cast/setup.html?adb=连接码 |
| **下载Bridge** | https://aiotvr.xyz/cast/adb-bridge.py |
| **下载启动器** | https://aiotvr.xyz/cast/start-adb-bridge.bat |
| **信令状态** | https://aiotvr.xyz/signal/api/status |

### 文件
| 文件 | 说明 |
|------|------|
| `cast/setup.html` | 7步配置向导 + 公网ADB面板(连接码+一键配置+日志) |
| `cast/adb-bridge.py` | ADB Bridge v2.0 双模式(本地HTTP :8085 / 公网WebSocket) |
| `cast/start-adb-bridge.bat` | Windows一键启动器(自动检测Python/ADB/手机) |
| `signaling/server.js` | P2P信令 + ADB中继(adb-bridge/adb-controller角色) |

### 用户流程（3步）
1. **下载** — 电脑下载 `start-adb-bridge.bat` + `adb-bridge.py`，双击运行
2. **连接** — 网页输入6位连接码 → 🔗连接
3. **配置** — 点 ⚡一键自动配置 → 权限+启动+端口转发全部远程完成

### WebSocket命令协议
| 命令 | 方向 | 说明 |
|------|------|------|
| `get_status` | C→B | 查询Bridge状态(ADB路径/设备数) |
| `get_devices` | C→B | 列出所有USB设备 |
| `adb_command{args}` | C→B | 执行任意ADB命令(白名单过滤) |
| `preset{action}` | C→B | 执行预设操作(check_device/get_device_info等) |
| `auto_config` | C→B | 一键自动配置(检测→权限→启动→端口转发) |
| `device_info` | B→C | 设备信息广播 |
| `adb_connected` | S→C | Bridge已连接通知 |

### 验证结果 (2026-03-04)
| 测试项 | 结果 |
|--------|------|
| Bridge→信令 WebSocket | ✅ 连接+注册+自动重连 |
| Controller→信令→Bridge 中继 | ✅ 11条命令全部成功 |
| 0设备优雅降级 | ✅ 禁用按钮+明确提示 |
| auto_config 7步配置 | ✅ 逐步结果+错误恢复 |
| 公网4 URL全部200 | ✅ setup/bridge/bat/status |

## 十三、关键教训

1. **Cloudflare缓冲WebSocket二进制帧** → 0-1fps(致命) → FRP TCP直连50ms RTT → 21-44fps
2. **降分辨率1080p→270p** → IDR从1.1MB→29KB → 带宽减97%
3. **WebRTC需PlayStore flavor** → `./gradlew :app:assemblePlayStoreDebug`
4. **自托管模式**: `CLOUD_PROJECT_NUMBER=0` → 跳过Play Integrity
5. **PeerJS Node.js不可用** — 需浏览器WebRTC API，故bridge用HTML而非Node.js
6. **PeerJS Cloud国内可达** — 0.peerjs.com WebSocket连接正常(2026-02-27验证)
