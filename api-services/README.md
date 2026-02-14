# ScreenStream API Services

基于OpenClaw技术的ScreenStream API服务化架构，实现投屏功能的独立服务化，支持后端直接测试而无需APK打包。

## 🎯 项目目标

- **快速迭代**：服务秒级重启，避免APK编译等待
- **并行开发**：前后端可独立开发测试
- **自动化测试**：集成OpenClaw Skills实现完整自动化测试
- **水平扩展**：各服务独立扩容和版本管理

## 📁 架构设计

```
ScreenStream API Services
├── Gateway (8080)          # 统一API网关
├── MJPEG Server (8081)     # MJPEG流媒体服务
├── RTSP Server (8082)      # RTSP流媒体服务  
├── WebRTC Server (8083)    # WebRTC信令服务
└── Input Server (8084)     # 反向控制服务
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 安装JDK 17+
java -version

# 安装OpenClaw (用于自动化测试)
npm install -g openclaw

# 安装Docker (可选)
docker --version
```

### 2. 构建服务

```bash
# 构建所有服务
./gradlew build

# 或单独构建
./gradlew :gateway:build
./gradlew :mjpeg-server:build
./gradlew :rtsp-server:build
./gradlew :webrtc-server:build  
./gradlew :input-server:build
```

### 3. 启动服务

**方式一：单独启动**
```bash
# 启动Gateway网关
java -jar gateway/build/libs/gateway-2.0.0.jar

# 启动MJPEG服务
java -jar mjpeg-server/build/libs/mjpeg-server-2.0.0.jar

# 启动其他服务...
```

**方式二：Docker Compose**
```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f gateway
```

### 4. 验证服务

```bash
# 检查网关健康
curl http://localhost:8080/health

# 获取所有服务状态
curl http://localhost:8080/status

# 一键启动所有流媒体服务
curl -X POST http://localhost:8080/start-all
```

## 🎮 API使用指南

### Gateway API (8080)

```bash
# 健康检查
GET /health

# 服务状态
GET /status

# 一键启动/停止所有服务
POST /start-all
POST /stop-all
```

### MJPEG API (8081)

```bash
# 启动MJPEG流
POST /mjpeg/start
{
  "quality": "high",
  "fps": 30,
  "resolution": "1080p"
}

# 获取MJPEG流
GET /mjpeg/stream

# 停止流
POST /mjpeg/stop
```

### Input API (8084)

```bash
# 发送触摸事件
POST /input/touch
{
  "x": 100,
  "y": 200,
  "action": "tap"
}

# 发送按键事件  
POST /input/key
{
  "keyCode": 4,
  "action": "press"
}

# 发送文本输入
POST /input/text
{
  "text": "Hello World"
}
```

## 🦞 OpenClaw Skills集成

### 安装Skills

```bash
# 复制Skills到OpenClaw目录
cp openclaw-skills/*.js ~/.openclaw/skills/

# 验证安装
openclaw skills list
```

### 使用Skills

```javascript
// 启动流媒体服务
await screenstream.startStream({type: 'mjpeg', config: {quality: 'high'}})

// 发送触摸事件
await screenstream.sendTouch({x: 100, y: 200})

// 运行完整测试
await screenstream.quickDemo()
```

### 自动化测试

```bash
# 运行冒烟测试
openclaw skill run screenstream-test executeTestSuite smoke-test

# 运行性能测试
openclaw skill run screenstream-test executeTestSuite performance-test

# 运行CI流水线
openclaw skill run screenstream-test runCI
```

## 🔧 开发指南

### 添加新服务

1. 在`api-services/`下创建新目录
2. 实现Ktor服务器和RESTful API
3. 更新`settings.gradle.kts`包含新模块
4. 在Gateway中添加路由规则
5. 更新Docker Compose配置

### 扩展Skills

```javascript
// 在screenstream-control.js中添加新功能
actions: {
  async newAction(params) {
    // 实现逻辑
    return { success: true, data: result };
  }
}
```

### 自定义测试

```javascript
// 在screenstream-test.js中添加测试用例
testSuites: {
  "custom-test": [
    { name: "my-test", action: "runMyTest", timeout: 5000 }
  ]
}
```

## 📊 监控运维

### 服务监控

```bash
# 查看所有服务健康状态
curl http://localhost:8080/status

# 查看详细指标 (如果启用Prometheus)
curl http://localhost:9090/metrics
```

### 日志管理

```bash
# Docker环境查看日志
docker-compose logs -f gateway
docker-compose logs -f mjpeg-server

# 直接启动查看日志
tail -f logs/gateway.log
```

### 性能调优

- **JVM参数**: `-Xmx512m -Xms256m`
- **网络配置**: 调整`ktor`服务器参数
- **并发控制**: 配置连接池大小

## 🚀 部署指南

### 开发环境

```bash
# 本地启动
./gradlew bootRun

# 或使用IDE直接运行main函数
```

### 测试环境

```bash
# Docker部署
docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d
```

### 生产环境

```bash
# 包含监控和负载均衡
docker-compose --profile production --profile monitoring up -d
```

## 📈 性能基准

- **启动时间**: < 10秒 (所有服务)
- **响应延迟**: < 50ms (输入事件)
- **并发连接**: 100+ (单服务)
- **内存使用**: < 512MB (单服务)

## 🧪 测试覆盖

- **单元测试**: 每个API端点
- **集成测试**: 服务间通信
- **性能测试**: 并发和延迟
- **端到端测试**: 完整业务流程

## 📋 TODO

- [ ] 添加认证和授权机制
- [ ] 实现服务发现和注册
- [ ] 增加更多监控指标
- [ ] 支持配置热更新
- [ ] 添加API限流功能

## 🤝 贡献指南

1. Fork项目
2. 创建功能分支: `git checkout -b feature/new-feature`
3. 提交更改: `git commit -am 'Add new feature'`
4. 推送分支: `git push origin feature/new-feature`
5. 创建Pull Request

## 📄 许可证

本项目基于MIT许可证开源。

## 🆘 问题排查

### 常见问题

**Q: 服务启动失败？**
A: 检查端口是否被占用，确保JDK版本>=17

**Q: OpenClaw Skills无法加载？**
A: 确认Skills文件路径和node-fetch依赖

**Q: API调用超时？**
A: 检查服务健康状态和网络连接

### 获取帮助

- 查看日志文件
- 运行健康检查API
- 使用OpenClaw Skills诊断
- 提交Issue到GitHub仓库
