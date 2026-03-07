// Mock P2P provider for E2E testing
// Connects to signaling server as a provider, creates a room, and responds to viewer offers
const WebSocket = require('ws');

const SIGNALING_URL = 'ws://localhost:9100/signal/';
const ROOM_ID = '888888';

console.log(`[MockProvider] Connecting to ${SIGNALING_URL} as provider, room=${ROOM_ID}`);

const ws = new WebSocket(`${SIGNALING_URL}?role=provider&room=${ROOM_ID}`);

ws.on('open', () => {
  console.log('[MockProvider] Connected! Room code:', ROOM_ID);
  console.log('[MockProvider] Waiting for viewer to join...');
});

ws.on('message', (data) => {
  try {
    const msg = JSON.parse(data.toString());
    console.log(`[MockProvider] Received: type=${msg.type}`);
    
    if (msg.type === 'viewer_joined') {
      console.log('[MockProvider] Viewer joined! Sending mock offer...');
      // Send a mock SDP offer to trigger the viewer's P2P flow
      ws.send(JSON.stringify({
        type: 'offer',
        data: {
          sdp: 'v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\nc=IN IP4 0.0.0.0\r\na=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:test\r\na=ice-pwd:testpassword1234567890ab\r\na=fingerprint:sha-256 00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00\r\na=setup:actpass\r\na=mid:0\r\na=sendonly\r\na=rtpmap:96 H264/90000\r\n',
          type: 'offer'
        }
      }));
    }
    
    if (msg.type === 'answer') {
      console.log('[MockProvider] Got answer from viewer!');
      console.log('[MockProvider] P2P signaling flow COMPLETE ✅');
    }
    
    if (msg.type === 'ice_candidate') {
      console.log('[MockProvider] Got ICE candidate from viewer');
    }
    
    if (msg.type === 'error') {
      console.error('[MockProvider] Error:', msg.data?.message);
    }
  } catch (e) {
    console.error('[MockProvider] Parse error:', e.message);
  }
});

ws.on('close', (code, reason) => {
  console.log(`[MockProvider] Disconnected: code=${code} reason=${reason}`);
});

ws.on('error', (err) => {
  console.error('[MockProvider] Error:', err.message);
});

// Auto-close after 60 seconds
setTimeout(() => {
  console.log('[MockProvider] Test timeout, closing...');
  ws.close();
  process.exit(0);
}, 60000);
