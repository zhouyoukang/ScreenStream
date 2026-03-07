"""Navigate Chrome to a specific Douyin video page and check if video loads"""
import asyncio, json, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname).1s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("cdp")

INJECT_JS = (Path(__file__).parent / "douyin_cache" / "inject_hip_sync.js").read_text(encoding="utf-8")

# Get video URLs from jingxuan page, then navigate to first one
async def main():
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        log.info(f"CDP connected, {len(browser.contexts)} contexts")
        
        ctx = browser.contexts[0]
        pages = ctx.pages
        douyin = None
        for pg in pages:
            if "douyin.com" in pg.url:
                douyin = pg
                break
        
        if not douyin:
            log.error("No Douyin page found")
            return
        
        log.info(f"Douyin page: {douyin.url[:80]}")
        
        # Extract video URLs from current page
        urls = await douyin.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="/video/"]');
            return Array.from(links).slice(0, 10).map(a => a.href);
        }""")
        log.info(f"Found {len(urls)} video links")
        for u in urls[:5]:
            log.info(f"  {u}")
        
        if not urls:
            log.error("No video links found on page")
            return
        
        # Navigate to first video URL
        target_url = urls[0]
        log.info(f"Navigating to: {target_url}")
        await douyin.goto(target_url, wait_until="domcontentloaded", timeout=20000)
        await douyin.wait_for_timeout(3000)
        
        # Remove popups
        await douyin.evaluate("""() => {
            ['[id*="login"]','[class*="login"]','[class*="Login"]','[class*="modal"]',
             '[class*="mask"]','[class*="dialog"]','[class*="guide"]'].forEach(sel => {
                document.querySelectorAll(sel).forEach(el => {
                    if (el.offsetHeight > 50 && !el.querySelector('video')) el.remove();
                });
            });
            document.body.style.overflow = 'auto';
        }""")
        
        # Wait for video with detailed status
        log.info("Waiting for video to load...")
        for i in range(20):
            info = await douyin.evaluate("""() => {
                const vids = document.querySelectorAll('video');
                return Array.from(vids).map(v => ({
                    w: v.videoWidth, h: v.videoHeight,
                    rs: v.readyState, paused: v.paused,
                    src: (v.src || '').substring(0, 100),
                    csrc: (v.currentSrc || '').substring(0, 100),
                    srcCount: v.querySelectorAll('source').length,
                    networkState: v.networkState,
                    error: v.error ? v.error.message : null,
                }));
            }""")
            for vi, v in enumerate(info):
                playing = v['rs'] >= 2 and not v['paused'] and v['w'] > 0
                log.info(f"  [{i+1}s] video[{vi}]: {v['w']}x{v['h']} rs={v['rs']} net={v['networkState']} " +
                         f"{'PLAYING' if playing else 'paused' if v['paused'] else 'loading'} " +
                         f"src={v['src'][:50] if v['src'] else 'none'}")
                if playing:
                    log.info(f"  >>> VIDEO PLAYING! {v['w']}x{v['h']}")
                    # Inject hip sync!
                    log.info("Injecting Hip Sync script...")
                    await douyin.evaluate(INJECT_JS)
                    log.info("Script injected! Monitoring...")
                    
                    # Monitor
                    for t in range(120):
                        await douyin.wait_for_timeout(5000)
                        try:
                            status = await douyin.evaluate(
                                '() => document.getElementById("__hip_sync_hud")?.innerText || "N/A"')
                            log.info(f"[{t*5}s] {status.replace(chr(10),' ')[:100]}")
                        except Exception:
                            break
                    return
            
            # Try to play paused videos
            await douyin.evaluate("""() => {
                document.querySelectorAll('video').forEach(v => {
                    if (v.paused) v.play().catch(()=>{});
                });
            }""")
            await douyin.wait_for_timeout(1000)
        
        log.warning("Video never started playing")
        # Log page HTML structure for debugging
        structure = await douyin.evaluate("""() => {
            const body = document.body;
            const videos = document.querySelectorAll('video');
            const xgPlayers = document.querySelectorAll('[class*="xgplayer"], [class*="player"]');
            return {
                videoCount: videos.length,
                playerDivs: xgPlayers.length,
                bodyClassList: body.className.substring(0, 100),
                title: document.title,
            };
        }""")
        log.info(f"Page structure: {json.dumps(structure, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())
