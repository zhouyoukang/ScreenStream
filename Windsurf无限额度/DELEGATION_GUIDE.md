# 多模型委派实操指南 v1.0

> 反者道之动，弱者道之用。不从零开发，只用已有工具。

## 已验证的3条委派路径

### 路径A: g4f外部推理（当前最强，零新开发）

**原理**: 1次`run_command` → Python g4f库 → 零认证外部模型 = 1 Windsurf invocation获得外部推理

**已验证的Provider**:

| Provider | 模型 | 延迟 | 认证 |
|----------|------|------|------|
| Groq | llama-3.3-70b-versatile | **1.7s** | 零 |
| PollinationsAI | openai (GPT-4o-mini) | 10.1s | 零 |

**一行调用（在Cascade中通过run_command执行）**:

```python
# Groq Llama 70B — 1.7秒, 零认证
python -c "
import os; os.environ['G4F_PROXY']='http://127.0.0.1:7890'
from g4f.client import Client; from g4f import Provider
c = Client(provider=Provider.Groq)
r = c.chat.completions.create(model='llama-3.3-70b-versatile',
    messages=[{'role':'user','content':'你的任务指令'}], timeout=30)
print(r.choices[0].message.content)
"
```

**使用场景**: 
- Agent(Opus)需要外部模型帮忙分析/生成代码片段 → 1次run_command调g4f
- 不消耗额外Windsurf积分（仅1个invocation）
- 适合：代码生成、文本分析、方案对比

### 路径B: SWE-1.5零成本委派（最简，用户手动）

**原理**: 用户在新对话中选择SWE-1.5 Free → 0 credits执行任何任务

**步骤**:
1. 当前Agent(Opus)创建任务描述 → 写入文件或输出到聊天
2. 用户打开**新Cascade对话**(Ctrl+L 或侧边栏+号)
3. 用户在模型选择器中选择**SWE-1.5 Free**
4. 用户粘贴任务描述
5. SWE-1.5执行（0 credits）
6. 结果在文件系统中可见，用户可切回Opus验证

**适合**: 所有常规编码/修改/搜索任务

### 路径C: CLI Bridge程序化委派（半自动）

**已验证能力**:
- `switchToNextModel` ✅ — 可程序化循环切换模型
- `/api/health` `/api/status` ✅ — 健康检测
- `sendTextToChat` ❌ — 500错误
- `sendChatActionMessage` ❌ — 500错误（含TOGGLE_FOCUS/actionType等所有格式）
- `eval` ✅ — 可执行JS

**结论**: CLI Bridge当前版本仅支持基础VS Code命令，不支持Windsurf专有聊天命令。
文本注入和新对话创建必须用户手动完成。`switchToNextModel`是唯一可用的模型相关自动化。

**可用命令**:
```bash
# 创建委派任务文件
python Windsurf无限额度/credit_toolkit.py delegate "任务描述" "执行步骤"

# 程序化切换到下一个模型（循环）
python -c "import urllib.request,json;print(json.loads(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:19850/api/execute',data=json.dumps({'command':'windsurf.cascade.switchToNextModel'}).encode(),headers={'Content-Type':'application/json'},method='POST'),timeout=5).read()))"
```

## 已有工具完整清单（零新开发）

### 在线服务（当前可用）

| 服务 | 端口 | 能力 | 委派价值 |
|------|------|------|---------|
| CLI Bridge | :19850 | switchToNextModel、eval | ★★★ 模型切换 |
| Dispatch MCP | :19860 | 任务文件管理 | ★★ 任务持久化 |
| VSIX | :19870 | Webview面板 | ★ 可视化 |
| Python Hub | :9090 | 通用API | ★ 辅助 |

### 需启动的服务

| 服务 | 启动命令 | 能力 | 委派价值 |
|------|---------|------|---------|
| Model Router | `python 龙虾资源/model_router.py` | 21 Provider, 118+模型, OpenAI兼容API | ★★★★ |
| Ollama | `ollama serve` | 本地模型(qwen3:8b等) | ★★★ |

