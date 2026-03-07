/**
 * ScreenStream Public Network Relay Server
 *
 * 综合取精华：
 * - ws-scrcpy: WebSocket帧中继模式
 * - Headwind Remote: 设备主动外连（穿NAT）
 * - piping-adb-web: HTTP中继思路
 * - 我们自己: 帧格式 (1B type + 8B timestamp + data)
 *
 * 架构：
 *   手机(provider) ──WSS──→ Relay Server ──WSS──→ 浏览器(viewer)
 *   PC(desktop)   ──WSS──→ Relay Server ──WSS──→ 浏览器(viewer)
 *
 * 协议：
 *   文本消息: JSON {type, data}
 *   二进制消息: 直接转发（视频帧/音频/截图）
 */

const http = require('http');
const { WebSocketServer, WebSocket } = require('ws');
const { readFileSync, existsSync } = require('fs');
const { join } = require('path');
const crypto = require('crypto');

// ─── 配置 ───────────────────────────────────────────────
const PORT = parseInt(process.env.PORT || '9800');
const TOKEN = process.env.RELAY_TOKEN || 'screenstream_2026';
const MAX_VIEWERS = parseInt(process.env.MAX_VIEWERS || '10');
const HEARTBEAT_INTERVAL = 30000; // 30s
const AGENT_TIMEOUT = 10000; // 10s timeout for agent API calls
const isDev = process.argv.includes('--dev');

// ─── Agent API: 待处理请求 ─────────────────────────────
const pendingRequests = new Map(); // reqId -> { resolve, timer }
let reqCounter = 0;

function createPendingRequest(timeoutMs = AGENT_TIMEOUT) {
    const reqId = 'aq_' + (++reqCounter) + '_' + Date.now();
    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
            pendingRequests.delete(reqId);
            resolve({ ok: false, error: 'timeout', message: 'Provider did not respond within ' + timeoutMs + 'ms' });
        }, timeoutMs);
        pendingRequests.set(reqId, { resolve, timer });
    }).then(result => {
        return { reqId, ...result };
    });
}

function resolvePendingRequest(reqId, data) {
    const entry = pendingRequests.get(reqId);
    if (entry) {
        clearTimeout(entry.timer);
        pendingRequests.delete(reqId);
        entry.resolve({ ok: true, data });
    }
}

// ─── HTTP Body Parser ──────────────────────────────────
function parseBody(req) {
    return new Promise((resolve, reject) => {
        const chunks = [];
        req.on('data', c => {
            chunks.push(c);
            if (chunks.reduce((s, c) => s + c.length, 0) > 1024 * 1024) {
                reject(new Error('Body too large'));
                req.destroy();
            }
        });
        req.on('end', () => {
            try {
                const body = Buffer.concat(chunks).toString();
                resolve(body ? JSON.parse(body) : {});
            } catch (e) { reject(e); }
        });
        req.on('error', reject);
    });
}

function authCheck(req, url) {
    const token = url.searchParams.get('token')
        || req.headers.authorization?.replace('Bearer ', '')
        || req.headers['x-token'];
    return token === TOKEN;
}

