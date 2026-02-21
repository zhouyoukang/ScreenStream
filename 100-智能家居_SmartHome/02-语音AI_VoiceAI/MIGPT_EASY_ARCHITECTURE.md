# MIGPT-Easy 核心架构深度解析

> 从源码提炼的顶层思维和核心逻辑
> 源码已复制到: `migpt-easy-core/` (10个核心文件)

---

## 一、顶层设计思想

### 核心理念
**"让每个智能家居设备都成为独立的智能体(Agent)，小爱音箱作为专属管家统一调度。"**

### 三层决策链
```
用户语音 → 意图判断(三分支) → 执行 → TTS语音反馈
               │
               ├── HA关键词命中 → HomeAssistant API → 设备控制
               ├── AI关键词命中 → 大模型API(流式) → 智能回答
               └── 都不命中     → 小爱原生处理 → 原生回复
```

这是整个系统的**灵魂决策**：用关键词匹配做第一层路由，实现"无缝接入"——
用户不需要手动切换模式，说话方式自然区分了意图。

---

## 二、核心数据流

```
┌─────────────────────────────────────────────────────────────┐
│                    MIGPT-Easy 主循环                          │
│                                                              │
│  ┌──────────┐    50ms轮询     ┌──────────────┐              │
│  │ 小米API   │ ─────────────→ │ 时间戳对比    │              │
│  │ (micoapi) │ ←───────────── │ 新消息检测    │              │
│  └──────────┘                 └──────┬───────┘              │
│                                      │ 有新消息               │
│                               ┌──────▼───────┐              │
│                               │  意图路由器   │              │
│                               │ should_use_*  │              │
│                               └──┬───┬───┬───┘              │
│                    HA关键词│  AI关键词│  │原生               │
│                    ┌───────▼┐ ┌──▼────┐ ┌▼───────┐         │
│                    │HA处理  │ │AI处理 │ │小爱原生│          │
│                    │api_srv │ │V3流式 │ │        │          │
│                    └───┬────┘ └──┬────┘ └───┬────┘         │
│                        │         │           │               │
│                    ┌───▼─────────▼───────────▼────┐         │
│                    │     TTS播报 (do_tts)          │         │
│                    │  多设备广播 + 故障自动切换      │         │
│                    └──────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、七大核心模块

### 1. 意图路由器 (MIGPT.py:19-54)
```python
def should_use_ai(text):    # AI关键词: ["请","帮我","问一下","AI"]
def should_use_ha(text):    # HA关键词: 从config动态加载
def get_cleaned_input(text): # 去掉关键词，保留纯净意图
```
**设计精髓**: 关键词可通过GUI动态配置，实现零代码自定义触发逻辑。

### 2. 小米账号管理 (miaccount.py)
- 登录小米账号获取token
- 支持cookie持久化(~/.{user}.mi.token)
- 自动检测cookie过期并重新登录
- 多设备token独立管理

### 3. 小爱服务接口 (minaservice.py)
- `device_list()` — 获取账号下所有小爱设备
- `text_to_speech()` — 向指定设备发送TTS
- `text_to_speech_silent()` — 静默版本(减少日志噪音)
- `send_message()` — 向设备发送命令

### 4. 多设备管理 (MIGPT.py:94-364)
```python
class MiGPT:
    self.devices = []           # 所有设备列表
    self.selected_devices = []  # 已选择的设备索引
    self.device_cookies = {}    # 每设备独立cookie
    self.last_timestamps = {}   # 每设备独立时间戳
```
**核心能力**:
- 设备发现 → 用户选择(GUI菜单) → 多设备并行监听
- 消息广播: 一条命令同时发送到所有选中设备
- 故障转移: 主设备失败自动尝试备用设备
- ROM未响应重试: 指数退避 + 自动切换

### 5. AI对话引擎 (V3.py)
```python
class Chatbot:
    # 支持10+大模型API (OpenAI/DeepSeek/智谱/通义/Kimi/Claude...)
    # 统一接口: ask_stream(prompt, lock, stop_event)
    # 流式分割算法: 边生成边播报，减少80%延迟
    # Token计数: tiktoken精确控制上下文长度
    # 对话历史: 自动截断保持在max_tokens内
```

### 6. HomeAssistant集成 (api_server.py)
```python
# 两种控制方式:
send_ha_command(text)        # 文本指令 → HA text.set_value API
send_ha_voice_command(text)  # 语音指令 → HA conversation.process API

