FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# sqlite3 CLI is used by the backup script; libpq for postgres.
RUN apt-get update \
    && apt-get install -y --no-install-recommends sqlite3 libpq5 tzdata curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Default DB location inside the container (mount a volume here).
ENV DATABASE_URL=sqlite:////data/a2ros.db
RUN mkdir -p /data

EXPOSE 8000

# Default command runs the web app; the bot runs as a separate service
# (see docker-compose.yml).
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
