"""
Hip Sync × Douyin × ORS6 — End-to-End Pipeline
Uses Playwright to open Douyin, inject TF.js MoveNet pose estimation,
and sync hip movement to ORS6 Hub via WebSocket in real-time.

Usage:
  python _hip_sync_douyin.py                    # Open Douyin feed
  python _hip_sync_douyin.py --local dance.mp4  # Use local video file
  python _hip_sync_douyin.py --hip-sync-page    # Open hip_sync.html with test video
"""
import asyncio, json, sys, time, argparse, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname).1s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("hip_sync")

PROJECT_ROOT = Path(__file__).parent
HUB_URL = "http://localhost:8086"
HUB_WS = "ws://localhost:8086"

# ── TF.js MoveNet Injection Script ──
# This script is injected into the browser page and runs pose estimation
# on the video element, tracking hip keypoints and sending TCode to ORS6 Hub.
INJECT_SCRIPT = """
(async () => {
  const HUB_WS_URL = '__HUB_WS__';
  const log = (msg) => console.log('[HipSync]', msg);
  
  // 1. Find video element
  let video = null;
  for (let i = 0; i < 10; i++) {
    const videos = document.querySelectorAll('video');
    video = Array.from(videos).find(v => v.readyState >= 2 && v.videoWidth > 0) || videos[0];
    if (video && video.readyState >= 2) break;
    log('Waiting for video... (' + (i+1) + '/10)');
    await new Promise(r => setTimeout(r, 1000));
  }
  if (!video || video.readyState < 2) { log('ERROR: No video found'); return; }
  log('Video found: ' + video.videoWidth + 'x' + video.videoHeight);
  
  // 2. Load TF.js + Pose Detection
  const loadJS = (src) => new Promise((res, rej) => {
    if (document.querySelector('script[src="' + src + '"]')) { res(); return; }
    const s = document.createElement('script');
    s.src = src; s.onload = res; s.onerror = () => rej(new Error('Load failed: ' + src));
    document.head.appendChild(s);
  });
  
  log('Loading TF.js...');
  await loadJS('https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.17.0/dist/tf.min.js');
  log('Loading Pose Detection...');
  await loadJS('https://cdn.jsdelivr.net/npm/@tensorflow-models/pose-detection@2.1.3/dist/pose-detection.min.js');
  
  // 3. Create MoveNet detector
  log('Creating MoveNet detector...');
  const detector = await poseDetection.createDetector(
    poseDetection.SupportedModels.MoveNet,
    { modelType: poseDetection.movenet.modelType.SINGLEPOSE_LIGHTNING }
  );
  log('MoveNet ready!');
  
  // 4. Connect to ORS6 Hub
  let ws = null;
  let wsOk = false;
  function connectWS() {
    ws = new WebSocket(HUB_WS_URL);
    ws.onopen = () => { wsOk = true; log('ORS6 Hub connected'); };
    ws.onclose = () => { wsOk = false; log('ORS6 Hub disconnected, reconnecting...'); setTimeout(connectWS, 2000); };
    ws.onerror = () => {};
  }
  connectWS();
  
  // 5. Create overlay canvas
  const canvas = document.createElement('canvas');
  canvas.id = '__hip_sync_overlay';
  canvas.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:99999;';
  // Find video container and position relative
  let container = video.parentElement;
  if (container) {
    container.style.position = 'relative';
    container.appendChild(canvas);
  }
  
  // 6. Create status overlay
  const statusDiv = document.createElement('div');
  statusDiv.id = '__hip_sync_status';
  statusDiv.style.cssText = 'position:fixed;top:10px;right:10px;background:rgba(0,0,0,0.85);color:#0f0;padding:10px 16px;border-radius:8px;font:12px monospace;z-index:999999;min-width:260px;border:1px solid #0f0;';
  document.body.appendChild(statusDiv);
  
  // 7. Tracking state
  let baseline = null;
  let calibFrames = [];
  const axes = { L0: 5000, L1: 5000, R0: 5000 };
  const smooth = 0.35;
  let frameCount = 0, cmdCount = 0;
  let lastFpsTime = performance.now();
  let fps = 0;
  
  // 8. Main loop
  async function tick() {
    if (video.paused || video.ended || video.readyState < 2) {
      requestAnimationFrame(tick);
      return;
    }
    
    try {
      const poses = await detector.estimatePoses(video);
      if (poses.length === 0) { requestAnimationFrame(tick); return; }
      
      const kps = poses[0].keypoints;
      const lh = kps[11], rh = kps[12]; // left_hip, right_hip
      const ls = kps[5], rs = kps[6];   // left_shoulder, right_shoulder
      
      // Draw overlay
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      // Draw all keypoints
      const skeleton = [[0,1],[0,2],[1,3],[2,4],[5,6],[5,7],[7,9],[6,8],[8,10],[5,11],[6,12],[11,12],[11,13],[13,15],[12,14],[14,16]];
      for (const [i,j] of skeleton) {
        if (kps[i].score > 0.25 && kps[j].score > 0.25) {
          const isHip = [11,12].includes(i) || [11,12].includes(j);
          ctx.strokeStyle = isHip ? '#f80' : 'rgba(0,255,255,0.5)';
          ctx.lineWidth = isHip ? 4 : 2;
          ctx.beginPath(); ctx.moveTo(kps[i].x, kps[i].y); ctx.lineTo(kps[j].x, kps[j].y); ctx.stroke();
        }
      }
      for (let i = 0; i < kps.length; i++) {
        if (kps[i].score > 0.25) {
          const isHip = i === 11 || i === 12;
          ctx.beginPath(); ctx.arc(kps[i].x, kps[i].y, isHip ? 8 : 4, 0, Math.PI * 2);
          ctx.fillStyle = isHip ? '#f80' : '#0ff'; ctx.fill();
          if (isHip) { ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke(); }
        }
      }
      
      // Skip if hip confidence too low
      if (lh.score < 0.3 || rh.score < 0.3) {
        statusDiv.innerHTML = '<span style="color:#f44">⚠ Hip not detected (score: ' + 
          Math.min(lh.score, rh.score).toFixed(2) + ')</span>';
        requestAnimationFrame(tick);
        return;
      }
      
      // Hip center + twist
      const vw = video.videoWidth, vh = video.videoHeight;
      const hipX = (lh.x + rh.x) / 2 / vw;
      const hipY = (lh.y + rh.y) / 2 / vh;
      const twist = Math.atan2(rh.y - lh.y, rh.x - lh.x) * 180 / Math.PI;
      
      // Draw hip center cross
      const cx = (lh.x + rh.x) / 2, cy = (lh.y + rh.y) / 2;
      ctx.strokeStyle = '#ff0'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(cx-20,cy); ctx.lineTo(cx+20,cy); ctx.moveTo(cx,cy-20); ctx.lineTo(cx,cy+20); ctx.stroke();
      
      // Calibrate from first 30 frames
      if (calibFrames.length < 30) {
        calibFrames.push({ x: hipX, y: hipY, twist });
        if (calibFrames.length === 30) {
          baseline = {
            x: calibFrames.reduce((s,f) => s+f.x, 0) / 30,
            y: calibFrames.reduce((s,f) => s+f.y, 0) / 30,
            twist: calibFrames.reduce((s,f) => s+f.twist, 0) / 30,
          };
          log('Baseline calibrated: Y=' + baseline.y.toFixed(3) + ' X=' + baseline.x.toFixed(3));
        }
        statusDiv.innerHTML = '🔄 Calibrating... ' + calibFrames.length + '/30';
        requestAnimationFrame(tick);
        return;
      }
      
      // Map to TCode axes
      const SENS = 1.5;
      const dY = (baseline.y - hipY) * SENS;
      const dX = (hipX - baseline.x) * SENS;
      const dT = (twist - baseline.twist);
      
      const clamp = (v) => Math.max(0, Math.min(9999, v));
      axes.L0 = axes.L0 + (clamp(5000 + dY * 10000) - axes.L0) * (1 - smooth);
      axes.L1 = axes.L1 + (clamp(5000 + dX * 10000) - axes.L1) * (1 - smooth);
      axes.R0 = axes.R0 + (clamp(5000 + dT * 50) - axes.R0) * (1 - smooth);
      
      // Send TCode
      if (wsOk && ws.readyState === 1) {
        const pad = (n) => String(Math.round(n)).padStart(4, '0');
        const cmd = 'L0' + pad(axes.L0) + 'I33 L1' + pad(axes.L1) + 'I33 R0' + pad(axes.R0) + 'I33';
        ws.send(JSON.stringify({ type: 'command', cmd }));
        cmdCount++;
      }
      
      // FPS
      frameCount++;
      const now = performance.now();
      if (now - lastFpsTime > 1000) {
        fps = Math.round(frameCount * 1000 / (now - lastFpsTime));
        frameCount = 0;
        lastFpsTime = now;
      }
      
      // Status display
      statusDiv.innerHTML = 
        '<b style="color:#0ff">Hip Sync × ORS6</b> ' + (wsOk ? '🟢' : '🔴') + '<br>' +
        'FPS: <span style="color:#0f0">' + fps + '</span> | Cmd: ' + cmdCount + '<br>' +
        'L0: <span style="color:#f80">' + Math.round(axes.L0) + '</span> | ' +
        'L1: <span style="color:#f80">' + Math.round(axes.L1) + '</span> | ' +
        'R0: <span style="color:#f80">' + Math.round(axes.R0) + '</span><br>' +
        'Hip: Y=' + hipY.toFixed(3) + ' X=' + hipX.toFixed(3) + ' T=' + twist.toFixed(1) + '°';
      
    } catch(e) {
      // Skip frame on error
    }
    
    setTimeout(() => requestAnimationFrame(tick), 33); // ~30fps
  }
  
  // Start
  if (video.paused) video.play().catch(() => {});
  tick();
  log('Hip Sync started! Calibrating...');
  
  // Expose stop function
  window.__hipSyncStop = () => {
    const overlay = document.getElementById('__hip_sync_overlay');
    const status = document.getElementById('__hip_sync_status');
    if (overlay) overlay.remove();
    if (status) status.remove();
    if (ws) ws.close();
    log('Hip Sync stopped');
  };
})();
""".replace('__HUB_WS__', HUB_WS)


