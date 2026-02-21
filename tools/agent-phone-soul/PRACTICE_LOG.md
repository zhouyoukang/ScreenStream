# Phone Agent 实践日志

> 记录每次实践验证中发现的问题和设计修正。

## 2026-02-21 首次 OODA-L 实践

### 环境
- 设备：OnePlus NE2210, Android 15 (API 35), 1080x2412
- 电池：92%, WiFi 连接
- ScreenStream 端口：**8086**（非默认8081）
- ADB：`e:\...\090-构建与部署_Build\android-sdk\platform-tools\adb.exe`

### 执行的循环
```
Observe: GET /screen/text → 桌面, 27项, "设置" clickable=true
Orient:  在桌面, 目标"设置"可见
Decide:  findclick "设置"（桌面已可见，无需Intent）
Act:     POST /findclick {"text":"设置"} → ok=true, clicked=设置
Verify:  GET /screen/text → com.android.settings, 显示页面（非主页！）
Learn:   设置可能恢复上次位置，需要验证是否在目标页
---
Act:     GET /deviceinfo → OnePlus NE2210 全部信息获取成功
Act:     POST /home → 返回桌面
Verify:  GET /foreground → com.microsoft.launcher 确认
```

### 发现的设计问题

#### P1: 端口探测必须是第一步
- 设计假设默认8081，实际是8086
- **修正**：connect-phone workflow 必须探测 8080-8099
- **状态**：已知，待写入 workflow

#### P2: APP 恢复上次位置
- 点击"设置"预期进入主页，实际进入"显示"子页
- **原因**：Android 默认恢复 Activity 上次状态
- **修正**：打开系统设置时应用 `FLAG_ACTIVITY_CLEAR_TASK` Intent，而不是 findclick
- **影响**：app-open Skill 需要区分"通过图标打开"和"通过Intent打开"
- **状态**：待修正 Skill

#### P3: 信任模型在实践中有效
- T0 模式（每步确认+全量感知）确实捕获了 P2 问题
- 证实了"闭环感知"元规则的价值
- **状态**：✅ 验证通过

#### P4: API 调用审批阻断连续操作
- Windsurf 的 run_command 安全审批打断了 OODA-L 循环的连续性
- 真正的 Agent 需要对 localhost API 调用免审批
- **修正**：Agent 账户可能需要 Python 脚本封装，或调整 SafeToAutoRun 策略
- **状态**：部署时处理

#### P5: 响应时间可接受但不快
- 每个 API 调用 ~100-300ms
- 加上 800ms UI 稳定等待
- 一个完整的 observe-act-verify 约需 2-3 秒
- T2/T3 模式减少感知频率后可提速到 ~1 秒/步
- **状态**：可接受，T3 模式下速度足够

### 信任更新
```
设备 OnePlus NE2210:
  - /screen/text: T0 → T1（1次成功）
  - /findclick: T0 → T1（1次成功）
  - /deviceinfo: T0 → T1（1次成功）
  - /home: T0 → T1（1次成功）
  - /foreground: T0 → T1（1次成功）

APP com.android.settings:
  - 打开方式: findclick"设置" → 进入子页面（非主页），信任不变T0
  - 推荐方式: Intent ACTION_SETTINGS + CLEAR_TASK → 待验证
```

---

## 2026-02-21 场景2：探索陌生APP（时钟）

### 目的
验证 explore-unknown-app Skill 的设计逻辑

### 执行过程
```
Phase 1: 第一印象
  Observe: 桌面 27 项, "时钟" clickable
  Act:     findclick "时钟" → ok
  Verify:  com.coloros.alarmclock, 24 项
  心智模型: 底部4Tab导航（闹钟/世界时钟/秒表/计时器），当前在闹钟Tab

Phase 2: 导航验证
  Act:     findclick "秒表" → ok (class=FrameLayout)
  Verify:  秒表页，6项，有"开始"按钮

Phase 3: 功能操作
  Act:     findclick "开始" → ok (class=ImageView)
  Verify:  UI变化: "开始" → "暂停"+"复位"+"计次"，秒表在计时

Phase 4: 状态控制
  Act:     findclick "暂停" → ok
  Act:     findclick "复位" → ok
  Act:     POST /home → ok

全链路耗时: ~8秒（含等待和验证）
```

