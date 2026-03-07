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
const isDev = process.argv.includes('--dev');

// ─── IP速率限制 ─────────────────────────────────────────
const ipConnections = new Map(); // ip -> { count, resetAt }
const RATE_LIMIT_WINDOW = 60_000; // 1 minute
const RATE_LIMIT_MAX = 20; // max connections per IP per window

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

// Clean expired rate limit entries every 5 minutes
setInterval(() => {
    const now = Date.now();
    for (const [ip, entry] of ipConnections) {
        if (now > entry.resetAt) ipConnections.delete(ip);
    }
}, 5 * 60 * 1000);

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
const server = http.createServer((req, res) => {
    const url = new URL(req.url, `http://${req.headers.host}`);

    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
    if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

    // API: 房间列表
    if (url.pathname === '/api/rooms') {
        const token = url.searchParams.get('token') || req.headers.authorization?.replace('Bearer ', '');
        if (token !== TOKEN) { res.writeHead(401); res.end('Unauthorized'); return; }
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
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
            ok: true,
            rooms: rooms.size,
            totalViewers: [...rooms.values()].reduce((s, r) => s + r.viewers.size, 0),
            uptime: process.uptime(),
            memory: Math.round(process.memoryUsage().heapUsed / 1024 / 1024) + 'MB'
        }));
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
        filePath = require('path').resolve(join(viewerDir, url.pathname));
        // Path traversal protection: ensure resolved path stays within viewerDir
        if (!filePath.startsWith(require('path').resolve(viewerDir))) {
            res.writeHead(403);
            res.end('Forbidden');
            return;
        }
    }

    if (filePath && existsSync(filePath)) {
        const ext = filePath.split('.').pop();
        const types = { html: 'text/html; charset=utf-8', js: 'application/javascript', css: 'text/css', png: 'image/png', ico: 'image/x-icon', svg: 'image/svg+xml' };
        res.writeHead(200, { 'Content-Type': types[ext] || 'application/octet-stream' });
        require('fs').createReadStream(filePath).pipe(res);
        return;
    }

    res.writeHead(404);
    res.end('Not Found');
});

// ─── WebSocket服务器 ────────────────────────────────────
const wss = new WebSocketServer({ server });

wss.on('connection', (ws, req) => {
    const ip = req.headers['x-forwarded-for']?.split(',')[0]?.trim() || req.socket.remoteAddress;
    const url = new URL(req.url, `http://${req.headers.host}`);
    const role = url.searchParams.get('role');      // 'provider' | 'viewer'
    const token = url.searchParams.get('token');
    const roomId = url.searchParams.get('room');
    const deviceType = url.searchParams.get('type'); // 'phone' | 'desktop'

    // Rate limiting
    if (!checkRateLimit(ip)) {
        log(`Rate limit exceeded: ${ip}`);
        ws.close(4029, 'Rate limit exceeded');
        return;
    }

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
                viewerUrl: `${isDev ? 'http://localhost:' + PORT : 'https://aiotvr.xyz/relay'}/?room=${id}`,
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

        case 'api_response':
            // API response from phone → forward to requesting viewer
            room.notifyViewers('api_response', msg.data);
            break;

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
