"""
Screen Capture Bridge — 统一 CLI

命令:
  watch    实时监控，分段完成自动评分
  batch    批量处理已有分段
  assemble 从EDL生成粗剪视频
  analyze  分析视频，提取关键帧
  status   显示当前状态
  cleanup  清理旧文件
"""
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

from bridge import (
    ScreenBridge, EditDecisionList, check_ffmpeg, get_video_info,
    score_segment, is_file_locked, VIDEO_EXTS, EXCLUDE_NAMES, DEFAULT_DIR,
)


def cmd_watch(args):
    """实时监控模式：分段完成自动评分，Ctrl+C停止"""
    watch_dir = Path(args.dir)
    if not watch_dir.exists():
        print(f"目录不存在: {watch_dir}")
        sys.exit(1)

    edl = EditDecisionList(str(watch_dir), args.threshold)
    known = {s['file'] for s in edl.segments}

    print(f"🎬 实时编辑器启动")
    print(f"📂 监控: {watch_dir}")
    print(f"📊 阈值: {args.threshold}")
    if edl.segments:
        print(f"   已有 {len(edl.segments)} 段 (从上次会话恢复)")
    print(f"Ctrl+C 停止\n")

    try:
        while True:
            for f in sorted(watch_dir.iterdir()):
                if f.suffix.lower() not in VIDEO_EXTS or f.name in EXCLUDE_NAMES:
                    continue
                fpath = str(f)
                if fpath in known or f.stat().st_size < 1024 or is_file_locked(fpath):
                    continue

                known.add(fpath)
                ts = datetime.now().strftime('%H:%M:%S')
                print(f"[{ts}] 新分段: {f.name}")

                info = get_video_info(fpath)
                score = score_segment(fpath, args.sample_interval)
                entry = edl.add_segment(fpath, score, info)

                icon = {'keep': '✅', 'skip': '⏭️', 'highlight': '⭐'}[entry['action']]
                dur_str = info.duration_str if info else '?'
                size_str = f"{info.size_mb}MB" if info else '?'
                print(f"  {icon} {entry['action']} (活跃度: {score:.2f}, {dur_str}, {size_str})")

                stats = edl.get_stats()
                print(f"  📊 {stats['kept']}/{stats['total']}段保留, "
                      f"{stats['kept_duration']}s/{stats['total_duration']}s\n")

                # 回调
                if args.callback:
                    import subprocess
                    try:
                        subprocess.Popen([sys.executable, args.callback, fpath])
                        print(f"  🔄 回调: {args.callback}")
                    except Exception as e:
                        print(f"  ❌ 回调失败: {e}")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\n⏹️ 停止")
        if edl.segments:
            stats = edl.get_stats()
            print(f"📊 {stats['total']}段, 保留{stats['kept']}({stats['kept_duration']}s), "
                  f"跳过{stats['skipped']}, 高光{stats['highlights']}")
            print(f"📋 EDL: {edl.edl_path}")

            if args.auto_assemble and stats['kept'] > 0:
                print(f"\n🎞️ 自动生成粗剪...")
                bridge = ScreenBridge(str(watch_dir))
                result = bridge.assemble()
                if result:
                    size = round(Path(result).stat().st_size / (1024 * 1024), 1)
                    print(f"✅ {result} ({size} MB)")


