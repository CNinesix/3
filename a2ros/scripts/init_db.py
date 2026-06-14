"""Thin wrapper so `python scripts/init_db.py` works like `python manage.py init-db`."""
from manage import cmd_init_db

if __name__ == "__main__":
    raise SystemExit(cmd_init_db())
