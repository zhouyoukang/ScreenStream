"""
端到端视频同步管道

将 Stash媒体库 → funscript脚本匹配 → MultiFunPlayer/本地设备播放 
串联为一键式工作流。

典型使用场景:
1. 用户在Stash中标记视频为interactive
2. pipeline自动查找匹配的多轴funscript
3. 启动MultiFunPlayer或本地FunscriptPlayer同步播放
4. 实时状态监控 + 安全保护

用法:
    pipe = SyncPipeline(SyncConfig(
        stash_port=9999,
        device_port="COM5",
    ))
    
    # 场景1: 从Stash查找并播放
    scenes = pipe.discover_scenes(query="", interactive_only=True)
    pipe.play_scene(scenes[0])
    
    # 场景2: 直接播放本地视频+脚本
    pipe.play_local("video.mp4", "scripts_dir/")
    
    # 场景3: 连接MultiFunPlayer监控
    await pipe.monitor_mfp()
"""

import time
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class SyncConfig:
    """同步管道配置"""
    # Stash
    stash_host: str = "127.0.0.1"
    stash_port: int = 9999
    stash_api_key: str = ""
    
    # XBVR
    xbvr_host: str = "127.0.0.1"
    xbvr_port: int = 9999
    
    # 视频下载
    download_dir: str = "downloads"
    proxy: str = ""               # 代理 (如 http://127.0.0.1:7890)
    max_resolution: Optional[int] = None  # 限制下载分辨率
    
    # 节拍同步
    beat_mode: str = "beat"        # beat/onset/hybrid
    beat_divisor: int = 1          # 1=全拍 2=半拍
    intensity_curve: str = "sine"  # linear/sine/bounce/saw
    multi_axis_beat: bool = False  # 多轴频谱分离
    
    # 设备连接 (串口优先, 其次WiFi)
    device_port: Optional[str] = None   # COM口, None=自动检测
    device_wifi: Optional[str] = None   # WiFi IP
    device_wifi_port: int = 8000
    
    # MultiFunPlayer
    mfp_host: str = "127.0.0.1"
    mfp_port: int = 8088
    
    # 脚本搜索
    script_dirs: list[str] = field(default_factory=list)
    
    # 播放
    update_hz: int = 60
    auto_play: bool = True
    
    # 安全
    max_speed: int = 15000
    position_min: int = 0
    position_max: int = 9999


@dataclass
class SceneInfo:
    """场景信息 (统一Stash和本地)"""
    title: str = ""
    video_path: str = ""
    duration_sec: float = 0.0
    scripts: dict[str, str] = field(default_factory=dict)
    source: str = "local"  # "stash" / "local"
    stash_id: str = ""
    tags: list[str] = field(default_factory=list)
    performers: list[str] = field(default_factory=list)
    
    @property
    def script_count(self) -> int:
        return len(self.scripts)
    
    @property
    def has_scripts(self) -> bool:
        return len(self.scripts) > 0
    
    def summary(self) -> str:
        axes = ", ".join(sorted(self.scripts.keys())) if self.scripts else "无"
        return (f"{self.title} [{self.duration_sec:.0f}s] "
                f"— {self.script_count}轴({axes})")


