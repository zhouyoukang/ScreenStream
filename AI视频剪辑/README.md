# Agent 视频工坊

> 全盘搜索 C/D/E 三盘，汇总所有 AI Agent 视频产出。去其杂，留其精。

## 统一入口

```bash
cd AI视频剪辑
python pipeline.py           # 查看全项目状态（默认）
python pipeline.py build1    # 构建项目一（B站视频: TTS→截图→视频→字幕→BGM）
python pipeline.py build2    # 构建项目二（录屏智剪V5）
python pipeline.py collect   # 汇聚所有精华到本目录
python pipeline.py serve     # 启动预览 http://127.0.0.1:9876
python pipeline.py analyze   # 自动质量分析（五维评分+问题检测）
python pipeline.py thumbnail # 自动提取封面图
python pipeline.py silence   # 静音检测分析
python pipeline.py clean     # 清理中间产物
python pipeline.py info      # 帮助
```

## 质量分析结果

| 视频 | 等级 | 分数 | 问题 | 已修复 |
|------|------|------|------|--------|
| P3 相机成品 | A | 50/50 | 94.6%静音 | ✅ 已加BGM |
| P1 完整版 | B | 42/50 | 单声道+低采样率 | — (edge-tts限制) |
| P2 录屏V5 | B | 39/50 | 帧率15fps | — (录屏源限制) |

## 五个项目 · 七个最终视频

| # | 项目 | 最终视频 | 时长 | 大小 |
|---|------|---------|------|------|
| 1 | **B站科技视频** "为什么AI越聊越笨" | v16_final / subtitled / no_subtitle | 4:46 | 40MB |
| 2 | **录屏智剪** AI全自动剪辑系统 | showcase_v5 / showcase_v3 | 2:07+2:12 | 14MB |
| 3 | **相机AI剪辑** AI Video Editor | final_july2025 | 3:41 | 471MB |
| 4 | **智能精华** 50素材→自动成片 | smart_highlight | 2:54 | 240MB |
| 5 | **旅行电影** 骑行旅拍五幕叙事 | travel_film_ultimate | 2:15 | 135MB |
| 5v2 | **旅行电影v2** 叙事驱动·运动分析·crossfade | travel_film_v2 | **3:24** | **236MB** |

## 目录结构

```
AI视频剪辑/
├── pipeline.py              ← 统一管线入口（9命令）
├── smart_cut.py             ← AI智能精华提取器（scan→cut→assemble）
├── index.html               ← 五感化前端展示（6Tab）
├── README.md                ← 本文件
├── quality_report.json      ← 自动质量分析报告
├── 01-B站科技视频/
│   ├── v16_final.mp4        ★ 完整版（字幕+BGM）
│   ├── v16_subtitled.mp4    字幕版
│   ├── v16_no_subtitle.mp4  纯净版
│   ├── slides.html          22张交互幻灯片
│   ├── 02_script.md / bilibili_publish.md / transcript.md
│   ├── bgm.mp3 / tts_full.mp3
│   └── cover.jpg            自动提取封面
├── 02-录屏智剪/
│   ├── showcase_v5.mp4      ★ V5完整版（PPT+TTS+字幕）
│   ├── showcase_v3.mp4      V3精华版
│   └── cover.jpg
├── 03-相机AI剪辑/
│   ├── final_july2025_bgm.mp4  ★ AI成品+BGM（原片94%静音已修复）
│   ├── final_july2025.mp4      原始版
│   └── cover.jpg
├── 04-智能精华/
│   ├── smart_highlight.mp4  ★ 50素材→15精华→自动成片
│   └── cover.jpg
└── 05-旅行电影/
    ├── travel_film_v2.mp4       ★★ v2（21片段·5幕·crossfade·sidechain·loudnorm）
    ├── travel_film_ultimate.mp4  ★ 终极版（19片段·5幕·字幕·BGM ducking）
    ├── build_v2.py              v2构建脚本（运动分析+智能选片）
    ├── build_ultimate.py        v1.3构建脚本
    ├── travel_v2.srt            v2精确字幕
    ├── ITERATION_LOG_v2.md      迭代改进日志+对标分析
    ├── cover_v2.jpg             v2封面
    └── clips_v3/               21个精华片段
```

## 源目录（精华已复制到此，原始仍在原位）

| 项目 | 源目录 | 原始规模 |
|------|--------|---------|
| B站科技视频 | `E:\道\道生一\_video\` | 60+文件, ~76MB |
| 录屏智剪 | `D:\屏幕录制\` | 50+文件, ~14GB (含OBS录屏) |
| 相机AI剪辑 | `E:\VideoEdit\` | 30+文件, ~数GB (含相机原片) |
| 旅行电影 | `E:\骑行拍摄\使用素材\` + `E:\VideoEdit\` | 59素材, ~22GB |

## 排除项（非Agent产出）

- C:\CrossDevice\ — 手机同步视频(60+)
- E:\嗨格式录屏文件\ — 手动录屏
- E:\JianyingPro Drafts\ — 剪映草稿
- E:\个人归档\ — 个人视频