### 新发现

#### P6: 探索模式设计在实践中有效
- Phase 1-4 的渐进探索流程自然流畅
- 心智模型（底部Tab导航）第一次感知就建立了
- **设计验证**: ✅ explore-unknown-app Skill 的 Phase 结构合理

#### P7: 按钮class多样性
- "时钟"桌面图标: class=TextView
- "秒表"Tab: class=FrameLayout
- "开始/暂停/复位"按钮: class=ImageView
- **发现**: 不能依赖 class 判断可交互性，要依赖 clickable 属性
- **影响**: skills-hierarchy 中的 Strategy 4 (findByClassName) 可靠度低于预期

#### P8: UI 状态转换可观测
- 秒表启动后，"开始"消失，"暂停/复位/计次"出现
- 通过对比 observe 前后的 text 列表变化可以可靠地检测操作是否生效
- **发现**: 文本列表差异对比是低成本高可靠的验证方式

#### P9: 全链路8秒，探索模式可接受
- 5步操作 × ~1.5秒/步 ≈ 8秒
- 探索模式（T0）全量感知每步~1.5秒
- 执行模式（T2+）减少感知可压到~0.5秒/步
- **结论**: 速度可接受，实际操作不需要毫秒级响应

### 信任更新（累加）
```
APP com.coloros.alarmclock（时钟）:
  - Tab导航: T0 → T1（1次成功）
  - 按钮操作(开始/暂停/复位): T0 → T1（1次成功）
  - 导航模式: 底部4Tab（闹钟/世界时钟/秒表/计时器）
  - 按钮标识方式: findByText 有效，class=ImageView
```

---

## 2026-02-21 场景3：Intent 方式打开APP + API 限制发现

### 目的
验证 P2 的修正方案（Intent + CLEAR_TASK 打开设置主页）

### 执行过程
```
Act:     POST /intent {"action":"android.settings.SETTINGS"}
         → ok=true
Verify:  com.android.settings, 仍在"显示"子页面（与 findclick 结果相同）
```

### 新发现

#### P10: sendIntent 缺少 flags 参数（API 限制）
- InputService.kt:2168 硬编码 FLAG_ACTIVITY_NEW_TASK
- 不暴露 flags 参数 → 无法传入 FLAG_ACTIVITY_CLEAR_TASK
- **影响**: 所有需要"干净启动"的场景
- **已写入**: shared-knowledge/api-issues.md → Developer Cascade 可读
- **临时绕行**: 先多次 /back 退到主页

#### P11: 共享知识通道首次使用验证
- Phone Agent 发现 API 问题 → 写入 shared-knowledge/api-issues.md
- Developer Cascade 可从中读取并修复
- **设计验证**: ✅ 共享知识通道工作流程合理

### 累计实践统计
```
总操作数: 15+
成功率: 14/15 (93%) — 唯一"失败"是设置打开到子页面（API限制，非Agent错误）
API 调用类型: screen/text(5), findclick(6), home(3), intent(1), deviceinfo(1), foreground(1)
设备信任: OnePlus NE2210 → 多数 API 已 T1
APP 信任: 时钟 T1, 设置 T0（需 Intent flags 修复后重新验证）
发现的设计问题: 11 个（P1-P11）
  - 设计验证通过: P3(信任模型), P6(探索模式), P8(状态转换检测), P9(速度), P11(共享通道)
  - 需修正: P1(端口探测), P2(APP恢复位置), P7(class不可靠)
  - 需API改进: P10(Intent flags)
  - 需部署处理: P4(审批阻断)
  - 已确认: P5(响应时间)
```

---

