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
    mktemp -d "${TMPDIR:-/tmp}/grounded-growth-competency-evidence.XXXXXX"
)"

cleanup() {
    local status=$?
    trap - EXIT
    if [[ "$probe_dir" == "${TMPDIR:-/tmp}"/grounded-growth-competency-evidence.* ]]; then
        rm -rf -- "$probe_dir"
    fi
    exit "$status"
}
trap cleanup EXIT

export APP_DATA_DIR="$probe_dir"
export DJANGO_SECRET_KEY="competency-evidence-readiness-secret-key-47"
export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"
export APP_BOOTSTRAP_USERNAME="m6b-probe"
export APP_BOOTSTRAP_PASSWORD="Competency-evidence-password-47!"
export APP_TIME_ZONE="UTC"
export APP_DEBUG="true"
export APP_SECURE_COOKIES="false"

printf '\n==> Verify canonical and deterministic M6A/M6B source contracts\n'
"$python_bin" manage.py validate_canonical_content
"$python_bin" manage.py generate_practice_reports --check
"$python_bin" manage.py generate_competency_evidence_reports --check

printf '\n==> Build an isolated migrated and idempotently seeded application database\n'
"$python_bin" manage.py migrate --noinput
"$python_bin" manage.py bootstrap_user
"$python_bin" manage.py seed_canonical
"$python_bin" manage.py seed_canonical
"$python_bin" manage.py backfill_evidence_events
"$python_bin" manage.py rebuild_score_state

printf '\n==> Preserve exact v1 evidence and production score-state replay\n'
"$python_bin" manage.py verify_evidence_events
"$python_bin" manage.py rebuild_score_state --verify-only

printf '\n==> Preserve M6A and verify additive M6B software readiness\n'
"$python_bin" manage.py verify_expansion_readiness
"$python_bin" manage.py verify_competency_evidence_readiness
"$python_bin" manage.py migrate --check

printf '\nCompetency-evidence software readiness verification passed.\n'
