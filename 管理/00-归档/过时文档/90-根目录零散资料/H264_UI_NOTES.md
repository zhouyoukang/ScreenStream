
## H264 UI Debug Notes (Local Web UI)

This repository includes a customized local web UI (`mjpeg/src/main/assets/index.html`).

### What works (stable)

- MJPEG mode: stable and recommended for normal use.

### What was tried for H.264/H.265 “small window” (not solved)

- CSS 100% + `object-fit: contain` + absolute positioning for `<video>`.
- JS `applyVideoFillFix()` that forces `<video>` to fill `#streamDiv`.
- Extra attributes to suppress native overlays (PiP/remote playback).

Result: H.264/H.265 still renders as a small viewport on Android browsers/WebView.

### Experiments reverted due to side effects

- `transform: scale(...)` loop (v24): intended to force scaling; caused stutter/lag.
- Canvas mirror render (v25): decode via `<video>`, display via `<canvas>`; caused stutter/lag and did not resolve small window.

### Next steps (future)

- Investigate Android WebView/Chromium video rendering constraints with MSE/jMuxer.
- Consider WebCodecs (if available) or server-side scaling/packaging changes.
