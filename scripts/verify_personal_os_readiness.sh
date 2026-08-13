#!/usr/bin/env bash
set -Eeuo pipefail

readonly repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

readonly python_bin="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$python_bin" ]] && ! command -v "$python_bin" >/dev/null 2>&1; then
    printf 'Python executable is unavailable: %s\n' "$python_bin" >&2
    exit 1
fi

readonly probe_dir="$(mktemp -d "${TMPDIR:-/tmp}/grounded-growth-personal-os.XXXXXX")"

cleanup() {
    local status=$?
    trap - EXIT
    if [[ "$probe_dir" == "${TMPDIR:-/tmp}"/grounded-growth-personal-os.* ]]; then
        rm -rf -- "$probe_dir"
    fi
    exit "$status"
}
trap cleanup EXIT

export APP_DATA_DIR="$probe_dir"
export DJANGO_SECRET_KEY="personal-os-readiness-only-secret-key-with-sufficient-length-47"
export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"
export APP_BOOTSTRAP_USERNAME="personal-os-readiness"
export APP_BOOTSTRAP_PASSWORD="M6c-personal-OS-Drill-47!"
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

printf '\n==> Preserve evidence, score, pilot, curriculum, competency, and context readiness\n'
"$python_bin" manage.py verify_evidence_events
"$python_bin" manage.py rebuild_score_state --verify-only
"$python_bin" manage.py verify_pilot_readiness
"$python_bin" manage.py verify_expansion_readiness
"$python_bin" manage.py verify_competency_evidence_readiness
"$python_bin" manage.py verify_context_readiness

printf '\n==> Verify empty optional state then one synthetic append-only revision\n'
"$python_bin" manage.py verify_personal_os_readiness
"$python_bin" manage.py shell -c \
    'from growth.models import AssessmentRun; from growth.services.personal_os import record_personal_os_revision; run=AssessmentRun.objects.select_related("user").order_by("stable_id").first(); state={"state":"provided"}; identity={"mission":{**state,"value":"Synthetic readiness direction."},"principles":{**state,"value":["Synthetic bounded principle."]},"anti_goals":{**state,"value":["Synthetic unbounded work."]},"twelve_month_direction":{**state,"value":"Synthetic dependable operation."},"priority_stack":{**state,"value":["Synthetic recovery proof."]}}; audit={key:{**state,"value":"Synthetic descriptive response."} for key in ("current_truth","autopilot_pattern","misalignment_or_fragmentation","deliberate_next_step")}; first=record_personal_os_revision(user=run.user,assessment_run=run,identity_sections=identity,audit_responses=audit); second=record_personal_os_revision(user=run.user,assessment_run=run,identity_sections=identity,audit_responses=audit); assert first.created and not second.created and first.revision.pk == second.revision.pk'
"$python_bin" manage.py verify_personal_os_readiness
"$python_bin" manage.py migrate --check

printf '\nPersonal OS readiness verification passed.\n'
