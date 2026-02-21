---
description: 全流程开发管线：从一句话需求到完整交付。用户给出需求后，AI 自动完成分析→设计→编码→构建→部署→测试→验证→文档全流程。
---

# /dev — 全流程开发管线

> 用户只需给出一句话需求，AI 自动推进全流程直到可验收的产物。
> 每个 Phase 有明确的入口条件和产出物，跳过条件也写明。
> **铁律：无论小模块还是大模块，Phase 3→4→5→5.5 必须连续执行，禁止在任何 Phase 结束后停下来询问。**

## 模块规模判定与执行策略

| 规模 | 判定标准 | 执行策略 |
|------|---------|---------|
| **小模块** | 单文件或 <100 行改动 | Phase 0→3→4→5→5.5→6→7 一气呵成 |
| **中模块** | 2-3 文件，100-300 行 | 同小模块，无停顿 |
| **大模块** | 3+ 文件，300+ 行，新 API 体系 | Phase 3 可分段编辑（防 IDE 卡顿），但 Phase 3 全部完成后**立即**推进 Phase 4，**禁止停下来问用户** |

### 大模块额外规则
1. **Phase 3 分段写入**：每段 <200 行，防止 IDE 卡顿。段间不停顿，连续推进
2. **Phase 4 编译**：Phase 3 完成后**立即编译**，不问"需要我编译吗？"
3. **Phase 5 部署**：编译通过后**立即部署**，不问"需要我部署吗？"
4. **Phase 5.5 新 API 专项验证**：大模块通常有新 API，必须逐个 curl 验证每个新端点
5. **Phase 5.5 前端验证**：如有前端面板，必须打开浏览器预览并验证可交互
6. **Bug 修复闭环**：编译/运行时发现 bug → 修复 → 重编译 → 重部署 → 重验证（最多 2 轮）
7. **交付标准**：用户拿到手就能用，99.9% 无需二次调试

## Phase 0: 需求理解（30 秒）

**输入**：用户的一句话需求

**动作**：
1. 将需求拆解为：**做什么** + **在哪做** + **影响什么**
2. 判断需求类型：
   - `NEW_FEATURE` — 新功能开发
   - `BUG_FIX` — Bug 修复
   - `REFACTOR` — 重构优化
   - `CONFIG` — 配置/构建调整
   - `DOC` — 仅文档更新
3. 用一句话确认理解（不等用户回复，直接推进）

**产出**：需求类型 + 影响模块列表

---


## Phase 0.5: Fast-Path Detection (NEW - efficiency optimization)

> Before running the full pipeline, classify task complexity to skip unnecessary phases.

**Classification**:
| Type | Criteria | Skip |
|------|----------|------|
| TRIVIAL | Single file, < 10 lines change, no new API | Skip Phase 2 (research), go straight to Phase 3 |
| SMALL | 2-3 files, follows existing pattern exactly | Skip Phase 2, use quick-recipes.md templates |
| MEDIUM | New API endpoint (backend+frontend+docs) | Read code-index.md first, then Phase 2-lite (internal pattern only) |
| LARGE | New module/major feature, 4+ files | Full pipeline with external research |

**Mandatory First Step**: Read `.windsurf/code-index.md` to locate exact insertion points — saves reading 3600+ line files.

**Mandatory Second Step**: Check `.windsurf/quick-recipes.md` for matching recipe — skip pattern derivation.

## Phase 1: 影响分析（1-2 分钟）

**动作**：
1. 根据需求定位涉及的模块（参考项目结构映射）：
   ```
   :app    → 010-用户界面与交互_UI/
   :common → 070-基础设施_Infrastructure/
   :mjpeg  → 020-投屏链路_Streaming/010-MJPEG投屏_MJPEG/
   :rtsp   → 020-投屏链路_Streaming/020-RTSP投屏_RTSP/
   :webrtc → 020-投屏链路_Streaming/030-WebRTC投屏_WebRTC/
   :input  → 040-反向控制_Input/
   ```
