"""Management CLI for A2 ROS.

Usage:
    python manage.py init-db          # create tables + bootstrap admin + defaults
    python manage.py create-admin     # (re)create/update the admin from .env
    python manage.py seed             # load sample data (idempotent-ish)
    python manage.py set-telegram <user_id>   # set admin's Telegram ID
    python manage.py reset-password <email> <password>
"""
from __future__ import annotations

import sys

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import User
from app.services import settings as settings_svc
from config import config


def cmd_init_db() -> int:
    init_db()
    session = SessionLocal()
    try:
        settings_svc.ensure_defaults(session)
        _ensure_admin(session)
    finally:
        SessionLocal.remove()
    print("✅ Database initialised.")
    print(f"   Admin login: {config.ADMIN_EMAIL}")
    return 0


def _ensure_admin(session) -> None:
    admin = session.scalars(select(User).where(User.email == config.ADMIN_EMAIL.lower())).first()
    if admin is None:
        admin = User(email=config.ADMIN_EMAIL.lower(), name=config.ADMIN_NAME, role="admin")
        admin.set_password(config.ADMIN_PASSWORD)
        session.add(admin)
        session.commit()
        print(f"   Created admin user {config.ADMIN_EMAIL}")
    else:
        print(f"   Admin {config.ADMIN_EMAIL} already exists (left unchanged).")


def cmd_create_admin() -> int:
    init_db()
    session = SessionLocal()
    try:
        admin = session.scalars(select(User).where(User.email == config.ADMIN_EMAIL.lower())).first()
        if admin is None:
            admin = User(email=config.ADMIN_EMAIL.lower(), name=config.ADMIN_NAME, role="admin")
            session.add(admin)
        admin.role = "admin"
        admin.is_active = True
        admin.set_password(config.ADMIN_PASSWORD)
        session.commit()
        print(f"✅ Admin {config.ADMIN_EMAIL} created/updated.")
    finally:
        SessionLocal.remove()
    return 0


def cmd_reset_password(email: str, password: str) -> int:
    session = SessionLocal()
    try:
        user = session.scalars(select(User).where(User.email == email.lower())).first()
        if not user:
            print(f"❌ No user with email {email}")
            return 1
        user.set_password(password)
        session.commit()
        print(f"✅ Password updated for {email}")
    finally:
        SessionLocal.remove()
    return 0


def cmd_set_telegram(user_id: str) -> int:
    if not user_id.isdigit():
        print("❌ Telegram user id must be numeric")
        return 1
    session = SessionLocal()
    try:
        admin = session.scalars(select(User).where(User.email == config.ADMIN_EMAIL.lower())).first()
        if not admin:
            print("❌ Admin not found; run init-db first")
            return 1
        admin.telegram_user_id = int(user_id)
        session.commit()
        print(f"✅ Admin Telegram ID set to {user_id}")
    finally:
        SessionLocal.remove()
    return 0


def cmd_seed() -> int:
    from scripts.seed import seed

    init_db()
    seed()
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    cmd, *rest = argv
    if cmd == "init-db":
        return cmd_init_db()
    if cmd == "create-admin":
        return cmd_create_admin()
    if cmd == "seed":
        return cmd_seed()
    if cmd == "set-telegram" and rest:
        return cmd_set_telegram(rest[0])
    if cmd == "reset-password" and len(rest) >= 2:
        return cmd_reset_password(rest[0], rest[1])
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
