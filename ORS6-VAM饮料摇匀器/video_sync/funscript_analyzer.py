"""
Funscript脚本分析器

对成人视频funscript进行质量和强度分析:
- 速度/强度统计 (平均/峰值/分布)
- 时间段热力图 (哪些时段最激烈)
- 多轴覆盖度分析
- 脚本质量评分 (动作密度/平滑度/极端值)
- 章节自动分割 (按强度变化)

用法:
    from video_sync.funscript_analyzer import FunscriptAnalyzer
    
    analyzer = FunscriptAnalyzer()
    report = analyzer.analyze("video.funscript")
    print(report.summary)
    
    # 多轴分析
    report = analyzer.analyze_multi("video.funscript")
    
    # 热力图 (10秒粒度)
    heatmap = report.heatmap(bucket_sec=10)
"""

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SpeedStats:
    """速度统计"""
    avg_speed: float = 0.0
    max_speed: float = 0.0
    min_speed: float = 0.0
    median_speed: float = 0.0
    std_dev: float = 0.0
    
    @property
    def intensity_label(self) -> str:
        if self.avg_speed < 100:
            return "缓慢"
        elif self.avg_speed < 250:
            return "中等"
        elif self.avg_speed < 400:
            return "激烈"
        else:
            return "极限"


@dataclass
class HeatmapBucket:
    """热力图时间桶"""
    start_sec: float
    end_sec: float
    avg_speed: float = 0.0
    max_speed: float = 0.0
    action_count: int = 0
    intensity: float = 0.0  # 0.0-1.0 归一化强度
    
    @property
    def label(self) -> str:
        if self.intensity < 0.2:
            return "░"
        elif self.intensity < 0.4:
            return "▒"
        elif self.intensity < 0.6:
            return "▓"
        elif self.intensity < 0.8:
            return "█"
        else:
            return "█"


@dataclass
class Chapter:
    """自动检测的章节"""
    start_sec: float
    end_sec: float
    label: str = ""
    avg_intensity: float = 0.0
    
    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec


@dataclass
class AxisReport:
    """单轴分析报告"""
    axis: str
    action_count: int = 0
    duration_sec: float = 0.0
    speed_stats: SpeedStats = field(default_factory=SpeedStats)
    position_range: tuple[int, int] = (0, 100)
    avg_position: float = 50.0
    stroke_count: int = 0
    quality_score: float = 0.0


