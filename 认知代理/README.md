# 认知代理 — Cognitive Agent

> **人不应该重复自己。**
> 电脑存在的意义是放大人的意志，而非消耗人的注意力。

## 一句话

感知系统采集人机交互全维上下文 → IDE Agent（Cascade）理解意图并决策 → 执行系统操作电脑。
三层通过 HTTP API / MCP 通信，任一层可独立升级。

## 架构

```
用户(意图) ──→ IDE Agent (Cascade: 分析/规划/决策)
                    │
          ┌────────┼────────┐
          ↓        ↓        ↓
      感知系统    工作流引擎   执行系统
    (本项目)    (本项目)    (remote_agent/Win32/Playwright)
```

- **感知系统** = Agent的感官，只采集不决策，暴露HTTP API供Agent查询
- **IDE Agent** = 大脑（Cascade），理解意图、生成策略、做判断
- **执行系统** = 手脚，复用现有 remote_agent 45+ API / phone_lib 90+ API / Playwright

## Phase 0 · 能力矩阵

### 现有基础设施（可直接复用）

| 系统 | 文件 | 能力 | API数 |
|------|------|------|-------|
| remote_agent | `远程桌面/remote_agent.py` | 截屏/键鼠/窗口/进程/剪贴板/Shell/文件/服务/网络/Guardian | 45+ |
| phone_lib | `手机操控库/phone_lib.py` | 手机五感/APP控制/触摸/文字/设置/通知/文件 | 90+ |
| network_guardian | `构建部署/network_guardian.py` | 网络自愈/多链路切换/心跳 | 8 |
| Playwright MCP | IDE内置 | 浏览器自动化/E2E | 22 |
| Chrome DevTools MCP | IDE内置 | 浏览器调试/检查 | 28 |

### 已安装Python库（零安装成本）

| 库 | 版本 | 用于 |
|----|------|------|
| **uiautomation** | 2.0.18 | UIA控件树读取（**最大低垂果实**） |
| **pywinauto** | 0.6.8 | 窗口自动化/控件操作 |
| **pywin32** | — | Win32 API全量访问 |
| **comtypes** | 1.4.11 | COM接口（UIA底层） |
| **keyboard** | — | 全局键盘Hook |
| **psutil** | 5.9.8 | 进程/系统监控 |
| **mss** | 10.1.0 | 屏幕截取 |
| **pyautogui** | 0.9.54 | 键鼠模拟 |
| **Pillow** | 10.3.0 | 图像处理 |

### 需要建设的（本项目）

| 模块 | Phase | 用途 |
|------|-------|------|
| `perception/screen.py` | 1 | UIA控件树→语义快照（非像素） |
| `perception/input_monitor.py` | 1 | 键盘/鼠标事件流 + 控件绑定 |
| `perception/window_tracker.py` | 1 | 窗口焦点链 + 应用切换记录 |
| `perception/file_watcher.py` | 1 | 文件系统变化（Win32原生） |
| `perception/process_monitor.py` | 1 | 进程生命周期事件 |
| `semantics/event_stream.py` | 1 | 事件录制/查询（SQLite） |
| `semantics/intent.py` | 2 | 事件流→意图四元组 |
| `workflow/graph.py` | 3 | 意图行为图谱 |
| `workflow/executor.py` | 4 | 图谱执行+自纠偏 |
| `server.py` | 1 | HTTP API入口 |

## 五维感知

| 维度 | 采集内容 | 存储形式 | 实现 |
|------|---------|---------|------|
| 视觉 | UIA控件树+窗口状态+OCR | 语义快照JSON | uiautomation+pywinauto |
| 操作 | 键鼠输入+手势+目标控件 | 事件流+控件标注 | keyboard+Win32Hook |
| 听觉 | 系统通知+应用事件 | 事件标签 | Win32通知监听 |
| 认知 | 焦点链+剪贴板+对话框 | 状态快照序列 | Win32 SetWinEventHook |
| 暗维 | 文件变化+进程生命周期 | 差分日志 | ReadDirectoryChangesW+psutil |

## 文件结构

