---
name: feature-development
description: 为ScreenStream项目开发新功能的完整技能。当用户提出新功能需求、需要添加API端点、前端交互、或跨模块功能时自动触发。
---

## 核心原则
- 一句话需求 → 全流程交付，中间不停顿
- 后端先行，前端同步，文档收尾
- 遵循现有代码模式，不发明新模式

## 模块知识图谱

### 后端 API 开发模式
所有 Input API 遵循统一模式：

```kotlin
// InputRoutes.kt — 路由定义
post("/新端点") { requireInputService { svc ->
    val json = JSONObject(call.receiveText())
    svc.新方法(json.getXxx("参数"))
    call.respondText(jsonOk(), ContentType.Application.Json)
}}

// InputService.kt — 业务实现
fun 新方法(参数: Type) {
    // AccessibilityService 操作
    performGlobalAction(GLOBAL_ACTION_XXX)
}
```

### 前端交互开发模式
所有前端交互遵循统一模式：

```javascript
// index.html — 导航栏按钮
<button id="newBtn" onclick="newBtnClick()" title="功能名">
    <svg width="24" height="24" viewBox="0 0 24 24">
        <path fill="#FFF" d="SVG_PATH"/>
    </svg>
</button>

// 事件处理
function newBtnClick() {
    sendNavAction('/新端点');  // 导航类
    // 或
    sendInputJson('/新端点', { 参数: 值 });  // 数据类
}
```

### MJPEG 流媒体开发模式
```kotlin
// HttpServer.kt — WebSocket 端点
webSocket("/stream/新协议") {
    handleVideoStream("CODEC", sharedFlow, reportLatency = false)
}

// 路由挂载
routing {
    installInputRoutes()  // Input API 共享挂载
    // 新路由在这里添加
}
```

## 常用开发场景速查

### 场景 A: 新增导航按钮（如音量+/-、锁屏）
1. `InputService.kt` — 添加 `performGlobalAction()` 或 shell 命令
2. `InputRoutes.kt` — 添加 `post("/新端点")` 路由
3. `index.html` — 在 `navBar` 中添加按钮 + SVG 图标 + 事件处理

### 场景 B: 新增设置项
1. `InputSettings.kt` 或对应模块 Settings — 添加数据字段
2. `*SettingsUI.kt` — 添加 Compose UI
3. Koin Module — 确认 Settings 已注入

### 场景 C: 新增流媒体功能
1. `HttpServer.kt` — 添加 WebSocket 或 HTTP 端点
2. `index.html` — 添加前端播放/控制逻辑
3. CORS — 确认新端点的 header/method 已允许

### 场景 D: 修改触控/键盘输入行为
1. `index.html` — 修改事件监听器（mousedown/touchstart/keydown）
2. `InputRoutes.kt` — 如需新参数，修改 JSON 解析
3. `InputService.kt` — 修改 AccessibilityService 操作

## 文件位置速查
| 功能 | 文件路径 |
|------|---------|
| 输入路由 | `反向控制/输入路由/InputRoutes.kt` |
| 输入服务 | `反向控制/输入服务/InputService.kt` |
| 输入设置 | `反向控制/输入服务/InputSettings.kt` |
| HTTP 服务 | `投屏链路/MJPEG投屏/mjpeg/internal/HttpServer.kt` |
| 前端页面 | `投屏链路/MJPEG投屏/assets/index.html` |
| 前端脚本 | `投屏链路/MJPEG投屏/assets/dev/script.js` |
| Koin DI | `反向控制/HTTP服务器/InputKoinModule.kt` |
| 模块设置 | `基础设施/030-通用工具_Utils/ModuleSettings.kt` |
| 应用入口 | `用户界面/src/main/kotlin/.../SingleActivity.kt` |

## ⚠️ 关键教训（铁律）

### 端口路由铁律
- `index.html` 的 `inputApiPort` 必须为 `null`（同源），**禁止硬编码 8084**
- Input API 路由已挂载在 MJPEG HttpServer 上，与页面同端口
- 手机实际监听端口由系统动态分配（可能是 8080/8081/8086 等），8084 可能根本不存在
- 验证方法：`curl http://127.0.0.1:<端口>/status` 确认端口可达

### 端到端验证铁律
- 功能开发完成后，**必须在浏览器中实际点击每个按钮**验证效果
- API 返回 `{"ok":true}` ≠ 前端调用成功（端口/CORS/JS错误都可能阻断）
- 前端调试：打开浏览器 DevTools → Network 面板，确认每个请求的 URL 和状态码
- 键盘输入验证：在手机输入框中打字，确认字符出现

### 菜单设计原则
- 核心功能（导航/系统控制/远程工具）= 用户直接需要 → 保留
- 开发者工具（View树/语义点击）= 仅开发时需要 → 不放主菜单
- 自动化（宏系统）= 高级用户需要 → 保留但简化

## 质量检查清单
- [ ] Kotlin 代码遵循项目的 public API 可见性规则
- [ ] JSON 响应使用 `JSONObject` 构建（禁止手拼字符串）
- [ ] 新路由使用 `requireInputService` 包装
- [ ] 前端事件有 `preventDefault()` 防止默认行为
- [ ] CORS 配置覆盖新增的 header/method
- [ ] 前端版本号已更新（`verDiv.innerText`）
- [ ] `index.html` 的 `"use strict"` 模式下无语法错误
- [ ] **前端 API 调用走同源端口**（`getInputApiBase()` 返回 `window.location.origin`）
- [ ] **浏览器实测每个按钮**：点击后手机端产生真实效果
- [ ] **键盘输入实测**：PC 按键 → 手机端出现字符
