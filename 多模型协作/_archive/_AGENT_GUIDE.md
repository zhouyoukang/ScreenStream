# 多模型协作 · Agent操作指令

> Agent为中枢·零手动操作。**E2E: 45/46 PASS (97.8%)**。五层+Router: 43模型零干扰可调用。

## 核心入口 (v4.0, 2026-03-14)

| 文件 | 用途 | 状态 |
|------|------|------|
| `multi_model_engine.py` | ★统一引擎v4.0: 五层调度+Router+CSRF+F91 | ✅ 45/46 E2E |
| `_e2e_all_models.py` | ★全量E2E: Router 44+Private LS+Bridge | ✅ 43/44 Router |
| `windsurf_cli.py` | Private LS chat引擎: GPT-4o/mini文本Q&A | v4.0 ✅ |
| `cli_dispatch.py` | 并行dispatch引擎: subprocess + ThreadPool | v1.0 ✅ |
| `_extract_csrf_env.py` | CSRF提取: PEB读取Running LS环境变量 | v1.0 ✅ |
| `windsurf-cli-bridge/` | CLI Bridge扩展(:19850) 3039 vscode命令 | v1.0 ✅ |

## 五层+Router调度架构

```
L1:   Private LS (:19852) → GPT-4o/mini 文本Q&A (零UI, 需auto-restart)
L1.5: Model Router (:18881) → 43/44模型 (零UI, 4 Provider, OpenAI兼容API)
L2:   Running LS (动态端口) → CSRF from PEB → Heartbeat/GetUserStatus
L3:   CLI Bridge (:19850) → 3039 vscode commands → eval/文件/命令 (零UI)
L4:   Cascade Pipeline → sendTextToChat + stopListeningAndSubmit (最小UI)
L5:   sendChatActionMessage → {actionType:N} 程序化控制 (零UI)
```

## Agent命令

```bash
# 统一引擎
python multi_model_engine.py boot       # 初始化全部层
python multi_model_engine.py status     # 系统状态
python multi_model_engine.py ask "x"    # GPT-4o via Private LS
python multi_model_engine.py models     # 模型矩阵
python multi_model_engine.py test       # 14项E2E测试

# Python API
from multi_model_engine import MultiModelEngine
engine = MultiModelEngine()
engine.boot()
engine.ask("问题")                       # Private LS GPT-4o
engine.ask_router("问题", model="qwen3-8b")  # Router 44+模型
engine.ask_router("问题", model="gpt-4o")    # GitHub Models
engine.dispatch_cascade("prompt")         # Cascade当前模型
engine.send_action(17)                    # NEW_CONVERSATION
engine.send_action(18)                    # CHANGE_MODEL
engine.read_file("path")                  # 零干扰文件读
engine.eval_js("js code")                 # Extension Host JS
```

## 实测通过模型矩阵 (45/46, 2026-03-14)

### Router: 43/44 PASS
| Provider | 模型 | 延迟 | 状态 |
|----------|------|------|------|
| Ollama | qwen3-8b, gemma3-4b, deepseek-r1-8b | 3-9s | ✅ |
| GitHub | gpt-4o, gpt-4o-mini, deepseek-r1, llama-405b, llama-70b, phi-4, cohere-r | 2-14s | ✅ |
| g4f | gpt-4 | 6s | ✅ |
| Groq | llama-70b, llama-8b, mixtral-8x7b, gemma2-9b | 2-3s | ✅ |
| Gemini | gemini-2.5-flash/pro, gemini-2.0-flash | 2-3s | ✅ |
| OpenRouter | deepseek-r1/v3-free, llama-70b-free, gemini-free, qwen-72b-free, mistral-free | 2-3s | ✅ |
| Cerebras | llama-70b, llama-8b | 2-12s | ✅ |
| Mistral | mistral-small, codestral, mistral-nemo | 2-3s | ✅ |
| Cohere | command-r-plus, command-r, command-light | 2-3s | ✅ |
| HuggingFace | qwen2.5-72b, llama-70b, mistral-7b | 3-4s | ✅ |
| SiliconFlow | deepseek-v3/r1, qwen2.5-7b | 2s | ✅ |
| DeepSeek | deepseek-chat, deepseek-reasoner | 2-14s | ✅ |
| Together | llama-70b, deepseek-r1-70b, qwen2.5-72b | 2-3s | ✅ |

### 8个命令模型 (Cascade可调度)
| 模型 | 成本 | 调用路径 |
|------|------|---------|
| Claude Opus 4.6 Thinking 1M | 12x | Cascade(当前) |
| SWE-1.5 | 0x ★FREE | switchToNextModel循环 |
| GPT-4.1 | 1x | switchToNextModel循环 |
| Claude Sonnet 4.5 | 2x | switchToNextModel循环 |
| Claude Sonnet 4 | 2x | switchToNextModel循环 |
| Claude Haiku 4.5 | 1x | switchToNextModel循环 |
| GPT 5.1 | 0.5x | switchToNextModel循环 |
| Windsurf Fast | 0.5x | switchToNextModel循环 |

## ChatActionType枚举 (sendChatActionMessage)
| 值 | 名称 | 用途 |
|---|------|------|
| 13 | CHAT_MENTION_INSERT | 插入@提及 |
| 14 | CHAT_OPEN_SETTINGS | 打开设置 |
| 15 | CHAT_OPEN_CONTEXT_SETTINGS | 上下文设置 |
| 16 | CHAT_WITH_CODEBASE | 使用代码库 |
| 17 | CHAT_NEW_CONVERSATION | 新建对话 |
| 18 | CHAT_CHANGE_MODEL | 切换模型 |
| 19 | CHAT_MENTION_MENU_OPEN | @菜单 |
| 34 | CHAT_TOGGLE_FOCUS_INSERT_TEXT | 聚焦输入 |

## 修改规则
- CSRF每次LS重启后变化 → engine.boot()自动PEB提取
- Running LS端口动态变化 → engine自动发现(>60000端口扫描)
- Running LS CSRF header: `x-csrf-windsurf` (非x-codeium-csrf-token)
- SendUserCascadeMessage直接gRPC会crash LS → 用L4 Cascade Pipeline
- F91 = windsurfConfigurations field 91 = selectedCommandModel (string)
- Private LS不稳定(crash后1-2请求) → engine.boot()自动重启
- 禁止bare except，必须用except Exception
