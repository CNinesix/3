"""SQLAlchemy ORM models for A2 ROS."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import Base

# Pipeline stages in order. "Won"/"Lost" are terminal.
STAGES = [
    "New",
    "Qualified",
    "Meeting",
    "Proposal",
    "Negotiation",
    "Won",
    "Lost",
]
OPEN_STAGES = ["New", "Qualified", "Meeting", "Proposal", "Negotiation"]


def utcnow() -> dt.datetime:
    """Naive UTC timestamp. All stored datetimes use naive UTC for consistency."""
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")  # admin|user
    telegram_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    accounts: Mapped[list["Account"]] = relationship(back_populates="owner")

    # --- password helpers ---
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # --- Flask-Login interface ---
    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_id(self) -> str:
        return str(self.id)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class Account(Base):
    """A customer / company in the pipeline."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    industry: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    zone: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    location: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    contact_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    contact_email: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    owner: Mapped[Optional[User]] = relationship(back_populates="accounts")
    opportunities: Mapped[list["Opportunity"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class Opportunity(Base):
    """A deal / sales opportunity attached to an account."""

    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    stage: Mapped[str] = mapped_column(String(40), default="New", nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="RM", nullable=False)
    probability: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0-100
    expected_close_date: Mapped[Optional[dt.date]] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_hot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
    last_activity_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    # Timestamp when stage entered "Proposal" — used for the 3-day no-follow-up alert.
    proposal_sent_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)

    account: Mapped[Account] = relationship(back_populates="opportunities")
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )

    @property
    def is_open(self) -> bool:
        return self.stage in OPEN_STAGES

    @property
    def weighted_value(self) -> float:
        return round(self.value * (self.probability or 0) / 100.0, 2)


class Activity(Base):
    """A logged interaction: note, meeting note, call, stage change, voice note."""

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("opportunities.id"), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(String(30), default="note", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="web", nullable=False)  # web|telegram
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    account: Mapped[Optional[Account]] = relationship(back_populates="activities")
    opportunity: Mapped[Optional[Opportunity]] = relationship(back_populates="activities")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(ForeignKey("opportunities.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    account: Mapped[Optional[Account]] = relationship()
    opportunity: Mapped[Optional[Opportunity]] = relationship()


class TelegramLog(Base):
    __tablename__ = "telegram_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    command: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    response_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class SentAlert(Base):
    """Tracks proactive alerts already sent, to avoid duplicates."""

    __tablename__ = "sent_alerts"
    __table_args__ = (UniqueConstraint("alert_key", name="uq_sent_alert_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Setting(Base):
    """Simple key/value store for runtime-editable settings."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # default keys: daily_report_enabled, alerts_enabled, extra_telegram_ids
