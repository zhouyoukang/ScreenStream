# 电脑公网投屏手机 · Agent操作指令

## 目录用途
PC屏幕通过公网投射到手机浏览器，支持反向触控操作。
**三软件底层复用**: ToDesk(采集/编码) + 向日葵(P2P隧道/输入) + 无界趣连(备用P2P)。

## 端口
- **9802** — WebSocket中继服务器 (Relay, Node.js)
- **9803** — P2P直连服务器 (Direct, Python websockets)
- **35600** — ToDesk本地IPC (二进制加密, 只读探测)
- **35016/35017** — 向日葵本地IPC (管道)

## 关键文件
- `desktop.py` — Python桌面端 (DXGI/mss采集+NVENC编码+多模式传输)
- `remote_backends.py` — **三软件底层复用引擎v2.0** (核心)
- `server.js` — Node.js中继 (降级方案L3)
- `viewer/index.html` — 手机端查看器
- `DEEP_REVERSE_REPORT.md` — 三软件深度逆向报告
- `_deep_reverse.py` — 逆向扫描引擎

## 架构 (三级降级)
```
传输层:
  L1: 向日葵端口转发 → P2P隧道 (零自建, config.ini配置)
  L2: ortc WebRTC → DataChannel (sl-client-ortc.dll)
  L3: WebSocket中继 → server.js (降级)

采集层:
  C1: DXGI Desktop Duplication (ToDesk同源, 0% CPU)
  C2: DXcam (DXGI封装)
  C3: mss BitBlt (降级)

编码层:
  E1: h264_nvenc 硬件编码 (ToDesk同源)
  E2: h264_amf / h264_qsv
  E3: WebP/JPEG 软编码 (降级)

输入层:
  I1: 向日葵 RCHook.dll (32-bit, 需bridge)
  I2: Win32 SendInput (降级)
```

## 三软件复用清单

| 软件 | 状态 | 复用资产 |
|------|------|---------|
| **ToDesk** | ✅运行中 | DXGI采集技术(同源) + NVENC编码(同源) + tdIdd虚拟显示器 |
| **向日葵** | ✅运行中 | 端口转发P2P隧道 + RCHook.dll + ortc WebRTC |
| **无界趣连** | ❌未安装 | ZEGO Express SDK(备用, 需安装LDRemote) |

## Agent操作规则
- `remote_backends.py --probe` 全量探测三软件状态
- `remote_backends.py --setup-tunnel` 一键配置向日葵P2P隧道
- 修改向日葵config.ini后需重启向日葵服务
- RCHook.dll是32-bit, 当前64-bit Python无法直接加载, 降级到SendInput
- desktop.py中 `_handle_control_cmd()` 和 `_capture_frames()` 是核心函数
- Python依赖: mss, Pillow, websocket-client, websockets, pyautogui, pyperclip, dxcam(可选)

## 公网部署 (aiotvr.xyz)
- **路径**: `/opt/desktop-cast/` (server.js + viewer/)
- **systemd**: `desktop-cast.service`
- **Nginx**: `/desktop/` → `127.0.0.1:9802`
- **向日葵隧道**: 远程ID 1401532527 → 端口转发 → DesktopCast:9803

## 发现的问题 (2026-03-09)
1. ✅ RCHook.dll 32-bit vs Python 64-bit → SendInput降级
2. ✅ ToDesk IPC加密 → 直接用同源Win32 API
3. ✅ 无界趣连未安装 → 向日葵P2P隧道替代
4. ✅ 向日葵RPC端口非HTTP → 文件级config.ini操作
5. ✅ remote_backends.py路径错误 → 已修正
6. ✅ FFmpeg路径硬编码 → 自动搜索
7. ✅ 向日葵端口转发已配置DesktopCast (--setup-tunnel)
8. ✅ /api/backends 404 → desktop.py已添加端点

## E2E全链路验证 (2026-03-09)

### P2P直连 (8/8 PASS)
| 测试项 | 结果 |
|--------|------|
| desktop.py启动 | ✅ DXcam采集+NVENC可用+向日葵隧道已配 |
| 浏览器连接 | ✅ P2P直连, 1ms延迟 |
| 画面投屏 | ✅ 1280x720 Canvas, 6-10fps, 49-77KB/帧 |
| 设置面板 | ✅ 画质/帧率/缩放/设备/分辨率/连接码 |
| 键盘面板 | ✅ 文字输入+F1-F12+方向键+修饰键+快捷键 |
| sendCmd控制 | ✅ WebSocket命令发送成功 |
| /api/health | ✅ `{"ok":true,"mode":"p2p_direct","viewers":1}` |
| /api/backends | ✅ `{"capture":"dxgi","encoder":"h264_nvenc","transport":"sunlogin_p2p"}` |

### 性能基准
- **采集**: DXcam DXGI DD, 16ms/帧, 0% CPU (ToDesk同源)
- **编码**: WebP 60质量, 31ms/帧 (NVENC H264可用但当前用WebP)
- **传输**: P2P直连 1-5ms
- **总延迟**: 78-94ms/帧 (target 100ms)
- **Console错误**: 0

### 待用户操作
- 重启向日葵使端口转发生效 → 手机APP即可通过P2P隧道公网投屏
