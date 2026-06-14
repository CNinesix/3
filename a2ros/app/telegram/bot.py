"""Telegram bot worker: long-polling loop + scheduled jobs.

Run with:  python run_bot.py
"""
from __future__ import annotations

import logging
import signal
import sys
import time

from app.db import init_db
from app.telegram.client import TelegramClient
from app.telegram.handlers import Dispatcher
from app.telegram.scheduler import build_scheduler
from config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("a2ros.bot")

_running = True


def _stop(*_args):
    global _running
    _running = False
    log.info("Shutdown signal received; stopping…")


def main() -> int:
    if not config.TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN is not set. Configure .env first.")
        return 1

    init_db()
    client = TelegramClient()

    me = client.get_me()
    if not me.get("ok"):
        log.error("Could not reach Telegram (check token / network): %s", me)
        return 1
    bot_username = me["result"].get("username")
    log.info("Bot @%s online. Allowed IDs: %s", bot_username, sorted(config.TELEGRAM_ALLOWED_USER_IDS) or "(set in dashboard)")

    client.set_my_commands()

    dispatcher = Dispatcher(client)
    scheduler = build_scheduler(client)
    scheduler.start()
    log.info("Scheduler started (timezone=%s, daily report=%s).", config.TIMEZONE, config.DAILY_REPORT_TIME)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    offset = None
    while _running:
        try:
            updates = client.get_updates(offset=offset)
            for update in updates:
                offset = update["update_id"] + 1
                dispatcher.handle_update(update)
        except Exception:  # pragma: no cover - keep the loop alive
            log.exception("Polling error; retrying in 3s")
            time.sleep(3)

    scheduler.shutdown(wait=False)
    log.info("Bot stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
