/**
 * 号池管理端 热部署脚本 v1.0
 *
 * 用法:
 *   npm run hot          — 源文件 -> ~/.pool-admin-hot/ -> 自动热重载
 *   npm run hot:build    — webpack构建 -> 热部署
 *   npm run hot:signal   — 仅触发热重载信号
 *   npm run hot:inject   — 覆盖安装目录 (首次启用热重载)
 *   npm run hot:watch    — 持续监听src/ -> 自动部署
 */
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const HOT_DIR = path.join(os.homedir(), '.pool-admin-hot');
const PROJECT = path.join(__dirname, '..');
const SRC_DIR = path.join(PROJECT, 'src');
const SRC_FILES = ['extension.js', 'lanGuard.js', 'poolManager.js', 'adminPanel.js'];

const args = process.argv.slice(2);
const isInject = args.includes('--inject');
const isBuild = args.includes('--build');
const isSignalOnly = args.includes('--signal');
const isWatch = args.includes('--watch');

function log(step, msg) { console.log(`  [${step}] ${msg}`); }

function findInstallDir() {
  const candidates = [
    path.join(os.homedir(), '.windsurf', 'extensions'),
    path.join(os.homedir(), '.codeium', 'windsurf', 'data', 'User', 'extensions'),
  ];
  for (const base of candidates) {
    if (!fs.existsSync(base)) continue;
    const dirs = fs.readdirSync(base).filter(d => d.startsWith('zhouyoukang.pool-admin'));
    if (dirs.length > 0) return path.join(base, dirs.sort().pop());
  }
  return null;
}

console.log('');
console.log('===================================');
console.log('  Pool Admin Hot Deploy v1.0');
console.log('===================================');
console.log('');

if (isSignalOnly) {
  log('1/1', 'Signal...');
  fs.mkdirSync(HOT_DIR, { recursive: true });
  fs.writeFileSync(path.join(HOT_DIR, '.reload'), String(Date.now()));
  console.log('\n  Done.\n');
  process.exit(0);
}

if (isInject) {
  const installDir = findInstallDir();
  if (!installDir) { console.error('  Extension install dir not found.'); process.exit(1); }
  log('1/3', 'Found: ' + installDir);
  log('2/3', 'Copying...');
  const targets = [
    ...SRC_FILES.map(f => ({ src: path.join(SRC_DIR, f), dst: path.join(installDir, 'src', f) })),
    { src: path.join(PROJECT, 'package.json'), dst: path.join(installDir, 'package.json') },
  ];
  let n = 0;
  for (const { src, dst } of targets) {
    if (fs.existsSync(src)) {
      fs.mkdirSync(path.dirname(dst), { recursive: true });
      fs.copyFileSync(src, dst);
      log('   ', path.basename(src) + ' (' + (fs.statSync(dst).size / 1024).toFixed(1) + 'KB)');
      n++;
    }
  }
  log('3/3', n + ' files injected.');
  console.log('\n  Restart Extension Host to apply.\n');
  process.exit(0);
}

function deployRaw(quiet) {
  fs.mkdirSync(HOT_DIR, { recursive: true });
  let n = 0;
  for (const f of SRC_FILES) {
    const src = path.join(SRC_DIR, f);
    const dst = path.join(HOT_DIR, f);
    if (fs.existsSync(src)) {
      fs.copyFileSync(src, dst);
      if (!quiet) log('   ', f + ' (' + (fs.statSync(dst).size / 1024).toFixed(1) + 'KB)');
      n++;
    }
  }
  // Also copy media files
  const mediaDir = path.join(PROJECT, 'media');
  const hotMedia = path.join(HOT_DIR, 'media');
  if (fs.existsSync(mediaDir)) {
    fs.mkdirSync(hotMedia, { recursive: true });
    for (const f of fs.readdirSync(mediaDir)) {
      fs.copyFileSync(path.join(mediaDir, f), path.join(hotMedia, f));
      if (!quiet) log('   ', 'media/' + f);
    }
  }
  fs.writeFileSync(path.join(HOT_DIR, '.reload'), String(Date.now()));
  return n;
}

if (isWatch) {
  log('WATCH', 'Monitoring ' + SRC_DIR);
  const initial = deployRaw(false);
  console.log('\n  Initial: ' + initial + ' files. Watching... Ctrl+C to stop.\n');
  let debounce = null;
  fs.watch(SRC_DIR, { persistent: true }, (ev, fn) => {
    if (!fn || !SRC_FILES.includes(fn)) return;
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => {
      debounce = null;
      const ts = new Date().toLocaleTimeString();
      const n = deployRaw(true);
      console.log('  [' + ts + '] ' + fn + ' -> ' + n + ' files deployed');
    }, 400);
  });
  process.on('SIGINT', () => { console.log('\n  Stopped.\n'); process.exit(0); });
  return;
}

// Default: raw source deploy
log('1/2', 'Copying source -> ' + HOT_DIR);
const copied = deployRaw(false);
log('2/2', 'Signal sent.');
console.log('\n  ' + copied + ' files -> ' + HOT_DIR);
console.log('  Hot reload active. Zero restart.\n');
