"""
抖音Playwright实时同步Agent — 浏览器自动化 + OSR6设备同步

架构:
  Playwright (Chromium) → 打开抖音页面
    → JS注入监控视频切换/播放进度
    → 检测新视频 → yt-dlp下载 → librosa节拍分析 → funscript生成
    → FunscriptPlayer实时同步设备 (跟随视频播放进度)

全链路:
  抖音网页 → Playwright监控 → 视频URL → yt-dlp下载
  → 音频提取 → 节拍检测 → funscript生成 → TCode → OSR6设备

用法:
    # 方式1: 异步上下文管理器
    async with DouyinPlaywrightAgent(device_port="COM5") as agent:
        await agent.run()

    # 方式2: 命令行
    python -m video_sync.douyin_playwright_agent --port COM5

    # 方式3: 手动控制
    agent = DouyinPlaywrightAgent(device_port="COM5")
    await agent.start()
    # ... 用户浏览抖音 ...
    await agent.stop()
"""

import asyncio
import logging
import time
import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Playwright抖音同步Agent配置"""
    # 设备连接
    device_port: Optional[str] = None
    device_wifi: Optional[str] = None
    device_wifi_port: int = 8000

    # 浏览器
    headless: bool = False
    user_data_dir: str = ""  # 空=临时目录, 设置路径=持久登录
    proxy: str = ""
    stealth: bool = True  # 反检测

    # 下载与生成
    download_dir: str = "douyin_cache"
    beat_mode: str = "onset"  # onset对短视频效果更好
    beat_divisor: int = 1
    intensity_curve: str = "sine"
    multi_axis: bool = True  # 6轴同步

    # 同步行为
    auto_sync: bool = True
    poll_interval: float = 0.5  # 播放进度轮询(秒)
    process_cooldown: float = 2.0  # 新视频处理冷却(秒)
    min_duration: float = 5.0  # 最短视频时长(秒)
    cache_funscripts: bool = True
    sync_playback: bool = True  # 实时跟随视频播放进度
    loop_sync: bool = True  # 视频循环时重新同步

    # 安全
    max_speed: int = 15000
    position_min: int = 0
    position_max: int = 9999
    update_hz: int = 60

    # 回调
    on_video_change: Optional[Callable] = field(default=None, repr=False)
    on_sync_complete: Optional[Callable] = field(default=None, repr=False)
    on_error: Optional[Callable] = field(default=None, repr=False)


# ── 抖音页面JS注入脚本 ──

JS_INIT_MONITOR = """
() => {
    if (window._osr6_ready) return { status: 'already_initialized' };

    window._osr6_ready = true;
    window._osr6_lastSrc = '';
    window._osr6_lastUrl = '';
    window._osr6_events = [];

    // MutationObserver: 检测视频元素变化
    const observer = new MutationObserver(() => {
        const videos = document.querySelectorAll('video');
        for (const v of videos) {
            const src = v.src || v.currentSrc || '';
            const url = window.location.href;
            if ((src && src !== window._osr6_lastSrc) ||
                (url !== window._osr6_lastUrl && url.includes('/video/'))) {
                window._osr6_lastSrc = src;
                window._osr6_lastUrl = url;
                window._osr6_events.push({
                    type: 'video_change',
                    src: src,
                    url: url,
                    time: Date.now(),
                });
            }
        }
    });

    observer.observe(document.body, {
        childList: true, subtree: true, attributes: true,
        attributeFilter: ['src', 'currentSrc']
    });

    // URL变化监控 (抖音SPA路由)
    let lastHref = window.location.href;
    const urlCheck = setInterval(() => {
        if (window.location.href !== lastHref) {
            lastHref = window.location.href;
            if (lastHref.includes('/video/')) {
                window._osr6_events.push({
                    type: 'url_change',
                    url: lastHref,
                    time: Date.now(),
                });
            }
        }
    }, 300);

    window._osr6_observer = observer;
    window._osr6_urlCheck = urlCheck;
    return { status: 'initialized' };
}
"""

JS_GET_STATE = """
() => {
    const videos = document.querySelectorAll('video');
    let active = null;
    // 优先选未暂停且有时长的
    for (const v of videos) {
        if (!v.paused && v.duration > 0 && v.readyState >= 2) {
            active = v;
            break;
        }
    }
    // 退而选有时长的
    if (!active) {
        for (const v of videos) {
            if (v.duration > 0 && v.readyState >= 2) {
                active = v;
                break;
            }
        }
    }
    if (!active) return null;

    // 视频描述
    const descEl = document.querySelector('[data-e2e="video-desc"]')
        || document.querySelector('.video-info-detail')
        || document.querySelector('.video-desc');
    const desc = descEl ? descEl.textContent.trim().substring(0, 200) : '';

    // 作者
    const authorEl = document.querySelector('[data-e2e="video-author-name"]')
        || document.querySelector('.author-card-user-name')
        || document.querySelector('[class*="author"] [class*="name"]');
    const author = authorEl ? authorEl.textContent.trim() : '';

    return {
        src: active.src || active.currentSrc || '',
        currentTime: active.currentTime,
        duration: active.duration,
        paused: active.paused,
        ended: active.ended,
        loop: active.loop,
        playbackRate: active.playbackRate,
        volume: active.volume,
        width: active.videoWidth,
        height: active.videoHeight,
        pageUrl: window.location.href,
        description: desc,
        author: author,
        readyState: active.readyState,
    };
}
"""

JS_POLL_EVENTS = """
() => {
    const events = window._osr6_events || [];
    window._osr6_events = [];
    return events;
}
"""

JS_GET_PLAYBACK = """
() => {
    const videos = document.querySelectorAll('video');
    for (const v of videos) {
        if (v.duration > 0 && v.readyState >= 2) {
            return {
                t: v.currentTime,
                d: v.duration,
                p: v.paused,
                e: v.ended,
                r: v.playbackRate,
            };
        }
    }
    return null;
}
"""


class DouyinPlaywrightAgent:
    """Playwright抖音实时同步Agent

    负责:
    1. 启动Chromium浏览器,导航到抖音
    2. 注入JS监控视频切换和播放进度
    3. 视频切换时自动: 下载→节拍分析→funscript生成
    4. 实时同步: 跟随视频播放进度驱动设备
    """

    def __init__(self, config: AgentConfig = None, **kwargs):
        self.config = config or AgentConfig(**kwargs)
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._running = False
        self._processing_lock = asyncio.Lock()

        # 同步状态
        self._current_hash: Optional[str] = None
        self._current_state: Optional[dict] = None
        self._funscript_paths: dict[str, str] = {}
        self._last_process_time: float = 0

        # 管道组件 (延迟初始化)
        self._pipeline = None
        self._player = None
        self._device_ok = False

        # 缓存
        self._cache: dict[str, dict] = {}  # hash → {funscripts, ...}
        self._cache_file = Path(self.config.download_dir) / '.agent_cache.json'
        os.makedirs(self.config.download_dir, exist_ok=True)
        self._load_cache()

        # 统计
        self._stats = {
            'videos_processed': 0,
            'cache_hits': 0,
            'errors': 0,
            'start_time': 0,
        }

    # ── 生命周期 ──

    async def start(self, url: str = "https://www.douyin.com"):
        """启动Agent: 打开浏览器 → 导航抖音 → 开始监控"""
        self._running = True
        self._stats['start_time'] = time.time()

        # 1. 启动Playwright浏览器
        await self._launch_browser()

        # 2. 导航到抖音
        logger.info(f"导航到: {url}")
        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)  # 等待SPA渲染

        # 3. 注入监控JS
        await self._inject_monitor()

        # 4. 连接设备
        self._init_device()

        logger.info("═" * 50)
        logger.info("  抖音同步Agent已启动")
        logger.info(f"  设备: {'✅ ' + (self.config.device_port or self.config.device_wifi or '未配置') if self._device_ok else '❌ 未连接'}")
        logger.info(f"  模式: {'多轴' if self.config.multi_axis else '单轴'} | {self.config.beat_mode} | {self.config.intensity_curve}")
        logger.info(f"  缓存: {len(self._cache)}条")
        logger.info("═" * 50)

    async def run(self, url: str = "https://www.douyin.com"):
        """启动并持续运行监控循环"""
        await self.start(url)
        await self._monitor_loop()

    async def stop(self):
        """停止Agent并释放资源"""
        self._running = False
        logger.info("正在停止Agent...")

        # 停止设备播放
        if self._player:
            try:
                self._player.stop()
                self._player.disconnect()
            except Exception:
                pass
            self._player = None

        # 关闭管道
        if self._pipeline:
            try:
                self._pipeline.close()
            except Exception:
                pass
            self._pipeline = None

        # 关闭浏览器
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass

        self._save_cache()

        elapsed = time.time() - self._stats['start_time'] if self._stats['start_time'] else 0
        logger.info("═" * 50)
        logger.info("  Agent已停止")
        logger.info(f"  运行时间: {elapsed/60:.1f}分钟")
        logger.info(f"  处理视频: {self._stats['videos_processed']}个")
        logger.info(f"  缓存命中: {self._stats['cache_hits']}次")
        logger.info(f"  错误: {self._stats['errors']}次")
        logger.info("═" * 50)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.stop()

    # ── 浏览器管理 ──

    async def _launch_browser(self):
        """启动Playwright Chromium"""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()

        launch_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-infobars',
            '--no-first-run',
        ]
        if self.config.proxy:
            launch_args.append(f'--proxy-server={self.config.proxy}')

        if self.config.user_data_dir:
            # 持久上下文: 保留登录状态和cookies
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=self.config.user_data_dir,
                headless=self.config.headless,
                args=launch_args,
                viewport={'width': 1280, 'height': 800},
                locale='zh-CN',
                timezone_id='Asia/Shanghai',
            )
            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        else:
            # 临时上下文
            self._browser = await self._playwright.chromium.launch(
                headless=self.config.headless,
                args=launch_args,
            )
            self._context = await self._browser.new_context(
                viewport={'width': 1280, 'height': 800},
                locale='zh-CN',
                timezone_id='Asia/Shanghai',
            )
            self._page = await self._context.new_page()

        # 反检测: 覆盖navigator.webdriver
        if self.config.stealth:
            await self._page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
                window.chrome = { runtime: {} };
            """)

        logger.info(f"浏览器已启动 (headless={self.config.headless})")

    async def _inject_monitor(self):
        """注入视频监控脚本"""
        try:
            result = await self._page.evaluate(JS_INIT_MONITOR)
            logger.info(f"监控脚本注入: {result.get('status', 'unknown') if result else 'no_result'}")
        except Exception as e:
            logger.warning(f"监控脚本注入失败(非致命): {e}")

    # ── 设备管理 ──

    def _init_device(self):
        """初始化设备连接"""
        if not self.config.device_port and not self.config.device_wifi:
            logger.warning("未配置设备端口, 将只生成funscript不播放")
            self._device_ok = False
            return

        try:
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
            # FunscriptPlayer在play()时才真正connect, 这里先标记可用
            self._device_ok = True
            logger.info(f"设备已配置: {self.config.device_port or self.config.device_wifi}")
        except Exception as e:
            self._device_ok = False
            logger.error(f"设备初始化失败: {e}")

    # ── 监控循环 ──

    async def _monitor_loop(self):
        """主监控循环: 检测视频变化 + 同步播放进度"""
        logger.info("监控循环启动")
        reinject_counter = 0

        while self._running:
            try:
                # 1. 检查JS事件队列 (视频切换)
                events = await self._safe_evaluate(JS_POLL_EVENTS)
                if events and isinstance(events, list):
                    for ev in events:
                        logger.info(f"事件: {ev.get('type')} → {ev.get('url', '')[:60]}")
                    # 有视频变化事件, 获取状态并处理
                    state = await self._safe_evaluate(JS_GET_STATE)
                    if state and state.get('duration', 0) > 0:
                        video_hash = self._compute_hash(state)
                        self._current_hash = video_hash
                        self._current_state = state
                        await self._on_video_change(state)
                    await asyncio.sleep(self.config.poll_interval)
                    continue  # 跳过下面的状态轮询,避免重复JS调用

                # 2. 获取当前视频状态
                state = await self._safe_evaluate(JS_GET_STATE)
                if state and state.get('duration', 0) > 0:
                    video_hash = self._compute_hash(state)

                    if video_hash != self._current_hash:
                        # 新视频 (可能是通过滑动切换, 未触发MutationObserver)
                        logger.info(f"视频切换(hash): {state.get('description', '')[:40]} "
                                    f"[{state['duration']:.1f}s]")
                        self._current_hash = video_hash
                        self._current_state = state
                        await self._on_video_change(state)
                    elif self.config.sync_playback and self._player_active():
                        # 同步播放进度
                        await self._sync_playback(state)
                else:
                    # 无有效视频
                    if self._player_active():
                        self._player.stop()
                        logger.info("无有效视频, 停止播放")
                    self._current_hash = None
                    self._current_state = None

                # 3. 定期重注入 (抖音SPA可能重建DOM)
                reinject_counter += 1
                if reinject_counter >= int(30 / self.config.poll_interval):  # ~30秒
                    reinject_counter = 0
                    await self._safe_evaluate(JS_INIT_MONITOR)

            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                self._stats['errors'] += 1
                await asyncio.sleep(2)
                # 尝试重注入
                try:
                    await self._inject_monitor()
                except Exception:
                    pass

            await asyncio.sleep(self.config.poll_interval)

        logger.info("监控循环结束")

    async def _on_video_change(self, state: dict = None):
        """处理视频切换事件"""
        # 冷却检查
        now = time.time()
        if now - self._last_process_time < self.config.process_cooldown:
            return
        self._last_process_time = now

        # 获取当前视频完整状态 (优先用传入的, 避免重复JS调用)
        if not state:
            state = await self._safe_evaluate(JS_GET_STATE)
        if not state:
            logger.warning("无法获取视频状态")
            return

        duration = state.get('duration', 0)
        if duration < self.config.min_duration:
            logger.info(f"视频太短({duration:.1f}s), 跳过")
            return

        # 停止当前播放
        if self._player_active():
            self._player.stop()

        self._current_state = state
        video_hash = self._compute_hash(state)
        self._current_hash = video_hash

        desc = state.get('description', '')[:40] or state.get('pageUrl', '')[:40]
        logger.info(f"处理新视频: {desc} [{duration:.1f}s]")

        # 回调
        if self.config.on_video_change:
            try:
                self.config.on_video_change(state)
            except Exception:
                pass

        if not self.config.auto_sync:
            return

        # 检查缓存
        if self.config.cache_funscripts and video_hash in self._cache:
            cached = self._cache[video_hash]
            fs_paths = cached.get('funscripts', {})
            # 验证文件存在
            if all(os.path.exists(p) for p in fs_paths.values()):
                logger.info(f"⚡ 缓存命中: {len(fs_paths)}轴")
                self._stats['cache_hits'] += 1
                self._funscript_paths = fs_paths
                self._start_playback()
                return
            else:
                del self._cache[video_hash]

        # 全链路处理 (异步, 不阻塞监控循环, 用锁防止并发)
        task = asyncio.create_task(self._process_video_guarded(state, video_hash))
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task):
        """异步任务完成回调 — 捕获火忘task的异常"""
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error(f"后台任务异常: {exc}")
            self._stats['errors'] += 1
            if self.config.on_error:
                try:
                    self.config.on_error(str(exc))
                except Exception:
                    pass

    async def _process_video_guarded(self, state: dict, video_hash: str):
        """带锁的视频处理, 防止并发竞争"""
        if self._processing_lock.locked():
            logger.info("已有视频在处理中, 跳过")
            return
        async with self._processing_lock:
            await self._process_video(state, video_hash)

    async def _process_video(self, state: dict, video_hash: str):
        """处理视频全链路: 下载→分析→生成funscript→播放"""
        url = state.get('pageUrl', '')
        if not url or 'douyin.com' not in url:
            logger.warning(f"非抖音URL, 跳过: {url[:60]}")
            return

        # 从抖音URL提取分享URL
        share_url = url.split('?')[0] if '/video/' in url else url

        try:
            # 使用SyncPipeline全链路处理
            pipeline = self._get_pipeline()
            logger.info(f"[1/3] 开始下载: {share_url[:60]}")

            # 导出Playwright cookies给yt-dlp使用
            await self._export_cookies()

            # 在线程池中运行同步操作 (下载+分析+生成)
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, pipeline.url_to_funscript, share_url
            )

            if 'error' in result:
                logger.error(f"处理失败: {result['error']}")
                self._stats['errors'] += 1
                if self.config.on_error:
                    self.config.on_error(result['error'])
                return

            fs_paths = result.get('funscripts', {})
            if not fs_paths:
                logger.error("未生成funscript")
                self._stats['errors'] += 1
                return

            self._funscript_paths = fs_paths
            self._stats['videos_processed'] += 1

            # 缓存
            if self.config.cache_funscripts:
                self._cache[video_hash] = {
                    'funscripts': fs_paths,
                    'url': share_url,
                    'description': state.get('description', ''),
                    'duration': state.get('duration', 0),
                    'time': time.time(),
                }
                self._save_cache()

            # 分析结果
            analysis = result.get('analysis', {})
            tempo = analysis.get('tempo', 0)
            logger.info(f"✅ 生成完成: {len(fs_paths)}轴, BPM={tempo:.0f}")

            # 检查是否还是同一个视频
            if self._current_hash == video_hash:
                self._start_playback()
            else:
                logger.info("视频已切换, 不播放此funscript")

            if self.config.on_sync_complete:
                try:
                    self.config.on_sync_complete(result)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"处理异常: {e}")
            self._stats['errors'] += 1
            if self.config.on_error:
                try:
                    self.config.on_error(str(e))
                except Exception:
                    pass

    def _start_playback(self):
        """加载funscript并开始设备播放"""
        if not self._device_ok or not self._player:
            logger.info(f"Funscript已就绪({len(self._funscript_paths)}轴), 设备未连接")
            return

        if not self._funscript_paths:
            return

        try:
            # 停止当前播放
            if self._player_active():
                self._player.stop()

            # 清空已加载脚本, 重新加载
            self._player.clear_scripts()

            for axis, path in self._funscript_paths.items():
                try:
                    self._player.load_single(path, axis)
                except Exception as e:
                    logger.warning(f"加载脚本失败 [{axis}]: {e}")

            if self._player.has_scripts:
                # 同步到当前视频播放位置
                if self._current_state:
                    current_time = self._current_state.get('currentTime', 0)
                    if current_time > 0.5:
                        self._player.seek(current_time)

                self._player.play()
                logger.info(f"▶ 设备播放中: {list(self._funscript_paths.keys())}")
            else:
                logger.error("无可用funscript脚本")

        except Exception as e:
            logger.error(f"播放启动失败: {e}")
            self._stats['errors'] += 1

    async def _sync_playback(self, state: dict):
        """同步设备播放进度到视频当前时间"""
        if not self._player or not self._player.is_playing:
            return

        video_time = state.get('currentTime', 0)
        video_paused = state.get('paused', False)
        video_ended = state.get('ended', False)

        if video_paused and not self._player.is_paused:
            self._player.pause()
            logger.debug("同步暂停")
            return

        if not video_paused and self._player.is_paused:
            self._player.play()  # play()内部处理resume逻辑
            logger.debug("同步恢复")

        # 同步播放速率
        video_rate = state.get('playbackRate', 1.0)
        if abs(self._player.speed - video_rate) > 0.05:
            self._player.speed = video_rate
            logger.debug(f"同步播放速率: {video_rate}x")

        if video_ended:
            if self.config.loop_sync:
                # 视频循环播放, 重置到开头
                self._player.seek(0)
            else:
                self._player.stop()
            return

        # 检查漂移, 超过0.5秒则纠正
        player_time = self._player.current_time_sec
        drift = abs(video_time - player_time)
        if drift > 0.5:
            self._player.seek(video_time)
            logger.debug(f"同步纠正: 漂移{drift:.2f}s → seek({video_time:.1f}s)")

    # ── 辅助方法 ──

    def _player_active(self) -> bool:
        """检查播放器是否活跃"""
        return bool(self._player and self._player.is_playing)

    def _compute_hash(self, state: dict) -> str:
        """计算视频内容哈希 (含src防止feed页同时长视频冲突)"""
        import hashlib
        url = state.get('pageUrl', '')
        src = state.get('src', '')
        dur = state.get('duration', 0)
        key = f"{url}:{src}:{dur:.1f}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    async def _safe_evaluate(self, js: str):
        """安全执行JS, 捕获异常"""
        try:
            return await self._page.evaluate(js)
        except Exception as e:
            logger.debug(f"JS执行失败: {e}")
            return None

    async def _export_cookies(self):
        """导出Playwright cookies为Netscape格式, 供yt-dlp使用"""
        try:
            cookies = await self._context.cookies()
            if not cookies:
                return

            cookie_file = Path(self.config.download_dir) / '.cookies.txt'
            lines = ["# Netscape HTTP Cookie File\n"]
            for c in cookies:
                domain = c.get('domain', '')
                flag = "TRUE" if domain.startswith('.') else "FALSE"
                path = c.get('path', '/')
                secure = "TRUE" if c.get('secure', False) else "FALSE"
                expires = str(int(c.get('expires', 0)))
                name = c.get('name', '')
                value = c.get('value', '')
                lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")

            cookie_file.write_text(''.join(lines), encoding='utf-8')

            # 设置yt-dlp cookie文件路径到pipeline的fetcher
            pipeline = self._get_pipeline()
            fetcher = pipeline._get_fetcher()
            if hasattr(fetcher, '_config'):
                fetcher._config.cookies_file = str(cookie_file)
            elif hasattr(fetcher, 'config'):
                fetcher.config.cookies_file = str(cookie_file)

            logger.debug(f"导出{len(cookies)}个cookies → {cookie_file}")
        except Exception as e:
            logger.debug(f"Cookie导出失败(非致命): {e}")

    def _get_pipeline(self):
        """获取或创建SyncPipeline"""
        if self._pipeline is None:
            from .pipeline import SyncPipeline, SyncConfig as PipeConfig
            self._pipeline = SyncPipeline(PipeConfig(
                download_dir=self.config.download_dir,
                proxy=self.config.proxy,
                beat_mode=self.config.beat_mode,
                beat_divisor=self.config.beat_divisor,
                intensity_curve=self.config.intensity_curve,
                multi_axis_beat=self.config.multi_axis,
                device_port=self.config.device_port,
                device_wifi=self.config.device_wifi,
                device_wifi_port=self.config.device_wifi_port,
                update_hz=self.config.update_hz,
                max_speed=self.config.max_speed,
                position_min=self.config.position_min,
                position_max=self.config.position_max,
            ))
        return self._pipeline

    # ── 缓存 ──

    def _load_cache(self):
        if self._cache_file.exists():
            try:
                with open(self._cache_file) as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}

    def _save_cache(self):
        try:
            with open(self._cache_file, 'w') as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"缓存保存失败: {e}")

    def clear_cache(self):
        self._cache.clear()
        self._save_cache()
        logger.info("缓存已清空")

    # ── 状态查询 ──

    @property
    def status(self) -> dict:
        """当前Agent状态"""
        return {
            'running': self._running,
            'device_connected': self._device_ok,
            'current_video': {
                'hash': self._current_hash,
                'description': (self._current_state or {}).get('description', ''),
                'duration': (self._current_state or {}).get('duration', 0),
                'url': (self._current_state or {}).get('pageUrl', ''),
            } if self._current_state else None,
            'playing': self._player_active(),
            'funscript_axes': list(self._funscript_paths.keys()),
            'stats': self._stats.copy(),
            'cache_size': len(self._cache),
        }

    def format_status(self) -> str:
        """格式化状态输出"""
        s = self.status
        lines = ["═" * 50]
        lines.append(f"  Agent: {'🟢 运行中' if s['running'] else '🔴 已停止'}")
        lines.append(f"  设备:  {'✅ 已连接' if s['device_connected'] else '❌ 未连接'}")

        if s['current_video']:
            v = s['current_video']
            lines.append(f"  视频:  {v['description'][:40] or v['url'][:40]}")
            lines.append(f"  时长:  {v['duration']:.1f}s")

        if s['playing']:
            lines.append(f"  播放:  ▶ {', '.join(s['funscript_axes'])}")
        else:
            lines.append(f"  播放:  ⏸ 未播放")

        st = s['stats']
        lines.append(f"  统计:  处理{st['videos_processed']}个 缓存命中{st['cache_hits']}次 错误{st['errors']}次")
        lines.append("═" * 50)
        return '\n'.join(lines)


