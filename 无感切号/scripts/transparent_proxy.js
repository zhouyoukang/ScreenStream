/**
 * 透明gRPC代理 — 道之本·根·源·头·底
 * 
 * 本质: 在网络层拦截Windsurf LS的gRPC请求，替换protobuf中的apiKey
 *       让每个请求可以使用不同账号的配额，实现所有账号同时在线
 *
 * 架构:
 *   LS → HTTPS_PROXY(本代理) → TLS MITM → protobuf apiKey替换 → 真实服务器
 *
 * 使用:
 *   1. node scripts/transparent_proxy.js keygen    — 生成自签名CA证书
 *   2. node scripts/transparent_proxy.js warmup    — 预热所有账号apiKey
 *   3. node scripts/transparent_proxy.js serve     — 启动透明代理
 *   4. node scripts/transparent_proxy.js test      — POC验证(apiKey替换可行性)
 *   5. node scripts/transparent_proxy.js status    — 号池状态
 */

const https = require('https');
const http = require('http');
const tls = require('tls');
const net = require('net');
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const { execSync } = require('child_process');

// ═══ 配置 ═══
const PROXY_PORT = 19443;
const DATA_DIR = path.join(__dirname, '..', 'data');
const CERT_DIR = path.join(DATA_DIR, 'certs');
const KEYPOOL_FILE = path.join(DATA_DIR, 'keypool.json');

// Windsurf gRPC 目标域名 (需要MITM的域名)
const INTERCEPT_DOMAINS = new Set([
  'server.codeium.com',
  'web-backend.windsurf.com',
  'register.windsurf.com',
]);

// Firebase配置 (复用authService.js的常量)
const FIREBASE_KEYS = [
  'AIzaSyDsOl-1XpT5err0Tcnx8FFod1H8gVGIycY',
  'AIzaSyDKm6GGxMJfCbNf-k0kPytiGLaqFJpeSac',
];
const REGISTER_URLS = [
  'https://register.windsurf.com/exa.seat_management_pb.SeatManagementService/RegisterUser',
  'https://server.codeium.com/exa.seat_management_pb.SeatManagementService/RegisterUser',
];
const PLAN_STATUS_URLS = [
  'https://server.codeium.com/exa.seat_management_pb.SeatManagementService/GetPlanStatus',
  'https://web-backend.windsurf.com/exa.seat_management_pb.SeatManagementService/GetPlanStatus',
];
const CHECK_RL_URLS = [
  'https://server.codeium.com/exa.api_server_pb.ApiServerService/CheckUserMessageRateLimit',
  'https://web-backend.windsurf.com/exa.api_server_pb.ApiServerService/CheckUserMessageRateLimit',
];

// 代理配置 (用于访问被墙的API)
const LOCAL_PROXY_PORT = 7890;

// ═══ Protobuf工具 (精简复用自authService.js) ═══

function encodeVarint(value) {
  const bytes = [];
  let v = value;
  while (v > 127) { bytes.push((v & 0x7f) | 0x80); v >>>= 7; }
  bytes.push(v & 0x7f);
  return Buffer.from(bytes);
}

function readVarint(data, pos) {
  let result = 0, shift = 0;
  while (pos < data.length) {
    const b = data[pos++];
    if (shift < 28) result |= (b & 0x7f) << shift;
    else result += (b & 0x7f) * (2 ** shift);
    if ((b & 0x80) === 0) break;
    shift += 7;
  }
  return { value: result, nextPos: pos };
}

function encodeProtoString(value, fieldNumber = 1) {
  const bytes = Buffer.from(value, 'utf8');
  const tag = (fieldNumber << 3) | 2;
  const len = encodeVarint(bytes.length);
  return Buffer.concat([Buffer.from([tag]), len, bytes]);
}

function parseProtoString(buf) {
  const bytes = new Uint8Array(buf);
  if (bytes.length < 3 || bytes[0] !== 0x0a) return null;
  let pos = 1;
  const r = readVarint(bytes, pos);
  pos = r.nextPos;
  if (pos + r.value > bytes.length) return null;
  return Buffer.from(bytes.slice(pos, pos + r.value)).toString('utf8');
}

/** 解析protobuf消息的所有字段 */
function parseProtoMsg(buf) {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  const fields = {};
  let pos = 0;
  while (pos < bytes.length) {
    const tagResult = readVarint(bytes, pos);
    const tag = tagResult.value;
    pos = tagResult.nextPos;
    const fieldNum = tag >>> 3;
    const wireType = tag & 0x07;
    if (fieldNum === 0 || fieldNum > 1000 || pos > bytes.length) break;
    if (!fields[fieldNum]) fields[fieldNum] = [];
    switch (wireType) {
      case 0: { const r = readVarint(bytes, pos); fields[fieldNum].push({ value: r.value }); pos = r.nextPos; break; }
      case 2: { const r = readVarint(bytes, pos); const len = r.value; pos = r.nextPos; if (len < 0 || len > 1048576 || pos + len > bytes.length) { pos = bytes.length; break; } fields[fieldNum].push({ bytes: bytes.slice(pos, pos + len), length: len }); pos += len; break; }
      case 1: { if (pos + 8 > bytes.length) { pos = bytes.length; break; } fields[fieldNum].push({ bytes: bytes.slice(pos, pos + 8) }); pos += 8; break; }
      case 5: { if (pos + 4 > bytes.length) { pos = bytes.length; break; } fields[fieldNum].push({ bytes: bytes.slice(pos, pos + 4) }); pos += 4; break; }
      default: pos = bytes.length;
    }
  }
  return fields;
}

// ═══ protobuf apiKey替换 — 核心突破 ═══

/**
 * 在gRPC请求的protobuf body中查找并替换apiKey
 * 
 * 请求结构 (逆向自@exa/chat-client):
 *   field 1 (metadata): nested message
 *     field 1 (api_key): string = "sk-ws-01-..."
 *   field N (其余字段): ...
 *
 * 替换策略:
 *   1. 所有apiKey都是"sk-ws-01-"开头, 103字符
 *   2. 先用indexOf找到"sk-ws-01-"前缀的位置
 *   3. 确认是在protobuf length-delimited string中
 *   4. 替换为新apiKey (等长, 直接覆盖字节)
 *
 * @returns {Buffer} 替换后的body, 或null(未找到apiKey)
 */
function replaceApiKeyInProtobuf(bodyBuf, newApiKey) {
  const SK_PREFIX = Buffer.from('sk-ws-01-');
  const bodyBytes = Buffer.isBuffer(bodyBuf) ? bodyBuf : Buffer.from(bodyBuf);
  
  // 快速搜索: 找到"sk-ws-01-"前缀位置
  let idx = bodyBytes.indexOf(SK_PREFIX);
  if (idx < 0) return null; // 没有apiKey, 不需要替换

  // 确定apiKey的完整长度: 从前缀位置开始, 找到非printable ASCII的位置
  let keyEnd = idx;
  while (keyEnd < bodyBytes.length && bodyBytes[keyEnd] >= 0x20 && bodyBytes[keyEnd] <= 0x7e) {
    keyEnd++;
  }
  const oldKeyLen = keyEnd - idx;
  const oldKey = bodyBytes.slice(idx, keyEnd).toString('utf8');
  
  // 验证: apiKey通常是103字符, sk-ws-01-开头
  if (oldKeyLen < 50 || oldKeyLen > 200) {
    console.log(`[REWRITE] suspicious key length: ${oldKeyLen}, skipping`);
    return null;
  }

  const newKeyBuf = Buffer.from(newApiKey, 'utf8');
  
  if (newKeyBuf.length === oldKeyLen) {
    // 等长替换: 直接覆盖字节 (最优, O(1))
    const result = Buffer.from(bodyBytes);
    newKeyBuf.copy(result, idx);
    return result;
  } else {
    // 不等长: 需要重新编码protobuf长度前缀
    // 找到apiKey前面的varint长度字段
    // 向前扫描: tag(1byte) + varint_length + key_bytes
    // 在metadata嵌套中: outer_tag + outer_len + inner_tag + inner_len + key_bytes
    // 简化: 用结构化解析替换
    return _structuredReplace(bodyBytes, oldKey, newApiKey);
  }
}

/** 结构化protobuf apiKey替换 (处理不等长情况) */
function _structuredReplace(bodyBuf, oldKey, newKey) {
  // 解析外层message
  const outer = parseProtoMsg(bodyBuf);
  if (!outer[1] || !outer[1][0]?.bytes) return null;
  
  // 解析metadata (field 1)
  const metaBytes = outer[1][0].bytes;
  const meta = parseProtoMsg(metaBytes);
  if (!meta[1] || !meta[1][0]?.bytes) return null;
  
  const foundKey = Buffer.from(meta[1][0].bytes).toString('utf8');
  if (foundKey !== oldKey) return null;
  
  // 重新编码metadata with新apiKey
  const newKeyField = encodeProtoString(newKey, 1);
  // 保留metadata中除field 1外的所有字段
  const metaParts = [newKeyField];
  for (const [fn, entries] of Object.entries(meta)) {
    if (fn === '1') continue; // 跳过旧apiKey
    for (const entry of entries) {
      const fieldNum = parseInt(fn);
      if (entry.value !== undefined) {
        // varint
        const tag = (fieldNum << 3) | 0;
        metaParts.push(Buffer.concat([encodeVarint(tag), encodeVarint(entry.value)]));
      } else if (entry.bytes) {
        // length-delimited
        const tag = (fieldNum << 3) | 2;
        metaParts.push(Buffer.concat([encodeVarint(tag), encodeVarint(entry.bytes.length), Buffer.from(entry.bytes)]));
      }
    }
  }
  const newMetaPayload = Buffer.concat(metaParts);
  
  // 重新编码外层message: field 1 = newMetadata, 保留其余字段
  const outerParts = [];
  // field 1 = metadata
  const metaTag = (1 << 3) | 2;
  outerParts.push(Buffer.concat([encodeVarint(metaTag), encodeVarint(newMetaPayload.length), newMetaPayload]));
  // 其余字段
  for (const [fn, entries] of Object.entries(outer)) {
    if (fn === '1') continue;
    for (const entry of entries) {
      const fieldNum = parseInt(fn);
      if (entry.value !== undefined) {
        outerParts.push(Buffer.concat([encodeVarint((fieldNum << 3) | 0), encodeVarint(entry.value)]));
      } else if (entry.bytes) {
        outerParts.push(Buffer.concat([encodeVarint((fieldNum << 3) | 2), encodeVarint(entry.bytes.length), Buffer.from(entry.bytes)]));
      }
    }
  }
  return Buffer.concat(outerParts);
}

/** 从protobuf body中提取apiKey (不修改) */
function extractApiKey(bodyBuf) {
  const SK_PREFIX = Buffer.from('sk-ws-01-');
  const buf = Buffer.isBuffer(bodyBuf) ? bodyBuf : Buffer.from(bodyBuf);
  const idx = buf.indexOf(SK_PREFIX);
  if (idx < 0) return null;
  let end = idx;
  while (end < buf.length && buf[end] >= 0x20 && buf[end] <= 0x7e) end++;
  return buf.slice(idx, end).toString('utf8');
}

