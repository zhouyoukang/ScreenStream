# Phone Agent 技能体系设计

> 技能按抽象层级组织。上层技能调用下层技能，形成可组合的能力栈。
> 部署位置：Agent 项目的 `.windsurf/skills/`

## 层级架构

```
Level 4: 任务技能（Goal-oriented）
  "发微信消息给张三"  "打开高德导航到公司"  "截屏发给我"
  ↓ 调用
Level 3: APP 操作技能（App-specific）
  open_wechat_chat()  navigate_settings()  toggle_wifi()
  ↓ 调用
Level 2: 语义操作技能（Semantic）
  find_and_click(text)  scroll_to_find(text)  wait_for(text)
  ↓ 调用
Level 1: 原子操作技能（Atomic）
  tap(x,y)  swipe(dir)  input_text(t)  press_key(k)  global_action(a)
  ↓ 调用
Level 0: API 接口（HTTP）
  POST /tap  POST /swipe  POST /text  POST /key  POST /home ...
```

## Level 0: API 接口（不是技能，是基础设施）

这一层不需要 Skill 文件。这是 ScreenStream 提供的 40+ REST 端点。
Agent 直接通过 HTTP 调用。

### 感知类
- `GET /screen/text` — 屏幕文本+可点击元素
- `GET /viewtree?depth=N` — View 树结构
- `GET /windowinfo` — 当前窗口信息
- `GET /foreground` — 前台 APP
- `GET /deviceinfo` — 设备信息
- `GET /notifications/read` — 通知列表

### 操作类
- `POST /tap` — 归一化点击
- `POST /swipe` — 归一化滑动
- `POST /text` — 文本输入
- `POST /key` — 按键事件
- `POST /findclick` — 语义查找并点击
- `POST /dismiss` — 关闭弹窗
- `POST /settext` — 设置输入框文本
- `POST /intent` — 发送 Intent
- `POST /command` — 自然语言命令
- `GET /wait` — 等待条件

### 导航类
- `POST /home` `POST /back` `POST /recents` `POST /notifications`

### 系统控制类
- `POST /volume` `POST /brightness` `POST /flashlight` `POST /dnd`
- `POST /wake` `POST /lock` `POST /rotate`

## Level 1: 原子操作技能

对 Level 0 的轻度封装，加入错误处理和日志。

### `skills/atomic-tap/SKILL.md`
```
触发：需要点击屏幕上的精确坐标
步骤：POST /tap {nx, ny} → 等待 300ms → 验证屏幕变化
注意：归一化坐标 (0.0-1.0)，不是像素
```

### `skills/atomic-input/SKILL.md`
```
触发：需要输入文本到当前焦点输入框
步骤：确认有可编辑焦点 → POST /text {text} → 验证输入内容
回退：无焦点时先 findclick 输入框再输入
```

### `skills/atomic-navigate/SKILL.md`
```
触发：需要执行系统导航操作
步骤：POST /home|/back|/recents → 等待 500ms → 验证包名变化
```

## Level 2: 语义操作技能

封装"在屏幕上找到东西并与之交互"的通用能力。

### `skills/semantic-find-click/SKILL.md`
```
触发：需要按文本/描述找到UI元素并点击
步骤：
1. 调用 POST /findclick {text: "目标文字"}
   ⚠️ 实践验证：findByText 同时搜索 text 和 contentDescription
   → 图标按钮（只有 desc 无 text）也能被找到
2. 如果成功 → 等待 500ms → 验证屏幕变化
3. 如果失败（text 找不到）：
   a. 尝试 POST /findnodes {text: "目标文字"} 看是否存在但不可点击
   b. 如果存在 → 尝试点击其 parent（向上冒泡）
   c. 如果不存在 → 尝试滚动查找（scroll-to-find）
4. 全部失败 → 返回失败原因 + 当前屏幕摘要
经验积累：记录哪种策略在哪个 APP 上成功
```

### `skills/semantic-scroll-find/SKILL.md`
```
触发：目标元素不在当前可见区域
步骤：
1. 记录当前屏幕文本快照
2. 向下滚动一屏（POST /scroll {direction: "down"}）
3. 等待 500ms
4. 读取新屏幕，搜索目标文本
5. 如果找到 → 调用 find-click
6. 如果没找到 → 对比新旧屏幕
   - 屏幕无变化 = 已到底部 → 尝试向上滚动
   - 屏幕有变化 = 还有内容 → 继续滚动（最多 5 次）
7. 上下都找不到 → 返回失败
```

