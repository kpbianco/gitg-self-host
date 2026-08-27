from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from growth.domain.ranking import RANKING_ALGORITHM_VERSION, rank_needs
from growth.domain.scoring import SCORING_ALGORITHM_VERSION, ScoringContractError
from growth.models import (
    AssessmentRun,
    EvidenceEvent,
    LeverBaseline,
    LeverState,
    PracticeCheckIn,
    PracticeProtocol,
    ScoreSnapshot,
)
from growth.services.scoring import (
    PRODUCTION_SCORE_STATE_VERSION,
    project_assessment_events,
    validate_production_scoring_event,
    validate_production_scoring_protocol,
)

STATE_SCHEMA_VERSION = PRODUCTION_SCORE_STATE_VERSION


class ScoreStateError(ValueError):
    pass


@dataclass(frozen=True)
class ScoreStateSyncSummary:
    assessment_runs: int
    states_initialized: int
    events_processed: int
    rebuilds_created: int


@dataclass(frozen=True)
class RunSyncResult:
    assessment_run: AssessmentRun
    initialized: bool
    events_processed: int
    rebuilt: bool


def _decimal_string(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _event_hash(events: Iterable[EvidenceEvent]) -> str:
    return _canonical_hash([str(event.pk) for event in events])


def _state_payload(states: Iterable[LeverState]) -> list[dict[str, Any]]:
    return [
        {
            "lever_id": state.lever_id,
            "status": state.status,
            "algorithm_version": state.algorithm_version,
            "alpha": _decimal_string(state.current_alpha),
            "beta": _decimal_string(state.current_beta),
            "estimate": _decimal_string(state.current_estimate),
            "confidence": _decimal_string(state.current_confidence),
            "evidence_mass": _decimal_string(state.cumulative_evidence_mass),
            "included_evidence_events": state.included_evidence_events,
            "need_score": _decimal_string(state.current_need_score),
            "need_rank": state.current_need_rank,
        }
        for state in sorted(states, key=lambda item: item.lever_id)
    ]


def _desired_payload(
    desired: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "lever_id": lever_id,
            "status": values["status"],
            "algorithm_version": values["algorithm_version"],
            "alpha": _decimal_string(values["current_alpha"]),
            "beta": _decimal_string(values["current_beta"]),
            "estimate": _decimal_string(values["current_estimate"]),
            "confidence": _decimal_string(values["current_confidence"]),
            "evidence_mass": _decimal_string(values["cumulative_evidence_mass"]),
            "included_evidence_events": values["included_evidence_events"],
            "need_score": _decimal_string(values["current_need_score"]),
            "need_rank": values["current_need_rank"],
        }
        for lever_id, values in sorted(desired.items())
    ]


def _baselines_for_run(assessment_run: AssessmentRun) -> list[LeverBaseline]:
    baselines = list(
        LeverBaseline.objects.filter(
            assessment_run=assessment_run,
            user=assessment_run.user,
        )
        .select_related("lever")
        .order_by("lever_id")
    )
    expected = assessment_run.curriculum_version.levers.count()
    if not baselines or len(baselines) != expected:
        raise ScoreStateError(
            f"{assessment_run.pk}: expected {expected} lever baselines, found {len(baselines)}."
        )
    return baselines


def _baseline_values(
    assessment_run: AssessmentRun,
) -> dict[str, dict[str, Any]]:
    baselines = _baselines_for_run(assessment_run)
    ranking = rank_needs(
        {
            baseline.lever_id: (
                baseline.calibrated_estimate,
                baseline.evidence_confidence,
            )
            for baseline in baselines
        }
    )
    ranked = {item.lever_id: item for item in ranking}
    return {
        baseline.lever_id: {
            "user": assessment_run.user,
            "assessment_run": assessment_run,
            "baseline": baseline,
            "lever": baseline.lever,
            "algorithm_version": SCORING_ALGORITHM_VERSION,
            "status": (
                LeverState.Status.ACTIVE
                if baseline.calibrated_estimate is not None
                and baseline.baseline_alpha is not None
                and baseline.baseline_beta is not None
                else LeverState.Status.BASELINE_ONLY
            ),
            "current_alpha": baseline.baseline_alpha,
            "current_beta": baseline.baseline_beta,
            "current_estimate": baseline.calibrated_estimate,
            "current_confidence": baseline.evidence_confidence,
            "cumulative_evidence_mass": Decimal("0.000000"),
            "included_evidence_events": 0,
            "current_need_score": ranked[baseline.lever_id].score,
            "current_need_rank": ranked[baseline.lever_id].rank,
        }
        for baseline in baselines
    }


