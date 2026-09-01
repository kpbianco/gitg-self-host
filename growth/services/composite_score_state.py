from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from growth.domain.composite_scoring import (
    ALGORITHM_VERSION,
    STATE_SCHEMA_VERSION,
    CompetencyProjectionInput,
    CompositeScoringError,
    CompositeScoringPolicy,
    LeverAssessmentInput,
    build_assessment_projection,
    build_completion_state,
    canonical_hash,
    closeout_credit,
    policy_from_contract,
)
from growth.models import (
    AssessmentRun,
    Competency,
    CompletionCreditEvent,
    CompositeAssessmentSnapshot,
    CompositeScoreSnapshot,
    CompositeScoreState,
    LeverBaseline,
    PracticeCheckIn,
    PracticeReview,
    PracticeSprint,
)

COMPOSITE_SCORING_CONTRACT_PATH = Path("contracts") / "composite-closeout-scoring.yaml"
COMPOSITE_SCORING_SCHEMA_PATH = Path("contracts") / "composite-closeout-scoring.schema.json"


class CompositeScoreStateError(ValueError):
    pass


@dataclass(frozen=True)
class CompositeRunSyncResult:
    assessment_run: AssessmentRun
    initialized: bool
    events_processed: int
    rebuilt: bool


@dataclass(frozen=True)
class CompositeStateSyncSummary:
    assessment_runs: int
    states_initialized: int
    events_processed: int
    rebuilds_created: int


@dataclass(frozen=True)
class CompositeStateVerificationSummary:
    assessment_runs: int


@lru_cache(maxsize=1)
def load_composite_scoring_policy() -> CompositeScoringPolicy:
    path = settings.BASE_DIR / COMPOSITE_SCORING_CONTRACT_PATH
    try:
        contract = yaml.safe_load(path.read_text())
        schema = json.loads((settings.BASE_DIR / COMPOSITE_SCORING_SCHEMA_PATH).read_text())
        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(schema).iter_errors(contract),
            key=lambda item: list(item.path),
        )
        if errors:
            raise CompositeScoringError(
                "Schema validation failed: " + "; ".join(error.message for error in errors[:8])
            )
        return policy_from_contract(contract)
    except (
        OSError,
        json.JSONDecodeError,
        yaml.YAMLError,
        SchemaError,
        CompositeScoringError,
    ) as exc:
        raise CompositeScoreStateError(f"Composite scoring contract is invalid: {exc}") from exc


