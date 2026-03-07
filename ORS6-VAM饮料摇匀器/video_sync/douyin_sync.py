"""
抖音浏览器实时同步 — 用户浏览抖音网页时自动同步OSR6设备

架构:
  Chrome DevTools (CDP) ← 监控抖音页面
    → 检测视频切换 (URL变化 / video元素变化)
    → 提取视频信息 (分享URL / CDN地址 / 视频元数据)
    → yt-dlp下载音频 / 或直接从CDN获取
    → librosa节拍分析 → funscript生成
    → 实时同步设备 (跟随视频播放进度)

用法:
    # 方式1: 作为独立守护程序运行
    sync = DouyinSync(device_port="COM3")
    sync.start()  # 开始监控浏览器
    
    # 方式2: 单视频同步
    sync = DouyinSync()
    result = sync.sync_current_video()  # 同步当前播放的视频
    
    # 方式3: 从CDP页面快照提取
    sync = DouyinSync()
    info = sync.extract_video_info(page_snapshot)
"""

import os
import re
import json
import time
import logging
import hashlib
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


# ── 抖音页面JS注入脚本 ──

# 获取当前视频信息的JS (注入到抖音页面)
JS_GET_VIDEO_INFO = """
() => {
    // 找到当前播放的video元素
    const videos = document.querySelectorAll('video');
    let activeVideo = null;
    for (const v of videos) {
        if (!v.paused && v.readyState >= 2) {
            activeVideo = v;
            break;
        }
    }
    if (!activeVideo && videos.length > 0) {
        activeVideo = videos[0];
    }
    if (!activeVideo) return null;
    
    // 获取视频源URL (可能是blob)
    const src = activeVideo.src || activeVideo.currentSrc || '';
    
    // 获取播放状态
    const state = {
        src: src,
        currentTime: activeVideo.currentTime,
        duration: activeVideo.duration,
        paused: activeVideo.paused,
        volume: activeVideo.volume,
        width: activeVideo.videoWidth,
        height: activeVideo.videoHeight,
        playbackRate: activeVideo.playbackRate,
    };
    
    // 尝试获取分享URL (抖音特有)
    const shareBtn = document.querySelector('[data-e2e="video-share"]');
    const url = window.location.href;
    
    // 尝试获取视频描述/标题
    const descEl = document.querySelector('[data-e2e="video-desc"]') 
        || document.querySelector('.video-info-detail');
    const desc = descEl ? descEl.textContent.trim() : '';
    
    // 尝试获取作者
    const authorEl = document.querySelector('[data-e2e="video-author-name"]')
        || document.querySelector('.author-card-user-name');
    const author = authorEl ? authorEl.textContent.trim() : '';
    
    state.pageUrl = url;
    state.description = desc.substring(0, 200);
    state.author = author;
    
    return state;
}
"""

# 监控视频切换的JS (返回视频变化事件)
JS_WATCH_VIDEO_CHANGE = """
() => {
    // 检查是否已经安装了observer
    if (window._osr6_observer) return { status: 'already_watching' };
    
    window._osr6_lastSrc = '';
    window._osr6_events = [];
    
    const observer = new MutationObserver((mutations) => {
        const videos = document.querySelectorAll('video');
        for (const v of videos) {
            const src = v.src || v.currentSrc || '';
            if (src && src !== window._osr6_lastSrc) {
                window._osr6_lastSrc = src;
                window._osr6_events.push({
                    type: 'video_change',
                    src: src,
                    time: Date.now(),
                    url: window.location.href,
                });
            }
        }
    });
    
    observer.observe(document.body, {
        childList: true, subtree: true, attributes: true,
        attributeFilter: ['src']
    });
    
    window._osr6_observer = observer;
    return { status: 'watching' };
}
"""

# 获取并清空事件队列
JS_GET_EVENTS = """
() => {
    const events = window._osr6_events || [];
    window._osr6_events = [];
    return events;
}
"""

# 获取当前播放进度
JS_GET_PLAYBACK = """
() => {
    const videos = document.querySelectorAll('video');
    for (const v of videos) {
        if (!v.paused && v.readyState >= 2) {
            return {
                currentTime: v.currentTime,
                duration: v.duration,
                paused: v.paused,
                playbackRate: v.playbackRate,
            };
        }
    }
    return null;
}
"""

