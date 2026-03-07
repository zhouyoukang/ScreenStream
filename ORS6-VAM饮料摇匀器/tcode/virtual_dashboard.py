"""ORS6 虚拟仪表盘 — HTTP + WebSocket 服务器 + Three.js 3D可视化

启动后打开浏览器访问 http://localhost:8085 即可看到:
- 6轴3D机械臂实时运动
- 各轴位置/速度仪表
- TCode命令历史
- 手动控制面板

用法:
    # 独立运行 (内置虚拟设备)
    python -m tcode.virtual_dashboard

    # 或传入已有虚拟设备
    from tcode.virtual_device import VirtualORS6
    from tcode.virtual_dashboard import DashboardServer
    dev = VirtualORS6()
    server = DashboardServer(dev, port=8085)
    server.start()  # 阻塞
"""

import json
import time
import asyncio
import logging
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional

logger = logging.getLogger(__name__)

# ── 内嵌HTML (Three.js 3D仪表盘) ──

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ORS6 Virtual Device</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0f;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;overflow:hidden}
#app{display:grid;grid-template-columns:1fr 320px;grid-template-rows:48px 1fr 200px;height:100vh;gap:1px;background:#1a1a2e}
header{grid-column:1/-1;background:#16213e;display:flex;align-items:center;padding:0 16px;gap:16px}
header h1{font-size:16px;font-weight:600;color:#0ff}
header .status{font-size:12px;padding:2px 8px;border-radius:4px;background:#1a3a1a;color:#4f4}
header .status.off{background:#3a1a1a;color:#f44}
header .stat{font-size:11px;color:#888;margin-left:auto}
#viewport{background:#0d1117;position:relative}
#canvas3d{width:100%;height:100%;display:block}
#sidebar{background:#12121f;padding:12px;overflow-y:auto;display:flex;flex-direction:column;gap:8px}
.axis-card{background:#1a1a2e;border-radius:6px;padding:8px 10px;border-left:3px solid #0ff}
.axis-card.linear{border-color:#0af}
.axis-card.rotation{border-color:#fa0}
.axis-card.vibration{border-color:#f0a}
.axis-card .name{font-size:11px;font-weight:700;text-transform:uppercase;color:#888;display:flex;justify-content:space-between}
.axis-card .value{font-size:22px;font-weight:300;color:#fff;font-variant-numeric:tabular-nums}
.axis-card .bar{height:4px;background:#222;border-radius:2px;margin-top:4px}
.axis-card .bar-fill{height:100%;border-radius:2px;transition:width 50ms linear}
.axis-card .bar-fill.linear{background:linear-gradient(90deg,#024,#0af)}
.axis-card .bar-fill.rotation{background:linear-gradient(90deg,#420,#fa0)}
.axis-card .bar-fill.vibration{background:linear-gradient(90deg,#402,#f0a)}
.axis-card .meta{font-size:10px;color:#555;margin-top:2px;display:flex;justify-content:space-between}
#controls{background:#12121f;padding:8px 12px;display:flex;flex-direction:column;gap:4px}
#controls h3{font-size:11px;color:#666;text-transform:uppercase;letter-spacing:1px}
.ctrl-row{display:flex;gap:6px;align-items:center}
.ctrl-row label{font-size:11px;width:28px;color:#888;text-align:right}
.ctrl-row input[type=range]{flex:1;accent-color:#0af}
.ctrl-row .val{font-size:11px;width:40px;color:#aaa;font-variant-numeric:tabular-nums}
#cmd-input{background:#1a1a2e;border:1px solid #333;color:#0f0;font-family:monospace;font-size:13px;padding:6px 8px;border-radius:4px;width:100%}
#cmd-input:focus{outline:none;border-color:#0af}
#history{grid-column:1/-1;background:#0d1117;padding:6px 12px;overflow-y:auto;font-family:monospace;font-size:11px;color:#666;display:flex;flex-direction:column-reverse;gap:1px}
.hist-line{white-space:nowrap}.hist-line .t{color:#444}.hist-line .c{color:#0a8}
.moving-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#0f0;animation:pulse 0.5s infinite alternate}
@keyframes pulse{0%{opacity:.3}100%{opacity:1}}
</style>
</head>
<body>
<div id="app">
  <header>
    <h1>ORS6 Virtual Device</h1>
    <span class="status off" id="connStatus">OFFLINE</span>
    <span class="stat" id="statInfo">--</span>
  </header>
  <div id="viewport"><canvas id="canvas3d"></canvas></div>
  <div id="sidebar"></div>
  <div id="controls">
    <h3>TempestStroke Patterns <small>(ported from ayvajs)</small></h3>
    <div class="ctrl-row"><select id="patternSel" style="flex:1;background:#1a1a2e;color:#0ff;border:1px solid #333;padding:4px;border-radius:4px;font-size:11px"><option value="">-- select pattern --</option></select><input type="number" id="bpmInput" value="60" min="10" max="300" style="width:50px;background:#1a1a2e;color:#fa0;border:1px solid #333;padding:4px;border-radius:4px;text-align:center" title="BPM"><button id="stopBtn" style="background:#a00;color:#fff;border:none;padding:4px 8px;border-radius:4px;cursor:pointer;font-size:11px">STOP</button></div>
    <h3>Manual Control</h3>
    <div class="ctrl-row"><label>L0</label><input type="range" min="0" max="9999" value="5000" data-axis="L0"><span class="val">5000</span></div>
    <div class="ctrl-row"><label>L1</label><input type="range" min="0" max="9999" value="5000" data-axis="L1"><span class="val">5000</span></div>
    <div class="ctrl-row"><label>L2</label><input type="range" min="0" max="9999" value="5000" data-axis="L2"><span class="val">5000</span></div>
    <div class="ctrl-row"><label>R0</label><input type="range" min="0" max="9999" value="5000" data-axis="R0"><span class="val">5000</span></div>
    <div class="ctrl-row"><label>R1</label><input type="range" min="0" max="9999" value="5000" data-axis="R1"><span class="val">5000</span></div>
    <div class="ctrl-row"><label>R2</label><input type="range" min="0" max="9999" value="5000" data-axis="R2"><span class="val">5000</span></div>
    <input id="cmd-input" placeholder="TCode command (e.g. L09999I1000)" autocomplete="off">
  </div>
  <div id="history"></div>
</div>

<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.170.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.170.0/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ── Three.js Scene ──
const canvas = document.getElementById('canvas3d');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.toneMapping = THREE.ACESFilmicToneMapping;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0d1117);
scene.fog = new THREE.Fog(0x0d1117, 15, 35);

const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
camera.position.set(6, 5, 8);

const controls = new OrbitControls(camera, canvas);
controls.target.set(0, 2, 0);
controls.enableDamping = true;
controls.dampingFactor = 0.05;
controls.update();

// Lights
const ambient = new THREE.AmbientLight(0x404060, 0.6);
scene.add(ambient);
const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
dirLight.position.set(5, 8, 4);
dirLight.castShadow = true;
dirLight.shadow.mapSize.set(1024, 1024);
scene.add(dirLight);
const pointLight = new THREE.PointLight(0x00aaff, 0.5, 20);
pointLight.position.set(-3, 6, -2);
scene.add(pointLight);

// Ground
const groundGeo = new THREE.PlaneGeometry(20, 20);
const groundMat = new THREE.MeshStandardMaterial({ color: 0x111122, roughness: 0.9 });
const ground = new THREE.Mesh(groundGeo, groundMat);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

// Grid
const grid = new THREE.GridHelper(20, 40, 0x222244, 0x16162a);
scene.add(grid);

// ── ORS6 Mechanical Model ──
const matBase = new THREE.MeshStandardMaterial({ color: 0x2a2a3e, metalness: 0.7, roughness: 0.3 });
const matArm = new THREE.MeshStandardMaterial({ color: 0x3a3a5e, metalness: 0.6, roughness: 0.4 });
const matJoint = new THREE.MeshStandardMaterial({ color: 0x00aaff, metalness: 0.8, roughness: 0.2, emissive: 0x003355 });
const matHead = new THREE.MeshStandardMaterial({ color: 0x4a4a6e, metalness: 0.5, roughness: 0.3 });

// Base platform
const base = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 1.8, 0.4, 32), matBase);
base.position.y = 0.2; base.castShadow = true;
scene.add(base);

// Stroke column (L0 - vertical)
const strokeGroup = new THREE.Group();
strokeGroup.position.y = 0.4;
scene.add(strokeGroup);

const column = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.15, 3, 16), matArm);
column.position.y = 1.5; column.castShadow = true;
strokeGroup.add(column);

// Stroke slider (moves up/down)
const slider = new THREE.Group();
slider.position.y = 1.5;
strokeGroup.add(slider);

const sliderBody = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.3, 0.6), matJoint);
sliderBody.castShadow = true;
slider.add(sliderBody);

// Surge arm (L1 - forward/back)
const surgeGroup = new THREE.Group();
slider.add(surgeGroup);

const surgeArm = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.2, 1.5), matArm);
surgeArm.position.z = 0.75; surgeArm.castShadow = true;
surgeGroup.add(surgeArm);

// Sway pivot (L2 - left/right)
const swayGroup = new THREE.Group();
swayGroup.position.z = 1.5;
surgeGroup.add(swayGroup);

// Twist joint (R0 - rotation)
const twistGroup = new THREE.Group();
swayGroup.add(twistGroup);

const twistJoint = new THREE.Mesh(new THREE.SphereGeometry(0.2, 16, 16), matJoint);
twistJoint.castShadow = true;
twistGroup.add(twistJoint);

// Roll pivot (R1)
const rollGroup = new THREE.Group();
twistGroup.add(rollGroup);

// Pitch pivot (R2)
const pitchGroup = new THREE.Group();
rollGroup.add(pitchGroup);

// End effector (head)
const head = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.25, 0.8, 16), matHead);
head.position.y = 0.4; head.castShadow = true;
pitchGroup.add(head);

// Indicator ring on head
const ring = new THREE.Mesh(
  new THREE.TorusGeometry(0.38, 0.03, 8, 32),
  new THREE.MeshStandardMaterial({ color: 0x00ff88, emissive: 0x00ff88, emissiveIntensity: 0.5 })
);
ring.position.y = 0.7;
pitchGroup.add(ring);

// ── Axis mapping ──
function applyAxes(axes) {
  if (!axes) return;
  const norm = (v) => (v - 5000) / 5000; // -1 to 1
  const pct = (v) => v / 9999;            // 0 to 1

  // L0 Stroke: slider Y position (0=bottom, 9999=top)
  if (axes.L0) slider.position.y = 0.3 + pct(axes.L0.current) * 2.5;

  // L1 Surge: forward/back Z
  if (axes.L1) surgeGroup.position.z = norm(axes.L1.current) * 0.8;

  // L2 Sway: left/right X
  if (axes.L2) swayGroup.position.x = norm(axes.L2.current) * 0.8;

  // R0 Twist: Y rotation
  if (axes.R0) twistGroup.rotation.y = norm(axes.R0.current) * Math.PI * 0.5;

  // R1 Roll: Z rotation
  if (axes.R1) rollGroup.rotation.z = norm(axes.R1.current) * Math.PI * 0.3;

  // R2 Pitch: X rotation
  if (axes.R2) pitchGroup.rotation.x = norm(axes.R2.current) * Math.PI * 0.3;

  // Ring glow based on movement
  const moving = Object.values(axes).some(a => a.is_moving);
  ring.material.emissiveIntensity = moving ? 1.0 : 0.3;
  ring.material.color.setHex(moving ? 0x00ff44 : 0x00ff88);
}

// ── Resize ──
function onResize() {
  const vp = document.getElementById('viewport');
  const w = vp.clientWidth, h = vp.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}
window.addEventListener('resize', onResize);
setTimeout(onResize, 100);
new ResizeObserver(onResize).observe(document.getElementById('viewport'));

// ── Animation Loop ──
let lastState = null;
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  if (lastState) applyAxes(lastState.axes);
  renderer.render(scene, camera);
}
animate();

// ── WebSocket ──
const WS_URL = `ws://${location.host}/ws`;
let ws = null;
let reconnectTimer = null;

function connectWS() {
  ws = new WebSocket(WS_URL);
  ws.onopen = () => {
    document.getElementById('connStatus').textContent = 'ONLINE';
    document.getElementById('connStatus').className = 'status';
    if (reconnectTimer) { clearInterval(reconnectTimer); reconnectTimer = null; }
  };
  ws.onclose = () => {
    document.getElementById('connStatus').textContent = 'OFFLINE';
    document.getElementById('connStatus').className = 'status off';
    if (!reconnectTimer) reconnectTimer = setInterval(connectWS, 2000);
  };
  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'state') {
        lastState = msg.data;
        updateSidebar(msg.data);
        updateStat(msg.data);
      } else if (msg.type === 'history') {
        updateHistory(msg.data);
      }
    } catch(err) {}
  };
}
connectWS();

function sendCmd(cmd) {
  if (ws && ws.readyState === 1) {
    ws.send(JSON.stringify({ type: 'command', cmd }));
  }
}

// ── Sidebar ──
const sidebarEl = document.getElementById('sidebar');
const AXIS_META = {
  L0: { label: 'Stroke ↕', cls: 'linear' },
  L1: { label: 'Surge ↔', cls: 'linear' },
  L2: { label: 'Sway ⇔', cls: 'linear' },
  R0: { label: 'Twist ↻', cls: 'rotation' },
  R1: { label: 'Roll ⟳', cls: 'rotation' },
  R2: { label: 'Pitch ⤴', cls: 'rotation' },
};

function updateSidebar(state) {
  if (!state.axes) return;
  let html = '';
  for (const [axis, meta] of Object.entries(AXIS_META)) {
    const a = state.axes[axis];
    if (!a) continue;
    const moving = a.is_moving ? '<span class="moving-dot"></span>' : '';
    html += `<div class="axis-card ${meta.cls}">
      <div class="name"><span>${meta.label}</span>${moving}</div>
      <div class="value">${Math.round(a.current)}</div>
      <div class="bar"><div class="bar-fill ${meta.cls}" style="width:${a.position_pct}%"></div></div>
      <div class="meta"><span>T:${Math.round(a.target)}</span><span>V:${Math.round(a.velocity)}/s</span><span>#${a.command_count}</span></div>
    </div>`;
  }
  sidebarEl.innerHTML = html;
}

function updateStat(state) {
  const el = document.getElementById('statInfo');
  el.textContent = `Cmds: ${state.total_commands} | Ticks: ${state.tick_count} | Up: ${state.uptime_sec}s`;
}

// ── History ──
const histEl = document.getElementById('history');
function updateHistory(items) {
  let html = '';
  for (const item of items.slice(-30).reverse()) {
    const t = new Date(item.time * 1000).toLocaleTimeString();
    html += `<div class="hist-line"><span class="t">${t}</span> <span class="c">${item.cmd}</span></div>`;
  }
  histEl.innerHTML = html;
}

// ── Controls ──
document.querySelectorAll('#controls input[type=range]').forEach(sl => {
  sl.addEventListener('input', () => {
    const axis = sl.dataset.axis;
    const val = sl.value;
    sl.nextElementSibling.textContent = val;
    sendCmd(`${axis}${val.padStart(4,'0')}I200`);
  });
});

document.getElementById('cmd-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && e.target.value.trim()) {
    sendCmd(e.target.value.trim());
    e.target.value = '';
  }
});

// ── TempestStroke Pattern Controls ──
const patSel = document.getElementById('patternSel');
const bpmInput = document.getElementById('bpmInput');
document.getElementById('stopBtn').addEventListener('click', () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'pattern_stop' }));
  patSel.value = '';
});
patSel.addEventListener('change', () => {
  const name = patSel.value;
  if (name && ws && ws.readyState === 1) {
    ws.send(JSON.stringify({ type: 'pattern_play', name, bpm: parseInt(bpmInput.value) || 60 }));
  }
});
bpmInput.addEventListener('change', () => {
  const name = patSel.value;
  if (name && ws && ws.readyState === 1) {
    ws.send(JSON.stringify({ type: 'pattern_play', name, bpm: parseInt(bpmInput.value) || 60 }));
  }
});
// Request pattern list on connect
function requestPatterns() {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'get_patterns' }));
}
// Patch onmessage to handle patterns
function patchWS() {
  if (!ws) return;
  const prevOnOpen = ws.onopen;
  ws.onopen = (e) => { if(prevOnOpen) prevOnOpen(e); requestPatterns(); };
  const prevOnMsg = ws.onmessage;
  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'patterns') {
        patSel.innerHTML = '<option value="">-- select pattern --</option>';
        for (const name of msg.data) {
          const opt = document.createElement('option');
          opt.value = name; opt.textContent = name;
          patSel.appendChild(opt);
        }
        return;
      }
    } catch(err) {}
    if (prevOnMsg) prevOnMsg(e);
  };
}
patchWS();
// Re-patch on reconnect
const _origConnectWS = connectWS;
connectWS = function() { _origConnectWS(); patchWS(); };
</script>
</body>
</html>"""


class WebSocketHandler:
    """简易WebSocket处理 (无外部依赖)"""

    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.closed = False

    @staticmethod
    def handshake(request_text: str) -> bytes:
        """WebSocket握手"""
        import hashlib
        import base64
        key = ""
        for line in request_text.split("\r\n"):
            if line.lower().startswith("sec-websocket-key:"):
                key = line.split(":", 1)[1].strip()
                break
        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-5AB5DC085B11").encode()).digest()
        ).decode()
        return (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        ).encode()

    def send(self, data: str):
        """发送文本帧"""
        if self.closed:
            return
        try:
            payload = data.encode("utf-8")
            frame = bytearray()
            frame.append(0x81)  # text frame
            length = len(payload)
            if length < 126:
                frame.append(length)
            elif length < 65536:
                frame.append(126)
                frame.extend(length.to_bytes(2, "big"))
            else:
                frame.append(127)
                frame.extend(length.to_bytes(8, "big"))
            frame.extend(payload)
            self.conn.sendall(bytes(frame))
        except Exception:
            self.closed = True

    def recv(self) -> Optional[str]:
        """接收文本帧"""
        try:
            data = self.conn.recv(2)
            if not data or len(data) < 2:
                self.closed = True
                return None
            opcode = data[0] & 0x0F
            if opcode == 0x8:  # close
                self.closed = True
                return None
            masked = data[1] & 0x80
            length = data[1] & 0x7F
            if length == 126:
                length = int.from_bytes(self.conn.recv(2), "big")
            elif length == 127:
                length = int.from_bytes(self.conn.recv(8), "big")
            mask_key = self.conn.recv(4) if masked else None
            payload = bytearray()
            while len(payload) < length:
                chunk = self.conn.recv(min(4096, length - len(payload)))
                if not chunk:
                    self.closed = True
                    return None
                payload.extend(chunk)
            if mask_key:
                payload = bytearray(b ^ mask_key[i % 4] for i, b in enumerate(payload))
            return payload.decode("utf-8", errors="ignore")
        except Exception:
            self.closed = True
            return None

    def close(self):
        self.closed = True
        try:
            self.conn.close()
        except Exception:
            pass


class DashboardServer:
    """ORS6虚拟仪表盘HTTP+WebSocket服务器"""

    def __init__(self, device=None, port: int = 8085):
        from .virtual_device import VirtualORS6
        self.device = device or VirtualORS6()
        self.port = port
        self._ws_clients: list[WebSocketHandler] = []
        self._running = False
        self._lock = threading.Lock()
        self._pattern_thread: threading.Thread = None
        self._pattern_running = False

    def start(self, open_browser: bool = True):
        """启动服务器 (阻塞)"""
        import socket

        self.device.connect()
        self.device.on_state_change = self._broadcast_state

        self._running = True

        # 启动HTTP+WS服务
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("0.0.0.0", self.port))
        server_sock.listen(5)
        server_sock.settimeout(1.0)

        url = f"http://localhost:{self.port}"
        logger.info(f"ORS6 Virtual Dashboard: {url}")
        print(f"\n  ORS6 Virtual Dashboard: {url}\n")

        if open_browser:
            threading.Timer(0.5, lambda: webbrowser.open(url)).start()

        # 定期广播历史
        threading.Thread(target=self._history_broadcaster, daemon=True).start()

        try:
            while self._running:
                try:
                    conn, addr = server_sock.accept()
                    threading.Thread(
                        target=self._handle_connection,
                        args=(conn, addr),
                        daemon=True
                    ).start()
                except socket.timeout:
                    continue
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False
            server_sock.close()
            self.device.disconnect()

    def _handle_connection(self, conn, addr):
        """处理HTTP或WebSocket连接"""
        try:
            conn.settimeout(10)
            data = conn.recv(4096).decode("utf-8", errors="ignore")
            if not data:
                conn.close()
                return

            first_line = data.split("\r\n")[0]

            # WebSocket升级
            if "upgrade: websocket" in data.lower():
                handshake = WebSocketHandler.handshake(data)
                conn.sendall(handshake)
                conn.settimeout(5)  # send timeout防止阻塞
                ws = WebSocketHandler(conn, addr)
                with self._lock:
                    self._ws_clients.append(ws)
                self._ws_loop(ws)
                return

            # HTTP
            if "GET / " in first_line or "GET /index.html" in first_line:
                self._send_html(conn)
            elif "GET /api/state" in first_line:
                self._send_json(conn, self.device.get_state())
            elif "GET /api/history" in first_line:
                self._send_json(conn, self.device.get_history(100))
            elif "GET /api/patterns" in first_line:
                from .tempest_stroke import TempestStroke
                self._send_json(conn, TempestStroke.list_patterns())
            elif "GET /favicon" in first_line:
                self._send_empty(conn, 204)
            else:
                self._send_404(conn)

        except Exception as e:
            logger.debug(f"Connection error: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _ws_loop(self, ws: WebSocketHandler):
        """WebSocket消息循环"""
        ws.conn.settimeout(60)
        try:
            while not ws.closed and self._running:
                msg = ws.recv()
                if msg is None:
                    break
                try:
                    data = json.loads(msg)
                    msg_type = data.get("type")
                    if msg_type == "command":
                        cmd = data.get("cmd", "")
                        if cmd:
                            self.device.send(cmd)
                    elif msg_type == "get_patterns":
                        from .tempest_stroke import TempestStroke
                        names = TempestStroke.list_patterns()
                        ws.send(json.dumps({"type": "patterns", "data": names}))
                    elif msg_type == "pattern_play":
                        name = data.get("name", "")
                        bpm = data.get("bpm", 60)
                        self._start_pattern(name, bpm)
                    elif msg_type == "pattern_stop":
                        self._stop_pattern()
                except json.JSONDecodeError:
                    pass
        finally:
            with self._lock:
                if ws in self._ws_clients:
                    self._ws_clients.remove(ws)
            ws.close()

    def _broadcast_state(self, state: dict):
        """广播状态到所有WebSocket客户端"""
        msg = json.dumps({"type": "state", "data": state})
        with self._lock:
            dead = []
            for ws in self._ws_clients:
                if ws.closed:
                    dead.append(ws)
                    continue
                ws.send(msg)
            for ws in dead:
                self._ws_clients.remove(ws)

    def _history_broadcaster(self):
        """定期广播命令历史"""
        while self._running:
            time.sleep(1.0)
            history = self.device.get_history(50)
            if history:
                msg = json.dumps({"type": "history", "data": history})
                with self._lock:
                    for ws in self._ws_clients:
                        if not ws.closed:
                            ws.send(msg)

    def _start_pattern(self, name: str, bpm: float = 60):
        """启动TempestStroke模式播放"""
        self._stop_pattern(home=False)
        from .tempest_stroke import TempestStroke
        try:
            stroke = TempestStroke(name, bpm=bpm)
        except ValueError:
            return
        self._pattern_running = True
        def pattern_loop():
            idx = 0
            freq = 60.0
            interval_ms = int(1000 / freq)
            while self._pattern_running and self._running:
                cmd = stroke.generate_tcode(idx, frequency=freq, interval_ms=interval_ms)
                self.device.send(cmd)
                idx += 1
                time.sleep(1.0 / freq)
        self._pattern_thread = threading.Thread(target=pattern_loop, daemon=True)
        self._pattern_thread.start()
        logger.info(f"TempestStroke: {name} @ {bpm}bpm")

    def _stop_pattern(self, home: bool = True):
        """停止模式播放"""
        self._pattern_running = False
        if self._pattern_thread:
            self._pattern_thread.join(timeout=1)
            self._pattern_thread = None
        if home:
            self.device.send("D1")  # 归位

    def _send_html(self, conn):
        body = DASHBOARD_HTML.encode("utf-8")
        header = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n"
        )
        conn.sendall(header.encode() + body)

    def _send_json(self, conn, data):
        body = json.dumps(data).encode("utf-8")
        header = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"Connection: close\r\n\r\n"
        )
        conn.sendall(header.encode() + body)

    def _send_empty(self, conn, status=204):
        header = f"HTTP/1.1 {status} No Content\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        conn.sendall(header.encode())

    def _send_404(self, conn):
        body = b"Not Found"
        header = f"HTTP/1.1 404 Not Found\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n"
        conn.sendall(header.encode() + body)


def main():
    """CLI入口"""
    import argparse
    parser = argparse.ArgumentParser(description="ORS6 Virtual Dashboard")
    parser.add_argument("--port", type=int, default=8085, help="HTTP port")
    parser.add_argument("--hz", type=float, default=120, help="Simulation Hz")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")
    parser.add_argument("--demo", action="store_true", help="Run demo oscillation pattern")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname).1s] %(message)s")

    from .virtual_device import VirtualORS6, ServoConfig
    device = VirtualORS6(tick_hz=args.hz)

    if args.demo:
        # 演示模式: 自动运动
        def demo_loop():
            import time as t
            import math as m
            t.sleep(2)
            while True:
                for i in range(200):
                    phase = i / 200 * m.pi * 2
                    l0 = int(5000 + 4000 * m.sin(phase))
                    r0 = int(5000 + 3000 * m.sin(phase * 2))
                    l1 = int(5000 + 2000 * m.cos(phase * 0.7))
                    device.send(f"L0{l0:04d}I100 R0{r0:04d}I100 L1{l1:04d}I100")
                    t.sleep(0.1)

        threading.Thread(target=demo_loop, daemon=True).start()

    server = DashboardServer(device, port=args.port)
    server.start(open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
