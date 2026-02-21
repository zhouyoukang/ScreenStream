# Screen Capture Bridge

录屏文件 ↔ AI处理 的桥接工具。解决"OBS录屏时文件被锁定，AI无法处理"的问题。

## 核心问题

OBS 录制时**独占锁定**视频文件，任何其他进程（包括AI）都无法读取。
本工具提供两个互补方案，实现**录屏不中断 + AI实时处理**。

## 工具清单

| 脚本 | 用途 | 必要性 |
|------|------|--------|
| `parallel_capture.py` | ⭐ FFmpeg并行轻量录屏，独立于OBS，AI可随时处理 | **核心** |
| `watcher.py` | 监控录屏目录，检测已完成的分段文件，输出JSON供AI消费 | **核心** |
| `setup_obs_split.py` | 配置OBS为分段录制模式（需OBS未在录制时） | 备选 |
| `obs_control.py` | OBS WebSocket控制（需在OBS中启用WebSocket） | 备选 |

## 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **FFmpeg并行** ⭐ | 立即可用，不影响OBS | 额外CPU(3-8%) | 随时启用，推荐 |
| **OBS分段** | 零额外CPU，高画质 | 需从OBS设置中配置 | 日常录屏 |

## 快速开始

### 方案A: FFmpeg并行捕获（推荐）
```bash
# OBS正常录制（高质量存档），同时启动FFmpeg轻量录屏供AI处理
python parallel_capture.py --segment 2 --quality low

# 选项说明
#   --segment N    每N分钟产生一个新文件（默认5）
#   --quality      low(720p)/medium(1080p)/high(1440p)/source
#   --duration N   总录制N分钟后停止（0=无限）
#   --dry-run      仅显示命令不执行
#   --outdir PATH  指定输出目录

# 输出目录: D:\屏幕录制\ai_segments\
# AI可直接用 ffprobe / read_file 处理已完成的分段
```

### 方案B: OBS分段录制
在 OBS 中手动配置：
1. 打开 OBS → 设置 → 输出
2. 输出模式选 **高级**
3. 录像 → 勾选 **自动分割文件**
4. 分割方式选 **按时间**，时长设为 **5分钟**
5. 确定并开始录制

或用脚本一键配置（需OBS未在录制时）：
```bash
python setup_obs_split.py --split-minutes 5
```

### 监控录屏目录
```bash
python watcher.py --once              # 扫描一次，人类可读
python watcher.py --once --json       # JSON格式（供AI消费）
python watcher.py                     # 持续监控，检测新分段
python watcher.py --dir "D:\屏幕录制\ai_segments"  # 监控FFmpeg输出
```

## 画质预设

| 预设 | 分辨率 | FPS | 用途 |
|------|--------|-----|------|
| low | 720p | 15 | 文字/UI分析，最低CPU |
| medium | 1080p | 24 | 均衡 |
| high | 1440p | 30 | 高质量 |
| source | 原始 | 30 | 完整保真 |

## 环境

| 依赖 | 版本 | 必要性 |
|------|------|--------|
| Python | 3.8+ | 必须 |
| FFmpeg | 8.0.1 | 必须（parallel_capture + watcher） |
| OBS Studio | 31.1.2 | 仅方案B需要 |
| websocket-client | pip | 仅 obs_control.py 需要 |

## 验证记录（2026-02-21）

- ✅ FFmpeg gdigrab 捕获 + segment 分段输出
- ✅ 分段文件 h264 720p，每段30s仅0.4MB
- ✅ 已完成分段立即可读（ffprobe + Python open）
- ✅ watcher 正确检测新文件和锁定状态
- ✅ OBS 与 FFmpeg 可同时运行互不干扰
