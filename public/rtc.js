// Shared helpers for signaling + WebRTC config used by host and viewer.

export const RTC_CONFIG = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    // For connections across strict NATs/firewalls you must add a TURN relay,
    // e.g. a self-hosted coturn server:
    // { urls: 'turn:your-host:3478', username: 'user', credential: 'pass' },
  ],
};

export function connectSignaling() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return new WebSocket(`${proto}://${location.host}`);
}

export function makeLogger(el) {
  return (msg) => {
    const line = document.createElement('div');
    line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    el.appendChild(line);
    el.scrollTop = el.scrollHeight;
  };
}
