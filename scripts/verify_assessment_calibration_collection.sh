#!/usr/bin/env bash
set -Eeuo pipefail

readonly repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

readonly python_bin="${PYTHON_BIN:-.venv/bin/python}"
readonly probe_dir="$(mktemp -d "${TMPDIR:-/tmp}/grounded-growth-calibration-consent.XXXXXX")"

cleanup() {
    local status=$?
    trap - EXIT
    if [[ "$probe_dir" == "${TMPDIR:-/tmp}"/grounded-growth-calibration-consent.* ]]; then
        rm -rf -- "$probe_dir"
    fi
    exit "$status"
}
trap cleanup EXIT

export APP_DATA_DIR="$probe_dir"
export DJANGO_SECRET_KEY="calibration-consent-readiness-secret-key-47"
export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"
export APP_BOOTSTRAP_USERNAME="calibration-consent-readiness"
export APP_BOOTSTRAP_PASSWORD="Prismatic-Willow-47!"
export APP_TIME_ZONE="UTC"
export APP_DEBUG="true"
export APP_SECURE_COOKIES="false"

"$python_bin" manage.py migrate --noinput
"$python_bin" manage.py bootstrap_user
"$python_bin" manage.py seed_canonical
"$python_bin" manage.py verify_assessment_calibration_collection
"$python_bin" manage.py verify_assessment_calibration_collection --json > "$probe_dir/readiness.json"
"$python_bin" -c \
    'import json,sys; value=json.load(open(sys.argv[1], encoding="utf-8")); assert value["software_ready"] and value["active_assessment_runs"] == 0 and value["participant_evidence_axes_completed"] == 0; assert set(value).isdisjoint({"participant_token","answers","timing_data"})' \
    "$probe_dir/readiness.json"
"$python_bin" manage.py migrate --check

printf '\nAssessment calibration consent readiness verification passed.\n'
