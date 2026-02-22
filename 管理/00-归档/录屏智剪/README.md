# 录屏智剪

PC桌面录屏分析库 — 解决OBS独占锁定文件导致AI无法读取的问题。

## 核心机制

```
FFmpeg gdigrab → 自动分段(.ts) → JPEG采样评分 → EDL剪辑决策 → 粗剪组装
```

**评分算法**（零额外依赖，三维加权）：
```
每2秒提取一帧JPEG → 文件大小作为视觉复杂度代理
评分 = 50% CV变异系数(std/mean) + 20% 绝对复杂度(mean_size) + 30% 帧间极差((max-min)/mean)
  ≥0.4 highlight | ≥0.10 keep | <0.10 skip → EDL → FFmpeg concat无重编码粗剪
```

## API

```python
from bridge import ScreenBridge

bridge = ScreenBridge()  # 默认 ~/screen_captures，可设 SCB_DIR 环境变量

# 录屏（FFmpeg gdigrab分段录制）
proc = bridge.capture(segment_min=2, fps=15)  # 返回Popen
bridge.stop_capture()                          # 优雅停止（CTRL_BREAK，确保最后一段不是0KB）

# 查询
summary = bridge.what_happened(minutes=5)  # 最近N分钟活动摘要
segments = bridge.get_segments()            # 分段列表
score = bridge.score(segments[0].path)      # 单段评分 (0.0-1.0)

# 分析
report = bridge.analyze(path, mode='scene')  # 关键帧提取

# 剪辑
cut = bridge.assemble()                      # EDL → 粗剪视频

# 维护
bridge.status()                              # 状态摘要
bridge.cleanup(keep_days=7, dry_run=False)   # 清理旧文件
```

## 依赖

- **Python** 3.8+
- **FFmpeg** 8.0+ (gdigrab + segment + ffprobe + concat)

## 状态

已归档。与ScreenStream Android核心无直接关联。
