# AGENTS.md — 雷鸟V3 AR眼镜开发

## 项目定位

RayNeo V3 (XRGF50) AI眼镜的PC端感知引擎。三层架构：五感→道感知→三联道。

## 关键约束

- **无屏幕**: V3没有显示屏，所有交互通过语音/触觉/LED
- **ADB夹具**: 必须用专用磁吸ADB夹具，普通USB充电线不可用（WiFi ADB已配置，可无线调试）
- **开发版ROM**: C端ROM无法安装自研APK，需刷开发版
- **设备序列号**: 眼镜=`841571AC688C360` 手机=`158377ff`
- **SDK**: MarsAndroidSDK v1.0.1 (包名 `com.ffalcon.mars.android.sdk`)

## 文件说明

| 文件 | 角色 | 修改风险 |
|------|------|----------|
| `rayneo_五感.py` | 五感基础层（视/听/触/空间/环境） | 中 — 核心感知类 |
| `rayneo_道.py` | 道感知层（意图前馈/无感度/归根） | 中 — 依赖五感层 |
| `san_lian.py` | 三联道引擎（PC+手机+眼镜） | 高 — 三设备协调 |
| `phone_server.py` | 手机脑服务器（Termux端运行） | 低 — 独立运行 |
| `shou_ji_nao.py` | PC桥接层（临时，Phase 2后可撤） | 低 — 临时桥接 |
| `wireless_config.py` | **无线配置中枢**（ADB/IP/健康监测） | 中 — 所有文件依赖 |
| `phone_relay.py` | **Phase 2手机直连脚本**（Termux端） | 低 — 独立运行 |
| `_INDEX_SDK文档.md` | SDK完整文档（飞书原文汇编） | 只读参考 |

## 操作指南

```bash
# 检查眼镜连接
adb -s 841571AC688C360 devices -l

# 五感状态
python rayneo_五感.py --sense

# 启动五感引擎
python rayneo_五感.py --run

# 三体联动
python san_lian.py --run

# 安装语音助手
adb -s 841571AC688C360 install -r SDK/MarsSpeech-*.apk
```

## 依赖

- Python 3.10+
- `pyttsx3` (PC端TTS)
- ADB in PATH 或 `D:\platform-tools\` 或 `D:\scrcpy\` 目录

## 注意事项

- 所有Python文件使用 `Path(__file__).parent` 作为项目根目录
- **无线配置**: 所有设备IP/ADB由 `wireless_config.py` 统一管理，禁止硬编码IP
- ADB路径通过 `wireless_config.find_adb()` 自动搜索
- `phone_server.py` 设计为在手机Termux内运行，不在PC执行
- `captures/` 和 `san_lian_captures/` 已被 `.gitignore` 忽略
- SDK二进制文件（.aar/.apk/.zip）已被 `.gitignore` 忽略
- 环境变量 `DASHSCOPE_API_KEY` 用于通义Vision API

## 架构三阶段（脱PC）

1. **Phase 1 (当前)**: PC运行 `shou_ji_nao.py` → ADB桥接眼镜+手机
2. **Phase 2 (就绪)**: 手机运行 `phone_relay.py` → WiFi ADB直连眼镜 → 无需PC
3. **Phase 3 (远期)**: 原生SDK Kotlin App → 完全无线无PC

## 审计报告 (2026-03-05)

### 资源整合
- **来源**: 台式机E盘 `E:\道\AI--AR\雷鸟V3\` + 笔记本SMB `\\192.168.31.179\E$\道\Lab\`
- **目标**: `d:\道\道生一\一生二\雷鸟v3开发\`
- **内容**: SDK v1.0.0/v1.0.1, 示例项目, APK, 核心Python脚本, SDK文档

### 已修复问题 (三轮，共19项)

| # | 级别 | 问题 | 文件 | 修复 |
|---|------|------|------|------|
| F1 | 🔴 | 硬编码路径 `E:\道\AI--AR\` | rayneo_五感.py | `Path(__file__).parent` + `_find_adb()` |
| F2 | 🔴 | 硬编码路径 | san_lian.py | 同上 |
| F3 | 🔴 | 硬编码路径 | shou_ji_nao.py | 同上 |
| F4 | 🔴 | .cmd硬编码路径 | 3个.cmd | `%~dp0` + 通用`adb` |
| F5 | 🟡 | .DS_Store垃圾 | docs/ | 已删除8个 |
| F6 | 🟡 | 缺少.gitignore | 根目录 | 已创建(含TTS/截图/SDK) |
| F7 | 🟡 | 缺少requirements.txt | 根目录 | 已创建(含可选依赖说明) |
| F8 | 🟢 | 缺少README+AGENTS | 根目录 | 已创建 |
| F9 | 🔴 | `sense()`三次调ADB+崩溃 | shou_ji_nao.py:350 | 重写为安全循环解析 |
| F10 | 🔴 | `show_depc_path()`硬编码E盘 | shou_ji_nao.py:327 | 改为相对路径 |
| F11 | 🔴 | feishu包名=钉钉(错误) | phone_server.py:56 | 改为`com.ss.android.lark` |
| F12 | 🔴 | `urllib.request.quote`不存在 | phone_server.py:150 | 改为`urllib.parse.quote` |
| F13 | 🟡 | `__import__("os")`反模式 | shou_ji_nao.py:255 | 改为`Path().exists()` |
| F14 | 🟡 | .gitignore缺少_sj_tts/cap_ | .gitignore | 已补充 |
| F15 | 🔴 | GuiGenManager进程泄漏(zombie ADB) | rayneo_道.py | `_procs`跟踪+stop时kill |
| F16 | 🔴 | IMUDaoListener用logcat(不可靠) | rayneo_道.py | sysfs IIO + sensorservice双策略 |
| F17 | 🟡 | README TODO过时+硬编码E:路径 | README.md | 更新TODO+相对路径 |
| F18 | 🟡 | §5.1覆盖率与§10不一致 | V3_SYSTEM_REVERSE.md | 同步M1/M3为已解决 |
| F19 | 🟡 | ADB路径缺D:\platform-tools | rayneo_五感.py | 添加为最高优先级 |

### 已知限制
- `pyttsx3` 在 `glasses_tts()` 中每次创建新引擎（性能可优化为缓存）
- `device_online()` 检查不够精确（同行匹配vs全文匹配）
- `file:///sdcard/` URI 在 Android 12+ 可能被 FileUriExposedException 阻止

