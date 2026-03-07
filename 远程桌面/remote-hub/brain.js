// Brain CLI - 道的手指
// Usage: node brain.js exec "command"
//        node brain.js state
//        node brain.js say "message"
//        node brain.js terminal

const http = require('http');
const BASE = 'http://localhost:3002';

function post(path, data) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(data);
    const req = http.request(BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    }, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => {
        try { resolve(JSON.parse(d)); } catch(e) { resolve(d); }
      });
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

function get(path) {
  return new Promise((resolve, reject) => {
    http.get(BASE + path, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => {
        try { resolve(JSON.parse(d)); } catch(e) { resolve(d); }
      });
    }).on('error', reject);
  });
}

async function main() {
  const cmd = process.argv[2];
  const arg = process.argv.slice(3).join(' ');

  if (cmd === 'exec' || cmd === 'x') {
    const t0 = Date.now();
    const r = await post('/brain/exec', { cmd: arg, timeout: 60000 });
    const dt = Date.now() - t0;
    if (r.ok) {
      console.log(r.output);
      console.log('\n--- OK ' + (r.ms || '?') + 'ms (roundtrip ' + dt + 'ms) ---');
    } else {
      console.error('FAIL:', r.error || r.output);
    }
  } else if (cmd === 'state' || cmd === 's') {
    const r = await get('/brain/state');
    console.log(JSON.stringify(r, null, 2));
  } else if (cmd === 'say') {
    const r = await post('/brain/say', { text: arg, level: 'system' });
    console.log(r);
  } else if (cmd === 'terminal' || cmd === 't') {
    const r = await get('/brain/terminal?n=' + (arg || 10));
    r.forEach(e => {
      console.log('> ' + e.cmd);
      console.log(e.output);
      console.log('---');
    });
  } else if (cmd === 'sysinfo' || cmd === 'si') {
    const r = await post('/brain/sysinfo', {});
    console.log(JSON.stringify(r, null, 2));
  } else if (cmd === 'auto' || cmd === 'a') {
    console.log('Running auto-diagnostics...\n');
    const t0 = Date.now();
    const r = await post('/brain/auto', {});
    const dt = Date.now() - t0;
    if (r.ok && r.results) {
      var maxName = 0;
      r.results.forEach(function(x) { if (x.name.length > maxName) maxName = x.name.length; });
      r.results.forEach(function(x) {
        var pad = x.name + ' '.repeat(maxName - x.name.length + 2);
        var out = (x.output || '').replace(/\n/g, ' ').substring(0, 80);
        console.log((x.ok ? 'OK' : 'FAIL') + '  ' + pad + out + (x.ms ? '  (' + x.ms + 'ms)' : ''));
      });
      console.log('\n--- ' + r.results.filter(function(x){return x.ok}).length + '/' + r.results.length + ' passed (' + dt + 'ms total) ---');
    } else {
      console.error('FAIL:', r.error || JSON.stringify(r));
    }
  } else if (cmd === 'messages' || cmd === 'msg' || cmd === 'm') {
    const r = await get('/brain/messages' + (arg === 'peek' ? '?clear=false' : ''));
    if (r.count === 0) { console.log('(no new messages)'); }
    else { r.messages.forEach(function(m) { console.log('[' + m.time + '] ' + m.text); }); }
  } else {
    console.log('Usage: node brain.js <exec|state|say|terminal|sysinfo|auto|messages> [args]');
  }
}

main().catch(e => console.error(e.message));
