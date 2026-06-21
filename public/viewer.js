// Viewer: joins a session, receives the remote screen, and forwards
// mouse/keyboard input to the host over a WebRTC data channel.

import { RTC_CONFIG, connectSignaling, makeLogger } from './rtc.js';

const sessionInput = document.getElementById('sessionInput');
const joinBtn = document.getElementById('joinBtn');
const controlToggle = document.getElementById('controlToggle');
const statusEl = document.getElementById('status');
const remote = document.getElementById('remote');
const log = makeLogger(document.getElementById('log'));

let ws;
let pc;
let inputChannel;

function setStatus(text, cls = '') {
  statusEl.textContent = text;
  statusEl.className = 'status' + (cls ? ' ' + cls : '');
}

joinBtn.addEventListener('click', () => {
  const sessionId = sessionInput.value.trim();
  if (!/^\d{9}$/.test(sessionId)) {
    setStatus('enter a 9-digit ID', 'err');
    return;
  }
  joinBtn.disabled = true;
  setStatus('connecting…');

  ws = connectSignaling();
  ws.addEventListener('open', () =>
    ws.send(JSON.stringify({ type: 'viewer-join', sessionId })));
  ws.addEventListener('message', onSignal);
});

async function onSignal(event) {
  const msg = JSON.parse(event.data);

  switch (msg.type) {
    case 'joined':
      log('Joined session ' + msg.sessionId + '. Waiting for stream…');
      setupPeer();
      break;

    case 'signal':
      await handlePeerSignal(msg.signal);
      break;

    case 'error':
      setStatus(msg.message, 'err');
      joinBtn.disabled = false;
      break;

    case 'host-left':
      setStatus('host disconnected', 'err');
      if (pc) pc.close();
      break;
  }
}

function setupPeer() {
  pc = new RTCPeerConnection(RTC_CONFIG);

  // Data channel to send input to the host.
  inputChannel = pc.createDataChannel('input');
  inputChannel.onopen = () => {
    log('Input channel open.');
    attachInputForwarding();
  };

  pc.ontrack = (e) => {
    remote.srcObject = e.streams[0];
    setStatus('live', 'live');
    log('Remote stream connected.');
  };

  pc.onicecandidate = (e) => {
    if (e.candidate) {
      ws.send(JSON.stringify({ type: 'signal', signal: { candidate: e.candidate } }));
    }
  };
}

async function handlePeerSignal(signal) {
  if (signal.sdp) {
    await pc.setRemoteDescription(signal.sdp);
    if (signal.sdp.type === 'offer') {
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      ws.send(JSON.stringify({ type: 'signal', signal: { sdp: pc.localDescription } }));
    }
  } else if (signal.candidate) {
    try { await pc.addIceCandidate(signal.candidate); } catch {}
  }
}

// Translate viewer-side pointer/keyboard events into normalized coordinates
// (0..1) and ship them to the host. Normalizing means the host can map them
// onto its own resolution regardless of the viewer's video size.
function attachInputForwarding() {
  function rel(e) {
    const r = remote.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
      y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)),
    };
  }

  function send(payload) {
    if (controlToggle.checked && inputChannel?.readyState === 'open') {
      inputChannel.send(JSON.stringify(payload));
    }
  }

  remote.addEventListener('mousemove', (e) => send({ type: 'mousemove', ...rel(e) }));
  remote.addEventListener('mousedown', (e) => send({ type: 'mousedown', button: e.button, ...rel(e) }));
  remote.addEventListener('mouseup', (e) => send({ type: 'mouseup', button: e.button, ...rel(e) }));
  remote.addEventListener('wheel', (e) => send({ type: 'wheel', dx: e.deltaX, dy: e.deltaY }), { passive: true });
  remote.addEventListener('contextmenu', (e) => e.preventDefault());

  remote.addEventListener('keydown', (e) => {
    e.preventDefault();
    send({ type: 'keydown', key: e.key, code: e.code });
  });
  remote.addEventListener('keyup', (e) => {
    e.preventDefault();
    send({ type: 'keyup', key: e.key, code: e.code });
  });
}
