/**
 * Pool Relay Client — 本机中继对接
 * 道: 客户端不知云端, 云端不知客户端。中间人是唯一知情者。
 *
 * 连接: 127.0.0.1:19881 (本机管理端)
 * 认证: 机器指纹派生HMAC, 双端独立计算, 无硬编码密钥
 * 路径: 语义混淆, 无法从路径推断业务逻辑
 */
const http = require('http');
const crypto = require('crypto');
const os = require('os');

// Keep-alive agent — reuse TCP connections to local hub
const _agent = new http.Agent({ keepAlive: true, maxSockets: 4, timeout: 5000 });

function _machineId() {
  return crypto.createHash('sha256').update(
    [os.hostname(), os.userInfo().username, os.cpus()[0]?.model || '', os.platform(), os.arch()].join('|')
  ).digest('hex');
}

function _localSecret() {
  return crypto.createHmac('sha256', _machineId()).update('wam-relay-v1').digest('hex');
}

class CloudPoolClient {
  constructor() {
    this._port = 19881;
    this._host = '127.0.0.1';
    this._deviceId = crypto.createHash('sha256')
      .update(os.hostname() + '|' + os.userInfo().username).digest('hex').slice(0, 16);
    this._lastPull = null;
    this._lastSync = 0;
    this._online = false;
    this._lastCheck = 0;
    this._poolCache = null;
    this._poolCacheTs = 0;
    this._errors = 0;
    this._retryDelay = 1000;
    this._enhancedCache = null;
    this._devStatusCache = null;
    this._devStatusTs = 0;
    this._machineId = _machineId();
  }

  _signHeaders() {
    const ts = Math.floor(Date.now() / 1000).toString();
    const nonce = crypto.randomBytes(8).toString('hex');
    const sig = crypto.createHmac('sha256', _localSecret()).update(ts + '.' + nonce).digest('hex');
    return { 'x-ts': ts, 'x-nc': nonce, 'x-sg': sig, 'x-di': this._deviceId };
  }

  _request(method, path, body, qs) {
    return new Promise((resolve, reject) => {
      const fullPath = path + (qs ? '?' + qs : '');
      const bodyStr = body ? JSON.stringify(body) : null;
      const bodyBuf = bodyStr ? Buffer.from(bodyStr) : null;
      const opts = {
        hostname: this._host,
        port: this._port,
        path: fullPath,
        method,
        headers: {
          'Content-Type': 'application/json',
          ...this._signHeaders(),
          ...(bodyBuf ? { 'Content-Length': bodyBuf.length } : {}),
        },
        agent: _agent,
        timeout: 5000,
      };
      const req = http.request(opts, (res) => {
        let data = '';
        res.on('data', c => data += c);
        res.on('end', () => {
          try {
            const json = JSON.parse(data);
            this._online = true;
            this._errors = 0;
            this._retryDelay = 1000;
            resolve({ ok: res.statusCode === 200, status: res.statusCode, data: json });
          } catch {
            resolve({ ok: false, status: res.statusCode, data: { error: 'parse_error' } });
          }
        });
      });
      req.on('error', e => { this._online = false; this._errors++; this._retryDelay = Math.min(this._retryDelay * 1.5, 15000); reject(e); });
      req.on('timeout', () => { req.destroy(); this._online = false; this._errors++; this._retryDelay = Math.min(this._retryDelay * 1.5, 15000); reject(new Error('timeout')); });
      if (bodyBuf) req.write(bodyBuf);
      req.end();
    });
  }

  async checkHealth() {
    try {
      const r = await this._request('GET', '/api/v1/ping');
      this._online = r.ok && r.data?.status === 'ok';
      this._lastCheck = Date.now();
      if (this._online) {
        // Sequential to avoid flooding local hub
        try { const d = await this.getEnhancedPool(); if (d?.ok) this._enhancedCache = d; } catch {}
        try { const d = await this.getDeviceStatus(); if (d) this._devStatusCache = d; } catch {}
      }
      return { online: this._online, version: r.data?.version, accounts: r.data?.accounts, available: r.data?.available };
    } catch (e) {
      this._online = false;
      this._lastCheck = Date.now();
      return { online: false, error: e.message };
    }
  }

