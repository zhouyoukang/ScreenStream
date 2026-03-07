const http = require('http');
const net = require('net');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PORT = 8444;
const ROOT = __dirname;
const IWE_SCRIPT = '<script src="/iwe.min.js"></script>';
const WS_PROXY_PATH = '/quest-ws/';
const WS_BACKEND = { host: '127.0.0.1', port: 9200 };
const NO_INJECT = ['/simulator.html', '/devops.html'];

const MIME = {
  '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css',
  '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.gif': 'image/gif', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
  '.woff2': 'font/woff2', '.fnt': 'text/plain', '.splat': 'application/octet-stream',
  '.gltf': 'model/gltf+json', '.glb': 'model/gltf-binary'
};

// ── IWER Gap Patches (injected after iwe.min.js loads) ──────────────────────
// Real Quest 3 specs (from ADB 2026-03-06):
//   SoC: Qualcomm SXR2230P | GPU: Adreno 740 | RAM: 8GB | Display: 4128×2208 native
//   Render: 3104×1664 (per-eye 1552×1664) | FPS: 72-120 | HDR: HLG+HDR10+HDR10+
//   IMU: ICM45688@800Hz | WiFi6: 5GHz 2401Mbps | Oculus Browser: v41.4
// G1:  Add 'dom-overlay' to supportedFeatures
// G2:  Enable stereo rendering (Quest 3 always renders stereo)
// G3:  Set FOV to ~96° vertical (Quest 3 actual: ~104°H × 96°V)
// G4:  Add 'layers' to supportedFeatures (Quest 3 supports WebXR Layers)
// G5:  Add 'camera-access' to supportedFeatures (cameraserver running on device)
// G13: Update User-Agent to match real Quest 3 OculusBrowser/41.4
const QUEST3_PATCHES = `<script>
(function() {
  // Guard: only run if IWER loaded (sets window.IWE) or polyfilled navigator.xr
  if (typeof IWE === 'undefined' && !(navigator.xr)) return;
  var xr = navigator.xr;
  if (!xr) return;

  // Find IWER's internal XRDevice via Symbol(@iwer/xr-system).device
  function findDevice() {
    var syms = Object.getOwnPropertySymbols ? Object.getOwnPropertySymbols(xr) : [];
    for (var i = 0; i < syms.length; i++) {
      try {
        var v = xr[syms[i]];
        if (v && v.supportedFeatures) return v;
        if (v && v.device && v.device.supportedFeatures) return v.device;
      } catch(e) {}
    }
    return null;
  }

  var _t = setInterval(function() {
    var dev = findDevice();
    if (!dev) return;
    clearInterval(_t);

    // G1: dom-overlay
    if (dev.supportedFeatures && !(dev.supportedFeatures.has ? dev.supportedFeatures.has('dom-overlay') : dev.supportedFeatures.includes('dom-overlay'))) {
      (dev.supportedFeatures.add || dev.supportedFeatures.push).call(dev.supportedFeatures, 'dom-overlay');
      console.log('[XR-Proxy] G1: dom-overlay added');
    }
    // G4: layers
    if (dev.supportedFeatures && !(dev.supportedFeatures.has ? dev.supportedFeatures.has('layers') : dev.supportedFeatures.includes('layers'))) {
      (dev.supportedFeatures.add || dev.supportedFeatures.push).call(dev.supportedFeatures, 'layers');
      console.log('[XR-Proxy] G4: layers added');
    }
    // G5: camera-access
    if (dev.supportedFeatures && !(dev.supportedFeatures.has ? dev.supportedFeatures.has('camera-access') : dev.supportedFeatures.includes('camera-access'))) {
      (dev.supportedFeatures.add || dev.supportedFeatures.push).call(dev.supportedFeatures, 'camera-access');
      console.log('[XR-Proxy] G5: camera-access added');
    }
    // G2: stereo rendering
    if (dev.stereoEnabled !== undefined) {
      dev.stereoEnabled = true;
      console.log('[XR-Proxy] G2: stereoEnabled=true');
    }
    // G3: FOV (Quest 3 vertical ~96° = 1.6755 rad)
    if (dev.fovy !== undefined) {
      dev.fovy = 1.6755;
      console.log('[XR-Proxy] G3: fovy=1.6755 (~96\\u00B0)');
    }
    // G13: User-Agent (IWER sets navigator.userAgent via defineProperty with outdated Chrome/126)
    var q3ua = 'Mozilla/5.0 (X11; Linux x86_64; Quest 3) AppleWebKit/537.36 (KHTML, like Gecko) OculusBrowser/41.4.0.25.55 Chrome/132.0.6834.122 VR Safari/537.36';
    try {
      Object.defineProperty(navigator, 'userAgent', { value: q3ua, configurable: true, writable: true });
      console.log('[XR-Proxy] G13: UA→OculusBrowser/41.4 Chrome/132');
    } catch(e) {
      try { navigator.__defineGetter__('userAgent', function() { return q3ua; }); console.log('[XR-Proxy] G13: UA→OculusBrowser/41.4 (getter)'); }
      catch(e2) { console.log('[XR-Proxy] G13: UA override skipped (non-critical)'); }
    }
    console.log('[XR-Proxy] All patches applied (G1+G2+G3+G4+G5+G13)');
  }, 50);
  setTimeout(function() { clearInterval(_t); }, 5000);
})();
</script>`;

