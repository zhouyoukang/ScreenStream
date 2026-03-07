# 雷电模拟器开发部署中枢

> 统一管理LDPlayer虚拟机，为工作区13个手机相关项目提供全自动化测试/开发/部署/验证，无需实体机。

## 全景架构

```
┌─────────────────────────────────────────────────────────────┐
│                    雷电模拟器 LDPlayer 9                      │
│            D:\leidian\LDPlayer9 (v9.0.75.01)                │
│     VT=1 | RTX 4070 SUPER | Ryzen 7 9700X | 61.6GB         │
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│  VM[0]   │  VM[3]   │  VM[4]   │  VM[5]   │ VM[1][2]归档   │
│ 通用主控  │ SS投屏   │ PWA-Web  │ 采集自动化│                │
│ vivo     │ vivo     │ OPPO     │ nubia    │                │
│ 1080p    │ Root✅   │ Chrome   │ SS       │                │
│          │ SS+V2ray │          │          │                │
├──────────┼──────────┼──────────┼──────────┤                │
│ 构建验证  │ SS开发   │ 二手书   │ 订单采集  │                │
│          │ PhoneLib │ 公网投屏  │ 抖音同步  │                │
│          │ 公网投屏  │ 智能家居  │ Agent控制 │                │
│          │ 亲情远程  │ 微信公众号│          │                │
│          │ 软路由   │          │          │                │
└──────────┴──────────┴──────────┴──────────┴─────────────────┘
     ↕ ADB          ↕ ADB         ↕ ADB        ↕ ADB
  emulator-5554  emulator-5560 emulator-5562 emulator-5564
     ↕ forward      ↕ forward     ↕ forward    ↕ forward
  (按需)          18080-18084   28080-28084   38080-38084
```

## 快速开始

```powershell
# 全景状态
python 雷电模拟器/ld_manager.py

# 详细状态 (含应用+SS)
python 雷电模拟器/ld_manager.py --status

# 健康检查
python 雷电模拟器/ld_manager.py --health

# 端到端验证
python 雷电模拟器/ld_manager.py --e2e

# 端口映射
python 雷电模拟器/ld_manager.py --ports setup

# 项目测试
python 雷电模拟器/ld_manager.py --test ScreenStream
python 雷电模拟器/ld_manager.py --test all
```

## 虚拟机详情

### VM[0] 雷电模拟器 — 通用主控

- **型号**: vivo V1916A | **分辨率**: 1920×1080@280dpi
- **ADB**: emulator-5554
- **用途**: ScreenStream APK构建后的首次安装验证
- **应用**: 空白(按需安装)

### VM[3] 开发测试1 → SS-投屏主控

- **型号**: vivo V1824A | **分辨率**: 540×960@240dpi | **Root**: ✅
- **ADB**: emulator-5560
- **已装**: ScreenStream, V2rayNG, Chrome, 拼多多, 学堂云, AudioCenter
- **项目**: ScreenStream核心开发, 手机操控库, 公网投屏, 亲情远程, 手机软路由
- **端口**: 8084(Input), 8080(Gateway), 8088/8089(本地服务)

### VM[4] 开发测试2 → PWA-Web测试

- **型号**: OPPO PCLM10 | **分辨率**: 540×960@240dpi
- **ADB**: emulator-5562
- **已装**: ScreenStream, V2rayNG, Chrome, 拼多多, 学堂云
- **项目**: 二手书手机端, 电脑公网投屏手机(Viewer), 智能家居, 微信公众号
- **端口**: 8085(服务)

### VM[5] 开发测试 → 采集-自动化

- **型号**: nubia NX629J | **分辨率**: 540×960@240dpi
- **ADB**: emulator-5564
- **已装**: ScreenStream, Chrome, 拼多多, 学堂云
- **项目**: 手机购物订单采集, ORS6-VAM抖音同步, agent-phone-control
- **端口**: 8084(Input)

## 13个项目测试方案

### 1. ScreenStream (核心)

```powershell
# 构建APK
./gradlew :app:assembleDevDebug

# 安装到VM[3]
D:\leidian\LDPlayer9\adb.exe -s emulator-5560 install -r -t app\build\outputs\apk\dev\debug\*.apk

# 启动
D:\leidian\LDPlayer9\adb.exe -s emulator-5560 shell "am start -n info.dvkr.screenstream.dev/info.dvkr.screenstream.ui.activity.AppActivity"

# 端口映射
D:\leidian\LDPlayer9\adb.exe -s emulator-5560 forward tcp:18080 tcp:8080
D:\leidian\LDPlayer9\adb.exe -s emulator-5560 forward tcp:18084 tcp:8084

# 验证
curl http://127.0.0.1:18080/api/status
curl http://127.0.0.1:18084/status
```

### 2. 手机操控库 (PhoneLib)

```python
from phone_lib import Phone
phone = Phone(host='127.0.0.1', port=18084)
print(phone.status())    # connected, inputEnabled
print(phone.read())      # 屏幕文本
phone.home()             # 按Home
phone.click('设置')       # 点击
```

### 3. 公网投屏

```powershell
# SS运行后，MJPEG端口映射
D:\leidian\LDPlayer9\adb.exe -s emulator-5560 forward tcp:18081 tcp:8081
# 浏览器访问 http://127.0.0.1:18081 查看投屏画面
```

