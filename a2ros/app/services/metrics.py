"""Pipeline metrics and report data, shared by dashboard and Telegram."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.models import (
    Account,
    Activity,
    OPEN_STAGES,
    Opportunity,
    Reminder,
    utcnow,
)
from config import config

TZ = ZoneInfo(config.TIMEZONE)
HOT_FOLLOWUP_DAYS = 3   # proposal with no follow-up after N days
IDLE_DAYS = 7           # deal idle for more than N days
CLOSING_SOON_DAYS = 5   # closing date within N days


def _local_now() -> dt.datetime:
    return dt.datetime.now(TZ)


def _to_utc_naive(local: dt.datetime) -> dt.datetime:
    return local.astimezone(dt.timezone.utc).replace(tzinfo=None)


def _month_bounds_utc(now_local: dt.datetime | None = None) -> tuple[dt.datetime, dt.datetime]:
    now_local = now_local or _local_now()
    start_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start_local.month == 12:
        next_month = start_local.replace(year=start_local.year + 1, month=1)
    else:
        next_month = start_local.replace(month=start_local.month + 1)
    return _to_utc_naive(start_local), _to_utc_naive(next_month)


def _day_bounds_utc(now_local: dt.datetime | None = None) -> tuple[dt.datetime, dt.datetime]:
    now_local = now_local or _local_now()
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + dt.timedelta(days=1)
    return _to_utc_naive(start_local), _to_utc_naive(end_local)


def summary(session) -> dict:
    """Top-level KPIs for the CEO/dashboard summary."""
    month_start, month_end = _month_bounds_utc()

    # Monthly revenue = value of opportunities marked Won this month
    monthly_revenue = session.scalar(
        select(func.coalesce(func.sum(Opportunity.value), 0.0)).where(
            Opportunity.stage == "Won",
            Opportunity.updated_at >= month_start,
            Opportunity.updated_at < month_end,
        )
    ) or 0.0

    pipeline_value = session.scalar(
        select(func.coalesce(func.sum(Opportunity.value), 0.0)).where(
            Opportunity.stage.in_(OPEN_STAGES)
        )
    ) or 0.0

    weighted_pipeline = session.scalar(
        select(
            func.coalesce(func.sum(Opportunity.value * Opportunity.probability / 100.0), 0.0)
        ).where(Opportunity.stage.in_(OPEN_STAGES))
    ) or 0.0

    hot_count = session.scalar(
        select(func.count(Opportunity.id)).where(
            Opportunity.is_hot.is_(True), Opportunity.stage.in_(OPEN_STAGES)
        )
    ) or 0

    proposals_pending = session.scalar(
        select(func.count(Opportunity.id)).where(Opportunity.stage == "Proposal")
    ) or 0

    expected_closing = session.scalar(
        select(func.coalesce(func.sum(Opportunity.value), 0.0)).where(
            Opportunity.stage.in_(OPEN_STAGES),
            Opportunity.expected_close_date.is_not(None),
            Opportunity.expected_close_date >= month_start,
            Opportunity.expected_close_date < month_end,
        )
    ) or 0.0

    open_count = session.scalar(
        select(func.count(Opportunity.id)).where(Opportunity.stage.in_(OPEN_STAGES))
    ) or 0

    return {
        "monthly_revenue": float(monthly_revenue),
        "pipeline_value": float(pipeline_value),
        "weighted_pipeline": float(weighted_pipeline),
        "hot_count": int(hot_count),
        "proposals_pending": int(proposals_pending),
        "expected_closing": float(expected_closing),
        "open_count": int(open_count),
        "month_label": _local_now().strftime("%B %Y"),
    }


def pipeline_by_stage(session) -> list[dict]:
    rows = session.execute(
        select(
            Opportunity.stage,
            func.count(Opportunity.id),
            func.coalesce(func.sum(Opportunity.value), 0.0),
        ).group_by(Opportunity.stage)
    ).all()
    data = {stage: {"count": 0, "value": 0.0} for stage in OPEN_STAGES}
    for stage, count, value in rows:
        if stage in data:
            data[stage] = {"count": int(count), "value": float(value)}
    return [{"stage": s, **data[s]} for s in OPEN_STAGES]


def value_by_zone(session) -> list[dict]:
    rows = session.execute(
        select(Account.zone, func.coalesce(func.sum(Opportunity.value), 0.0))
        .join(Opportunity, Opportunity.account_id == Account.id)
        .where(Opportunity.stage.in_(OPEN_STAGES))
        .group_by(Account.zone)
        .order_by(func.sum(Opportunity.value).desc())
    ).all()
    return [{"zone": (z or "Unspecified"), "value": float(v)} for z, v in rows]


def meetings_today(session) -> list[Reminder]:
    start, end = _day_bounds_utc()
    return list(
        session.scalars(
            select(Reminder)
            .where(Reminder.due_at >= start, Reminder.due_at < end, Reminder.done.is_(False))
            .order_by(Reminder.due_at)
        )
    )


def followups_due(session, include_overdue: bool = True) -> list[Reminder]:
    _, end = _day_bounds_utc()
    stmt = select(Reminder).where(Reminder.done.is_(False))
    if include_overdue:
        stmt = stmt.where(Reminder.due_at < end)
    stmt = stmt.order_by(Reminder.due_at)
    return list(session.scalars(stmt))


def hot_opportunities(session, limit: int = 10) -> list[Opportunity]:
    return list(
        session.scalars(
            select(Opportunity)
            .where(Opportunity.is_hot.is_(True), Opportunity.stage.in_(OPEN_STAGES))
            .order_by(Opportunity.value.desc())
            .limit(limit)
        )
    )


def proposals_pending(session, limit: int = 20) -> list[Opportunity]:
    return list(
        session.scalars(
            select(Opportunity)
            .where(Opportunity.stage == "Proposal")
            .order_by(Opportunity.value.desc())
            .limit(limit)
        )
    )


def new_leads(session, limit: int = 20) -> list[Opportunity]:
    return list(
        session.scalars(
            select(Opportunity)
            .where(Opportunity.stage == "New")
            .order_by(Opportunity.created_at.desc())
            .limit(limit)
        )
    )


# --------------------------------------------------------------------------- #
# Alert scanning (used by scheduler)
# --------------------------------------------------------------------------- #
def scan_alerts(session) -> list[dict]:
    """Return a list of alert dicts: {key, kind, opportunity, message}."""
    now = utcnow()
    alerts: list[dict] = []

    # 1. Proposal with no follow-up after 3 days
    proposal_cutoff = now - dt.timedelta(days=HOT_FOLLOWUP_DAYS)
    for opp in session.scalars(select(Opportunity).where(Opportunity.stage == "Proposal")):
        ref = opp.proposal_sent_at or opp.updated_at
        if ref and ref <= proposal_cutoff and opp.last_activity_at <= proposal_cutoff:
            alerts.append({
                "key": f"proposal_nofollow:{opp.id}:{ref.date()}",
                "kind": "proposal_no_followup",
                "opportunity": opp,
                "message": (
                    f"⚠️ Proposal with no follow-up >{HOT_FOLLOWUP_DAYS}d: "
                    f"{opp.account.name} — {opp.title} ({opp.currency}{opp.value:,.0f})"
                ),
            })

    # 2. Deal idle for more than 7 days
    idle_cutoff = now - dt.timedelta(days=IDLE_DAYS)
    for opp in session.scalars(
        select(Opportunity).where(Opportunity.stage.in_(OPEN_STAGES))
    ):
        if opp.last_activity_at <= idle_cutoff:
            alerts.append({
                "key": f"idle:{opp.id}:{opp.last_activity_at.date()}",
                "kind": "idle",
                "opportunity": opp,
                "message": (
                    f"💤 Idle >{IDLE_DAYS}d: {opp.account.name} — {opp.title} "
                    f"(stage {opp.stage}, last activity {opp.last_activity_at.date()})"
                ),
            })

    # 3. Closing date within 5 days
    soon = now + dt.timedelta(days=CLOSING_SOON_DAYS)
    for opp in session.scalars(
        select(Opportunity).where(
            Opportunity.stage.in_(OPEN_STAGES),
            Opportunity.expected_close_date.is_not(None),
            Opportunity.expected_close_date <= soon,
        )
    ):
        alerts.append({
            "key": f"closing:{opp.id}:{opp.expected_close_date.date()}",
            "kind": "closing_soon",
            "opportunity": opp,
            "message": (
                f"⏰ Closing within {CLOSING_SOON_DAYS}d: {opp.account.name} — {opp.title} "
                f"(expected {opp.expected_close_date.date()}, {opp.currency}{opp.value:,.0f})"
            ),
        })

    return alerts
