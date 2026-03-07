"""
节拍同步器 — 音频节拍/onset检测 → Funscript自动生成

基于librosa实现,支持:
- 音乐节拍(beat)检测 → 主轴(L0)运动
- 音频onset检测 → 辅助轴动作
- 频谱分析 → 多轴映射(低频→L0, 中频→R0, 高频→V0)
- 节拍强度 → 行程幅度映射
- 自定义节拍模式(半拍/倍拍/三连音)
- 输出标准.funscript文件

用法:
    syncer = BeatSyncer()
    
    # 从音频生成funscript
    result = syncer.generate("music.wav")
    result.save("music.funscript")
    
    # 多轴生成 (低频/中频/高频分离)
    multi = syncer.generate_multi("music.wav")
    multi.save_all("output/")  # music.funscript, music.twist.funscript, ...
    
    # 自定义配置
    syncer = BeatSyncer(BeatSyncConfig(
        mode="onset",           # "beat" | "onset" | "hybrid"
        beat_divisor=2,         # 半拍
        intensity_curve="sine", # "linear" | "sine" | "bounce"
        min_pos=10, max_pos=90, # 行程范围
    ))
"""

import json
import math
import logging
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Literal
from enum import Enum

logger = logging.getLogger(__name__)


class SyncMode(str, Enum):
    BEAT = "beat"       # 仅节拍点
    ONSET = "onset"     # 音频onset (更密集)
    HYBRID = "hybrid"   # 节拍+onset混合


class IntensityCurve(str, Enum):
    LINEAR = "linear"   # 线性插值
    SINE = "sine"       # 正弦波 (自然感)
    BOUNCE = "bounce"   # 弹跳 (快下慢上)
    SAWTOOTH = "saw"    # 锯齿波 (快速抽插)


# 频率范围定义 (Hz)
FREQ_BANDS = {
    "bass":   (20, 250),     # 低频 → L0 (主轴, 上下)
    "mid":    (250, 2000),   # 中频 → R0 (旋转)
    "treble": (2000, 8000),  # 高频 → V0 (震动)
}

# 轴映射
BAND_AXIS_MAP = {
    "bass": "L0",
    "mid": "R0",
    "treble": "V0",
}

# 轴后缀映射 (用于多轴funscript命名)
AXIS_SUFFIX = {
    "L0": "",
    "L1": ".surge",
    "L2": ".sway",
    "R0": ".twist",
    "R1": ".roll",
    "R2": ".pitch",
    "V0": ".vib",
    "V1": ".lube",
}


@dataclass
class BeatSyncConfig:
    """节拍同步配置"""
    mode: str = "beat"              # beat/onset/hybrid
    beat_divisor: int = 1           # 1=全拍, 2=半拍, 4=四分音
    intensity_curve: str = "sine"   # linear/sine/bounce/saw
    min_pos: int = 5                # funscript最小位置 (0-100)
    max_pos: int = 95               # funscript最大位置 (0-100)
    
    # onset参数
    onset_delta: float = 0.07       # onset检测灵敏度 (越小越灵敏)
    onset_wait: int = 5             # onset间最小帧间隔
    
    # 强度映射
    use_intensity: bool = True      # 节拍强度映射到行程
    intensity_min: float = 0.3      # 弱拍最小行程比例
    intensity_smoothing: int = 3    # 强度平滑窗口
    
    # 多轴
    multi_axis: bool = False        # 启用多轴生成
    bass_weight: float = 1.0        # 低频权重
    mid_weight: float = 0.6         # 中频权重
    treble_weight: float = 0.4      # 高频权重
    
    # 音频处理
    sr: int = 22050                 # 采样率
    hop_length: int = 512           # librosa hop长度


@dataclass
class BeatAction:
    """单个funscript动作"""
    at: int     # 时间戳 (ms)
    pos: int    # 位置 (0-100)


