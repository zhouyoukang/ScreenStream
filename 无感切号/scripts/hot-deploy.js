/**
 * WAM 热部署脚本 v4.0 — 万法归宗·永不重载
 *
 * 道法自然 · 水利万物而不争 · 状态不灭
 *
 * 核心改进(v4.0): 双写归一
 *   每次部署同时写入 ~/.wam-hot/ (即时热重载) + 安装目录 (持久化)
 *   → 即时生效 + 重启不丢失 = 永不需要重载窗口
 *
 * 用法:
 *   npm run hot          — src/ → hot+install → 即时生效 (唯一需要的命令)
 *   npm run hot:watch    — 持续监听src/ → 自动双写+热重载 (开发推荐)
 *   npm run hot:build    — webpack构建 → hot+install → 热重载
 *   npm run hot:signal   — 仅触发热重载信号
 *   npm run hot:inject   — 兼容: 仅覆盖安装目录
 */
const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const os = require("os");

const HOT_DIR = path.join(os.homedir(), ".wam-hot");
const PROJECT = path.join(__dirname, "..");
const DIST = path.join(PROJECT, "dist", "extension.js");
const SRC_DIR = path.join(PROJECT, "src");
const MEDIA_DIR = path.join(PROJECT, "media");
const SRC_FILES = [
  "extension.js",
  "accountManager.js",
  "authService.js",
  "fingerprintManager.js",
  "webviewProvider.js",
  "cloudPool.js",
];
const MEDIA_FILES = ["panel.html", "panel.js", "icon.svg"];
const EXTRA_FILES = ["package.json"];

const args = process.argv.slice(2);
const isInject = args.includes("--inject");
const isBuild = args.includes("--build");
const isSignalOnly = args.includes("--signal");
const isWatch = args.includes("--watch");

function log(step, msg) {
  console.log(`  [${step}] ${msg}`);
}

/** 搜索扩展安装目录 (Windsurf多版本兼容) */
function findInstallDir() {
  const candidates = [
    path.join(os.homedir(), ".windsurf", "extensions"),
    path.join(os.homedir(), ".codeium", "windsurf", "data", "User", "extensions"),
  ];
  // 额外: 从Windsurf进程路径推断
  try {
    const windsurf = process.env.VSCODE_PID ? null : null; // placeholder
    const portable = process.env.WINDSURF_PORTABLE;
    if (portable) candidates.unshift(path.join(portable, "extensions"));
  } catch {}
  for (const base of candidates) {
    if (!fs.existsSync(base)) continue;
    const dirs = fs.readdirSync(base).filter(d =>
      d.startsWith("zhouyoukang.windsurf-assistant")
    );
    if (dirs.length > 0) {
      return path.join(base, dirs.sort().pop());
    }
  }
  return null;
}

/** 复制单文件, 返回字节数 */
function copyOne(src, dst) {
  if (!fs.existsSync(src)) return 0;
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
  return fs.statSync(dst).size;
}

console.log("");
console.log("═══════════════════════════════════════════");
console.log("  WAM Hot Deploy v4.0 · 道法自然 · 万法归宗");
console.log("═══════════════════════════════════════════");
console.log("");

// ── 仅触发信号 ──
if (isSignalOnly) {
  log("1/1", "Triggering reload signal...");
  fs.mkdirSync(HOT_DIR, { recursive: true });
  fs.writeFileSync(path.join(HOT_DIR, ".reload"), String(Date.now()));
  console.log("\n  ✓ Signal sent.\n");
  process.exit(0);
}

// ── v5.0: --inject 自动激活 (道法自然: 注入即生效, 无需手动操作) ──
if (isInject) {
  const installDir = findInstallDir();
  if (!installDir) {
    console.error('  \u2717 Extension install directory not found.');
    process.exit(1);
  }
  log('1/3', 'Found install: ' + installDir);
  log('2/3', 'Copying source files to install directory...');
  let copied = 0;
  for (const f of SRC_FILES) {
    const sz = copyOne(path.join(SRC_DIR, f), path.join(installDir, 'src', f));
    if (sz) { log('   ', 'src/' + f + ' (' + (sz / 1024).toFixed(1) + 'KB)'); copied++; }
  }
  for (const f of MEDIA_FILES) {
    const sz = copyOne(path.join(MEDIA_DIR, f), path.join(installDir, 'media', f));
    if (sz) { log('   ', 'media/' + f + ' (' + (sz / 1024).toFixed(1) + 'KB)'); copied++; }
  }
  for (const f of EXTRA_FILES) {
    const sz = copyOne(path.join(PROJECT, f), path.join(installDir, f));
    if (sz) { log('   ', f + ' (' + (sz / 1024).toFixed(1) + 'KB)'); copied++; }
  }
  // v5.0: Auto-activate — dual-write to hot dir + signal + autoHeal
  log('3/3', 'Auto-activating: dual-write + signal + autoHeal...');
  fs.mkdirSync(HOT_DIR, { recursive: true });
  for (const f of SRC_FILES) {
    const src = path.join(SRC_DIR, f);
    if (fs.existsSync(src)) fs.copyFileSync(src, path.join(HOT_DIR, f));
  }
  // Syntax validation
  const extHot = path.join(HOT_DIR, 'extension.js');
  if (fs.existsSync(extHot)) {
    const v = validateSyntax(extHot);
    if (!v.ok) {
      console.error('  SYNTAX ERROR -> signal NOT sent. Fix and retry.');
      console.error('    ' + v.error);
      process.exit(1);
    }
  }
  // Completeness check
  const missing = SRC_FILES.filter(f => !fs.existsSync(path.join(HOT_DIR, f)));
  if (missing.length > 0) {
    console.error('  ABORT: hot dir missing ' + missing.join(', '));
    process.exit(1);
  }
  // Signal hot reload
  fs.writeFileSync(path.join(HOT_DIR, '.reload'), String(Date.now()));
  console.log('');
  console.log('  ' + copied + ' files -> install+hot dir. Auto-activating...');
  // autoHeal: verify Hub comes back, IPC restart if needed
  autoHeal(10000).then(ok => {
    if (ok) console.log('  Hub OK. inject auto-activated. \u4e07\u6cd5\u5f52\u5b97\n');
    else console.log('  Hub no response. Try Reload Window.\n');
    process.exit(0); // prevent fall-through to default deploy section
  });
}

