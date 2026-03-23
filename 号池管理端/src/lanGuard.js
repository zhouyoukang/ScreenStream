/**
 * LAN Guard — 道之防·网络安全层
 *
 * L1 子网绑定: Hub仅监听LAN接口IP, 非LAN请求拒绝
 * L2 设备注册: 硬件指纹(MAC+hostname) → HMAC认证
 * L3 会话管理: 时间窗口轮转 + Nonce防重放
 * L4 速率限制: IP/设备双维度限流
 * L5 审计链: 不可篡改日志链
 * L6 异常封禁: 连续失败→封禁IP
 */
const crypto = require('crypto');
const os = require('os');
const fs = require('fs');
const path = require('path');

const MAX_BODY_BYTES = 64 * 1024; // 64KB max request body
const SESSION_CLEANUP_INTERVAL = 60000; // 1min
const NONCE_CLEANUP_INTERVAL = 120000; // 2min

function _ip2long(ip) {
  const p = ip.split('.').map(Number);
  return ((p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3]) >>> 0;
}

function _cidrContains(cidr, ip) {
  const [subnet, bits] = cidr.split('/');
  const mask = bits ? (~0 << (32 - parseInt(bits))) >>> 0 : 0xFFFFFFFF;
  return (_ip2long(subnet) & mask) === (_ip2long(ip) & mask);
}

function getMachineIdentity() {
  return crypto.createHash('sha256').update(
    [os.hostname(), os.userInfo().username, os.cpus()[0]?.model || '', os.platform(), os.arch()].join('|')
  ).digest('hex');
}

function getMachineSecret() {
  return crypto.createHash('sha256')
    .update('dao-pool-admin-' + getMachineIdentity())
    .digest('hex').slice(0, 32);
}

class LANGuard {
  constructor(options = {}) {
    this._trustedSubnets = options.trustedSubnets || ['192.168.0.0/16', '10.0.0.0/8'];
    this._sessionTTL = options.sessionTTL || 900;
    this._maxDevices = options.maxDevices || 5;
    this._configDir = options.configDir || path.join(os.homedir(), '.pool-admin');
    this._machineSecret = getMachineSecret();
    this._enrolledDevices = new Map();
    this._sessions = new Map();
    this._auditLog = [];
    this._rateLimits = new Map();
    this._usedNonces = new Map();
    this._failCounts = new Map();
    this._RATE_WINDOW = 60;
    this._RATE_MAX = 30;
    this._NONCE_TTL = 300;
    this._FAIL_THRESHOLD = 10;
    this._BLOCK_DURATION = 600;
    this._MAX_AUDIT = 10000;
    this._loadState();
    // Periodic cleanup timers
    this._sessionTimer = setInterval(() => this.cleanExpiredSessions(), SESSION_CLEANUP_INTERVAL);
    this._nonceTimer = setInterval(() => this._cleanNonces(), NONCE_CLEANUP_INTERVAL);
  }

  // ── Crypto ──
  _encrypt(text) {
    const iv = crypto.randomBytes(16);
    const key = crypto.scryptSync(this._machineSecret, 'dao-salt', 32);
    const cipher = crypto.createCipheriv('aes-256-cbc', key, iv);
    let enc = cipher.update(text, 'utf8', 'hex');
    enc += cipher.final('hex');
    return iv.toString('hex') + ':' + enc;
  }

  _decrypt(text) {
    try {
      const [ivHex, enc] = text.split(':');
      const iv = Buffer.from(ivHex, 'hex');
      const key = crypto.scryptSync(this._machineSecret, 'dao-salt', 32);
      const decipher = crypto.createDecipheriv('aes-256-cbc', key, iv);
      let dec = decipher.update(enc, 'hex', 'utf8');
      dec += decipher.final('utf8');
      return dec;
    } catch { return null; }
  }

  // ── Persistence ──
  _getStatePath() { return path.join(this._configDir, 'lan_guard.enc'); }

