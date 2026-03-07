# Desktop Browser Bridge — 桌面应用浏览器化

> 道生一(捕获) → 一生二(编码+传输) → 二生三(渲染+输入+感知) → 三生万物(完全替代用户操作)

## 架构

```
Desktop App (VaM/Unity/Any)
    ↓ mss screen capture (16ms/frame, multi-monitor)
    ↓ JPEG encode (OpenCV, quality configurable)
    ↓ WebSocket broadcast (threading.Lock shared buffer)
Browser (HTML5 Canvas)
    ↓ Playwright can see + interact
    ↓ Mouse/keyboard events → WebSocket → SendInput API
Desktop App receives input
```

## 八卦映射

| 卦 | 模块 | 职责 |
|----|------|------|
| ☰乾 | CaptureEngine | 视觉捕获 — mss screen grab |
| ☷坤 | InputEngine | 输入注入 — Win32 SendInput |
| ☵坎 | WebSocket | 传输通道 — 帧推送 + 事件接收 |
| ☲离 | JPEG Encoder | 编码 — OpenCV imencode |
| ☳震 | Canvas Renderer | 浏览器渲染 — requestAnimationFrame |
| ☴巽 | DesktopAgent | AI感知 — OCR + Playwright |
| ☶艮 | Server State | 状态管理 — FPS/Quality/Target |
| ☱兑 | Multi-Client | 多客户端协同 — Set broadcast |

## 快速开始

```bash
# 安装依赖
pip install fastapi uvicorn[standard] mss opencv-python numpy playwright rapidocr-onnxruntime
python -m playwright install chromium

# 启动服务 (自动检测VaM窗口)
python -m browser_bridge.server --port 9870 --fps 15 --quality 70

# 浏览器打开
# http://localhost:9870
```

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web客户端 |
| `/ws` | WS | 帧流(binary) + 输入事件(JSON) |
| `/api/status` | GET | 服务状态 |
| `/api/screenshot` | GET | 单帧JPEG截图 |
| `/api/windows` | GET | 枚举可见窗口 |
| `/api/target` | POST | 设置目标窗口 `{hwnd/title/class}` |
| `/api/config` | POST | 配置 `{fps, quality}` |
| `/api/input` | POST | REST输入注入(备用) |

## Playwright Agent

```python
from browser_bridge.playwright_agent import DesktopAgent

agent = DesktopAgent("http://localhost:9870")
await agent.connect()

# OCR扫描
texts = await agent.ocr_scan()

# 点击文字
await agent.click_text("编辑模式")

# 键盘操作
await agent.press_key("Tab")
await agent.press_key("Control+z")

# 拖拽 (相对坐标 0-1)
await agent.drag(0.3, 0.5, 0.7, 0.5)

# 等待文字出现
result = await agent.wait_for_text("加载完成", timeout=30)

await agent.close()
```

## 关键技术决策

1. **mss > dxcam** — dxcam不支持负坐标(多显示器副屏), mss原生支持
2. **threading.Thread > asyncio.Task** — uvicorn不调度startup中创建的asyncio task
3. **共享帧缓冲** — capture线程写入 `_latest_jpeg`, WebSocket sender读取, threading.Lock保护
4. **BGRA→BGR** — mss返回BGRA (`shot.bgra`), OpenCV需要BGR, 切片`[:,:,:3]`

## 性能

| 指标 | 值 |
|------|-----|
| 捕获延迟 | ~16ms (mss) |
| JPEG编码 | ~10ms (1298×1377 @ q70) |
| 帧大小 | ~83KB |
| 端到端延迟 | ~100ms |
| 目标FPS | 15 (可调1-60) |

## 文件

- `server.py` — FastAPI服务器 + 捕获线程 + 输入注入
- `static/index.html` — Web客户端 (Canvas + 输入捕获 + HUD)
- `playwright_agent.py` — Playwright自动化Agent + OCR
- `test_e2e.py` — 全链路E2E测试
