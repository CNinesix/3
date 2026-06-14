"""Run the dashboard with the Flask development server (local use).

For production use gunicorn (see README / systemd unit).
"""
from app.webapp import create_app
from config import config

app = create_app()

if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
