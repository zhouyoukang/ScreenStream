---
description: 按文本/描述语义查找UI元素并点击。当需要在屏幕上找到特定按钮、链接、菜单项并点击时触发。
---

# 语义查找并点击

## 触发条件
- 需要点击屏幕上包含特定文字的元素
- 需要点击图标按钮（通过 contentDescription 匹配）
- 需要点击特定 resource ID 的元素

## 前置：确认已 observe
执行前必须有最近 3 秒内的屏幕感知结果。如果没有：
```
GET /screen/text
```

## 执行步骤

### Step 1: 尝试文本精确匹配
```
POST /findclick {"text": "<目标文字>"}
```
成功（ok=true）→ 跳到 Step 5 验证

### Step 2: 文本找不到 → 尝试节点搜索
```
POST /findnodes {"text": "<目标文字>"}
```
- 如果返回节点（count > 0）但 click=false → 元素存在但不可点击
  - 读取节点的 bounds → 计算中心坐标 → `POST /tap {"nx": centerX/screenWidth, "ny": centerY/screenHeight}`
- 如果返回 count=0 → 元素不在当前屏幕，跳到 Step 3

### Step 3: 当前屏幕找不到 → 尝试滚动查找
```
记录当前屏幕文本快照
POST /scroll {"nx":0.5, "ny":0.5, "direction":"down", "duration":600}
等待 500ms
GET /screen/text
对比新旧屏幕
```
- 屏幕有变化 → 重新执行 Step 1（最多滚动 3 次）
- 屏幕无变化 = 已到底 → 尝试向上滚动（最多 2 次）
- 上下都找不到 → Step 4

### Step 4: 全部失败 → 降级到模糊匹配
```
GET /screen/text
```
遍历返回的所有 text 元素，找包含目标文字子串的：
- 完全匹配 > 包含匹配 > 前缀匹配
- 找到最佳匹配 → `POST /findclick {"text": "<匹配到的完整文字>"}`
- 仍然失败 → 返回失败，附带当前屏幕摘要

### Step 5: 验证
```
等待 500ms
GET /screen/text
```
对比操作前后：
- 包名变化 = 页面跳转，操作成功
- 文本内容明显变化 = UI 响应，操作成功
- 无变化 = 可能点击未生效，考虑重试或换策略

## 经验记录

每次执行记录：
```
{设备型号, APP包名, 目标文字, 成功策略(1-4), 耗时ms}
```

同一 APP 同一元素连续 3 次都需要降级到 Strategy 2+ → 写入 Memory 作为 APP 特性。

## 常见陷阱

- Toast 提示文字也会出现在 View 树中，但不可点击且很快消失
- 列表中的文字可能有多个匹配项，优先点击 clickable=true 的
- 某些 OEM 的系统设置页面，文字节点和可点击容器分离（需要向上冒泡到 parent）