# OpenAI兼容API服务器 (Flask, 端口5001)
# 让HA可以把MIGPT当作OpenAI API调用
POST /v1/chat/completions → 转发到大模型 → 返回标准格式
```

### 7. 主循环 (MIGPT.py:1069-1148)
```python
async def run(self):
    # 1. 初始化(小米登录+设备发现+AI初始化)
    await self.init_all_data(session)
    
    # 2. 启动命令输入线程(非阻塞读取stdin)
    input_thread = Thread(target=self.input_reader)
    
    # 3. 启动命令处理协程
    command_task = create_task(self.command_handler())
    
    # 4. 50ms轮询主循环
    while self.running:
        if self.auto_process:
            await self.process_all_devices()  # 并行处理所有设备
        await asyncio.sleep(0.05)
```

---

## 四、关键创新点

### 1. NLP自动模式切换
传统方案: 手动开关AI模式 → 不实用，长期部署失败
MIGPT-Easy: 关键词自动判断 → 无缝共存，原生+AI+HA三模式

### 2. 流式分割播报
```
传统: 等待完整回答(5-10秒) → 一次性播报
MIGPT: 边生成边分割(标点断句) → 0.5秒开始播报
```

### 3. 打断机制
```python
await self.send_stop_command(device_idx)  # 立即打断小爱原生回复
# 然后再发送AI/HA的回答
```
关键: 在AI处理前先打断小爱，防止小爱的"我不太明白"和AI回答冲突。

### 4. 双向HA集成
```
方向1: 用户→小爱→MIGPT→HA API→设备
方向2: HA自动化→MIGPT API服务器(5001)→小爱TTS
```

---

## 五、文件依赖图

```
__main__.py (入口)
├── config.py (配置管理, 380行)
│   └── config.json (运行时配置)
├── MIGPT.py (核心引擎, 1311行)
│   ├── miaccount.py (小米账号)
│   ├── minaservice.py (小爱服务)
│   ├── V3.py (AI对话, 641行)
│   ├── api_server.py (HA集成, 544行)
│   └── config.py
├── config_gui.py (GUI配置界面, 37KB)
└── migpt.bat (Windows启动脚本)
```

**总代码量**: ~3100行 Python (不含GUI)

---

## 六、与ScreenStream的连接点

MIGPT-Easy 和 ScreenStream 可以在以下层面打通:

| 连接点 | MIGPT-Easy侧 | ScreenStream侧 |
|--------|-------------|----------------|
| **HA API** | 通过HA API控制设备 | 通过Intent/HTTP也能控制HA |
| **语音→手机** | 小爱语音指令 | 手机接收并执行 |
| **手机→语音** | API服务器接收命令 | ScreenStream POST到MIGPT |
| **设备状态** | 从HA获取状态 | 可在ScreenStream UI展示 |
| **场景联动** | 触发HA场景 | 触发手机自动化 |

### 潜在集成方案
```
ScreenStream前端 → "智能家居"面板
  ├── 设备控制: 直接调HA API
  ├── 语音控制: POST到MIGPT API(5001)
  ├── 场景触发: POST到n8n webhook(5678)
  └── 设备状态: 轮询HA API显示
```

---

## 七、源码快速导航

| 功能 | 文件 | 行号 | 说明 |
|------|------|------|------|
| 意图判断 | MIGPT.py | 19-54 | should_use_ai/ha/get_cleaned |
| 类初始化 | MIGPT.py | 94-128 | 多设备管理状态 |
| 小米登录 | MIGPT.py | 147-298 | init_all_data |
| TTS播报 | MIGPT.py | 365-468 | do_tts (多设备+故障转移) |
| 消息轮询 | MIGPT.py | 470-533 | get_latest_ask_from_xiaoai |
| 消息解析 | MIGPT.py | 535-618 | get_last_timestamp_and_record |
| 设备输入处理 | MIGPT.py | 655-864 | process_device_input (三分支路由) |
| 主循环 | MIGPT.py | 1069-1148 | run() |
| AI引擎 | V3.py | 10-641 | Chatbot类 (流式对话) |
| HA文本指令 | api_server.py | 59-123 | send_ha_command |
| HA语音指令 | api_server.py | 126-200 | send_ha_voice_command |
| API服务器 | api_server.py | 200+ | Flask OpenAI兼容 |
