# WebView Remote

A browser-based remote-desktop **MVP** built over WebRTC. It demonstrates the
core mechanics behind low-latency remote-play tools like **Parsec** — session
IDs, live screen streaming, gamepad/keyboard/mouse passthrough, and per-session
quality controls — without any native install.

> This is a learning/starter scaffold, **not** a Parsec clone. See
> [Scope & honest limits](#scope--honest-limits) below.

## What works today

- **Session IDs** — the host generates a 9-digit ID; viewers connect with it.
- **Live screen sharing** — the host's screen is captured with
  `getDisplayMedia` and streamed peer-to-peer over WebRTC.
- **Multiple viewers** — each viewer gets its own peer connection.
- **Input forwarding** — viewers send mouse/keyboard **and gamepad** events to
  the host over a data channel (normalized coordinates; gamepad deltas only).
- **Quality controls** — the host caps **max FPS (30/60/120)** and **bitrate**
  per session via `RTCRtpSender` encodings, applied live to all viewers.
- **Live latency stats** — the viewer shows real-time **RTT, FPS, bitrate,
  jitter, and resolution** from `getStats()`.
- **Signaling server** — relays SDP/ICE only; never sees pixels or input.

## Run it

```bash
npm install
npm start
# open http://localhost:3000
```

1. Open **Share this screen**, click *Start sharing*, pick a screen/tab — note
   the Session ID.
2. In another browser/device, open **Connect to a screen**, enter the ID.
3. You'll see the host's screen live. Mouse/keyboard events you make over the
   video are sent to the host and logged there.

Works on `localhost` over HTTP. For LAN/Internet you need **HTTPS** (browsers
require a secure context for screen capture) and a **TURN** server for NAT
traversal.

## Architecture

```
Host browser  ──WebRTC media──▶  Viewer browser
     │            (P2P)               │
     └──── signaling (WS) ────────────┘
                  │
            server.js (relay)
```

- `server.js` — Express static host + WebSocket signaling relay.
- `public/host.js` — screen capture, one RTCPeerConnection per viewer.
- `public/viewer.js` — receives stream, forwards input over a data channel.

## Scope & honest limits

This MVP covers the *transport, input model, and UX* of remote play. Reaching
real **Parsec** parity requires substantially more:

- **OS-level input injection** — browsers are sandboxed and cannot move the
  real cursor, type, or emulate a controller in other apps. The host currently
  *logs* received input. A native agent is needed: e.g. `nut.js` (Electron/
  Tauri) for keyboard/mouse and **ViGEm** for virtual gamepads on Windows.
- **Hardware encode for true low latency** — Parsec's edge is a
  hardware-accelerated capture→encode pipeline (NVENC/AMF/QuickSync) plus a
  UDP transport tuned over years. Browser WebRTC gets *close* but not there.
- **Reliable connectivity** — self-hosted/global TURN relays for any-firewall
  connections.
- **Security** — end-to-end encryption posture, code signing, anti-abuse,
  permission prompts, audit logging.
- **Extras** — multi-monitor, HDR, audio passthrough, host-side cursor capture.

For a production-grade open-source path, look at **Sunshine** (host) +
**Moonlight** (client), which already implement hardware encode and low-latency
gamepad streaming.

## License

MIT
