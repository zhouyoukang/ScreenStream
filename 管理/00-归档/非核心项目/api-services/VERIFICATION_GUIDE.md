# ScreenStream API服务化验证指南

## 🎯 验证目标

确保API服务化架构完整可用，实现**不打包APK即可完成所有后端测试**的核心目标。

## 📋 完整验证清单

### 1. 环境准备验证

```bash
# 检查Java环境（必须JDK 17+）
java -version

# 检查端口可用性
netstat -an | findstr "8080 8081 8082 8083 8084"

# 检查项目结构完整性
ls api-services/
ls api-services/gateway/src/main/kotlin/
ls api-services/scripts/
```

### 2. 构建验证

```bash
# 进入API服务目录
cd api-services

# 构建所有服务
./gradlew build

# 检查构建产物
ls gateway/build/libs/
ls mjpeg-server/build/libs/
ls rtsp-server/build/libs/
ls webrtc-server/build/libs/
ls input-server/build/libs/
```

### 3. 服务启动验证

```bash
# 方式一：使用启动脚本（推荐）
chmod +x scripts/start-all.sh
./scripts/start-all.sh

# 方式二：手动启动（调试用）
java -jar gateway/build/libs/gateway-2.0.0.jar &
java -jar mjpeg-server/build/libs/mjpeg-server-2.0.0.jar &
java -jar rtsp-server/build/libs/rtsp-server-2.0.0.jar &
java -jar webrtc-server/build/libs/webrtc-server-2.0.0.jar &
java -jar input-server/build/libs/input-server-2.0.0.jar &
```

### 4. 健康检查验证

```bash
# 检查所有服务健康状态
curl http://localhost:8080/health    # Gateway
curl http://localhost:8081/health    # MJPEG
curl http://localhost:8082/health    # RTSP
curl http://localhost:8083/health    # WebRTC
curl http://localhost:8084/health    # Input

# 获取综合服务状态
curl http://localhost:8080/status
```

### 5. 核心功能验证

#### 5.1 投屏功能测试

```bash
# 启动MJPEG流媒体
curl -X POST http://localhost:8080/mjpeg/start \
  -H "Content-Type: application/json" \
  -d '{"quality":"high","fps":30,"resolution":"1080p"}'

# 检查流状态
curl http://localhost:8080/mjpeg/status

# 访问流地址
curl http://localhost:8080/mjpeg/stream

# 启动RTSP服务
curl -X POST http://localhost:8080/rtsp/start \
  -H "Content-Type: application/json" \
  -d '{"codec":"H264","bitrate":2000000}'

# 启动WebRTC信令
curl -X POST http://localhost:8080/webrtc/start \
  -H "Content-Type: application/json" \
  -d '{"enableAudio":true,"videoCodec":"VP8"}'
```

#### 5.2 输入控制测试

```bash
# 发送触摸事件
curl -X POST http://localhost:8080/input/touch \
  -H "Content-Type: application/json" \
  -d '{"x":100,"y":200,"action":"tap"}'

# 发送按键事件
curl -X POST http://localhost:8080/input/key \
  -H "Content-Type: application/json" \
  -d '{"keyCode":4,"action":"press"}'

# 发送文本输入
curl -X POST http://localhost:8080/input/text \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello ScreenStream API!"}'

# 检查输入统计
curl http://localhost:8080/input/status
```

#### 5.3 批量操作测试

```bash
# 一键启动所有服务
curl -X POST http://localhost:8080/start-all

# 一键停止所有服务
curl -X POST http://localhost:8080/stop-all
```

### 6. 压力测试验证

```bash
# 并发输入测试
for i in {1..10}; do
  curl -X POST http://localhost:8080/input/touch \
    -H "Content-Type: application/json" \
    -d "{\"x\":$((100+i)),\"y\":$((200+i)),\"action\":\"tap\"}" &
done

# 检查延迟统计
curl http://localhost:8080/input/status
```

### 7. 错误恢复测试

```bash
# 停止单个服务
curl -X POST http://localhost:8080/mjpeg/stop

# 检查服务状态
curl http://localhost:8080/status

# 重新启动
curl -X POST http://localhost:8080/mjpeg/start
```

## 🔧 故障排查

### 常见问题及解决方案

#### 1. 端口占用
```bash
# 查看端口占用
netstat -ano | findstr ":8080"

# 强制结束进程
taskkill /PID <pid> /F
```

#### 2. 服务启动失败
```bash
# 查看服务日志
cat logs/gateway.log
cat logs/mjpeg-server.log

# 检查Java版本
java -version

# 检查JAR文件
ls -la */build/libs/
```

#### 3. API调用失败
```bash
# 检查服务健康状态
curl -v http://localhost:8080/health

# 检查网络连接
ping localhost

# 检查防火墙设置
```

## ✅ 验收标准

### 必须通过的测试项

- [ ] **环境检查**：Java 17+环境可用
- [ ] **构建成功**：所有5个服务JAR文件生成
- [ ] **服务启动**：所有服务健康检查返回200
- [ ] **网关路由**：Gateway能正确转发到各服务
- [ ] **投屏功能**：MJPEG/RTSP/WebRTC服务响应正常
- [ ] **输入控制**：触摸、按键、文本输入API正常
- [ ] **批量操作**：一键启停所有服务功能正常
- [ ] **状态监控**：能正确获取服务状态和统计信息

### 核心目标验证

- [ ] **无需APK打包**：所有测试通过RESTful API完成
- [ ] **开发效率提升**：服务重启时间 < 10秒
- [ ] **并行开发支持**：前后端可独立开发测试
- [ ] **自动化测试**：API接口支持脚本化测试

## 📊 性能基准

- **服务启动时间**：< 15秒（所有5个服务）
- **API响应延迟**：< 100ms（健康检查）
- **输入事件延迟**：< 50ms（触摸、按键）
- **并发连接数**：> 10个同时连接
- **内存使用**：< 512MB/服务

## 🎉 验证完成确认

当所有验收标准通过后，确认以下成果：

1. ✅ **API服务化架构**：5个独立服务完整可用
2. ✅ **技能化思维应用**：可复用工作流建立
3. ✅ **开发痛点解决**：无需APK打包即可完整测试
4. ✅ **部署方案完整**：Docker、脚本、文档齐全

**项目状态：API服务化改造成功交付**
