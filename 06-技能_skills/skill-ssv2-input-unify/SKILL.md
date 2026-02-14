---
name: skill-ssv2-input-unify
description: 输入链路收敛（MJPEG HttpServer vs InputHttpServer）的证据定位→ADR→实现→验收→归档工作流
metadata: {"aiot":{"risk":"high","needs_user_confirm":false}}
---

## 触发条件（triggers）

- 发现存在双 HTTP 入口/双端口（MJPEG 与 Input 分离），导致：
  - FRP/反代配置复杂
  - 鉴权/Pin/CORS 分裂
  - 用户需要记多个 URL

## 目标（goal）

- 输出 1 份 ADR（端口/路由/鉴权/兼容策略）
- 输出 1 份实施计划（Phase-1/Phase-2）
- 输出 1 份验收清单（本地/FRP/Quest）

## 输入（inputs）

- 目标统一策略（默认：单入口/单端口）
- 是否需要兼容旧端口（默认：需要）

## refs（权威入口）

- docs 权威入口：`ScreenStream_v2/docs/README.md`
- 状态面板：`ScreenStream_v2/docs/STATUS.md`
- ADR：`ScreenStream_v2/docs/adr/ADR-20260210-input-http-entrypoints.md`
- 代码入口：
  - `ScreenStream_v2/mjpeg/src/main/java/info/dvkr/screenstream/mjpeg/internal/HttpServer.kt`
  - `ScreenStream_v2/input/src/main/java/info/dvkr/screenstream/input/InputKoinModule.kt`
  - `ScreenStream_v2/input/src/main/java/info/dvkr/screenstream/input/InputHttpServer.kt`

## 护栏（guardrails）

- 端口/入口/鉴权属于架构级决策：必须先 ADR 再改代码。
- 禁止隐式修改：构建/签名/版本策略。

## 步骤（steps）

1. 证据定位
2. 差异/根因
3. ADR
4. 实现（Phase-1）
5. 验收
6. 归档（更新 STATUS + README + 清单）

## 输出与验收（outputs）

- 产出文件：
  - `docs/adr/ADR-20260210-input-http-entrypoints.md`
  - `docs/STATUS.md`（更新进度）
- 验收标准：
  - 用户只记一个入口地址即可完成“看画面 + 输入控制”（或明确迁移路径）
