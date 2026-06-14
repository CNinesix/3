"""Central configuration loaded from environment variables / .env file."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load .env from the project root if present (no-op if missing).
load_dotenv(BASE_DIR / ".env")


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_ids(raw: str | None) -> set[int]:
    ids: set[int] = set()
    for chunk in (raw or "").replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            ids.add(int(chunk))
    return ids


class Config:
    # Core
    SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-insecure-secret-change-me")
    BASE_URL = os.getenv("APP_BASE_URL", "https://a2.snmk.xyz")
    HOST = os.getenv("APP_HOST", "127.0.0.1")
    PORT = int(os.getenv("APP_PORT", "8000"))
    TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kuala_Lumpur")
    ENV = os.getenv("APP_ENV", "production")
    DEBUG = ENV == "development"

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'a2ros.db'}")

    # Bootstrap admin
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@a2.snmk.xyz")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeThisAdminPassword123")
    ADMIN_NAME = os.getenv("ADMIN_NAME", "A2 Admin")

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_ALLOWED_USER_IDS = _parse_ids(os.getenv("TELEGRAM_ALLOWED_USER_IDS"))
    TELEGRAM_POLL_TIMEOUT = int(os.getenv("TELEGRAM_POLL_TIMEOUT", "30"))

    # Scheduling / alerts
    DAILY_REPORT_TIME = os.getenv("DAILY_REPORT_TIME", "08:30")
    ALERTS_ENABLED = _bool(os.getenv("ALERTS_ENABLED"), True)

    # Optional transcription
    TRANSCRIBE_API_BASE = os.getenv("TRANSCRIBE_API_BASE", "").strip()
    TRANSCRIBE_API_KEY = os.getenv("TRANSCRIBE_API_KEY", "").strip()
    TRANSCRIBE_MODEL = os.getenv("TRANSCRIBE_MODEL", "whisper-1").strip()

    @classmethod
    def transcription_enabled(cls) -> bool:
        return bool(cls.TRANSCRIBE_API_BASE and cls.TRANSCRIBE_API_KEY)


config = Config()
