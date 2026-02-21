# 展示与页面工作总索引（SHOWCASE INDEX）

> 版本：v1.0 | 创建：2026-02-21
> 定位：连接本项目中所有"展示/页面/对外呈现"相关的工作，提供统一入口。

---

## 顶层哲学

本项目有两个"对外展示"层面的工作，它们看似无关，实则共享同一个深层信念：

**人是系统的瓶颈，也是系统的灵魂。**

| 项目 | 解决的问题 | 核心洞察 |
|------|-----------|---------|
| `presentation/` | 如何向外界解释"人+AI协作" | 天才和疯子只差一个过滤器，AI就是那个过滤器 |
| `agent-comm/` | 如何让一个人同时指挥多个AI | 人的注意力是稀缺资源，Agent的并行能力是廉价资源 |

**统一真理**：AI 时代的根本矛盾不是"AI 能不能做"，而是"人能不能驾驭"。两个项目从不同角度回答同一个问题。

---

## 一、presentation/ — 视频展示（意识流编程）

### 定位
面向 B 站观众的视频作品，主题："人工天才模式"。

### 核心逻辑（三层）
```
Layer 3: 哲学升华 — AI越强人越重要，瓶颈在人不在AI
Layer 2: 方法论   — 5步意识流编程（不过滤→AI分工→直觉验收→失败就修→断路器）
Layer 1: 实证     — 打开微信957ms，没写一行代码做出中文控制手机系统
```

### 产出清单
| 类型 | 文件 | 状态 |
|------|------|------|
| **终稿** | `docs/UNIFIED_VIDEO_ANALYSIS.md` | ✅ 三模式归一，最终7段逐字稿 |
| **管线** | `generate_v2.py` | ✅ V13，可执行 |
| **视频** | `bilibili_final.mp4` | ✅ 9:23, 1080p, 硬字幕 |
| **视频** | `matched_bilibili_hq.mp4` | ✅ 7:14, 最佳品质 |
| **发布** | `bilibili_publish/` | ✅ 封面×5 + 字幕 + 指南 |
| **工具** | 5个Python脚本 | ✅ TTS/ASR/合成/字幕/剪辑 |

### 文件健康度（清理后）
- 核心文档：1个（UNIFIED终稿）
- 参考文档：6个（叙事/迭代/质量/TTS/交接/未来）
- 已归档：6个（原始稿，被终稿吸收）
- 垃圾：0个（已清理）

---

## 二、agent-comm/ — Multi-Agent Dashboard 页面

### 定位
开发者工具：一个网页控制台，让一个人同时指挥多个 Windsurf AI Agent。

### 核心逻辑（三层）
```
Layer 3: 人机界面   — Dashboard Web UI（卡片式请求 + 一键回复 + 状态监控）
Layer 2: 通信协议   — HTTP API + Long-polling + JSON 消息格式
Layer 1: 行为注入   — PRIORITY RULE（global_rules.md 强制 Agent 每次回复调用 bridge）
```

### 灵魂机制
**Prompt Injection as a Feature** — 你无法修改 IDE 源码，但可以通过 global_rules.md 注入规则，强制 Agent 在每次回复时执行指定命令。利用 AI 的"遵守规则"特性，将外部系统调用嵌入 Agent 行为循环。

### 产出清单
| 类型 | 文件 | 行数 | 状态 |
|------|------|------|------|
| **服务端** | `core/dashboard.py` | 905 | ✅ v2.0 + token认证 + 持久化 |
| **客户端** | `core/bridge_agent.py` | 359 | ✅ 6种模式 + 自动启动 |
| **启动器** | `start.bat` + `core/bridge.bat` | — | ✅ 一键启动 |
| **配置** | `config.json` | — | ✅ 集中配置 |
| **模板** | `config/agent_rules_template.md` | — | ✅ 可移植 |
| **分析** | `DEEP_ANALYSIS.md` | 322 | ✅ 完整解析 |

### 已验证（E2E）
- [x] Dashboard 启动 + Token认证
- [x] Agent 状态上报
- [x] 阻塞式请求（ask → card）
- [x] 回复闭环（respond → JSON）
- [x] 请求持久化

### 已修复的Bug（2026-02-21）
- **addLog 函数失效**：HTML 中缺少 `<div id="log">` 元素，导致所有本地日志（回复确认、广播、指令下发）静默失败。已添加 log 面板 + 样式。

---

## 三、两个项目的关系

```
ScreenStream_v2（Android投屏+控制）
    │
    ├── presentation/     ← 对外展示：向观众解释"为什么这样做"
    │   └── 主题：人工天才模式
    │
    └── agent-comm/       ← 对内展示：开发者如何管理多个AI助手
        └── 主题：Multi-Agent 编排
```

- `presentation/` 是产品的**外部叙事**（给用户看的故事）
- `agent-comm/` 是产品的**内部基础设施**（给开发者用的工具）
- 两者不需要合并到一个文件夹，因为职责完全不同
- 但它们共享同一个哲学根基：**人+AI > 人 or AI**

---

## 四、入口导航

| 我想… | 去哪里 |
|--------|--------|
| 了解视频内容和哲学 | `presentation/docs/UNIFIED_VIDEO_ANALYSIS.md` |
| 运行视频生成管线 | `presentation/generate_v2.py --key sk-xxx` |
| 查看最终视频 | `presentation/bilibili_final.mp4` |
| 启动 Agent Dashboard | `agent-comm/start.bat`（双击） |
| 理解 Dashboard 架构 | `agent-comm/DEEP_ANALYSIS.md` |
| 给新 Agent 注入规则 | `agent-comm/config/agent_rules_template.md` |
| 查看 Dashboard API | `agent-comm/README.md` → API 端点表 |
