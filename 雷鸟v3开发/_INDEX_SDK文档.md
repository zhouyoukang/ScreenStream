# AI--AR — 增强现实（雷鸟V3开发域）

> **优先级**: ⭐⭐⭐
> **本质**: 用AI打通人的五感 → 以眼镜为载体，世界即界面，感知即计算，至于「无感」
> **SDK来源**: V3 RayNeo SDK for Android（飞书原文，2026-02-12最新版，B端专用）

---

## 硬件核心：雷鸟V3 AI拍摄眼镜

### 五感硬件映射
| 感官 | 硬件 | 规格 |
|---|---|---|
| 👁️ 视觉 | Sony IMX681摄像头 | 1200万像素，等效16mm超广角，4K照片，双ISP |
| 👂 听觉 | 3× MEMS麦克风 + 双镜腿扬声器 | 镜框1个 + 左右镜腿各1个，AW88166音频功放 |
| 🤚 触觉 | **右镜腿**触控板（TP） | **仅支持X轴一维坐标**，Y轴为固定值 |
| 🧠 空间感 | 陀螺仪（IMU） | 头部朝向/姿态/运动检测 |
| 🌍 环境感 | 环境光传感器 | 自动亮度适配，防误触遮挡检测 |

### 处理器与连接
- **CPU/AI**: 高通骁龙AR1（4nm）+ Hexagon NPU + 双ISP
- **系统**: **Android 12**（APK直接安装运行，无屏幕显示）
- **WiFi**: 高通WCN7851 | **电池**: 右镜腿159mAh，TI BQ25600

---

## ADB连接（已通过专用夹具 ✅ 2026-02-26）

```
841571AC688C360  device  product:RayNeoV3 model:XRGF50 device:Mars
```

**userdebug 开发版ROM ✅ | 电量93% ✅ | AISpeech已内置 ✅**

### 快速命令
```powershell
# 五感引擎（E:\道\AI--AR\雷鸟V3\rayneo_五感.py）
python rayneo_五感.py              # 状态报告
python rayneo_五感.py --run        # 启动完整五感监听
python rayneo_五感.py --speak "文字"  # 语音播报到眼镜扬声器
python rayneo_五感.py --photo      # 触发拍照
python rayneo_五感.py --battery    # 查看电量

# 直接ADB
D:\scrcpy\scrcpy-win64-v3.1\adb.exe -s 841571AC688C360 devices -l
D:\scrcpy\scrcpy-win64-v3.1\adb.exe -s 841571AC688C360 shell pm list packages
D:\scrcpy\scrcpy-win64-v3.1\adb.exe -s 841571AC688C360 install -r app.apk
```

### 设备规格（实测确认）
- 序列号: 841571AC688C360 | ROM: RayNeoV3-userdebug SKQ1.240815.001 3D7I
- 输入设备: cyttsp5_mt(event3) TP + gpio-keys(event1) ActionButton + hall(event0) 佩戴
- 传感器: STMicro lsm6dsr 加速度计+陀螺仪 415Hz | 光传感器 stk_stk3x3x
- TTS链路: pyttsx3(PC) → WAV推送 → am VIEW intent → 扬声器 ✅
- AISpeech: com.rayneo.aispeech + RayNeoVoiceInteractionService ✅

---

## SDK接入完整文档（MarsAndroidSDK-v1.0.1）

### 下载文件清单
| 文件 | 大小 | 用途 |
|---|---|---|
| `MarsAndroidSDK-v1.0.1-20260112112529_a7c9bf89.aar` | 162KB | ⭐ 核心SDK |
| `MarsAndroidSDKSample.zip` | 344KB | 示例代码 |
| `v3_mobile_app.apk` | 49.5MB | 配套手机App |
| `V3MobileApp.zip` | 136KB | 手机App源码 |
| `SilentInstaller.kt` | 2.86KB | 静默安装工具 |
| `MarsSpeech-V2025.06.27.16-*.apk` | 15.3MB | 语音助手（"小雷小雷"） |

