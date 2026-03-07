# V3 RayNeo SDK for Android

> **Note**: This document was recovered from the browser snapshot as the original `开发文档.md` was empty.

## 1. 概述
### 1.1 V3特性介绍
RayNeo V3 是一款AI眼镜，它内含一个完整的Android系统（Android 12）。开发者开发的APK接入SDK后，可直接安装到眼镜上运行。
与一般手机端App开发相比，主要有以下不同：
1. **屏幕显示**： V3没有屏幕显示，用户无法直接看到眼镜系统显示的内容，需通过音频或LED提示用户。
2. **事件响应**：V3眼镜镜腿触控板（TP）只支持一维坐标（X轴），无法响应Y轴。SDK会将触摸事件映射到系统及应用中。

### 1.2 前置准备
1. **开发版本眼镜**：需刷入开发版ROM（不含C端功能，如AI助手等），可通过销售渠道获取。
2. **专用ADB夹具**：普通USB线无法传输数据，必须使用专用磁吸ADB夹具连接。

## 2. 文件下载
- **SDK**: `MarsAndroidSDK-v1.0.0-*.aar`
- **Sample**: `marsandroidsample.zip`
- **Tools**: SDK及相关工具请联系官方或者在飞书文档下载。

## 3. 快速开始
### 3.1 引入依赖
将AAR文件放入libs目录，并在 `build.gradle` 中添加依赖：
```gradle
implementation fileTree(dir: 'libs', include: ['*.aar'])
```

### 3.2 初始化SDK
在 `Application` 或 `Activity` 的 `onCreate` 中初始化：
```kotlin
// 示例代码，具体参考demo
RayNeoSDK.init(context)
```

## 4. 能力介绍 & API
### 4.1 触摸事件 (TP)
- 支持单点触控、滑动（左右）、长按等。
- **TP音效**：SDK提供默认音效反馈，开发者也可自定义。

### 4.2 焦点管理 (Focus)
由于无屏幕，焦点通常通过音频焦点或逻辑焦点管理，确保按键事件分发正确。

### 4.3 ActionButton
眼镜上的实体按键，可用于确认、唤醒等操作。

### 4.4 音频开发
- 标准Android AudioTrack/MediaPlayer开发。
- 建议使用TTS进行交互反馈。

### 4.5 Camera LED (外侧LED)
- 可控制拍摄指示灯，用于隐私提示或状态显示。

### 4.6 佩戴检测
- 监听用户佩戴状态（摘下/戴上），用于暂停/恢复业务。

## 5. 系统签名能力
以下功能需要系统签名权限（`android:sharedUserId="android.uid.system"`）：

### 5.1 WiFi配网
- **扫码配网**：通过摄像头识别二维码进行配网。

### 5.2 静默安装
- 配合 `SilentInstaller.kt` 使用。
- Android 12+ 需使用 `PackageInstaller` 新API。

### 5.3 内侧LED
- 控制镜腿内侧指示灯，仅用户可见。

### 5.4 防止休眠
- 保持系统唤醒状态，避免后台杀活。

## 6. 开发调试工具
- 使用ADB夹具连接PC进行Logcat查看和APK安装。
- `adb install` / `adb shell` 正常使用。

## 7. FAQ
1. **语音助手唤醒**：如何接收“小雷小雷”通知？（需参考Speech SDK）
2. **开机自启动**：配置 `BOOT_COMPLETED` 广播。
3. **ADB夹具使用**：确保触点接触良好，指示灯亮起。
