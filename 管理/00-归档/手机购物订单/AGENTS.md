# AGENTS.md — 手机购物订单

## 目录用途
通过Agent操控手机采集淘宝等电商平台购物订单数据，
解析并生成结构化报告。

## 技术栈
- **语言**: Python 3.10+
- **采集**: ADB + AccessibilityService (通过ScreenStream API)
- **解析**: 正则 + JSON结构化
- **依赖**: `手机操控库/phone_lib.py`

## 目录结构
- `原始数据/` — 采集的原始文本/XML dump
- `解析结果/` — 结构化JSON + Markdown报告
- `采集脚本/` — Agent滚动采集+深度解析脚本

## 与其他项目关系
- **上游**: `手机操控库/` (Phone类) + `反向控制/` (70+ API)
- **设备**: 需要Android手机连接 (ADB)

## Agent操作规则
- 采集操作需手机已连接且ScreenStream运行
- 原始数据文件不可删除(可追加)
- 解析结果可重新生成
