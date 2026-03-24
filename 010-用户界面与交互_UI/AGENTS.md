# 用户界面模块 · Android应用入口 (UI / :app)

## 身份
ScreenStream Android应用入口。Jetpack Compose UI，SingleActivity架构。

## 边界
- ✅ 本模块所有文件
- 🚫 依赖所有其他模块(`:common`,`:mjpeg`,`:rtsp`,`:webrtc`,`:input`)

## 入口
- 唯一Activity: `SingleActivity.kt`
- Gradle: `:app`模块，产物`build/outputs/apk/FDroid/debug/`
- 包名: `info.dvkr.screenstream.dev`(FDroid debug)

## 铁律
1. 前台服务权限和通知渠道在此模块声明
2. 修改UI需检查关联模块是否需同步适配
