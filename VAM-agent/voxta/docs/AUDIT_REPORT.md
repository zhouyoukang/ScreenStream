# VAM-AI 五感审计报告

> 审计时间: 2026-03-04 02:00 (v1) / 02:45 (v2-SignalR) / 12:38 (v3-隔离审计) / 12:52 (v4-深度审计)
> 审计脚本: `tools/_audit.py` + `tools/_audit2.py`

## 一、视 (文件完整性) — 9/9 PASS

| 文件 | 路径 | 状态 |
|------|------|------|
| VAM主程序 | `F:\vam1.22\VAM版本\vam1.22.1.0\VaM.exe` | ✅ |
| Voxta服务端 | `F:\vam1.22\Voxta\Active\Voxta.Server.exe` | ✅ |
| Voxta桌面端 | `F:\vam1.22\Voxta\Active\Voxta.DesktopApp.exe` | ✅ |
| Voxta配置 | `F:\vam1.22\Voxta\Active\appsettings.json` | ✅ |
| Voxta数据库 | `F:\vam1.22\Voxta\Active\Data\Voxta.sqlite.db` | ✅ |
| TextGen启动脚本 | `F:\vam1.22\text-generation-webui\start_windows.bat` | ✅ |
| EdgeTTS服务器 | `F:\vam1.22\EdgeTTS\voxta_edge_tts_server.py` | ✅ |
| Scripter插件 | `F:\vam1.22\scripter.github\AcidBubbles.Scripter1.21.var` | ✅ |
| one-api数据库 | `F:\vam1.22\one-api-data\one-api.db` | ✅ |

## 二、听 (服务状态) — 4/5 在线 (v3实测)

| 端口 | 服务 | 状态 | 进程 | 内存 |
|------|------|------|------|------|
| — | VaM | ✅ 运行 | PID 31388 | 703MB |
| :5050 | EdgeTTS | ✅ OPEN | PID 50524 | 53MB |
| :5384 | Voxta Server | ✅ OPEN | PID 17492 | 371MB |
| :3000 | one-api | ✅ OPEN | — | — |
| :7860 | TextGen WebUI | ⬇ CLOSED | — | 非主力(DashScope为主) |

## 三、触 (DB完整性) — v3修复后

### 表统计

| 表 | v2行数 | v3行数 | 变化 |
|----|--------|--------|------|
| Characters | 6→8(重复) | 6 | ✅ 删除2重复 |
| ChatMessages | 351 | 246 | — |
| Chats | 14→64→69 | 52 | ✅ v4删除17空聊天 |
| Modules | 15 | 15 | — |
| Presets | 19 | 19 | — |
| MemoryBooks | 3→6 | 6 | ✅ Owner规范化 |
| Scenarios | 2 | 2 | — |

### 角色清单 (6个，无重复)

| 角色 | ID | 语言 | TTS |
|------|-----|------|-----|
| 小雅 | 67E139A4-...-BB1 | zh-CN | WindowsSpeech Huihui |
| George | 6227DC38-... | en-US | F5TTS |
| Male Narrator | 397F9094-... | en-US | F5TTS |
| Voxta | 35C74D75-... | en-US | F5TTS |
| 香草 | 67E139A4-...-BB2 | zh-CN | WindowsSpeech Huihui |
| Catherine | 575B8203-...-CFE | zh-CN | WindowsSpeech Huihui |

### 模块状态 (15个: 10 ON / 5 OFF)

| 状态 | ServiceName | 备注 |
|------|-------------|------|
| ON | BuiltInAudioRms | 音频RMS检测 |
| ON | BuiltInReplyPrefixing | 回复前缀 |
| ON | BuiltInSimpleMemory | 简单记忆 |
| ON | BuiltInTextReplacements | 文本替换 |
| ON | NAudio | 音频处理 |
| ON | OpenAICompatible | DashScope qwen-plus |
| ON | WindowsSpeech | 中文TTS主力 |
| ON | Vosk | 离线STT |
| ON | Silero | 英文TTS |
| ON | F5TTS | 高质量TTS |
| OFF | WhisperLive | 已禁用 |
| OFF | Deepgram | 已禁用(付费) |
| OFF | OpenAI | 已禁用(付费) |
| OFF | TextToSpeechHttpApi | 火山引擎(已禁用) |
| OFF | TextToSpeechHttpApi | Docker OpenAI-TTS(已禁用) |

