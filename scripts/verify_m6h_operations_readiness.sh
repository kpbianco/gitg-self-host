#!/usr/bin/env bash
set -Eeuo pipefail

readonly repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

readonly python_bin="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$python_bin" ]] && ! command -v "$python_bin" >/dev/null 2>&1; then
    printf 'Python executable is unavailable: %s\n' "$python_bin" >&2
    exit 1
fi

readonly probe_dir="$(mktemp -d "${TMPDIR:-/tmp}/grounded-growth-operations.XXXXXX")"

cleanup() {
    local status=$?
    trap - EXIT
    if [[ "$probe_dir" == "${TMPDIR:-/tmp}"/grounded-growth-operations.* ]]; then
        rm -rf -- "$probe_dir"
    fi
    exit "$status"
}
trap cleanup EXIT

export APP_DATA_DIR="$probe_dir"
export DJANGO_SECRET_KEY="m6h-operations-readiness-secret-key-with-sufficient-length-47"
export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"
export APP_BOOTSTRAP_USERNAME="m6h-operations-readiness"
export APP_BOOTSTRAP_PASSWORD="Quasar-River-Copper-Operations-47!"
export APP_TIME_ZONE="UTC"
export APP_DEBUG="true"
export APP_SECURE_COOKIES="false"
export APP_OWNER_RETENTION_ENABLED="false"
export APP_OWNER_RETENTION_DAYS="365"

printf '\n==> Build isolated migrated and idempotently seeded state\n'
"$python_bin" manage.py migrate --noinput
"$python_bin" manage.py bootstrap_user
"$python_bin" manage.py seed_canonical
"$python_bin" manage.py seed_canonical
"$python_bin" manage.py rebuild_score_state

printf '\n==> Verify deterministic owner archive and disabled retention\n'
"$python_bin" manage.py verify_m6h_operations_readiness
"$python_bin" manage.py verify_m6h_operations_readiness --json > "$probe_dir/readiness.json"
"$python_bin" -c \
    'import json,sys; value=json.load(open(sys.argv[1], encoding="utf-8")); assert value["software_ready"] and value["retention_enabled"] is False and value["retention_candidates"] == 0; assert set(value).isdisjoint({"username","email","password","records"})' \
    "$probe_dir/readiness.json"

printf '\n==> Create and verify a private pre-upgrade backup\n'
"$python_bin" manage.py backup_database --output "$probe_dir/pre-upgrade.sqlite3"
"$python_bin" manage.py verify_database_backup "$probe_dir/pre-upgrade.sqlite3" --compare-live
test "$(stat -c '%a' "$probe_dir/pre-upgrade.sqlite3")" = "600"
test "$(stat -c '%a' "$probe_dir/pre-upgrade.sqlite3.manifest.json")" = "600"

printf '\n==> Verify migration health and preserved runtime contracts\n'
"$python_bin" manage.py migrate --check
"$python_bin" manage.py verify_evidence_events
"$python_bin" manage.py rebuild_score_state --verify-only
"$python_bin" manage.py verify_weekly_execution_readiness

printf '\nM6H-02 operations readiness verification passed.\n'
