# MacroDroid 万能桥接器 (Universal Bridge) 配置指南 v2.5

## 简介
这是一个高级的 MacroDroid 集成方案，利用 MQTT 实现 Home Assistant 对手机的**全能控制**。
只需在手机上配置一次，即可支持 shell 脚本、通知、系统设置、**智能App启动** (按名字)、**UI点击** (点按钮) 等多种功能。

## 第一步：导入 Action Block (动作块)
为了确保成功率，我将功能分成了两个包。请**依次**导入：

1.  **基础包 (必选)**：
    *   文件：`d:\homeassistant\macrodroid\HA_Universal_Core.macro`
    *   内容：包含 `MDWC - Execute action` 等核心引擎。
    *   **先导入这个**，如果成功，说明万能命令的基础功能（Shell/通知等）已就绪。

2.  **扩展包 (可选)**：
    *   文件：`d:\homeassistant\macrodroid\HA_Universal_Extras.macro`
    *   内容：包含 `智能 App 启动` 和 `UI 点击` 功能。
    *   **基础包成功后再尝试导入这个**。如果这个导入失败，至少基础功能还能用。

## 第二步：创建触发宏
新建一个宏，命名为 `HA_Receiver`：

### 1. 触发器 (Trigger)
*   **MQTT 客户端 -> 收到消息 (Message Received)**
    *   **Topic**: `ha/phone/universal/你的设备名` (例如 `ha/phone/universal/oneplus`)
    *   **变量 (Variable)**: 存入局部变量 `json_payload` (String)。

### 2. 动作 (Actions)
*   **JSON 解析 (JSON Parse)**
    *   输入: `json_payload` -> 输出: `cmd`
*   **If Condition (判断 actionId)**
    *   **条件**: `cmd[actionId]` 等于 `launch_app_smart`
        *   **Action Block**: `Launch app (voice commands)`
        *   **参数**: `input` = `cmd[stringArgs][app_name]`
    *   **Else If**: `cmd[actionId]` 等于 `ui_click`
        *   **Action Block**: `UI Press/Hold (id/text) pro`
        *   **参数**: 
            *   `textToClick` = `cmd[stringArgs][text]`
            *   `idToClick` = `cmd[stringArgs][id]`
    *   **Else**:
        *   **Action Block**: `MDWC - Execute action`
        *   **参数**: 
            *   `actionId` = `cmd[actionId]`
            *   `stringArgs` = `cmd[stringArgs]`
            *   (以及其他 args)

## 第三步：Home Assistant 使用

### 示例 1：智能启动 App (无需包名)
```yaml
service: script.send_universal_cmd
data:
  action_id: "launch_app_smart"
  target: "oneplus"
  string_args:
    app_name: "微信"  # 手机会自动找"微信"
```

### 示例 2：模拟点击 (UI Interaction)
```yaml
service: script.send_universal_cmd
data:
  action_id: "ui_click"
  target: "oneplus"
  string_args:
    text: "发送"  # 点击屏幕上文字为"发送"的按钮
    # id: "com.tencent.mm:id/send_btn" # 或者用 ID
```

### 示例 3：原版 MDWC 功能 (Shell/Toast/Etc)
```yaml
service: script.send_universal_cmd
data:
  action_id: "post_notification"
  string_args:
    title: "HA"
    text: "Hello"
```