# 从网络请求中提取视频CDN URL的模式
DOUYIN_CDN_PATTERNS = [
    r'https?://v\d+-[a-z]+\.douyinvod\.com/[^\s"]+',
    r'https?://[a-z0-9-]+\.bytedance\.com/[^\s"]+\.mp4[^\s"]*',
    r'https?://[a-z0-9-]+\.tiktokcdn\.com/[^\s"]+',
    r'https?://[a-z0-9-]+\.musical\.ly/[^\s"]+',
]


@dataclass
class VideoState:
    """当前视频状态"""
    page_url: str = ""
    video_src: str = ""
    current_time: float = 0.0
    duration: float = 0.0
    paused: bool = True
    description: str = ""
    author: str = ""
    width: int = 0
    height: int = 0
    
    # 处理状态
    video_id: str = ""
    funscript_path: str = ""
    synced: bool = False
    
    @property
    def is_douyin(self) -> bool:
        return 'douyin.com' in self.page_url
    
    @property 
    def share_url(self) -> str:
        """从页面URL提取分享URL"""
        if 'douyin.com/video/' in self.page_url:
            return self.page_url.split('?')[0]
        return self.page_url
    
    def content_hash(self) -> str:
        """内容哈希,用于检测视频是否变化"""
        key = f"{self.page_url}:{self.video_src}:{self.duration:.1f}"
        return hashlib.md5(key.encode()).hexdigest()[:12]


@dataclass
class SyncConfig:
    """同步配置"""
    # 设备
    device_port: Optional[str] = None
    device_wifi: Optional[str] = None
    
    # 下载
    download_dir: str = "douyin_cache"
    proxy: str = ""
    
    # 节拍同步
    beat_mode: str = "beat"
    beat_divisor: int = 1
    intensity_curve: str = "sine"
    multi_axis: bool = False
    
    # 行为
    auto_sync: bool = True          # 自动同步新视频
    cache_funscripts: bool = True   # 缓存已生成的funscript
    poll_interval: float = 1.0      # 轮询间隔(秒)
    min_duration: float = 3.0       # 最短视频时长(秒)


