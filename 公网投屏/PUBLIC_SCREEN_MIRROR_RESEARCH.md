# 公网投屏+反控：全景研究报告

> **核心目标**：任何人在任何地方打开一个网页，即可看到手机屏幕并完全操控手机
> **作者**：AI Agent | **日期**：2026-02-26

---

## 一、现状诊断（问·惑·祸）

### 1.1 当前架构

```
手机(ScreenStream)                    PC(局域网)
┌──────────────────┐                ┌────────────┐
│ MediaProjection  │──MJPEG/H264──→│ 浏览器      │
│ Ktor HTTP :8081  │←──POST API────│ index.html  │
│ InputService 70+ │                │ 6400行前端  │
│ WebSocket touch  │                └────────────┘
└──────────────────┘
        ↓ ADB forward
  localhost:8086 → 手机:8081
```

**可用路径**：
- 局域网直连：`http://手机IP:8081` ✅ 完美
- USB ADB转发：`http://127.0.0.1:8086` ✅ 完美
- WiFi直连：`http://192.168.x.x:8084` ✅ 可用

### 1.2 公网现状

| 组件 | 状态 | 问题 |
|------|------|------|
| FRP隧道 | ✅ `aiotvr.xyz:19903→:9903` | 仅为remote_agent，非投屏 |
| Nginx | ✅ aiotvr.xyz:443 | 仅静态网站和HA反代 |
| WebRTC模块 | ❌ 死代码 | 依赖上游云信令+Play Integrity验证 |
| TURN/STUN | ❌ 无 | 无NAT穿透能力 |
| 公网投屏 | ❌ 不可用 | 从未实现 |
| 公网反控 | ❌ 不可用 | 从未实现 |

### 1.3 十二问（技术问题清单）

| # | 问 | 严重度 | 根因 |
|---|-----|--------|------|
| Q1 | 手机在4G/5G网络时，PC无法连接 | 🔴致命 | 运营商NAT，手机无公网IP |
| Q2 | 手机在外地WiFi时，跨网段不可达 | 🔴致命 | 路由器NAT隔离 |
| Q3 | WebRTC模块无法使用 | 🔴致命 | 信令服务器是上游私有的screenstream.io |
| Q4 | MJPEG流带宽消耗巨大（3-10 Mbps） | 🟡高 | 无压缩的JPEG序列 |
| Q5 | H264 WebSocket流无公网中继 | 🟡高 | 无WebSocket反代/中继 |
| Q6 | 70+ API端点无公网暴露 | 🟡高 | 仅局域网Ktor HTTP可达 |
| Q7 | WebSocket触控流无公网中继 | 🟡高 | /ws/touch仅局域网 |
| Q8 | 无身份认证（公网暴露=裸奔） | 🔴致命 | PIN码仅限局域网场景 |
| Q9 | 无TLS加密（公网传输明文） | 🔴致命 | Ktor HTTP无SSL |
| Q10 | 延迟不可控 | 🟡高 | 跨地域+中继=延迟叠加 |
| Q11 | 多人同时观看时带宽爆炸 | 🟢中 | 每个客户端独立编码流 |
| Q12 | 手机电量/性能持续消耗 | 🟢中 | MediaProjection+编码+网络 |

### 1.4 七惑（认知困惑）

| # | 惑 | 解答 |
|---|-----|------|
| H1 | WebRTC不是已经有P2P了吗？ | 是，但需要信令服务器协商。上游用screenstream.io私有服务器+Play Integrity验证，我们的fork不可能通过验证 |
| H2 | FRP不是已经打通了吗？ | FRP隧道只转发了remote_agent:9903，没有转发投屏端口8081/8084 |
| H3 | MJPEG和H264哪个更适合公网？ | H264带宽仅为MJPEG的1/5-1/10，公网必须用H264/H265 |
| H4 | 为什么不直接FRP转发8081？ | 可以但有三个问题：①无TLS ②WebSocket需特殊配置 ③FRP TCP隧道延迟高 |
| H5 | 上游WebRTC代码能直接复用吗？ | **不能**。`SocketSignaling.kt`硬绑定screenstream.io + `PlayIntegrity.kt`需要Google Cloud Project验证。必须替换信令层 |
| H6 | 用什么技术在浏览器解码H264？ | 优先WebCodecs API（硬件加速）→ 降级MSE（MediaSource Extension）→ 最后Broadway/tinyh264（WASM软解） |
| H7 | coturn TURN服务器部署难度？ | 中等。Docker一键部署，但需要公网IP+开放UDP端口范围 |

