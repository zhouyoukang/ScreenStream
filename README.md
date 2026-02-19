# ScreenStream Enhanced

**Android screen streaming + full remote control + AI Agent brain — all in your browser.**

> A feature-rich fork of [dkrivoruchko/ScreenStream](https://github.com/dkrivoruchko/ScreenStream) with AI-powered phone control, VR headset support, full keyboard input, and reverse proxy (FRP) compatibility.

[![Android](https://img.shields.io/badge/Android-6.0%2B-green?logo=android)](https://developer.android.com)
[![Kotlin](https://img.shields.io/badge/Kotlin-Ktor-purple?logo=kotlin)](https://kotlinlang.org)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

---

## What's Different in This Fork?

| Capability | Upstream ScreenStream | This Fork |
|---|---|---|
| Screen streaming | MJPEG / WebRTC / RTSP | Same |
| Remote touch control | Basic tap/swipe | **Pixel-perfect** (aspect-ratio aware) |
| Keyboard input | None | **Full keyboard** + Chinese IME + shortcuts |
| AI Agent | None | **Natural language commands** — "open WeChat", "turn off WiFi" |
| VR / Quest | None | **Controller mapping** + joystick swiping + PiP |
| Reverse proxy (FRP) | Not supported | **Custom port routing** via URL params |
| System control | None | **Volume / lock / notifications / brightness / clipboard** |

---

## Key Features

### 🤖 AI Agent Brain

Use natural language to control your phone — no manual tapping required.

```
"打开支付宝"  →  App launches automatically
"关闭WiFi"    →  WiFi toggles off
"返回桌面"    →  Home screen
```

- **Observe → Think → Act** loop powered by AccessibilityService + View Tree analysis
- **18 action types**: tap, swipe, type, scroll, open app, navigate, toggle WiFi, and more
- **Smart dialog handling**: auto-detects permission popups and handles them
- **Compound commands**: chain multiple actions in one sentence
- **Zero extra cost**: uses the IDE's AI (Cascade) as the LLM brain — no API keys needed

### ⌨️ Full Keyboard & Mouse Control

- Type directly from PC → phone (including **Chinese IME**)
- **Shortcuts**: `Ctrl+V` paste, `Ctrl+C` copy, `Escape` = Back, arrow keys, Tab, Delete
- **Mouse**: pixel-perfect click, right-click = Back, scroll wheel with natural direction
- **Horizontal scroll**: right-click + scroll wheel

### 🥽 VR / Meta Quest Ready

- **B / Y buttons** → Back action (no context menu conflicts)
- **Joystick** → 4-directional swiping (45° sector logic, no diagonal cross-talk)
- **PiP mode** → Picture-in-Picture for MJPEG and H.264/H.265 streams
- Soft keyboard suppression for VR browsers

### 🌐 Network & FRP Support

- Server binds to `0.0.0.0` — works with `localhost`, LAN, USB tethering, and FRP
- **Custom input port**: `http://<ip>:8080/?input_port=9000`
- Full IPv4/IPv6 support, enhanced `rndis` (USB network) detection

### 📱 System-Level Control (30+ APIs)

| Category | Actions |
|---|---|
| **Navigation** | Home, Back, Recents, Notifications, Quick Settings |
| **Media** | Volume up/down/mute |
| **Power** | Wake, Lock screen, Brightness |
| **Input** | Tap, Long press, Double tap, Swipe, Pinch, Scroll |
| **Apps** | Open by name, Device info, Clipboard sync |
| **AI** | View tree, Semantic click, Smart close dialog, Find & navigate |

---

## Quick Start

### 1. Install & Run

Install the APK on your Android device (Android 6.0+), grant the required permissions (Screen Capture + Accessibility Service), and start streaming.

### 2. Connect from Browser

```
http://<phone-ip>:8080/
```

| Scenario | URL |
|---|---|
| Same WiFi | `http://192.168.1.x:8080/` |
| USB tethering | `http://192.168.42.129:8080/` |
| FRP / reverse proxy | `http://your-domain:port/?input_port=9000` |
| VR mode | `http://<ip>:8080/?vr=1` |
| Debug panel | `http://<ip>:8080/?debug=1` |

### 3. Control

- **Touch**: Click/drag on the stream image
- **Keyboard**: Just start typing (click the stream area first)
- **AI commands**: Open the command bar and type natural language instructions
- **VR**: Use Quest controllers — joystick to swipe, B/Y to go back

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  Browser (PC / VR / Mobile)                 │
│  ┌───────────┬──────────┬─────────────────┐ │
│  │ Stream    │ Touch /  │ AI Command Bar  │ │
│  │ Viewer    │ Keyboard │ (NL → Action)   │ │
│  └─────┬─────┴────┬─────┴───────┬─────────┘ │
└────────┼──────────┼─────────────┼───────────┘
         │ MJPEG    │ HTTP/WS     │ HTTP POST
         ▼          ▼             ▼
┌─────────────────────────────────────────────┐
│  Android Device                              │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐ │
│  │ MJPEG    │  │ Input      │  │ AI Brain │ │
│  │ Server   │  │ Service    │  │ (Agent)  │ │
│  │ :8080    │  │ :8084      │  │ :8086    │ │
│  └──────────┘  └────────────┘  └──────────┘ │
│       │        AccessibilityService          │
│       │        MediaProjection               │
└───────┼──────────────────────────────────────┘
        ▼
   Screen Capture → JPEG frames → HTTP stream
```

---

## Stream Modes

| Mode | Transport | Audio | Internet | Security |
|---|---|---|---|---|
| **Local (MJPEG)** | HTTP MJPEG | No | Not required | Optional PIN |
| **Global (WebRTC)** | WebRTC | Yes | Required | E2E encryption + password |
| **RTSP** | RTSP (H.265/H.264/AV1) | Yes | Depends | Basic Auth + TLS |

**Recommended**: Use **MJPEG (Local mode)** for best stability and lowest latency on LAN/USB.

---

## URL Parameters

| Parameter | Description | Example |
|---|---|---|
| `input_port` | Custom input control port (for FRP) | `?input_port=9000` |
| `debug` | Show debug panel | `?debug=1` |
| `vr` | VR fullscreen mode | `?vr=1` or `?vr=fill` |
| `kb` | Enable keyboard focus on mobile | `?kb=1` |
| `vr_kb` | Allow keyboard in VR mode | `?vr_kb=1` |

---

## Contributing

Issues and PRs welcome. This fork focuses on **remote control**, **AI automation**, and **VR** use cases.

For translation contributions to the upstream project, see [dkrivoruchko/ScreenStream](https://github.com/dkrivoruchko/ScreenStream).

## Credits

- **Upstream**: [Dmytro Kryvoruchko](https://github.com/dkrivoruchko) — original ScreenStream
- **Fork maintainer**: [zhouyoukang](https://github.com/zhouyoukang) — remote control, AI Agent, VR enhancements

## License

[MIT License](LICENSE) — Copyright (c) 2016 Dmytro Kryvoruchko
