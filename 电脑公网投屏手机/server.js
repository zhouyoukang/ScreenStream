/**
 * Desktop Cast Relay Server v2.3
 * 电脑公网投屏手机 — 中继+信令服务器
 *
 * Architecture:
 *   Mode 1 (Relay):  Desktop ──WSS──→ Relay ──WSS──→ Phone Browser
 *   Mode 2 (P2P):    Desktop ←──WebRTC──→ Phone Browser (relay = signaling only)
 *
 * Protocol:
 *   Binary: JPEG frames (provider → viewers) [relay mode]
 *   Text/JSON: Control commands (viewer → provider)
 *   Text/JSON: WebRTC signaling (SDP offer/answer, ICE candidates)
 *   Text/JSON: Status/device info (bidirectional)
 */

const http = require('http');
const { WebSocketServer, WebSocket } = require('ws');
const { readFileSync, existsSync, statSync, readdirSync } = require('fs');
const { join, extname, resolve } = require('path');
const crypto = require('crypto');

// ─── Config ───────────────────────────────────────────────
const PORT = parseInt(process.env.PORT || '9802');
const TOKEN = process.env.RELAY_TOKEN || 'desktop_cast_2026';
const MAX_VIEWERS = parseInt(process.env.MAX_VIEWERS || '5');
const HEARTBEAT_MS = 30000;
const isDev = process.argv.includes('--dev');

// ─── IP Rate Limiting ────────────────────────────────────
const ipConnections = new Map();
const RATE_LIMIT_WINDOW = 60_000;
const RATE_LIMIT_MAX = 20;

function checkRateLimit(ip) {
    const now = Date.now();
    let entry = ipConnections.get(ip);
    if (!entry || now > entry.resetAt) {
        entry = { count: 0, resetAt: now + RATE_LIMIT_WINDOW };
        ipConnections.set(ip, entry);
    }
    entry.count++;
    return entry.count <= RATE_LIMIT_MAX;
}

setInterval(() => {
    const now = Date.now();
    for (const [ip, entry] of ipConnections) {
        if (now > entry.resetAt) ipConnections.delete(ip);
    }
}, 5 * 60 * 1000);

// ─── Room Management ─────────────────────────────────────
const rooms = new Map();

class Room {
    constructor(id, provider) {
        this.id = id;
        this.provider = provider;
        this.viewers = new Map();       // viewerId → ws
        this.deviceInfo = {};
        this.lastFrame = null;          // Cache last JPEG for instant display
        this.createdAt = Date.now();
        this.stats = { frames: 0, bytes: 0, controlCmds: 0 };
    }

    addViewer(id, ws) {
        if (this.viewers.size >= MAX_VIEWERS) return false;
        this.viewers.set(id, ws);
        // Send cached frame for instant display on join
        if (this.lastFrame) {
            try { ws.send(this.lastFrame); } catch (e) { /* ignore */ }
        }
        this.notifyProvider('viewer_joined', { id, count: this.viewers.size });
        return true;
    }

    removeViewer(id) {
        this.viewers.delete(id);
        this.notifyProvider('viewer_left', { id, count: this.viewers.size });
    }

    broadcastFrame(data) {
        this.lastFrame = data;
        this.stats.frames++;
        this.stats.bytes += data.length;
        for (const [, viewer] of this.viewers) {
            if (viewer.readyState !== WebSocket.OPEN) continue;
            // Skip viewers that have established P2P
            if (viewer._p2p) continue;
            // Backpressure: skip frame if viewer buffer > 1MB
            if ((viewer.bufferedAmount || 0) > 1048576) continue;
            try { viewer.send(data); } catch (e) { /* ignore */ }
        }
    }

    sendToProvider(msg) {
        if (this.provider && this.provider.readyState === WebSocket.OPEN) {
            try {
                this.provider.send(typeof msg === 'string' ? msg : JSON.stringify(msg));
            } catch (e) { /* ignore */ }
        }
    }

    notifyProvider(event, data) {
        this.sendToProvider(JSON.stringify({ type: event, data }));
    }

    notifyViewers(event, data) {
        const msg = JSON.stringify({ type: event, data });
        for (const [, viewer] of this.viewers) {
            if (viewer.readyState === WebSocket.OPEN) {
                try { viewer.send(msg); } catch (e) { /* ignore */ }
            }
        }
    }

    destroy() {
        this.notifyViewers('provider_disconnected', {});
        for (const [, v] of this.viewers) {
            try { v.close(1000, 'Room closed'); } catch (e) { /* ignore */ }
        }
        this.viewers.clear();
    }
}

