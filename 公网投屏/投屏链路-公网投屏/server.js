/**
 * ScreenStream Self-Hosted Signaling Server
 *
 * Protocol-compatible with dkrivoruchko/ScreenStreamWeb (MIT License).
 * Simplified: no Play Integrity, no Cloudflare Turnstile, no DataDog.
 *
 * Flow:
 *   1. Host (Android app) connects → STREAM:CREATE → gets room
 *   2. Client (web browser) connects → STREAM:JOIN → joins room
 *   3. Server relays WebRTC signaling (offer/answer/candidates) between them
 *   4. P2P WebRTC connection established, media flows directly
 */

import { randomBytes, createHmac } from 'crypto';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import express from 'express';
import { Server } from 'socket.io';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PORT = process.env.PORT || 9100;
const SOCKET_TIMEOUT = 10_000;
const STREAM_ID_LENGTH = 8;
const STREAM_ID_CHARS = '0123456789';

// Optional TURN server config via environment
const TURN_SERVER = process.env.TURN_SERVER;        // e.g. "turn:turn.aiotvr.xyz:3478"
const TURN_SECRET = process.env.TURN_SECRET;        // coturn shared secret
const TURN_CREDENTIAL_TTL = 6 * 60 * 60;           // 6 hours

// ─── ICE Servers ────────────────────────────────────────────────────────────

const GOOGLE_STUN = [
  'stun:stun.l.google.com:19302',
  'stun:stun1.l.google.com:19302',
  'stun:stun2.l.google.com:19302',
  'stun:stun3.l.google.com:19302',
  'stun:stun4.l.google.com:19302',
];

function getIceServers(username) {
  const servers = [];

  // Random STUN server
  const stun = GOOGLE_STUN[Math.floor(Math.random() * GOOGLE_STUN.length)];
  servers.push({ urls: stun });

  // TURN server (if configured)
  if (TURN_SERVER && TURN_SECRET) {
    const timestamp = Math.floor(Date.now() / 1000) + TURN_CREDENTIAL_TTL;
    const turnUser = `${timestamp}:${username}`;
    const credential = createHmac('sha1', TURN_SECRET).update(turnUser).digest('base64');
    servers.push({ urls: TURN_SERVER, username: turnUser, credential });
  }

  return servers;
}

// ─── Stream Management ──────────────────────────────────────────────────────

function createStreamId(io) {
  let id;
  do {
    id = '';
    for (let i = 0; i < STREAM_ID_LENGTH; i++) {
      id += STREAM_ID_CHARS.charAt(Math.floor(Math.random() * STREAM_ID_CHARS.length));
    }
  } while (io.sockets.adapter.rooms.has(id));
  return id;
}

function isValidStreamId(id) {
  return typeof id === 'string' && /^\d+$/.test(id) && id.length === STREAM_ID_LENGTH;
}

function getStreamId(socket) {
  return Array.from(socket.rooms).find(room => room !== socket.id);
}

async function getHostSocket(io, streamId) {
  try {
    const sockets = await io.in(streamId).fetchSockets();
    return sockets.find(s => s.data?.isHost === true) || null;
  } catch { return null; }
}

// ─── JWT Helper ─────────────────────────────────────────────────────────────
// Android host sends { jwt: "header.payload.signature" } in STREAM:CREATE
// We decode the payload to extract streamId (no crypto verification in self-hosted mode)

function extractStreamIdFromJWT(jwt) {
  if (!jwt || typeof jwt !== 'string') return null;
  const parts = jwt.split('.');
  if (parts.length !== 3) return null;
  try {
    // base64url → base64 → JSON
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const decoded = JSON.parse(Buffer.from(payload, 'base64').toString('utf8'));
    return decoded.streamId || null;
  } catch { return null; }
}

// ─── Express App ────────────────────────────────────────────────────────────

const app = express()
  .set('x-powered-by', false)
  .set('trust proxy', true)
  .use(express.static(join(__dirname, 'client')))
  .get('/app/nonce', (_, res) => {
    res.setHeader('Cache-Control', 'no-store');
    res.send(randomBytes(32).toString('hex'));
  })
  .get('/app/ping', (_, res) => res.sendStatus(204))
  .get('/api/status', (_, res) => {
    const rooms = io.sockets.adapter.rooms;
    let streams = 0, clients = 0;
    for (const [, sockets] of rooms) {
      if (sockets.size > 0) streams++;
      clients += sockets.size;
    }
    res.json({ status: 'ok', streams, clients, uptime: process.uptime() | 0 });
  });

