"""Dashboard, CRM, Telegram-control, settings and admin routes."""
from __future__ import annotations

import datetime as dt
import functools
import json

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import desc, select

from app.db import SessionLocal
from app.models import (
    STAGES,
    Account,
    Activity,
    Opportunity,
    Reminder,
    TelegramLog,
    User,
    utcnow,
)
from app.services import crm, metrics
from app.services import settings as settings_svc
from app.telegram.client import TelegramClient
from config import config

bp = Blueprint("web", __name__)


def admin_required(view):
    @functools.wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def _parse_date(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def _parse_float(value: str | None) -> float:
    try:
        return float((value or "0").replace(",", "").replace("RM", "").strip() or 0)
    except ValueError:
        return 0.0


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@bp.route("/")
@login_required
def dashboard():
    s = SessionLocal()
    summary = metrics.summary(s)
    by_stage = metrics.pipeline_by_stage(s)
    by_zone = metrics.value_by_zone(s)
    return render_template(
        "dashboard.html",
        summary=summary,
        by_stage=by_stage,
        by_zone=by_zone,
        meetings=metrics.meetings_today(s),
        followups=metrics.followups_due(s),
        hot=metrics.hot_opportunities(s),
        leads=metrics.new_leads(s, limit=8),
        proposals=metrics.proposals_pending(s, limit=8),
        chart_stage=json.dumps([{"label": r["stage"], "value": r["value"], "count": r["count"]} for r in by_stage]),
        chart_zone=json.dumps([{"label": r["zone"], "value": r["value"]} for r in by_zone]),
    )


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
@bp.route("/accounts")
@login_required
def accounts():
    s = SessionLocal()
    q = (request.args.get("q") or "").strip()
    if q:
        rows = crm.search_accounts(s, q, limit=200)
    else:
        rows = list(s.scalars(select(Account).order_by(Account.name)))
    return render_template("accounts.html", accounts=rows, q=q)


@bp.route("/accounts/new", methods=["GET", "POST"])
@login_required
def account_new():
    if request.method == "POST":
        s = SessionLocal()
        account = Account(
            name=(request.form.get("name") or "").strip(),
            industry=(request.form.get("industry") or "").strip(),
            zone=(request.form.get("zone") or "").strip(),
            location=(request.form.get("location") or "").strip(),
            contact_name=(request.form.get("contact_name") or "").strip(),
            contact_phone=(request.form.get("contact_phone") or "").strip(),
            contact_email=(request.form.get("contact_email") or "").strip(),
            notes=(request.form.get("notes") or "").strip(),
            owner_id=current_user.id,
        )
        if not account.name:
            flash("Company name is required.", "danger")
            return render_template("account_form.html", account=account, stages=STAGES, new=True)
        s.add(account)
        s.commit()
        flash("Account created.", "success")
        return redirect(url_for("web.account_detail", account_id=account.id))
    return render_template("account_form.html", account=Account(), stages=STAGES, new=True)


@bp.route("/accounts/<int:account_id>")
@login_required
def account_detail(account_id: int):
    s = SessionLocal()
    account = s.get(Account, account_id)
    if not account:
        abort(404)
    activities = list(
        s.scalars(
            select(Activity).where(Activity.account_id == account_id).order_by(desc(Activity.created_at)).limit(50)
        )
    )
    reminders = list(
        s.scalars(
            select(Reminder).where(Reminder.account_id == account_id, Reminder.done.is_(False)).order_by(Reminder.due_at)
        )
    )
    return render_template(
        "account_detail.html",
        account=account,
        activities=activities,
        reminders=reminders,
        stages=STAGES,
    )


@bp.route("/accounts/<int:account_id>/edit", methods=["GET", "POST"])
@login_required
def account_edit(account_id: int):
    s = SessionLocal()
    account = s.get(Account, account_id)
    if not account:
        abort(404)
    if request.method == "POST":
        account.name = (request.form.get("name") or account.name).strip()
        account.industry = (request.form.get("industry") or "").strip()
        account.zone = (request.form.get("zone") or "").strip()
        account.location = (request.form.get("location") or "").strip()
        account.contact_name = (request.form.get("contact_name") or "").strip()
        account.contact_phone = (request.form.get("contact_phone") or "").strip()
        account.contact_email = (request.form.get("contact_email") or "").strip()
        account.notes = (request.form.get("notes") or "").strip()
        s.commit()
        flash("Account updated.", "success")
        return redirect(url_for("web.account_detail", account_id=account.id))
    return render_template("account_form.html", account=account, stages=STAGES, new=False)


@bp.route("/accounts/<int:account_id>/note", methods=["POST"])
@login_required
def account_add_note(account_id: int):
    s = SessionLocal()
    account = s.get(Account, account_id)
    if not account:
        abort(404)
    note = (request.form.get("note") or "").strip()
    note_type = request.form.get("type") or "note"
    if note:
        crm.add_note(
            s, account_name=account.name, note=note, type=note_type,
            created_by=current_user.name or current_user.email, source="web",
        )
        flash("Note added.", "success")
    return redirect(url_for("web.account_detail", account_id=account_id))


# --------------------------------------------------------------------------- #
# Opportunities
# --------------------------------------------------------------------------- #
@bp.route("/opportunities")
@login_required
def opportunities():
    s = SessionLocal()
    stage = request.args.get("stage")
    stmt = select(Opportunity).order_by(desc(Opportunity.updated_at))
    if stage in STAGES:
        stmt = select(Opportunity).where(Opportunity.stage == stage).order_by(desc(Opportunity.updated_at))
    rows = list(s.scalars(stmt))
    return render_template("opportunities.html", opportunities=rows, stages=STAGES, active_stage=stage)


@bp.route("/opportunities/new", methods=["GET", "POST"])
@login_required
def opportunity_new():
    s = SessionLocal()
    if request.method == "POST":
        account_id = request.form.get("account_id")
        account = s.get(Account, int(account_id)) if account_id else None
        if not account:
            flash("Select a valid account.", "danger")
            return redirect(url_for("web.opportunities"))
        opp = Opportunity(
            account_id=account.id,
            title=(request.form.get("title") or "Opportunity").strip(),
            description=(request.form.get("description") or "").strip(),
            stage=request.form.get("stage") if request.form.get("stage") in STAGES else "New",
            value=_parse_float(request.form.get("value")),
            probability=int(request.form.get("probability") or 0),
            expected_close_date=_parse_date(request.form.get("expected_close_date")),
            is_hot=bool(request.form.get("is_hot")),
            owner_id=current_user.id,
            last_activity_at=utcnow(),
        )
        if opp.stage == "Proposal":
            opp.proposal_sent_at = utcnow()
        s.add(opp)
        s.commit()
        flash("Opportunity created.", "success")
        return redirect(url_for("web.opportunity_detail", opp_id=opp.id))
    accounts = list(s.scalars(select(Account).order_by(Account.name)))
    return render_template("opportunity_form.html", opp=Opportunity(), accounts=accounts, stages=STAGES, new=True)


@bp.route("/opportunities/<int:opp_id>")
@login_required
def opportunity_detail(opp_id: int):
    s = SessionLocal()
    opp = s.get(Opportunity, opp_id)
    if not opp:
        abort(404)
    activities = list(
        s.scalars(select(Activity).where(Activity.opportunity_id == opp_id).order_by(desc(Activity.created_at)))
    )
    return render_template("opportunity_detail.html", opp=opp, activities=activities, stages=STAGES)


@bp.route("/opportunities/<int:opp_id>/edit", methods=["GET", "POST"])
@login_required
def opportunity_edit(opp_id: int):
    s = SessionLocal()
    opp = s.get(Opportunity, opp_id)
    if not opp:
        abort(404)
    if request.method == "POST":
        opp.title = (request.form.get("title") or opp.title).strip()
        opp.description = (request.form.get("description") or "").strip()
        opp.value = _parse_float(request.form.get("value"))
        opp.probability = int(request.form.get("probability") or 0)
        opp.expected_close_date = _parse_date(request.form.get("expected_close_date"))
        opp.is_hot = bool(request.form.get("is_hot"))
        new_stage = request.form.get("stage")
        if new_stage in STAGES and new_stage != opp.stage:
            crm.set_stage(s, opp, new_stage, created_by=current_user.name or current_user.email, source="web", commit=False)
        opp.updated_at = utcnow()
        s.commit()
        flash("Opportunity updated.", "success")
        return redirect(url_for("web.opportunity_detail", opp_id=opp.id))
    accounts = list(s.scalars(select(Account).order_by(Account.name)))
    return render_template("opportunity_form.html", opp=opp, accounts=accounts, stages=STAGES, new=False)


@bp.route("/opportunities/<int:opp_id>/stage", methods=["POST"])
@login_required
def opportunity_stage(opp_id: int):
    s = SessionLocal()
    opp = s.get(Opportunity, opp_id)
    if not opp:
        abort(404)
    stage = request.form.get("stage")
    if stage in STAGES:
        crm.set_stage(s, opp, stage, created_by=current_user.name or current_user.email, source="web")
        flash(f"Stage updated to {stage}.", "success")
    return redirect(request.referrer or url_for("web.opportunity_detail", opp_id=opp_id))


# --------------------------------------------------------------------------- #
# Reminders
# --------------------------------------------------------------------------- #
@bp.route("/reminders", methods=["GET", "POST"])
@login_required
def reminders():
    s = SessionLocal()
    if request.method == "POST":
        text = (request.form.get("text") or "").strip()
        due_raw = request.form.get("due_at")
        account_id = request.form.get("account_id")
        if text and due_raw:
            try:
                due_local = dt.datetime.strptime(due_raw, "%Y-%m-%dT%H:%M")
            except ValueError:
                due_local = None
            if due_local:
                from zoneinfo import ZoneInfo

                tz = ZoneInfo(config.TIMEZONE)
                due_utc = due_local.replace(tzinfo=tz).astimezone(dt.timezone.utc).replace(tzinfo=None)
                reminder = Reminder(
                    text=text,
                    due_at=due_utc,
                    user_id=current_user.id,
                    account_id=int(account_id) if account_id else None,
                )
                s.add(reminder)
                s.commit()
                flash("Reminder created.", "success")
        return redirect(url_for("web.reminders"))

    pending = list(s.scalars(select(Reminder).where(Reminder.done.is_(False)).order_by(Reminder.due_at)))
    done = list(s.scalars(select(Reminder).where(Reminder.done.is_(True)).order_by(desc(Reminder.due_at)).limit(30)))
    accounts = list(s.scalars(select(Account).order_by(Account.name)))
    return render_template("reminders.html", pending=pending, done=done, accounts=accounts)


@bp.route("/reminders/<int:reminder_id>/done", methods=["POST"])
@login_required
def reminder_done(reminder_id: int):
    s = SessionLocal()
    reminder = s.get(Reminder, reminder_id)
    if reminder:
        reminder.done = True
        s.commit()
        flash("Reminder marked done.", "success")
    return redirect(url_for("web.reminders"))


# --------------------------------------------------------------------------- #
# Telegram control page
# --------------------------------------------------------------------------- #
@bp.route("/telegram", methods=["GET", "POST"])
@login_required
def telegram_page():
    s = SessionLocal()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "settings":
            settings_svc.set_value(s, "daily_report_enabled", "true" if request.form.get("daily_report_enabled") else "false")
            settings_svc.set_value(s, "alerts_enabled", "true" if request.form.get("alerts_enabled") else "false")
            settings_svc.set_value(s, "extra_telegram_ids", (request.form.get("extra_telegram_ids") or "").strip())
            flash("Telegram settings saved.", "success")
        return redirect(url_for("web.telegram_page"))

    client = TelegramClient()
    status = {"configured": client.configured, "online": False, "username": None, "error": None}
    if client.configured:
        me = client.get_me()
        if me.get("ok"):
            status["online"] = True
            status["username"] = me["result"].get("username")
        else:
            status["error"] = me.get("description", "Unreachable")

    logs = list(s.scalars(select(TelegramLog).order_by(desc(TelegramLog.created_at)).limit(50)))
    last = logs[0] if logs else None
    pending_reminders = list(s.scalars(select(Reminder).where(Reminder.done.is_(False)).order_by(Reminder.due_at).limit(20)))
    return render_template(
        "telegram.html",
        status=status,
        logs=logs,
        last=last,
        env_ids=sorted(config.TELEGRAM_ALLOWED_USER_IDS),
        extra_ids=settings_svc.get(s, "extra_telegram_ids", ""),
        daily_report_enabled=settings_svc.get_bool(s, "daily_report_enabled", True),
        alerts_enabled=settings_svc.get_bool(s, "alerts_enabled", True),
        daily_report_time=config.DAILY_REPORT_TIME,
        reminders=pending_reminders,
        transcription_enabled=config.transcription_enabled(),
    )


# --------------------------------------------------------------------------- #
# Admin: users
# --------------------------------------------------------------------------- #
@bp.route("/admin/users", methods=["GET", "POST"])
@admin_required
def admin_users():
    s = SessionLocal()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            if not email or not password:
                flash("Email and password are required.", "danger")
            elif s.scalars(select(User).where(User.email == email)).first():
                flash("A user with that email already exists.", "danger")
            else:
                user = User(
                    email=email,
                    name=(request.form.get("name") or "").strip(),
                    role="admin" if request.form.get("role") == "admin" else "user",
                    telegram_user_id=int(request.form["telegram_user_id"]) if (request.form.get("telegram_user_id") or "").isdigit() else None,
                )
                user.set_password(password)
                s.add(user)
                s.commit()
                flash("User created.", "success")
        elif action == "update":
            user = s.get(User, int(request.form.get("user_id")))
            if user:
                user.name = (request.form.get("name") or user.name).strip()
                user.role = "admin" if request.form.get("role") == "admin" else "user"
                tid = request.form.get("telegram_user_id")
                user.telegram_user_id = int(tid) if (tid or "").isdigit() else None
                user.is_active = bool(request.form.get("is_active"))
                if request.form.get("password"):
                    user.set_password(request.form["password"])
                s.commit()
                flash("User updated.", "success")
        return redirect(url_for("web.admin_users"))

    users = list(s.scalars(select(User).order_by(User.created_at)))
    return render_template("admin_users.html", users=users)


# --------------------------------------------------------------------------- #
# Settings (own profile / password)
# --------------------------------------------------------------------------- #
@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    s = SessionLocal()
    user = s.get(User, current_user.id)
    if request.method == "POST":
        user.name = (request.form.get("name") or user.name).strip()
        tid = request.form.get("telegram_user_id")
        user.telegram_user_id = int(tid) if (tid or "").isdigit() else None
        new_pw = request.form.get("password")
        if new_pw:
            user.set_password(new_pw)
        s.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("web.settings_page"))
    return render_template("settings.html", user=user)


@bp.app_errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403, message="You don't have access to that page."), 403


@bp.app_errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, message="Page not found."), 404
