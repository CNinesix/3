# Self-Hosting Obsidian Sync on Proxmox (Access From All Devices)

Goal: keep your Obsidian vault data on your own Proxmox server, and have it
sync in near-real-time to every device — Windows/Mac/Linux desktops, Android,
and iPhone/iPad — even when you're away from home.

The recommended stack is:

| Layer | Choice | Why |
|---|---|---|
| Sync engine | **Self-hosted LiveSync** Obsidian plugin + **CouchDB** | Real-time sync, conflict handling, works on iOS and Android, free |
| Where it runs | Debian/Ubuntu **LXC container** on Proxmox (Docker inside, or bare CouchDB) | Lightweight, easy to back up with Proxmox Backup / vzdump |
| Remote access | **Tailscale** (easiest) or Cloudflare Tunnel / reverse proxy + HTTPS | iOS requires HTTPS for non-localhost; Tailscale avoids opening ports |

Alternatives are covered at the end (Syncthing, Remotely Save + WebDAV, Git).

---

## 1. Create an LXC container on Proxmox

1. In the Proxmox web UI: **Create CT** → Debian 12 template.
   - 1 vCPU, 1 GB RAM, 8 GB disk is plenty for a personal vault.
   - For Docker inside LXC: check **Nesting** (Options → Features → nesting=1).
     An *unprivileged* container with nesting works fine.
2. Start the container and open its console.

```bash
apt update && apt upgrade -y
# Install Docker
curl -fsSL https://get.docker.com | sh
```

> You can also skip Docker and `apt install couchdb`, but the Docker image is
> easier to pin and upgrade.

## 2. Run CouchDB

Create `/opt/couchdb/docker-compose.yml`:

```yaml
services:
  couchdb:
    image: couchdb:3
    container_name: obsidian-couchdb
    restart: unless-stopped
    environment:
      - COUCHDB_USER=obsidian
      - COUCHDB_PASSWORD=CHANGE_ME_STRONG_PASSWORD
    ports:
      - "5984:5984"
    volumes:
      - ./data:/opt/couchdb/data
      - ./local.ini:/opt/couchdb/etc/local.d/local.ini
```

Create `/opt/couchdb/local.ini` with the settings LiveSync needs:

```ini
[couchdb]
single_node = true
max_document_size = 50000000

[chttpd]
require_valid_user = true
max_http_request_size = 4294967296
enable_cors = true

[chttpd_auth]
require_valid_user = true
authentication_redirect = /_utils/session.html

[httpd]
WWW-Authenticate = Basic realm="couchdb"
bind_address = 0.0.0.0

[cors]
origins = app://obsidian.md, capacitor://localhost, http://localhost
credentials = true
headers = accept, authorization, content-type, origin, referer
methods = GET,PUT,POST,HEAD,DELETE
max_age = 3600
```

Start it:

```bash
cd /opt/couchdb && docker compose up -d
# Verify:
curl http://localhost:5984
```

You should get a JSON `{"couchdb":"Welcome",...}` response.

## 3. Make it reachable from anywhere (pick ONE)

### Option A — Tailscale (recommended, no open ports)

Tailscale creates a private VPN between all your devices. Nothing is exposed
to the public internet.

1. In the LXC (or on the Proxmox host):
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   tailscale up
   ```
2. Install the Tailscale app on every phone/laptop and log in with the same
   account.
3. Get HTTPS with a valid certificate (needed for the iOS Obsidian app):
   ```bash
   # Enable HTTPS certificates + MagicDNS in the Tailscale admin console first
   tailscale serve --bg 5984
   ```
   Your CouchDB is now at `https://<container-name>.<tailnet>.ts.net`
   with a real TLS certificate, reachable only by your own devices.

### Option B — Cloudflare Tunnel (public URL, no open ports)

If you own a domain on Cloudflare: run `cloudflared` in the container and map
`couchdb.yourdomain.com` → `http://localhost:5984`. You get HTTPS
automatically and never open a port on your router.

### Option C — Reverse proxy + port forward (classic)

Nginx Proxy Manager / Caddy in front of CouchDB, Let's Encrypt certificate,
forward 443 on your router. Works, but exposes the service publicly — use a
strong password and consider fail2ban.

> Whatever you pick, the end result you need is a single **HTTPS URL** for
> CouchDB. Plain `http://192.168.x.x:5984` works on desktop but the iOS app
> will refuse it.

## 4. Set up Obsidian on your devices

On **every** device:

1. Install Obsidian and open (or create) your vault.
2. Community plugins → browse → install **Self-hosted LiveSync** → enable.
3. In the plugin's setup wizard enter:
   - **URI**: your HTTPS URL (e.g. `https://couch.tailnet.ts.net`)
   - **Username / Password**: the CouchDB credentials from step 2
   - **Database name**: e.g. `obsidian` (same on all devices; the plugin
     creates it)
4. Enable **End-to-End Encryption** in the plugin and set a passphrase —
   your notes are then encrypted before they ever reach the server.
5. On the first device choose **"Copy setup to other devices"**: the plugin
   generates a setup URI (a long `obsidian://setuplivesync?...` string
   protected by a passphrase). On each other device, just paste that URI
   instead of retyping everything.
6. Set sync mode to **LiveSync** for instant sync, or Periodic if you prefer.

Edit a note on one device and watch it appear on the others within seconds.

## 5. Back it up

The database *is* your vault now, so back it up:

- Add the LXC to your normal Proxmox backup job (Datacenter → Backup, or
  Proxmox Backup Server). This captures `/opt/couchdb/data`.
- Each device also keeps a full local copy of the vault, which is itself a
  layer of redundancy.

## Maintenance notes

- Upgrade CouchDB: `docker compose pull && docker compose up -d`.
- The LiveSync plugin occasionally suggests "Rebuild database" after major
  plugin upgrades — do it from your primary device.
- If the database grows large, use the plugin's `Hatch → Compact database`
  or CouchDB's `_compact` endpoint.

---

## Alternatives, if LiveSync isn't your taste

| Method | Good | Bad |
|---|---|---|
| **Syncthing** (LXC on Proxmox as the always-on node) | Simple file sync, no plugin needed | No official iOS client (Möbius Sync is paid/limited); sync conflicts on simultaneous edits |
| **Remotely Save plugin + WebDAV/S3** (Nextcloud or MinIO on Proxmox) | Works if you already run Nextcloud | Manual/interval sync, slower, more conflict-prone |
| **obsidian-git** (Gitea/Forgejo on Proxmox) | Full history, diffs | Clunky on mobile, merge conflicts are on you |
| **Official Obsidian Sync** | Zero maintenance, supports the developers | $4–8/month, data not on your Proxmox |

For "edit anywhere on every device including iPhone, hosted on my own
Proxmox," **CouchDB + Self-hosted LiveSync + Tailscale** is the combination
that works best in practice.