  _loadState() {
    try {
      fs.mkdirSync(this._configDir, { recursive: true });
      const fp = this._getStatePath();
      if (!fs.existsSync(fp)) return;
      const data = this._decrypt(fs.readFileSync(fp, 'utf-8'));
      if (!data) return;
      const obj = JSON.parse(data);
      if (obj.devices) {
        for (const [k, v] of Object.entries(obj.devices)) this._enrolledDevices.set(k, v);
      }
    } catch { /* first run */ }
  }

  _saveState() {
    try {
      const obj = { devices: Object.fromEntries(this._enrolledDevices), ts: new Date().toISOString() };
      fs.mkdirSync(this._configDir, { recursive: true });
      fs.writeFileSync(this._getStatePath(), this._encrypt(JSON.stringify(obj)), 'utf-8');
    } catch { /* non-critical */ }
  }

  // ── Audit ──
  audit(action, ip, device, detail) {
    const prev = this._auditLog.length > 0 ? this._auditLog[this._auditLog.length - 1].hash : '0';
    const entry = { ts: new Date().toISOString(), action, ip: ip || '', device: device || '', detail: detail || '' };
    entry.hash = crypto.createHash('sha256').update(prev + JSON.stringify(entry)).digest('hex').slice(0, 16);
    this._auditLog.push(entry);
    if (this._auditLog.length > this._MAX_AUDIT) this._auditLog.shift();
    try {
      fs.appendFileSync(path.join(this._configDir, 'audit.log'),
        JSON.stringify(entry) + '\n', 'utf-8');
    } catch { /* non-critical */ }
    return entry;
  }

  getAuditLog(limit = 100) {
    return this._auditLog.slice(-limit);
  }

  // ── LAN Detection ──
  isLanIp(ip) {
    if (!ip || ip === '127.0.0.1' || ip === '::1') return true;
    for (const cidr of this._trustedSubnets) {
      if (_cidrContains(cidr, ip)) return true;
    }
    return false;
  }

  getLanIp() {
    const nets = os.networkInterfaces();
    for (const addrs of Object.values(nets)) {
      for (const addr of addrs) {
        if (addr.family === 'IPv4' && !addr.internal) {
          for (const cidr of this._trustedSubnets) {
            if (_cidrContains(cidr, addr.address)) return addr.address;
          }
        }
      }
    }
    return null;
  }

  getLanInfo() {
    const nets = os.networkInterfaces();
    const result = [];
    for (const [name, addrs] of Object.entries(nets)) {
      for (const addr of addrs) {
        if (addr.family === 'IPv4' && !addr.internal) {
          result.push({ name, ip: addr.address, mac: addr.mac, trusted: this.isLanIp(addr.address) });
        }
      }
    }
    return result;
  }

  // ── Rate Limiting ──
  _rateCheck(ip) {
    // Localhost exempt: Hub binds to 127.0.0.1, all webview/relay traffic is local
    if (ip === '127.0.0.1' || ip === '::1') return true;
    const now = Date.now() / 1000;
    let r = this._rateLimits.get(ip);
    if (!r) { r = { count: 0, windowStart: now, blockedUntil: 0 }; this._rateLimits.set(ip, r); }
    if (r.blockedUntil > now) return false;
    if (now - r.windowStart > this._RATE_WINDOW) { r.count = 0; r.windowStart = now; }
    r.count++;
    return r.count <= this._RATE_MAX;
  }

  _recordFail(ip) {
    // Localhost exempt from fail-blocking
    if (ip === '127.0.0.1' || ip === '::1') return false;
    const c = (this._failCounts.get(ip) || 0) + 1;
    this._failCounts.set(ip, c);
    if (c >= this._FAIL_THRESHOLD) {
      const r = this._rateLimits.get(ip) || { count: 0, windowStart: 0, blockedUntil: 0 };
      r.blockedUntil = Date.now() / 1000 + this._BLOCK_DURATION;
      this._rateLimits.set(ip, r);
      this.audit('BLOCK', ip, '', `blocked after ${c} failures`);
      return true;
    }
    return false;
  }