function jsonResponse(res, status, data) {
    res.writeHead(status, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
}

// ─── 房间管理 ───────────────────────────────────────────
const rooms = new Map(); // roomId -> Room

class Room {
    constructor(id, provider) {
        this.id = id;
        this.provider = provider;       // WebSocket (phone or desktop)
        this.providerType = null;       // 'phone' | 'desktop'
        this.viewers = new Set();       // Set<WebSocket>
        this.lastVideoConfig = null;    // SPS/PPS config frame (type=0)
        this.lastKeyFrame = null;       // Last IDR frame
        this.deviceInfo = {};           // Device metadata
        this.createdAt = Date.now();
        this.stats = { frames: 0, bytes: 0, viewers: 0 };
    }

    addViewer(ws) {
        if (this.viewers.size >= MAX_VIEWERS) return false;
        this.viewers.add(ws);
        this.stats.viewers = this.viewers.size;
        // Send cached config + keyframe for instant display
        if (this.lastVideoConfig) ws.send(this.lastVideoConfig);
        if (this.lastKeyFrame) ws.send(this.lastKeyFrame);
        this.notifyProvider('viewer_joined', { count: this.viewers.size });
        this.notifyViewers('viewer_joined', { count: this.viewers.size });
        return true;
    }

    removeViewer(ws) {
        this.viewers.delete(ws);
        this.stats.viewers = this.viewers.size;
        this.notifyProvider('viewer_left', { count: this.viewers.size });
        this.notifyViewers('viewer_left', { count: this.viewers.size });
    }

    broadcastVideo(data) {
        // Cache config and keyframes for late-joining viewers
        if (data.length > 0) {
            const frameType = data[0];
            if (frameType === 0) this.lastVideoConfig = data;
            else if (frameType === 1) this.lastKeyFrame = data;
        }
        this.stats.frames++;
        this.stats.bytes += data.length;

        for (const viewer of this.viewers) {
            if (viewer.readyState !== WebSocket.OPEN) continue;
            // Backpressure: skip delta frames if viewer is slow (buffered > 512KB)
            const buffered = viewer.bufferedAmount || 0;
            if (buffered > 524288 && data.length > 0 && data[0] === 2) {
                continue; // Skip P-frame for slow viewer
            }
            try { viewer.send(data); } catch (e) { /* ignore */ }
        }
    }

    sendToProvider(data) {
        if (this.provider && this.provider.readyState === WebSocket.OPEN) {
            try { this.provider.send(data); } catch (e) { /* ignore */ }
        }
    }

    notifyProvider(event, data) {
        this.sendToProvider(JSON.stringify({ type: event, data }));
    }

    notifyViewers(event, data) {
        const msg = JSON.stringify({ type: event, data });
        for (const viewer of this.viewers) {
            if (viewer.readyState === WebSocket.OPEN) {
                try { viewer.send(msg); } catch (e) { /* ignore */ }
            }
        }
    }

    destroy() {
        this.notifyViewers('provider_disconnected', {});
        for (const v of this.viewers) {
            try { v.close(1000, 'Room closed'); } catch (e) { /* ignore */ }
        }
        this.viewers.clear();
    }
}

// ─── HTTP服务器 ──────────────────────────────────────────
const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://${req.headers.host}`);

    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Token');
    if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

    // API: 房间列表
    if (url.pathname === '/api/rooms') {
        if (!authCheck(req, url)) { jsonResponse(res, 401, { error: 'Unauthorized' }); return; }
        const list = [];
        for (const [id, room] of rooms) {
            list.push({
                id,
                type: room.providerType,
                device: room.deviceInfo,
                viewers: room.viewers.size,
                uptime: Date.now() - room.createdAt,
                stats: room.stats
            });
        }
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ rooms: list }));
        return;
    }

    // API: 服务状态
    if (url.pathname === '/api/status') {
        jsonResponse(res, 200, {
            ok: true,
            rooms: rooms.size,
            totalViewers: [...rooms.values()].reduce((s, r) => s + r.viewers.size, 0),
            uptime: process.uptime(),
            memory: Math.round(process.memoryUsage().heapUsed / 1024 / 1024) + 'MB',
            pendingRequests: pendingRequests.size
        });
        return;
    }

    // ─── Agent API: 获取单个房间详情 ───
    const roomMatch = url.pathname.match(/^\/api\/room\/([^/]+)$/);
    if (roomMatch && req.method === 'GET') {
        if (!authCheck(req, url)) { jsonResponse(res, 401, { error: 'Unauthorized' }); return; }
        const room = rooms.get(roomMatch[1]);
        if (!room) { jsonResponse(res, 404, { error: 'Room not found' }); return; }
        jsonResponse(res, 200, {
            id: room.id,
            type: room.providerType,
            device: room.deviceInfo,
            viewers: room.viewers.size,
            uptime: Date.now() - room.createdAt,
            stats: room.stats,
            providerConnected: room.provider && room.provider.readyState === WebSocket.OPEN
        });
        return;
    }

    // ─── Agent API: 发送控制命令 ───
    if (url.pathname === '/api/command' && req.method === 'POST') {
        if (!authCheck(req, url)) { jsonResponse(res, 401, { error: 'Unauthorized' }); return; }
        try {
            const body = await parseBody(req);
            const { room: roomId, type, action, data, x, y, x1, y1, x2, y2, duration, text, code, package: pkg } = body;
            if (!roomId) { jsonResponse(res, 400, { error: 'Missing room field' }); return; }
            const room = rooms.get(roomId);
            if (!room) { jsonResponse(res, 404, { error: 'Room not found' }); return; }
            if (!room.provider || room.provider.readyState !== WebSocket.OPEN) {
                jsonResponse(res, 503, { error: 'Provider not connected' }); return;
            }

            // Build command message
            const reqId = 'aq_' + (++reqCounter) + '_' + Date.now();
            const cmd = {
                type: type || 'api_call',
                _reqId: reqId,
                data: data || {}
            };
            // Convenience: flatten common fields into data
            if (action) cmd.data.action = action;
            if (duration !== undefined) cmd.data.duration = duration;
            if (text !== undefined) cmd.data.text = text;
            if (code !== undefined) { cmd.data.keyCode = code; cmd.data.code = code; }
            if (pkg) cmd.data.package = pkg;

            // Auto-normalize pixel coordinates for touch commands
            // CloudRelayClient expects normalized 0-1 coords (data.x→nx, data.y→ny)
            // If coords > 1, treat as pixels and normalize using screenW/screenH
            const sw = body.screenW || 1080, sh = body.screenH || 2400;
            const norm = (v, max) => v > 1 ? Math.min(1, v / max) : v;
            if (cmd.type === 'touch') {
                if (x !== undefined) cmd.data.x = norm(x, sw);
                if (y !== undefined) cmd.data.y = norm(y, sh);
                // Swipe: support both x1/y1 and fromX/fromY naming
                if (x1 !== undefined) cmd.data.fromX = norm(x1, sw);
                if (y1 !== undefined) cmd.data.fromY = norm(y1, sh);
                if (x2 !== undefined) cmd.data.toX = norm(x2, sw);
                if (y2 !== undefined) cmd.data.toY = norm(y2, sh);
            } else {
                if (x !== undefined) cmd.data.x = x;
                if (y !== undefined) cmd.data.y = y;
            }

            room.sendToProvider(JSON.stringify(cmd));
            log(`[Agent] Command → room=${roomId} type=${cmd.type} action=${cmd.data.action || ''} reqId=${reqId}`);

            // Fire-and-forget mode: skip waiting for response
            const nowait = body.nowait || url.searchParams.has('nowait');
            if (nowait) {
                jsonResponse(res, 200, { ok: true, reqId, sent: true });
                return;
            }

            // Wait for provider response
            const responsePromise = new Promise((resolve) => {
                const timer = setTimeout(() => {
                    pendingRequests.delete(reqId);
                    resolve({ ok: false, error: 'timeout' });
                }, AGENT_TIMEOUT);
                pendingRequests.set(reqId, { resolve, timer });
            });

            const result = await responsePromise;
            if (result.ok) {
                jsonResponse(res, 200, { ok: true, reqId, data: result.data });
            } else {
                jsonResponse(res, 200, { ok: false, reqId, error: result.error, message: 'Provider did not respond within timeout. Command was sent but no confirmation received.' });
            }
        } catch (e) {
            jsonResponse(res, 400, { error: 'Invalid request', message: e.message });
        }
        return;
    }

    // ─── Agent API: 批量命令 ───
    if (url.pathname === '/api/batch' && req.method === 'POST') {
        if (!authCheck(req, url)) { jsonResponse(res, 401, { error: 'Unauthorized' }); return; }
        try {
            const body = await parseBody(req);
            const { room: roomId, commands } = body;
            if (!roomId || !Array.isArray(commands)) { jsonResponse(res, 400, { error: 'Missing room or commands[]' }); return; }
            const room = rooms.get(roomId);
            if (!room) { jsonResponse(res, 404, { error: 'Room not found' }); return; }
            if (!room.provider || room.provider.readyState !== WebSocket.OPEN) {
                jsonResponse(res, 503, { error: 'Provider not connected' }); return;
            }

            const nowait = body.nowait || url.searchParams.has('nowait');
            const sw = body.screenW || 1080, sh = body.screenH || 2400;
            const norm = (v, max) => v > 1 ? Math.min(1, v / max) : v;

            if (nowait) {
                // Fire-and-forget: send all commands with delays, don't wait
                let sent = 0;
                (async () => {
                    for (const cmdDef of commands) {
                        const reqId = 'aq_' + (++reqCounter) + '_' + Date.now();
                        const cmd = { type: cmdDef.type || 'api_call', _reqId: reqId, data: cmdDef.data || {} };
                        if (cmdDef.action) cmd.data.action = cmdDef.action;
                        // Auto-normalize touch coords
                        if (cmd.type === 'touch' && cmd.data) {
                            if (cmd.data.x > 1) cmd.data.x = norm(cmd.data.x, sw);
                            if (cmd.data.y > 1) cmd.data.y = norm(cmd.data.y, sh);
                            if (cmd.data.fromX > 1) cmd.data.fromX = norm(cmd.data.fromX, sw);
                            if (cmd.data.fromY > 1) cmd.data.fromY = norm(cmd.data.fromY, sh);
                            if (cmd.data.toX > 1) cmd.data.toX = norm(cmd.data.toX, sw);
                            if (cmd.data.toY > 1) cmd.data.toY = norm(cmd.data.toY, sh);
                        }
                        room.sendToProvider(JSON.stringify(cmd));
                        sent++;
                        if (cmdDef.delay) await new Promise(r => setTimeout(r, cmdDef.delay));
                    }
                })();
                jsonResponse(res, 200, { ok: true, queued: commands.length });
            } else {
                const results = [];
                for (const cmdDef of commands) {
                    const reqId = 'aq_' + (++reqCounter) + '_' + Date.now();
                    const cmd = { type: cmdDef.type || 'api_call', _reqId: reqId, data: cmdDef.data || {} };
                    if (cmdDef.action) cmd.data.action = cmdDef.action;
                    // Auto-normalize touch coords (same as nowait path)
                    if (cmd.type === 'touch' && cmd.data) {
                        if (cmd.data.x > 1) cmd.data.x = norm(cmd.data.x, sw);
                        if (cmd.data.y > 1) cmd.data.y = norm(cmd.data.y, sh);
                        if (cmd.data.fromX > 1) cmd.data.fromX = norm(cmd.data.fromX, sw);
                        if (cmd.data.fromY > 1) cmd.data.fromY = norm(cmd.data.fromY, sh);
                        if (cmd.data.toX > 1) cmd.data.toX = norm(cmd.data.toX, sw);
                        if (cmd.data.toY > 1) cmd.data.toY = norm(cmd.data.toY, sh);
                    }

                    const responsePromise = new Promise((resolve) => {
                        const timer = setTimeout(() => {
                            pendingRequests.delete(reqId);
                            resolve({ ok: false, error: 'timeout' });
                        }, AGENT_TIMEOUT);
                        pendingRequests.set(reqId, { resolve, timer });
                    });

                    room.sendToProvider(JSON.stringify(cmd));
                    const result = await responsePromise;
                    results.push({ reqId, ...result });

                    if (cmdDef.delay) await new Promise(r => setTimeout(r, cmdDef.delay));
                }
                jsonResponse(res, 200, { ok: true, results });
            }
        } catch (e) {
            jsonResponse(res, 400, { error: 'Invalid request', message: e.message });
        }
        return;
    }

    // Welcome落地页（无参数时显示）
    if ((url.pathname === '/' || url.pathname === '/index.html') && !url.searchParams.has('room')) {
        const welcomePath = join(__dirname, '..', 'welcome.html');
        if (existsSync(welcomePath)) {
            res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
            res.end(readFileSync(welcomePath));
            return;
        }
    }

    // APK下载
    if (url.pathname === '/ScreenStream.apk') {
        const apkPath = join(__dirname, '..', 'ScreenStream.apk');
        if (existsSync(apkPath)) {
            const stat = require('fs').statSync(apkPath);
            res.writeHead(200, {
                'Content-Type': 'application/vnd.android.package-archive',
                'Content-Disposition': 'attachment; filename=ScreenStream.apk',
                'Content-Length': stat.size
            });
            require('fs').createReadStream(apkPath).pipe(res);
            return;
        }
    }

    // 静态文件: viewer页面
    const viewerDir = join(__dirname, '..', 'viewer');
    let filePath;
    if (url.pathname === '/' || url.pathname === '/index.html') {
        filePath = join(viewerDir, 'index.html');
    } else if (url.pathname.startsWith('/')) {
        // Path traversal protection: resolve and verify within viewerDir
        const resolved = require('path').resolve(viewerDir, '.' + url.pathname);
        if (resolved.startsWith(require('path').resolve(viewerDir))) {
            filePath = resolved;
        }
    }

    if (filePath && existsSync(filePath)) {
        const ext = filePath.split('.').pop();
        const types = { html: 'text/html', js: 'application/javascript', css: 'text/css', png: 'image/png', ico: 'image/x-icon' };
        res.writeHead(200, { 'Content-Type': (types[ext] || 'application/octet-stream') + '; charset=utf-8' });
        require('fs').createReadStream(filePath).pipe(res);
        return;
    }

    res.writeHead(404);
    res.end('Not Found');
});

