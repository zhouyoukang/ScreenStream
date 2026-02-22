# Skill: Agent Phone Control

## 触发条件
用户要求执行多步手机操作、跨APP工作流、或需要动态决策的任务时自动触发。

## 架构
```
Cascade ←→ phone_lib.py ←→ ScreenStream API ←→ Android Phone
                             ↑
              自动发现: USB(:8086) → WiFi(IP:port) → Tailscale(100.x:port)
              弹性: 心跳 + 重试 + 负面状态自动恢复
```
Cascade 本身就是 Agent 大脑。通过 phone_lib 或终端调用手机API，实现 Observe→Think→Act→Verify 循环。
**支持远程**：只要手机有网络（WiFi/4G+Tailscale），无需USB即可全功能操控。

## Agent 循环

### 1. Observe（观察）
```powershell
Invoke-RestMethod http://127.0.0.1:8086/screen/text
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
Invoke-RestMethod -Method POST http://127.0.0.1:8086/findclick -Body '{"text":"设置"}' -ContentType 'application/json'

# 坐标点击（归一化）
Invoke-RestMethod -Method POST http://127.0.0.1:8086/tap -Body '{"nx":0.5,"ny":0.5}' -ContentType 'application/json'

# Intent直跳
Invoke-RestMethod -Method POST http://127.0.0.1:8086/intent -Body '{"action":"android.settings.WIFI_SETTINGS","flags":["FLAG_ACTIVITY_NEW_TASK","FLAG_ACTIVITY_CLEAR_TASK"]}' -ContentType 'application/json'

# 导航
Invoke-RestMethod -Method POST http://127.0.0.1:8086/home
Invoke-RestMethod -Method POST http://127.0.0.1:8086/back

# 文本输入
Invoke-RestMethod -Method POST http://127.0.0.1:8086/text -Body '{"text":"搜索词"}' -ContentType 'application/json'

# 滑动
Invoke-RestMethod -Method POST http://127.0.0.1:8086/swipe -Body '{"nx1":0.5,"ny1":0.7,"nx2":0.5,"ny2":0.3,"duration":300}' -ContentType 'application/json'
```

### 4. Verify（验证）
```powershell
# 等待文本出现
Invoke-RestMethod http://127.0.0.1:8086/wait?text=蓝牙&timeout=5000
# → { found: true/false }

# 或重新观察确认前台APP
Invoke-RestMethod http://127.0.0.1:8086/foreground
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
p = Phone(port=8086)
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
默认 8086（扫描 8080-8099 找 `/status` 响应）。
检查: `Invoke-RestMethod http://127.0.0.1:8086/status`
