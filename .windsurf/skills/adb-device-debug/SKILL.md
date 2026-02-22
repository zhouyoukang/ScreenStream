---
name: adb-device-debug
description: 调试Android设备连接和ADB问题。当设备连接失败、adb命令无响应、或需要查看设备日志时触发。
---

## ADB 路径
```
e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe
```

## 诊断流程

### 1. 设备连接检查
```powershell
& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" devices
```

### 2. 应用状态检查
```powershell
# 检查应用是否安装
& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" shell pm list packages | findstr screenstream

# 检查应用是否运行
& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" shell ps | findstr screenstream
```

### 3. 查看应用日志（限制输出量）
```powershell
& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" logcat -d -t 50 --pid=$(& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" shell pidof info.dvkr.screenstream.dev)
```

### 4. AccessibilityService 状态
```powershell
& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" shell settings get secure enabled_accessibility_services | findstr screenstream
```

### 5. 网络连通性
```powershell
# 获取设备IP
& "e:\github\AIOT\ScreenStream_v2\构建部署\android-sdk\platform-tools\adb.exe" shell ip route | findstr "src"
```

## 常见问题
- **设备离线**: `adb kill-server` 然后 `adb start-server`
- **unauthorized**: 检查手机上的USB调试授权弹窗
- **多设备**: 使用 `-s <serial>` 指定设备
