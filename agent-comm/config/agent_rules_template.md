# PRIORITY RULE - agent-bridge (MANDATORY)

**每次回复结束前，必须通过 `run_command` 调用 bridge 让用户决定下一步！**

### 调用格式
```
<BRIDGE_PATH>\core\bridge.bat --ask --message "<简短摘要>" --options "<选项1>,<选项2>,..."
```

> **部署说明**：将 `<BRIDGE_PATH>` 替换为 agent-comm 的实际安装路径。
> 例如：`E:\github\AIOT\ScreenStream_v2\agent-comm\core\bridge.bat`

### 规则
- **必须设置 SafeToAutoRun=true**（该命令安全：只发送消息等待回复）
- `--message`：简短描述当前完成了什么（1-3行）
- `--options`：根据上下文动态生成2-4个选项（逗号分隔）
- **每次回复必须调用**，禁止跳过，禁止自行终止对话
- 等待返回的JSON，按 `user_input` / `selected_options` 执行
- 用户输入优先级最高，覆盖正在进行的任何工作

### 返回字段（JSON）
- `user_input` → 用户自由输入的指令（最高优先级）
- `selected_options` → 用户选择的预定义选项
- `cancelled` → true时停止当前工作

如果命令超时，会自动返回继续信号，Agent可以继续工作。

---

## 核心原则
- 中文回复
- 不确定时明确告知，禁止猜测
- 一次性闭环完成，不留半成品
- 禁止修改系统配置（hooks.json, global_rules.md, mcp_config.json）
