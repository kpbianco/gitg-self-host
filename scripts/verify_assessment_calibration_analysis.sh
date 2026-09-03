#!/usr/bin/env bash
set -Eeuo pipefail

readonly repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

readonly python_bin="${PYTHON_BIN:-.venv/bin/python}"
readonly probe_dir="$(mktemp -d "${TMPDIR:-/tmp}/grounded-growth-calibration-analysis.XXXXXX")"

cleanup() {
    local status=$?
    trap - EXIT
    if [[ "$probe_dir" == "${TMPDIR:-/tmp}"/grounded-growth-calibration-analysis.* ]]; then
        rm -rf -- "$probe_dir"
    fi
    exit "$status"
}
trap cleanup EXIT

export APP_DATA_DIR="$probe_dir"
export DJANGO_SECRET_KEY="calibration-analysis-readiness-secret-key-47"
export APP_TIME_ZONE="UTC"
export APP_DEBUG="true"

"$python_bin" manage.py verify_assessment_calibration_analysis
"$python_bin" manage.py verify_assessment_calibration_analysis --json > "$probe_dir/readiness.json"
"$python_bin" -c \
    'import json,sys; value=json.load(open(sys.argv[1], encoding="utf-8")); assert value["software_ready"] and value["synthetic_participants"] == 30 and value["synthetic_assessment_runs"] == 60; assert value["participant_evidence_axes_completed"] == 0 and not value["database_accessed"] and not value["raw_values_in_report"] and value["requires_qualified_analysis"]' \
    "$probe_dir/readiness.json"

printf '\nAssessment calibration analysis readiness verification passed.\n'
