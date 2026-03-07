"""视频同步模块 — 连接视频播放器、媒体管理器和AI脚本生成器

子模块按需延迟导入，避免可选依赖(librosa/yt-dlp/playwright/websockets)
未安装时阻止整个模块加载。
"""

# 始终安全的导入 (仅依赖stdlib)
from .funscript_naming import FunscriptNaming, FunscriptFile, AXIS_SUFFIX_MAP
from .douyin_sync import DouyinSync, VideoState
from .douyin_sync import SyncConfig as DouyinSyncConfig

# 延迟导入映射: name → (module, attr)
_LAZY_IMPORTS = {
    "MultiFunPlayerClient": (".mfp_client", "MultiFunPlayerClient"),
    "MFPConfig": (".mfp_client", "MFPConfig"),
    "PlaybackState": (".mfp_client", "PlaybackState"),
    "AxisState": (".mfp_client", "AxisState"),
    "DeoVRMonitor": (".mfp_client", "DeoVRMonitor"),
    "HereSphereMonitor": (".mfp_client", "HereSphereMonitor"),
    "StashClient": (".stash_client", "StashClient"),
    "StashScene": (".stash_client", "StashScene"),
    "MotionTracker": (".motion_tracker", "MotionTracker"),
    "TrackerConfig": (".motion_tracker", "TrackerConfig"),
    "TCodeFrame": (".motion_tracker", "TCodeFrame"),
    "SyncPipeline": (".pipeline", "SyncPipeline"),
    "SyncConfig": (".pipeline", "SyncConfig"),
    "SceneInfo": (".pipeline", "SceneInfo"),
    "FunscriptAnalyzer": (".funscript_analyzer", "FunscriptAnalyzer"),
    "AnalysisReport": (".funscript_analyzer", "AnalysisReport"),
    "XBVRClient": (".xbvr_client", "XBVRClient"),
    "XBVRScene": (".xbvr_client", "XBVRScene"),
    "XBVRFile": (".xbvr_client", "XBVRFile"),
    "BeatSyncer": (".beat_sync", "BeatSyncer"),
    "BeatSyncConfig": (".beat_sync", "BeatSyncConfig"),
    "SyncResult": (".beat_sync", "SyncResult"),
    "MultiSyncResult": (".beat_sync", "MultiSyncResult"),
    "VideoFetcher": (".video_fetcher", "VideoFetcher"),
    "FetcherConfig": (".video_fetcher", "FetcherConfig"),
    "FetchResult": (".video_fetcher", "FetchResult"),
    "DouyinPlaywrightAgent": (".douyin_playwright_agent", "DouyinPlaywrightAgent"),
    "AgentConfig": (".douyin_playwright_agent", "AgentConfig"),
}


def __getattr__(name):
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        import importlib
        mod = importlib.import_module(module_path, __package__)
        return getattr(mod, attr)
    raise AttributeError(f"module 'video_sync' has no attribute {name!r}")


__all__ = [
    "FunscriptNaming", "FunscriptFile", "AXIS_SUFFIX_MAP",
    "DouyinSync", "VideoState", "DouyinSyncConfig",
    *_LAZY_IMPORTS.keys(),
]
