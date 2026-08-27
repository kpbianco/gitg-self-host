#!/usr/bin/env bash
set -Eeuo pipefail

readonly repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

for required_command in docker curl python3; do
    if ! command -v "$required_command" >/dev/null 2>&1; then
        printf 'Required command is unavailable: %s\n' "$required_command" >&2
        exit 1
    fi
done
docker compose version

readonly probe_dir="$(mktemp -d "${TMPDIR:-/tmp}/grounded-growth-compose-smoke.XXXXXX")"
readonly initial_env="$probe_dir/initial.env"
readonly changed_env="$probe_dir/changed.env"
readonly project_name="ggsmoke${GITHUB_RUN_ID:-local}${GITHUB_RUN_ATTEMPT:-0}$$"
readonly username="compose-probe"
readonly original_password="Original-probe-password-47!"
readonly persisted_password="Persisted-probe-password-58!"
readonly changed_env_password="Changed-env-password-69!"
readonly backup_path="/data/backups/compose-smoke.sqlite3"
readonly expected_counts="37,383,1403,383,383,383,37"

if [[ -n "${SMOKE_APP_PORT:-}" ]]; then
    readonly app_port="$SMOKE_APP_PORT"
else
    readonly app_port="$(
        python3 -c \
            'import socket; sock = socket.socket(); sock.bind(("127.0.0.1", 0)); print(sock.getsockname()[1]); sock.close()'
    )"
fi
readonly base_url="http://127.0.0.1:$app_port"

write_env() {
    local path="$1"
    local password="$2"
    {
        printf 'APP_PORT=%s\n' "$app_port"
        printf 'DJANGO_SECRET_KEY=compose-smoke-only-secret-key-with-sufficient-length-47\n'
        printf 'DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1\n'
        printf 'APP_BOOTSTRAP_USERNAME=%s\n' "$username"
        printf 'APP_BOOTSTRAP_PASSWORD=%s\n' "$password"
        printf 'APP_TIME_ZONE=UTC\n'
        printf 'APP_DEBUG=false\n'
        printf 'APP_SECURE_COOKIES=false\n'
        printf 'GUNICORN_WORKERS=1\n'
    } >"$path"
}

write_env "$initial_env" "$original_password"
write_env "$changed_env" "$changed_env_password"
active_env="$initial_env"

compose() {
    APP_ENV_FILE="$active_env" APP_PORT="$app_port" \
        docker compose --project-name "$project_name" "$@"
}

cleanup() {
    local status=$?
    trap - EXIT
    if ((status != 0)); then
        printf '\nCompose verification failed; final service state and logs follow.\n' >&2
        compose ps >&2 || true
        compose logs --no-color app >&2 || true
    fi
    if [[ "$project_name" == ggsmoke* ]]; then
        compose down --volumes --remove-orphans >/dev/null 2>&1 || true
    fi
    rm -f -- "$initial_env" "$changed_env"
    rmdir "$probe_dir" 2>/dev/null || true
    exit "$status"
}
trap cleanup EXIT

http_probe() {
    local password="$1"
    local expectation="$2"
    local boundary_option=()
    if [[ "$expectation" == "failure" ]]; then
        boundary_option=(--skip-public-boundary)
    fi
    python3 scripts/verify_http_login.py \
        --base-url "$base_url" \
        --username "$username" \
        --password "$password" \
        --expect "$expectation" \
        --authenticated-path "/personal-os/" \
        "${boundary_option[@]}"
}

canonical_counts() {
    compose exec -T app python manage.py shell -c \
        'from growth.models import Competency, CompetencyLeverLink, Lever, LeverBaseline, PracticeProtocol; print(",".join(str(value) for value in (Lever.objects.count(), Competency.objects.count(), CompetencyLeverLink.objects.count(), PracticeProtocol.objects.count(), PracticeProtocol.objects.filter(availability=PracticeProtocol.Availability.ACTIVE).count(), PracticeProtocol.objects.filter(score_active=True).count(), LeverBaseline.objects.count())))' \
        | tail -n 1
}

