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
