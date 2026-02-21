# ha-chat-card 概述

> 源项目: `e:\github\ha-chat-card\` | 原作者: knoop7
> Home Assistant AI聊天卡片前端组件

## 定位

为Home Assistant提供AI聊天界面的Web Component，支持语音交互、多Agent、深度思考模式。

## 核心特性

- **AI聊天界面** — 可嵌入HA仪表盘的聊天卡片
- **语音识别** — 长按发送按钮语音输入（Android/iOS/Chrome）
- **唤醒词** — 自定义唤醒词，低延迟识别
- **多Agent** — 最多3个AI Agent并行，智能切换+自动降级
- **TTS** — 浏览器播放 / HA服务调用
- **深度思考** — 多维问题分析+思考过程可视化

## 配置示例

```yaml
type: custom:ha-chat-card
agent_id: conversation.home_assistant
agents:
  - conversation.home_assistant
voice_recognition: true
wake_word: 'hey assistant'
language: 'zh-cn'
deep_think: true
tts_mode: 'service'
tts_engine: 'tts.google_translate'
```

## 安装

1. 复制 `ha-chat-card.js` (146KB) 到 HA的 `www/` 目录
2. 在 `configuration.yaml` 添加:
```yaml
frontend:
  extra_module_url:
    - /local/ha-chat-card.js
```

## 关键文件

| 文件 | 大小 | 功能 |
|------|------|------|
| `ha-chat-card.js` | 146KB | 主组件（生产版） |
| `speech-recognition.js` | 17KB | 语音识别模块 |
| `index.html` | 11KB | 独立测试页面 |
| `voice_server/` | - | 语音服务端 |
| `funasr_ws/` | - | FunASR WebSocket语音识别 |

## 与生态的关系

```
用户 → ha-chat-card (语音/文字) → HA Conversation Agent → AI模型
                                                        → 设备控制
```

## 用户环境中的副本

- `e:\github\ha-chat-card\` — 主项目（含.git）
- `e:\github1\ha-chat-card\` — 副本
- `e:\github\AIOT\ha-chat-card.js` — 单文件副本（可删）

## 优化方向

- [ ] 与MIGPT-Easy的AI能力合并（统一AI后端）
- [ ] 自定义场景快捷按钮
- [ ] 设备状态实时显示
