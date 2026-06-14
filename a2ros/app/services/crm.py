"""CRM operations shared by the web dashboard and the Telegram bot."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import func, or_, select

from app.models import (
    Account,
    Activity,
    OPEN_STAGES,
    Opportunity,
    Reminder,
    User,
    utcnow,
)


# --------------------------------------------------------------------------- #
# Lookups
# --------------------------------------------------------------------------- #
def find_account(session, name: str) -> Optional[Account]:
    """Find an account by (case-insensitive) exact then partial name match."""
    if not name:
        return None
    name = name.strip()
    exact = session.scalars(
        select(Account).where(func.lower(Account.name) == name.lower())
    ).first()
    if exact:
        return exact
    partial = session.scalars(
        select(Account).where(Account.name.ilike(f"%{name}%")).order_by(Account.name)
    ).first()
    return partial


def search_accounts(session, query: str, limit: int = 10) -> list[Account]:
    q = f"%{query.strip()}%"
    return list(
        session.scalars(
            select(Account)
            .where(or_(Account.name.ilike(q), Account.contact_name.ilike(q), Account.location.ilike(q)))
            .order_by(Account.name)
            .limit(limit)
        )
    )


def primary_opportunity(session, account: Account) -> Optional[Opportunity]:
    """The most relevant open opportunity for an account (latest open, else latest)."""
    opp = session.scalars(
        select(Opportunity)
        .where(Opportunity.account_id == account.id, Opportunity.stage.in_(OPEN_STAGES))
        .order_by(Opportunity.updated_at.desc())
    ).first()
    if opp:
        return opp
    return session.scalars(
        select(Opportunity)
        .where(Opportunity.account_id == account.id)
        .order_by(Opportunity.updated_at.desc())
    ).first()


# --------------------------------------------------------------------------- #
# Mutations
# --------------------------------------------------------------------------- #
def create_lead(
    session,
    *,
    name: str,
    title: str = "New opportunity",
    zone: str = "",
    contact_name: str = "",
    contact_phone: str = "",
    value: float | None = None,
    description: str = "",
    owner_id: int | None = None,
    created_by: str = "",
    source: str = "web",
) -> tuple[Account, Opportunity]:
    """Create (or reuse) an account and attach a new opportunity."""
    account = find_account(session, name)
    if account is None:
        account = Account(
            name=name.strip() or "Unnamed",
            zone=zone or "",
            contact_name=contact_name or "",
            contact_phone=contact_phone or "",
            owner_id=owner_id,
        )
        session.add(account)
        session.flush()
    else:
        # enrich existing account with any new contact info
        if contact_name and not account.contact_name:
            account.contact_name = contact_name
        if contact_phone and not account.contact_phone:
            account.contact_phone = contact_phone
        if zone and not account.zone:
            account.zone = zone

    opp = Opportunity(
        account_id=account.id,
        title=title or "New opportunity",
        description=description or "",
        stage="New",
        value=value or 0.0,
        owner_id=owner_id,
        last_activity_at=utcnow(),
    )
    session.add(opp)
    session.flush()

    log_activity(
        session,
        account=account,
        opportunity=opp,
        type="note",
        note=f"Lead created: {title}" + (f" (value RM{value:,.0f})" if value else ""),
        created_by=created_by,
        source=source,
        commit=False,
    )
    session.commit()
    return account, opp


def update_stage(
    session,
    *,
    account_name: str,
    stage: str,
    created_by: str = "",
    source: str = "web",
) -> Optional[Opportunity]:
    account = find_account(session, account_name)
    if account is None:
        return None
    opp = primary_opportunity(session, account)
    if opp is None:
        opp = Opportunity(account_id=account.id, title="Opportunity", stage="New")
        session.add(opp)
        session.flush()
    old = opp.stage
    set_stage(session, opp, stage, created_by=created_by, source=source, commit=True)
    return opp


def set_stage(session, opp: Opportunity, stage: str, *, created_by="", source="web", commit=True):
    old = opp.stage
    opp.stage = stage
    opp.updated_at = utcnow()
    opp.last_activity_at = utcnow()
    if stage == "Proposal" and opp.proposal_sent_at is None:
        opp.proposal_sent_at = utcnow()
    if stage == "Won":
        opp.probability = 100
    elif stage == "Lost":
        opp.probability = 0
    log_activity(
        session,
        account=opp.account,
        opportunity=opp,
        type="stage_change",
        note=f"Stage changed: {old} -> {stage}",
        created_by=created_by,
        source=source,
        commit=False,
    )
    if commit:
        session.commit()


def log_activity(
    session,
    *,
    account: Account | None,
    opportunity: Opportunity | None,
    type: str,
    note: str,
    created_by: str = "",
    source: str = "web",
    commit: bool = True,
) -> Activity:
    act = Activity(
        account_id=account.id if account else None,
        opportunity_id=opportunity.id if opportunity else None,
        type=type,
        note=note,
        created_by=created_by,
        source=source,
    )
    session.add(act)
    if opportunity is not None:
        opportunity.last_activity_at = utcnow()
    if commit:
        session.commit()
    return act


def add_note(
    session,
    *,
    account_name: str,
    note: str,
    type: str = "meeting_note",
    created_by: str = "",
    source: str = "web",
) -> Optional[Activity]:
    account = find_account(session, account_name)
    if account is None:
        return None
    opp = primary_opportunity(session, account)
    return log_activity(
        session,
        account=account,
        opportunity=opp,
        type=type,
        note=note,
        created_by=created_by,
        source=source,
        commit=True,
    )


def add_reminder(
    session,
    *,
    text: str,
    due_at: dt.datetime,
    user_id: int | None = None,
    account_name: str | None = None,
) -> Reminder:
    account = find_account(session, account_name) if account_name else None
    opp = primary_opportunity(session, account) if account else None
    reminder = Reminder(
        user_id=user_id,
        account_id=account.id if account else None,
        opportunity_id=opp.id if opp else None,
        text=text,
        due_at=due_at.astimezone(dt.timezone.utc).replace(tzinfo=None)
        if due_at.tzinfo
        else due_at,
    )
    session.add(reminder)
    session.commit()
    return reminder
