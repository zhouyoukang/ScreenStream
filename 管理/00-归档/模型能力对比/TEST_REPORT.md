# Windsurf 全模型后端测试报告

> 生成时间: 2026-03-07 03:54:21
> 测试方法: 不依赖IDE页面, 直接后端API调用
> Python: 3.12.7 | 平台: win32

## 一、环境概览

| 组件 | 状态 | 详情 |
|------|------|------|
| CFW代理 | ✅ | 127.0.0.1:443 |
| Clash代理 | ✅ | 127.0.0.1:7890 |
| 语言服务器 | ✅ | 1个进程 |
| Windsurf JS | ✅ | D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js |
| API Keys | 9个 | SECRET_QUESTION_ANSWER, FRP_TOKEN, HA_TOKEN, WECHAT_APPSECRET, WECHAT_TOKEN, GITHUB_PERSONAL_ACCESS_TOKEN, HF_TOKEN, SAKURACAT_SUB_TOKEN, REMOTE_AGENT_TOKEN |

### 语言服务器进程

| PID | API Server | Ext Port | Version |
|-----|-----------|----------|---------|
| 28908 | https://server.self-serve.windsurf.com | 49378 | 1.9566.11 |

## 二、路径A — CFW代理测试

| 测试项 | 状态 | 详情 |
|--------|------|------|
| tcp_probe | ✅ pass |  |
| https_get | ✅ pass | 200 OK |
| grpc_heartbeat | ✅ pass | 200 ct=application/proto |
| grpc_GetUser | ✅ pass | status=200 body=0B grpc_status= |
| grpc_GetApiKeySummary | ✅ pass | status=200 body=0B grpc_status= |
| grpc_GetChatMessage | ✅ pass | status=200 body=0B grpc_status= |
| grpc_GetProcesses | ✅ pass | status=200 body=0B grpc_status= |

## 三、路径B — 模型提供商API测试

