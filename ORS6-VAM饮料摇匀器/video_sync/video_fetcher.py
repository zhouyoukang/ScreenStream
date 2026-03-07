"""
视频获取器 — 从抖音/TikTok/YouTube等平台下载视频并提取音频

基于yt-dlp实现,支持:
- 抖音/TikTok短视频下载
- YouTube/Bilibili等主流平台
- 自动提取音频(WAV/MP3)用于节拍分析
- 视频元数据获取(标题/时长/封面)
- 下载进度回调

用法:
    fetcher = VideoFetcher(output_dir="downloads/")
    
    # 下载视频+提取音频
    result = fetcher.fetch("https://v.douyin.com/xxxxx")
    print(result.title, result.video_path, result.audio_path)
    
    # 仅获取信息不下载
    info = fetcher.get_info("https://v.douyin.com/xxxxx")
    print(info['title'], info['duration'])
    
    # 批量下载
    results = fetcher.fetch_batch([url1, url2, url3])
"""

import os
import json
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """下载结果"""
    url: str = ""
    title: str = ""
    video_path: str = ""
    audio_path: str = ""
    duration: float = 0.0
    thumbnail: str = ""
    uploader: str = ""
    platform: str = ""
    video_id: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    filesize: int = 0
    metadata: dict = field(default_factory=dict)
    error: str = ""
    
    @property
    def ok(self) -> bool:
        return bool(self.video_path) and not self.error
    
    @property
    def has_audio(self) -> bool:
        return bool(self.audio_path) and os.path.exists(self.audio_path)
    
    def summary(self) -> str:
        status = "✓" if self.ok else "✗"
        dur = f"{self.duration:.0f}s" if self.duration else "?"
        res = f"{self.width}x{self.height}" if self.width else ""
        return f"[{status}] {self.title} ({dur}) {res} @{self.platform}"


@dataclass
class FetcherConfig:
    """获取器配置"""
    output_dir: str = "downloads"
    extract_audio: bool = True
    audio_format: str = "wav"        # wav最适合librosa分析
    audio_quality: str = "192"       # kbps
    video_format: str = "best"       # best/worst/bestvideo+bestaudio
    max_resolution: Optional[int] = None  # 限制最大分辨率 (如720)
    proxy: str = ""                  # 代理 (如 http://127.0.0.1:7890)
    cookies_file: str = ""           # cookies文件路径
    download_thumbnail: bool = True
    quiet: bool = True
    max_filesize: str = ""           # 最大文件大小 (如 500M)
    rate_limit: str = ""             # 限速 (如 1M)
    
    # 抖音/TikTok特殊配置
    douyin_watermark: bool = False   # 是否保留水印