```
认知代理/
├── server.py                      # HTTP API :9070 (30+端点)
├── config.py                      # 全局配置
├── perception/                    # Phase 1 — 五维感知
│   ├── screen.py                  # UIA控件树→语义快照 (105ms)
│   ├── input_monitor.py           # 键盘(keyboard)+鼠标(Win32 LL Hook)
│   ├── window_tracker.py          # Win32 SetWinEventHook焦点链
│   ├── process_monitor.py         # psutil进程生命周期
│   └── file_watcher.py            # Win32 ReadDirectoryChangesW
├── semantics/                     # Phase 2 — 语义提炼
│   ├── event_stream.py            # SQLite WAL批量录制/查询
│   └── intent.py                  # 事件分组→模式识别→意图四元组→跨应用流
├── workflow/                      # Phase 3+4 — 工作流引擎
│   ├── graph.py                   # 参数化工作流图谱(JSON)
│   ├── storage.py                 # 持久化+版本管理
│   └── executor.py                # 执行引擎(Local+RemoteAgent后端+自纠偏)
└── data/                          # 运行时数据(gitignored)
    ├── events.db                  # SQLite事件库
    └── workflows/                 # 工作流JSON文件
```

## 启动

```powershell
cd 认知代理
python server.py                    # HTTP API :9070
python server.py --port 9071        # 自定义端口
python -m perception.screen         # 单独测试屏幕感知
python -m perception.input_monitor  # 单独测试输入监听
python -m workflow.executor         # 单独测试工作流执行
```

## API (30+端点)

### 感知层
| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/snapshot` | 屏幕语义快照(UIA控件树) |
| GET | `/snapshot?controls=false` | 仅前台窗口(33ms) |
| POST | `/session/start` | 开始录制(同时启动感知) |
| POST | `/session/stop` | 停止录制(同时停止感知) |
| GET | `/session/status` | 当前会话状态 |
| GET | `/session/list` | 历史会话列表 |
| GET | `/session/events` | 查询事件(?type=&limit=&since=) |
| GET | `/session/stats` | 会话统计 |
| GET | `/input/events` | 输入事件 |
| GET | `/input/stats` | 输入统计 |
| GET | `/focus/current` | 当前焦点窗口 |
| GET | `/focus/chain` | 焦点切换链 |
| GET | `/focus/stats` | 焦点统计 |
| GET | `/process/events` | 进程事件 |
| GET | `/process/stats` | 进程统计 |
| GET | `/files/events` | 文件变化事件 |
| GET | `/files/stats` | 文件监控统计 |
| GET | `/perception/status` | 感知模块状态总览 |

### 语义层
| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/analyze` | 分析事件→意图四元组+跨应用流 |
| GET | `/analyze/summary` | 会话摘要(意图统计) |

### 工作流层
| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/workflows` | 列出所有工作流 |
| GET | `/workflow/{id}` | 获取工作流详情 |
| POST | `/workflow/save` | 保存工作流 |
| POST | `/workflow/delete` | 删除工作流 |
| POST | `/workflow/extract` | 从当前会话提取工作流 |
| POST | `/workflow/execute` | 执行工作流(支持dry_run) |

## 端口

**9070** — 认知代理HTTP API（不与其他服务冲突）

## 约束

- 默认不采集，用户通过 `POST /session/start` 明确开启
- 所有数据本地SQLite，零外传
- 感知帧率 ≤2fps（语义快照），输入事件实时
- 单次采集会话 ≤100MB
- 每个子模块可独立 `python -m` 测试
- 零外部服务依赖，零pip install
- 敏感窗口(密码/银行)自动脱敏

## 验证数据

| 指标 | 结果 |
|------|------|
| UIA快照 | 105ms / 7控件 (depth=4) |
| 轻量快照 | 33ms (仅前台窗口) |
| 进程监控 | 34事件 / 5秒 |
| 会话录制 | 817事件 / 97KB (~30秒) |
| 工作流执行 | 2/2步骤成功 |
| API端点 | 30+ 全通 |
| 安装依赖 | 0 (复用已有库) |

## 演进路线

| Phase | 状态 | 交付 |
|-------|------|------|
| 0 · 盘点 | ✅ | 能力矩阵 + 架构设计 |
| 1 · 最小感知 | ✅ | 五维感知模块 + HTTP API + E2E验证 |
| 2 · 语义提炼 | ✅ | 意图引擎(分组/模式/推断/跨应用) |
| 3 · 工作流生成 | ✅ | 参数化图谱 + JSON持久化 + 版本管理 |
| 4 · 自主执行 | ✅ | 执行引擎(Local/RemoteAgent + 状态验证 + 自纠偏) |
| 5 · 泛化进化 | 🔮 | 跨场景迁移 + 工作流组合 + 持续学习 |
