PYTHON ?= .venv/bin/python
APP_DATA_DIR ?= $(CURDIR)/var

.PHONY: format lint test e2e migrate seed evidence-backfill evidence-verify score-rebuild score-verify composite-score-rebuild composite-score-verify composite-scoring-check applicability-coverage-check assessment-calibration assessment-calibration-check assessment-calibration-collection-check assessment-calibration-analysis-check pilot-check practice-reports practice-report-check catalog-governance-audit catalog-governance-audit-check composite-scoring-catalog composite-scoring-catalog-check curriculum-check full-frontier-check competency-evidence-reports competency-evidence-report-check competency-evidence-check context-check personal-os-check context-priority-check m6c-pilot-check m6d-01-check m6h-weekly-check m6h-operations-check run compose-up compose-down compose-smoke backup

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

lint:
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m ruff check .
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-check-secret APP_DEBUG=true \
		$(PYTHON) manage.py check
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-check-secret APP_DEBUG=true \
		$(PYTHON) manage.py makemigrations --check --dry-run

test:
	$(PYTHON) -m pytest -m "not e2e"

e2e:
	PLAYWRIGHT_BROWSERS_PATH="$(CURDIR)/.playwright-browsers" \
		$(PYTHON) -m pytest -m e2e \
		--tracing=retain-on-failure \
		--screenshot=only-on-failure \
		--output=test-results

migrate:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py migrate

seed:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py seed_canonical

evidence-backfill:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py backfill_evidence_events

evidence-verify:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py verify_evidence_events

score-rebuild:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py rebuild_score_state

score-verify:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py rebuild_score_state --verify-only

composite-score-rebuild:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py rebuild_composite_score_state

composite-score-verify:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py rebuild_composite_score_state --verify-only

pilot-check:
	PYTHON_BIN="$(PYTHON)" ./scripts/verify_pilot_readiness.sh

practice-reports:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py generate_practice_reports

practice-report-check:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py generate_practice_reports --check

catalog-governance-audit:
	$(PYTHON) scripts/catalog_governance_audit.py

catalog-governance-audit-check:
	$(PYTHON) scripts/catalog_governance_audit.py --check

composite-scoring-catalog:
	$(PYTHON) scripts/composite_scoring_catalog.py

composite-scoring-catalog-check:
	$(PYTHON) scripts/composite_scoring_catalog.py --check

composite-scoring-check:
	PYTHON_BIN="$(PYTHON)" ./scripts/verify_composite_scoring_readiness.sh

applicability-coverage-check:
	PYTHON_BIN="$(PYTHON)" ./scripts/verify_applicability_coverage.sh

assessment-calibration:
	$(PYTHON) scripts/assessment_calibration_readiness.py

assessment-calibration-check:
	$(PYTHON) scripts/assessment_calibration_readiness.py --check
	node scripts/verify_assessment_golden.js >/dev/null

assessment-calibration-collection-check:
	PYTHON_BIN="$(PYTHON)" ./scripts/verify_assessment_calibration_collection.sh

assessment-calibration-analysis-check:
	PYTHON_BIN="$(PYTHON)" ./scripts/verify_assessment_calibration_analysis.sh

curriculum-check:
	PYTHON_BIN="$(PYTHON)" ./scripts/verify_expansion_readiness.sh

full-frontier-check:
	$(PYTHON) scripts/author_full_competency_frontier.py --check
	$(PYTHON) -m pytest tests/test_full_competency_frontier.py tests/test_practice_content.py::test_generated_coverage_and_originality_reports_are_current_and_complete

competency-evidence-reports:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py generate_competency_evidence_reports

competency-evidence-report-check:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py generate_competency_evidence_reports --check

competency-evidence-check:
	PYTHON_BIN="$(PYTHON)" ./scripts/verify_competency_evidence_readiness.sh

context-check:
	PYTHON_BIN="$(PYTHON)" ./scripts/verify_context_readiness.sh

personal-os-check:
	PYTHON_BIN="$(PYTHON)" ./scripts/verify_personal_os_readiness.sh

context-priority-check:
	PYTHON_BIN="$(PYTHON)" ./scripts/verify_context_priority_readiness.sh

m6c-pilot-check:
	PYTHON_BIN="$(PYTHON)" ./scripts/verify_m6c_pilot_readiness.sh

m6d-01-check:
	PYTHON_BIN="$(PYTHON)" ./scripts/verify_m6d_authoring_readiness.sh

m6h-weekly-check:
	PYTHON_BIN="$(PYTHON)" ./scripts/verify_weekly_execution_readiness.sh

m6h-operations-check:
	PYTHON_BIN="$(PYTHON)" ./scripts/verify_m6h_operations_readiness.sh

run:
	APP_DATA_DIR="$(APP_DATA_DIR)" DJANGO_SECRET_KEY=local-development-secret APP_DEBUG=true \
		$(PYTHON) manage.py runserver 0.0.0.0:3000

compose-up:
	docker compose up -d --build

compose-down:
	docker compose down

compose-smoke:
	./scripts/verify_compose.sh

backup:
	docker compose exec app python manage.py backup_database
