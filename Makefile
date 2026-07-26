.PHONY: install migrate migrate-dev seed seed-dev ensure-superuser createsuperuser db-up dbgate-up db-down run runserver tw-build tw-watch tailwind tailwind-watch test lint format check manage-check migrations-check deploy-migrate deploy-ensure-superuser deploy-check deploy-release reminders-dry-run reminders-run

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

migrate:
	$(PYTHON) manage.py migrate

migrate-dev:
	$(PYTHON) manage.py migrate

ensure-superuser:
	$(PYTHON) manage.py ensure_superuser

seed:
	$(PYTHON) manage.py seed_demo

seed-dev:
	$(PYTHON) manage.py seed_demo

db-up:
	docker compose up -d db

dbgate-up:
	docker compose up -d db dbgate

db-down:
	docker compose stop db dbgate

run:
	$(PYTHON) manage.py runserver

runserver: run

createsuperuser:
	$(PYTHON) manage.py createsuperuser

tw-build:
	npm run tailwind:build

tw-watch:
	npm run tailwind:watch

tailwind: tw-build

tailwind-watch: tw-watch

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src conftest.py

manage-check:
	$(PYTHON) manage.py check

migrations-check:
	$(PYTHON) manage.py makemigrations --check --dry-run

deploy-migrate:
	$(PYTHON) manage.py migrate --noinput

deploy-ensure-superuser:
	$(PYTHON) manage.py ensure_superuser

deploy-check:
	$(PYTHON) manage.py check --deploy || $(PYTHON) manage.py check

deploy-release: deploy-migrate deploy-ensure-superuser deploy-check

reminders-dry-run:
	$(PYTHON) manage.py send_reminders --dry-run

reminders-run:
	$(PYTHON) manage.py send_reminders

check: lint manage-check migrations-check test

format:
	$(PYTHON) -m ruff format src conftest.py