### 1.5 九祸（已知和潜在灾难）

| # | 祸 | 后果 | 等级 |
|---|-----|------|------|
| D1 | 无认证公网暴露 | 任何人可操控你的手机 | 🔴致命 |
| D2 | 明文传输 | 屏幕内容被中间人截获 | 🔴致命 |
| D3 | WebRTC信令服务器依赖上游 | 完全受制于人 | 🔴致命 |
| D4 | MJPEG公网带宽耗尽 | 移动流量+服务器带宽双爆 | 🟡高 |
| D5 | 中继服务器单点故障 | 服务器挂=全部断 | 🟡高 |
| D6 | 手机休眠/网络切换断流 | 投屏中断无自动恢复 | 🟡高 |
| D7 | 阿里云带宽限制（1-5Mbps） | 视频流卡顿/断流 | 🟡高 |
| D8 | Play Integrity验证 | 非Google Play版本无法使用上游WebRTC | 🟢已知 |
| D9 | SSL证书过期(2026-05-26) | HTTPS失效 | 🟢可控 |

---

## 二、全球开源方案对标

### 2.1 方案全景矩阵

| 项目 | ★数 | 架构模式 | 视频编码 | 浏览器解码 | 反向控制 | 公网支持 | 自托管 |
|------|------|---------|---------|-----------|---------|---------|--------|
| **scrcpy** | 120K | ADB+本地渲染 | H264/H265 | N/A(SDL) | ✅ ADB | ❌ 仅本地 | N/A |
| **ws-scrcpy** | 4.5K | WebSocket中继 | H264 | Broadway/tinyh264/WebCodecs/MSE | ✅ 触控+键盘 | ✅ 需中继 | ✅ Node.js |
| **ya-webadb(Tango)** | 5K | WebUSB直连 | H264 | WebCodecs/tinyh264 | ✅ ADB协议 | ❌ USB限 | N/A |
| **DeviceFarmer STF** | 13K | ADB+minicap+minitouch | JPEG | `<img>` | ✅ minitouch | ✅ 需服务器 | ✅ 重量级 |
| **Headwind Remote** | 1K | Janus WebRTC | H264 | 原生WebRTC | ✅ 虚拟鼠标 | ✅ TURN | ✅ 重量级 |
| **dkrivoruchko ScreenStream** | 3K | WebRTC+云信令 | VP8/H264 | 原生WebRTC | ❌ 仅投屏 | ✅ 云服务 | ❌ 私有云 |
| **web_screen** | 0.3K | WebRTC直连 | H264 | 原生WebRTC | ✅ 基础触控 | ❌ P2P仅局域网 | ✅ |
| **我们的ScreenStream v2** | — | HTTP/WS直连 | MJPEG/H264/H265 | canvas/WS | ✅ 70+ API | ❌ 仅局域网 | ✅ |

### 2.2 技术栈深度对比

#### ws-scrcpy（最接近我们的需求）
```
架构：
  PC/Server (Node.js)
    ├─ adb 连接手机（USB/WiFi）
    ├─ 启动 scrcpy-server.jar（修改版）
    ├─ WebSocket代理视频流+控制消息
    └─ 静态Web前端
  
  Browser
    ├─ WebSocket接收H264帧
    ├─ 解码器选择：WebCodecs > MSE > tinyh264 > Broadway
    └─ Canvas渲染 + 触控/键盘事件发送

优点：成熟、多解码器支持、包含shell/文件管理
缺点：依赖ADB（需要PC中间人），不能手机直出
```

#### Headwind Remote（最接近我们的目标架构）
```
架构：
  Android Agent (手机上)
    ├─ MediaProjection 采集屏幕
    ├─ 编码 H264
    ├─ 通过 WebSocket 发送到 Janus
    └─ 接收触控指令执行
  
  Janus WebRTC Gateway (服务器)
    ├─ 接收手机的H264流
    ├─ 转换为WebRTC流
    ├─ 信令协商
    └─ TURN中继（coturn）
  
  Browser
    ├─ 标准WebRTC接收
    ├─ 原生<video>标签播放
    └─ 触控事件通过DataChannel或HTTP

优点：标准WebRTC、低延迟、浏览器原生解码
缺点：Janus部署复杂、服务器CPU消耗高
```