### 4. 亲情远程

```powershell
# WebRTC端口映射
D:\leidian\LDPlayer9\adb.exe -s emulator-5560 forward tcp:18083 tcp:8083
# 测试WebRTC信令连接
```

### 5. 手机软路由

```powershell
# V2rayNG已安装在VM[3]
D:\leidian\LDPlayer9\adb.exe -s emulator-5560 shell "am start -n com.v2ray.ang/.ui.MainActivity"
# SOCKS5端口映射
D:\leidian\LDPlayer9\adb.exe -s emulator-5560 forward tcp:10808 tcp:10808
```

### 6. 二手书手机端 (PWA)

```powershell
# 在VM[4]的Chrome中打开
D:\leidian\LDPlayer9\adb.exe -s emulator-5562 shell "am start -a android.intent.action.VIEW -d 'http://127.0.0.1:8088'"
# 需先反向映射PC的二手书服务到模拟器
D:\leidian\LDPlayer9\adb.exe -s emulator-5562 reverse tcp:8088 tcp:8088
```

### 7. 电脑公网投屏手机 (Viewer)

```powershell
# 反向映射PC投屏服务
D:\leidian\LDPlayer9\adb.exe -s emulator-5562 reverse tcp:9803 tcp:9803
# Chrome打开Viewer
D:\leidian\LDPlayer9\adb.exe -s emulator-5562 shell "am start -a android.intent.action.VIEW -d 'http://127.0.0.1:9803'"
```

### 8. 智能家居

```powershell
# 反向映射
D:\leidian\LDPlayer9\adb.exe -s emulator-5562 reverse tcp:8900 tcp:8900
# 打开控制面板
D:\leidian\LDPlayer9\adb.exe -s emulator-5562 shell "am start -a android.intent.action.VIEW -d 'http://127.0.0.1:8900/wx/web'"
```

### 9. 手机购物订单

```powershell
# VM[5]用于ADB UI自动化
D:\leidian\LDPlayer9\adb.exe -s emulator-5564 shell "uiautomator dump /dev/tty"
# PhoneLib采集
python 手机购物订单/采集脚本/_agent_scroll_dump.py --serial emulator-5564
```

### 10-13. 其他项目

参见 `AGENTS.md` 中的项目→VM映射表。

## 伏羲八卦 · 问题与解决

### ☰乾 · 认知卸载

| 问题 | 解决 |
|------|------|
| VM名称含义不清 | 规划重命名方案(需停止VM执行) |
| 主VM无第三方应用 | 保持空白作为构建验证专用 |

### ☷坤 · 信息熵减

| 问题 | 解决 |
|------|------|
| VM1/2旧跑步记录VM | 保留归档，不影响开发 |
| 无文档记录 | 本README+AGENTS.md |

### ☵坎 · 上善若水

| 问题 | 解决 |
|------|------|
| CPU=1核/RAM=1536MB过低 | setup命令升级(需停VM) |
| Android 9受限 | LDPlayer 9限制，接受并适配 |

### ☲离 · 结构先于行动

| 问题 | 解决 |
|------|------|
| 分辨率540×960过低 | setup升级到720×1280 |
| SS安装但未运行 | 需手动授权MediaProjection |
| 端口映射不统一 | 规范化18xxx/28xxx/38xxx |

### ☳震 · 一次推到底

| 问题 | 解决 |
|------|------|
| 无自动化脚本 | ld_manager.py全覆盖 |
| 无测试配方 | --test命令+PROJECT_CONFIG |

### ☴巽 · 渐进渗透

| 问题 | 解决 |
|------|------|
| 共享路径可能不存在 | 模拟器内部路径，不影响功能 |
| 无.gitignore | 纯管理目录，无需git |

### ☶艮 · 知止

| 问题 | 解决 |
|------|------|
| 不需要更多VM | 4台运行中足够覆盖13项目 |
| x86_64架构限制 | ScreenStream已适配x86 |

### ☱兑 · 集群涌现

| 问题 | 解决 |
|------|------|
| 端口冲突 | 18xxx/28xxx/38xxx三段隔离 |
| 各项目无LDPlayer文档 | AGENTS.md统一记录 |

## 已安装应用清单

### VM[3] (开发测试1)

| 包名 | 应用 |
|------|------|
| info.dvkr.screenstream.dev | ScreenStream |
| com.v2ray.ang | V2rayNG |
| com.android.chrome | Chrome |
| com.xunmeng.pinduoduo | 拼多多 |
| com.xuetangx.xuetangcloud | 学堂云 |
| com.github.audiocenter | AudioCenter |
| com.example.hongqingting | 红蜻蜓 |
| com.rerware.android.MyBackupPro | MyBackup Pro |
| com.gmd.speedtime | SpeedTime |
| com.pro.backups02 | Backup工具 |

### VM[4] (开发测试2)

同VM[3]但无V2rayNG和AudioCenter。

### VM[5] (开发测试)

同VM[4]但无V2rayNG。

## 文件清单

| 文件 | 用途 |
|------|------|
| `ld_manager.py` | 统一管理脚本(状态/健康/测试/端口/安装) |
| `AGENTS.md` | Agent操作手册 |
| `README.md` | 本文档 |