2. 读取相关模块的 `AGENTS.md` 获取模块约束
3. 搜索现有代码确认修改点
4. 评估前后端同步需求：
   - 后端 API 变更 → 前端 `index.html` 必须同步
   - 路由变更 → InputRoutes 和 HttpServer 路由表必须同步
   - 新端口 → `project-structure.md` 必须登记

**产出**：修改文件清单 + 依赖关系

**跳过条件**：`DOC` 类型直接跳到 Phase 6

---

## Phase 2: 参考研究 + 方案设计（NEW_FEATURE 必须执行，不可跳过）

> **铁律：不做丛林开发。** 任何新功能都先找行业最优参考，复刻最优模式，用最少代码实现最大效果。
> 跳过参考研究 = 用 400 行代码实现别人 40 行就能做到的效果。

### Step 1: 外部参考研究（2-5 分钟）

**动作**：
1. `search_web` 搜索同类最优开源实现（关键词：`best open source <功能名> <平台> GitHub`）
2. 找到 2-3 个高星项目，用 `read_url_content` 读取其 README / DeepWiki 概览
3. 重点提取：
   - **功能清单**：它有哪些子功能？哪些我们没想到？
   - **API 设计**：端点命名、参数结构、错误处理模式
   - **前端 UX**：交互模式（拖拽/右键/多选/视图切换）
   - **性价比排序**：哪些特性用最少代码带来最大体验提升？

**产出**：参考分析表（内部决策，一句话总结给用户）

### Step 2: 内部模式匹配

**动作**：
1. 搜索项目中类似功能的实现模式（search + grep）
2. 如果涉及新 API → 参考 `InputRoutes.kt` 的 `requireInputService` 模式
3. 如果涉及新 UI → 参考现有 Compose UI 模式
4. 如果涉及新前端交互 → 参考 `index.html` 现有事件处理模式

### Step 3: 方案决策

**动作**：
1. 将外部参考的高价值特性 + 内部模式 → 合并为实现方案
2. 按**价值/成本比**排序特性，优先实现 ⭐⭐⭐⭐⭐ 项
3. 确定技术方案（不需要用户确认，直接执行最优方案）

**参考研究模板**（搜索时使用）：
```
搜索词1: best open source <功能> <平台> GitHub
搜索词2: <功能> web UI UX best practices features
搜索词3: <功能> REST API design patterns
```

**跳过条件**：`BUG_FIX` / `REFACTOR` / `CONFIG` 直接跳到 Phase 3

---

## Phase 3: 实现（核心阶段）

**动作**：
1. **后端优先**：先修改 Kotlin 代码
   - 遵循 `kotlin-android.md` 规则
   - 新 API → 在 InputRoutes.kt 添加路由 + InputService.kt 添加实现
   - 修改现有逻辑 → 读取 → 理解 → 最小化修改
2. **前端同步**：如果后端有 API 变更
   - 遵循 `frontend-html.md` 规则
   - 修改 `assets/index.html`
   - 确保 CORS 配置覆盖新端点
3. **关联修改**：
   - Koin DI → 检查 `*KoinModule.kt` 是否需要更新
   - Gradle → 检查是否需要新依赖
   - AndroidManifest → 检查是否需要新权限
4. **修改原则**：
   - 每个文件使用 `multi_edit` 一次性完成所有修改
   - 保持现有代码风格
   - 不添加不必要的注释
   - 不删除现有注释

**产出**：所有代码修改完成

---

## Phase 4: 构建验证

**动作**：
// turbo
1. 设置环境变量并编译：
```powershell
$env:JAVA_HOME = "C:\Program Files\Processing\app\resources\jdk"; $env:ANDROID_SDK_ROOT = "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\android-sdk"; & "e:\github\AIOT\ScreenStream_v2\gradlew.bat" assembleFDroidDebug --no-configuration-cache 2>&1 | Select-Object -Last 20
```
2. 如果编译失败：
   - 读取错误信息
   - 修复代码
   - 重新编译（最多 2 轮，超过则 L2 升级）

**产出**：`app-FDroid-debug.apk` 编译成功

**跳过条件**：`DOC` / `CONFIG`（不涉及代码）类型跳到 Phase 6

---

## Phase 5: 部署与测试（必须执行，不可跳过）

