# Skill: Agent Phone Control (Cascade as LLM Brain)

## 触发条件
当用户要求执行复杂的多步手机操作、跨APP工作流、或需要动态决策的任务时自动触发。

## 核心架构
```
Cascade (LLM Brain) ←→ Browser (MCP) ←→ ScreenStream API ←→ Android Phone
                    or
Cascade (LLM Brain) ←→ Terminal (curl) ←→ ScreenStream API ←→ Android Phone
```

Cascade 本身就是 Agent 的大脑，不需要额外的 LLM API。通过 MCP 浏览器工具或 curl 调用手机 API，实现 Observe-Think-Act 循环。

## Agent 循环（每一步）

### 1. Observe（观察）
```javascript
// MCP 方式（推荐）
const screen = await agent.observe();
// 返回: { pkg, texts[], clickables[], textCount, summary }

// curl 方式
curl -s http://127.0.0.1:PORT/screen/text
```

### 2. Think（决策）
Cascade 根据观察结果决定下一步动作。关键决策点：
- 当前在哪个APP？目标APP是什么？
- 屏幕上有没有目标元素？需要滚动吗？
- 有没有弹窗/权限对话框需要先处理？
- 上一步操作是否成功？需要回退吗？

### 3. Act（执行）
```javascript
// MCP 方式
await agent.act('click', {text: '设置'});  // 按文字点击
await agent.act('tap', {x: 540, y: 1200}); // 坐标点击
await agent.act('intent', {action: 'android.settings.WIFI_SETTINGS', flags: ['FLAG_ACTIVITY_NEW_TASK']}); // 直接Intent
await agent.act('home');                     // 导航
await agent.act('type', {text: '搜索词'});  // 输入文字
await agent.act('swipe', {x1:540,y1:1800,x2:540,y2:600,duration:300}); // 滑动
await agent.act('scroll_down');              // 向下滚动

// curl 方式
curl -s -X POST http://127.0.0.1:PORT/findclick -H "Content-Type: application/json" -d '{"text":"设置"}'
curl -s -X POST http://127.0.0.1:PORT/tap -H "Content-Type: application/json" -d '{"x":540,"y":1200}'
curl -s -X POST http://127.0.0.1:PORT/intent -H "Content-Type: application/json" -d '{"action":"android.settings.WIFI_SETTINGS"}'
```

### 4. Verify（验证）
```javascript
// 等待特定文本出现
await agent.waitFor('蓝牙', 5000);

// 或重新观察确认
const after = await agent.observe();
// 检查 after.pkg 和 after.texts 是否符合预期
```

## 可用动作清单

| 动作 | agent.act() | 参数 | 说明 |
|------|-------------|------|------|
| 按文字点击 | `click` | `{text}` | 在View树中找到文字并点击 |
| 坐标点击 | `tap` | `{x, y}` | 直接坐标点击 |
| 滑动 | `swipe` | `{x1,y1,x2,y2,duration}` | 任意方向滑动 |
| 输入文字 | `type` | `{text}` | 在当前焦点输入 |
| 按键 | `key` | `{keycode}` | 发送按键事件 |
| Intent | `intent` | `{action,data,package,flags,extras}` | 发送任意Intent |
| 主页 | `home` | - | 按Home键 |
| 返回 | `back` | - | 按Back键 |
| 最近任务 | `recents` | - | 打开最近任务 |
| 唤醒 | `wake` | - | 唤醒屏幕 |
| 锁屏 | `lock` | - | 锁定屏幕 |
| 向下滚动 | `scroll_down` | - | 页面下滑 |
| 向上滚动 | `scroll_up` | - | 页面上滑 |
| 音量+ | `volume_up` | - | 增大音量 |
| 音量- | `volume_down` | - | 减小音量 |
| 通知栏 | `notifications` | - | 下拉通知 |
| 快捷设置 | `quicksettings` | - | 下拉快捷设置 |

## 高级API

| API | 方法 | 说明 |
|-----|------|------|
| `/screen/text` | GET | 提取屏幕文字+可点击元素 |
| `/viewtree` | GET | 完整View树（含坐标） |
| `/deviceinfo` | GET | 设备信息 |
| `/notifications/read` | GET | 读取通知列表 |
| `/wait?text=X&timeout=T` | GET | 等待文字出现 |
| `/command` | POST | 自然语言命令（走关键词引擎） |
| `/command/stream` | POST | SSE流式命令执行 |
| `/files/list?path=X` | GET | 文件列表 |
| `/screenshot` | GET | 截屏 |

## 策略模式

### 直接Intent（最快，适用于已知目标）
```javascript
// 直接跳到WiFi设置
await agent.act('intent', {action: 'android.settings.WIFI_SETTINGS', flags: ['FLAG_ACTIVITY_NEW_TASK', 'FLAG_ACTIVITY_CLEAR_TASK']});
```

### 搜索+点击（通用，适用于需要找元素）
```javascript
const s = await agent.observe();
// 判断目标是否在屏幕上
if (s.texts.some(t => t.includes('蓝牙'))) {
    await agent.act('click', {text: '蓝牙'});
} else {
    await agent.act('scroll_down');  // 找不到就滚动
    // 重新观察...
}
```

### 应对弹窗（防御性，Agent必备）
```javascript
const s = await agent.observe();
if (s.pkg.includes('securitypermission') || s.texts.some(t => t.includes('允许'))) {
    // 系统权限弹窗 → 用viewtree找按钮坐标 → 精确点击
    const tree = await agent.viewTree();
    // 解析tree找到"打开"/"允许"按钮的bounds → tap中心点
}
```

## 端口发现
当前固定端口由 dev-deploy.ps1 设置，默认 8086（如 8080-8085 被占用）。
检查: `curl -s http://127.0.0.1:8086/status`

## 常见Intent速查
| 目标 | Intent Action |
|------|---------------|
| WiFi设置 | `android.settings.WIFI_SETTINGS` |
| 蓝牙设置 | `android.settings.BLUETOOTH_SETTINGS` |
| 关于手机 | `android.settings.DEVICE_INFO_SETTINGS` |
| 显示设置 | `android.settings.DISPLAY_SETTINGS` |
| 电池设置 | `android.intent.action.POWER_USAGE_SUMMARY` |
| 应用管理 | `android.settings.APPLICATION_SETTINGS` |
| 位置设置 | `android.settings.LOCATION_SOURCE_SETTINGS` |
| 打开URL | `android.intent.action.VIEW` + data=URL |
| 拨号 | `android.intent.action.DIAL` + data=tel:NUMBER |
| 发短信 | `android.intent.action.SENDTO` + data=sms:NUMBER |