// ─── WebSocket服务器 ────────────────────────────────────
const wss = new WebSocketServer({ server });

wss.on('connection', (ws, req) => {
    const url = new URL(req.url, `http://${req.headers.host}`);
    const role = url.searchParams.get('role');      // 'provider' | 'viewer'
    const token = url.searchParams.get('token');
    const roomId = url.searchParams.get('room');
    const deviceType = url.searchParams.get('type'); // 'phone' | 'desktop'

    ws._isAlive = true;
    ws._role = role;
    ws._roomId = null;

    // ── Provider（手机/PC主动连入）──
    if (role === 'provider') {
        if (token !== TOKEN) {
            ws.close(4001, 'Invalid token');
            return;
        }

        const id = roomId || crypto.randomBytes(4).toString('hex');

        // Cleanup existing room if re-connecting
        if (rooms.has(id)) {
            const old = rooms.get(id);
            old.provider = ws;
            old.providerType = deviceType || 'phone';
            old.notifyViewers('provider_reconnected', {});
            ws._roomId = id;
            log(`Provider reconnected: ${id} (${deviceType})`);
        } else {
            const room = new Room(id, ws);
            room.providerType = deviceType || 'phone';
            rooms.set(id, room);
            ws._roomId = id;
            log(`Provider connected: ${id} (${deviceType})`);
        }

        ws.send(JSON.stringify({
            type: 'registered',
            data: {
                roomId: id,
                viewerUrl: `http://localhost:${PORT}/?room=${id}`,
                maxViewers: MAX_VIEWERS
            }
        }));

        ws.on('message', (data, isBinary) => {
            const room = rooms.get(ws._roomId);
            if (!room) return;

            if (isBinary) {
                // Binary: video/audio frame → broadcast to all viewers
                room.broadcastVideo(data);
            } else {
                // Text: JSON message from provider
                try {
                    const msg = JSON.parse(data.toString());
                    handleProviderMessage(room, msg);
                } catch (e) { /* ignore malformed */ }
            }
        });

        ws.on('close', () => {
            const room = rooms.get(ws._roomId);
            if (room && room.provider === ws) {
                log(`Provider disconnected: ${ws._roomId}`);
                room.destroy();
                rooms.delete(ws._roomId);
            }
        });

        ws.on('pong', () => { ws._isAlive = true; });
        return;
    }

    // ── Viewer（浏览器观看/控制）──
    if (role === 'viewer') {
        if (token !== TOKEN) {
            ws.close(4001, 'Invalid token');
            return;
        }

        if (!roomId || !rooms.has(roomId)) {
            ws.send(JSON.stringify({ type: 'error', data: { message: 'Room not found' } }));
            ws.close(4004, 'Room not found');
            return;
        }

        const room = rooms.get(roomId);
        if (!room.addViewer(ws)) {
            ws.close(4002, 'Room full');
            return;
        }

        ws._roomId = roomId;
        log(`Viewer joined room ${roomId} (${room.viewers.size}/${MAX_VIEWERS})`);

        ws.send(JSON.stringify({
            type: 'joined',
            data: {
                roomId,
                providerType: room.providerType,
                deviceInfo: room.deviceInfo,
                viewerCount: room.viewers.size
            }
        }));

        ws.on('message', (data, isBinary) => {
            const room = rooms.get(ws._roomId);
            if (!room) return;

            if (isBinary) {
                // Binary from viewer → forward to provider (e.g., file upload)
                room.sendToProvider(data);
            } else {
                // Text: control command from viewer → forward to provider
                try {
                    const msg = JSON.parse(data.toString());
                    handleViewerMessage(room, ws, msg);
                } catch (e) { /* ignore */ }
            }
        });

        ws.on('close', () => {
            const room = rooms.get(ws._roomId);
            if (room) {
                room.removeViewer(ws);
                log(`Viewer left room ${ws._roomId} (${room.viewers.size}/${MAX_VIEWERS})`);
            }
        });

        ws.on('pong', () => { ws._isAlive = true; });
        return;
    }

    // Unknown role
    ws.close(4000, 'Specify ?role=provider or ?role=viewer');
});

