/**
 * Pool Manager — 多池统管·分知加密
 *
 * 分知加密: admin_key = HMAC(stored_half, machine_identity)
 *   即使配置文件被窃, 无本机身份无法还原完整密钥
 * Outbound-only: 管理Hub从不暴露admin key, 仅向云池发出请求
 * 多池: 同时管理多个cloud_pool_server.py实例
 */
const crypto = require('crypto');
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { getMachineIdentity } = require('./lanGuard');

class PoolManager {
  constructor(options = {}) {
    this._configDir = options.configDir || path.join(os.homedir(), '.pool-admin');
    this._pools = new Map();
    this._loadPools();
  }

  // Split-Knowledge: admin_key = HMAC(stored_half, machine_identity)
  // Direct mode: if stored_half starts with 'DIRECT:', use the key as-is (no HMAC)
  _deriveAdminKey(storedHalf) {
    if (!storedHalf) return '';
    if (storedHalf.startsWith('DIRECT:')) return storedHalf.slice(7);
    return crypto.createHmac('sha256', getMachineIdentity())
      .update(storedHalf).digest('hex');
  }

  _signHeaders(hmacSecret, bodyBytes) {
    const headers = {};
    if (!hmacSecret) return headers;
    const ts = Math.floor(Date.now() / 1000).toString();
    const nonce = crypto.randomBytes(8).toString('hex');
    const msg = ts + '.' + nonce + '.' + (bodyBytes ? bodyBytes.toString() : '');
    headers['X-Timestamp'] = ts;
    headers['X-Nonce'] = nonce;
    headers['X-Signature'] = crypto.createHmac('sha256', hmacSecret).update(msg).digest('hex');
    return headers;
  }

  _request(poolId, method, apiPath, body, useAdmin, deviceId) {
    const pool = this._pools.get(poolId);
    if (!pool) return Promise.reject(new Error('pool not found: ' + poolId));
    return new Promise((resolve, reject) => {
      const fullUrl = pool.url.replace(/\/+$/, '') + apiPath;
      const u = new URL(fullUrl);
      const isHttps = u.protocol === 'https:';
      const bodyStr = body ? JSON.stringify(body) : null;
      const bodyBuf = bodyStr ? Buffer.from(bodyStr) : null;
      const hdrs = { 'Content-Type': 'application/json' };
      if (useAdmin) hdrs['X-Admin-Key'] = this._deriveAdminKey(pool.adminKeyHalf);
      if (pool.hmacSecret) Object.assign(hdrs, this._signHeaders(pool.hmacSecret, bodyBuf));
      if (deviceId) hdrs['X-Device-Id'] = deviceId;
      if (bodyBuf) hdrs['Content-Length'] = bodyBuf.length;
      const opts = {
        hostname: u.hostname, port: u.port || (isHttps ? 443 : 80),
        path: u.pathname + u.search, method, headers: hdrs, timeout: 30000,
      };
      const lib = isHttps ? https : http;
      const req = lib.request(opts, (res) => {
        let data = '';
        res.on('data', c => data += c);
        res.on('end', () => {
          try { resolve({ ok: res.statusCode === 200, status: res.statusCode, data: JSON.parse(data) }); }
          catch { resolve({ ok: false, status: res.statusCode, data: { error: 'parse_error' } }); }
        });
      });
      req.on('error', e => reject(e));
      req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
      if (bodyBuf) req.write(bodyBuf);
      req.end();
    });
  }

  // Persistence (encrypted with machine secret)
  _encrypt(text) {
    const key = crypto.scryptSync(getMachineIdentity().slice(0, 32), 'pool-salt', 32);
    const iv = crypto.randomBytes(16);
    const cipher = crypto.createCipheriv('aes-256-cbc', key, iv);
    let enc = cipher.update(text, 'utf8', 'hex');
    enc += cipher.final('hex');
    return iv.toString('hex') + ':' + enc;
  }

