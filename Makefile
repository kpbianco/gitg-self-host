PYTHON ?= .venv/bin/python
APP_DATA_DIR ?= $(CURDIR)/var

.PHONY: format lint test e2e migrate seed evidence-backfill run compose-up compose-down backup

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

lint:
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m ruff check .
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-check-secret APP_DEBUG=true \
		$(PYTHON) manage.py check

test:
	$(PYTHON) -m pytest -m "not e2e"

e2e:
	PLAYWRIGHT_BROWSERS_PATH="$(CURDIR)/.playwright-browsers" \
		$(PYTHON) -m pytest -m e2e

migrate:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py migrate

seed:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py seed_canonical

evidence-backfill:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py backfill_evidence_events

run:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py runserver 0.0.0.0:3000

compose-up:
	docker compose up -d --build

compose-down:
	docker compose down

backup:
	docker compose exec app python manage.py backup_database
