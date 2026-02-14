# Audio Center - Project Tasks (Unified)

## 1. Unified Engine (Single APK)
>
> **Goal**: One app (`AudioCenter`) that can act as Source, Receiver, or Relay.

- [x] **Project Setup**:
  - [x] Base Ktor Server (Port 8085)
  - [x] Permissions (Mic, Foreground Service)
  - [ ] Web Asset Hosting (Serve `dashboard/index.html`)

- [ ] **Module A: Source (The Ear)**
  - [x] `AudioStreamingService` (Mic Capture 16kHz)
  - [x] WebSocket Broadcaster

- [ ] **Module B: Receiver (The Monitor)**
  - [ ] **Migrate**: `PlayerService` from `android-receiver`
  - [ ] AudioTrack Logic
  - [ ] Auto-Reconnect

## 2. Web Interface (The Hub)
>
> Hosted by the App, accessible via Browser (`http://IP:8085`)

- [x] **Dashboard**:
  - [x] `index.html` Mixer UI
  - [x] Jitter Buffer Implementation
- [ ] **Integration**:
  - [ ] Copy `index.html` to App Assets
  - [ ] Ktor Static Content Routing

## 3. UI & Control

- [ ] **MainActivity**:
  - [ ] Toggle: "Start Broadcasting" (Source)
  - [ ] Toggle: "Start Listening" (Receiver - Input Target IP)
  - [ ] Status: "Web Dashboard available at http://..."
