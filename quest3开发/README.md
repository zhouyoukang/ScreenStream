# Meta Quest 3 开发全景资源中枢

> 道生一，一生二，二生三，三生万物。VR/MR是三维世界的入口。
> Agent全链路开发Quest内容——从代码到头显，无需人工干预。

## Live Demos (已部署，Quest浏览器可直接访问)

| Demo | URL | 技术栈 | 功能 |
| ---- | --- | ------ | ---- |
| **Portal** | <https://aiotvr.xyz/quest/> | HTML/CSS | 导航首页+XR检测 |
| **Simulator** | <https://aiotvr.xyz/quest/simulator.html> | HTML/JS+IWER | Quest 3虚拟仿真环境 |
| **Hello VR** | <https://aiotvr.xyz/quest/hello-vr/> | WebGL2原生 | 3D立方体+手部追踪 |
| **MR Passthrough** | <https://aiotvr.xyz/quest/mr-passthrough/> | WebGL2原生 | 透视+浮动球体+手部追踪 |
| **A-Frame Playground** | <https://aiotvr.xyz/quest/aframe-playground/> | A-Frame 1.6 | 声明式3D场景+动画+交互 |
| **Hand Grab Lab** | <https://aiotvr.xyz/quest/hand-grab/> | A-Frame 1.6 | 手部抓取交互+捏合手势+桌面布局 |
| **Shared Space** | <https://aiotvr.xyz/quest/shared-space/> | A-Frame+WebSocket | 多人VR+实时同步+聊天(待部署WS服务) |
| **Smart Home MR** | <https://aiotvr.xyz/quest/smart-home/> | A-Frame+HA WebSocket | 智能家居MR控制(HA实体+3D面板+实时状态) |

## 本地参考项目 (refs/ — 10个)

### 官方 (meta-quest)
| 项目 | 来源 | 用途 |
| ---- | ---- | ---- |
| `refs/ratk/` | meta-quest/reality-accelerator-toolkit | **WebXR MR核心库**(Plane/Anchor/HitTest/Mesh) |
| `refs/webxr-first-steps/` | meta-quest/webxr-first-steps | 官方WebXR入门教程(Three.js) |
| `refs/webxr-first-steps-react/` | meta-quest/webxr-first-steps-react | 官方WebXR入门(React Three Fiber) |
| `refs/ProjectFlowerbed/` | meta-quest/ProjectFlowerbed | **完整WebXR游戏**(花园体验,Three.js) |
| `refs/immersive-web-emulator/` | meta-quest/immersive-web-emulator | **Quest WebXR模拟器**(Chrome扩展,桌面调试) |
| `refs/bubblewrap/` | meta-quest/bubblewrap | **PWA→Quest APK**(TWA打包工具) |

### 社区精华
| 项目 | 来源 | 用途 |
| ---- | ---- | ---- |
| `refs/webxr-handtracking/` | marlon360/webxr-handtracking (213⭐) | 手部追踪示例集(关节可视化+手势) |
| `refs/passtracing/` | fabio914/passtracing (38⭐) | MR画笔/描线(Passthrough+手部追踪) |
| `refs/enva-xr/` | tentone/enva-xr (136⭐) | WebXR AR遮挡+光照+物理+交互(TypeScript) |
| `refs/immersive-home/` | Nitwel/Immersive-Home (550⭐) | Godot 4 MR智能家居(Quest+HA, Apache-2.0) |

## 生态发现 (本轮MCP搜索新增)

| 项目 | ⭐ | 技术栈 | 价值 |
| ---- | -- | ------ | ---- |
| pmndrs/xr | 2571 | React Three Fiber | React生态XR核心库(VR/AR) |
| marlon360/webxr-handtracking | 213 | WebXR原生 | 手部追踪示例集 |
| tentone/enva-xr | 136 | Three.js | AR遮挡+光照+物理+交互 |
| DePasqualeOrg/three-immersive-controls | 39 | Three.js | VR控制器封装 |
| fabio914/passtracing | 38 | WebXR原生 | MR描线画笔 |
| omnidotdev/rdk | 31 | TypeScript | XR统一API(Reality Dev Kit) |
| networked-aframe | — | A-Frame | 多人VR网络(WebRTC+语音) |
| c-frame/aframe-physics-system | — | A-Frame | VR物理引擎(CANNON/Ammo) |

