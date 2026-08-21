#!/usr/bin/env bash
set -Eeuo pipefail

readonly repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

readonly python_bin="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$python_bin" ]] && ! command -v "$python_bin" >/dev/null 2>&1; then
    printf 'Python executable is unavailable: %s\n' "$python_bin" >&2
    exit 1
fi

readonly probe_dir="$(mktemp -d "${TMPDIR:-/tmp}/grounded-growth-m6d-01.XXXXXX")"

cleanup() {
    local status=$?
    trap - EXIT
    if [[ "$probe_dir" == "${TMPDIR:-/tmp}"/grounded-growth-m6d-01.* ]]; then
        rm -rf -- "$probe_dir"
    fi
    exit "$status"
}
trap cleanup EXIT

export APP_DATA_DIR="$probe_dir"
export DJANGO_SECRET_KEY="m6d-01-authoring-readiness-secret-key-59"
export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"
export APP_BOOTSTRAP_USERNAME="m6d-01-probe"
export APP_BOOTSTRAP_PASSWORD="M6D-01-readiness-password-59!"
export APP_TIME_ZONE="UTC"
export APP_DEBUG="true"
export APP_SECURE_COOKIES="false"

printf '\n==> Verify canonical source, deterministic reports, and M6D-01 fixture\n'
"$python_bin" manage.py validate_canonical_content
"$python_bin" manage.py generate_practice_reports --check
"$python_bin" manage.py generate_competency_evidence_reports --check

printf '\n==> Build isolated migrated and idempotently seeded runtime state\n'
"$python_bin" manage.py migrate --noinput
"$python_bin" manage.py bootstrap_user
"$python_bin" manage.py seed_canonical
"$python_bin" manage.py seed_canonical
"$python_bin" manage.py backfill_evidence_events
"$python_bin" manage.py rebuild_score_state

printf '\n==> Preserve historical replay and prerequisite readiness\n'
"$python_bin" manage.py verify_evidence_events
"$python_bin" manage.py rebuild_score_state --verify-only
"$python_bin" manage.py verify_expansion_readiness
"$python_bin" manage.py verify_competency_evidence_readiness

printf '\n==> Verify additive read-only M6D-01 authoring readiness\n'
"$python_bin" manage.py verify_m6d_authoring_readiness
"$python_bin" manage.py migrate --check

printf '\nM6D-01 authoring readiness verification passed.\n'
