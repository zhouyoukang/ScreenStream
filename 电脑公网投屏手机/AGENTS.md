# AGENTS.md — 电脑公网投屏手机

## 目录用途
PC屏幕通过公网WebSocket投射到手机浏览器，支持反向触控操作。
双模式: Relay(公网中继) + P2P Direct(局域网直连)。

## 端口
- **9802** — WebSocket中继服务器 (Relay, Node.js)
- **9803** — P2P直连服务器 (Direct, Python websockets)

## 关键文件
- `server.js` — Node.js中继 (房间管理+帧转发+WebRTC信令)
- `desktop.py` — Python桌面端 (mss采集+pyautogui控制+P2P直连服务)
- `viewer/index.html` — 手机端查看器 (Canvas+触控+虚拟键盘)

## 架构
```
Mode 1 (Relay):   Desktop ──WS──→ server.js ──WS──→ Phone Browser
Mode 2 (Direct):  Desktop ──WS──→ (built-in) ──WS──→ Phone Browser
```

## Agent操作规则
- 修改server.js后需重启node进程
- 修改desktop.py后需重启python进程
- viewer是纯静态HTML，修改后刷新即可
- Token默认 `desktop_cast_2026`，修改需同步server.js和desktop.py
- desktop.py中 `_handle_control_cmd()` 和 `_capture_frames()` 是两个Provider共享的核心函数
- Python依赖: mss, Pillow, websocket-client, websockets, pyautogui, pyperclip

## 公网部署 (aiotvr.xyz)
- **路径**: `/opt/desktop-cast/` (server.js + viewer/)
- **systemd**: `desktop-cast.service` (Restart=always, RestartSec=3)
- **Nginx**: `/desktop/` → `127.0.0.1:9802` (WebSocket upgrade)
- **日志**: `/var/log/desktop-cast.log`
- **部署**: `bash deploy.sh` 或手动 `scp + systemctl restart desktop-cast`

## E2E验证记录 (2026-03-06 v2.3)

### P2P直连
- OPPO PEAM00 WiFi LAN → 192.168.31.141:9803 ✅
- LDPlayer emulator-5560 adb reverse → 127.0.0.1:9803 ✅
- 帧流: 111KB WebP, 1080x1920, skip 4%
- HTTP: / ✅ /manifest.json ✅ /api/health ✅ /api/info ✅

### Relay公网
- desktop.py → wss://aiotvr.xyz/desktop/ → Room:BA4530 ✅
- 帧流: 111KB WebP, 1080x1920, skip 2%
- 公网HTTP: /desktop/ ✅ /desktop/manifest.json ✅

### 修复
- 累计21个Bug修复 (v2.1→v2.3.3)
- 本轮: 服务器v2.0→v2.3升级 + EADDRINUSE崩溃循环修复
