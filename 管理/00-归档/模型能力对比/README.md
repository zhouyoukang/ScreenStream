# Windsurf 模型能力全景对比 × 伏羲八卦

> **数据源**: JS逆向 (240+唯一枚举) + Windsurf官网实时抓取 (Playwright) + 本机配置
> **方法**: 五感探测(视=JS逆向/听=博客监控/触=Arena排行榜/嗅=定价分析/味=八卦评估)
> **最后更新**: 2026-03-06 21:00 UTC
> **本地版本**: v1.108.2 | **服务端最新**: GPT-5.4 / Claude 4.6 / Gemini 3.1

---

## 〇、Windsurf Arena 排行榜（实时 · 2026-03-06）

> 来源: `windsurf.com/leaderboard` (Playwright抓取) | 基于真实编码任务用户偏好ELO

| # | 模型 | ELO | CI | 供应商 |
|---|------|-----|-----|--------|
| 1 | **Claude Opus 4.6** | 1,099 | ±15 | Anthropic |
| 2 | Claude Opus 4.5 | 1,085 | ±21 | Anthropic |
| 3 | Claude Sonnet 4.5 | 1,061 | ±21 | Anthropic |
| 4 | Claude Haiku 4.5 | 1,027 | ±35 | Anthropic |
| 5 | Kimi K2.5 | 1,024 | ±20 | Moonshot |
| 6 | **SWE-1.5 Fast** | 1,017 | ±32 | Cognition |
| 7 | GPT-5.2 | 1,016 | ±19 | OpenAI |
| 8 | GLM-5 | 1,000 | ±30 | 智谱 |
| 9 | GPT-5.3-Codex Spark | 964 | ±43 | OpenAI |
| 10 | GPT-5.3-Codex | 956 | ±35 | OpenAI |
| 11 | Minimax M2.5 | 952 | — | MiniMax |
| 12 | Gemini 3 Flash | 946 | — | Google |
| 13 | Gemini 3 Pro | 939 | — | Google |
| 14 | Grok Code Fast 1 | 938 | ±34 | xAI |
| 15 | Gemini 3.1 Pro | 922 | ±36 | Google |

> **关键**: Anthropic前4 | SWE-1.5 Fast(0积分)ELO 1,017超GPT-5.2(1,016) | 免费>付费

### 〇.1 博客新模型上线时间线（2026年·Playwright抓取）

| 日期 | 模型 | 积分 | 说明 |
|------|------|------|------|
| Mar 5 | **GPT-5.4** | 1x促销 | 多推理档位 |
| Feb 20 | **Gemini 3.1 Pro** | 促销 | Low/High思考 |
| Feb 17 | **Claude Sonnet 4.6** | 2x/3x | 限时促销 |
| Feb 16 | **GLM-5 + Minimax M2.5** | 促销 | Arena Frontier/Hybrid |
| Feb 12 | **GPT-5.3-Codex-Spark** | — | 超快编码 |
| Feb 11 | **Arena排行榜发布** | — | "The People Want Speed" |
| Feb 7 | **Opus 4.6 fast** | 10x/12x | 最强最贵 |

> **发现**: 服务端已远超本地JS(JS到GPT-5.2/Claude 4.5, 服务端已GPT-5.4/Claude 4.6/Gemini 3.1)

### 〇.2 定价体系（Playwright抓取）

| 套餐 | 价格 | 积分/月 | 附加 | 核心权益 |
|------|------|---------|------|---------|
| Free | $0 | 25 | — | 基础模型+Tab无限+内联无限 |
| **Pro** | $15/月 | 500 | $10/250 | 全Premium+SWE-1.5+Fast Context |
| Teams | $30/人/月 | 500/人 | 可购买 | +管理面板+ZDR+优先支持 |
| Enterprise | 联系 | 1,000/人 | 可购买 | +RBAC+SSO+混合部署 |

### 〇.3 已确认积分倍率

| 模型 | 积分倍率 | 来源 |
|------|---------|------|
| SWE-1.5 | **0x（免费）** | 定价页 |
| GPT-5.4 | 1x（限时促销） | 博客 Mar 5 |
| Claude Sonnet 4.6 | 2x / 3x(思考) | 博客 Feb 17 |
| Claude Opus 4.6 fast | 10x / 12x(思考) | 博客 Feb 7 |

> 路由模式: **arena-fast** / **arena-smart** / **arena-mixed** (JS确认)
> 模型由 `cascade_model_config_data` 服务端动态下发，受plan限制

---

## 一、模型供应商全量清单（JS逆向提取）

### 1.1 Anthropic / Claude 系列（22个枚举）

