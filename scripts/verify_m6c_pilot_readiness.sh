#!/usr/bin/env bash
set -Eeuo pipefail

readonly repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

readonly python_bin="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$python_bin" ]] && ! command -v "$python_bin" >/dev/null 2>&1; then
    printf 'Python executable is unavailable: %s\n' "$python_bin" >&2
    exit 1
fi

readonly probe_dir="$(mktemp -d "${TMPDIR:-/tmp}/grounded-growth-m6c-pilot.XXXXXX")"

cleanup() {
    local status=$?
    trap - EXIT
    if [[ "$probe_dir" == "${TMPDIR:-/tmp}"/grounded-growth-m6c-pilot.* ]]; then
        rm -rf -- "$probe_dir"
    fi
    exit "$status"
}
trap cleanup EXIT

export APP_DATA_DIR="$probe_dir"
export DJANGO_SECRET_KEY="m6c-pilot-readiness-only-secret-key-47"
export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"
export APP_BOOTSTRAP_USERNAME="m6c-pilot-readiness"
export APP_BOOTSTRAP_PASSWORD="M6c-browser-gate-password-47!"
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

printf '\n==> Verify empty optional state through the additive M6C aggregate\n'
"$python_bin" manage.py verify_m6c_pilot_readiness
"$python_bin" manage.py verify_m6c_pilot_readiness --json >/dev/null

printf '\n==> Exercise synthetic public Personal OS, context, and priority services\n'
"$python_bin" manage.py shell -c \
    'from growth.domain.context import ContextFactorValue; from growth.models import AssessmentRun, PracticeProtocol; from growth.services.context import PracticeContextInput, record_context_bundle; from growth.services.context_priority import build_context_priority_for_epoch; from growth.services.personal_os import record_personal_os_revision; run=AssessmentRun.objects.select_related("user").order_by("stable_id").first(); protocol=PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01"); provided=lambda value: ContextFactorValue("provided",value); identity={"mission":{"state":"provided","value":"Synthetic readiness direction."},"principles":{"state":"provided","value":["Synthetic bounded principle."]},"anti_goals":{"state":"provided","value":["Synthetic unbounded operation."]},"twelve_month_direction":{"state":"provided","value":"Synthetic recovery remains exact."},"priority_stack":{"state":"provided","value":["Synthetic replay proof."]}}; audit={key:{"state":"provided","value":"Synthetic descriptive response."} for key in ("current_truth","autopilot_pattern","misalignment_or_fragmentation","deliberate_next_step")}; first_personal=record_personal_os_revision(user=run.user,assessment_run=run,identity_sections=identity,audit_responses=audit); second_personal=record_personal_os_revision(user=run.user,assessment_run=run,identity_sections=identity,audit_responses=audit); assessment={"season":provided("foundation"),"capacity":provided(3)}; practice={key:provided(value) for key,value in (("applicability",4),("importance",3),("readiness",3),("urgency",2),("opportunity_resources",3),("burden",1))}; first_context=record_context_bundle(user=run.user,assessment_run=run,assessment_factors=assessment,practice_inputs=(PracticeContextInput(protocol=protocol,factors=practice),)); second_context=record_context_bundle(user=run.user,assessment_run=run,assessment_factors=assessment,practice_inputs=(PracticeContextInput(protocol=protocol,factors=practice),)); result=build_context_priority_for_epoch(user=run.user,assessment_run=run,protocol_stable_ids=(protocol.stable_id,)); assert first_personal.created and not second_personal.created and first_personal.revision.pk == second_personal.revision.pk; assert first_context.assessment_created and first_context.practice_created == (True,); assert not second_context.assessment_created and second_context.practice_created == (False,); assert result.primary_protocol_stable_id == protocol.stable_id and len(result.content_hash) == 64'

printf '\n==> Replay valid optional state without exposing private authored values\n'
"$python_bin" manage.py verify_m6c_pilot_readiness
"$python_bin" manage.py verify_m6c_pilot_readiness --json >/dev/null
"$python_bin" manage.py migrate --check

printf '\nM6C pilot-readiness verification passed.\n'