// ── Webpack构建模式 ──
if (isBuild) {
  log("1/4", "Building with webpack...");
  try {
    execSync("npx webpack --config webpack.config.js", { cwd: PROJECT, stdio: "inherit" });
  } catch (e) {
    console.error("\n  ✗ Build failed.\n");
    process.exit(1);
  }
  if (!fs.existsSync(DIST)) {
    console.error(`\n  ✗ Build output not found: ${DIST}\n`);
    process.exit(1);
  }
  fs.mkdirSync(HOT_DIR, { recursive: true });
  const dst = path.join(HOT_DIR, "extension.js");
  fs.copyFileSync(DIST, dst);
  const size = fs.statSync(dst).size;
  log("2/4", `extension.js (${(size / 1024).toFixed(1)}KB) → ${HOT_DIR}`);
  // 双写: 同步到安装目录
  const installDir = findInstallDir();
  if (installDir) {
    fs.copyFileSync(DIST, path.join(installDir, "src", "extension.js"));
    log("3/4", `extension.js → install dir (持久化)`);
  } else {
    log("3/4", `install dir not found (跳过持久化, 仅热重载)`);
  }
  log("4/4", "Signal...");
  fs.writeFileSync(path.join(HOT_DIR, ".reload"), String(Date.now()));
  console.log(`\n  ✓ Webpack hot deploy done. 即时生效·永不重载.\n`);
  process.exit(0);
}

// ═══ v16.0: 语法验证防护 + IPC自愈 (道法自然·热传递链完整性) ═══
// 根因: PowerShell模板字符串被吃→语法错误→扩展崩溃→watcher死→需手动重载
// 修复: 部署前Node.js语法检查 + 部署后健康探测 + 失败时IPC管道自动恢复

function validateSyntax(filePath) {
  try {
    const code = fs.readFileSync(filePath, 'utf8');
    new Function(code); // 语法检查(不执行)
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message, line: e.lineNumber || '?' };
  }
}

function autoHeal(maxWait) {
  const http = require('http');
  const net = require('net');
  const wait = maxWait || 8000;
  const start = Date.now();
  
  return new Promise((resolve) => {
    const check = () => {
      if (Date.now() - start > wait) {
        // Hub still down → IPC pipe recovery
        log('HEAL', 'Hub offline after deploy → IPC pipe recovery...');
        try {
          // Find Windsurf IPC pipe
          const pipes = fs.readdirSync('\\\\.\\pipe\\').filter(p => /main-sock$/.test(p));
          if (pipes.length === 0) { log('HEAL', 'No IPC pipe found'); resolve(false); return; }
          const pipePath = '\\\\.\\pipe\\' + pipes[0];
          const client = net.connect(pipePath, () => {
            const msg = JSON.stringify({type:'restartExtensionHost'});
            const header = Buffer.alloc(4);
            header.writeUInt32LE(Buffer.byteLength(msg));
            client.write(header);
            client.write(msg);
            log('HEAL', 'IPC restart sent via ' + pipePath);
            setTimeout(() => { client.destroy(); resolve(true); }, 1000);
          });
          client.on('error', () => { log('HEAL', 'IPC pipe failed'); resolve(false); });
        } catch (e) { log('HEAL', 'IPC recovery error: ' + e.message); resolve(false); }
        return;
      }
      // Health check
      http.get('http://127.0.0.1:9870/health', { timeout: 2000 }, (res) => {
        let body = '';
        res.on('data', d => body += d);
        res.on('end', () => {
          try { const j = JSON.parse(body); if (j.status === 'ok') { resolve(true); return; } } catch {}
          setTimeout(check, 1500);
        });
      }).on('error', () => setTimeout(check, 1500));
    };
    setTimeout(check, 2000); // initial delay for hot reload
  });
}