class SyncPipeline:
    """端到端视频同步管道
    
    连接 Stash媒体库 → funscript匹配 → 设备播放 的完整链路。
    """
    
    def __init__(self, config: SyncConfig = None):
        self.config = config or SyncConfig()
        self._player = None
        self._stash = None
        self._xbvr = None
        self._mfp = None
        self._fetcher = None
        self._syncer = None
        self._playing = False
        self._current_scene: Optional[SceneInfo] = None
        self._on_status: Optional[Callable] = None
    
    # ── 发现阶段 ──
    
    def discover_scenes(self, query: str = "",
                        interactive_only: bool = True,
                        limit: int = 50) -> list[SceneInfo]:
        """从Stash发现场景并匹配脚本
        
        Args:
            query: 搜索关键词
            interactive_only: 只返回标记为interactive的场景
            limit: 最大返回数量
            
        Returns:
            SceneInfo列表, 按脚本数量降序排列
        """
        stash = self._get_stash()
        if not stash.health_check():
            logger.error(f"Stash不可达: {stash.url}")
            return []
        
        if interactive_only:
            stash_scenes = stash.find_interactive_scenes(per_page=limit)
        else:
            stash_scenes = stash.find_scenes(
                query=query, per_page=limit)
        
        scenes = []
        for ss in stash_scenes:
            info = SceneInfo(
                title=ss.title or ss.filename,
                video_path=ss.path,
                duration_sec=ss.duration,
                source="stash",
                stash_id=ss.id,
                tags=ss.tags,
                performers=ss.performers,
            )
            info.scripts = self._find_scripts_for(ss.path)
            scenes.append(info)
        
        scenes.sort(key=lambda s: s.script_count, reverse=True)
        
        logger.info(f"发现 {len(scenes)} 个场景, "
                     f"{sum(1 for s in scenes if s.has_scripts)} 个有脚本")
        return scenes
    
    def discover_xbvr(self, query: str = "",
                       scripted_only: bool = True,
                       limit: int = 50) -> list[SceneInfo]:
        """从XBVR发现VR场景并匹配脚本
        
        Args:
            query: 搜索关键词
            scripted_only: 只返回有脚本的场景
            limit: 最大返回数量
            
        Returns:
            SceneInfo列表
        """
        xbvr = self._get_xbvr()
        if not xbvr.health_check():
            logger.error(f"XBVR不可达: {xbvr.base_url}")
            return []
        
        if query:
            xbvr_scenes = xbvr.search(query, limit=limit)
        elif scripted_only:
            xbvr_scenes = xbvr.find_scripted_scenes(limit=limit)
        else:
            xbvr_scenes = xbvr.find_scenes(limit=limit)
        
        scenes = []
        for xs in xbvr_scenes:
            info = SceneInfo(
                title=xs.title,
                video_path=xs.file_path,
                duration_sec=xs.duration,
                source="xbvr",
                tags=xs.tags,
                performers=xs.cast,
            )
            info.scripts = self._find_scripts_for(xs.file_path)
            if not scripted_only or info.has_scripts or xs.is_scripted:
                scenes.append(info)
        
        scenes.sort(key=lambda s: s.script_count, reverse=True)
        logger.info(f"XBVR发现 {len(scenes)} 个场景, "
                     f"{sum(1 for s in scenes if s.has_scripts)} 个有脚本")
        return scenes
    
    def discover_all(self, query: str = "",
                     scripted_only: bool = True) -> list[SceneInfo]:
        """从所有来源发现场景 (Stash + XBVR + 本地)
        
        自动去重，按脚本数量排序。
        """
        all_scenes = []
        seen_paths = set()
        
        # Stash
        try:
            for s in self.discover_scenes(query=query,
                                           interactive_only=scripted_only):
                if s.video_path not in seen_paths:
                    seen_paths.add(s.video_path)
                    all_scenes.append(s)
        except Exception as e:
            logger.warning(f"Stash发现失败: {e}")
        
        # XBVR
        try:
            for s in self.discover_xbvr(query=query,
                                         scripted_only=scripted_only):
                if s.video_path not in seen_paths:
                    seen_paths.add(s.video_path)
                    all_scenes.append(s)
        except Exception as e:
            logger.warning(f"XBVR发现失败: {e}")
        
        # 本地额外目录
        for d in self.config.script_dirs:
            try:
                for s in self.discover_local(d):
                    if s.video_path not in seen_paths:
                        seen_paths.add(s.video_path)
                        all_scenes.append(s)
            except Exception as e:
                logger.warning(f"本地目录 {d} 发现失败: {e}")
        
        all_scenes.sort(key=lambda s: s.script_count, reverse=True)
        logger.info(f"全源发现: {len(all_scenes)} 个场景")
        return all_scenes
    
    def discover_local(self, directory: str,
                       extensions: list[str] = None) -> list[SceneInfo]:
        """从本地目录发现视频和匹配的脚本
        
        Args:
            directory: 视频目录
            extensions: 视频扩展名列表
            
        Returns:
            SceneInfo列表
        """
        if extensions is None:
            extensions = [".mp4", ".mkv", ".avi", ".wmv", ".mov", ".webm"]
        
        d = Path(directory)
        if not d.exists():
            logger.error(f"目录不存在: {directory}")
            return []
        
        scenes = []
        for ext in extensions:
            for vf in d.glob(f"*{ext}"):
                info = SceneInfo(
                    title=vf.stem,
                    video_path=str(vf),
                    source="local",
                )
                info.scripts = self._find_scripts_for(str(vf))
                if info.has_scripts:
                    scenes.append(info)
        
        scenes.sort(key=lambda s: s.script_count, reverse=True)
        logger.info(f"本地发现 {len(scenes)} 个有脚本的视频")
        return scenes
    
    def _find_scripts_for(self, video_path: str) -> dict[str, str]:
        """查找视频匹配的所有funscript文件"""
        from .funscript_naming import FunscriptNaming
        
        result = {}
        
        # 1. 视频同目录查找
        scripts = FunscriptNaming.find_scripts_for_video(video_path)
        for sf in scripts:
            result[sf.axis_code] = str(sf.path)
        
        # 2. 额外脚本目录查找
        video_stem = Path(video_path).stem
        for sd in self.config.script_dirs:
            extra = FunscriptNaming.find_scripts(sd, video_stem)
            for sf in extra:
                if sf.axis_code not in result:
                    result[sf.axis_code] = str(sf.path)
        
        return result
    
    # ── 播放阶段 ──
    
    def play_scene(self, scene: SceneInfo) -> bool:
        """播放场景
        
        Args:
            scene: SceneInfo对象
            
        Returns:
            是否成功开始播放
        """
        if not scene.has_scripts:
            logger.error(f"场景无脚本: {scene.title}")
            return False
        
        self.stop()
        self._current_scene = scene
        
        player = self._get_player()
        
        # 加载所有轴脚本
        for axis, path in scene.scripts.items():
            try:
                player.load_single(path, axis)
            except Exception as e:
                logger.warning(f"加载脚本失败 {axis}: {e}")
        
        if not player._scripts:
            logger.error("无可用脚本")
            return False
        
        logger.info(f"▶ 播放: {scene.summary()}")
        player.play()
        self._playing = True
        return True
    
    def play_local(self, video_path: str,
                   script_dir: str = None) -> bool:
        """播放本地视频+脚本
        
        Args:
            video_path: 视频文件路径
            script_dir: 脚本目录 (None=视频同目录)
        """
        if script_dir:
            self.config.script_dirs = [script_dir]
        
        scene = SceneInfo(
            title=Path(video_path).stem,
            video_path=video_path,
            source="local",
        )
        scene.scripts = self._find_scripts_for(video_path)
        
        if not scene.has_scripts:
            logger.error(f"未找到匹配脚本: {video_path}")
            return False
        
        return self.play_scene(scene)
    
    def pause(self):
        """暂停"""
        if self._player:
            self._player.pause()
    
    def resume(self):
        """恢复"""
        if self._player:
            self._player.play()
    
    def stop(self):
        """停止播放"""
        if self._player and self._playing:
            self._player.stop()
        self._playing = False
        self._current_scene = None
    
    def seek(self, time_sec: float):
        """跳转"""
        if self._player:
            self._player.seek(time_sec)
    
    @property
    def status(self) -> dict:
        """当前状态"""
        result = {
            "playing": self._playing,
            "scene": self._current_scene.title if self._current_scene else None,
        }
        if self._player:
            result.update(self._player.status())
        return result
    
    # ── MultiFunPlayer监控模式 ──
    
    async def monitor_mfp(self, on_update: Callable = None):
        """连接MultiFunPlayer并监控播放状态
        
        适用于: 用户在DeoVR/HereSphere/VLC中播放视频,
        MultiFunPlayer处理脚本→设备同步,
        本管道监控状态供UI展示。
        
        Args:
            on_update: 状态更新回调
        """
        from .mfp_client import MultiFunPlayerClient, MFPConfig
        
        config = MFPConfig(
            host=self.config.mfp_host,
            port=self.config.mfp_port,
            on_playback_update=on_update,
        )
        
        self._mfp = MultiFunPlayerClient(config)
        connected = await self._mfp.connect()
        
        if connected:
            logger.info(f"已连接MultiFunPlayer: {self._mfp.url}")
        else:
            logger.error("连接MultiFunPlayer失败")
        
        return connected
    
    # ── 批量分析 ──
    
    def analyze_library(self, interactive_only: bool = True) -> dict:
        """分析Stash媒体库的脚本覆盖状况
        
        Returns:
            统计信息字典
        """
        scenes = self.discover_scenes(
            interactive_only=interactive_only, limit=500)
        
        total = len(scenes)
        with_scripts = sum(1 for s in scenes if s.has_scripts)
        
        axis_coverage = {}
        for s in scenes:
            for axis in s.scripts:
                axis_coverage[axis] = axis_coverage.get(axis, 0) + 1
        
        performer_stats = {}
        for s in scenes:
            for p in s.performers:
                if p not in performer_stats:
                    performer_stats[p] = {"total": 0, "scripted": 0}
                performer_stats[p]["total"] += 1
                if s.has_scripts:
                    performer_stats[p]["scripted"] += 1
        
        report = {
            "total_scenes": total,
            "scenes_with_scripts": with_scripts,
            "coverage_pct": f"{with_scripts/total*100:.1f}%" if total else "0%",
            "axis_coverage": dict(sorted(
                axis_coverage.items(),
                key=lambda x: x[1], reverse=True)),
            "top_performers": dict(sorted(
                performer_stats.items(),
                key=lambda x: x[1]["scripted"], reverse=True)[:10]),
        }
        
        logger.info(
            f"媒体库分析: {total}场景, {with_scripts}有脚本 "
            f"({report['coverage_pct']})")
        return report
    
    # ── 内部 ──
    
    def _get_stash(self):
        """获取或创建Stash客户端"""
        if self._stash is None:
            from .stash_client import StashClient
            self._stash = StashClient(
                host=self.config.stash_host,
                port=self.config.stash_port,
                api_key=self.config.stash_api_key,
            )
        return self._stash
    
    def _get_xbvr(self):
        """获取或创建XBVR客户端"""
        if self._xbvr is None:
            from .xbvr_client import XBVRClient
            self._xbvr = XBVRClient(
                host=self.config.xbvr_host,
                port=self.config.xbvr_port,
            )
        return self._xbvr
    
    def _get_player(self):
        """获取或创建FunscriptPlayer"""
        if self._player is None:
            from funscript.player import FunscriptPlayer, SafetyConfig
            
            safety = SafetyConfig(
                max_speed=self.config.max_speed,
                position_min=self.config.position_min,
                position_max=self.config.position_max,
            )
            
            self._player = FunscriptPlayer(
                port=self.config.device_port,
                wifi_host=self.config.device_wifi,
                wifi_port=self.config.device_wifi_port,
                update_hz=self.config.update_hz,
                safety=safety,
            )
        return self._player
    
    # ── URL→设备 全链路 ──
    
    def url_to_funscript(self, url: str,
                          output_dir: str = None) -> dict:
        """URL→下载→节拍分析→生成funscript (不播放)
        
        全链路: 抖音/TikTok/YouTube URL → 下载视频 → 提取音频
                → librosa节拍检测 → 生成.funscript文件
        
        Args:
            url: 视频URL (支持抖音/TikTok/YouTube/Bilibili等)
            output_dir: 输出目录 (默认用config.download_dir)
            
        Returns:
            {'video': 视频路径, 'audio': 音频路径,
             'funscripts': {轴: 路径}, 'info': FetchResult,
             'analysis': 音频分析结果}
        """
        out = output_dir or self.config.download_dir
        
        # Step 1: 下载视频+提取音频
        fetcher = self._get_fetcher()
        logger.info(f"[1/3] 下载视频: {url}")
        fetch_result = fetcher.fetch(url)
        if not fetch_result.ok:
            logger.error(f"下载失败: {fetch_result.error}")
            return {'error': fetch_result.error}
        
        if not fetch_result.has_audio:
            logger.error("无法提取音频")
            return {'error': '音频提取失败', 'video': fetch_result.video_path}
        
        # Step 2: 节拍分析
        syncer = self._get_syncer()
        logger.info(f"[2/3] 分析音频: {fetch_result.audio_path}")
        analysis = syncer.analyze_audio(fetch_result.audio_path)
        
        # Step 3: 生成funscript
        logger.info(f"[3/3] 生成funscript (BPM={analysis['tempo']:.0f})")
        from pathlib import Path
        base_name = Path(fetch_result.video_path).stem
        
        funscript_paths = {}
        if self.config.multi_axis_beat:
            multi = syncer.generate_multi(fetch_result.audio_path)
            multi.save_all(out, base_name)
            for axis, r in multi.results.items():
                from .beat_sync import AXIS_SUFFIX
                suffix = AXIS_SUFFIX.get(axis, f'.{axis.lower()}')
                funscript_paths[axis] = str(
                    Path(out) / f"{base_name}{suffix}.funscript"
                )
        else:
            result = syncer.generate(fetch_result.audio_path)
            fs_path = str(Path(out) / f"{base_name}.funscript")
            result.save(fs_path)
            funscript_paths['L0'] = fs_path
        
        logger.info(f"全链路完成: {len(funscript_paths)}轴 funscript")
        return {
            'video': fetch_result.video_path,
            'audio': fetch_result.audio_path,
            'funscripts': funscript_paths,
            'info': fetch_result,
            'analysis': analysis,
        }
    
    def url_to_device(self, url: str,
                      output_dir: str = None) -> dict:
        """URL→下载→节拍→funscript→设备播放 (一键全链路)
        
        Args:
            url: 视频URL
            output_dir: 输出目录
            
        Returns:
            同url_to_funscript, 额外包含 'playing': True/False
        """
        chain = self.url_to_funscript(url, output_dir)
        if 'error' in chain:
            return chain
        
        # Step 4: 加载funscript并播放
        try:
            scene = SceneInfo(
                title=chain['info'].title,
                video_path=chain['video'],
                duration_sec=chain['info'].duration,
                scripts=chain['funscripts'],
                source=chain['info'].platform,
            )
            self.play_scene(scene)
            chain['playing'] = True
            logger.info(f"设备播放中: {scene.title}")
        except Exception as e:
            chain['playing'] = False
            chain['play_error'] = str(e)
            logger.error(f"设备播放失败: {e}")
        
        return chain
    
    def _get_fetcher(self):
        """获取或创建VideoFetcher"""
        if self._fetcher is None:
            from .video_fetcher import VideoFetcher, FetcherConfig
            self._fetcher = VideoFetcher(FetcherConfig(
                output_dir=self.config.download_dir,
                proxy=self.config.proxy,
                max_resolution=self.config.max_resolution,
                extract_audio=True,
                audio_format='wav',
            ))
        return self._fetcher
    
    def _get_syncer(self):
        """获取或创建BeatSyncer"""
        if self._syncer is None:
            from .beat_sync import BeatSyncer, BeatSyncConfig
            self._syncer = BeatSyncer(BeatSyncConfig(
                mode=self.config.beat_mode,
                beat_divisor=self.config.beat_divisor,
                intensity_curve=self.config.intensity_curve,
                multi_axis=self.config.multi_axis_beat,
            ))
        return self._syncer
    
    def close(self):
        """释放所有资源"""
        self.stop()
        if self._player:
            self._player.disconnect()
            self._player = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
