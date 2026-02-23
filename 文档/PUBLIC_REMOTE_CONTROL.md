# 公网远程控制指南

> **一个网页，完整控制手机** — 视觉、听觉、触觉、认知、管控，五感齐全。

## 架构概览

```
远程用户浏览器 ──HTTPS──→ Cloudflare Tunnel / FRP ──→ 手机 ScreenStream (port 8081)
     │                                                      │
     ├── 画面流 (MJPEG/H264/H265 WebSocket)                │
     ├── 音频流 (/stream/audio WebSocket)                    │
     ├── 触控输入 (/ws/touch WebSocket)                      │
     ├── 70+ REST API (导航/输入/设备控制/文件/宏/AI)         │
     └── Bearer Token 认证 (所有请求自动附带)                 │
```

## 快速开始（3步）

### 1. 生成认证令牌

**方式A：手机设置界面（推荐）**
- 打开 ScreenStream → 反向控制设置 → Remote Access → 打开开关
- 自动生成 32 位安全令牌（SecureRandom），可复制/重新生成

**方式B：HTTP API**
```bash
adb forward tcp:8081 tcp:8081
curl -X POST http://localhost:8081/auth/generate
# 返回: {"ok":true,"token":"aBcDeFgH...32chars..."}
```

### 2. 启动公网隧道

**方式A：Cloudflare Quick Tunnel（最简单，免注册）**
```powershell
# 安装 cloudflared
winget install Cloudflare.cloudflared

# 一键启动（会输出公网 URL）
cloudflared tunnel --url http://localhost:8081

# 或使用脚本
.\构建部署\remote-tunnel-setup.ps1 -Mode quick -LocalPort 8081 -GenerateToken
```

**方式B：FRP（自建服务器）**
```powershell
.\构建部署\remote-tunnel-setup.ps1 -Mode frp -FrpServer your-server.com -LocalPort 8081
```

### 3. 分享给远程用户

将隧道 URL + 令牌分享给远程用户：
```
https://xxxx-xxxx.trycloudflare.com/?auth=aBcDeFgH12345678
```

远程用户打开链接即可直接使用，令牌会自动保存到浏览器。

## 认证系统

### API 端点

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/auth/info` | GET | 否 | 查询是否启用认证 |
| `/auth/verify` | POST | 否 | 验证令牌 `{"token":"xxx"}` |
| `/auth/generate` | POST | **是** | 生成新随机令牌 |
| `/auth/revoke` | POST | **是** | 撤销令牌（关闭认证） |

### 认证流程

1. 页面加载 → 检查 `/auth/info`
2. 如果 `authEnabled=true`：
   - 检查 URL 参数 `?auth=xxx` 或 localStorage 中的 token
   - 调用 `/auth/verify` 验证
   - 有效 → 隐藏认证门，正常使用
   - 无效/无 token → 显示认证门，要求输入
3. 如果 `authEnabled=false` → 直接使用（向后兼容）

### 令牌传递

- **HTTP 请求**：`Authorization: Bearer <token>`（自动通过 fetch override 注入）
- **WebSocket**：`?token=<token>` 查询参数（自动通过 authWsUrl 注入）
- **分享链接**：`?auth=<token>`（首次访问自动保存到 localStorage）

## 远程用户五感体验

### 👁 视觉 — 屏幕投射
- **MJPEG**：兼容性最好，任何浏览器
- **H.264/H.265**：低带宽高画质，需现代浏览器
- FPS/延迟实时显示（Alt+I）
- 1:1 像素模式（Alt+G）
- 画面旋转、镜像、滤镜

### 👂 听觉 — 音频流
- 48kHz 立体声 WebSocket 实时音频
- 自动处理浏览器 autoplay 策略
- 点击 AUDIO 按钮或页面后自动启动

### 🖐 触觉 — 输入控制
- **触摸**：点击、滑动、长按、双击、缩放
- **键盘**：完整 PC 键盘映射（中文/英文/特殊键/Ctrl 组合）
- **鼠标**：左键=触摸，右键=返回，中键=Home，滚轮=滚动
- **手柄**：Quest VR 手柄 + 标准游戏手柄
- **Ctrl+拖拽**：缩放手势模拟（scrcpy 风格）

### 🧠 认知 — AI + 自动化
- **AI 命令栏**：自然语言控制（"打开微信"、"设置WiFi"）
- **View Tree**：获取界面元素树
- **语义点击**：按文本查找并点击元素
- **宏系统**：录制/回放/触发器/导入导出

### 🎮 管控 — 设备完整控制
- 70+ API 端点覆盖手机所有功能
- 文件管理器（浏览/上传/下载/删除）
- 应用管理（启动/列表/安装）
- 系统控制（音量/亮度/WiFi/蓝牙/手电/GPS）
- 智能家居集成（Home Assistant + 涂鸦）
- 通知管理（读取/清除/历史）

## 连接质量

页面右上角显示实时连接质量：
- 🟢 **Good** (<100ms)：流畅操控
- 🟡 **Fair** (100-300ms)：可用，有轻微延迟
- 🔴 **Poor** (>300ms)：高延迟，建议降低画质
- ⚫ **Offline**：连接中断，自动重连中

### WebSocket 自动重连
- 触控 WS：指数退避重连（1s → 30s 上限）
- 主连接 WS：内置心跳 + 自动重连
- 视频 WS：断线后 2s 自动重连
- 音频 WS：断线后自动停止

## 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| Alt+H | Home |
| Alt+B / Esc | Back |
| Alt+S | Recents |
| Alt+F | 全屏 |
| Alt+M | 命令菜单 |
| Alt+/ | AI 命令栏 |
| Alt+I | FPS/延迟面板 |
| Alt+1~0 | 平台面板（应用/通知/阅读器/...） |
| Ctrl+V | 粘贴到手机 |
| F1 / ? | 快捷键帮助 |

## 安全建议

1. **始终启用认证**：公网暴露前必须生成令牌
2. **使用 HTTPS**：Cloudflare Tunnel 自动提供 HTTPS
3. **定期更换令牌**：调用 `/auth/generate` 生成新令牌
4. **不用时撤销**：调用 `/auth/revoke` 关闭认证（恢复局域网模式）
5. **监控连接**：注意连接质量指示器，异常延迟可能意味着中间人攻击

## 故障排除

| 问题 | 解决方案 |
|------|----------|
| 认证门一直显示 | 检查令牌是否正确，清除 localStorage 重试 |
| WebSocket 连不上 | 确认隧道支持 WebSocket（Cloudflare Tunnel 默认支持） |
| 画面卡顿 | 切换到 H.264 编码，降低分辨率 |
| 音频不播放 | 点击页面任意位置解锁浏览器 autoplay |
| 触控无响应 | 确认手机端 InputService（无障碍服务）已启动 |
| FRP 连接失败 | 检查 FRP 服务器是否开放端口，确认配置正确 |

## 端口分配

| 端口 | 服务 | 说明 |
|------|------|------|
| 8081 | MJPEG Gateway | **主入口**，包含投屏+所有 Input API |
| 8084 | Input HTTP | 独立 Input API（可选，通常不需要） |
