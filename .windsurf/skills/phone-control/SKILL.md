---
name: phone-control
description: Agent远程操控手机。当用户要求执行多步手机操作、跨APP工作流、或需要动态决策的任务时自动触发。
triggers:
  - 用户要求操控手机执行多步任务
  - 跨APP工作流编排
  - 手机屏幕读取/语义点击/Intent跳转
  - phone_lib调用或ScreenStream API交互
---

# Agent Phone Control

## 触发条件
用户要求执行多步手机操作、跨APP工作流、或需要动态决策的任务时自动触发。

## 架构
```
Cascade ←→ phone_lib.py ←→ ScreenStream API ←→ Android Phone
                             ↑
              自动发现: USB(:8084) → WiFi(IP:port) → Tailscale(100.x:port)
              弹性: 心跳 + 重试 + 负面状态自动恢复
```
Cascade 本身就是 Agent 大脑。通过 phone_lib 或终端调用手机API，实现 Observe→Think→Act→Verify 循环。
**支持远程**：只要手机有网络（WiFi/4G+Tailscale），无需USB即可全功能操控。

## Agent 循环

### 1. Observe（观察）
```powershell
Invoke-RestMethod http://127.0.0.1:8084/screen/text
# → { package, texts[], clickables[], textCount, clickableCount }
```

### 2. Think（决策）
- 当前APP？目标APP？→ 需要切换？
- 目标元素在屏幕上？→ 需要滚动？
- 有弹窗/权限对话框？→ 先dismiss
- 上一步成功？→ 需要回退？

### 3. Act（执行）
```powershell
# 语义点击
Invoke-RestMethod -Method POST http://127.0.0.1:8084/findclick -Body '{"text":"设置"}' -ContentType 'application/json'

# 坐标点击（归一化）
Invoke-RestMethod -Method POST http://127.0.0.1:8084/tap -Body '{"nx":0.5,"ny":0.5}' -ContentType 'application/json'

# Intent直跳
Invoke-RestMethod -Method POST http://127.0.0.1:8084/intent -Body '{"action":"android.settings.WIFI_SETTINGS","flags":["FLAG_ACTIVITY_NEW_TASK","FLAG_ACTIVITY_CLEAR_TASK"]}' -ContentType 'application/json'

# 导航
Invoke-RestMethod -Method POST http://127.0.0.1:8084/home
Invoke-RestMethod -Method POST http://127.0.0.1:8084/back

# 文本输入
Invoke-RestMethod -Method POST http://127.0.0.1:8084/text -Body '{"text":"搜索词"}' -ContentType 'application/json'

# 滑动
Invoke-RestMethod -Method POST http://127.0.0.1:8084/swipe -Body '{"nx1":0.5,"ny1":0.7,"nx2":0.5,"ny2":0.3,"duration":300}' -ContentType 'application/json'
```

### 4. Verify（验证）
```powershell
# 等待文本出现
Invoke-RestMethod http://127.0.0.1:8084/wait?text=蓝牙&timeout=5000
# → { found: true/false }

# 或重新观察确认前台APP
Invoke-RestMethod http://127.0.0.1:8084/foreground
```

## 常用API速查

| API | 方法 | 用途 |
|-----|------|------|
| `/status` | GET | 连接状态 |
| `/screen/text` | GET | 屏幕文字+可点击 |
| `/foreground` | GET | 前台APP |
| `/deviceinfo` | GET | 设备信息 |
| `/viewtree?depth=4` | GET | View树（含坐标） |
| `/notifications/read` | GET | 通知列表 |
| `/wait?text=X&timeout=T` | GET | 等待文字 |
| `/findclick` | POST | 语义点击 |
| `/tap` | POST | 坐标点击 |
| `/intent` | POST | 发送Intent |
| `/command` | POST | 自然语言命令 |
| `/home` `/back` `/wake` | POST | 导航/唤醒 |
| `/volume` `/brightness` | POST | 系统控制 |
| `/clipboard` | GET/POST | 剪贴板读写 |
| `/apps` | GET | 已装APP列表 |
| `/files/list?path=X` | GET | 文件列表 |

## 或用 phone_lib（Python）

```python
from phone_lib import Phone  # 手机操控库/phone_lib.py
p = Phone(port=8084)
p.click("设置"); p.read(); p.home()
```

## Intent速查

| 目标 | Action |
|------|--------|
| WiFi | `android.settings.WIFI_SETTINGS` |
| 蓝牙 | `android.settings.BLUETOOTH_SETTINGS` |
| 关于手机 | `android.settings.DEVICE_INFO_SETTINGS` |
| 电池 | `android.intent.action.POWER_USAGE_SUMMARY` |
| 应用管理 | `android.settings.APPLICATION_SETTINGS` |
| 打开URL | `android.intent.action.VIEW` + data=URL |
| 拨号 | `android.intent.action.DIAL` + data=tel:NUMBER |

## 端口
默认 8084（扫描 8080-8099 找 `/status` 响应）。
检查: `Invoke-RestMethod http://127.0.0.1:8084/status`

## a11y失效降级策略
微信/WebView/游戏等反无障碍APP → `/screen/text` 返回 texts=0 时：
1. 用 `/foreground` 包名验证替代文本验证
2. 用 `/viewtree?depth=8` 尝试获取更多节点
3. （待实现）截屏→VLM理解→坐标操作

## 全景文档
- `tools/phone-fleet/AI_PHONE_CONTROL.md` — AI操控手机全景图（全球40+项目对标+演进路线）
- `双电脑互联/agent操作电脑/AI_COMPUTER_CONTROL.md` — AI操作电脑全景图（PC+手机）
