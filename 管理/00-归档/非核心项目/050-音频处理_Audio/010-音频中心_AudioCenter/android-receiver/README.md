# AudioCenter - Receiver (Native Client)

This module is the **Native Android Receiver** designed for robust, long-term background audio monitoring over public networks (`ws://<IP>:8085`).

## Features

* **Background Playback**: Continues playing even when the screen is off or app is minimized (via `ForegroundService`).
* **Low Latency**: Uses Android `AudioTrack` API for direct PCM streaming (16kHz Mono).
* **Resilient**: Auto-reconnect logic via `OkHttp` WebSocket.
* **Notification Controls**: Quickly stop the service from the notification shade.

## Quick Start

1. **Build APK**:
    Open this folder (`AudioCenter/android-receiver`) in Android Studio and build `debug` variant.

2. **Install**:
    Install on your destination phone (the one you listen with).

3. **Usage**:
    * Open App.
    * Enter the IP of your Source Device (e.g., `192.168.1.5`).
    * Click **"Connect & Listen"**.
    * *Result*: You should hear audio immediately. You can now lock the screen.

## Technical Details

* **Protocol**: WebSocket (Binary Frame -> 16-bit PCM Mono 16kHz).
* **Buffer**: Dynamic buffering (~150ms) to handle network jitter.
* **Permissions**: `INTERNET`, `FOREGROUND_SERVICE` (Media Playback).

## Prerequisites

* Ensure the **Source Device** (AudioCenter Lite) is running and on the same network (or reachable via FRP).
