# 远程桌面控制 (RemoteDesktop)

> **独立项目** — 可由专属 Agent 独立开发，与 ScreenStream/SmartHome 完全无依赖。

## 项目边界

| 维度 | 值 |
|------|-----|
| **目录** | `远程桌面/` |
| **语言** | Python 3.8+ |
| **端口** | 9903 (默认), 9904 (跨会话), 9905 (测试) |
| **入口** | `remote_agent.py` (服务端) |
| **前端** | `remote_desktop.html` (也通过 GET / 提供) |
| **依赖** | mss + Pillow (截屏) + pyautogui (键鼠) |

## 可修改文件

```
远程桌面/
├── remote_agent.py          ← 服务端 (~1230行，30+API，MouseGuard，唤醒/屏幕状态)
├── remote_desktop.html      ← Web 前端 (~1850行，7面板，触摸五感+响应式)
├── guard-toggle.ps1         ← MouseGuard 一键切换
├── tests/
│   └── test_remote.py       ← 55+ 项自动化测试 (24轮)
└── README.md
```

## 禁止修改

- ScreenStream 所有目录（用户界面/投屏链路/反向控制/基础设施/配置管理/构建部署）
- `智能家居/`
- `手机操控库/`
- `.windsurf/` 配置文件

## 与其他项目的集成点

| 集成 | 说明 |
|------|------|
| 无硬依赖 | 本项目完全独立，不依赖其他项目运行 |
| 可选联动 | SmartHome dashboard.html 可 iframe 嵌入本项目前端 |

## 独立开发流程

```powershell
# 安装依赖
pip install mss Pillow pyautogui

# 启动
python remote_agent.py                  # 默认 :9903
python remote_agent.py --port 9904      # 自定义端口
python remote_agent.py --no-guard       # 禁用鼠标保护

# 访问前端
# 浏览器打开 http://127.0.0.1:9903/

# 测试
python tests/test_remote.py             # 27 项 (默认 :9905)
python tests/test_remote.py --port 9903 # 自定义端口
```

## 共享资源

| 资源 | 冲突风险 | 协调方式 |
|------|---------|---------|
| 端口 9903-9905 | 低（独占范围） | 本项目专用 |
| Windows 桌面会话 | 中 | 跨会话部署用不同端口 |
| pyautogui | 低 | MouseGuard 防劫持 |

## 架构要点

- **零框架**：纯 `http.server`，无 Flask/FastAPI 依赖
- **MouseGuard**：检测用户鼠标活动，自动暂停自动化防止劫持
- **跨会话**：支持多 Windows 用户会话，每个会话独立端口
- **Unicode**：非 ASCII 文本自动用 clip.exe + Ctrl+V 粘贴
- **手机五感**：触摸点击/长按右键/滑动滚屏/双指缩放/底部导航/响应式布局

## 对话结束选项

> 任务完成后调用 `ask_user_question`，从下表选 4 个最贴合的：

| label | description |
|-------|-------------|
| 打开浏览器试试 | 启动服务，浏览器打开确认效果 |
| 跑全套测试 | 执行55项自动化测试验证 |
| 手机上试试 | 用手机浏览器访问，测试触摸操控 |
| 继续完善功能 | 改进API/前端交互/MouseGuard |
| 收工提交 | 记录成果 + git commit |