def _events_for_run(assessment_run: AssessmentRun) -> list[EvidenceEvent]:
    eligible_protocols = tuple(
        PracticeProtocol.objects.filter(score_active=True)
        .select_related("parent_competency")
        .prefetch_related("actions", "target_levers", "parent_competency__lever_links__lever")
        .order_by("stable_id")
    )
    eligible_ids = {protocol.stable_id for protocol in eligible_protocols}
    if len(eligible_ids) != 383:
        raise ScoreStateError(
            f"Expected 383 production scoring protocols, found {len(eligible_ids)}."
        )
    try:
        for protocol in eligible_protocols:
            validate_production_scoring_protocol(protocol)
    except ScoringContractError as exc:
        raise ScoreStateError(str(exc)) from exc

    processed_ids = _processed_event_ids(assessment_run)
    all_events = list(
        EvidenceEvent.objects.filter(
            check_in__sprint__assessment_run=assessment_run,
        )
        .select_related(
            "check_in__action",
            "check_in__sprint__assessment_run",
            "check_in__sprint__protocol",
        )
        .order_by(
            "check_in__submitted_at",
            "check_in__created_at",
            "check_in__stable_id",
        )
    )
    events = [
        event
        for event in all_events
        if event.protocol_stable_id in eligible_ids or event.pk in processed_ids
    ]
    submitted_count = PracticeCheckIn.objects.filter(
        sprint__assessment_run=assessment_run,
        sprint__protocol_id__in=eligible_ids,
        status=PracticeCheckIn.Status.SUBMITTED,
    ).count()
    eligible_event_count = sum(event.protocol_stable_id in eligible_ids for event in events)
    if eligible_event_count != submitted_count:
        raise ScoreStateError(
            f"{assessment_run.pk}: {submitted_count} submitted check-ins have "
            f"{eligible_event_count} production-eligible evidence events."
        )
    return events


def _processed_event_ids(assessment_run: AssessmentRun) -> set[object]:
    return set(
        ScoreSnapshot.objects.filter(
            assessment_run=assessment_run,
            operation=ScoreSnapshot.Operation.PROCESS,
        ).values_list("evidence_event_id", flat=True)
    )


def _reversed_event_ids(assessment_run: AssessmentRun) -> set[object]:
    return set(
        ScoreSnapshot.objects.filter(
            assessment_run=assessment_run,
            operation=ScoreSnapshot.Operation.REVERSE,
        ).values_list("evidence_event_id", flat=True)
    )


def _active_events(
    assessment_run: AssessmentRun,
    events: Iterable[EvidenceEvent],
) -> list[EvidenceEvent]:
    processed = _processed_event_ids(assessment_run)
    reversed_ids = _reversed_event_ids(assessment_run)
    return [event for event in events if event.pk in processed and event.pk not in reversed_ids]


def _next_sequence(assessment_run: AssessmentRun) -> int:
    latest = (
        ScoreSnapshot.objects.filter(assessment_run=assessment_run)
        .order_by("-sequence")
        .values_list("sequence", flat=True)
        .first()
    )
    return (latest or 0) + 1


def _create_snapshot(
    *,
    assessment_run: AssessmentRun,
    operation: str,
    before_state: list[dict[str, Any]],
    after_state: list[dict[str, Any]],
    active_events: Iterable[EvidenceEvent],
    evidence_event: EvidenceEvent | None = None,
    contribution_snapshot: dict[str, Any] | None = None,
    reason: str = "",
) -> ScoreSnapshot:
    resolved_events = tuple(active_events)
    snapshot = ScoreSnapshot(
        assessment_run=assessment_run,
        evidence_event=evidence_event,
        operation=operation,
        sequence=_next_sequence(assessment_run),
        algorithm_version=SCORING_ALGORITHM_VERSION,
        state_schema_version=STATE_SCHEMA_VERSION,
        before_state=before_state,
        after_state=after_state,
        contribution_snapshot=contribution_snapshot or {},
        active_event_count=len(resolved_events),
        active_event_hash=_event_hash(resolved_events),
        before_state_hash=_canonical_hash(before_state),
        after_state_hash=_canonical_hash(after_state),
        reason=reason,
    )
    try:
        snapshot.full_clean()
    except ValidationError as exc:
        raise ScoreStateError("; ".join(exc.messages)) from exc
    snapshot.save()
    return snapshot