@dataclass
class SyncResult:
    """同步生成结果"""
    actions: list[BeatAction] = field(default_factory=list)
    axis: str = "L0"
    tempo: float = 0.0
    duration_sec: float = 0.0
    beat_count: int = 0
    onset_count: int = 0
    
    @property
    def action_count(self) -> int:
        return len(self.actions)
    
    def to_funscript(self) -> dict:
        """转换为funscript JSON格式"""
        return {
            "version": "1.0",
            "inverted": False,
            "range": 100,
            "metadata": {
                "creator": "BeatSyncer",
                "tempo": round(self.tempo, 1),
                "duration": round(self.duration_sec, 1),
                "type": "beat-sync",
            },
            "actions": [
                {"at": a.at, "pos": a.pos} for a in self.actions
            ]
        }
    
    def save(self, path: str):
        """保存为.funscript文件"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(self.to_funscript(), f, indent=2)
        logger.info(f"已保存: {p.name} ({self.action_count}个动作, "
                     f"{self.tempo:.0f}BPM)")
    
    def summary(self) -> str:
        return (f"[{self.axis}] {self.action_count}动作 | "
                f"{self.tempo:.0f}BPM | {self.duration_sec:.1f}s | "
                f"{self.beat_count}拍 {self.onset_count}onset")


@dataclass
class MultiSyncResult:
    """多轴同步结果"""
    results: dict[str, SyncResult] = field(default_factory=dict)
    
    @property
    def axes(self) -> list[str]:
        return list(self.results.keys())
    
    def save_all(self, output_dir: str, base_name: str = "output"):
        """保存所有轴的funscript文件"""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        
        for axis, result in self.results.items():
            suffix = AXIS_SUFFIX.get(axis, f".{axis.lower()}")
            filename = f"{base_name}{suffix}.funscript"
            result.save(str(out / filename))
    
    def summary(self) -> str:
        lines = [f"多轴同步: {len(self.results)}轴"]
        for axis, r in self.results.items():
            lines.append(f"  {r.summary()}")
        return "\n".join(lines)


class BeatSyncer:
    """节拍同步器 — 音频分析→Funscript生成
    
    核心链路: 音频 → librosa分析 → 节拍/onset → 动作序列 → funscript
    """
    
    def __init__(self, config: BeatSyncConfig = None):
        self.config = config or BeatSyncConfig()
        self._ensure_librosa()
    
    def _ensure_librosa(self):
        """检查librosa是否可用"""
        try:
            import librosa
            self._librosa = librosa
        except ImportError:
            raise ImportError(
                "librosa未安装。请运行: pip install librosa"
            )
    
    def generate(self, audio_path: str) -> SyncResult:
        """从音频生成单轴funscript
        
        Args:
            audio_path: 音频文件路径 (.wav/.mp3/.ogg等)
            
        Returns:
            SyncResult包含动作序列
        """
        librosa = self._librosa
        cfg = self.config
        
        logger.info(f"分析音频: {audio_path}")
        
        # 加载音频
        y, sr = librosa.load(audio_path, sr=cfg.sr, mono=True)
        duration = len(y) / sr
        
        # 获取节拍/onset时间点
        if cfg.mode == "beat" or cfg.mode == "hybrid":
            tempo, beat_frames = librosa.beat.beat_track(
                y=y, sr=sr, hop_length=cfg.hop_length
            )
            beat_times = librosa.frames_to_time(
                beat_frames, sr=sr, hop_length=cfg.hop_length
            )
            # 处理tempo (librosa可能返回数组)
            if hasattr(tempo, '__len__'):
                tempo = float(tempo[0]) if len(tempo) > 0 else 120.0
            else:
                tempo = float(tempo)
        else:
            tempo = 0.0
            beat_times = np.array([])
        
        if cfg.mode == "onset" or cfg.mode == "hybrid":
            onset_env = librosa.onset.onset_strength(
                y=y, sr=sr, hop_length=cfg.hop_length
            )
            onset_frames = librosa.onset.onset_detect(
                onset_envelope=onset_env, sr=sr,
                hop_length=cfg.hop_length,
                delta=cfg.onset_delta,
                wait=cfg.onset_wait
            )
            onset_times = librosa.frames_to_time(
                onset_frames, sr=sr, hop_length=cfg.hop_length
            )
        else:
            onset_env = None
            onset_times = np.array([])
        
        # 合并时间点
        if cfg.mode == "hybrid":
            all_times = np.unique(np.concatenate([beat_times, onset_times]))
        elif cfg.mode == "beat":
            all_times = beat_times
        else:
            all_times = onset_times
        
        # 节拍细分 (半拍/四分音)
        if cfg.beat_divisor > 1 and len(all_times) > 1:
            all_times = self._subdivide_beats(all_times, cfg.beat_divisor)
        
        all_times.sort()
        
        # 计算强度 (如果启用)
        intensities = None
        if cfg.use_intensity and onset_env is not None:
            intensities = self._compute_intensities(
                all_times, onset_env, sr, cfg.hop_length
            )
        
        # 生成动作序列
        actions = self._times_to_actions(
            all_times, intensities, cfg.intensity_curve
        )
        
        result = SyncResult(
            actions=actions,
            axis="L0",
            tempo=tempo,
            duration_sec=duration,
            beat_count=len(beat_times),
            onset_count=len(onset_times),
        )
        
        logger.info(f"生成完成: {result.summary()}")
        return result
    
    def generate_multi(self, audio_path: str) -> MultiSyncResult:
        """多轴生成 — 频谱分离→不同轴
        
        - 低频(20-250Hz) → L0 (主轴上下)
        - 中频(250-2kHz) → R0 (旋转)
        - 高频(2k-8kHz) → V0 (震动)
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            MultiSyncResult包含多轴结果
        """
        librosa = self._librosa
        cfg = self.config
        
        logger.info(f"多轴分析: {audio_path}")
        
        y, sr = librosa.load(audio_path, sr=cfg.sr, mono=True)
        duration = len(y) / sr
        
        # 全局tempo
        tempo_val, _ = librosa.beat.beat_track(
            y=y, sr=sr, hop_length=cfg.hop_length
        )
        if hasattr(tempo_val, '__len__'):
            tempo_val = float(tempo_val[0]) if len(tempo_val) > 0 else 120.0
        else:
            tempo_val = float(tempo_val)
        
        # STFT for频谱分析
        S = np.abs(librosa.stft(y, hop_length=cfg.hop_length))
        freqs = librosa.fft_frequencies(sr=sr)
        
        multi = MultiSyncResult()
        weights = {
            "bass": cfg.bass_weight,
            "mid": cfg.mid_weight,
            "treble": cfg.treble_weight,
        }
        
        for band_name, (f_low, f_high) in FREQ_BANDS.items():
            axis = BAND_AXIS_MAP[band_name]
            weight = weights.get(band_name, 1.0)
            
            if weight <= 0:
                continue
            
            # 频带掩码
            band_mask = (freqs >= f_low) & (freqs <= f_high)
            if not band_mask.any():
                continue
            
            # 频带能量包络
            band_energy = S[band_mask, :].sum(axis=0)
            band_energy = band_energy / (band_energy.max() + 1e-8)
            
            # onset检测 (使用频带能量)
            onset_frames = librosa.onset.onset_detect(
                onset_envelope=band_energy, sr=sr,
                hop_length=cfg.hop_length,
                delta=cfg.onset_delta * (1.0 / weight),
                wait=cfg.onset_wait
            )
            onset_times = librosa.frames_to_time(
                onset_frames, sr=sr, hop_length=cfg.hop_length
            )
            
            if len(onset_times) < 2:
                continue
            
            # 强度计算
            intensities = self._compute_intensities(
                onset_times, band_energy, sr, cfg.hop_length
            )
            
            # 行程范围根据权重调整
            effective_range = int((cfg.max_pos - cfg.min_pos) * weight)
            effective_min = cfg.min_pos + (cfg.max_pos - cfg.min_pos - effective_range) // 2
            effective_max = effective_min + effective_range
            
            # 生成动作
            actions = self._times_to_actions(
                onset_times, intensities, cfg.intensity_curve,
                min_pos=effective_min, max_pos=effective_max
            )
            
            multi.results[axis] = SyncResult(
                actions=actions,
                axis=axis,
                tempo=tempo_val,
                duration_sec=duration,
                beat_count=0,
                onset_count=len(onset_times),
            )
        
        logger.info(f"多轴生成完成:\n{multi.summary()}")
        return multi
    
    def analyze_audio(self, audio_path: str) -> dict:
        """分析音频特征 (不生成funscript)
        
        Returns:
            包含tempo/beats/onsets/duration/spectral特征的字典
        """
        librosa = self._librosa
        cfg = self.config
        
        y, sr = librosa.load(audio_path, sr=cfg.sr, mono=True)
        
        tempo, beat_frames = librosa.beat.beat_track(
            y=y, sr=sr, hop_length=cfg.hop_length
        )
        if hasattr(tempo, '__len__'):
            tempo = float(tempo[0]) if len(tempo) > 0 else 0.0
        else:
            tempo = float(tempo)
        
        beat_times = librosa.frames_to_time(
            beat_frames, sr=sr, hop_length=cfg.hop_length
        )
        
        onset_env = librosa.onset.onset_strength(
            y=y, sr=sr, hop_length=cfg.hop_length
        )
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=onset_env, sr=sr,
            hop_length=cfg.hop_length
        )
        onset_times = librosa.frames_to_time(
            onset_frames, sr=sr, hop_length=cfg.hop_length
        )
        
        # 频谱特征
        spectral_centroid = librosa.feature.spectral_centroid(
            y=y, sr=sr
        ).mean()
        rms = librosa.feature.rms(y=y).mean()
        
        return {
            "duration": len(y) / sr,
            "tempo": tempo,
            "beat_count": len(beat_times),
            "onset_count": len(onset_times),
            "beat_times": beat_times.tolist(),
            "onset_times": onset_times.tolist(),
            "spectral_centroid": float(spectral_centroid),
            "rms_energy": float(rms),
            "recommended_mode": "beat" if tempo > 80 else "onset",
            "recommended_divisor": 2 if tempo < 100 else 1,
        }
    
    # ── 内部方法 ──
    
    def _subdivide_beats(self, times: np.ndarray, 
                          divisor: int) -> np.ndarray:
        """将节拍细分为半拍/四分音等"""
        subdivided = []
        for i in range(len(times) - 1):
            interval = (times[i + 1] - times[i]) / divisor
            for d in range(divisor):
                subdivided.append(times[i] + interval * d)
        subdivided.append(times[-1])
        return np.array(subdivided)
    
    def _compute_intensities(self, times: np.ndarray,
                              envelope: np.ndarray,
                              sr: int, hop_length: int) -> np.ndarray:
        """计算每个时间点的强度"""
        cfg = self.config
        frame_indices = self._librosa.time_to_frames(
            times, sr=sr, hop_length=hop_length
        )
        
        intensities = np.zeros(len(times))
        for i, fi in enumerate(frame_indices):
            fi = min(fi, len(envelope) - 1)
            intensities[i] = envelope[fi]
        
        # 归一化到 [intensity_min, 1.0]
        if intensities.max() > 0:
            intensities = intensities / intensities.max()
        intensities = np.clip(
            intensities, cfg.intensity_min, 1.0
        )
        
        # 平滑
        if cfg.intensity_smoothing > 1 and len(intensities) > cfg.intensity_smoothing:
            kernel = np.ones(cfg.intensity_smoothing) / cfg.intensity_smoothing
            intensities = np.convolve(intensities, kernel, mode='same')
            intensities = np.clip(intensities, cfg.intensity_min, 1.0)
        
        return intensities
    
    def _times_to_actions(self, times: np.ndarray,
                           intensities: Optional[np.ndarray],
                           curve: str,
                           min_pos: int = None,
                           max_pos: int = None) -> list[BeatAction]:
        """将时间点转换为funscript动作序列"""
        cfg = self.config
        min_p = min_pos if min_pos is not None else cfg.min_pos
        max_p = max_pos if max_pos is not None else cfg.max_pos
        
        actions = []
        going_up = True  # 交替上下
        
        for i, t in enumerate(times):
            ms = int(t * 1000)
            
            # 计算行程
            if intensities is not None and i < len(intensities):
                intensity = intensities[i]
            else:
                intensity = 1.0
            
            # 根据曲线计算位置
            if going_up:
                raw_pos = max_p
            else:
                raw_pos = min_p
            
            # 强度调制行程
            center = (min_p + max_p) / 2
            half_range = (max_p - min_p) / 2
            effective_range = half_range * intensity
            
            if going_up:
                pos = int(center + effective_range)
            else:
                pos = int(center - effective_range)
            
            pos = max(0, min(100, pos))
            actions.append(BeatAction(at=ms, pos=pos))
            going_up = not going_up
        
        # 应用曲线变形
        if curve == "sine":
            actions = self._apply_sine_curve(actions, min_p, max_p)
        elif curve == "bounce":
            actions = self._apply_bounce_curve(actions, min_p, max_p)
        elif curve == "saw":
            actions = self._apply_saw_curve(actions, min_p, max_p)
        
        return actions
    
    def _apply_sine_curve(self, actions: list[BeatAction],
                           min_p: int, max_p: int) -> list[BeatAction]:
        """正弦曲线 — 在动作间插入中间点实现平滑运动"""
        if len(actions) < 2:
            return actions
        
        smooth_actions = []
        for i in range(len(actions) - 1):
            a1, a2 = actions[i], actions[i + 1]
            smooth_actions.append(a1)
            
            # 在两个动作间插入一个中间点 (正弦过渡)
            mid_t = (a1.at + a2.at) // 2
            # 正弦缓入缓出
            progress = 0.5
            sine_val = (1 - math.cos(progress * math.pi)) / 2
            mid_pos = int(a1.pos + (a2.pos - a1.pos) * sine_val)
            smooth_actions.append(BeatAction(at=mid_t, pos=mid_pos))
        
        smooth_actions.append(actions[-1])
        return smooth_actions
    
    def _apply_bounce_curve(self, actions: list[BeatAction],
                             min_p: int, max_p: int) -> list[BeatAction]:
        """弹跳曲线 — 快速到达,缓慢回弹"""
        if len(actions) < 2:
            return actions
        
        bounce_actions = []
        for i in range(len(actions) - 1):
            a1, a2 = actions[i], actions[i + 1]
            bounce_actions.append(a1)
            
            # 在70%时间点插入过冲
            t_70 = a1.at + int((a2.at - a1.at) * 0.3)
            overshoot = int((a2.pos - a1.pos) * 1.15)
            over_pos = max(0, min(100, a1.pos + overshoot))
            bounce_actions.append(BeatAction(at=t_70, pos=over_pos))
        
        bounce_actions.append(actions[-1])
        return bounce_actions
    
    def _apply_saw_curve(self, actions: list[BeatAction],
                          min_p: int, max_p: int) -> list[BeatAction]:
        """锯齿波 — 快速移动到位,短暂停留"""
        if len(actions) < 2:
            return actions
        
        saw_actions = []
        for i in range(len(actions) - 1):
            a1, a2 = actions[i], actions[i + 1]
            saw_actions.append(a1)
            
            # 在20%时间点已到达目标位置
            t_20 = a1.at + int((a2.at - a1.at) * 0.2)
            saw_actions.append(BeatAction(at=t_20, pos=a2.pos))
            
            # 保持到80%
            t_80 = a1.at + int((a2.at - a1.at) * 0.8)
            saw_actions.append(BeatAction(at=t_80, pos=a2.pos))
        
        saw_actions.append(actions[-1])
        return saw_actions
    
    def __repr__(self):
        return (f"BeatSyncer(mode={self.config.mode}, "
                f"divisor={self.config.beat_divisor})")
