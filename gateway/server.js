'use strict';

/**
 * PDF Suite gateway.
 *
 *  - Serves a branded login page and dashboard.
 *  - Protects everything with a session cookie.
 *  - Reverse-proxies all authenticated traffic to Stirling-PDF.
 *
 * The login page deliberately *displays* a "minimum 8 characters" hint, but
 * the real credentials are whatever GATEWAY_USER / GATEWAY_PASS are set to
 * (defaults: pdf / 1). There is intentionally no length validation so the
 * short password still works — the hint is decoration only.
 */

const path = require('path');
const express = require('express');
const session = require('express-session');
const { createProxyMiddleware } = require('http-proxy-middleware');

const PORT = parseInt(process.env.PORT || '3000', 10);
const STIRLING_URL = process.env.STIRLING_URL || 'http://stirling:8080';
const USER = process.env.GATEWAY_USER || 'pdf';
const PASS = process.env.GATEWAY_PASS || '1';
const SECRET = process.env.SESSION_SECRET || 'please-change-this-secret';
const SITE_TITLE = process.env.SITE_TITLE || 'PDF Studio';

const app = express();
app.disable('x-powered-by');
app.set('trust proxy', 1);

app.use(
  session({
    name: 'pdfsuite.sid',
    secret: SECRET,
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      sameSite: 'lax',
      maxAge: 1000 * 60 * 60 * 12, // 12h
    },
  })
);

// ---------------------------------------------------------------------------
// Public routes (no auth required)
// ---------------------------------------------------------------------------

app.get('/login', (req, res) => {
  if (req.session && req.session.authed) return res.redirect('/dashboard');
  res.sendFile(path.join(__dirname, 'public', 'login.html'));
});

// Login form posts here. urlencoded only on this route.
app.post('/_auth/login', express.urlencoded({ extended: false }), (req, res) => {
  const u = (req.body.username || '').trim();
  const p = req.body.password || '';
  if (u === USER && p === PASS) {
    req.session.authed = true;
    req.session.user = u;
    return res.redirect('/dashboard');
  }
  // Generic message — does not reveal which field was wrong.
  return res.redirect('/login?error=1');
});

app.get('/_auth/logout', (req, res) => {
  req.session.destroy(() => res.redirect('/login'));
});

// Lightweight health endpoint for Proxmox / monitoring (public, no secrets).
app.get('/_auth/health', (req, res) => res.json({ ok: true }));

// ---------------------------------------------------------------------------
// Auth gate — everything below requires a valid session.
// ---------------------------------------------------------------------------

app.use((req, res, next) => {
  if (req.session && req.session.authed) return next();
  // For browser navigations redirect; for XHR/asset calls send 401 so the
  // browser doesn't render the login HTML inside the app frame.
  const wantsHtml = (req.headers.accept || '').includes('text/html');
  if (wantsHtml) return res.redirect('/login');
  return res.status(401).send('Unauthorized');
});

// Branded dashboard.
app.get('/dashboard', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'dashboard.html'));
});

// Brand/static assets used by the dashboard (served after auth).
app.use('/_brand', express.static(path.join(__dirname, 'public', 'brand')));

// ---------------------------------------------------------------------------
// Reverse proxy into Stirling-PDF for everything else.
// ---------------------------------------------------------------------------

app.use(
  '/',
  createProxyMiddleware({
    target: STIRLING_URL,
    changeOrigin: true,
    ws: true,
    xfwd: true,
    proxyTimeout: 120000,
    timeout: 120000,
  })
);

app.listen(PORT, () => {
  console.log(`[pdfsuite] gateway listening on :${PORT}`);
  console.log(`[pdfsuite] proxying authenticated traffic to ${STIRLING_URL}`);
  console.log(`[pdfsuite] login user="${USER}" (title: ${SITE_TITLE})`);
});
