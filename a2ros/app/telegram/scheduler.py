"""Scheduled Telegram jobs: morning report, proactive alerts, due reminders."""
from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Reminder, SentAlert, utcnow
from app.services import metrics
from app.services import settings as settings_svc
from app.telegram import formatting
from app.telegram.client import TelegramClient
from config import config

log = logging.getLogger("a2ros.scheduler")
TZ = ZoneInfo(config.TIMEZONE)


def _recipients(session) -> list[int]:
    return sorted(settings_svc.allowed_telegram_ids(session))


def _broadcast(client: TelegramClient, session, text: str) -> None:
    for chat_id in _recipients(session):
        client.send_message(chat_id, text)


def send_morning_report(client: TelegramClient) -> None:
    session = SessionLocal()
    try:
        if not settings_svc.get_bool(session, "daily_report_enabled", True):
            log.info("Morning report disabled in settings; skipping.")
            return
        text = formatting.morning_report_text(session)
        _broadcast(client, session, text)
        log.info("Morning report sent.")
    finally:
        SessionLocal.remove()


def scan_and_send_alerts(client: TelegramClient) -> None:
    session = SessionLocal()
    try:
        if not settings_svc.get_bool(session, "alerts_enabled", True):
            return
        alerts = metrics.scan_alerts(session)
        recipients = _recipients(session)
        for alert in alerts:
            # dedupe via SentAlert unique key
            existing = session.scalars(
                select(SentAlert).where(SentAlert.alert_key == alert["key"])
            ).first()
            if existing:
                continue
            session.add(SentAlert(alert_key=alert["key"]))
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                continue
            for chat_id in recipients:
                client.send_message(chat_id, alert["message"])
        if alerts:
            log.info("Alert scan complete (%d candidates).", len(alerts))
    finally:
        SessionLocal.remove()


def dispatch_due_reminders(client: TelegramClient) -> None:
    session = SessionLocal()
    try:
        now = utcnow()
        due = session.scalars(
            select(Reminder).where(
                Reminder.done.is_(False),
                Reminder.notified.is_(False),
                Reminder.due_at <= now,
            )
        ).all()
        recipients = _recipients(session)
        for reminder in due:
            where = f" — {reminder.account.name}" if reminder.account else ""
            msg = f"⏰ <b>Reminder</b>{where}\n{reminder.text}"
            for chat_id in recipients:
                client.send_message(chat_id, msg)
            reminder.notified = True
        if due:
            session.commit()
            log.info("Dispatched %d due reminders.", len(due))
    finally:
        SessionLocal.remove()


def build_scheduler(client: TelegramClient) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=TZ)

    hour, minute = (config.DAILY_REPORT_TIME.split(":") + ["0"])[:2]
    scheduler.add_job(
        send_morning_report,
        CronTrigger(hour=int(hour), minute=int(minute), timezone=TZ),
        args=[client],
        id="morning_report",
        replace_existing=True,
    )
    # Alerts: every hour on the hour
    scheduler.add_job(
        scan_and_send_alerts,
        CronTrigger(minute=0, timezone=TZ),
        args=[client],
        id="alert_scan",
        replace_existing=True,
    )
    # Due reminders: every minute
    scheduler.add_job(
        dispatch_due_reminders,
        "interval",
        minutes=1,
        args=[client],
        id="due_reminders",
        replace_existing=True,
    )
    return scheduler
