---
name: skill-ssv2-merge-plan
description: 以 ScreenStream_v2 为主线，生成并维护 Quest/上游差异的文件级合并与归档清单
metadata: {"aiot":{"risk":"medium","needs_user_confirm":false}}
---

## 触发条件（triggers）

- 需要把 `ScreenStream_Quest` 或上游 repo 的能力合入 v2，但不希望产生第二条代码线。

## 目标（goal）

- 输出/维护 1 份“文件级差异登记表”，并把每条差异绑定到入口与验收。

## 输入（inputs）

- 差异来源目录（默认：`ScreenStream_Quest/`）
- 合并目标目录（固定：`ScreenStream_v2/`）

## refs（权威入口）

- docs 权威入口：`ScreenStream_v2/docs/README.md`
- 合并/归档清单：`ScreenStream_v2/docs/MERGE_ARCHIVE_CHECKLIST.md`

## 护栏（guardrails）

- 禁止：为 Quest 维护独立分支作为长期方案。
- 禁止：直接删除历史文件（除非你明确要求）。

## 步骤（steps）

1. 证据定位：对照目录与入口
2. 差异登记：追加到 `docs/MERGE_ARCHIVE_CHECKLIST.md`
3. 方案：开关/配置/设备判定（必要时补 ADR）
4. 实现：最小改动合入
5. 验收：按差异条目逐项验证
6. 归档：更新 STATUS 与清单状态

## 输出与验收（outputs）

- 产出文件：
  - `docs/MERGE_ARCHIVE_CHECKLIST.md`
- 验收标准：
  - 任意一条差异都能从清单定位到：代码入口 + 配置入口 + 文档入口 + 验收方式
