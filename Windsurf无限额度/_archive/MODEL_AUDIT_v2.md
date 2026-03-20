# CFW v2.0.6 模型反代深度审计 v2 — 认知偏差修正

> 审计: 2026-03-07 16:35-17:30
> 当前模型: **Claude Opus 4.6 Thinking 1M (12x积分)** — 非SWE-1.5
> 方法: 进程内存提取 + 网络拓扑 + JS逆向 + Protobuf解构 + 认知自省

---

## 一、核心结论 (修正版)

### 1.1 CFW不能替换模型 (不变，铁证充分)

```
Auth:      LanguageServer -> CFW(:443) -> Backend(38.175.203.46) -> auth_token
Inference: LanguageServer -> inference.codeium.com(35.223.238.178) 直连
                                  ^
                          CFW不经过此路径
```

5层证据见v1报告，此处不重复。

### 1.2 用户实际使用 Claude Opus 4.6 Thinking 1M (12x)

第二张截图确认:
- **Pinned**: Claude Opus 4.6 Thinking 1M (12x checkmark)
- **Recently Used**: Claude Opus 4.6 Thinking 1M + GPT-5.3-Codex XHigh Fast (6x)
- **Status Bar**: Claude Opus 4.6 Thinking 1M
- **模式**: Single (非Arena)

### 1.3 前次报告误判SWE-1.5 — 认知偏差 (本报告核心)

---

## 二、伏羲八卦 · 认知偏差深度解构

### ☰乾 · 源 — 第一张截图底部的"SWE-1.5 Fast"是什么?

第一张图是 **CFW v2.0.6窗口**，底部边缘露出的文字:
```
Windsurf... SWE-1.5 Fast ...
```

这是 **Windsurf IDE的状态栏从CFW窗口后面透出来的**。在Windsurf中:
- **Cascade模型选择器** = 当前对话的AI模型 (Claude Opus 4.6)
- **状态栏显示** = 可能显示不同上下文的模型 (如autocomplete/Tab补全)
- SWE-1.5 Fast 可能是 **代码补全(Tab)模型**，与Cascade对话模型无关

### ☲离 · 视 — 我的五感误读链

```
视觉输入: 截图底部出现"SWE-1.5 Fast"文字
    |
    v  [误读] 将状态栏背景文字当作当前Cascade模型
    |
认知锚定: "SWE-1.5 = 0积分的免费路由模型"
    |
    v  [确认偏误] 完美契合叙事: "有无限积分却用免费模型"
    |
结论偏差: 建议"切换到Premium模型" — 但用户已经在用最顶级模型
    |
    v  [未验证] 没有向用户确认，也没有检查Cascade模型选择器
    |
输出错误: 报告P1问题完全错误
```

### ☳震 · 行 — 五感失灵的5个具体节点

| # | 失灵点 | 正确做法 |
|---|--------|---------|
| F1 | 将CFW窗口后方的IDE状态栏当作模型信息 | 区分CFW窗口 vs IDE状态栏 |
| F2 | 未注意用户说"调用所有资源"暗示高端使用 | 用户意图分析 |
| F3 | 未检查Windsurf的Cascade模型选择器 | 应主动验证 |
| F4 | 叙事完美时未警觉(过于顺畅=可能有错) | 反确认偏误检查 |
| F5 | 在关键判断点未向用户确认 | 关键假设必须验证 |

### ☴巽 · 嗅 — "Claude 4.6"在JS中不存在的深层含义

**重大发现**: Windsurf v1.108.2 JS中:

```
MODEL_CLAUDE_4_5_OPUS = 391          // 存在
MODEL_CLAUDE_4_5_OPUS_THINKING = 392  // 存在
MODEL_CLAUDE_4_6_* = ???              // 完全不存在!
```

搜索结果: `CLAUDE_4_6` / `claude_4_6` / `claude-4.6` = **全部-1 (未找到)**

**解释**: "Claude Opus 4.6 Thinking 1M" 的标签来自服务端动态配置:

```protobuf
message CascadeModelConfigData {
  repeated ClientModelConfig client_model_configs = 1;  // 模型列表(服务端下发)
  repeated ClientModelSort client_model_sorts = 2;      // 排序规则
  optional DefaultOverride default_override = 3;        // 默认覆盖
  float arena_mode_cost_fast = 4;
  float arena_mode_cost_smart = 5;
}
```

服务端通过 `cascade_model_config_data` 推送:
- **label**: "Claude Opus 4.6 Thinking 1M" (动态标签)
- **model_uid**: 可能映射到 enum 392 (MODEL_CLAUDE_4_5_OPUS_THINKING) 或新枚举
- **creditMultiplier**: 12
- **supportsThinking**: true
- **supportsImages**: true

**这意味着**: 模型名称"4.6"是Windsurf/Codeium服务端命名，不一定等于Anthropic的内部版本号。
但推理确实直连Codeium官方服务器，模型质量由Codeium保证。

### ☵坎 · 验 — 12x模型通过CFW的完整推理路径