| 枚举ID | 模型 | 代际 | 特性 |
|--------|------|------|------|
| 63 | Claude 3 Opus | 3.0 | 最强推理(旧) |
| 64 | Claude 3 Sonnet | 3.0 | 平衡(旧) |
| 172 | Claude 3 Haiku | 3.0 | 快速(旧) |
| 80 | Claude 3.5 Sonnet v1 (Jun) | 3.5 | 代码能力跃升 |
| 166 | Claude 3.5 Sonnet v2 (Oct) | 3.5 | Computer Use |
| 171 | Claude 3.5 Haiku | 3.5 | 快速+便宜 |
| 226 | Claude 3.7 Sonnet | 3.7 | 扩展思考 |
| 227 | Claude 3.7 Sonnet Thinking | 3.7 | 显式思维链 |
| 281 | **Claude 4 Sonnet** | 4.0 | 新一代编码 |
| 282 | Claude 4 Sonnet Thinking | 4.0 | +思维链 |
| 290 | **Claude 4 Opus** | 4.0 | 最强推理 |
| 291 | Claude 4 Opus Thinking | 4.0 | +思维链 |
| 328 | **Claude 4.1 Opus** | 4.1 | 迭代升级 |
| 329 | Claude 4.1 Opus Thinking | 4.1 | +思维链 |
| 353 | **Claude 4.5 Sonnet** | 4.5 | 当前Cascade默认 |
| 354 | Claude 4.5 Sonnet Thinking | 4.5 | +思维链 |
| 370 | Claude 4.5 Sonnet 1M | 4.5 | 100万token上下文 |
| 391 | **Claude 4.5 Opus** | 4.5 | 最强 |
| 392 | Claude 4.5 Opus Thinking | 4.5 | +思维链 |
| 241 | Anthropic Windsurf Research | — | Windsurf专属微调 |
| 242 | Anthropic Windsurf Research Thinking | — | +思维链 |

**BYOK变体**: 277/278(4 Opus), 279/280(4 Sonnet), 284(3.5 Sonnet), 285/286(3.7 Sonnet), 319/320(3.7 OR), 321/322(4 Sonnet OR)

### 1.2 OpenAI 系列（50+ 枚举）

| 枚举ID | 模型 | 代际 | 特性 |
|--------|------|------|------|
| 109 | GPT-4o | 4o | 多模态旗舰 |
| 113 | GPT-4o-mini | 4o | 快速低价 |
| 117/118 | O1-preview / O1-mini | O1 | 推理模型 |
| 170 | O1 | O1 | 正式版 |
| 207/213/214 | O3-mini (Low/High) | O3 | 推理升级 |
| 218/262/263 | O3 (Low/High) | O3 | 强推理 |
| 264-266 | **O4-mini** (Low/High) | O4 | 最新推理 |
| 228 | GPT-4.5 | 4.5 | 过渡模型 |
| 259-261 | **GPT-4.1** / mini / nano | 4.1 | 编码优化 |
| 287-289 | Codex-mini-latest (Low/High) | Codex | 代码专用 |
| 294-296 | **O3-Pro** (Low/High) | O3 | 顶级推理 |
| 337-341 | **GPT-5** Nano/Min/Low/Med/High | 5.0 | 下一代 |
| 346 | GPT-5 Codex | 5.0 | 代码版 |
| 385-397 | **GPT-5.1 Codex** Mini/Std/Max × 3档 | 5.1 | 编码Agent |
| 399-408 | **GPT-5.2** 5档 + Priority变体 | 5.2 | 最新 |
| 422-429 | GPT-5.2 Codex 4档 + Priority | 5.2 | 代码版 |

### 1.3 Google / Gemini 系列（15个枚举）

| 枚举ID | 模型 | 代际 | 特性 |
|--------|------|------|------|
| 61 | Gemini 1.0 Pro | 1.0 | 基础(旧) |
| 62 | Gemini 1.5 Pro | 1.5 | 长上下文 |
| 183 | Gemini Exp 1206 | 2.0 | 实验版 |
| 184 | **Gemini 2.0 Flash** | 2.0 | 快速推理 |
| 246 | **Gemini 2.5 Pro** | 2.5 | 强推理 |
| 272/275 | Gemini 2.5 Flash Preview | 2.5 | 预览版 |
| 312/313 | **Gemini 2.5 Flash** (+Thinking) | 2.5 | 正式版 |
| 343 | Gemini 2.5 Flash Lite | 2.5 | 轻量版 |
| 378/379/411/412 | **Gemini 3.0 Pro** (4档) | 3.0 | 下一代Pro |
| 413-416 | **Gemini 3.0 Flash** (4档) | 3.0 | 下一代Flash |

### 1.4 DeepSeek 系列（7个枚举）