### USB模式发现 (本次审计)
- V3 USB PID映射: **F000**=MassStorage, **901D**=Qualcomm ADB, **4EE2**=Google ADB
- 普通充电线→PID_F000(G:盘挂载，无ADB); ADB夹具→PID_4EE2/901D
- ADB驱动已安装(android_winusb.inf, VID_18D1/VID_05C6)
- WiFi ADB(5555端口)未配置/不可达

### 网络资源调研
- **V3 SDK不公开**: 仅通过业务合作获取（飞书表单申请）
- **开放平台**: https://open.rayneo.cn/ (X/AIR系列有公开SDK，V系列无)
- **开发者论坛**: https://bbs.rayneo.cn/
- **X Series文档**: 飞书Wiki (可参考通用API模式)

## 五感E2E审计修复 (2026-03-05)

### 修复清单 (F20-F24, 共5项)
| ID | 严重度 | 文件 | 问题 | 修复 |
|----|--------|------|------|------|
| F20 | 🔴P0 | rayneo_五感.py | `_action_ask_ai()`是空stub | 接入通义千问qwen-turbo文本API |
| F21 | 🔴P0 | rayneo_五感.py + rayneo_道.py | `_find_imu_iio()` IIO name文件不可读导致检测失败 | 增加in_accel_x_raw文件存在性fallback |
| F22 | 🟡P1 | shou_ji_nao.py | `glasses_tts()`每次创建pyttsx3引擎(内存泄漏) | 模块级缓存`_get_tts_engine()` |
| F23 | 🟡P1 | san_lian.py | `GlassesArm.speak()` file:// URI被Android 12+阻止; `sense()`设备检测不精确 | 加`--grant-read-uri-permission`; 精确行解析 |
| F24 | 🟡P1 | rayneo_五感.py | tinycap录音设备号硬编码为0(不存在)且无权限 | 自动探测PCM设备号+su提权+空录音检测 |