def _without_hash(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = dict(payload)
    value.pop(key, None)
    return value


def _verify_projection_payload(payload: dict[str, Any]) -> None:
    if payload.get("algorithm_version") != ALGORITHM_VERSION:
        raise CompositeScoreStateError("Composite assessment algorithm version is unsupported.")
    if payload.get("state_schema_version") != STATE_SCHEMA_VERSION:
        raise CompositeScoreStateError("Composite assessment state schema is unsupported.")
    expected = canonical_hash(_without_hash(payload, "projection_hash"))
    if payload.get("projection_hash") != expected:
        raise CompositeScoreStateError("Composite assessment projection hash does not verify.")


def _verify_state_payload(payload: dict[str, Any]) -> None:
    if payload.get("algorithm_version") != ALGORITHM_VERSION:
        raise CompositeScoreStateError("Composite state algorithm version is unsupported.")
    if payload.get("state_schema_version") != STATE_SCHEMA_VERSION:
        raise CompositeScoreStateError("Composite state schema is unsupported.")
    expected = canonical_hash(_without_hash(payload, "state_hash"))
    if payload.get("state_hash") != expected:
        raise CompositeScoreStateError("Composite state hash does not verify.")


def _projection_inputs(
    assessment_run: AssessmentRun,
) -> tuple[list[LeverAssessmentInput], list[CompetencyProjectionInput]]:
    baselines = list(
        LeverBaseline.objects.filter(
            assessment_run=assessment_run,
            user=assessment_run.user,
        )
        .select_related("lever")
        .order_by("lever_id")
    )
    competencies = list(
        Competency.objects.filter(curriculum_version=assessment_run.curriculum_version)
        .prefetch_related("lever_links")
        .order_by("stable_id")
    )
    lever_inputs = [
        LeverAssessmentInput(
            lever_id=baseline.lever_id,
            family_id=baseline.lever.family_id,
            estimate=baseline.calibrated_estimate,
            confidence=baseline.evidence_confidence,
        )
        for baseline in baselines
    ]
    competency_inputs = [
        CompetencyProjectionInput(
            competency_id=competency.stable_id,
            domain_id=competency.domain_id,
            canonical_weights={link.lever_id: link.weight for link in competency.lever_links.all()},
        )
        for competency in competencies
    ]
    return lever_inputs, competency_inputs


def project_assessment_run(assessment_run: AssessmentRun) -> dict[str, Any]:
    policy = load_composite_scoring_policy()
    levers, competencies = _projection_inputs(assessment_run)
    try:
        return build_assessment_projection(
            levers=levers,
            competencies=competencies,
            policy=policy,
        )
    except CompositeScoringError as exc:
        raise CompositeScoreStateError(f"{assessment_run.pk}: {exc}") from exc


def _assessment_snapshot(assessment_run: AssessmentRun) -> CompositeAssessmentSnapshot:
    existing = CompositeAssessmentSnapshot.objects.filter(assessment_run=assessment_run).first()
    if existing is not None:
        if (
            existing.algorithm_version != ALGORITHM_VERSION
            or existing.state_schema_version != STATE_SCHEMA_VERSION
            or existing.projection_hash != existing.projection.get("projection_hash")
        ):
            raise CompositeScoreStateError(
                f"{assessment_run.pk}: composite assessment metadata does not match."
            )
        _verify_projection_payload(existing.projection)
        return existing
    projection = project_assessment_run(assessment_run)
    snapshot = CompositeAssessmentSnapshot(
        assessment_run=assessment_run,
        algorithm_version=ALGORITHM_VERSION,
        state_schema_version=STATE_SCHEMA_VERSION,
        projection=projection,
        projection_hash=projection["projection_hash"],
    )
    try:
        snapshot.full_clean()
        snapshot.save()
    except ValidationError as exc:
        raise CompositeScoreStateError("; ".join(exc.messages)) from exc
    return snapshot


def _event_hash(events: list[CompletionCreditEvent]) -> str:
    return canonical_hash([str(event.pk) for event in events])


def _all_events(assessment_run: AssessmentRun) -> list[CompletionCreditEvent]:
    events = list(
        CompletionCreditEvent.objects.filter(assessment_run=assessment_run)
        .select_related("competency", "review", "sprint", "protocol")
        .order_by("created_at", "stable_id")
    )
    for event in events:
        verify_completion_credit_event(event)
    return events


def verify_completion_credit_event(event: CompletionCreditEvent) -> None:
    source = event.source_snapshot
    if event.algorithm_version != ALGORITHM_VERSION:
        raise CompositeScoreStateError("Completion credit algorithm version is unsupported.")
    if event.source_hash != canonical_hash(source):
        raise CompositeScoreStateError("Completion credit source hash does not verify.")
    if (
        event.sprint.assessment_run_id != event.assessment_run_id
        or event.review.sprint_id != event.sprint_id
        or event.sprint.protocol_id != event.protocol_id
        or event.protocol.parent_competency_id != event.competency_id
        or event.sprint.scoring_contract_version != ALGORITHM_VERSION
        or event.sprint.status != PracticeSprint.Status.COMPLETED
    ):
        raise CompositeScoreStateError("Completion credit stable relationships do not match.")
    action_ids = source.get("action_ids")
    completed_action_ids = source.get("completed_action_ids")
    if (
        not isinstance(action_ids, list)
        or not isinstance(completed_action_ids, list)
        or len(action_ids) != len(set(action_ids))
        or len(completed_action_ids) != len(set(completed_action_ids))
        or not set(completed_action_ids).issubset(action_ids)
        or event.completed_action_ids != completed_action_ids
        or event.total_actions != len(action_ids)
        or event.minimum_completed != source.get("minimum_completed")
    ):
        raise CompositeScoreStateError("Completion credit action snapshot does not verify.")
    expected_metadata = {
        "algorithm_version": ALGORITHM_VERSION,
        "assessment_run_id": event.assessment_run_id,
        "sprint_id": str(event.sprint_id),
        "review_id": str(event.review_id),
        "protocol_id": event.protocol_id,
        "competency_id": event.competency_id,
        "action_weighting": "equal",
        "review_actions_attempted": event.review.actions_attempted,
        "review_actions_completed": event.review.actions_completed,
        "review_substantive_interaction": event.review.substantive_interaction_occurred,
    }
    if any(source.get(key) != value for key, value in expected_metadata.items()):
        raise CompositeScoreStateError("Completion credit review snapshot does not verify.")
    if (
        event.review.actions_completed != len(completed_action_ids)
        or not event.review.substantive_interaction_occurred
        or source.get("total_actions") != event.total_actions
    ):
        raise CompositeScoreStateError("Completion credit review totals do not verify.")
    policy = load_composite_scoring_policy()
    try:
        snapshotted_minimum = Decimal(str(source.get("minimum_closeout_credit")))
        snapshotted_full = Decimal(str(source.get("full_closeout_credit")))
        snapshotted_credit = Decimal(str(source.get("completion_credit")))
    except Exception as exc:  # pragma: no cover - Decimal raises several input errors
        raise CompositeScoreStateError(
            "Completion credit numeric snapshot does not verify."
        ) from exc
    if (
        snapshotted_minimum != policy.minimum_closeout_credit
        or snapshotted_full != policy.full_closeout_credit
    ):
        raise CompositeScoreStateError("Completion credit policy snapshot does not verify.")
    try:
        expected_credit = closeout_credit(
            completed_actions=len(completed_action_ids),
            total_actions=event.total_actions,
            minimum_completed=event.minimum_completed,
            policy=policy,
        )
    except CompositeScoringError as exc:
        raise CompositeScoreStateError(str(exc)) from exc
    if event.completion_credit != expected_credit or snapshotted_credit != expected_credit:
        raise CompositeScoreStateError("Completion credit value does not verify.")


def _processed_event_ids(assessment_run: AssessmentRun) -> set[object]:
    return set(
        CompositeScoreSnapshot.objects.filter(
            assessment_run=assessment_run,
            operation=CompositeScoreSnapshot.Operation.PROCESS,
        ).values_list("completion_credit_event_id", flat=True)
    )


def _reversed_event_ids(assessment_run: AssessmentRun) -> set[object]:
    return set(
        CompositeScoreSnapshot.objects.filter(
            assessment_run=assessment_run,
            operation=CompositeScoreSnapshot.Operation.REVERSE,
        ).values_list("completion_credit_event_id", flat=True)
    )


def _active_events(
    assessment_run: AssessmentRun,
    all_events: list[CompletionCreditEvent],
) -> list[CompletionCreditEvent]:
    processed = _processed_event_ids(assessment_run)
    reversed_ids = _reversed_event_ids(assessment_run)
    return [event for event in all_events if event.pk in processed - reversed_ids]


def _credits(events: list[CompletionCreditEvent]) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    for event in events:
        values[event.competency_id] = max(
            values.get(event.competency_id, Decimal("0")),
            event.completion_credit,
        )
    return values


def _desired_state(
    projection: dict[str, Any],
    events: list[CompletionCreditEvent],
) -> dict[str, Any]:
    try:
        return build_completion_state(
            assessment_projection=projection,
            competency_credits=_credits(events),
            policy=load_composite_scoring_policy(),
        )
    except CompositeScoringError as exc:
        raise CompositeScoreStateError(str(exc)) from exc


def _next_sequence(assessment_run: AssessmentRun) -> int:
    latest = (
        CompositeScoreSnapshot.objects.filter(assessment_run=assessment_run)
        .order_by("-sequence")
        .values_list("sequence", flat=True)
        .first()
    )
    return (latest or 0) + 1


def _create_snapshot(
    *,
    assessment_run: AssessmentRun,
    operation: str,
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    active_events: list[CompletionCreditEvent],
    completion_credit_event: CompletionCreditEvent | None = None,
    reason: str = "",
) -> CompositeScoreSnapshot:
    snapshot = CompositeScoreSnapshot(
        assessment_run=assessment_run,
        completion_credit_event=completion_credit_event,
        operation=operation,
        sequence=_next_sequence(assessment_run),
        algorithm_version=ALGORITHM_VERSION,
        state_schema_version=STATE_SCHEMA_VERSION,
        before_state=before_state,
        after_state=after_state,
        active_event_count=len(active_events),
        active_event_hash=_event_hash(active_events),
        before_state_hash=canonical_hash(before_state),
        after_state_hash=canonical_hash(after_state),
        reason=reason,
    )
    try:
        snapshot.full_clean()
        snapshot.save()
    except ValidationError as exc:
        raise CompositeScoreStateError("; ".join(exc.messages)) from exc
    return snapshot


def _write_state(
    state: CompositeScoreState,
    payload: dict[str, Any],
    active_events: list[CompletionCreditEvent],
) -> None:
    _verify_state_payload(payload)
    state.state = payload
    state.state_hash = payload["state_hash"]
    state.active_event_count = len(active_events)
    state.active_event_hash = _event_hash(active_events)
    state.save(
        update_fields=(
            "state",
            "state_hash",
            "active_event_count",
            "active_event_hash",
            "updated_at",
        )
    )


def _initialize_locked(
    assessment_run: AssessmentRun,
    projection: dict[str, Any],
) -> tuple[CompositeScoreState, bool]:
    state = (
        CompositeScoreState.objects.select_for_update()
        .filter(assessment_run=assessment_run)
        .first()
    )
    if state is not None:
        if not CompositeScoreSnapshot.objects.filter(
            assessment_run=assessment_run,
            operation=CompositeScoreSnapshot.Operation.INITIALIZE,
        ).exists():
            raise CompositeScoreStateError(
                f"{assessment_run.pk}: composite state has no initialization snapshot."
            )
        return state, False
    payload = _desired_state(projection, [])
    state = CompositeScoreState.objects.create(
        assessment_run=assessment_run,
        user=assessment_run.user,
        algorithm_version=ALGORITHM_VERSION,
        state_schema_version=STATE_SCHEMA_VERSION,
        state=payload,
        state_hash=payload["state_hash"],
        active_event_count=0,
        active_event_hash=_event_hash([]),
    )
    _create_snapshot(
        assessment_run=assessment_run,
        operation=CompositeScoreSnapshot.Operation.INITIALIZE,
        before_state={},
        after_state=payload,
        active_events=[],
    )
    return state, True


def _process_event_locked(
    *,
    assessment_run: AssessmentRun,
    state: CompositeScoreState,
    projection: dict[str, Any],
    event: CompletionCreditEvent,
    all_events: list[CompletionCreditEvent],
) -> CompositeScoreSnapshot:
    existing = CompositeScoreSnapshot.objects.filter(
        completion_credit_event=event,
        operation=CompositeScoreSnapshot.Operation.PROCESS,
    ).first()
    if existing is not None:
        return existing
    before = state.state
    active = _active_events(assessment_run, all_events)
    active_ids = {item.pk for item in active} | {event.pk}
    active = [item for item in all_events if item.pk in active_ids]
    after = _desired_state(projection, active)
    _write_state(state, after, active)
    return _create_snapshot(
        assessment_run=assessment_run,
        completion_credit_event=event,
        operation=CompositeScoreSnapshot.Operation.PROCESS,
        before_state=before,
        after_state=after,
        active_events=active,
    )


def _repair_locked(
    *,
    assessment_run: AssessmentRun,
    state: CompositeScoreState,
    projection: dict[str, Any],
    all_events: list[CompletionCreditEvent],
) -> bool:
    active = _active_events(assessment_run, all_events)
    desired = _desired_state(projection, active)
    if state.state == desired:
        if (
            state.active_event_count != len(active)
            or state.active_event_hash != _event_hash(active)
            or state.state_hash != desired["state_hash"]
        ):
            before = state.state
            _write_state(state, desired, active)
            _create_snapshot(
                assessment_run=assessment_run,
                operation=CompositeScoreSnapshot.Operation.REBUILD,
                before_state=before,
                after_state=desired,
                active_events=active,
                reason="Deterministic composite-state metadata repair.",
            )
            return True
        return False
    before = state.state
    _write_state(state, desired, active)
    _create_snapshot(
        assessment_run=assessment_run,
        operation=CompositeScoreSnapshot.Operation.REBUILD,
        before_state=before,
        after_state=desired,
        active_events=active,
        reason="Deterministic composite-state repair.",
    )
    return True


@transaction.atomic
def synchronize_composite_score_state_for_run(
    assessment_run: AssessmentRun,
) -> CompositeRunSyncResult:
    locked_run = (
        AssessmentRun.objects.select_for_update()
        .select_related("user", "curriculum_version")
        .get(pk=assessment_run.pk)
    )
    assessment_snapshot = _assessment_snapshot(locked_run)
    state, initialized = _initialize_locked(locked_run, assessment_snapshot.projection)
    all_events = _all_events(locked_run)
    processed = _processed_event_ids(locked_run)
    processed_count = 0
    for event in all_events:
        if event.pk not in processed:
            _process_event_locked(
                assessment_run=locked_run,
                state=state,
                projection=assessment_snapshot.projection,
                event=event,
                all_events=all_events,
            )
            processed.add(event.pk)
            processed_count += 1
    rebuilt = _repair_locked(
        assessment_run=locked_run,
        state=state,
        projection=assessment_snapshot.projection,
        all_events=all_events,
    )
    verify_composite_score_state_for_run(locked_run)
    return CompositeRunSyncResult(
        assessment_run=locked_run,
        initialized=initialized,
        events_processed=processed_count,
        rebuilt=rebuilt,
    )


def synchronize_all_composite_score_states() -> CompositeStateSyncSummary:
    results = [
        synchronize_composite_score_state_for_run(assessment_run)
        for assessment_run in AssessmentRun.objects.select_related(
            "user", "curriculum_version"
        ).order_by("created_at", "stable_id")
    ]
    return CompositeStateSyncSummary(
        assessment_runs=len(results),
        states_initialized=sum(item.initialized for item in results),
        events_processed=sum(item.events_processed for item in results),
        rebuilds_created=sum(item.rebuilt for item in results),
    )


def verify_all_composite_score_states() -> CompositeStateVerificationSummary:
    assessment_runs = list(
        AssessmentRun.objects.select_related("user", "curriculum_version").order_by(
            "created_at", "stable_id"
        )
    )
    for assessment_run in assessment_runs:
        verify_composite_score_state_for_run(assessment_run)
    return CompositeStateVerificationSummary(assessment_runs=len(assessment_runs))


@transaction.atomic
def create_completion_credit_event(review: PracticeReview) -> CompletionCreditEvent:
    locked_review = (
        PracticeReview.objects.select_for_update()
        .select_related(
            "sprint__assessment_run",
            "sprint__protocol__parent_competency",
        )
        .get(pk=review.pk)
    )
    sprint = locked_review.sprint
    if sprint.scoring_contract_version != ALGORITHM_VERSION:
        raise CompositeScoreStateError("This sprint does not use composite closeout scoring.")
    if sprint.status != PracticeSprint.Status.COMPLETED or sprint.assessment_run is None:
        raise CompositeScoreStateError(
            "Completion credit requires a completed assessment-linked sprint."
        )
    if sprint.protocol.parent_competency_id is None:
        raise CompositeScoreStateError("Completion credit requires a parent competency.")
    existing = CompletionCreditEvent.objects.filter(sprint=sprint).first()
    if existing is not None:
        verify_completion_credit_event(existing)
        apply_completion_credit_event(existing)
        return existing

    action_ids = list(
        sprint.protocol.actions.order_by("sequence", "stable_id").values_list(
            "stable_id", flat=True
        )
    )
    completed_action_ids = sorted(
        set(
            sprint.check_ins.filter(
                status=PracticeCheckIn.Status.SUBMITTED,
                action_completed=True,
                action_id__in=action_ids,
            ).values_list("action_id", flat=True)
        )
    )
    attempted_action_ids = sorted(
        set(
            sprint.check_ins.filter(
                status=PracticeCheckIn.Status.SUBMITTED,
                action_attempted=True,
                action_id__in=action_ids,
            ).values_list("action_id", flat=True)
        )
    )
    if (
        locked_review.actions_attempted != len(attempted_action_ids)
        or locked_review.actions_completed != len(completed_action_ids)
        or not locked_review.substantive_interaction_occurred
    ):
        raise CompositeScoreStateError(
            "Completion credit requires review totals and substantive closeout evidence to agree."
        )
    minimum_completed = int(sprint.protocol.completion_rules.get("minimum_completed", 0))
    try:
        policy = load_composite_scoring_policy()
        credit = closeout_credit(
            completed_actions=len(completed_action_ids),
            total_actions=len(action_ids),
            minimum_completed=minimum_completed,
            policy=policy,
        )
    except CompositeScoringError as exc:
        raise CompositeScoreStateError(str(exc)) from exc
    source = {
        "algorithm_version": ALGORITHM_VERSION,
        "assessment_run_id": sprint.assessment_run_id,
        "sprint_id": str(sprint.pk),
        "review_id": str(locked_review.pk),
        "protocol_id": sprint.protocol_id,
        "competency_id": sprint.protocol.parent_competency_id,
        "action_weighting": "equal",
        "action_ids": action_ids,
        "completed_action_ids": completed_action_ids,
        "total_actions": len(action_ids),
        "review_actions_attempted": locked_review.actions_attempted,
        "review_actions_completed": locked_review.actions_completed,
        "review_substantive_interaction": locked_review.substantive_interaction_occurred,
        "minimum_completed": minimum_completed,
        "minimum_closeout_credit": format(policy.minimum_closeout_credit, "f"),
        "full_closeout_credit": format(policy.full_closeout_credit, "f"),
        "completion_credit": format(credit, "f"),
    }
    event = CompletionCreditEvent(
        assessment_run=sprint.assessment_run,
        sprint=sprint,
        review=locked_review,
        protocol=sprint.protocol,
        competency=sprint.protocol.parent_competency,
        algorithm_version=ALGORITHM_VERSION,
        completed_action_ids=completed_action_ids,
        total_actions=len(action_ids),
        minimum_completed=minimum_completed,
        completion_credit=credit,
        source_snapshot=source,
        source_hash=canonical_hash(source),
    )
    try:
        event.full_clean()
        event.save()
    except ValidationError as exc:
        raise CompositeScoreStateError("; ".join(exc.messages)) from exc
    verify_completion_credit_event(event)
    apply_completion_credit_event(event)
    return event


@transaction.atomic
def apply_completion_credit_event(
    event: CompletionCreditEvent,
) -> CompositeScoreSnapshot:
    source = (
        CompletionCreditEvent.objects.select_for_update()
        .select_related("assessment_run", "sprint", "review", "protocol", "competency")
        .get(pk=event.pk)
    )
    verify_completion_credit_event(source)
    synchronize_composite_score_state_for_run(source.assessment_run)
    return CompositeScoreSnapshot.objects.get(
        completion_credit_event=source,
        operation=CompositeScoreSnapshot.Operation.PROCESS,
    )


@transaction.atomic
def reverse_completion_credit_event(
    event: CompletionCreditEvent,
    *,
    reason: str,
) -> CompositeScoreSnapshot:
    reason = reason.strip()
    if not reason:
        raise CompositeScoreStateError("A completion-credit reversal requires a reason.")
    source = CompletionCreditEvent.objects.select_for_update().get(pk=event.pk)
    synchronize_composite_score_state_for_run(source.assessment_run)
    existing = CompositeScoreSnapshot.objects.filter(
        completion_credit_event=source,
        operation=CompositeScoreSnapshot.Operation.REVERSE,
    ).first()
    if existing is not None:
        return existing
    assessment_run = AssessmentRun.objects.select_for_update().get(pk=source.assessment_run_id)
    assessment_snapshot = _assessment_snapshot(assessment_run)
    state = CompositeScoreState.objects.select_for_update().get(assessment_run=assessment_run)
    all_events = _all_events(assessment_run)
    active = _active_events(assessment_run, all_events)
    active = [item for item in active if item.pk != source.pk]
    before = state.state
    after = _desired_state(assessment_snapshot.projection, active)
    _write_state(state, after, active)
    snapshot = _create_snapshot(
        assessment_run=assessment_run,
        completion_credit_event=source,
        operation=CompositeScoreSnapshot.Operation.REVERSE,
        before_state=before,
        after_state=after,
        active_events=active,
        reason=reason,
    )
    verify_composite_score_state_for_run(assessment_run)
    return snapshot


def verify_composite_score_state_for_run(assessment_run: AssessmentRun) -> None:
    try:
        assessment_snapshot = CompositeAssessmentSnapshot.objects.get(assessment_run=assessment_run)
        state = CompositeScoreState.objects.get(assessment_run=assessment_run)
    except (CompositeAssessmentSnapshot.DoesNotExist, CompositeScoreState.DoesNotExist) as exc:
        raise CompositeScoreStateError(
            f"{assessment_run.pk}: composite assessment or state is missing."
        ) from exc
    _verify_projection_payload(assessment_snapshot.projection)
    _verify_state_payload(state.state)
    if (
        assessment_snapshot.projection_hash != assessment_snapshot.projection["projection_hash"]
        or assessment_snapshot.algorithm_version != ALGORITHM_VERSION
        or assessment_snapshot.state_schema_version != STATE_SCHEMA_VERSION
        or state.state_hash != state.state["state_hash"]
        or state.user_id != assessment_run.user_id
        or state.algorithm_version != ALGORITHM_VERSION
        or state.state_schema_version != STATE_SCHEMA_VERSION
    ):
        raise CompositeScoreStateError(
            f"{assessment_run.pk}: composite current-state metadata does not verify."
        )

    all_events = _all_events(assessment_run)
    event_by_id = {event.pk: event for event in all_events}
    snapshots = list(
        CompositeScoreSnapshot.objects.filter(assessment_run=assessment_run)
        .select_related("completion_credit_event")
        .order_by("sequence")
    )
    if not snapshots or snapshots[0].operation != CompositeScoreSnapshot.Operation.INITIALIZE:
        raise CompositeScoreStateError(
            f"{assessment_run.pk}: composite initialization snapshot is missing."
        )
    if [item.sequence for item in snapshots] != list(range(1, len(snapshots) + 1)):
        raise CompositeScoreStateError(
            f"{assessment_run.pk}: composite snapshot sequence is not contiguous."
        )
    active_ids: list[object] = []
    prior_after: dict[str, Any] | None = None
    for snapshot in snapshots:
        if (
            snapshot.algorithm_version != ALGORITHM_VERSION
            or snapshot.state_schema_version != STATE_SCHEMA_VERSION
            or snapshot.before_state_hash != canonical_hash(snapshot.before_state)
            or snapshot.after_state_hash != canonical_hash(snapshot.after_state)
        ):
            raise CompositeScoreStateError(f"{snapshot.pk}: snapshot metadata does not verify.")
        if (
            prior_after is not None
            and snapshot.operation != CompositeScoreSnapshot.Operation.REBUILD
            and snapshot.before_state != prior_after
        ):
            raise CompositeScoreStateError(f"{snapshot.pk}: snapshot history is discontinuous.")
        if snapshot.operation == CompositeScoreSnapshot.Operation.INITIALIZE:
            if snapshot.sequence != 1 or snapshot.before_state:
                raise CompositeScoreStateError(
                    f"{snapshot.pk}: initialization snapshot is malformed."
                )
        elif snapshot.operation == CompositeScoreSnapshot.Operation.PROCESS:
            event = snapshot.completion_credit_event
            if event is None or event.pk not in event_by_id or event.pk in active_ids:
                raise CompositeScoreStateError(
                    f"{snapshot.pk}: processed closeout history is malformed."
                )
            active_ids.append(event.pk)
        elif snapshot.operation == CompositeScoreSnapshot.Operation.REVERSE:
            event = snapshot.completion_credit_event
            if event is None or event.pk not in active_ids:
                raise CompositeScoreStateError(
                    f"{snapshot.pk}: reversed closeout history is malformed."
                )
            active_ids.remove(event.pk)
        elif snapshot.operation != CompositeScoreSnapshot.Operation.REBUILD:
            raise CompositeScoreStateError(f"{snapshot.pk}: snapshot operation is unsupported.")
        active = [event for event in all_events if event.pk in active_ids]
        expected = _desired_state(assessment_snapshot.projection, active)
        if snapshot.after_state != expected:
            raise CompositeScoreStateError(f"{snapshot.pk}: snapshot state does not replay.")
        if snapshot.active_event_count != len(active) or snapshot.active_event_hash != _event_hash(
            active
        ):
            raise CompositeScoreStateError(
                f"{snapshot.pk}: snapshot active-event set does not verify."
            )
        prior_after = snapshot.after_state

    processed = _processed_event_ids(assessment_run)
    if processed != set(event_by_id):
        raise CompositeScoreStateError(
            f"{assessment_run.pk}: not every closeout event has been processed."
        )
    active = [
        event for event in all_events if event.pk in processed - _reversed_event_ids(assessment_run)
    ]
    desired = _desired_state(assessment_snapshot.projection, active)
    if (
        state.state != desired
        or state.active_event_count != len(active)
        or state.active_event_hash != _event_hash(active)
    ):
        raise CompositeScoreStateError(
            f"{assessment_run.pk}: composite current state does not match replay."
        )