// ─── 消息处理 ────────────────────────────────────────────

function handleProviderMessage(room, msg) {
    switch (msg.type) {
        case 'device_info':
            room.deviceInfo = msg.data;
            room.notifyViewers('device_info', msg.data);
            break;

        case 'api_response': {
            // Check if this is a response to an Agent API request
            const reqId = msg._reqId || msg.data?._reqId;
            if (reqId && pendingRequests.has(reqId)) {
                resolvePendingRequest(reqId, msg.data);
            }
            // Also forward to viewers
            room.notifyViewers('api_response', msg.data);
            break;
        }

        case 'status':
            room.notifyViewers('provider_status', msg.data);
            break;

        default:
            // Forward unknown messages to all viewers
            room.notifyViewers(msg.type, msg.data);
    }
}

function handleViewerMessage(room, viewer, msg) {
    switch (msg.type) {
        case 'touch':
        case 'key':
        case 'text':
        case 'scroll':
        case 'api_call':
        case 'control':
            // Control commands → forward to provider
            room.sendToProvider(JSON.stringify(msg));
            break;

        case 'request_keyframe':
            room.sendToProvider(JSON.stringify({ type: 'request_keyframe' }));
            break;

        default:
            room.sendToProvider(JSON.stringify(msg));
    }
}

