# VP99 华强北手表 — ADB命令参考

## 连接

```powershell
# VP99 ADB突破后连接 (详见 watch_breakthrough.py --guide)
adb connect 192.168.31.41:5555

# 断开
adb disconnect 192.168.31.41:5555
```

## 系统信息

```powershell
# 设备基础
adb shell getprop ro.product.model              # VP99
adb shell getprop ro.product.brand               # OEM
adb shell getprop ro.product.device               # 设备代号
adb shell getprop ro.hardware                      # Unisoc展锐

# 系统版本
adb shell getprop ro.build.version.release         # Android版本 (11/13/14)
adb shell getprop ro.build.version.sdk             # API Level (30/33/34)
adb shell getprop ro.build.display.id              # 完整固件版本号
adb shell getprop ro.build.version.security_patch  # 安全补丁日期
adb shell getprop ro.build.version.oneui           # One UI Watch版本
adb shell getprop ro.build.date                    # 编译日期

# 序列号/标识
adb shell getprop ro.serialno                      # 设备序列号
adb shell getprop ro.bootloader                    # Bootloader版本
adb shell settings get secure android_id           # Android ID

# 运行状态
adb shell uptime                                    # 运行时间
adb shell cat /proc/version                        # 内核版本
adb shell uname -a                                 # 系统信息
```

## 电池与电源

```powershell
adb shell dumpsys battery                          # 完整电池信息
# level: 电量百分比
# temperature: 温度(除以10=摄氏度)
# status: 1=未知 2=充电 3=放电 4=未充电 5=满
# health: 2=良好 3=过热 4=坏电池
# voltage: 电压(mV)

adb shell dumpsys batterystats                     # 电池统计(详细)
adb shell dumpsys deviceidle                       # 省电模式状态
```

## 存储与内存

```powershell
adb shell df -h                                    # 磁盘使用
adb shell df -h /data                              # 用户数据分区
adb shell du -sh /data/app                         # 应用占用空间
adb shell cat /proc/meminfo                        # 内存详情
adb shell dumpsys meminfo                          # 进程内存
adb shell dumpsys meminfo <package>                # 指定应用内存
```

## 应用管理

```powershell
# 列出应用
adb shell pm list packages                         # 所有包
adb shell pm list packages -s                      # 系统应用
adb shell pm list packages -3                      # 第三方应用
adb shell pm list packages -f                      # 包含APK路径
adb shell pm list packages | findstr samsung       # 过滤Samsung应用
adb shell pm list packages | findstr google        # 过滤Google应用

# 应用信息
adb shell dumpsys package <package>                # 包完整信息
adb shell pm dump <package> | findstr version      # 版本信息
adb shell pm path <package>                        # APK路径

# 安装/卸载
adb install app.apk                                # 安装
adb install -r app.apk                             # 覆盖安装
adb uninstall <package>                            # 卸载
adb shell pm disable-user --user 0 <package>       # 禁用(不卸载)
adb shell pm enable <package>                      # 启用

# 清除数据
adb shell pm clear <package>                       # 清除应用数据
adb shell am force-stop <package>                  # 强制停止

# 提取APK
adb shell pm path <package>                        # 获取路径
adb pull /data/app/<package>/base.apk              # 拉取APK
```

## Activity与Service

```powershell
# 当前Activity
adb shell dumpsys activity activities | findstr "mResumedActivity"
adb shell dumpsys activity top                     # 顶部Activity详情

# 启动应用
adb shell am start -n <package>/<activity>
adb shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n <package>/<activity>

# 启动设置
adb shell am start -a android.settings.SETTINGS                      # 主设置
adb shell am start -a android.settings.BLUETOOTH_SETTINGS             # 蓝牙
adb shell am start -a android.settings.WIFI_SETTINGS                  # WiFi
adb shell am start -a android.settings.APPLICATION_SETTINGS           # 应用
adb shell am start -a android.settings.ACCESSIBILITY_SETTINGS         # 无障碍
adb shell am start -a android.settings.APPLICATION_DEVELOPMENT_SETTINGS   # 开发者选项(VP99)

# 服务
adb shell dumpsys activity services                # 运行中的服务
adb shell dumpsys activity services <package>      # 指定应用服务
```

