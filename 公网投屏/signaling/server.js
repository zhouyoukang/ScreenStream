/**
 * P2P Screen Share Signaling Server
 * 
 * 职责：仅交换SDP offer/answer和ICE candidates，不中转任何媒体流。
 * 房间模型：provider(手机) 1:N viewer(浏览器)
 * 协议：WebSocket JSON
 */

const http = require('http');
const { WebSocketServer, WebSocket } = require('ws');

const PORT = parseInt(process.env.PORT || '9801');
const rooms = new Map(); // roomId -> { provider: ws, viewers: Map<id, ws>, deviceInfo: {} }
const adbRooms = new Map(); // roomId -> { bridge: ws, controller: ws, deviceInfo: {}, createdAt: number }

const server = http.createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

    const url = new URL(req.url, `http://${req.headers.host}`);

    if (url.pathname === '/api/status') {
        const roomList = [];
        for (const [id, room] of rooms) {
            roomList.push({ id, viewers: room.viewers.size, device: room.deviceInfo });
        }
        const adbList = [];
        for (const [id, aRoom] of adbRooms) {
            adbList.push({ id, hasController: !!aRoom.controller, device: aRoom.deviceInfo, age: Math.round((Date.now() - aRoom.createdAt) / 1000) });
        }
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, rooms: roomList, adbRooms: adbList, uptime: process.uptime() }));
        return;
    }

    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('P2P Signaling Server. WebSocket at ws://host:' + PORT + '/?role=provider|viewer&room=ROOM_ID');
});

const wss = new WebSocketServer({ server });

