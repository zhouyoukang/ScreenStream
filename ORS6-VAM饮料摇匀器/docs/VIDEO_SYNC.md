# 视频同步全景指南 — OSR设备 × 网络视频 × VR资源

> 从视频到物理运动的完整同步链路：视频源 → 脚本 → 播放器 → TCode → 设备

## 同步架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    视频/VR 资源层                         │
│  本地视频 │ DeoVR │ HereSphere │ VLC │ Plex │ Jellyfin  │
│  XBVR(450⭐) │ Stash(11933⭐) │ Quest 3 Streaming      │
└─────────────┬───────────────────────────────────────────┘
              │ API / 文件路径
┌─────────────▼───────────────────────────────────────────┐
│                    脚本生成/获取层                        │
│  手动: OFS(135⭐) │ ScriptAxis │ EroScripts社区         │
│  AI:  FunGen(150⭐) │ Funscript-Flow(64⭐)              │
│  CV:  Python-Funscript-Editor(77⭐) │ MediaPipe姿态估计  │
└─────────────┬───────────────────────────────────────────┘
              │ .funscript 文件 (多轴)
┌─────────────▼───────────────────────────────────────────┐
│                    播放/同步层                            │
│  MultiFunPlayer(226⭐) — 多轴同步标杆                    │
│  ScriptPlayer(209⭐) — 视频+脚本同步                     │
│  VaM ToySerialController — VaM场景实时联动               │
│  本项目 funscript/player.py — Python原生播放             │
└─────────────┬───────────────────────────────────────────┘
              │ TCode / Buttplug协议
┌─────────────▼───────────────────────────────────────────┐
│                    设备通信层                             │
│  Serial(USB) │ WiFi(UDP) │ BLE │ Buttplug/Intiface      │
│  本项目 tcode/ + buttplug_conn.py                        │
└─────────────┬───────────────────────────────────────────┘
              │ PWM信号
