// Viewer: joins a session, receives the remote screen, and forwards
// mouse/keyboard input to the host over a WebRTC data channel.

import { RTC_CONFIG, connectSignaling, makeLogger } from './rtc.js';

const sessionInput = document.getElementById('sessionInput');
const joinBtn = document.getElementById('joinBtn');
const controlToggle = document.getElementById('controlToggle');
const statusEl = document.getElementById('status');
const gamepadStatusEl = document.getElementById('gamepadStatus');
const remote = document.getElementById('remote');
const statsEl = document.getElementById('stats');
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
    statsEl.classList.remove('hidden');
    log('Remote stream connected.');
    startStats();
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

  startGamepadLoop(send);
}

// --- Gamepad passthrough (Parsec's signature feature) ----------------------
// Poll connected controllers each animation frame and forward button/axis
// changes to the host. We diff against the previous snapshot so we only send
// deltas, keeping the data channel quiet when nothing moves.
function startGamepadLoop(send) {
  const last = new Map(); // index -> { buttons:[], axes:[] }
  const DEADZONE = 0.08;

  window.addEventListener('gamepadconnected', (e) => {
    gamepadStatusEl.textContent = 'gamepad: ' + e.gamepad.id.slice(0, 24);
    gamepadStatusEl.className = 'status live';
    log('Gamepad connected: ' + e.gamepad.id);
  });
  window.addEventListener('gamepaddisconnected', () => {
    gamepadStatusEl.textContent = 'no gamepad';
    gamepadStatusEl.className = 'status';
  });

  function poll() {
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    for (const pad of pads) {
      if (!pad) continue;
      const prev = last.get(pad.index) || { buttons: [], axes: [] };

      pad.buttons.forEach((btn, i) => {
        const pressed = btn.pressed;
        if (pressed !== !!prev.buttons[i]) {
          send({ type: 'gamepad-button', pad: pad.index, button: i, pressed, value: btn.value });
        }
      });

      pad.axes.forEach((axis, i) => {
        const v = Math.abs(axis) < DEADZONE ? 0 : axis;
        const prevV = prev.axes[i] ?? 0;
        if (Math.abs(v - prevV) > 0.02) {
          send({ type: 'gamepad-axis', pad: pad.index, axis: i, value: +v.toFixed(3) });
        }
      });

      last.set(pad.index, {
        buttons: pad.buttons.map((b) => b.pressed),
        axes: pad.axes.map((a) => (Math.abs(a) < DEADZONE ? 0 : a)),
      });
    }
    requestAnimationFrame(poll);
  }
  requestAnimationFrame(poll);
}

// --- Live connection stats (latency / fps / bitrate) -----------------------
function startStats() {
  let lastBytes = 0;
  let lastTs = 0;
  const $rtt = document.getElementById('statRtt');
  const $fps = document.getElementById('statFps');
  const $bitrate = document.getElementById('statBitrate');
  const $jitter = document.getElementById('statJitter');
  const $res = document.getElementById('statRes');

  setInterval(async () => {
    if (!pc || pc.connectionState !== 'connected') return;
    const stats = await pc.getStats();
    let inbound, pair;
    stats.forEach((r) => {
      if (r.type === 'inbound-rtp' && r.kind === 'video') inbound = r;
      if (r.type === 'candidate-pair' && r.nominated) pair = r;
    });

    if (pair?.currentRoundTripTime != null) {
      $rtt.textContent = Math.round(pair.currentRoundTripTime * 1000);
    }
    if (inbound) {
      if (inbound.framesPerSecond != null) $fps.textContent = Math.round(inbound.framesPerSecond);
      if (inbound.jitter != null) $jitter.textContent = Math.round(inbound.jitter * 1000);
      if (inbound.frameWidth) $res.textContent = `${inbound.frameWidth}×${inbound.frameHeight}`;

      const now = inbound.timestamp;
      const bytes = inbound.bytesReceived || 0;
      if (lastTs) {
        const mbps = ((bytes - lastBytes) * 8) / ((now - lastTs) / 1000) / 1e6;
        $bitrate.textContent = mbps.toFixed(1);
      }
      lastBytes = bytes;
      lastTs = now;
    }
  }, 1000);
}
