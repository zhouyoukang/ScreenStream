/**
 * 亲情远程 — WebRTC 信令服务器
 * 
 * 协议匹配 WebRtcP2PClient.kt 的信令消息格式。
 * 职责：仅中继SDP/ICE信令，不接触任何媒体流。
 * 
 * 本地开发：node server.js (默认端口9100，可通过PORT环境变量覆盖)
 * 生产部署：Nginx反代 wss://域名/signal/ → ws://127.0.0.1:PORT/
 */

const http = require('http');
const { WebSocketServer, WebSocket } = require('ws');
const { readFileSync, existsSync, statSync } = require('fs');
const { join, resolve, extname } = require('path');
const crypto = require('crypto');

const PORT = parseInt(process.env.PORT || '9100');
const VIEWER_DIR = join(__dirname, '..', 'viewer');

// ─── HTTP Server (raw, no express) ───
const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  // Health ping
  if (url.pathname === '/app/ping') {
    res.writeHead(204);
    res.end();
    return;
  }

  // Status API
  if (url.pathname === '/api/status') {
    const roomList = [];
    for (const [roomId, room] of rooms) {
      roomList.push({
        id: roomId,
        viewers: room.viewers.size,
        device: room.provider ? { model: room.providerDevice, connected: true } : null
      });
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      ok: true,
      rooms: roomList,
      totalRooms: rooms.size,
      uptime: process.uptime()
    }));
    return;
  }

  // Nonce
  if (url.pathname === '/app/nonce') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ nonce: crypto.randomBytes(16).toString('hex') }));
    return;
  }

  // Static files: /cast/* → viewer directory
  if (url.pathname.startsWith('/cast')) {
    let filePath;
    const subPath = url.pathname.replace(/^\/cast\/?/, '') || 'index.html';
    const resolved = resolve(VIEWER_DIR, subPath);
    if (resolved.startsWith(resolve(VIEWER_DIR))) filePath = resolved;
    if (filePath && existsSync(filePath) && statSync(filePath).isFile()) {
      const ext = extname(filePath).slice(1);
      const types = { html: 'text/html', js: 'application/javascript', css: 'text/css', png: 'image/png', ico: 'image/x-icon' };
      res.writeHead(200, { 'Content-Type': (types[ext] || 'application/octet-stream') + '; charset=utf-8' });
      require('fs').createReadStream(filePath).pipe(res);
      return;
    }
  }

  res.writeHead(404);
  res.end('Not Found');
});

// ─── Room Management ───

class Room {
  constructor(id) {
    this.id = id;
    this.provider = null;       // WebSocket of the phone (provider)
    this.providerDevice = '';
    this.viewers = new Map();   // viewerId -> WebSocket
    this.created = new Date().toISOString();
  }

  addViewer(viewerId, ws) {
    this.viewers.set(viewerId, ws);
  }

  removeViewer(viewerId) {
    this.viewers.delete(viewerId);
  }

  destroy() {
    if (this.provider && this.provider.readyState === WebSocket.OPEN) {
      this.provider.close(1000, 'Room destroyed');
    }
    for (const [, ws] of this.viewers) {
      if (ws.readyState === WebSocket.OPEN) ws.close(1000, 'Room destroyed');
    }
    this.viewers.clear();
  }
}

const rooms = new Map(); // roomId -> Room

// ─── Rate Limiting (brute-force protection) ───
const ipConnections = new Map(); // ip -> { count, resetAt }
const RATE_LIMIT_WINDOW = 60_000; // 1 minute
const RATE_LIMIT_MAX = 10; // max connections per IP per window

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

// Clean stale rooms every 5 minutes
setInterval(() => {
  const now = Date.now();
  for (const [roomId, room] of rooms) {
    const age = now - new Date(room.created).getTime();
    if (age > 24 * 60 * 60 * 1000 && room.viewers.size === 0 && !room.provider) {
      rooms.delete(roomId);
      console.log(`[GC] Removed stale room ${roomId}`);
    }
  }
}, 5 * 60 * 1000);

// ─── WebSocket Signaling ───

const wss = new WebSocketServer({ server });

wss.on('connection', (ws, req) => {
  // Heartbeat: mark alive on connect and pong
  ws._isAlive = true;
  ws.on('pong', () => { ws._isAlive = true; });

  const ip = req.headers['x-forwarded-for']?.split(',')[0]?.trim() || req.socket.remoteAddress;
  const url = new URL(req.url, `http://${req.headers.host}`);
  const role = url.searchParams.get('role');     // 'provider' or 'viewer'
  const roomId = url.searchParams.get('room');
  const device = url.searchParams.get('device') || 'Unknown';

  if (!role || !roomId) {
    ws.close(4001, 'Missing role or room parameter');
    return;
  }

  // Rate limiting
  if (!checkRateLimit(ip)) {
    console.warn(`[RATE] Blocked ${ip} (exceeded ${RATE_LIMIT_MAX}/min)`);
    ws.close(4029, 'Rate limit exceeded');
    return;
  }

  console.log(`[WS] ${role} connected: room=${roomId}, device=${device}, ip=${ip}`);

  if (role === 'provider') {
    handleProvider(ws, roomId, device);
  } else if (role === 'viewer') {
    handleViewer(ws, roomId);
  } else {
    ws.close(4002, 'Invalid role');
  }
});

