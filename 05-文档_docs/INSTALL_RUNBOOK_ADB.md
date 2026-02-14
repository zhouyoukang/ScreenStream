# ScreenStream_v2 手机更新/安装一条龙（ADB Runbook）

> 目标：用最少命令 + 可控输出完成：安装 APK → 启动 App → 通过 ADB 验证版本/前台/端口（若服务未启动给出最小人工步骤）。

## 0. 约束（防卡顿）

- 每次只跑 3-6 条短命令。
- 禁止一次性长脚本/循环/大段管道输出。
- Windows 下 HTTP 探测必须使用 `curl.exe`。

## 1. 固定信息

- 设备序列号（示例）：`158377ff`
- dev 包名：`info.dvkr.screenstream.dev`
- 主线包名（如需）：`info.dvkr.screenstream`
- 主 Activity（示例）：`info.dvkr.screenstream.SingleActivity`

## 2. 安装（覆盖安装，必要时卸载重装）

### 2.1 证据：设备在线

```powershell
$serial='158377ff'
adb -s $serial get-state
adb devices
```

### 2.2 安装 APK（例：现成 dev APK）

把 `$apk` 换成你要安装的 APK 路径。

```powershell
$serial='158377ff'
$apk='e:\github\AIOT\ScreenStream_v2\管理\00-归档\发布产物_releases\ScreenStream-FDroid-debug.apk'
adb -s $serial install -r "$apk"
```

若提示签名/冲突等错误，再执行（会清数据）：

```powershell
$serial='158377ff'
$pkg='info.dvkr.screenstream.dev'
adb -s $serial uninstall $pkg
adb -s $serial install "$apk"
```

## 3. 启动与版本验收

```powershell
$serial='158377ff'
$pkg='info.dvkr.screenstream.dev'

adb -s $serial shell am start -n "$pkg/info.dvkr.screenstream.SingleActivity"
adb -s $serial shell dumpsys package $pkg | findstr /R /C:"versionName" /C:"versionCode"
adb -s $serial shell dumpsys window | findstr /I mCurrentFocus
adb -s $serial shell pidof $pkg
```

## 4. 端口/服务是否启动（8080/8084）

说明：ScreenStream 的 HTTP 服务通常只有在你在 App 内点击“开始投屏/Start”并通过系统录屏授权后才会真正监听端口。

### 4.1 证据：是否监听 8080/8084

- 8080 十六进制端口：`1F90`
- 8084 十六进制端口：`1F94`

```powershell
$serial='158377ff'

# 8080
$r8080 = (adb -s $serial shell cat /proc/net/tcp 2>$null | findstr /I ":1F90")
if(-not $r8080){'NO_LISTEN_8080'} else { $r8080 | Select-Object -First 1 }

# 8084
$r8084 = (adb -s $serial shell cat /proc/net/tcp 2>$null | findstr /I ":1F94")
if(-not $r8084){'NO_LISTEN_8084'} else { $r8084 | Select-Object -First 1 }
```

### 4.2 从 PC 探测（adb forward + curl.exe）

```powershell
$serial='158377ff'

adb -s $serial forward tcp:18080 tcp:8080
adb -s $serial forward tcp:18084 tcp:8084

curl.exe -sS -I --max-time 3 http://127.0.0.1:18080/ | Select-Object -First 12
curl.exe -sS --max-time 3 http://127.0.0.1:18084/status | Select-Object -First 20

adb -s $serial forward --remove tcp:18080
adb -s $serial forward --remove tcp:18084
```

## 5. 输入控制（无障碍）验收

```powershell
$serial='158377ff'
adb -s $serial shell settings get secure enabled_accessibility_services
```

若输出中包含：

- `info.dvkr.screenstream.dev/info.dvkr.screenstream.input.InputService`

说明无障碍服务已启用。

## 6. 最小人工步骤（无法 100% 全自动的部分）

由于 Android 安全机制，以下动作通常需要你在手机上点一次：

1. 打开 App。
2. 点击“开始投屏/Start”（或同义按钮）。
3. 系统弹出“屏幕录制/投屏授权（MediaProjection）”对话框时点“允许”。

完成后再回到第 4 节重跑端口监听/探测即可。

## 7. 可选：从源码构建 APK（需要 JDK17 + Android SDK）

> 本节会写入 `build/` 并可能触发 Gradle 下载依赖。只有在你确认本机构建环境可用时才执行。

```powershell
# 例：构建 FDroid Debug
./gradlew :app:assembleFDroidDebug
```

产物路径通常在 `010-用户界面与交互_UI/build/outputs/apk/...` 下（按 flavor/variant 不同而变化）。