## 2026-02-21 方法论反思：实践方式的底层逻辑错误

### 错误诊断

前三个场景的实践方式是"实践→发现→实践→发现"的反应式循环。
正确的方式应该是"思考→假设→设计验证→实践→深度思考→调整"的目的性循环。

具体错误：
1. 场景选择由好奇心驱动而非假设驱动
2. 每次实践后只记录事实不提炼洞察
3. 广度多深度少（3个浅场景 vs 1个深场景）
4. 违反了自己设计的"渐进抽象"——只做第一步（记录具体）不做后续（提炼模式）

### 修正后的实践方法

```
思考：要验证的核心假设是什么？
设计：什么最小实践能验证/证伪？
实践：执行
深度思考：结果vs预期，假设哪里错了，对设计意味什么
调整：修正设计
→ 回到思考
```

---

## 2026-02-21 场景4：便签APP深度探索（思考驱动的实践）

### 核心假设
Agent 可以通过 findByText 可靠地操控大多数 APP 的 UI。
成功率预期：>80% 假设成立，50-80% 部分成立，<50% 需重新设计。

### 思考先行：打开便签后的屏幕分析

**发现**：View 树中每条笔记出现两次（clickable 容器 + non-clickable 子 TextView）。
**假设**：文本重复可能导致 findByText 误点不可点击的节点。
**验证设计**：点击第一条笔记"超级项目"，观察是否成功打开。

### 实践结果

findclick "超级项目" → 成功打开编辑页面。
findAndClickByText 的实现已有优先选择 clickable 节点的逻辑。
**假设被证伪** — 文本重复不是问题，代码已有防护。

### 深度反思

1. **过度推断**：基于表面观察做悲观假设，未验证就准备修改设计 → 会引入不必要的复杂性
2. **findByText 成功率**：8/8 = 100%（但都是简单场景，需更复杂验证）
3. **未验证的盲区**：
   - 负例（findByText 找不到时的降级行为）
   - 边界（部分匹配、相似文本、动态内容）
   - 失败路径（操作后UI没变化或出错）
4. **信任模型的缺陷**：T0-T3 只统计成功次数，不考虑"是否测试过困难场景"。
   一个从未失败过的 Agent 不一定很强，可能只是没遇到过困难。

### 设计改进洞察

soul.md 的信任模型应增加维度：
- 当前：信任 = 成功次数
- 改进：信任 = 成功次数 × 场景难度覆盖率

以及：View 树冗余（同一元素多节点表示）是常见现象，/screen/text 的结果需要去重能力。

---

## 2026-02-21 场景5：负例验证 + contentDescription 发现

### 核心假设
findByText 在找不到目标时能优雅降级；图标按钮（无text只有desc）需要单独策略。

### 实践1：负例（搜索不存在的文字）
```
Act:     POST /findclick {"text":"不存在的按钮名称XYZ"}
Result:  {"ok":false,"error":"Node not found: 不存在的按钮名称XYZ"}
```
**结论**：负例处理正常——返回清晰错误，不崩溃不卡死。Agent 收到 ok=false 后可按降级策略继续。

### 实践2：View 树中 desc-only 元素识别
```
Act:     GET /viewtree?depth=3 → 过滤只有 desc 没有 text 的元素
Result:  发现4个 desc-only 元素：天气小组件/时间小组件/展开快捷栏/必应壁纸
```

### 实践3：findByText 能否找到 desc-only 元素
```
Act:     POST /findclick {"text":"必应壁纸"}
Result:  {"ok":true,"clicked":"必应壁纸","class":"android.widget.ImageView"}
```
**重大发现**：findByText 成功找到并点击了一个只有 contentDescription 没有 text 的元素！

### 根因分析
Android `findAccessibilityNodeInfosByText()` API 的行为：
同时搜索 `text` 属性和 `contentDescription` 属性。
这意味着 **Strategy 1 (findByText) 已经覆盖了 Strategy 2 (findByContentDescription)**。

