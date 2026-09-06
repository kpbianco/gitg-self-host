from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_compose_is_one_service_with_persistent_data_and_healthcheck():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    assert set(compose["services"]) == {"app"}
    app = compose["services"]["app"]
    assert app["env_file"] == ["${APP_ENV_FILE:-.env}"]
    assert app["ports"] == ["${APP_PORT:-3000}:8000"]
    assert app["volumes"] == ["grounded_growth_data:/data"]
    assert app["restart"] == "unless-stopped"
    assert app["stop_grace_period"] == "30s"
    assert app["healthcheck"]["test"][0:2] == ["CMD", "python"]
    assert "grounded_growth_data" in compose["volumes"]


def test_container_runs_nonroot_gunicorn_and_safe_startup_sequence():
    dockerfile = (ROOT / "Dockerfile").read_text()
    entrypoint = (ROOT / "docker-entrypoint.sh").read_text()
    assert dockerfile.startswith("FROM python:3.13-slim")
    assert "USER grounded" in dockerfile
    assert "EXPOSE 8000" in dockerfile
    assert "node" not in dockerfile.lower()

    validate = entrypoint.index("manage.py validate_canonical_content")
    migrate = entrypoint.index("manage.py migrate")
    bootstrap = entrypoint.index("manage.py bootstrap_user")
    seed = entrypoint.index("manage.py seed_canonical")
    evidence_backfill = entrypoint.index("manage.py backfill_evidence_events")
    score_rebuild = entrypoint.index("manage.py rebuild_score_state")
    composite_rebuild = entrypoint.index("manage.py rebuild_composite_score_state")
    gunicorn = entrypoint.index("exec gunicorn")
    assert (
        validate
        < migrate
        < bootstrap
        < seed
        < evidence_backfill
        < score_rebuild
        < composite_rebuild
        < gunicorn
    )
    assert "--bind 0.0.0.0:8000" in entrypoint
    assert "--access-logfile -" in entrypoint
    assert "--error-logfile -" in entrypoint


def test_environment_example_covers_deployment_and_cookie_contract():
    keys = {
        line.split("=", 1)[0]
        for line in (ROOT / ".env.example").read_text().splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    assert {
        "APP_PORT",
        "DJANGO_SECRET_KEY",
        "DJANGO_ALLOWED_HOSTS",
        "APP_BOOTSTRAP_USERNAME",
        "APP_BOOTSTRAP_PASSWORD",
        "APP_TIME_ZONE",
        "APP_DEBUG",
        "APP_SECURE_COOKIES",
        "APP_OWNER_RETENTION_ENABLED",
        "APP_OWNER_RETENTION_DAYS",
    } <= keys


def test_repeatable_compose_acceptance_is_wired_into_make_and_ci():
    makefile = (ROOT / "Makefile").read_text()
    smoke_script = (ROOT / "scripts" / "verify_compose.sh").read_text()
    pilot_script = (ROOT / "scripts" / "verify_pilot_readiness.sh").read_text()
    expansion_script = (ROOT / "scripts" / "verify_expansion_readiness.sh").read_text()
    operations_script = (ROOT / "scripts" / "verify_m6h_operations_readiness.sh").read_text()
    calibration_collection_script = (
        ROOT / "scripts" / "verify_assessment_calibration_collection.sh"
    ).read_text()
    calibration_analysis_script = (
        ROOT / "scripts" / "verify_assessment_calibration_analysis.sh"
    ).read_text()
    login_probe = (ROOT / "scripts" / "verify_http_login.py").read_text()
    workflow = (ROOT / ".github" / "workflows" / "verification.yml").read_text()
    workflow_data = yaml.safe_load(workflow)

    assert "compose-smoke:" in makefile
    assert "./scripts/verify_compose.sh" in makefile
    assert "docker compose --project-name" in smoke_script
    assert "up -d --build --wait" in smoke_script
    assert "seed_canonical" in smoke_script
    assert "migrate --check" in smoke_script
    assert 'expected_counts="37,383,1403,383,383,383,37"' in smoke_script
    assert "availability=PracticeProtocol.Availability.ACTIVE" in smoke_script
    assert "PracticeProtocol.objects.filter(score_active=True).count()" in smoke_script
    assert "score_active=383:[0-9a-f]{64}" in smoke_script
    assert "backup_database" in smoke_script
    assert "verify_database_backup" in smoke_script
    assert "--compare-live" in smoke_script
    restore_steps = smoke_script.split("==> Restore the verified backup", 1)[1]
    assert restore_steps.index("verify_database_backup") < restore_steps.index(
        'http_probe "$original_password" success'
    )
    assert "--force-recreate" in smoke_script
    assert "shutil.copy2" in smoke_script
    assert "verify_http_login.py" in smoke_script
    assert "csrfmiddlewaretoken" in login_probe
    assert "HttpOnly" in login_probe
    assert "HTTP_TIMEOUT_SECONDS = 30" in login_probe
    assert "make compose-smoke" in workflow
    # Keep the approved slow-runner budgets tied to the jobs they protect.
    assert workflow_data["jobs"]["quality"]["timeout-minutes"] == 180
    assert workflow_data["jobs"]["compose"]["timeout-minutes"] == 60
    assert "pilot-check:" in makefile
    assert "verify_pilot_readiness.sh" in makefile
    assert "verify_pilot_readiness" in pilot_script
    assert smoke_script.count("verify_pilot_readiness") == 3
    assert "make pilot-check PYTHON=python" in workflow
    assert "curriculum-check:" in makefile
    assert "verify_expansion_readiness.sh" in makefile
    assert "generate_practice_reports --check" in expansion_script
    assert "verify_expansion_readiness" in expansion_script
    assert smoke_script.count("verify_expansion_readiness") == 3
    assert "make curriculum-check PYTHON=python" in workflow
    assert "m6h-operations-check:" in makefile
    assert "verify_m6h_operations_readiness.sh" in makefile
    assert "verify_m6h_operations_readiness" in operations_script
    assert smoke_script.count("verify_m6h_operations_readiness") == 4
    assert "make m6h-operations-check PYTHON=python" in workflow
    assert "composite-scoring-check:" in makefile
    assert "verify_composite_scoring_readiness.sh" in makefile
    assert smoke_script.count("verify_composite_scoring_readiness") == 3
    assert "make composite-scoring-check PYTHON=python" in workflow
    assert "assessment-calibration-check:" in makefile
    assert "assessment_calibration_readiness.py --check" in makefile
    assert "make assessment-calibration-check PYTHON=python" in workflow
    assert "assessment-calibration-collection-check:" in makefile
    assert "verify_assessment_calibration_collection.sh" in makefile
    assert "verify_assessment_calibration_collection" in calibration_collection_script
    assert smoke_script.count("verify_assessment_calibration_collection") == 4
    assert "make assessment-calibration-collection-check PYTHON=python" in workflow
    assert "assessment-calibration-analysis-check:" in makefile
    assert "verify_assessment_calibration_analysis.sh" in makefile
    assert "verify_assessment_calibration_analysis" in calibration_analysis_script
    assert smoke_script.count("verify_assessment_calibration_analysis") == 4
    assert "make assessment-calibration-analysis-check PYTHON=python" in workflow
    assert "Pilot readiness gate" in workflow
    assert set(workflow_data["jobs"]["pilot-ready"]["needs"]) == {
        "quality",
        "browser",
        "compose",
    }
    assert workflow_data["jobs"]["pilot-ready"]["if"] == "always()"
