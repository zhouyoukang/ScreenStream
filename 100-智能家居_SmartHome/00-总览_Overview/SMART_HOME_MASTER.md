# 智能家居全景总览 (Smart Home Master Document)

> 最后更新: 2026-02-21 | 维护者: zhouyoukang (AIOTVR)

## 核心长期目标

**优化当前世界范围内的智能家居相关内容的体验。**

以用户现有的硬件+软件生态为基础，打造一个：
- **更智能**：AI驱动的场景自动化，从被动响应到主动预测
- **更统一**：一个入口控制所有设备，消除平台碎片化
- **更沉浸**：VR/AR + 语音 + 手机 多模态交互
- **更开放**：基于开源生态，可复制推广到全球用户

---

## 一、硬件设备清单

### Sonoff 智能开关 (×5)
| 设备名 | Entity ID | 用途 |
|--------|-----------|------|
| 四号开关 | `switch.sonoff_10022dede9_1` | 主控开关 |
| 五号开关 | `switch.sonoff_10022dedc7_1` | 备用开关 |
| 中央插头 | `switch.sonoff_10022cf71d` | 中央电源 |
| 户外插头 | `switch.sonoff_100235142b_1` | 户外电源 |
| 床插头 | `switch.sonoff_10022cf6a2` | 床头电源 |

### 照明系统 (×3)
| 设备名 | Entity ID | 能力 |
|--------|-----------|------|
| 飞利浦灯带 | `light.philips_strip3_12ad_light` | RGB+亮度+呼吸 |
| 技嘉RGB | `light.b650m_aorus_elite_ax_0` | RGB灯效 |
| 床底灯 | (Node-RED控制) | 定时开关 |

### 环境控制 (×2)
| 设备名 | Entity ID | 能力 |
|--------|-----------|------|
| 小米风扇P221 | `fan.dmaker_p221_5b47_fan` | 多档风速 |
| 小米开关 | `switch.xiaomi_miio_switch` | 开关控制 |

### AI语音设备
- **小爱音箱Pro** — 语音交互核心，通过MIGPT接入大模型
- **豆包/Kimi通话系统** — AI语音对话
- **网易云音乐** — 音乐播放控制

---

## 二、软件平台架构

```
┌──────────────────────────────────────────────────────────────┐
│                    n8n 智能编排层 (5678)                       │
│   AI决策 · 跨平台协调 · 外部集成 · 数据分析                    │
└────────────────────────┬─────────────────────────────────────┘
                         │ REST API / Webhook
┌────────────────────────┴─────────────────────────────────────┐
│                   自动化引擎层                                 │
│   Node-RED (1880)  ←→  Home Assistant (8123)                 │
│   设备控制流程           状态管理+实体注册                      │
└────────────────────────┬─────────────────────────────────────┘
                         │ Zigbee / WiFi / HTTP
┌────────────────────────┴─────────────────────────────────────┐
│                     设备+AI层                                  │
│   Sonoff · 小米 · 飞利浦 · 小爱(MIGPT) · 豆包 · 音乐          │
└──────────────────────────────────────────────────────────────┘
```

### 平台详情

| 平台 | 端口 | 角色 | 状态 |
|------|------|------|------|
| Home Assistant | 8123 | 设备状态管理+实体注册 | ✅ 运行中 |
| Node-RED | 1880 | 设备控制自动化流程 | ✅ 运行中 |
| n8n | 5678 | 上层编排+AI增强+外部集成 | ⚠️ 已部署未充分利用 |
| MIGPT-Easy | - | 小爱音箱+大模型接入 | ✅ 核心项目 |
| ha-chat-card | - | HA AI聊天前端组件 | ✅ 已集成 |
| ScreenStream | 8080+ | 手机远程控制(含智能家居Intent) | ✅ 运行中 |

---

## 三、已有自动化场景

