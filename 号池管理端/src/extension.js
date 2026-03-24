/**
 * 号池管理端 v1.0.0 — 道之防·公网号池统管
 *
 * 道: 以本机为源, LAN为界, 管辖一切公网号池之资
 * 防: 分知加密·LAN锚定·设备绑定·反逆向·审计不灭
 *
 * 架构:
 *   管理Hub (:19881, LAN-only) -> 多云池统管
 *   LAN Guard -> 设备注册·会话管理·子网绑定
 *   Split-Knowledge -> admin_key = HMAC(stored_half, machine_identity)
 *   Hot Reload -> 薄壳+热模块·零重启部署
 */
const vscode = require('vscode');
const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');

// ═══ Hot Reload Shell (global持久化·零重启) ═══
const _G = global.__poolAdminHot = global.__poolAdminHot || {
  handlers: new Map(), registered: new Set(),
  viewRegistered: false, viewDelegate: null, cachedView: null,
  ctx: null, vscode: null, watcher: null, debounce: null,
  reloadCount: 0, hubServerRef: null, isHotReloading: false,
};
_G.vscode = _G.vscode || vscode;

function _proxyCmd(context, id, handler) {
  _G.handlers.set(id, handler);
  if (_G.registered.has(id)) return;
  _G.registered.add(id);
  context.subscriptions.push(
    vscode.commands.registerCommand(id, (...args) => {
      const h = _G.handlers.get(id);
      return h ? h(...args) : undefined;
    })
  );
}

function _proxyView(context, viewId, provider) {
  _G.viewDelegate = provider;
  if (_G.viewRegistered) return;
  _G.viewRegistered = true;
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(viewId, {
      resolveWebviewView(view, ctx, tok) {
        _G.cachedView = view;
        if (_G.viewDelegate) return _G.viewDelegate.resolveWebviewView(view, ctx, tok);
      }
    })
  );
}

// ═══ State ═══
let lanGuard, poolManager, adminPanel, statusBar, _hubServer, _out;
let _syncTimer = null;
const HOT_DIR = path.join(os.homedir(), '.pool-admin-hot');

function _log(msg) {
  const ts = new Date().toISOString().slice(11, 19);
  if (_out) _out.appendLine('[' + ts + '] ' + msg);
}

// ═══ Activate ═══
async function activate(context) {
  _G.ctx = _G.ctx || context;
  const ctx = _G.ctx;
  _out = _out || vscode.window.createOutputChannel('号池管理端');

  const cfg = vscode.workspace.getConfiguration('poolAdmin');
  const hubPort = cfg.get('hubPort', 19881);
  const subnets = cfg.get('trustedSubnets', ['192.168.0.0/16', '10.0.0.0/8']);
  const sessionTTL = cfg.get('sessionTTL', 900);
  const maxDevices = cfg.get('maxDevices', 5);

  // Init modules
  const { LANGuard } = require('./lanGuard');
  const { PoolManager } = require('./poolManager');
  const { AdminPanelProvider } = require('./adminPanel');

  lanGuard = new LANGuard({ trustedSubnets: subnets, sessionTTL, maxDevices });
  poolManager = new PoolManager();
  lanGuard.enrollSelf();

  adminPanel = new AdminPanelProvider(ctx, hubPort, lanGuard);
  adminPanel.setPoolManager(poolManager);
  _proxyView(ctx, 'pool-admin.dashboard', adminPanel);

  // Status bar
  statusBar = statusBar || vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 90);
  statusBar.text = '$(shield) 号池管理';
  statusBar.tooltip = '号池管理端 · LAN: ' + (lanGuard.getLanIp() || 'detecting...');
  statusBar.command = 'poolAdmin.openDashboard';
  statusBar.show();

  // Start Hub
  _startHub(hubPort);

  // Register commands
  _registerCommands(ctx, hubPort);

  // Hot reload watcher
  _setupHotReload(ctx);

  // Auto-sync timer
  if (cfg.get('autoSync', true)) {
    const interval = cfg.get('syncInterval', 300) * 1000;
    _syncTimer = setInterval(() => _autoSync(), interval);
  }

  _log('Activated. LAN=' + (lanGuard.getLanIp() || 'none') + ' Hub=:' + hubPort);
  _log('Machine ID: ' + require('./lanGuard').getMachineIdentity().slice(0, 12) + '...');
}

