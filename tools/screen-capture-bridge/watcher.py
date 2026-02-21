"""
录屏文件监控器
- 监控OBS录屏目录，检测已完成的分段文件
- 文件未被锁定时自动报告"可处理"
- 支持回调/输出JSON供AI消费

用法:
  python watcher.py                          # 监控默认目录 D:\屏幕录制
  python watcher.py --dir "E:\录屏"          # 监控指定目录
  python watcher.py --callback process.py    # 检测到新文件时调用脚本
  python watcher.py --once                   # 仅扫描一次（不持续监控）
"""
import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

DEFAULT_DIR = r"D:\屏幕录制"
VIDEO_EXTS = {'.mkv', '.mp4', '.flv', '.ts', '.mov', '.avi', '.webm'}
CHECK_INTERVAL = 3  # 秒


def is_file_locked(filepath: str) -> bool:
    """检测文件是否被其他进程锁定"""
    try:
        with open(filepath, 'rb') as f:
            # 尝试读取前几个字节
            f.read(1)
        # 进一步尝试独占打开
        import msvcrt
        fh = open(filepath, 'rb')
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            fh.close()
            return False
        except (IOError, OSError):
            fh.close()
            return True
    except (IOError, OSError):
        return True


def get_video_info(filepath: str) -> dict:
    """用FFmpeg获取视频基本信息"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json',
             '-show_format', '-show_streams', filepath],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            fmt = data.get('format', {})
            duration = float(fmt.get('duration', 0))
            size_mb = int(fmt.get('size', 0)) / (1024 * 1024)
            streams = data.get('streams', [])
            video_stream = next((s for s in streams if s.get('codec_type') == 'video'), {})
            return {
                'duration_sec': round(duration, 1),
                'duration_str': f"{int(duration//60)}m{int(duration%60)}s",
                'size_mb': round(size_mb, 1),
                'width': video_stream.get('width', 0),
                'height': video_stream.get('height', 0),
                'codec': video_stream.get('codec_name', '?'),
                'fps': video_stream.get('r_frame_rate', '?'),
            }
    except Exception:
        pass
    p = Path(filepath)
    return {
        'duration_sec': 0,
        'duration_str': '?',
        'size_mb': round(p.stat().st_size / (1024*1024), 1),
        'width': 0, 'height': 0, 'codec': '?', 'fps': '?',
    }


def scan_directory(watch_dir: str, known_files: set) -> list:
    """扫描目录，返回新的可处理文件列表"""
    new_ready = []
    watch_path = Path(watch_dir)
    
    for f in watch_path.iterdir():
        if f.suffix.lower() not in VIDEO_EXTS:
            continue
        fpath = str(f)
        if fpath in known_files:
            continue
        # 跳过太小的文件（可能刚创建）
        if f.stat().st_size < 1024:
            continue
        
        locked = is_file_locked(fpath)
        if not locked:
            info = get_video_info(fpath)
            entry = {
                'file': fpath,
                'name': f.name,
                'locked': False,
                'ready': True,
                'modified': f.stat().st_mtime,
                'modified_str': datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                **info
            }
            new_ready.append(entry)
    
    return new_ready


def scan_all(watch_dir: str) -> dict:
    """完整扫描，返回所有文件状态"""
    watch_path = Path(watch_dir)
    result = {'ready': [], 'locked': [], 'dir': watch_dir}
    
    for f in sorted(watch_path.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.suffix.lower() not in VIDEO_EXTS:
            continue
        fpath = str(f)
        locked = is_file_locked(fpath)
        size_mb = round(f.stat().st_size / (1024*1024), 1)
        entry = {
            'file': fpath,
            'name': f.name,
            'size_mb': size_mb,
            'locked': locked,
            'ready': not locked,
            'modified': datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        }
        if locked:
            result['locked'].append(entry)
        else:
            result['ready'].append(entry)
    
    result['summary'] = {
        'total': len(result['ready']) + len(result['locked']),
        'ready_count': len(result['ready']),
        'locked_count': len(result['locked']),
        'ready_size_mb': round(sum(f['size_mb'] for f in result['ready']), 1),
    }
    return result


def main():
    parser = argparse.ArgumentParser(description='录屏文件监控器')
    parser.add_argument('--dir', default=DEFAULT_DIR, help=f'监控目录 (默认: {DEFAULT_DIR})')
    parser.add_argument('--once', action='store_true', help='仅扫描一次')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')
    parser.add_argument('--callback', type=str, help='检测到新文件时调用的脚本')
    parser.add_argument('--interval', type=int, default=CHECK_INTERVAL, help=f'检查间隔秒数 (默认: {CHECK_INTERVAL})')
    args = parser.parse_args()
    
    watch_dir = args.dir
    if not Path(watch_dir).exists():
        print(f"❌ 目录不存在: {watch_dir}")
        sys.exit(1)
    
    # 一次性扫描模式
    if args.once:
        result = scan_all(watch_dir)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            s = result['summary']
            print(f"📂 {watch_dir}")
            print(f"   总计: {s['total']} 个视频文件")
            print(f"   ✅ 可处理: {s['ready_count']} 个 ({s['ready_size_mb']} MB)")
            print(f"   🔒 录制中: {s['locked_count']} 个")
            if result['locked']:
                print(f"\n🔴 正在录制:")
                for f in result['locked']:
                    print(f"   {f['name']} ({f['size_mb']} MB) — 锁定中")
            if result['ready']:
                print(f"\n🟢 可处理文件 (最近10个):")
                for f in result['ready'][:10]:
                    print(f"   {f['name']} ({f['size_mb']} MB) — {f['modified']}")
        return
    
    # 持续监控模式
    print(f"👁️  监控目录: {watch_dir}")
    print(f"⏱️  检查间隔: {args.interval}秒")
    print(f"按 Ctrl+C 停止\n")
    
    known_files = set()
    # 初始扫描，标记已有文件
    for f in Path(watch_dir).iterdir():
        if f.suffix.lower() in VIDEO_EXTS and not is_file_locked(str(f)):
            known_files.add(str(f))
    print(f"📋 已有 {len(known_files)} 个已完成文件（跳过）")
    
    try:
        while True:
            new_files = scan_directory(watch_dir, known_files)
            for entry in new_files:
                known_files.add(entry['file'])
                ts = datetime.now().strftime('%H:%M:%S')
                if args.json:
                    print(json.dumps({'event': 'new_ready', 'time': ts, **entry}, ensure_ascii=False))
                else:
                    print(f"\n🆕 [{ts}] 新文件可处理!")
                    print(f"   📄 {entry['name']}")
                    print(f"   📏 {entry['size_mb']} MB | ⏱️ {entry['duration_str']} | 🎬 {entry['width']}x{entry['height']} {entry['codec']}")
                
                if args.callback:
                    try:
                        subprocess.Popen([sys.executable, args.callback, entry['file']])
                        print(f"   🔄 已触发回调: {args.callback}")
                    except Exception as e:
                        print(f"   ❌ 回调失败: {e}")
            
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n\n👋 监控已停止")


if __name__ == '__main__':
    main()