| 场景 | 触发方式 | 动作 |
|------|----------|------|
| 睡眠模式 | 语音/定时 | 关音乐+开床灯+关豆包 |
| 聚会模式 | 语音 | 彩灯+高速风扇+音乐 |
| 阅读模式 | 语音 | 白光+低速风扇 |
| 浪漫模式 | 语音 | 暖光+呼吸效果 |
| 专注模式 | 语音 | 冷白光+中速风扇 |
| 定时开灯 | 21:00 | 开启床底灯 |
| 定时关灯 | 07:00 | 关闭床底灯 |
| 能耗监控 | 持续 | 实时功率+成本计算 |
| 互斥控制 | 自动 | 开4号自动关5号 |

---

## 四、项目资产地图

### ⭐⭐⭐⭐⭐ 核心项目（必须保留+持续开发）

| 项目 | 位置 | 说明 |
|------|------|------|
| **MIGPT-Easy** | `e:\migpt-easy\` | 用户自研，小爱+多模型+HA集成，GitHub已发布 |
| **n8n 工作空间** | `e:\github\n8n\` | 智能编排层，含3+个智能家居工作流+29篇文档 |
| **ScreenStream_v2** | 当前工作区 | 手机远程控制，已有Intent/设备控制能力 |

### ⭐⭐⭐⭐ 重要参考（保留参考，不需主动开发）

| 项目 | 位置 | 说明 |
|------|------|------|
| **mi-gpt 4.2.0** | `e:\mi-gpt-4.2.0\` | MIGPT上游项目(idootop)，Node.js版 |
| **ha-chat-card** | `e:\github\ha-chat-card\` | HA AI聊天组件(knoop7)，含语音识别+TTS |

### ⭐⭐⭐ 探索方向（有价值但未深入）

| 项目 | 位置 | 说明 |
|------|------|------|
| **Immersive-Home** | `e:\github\AIOT\Immersive-Home\` | VR+智能家居(Godot+Quest)，参考方向 |

### ⭐ 重复/过时内容（建议清理）

| 内容 | 位置 | 原因 |
|------|------|------|
| MIGPT副本1 | `e:\github1\MIGPT最新\` | 编译版，已有源码 |
| MIGPT副本2 | `e:\github1\migpt-easy(4)\` | 旧版本 |
| MIGPT副本3 | `e:\github1\migpt-easy-ha\` | 重复 |
| MIGPT副本4 | `e:\github\migpt-easy-ha\` | 重复 |
| MIGPT副本5 | `e:\github\MIGPT_Release_v5.1\` | 发布包，可在GitHub下载 |
| MIGPT副本6 | `e:\AI助手升级版\` | 最早期版本 |
| ha-chat-card.js | `e:\github\AIOT\ha-chat-card.js` | 单文件副本(146KB) |
| 浏览器下载 | `e:\浏览器下载位置\HassWP-*.zip` | 安装包，可重新下载 |

---

## 五、n8n 智能家居工作流

| 工作流文件 | 功能 | 状态 |
|-----------|------|------|
| `smart-home-simple.json` | 基础设备控制(状态查询+互斥开关) | ✅ |
| `smart-home-ai-orchestrator.json` | AI增强场景(天气自适应+AI决策) | ✅ |
| `ha-device-control.json` | HA设备发现+控制+高级灯光 | ✅ |
| `ha-simple-control.json` | 简化HA控制 | ✅ |
| `init-smart-home-db.sql` | 智能家居数据库初始化 | ✅ |

---

## 六、关键配置信息

### Home Assistant
- **地址**: `http://localhost:8123` (本地) / `http://192.168.31.228:8123` (局域网)
- **Token**: 见 `e:\github\n8n\.env`
- **协议**: Zigbee (Sonoff), WiFi (小米), HTTP API

### n8n
- **地址**: `http://localhost:5678`
- **凭据**: admin / admin123
- **Webhook基路径**: `http://localhost:5678/webhook/`

### MIGPT-Easy
- **配置文件**: `e:\migpt-easy\config.json`
- **API服务器**: 端口5001
- **GitHub**: `zhouyoukang/MIGPT-easy`

