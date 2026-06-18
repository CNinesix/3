"""Load realistic sample data for A2 Automation (Johor Bahru pipeline).

Run with:  python manage.py seed
Safe to run on an empty DB; skips if accounts already exist.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import Account, Activity, Opportunity, Reminder, User, utcnow
from config import config


def _days(n: int) -> dt.datetime:
    return utcnow() + dt.timedelta(days=n)


SAMPLE_ACCOUNTS = [
    # name, industry, zone, contact, phone, opp_title, stage, value, prob, hot, close_in_days
    ("STACK Infrastructure (Johor)", "Data Centre", "Iskandar Puteri", "Construction Lead", "+60 7-000 0001",
     "Campus-wide AI CCTV + access control package", "Proposal", 1850000, 55, True, 20),
    ("AirTrunk JHB1", "Data Centre", "Sedenak / Kulai", "Project Procurement", "+60 7-000 0002",
     "Perimeter intrusion analytics + ANPR gates", "Meeting", 1200000, 35, True, 45),
    ("YTL Green Data Center Park", "Data Centre", "Sedenak / Kulai", "DC Project Director", "+60 7-000 0003",
     "Phase 1 surveillance & BMS integration", "Qualified", 2400000, 25, True, 70),
    ("AME Elite Consortium", "Developer / Contractor", "Senai / Airport City", "Projects Manager", "+60 7-000 0004",
     "Preferred-vendor smart-security framework (i-Park)", "Negotiation", 680000, 60, False, 15),
    ("Eco Business Park (EcoWorld)", "Developer / Contractor", "Senai / Airport City", "Estate Manager", "+60 7-000 0005",
     "Estate-wide ANPR + command centre", "Proposal", 540000, 50, False, 25),
    ("Megapower M&E Consultants", "M&E Consultant", "JB City", "Senior Partner", "+60 7-000 0006",
     "Get specified as preferred ELV/security vendor", "Qualified", 0, 20, False, None),
    ("Pasir Gudang Petrochem Plant", "Manufacturer", "Pasir Gudang / Tg Langsat", "HSE Manager", "+60 7-000 0007",
     "PPE/safety-zone AI detection + truck ANPR", "Meeting", 420000, 40, True, 35),
    ("Senai E&E Manufacturer", "Manufacturer", "Senai / Airport City", "Facilities Manager", "+60 7-000 0008",
     "Cleanroom access control + line monitoring CCTV", "New", 310000, 10, False, None),
    ("JB City Mall (FM operator)", "Facilities Manager", "JB City", "Operations Manager", "+60 7-000 0009",
     "Retrofit existing CCTV to AI loss-prevention analytics", "Proposal", 260000, 45, False, 18),
    ("Tebrau Logistics Hub", "Developer / Contractor", "Tebrau / Plentong", "Site Manager", "+60 7-000 0010",
     "Warehouse perimeter + visitor management", "Won", 195000, 100, False, -5),
    ("Kulai Cold Chain Facility", "Manufacturer", "Sedenak / Kulai", "Plant Manager", "+60 7-000 0011",
     "Access control + cold-store temperature alerting", "New", 145000, 10, False, None),
    ("Iskandar Mixed-Use Tower", "Developer / Contractor", "Iskandar Puteri", "Development Director", "+60 7-000 0012",
     "Building-wide IP CCTV, ANPR car park, turnstiles", "Negotiation", 920000, 65, True, 12),
]


def seed() -> None:
    init_db()
    session = SessionLocal()
    try:
        if session.scalars(select(Account)).first():
            print("ℹ️  Accounts already present; skipping sample data.")
            return

        admin = session.scalars(select(User).where(User.email == config.ADMIN_EMAIL.lower())).first()
        owner_id = admin.id if admin else None

        created = 0
        for (name, industry, zone, contact, phone, title, stage, value, prob, hot, close_in) in SAMPLE_ACCOUNTS:
            account = Account(
                name=name, industry=industry, zone=zone,
                contact_name=contact, contact_phone=phone, owner_id=owner_id,
            )
            session.add(account)
            session.flush()

            opp = Opportunity(
                account_id=account.id, title=title, stage=stage, value=float(value),
                probability=prob, is_hot=hot, owner_id=owner_id,
                expected_close_date=_days(close_in) if close_in is not None else None,
                last_activity_at=utcnow() - dt.timedelta(days=2),
            )
            if stage == "Proposal":
                opp.proposal_sent_at = utcnow() - dt.timedelta(days=4)
            session.add(opp)
            session.flush()

            session.add(Activity(
                account_id=account.id, opportunity_id=opp.id, type="note",
                note=f"Initial qualification for {title}.",
                created_by="seed", source="web",
            ))
            created += 1

        # A couple of reminders (today + upcoming) so the dashboard/bot show data.
        first_account = session.scalars(select(Account).order_by(Account.id)).first()
        session.add(Reminder(
            user_id=owner_id, account_id=first_account.id if first_account else None,
            text="Call to confirm site walk for STACK campus proposal",
            due_at=utcnow().replace(hour=2, minute=0, second=0, microsecond=0),  # ~10:00 MYT
        ))
        session.add(Reminder(
            user_id=owner_id,
            text="Send revised quote to AME Elite", due_at=_days(1),
        ))
        session.commit()
        print(f"✅ Seeded {created} accounts with opportunities, activities and reminders.")
    finally:
        SessionLocal.remove()


if __name__ == "__main__":
    seed()
