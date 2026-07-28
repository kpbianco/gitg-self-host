#!/usr/bin/env bash
set -Eeuo pipefail

readonly repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

for required_command in docker curl python3; do
    if ! command -v "$required_command" >/dev/null 2>&1; then
        printf 'Required command is unavailable: %s\n' "$required_command" >&2
        exit 1
    fi
done
docker compose version

readonly probe_dir="$(mktemp -d "${TMPDIR:-/tmp}/grounded-growth-compose-smoke.XXXXXX")"
readonly initial_env="$probe_dir/initial.env"
readonly changed_env="$probe_dir/changed.env"
readonly project_name="ggsmoke${GITHUB_RUN_ID:-local}${GITHUB_RUN_ATTEMPT:-0}$$"
readonly username="compose-probe"
readonly original_password="Original-probe-password-47!"
readonly persisted_password="Persisted-probe-password-58!"
readonly changed_env_password="Changed-env-password-69!"
readonly backup_path="/data/backups/compose-smoke.sqlite3"
readonly expected_counts="37,383,1403,5,37"

if [[ -n "${SMOKE_APP_PORT:-}" ]]; then
    readonly app_port="$SMOKE_APP_PORT"
else
    readonly app_port="$(
        python3 -c \
            'import socket; sock = socket.socket(); sock.bind(("127.0.0.1", 0)); print(sock.getsockname()[1]); sock.close()'
    )"
fi
readonly base_url="http://127.0.0.1:$app_port"

write_env() {
    local path="$1"
    local password="$2"
    {
        printf 'APP_PORT=%s\n' "$app_port"
        printf 'DJANGO_SECRET_KEY=compose-smoke-only-secret-key-with-sufficient-length-47\n'
        printf 'DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1\n'
        printf 'APP_BOOTSTRAP_USERNAME=%s\n' "$username"
        printf 'APP_BOOTSTRAP_PASSWORD=%s\n' "$password"
        printf 'APP_TIME_ZONE=UTC\n'
        printf 'APP_DEBUG=false\n'
        printf 'APP_SECURE_COOKIES=false\n'
        printf 'GUNICORN_WORKERS=1\n'
    } >"$path"
}

write_env "$initial_env" "$original_password"
write_env "$changed_env" "$changed_env_password"
active_env="$initial_env"

compose() {
    APP_ENV_FILE="$active_env" APP_PORT="$app_port" \
        docker compose --project-name "$project_name" "$@"
}

cleanup() {
    local status=$?
    trap - EXIT
    if ((status != 0)); then
        printf '\nCompose verification failed; final service state and logs follow.\n' >&2
        compose ps >&2 || true
        compose logs --no-color app >&2 || true
    fi
    if [[ "$project_name" == ggsmoke* ]]; then
        compose down --volumes --remove-orphans >/dev/null 2>&1 || true
    fi
    rm -f -- "$initial_env" "$changed_env"
    rmdir "$probe_dir" 2>/dev/null || true
    exit "$status"
}
trap cleanup EXIT

http_probe() {
    local password="$1"
    local expectation="$2"
    local boundary_option=()
    if [[ "$expectation" == "failure" ]]; then
        boundary_option=(--skip-public-boundary)
    fi
    python3 scripts/verify_http_login.py \
        --base-url "$base_url" \
        --username "$username" \
        --password "$password" \
        --expect "$expectation" \
        "${boundary_option[@]}"
}

canonical_counts() {
    compose exec -T app python manage.py shell -c \
        'from growth.models import Competency, CompetencyLeverLink, Lever, LeverBaseline, PracticeProtocol; print(",".join(str(value) for value in (Lever.objects.count(), Competency.objects.count(), CompetencyLeverLink.objects.count(), PracticeProtocol.objects.count(), LeverBaseline.objects.count())))' \
        | tail -n 1
}

printf '\n==> Build and start the isolated application stack\n'
compose up -d --build --wait --wait-timeout 180
container_id="$(compose ps -q app)"
test -n "$container_id"
test "$(docker inspect --format '{{.State.Health.Status}}' "$container_id")" = "healthy"
test "$(compose exec -T app id -u | tr -d '\r')" = "10001"
http_probe "$original_password" success

printf '\n==> Verify migrations, canonical seed idempotency, and score-state replay\n'
compose exec -T app python manage.py migrate --check
before_counts="$(canonical_counts)"
compose exec -T app python manage.py seed_canonical
compose exec -T app python manage.py seed_canonical
after_counts="$(canonical_counts)"
test "$before_counts" = "$after_counts"
test "$after_counts" = "$expected_counts"
compose exec -T app python manage.py verify_evidence_events
compose exec -T app python manage.py rebuild_score_state --verify-only
compose exec -T app python manage.py verify_pilot_readiness
compose exec -T app python manage.py verify_expansion_readiness

printf '\n==> Create and integrity-check an online SQLite backup\n'
compose exec -T app python manage.py backup_database --output "$backup_path"
compose exec -T app python -c \
    'import sqlite3; connection = sqlite3.connect("/data/backups/compose-smoke.sqlite3"); result = connection.execute("PRAGMA integrity_check").fetchone()[0]; connection.close(); assert result == "ok", result; print(result)'

printf '\n==> Prove volume and one-time bootstrap persistence across recreation\n'
compose exec -T -e DEPLOYMENT_PROBE_PASSWORD="$persisted_password" app \
    python manage.py shell -c \
    'import os; from django.contrib.auth import get_user_model; user = get_user_model().objects.get(username="compose-probe"); user.set_password(os.environ["DEPLOYMENT_PROBE_PASSWORD"]); user.save(update_fields=["password"])'
active_env="$changed_env"
compose up -d --force-recreate --wait --wait-timeout 180
http_probe "$persisted_password" success
http_probe "$changed_env_password" failure
test "$(canonical_counts)" = "$expected_counts"
compose exec -T app python manage.py migrate --check
compose exec -T app python manage.py rebuild_score_state --verify-only
compose exec -T app python manage.py verify_pilot_readiness
compose exec -T app python manage.py verify_expansion_readiness

printf '\n==> Restore the verified backup inside the isolated volume\n'
compose down
compose run --rm --no-deps --entrypoint python app -c \
    'from pathlib import Path; import shutil; source = Path("/data/backups/compose-smoke.sqlite3"); target = Path("/data/grounded_growth.sqlite3"); shutil.copy2(source, target); target.with_name(target.name + "-wal").unlink(missing_ok=True); target.with_name(target.name + "-shm").unlink(missing_ok=True)'
compose up -d --wait --wait-timeout 180
http_probe "$original_password" success
http_probe "$persisted_password" failure
http_probe "$changed_env_password" failure
test "$(canonical_counts)" = "$expected_counts"
compose exec -T app python manage.py rebuild_score_state --verify-only
compose exec -T app python manage.py verify_pilot_readiness
compose exec -T app python manage.py verify_expansion_readiness

printf '\n==> Confirm clean Gunicorn shutdown\n'
compose stop --timeout 30 app
test "$(docker inspect --format '{{.State.ExitCode}}' "$(compose ps -a -q app)")" = "0"

printf '\nDocker Compose deployment verification passed.\n'
