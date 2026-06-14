.PHONY: help venv install init seed web bot run backup test docker-up docker-down

help:
	@echo "A2 Revenue OS — make targets:"
	@echo "  make install    create venv and install dependencies"
	@echo "  make init       initialise database + bootstrap admin"
	@echo "  make seed       load sample Johor pipeline data"
	@echo "  make web        run the dashboard (dev server)"
	@echo "  make bot        run the Telegram bot worker"
	@echo "  make backup     back up the database"
	@echo "  make docker-up  build & start via docker compose"

venv:
	python3 -m venv .venv

install: venv
	. .venv/bin/activate && pip install -r requirements.txt

init:
	. .venv/bin/activate && python manage.py init-db

seed:
	. .venv/bin/activate && python manage.py seed

web:
	. .venv/bin/activate && python run_web.py

bot:
	. .venv/bin/activate && python run_bot.py

backup:
	./scripts/backup.sh

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