### `skills/semantic-wait-for/SKILL.md`
```
触发：需要等待特定内容出现（APP 加载/页面跳转/动画结束）
步骤：
1. 调用 GET /wait?text={keyword}&timeout={ms}
2. 如果 found=true → 返回成功 + 元素位置
3. 如果 found=false → 返回失败 + 当前屏幕摘要
最佳实践：
- APP 启动后等待 APP 标题文本
- 页面跳转后等待目标页面的标志性文本
- 不要等待可能不出现的文本（用超时保护）
```

### `skills/semantic-dismiss/SKILL.md`
```
触发：弹窗/对话框阻挡了操作
步骤：
1. 调用 POST /dismiss
2. 如果成功（点击了关闭/取消/确定按钮）→ 继续原操作
3. 如果失败（没找到可关闭的按钮）→ 尝试 POST /back
4. 再次失败 → 读取弹窗内容，报告给人类
注意：有些"弹窗"实际是 APP 的核心 UI（如权限请求），不应该盲目关闭
```

## Level 3: APP 操作技能

这些技能封装特定 APP 或系统场景的操作路径。随经验积累逐步增加。

### `skills/app-open/SKILL.md`
```
触发：需要打开指定 APP
步骤：
1. 检查 Memory 中是否有该 APP 的 Intent 记录
2. 如果有 → POST /intent {已知的 intent 参数}
3. 如果没有 → POST /intent {action: "android.intent.action.MAIN", package: "搜索到的包名"}
4. 等待 APP 启动（waitForCondition 2-5s）
5. 验证：foreground APP 是否是目标包名
6. 成功 → 记录 Intent 到 Memory（下次直接用）
APP 名称映射：
- 中文名 → 搜索 GET /apps 匹配
- 英文名 → 搜索包名/标签
- 通用类型（"浏览器"/"相机"）→ Intent Category
```

### `skills/app-settings-navigate/SKILL.md`
```
触发：需要导航到系统设置的特定页面
步骤：
1. 使用专用 Intent 直达目标页面
   - WiFi: android.settings.WIFI_SETTINGS
   - 蓝牙: android.settings.BLUETOOTH_SETTINGS
   - 显示: android.settings.DISPLAY_SETTINGS
   - 声音: android.settings.SOUND_SETTINGS
   - 电池: android.intent.action.POWER_USAGE_SUMMARY
2. 如果 Intent 失效（OEM 自定义）→ 打开设置主页 → scroll-find 目标项
3. 验证：屏幕上出现目标设置项的关键词
```

### `skills/app-toggle-setting/SKILL.md`
```
触发：需要切换系统开关（WiFi/蓝牙/DND等）
步骤：
1. 导航到目标设置页面（调用 settings-navigate）
2. 在 View 树中搜索 Switch/Toggle/CheckBox 类型的控件
   策略 A: 按 className 搜索（Switch, ToggleButton, CheckBox）
   策略 B: 按 resourceId 搜索（android:id/switch_widget 等）
   策略 C: 按 checkable 属性 + 相关文本搜索
3. 记录当前状态（isChecked）
4. 点击切换
5. 验证：重新读取控件状态，确认 isChecked 翻转
6. 验证：调用系统 API 确认实际状态（如 WiFi 是否真的关了）
OEM 差异经验：写入 Memory，格式见 global-rules.md
```

## Level 4: 任务技能

这些是面向用户意图的高层技能。初期为空，随使用积累。

### 设计原则
- Level 4 技能不硬编码在 SKILL.md 中
- 它们是 Agent 在实际操作中**动态组合** Level 2-3 技能形成的
- 成功的组合模式记录到 Memory，频繁使用的提升为 Skill
- 示例：

```
任务："发微信消息给张三说我到了"
动态组合：
  1. app-open("微信")
  2. semantic-find-click("搜索") → 输入"张三" → wait-for("张三") → find-click("张三")
  3. semantic-find-click("输入框") → input("我到了") → find-click("发送")
  4. verify: 屏幕上出现"我到了"的消息气泡
  5. navigate-home
```

## 技能进化路径

```
新场景出现
  ↓
Agent 用 Level 1-2 技能临时组合完成
  ↓
成功 → 记录到 Memory（操作路径 + 设备 + APP）
  ↓
同一模式出现 3+ 次
  ↓
提升为 Level 3 Skill（固化为 SKILL.md）
  ↓
跨设备验证通过
  ↓
泛化为通用 Level 3 Skill
```