// ─── HTTP Server ──────────────────────────────────────────
const server = http.createServer((req, res) => {
    const url = new URL(req.url, `http://${req.headers.host}`);

    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

    // API: health (quick check)
    if (url.pathname === '/api/health') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, rooms: rooms.size, uptime: Math.round(process.uptime()) }));
        return;
    }

    // API: status (detailed)
    if (url.pathname === '/api/status') {
        const list = [];
        for (const [id, room] of rooms) {
            list.push({
                id,
                device: room.deviceInfo,
                viewers: room.viewers.size,
                p2pViewers: [...room.viewers.values()].filter(v => v._p2p).length,
                uptime: Math.round((Date.now() - room.createdAt) / 1000),
                stats: room.stats
            });
        }
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
            ok: true, rooms: list,
            totalViewers: list.reduce((s, r) => s + r.viewers, 0),
            uptime: Math.round(process.uptime()),
            memory: Math.round(process.memoryUsage().heapUsed / 1024 / 1024) + 'MB'
        }));
        return;
    }

    // Static files (viewer) — served from cache
    const pathname = url.pathname === '/' ? '/index.html' : url.pathname;
    if (staticCache.has(pathname)) {
        const cached = staticCache.get(pathname);
        res.writeHead(200, { 'Content-Type': cached.mime, 'Cache-Control': 'public, max-age=60' });
        res.end(cached.data);
        return;
    }

    res.writeHead(404);
    res.end('Not Found');
});

// ─── WebSocket Server ─────────────────────────────────────
const wss = new WebSocketServer({ server });