browser_slice_state() {
    compose exec -T app python manage.py shell -c \
        'import hashlib; from growth.models import AssessmentContext, AssessmentRun, PersonalOSRevision, PracticeContext, PracticeProtocol, WeeklyExecutionPlan, WeeklyExecutionReview; from growth.services.context_priority import build_context_priority_for_epoch; run=AssessmentRun.objects.select_related("user").order_by("stable_id").first(); personal=tuple(PersonalOSRevision.objects.order_by("assessment_run_id","revision").values_list("content_hash",flat=True)); assessment=tuple(AssessmentContext.objects.order_by("assessment_run_id","revision").values_list("content_hash",flat=True)); practice=tuple(PracticeContext.objects.order_by("assessment_run_id","protocol_id","revision").values_list("content_hash",flat=True)); weekly_plans=tuple(WeeklyExecutionPlan.objects.order_by("assessment_run_id","week_start","revision").values_list("content_hash",flat=True)); weekly_reviews=tuple(WeeklyExecutionReview.objects.order_by("plan_id").values_list("content_hash",flat=True)); priority=build_context_priority_for_epoch(user=run.user,assessment_run=run,protocol_stable_ids=("PRACTICE-FRIENDSHIP-01",)); active=tuple(PracticeProtocol.objects.filter(score_active=True).order_by("stable_id").values_list("stable_id",flat=True)); active_hash=hashlib.sha256(chr(44).join(active).encode()).hexdigest(); print("|".join((f"personal={len(personal)}:{chr(44).join(personal)}",f"assessment={len(assessment)}:{chr(44).join(assessment)}",f"practice={len(practice)}:{chr(44).join(practice)}",f"weekly_plans={len(weekly_plans)}:{chr(44).join(weekly_plans)}",f"weekly_reviews={len(weekly_reviews)}:{chr(44).join(weekly_reviews)}",f"priority={priority.content_hash}",f"score_active={len(active)}:{active_hash}")))' \
        | tail -n 1
}

printf '\n==> Build and start the isolated application stack\n'
compose up -d --build --wait --wait-timeout 180
container_id="$(compose ps -q app)"
test -n "$container_id"
test "$(docker inspect --format '{{.State.Health.Status}}' "$container_id")" = "healthy"
test "$(compose exec -T app id -u | tr -d '\r')" = "10001"
http_probe "$original_password" success

printf '\n==> Verify migrations, canonical seed idempotency, and score-state replay\n'
compose exec -T app python manage.py migrate --check
before_counts="$(canonical_counts)"
compose exec -T app python manage.py seed_canonical
compose exec -T app python manage.py seed_canonical
after_counts="$(canonical_counts)"
test "$before_counts" = "$after_counts"
test "$after_counts" = "$expected_counts"
compose exec -T app python manage.py verify_evidence_events
compose exec -T app python manage.py rebuild_score_state --verify-only
compose exec -T app python manage.py generate_competency_evidence_reports --check
compose exec -T app python manage.py verify_pilot_readiness
compose exec -T app python manage.py verify_expansion_readiness
compose exec -T app python manage.py verify_competency_evidence_readiness
compose exec -T app python manage.py verify_context_readiness
compose exec -T app python manage.py verify_personal_os_readiness
compose exec -T app python manage.py verify_context_priority_readiness
compose exec -T app python manage.py verify_m6c_pilot_readiness
compose exec -T app python manage.py verify_m6d_authoring_readiness
compose exec -T app python manage.py verify_weekly_execution_readiness

printf '\n==> Persist synthetic Personal OS and context revisions through public services\n'
compose exec -T app python manage.py shell -c \
    'from growth.domain.context import ContextFactorValue; from growth.models import AssessmentRun, PracticeProtocol; from growth.services.context import PracticeContextInput, record_context_bundle; from growth.services.context_priority import build_context_priority_for_epoch; from growth.services.personal_os import record_personal_os_revision; run=AssessmentRun.objects.select_related("user").order_by("stable_id").first(); protocol=PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01"); state={"state":"provided"}; identity={"mission":{**state,"value":"Synthetic Compose direction."},"principles":{**state,"value":["Synthetic bounded operation."]},"anti_goals":{**state,"value":["Synthetic unrecoverable state."]},"twelve_month_direction":{**state,"value":"Synthetic recovery remains exact."},"priority_stack":{**state,"value":["Synthetic backup proof."]}}; audit={key:{**state,"value":"Synthetic descriptive response."} for key in ("current_truth","autopilot_pattern","misalignment_or_fragmentation","deliberate_next_step")}; first_personal=record_personal_os_revision(user=run.user,assessment_run=run,identity_sections=identity,audit_responses=audit); second_personal=record_personal_os_revision(user=run.user,assessment_run=run,identity_sections=identity,audit_responses=audit); provided=lambda value: ContextFactorValue("provided",value); assessment={"season":provided("foundation"),"capacity":provided(3)}; practice={key:provided(value) for key,value in (("applicability",4),("importance",3),("readiness",3),("urgency",2),("opportunity_resources",3),("burden",1))}; first_context=record_context_bundle(user=run.user,assessment_run=run,assessment_factors=assessment,practice_inputs=(PracticeContextInput(protocol=protocol,factors=practice),)); second_context=record_context_bundle(user=run.user,assessment_run=run,assessment_factors=assessment,practice_inputs=(PracticeContextInput(protocol=protocol,factors=practice),)); result=build_context_priority_for_epoch(user=run.user,assessment_run=run,protocol_stable_ids=(protocol.stable_id,)); assert first_personal.created and not second_personal.created and first_personal.revision.pk == second_personal.revision.pk; assert first_context.assessment_created and first_context.practice_created == (True,); assert not second_context.assessment_created and second_context.practice_created == (False,); assert result.primary_protocol_stable_id == protocol.stable_id and len(result.content_hash) == 64'