class DouyinSync:
    """抖音浏览器实时同步器
    
    通过Chrome DevTools协议(CDP)监控抖音网页,
    自动检测视频切换,生成funscript并同步到OSR6设备。
    """
    
    def __init__(self, config: SyncConfig = None, **kwargs):
        self.config = config or SyncConfig(**kwargs)
        self._current_video: Optional[VideoState] = None
        self._cache: dict[str, str] = {}  # hash → funscript_path
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._syncer = None
        self._fetcher = None
        self._player = None
        
        os.makedirs(self.config.download_dir, exist_ok=True)
        self._load_cache()
    
    def extract_video_info_from_snapshot(self, snapshot_text: str) -> Optional[VideoState]:
        """从Chrome DevTools快照文本提取视频信息
        
        解析take_snapshot返回的a11y树,找到视频相关元素
        """
        state = VideoState()
        
        # 从快照找video元素
        if 'video' in snapshot_text.lower():
            state.video_src = "detected_from_snapshot"
        
        # 找URL (从快照中的地址栏或链接)
        url_match = re.search(r'https?://www\.douyin\.com/\S+', snapshot_text)
        if url_match:
            state.page_url = url_match.group(0)
        
        return state if state.page_url else None
    
    def extract_video_from_js_result(self, js_result: dict) -> Optional[VideoState]:
        """从JS_GET_VIDEO_INFO的返回结果构建VideoState"""
        if not js_result:
            return None
        
        state = VideoState(
            page_url=js_result.get('pageUrl', ''),
            video_src=js_result.get('src', ''),
            current_time=js_result.get('currentTime', 0),
            duration=js_result.get('duration', 0),
            paused=js_result.get('paused', True),
            description=js_result.get('description', ''),
            author=js_result.get('author', ''),
            width=js_result.get('width', 0),
            height=js_result.get('height', 0),
        )
        
        # 生成video_id
        if state.page_url:
            vid_match = re.search(r'/video/(\d+)', state.page_url)
            if vid_match:
                state.video_id = vid_match.group(1)
        
        return state
    
    def extract_cdn_url_from_requests(self, requests_text: str) -> Optional[str]:
        """从网络请求列表中提取视频CDN URL"""
        for pattern in DOUYIN_CDN_PATTERNS:
            match = re.search(pattern, requests_text)
            if match:
                return match.group(0)
        return None
    
    def process_video(self, state: VideoState) -> dict:
        """处理单个视频: 下载→分析→生成funscript
        
        Args:
            state: 视频状态信息
            
        Returns:
            {'funscript': 路径, 'analysis': 分析结果, ...}
        """
        content_hash = state.content_hash()
        
        # 检查缓存
        if self.config.cache_funscripts and content_hash in self._cache:
            cached_path = self._cache[content_hash]
            if os.path.exists(cached_path):
                logger.info(f"命中缓存: {cached_path}")
                state.funscript_path = cached_path
                state.synced = True
                return {'funscript': cached_path, 'cached': True}
        
        # 确定下载URL
        download_url = state.share_url or state.page_url
        if not download_url:
            return {'error': '无法获取视频URL'}
        
        logger.info(f"处理视频: {state.description[:50] or state.video_id or download_url}")
        
        # 使用pipeline处理
        from .pipeline import SyncPipeline, SyncConfig as PipeConfig
        pipe = SyncPipeline(PipeConfig(
            download_dir=self.config.download_dir,
            proxy=self.config.proxy,
            beat_mode=self.config.beat_mode,
            beat_divisor=self.config.beat_divisor,
            intensity_curve=self.config.intensity_curve,
            multi_axis_beat=self.config.multi_axis,
        ))
        
        result = pipe.url_to_funscript(download_url)
        
        if 'error' not in result:
            fs_paths = result.get('funscripts', {})
            if fs_paths:
                main_path = list(fs_paths.values())[0]
                state.funscript_path = main_path
                state.synced = True
                
                # 缓存
                if self.config.cache_funscripts:
                    self._cache[content_hash] = main_path
                    self._save_cache()
                
                result['cached'] = False
        
        return result
    
    def get_js_scripts(self) -> dict:
        """获取所有需要注入的JS脚本
        
        用于在Chrome DevTools MCP中手动执行:
        1. 先执行 get_video_info 获取当前视频
        2. 再执行 watch_changes 安装视频切换监控
        3. 定期执行 get_events 获取切换事件
        4. 执行 get_playback 获取实时播放进度
        """
        return {
            'get_video_info': JS_GET_VIDEO_INFO,
            'watch_changes': JS_WATCH_VIDEO_CHANGE,
            'get_events': JS_GET_EVENTS,
            'get_playback': JS_GET_PLAYBACK,
        }
    
    def format_sync_status(self, state: VideoState, result: dict) -> str:
        """格式化同步状态输出"""
        lines = []
        lines.append(f"{'='*50}")
        lines.append(f"视频: {state.description[:60] or '未知'}")
        lines.append(f"作者: {state.author or '未知'}")
        lines.append(f"时长: {state.duration:.1f}s")
        lines.append(f"URL:  {state.share_url}")
        
        if 'error' in result:
            lines.append(f"状态: ❌ {result['error']}")
        elif result.get('cached'):
            lines.append(f"状态: ⚡ 命中缓存")
            lines.append(f"脚本: {state.funscript_path}")
        else:
            analysis = result.get('analysis', {})
            tempo = analysis.get('tempo', 0)
            beats = analysis.get('beat_count', 0)
            lines.append(f"状态: ✅ 同步完成")
            lines.append(f"BPM:  {tempo:.0f} ({beats}拍)")
            fs = result.get('funscripts', {})
            for axis, path in fs.items():
                lines.append(f"脚本: [{axis}] {Path(path).name}")
        
        lines.append(f"{'='*50}")
        return '\n'.join(lines)
    
    # ── 缓存管理 ──
    
    def _load_cache(self):
        """加载funscript缓存索引"""
        cache_file = Path(self.config.download_dir) / '.sync_cache.json'
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}
    
    def _save_cache(self):
        """保存缓存索引"""
        cache_file = Path(self.config.download_dir) / '.sync_cache.json'
        try:
            with open(cache_file, 'w') as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            logger.warning(f"缓存保存失败: {e}")
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._save_cache()
    
    def __repr__(self):
        return (f"DouyinSync(auto={self.config.auto_sync}, "
                f"cache={len(self._cache)})")