  async getPoolStatus() {
    if (this._poolCache && Date.now() - this._poolCacheTs < 30000) return this._poolCache;
    try {
      const r = await this._request('GET', '/api/v1/status');
      if (r.ok && r.data?.ok) {
        this._poolCache = r.data;
        this._poolCacheTs = Date.now();
        return r.data;
      }
      return { ok: false, error: r.data?.error || 'request failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async pullAccount() {
    try {
      const r = await this._request('GET', '/api/v1/acquire');
      if (r.ok && r.data?.ok) {
        this._lastPull = { ...r.data, pulledAt: Date.now() };
        return r.data;
      }
      return { ok: false, error: r.data?.error || 'pull failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async pullBlob(email) {
    try {
      const qs = email ? 'e=' + encodeURIComponent(email) : '';
      const r = await this._request('GET', '/api/v1/inject', null, qs);
      if (r.ok && r.data?.ok) {
        this._lastPull = { ...r.data, pulledAt: Date.now(), hasBlob: true };
        return r.data;
      }
      return { ok: false, error: r.data?.error || 'inject failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async heartbeat(email, daily, weekly) {
    try {
      const r = await this._request('POST', '/api/v1/signal', { email, daily, weekly });
      if (r.ok && r.data?.ok) return r.data;
      return { ok: false, error: r.data?.error || 'signal failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async pushHealth(accounts) {
    try {
      const r = await this._request('POST', '/api/v1/report', { accounts });
      this._lastSync = Date.now();
      return r.ok ? r.data : { ok: false, error: r.data?.error };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async releaseAccount(email) {
    try {
      const r = await this._request('POST', '/api/v1/reclaim', { email });
      return r.ok ? r.data : { ok: false, error: r.data?.error };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async getEnhancedPool() {
    try {
      const r = await this._request('GET', '/api/v1/metric');
      if (r.ok && r.data?.ok) return r.data;
      return { ok: false, error: r.data?.error || 'failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async activate(hwid, name) {
    try {
      const r = await this._request('POST', '/api/v1/activate', { hwid: hwid || this._deviceId, name: name || os.hostname() });
      return r.ok ? { ok: true, ...r.data } : { ok: false, reason: r.data?.error || 'activation failed' };
    } catch (e) { return { ok: false, reason: e.message }; }
  }

  async remotePending() {
    try {
      const r = await this._request('GET', '/api/v1/remote-pending');
      return r.ok ? r.data : { ok: false, requests: [] };
    } catch { return { ok: false, requests: [] }; }
  }

  async getDeviceStatus() {
    try {
      const r = await this._request('GET', '/api/v1/me-status');
      this._devStatusTs = Date.now();
      if (r.ok && r.data) { this._devStatusCache = r.data; return r.data; }
      return { ok: false, device_activated: false };
    } catch { return { ok: false, device_activated: false }; }
  }

  async remoteRespond(requestId, approved, reason) {
    try {
      const r = await this._request('POST', '/api/v1/remote-respond', { requestId, approved: !!approved, reason: reason || '' });
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'respond failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async reportRateLimit(email, traceId, dPercent, wPercent, model, resetAt, resetMs) {
    try {
      // v19.0: 透传 _resetAt/_resetMs (来自 ws_repatch Patch5)
      const payload = {
        email, traceId: traceId || '', dPercent: dPercent || 0,
        wPercent: wPercent || 0, model: model || '',
      };
      if (resetAt && resetAt > Date.now()) payload.resetAt = resetAt;
      if (resetMs && resetMs > 0)          payload.resetMs = resetMs;
      const r = await this._request('POST', '/api/v1/rate-limit-report', payload);
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'report failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }


  async payInit(amount, note) {
    try {
      const r = await this._request('POST', '/api/v1/pay-init', { amount, note: note || '' });
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'pay-init failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  async payStatus(orderId) {
    try {
      const r = await this._request('GET', '/api/v1/pay-status', null, 'orderId=' + encodeURIComponent(orderId));
      return r.ok ? r.data : { ok: false, error: r.data?.error || 'pay-status failed' };
    } catch (e) { return { ok: false, error: e.message }; }
  }

  getStatus() {
    const enh = this._enhancedCache;
    return {
      online: this._online,
      deviceId: this._deviceId,
      lastCheck: this._lastCheck,
      lastSync: this._lastSync,
      lastPull: this._lastPull,
      errors: this._errors,
      poolW: enh && enh.pool ? (enh.pool.total_w || 0) : null,
      availW: enh && enh.w_resource ? (enh.w_resource.available_w || 0) : null,
      devices: enh && enh.w_resource ? (enh.w_resource.devices || 0) : null,
      initialBonus: enh && enh.w_resource ? (enh.w_resource.initial_bonus || 100) : 100,
      device_activated: this._devStatusCache ? !!this._devStatusCache.device_activated : false,
      my_w: this._devStatusCache ? (this._devStatusCache.w_total || 0) : 0,
      my_w_available: this._devStatusCache ? (this._devStatusCache.w_available || 0) : 0,
      machine_code: this._machineId,
    };
  }

  isOnline() { return this._online; }

  dispose() { this._poolCache = null; _agent.destroy(); }
}

module.exports = { CloudPoolClient };
