"""
FFmpeg 并行轻量录屏
- 独立于OBS运行，用FFmpeg的gdigrab捕获屏幕
- 自动分段输出，每段可被AI立即处理
- 低质量/低资源占用，专为AI分析优化

用法:
  python parallel_capture.py                        # 默认5分钟分段，720p
  python parallel_capture.py --segment 2            # 每2分钟一段
  python parallel_capture.py --quality high         # 高质量(1080p)
  python parallel_capture.py --outdir "E:\ai录屏"   # 指定输出目录
  python parallel_capture.py --duration 60          # 录制60分钟后自动停止
  python parallel_capture.py --dry-run                # 仅显示命令不执行
"""
import os
import sys
import signal
import subprocess
import argparse
import time
from pathlib import Path
from datetime import datetime

DEFAULT_OUTDIR = r"D:\屏幕录制\ai_segments"

QUALITY_PRESETS = {
    'low': {
        'scale': '1280:720',
        'fps': 15,
        'crf': 30,
        'preset': 'ultrafast',
        'desc': '720p 15fps (最低CPU占用，适合文字/UI分析)',
    },
    'medium': {
        'scale': '1920:1080',
        'fps': 24,
        'crf': 26,
        'preset': 'veryfast',
        'desc': '1080p 24fps (均衡)',
    },
    'high': {
        'scale': '2560:1440',
        'fps': 30,
        'crf': 23,
        'preset': 'fast',
        'desc': '1440p 30fps (高质量)',
    },
    'source': {
        'scale': None,  # 原始分辨率
        'fps': 30,
        'crf': 23,
        'preset': 'fast',
        'desc': '原始分辨率 30fps',
    },
}


def check_ffmpeg():
    """检查FFmpeg是否可用"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
        version_line = result.stdout.split('\n')[0] if result.stdout else '?'
        print(f"✅ FFmpeg: {version_line}")
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("❌ FFmpeg未找到，请安装FFmpeg")
        return False


def build_ffmpeg_cmd(outdir: str, segment_min: int, quality: str,
                     duration_min: int = 0) -> tuple:
    """构建FFmpeg分段录屏命令（gdigrab桌面捕获，无音频，兼容性最优）"""
    preset = QUALITY_PRESETS[quality]
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_pattern = str(Path(outdir) / f"ai_seg_{ts}_%03d.mp4")

    cmd = ['ffmpeg', '-y']
    cmd += ['-f', 'gdigrab']
    cmd += ['-framerate', str(preset['fps'])]
    cmd += ['-i', 'desktop']
    cmd += ['-c:v', 'libx264']
    cmd += ['-preset', preset['preset']]
    cmd += ['-crf', str(preset['crf'])]

    if preset['scale']:
        cmd += ['-vf', f"scale={preset['scale']}:force_original_aspect_ratio=decrease"]

    cmd += ['-f', 'segment']
    cmd += ['-segment_time', str(segment_min * 60)]
    cmd += ['-reset_timestamps', '1']
    cmd += ['-segment_format', 'mp4']

    if duration_min > 0:
        cmd += ['-t', str(duration_min * 60)]

    cmd += [out_pattern]
    return cmd, out_pattern


def main():
    parser = argparse.ArgumentParser(description='FFmpeg并行轻量录屏（AI分析专用）')
    parser.add_argument('--outdir', default=DEFAULT_OUTDIR, help=f'输出目录 (默认: {DEFAULT_OUTDIR})')
    parser.add_argument('--segment', type=int, default=5, help='分段时长(分钟), 默认5')
    parser.add_argument('--quality', choices=QUALITY_PRESETS.keys(), default='low',
                        help='画质预设 (默认: low)')
    parser.add_argument('--duration', type=int, default=0, help='总录制时长(分钟), 0=无限')
    parser.add_argument('--dry-run', action='store_true', help='仅显示命令，不执行')
    parser.add_argument('--list-presets', action='store_true', help='列出画质预设')
    args = parser.parse_args()

    if args.list_presets:
        print("画质预设:")
        for name, p in QUALITY_PRESETS.items():
            print(f"  {name:8s} — {p['desc']}")
        return

    if not check_ffmpeg():
        sys.exit(1)

    # 确保输出目录存在
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    preset = QUALITY_PRESETS[args.quality]
    print(f"\n{'='*50}")
    print(f"🎬 FFmpeg 并行录屏 (AI分析专用)")
    print(f"{'='*50}")
    print(f"📂 输出: {outdir}")
    print(f"🎯 画质: {args.quality} — {preset['desc']}")
    print(f"✂️  分段: 每 {args.segment} 分钟")
    if args.duration:
        print(f"⏱️  总时长: {args.duration} 分钟")

    cmd, out_pattern = build_ffmpeg_cmd(outdir, args.segment, args.quality, args.duration)

    print(f"\n📋 命令:")
    print(f"   {' '.join(cmd)}")

    if args.dry_run:
        print("\n(dry-run 模式，未执行)")
        return

    print(f"\n▶️  开始录制... (Ctrl+C 停止)")
    print(f"   输出文件: {out_pattern}")
    print(f"   每 {args.segment} 分钟产生一个新文件，已完成的段可被AI立即处理\n")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # 等待几秒检查是否启动成功
        time.sleep(2)
        if process.poll() is not None:
            stderr = process.stderr.read().decode('utf-8', errors='replace')
            print(f"❌ FFmpeg启动失败:")
            print(stderr[-500:] if len(stderr) > 500 else stderr)
            sys.exit(1)

        print(f"✅ 录制进行中 (PID: {process.pid})")

        # 监控输出
        segment_count = 0
        start_time = time.time()
        while process.poll() is None:
            time.sleep(5)
            elapsed = time.time() - start_time
            elapsed_str = f"{int(elapsed//60)}m{int(elapsed%60)}s"

            # 检查已生成的分段文件
            segments = sorted(outdir.glob(f"ai_seg_*_*.mp4"))
            new_count = len(segments)
            if new_count > segment_count:
                for seg in segments[segment_count:]:
                    size_mb = round(seg.stat().st_size / (1024*1024), 1)
                    print(f"   ✅ 分段完成: {seg.name} ({size_mb} MB)")
                segment_count = new_count

            # 每30秒显示状态
            if int(elapsed) % 30 < 5:
                print(f"   ⏱️ {elapsed_str} | 🎬 {segment_count} 段已完成", end='\r')

        print(f"\n\n录制结束. 共 {segment_count} 段.")

    except KeyboardInterrupt:
        print(f"\n\n⏹️  停止录制...")
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

        segments = sorted(outdir.glob(f"ai_seg_*_*.mp4"))
        elapsed = time.time() - start_time
        print(f"✅ 录制结束: {int(elapsed//60)}m{int(elapsed%60)}s, {len(segments)} 段")
        print(f"📂 文件位置: {outdir}")


if __name__ == '__main__':
    main()
