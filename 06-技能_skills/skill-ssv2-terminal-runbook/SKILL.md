# skill-ssv2-terminal-runbook

## 触发条件（什么时候用）

- 你需要在 IDE/终端里推进排查、对比、构建，但不想被“中途补命令/反复确认/高风险误执行”拖慢。
- 你需要把本轮终端推进固化成可复用的命令组（证据包）。

## 目标（要产出什么）

- 形成一次性可执行的“命令组”（含目的/预期输出/风险等级）。
- 输出可复查的证据包：命令原文 + 关键输出 + 对应文件路径。

## Refs（权威入口）

- `ScreenStream_v2/docs/TERMINAL_RUNBOOK.md`
- `ScreenStream_v2/docs/PROCESS.md`

## 护栏（必须遵守）

- 命令必须成组提交：一次性给出本轮需要的全部命令（含目的/预期输出/风险等级）。
- 默认只自动执行低风险（只读）命令。
- 任何可能写磁盘/改状态/联网/安装依赖/杀进程/改端口/改签名 的命令：必须在同一组里一次性列出，并等待一次确认后再执行。
- 禁止“执行过程中追加零散命令”；发现缺命令必须重新汇总成下一组再提交。

## 步骤

### Step 1：定义本轮目标与证据需求

- 写清楚：要回答的问题是什么（例如：Quest vs v2 某模块差异、某端口冲突、某构建失败原因）。
- 明确证据类型：
  - 文件路径证据（哪个模块/哪个文件/哪段配置）
  - 终端输出证据（diff/lint/构建任务输出）

### Step 2：组装“只读命令组”（低风险）

- Git 基本证据：
  - `git status`
  - `git diff`
- 模块差异统计（只对比 `src`，避免 Windows 下扫描 `build/intermediates` 卡住）：
  - `git diff --no-index --stat -- ScreenStream_Quest/app/src ScreenStream_v2/app/src`
  - `git diff --no-index --stat -- ScreenStream_Quest/mjpeg/src ScreenStream_v2/mjpeg/src`
  - `git diff --no-index --stat -- ScreenStream_Quest/input/src ScreenStream_v2/input/src`
- Gradle 任务与依赖（只读）：
  - `gradlew tasks`
  - `gradlew :app:tasks`

### Step 3：如需构建/验收，组装“中风险命令组”（需确认）

- 说明：构建会写入 `build/`，属于中风险；必须一次性列全。
- 示例：
  - `gradlew :ScreenStream_v2:app:assembleDebug`
  - `gradlew :ScreenStream_v2:app:lint`

### Step 4：输出与归档

- 保留：
  - 本轮命令组原文
  - 关键输出（错误栈/端口占用/任务失败原因）
  - 对应的文件路径证据
- 将结论收敛回：
  - `docs/STATUS.md`（当前状态与下一步）
  - `docs/MERGE_ARCHIVE_CHECKLIST.md`（差异条目，必须带证据）
  - 必要时新增 ADR（端口/入口/鉴权等架构决策）

## 输出与验收

- 你能在不追加命令的情况下复现同一轮证据收集。
- 任何高风险命令在执行前都经过一次性确认。
- 结论可追溯到具体文件路径与终端输出。