/** 从protobuf body中提取modelUid */
function extractModelUid(bodyBuf) {
  try {
    const outer = parseProtoMsg(bodyBuf);
    // modelUid通常在field 3 (GetChatMessage, CheckRateLimit)
    // 或field 2 (某些请求)
    for (const fn of [3, 2, 4, 5]) {
      if (outer[fn]?.[0]?.bytes) {
        const s = Buffer.from(outer[fn][0].bytes).toString('utf8');
        if (/^[a-z0-9\-]+$/.test(s) && s.includes('-')) return s;
      }
    }
  } catch {}
  return null;
}

// ═══ HTTP/网络工具 ═══

function proxyTunnel(hostname, proxyPort = LOCAL_PROXY_PORT) {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: '127.0.0.1', port: proxyPort,
      method: 'CONNECT', path: `${hostname}:443`, timeout: 8000
    });
    req.on('connect', (res, socket) => {
      if (res.statusCode !== 200) { socket.destroy(); return reject(new Error(`CONNECT ${res.statusCode}`)); }
      const tlsSocket = tls.connect({ socket, servername: hostname, rejectUnauthorized: true }, () => resolve(tlsSocket));
      tlsSocket.on('error', reject);
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('tunnel timeout')); });
    req.end();
  });
}

function rawRequest(tlsSocket, hostname, pathStr, method, headers, bodyData) {
  return new Promise((resolve, reject) => {
    let req = `${method} ${pathStr} HTTP/1.1\r\nHost: ${hostname}\r\n`;
    for (const [k, v] of Object.entries(headers)) req += `${k}: ${v}\r\n`;
    if (bodyData) req += `Content-Length: ${Buffer.byteLength(bodyData)}\r\n`;
    req += `Connection: close\r\n\r\n`;
    tlsSocket.write(req);
    if (bodyData) tlsSocket.write(bodyData);
    const chunks = [];
    tlsSocket.on('data', c => chunks.push(c));
    tlsSocket.on('end', () => {
      const raw = Buffer.concat(chunks).toString('binary');
      const idx = raw.indexOf('\r\n\r\n');
      if (idx < 0) return reject(new Error('no header boundary'));
      const hdr = raw.substring(0, idx);
      let body = raw.substring(idx + 4);
      if (/transfer-encoding:\s*chunked/i.test(hdr)) body = decodeChunked(body);
      const m = hdr.match(/HTTP\/1\.[01] (\d+)/);
      resolve({ status: m ? parseInt(m[1]) : 0, header: hdr, body: Buffer.from(body, 'binary') });
    });
    tlsSocket.on('error', reject);
    setTimeout(() => { tlsSocket.destroy(); reject(new Error('timeout')); }, 15000);
  });
}

function decodeChunked(raw) {
  const parts = []; let pos = 0;
  while (pos < raw.length) {
    const end = raw.indexOf('\r\n', pos);
    if (end < 0) break;
    const size = parseInt(raw.substring(pos, end).trim(), 16);
    if (isNaN(size) || size === 0) break;
    const start = end + 2;
    if (start + size > raw.length) { parts.push(raw.substring(start)); break; }
    parts.push(raw.substring(start, start + size));
    pos = start + size + 2;
  }
  return parts.join('');
}

async function httpsProto(url, bodyBuffer) {
  const u = new URL(url);
  try {
    const sock = await proxyTunnel(u.hostname);
    const resp = await rawRequest(sock, u.hostname, u.pathname, 'POST', {
      'Content-Type': 'application/proto',
      'connect-protocol-version': '1',
    }, bodyBuffer);
    return { ok: resp.status === 200, status: resp.status, buffer: resp.body };
  } catch (e) {
    return { ok: false, status: 0, error: e.message };
  }
}