#### 上游ScreenStream WebRTC（分析其不可用原因）
```
架构：
  Android App (手机上)
    ├─ MediaProjection → org.webrtc原生编码
    ├─ Socket.IO连接 screenstream.io（私有云）
    ├─ PlayIntegrity验证（绑定Google Cloud Project）
    └─ WebRTC P2P连接（STUN/TURN由云提供）
  
  screenstream.io (私有云)
    ├─ Socket.IO信令服务器
    ├─ JWT验证
    ├─ Play Integrity Token验证
    ├─ ICE Server动态分配
    └─ Web客户端托管

不可用原因（3个致命点）：
  1. BuildConfig.SIGNALING_SERVER 指向 screenstream.io（私有）
  2. PlayIntegrity 需要 CLOUD_PROJECT_NUMBER（我们没有）
  3. 我们的fork签名与上游不同，Integrity验证必定失败
```

### 2.3 浏览器视频解码技术对比

| 技术 | 硬件加速 | 延迟 | 兼容性 | 最适场景 |
|------|---------|------|--------|---------|
| **WebRTC原生** | ✅ | <100ms | Chrome/Firefox/Safari | P2P直连或TURN中继 |
| **WebCodecs API** | ✅ | ~50ms | Chrome 94+ | WebSocket传输的H264 |
| **MSE (MediaSource)** | ✅ | 200-500ms | 所有现代浏览器 | 点播/低延迟直播 |
| **tinyh264 (WASM)** | ❌ | ~100ms | 所有支持WASM的 | 降级方案 |
| **Broadway (WASM)** | ❌ | ~150ms | 同上 | 最老的降级方案 |

**结论**：WebRTC原生 > WebCodecs > MSE > tinyh264 > Broadway

---

## 三、架构方案设计（四种路线）

### 3.1 方案A：FRP直通增强（最快实现，1-2天）

```
                     公网
手机 ──FRP TCP──→ aiotvr.xyz ──→ Nginx(TLS+WS) ──→ 浏览器
 :8081                :443
 Ktor HTTP/WS         反代 → frpc客户端端口
```

**改动**：
1. frpc.ini 新增投屏端口映射（8081→aiotvr.xyz某端口）
2. Nginx配置WebSocket反代 + TLS终止
3. 前端加Token认证
4. 选择H264 WebSocket流（非MJPEG）

**优势**：改动最小，1-2天完成
**劣势**：所有流量经服务器（阿里云1Mbps带宽 ≈ 能支撑H264低画质），无P2P

### 3.2 方案B：WebSocket中继服务器（中等难度，1周）

```
手机(Ktor) ←WebSocket→ 中继服务器(Node.js) ←WebSocket→ 浏览器
                      aiotvr.xyz:443
                     ┌──────────────┐
                     │ 视频流复用    │
                     │ API请求转发   │
                     │ Token认证    │
                     │ TLS加密      │
                     │ 多客户端广播  │
                     └──────────────┘
```

**核心设计**：
- 手机主动连接服务器（解决NAT问题，手机是WebSocket客户端）
- 服务器广播视频帧给所有浏览器观众
- API请求通过服务器中继到手机
- 单端口复用（视频/控制/API全走WSS）

**改动**：
1. 服务器端：Node.js中继服务（~500行）
2. 手机端：Ktor新增WebSocket外连能力（连接中继服务器）
3. 前端：修改连接目标为中继服务器

**优势**：手机主动外连（穿NAT）、多观众、统一入口
**劣势**：所有流量经服务器，带宽受限

### 3.3 方案C：自托管WebRTC（推荐路线，2-3周）

```
手机(libwebrtc) ←信令→ aiotvr.xyz(信令+coturn) ←信令→ 浏览器
       ↕                      ↕
       └──── WebRTC P2P ──────┘  (如果NAT允许)
       └──── TURN中继 ────────┘  (如果NAT不允许)
```