compose exec -T app python manage.py shell -c \
    'from django.utils import timezone; from growth.models import AssessmentRun, PracticeProtocol; from growth.services.practice import start_practice; from growth.services.weekly_execution import current_window, record_weekly_plan, record_weekly_review; run=AssessmentRun.objects.select_related("user").order_by("stable_id").first(); protocol=PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01"); sprint=start_practice(user=run.user,protocol=protocol,person_or_context="Synthetic Compose weekly context",start_date=timezone.localdate()); action=protocol.actions.order_by("sequence").first(); week_start,_=current_window(); plan=record_weekly_plan(user=run.user,assessment_run=run,sprint=sprint,action=action,week_start=week_start,intended_on=week_start); review=record_weekly_review(user=run.user,plan=plan.plan,next_step="continue_current",adjustment="none"); assert plan.created and review.created and review.review.outcome == "no_submitted_evidence"'
compose exec -T app python manage.py verify_m6c_pilot_readiness
compose exec -T app python manage.py verify_m6d_authoring_readiness
compose exec -T app python manage.py verify_weekly_execution_readiness
readonly expected_browser_slice_state="$(browser_slice_state)"
[[ "$expected_browser_slice_state" =~ ^personal=1:[0-9a-f]{64}\|assessment=1:[0-9a-f]{64}\|practice=1:[0-9a-f]{64}\|weekly_plans=1:[0-9a-f]{64}\|weekly_reviews=1:[0-9a-f]{64}\|priority=[0-9a-f]{64}\|score_active=383:[0-9a-f]{64}$ ]]

printf '\n==> Create and integrity-check an online SQLite backup\n'
compose exec -T app python manage.py backup_database --output "$backup_path"
compose exec -T app python -c \
    'import sqlite3; connection = sqlite3.connect("/data/backups/compose-smoke.sqlite3"); result = connection.execute("PRAGMA integrity_check").fetchone()[0]; connection.close(); assert result == "ok", result; print(result)'

printf '\n==> Prove volume and one-time bootstrap persistence across recreation\n'
compose exec -T -e DEPLOYMENT_PROBE_PASSWORD="$persisted_password" app \
    python manage.py shell -c \
    'import os; from django.contrib.auth import get_user_model; user = get_user_model().objects.get(username="compose-probe"); user.set_password(os.environ["DEPLOYMENT_PROBE_PASSWORD"]); user.save(update_fields=["password"])'
active_env="$changed_env"
compose up -d --force-recreate --wait --wait-timeout 180
http_probe "$persisted_password" success
http_probe "$changed_env_password" failure
test "$(canonical_counts)" = "$expected_counts"
compose exec -T app python manage.py migrate --check
compose exec -T app python manage.py rebuild_score_state --verify-only
compose exec -T app python manage.py verify_pilot_readiness
compose exec -T app python manage.py verify_expansion_readiness
compose exec -T app python manage.py verify_competency_evidence_readiness
compose exec -T app python manage.py verify_context_readiness
compose exec -T app python manage.py verify_personal_os_readiness
compose exec -T app python manage.py verify_context_priority_readiness
compose exec -T app python manage.py verify_m6c_pilot_readiness
compose exec -T app python manage.py verify_m6d_authoring_readiness
compose exec -T app python manage.py verify_weekly_execution_readiness
test "$(browser_slice_state)" = "$expected_browser_slice_state"

printf '\n==> Restore the verified backup inside the isolated volume\n'
compose down
compose run --rm --no-deps --entrypoint python app -c \
    'from pathlib import Path; import shutil; source = Path("/data/backups/compose-smoke.sqlite3"); target = Path("/data/grounded_growth.sqlite3"); shutil.copy2(source, target); target.with_name(target.name + "-wal").unlink(missing_ok=True); target.with_name(target.name + "-shm").unlink(missing_ok=True)'
compose up -d --wait --wait-timeout 180
http_probe "$original_password" success
http_probe "$persisted_password" failure
http_probe "$changed_env_password" failure
test "$(canonical_counts)" = "$expected_counts"
compose exec -T app python manage.py rebuild_score_state --verify-only
compose exec -T app python manage.py verify_pilot_readiness
compose exec -T app python manage.py verify_expansion_readiness
compose exec -T app python manage.py verify_competency_evidence_readiness
compose exec -T app python manage.py verify_context_readiness
compose exec -T app python manage.py verify_personal_os_readiness
compose exec -T app python manage.py verify_context_priority_readiness
compose exec -T app python manage.py verify_m6c_pilot_readiness
compose exec -T app python manage.py verify_m6d_authoring_readiness
compose exec -T app python manage.py verify_weekly_execution_readiness
test "$(browser_slice_state)" = "$expected_browser_slice_state"

printf '\n==> Confirm clean Gunicorn shutdown\n'
compose stop --timeout 30 app
test "$(docker inspect --format '{{.State.ExitCode}}' "$(compose ps -a -q app)")" = "0"

printf '\nDocker Compose deployment verification passed.\n'
