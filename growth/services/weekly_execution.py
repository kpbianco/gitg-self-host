from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone

from growth.domain.evidence_dispatch import replay_evidence_by_version
from growth.domain.weekly_execution import (
    MAX_WEEKLY_SNAPSHOT_BYTES,
    WEEKLY_EXECUTION_CONTRACT_VERSION,
    WEEKLY_EXECUTION_READINESS_CONTRACT_VERSION,
    CanonicalWeeklySnapshot,
    WeeklyAdjustment,
    WeeklyNextStep,
    build_weekly_plan_snapshot,
    build_weekly_review_snapshot,
    current_week_start,
    week_end,
)
from growth.models import (
    AssessmentRun,
    EvidenceEvent,
    PracticeAction,
    PracticeSprint,
    WeeklyExecutionPlan,
    WeeklyExecutionReview,
)
from growth.services.evidence import EvidenceWorkflowError, verify_evidence_event


class WeeklyExecutionServiceError(ValueError):
    pass


class WeeklyExecutionWriteConflictError(WeeklyExecutionServiceError):
    retryable = True


class WeeklyExecutionReadinessError(ValueError):
    pass


@dataclass(frozen=True)
class WeeklyPlanWriteResult:
    plan: WeeklyExecutionPlan
    created: bool


@dataclass(frozen=True)
class WeeklyReviewWriteResult:
    review: WeeklyExecutionReview
    created: bool


@dataclass(frozen=True)
class WeeklyExecutionReadinessSummary:
    contract_version: str
    weekly_execution_contract_version: str
    plans: int
    reviews: int
    assessment_epochs_with_plans: int
    exact_replayed_proof_events: int
    maximum_snapshot_bytes: int
    software_ready: bool
    changes_evidence: bool
    changes_score_state: bool
    changes_recommendation_order: bool
    changes_practice_completion: bool
    requires_human_gate: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_scope(*, user, assessment_run: AssessmentRun) -> None:
    if not getattr(user, "is_authenticated", False) or user.pk is None:
        raise WeeklyExecutionServiceError("Weekly execution requires an authenticated user.")
    if assessment_run.user_id != user.pk:
        raise WeeklyExecutionServiceError("Weekly execution user must own the assessment epoch.")


def current_window(*, today: date | None = None) -> tuple[date, date]:
    resolved = today or timezone.localdate()
    start = current_week_start(resolved)
    return start, week_end(start)


def latest_weekly_plan(
    *,
    user,
    assessment_run: AssessmentRun,
    week_start: date,
) -> WeeklyExecutionPlan | None:
    _validate_scope(user=user, assessment_run=assessment_run)
    return (
        WeeklyExecutionPlan.objects.filter(
            user=user,
            assessment_run=assessment_run,
            week_start=week_start,
        )
        .select_related("sprint__protocol", "action")
        .order_by("-revision")
        .first()
    )


def latest_unreviewed_plan(*, user, assessment_run: AssessmentRun) -> WeeklyExecutionPlan | None:
    _validate_scope(user=user, assessment_run=assessment_run)
    plans = (
        WeeklyExecutionPlan.objects.filter(
            user=user,
            assessment_run=assessment_run,
        )
        .select_related("sprint__protocol", "action", "review")
        .order_by("-week_start", "-revision")
    )
    seen_windows = set()
    for plan in plans:
        if plan.week_start in seen_windows:
            continue
        seen_windows.add(plan.week_start)
        if not hasattr(plan, "review"):
            return plan
    return None


def _plan_snapshot(
    *,
    assessment_run: AssessmentRun,
    sprint: PracticeSprint,
    action: PracticeAction,
    week_start,
    intended_on,
) -> CanonicalWeeklySnapshot:
    return build_weekly_plan_snapshot(
        assessment_epoch_id=assessment_run.pk,
        sprint_id=str(sprint.pk),
        protocol_stable_id=sprint.protocol_id,
        action_stable_id=action.pk,
        week_start=week_start,
        intended_on=intended_on,
    )