**核心设计**：
```
┌─────────────────────────────────────────────────┐
│              aiotvr.xyz 服务器                    │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ 信令服务  │  │ coturn   │  │ Web前端托管    │  │
│  │ Node.js  │  │ TURN/STUN│  │ index.html    │  │
│  │ Socket.IO│  │ UDP:3478 │  │ viewer.html   │  │
│  │ :443/ws  │  │ UDP:49152│  │ TLS:443       │  │
│  │          │  │ -65535   │  │               │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
│                                                  │
│  认证：JWT Token + 设备指纹 + 可选密码            │
│  加密：DTLS(WebRTC自带) + WSS(信令)              │
└─────────────────────────────────────────────────┘

┌──────────────┐                    ┌──────────────┐
│  Android手机  │                    │  浏览器客户端  │
│              │                    │              │
│ MediaProject │←── WebRTC P2P ────→│ <video>标签   │
│ → libwebrtc  │    (或经TURN中继)   │ 原生解码      │
│ 编码+发送    │                    │              │
│              │←── DataChannel ───→│ 触控/键盘事件  │
│ InputService │    (或HTTP API)    │ 发送控制指令   │
│ 执行操控     │                    │              │
└──────────────┘                    └──────────────┘
```

**改动**：
1. **服务器端**：
   - coturn Docker部署（TURN/STUN）
   - Node.js信令服务器（Socket.IO，替代screenstream.io）
   - JWT认证（替代Play Integrity）
   - Web前端托管
2. **手机端**：
   - 替换`WebRtcEnvironment.kt`的信令URL为自己的服务器
   - 删除`PlayIntegrity.kt`的验证逻辑，改用JWT
   - 添加libwebrtc依赖到build.gradle.kts（当前缺失！）
   - `SocketSignaling.kt`改为连接自有信令
3. **浏览器端**：
   - viewer.html：WebRTC播放+触控发送
   - 或直接复用现有index.html，增加WebRTC连接模式

**优势**：P2P直连（最低延迟）、标准WebRTC、可扩展
**劣势**：需要libwebrtc库（APK增大~10MB）、coturn需公网UDP端口

### 3.4 方案D：混合架构（终极方案，1-2月）

```
                    ┌──────────────────────────┐
                    │    aiotvr.xyz 统一网关     │
                    │                          │
浏览器 ←──WSS───→  │  ┌─────┐  ┌──────────┐  │
                    │  │信令  │  │WebSocket │  │  ←──WSS──→ 手机
                    │  │服务  │  │中继/广播  │  │
                    │  └─────┘  └──────────┘  │
                    │  ┌─────┐  ┌──────────┐  │
                    │  │coturn│  │API代理   │  │
                    │  │TURN  │  │70+端点   │  │
                    │  └─────┘  └──────────┘  │
                    └──────────────────────────┘

连接策略（自动升级）：
1. 尝试 WebRTC P2P（延迟最低）
2. P2P失败 → WebRTC TURN中继（延迟中等）
3. TURN失败 → WebSocket中继（兜底，延迟最高但最可靠）
```

**优势**：三级降级保证连通性，最优体验
**劣势**：开发量最大

---

## 四、推荐实施路径

### Phase 1：FRP直通增强（立即可做，1-2天）
> 目标：最快速让公网能看到手机屏幕+基础控制

| 步骤 | 内容 | 时间 |
|------|------|------|
| 1 | frpc.ini添加投屏端口映射（tcp:8081→aiotvr.xyz:18081） | 30min |
| 2 | Nginx配置反代+WebSocket升级+TLS | 1h |
| 3 | 前端添加Token认证（URL参数或Basic Auth） | 2h |
| 4 | 默认切换到H264编码（降低带宽） | 1h |
| 5 | 测试公网 `https://aiotvr.xyz/screen/` | 1h |

**交付物**：`https://aiotvr.xyz/screen/?token=xxx` 可看到手机画面+触控操作

### Phase 2：WebSocket中继服务器（1周）
> 目标：手机主动外连，解决所有NAT问题