async function httpsJson(url, body) {
  const u = new URL(url);
  const data = JSON.stringify(body);
  try {
    const sock = await proxyTunnel(u.hostname);
    const resp = await rawRequest(sock, u.hostname, u.pathname + u.search, 'POST', {
      'Content-Type': 'application/json',
    }, data);
    return { ok: resp.status === 200, status: resp.status, data: JSON.parse(resp.body.toString('utf8')) };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

// ═══ Firebase认证 + apiKey获取 ═══

async function firebaseLogin(email, password) {
  for (const key of FIREBASE_KEYS) {
    const url = `https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${key}`;
    const r = await httpsJson(url, { email, password, returnSecureToken: true, clientType: 'CLIENT_TYPE_WEB' });
    if (r.ok && r.data.idToken) return { ok: true, idToken: r.data.idToken, refreshToken: r.data.refreshToken, email: r.data.email || email };
    if (r.data?.error?.message) console.log(`  Firebase error (${key.slice(-4)}): ${r.data.error.message}`);
  }
  return { ok: false };
}

/** Firebase refreshToken → 新idToken (续命, 无需密码) */
async function firebaseRefresh(refreshToken) {
  for (const key of FIREBASE_KEYS) {
    const url = `https://securetoken.googleapis.com/v1/token?key=${key}`;
    const r = await httpsJson(url, { grant_type: 'refresh_token', refresh_token: refreshToken });
    if (r.ok && r.data.id_token) {
      return { ok: true, idToken: r.data.id_token, refreshToken: r.data.refresh_token || refreshToken };
    }
    if (r.data?.error?.message) console.log(`  Refresh error (${key.slice(-4)}): ${r.data.error.message}`);
  }
  return { ok: false };
}

async function registerUser(idToken) {
  const reqData = encodeProtoString(idToken);
  for (const url of REGISTER_URLS) {
    const r = await httpsProto(url, reqData);
    if (r.ok && r.buffer) {
      const apiKey = parseProtoString(r.buffer);
      if (apiKey && apiKey.startsWith('sk-ws-01-')) return apiKey;
    }
  }
  return null;
}

async function getPlanStatus(idToken) {
  const reqData = encodeProtoString(idToken);
  for (const url of PLAN_STATUS_URLS) {
    const r = await httpsProto(url, reqData);
    if (r.ok && r.buffer) return parsePlanStatus(r.buffer);
  }
  return null;
}

function parsePlanStatus(buf) {
  try {
    const outer = parseProtoMsg(buf);
    if (!outer[1]?.[0]?.bytes) return null;
    const ps = parseProtoMsg(outer[1][0].bytes);
    const result = {};
    // Quota
    const daily = ps[14]?.[0]?.value;
    const weekly = ps[15]?.[0]?.value;
    if (daily !== undefined) result.daily = daily;
    if (weekly !== undefined) result.weekly = weekly;
    // Plan
    if (ps[1]?.[0]?.bytes) {
      const pi = parseProtoMsg(ps[1][0].bytes);
      if (pi[2]?.[0]?.bytes) result.plan = Buffer.from(pi[2][0].bytes).toString('utf8');
    }
    // Credits
    const used = ps[6]?.[0]?.value || 0;
    const avail = ps[8]?.[0]?.value || 0;
    result.credits = Math.round(avail / 100 - used / 100);
    return result;
  } catch { return null; }
}

async function checkRateLimit(apiKey, modelUid) {
  // Encode: field1{field1: apiKey} + field3: modelUid
  const apiKeyBuf = Buffer.from(apiKey, 'utf8');
  const innerPayload = Buffer.concat([Buffer.from([0x0a]), encodeVarint(apiKeyBuf.length), apiKeyBuf]);
  const modelBuf = Buffer.from(modelUid, 'utf8');
  const reqData = Buffer.concat([
    Buffer.from([0x0a]), encodeVarint(innerPayload.length), innerPayload,
    Buffer.from([0x1a]), encodeVarint(modelBuf.length), modelBuf,
  ]);
  for (const url of CHECK_RL_URLS) {
    const r = await httpsProto(url, reqData);
    if (r.ok && r.buffer) {
      const fields = parseProtoMsg(r.buffer);
      return {
        hasCapacity: fields[1]?.[0]?.value !== 0,
        messagesRemaining: fields[3]?.[0]?.value ?? -1,
        maxMessages: fields[4]?.[0]?.value ?? -1,
        resetsInSeconds: fields[5]?.[0]?.value ?? 0,
      };
    }
  }
  return null;
}

// ═══ 账号池 ═══

function loadAccounts() {
  const p = process.platform;
  let gsPath;
  if (p === 'win32') {
    gsPath = path.join(process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'),
      'Windsurf', 'User', 'globalStorage', 'undefined_publisher.windsurf-login-helper');
  } else if (p === 'darwin') {
    gsPath = path.join(os.homedir(), 'Library', 'Application Support', 'Windsurf', 'User', 'globalStorage', 'undefined_publisher.windsurf-login-helper');
  } else {
    gsPath = path.join(os.homedir(), '.config', 'Windsurf', 'User', 'globalStorage', 'undefined_publisher.windsurf-login-helper');
  }
  const gsBase = gsPath.replace(/[/\\][^/\\]+$/, ''); // parent: globalStorage/
  const candidates = [
    path.join(gsPath, 'windsurf-login-accounts.json'),
    path.join(gsBase, 'zhouyoukang.windsurf-assistant', 'windsurf-login-accounts.json'),
    path.join(gsBase, 'undefined_publisher.windsurf-assistant', 'windsurf-login-accounts.json'),
    path.join(gsBase, 'windsurf-login-accounts.json'),
  ];
  for (const file of candidates) {
    if (fs.existsSync(file)) {
      console.log(`[ACCOUNTS] found: ${file}`);
      return JSON.parse(fs.readFileSync(file, 'utf8'));
    }
  }
  console.log(`账号文件不存在, 已搜索: ${candidates.map(c => path.basename(path.dirname(c))).join(', ')}`);
  return [];
}

// ═══ KeyPool — 所有apiKey预热池 · 活水永续 ═══

const TOKEN_TTL_MS = 45 * 60 * 1000;       // 45min刷新 (idToken有效期50min, 留5min裕量)
const QUOTA_REFRESH_MS = 10 * 60 * 1000;    // 10min配额刷新
const SAVE_DEBOUNCE_MS = 5000;              // 5s防抖写盘

class KeyPool {
  constructor() {
    this.keys = new Map(); // email → { apiKey, idToken, refreshToken, quota, lastCheck, lastRefresh, rateLimited, quotaCostAccum }
    this._refreshTimer = null;
    this._saveTimer = null;
    this._refreshing = false;
    this.refreshStats = { total: 0, success: 0, fail: 0, lastRun: 0 };
    this._load();
  }

  _load() {
    try {
      if (fs.existsSync(KEYPOOL_FILE)) {
        const data = JSON.parse(fs.readFileSync(KEYPOOL_FILE, 'utf8'));
        for (const [email, entry] of Object.entries(data)) {
          this.keys.set(email, entry);
        }
        console.log(`[KeyPool] loaded ${this.keys.size} keys from cache`);
      }
    } catch {}
  }

  save() {
    try {
      if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
      const obj = {};
      this.keys.forEach((v, k) => { obj[k] = v; });
      fs.writeFileSync(KEYPOOL_FILE, JSON.stringify(obj, null, 2), 'utf8');
    } catch (e) { console.log(`[KeyPool] save error: ${e.message}`); }
  }

  /** 防抖写盘: 高频操作不每次都写磁盘 */
  debounceSave() {
    if (this._saveTimer) clearTimeout(this._saveTimer);
    this._saveTimer = setTimeout(() => this.save(), SAVE_DEBOUNCE_MS);
  }

  get(email) { return this.keys.get(email); }
  set(email, entry) { this.keys.set(email, entry); }

  /** 通过apiKey找到对应的entry */
  findByApiKey(apiKey) {
    for (const [email, entry] of this.keys) {
      if (entry.apiKey === apiKey) return { email, entry };
    }
    return null;
  }
  
  /** 选择最优账号 (按quota加权) */
  selectBest(excludeKey = null, modelUid = null) {
    let best = null, bestScore = -1;
    for (const [email, entry] of this.keys) {
      if (!entry.apiKey) continue;
      if (entry.apiKey === excludeKey) continue;
      if (entry.rateLimited && Date.now() < entry.rateLimitedUntil) continue;
      
      const daily = entry.quota?.daily ?? 100;
      const weekly = entry.quota?.weekly ?? 100;
      const effective = Math.min(daily, weekly);
      if (effective <= 0) continue;
      
      const score = effective;
      if (score > bestScore) { bestScore = score; best = entry; }
    }
    return best;
  }

  /** 标记rate limited */
  markRateLimited(apiKey, seconds = 1200) {
    for (const [, entry] of this.keys) {
      if (entry.apiKey === apiKey) {
        entry.rateLimited = true;
        entry.rateLimitedUntil = Date.now() + seconds * 1000;
        this.debounceSave();
        return;
      }
    }
  }

  /** 实时配额扣减: 从gRPC响应中提取的quota_cost_basis_points */
  deductQuota(apiKey, basisPoints) {
    const found = this.findByApiKey(apiKey);
    if (!found) return;
    const { entry } = found;
    if (!entry.quota) entry.quota = {};
    // basis_points: 100bp = 1% daily quota
    const dailyCost = basisPoints / 100;
    entry.quota.daily = Math.max(0, (entry.quota.daily ?? 100) - dailyCost);
    // weekly cost: 日配额/周配额比例 (empirical: weekly ~ daily * 0.3-0.5)
    const weeklyCost = dailyCost * 0.35;
    entry.quota.weekly = Math.max(0, (entry.quota.weekly ?? 100) - weeklyCost);
    entry.quotaCostAccum = (entry.quotaCostAccum || 0) + basisPoints;
    entry.lastQuotaUpdate = Date.now();
    this.debounceSave();
  }

  /** 标记配额耗尽 */
  markQuotaExhausted(apiKey) {
    const found = this.findByApiKey(apiKey);
    if (!found) return;
    found.entry.quota = { ...(found.entry.quota || {}), daily: 0, weekly: 0 };
    found.entry.rateLimited = true;
    found.entry.rateLimitedUntil = Date.now() + 3600 * 1000; // 1h cooldown
    this.debounceSave();
  }

  // ═══ 活水永续: refreshToken自动续命 ═══

  /** 启动自动刷新循环 (道法自然 · 水流不息) */
  startAutoRefresh() {
    if (this._refreshTimer) return;
    console.log(`[KeyPool] 活水启动: 每${TOKEN_TTL_MS / 60000}min刷新idToken, 每${QUOTA_REFRESH_MS / 60000}min刷新配额`);
    // 立即检查一次stale tokens
    this._autoRefreshCycle();
    this._refreshTimer = setInterval(() => this._autoRefreshCycle(), TOKEN_TTL_MS);
  }

  stopAutoRefresh() {
    if (this._refreshTimer) { clearInterval(this._refreshTimer); this._refreshTimer = null; }
    if (this._saveTimer) { clearTimeout(this._saveTimer); this._saveTimer = null; this.save(); }
  }

  async _autoRefreshCycle() {
    if (this._refreshing) return; // 防重入
    this._refreshing = true;
    const now = Date.now();
    this.refreshStats.lastRun = now;
    let refreshed = 0, failed = 0, quotaUpdated = 0;

    for (const [email, entry] of this.keys) {
      if (!entry.refreshToken) continue;
      
      const tokenAge = now - (entry.lastRefresh || entry.lastCheck || 0);
      const quotaAge = now - (entry.lastQuotaUpdate || entry.lastCheck || 0);
      
      // Token续命: idToken即将过期(>45min)
      if (tokenAge > TOKEN_TTL_MS) {
        try {
          const result = await firebaseRefresh(entry.refreshToken);
          if (result.ok) {
            entry.idToken = result.idToken;
            entry.refreshToken = result.refreshToken;
            entry.lastRefresh = now;
            refreshed++;
            
            // 顺便刷新apiKey (RegisterUser是幂等的, 同idToken返回同apiKey)
            const apiKey = await registerUser(result.idToken);
            if (apiKey) entry.apiKey = apiKey;
          } else {
            failed++;
          }
        } catch (e) {
          failed++;
        }
      }
      
      // 配额刷新: 每10min查一次真实配额
      if (quotaAge > QUOTA_REFRESH_MS && entry.idToken) {
        try {
          const status = await getPlanStatus(entry.idToken);
          if (status) {
            entry.quota = { ...entry.quota, ...status };
            entry.lastQuotaUpdate = now;
            // 清除过期的rate limit标记
            if (entry.rateLimited && entry.quota.daily > 5 && entry.quota.weekly > 5) {
              entry.rateLimited = false;
              entry.rateLimitedUntil = 0;
            }
            quotaUpdated++;
          }
        } catch {}
      }
      
      // 节流: 每个账号间隔100ms, 避免打满Firebase API
      await new Promise(r => setTimeout(r, 100));
    }

    this.refreshStats.total++;
    this.refreshStats.success += refreshed;
    this.refreshStats.fail += failed;
    this._refreshing = false;

    if (refreshed + failed + quotaUpdated > 0) {
      console.log(`[REFRESH] cycle #${this.refreshStats.total}: token=${refreshed}ok/${failed}fail quota=${quotaUpdated}updated`);
      this.save();
    }
  }

  stats() {
    let total = 0, ready = 0, limited = 0, noKey = 0, stale = 0;
    let sumDaily = 0, sumWeekly = 0;
    const now = Date.now();
    for (const [, entry] of this.keys) {
      total++;
      if (!entry.apiKey) { noKey++; continue; }
      if (entry.rateLimited && now < entry.rateLimitedUntil) { limited++; continue; }
      // Token stale check
      const tokenAge = now - (entry.lastRefresh || entry.lastCheck || 0);
      if (tokenAge > 55 * 60 * 1000 && !entry.refreshToken) { stale++; }
      ready++;
      sumDaily += entry.quota?.daily ?? 100;
      sumWeekly += entry.quota?.weekly ?? 100;
    }
    return {
      total, ready, limited, noKey, stale,
      avgDaily: ready ? Math.round(sumDaily / ready) : 0,
      avgWeekly: ready ? Math.round(sumWeekly / ready) : 0,
      refresh: this.refreshStats,
    };
  }
}

// ═══ 速率桶追踪器 — 模拟服务端per-(apiKey, modelUid)速率桶 ═══

/**
 * 服务端真相 (v14.0实测更新):
 *   - 每个(apiKey, modelUid)有独立的滑动窗口速率桶
 *   - 窗口已缩至~10min (实测"Resets in: 9m22s"=562s)
 *     ACU=10x(Opus T1M) → ~1-2条/10min
 *     ACU=8x(Opus Thinking) → ~1-2条/10min
 *     ACU=6x(Opus) → ~2条/10min
 *     ACU=1x(Haiku/Flash) → ~15条/10min
 *   - 6个Opus变体共享同一桶
 *   - 触发后返回 gRPC PermissionDenied + "Reached message rate limit"
 *   - Resets in: ~9-12min (滑动窗口, 实测9m22s)
 */
class RateBucketTracker {
  constructor() {
    // bucketKey = `${apiKey_prefix}:${modelGroup}` → { msgs: [{ts}], capacity, windowMs }
    this.buckets = new Map();
    this.WINDOW_MS = 25 * 60 * 1000; // 25min — v3.11: T1M实测22m13s(1333s), 25min保守窗口覆盖所有Opus变体
    this.MODEL_CAPACITY = {
      'opus-t1m': 1,    // claude-opus-4-6-thinking-1m, claude-opus-4-6-1m (v14.0: 3→1)
      'opus-thinking': 1, // claude-opus-4-6-thinking (v14.0: 4→1)
      'opus': 1,         // claude-opus-4-6 (v14.0: 5→1, 每条即切)
      'opus-fast': 1,    // claude-opus-4-6-thinking-fast, claude-opus-4-6-fast (v14.0: 2→1)
      'sonnet': 10,      // claude-sonnet-4-* (v14.0: 15→10, 保守)
      'haiku': 20,       // claude-haiku-* (v14.0: 30→20)
      'flash': 20,       // gemini-*-flash-* (v14.0: 30→20)
      'gpt': 8,          // gpt-* (v14.0: 10→8)
      'swe': 999,        // swe-* (ACU=0, effectively unlimited)
      'default': 8,      // (v14.0: 10→8)
    };
    // Opus变体→统一桶组 (服务端共享桶)
    this.OPUS_GROUP = new Set([
      'claude-opus-4-6-thinking-1m', 'claude-opus-4-6-thinking',
      'claude-opus-4-6-1m', 'claude-opus-4-6',
      'claude-opus-4-6-thinking-fast', 'claude-opus-4-6-fast',
    ]);
  }

  /** 将modelUid映射到桶组 */
  _modelGroup(modelUid) {
    if (!modelUid) return 'default';
    if (this.OPUS_GROUP.has(modelUid)) {
      if (modelUid.includes('1m') || modelUid.includes('thinking-1m')) return 'opus-t1m';
      if (modelUid.includes('fast')) return 'opus-fast';
      if (modelUid.includes('thinking')) return 'opus-thinking';
      return 'opus';
    }
    if (modelUid.includes('sonnet')) return 'sonnet';
    if (modelUid.includes('haiku')) return 'haiku';
    if (modelUid.includes('flash')) return 'flash';
    if (modelUid.includes('gpt')) return 'gpt';
    if (modelUid.includes('swe')) return 'swe';
    return 'default';
  }

  _bucketKey(apiKey, modelUid) {
    const prefix = apiKey ? apiKey.substring(0, 20) : '?';
    // Opus变体共享桶 → 统一到'opus'组
    const group = this.OPUS_GROUP.has(modelUid) ? 'opus' : this._modelGroup(modelUid);
    return `${prefix}:${group}`;
  }

  /** 记录一次请求发送 */
  recordRequest(apiKey, modelUid) {
    const key = this._bucketKey(apiKey, modelUid);
    if (!this.buckets.has(key)) {
      const group = this.OPUS_GROUP.has(modelUid) ? 'opus' : this._modelGroup(modelUid);
      // Opus共享桶取最小容量
      let capacity = this.MODEL_CAPACITY[group] || this.MODEL_CAPACITY.default;
      if (this.OPUS_GROUP.has(modelUid)) capacity = this.MODEL_CAPACITY['opus-t1m']; // 最保守
      this.buckets.set(key, { msgs: [], capacity, windowMs: this.WINDOW_MS, group });
    }
    const bucket = this.buckets.get(key);
    bucket.msgs.push({ ts: Date.now() });
    this._cleanup(bucket);
  }

  /** 记录服务端返回的rate limit错误 (自适应校准) */
  recordRateLimit(apiKey, modelUid, resetsInSeconds) {
    const key = this._bucketKey(apiKey, modelUid);
    if (!this.buckets.has(key)) {
      this.buckets.set(key, { msgs: [], capacity: 0, windowMs: this.WINDOW_MS, group: this._modelGroup(modelUid), calibrations: [] });
    }
    const bucket = this.buckets.get(key);
    const now = Date.now();
    bucket.rateLimitedUntil = now + (resetsInSeconds || 1200) * 1000;
    bucket.hitCount = (bucket.hitCount || 0) + 1;

    // ═══ 自适应校准: 从实测数据学习真实容量和窗口 ═══
    const activeMsgs = this._activeCount(bucket);

    // 校准1: 容量下调 — 触发RL时的活跃消息数即为真实容量上限
    if (activeMsgs > 0 && activeMsgs <= bucket.capacity) {
      const oldCap = bucket.capacity;
      bucket.capacity = Math.max(1, activeMsgs - 1); // 保守: 减1作为安全裕量
      if (oldCap !== bucket.capacity) {
        console.log(`[CALIBRATE] ${key}: capacity ${oldCap}→${bucket.capacity} (hit@${activeMsgs}msgs)`);
      }
    }

    // 校准2: 窗口学习 — 从resetSeconds推算真实窗口长度
    if (resetsInSeconds > 0) {
      if (!bucket.calibrations) bucket.calibrations = [];
      bucket.calibrations.push({ ts: now, resetSec: resetsInSeconds, activeMsgs });
      // 保留最近10次校准数据
      if (bucket.calibrations.length > 10) bucket.calibrations.shift();
      // 如果有足够数据, 计算平均窗口
      if (bucket.calibrations.length >= 1) { // v3.11: 1次校准即生效(速学)
        const avgReset = bucket.calibrations.reduce((s, c) => s + c.resetSec, 0) / bucket.calibrations.length;
        // 窗口 ≈ 最大resetSeconds (因为reset是剩余时间, 窗口=最大reset)
        const maxReset = Math.max(...bucket.calibrations.map(c => c.resetSec));
        const calibratedWindow = maxReset * 1000;
        if (Math.abs(calibratedWindow - bucket.windowMs) > 60000) { // 差异>1min才更新
          console.log(`[CALIBRATE] ${key}: window ${Math.round(bucket.windowMs/60000)}m→${Math.round(calibratedWindow/60000)}m (avg_reset=${Math.round(avgReset)}s)`);
          bucket.windowMs = calibratedWindow;
        }
      }
    }
  }

  /** 检查(apiKey, modelUid)是否可发送 */
  hasCapacity(apiKey, modelUid) {
    const key = this._bucketKey(apiKey, modelUid);
    const bucket = this.buckets.get(key);
    if (!bucket) return true; // 无记录 = 可发送
    if (bucket.rateLimitedUntil && Date.now() < bucket.rateLimitedUntil) return false;
    this._cleanup(bucket);
    return this._activeCount(bucket) < bucket.capacity;
  }

  /** 获取(apiKey, modelUid)的剩余容量 */
  remaining(apiKey, modelUid) {
    const key = this._bucketKey(apiKey, modelUid);
    const bucket = this.buckets.get(key);
    if (!bucket) return 999;
    if (bucket.rateLimitedUntil && Date.now() < bucket.rateLimitedUntil) return 0;
    this._cleanup(bucket);
    return Math.max(0, bucket.capacity - this._activeCount(bucket));
  }

  /** 获取所有桶的快照 (用于Dashboard) */
  snapshot() {
    const snap = [];
    const now = Date.now();
    for (const [key, bucket] of this.buckets) {
      this._cleanup(bucket);
      snap.push({
        key,
        group: bucket.group,
        active: this._activeCount(bucket),
        capacity: bucket.capacity,
        rateLimited: bucket.rateLimitedUntil ? now < bucket.rateLimitedUntil : false,
        resetsIn: bucket.rateLimitedUntil ? Math.max(0, Math.round((bucket.rateLimitedUntil - now) / 1000)) : 0,
        hitCount: bucket.hitCount || 0,
      });
    }
    return snap;
  }

  _activeCount(bucket) { return bucket.msgs.filter(m => Date.now() - m.ts < bucket.windowMs).length; }
  _cleanup(bucket) { const cutoff = Date.now() - bucket.windowMs; bucket.msgs = bucket.msgs.filter(m => m.ts > cutoff); }
}

/**
 * 模型感知路由器 — 调配额度而非账号，调配底层而非表象
 * 
 * 本质: 每个请求独立决策，选择最优(apiKey, modelUid)组合
 *   1. 速率桶有容量? (per-apiKey-per-model)
 *   2. 配额充足? (per-apiKey daily/weekly)
 *   3. 未被全局rate limit?
 *   → 加权评分 → 选最优
 */
class ModelAwareRouter {
  constructor(keyPool, bucketTracker) {
    this.pool = keyPool;
    this.tracker = bucketTracker;
    this.routeCount = 0;
    this.retryCount = 0;
    this.modelStats = new Map(); // modelUid → { requests, retries, rateLimits }
  }

  /**
   * 为请求选择最优apiKey
   * @param {string} currentApiKey - LS当前使用的apiKey
   * @param {string} modelUid - 请求的模型
   * @returns {{ apiKey, email, score, reason }} 或 null
   */
  route(currentApiKey, modelUid) {
    this.routeCount++;
    const modelGroup = modelUid || 'unknown';
    if (!this.modelStats.has(modelGroup)) this.modelStats.set(modelGroup, { requests: 0, retries: 0, rateLimits: 0 });
    this.modelStats.get(modelGroup).requests++;

    let best = null, bestScore = -Infinity;
    const now = Date.now();
    const candidates = [];

    for (const [email, entry] of this.pool.keys) {
      if (!entry.apiKey) continue;

      // Gate 1: 全局rate limit (账号级)
      if (entry.rateLimited && now < entry.rateLimitedUntil) continue;

      // Gate 2: 配额检查
      const daily = entry.quota?.daily ?? 100;
      const weekly = entry.quota?.weekly ?? 100;
      const effective = Math.min(daily, weekly);
      if (effective <= 0) continue;

      // Gate 3: per-model速率桶
      const bucketOk = this.tracker.hasCapacity(entry.apiKey, modelUid);
      const bucketRemaining = this.tracker.remaining(entry.apiKey, modelUid);

      // 评分公式: 综合配额 + 速率桶余量 + 偏好当前apiKey(减少不必要替换)
      let score = 0;
      score += effective * 0.4;                         // 配额权重40%
      score += Math.min(bucketRemaining, 10) * 5;      // 速率桶余量权重(capped)
      if (!bucketOk) score -= 1000;                     // 桶满 = 严重惩罚
      if (entry.apiKey === currentApiKey) score += 2;   // 轻微偏好当前key(减少无谓切换)

      candidates.push({ email, entry, score, bucketOk, bucketRemaining, effective });
      if (score > bestScore) { bestScore = score; best = { email, entry, score, bucketOk, bucketRemaining, effective }; }
    }

    if (!best || !best.bucketOk) {
      // 所有桶都满了 → 选配额最高的(等桶自然恢复)
      const fallback = candidates.filter(c => c.effective > 0).sort((a, b) => b.effective - a.effective)[0];
      if (fallback) {
        return { apiKey: fallback.entry.apiKey, email: fallback.email, score: fallback.score, reason: 'fallback-quota-best' };
      }
      return null; // 所有账号耗尽
    }

    return {
      apiKey: best.entry.apiKey,
      email: best.email,
      score: best.score,
      reason: best.entry.apiKey === currentApiKey ? 'keep-current' : 'model-aware-route',
    };
  }

  /** 处理rate limit错误 → 更新桶 + 返回重试apiKey */
  handleRateLimit(failedApiKey, modelUid, resetsInSeconds) {
    this.retryCount++;
    if (this.modelStats.has(modelUid)) this.modelStats.get(modelUid).rateLimits++;
    this.tracker.recordRateLimit(failedApiKey, modelUid, resetsInSeconds);
    // 选择另一个有容量的账号
    return this.route(failedApiKey, modelUid);
  }

  /** 路由统计 */
  stats() {
    const models = {};
    for (const [uid, s] of this.modelStats) models[uid] = s;
    return {
      totalRoutes: this.routeCount,
      totalRetries: this.retryCount,
      modelStats: models,
      buckets: this.tracker.snapshot(),
    };
  }
}

/**
 * gRPC响应监控器 — 解析响应流，检测错误，提取配额变化
 * 
 * 本质: 水面之下的感知 — 每个响应都携带着服务端的真实状态
 *   - gRPC错误 → PermissionDenied = rate limit
 *   - 正常响应 → 可能含quota_cost_basis_points (F30)
 *   - 流式响应 → 逐chunk转发，同时窥探
 */
const RATE_LIMIT_PATTERNS = [
  /Reached message rate limit/i,
  /rate.?limit/i,
  /Permission denied/i,
  /quota.?exhaust/i,
  /RESOURCE_EXHAUSTED/i,
];

function detectRateLimitInResponse(responseBytes) {
  try {
    const text = responseBytes.toString('utf8');
    for (const pat of RATE_LIMIT_PATTERNS) {
      if (pat.test(text)) {
        // 提取reset时间
        const resetMatch = text.match(/Resets?\s*in[:\s]*(\d+)m\s*(\d+)s/i);
        const resetSeconds = resetMatch ? parseInt(resetMatch[1]) * 60 + parseInt(resetMatch[2]) : 1200;
        return { detected: true, resetSeconds, pattern: pat.source };
      }
    }
  } catch {}
  return { detected: false };
}

function detectQuotaExhausted(responseBytes) {
  try {
    const text = responseBytes.toString('utf8');
    if (/quota.?exhaust/i.test(text) && !/rate.?limit/i.test(text)) {
      return { detected: true, type: 'quota_exhausted' };
    }
  } catch {}
  return { detected: false };
}

/**
 * 从gRPC响应流中提取配额成本 — 水面之下最深层的感知
 * 
 * CortexStepMetadata (逆向自workbench.js):
 *   F25: cumulative_tokens_at_step (uint64) — 累计token数
 *   F29: acu_cost (double/fixed64)          — ACU成本
 *   F30: quota_cost_basis_points (int32)    — ★配额成本(基点, 100bp=1%)
 *   F31: overage_cost_cents (int32)         — 超额成本(美分)
 *
 * gRPC流式响应格式: 5字节frame头(compressed_flag + length) + protobuf payload
 * 响应中嵌套多层message, F30在深层CortexStepMetadata中
 */
function extractQuotaCostFromResponse(responseBytes) {
  const result = { quotaCostBp: 0, cumulativeTokens: 0, acuCost: 0, overageCents: 0 };
  try {
    const buf = Buffer.isBuffer(responseBytes) ? responseBytes : Buffer.from(responseBytes);
    // gRPC帧可能有多个, 遍历所有帧
    let pos = 0;
    while (pos + 5 <= buf.length) {
      // gRPC frame: 1byte compressed + 4byte BE length
      const frameLen = buf.readUInt32BE(pos + 1);
      if (frameLen <= 0 || pos + 5 + frameLen > buf.length) break;
      const framePayload = buf.slice(pos + 5, pos + 5 + frameLen);
      _scanForQuotaFields(framePayload, result, 0);
      pos += 5 + frameLen;
    }
    // 如果没有gRPC帧头, 尝试直接扫描整个buffer
    if (pos === 0 && buf.length > 10) {
      _scanForQuotaFields(buf, result, 0);
    }
  } catch {}
  return result;
}

/** 递归扫描protobuf寻找F25/F29/F30/F31 (最多4层深) */
function _scanForQuotaFields(buf, result, depth) {
  if (depth > 4 || buf.length < 2) return;
  try {
    const fields = parseProtoMsg(buf);
    // F30: quota_cost_basis_points (varint)
    if (fields[30]?.[0]?.value !== undefined) {
      const bp = fields[30][0].value;
      if (bp > 0 && bp < 100000) result.quotaCostBp = Math.max(result.quotaCostBp, bp);
    }
    // F25: cumulative_tokens (varint)
    if (fields[25]?.[0]?.value !== undefined) {
      result.cumulativeTokens = Math.max(result.cumulativeTokens, fields[25][0].value);
    }
    // F31: overage_cost_cents (varint)
    if (fields[31]?.[0]?.value !== undefined) {
      result.overageCents = Math.max(result.overageCents, fields[31][0].value);
    }
    // 递归: 扫描所有length-delimited子消息
    for (const [, entries] of Object.entries(fields)) {
      for (const entry of entries) {
        if (entry.bytes && entry.bytes.length > 5) {
          _scanForQuotaFields(Buffer.from(entry.bytes), result, depth + 1);
        }
      }
    }
  } catch {}
}

// ═══ CA证书生成 ═══

function generateCA() {
  if (!fs.existsSync(CERT_DIR)) fs.mkdirSync(CERT_DIR, { recursive: true });
  const caKeyFile = path.join(CERT_DIR, 'ca.key');
  const caCertFile = path.join(CERT_DIR, 'ca.crt');
  
  if (fs.existsSync(caKeyFile) && fs.existsSync(caCertFile)) {
    console.log('[CERT] CA证书已存在');
    return { key: fs.readFileSync(caKeyFile), cert: fs.readFileSync(caCertFile) };
  }

  console.log('[CERT] 生成自签名CA证书...');
  // 使用Node.js crypto生成RSA密钥对
  const { privateKey, publicKey } = crypto.generateKeyPairSync('rsa', {
    modulusLength: 2048,
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
  });
  
  // 自签名CA需要openssl (Windows通常在Git for Windows中)
  // 写入密钥
  fs.writeFileSync(caKeyFile, privateKey);
  
  // 生成自签名证书
  const confFile = path.join(CERT_DIR, 'ca.cnf');
  fs.writeFileSync(confFile, `[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_ca
prompt = no

[req_distinguished_name]
CN = WAM Transparent Proxy CA
O = WAM
C = CN

[v3_ca]
basicConstraints = critical,CA:TRUE
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
`);
  
  try {
    // Find openssl: Git for Windows bundled → PATH → fail
    let opensslBin = 'openssl';
    const gitOpenssl = 'C:\\Program Files\\Git\\usr\\bin\\openssl.exe';
    if (process.platform === 'win32' && fs.existsSync(gitOpenssl)) opensslBin = `"${gitOpenssl}"`;
    execSync(`${opensslBin} req -new -x509 -days 3650 -key "${caKeyFile}" -out "${caCertFile}" -config "${confFile}"`, { stdio: 'pipe' });
    console.log(`[CERT] CA证书生成成功: ${caCertFile}`);
    console.log('[CERT] 请将CA证书安装到系统信任存储:');
    console.log(`  Windows: certutil -addstore Root "${caCertFile}"`);
    console.log(`  或设置环境变量: NODE_EXTRA_CA_CERTS=${caCertFile}`);
    return { key: privateKey, cert: fs.readFileSync(caCertFile) };
  } catch (e) {
    console.log(`[CERT] openssl不可用: ${e.message}`);
    console.log('[CERT] 请安装Git for Windows (自带openssl) 或单独安装openssl');
    return null;
  }
}

/** 为指定域名生成TLS证书 (使用CA签名) */
function generateDomainCert(domain, caKey, caCert) {
  const domainKeyFile = path.join(CERT_DIR, `${domain}.key`);
  const domainCertFile = path.join(CERT_DIR, `${domain}.crt`);
  
  if (fs.existsSync(domainKeyFile) && fs.existsSync(domainCertFile)) {
    return { key: fs.readFileSync(domainKeyFile), cert: fs.readFileSync(domainCertFile) };
  }

  const caKeyFile = path.join(CERT_DIR, 'ca.key');
  const caCertFile = path.join(CERT_DIR, 'ca.crt');
  const csrFile = path.join(CERT_DIR, `${domain}.csr`);
  const extFile = path.join(CERT_DIR, `${domain}.ext`);
  
  // 生成域名密钥
  const { privateKey } = crypto.generateKeyPairSync('rsa', {
    modulusLength: 2048,
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
    publicKeyEncoding: { type: 'spki', format: 'pem' },
  });
  fs.writeFileSync(domainKeyFile, privateKey);
  
  // SAN扩展
  fs.writeFileSync(extFile, `[req]
distinguished_name = req_dn
req_extensions = v3_req
prompt = no

[req_dn]
CN = ${domain}

[v3_req]
subjectAltName = DNS:${domain},DNS:*.${domain}

[san]
subjectAltName = DNS:${domain},DNS:*.${domain}
`);
  
  try {
    let opensslBin = 'openssl';
    const gitOpenssl = 'C:\\Program Files\\Git\\usr\\bin\\openssl.exe';
    if (process.platform === 'win32' && fs.existsSync(gitOpenssl)) opensslBin = `"${gitOpenssl}"`;
    execSync(`${opensslBin} req -new -key "${domainKeyFile}" -out "${csrFile}" -config "${extFile}"`, { stdio: 'pipe' });
    execSync(`${opensslBin} x509 -req -in "${csrFile}" -CA "${caCertFile}" -CAkey "${caKeyFile}" -CAcreateserial -out "${domainCertFile}" -days 365 -extfile "${extFile}" -extensions san`, { stdio: 'pipe' });
    console.log(`[CERT] 域名证书生成: ${domain}`);
    return { key: privateKey, cert: fs.readFileSync(domainCertFile) };
  } catch (e) {
    console.log(`[CERT] 域名证书生成失败(${domain}): ${e.message}`);
    return null;
  }
}

// ═══ 透明代理服务器 ═══

class TransparentProxy {
  constructor(keyPool) {
    this.pool = keyPool;
    this.server = null;
    this.domainCerts = new Map();
    this.stats = { requests: 0, rewrites: 0, passthrough: 0, errors: 0, retries: 0, rateLimitsDetected: 0, quotaExhausted: 0 };
    this.caKey = null;
    this.caCert = null;
    // 底层引擎 — 水面之下
    this.bucketTracker = new RateBucketTracker();
    this.router = new ModelAwareRouter(keyPool, this.bucketTracker);
    this.requestLog = []; // 最近100条请求日志
    this.MAX_LOG = 200;
    this.MAX_RETRY = 3; // 单请求最大重试次数
  }

  async start() {
    // 加载CA证书
    const caKeyFile = path.join(CERT_DIR, 'ca.key');
    const caCertFile = path.join(CERT_DIR, 'ca.crt');
    if (!fs.existsSync(caKeyFile) || !fs.existsSync(caCertFile)) {
      console.log('[PROXY] CA证书不存在, 请先运行: node transparent_proxy.js keygen');
      return false;
    }
    this.caKey = fs.readFileSync(caKeyFile);
    this.caCert = fs.readFileSync(caCertFile);

    // 预生成所有目标域名的证书
    for (const domain of INTERCEPT_DOMAINS) {
      const cert = generateDomainCert(domain, this.caKey, this.caCert);
      if (cert) this.domainCerts.set(domain, cert);
    }

    // 创建HTTP代理服务器 (处理CONNECT请求 + 底层状态API)
    this.server = http.createServer((req, res) => {
      const url = new URL(req.url, `http://127.0.0.1:${PROXY_PORT}`);
      const p = url.pathname.replace(/\/$/, '') || '/';
      const cors = { 'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json' };
      const json = (data) => { res.writeHead(200, cors); res.end(JSON.stringify(data, null, 2)); };

      if (p === '/api/deep' || p === '/api/v3/deep') {
        // 水面之下的全景 — 速率桶 + 路由统计 + 请求日志 + 活水续命
        return json({
          status: 'ok', type: 'transparent-proxy-v3', version: '3.0.0',
          ...this.stats,
          pool: this.pool.stats(),
          router: this.router.stats(),
          recentRequests: this.requestLog.slice(-50),
        });
      }
      if (p === '/api/buckets') {
        return json({ buckets: this.bucketTracker.snapshot() });
      }
      if (p === '/api/routes') {
        return json(this.router.stats());
      }
      if (p === '/api/quota') {
        // 实时配额全景: 每个账号的配额+累计消耗+刷新状态
        const accounts = [];
        for (const [email, entry] of this.pool.keys) {
          if (!entry.apiKey) continue;
          accounts.push({
            email: email.substring(0, 25) + '...',
            apiKey: entry.apiKey.substring(0, 20) + '...',
            daily: entry.quota?.daily ?? '?',
            weekly: entry.quota?.weekly ?? '?',
            plan: entry.quota?.plan ?? '?',
            quotaCostAccum: entry.quotaCostAccum || 0,
            rateLimited: entry.rateLimited && Date.now() < entry.rateLimitedUntil,
            hasRefreshToken: !!entry.refreshToken,
            lastRefresh: entry.lastRefresh ? new Date(entry.lastRefresh).toISOString() : null,
            lastQuotaUpdate: entry.lastQuotaUpdate ? new Date(entry.lastQuotaUpdate).toISOString() : null,
          });
        }
        return json({ total: accounts.length, accounts });
      }
      // 默认: 兼容旧格式 + 新引擎概要
      json({
        status: 'ok', type: 'transparent-proxy-v3', version: '3.0.0',
        ...this.stats,
        pool: this.pool.stats(),
        routerRoutes: this.router.routeCount,
        routerRetries: this.router.retryCount,
        activeBuckets: this.bucketTracker.buckets.size,
      });
    });

    this.server.on('connect', (req, clientSocket, head) => {
      const [hostname, port] = req.url.split(':');
      
      if (INTERCEPT_DOMAINS.has(hostname) && this.domainCerts.has(hostname)) {
        // MITM: 拦截目标域名
        this._handleMITM(hostname, parseInt(port) || 443, clientSocket, head);
      } else {
        // 透传: 其他域名直接转发
        this._handlePassthrough(hostname, parseInt(port) || 443, clientSocket, head);
      }
    });

    return new Promise((resolve) => {
      this.server.listen(PROXY_PORT, '127.0.0.1', () => {
        console.log(`[PROXY] 透明代理启动 — http://127.0.0.1:${PROXY_PORT}`);
        console.log(`[PROXY] 拦截域名: ${[...INTERCEPT_DOMAINS].join(', ')}`);
        console.log(`[PROXY] apiKey池: ${this.pool.keys.size} 个账号`);
        console.log(`[PROXY] 设置代理: set HTTPS_PROXY=http://127.0.0.1:${PROXY_PORT}`);
        resolve(true);
      });
    });
  }

  _handleMITM(hostname, port, clientSocket, head) {
    const cert = this.domainCerts.get(hostname);
    if (!cert) return this._handlePassthrough(hostname, port, clientSocket, head);

    // 告诉客户端CONNECT成功
    clientSocket.write('HTTP/1.1 200 Connection Established\r\n\r\n');

    // 创建TLS服务器(用域名证书)
    const tlsServer = new tls.TLSSocket(clientSocket, {
      isServer: true,
      key: cert.key,
      cert: cert.cert,
      ca: this.caCert,
    });

    // 收集请求数据
    let requestData = Buffer.alloc(0);
    let headerParsed = false;
    let contentLength = 0;
    let headerEnd = -1;

    tlsServer.on('data', (chunk) => {
      requestData = Buffer.concat([requestData, chunk]);
      
      if (!headerParsed) {
        headerEnd = requestData.indexOf('\r\n\r\n');
        if (headerEnd < 0) return; // 等待更多数据
        headerParsed = true;
        const headerStr = requestData.slice(0, headerEnd).toString('utf8');
        const clMatch = headerStr.match(/content-length:\s*(\d+)/i);
        contentLength = clMatch ? parseInt(clMatch[1]) : 0;
      }

      const bodyStart = headerEnd + 4;
      const bodyReceived = requestData.length - bodyStart;
      
      if (bodyReceived >= contentLength) {
        // 完整请求已收到
        const headerBuf = requestData.slice(0, bodyStart);
        const bodyBuf = requestData.slice(bodyStart, bodyStart + contentLength);
        this._processRequest(hostname, headerBuf, bodyBuf, tlsServer);
        requestData = Buffer.alloc(0);
        headerParsed = false;
      }
    });

    tlsServer.on('error', (e) => {
      this.stats.errors++;
      console.log(`[MITM] TLS error (${hostname}): ${e.message}`);
    });
  }

  async _processRequest(hostname, headerBuf, bodyBuf, clientTls) {
    this.stats.requests++;
    const headerStr = headerBuf.toString('utf8');
    const firstLine = headerStr.split('\r\n')[0];
    const [method, pathStr] = firstLine.split(' ');
    const isProto = /content-type:\s*application\/proto/i.test(headerStr);
    const isChatMsg = pathStr && pathStr.includes('GetChatMessage');
    const isCheckRL = pathStr && pathStr.includes('CheckUserMessageRateLimit');

    // 提取请求元数据
    let oldKey = null, modelUid = null;
    if (isProto && bodyBuf.length > 0) {
      oldKey = extractApiKey(bodyBuf);
      modelUid = extractModelUid(bodyBuf);
    }

    const logEntry = {
      ts: Date.now(), hostname, path: pathStr, method,
      bodyLen: bodyBuf.length, isProto, modelUid,
      oldKey: oldKey ? oldKey.substring(0, 20) + '...' : null,
      newKey: null, rewritten: false, retried: false,
      responseStatus: 0, rateLimitDetected: false,
    };

    console.log(`[REQ] ${method} ${hostname}${pathStr} (${bodyBuf.length}B${isProto ? ' proto' : ''}${modelUid ? ' model=' + modelUid : ''})`);

    let finalBody = bodyBuf;
    let rewritten = false;
    let usedApiKey = oldKey;

    // ═══ 模型感知路由 — 调配额度而非账号 ═══
    if (isProto && bodyBuf.length > 0 && oldKey) {
      const routeResult = this.router.route(oldKey, modelUid);
      if (routeResult && routeResult.apiKey !== oldKey) {
        const newBody = replaceApiKeyInProtobuf(bodyBuf, routeResult.apiKey);
        if (newBody) {
          finalBody = newBody;
          rewritten = true;
          usedApiKey = routeResult.apiKey;
          this.stats.rewrites++;
          logEntry.rewritten = true;
          logEntry.newKey = routeResult.apiKey.substring(0, 20) + '...';
          logEntry.routeReason = routeResult.reason;
          console.log(`[ROUTE] ${oldKey.substring(0, 15)}→${routeResult.apiKey.substring(0, 15)} score=${routeResult.score.toFixed(1)} reason=${routeResult.reason} model=${modelUid || '?'}`);
        }
      } else if (routeResult) {
        logEntry.routeReason = routeResult.reason;
      }
    }

    if (!rewritten) this.stats.passthrough++;

    // 记录请求到速率桶 (用实际发送的apiKey)
    if (usedApiKey && modelUid && (isChatMsg || isCheckRL)) {
      this.bucketTracker.recordRequest(usedApiKey, modelUid);
    }

    // ═══ 转发 + 响应监控 + 自动重试 ═══
    await this._forwardWithRetry(hostname, headerStr, finalBody, bodyBuf, clientTls, usedApiKey, oldKey, modelUid, logEntry, 0);

    // 记录日志
    this.requestLog.push(logEntry);
    if (this.requestLog.length > this.MAX_LOG) this.requestLog.splice(0, this.requestLog.length - this.MAX_LOG);
  }

  /**
   * 转发请求到真实服务器，监控响应，rate limit时自动重试
   * 道法自然: 水遇石则绕 — rate limit即换路，用户无感知
   */
  async _forwardWithRetry(hostname, headerStr, finalBody, originalBody, clientTls, usedApiKey, originalKey, modelUid, logEntry, retryCount) {
    try {
      const realSock = await proxyTunnel(hostname);

      // 构建请求头 (可能Content-Length变了)
      let newHeader = headerStr;
      if (finalBody.length !== (logEntry.bodyLen || 0)) {
        newHeader = newHeader.replace(/content-length:\s*\d+/i, `Content-Length: ${finalBody.length}`);
      }

      realSock.write(Buffer.from(newHeader, 'utf8'));
      realSock.write(finalBody);

      // ═══ 响应监控: 收集响应，检测错误，决策重试 ═══
      const responseChunks = [];
      let responseSent = false;
      let headerReceived = false;
      let responseHeaderStr = '';

      realSock.on('data', (chunk) => {
        responseChunks.push(chunk);

        // 解析响应头
        if (!headerReceived) {
          const accumulated = Buffer.concat(responseChunks);
          const hdrEnd = accumulated.indexOf('\r\n\r\n');
          if (hdrEnd >= 0) {
            headerReceived = true;
            responseHeaderStr = accumulated.slice(0, hdrEnd).toString('utf8');
            const statusMatch = responseHeaderStr.match(/HTTP\/1\.[01] (\d+)/);
            logEntry.responseStatus = statusMatch ? parseInt(statusMatch[1]) : 0;

            // 非200响应 = 可能是错误，先收集完整响应再决策
            if (logEntry.responseStatus === 200) {
              // 正常响应: 立即开始流式转发
              responseSent = true;
              try { clientTls.write(accumulated); } catch {}
            }
            // 非200: 等待完整响应后检查是否需要重试
          }
        } else if (responseSent) {
          // 已确认正常响应，继续流式转发
          try { clientTls.write(chunk); } catch {}
        }
      });

      realSock.on('end', async () => {
        const fullResponse = Buffer.concat(responseChunks);

        if (responseSent) {
          // 正常流已在转发中，结束
          try { clientTls.end(); } catch {}

          // ═══ 水面之下最深层感知: 异步解析完整响应 ═══
          const hdrEnd = fullResponse.indexOf('\r\n\r\n');
          if (hdrEnd >= 0) {
            const respBody = fullResponse.slice(hdrEnd + 4);

            // 感知1: 隐含rate limit信号 (gRPC流式错误嵌入200中)
            const rlCheck = detectRateLimitInResponse(respBody);
            if (rlCheck.detected && usedApiKey) {
              console.log(`[DETECT] rate limit in 200 stream: ${rlCheck.pattern} reset=${rlCheck.resetSeconds}s`);
              this.stats.rateLimitsDetected++;
              logEntry.rateLimitDetected = true;
              this.bucketTracker.recordRateLimit(usedApiKey, modelUid, rlCheck.resetSeconds);
            }

            // 感知2: 配额耗尽信号
            const quotaCheck = detectQuotaExhausted(respBody);
            if (quotaCheck.detected && usedApiKey) {
              console.log(`[DETECT] quota exhausted in stream for ${usedApiKey.substring(0, 15)}`);
              this.stats.quotaExhausted++;
              this.pool.markQuotaExhausted(usedApiKey);
            }

            // 感知3: 配额成本提取 (F30 quota_cost_basis_points) — 实时扣减
            if (usedApiKey && respBody.length > 20) {
              const costInfo = extractQuotaCostFromResponse(respBody);
              if (costInfo.quotaCostBp > 0) {
                this.pool.deductQuota(usedApiKey, costInfo.quotaCostBp);
                this.stats.quotaCostExtracted = (this.stats.quotaCostExtracted || 0) + 1;
                logEntry.quotaCostBp = costInfo.quotaCostBp;
                logEntry.cumulativeTokens = costInfo.cumulativeTokens;
                console.log(`[QUOTA] ${usedApiKey.substring(0, 15)}: -${costInfo.quotaCostBp}bp (${(costInfo.quotaCostBp/100).toFixed(2)}%) tokens=${costInfo.cumulativeTokens}`);
              }
            }
          }
          return;
        }

        // ═══ 非200响应: 检查是否rate limit → 自动重试 ═══
        const hdrEnd = fullResponse.indexOf('\r\n\r\n');
        const respBody = hdrEnd >= 0 ? fullResponse.slice(hdrEnd + 4) : fullResponse;
        const rlCheck = detectRateLimitInResponse(respBody);
        const quotaCheck = detectQuotaExhausted(respBody);

        if (rlCheck.detected && retryCount < this.MAX_RETRY && usedApiKey) {
          // ═══ 水遇石则绕: rate limit → 换账号重试 (v3.1: modelUid可为null仍重试) ═══
          this.stats.rateLimitsDetected++;
          this.stats.retries++;
          logEntry.rateLimitDetected = true;
          logEntry.retried = true;
          console.log(`[RETRY] rate limit detected (${rlCheck.pattern} reset=${rlCheck.resetSeconds}s model=${modelUid||'?'}), retry #${retryCount + 1}/${this.MAX_RETRY}`);

          const retryRoute = this.router.handleRateLimit(usedApiKey, modelUid || 'opus', rlCheck.resetSeconds);
          if (retryRoute) {
            const retryBody = replaceApiKeyInProtobuf(originalBody, retryRoute.apiKey);
            if (retryBody) {
              logEntry.retryKey = retryRoute.apiKey.substring(0, 20) + '...';
              console.log(`[RETRY] rerouting → ${retryRoute.apiKey.substring(0, 15)} (${retryRoute.reason})`);
              if (modelUid) this.bucketTracker.recordRequest(retryRoute.apiKey, modelUid);
              return this._forwardWithRetry(hostname, headerStr, retryBody, originalBody, clientTls, retryRoute.apiKey, originalKey, modelUid, logEntry, retryCount + 1);
            }
          }
          console.log(`[RETRY] no alternative account available, forwarding error to client`);
        }

        if (quotaCheck.detected && usedApiKey) {
          this.stats.quotaExhausted++;
          this.pool.markRateLimited(usedApiKey, 3600);
          console.log(`[QUOTA] exhausted for ${usedApiKey.substring(0, 15)}, marked for 1h`);
        }

        // 无法重试 或 非rate limit错误 → 转发原始响应
        try { clientTls.write(fullResponse); clientTls.end(); } catch {}
      });

      realSock.on('error', (e) => {
        console.log(`[FWD] error: ${e.message}`);
        logEntry.error = e.message;
        if (!responseSent) {
          const errResp = `HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n`;
          try { clientTls.write(errResp); clientTls.end(); } catch {}
        } else {
          try { clientTls.end(); } catch {}
        }
      });
    } catch (e) {
      this.stats.errors++;
      console.log(`[FWD] tunnel failed: ${e.message}`);
      logEntry.error = e.message;
      const errResp = `HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n`;
      try { clientTls.write(errResp); clientTls.end(); } catch {}
    }
  }

  _handlePassthrough(hostname, port, clientSocket, head) {
    // Chain through upstream proxy (7890) for GFW bypass
    const upstreamReq = http.request({
      hostname: '127.0.0.1', port: LOCAL_PROXY_PORT,
      method: 'CONNECT', path: `${hostname}:${port}`, timeout: 10000
    });
    upstreamReq.on('connect', (res, upstreamSocket) => {
      if (res.statusCode !== 200) {
        upstreamSocket.destroy();
        clientSocket.end();
        return;
      }
      clientSocket.write('HTTP/1.1 200 Connection Established\r\n\r\n');
      if (head && head.length > 0) upstreamSocket.write(head);
      upstreamSocket.pipe(clientSocket);
      clientSocket.pipe(upstreamSocket);
      upstreamSocket.on('error', () => { try { clientSocket.end(); } catch {} });
      clientSocket.on('error', () => { try { upstreamSocket.end(); } catch {} });
    });
    upstreamReq.on('error', () => {
      // Fallback: try direct connect if upstream proxy unavailable
      const serverSocket = net.connect(port, hostname, () => {
        clientSocket.write('HTTP/1.1 200 Connection Established\r\n\r\n');
        if (head && head.length > 0) serverSocket.write(head);
        serverSocket.pipe(clientSocket);
        clientSocket.pipe(serverSocket);
      });
      serverSocket.on('error', () => clientSocket.end());
      clientSocket.on('error', () => serverSocket.end());
    });
    upstreamReq.on('timeout', () => { upstreamReq.destroy(); clientSocket.end(); });
    upstreamReq.end();
  }

  stop() {
    if (this.server) { this.server.close(); this.server = null; }
  }
}

// ═══ 命令行入口 ═══

async function cmdKeygen() {
  console.log('═══ 生成CA证书 ═══');
  const ca = generateCA();
  if (ca) {
    console.log('\n[OK] CA证书生成完成');
    // 预生成所有目标域名证书
    for (const domain of INTERCEPT_DOMAINS) {
      generateDomainCert(domain, ca.key, ca.cert);
    }
    console.log(`\n安装CA证书到系统信任:
  certutil -addstore Root "${path.join(CERT_DIR, 'ca.crt')}"
  
或设置Windsurf环境变量:
  NODE_EXTRA_CA_CERTS=${path.join(CERT_DIR, 'ca.crt')}
  
或禁用TLS验证(仅测试):
  NODE_TLS_REJECT_UNAUTHORIZED=0`);
  }
}

async function cmdWarmup() {
  console.log('═══ 预热apiKey池 ═══\n');
  const accounts = loadAccounts();
  if (accounts.length === 0) { console.log('没有找到账号'); return; }
  
  const pool = new KeyPool();
  let success = 0, fail = 0;
  const limit = parseInt(process.argv[3]) || accounts.length;
  
  console.log(`共 ${accounts.length} 个账号, 预热前 ${limit} 个\n`);
  
  for (let i = 0; i < Math.min(limit, accounts.length); i++) {
    const a = accounts[i];
    process.stdout.write(`[${i + 1}/${limit}] ${a.email.substring(0, 25)}... `);
    
    try {
      const login = await firebaseLogin(a.email, a.password);
      if (!login.ok) { console.log('❌ Firebase登录失败'); fail++; continue; }
      
      const apiKey = await registerUser(login.idToken);
      if (!apiKey) { console.log('❌ RegisterUser失败'); fail++; continue; }
      
      const status = await getPlanStatus(login.idToken);
      
      pool.set(a.email, {
        apiKey,
        idToken: login.idToken,
        refreshToken: login.refreshToken,
        quota: status || {},
        lastCheck: Date.now(),
        lastRefresh: Date.now(),
        rateLimited: false,
        rateLimitedUntil: 0,
        quotaCostAccum: 0,
      });
      
      const d = status?.daily ?? '?', w = status?.weekly ?? '?', plan = status?.plan ?? '?';
      console.log(`✅ ${apiKey.substring(0, 20)}... D${d}% W${w}% ${plan}`);
      success++;
    } catch (e) {
      console.log(`❌ ${e.message}`);
      fail++;
    }
  }
  
  pool.save();
  console.log(`\n═══ 预热完成: ${success} 成功, ${fail} 失败, 共 ${pool.keys.size} 个apiKey ═══`);
}

async function cmdTest() {
  console.log('═══ POC验证: apiKey替换可行性 ═══\n');
  
  const pool = new KeyPool();
  const keys = [...pool.keys.entries()].filter(([, v]) => v.apiKey);
  
  if (keys.length < 2) {
    console.log('需要至少2个apiKey, 请先运行: node transparent_proxy.js warmup');
    return;
  }
  
  const [emailA, entryA] = keys[0];
  const [emailB, entryB] = keys[1];
  
  console.log(`账号A: ${emailA} (D${entryA.quota?.daily ?? '?'}% W${entryA.quota?.weekly ?? '?'}%)`);
  console.log(`账号B: ${emailB} (D${entryB.quota?.daily ?? '?'}% W${entryB.quota?.weekly ?? '?'}%)\n`);
  
  // 测试1: 用账号A的apiKey查询rate limit
  console.log('--- 测试1: 用账号A的apiKey查CheckRateLimit ---');
  const rlA = await checkRateLimit(entryA.apiKey, 'claude-sonnet-4-6-thinking');
  console.log(`  结果: hasCapacity=${rlA?.hasCapacity}, remaining=${rlA?.messagesRemaining}, max=${rlA?.maxMessages}`);
  
  // 测试2: 用账号B的apiKey查询rate limit  
  console.log('\n--- 测试2: 用账号B的apiKey查CheckRateLimit ---');
  const rlB = await checkRateLimit(entryB.apiKey, 'claude-sonnet-4-6-thinking');
  console.log(`  结果: hasCapacity=${rlB?.hasCapacity}, remaining=${rlB?.messagesRemaining}, max=${rlB?.maxMessages}`);
  
  // 测试3: protobuf apiKey替换
  console.log('\n--- 测试3: protobuf apiKey字节级替换 ---');
  // 构造一个模拟的gRPC请求体(CheckRateLimit格式)
  const testApiKey = entryA.apiKey;
  const testModel = 'claude-sonnet-4-6-thinking';
  const apiKeyBuf = Buffer.from(testApiKey, 'utf8');
  const innerPayload = Buffer.concat([Buffer.from([0x0a]), encodeVarint(apiKeyBuf.length), apiKeyBuf]);
  const modelBuf = Buffer.from(testModel, 'utf8');
  const testBody = Buffer.concat([
    Buffer.from([0x0a]), encodeVarint(innerPayload.length), innerPayload,
    Buffer.from([0x1a]), encodeVarint(modelBuf.length), modelBuf,
  ]);
  
  console.log(`  原始body长度: ${testBody.length}`);
  console.log(`  原始apiKey: ${extractApiKey(testBody)?.substring(0, 30)}...`);
  
  const rewritten = replaceApiKeyInProtobuf(testBody, entryB.apiKey);
  if (rewritten) {
    console.log(`  替换后body长度: ${rewritten.length}`);
    console.log(`  替换后apiKey: ${extractApiKey(rewritten)?.substring(0, 30)}...`);
    console.log(`  长度变化: ${rewritten.length - testBody.length} bytes`);
    
    // 验证替换后的请求仍然可以被服务端接受
    console.log('\n--- 测试4: 替换后的请求发送到服务端 ---');
    for (const url of CHECK_RL_URLS) {
      const r = await httpsProto(url, rewritten);
      if (r.ok && r.buffer) {
        const fields = parseProtoMsg(r.buffer);
        const result = {
          hasCapacity: fields[1]?.[0]?.value !== 0,
          remaining: fields[3]?.[0]?.value ?? -1,
          max: fields[4]?.[0]?.value ?? -1,
        };
        console.log(`  ✅ 服务端接受替换后的请求! hasCapacity=${result.hasCapacity} remaining=${result.remaining}`);
        console.log(`\n═══ POC验证成功! apiKey替换可行! ═══`);
        console.log(`  → 服务端只看apiKey字段，不验证其他信息`);
        console.log(`  → 可以在网络层透明替换apiKey`);
        console.log(`  → 每个请求可使用不同账号的配额`);
        return;
      }
      console.log(`  ${url}: status=${r.status} ${r.error || ''}`);
    }
    console.log('  ⚠ 服务端请求失败(可能是网络问题)');
  } else {
    console.log('  ❌ apiKey替换失败');
  }
}

async function cmdServe() {
  console.log('═══ 启动透明gRPC代理 v3.0 — 活水永续 ═══\n');
  const pool = new KeyPool();
  const proxy = new TransparentProxy(pool);
  const ok = await proxy.start();
  if (!ok) return;

  // ═══ 启动活水永续: refreshToken自动续命 ═══
  const hasRefreshTokens = [...pool.keys.values()].filter(e => e.refreshToken).length;
  if (hasRefreshTokens > 0) {
    pool.startAutoRefresh();
    console.log(`[REFRESH] ${hasRefreshTokens}/${pool.keys.size} 账号有refreshToken, 活水已启动`);
  } else {
    console.log(`[WARN] 无refreshToken — 请重新 warmup 获取。idToken将在50min后过期。`);
  }
  
  // 打印Windsurf配置指引
  const caCert = path.join(CERT_DIR, 'ca.crt');
  console.log(`\n═══ 配置Windsurf使用代理 ═══`);
  console.log(`方法1 (推荐): 运行启动脚本`);
  console.log(`  node scripts/transparent_proxy.js launcher`);
  console.log(`\n方法2: 设置Windsurf settings.json:`);
  console.log(`  "http.proxy": "http://127.0.0.1:${PROXY_PORT}"`);
  console.log(`  "http.proxyStrictSSL": false`);
  console.log(`\n方法3: 环境变量启动Windsurf:`);
  console.log(`  set HTTPS_PROXY=http://127.0.0.1:${PROXY_PORT}`);
  console.log(`  set NODE_EXTRA_CA_CERTS=${caCert}`);
  console.log(`  windsurf.exe`);
  console.log(`\n═══ 代理已就绪，等待连接... ═══\n`);
  
  // 定期打印底层引擎状态 (含活水续命统计)
  setInterval(() => {
    const s = proxy.stats;
    const p = pool.stats();
    const r = proxy.router;
    const bk = proxy.bucketTracker.buckets.size;
    const qe = s.quotaCostExtracted || 0;
    const rf = p.refresh;
    console.log(`[STATS] req=${s.requests} route=${s.rewrites} pass=${s.passthrough} retry=${s.retries} rlDetect=${s.rateLimitsDetected} quotaCost=${qe} err=${s.errors} | pool: ${p.ready}/${p.total} stale=${p.stale} avgD=${p.avgDaily}% | refresh: #${rf.total} ok=${rf.success} fail=${rf.fail} | buckets=${bk} routes=${r.routeCount}`);
  }, 30000);
  
  // 优雅退出 (停止活水, 保存状态)
  const shutdown = () => {
    console.log('\n[PROXY] shutting down... saving state...');
    pool.stopAutoRefresh();
    proxy.stop();
    process.exit(0);
  };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

async function cmdStatus() {
  console.log('═══ KeyPool状态 ═══\n');
  const pool = new KeyPool();
  const s = pool.stats();
  console.log(`总计: ${s.total} 账号`);
  console.log(`就绪: ${s.ready} (有apiKey且未限流)`);
  console.log(`限流: ${s.limited}`);
  console.log(`无Key: ${s.noKey}`);
  console.log(`平均配额: D${s.avgDaily}% W${s.avgWeekly}%`);
  
  if (pool.keys.size > 0) {
    console.log('\n--- 详细 ---');
    let i = 0;
    for (const [email, entry] of pool.keys) {
      i++;
      const d = entry.quota?.daily ?? '?';
      const w = entry.quota?.weekly ?? '?';
      const plan = entry.quota?.plan ?? '?';
      const key = entry.apiKey ? entry.apiKey.substring(0, 20) + '...' : '(无)';
      const rl = entry.rateLimited && Date.now() < entry.rateLimitedUntil ? '🔴' : '🟢';
      console.log(`  ${rl} #${i} ${email.substring(0, 30).padEnd(30)} D${String(d).padStart(3)}% W${String(w).padStart(3)}% ${plan.padEnd(8)} ${key}`);
      if (i >= 20) { console.log(`  ... 还有 ${pool.keys.size - 20} 个`); break; }
    }
  }
}

// ═══ 主入口 ═══
const cmd = process.argv[2] || 'help';
const commands = {
  keygen: cmdKeygen,
  warmup: cmdWarmup,
  test: cmdTest,
  serve: cmdServe,
  status: cmdStatus,
};

async function cmdLauncher() {
  console.log('═══ 生成Windsurf启动脚本 ═══\n');
  const caCert = path.join(CERT_DIR, 'ca.crt').replace(/\//g, '\\');
  const proxyScript = path.resolve(__filename).replace(/\//g, '\\');
  
  // Find Windsurf executable
  const windsurfPaths = [
    'D:\\Windsurf\\Windsurf.exe',
    path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Windsurf', 'Windsurf.exe'),
    path.join(process.env.LOCALAPPDATA || '', 'Windsurf', 'Windsurf.exe'),
    'C:\\Program Files\\Windsurf\\Windsurf.exe',
  ];
  let windsurfExe = 'windsurf';
  for (const p of windsurfPaths) {
    if (fs.existsSync(p)) { windsurfExe = p; break; }
  }
  
  const batContent = `@echo off
REM 透明gRPC代理 — 道法自然
REM 自动启动代理 + Windsurf
title WAM Transparent Proxy

REM 启动透明代理(后台)
start /min "WAM Proxy" node "${proxyScript}" serve

REM 等待代理启动
timeout /t 2 /nobreak >nul

REM 设置环境变量
set HTTPS_PROXY=http://127.0.0.1:${PROXY_PORT}
set NODE_EXTRA_CA_CERTS=${caCert}
set NODE_TLS_REJECT_UNAUTHORIZED=0

REM 启动Windsurf
start "" "${windsurfExe}"

echo.
echo [OK] 透明代理(:${PROXY_PORT}) + Windsurf 已启动
echo [OK] 96个apiKey已就绪，所有请求将自动路由到最优账号
echo.
pause
`;
  
  const batFile = path.join(path.dirname(__dirname), '→透明代理启动.cmd');
  fs.writeFileSync(batFile, batContent, 'utf8');
  console.log(`启动脚本已生成: ${batFile}`);
  console.log('双击运行即可启动代理+Windsurf');
}

commands.launcher = cmdLauncher;

/** 底层全景: 查询运行中代理的深层状态 */
async function cmdDeep() {
  console.log('═══ 水面之下 — 底层全景 ═══\n');
  try {
    const resp = await new Promise((resolve, reject) => {
      const req = http.get(`http://127.0.0.1:${PROXY_PORT}/api/deep`, (res) => {
        let buf = ''; res.on('data', c => buf += c);
        res.on('end', () => resolve(JSON.parse(buf)));
      });
      req.on('error', reject);
      req.setTimeout(3000, () => { req.destroy(); reject(new Error('timeout')); });
    });

    // 总览
    console.log('── 代理引擎 ──');
    console.log(`  请求总数: ${resp.requests} | 路由重写: ${resp.rewrites} | 透传: ${resp.passthrough}`);
    console.log(`  自动重试: ${resp.retries} | 限流检测: ${resp.rateLimitsDetected} | 配额耗尽: ${resp.quotaExhausted} | 错误: ${resp.errors}`);

    // 号池 + 活水续命
    const p = resp.pool;
    console.log(`\n── 号池 ──`);
    console.log(`  就绪: ${p.ready}/${p.total} | 限流: ${p.limited} | 过期: ${p.stale || 0} | 平均配额: D${p.avgDaily}% W${p.avgWeekly}%`);
    if (p.refresh) {
      const rf = p.refresh;
      console.log(`  活水续命: 周期#${rf.total} | 成功: ${rf.success} | 失败: ${rf.fail} | 上次: ${rf.lastRun ? new Date(rf.lastRun).toLocaleTimeString() : '未运行'}`);
    }

    // 路由器
    if (resp.router) {
      console.log(`\n── 模型感知路由 ──`);
      console.log(`  总路由决策: ${resp.router.totalRoutes} | 总重试: ${resp.router.totalRetries}`);
      if (resp.router.modelStats) {
        for (const [model, s] of Object.entries(resp.router.modelStats)) {
          console.log(`  ${model.padEnd(40)} req=${s.requests} retry=${s.retries} rl=${s.rateLimits}`);
        }
      }

      // 速率桶
      if (resp.router.buckets && resp.router.buckets.length > 0) {
        console.log(`\n── 速率桶 (per-apiKey-per-model) ──`);
        for (const b of resp.router.buckets) {
          const rl = b.rateLimited ? ` 🔴 LOCKED ${b.resetsIn}s` : '';
          console.log(`  ${b.key.padEnd(35)} ${b.active}/${b.capacity} active${rl}${b.hitCount > 0 ? ` hits=${b.hitCount}` : ''}`);
        }
      }
    }

    // 最近请求
    if (resp.recentRequests && resp.recentRequests.length > 0) {
      console.log(`\n── 最近请求 (${resp.recentRequests.length}条) ──`);
      for (const r of resp.recentRequests.slice(-10)) {
        const dt = new Date(r.ts).toLocaleTimeString();
        const model = r.modelUid ? r.modelUid.substring(0, 25) : '?';
        const action = r.retried ? '↻RETRY' : r.rewritten ? '↝ROUTE' : '→PASS';
        const rl = r.rateLimitDetected ? ' 🚫RL' : '';
        const qc = r.quotaCostBp ? ` -${r.quotaCostBp}bp` : '';
        console.log(`  ${dt} ${action} ${model.padEnd(25)} ${r.path?.substring(0, 50) || ''}${rl}${qc}`);
      }
    }
  } catch (e) {
    console.log(`代理未运行或无法连接: ${e.message}`);
    console.log('请先启动代理: node scripts/transparent_proxy.js serve');
  }
}
commands.deep = cmdDeep;

if (commands[cmd]) {
  commands[cmd]().catch(e => { console.error(`错误: ${e.message}`); process.exit(1); });
} else {
  console.log(`透明代理引擎 v3.0 — 活水永续·道法自然

  道生一(apiKey) → 一生二(Quota+RateLimit) → 二生三(Router+Bucket+Monitor) → 三生万物(96账号×107模型)
  v3.0: refreshToken活水续命 + F30实时配额提取 + 自适应桶校准

使用方法:
  node transparent_proxy.js keygen         生成自签名CA证书
  node transparent_proxy.js warmup [N]     预热apiKey池 (含refreshToken永续凭证)
  node transparent_proxy.js test           POC验证(apiKey替换可行性)
  node transparent_proxy.js serve          启动代理 (含活水续命+实时配额)
  node transparent_proxy.js status         查看号池状态
  node transparent_proxy.js deep           查看底层全景(速率桶/路由/请求日志)
  node transparent_proxy.js launcher       生成Windsurf启动脚本

底层引擎 v3.0:
  KeyPool+AutoRefresh — 96个apiKey永续: refreshToken每45min自动续命
  QuotaExtractor      — gRPC响应F30提取: 实时配额成本扣减(basis_points)
  RateBucketTracker   — 自适应速率桶: 从实测rate limit学习真实容量+窗口
  ModelAwareRouter    — 模型感知路由: 配额×速率桶×模型tier加权评分
  ResponseMonitor     — 三层感知: rate limit + quota exhausted + F30成本
  AutoRetry           — 水遇石则绕: rate limit自动换账号重试(最多3次)

API端点 (代理运行时):
  http://127.0.0.1:${PROXY_PORT}/           代理概要
  http://127.0.0.1:${PROXY_PORT}/api/deep   底层全景(桶+路由+日志+续命)
  http://127.0.0.1:${PROXY_PORT}/api/quota  实时配额全景(每账号配额+消耗)
  http://127.0.0.1:${PROXY_PORT}/api/buckets 所有速率桶快照
  http://127.0.0.1:${PROXY_PORT}/api/routes  路由统计
`);
}
