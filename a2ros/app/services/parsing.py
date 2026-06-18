"""Natural-language parsing for Telegram lead capture, stage updates and reminders.

Dependency-free (regex + a small relative-date parser) so it runs anywhere.
All datetimes are produced in the configured app timezone, then returned as
timezone-aware values.
"""
from __future__ import annotations

import datetime as dt
import re
from zoneinfo import ZoneInfo

from app.models import STAGES
from config import config

TZ = ZoneInfo(config.TIMEZONE)

_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


# --------------------------------------------------------------------------- #
# Monetary values:  RM80k, RM 80,000, 80k, 120000, RM1.2m
# --------------------------------------------------------------------------- #
def parse_money(text: str) -> float | None:
    if not text:
        return None
    m = re.search(
        r"(?:rm|myr|\$)?\s*([\d][\d,\.]*)\s*(k|m|ribu|juta)?",
        text.strip().lower(),
    )
    if not m:
        return None
    num = m.group(1).replace(",", "")
    try:
        value = float(num)
    except ValueError:
        return None
    suffix = (m.group(2) or "").lower()
    if suffix in {"k", "ribu"}:
        value *= 1_000
    elif suffix in {"m", "juta"}:
        value *= 1_000_000
    return value


# --------------------------------------------------------------------------- #
# Pipeline stage from free text
# --------------------------------------------------------------------------- #
_STAGE_ALIASES = {
    "new": "New", "lead": "New",
    "qualified": "Qualified", "qualify": "Qualified",
    "meeting": "Meeting", "site visit": "Meeting", "demo": "Meeting",
    "proposal": "Proposal", "quote": "Proposal", "quotation": "Proposal",
    "negotiation": "Negotiation", "negotiate": "Negotiation", "nego": "Negotiation",
    "won": "Won", "win": "Won", "closed won": "Won", "close won": "Won",
    "lost": "Lost", "closed lost": "Lost", "close lost": "Lost", "dead": "Lost",
}


def parse_stage(text: str) -> str | None:
    if not text:
        return None
    low = text.strip().lower()
    # direct stage names first
    for stage in STAGES:
        if stage.lower() in low:
            return stage
    for alias, stage in _STAGE_ALIASES.items():
        if alias in low:
            return stage
    return None


# --------------------------------------------------------------------------- #
# Lead capture:
#   "ABC Factory, Johor, CCTV upgrade, contact Mr Tan, value RM80k"
# Fields are comma separated; we detect zone/contact/value heuristically.
# --------------------------------------------------------------------------- #
def parse_lead(text: str) -> dict:
    text = re.sub(r"^\s*(new\s+lead|lead|addlead)\s*:?\s*", "", text, flags=re.I).strip()
    parts = [p.strip() for p in text.split(",") if p.strip()]
    result = {
        "name": "",
        "zone": "",
        "title": "",
        "contact_name": "",
        "contact_phone": "",
        "value": None,
        "raw": text,
    }
    if not parts:
        return result

    result["name"] = parts[0]
    leftover: list[str] = []
    for part in parts[1:]:
        low = part.lower()
        phone = re.search(r"(\+?\d[\d\s\-]{6,}\d)", part)
        if low.startswith("contact") or low.startswith("pic") or low.startswith("mr ") or low.startswith("ms ") or low.startswith("pn ") or low.startswith("en "):
            result["contact_name"] = re.sub(r"^(contact|pic)\s*:?\s*", "", part, flags=re.I).strip()
        elif "value" in low or "budget" in low or re.search(r"\brm\b|\bmyr\b", low) or re.search(r"\d+\s*(k|m)\b", low):
            money = parse_money(part)
            if money is not None:
                result["value"] = money
            else:
                leftover.append(part)
        elif phone:
            result["contact_phone"] = phone.group(1).strip()
        elif _looks_like_zone(low):
            result["zone"] = part
        else:
            leftover.append(part)

    # The first leftover (often the requirement/scope) becomes the opportunity title.
    if leftover:
        result["title"] = leftover[0]
        if len(leftover) > 1:
            result["raw"] = "; ".join(leftover)
    if not result["title"]:
        result["title"] = "New opportunity"
    return result


_ZONE_HINTS = [
    "johor", "jb", "iskandar", "nusajaya", "puteri", "sedenak", "kulai",
    "pasir gudang", "tanjung", "tg langsat", "senai", "tebrau", "plentong",
    "skudai", "masai", "ulu tiram", "gelang patok", "kota tinggi",
]


def _looks_like_zone(low: str) -> bool:
    return any(hint in low for hint in _ZONE_HINTS)


# --------------------------------------------------------------------------- #
# Account name extraction for /update, /search, /addnote, /remind
#   "Update ABC Factory to proposal stage" -> ("ABC Factory", "Proposal")
#   "Meeting note ABC Factory: they need 64 CCTV" -> ("ABC Factory", "they need…")
# --------------------------------------------------------------------------- #
def parse_update(text: str) -> tuple[str | None, str | None]:
    body = re.sub(r"^\s*(update|move)\s+", "", text, flags=re.I).strip()
    m = re.search(r"\bto\b\s+(.+)$", body, flags=re.I)
    stage = None
    name = body
    if m:
        stage = parse_stage(m.group(1))
        name = body[: m.start()].strip()
    else:
        stage = parse_stage(body)
    # strip trailing "stage" word from name if it leaked
    name = re.sub(r"\bstage\b", "", name, flags=re.I).strip(" .")
    return (name or None), stage