// ═══ Hub Server (LAN-only binding) ═══
function _startHub(port) {
  if (_G.hubServerRef) { _hubServer = _G.hubServerRef; return; }

  const lanIp = lanGuard.getLanIp();
  const bindHost = '127.0.0.1'; // Webview connects via localhost; LAN guard handles auth

  _hubServer = http.createServer((req, res) => {
    // Delegate entire handler to _G for hot-reloadable routing
    const handler = _G.hubHandler || _hubHandle;
    handler(req, res);
  });

  _hubServer.listen(port, bindHost, () => {
    _log('Hub: ' + bindHost + ':' + port + ' (LAN-only)');
    lanGuard.audit('HUB_START', bindHost, '', 'port ' + port);
  });
  _hubServer.on('error', e => {
    if (e.code === 'EADDRINUSE') _hubServer.listen(port + 1, bindHost);
    else _log('Hub error: ' + e.message);
  });
  _G.hubServerRef = _hubServer;
  _G.hubHandler = _hubHandle; // Set initial handler
}

// ═══ Hub Request Handler (fully hot-reloadable via _G.hubHandler) ═══
function _hubHandle(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type,X-Session,X-Nonce');
  if (req.method === 'OPTIONS') { res.writeHead(200); res.end(); return; }

  const url = (req.url || '').split('?')[0].replace(/\/+$/, '') || '/';
  const auth = lanGuard.authenticateRequest(req);

  // Public (LAN-only, no session needed)
  if (url === '/api/health') return _json(res, { ok: true, v: '1.0.0', lan: lanGuard.getStatus() });
  if (url === '/dashboard') return _serveDashboard(req, res);
  if (url === '/api/enroll' && req.method === 'POST') {
    if (!lanGuard.isLanIp(auth.ip)) return _json(res, { ok: false, error: 'LAN only' }, 403);
    return _readBody(req, body => {
      const fp = body.fingerprint || '';
      const r = lanGuard.enrollDevice(fp, body.name || '', auth.ip);
      if (r.ok || r.error === 'already enrolled') {
        const s = lanGuard.createSession(fp, auth.ip);
        return _json(res, { ok: true, fingerprint: fp, session: s.sessionId || '', expiresAt: s.expiresAt || '', existing: !r.ok });
      }
      _json(res, r);
    });
  }

  // Local relay (machine-HMAC auth, no LAN session needed)
  if (url.startsWith('/api/v1/')) return _relayRoute(req, res, url);

  // ── Localhost-trusted endpoints (Hub binds 127.0.0.1 only, no external access possible) ──
  // Activation & remote-connect: accessible without session for backward compat with pre-v15.0 clients
  if (url === '/api/activate-device' && req.method === 'POST') {
    return _readBody(req, async b => {
      if (!poolManager) return _json(res, { ok: false, error: 'not ready' }, 503);
      const { getMachineIdentity } = require('./lanGuard');
      const os = require('os');
      const mid = b.machineCode || getMachineIdentity();
      const pid = poolManager.getActivePoolId();
      if (!pid) return _json(res, { ok: false, error: 'no cloud pools configured' });
      try {
        const r = await poolManager._request(pid, 'POST', '/api/device/activate',
          { hwid: mid, name: os.hostname() }, true);
        if (lanGuard) lanGuard.audit('ACTIVATE_OPEN', auth.ip, '', 'activate: ' + mid.slice(0, 12));
        _json(res, r.ok ? { ok: true, activated: true, ...r.data } : { ok: false, error: r.data?.error || 'activation failed' });
      } catch (e) { _json(res, { ok: false, error: e.message }); }
    });
  }

  // Authenticated endpoints
  if (!auth.ok) return _json(res, { ok: false, error: auth.error }, auth.code || 403);
  _route(req, res, url, auth);
}