┌─────────────▼───────────────────────────────────────────┐
│              ESP32 → 6轴舵机 → 物理运动                  │
└─────────────────────────────────────────────────────────┘
```

## 一、视频播放器集成

### 1.1 MultiFunPlayer (226⭐) — 核心中枢

**支持的视频播放器** (12个):
| 播放器 | 类型 | 连接方式 | VR支持 |
|--------|------|---------|--------|
| **DeoVR** | VR播放器 | WebSocket API | ✅ 6DoF |
| **HereSphere** | VR播放器(Steam) | Remote Control API | ✅ 6DoF |
| **Whirligig** | VR媒体播放器 | Remote Server | ✅ |
| **MPV** | 通用播放器 | IPC Socket | ❌ |
| **MPC-HC/BE** | Windows播放器 | Web Interface | ❌ |
| **VLC** | 通用播放器 | HTTP API | ❌ |
| **PotPlayer** | Windows播放器 | API | ❌ |
| **OFS** | 脚本编辑器 | WebSocket | ❌ |
| **Plex** | 媒体服务器 | API | ❌ |
| **Emby** | 媒体服务器 | API | ❌ |
| **Jellyfin** | 开源媒体服务器 | API | ❌ |
| **内置播放器** | 无视频脚本播放 | 直接 | ❌ |

**支持的输出** (8种): Buttplug.io / TCP / UDP / WebSocket / NamedPipe / Serial / File / The Handy

**脚本库**: XBVR / Stash 自动匹配

**高级功能**:
- 多轴同步 (L0-L2, R0-R2, V0, A0-A2)
- PCHIP/Makima 插值平滑
- 轴速度限制 + 自动归位
- Smart Limit (轴间联动限速)
- Soft Start (防突然运动)
- 书签和章节支持
- C# 插件系统

### 1.2 DeoVR — VR视频播放

**平台**: PC VR / Quest / Gear VR / Daydream
**连接**: MultiFunPlayer通过WebSocket监听DeoVR播放状态

```
DeoVR设置 → Remote Control → 启用 → 端口23554
MultiFunPlayer → 添加DeoVR → ws://127.0.0.1:23554
```

**SLR Interactive** (Patreon功能): 直接从SLR流媒体获取同步脚本

### 1.3 HereSphere — 高级VR播放器

**平台**: SteamVR (PC VR + Quest Link)
**特点**: 内置脚本支持、时间轴编辑、远程控制API
**连接**: MultiFunPlayer通过远程控制协议

```
HereSphere设置 → 远程控制 → 启用
MultiFunPlayer → 添加HereSphere → 自动发现
```

### 1.4 Quest 3 独立模式

**方案A**: DeoVR Quest版 + 无线串流
**方案B**: HereSphere Quest Link
**方案C**: FunGen Streamer → Quest 3 (Ko-fi附加功能)
**方案D**: XBVR DLNA → Quest浏览器

## 二、媒体管理与脚本匹配

### 2.1 XBVR (450⭐) — VR视频管理器

**功能**: 视频整理 / 元数据刮削 / DLNA流媒体 / 脚本匹配
**部署**: Docker / 树莓派 / Windows
**API**: REST API 用于视频查询和管理
**与MultiFunPlayer集成**: 作为脚本库自动匹配

```bash
# Docker部署
docker run -d --name xbvr -p 9999:9999 -v /path/to/videos:/videos xbapps/xbvr
```

### 2.2 Stash (11933⭐) — 通用媒体管理

**功能**: 元数据管理 / 标签 / 过滤 / GraphQL API / 场景匹配
**部署**: 跨平台独立应用
**API**: GraphQL (端口9999)
**与FunGen集成**: 直接连接获取场景列表

```graphql
# Stash GraphQL 查询场景
query {
  findScenes(filter: { per_page: 10 }) {
    scenes { id title path files { path } }
  }
}
```

### 2.3 Funscript 文件命名规范

MultiFunPlayer标准 (所有播放器通用):

| 轴 | 文件名 | 说明 |
|----|--------|------|
| L0 | `video.funscript` | 上下行程 (主轴) |
| L1 | `video.surge.funscript` | 前后推进 |
| L2 | `video.sway.funscript` | 左右摆动 |
| R0 | `video.twist.funscript` | 旋转扭转 |
| R1 | `video.roll.funscript` | 横滚 |
| R2 | `video.pitch.funscript` | 俯仰 |
| V0 | `video.vib.funscript` | 振动 |
| A0 | `video.valve.funscript` | 气阀 |
| A1 | `video.suck.funscript` | 吸力 |
| A2 | `video.lube.funscript` | 润滑 |

### 2.4 脚本获取渠道

| 渠道 | 链接 | 特点 |
|------|------|------|
| **ScriptAxis** | scriptaxis.com | 搜索引擎,按场景/演员查 |
| **EroScripts** | discuss.eroscripts.com | 社区分享,DIY区 |
| **SLR** | sexlikereal.com | 官方脚本+Interactive |
| **FapTap** | faptap.net | 在线播放+脚本 |
| **XBVR** | 本地部署 | 自动匹配刮削 |

## 三、AI自动生成 Funscript — 人物动作同步

### 3.1 FunGen AI (150⭐) — 最强AI方案

**核心能力**:
- AI视觉分析VR/2D POV视频 → 自动生成funscript
- **多轴支持**: stroke/roll/pitch/surge/sway/twist 全6轴
- 14+ 内置滤波器插件 (自动调优/RDP简化/速度限制/反抖动等)
- 批量处理整个文件夹
- 设备控制: OSR/Buttplug 实时硬件控制
- VR串流: HereSphere/Quest 3 直接串流

**安装**:
```bash
# Windows一键安装
curl -o install.bat https://raw.githubusercontent.com/ack00gar/FunGen-AI-Powered-Funscript-Generator/main/install.bat
install.bat
# 需要: NVIDIA GPU (20xx+), CUDA 12.8, Python 3.11
```

**与本项目集成**:
```python
# FunGen生成的funscript可直接用本项目播放
from funscript import FunscriptPlayer
player = FunscriptPlayer(port="COM5")
player.load("video.funscript")        # L0 主轴
player.load("video.roll.funscript")   # R1 横滚
player.play()
```

### 3.2 Python-Funscript-Editor (77⭐) — OpenCV运动追踪

**核心能力**:
- OpenCV运动追踪 → 半自动funscript生成
- 可视化编辑器
- 手动校正+自动追踪结合

### 3.3 Funscript-Flow (64⭐) — 计算机视觉

**核心能力**:
- 纯CV方案，无需GPU
- 光流/运动检测 → funscript
- 适合简单场景

### 3.4 自定义姿态估计 → TCode (实验性)

**方案**: MediaPipe/OpenPose → 骨骼关键点 → 运动幅度 → TCode命令

```python
# 概念验证: MediaPipe姿态 → TCode
import mediapipe as mp
import cv2

mp_pose = mp.solutions.pose
pose = mp_pose.Pose()

cap = cv2.VideoCapture("video.mp4")
while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break
    results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    if results.pose_landmarks:
        # 骨盆Y位置 → L0 (行程)
        hip_y = results.pose_landmarks.landmark[mp_pose.PoseLandmark.LEFT_HIP].y
        l0_pos = int((1.0 - hip_y) * 9999)  # 反转Y轴
        
        # 肩膀旋转 → R0 (扭转)
        l_shoulder = results.pose_landmarks.landmark[mp_pose.PoseLandmark.LEFT_SHOULDER]
        r_shoulder = results.pose_landmarks.landmark[mp_pose.PoseLandmark.RIGHT_SHOULDER]
        twist = (l_shoulder.z - r_shoulder.z) * 5000 + 5000
        r0_pos = int(max(0, min(9999, twist)))
