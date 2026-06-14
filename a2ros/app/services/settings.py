"""Runtime settings helpers (DB-backed key/value, with env defaults)."""
from __future__ import annotations

from sqlalchemy import select

from app.models import Setting
from config import config

_DEFAULTS = {
    "daily_report_enabled": "true",
    "alerts_enabled": "true" if config.ALERTS_ENABLED else "false",
    "extra_telegram_ids": "",  # comma separated, added on top of env whitelist
}


def get(session, key: str, default: str | None = None) -> str:
    row = session.get(Setting, key)
    if row is not None:
        return row.value
    if default is not None:
        return default
    return _DEFAULTS.get(key, "")


def get_bool(session, key: str, default: bool = False) -> bool:
    raw = get(session, key, "true" if default else "false")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def set_value(session, key: str, value: str) -> None:
    row = session.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    session.commit()


def ensure_defaults(session) -> None:
    changed = False
    for key, value in _DEFAULTS.items():
        if session.get(Setting, key) is None:
            session.add(Setting(key=key, value=value))
            changed = True
    if changed:
        session.commit()


def allowed_telegram_ids(session) -> set[int]:
    """Union of env-configured IDs + extra IDs configured in the dashboard."""
    ids = set(config.TELEGRAM_ALLOWED_USER_IDS)
    extra = get(session, "extra_telegram_ids", "")
    for chunk in extra.replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            ids.add(int(chunk))
    return ids
