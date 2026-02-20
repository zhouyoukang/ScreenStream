# AI Vision Bridge v2.0 — Command Center

## 核心问题
传统视频录制 = 文件被进程锁定 → AI Agent 无法同时消费视频流
多Agent协作 = Agent之间信息不透明 → 用户焦虑(不可观测性)

## v2 架构
```
[摄像头/屏幕] → [浏览器捕获] → [分流器]
                                  ├→ 路1: MediaRecorder → .webm (B站素材)
                                  └→ 路2: Canvas → HTTP POST → server.py
                                                                  ↓
                                              ┌─────────────────────────────┐
                                              │  server.py (port 9902)      │
                                              │  GET /api/frame/latest      │ ← 任何Agent
                                              │  GET /api/frame/latest.jpg  │ ← AI Vision API
                                              │  GET /api/agents            │ ← 可观测性
                                              │  POST /api/agent/heartbeat  │ ← Agent注册
                                              └─────────────────────────────┘
```

## 文件说明
| 文件 | 用途 |
|------|------|
| `server.py` | HTTP Bridge Server — 帧API + Agent注册 + cunzhi代理 |
| `index.html` | Command Center — 视频+录制+桥接+Agent监控+焦虑指标 |
| `agent-observer.html` | 独立Agent Observer (localStorage版, 向后兼容) |

## 快速开始
```bash
# 1. 启动服务器
python tools/vision-bridge/server.py

# 2. 浏览器访问
http://localhost:9902

# 3. 选择视频源 → 开始录制 → 启动桥接
# 或直接 Alt+A 全自动模式
```

## Agent 消费帧 (HTTP — 跨进程)
```python
# Python Agent
import requests
frame = requests.get("http://localhost:9902/api/frame/latest").json()
# frame["dataUrl"] = data:image/jpeg;base64,...
# frame["age_seconds"] = 帧年龄

# 或直接获取 JPEG
img = requests.get("http://localhost:9902/api/frame/latest.jpg").content
```

```bash
# curl
curl http://localhost:9902/api/frame/latest.jpg -o frame.jpg
```

## Agent 心跳 (跨进程可观测性)
```python
requests.post("http://localhost:9902/api/agent/heartbeat", json={
    "name": "Agent-A",
    "role": "developer",
    "task": "实现新功能",
    "status": "working",
    "message": "Phase 3 完成, 开始编译"
})
```

## API 端点
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/status` | 服务器健康+统计 |
| POST | `/api/frame` | 接收帧(浏览器→服务器) |
| GET | `/api/frame/latest` | 最新帧(JSON+base64) |
| GET | `/api/frame/latest.jpg` | 最新帧(原始JPEG) |
| POST | `/api/agent/heartbeat` | Agent心跳注册 |
| GET | `/api/agents` | 所有Agent状态 |
| GET | `/api/cunzhi` | 代理cunzhi状态(9901) |

## 快捷键
| 快捷键 | 功能 |
|--------|------|
| Alt+A | 全自动(屏幕+录制+桥接) |
| Alt+1/2/3 | 摄像头/屏幕/双路 |
| Alt+R | 开始/停止录制 |
| Alt+E | 启动/停止桥接 |
| Alt+P | 画中画(PiP) |
| Esc | 停止桥接 |

## 焦虑指标
| 时间 | 状态 | 颜色 |
|------|------|------|
| < 30s | 平静 | 绿色 |
| 30s-2min | 关注 | 黄色 |
| 2-5min | 焦虑 | 橙色 |
| > 5min | 需干预 | 红色 |

## 与 "AI+人=AGI" 视频的关系
这个工具本身就是 AI+人协作的实证:
- 人负责创作内容(录视频)
- AI实时观察并提供反馈(消费帧流)
- 多Agent状态透明可观测(消除焦虑)
- 两者同时工作,互不阻塞
- 这个工具的开发过程本身就是视频内容