@dataclass
class AnalysisReport:
    """完整分析报告"""
    title: str = ""
    source_path: str = ""
    duration_sec: float = 0.0
    axes: dict[str, AxisReport] = field(default_factory=dict)
    chapters: list[Chapter] = field(default_factory=list)
    overall_intensity: str = "未知"
    quality_score: float = 0.0
    
    @property
    def summary(self) -> str:
        lines = [
            f"═══ Funscript分析: {self.title} ═══",
            f"时长: {self.duration_sec:.0f}s ({self.duration_sec/60:.1f}min)",
            f"轴数: {len(self.axes)}",
            f"强度: {self.overall_intensity}",
            f"质量: {self.quality_score:.0f}/100",
            "",
        ]
        for axis, report in sorted(self.axes.items()):
            lines.append(
                f"  {axis}: {report.action_count}动作, "
                f"速度{report.speed_stats.avg_speed:.0f}avg/"
                f"{report.speed_stats.max_speed:.0f}max, "
                f"行程{report.stroke_count}次, "
                f"强度[{report.speed_stats.intensity_label}]"
            )
        
        if self.chapters:
            lines.append("")
            lines.append("章节:")
            for i, ch in enumerate(self.chapters, 1):
                mins = int(ch.start_sec // 60)
                secs = int(ch.start_sec % 60)
                lines.append(
                    f"  {i}. [{mins:02d}:{secs:02d}] "
                    f"{ch.label} ({ch.duration_sec:.0f}s)")
        
        return "\n".join(lines)
    
    def heatmap(self, bucket_sec: float = 10.0) -> list[HeatmapBucket]:
        """生成热力图"""
        if "L0" not in self.axes:
            return []
        return FunscriptAnalyzer._compute_heatmap_static(
            self.source_path, bucket_sec)
    
    def heatmap_ascii(self, bucket_sec: float = 10.0,
                      width: int = 60) -> str:
        """ASCII热力图"""
        buckets = self.heatmap(bucket_sec)
        if not buckets:
            return "无数据"
        
        max_speed = max(b.avg_speed for b in buckets) if buckets else 1
        lines = []
        for b in buckets:
            bar_len = int(b.avg_speed / max_speed * width) if max_speed > 0 else 0
            mins = int(b.start_sec // 60)
            secs = int(b.start_sec % 60)
            bar = "█" * bar_len
            lines.append(f"{mins:02d}:{secs:02d} |{bar}")
        
        return "\n".join(lines)


class FunscriptAnalyzer:
    """Funscript分析引擎"""
    
    def analyze(self, path: str | Path) -> AnalysisReport:
        """分析单个funscript文件"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        actions = data.get("actions", [])
        if not actions:
            return AnalysisReport(title=path.stem, source_path=str(path))
        
        actions.sort(key=lambda a: a["at"])
        
        # 推断轴
        from .funscript_naming import FunscriptNaming
        try:
            file_info = FunscriptNaming.parse_filename(path)
            axis = file_info.axis_code
        except ValueError:
            axis = "L0"
        
        axis_report = self._analyze_actions(actions, axis)
        duration = actions[-1]["at"] / 1000.0
        
        report = AnalysisReport(
            title=path.stem,
            source_path=str(path),
            duration_sec=duration,
            axes={axis: axis_report},
            overall_intensity=axis_report.speed_stats.intensity_label,
            quality_score=axis_report.quality_score,
        )
        
        # 自动章节检测
        report.chapters = self._detect_chapters(actions, duration)
        
        return report
    
    def analyze_multi(self, base_path: str | Path) -> AnalysisReport:
        """分析多轴funscript文件集"""
        from .funscript_naming import FunscriptNaming
        
        base_path = Path(base_path)
        scripts = FunscriptNaming.find_scripts_for_video(base_path)
        
        if not scripts:
            scripts = FunscriptNaming.find_scripts(
                base_path.parent, base_path.stem)
        
        if not scripts:
            return self.analyze(base_path)
        
        report = AnalysisReport(
            title=base_path.stem,
            source_path=str(base_path),
        )
        
        max_duration = 0.0
        total_quality = 0.0
        intensities = []
        
        for sf in scripts:
            try:
                with open(sf.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                actions = data.get("actions", [])
                if not actions:
                    continue
                actions.sort(key=lambda a: a["at"])
                
                axis_report = self._analyze_actions(actions, sf.axis_code)
                report.axes[sf.axis_code] = axis_report
                
                dur = actions[-1]["at"] / 1000.0
                if dur > max_duration:
                    max_duration = dur
                
                total_quality += axis_report.quality_score
                intensities.append(axis_report.speed_stats.avg_speed)
                
            except Exception as e:
                logger.warning(f"分析失败 {sf.path}: {e}")
        
        report.duration_sec = max_duration
        
        if report.axes:
            report.quality_score = total_quality / len(report.axes)
            avg_intensity = sum(intensities) / len(intensities)
            if avg_intensity < 100:
                report.overall_intensity = "缓慢"
            elif avg_intensity < 250:
                report.overall_intensity = "中等"
            elif avg_intensity < 400:
                report.overall_intensity = "激烈"
            else:
                report.overall_intensity = "极限"
        
        # 从主轴检测章节
        main_path = base_path
        if not main_path.suffix == ".funscript":
            main_path = base_path.with_suffix(".funscript")
        if main_path.exists():
            with open(main_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            actions = data.get("actions", [])
            if actions:
                actions.sort(key=lambda a: a["at"])
                report.chapters = self._detect_chapters(
                    actions, max_duration)
        
        return report
    
    def _analyze_actions(self, actions: list[dict],
                         axis: str) -> AxisReport:
        """分析动作点列表"""
        if not actions:
            return AxisReport(axis=axis)
        
        positions = [a["pos"] for a in actions]
        
        # 计算速度 (pos变化/秒)
        speeds = []
        for i in range(1, len(actions)):
            dt = (actions[i]["at"] - actions[i-1]["at"]) / 1000.0
            if dt > 0:
                dp = abs(actions[i]["pos"] - actions[i-1]["pos"])
                speeds.append(dp / dt)
        
        if not speeds:
            return AxisReport(
                axis=axis,
                action_count=len(actions),
                duration_sec=actions[-1]["at"] / 1000.0,
            )
        
        speeds.sort()
        avg_speed = sum(speeds) / len(speeds)
        median_speed = speeds[len(speeds) // 2]
        
        # 标准差
        variance = sum((s - avg_speed) ** 2 for s in speeds) / len(speeds)
        std_dev = math.sqrt(variance)
        
        # 行程计数 (方向反转次数 / 2)
        stroke_count = 0
        if len(actions) >= 3:
            for i in range(2, len(actions)):
                d1 = actions[i-1]["pos"] - actions[i-2]["pos"]
                d2 = actions[i]["pos"] - actions[i-1]["pos"]
                if d1 * d2 < 0 and abs(d1) > 5 and abs(d2) > 5:
                    stroke_count += 1
            stroke_count = max(1, stroke_count // 2)
        
        # 质量评分
        quality = self._quality_score(actions, speeds, avg_speed, std_dev)
        
        return AxisReport(
            axis=axis,
            action_count=len(actions),
            duration_sec=actions[-1]["at"] / 1000.0,
            speed_stats=SpeedStats(
                avg_speed=avg_speed,
                max_speed=max(speeds),
                min_speed=min(speeds),
                median_speed=median_speed,
                std_dev=std_dev,
            ),
            position_range=(min(positions), max(positions)),
            avg_position=sum(positions) / len(positions),
            stroke_count=stroke_count,
            quality_score=quality,
        )
    
    def _quality_score(self, actions: list[dict], speeds: list[float],
                       avg_speed: float, std_dev: float) -> float:
        """计算脚本质量评分 (0-100)
        
        评分维度:
        - 动作密度: 每秒动作点数 (太少=低质, 太多=噪声)
        - 行程覆盖: 位置范围是否覆盖0-100
        - 平滑度: 速度标准差相对于均值的比例
        - 极端值: 不合理的极快速度占比
        """
        score = 100.0
        
        duration_sec = actions[-1]["at"] / 1000.0 if actions else 1
        density = len(actions) / duration_sec
        
        # 密度评分 (理想: 2-10/秒)
        if density < 0.5:
            score -= 30  # 太稀疏
        elif density < 2:
            score -= 10
        elif density > 30:
            score -= 20  # 太密集(噪声)
        
        # 行程覆盖评分
        positions = [a["pos"] for a in actions]
        pos_range = max(positions) - min(positions)
        if pos_range < 20:
            score -= 25  # 行程太小
        elif pos_range < 50:
            score -= 10
        
        # 平滑度评分
        if avg_speed > 0:
            cv = std_dev / avg_speed  # 变异系数
            if cv > 3.0:
                score -= 15  # 速度变化太剧烈
        
        # 极端速度惩罚
        extreme_count = sum(1 for s in speeds if s > 1000)
        extreme_ratio = extreme_count / len(speeds) if speeds else 0
        if extreme_ratio > 0.1:
            score -= 20
        
        return max(0.0, min(100.0, score))
    
    def _detect_chapters(self, actions: list[dict],
                         duration_sec: float,
                         min_chapter_sec: float = 30.0) -> list[Chapter]:
        """根据强度变化自动检测章节
        
        使用滑动窗口计算局部平均速度，
        在速度显著变化处分割章节。
        """
        if not actions or duration_sec < min_chapter_sec * 2:
            return []
        
        # 计算每10秒的平均速度
        window = 10.0
        bucket_speeds = []
        t = 0.0
        while t < duration_sec:
            speeds = []
            for i in range(1, len(actions)):
                a_t = actions[i]["at"] / 1000.0
                if t <= a_t < t + window:
                    dt = (actions[i]["at"] - actions[i-1]["at"]) / 1000.0
                    if dt > 0:
                        dp = abs(actions[i]["pos"] - actions[i-1]["pos"])
                        speeds.append(dp / dt)
            avg = sum(speeds) / len(speeds) if speeds else 0
            bucket_speeds.append((t, avg))
            t += window
        
        if len(bucket_speeds) < 3:
            return []
        
        # 平滑
        smoothed = []
        for i in range(len(bucket_speeds)):
            window_vals = [bucket_speeds[j][1]
                          for j in range(max(0, i-2), min(len(bucket_speeds), i+3))]
            smoothed.append(sum(window_vals) / len(window_vals))
        
        # 寻找显著变化点 (> 均值的50%变化)
        avg_speed = sum(smoothed) / len(smoothed) if smoothed else 1
        threshold = avg_speed * 0.5
        
        change_points = [0.0]
        for i in range(1, len(smoothed)):
            if abs(smoothed[i] - smoothed[i-1]) > threshold:
                t = bucket_speeds[i][0]
                if t - change_points[-1] >= min_chapter_sec:
                    change_points.append(t)
        change_points.append(duration_sec)
        
        # 生成章节
        intensity_labels = {
            (0, 100): "缓慢",
            (100, 250): "中等",
            (250, 400): "激烈",
            (400, float("inf")): "极限",
        }
        
        chapters = []
        for i in range(len(change_points) - 1):
            start = change_points[i]
            end = change_points[i + 1]
            
            # 计算区间平均强度
            seg_speeds = [smoothed[j]
                         for j, (t, _) in enumerate(bucket_speeds)
                         if start <= t < end]
            avg_int = sum(seg_speeds) / len(seg_speeds) if seg_speeds else 0
            
            label = "缓慢"
            for (lo, hi), lbl in intensity_labels.items():
                if lo <= avg_int < hi:
                    label = lbl
                    break
            
            chapters.append(Chapter(
                start_sec=start,
                end_sec=end,
                label=label,
                avg_intensity=avg_int,
            ))
        
        return chapters
    
    @staticmethod
    def _compute_heatmap_static(path: str,
                                bucket_sec: float) -> list[HeatmapBucket]:
        """计算热力图桶"""
        path = Path(path)
        if not path.exists():
            return []
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        actions = data.get("actions", [])
        if len(actions) < 2:
            return []
        
        actions.sort(key=lambda a: a["at"])
        duration = actions[-1]["at"] / 1000.0
        
        buckets = []
        t = 0.0
        
        while t < duration:
            speeds = []
            count = 0
            for i in range(1, len(actions)):
                a_t = actions[i]["at"] / 1000.0
                if t <= a_t < t + bucket_sec:
                    dt = (actions[i]["at"] - actions[i-1]["at"]) / 1000.0
                    if dt > 0:
                        dp = abs(actions[i]["pos"] - actions[i-1]["pos"])
                        speeds.append(dp / dt)
                    count += 1
            
            avg = sum(speeds) / len(speeds) if speeds else 0
            mx = max(speeds) if speeds else 0
            
            buckets.append(HeatmapBucket(
                start_sec=t,
                end_sec=min(t + bucket_sec, duration),
                avg_speed=avg,
                max_speed=mx,
                action_count=count,
            ))
            t += bucket_sec
        
        # 归一化强度
        max_avg = max(b.avg_speed for b in buckets) if buckets else 1
        for b in buckets:
            b.intensity = b.avg_speed / max_avg if max_avg > 0 else 0
        
        return buckets