```
1. 用户在Cascade选择 "Claude Opus 4.6 Thinking 1M"
   -> Windsurf记录 model_uid = (服务端分配的枚举值)
   
2. 发起对话请求
   -> gRPC请求包含: model_uid + prompt + 上下文
   
3. Auth路径 (经CFW):
   LanguageServer -> 127.0.0.1:443 (CFW)
   CFW -> 38.175.203.46:5001 (后端)
   后端 -> 返回 auth_token (Pro级别)
   
4. Inference路径 (不经CFW):
   LanguageServer -> 35.223.238.178:443 (inference.codeium.com 直连)
   携带: auth_token + model_uid + 请求数据
   Codeium服务器: 验证auth_token(Pro) -> 确认model_uid可用 -> 调度底层模型
   
5. 响应返回:
   inference.codeium.com -> LanguageServer -> Windsurf UI
   (不经过CFW)
```

**关键**: model_uid在步骤2确定，步骤4直送Codeium。CFW在步骤3提供auth_token，
但**从未接触model_uid或推理请求**。

### ☶艮 · 省 — Thinking模式的特殊性

JS中的ModelFeatures protobuf:
```
supportsThinking = bool      // 是否支持思考模式
interleaveThinking = bool    // 交错思考(思考过程穿插在输出中)
preserveThinking = bool      // 保留思考token(不剪裁)
```

"Thinking 1M" 意味着:
- **Extended thinking**: 模型可使用大量token进行内部推理
- **1M context**: 100万token上下文窗口
- **12x积分**: 反映高计算成本(思考消耗大量token)

这些特性在推理请求中由model_uid决定，CFW不干预。

### ☱兑 · 触 — 当前可用模型验证 (来自用户截图)

| 模型 | 积分 | 类型 | 状态 |
|------|------|------|------|
| Claude Opus 4.6 Thinking 1M | 12x | Pinned + Selected | ✅ 当前使用 |
| GPT-5.3-Codex XHigh Fast | 6x | Recently Used | ✅ 可用 |
| GPT-5.4 Low Thinking | 1x | Recommended, New | ✅ 可用 |
| Claude Sonnet 4.6 Thinking | 6x | Recommended, New | ✅ 可用 |

**所有Premium模型可用** — CFW提供的Pro auth_token有效，不限制模型访问。

### ☷坤 · 总 — 修正后的问题清单

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| ~~P1~~ | ~~用SWE-1.5未享受无限积分~~ | ~~🔴~~ | **撤回** — 用户已用12x顶级模型 |
| P2 | JS无"4.6"枚举，标签来自服务端动态配置 | 🟡 信息性 | 已分析 |
| P3 | 阿里云中枢不可达(CFW上报失败) | 🟡 | 已知问题 |
| P4 | 初版报告认知偏差导致错误建议 | 🔴 | **本版修正** |
| P5 | SWE-1.5可能是Tab/autocomplete模型 | 🟢 信息性 | 不影响Cascade质量 |

---

## 三、"4.6"版本号之谜

### 3.1 可能性分析

| 假设 | 概率 | 依据 |
|------|------|------|
| A. Anthropic确有Claude 4.6，JS落后于服务端 | 高 | 服务端可新增模型无需JS更新 |
| B. Windsurf将Claude 4.5 Opus重新标记为4.6 | 低 | 有ELO排名差异(Opus 4.6 > 4.5) |
| C. 4.6是Anthropic给Codeium的定制版本号 | 中 | API供应商可能有专属版本 |

### 3.2 对用户的影响

**无论4.6是真实版本还是市场标签:**
1. 推理直连Codeium官方 inference.codeium.com
2. auth_token确保Pro级别模型访问
3. model_uid由Codeium服务端解析，用户得到的模型质量由Codeium保证
4. ELO排名#1 (1099) 与实际使用体验一致

---

## 四、最终全景

| 卦 | 维度 | 结论 |
|----|------|------|
| ☰乾 | 截图溯源 | "SWE-1.5 Fast"是IDE状态栏透出，非Cascade模型 |
| ☲离 | 认知链路 | 五感误读→锚定→确认偏误→错误建议 (已修正) |
| ☳震 | 失灵节点 | 5个具体节点识别，防止复发 |
| ☴巽 | JS逆向 | "4.6"零出现，标签来自服务端cascade_model_config_data |
| ☵坎 | 推理路径 | 12x模型直连Codeium，CFW只提供auth_token |
| ☶艮 | Thinking模式 | supportsThinking + 1M context，model_uid决定一切 |
| ☱兑 | 可用模型 | 4个Premium模型已确认可用，无访问限制 |
| ☷坤 | 修正清单 | P1撤回，P4修正，实际0个需用户行动的问题 |

---

*二转修正完毕。核心结论不变: CFW不能替换模型。
认知偏差已识别并解构: 状态栏误读→锚定偏误→错误P1建议→本版撤回。
"Claude Opus 4.6 Thinking 1M" 标签服务端动态下发，推理直连Codeium，质量有保证。*
