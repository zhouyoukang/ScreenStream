# n8n 智能编排平台概述

> 源项目: `e:\github\n8n\` | 端口: 5678
> 智能家居的"大脑层"，负责跨平台编排和AI增强

## 定位

在 Home Assistant(设备管理) 和 Node-RED(设备控制) 之上，提供：
- 统一API网关
- 跨系统协调
- AI驱动决策
- 外部服务集成
- 数据分析和报告

## 已有的智能家居工作流

### 1. smart-home-simple.json
**功能**: 基础设备控制 — 状态查询 + 互斥开关(4号/5号联动)
**Webhook**: `POST /webhook/smart-home`
```json
{"action": "status"}
{"action": "control", "device": "4"}
```

### 2. smart-home-ai-orchestrator.json
**功能**: AI增强场景 — 天气自适应 + 活动感知 + 智能分析
**Webhook**: `POST /webhook/unified-scene`, `POST /webhook/ai-scene-adjust`, `POST /webhook/smart-analysis`
```json
{"scene": "morning_routine", "parameters": {"weather_adaptive": true}}
{"ai_analysis": "用户正在创作", "auto_adjust": true}
{"analysis_type": "energy_optimization", "time_range": "last_7_days"}
```

### 3. ha-device-control.json
**功能**: HA设备发现 + 精细控制 + 高级灯光(亮度/颜色)
**Webhook**: `POST /webhook/ha-control`
```json
{"action": "get_status", "entity_id": "switch.living_room"}
{"action": "control", "entity_id": "light.bedroom", "command": "on", "brightness": 128}
```

### 4. ha-simple-control.json
**功能**: 简化版HA控制，快速开关设备

## 文档索引（已复制到 n8n-docs/）

| 文档 | 内容 |
|------|------|
| `smart-home-integration-strategy.md` | 完整接入策略+三层架构+实施路线图 |
| `smart-home-control-guide-zh.md` | 中文使用指南(状态查询+互斥控制) |
| `ha-integration-guide.md` | HA集成完整指南(设备发现+控制+测试) |
| `ha-mcp-integration-guide.md` | MCP协议集成(9设备+3场景+API文档) |
| `personalized-automation-analysis.md` | 个性化自动化深度分析+AI增强建议 |

## 启动方式

```bash
# 在 e:\github\n8n\ 目录
npm start
# 访问 http://localhost:5678 (admin/admin123)
```

## 当前状态评估

| 维度 | 状态 | 说明 |
|------|------|------|
| 部署 | ✅ | Docker/本地均可用 |
| 工作流 | ✅ | 4个智能家居工作流已创建 |
| HA集成 | ⚠️ | Token已配置，需验证连通性 |
| AI增强 | ⚠️ | 工作流已设计，需实测效果 |
| 实际使用 | ❌ | 文档齐全但日常使用率低 |

## 优先行动

1. **验证n8n→HA连通性** — `curl http://localhost:5678/webhook/smart-home -d '{"action":"status"}'`
2. **测试基础场景控制** — 通过webhook触发睡眠/专注模式
3. **接入日常使用** — 创建快捷方式/定时触发