function _route(req, res, url, auth) {
  if (url === '/api/overview') {
    return poolManager.getAllOverviews()
      .then(d => _json(res, { ok: true, pools: d, lan: lanGuard.getStatus() }))
      .catch(e => _json(res, { ok: false, error: e.message }, 500));
  }
  if (url === '/api/pools') return _json(res, { ok: true, pools: poolManager.listPools() });
  if (url === '/api/pools/add' && req.method === 'POST') {
    return _readBody(req, b => {
      const r = poolManager.addPool(b.name, b.url, b.adminKeyHalf, b.hmacSecret);
      lanGuard.audit('POOL_ADD', auth.ip, auth.deviceFp, b.name || '');
      _json(res, r);
    });
  }
  if (url === '/api/pools/remove' && req.method === 'POST') {
    return _readBody(req, b => {
      const r = poolManager.removePool(b.poolId);
      lanGuard.audit('POOL_REMOVE', auth.ip, auth.deviceFp, b.poolId || '');
      _json(res, r);
    });
  }
  // Cloud pool device/P2P forwarding (must match before general pool action)
  const cm = url.match(/^\/api\/pools\/([^/]+)\/(cloud-devices|cloud-p2p|cloud-pool-enhanced)$/);
  if (cm) return _cloudForward(req, res, cm[1], cm[2], auth);
  // /api/pools/:id/:action
  const m = url.match(/^\/api\/pools\/([^/]+)\/(.+)$/);
  if (m) return _poolAction(req, res, m[1], m[2], auth);
  if (url === '/api/devices') return _json(res, { ok: true, devices: lanGuard.getDevices() });
  if (url === '/api/devices/revoke' && req.method === 'POST') {
    return _readBody(req, b => _json(res, lanGuard.revokeDevice(b.fingerprint)));
  }
  if (url === '/api/audit') {
    return _json(res, { ok: true, entries: lanGuard.getAuditLog(100) });
  }
  if (url === '/api/lan/status') return _json(res, { ok: true, ...lanGuard.getStatus() });

  // ── Push Directive routes ──
  if (url === '/api/push/list') {
    const pools = poolManager.listPools();
    if (!pools.length) return _json(res, { ok: false, error: 'no pools' });
    return poolManager.listDirectives(pools[0].id)
      .then(d => _json(res, d))
      .catch(e => _json(res, { ok: false, error: e.message }, 500));
  }
  if (url === '/api/push/create' && req.method === 'POST') {
    return _readBody(req, async b => {
      const pools = poolManager.listPools();
      if (!pools.length) return _json(res, { ok: false, error: 'no pools' });
      const r = await poolManager.pushDirective(pools[0].id, b).catch(e => ({ ok: false, error: e.message }));
      lanGuard.audit('PUSH_CREATE', auth.ip, auth.deviceFp, (b.type || '') + ':' + (r.directive_id || ''));
      _json(res, r);
    });
  }
  if (url === '/api/push/revoke' && req.method === 'POST') {
    return _readBody(req, async b => {
      const pools = poolManager.listPools();
      if (!pools.length) return _json(res, { ok: false, error: 'no pools' });
      const r = await poolManager.revokeDirective(pools[0].id, b.directiveId).catch(e => ({ ok: false, error: e.message }));
      lanGuard.audit('PUSH_REVOKE', auth.ip, auth.deviceFp, b.directiveId || '');
      _json(res, r);
    });
  }

  // ── Security routes ──
  if (url === '/api/security/events') {
    const pools = poolManager.listPools();
    if (!pools.length) return _json(res, { ok: false, error: 'no pools' });
    return poolManager.getSecurityEvents(pools[0].id)
      .then(d => _json(res, d))
      .catch(e => _json(res, { ok: false, error: e.message }, 500));
  }
  if (url === '/api/security/block' && req.method === 'POST') {
    return _readBody(req, async b => {
      const pools = poolManager.listPools();
      if (!pools.length) return _json(res, { ok: false, error: 'no pools' });
      const r = await poolManager.blockIp(pools[0].id, b.ip, b.action).catch(e => ({ ok: false, error: e.message }));
      lanGuard.audit('IP_BLOCK', auth.ip, auth.deviceFp, (b.action || 'block') + ':' + (b.ip || ''));
      _json(res, r);
    });
  }

  // ── Three-mode APIs: delegate to adminPanel (hot-reloadable) ──
  if (adminPanel && adminPanel.handleExtRoute) {
    const handled = adminPanel.handleExtRoute(req, res, url, auth, { json: _json, readBody: _readBody, G: _G });
    if (handled) return;
  }

  _json(res, { ok: false, error: 'not found' }, 404);
}