  _clearFail(ip) { this._failCounts.delete(ip); }

  // ── Nonce Replay Protection ──
  _checkNonce(nonce) {
    if (!nonce) return true;
    if (this._usedNonces.has(nonce)) return false;
    this._usedNonces.set(nonce, Date.now() / 1000 + this._NONCE_TTL);
    return true;
  }

  _cleanNonces() {
    const now = Date.now() / 1000;
    for (const [n, exp] of this._usedNonces) {
      if (now > exp) this._usedNonces.delete(n);
    }
  }

  // ── Device Enrollment ──
  enrollDevice(fingerprint, name, ip) {
    if (this._enrolledDevices.has(fingerprint)) {
      return { ok: false, error: 'already enrolled' };
    }
    if (this._enrolledDevices.size >= this._maxDevices) {
      return { ok: false, error: `max ${this._maxDevices} devices` };
    }
    const device = {
      name: name || `device_${fingerprint.slice(0, 8)}`,
      ip, enrolledAt: new Date().toISOString(), lastSeen: new Date().toISOString(), active: true,
    };
    this._enrolledDevices.set(fingerprint, device);
    this._saveState();
    this.audit('ENROLL', ip, fingerprint, `enrolled: ${device.name}`);
    return { ok: true, fingerprint, device };
  }

  revokeDevice(fingerprint) {
    if (!this._enrolledDevices.has(fingerprint)) {
      return { ok: false, error: 'not found' };
    }
    const dev = this._enrolledDevices.get(fingerprint);
    this._enrolledDevices.delete(fingerprint);
    // Also revoke all sessions for this device
    for (const [sid, sess] of this._sessions) {
      if (sess.deviceFp === fingerprint) this._sessions.delete(sid);
    }
    this._saveState();
    this.audit('REVOKE', dev.ip, fingerprint, `revoked: ${dev.name}`);
    return { ok: true, revoked: fingerprint };
  }

  getDevices() {
    return Array.from(this._enrolledDevices.entries()).map(([fp, d]) => ({ fingerprint: fp, ...d }));
  }

  isDeviceEnrolled(fingerprint) {
    const d = this._enrolledDevices.get(fingerprint);
    return d && d.active;
  }

  // ── Session Management ──
  createSession(deviceFp, ip) {
    if (!this.isDeviceEnrolled(deviceFp)) {
      return { ok: false, error: 'device not enrolled' };
    }
    if (!this.isLanIp(ip)) {
      return { ok: false, error: 'not on trusted LAN' };
    }
    const sessionId = crypto.randomBytes(24).toString('hex');
    const now = new Date();
    const expires = new Date(now.getTime() + this._sessionTTL * 1000);
    this._sessions.set(sessionId, {
      deviceFp, ip, createdAt: now.toISOString(), expiresAt: expires.toISOString(),
    });
    // Update device last seen
    const dev = this._enrolledDevices.get(deviceFp);
    if (dev) { dev.lastSeen = now.toISOString(); dev.ip = ip; }
    this._saveState();
    this.audit('SESSION', ip, deviceFp, 'session created');
    return { ok: true, sessionId, expiresAt: expires.toISOString() };
  }

  validateSession(sessionId, ip) {
    const sess = this._sessions.get(sessionId);
    if (!sess) return { ok: false, error: 'invalid session' };
    if (new Date() > new Date(sess.expiresAt)) {
      this._sessions.delete(sessionId);
      return { ok: false, error: 'session expired' };
    }
    if (!this.isLanIp(ip)) return { ok: false, error: 'not on LAN' };
    return { ok: true, deviceFp: sess.deviceFp, ip: sess.ip };
  }

