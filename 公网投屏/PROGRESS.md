# P2P远程协助投屏 — 进度记录

> 唯一目的：让远方家人打开网页即可看到并操控老人手机屏幕，P2P直连，不经服务器中转。

## 已完成 ✅

### 1. 技术路径对比（10条路径）
- 文件：`公网投屏/技术路径对比.md`
- 结论：**原生WebRTC + CloudRelay三级降级**
- 淘汰：scrcpy(需ADB)、Miracast(仅局域网)、云手机(非真实手机)、Tailscale(配置复杂)、浏览器PeerJS(Chrome后台节流)

### 2. 五感代入审计（33个摩擦点）
- 文件：`公网投屏/五感代入审计.md`
- 15个致命 + 15个高 + 3个低
- 核心洞察：技术不是问题，恐惧才是

### 3. 信令服务器部署
- URL：`https://aiotvr.xyz/signal/`
- 验证：`curl https://aiotvr.xyz/signal/api/status` → `{"ok":true}`
- systemd服务：`p2p-signaling.service` (enabled, active)
- Nginx反代：`/signal/` → `127.0.0.1:9801` (WebSocket升级支持)

### 4. 原生WebRTC P2P客户端
- 文件：`投屏链路/MJPEG投屏/mjpeg/internal/WebRtcP2PClient.kt`
- 编译：✅ BUILD SUCCESSFUL
- 依赖：`stream-webrtc-android:1.2.2` 已加入MJPEG模块
- 功能：PeerConnection + 信令 + DataChannel控制 + ICE(STUN+TURN) + 自动重连

### 5. MJPEG WS端点
- HttpServer.kt新增：`/stream/mjpeg` WebSocket端点
- 验证：Python客户端收到29861字节JPEG帧 type=3 ✅
- bridge.html集成到APP assets + `/bridge`路由

### 6. PeerJS浏览器桥接验证（已证明不可行）
- P2P DataChannel建立 ✅ (8fps 1080×2412)
- 致命缺陷：Chrome后台节流 + 屏幕捕获反馈环 = 架构级死锁
- Memory已记录，避免未来重复踩坑

### 7. 公网远程ADB v2.0 (2026-03-04)
- **架构**：网页 ←WebSocket→ 信令服务器 ←WebSocket→ ADB Bridge(PC+USB手机)
- **信令升级**：`signaling/server.js` 新增 `adb-bridge`/`adb-controller` 角色 + `adbRooms` 中继
- **Bridge升级**：`cast/adb-bridge.py` v2.0 双模式(本地HTTP + 公网WebSocket)
- **网页面板**：`cast/setup.html` 新增公网ADB面板(① 下载 → ② 输入码 → ③ 一键配置)
- **一键启动器**：`cast/start-adb-bridge.bat` 用户双击即运行，零手动配置
- **E2E验证**：11条命令全链路中继 PASS + 3项UX验证 PASS
- **UX优化**：0设备禁用按钮+FAQ+错误提示优化
- **部署**：信令服务器 + cast页面 + 启动器 全部部署到 aiotvr.xyz
- **清理**：59张截图 + 6个测试文件已删除

### 8. 配置中心 setup.html 完整功能
- **7步向导**：健康检查→安装→权限→网络→设置→投屏→诊断
- **本地ADB**：自动检测 localhost:8085 bridge
- **公网ADB**：WebSocket中继，6位连接码，一键远程配置
- **下载入口**：start-adb-bridge.bat + adb-bridge.py 直接下载
- **URL参数**：`?room=X` 预填房间码 / `?adb=X` 预填连接码并自动连接

## 进行中 🔧

### Phase 1b: 集成WebRtcP2PClient到MjpegStreamingService
**阻塞**：Android 14+ 单MediaProjection限制
- ScreenCapturerAndroid会创建新的MediaProjection，与现有BitmapCapture冲突
- **解决方案**：修改WebRtcP2PClient，从bitmapStateFlow喂帧到自定义VideoSource
  - 不用ScreenCapturerAndroid，避免MediaProjection冲突
  - Bitmap → I420Buffer → VideoFrame → VideoSource → VideoTrack → PeerConnection
  - 或使用VideoSource.adaptOutputFormat() + CapturerObserver手动喂帧

### Phase 1c: WebRTC Viewer页面
- 需要创建接收WebRTC MediaStream的viewer（不同于DataChannel帧的viewer）
- `<video>` 标签直接播放MediaStream
- DataChannel发送触控命令

## 待做 📋

| Phase | 内容 | 预估 |
|-------|------|------|
| 1b | WebRtcP2PClient集成(bitmapStateFlow喂帧) | 3-4小时 |
| 1c | WebRTC viewer页面 | 1小时 |
| 2 | 构建APK + 端到端P2P验证 | 1小时 |
| 3 | 三级降级 + 无障碍引导 + 品牌适配 | 3-4小时 |
| 4 | 双品牌实测(OnePlus+OPPO) + 4G公网 | 2小时 |

## 关键文件索引

| 文件 | 说明 |
|------|------|
| `公网投屏/技术路径对比.md` | 10条路径对比矩阵 |
| `公网投屏/五感代入审计.md` | 33个中老年摩擦点 |
| `公网投屏/signaling/server.js` | P2P信令服务器(仅SDP/ICE，不中转媒体) |
| `投屏链路/MJPEG投屏/mjpeg/internal/WebRtcP2PClient.kt` | 原生WebRTC P2P客户端核心 |
| `投屏链路/MJPEG投屏/mjpeg/internal/HttpServer.kt` | +/stream/mjpeg WS + /bridge路由 |
| `投屏链路/MJPEG投屏/assets/bridge.html` | P2P桥接页(已证明不可行) |
| `公网投屏/cast-viewer.html` | P2P观看页(DataChannel模式) |
| `公网投屏/viewer/index.html` | 统一观看页(relay模式) |
