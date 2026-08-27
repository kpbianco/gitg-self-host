#!/usr/bin/env bash
set -Eeuo pipefail

readonly repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

readonly python_bin="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$python_bin" ]] && ! command -v "$python_bin" >/dev/null 2>&1; then
    printf 'Python executable is unavailable: %s\n' "$python_bin" >&2
    exit 1
fi

readonly probe_dir="$(mktemp -d "${TMPDIR:-/tmp}/grounded-growth-weekly.XXXXXX")"

cleanup() {
    local status=$?
    trap - EXIT
    if [[ "$probe_dir" == "${TMPDIR:-/tmp}"/grounded-growth-weekly.* ]]; then
        rm -rf -- "$probe_dir"
    fi
    exit "$status"
}
trap cleanup EXIT

export APP_DATA_DIR="$probe_dir"
export DJANGO_SECRET_KEY="weekly-execution-readiness-secret-key-with-sufficient-length-47"
export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"
export APP_BOOTSTRAP_USERNAME="weekly-execution-readiness"
export APP_BOOTSTRAP_PASSWORD="Quasar-River-Copper-Drill-47!"
export APP_TIME_ZONE="UTC"
export APP_DEBUG="true"
export APP_SECURE_COOKIES="false"

printf '\n==> Build isolated migrated and idempotently seeded state\n'
"$python_bin" manage.py migrate --noinput
"$python_bin" manage.py migrate --noinput
"$python_bin" manage.py bootstrap_user
"$python_bin" manage.py seed_canonical
"$python_bin" manage.py seed_canonical
"$python_bin" manage.py rebuild_score_state

printf '\n==> Verify empty optional weekly state\n'
"$python_bin" manage.py verify_weekly_execution_readiness

printf '\n==> Exercise append-only planning, exact proof, and immutable review\n'
"$python_bin" manage.py shell -c \
    'from django.utils import timezone; from growth.models import AssessmentRun, PracticeCheckIn, PracticeProtocol; from growth.services.practice import save_check_in, start_practice; from growth.services.weekly_execution import current_window, record_weekly_plan, record_weekly_review; run=AssessmentRun.objects.select_related("user").order_by("stable_id").first(); protocol=PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01"); sprint=start_practice(user=run.user,protocol=protocol,person_or_context="Synthetic weekly readiness",start_date=timezone.localdate()); action=protocol.actions.order_by("sequence").first(); week_start,_=current_window(); first=record_weekly_plan(user=run.user,assessment_run=run,sprint=sprint,action=action,week_start=week_start,intended_on=week_start); retry=record_weekly_plan(user=run.user,assessment_run=run,sprint=sprint,action=action,week_start=week_start,intended_on=week_start); assert first.created and not retry.created and first.plan.pk == retry.plan.pk; save_check_in(sprint=sprint,cleaned_data={"action":action,"action_attempted":True,"action_completed":True,"support_level":PracticeCheckIn.SupportLevel.INDEPENDENT,"context_comparison":PracticeCheckIn.ContextComparison.FIRST_RECORD,"evidence_direction":PracticeCheckIn.EvidenceDirection.SUPPORTS},submit=True); review=record_weekly_review(user=run.user,plan=first.plan,next_step="plan_next_action",adjustment="none"); review_retry=record_weekly_review(user=run.user,plan=first.plan,next_step="plan_next_action",adjustment="none"); assert review.created and not review_retry.created and review.review.pk == review_retry.review.pk and review.review.outcome == "completed"'

printf '\n==> Replay weekly state and preserved scoring/runtime readiness\n'
"$python_bin" manage.py verify_weekly_execution_readiness
"$python_bin" manage.py verify_evidence_events
"$python_bin" manage.py rebuild_score_state --verify-only
"$python_bin" manage.py verify_m6d_authoring_readiness
"$python_bin" manage.py migrate --check

printf '\nWeekly execution readiness verification passed.\n'