## 传感器

```powershell
adb shell dumpsys sensorservice                    # 所有传感器信息
adb shell dumpsys sensorservice | findstr "name"   # 传感器名称列表

# VP99传感器待ADB确认
```

## 屏幕与显示

```powershell
adb shell wm size                                  # 屏幕分辨率(VP99: 480x576)
adb shell wm density                               # 屏幕密度
adb shell screencap /sdcard/screen.png             # 截屏
adb pull /sdcard/screen.png .                      # 拉取截屏
adb shell screenrecord /sdcard/record.mp4          # 录屏(最长180秒)
adb shell input keyevent KEYCODE_WAKEUP            # 唤醒屏幕
adb shell input keyevent KEYCODE_SLEEP             # 熄屏
```

## 输入控制

```powershell
# 按键
adb shell input keyevent KEYCODE_HOME              # Home键
adb shell input keyevent KEYCODE_BACK              # 返回键
adb shell input keyevent KEYCODE_POWER             # 电源键
adb shell input keyevent KEYCODE_WAKEUP            # 唤醒
adb shell input keyevent KEYCODE_VOLUME_UP         # 音量+
adb shell input keyevent KEYCODE_VOLUME_DOWN       # 音量-

# 触控
adb shell input tap 240 288                        # 点击屏幕中心(VP99: 480x576)
adb shell input swipe 50 288 430 288 300           # 左→右滑动
adb shell input swipe 430 288 50 288 300           # 右→左滑动
adb shell input swipe 240 50 240 526 300           # 上→下滑动
adb shell input swipe 240 526 240 50 300           # 下→上滑动
adb shell input text "hello"                       # 输入文本

```

## 网络

```powershell
adb shell ip addr show wlan0                       # WiFi IP
adb shell dumpsys wifi                             # WiFi详细状态
adb shell dumpsys bluetooth_manager                # 蓝牙状态 (VP99 BT MAC: 85:78:11:18:42:22)
adb shell dumpsys connectivity                     # 网络连接状态
adb shell dumpsys nfc                              # NFC状态
adb shell ping -c 3 google.com                     # 网络连通性
```

## VP99专用

```powershell
# 授权MacroDroid (ADB连接后首要)
adb shell pm grant com.arlosoft.macrodroid android.permission.WRITE_SECURE_SETTINGS

# 启动DroidVNC-NG
adb shell am start -n net.christianbeier.droidvnc_ng/.MainActivity

# 充电时屏幕常亮
adb shell settings put global stay_on_while_plugged_in 3

# 持久化WiFi ADB
adb shell setprop service.adb.tcp.port 5555
```

## 性能调试

```powershell
adb shell dumpsys cpuinfo                          # CPU使用率
adb shell top -n 1                                 # 进程列表
adb shell dumpsys gfxinfo <package>                # 渲染性能
adb shell dumpsys procstats                        # 进程统计
adb logcat -b events                               # 系统事件日志
adb bugreport > bugreport.zip                      # 完整Bug报告
```

## 文件操作

```powershell
adb push local_file /sdcard/                       # 推送文件到手表
adb pull /sdcard/remote_file .                     # 拉取文件到PC
adb shell ls /sdcard/                              # 列出文件
adb shell rm /sdcard/temp_file                     # 删除文件
```

## 开发者选项

```powershell
# 窗口动画缩放
adb shell settings put global window_animation_scale 0.5
adb shell settings put global transition_animation_scale 0.5
adb shell settings put global animator_duration_scale 0.5

# 保持唤醒(充电时)
adb shell settings put global stay_on_while_plugged_in 3

# GPU渲染
adb shell setprop debug.hwui.overdraw show
```
