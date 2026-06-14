"""Build the text bodies for Telegram messages from CRM data."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from app.models import Account, Opportunity, Reminder
from app.services import crm, metrics
from config import config

TZ = ZoneInfo(config.TIMEZONE)


def _money(value: float, currency: str = "RM") -> str:
    return f"{currency}{value:,.0f}"


def _local(value: dt.datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(TZ).strftime("%d %b %H:%M")


def summary_text(session) -> str:
    s = metrics.summary(session)
    lines = [
        f"<b>📊 A2 CEO Summary — {s['month_label']}</b>",
        "",
        f"💰 Monthly revenue (Won): <b>{_money(s['monthly_revenue'])}</b>",
        f"📈 Pipeline value (open): <b>{_money(s['pipeline_value'])}</b>",
        f"⚖️ Weighted pipeline: {_money(s['weighted_pipeline'])}",
        f"🔥 Hot opportunities: <b>{s['hot_count']}</b>",
        f"📝 Proposals pending: <b>{s['proposals_pending']}</b>",
        f"🎯 Expected closing this month: <b>{_money(s['expected_closing'])}</b>",
        f"📂 Open deals: {s['open_count']}",
    ]
    return "\n".join(lines)


def _reminder_line(r: Reminder) -> str:
    where = f" — {r.account.name}" if r.account else ""
    return f"• {_local(r.due_at)}{where}: {r.text}"


def today_text(session) -> str:
    meetings = metrics.meetings_today(session)
    follow = metrics.followups_due(session)
    lines = [f"<b>🗓 Today — {dt.datetime.now(TZ):%A %d %b %Y}</b>", ""]
    lines.append("<b>Meetings / scheduled today:</b>")
    lines += [_reminder_line(r) for r in meetings] or ["• none"]
    lines.append("")
    lines.append("<b>Follow-ups due (incl. overdue):</b>")
    lines += [_reminder_line(r) for r in follow] or ["• none"]
    return "\n".join(lines)


def followup_text(session) -> str:
    follow = metrics.followups_due(session)
    lines = ["<b>📌 Follow-ups due</b>", ""]
    lines += [_reminder_line(r) for r in follow] or ["• Nothing due. 🎉"]
    return "\n".join(lines)


def _opp_line(o: Opportunity) -> str:
    flag = "🔥 " if o.is_hot else ""
    return f"• {flag}{o.account.name} — {o.title} ({_money(o.value, o.currency)}, {o.stage})"


def hot_text(session) -> str:
    hot = metrics.hot_opportunities(session)
    lines = ["<b>🔥 Hot opportunities</b>", ""]
    lines += [_opp_line(o) for o in hot] or ["• none flagged hot"]
    return "\n".join(lines)


def leads_text(session) -> str:
    leads = metrics.new_leads(session)
    lines = ["<b>🆕 New leads to contact</b>", ""]
    lines += [_opp_line(o) for o in leads] or ["• none"]
    return "\n".join(lines)


def pipeline_text(session) -> str:
    rows = metrics.pipeline_by_stage(session)
    total = sum(r["value"] for r in rows)
    lines = ["<b>📈 Pipeline by stage</b>", ""]
    for r in rows:
        lines.append(f"• {r['stage']}: {r['count']} deals — {_money(r['value'])}")
    lines.append("")
    lines.append(f"<b>Total open: {_money(total)}</b>")
    return "\n".join(lines)


def proposals_text(session) -> str:
    props = metrics.proposals_pending(session)
    lines = ["<b>📝 Proposals pending</b>", ""]
    lines += [_opp_line(o) for o in props] or ["• none"]
    return "\n".join(lines)


def account_detail_text(session, account: Account) -> str:
    opp = crm.primary_opportunity(session, account)
    lines = [f"<b>🏢 {account.name}</b>"]
    if account.zone:
        lines.append(f"📍 {account.zone}" + (f" — {account.location}" if account.location else ""))
    if account.contact_name or account.contact_phone:
        lines.append(f"👤 {account.contact_name} {account.contact_phone}".strip())
    if account.industry:
        lines.append(f"🏭 {account.industry}")
    lines.append("")
    if opp:
        lines.append(f"<b>Deal:</b> {opp.title}")
        lines.append(f"Stage: <b>{opp.stage}</b> | Value: {_money(opp.value, opp.currency)} | Prob: {opp.probability}%")
        if opp.expected_close_date:
            lines.append(f"Expected close: {opp.expected_close_date.date()}")
        last = sorted(opp.activities, key=lambda a: a.created_at, reverse=True)
        if last:
            lines.append(f"Last activity: {_local(last[0].created_at)} — {last[0].note[:120]}")
        nxt = _next_action(session, account, opp)
        if nxt:
            lines.append(f"⏭ Next action: {nxt}")
    else:
        lines.append("No opportunity yet for this account.")
    return "\n".join(lines)


def _next_action(session, account, opp) -> str:
    from sqlalchemy import select
    from app.models import Reminder

    rem = session.scalars(
        select(Reminder)
        .where(Reminder.account_id == account.id, Reminder.done.is_(False))
        .order_by(Reminder.due_at)
    ).first()
    if rem:
        return f"{rem.text} ({_local(rem.due_at)})"
    return ""


def morning_report_text(session) -> str:
    s = metrics.summary(session)
    meetings = metrics.meetings_today(session)
    follow = metrics.followups_due(session)
    hot = metrics.hot_opportunities(session, limit=5)
    leads = metrics.new_leads(session, limit=5)
    props = metrics.proposals_pending(session, limit=5)

    lines = [
        f"<b>☀️ Good morning! A2 Daily Report — {dt.datetime.now(TZ):%A %d %b %Y}</b>",
        "",
        f"💰 Revenue MTD: {_money(s['monthly_revenue'])} | 📈 Pipeline: {_money(s['pipeline_value'])}",
        "",
        "<b>🗓 Today's meetings:</b>",
    ]
    lines += [_reminder_line(r) for r in meetings] or ["• none"]
    lines += ["", "<b>📌 Follow-ups due:</b>"]
    lines += [_reminder_line(r) for r in follow] or ["• none"]
    lines += ["", "<b>🔥 Hot deals:</b>"]
    lines += [_opp_line(o) for o in hot] or ["• none"]
    lines += ["", "<b>🆕 New leads to contact:</b>"]
    lines += [_opp_line(o) for o in leads] or ["• none"]
    lines += ["", "<b>📝 Proposal deadlines / pending:</b>"]
    lines += [_opp_line(o) for o in props] or ["• none"]
    return "\n".join(lines)


HELP_TEXT = (
    "<b>🤖 A2 Sales Assistant — Commands</b>\n\n"
    "/summary — CEO summary\n"
    "/today — today's meetings & follow-ups\n"
    "/leads — new leads to contact\n"
    "/hot — hot opportunities\n"
    "/pipeline — pipeline by stage\n"
    "/followup — follow-ups due\n"
    "/report — full morning report now\n"
    "/addlead — <i>ABC Factory, Johor, CCTV upgrade, contact Mr Tan, value RM80k</i>\n"
    "/addnote — <i>ABC Factory: need 64 CCTV, budget RM120k, decide July</i>\n"
    "/search — <i>ABC Factory</i>\n"
    "/update — <i>ABC Factory to proposal</i>\n"
    "/remind — <i>call ABC Factory next Monday 10am</i>\n\n"
    "You can also just type naturally, e.g.\n"
    "“New lead: ABC Factory, Johor, CCTV upgrade, contact Mr Tan, value RM80k”\n"
    "“Update ABC Factory to proposal stage”\n"
    "“Meeting note ABC Factory: they need access control, budget RM120k”\n"
    "🎤 Send a voice note and it's saved as a meeting note (transcribed if enabled)."
)