wss.on('connection', (ws, req) => {
    const url = new URL(req.url, `http://${req.headers.host}`);
    const role = url.searchParams.get('role');
    const roomId = url.searchParams.get('room');

    if (!role || !roomId) {
        ws.close(4000, 'Missing ?role=provider|viewer&room=ID');
        return;
    }

    ws._isAlive = true;
    ws.on('pong', () => { ws._isAlive = true; });

    // ── Provider (手机端) ──
    if (role === 'provider') {
        let room = rooms.get(roomId);
        if (!room) {
            room = { provider: ws, viewers: new Map(), deviceInfo: {} };
            rooms.set(roomId, room);
        } else {
            // Provider reconnect
            room.provider = ws;
            room.viewers.forEach((v) => safeSend(v, { type: 'provider_reconnected' }));
        }
        log(`Provider joined room ${roomId}`);

        safeSend(ws, { type: 'registered', data: { roomId, viewerCount: room.viewers.size } });

        ws.on('message', (raw) => {
            try {
                const msg = JSON.parse(raw.toString());
                handleProviderMsg(roomId, msg);
            } catch (e) { /* ignore */ }
        });

        ws.on('close', () => {
            const room = rooms.get(roomId);
            if (room && room.provider === ws) {
                log(`Provider left room ${roomId}`);
                room.viewers.forEach((v) => safeSend(v, { type: 'provider_disconnected' }));
                rooms.delete(roomId);
            }
        });
        return;
    }

    // ── Viewer (浏览器端) ──
    if (role === 'viewer') {
        const room = rooms.get(roomId);
        if (!room) {
            safeSend(ws, { type: 'error', data: { message: 'Room not found' } });
            ws.close(4004, 'Room not found');
            return;
        }

        const viewerId = 'v-' + Math.random().toString(36).substring(2, 8);
        room.viewers.set(viewerId, ws);
        log(`Viewer ${viewerId} joined room ${roomId} (${room.viewers.size} viewers)`);

        safeSend(ws, { type: 'joined', data: { roomId, viewerId, deviceInfo: room.deviceInfo, viewerCount: room.viewers.size } });
        safeSend(room.provider, { type: 'viewer_joined', data: { viewerId, count: room.viewers.size } });

        ws.on('message', (raw) => {
            try {
                const msg = JSON.parse(raw.toString());
                // Forward SDP/ICE from viewer to provider (tagged with viewerId)
                msg._viewerId = viewerId;
                safeSend(room.provider, msg);
            } catch (e) { /* ignore */ }
        });

        ws.on('close', () => {
            const room = rooms.get(roomId);
            if (room) {
                room.viewers.delete(viewerId);
                log(`Viewer ${viewerId} left room ${roomId} (${room.viewers.size} viewers)`);
                safeSend(room.provider, { type: 'viewer_left', data: { viewerId, count: room.viewers.size } });
            }
        });
        return;
    }

    // ── ADB Bridge (PC with ADB + USB phone) ──
    if (role === 'adb-bridge') {
        let aRoom = adbRooms.get(roomId);
        if (aRoom && aRoom.bridge && aRoom.bridge.readyState === WebSocket.OPEN) {
            // Another bridge already connected with this code
            safeSend(ws, { type: 'error', data: { message: 'Room code already in use' } });
            ws.close(4001, 'Room code already in use');
            return;
        }
        aRoom = { bridge: ws, controller: null, deviceInfo: {}, createdAt: Date.now() };
        adbRooms.set(roomId, aRoom);
        log(`[ADB] Bridge connected, room=${roomId}`);
        safeSend(ws, { type: 'adb_registered', data: { roomId } });

        ws.on('message', (raw) => {
            try {
                const msg = JSON.parse(raw.toString());
                const r = adbRooms.get(roomId);
                if (!r) return;
                if (msg.type === 'device_info') {
                    r.deviceInfo = msg.data || {};
                }
                // Forward all messages from bridge to controller
                if (r.controller && r.controller.readyState === WebSocket.OPEN) {
                    safeSend(r.controller, msg);
                }
            } catch (e) { /* ignore */ }
        });

        ws.on('close', () => {
            const r = adbRooms.get(roomId);
            if (r && r.bridge === ws) {
                log(`[ADB] Bridge disconnected, room=${roomId}`);
                if (r.controller) safeSend(r.controller, { type: 'bridge_disconnected' });
                adbRooms.delete(roomId);
            }
        });
        return;
    }

    // ── ADB Controller (web page sending ADB commands) ──
    if (role === 'adb-controller') {
        const aRoom = adbRooms.get(roomId);
        if (!aRoom) {
            safeSend(ws, { type: 'error', data: { message: 'ADB Bridge not found. Check the code.' } });
            ws.close(4004, 'ADB room not found');
            return;
        }
        if (aRoom.controller && aRoom.controller.readyState === WebSocket.OPEN) {
            // Disconnect old controller
            safeSend(aRoom.controller, { type: 'replaced', data: { message: 'Another controller connected' } });
            aRoom.controller.close(4002, 'Replaced');
        }
        aRoom.controller = ws;
        log(`[ADB] Controller connected, room=${roomId}`);
        safeSend(ws, { type: 'adb_connected', data: { roomId, deviceInfo: aRoom.deviceInfo } });
        safeSend(aRoom.bridge, { type: 'controller_connected' });

        ws.on('message', (raw) => {
            try {
                const msg = JSON.parse(raw.toString());
                const r = adbRooms.get(roomId);
                if (!r || !r.bridge || r.bridge.readyState !== WebSocket.OPEN) {
                    safeSend(ws, { type: 'error', data: { message: 'Bridge offline' } });
                    return;
                }
                // Forward all messages from controller to bridge
                safeSend(r.bridge, msg);
            } catch (e) { /* ignore */ }
        });

        ws.on('close', () => {
            const r = adbRooms.get(roomId);
            if (r && r.controller === ws) {
                r.controller = null;
                log(`[ADB] Controller disconnected, room=${roomId}`);
                safeSend(r.bridge, { type: 'controller_disconnected' });
            }
        });
        return;
    }

    ws.close(4000, 'Invalid role');
});

function handleProviderMsg(roomId, msg) {
    const room = rooms.get(roomId);
    if (!room) return;

    switch (msg.type) {
        case 'device_info':
            room.deviceInfo = msg.data || {};
            room.viewers.forEach((v) => safeSend(v, msg));
            break;

        case 'answer':
        case 'candidate':
            // SDP answer or ICE candidate targeted at a specific viewer
            const targetId = msg._viewerId;
            if (targetId && room.viewers.has(targetId)) {
                safeSend(room.viewers.get(targetId), msg);
            }
            break;

        default:
            // Forward unknown messages to all viewers
            room.viewers.forEach((v) => safeSend(v, msg));
    }
}

function safeSend(ws, data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        try { ws.send(JSON.stringify(data)); } catch (e) { /* ignore */ }
    }
}

// Heartbeat
const heartbeat = setInterval(() => {
    wss.clients.forEach(ws => {
        if (!ws._isAlive) return ws.terminate();
        ws._isAlive = false;
        ws.ping();
    });
}, 30000);
wss.on('close', () => clearInterval(heartbeat));

function log(msg) {
    console.log(`[${new Date().toISOString().slice(11, 19)}] ${msg}`);
}

server.listen(PORT, () => {
    log(`P2P Signaling Server listening on :${PORT}`);
    log(`Rooms: /api/status`);
});
