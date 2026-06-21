# WebView Remote

A browser-based remote-desktop **MVP** built over WebRTC. It demonstrates the
core mechanics behind tools like TeamViewer — session IDs, live screen
streaming, and remote input forwarding — without any native install.

> This is a learning/starter scaffold, **not** a TeamViewer clone. See
> [Scope & honest limits](#scope--honest-limits) below.

## What works today

- **Session IDs** — the host generates a 9-digit ID; viewers connect with it.
- **Live screen sharing** — the host's screen is captured with
  `getDisplayMedia` and streamed peer-to-peer over WebRTC.
- **Multiple viewers** — each viewer gets its own peer connection.
- **Remote input forwarding** — viewers send mouse/keyboard events to the host
  over a data channel (normalized 0..1 coordinates).
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

This MVP covers the *transport and UX* of remote desktop. Reaching real
TeamViewer parity requires substantially more:

- **OS-level input injection** — browsers are sandboxed and cannot move the
  real cursor or type into other apps. The host currently *logs* received
  input. A native agent (Electron/Tauri + e.g. `nut.js`, or a Rust/C++ agent)
  is needed to inject events into the operating system.
- **Unattended access** — installed background service, device list, auth.
- **Reliable connectivity** — self-hosted/global TURN relays for any-firewall
  connections.
- **Security** — end-to-end encryption posture, code signing, anti-abuse,
  permission prompts, audit logging.
- **Extras** — file transfer, clipboard sync, multi-monitor, session
  recording, chat, mobile clients.

See the roadmap discussion in the PR/branch for how these phases stack up.

## License

MIT