function handleProvider(ws, roomId, device) {
  // Create or reuse room
  let room = rooms.get(roomId);
  if (!room) {
    room = new Room(roomId);
    rooms.set(roomId, room);
  }

  // Replace existing provider if any
  if (room.provider && room.provider.readyState === WebSocket.OPEN) {
    room.provider.close(1000, 'Replaced by new provider');
  }

  room.provider = ws;
  room.providerDevice = device;

  // Confirm registration
  send(ws, {
    type: 'registered',
    data: { roomId, viewerCount: room.viewers.size }
  });

  // Notify provider about existing viewers
  for (const [viewerId] of room.viewers) {
    send(ws, {
      type: 'viewer_joined',
      data: { viewerId, count: room.viewers.size }
    });
  }

  ws.on('message', (data) => {
    try {
      const msg = JSON.parse(data.toString());
      handleProviderMessage(room, msg);
    } catch (e) {
      console.error(`[Provider] Parse error:`, e.message);
    }
  });

  ws.on('close', () => {
    console.log(`[WS] Provider left: room=${roomId}`);
    if (room.provider === ws) {
      room.provider = null;
      // Notify all viewers that provider disconnected
      for (const [viewerId, viewerWs] of room.viewers) {
        send(viewerWs, { type: 'provider_disconnected' });
      }
    }
    // Clean up empty room
    if (room.viewers.size === 0 && !room.provider) {
      rooms.delete(roomId);
    }
  });

  ws.on('error', (err) => console.error(`[Provider] Error:`, err.message));
}

function handleViewer(ws, roomId) {
  const room = rooms.get(roomId);
  if (!room) {
    send(ws, { type: 'error', data: { message: '房间不存在，请确认手机已开始投屏' } });
    ws.close(4004, 'Room not found');
    return;
  }

  const viewerId = 'v_' + crypto.randomBytes(6).toString('hex');
  ws._viewerId = viewerId;
  room.addViewer(viewerId, ws);

  console.log(`[WS] Viewer joined: room=${roomId}, viewerId=${viewerId}, total=${room.viewers.size}`);

  // Tell viewer their ID and room info
  send(ws, {
    type: 'joined',
    data: {
      viewerId,
      roomId,
      providerOnline: !!room.provider,
      device: room.providerDevice
    }
  });

  // Tell provider a new viewer joined
  if (room.provider && room.provider.readyState === WebSocket.OPEN) {
    send(room.provider, {
      type: 'viewer_joined',
      data: { viewerId, count: room.viewers.size }
    });
  }

  ws.on('message', (data) => {
    try {
      const msg = JSON.parse(data.toString());
      handleViewerMessage(room, viewerId, msg);
    } catch (e) {
      console.error(`[Viewer] Parse error:`, e.message);
    }
  });

  ws.on('close', () => {
    console.log(`[WS] Viewer left: room=${roomId}, viewerId=${viewerId}`);
    room.removeViewer(viewerId);
    // Notify provider
    if (room.provider && room.provider.readyState === WebSocket.OPEN) {
      send(room.provider, {
        type: 'viewer_left',
        data: { viewerId, count: room.viewers.size }
      });
    }
    // Clean up empty room
    if (room.viewers.size === 0 && !room.provider) {
      rooms.delete(roomId);
    }
  });

  ws.on('error', (err) => console.error(`[Viewer] Error:`, err.message));
}

// ─── Message Routing ───

function handleProviderMessage(room, msg) {
  // Provider sends: offer, candidate, answer, device_info
  const viewerId = msg._viewerId;

  switch (msg.type) {
    case 'offer':
    case 'answer':
    case 'candidate': {
      // Forward to specific viewer
      const viewerWs = room.viewers.get(viewerId);
      if (viewerWs && viewerWs.readyState === WebSocket.OPEN) {
        send(viewerWs, msg);
      }
      break;
    }
    case 'device_info': {
      room.providerDevice = msg.data?.model || room.providerDevice;
      break;
    }
  }
}

function handleViewerMessage(room, viewerId, msg) {
  // Viewer sends: answer, candidate
  if (!room.provider || room.provider.readyState !== WebSocket.OPEN) {
    return;
  }

  // Tag message with viewerId and forward to provider
  msg._viewerId = viewerId;
  send(room.provider, msg);
}

// ─── Utilities ───

function send(ws, msg) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
  }
}

// ─── Heartbeat (detect dead connections) ───

const HEARTBEAT_INTERVAL = 30000; // 30s

const heartbeat = setInterval(() => {
  wss.clients.forEach(ws => {
    if (ws._isAlive === false) {
      console.log(`[Heartbeat] Terminating dead connection`);
      return ws.terminate();
    }
    ws._isAlive = false;
    ws.ping();
  });
}, HEARTBEAT_INTERVAL);

wss.on('close', () => clearInterval(heartbeat));

// ─── Graceful Shutdown ───

function gracefulShutdown(signal) {
  console.log(`[${signal}] Shutting down...`);
  clearInterval(heartbeat);
  // Close all rooms
  for (const [roomId, room] of rooms) {
    room.destroy();
    rooms.delete(roomId);
  }
  wss.close(() => {
    server.close(() => {
      console.log(`[Shutdown] Complete`);
      process.exit(0);
    });
  });
  // Force exit after 5s
  setTimeout(() => process.exit(1), 5000);
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

// ─── Start ───

// ─── 崩溃保护 ───
process.on('uncaughtException', (err) => {
  console.error(`[FATAL] Uncaught exception: ${err.message}`);
  console.error(err.stack);
});
process.on('unhandledRejection', (reason) => {
  console.warn(`[WARN] Unhandled rejection: ${reason}`);
});

server.listen(PORT, () => {
  console.log(`[Family Remote Signaling] Running on port ${PORT}`);
  console.log(`  WebSocket: ws://localhost:${PORT}/signal/`);
  console.log(`  Viewer:    http://localhost:${PORT}/cast/`);
  console.log(`  Status:    http://localhost:${PORT}/api/status`);
  console.log(`  Ping:      http://localhost:${PORT}/app/ping`);
});
