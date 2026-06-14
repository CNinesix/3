# A2 Revenue OS

**A2 Automation Revenue Operating System** — a self-hosted sales CRM dashboard
plus a Telegram mobile sales assistant for **A2 Automation Sdn Bhd**
(AI-powered security & smart-infrastructure, Johor Bahru).

Main dashboard URL (production): **https://a2.snmk.xyz**

It helps you run the whole revenue pipeline — leads, accounts, opportunities,
proposals, reminders and CEO-level reporting — from a browser **and** from
Telegram on your phone.

---

## Table of contents
1. [Features](#features)
2. [Architecture & tech stack](#architecture--tech-stack)
3. [Quick start (local)](#quick-start-local)
4. [Configuration (environment variables)](#configuration-environment-variables)
5. [Telegram bot setup](#telegram-bot-setup)
6. [Telegram commands](#telegram-commands)
7. [Security model](#security-model)
8. [Production deployment (a2.snmk.xyz)](#production-deployment-a2snmkxyz)
9. [Docker deployment](#docker-deployment)
10. [Database schema](#database-schema)
11. [Backup & restore](#backup--restore)
12. [Project layout](#project-layout)

---

## Features

### Dashboard (web)
- **Login authentication** with admin & user roles (Flask-Login, hashed passwords).
- **Mobile-responsive** dashboard (works as a phone web-app).
- **KPIs**: monthly revenue (Won), pipeline value, weighted pipeline, hot
  opportunities, proposals pending, expected closing this month.
- **Charts**: pipeline by stage, open value by zone (built-in canvas charts, no CDN).
- **Accounts / customers** CRUD with contacts, zone, notes & activity log.
- **Opportunities / pipeline** with stages New → Qualified → Meeting → Proposal →
  Negotiation → Won/Lost, value, probability, expected close, hot flag.
- **Reminders / follow-ups** that fire via Telegram.
- **Telegram control page**: bot status, allowed user IDs, last command,
  activity log, reminder list, daily-report toggle, enable/disable alerts.
- **Admin → Users**: create users, set roles, whitelist Telegram IDs.

### Telegram mobile sales assistant
1. Daily sales reminder (meetings, follow-ups, proposals pending, hot deals).
2. **Lead capture** — `New lead: ABC Factory, Johor, CCTV upgrade, contact Mr Tan, value RM80k` → saved to CRM automatically.
3. **Quick pipeline update** — `Update ABC Factory to proposal stage`.
4. **Follow-up reminders** — `Remind me to call ABC Factory next Monday 10am`.
5. **CEO summary** — `/summary` (revenue, pipeline value, hot opps, proposals, expected closing).
6. **Opportunity search** — `/search ABC Factory` (info, stage, value, last activity, next action).
7. **Meeting-note capture** — `Meeting note ABC Factory: need 64 CCTV, access control, budget RM120k, decide July`.
8. **Daily morning report** every day at 08:30 Malaysia time.
9. **Proactive alerts** — proposal with no follow-up after 3 days, deal idle > 7 days, closing within 5 days.
10. **Voice notes** — send a Telegram voice note; it's transcribed (if enabled) and saved as a meeting note.

---

## Architecture & tech stack

```
                         ┌──────────────────────────┐
  Browser  ── HTTPS ──►  │ Nginx (TLS, a2.snmk.xyz)  │
                         └────────────┬─────────────┘
                                      │ proxy :8000
                          ┌───────────▼───────────┐
                          │  a2ros-web (gunicorn)  │  Flask dashboard + auth
                          └───────────┬───────────┘
                                      │  shared DB (SQLAlchemy)
                          ┌───────────▼───────────┐
                          │   SQLite / PostgreSQL  │
                          └───────────▲───────────┘
                                      │
                          ┌───────────┴───────────┐   long-poll
   Telegram  ◄────────────│   a2ros-bot worker     │◄───────────►  Telegram API
                          │  polling + APScheduler │
                          └────────────────────────┘
```

- **Python 3.11**, **Flask 3**, **Flask-Login**, **SQLAlchemy 2**.
- **Telegram**: plain `requests` client + long-polling worker (no async deps).
- **Scheduling**: APScheduler (morning report, alerts, due reminders) in
  `Asia/Kuala_Lumpur` time.
- **DB**: SQLite by default (zero-config), PostgreSQL supported via `DATABASE_URL`.
- **Serving**: Gunicorn behind Nginx; systemd or Docker Compose.

The web app and the bot are **two processes** sharing one database, so you can
run, restart and scale them independently.

---

## Quick start (local)

```bash
cd a2ros
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then edit secrets (at least APP_SECRET_KEY)
python manage.py init-db      # create tables + bootstrap admin
python manage.py seed         # optional: load sample Johor pipeline data

# Terminal 1 — dashboard
python run_web.py             # http://127.0.0.1:8000

# Terminal 2 — Telegram bot (after setting TELEGRAM_* in .env)
python run_bot.py
```

Log in at http://127.0.0.1:8000 with the `ADMIN_EMAIL` / `ADMIN_PASSWORD`
from your `.env`.

> Using `make`? `make install && make init && make seed && make web`.

---

## Configuration (environment variables)

All configuration is via environment variables, loaded from `.env`
(see `.env.example`). Key ones:

| Variable | Purpose |
|---|---|
| `APP_SECRET_KEY` | Flask session signing key — **set a long random value**. |
| `APP_BASE_URL` | Public URL, e.g. `https://a2.snmk.xyz`. |
| `APP_HOST` / `APP_PORT` | Bind address (use `0.0.0.0` in containers). |
| `APP_TIMEZONE` | Timezone for reports/reminders (default `Asia/Kuala_Lumpur`). |
| `APP_ENV` | `production` (secure cookies) or `development`. |
| `DATABASE_URL` | `sqlite:////var/lib/a2ros/a2ros.db` or `postgresql+psycopg2://…`. |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_NAME` | Bootstrap admin created on `init-db`. |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather. |
| `TELEGRAM_ALLOWED_USER_IDS` | Comma-separated numeric Telegram user IDs allowed to use the bot. |
| `DAILY_REPORT_TIME` | `HH:MM` (24h) for the morning report (default `08:30`). |
| `ALERTS_ENABLED` | Master switch for proactive alerts. |
| `TRANSCRIBE_API_BASE` / `TRANSCRIBE_API_KEY` / `TRANSCRIBE_MODEL` | Optional voice-note transcription (OpenAI-compatible `/audio/transcriptions`). |

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## Telegram bot setup

1. In Telegram, open **@BotFather** → `/newbot` → choose a name & username →
   copy the **bot token** into `TELEGRAM_BOT_TOKEN` in `.env`.
2. Get your **numeric Telegram user ID** from **@userinfobot** and put it in
   `TELEGRAM_ALLOWED_USER_IDS` (comma-separated for multiple people).
3. Start the worker: `python run_bot.py` (or the `a2ros-bot` service).
   On start it registers the command menu with Telegram automatically.
4. Message your bot `/start`. You can add more allowed IDs at runtime on the
   dashboard **Telegram** page (no restart needed).

Voice transcription is optional: set `TRANSCRIBE_API_BASE` +
`TRANSCRIBE_API_KEY` (e.g. an OpenAI Whisper endpoint). If unset, voice notes
are still saved as untranscribed notes.

---

## Telegram commands

| Command | What it does |
|---|---|
| `/start` | Connect & show help. |
| `/help` | List all commands. |
| `/summary` | CEO summary: revenue, pipeline value, hot opps, proposals, expected closing. |
| `/today` | Today's meetings & follow-ups. |
| `/leads` | New leads to contact. |
| `/hot` | Hot opportunities. |
| `/pipeline` | Pipeline value by stage. |
| `/followup` | Follow-ups due (incl. overdue). |
| `/addlead` | `ABC Factory, Johor, CCTV upgrade, contact Mr Tan, value RM80k` |
| `/addnote` | `ABC Factory: need 64 CCTV, budget RM120k, decide July` |
| `/search` | `ABC Factory` → info, stage, value, last activity, next action. |
| `/update` | `ABC Factory to proposal` |
| `/remind` | `call ABC Factory next Monday 10am` |
| `/report` | Send today's full morning report now. |

Natural language also works without slashes, e.g.
*“New lead: …”*, *“Update ABC Factory to proposal stage”*,
*“Meeting note ABC Factory: …”*, *“Remind me to call ABC Factory tomorrow 9am”*.

**Scheduled automatically:**
- 08:30 (Malaysia) — daily morning report.
- Hourly — alert scan (proposal no-follow-up > 3 days, idle > 7 days, closing within 5 days).
- Every minute — due reminders dispatched to Telegram.

---

## Security model

- **The bot only responds to whitelisted Telegram user IDs.** If no whitelist is
  configured, the bot denies everyone (secure default). Whitelist = the env list
  `TELEGRAM_ALLOWED_USER_IDS` **plus** any IDs added on the dashboard Telegram page.
- **No public access** to the bot; denied attempts are logged on the Telegram page.
- **Dashboard requires login**; passwords are hashed (Werkzeug PBKDF2).
- Secrets live in environment variables (`TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_ALLOWED_USER_IDS`, `APP_SECRET_KEY`, `DATABASE_URL`) — never in code.
- Production cookies are `Secure`, `HttpOnly`, `SameSite=Lax`.
- Nginx adds HSTS and other security headers (see the vhost config).
- Run the services as a non-root `a2ros` user (systemd units do this).

---

## Production deployment (a2.snmk.xyz)

Target: Ubuntu/Debian server, app in `/opt/a2ros`, DB in `/var/lib/a2ros`.

```bash
# 1. System packages
sudo apt update && sudo apt install -y python3-venv python3-pip nginx sqlite3

# 2. Dedicated user + directories
sudo useradd --system --create-home --shell /usr/sbin/nologin a2ros
sudo mkdir -p /opt/a2ros /var/lib/a2ros
sudo chown -R a2ros:a2ros /opt/a2ros /var/lib/a2ros

# 3. Deploy the code (clone or copy the a2ros/ folder into /opt/a2ros)
sudo -u a2ros git clone <your-repo> /opt/a2ros   # or rsync the a2ros/ dir
cd /opt/a2ros

# 4. Virtualenv + deps
sudo -u a2ros python3 -m venv .venv
sudo -u a2ros .venv/bin/pip install -r requirements.txt

# 5. Configuration
sudo -u a2ros cp .env.example .env
sudo -u a2ros nano .env        # set APP_SECRET_KEY, DATABASE_URL=sqlite:////var/lib/a2ros/a2ros.db,
                               # ADMIN_*, TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_IDS, APP_BASE_URL

# 6. Initialise DB + admin (+ optional sample data)
sudo -u a2ros .venv/bin/python manage.py init-db
sudo -u a2ros .venv/bin/python manage.py seed   # optional

# 7. systemd services (web + bot)
sudo cp deploy/systemd/a2ros-web.service /etc/systemd/system/
sudo cp deploy/systemd/a2ros-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now a2ros-web a2ros-bot
sudo systemctl status a2ros-web a2ros-bot

# 8. Nginx reverse proxy
sudo cp deploy/nginx/a2.snmk.xyz.conf /etc/nginx/sites-available/a2.snmk.xyz
sudo ln -s /etc/nginx/sites-available/a2.snmk.xyz /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 9. TLS — see deploy/SSL.md (Let's Encrypt or Cloudflare)
```

Then browse to **https://a2.snmk.xyz** and sign in.

### Automated daily backup (cron)
```bash
sudo crontab -u a2ros -e
# add:
0 2 * * *  /opt/a2ros/scripts/backup.sh /var/backups/a2ros >> /var/log/a2ros-backup.log 2>&1
```

---

## Docker deployment

```bash
cp .env.example .env            # edit; APP_HOST is forced to 0.0.0.0 in compose
docker compose up -d --build
docker compose exec web python manage.py init-db
docker compose exec web python manage.py seed   # optional
```

The web app listens on `127.0.0.1:8000`; put the provided Nginx config + TLS in
front of it for `a2.snmk.xyz`. The `bot` service runs the Telegram worker.
Data persists in the `a2ros-data` volume; backups land in `./backups`.

---

## Database schema

Tables (created by `manage.py init-db`):

- **users** — `id, email, password_hash, name, role(admin|user), telegram_user_id, is_active, created_at`
- **accounts** — `id, name, industry, zone, location, contact_name, contact_phone, contact_email, notes, owner_id, created_at`
- **opportunities** — `id, account_id, title, description, stage, value, currency, probability, expected_close_date, source, owner_id, is_hot, created_at, updated_at, last_activity_at, proposal_sent_at`
- **activities** — `id, account_id, opportunity_id, type(note|meeting_note|call|email|stage_change|voice_note), note, created_by, source(web|telegram), created_at`
- **reminders** — `id, user_id, account_id, opportunity_id, text, due_at, done, notified, created_at`
- **telegram_logs** — `id, telegram_user_id, username, command, raw_text, response_summary, allowed, created_at`
- **sent_alerts** — `id, alert_key (unique), created_at` (alert de-duplication)
- **settings** — `key, value` (runtime toggles: daily report, alerts, extra Telegram IDs)

Pipeline stages: `New, Qualified, Meeting, Proposal, Negotiation, Won, Lost`
(open = the first five).

---

## Backup & restore

```bash
# Backup (auto-detects SQLite vs Postgres from DATABASE_URL)
./scripts/backup.sh /var/backups/a2ros

# Restore (stop services first!)
sudo systemctl stop a2ros-web a2ros-bot
./scripts/restore.sh /var/backups/a2ros/a2ros_20260614_020000.sqlite.gz
sudo systemctl start a2ros-web a2ros-bot
```

Backups are gzipped and timestamped; `backup.sh` prunes ones older than
`RETENTION_DAYS` (default 30).

---

## Admin & user login

- **Admin** is bootstrapped from `ADMIN_EMAIL` / `ADMIN_PASSWORD` on `init-db`.
  Admins can manage users and whitelist Telegram IDs (**Users** page).
- **Add users** via **Users → Add user** (role user or admin).
- Change your own name / password / Telegram ID under **Settings**.
- Reset a password from the CLI: `python manage.py reset-password user@example.com NewPass123`.

---

## Project layout

```
a2ros/
├── app/
│   ├── webapp.py            # Flask app factory
│   ├── db.py  models.py     # SQLAlchemy engine + ORM models
│   ├── extensions.py        # Flask-Login
│   ├── auth/routes.py       # login / logout
│   ├── web/routes.py        # dashboard, accounts, pipeline, reminders, telegram, admin
│   ├── services/            # crm, metrics, parsing, settings (shared web+bot)
│   └── telegram/            # client, handlers, formatting, scheduler, transcribe, bot
├── templates/  static/      # Jinja2 templates + CSS/JS
├── scripts/                 # init_db, seed, backup.sh, restore.sh
├── deploy/                  # nginx vhost, systemd units, SSL.md
├── manage.py                # CLI: init-db / create-admin / seed / reset-password
├── run_web.py  run_bot.py  wsgi.py  gunicorn.conf.py
├── Dockerfile  docker-compose.yml  Makefile
└── requirements.txt  .env.example
```

---

© A2 Automation Sdn Bhd. Internal sales tooling.
