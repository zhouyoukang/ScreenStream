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

> 任务完成后，AI 必须调用 `ask_user_question` 从以下选项中选取 4 个最相关的：

| label | description |
|-------|-------------|
| 编译部署验证 | 执行 Gradle 构建→推送→安装→启动，确认修改生效 |
| 优化UI交互 | 继续改进 Compose 组件、布局或动画效果 |
| 同步关联模块 | 检查 common/mjpeg/input 等依赖模块是否需要同步修改 |
| 更新文档提交 | 更新 FEATURES.md + git commit 记录变更 |
