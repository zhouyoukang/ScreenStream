---
name: build-and-deploy
description: 构建APK、推送到Android手机、安装并启动ScreenStream应用的完整流程。当需要编译、部署、安装APK到手机时自动触发。
---

## 推荐方式：一键脚本（Root 设备）
```powershell
# 全量：编译 + 推送 + 安装 + 自动启用 AccessibilityService + 端口转发 + 验证
& "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\dev-deploy.ps1"

# 跳过编译（仅部署已有 APK）
& "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\dev-deploy.ps1" -SkipBuild

# 跳过编译和安装（仅启用服务 + 端口转发）
& "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\dev-deploy.ps1" -SkipBuild -SkipInstall
```

## 手动步骤（备用）

### 构建
```powershell
$env:JAVA_HOME = "C:\Program Files\Processing\app\resources\jdk"
$env:ANDROID_SDK_ROOT = "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\android-sdk"
& "e:\github\AIOT\ScreenStream_v2\gradlew.bat" assembleFDroidDebug --no-configuration-cache
```

### 推送 + 安装
```powershell
$ADB = "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\android-sdk\platform-tools\adb.exe"
$APK = "e:\github\AIOT\ScreenStream_v2\010-用户界面与交互_UI\build\outputs\apk\FDroid\debug\app-FDroid-debug.apk"
& $ADB push $APK /data/local/tmp/ss.apk
$size = (Get-Item $APK).Length
& $ADB shell "cat /data/local/tmp/ss.apk | pm install -t -r -S $size"
```

### 启用 AccessibilityService（Root）
```powershell
$SVC = "info.dvkr.screenstream.dev/info.dvkr.screenstream.input.InputService"
$cur = & $ADB shell "settings get secure enabled_accessibility_services"
if ($cur -notlike "*$SVC*") {
    & $ADB shell "settings put secure enabled_accessibility_services `"$cur`:$SVC`""
    & $ADB shell "settings put secure accessibility_enabled 1"
}
```

### 启动 + 动态端口转发
```powershell
& $ADB shell am start -n info.dvkr.screenstream.dev/info.dvkr.screenstream.SingleActivity
# 探测手机实际监听端口并转发（端口因设备配置不同而异）
$ports = & $ADB shell "netstat -tlnp 2>/dev/null" | Select-String ':::80\d{2}' | ForEach-Object { if ($_ -match ':::?(80\d{2})\s') { $Matches[1] } } | Sort-Object -Unique
foreach ($p in $ports) { & $ADB forward tcp:$p tcp:$p }
```

### 验证（用探测到的端口）
```powershell
foreach ($p in $ports) { curl.exe -s http://127.0.0.1:${p}/status }
```

## 已知要点
- 构建产物路径: `010-用户界面与交互_UI\build\outputs\apk\FDroid\debug\`
- `pm install -S` 字节数必须精确
- **端口不固定**：MJPEG 投屏端口因设备其他应用占用而不同（默认8081，可能是其他808x），必须动态探测
- `force-stop` 会断开 AccessibilityService，改用 `am start` 重启
- Root 设备可通过 `settings put` 自动启用 AccessibilityService
