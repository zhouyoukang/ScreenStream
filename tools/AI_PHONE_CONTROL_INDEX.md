# AI 操作手机 — 统一索引

> ScreenStream HTTP API 40+ 端点，通过 AccessibilityService 实现手机反向控制。

## 连接

```powershell
adb devices
adb forward tcp:8086 tcp:8086
curl -s http://127.0.0.1:8086/status   # → {"connected":true,"inputEnabled":true}
```

端口范围 8080-8099，实际端口取决于 ScreenStream 启动时分配。

## API 速查

### 感知（只读）
| 端点 | 方法 | 说明 |
|------|------|------|
| `/status` | GET | 连接状态 |
| `/deviceinfo` | GET | 设备完整信息 |
| `/foreground` | GET | 前台APP包名 |
| `/screen/text` | GET | 屏幕文本+可点击元素 |
| `/viewtree?depth=N` | GET | View树结构 |
| `/windowinfo` | GET | 窗口包名+节点数 |
| `/notifications/read?limit=N` | GET | 通知列表 |
| `/apps` | GET | 已安装APP列表 |
| `/clipboard` | GET | 剪贴板内容 |
| `/wait?text=X&timeout=T` | GET | 等待文本出现 |

### 操控
| 端点 | 方法 | 说明 |
|------|------|------|
| `/findclick` | POST | 语义查找并点击 `{"text":"X"}` |
| `/findnodes` | POST | 节点搜索 |
| `/tap` | POST | 坐标点击 `{"nx":0.5,"ny":0.5}` |
| `/text` | POST | 输入文本 `{"text":"X"}` |
| `/settext` | POST | 设置输入框 `{"search":"X","value":"Y"}` |
| `/intent` | POST | 发送Intent `{"action":"X","data":"Y"}` |
| `/command` | POST | 自然语言命令 `{"command":"X"}` |
| `/dismiss` | POST | 关闭弹窗 |

### 导航
`POST /home` | `POST /back` | `POST /recents` | `POST /notifications`

### 系统控制
| 端点 | 方法 | 说明 |
|------|------|------|
| `/volume` | POST | 音量控制 |
| `/brightness/N` | POST | 亮度 |
| `/wake` | POST | 唤醒屏幕 |
| `/screenshot` | POST | 截屏 |
| `/flashlight/bool` | POST | 手电筒 |
| `/stayawake/bool` | POST | 保持唤醒 |

### 文件管理
`GET /files/storage` | `GET /files/list?path=X` | `POST /files/mkdir` | `POST /files/delete` 等12端点

### 宏系统
`GET /macro/list` | `POST /macro/create` | `POST /macro/run` 等11端点

## tools/ 目录

| 模块 | 说明 |
|------|------|
| `screen-capture-bridge/` | FFmpeg并行录屏+分段监控，让AI处理录屏文件 |
| `vision-bridge/` | 视频帧HTTP桥接(port 9902)+Agent监控面板 |
| `github-mcp.cmd` | GitHub MCP Server wrapper |

## 后端源码

| 文件 | 说明 |
|------|------|
| `040-反向控制_Input/010-输入路由_Routes/InputRoutes.kt` | 40+个API路由定义 |
| `040-反向控制_Input/020-输入服务_Service/InputService.kt` | 核心服务实现 |
| `040-反向控制_Input/040-宏系统_Macro/MacroEngine.kt` | 宏引擎 |

## 经验要点

- **findByText 100%成功率**（同时搜索 text + contentDescription）
- **OPPO/OnePlus Intent 被系统拦截** → 用 monkey 或 /command 绕过
- **ADB+API混合** 是最优模式（最小化屏幕依赖）
- **通知监控** 是零依赖的高价值通道

## 归档

Phone Agent 设计蓝图（soul/execution-engine/deploy等27项）已归档至 `管理/00-归档/agent-phone-soul/`.
