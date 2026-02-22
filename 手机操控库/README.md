# 手机操控库 (PhoneLib)

> 零外部依赖(纯urllib)，封装ScreenStream 90+ HTTP API为`Phone`类。
> 支持USB/WiFi/Tailscale/公网穿透全链路。内建自动发现、心跳、断线重连、负面状态恢复。

## 快速开始

```python
from phone_lib import Phone

# 自动发现最优连接（USB→WiFi→Tailscale）
p = Phone()

# 或指定连接方式
p = Phone(host="192.168.31.100")          # WiFi直连
p = Phone(host="100.100.1.5")             # Tailscale
p = Phone(url="https://my.domain.com")    # 公网穿透
p = Phone(port=8086, auto_discover=False) # 传统USB模式

# 带心跳守护（30秒自动检测+恢复）
p = Phone(heartbeat_sec=30)
```

## 弹性特性（远程核心）

```python
# 五感全采集
s = p.senses()  # → {vision, hearing, touch, smell, taste}

# 健康检查
h = p.health()  # → {state, detail, battery, network, ...}

# 确保可用（自动检测+恢复全部负面状态）
alive, log = p.ensure_alive()
# 自动处理: 息屏→唤醒 / APP被杀→重启 / 无障碍断→重连 / USB断→切WiFi / ...

# 重连
p.reconnect()                    # 自动发现最优路径
p.switch_to(host="100.100.1.5") # 手动切换
```

### 负面状态自动恢复矩阵

| 状态 | 检测 | 恢复 |
|------|------|------|
| 息屏/锁屏 | screenOffMode=true | POST /wake |
| 无障碍断开 | inputEnabled=false | /a11y/enable 或 ADB重启 |
| APP被杀 | HTTP不通+ADB可达 | monkey重启+端口重探测 |
| USB断开 | ADB不可达 | 自动切WiFi/Tailscale |
| 电量低 | battery<10% | 告警（功能仍可用） |
| Doze冻结 | API超时 | ADB unforce + wake |

## 五感操控

```python
# 👁 视觉
texts, pkg = p.read()               # 屏幕文本
p.viewtree(depth=4)                 # View树
p.foreground()                      # 前台APP

# 👂 听觉
p.volume(8); p.media("next")        # 音量/媒体控制
p.findphone()                       # 找手机响铃

# 🖐 触觉
p.click("设置"); p.tap(0.5, 0.5)    # 语义/坐标点击
p.swipe("up"); p.home(); p.back()   # 滑动/导航
p.command("打开WiFi设置")            # 自然语言命令

# 👃 嗅觉（通知）
p.notifications(10)                 # 最近通知
p.check_notifications_smart()       # 智能分类

# 👅 味觉（状态）
p.device()                          # 电池/存储/网络/WiFi
p.collect_status()                  # 一键全状态

# APP操控
p.open_app("com.tencent.mm")        # 打开微信（自动处理OEM弹窗）
p.alipay("10000007")                # 支付宝扫一扫
p.amap_search("星巴克")              # 高德搜索
p.search_in_app("耳机")            # APP内搜索

# 系统
p.wake(); p.lock(); p.screenshot()
p.brightness(128); p.flashlight()
p.dnd(); p.stayawake(); p.vibrate()

# 文件/智能家居/宏
p.files("/sdcard/DCIM")
p.smarthome_control("light.bedroom", "toggle")
p.macro_inline([{"action":"tap","nx":0.5,"ny":0.5}])
```

> **完整API**：`反向控制/输入路由/InputRoutes.kt`（90+路由）
> **Agent技能**：`.windsurf/skills/agent-phone-control/SKILL.md`

## 连接层级

| 层 | 方式 | 延迟 | 适用场景 |
|----|------|------|----------|
| L1 | USB `adb forward` | 1ms | 开发调试 |
| L2 | WiFi直连 | 1-5ms | 家/办公室 |
| L3 | Tailscale | 20-100ms | 外出任何网络 |
| L4 | 公网穿透 | 50-200ms | 极端场景 |

## 测试（46/46 通过，2026-02-22）

```bash
python tests/standalone_test.py --port 8086   # 36项 L0/L1 原始HTTP验证
python tests/agent_demo.py --port 8086        # 5个多步Agent任务
python tests/complex_scenarios.py --port 8086 # 5场景43步，86%零AI
```

## 依赖度分层

| 级别 | 操作类型 | 特点 |
|------|---------|------|
| **零依赖** | 通知·设备信息·APP列表·电池·前台APP·截图·存储 | 人机共存 |
| **低依赖** | 启动APP·按键·触控·干净启动 | 瞬间影响前台 |
| **中依赖** | 屏幕文本·View树·窗口信息·剪贴板 | 只读 |
| **高依赖** | 语义点击·文本输入·关弹窗·Intent | 占用前台 |

**默认"零依赖感知+低依赖操控"，精确UI交互时才用"高依赖"。**
