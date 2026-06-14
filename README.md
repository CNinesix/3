# PDF Studio — self-hosted PDF editing & security suite for Proxmox

A complete, web-based PDF toolkit you run on your own Proxmox box. It bundles:

- **A branded login page + dashboard** (the gateway) — a clean entry point with
  a sign-in screen and a categorized tool dashboard.
- **[Stirling-PDF](https://github.com/Stirling-Tools/Stirling-PDF)** — the engine:
  50+ tools for editing, organizing, converting and **securing** PDFs, all
  running locally so your files never leave the server.

Everything runs as Docker containers, orchestrated with Docker Compose.

```
Browser ──HTTPS──> Caddy (pdf.snmk.xyz, :80/:443)
                     └─> gateway (login + dashboard) ──> Stirling-PDF (private)
```

**Caddy** is the only thing published; it terminates HTTPS for **pdf.snmk.xyz**
with an automatic Let's Encrypt certificate. The gateway and Stirling-PDF stay on
the internal Docker network — every request enters via HTTPS and must pass the
login first.

---

## What you get

**Edit & organize:** merge, split, organize/reorder pages, rotate, remove pages,
compress, page numbers, stamps.

**Convert:** image ↔ PDF, Office (Word/Excel/PowerPoint) → PDF, OCR (make scans
searchable), PDF → image.

**Security & protection:** password/encrypt, decrypt, change permissions
(printing/copying/editing), watermark, **sanitize** (strip scripts, metadata and
hidden data), **redact** sensitive content, digital/drawn **signatures**, inspect
metadata & security details.

The dashboard links to the most-used tools; **"Open full toolbox"** opens the
complete Stirling-PDF interface with every feature.

---

## Login

| Field    | Value |
|----------|-------|
| Username | `pdf` |
| Password | `1`   |

> The login screen displays **"Minimum 8 characters required."** This hint is a
> **decoy** — no length is actually enforced, so the short password works. Change
> the real credentials any time in `.env` (`GATEWAY_USER` / `GATEWAY_PASS`).

---

## Domain & HTTPS (pdf.snmk.xyz)

The stack serves **https://pdf.snmk.xyz** out of the box via Caddy. To make it
work:

1. **DNS** — create an `A` record for `pdf.snmk.xyz` pointing at the public IP of
   the host running this stack (add an `AAAA` record too if you have IPv6).
2. **Ports** — make sure inbound **TCP 80 and 443** reach this host. If the
   Proxmox box is behind a home router, port-forward 80 and 443 to the
   container/VM's LAN IP. Port 80 is required for the Let's Encrypt challenge.
3. Start the stack (below). Caddy automatically requests and renews the TLS
   certificate; the first request may take a few seconds while the cert is
   issued.

Change the domain or ACME email in `.env` (`DOMAIN`, `ACME_EMAIL`).

> **Internal-only / no public ports?** Let's Encrypt's HTTP challenge needs port
> 80 reachable. If you can't expose it, either use Caddy's DNS-01 challenge
> (requires a Caddy build with your DNS provider's plugin) or replace the
> `{$DOMAIN}` block in `caddy/Caddyfile` with `tls internal` for a self-signed
> cert. Ask and I can wire either up.

## Deploy on Proxmox

### Option A — one shot from the Proxmox host (creates an LXC for you)

Run on the **Proxmox host** as root:

```bash
# get the project onto the host first (git clone or scp), then:
REPO_URL="https://github.com/cninesix/3.git" bash deploy/proxmox-create-lxc.sh
```

This creates a Debian 12 LXC (nesting enabled), installs Docker, clones the repo
and starts the stack. Tweak `CTID`, `RAM_MB`, `STORAGE`, etc. at the top of the
script or via environment variables. When it finishes it prints the URL.

### Option B — inside an existing LXC / VM

Create a Debian/Ubuntu LXC (enable **nesting** in *Options → Features* so Docker
works), or use a VM. Copy this project in, then:

```bash
cd /opt/pdfsuite        # wherever you put it
bash deploy/install.sh
```

### Option C — manual

```bash
cp .env.example .env       # edit credentials + SESSION_SECRET + DOMAIN
docker compose up -d --build
```

Then open **https://pdf.snmk.xyz** (once DNS and ports 80/443 are in place).

---

## Configuration

Edit `.env` (copied from `.env.example`):

| Variable         | Default                    | Meaning                                   |
|------------------|----------------------------|-------------------------------------------|
| `GATEWAY_USER`   | `pdf`                      | Login username                            |
| `GATEWAY_PASS`   | `1`                        | Login password (decoy hint aside)         |
| `SESSION_SECRET` | `please-change-this-secret`| Cookie signing key — **change this**      |
| `SITE_TITLE`     | `PDF Studio`               | Branding text                             |
| `DOMAIN`         | `pdf.snmk.xyz`             | Public hostname Caddy serves over HTTPS   |
| `ACME_EMAIL`     | _(empty)_                  | Let's Encrypt contact email (optional)    |

Generate a strong secret: `openssl rand -hex 32`.

---

## Operations

```bash
docker compose ps            # status
docker compose logs -f       # follow logs
docker compose pull && docker compose up -d   # update images
docker compose down          # stop
```

Stirling-PDF state (OCR language packs, configs, logs) lives in named Docker
volumes, so it survives restarts and updates.

---

## Security notes

- Traffic is served over **HTTPS** by Caddy with an auto-renewing Let's Encrypt
  certificate, and session cookies are flagged `Secure`/`HttpOnly`. Only ports
  80/443 (Caddy) are exposed; the gateway and Stirling stay on the internal
  network.
- Always change `SESSION_SECRET` from the default.
- The single-user login is intended for a private home lab. For multi-user setups
  with real accounts, enable Stirling-PDF's own login system instead.