> **铁律**：代码改完不部署 = 半成品。只要设备已连接，必须走完部署+验证。

**动作**：
// turbo
1. 使用一键部署脚本（跳过编译，Phase 4 已编译）：
```powershell
& "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\dev-deploy.ps1" -SkipBuild
```

脚本自动完成：推送 → 安装 → 启用 AccessibilityService → 唤醒 → 启动 → 端口探测 → 端口转发 → API 验证

2. 如果 API 未就绪（投屏未启动）：
   - 提示用户：「请在手机上点击开始投屏」
   - 等待后用 `-SkipBuild -SkipInstall` 重试验证
3. API 就绪后，运行独立验证脚本（22 个端点全量测试）：
// turbo
```powershell
& "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\api-verify.ps1"
```
4. 如果涉及新 API，手动追加验证：
```powershell
curl.exe -s http://127.0.0.1:8086/<new-endpoint>
```

**产出**：应用已安装运行 + API 22/22 验证通过

**设备未连接时**：标记为“待设备测试”并在 Phase 7 说明

---

## Phase 5.5: 深度 E2E 验证（模拟用户实操）

> **铁律**：API 返回 ok ≠ 前端实际可用。必须模拟用户角度验证。

**动作**：
// turbo
1. **前端页面加载测试**：
```powershell
$html = curl.exe -s http://127.0.0.1:8086/ 2>$null; if ($html -match 'ScreenStream') { Write-Host '[OK] 页面加载正常' } else { Write-Host '[FAIL] 页面加载失败' }
```

2. **端口路由验证**（防止 inputApiPort 回归）：
```powershell
$html = curl.exe -s http://127.0.0.1:8086/ 2>$null; if ($html -match 'inputApiPort.*8084') { Write-Host '[FAIL] inputApiPort 硬编码 8084，前端将全部失效！' } else { Write-Host '[OK] inputApiPort 未硬编码' }
```

