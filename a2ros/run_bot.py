"""Run the Telegram bot worker (long polling + scheduled jobs)."""
import sys

from app.telegram.bot import main

if __name__ == "__main__":
    sys.exit(main())
