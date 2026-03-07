# AI操作电脑 — 全景图

> **一句话**：从GitHub 30+顶级项目中提炼精华，与自有三件套（remote_agent + phone_lib + Guardian）对标，
> 找到差距、汲取灵感、明确演进路线。
>
> 生成时间：2026-02-26 | 数据源：GitHub搜索 + trycua/acu策展 + 官方文档

---

## 一、全球AI操作电脑项目全景

### 1.1 三大范式

| 范式 | 核心思路 | 代表项目 | 适用场景 |
|------|----------|----------|----------|
| **Vision-VLM** | 截屏→VLM理解→坐标动作 | UI-TARS, OmniParser, CogAgent | 通用GUI自动化 |
| **API-First** | 结构化API→Agent编排 | **remote_agent**(自有), Open Interpreter | 深度系统控制 |
| **Hybrid** | VLM感知+API执行 | UFO³, Agent-S, Anthropic CU | 复杂工作流 |

### 1.2 顶级开源项目（按星标/影响力排序）

| 项目 | 机构 | Stars | 核心能力 | 我们能学什么 |
|------|------|-------|----------|-------------|
| **[UFO³](https://github.com/microsoft/UFO)** | Microsoft | 25K+ | Windows GUI Agent, **多设备DAG编排**, UIA+API混合 | ★ 多设备协调架构(Galaxy) |
| **[OmniParser](https://github.com/microsoft/OmniParser)** | Microsoft | 15K+ | 截屏→结构化UI元素, Set-of-Mark | ★ 屏幕元素解析模型 |
| **[UI-TARS](https://github.com/bytedance/UI-TARS-desktop)** | ByteDance | 12K+ | 多模态VLM Agent, SDK跨平台 | ★ UI-TARS SDK通用操控 |
| **[Open Interpreter](https://github.com/openinterpreter/open-interpreter)** | 社区 | 58K+ | 自然语言→代码执行→系统操控 | ★ 对话式计算机控制 |
| **[Agent-S](https://github.com/simular-ai/Agent-S)** | Simular AI | 5K+ | Agent框架, Mac/Win/Linux | ★ 经验学习+知识增强 |
| **[OS-Copilot](https://github.com/OS-Copilot/OS-Copilot)** | 学术 | 3K+ | 通用OS Agent, 自改进能力 | ★ 工具自学习 |
| **[Bytebot](https://github.com/bytebot-ai/bytebot)** | 社区 | 2K+ | 自托管桌面Agent, Docker虚拟桌面 | ★ 沙箱隔离执行 |
| **[Cua](https://github.com/trycua/cua)** | trycua | 6K+ | VM沙箱+Agent SDK, macOS/Linux | ★ 安全沙箱 |
| **[computer-agent](https://github.com/suitedaces/computer-agent)** | 社区 | 4K+ | 桌面APP, 后台运行不占键鼠 | ★ 后台模式 |

### 1.3 商业闭源方案

| 方案 | 提供商 | 模型 | 核心差异 |
|------|--------|------|----------|
| **Claude Computer Use** | Anthropic | Claude 4 Sonnet | `computer` tool类型, 截屏+坐标+按键, Docker参考实现 |
| **Operator/CUA** | OpenAI | computer-use-preview | 浏览器内操控, 强推理, API可用(2025.3+) |
| **Copilot Vision** | Microsoft | GPT-4o系列 | Windows深度集成, UIA原生 |
| **Apple Intelligence** | Apple | 私有 | 设备端推理, Private Cloud Compute |

---

## 二、技术精华提炼

### 2.1 屏幕感知（最大差距所在）

**业界最佳实践**：
```
截屏 → OmniParser/UI-TARS → 结构化元素(bbox+label+type)
     → Set-of-Mark(SoM) 标注 → VLM理解 → 精确动作
```

**我们的现状**：
- remote_agent: `pyautogui` + `mss` 截屏 → JPEG → 人眼看
- phone_lib: `/screen/text` AccessibilityService → 文本+可点击元素

**差距与机会**：
| 维度 | 业界 | 我们 | 差距 | 补救路径 |
|------|------|------|------|----------|
| PC屏幕理解 | OmniParser解析 | 纯截图JPEG | 🔴大 | 接入OmniParser本地/API |
| 手机屏幕理解 | VLM+OCR | AccessibilityService | 🟢无(a11y更精准) | 保持优势 |
| 元素定位 | SoM标注+VLM | 手机findByText/PC坐标 | 🟡中 | PC端增加UIA/Win32自动化 |
| 跨平台 | UI-TARS SDK | 手机a11y+PC pyautogui | 🟡中 | 统一抽象层 |

### 2.2 动作执行（我们的强项）

| 能力 | UFO³ | Agent-S | remote_agent | phone_lib |
|------|------|---------|-------------|-----------|
| 键鼠控制 | ✅ UIA | ✅ pyautogui | ✅ pyautogui+Win32 | ✅ a11y+ADB |
| Shell执行 | ✅ | ✅ | ✅ 无超时风险 | — |
| 文件操作 | ✅ | ❌ | ✅ CRUD | ✅ /files |
| 进程管理 | ❌ | ❌ | ✅ list+kill | — |
| 服务管理 | ❌ | ❌ | ✅ start/stop | — |
| 网络自愈 | ❌ | ❌ | ✅ Guardian | ✅ ensure_alive |
| 跨会话 | ❌ | ❌ | ✅ PSRemoting | — |
| 防劫持 | ❌ | ❌ | ✅ MouseGuard | — |

**结论**：动作执行层我们**领先**业界开源方案，尤其是Guardian引擎、MouseGuard、跨会话、服务管理这些能力是独有的。

### 2.3 Agent编排（最值得学习的）

**UFO³ Galaxy 架构**（最先进的多设备编排）：
```
用户请求 → Constellation(任务分解) → DAG(有向无环图)
         → TaskStar(原子任务) + 依赖关系
         → 能力匹配(哪个设备能做)
         → 异步并行执行 + 动态改图
         → AIP协议(WebSocket安全通信)
```

**我们的现状**：
```
用户请求 → Cascade(单线程) → 逐步调API
         → 无DAG，无并行，无任务分解
         → 依赖Cascade上下文，不可持久化
```

**可借鉴**：
1. **任务DAG**：复杂操作分解为原子步骤+依赖图 → Guardian任务队列可扩展
2. **能力注册**：每台设备声明自己能做什么 → remote_agent `/health` 可扩展
3. **异步执行**：不等前一步完成就启动无依赖步骤 → Guardian已有基础
4. **MCP集成**：UFO³用MCP扩展工具 → 我们Windsurf已有MCP

### 2.4 安全与沙箱（业界趋势）

| 方案 | 沙箱 | 我们 |
|------|------|------|
| Bytebot | Docker虚拟桌面 | ❌ 无沙箱，直操宿主 |
| Cua | VM(Virtualization.framework) | ❌ 同上 |
| Anthropic CU | Docker参考实现 | ❌ 同上 |
| OpenAI CUA | 云端浏览器 | ❌ 同上 |

**我们的替代方案**：MouseGuard + Token认证 + Guardian规则 + 台式机保护铁律13条。
**不需要沙箱的原因**：我们的Agent是受控的(Windsurf Cascade)，不是自主运行的，有人在环路中。

---

## 三、自有资产总盘（AI操作电脑三件套）

### 3.1 remote_agent.py — PC控制核心

| 指标 | 值 |
|------|-----|
| **代码量** | 2354行，零框架依赖(纯stdlib) |
| **API数** | 45+端点，覆盖视觉/输入/数据/系统/守护五域 |
| **部署** | 双机对称(笔记本:9903 + 台式机:9903) |
| **穿透** | FRP(60.205.171.100:19903) + Cloudflare(临时) |
| **自愈** | Guardian Engine(SQLite+规则+任务+网络+进程监控) |
| **防护** | MouseGuard + Token认证 + 跨会话隔离 |
| **前端** | remote_desktop.html 2500行, 9面板, PWA, 触摸五感 |
| **测试** | 24轮 55+项自动化 |

### 3.2 phone_lib.py — 手机操控核心

| 指标 | 值 |
|------|-----|
| **代码量** | 1009行，零外部依赖(纯urllib) |
| **API封装** | 90+ ScreenStream HTTP API |
| **连接** | 五层自动发现: USB→WiFi→Tailscale→公网→局域网扫描 |
| **弹性** | 心跳+断线重连+7种负面状态自动恢复 |
| **五感** | vision/hearing/touch/smell/taste 全采集 |
| **测试** | 46/46全通过(standalone 36 + agent 5 + complex 5) |

### 3.3 Guardian Engine — 自治守护

| 指标 | 值 |
|------|-----|
| **嵌入** | remote_agent.py内置，SQLite持久化 |
| **规则** | 5种触发器: network_down/up, process_exit, cron, session_disconnect |
| **任务** | 提交/取消/清理，支持定时调度 |
| **网络** | 4级自愈链: DHCP→WiFi→网卡→DNS |
| **进程** | Watchdog监控+自动重启 |
| **独立** | 主脑断联后仍在台式机独立运行 |

---

## 四、祸 · 惑 · 问（诊断清单）

### 4.1 已治之祸（12/12）

| # | 祸名 | 状态 | 治法 |
|---|------|------|------|
| 1 | 延迟 | ✅ | 多通道(RDP/Sunshine/agent)按场景选 |
| 2 | 感官剥夺 | ⚠️部分 | 缩放+横屏；**音频待实现** |
| 3 | 精度 | ⚠️部分 | MouseGuard+快捷面板；**触控板模式待实现** |
| 4 | 穿透 | ✅ | FRP+Cloudflare+Tailscale三档 |
| 5 | 安全 | ⚠️部分 | Token认证；**FRP TLS+fail2ban待实现** |
| 6 | 冷启 | ✅ | 向日葵WoL+Guardian自愈+auto-start |
| 7 | 劫持 | ✅ | MouseGuard+跨会话 |
| 8 | 分身错乱 | ✅ | /health确认hostname |
| 9 | 竞态 | ✅ | MouseGuard+Guardian串行+铁律 |
| 10 | 会话断裂 | ✅ | 多端口+screen/info检测 |
| 11 | 认知分裂 | ✅ | 三连查(health+guard+screen/info) |
| 12 | 单向哑巴 | ⚠️ | Guardian事件驱动；**SSE/WebSocket待实现** |

### 4.2 新发现之祸（对标业界后）

| # | 新祸 | 根因 | 影响 | 解法 |
|---|------|------|------|------|
| 13 | **PC屏幕盲** | remote_agent截图是JPEG像素，AI看不懂 | Agent无法语义理解PC屏幕 | 接入OmniParser/VLM |
| 14 | **无任务持久化** | 复杂操作依赖Cascade会话，断了就丢 | 跨会话任务不可恢复 | Guardian任务队列扩展为DAG |
| 15 | **无能力注册** | 设备不声明自己能做什么 | 多设备编排靠人硬编码 | /capabilities端点 |
| 16 | **无统一协议** | remote_agent和phone_lib各自独立 | 不能统一编排手机+PC | 统一Agent协议(参考UFO³ AIP) |

### 4.3 已发现并修复之惑

| # | 惑 | 修复 |
|---|-----|------|
| 1 | SKILL.md端口写8086实际8084 | ✅ 已全部修正为8084 |
| 2 | AGENTS.md行数/文件列表过时 | ✅ 已更新为实际值 |
| 3 | 双电脑互联§十四演进路线不含新发现 | 见下方§五 |

---

## 五、演进路线（三阶段）

### Phase 1: 补短板（投入小，收益大）

| 项 | 内容 | 工作量 | 收益 |
|----|------|--------|------|
| **P1.1** | PC端 UIA 感知 | ~200行 | remote_agent获得结构化窗口元素(非截图) |
| **P1.2** | `/capabilities` 端点 | ~50行 | 设备自描述能力，为多设备编排奠基 |
| **P1.3** | SSE事件推送 | ~100行 | 治祸十二(单向哑巴)，台式机出事秒通知 |
| **P1.4** | 触控板相对移动 | ~30行 | 治祸三(精度)，手机远控精确移动鼠标 |
| **P1.5** | FRP TLS + 安全组 | 配置 | 治祸五(安全)，公网传输加密 |

### Phase 2: 借力VLM（接入AI视觉）

| 项 | 内容 | 工作量 | 收益 |
|----|------|--------|------|
| **P2.1** | OmniParser本地部署 | 部署+API | PC截屏→结构化元素，Agent可语义理解桌面 |
| **P2.2** | `/screen/elements` 端点 | ~100行 | remote_agent原生提供结构化UI元素 |
| **P2.3** | VLM决策循环 | ~200行 | Observe(截屏+解析)→Think(VLM)→Act(API) |
| **P2.4** | Ollama本地推理 | 已有 | 台式机64GB+已有5模型，可直接用 |

### Phase 3: 多设备Galaxy（长期愿景）

| 项 | 内容 | 灵感来源 | 收益 |
|----|------|----------|------|
| **P3.1** | 统一Agent协议 | UFO³ AIP | 手机+笔记本+台式机统一编排 |
| **P3.2** | 任务DAG引擎 | UFO³ Constellation | 复杂工作流分解+并行+持久化 |
| **P3.3** | 能力发现+匹配 | UFO³ Galaxy | 自动选择最优设备执行 |
| **P3.4** | 双向心跳+告警 | 自有 | 任何设备断联→秒级告警 |

---

## 六、技术方案速查（可直接实施）

### 6.1 UIA感知（Phase 1.1）

```python
# remote_agent.py 新增 /screen/elements 端点
import ctypes
from ctypes import wintypes
import comtypes.client

def get_ui_elements():
    """使用Windows UI Automation获取当前窗口所有元素"""
    uia = comtypes.client.CreateObject("{ff48dba4-60ef-4201-aa87-54103eef594e}")
    root = uia.GetRootElement()
    # 获取焦点窗口 → 遍历子元素 → 返回 {name, type, bbox, clickable}
    # 比截图+OCR更快更准
```

**替代方案**（更简单）：
```python
# 用 pywinauto（纯Python，pip install pywinauto）
from pywinauto import Desktop
desktop = Desktop(backend="uia")
windows = desktop.windows()
for w in windows:
    elements = w.descendants()  # 所有UI元素
```

### 6.2 SSE事件推送（Phase 1.3）

```python
# remote_agent.py 新增 GET /events/stream (SSE)
def handle_sse(self):
    self.send_response(200)
    self.send_header("Content-Type", "text/event-stream")
    self.send_header("Cache-Control", "no-cache")
    self.send_header("Connection", "keep-alive")
    self.end_headers()
    while True:
        event = guardian.wait_event(timeout=30)
        if event:
            self.wfile.write(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode())
            self.wfile.flush()
        else:
            self.wfile.write(b": keepalive\n\n")  # heartbeat
            self.wfile.flush()
```

### 6.3 OmniParser接入（Phase 2.1）

```python
# 台式机已有Ollama(64GB RAM)，可本地运行OmniParser
# 安装: pip install omniparser  (或 Docker)
# 使用:
from omniparser import OmniParser
parser = OmniParser()
screenshot = mss.mss().grab(mss.mss().monitors[1])
elements = parser.parse(screenshot)
# → [{"label":"Settings", "type":"button", "bbox":[100,200,200,250], "confidence":0.95}, ...]
```

### 6.4 统一Agent协议（Phase 3.1 草案）

```json
// 设备能力声明 GET /capabilities
{
    "device_id": "desktop-master",
    "type": "windows_pc",
    "capabilities": ["screenshot", "keyboard", "mouse", "shell", "files", "services", "network_heal", "guardian"],
    "status": "online",
    "load": {"cpu": 15, "ram_pct": 32},
    "endpoints": {
        "control": "http://192.168.31.141:9903",
        "files": "http://192.168.31.141:9998"
    }
}

// 手机能力声明
{
    "device_id": "samsung-s23u",
    "type": "android_phone",
    "capabilities": ["screen_text", "tap", "swipe", "intent", "notifications", "volume", "brightness", "files"],
    "status": "online",
    "battery": 85,
    "endpoints": {
        "control": "http://192.168.31.100:8084"
    }
}

// 任务提交 POST /tasks
{
    "workflow": "send_wechat_photo",
    "steps": [
        {"device": "windows_pc", "action": "file/download", "params": {"path": "D:\\photo.jpg"}},
        {"device": "android_phone", "action": "intent", "params": {"action": "VIEW", "package": "com.tencent.mm"}},
        {"device": "android_phone", "action": "findclick", "params": {"text": "发现"}}
    ]
}
```

---

## 七、与业界的终极对标

### 我们独有（护城河）

| 能力 | 说明 | 竞品有吗 |
|------|------|----------|
| **Guardian自治引擎** | 断网自愈+进程监控+事件规则+任务队列 | ❌ 全球独有 |
| **MouseGuard防劫持** | 检测物理输入，cooldown保护 | ❌ 全球独有 |
| **跨Windows会话** | 不同用户会话独立Agent | ❌ 全球独有 |
| **手机五感全采集** | vision/hearing/touch/smell/taste | ❌ 全球独有 |
| **双机对称架构** | 同代码同端口，角色随行为流转 | ❌ 全球独有 |
| **零框架零依赖** | 纯stdlib运行，部署极简 | ❌ 独有(UFO要pip一堆) |
| **PWA触摸前端** | 手机浏览器全功能操控PC | ❌ 独有 |

### 业界领先但我们缺（需补的）

| 能力 | 说明 | 来源 |
|------|------|------|
| **VLM屏幕理解** | AI看懂PC屏幕内容 | OmniParser/UI-TARS |
| **多设备DAG编排** | 复杂任务分解+并行 | UFO³ Galaxy |
| **UIA原生感知** | 结构化UI元素(非截图) | UFO²/pywinauto |
| **经验学习** | 从成功操作中学习模式 | Agent-S |

---

## 八、参考资源索引

### 策展列表
- **[trycua/acu](https://github.com/trycua/acu)** — AI Computer Use资源大全（论文+项目+框架+工具）

### 核心项目
- **[microsoft/UFO](https://github.com/microsoft/UFO)** — 多设备Agent Galaxy
- **[microsoft/OmniParser](https://github.com/microsoft/OmniParser)** — 屏幕→结构化元素
- **[bytedance/UI-TARS-desktop](https://github.com/bytedance/UI-TARS-desktop)** — VLM桌面Agent
- **[simular-ai/Agent-S](https://github.com/simular-ai/Agent-S)** — 经验学习Agent
- **[openinterpreter/open-interpreter](https://github.com/openinterpreter/open-interpreter)** — 对话式电脑控制

### API文档
- **[Anthropic Computer Use](https://docs.anthropic.com/en/docs/build-with-claude/computer-use)** — Claude computer tool
- **[OpenAI CUA](https://platform.openai.com/docs/guides/tools-computer-use)** — Computer-Using Agent API

### 自有文档链
- `文档/AI_PHONE_CONTROL.md` — **AI操控手机全景图**（40+项目对标+演进路线）
- `远程桌面/README.md` — remote_agent完整API文档
- `手机操控库/README.md` — phone_lib使用指南
- `双电脑互联/README.md` — 五感全景架构(710行)
- `台式机保护/README.md` — 铁律13条+守护体系(250行)
- `.windsurf/skills/agent-phone-control/SKILL.md` — Agent操控手机技能

---

*汇总自：GitHub 30+项目 + 官方文档 + 自有三件套全量代码 + Memory 20+条*
*先增再减，再增再简，取之于精华，归之于总。*