def cmd_batch(args):
    """批量处理已有分段"""
    watch_dir = Path(args.dir)
    if not watch_dir.exists():
        print(f"目录不存在: {watch_dir}")
        sys.exit(1)

    videos = sorted([f for f in watch_dir.iterdir()
                     if f.suffix.lower() in VIDEO_EXTS
                     and f.name not in EXCLUDE_NAMES
                     and not is_file_locked(str(f))])

    if not videos:
        print(f"无可处理的视频: {watch_dir}")
        return

    edl = EditDecisionList(str(watch_dir), args.threshold)
    known = {s['file'] for s in edl.segments}
    new_videos = [v for v in videos if str(v) not in known]

    if not new_videos:
        print(f"所有 {len(videos)} 个视频已分析")
    else:
        print(f"批量: {len(new_videos)} 新 (已有 {len(known)})\n")
        for i, v in enumerate(new_videos, 1):
            print(f"[{i}/{len(new_videos)}] {v.name} ... ", end='', flush=True)
            info = get_video_info(str(v))
            score = score_segment(str(v), args.sample_interval)
            entry = edl.add_segment(str(v), score, info)
            icon = {'keep': '✅', 'skip': '⏭️', 'highlight': '⭐'}[entry['action']]
            dur_str = info.duration_str if info else '?'
            print(f"{icon} {entry['action']} ({score:.2f}, {dur_str})")

    stats = edl.get_stats()
    print(f"\n📊 {stats['total']}段, 保留{stats['kept']}({stats['kept_duration']}s), "
          f"跳过{stats['skipped']}, 高光{stats['highlights']}")
    print(f"📋 EDL: {edl.edl_path}")

    if args.assemble and stats['kept'] > 0:
        print(f"\n🎞️ 生成粗剪...")
        bridge = ScreenBridge(str(watch_dir))
        result = bridge.assemble()
        if result:
            size = round(Path(result).stat().st_size / (1024 * 1024), 1)
            print(f"✅ {result} ({size} MB)")


def cmd_assemble(args):
    """从EDL生成粗剪"""
    bridge = ScreenBridge(args.dir)
    edl = bridge.get_edl()
    if not edl:
        print(f"EDL不存在，请先运行 watch 或 batch")
        sys.exit(1)

    kept = [s['file'] for s in edl.get('segments', []) if s.get('action') != 'skip']
    if not kept:
        print("EDL中没有保留的分段")
        return

    output = args.output or str(Path(args.dir) / 'rough_cut.mp4')
    print(f"🎞️ {len(kept)} 段 → {output}")

    result = bridge.assemble(output)
    if result:
        size = round(Path(result).stat().st_size / (1024 * 1024), 1)
        print(f"✅ {result} ({size} MB)")
    else:
        print("❌ 粗剪失败")


def cmd_analyze(args):
    """分析视频，提取关键帧"""
    videos = []
    if args.video:
        videos = [args.video]
    elif args.batch_dir:
        d = Path(args.batch_dir)
        if not d.exists():
            print(f"目录不存在: {d}")
            sys.exit(1)
        videos = [str(f) for f in sorted(d.iterdir())
                  if f.suffix.lower() in VIDEO_EXTS]

    if not videos:
        print("无视频文件")
        sys.exit(1)

    bridge = ScreenBridge(str(Path(videos[0]).parent))

    for v in videos:
        name = Path(v).name
        if not args.json:
            print(f"分析: {name} ...")

        report = bridge.analyze(v, args.mode, args.interval, args.threshold)

        if report.error:
            if args.json:
                print(json.dumps({'error': report.error}, ensure_ascii=False))
            else:
                print(f"  错误: {report.error}")
            continue

        if args.json:
            print(json.dumps(asdict(report), ensure_ascii=False))
        else:
            vi = report.video_info
            print(f"  {vi.width}x{vi.height} {vi.codec} {vi.duration}s {vi.size_mb}MB")
            print(f"  {report.frame_count} 帧 → {report.frames_dir}")
            if report.report_path:
                print(f"  报告: {report.report_path}")

    if len(videos) > 1 and not args.json:
        print(f"\n批量完成: {len(videos)} 个视频")


def cmd_status(args):
    """显示当前状态"""
    bridge = ScreenBridge(args.dir)
    s = bridge.status()
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
    else:
        print(f"📂 {s['watch_dir']}")
        print(f"   分段: {s['total_segments']} ({s['ready']}就绪, {s['recording']}录制中)")
        print(f"   大小: {s['total_size_mb']} MB")
        print(f"   最新: {s['latest'] or '无'}")
        if s['has_edl'] and s['edl_stats']:
            st = s['edl_stats']
            print(f"   EDL: {st['kept']}/{st['total']}保留, {st['kept_duration']}s")


