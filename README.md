# PDF Studio — self-hosted PDF editing & security suite for Proxmox

A complete, web-based PDF toolkit you run on your own Proxmox box. It bundles:

- **A branded login page + dashboard** (the gateway) — a clean entry point with
  a sign-in screen and a categorized tool dashboard.
- **[Stirling-PDF](https://github.com/Stirling-Tools/Stirling-PDF)** — the engine:
  50+ tools for editing, organizing, converting and **securing** PDFs, all
  running locally so your files never leave the server.

Everything runs as Docker containers, orchestrated with Docker Compose.

```
Browser ──> gateway (login + dashboard, :8088) ──> Stirling-PDF (private)
```

The gateway is the only thing exposed on your LAN. Stirling-PDF has no published
port — every request must pass the login first.

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
cp .env.example .env       # edit credentials + SESSION_SECRET
docker compose up -d --build
```

Then open **http://&lt;container-ip&gt;:8088**.

---

## Configuration

Edit `.env` (copied from `.env.example`):

| Variable         | Default                    | Meaning                                   |
|------------------|----------------------------|-------------------------------------------|
| `GATEWAY_USER`   | `pdf`                      | Login username                            |
| `GATEWAY_PASS`   | `1`                        | Login password (decoy hint aside)         |
| `SESSION_SECRET` | `please-change-this-secret`| Cookie signing key — **change this**      |
| `SITE_TITLE`     | `PDF Studio`               | Branding text                             |

Generate a strong secret: `openssl rand -hex 32`.

Change the published port by editing the `8088:3000` mapping in
`docker-compose.yml`.

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

- This serves plain **HTTP** on your LAN. For remote access, put it behind a
  reverse proxy with TLS (e.g. Caddy/Traefik/Nginx Proxy Manager) or a VPN
  (WireGuard/Tailscale). Don't port-forward `:8088` to the internet as-is.
- Always change `SESSION_SECRET` from the default.
- The single-user login is intended for a private home lab. For multi-user setups
  with real accounts, enable Stirling-PDF's own login system instead.