def record_weekly_plan(
    *,
    user,
    assessment_run: AssessmentRun,
    sprint: PracticeSprint,
    action: PracticeAction,
    week_start: date,
    intended_on: date,
    today: date | None = None,
) -> WeeklyPlanWriteResult:
    _validate_scope(user=user, assessment_run=assessment_run)
    expected_start, _ = current_window(today=today)
    if week_start != expected_start:
        raise WeeklyExecutionServiceError(
            "The weekly window changed. Reload before saving the plan."
        )
    snapshot = _plan_snapshot(
        assessment_run=assessment_run,
        sprint=sprint,
        action=action,
        week_start=week_start,
        intended_on=intended_on,
    )
    attempted_revision = 1
    try:
        with transaction.atomic():
            locked_run = AssessmentRun.objects.select_for_update().get(pk=assessment_run.pk)
            _validate_scope(user=user, assessment_run=locked_run)
            locked_sprint = (
                PracticeSprint.objects.select_for_update()
                .select_related("protocol", "assessment_run")
                .get(pk=sprint.pk)
            )
            if locked_sprint.user_id != user.pk:
                raise WeeklyExecutionServiceError("Weekly plan user must own the practice sprint.")
            if locked_sprint.assessment_run_id != locked_run.pk:
                raise WeeklyExecutionServiceError(
                    "Weekly plan sprint must belong to the current assessment epoch."
                )
            if locked_sprint.status != PracticeSprint.Status.ACTIVE:
                raise WeeklyExecutionServiceError(
                    "Create a weekly plan only while the selected practice is active."
                )
            locked_action = PracticeAction.objects.select_related("protocol").get(pk=action.pk)
            if locked_action.protocol_id != locked_sprint.protocol_id:
                raise WeeklyExecutionServiceError(
                    "Weekly plan action must belong to the active practice."
                )
            snapshot = _plan_snapshot(
                assessment_run=locked_run,
                sprint=locked_sprint,
                action=locked_action,
                week_start=week_start,
                intended_on=intended_on,
            )
            latest = latest_weekly_plan(
                user=user,
                assessment_run=locked_run,
                week_start=week_start,
            )
            if latest is not None and latest.content_hash == snapshot.content_hash:
                return WeeklyPlanWriteResult(plan=latest, created=False)
            attempted_revision = 1 if latest is None else latest.revision + 1
            plan = WeeklyExecutionPlan(
                user=user,
                assessment_run=locked_run,
                sprint=locked_sprint,
                action=locked_action,
                contract_version=WEEKLY_EXECUTION_CONTRACT_VERSION,
                week_start=week_start,
                revision=attempted_revision,
                intended_on=intended_on,
                canonical_snapshot=snapshot.payload,
                content_hash=snapshot.content_hash,
            )
            plan.save(force_insert=True)
            return WeeklyPlanWriteResult(plan=plan, created=True)
    except IntegrityError as exc:
        winner = (
            WeeklyExecutionPlan.objects.filter(
                assessment_run=assessment_run,
                week_start=week_start,
                revision=attempted_revision,
            )
            .select_related("sprint__protocol", "action")
            .first()
        )
        if winner is not None and winner.content_hash == snapshot.content_hash:
            return WeeklyPlanWriteResult(plan=winner, created=False)
        raise WeeklyExecutionWriteConflictError(
            "A concurrent weekly plan was recorded; retry from the latest revision."
        ) from exc
    except OperationalError as exc:
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            raise WeeklyExecutionWriteConflictError(
                "The weekly execution store is busy; retry the write."
            ) from exc
        raise


def _window_bounds(plan: WeeklyExecutionPlan) -> tuple[datetime, datetime]:
    current_timezone = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(plan.week_start, time.min), current_timezone)
    end = timezone.make_aware(
        datetime.combine(plan.week_start + timedelta(days=7), time.min),
        current_timezone,
    )
    return start, end


