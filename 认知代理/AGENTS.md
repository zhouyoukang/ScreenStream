# 认知代理 — Agent操作指南

## 核心职责
PC人机交互的全维感知系统。采集屏幕语义、输入事件、窗口焦点、文件变化、进程生命周期，供IDE Agent查询和推断用户意图。

## 关键文件
- `server.py` — HTTP API入口(:9070)
- `perception/screen.py` — UIA控件树→语义快照
- `perception/input_monitor.py` — 键鼠事件流
- `perception/window_tracker.py` — 窗口焦点链
- `semantics/event_stream.py` — 事件录制/查询(SQLite)

## 铁律
- **只采集不决策** — 感知系统是眼耳，不是大脑
- **用户授权** — 默认关闭，POST /session/start 才开始采集
- **本地存储** — 数据永远不离开本机
- **语义优先** — 存结构化JSON，不存原始像素/音频

## 端口
9070（固定，不可变更）

## 对话结束选项
- **看看效果** — 启动server.py，浏览器查看感知数据
- **测试模块** — 单独运行某个perception模块验证
- **继续建设** — 推进下一个Phase
- **收工提交** — git commit变更