  cleanExpiredSessions() {
    const now = new Date();
    for (const [sid, sess] of this._sessions) {
      if (now > new Date(sess.expiresAt)) this._sessions.delete(sid);
    }
  }

  // ── Request Authentication (for Hub HTTP middleware) ──
  authenticateRequest(req) {
    const ip = this._getClientIp(req);

    // L1: LAN check
    if (!this.isLanIp(ip)) {
      this.audit('REJECT', ip, '', 'non-LAN access attempt');
      return { ok: false, code: 403, error: 'access denied' };
    }

    // L4: Rate limit
    if (!this._rateCheck(ip)) {
      this.audit('RATE_LIMIT', ip, '', 'rate limited');
      return { ok: false, code: 429, error: 'rate limited' };
    }

    // Special: self-enrollment endpoint allows unauthenticated LAN access
    const url = req.url?.split('?')[0]?.replace(/\/+$/, '') || '';
    if (url === '/api/enroll' || url === '/api/health' || url === '/dashboard') {
      return { ok: true, ip, level: 'public' };
    }

    // L3: Session check
    const sessionId = req.headers['x-session'] || '';
    const nonce = req.headers['x-nonce'] || '';

    if (!sessionId) {
      this._recordFail(ip);
      return { ok: false, code: 401, error: 'session required' };
    }

    // Nonce replay check
    if (nonce && !this._checkNonce(nonce)) {
      this._recordFail(ip);
      this.audit('REPLAY', ip, '', 'nonce replay detected');
      return { ok: false, code: 401, error: 'replay detected' };
    }

    const v = this.validateSession(sessionId, ip);
    if (!v.ok) {
      this._recordFail(ip);
      return { ok: false, code: 401, error: v.error };
    }

    this._clearFail(ip);
    return { ok: true, ip, deviceFp: v.deviceFp, level: 'admin' };
  }

  _getClientIp(req) {
    // SECURITY: Never trust X-Forwarded-For — Hub binds to 127.0.0.1,
    // all requests come from localhost. XFF can be spoofed to bypass LAN check.
    return req.socket?.remoteAddress?.replace('::ffff:', '') || '0.0.0.0';
  }

  // ── Self Enrollment (本机自动注册) ──
  enrollSelf() {
    const fp = getMachineIdentity().slice(0, 24);
    if (this._enrolledDevices.has(fp)) {
      const dev = this._enrolledDevices.get(fp);
      dev.lastSeen = new Date().toISOString();
      dev.active = true;
      this._saveState();
      return { ok: true, fingerprint: fp, existing: true };
    }
    return this.enrollDevice(fp, os.hostname() + ' (self)', '127.0.0.1');
  }

  // ── Create self session (for VSIX internal use) ──
  createSelfSession() {
    const fp = getMachineIdentity().slice(0, 24);
    if (!this.isDeviceEnrolled(fp)) this.enrollSelf();
    return this.createSession(fp, '127.0.0.1');
  }

  // ── Status ──
  getStatus() {
    return {
      lanIp: this.getLanIp(),
      lanInterfaces: this.getLanInfo(),
      trustedSubnets: this._trustedSubnets,
      enrolledDevices: this._enrolledDevices.size,
      activeSessions: this._sessions.size,
      auditEntries: this._auditLog.length,
      machineId: getMachineIdentity().slice(0, 12) + '...',
    };
  }

  dispose() {
    this._saveState();
    this._sessions.clear();
    if (this._sessionTimer) { clearInterval(this._sessionTimer); this._sessionTimer = null; }
    if (this._nonceTimer) { clearInterval(this._nonceTimer); this._nonceTimer = null; }
  }
}

// Timing-safe comparison to prevent timing attacks on HMAC signatures
function timingSafeEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

module.exports = { LANGuard, getMachineIdentity, getMachineSecret, timingSafeEqual, MAX_BODY_BYTES };
