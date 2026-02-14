# 用户界面模块 (UI / :app)

## 核心职责
Android 应用入口，Jetpack Compose UI，SingleActivity 架构。

## 关键文件
- `SingleActivity.kt` — 唯一 Activity，应用入口
- Gradle: `:app` 模块，产物输出到 `build/outputs/apk/FDroid/debug/`

## 关键约束
- 包名: `info.dvkr.screenstream.dev`（FDroid debug）
- 依赖所有其他模块（`:common`, `:mjpeg`, `:rtsp`, `:webrtc`, `:input`）
- 前台服务权限和通知渠道在此模块声明