async function _poolAction(req, res, pid, act, auth) {
  try {
    if (act === 'overview') return _json(res, await poolManager.getOverview(pid));
    if (act === 'accounts') return _json(res, await poolManager.getAccounts(pid));
    if (act === 'users') return _json(res, await poolManager.getUsers(pid));
    if (act === 'payments') return _json(res, await poolManager.getPayments(pid));
    if (act === 'health') return _json(res, await poolManager.getHealth(pid));
    if (act === 'public') return _json(res, await poolManager.getPublicPool(pid));
    if (act === 'sync' && req.method === 'POST') {
      return _readBody(req, async b => {
        const r = await poolManager.syncAccounts(pid, b.accounts || []);
        lanGuard.audit('SYNC', auth.ip, auth.deviceFp, pid + ':' + (r.synced || 0));
        _json(res, r);
      });
    }
    if (act === 'confirm' && req.method === 'POST') {
      return _readBody(req, async b => {
        const r = await poolManager.confirmPayment(pid, b.paymentId);
        lanGuard.audit('CONFIRM', auth.ip, auth.deviceFp, b.paymentId || '');
        _json(res, r);
      });
    }
    if (act === 'reject' && req.method === 'POST') {
      return _readBody(req, async b => {
        const r = await poolManager.rejectPayment(pid, b.paymentId);
        lanGuard.audit('REJECT', auth.ip, auth.deviceFp, b.paymentId || '');
        _json(res, r);
      });
    }
    if (act === 'p2p-confirm' && req.method === 'POST') {
      return _readBody(req, async b => {
        const r = await poolManager.confirmP2POrder(pid, b.orderId || b.paymentId);
        lanGuard.audit('P2P_CONFIRM', auth.ip, auth.deviceFp, b.orderId || b.paymentId || '');
        _json(res, r);
      });
    }
    if (act === 'p2p-reject' && req.method === 'POST') {
      return _readBody(req, async b => {
        const r = await poolManager.rejectP2POrder(pid, b.orderId || b.paymentId, b.note);
        lanGuard.audit('P2P_REJECT', auth.ip, auth.deviceFp, b.orderId || b.paymentId || '');
        _json(res, r);
      });
    }
    if (act === 'p2p-create' && req.method === 'POST') {
      return _readBody(req, async b => {
        const r = await poolManager.createP2POrder(pid, b);
        lanGuard.audit('P2P_CREATE', auth.ip, auth.deviceFp, (b.device_id || '') + ':' + (b.w_credits || ''));
        _json(res, r);
      });
    }
    if (act === 'payment-stats') {
      return poolManager.getPaymentStats(pid)
        .then(d => _json(res, d))
        .catch(e => _json(res, { ok: false, error: e.message }, 500));
    }
    _json(res, { ok: false, error: 'unknown: ' + act }, 404);
  } catch (e) { _json(res, { ok: false, error: e.message }, 500); }
}

async function _cloudForward(req, res, pid, act, auth) {
  try {
    const apiMap = {
      'cloud-devices': 'getCloudDevices',
      'cloud-p2p': 'getCloudP2POrders',
      'cloud-pool-enhanced': 'getPublicPoolEnhanced',
    };
    const method = apiMap[act];
    if (!method || !poolManager[method]) return _json(res, { ok: false, error: 'unknown: ' + act }, 404);
    const r = await poolManager[method](pid);
    _json(res, r);
  } catch (e) { _json(res, { ok: false, error: e.message }, 500); }
}

// ═══ Local Relay Auth (machine-identity HMAC, no hardcoded secrets) ═══
// Both client and admin derive the same secret from hardware fingerprint.
// Secret = HMAC-SHA256(machineIdentity, 'wam-relay-v1') — never stored, never transmitted.
function _getLocalRelaySecret() {
  const { getMachineIdentity } = require('./lanGuard');
  return crypto.createHmac('sha256', getMachineIdentity()).update('wam-relay-v1').digest('hex');
}

function _verifyLocalRelay(req) {
  const ts = req.headers['x-ts'] || '';
  const nonce = req.headers['x-nc'] || '';
  const sig = req.headers['x-sg'] || '';
  if (!ts || !nonce || !sig) return { ok: false, error: 'missing auth' };
  const now = Math.floor(Date.now() / 1000);
  if (Math.abs(now - parseInt(ts, 10)) > 60) return { ok: false, error: 'clock skew' };
  const secret = _getLocalRelaySecret();
  const expected = crypto.createHmac('sha256', secret).update(ts + '.' + nonce).digest('hex');
  const { timingSafeEqual } = require('./lanGuard');
  if (!timingSafeEqual(sig, expected)) return { ok: false, error: 'invalid sig' };
  return { ok: true };
}