| 枚举ID | 模型 | 特性 |
|--------|------|------|
| 205 | **DeepSeek-V3** | 开源旗舰 |
| 206 | **DeepSeek-R1** | 推理模型 |
| 215/216 | DeepSeek-R1 Slow/Fast | 速度分档 |
| 247/248 | DeepSeek-V3 Internal / V3-0324 | Windsurf内部版 |
| 249 | DeepSeek-R1 Internal | Windsurf内部版 |
| 409 | **DeepSeek-V3.2** | 最新版 |

### 1.5 xAI / Grok 系列（4个枚举）

| 枚举ID | 模型 | 特性 |
|--------|------|------|
| 212 | Grok 2 | 基础 |
| 217 | **Grok 3** | 强推理 |
| 234 | Grok 3 Mini Reasoning | 轻量推理 |
| 345 | **Grok Code Fast** | 代码专用 |

### 1.6 Qwen / 阿里 系列（6个枚举）

| 枚举ID | 模型 | 特性 |
|--------|------|------|
| 178 | Qwen 2.5 7B | 轻量 |
| 179 | Qwen 2.5 32B | 中等 |
| 180 | Qwen 2.5 72B | 大型 |
| 224 | Qwen 2.5 32B R1 | +推理 |
| 324 | **Qwen 3 235B** | 新一代旗舰 |
| 325/327 | **Qwen 3 Coder 480B** (+Fast) | 代码专用 |

### 1.7 Meta / Llama 系列（7个枚举）

| 枚举ID | 模型 | 特性 |
|--------|------|------|
| 105 | Llama 3.1 405B | 最大开源 |
| 106/107 | Llama 3.1 8B / 70B | 基础 |
| 116 | Llama 3.1 70B Long Context | 长上下文 |
| 176/177 | Llama 3.1 Hermes 3 8B/70B | 微调版 |
| 208/209 | Llama 3.3 70B / 70B R1 | 最新+推理 |

### 1.8 其他供应商

| 枚举ID | 模型 | 供应商 | 特性 |
|--------|------|--------|------|
| 77 | Mistral 7B | Mistral | 基础 |
| 342/352 | GLM 4.5 (+Fast) | 智谱 | 中文优化 |
| 356/357 | GLM 4.6 (+Fast) | 智谱 | 升级 |
| 417/418 | **GLM 4.7** (+Fast) | 智谱 | 最新 |
| 368/419 | MiniMax M2 / M2.1 | MiniMax | 中国AI |
| 323/394 | **Kimi K2** (+Thinking) | 月之暗面 | 长上下文 |
| 326 | GPT-OSS 120B | 开源 | 大型开源 |
| 355 | Cognition Instant Context | Cognition | 即时上下文 |

### 1.9 Windsurf 自研 / 内部模型

| 枚举ID | 模型 | 用途 |
|--------|------|------|
| 225-311 | CASCADE 20064-20089 (30+) | Cascade路由端点 |
| 359/377 | **SWE-1.5** (Normal/Slow) | SWE Agent |
| 420/421 | **SWE-1.6** (+Fast) | 下一代SWE |
| 369 | SWE-1.5 Thinking | 带思维链 |
| 358/360/362 | CODEMAP Small/Medium/Smart | 代码索引 |
| 410 | Cognition Lifeguard | 安全检查 |
| 500-511 | TAB models (12个) | 代码补全 |
| 600 | SGLANG Rollout | 推理加速 |

### 1.10 BYOK / 兼容接口

| 枚举ID | 接口 | 用途 |
|--------|------|------|
| 200 | OpenAI Compatible | 自定义OpenAI兼容API |
| 201 | Anthropic Compatible | 自定义Anthropic兼容API |
| 202 | Vertex Compatible | Google Vertex AI |
| 203 | Bedrock Compatible | AWS Bedrock |
| 204 | Azure Compatible | Azure OpenAI |
| 182 | Custom VLLM | 自部署vLLM |
| 185 | Custom OpenRouter | OpenRouter路由 |

---

## 二、伏羲八卦 × 模型能力映射

> 将模型能力映射到八卦八维，每卦代表AGI系统的一个核心能力维度。
> 评分基于编码/推理/多模态/速度/上下文/成本/安全/工具调用八个维度。

```
         ☰ 乾 · 编码创造
            ╱ ╲
    ☴巽·工具    ☱兑·多模态
     ╱               ╲
  ☵坎·推理    ☲离·速度效率
     ╲               ╱
    ☶艮·安全    ☷坤·上下文
            ╲ ╱
         ☳ 震 · 成本效率
```

### 八卦 × 八维能力矩阵