def proof_events_for_plan(
    plan: WeeklyExecutionPlan,
    *,
    through: datetime | None = None,
) -> tuple[dict[str, Any], ...]:
    start, end = _window_bounds(plan)
    after = max(start, plan.created_at)
    filters = {
        "check_in__sprint_id": plan.sprint_id,
        "check_in__action_id": plan.action_id,
        "check_in__submitted_at__gte": after,
        "check_in__submitted_at__lt": end,
    }
    if through is not None:
        if timezone.is_naive(through):
            raise WeeklyExecutionServiceError("Weekly proof cutoff must include a timezone.")
        filters["check_in__submitted_at__lte"] = through
    events = (
        EvidenceEvent.objects.filter(**filters)
        .select_related("check_in__sprint", "check_in__action")
        .order_by("check_in__submitted_at", "stable_id")
    )
    proof = []
    for event in events:
        try:
            verify_evidence_event(event)
            replayed = replay_evidence_by_version(event.algorithm_version, event.input_snapshot)
        except (EvidenceWorkflowError, ValueError, TypeError) as exc:
            raise WeeklyExecutionServiceError(
                f"Weekly proof event {event.pk} failed deterministic replay."
            ) from exc
        proof.append(
            {
                "action_completed": event.check_in.action_completed,
                "action_attempted": event.check_in.action_attempted,
                "adverse": bool(getattr(replayed, "adverse", False)),
                "algorithm_version": event.algorithm_version,
                "direction": event.input_snapshot.get("evidence_direction") or "not_recorded",
                "event_id": str(event.pk),
                "submitted_at": event.check_in.submitted_at.isoformat(),
                "withholding_reasons": list(getattr(replayed, "withholding_reasons", ())),
            }
        )
    return tuple(proof)


def record_weekly_review(
    *,
    user,
    plan: WeeklyExecutionPlan,
    next_step: WeeklyNextStep | str,
    adjustment: WeeklyAdjustment | str,
) -> WeeklyReviewWriteResult:
    snapshot: CanonicalWeeklySnapshot | None = None
    try:
        with transaction.atomic():
            locked = (
                WeeklyExecutionPlan.objects.select_for_update()
                .select_related("assessment_run", "sprint__protocol", "action")
                .get(pk=plan.pk)
            )
            _validate_scope(user=user, assessment_run=locked.assessment_run)
            if locked.user_id != user.pk:
                raise WeeklyExecutionServiceError("Weekly review user must own the weekly plan.")
            latest_revision = (
                WeeklyExecutionPlan.objects.filter(
                    assessment_run=locked.assessment_run,
                    week_start=locked.week_start,
                )
                .order_by("-revision")
                .values_list("revision", flat=True)
                .first()
            )
            if locked.revision != latest_revision:
                raise WeeklyExecutionServiceError(
                    "Only the latest weekly plan revision can be reviewed."
                )
            existing = WeeklyExecutionReview.objects.filter(plan=locked).first()
            reviewed_at = existing.submitted_at if existing is not None else timezone.now()
            proof = proof_events_for_plan(locked, through=reviewed_at)
            snapshot = build_weekly_review_snapshot(
                plan_stable_id=str(locked.pk),
                plan_content_hash=locked.content_hash,
                proof_events=proof,
                reviewed_at=reviewed_at,
                next_step=next_step,
                adjustment=adjustment,
            )
            if existing is not None:
                if existing.content_hash == snapshot.content_hash:
                    return WeeklyReviewWriteResult(review=existing, created=False)
                raise WeeklyExecutionWriteConflictError(
                    "This weekly plan already has an immutable review."
                )
            review = WeeklyExecutionReview(
                user=user,
                plan=locked,
                contract_version=WEEKLY_EXECUTION_CONTRACT_VERSION,
                outcome=snapshot.payload["outcome"],
                next_step=snapshot.payload["next_step"],
                adjustment=snapshot.payload["adjustment"],
                canonical_snapshot=snapshot.payload,
                content_hash=snapshot.content_hash,
                submitted_at=reviewed_at,
            )
            review.save(force_insert=True)
            return WeeklyReviewWriteResult(review=review, created=True)
    except IntegrityError as exc:
        winner = WeeklyExecutionReview.objects.filter(plan_id=plan.pk).first()
        if (
            winner is not None
            and snapshot is not None
            and winner.content_hash == snapshot.content_hash
        ):
            return WeeklyReviewWriteResult(review=winner, created=False)
        raise WeeklyExecutionWriteConflictError(
            "A concurrent weekly review was recorded; reload the completed review."
        ) from exc
    except OperationalError as exc:
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            raise WeeklyExecutionWriteConflictError(
                "The weekly execution store is busy; retry the write."
            ) from exc
        raise


