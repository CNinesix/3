// Close the mobile nav when a link is tapped.
document.querySelectorAll('.sidebar a').forEach(function (a) {
  a.addEventListener('click', function () {
    document.body.classList.remove('nav-open');
  });
});

// Lightweight chart renderer (no external dependency) for bar charts.
// Usage: data-bar-chart='[{"label":"x","value":1}]'
function renderBarCharts() {
  document.querySelectorAll('canvas[data-bar-chart]').forEach(function (canvas) {
    let data;
    try { data = JSON.parse(canvas.getAttribute('data-bar-chart')); } catch (e) { return; }
    if (!data.length) {
      const ctx0 = canvas.getContext('2d');
      ctx0.fillStyle = '#6b7689';
      ctx0.font = '14px sans-serif';
      ctx0.fillText('No data yet', 10, 24);
      return;
    }
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement.getBoundingClientRect();
    const W = rect.width, H = canvas.parentElement.clientHeight || 260;
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    const pad = {l: 10, r: 10, t: 16, b: 56};
    const max = Math.max.apply(null, data.map(d => d.value)) || 1;
    const n = data.length;
    const bw = (W - pad.l - pad.r) / n * 0.62;
    const gap = (W - pad.l - pad.r) / n;
    const colors = ['#2f80ed','#27ae60','#f2994a','#6b39c4','#c2185b','#eb5757','#11999e'];
    data.forEach(function (d, i) {
      const x = pad.l + i * gap + (gap - bw) / 2;
      const h = (H - pad.t - pad.b) * (d.value / max);
      const y = H - pad.b - h;
      ctx.fillStyle = colors[i % colors.length];
      roundRect(ctx, x, y, bw, h, 6); ctx.fill();
      ctx.fillStyle = '#1a2030'; ctx.font = '600 11px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText(shortNum(d.value), x + bw / 2, y - 6);
      ctx.fillStyle = '#6b7689'; ctx.font = '11px sans-serif';
      wrapLabel(ctx, d.label, x + bw / 2, H - pad.b + 16);
    });
  });
}
function roundRect(ctx, x, y, w, h, r) {
  if (h < r) r = h;
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, 0);
  ctx.arcTo(x, y + h, x, y, 0);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
function shortNum(v) {
  if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
  if (v >= 1e3) return (v / 1e3).toFixed(0) + 'k';
  return '' + Math.round(v);
}
function wrapLabel(ctx, text, x, y) {
  const words = String(text).split(' ');
  let line = '', lines = [];
  words.forEach(function (w) {
    if ((line + ' ' + w).length > 12) { lines.push(line); line = w; }
    else { line = line ? line + ' ' + w : w; }
  });
  if (line) lines.push(line);
  lines.slice(0, 2).forEach(function (l, i) { ctx.fillText(l, x, y + i * 12); });
}
window.addEventListener('load', renderBarCharts);
window.addEventListener('resize', function () {
  clearTimeout(window.__chartT);
  window.__chartT = setTimeout(renderBarCharts, 200);
});