## 开发路径总览

| 路径 | 引擎/框架 | 语言 | Agent可控度 | 推荐场景 |
|------|----------|------|------------|---------|
| **① WebXR** | Three.js / A-Frame / R3F | JS/TS | ⭐⭐⭐⭐⭐ | 快速原型/Web应用/PWA |
| **② Meta Spatial SDK** | Android Studio | Kotlin/Java | ⭐⭐⭐⭐ | 原生MR应用/Horizon OS |
| **③ Unity + Meta XR** | Unity 2022+ | C# | ⭐⭐⭐ | 游戏/复杂3D/商店上架 |
| **④ Unreal + Meta XR** | UE 5.3+ | C++/BP | ⭐⭐ | 高保真渲染/AAA |
| **⑤ Native OpenXR** | C/C++ | C/C++ | ⭐⭐⭐ | 底层性能/自定义引擎 |
| **⑥ Godot XR** | Godot 4.x | GDScript/C# | ⭐⭐⭐ | 开源/轻量级游戏 |

**Agent首选路径: ① WebXR** — 纯代码、无GUI依赖、即时部署、Quest浏览器直接运行。

---

## 一、官方资源 (meta-quest 组织, 17个仓库)

### 核心SDK
| 仓库 | 描述 | 路径 |
|------|------|------|
| [Meta-OpenXR-SDK](https://github.com/meta-quest/Meta-OpenXR-SDK) | Quest全设备Native OpenXR开发资源 | ⑤ Native |
| [Meta-Spatial-SDK-Samples](https://github.com/meta-quest/Meta-Spatial-SDK-Samples) | Spatial SDK示例集(Android原生MR) | ② Spatial |
| [Meta-Spatial-SDK-Templates](https://github.com/meta-quest/Meta-Spatial-SDK-Templates) | Spatial SDK项目模板(Android Studio插件) | ② Spatial |
| [Meta-Horizon-Platform-SDK-Samples](https://github.com/meta-quest/Meta-Horizon-Platform-SDK-Samples) | Horizon平台SDK示例(社交/排行/成就) | ② Spatial |
| [Unity-UtilityPackages](https://github.com/meta-quest/Unity-UtilityPackages) | Meta Unity工具包集合 | ③ Unity |
| [Unity-MCP-Extensions](https://github.com/meta-quest/Unity-MCP-Extensions) | **Unity MCP扩展**(AI/LLM辅助Quest开发) | ③ Unity |

### WebXR (Agent最佳路径)
| 仓库 | 描述 | 价值 |
|------|------|------|
| [webxr-first-steps](https://github.com/meta-quest/webxr-first-steps) | WebXR入门教程(Three.js) | ⭐⭐⭐ 入门必读 |
| [webxr-first-steps-react](https://github.com/meta-quest/webxr-first-steps-react) | WebXR入门(React Three Fiber) | ⭐⭐⭐ React路线 |
| [reality-accelerator-toolkit](https://github.com/meta-quest/reality-accelerator-toolkit) | **RATK** — WebXR MR快速集成工具包 | ⭐⭐⭐⭐⭐ 核心 |
| [immersive-web-emulator](https://github.com/meta-quest/immersive-web-emulator) | Quest设备WebXR模拟器(浏览器扩展) | ⭐⭐⭐⭐ 调试必备 |
| [immersive-web-emulation-runtime](https://github.com/meta-quest/immersive-web-emulation-runtime) | WebXR运行时模拟(JS) | ⭐⭐⭐ 测试 |
| [ProjectFlowerbed](https://github.com/meta-quest/ProjectFlowerbed) | WebXR沉浸式花园体验(完整项目) | ⭐⭐⭐⭐ 参考 |
| [webxr-showcases](https://github.com/meta-quest/webxr-showcases) | WebXR展示项目集 | ⭐⭐⭐ 参考 |
| [bubblewrap](https://github.com/meta-quest/bubblewrap) | PWA→Quest APK打包工具(TWA) | ⭐⭐⭐⭐ 上架必备 |

### 其他
| 仓库 | 描述 |
|------|------|
| [Meta-Passthrough-Camera-API-Samples](https://github.com/meta-quest/Meta-Passthrough-Camera-API-Samples) | Passthrough相机API原生示例 |
| [meta-horizon-worlds-sample-scripts](https://github.com/meta-quest/meta-horizon-worlds-sample-scripts) | Horizon Worlds脚本示例 |
| [orchestrator](https://github.com/meta-quest/orchestrator) | Linux资源管理构建块 |

---

## 二、官方示例 (oculus-samples 组织, 62个仓库)

### Unity 精华 (按能力分类)

#### MR/Passthrough (Quest 3核心能力)
| 仓库 | 描述 | 关键API |
|------|------|---------|
| [Unity-Discover](https://github.com/oculus-samples/Unity-Discover) | MR API全面展示 | Passthrough/SpatialAnchors/SceneAPI/Colocation |
| [Unity-Phanto](https://github.com/oculus-samples/Unity-Phanto) | MR Mesh展示 | Scene Mesh/空间理解 |
| [Unity-TheWorldBeyond](https://github.com/oculus-samples/Unity-TheWorldBeyond) | Presence Platform展示 | Scene/Passthrough/Interaction/Voice |
| [Unity-DepthAPI](https://github.com/oculus-samples/Unity-DepthAPI) | 深度API实时遮挡 | Depth Occlusion |
| [Unity-PassthroughCameraApiSamples](https://github.com/oculus-samples/Unity-PassthroughCameraApiSamples) | Passthrough相机API | Camera Access |

#### 手部追踪 & 交互
| 仓库 | 描述 |
|------|------|
| [Unity-FirstHand](https://github.com/oculus-samples/Unity-FirstHand) | Interaction SDK手部追踪展示 |
| [Unity-Movement](https://github.com/oculus-samples/Unity-Movement) | 身体/眼睛/面部追踪 |
| [Unity-HandsInteractionTrainingModule](https://github.com/oculus-samples/Unity-HandsInteractionTrainingModule) | 手部交互训练模块 |

#### 图形 & 性能
| 仓库 | 描述 |
|------|------|
| [Unity-NorthStar](https://github.com/oculus-samples/Unity-NorthStar) | 顶级图形展示(海盗主题)+AppSpaceWarp |
| [Unity-AppSpaceWarp](https://github.com/oculus-samples/Unity-AppSpaceWarp) | Application SpaceWarp帧率优化 |
| [Unity-AssetStreaming](https://github.com/oculus-samples/Unity-AssetStreaming) | 开放世界资产流式加载 |
| [Unity-ShaderPrewarmer](https://github.com/oculus-samples/Unity-ShaderPrewarmer) | Shader预热(消除首次卡顿) |
| [Unity-CompositorLayers](https://github.com/oculus-samples/Unity-CompositorLayers) | Compositor Layers使用 |
| [Unity-VirtualCameraPublisher](https://github.com/oculus-samples/Unity-VirtualCameraPublisher) | 虚拟相机发布器 |

#### 多人 & 社交
| 仓库 | 描述 |
|------|------|
| [Unity-SharedSpatialAnchors](https://github.com/oculus-samples/Unity-SharedSpatialAnchors) | 共享空间锚点(多人对齐) |
| [Unity-LocalMultiplayerMR](https://github.com/oculus-samples/Unity-LocalMultiplayerMR) | 本地多人MR |
| [Unity-CrypticCabinet](https://github.com/oculus-samples/Unity-CrypticCabinet) | MR密室逃脱(多人+空间理解) |

#### 音频 & AI
| 仓库 | 描述 |
|------|------|
| [Unity-StarterSamples](https://github.com/oculus-samples/Unity-StarterSamples) | 入门示例合集 |
| [Unity-SpatialPlatformTemplate](https://github.com/oculus-samples/Unity-SpatialPlatformTemplate) | 空间平台模板 |

### Unreal 精华
| 仓库 | 描述 |
|------|------|
| [Unreal-Discover](https://github.com/oculus-samples/Unreal-Discover) | UE版MR API展示 |
| [Unreal-MetaXRAudioSDK](https://github.com/oculus-samples/Unreal-MetaXRAudioSDK) | Meta XR音频SDK |
| [Unreal-AppSpaceWarp](https://github.com/oculus-samples/Unreal-AppSpaceWarp) | UE版帧率优化 |
| [Unreal-ColocationDiscoverySample](https://github.com/oculus-samples/Unreal-ColocationDiscoverySample) | UE版共置发现 |
| [Unreal-OculusInputTest](https://github.com/oculus-samples/Unreal-OculusInputTest) | UE版输入测试 |
| [Unreal-AndroidPermissions](https://github.com/oculus-samples/Unreal-AndroidPermissions) | UE版Android权限 |

---

## 三、开源生态 (精华筛选)

### 标准层
| 仓库 | 星标 | 描述 |
|------|------|------|
| [KhronosGroup/OpenXR-SDK](https://github.com/KhronosGroup/OpenXR-SDK) | 700+ | OpenXR标准SDK(Quest底层标准) |
| [KhronosGroup/OpenXR-SDK-Source](https://github.com/KhronosGroup/OpenXR-SDK-Source) | 500+ | OpenXR源码+Loader+示例 |

### WebXR框架
| 仓库 | 星标 | 描述 | Agent适配 |
|------|------|------|----------|
| [aframevr/aframe](https://github.com/aframevr/aframe) | 16K+ | HTML声明式WebVR/AR框架 | ⭐⭐⭐⭐⭐ |
| [pmndrs/xr](https://github.com/pmndrs/xr) | 2K+ | React Three Fiber XR扩展 | ⭐⭐⭐⭐⭐ |

### 社区优质项目
| 仓库 | 描述 | 价值 |
|------|------|------|
| [sandeepv6/questvision](https://github.com/sandeepv6/questvision) | Quest 3实时物体检测(YOLO+Passthrough) | ⭐⭐⭐⭐ AI+MR |

---

## 四、Agent全链路开发能力

### WebXR路径 (Agent完全自主)

```
代码编写 → 本地预览 → 部署公网 → Quest浏览器访问 → PWA安装
   ✅          ✅          ✅            ✅              ✅
```

| 步骤 | Agent工具 | 状态 |
|------|----------|------|
| 1. 编写WebXR代码 | `write_to_file` / `edit` | ✅ 完全自主 |
| 2. 本地dev server | `run_command` (npx serve) | ✅ 完全自主 |
| 3. 浏览器预览 | `browser_preview` / Playwright | ✅ 完全自主 |
| 4. 部署公网 | `deploy_web_app` / scp到aiotvr.xyz | ✅ 完全自主 |
| 5. Quest访问 | Quest浏览器输入URL | ✅ 用户仅戴头显 |
| 6. PWA打包APK | bubblewrap CLI | ✅ 完全自主 |
| 7. Sideload到Quest | `adb install` | ✅ USB连接后自主 |

### Meta Spatial SDK路径 (Agent大部分自主)

```
Kotlin代码 → Gradle构建 → APK → ADB安装 → Quest运行
   ✅           ✅         ✅      ✅          ✅
```

### Unity路径 (需要Unity GUI)

```
C#代码 → Unity编辑器构建 → APK → ADB安装
  ✅        ⚠️需GUI          ✅      ✅
```

---

## 五、快速开始

### 路径①: WebXR (推荐，Agent全自主)

```bash
# 1. 创建项目
mkdir my-quest-app && cd my-quest-app
npm init -y
npm install three @webxr-input/profiles

# 2. 开发 (Agent编写代码)
# 3. 本地测试 (需要HTTPS才能启WebXR)
npx serve --ssl-cert cert.pem --ssl-key key.pem -l 8443

# 4. Quest浏览器访问
# https://<你的IP>:8443 或 https://aiotvr.xyz/quest/
```

### 路径②: Meta Spatial SDK

```bash
# 1. 安装Meta Horizon Plugin for Android Studio
# 2. 使用模板创建项目
# 3. Gradle构建
./gradlew assembleDebug

# 4. ADB安装
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

---

## 六、目录结构 (实际)

```
quest3开发/
├── README.md                  ← 本文件(全景索引)
├── AGENTS.md                  ← Agent操作手册
├── webxr/                     ← WebXR项目(Agent首选, 12个demo)
│   ├── index.html             ← Portal导航页(XR检测+卡片)
│   ├── hello-vr/              ← 纯WebGL2入门(手部追踪)
│   ├── mr-passthrough/        ← MR透视(浮动球体+手部关节)
│   ├── aframe-playground/     ← A-Frame声明式场景(动画+交互)
│   ├── hand-grab/             ← 手部抓取(pinch-grab组件)
│   ├── shared-space/          ← 多人WebSocket(位置同步+聊天)
│   ├── smart-home/            ← HA智能家居MR(3D面板+实时控制)
│   ├── ar-placement/          ← AR放置(hit-test+平面检测+锚点)
│   ├── hand-physics/          ← 手部物理(官方手部模型+抓投)
│   ├── controller-shooter/    ← 手柄射击(目标+粒子+触觉反馈)
│   ├── spatial-audio/         ← 空间音频(HRTF+距离衰减+可视化)
│   ├── gaussian-splat/       ← 3D高斯溅射VR查看器(多场景切换)
│   ├── vr-painter/           ← VR画笔(手部追踪/手柄+多色+撤销)
│   ├── simulator.html        ← Quest 3虚拟仿真环境(IWER+性能监控+全量测试)
│   └── devops.html           ← 全链路DevOps管理面板(测试/CDN/XR检测)
├── refs/                      ← 参考项目(10个, git clone --depth 1)
│   ├── ratk/                  ← RATK — MR核心库
│   ├── webxr-first-steps/     ← Meta官方入门(Three.js)
│   ├── webxr-first-steps-react/ ← Meta官方入门(R3F)
│   ├── ProjectFlowerbed/      ← Meta完整WebXR游戏
│   ├── immersive-web-emulator/ ← Quest WebXR模拟器
│   ├── bubblewrap/            ← PWA→APK工具
│   ├── webxr-handtracking/    ← 手部追踪示例集
│   ├── passtracing/           ← MR描线画笔
│   ├── enva-xr/               ← AR遮挡+物理
│   └── immersive-home/        ← Godot MR智能家居
└── tools/                     ← 开发工具脚本(3个)
    ├── setup.ps1              ← 环境一键配置(Node+ADB+证书)
    ├── deploy-quest.ps1       ← 部署(远程scp/本地HTTPS)
    └── deploy-pending.ps1     ← 待部署清单(shared-space/smart-home)
```

---

## 七、环境要求

| 组件 | 最低版本 | 用途 |
|------|---------|------|
| Node.js | 18+ | WebXR开发/构建 |
| ADB | 最新 | Quest连接/安装APK |
| Quest 3 | v69+ | 目标设备 |
| 开发者模式 | 已开启 | Sideload |
| Android Studio | 2024.1+ | Spatial SDK (可选) |
| Unity | 2022.3 LTS | Unity开发 (可选) |

---

## 八、关键API能力矩阵 (Quest 3)

| 能力 | WebXR | Spatial SDK | Unity | Unreal |
|------|-------|------------|-------|--------|
| Passthrough | ✅ | ✅ | ✅ | ✅ |
| 手部追踪 | ✅ | ✅ | ✅ | ✅ |
| 空间锚点 | ✅(RATK) | ✅ | ✅ | ✅ |
| Scene API | ✅(RATK) | ✅ | ✅ | ✅ |
| Depth API | ❌ | ✅ | ✅ | ✅ |
| 面部追踪 | ❌ | ✅ | ✅ | ✅ |
| 身体追踪 | ❌ | ✅ | ✅ | ✅ |
| 共置多人 | ❌ | ✅ | ✅ | ✅ |
| Compositor Layers | ❌ | ✅ | ✅ | ✅ |
| AppSpaceWarp | ❌ | ❌ | ✅ | ✅ |

---

## 九、已知问题与解决方案

| 问题 | 影响 | 解决 |
|------|------|------|
| WebXR需要HTTPS | 开发时无法直接HTTP | 自签证书 / ngrok / aiotvr.xyz |
| Quest浏览器限制 | 部分WebGL2特性不支持 | 降级shader / 使用兼容特性 |
| ADB WiFi不稳定 | 调试断连 | USB优先 / adb tcpip 5555 |
| Unity需GUI操作 | Agent无法直接构建 | Unity CLI构建 / MCP扩展 |
| Spatial SDK较新 | 文档和示例较少 | 参考官方Samples+Templates |

---

*最后更新: 2026-03-06 by Agent*
*数据来源: GitHub oculus-samples(62仓库) + meta-quest(17仓库) + 开源生态*
*refs/: 10个本地克隆 | webxr/: 12个自研demo + 2个管理页 | tools/: 3个自动化脚本*