```

**限制**: 
- 2D视频姿态估计精度有限 (Z轴深度不准)
- VR 180°/360°视频需要特殊处理
- 实时性取决于GPU性能
- **推荐使用FunGen AI** (已优化的完整方案)

## 四、同步方案选择指南

### 4.1 按使用场景选择

| 场景 | 推荐方案 | 工具链 |
|------|---------|--------|
| **已有脚本的视频** | MultiFunPlayer | 视频播放器 → MFP → Serial/Buttplug → 设备 |
| **VR视频+已有脚本** | DeoVR + MultiFunPlayer | DeoVR → MFP → 设备 |
| **无脚本视频** | FunGen AI生成 | FunGen → .funscript → MFP → 设备 |
| **VaM实时场景** | ToySerialController | VaM → TSC → Serial → 设备 |
| **VaM + 本项目** | AgentBridge | VaM → AgentBridge API → Python → 设备 |
| **Quest 3独立** | DeoVR Quest + WiFi | DeoVR → WiFi → MFP(PC) → 设备 |
| **自定义Python** | 本项目 | video_sync/ → funscript/ → tcode/ → 设备 |

### 4.2 按延迟要求选择

| 方案 | 延迟 | 说明 |
|------|------|------|
| Serial直连 | <10ms | 最低延迟 |
| WiFi UDP | 10-50ms | 局域网内 |
| MultiFunPlayer | 20-50ms | 含插值平滑 |
| Buttplug/Intiface | 30-80ms | 多一层协议 |
| WiFi + Quest 3 | 50-150ms | 无线VR |
| The Handy (蓝牙) | 100-300ms | 蓝牙固有延迟 |

## 五、完全同步 — 人物动作→设备运动

### 5.1 什么是"完全同步"

**目标**: 视频/VR中角色的每一个动作都精确映射到物理设备的对应轴运动。

**6轴映射关系**:
| 人物动作 | TCode轴 | 设备运动 |
|----------|---------|---------|
| 骨盆上下 | L0 Stroke | 行程往复 |
| 骨盆前后 | L1 Surge | 前后推进 |
| 骨盆左右 | L2 Sway | 左右摆动 |
| 髋部旋转 | R0 Twist | 扭转 |
| 身体侧倾 | R1 Roll | 横滚 |
| 身体前倾 | R2 Pitch | 俯仰 |

### 5.2 实现路径

**路径1: 预制脚本 (最成熟)**
```
专业脚本制作者 → OFS手动标记6轴 → 多轴.funscript → MultiFunPlayer
```
- 优点: 精确、流畅、已验证
- 缺点: 每个视频需人工制作 (30分钟视频约需2-4小时)

**路径2: AI自动生成 (最有前景)**
```
FunGen AI → 视频分析 → 多轴funscript自动生成 → 播放器 → 设备
```
- 优点: 全自动、批量处理、支持6轴
- 缺点: 准确度不如人工、需要GPU

**路径3: VaM实时 (最灵活)**
```
VaM场景 → 角色骨骼实时数据 → ToySerialController/AgentBridge → TCode
```
- 优点: 真正实时、交互式、可自定义
- 缺点: 仅限VaM场景

**路径4: 自定义CV (实验性)**
```
视频 → MediaPipe姿态估计 → 骨骼关键点 → 自定义映射 → TCode
```
- 优点: 完全可控、可定制
- 缺点: 开发工作量大、精度有限

### 5.3 当前生态成熟度评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 预制脚本播放 | ⭐⭐⭐⭐⭐ | MultiFunPlayer完美支持 |
| VR播放器集成 | ⭐⭐⭐⭐ | DeoVR/HereSphere API成熟 |
| 媒体管理 | ⭐⭐⭐⭐ | XBVR/Stash功能强大 |
| AI脚本生成 | ⭐⭐⭐ | FunGen v0.6进步快但仍在早期 |
| 多轴同步 | ⭐⭐⭐ | 6轴脚本稀缺,大多只有L0 |
| 实时姿态同步 | ⭐⭐ | 研究阶段,无成熟方案 |

## 六、本项目集成计划

### 已完成
- ✅ TCode协议全轴支持 (L0-L2, R0-R2, V0-V1, A0-A2)
- ✅ Funscript解析+多轴播放器
- ✅ VaM桥接 (AgentBridge + TSC)
- ✅ Buttplug.io WebSocket集成
- ✅ 多轴funscript文件命名兼容

### 可扩展
- 📋 MultiFunPlayer WebSocket API集成
- 📋 DeoVR远程控制协议对接
- 📋 Stash GraphQL脚本查询
- 📋 XBVR REST API视频管理
- 📋 FunGen AI Python直接调用
- 📋 MediaPipe姿态估计→TCode管道

## 七、关键链接

| 资源 | 链接 |
|------|------|
| MultiFunPlayer | https://github.com/Yoooi0/MultiFunPlayer |
| FunGen AI | https://github.com/ack00gar/FunGen-AI-Powered-Funscript-Generator |
| XBVR | https://github.com/xbapps/xbvr |
| Stash | https://github.com/stashapp/stash |
| DeoVR | https://deovr.com |
| HereSphere | https://store.steampowered.com/app/1234730/HereSphere/ |
| OFS | https://github.com/OpenFunscripter/OFS |
| ScriptAxis | https://scriptaxis.com |
| EroScripts | https://discuss.eroscripts.com |
| Intiface Central | https://intiface.com/central/ |