let requestCount = 0;
const startTime = Date.now();

const server = http.createServer((req, res) => {
  let urlPath = decodeURIComponent(req.url.split('?')[0]);

  // API: proxy status endpoint
  if (urlPath === '/api/status') {
    let adbDevices = [];
    try {
      const adbPath = process.env.ADB_PATH || 'D:\\platform-tools\\adb.exe';
      const out = execSync(`"${adbPath}" devices -l`, { timeout: 5000, encoding: 'utf8' });
      adbDevices = out.split('\n').filter(l => l.includes('device') && !l.startsWith('List'))
        .map(l => l.split(/\s+/)[0]).filter(Boolean);
    } catch(e) {}
    const status = {
      proxy: 'running',
      port: PORT,
      uptime: Math.floor((Date.now() - startTime) / 1000),
      requests: requestCount,
      adb: adbDevices,
      patches: ['G1:dom-overlay', 'G2:stereo', 'G3:fov-96deg', 'G4:layers', 'G5:camera-access', 'G13:ua-oculusbrowser41.4'],
      iwer: fs.existsSync(path.join(ROOT, 'iwe.min.js')) ? 'present' : 'missing',
      demos: fs.readdirSync(ROOT).filter(f => {
        try { return fs.statSync(path.join(ROOT, f)).isDirectory() && fs.existsSync(path.join(ROOT, f, 'index.html')); }
        catch(e) { return false; }
      })
    };
    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify(status, null, 2));
    return;
  }

  // API: launch app on device via ADB
  if (urlPath === '/api/launch') {
    const params = new URL(req.url, `http://localhost:${PORT}`).searchParams;
    const pkg = params.get('pkg');
    if (!pkg || !/^[a-zA-Z0-9._]+$/.test(pkg)) {
      res.writeHead(400, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      res.end(JSON.stringify({ ok: false, error: 'invalid package name' }));
      return;
    }
    const ADB = process.env.ADB_PATH || 'D:\\platform-tools\\adb.exe';
    const DEVICE = params.get('device') || process.env.QUEST_SERIAL || '2G0YC5ZG8L08Z7';
    const { execFile } = require('child_process');
    execFile(ADB, ['-s', DEVICE, 'shell', 'monkey', '-p', pkg, '-c', 'android.intent.category.LAUNCHER', '1'], { timeout: 10000 }, (err, stdout, stderr) => {
      res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      if (err) {
        res.end(JSON.stringify({ ok: false, error: err.message, stderr }));
      } else {
        console.log(`[ADB] Launched ${pkg} on ${DEVICE}`);
        res.end(JSON.stringify({ ok: true, pkg, device: DEVICE, output: stdout.trim() }));
      }
    });
    return;
  }

  // API: Screen mirror management (scrcpy + ffmpeg gdigrab)
  const SCRCPY = process.env.SCRCPY_PATH || 'D:\\scrcpy\\scrcpy-win64-v3.1\\scrcpy.exe';
  const SCRCPY_TITLE = 'Q3Mirror';

  const FRAME_PATH = path.join(require('os').tmpdir(), 'q3_frame.jpg');
  const CAPTURE_SCRIPT = path.join(__dirname, 'screen-capture.ps1');

  if (urlPath === '/api/mirror/start') {
    if (global._scrcpyProc) {
      res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      res.end(JSON.stringify({ ok: true, status: 'already running' }));
      return;
    }
    const DEVICE = process.env.QUEST_SERIAL || '2G0YC5ZG8L08Z7';
    const { spawn } = require('child_process');
    // 1. Start scrcpy with visible window
    const scArgs = ['-s', DEVICE, '--max-size', '720', '--max-fps', '15', '--no-audio',
      '--window-title', SCRCPY_TITLE, '--window-x', '0', '--window-y', '0',
      '--window-width', '480', '--window-height', '256', '--always-on-top'];
    global._scrcpyProc = spawn(SCRCPY, scArgs, { stdio: 'ignore' });
    global._scrcpyProc.on('exit', () => { global._scrcpyProc = null; });
    // 2. Start capture daemon (PowerShell with PrintWindow API)
    setTimeout(() => {
      global._captureProc = spawn('powershell', ['-ExecutionPolicy', 'Bypass', '-File', CAPTURE_SCRIPT,
        '-OutputPath', FRAME_PATH, '-WindowTitle', SCRCPY_TITLE, '-IntervalMs', '150'],
        { stdio: 'ignore' });
      global._captureProc.on('exit', () => { global._captureProc = null; });
      console.log('[Mirror] capture daemon started');
    }, 2000);
    console.log(`[Mirror] scrcpy started for ${DEVICE}`);
    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify({ ok: true, status: 'started' }));
    return;
  }

  if (urlPath === '/api/mirror/stop') {
    if (global._captureProc) {
      try { global._captureProc.kill(); } catch(e) {}
      global._captureProc = null;
    }
    if (global._scrcpyProc) {
      try { global._scrcpyProc.kill(); } catch(e) {}
      global._scrcpyProc = null;
    }
    const { execSync: es } = require('child_process');
    try { es('taskkill /F /IM scrcpy.exe 2>nul', { timeout: 3000 }); } catch(e) {}
    try { fs.unlinkSync(FRAME_PATH); } catch(e) {}
    console.log('[Mirror] scrcpy + capture stopped');
    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify({ ok: true, status: 'stopped' }));
    return;
  }

  if (urlPath === '/api/screen') {
    if (!global._scrcpyProc) {
      res.writeHead(400, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      res.end(JSON.stringify({ ok: false, error: 'mirror not started' }));
      return;
    }
    fs.readFile(FRAME_PATH, (err, data) => {
      if (err || !data || data.length < 100) {
        res.writeHead(202, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
        res.end(JSON.stringify({ ok: false, error: 'frame not ready yet — capture daemon starting' }));
      } else {
        res.writeHead(200, { 'Content-Type': 'image/jpeg', 'Cache-Control': 'no-cache, no-store', 'Access-Control-Allow-Origin': '*' });
        res.end(data);
      }
    });
    return;
  }

  // API: Device info (battery, temp, current app, display)
  if (urlPath === '/api/device-info') {
    const params = new URL(req.url, `http://localhost:${PORT}`).searchParams;
    const ADB = process.env.ADB_PATH || 'D:\\platform-tools\\adb.exe';
    const DEVICE = params.get('device') || process.env.QUEST_SERIAL || '2G0YC5ZG8L08Z7';
    const cmd = [
      'dumpsys battery',
      'echo "---SEP---"',
      'dumpsys activity activities | grep mResumedActivity',
      'echo "---SEP---"',
      'cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0',
      'echo "---SEP---"',
      'dumpsys display | grep "mCurrentDisplayRect\\|mScreenSize" | head -2',
      'echo "---SEP---"',
      'dumpsys SurfaceFlinger --latency 2>/dev/null | head -1'
    ].join(' && ');
    const { execFile } = require('child_process');
    execFile(ADB, ['-s', DEVICE, 'shell', cmd], { timeout: 8000, encoding: 'utf8' }, (err, stdout) => {
      res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      if (err) { res.end(JSON.stringify({ ok: false, error: err.message })); return; }
      const parts = stdout.split('---SEP---');
      const battery = {};
      if (parts[0]) {
        const ml = parts[0].match(/level: (\d+)/); if (ml) battery.level = parseInt(ml[1]);
        const mt = parts[0].match(/temperature: (\d+)/); if (mt) battery.temp = parseInt(mt[1]) / 10;
        const ms = parts[0].match(/status: (\d+)/); if (ms) battery.charging = parseInt(ms[1]) === 2;
      }
      let currentApp = 'unknown', currentActivity = '';
      if (parts[1]) {
        const m = parts[1].match(/u0\s+([^\s/]+)\/([^\s}]+)/);
        if (m) { currentApp = m[1]; currentActivity = m[2]; }
      }
      const cpuTemp = parts[2] ? parseInt(parts[2].trim()) / 1000 : 0;
      res.end(JSON.stringify({ ok: true, battery, currentApp, currentActivity, cpuTemp, serial: DEVICE }));
    });
    return;
  }

  // API: Forward input to device (tap/swipe/key/text)
  if (urlPath === '/api/input' && req.method === 'POST') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', () => {
      const ADB = process.env.ADB_PATH || 'D:\\platform-tools\\adb.exe';
      const { execFile } = require('child_process');
      try {
        const inp = JSON.parse(body);
        const DEVICE = inp.device || process.env.QUEST_SERIAL || '2G0YC5ZG8L08Z7';
        let args;
        switch (inp.type) {
          case 'tap': args = ['shell', 'input', 'tap', String(inp.x), String(inp.y)]; break;
          case 'swipe': args = ['shell', 'input', 'swipe', String(inp.x1), String(inp.y1), String(inp.x2), String(inp.y2), String(inp.duration || 300)]; break;
          case 'key': args = ['shell', 'input', 'keyevent', String(inp.keycode)]; break;
          case 'text': args = ['shell', 'input', 'text', String(inp.text).replace(/ /g, '%s')]; break;
          case 'back': args = ['shell', 'input', 'keyevent', '4']; break;
          case 'home': args = ['shell', 'input', 'keyevent', '3']; break;
          default:
            res.writeHead(400, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
            res.end(JSON.stringify({ ok: false, error: 'unknown type: ' + inp.type }));
            return;
        }
        execFile(ADB, ['-s', DEVICE, ...args], { timeout: 5000 }, (err) => {
          res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
          res.end(JSON.stringify({ ok: !err, type: inp.type }));
        });
      } catch(e) {
        res.writeHead(400, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  // ── Android Runtime APIs ─────────────────────────────────────────────────
  // API: List all connected ADB devices
  if (urlPath === '/api/devices') {
    const ADB = process.env.ADB_PATH || 'D:\\platform-tools\\adb.exe';
    const { execFile } = require('child_process');
    execFile(ADB, ['devices', '-l'], { timeout: 5000, encoding: 'utf8' }, (err, stdout) => {
      res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      if (err) { res.end(JSON.stringify({ ok: false, error: err.message })); return; }
      const devices = [];
      stdout.split('\n').forEach(line => {
        const m = line.match(/^(\S+)\s+(device|unauthorized|offline)\s*(.*)/);
        if (m) {
          const props = {};
          (m[3] || '').split(/\s+/).forEach(p => {
            const kv = p.split(':');
            if (kv.length === 2) props[kv[0]] = kv[1];
          });
          devices.push({ serial: m[1], status: m[2], model: props.model || '', product: props.product || '', device: props.device || '' });
        }
      });
      res.end(JSON.stringify({ ok: true, devices, count: devices.length }));
    });
    return;
  }

  // API: Screenshot from any device (uses adb screencap, no scrcpy needed)
  if (urlPath === '/api/screenshot') {
    const params = new URL(req.url, `http://localhost:${PORT}`).searchParams;
    const serial = params.get('device') || process.env.QUEST_SERIAL || '2G0YC5ZG8L08Z7';
    const ADB = process.env.ADB_PATH || 'D:\\platform-tools\\adb.exe';
    const { execFile } = require('child_process');
    execFile(ADB, ['-s', serial, 'exec-out', 'screencap', '-p'], { timeout: 10000, encoding: 'buffer', maxBuffer: 10 * 1024 * 1024 }, (err, stdout) => {
      if (err || !stdout || stdout.length < 100) {
        res.writeHead(500, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
        res.end(JSON.stringify({ ok: false, error: err ? err.message : 'empty frame', device: serial }));
        return;
      }
      res.writeHead(200, { 'Content-Type': 'image/png', 'Cache-Control': 'no-cache', 'Access-Control-Allow-Origin': '*' });
      res.end(stdout);
    });
    return;
  }

  // API: Check if app is installed on device
  if (urlPath === '/api/app/check') {
    const params = new URL(req.url, `http://localhost:${PORT}`).searchParams;
    const pkg = params.get('pkg');
    const serial = params.get('device') || process.env.QUEST_SERIAL || '2G0YC5ZG8L08Z7';
    if (!pkg || !/^[a-zA-Z0-9._]+$/.test(pkg)) {
      res.writeHead(400, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      res.end(JSON.stringify({ ok: false, error: 'invalid pkg' }));
      return;
    }
    const ADB = process.env.ADB_PATH || 'D:\\platform-tools\\adb.exe';
    const { execFile } = require('child_process');
    execFile(ADB, ['-s', serial, 'shell', 'pm', 'list', 'packages', pkg], { timeout: 8000, encoding: 'utf8' }, (err, stdout) => {
      res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      const installed = !err && stdout.includes(`package:${pkg}`);
      res.end(JSON.stringify({ ok: true, pkg, installed, device: serial }));
    });
    return;
  }

  // API: Automated single app test (launch → wait → check foreground → return status)
  if (urlPath === '/api/app/test') {
    const params = new URL(req.url, `http://localhost:${PORT}`).searchParams;
    const pkg = params.get('pkg');
    const serial = params.get('device') || process.env.QUEST_SERIAL || '2G0YC5ZG8L08Z7';
    if (!pkg || !/^[a-zA-Z0-9._]+$/.test(pkg)) {
      res.writeHead(400, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      res.end(JSON.stringify({ ok: false, error: 'invalid pkg' }));
      return;
    }
    const ADB = process.env.ADB_PATH || 'D:\\platform-tools\\adb.exe';
    const { execFile } = require('child_process');
    const result = { pkg, device: serial, steps: {} };

    // Step 1: Check installed
    execFile(ADB, ['-s', serial, 'shell', 'pm', 'list', 'packages', pkg], { timeout: 5000, encoding: 'utf8' }, (err, stdout) => {
      result.steps.installed = !err && stdout.includes(`package:${pkg}`);
      if (!result.steps.installed) {
        result.ok = false;
        result.error = 'not_installed';
        res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
        res.end(JSON.stringify(result));
        return;
      }
      // Step 2: Launch
      execFile(ADB, ['-s', serial, 'shell', 'monkey', '-p', pkg, '-c', 'android.intent.category.LAUNCHER', '1'], { timeout: 10000, encoding: 'utf8' }, (err2, stdout2) => {
        result.steps.launched = !err2 && !stdout2.includes('No activities found');
        if (!result.steps.launched) {
          result.ok = false;
          result.error = 'launch_failed';
          result.detail = err2 ? err2.message : stdout2.trim();
          res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
          res.end(JSON.stringify(result));
          return;
        }
        // Step 3: Wait 2s then check foreground activity
        setTimeout(() => {
          execFile(ADB, ['-s', serial, 'shell', 'dumpsys', 'activity', 'activities', '|', 'grep', 'mResumedActivity'], { timeout: 5000, encoding: 'utf8' }, (err3, stdout3) => {
            const fgMatch = stdout3 ? stdout3.match(/u0\s+([^\s/]+)/) : null;
            result.steps.foreground = fgMatch ? fgMatch[1] : 'unknown';
            result.steps.isForeground = result.steps.foreground.startsWith(pkg.split('.').slice(0, 2).join('.'));
            result.ok = true;
            result.steps.crashed = false;

            // Step 4: Check for crash dialog
            execFile(ADB, ['-s', serial, 'shell', 'dumpsys', 'window', 'windows', '|', 'grep', '-i', 'crash\\|anr\\|stopped'], { timeout: 3000, encoding: 'utf8' }, (err4, stdout4) => {
              if (!err4 && stdout4 && stdout4.trim()) {
                result.steps.crashed = true;
                result.steps.crashInfo = stdout4.trim().substring(0, 200);
              }
              console.log(`[AppTest] ${pkg} on ${serial}: installed=${result.steps.installed} launched=${result.steps.launched} fg=${result.steps.foreground} crashed=${result.steps.crashed}`);
              res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
              res.end(JSON.stringify(result));
            });
          });
        }, 2000);
      });
    });
    return;
  }

  // API: Open URL in Quest 3 browser
  if (urlPath === '/api/launch-url') {
    const params = new URL(req.url, `http://localhost:${PORT}`).searchParams;
    const url = params.get('url');
    if (!url) {
      res.writeHead(400, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      res.end(JSON.stringify({ ok: false, error: 'url parameter required' }));
      return;
    }
    const ADB = process.env.ADB_PATH || 'D:\\platform-tools\\adb.exe';
    const DEVICE = process.env.QUEST_SERIAL || '2G0YC5ZG8L08Z7';
    const { execFile } = require('child_process');
    execFile(ADB, ['-s', DEVICE, 'shell', 'am', 'start', '-a', 'android.intent.action.VIEW', '-d', url], { timeout: 10000, encoding: 'utf8' }, (err, stdout) => {
      res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      if (err) { res.end(JSON.stringify({ ok: false, error: err.message })); }
      else {
        console.log(`[ADB] Opened URL on ${DEVICE}: ${url}`);
        res.end(JSON.stringify({ ok: true, url, device: DEVICE }));
      }
    });
    return;
  }

  requestCount++;
  // Strip /quest/ prefix so self-hosted paths work locally (matches Nginx alias on public server)
  if (urlPath.startsWith('/quest/')) urlPath = urlPath.slice(6);
  if (urlPath.endsWith('/')) urlPath += 'index.html';
  const filePath = path.join(ROOT, urlPath);

  if (!filePath.startsWith(ROOT)) {
    res.writeHead(403); res.end('Forbidden'); return;
  }

  fs.readFile(filePath, (err, data) => {
    if (err) { res.writeHead(404); res.end('Not Found: ' + urlPath); return; }
    const ext = path.extname(filePath).toLowerCase();
    const mime = MIME[ext] || 'application/octet-stream';
    
    if (ext === '.html' && !NO_INJECT.includes(urlPath)) {
      let html = data.toString('utf8');
      const injection = IWE_SCRIPT + QUEST3_PATCHES;
      // Inject IWER + patches before first <script> or after <head>
      if (html.includes('<head>')) {
        html = html.replace('<head>', '<head>' + injection);
      } else if (html.includes('<script')) {
        html = html.replace(/<script/, injection + '<script');
      } else {
        html = injection + html;
      }
      res.writeHead(200, { 'Content-Type': mime, 'Access-Control-Allow-Origin': '*' });
      res.end(html);
    } else {
      res.writeHead(200, { 'Content-Type': mime, 'Access-Control-Allow-Origin': '*' });
      res.end(data);
    }
  });
});

// WebSocket proxy: forward /quest-ws/ upgrades to shared-space server (:9200)
server.on('upgrade', (req, socket, head) => {
  if (!req.url.startsWith(WS_PROXY_PATH)) {
    socket.destroy();
    return;
  }

  const backend = net.connect(WS_BACKEND.port, WS_BACKEND.host, () => {
    // Rewrite request path: strip /quest-ws/ prefix
    const newPath = '/' + req.url.slice(WS_PROXY_PATH.length);
    const reqLine = `${req.method} ${newPath} HTTP/${req.httpVersion}\r\n`;
    const headers = Object.entries(req.headers)
      .map(([k, v]) => `${k}: ${v}`)
      .join('\r\n');
    backend.write(reqLine + headers + '\r\n\r\n');
    if (head.length) backend.write(head);
    socket.pipe(backend).pipe(socket);
  });

  backend.on('error', () => {
    try {
      socket.write('HTTP/1.1 502 Bad Gateway\r\n\r\nShared-Space server not running on :9200\n');
    } catch(e) {}
    socket.destroy();
  });

  socket.on('error', () => backend.destroy());
});

// ── Hot-reload: watch for file changes ──────────────────────────────────────
let reloadClients = [];
server.on('request', (req, res) => {
  if (req.url === '/__reload_events') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*'
    });
    reloadClients.push(res);
    req.on('close', () => { reloadClients = reloadClients.filter(c => c !== res); });
    return;
  }
});

let debounce = null;
fs.watch(ROOT, { recursive: true }, (eventType, filename) => {
  if (!filename || filename.startsWith('.') || filename.includes('node_modules')) return;
  const ext = path.extname(filename).toLowerCase();
  if (!['.html', '.js', '.css', '.json'].includes(ext)) return;
  clearTimeout(debounce);
  debounce = setTimeout(() => {
    console.log(`[Hot-Reload] ${filename} changed — notifying ${reloadClients.length} client(s)`);
    reloadClients.forEach(c => { try { c.write(`data: ${filename}\n\n`); } catch(e) {} });
  }, 300);
});

server.listen(PORT, () => {
  console.log(`\n  ╔══════════════════════════════════════════════════════╗`);
  console.log(`  ║  Quest 3 XR Proxy — Enhanced                        ║`);
  console.log(`  ╠══════════════════════════════════════════════════════╣`);
  console.log(`  ║  URL:      http://localhost:${PORT}                    ║`);
  console.log(`  ║  Status:   http://localhost:${PORT}/api/status          ║`);
  console.log(`  ║  WS Proxy: ${WS_PROXY_PATH} → :${WS_BACKEND.port}                      ║`);
  console.log(`  ║  IWER:     ${fs.existsSync(path.join(ROOT, 'iwe.min.js')) ? '✅ present' : '❌ MISSING'}                              ║`);
  console.log(`  ╠══════════════════════════════════════════════════════╣`);
  console.log(`  ║  Patches:  G1 dom-overlay  │ G2 stereo             ║`);
  console.log(`  ║            G3 fov-96°      │ G4 layers             ║`);
  console.log(`  ║            G5 camera-access│ G13 UA OB/41.4        ║`);
  console.log(`  ║  Features: Hot-reload SSE  │ /api/status           ║`);
  console.log(`  ║           App Center (39)  │ /api/launch           ║`);
  console.log(`  ╚══════════════════════════════════════════════════════╝\n`);
});
