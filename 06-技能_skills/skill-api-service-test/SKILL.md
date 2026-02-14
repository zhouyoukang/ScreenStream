# skill-api-service-test

## 触发条件（什么时候用）

- 需要验证API服务化架构是否正常工作
- 要测试投屏、数据传输、系统通知等功能而无需APK打包
- 进行后端功能的完整测试流程

## 目标（要产出什么）

- 验证所有API服务能正常启动和响应
- 测试MJPEG、RTSP、WebRTC、Input等核心功能
- 确保可以完全脱离APK进行功能验证
- 输出完整的测试证据包

## Refs（权威入口）

- `api-services/README.md` - API服务使用指南
- `api-services/scripts/start-all.sh` - 服务启动脚本
- `IMPLEMENTATION_SUMMARY.md` - 实施总结文档

## 护栏（必须遵守）

- 测试前必须先检查所有必要文件是否存在
- 服务启动失败时不要强行继续，先排查原因
- 高风险操作（端口占用处理）需要明确确认
- 所有测试结果必须记录到证据包中

## 步骤

### Step 1：环境检查与准备

检查必要环境：
- Java 17+ 环境
- 端口8080-8084可用性检查
- 构建产物存在性验证

### Step 2：构建验证

只读命令组：
```bash
# 检查项目结构
ls -la api-services/
find api-services/ -name "*.kt" | head -5

# 检查Gradle配置
cat api-services/settings.gradle.kts
cat api-services/build.gradle.kts
```

构建命令组（需确认）：
```bash
# 构建所有API服务
./gradlew :api-services:gateway:build
./gradlew :api-services:mjpeg-server:build  
./gradlew :api-services:rtsp-server:build
./gradlew :api-services:webrtc-server:build
./gradlew :api-services:input-server:build
```

### Step 3：服务启动测试

启动命令组（需确认）：
```bash
# 使用启动脚本
chmod +x api-services/scripts/start-all.sh
./api-services/scripts/start-all.sh
```

### Step 4：功能验证测试

API测试命令组：
```bash
# 健康检查
curl http://localhost:8080/health
curl http://localhost:8081/health
curl http://localhost:8082/health
curl http://localhost:8083/health
curl http://localhost:8084/health

# 服务状态检查
curl http://localhost:8080/status

# 功能测试
curl -X POST http://localhost:8080/mjpeg/start -H "Content-Type: application/json" -d '{"quality":"high","fps":30}'
curl -X POST http://localhost:8080/input/touch -H "Content-Type: application/json" -d '{"x":100,"y":200,"action":"tap"}'
curl -X POST http://localhost:8080/start-all
```

### Step 5：清理与停止

```bash
# 停止所有服务
./api-services/scripts/stop-all.sh
```

## 输出与验收

- [ ] 所有5个服务能正常启动
- [ ] 网关能正确路由到各个服务
- [ ] MJPEG流服务响应正常
- [ ] 输入控制API功能正常
- [ ] 可以通过API完成基本的投屏和控制功能
- [ ] 无需APK打包即可完成所有测试

## 证据包要求

- 服务启动日志
- 健康检查响应
- 功能测试API响应
- 错误日志（如有）
- 端口占用情况

## 归档

- 更新 `docs/STATUS.md` 记录测试结果
- 如发现问题，记录到问题列表并修复
- 测试成功后确认API服务化目标达成
