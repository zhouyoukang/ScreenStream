---
name: requirement-decompose
description: 将用户的顶层需求自动分解为可执行的特性列表。当用户给出一句话需求时自动触发，输出结构化的实现计划。
---

## 核心流程：一句话需求 → 结构化特性列表

### Step 1: 意图解析

从用户输入中提取：
- **动词**：添加/修改/删除/优化/修复
- **对象**：什么功能/哪个模块
- **约束**：性能/安全/兼容性要求

### Step 2: 影响分析

根据 code-index.md 判断：
| 影响范围 | 需要修改的文件 |
|---------|--------------|
| 仅后端 | InputService.kt + InputRoutes.kt |
| 仅前端 | index.html |
| 前后端 | InputService.kt + InputRoutes.kt + index.html |
| 新面板 | index.html (panel) + 可能需要新后端API |
| 系统级 | AndroidManifest + 可能需要新权限 |

### Step 3: 特性分解

将需求拆分为独立可测试的特性：

`json
{
  "requirement": "用户原始需求",
  "features": [
    {
      "id": "F1",
      "description": "具体特性描述",
      "type": "BACKEND|FRONTEND|FULLSTACK",
      "files": ["file1.kt", "file2.html"],
      "insertPoints": {"InputService.kt": "line~1610", "InputRoutes.kt": "line~418"},
      "pattern": "Recipe 1/2/3 from quick-recipes.md",
      "complexity": "S(1-5行)|M(5-20行)|L(20+行)",
      "dependencies": [],
      "testMethod": "curl POST /endpoint | browser click",
      "passes": false
    }
  ],
  "totalComplexity": "TRIVIAL|SMALL|MEDIUM|LARGE",
  "estimatedFiles": 3,
  "skipResearch": true/false
}
`

### Step 4: 执行策略选择

| 总复杂度 | 策略 |
|---------|------|
| TRIVIAL (1-2个S特性) | 直接实现，不研究不确认 |
| SMALL (2-3个S/M特性) | 用quick-recipes模板，不研究 |
| MEDIUM (含L特性或4+文件) | 先读code-index定位，内部模式匹配 |
| LARGE (新模块/架构变更) | 完整研究+外部搜索+用户确认 |

### Step 5: 输出

向用户展示（仅MEDIUM+以上）：
`
## 需求分解：<原始需求>
- F1: <描述> (S, InputService+Routes)
- F2: <描述> (M, index.html)
- F3: <描述> (S, FEATURES.md)
预计修改 3 个文件，复杂度 MEDIUM
`

TRIVIAL/SMALL 不展示，直接执行。

## ScreenStream 常见需求模式速查

| 用户说 | 实际意味着 | 模式 |
|-------|----------|------|
| "加个XX按钮" | 新API + 前端按钮 | Recipe 1 + menu item |
| "加个XX面板" | 新平台面板 | Recipe 2 (S34模式) |
| "支持XX控制" | 新设备控制开关 | Recipe 3 (toggle) |
| "批量加几个功能" | 多个小特性 | Recipe 4 (batch) |
| "优化XX" | 修改现有代码 | 读code-index找到位置，局部修改 |
| "修复XX" | Bug fix | grep_search定位，最小修改 |
| "文件管理加XX" | S33扩展 | 在文件管理区段(4074-4640)扩展 |
| "宏系统加XX" | MacroEngine扩展 | MacroEngine.kt + 宏路由区段 |
