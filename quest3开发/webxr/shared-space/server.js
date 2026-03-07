const http = require('http');
const { WebSocketServer } = require('ws');

const PORT = process.env.PORT || 9200;
const MAX_MSG_SIZE = 2048;
const MAX_USERS = 50;
const RATE_LIMIT_MS = 50;
const MAX_NAME_LEN = 20;
const COLOR_RE = /^#[0-9a-fA-F]{3,8}$/;
const VALID_TYPES = new Set(['join', 'pos', 'chat']);

const server = http.createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', users: Object.keys(users).length }));
});

const wss = new WebSocketServer({ server, maxPayload: MAX_MSG_SIZE });
const users = {};

wss.on('connection', (ws) => {
    let userId = null;
    let lastMsg = 0;

    if (Object.keys(users).length >= MAX_USERS) {
        ws.close(1013, 'Server full');
        return;
    }

    ws.on('message', (data) => {
        const now = Date.now();
        if (now - lastMsg < RATE_LIMIT_MS) return;
        lastMsg = now;

        try {
            const raw = data.toString();
            if (raw.length > MAX_MSG_SIZE) return;
            const msg = JSON.parse(raw);
            if (!msg.type || !VALID_TYPES.has(msg.type)) return;

            if (msg.type === 'join') {
                if (!msg.id || typeof msg.id !== 'string') return;
                const name = String(msg.name || '').substring(0, MAX_NAME_LEN) || 'anon';
                const color = COLOR_RE.test(msg.color) ? msg.color : '#888';
                userId = msg.id.substring(0, 16);
                users[userId] = { id: userId, name, color, ws };
                // Send current state to new user
                const userList = Object.values(users)
                    .filter(u => u.id !== userId)
                    .map(u => ({ id: u.id, name: u.name, color: u.color }));
                ws.send(JSON.stringify({ type: 'state', users: userList }));
                // Broadcast sanitized join
                broadcast(JSON.stringify({ type: 'join', id: userId, name, color }), userId);
                console.log(`[+] ${name} joined (${Object.keys(users).length} online)`);
            } else if (msg.type === 'chat') {
                if (!userId) return;
                const text = String(msg.text || '').substring(0, 500);
                if (!text) return;
                broadcast(JSON.stringify({ type: 'chat', id: userId, text }), userId);
            } else if (msg.type === 'pos') {
                if (!userId) return;
                const p = msg.pos;
                if (!p || typeof p.x !== 'number' || typeof p.y !== 'number' || typeof p.z !== 'number') return;
                broadcast(JSON.stringify({
                    type: 'pos', id: userId,
                    pos: { x: +p.x.toFixed(2), y: +p.y.toFixed(2), z: +p.z.toFixed(2) },
                    rot: msg.rot || {}
                }), userId);
            }
        } catch (e) {}
    });

    ws.on('close', () => {
        if (userId && users[userId]) {
            const name = users[userId].name;
            delete users[userId];
            broadcast(JSON.stringify({ type: 'leave', id: userId }));
            console.log(`[-] ${name} left (${Object.keys(users).length} online)`);
        }
    });
});

function broadcast(data, excludeId) {
    for (const [id, user] of Object.entries(users)) {
        if (id !== excludeId && user.ws.readyState === 1) {
            user.ws.send(data);
        }
    }
}

server.listen(PORT, () => {
    console.log(`[SharedSpace] WebSocket server on :${PORT}`);
});
