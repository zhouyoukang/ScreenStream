# ScreenStream 端口策略实测指南

> 本指南需要在**手机连接 ADB** 的状态下执行，用于验证各端口在不同网络场景下的可达性。

## 前提条件

- 手机已安装 ScreenStream dev 版本
- AccessibilityService 已启用
- ADB 已连接

## 场景 1：本地 USB（ADB 端口转发）

```powershell
# 转发所有端口
adb forward tcp:8080 tcp:8080
adb forward tcp:8081 tcp:8081
adb forward tcp:8084 tcp:8084

# 测试 Gateway
curl http://localhost:8080/

# 测试 MJPEG Server（主入口，包含 InputRoutes）
curl http://localhost:8081/status

# 测试 InputHttpServer（兼容入口）
curl http://localhost:8084/status
```

**预期结果**：三个端口都能返回 JSON 响应。

## 场景 2：局域网直连

```powershell
# 查看手机 IP（在手机上执行）
adb shell ip addr show wlan0 | findstr "inet "

# 假设手机 IP 为 192.168.1.100
curl http://192.168.1.100:8081/status
curl http://192.168.1.100:8084/status
```

**预期结果**：
- 8081（MJPEG Server）：应该能访问（绑定 0.0.0.0）
- 8084（InputHttpServer）：取决于 `autoStartHttp` 设置是否开启

## 场景 3：宏系统 API 验证

```powershell
# 创建宏
curl -X POST http://localhost:8081/macro/create -H "Content-Type: application/json" -d "{\"name\":\"测试宏\",\"actions\":[{\"type\":\"api\",\"endpoint\":\"/home\"},{\"type\":\"wait\",\"ms\":1000},{\"type\":\"api\",\"endpoint\":\"/back\"}]}"

# 列出宏
curl http://localhost:8081/macro/list

# 运行宏（替换 xxx 为实际 ID）
curl -X POST http://localhost:8081/macro/run/xxx

# 查看运行状态
curl http://localhost:8081/macro/running

# 查看执行日志
curl http://localhost:8081/macro/log/xxx

# 内联执行（不保存）
curl -X POST http://localhost:8081/macro/run-inline -H "Content-Type: application/json" -d "{\"actions\":[{\"type\":\"api\",\"endpoint\":\"/home\"},{\"type\":\"wait\",\"ms\":500},{\"type\":\"api\",\"endpoint\":\"/recents\"}]}"
```

## 场景 4：FRP/公网穿透

如果使用 FRP 将 8081 映射到公网：

```powershell
# 测试公网访问
curl http://your-frp-domain:mapped-port/status

# 验证 InputRoutes 是否挂载
curl http://your-frp-domain:mapped-port/deviceinfo
```

**注意**：公网暴露时应考虑 PIN 码认证（MjpegSettings.enablePin）。

## 验证清单

| 项目 | 命令 | 预期 |
|------|------|------|
| 状态查询 | `GET /status` | `{"connected":true,...}` |
| 触控 | `POST /tap {"nx":0.5,"ny":0.5}` | `{"ok":true}` |
| 设备信息 | `GET /deviceinfo` | 电量/型号/分辨率 JSON |
| 宏列表 | `GET /macro/list` | JSON 数组 |
| 宏创建 | `POST /macro/create` | `{"ok":true,"id":"xxx"}` |
| View 树 | `GET /viewtree` | 界面层级 JSON |
| WebSocket | `ws://localhost:8081/ws/touch` | 连接成功 |
