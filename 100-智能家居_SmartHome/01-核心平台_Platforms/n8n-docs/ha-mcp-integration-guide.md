# 🏠 Home Assistant MCP 集成指南

## 📋 概述

本指南将帮你通过 n8n 实现 Home Assistant 的 MCP (Model Context Protocol) 集成，让你能够通过统一的 API 接口控制智能家居设备和接收设备数据。

## 🎯 功能特性

### ✅ 已实现功能
- **设备控制**: 开关、灯光、风扇等设备的控制
- **状态查询**: 获取所有设备的实时状态
- **场景控制**: 预定义场景的一键执行
- **设备映射**: 友好名称到实体ID的自动映射
- **错误处理**: 完善的错误处理和响应格式化

### 🔧 支持的设备类型
- **Sonoff 开关**: 5个智能开关设备
- **照明设备**: 飞利浦灯带、技嘉RGB灯
- **环境控制**: 小米风扇、小米开关

### 🎬 预定义场景
- **睡眠模式**: 暖光低亮度 + 低速风扇
- **工作模式**: 冷白光高亮度 + 中速风扇  
- **聚会模式**: 彩色灯光 + 高速风扇

## 🚀 快速开始

### 1. 导入工作流

```bash
# 启动 n8n
npm start

# 在 n8n 界面中导入工作流
# 文件: workflows/ha-mcp-integration.json
```

### 2. 验证连接

```bash
# 运行测试脚本
node test-ha-mcp-integration.js
```

### 3. 基本使用

#### 获取设备状态
```bash
curl -X GET "http://localhost:5678/webhook/ha-mcp-status"
```

#### 控制设备
```bash
# 切换 Sonoff 开关
curl -X POST "http://localhost:5678/webhook/ha-mcp-control" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "control_device",
    "device": "sonoff_switch_4",
    "command": "toggle"
  }'

# 调节灯光亮度
curl -X POST "http://localhost:5678/webhook/ha-mcp-control" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "control_device",
    "device": "philips_strip",
    "command": "set_brightness",
    "brightness": 80
  }'
```

#### 执行场景
```bash
# 睡眠模式
curl -X POST "http://localhost:5678/webhook/ha-mcp-scene" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "scene_control",
    "scene": "sleep_mode"
  }'
```

## 📡 API 接口文档

### 设备控制接口

**端点**: `POST /webhook/ha-mcp-control`

**请求格式**:
```json
{
  "action": "control_device",
  "device": "设备友好名称",
  "command": "控制命令",
  "参数": "值"
}
```

**支持的设备**:
- `sonoff_switch_4`: Sonoff 四号开关
- `sonoff_switch_5`: Sonoff 五号开关  
- `sonoff_center_plug`: Sonoff 中央插头
- `sonoff_outdoor_plug`: Sonoff 户外插头
- `sonoff_bed_plug`: Sonoff 床插头
- `philips_strip`: 飞利浦灯带
- `gigabyte_rgb`: 技嘉RGB灯
- `xiaomi_fan`: 小米风扇
- `xiaomi_switch`: 小米开关

**支持的命令**:
- `turn_on`: 打开设备
- `turn_off`: 关闭设备
- `toggle`: 切换设备状态
- `set_brightness`: 设置亮度 (0-100)
- `set_color`: 设置颜色 [R, G, B]
- `set_fan_speed`: 设置风扇速度 (0-100)

### 状态查询接口

**端点**: `GET /webhook/ha-mcp-status`

**响应格式**:
```json
{
  "status": "success",
  "action": "get_status",
  "total_entities": 150,
  "my_devices_count": 10,
  "devices": [
    {
      "entity_id": "switch.sonoff_10022dede9_1",
      "friendly_name": "Sonoff 四号开关",
      "state": "on",
      "device_class": "switch",
      "last_changed": "2025-01-08T15:30:00Z"
    }
  ],
  "timestamp": "2025-01-08T15:30:00Z"
}
```

### 场景控制接口

**端点**: `POST /webhook/ha-mcp-scene`

**请求格式**:
```json
{
  "action": "scene_control",
  "scene": "场景名称"
}
```

**可用场景**:
- `sleep_mode`: 睡眠模式
- `work_mode`: 工作模式
- `party_mode`: 聚会模式

## 🔧 配置说明

### Home Assistant 令牌

当前使用的令牌:
```
REDACTED_HA_TOKEN_2
```

### 设备映射配置

在工作流的 `mcp-request-processor` 节点中，你可以修改设备映射:

```javascript
const deviceMapping = {
  // 添加新设备
  'new_device_name': 'switch.new_entity_id',
  
  // 修改现有设备
  'sonoff_switch_4': 'switch.sonoff_10022dede9_1'
};
```

### 场景配置

在同一节点中，你可以添加或修改场景:

```javascript
const scenes = {
  'custom_scene': {
    actions: [
      { 
        entity_id: 'light.philips_strip3_12ad_light', 
        service: 'turn_on', 
        brightness: 100, 
        rgb_color: [255, 255, 255] 
      }
    ]
  }
};
```

## 🧪 测试和调试

### 运行完整测试
```bash
node test-ha-mcp-integration.js
```

### 单独测试 Home Assistant 连接
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8123/api/
```

### 查看 n8n 执行日志
1. 打开 n8n 界面: http://localhost:5678
2. 进入工作流执行历史
3. 查看详细执行日志

## 🔍 故障排除

### 常见问题

1. **连接失败**
   - 检查 Home Assistant 是否运行在 localhost:8123
   - 验证令牌是否有效
   - 确认防火墙设置

2. **设备控制失败**
   - 检查设备实体ID是否正确
   - 验证设备是否在线
   - 查看 Home Assistant 日志

3. **n8n 工作流错误**
   - 检查工作流是否已激活
   - 验证 webhook 路径是否正确
   - 查看执行历史中的错误信息

### 调试技巧

1. **启用详细日志**
   ```bash
   # 在 n8n 中启用调试模式
   N8N_LOG_LEVEL=debug npm start
   ```

2. **使用 Postman 测试**
   - 导入 API 集合进行测试
   - 验证请求格式和响应

3. **检查 Home Assistant 状态**
   ```bash
   # 直接查询 HA API
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8123/api/states
   ```

## 🚀 扩展功能

### 添加新设备类型

1. 在 `deviceMapping` 中添加设备
2. 在 `actionTypes` 中添加支持的命令
3. 测试新设备的控制功能

### 创建自定义场景

1. 在 `scenes` 对象中定义新场景
2. 指定每个动作的参数
3. 通过 API 测试场景执行

### 集成外部系统

1. 添加新的 webhook 端点
2. 实现数据转换逻辑
3. 配置错误处理

---

## 📞 支持

如果遇到问题，请:
1. 查看本文档的故障排除部分
2. 运行测试脚本诊断问题
3. 检查 n8n 和 Home Assistant 的日志
4. 参考 Home Assistant 官方文档

**祝你使用愉快！** 🎉