def _verify_plan_snapshot(plan: WeeklyExecutionPlan) -> None:
    rebuilt = _plan_snapshot(
        assessment_run=plan.assessment_run,
        sprint=plan.sprint,
        action=plan.action,
        week_start=plan.week_start,
        intended_on=plan.intended_on,
    )
    if plan.canonical_snapshot != rebuilt.payload or plan.content_hash != rebuilt.content_hash:
        raise WeeklyExecutionReadinessError(
            "A weekly plan failed deterministic snapshot verification."
        )


def verify_weekly_execution_readiness() -> WeeklyExecutionReadinessSummary:
    plans = tuple(
        WeeklyExecutionPlan.objects.select_related(
            "assessment_run", "sprint__protocol", "action"
        ).order_by("assessment_run_id", "week_start", "revision")
    )
    revisions: dict[tuple[str, date], list[int]] = {}
    for plan in plans:
        try:
            plan.full_clean()
            _verify_plan_snapshot(plan)
        except (ValidationError, ValueError, TypeError):
            raise WeeklyExecutionReadinessError(
                "A weekly plan failed version, ownership, linkage, or snapshot validation."
            ) from None
        if len(json_bytes(plan.canonical_snapshot)) > MAX_WEEKLY_SNAPSHOT_BYTES:
            raise WeeklyExecutionReadinessError("A weekly plan exceeds the snapshot bound.")
        revisions.setdefault((plan.assessment_run_id, plan.week_start), []).append(plan.revision)
    if any(actual != list(range(1, len(actual) + 1)) for actual in revisions.values()):
        raise WeeklyExecutionReadinessError(
            "Weekly plan revisions are not contiguous from 1 for a weekly window."
        )

    replayed_events = 0
    reviews = tuple(
        WeeklyExecutionReview.objects.select_related(
            "plan__assessment_run", "plan__sprint__protocol", "plan__action"
        ).order_by("plan__assessment_run_id", "plan__week_start", "plan__revision")
    )
    for review in reviews:
        try:
            review.full_clean()
            proof = proof_events_for_plan(review.plan, through=review.submitted_at)
            rebuilt = build_weekly_review_snapshot(
                plan_stable_id=str(review.plan_id),
                plan_content_hash=review.plan.content_hash,
                proof_events=proof,
                reviewed_at=review.submitted_at,
                next_step=review.next_step,
                adjustment=review.adjustment,
            )
        except (ValidationError, ValueError, TypeError, WeeklyExecutionServiceError):
            raise WeeklyExecutionReadinessError(
                "A weekly review failed version, ownership, proof replay, or snapshot validation."
            ) from None
        if (
            review.canonical_snapshot != rebuilt.payload
            or review.content_hash != rebuilt.content_hash
        ):
            raise WeeklyExecutionReadinessError(
                "A weekly review failed deterministic proof snapshot verification."
            )
        replayed_events += len(proof)

    return WeeklyExecutionReadinessSummary(
        contract_version=WEEKLY_EXECUTION_READINESS_CONTRACT_VERSION,
        weekly_execution_contract_version=WEEKLY_EXECUTION_CONTRACT_VERSION,
        plans=len(plans),
        reviews=len(reviews),
        assessment_epochs_with_plans=len({plan.assessment_run_id for plan in plans}),
        exact_replayed_proof_events=replayed_events,
        maximum_snapshot_bytes=MAX_WEEKLY_SNAPSHOT_BYTES,
        software_ready=True,
        changes_evidence=False,
        changes_score_state=False,
        changes_recommendation_order=False,
        changes_practice_completion=False,
        requires_human_gate=False,
    )


def json_bytes(payload: dict[str, Any]) -> bytes:
    import json

    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