---

## 七、短期行动计划

### Phase 1: 整合与清理 (本周)
- [x] 扫描所有智能家居资产
- [x] 建立统一文件夹结构
- [ ] 清理6个MIGPT重复副本
- [ ] 验证n8n工作流可用性
- [ ] 确认HA+Node-RED当前状态

### Phase 2: 体验优化 (下周)
- [ ] 评估当前自动化场景的实际使用频率
- [ ] 用n8n AI编排层增强最常用场景
- [ ] 将ScreenStream手机控制与HA打通
- [ ] 测试ha-chat-card语音控制体验

### Phase 3: 能力扩展 (持续)
- [ ] MIGPT-Easy v2: 更智能的意图识别
- [ ] VR智能家居控制原型(Immersive-Home参考)
- [ ] 跨设备场景联动(手机+音箱+PC)
- [ ] 能耗数据分析和优化建议

---

## 八、S50 智能家居集成（2026-02-21 新增）

### 已实现

| 组件 | 位置 | 说明 |
|------|------|------|
| **平台API研究** | `00-总览_Overview/PLATFORM_API_RESEARCH.md` | 10平台API接入深度研究(600+行) |
| **统一网关** | `07-网关服务_Gateway/gateway.py` | FastAPI服务(端口8900)，代理HA+涂鸦 |
| **ScreenStream路由** | `InputRoutes.kt` /smarthome/* | 8个新API端点 |
| **前端面板** | `index.html` Alt+H | 设备列表+状态+开关+亮度+场景 |
| **n8n工作流** | `01-核心平台/n8n-workflows/` | 智能家居Webhook控制模板 |
| **验证脚本** | `07-网关服务_Gateway/verify_platforms.py` | 全平台连通性检测 |

### 使用方法

```bash
# 1. 配置网关
cd 100-智能家居_SmartHome/07-网关服务_Gateway/
cp .env.example .env   # 填入 HA_TOKEN 等
pip install -r requirements.txt

# 2. 启动网关
python gateway.py      # http://127.0.0.1:8900

# 3. 手机端 adb reverse（让手机访问PC网关）
adb reverse tcp:8900 tcp:8900

# 4. 浏览器打开 ScreenStream → Alt+H 打开智能家居面板
```

---

## 九、本文件夹结构

```
100-智能家居_SmartHome/
├── 00-总览_Overview/
│   ├── SMART_HOME_MASTER.md          ← 你正在看的这个文件
│   ├── PLATFORM_API_RESEARCH.md      ← 10平台API接入研究
│   └── PLATFORM_EXPANSION_STRATEGY.md ← 多平台扩展策略
├── 01-核心平台_Platforms/
│   ├── n8n-docs/                      ← n8n智能家居文档精选
│   └── n8n-workflows/                 ← n8n智能家居工作流(含gateway-control)
├── 02-语音AI_VoiceAI/
│   ├── MIGPT_EASY_OVERVIEW.md         ← MIGPT-Easy核心概述
│   └── MI_GPT_UPSTREAM.md             ← 上游mi-gpt参考
├── 03-设备与场景_DevicesScenes/
│   └── (设备清单和场景配置)
├── 04-前端组件_Frontend/
│   └── HA_CHAT_CARD_OVERVIEW.md       ← ha-chat-card概述
├── 05-VR探索_VR/
│   └── IMMERSIVE_HOME_OVERVIEW.md     ← VR智能家居参考
├── 06-清理报告_Cleanup/
│   └── CLEANUP_REPORT.md              ← 重复/过时内容清理建议
└── 07-网关服务_Gateway/               ← NEW: 统一API网关
    ├── gateway.py                     ← FastAPI服务(HA代理+涂鸦)
    ├── verify_platforms.py            ← 平台连通性验证
    ├── requirements.txt               ← Python依赖
    ├── .env.example                   ← 配置模板
    └── start.bat                      ← 一键启动
```
