# PDF Studio — self-hosted PDF editing & security suite for Proxmox

A complete, web-based PDF toolkit you run on your own Proxmox box. It bundles:

- **A branded login page + dashboard** (the gateway) — a clean entry point with
  a sign-in screen and a categorized tool dashboard.
- **[Stirling-PDF](https://github.com/Stirling-Tools/Stirling-PDF)** — the engine:
  50+ tools for editing, organizing, converting and **securing** PDFs, all
  running locally so your files never leave the server.

Everything runs as Docker containers, orchestrated with Docker Compose, and is
published at **https://pdf.snmk.xyz** through Cloudflare.

```
You ──HTTPS──> Cloudflare (pdf.snmk.xyz)
                  ⇡ outbound-only tunnel (no port-forward needed)
            cloudflared ──> gateway :9932 (login + dashboard) ──> Stirling-PDF
```

The gateway is published on the host at port **9932**, so Cloudflare's origin is
`http://<host-LAN-IP>:9932`. Add a **Cloudflare Access** policy to limit entry to
your email, and the gateway's `pdf`/`1` login is a second layer behind it.

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

## Publish pdf.snmk.xyz with Cloudflare

> **What "local IP" goes into Cloudflare?** The LAN IP of the container/VM
> running this stack. Find it by running this **on that machine**:
> ```bash
> hostname -I | awk '{print $1}'
> ```
> It looks like `192.168.x.x` or `10.x.x.x`. Use it as `http://<that-ip>:9932`.

### Recommended — Cloudflare Tunnel (no port-forwarding, works behind NAT)

1. Cloudflare **Zero Trust → Networks → Tunnels → Create a tunnel** → name it,
   choose **Docker**, and copy the tunnel **token** (`eyJ...`).
2. Put the token in `.env` as `TUNNEL_TOKEN=...` and run the stack — the bundled
   `cloudflared` container connects automatically.
3. In the tunnel, **add a Public Hostname**:
   - **Subdomain:** `pdf`  **Domain:** `snmk.xyz`
   - **Service:** `HTTP` → **URL:** `gateway:3000`
     *(cloudflared is in the same compose network, so it reaches the gateway by
     name — no IP needed. If you instead run cloudflared elsewhere on your LAN,
     use `http://<host-LAN-IP>:9932`.)*
4. Cloudflare auto-creates the DNS record. Done — `https://pdf.snmk.xyz` is live.

### Alternative — plain DNS A record (needs a public IP + port-forward)

Cloudflare DNS records must point at a **public** IP, *not* a local one. If you
have a static public IP: create an `A` record `pdf` → your public IP
(`curl ifconfig.me`), port-forward `9932` (or `80/443` via your own reverse
proxy) to the container, and proxy through Cloudflare. The Tunnel above avoids
all of this.

### Lock access to only you

Cloudflare **Zero Trust → Access → Applications → Add a self-hosted app** for
`pdf.snmk.xyz`, with a policy that **allows only `cninesix@gmail.com`**.
Cloudflare then requires your login before anyone reaches the site.

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
cp .env.example .env       # set SESSION_SECRET + TUNNEL_TOKEN (+ credentials)
docker compose up -d --build
```

On the LAN it's reachable at `http://<host-LAN-IP>:9932`; publicly at
**https://pdf.snmk.xyz** once the Cloudflare Tunnel/DNS is configured above.

---

## Configuration

Edit `.env` (copied from `.env.example`):

| Variable         | Default                    | Meaning                                   |
|------------------|----------------------------|-------------------------------------------|
| `GATEWAY_USER`   | `pdf`                      | Login username                            |
| `GATEWAY_PASS`   | `1`                        | Login password (decoy hint aside)         |
| `SESSION_SECRET` | `please-change-this-secret`| Cookie signing key — **change this**      |
| `SITE_TITLE`     | `PDF Studio`               | Branding text                             |
| `TUNNEL_TOKEN`   | _(required)_               | Cloudflare Tunnel token (`eyJ...`)        |

Generate a strong secret: `openssl rand -hex 32`.

Change the LAN port by editing the `9932:3000` mapping in `docker-compose.yml`.

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

- Public traffic is served over **HTTPS by Cloudflare**; `cloudflared` dials out,
  so no inbound ports are open to the internet. Session cookies are flagged
  `Secure`/`HttpOnly`. Stirling-PDF stays on the internal network.
- The gateway's `9932` port is on your **LAN** only — don't port-forward it to
  the internet; reach the public site through Cloudflare instead.
- Restrict access with a **Cloudflare Access** policy (only your email) so it
  isn't open to the public.
- Always change `SESSION_SECRET` from the default.
- The single-user login is intended for a private home lab. For multi-user setups
  with real accounts, enable Stirling-PDF's own login system instead.
