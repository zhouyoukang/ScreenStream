"""
CDP Watcher: monitors Chrome for video playback, auto-injects hip sync when detected.

Usage:
  1. Chrome is already open with CDP on port 9222 and Douyin loaded
  2. Run this script
  3. In Chrome, manually click on a dancing video
  4. Script auto-detects playback and injects MoveNet hip tracking → ORS6 sync
"""
import asyncio, json, logging, sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname).1s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("watcher")

INJECT_JS = (Path(__file__).parent / "douyin_cache" / "inject_hip_sync.js").read_text(encoding="utf-8")


async def main():
    from playwright.async_api import async_playwright

    log.info("连接 Chrome CDP:9222...")
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        ctx = browser.contexts[0]
        log.info(f"已连接 ({len(ctx.pages)} pages)")

        injected_urls = set()

        log.info("=" * 50)
        log.info("请在 Chrome 中点击一个跳舞视频!")
        log.info("脚本会自动检测视频播放并注入臀部追踪")
        log.info("=" * 50)

        for tick in range(300):  # 25 min
            await asyncio.sleep(2)

            # Scan all pages for playing videos
            for page in ctx.pages:
                url = page.url
                if "douyin.com" not in url:
                    continue
                if url in injected_urls:
                    # Already injected on this page, just monitor
                    try:
                        status = await page.evaluate(
                            '() => document.getElementById("__hip_sync_hud")?.innerText || ""',
                        )
                        if status:
                            if tick % 5 == 0:  # Log every 10s
                                log.info(f"[同步中] {status.replace(chr(10), ' | ')[:100]}")
                    except Exception:
                        injected_urls.discard(url)
                    continue

                # Check for playing video on this page
                try:
                    result = await page.evaluate("""() => {
                        const vids = document.querySelectorAll('video');
                        let best = null;
                        for (const v of vids) {
                            if (v.readyState >= 2 && v.videoWidth > 0) {
                                if (!v.paused) {
                                    return {playing: true, w: v.videoWidth, h: v.videoHeight,
                                            src: (v.src||v.currentSrc||'').substring(0,60)};
                                }
                                if (!best) best = v;
                            }
                        }
                        // Try to play any ready video
                        if (best) {
                            best.play().catch(()=>{});
                            return {playing: false, ready: true, w: best.videoWidth, h: best.videoHeight};
                        }
                        return {playing: false, ready: false, count: vids.length};
                    }""")
                except Exception:
                    continue

                if result.get("playing"):
                    log.info(f"检测到视频播放! {result['w']}x{result['h']} on {url[:60]}")

                    # Remove popups first
                    try:
                        await page.evaluate("""() => {
                            ['[id*="login"]','[class*="login"]','[class*="Login"]',
                             '[class*="modal"]','[class*="mask"]','[class*="dialog"]',
                             '[class*="guide"]'].forEach(sel => {
                                document.querySelectorAll(sel).forEach(el => {
                                    if (el.offsetHeight > 50 && !el.querySelector('video')) el.remove();
                                });
                            });
                        }""")
                    except Exception:
                        pass

                    # Inject hip sync
                    log.info("注入 Hip Sync + MoveNet 追踪...")
                    try:
                        await page.evaluate(INJECT_JS)
                        injected_urls.add(url)
                        log.info("注入成功! MoveNet加载中(约5-10秒)...")
                        log.info("臀部骨骼叠加层 + ORS6 TCode 指令即将启动")
                    except Exception as e:
                        log.error(f"注入失败: {e}")
                elif result.get("ready"):
                    if tick % 10 == 0:
                        log.info(f"视频就绪但暂停 ({result['w']}x{result['h']}), 尝试播放...")
                else:
                    if tick % 15 == 0 and result.get("count", 0) > 0:
                        log.info(f"页面有 {result['count']} 个video元素但未就绪, 等待用户操作...")

        log.info("监听超时, 退出")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("用户中断")