def _contribution_snapshot(
    assessment_run: AssessmentRun,
    event: EvidenceEvent,
) -> dict[str, Any]:
    try:
        individual = project_assessment_events(assessment_run, (event,))
    except ScoringContractError as exc:
        raise ScoreStateError(str(exc)) from exc
    return {
        "event_id": str(event.pk),
        "evidence_algorithm_version": event.algorithm_version,
        "direction": event.input_snapshot.get("evidence_direction") or "not_recorded",
        "levers": [
            {
                "lever_id": lever.lever_id,
                "included": contribution.included,
                "exclusion_reason": contribution.exclusion_reason,
                "task_coefficient": _decimal_string(contribution.task_coefficient),
                "evidence_mass": _decimal_string(contribution.evidence_mass),
                "success_mass": _decimal_string(contribution.success_mass),
                "failure_mass": _decimal_string(contribution.failure_mass),
            }
            for lever in individual.projection.levers
            for contribution in lever.contributions
        ],
    }


def _desired_state(
    assessment_run: AssessmentRun,
    active_events: Iterable[EvidenceEvent],
) -> dict[str, dict[str, Any]]:
    resolved_events = tuple(active_events)
    desired = _baseline_values(assessment_run)
    if resolved_events:
        try:
            score_projection = project_assessment_events(
                assessment_run,
                resolved_events,
            )
        except ScoringContractError as exc:
            raise ScoreStateError(str(exc)) from exc
        for projected in score_projection.projection.levers:
            values = desired[projected.lever_id]
            if values["status"] != LeverState.Status.ACTIVE:
                raise ScoreStateError(
                    f"{projected.lever_id}: reassessment is required before evidence can "
                    "update this baseline."
                )
            values.update(
                {
                    "current_alpha": projected.projected_alpha,
                    "current_beta": projected.projected_beta,
                    "current_estimate": projected.projected_estimate,
                    "current_confidence": projected.projected_confidence,
                    "cumulative_evidence_mass": projected.evidence_mass,
                    "included_evidence_events": sum(
                        contribution.included for contribution in projected.contributions
                    ),
                }
            )

    ranking = rank_needs(
        {
            lever_id: (
                values["current_estimate"],
                values["current_confidence"],
            )
            for lever_id, values in desired.items()
        }
    )
    ranked = {item.lever_id: item for item in ranking}
    for lever_id, values in desired.items():
        values["current_need_score"] = ranked[lever_id].score
        values["current_need_rank"] = ranked[lever_id].rank
    return desired


def _apply_desired_state(
    states: Iterable[LeverState],
    desired: Mapping[str, Mapping[str, Any]],
) -> None:
    resolved_states = list(states)
    updated_at = timezone.now()
    for state in resolved_states:
        values = desired[state.lever_id]
        for field in (
            "algorithm_version",
            "status",
            "current_alpha",
            "current_beta",
            "current_estimate",
            "current_confidence",
            "cumulative_evidence_mass",
            "included_evidence_events",
            "current_need_score",
            "current_need_rank",
        ):
            setattr(state, field, values[field])
        state.updated_at = updated_at
    LeverState.objects.bulk_update(
        resolved_states,
        [
            "algorithm_version",
            "status",
            "current_alpha",
            "current_beta",
            "current_estimate",
            "current_confidence",
            "cumulative_evidence_mass",
            "included_evidence_events",
            "current_need_score",
            "current_need_rank",
            "updated_at",
        ],
    )


def _locked_states(assessment_run: AssessmentRun) -> list[LeverState]:
    return list(
        LeverState.objects.select_for_update()
        .filter(assessment_run=assessment_run)
        .select_related("baseline", "lever")
        .order_by("lever_id")
    )


def _initialize_locked(assessment_run: AssessmentRun) -> bool:
    desired = _baseline_values(assessment_run)
    states = _locked_states(assessment_run)
    if states:
        if set(desired) != {state.lever_id for state in states}:
            raise ScoreStateError(
                f"{assessment_run.pk}: current lever state coverage is incomplete."
            )
        if not ScoreSnapshot.objects.filter(
            assessment_run=assessment_run,
            operation=ScoreSnapshot.Operation.INITIALIZE,
        ).exists():
            raise ScoreStateError(
                f"{assessment_run.pk}: current state exists without an initialization snapshot."
            )
        return False

    LeverState.objects.bulk_create(LeverState(**values) for values in desired.values())
    states = _locked_states(assessment_run)
    after = _state_payload(states)
    _create_snapshot(
        assessment_run=assessment_run,
        operation=ScoreSnapshot.Operation.INITIALIZE,
        before_state=[],
        after_state=after,
        active_events=(),
        contribution_snapshot={
            "ranking_algorithm_version": RANKING_ALGORITHM_VERSION,
            "baseline_only_levers": [
                state.lever_id
                for state in states
                if state.status == LeverState.Status.BASELINE_ONLY
            ],
        },
    )
    return True


