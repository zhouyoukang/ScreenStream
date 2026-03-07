# AI操控手机 — 全景图

> **一句话**：从GitHub 40+全球顶级项目中提炼精华，与自有phone_lib对标，
> 找到差距、汲取灵感、明确演进路线。
>
> 生成时间：2026-02-26 | 数据源：GitHub搜索 + 论文 + awesome-mobile-agents策展 + 官方文档

---

## 一、全球AI操控手机项目全景

### 1.1 三大范式

| 范式 | 核心思路 | 代表项目 | 适用场景 |
|------|----------|----------|----------|
| **Vision-VLM** | 截屏→VLM理解→坐标动作 | AppAgent, CogAgent, Mobile-Agent, UI-TARS | 通用GUI自动化，无需a11y |
| **Accessibility-First** | a11y树→结构化元素→精确操控 | **phone_lib(自有)**, DroidBot-GPT, AutoDroid | 深度精确控制，速度快 |
| **Hybrid** | VLM感知+a11y/ADB执行 | Open-AutoGLM, mobile-use, Agent-S | 复杂工作流，高鲁棒性 |

### 1.2 顶级开源项目（按星标/影响力排序）

| 项目 | 机构 | Stars | 范式 | 核心能力 | 我们能学什么 |
|------|------|-------|------|----------|-------------|
| **[AppAgent](https://github.com/TencentQQGYLab/AppAgent)** | 腾讯 | 5K+ | Vision | 多模态Agent，自主探索学APP，生成操作文档 | ★ 自主探索+经验记录 |
| **[Mobile-Agent](https://github.com/X-PLUG/MobileAgent)** | 阿里X-PLUG | 3K+ | Hybrid | v1→v2→v3进化，AndroidWorld SOTA，RL训练 | ★ 多Agent协作+反思机制 |
| **[Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM)** | 智谱Z.AI | 2K+ | Hybrid | 9B专用VLM，ADB控制，远程/本地双模式 | ★ 专用小模型+远程ADB |
| **[mobile-use](https://github.com/minitap-ai/mobile-use)** | Minitap | 2K+ | Hybrid | Android+iOS真机，AndroidWorld冠军(Forbes报道) | ★ 跨平台+任务分解+动态Agent |
| **[DroidBot-GPT](https://github.com/MobileLLM/DroidBot-GPT)** | 北大MobileLLM | 1K+ | A11y | 基于DroidBot框架，LLM驱动UI策略 | ★ 状态→LLM→动作的极简架构 |
| **[AutoDroid](https://github.com/MobileLLM/AutoDroid)** | 北大MobileLLM | 1K+ | A11y | 功能感知UI表示+探索式记忆注入，90.9%准确率 | ★ 功能感知+记忆注入 |
| **[agent-device](https://github.com/callstackincubator/agent-device)** | Callstack | 1K+ | A11y | CLI控制iOS+Android，MCP集成，实时日志流 | ★ MCP Server模式+日志流 |
| **[DigiRL](https://digirl-agent.github.io/)** | 学术 | — | Vision | 1.5B VLM+RL，AitW 67.2%（+49.5%绝对提升） | ★ 强化学习训练策略 |
| **[CogAgent](https://github.com/THUDM/CogAgent)** | 清华 | 3K+ | Vision | 18B视觉语言模型，原生GUI理解 | ★ 端到端GUI VLM |
| **[Arbigent](https://github.com/takahirom/arbigent)** | 社区 | 1K+ | Hybrid | Android/iOS/Web测试，可复用组件，多配置 | ★ 测试框架设计 |

### 1.3 策展资源

| 资源 | 说明 |
|------|------|
| **[awesome-mobile-agents](https://github.com/aialt/awesome-mobile-agents)** | 最全手机Agent论文+项目列表 |
| **[awesome-gui-agent](https://github.com/showlab/Awesome-GUI-Agent)** | GUI Agent全景（含手机） |
| **[trycua/acu](https://github.com/trycua/acu)** | AI Computer Use资源大全 |
| **[e2b-dev/awesome-ai-agents](https://github.com/e2b-dev/awesome-ai-agents)** | 通用AI Agent列表 |

### 1.4 评测基准

| 基准 | 来源 | 规模 | 说明 |
|------|------|------|------|
| **AndroidWorld** | Google DeepMind | 116任务/20APP | 动态参数化任务，可编程验证，业界标准 |
| **Android-in-the-Wild (AitW)** | Google | 大规模 | 真实交互轨迹数据集 |
| **MobileWorld** | 学术 | Agent-User交互 | 对话式任务基准 |
| **AndroidLab** | 学术 | 系统框架 | 支持评估+训练 |

### 1.5 商业方案

| 方案 | 提供商 | 核心差异 |
|------|--------|----------|
| **Gemini Nano** | Google | 设备端推理，Android原生集成 |
| **Apple Intelligence** | Apple | Private Cloud Compute，设备端优先 |
| **Galaxy AI** | Samsung | 三星设备深度集成 |
| **Claude Computer Use** | Anthropic | computer tool类型，截屏+坐标+按键 |

---

## 二、技术精华提炼

### 2.1 屏幕感知（三条路线对比）

| 路线 | 代表 | 延迟 | 精度 | 通用性 | 依赖 |
|------|------|------|------|--------|------|
| **A11y树** | phone_lib, DroidBot-GPT | 10-50ms | ★★★★★ | ★★★ (需a11y权限) | 无障碍服务 |
| **VLM截屏** | AppAgent, CogAgent | 1-5s | ★★★ | ★★★★★ (任何界面) | GPU/API |
| **混合** | mobile-use, AutoGLM | 0.5-2s | ★★★★ | ★★★★★ | a11y+VLM |

**phone_lib的优势**：A11y路线在**速度和精度**上碾压VLM路线（10ms vs 2s），但在WebView/游戏/反无障碍APP上失效。
**应补的短板**：可选VLM降级——a11y失效时截屏→VLM理解→坐标操作。

### 2.2 动作执行对比

| 能力 | AppAgent | Mobile-Agent | AutoGLM | mobile-use | **phone_lib** |
|------|----------|-------------|---------|------------|---------------|
| 点击 | ✅坐标 | ✅坐标 | ✅ADB | ✅坐标 | ✅**语义+坐标** |
| 滑动 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 输入 | ❌ADB | ✅ADB | ✅ADB Keyboard | ✅ | ✅**HTTP+ADB双通道** |
| Intent | ❌ | ❌ | ❌ | ❌ | ✅**独有** |
| 通知读取 | ❌ | ❌ | ❌ | ❌ | ✅**独有** |
| APP管理 | ❌ | ❌ | ✅ | ✅ | ✅**monkey+HTTP双通道** |
| 系统控制 | ❌ | ❌ | ❌ | ❌ | ✅**15+系统API** |
| 智能家居 | ❌ | ❌ | ❌ | ❌ | ✅**独有** |
| 文件操作 | ❌ | ❌ | ❌ | ❌ | ✅**独有** |
| 负面状态恢复 | ❌ | ❌ | ❌ | ❌ | ✅**7种自动恢复** |
| 纯HTTP(无ADB) | ❌ | ❌ | ❌ | ❌ | ✅**全球唯一** |
| 心跳+远程重连 | ❌ | ❌ | ❌ | ❌ | ✅**独有** |

**结论**：动作执行层phone_lib**远超**所有开源方案，尤其Intent/通知/系统控制/智能家居/负面状态恢复/纯HTTP模式是全球独有。

### 2.3 Agent编排模式对比

| 模式 | 代表 | 特点 | phone_lib |
|------|------|------|-----------|
| **单Agent循环** | AppAgent, DroidBot-GPT | Observe→Think→Act→Verify | ✅ 已支持(SKILL.md) |
| **多Agent协作** | Mobile-Agent-v2 | 规划Agent+操作Agent+反思Agent | ❌ 待实现 |
| **任务分解** | mobile-use | 复杂任务→子任务DAG | ❌ 待实现 |
| **经验学习** | AppAgent, AutoDroid | 从操作中学习模式并复用 | ❌ 待实现 |
| **自主探索** | AppAgent | 自动探索APP生成操作文档 | ❌ 待实现 |
| **RL训练** | DigiRL, Mobile-Agent-v3 | 强化学习优化策略 | ❌ 非目标 |

### 2.4 连接架构对比

| 能力 | 大多数项目 | **phone_lib** |
|------|-----------|---------------|
| USB ADB | ✅ | ✅ |
| WiFi ADB | 部分 | ✅ |
| WiFi HTTP直连 | ❌ | ✅ |
| Tailscale穿透 | ❌ | ✅ |
| 公网穿透 | ❌ | ✅ |
| 局域网扫描 | ❌ | ✅ |
| 自动发现 | ❌ | ✅ 五层 |
| 断线重连 | ❌ | ✅ |
| 心跳守护 | ❌ | ✅ |

**结论**：连接层是phone_lib的**绝对护城河**。所有开源方案都需USB ADB常驻，phone_lib是唯一支持纯HTTP远程操控的。

---

## 三、自有资产总盘

### 3.1 phone_lib.py — 手机操控核心

| 指标 | 值 |
|------|-----|
| **代码量** | 1009行，零外部依赖(纯urllib) |
| **API封装** | 90+ ScreenStream HTTP API |
| **连接** | 五层自动发现: USB→WiFi→Tailscale→公网→局域网扫描 |
| **弹性** | 心跳+断线重连+7种负面状态自动恢复 |
| **五感** | vision/hearing/touch/smell/taste 全采集 |
| **测试** | 46/46全通过(standalone 36 + agent 5 + complex 5) |

### 3.2 agent-phone-control SKILL

| 指标 | 值 |
|------|-----|
| **架构** | Cascade ←→ phone_lib ←→ ScreenStream API ←→ Android |
| **循环** | Observe→Think→Act→Verify |
| **API速查** | 20+常用端点 |
| **Intent速查** | 7种常用Intent |

### 3.3 测试矩阵

| 测试文件 | 项数 | 覆盖 |
|----------|------|------|
| `standalone_test.py` | 36项 | L0/L1原始HTTP验证 |
| `agent_demo.py` | 5项 | 多步Agent任务 |
| `complex_scenarios.py` | 5场景43步 | 86%零AI |
| `remote_test.py` | 8节 | 远程五感端到端 |
| `_no_adb_test.py` | 35项 | 纯HTTP(无ADB) |
| `ai_hub_test.py` | AI中枢 | 多AI App能力测试 |

---

## 四、祸 · 惑 · 问（诊断清单）

### 4.1 已治之祸（本次修复 ✅）

| # | 祸名 | 修复 |
|---|------|------|
| 1 | **端口残留8086** — 14处散落在8文件中 | ✅ 全部修正为8084 |
| 2 | **AGENTS.md ADB端口写错** | ✅ `8086→8084` |
| 3 | **switch_to默认端口8086** | ✅ 回退端口改为8084 |
| 4 | **remote_setup/assist默认端口8086** | ✅ 改为8084 |
| 5 | **family_setup_guide端口示例8086** | ✅ 改为8084 |
| 6 | **.gitignore未排除一次性分析产物** | ✅ 增加淘宝订单详解/ai_hub_report规则 |

### 4.2 已知之惑（需关注）

| # | 惑 | 状态 | 说明 |
|---|-----|------|------|
| 1 | 测试文件IP硬编码 `192.168.10.122` | ⚠️ | 旧设备IP，当前设备`192.168.31.32`。测试需`--host`参数覆盖 |
| 2 | 微信反无障碍 | 🔒 | 平台限制不可绕过，用包名验证替代文本验证 |
| 3 | WebView不走accessibility | 🔒 | 闲鱼/1688等返回DOM ID非文本，需VLM降级 |
| 4 | 剪贴板后台限制(Android 10+) | 🔒 | API写入时内部缓存；手机手动复制的无法读取 |

### 4.3 对标业界后的新祸

| # | 新祸 | 根因 | 影响 | 解法 |
|---|------|------|------|------|
| 1 | **无VLM降级** | a11y失效时无备选 | 微信/WebView/游戏无法操控 | 接入截屏→VLM理解(P2) |
| 2 | **无经验学习** | 每次操控从零开始 | 重复操作不积累经验 | 操作记录→模式提取(P2) |
| 3 | **无自主探索** | 不能自动学习新APP | 每个APP需人工编程 | AppAgent式自主探索(P3) |
| 4 | **无多Agent编排** | 单Agent顺序执行 | 复杂工作流效率低 | Mobile-Agent-v2式多Agent(P3) |

---

## 五、与业界的终极对标

### 我们独有（护城河）

| 能力 | 说明 | 竞品有吗 |
|------|------|----------|
| **纯HTTP全功能操控** | 无需ADB，网络即可操控90+API | ❌ 全球独有 |
| **五感全采集** | vision/hearing/touch/smell/taste | ❌ 全球独有 |
| **7种负面状态自动恢复** | 息屏/a11y断/APP杀/USB断/WiFi断/Doze/低电 | ❌ 全球独有 |
| **五层自动发现** | USB→WiFi→Tailscale→公网→局域网扫描 | ❌ 全球独有 |
| **心跳守护+断线重连** | 后台线程自动检测+恢复 | ❌ 全球独有 |
| **Intent直跳** | 深度链接直达APP功能 | ❌ 独有(其他项目仅用ADB) |
| **零框架零依赖** | 纯stdlib运行，部署极简 | ❌ 独有 |
| **系统级控制** | 音量/亮度/手电/振动/免打扰/旋转/保持唤醒 | ❌ 独有 |
| **智能家居联动** | 通过手机控制智能家居设备 | ❌ 独有 |
| **宏系统** | 内联/预定义宏执行 | ❌ 独有 |

### 业界领先但我们缺（需补的）

| 能力 | 说明 | 来源 | 优先级 |
|------|------|------|--------|
| **VLM屏幕理解** | AI看懂手机截屏 | CogAgent/UI-TARS | P2 |
| **经验学习** | 从成功操作中学习模式 | AppAgent/AutoDroid | P2 |
| **自主探索** | 自动学习新APP操作方式 | AppAgent | P3 |
| **多Agent协作** | 规划+操作+反思 | Mobile-Agent-v2 | P3 |
| **任务DAG** | 复杂任务分解+并行 | mobile-use | P3 |
| **MCP Server模式** | 作为MCP工具供外部Agent调用 | agent-device | P1 |

---

## 六、演进路线（三阶段）

### Phase 1: 补短板（投入小，收益大）

| 项 | 内容 | 工作量 | 收益 |
|----|------|--------|------|
| **P1.1** | phone_lib → MCP Server | ~100行 | 任何MCP Client(Claude/GPT)可直接操控手机 |
| **P1.2** | 操作日志持久化 | ~50行 | 每次操作记录到SQLite，为经验学习奠基 |
| **P1.3** | `/capabilities` 端点 | ~30行 | 设备自描述能力，为多设备编排奠基 |
| **P1.4** | 截屏API封装 | ~20行 | `/screenshot` 返回base64，为VLM降级准备 |

### Phase 2: 借力VLM（接入AI视觉）

| 项 | 内容 | 工作量 | 收益 |
|----|------|--------|------|
| **P2.1** | VLM降级通道 | ~150行 | a11y失效→截屏→VLM→坐标操作 |
| **P2.2** | 经验记录+复用 | ~200行 | 操作序列→模式→下次直接调用 |
| **P2.3** | APP操作文档自动生成 | ~100行 | 探索APP→生成操作手册(学AppAgent) |

### Phase 3: 多设备Galaxy（长期愿景）

| 项 | 内容 | 灵感来源 | 收益 |
|----|------|----------|------|
| **P3.1** | 多Agent编排 | Mobile-Agent-v2 | 规划+操作+反思三Agent协作 |
| **P3.2** | 任务DAG引擎 | mobile-use | 复杂工作流分解+并行+持久化 |
| **P3.3** | 自主探索引擎 | AppAgent | 自动学习新APP |
| **P3.4** | 统一Agent协议 | 参考AI_COMPUTER_CONTROL.md | 手机+PC统一编排 |

---

## 七、可借鉴的关键技术

### 7.1 AppAgent 自主探索机制

```
Phase 1: 探索 — Agent自主操作APP，记录每个UI元素的作用
Phase 2: 部署 — 用户给任务，Agent查阅探索记录，生成操作序列
```
**可借鉴**：phone_lib已有`/screen/text`+`/viewtree`，可实现：
```python
# 自动探索: 遍历clickables → 点击 → 观察变化 → 记录
for elem in clickables:
    before = p.read()
    p.click(elem)
    after = p.read()
    log_transition(elem, before, after)
```

### 7.2 Mobile-Agent-v2 多Agent协作

```
规划Agent: 理解任务，分解为步骤
操作Agent: 执行每个步骤
反思Agent: 检查执行结果，发现问题回退
```
**可借鉴**：Cascade本身可扮演三个角色，通过prompt切换。

### 7.3 AutoDroid 功能感知UI表示

```
传统: 把所有UI元素dump给LLM（太长）
AutoDroid: 只保留与任务相关的元素（功能感知）
```
**可借鉴**：phone_lib的`/screen/text`已经精简（只返回文本+可点击），天然接近功能感知。

### 7.4 mobile-use 动态Agent

```
不同任务阶段使用不同的Agent prompt:
- Contextor: 理解当前屏幕上下文
- Navigator: 决定导航策略
- Executor: 执行具体操作
```
**可借鉴**：可在SKILL.md中定义不同阶段的prompt模板。

### 7.5 agent-device MCP Server模式

```
# 将手机控制能力暴露为MCP工具
tools:
  - tap(x, y)
  - type_text(text)
  - screenshot()
  - get_ui_tree()
```
**可借鉴**：phone_lib封装为MCP Server，任何支持MCP的AI都能操控手机。

---

## 八、参考资源索引

### 核心项目
- **[AppAgent](https://github.com/TencentQQGYLab/AppAgent)** — 自主探索+经验学习
- **[Mobile-Agent](https://github.com/X-PLUG/MobileAgent)** — v1→v2→v3，多Agent+RL
- **[Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM)** — 9B专用VLM+远程ADB
- **[mobile-use](https://github.com/minitap-ai/mobile-use)** — AndroidWorld冠军
- **[DroidBot-GPT](https://github.com/MobileLLM/DroidBot-GPT)** — 极简LLM+UI架构
- **[AutoDroid](https://github.com/MobileLLM/AutoDroid)** — 功能感知+记忆注入
- **[agent-device](https://github.com/callstackincubator/agent-device)** — MCP模式
- **[CogAgent](https://github.com/THUDM/CogAgent)** — 18B GUI VLM
- **[DigiRL](https://digirl-agent.github.io/)** — RL训练移动Agent
- **[Arbigent](https://github.com/takahirom/arbigent)** — 跨平台测试框架

### 策展列表
- **[awesome-mobile-agents](https://github.com/aialt/awesome-mobile-agents)** — 最全
- **[awesome-gui-agent](https://github.com/showlab/Awesome-GUI-Agent)** — GUI全景

### 自有文档链
- `手机操控库/README.md` — phone_lib使用指南
- `手机操控库/FINDINGS.md` — 实测发现P1-P29+远程架构发现
- `.windsurf/skills/agent-phone-control/SKILL.md` — Agent操控手机技能
- `文档/AI_COMPUTER_CONTROL.md` — AI操作电脑全景图(PC+手机)

---

*汇总自：GitHub 40+项目 + 论文 + awesome策展 + 自有代码全量分析*
*先增再减，再增再简，取之于精华，归之于总。*
