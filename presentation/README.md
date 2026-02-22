# 意识流编程 · 视频制作全套

> 本目录是视频制作的统一归档，包含：生成管线、后处理脚本、ASR转录、最终产出、B站发布资料。

## 目录结构

```
presentation/
├── README.md                  ← 本文件
├── generate_v2.py             ← 核心：V13视频生成管线（7段AI slides + TTS + BGM）
├── cosyvoice_tts.py           ← TTS模块：CosyVoice API wrapper（可复用）
├── cloud_transcribe.py        ← ASR转录：Qwen3-ASR + 静音分割 + 并行（通用）
├── merge_matched.py           ← 后处理：AI配音叠加录屏 + 反应穿插 + loudnorm
├── gen_full_srt.py            ← 字幕整合：ASS提取 + 反应字幕 → 完整SRT
├── burst_cut.py               ← 剪辑：爆发点提取 + 加速 + NVENC + ASR字幕
├── bilibili_final.mp4         ← 最终版B站视频（9:23, 329MB, 1080p, 硬字幕）
├── matched_bilibili_hq.mp4   ← 最佳版匹配叠加（7:14, 148MB, CRF14）
├── bilibili_publish/          ← B站发布资料
│   ├── README_发布指南.md     ← 完整发布指南（标题/简介/标签/封面）
│   ├── matched_bilibili_hq.srt ← 最终字幕（119条）
│   └── cover_*.jpg            ← 5种封面（推荐 cover_title_v2.jpg）
└── video_output/
    └── consciousness_stream/  ← AI生成的7段视频 + 拼接产出
        ├── final_pure_ai.mp4  ← 纯AI版（6:05, 114MB, CRF12）
        ├── bilibili_cover.png ← 封面（1920x1080）
        ├── subtitles.srt      ← AI段字幕（107条）
        └── seg0~seg6/         ← 7段独立视频+slides+音频+ASS字幕
```

## 脚本说明

### generate_v2.py — 核心生成管线（V13）

```bash
python generate_v2.py --key sk-your-cosyvoice-key   # CosyVoice（推荐）
python generate_v2.py                                 # edge-tts 免费
```

管线：文本 → Slide(PIL) → TTS(CosyVoice/edge-tts) → EBU R128均衡 → Ken Burns视频(ffmpeg) → ASS字幕烧录 → 拼接(hook+7段+结尾) → numpy BGM → 色彩分级 → ducking → 输出

### cloud_transcribe.py — 云端ASR转录

```bash
python cloud_transcribe.py --key sk-xxx --audio recording.wav --threads 4
```

静音检测分割 → 并行Qwen3-ASR转录 → SRT + JSON输出

### merge_matched.py — 匹配叠加合成

AI配音段叠加录屏画面 + 真实反应片段穿插 + EBU R128 2-pass loudnorm + 棕噪声氛围

### burst_cut.py — 爆发点精华

多段裁剪 → copy拼接 → 加速(NVENC/libx264) → loudnorm → ASR字幕 → 嵌入

### gen_full_srt.py — 字幕整合

从各段ASS字幕提取 + 反应段手写字幕 → 时间轴偏移 → 完整SRT

### cosyvoice_tts.py — TTS模块

```python
from cosyvoice_tts import synthesize
synthesize("你好", "output.mp3", api_key="sk-xxx")
```

CosyVoice v3-plus / 龙安洋语音 / 支持语速和音调调节 / 失败自动降级edge-tts

## 最终产出对比

| 版本 | 文件 | 时长 | 大小 | 特点 |
|------|------|------|------|------|
| **匹配叠加版** | `matched_bilibili_hq.mp4` | 7:14 | 148MB | AI配音+录屏画面+真实反应, CRF14 |
| **B站硬字幕版** | `bilibili_final.mp4` | 9:23 | 329MB | 1.3x加速, 104条硬字幕 |
| **纯AI版** | `video_output/.../final_pure_ai.mp4` | 6:05 | 114MB | 纯slides+TTS, CRF12, V13 |

## 技术参数

- **视频**: H.264 High Profile L4.1, CRF 12-14, 30fps, yuv420p, 1080p
- **音频**: AAC LC 192-320kbps, 48kHz stereo
- **语音处理**: highpass 80Hz + 3kHz EQ + EBU R128 loudnorm (-16 LUFS)
- **BGM**: numpy 4层合成 (drone 110Hz + pad 220/277/330Hz + shimmer 660/880Hz + noise)
- **Ducking**: ffmpeg sidechaincompress (threshold=0.02, ratio=4)

## 依赖

- Python 3.10+, numpy, Pillow, ffmpeg
- edge-tts (`pip install edge-tts`)
- dashscope (`pip install dashscope`) — CosyVoice/Qwen3-ASR

## docs/ — 视频制作知识库（从 windsurf-intelligence-pack 迁入）

| 文件 | 内容 | 价值 |
|------|------|------|
| `video_script_v3_consciousness.md` | V3逐字稿：7段+prosody+视觉+金句+TTS策略 | ⭐核心脚本 |
| `video_production_guide_18min.md` | 18分钟长版脚本+分镜+录制检查清单+截图定位 | ⭐完整制作指南 |
| `handoff_video_agent.md` | Agent交接：V3脚本摘要+录屏时间戳+拼接顺序 | ⭐快速上手 |
| `narrative_research.md` | 10节叙事弧线分析+情绪曲线+核心转折点 | 叙事设计参考 |
| `7_principles.md` | 7条AI Agent实验原则（3min短视频素材） | 独立内容 |
| `video_script_3min.md` | 3分钟短视频完整逐字稿（7条原则版） | 独立脚本 |
| `video_script_agi.md` | AGI视频脚本（人+AI=AGI论点） | 备选主题 |
| `video_agi_dual_screen.md` | 双屏录制方案（Screen1人+Screen2 AI） | 录制方案 |
| `tts_research.md` | TTS方案对比：Fish Speech/CosyVoice/Azure/GPT-SoVITS | 技术选型 |
| `production_iteration_report.md` | V1→V12八轮迭代报告+技术决策+质量天花板 | 工程经验 |
| `quality_decline_analysis.md` | Agent质量下滑根因分析+4条结构性教训 | 认知价值 |
| `future_directions.md` | 6个未来方向：视频/产品/方法论/架构/深化/多Agent | 规划参考 |

## legacy/ — 历史脚本参考（不活跃，仅供参考）

| 文件 | 说明 |
|------|------|
| `video_evaluator.py` | 视频质量自动评估器（6维度打分） |
| `generate_bgm_v2.py` | numpy生成式BGM（4层ambient pad） |
| `generate_subtitles.py` | SRT字幕生成+ffmpeg烧入 |
| `create_hook.py` | 视频开头钩子片段生成 |
| `v16_narrative.py` | V16叙事脚本（最新版叙事内容参考） |

## 版本历史

- **V13**: 真实录屏demo hook (8s) + numpy BGM + sidechaincompress ducking
- **V12**: hook开头 (3s文字) + numpy BGM替代纯正弦波
- **V11**: BGM + ducking + B站封面 + CRF 12
- **V10**: CosyVoice TTS + ASS字幕 + 色彩分级
