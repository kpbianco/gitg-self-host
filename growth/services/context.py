from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet

from growth.domain.context import (
    ASSESSMENT_FACTOR_IDS,
    CONTEXT_CONTRACT_VERSION,
    CONTEXT_READINESS_CONTRACT_VERSION,
    PRACTICE_FACTOR_IDS,
    CanonicalContextSnapshot,
    ContextFactorValue,
    DeferReason,
    PracticeDisposition,
    build_assessment_context_snapshot,
    build_practice_context_snapshot,
)
from growth.models import (
    AssessmentContext,
    AssessmentRun,
    PracticeContext,
    PracticeProtocol,
)

MAX_CANONICAL_SNAPSHOT_BYTES = 4096


class ContextServiceError(ValueError):
    pass


class ContextReadinessError(ValueError):
    pass


@dataclass(frozen=True)
class PracticeContextInput:
    protocol: PracticeProtocol
    factors: Mapping[str, ContextFactorValue | Mapping[str, Any]]
    disposition: PracticeDisposition | str = PracticeDisposition.CONSIDERING
    defer_reason: DeferReason | str | None = None
    review_horizon_days: int | None = None


@dataclass(frozen=True)
class ContextWriteResult:
    assessment_context: AssessmentContext
    practice_contexts: tuple[PracticeContext, ...]
    assessment_created: bool
    practice_created: tuple[bool, ...]


@dataclass(frozen=True)
class ContextReadinessSummary:
    contract_version: str
    context_contract_version: str
    assessment_factor_ids: tuple[str, ...]
    practice_factor_ids: tuple[str, ...]
    assessment_records: int
    practice_records: int
    assessment_epochs_with_context: int
    practice_candidates_with_context: int
    software_ready: bool
    changes_recommendations: bool
    changes_score_state: bool
    ordinary_ui_changes: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _snapshot_size(snapshot: Mapping[str, Any]) -> int:
    return len(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
    )


def _validate_scope_ownership(*, user, assessment_run: AssessmentRun) -> None:
    if assessment_run.user_id != user.pk:
        raise ContextServiceError("Context user must own the assessment epoch.")


def _validate_protocol_scope(
    *,
    assessment_run: AssessmentRun,
    protocol: PracticeProtocol,
) -> None:
    parent = protocol.parent_competency
    if parent is None:
        raise ContextServiceError("Context protocol must have a canonical parent competency.")
    if parent.curriculum_version_id != assessment_run.curriculum_version_id:
        raise ContextServiceError(
            "Context protocol must belong to the assessment epoch curriculum."
        )


def _validate_snapshot_size(snapshot: CanonicalContextSnapshot) -> None:
    if _snapshot_size(snapshot.payload) > MAX_CANONICAL_SNAPSHOT_BYTES:
        raise ContextServiceError(
            f"Canonical context snapshot exceeds {MAX_CANONICAL_SNAPSHOT_BYTES} bytes."
        )


def _next_revision(queryset: QuerySet) -> int:
    latest = queryset.order_by("-revision").values_list("revision", flat=True).first()
    return 1 if latest is None else latest + 1


def _persist_assessment_snapshot(
    *,
    user,
    assessment_run: AssessmentRun,
    snapshot: CanonicalContextSnapshot,
) -> tuple[AssessmentContext, bool]:
    records = AssessmentContext.objects.filter(assessment_run=assessment_run)
    latest = records.order_by("-revision").first()
    if latest is not None and latest.content_hash == snapshot.content_hash:
        return latest, False
    factor_payload = snapshot.payload["factors"]
    record = AssessmentContext(
        user=user,
        assessment_run=assessment_run,
        contract_version=CONTEXT_CONTRACT_VERSION,
        revision=_next_revision(records),
        season_state=factor_payload["season"]["state"],
        season_value=factor_payload["season"]["value"] or "",
        capacity_state=factor_payload["capacity"]["state"],
        capacity_value=factor_payload["capacity"]["value"],
        canonical_snapshot=snapshot.payload,
        content_hash=snapshot.content_hash,
    )
    record.full_clean()
    record.save(force_insert=True)
    return record, True


def _persist_practice_snapshot(
    *,
    user,
    assessment_run: AssessmentRun,
    protocol: PracticeProtocol,
    snapshot: CanonicalContextSnapshot,
) -> tuple[PracticeContext, bool]:
    records = PracticeContext.objects.filter(
        assessment_run=assessment_run,
        protocol=protocol,
    )
    latest = records.order_by("-revision").first()
    if latest is not None and latest.content_hash == snapshot.content_hash:
        return latest, False
    factor_payload = snapshot.payload["factors"]
    record = PracticeContext(
        user=user,
        assessment_run=assessment_run,
        protocol=protocol,
        contract_version=CONTEXT_CONTRACT_VERSION,
        revision=_next_revision(records),
        disposition=snapshot.payload["disposition"],
        defer_reason=snapshot.payload["defer"]["reason"] or "",
        review_horizon_days=snapshot.payload["defer"]["review_horizon_days"],
        canonical_snapshot=snapshot.payload,
        content_hash=snapshot.content_hash,
        **{
            f"{factor_id}_{suffix}": factor_payload[factor_id][key]
            for factor_id in PRACTICE_FACTOR_IDS
            for suffix, key in (("state", "state"), ("value", "value"))
        },
    )
    record.full_clean()
    record.save(force_insert=True)
    return record, True


