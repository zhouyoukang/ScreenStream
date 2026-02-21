# Phone Agent 能力全景图
> 基于 2026-02-21 实践验证，映射"最大化可达性，最小化依赖"到具体能力

## 已验证能力（按依赖度分层）

### 零依赖（人机完全共存）
| 能力 | 路径 | 实践验证 |
|------|------|---------|
| 设备信息 | API /deviceinfo | ✅ 电池/内存/存储/WiFi/运行时间 |
| 通知监控 | API /notifications/read | ✅ 微信/HA/淘宝等实时捕获 |
| 前台APP | API /foreground | ✅ 包名+Activity |
| APP列表 | ADB pm list packages | ✅ 296个第三方APP |
| 系统属性 | ADB getprop | ✅ 型号/系统版本 |
| 电池详情 | ADB dumpsys battery | ✅ 电量/充电状态 |
| 内存状态 | ADB cat /proc/meminfo | ✅ 可用/总量 |
| CPU温度 | ADB cat thermal_zone | ✅ 29.5°C |
| 网络路由 | ADB ip route | ✅ WiFi+蜂窝 |
| 存储占用 | ADB du -sh | ✅ DCIM 59G等 |
| 系统设置读取 | ADB settings get | ✅ 飞行/蓝牙/亮度/旋转 |
| 截图到PC | ADB screencap + pull | ✅ 2.5MB, 28MB/s |
| 进程列表 | ADB ps -A | ✅ CPU/MEM排序 |

### 低依赖（一瞬间影响前台）
| 能力 | 路径 | 实践验证 |
|------|------|---------|
| 启动APP | ADB monkey / am start | ✅ monkey更可靠 |
| 干净启动 | ADB --activity-clear-task | ✅ 解决Activity恢复问题 |
| 按键注入 | ADB input keyevent | ✅ HOME/BACK等 |
| 触控注入 | ADB input tap/swipe | ✅ 像素坐标 |
| 通知推送 | ADB cmd notification post | ✅ 置顶+铃声+振动 |
| 通知栏控制 | ADB cmd statusbar | ✅ 展开/收起 |

### 中依赖（需要ScreenStream运行，只读不操控）
| 能力 | 路径 | 实践验证 |
|------|------|---------|
| 屏幕文本 | API /screen/text | ✅ 27项文本+18可点击 |
| View树 | API /viewtree | ✅ 深度可控 |
| 窗口信息 | API /windowinfo | ✅ 包名+节点数 |
| 剪贴板 | API /clipboard | ✅ |

### 高依赖（占用前台，人机互斥）
| 能力 | 路径 | 实践验证 |
|------|------|---------|
| 语义点击 | API /findclick | ✅ 12/12=100% (text+desc) |
| 文本输入 | API /text | ✅ |
| 智能关弹窗 | API /dismiss | ✅ 12种预设 |
| Intent发送 | API /intent | ✅ (+clearTask待编译) |
| 自然语言命令 | API /command | ✅ |
| 节点搜索 | API /findnodes | ✅ |
| 文本设置 | API /settext | ✅ |

## 可编排的子系统（手机上已安装）
| 系统 | PID状态 | Agent可调用方式 | 已验证 |
|------|---------|----------------|--------|
| ScreenStream | 运行 | HTTP API (40+端点) | ✅ |
| Tasker | PID=29523 | Intent广播 | 部分(广播送达,任务执行待验证) |
| MacroDroid | PID=23601 | HTTP Server(未启用) | ❌ 需手动启用 |
| AutoJS Pro | PID=18443 | Intent(未导出) | ❌ Android 15安全限制 |
| Termux | 未运行 | RUN_COMMAND | ❌ 需allow-external-apps |
| HomeAssistant | PID=15637 | 通知监控 | ✅ 12条捕获 |

## 反馈通道（Agent → 用户）
| 通道 | 方式 | 状态 |
|------|------|------|
| PC终端 | Cascade输出 | ✅ 默认 |
| 手机通知 | ADB cmd notification | ✅ 已修复(置顶+铃声+振动) |
| 手机文件 | ADB写入/sdcard/Download | ✅ 晨报已验证 |
| 手机截图 | ADB screencap+pull到PC | ✅ |

## 连接方式
| 方式 | 状态 | 备注 |
|------|------|------|
| USB ADB | ✅ | 设备158377ff |
| WiFi ADB | ✅ | 192.168.10.122:5555 |
| 端口转发 | ✅ | 8087→8086 |
| 公网穿透 | 待验证 | FRP/Tailscale |

## 差距分析

### 已验证但需改进
- Intent clearTask: 代码已改待编译
- /apps端点WiFi下超时: JSON过大
- 豆包发送按钮无障碍标签缺失: 需坐标定位

### 需要配置才能使用
- Termux: allow-external-apps=true
- MacroDroid HTTP Server: 需在APP内手动启用
- AutoJS: 需找到正确的Intent/广播路径

### 架构级差距
- LLM集成: Agent缺少"think"能力,当前只有关键词匹配
- 持久化工作流: 只有前端localStorage,无服务端持久化
- 多设备支持: 当前只能操控一台手机
- 公网远程: WiFi ADB仅限局域网

## 哲学原则映射

```
最大化可达性，最小化依赖
         ↓
  13种零依赖能力     → 人机完全共存
  6种低依赖能力      → 一瞬间影响
  4种中依赖能力      → 需ScreenStream但只读
  7种高依赖能力      → 需要屏幕控制
  6个可编排子系统    → 手机=自动化生态
  4种反馈通道        → Agent→用户多路径
  4种连接方式        → 有线/无线/远程
```

**Agent的默认模式应该是"零依赖感知+低依赖操控"，
只在需要精确UI交互时才使用"高依赖"路径。**
