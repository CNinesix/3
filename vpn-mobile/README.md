# Mobile VPN setup for the USB auto-install (th2)

This folder adds a **"set up VPN for mobile"** step to the USB auto-install
flow. It turns the server lists already tracked in this repo into config that a
phone's SSH/SSL-tunnel app can import.

The repo stores only each server's **name, host, and status**:

- `authbot` — SSH servers, lines look like `### Name 1.2.3.4 true`
- `authws`  — WebSocket/SSL entries, lines look like `#& Name 1.2.3.4`

Ports, username/password, and the SNI/payload are **per-account** and are *not*
stored in the repo. You supply them at generation time, so nothing secret is
committed.

## Files

| File | What it does |
|------|--------------|
| `autorun-usb.sh` | Entry point. Drop this folder on the USB next to the th2 installer and run it. Generates the config and prints phone instructions. |
| `generate-mobile-config.sh` | Parses `authbot`/`authws` and writes import-ready files to `dist/`. |
| `dist/` | Generated output (git-ignored). Created on first run. |

## Quick start

From the USB (PC, or Termux on Android):

```sh
sh vpn-mobile/autorun-usb.sh
```

It first asks for the **installation code** (see
[`../install/README.md`](../install/README.md)) and refuses to run without it.
Pass it non-interactively with `INSTALL_CODE=...`, or bypass for testing with
`SKIP_CODE=1`.

That writes into `vpn-mobile/dist/`:

- `mobile-vpn-servers.txt` — human-readable list (name, host, ws/wss URLs, status)
- `http-injector-import.txt` — one importable block per server
- `mobile-vpn-servers.json` — same data as JSON for apps that read it

## Baking in your real account details

The default output uses obvious placeholders (`YOUR_USERNAME`, etc.). Pass your
real values as environment variables and re-run to bake them in:

```sh
VPN_USER=me \
VPN_PASS=secret \
VPN_SNI=bug.example.com \
VPN_WS_PORT=80 \
VPN_SSL_PORT=443 \
  sh vpn-mobile/generate-mobile-config.sh
```

| Variable | Meaning | Default |
|----------|---------|---------|
| `VPN_USER` | SSH username | `YOUR_USERNAME` |
| `VPN_PASS` | SSH password | `YOUR_PASSWORD` |
| `VPN_SNI` | SNI / bug host for SSL tunnels | `YOUR_SNI_OR_BUGHOST` |
| `VPN_WS_PORT` | WebSocket (ws) port | `80` |
| `VPN_SSL_PORT` | SSL/TLS (wss) port | `443` |
| `VPN_PAYLOAD` | HTTP payload; `[host]` is substituted per server | `GET / HTTP/1.1…Upgrade: websocket` |

## Using it on the phone

1. Copy `vpn-mobile/dist/*` from the USB to the phone's **Download** folder
   (on Termux: `termux-setup-storage` once, then
   `cp vpn-mobile/dist/* ~/storage/shared/Download/`).
2. Open your tunnel app — HTTP Injector, HTTP Custom, SocksHTTP, or
   NapsternetV — and choose **Import config**, then pick
   `http-injector-import.txt`.
3. Select a server from the list, confirm user/pass/SNI, and connect.

Use only servers and accounts you are authorized to use.
