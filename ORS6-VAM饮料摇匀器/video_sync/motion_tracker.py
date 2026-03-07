"""
视频人物运动追踪 → TCode命令转换

将视频中人物的骨骼运动映射到OSR设备的6轴TCode命令。
支持两种模式:
1. 离线模式: 分析视频 → 生成多轴.funscript文件
2. 实时模式: 摄像头/视频流 → 实时TCode命令

依赖: mediapipe (Google姿态估计), opencv-python
安装: pip install mediapipe opencv-python

注意: 这是实验性模块。对于生产级使用，推荐:
- FunGen AI (150⭐) — 专业AI funscript生成
- Python-Funscript-Editor (77⭐) — OpenCV运动追踪+手动校正
"""

import json
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BodyKeypoints:
    """人体关键点 (归一化坐标 0.0-1.0)"""
    nose: tuple[float, float, float] = (0.5, 0.5, 0.0)
    left_shoulder: tuple[float, float, float] = (0.4, 0.4, 0.0)
    right_shoulder: tuple[float, float, float] = (0.6, 0.4, 0.0)
    left_hip: tuple[float, float, float] = (0.4, 0.6, 0.0)
    right_hip: tuple[float, float, float] = (0.6, 0.6, 0.0)
    left_elbow: tuple[float, float, float] = (0.3, 0.5, 0.0)
    right_elbow: tuple[float, float, float] = (0.7, 0.5, 0.0)
    timestamp_ms: float = 0.0
    confidence: float = 0.0


@dataclass
class TCodeFrame:
    """单帧TCode数据"""
    timestamp_ms: float = 0.0
    L0: int = 5000  # 行程 (上下)
    L1: int = 5000  # 推进 (前后)
    L2: int = 5000  # 摆动 (左右)
    R0: int = 5000  # 扭转
    R1: int = 5000  # 横滚
    R2: int = 5000  # 俯仰
    
    def to_tcode(self) -> str:
        """转换为TCode命令字符串"""
        parts = []
        for axis in ["L0", "L1", "L2", "R0", "R1", "R2"]:
            val = getattr(self, axis)
            parts.append(f"{axis}{val:04d}")
        return " ".join(parts) + "\n"
    
    def to_funscript_actions(self) -> dict[str, dict]:
        """转换为funscript动作点 (每轴一个)"""
        result = {}
        for axis in ["L0", "L1", "L2", "R0", "R1", "R2"]:
            val = getattr(self, axis)
            # funscript位置: 0-100
            pos = int(val / 9999 * 100)
            result[axis] = {
                "at": int(self.timestamp_ms),
                "pos": max(0, min(100, pos)),
            }
        return result


@dataclass
class TrackerConfig:
    """运动追踪配置"""
    # 姿态估计
    model_complexity: int = 1  # 0=轻量, 1=标准, 2=精确
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    
    # 轴映射灵敏度 (乘数)
    stroke_sensitivity: float = 2.0   # L0
    surge_sensitivity: float = 1.5    # L1
    sway_sensitivity: float = 1.5     # L2
    twist_sensitivity: float = 2.0    # R0
    roll_sensitivity: float = 1.5     # R1
    pitch_sensitivity: float = 1.5    # R2
    
    # 平滑
    smoothing_factor: float = 0.3  # 0=无平滑, 1=最大平滑
    
    # 输出
    output_fps: int = 30  # funscript输出帧率
    
    # 关键点选择
    track_point: str = "hip"  # hip / shoulder / nose