def _process_event_locked(
    assessment_run: AssessmentRun,
    event: EvidenceEvent,
    all_events: list[EvidenceEvent],
) -> ScoreSnapshot:
    existing = ScoreSnapshot.objects.filter(
        evidence_event=event,
        operation=ScoreSnapshot.Operation.PROCESS,
    ).first()
    if existing is not None:
        if existing.assessment_run_id != assessment_run.pk:
            raise ScoreStateError(f"{event.pk}: event was processed against another assessment.")
        return existing

    states = _locked_states(assessment_run)
    before = _state_payload(states)
    active = _active_events(assessment_run, all_events)
    active.append(event)
    active_ids = [item.pk for item in active]
    active = [item for item in all_events if item.pk in active_ids]
    desired = _desired_state(assessment_run, active)
    _apply_desired_state(states, desired)
    states = _locked_states(assessment_run)
    return _create_snapshot(
        assessment_run=assessment_run,
        evidence_event=event,
        operation=ScoreSnapshot.Operation.PROCESS,
        before_state=before,
        after_state=_state_payload(states),
        active_events=active,
        contribution_snapshot=_contribution_snapshot(assessment_run, event),
    )


def _repair_locked(
    assessment_run: AssessmentRun,
    all_events: list[EvidenceEvent],
) -> bool:
    active = _active_events(assessment_run, all_events)
    desired = _desired_state(assessment_run, active)
    expected = _desired_payload(desired)
    states = _locked_states(assessment_run)
    before = _state_payload(states)
    if before == expected:
        return False
    _apply_desired_state(states, desired)
    after = _state_payload(_locked_states(assessment_run))
    _create_snapshot(
        assessment_run=assessment_run,
        operation=ScoreSnapshot.Operation.REBUILD,
        before_state=before,
        after_state=after,
        active_events=active,
        contribution_snapshot={
            "ranking_algorithm_version": RANKING_ALGORITHM_VERSION,
            "repair": "Current state rebuilt from baseline and active versioned evidence.",
        },
        reason="Deterministic state repair.",
    )
    return True


@transaction.atomic
def synchronize_score_state_for_run(
    assessment_run: AssessmentRun,
) -> RunSyncResult:
    locked_run = (
        AssessmentRun.objects.select_for_update()
        .select_related("user", "curriculum_version")
        .get(pk=assessment_run.pk)
    )
    initialized = _initialize_locked(locked_run)
    all_events = _events_for_run(locked_run)
    processed_ids = _processed_event_ids(locked_run)
    processed = 0
    for event in all_events:
        if event.pk not in processed_ids:
            _process_event_locked(locked_run, event, all_events)
            processed_ids.add(event.pk)
            processed += 1
    rebuilt = _repair_locked(locked_run, all_events)
    verify_score_state_for_run(locked_run)
    return RunSyncResult(
        assessment_run=locked_run,
        initialized=initialized,
        events_processed=processed,
        rebuilt=rebuilt,
    )


@transaction.atomic
def apply_evidence_event(event: EvidenceEvent) -> ScoreSnapshot:
    source = (
        EvidenceEvent.objects.select_related("check_in__sprint__assessment_run")
        .select_for_update()
        .get(pk=event.pk)
    )
    assessment_run = source.check_in.sprint.assessment_run
    if assessment_run is None:
        raise ScoreStateError(
            "Evidence without an assessment link remains auditable but cannot update a score."
        )
    try:
        validate_production_scoring_event(source, assessment_run)
    except ScoringContractError as exc:
        raise ScoreStateError(str(exc)) from exc
    synchronize_score_state_for_run(assessment_run)
    return ScoreSnapshot.objects.get(
        evidence_event=source,
        operation=ScoreSnapshot.Operation.PROCESS,
    )


