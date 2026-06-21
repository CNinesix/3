// Host: captures the screen and streams it to any number of viewers.
// Each viewer gets its own RTCPeerConnection. The host creates the offer
// when the server reports a viewer has joined.

import { RTC_CONFIG, connectSignaling, makeLogger } from './rtc.js';

const startBtn = document.getElementById('startBtn');
const sessionIdEl = document.getElementById('sessionId');
const statusEl = document.getElementById('status');
const preview = document.getElementById('preview');
const log = makeLogger(document.getElementById('log'));

let ws;
let localStream;
const peers = new Map(); // viewerId -> RTCPeerConnection

function setStatus(text, cls = '') {
  statusEl.textContent = text;
  statusEl.className = 'status' + (cls ? ' ' + cls : '');
}

startBtn.addEventListener('click', async () => {
  try {
    localStream = await navigator.mediaDevices.getDisplayMedia({
      video: { frameRate: 30 },
      audio: false,
    });
  } catch (err) {
    log('Screen capture cancelled or denied: ' + err.message);
    return;
  }
  preview.srcObject = localStream;
  startBtn.disabled = true;
  setStatus('connecting…');

  // Ending the share from the browser UI stops everything.
  localStream.getVideoTracks()[0].addEventListener('ended', () => {
    log('Screen sharing stopped.');
    for (const pc of peers.values()) pc.close();
    peers.clear();
    if (ws) ws.close();
    setStatus('ended', 'err');
    startBtn.disabled = false;
  });

  ws = connectSignaling();
  ws.addEventListener('open', () => ws.send(JSON.stringify({ type: 'host-create' })));
  ws.addEventListener('message', onSignal);
});

async function onSignal(event) {
  const msg = JSON.parse(event.data);

  switch (msg.type) {
    case 'session-created':
      sessionIdEl.textContent = msg.sessionId;
      setStatus('waiting for viewers', 'live');
      log('Session ready. Share ID: ' + msg.sessionId);
      break;

    case 'viewer-joined':
      log('Viewer joined: ' + msg.viewerId);
      await createPeer(msg.viewerId);
      break;

    case 'signal':
      await handlePeerSignal(msg.viewerId, msg.signal);
      break;

    case 'viewer-left': {
      const pc = peers.get(msg.viewerId);
      if (pc) pc.close();
      peers.delete(msg.viewerId);
      log('Viewer left: ' + msg.viewerId);
      break;
    }
  }
}

async function createPeer(viewerId) {
  const pc = new RTCPeerConnection(RTC_CONFIG);
  peers.set(viewerId, pc);

  for (const track of localStream.getTracks()) pc.addTrack(track, localStream);

  // Receive remote input from this viewer.
  pc.ondatachannel = (e) => {
    const ch = e.channel;
    ch.onmessage = (m) => handleRemoteInput(viewerId, JSON.parse(m.data));
  };

  pc.onicecandidate = (e) => {
    if (e.candidate) {
      ws.send(JSON.stringify({ type: 'signal', viewerId, signal: { candidate: e.candidate } }));
    }
  };

  pc.onconnectionstatechange = () => {
    if (pc.connectionState === 'connected') setStatus('live · sharing', 'live');
  };

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  ws.send(JSON.stringify({ type: 'signal', viewerId, signal: { sdp: pc.localDescription } }));
}

async function handlePeerSignal(viewerId, signal) {
  const pc = peers.get(viewerId);
  if (!pc) return;
  if (signal.sdp) {
    await pc.setRemoteDescription(signal.sdp);
  } else if (signal.candidate) {
    try { await pc.addIceCandidate(signal.candidate); } catch {}
  }
}

// In the browser sandbox we can only display received input. A native host
// agent would translate these into real OS-level mouse/keyboard events.
function handleRemoteInput(viewerId, input) {
  if (input.type === 'mousemove') return; // too noisy to log every move
  log(`input from ${viewerId}: ${input.type} ${JSON.stringify(input).slice(0, 80)}`);
}
