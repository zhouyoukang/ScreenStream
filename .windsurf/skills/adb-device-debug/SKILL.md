---
name: adb-device-debug
description: 调试Android设备连接和ADB问题。当设备连接失败、adb命令无响应、或需要查看设备日志时触发。
triggers:
  - 设备连接失败或adb devices无输出
  - adb命令返回错误或无响应
  - 需要查看设备日志定位问题
  - WiFi ADB连接/端口发现
  - OEM安全拦截（Vivo/OPPO/ColorOS）
---

## ADB 路径
```
$ADB = "e:\道\道生一\一生二\构建部署\android-sdk\platform-tools\adb.exe"
```

## 一、诊断流程（按顺序执行到第一个失败点停下）

### Step 1: 设备连接检查
```powershell
$ADB = "e:\道\道生一\一生二\构建部署\android-sdk\platform-tools\adb.exe"
& $ADB devices
```
**期望**: 至少一个 `device` 状态（非 `offline`/`unauthorized`/空）

### Step 2: 应用状态检查
```powershell
& $ADB shell pm list packages | findstr screenstream
& $ADB shell pidof info.dvkr.screenstream.dev
```

### Step 3: AccessibilityService 状态
```powershell
& $ADB shell settings get secure enabled_accessibility_services | findstr screenstream
```
**失败**: 见下方"启用无障碍"

### Step 4: 端口监听
```powershell
& $ADB shell "netstat -tlnp 2>/dev/null | grep 808"
```
**期望**: 至少 8080 或 8084 在监听

### Step 5: 端口转发 + API验证
```powershell
& $ADB forward tcp:8084 tcp:8084
curl.exe -s --connect-timeout 5 http://127.0.0.1:8084/status
```

### Step 6: 应用日志（限50行）
```powershell
& $ADB logcat -d -t 50 --pid=$(& $ADB shell pidof info.dvkr.screenstream.dev) 2>$null
```

## 二、WiFi ADB 连接

### 方式A: 无线调试端口扫描（Android 11+）
```powershell
# 1. 获取设备WiFi IP
$ip = (& $ADB shell "ip addr show wlan0" | Select-String 'inet (\d+\.\d+\.\d+\.\d+)').Matches.Groups[1].Value

# 2. 扫描无线调试端口范围（37000-47000）
$found = $null
37000..47000 | ForEach-Object {
    $r = Test-NetConnection -ComputerName $ip -Port $_ -WarningAction SilentlyContinue -InformationLevel Quiet
    if ($r) { $found = $_; break }
}

# 3. 连接
& $ADB connect "${ip}:${found}"
```

### 方式B: tcpip模式（需先USB连接）
```powershell
& $ADB tcpip 5555
$ip = (& $ADB shell "ip route" | Select-String 'src (\d+\.\d+\.\d+\.\d+)').Matches.Groups[1].Value
& $ADB connect "${ip}:5555"
# 可拔线
```

### 方式C: WiFi直连API（无需ADB forward）
ScreenStream Input API监听`0.0.0.0:8084`，WiFi可直连：
```powershell
curl.exe -s --connect-timeout 3 http://${ip}:8084/status
```

## 三、多设备处理

```powershell
# 列出所有设备
& $ADB devices -l

# 指定USB设备（用serial）
& $ADB -s 158377ff shell xxx

# 指定WiFi设备
& $ADB -s 192.168.31.40:5555 shell xxx
```

**铁律**: phone_lib.py的`_adb()`方法已内置`-s serial`多设备支持。

## 四、启用无障碍服务

### Root设备（自动）
```powershell
$SVC = "info.dvkr.screenstream.dev/info.dvkr.screenstream.input.InputService"
$cur = (& $ADB shell settings get secure enabled_accessibility_services).Trim()
if ($cur -notlike "*$SVC*") {
    $new = if ($cur -and $cur -ne "null") { "${cur}:${SVC}" } else { $SVC }
    & $ADB shell "settings put secure enabled_accessibility_services '$new'"
    & $ADB shell "settings put secure accessibility_enabled 1"
}
```

### 非Root设备
需用户在手机端：设置 → 无障碍 → ScreenStream → 开启

## 五、OEM安全拦截（实战踩坑）

| OEM | 拦截行为 | 绕过方案 |
|-----|---------|---------|
| **Vivo** | USB安装永远弹"用户拒绝权限" | 手动开"通过USB安装应用"开关 / 手动安装APK |
| **OPPO/ColorOS** | `com.oplus.securitypermission`弹窗拦截启动 | `adb shell appops set <pkg> AUTO_START allow` |
| **OPPO** | 通知正文ADB不可读 | 需AccessibilityService |
| **Samsung** | `am force-stop`禁用AccessibilityService | 用`am start`重启代替force-stop |
| **通用** | 电池优化杀后台 | `adb shell dumpsys deviceidle whitelist +<pkg>` |

### OPPO自启动授权
```powershell
& $ADB shell appops set info.dvkr.screenstream.dev AUTO_START allow
& $ADB shell appops set info.dvkr.screenstream.dev RUN_IN_BACKGROUND allow
& $ADB shell appops set info.dvkr.screenstream.dev RUN_ANY_IN_BACKGROUND allow
```

## 六、常见故障速查

| 症状 | 原因 | 解法 |
|------|------|------|
| `devices`无输出 | USB线/驱动 | 换线；安装OEM驱动 |
| `offline` | daemon异常 | `adb kill-server && adb start-server` |
| `unauthorized` | 未授权 | 检查手机上的USB调试授权弹窗 |
| 端口不通 | 防火墙/未启动 | `adb forward` 或检查`netstat` |
| API返回503 | AccessibilityService断连 | 重新启用（见上方） |
| WiFi ADB断连 | 端口变化 | 重新扫描端口（每次重启可能变） |
| `INSTALL_FAILED_ABORTED` | OEM拦截 | 见上方OEM表 |
