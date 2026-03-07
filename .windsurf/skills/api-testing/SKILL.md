---
name: api-testing
description: 测试ScreenStream的HTTP API端点。当需要验证API功能、健康检查、或调试HTTP服务时触发。
---

## API 端口（固定分配，禁止冲突）
- **Gateway**: 8080
- **MJPEG**: 8081 (流媒体+Input路由共享，需用户启动投屏)
- **RTSP**: 8082
- **WebRTC**: 8083
- **Input**: 8084 (应用启动即监听)

## 标准测试流程

### 0. 端口转发（推荐，绕过防火墙）
```powershell
& "D:\platform-tools\adb.exe" forward tcp:8084 tcp:8084
& "D:\platform-tools\adb.exe" forward tcp:8081 tcp:8081
```

### 1. 健康检查
```powershell
# Input API（应用启动后即可）
curl.exe -s --connect-timeout 5 http://127.0.0.1:8084/status

# MJPEG（需要用户在手机上启动投屏）
curl.exe -s --connect-timeout 5 http://127.0.0.1:8081/
```

### 2. 输入API测试
```powershell
# 点击（归一化坐标，PowerShell 中 JSON 用单引号）
curl.exe -s -X POST http://127.0.0.1:8084/tap -H "Content-Type: application/json" --data-raw '{"x":0.5,"y":0.5}'

# 滑动
curl.exe -s -X POST http://127.0.0.1:8084/swipe -H "Content-Type: application/json" --data-raw '{"nx1":0.5,"ny1":0.8,"nx2":0.5,"ny2":0.2,"duration":300}'

# 发送文本
curl.exe -s -X POST http://127.0.0.1:8084/text -H "Content-Type: application/json" --data-raw '{"text":"hello"}'

# 发送按键（Backspace）
curl.exe -s -X POST http://127.0.0.1:8084/key -H "Content-Type: application/json" --data-raw '{"keysym":65288,"down":true,"shift":false,"ctrl":false}'

# 导航键
curl.exe -s -X POST http://127.0.0.1:8084/back
curl.exe -s -X POST http://127.0.0.1:8084/home
curl.exe -s -X POST http://127.0.0.1:8084/recents
```

### 3. 设备端口排查
```powershell
& "D:\platform-tools\adb.exe" shell "netstat -tlnp 2>/dev/null | grep 808"
```

## 端口监听时机
- **8080**（Gateway）、**8084**（Input）：应用启动后立即监听
- **8081**（MJPEG）：用户在手机上点击"开始投屏"后才监听

### 4. WiFi直连测试（无需ADB）
```powershell
# 获取手机WiFi IP后直连
curl.exe -s --connect-timeout 3 http://192.168.31.40:8084/status
curl.exe -s --connect-timeout 3 http://192.168.31.40:8084/foreground
```

### 5. phone_lib测试（Python）
```powershell
# 五感快速验证
python -c "from phone_lib import Phone; p=Phone(port=8084); print(p.senses())"
```

## 常见问题
- 连接拒绝 → 先用 `adb forward` 再试；检查应用是否已启动投屏服务
- 端口不通 → `netstat` 确认端口是否在监听
- JSON 解析失败 → PowerShell 中用 `--data-raw '...'` 而非 `-d "..."`
- 输入无响应 → 检查 AccessibilityService 是否已授权
- 端口动态变化 → MJPEG端口可能因设备占用偏移，用`netstat`探测实际端口
