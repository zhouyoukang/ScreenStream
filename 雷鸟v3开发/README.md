# 雷鸟V3 AR眼镜开发

> 道生一，一生二，二生三，三生万物。
> 眼镜最有用时，用户忘记了它。—— 老子第十一章

## 概述

RayNeo V3 (XRGF50) 是一款AI拍摄眼镜，内含完整Android 12系统。无屏幕显示，通过**语音+触觉+LED**与用户交互。

本项目实现了五层架构：

| 层 | 文件 | 功能 | 端口 |
|----|------|------|------|
| **五感层** | `rayneo_五感.py` | 视觉/听觉/触觉/空间/环境 五感基础引擎 | — |
| **道感知层** | `rayneo_道.py` | 以气听·意图前馈·无感度评分·归根管理 | — |
| **三联道** | `san_lian.py` | PC+手机+眼镜 三体联动引擎 | — |
| **手机脑** | `phone_server.py` | Termux HTTP服务 (运行在手机端) | 8765 |
| **PC桥接** | `shou_ji_nao.py` | PC→手机→眼镜 临时桥接层 | — |
| **管理中枢** | `rayneo_dashboard.py` | PC端Dashboard后端 (6页面SPA) | 8800/8801 |
| **虚拟仿真** | `rayneo_sim_server.py` | V3仿真器+App Center后端 | 8767/8768 |
| **无线中枢** | `wireless_config.py` | ADB/IP/健康监测统一管理 | — |

## 设备

| 角色 | 设备 | ADB序列号 | 系统 |
|------|------|-----------|------|
| 道/PC | 台式机 192.168.31.141 | — | Windows |
| 二/手机 | OnePlus NE2210 | 158377ff | Android 15 |
| 三/眼镜 | RayNeo V3 XRGF50 | 841571AC688C360 | Android 12 userdebug |

## 快速开始

### 前置条件

- Python 3.10+
- ADB 已安装且在 PATH 中（或位于 `D:\scrcpy\` 目录）
- RayNeo V3 通过 **专用ADB调试夹具** 连接（充电线不可用）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动

```bash
# 单机五感引擎（眼镜+PC）
python rayneo_五感.py --run

# 道感知引擎（含意图前馈+无感度评分）
python rayneo_道.py --run

# 三体联动（PC+手机+眼镜）
python san_lian.py --run

# 手机脑模式（先在手机Termux启动 phone_server.py）
python shou_ji_nao.py --run

# 管理中枢 Dashboard（6页面SPA）
python rayneo_dashboard.py
# → http://localhost:8800

