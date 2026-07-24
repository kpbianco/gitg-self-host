from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_compose_is_one_service_with_persistent_data_and_healthcheck():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    assert set(compose["services"]) == {"app"}
    app = compose["services"]["app"]
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

    migrate = entrypoint.index("manage.py migrate")
    bootstrap = entrypoint.index("manage.py bootstrap_user")
    seed = entrypoint.index("manage.py seed_canonical")
    evidence_backfill = entrypoint.index("manage.py backfill_evidence_events")
    gunicorn = entrypoint.index("exec gunicorn")
    assert migrate < bootstrap < seed < evidence_backfill < gunicorn
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
    } <= keys
