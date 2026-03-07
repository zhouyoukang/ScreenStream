# EroScripts 社区资源索引

> 来源: [discuss.eroscripts.com](https://discuss.eroscripts.com) — Adult IoT 社区论坛
> 采集日期: 2026-03-05 | 与 `GITHUB_RESOURCES.md` 互补，本文聚焦社区帖子、教程和非GitHub资源

## 1. 设备总览

### OSR 系列 (Open Source Stroker Robot)

| 设备 | 轴数 | 特点 | 行程 |
|------|------|------|------|
| **OSR2** | 2轴 (L0+R1) | 入门级, 2个舵机 | 112mm (默认) / 150mm (最大) |
| **OSR2+** | 3轴 (L0+R1+R2) | 加装pitch模块 | 同上 |
| **SR6** | 6轴 (L0-L2+R0-R2) | Stewart平台, 6个舵机 | 120mm上下 / 60mm左右前后 |
| **SSR1** | 1轴 (L0) | 无刷电机皮带驱动, 静音 | 120mm |
| **SSR2** | 2轴 (L0+R0) | TBA, 皮带驱动+旋转 | — |

### 可选模块

| 模块 | 轴 | 说明 |
|------|-----|------|
| **T-Twist 4/5** | R0 | 齿轮/线缆驱动旋转环, 270°舵机 |
| **T-Valve** | A1 | 微型舵机动态气压控制 |
| **I-Lube** | — | 自动注润滑 (by IsaacNewtongue) |
| **Squeeze** | — | WIP, 橡胶手套模拟肌肉收缩 |

> 来源: [Guide] What Is the OSR2/SR6/SSR1 — [t/158805](https://discuss.eroscripts.com/t/guide-what-is-the-osr2-sr6-ssr1-and-how-do-i-get-one/158805)

## 2. 固件

| 名称 | 链接 | 说明 |
|------|------|------|
| **TCodeESP32** | [GitHub](https://github.com/jcfain/TCodeESP32) | ESP32 TCode固件, Serial+WiFi+BLE, Web配置 |
| **SR-Control** | [controlfirmware.com](https://controlfirmware.com/) | 商业固件, 高级功能 |
| **Tempest原版** | Patreon专属 | Arduino/Romeo BLE Mini原始固件 |

## 3. 播放器与同步软件

### 桌面播放器

| 名称 | 平台 | 帖子 | 说明 |
|------|------|------|------|
| **MultiFunPlayer** | Windows | [t/23006](https://discuss.eroscripts.com/t/multifunplayer-v1-29-4-multi-axis-funscript-player-now-with-slr-interactive-support/23006) | 最全多轴播放器, 12种播放器+8种输出, SLR/FapTap |
| **XTPlayer** | 跨平台 | [t/4496](https://discuss.eroscripts.com/t/xtplayer-cross-platform-tcode-sync-osr-sr6-stream-your-local-media-and-sync-funscripts-to-almost-any-device-with-a-browser/4496) | 内置媒体浏览器, 浏览器同步 |
| **FunPlayer** | macOS | [t/274070](https://discuss.eroscripts.com/t/funplayer-v1-3-1-macos-funscript-player-tcode-usb-the-handy-intiface/274070) | TCode USB/Handy/Intiface, VLC/IINA/Safari扩展 |
| **ScriptPlayer** | Windows | [GitHub](https://github.com/FredTungsten/ScriptPlayer) | 视频+Funscript同步, Handy/OSR/Buttplug |

### Web 控制器

| 名称 | URL | 说明 |
|------|-----|------|
| **Ayva Stroker Lite** | [ayva-stroker-lite.io](https://www.ayva-stroker-lite.io/) | Web TCode控制器, TempestStroke模式引擎 (本项目42模式的源头) |
| **Mosa** | [trymosa.netlify.app](https://trymosa.netlify.app/) | Web控制器 by tnxa |
| **The Edgy** | EroScripts | 浏览器边缘控制器 |
| **Funscript.org** | [funscript.org](https://funscript.org/) | AI控制+编辑器 |

### 智能引擎

| 名称 | 帖子 | 说明 |
|------|------|------|
| **MiraPlay AiO** | [t/287825](https://discuss.eroscripts.com/t/miraplay-aio-smart-engine-for-osr-devices-updates-inside/287825) | OSR设备智能引擎, 多功能一体化 |
| **OSRChat** | EroScripts | LLM + OSR 对话控制 |
| **Joytech WebPlayer** | [t/281098](https://discuss.eroscripts.com/t/joytech-funscript-webplayer-web-funscript-player-with-tcode-support/281098) | Web Funscript播放器+TCode支持 |

## 4. Funscript 工具

### 编辑器

| 名称 | 链接 | 说明 |
|------|------|------|
| **OpenFunScripter (OFS)** | [GitHub](https://github.com/OpenFunscripter/OFS) | 标准编辑器, 手动标记 |
| **OFS Simulator3D** | [t/146053](https://discuss.eroscripts.com/t/ofs-simulator3d-mod-surge-sway-fix/146053) | OFS 3D模拟器插件, Surge/Sway修复 |
| **Blender 多轴编辑** | [t/76546](https://discuss.eroscripts.com/t/using-blender-as-a-multi-axis-script-editor/76546) | Blender作为多轴脚本编辑器 |
| **Attck's Merge Tool** | EroScripts | Funscript合并工具 |

### AI/自动生成

| 名称 | 链接 | 说明 |
|------|------|------|
| **FunGen AI** | [GitHub](https://github.com/ack00gar/FunGen-AI-Powered-Funscript-Generator) | AI视觉→Funscript, XBVR/Stash集成 |
| **MTFG** | [t/28117](https://discuss.eroscripts.com/t/motion-tracking-funscript-generator-v0-5-x/28117) | 运动追踪Funscript生成器 |
| **Funscript-Flow** | [GitHub](https://github.com/Funscript-Flow/Funscript-Flow) | 计算机视觉自动生成 |

### 多轴命名规范

| 后缀 | 轴 | 示例 |
|------|-----|------|
| (无后缀) | L0 Stroke | `video.funscript` |
| `.surge` | L1 | `video.surge.funscript` |
| `.sway` | L2 | `video.sway.funscript` |
| `.twist` | R0 | `video.twist.funscript` |
| `.roll` | R1 | `video.roll.funscript` |
| `.pitch` | R2 | `video.pitch.funscript` |
| `.vib` | V0 | `video.vib.funscript` |
| `.suck` | A1 | `video.suck.funscript` |

## 5. VaM (Virt-A-Mate) 插件

| 插件 | 作者 | Hub链接 | 说明 |
|------|------|---------|------|
| **T-Code Serial Controller** | Tempest | [Hub/20783](https://hub.virtamate.com/resources/t-code-serial-controller.20783/) | 官方串口控制 |
| **ToySerialController** | Yoooi | [Hub/19853](https://hub.virtamate.com/resources/toyserialcontroller.19853/) | 高级串口控制 (本项目UDP监听对接) |
| **Multi-axis Random Stroker** | Tempest | [Hub/25408](https://hub.virtamate.com/resources/multi-axis-random-stroker-v2.25408/) | 随机多轴动作 |
| **BusDriver** | Yoooi | [Hub/40872](https://hub.virtamate.com/resources/busdriver.40872/) | 高级运动引擎 |

## 6. 游戏/VR 集成

| 名称 | 说明 |
|------|------|
| **Intiface/Buttplug** | [intiface.com](https://intiface.com/) — 通用设备管理器 |
| **LoveMachine** | [GitHub](https://github.com/Sauceke/LoveMachine) — Unity游戏Intiface集成 |
| **Koikatsu Link** | [GitHub](https://github.com/qinyan-alpha/KK-osr2-sr6-link) — Koikatsu→OSR2/SR6 |
| **To4st FunscriptPlayer** | [t/99000](https://discuss.eroscripts.com/t/to4st-game-integration-mods/99000/14) — 游戏mod原生OSR支持 |

### VR 播放器兼容

| 播放器 | 集成方式 |
|--------|---------|
| **DeoVR** | WebSocket API → MultiFunPlayer (端口23554) |
| **HereSphere** | Remote Control API → MultiFunPlayer |
| **SLR Interactive** | 内置脚本流媒体 → MultiFunPlayer |

## 7. 硬件购买渠道

| 卖家 | 地区 | 链接 | 说明 |
|------|------|------|------|
| **YourHobbiesCustomized** | 美国 | [yourhobbiescustomized.com](https://yourhobbiescustomized.com/) | by M0SAIC, 社区首选 |
| **FunOSR** | 中国 | [funosr.com](https://www.funosr.com/) / [AliExpress](https://www.aliexpress.com/store/1103361043) | by renwoxing |
| **MiraBot S6** | — | [t/291353](https://discuss.eroscripts.com/t/mirabot-s6-a-refined-quiet-high-precision-6-axis-evolution-of-sr6/291353) | 精密安静6轴SR6进化版 |
| **g90ak Edition** | 美国 | [t/133538](https://discuss.eroscripts.com/t/osr2-g90ak-edition-extremely-limited-availability-160-shipping-dropping-monthly-starting-in-2024/133538) | 限量版OSR2+ $160 |
| **vESP Edition** | 英国 | [t/229247](https://discuss.eroscripts.com/t/multi-axis-modified-osr2-sr6-with-twist-for-sale-since-2023-february-2-5-just-1-unit-left/229247) | 改装OSR2+/SR6+Twist |

## 8. DIY 资源

| 资源 | 链接 | 说明 |
|------|------|------|
| **官方STL+说明** | [Patreon/TempestVR](https://www.patreon.com/tempestvr) | 3D打印文件+BOM+组装 (Patron专属) |
| **OSR Wiki** | [osr.wiki](https://osr.wiki/) | 社区Wiki, 开放编辑 |
| **TidyPrints** | [Patreon/TidyPrints](https://www.patreon.com/TidyPrints) | 改良版3D打印设计 |
| **EroScripts DIY版块** | [/c/diy](https://discuss.eroscripts.com/c/diy/) | 社区DIY讨论 |

## 9. 社区热门帖子 (SR6标签)

| 帖子 | 分类 | 浏览 | 说明 |
|------|------|------|------|
| MiraPlay AiO | Software | 4.0k | OSR智能引擎 |
| MultiFunPlayer v1.33.10 | Software | — | 最新版多轴播放器 |
| Joytech Funscript WebPlayer | Software | — | Web TCode播放器 |
| MiraBot S6 Review | General | — | 新金标准SR6评测 |
| XTPlayer Advanced Tutorial | Software | — | OSR设备XTPlayer教程 |
| FunSR PRO Review | General | — | FunSR PRO声音测试 |
| SSR2 Alpha | DIY | — | Tempest新2轴静音设备 |

## 10. 本项目已集成的EroScripts资源

| 资源 | 状态 | 对接方式 |
|------|------|---------|
| **Ayva TempestStroke 42模式** | ✅ 已移植 | `tcode/tempest_stroke.py` + `douyin_cache/_ayva_patterns.js` |
| **TCode协议 v0.3** | ✅ 已实现 | `tcode/protocol.py` (11轴+设备命令) |
| **MultiFunPlayer** | ✅ WebSocket+Funscript | `video_sync/mfp_client.py` |
| **ToySerialController** | ✅ UDP监听 | `vam_bridge/bridge.py` TSC模式 |
| **Buttplug/Intiface** | ✅ WebSocket | `tcode/buttplug_conn.py` |
| **DeoVR/HereSphere** | ✅ HTTP监控 | `video_sync/mfp_client.py` |
| **Funscript命名规范** | ✅ 10轴映射 | `video_sync/funscript_naming.py` |
| **OFS 3D Simulator** | 📋 参考 | 可集成到Hub 3D可视化 |
| **MiraPlay AiO** | 📋 参考 | 智能模式切换逻辑 |
| **OSRChat** | 📋 参考 | LLM→TCode控制模式 |

## 11. 发现的问题与改进方向

### 可集成资源 (优先级排序)

1. **OSRChat LLM控制** — 自然语言→TCode命令生成, 可增强Hub的AI能力
2. **MiraPlay 智能引擎** — 自适应模式切换, 可参考其UX设计
3. **Joytech WebPlayer** — Web端Funscript播放, 可对标Hub的Funscript Tab
4. **SR-Control 固件** — 商业固件的高级特性, 可参考API设计
5. **T-Twist 连续旋转** — 360°反馈舵机实现, 可扩展TCode R0轴范围

### 文档完善建议

- 添加 SSR1/SSR2 设备支持说明
- 添加 T-Twist/T-Valve 模块的TCode轴映射
- 添加 MiraBot S6 等商业预装机的兼容说明
- 补充 macOS (FunPlayer) 和 Linux 平台支持状态
