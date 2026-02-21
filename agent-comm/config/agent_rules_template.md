# PRIORITY RULE - agent-comm bridge (MANDATORY)

**每次回复结束前，必须通过 `run_command` 调用 bridge 让用户决定下一步！**

## 部署

将 `<BRIDGE_PATH>` 替换为 agent-comm 实际路径后，写入 Agent 的 `global_rules.md`。

## 调用格式

```
<BRIDGE_PATH>/core/bridge.bat --ask --message "<简短摘要>" --options "<选项1>,<选项2>,..."
```

## 规则

- **SafeToAutoRun=true**（安全：只发消息等回复）
- `--message`：1-3行简短摘要，**禁止反引号**
- `--options`：2-4个动态选项，逗号分隔
- 每次回复必须调用，禁止跳过
- 等待返回JSON，按 `user_input` / `selected_options` 执行
- `user_input` 优先级最高
- 超时自动返回继续信号

## 可选：上报状态和活动

```
bridge.bat --notify --message "<任务>" --source "<项目>" --phase "working" --progress "<进度>"
bridge.bat --activity --message "<做了什么>" --source "<项目>" --type "edit" --details "<文件>"
```

> 状态和活动上报是可选的，仅在多Agent场景下有价值。

## 返回字段（JSON）

| 字段 | 说明 |
|------|------|
| `user_input` | 用户自由输入（最高优先级） |
| `selected_options` | 用户选择的选项 |
| `cancelled` | true 时停止工作 |
