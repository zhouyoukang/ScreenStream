# 智能家居完整控制系统

## 🎯 功能概述

这是一个简化但功能完整的智能家居控制系统，具有以下特点：

### ✨ 主要功能
1. **设备状态查询** - 实时获取所有设备状态
2. **互斥控制** - 开4号自动关5号，开5号自动关4号
3. **错误处理** - 完善的错误处理和状态反馈
4. **简单易用** - 通过简单的HTTP请求控制

### 🔧 工作流结构
- **触发器**: Webhook接收控制请求
- **路由器**: 根据action参数分发请求
- **状态查询**: 获取并处理所有设备状态
- **设备控制**: 执行开关操作
- **响应**: 返回操作结果

## 📋 使用方法

### 1. 导入工作流
1. 在n8n中导入 `workflows/smart-home-complete.json`
2. 激活工作流
3. 记录webhook URL

### 2. API调用方式

#### 查询设备状态
```bash
curl -X POST http://localhost:5678/webhook/smart-home \
  -H "Content-Type: application/json" \
  -d '{"action": "status"}'
```

#### 控制4号设备（自动关闭5号）
```bash
curl -X POST http://localhost:5678/webhook/smart-home \
  -H "Content-Type: application/json" \
  -d '{"action": "control", "device": "4"}'
```

#### 控制5号设备（自动关闭4号）
```bash
curl -X POST http://localhost:5678/webhook/smart-home \
  -H "Content-Type: application/json" \
  -d '{"action": "control", "device": "5"}'
```

### 3. 使用测试脚本

#### 安装依赖
```bash
npm install axios
```

#### 运行测试
```bash
# 完整测试
node test-smart-home.js

# 只查询状态
node test-smart-home.js status

# 只控制4号设备
node test-smart-home.js device4

# 只控制5号设备
node test-smart-home.js device5
```

## 🔍 响应格式

### 状态查询响应
```json
{
  "success": true,
  "action": "status",
  "devices": {
    "4": {
      "entity_id": "switch.4",
      "state": "on",
      "friendly_name": "设备4",
      "last_changed": "2024-01-08T10:30:00Z"
    },
    "5": {
      "entity_id": "switch.5", 
      "state": "off",
      "friendly_name": "设备5",
      "last_changed": "2024-01-08T10:25:00Z"
    }
  },
  "total_devices": 2,
  "timestamp": "2024-01-08T10:35:00Z"
}
```

### 控制操作响应
```json
{
  "success": true,
  "action": "control",
  "device": "4",
  "message": "操作完成",
  "timestamp": "2024-01-08T10:35:00Z"
}
```

## 🛠️ 配置说明

### Home Assistant配置
- **地址**: `http://192.168.1.123:8123`
- **API Token**: 已配置在工作流中
- **设备实体**: `switch.4` 和 `switch.5`

### 修改配置
如需修改IP地址或Token，请编辑工作流中的以下节点：
1. "获取所有设备状态"
2. "打开4号设备"
3. "关闭5号设备"
4. "打开5号设备"
5. "关闭4号设备"

## 🚨 故障排除

### 常见问题

#### 1. 连接失败
- 检查n8n是否运行
- 确认工作流已激活
- 验证webhook URL正确

#### 2. Home Assistant连接失败
- 检查HA地址是否正确
- 验证API Token是否有效
- 确认设备entity_id存在

#### 3. 设备控制失败
- 检查设备是否在线
- 验证entity_id格式
- 确认设备支持开关操作

### 调试方法
1. 在n8n中查看执行日志
2. 使用测试脚本逐步测试
3. 检查HA日志确认API调用

## 📝 注意事项

1. **网络环境**: 确保n8n能访问Home Assistant
2. **设备状态**: 设备需要在线且可控制
3. **API限制**: 注意HA的API调用频率限制
4. **安全性**: 在生产环境中使用HTTPS和强密码

## 🔄 扩展功能

可以轻松扩展的功能：
- 添加更多设备
- 支持调光控制
- 添加定时任务
- 集成传感器数据
- 添加场景模式

## 📞 技术支持

如遇问题，请检查：
1. n8n执行日志
2. Home Assistant日志
3. 网络连接状态
4. 设备在线状态