class VideoFetcher:
    """视频获取器 — 基于yt-dlp的多平台视频下载+音频提取
    
    支持平台: 抖音/TikTok/YouTube/Bilibili/Twitter/Instagram等1000+站点
    """
    
    # 平台识别
    PLATFORM_MAP = {
        "douyin": ["douyin.com", "v.douyin.com", "iesdouyin.com"],
        "tiktok": ["tiktok.com", "vm.tiktok.com"],
        "youtube": ["youtube.com", "youtu.be"],
        "bilibili": ["bilibili.com", "b23.tv"],
        "twitter": ["twitter.com", "x.com"],
        "instagram": ["instagram.com"],
        "pornhub": ["pornhub.com"],
        "xvideos": ["xvideos.com"],
        "xhamster": ["xhamster.com"],
    }
    
    def __init__(self, config: FetcherConfig = None,
                 output_dir: str = None):
        self.config = config or FetcherConfig()
        if output_dir:
            self.config.output_dir = output_dir
        
        self._ensure_yt_dlp()
        os.makedirs(self.config.output_dir, exist_ok=True)
    
    def _ensure_yt_dlp(self):
        """检查yt-dlp是否可用"""
        try:
            import yt_dlp
            self._yt_dlp = yt_dlp
        except ImportError:
            raise ImportError(
                "yt-dlp未安装。请运行: pip install yt-dlp"
            )
    
    def detect_platform(self, url: str) -> str:
        """检测URL所属平台"""
        url_lower = url.lower()
        for platform, domains in self.PLATFORM_MAP.items():
            for domain in domains:
                if domain in url_lower:
                    return platform
        return "unknown"
    
    def get_info(self, url: str) -> dict:
        """获取视频元数据(不下载)
        
        Args:
            url: 视频URL
            
        Returns:
            包含title/duration/uploader等的字典
        """
        opts = self._base_opts()
        opts['skip_download'] = True
        
        with self._yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                return ydl.sanitize_info(info)
            except Exception as e:
                logger.error(f"获取信息失败: {url} — {e}")
                return {"error": str(e)}
    
    def fetch(self, url: str, 
              on_progress: Optional[Callable] = None) -> FetchResult:
        """下载视频并提取音频
        
        Args:
            url: 视频URL (抖音/TikTok/YouTube等)
            on_progress: 进度回调 fn(downloaded_bytes, total_bytes, speed)
            
        Returns:
            FetchResult包含视频/音频路径和元数据
        """
        result = FetchResult(url=url)
        result.platform = self.detect_platform(url)
        
        logger.info(f"开始获取: {url} (平台: {result.platform})")
        
        try:
            # Step 1: 下载视频
            opts = self._build_download_opts(on_progress)
            
            with self._yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info is None:
                    result.error = "无法获取视频信息"
                    return result
                
                info = ydl.sanitize_info(info)
                
                # 填充元数据
                result.title = info.get('title', '')
                result.duration = info.get('duration', 0) or 0
                result.uploader = info.get('uploader', '')
                result.video_id = info.get('id', '')
                result.width = info.get('width', 0) or 0
                result.height = info.get('height', 0) or 0
                result.fps = info.get('fps', 0) or 0
                result.filesize = info.get('filesize', 0) or 0
                result.thumbnail = info.get('thumbnail', '')
                result.metadata = {
                    k: info.get(k) for k in 
                    ['view_count', 'like_count', 'comment_count',
                     'upload_date', 'description', 'tags']
                    if info.get(k) is not None
                }
                
                # 找到下载的视频文件
                result.video_path = self._find_downloaded_file(info, opts)
                
            # Step 2: 提取音频 (如果配置了)
            if self.config.extract_audio and result.video_path:
                result.audio_path = self._extract_audio(result.video_path)
            
            logger.info(f"获取完成: {result.summary()}")
            
        except Exception as e:
            result.error = str(e)
            logger.error(f"获取失败: {url} — {e}")
        
        return result
    
    def fetch_batch(self, urls: list[str],
                    on_each: Optional[Callable] = None) -> list[FetchResult]:
        """批量下载视频
        
        Args:
            urls: URL列表
            on_each: 每个完成后的回调 fn(index, result)
            
        Returns:
            FetchResult列表
        """
        results = []
        for i, url in enumerate(urls):
            result = self.fetch(url)
            results.append(result)
            if on_each:
                on_each(i, result)
            # 防止请求过快
            if i < len(urls) - 1:
                time.sleep(1.0)
        
        ok = sum(1 for r in results if r.ok)
        logger.info(f"批量完成: {ok}/{len(urls)} 成功")
        return results
    
    def fetch_audio_only(self, url: str) -> FetchResult:
        """仅下载音频(不下载视频,更快)
        
        Args:
            url: 视频URL
            
        Returns:
            FetchResult (video_path为空, audio_path有值)
        """
        result = FetchResult(url=url)
        result.platform = self.detect_platform(url)
        
        opts = self._base_opts()
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': self.config.audio_format,
            'preferredquality': self.config.audio_quality,
        }]
        opts['outtmpl'] = str(
            Path(self.config.output_dir) / '%(title)s.%(ext)s'
        )
        
        try:
            with self._yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    info = ydl.sanitize_info(info)
                    result.title = info.get('title', '')
                    result.duration = info.get('duration', 0) or 0
                    result.uploader = info.get('uploader', '')
                    result.video_id = info.get('id', '')
                    
                    # 找音频文件
                    base = Path(self.config.output_dir)
                    title = info.get('title', result.video_id)
                    # 清理文件名
                    safe_title = self._safe_filename(title)
                    audio_ext = self.config.audio_format
                    candidates = list(base.glob(f"*{safe_title}*.{audio_ext}"))
                    if not candidates:
                        candidates = list(base.glob(f"*.{audio_ext}"))
                    if candidates:
                        result.audio_path = str(
                            max(candidates, key=lambda p: p.stat().st_mtime)
                        )
        except Exception as e:
            result.error = str(e)
            logger.error(f"音频获取失败: {url} — {e}")
        
        return result
    
    # ── 内部方法 ──
    
    def _base_opts(self) -> dict:
        """基础yt-dlp选项"""
        opts = {
            'quiet': self.config.quiet,
            'no_warnings': self.config.quiet,
            'ignoreerrors': False,
            'nocheckcertificate': True,
        }
        
        if self.config.proxy:
            opts['proxy'] = self.config.proxy
        if self.config.cookies_file:
            opts['cookiefile'] = self.config.cookies_file
        if self.config.rate_limit:
            opts['ratelimit'] = self.config.rate_limit
        
        return opts
    
    def _build_download_opts(self, 
                              on_progress: Optional[Callable] = None) -> dict:
        """构建下载选项"""
        opts = self._base_opts()
        
        # 输出模板
        opts['outtmpl'] = str(
            Path(self.config.output_dir) / '%(title)s.%(ext)s'
        )
        
        # 视频格式
        if self.config.max_resolution:
            opts['format'] = (
                f'bestvideo[height<={self.config.max_resolution}]'
                f'+bestaudio/best[height<={self.config.max_resolution}]'
                f'/best'
            )
        else:
            opts['format'] = self.config.video_format
        
        # 缩略图
        if self.config.download_thumbnail:
            opts['writethumbnail'] = True
        
        # 文件大小限制
        if self.config.max_filesize:
            opts['max_filesize'] = self._parse_size(self.config.max_filesize)
        
        # 进度回调
        if on_progress:
            def _hook(d):
                if d['status'] == 'downloading':
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes') or d.get(
                        'total_bytes_estimate', 0)
                    speed = d.get('speed', 0)
                    on_progress(downloaded, total, speed)
            opts['progress_hooks'] = [_hook]
        
        return opts
    
    def _find_downloaded_file(self, info: dict, opts: dict) -> str:
        """从yt-dlp info中找到下载的文件路径"""
        # 方法1: 从requested_downloads获取
        downloads = info.get('requested_downloads', [])
        if downloads:
            filepath = downloads[0].get('filepath', '')
            if filepath and os.path.exists(filepath):
                return filepath
        
        # 方法2: 从outtmpl推算
        title = info.get('title', info.get('id', 'video'))
        ext = info.get('ext', 'mp4')
        safe_title = self._safe_filename(title)
        
        base = Path(self.config.output_dir)
        # 尝试精确匹配
        exact = base / f"{safe_title}.{ext}"
        if exact.exists():
            return str(exact)
        
        # 模糊匹配 (取最新的视频文件)
        video_exts = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv']
        candidates = []
        for vext in video_exts:
            candidates.extend(base.glob(f"*{vext}"))
        
        if candidates:
            newest = max(candidates, key=lambda p: p.stat().st_mtime)
            return str(newest)
        
        return ""
    
    def _extract_audio(self, video_path: str) -> str:
        """从视频提取音频
        
        优先用yt-dlp/ffmpeg, 回退用soundfile
        """
        vp = Path(video_path)
        audio_path = vp.with_suffix(f'.{self.config.audio_format}')
        
        if audio_path.exists():
            return str(audio_path)
        
        # 用ffmpeg提取
        try:
            import subprocess
            cmd = [
                'ffmpeg', '-i', str(vp),
                '-vn',  # 无视频
                '-acodec', 'pcm_s16le' if self.config.audio_format == 'wav'
                    else 'libmp3lame',
                '-ar', '22050',  # librosa默认采样率
                '-ac', '1',     # 单声道 (节省空间,分析够用)
                '-y',           # 覆盖
                str(audio_path)
            ]
            subprocess.run(
                cmd, capture_output=True, timeout=120,
                check=True
            )
            if audio_path.exists():
                logger.info(f"音频提取: {audio_path.name}")
                return str(audio_path)
        except FileNotFoundError:
            logger.warning("ffmpeg未找到, 尝试librosa加载...")
        except Exception as e:
            logger.warning(f"ffmpeg提取失败: {e}")
        
        # 回退: 直接用librosa加载视频文件 (如果有soundfile)
        try:
            import librosa
            import soundfile as sf
            y, sr = librosa.load(str(vp), sr=22050, mono=True)
            sf.write(str(audio_path), y, sr)
            logger.info(f"音频提取(librosa): {audio_path.name}")
            return str(audio_path)
        except Exception as e:
            logger.warning(f"librosa回退也失败: {e}")
        
        return ""
    
    @staticmethod
    def _safe_filename(name: str) -> str:
        """将文件名中的不安全字符替换"""
        unsafe = '<>:"/\\|?*'
        for c in unsafe:
            name = name.replace(c, '_')
        return name.strip()
    
    @staticmethod
    def _parse_size(size_str: str) -> int:
        """解析大小字符串 (如 '500M' → 524288000)"""
        size_str = size_str.strip().upper()
        multipliers = {'K': 1024, 'M': 1024**2, 'G': 1024**3}
        for suffix, mult in multipliers.items():
            if size_str.endswith(suffix):
                return int(float(size_str[:-1]) * mult)
        return int(size_str)
    
    def __repr__(self):
        return f"VideoFetcher(output={self.config.output_dir})"
