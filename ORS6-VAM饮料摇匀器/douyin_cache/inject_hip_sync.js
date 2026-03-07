// === Hip Sync x ORS6 === Douyin Injection Script ===
// Usage: Open Douyin in Chrome, press F12, paste this into Console, press Enter.
// Prerequisites: ORS6 Hub running at localhost:8086
(async () => {
  const HUB_WS_URL = 'ws://localhost:8086';
  const log = (msg) => console.log('[HipSync]', msg);
  
  // 1. Find video element
  let video = null;
  for (let i = 0; i < 15; i++) {
    const videos = document.querySelectorAll('video');
    video = Array.from(videos).find(v => !v.paused && v.readyState >= 2 && v.videoWidth > 0) || 
            Array.from(videos).find(v => v.readyState >= 2 && v.videoWidth > 0) ||
            videos[0];
    if (video && video.readyState >= 2 && video.videoWidth > 0) break;
    log('Waiting for video... (' + (i+1) + '/15)');
    await new Promise(r => setTimeout(r, 1000));
  }
  if (!video || video.readyState < 2 || video.videoWidth === 0) {
    log('ERROR: No playable video found. Make sure a video is playing on the page.');
    return;
  }
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
  log('Creating MoveNet detector (may take 5-10s)...');
  const detector = await poseDetection.createDetector(
    poseDetection.SupportedModels.MoveNet,
    { modelType: poseDetection.movenet.modelType.SINGLEPOSE_LIGHTNING }
  );
  log('MoveNet ready!');
  
  // 4. Connect to ORS6 Hub
  let ws = null, wsOk = false;
  function connectWS() {
    ws = new WebSocket(HUB_WS_URL);
    ws.onopen = () => { wsOk = true; log('ORS6 Hub connected'); };
    ws.onclose = () => { wsOk = false; log('Hub disconnected, reconnecting...'); setTimeout(connectWS, 2000); };
  }
  connectWS();
  
  // 5. Create overlay canvas
  const canvas = document.createElement('canvas');
  canvas.id = '__hip_sync_overlay';
  canvas.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:99999;';
  let container = video.parentElement;
  if (container) { container.style.position = 'relative'; container.appendChild(canvas); }
  
  // 6. Status HUD
  const hud = document.createElement('div');
  hud.id = '__hip_sync_hud';
  hud.style.cssText = 'position:fixed;top:10px;right:10px;background:rgba(0,0,0,0.85);color:#0f0;padding:10px 16px;border-radius:8px;font:12px monospace;z-index:999999;min-width:280px;border:1px solid #0f0;';
  document.body.appendChild(hud);
  
  // 7. Tracking
  let baseline = null, calibFrames = [];
  const axes = { L0: 5000, L1: 5000, R0: 5000 };
  const smooth = 0.35;
  let frameCount = 0, cmdCount = 0, lastFpsTime = performance.now(), fps = 0;
  const HIP_L = 11, HIP_R = 12;
  const SKELETON = [[0,1],[0,2],[1,3],[2,4],[5,6],[5,7],[7,9],[6,8],[8,10],[5,11],[6,12],[11,12],[11,13],[13,15],[12,14],[14,16]];
  
  async function tick() {
    if (video.paused || video.ended || video.readyState < 2) { requestAnimationFrame(tick); return; }
    
    try {
      const poses = await detector.estimatePoses(video);
      if (!poses.length) { requestAnimationFrame(tick); return; }
      
      const kps = poses[0].keypoints;
      const lh = kps[HIP_L], rh = kps[HIP_R];
      
      // Draw skeleton
      canvas.width = video.videoWidth; canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const [i,j] of SKELETON) {
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
          ctx.beginPath(); ctx.arc(kps[i].x, kps[i].y, isHip ? 8 : 4, 0, Math.PI*2);
          ctx.fillStyle = isHip ? '#f80' : '#0ff'; ctx.fill();
        }
      }
      
      if (lh.score < 0.3 || rh.score < 0.3) {
        hud.innerHTML = '<span style="color:#f44">Hip not detected (conf: ' + Math.min(lh.score,rh.score).toFixed(2) + ')</span>';
        requestAnimationFrame(tick); return;
      }
      
      // Hip center cross
      const cx = (lh.x+rh.x)/2, cy = (lh.y+rh.y)/2;
      ctx.strokeStyle = '#ff0'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(cx-20,cy); ctx.lineTo(cx+20,cy); ctx.moveTo(cx,cy-20); ctx.lineTo(cx,cy+20); ctx.stroke();
      
      const vw = video.videoWidth, vh = video.videoHeight;
      const hipX = (lh.x+rh.x)/2/vw, hipY = (lh.y+rh.y)/2/vh;
      const twist = Math.atan2(rh.y-lh.y, rh.x-lh.x) * 180/Math.PI;
      
      // Calibrate
      if (calibFrames.length < 30) {
        calibFrames.push({x:hipX, y:hipY, twist});
        if (calibFrames.length === 30) {
          baseline = {
            x: calibFrames.reduce((s,f)=>s+f.x,0)/30,
            y: calibFrames.reduce((s,f)=>s+f.y,0)/30,
            twist: calibFrames.reduce((s,f)=>s+f.twist,0)/30,
          };
          log('Baseline: Y='+baseline.y.toFixed(3)+' X='+baseline.x.toFixed(3));
        }
        hud.innerHTML = 'Calibrating... ' + calibFrames.length + '/30';
        requestAnimationFrame(tick); return;
      }
      
      // Map to axes
      const SENS = 1.5;
      const clamp = v => Math.max(0, Math.min(9999, v));
      axes.L0 += (clamp(5000 + (baseline.y-hipY)*SENS*10000) - axes.L0) * (1-smooth);
      axes.L1 += (clamp(5000 + (hipX-baseline.x)*SENS*10000) - axes.L1) * (1-smooth);
      axes.R0 += (clamp(5000 + (twist-baseline.twist)*50) - axes.R0) * (1-smooth);
      
      // Send TCode
      if (wsOk && ws.readyState === 1) {
        const pad = n => String(Math.round(n)).padStart(4,'0');
        ws.send(JSON.stringify({type:'command', cmd:'L0'+pad(axes.L0)+'I33 L1'+pad(axes.L1)+'I33 R0'+pad(axes.R0)+'I33'}));
        cmdCount++;
      }
      
      // FPS
      frameCount++;
      const now = performance.now();
      if (now - lastFpsTime > 1000) { fps = Math.round(frameCount*1000/(now-lastFpsTime)); frameCount=0; lastFpsTime=now; }
      
      hud.innerHTML = '<b style="color:#0ff">Hip Sync x ORS6</b> '+(wsOk?'🟢':'🔴')+'<br>'+
        fps+'fps | '+cmdCount+' cmds<br>'+
        'L0:<span style="color:#f80">'+Math.round(axes.L0)+'</span> L1:<span style="color:#f80">'+Math.round(axes.L1)+'</span> R0:<span style="color:#f80">'+Math.round(axes.R0)+'</span><br>'+
        'Hip Y='+hipY.toFixed(3)+' X='+hipX.toFixed(3)+' T='+twist.toFixed(1)+'deg';
    } catch(e) {}
    
    setTimeout(() => requestAnimationFrame(tick), 33);
  }
  
  if (video.paused) video.play().catch(()=>{});
  tick();
  log('Hip Sync started! Calibrating (30 frames)...');
  
  // Stop function
  window.__hipSyncStop = () => {
    document.getElementById('__hip_sync_overlay')?.remove();
    document.getElementById('__hip_sync_hud')?.remove();
    if (ws) ws.close();
    log('Hip Sync stopped');
  };
  log('To stop: window.__hipSyncStop()');
})();