def cmd_cleanup(args):
    """清理旧文件"""
    bridge = ScreenBridge(args.dir)
    result = bridge.cleanup(keep_days=args.days, dry_run=not args.force)
    if result['to_delete'] == 0:
        print(f"无需清理 (保留{result['to_keep']}个)")
    else:
        action = "已删除" if args.force else "待删除(加 --force 执行)"
        print(f"{action}: {result['to_delete']}个, 保留: {result['to_keep']}个")
        if not args.force:
            for f in result['files']:
                print(f"  {f}")


def main():
    parser = argparse.ArgumentParser(
        description='Screen Capture Bridge CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例:\n'
               '  python cli.py watch --dir "D:\\屏幕录制\\ai_segments" --auto-assemble\n'
               '  python cli.py batch --dir "D:\\屏幕录制\\ai_segments" --assemble\n'
               '  python cli.py analyze video.mp4\n'
               '  python cli.py status\n'
    )
    sub = parser.add_subparsers(dest='command')

    # watch
    p = sub.add_parser('watch', help='实时监控，分段完成自动评分')
    p.add_argument('--dir', default=DEFAULT_DIR, help='监控目录')
    p.add_argument('--threshold', type=float, default=0.10,
                   help='活跃度阈值(0-1, 默认0.10)')
    p.add_argument('--interval', type=int, default=3,
                   help='检查间隔秒(默认3)')
    p.add_argument('--sample-interval', type=int, default=2,
                   help='帧采样间隔秒(默认2)')
    p.add_argument('--auto-assemble', action='store_true',
                   help='停止时自动生成粗剪')
    p.add_argument('--callback', help='新分段完成时调用的脚本')

    # batch
    p = sub.add_parser('batch', help='批量处理已有分段')
    p.add_argument('--dir', default=DEFAULT_DIR, help='视频目录')
    p.add_argument('--threshold', type=float, default=0.10,
                   help='活跃度阈值(0-1, 默认0.10)')
    p.add_argument('--sample-interval', type=int, default=2,
                   help='帧采样间隔秒(默认2)')
    p.add_argument('--assemble', action='store_true',
                   help='分析后自动生成粗剪')

    # assemble
    p = sub.add_parser('assemble', help='从EDL生成粗剪视频')
    p.add_argument('--dir', default=DEFAULT_DIR, help='会话目录')
    p.add_argument('--output', help='输出文件路径')

    # analyze
    p = sub.add_parser('analyze', help='分析视频，提取关键帧')
    p.add_argument('video', nargs='?', help='视频文件路径')
    p.add_argument('--batch-dir', help='批量处理目录')
    p.add_argument('--mode', choices=['scene', 'interval'], default='scene',
                   help='scene(场景变化) / interval(固定间隔)')
    p.add_argument('-n', '--interval', type=int, default=10,
                   help='间隔秒数(interval模式)')
    p.add_argument('-t', '--threshold', type=float, default=0.3,
                   help='场景变化阈值(scene模式, 0-1)')
    p.add_argument('--json', action='store_true', help='JSON输出')

    # status
    p = sub.add_parser('status', help='显示当前状态')
    p.add_argument('--dir', default=DEFAULT_DIR, help='目录')
    p.add_argument('--json', action='store_true', help='JSON输出')

    # cleanup
    p = sub.add_parser('cleanup', help='清理旧文件')
    p.add_argument('--dir', default=DEFAULT_DIR, help='目录')
    p.add_argument('--days', type=int, default=7, help='保留天数(默认7)')
    p.add_argument('--force', action='store_true', help='实际删除(默认仅预览)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command not in ('status',) and not check_ffmpeg():
        print("错误: FFmpeg未找到，请安装FFmpeg")
        sys.exit(1)

    cmds = {
        'watch': cmd_watch, 'batch': cmd_batch, 'assemble': cmd_assemble,
        'analyze': cmd_analyze, 'status': cmd_status, 'cleanup': cmd_cleanup,
    }
    cmds[args.command](args)


if __name__ == '__main__':
    main()