### 3.1 引入依赖（AAR接入）
```groovy
// 1. 将 .aar 放入主模块 libs/ 目录
// 2. build.gradle 添加：
implementation(fileTree("libs"))
implementation 'androidx.lifecycle:lifecycle-runtime-ktx:2.5.1'
implementation 'androidx.fragment:fragment-ktx:1.5.3'
implementation 'androidx.core:core-ktx:1.7.0'
implementation 'androidx.appcompat:appcompat:1.3.0'
implementation 'com.google.android.material:material:1.8.0'
// 注：SDK基于Kotlin编写，需添加Kotlin依赖
```

### 3.2 初始化SDK
```kotlin
class MarsDemoApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        MarsSDK.init(this)   // Application中初始化，仅此一行
    }
}
```

---

## 核心API速查表

### 4.1 触摸事件 & 事件响应
> 仅右镜腿TP，**一维（X轴）**，识别：单击/双击/三击/长按/前滑/后滑

```kotlin
// 继承 BaseEventActivity → 获得 TempleAction Flow事件流
class MyActivity : BaseEventActivity() {
    private fun initEvent() {
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.RESUMED) {
                templeActionViewModel.state.collect { action ->
                    when (action) {
                        is TempleAction.Click       -> { /* 单击 */ }
                        is TempleAction.DoubleClick -> { /* 双击 */ }
                        is TempleAction.TripleClick -> { /* 三击 */ }
                        is TempleAction.LongClick   -> { /* 长按 */ }
                        else -> Unit
                    }
                }
            }
        }
    }
}
// ⚠️ 一个页面Button不超过4个，建议用TextView代替Button
```

### 4.2 焦点管理（多视图场景）
```kotlin
// FocusHolder → 管理同层级焦点位
// FocusInfo   → 单个焦点位（绑定View + eventHandler + focusChangeHandler）
// FixPosFocusTracker → 最终对接TempleAction事件流

val focusHolder = FocusHolder(false)
focusHolder.addFocusTarget(
    FocusInfo(btn1, eventHandler = { action -> /* 处理事件 */ }, focusChangeHandler = { hasFocus -> }),
    FocusInfo(btn2, eventHandler = { action -> /* 处理事件 */ }, focusChangeHandler = { hasFocus -> })
)
focusHolder.currentFocus(btn1)   // 设置默认焦点
fixPosFocusTracker = FixPosFocusTracker(focusHolder).apply { focusObj.hasFocus = true }
// FixPosFocusTracker本身可作为FocusInfo的target → 层层嵌套应对复杂页面
```

### 4.3 ActionButton（右镜腿物理按键）
```kotlin
// ReceiverKeyEventManager — 短按onClick / 长按onLongClick
private lateinit var receiverKeyEventManager: ReceiverKeyEventManager
// 初始化与开启监听（参考Sample代码）
```

### 4.4 音频开发
```kotlin
object AudioUtil {
    private var audioManager: AudioManager? = null
    fun init(context: Context) {
        audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    }
    fun setAudioParameters(parameter: String) {
        audioManager?.setParameters("audio_source_record=$parameter")
    }
}
```

### 4.5 Camera LED（外侧LED，合规必须）
```xml
<!-- AndroidManifest.xml -->
<uses-permission android:name="android.permission.CONTROL_DEVICE_LIGHTS" />
```
```kotlin
LedBroadcastUtils.notifyCapture()     // 开启摄像头时点亮LED
LedBroadcastUtils.notifyCaptureEnd()  // 关闭摄像头时熄灭LED
// 工信部合规要求：摄像头开启时必须有明显提示
```

### 4.6 佩戴检测
```kotlin
SystemUtil.deviceWearingState.onEach { wearingState ->
    // wearingState = true/false
}.launchIn(MainScope())
```

---

## 系统级能力（需系统签名）

### 5. 系统签名（生成 platform.jks）
```bash
openssl pkcs8 -inform DER -nocrypt -in platform.pk8 -out platform_key.pem
openssl pkcs12 -export -in platform.x509.pem -inkey platform_key.pem \
    -out platform.p12 -name platform -password pass:android
keytool -importkeystore -deststorepass android -destkeypass android \
    -destkeystore platform.jks -srckeystore platform.p12 \
    -srcstoretype PKCS12 -srcstorepass android -alias platform
```

### 5.1 WiFi配网
```xml
<!-- AndroidManifest.xml 需要系统uid -->
<manifest android:sharedUserId="android.uid.system">
<uses-permission android:name="android.permission.CHANGE_WIFI_STATE" />
<uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
```
```kotlin
val wifiManager = getSystemService(Context.WIFI_SERVICE) as WifiManager
if (!wifiManager.isWifiEnabled) wifiManager.isWifiEnabled = true
connectToWifi(wifiManager, "wifi名称", "wifi密码")
```