// ═══ /api/v1/* Relay Routes (obfuscated paths, ext client only) ═══
async function _relayRoute(req, res, url) {
  const auth = _verifyLocalRelay(req);
  if (!auth.ok) return _json(res, { ok: false, error: auth.error }, 401);
  if (!poolManager) return _json(res, { ok: false, error: 'not ready' }, 503);

  const devId = req.headers['x-di'] || '';
  const qs = (req.url || '').split('?')[1] || '';
  const params = new URLSearchParams(qs);

  if (url === '/api/v1/ping') {
    return poolManager.extHealth()
      .then(d => _json(res, d))
      .catch(e => _json(res, { ok: false, error: e.message }, 500));
  }
  if (url === '/api/v1/status') {
    return poolManager.extPool(devId)
      .then(d => _json(res, d))
      .catch(e => _json(res, { ok: false, error: e.message }, 500));
  }
  if (url === '/api/v1/acquire') {
    return poolManager.extPull(devId)
      .then(d => _json(res, d))
      .catch(e => _json(res, { ok: false, error: e.message }, 500));
  }
  if (url === '/api/v1/inject') {
    const email = params.get('e') || '';
    return poolManager.extPullBlob(devId, email || undefined)
      .then(d => _json(res, d))
      .catch(e => _json(res, { ok: false, error: e.message }, 500));
  }
  if (url === '/api/v1/signal' && req.method === 'POST') {
    return _readBody(req, async b => {
      const d = await poolManager.extHeartbeat(devId, b).catch(e => ({ ok: false, error: e.message }));
      _json(res, d);
    });
  }
  if (url === '/api/v1/report' && req.method === 'POST') {
    return _readBody(req, async b => {
      const d = await poolManager.extPush(devId, b).catch(e => ({ ok: false, error: e.message }));
      _json(res, d);
    });
  }
  if (url === '/api/v1/reclaim' && req.method === 'POST') {
    return _readBody(req, async b => {
      const d = await poolManager.extRelease(devId, b).catch(e => ({ ok: false, error: e.message }));
      _json(res, d);
    });
  }
  if (url === '/api/v1/metric') {
    return poolManager.extPoolEnhanced(devId)
      .then(d => _json(res, d))
      .catch(e => _json(res, { ok: false, error: e.message }, 500));
  }
  if (url === '/api/v1/activate' && req.method === 'POST') {
    return _readBody(req, async b => {
      const d = await poolManager.extActivateDevice(devId, b).catch(e => ({ ok: false, error: e.message }));
      _json(res, d);
    });
  }
  if (url === '/api/v1/remote-pending') {
    return poolManager.extRemotePending(devId)
      .then(d => _json(res, d))
      .catch(e => _json(res, { ok: false, error: e.message }, 500));
  }
  if (url === '/api/v1/remote-respond' && req.method === 'POST') {
    return _readBody(req, async b => {
      const d = await poolManager.extRemoteRespond(devId, b).catch(e => ({ ok: false, error: e.message }));
      _json(res, d);
    });
  }
  if (url === '/api/v1/me-status') {
    return poolManager.extDeviceStatus(devId)
      .then(d => _json(res, d))
      .catch(e => _json(res, { ok: false, device_activated: false, error: e.message }, 500));
  }
  // ── Payment: client creates/checks payment orders ──
  if (url === '/api/v1/pay-init' && req.method === 'POST') {
    return _readBody(req, async b => {
      const d = await poolManager.extPayInit(devId, b).catch(e => ({ ok: false, error: e.message }));
      if (lanGuard) lanGuard.audit('PAY_INIT', '127.0.0.1', devId, (d.order_id || '') + ' ' + (b.w_credits || ''));
      _json(res, d);
    });
  }
  if (url === '/api/v1/pay-status') {
    const oid = params.get('oid') || params.get('order_id') || '';
    return poolManager.extPayStatus(devId, oid)
      .then(d => _json(res, d))
      .catch(e => _json(res, { ok: false, error: e.message }, 500));
  }
  // ── Rate Limit Guard: client reports rate limit hit ──
  if (url === '/api/v1/rate-limit-report' && req.method === 'POST') {
    return _readBody(req, async b => {
      const d = await poolManager.reportRateLimit(devId, b).catch(e => ({ ok: false, error: e.message }));
      if (lanGuard) lanGuard.audit('RATE_LIMIT', '127.0.0.1', devId, (b.email || '') + ' → ' + (d.action || ''));
      _json(res, d);
    });
  }
  return _json(res, { ok: false, error: 'not found' }, 404);
}

