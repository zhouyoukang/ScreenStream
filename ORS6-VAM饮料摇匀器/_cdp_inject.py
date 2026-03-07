"""Connect to user's Chrome via CDP, navigate Douyin, inject hip sync tracking"""
import asyncio, json, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname).1s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("cdp")

INJECT_SCRIPT = (Path(__file__).parent / "douyin_cache" / "inject_hip_sync.js").read_text(encoding="utf-8")


async def main():
    from playwright.async_api import async_playwright
    
    log.info("连接到 Chrome CDP (localhost:9222)...")
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        log.info(f"已连接! {len(browser.contexts)} 个context")
        
        # Find the Douyin page
        douyin_page = None
        for ctx in browser.contexts:
            for page in ctx.pages:
                log.info(f"  Page: {page.url[:80]}")
                if "douyin.com" in page.url:
                    douyin_page = page
        
        if not douyin_page:
            log.error("未找到抖音页面")
            return
        
        log.info(f"找到抖音页面: {douyin_page.url[:80]}")
        
        # Remove login popups
        log.info("清除弹窗...")
        for _ in range(3):
            removed = await douyin_page.evaluate("""() => {
                let c = 0;
                ['[id*="login"]','[class*="login"]','[class*="Login"]','[class*="modal"]',
                 '[class*="Modal"]','[class*="mask"]','[class*="dialog"]','[class*="guide"]'
                ].forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => {
                        if (el.offsetHeight > 50 && !el.querySelector('video')) { el.remove(); c++; }
                    });
                });
                document.querySelectorAll('div').forEach(el => {
                    const s = getComputedStyle(el);
                    if ((s.position==='fixed'||s.position==='absolute') && parseInt(s.zIndex)>100 &&
                        el.offsetWidth>400 && el.offsetHeight>200 && !el.querySelector('video')) {
                        el.remove(); c++;
                    }
                });
                document.body.style.overflow = 'auto';
                return c;
            }""")
            if removed == 0:
                break
            log.info(f"  移除 {removed} 个弹窗元素")
            await douyin_page.wait_for_timeout(500)
        
        # Strategy: click a video card on /jingxuan to open player
        log.info("寻找视频卡片...")
        clicked = await douyin_page.evaluate("""() => {
            // Find video links on jingxuan page
            const links = document.querySelectorAll('a[href*="/video/"]');
            if (links.length > 0) {
                // Click the first video link
                links[0].click();
                return {ok: true, href: links[0].href, count: links.length};
            }
            // Try clicking any large image/poster that might be a video card
            const imgs = document.querySelectorAll('img[src*="douyin"], img[src*="tiktok"]');
            for (const img of imgs) {
                if (img.offsetWidth > 100 && img.offsetHeight > 100) {
                    img.click();
                    return {ok: true, alt: 'image click', count: imgs.length};
                }
            }
            return {ok: false, links: links.length};
        }""")
        log.info(f"点击结果: {json.dumps(clicked, ensure_ascii=False)}")
        
        if clicked.get('ok'):
            log.info("等待视频页面加载...")
            await douyin_page.wait_for_timeout(5000)
            # Remove popups again on new page
            await douyin_page.evaluate("""() => {
                ['[id*="login"]','[class*="login"]','[class*="modal"]','[class*="mask"]',
                 '[class*="dialog"]','[class*="guide"]'].forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => {
                        if (el.offsetHeight > 50 && !el.querySelector('video')) el.remove();
                    });
                });
            }""")
        else:
            # Fallback: try navigating to recommend feed
            log.info("无视频卡片，尝试推荐页...")
            await douyin_page.goto("https://www.douyin.com/recommend", 
                                   wait_until="domcontentloaded", timeout=15000)
            await douyin_page.wait_for_timeout(5000)
        
        # Wait for video to start playing
        log.info("等待视频播放...")
        playing = []
        for i in range(25):
            info = await douyin_page.evaluate("""() => {
                const vids = document.querySelectorAll('video');
                const list = [];
                for (const v of vids) {
                    list.push({w: v.videoWidth, h: v.videoHeight, rs: v.readyState, p: v.paused,
                        src: (v.src||v.currentSrc||'').substring(0,80)});
                    if (v.paused && v.readyState >= 1) v.play().catch(()=>{});
                }
                return list;
            }""")
            playing = [v for v in info if v['rs'] >= 2 and not v['p'] and v['w'] > 0]
            has_src = [v for v in info if v['src'] and len(v['src']) > 10]
            log.info(f"  [{i+1}s] {len(info)}个video, {len(has_src)}有src, {len(playing)}播放中" + 
                     (f" → {playing[0]['w']}x{playing[0]['h']}" if playing else ""))
            if playing:
                break
            await douyin_page.wait_for_timeout(1000)
        
        if not playing:
            log.warning("视频未播放。可能需要手动在Chrome中点击视频。注入仍继续...")
        
        # Inject hip sync script
        log.info("注入 Hip Sync 追踪脚本...")
        await douyin_page.evaluate(INJECT_SCRIPT)
        log.info("脚本已注入! 等待 MoveNet 加载...")
        
        # Monitor status
        log.info("同步运行中... 按 Ctrl+C 停止")
        try:
            for tick in range(600):  # 50 min max
                await douyin_page.wait_for_timeout(5000)
                try:
                    status = await douyin_page.evaluate(
                        '() => document.getElementById("__hip_sync_hud")?.innerText || "N/A"')
                    status_short = status.replace('\n', ' | ')[:100]
                    log.info(f"[{tick*5}s] {status_short}")
                except Exception:
                    log.warning("页面可能已关闭")
                    break
        except KeyboardInterrupt:
            log.info("用户中断")
        
        # Don't close browser - it's user's Chrome
        log.info("完成 (Chrome保持打开)")


if __name__ == "__main__":
    asyncio.run(main())
