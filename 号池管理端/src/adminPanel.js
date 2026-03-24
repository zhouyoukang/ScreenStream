/**
 * Admin Panel - Webview管理面板
 * 全局总览·多池管理·设备授权·安全审计
 * HTML模板外置于media/panel.html, 交互逻辑在media/admin.js
 */
const vscode = require('vscode');
const path = require('path');
const http = require('http');
const crypto = require('crypto');
const fs = require('fs');

class AdminPanelProvider {
  constructor(context, hubPort, lanGuard) {
    this._context = context;
    this._hubPort = hubPort;
    this._lanGuard = lanGuard;
    this._poolManager = null;
    this._view = null;
    this._sessionId = null;
    // Clean up stale _patchHubHandler interceptor listeners from previous versions.
    // The old code added extra 'request' listeners that bypass the main handler.
    // After hot reload, only the main delegate handler should remain.
    this._cleanupStaleListeners();
  }

  _cleanupStaleListeners() {
    const G = global.__poolAdminHot;
    if (!G || !G.hubServerRef) return;
    const server = G.hubServerRef;
    // Unconditionally rebuild: replace ALL listeners with one clean delegate.
    // This ensures no stale interceptors survive across hot reloads.
    server.removeAllListeners('request');
    server.on('request', (req, res) => {
      const handler = G.hubHandler;
      if (handler) handler(req, res);
      else { res.writeHead(503); res.end('not ready'); }
    });
  }

  setPoolManager(pm) { this._poolManager = pm; }

  resolveWebviewView(view, ctx, tok) {
    this._view = view;
    view.webview.options = { enableScripts: true, localResourceRoots: [
      vscode.Uri.file(path.join(this._context.extensionPath, 'media'))
    ]};
    const sess = this._lanGuard.createSelfSession();
    this._sessionId = sess.ok ? sess.sessionId : '';
    view.webview.html = this._getHtml(view.webview);
    view.webview.onDidReceiveMessage(msg => this._onMessage(msg));
  }

  async _onMessage(msg) {
    if (!this._view) return;
    const { command, data } = msg;
    try {
      const resp = await this._hubRequest(command, data);
      this._view.webview.postMessage({ command: command + '_result', data: resp });
    } catch (e) {
      this._view.webview.postMessage({
        command: command + '_result',
        data: { ok: false, error: e.message }
      });
    }
  }

  _hubRequest(action, data) {
    return new Promise((resolve, reject) => {
      const isPost = ['addPool', 'removePool', 'syncAccounts',
        'confirmPayment', 'rejectPayment', 'enrollDevice', 'revokeDevice',
        'activateDevice', 'remoteConnect', 'remoteProbe', 'setStrategy',
        'pushCreate', 'pushRevoke', 'securityBlock', 'remoteRequest',
        'rateLimitConfig', 'rateLimitClear', 'rateLimitTrigger',
        'confirmP2P', 'rejectP2P', 'createP2P'
      ].includes(action);
      const pid = (data && data.poolId) || '';
      const pathMap = {
        overview: '/api/overview',
        pools: '/api/pools',
        addPool: '/api/pools/add',
        removePool: '/api/pools/remove',
        poolDetail: '/api/pools/' + pid + '/overview',
        poolAccounts: '/api/pools/' + pid + '/accounts',
        poolUsers: '/api/pools/' + pid + '/users',
        poolPayments: '/api/pools/' + pid + '/payments',
        poolHealth: '/api/pools/' + pid + '/health',
        poolPublic: '/api/pools/' + pid + '/public',
        syncAccounts: '/api/pools/' + pid + '/sync',
        confirmPayment: '/api/pools/' + pid + '/confirm',
        rejectPayment: '/api/pools/' + pid + '/reject',
        confirmP2P: '/api/p2p/confirm',
        rejectP2P: '/api/p2p/reject',
        createP2P: '/api/p2p/create',
        paymentStats: '/api/payment-stats',
        devices: '/api/devices',
        enrollDevice: '/api/enroll',
        revokeDevice: '/api/devices/revoke',
        audit: '/api/audit',
        lanStatus: '/api/lan/status',
        cloudDevices: '/api/pools/' + pid + '/cloud-devices',
        cloudP2P: '/api/pools/' + pid + '/cloud-p2p',
        cloudPoolEnhanced: '/api/pools/' + pid + '/cloud-pool-enhanced',
        machineInfo: '/api/machine-info',
        cloudStatus: '/api/cloud-status',
        activateDevice: '/api/activate-device',
        remoteConnect: '/api/remote-connect',
        remoteProbe: '/api/remote-probe',
        setStrategy: '/api/set-strategy',
        pushList: '/api/push/list',
        pushCreate: '/api/push/create',
        pushRevoke: '/api/push/revoke',
        securityEvents: '/api/security/events',
        securityBlock: '/api/security/block',
        remoteRequest: '/api/remote/request',
        remoteStatus: '/api/remote/status' + (data && data.requestId ? '?requestId=' + data.requestId : ''),
        remoteDevices: '/api/remote/devices',
        rateLimitStatus: '/api/ratelimit/status',
        rateLimitConfig: '/api/ratelimit/config',
        rateLimitClear: '/api/ratelimit/clear',
        rateLimitTrigger: '/api/ratelimit/trigger-switch',
      };
      const apiPath = pathMap[action] || '/api/health';
      const bodyStr = isPost && data ? JSON.stringify(data) : null;
      const opts = {
        hostname: '127.0.0.1', port: this._hubPort,
        path: apiPath, method: isPost ? 'POST' : 'GET',
        headers: {
          'Content-Type': 'application/json',
          'X-Session': this._sessionId || '',
        },
        timeout: 30000,
      };
      if (bodyStr) opts.headers['Content-Length'] = Buffer.byteLength(bodyStr);
      const req = http.request(opts, (res) => {
        let d = '';
        res.on('data', c => d += c);
        res.on('end', () => {
          try { resolve(JSON.parse(d)); }
          catch { resolve({ ok: false, error: 'parse error' }); }
        });
      });
      req.on('error', e => reject(e));
      req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
      if (bodyStr) req.write(bodyStr);
      req.end();
    });
  }