### 记忆书 (6本，全部Owner正确)

| 名称 | 条目 | 归属 |
|------|------|------|
| Voxta | 3 | global |
| 香草 | 27 | 香草(BB2) ✅ |
| 香草 | 3 | 香草(BB2) ✅ |
| 香草 | 28 | 香草(BB2) ✅ |
| 小雅 | 13 | 小雅(BB1) ✅ |
| Catherine | 1 | Catherine(CFE) ✅ |

### v3发现并修复的问题

1. **✅ 重复角色** — 小雅×2(D04C5D25 dup)+香草×2(575B8203-CFF dup)，0个聊天引用→安全删除
2. **✅ 记忆书Owner格式混乱** — 3种格式混存(纯ID/引号ID/JSON对象)，5本→全部规范化为纯ID
3. **✅ _audit.py模块检测bug** — 按Label搜索导致10个Label=null的模块全部NOT FOUND→改为ServiceName
4. **✅ _audit.py Owner匹配bug** — 不解析引号/JSON导致误报ORPHAN→添加JSON解析逻辑
5. **⚠️ EdgeTTS端口占用但未被Voxta引用** — :5050运行中，但Voxta TTS模块用的是WindowsSpeech/Silero/F5TTS
6. **✅ 小雅/Catherine TTS label错误** — label均为"香草的可爱中文声音"→修正为各自名称

### v4深度审计修复 (八卦×五感)

7. **✅ _audit.py模块显示名** — 10个模块显示"(unnamed)"→改为ServiceName
8. **✅ _audit.py TTS解析** — 6个角色voice全显"?"→正确解析JSON数组结构
9. **✅ _audit.py凭据误报** — "Keywords"匹配"key"误报→严格匹配"apikey/token/secret/password"
10. **✅ 空聊天清理** — 17个0消息聊天删除(69→52)，WAL checkpoint持久化
11. **✅ TTS label修正** — 小雅:"小雅的温柔中文声音" / Catherine:"Catherine的中文声音"
12. **✅ vam_control.py模块分类** — Memory/Processing类未显示→修复ServiceName匹配(BuiltIn无点)
13. **✅ health_check.py one-api** — 健康检查URL修复→正确检测one-api(:3000)状态
14. **✅ agent_hub.py WindowsSpeech分类** — WindowsSpeech被归为STT→修正为TTS
15. **✅ voxta_manager.py exe路径** — 在VOXTA_ROOT下找exe(永远✖)→修正为VOXTA_ROOT/Active/
16. **⚠️ 火山引擎token明文** — TextToSpeechHttpApi模块配置中含明文token(模块已禁用，风险低)

### 历史已修复问题 (v1/v2)

7. EdgeTTS warmup 400错误 → 返回静音帧
8. TTS nova声音失效 → 重映射YunyangNeural
9. SignalR send_message无响应 → doReply: str→bool
10. VoxtaSignalR start_chat过早退出 → 30s循环recv
11. MemoryBook malformed JSON → UUID包裹为JSON字符串

## 四、嗅 (凭据安全 + 风险) — 安全

| 模块 | 字段 | 风险 |
|------|------|------|
| OpenAICompatible | ApiKey | DPAPI加密(AQAAANCM...前缀)，非明文 |
| Deepgram | ApiKey | DPAPI加密(AQAAANCM...前缀)，非明文 |
| TextToSpeechHttpApi | token | ⚠️ 火山引擎明文token(模块已OFF，低风险) |

**结论**: API Key使用DPAPI加密存储，安全性可接受。

### 路径硬编码风险

所有tools/脚本硬编码`F:\vam1.22`为`VAM_ROOT`。如VaM安装位置变更，需修改6个文件:
- `health_check.py` / `resource_scanner.py` / `vam_launcher.py`
- `voxta_manager.py` / `vam_control.py` / `_audit.py`

