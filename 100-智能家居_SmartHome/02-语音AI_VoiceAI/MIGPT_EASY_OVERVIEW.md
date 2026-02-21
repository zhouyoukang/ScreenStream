# MIGPT-Easy 核心概述

> 源项目: `e:\migpt-easy\` | GitHub: `zhouyoukang/MIGPT-easy`
> 用户自研项目，智能家居语音AI核心

## 定位

将小爱音箱从"人工智障"升级为真正的AI智能家居中枢。通过接入ChatGPT等大模型，实现：
- 自然语言理解和多轮对话
- HomeAssistant设备语音控制
- 多设备同步管理
- 流式对话(减少80%延迟)

## 核心架构

```
用户语音 → 小爱音箱 → MIGPT-Easy → 大模型API(GPT/DeepSeek/通义/智谱...)
                                  ↓
                          HomeAssistant API → 智能设备控制
```

## 关键文件

| 文件 | 功能 |
|------|------|
| `MIGPT.py` | 主程序(60KB)，设备监听+AI调用+HA控制 |
| `V3.py` | ChatGPT API封装，流式传输 |
| `miaccount.py` | 小米账号登录管理 |
| `minaservice.py` | 小爱服务API接口 |
| `api_server.py` | HomeAssistant兼容API服务器(端口5001) |
| `config_gui.py` | 图形化配置界面 |
| `config.json` | 运行时配置 |
| `migpt.bat` | Windows启动脚本(含菜单) |

## 支持的大模型

OpenAI / DeepSeek / 智谱AI(GLM) / 通义千问 / Moonshot(Kimi) / Claude / 方舟 / Siliconflow

## HomeAssistant集成

```json
{
  "homeassistant": {
    "enabled": true,
    "url": "http://your-ha-ip:8123",
    "token": "long-lived-access-token",
    "device_mapping": {
      "客厅灯": "light.living_room_light",
      "卧室灯": "light.bedroom_light"
    }
  }
}
```

触发方式：
- 语音关键词（如"小周，把客厅的灯打开"）
- 文本控制（通过HA实体）

## 核心创新

1. **自研大模型调用算法** — NLP自动判断是否需要调用大模型，无需手动切换
2. **流式分割算法** — 不等完整回复，边生成边播报
3. **多设备广播** — 一条指令控制所有小爱设备
4. **双向控制闭环** — 小爱→HA→设备，HA→小爱→语音反馈

## 与当前生态的关系

```
MIGPT-Easy ←→ Home Assistant ←→ n8n编排层
     ↑              ↑               ↑
  语音入口       设备管理        智能决策
```

## 下一步优化方向

- [ ] 接入更多设备类型(摄像头/传感器/扫地机)
- [ ] 多房间音箱协同(不同房间不同响应)
- [ ] 上下文感知(时间+位置+历史)
- [ ] 与ScreenStream打通(手机→小爱→设备)