class MotionTracker:
    """视频运动追踪器
    
    将视频中的人物运动转换为TCode命令。
    
    用法:
        tracker = MotionTracker(TrackerConfig(stroke_sensitivity=2.5))
        
        # 离线: 视频 → funscript文件
        tracker.video_to_funscripts("video.mp4", "output_dir/")
        
        # 分析单帧
        frame = tracker.process_frame(image_array)
    """
    
    def __init__(self, config: TrackerConfig = None):
        self.config = config or TrackerConfig()
        self._pose = None
        self._mp = None
        self._prev_frame: Optional[TCodeFrame] = None
        self._prev_keypoints: Optional[BodyKeypoints] = None
        self._baseline_hip_y: Optional[float] = None
        self._frames: list[TCodeFrame] = []
    
    def _ensure_mediapipe(self):
        """确保mediapipe已导入"""
        if self._mp is not None:
            return True
        
        try:
            import mediapipe as mp
            self._mp = mp
            self._pose = mp.solutions.pose.Pose(
                model_complexity=self.config.model_complexity,
                min_detection_confidence=self.config.min_detection_confidence,
                min_tracking_confidence=self.config.min_tracking_confidence,
            )
            return True
        except ImportError:
            logger.error(
                "需要安装 mediapipe: pip install mediapipe opencv-python"
            )
            return False
    
    def extract_keypoints(self, image, timestamp_ms: float = 0.0
                          ) -> Optional[BodyKeypoints]:
        """从图像提取人体关键点
        
        Args:
            image: BGR numpy数组 (OpenCV格式)
            timestamp_ms: 当前时间戳(毫秒)
            
        Returns:
            BodyKeypoints 或 None(未检测到人体)
        """
        if not self._ensure_mediapipe():
            return None
        
        import cv2
        mp_pose = self._mp.solutions.pose
        
        # BGR→RGB
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self._pose.process(rgb)
        
        if not results.pose_landmarks:
            return None
        
        lm = results.pose_landmarks.landmark
        
        def get_point(idx):
            p = lm[idx]
            return (p.x, p.y, p.z)
        
        kp = BodyKeypoints(
            nose=get_point(mp_pose.PoseLandmark.NOSE),
            left_shoulder=get_point(mp_pose.PoseLandmark.LEFT_SHOULDER),
            right_shoulder=get_point(mp_pose.PoseLandmark.RIGHT_SHOULDER),
            left_hip=get_point(mp_pose.PoseLandmark.LEFT_HIP),
            right_hip=get_point(mp_pose.PoseLandmark.RIGHT_HIP),
            left_elbow=get_point(mp_pose.PoseLandmark.LEFT_ELBOW),
            right_elbow=get_point(mp_pose.PoseLandmark.RIGHT_ELBOW),
            timestamp_ms=timestamp_ms,
            confidence=min(
                lm[mp_pose.PoseLandmark.LEFT_HIP].visibility,
                lm[mp_pose.PoseLandmark.RIGHT_HIP].visibility,
            ),
        )
        
        return kp
    
    def keypoints_to_tcode(self, kp: BodyKeypoints) -> TCodeFrame:
        """将骨骼关键点映射为TCode帧
        
        映射逻辑:
        - L0 (行程): 骨盆Y轴运动幅度
        - L1 (推进): 骨盆Z轴深度变化
        - L2 (摆动): 骨盆X轴水平偏移
        - R0 (扭转): 双肩Z轴差 (旋转)
        - R1 (横滚): 双肩Y轴差 (倾斜)
        - R2 (俯仰): 肩-髋垂直角度变化
        """
        cfg = self.config
        
        # 骨盆中心
        hip_cx = (kp.left_hip[0] + kp.right_hip[0]) / 2
        hip_cy = (kp.left_hip[1] + kp.right_hip[1]) / 2
        hip_cz = (kp.left_hip[2] + kp.right_hip[2]) / 2
        
        # 初始化基线
        if self._baseline_hip_y is None:
            self._baseline_hip_y = hip_cy
        
        # 肩膀中心
        sh_cx = (kp.left_shoulder[0] + kp.right_shoulder[0]) / 2
        sh_cy = (kp.left_shoulder[1] + kp.right_shoulder[1]) / 2
        
        # L0: 骨盆Y运动 (下=0, 上=9999)
        dy = (self._baseline_hip_y - hip_cy) * cfg.stroke_sensitivity
        l0 = int(max(0, min(9999, 5000 + dy * 10000)))
        
        # L1: 骨盆Z深度 (远=0, 近=9999)
        l1 = int(max(0, min(9999, 5000 - hip_cz * cfg.surge_sensitivity * 5000)))
        
        # L2: 骨盆X偏移 (左=0, 右=9999)
        dx = (hip_cx - 0.5) * cfg.sway_sensitivity
        l2 = int(max(0, min(9999, 5000 + dx * 10000)))
        
        # R0: 双肩旋转 (Z轴差)
        shoulder_twist = (kp.left_shoulder[2] - kp.right_shoulder[2])
        r0 = int(max(0, min(9999,
                 5000 + shoulder_twist * cfg.twist_sensitivity * 10000)))
        
        # R1: 双肩倾斜 (Y轴差)
        shoulder_roll = (kp.left_shoulder[1] - kp.right_shoulder[1])
        r1 = int(max(0, min(9999,
                 5000 + shoulder_roll * cfg.roll_sensitivity * 10000)))
        
        # R2: 躯干前倾 (肩-髋Y差异变化)
        torso_lean = (sh_cy - hip_cy + 0.25) * 2  # 归一化
        r2 = int(max(0, min(9999,
                 torso_lean * cfg.pitch_sensitivity * 5000)))
        
        frame = TCodeFrame(
            timestamp_ms=kp.timestamp_ms,
            L0=l0, L1=l1, L2=l2,
            R0=r0, R1=r1, R2=r2,
        )
        
        # 平滑处理
        if self._prev_frame and cfg.smoothing_factor > 0:
            sf = cfg.smoothing_factor
            for axis in ["L0", "L1", "L2", "R0", "R1", "R2"]:
                prev_val = getattr(self._prev_frame, axis)
                curr_val = getattr(frame, axis)
                smoothed = int(prev_val * sf + curr_val * (1 - sf))
                setattr(frame, axis, smoothed)
        
        self._prev_frame = frame
        self._prev_keypoints = kp
        return frame
    
    def process_frame(self, image, timestamp_ms: float = 0.0
                      ) -> Optional[TCodeFrame]:
        """处理单帧图像 → TCode帧
        
        Args:
            image: BGR numpy数组
            timestamp_ms: 时间戳(毫秒)
            
        Returns:
            TCodeFrame 或 None
        """
        kp = self.extract_keypoints(image, timestamp_ms)
        if kp is None or kp.confidence < self.config.min_detection_confidence:
            return None
        return self.keypoints_to_tcode(kp)
    
    def video_to_funscripts(self, video_path: str, output_dir: str,
                            progress_callback=None) -> dict[str, str]:
        """分析视频生成多轴funscript文件
        
        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            progress_callback: 进度回调 (current_frame, total_frames)
            
        Returns:
            {轴代码: 输出文件路径} 字典
        """
        try:
            import cv2
        except ImportError:
            logger.error("需要安装 opencv-python: pip install opencv-python")
            return {}
        
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.error(f"无法打开视频: {video_path}")
            return {}
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_ms = total_frames / fps * 1000 if fps > 0 else 0
        
        logger.info(
            f"分析视频: {video_path.name}, "
            f"{total_frames}帧, {fps:.1f}fps, {duration_ms/1000:.1f}s"
        )
        
        # 采样间隔 (按输出fps)
        sample_interval = max(1, int(fps / self.config.output_fps))
        
        # 收集每轴的动作点
        axis_actions: dict[str, list[dict]] = {
            ax: [] for ax in ["L0", "L1", "L2", "R0", "R1", "R2"]
        }
        
        frame_idx = 0
        self._baseline_hip_y = None
        self._prev_frame = None
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_idx % sample_interval == 0:
                ts = frame_idx / fps * 1000
                tcode_frame = self.process_frame(frame, ts)
                
                if tcode_frame:
                    actions = tcode_frame.to_funscript_actions()
                    for axis, action in actions.items():
                        axis_actions[axis].append(action)
            
            frame_idx += 1
            
            if progress_callback and frame_idx % 100 == 0:
                progress_callback(frame_idx, total_frames)
        
        cap.release()
        
        if progress_callback:
            progress_callback(total_frames, total_frames)
        
        # 生成funscript文件
        video_stem = video_path.stem
        suffix_map = {
            "L0": "", "L1": "surge", "L2": "sway",
            "R0": "twist", "R1": "roll", "R2": "pitch",
        }
        
        output_files = {}
        for axis, actions in axis_actions.items():
            if not actions:
                continue
            
            suffix = suffix_map[axis]
            if suffix:
                filename = f"{video_stem}.{suffix}.funscript"
            else:
                filename = f"{video_stem}.funscript"
            
            filepath = output_dir / filename
            
            funscript = {
                "version": "1.0",
                "inverted": False,
                "range": 100,
                "actions": actions,
                "metadata": {
                    "creator": "ORS6-VAM MotionTracker",
                    "description": f"Auto-generated from {video_path.name}",
                    "duration": int(duration_ms),
                    "average_speed": 0,
                    "type": "basic",
                },
            }
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(funscript, f, indent=2)
            
            output_files[axis] = str(filepath)
            logger.info(f"生成: {filename} ({len(actions)}个动作点)")
        
        return output_files
    
    def reset(self):
        """重置追踪器状态"""
        self._prev_frame = None
        self._prev_keypoints = None
        self._baseline_hip_y = None
        self._frames.clear()
    
    def close(self):
        """释放资源"""
        if self._pose:
            self._pose.close()
            self._pose = None
        self._mp = None
