# ScreenStream_v2 终端执行 Runbook（TERMINAL_RUNBOOK）

> 目的：把“终端命令如何执行才不会中途停顿/反复确认/反复补命令”固化成标准模板。

## 0) 核心规则（必须遵守）

- **命令必须成组提交**：一次性给出本轮需要的全部命令（含目的/预期输出/风险等级）。
- **默认只自动执行只读命令**：例如 `git status` / `git diff` / `--version` / `gradlew tasks`。
- **高风险命令必须一次性列出并等待一次确认**：任何可能写磁盘/改状态/联网/安装依赖/杀进程/改端口/改签名 的命令。
- **禁止“执行过程中追加零散命令”**：发现缺命令时必须重新汇总成下一组命令再提交。

## 1) 风险分级（用于在命令组里标注）

- **低风险（只读）**
  - 读取文件、查看 git 状态、打印版本、列出任务
  - 典型：`git status`、`git diff`、`gradlew tasks`、`gradlew :module:dependencies`

- **中风险（写入但可回滚）**
  - 生成构建产物、写入缓存、修改本地状态
  - 典型：`gradlew assembleDebug`、`gradlew lint`、写入 `build/`、生成报告

- **高风险（可能不可逆/影响外部环境）**
  - 联网下载/安装依赖、修改端口、杀进程、修改签名/keystore、写入敏感配置
  - 典型：`gradlew publish`、脚本安装 SDK/依赖、修改系统配置

## 2) ScreenStream_v2 常用只读命令组（模板）

> 说明：以下命令都属于低风险（只读），可用于一次性拿到“证据包”。

- Git 基本证据：
  - `git status`
  - `git diff`

- 模块差异统计（避免被 build 产物卡住）：
  - **只对比 src 目录**：
    - `git diff --no-index --stat -- ScreenStream_Quest/app/src ScreenStream_v2/app/src`
    - `git diff --no-index --stat -- ScreenStream_Quest/mjpeg/src ScreenStream_v2/mjpeg/src`
    - `git diff --no-index --stat -- ScreenStream_Quest/input/src ScreenStream_v2/input/src`
  - **不要**对比整个模块根目录（会扫到 `build/intermediates`，Windows 下容易 “Could not access”）：
    - 不推荐：`git diff --no-index --stat -- ScreenStream_Quest ScreenStream_v2`

- Gradle 任务与依赖（只读）：
  - `gradlew tasks`
  - `gradlew :app:tasks`

## 3) 构建/验收命令组（需要确认后执行）

> 说明：构建会写入 `build/`，属于中风险；应当在同一组命令里一次性列出。

- 示例（中风险，需确认）：
  - `gradlew :ScreenStream_v2:app:assembleDebug`
  - `gradlew :ScreenStream_v2:app:lint`

## 4) 输出要求（避免“做了但不可复查”）

每次终端推进至少保留：

- 本轮命令组原文
- 关键输出（错误栈/端口占用/任务失败原因）
- 对应的文件路径证据（在哪个模块/哪个文件）

## 5) 与 docs/skills 的关系

- 权威入口：`docs/README.md`
- 标准流程：`docs/PROCESS.md`
- Skills：`skills/`（终端 runbook 也应对应一个可复用 skill）