  refresh() {
    if (this._view) {
      const sess = this._lanGuard.createSelfSession();
      this._sessionId = sess.ok ? sess.sessionId : this._sessionId;
      this._view.webview.html = this._getHtml(this._view.webview);
    }
  }

  _getHtml(webview) {
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.file(path.join(this._context.extensionPath, 'media', 'admin.js'))
    );
    const nonce = crypto.randomBytes(16).toString('hex');
    // Try to load external HTML template
    const tplPath = path.join(this._context.extensionPath, 'media', 'panel.html');
    if (fs.existsSync(tplPath)) {
      let html = fs.readFileSync(tplPath, 'utf-8');
      html = html.replace(/\$\{nonce\}/g, nonce);
      html = html.replace(/\$\{scriptUri\}/g, scriptUri.toString());
      return html;
    }
    // Fallback minimal HTML
    return this._getFallbackHtml(nonce, scriptUri);
  }

  _getFallbackHtml(nonce, scriptUri) {
    return [
      '<!DOCTYPE html><html><head><meta charset="UTF-8">',
      '<meta http-equiv="Content-Security-Policy" ',
      "content=\"default-src 'none'; style-src 'unsafe-inline'; ",
      "script-src 'nonce-" + nonce + "';\">",
      '<style>',
      ':root{--bg:#1e1e2e;--s:#282840;--p:#7c3aed;--ok:#10b981;',
      '--w:#f59e0b;--d:#ef4444;--t:#e2e8f0;--m:#94a3b8;--b:#374151}',
      '*{margin:0;padding:0;box-sizing:border-box}',
      'body{font-family:system-ui;background:var(--bg);color:var(--t);',
      'font-size:13px;padding:12px}',
      '.c{background:var(--s);border-radius:8px;padding:12px;',
      'margin-bottom:10px;border:1px solid var(--b)}',
      'h2{color:var(--p);font-size:15px;margin-bottom:8px}',
      'button{padding:6px 14px;border-radius:6px;border:none;',
      'cursor:pointer;font-size:12px;font-weight:600;',
      'background:var(--p);color:#fff}',
      'button:hover{opacity:.9}',
      '#content{min-height:200px}',
      '.loading{text-align:center;padding:20px;color:var(--m)}',
      '</style></head><body>',
      '<h2>&#x2618; 号池管理端</h2>',
      '<div id="content"><div class="loading">加载中...</div></div>',
      '<script nonce="' + nonce + '" src="' + scriptUri + '"></script>',
      '</body></html>',
    ].join('\n');
  }

  // ═══ Hot-reloadable three-mode API routes ═══
  // Called from extension.js _route before 404. Returns true if handled.
  handleExtRoute(req, res, url, auth, helpers) {
    const { json, readBody, G } = helpers;
    const os = require('os');
    const { getMachineIdentity } = require('./lanGuard');
    const pm = this._poolManager;
    const lg = this._lanGuard;

    if (url === '/api/machine-info') {
      const mid = getMachineIdentity();
      json(res, { ok: true, fullMachineId: mid, shortId: mid.slice(0, 12) + '...',
        hostname: os.hostname(), platform: os.platform(), arch: os.arch() });
      return true;
    }
    if (url === '/api/cloud-status') {
      this._getCloudStatus(res, json);
      return true;
    }
    if (url === '/api/activate-device' && req.method === 'POST') {
      readBody(req, async b => {
        const mid = b.machineCode || getMachineIdentity();
        lg.audit('ACTIVATE', auth.ip, auth.deviceFp, 'activate: ' + mid.slice(0, 12));
        const pools = pm ? pm.listPools() : [];
        if (pools.length === 0) return json(res, { ok: false, error: 'no cloud pools configured' });
        try {
          const r = await pm._request(pools[0].id, 'POST', '/api/device/activate',
            { hwid: mid, name: os.hostname() }, true);
          json(res, r.ok ? { ok: true, activated: true, ...r.data } : { ok: false, error: r.data?.error || 'activation failed' });
        } catch (e) { json(res, { ok: false, error: e.message }); }
      });
      return true;
    }
    if (url === '/api/remote-connect' && req.method === 'POST') {
      readBody(req, async b => {
        const target = b.targetMachineCode || '';
        lg.audit('REMOTE_CONNECT', auth.ip, auth.deviceFp, 'target: ' + target.slice(0, 12));
        const pools = pm ? pm.listPools() : [];
        if (pools.length === 0) return json(res, { ok: false, error: 'no cloud pools' });
        try {
          const r = await pm._request(pools[0].id, 'POST', '/api/admin/remote-connect',
            { target_hwid: target }, true);
          json(res, r.ok ? { ok: true, ...r.data } : { ok: false, error: r.data?.error || 'connect failed' });
        } catch (e) { json(res, { ok: false, error: e.message }); }
      });
      return true;
    }
    if (url === '/api/remote-probe' && req.method === 'POST') {
      readBody(req, async b => {
        const target = b.targetMachineCode || '';
        const pools = pm ? pm.listPools() : [];
        if (pools.length === 0) return json(res, { ok: false, error: 'no cloud pools' });
        try {
          const r = await pm._request(pools[0].id, 'GET',
            '/api/admin/device-status?hwid=' + encodeURIComponent(target), null, true);
          json(res, r.ok ? { ok: true, ...r.data } : { ok: false, error: r.data?.error || 'probe failed' });
        } catch (e) { json(res, { ok: false, error: e.message }); }
      });
      return true;
    }
    if (url === '/api/set-strategy' && req.method === 'POST') {
      readBody(req, b => {
        const strategy = b.strategy || 'local-first';
        lg.audit('STRATEGY', auth.ip, auth.deviceFp, 'set: ' + strategy);
        G.consumptionStrategy = strategy;
        json(res, { ok: true, strategy });
      });
      return true;
    }
    // ── Remote Management (道之安全 · 客户端必须授权) ──
    if (url === '/api/remote/request' && req.method === 'POST') {
      readBody(req, b => {
        if (!b.targetDeviceId || !b.action) return json(res, { ok: false, error: 'targetDeviceId and action required' });
        const allowed = ['diagnose', 'config_check', 'cache_clear', 'plugin_status', 'network_test', 'reset_binding', 'custom'];
        if (!allowed.includes(b.action)) return json(res, { ok: false, error: 'invalid action: ' + b.action + '. allowed: ' + allowed.join(',') });
        const mid = getMachineIdentity();
        const r = pm.createRemoteRequest(b.targetDeviceId, mid.slice(0, 16), b.action, b.payload || {});
        lg.audit('REMOTE_REQUEST', auth.ip, auth.deviceFp, 'target:' + b.targetDeviceId.slice(0, 12) + ' action:' + b.action);
        json(res, r);
      });
      return true;
    }
    if (url === '/api/remote/status') {
      const reqId = (req.url || '').split('requestId=')[1] || '';
      if (!reqId) return json(res, { ok: false, error: 'requestId required' }), true;
      const r = pm.getRemoteRequestStatus(reqId);
      json(res, r);
      return true;
    }
    if (url === '/api/remote/devices') {
      // Aggregate cloud devices + their remote access status
      this._getRemoteDevices(res, json);
      return true;
    }
    // ── Rate Limit Guard (道之防·限流防护) ──
    if (url === '/api/ratelimit/status') {
      const r = pm.getRateLimitStatus();
      json(res, r);
      return true;
    }
    if (url === '/api/ratelimit/config' && req.method === 'POST') {
      readBody(req, b => {
        const r = pm.setRateLimitConfig(b);
        lg.audit('RL_CONFIG', auth.ip, auth.deviceFp, JSON.stringify(b).slice(0, 80));
        json(res, r);
      });
      return true;
    }
    if (url === '/api/ratelimit/clear' && req.method === 'POST') {
      readBody(req, b => {
        const r = pm.clearCooldown(b.email || 'all');
        lg.audit('RL_CLEAR', auth.ip, auth.deviceFp, b.email || 'all');
        json(res, r);
      });
      return true;
    }
    if (url === '/api/ratelimit/trigger-switch' && req.method === 'POST') {
      readBody(req, async b => {
        const r = await pm.reportRateLimit(b.deviceId || 'admin', {
          email: b.email || '', traceId: 'manual-' + Date.now(),
          dPercent: b.dPercent || 0, wPercent: b.wPercent || 0,
        }).catch(e => ({ ok: false, error: e.message }));
        lg.audit('RL_MANUAL_SWITCH', auth.ip, auth.deviceFp, (b.email || '') + ' → ' + (r.action || ''));
        json(res, r);
      });
      return true;
    }
    // ── P2P Payment admin routes (hot-reloadable via handleExtRoute) ──
    if (url === '/api/p2p/confirm' && req.method === 'POST') {
      readBody(req, async b => {
        const pid2 = b.poolId || (pm.listPools()[0] || {}).id || '';
        if (!pid2) return json(res, { ok: false, error: 'no pool' });
        const r = await pm.confirmP2POrder(pid2, b.orderId || b.paymentId).catch(e => ({ ok: false, error: e.message }));
        lg.audit('P2P_CONFIRM', auth.ip, auth.deviceFp, b.orderId || b.paymentId || '');
        json(res, r);
      });
      return true;
    }
    if (url === '/api/p2p/reject' && req.method === 'POST') {
      readBody(req, async b => {
        const pid2 = b.poolId || (pm.listPools()[0] || {}).id || '';
        if (!pid2) return json(res, { ok: false, error: 'no pool' });
        const r = await pm.rejectP2POrder(pid2, b.orderId || b.paymentId, b.note).catch(e => ({ ok: false, error: e.message }));
        lg.audit('P2P_REJECT', auth.ip, auth.deviceFp, b.orderId || b.paymentId || '');
        json(res, r);
      });
      return true;
    }
    if (url === '/api/p2p/create' && req.method === 'POST') {
      readBody(req, async b => {
        const pid2 = b.poolId || (pm.listPools()[0] || {}).id || '';
        if (!pid2) return json(res, { ok: false, error: 'no pool' });
        const r = await pm.createP2POrder(pid2, b).catch(e => ({ ok: false, error: e.message }));
        lg.audit('P2P_CREATE', auth.ip, auth.deviceFp, (b.device_id || '') + ':' + (b.w_credits || ''));
        json(res, r);
      });
      return true;
    }
    if (url === '/api/payment-stats') {
      (async () => {
        const pid2 = (pm.listPools()[0] || {}).id || '';
        if (!pid2) return json(res, { ok: false, error: 'no pool' });
        const r = await pm.getPaymentStats(pid2).catch(e => ({ ok: false, error: e.message }));
        json(res, r);
      })();
      return true;
    }
    // ── Client payment relay (session-auth, localhost-only) ──
    if (url === '/api/relay/pay-init' && req.method === 'POST') {
      readBody(req, async b => {
        const devId = b.device_id || '';
        const r = await pm.extPayInit(devId, b).catch(e => ({ ok: false, error: e.message }));
        lg.audit('PAY_INIT', auth.ip, auth.deviceFp, (r.order_id || '') + ' ' + (b.w_credits || ''));
        json(res, r);
      });
      return true;
    }
    if (url.startsWith('/api/relay/pay-status')) {
      const oid = (req.url || '').split('oid=')[1]?.split('&')[0] || '';
      const devId = (req.url || '').split('device_id=')[1]?.split('&')[0] || '';
      pm.extPayStatus(devId, oid)
        .then(r => json(res, r))
        .catch(e => json(res, { ok: false, error: e.message }));
      return true;
    }
    return false; // not handled
  }

  async _getRemoteDevices(res, json) {
    const pm = this._poolManager;
    try {
      const pools = pm ? pm.listPools() : [];
      if (pools.length === 0) return json(res, { ok: false, error: 'no cloud pools' });
      const allDevices = [];
      for (const p of pools) {
        try {
          const devs = await pm.getCloudDevices(p.id);
          if (devs && devs.ok && devs.devices) {
            devs.devices.forEach(d => {
              const store = pm._getRemoteStore();
              const queue = store.get(d.hwid) || [];
              const pending = queue.filter(r => r.status === 'pending').length;
              const lastApproved = queue.filter(r => r.status === 'approved').sort((a, b) => (b.response?.respondedAt || 0) - (a.response?.respondedAt || 0))[0];
              allDevices.push({
                ...d, poolName: p.name, poolId: p.id,
                remotePending: pending,
                lastRemoteApproved: lastApproved ? lastApproved.response.respondedAt : null,
              });
            });
          }
        } catch { /* pool offline */ }
      }
      json(res, { ok: true, devices: allDevices });
    } catch (e) { json(res, { ok: false, error: e.message }, 500); }
  }

  async _getCloudStatus(res, json) {
    const pm = this._poolManager;
    const { getMachineIdentity } = require('./lanGuard');
    try {
      const pools = pm ? pm.listPools() : [];
      if (pools.length === 0) return json(res, { ok: false, error: 'no cloud pools' });
      let totalW = 0, availW = 0, totalDevices = 0, totalUsers = 0;
      let activeUsers = 0, todayCalls = 0, myW = 100, myWUsed = 0;
      let deviceActivated = false, urgent = 0, expiring = 0, dPercent = 0;
      for (const p of pools) {
        try {
          const enh = await pm.getPublicPoolEnhanced(p.id);
          if (enh && enh.ok) {
            if (enh.pool) totalW += enh.pool.total_w || 0;
            if (enh.w_resource) { availW += enh.w_resource.available_w || 0; totalDevices += enh.w_resource.devices || 0; }
            if (enh.stats) { totalUsers += enh.stats.total_users || 0; activeUsers += enh.stats.active_users || 0; todayCalls += enh.stats.today_calls || 0; }
          }
          const overview = await pm.getOverview(p.id);
          if (overview && overview.ok && overview.pool) {
            dPercent += overview.pool.available ? Math.round(overview.pool.available / (overview.pool.total || 1) * 100) : 0;
            urgent += overview.pool.urgent || 0; expiring += overview.pool.expiring || 0;
          }
        } catch { /* pool offline */ }
      }
      const mid = getMachineIdentity();
      for (const p of pools) {
        try {
          const devs = await pm.getCloudDevices(p.id);
          if (devs && devs.ok && devs.devices) {
            const myDev = devs.devices.find(d => d.hwid === mid || (d.hwid && mid.startsWith(d.hwid)));
            if (myDev) { deviceActivated = true; myW = myDev.w_total || 100; myWUsed = (myDev.w_total || 100) - (myDev.w_available || 100); }
          }
        } catch { /* */ }
      }
      json(res, { ok: true, d_percent: dPercent || 100, w_percent: totalW || availW || 100, w_available: availW || 100,
        total_devices: totalDevices, total_users: totalUsers, active_users: activeUsers, today_calls: todayCalls,
        device_activated: deviceActivated, my_w: myW, my_w_used: myWUsed, urgent, expiring,
        pools_count: pools.length, strategy: (global.__poolAdminHot || {}).consumptionStrategy || 'local-first',
        machine_code: mid, machine_code_short: mid.slice(0, 16) });
    } catch (e) { json(res, { ok: false, error: e.message }, 500); }
  }

  dispose() { this._view = null; }
}

module.exports = { AdminPanelProvider };