const server = app.listen(PORT, () => {
  console.log(`[ScreenStream Relay] Listening on :${PORT}`);
  console.log(`[ScreenStream Relay] TURN: ${TURN_SERVER ? 'configured' : 'disabled (STUN only)'}`);
});

// ─── Socket.IO ──────────────────────────────────────────────────────────────

const io = new Server(server, {
  path: '/app/socket',
  transports: ['websocket'],
  cleanupEmptyChildNamespaces: true,
  pingTimeout: 30_000,
  pingInterval: 25_000,
});

// ─── Auth Middleware ────────────────────────────────────────────────────────
// Host: sends { token, device } → isHost=true
// Client: sends { token } (no device) → isClient=true

io.use((socket, next) => {
  const auth = socket.handshake.auth || {};
  // Android host sends { hostToken, device }, web client sends { token }
  const token = auth.hostToken || auth.token;

  if (!token || typeof token !== 'string') {
    return next(new Error('AUTH:NO_TOKEN'));
  }

  if (auth.device) {
    // Host (Android app) — identified by presence of 'device' field
    socket.data = { isHost: true, isClient: false, device: auth.device };
  } else {
    // Client (web browser)
    socket.data = { isHost: false, isClient: true };
  }

  next();
});

// ─── Connection Handler ─────────────────────────────────────────────────────

io.on('connection', (socket) => {
  const role = socket.data.isHost ? 'HOST' : 'CLIENT';
  console.log(`[${role}] Connected: ${socket.id}`);

  socket.on('disconnect', (reason) => {
    console.log(`[${role}] Disconnected: ${socket.id} (${reason})`);
    socket.removeAllListeners();
    socket.data = undefined;
  });

  socket.data.errorCounter = 0;

  if (socket.data.isHost) {
    setupHostHandlers(socket);
  }
  if (socket.data.isClient) {
    setupClientHandlers(socket);
  }
});

// ─── Host Handlers ──────────────────────────────────────────────────────────
// Events from Android app (host)