wss.on('connection', (ws, req) => {
    const ip = req.headers['x-forwarded-for']?.split(',')[0]?.trim() || req.socket.remoteAddress;
    const url = new URL(req.url, `http://${req.headers.host}`);
    const role = url.searchParams.get('role');
    const token = url.searchParams.get('token');
    const roomId = url.searchParams.get('room');

    if (!checkRateLimit(ip)) {
        log(`Rate limit exceeded: ${ip}`);
        ws.close(4029, 'Rate limit exceeded');
        return;
    }

    ws._isAlive = true;
    ws.on('pong', () => { ws._isAlive = true; });

    // ── Provider (desktop) ──
    if (role === 'provider') {
        if (token !== TOKEN) {
            ws.close(4001, 'Invalid token');
            return;
        }

        const id = roomId || crypto.randomBytes(3).toString('hex').toUpperCase();

        if (rooms.has(id)) {
            const room = rooms.get(id);
            room.provider = ws;
            room.notifyViewers('provider_reconnected', {});
            log(`Provider reconnected: ${id}`);
        } else {
            const room = new Room(id, ws);
            rooms.set(id, room);
            log(`Provider connected: ${id}`);
        }

        ws._roomId = id;
        ws.send(JSON.stringify({
            type: 'registered',
            data: { roomId: id, maxViewers: MAX_VIEWERS }
        }));

        ws.on('message', (data, isBinary) => {
            const room = rooms.get(ws._roomId);
            if (!room) return;

            if (isBinary) {
                room.broadcastFrame(data);
            } else {
                try {
                    const msg = JSON.parse(data.toString());
                    if (msg.type === 'device_info') {
                        room.deviceInfo = msg.data || {};
                        room.notifyViewers('device_info', room.deviceInfo);
                    } else if (msg.type === 'screenshot_response') {
                        room.notifyViewers('screenshot_info', msg.data);
                    } else if (msg.type === 'webrtc_answer' || msg.type === 'webrtc_ice_provider') {
                        // WebRTC signaling: provider → specific viewer
                        const targetId = msg.target;
                        if (targetId && room.viewers.has(targetId)) {
                            const viewer = room.viewers.get(targetId);
                            try { viewer.send(JSON.stringify(msg)); } catch (e) {}
                        }
                    } else {
                        room.notifyViewers(msg.type, msg.data);
                    }
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
        return;
    }

    // ── Viewer (phone browser) ──
    if (role === 'viewer') {
        if (token !== TOKEN) {
            ws.close(4001, 'Invalid token');
            return;
        }

        if (!roomId) {
            ws.send(JSON.stringify({ type: 'error', data: { message: 'Missing room code' } }));
            ws.close(4000, 'Missing room');
            return;
        }

        // Case-insensitive room lookup
        const roomKey = [...rooms.keys()].find(k => k.toUpperCase() === roomId.toUpperCase());
        if (!roomKey) {
            ws.send(JSON.stringify({ type: 'error', data: { message: 'Room not found' } }));
            ws.close(4004, 'Room not found');
            return;
        }

        const room = rooms.get(roomKey);
        const viewerId = 'v-' + crypto.randomBytes(3).toString('hex');

        if (!room.addViewer(viewerId, ws)) {
            ws.close(4002, 'Room full');
            return;
        }

        ws._roomId = roomKey;
        ws._viewerId = viewerId;
        log(`Viewer ${viewerId} joined room ${roomKey} (${room.viewers.size}/${MAX_VIEWERS})`);

        ws.send(JSON.stringify({
            type: 'joined',
            data: {
                roomId: roomKey,
                viewerId,
                deviceInfo: room.deviceInfo,
                viewerCount: room.viewers.size
            }
        }));

        ws.on('message', (data, isBinary) => {
            const room = rooms.get(ws._roomId);
            if (!room) return;
            if (!isBinary) {
                try {
                    const msg = JSON.parse(data.toString());
                    room.stats.controlCmds++;
                    if (msg.type === 'webrtc_offer' || msg.type === 'webrtc_ice_viewer') {
                        // WebRTC signaling: viewer → provider (tag with viewerId)
                        msg.source = ws._viewerId;
                        room.sendToProvider(JSON.stringify(msg));
                    } else if (msg.type === 'p2p_established') {
                        // Viewer established P2P — mark to skip relay frames
                        ws._p2p = true;
                        log(`Viewer ${ws._viewerId} switched to P2P`);
                    } else {
                        room.sendToProvider(JSON.stringify(msg));
                    }
                } catch (e) { /* ignore */ }
            }
        });

        ws.on('close', () => {
            const room = rooms.get(ws._roomId);
            if (room) {
                room.removeViewer(ws._viewerId);
                log(`Viewer ${ws._viewerId} left room ${ws._roomId} (${room.viewers.size})`);
            }
        });
        return;
    }

    ws.close(4000, 'Specify ?role=provider or ?role=viewer');
});

// ─── Heartbeat ────────────────────────────────────────────
const heartbeat = setInterval(() => {
    wss.clients.forEach(ws => {
        if (!ws._isAlive) {
            log(`Heartbeat timeout: room=${ws._roomId}`);
            return ws.terminate();
        }
        ws._isAlive = false;
        ws.ping();
    });
}, HEARTBEAT_MS);
wss.on('close', () => clearInterval(heartbeat));

// ─── Startup ──────────────────────────────────────────────
function log(msg) {
    console.log(`[${new Date().toISOString().slice(11, 19)}] ${msg}`);
}

// ─── Static File Cache ────────────────────────────────────
const staticCache = new Map();
const MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.ico': 'image/x-icon',
    '.svg': 'image/svg+xml'
};

const VIEWER_ROOT = resolve(join(__dirname, 'viewer'));
function loadStaticFiles(dir, prefix = '') {
    if (!existsSync(dir)) return;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const fullPath = join(dir, entry.name);
        const urlPath = prefix + '/' + entry.name;
        if (entry.isDirectory()) {
            loadStaticFiles(fullPath, urlPath);
        } else if (entry.isFile()) {
            const safeCheck = resolve(fullPath).startsWith(VIEWER_ROOT);
            if (!safeCheck) continue;
            staticCache.set(urlPath, {
                data: readFileSync(fullPath),
                mime: MIME_TYPES[extname(entry.name)] || 'application/octet-stream'
            });
        }
    }
}
loadStaticFiles(VIEWER_ROOT);

server.listen(PORT, () => {
    log(`Desktop Cast Relay v2.3 on :${PORT}`);
    log(`Token: ${TOKEN.slice(0, 4)}${'*'.repeat(Math.max(0, TOKEN.length - 4))}`);
    log(`Max viewers: ${MAX_VIEWERS}`);
    log(`Viewer: http://localhost:${PORT}/ (${staticCache.size} cached files)`);
    if (isDev) log(`DEV MODE`);
});

// ─── 崩溃保护 ────────────────────────────────────────────
process.on('uncaughtException', (err) => {
    log(`[FATAL] Uncaught exception: ${err.message}`);
    console.error(err.stack);
});
process.on('unhandledRejection', (reason) => {
    log(`[WARN] Unhandled rejection: ${reason}`);
});

// Graceful shutdown
function shutdown() {
    log('Shutting down...');
    clearInterval(heartbeat);
    for (const [, room] of rooms) room.destroy();
    wss.close();
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(1), 5000);
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
