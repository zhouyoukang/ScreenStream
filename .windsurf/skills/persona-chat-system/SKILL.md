# 人格对话系统 (Persona Chat System)

> **核心理念**：概率加权场景回复+记忆搜索增强，低成本实现人格一致性

## 触发条件
- 需要构建具有特定人格的对话AI
- 要求对话风格一致性和可预测性
- 需要结合历史记忆的上下文感知对话
- 关键词：人格对话、AI角色扮演、记忆搜索、场景回复

## 系统架构

### 三层架构
```
用户输入 → 记忆搜索 → 场景匹配 → 概率回复 → 人格过滤 → 输出
```

1. **记忆层**：历史对话数据嵌入+实时搜索
2. **场景层**：关键词匹配+概率权重分发
3. **人格层**：风格统一+禁忌词过滤

## 核心组件

### 1. 记忆搜索引擎
```javascript
// 中文优化的字符匹配算法
const STOP_WORDS = new Set("的了是在我你他她吗呢啊嗯哦吧呀和就都也不有这那个到说会要去看".split(""));

function searchMemories(query, limit = 5) {
  if (!MEMORIES.length || !query) return [];
  const qChars = new Set([...query].filter(c => !STOP_WORDS.has(c) && c.trim()));
  if (!qChars.size) return [];
  
  const scored = [];
  for (const m of MEMORIES) {
    const mChars = new Set([...m.text].filter(c => !STOP_WORDS.has(c) && c.trim()));
    let overlap = 0;
    for (const c of qChars) { if (mChars.has(c)) overlap++ }
    if (overlap > 0) scored.push({ score: overlap / qChars.size, memory: m });
  }
  
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, limit).map(s => s.memory);
}
```

**优化要点**：
- 字符级匹配适配中文语言特性
- 停用词过滤提升搜索精度
- 重叠度评分算法简单高效
- 内存友好的实时搜索

### 2. 场景概率回复系统
```javascript
// 概率权重选择器
function pick(choices) {
  let total = 0;
  choices.forEach(c => total += c[0]);
  let rand = Math.floor(Math.random() * total) + 1;
  let acc = 0;
  for (const [weight, value] of choices) {
    acc += weight;
    if (rand <= acc) return value;
  }
  return choices[choices.length - 1][1];
}

// 场景定义模板
const SCENES = [
  [["关键词1", "关键词2"], [[权重1, "回复1"], [权重2, "回复2"]]],
  [["在吗", "你好"], [[70, "在呢"], [15, "干嘛"], [10, "嗯"], [5, "怎么了"]]],
  // ... 更多场景
];

function getSceneReply(message) {
  for (const [keywords, choices] of SCENES) {
    if (keywords.some(k => message.includes(k))) {
      return pick(choices);
    }
  }
  return pick(DEFAULT_REPLIES);
}
```

**设计原则**：
- 场景覆盖日常对话全生命周期
- 权重控制回复频次和语气
- 降级兼容保证系统鲁棒性
- 易于扩展新场景和回复

### 3. 人格定义系统
```javascript
const PERSONA_TEMPLATE = `你现在完全扮演{角色名}，{基本信息}。

性格特征：
- {特征1}({百分比}%)
- {特征2}({百分比}%)

说话风格：
- 字数控制：{范围}字
- 语气特点：{描述}
- 表情习惯：{emoji使用规则}

情感态度：
- {核心态度}
- {边界设定}

严格禁止：
❌ {禁忌1}
❌ {禁忌2}
❌ {超出人设行为}`;
```

## 实现流程

### Phase 1: 数据准备
1. **记忆数据清洗**
   - 提取有效对话内容
   - 统一时间格式
   - 去除无效信息

2. **场景分析**
   - 统计高频关键词
   - 分析回复模式
   - 确定概率权重

3. **人格建模**
   - 总结说话特征
   - 提取情感态度
   - 定义行为边界

### Phase 2: 系统集成
```javascript
async function getChatReply(message) {
  // 1. 搜索相关记忆
  const memories = searchMemories(message);
  
  // 2. 构建上下文
  let context = "";
  if (memories.length) {
    context = memories.map(m => `[${m.time}] ${m.sender}: ${m.text}`).join('\n');
  }
  
  // 3. 选择回复模式
  if (hasLLMAPI()) {
    // LLM增强模式
    return await getLLMReply(message, context, PERSONA);
  } else {
    // 本地场景模式
    return getSceneReply(message);
  }
}
```

### Phase 3: 质量优化
- **A/B测试**：多版本人格参数对比
- **一致性检查**：回复风格统计分析
- **用户反馈**：互动质量评估
- **持续迭代**：场景和权重调优

## 五感体验设计

### 认知层面
- **可预测性**：用户能推测AI回复倾向
- **惊喜感**：概率机制带来的自然变化
- **连续性**：基于记忆的上下文关联
- **真实感**：符合人物设定的行为逻辑

### 情感层面
- **温度控制**：通过权重调节亲密度
- **边界感**：明确的禁忌和限制
- **成长感**：记忆积累带来的熟悉度增加
- **独特性**：区别于通用AI的个性化体验

## 配置模板

### 基础配置
```json
{
  "persona": {
    "name": "角色名",
    "age": 年龄,
    "personality": ["特征1", "特征2"],
    "speech_style": {
      "length": [最小字数, 最大字数],
      "tone": "语气描述",
      "emoji_usage": "使用规则"
    }
  },
  "scenes": {
    "greeting": {
      "keywords": ["你好", "在吗"],
      "replies": [[权重, "回复内容"]]
    }
  },
  "memory": {
    "search_limit": 5,
    "min_overlap": 1
  }
}
```

### 高级配置
- **时间感知**：根据时段调整回复
- **情绪状态**：多状态人格切换
- **学习机制**：用户偏好自适应
- **群体人格**：多角色协作对话

## 部署选项

### 轻量级部署
- 纯前端JavaScript实现
- 数据直接嵌入代码
- 无服务器依赖
- 适合：小规模个人项目

### 完整版部署
- 后端API服务
- 数据库存储记忆
- LLM接口集成
- 适合：生产级应用

## 成功案例

### AI初恋 - 洪韵琪人格
- **记忆规模**：1400条真实对话
- **场景覆盖**：22种日常情况
- **人格特征**：高三女生，外向开朗，有主见
- **成功指标**：用户沉浸感强，人格识别度高

## 最佳实践

1. **数据驱动**：基于真实对话构建，而非想象
2. **概率平衡**：避免过度重复，保持自然变化
3. **边界清晰**：明确角色能做和不能做的事
4. **迭代优化**：持续收集反馈调整参数
5. **降级优雅**：确保在各种环境下都能工作

## 扩展方向

- **多模态对话**：语音、图像理解集成
- **情感计算**：基于情绪状态的动态调整  
- **社交网络**：多人格协作和互动
- **学习进化**：基于用户交互的人格成长