// ═══ HTTP Helpers ═══
function _json(res, data, code) {
  const b = JSON.stringify(data);
  res.writeHead(code || 200, { 'Content-Type': 'application/json; charset=utf-8', 'Content-Length': Buffer.byteLength(b) });
  res.end(b);
}

function _readBody(req, cb) {
  const { MAX_BODY_BYTES } = require('./lanGuard');
  let d = '', size = 0;
  req.on('data', c => {
    size += c.length;
    if (size > MAX_BODY_BYTES) { req.destroy(); return; }
    d += c;
  });
  req.on('end', () => {
    if (size > MAX_BODY_BYTES) return;
    try { cb(d ? JSON.parse(d) : {}); } catch { cb({}); }
  });
}

function _serveDashboard(req, res) {
  const fp = path.join(__dirname, '..', 'media', 'dashboard.html');
  if (fs.existsSync(fp)) {
    const b = fs.readFileSync(fp);
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(b);
  } else {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end('<h3>Dashboard: install media/dashboard.html</h3>');
  }
}

// ═══ Commands ═══
function _registerCommands(ctx, hubPort) {
  _proxyCmd(ctx, 'poolAdmin.overview', async () => {
    const data = await poolManager.getAllStatus();
    const msg = data.map(p => (p.ok ? '\u2705' : '\u274C') + ' ' + p.name + ' (' + p.url + ')').join('\n');
    vscode.window.showInformationMessage('号池总览:\n' + msg);
  });

  _proxyCmd(ctx, 'poolAdmin.addPool', async () => {
    const name = await vscode.window.showInputBox({ prompt: '云池名称', placeHolder: 'e.g. 阿里云主池' });
    if (!name) return;
    const url = await vscode.window.showInputBox({ prompt: '云池URL', placeHolder: 'https://aiotvr.xyz/pool' });
    if (!url) return;
    const keyHalf = await vscode.window.showInputBox({ prompt: 'Admin Key半密钥 (分知加密, 可留空)', password: true });
    const hmac = await vscode.window.showInputBox({ prompt: 'HMAC Secret (可留空)', password: true });
    const r = poolManager.addPool(name, url, keyHalf || '', hmac || '');
    vscode.window.showInformationMessage(r.ok ? '\u2705 已添加: ' + name : '\u274C ' + (r.error || 'failed'));
    if (adminPanel) adminPanel.refresh();
  });

  _proxyCmd(ctx, 'poolAdmin.syncAll', async () => {
    const data = await poolManager.getAllStatus();
    vscode.window.showInformationMessage('\u2705 同步完成: ' + data.length + ' pools checked');
    if (adminPanel) adminPanel.refresh();
  });

  _proxyCmd(ctx, 'poolAdmin.enrollDevice', async () => {
    const fp = await vscode.window.showInputBox({ prompt: '设备指纹 (24位hex)' });
    if (!fp) return;
    const name = await vscode.window.showInputBox({ prompt: '设备名称' });
    const r = lanGuard.enrollDevice(fp, name || '', '');
    vscode.window.showInformationMessage(r.ok ? '\u2705 设备已注册' : '\u274C ' + r.error);
  });

  _proxyCmd(ctx, 'poolAdmin.revokeDevice', async () => {
    const devs = lanGuard.getDevices();
    if (devs.length === 0) { vscode.window.showInformationMessage('无注册设备'); return; }
    const pick = await vscode.window.showQuickPick(
      devs.map(d => ({ label: d.name, description: d.fingerprint.slice(0, 12) + '...', fp: d.fingerprint })),
      { placeHolder: '选择要撤销的设备' }
    );
    if (pick) { lanGuard.revokeDevice(pick.fp); vscode.window.showInformationMessage('\u2705 已撤销'); }
  });

  _proxyCmd(ctx, 'poolAdmin.auditLog', () => {
    const entries = lanGuard.getAuditLog(50);
    _out.clear();
    entries.forEach(e => _out.appendLine(e.ts + ' [' + e.action + '] ' + e.ip + ' ' + e.detail));
    _out.show();
  });

  _proxyCmd(ctx, 'poolAdmin.openDashboard', () => {
    if (adminPanel) adminPanel.refresh();
    vscode.commands.executeCommand('pool-admin.dashboard.focus');
  });

  _proxyCmd(ctx, 'poolAdmin.lanStatus', () => {
    const s = lanGuard.getStatus();
    vscode.window.showInformationMessage(
      'LAN: ' + (s.lanIp || 'none') + ' | Devices: ' + s.enrolledDevices +
      ' | Sessions: ' + s.activeSessions + ' | Audit: ' + s.auditEntries
    );
  });

  _proxyCmd(ctx, 'poolAdmin.hotReload', () => _triggerHotReload());
  _proxyCmd(ctx, 'poolAdmin.hotStatus', () => {
    vscode.window.showInformationMessage('Hot Reload #' + _G.reloadCount + ' | Dir: ' + HOT_DIR);
  });
}