| 步骤 | 内容 | 时间 |
|------|------|------|
| 1 | Node.js中继服务器（视频广播+API转发+认证） | 3天 |
| 2 | 手机端Kotlin：WebSocket外连+心跳+断线重连 | 2天 |
| 3 | 浏览器前端适配（连接中继而非直连手机） | 1天 |
| 4 | 部署到aiotvr.xyz + 测试 | 1天 |

**交付物**：手机4G/5G网络下也能通过 `https://aiotvr.xyz/screen/` 操控

### Phase 3：自托管WebRTC（2-3周）
> 目标：P2P直连，最低延迟

| 步骤 | 内容 | 时间 |
|------|------|------|
| 1 | 阿里云部署coturn Docker | 1天 |
| 2 | Node.js信令服务器（Socket.IO） | 3天 |
| 3 | 手机端：添加libwebrtc依赖+替换信令层 | 5天 |
| 4 | 浏览器端：WebRTC viewer + 触控DataChannel | 3天 |
| 5 | 集成测试+降级策略 | 2天 |

**交付物**：WebRTC P2P直连（延迟<100ms）+ TURN兜底

### Phase 4：混合架构+产品化（1-2月）
> 目标：三级降级、多用户、移动端PWA

- WebRTC P2P → TURN → WebSocket三级自动降级
- 设备管理面板（多设备注册/在线状态/连接历史）
- PWA客户端（手机控手机）
- 录屏/截屏云存储
- 权限管理（只看/可控/完全控制）

---

## 五、关键技术选型决策

### 5.1 信令服务器

| 选项 | 推荐度 | 理由 |
|------|--------|------|
| **Socket.IO (Node.js)** | ⭐⭐⭐⭐⭐ | 上游已用、生态成熟、自动重连、房间机制 |
| 原生WebSocket | ⭐⭐⭐ | 更轻量但需手写重连/房间逻辑 |
| Firebase Realtime DB | ⭐⭐ | 免费但依赖Google |
| gRPC | ⭐ | 过重 |

**决定**：Socket.IO — 可直接复用上游`SocketSignaling.kt`的事件名和协议格式

### 5.2 TURN服务器

| 选项 | 推荐度 | 理由 |
|------|--------|------|
| **coturn (Docker)** | ⭐⭐⭐⭐⭐ | 开源标准、Docker一键、配置灵活 |
| Twilio TURN | ⭐⭐⭐ | 免费额度、零维护、但依赖第三方 |
| Google STUN | ⭐⭐ | 仅STUN无TURN，对称NAT不可用 |
| Xirsys | ⭐⭐ | 免费额度少 |

**决定**：coturn Docker + Google STUN备用

### 5.3 认证方案

| 选项 | Phase 1 | Phase 2-3 | 理由 |
|------|---------|-----------|------|
| URL Token | ✅ | ❌ | 最简单但不安全（可被分享） |
| **JWT** | ❌ | ✅ | 标准、可过期、可携带权限 |
| Basic Auth | ✅ | ❌ | Nginx原生支持 |
| WebAuthn | ❌ | ❌ | 过重 |

**决定**：Phase 1 用Basic Auth，Phase 2+用JWT

### 5.4 视频编码策略

| 网络环境 | 推荐编码 | 分辨率 | 码率 | 帧率 |
|---------|---------|--------|------|------|
| WiFi/光纤 | H264 High | 1080p | 2-4 Mbps | 30fps |
| 4G | H264 Baseline | 720p | 500k-1M | 20fps |
| 3G/弱网 | H264 Baseline | 480p | 200-500k | 15fps |
| 极弱网 | MJPEG降级 | 360p | 100-200k | 5fps |

**自适应策略**：根据RTT和丢包率动态调整（WebRTC自带拥塞控制）

### 5.5 阿里云带宽评估

| 带宽 | 支持能力 | 适用 |
|------|---------|------|
| 1Mbps | 1路720p@15fps 或 2路480p | Phase 1 FRP直通 |
| 5Mbps | 1路1080p@30fps 或 3路720p | Phase 2 中继 |
| 按量付费 | 弹性，但成本高 | 峰值保障 |

**关键认知**：WebRTC P2P直连时**不消耗服务器带宽**（仅TURN中继时消耗）
→ Phase 3 WebRTC是解决带宽限制的根本方案

---

## 六、参考项目精选清单

### 6.1 必读源码