# ── CLI入口 ──

def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description='抖音视频 × OSR6设备 实时同步Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 串口连接
  python -m video_sync.douyin_playwright_agent --port COM5

  # WiFi连接
  python -m video_sync.douyin_playwright_agent --wifi 192.168.1.100

  # 自定义参数
  python -m video_sync.douyin_playwright_agent --port COM5 --multi-axis --beat onset

  # 仅生成funscript (无设备)
  python -m video_sync.douyin_playwright_agent --no-device

  # 持久登录 (保留cookies)
  python -m video_sync.douyin_playwright_agent --port COM5 --user-data ./douyin_profile
        """,
    )
    parser.add_argument('--port', help='串口端口 (如 COM5)')
    parser.add_argument('--wifi', help='WiFi设备IP')
    parser.add_argument('--wifi-port', type=int, default=8000, help='WiFi端口 (默认8000)')
    parser.add_argument('--no-device', action='store_true', help='不连接设备,仅生成funscript')
    parser.add_argument('--headless', action='store_true', help='无头模式')
    parser.add_argument('--user-data', default='', help='浏览器用户数据目录 (持久登录)')
    parser.add_argument('--proxy', default='', help='代理 (如 http://127.0.0.1:7890)')
    parser.add_argument('--beat', default='onset', choices=['beat', 'onset', 'hybrid'], help='节拍模式')
    parser.add_argument('--multi-axis', action='store_true', default=True, help='多轴模式 (默认开启)')
    parser.add_argument('--single-axis', action='store_true', help='单轴模式')
    parser.add_argument('--curve', default='sine', choices=['linear', 'sine', 'bounce', 'saw'], help='强度曲线')
    parser.add_argument('--cache-dir', default='douyin_cache', help='缓存目录')
    parser.add_argument('--url', default='https://www.douyin.com', help='起始URL')
    parser.add_argument('--poll', type=float, default=0.5, help='轮询间隔(秒)')
    parser.add_argument('--min-duration', type=float, default=5.0, help='最短视频时长(秒)')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细日志')

    args = parser.parse_args()

    # 日志
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname).1s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )

    config = AgentConfig(
        device_port=args.port if not args.no_device else None,
        device_wifi=args.wifi if not args.no_device else None,
        device_wifi_port=args.wifi_port,
        headless=args.headless,
        user_data_dir=args.user_data,
        proxy=args.proxy,
        download_dir=args.cache_dir,
        beat_mode=args.beat,
        multi_axis=not args.single_axis,
        intensity_curve=args.curve,
        poll_interval=args.poll,
        min_duration=args.min_duration,
    )

    async def run():
        async with DouyinPlaywrightAgent(config=config) as agent:
            await agent.run(url=args.url)

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("用户中断, 正在退出...")


if __name__ == "__main__":
    main()
