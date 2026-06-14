"""Flask extensions shared across the web app."""
from __future__ import annotations

from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to continue."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id: str):
    from app.db import SessionLocal
    from app.models import User

    session = SessionLocal()
    try:
        return session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None
