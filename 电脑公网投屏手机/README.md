# 电脑公网投屏手机 — Desktop Cast v2.3

通过公网或局域网将电脑屏幕投射到手机浏览器，支持反向操控。

## 架构

支持两种模式：

```
┌─── P2P 直连模式 (局域网，零延迟) ───┐
│ PC (desktop.py --direct)            │
│   内置HTTP+WS服务器                  │
│   手机直连，无需中继                  │
│ Phone ──WebSocket──→ PC:9803        │
└─────────────────────────────────────┘

┌─── 中继模式 (公网，跨网段) ──────────┐
│ PC ──WS──→ Relay (server.js) ──WS──→ Phone │
│  屏幕采集    帧中继+房间管理    触控/键盘   │
└─────────────────────────────────────┘
```

## 快速启动

### 方式一：P2P 直连 (推荐局域网)

```bash
pip install -r requirements.txt

# 启动P2P直连 (手机与电脑需在同一WiFi)
python desktop.py --direct

# 自定义端口和参数
python desktop.py --direct --port 9803 --fps 15 --quality 70 --scale 60
```

手机浏览器打开终端显示的地址 (如 `http://192.168.x.x:9803/`)，自动连接，无需连接码。

### 方式二：中继模式 (公网)

```bash
# 1. 启动中继服务器
npm install && node server.js

# 2. 启动桌面端
python desktop.py                                    # 连接本地中继
python desktop.py --relay wss://aiotvr.xyz/desktop/  # 连接公网中继
python desktop.py --fps 15 --quality 70 --room MYCODE
```

手机浏览器访问:
- 本地: `http://电脑IP:9802/`
- 公网: `https://aiotvr.xyz/desktop/`

输入电脑上显示的连接码即可。

## 功能

| 功能 | 说明 |
|------|------|
| 屏幕投射 | JPEG帧流，可调画质/帧率/缩放 |
| 点击 | 单击触屏 = 鼠标左键 |
| 双击 | 快速双击触屏 |
| 右键 | 长按触屏 或 右键模式按钮 |
| 滚动 | 双指滑动 或 单指短滑 |
| 拖拽 | 单指长滑 |
| 键盘 | 虚拟键盘面板 + 文字输入 |
| 快捷键 | Ctrl/Alt/Shift修饰键 + 常用快捷键按钮 |
| 远程设置 | 手机端实时调整画质/帧率/缩放 |
| 自动重连 | 断线指数退避重连 |
| 全屏 | 手机全屏模式 |

## 参数

### desktop.py

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--direct` | - | P2P直连模式（内置服务器，无需中继） |
| `--port` | 9803 | P2P直连端口 |
| `--relay` | `wss://aiotvr.xyz/desktop/` | 中继服务器地址 |
| `--token` | `desktop_cast_2026` | 认证Token |
| `--room` | 自动生成 | 房间连接码 |
| `--fps` | 10 | 目标帧率 (1-30) |
| `--quality` | 60 | JPEG质量 (10-100) |
| `--scale` | 50 | 缩放比例% (10-100) |
| `--monitor` | 1 | 显示器索引 |

### server.js 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | 9802 | 监听端口 |
| `RELAY_TOKEN` | `desktop_cast_2026` | 认证Token |
| `MAX_VIEWERS` | 5 | 每房间最大观众数 |

## 部署到公网 (aiotvr.xyz)

```bash
bash deploy.sh
```

需要 Nginx 反代配置:
```nginx
location /desktop/ {
    proxy_pass http://127.0.0.1:9802/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400;
}
```

## 技术精华来源

| 来源项目 | 提取内容 |
|----------|----------|
| 远程桌面/remote_agent.py | 屏幕采集(mss/GDI)、pyautogui控制、MouseGuard |
| 公网投屏/relay-server | Room类、背压控制、二进制帧中继 |
| 公网投屏/signaling | 房间模型、心跳检测 |
| 公网投屏/cast/index.html | 移动端UI、触控手势、控制栏设计 |
| 远程桌面/remote_desktop.html | 坐标映射、快捷键面板、拖拽支持 |
| 亲情远程/viewer | P2P降级策略、重连机制、画质徽章 |
| 投屏链路/公网投屏 | Socket.IO协议、TURN支持、ICE配置 |

## 端口

- **9802**: 中继服务器 (Relay)
- **9803**: P2P直连服务器 (Direct)