def record_context_bundle(
    *,
    user,
    assessment_run: AssessmentRun,
    assessment_factors: Mapping[str, ContextFactorValue | Mapping[str, Any]],
    practice_inputs: Sequence[PracticeContextInput] = (),
) -> ContextWriteResult:
    """Append one deterministic context revision per changed scope, atomically."""

    _validate_scope_ownership(user=user, assessment_run=assessment_run)
    assessment_snapshot = build_assessment_context_snapshot(
        assessment_epoch_id=assessment_run.pk,
        factors=assessment_factors,
    )
    _validate_snapshot_size(assessment_snapshot)

    prepared_practices: list[tuple[PracticeContextInput, CanonicalContextSnapshot]] = []
    seen_protocol_ids: set[str] = set()
    for item in practice_inputs:
        protocol_id = item.protocol.pk
        if protocol_id in seen_protocol_ids:
            raise ContextServiceError(f"Practice context input repeats protocol {protocol_id!r}.")
        seen_protocol_ids.add(protocol_id)
        _validate_protocol_scope(assessment_run=assessment_run, protocol=item.protocol)
        snapshot = build_practice_context_snapshot(
            assessment_epoch_id=assessment_run.pk,
            protocol_stable_id=protocol_id,
            factors=item.factors,
            disposition=item.disposition,
            defer_reason=item.defer_reason,
            review_horizon_days=item.review_horizon_days,
        )
        _validate_snapshot_size(snapshot)
        prepared_practices.append((item, snapshot))

    with transaction.atomic():
        locked_run = AssessmentRun.objects.select_for_update().get(pk=assessment_run.pk)
        _validate_scope_ownership(user=user, assessment_run=locked_run)
        assessment_record, assessment_created = _persist_assessment_snapshot(
            user=user,
            assessment_run=locked_run,
            snapshot=assessment_snapshot,
        )
        practice_records = []
        practice_created = []
        for item, snapshot in prepared_practices:
            record, created = _persist_practice_snapshot(
                user=user,
                assessment_run=locked_run,
                protocol=item.protocol,
                snapshot=snapshot,
            )
            practice_records.append(record)
            practice_created.append(created)
    return ContextWriteResult(
        assessment_context=assessment_record,
        practice_contexts=tuple(practice_records),
        assessment_created=assessment_created,
        practice_created=tuple(practice_created),
    )


def latest_assessment_context(*, user, assessment_run: AssessmentRun) -> AssessmentContext | None:
    _validate_scope_ownership(user=user, assessment_run=assessment_run)
    return (
        AssessmentContext.objects.filter(user=user, assessment_run=assessment_run)
        .order_by("-revision")
        .first()
    )


def latest_practice_context(
    *,
    user,
    assessment_run: AssessmentRun,
    protocol: PracticeProtocol,
) -> PracticeContext | None:
    _validate_scope_ownership(user=user, assessment_run=assessment_run)
    _validate_protocol_scope(assessment_run=assessment_run, protocol=protocol)
    return (
        PracticeContext.objects.filter(
            user=user,
            assessment_run=assessment_run,
            protocol=protocol,
        )
        .order_by("-revision")
        .first()
    )


def _validate_revision_series(
    *, label: str, records: QuerySet, key_fields: tuple[str, ...]
) -> None:
    revisions: dict[tuple[Any, ...], list[int]] = {}
    for values in records.values_list(*key_fields, "revision"):
        revisions.setdefault(tuple(values[:-1]), []).append(values[-1])
    for key, actual in revisions.items():
        expected = list(range(1, len(actual) + 1))
        if sorted(actual) != expected:
            raise ContextReadinessError(f"{label} revisions for {key!r} are not contiguous from 1.")


def verify_context_readiness() -> ContextReadinessSummary:
    """Read and validate every persisted v1 context record without writing state."""

    assessment_records = AssessmentContext.objects.select_related("assessment_run").order_by(
        "assessment_run_id", "revision"
    )
    practice_records = PracticeContext.objects.select_related(
        "assessment_run", "protocol__parent_competency"
    ).order_by("assessment_run_id", "protocol_id", "revision")
    try:
        for record in assessment_records:
            record.full_clean()
            if _snapshot_size(record.canonical_snapshot) > MAX_CANONICAL_SNAPSHOT_BYTES:
                raise ContextReadinessError(
                    f"Assessment context {record.pk} exceeds the snapshot resource bound."
                )
        for record in practice_records:
            record.full_clean()
            if _snapshot_size(record.canonical_snapshot) > MAX_CANONICAL_SNAPSHOT_BYTES:
                raise ContextReadinessError(
                    f"Practice context {record.pk} exceeds the snapshot resource bound."
                )
    except ValidationError as exc:
        raise ContextReadinessError(f"Persisted context record is invalid: {exc}") from exc

    _validate_revision_series(
        label="Assessment context",
        records=assessment_records,
        key_fields=("assessment_run_id",),
    )
    _validate_revision_series(
        label="Practice context",
        records=practice_records,
        key_fields=("assessment_run_id", "protocol_id"),
    )
    return ContextReadinessSummary(
        contract_version=CONTEXT_READINESS_CONTRACT_VERSION,
        context_contract_version=CONTEXT_CONTRACT_VERSION,
        assessment_factor_ids=ASSESSMENT_FACTOR_IDS,
        practice_factor_ids=PRACTICE_FACTOR_IDS,
        assessment_records=assessment_records.count(),
        practice_records=practice_records.count(),
        assessment_epochs_with_context=assessment_records.values("assessment_run_id")
        .distinct()
        .count(),
        practice_candidates_with_context=practice_records.values("assessment_run_id", "protocol_id")
        .distinct()
        .count(),
        software_ready=True,
        changes_recommendations=False,
        changes_score_state=False,
        ordinary_ui_changes=False,
    )
