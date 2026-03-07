# OSR6 × VaM 饮料摇匀器 — 全景资源中枢

> OSR (Open Source Stroker Robot) 系列 × Virt-A-Mate 联动项目
> 硬件构建 + 固件烧录 + VaM实时联动 + Funscript播放

## 项目概览

**OSR6/SR6** 是由 [TempestMAx](https://www.patreon.com/tempestvr) 设计的6轴开源机器人，
通过 **TCode协议** 与 VaM (Virt-A-Mate) 实时联动，实现角色动作→物理设备的同步驱动。

```text
VaM 场景 ──ToySerialController──→ TCode ──Serial/WiFi/BLE──→ ESP32 ──PWM──→ 6个舵机
                                                                           ↓
Funscript ──MultiFunPlayer──→ TCode ──────────────────────────────→ 物理运动
                  ↑                                                        ↑
Stash/XBVR ──脚本匹配──→ 多轴funscript                    Buttplug.io/Intiface
                  ↑
视频 ──MediaPipe姿态估计──→ 骨骼→TCode映射 ──→ 自动生成funscript
```

## TCode 6轴映射

| 轴 | TCode | 名称 | 运动方向 | 范围 |
|----|-------|------|---------|------|
| L0 | `L0xxxx` | Stroke | 上下行程 | 0-9999 (5000=中位) |
| L1 | `L1xxxx` | Surge | 前后推进 | 0-9999 |
| L2 | `L2xxxx` | Sway | 左右摆动 | 0-9999 |
| R0 | `R0xxxx` | Twist | 旋转扭转 | 0-9999 |
| R1 | `R1xxxx` | Roll | 横滚 | 0-9999 |
| R2 | `R2xxxx` | Pitch | 俯仰 | 0-9999 |

**TCode示例**: `L09999I1000` = L0轴移到最大位置，用时1000ms

## 资源索引

### 1. 硬件设计 (3D打印 + BOM)

| 资源 | 链接 | 说明 |
|------|------|------|
| **SR6 构建指南** | [Patreon/TempestVR](https://www.patreon.com/tempestvr) | 官方STL+BOM+组装说明 (Patron专属) |
| **OSR2++ Thingiverse** | [thing:5169813](https://www.thingiverse.com/thing:5169813) | 紧凑型OSR2+改进版 (免费) |
| **3D模型搜索** | [yeggi.com/q/osr2+osr6](https://www.yeggi.com/q/osr2+osr6/) | 22个可打印模型 |
| **OSR Wiki - SR6** | [osr.wiki/books/sr6](https://www.osr.wiki/books/sr6) | 官方Wiki (BOM+概览+挂载) |
| **构建教程** | [studylib.net/doc/28302096](https://studylib.net/doc/28302096/sr6-build-instructions) | SR6详细组装指南缓存 |
| **OSR Wiki - 概览** | [osr.wiki/books/sr6/page/overview](https://www.osr.wiki/books/sr6/page/overview) | SR6是什么 |

### 2. 固件 (ESP32)

| 仓库 | 链接 | 特点 |
|------|------|------|
| **TCodeESP32** ⭐ | [jcfain/TCodeESP32](https://github.com/jcfain/TCodeESP32) | 主流固件，Serial+WiFi+BT |
| **TCodeESP32-SR6MB** | [Diy6bot/TCodeESP32-SR6MB](https://github.com/Diy6bot/TCodeESP32-SR6MB) | SR6主板专用版 v1.38b |
| **osr-esp32** | [ayvasoftware/osr-esp32](https://github.com/ayvasoftware/osr-esp32) | BLE增强版 |
| **osr-esp32-s3** | [BQsummer/osr-esp32-s3](https://github.com/BQsummer/osr-esp32-s3) | ESP32-S3适配，默认OSR6模式 |
| **MiraBot固件** | [mirabotx.com/guide](https://mirabotx.com/guide-osr-compatible-firmware/) | 可视化刷写工具 |

### 3. 通信协议

| 资源 | 链接 | 说明 |
|------|------|------|
| **TCode规范** | [multiaxis/TCode-Specification](https://github.com/multiaxis/TCode-Specification) | 官方协议文档 |
| **OSR Wiki - TCode** | [osr.wiki/...tcode](https://www.osr.wiki/books/communication-protocols/page/tcode) | 协议详解 |

### 4. VaM 集成

| 资源 | 链接 | 说明 |
|------|------|------|
| **ToySerialController** ⭐ | [hub.virtamate.com/19853](https://hub.virtamate.com/resources/toyserialcontroller.19853/) | VaM官方插件，Serial+UDP TCode输出 |
| **百度贴吧教程** | [tieba.baidu.com/p/9218988520](https://tieba.baidu.com/p/9218988520) | VaM连接OSR的几个方法 |

### 5. Funscript 播放器

| 播放器 | 链接 | 平台 |
|--------|------|------|
| **MultiFunPlayer** ⭐ | [GitHub](https://github.com/Yoooi0/MultiFunPlayer) | Windows，多轴同步 |
| **XTPlayer** | [EroScripts](https://discuss.eroscripts.com) | 跨平台浏览器播放器 |
| **FunPlayer** | macOS | macOS专用 |
| **ScriptAxis** | [scriptaxis.com](https://scriptaxis.com) | Funscript资源库 |
| **FapTap** | [faptap.net](https://faptap.net) | 在线单轴播放 |

### 6. 社区

| 社区 | 链接 | 说明 |
|------|------|------|
| **EroScripts** | [discuss.eroscripts.com](https://discuss.eroscripts.com) | 主论坛 (脚本+硬件+教程) |
| **Reddit/VAMscenes** | [r/VAMscenes](https://www.reddit.com/r/VAMscenes/) | VaM场景分享 |
| **OSR Wiki** | [osr.wiki](https://www.osr.wiki/) | 官方知识库 |
| **Bilibili** | [VRC+OSR6演示](https://www.bilibili.com/video/BV1gz9VYAEaS/) | 中文实战演示 |
| **百度贴吧** | [osr交流吧](https://tieba.baidu.com/f?kw=osr%E4%BA%A4%E6%B5%81) | 中文社区 |

### 7. 商业购买 (成品)

| 商家 | 链接 | 说明 |
|------|------|------|
| **YourHobbiesCustomized** | [yourhobbiescustomized.com](https://yourhobbiescustomized.com) | OSR2/SR6成品 |
| **Genijoy SR3** | 百度搜索 | 商业级OSR |

## 硬件BOM (SR6)

### 电子元件

| 组件 | 型号 | 数量 | 说明 |
|------|------|------|------|
| **MCU** | ESP32 DevKit V1 | 1 | 主控板 |
| **舵机** | MG996R / DS3218 | 6 | 20kg扭矩推荐 |
| **电源** | 5V 10A+ | 1 | 舵机供电 |
| **升压/降压模块** | 5V稳压 | 1 | 如用12V电源 |
| **杜邦线** | 公对母 | ~20 | 接线 |
| **USB线** | Micro USB | 1 | ESP32编程/通信 |

### 机械件

| 组件 | 规格 | 数量 |
|------|------|------|
| **3D打印件** | PLA/PETG | ~15件 |
| **轴承** | 608ZZ (8×22×7mm) | 6 |
| **M3螺丝** | 各种长度 | ~40 |
| **M4螺丝** | 25mm (VESA挂载) | 4 |
| **弹簧** | 拉伸弹簧 | 2 |

## 软件架构 (本项目)

```
ORS6-VAM饮料摇匀器/
├── README.md              ← 全景索引 (本文件)
├── AGENTS.md              ← Agent操作手册
├── requirements.txt       ← Python依赖
│
├── tcode/                 ← TCode通信库
│   ├── __init__.py
│   ├── protocol.py        ← TCode协议编解码
│   ├── serial_conn.py     ← USB串口连接
│   ├── wifi_conn.py       ← WiFi UDP连接
│   ├── ble_conn.py        ← BLE蓝牙连接
│   └── buttplug_conn.py   ← Buttplug.io/Intiface Central集成
│
├── vam_bridge/            ← VaM联动桥接
│   ├── __init__.py
│   ├── bridge.py          ← VaM→TCode实时桥接
│   └── config.py          ← 连接配置
│
├── funscript/             ← Funscript解析播放
│   ├── __init__.py
│   ├── parser.py          ← .funscript JSON解析
│   └── player.py          ← 多轴同步播放器 (含SafetyConfig硬件保护)
│
├── video_sync/            ← 视频同步集成
│   ├── __init__.py
│   ├── pipeline.py        ← 端到端管道 (Stash+XBVR+URL→设备)
│   ├── video_fetcher.py   ← 多平台视频下载 (抖音/TikTok/YouTube/Bilibili)
│   ├── beat_sync.py       ← 音频节拍→Funscript生成 (多轴+多曲线)
│   ├── funscript_analyzer.py ← 脚本分析 (强度/热力图/章节/质量)
│   ├── xbvr_client.py     ← XBVR REST API (VR场景/演员/脚本匹配)
│   ├── mfp_client.py      ← MultiFunPlayer WebSocket + DeoVR/HereSphere监控
│   ├── stash_client.py    ← Stash GraphQL API (场景/标签/脚本匹配)
│   ├── funscript_naming.py← 多轴funscript命名规范 (10轴映射)
│   └── motion_tracker.py  ← MediaPipe姿态估计→TCode 6轴映射
│
├── tools/                 ← 工具脚本
│   ├── flash_firmware.py  ← ESP32固件烧写辅助
│   ├── servo_test.py      ← 舵机逐轴测试
│   └── calibrate.py       ← 轴校准工具
│
├── firmware/              ← 固件参考 (git submodule或说明)
│   └── README.md          ← 固件选择指南
│
├── 3d_models/             ← 3D模型说明
│   └── README.md          ← 模型获取指南
│
└── docs/                  ← 文档
    ├── TCODE_REFERENCE.md  ← TCode协议参考
    ├── VAM_SETUP.md        ← VaM配置指南
    ├── VIDEO_SYNC.md       ← 视频同步全景方案
    ├── TROUBLESHOOTING.md  ← 常见问题
    └── GITHUB_RESOURCES.md ← **30+GitHub生态仓库索引**
```

## 快速开始

### 1. 硬件准备
```bash
# 硬件组装步骤
# 1. 3D打印零件 (从Patreon/Thingiverse获取STL)
# 2. 购买电子元件 (见上方BOM)
# 3. 组装SR6
# 4. 烧录ESP32固件
```

### 2. 安装Python库
```bash
pip install -r requirements.txt
```

### 3. 测试连接
```python
from tcode import TCodeSerial

# USB串口连接
dev = TCodeSerial(port="COM5", baudrate=115200)
dev.connect()

# 舵机归中位
dev.home_all()

# 单轴控制
dev.move(axis="L0", position=9999, interval=1000)  # L0轴移到最大，1秒
```

### 4. VaM联动
```python
from vam_bridge import VaMTCodeBridge

bridge = VaMTCodeBridge(
    vam_host="127.0.0.1",
    vam_port=8084,
    tcode_port="COM5"
)
bridge.start()  # 开始实时同步
```

### 5. Funscript播放
```python
from funscript import FunscriptPlayer

player = FunscriptPlayer(port="COM5")
player.load("video.funscript")
player.play()  # 同步播放
```

### 6. 视频同步 (MultiFunPlayer + Stash)
```python
from video_sync import MultiFunPlayerClient, StashClient, FunscriptNaming

# 连接MultiFunPlayer获取播放状态
import asyncio
client = MultiFunPlayerClient()  # ws://127.0.0.1:8088
await client.connect()
print(f"播放中: {client.playback_state.is_playing}")

# 查询Stash媒体库中有脚本的场景
stash = StashClient(port=9999)
scenes = stash.find_interactive_scenes()
for s in scenes:
    scripts = FunscriptNaming.find_scripts_for_video(s.path)
    print(f"{s.title}: {len(scripts)}轴脚本")
```

### 7. 一键播放管道 (Stash → 脚本匹配 → 设备)
```python
from video_sync import SyncPipeline, SyncConfig

pipe = SyncPipeline(SyncConfig(
    stash_port=9999,
    device_port="COM5",
    script_dirs=["D:/funscripts/"],  # 额外脚本搜索目录
))

# 从Stash发现有脚本的场景
scenes = pipe.discover_scenes(interactive_only=True)
for s in scenes:
    print(s.summary())  # "Title [120s] — 3轴(L0, R0, R1)"

# 一键播放
pipe.play_scene(scenes[0])
```

### 8. 脚本分析 (强度/热力图/章节)
```python
from video_sync import FunscriptAnalyzer

analyzer = FunscriptAnalyzer()
report = analyzer.analyze_multi("video.funscript")  # 自动发现多轴
print(report.summary)     # 强度/速度/行程统计
print(report.heatmap_ascii())  # ASCII热力图
# 自动章节: [00:00] 缓慢 → [02:30] 激烈 → [05:00] 极限
```

### 9. XBVR VR场景管理
```python
from video_sync import XBVRClient

xbvr = XBVRClient(port=9999)
# 查找有脚本的VR场景
scripted = xbvr.find_scripted_scenes()
for s in scripted:
    print(s.summary())  # "[1] Title (5min) — Performer [VR 6K] ✓脚本"

# 按演员搜索
scenes = xbvr.find_scenes_by_cast("performer_name", scripted_only=True)

# 库统计
stats = xbvr.get_stats()
print(f"总计: {stats['total_scenes']}场景, 脚本覆盖: {stats['script_coverage']}")
```

### 10. 全源发现 (Stash + XBVR + 本地)
```python
from video_sync import SyncPipeline, SyncConfig

pipe = SyncPipeline(SyncConfig(
    stash_port=9999,
    xbvr_port=9998,
    script_dirs=["D:/funscripts/"],
))

# 从所有来源发现，自动去重
all_scenes = pipe.discover_all(scripted_only=True)
for s in all_scenes:
    print(f"[{s.source}] {s.summary()}")
```

### 11. 音乐节拍 → Funscript自动生成
```python
from video_sync import BeatSyncer, BeatSyncConfig

# 基本用法: 音频→节拍检测→funscript
syncer = BeatSyncer()
result = syncer.generate("music.wav")
result.save("music.funscript")  # 120BPM, 240动作

# 多轴: 低频→L0 中频→R0 高频→V0
multi = syncer.generate_multi("music.wav")
multi.save_all("output/", "music")

# 半拍+弹跳曲线
syncer = BeatSyncer(BeatSyncConfig(
    beat_divisor=2, intensity_curve="bounce"
))
```

### 12. 抖音/TikTok URL → 设备一键同步
```python
from video_sync import SyncPipeline, SyncConfig

pipe = SyncPipeline(SyncConfig(
    beat_mode="beat",
    beat_divisor=1,
    proxy="http://127.0.0.1:7890",  # 可选代理
))

# 一键全链路: URL → 下载 → 节拍分析 → funscript → 设备播放
chain = pipe.url_to_device("https://v.douyin.com/xxxxx")
print(chain['analysis'])  # {tempo: 128, beats: 64, ...}

# 仅生成funscript不播放
chain = pipe.url_to_funscript("https://www.tiktok.com/@user/video/xxx")
print(chain['funscripts'])  # {'L0': 'downloads/video.funscript'}
```

### 13. AI运动追踪 → funscript生成 (实验性)
```python
from video_sync import MotionTracker, TrackerConfig

# pip install mediapipe opencv-python
tracker = MotionTracker(TrackerConfig(stroke_sensitivity=2.5))
output = tracker.video_to_funscripts("video.mp4", "output/")
# 生成: video.funscript, video.surge.funscript, video.twist.funscript ...
```

## EroScripts 社区资源导航

> 论坛地址: https://discuss.eroscripts.com (可能需要VPN)
> 详细索引: [docs/EROSCRIPTS_RESOURCES.md](docs/EROSCRIPTS_RESOURCES.md) — 设备/固件/播放器/工具/硬件购买/VaM插件

### 关键帖子

| 帖子 | 链接 | 内容 |
|------|------|------|
| **入门指南** | [/t/158805](https://discuss.eroscripts.com/t/guide-what-is-the-osr2-sr6-ssr1-and-how-do-i-get-one/158805) | OSR2/SR6/SSR1是什么+如何获取 |
| **脚本入门** | [/t/2234](https://discuss.eroscripts.com/t/how-to-get-started-with-scripting/2234) | Funscript制作教程 |
| **SR6 3D打印** | [/t/76533](https://discuss.eroscripts.com/t/getting-started-with-3d-printing-sr6/76533) | 3D打印入门 |
| **MultiFunPlayer** | [/t/23006](https://discuss.eroscripts.com/t/multifunplayer-v1-29-4-multi-axis-funscript-player-now-with-slr-interactive-support/23006) | 最全多轴播放器 |
| **MiraPlay AiO** | [/t/287825](https://discuss.eroscripts.com/t/miraplay-aio-smart-engine-for-osr-devices-updates-inside/287825) | OSR智能引擎 |

### 论坛分类
- **DIY** — 硬件构建、改装、3D打印
- **Scripts** — Funscript脚本分享
- **Software** — 播放器、插件开发 (MultiFunPlayer/XTPlayer/MiraPlay/Ayva)
- **Help** — 技术支持

### 硬件购买渠道
- **YourHobbiesCustomized** — [yourhobbiescustomized.com](https://yourhobbiescustomized.com/) (美国, 社区首选)
- **FunOSR** — [funosr.com](https://www.funosr.com/) / [AliExpress](https://www.aliexpress.com/store/1103361043) (中国)
- **MiraBot S6** — 精密安静6轴SR6进化版

## VaM集成方式 (4种)

| 方式 | 延迟 | 多轴 | 说明 |
|------|------|------|------|
| **ToySerialController** | ★★★ | 6轴 | VaM内置插件，Serial+UDP直连 |
| **MultiFunPlayer** (226⭐) | ★★★ | 6轴 | 独立播放器，支持VaM/DeoVR/HereSphere |
| **Buttplug.io/Intiface** (216⭐) | ★★ | 设备依赖 | 通用设备抽象层，本项目已集成 |
| **ScriptPlayer** (209⭐) | ★★ | 1轴 | 视频+Funscript同步播放器 |
| **Stash** (11933⭐) | ★★★ | — | 媒体管理+脚本匹配 (本项目已集成GraphQL) |
| **DeoVR** | ★★★ | — | VR播放器 (本项目已集成状态监控) |

> 详见 [docs/VAM_SETUP.md](docs/VAM_SETUP.md) | 视频同步见 [docs/VIDEO_SYNC.md](docs/VIDEO_SYNC.md) | 生态资源见 [docs/GITHUB_RESOURCES.md](docs/GITHUB_RESOURCES.md)

## 许可证

本项目工具代码: MIT
OSR/SR6硬件设计: 见TempestMAx Patreon条款
TCode协议: 开源