# V3仿真器 + App Center（20个App模拟器）
python rayneo_sim_server.py
# → http://localhost:8768/v3_app_center.html
# → http://localhost:8768/rayneo_simulator.html
```

或双击 `.cmd` 文件一键启动。

### 常用命令

```bash
python rayneo_五感.py --sense      # 五感状态报告
python rayneo_五感.py --photo      # 拍照一次
python rayneo_五感.py --speak "你好" # TTS播报
python rayneo_五感.py --battery    # 查看电量
python san_lian.py --test          # 三体链路验证
python san_lian.py --scene 1       # 运行场景1
```

## 五感映射

```
视觉 → 摄像头帧 → CV/通义Vision → 语音播报（无需看屏幕）
听觉 → 3麦降噪 → "小雷小雷"唤醒 → 通义理解 → TTS扬声器
触觉 → 右镜腿TP(X轴) → 单击/滑动/长按（轻触无需掏机）
空间 → IMU姿态 → 头部朝向=意图：低头=拍照，抬头=提问，转头=翻页
环境 → 光传感器 → 室内/室外自适应
```

## 三联道场景（万物）

| # | 场景 | 描述 | 触发 |
|---|------|------|------|
| 1 | 眼镜看→PC AI→眼镜说 | 第一人称AI助手 | 眼镜单击TP |
| 2 | 手机屏→OCR→眼镜播 | 手机→眼镜信息中继 | 眼镜双击TP |
| 3 | 通知→眼镜播报 | 手机通知音频化 | ActionButton短按 |
| 4 | 眼镜触控→手机操作 | 跨设备遥控 | 眼镜前/后滑TP |
| 5 | 三体全景感知报告 | 三体状态全景 | 眼镜长按TP |

## 目录结构

```
雷鸟v3开发/
├── 核心引擎
│   ├── rayneo_五感.py          # 五感基础引擎 (35KB)
│   ├── rayneo_道.py            # 道感知层 (31KB)
│   ├── san_lian.py             # 三联道引擎 (29KB)
│   ├── phone_server.py         # 手机脑服务器 Termux (24KB)
│   ├── shou_ji_nao.py          # PC桥接层 临时 (19KB)
│   ├── phone_relay.py          # Phase 2手机直连 Termux (14KB)
│   └── wireless_config.py      # 无线配置中枢 (20KB)
│
├── Web服务
│   ├── rayneo_sim_server.py    # V3仿真器+App Center后端 :8767/:8768 (45KB)
│   ├── rayneo_dashboard.py     # 管理中枢后端 :8800/:8801 (20KB)
│   ├── v3_app_center.html      # V3 App Center+设备模拟器 (62KB)
│   ├── rayneo_simulator.html   # 五感仿真器UI (43KB)
│   └── rayneo_dashboard.html   # 管理中枢Dashboard (47KB)
│
├── 一键启动
│   ├── →启动五感引擎.cmd
│   ├── →三联道万物.cmd
│   ├── →手机脑启动.cmd
│   ├── →管理中枢.cmd
│   └── →Phase2手机直连.cmd
│
├── 文档
│   ├── README.md               # 本文件
│   ├── AGENTS.md               # Agent操作手册
│   ├── _INDEX_SDK文档.md       # SDK完整文档（飞书原文）
│   ├── V3_SYSTEM_REVERSE_ENGINEERING.md  # 逆向工程报告
│   └── AUDIT_REPORT_20260614.md          # 审计报告(合并版)
│
├── SDK/                        # SDK资源 (gitignored二进制)
├── docs/                       # 开发指南 + SDK示例项目
├── requirements.txt
└── .gitignore
```

## SDK 接入要点

- SDK: `MarsAndroidSDK-v1.0.1.aar` → 放入 `libs/`
- 初始化: `MarsSDK.init(this)`
- 触控: 监听 `TempleAction` 事件流
- 语音唤醒: 安装 `MarsSpeech` APK → 监听广播 `com.rayneo.aispeech.wakeup`
- 佩戴检测: `SystemUtil.deviceWearingState`
- WiFi防休眠: `RayneoSuspendManager.setWifiKeepOnStateByUserWithTimer(true/false)`
- 系统签名: 需 `platform.jks`（见 `_INDEX_SDK文档.md`）

## 雷鸟开放平台资源 (2026-03-05 调研)

| 资源 | 链接 | 说明 |
|------|------|------|
| 开放平台首页 | https://open.rayneo.cn/ | 设备系列/开发者服务/XR能力/发布流程 |
| V系列合作申请 | https://leiniao-ibg.feishu.cn/share/base/form/shrcnK5XaulI5z6J55EaLb8BaWs | V3 SDK不公开，需业务合作 |
| X Series SDK文档 | https://leiniao-ibg.feishu.cn/wiki/space/7384714761510518787 | 飞书Wiki(可参考通用API) |
| 开发者论坛 | https://bbs.rayneo.cn/ | 技术支持社群 |
| API文档(X系列) | https://open.rayneo.cn/#/docs → API | NativeModule/SDKWebView/2DUI |

> **重要**: V3 SDK (MarsAndroidSDK) 不在开放平台公开下载，仅通过业务合作获取。
> 本项目已有 v1.0.0 和 v1.0.1 两个版本。

## 端口分配

| 服务 | 端口 | 运行位置 | 用途 |
|------|------|----------|------|
| phone_server.py | 8765 | 手机(Termux) | 手机脑HTTP API |
| rayneo_sim_server.py | 8767/8768 | PC | 仿真器WS/HTTP |
| rayneo_dashboard.py | 8800/8801 | PC | Dashboard HTTP/WS |

## TODO

- [x] 获取专用ADB调试夹具
- [x] 确认ROM版本 (userdebug, root ADB)
- [x] 通义Vision API场景识别
- [x] 麦克风采集 (tinycap/screenrecord 双策略)
- [x] IMU姿态交互 (sysfs IIO + sensorservice 双策略)
- [x] WiFi ADB无线调试 (`wireless_config.py`)
- [x] 管理中枢Dashboard (6页面SPA)
- [x] V3虚拟仿真器 (五感模拟)
- [x] V3 App Center (20个App + 设备模拟器)
- [x] 三轮代码审计 (F1-F26, 26项修复)
- [ ] 脱PC Phase 2: 眼镜WiFi直连手机
- [ ] 注册雷鸟开放平台开发者账号
- [ ] 探索X Series SDK文档中可复用的通用API

## 资源来源

| 来源 | 说明 |
|------|------|
| 本目录 `SDK/` | MarsAndroidSDK v1.0.0/v1.0.1 + 示例 + APK |
| 本目录 `docs/` | 开发指南 + SDK示例项目源码 |
| `_INDEX_SDK文档.md` | 飞书原文完整SDK文档 |
| `V3_SYSTEM_REVERSE_ENGINEERING.md` | 逆向工程报告 |
| `AUDIT_REPORT_20260614.md` | 三轮审计报告(合并版, 15项修复) |

---

*汇集: 2026-03-05 | 审计: 三轮26项修复 | 最后更新: 2026-03-06*
