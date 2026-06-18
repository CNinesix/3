# SSL / TLS setup for a2.snmk.xyz

Pick **one** of the two options below. Both terminate TLS at Nginx.

---

## Option A — Let's Encrypt (free, auto-renewing)

Use this when your server is reachable on ports 80/443 from the internet
(DNS A/AAAA record for `a2.snmk.xyz` points at the server's public IP, and
in Cloudflare the record is **DNS only / grey cloud** during issuance).

```bash
sudo apt install certbot python3-certbot-nginx
sudo mkdir -p /var/www/certbot

# First install the HTTP server block from deploy/nginx, then:
sudo certbot --nginx -d a2.snmk.xyz --redirect -m you@example.com --agree-tos

# Auto-renewal is installed as a systemd timer; test it:
sudo certbot renew --dry-run
```

Certbot will fill in the `ssl_certificate` paths used in
`deploy/nginx/a2.snmk.xyz.conf` (`/etc/letsencrypt/live/a2.snmk.xyz/...`).

---

## Option B — Cloudflare (proxied, orange cloud)

Use this when the domain is proxied through Cloudflare. Two layers:

1. **Browser → Cloudflare**: enable SSL/TLS mode **Full (strict)** in the
   Cloudflare dashboard (SSL/TLS → Overview).
2. **Cloudflare → your server (origin)**: install a free Cloudflare
   **Origin Certificate** (SSL/TLS → Origin Server → Create Certificate,
   15-year validity).

```bash
sudo mkdir -p /etc/ssl/cloudflare
sudo nano /etc/ssl/cloudflare/a2.snmk.xyz.pem   # paste the Origin Certificate
sudo nano /etc/ssl/cloudflare/a2.snmk.xyz.key   # paste the Private Key
sudo chmod 600 /etc/ssl/cloudflare/a2.snmk.xyz.key
```

Then in `deploy/nginx/a2.snmk.xyz.conf` comment out the Let's Encrypt
`ssl_certificate*` lines and uncomment the Cloudflare ones, and reload:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Recommended Cloudflare hardening:
- Turn on **Always Use HTTPS**.
- Set **Minimum TLS Version** to 1.2.
- (Optional) Lock origin to Cloudflare IPs with a firewall / `allow` rules,
  or use **Authenticated Origin Pulls**.

---

## DNS

Create an `A` record (and `AAAA` if you have IPv6):

```
a2.snmk.xyz.  A   <your-server-public-ip>
```

For Cloudflare proxied mode keep the orange cloud **on**; for Let's Encrypt
issuance via the nginx plugin keep it **off** until the cert is issued, then
you may turn it back on.
