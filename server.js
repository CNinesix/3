// Signaling server for the WebView Remote MVP.
//
// Responsibilities:
//   - Serve the static host/viewer web clients.
//   - Relay WebRTC signaling (SDP offers/answers + ICE candidates) between a
//     host (the machine sharing its screen) and viewers, keyed by a short
//     numeric session ID (the "TeamViewer ID" equivalent).
//
// The server never sees screen pixels or input events: once WebRTC negotiates,
// media and the input data channel flow peer-to-peer.

import express from 'express';
import { WebSocketServer } from 'ws';
import { createServer } from 'http';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PORT = process.env.PORT || 3000;

const app = express();
app.use(express.static(join(__dirname, 'public')));

const server = createServer(app);
const wss = new WebSocketServer({ server });

// sessionId -> { host: ws|null, viewers: Set<ws> }
const sessions = new Map();

function makeSessionId() {
  let id;
  do {
    id = String(Math.floor(100000000 + Math.random() * 900000000)); // 9 digits
  } while (sessions.has(id));
  return id;
}

function send(ws, msg) {
  if (ws && ws.readyState === ws.OPEN) ws.send(JSON.stringify(msg));
}

wss.on('connection', (ws) => {
  ws.role = null;
  ws.sessionId = null;

  ws.on('message', (raw) => {
    let msg;
    try {
      msg = JSON.parse(raw.toString());
    } catch {
      return;
    }

    switch (msg.type) {
      // Host opens a new session and gets back an ID to share.
      case 'host-create': {
        const id = makeSessionId();
        sessions.set(id, { host: ws, viewers: new Set() });
        ws.role = 'host';
        ws.sessionId = id;
        send(ws, { type: 'session-created', sessionId: id });
        break;
      }

      // Viewer asks to join an existing session.
      case 'viewer-join': {
        const session = sessions.get(msg.sessionId);
        if (!session || !session.host) {
          send(ws, { type: 'error', message: 'Session not found' });
          return;
        }
        ws.role = 'viewer';
        ws.sessionId = msg.sessionId;
        session.viewers.add(ws);
        // Tell the host a viewer arrived so it can create an offer.
        const viewerId = Math.random().toString(36).slice(2, 10);
        ws.viewerId = viewerId;
        send(session.host, { type: 'viewer-joined', viewerId });
        send(ws, { type: 'joined', sessionId: msg.sessionId });
        break;
      }

      // WebRTC signaling relay (offer / answer / ice).
      // Host -> specific viewer, or viewer -> host.
      case 'signal': {
        const session = sessions.get(ws.sessionId);
        if (!session) return;
        if (ws.role === 'host') {
          const target = [...session.viewers].find((v) => v.viewerId === msg.viewerId);
          send(target, { type: 'signal', signal: msg.signal, viewerId: msg.viewerId });
        } else {
          send(session.host, { type: 'signal', signal: msg.signal, viewerId: ws.viewerId });
        }
        break;
      }

      default:
        break;
    }
  });

  ws.on('close', () => {
    const session = sessions.get(ws.sessionId);
    if (!session) return;
    if (ws.role === 'host') {
      // Host left: tear down session and notify viewers.
      for (const v of session.viewers) send(v, { type: 'host-left' });
      sessions.delete(ws.sessionId);
    } else if (ws.role === 'viewer') {
      session.viewers.delete(ws);
      send(session.host, { type: 'viewer-left', viewerId: ws.viewerId });
    }
  });
});

server.listen(PORT, () => {
  console.log(`WebView Remote signaling server on http://localhost:${PORT}`);
});