### 设计影响
- skills-hierarchy.md 策略降级：5级简化为4级（合并 Strategy 1+2）
- memory-seeds.md Seed 3：已更新策略描述
- 整体评估：findByText 的覆盖面比预期更广，是更可靠的主策略

### 累计 findByText 成功率
```
总调用: 10 次（含1次负例）
正例成功: 9/9 = 100%
  - text 匹配: 8次（设置/时钟/秒表/开始/暂停/复位/便签/超级项目）
  - desc 匹配: 1次（必应壁纸，只有 contentDescription）
负例正确返回: 1/1 = 100%
```

### 仍未验证的盲区
- 部分匹配（用户说"设置"但 UI 上显示"系统设置"）
- 相似文本（多个元素包含相同关键词）
- 动态加载内容（列表滚动后新出现的元素）
- 非中文环境（英文/混合语言 UI）

---

## 2026-02-21 场景6：Tasker探索 + 弹窗处理 + 循环密度验证

### 使用新模型（三层可变性 α/β/γ）

### 执行过程
```
[T1 API, 低密度] findclick "Tasker" → ok (信任API，不额外verify)
[T0 APP, 高密度] screen/text → 弹窗！电池优化提示
[处理障碍] findclick "不再提醒" → ok
[T0 APP, 高密度] screen/text → Tasker主界面（配置文件/任务/场景/变量 4Tab + MQTT配置）
[T1 API, 低密度] POST /home → ok (信任API)
```

### 新发现

#### P12: 弹窗是最常见的首次打开障碍
- Tasker 首次打开 → 电池优化弹窗
- 验证了 explore-unknown-app Skill Phase 2 的必要性
- **设计验证**: ✅

#### P13: /dismiss 对APP自定义弹窗覆盖不全
- /dismiss 预设12种关闭文字(取消/关闭/知道了/OK等)
- Tasker的"不再提醒"不在预设列表中
- findclick 可以作为补充(手动指定弹窗按钮文字)
- **设计启示**: /dismiss 是"通用弹窗处理"，但复杂APP需要用 findclick 精确处理

#### P14: 循环密度变化自然发生
- 对T1的API(findclick/home)：没有额外verify，直接信任返回值
- 对T0的APP(Tasker)：全量screen/text感知
- **密度差异不需要显式切换，信任自然驱动**
- **设计验证**: ✅ β1循环密度模型有效

### β规则审视（反思模式）
- β1循环：密度变化自然，不需修正
- β2信任：发现新维度——弹窗处理信任应独立于APP操作信任（观察中，未达修正门槛）
- β4硬边界：Tasker有MQTT外部连接，但是APP自身功能，不是Agent发起的，不影响边界

### 累计统计
```
总场景: 6 | 总API调用: 25+ | findByText成功率: 11/11=100%
设备: OnePlus NE2210, Android 15, 端口8086
信任状态:
  API findclick: T1→T2 (6+次连续成功)
  API screen/text: T1→T2 (7+次成功)
  API home: T1→T2 (4次成功)
  APP 时钟: T1
  APP 便签: T1
  APP Tasker: T0→T1 (首次成功打开+弹窗处理)
  APP 设置: T0 (打开到子页面问题未解决，需编译验证Intent修复)

设计发现: P1-P14
  验证通过(7): P3信任 P6探索 P8状态检测 P9速度 P11共享通道 P12弹窗障碍 P14密度变化
  需修正(3): P1端口探测 P2APP恢复位置 P7class不可靠
  需API改进(1): P10 Intent flags ✅已修复代码
  需部署处理(1): P4审批阻断
  信息性(2): P5响应时间 P13 dismiss覆盖范围
```

---

## 2026-02-21 场景8：后台路径验证（零屏幕依赖）

### 核心假设
Agent不必依赖手机屏幕，可以通过后台路径完成很多任务。

### 验证结果

