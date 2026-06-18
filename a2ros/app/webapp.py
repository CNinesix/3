"""Flask application factory for the A2 ROS dashboard."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from flask import Flask

from app import __version__
from app.db import SessionLocal, init_db
from app.extensions import login_manager
from app.services import settings as settings_svc
from config import config

TZ = ZoneInfo(config.TIMEZONE)


def create_app() -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["BASE_URL"] = config.BASE_URL
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Secure cookies when served over HTTPS in production.
    app.config["SESSION_COOKIE_SECURE"] = config.ENV == "production"
    app.config["PERMANENT_SESSION_LIFETIME"] = dt.timedelta(days=14)

    login_manager.init_app(app)

    # Ensure schema + default settings exist on boot.
    init_db()
    _session = SessionLocal()
    try:
        settings_svc.ensure_defaults(_session)
    finally:
        SessionLocal.remove()

    # Register blueprints
    from app.auth.routes import bp as auth_bp
    from app.web.routes import bp as web_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(web_bp)

    # Tear down the scoped session after each request.
    @app.teardown_appcontext
    def _remove_session(exc=None):  # noqa: ANN001
        SessionLocal.remove()

    # Template helpers
    @app.template_filter("money")
    def _money(value, currency="RM"):
        try:
            return f"{currency}{float(value):,.0f}"
        except (TypeError, ValueError):
            return f"{currency}0"

    @app.template_filter("localdt")
    def _localdt(value, fmt="%d %b %Y %H:%M"):
        if not value:
            return "-"
        if isinstance(value, dt.datetime) and value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value.astimezone(TZ).strftime(fmt)

    @app.context_processor
    def _ctx():
        return {
            "app_version": __version__,
            "base_url": config.BASE_URL,
            "now_local": dt.datetime.now(TZ),
        }

    return app
