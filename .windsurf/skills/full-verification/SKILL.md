---
name: full-verification
description: 构建→推送→安装→启动→API验证→日志检查的完整验证链。当代码修改完成需要端到端验证时触发。
---

## 验证链（按顺序执行）

### Step 1: 编译
```powershell
$env:JAVA_HOME = "C:\Program Files\Processing\app\resources\jdk"
$env:ANDROID_SDK_ROOT = "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk"
& "e:\github\AIOT\ScreenStream_v2\gradlew.bat" assembleFDroidDebug --no-configuration-cache 2>&1 | Select-Object -Last 20
```
**成功标志**：`BUILD SUCCESSFUL`
**失败处理**：读取错误 → 修复 → 重编译（最多2轮）

### Step 2: 设备检查
```powershell
& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" devices
```
**无设备**：跳过 Step 3-6，标记为"待设备测试"

### Step 3: 推送 APK
```powershell
& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" push "e:\github\AIOT\ScreenStream_v2\用户界面\build\outputs\apk\FDroid\debug\app-FDroid-debug.apk" /data/local/tmp/ss.apk
```
**记录输出的字节数**，用于 Step 4

### Step 4: 安装
```powershell
& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" shell "cat /data/local/tmp/ss.apk | pm install -t -r -S <字节数>"
```
**成功标志**：`Success`

### Step 5: 重启应用
```powershell
& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" shell am force-stop info.dvkr.screenstream.dev
```
等待 2 秒后启动：
```powershell
& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" shell am start -n info.dvkr.screenstream.dev/info.dvkr.screenstream.SingleActivity
```

### Step 6: API 验证（如果涉及 API 变更）

**优先用 adb forward（绕过防火墙）**：
```powershell
# 端口转发（推荐，避免防火墙拦截）
& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" forward tcp:8084 tcp:8084

# Input API 状态检查
curl.exe -s --connect-timeout 5 http://127.0.0.1:8084/status

# 触控测试（注意 PowerShell 中 JSON 用单引号包裹）
curl.exe -s -X POST http://127.0.0.1:8084/tap -H "Content-Type: application/json" --data-raw '{"x":0.5,"y":0.5}'
```

**MJPEG 端口（8081）需要用户在手机上启动投屏后才会监听**：
```powershell
& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" forward tcp:8081 tcp:8081
curl.exe -s --connect-timeout 5 http://127.0.0.1:8081/
```

**设备端口状态排查**：
```powershell
& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" shell "netstat -tlnp 2>/dev/null | grep 808"
```

### Step 7: 日志检查（如果有异常）
```powershell
& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" logcat -d -t 30 --pid=$(& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" shell pidof info.dvkr.screenstream.dev) 2>$null
```

## 实战经验（2026-02-13 验证沉淀）

### PowerShell curl JSON 转义
- ❌ `-d "{\"key\":\"value\"}"` — PowerShell 双重转义导致 JSON 解析失败
- ✅ `--data-raw '{"key":"value"}'` — 单引号包裹，JSON 原样传递

### 网络连通性
- 设备 IP 直连可能被 Windows 防火墙或路由器拦截
- **优先使用 `adb forward`**，通过 USB 转发端口，100% 可靠

### 端口监听时机
- **8080**（Gateway）和 **8084**（Input）：应用启动后立即监听
- **8081**（MJPEG）：用户在手机上点击"开始投屏"后才监听
- 如果 8081 不通 → 先检查 `netstat` 确认端口是否在监听

### Ktor WebSocket 类型陷阱
- `DefaultWebSocketSession` — 基础接口，**没有 `call` 属性**
- `DefaultWebSocketServerSession` — 服务端接口，**有 `call` 属性**
- import 路径：`io.ktor.server.websocket.DefaultWebSocketServerSession`（不是 `io.ktor.websocket`）

## 验证结果模板
```
✅ 编译：成功 / ❌ 失败（原因）
✅ 设备：已连接 / ⏭ 无设备
✅ 安装：成功 / ❌ 失败（原因）
✅ 启动：成功 / ❌ 崩溃（日志）
✅ API：响应正常 / ❌ 异常（详情）
```