// ═══ 核心: 双写部署 (hot dir + install dir) ═══
function deployDual(quiet) {
  fs.mkdirSync(HOT_DIR, { recursive: true });
  const installDir = findInstallDir();
  let hotCount = 0, installCount = 0, totalBytes = 0;

  // 1. 源文件 → hot dir + install/src/
  for (const f of SRC_FILES) {
    const src = path.join(SRC_DIR, f);
    if (!fs.existsSync(src)) continue;
    const sz = fs.statSync(src).size;
    totalBytes += sz;
    // hot dir (即时热重载)
    fs.copyFileSync(src, path.join(HOT_DIR, f));
    hotCount++;
    // install dir (持久化)
    if (installDir) {
      copyOne(src, path.join(installDir, "src", f));
      installCount++;
    }
    if (!quiet) log("   ", `${f} (${(sz / 1024).toFixed(1)}KB)`);
  }

  // 2. media文件 → install/media/ (webview从安装目录加载)
  for (const f of MEDIA_FILES) {
    const src = path.join(MEDIA_DIR, f);
    if (!fs.existsSync(src)) continue;
    if (installDir) {
      copyOne(src, path.join(installDir, "media", f));
      installCount++;
    }
  }

  // 3. package.json → install/ (版本号等元数据)
  for (const f of EXTRA_FILES) {
    const src = path.join(PROJECT, f);
    if (!fs.existsSync(src)) continue;
    if (installDir) {
      copyOne(src, path.join(installDir, f));
      installCount++;
    }
  }

  // 4a. v16.0: 语法验证 — 部署前检查,防止坏代码杀死watcher
  const extHot = path.join(HOT_DIR, 'extension.js');
  if (fs.existsSync(extHot)) {
    const v = validateSyntax(extHot);
    if (!v.ok) {
      console.error('  ✗ SYNTAX ERROR in extension.js → .reload NOT written (watcher safe)');
      console.error('    ' + v.error);
      // Restore from backup if available
      const bak = extHot + '.bak';
      if (fs.existsSync(bak)) {
        fs.copyFileSync(bak, extHot);
        console.error('  ↻ Restored from backup');
      }
      return { hotCount, installCount, totalBytes, installDir, error: 'syntax: ' + v.error };
    }
  }

  // 4b. 原始完整性检查 (防止缺文件导致热重载失败 — 根因防护)
  const missing = SRC_FILES.filter(f => !fs.existsSync(path.join(HOT_DIR, f)));
  if (missing.length > 0) {
    console.error(`  ✗ ABORT: hot dir missing ${missing.join(', ')} — .reload NOT written`);
    return { hotCount, installCount, totalBytes, installDir, error: `missing: ${missing.join(', ')}` };
  }

  // 5. 触发热重载信号 (最后写, 确保所有文件已就位且验证通过)
  fs.writeFileSync(path.join(HOT_DIR, ".reload"), String(Date.now()));

  return { hotCount, installCount, totalBytes, installDir };
}

// ── Watch模式: 持续监听src/变更 → 自动双写+热重载 ──
if (isWatch) {
  log("WATCH", `Monitoring ${SRC_DIR} for changes...`);
  const r = deployDual(false);
  const installOk = r.installDir ? `install=${r.installCount}` : 'install=N/A';
  console.log(`\n  ✓ Initial: hot=${r.hotCount} ${installOk}. Watching...`);
  console.log("  ─ Save any src/ file → auto deploy+reload. Ctrl+C to stop.\n");

  let debounce = null;
  fs.watch(SRC_DIR, { persistent: true }, (ev, fn) => {
    if (!fn || !SRC_FILES.includes(fn)) return;
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => {
      debounce = null;
      const ts = new Date().toLocaleTimeString();
      const r = deployDual(true);
      const installOk = r.installDir ? `+install` : '';
      console.log(`  [${ts}] ${fn} → hot${installOk} · signal sent`);
    }, 400);
  });
  process.on("SIGINT", () => { console.log("\n  ✓ Watch stopped.\n"); process.exit(0); });
  return;
}

// ── 默认: 双写部署 (唯一需要的命令) ──
log("1/2", "双写部署: src/ → hot dir + install dir");
const result = deployDual(false);
log("2/2", "Signal sent → 热重载触发");

console.log("");
console.log("  ═══════════════════════════════════════════");
console.log(`  ✓ hot dir:     ${result.hotCount} files → ${HOT_DIR}`);
if (result.installDir) {
  console.log(`  ✓ install dir: ${result.installCount} files → ${path.basename(result.installDir)}`);
} else {
  console.log(`  ○ install dir: not found (仅热重载, 重启后需重新部署)`);
}
console.log(`  ✓ 总计 ${(result.totalBytes / 1024).toFixed(0)}KB · 即时生效 · 永不重载`);
console.log("  ═══════════════════════════════════════════");
console.log("");
// v16.0: 部署后自愈 — 探测Hub健康,失败时IPC恢复
if (!result.error) {
  autoHeal(10000).then(ok => {
    if (ok) console.log('  ✓ Hub健康确认 · 热传递链完整');
    else console.log('  ⚠ Hub未响应 · 请检查扩展状态');
  });
}
