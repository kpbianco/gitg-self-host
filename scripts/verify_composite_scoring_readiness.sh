#!/usr/bin/env bash
set -Eeuo pipefail

readonly repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

readonly python_bin="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$python_bin" ]] && ! command -v "$python_bin" >/dev/null 2>&1; then
    printf 'Python executable is unavailable: %s\n' "$python_bin" >&2
    exit 1
fi

readonly probe_dir="$(mktemp -d "${TMPDIR:-/tmp}/grounded-growth-composite-scoring.XXXXXX")"

cleanup() {
    local status=$?
    trap - EXIT
    if [[ "$probe_dir" == "${TMPDIR:-/tmp}"/grounded-growth-composite-scoring.* ]]; then
        rm -rf -- "$probe_dir"
    fi
    exit "$status"
}
trap cleanup EXIT

export APP_DATA_DIR="$probe_dir"
export DJANGO_SECRET_KEY="composite-scoring-readiness-secret-key-with-sufficient-length-47"
export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"
export APP_BOOTSTRAP_USERNAME="composite-scoring-readiness"
export APP_BOOTSTRAP_PASSWORD="Tundra-Quartz!947-Maple"
export APP_TIME_ZONE="UTC"
export APP_DEBUG="true"
export APP_SECURE_COOKIES="false"

printf '\n==> Verify the committed whole-catalog scoring disposition\n'
"$python_bin" scripts/composite_scoring_catalog.py --check

printf '\n==> Build isolated migrated and idempotently seeded score state\n'
"$python_bin" manage.py migrate --noinput
"$python_bin" manage.py migrate --noinput
"$python_bin" manage.py bootstrap_user
"$python_bin" manage.py seed_canonical
"$python_bin" manage.py seed_canonical
"$python_bin" manage.py rebuild_score_state
"$python_bin" manage.py rebuild_composite_score_state

printf '\n==> Verify legacy replay and additive composite replay independently\n'
"$python_bin" manage.py verify_evidence_events
"$python_bin" manage.py rebuild_score_state --verify-only
"$python_bin" manage.py rebuild_composite_score_state --verify-only
"$python_bin" manage.py verify_composite_scoring_readiness
"$python_bin" manage.py verify_composite_scoring_readiness --json > "$probe_dir/readiness.json"
"$python_bin" -c \
    'import json,sys; value=json.load(open(sys.argv[1], encoding="utf-8")); assert value["software_ready"] and value["requires_human_gate"]; assert value["competencies_per_epoch"] == 383 and value["practices"] == 383 and value["actions"] == 1151; assert value["specialist_review_status"] == "pending" and not value["specialist_review_complete"]; assert value["research_gap_status"] == "open" and not value["m6b_accepted"]' \
    "$probe_dir/readiness.json"
"$python_bin" manage.py migrate --check

printf '\nComposite scoring readiness verification passed.\n'
