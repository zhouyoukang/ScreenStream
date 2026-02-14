# ScreenStream_v2 数据管理（DATA）

> 目的：把“数据/配置/日志/资产/运行时状态”放到可追溯的管理结构中，避免散落与重复。

## 0) 数据分类（你关心的“各方面数据管理”）

- **配置数据（Settings）**：端口、开关、质量参数、Pin/权限相关。
- **运行时状态（Runtime State）**：连接状态、是否 streaming、输入是否连接、当前网络接口。
- **日志与诊断数据（Logs/Diagnostics）**：XLog、崩溃信息、调试输出。
- **静态资产（Assets）**：Web UI（`index.html`、`jmuxer.min.js` 等），图标，证书容器（如有）。
- **本地敏感数据（Secrets）**：keystore、证书、私钥、`.env`（必须 gitignore）。

## 1) 配置入口（权威）

- Input 配置：`input/.../settings/InputSettings.kt`
  - 关键项：`apiPort`、`autoStartHttp`、`inputEnabled`、`requirePin` 等
- MJPEG 配置：模块内 Settings（以代码为准）

## 2) 静态资产入口

- MJPEG Web UI：`mjpeg/src/main/assets/index.html`
- JS 依赖：`mjpeg/src/main/assets/jmuxer.min.js`

## 3) 日志与证据收集（原则）

- 任何“健康/可用/不可用”的判断必须落到：
  - 端口监听证据
  - 关键日志片段
  - 可复现步骤

## 4) 护栏（必须遵守）

- 敏感文件不得提交：keystore/证书/私钥/`.env`（以 `.gitignore` 为准）。
- 配置变更影响端口/入口/鉴权时必须 ADR。