### 5.4 防止WiFi休眠（文件传输必用）
```xml
<uses-permission android:name="android.permission.WAKE_LOCK" />
```
```kotlin
RayneoSuspendManager.setWifiKeepOnStateByUserWithTimer(true)   // 开始任务
// ... 执行网络传输 ...
RayneoSuspendManager.setWifiKeepOnStateByUserWithTimer(false)  // ‼️ 完成后必须关闭，否则耗电增加
```

---

## FAQ

### Q1: 接收语音助手"小雷小雷"唤醒通知
```kotlin
// 步骤1: 安装 MarsSpeech APK → 设置→应用→默认应用→数字助理→选中"marsspeech"
// 步骤2: 注册广播接收器
val filter = IntentFilter("com.rayneo.aispeech.wakeup")
registerReceiver(object : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        // 收到唤醒事件
    }
}, filter)
// 记得 onDestroy 中 unregisterReceiver
```

### Q2: 开机自启动
使用 `BOOT_COMPLETED` 广播，配合系统签名

### Q3: ADB夹具
充电线不能传输调试数据，必须使用**专用ADB调试夹具**（联系雷鸟销售获取）

---

## 五感开发路线（AI五感 × 眼镜硬件）

```
视觉 → 摄像头帧 → CV/通义Vision → 场景识别 → 语音播报（无需看屏幕）
听觉 → 3麦降噪 → "小雷小雷"唤醒 → 通义理解 → TTS扬声器（开口即交互）
触觉 → 右镜腿TP(X轴) → TempleAction → 单击/滑动/长按（轻触无需掏机）
空间 → IMU姿态 → 头部朝向=意图：低头=拍照，抬头=提问，转头=翻页
环境 → 光传感器 → 室内/室外自适应 → 感知无间断
```

## 平衡策略
- **眼镜** = 感知终端（采集五感，无显示屏）
- **云端（通义）** = 理解推理（1.3s响应）
- **本机（台式机）** = 开发/调试/中转Agent
- **道之平衡**：硬件轻量 → 计算重云端 → 体验至无感

## AR与VR的边界
| 属于 AI--AR | 属于 AI--VR | 公共工具 |
|---|---|---|
| 雷鸟V3 SDK开发 | Quest 3沉浸式VR | Unity编译 |
| MarsAndroidSDK接入 | Oculus驱动/生态 | aiovr.xyz WebXR |
| 摄像头+语音+触控 | HA-卡片(3.5GB) | ADB/scrcpy调试 |
| 头部姿态交互 | 完全沉浸体验 | ScreenStream投屏 |

---

## 解惑（问/惑/祸）
| 问题 | 解答 |
|---|---|
| **飞书SDK文档内容？** | ✅ 已读取全文（2026-02-26），B端专用，完整SDK文档已汇入此文件 |
| **ADB连接的是手机不是眼镜？** | ✅ 已确认：158377ff=OnePlus NE2210 手机。眼镜需专用夹具+开发版ROM才能ADB调试 |
| **无显示屏如何做AR？** | V3是AI拍摄眼镜，AR=摄像头看世界+AI理解+语音/触觉反馈，非光波导AR |
| **SDK叫什么名字？** | MarsAndroidSDK，init: `MarsSDK.init(this)` |
| **如何接收语音唤醒？** | 安装MarsSpeech APK → 监听广播 `com.rayneo.aispeech.wakeup` |
| **如何防止WiFi休眠？** | `RayneoSuspendManager.setWifiKeepOnStateByUserWithTimer(true/false)` |

---

## TODO（按优先级）
1. ⚠️ **获取专用ADB调试夹具** — 当前充电线无法ADB调试眼镜（联系雷鸟销售）
2. ⚠️ **确认ROM版本** — C端版需刷开发版ROM才能安装自研APK
3. 下载 `MarsAndroidSDK-v1.0.1.aar` 并创建Android Studio项目
4. 完成SDK接入：`MarsSDK.init(this)` → 监听 `TempleAction` 事件流
5. 开发 `雷鸟_感知_demo` APK：摄像头帧 → 通义Vision → 语音播报
6. 打通麦克风 → Whisper → 通义问答 → TTS闭环
7. IMU姿态：低头拍照/识别，抬头提问，转头翻页