| 项目 | 重点文件 | 学什么 |
|------|---------|--------|
| [ws-scrcpy](https://github.com/NetrisTV/ws-scrcpy) | `src/server/`, `src/app/player/` | WebSocket中继+多解码器 |
| [ya-webadb](https://github.com/yume-chan/ya-webadb) | `libraries/scrcpy/` | TypeScript scrcpy协议+WebCodecs |
| [Headwind Remote](https://github.com/nicedoc/headwind-remote) | agent+server | Janus WebRTC+Android采集 |
| [web_screen](https://github.com/bbogush/web_screen) | 全部 | 最小WebRTC投屏实现 |
| [coturn](https://github.com/coturn/coturn) | Docker配置 | TURN服务器部署 |
| 上游ScreenStream | `webrtc/internal/` | 信令协议+WebRTC Android |

### 6.2 关键参考文档

| 文档 | URL | 内容 |
|------|-----|------|
| WebRTC API (MDN) | developer.mozilla.org/docs/Web/API/WebRTC_API | 浏览器端WebRTC |
| WebCodecs API | developer.mozilla.org/docs/Web/API/WebCodecs_API | H264硬解码 |
| Tango scrcpy开发指南 | tangoadb.dev/scrcpy/ | TypeScript scrcpy实现 |
| coturn WebRTC配置 | github.com/coturn/coturn/wiki | TURN服务器 |
| Socket.IO协议 | socket.io/docs/ | 信令传输 |

---

## 七、我们的独特优势（护城河）

vs 所有竞品，我们已有而他们没有的：

| 优势 | 详情 | 竞品状态 |
|------|------|---------|
| **70+ API端点** | 触控/导航/系统控制/AI Brain/宏/文件管理 | ws-scrcpy仅有触控+键盘 |
| **AccessibilityService** | 免Root、View树分析、语义化操作 | scrcpy需ADB |
| **6400行成熟前端** | 12个功能面板、手柄支持、PiP、录屏 | ws-scrcpy前端简陋 |
| **宏自动化引擎** | 触发器→条件→动作、内联执行 | 竞品均无 |
| **AI Brain** | /findclick /command /screen/text 语义操控 | 全球独有 |
| **智能家居集成** | 一个界面控手机+控家居 | 全球独有 |
| **多编码支持** | MJPEG+H264+H265+音频 | ws-scrcpy仅H264 |

**结论**：我们不需要从零造轮子，只需要补上**公网传输层**这一块拼图。

---

## 八、风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 阿里云带宽不足 | 🟡高 | 视频卡顿 | Phase 3 WebRTC P2P不消耗服务器带宽 |
| 阿里云UDP端口被封 | 🟡中 | coturn不可用 | TCP TURN兜底（性能降低） |
| libwebrtc库体积大(~10MB) | 🟢低 | APK增大 | 可接受、竞品也一样 |
| 手机电量消耗加剧 | 🟡中 | 续航缩短 | 自适应帧率+空闲休眠 |
| 中国网络环境STUN失败 | 🟡高 | P2P不可用 | 必须有TURN兜底 |
| 多人同时控制冲突 | 🟢低 | 操控混乱 | 锁定机制：同时只允许一人控制 |

---

## 九、总结：一句话路线图

```
Phase 1 (1-2天)    Phase 2 (1周)       Phase 3 (2-3周)      Phase 4 (1-2月)
FRP+Nginx直通  →  WS中继服务器    →   WebRTC P2P+TURN   →  混合降级+产品化
局域网扩展公网    手机4G也能用       延迟<100ms P2P       三级降级·多设备·PWA
                                   零服务器带宽消耗
```

**最小可行方案**：Phase 1（今天就能做到公网投屏）
**推荐目标**：Phase 3（WebRTC P2P是正确的终极方案）
**核心认知**：我们已有最强的控制层(70+ API)和最强的前端(6400行)，只缺公网传输层这一块拼图。

---

> 📁 本文档路径：`文档/PUBLIC_SCREEN_MIRROR_RESEARCH.md`
> 📅 创建：2026-02-26 | 版本：v1.0
> 🔗 相关：`核心架构.md` | `文档/VISION.md` | `文档/ARCHITECTURE_v32.md`
