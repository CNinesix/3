"""WSGI entrypoint for gunicorn:  gunicorn -c gunicorn.conf.py wsgi:app"""
from app.webapp import create_app

app = create_app()

if __name__ == "__main__":
    from config import config

    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