// ═══ Hot Reload ═══
function _setupHotReload(ctx) {
  if (_G.watcher) return;
  try {
    fs.mkdirSync(HOT_DIR, { recursive: true });
    _G.watcher = fs.watch(HOT_DIR, (ev, fn) => {
      if (fn === '.reload') {
        if (_G.debounce) clearTimeout(_G.debounce);
        _G.debounce = setTimeout(() => _triggerHotReload(), 500);
      }
    });
  } catch { /* hot dir not available */ }
}

function _triggerHotReload() {
  _G.isHotReloading = true;
  _G.reloadCount++;
  _log('Hot reload #' + _G.reloadCount);

  // Clear module cache for our modules (including extension.js for route updates)
  const srcDir = path.join(__dirname);
  const selfPath = __filename;
  Object.keys(require.cache).forEach(k => {
    if (k.startsWith(srcDir) && k !== selfPath) delete require.cache[k];
  });

  // Re-require and re-activate
  try {
    const { LANGuard } = require('./lanGuard');
    const { PoolManager } = require('./poolManager');
    const { AdminPanelProvider } = require('./adminPanel');

    // Dispose old instances (stops timers, saves state to disk)
    if (lanGuard) lanGuard.dispose();
    if (poolManager) poolManager.dispose();

    // New instances auto-load persisted state from disk (pools.enc, lan_guard.enc)
    lanGuard = new LANGuard({
      trustedSubnets: vscode.workspace.getConfiguration('poolAdmin').get('trustedSubnets', ['192.168.0.0/16', '10.0.0.0/8']),
    });
    poolManager = new PoolManager();
    lanGuard.enrollSelf();

    const hubPort = vscode.workspace.getConfiguration('poolAdmin').get('hubPort', 19881);
    adminPanel = new AdminPanelProvider(_G.ctx, hubPort, lanGuard);
    adminPanel.setPoolManager(poolManager);
    _G.viewDelegate = adminPanel;

    // Update hub handler in _G so Hub server uses latest routing (full hot-reload)
    _G.hubHandler = _hubHandle;

    if (_G.cachedView) adminPanel.resolveWebviewView(_G.cachedView, null, null);
    _log('Hot reload complete. Pools=' + poolManager.listPools().length);
  } catch (e) {
    _log('Hot reload error: ' + e.message);
  }
  _G.isHotReloading = false;
}

async function _autoSync() {
  try {
    const pools = poolManager.listPools();
    for (const p of pools) { await poolManager.getHealth(p.id); }
    _log('Auto-sync: ' + pools.length + ' pools checked');
  } catch { /* silent */ }
}

// ═══ Deactivate ═══
function deactivate() {
  if (_G.isHotReloading) return;
  if (_syncTimer) { clearInterval(_syncTimer); _syncTimer = null; }
  if (lanGuard) lanGuard.dispose();
  if (poolManager) poolManager.dispose();
  if (_hubServer && !_G.isHotReloading) {
    _hubServer.close();
    _G.hubServerRef = null;
  }
  if (_G.watcher) { _G.watcher.close(); _G.watcher = null; }
}

module.exports = { activate, deactivate };