function setupHostHandlers(socket) {

  // [STREAM:CREATE] Host requests to create or reclaim a stream room
  // Android sends { jwt: "..." } where JWT payload contains streamId
  socket.on('STREAM:CREATE', async (payload, callback) => {
    if (!payload || !callback) return;

    // Support both { jwt } (Android) and { streamId } (direct)
    let streamId = payload.streamId || extractStreamIdFromJWT(payload.jwt);

    // If requested ID is taken by another host, generate new one
    if (streamId && isValidStreamId(streamId)) {
      const existing = await getHostSocket(io, streamId);
      if (existing && existing.id !== socket.id) {
        streamId = createStreamId(io);
      }
    } else {
      streamId = createStreamId(io);
    }

    // Leave any previous room
    const prevRoom = getStreamId(socket);
    if (prevRoom) socket.leave(prevRoom);

    socket.join(streamId);
    socket.data.streamId = streamId;
    console.log(`[HOST] Stream created: ${streamId} by ${socket.id}`);
    callback({ status: 'OK', streamId });
  });

  // [STREAM:REMOVE] Host removes its stream
  socket.on('STREAM:REMOVE', async (_, callback) => {
    const streamId = socket.data.streamId;
    if (!streamId) {
      callback?.({ status: 'ERROR:NO_STREAM' });
      return;
    }

    // Notify all clients in this room
    const sockets = await io.in(streamId).fetchSockets();
    for (const s of sockets) {
      if (s.data?.isClient && s.connected) {
        s.emit('REMOVE:STREAM', {});
        s.leave(streamId);
      }
    }

    socket.leave(streamId);
    socket.data.streamId = null;
    console.log(`[HOST] Stream removed: ${streamId}`);
    callback?.({ status: 'OK' });
  });

  // [STREAM:START] Host notifies that streaming has started
  socket.on('STREAM:START', async (payload, callback) => {
    const streamId = socket.data.streamId;
    if (!streamId) {
      callback?.({ status: 'ERROR:NO_STREAM' });
      return;
    }

    const targetClientId = payload?.clientId;

    if (targetClientId && targetClientId !== 'ALL') {
      // Notify specific client
      const sockets = await io.in(streamId).fetchSockets();
      const client = sockets.find(s => s.data?.clientId === targetClientId);
      if (!client || !client.connected) {
        callback?.({ status: 'ERROR:NO_CLIENT_FOUND' });
        return;
      }
      client.timeout(SOCKET_TIMEOUT).emit('STREAM:START', {}, (err, resp) => {
        if (err) { callback?.({ status: 'ERROR:TIMEOUT' }); return; }
        callback?.({ status: resp?.status || 'OK' });
      });
    } else {
      // Notify all clients
      const sockets = await io.in(streamId).fetchSockets();
      for (const s of sockets) {
        if (s.data?.isClient && s.connected) {
          s.emit('STREAM:START', {});
        }
      }
      callback?.({ status: 'OK' });
    }
  });

  // [STREAM:STOP] Host stops streaming
  socket.on('STREAM:STOP', async (_, callback) => {
    const streamId = socket.data.streamId;
    if (!streamId) {
      callback?.({ status: 'ERROR:NO_STREAM' });
      return;
    }

    const sockets = await io.in(streamId).fetchSockets();
    for (const s of sockets) {
      if (s.data?.isClient && s.connected) {
        s.emit('STREAM:STOP', {});
      }
    }
    callback?.({ status: 'OK' });
  });

  // [HOST:OFFER] Host sends WebRTC offer to a specific client
  socket.on('HOST:OFFER', async (payload, callback) => {
    if (!payload?.clientId || !payload?.offer) {
      callback?.({ status: 'ERROR:EMPTY_OR_BAD_DATA' });
      return;
    }

    const streamId = socket.data.streamId;
    if (!streamId) {
      callback?.({ status: 'ERROR:NO_STREAM' });
      return;
    }

    const sockets = await io.in(streamId).fetchSockets();
    const client = sockets.find(s => s.data?.clientId === payload.clientId);
    if (!client?.connected) {
      callback?.({ status: 'ERROR:NO_CLIENT_FOUND' });
      return;
    }

    client.timeout(SOCKET_TIMEOUT).emit('HOST:OFFER', { offer: payload.offer }, (err, resp) => {
      if (err) { callback?.({ status: 'ERROR:TIMEOUT_OR_NO_RESPONSE' }); return; }
      callback?.({ status: resp?.status || 'OK' });
    });
  });

  // [HOST:CANDIDATE] Host sends ICE candidates to a specific client
  socket.on('HOST:CANDIDATE', async (payload, callback) => {
    if (!payload?.clientId || (!payload?.candidate && !payload?.candidates)) {
      callback?.({ status: 'ERROR:EMPTY_OR_BAD_DATA' });
      return;
    }

    const streamId = socket.data.streamId;
    if (!streamId) {
      callback?.({ status: 'ERROR:NO_STREAM' });
      return;
    }

    const sockets = await io.in(streamId).fetchSockets();
    const client = sockets.find(s => s.data?.clientId === payload.clientId);
    if (!client?.connected) {
      callback?.({ status: 'ERROR:NO_CLIENT_FOUND' });
      return;
    }

    const candidates = payload.candidates || [payload.candidate];
    client.timeout(SOCKET_TIMEOUT).emit('HOST:CANDIDATE', { candidates }, (err, resp) => {
      if (err) { callback?.({ status: 'ERROR:TIMEOUT_OR_NO_RESPONSE' }); return; }
      callback?.({ status: resp?.status || 'OK' });
    });
  });

  // [REMOVE:CLIENT] Host kicks specific clients
  socket.on('REMOVE:CLIENT', async (payload, callback) => {
    if (!payload?.clientId || !Array.isArray(payload.clientId)) {
      callback?.({ status: 'ERROR:EMPTY_OR_BAD_DATA' });
      return;
    }

    const streamId = socket.data.streamId;
    const allSockets = await io.fetchSockets();
    const targets = allSockets.filter(
      s => s.data?.isClient && payload.clientId.includes(s.data.clientId)
    );

    for (const t of targets) {
      if (t.connected) {
        t.rooms.forEach(r => { if (r !== t.id) t.leave(r); });
        t.emit('REMOVE:CLIENT', {});
      }
    }

    callback?.({ status: 'OK' });
  });

  // Cleanup on disconnect: notify clients
  socket.on('disconnect', async () => {
    const streamId = socket.data?.streamId;
    if (!streamId) return;

    try {
      const sockets = await io.in(streamId).fetchSockets();
      for (const s of sockets) {
        if (s.data?.isClient && s.connected) {
          s.emit('REMOVE:STREAM', {});
          s.leave(streamId);
        }
      }
    } catch { }
  });
}

// ─── Client Handlers ────────────────────────────────────────────────────────
// Events from web browser (client)