async def run_douyin_mode():
    """Open Douyin in Playwright, inject hip tracking, sync with ORS6"""
    from playwright.async_api import async_playwright
    import tempfile
    
    log.info("启动 Playwright (使用系统Chrome配置)...")
    async with async_playwright() as p:
        # Use persistent context with Chrome channel — inherits system cookies
        user_data = Path(tempfile.gettempdir()) / "hip_sync_chrome_profile"
        user_data.mkdir(exist_ok=True)
        
        # Try to copy Chrome cookies for Douyin auth
        chrome_default = Path.home() / "AppData/Local/Google/Chrome/User Data"
        
        context = await p.chromium.launch_persistent_context(
            str(user_data),
            headless=False,
            channel='chrome',
            viewport={'width': 1280, 'height': 720},
            args=[
                '--disable-blink-features=AutomationControlled',
                '--autoplay-policy=no-user-gesture-required',
            ],
            ignore_default_args=['--enable-automation'],
        )
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Navigate to Douyin main feed (auto-plays videos)
        log.info("导航到抖音主页 (自动播放)...")
        await page.goto('https://www.douyin.com/', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        # Aggressive popup removal loop
        for attempt in range(3):
            removed = await page.evaluate("""() => {
                let count = 0;
                // Remove login/captcha/dialog overlays
                const sels = [
                    '[id*="login"]', '[class*="login"]', '[class*="Login"]',
                    '[class*="modal"]', '[class*="Modal"]', '[class*="mask"]',
                    '[class*="dialog"]', '[class*="Dialog"]',
                    '[id*="captcha"]', '[class*="verify"]', '[class*="guide"]',
                ];
                for (const sel of sels) {
                    document.querySelectorAll(sel).forEach(el => {
                        if (el.offsetHeight > 50 && !el.querySelector('video')) {
                            el.remove(); count++;
                        }
                    });
                }
                // Remove fixed overlays blocking content
                document.querySelectorAll('div').forEach(el => {
                    const s = getComputedStyle(el);
                    if ((s.position === 'fixed' || s.position === 'absolute') &&
                        parseInt(s.zIndex) > 100 && el.offsetWidth > 400 && el.offsetHeight > 200 &&
                        !el.querySelector('video') && !el.querySelector('canvas')) {
                        el.remove(); count++;
                    }
                });
                document.body.style.overflow = 'auto';
                return count;
            }""")
            log.info(f"弹窗清除第{attempt+1}轮: 移除{removed}个元素")
            if removed == 0:
                break
            await page.wait_for_timeout(1000)
        
        # Wait for video to become ready (up to 15s)
        log.info("等待视频加载...")
        for wait in range(15):
            video_info = await page.evaluate("""() => {
                const videos = document.querySelectorAll('video');
                const list = Array.from(videos).map((v, i) => ({
                    i, w: v.videoWidth, h: v.videoHeight,
                    rs: v.readyState, p: v.paused,
                    src: (v.src || v.currentSrc || '').substring(0, 60),
                }));
                // Try to play any paused video
                for (const v of videos) {
                    if (v.paused && v.readyState >= 1) v.play().catch(()=>{});
                }
                return list;
            }""")
            playing = [v for v in video_info if v['rs'] >= 2 and not v['p']]
            ready = [v for v in video_info if v['rs'] >= 2]
            log.info(f"  [{wait+1}s] {len(video_info)}个video, {len(ready)}就绪, {len(playing)}播放中")
            if playing:
                log.info(f"  视频播放中: {playing[0]['w']}x{playing[0]['h']}")
                break
            if ready:
                log.info(f"  视频就绪但暂停, 尝试点击播放")
                try:
                    await page.click('video', force=True, timeout=2000)
                except Exception:
                    pass
            await page.wait_for_timeout(1000)
        
        # Inject hip sync script
        log.info("注入 Hip Sync 脚本...")
        await page.evaluate(INJECT_SCRIPT)
        log.info("Hip Sync 脚本已注入，开始跟踪...")
        
        # Keep running
        log.info("同步运行中... 按 Ctrl+C 停止")
        try:
            while True:
                await page.wait_for_timeout(5000)
                # Check if sync is still running
                try:
                    status = await page.evaluate('() => document.getElementById("__hip_sync_status")?.innerText || "N/A"')
                    log.info(f"状态: {status.replace(chr(10), ' ')[:80]}")
                except Exception:
                    pass
        except KeyboardInterrupt:
            log.info("用户中断")
        finally:
            await context.close()


async def run_local_mode(video_path: str):
    """Open hip_sync.html with a local video file"""
    from playwright.async_api import async_playwright
    
    log.info(f"本地视频模式: {video_path}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(viewport={'width': 1400, 'height': 800})
        
        # Open hip sync page
        await page.goto(f'{HUB_URL}/hip_sync', wait_until='domcontentloaded', timeout=15000)
        await page.wait_for_timeout(2000)
        
        # Load local video via file input
        file_input = await page.query_selector('#file-input')
        if file_input:
            await file_input.set_input_files(video_path)
            log.info("视频已加载")
        
        # Wait for model to load, then start sync
        await page.wait_for_timeout(5000)
        try:
            await page.click('#btn-sync')
            log.info("同步已启动")
        except Exception:
            pass
        
        log.info("运行中... 按 Ctrl+C 停止")
        try:
            while True:
                await page.wait_for_timeout(5000)
        except KeyboardInterrupt:
            pass
        finally:
            await browser.close()


async def run_hip_sync_page():
    """Open hip_sync.html with test video"""
    from playwright.async_api import async_playwright
    
    log.info("打开 Hip Sync 页面...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(viewport={'width': 1400, 'height': 800})
        
        await page.goto(f'{HUB_URL}/hip_sync', wait_until='domcontentloaded', timeout=15000)
        log.info("Hip Sync 页面已打开")
        
        # Click test video button
        await page.wait_for_timeout(3000)
        try:
            await page.click('#btn-test')
            log.info("测试视频已加载")
        except Exception:
            pass
        
        log.info("页面已打开，请在浏览器中操作。按 Ctrl+C 停止")
        try:
            while True:
                await page.wait_for_timeout(5000)
        except KeyboardInterrupt:
            pass
        finally:
            await browser.close()


def main():
    parser = argparse.ArgumentParser(description='Hip Sync × Douyin × ORS6')
    parser.add_argument('--local', type=str, help='Local video file path')
    parser.add_argument('--hip-sync-page', action='store_true', help='Open hip_sync.html with test video')
    parser.add_argument('--hub', type=str, default='http://localhost:8086', help='ORS6 Hub URL')
    args = parser.parse_args()
    
    global HUB_URL, HUB_WS, INJECT_SCRIPT
    HUB_URL = args.hub
    HUB_WS = args.hub.replace('http', 'ws')
    INJECT_SCRIPT = INJECT_SCRIPT.replace('ws://localhost:8086', HUB_WS)
    
    if args.local:
        asyncio.run(run_local_mode(args.local))
    elif args.hip_sync_page:
        asyncio.run(run_hip_sync_page())
    else:
        asyncio.run(run_douyin_mode())


if __name__ == '__main__':
    main()