@transaction.atomic
def reverse_evidence_event(
    event: EvidenceEvent,
    *,
    reason: str,
) -> ScoreSnapshot:
    reason = reason.strip()
    if not reason:
        raise ScoreStateError("A score-event reversal requires an audit reason.")
    source = (
        EvidenceEvent.objects.select_related("check_in__sprint__assessment_run")
        .select_for_update()
        .get(pk=event.pk)
    )
    assessment_run = source.check_in.sprint.assessment_run
    if assessment_run is None:
        raise ScoreStateError("Evidence without an assessment link has no score to reverse.")
    try:
        validate_production_scoring_event(source, assessment_run)
    except ScoringContractError as exc:
        raise ScoreStateError(str(exc)) from exc
    synchronize_score_state_for_run(assessment_run)
    existing = ScoreSnapshot.objects.filter(
        evidence_event=source,
        operation=ScoreSnapshot.Operation.REVERSE,
    ).first()
    if existing is not None:
        return existing

    locked_run = AssessmentRun.objects.select_for_update().get(pk=assessment_run.pk)
    all_events = _events_for_run(locked_run)
    states = _locked_states(locked_run)
    before = _state_payload(states)
    reversed_ids = _reversed_event_ids(locked_run) | {source.pk}
    processed_ids = _processed_event_ids(locked_run)
    active = [
        item for item in all_events if item.pk in processed_ids and item.pk not in reversed_ids
    ]
    desired = _desired_state(locked_run, active)
    _apply_desired_state(states, desired)
    snapshot = _create_snapshot(
        assessment_run=locked_run,
        evidence_event=source,
        operation=ScoreSnapshot.Operation.REVERSE,
        before_state=before,
        after_state=_state_payload(_locked_states(locked_run)),
        active_events=active,
        contribution_snapshot={
            "reversed_event_id": str(source.pk),
            "event_remains_in_evidence_ledger": True,
        },
        reason=reason,
    )
    verify_score_state_for_run(locked_run)
    return snapshot