function setupClientHandlers(socket) {

  // [STREAM:JOIN] Client wants to join a stream
  socket.on('STREAM:JOIN', async (payload, callback) => {
    if (!payload?.streamId || !isValidStreamId(payload.streamId)) {
      callback?.({ status: 'ERROR:INVALID_STREAM_ID' });
      return;
    }

    const streamId = payload.streamId;
    const host = await getHostSocket(io, streamId);
    if (!host?.connected) {
      callback?.({ status: 'ERROR:NO_STREAM_FOUND' });
      return;
    }

    // Generate unique client ID
    const clientId = randomBytes(8).toString('hex');
    socket.data.clientId = clientId;
    socket.join(streamId);

    const iceServers = getIceServers(socket.id);

    // Notify host about new client (event name must be STREAM:JOIN to match Android's SocketSignaling.kt)
    host.timeout(SOCKET_TIMEOUT).emit('STREAM:JOIN',
      { clientId, passwordHash: payload.passwordHash || '', iceServers },
      (err, resp) => {
        if (err) {
          socket.leave(streamId);
          callback?.({ status: 'ERROR:HOST_TIMEOUT' });
          return;
        }
        if (resp?.status !== 'OK') {
          socket.leave(streamId);
          callback?.({ status: resp?.status || 'ERROR:HOST_REJECTED' });
          return;
        }

        console.log(`[CLIENT] Joined stream ${streamId} as ${clientId}`);
        callback?.({ status: 'OK', iceServers, clientId });
      }
    );
  });

  // [CLIENT:ANSWER] Client sends WebRTC answer to host
  socket.on('CLIENT:ANSWER', async (payload, callback) => {
    if (!payload?.answer) {
      callback?.({ status: 'ERROR:EMPTY_OR_BAD_DATA' });
      return;
    }

    const streamId = getStreamId(socket);
    if (!streamId) {
      callback?.({ status: 'ERROR:NO_STREAM_JOINED' });
      return;
    }

    const host = await getHostSocket(io, streamId);
    if (!host?.connected) {
      callback?.({ status: 'ERROR:NO_STREAM_HOST_FOUND' });
      return;
    }

    host.timeout(SOCKET_TIMEOUT).emit('CLIENT:ANSWER',
      { clientId: socket.data.clientId, answer: payload.answer },
      (err, resp) => {
        if (err) { callback?.({ status: 'ERROR:TIMEOUT_OR_NO_RESPONSE' }); return; }
        callback?.({ status: resp?.status || 'OK' });
      }
    );
  });

  // [CLIENT:CANDIDATE] Client sends ICE candidate to host
  socket.on('CLIENT:CANDIDATE', async (payload, callback) => {
    if (!payload?.candidate) {
      callback?.({ status: 'ERROR:EMPTY_OR_BAD_DATA' });
      return;
    }

    const streamId = getStreamId(socket);
    if (!streamId) {
      callback?.({ status: 'ERROR:NO_STREAM_JOINED' });
      return;
    }

    const host = await getHostSocket(io, streamId);
    if (!host?.connected) {
      callback?.({ status: 'ERROR:NO_STREAM_HOST_FOUND' });
      return;
    }

    host.timeout(SOCKET_TIMEOUT).emit('CLIENT:CANDIDATE',
      { clientId: socket.data.clientId, candidate: payload.candidate },
      (err, resp) => {
        if (err) { callback?.({ status: 'ERROR:TIMEOUT_OR_NO_RESPONSE' }); return; }
        callback?.({ status: resp?.status || 'OK' });
      }
    );
  });

  // [STREAM:LEAVE] Client leaves the stream
  socket.on('STREAM:LEAVE', async (callback) => {
    const streamId = getStreamId(socket);
    if (!streamId) {
      callback?.({ status: 'ERROR:NO_STREAM_JOINED' });
      return;
    }

    socket.leave(streamId);

    const host = await getHostSocket(io, streamId);
    if (host?.connected) {
      host.timeout(SOCKET_TIMEOUT).emit('STREAM:LEAVE',
        { clientId: socket.data.clientId },
        (err, resp) => {
          callback?.({ status: resp?.status || 'OK' });
        }
      );
    } else {
      callback?.({ status: 'OK' });
    }
  });

  // Cleanup on disconnect: notify host
  socket.on('disconnect', async () => {
    const streamId = getStreamId(socket);
    const clientId = socket.data?.clientId;
    if (!streamId || !clientId) return;

    try {
      const host = await getHostSocket(io, streamId);
      if (host?.connected) {
        host.emit('STREAM:LEAVE', { clientId });
      }
    } catch { }
  });
}

// ─── Graceful Shutdown ──────────────────────────────────────────────────────

process.on('SIGTERM', () => {
  io.disconnectSockets(true);
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 5000);
});

process.on('SIGINT', () => {
  io.disconnectSockets(true);
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 5000);
});
