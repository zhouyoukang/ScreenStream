# Screen Capture Bridge

录屏文件 ↔ AI处理 的桥接工具。

## 核心问题

OBS 录制时**独占锁定**视频文件，AI无法读取。
FFmpeg 并行录屏 + 自动分段 → **录屏不中断 + AI实时处理**。

## 架构

```
parallel_capture.py ──segment──→ seg_001.ts ──→ bridge.py ──→ edl.json + rough_cut.mp4
  (FFmpeg gdigrab)     (分段)     seg_002.ts     (评分+EDL+组装)
                                  seg_003.ts
```

**评分算法**（零额外依赖）：
```
视频分段 → 每2秒采样帧 → JPEG文件大小(复杂度代理)
综合评分 = 70% 变化量(CV=std/mean) + 30% 绝对复杂度(mean_size)
  高分 = 画面变化大或内容丰富 → keep/highlight
  低分 = 画面静止且简单 → skip
```

## 文件

| 文件 | 职责 |
|------|------|
| `bridge.py` | **核心库**：评分 + EDL + 分段管理 + 关键帧提取（供Agent import） |
| `server.py` | **Web UI + REST API**：浏览器操控录制/评分/EDL/粗剪（port 9905） |
| `cli.py` | **统一CLI**：watch / batch / assemble / analyze / status / cleanup |
| `parallel_capture.py` | FFmpeg gdigrab 并行录屏，自动分段输出 |

## 快速开始

```bash
# Web UI（推荐）
python server.py --port 9905
# 浏览器打开 http://localhost:9905

# 或 CLI 模式:
# 1. 启动并行录屏
python parallel_capture.py --segment 2 --quality low

# 2. 实时编辑（Ctrl+C停止时自动粗剪）
python cli.py watch --dir "D:\屏幕录制\ai_segments" --auto-assemble

# 或分步:
python cli.py batch --dir "D:\屏幕录制\ai_segments" --assemble
python cli.py analyze video.mp4
python cli.py assemble --dir "D:\屏幕录制\ai_segments"
python cli.py status
python cli.py cleanup --days 7 --force
```

## Python API

```python
from bridge import ScreenBridge

bridge = ScreenBridge("D:\\屏幕录制\\ai_segments")

# Agent核心查询
summary = bridge.what_happened(minutes=5)
print(summary.timeline)
print(summary.avg_activity)

# 分段管理
segments = bridge.get_segments()
latest = bridge.get_latest_segment()
score = bridge.score(latest.path)

# 分析 + 粗剪
report = bridge.analyze(latest.path, mode='scene')
cut = bridge.assemble()

# 状态 + 清理
print(bridge.status())
bridge.cleanup(keep_days=7, dry_run=False)
```

| 方法 | 说明 |
|------|------|
| `what_happened(minutes)` | 最近N分钟的活动摘要（时间线+评分） |
| `get_segments()` | 分段列表（可按时间过滤） |
| `score(path)` | 活跃度评分（0-1） |
| `analyze(path, mode)` | 关键帧提取（scene/interval） |
| `assemble()` | 从EDL生成粗剪（FFmpeg concat，无重编码） |
| `status()` / `cleanup()` | 状态摘要 / 清理旧文件 |

## 配置

设置环境变量 `SCB_DIR` 可覆盖默认目录：
```bash
set SCB_DIR=E:\my_recordings\segments
python cli.py status
```

## 依赖

- **Python** 3.8+ (Windows/Linux/macOS)
- **FFmpeg** 8.0+（gdigrab + segment + scene filter + ffprobe + concat）

## 状态

本工具是PC桌面录屏分析工具，与ScreenStream Android核心功能无直接关联。已归档。

## 与 vision-bridge 的关系

| 工具 | 解决的问题 | 输出 | 访问方式 |
|------|-----------|------|---------|
| **screen-capture-bridge** | 录屏时序分析+实时剪辑 | 视频分段+关键帧+粗剪 | CLI + Python API |
| **vision-bridge** (port 9902) | AI实时看屏幕 | JPEG截图 | HTTP API |
