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

## 对话结束选项

> 任务完成后调用 `ask_user_question`，从下表选 4 个最贴合的：

| label | description |
|-------|-------------|
| 装手机看效果 | 编译安装到手机，确认界面改动生效 |
| 继续打磨界面 | 优化组件的视觉和交互细节 |
| 检查关联影响 | 确认其他模块是否需要同步适配 |
| 收工提交 | 记录成果 + git commit |
