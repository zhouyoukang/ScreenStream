# Audio Center Lite

This is the lightweight components of the "Universal Audio Streaming" system.

## Components

### 1. Android Client (Lite)

Located in `android-client/`.

* **Min SDK**: API 21 (Android 5.0)
* **Function**: Streams Microphone audio via WebSocket over LAN.
* **Port**: `8085` (HTTP/WebSocket)
* **Endpoint**: `ws://<DEVICE_IP>:8085/stream/audio`
* **Permissions**: `RECORD_AUDIO`, `FOREGROUND_SERVICE`
* **Control**:
  * **Manual**: Open App -> Click "Start Audio Stream"
  * **Automation**:
    * Start: `am broadcast -a com.github.audiocenter.ACTION_START`
    * Stop: `am broadcast -a com.github.audiocenter.ACTION_STOP`
    * *Note: First run requires manual permission grant.*

### 2. Web Dashboard

Located in `dashboard/`.

* **File**: `index.html`
* **Usage**: Open in any modern browser (Chrome/Edge/Firefox).
* **Features**:
  * Connect to multiple devices IP:Port.
  * Mix audio streams.
  * Volume control.

## Setup Guide

1. **Build APK**: Open `android-client` in Android Studio and build `debug` APK.
2. **Install**: Install on Phone/Watch/IoT device.
3. **Run**: Open app, grant Mic permission.
4. **Listen**: Open `dashboard/index.html` on PC/Phone, enter Device IP and Port (8085), click Connect.
