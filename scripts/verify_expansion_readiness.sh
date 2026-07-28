#!/usr/bin/env bash
set -Eeuo pipefail

readonly repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

readonly python_bin="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$python_bin" ]] && ! command -v "$python_bin" >/dev/null 2>&1; then
    printf 'Python executable is unavailable: %s\n' "$python_bin" >&2
    exit 1
fi

readonly probe_dir="$(
    mktemp -d "${TMPDIR:-/tmp}/grounded-growth-expansion-readiness.XXXXXX"
)"

cleanup() {
    local status=$?
    trap - EXIT
    if [[ "$probe_dir" == "${TMPDIR:-/tmp}"/grounded-growth-expansion-readiness.* ]]; then
        rm -rf -- "$probe_dir"
    fi
    exit "$status"
}
trap cleanup EXIT

export APP_DATA_DIR="$probe_dir"
export DJANGO_SECRET_KEY="expansion-readiness-only-secret-key-with-sufficient-length-47"
export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"
export APP_BOOTSTRAP_USERNAME="m6a-probe"
export APP_BOOTSTRAP_PASSWORD="Canonical-foundation-password-47!"
export APP_TIME_ZONE="UTC"
export APP_DEBUG="true"
export APP_SECURE_COOKIES="false"

printf '\n==> Verify deterministic canonical practice-content reports\n'
"$python_bin" manage.py generate_practice_reports --check

printf '\n==> Build an isolated migrated and idempotently seeded application database\n'
"$python_bin" manage.py migrate --noinput
"$python_bin" manage.py bootstrap_user
"$python_bin" manage.py seed_canonical
"$python_bin" manage.py seed_canonical
"$python_bin" manage.py backfill_evidence_events
"$python_bin" manage.py rebuild_score_state

printf '\n==> Run the additive M6A curriculum-expansion readiness contract\n'
"$python_bin" manage.py verify_expansion_readiness
"$python_bin" manage.py migrate --check

printf '\nCurriculum-expansion readiness verification passed.\n'