  _decrypt(text) {
    try {
      const [ivHex, enc] = text.split(':');
      const key = crypto.scryptSync(getMachineIdentity().slice(0, 32), 'pool-salt', 32);
      const iv = Buffer.from(ivHex, 'hex');
      const decipher = crypto.createDecipheriv('aes-256-cbc', key, iv);
      let dec = decipher.update(enc, 'hex', 'utf8');
      dec += decipher.final('utf8');
      return dec;
    } catch { return null; }
  }

  _getPoolsPath() { return path.join(this._configDir, 'pools.enc'); }

  _loadPools() {
    try {
      fs.mkdirSync(this._configDir, { recursive: true });
      const fp = this._getPoolsPath();
      if (!fs.existsSync(fp)) return;
      const data = this._decrypt(fs.readFileSync(fp, 'utf-8'));
      if (!data) return;
      const obj = JSON.parse(data);
      if (obj.pools) {
        for (const [k, v] of Object.entries(obj.pools)) this._pools.set(k, v);
      }
    } catch { /* first run */ }
  }

  _savePools() {
    try {
      const obj = { pools: Object.fromEntries(this._pools), ts: new Date().toISOString() };
      fs.mkdirSync(this._configDir, { recursive: true });
      fs.writeFileSync(this._getPoolsPath(), this._encrypt(JSON.stringify(obj)), 'utf-8');
    } catch { /* non-critical */ }
  }

  // Pool CRUD
  addPool(name, url, adminKeyHalf, hmacSecret) {
    if (!name || typeof name !== 'string' || name.trim().length === 0) {
      return { ok: false, error: '池名称不能为空' };
    }
    if (!url || typeof url !== 'string') {
      return { ok: false, error: 'URL不能为空' };
    }
    // Validate URL format
    const cleanUrl = url.trim().replace(/\/+$/, '');
    try {
      const u = new URL(cleanUrl);
      if (!['http:', 'https:'].includes(u.protocol)) {
        return { ok: false, error: 'URL必须使用http或https协议' };
      }
    } catch {
      return { ok: false, error: 'URL格式无效' };
    }
    // Sanitize name (strip HTML/script tags)
    const cleanName = name.trim().replace(/<[^>]*>/g, '').slice(0, 100);
    const id = 'pool_' + crypto.randomBytes(4).toString('hex');
    this._pools.set(id, {
      name: cleanName, url: cleanUrl, adminKeyHalf: adminKeyHalf || '',
      hmacSecret: hmacSecret || '', addedAt: new Date().toISOString(),
      lastSync: null, status: 'unknown',
    });
    this._savePools();
    return { ok: true, poolId: id, name: cleanName };
  }

  removePool(poolId) {
    if (!this._pools.has(poolId)) return { ok: false, error: 'not found' };
    const p = this._pools.get(poolId);
    this._pools.delete(poolId);
    this._savePools();
    return { ok: true, removed: poolId, name: p.name };
  }

  listPools() {
    return Array.from(this._pools.entries()).map(([id, p]) => ({
      id, name: p.name, url: p.url, lastSync: p.lastSync, status: p.status,
      hasAdmin: !!p.adminKeyHalf, hasHmac: !!p.hmacSecret,
    }));
  }

  // Remote operations
  async getHealth(poolId) {
    try {
      const r = await this._request(poolId, 'GET', '/api/health');
      const pool = this._pools.get(poolId);
      if (pool) pool.status = r.ok ? 'online' : 'error';
      return r.ok ? { ok: true, ...r.data } : { ok: false, error: r.data?.error || 'failed' };
    } catch (e) {
      const pool = this._pools.get(poolId);
      if (pool) pool.status = 'offline';
      return { ok: false, error: e.message };
    }
  }

