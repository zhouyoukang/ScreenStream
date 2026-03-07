# Voxta AI 集成指南

> VAM + Voxta + LLM + TTS/STT 完整中文配置

## 架构概览

```
用户语音 → STT(Vosk/Whisper) → 文本 → LLM(千问/GPT) → 回复文本 → TTS(EdgeTTS/火山) → 语音输出
                                                                          ↕
                                                                     Voxta引擎
                                                                          ↕
                                                                     VAM角色动画
```

## 本地安装

### Voxta路径

- 主程序: `F:\vam1.22\Voxta\Voxta.DesktopApp.exe`
- 服务器: `F:\vam1.22\Voxta\Voxta.Server.exe`
- 数据库: `F:\vam1.22\Voxta\Data\Voxta.sqlite.db`
- 配置: `F:\vam1.22\Voxta\appsettings.json`
- Web UI: http://localhost:5384

### 启动顺序

1. **EdgeTTS Server** (TTS后端)
2. **Voxta Server** (核心引擎)
3. **VAM** (3D前端)

```powershell
# 使用启动器
python tools/vam_launcher.py --full
```

## TTS 配置 (语音合成)

### EdgeTTS (推荐，免费)

```python
# 服务器: F:\vam1.22\Voxta\edge_tts_server.py
# 端口: 默认 5050

# 中文推荐声音
# 女声: zh-CN-XiaoxiaoNeural, zh-CN-XiaohanNeural, zh-CN-XiaomengNeural
# 男声: zh-CN-YunxiNeural, zh-CN-YunjianNeural
# 粤语: zh-HK-HiuMaanNeural
# 台湾: zh-TW-HsiaoChenNeural
```

Voxta配置:
- Service Type: Custom TTS
- URL: `http://localhost:5050/api/tts`
- Voice: `zh-CN-XiaoxiaoNeural`

### 火山引擎 (最佳中文质量)

- 配置文件: `F:\vam1.22\Voxta\volcano_tts_config.json`
- 需要API Key (见 secrets.env)
- 声音选择: 参见火山引擎控制台

### Kokoro TTS (离线)

- 内置于Voxta Modules中
- 路径: `F:\vam1.22\Voxta\Voxta\Modules\`
- 优点: 完全离线，无需网络
- 缺点: 中文质量一般

## STT 配置 (语音识别)

### Vosk (离线中文)

```json
{
  "model": "vosk-model-cn-0.22",
  "sampleRate": 16000,
  "language": "zh-CN"
}
```

- 模型下载: https://alphacephei.com/vosk/models
- 推荐模型: `vosk-model-cn-0.22` (1.3GB, 中文)
- 安装脚本: `F:\vam1.22\Scripts\Voxta\` 中的Vosk相关脚本

### Whisper (高质量)

- 模型: medium 或 large-v3
- 支持: 多语言自动检测
- 缺点: 需要GPU，延迟较高
- 配置: Voxta Settings → STT → Whisper

## LLM 配置

### text-generation-webui (本地)

- 路径: `F:\vam1.22\text-generation-webui\`
- 启动: `start_windows.bat`
- API: http://localhost:5000/v1/
- 兼容OpenAI API格式

Voxta配置:
```json
{
  "serviceType": "OpenAI",
  "url": "http://localhost:5000/v1/",
  "model": "模型名称",
  "maxTokens": 200,
  "temperature": 0.7
}
```

### one-api (多模型网关)

- 数据库: `F:\vam1.22\one-api.db`
- 统一入口，可接入多个LLM后端

### 阿里云千问

- 通过one-api或直接配置
- API Key: 见 secrets.env
- 模型: qwen-turbo, qwen-plus

### OpenRouter

- 聚合多个云端LLM
- 注册: https://openrouter.ai/
- 支持GPT-4, Claude, Llama等

## 中文角色配置

### 系统提示词模板

```
你是{角色名}，一个{性格描述}的角色。

## 角色设定
- 年龄: {年龄}
- 性格: {性格特点}
- 说话风格: {语言风格}
- 背景: {背景故事}

## 行为准则
- 始终使用中文回复
- 回复简洁自然，像真人对话
- 保持角色一致性
- 适当使用语气词和表情
- 回复长度控制在50-100字

## 示例对话
用户: 你好啊
{角色名}: 嗨~你来了呀！今天心情怎么样？
```

### 配置文件

- 模板: `configs/voxta_chinese.json`
- 小雅角色: `F:\vam1.22\Voxta\chinese_character_xiaoya.json`
- 系统提示词集: `F:\vam1.22\Voxta\chinese_system_prompts.txt`

## VAM 内集成

### 方式1: Voxta VAM Plugin

Voxta提供专用VAM插件，直接在VAM内加载:

1. 将Voxta VAM插件放入 `AddonPackages/`
2. 在场景中添加插件到Person Atom
3. 配置Voxta服务器地址 (`localhost:5384`)

### 方式2: BrowserAssist

通过BrowserAssist v45加载Voxta Web UI:

1. 在VAM中添加BrowserAssist插件
2. 导航到 `http://localhost:5384`
3. 在VAM内直接操作Voxta界面

### 方式3: Scripter 脚本

通过HTTP API与Voxta交互 (见 `docs/plugin-dev-guide.md`)

## 性能优化

| 组件 | 建议 | 延迟目标 |
|------|------|---------|
| STT | Vosk离线 (GPU无要求) | <500ms |
| LLM | 本地小模型 或 云端API | <2s |
| TTS | EdgeTTS (网络) / Kokoro (离线) | <1s |
| 总计 | — | <3-4s |

### 降低延迟的技巧

1. **LLM**: 使用较小模型 (7B-13B) 或云端API
2. **TTS**: EdgeTTS延迟最低，火山引擎次之
3. **STT**: Vosk离线最快，Whisper需GPU
4. **流式输出**: 启用Voxta流式TTS，边生成边播放
5. **VAM优化**: 降低渲染质量，保证CPU给AI用

## 故障排查

| 问题 | 检查 | 解决 |
|------|------|------|
| Voxta无法启动 | 端口5384占用? | 杀占用进程 |
| TTS无声 | EdgeTTS Server运行? | 重启TTS服务 |
| STT不识别 | 麦克风权限? Vosk模型? | 检查音频设备+模型路径 |
| LLM超时 | text-gen-webui运行? | 检查5000端口 |
| VAM无响应 | Voxta插件加载? | 检查插件日志 |