3. **核心 API 响应验证**（不只看状态码，验证返回数据）：
```powershell
$base = "http://127.0.0.1:8086"
$tests = @(
    @{name='导航-返回'; method='POST'; url="$base/back"; expect='ok'},
    @{name='系统-锁屏'; method='POST'; url="$base/lock"; expect='ok'},
    @{name='系统-唤醒'; method='POST'; url="$base/wake"; expect='ok'},
    @{name='系统-音量+'; method='POST'; url="$base/volume/up"; expect='ok'},
    @{name='设备信息'; method='GET'; url="$base/deviceinfo"; expect='model'},
    @{name='键盘输入'; method='POST'; url="$base/text"; body='{"text":"test"}'; expect='ok'}
)
$pass = 0; $fail = 0
foreach ($t in $tests) {
    if ($t.method -eq 'POST') {
        $r = curl.exe -s -X POST -H 'Content-Type: application/json' -d ($t.body ?? '{}') $t.url 2>$null
    } else { $r = curl.exe -s $t.url 2>$null }
    if ($r -match $t.expect) { Write-Host "[OK] $($t.name)"; $pass++ }
    else { Write-Host "[FAIL] $($t.name): $r"; $fail++ }
}
Write-Host "`nE2E验证: $pass 通过, $fail 失败"
```

4. **浏览器预览**：打开 browser_preview 让用户实测触控/键盘

5. **大模块新 API 专项验证**（当新增 3+ 个 API 端点时必须执行）：
```powershell
# 模板：逐个验证新 API，替换 $endpoints 内容
$base = "http://127.0.0.1:8086"
$pass = 0; $fail = 0
# GET 端点
@('/files/storage','/files/list','/files/info?path=/sdcard','/files/search?path=/sdcard&q=test') | ForEach-Object {
    $r = curl.exe -s "$base$_" 2>$null
    if ($r -match '"ok"') { Write-Host "[OK] GET $_"; $pass++ } else { Write-Host "[FAIL] GET $_`: $r"; $fail++ }
}
# POST 端点
@(@{u='/files/mkdir';b='{"path":"/sdcard/test_fm_tmp"}'},
  @{u='/files/rename';b='{"path":"/sdcard/test_fm_tmp","newName":"test_fm_tmp2"}'},
  @{u='/files/delete';b='{"path":"/sdcard/test_fm_tmp2"}'}) | ForEach-Object {
    $r = curl.exe -s -X POST -H 'Content-Type: application/json' -d $_.b "$base$($_.u)" 2>$null
    if ($r -match '"ok"') { Write-Host "[OK] POST $($_.u)"; $pass++ } else { Write-Host "[FAIL] POST $($_.u)`: $r"; $fail++ }
}
Write-Host "`n新API验证: $pass 通过, $fail 失败"
```

6. **前端面板交互验证**（当新增 UI 面板时必须执行）：
   - 用 `browser_preview` 打开页面
   - 用 MCP chrome-devtools 的 `take_snapshot` 验证面板元素存在
   - 点击触发面板，验证交互正常

**产出**：前端页面可访问 + 端口路由正确 + 核心功能全部可用 + 新 API 全部验证通过

---

## Phase 5R: 中断自愈（工作流被打断时自动执行）

> **原则**：直接诊断根因 + 给出最简修复。禁止问“为什么”，直接定位“是什么”。

**常见中断场景与自愈操作**：

| 现象 | 诊断命令 | 自愈操作 | 需用户 |
|------|----------|----------|--------|
| `未检测到 ADB 设备` | `adb devices` | `adb kill-server && adb start-server && adb devices` | 插USB |
| `端口不通` | `curl /status` | 重新探测端口 + `adb forward` | - |
| `API 未就绪` | `curl /status` | 检查应用是否运行 + 提示开始投屏 | 点开始 |
| `编译失败` | 读错误信息 | 修复代码 + 重编译（最多2轮） | - |
| `应用崩溃` | `adb logcat -d \| tail` | 重启应用 + 检查日志 | - |
| `AccessibilityService 未启用` | `adb shell settings get` | 自动启用 | - |

**执行顺序**：
1. 检测到错误 → 立即运行诊断命令
2. 根据诊断结果执行自愈操作
3. 如果需要用户物理操作（插USB/点屏幕）→ **直接告知“请做什么”**，不问“为什么”
4. 用户操作后 → 自动继续工作流（不需用户重复指令）

---

## Phase 6: 文档与收尾

**动作**：
1. 更新 `05-文档_docs/STATUS.md`（如果有实质性改动）
2. 如果新增模块 → 更新 `MODULES.md`
3. 如果新增 API → 更新 `FEATURES.md`
4. 如果有架构决策 → 在 `05-文档_docs/adr/` 创建 ADR

**产出**：文档已同步

---

## Phase 7: 交付总结

**动作**：
1. 输出简洁的完成总结：
   - 做了什么（1-3 行）
   - 修改了哪些文件
   - 构建/部署状态
   - 需要用户验证的点（如有）
2. 如果有编译失败或部署失败，明确说明卡在哪里

---

## 快速参考

### 端口标准
Gateway:8080 | MJPEG:8081 | RTSP:8082 | WebRTC:8083 | Input:8084

### 构建产物路径
`010-用户界面与交互_UI\build\outputs\apk\FDroid\debug\app-FDroid-debug.apk`

### 关键文件速查
| 需求类型 | 最可能涉及的文件 |
|---------|----------------|
| 输入控制 | `InputRoutes.kt` + `InputService.kt` + `index.html` |
| 投屏画面 | `HttpServer.kt` + `index.html` |
| UI 设置 | `010-用户界面与交互_UI/` 下 Compose 文件 |
| 新协议 | 新模块（参考 new-module-setup skill） |
| 前端交互 | `assets/index.html` + `assets/dev/script.js` |

### 需求示例 → 自动触发全流程
```
"加个音量控制按钮"
→ Phase 0: NEW_FEATURE, 影响 input + frontend
→ Phase 1: InputRoutes + InputService + index.html
→ Phase 2: 参考现有 /home /back 模式
→ Phase 3: 后端路由 + 前端按钮
→ Phase 4: 编译
→ Phase 5: 推送测试
→ Phase 6: STATUS.md
→ Phase 7: 总结
```