def parse_note(text: str) -> tuple[str | None, str]:
    """Returns (account_name, note_text)."""
    body = re.sub(r"^\s*(meeting\s+note|note|addnote)\s*", "", text, flags=re.I).strip()
    if ":" in body:
        name, note = body.split(":", 1)
        return name.strip() or None, note.strip()
    # fallback: first word group is the name
    return body.strip() or None, ""


# --------------------------------------------------------------------------- #
# Reminder parsing:
#   "Remind me to call ABC Factory next Monday 10am"
#   "/remind call ABC Factory tomorrow 9am"
# Returns (text, due_datetime_aware) ; due defaults to tomorrow 09:00 if absent.
# --------------------------------------------------------------------------- #
def parse_reminder(text: str, now: dt.datetime | None = None) -> tuple[str, dt.datetime]:
    body = re.sub(r"^\s*(remind(?:\s+me)?(?:\s+to)?|reminder)\s*:?\s*", "", text, flags=re.I).strip()
    now = now or dt.datetime.now(TZ)
    due, consumed_spans = _extract_datetime(body, now)
    # remove the consumed date/time tokens from the reminder text
    clean = body
    for span in sorted(consumed_spans, key=lambda s: s[0], reverse=True):
        clean = clean[: span[0]] + clean[span[1]:]
    clean = re.sub(r"\s{2,}", " ", clean).strip(" ,.")
    if not clean:
        clean = body
    if due is None:
        due = (now + dt.timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    return clean, due


def _extract_datetime(text: str, now: dt.datetime) -> tuple[dt.datetime | None, list[tuple[int, int]]]:
    low = text.lower()
    spans: list[tuple[int, int]] = []
    target_date = None
    hour, minute = None, None

    # --- time ---
    tmatch = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", low)
    if tmatch:
        hour = int(tmatch.group(1)) % 12
        if tmatch.group(3) == "pm":
            hour += 12
        minute = int(tmatch.group(2) or 0)
        spans.append(tmatch.span())
    else:
        tmatch = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", low)
        if tmatch:
            hour = int(tmatch.group(1))
            minute = int(tmatch.group(2))
            spans.append(tmatch.span())

    # --- explicit ISO date ---
    dmatch = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", low)
    if dmatch:
        target_date = dt.date(int(dmatch.group(1)), int(dmatch.group(2)), int(dmatch.group(3)))
        spans.append(dmatch.span())

    # --- "1 July" / "July 1" ---
    if target_date is None:
        m1 = re.search(r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\b", low)
        m2 = re.search(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2})\b", low)
        if m1:
            day = int(m1.group(1)); month = _MONTHS[m1.group(2)]
            target_date = _resolve_md(now, month, day)
            spans.append(m1.span())
        elif m2:
            month = _MONTHS[m2.group(1)]; day = int(m2.group(2))
            target_date = _resolve_md(now, month, day)
            spans.append(m2.span())

    # --- relative words ---
    if target_date is None:
        if re.search(r"\btomorrow\b", low):
            target_date = (now + dt.timedelta(days=1)).date()
            spans.append(re.search(r"\btomorrow\b", low).span())
        elif re.search(r"\btoday\b", low):
            target_date = now.date()
            spans.append(re.search(r"\btoday\b", low).span())
        elif re.search(r"\bnext week\b", low):
            target_date = (now + dt.timedelta(days=7)).date()
            spans.append(re.search(r"\bnext week\b", low).span())
        else:
            wd = re.search(r"\b(next\s+)?(" + "|".join(_WEEKDAYS) + r")\b", low)
            if wd:
                want = _WEEKDAYS[wd.group(2)]
                delta = (want - now.weekday()) % 7
                if delta == 0:
                    delta = 7  # "monday" means next monday if today is monday
                if wd.group(1):  # "next monday"
                    if delta < 7:
                        delta += 0  # already the upcoming one; "next" keeps upcoming
                target_date = (now + dt.timedelta(days=delta)).date()
                spans.append(wd.span())

    if target_date is None and hour is None:
        return None, spans

    if target_date is None:
        target_date = now.date()
    if hour is None:
        hour, minute = 9, 0

    due = dt.datetime(target_date.year, target_date.month, target_date.day, hour, minute, tzinfo=TZ)
    # if the resolved time already passed today, push to a sensible future
    if due <= now and not re.search(r"\btoday\b", text.lower()):
        due = due + dt.timedelta(days=1)
    return due, spans


def _resolve_md(now: dt.datetime, month: int, day: int) -> dt.date:
    year = now.year
    try:
        candidate = dt.date(year, month, day)
    except ValueError:
        candidate = dt.date(year, month, 1)
    if candidate < now.date():
        candidate = candidate.replace(year=year + 1)
    return candidate