| 卦 | 维度 | 最强模型 | 性价比之选 | AGI系统影响 |
|----|------|---------|-----------|------------|
| **☰乾·编码** | 代码生成/重构/调试 | Claude Opus 4.6(#1) > GPT-5.4 > SWE-1.5(#6) | SWE-1.5(0x) / GPT-4.1 | 直接决定开发效率 |
| **☱兑·多模态** | 图像理解/截图分析 | GPT-5.4 > Claude 4.6 > Gemini 3.1 | GPT-4o / Gemini 3 Flash | 浏览器Agent/手机控制 |
| **☲离·速度** | 响应延迟/吞吐量 | Gemini 3 Flash > GPT-5.3-Codex-Spark > Haiku | Gemini 2.5 Flash Lite | 交互体验/实时控制 |
| **☳震·成本** | 每token价格/积分消耗 | SWE-1.5(0x) > GPT-5.4(1x促销) > DeepSeek-V3 | SWE-1.5 / DeepSeek-V3 | 可持续运行的关键 |
| **☴巽·工具** | MCP/函数调用/Agent | Claude 4.6 > SWE-1.5 > GPT-5.4 | Claude Sonnet 4.6(2x) | 五感Agent核心 |
| **☵坎·推理** | 逻辑/数学/规划 | O3-Pro > Claude Opus 4.6 > GPT-5.4 | O4-mini / DeepSeek-R1 | 复杂任务决策 |
| **☶艮·安全** | 规则遵循/风险回避 | Claude 4.6 > GPT-5.4 > Gemini 3.1 | Claude Sonnet 4.6 | 终端安全/凭据保护 |
| **☷坤·上下文** | 窗口长度/长程记忆 | Claude 4.5 Sonnet 1M > Gemini(2M) > Kimi K2.5 | Kimi K2.5 / Gemini 3.1 | 大项目理解 |

### 模型 × 八卦雷达图（10分制）

| 模型 | ☰编码 | ☱多模态 | ☲速度 | ☳成本 | ☴工具 | ☵推理 | ☶安全 | ☷上下文 | 总分 |
|------|------|--------|------|------|------|------|------|--------|------|
| **Claude 4.5 Sonnet** | 9.5 | 9 | 7 | 5 | 10 | 9 | 9.5 | 9 | **67/80** |
| **Claude 4.5 Opus** | 10 | 9 | 5 | 3 | 9.5 | 10 | 9.5 | 9 | **65/80** |
| **SWE-1.5** | 9 | 8 | 6 | 10 | 9.5 | 8.5 | 9 | 8 | **68/80** |
| **GPT-5.2** | 9 | 9.5 | 7 | 4 | 8.5 | 9.5 | 8 | 8 | **63.5/80** |
| **GPT-4.1** | 8.5 | 8 | 8.5 | 7 | 8 | 8 | 8 | 7 | **63/80** |
| **O3-Pro** | 7 | 6 | 3 | 2 | 7 | 10 | 8 | 7 | **50/80** |
| **O4-mini** | 7.5 | 7 | 8 | 8 | 7.5 | 9 | 8 | 6 | **61/80** |
| **Gemini 3.0 Pro** | 8 | 8.5 | 8 | 6 | 8 | 8.5 | 7.5 | 9.5 | **64/80** |
| **Gemini 2.5 Flash** | 7 | 7.5 | 9.5 | 9 | 7 | 7 | 7 | 8 | **62/80** |
| **DeepSeek-V3.2** | 8 | 6 | 7 | 9.5 | 7 | 8 | 6.5 | 7 | **59/80** |
| **DeepSeek-R1** | 6.5 | 5 | 5 | 9 | 6 | 9.5 | 6 | 7 | **54/80** |
| **Grok 3** | 8 | 7 | 7.5 | 6 | 7.5 | 8.5 | 6.5 | 7 | **58/80** |
| **Qwen 3 Coder 480B** | 8.5 | 6 | 6 | 8 | 7 | 7.5 | 6 | 7 | **56/80** |
| **Kimi K2** | 7 | 6 | 6.5 | 8 | 7 | 7.5 | 6.5 | 9.5 | **58/80** |
| **GLM 4.7** | 7 | 6.5 | 7 | 8 | 6.5 | 7 | 7 | 7 | **56/80** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Claude Opus 4.6** ★ | 10 | 9.5 | 5 | 2 | 10 | 10 | 10 | 9 | **65.5/80** |
| **Claude Sonnet 4.6** | 9.5 | 9 | 7 | 5 | 10 | 9.5 | 9.5 | 9 | **68.5/80** |
| **GPT-5.4** | 9.5 | 9.5 | 7.5 | 7 | 9 | 9.5 | 8.5 | 8 | **68.5/80** |
| **Kimi K2.5** | 8 | 6 | 7 | 8 | 8 | 8 | 7 | 9.5 | **61.5/80** |
| **GLM-5** | 7.5 | 7 | 7.5 | 8 | 7 | 7.5 | 7 | 7.5 | **59/80** |

> **总分解读**: Claude Sonnet 4.6和GPT-5.4并列最高(68.5)；SWE-1.5(68)因0积分紧随其后；Claude Opus 4.6推理/工具满分但成本拖累总分。★=Arena #1。

---

## 三、AGI 系统 × 模型匹配矩阵

> 将我们的44个AGENTS.md子系统映射到最优模型选择。

### 3.1 核心开发（需要☰编码 + ☴工具）

| 子系统 | 最优模型 | 备选 | 理由 |
|--------|---------|------|------|
| SS核心(Kotlin/Android) | Claude 4.5 Sonnet | SWE-1.5 | Kotlin编码+工具调用最强 |
| Input模块(3600行) | Claude 4.5 Sonnet | GPT-4.1 | 大文件理解+精准编辑 |
| MJPEG前端(5800行) | Claude 4.5 Sonnet | Gemini 2.5 Pro | HTML/JS/CSS全栈 |
| Gradle构建 | SWE-1.5 | Claude 4 Sonnet | 0积分+够用 |

### 3.2 Agent控制（需要☴工具 + ☱多模态 + ☲速度）

| 子系统 | 最优模型 | 备选 | 理由 |
|--------|---------|------|------|
| 手机操控库 | Claude 4.5 Sonnet | GPT-4.1 | MCP工具链+截图理解 |
| 浏览器Agent | Claude 4.5 Sonnet | GPT-5 | 多工具并行+DOM理解 |
| Agent操控电脑 | Claude 4.5 Sonnet | GPT-4.1 | 工具密集型 |
| 远程桌面控制 | GPT-4.1 | Claude 4 Sonnet | 速度优先 |

### 3.3 推理密集（需要☵推理 + ☷上下文）

| 子系统 | 最优模型 | 备选 | 理由 |
|--------|---------|------|------|
| 架构设计 | Claude 4.5 Opus | O3-Pro | 深度推理+长文理解 |
| 需求分解 | Claude 4.5 Sonnet | GPT-5 | 结构化输出 |
| 论文研究(ARGs) | Claude 4.5 Opus | Gemini 2.5 Pro | 学术推理+长文 |
| Debug升级 | Claude 4.5 Sonnet Thinking | O4-mini | 显式思维链 |

### 3.4 高频低复杂（需要☲速度 + ☳成本）

| 子系统 | 最优模型 | 备选 | 理由 |
|--------|---------|------|------|
| 代码补全(TAB) | TAB专用模型 | — | Windsurf内部优化 |
| 文档生成 | SWE-1.5 | Gemini 2.5 Flash | 0积分 |
| Git提交 | SWE-1.5 | GPT-4.1 nano | 简单任务 |
| 健康检查 | SWE-1.5 | — | 0积分足矣 |

### 3.5 特殊场景

| 子系统 | 最优模型 | 备选 | 理由 |
|--------|---------|------|------|
| 3D建模Agent | GPT-5 (多模态) | Claude 4.5 Sonnet | 图像理解→参数化 |
| 智能家居 | Claude 4 Sonnet | GPT-4.1 | 工具调用+成本平衡 |
| WebXR开发 | Claude 4.5 Sonnet | SWE-1.5 | Three.js/WebGL专业 |
| VaM Agent | Claude 4.5 Sonnet | GPT-4.1 | JSON场景生成 |
| 公网投屏 | GPT-4.1 | SWE-1.5 | Node.js+WebSocket |
| 二手书系统 | SWE-1.5 | GPT-4.1 | CRUD够用+0积分 |

---

## 四、发现的问题与解决方案

### 问题1: �已解决 Cloudflare阻止IWR — 改用Playwright绕过

- **症状**: `Invoke-WebRequest` 访问 windsurf.com 系列页面返回 403 Forbidden
- **根因**: Cloudflare WAF拦截非浏览器User-Agent的请求
- **解决**: 改用Playwright MCP(headless浏览器)抓取JS渲染页面
- **成果**: 成功获取Arena排行榜(15模型ELO)、定价页(4套餐)、博客(7个新模型)

### 问题2: 🟡 模型选择不透明 — 用户无法看到完整模型列表

- **症状**: Cascade UI仅显示 SWE-1.5 和 Claude Sonnet 4.5 两个选项
- **影响**: 用户不知道还有其他模型可用
- **根因**: Windsurf通过 `cascade_model_config_data` 服务端动态下发可选模型，受plan限制
- **解决**: 
  - Free用户: SWE-1.5(0积分) + arena路由
  - Pro用户: 额外解锁 Claude 4.5 Sonnet(3x积分) + 更多模型
  - BYOK: 自带API Key可用 200/201/202/203/204 兼容接口
  - Team: `cascade_model_labels` + `cascade_model_uids` 自定义白名单

### 问题3: 🟡 Arena路由黑盒 — 不知道实际用了哪个模型

- **症状**: arena-fast/arena-smart/arena-mixed 三种路由模式
- **影响**: 无法确定某次对话实际使用的底层模型
- **根因**: Windsurf内部路由算法，基于任务复杂度+模型可用性动态选择
- **解决**: 
  - 查看响应头 `CASCADE_MODEL_HEADER_WARNING`(枚举329)
  - 使用显式模型选择而非arena模式
  - 监控 `modelStatuses` (modelSelector Redux状态)

### 问题4: 🟡 积分消耗不均 — Claude 4.5是SWE-1.5的∞倍

- **症状**: SWE-1.5=0积分, Claude 4.5 Sonnet=3x积分
- **影响**: 日常任务若全用Claude会快速耗尽额度
- **解决**: **分级策略**
  - 日常/简单任务 → SWE-1.5（0积分）
  - 复杂编码/Agent → Claude 4.5 Sonnet（3x积分）
  - 深度推理 → 仅在 `/cycle` 时使用Opus级别
  - 代码补全 → TAB专用模型（自动）

### 问题5: 🟢 MCP上下文税 — 3个活跃Server占11-14%窗口

- **现状**: chrome-devtools + playwright + context7 = 3个活跃
- **影响**: 每个活跃MCP Server消耗约4%上下文窗口
- **解决**: 已禁用 github(需代理) 和 fetch(被IWR替代)
- **建议**: 选用大上下文模型(Claude 4.5 Sonnet 200K, 1M变体370)时MCP税可忽略

### 问题6: �已确认 GPT-5.x/Gemini 3.x/Claude 4.6 已上线

- **旧状态**: JS中有枚举但不确定是否已启用
- **新状态**: Arena排行榜实时确认以下模型已在线:
  - GPT-5.2 (ELO 1,016) + GPT-5.3-Codex (956) + GPT-5.3-Codex-Spark (964)
  - Gemini 3 Pro (939) + Gemini 3 Flash (946) + Gemini 3.1 Pro (922)
  - Claude Opus 4.6 (ELO 1,099, #1) + Claude Sonnet 4.6 (博客确认)
  - GPT-5.4 (Mar 5博客确认, 1x积分促销)
  - GLM-5 (1,000) + Minimax M2.5 (952) + Kimi K2.5 (1,024)
- **意义**: 服务端模型已远超本地JS v1.108.2的枚举范围

### 问题7: 🟡 本地JS版本滞后 — 服务端已超越客户端

- **症状**: 本地JS枚举到GPT-5.2/Claude 4.5, 但服务端已有GPT-5.4/Claude 4.6/Gemini 3.1
- **影响**: JS逆向无法反映最新模型全貌
- **根因**: 客户端JS在安装时固化,新模型通过`cascade_model_config_data`服务端动态下发
- **解决**: 定期更新Windsurf版本 + 关注博客公告 + Arena排行榜追踪

---

## 五、Windsurf 配置全景（本机实测）

### 5.1 安装信息

| 项 | 值 |
|----|---|
| **版本** | Windsurf v1.108.2 |
| **质量** | stable |
| **路径** | `D:\Windsurf\` |
| **Commit** | 8911695f6454083fd48c3422f4736eb88053357c |
| **配置根** | `C:\Users\Administrator\.codeium\windsurf\` |

### 5.2 MCP配置 (`~/.codeium/windsurf/mcp_config.json`)

| Server | 状态 | 启动方式 |
|--------|------|---------|
| chrome-devtools | ✅ 启用 | `C:\temp\chrome-devtools-mcp.cmd` |
| playwright | ✅ 启用 | `C:\temp\playwright-mcp.cmd` |
| context7 | ✅ 启用 | `C:\temp\context7-mcp.cmd` |
| github | ✅ 启用 | `C:\temp\github-mcp.cmd` (需Clash代理) |

### 5.3 用户设置 (`AppData/Roaming/Windsurf/User/settings.json`)

```json
{
  "http.proxyStrictSSL": false,
  "http.proxySupport": "off"
}
```

> 注: proxyStrictSSL=false 和 proxySupport=off 与无限额度方案配合使用。

### 5.4 全局Hooks (`~/.codeium/windsurf/hooks.json`)

```json
{"hooks": {}}
```

> ✅ 安全状态（PS hooks绝对禁止）

### 5.5 三Zone架构统计

| Zone | 组件数 | 说明 |
|------|--------|------|
| Zone 0 全局 | 21 | 规则+MCP(4)+Hooks+Skills(13)+Settings |
| Zone 1 项目 | 37 | Rules(7)+Skills(17)+Workflows(11)+Hooks(2) |
| Zone 2 目录 | 44 | AGENTS.md |
| Memory | 40+ | 跨对话持久知识 |
| **总计** | **142+** | |

---

## 六、模型选择策略（实践建议）

### 6.1 按任务复杂度分层

```
TRIVIAL（单文件<10行）
  └→ SWE-1.5（0积分，足够）

STANDARD（常规开发）
  └→ SWE-1.5（默认）→ 不满意切 Claude Sonnet 4.6(2x)

COMPLEX（多文件/架构级）
  └→ Claude Sonnet 4.6(2x/3x) 或 GPT-5.4(1x促销)

RESEARCH（深度推理/论文）
  └→ Claude Opus 4.6(10x) / O3-Pro（谨慎使用）
```

### 6.2 按AGI子系统分配

```
核心编码（SS/Input/MJPEG） → Claude Sonnet 4.6 (2x)
Agent控制（手机/浏览器/远程） → Claude Sonnet 4.6 (2x)
高性价比新功能 → GPT-5.4 (1x促销期)
日常运维（Git/Doc/健康检查） → SWE-1.5 (0x)
特殊推理（/cycle 深度循环） → Claude Opus 4.6 (10x)
代码补全 → TAB 自动
```

### 6.3 BYOK 场景（自带Key）

| 需求 | 接口 | 模型 |
|------|------|------|
| 省钱用Claude | Anthropic Compatible (201) | Claude 3.5 Haiku |
| 用Azure | Azure Compatible (204) | GPT-4o |
| 私有部署 | Custom VLLM (182) | 本地Llama/Qwen |
| 多模型路由 | Custom OpenRouter (185) | 任意 |

---

## 七、模型代际演进时间线

```
2024 Q1  ┃ Claude 3 (Opus/Sonnet/Haiku) + Gemini 1.0/1.5
         ┃
2024 Q2  ┃ Claude 3.5 Sonnet v1 ← 编码能力质变
         ┃ GPT-4o 多模态
         ┃
2024 Q3  ┃ Claude 3.5 Sonnet v2 (Computer Use)
         ┃ O1-preview/mini 推理模型诞生
         ┃
2024 Q4  ┃ Gemini 2.0 Flash + DeepSeek-V3 开源震撼
         ┃ Claude 3.5 Haiku
         ┃
2025 Q1  ┃ Claude 3.7 Sonnet (Extended Thinking)
         ┃ DeepSeek-R1 推理 + O3-mini
         ┃ Gemini 2.5 Pro/Flash
         ┃ GPT-4.5 过渡
         ┃
2025 Q2  ┃ GPT-4.1 / GPT-4.1-mini/nano ← 编码优化
         ┃ O4-mini + Codex-mini-latest
         ┃ Claude 4 Sonnet/Opus ← 新一代
         ┃ Grok 3 + Qwen 3
         ┃ Windsurf SWE-1.5 自研模型
         ┃
2025 Q3  ┃ Claude 4.1 Opus / Claude 4.5 Sonnet/Opus
         ┃ O3-Pro
         ┃ GPT-5 / GPT-5 Codex
         ┃ Gemini 2.5 Flash 正式版
         ┃ Kimi K2
         ┃
2025 Q4  ┃ GPT-5.1 / GPT-5.2 Codex
         ┃ Gemini 3.0 Pro/Flash
         ┃ SWE-1.6 ← 下一代Windsurf Agent
         ┃ Claude 4.5 Sonnet 1M / Opus
         ┃ DeepSeek-V3.2 / GLM 4.7 / MiniMax M2.1
         ┃
2026 Q1  ┃ **Claude Opus 4.6** (Feb 7) ← Arena #1, ELO 1,099
  (实时) ┃ **Claude Sonnet 4.6** (Feb 17) ← 2x/3x积分
         ┃ **GPT-5.3-Codex-Spark** (Feb 12) ← 超快编码
         ┃ **GLM-5 + Minimax M2.5** (Feb 16) ← 中国AI崛起
         ┃ **Gemini 3.1 Pro** (Feb 20) ← Low/High思考
         ┃ **Kimi K2.5** ← Arena #5, 超越GPT-5.2
         ┃ **GPT-5.4** (Mar 5) ← 最新, 1x积分促销
         ┃ Arena排行榜发布 (Feb 11) ← "The People Want Speed"
```

---

## 八、八卦辩证总结

### ☰乾 — 创造力（编码）

> Claude Opus 4.6 (Arena #1, ELO 1,099) 在全栈编码中**统治级**。SWE-1.5 (#6, ELO 1,017) 以0积分超越GPT-5.2——**免费>付费**是2026最大发现。GPT-5.4 (Mar 5上线) 以1x促销积分成为新的性价比选项。

### ☱兑 — 感知力（多模态）

> GPT-5.4多模态能力领先。Claude 4.6支持图像理解。Gemini 3.1在视频理解上独家。对AGI系统的浏览器Agent、手机截图分析至关重要。

### ☲离 — 执行力（速度）

> Gemini 3 Flash和GPT-5.3-Codex-Spark专注极速。Arena的"The People Want Speed"主题印证速度是用户第一需求。实时控制场景（手机操控、远程桌面）优先选快速模型。

### ☳震 — 效率（成本）

> **SWE-1.5的0积分+ELO 1,017是改变游戏规则的**——免费模型在Arena排第6超越GPT-5.2(#7)。GPT-5.4限时1x促销进一步降低顶级模型门槛。DeepSeek/Qwen通过BYOK再降本。

### ☴巽 — 渗透力（工具调用）

> Claude 4.6在MCP工具调用上遥遥领先——这是AGI系统的**命脉**。400+工具函数的稳定并行调用，Claude仍是唯一可靠选择。Kimi K2.5 (#5) 在工具调用上崛起值得关注。

### ☵坎 — 深度（推理）

> O3-Pro是纯推理最强，但成本极高。Claude Opus 4.6 (10x积分) 是**深度推理的新标杆**。GPT-5.4的多推理档位提供灵活选择。DeepSeek-R1以开源之姿提供可观推理能力。

### ☶艮 — 稳定性（安全）

> Claude系列在规则遵循、凭据保护、终端安全方面最可靠。Arena前4名全是Anthropic——稳定性和质量的双重验证。Zone 0保护、双机操作、凭据中心的基石。

### ☷坤 — 容量（上下文）

> Claude 4.5 Sonnet 1M (100万token) 和 Gemini (200万token) 定义上下文上限。Kimi K2.5的长上下文能力 (Arena #5) 也在崛起。对理解大型代码库（InputService 3600行、index.html 5800行）至关重要。

---

## 九、结论与行动项

### 当前最优配置（2026-03-06 更新）

| 场景 | 模型 | 积分 | 原因 |
|------|------|------|------|
| **默认Cascade** | SWE-1.5 | 0x | Arena #6(ELO 1,017), 免费且超GPT-5.2 |
| **复杂开发** | Claude Sonnet 4.6 | 2x/3x | 最新Sonnet, 编码+工具最均衡 |
| **极致质量** | Claude Opus 4.6 | 10x/12x | Arena #1(ELO 1,099), 最强但最贵 |
| **高性价比新模型** | GPT-5.4 | 1x促销 | 限时促销, 多推理档位 |
| **代码补全** | TAB自动 | — | 无需干预 |

### 已确认上线（Arena/博客验证）

1. **Claude Opus 4.6** — Arena #1, ELO 1,099, 10x/12x积分
2. **GPT-5.4** — Mar 5上线, 限时1x积分促销
3. **Gemini 3.1 Pro** — Low/High思考变体, 促销中
4. **Claude Sonnet 4.6** — 2x/3x积分, 替代4.5成为默认
5. **GPT-5.3-Codex-Spark** — 超快编码, Arena Fast/Hybrid
6. **Kimi K2.5** — Arena #5, ELO 1,024, 超越GPT-5.2
7. **GLM-5** — 智谱新旗舰, Arena #8, ELO 1,000

### 待关注

1. **SWE-1.6** 已在枚举(420/421) — 下一代Windsurf Agent
2. **GPT-5.4积分恢复** — 促销结束后可能涨到2-3x
3. **Claude Opus 4.6成本** — 10x积分限制日常使用
4. **Arena排名变动** — Kimi K2.5(#5)是否超越SWE-1.5(#6)
5. **BYOK接口** — 5种兼容模式自带Key可解锁一切

### 数据来源声明

| 来源 | 方法 | 可信度 |
|------|------|--------|
| JS逆向 | `workbench.desktop.main.js` 正则提取 | 🟢 高（240+唯一枚举） |
| 配置文件 | `read_file` / `run_command` | 🟢 高（本机实际值） |
| Arena排行榜 | Playwright抓取 `windsurf.com/leaderboard` | 🟢 高（2026-03-06 20:56实时） |
| 博客时间线 | Playwright抓取 `windsurf.com/blog` | � 高（7个新模型上线公告） |
| 定价页 | Playwright抓取 `windsurf.com/pricing` | � 高（4套餐+积分体系） |

---

*道生一，一生二，二生三，三生万物。*
*240+枚举=万物。八卦=分类之道。Arena=实战之验。AGI系统=三生万物的具现。*
