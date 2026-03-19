# 亲情远程 · Agent操作指令 v6.0

> 反者道之动: P2P公网直连 + LAN兼容. 复用向日葵/ToDesk ICE基础设施.

## 目录用途
远方子女通过浏览器实时看到并操控父母 Android手机。
公网: WSS via FRP+Nginx (https://aiotvr.xyz/family/) | LAN: 直连 :9860

## 技术栈
- **唯一中枢**: `family_remote.py` (Python asyncio+websockets, :9860)
- **投屏**: ScreenStream H264 WebSocket (手机:8080) via ADB forward
- **控制**: ADB input + SS Input API (手机:8084) via ADB forward
- **前端**: `viewer/index.html` (WebCodecs H264解码 + 触控)
- **公网**: FRP隧道(9860→19860) + Nginx WSS代理 + SSL(Let's Encrypt)
- **ICE**: 7 STUN(向日葵/ToDesk逆向提取+Google) + 4 TURN(metered.ca免费)

## 端口
- **9860** — Hub唯一端口 (HTTP API + WebSocket relay + 静态文件)
- **19860** — 阿里云FRP隧道端口 (→127.0.0.1:9860)
- **28080/38080** — ADB forward到手机MJPEG/H264 (自动分配)
- **28084/38084** — ADB forward到手机Input API (自动分配)

## 公网访问
- **Viewer**: `https://aiotvr.xyz/family/cast/?room=ROOMID&token=family_remote_2026`
- **API**: `https://aiotvr.xyz/family/api/health`
- **链路**: 浏览器 → Nginx(SSL) → FRP隧道 → Hub(:9860) → ADB → 手机

## 伏羲八卦架构
| 卦 | 域 | 内容 |
|----|-----|------|
| ☰乾 | Hub | 统御一切的中枢, Agent最高权限 |
| ☷坤 | 设备 | 多台手机同时投屏+管理 |
| ☲离 | 视 | H264 WebCodecs实时解码 |
| ☳震 | 触 | 触控/滑动/文字/手势注入 |
| ☴巽 | 控 | ADB+SS API双通道(shell/pkg/file/sms) |
| ☵坎 | 流 | SS H264 WebSocket零转码 |
| ☶艮 | 部署 | ADB install -r零手动更新 |
| ☱兑 | Agent | HTTP GET全功能闭环 |

## 关键文件
| 文件 | 用途 | 修改风险 |
|------|------|---------|
| `family_remote.py` | ★唯一中枢(~860行, 全部功能) | �高 |
| `viewer/index.html` | 子女端Viewer(H264+触控, 1698行) | 🟡中 |
| `viewer/setup.html` | 配置指南 | 🟢低 |
| `→亲情远程.cmd` | 一键启动 | �低 |
| `_e2e_v5.py` | E2E测试(49项) | 🟢低 |
| `_archive/` | 旧系统归档(cloud relay/signaling/old hub) | 🟢冻结 |

## API端点 (family_remote.py :9860)

### ☰乾·Hub基础
- `GET /api/health` — 系统健康(版本/设备数/流/房间/运行时间)
- `GET /api/devices` — ADB设备列表(型号/Android/分辨率/投屏状态)
- `GET /api/status` — 所有活跃流状态(帧数/字节/重连/viewers)
- `GET /api/rooms` — 房间列表(设备/viewers/帧数)

### ☷坤·投屏控制
- `GET /api/start?device=X` — 启动设备投屏(自动ADB forward+SS+room)
- `GET /api/stop?device=X` — 停止投屏
- `GET /api/start-all` — 启动所有手机投屏
- `GET /api/projection?device=X` — 启动AgentProjectionActivity+自动批准

### ☳震·触控
- `GET /api/tap?device=X&x=0.5&y=0.5` — 点击(归一化坐标)
- `GET /api/swipe?device=X&x1=.5&y1=.3&x2=.5&y2=.7&dur=300` — 滑动
- `GET /api/text?device=X&t=hello` — 输入文字
- `GET /api/control?device=X&action=home|back|recents|wake|lock|notifications|quicksettings` — 按键
- `GET /api/app?device=X&package=com.xxx` — 启动APP

### ☴巽·Agent控制 (v5.0)
- `GET /api/shell?device=X&cmd=ls /sdcard` — ADB shell命令
- `GET /api/packages?device=X` — 已安装应用列表
- `GET /api/uninstall?device=X&package=com.xxx` — 卸载应用
- `GET /api/battery?device=X` — 电池信息
- `GET /api/sms?device=X&limit=20` — 读取短信
- `GET /api/calls?device=X&limit=20` — 读取通话记录
- `GET /api/clipboard?device=X&text=X` — 读取/设置剪贴板
- `GET /api/wifi?device=X` — WiFi信息
- `GET /api/screenshot?device=X` — ADB截图(base64 PNG)
- `GET /api/screen-state?device=X` — 屏幕开关状态
- `GET /api/foreground?device=X` — 当前前台应用
- `GET /api/input-method?device=X&text=中文` — Unicode文字输入
- `GET /api/reboot?device=X` — 重启设备

### ☶艮·部署
- `GET /api/deploy?device=X` — ADB install -r更新APK
- `GET /api/deploy-all` — 更新所有设备APK
- `GET /api/push?device=X&local=path&remote=/sdcard/` — 推送文件
- `GET /api/pull?device=X&remote=/sdcard/x` — 拉取文件

### ☵坎·SS代理
- `GET /api/ss/<path>?device=X` — 代理SS Input API

### WebSocket
- `WS /relay/?role=viewer&token=X&room=Y` — viewer连接
- `WS /relay/?role=provider&room=Y` — 外部provider

## 已连接设备
| 设备 | Serial | USB | SS投屏 | 备注 |
|------|--------|-----|--------|------|
| OnePlus NE2210 | 158377ff | ✅USB | ✅ | Android 15, 1080x2412 |
| OPPO PCHM30 (A11x) | 54ea19ff | ✅USB | ✅ | Android 11, 720x1600 |

## 启动
```
python family_remote.py --all     # 全部设备同时投屏
python family_remote.py -d 158377ff  # 指定设备
→亲情远程.cmd                      # 一键启动
```

## Agent操作规则
- 修改Hub后重启: `python family_remote.py --all`
- Agent所有操作通过HTTP API, 无需UI/SendKeys
- 设备serial省略时自动选择第一台
- `/api/deploy-all` 可一键更新所有设备SS APK
- 旧云端系统已归档到 `_archive/` — 不要恢复

## E2E验证
```
python _e2e_v5.py    # 49项伏羲八卦全功能测试(100% PASS)
```

## 2026-03-16 v5.0变更
- 从family_hub.py迁移到family_remote.py作为唯一中枢
- 去除所有阿里云中转(relay-server/signaling-server归档)
- 新增15个Agent Power API(shell/sms/calls/clipboard/wifi/battery等)
- 修复端口复用bug(stop/start cycle不再导致端口递增)
- ControlHandler增强(lock/quicksettings/splitscreen/brightness等)
- 版本号4.0→5.0
- 归档22个旧文件到_archive/
- ADB install -r验证通过(OnePlus+OPPO A11x双设备)