  async getOverview(poolId) {
    try {
      const r = await this._request(poolId, 'GET', '/api/admin/overview', null, true);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'forbidden' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async getAccounts(poolId) {
    try {
      const r = await this._request(poolId, 'GET', '/api/admin/accounts', null, true);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'forbidden' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async getUsers(poolId) {
    try {
      const r = await this._request(poolId, 'GET', '/api/admin/users', null, true);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'forbidden' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async getPayments(poolId) {
    try {
      const r = await this._request(poolId, 'GET', '/api/admin/payments', null, true);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'forbidden' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async syncAccounts(poolId, accounts) {
    try {
      const r = await this._request(poolId, 'POST', '/api/admin/sync', { accounts }, true);
      const pool = this._pools.get(poolId);
      if (pool && r.ok) pool.lastSync = new Date().toISOString();
      this._savePools();
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async confirmPayment(poolId, paymentId) {
    try {
      const r = await this._request(poolId, 'POST', '/api/admin/confirm', { payment_id: paymentId }, true);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async rejectPayment(poolId, paymentId) {
    try {
      const r = await this._request(poolId, 'POST', '/api/admin/reject', { payment_id: paymentId }, true);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async getPublicPool(poolId) {
    try {
      const r = await this._request(poolId, 'GET', '/api/public/pool');
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async getPublicPoolEnhanced(poolId) {
    try {
      const r = await this._request(poolId, 'GET', '/api/public/pool-enhanced');
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async getCloudDevices(poolId) {
    try {
      const r = await this._request(poolId, 'GET', '/api/admin/devices', null, true);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'forbidden' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async getCloudP2POrders(poolId) {
    try {
      const r = await this._request(poolId, 'GET', '/api/admin/p2p-orders', null, true);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'forbidden' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  // ── Active Pool Selection (auto-pick first available pool) ──
  getActivePoolId() {
    const ids = Array.from(this._pools.keys());
    return ids.length > 0 ? ids[0] : null;
  }

  // ── Ext Relay: forward /api/ext/* to cloud on behalf of client ──
  async extHealth() {
    const pid = this.getActivePoolId();
    if (!pid) return { ok: false, error: 'no pool configured' };
    try {
      const r = await this._request(pid, 'GET', '/api/health');
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async extPool(deviceId) {
    const pid = this.getActivePoolId();
    if (!pid) return { ok: false, error: 'no pool configured' };
    try {
      const r = await this._request(pid, 'GET', '/api/ext/pool', null, false, deviceId);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async extPull(deviceId) {
    const pid = this.getActivePoolId();
    if (!pid) return { ok: false, error: 'no pool configured' };
    try {
      const r = await this._request(pid, 'GET', '/api/ext/pull', null, false, deviceId);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async extPullBlob(deviceId, email) {
    const pid = this.getActivePoolId();
    if (!pid) return { ok: false, error: 'no pool configured' };
    try {
      const apiPath = email ? `/api/ext/pull-blob?email=${encodeURIComponent(email)}` : '/api/ext/pull-blob';
      const r = await this._request(pid, 'GET', apiPath, null, false, deviceId);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async extHeartbeat(deviceId, data) {
    const pid = this.getActivePoolId();
    if (!pid) return { ok: false, error: 'no pool configured' };
    try {
      const r = await this._request(pid, 'POST', '/api/ext/heartbeat', { ...data, device_id: deviceId }, false, deviceId);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async extPush(deviceId, data) {
    const pid = this.getActivePoolId();
    if (!pid) return { ok: false, error: 'no pool configured' };
    try {
      const r = await this._request(pid, 'POST', '/api/ext/push', { ...data, device_id: deviceId }, false, deviceId);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async extRelease(deviceId, data) {
    const pid = this.getActivePoolId();
    if (!pid) return { ok: false, error: 'no pool configured' };
    try {
      const r = await this._request(pid, 'POST', '/api/ext/release', { ...data, device_id: deviceId }, false, deviceId);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async extPoolEnhanced(deviceId) {
    const pid = this.getActivePoolId();
    if (!pid) return { ok: false, error: 'no pool configured' };
    try {
      const r = await this._request(pid, 'GET', '/api/public/pool-enhanced', null, false, deviceId);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  // ── Push Directives — 道之推·万法归宗 ──
  async pushDirective(poolId, directive) {
    try {
      const r = await this._request(poolId, 'POST', '/api/admin/push', directive, true);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'push failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async listDirectives(poolId) {
    try {
      const r = await this._request(poolId, 'GET', '/api/admin/push', null, true);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'forbidden' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async revokeDirective(poolId, directiveId) {
    try {
      const r = await this._request(poolId, 'POST', '/api/admin/push/revoke', { directive_id: directiveId }, true);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'revoke failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  // ── Security — 道之防·安全防护 ──
  async getSecurityEvents(poolId, limit) {
    try {
      const r = await this._request(poolId, 'GET', '/api/admin/security-events?limit=' + (limit || 100), null, true);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'forbidden' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async blockIp(poolId, ip, action) {
    try {
      const r = await this._request(poolId, 'POST', '/api/admin/ip-block', { ip, action: action || 'block' }, true);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  // ── Ext Relay: Device Activation (client → hub → cloud) ──
  async extActivateDevice(deviceId, data) {
    const pid = this.getActivePoolId();
    if (!pid) return { ok: false, error: 'no pool configured' };
    try {
      const r = await this._request(pid, 'POST', '/api/device/activate',
        { hwid: data.hwid || deviceId, name: data.name || require('os').hostname() }, true);
      return r.ok ? { ok: true, activated: true, ...r.data } : { ok: false, error: r.data?.error || 'activation failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  // ── Ext Relay: Device Status (is this device activated?) ──
  // Uses /api/device/activate (idempotent for existing devices, no admin key needed)
  async extDeviceStatus(deviceId) {
    const pid = this.getActivePoolId();
    if (!pid) return { ok: false, device_activated: false, error: 'no pool configured' };
    try {
      // POST activate is idempotent: returns action:"existing" + w_total/w_available for known devices
      const r = await this._request(pid, 'POST', '/api/device/activate',
        { hwid: deviceId, name: require('os').hostname() }, true);
      if (r.ok && r.data && (r.data.activated || r.data.action === 'existing' || r.data.device_id)) {
        return {
          ok: true, device_activated: true,
          w_total: r.data.w_total || 100,
          w_available: r.data.w_available || 0,
          device: { hwid: r.data.hwid || deviceId, name: r.data.name || '', w_total: r.data.w_total || 100, w_available: r.data.w_available || 0 },
        };
      }
      return { ok: true, device_activated: false };
    } catch (e) { return { ok: false, device_activated: false, error: e.message }; }
  }

  // ── Remote Management: Pending requests for client approval ──
  // In-memory store: { targetDeviceId → [{ id, adminId, action, payload, ts, status }] }
  _getRemoteStore() {
    if (!this._remoteRequests) this._remoteRequests = new Map();
    return this._remoteRequests;
  }

  createRemoteRequest(targetDeviceId, adminId, action, payload) {
    const store = this._getRemoteStore();
    const id = require('crypto').randomBytes(8).toString('hex');
    const req = { id, adminId, action, payload: payload || {}, ts: Date.now(), status: 'pending', response: null };
    if (!store.has(targetDeviceId)) store.set(targetDeviceId, []);
    const queue = store.get(targetDeviceId);
    // Max 10 pending per device, evict oldest
    while (queue.length >= 10) queue.shift();
    queue.push(req);
    return { ok: true, requestId: id };
  }

  getRemoteRequestStatus(requestId) {
    const store = this._getRemoteStore();
    for (const [, queue] of store) {
      const r = queue.find(q => q.id === requestId);
      if (r) return { ok: true, request: r };
    }
    return { ok: false, error: 'not found' };
  }

  async extRemotePending(deviceId) {
    const store = this._getRemoteStore();
    const queue = store.get(deviceId) || [];
    // Return only pending requests, clean expired (>5min)
    const now = Date.now();
    const pending = queue.filter(r => r.status === 'pending' && (now - r.ts) < 300000);
    store.set(deviceId, queue.filter(r => (now - r.ts) < 600000)); // clean old
    return { ok: true, requests: pending.map(r => ({ id: r.id, action: r.action, payload: r.payload, ts: r.ts })) };
  }

  async extRemoteRespond(deviceId, data) {
    const store = this._getRemoteStore();
    const queue = store.get(deviceId) || [];
    const req = queue.find(r => r.id === data.requestId);
    if (!req) return { ok: false, error: 'request not found or expired' };
    if (req.status !== 'pending') return { ok: false, error: 'already responded' };
    req.status = data.approved ? 'approved' : 'denied';
    req.response = { approved: !!data.approved, respondedAt: Date.now(), reason: data.reason || '' };
    return { ok: true, status: req.status };
  }

  // ══════════════════════════════════════════════════
  //  RATE LIMIT GUARD — 道之防·限流防护·从根本上解决
  // ══════════════════════════════════════════════════
  // In-memory: { email → { hitAt, cooldownUntil, hitCount, deviceId, traceId } }
  _getRateLimitStore() {
    if (!this._rateLimits) this._rateLimits = new Map();
    return this._rateLimits;
  }
  _getRateLimitEvents() {
    if (!this._rlEvents) this._rlEvents = [];
    return this._rlEvents;
  }
  _getRateLimitConfig() {
    if (!this._rlConfig) this._rlConfig = {
      enabled: true,
      autoSwitch: true,          // auto-push account switch on rate limit
      cooldownMinutes: 65,       // default cooldown = 65min (rate limit says ~1hr)
      preemptThreshold: 80,      // switch when D% drops below this (v17.0: 85→80 减少不必要切换)
      minSwitchInterval: 3000,   // v17.0: 最短切号间隔3秒(防连锁触发)
      rateLimitRetryDelay: 5000, // v17.0: 限流后5秒再切号(避免新账号立即触发)
      maxEventsKept: 200,
    };
    return this._rlConfig;
  }

  setRateLimitConfig(cfg) {
    const c = this._getRateLimitConfig();
    if (cfg.enabled !== undefined) c.enabled = !!cfg.enabled;
    if (cfg.autoSwitch !== undefined) c.autoSwitch = !!cfg.autoSwitch;
    if (cfg.cooldownMinutes > 0) c.cooldownMinutes = Math.min(cfg.cooldownMinutes, 1440);
    if (cfg.preemptThreshold > 0) c.preemptThreshold = Math.min(cfg.preemptThreshold, 100);
    return { ok: true, config: c };
  }

  // Called when client reports a rate limit hit
  async reportRateLimit(deviceId, data) {
    const cfg = this._getRateLimitConfig();
    if (!cfg.enabled) return { ok: true, action: 'ignored', reason: 'guard disabled' };

    const store = this._getRateLimitStore();
    const events = this._getRateLimitEvents();
    const now = Date.now();
    const email = data.email || data.account || 'unknown';
    const traceId = data.traceId || '';
    const cooldownMs = cfg.cooldownMinutes * 60 * 1000;

    // v17.0: 防连锁 — 两次切号间隔不能太短
    if (this._lastSwitchAt && (now - this._lastSwitchAt) < (cfg.minSwitchInterval || 3000)) {
      return { ok: true, action: 'throttled', reason: 'min_switch_interval', waitMs: (cfg.minSwitchInterval || 3000) - (now - this._lastSwitchAt) };
    }

    // Record the rate limit hit
    const existing = store.get(email) || { hitCount: 0 };
    const entry = {
      email,
      deviceId,
      hitAt: now,
      cooldownUntil: now + cooldownMs,
      hitCount: existing.hitCount + 1,
      traceId,
      dPercent: data.dPercent || 0,
      wPercent: data.wPercent || 0,
    };
    store.set(email, entry);

    // Log event
    const event = {
      ts: new Date().toISOString(),
      type: 'rate_limit_hit',
      email,
      deviceId,
      traceId,
      dPercent: data.dPercent || 0,
      wPercent: data.wPercent || 0,
      action: 'none',
    };

    // Auto-switch: push force_refresh to trigger account rotation
    if (cfg.autoSwitch) {
      try {
        const pid = this.getActivePoolId();
        if (pid) {
          // Tell cloud pool to release this account and assign a new one
          const releaseResult = await this._request(pid, 'POST', '/api/ext/release',
            { device_id: deviceId, email, reason: 'rate_limit' }, false, deviceId);
          // Push force_refresh directive to make client pull new account
          const pushResult = await this.pushDirective(pid, {
            type: 'force_refresh',
            target: deviceId,
            payload: JSON.stringify({
              reason: 'rate_limit_auto_switch',
              blocked_email: email,
              cooldown_until: new Date(now + cooldownMs).toISOString(),
              message: '账号 ' + email.slice(0, 6) + '*** 触发限流，已自动切换',
            }),
            priority: 'high',
            ttl_hours: 1,
          });
          event.action = 'auto_switched';
          event.newDirectiveId = pushResult.directive_id || '';
          event.releaseOk = !!(releaseResult && releaseResult.ok);
          this._lastSwitchAt = now; // v17.0: 记录切号时间戳
        }
      } catch (e) {
        event.action = 'switch_failed';
        event.error = e.message;
      }
    }

    events.unshift(event);
    if (events.length > cfg.maxEventsKept) events.length = cfg.maxEventsKept;

    return {
      ok: true,
      action: event.action,
      cooldownUntil: new Date(entry.cooldownUntil).toISOString(),
      switchedAccount: event.action === 'auto_switched',
    };
  }

  // Get rate limit dashboard data
  getRateLimitStatus() {
    const store = this._getRateLimitStore();
    const events = this._getRateLimitEvents();
    const cfg = this._getRateLimitConfig();
    const now = Date.now();

    const cooling = [];
    const expired = [];
    for (const [email, entry] of store) {
      if (entry.cooldownUntil > now) {
        cooling.push({
          email,
          deviceId: entry.deviceId,
          hitAt: new Date(entry.hitAt).toISOString(),
          cooldownUntil: new Date(entry.cooldownUntil).toISOString(),
          remainingMin: Math.ceil((entry.cooldownUntil - now) / 60000),
          hitCount: entry.hitCount,
        });
      } else {
        expired.push({ email, hitCount: entry.hitCount, lastHit: new Date(entry.hitAt).toISOString() });
      }
    }

    // Stats
    const last24h = events.filter(e => (now - new Date(e.ts).getTime()) < 86400000);
    const autoSwitched = last24h.filter(e => e.action === 'auto_switched').length;
    const switchFailed = last24h.filter(e => e.action === 'switch_failed').length;

    return {
      ok: true,
      config: cfg,
      cooling: cooling.sort((a, b) => a.remainingMin - b.remainingMin),
      coolingCount: cooling.length,
      expiredCount: expired.length,
      events: events.slice(0, 50),
      stats: {
        total24h: last24h.length,
        autoSwitched,
        switchFailed,
        totalTracked: store.size,
      },
    };
  }

  // Clear cooldown for specific account (admin manual override)
  clearCooldown(email) {
    const store = this._getRateLimitStore();
    if (email === 'all') {
      store.clear();
      return { ok: true, cleared: 'all' };
    }
    if (store.has(email)) {
      store.delete(email);
      return { ok: true, cleared: email };
    }
    return { ok: false, error: 'not found: ' + email };
  }

  // Check if an account is in cooldown
  isInCooldown(email) {
    const store = this._getRateLimitStore();
    const entry = store.get(email);
    if (!entry) return false;
    return entry.cooldownUntil > Date.now();
  }

  // Aggregate: all pools status
  async getAllStatus() {
    const results = [];
    for (const [id, pool] of this._pools) {
      try {
        const health = await this.getHealth(id);
        results.push({ id, name: pool.name, url: pool.url, ...health });
      } catch (e) {
        results.push({ id, name: pool.name, url: pool.url, ok: false, error: e.message });
      }
    }
    return results;
  }

  // Aggregate: all pools overview (admin)
  async getAllOverviews() {
    const results = [];
    for (const [id, pool] of this._pools) {
      try {
        const overview = await this.getOverview(id);
        results.push({ id, name: pool.name, url: pool.url, ...overview });
      } catch (e) {
        results.push({ id, name: pool.name, url: pool.url, ok: false, error: e.message });
      }
    }
    return results;
  }

  dispose() { this._savePools(); }
}

module.exports = { PoolManager };
