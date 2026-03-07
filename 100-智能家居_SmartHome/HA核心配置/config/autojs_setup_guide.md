# AutoJS Universal Bridge 配置指南

## 1. VS Code 插件安装
您之前没找到插件，请在 VS Code 扩展商店搜索以下准确名称：

*   **插件名称**: `Auto.js-Pro-Ext`
*   **发布者**: `Hyb1996` (或者类似 ID，认准 "Pro" 字样)
*   **备用**: 如果找不到 Pro 版，可以尝试 `Auto.js-VSCodeExt` (虽然主要是免费版用，但部分功能通用)。

## 2. 连接手机
1.  **启动服务**:
    *   在 VS Code 中按下 `Ctrl + Shift + P`。
    *   输入 `Auto.js Pro: Start Server` 并回车。
    *   **记下 IP**: VS Code 右下角会显示当前 IP，例如 `192.168.1.5:9317`。

2.  **手机连接**:
    *   打开 **AutoJS Pro** App。
    *   打开侧边栏 -> **连接电脑**。
    *   输入刚才电脑显示的 IP 地址。
    *   点击确定，等待 VS Code 提示连接成功。

## 3. 部署脚本
1.  **打开脚本文件**:
    *   在 VS Code 中打开 `d:\homeassistant\macrodroid\autojs_universal_bridge.js`。

2.  **配置 MQTT**:
    *   找到脚本开头的 `用户配置` 区域。
    *   **必须修改**: `MQTT_HOST` (您的 MQTT Broker IP)。
    *   可选修改: 用户名/密码 (如果有)。

3.  **运行**:
    *   确保手机已连接且屏幕开启。
    *   在 VS Code 中按下 `F5` (运行)。
    *   观察手机，应该会出现一个界面显示 "正在连接..." -> "已连接"。

## 4. 测试
在 Home Assistant 中调用服务：
```yaml
service: script.send_universal_cmd
data:
  target: "您的手机品牌" # 注意脚本里的 MQTT_TOPIC 也就是 device.brand
  action_id: "toast"
  string_args:
    text: "Hello from AutoJS!"
```
如果手机弹出提示，恭喜，万能桥接器已打通！
