# 本地投屏 — 局域网投屏统一中枢

> 手机屏幕通过局域网实时投射到PC浏览器，支持触控反操控。
> 零服务器、零中继、零依赖 — WiFi直连是本源。

## 核心本质

```
ScreenStream APP (手机) ──WiFi──→ PC浏览器
  ├── MJPEG/H264/H265 投屏流
  ├── 70+ REST API 全操控
  └── AI Agent Brain (语义操作+自然语言)
```

**ScreenStream的本地投屏 = 手机内置HTTP Server + 浏览器直连。** 这是最简单、最本源的场景。

## 三种投屏模式

| 模式 | 原理 | 延迟 | 适用场景 |
|------|------|------|---------|
| **WiFi直连** | 浏览器→手机IP:8080 | ~50ms | 日常使用（推荐） |
| **USB转发** | ADB forward→localhost | ~30ms | 开发/无WiFi |
| **scrcpy** | USB直投原生窗口 | ~20ms | 最低延迟需求 |

## 快速开始

### WiFi投屏（最简，推荐）

1. 手机和PC连同一WiFi
2. 手机打开ScreenStream APP → 开始投屏
3. PC浏览器访问 `http://手机IP:8080/`
4. 完成 — 可看画面+触控操作+10个功能面板+AI命令

### 使用Hub（多设备管理）

```powershell
# 一键启动
→本地投屏.cmd

# 或手动
python lan_cast.py --all --scan
# → http://localhost:9871/
```

Hub提供：
- 自动发现USB和WiFi设备
- ADB端口转发管理
- scrcpy集成
- 统一Dashboard入口

### 从源码构建（开发者）

```powershell
# 完整管线: 构建→部署→验证→E2E
.\build_pipeline.ps1

# 分阶段
.\build_pipeline.ps1 -Phase build    # 仅构建APK
.\build_pipeline.ps1 -Phase deploy   # 仅部署到手机
.\build_pipeline.ps1 -Phase verify   # 仅API验证
.\build_pipeline.ps1 -Phase e2e      # 端到端测试

# 轻量E2E验证
.\e2e_build_test.ps1 -Verbose
```

## 文件清单

| 文件 | 用途 |
|------|------|
| `build_pipeline.ps1` | 完整构建管线 (build→deploy→verify→e2e) |
| `e2e_build_test.ps1` | 轻量E2E验证 (18项测试) |
| `lan_cast.py` | Hub中枢 (设备发现+ADB管理+API, Python stdlib零依赖) |
| `dashboard.html` | Dashboard前端 (设备卡片+一键投屏) |
| `→本地投屏.cmd` | 一键启动 |
| `_AGENT_GUIDE.md` | Agent操作指令 v2.0 |

## 构建管线状态 (v2.0)

| 阶段 | 状态 | 详情 |
|------|------|------|
| 源码构建 | PASS | assembleFDroidDebug 1m24s, 17MB |
| 部署安装 | PASS | OnePlus NE2210, AccessibilityService自动启用 |
| Input API | PASS | 11/11端点响应 |
| H264视频流 | PASS | WebSocket NAL帧已验证 |
| 音频流 | PASS | WebSocket已连接 |
| 触控反操控 | PASS | TouchWS已连接 |
| E2E测试 | 17/18 | 全部核心功能验证通过 |

## 资源整合来源

本项目基于 [ScreenStream](https://github.com/zhouyoukang/ScreenStream) **从源码构建**：

| 来源 | 整合内容 |
|------|---------|
| `010-用户界面与交互_UI/` | Android主APP (Gradle :app模块) |
| `020-投屏链路_Streaming/` | MJPEG/RTSP/WebRTC投屏引擎 |
| `040-反向控制_Input/` | 70+ API + AccessibilityService |
| `070-基础设施_Infrastructure/` | 模块管理/DI/日志 |
| `scrcpy/` | USB投屏备选方案 |

## 衍生项目关系图

```
                    ScreenStream APP (手机端投屏引擎)
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    【本地投屏】      【公网投屏】      【亲情远程】
    WiFi直连/USB      H264 Relay       P2P公网直连
    零中继            WS中继服务器      FRP穿透
    :8080直连         :9800中继         :9860中枢
    本目录            ../公网投屏/      ../亲情远程/
```

## 端口分配

| 端口 | 服务 | 位置 |
|------|------|------|
| 8080 | SS Gateway | 手机端 |
| 8081 | SS MJPEG | 手机端 |
| 8084 | SS Input API | 手机端 |
| 9871 | 本地投屏 Hub | PC端 |
| 18080+ | ADB forward | PC端(动态) |

## SS前端能力（浏览器直连后可用）

手机开启投屏后，浏览器访问即拥有完整能力：

- **投屏**: MJPEG/H264/H265 + 音频
- **触控**: 点击/滑动/长按/双击/缩放/多指手势
- **键盘**: 完整PC键盘输入 + 中文IME
- **导航**: Home/Back/Recent/通知栏/快捷设置
- **系统**: 音量/亮度/锁屏/截图/手电/旋转
- **AI**: 自然语言命令 + View树分析 + 语义点击
- **面板**: 10个功能面板(Alt+1~0) — APP启动器/通知/屏幕阅读/工作流/文件管理...
- **宏**: 录制+回放操作序列
- **文件**: 远程文件管理器(浏览/上传/下载/编辑)
