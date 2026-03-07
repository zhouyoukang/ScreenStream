---
trigger: model_decision
description: 当任务涉及构建APK、推送到手机、安装、启动应用、或部署相关操作时激活
---

# 构建部署规则

## 标准流程
```powershell
# 1. 编译
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
$env:ANDROID_SDK_ROOT = "d:\道\道生一\一生二\090-构建与部署_Build\android-sdk"
& "d:\道\道生一\一生二\gradlew.bat" assembleFDroidDebug --no-configuration-cache

# 2. 推送
& "D:\platform-tools\adb.exe" push "010-用户界面与交互_UI\build\outputs\apk\FDroid\debug\app-FDroid-debug.apk" /data/local/tmp/ss.apk

# 3. 安装 (替换<size>为实际字节数)
& "D:\platform-tools\adb.exe" shell "cat /data/local/tmp/ss.apk | pm install -t -r -S <size>"

# 4. 重启应用
& "D:\platform-tools\adb.exe" shell am force-stop info.dvkr.screenstream.dev
Start-Sleep -Seconds 2
& "D:\platform-tools\adb.exe" shell am start -n info.dvkr.screenstream.dev/info.dvkr.screenstream.SingleActivity
```

## 注意事项
- 编译产物路径: `010-用户界面与交互_UI\build\outputs\apk\FDroid\debug\app-FDroid-debug.apk`
- `pm install -S` 需要精确的文件字节数
- 构建前确认设备已连接: `adb devices`
- **P23**: `force-stop` 会禁用 AccessibilityService，重启后必须恢复:
  ```powershell
  $current = & adb shell settings get secure enabled_accessibility_services
  & adb shell settings put secure enabled_accessibility_services "${current}:info.dvkr.screenstream.dev/info.dvkr.screenstream.input.InputService"
  ```