| 后台路径 | 能力 | 成功 | 屏幕依赖 |
|----------|------|------|---------|
| `adb shell pm list packages` | 获取已装APP | ✅ | 零 |
| `adb shell am start` | 启动APP | ✅ | 低(APP会到前台) |
| `adb shell dumpsys battery` | 电池信息 | ✅ | 零 |
| `adb shell wm size` | 屏幕分辨率 | ✅ | 零 |
| `adb shell getprop` | 设备属性 | ✅ | 零 |
| `adb shell input keyevent` | 按键注入 | ✅ | 低 |
| `GET /notifications/read` | 通知监控 | ✅ | 零 |
| `GET /deviceinfo` | 设备信息 | ✅ | 零 |
| `GET /foreground` | 前台APP | ✅ | 零 |

### 新发现

#### P16: 通知监控是极高价值的零依赖通道
- `/notifications/read` 捕获到微信消息（实时内容），人类完全无感
- 这意味着Agent可以"被动感知"手机上发生的事，不需要主动操控屏幕
- **这改变了Agent的运行模式**：不只是"被指令驱动"，还可以"被事件驱动"

#### P17: ADB后台路径覆盖面广
- APP列表/设备信息/电池状态/系统属性 全部可后台获取
- am start 可以启动APP但会影响前台（中等依赖）
- input keyevent 可以注入按键但会影响前台（中等依赖）

#### P18: "最大化可达性，最小化依赖"在实践中成立
- 大量Agent需要的信息可以零屏幕依赖获取
- 只有"在APP内的具体UI操作"才真正需要屏幕控制
- **Agent的默认模式应该是"后台感知"，只在必要时才"前台操控"**

### 路径依赖度分类（实践验证版）

```
零依赖（人类正常用手机，Agent完全不干扰）：
  - 通知监控, 设备信息, APP列表, 电池/网络状态, 系统属性

低依赖（一瞬间影响前台，然后交还）：
  - am start 启动APP, input keyevent 按键

高依赖（占用前台，人类不能同时操作）：
  - findclick, tap, swipe, text input, screen/text
```

---

## 2026-02-21 场景9-10：ADB后台路径 + 混合模式

### 场景9：ADB --activity-clear-task 解决P2
```
ADB: am start -a android.settings.SETTINGS --activity-clear-task
Result: 设置打开到主页（软件更新/WLAN/飞行模式）✅
```
P2问题通过ADB路径完美解决，不需要等待sendIntent代码编译。

### 场景10：ADB+API混合最小依赖模式
```
[1] ADB启动时钟（后台路径）
[2] API /screen/text 读取（只读，零操控）
[3] ADB KEYCODE_HOME 返回（后台路径）
→ 全程零findclick，最小屏幕依赖
```

### 新发现

#### P19: ADB --activity-clear-task 是通用的"干净启动"方案
- 不需要修改ScreenStream代码
- 任何APP都可以用：`am start -n <component> --activity-clear-task`
- 是P2(APP恢复位置)的完美绕行方案

#### P20: ADB+API混合模式验证通过
- ADB负责"启动/导航"（低依赖）
- API负责"感知/读取"（零依赖的只读操作）
- 只有"精确UI交互"才需要findclick（高依赖）
- 这是"最大化可达性，最小化依赖"的实际操作模式

### 全轮累计统计（10场景）
```
总场景: 10 | 总API调用: 35+ | ADB命令: 15+
findByText成功率: 12/12=100%
后台路径覆盖: 9种零/低依赖能力验证通过
设计发现: P1-P20
  验证通过(10): P3信任 P6探索 P8状态检测 P9速度 P11共享通道
                P12弹窗 P14密度变化 P16通知监控 P18最小依赖 P20混合模式
  需修正(2): P1端口探测 P7class不可靠
  已绕过(2): P2通过ADB --activity-clear-task绕过 P10代码已修复待编译
  需部署处理(1): P4审批阻断
  信息性(5): P5响应时间 P13dismiss覆盖 P15豆包发送按钮 P17 ADB覆盖面 P19 clear-task
```
