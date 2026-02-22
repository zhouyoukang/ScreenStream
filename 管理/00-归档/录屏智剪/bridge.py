"""
Screen Capture Bridge — 核心库

供 AI Agent 直接 import 使用：
    from bridge import ScreenBridge
    bridge = ScreenBridge()
    summary = bridge.what_happened(minutes=5)

管线：录屏分段 → 活跃度评分 → EDL剪辑决策 → 粗剪视频
评分算法：JPEG文件大小三维加权(50%变异系数 + 20%绝对复杂度 + 30%帧间极差)
"""
import json
import os
import subprocess
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

VIDEO_EXTS = {'.mp4', '.mkv', '.flv', '.ts', '.mov', '.avi', '.webm'}
EXCLUDE_NAMES = {'rough_cut.mp4', '.concat_list.txt'}
DEFAULT_DIR = os.environ.get('SCB_DIR', '') or str(Path.home() / 'screen_captures')



# ── 数据结构 ──

@dataclass
class VideoInfo:
    duration: float = 0
    duration_str: str = "?"
    size_mb: float = 0
    width: int = 0
    height: int = 0
    codec: str = "?"
    fps: str = "?"


@dataclass
class SegmentInfo:
    path: str = ""
    name: str = ""
    size_mb: float = 0
    modified: str = ""
    locked: bool = False
    video_info: Optional[VideoInfo] = None

    @property
    def ready(self) -> bool:
        return not self.locked


@dataclass
class FrameInfo:
    path: str = ""
    name: str = ""
    size_kb: float = 0


@dataclass
class AnalysisReport:
    video: str = ""
    video_info: Optional[VideoInfo] = None
    mode: str = "scene"
    frame_count: int = 0
    frames_dir: str = ""
    frames: List[FrameInfo] = field(default_factory=list)
    report_path: str = ""
    error: Optional[str] = None


@dataclass
class SessionSummary:
    """what_happened() 的返回值"""
    query_minutes: int = 5
    segments_found: int = 0
    total_duration: float = 0
    avg_activity: float = 0
    segments: List[Dict[str, Any]] = field(default_factory=list)
    timeline: str = ""


# ── 工具函数（单一源，全项目共享） ──

_ffmpeg_available: Optional[bool] = None


def check_ffmpeg() -> bool:
    """检查FFmpeg是否可用（结果缓存）"""
    global _ffmpeg_available
    if _ffmpeg_available is not None:
        return _ffmpeg_available
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        _ffmpeg_available = True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _ffmpeg_available = False
    return _ffmpeg_available


