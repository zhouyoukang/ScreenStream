"""
Funscript多轴文件命名规范
兼容MultiFunPlayer / OFS / FunGen AI标准

标准: <video_name>.<axis_suffix>.funscript
例:   video.funscript          → L0 (主轴/行程)
      video.surge.funscript    → L1 (前后)
      video.twist.funscript    → R0 (旋转)
"""

from pathlib import Path
from dataclasses import dataclass


# MultiFunPlayer / OFS 标准轴后缀映射
AXIS_SUFFIX_MAP = {
    # TCode v0.2 + v0.3 通用
    "L0": "",           # 主轴无后缀
    "L1": "surge",
    "L2": "sway",
    "R0": "twist",
    "R1": "roll",
    "R2": "pitch",
    # TCode v0.3
    "V0": "vib",
    "A0": "valve",
    "A1": "suck",
    "A2": "lube",
}

# 反向映射: 后缀 → 轴代码
SUFFIX_TO_AXIS = {v: k for k, v in AXIS_SUFFIX_MAP.items() if v}
SUFFIX_TO_AXIS[""] = "L0"


@dataclass
class FunscriptFile:
    """解析后的Funscript文件信息"""
    path: Path
    video_name: str
    axis_code: str
    axis_suffix: str
    
    @property
    def display_name(self) -> str:
        if self.axis_suffix:
            return f"{self.video_name}.{self.axis_suffix}.funscript"
        return f"{self.video_name}.funscript"


class FunscriptNaming:
    """Funscript文件命名工具"""
    
    @staticmethod
    def parse_filename(filepath: str | Path) -> FunscriptFile:
        """解析funscript文件名，提取视频名和轴信息
        
        Args:
            filepath: funscript文件路径
            
        Returns:
            FunscriptFile 包含视频名、轴代码、后缀
        """
        path = Path(filepath)
        name = path.name
        
        if not name.endswith(".funscript"):
            raise ValueError(f"不是funscript文件: {name}")
        
        # 去掉 .funscript 后缀
        base = name[:-len(".funscript")]
        
        # 检查是否有轴后缀
        for suffix, axis in SUFFIX_TO_AXIS.items():
            if suffix and base.endswith(f".{suffix}"):
                video_name = base[:-len(f".{suffix}")]
                return FunscriptFile(
                    path=path,
                    video_name=video_name,
                    axis_code=axis,
                    axis_suffix=suffix,
                )
        
        # 无后缀 → L0主轴
        return FunscriptFile(
            path=path,
            video_name=base,
            axis_code="L0",
            axis_suffix="",
        )
    
    @staticmethod
    def build_filename(video_name: str, axis_code: str) -> str:
        """根据视频名和轴代码构建funscript文件名
        
        Args:
            video_name: 视频文件名(不含扩展名)
            axis_code: TCode轴代码 (L0, R0, V0等)
            
        Returns:
            funscript文件名
        """
        suffix = AXIS_SUFFIX_MAP.get(axis_code.upper(), "")
        if suffix:
            return f"{video_name}.{suffix}.funscript"
        return f"{video_name}.funscript"
    
    @staticmethod
    def find_scripts(directory: str | Path, video_name: str = None
                     ) -> list[FunscriptFile]:
        """在目录中查找所有funscript文件
        
        Args:
            directory: 搜索目录
            video_name: 可选，只查找匹配此视频名的脚本
            
        Returns:
            FunscriptFile列表，按轴排序
        """
        d = Path(directory)
        if not d.exists():
            return []
        
        results = []
        for f in d.glob("*.funscript"):
            try:
                info = FunscriptNaming.parse_filename(f)
                if video_name is None or info.video_name == video_name:
                    results.append(info)
            except ValueError:
                continue
        
        # 按轴代码排序 (L0, L1, L2, R0, R1, R2, V0, A0, A1, A2)
        axis_order = list(AXIS_SUFFIX_MAP.keys())
        results.sort(key=lambda x: axis_order.index(x.axis_code)
                     if x.axis_code in axis_order else 99)
        return results
    
    @staticmethod
    def find_scripts_for_video(video_path: str | Path) -> list[FunscriptFile]:
        """根据视频文件路径，查找同目录下所有匹配的funscript
        
        Args:
            video_path: 视频文件完整路径
            
        Returns:
            匹配的FunscriptFile列表
        """
        vp = Path(video_path)
        video_name = vp.stem  # 去掉扩展名
        return FunscriptNaming.find_scripts(vp.parent, video_name)
    
    @staticmethod
    def generate_all_filenames(video_name: str,
                                axes: list[str] = None) -> dict[str, str]:
        """为视频生成所有轴的funscript文件名
        
        Args:
            video_name: 视频名(不含扩展名)
            axes: 要生成的轴列表, None=全部
            
        Returns:
            {轴代码: 文件名} 字典
        """
        if axes is None:
            axes = list(AXIS_SUFFIX_MAP.keys())
        
        return {
            axis: FunscriptNaming.build_filename(video_name, axis)
            for axis in axes
            if axis.upper() in AXIS_SUFFIX_MAP
        }
