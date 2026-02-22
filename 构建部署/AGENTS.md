# 构建部署

> **P1 ScreenStream 构建系统** — Gradle 构建配置 + ADB 部署脚本 + API 验证。

## 项目边界

| 维度 | 值 |
|------|-----|
| **目录** | `构建部署/` |
| **语言** | Gradle KTS + PowerShell |
| **所属** | P1 ScreenStream Android |

## 可修改文件

```
构建部署/
├── dev-deploy.ps1             ← 一键部署（编译→推送→安装→启动→验证）
├── api-verify.ps1             ← API 端点全量验证
├── s33-verify.ps1             ← S33 文件管理器专项验证
├── 010-应用构建_AppBuild      ← :app 模块 Gradle 配置
├── 020-基础设施构建_CommonBuild
├── 030-MJPEG构建_MjpegBuild
├── 040-RTSP构建_RtspBuild
├── 050-WebRTC构建_WebRtcBuild
├── 060-输入构建_InputBuild
└── android-sdk/               ← 本地 Android SDK（.gitignore 已排除）
```

## 禁止修改

- `智能家居/` `手机操控库/` `远程桌面/` 及所有外部项目

## 硬约束

- **构建串行**：同时只有 1 个 Agent 可执行 `gradlew` 命令
- **android-sdk/** 是 1GB 本地 SDK，禁止提交到 git
- 修改 Gradle 配置后必须验证编译通过