### E2E验证结果
| 感官 | 测试项 | 结果 | 备注 |
|------|--------|------|------|
| 视觉 | 截屏拍照 | ✅ | screencap → captures/cap_*.png |
| 听觉 | TTS播报 | ✅ | pyttsx3 → wav → push → 眼镜播放 |
| 听觉 | 麦克风录音 | ⚠️ | PCM设备被AISpeech独占(硬件限制) |
| 触觉 | TP事件设备 | ✅ | cyttsp5_mt /dev/input/event3 |
| 触觉 | 按钮事件 | ✅ | gpio-keys /dev/input/event1 |
| 空间 | IMU传感器 | ✅ | lsm6dsr Accel+Gyro via dumpsys(IIO需root) |
| 环境 | 光照传感器 | ✅ | stk_stk3x3x存在(无App监听时返回-1正常) |
| 环境 | 佩戴检测 | ✅ | Hall传感器 /dev/input/event0 |
| 系统 | 电量 | ✅ | 100% |
| 系统 | 设备在线 | ✅ | 841571AC688C360 |
| 系统 | AI问答 | ✅ | 通义千问qwen-turbo已接入(需DASHSCOPE_API_KEY) |

### 已知硬件限制
- **麦克风PCM独占**: AISpeech服务占用pcmC0D8c，tinycap即使su提权也录0帧
- **IIO sysfs需root**: name文件不可读，已fallback到dumpsys sensorservice
- **WiFi未连接**: wlan0 state DOWN，Phase 2(WiFi直连)受阻
- **光照需App监听**: dumpsys仅在有App注册listener时输出实时value

## 系统逆向工程报告 (2026-03-05)

详见 `V3_SYSTEM_REVERSE_ENGINEERING.md`，包含：

- **硬件架构**: 骁龙AR1 SoC + 5传感器 + 3麦+双扬声器 + IMX681相机
- **系统软件**: Android 12裁剪(无SystemUI/Launcher) + 3个evdev输入设备
- **SDK API树**: MarsSDK 8个核心模块 + 3个广播接口
- **开放平台**: 三产品线对比(X/V/AIR) + NativeModule API + AI Studio
- **五感映射**: 触觉95% > 视觉85% > 听觉80% > 空间75% > 环境50%
- **问题清单**: 3个P0 + 5个P1 + 4个P2
- **系统架构图**: 硬件→内核→框架→SDK→应用 五层全景

## F25: WiFi ADB 无线连接 (2026-03-05)

**目标**: 脱离有线ADB夹具，实现长时间无线调试

### 配置
| 项目 | 值 |
| --- | --- |
| WiFi SSID | 周老板的WiFi (WPA2-PSK) |
| 眼镜IP | 192.168.31.116 |
| PC IP | 192.168.31.55 |
| ADB端口 | 5555 |
| 持久化 | persist.adb.tcp.port=5555 (su设置) |
| WiFi保存 | Network ID 0, 重启自动连接 |
| 信号质量 | WiFi 6 5GHz, RSSI -37dBm, 576Mbps |

### 代码修改 (7文件 → wireless_config统一管理)
- `rayneo_五感.py`: 删除重复ADB/检测代码 → `from wireless_config import wm, ADB`
- `san_lian.py`: 同上
- `shou_ji_nao.py`: 同上
- `rayneo_dashboard.py`: 同上
- `rayneo_dashboard.html`: 硬编码brainAddr → 动态fetch
- `phone_server.py`: docstring去除硬编码IP
- `→启动五感引擎.cmd`: `adb connect 硬编码IP` → `python wireless_config.py --detect`

### 验证结果
- ✅ WiFi ADB连接稳定
- ✅ `--battery` 通过WiFi获取电量100%
- ✅ `--sense` 五感自检全部通过
- ✅ screencap + pull 文件传输正常
- ⚠️ ADB daemon重启会断开WiFi连接，代码已含自动重连逻辑

## F26: 虚拟仿真器 v1.0 (2026-03-05)

**目标**: 脱离物理设备，网页端模拟V3全部五感，加快开发迭代

### 架构
```
[Browser UI :8766] ←WebSocket→ [Python Bridge :8765] ←→ [五感引擎(待对接)]
```

### 文件
- `rayneo_sim_server.py` — WebSocket桥接+HTTP静态服务 (196行)
- `rayneo_simulator.html` — 单文件仿真器UI (420行)

### 仿真能力 (7/7 E2E PASS)
- ✅ 触控: 5手势按钮 + 触控板拖拽
- ✅ 按钮: Action/Vol+/Vol-/Long Press
- ✅ IMU: 键盘方向键→accel→head_pose推断
- ✅ TTS: Web Speech API中文朗读 + HUD显示
- ✅ 环境: 光照/电量/亮度滑块 + 佩戴开关
- ✅ 拍照: 虚拟拍照事件
- ✅ 语音: 文本输入模拟

### 启动
```bash
pip install websockets
python rayneo_sim_server.py
# → http://localhost:8766/rayneo_simulator.html
```
