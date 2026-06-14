"""Database engine and session management (shared by web app and bot worker)."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker

from config import config


class Base(DeclarativeBase):
    pass


def _make_engine():
    url = config.DATABASE_URL
    connect_args = {}
    if url.startswith("sqlite"):
        # Allow usage across threads (Flask + scheduler) for SQLite.
        connect_args = {"check_same_thread": False}
    return create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)


engine = _make_engine()

# scoped_session gives one session per thread; safe for Flask request handlers
# and for the bot/scheduler threads.
SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
)


def init_db() -> None:
    """Create all tables. Import models first so they register on Base."""
    from app import models  # noqa: F401  (ensures models are imported)

    Base.metadata.create_all(bind=engine)


def get_session():
    """Return the thread-local session."""
    return SessionLocal()
