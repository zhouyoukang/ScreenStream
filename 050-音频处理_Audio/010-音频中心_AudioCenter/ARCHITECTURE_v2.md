# Audio Center - Architecture v2.0 (Dual-Track)

Based on user requirements, the project is divided into two distinct product lines sharing a common "Universal Source".

## 1. Common Source (The "Ear")

**Project**: `AudioCenter Lite` (Android APK)

* **Role**: Runs on generic Android devices (Old Phones, Watches, IoT).
* **Function**: Captures Mic audio and serves it via WebSocket (`ws://IP:8085/stream/audio`).
* **Specs**: 16kHz Mono PCM (Low Bandwidth).
* **Management**: Controlled via ADB/Intents (`ACTION_START`/`STOP`).

---

## 2. Track A: The Web Mixer (The "Dashboard")

**Context**: LAN / Desktop / Temporary Monitoring
**Platform**: Web (HTML/JS) inside `ScreenStream` or standalone.
**Features**:

* **Multi-View**: Visual list of all discovered/configured devices.
* **Live Mixing**: Individual volume faders, mute buttons.
* **No Install**: Accessible via browser from any PC/Phone.
* [ ] **TODO**:
  * Integrate `index.html` into ScreenStream's main navigation.
  * Add "Device Discovery" (mDNS or static list management).

---

## 3. Track B: The Native Client (The "Guard")

**Context**: WAN / Mobile / Long-term Background Monitoring
**Platform**: Android Native APK (`AudioReceiver`)
**Why Native?**:
    ***Background Execution**: Crucial for pocket/screen-off listening.
    *   **Reliability**: Auto-reconnection on network switch (WiFi <-> 4G).
    *   **Management**: Centralized control center.
**Features**:

* **Device List**: Add/Remove Source IPs.
* **Background Player**: Foreground Service with Notification controls.
* **Remote Control**: Buttons to send "Start/Stop" commands to Sources via HTTP/TCP (Future).
* [ ] **TODO**:
  * Scaffold `AudioReceiver` Android Project.
  * Implement efficient Oboe/AudioTrack player.
