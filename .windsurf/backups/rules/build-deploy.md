---
trigger: model_decision
description: 当任务涉及构建APK、推送到手机、安装、启动应用、或部署相关操作时激活
---

# 构建部署规则

## 标准流程
```powershell
# 1. 编译
$env:JAVA_HOME = "C:\Program Files\Processing\app\resources\jdk"
$env:ANDROID_SDK_ROOT = "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk"
& "e:\github\AIOT\ScreenStream_v2\gradlew.bat" assembleFDroidDebug --no-configuration-cache

# 2. 推送
& "构建部署\android-sdk\platform-tools\adb.exe" push "用户界面\build\outputs\apk\FDroid\debug\app-FDroid-debug.apk" /data/local/tmp/ss.apk

# 3. 安装 (替换<size>为实际字节数)
& "构建部署\android-sdk\platform-tools\adb.exe" shell "cat /data/local/tmp/ss.apk | pm install -t -r -S <size>"

# 4. 重启应用
& "构建部署\android-sdk\platform-tools\adb.exe" shell am force-stop info.dvkr.screenstream.dev
Start-Sleep -Seconds 2
& "构建部署\android-sdk\platform-tools\adb.exe" shell am start -n info.dvkr.screenstream.dev/info.dvkr.screenstream.SingleActivity
```

## 注意事项
- 编译产物路径: `用户界面\build\outputs\apk\FDroid\debug\app-FDroid-debug.apk`
- `pm install -S` 需要精确的文件字节数
- 构建前确认设备已连接: `adb devices`
