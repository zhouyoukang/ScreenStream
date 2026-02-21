# ScreenStream v32 融合架构设计

> 版本：v32 (AI Brain) | 日期：2026-02-13
> 参考：KNOOP 三层架构理念 + trah RustDesk 建议 + 项目实践

## 一、三层架构

```
┌──────────────────────────────────────────────┐
│  Layer 3: AI 决策引擎 (AI Brain)              │  ← 未来：语义化控制、自动化操作
│  View 树分析 + 节点查找 + 智能关闭弹窗         │
├──────────────────────────────────────────────┤
│  Layer 2: 标准化接口层 (API + WebSocket)       │  ← 现在：70+ REST端点 + WS触控流
│  HTTP API / WebSocket / 前端 UI               │
├──────────────────────────────────────────────┤
│  Layer 1: 系统控制层 (AccessibilityService)    │  ← 现在：免Root合法Hook
│  触控注入 / 全局操作 / View树遍历 / 事件拦截   │
├──────────────────────────────────────────────┤
│  Layer 0: Android 宿主                        │  ← 普通 APK 安装
└──────────────────────────────────────────────┘
```

## 二、模块映射

| Gradle 模块 | 目录 | 端口 | 职责 |
|------------|------|------|------|
| `:app` | `010-用户界面与交互_UI` | - | 主应用 UI |
| `:mjpeg` | `020-投屏链路_Streaming/010-MJPEG投屏_MJPEG` | 8081 | MJPEG 流 + 前端 + Input路由挂载 |
| `:rtsp` | `020-投屏链路_Streaming/020-RTSP投屏_RTSP` | 8082 | RTSP 流 |
| `:webrtc` | `020-投屏链路_Streaming/030-WebRTC投屏_WebRTC` | 8083 | WebRTC P2P 流 |
| `:input` | `040-反向控制_Input` | 8084 | 输入控制 + AI Brain |
| `:common` | `070-基础设施_Infrastructure` | - | 公共组件 |
| Gateway | (MacroDroid) | 8080 | 网关路由 |

## 三、API 端点清单 (70+ 端点)

### 基础控制 (v30)
| 端点 | 方法 | 说明 |
|------|------|------|
| `/status` | GET | 服务状态 |
| `/pointer` | POST | 鼠标/触控事件 |
| `/tap` | POST | 归一化点击 |
| `/swipe` | POST | 归一化滑动 |
| `/text` | POST | 文字输入 |
| `/key` | POST | 按键事件 |
| `/home` | POST | Home 键 |
| `/back` | POST | 返回键 |
| `/recents` | POST | 最近任务 |
| `/notifications` | POST | 通知栏 |
| `/quicksettings` | POST | 快捷设置 |
| `/lock` | POST | 锁屏 |
| `/volume/up` `/volume/down` | POST | 音量控制 |

### 远程协助 (v31)
| 端点 | 方法 | 说明 |
|------|------|------|
| `/wake` | POST | 唤醒屏幕 |
| `/power` | POST | 电源菜单 |
| `/screenshot` | POST | 截屏 |
| `/splitscreen` | POST | 分屏 |
| `/brightness` `/brightness/{level}` | GET/POST | 亮度控制 |
| `/longpress` | POST | 长按 |
| `/doubletap` | POST | 双击 |
| `/scroll` | POST | 四方向滚动 |
| `/pinch` | POST | 捏合缩放 |
| `/openapp` | POST | 打开应用 |
| `/openurl` | POST | 打开链接 |
| `/deviceinfo` | GET | 设备信息 |
| `/apps` | GET | 已安装应用 |
| `/clipboard` | GET | 剪贴板内容 |

### AI Brain 层 (v32)
| 端点 | 方法 | 说明 |
|------|------|------|
| `/viewtree` | GET | View 树 JSON（可控深度） |
| `/windowinfo` | GET | 当前窗口信息 |
| `/findclick` | POST | 按文本/ID查找并点击 |
| `/dismiss` | POST | 智能关闭弹窗 |
| `/findnodes` | POST | 搜索节点 |
| `/settext` | POST | 设置文本内容 |
| `/ws/touch` | WebSocket | 实时触控流（1:1镜像） |

## 四、前端查看器模块化

| 查看端 | 优化重点 | 状态 |
|--------|---------|------|
| **PC 浏览器** | 键盘快捷键 + 鼠标操作 + 导航栏 | ✅ 已完成 |
| **手机浏览器** | 全屏沉浸 + WebSocket触控 + 手势导航 | ✅ v32 新增 |
| **VR 浏览器** | 16:9 裁剪 + 手柄映射 | ✅ 已完成 |

## 五、传输协议对比

| 协议 | 带宽需求 | 延迟 | 适用场景 |
|------|---------|------|---------|
| MJPEG | 5-15 Mbps | 低 | 局域网 |
| WebRTC H.264 | 0.5-2 Mbps | 低 | 局域网 / WAN |
| WebRTC H.265 | 0.3-1 Mbps | 低 | WAN / FRP |

## 六、远程方案路线

### 短期（零开发）
```
[查看端] ── FRP/ToDesk ──→ [被控手机 WebRTC 模式]
```
切换到 WebRTC 模式即可解决 FRP 卡顿问题。

### 中期（Web UI 优化）
- 手机端查看器已在 v32 实现
- WebSocket 实时触控流已实现
- 下一步：完善手势导航映射（底部上滑=Home，侧边滑=Back）

### 长期（独立查看端 APP）
- Android 原生查看端应用
- WebRTC P2P 直连
- STUN/TURN NAT 穿透
- 多指原生触控透传

## 七、与 KNOOP 建议的对照

| KNOOP 建议 | 我们的实现 | 差异 |
|-----------|----------|------|
| ptrace/LD_PRELOAD 注入 | AccessibilityService | 我们用合法API，不需要Root |
| 太极沙箱 | 不需要 | 目标APP正常运行，不需要沙箱 |
| AI → View树 → Hook show | AI → View树 → ACTION_DISMISS | 效果相同，方式更安全 |
| 语义化控制 | /findclick + /dismiss | ✅ 已实现 |
| 三层架构 | 宿主+API+AI Brain | ✅ 已实现 |

## 八、安全模型

- 所有控制通过 AccessibilityService（系统级权限，用户显式授权）
- HTTP API 仅局域网暴露（默认绑定设备 IP）
- PIN 码保护（MJPEG HttpServer）
- 无 Root、无注入、无沙箱 — 完全合规