def verify_score_state_for_run(assessment_run: AssessmentRun) -> None:
    states = list(
        LeverState.objects.filter(assessment_run=assessment_run)
        .select_related("baseline", "lever")
        .order_by("lever_id")
    )
    baselines = _baselines_for_run(assessment_run)
    if len(states) != len(baselines):
        raise ScoreStateError(
            f"{assessment_run.pk}: expected {len(baselines)} current states, found {len(states)}."
        )
    for state in states:
        if (
            state.user_id != assessment_run.user_id
            or state.baseline.assessment_run_id != assessment_run.pk
            or state.baseline.user_id != assessment_run.user_id
            or state.baseline.lever_id != state.lever_id
        ):
            raise ScoreStateError(
                f"{assessment_run.pk}: {state.lever_id} current state has mismatched stable links."
            )
        if state.algorithm_version != SCORING_ALGORITHM_VERSION:
            raise ScoreStateError(
                f"{assessment_run.pk}: {state.lever_id} current algorithm version is unsupported."
            )
    snapshots = list(
        ScoreSnapshot.objects.filter(assessment_run=assessment_run)
        .select_related("evidence_event")
        .order_by("sequence")
    )
    if not snapshots or snapshots[0].operation != ScoreSnapshot.Operation.INITIALIZE:
        raise ScoreStateError(f"{assessment_run.pk}: initialization snapshot is missing.")
    if [item.sequence for item in snapshots] != list(range(1, len(snapshots) + 1)):
        raise ScoreStateError(f"{assessment_run.pk}: score snapshot sequence is not contiguous.")
    all_events = _events_for_run(assessment_run)
    event_by_id = {event.pk: event for event in all_events}
    active_ids: list[object] = []
    prior_after: list[dict[str, Any]] | None = None
    for snapshot in snapshots:
        if snapshot.algorithm_version != SCORING_ALGORITHM_VERSION:
            raise ScoreStateError(
                f"{snapshot.pk}: score snapshot algorithm version is unsupported."
            )
        if snapshot.state_schema_version != STATE_SCHEMA_VERSION:
            raise ScoreStateError(
                f"{snapshot.pk}: score snapshot state schema version is unsupported."
            )
        if snapshot.before_state_hash != _canonical_hash(snapshot.before_state):
            raise ScoreStateError(f"{snapshot.pk}: before-state hash does not verify.")
        if snapshot.after_state_hash != _canonical_hash(snapshot.after_state):
            raise ScoreStateError(f"{snapshot.pk}: after-state hash does not verify.")
        if (
            prior_after is not None
            and snapshot.operation != ScoreSnapshot.Operation.REBUILD
            and snapshot.before_state != prior_after
        ):
            raise ScoreStateError(f"{snapshot.pk}: before-state does not follow prior history.")
        if snapshot.operation == ScoreSnapshot.Operation.INITIALIZE:
            if snapshot.sequence != 1 or snapshot.before_state:
                raise ScoreStateError(f"{snapshot.pk}: initialization history is malformed.")
        elif snapshot.operation == ScoreSnapshot.Operation.PROCESS:
            event = snapshot.evidence_event
            if event is None or event.pk not in event_by_id or event.pk in active_ids:
                raise ScoreStateError(f"{snapshot.pk}: processed event history is malformed.")
            if snapshot.contribution_snapshot != _contribution_snapshot(
                assessment_run,
                event,
            ):
                raise ScoreStateError(
                    f"{snapshot.pk}: event contribution snapshot does not replay."
                )
            active_ids.append(event.pk)
        elif snapshot.operation == ScoreSnapshot.Operation.REVERSE:
            event = snapshot.evidence_event
            if event is None or event.pk not in active_ids:
                raise ScoreStateError(f"{snapshot.pk}: reversal history is malformed.")
            active_ids.remove(event.pk)
        elif snapshot.operation != ScoreSnapshot.Operation.REBUILD:
            raise ScoreStateError(f"{snapshot.pk}: score snapshot operation is unsupported.")

        active_at_snapshot = [event for event in all_events if event.pk in active_ids]
        expected_after = _desired_payload(_desired_state(assessment_run, active_at_snapshot))
        if snapshot.after_state != expected_after:
            raise ScoreStateError(
                f"{snapshot.pk}: after-state does not match deterministic event replay."
            )
        if snapshot.active_event_count != len(
            active_at_snapshot
        ) or snapshot.active_event_hash != _event_hash(active_at_snapshot):
            raise ScoreStateError(f"{snapshot.pk}: active event set does not verify.")
        prior_after = snapshot.after_state

    event_ids = {event.pk for event in all_events}
    processed_ids = _processed_event_ids(assessment_run)
    if processed_ids != event_ids:
        missing = len(event_ids - processed_ids)
        extra = len(processed_ids - event_ids)
        raise ScoreStateError(
            f"{assessment_run.pk}: score history has {missing} pending and {extra} unknown events."
        )
    reversed_ids = _reversed_event_ids(assessment_run)
    if not reversed_ids.issubset(processed_ids):
        raise ScoreStateError(
            f"{assessment_run.pk}: a reversal exists without a processed evidence event."
        )
    active = [event for event in all_events if event.pk not in reversed_ids]
    desired = _desired_state(assessment_run, active)
    current = _state_payload(states)
    expected = _desired_payload(desired)
    if current != expected:
        raise ScoreStateError(
            f"{assessment_run.pk}: current state does not match deterministic event replay."
        )
    latest = snapshots[-1]
    if latest.after_state != current:
        raise ScoreStateError(
            f"{assessment_run.pk}: latest score snapshot does not match current state."
        )
    if latest.active_event_count != len(active) or latest.active_event_hash != _event_hash(active):
        raise ScoreStateError(
            f"{assessment_run.pk}: latest score snapshot event set does not verify."
        )


def synchronize_all_score_states() -> ScoreStateSyncSummary:
    runs = list(
        AssessmentRun.objects.select_related("user", "curriculum_version").order_by(
            "user_id",
            "created_at",
            "stable_id",
        )
    )
    initialized = 0
    processed = 0
    rebuilt = 0
    for assessment_run in runs:
        result = synchronize_score_state_for_run(assessment_run)
        initialized += result.initialized
        processed += result.events_processed
        rebuilt += result.rebuilt
    return ScoreStateSyncSummary(
        assessment_runs=len(runs),
        states_initialized=initialized,
        events_processed=processed,
        rebuilds_created=rebuilt,
    )


def verify_all_score_states() -> ScoreStateSyncSummary:
    runs = list(
        AssessmentRun.objects.select_related("user", "curriculum_version").order_by(
            "user_id",
            "created_at",
            "stable_id",
        )
    )
    for assessment_run in runs:
        verify_score_state_for_run(assessment_run)
    return ScoreStateSyncSummary(
        assessment_runs=len(runs),
        states_initialized=0,
        events_processed=0,
        rebuilds_created=0,
    )
