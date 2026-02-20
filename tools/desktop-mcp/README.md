# Desktop Automation MCP Server

> 给 AI Agent 装上"眼睛 + 双手"，实现自主操控电脑。

## 核心能力

| 能力 | 工具 | 说明 |
|------|------|------|
| 👁 截图 | `screenshot` | 全屏/区域截图，返回文件路径 |
| 👁 UI树 | `get_ui_tree` | Windows UI Automation 语义树 |
| 👁 查找元素 | `find_ui_element` | 按名称/类型/ID搜索UI元素 |
| 👁 综合观察 | `observe` | 截图 + UI树 + 窗口信息一次获取 |
| 🖱 点击 | `mouse_click` | 坐标点击（左/右/双击） |
| 🖱 移动 | `mouse_move` | 移动鼠标 |
| 🖱 拖拽 | `mouse_drag` | 从A拖到B |
| 🖱 滚动 | `mouse_scroll` | 滚轮上下 |
| ⌨️ 输入 | `type_text` | 键入文本（支持中文，自动切剪贴板） |
| ⌨️ 快捷键 | `hotkey` | 组合键如 `ctrl+s`, `alt+tab` |
| ⌨️ 按键 | `key_press` | 单键如 enter, escape, f1 |
| 🪟 窗口列表 | `get_windows` | 列出所有可见窗口 |
| 🪟 聚焦窗口 | `focus_window` | 按标题切换窗口到前台 |
| 🎯 点击元素 | `click_ui_element` | 按语义查找+点击 |
| ⏳ 等待+点击 | `wait_and_click` | 等元素出现再点击 |

## 架构

```
┌─────────────────────────────────────────────┐
│              AI Agent (Cascade等)             │
│  observe → analyze → find_element → click   │
└──────────────┬──────────────────────────────┘
               │ MCP Protocol (stdio)
┌──────────────▼──────────────────────────────┐
│         desktop-automation MCP Server        │
│                                              │
│  Eyes:  mss + pywinauto UIA                  │
│  Hands: pyautogui (mouse + keyboard)         │
│  Brain: composite actions                    │
└──────────────────────────────────────────────┘
               │
        Windows Desktop
```

## Agent 典型工作流

```
1. observe()           → 获取截图+UI树，理解当前状态
2. find_ui_element()   → 定位目标元素（如"Terminal"按钮）
3. click_ui_element()  → 点击目标
4. type_text()         → 输入内容
5. hotkey("ctrl+s")    → 保存
6. screenshot()        → 验证结果
```

## 安装

```bash
# 依赖（已在系统Python中安装）
pip install mcp pyautogui pywinauto mss Pillow pyperclip

# 自测
python server.py --test

# 作为 MCP Server 运行（由 Windsurf 自动启动）
python server.py
```

## Windsurf MCP 配置

已自动注册到 `~/.codeium/windsurf/mcp_config.json`:

```json
"desktop-automation": {
    "command": "python",
    "args": ["E:\\github\\AIOT\\ScreenStream_v2\\tools\\desktop-mcp\\server.py"],
    "disabled": false
}
```

**重载 Windsurf 后生效。**

## 跨 Agent 复用

本 Server 遵循标准 MCP 协议，任何支持 MCP 的 Agent 均可直接调用：
- **Windsurf Cascade** — 本项目主要消费者
- **Claude Desktop** — 将同样的配置加入 `claude_desktop_config.json`
- **Cursor** — 支持 MCP 的版本均可使用
- **自定义 Agent** — 通过 MCP SDK 连接 stdio

## 技术栈

| 组件 | 库 | 用途 |
|------|-----|------|
| MCP框架 | `mcp` (FastMCP) 1.20+ | 协议+服务端 |
| 截图 | `mss` | 高性能屏幕捕获 |
| 鼠标键盘 | `pyautogui` | 输入模拟 |
| UI自动化 | `pywinauto` (UIA backend) | 元素树+语义理解 |
| 图像处理 | `Pillow` | 截图缩放/编码 |
| 剪贴板 | `pyperclip` | 非ASCII文本输入 |

## 截图存储

临时截图存放在 `%TEMP%\desktop-mcp\`，不会累积（每次调用覆盖命名）。

## 安全说明

- `pyautogui.FAILSAFE = False` — Agent需要完全控制能力
- 所有操作在用户桌面会话内执行，无跨会话/远程能力
- UI树访问使用标准 Windows UI Automation API（无注入/hook）