---

## 本地 SDK 资产（E:\道\AI--AR\雷鸟V3\SDK\ ✅ 2026-02-26）
| 文件 | 大小 | 说明 |
| ---- | ---- | ---- |
| `MarsAndroidSDK-v1.0.1-20260112112529_a7c9bf89.aar` | 162KB | ⭐ 核心SDK，放入项目 libs/ |
| `MarsAndroidSDKSample.zip` | 344KB | 官方示例代码（含扫码配网Demo） |
| `v3_mobile_app.apk` | 49.5MB | 配套手机App（扫码配网用） |
| `V3MobileApp.zip` | 136KB | 手机App源码 |
| `SilentInstaller.kt` | 2.9KB | 静默安装工具源码 |
| `MarsSpeech-V2025.06.27.16-*.apk` | 15.3MB | 语音助手APK（"小雷小雷"） |

## 台式机资产
- **`D:\scrcpy\`** — ADB/scrcpy工具（adb.exe已验证）
- **`F:\Unity\`** — AR应用编译（APK构建）
- **`F:\oculus-go-adb-driver-2.0\`** — ADB通用驱动

---

## Agent锁
> (空=未认领。Agent认领时写入: 🔒 Agent:[对话ID] | 时间:[时间])

## 三联道（2026-02-26 ✅）

老子第四十二章：**道生一，一生二，二生三，三生万物**

| 层 | 设备 | ADB序列号 | 状态 |
|----|------|---------|------|
| 道/一 | PC 台式机 192.168.31.141 | — | ✅ 主脑 |
| 二 | OnePlus NE2210 Android 15 | 158377ff | ✅ 61% WiFi:192.168.31.40 |
| 三 | RayNeo V3 XRGF50 | 841571AC688C360 | ✅ 91% userdebug |

### 五大联动场景（万物）
| 场景 | 描述 | 触发 |
|------|------|------|
| 场景一 | 眼镜拍照→PC AI识别→眼镜TTS播报 | 眼镜单击TP |
| 场景二 | 手机屏幕→OCR摘要→眼镜播报 | 眼镜双击TP |
| 场景三 | 手机通知→眼镜音频播报 | ActionButton短按 |
| 场景四 | 眼镜手势→手机操作（翻页/主页/返回） | 眼镜前/后滑TP |
| 场景五 | 三体全景感知报告 | 眼镜长按TP / ActionButton长按 |

### 核心文件
```powershell
E:\道\AI--AR\雷鸟V3\san_lian.py          # 三联道主引擎
E:\道\AI--AR\雷鸟V3\rayneo_道.py         # 道感知层（无感度+以气听+归根）
E:\道\AI--AR\雷鸟V3\rayneo_五感.py       # 五感基础层
E:\道\AI--AR\雷鸟V3\→三联道万物.cmd      # 一键启动三体联动
E:\道\AI--AR\雷鸟V3\→启动五感引擎.cmd   # 单机眼镜五感

python san_lian.py --test      # 三体链路快速验证
python san_lian.py --sense     # 三体状态报告
python san_lian.py --scene N   # 运行场景 1~5
python san_lian.py --run       # 启动完整三体联动监听
python rayneo_道.py --run      # 眼镜单机道感知引擎
```

## 完成记录
- 2026-02-26: 飞书SDK原文阅读完成，全文汇入 _INDEX.md；ADB确认当前连接为OnePlus手机非眼镜
- 2026-02-26: ✅ 全部6个SDK资源文件从飞书下载完成，存入 `E:\道\AI--AR\雷鸟V3\SDK\`
- 2026-02-26: ✅ ADB驱动已安装（pnputil+android_winusb.inf，支持VID_18D1&PID_4EE2）
- 2026-02-26: ✅ 三联道建立：PC+NE2210+XRGF50 三体实测联通，san_lian.py全链路验证
- 2026-02-26: ✅ 老庄解AR哲学文档 + 道感知层（归根/以气听/物化/无感度）

---
*更新时间: 2026-02-26 | 来源: V3 RayNeo SDK for Android 飞书文档(官方原版) + ADB实测 + SDK全量下载*