### 已有Python工具

| 文件 | 核心功能 | 直接可用 |
|------|---------|---------|
| `credit_toolkit.py` | monitor/delegate/auto-delegate | ✅ |
| `patch_continue_bypass.py` | P1-P4 AutoContinue | ✅ |
| `dispatch_engine.py` | 任务文件创建/管理 | ✅ |
| `dispatch_mcp.py` | MCP服务端(3工具) | ✅ |
| `model_router.py` | 21 Provider统一API | 需启动 |
| `telemetry_reset.py` | 设备指纹重置 | ✅ |
| `windsurf_reverse_hub.py` | 5层统一中枢 | 需启动 |

### 已有VSIX扩展

| 文件 | 功能 |
|------|------|
| `windsurf-cli-bridge.vsix` | CLI Bridge(已安装) |
| `dispatch-commander-1.0.0.vsix` | 委派面板+HTTP API(已安装) |

## 最优委派策略矩阵

| 场景 | 最优路径 | 步骤数 | 成本 |
|------|---------|--------|------|
| 需要外部模型意见 | 路径A: g4f run_command | 1步(run_command) | 0 extra cr |
| 常规编码任务 | 路径B: 新对话SWE-1.5 | 3步(新对话→选模型→粘贴) | 0 cr |
| 批量文件修改 | 路径B: SWE-1.5 | 3步 | 0 cr |
| 复杂架构分析 | 路径A: g4f + 当前Agent综合 | 2步 | 0 extra cr |
| 多任务并行 | Wave 13 多Cascade面板 | 各面板独立选模型 | 视模型 |

## 用户手动互联交互指南

### 准备步骤（一次性）

1. **确认g4f可用**: 
   ```
   python -c "from g4f.client import Client; print('g4f OK')"
   ```

2. **确认CLI Bridge在线**:
   ```
   python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:19850/api/health', timeout=2); print('Bridge OK')"
   ```

3. **(可选) 启动Model Router**:
   ```
   python 龙虾资源/model_router.py
   ```

### 委派执行模式

**模式1: Opus规划 → SWE-1.5执行**
```
1. 在当前对话(Opus)中分析问题，产出任务描述
2. Ctrl+L 打开新Cascade面板
3. 选择SWE-1.5 Free (0x)
4. 粘贴任务 → SWE-1.5执行
5. 切回Opus面板验证结果
```

**模式2: 当前Agent调用外部模型**
```
Agent在对话中执行:
  run_command → python g4f脚本 → Groq Llama 70B响应(1.7s)
  → Agent分析响应 → 继续执行
```

**模式3: 多面板并行(Wave 13)**
```
面板1: Opus (架构/规划)
面板2: SWE-1.5 (执行任务A, 0cr)  
面板3: SWE-1.5 (执行任务B, 0cr)
Git Worktrees隔离各面板工作区
```

## 官方限制与规避

| 限制 | 性质 | 规避方案 |
|------|------|---------|
| 服务端积分计费 | 不可绕过 | 用0x模型(SWE-1.5) |
| ~25 invocation/prompt | 不可绕过 | run_command批处理+并行tools |
| 无精确模型选择API | 不可绕过 | switchToNextModel循环 或 用户手动选 |
| sendTextToChat不可用 | CLI Bridge限制 | 用户手动粘贴 |
| 跨对话通信 | 无API | 文件系统(dispatch/task_xxx.md) |

## 结论

**零新开发**。所有工具已就绪：
- g4f(已安装) + CLI Bridge(已运行) + credit_toolkit(已有) + dispatch(已有)

**最大突破**: `run_command → g4f → Groq` = 1.7秒获得Llama 70B推理，消耗仅1个Windsurf invocation。

**最简路径**: 新对话 → SWE-1.5 Free → 0 credits执行。

**用户只需**: 理解3条路径 → 手动在新对话中选SWE-1.5 → 粘贴任务 → 执行。
