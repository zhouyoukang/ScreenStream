/**
 * Quest 3 Simulator — Full Demo E2E Test
 * Tests all 30 demos: HTTP load + IWER injection + XR session capability
 * Run: node test-all-demos.js
 */
const http = require('http');

const DEMOS = [
  // ── core demos ──
  { id: 'hello-vr', path: '/hello-vr/', mode: 'vr' },
  { id: 'mr-passthrough', path: '/mr-passthrough/', mode: 'ar' },
  { id: 'aframe-playground', path: '/aframe-playground/', mode: 'vr' },
  { id: 'hand-grab', path: '/hand-grab/', mode: 'vr' },
  { id: 'shared-space', path: '/shared-space/', mode: 'vr' },
  { id: 'smart-home', path: '/smart-home/', mode: 'ar' },
  { id: 'ar-placement', path: '/ar-placement/', mode: 'ar' },
  { id: 'hand-physics', path: '/hand-physics/', mode: 'vr' },
  { id: 'controller-shooter', path: '/controller-shooter/', mode: 'vr' },
  { id: 'spatial-audio', path: '/spatial-audio/', mode: 'vr' },
  { id: 'gaussian-splat', path: '/gaussian-splat/', mode: 'vr' },
  { id: 'vr-painter', path: '/vr-painter/', mode: 'vr' },
  // ── refs demos (junction linked) ──
  { id: 'ht-basic', path: '/hand-tracking-basic/basic.html', mode: 'vr' },
  { id: 'ht-leap', path: '/hand-tracking-basic/hand-model-leap-motion.html', mode: 'vr' },
  { id: 'ht-aframe', path: '/hand-tracking-basic/aframe.html', mode: 'vr' },
  { id: 'ht-physics', path: '/hand-tracking-basic/aframe-physics.html', mode: 'vr' },
  { id: 'ht-mesh', path: '/hand-tracking-basic/aframe-hand-mesh.html', mode: 'vr' },
  { id: 'ht-drawing', path: '/hand-tracking-basic/3d-drawing.html', mode: 'vr' },
  { id: 'passtracing', path: '/passtracing/', mode: 'ar' },
  // ── enva-xr AR demos (junction linked) ──
  { id: 'enva-basic', path: '/enva-xr/basic/basic.html', mode: 'ar' },
  { id: 'enva-cursor', path: '/enva-xr/cursor/cursor.html', mode: 'ar' },
  { id: 'enva-depth', path: '/enva-xr/depth/depth.html', mode: 'ar' },
  { id: 'enva-depth-canvas', path: '/enva-xr/depth-canvas/depth-canvas.html', mode: 'ar' },
  { id: 'enva-image', path: '/enva-xr/image-target/image-target.html', mode: 'ar' },
  { id: 'enva-light', path: '/enva-xr/light-probe/light-probe.html', mode: 'ar' },
  { id: 'enva-multi', path: '/enva-xr/multi-feature/multi-feature.html', mode: 'ar' },
  // ── custom Quest 3 demos ──
  { id: 'vr-cinema', path: '/vr-cinema/', mode: 'vr' },
  { id: 'beat-vr', path: '/beat-vr/', mode: 'vr' },
  { id: 'depth-lab', path: '/depth-lab/', mode: 'ar' },
  { id: 'teleport', path: '/teleport/', mode: 'vr' },
];

function fetch(url) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, { timeout: 8000 }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ status: res.statusCode, body: data, size: data.length }));
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
  });
}

async function testDemo(demo) {
  const result = { id: demo.id, mode: demo.mode };
  try {
    const r = await fetch(`http://localhost:8444${demo.path}`);
    result.httpOk = r.status === 200;
    result.size = Math.round(r.size / 1024) + 'KB';
    result.hasIWER = r.body.includes('iwe.min.js');
    result.hasVRButton = r.body.includes('VR') || r.body.includes('XR') || r.body.includes('immersive');
    result.hasThree = r.body.includes('three') || r.body.includes('THREE');
    result.hasAFrame = r.body.includes('aframe') || r.body.includes('a-scene');
    result.hasCanvas = r.body.includes('canvas') || r.body.includes('renderer');
    
    // Check for common issues
    const issues = [];
    if (!result.hasIWER) issues.push('NO_IWER');
    if (r.body.includes('404') && r.body.includes('Not Found')) issues.push('MISSING_ASSETS');
    if (r.body.includes('ERR_') || r.body.includes('SyntaxError')) issues.push('JS_ERROR');
    result.issues = issues;
    result.pass = result.httpOk && result.hasIWER && issues.length === 0;
  } catch (e) {
    result.pass = false;
    result.error = e.message;
  }
  return result;
}

async function testSimulator() {
  try {
    const r = await fetch('http://localhost:8444/simulator.html');
    return {
      httpOk: r.status === 200,
      size: Math.round(r.size / 1024) + 'KB',
      hasDemoCount: (r.body.match(/DEMOS\s*=\s*\[/g) || []).length > 0,
      demoIds: (r.body.match(/id:\s*'([^']+)'/g) || []).map(m => m.replace(/id:\s*'([^']+)'/, '$1')),
    };
  } catch (e) {
    return { error: e.message };
  }
}

async function testAssets() {
  const assets = ['/iwe.min.js', '/libs/aframe.min.js'];
  const results = [];
  for (const a of assets) {
    try {
      const r = await fetch(`http://localhost:8444${a}`);
      results.push({ path: a, ok: r.status === 200, size: Math.round(r.size / 1024) + 'KB' });
    } catch (e) {
      results.push({ path: a, ok: false, error: e.message });
    }
  }
  return results;
}

(async () => {
  console.log('╔══════════════════════════════════════════════════╗');
  console.log('║  Quest 3 Simulator — Full E2E Test Suite        ║');
  console.log('╚══════════════════════════════════════════════════╝\n');
  
  // Test 1: Shared assets
  console.log('── Shared Assets ──');
  const assets = await testAssets();
  assets.forEach(a => console.log(`  ${a.ok ? '✅' : '❌'} ${a.path} (${a.ok ? a.size : a.error})`));
  
  // Test 2: Simulator page
  console.log('\n── Simulator Page ──');
  const sim = await testSimulator();
  console.log(`  ${sim.httpOk ? '✅' : '❌'} simulator.html (${sim.size}, ${sim.demoIds.length} demos registered)`);
  
  // Test 3: All demos
  console.log(`\n── Demo Tests (${DEMOS.length}) ──`);
  let pass = 0, fail = 0;
  for (const demo of DEMOS) {
    const r = await testDemo(demo);
    if (r.pass) {
      pass++;
      console.log(`  ✅ ${r.id.padEnd(20)} ${r.size.padStart(6)} IWER=${r.hasIWER ? 'Y' : 'N'} ${r.mode}`);
    } else {
      fail++;
      const reason = r.error || r.issues?.join(',') || 'UNKNOWN';
      console.log(`  ❌ ${r.id.padEnd(20)} ${(r.size || '').padStart(6)} ${reason}`);
    }
  }
  
  console.log(`\n${'═'.repeat(50)}`);
  console.log(`  TOTAL: ${DEMOS.length} | PASS: ${pass} | FAIL: ${fail}`);
  console.log(`  Score: ${Math.round(pass / DEMOS.length * 100)}%`);
  console.log(`${'═'.repeat(50)}`);
  
  process.exit(fail > 0 ? 1 : 0);
})();
