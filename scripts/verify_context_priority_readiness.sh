#!/usr/bin/env bash
set -Eeuo pipefail

readonly repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

readonly python_bin="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$python_bin" ]] && ! command -v "$python_bin" >/dev/null 2>&1; then
    printf 'Python executable is unavailable: %s\n' "$python_bin" >&2
    exit 1
fi

readonly probe_dir="$(mktemp -d "${TMPDIR:-/tmp}/grounded-growth-context-priority.XXXXXX")"

cleanup() {
    local status=$?
    trap - EXIT
    if [[ "$probe_dir" == "${TMPDIR:-/tmp}"/grounded-growth-context-priority.* ]]; then
        rm -rf -- "$probe_dir"
    fi
    exit "$status"
}
trap cleanup EXIT

export APP_DATA_DIR="$probe_dir"
export DJANGO_SECRET_KEY="context-priority-readiness-only-secret-key-47"
export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"
export APP_BOOTSTRAP_USERNAME="context-priority-readiness"
export APP_BOOTSTRAP_PASSWORD="Isolated-Gate-Password-47!"
export APP_TIME_ZONE="UTC"
export APP_DEBUG="true"
export APP_SECURE_COOKIES="false"

printf '\n==> Build an isolated migrated and idempotently seeded application database\n'
"$python_bin" manage.py migrate --noinput
"$python_bin" manage.py migrate --noinput
"$python_bin" manage.py bootstrap_user
"$python_bin" manage.py seed_canonical
"$python_bin" manage.py seed_canonical
"$python_bin" manage.py backfill_evidence_events
"$python_bin" manage.py rebuild_score_state

printf '\n==> Preserve evidence, score, pilot, curriculum, competency, context, and Personal OS readiness\n'
"$python_bin" manage.py verify_evidence_events
"$python_bin" manage.py rebuild_score_state --verify-only
"$python_bin" manage.py verify_pilot_readiness
"$python_bin" manage.py verify_expansion_readiness
"$python_bin" manage.py verify_competency_evidence_readiness
"$python_bin" manage.py verify_context_readiness
"$python_bin" manage.py verify_personal_os_readiness

printf '\n==> Verify deterministic M6C-03 replay with empty optional runtime context\n'
"$python_bin" manage.py verify_context_priority_readiness
"$python_bin" manage.py verify_context_priority_readiness --json >/dev/null
"$python_bin" manage.py migrate --check

printf '\nContext-priority readiness verification passed.\n'