**建议**: 未来可提取为统一配置文件或环境变量。当前不影响功能。

## 五、味 (资源可用性) — 磁盘健康

| 目录 | 大小 | 域 |
|------|------|-----|
| VaM (VAM版本/) | 148.9 GB | VaM |
| Voxta | 13.2 GB | Voxta |
| TextGen | 10.5 GB | Voxta |
| VAM-agent (本项目) | <0.1 GB | 混合 |
| F:盘剩余 | 431 GB | — |
| D:盘剩余 | 163 GB | — |

### F:\vam1.22 杂项清理建议

| 目录 | 内容 | 建议 |
|------|------|------|
| `_非VAM文件\` | 实验二PDF + voxta_plugin_src副本 + 随机图片 | ⚠️ 清理或移出 |
| `_AI报告归档\` | 71份旧AI报告 | 可安全删除 |
| `_旧脚本归档\` | 历史自动化脚本 | 保留参考 |

## 六、VaM vs Voxta 隔离 (v3新增)

> 详见 `AGENTS.md` v5 隔离边界章节

### 隔离矩阵

| 维度 | VaM | Voxta | 共享 |
|------|-----|-------|------|
| 进程 | VaM.exe | Voxta.Server + DesktopApp | EdgeTTS |
| 磁盘 | VAM版本/ scripter/ 资源文件/ | Voxta/ TextGen/ one-api/ | EdgeTTS/ |
| 工具 | vam_launcher / resource_scanner | agent_hub / chat_engine / voxta_manager / _audit | health_check / vam_control |
| 通信 | C# Scripter / BepInEx | SignalR / Python CLI | — |
| 桥接 | ← `configs/voxta_plugin_src/` (VaM插件连Voxta) → | — |

### 隔离措施

1. **AGENTS.md v5** — 新增VaM vs Voxta隔离边界表、工具分类速查、目录隔离地图
2. **工具标注** — 每个工具标明所属域(VaM/Voxta/混合)
3. **路径标注** — 每个关键路径标明所属域

## 七、实施总结

### v3修复 (本次审计)
1. 删除重复角色: 小雅(D04C5D25) + 香草(575B8203-CFF)，WAL checkpoint确保持久化
2. 规范化5本记忆书Owner: 引号ID→纯ID、JSON对象→纯ID
3. 修复`_audit.py`两个bug: 模块检测(Label→ServiceName) + Owner匹配(JSON解析)
4. 重写`AGENTS.md` v5: VaM/Voxta隔离边界文档化
5. DB备份: `Voxta.sqlite.db.bak_audit_*`

### v4修复 (深度审计·八卦×五感)
6. 修复`_audit.py`三个bug: 模块显示名(ServiceName)、TTS解析(JSON数组)、凭据误报(严格匹配)
7. 清理17个空聊天(0消息): 69→52
8. 修正小雅+Catherine TTS label: "香草的可爱中文声音"→各自正确label
9. 修复`vam_control.py`模块分类: BuiltIn前缀匹配(无点)→Memory/Processing正确显示
10. 修复`health_check.py` one-api健康检查URL
11. 修复`agent_hub.py` WindowsSpeech分类(STT→TTS)
12. 修复`voxta_manager.py` exe路径(VOXTA_ROOT→VOXTA_ROOT/Active/)

### 未实施 (需服务运行或用户决策)
- ChromaDB/ChainOfThought/Vision模块注册(DLL存在但未注册)
- EdgeTTS服务是否继续运行(当前未被Voxta引用)
- `_非VAM文件`目录清理(需用户确认)

## 八、建议

1. 设置`DEEPSEEK_API_KEY`环境变量以启用DeepSeek降级
2. 定期运行`python tools/_audit.py`进行健康检查
3. 清理`F:\vam1.22\_非VAM文件`和`_AI报告归档`减少混淆
4. 考虑关闭EdgeTTS(:5050)释放资源(当前Voxta用WindowsSpeech)
5. 将6个脚本的`VAM_ROOT`硬编码提取为统一配置(低优先级)