def get_video_info(video_path: str) -> Optional[VideoInfo]:
    """获取视频基本信息（ffprobe）"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json',
             '-show_format', '-show_streams', video_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            fmt = data.get('format', {})
            vs = next((s for s in data.get('streams', [])
                       if s.get('codec_type') == 'video'), {})
            dur = round(float(fmt.get('duration', 0)), 1)
            return VideoInfo(
                duration=dur,
                duration_str=f"{int(dur // 60)}m{int(dur % 60)}s",
                size_mb=round(int(fmt.get('size', 0)) / (1024 * 1024), 1),
                width=vs.get('width', 0),
                height=vs.get('height', 0),
                codec=vs.get('codec_name', '?'),
                fps=vs.get('r_frame_rate', '?'),
            )
    except Exception:
        pass
    return None


def is_file_locked(filepath: str) -> bool:
    """检测文件是否被锁定或正在写入
    方法1: Windows msvcrt字节锁 / Unix fcntl（检测OBS等独占锁）
    方法2: 文件大小增长检测（检测FFmpeg等不加锁的写入者）
    """
    # 方法1: 传统锁检测
    try:
        if os.name == 'nt':
            import msvcrt
            with open(filepath, 'rb') as fh:
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                except (IOError, OSError):
                    return True
        else:
            import fcntl
            with open(filepath, 'rb') as fh:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                except (IOError, OSError):
                    return True
    except (IOError, OSError):
        return True

    # 方法2: 文件修改时间检测（放宽到3s，FFmpeg持续刷写mtime会更新）
    try:
        mtime = os.path.getmtime(filepath)
        if time.time() - mtime < 3.0:
            return True
    except OSError:
        pass

    # 方法3: 文件大小增长检测（500ms间隔，捕获不加锁的持续写入）
    try:
        size1 = os.path.getsize(filepath)
        time.sleep(0.5)
        size2 = os.path.getsize(filepath)
        if size2 > size1:
            return True
    except OSError:
        pass

    return False


def score_segment(video_path: str, sample_interval: int = 2) -> float:
    """
    活跃度评分 (0.0-1.0)
    方法: 每N秒提取一帧JPEG，文件大小变异系数(CV=std/mean)作为画面变化代理
    高CV = 画面变化 = 有趣 | 低CV = 画面静止 = 无聊
    """
    tmpdir = Path(video_path).parent / f".score_{Path(video_path).stem}"
    tmpdir.mkdir(exist_ok=True)

    pattern = str(tmpdir / "s_%04d.jpg")
    subprocess.run(
        ['ffmpeg', '-y', '-i', str(video_path),
         '-vf', f'fps=1/{sample_interval}', '-q:v', '5', pattern],
        capture_output=True, timeout=60
    )

    frames = sorted(tmpdir.glob("s_*.jpg"))
    score = 0.5  # 默认中等（帧不足时）

    if len(frames) >= 2:
        sizes = [f.stat().st_size for f in frames]
        mean_size = sum(sizes) / len(sizes)
        if mean_size > 0:
            variance = sum((s - mean_size) ** 2 for s in sizes) / len(sizes)
            cv = (variance ** 0.5) / mean_size
            # CV维度: 画面变化量 (CV < 0.05 = 静止, CV > 0.3 = 高变化)
            cv_score = min(cv / 0.3, 1.0)
            # 绝对复杂度维度: JPEG大小反映画面丰富度
            # 基准: 720p低复杂度~15KB, 高复杂度~80KB+
            complexity_score = min(mean_size / 60000, 1.0)
            # 帧间极差维度: (max-min)/mean 捕获局部突变
            range_val = (max(sizes) - min(sizes)) / mean_size
            range_score = min(range_val / 0.5, 1.0)
            # 三维加权: 50%变化量 + 20%绝对复杂度 + 30%帧间极差
            score = min(cv_score * 0.5 + complexity_score * 0.2 + range_score * 0.3, 1.0)

    # 清理临时文件
    for f in frames:
        f.unlink()
    try:
        tmpdir.rmdir()
    except OSError:
        pass

    return round(score, 3)


def extract_frames(video_path: str, outdir: Path, mode: str = 'scene',
                   interval: int = 10, threshold: float = 0.3) -> List[FrameInfo]:
    """提取关键帧（场景变化检测 或 固定间隔）"""
    outdir.mkdir(exist_ok=True)
    pattern = str(outdir / "frame_%04d.jpg")

    if mode == 'interval':
        cmd = ['ffmpeg', '-y', '-i', video_path,
               '-vf', f'fps=1/{interval}', '-q:v', '2', pattern]
    else:
        cmd = ['ffmpeg', '-y', '-i', video_path,
               '-vf', f"select=gt(scene\\,{threshold}),setpts=N/FRAME_RATE/TB",
               '-vsync', 'vfr', '-q:v', '2', pattern]

    subprocess.run(cmd, capture_output=True, timeout=300)
    frames_files = sorted(outdir.glob("frame_*.jpg"))

    # 场景模式兜底：无帧时提取首帧
    if mode == 'scene' and not frames_files:
        first = str(outdir / "frame_0001.jpg")
        subprocess.run(
            ['ffmpeg', '-y', '-i', video_path, '-vframes', '1', '-q:v', '2', first],
            capture_output=True, timeout=30
        )
        frames_files = sorted(outdir.glob("frame_*.jpg"))

    return [
        FrameInfo(path=str(f), name=f.name,
                  size_kb=round(f.stat().st_size / 1024, 1))
        for f in frames_files
    ]


# ── EDL (剪辑决策列表) ──

class EditDecisionList:
    """记录每个分段的 keep/skip/highlight 决策，持久化到 edl.json"""

    def __init__(self, session_dir: str, threshold: float = 0.10):
        self.session_dir = Path(session_dir)
        self.threshold = threshold
        self.segments: List[Dict] = []
        self.created = datetime.now().isoformat()
        self.edl_path = self.session_dir / 'edl.json'
        if self.edl_path.exists():
            self._load()

    def add_segment(self, video_path: str, score: float,
                    info: Optional[VideoInfo] = None) -> Dict:
        """添加分段评估结果"""
        if score >= 0.4:
            action = 'highlight'
        elif score >= self.threshold:
            action = 'keep'
        else:
            action = 'skip'

        entry = {
            'file': str(video_path),
            'name': Path(video_path).name,
            'action': action,
            'score': score,
            'duration': info.duration if info else 0,
            'analyzed_at': datetime.now().isoformat(),
        }
        self.segments.append(entry)
        self._save()
        return entry

    def get_kept_files(self) -> List[str]:
        """获取保留的文件列表"""
        return [s['file'] for s in self.segments if s['action'] != 'skip']

    def get_stats(self) -> Dict:
        """计算统计信息"""
        kept = [s for s in self.segments if s['action'] != 'skip']
        return {
            'total': len(self.segments),
            'kept': len(kept),
            'skipped': len(self.segments) - len(kept),
            'highlights': sum(1 for s in self.segments if s['action'] == 'highlight'),
            'total_duration': round(sum(s['duration'] for s in self.segments), 1),
            'kept_duration': round(sum(s['duration'] for s in kept), 1),
        }

    def _save(self):
        data = {
            'session_dir': str(self.session_dir),
            'created': self.created,
            'threshold': self.threshold,
            'segments': self.segments,
            'stats': self.get_stats(),
        }
        with open(self.edl_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self):
        with open(self.edl_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.segments = data.get('segments', [])
        self.threshold = data.get('threshold', self.threshold)
        self.created = data.get('created', self.created)


# ── 主 API 类 ──

class ScreenBridge:
    """
    Screen Capture Bridge 统一 API

    用法:
        bridge = ScreenBridge("D:\\屏幕录制\\ai_segments")
        summary = bridge.what_happened(minutes=5)
        print(summary.timeline)
    """

    def __init__(self, watch_dir: str = DEFAULT_DIR):
        self.watch_dir = Path(watch_dir)
        self._capture_proc: Optional[subprocess.Popen] = None
        if not self.watch_dir.exists():
            self.watch_dir.mkdir(parents=True, exist_ok=True)

    # ── 分段管理 ──

    def get_segments(self, since_minutes: Optional[int] = None,
                     include_locked: bool = False) -> List[SegmentInfo]:
        """获取可用的视频分段列表（按修改时间倒序）"""
        cutoff = time.time() - since_minutes * 60 if since_minutes else None
        segments = []
        try:
            files = sorted(self.watch_dir.iterdir(),
                           key=lambda x: x.stat().st_mtime, reverse=True)
        except OSError:
            files = list(self.watch_dir.iterdir())
        for f in files:
            try:
                stat = f.stat()
            except OSError:
                continue
            if f.suffix.lower() not in VIDEO_EXTS or f.name in EXCLUDE_NAMES:
                continue
            if stat.st_size < 1024:
                continue
            mtime = stat.st_mtime
            if cutoff and mtime < cutoff:
                continue
            locked = is_file_locked(str(f))
            if locked and not include_locked:
                continue
            segments.append(SegmentInfo(
                path=str(f), name=f.name,
                size_mb=round(stat.st_size / (1024 * 1024), 1),
                modified=datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S'),
                locked=locked,
                video_info=get_video_info(str(f)) if not locked else None,
            ))
        return segments

    def get_latest_segment(self) -> Optional[SegmentInfo]:
        """获取最新完成（未锁定）的分段"""
        segments = self.get_segments()
        return segments[0] if segments else None

    # ── 分析 ──

    def analyze(self, video_path: str, mode: str = 'scene',
                interval: int = 10, threshold: float = 0.3) -> AnalysisReport:
        """分析视频分段，提取关键帧"""
        vp = Path(video_path)
        if not vp.exists():
            return AnalysisReport(error=f"文件不存在: {video_path}")
        info = get_video_info(str(vp))
        if not info:
            return AnalysisReport(error=f"无法读取视频: {video_path}")

        outdir = vp.parent / f"{vp.stem}_frames"
        frames = extract_frames(str(vp), outdir, mode, interval, threshold)

        report = AnalysisReport(
            video=str(vp), video_info=info, mode=mode,
            frame_count=len(frames), frames_dir=str(outdir), frames=frames,
        )
        # 保存JSON报告
        report_path = outdir / 'report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(report), f, ensure_ascii=False, indent=2)
        report.report_path = str(report_path)
        return report

    def score(self, video_path: str, sample_interval: int = 2) -> float:
        """计算视频分段的活跃度评分 (0.0-1.0)"""
        return score_segment(video_path, sample_interval)

    # ── 核心查询 ──

    def what_happened(self, minutes: int = 5) -> SessionSummary:
        """
        "最近N分钟屏幕发生了什么？" — Agent核心查询
        返回结构化摘要：分段列表、活跃度评分、总时长、时间线描述。
        """
        segments = self.get_segments(since_minutes=minutes)
        if not segments:
            return SessionSummary(
                query_minutes=minutes,
                timeline=f"最近{minutes}分钟没有可用的录屏分段"
            )

        scored = []
        for seg in segments:
            s = self.score(seg.path)
            dur = seg.video_info.duration if seg.video_info else 0
            scored.append({
                'name': seg.name, 'path': seg.path, 'score': s,
                'activity': 'highlight' if s >= 0.7 else ('active' if s >= 0.3 else 'idle'),
                'duration': dur,
                'duration_str': seg.video_info.duration_str if seg.video_info else '?',
                'modified': seg.modified,
            })

        total_dur = sum(s['duration'] for s in scored)
        avg_score = sum(s['score'] for s in scored) / len(scored)

        # 生成时间线描述（时间正序）
        timeline_parts = []
        for s in reversed(scored):
            icon = {'highlight': '⭐', 'active': '🟢', 'idle': '⚪'}[s['activity']]
            timeline_parts.append(
                f"{icon} {s['modified'][-8:]} {s['name']} "
                f"({s['duration_str']}, 活跃度{s['score']:.0%})"
            )

        return SessionSummary(
            query_minutes=minutes, segments_found=len(scored),
            total_duration=round(total_dur, 1),
            avg_activity=round(avg_score, 3),
            segments=scored, timeline='\n'.join(timeline_parts),
        )

    # ── EDL + 粗剪 ──

    def get_edl(self) -> Optional[dict]:
        """获取当前EDL（如果存在）"""
        edl_path = self.watch_dir / 'edl.json'
        if edl_path.exists():
            with open(edl_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def assemble(self, output_path: Optional[str] = None) -> Optional[str]:
        """从EDL生成粗剪视频（FFmpeg concat，无重编码）"""
        edl = self.get_edl()
        if not edl:
            return None
        kept = [s['file'] for s in edl.get('segments', [])
                if s.get('action') != 'skip']
        if not kept:
            return None

        if output_path is None:
            output_path = str(self.watch_dir / 'rough_cut.mp4')

        concat_list = self.watch_dir / '.concat_list.txt'
        with open(concat_list, 'w', encoding='utf-8') as f:
            for fp in kept:
                safe = fp.replace("'", "'\\''")
                f.write(f"file '{safe}'\n")

        result = subprocess.run(
            ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
             '-i', str(concat_list), '-c', 'copy', output_path],
            capture_output=True, timeout=300
        )
        concat_list.unlink(missing_ok=True)

        if result.returncode == 0 and Path(output_path).exists():
            return output_path
        return None

    # ── 录屏 ──

    def capture(self, segment_min: int = 2, fps: int = 15,
                crf: int = 30, preset: str = 'ultrafast',
                duration_min: int = 0) -> subprocess.Popen:
        """启动FFmpeg分段录屏 (gdigrab桌面捕获, Windows)

        Args:
            segment_min: 分段时长(分钟)
            fps: 帧率
            crf: 质量(越低越好, 23=高质量, 30=低质量)
            preset: x264预设(ultrafast/veryfast/fast)
            duration_min: 总录制时长(分钟), 0=无限

        Returns:
            FFmpeg Popen对象, 用 process.terminate() 停止
        """
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        pattern = str(self.watch_dir / f"seg_{ts}_%03d.ts")
        seg_sec = segment_min * 60

        cmd = ['ffmpeg', '-y', '-f', 'gdigrab', '-framerate', str(fps),
               '-i', 'desktop', '-c:v', 'libx264', '-preset', preset,
               '-crf', str(crf),
               '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease',
               '-force_key_frames', f'expr:gte(t,n_forced*{seg_sec})',
               '-f', 'segment', '-segment_time', str(seg_sec),
               '-reset_timestamps', '1', '-segment_format', 'mpegts']
        if duration_min > 0:
            cmd += ['-t', str(duration_min * 60)]
        cmd.append(pattern)

        self._capture_proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        return self._capture_proc

    def stop_capture(self, timeout: int = 5) -> bool:
        """优雅停止录屏（确保最后一段视频正确写入）

        Windows用CTRL_BREAK_EVENT让FFmpeg正常收尾，
        而非terminate()的硬杀(TerminateProcess)导致0KB残段。
        """
        import signal
        proc = self._capture_proc
        if not proc or proc.poll() is not None:
            return False

        if os.name == 'nt':
            os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
        else:
            proc.send_signal(signal.SIGINT)

        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()

        self._capture_proc = None
        return True

    # ── 清理 ──

    def cleanup(self, keep_days: int = 7, dry_run: bool = True) -> Dict[str, Any]:
        """清理旧分段文件"""
        cutoff = time.time() - keep_days * 86400
        to_delete, to_keep = [], []
        for f in self.watch_dir.iterdir():
            if f.suffix.lower() not in VIDEO_EXTS:
                continue
            (to_delete if f.stat().st_mtime < cutoff else to_keep).append(str(f))

        if not dry_run:
            for fp in to_delete:
                p = Path(fp)
                p.unlink(missing_ok=True)
                frames_dir = p.parent / f"{p.stem}_frames"
                if frames_dir.exists():
                    for ff in frames_dir.iterdir():
                        ff.unlink()
                    frames_dir.rmdir()

        return {
            'keep_days': keep_days, 'dry_run': dry_run,
            'to_delete': len(to_delete), 'to_keep': len(to_keep),
            'files': to_delete,
        }

    # ── 状态 ──

    def status(self) -> Dict[str, Any]:
        """获取当前状态摘要"""
        all_segs = self.get_segments(include_locked=True)
        ready = [s for s in all_segs if s.ready]
        locked = [s for s in all_segs if s.locked]
        edl = self.get_edl()
        return {
            'watch_dir': str(self.watch_dir),
            'exists': self.watch_dir.exists(),
            'total_segments': len(all_segs),
            'ready': len(ready),
            'recording': len(locked),
            'total_size_mb': round(sum(s.size_mb for s in all_segs), 1),
            'has_edl': edl is not None,
            'edl_stats': edl.get('stats') if edl else None,
            'latest': ready[0].name if ready else None,
        }