| 提供商 | 模型 | 状态 | 延迟 | 响应预览 |
|--------|------|------|------|----------|
| HuggingFace | meta-llama/llama-3.1-8b-instruct | ✅ success | 4099ms | ```python def fibonacci(n, memo={}):     """     Calculate t |

## 四、路径C — 本地语言服务器探测

- 监听端口: [61805, 61801, 57845, 57421, 49911, 49390, 49381]

| 端口 | 协议 | 状态 | 详情 |
|------|------|------|------|
| 61805 | connect | ❌ 502 | body=0B |
| 61801 | connect | ❌ 404 | body=22B |
| 57845 | connect | ❌ 404 | body=9B |
| 57421 | connect | ❌ 404 | body=66B |
| 49911 | connect | ❌ 404 | body=377B |

## 五、模型枚举全景（58个用户可见模型）

| # | 枚举ID | 提供商 | 名称 | 级别 | 积分 |
|---|--------|--------|------|------|------|
| 1 | `MODEL_CLAUDE_4_6_OPUS` | Anthropic | Claude 4.6 Opus | premium | 10x |
| 2 | `MODEL_CLAUDE_4_6_SONNET` | Anthropic | Claude 4.6 Sonnet | premium | 2x |
| 3 | `MODEL_CLAUDE_4_5_OPUS` | Anthropic | Claude 4.5 Opus | premium | 10x |
| 4 | `MODEL_CLAUDE_4_5_OPUS_THINKING` | Anthropic | Claude 4.5 Opus (Thinking) | premium | 10x |
| 5 | `MODEL_CLAUDE_4_5_SONNET` | Anthropic | Claude 4.5 Sonnet | premium | 2x |
| 6 | `MODEL_CLAUDE_4_5_SONNET_THINKING` | Anthropic | Claude 4.5 Sonnet (Thinking) | premium | 2x |
| 7 | `MODEL_CLAUDE_4_5_SONNET_1M` | Anthropic | Claude 4.5 Sonnet 1M | premium | 4x |
| 8 | `MODEL_CLAUDE_4_1_OPUS` | Anthropic | Claude 4.1 Opus | premium | 10x |
| 9 | `MODEL_CLAUDE_4_OPUS` | Anthropic | Claude 4 Opus | premium | 10x |
| 10 | `MODEL_CLAUDE_4_SONNET` | Anthropic | Claude 4 Sonnet | premium | 2x |
| 11 | `MODEL_CLAUDE_4_SONNET_THINKING` | Anthropic | Claude 4 Sonnet (Thinking) | premium | 2x |
| 12 | `MODEL_CLAUDE_3_7_SONNET_20250219` | Anthropic | Claude 3.7 Sonnet | standard | 1x |
| 13 | `MODEL_CLAUDE_3_5_SONNET_20241022` | Anthropic | Claude 3.5 Sonnet | standard | 1x |
| 14 | `MODEL_CLAUDE_3_5_HAIKU_20241022` | Anthropic | Claude 3.5 Haiku | lite | 0.5x |
| 15 | `MODEL_CHAT_GPT_5_4` | OpenAI | GPT-5.4 | premium | 1x |
| 16 | `MODEL_CHAT_GPT_5_3_CODEX_SPARK` | OpenAI | GPT-5.3 Codex Spark | standard | 1x |
| 17 | `MODEL_CHAT_GPT_5_3_CODEX` | OpenAI | GPT-5.3 Codex | standard | 1x |
| 18 | `MODEL_CHAT_GPT_5_2` | OpenAI | GPT-5.2 | premium | 2x |
| 19 | `MODEL_CHAT_GPT_5` | OpenAI | GPT-5 | premium | 2x |
| 20 | `MODEL_CHAT_GPT_5_HIGH` | OpenAI | GPT-5 High | premium | 4x |
| 21 | `MODEL_CHAT_GPT_5_LOW` | OpenAI | GPT-5 Low | standard | 1x |
| 22 | `MODEL_CHAT_GPT_5_CODEX` | OpenAI | GPT-5 Codex | premium | 2x |
| 23 | `MODEL_CHAT_GPT_4_5` | OpenAI | GPT-4.5 | premium | 4x |
| 24 | `MODEL_CHAT_GPT_4_1_2025_04_14` | OpenAI | GPT-4.1 | standard | 1x |
| 25 | `MODEL_CHAT_GPT_4_1_MINI_2025_04_14` | OpenAI | GPT-4.1 Mini | lite | 0.5x |
| 26 | `MODEL_CHAT_GPT_4O_2024_08_06` | OpenAI | GPT-4o | standard | 1x |
| 27 | `MODEL_CHAT_GPT_4O_MINI_2024_07_18` | OpenAI | GPT-4o Mini | lite | 0.25x |
| 28 | `MODEL_CHAT_O3` | OpenAI | O3 | premium | 4x |
| 29 | `MODEL_CHAT_O3_MINI` | OpenAI | O3 Mini | standard | 1x |
| 30 | `MODEL_CHAT_O4_MINI` | OpenAI | O4 Mini | standard | 1x |
| 31 | `MODEL_O3_PRO_2025_06_10` | OpenAI | O3 Pro | premium | 20x |
| 32 | `MODEL_CODEX_MINI_LATEST` | OpenAI | Codex Mini | standard | 1x |
| 33 | `MODEL_GOOGLE_GEMINI_3_1_PRO_HIGH` | Google | Gemini 3.1 Pro | premium | 1x |
| 34 | `MODEL_GOOGLE_GEMINI_3_0_PRO_HIGH` | Google | Gemini 3.0 Pro | premium | 2x |
| 35 | `MODEL_GOOGLE_GEMINI_3_0_FLASH_HIGH` | Google | Gemini 3.0 Flash | standard | 1x |
| 36 | `MODEL_GOOGLE_GEMINI_2_5_PRO` | Google | Gemini 2.5 Pro | premium | 2x |
| 37 | `MODEL_GOOGLE_GEMINI_2_5_FLASH` | Google | Gemini 2.5 Flash | lite | 0.5x |
| 38 | `MODEL_GOOGLE_GEMINI_2_0_FLASH` | Google | Gemini 2.0 Flash | lite | 0.25x |
| 39 | `MODEL_DEEPSEEK_V3_2` | DeepSeek | DeepSeek V3.2 | standard | 1x |
| 40 | `MODEL_DEEPSEEK_R1` | DeepSeek | DeepSeek R1 | standard | 1x |
| 41 | `MODEL_XAI_GROK_3` | xAI | Grok 3 | premium | 2x |
| 42 | `MODEL_XAI_GROK_3_MINI_REASONING` | xAI | Grok 3 Mini | standard | 1x |
| 43 | `MODEL_XAI_GROK_CODE_FAST` | xAI | Grok Code Fast | lite | 0.5x |
| 44 | `MODEL_QWEN_3_CODER_480B_INSTRUCT` | Qwen | Qwen 3 Coder 480B | standard | 1x |
| 45 | `MODEL_QWEN_3_235B_INSTRUCT` | Qwen | Qwen 3 235B | standard | 1x |
| 46 | `MODEL_KIMI_K2_5` | Moonshot | Kimi K2.5 | standard | 1x |
| 47 | `MODEL_KIMI_K2` | Moonshot | Kimi K2 | standard | 1x |
| 48 | `MODEL_KIMI_K2_THINKING` | Moonshot | Kimi K2 (Thinking) | standard | 1x |
| 49 | `MODEL_GLM_5` | Zhipu | GLM-5 | premium | 1x |
| 50 | `MODEL_GLM_4_7` | Zhipu | GLM 4.7 | standard | 1x |
| 51 | `MODEL_GLM_4_6` | Zhipu | GLM 4.6 | standard | 1x |
| 52 | `MODEL_GLM_4_5` | Zhipu | GLM 4.5 | standard | 1x |
| 53 | `MODEL_MINIMAX_M2_5` | MiniMax | Minimax M2.5 | standard | 1x |
| 54 | `MODEL_MINIMAX_M2_1` | MiniMax | MiniMax M2.1 | standard | 1x |
| 55 | `MODEL_LLAMA_3_3_70B_INSTRUCT` | Meta | Llama 3.3 70B | lite | 0.25x |
| 56 | `MODEL_SWE_1_5` | Windsurf | SWE-1.5 | free | 0x |
| 57 | `MODEL_SWE_1_6` | Windsurf | SWE-1.6 | free | 0x |
| 58 | `MODEL_SWE_1_6_FAST` | Windsurf | SWE-1.6 Fast | free | 0x |

## 六、伏羲八卦辩证分析

### 6.1 八维能力雷达

| 卦象 | 维度 | 得分 | 发现 |
|------|------|------|------|
| ☰乾_编码 | ░░░░░░░░░░ | 0/10 | 无法直接测试编码能力（需要IDE交互） |
| ☱兑_感知 | ██████████ | 10.0/10 | 提供商API 1/1 成功 |
| ☲离_速度 | ██████░░░░ | 6/10 | 平均延迟: 4099ms |
| ☳震_成本 | ████████░░ | 8/10 | 3个免费模型 (SWE系列), BYOK降本路径可用 |
| ☴巽_工具 | ██████████ | 10/10 | CFW gRPC 7个端点可达 |
| ☵坎_推理 | ███████░░░ | 7/10 | 已验证模型推理输出 |
| ☶艮_安全 | ██████████ | 10/10 | 0个错误 / 1个测试 |
| ☷坤_上下文 | ████████░░ | 8/10 | 覆盖58个模型, 8个提供商 |
| **总分** | | **59.0/80** | |

### 6.2 发现的问题

- **P4: 语言服务器7个端口监听但gRPC连接失败**

### 6.3 关键洞见

- I1: Windsurf通过gRPC-web代理转发到Codeium后端, CFW在中间注入auth_token
- I2: 语言服务器端口监听但不接受外部HTTP连接 — 可能仅接受pipe连接
- I3: 58个用户可见模型, 240+总枚举(含内部/embedding/tab)
- I4: 免费模型(SWE-1.5/1.6)在Arena排名超越付费模型 — 成本效率最优
- I5: BYOK支持OpenRouter/vLLM/Databricks等自定义端点

### 6.4 解决方案

- S1: 添加BYOK API Keys到环境变量 → 直接测试各提供商模型
- S2: 通过CFW gRPC-web代理测试Windsurf原生模型
- S3: 使用HuggingFace免费推理API测试开源模型
- S4: 逆向语言服务器gRPC协议 → 直接调用本地服务
- S5: 编写IDE扩展注入测试 → 通过Windsurf内部API测试

## 七、结论

### 后端直调可行性

| 路径 | 可行性 | 说明 |
|------|--------|------|
| A. CFW gRPC代理 | ⚠️ 部分 | gRPC端点可达但缺少auth_token |
| B. 提供商直调 | ✅ 可行 | BYOK路径, 需各提供商API Key |
| C. 语言服务器 | ❌ 受限 | 端口监听但gRPC连接超时/拒绝 |

### 推荐行动

1. **立即可做**: 添加DeepSeek/DashScope/智谱AI免费API Key到环境变量
2. **中期**: 开发Windsurf扩展注入,从IDE内部获取auth_token
3. **长期**: 完整逆向Codeium gRPC协议,实现独立调用

---
*由 model_test.py v1.0 自动生成 | 伏羲八卦 × 全模型测试*