// ─── 心跳检测 ────────────────────────────────────────────
const heartbeat = setInterval(() => {
    wss.clients.forEach(ws => {
        if (!ws._isAlive) {
            log(`Heartbeat timeout: role=${ws._role} room=${ws._roomId}`);
            return ws.terminate();
        }
        ws._isAlive = false;
        ws.ping();
    });
}, HEARTBEAT_INTERVAL);

wss.on('close', () => clearInterval(heartbeat));

// ─── 启动 ────────────────────────────────────────────────
function log(msg) {
    console.log(`[${new Date().toISOString().slice(11, 19)}] ${msg}`);
}

// ─── 崩溃保护 ────────────────────────────────────────────
process.on('uncaughtException', (err) => {
    log(`[FATAL] Uncaught exception: ${err.message}`);
    console.error(err.stack);
});
process.on('unhandledRejection', (reason) => {
    log(`[WARN] Unhandled rejection: ${reason}`);
});

server.listen(PORT, () => {
    log(`ScreenStream Relay Server v1.0`);
    log(`Listening on :${PORT}`);
    log(`Token: ${TOKEN.slice(0, 4)}${'*'.repeat(Math.max(0, TOKEN.length - 4))}`);
    log(`Max viewers per room: ${MAX_VIEWERS}`);
    log(`Viewer URL: http://localhost:${PORT}/`);
    if (isDev) log(`DEV MODE`);
});
