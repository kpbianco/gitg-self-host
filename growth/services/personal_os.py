from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction

from growth.domain.personal_os import (
    AUDIT_PROMPT_IDS,
    IDENTITY_SECTION_IDS,
    LIST_SECTION_IDS,
    MAX_CANONICAL_SNAPSHOT_BYTES,
    PERSONAL_OS_CONTRACT_VERSION,
    PERSONAL_OS_READINESS_CONTRACT_VERSION,
    SCALAR_SECTION_IDS,
    CanonicalPersonalOSSnapshot,
    PersonalOSValue,
    build_personal_os_snapshot,
    canonical_personal_os_snapshot_size,
)
from growth.models import AssessmentRun, PersonalOSRevision


class PersonalOSServiceError(ValueError):
    pass


class PersonalOSWriteConflictError(PersonalOSServiceError):
    retryable = True


class PersonalOSReadinessError(ValueError):
    pass


@dataclass(frozen=True)
class PersonalOSWriteResult:
    revision: PersonalOSRevision
    created: bool


@dataclass(frozen=True)
class PersonalOSReadinessSummary:
    contract_version: str
    personal_os_contract_version: str
    identity_section_ids: tuple[str, ...]
    audit_prompt_ids: tuple[str, ...]
    records: int
    assessment_epochs_with_personal_os: int
    maximum_snapshot_bytes: int
    software_ready: bool
    changes_recommendations: bool
    changes_score_state: bool
    changes_production_activation: bool
    ordinary_ui_changes: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_scope(*, user, assessment_run: AssessmentRun) -> None:
    if not getattr(user, "is_authenticated", False) or user.pk is None:
        raise PersonalOSServiceError("Personal OS revisions require an authenticated user.")
    if assessment_run.user_id != user.pk:
        raise PersonalOSServiceError("Personal OS user must own the assessment epoch.")


def _model_values(snapshot: CanonicalPersonalOSSnapshot) -> dict[str, Any]:
    values: dict[str, Any] = {}
    combined = {
        **snapshot.payload["identity_sections"],
        **snapshot.payload["audit_responses"],
    }
    for section_id in (*IDENTITY_SECTION_IDS, *AUDIT_PROMPT_IDS):
        item = combined[section_id]
        values[f"{section_id}_state"] = item["state"]
        if section_id in SCALAR_SECTION_IDS:
            values[f"{section_id}_value"] = item["value"] or ""
        elif section_id in LIST_SECTION_IDS:
            values[f"{section_id}_value"] = item["value"]
    return values


def _latest(*, user, assessment_run: AssessmentRun) -> PersonalOSRevision | None:
    return (
        PersonalOSRevision.objects.filter(user=user, assessment_run=assessment_run)
        .order_by("-revision")
        .first()
    )


def _winner_after_integrity_conflict(
    *,
    user,
    assessment_run: AssessmentRun,
    attempted_revision: int,
    content_hash: str,
    original_error: IntegrityError,
) -> PersonalOSWriteResult:
    winner = PersonalOSRevision.objects.filter(
        user=user,
        assessment_run=assessment_run,
        revision=attempted_revision,
    ).first()
    if winner is None:
        raise original_error
    if winner.content_hash == content_hash:
        return PersonalOSWriteResult(revision=winner, created=False)
    raise PersonalOSWriteConflictError(
        "A concurrent Personal OS revision was recorded; retry with the latest revision."
    )


def record_personal_os_revision(
    *,
    user,
    assessment_run: AssessmentRun,
    identity_sections,
    audit_responses,
) -> PersonalOSWriteResult:
    """Append one validated revision, or return the unchanged latest revision."""

    _validate_scope(user=user, assessment_run=assessment_run)
    snapshot = build_personal_os_snapshot(
        assessment_epoch_id=assessment_run.pk,
        identity_sections=identity_sections,
        audit_responses=audit_responses,
    )
    attempted_revision = 1
    try:
        with transaction.atomic():
            locked_run = AssessmentRun.objects.select_for_update().get(pk=assessment_run.pk)
            _validate_scope(user=user, assessment_run=locked_run)
            latest = _latest(user=user, assessment_run=locked_run)
            if latest is not None and latest.content_hash == snapshot.content_hash:
                return PersonalOSWriteResult(revision=latest, created=False)
            attempted_revision = 1 if latest is None else latest.revision + 1
            record = PersonalOSRevision(
                user=user,
                assessment_run=locked_run,
                contract_version=PERSONAL_OS_CONTRACT_VERSION,
                revision=attempted_revision,
                canonical_snapshot=snapshot.payload,
                content_hash=snapshot.content_hash,
                **_model_values(snapshot),
            )
            record.save(force_insert=True)
            return PersonalOSWriteResult(revision=record, created=True)
    except IntegrityError as exc:
        return _winner_after_integrity_conflict(
            user=user,
            assessment_run=assessment_run,
            attempted_revision=attempted_revision,
            content_hash=snapshot.content_hash,
            original_error=exc,
        )
    except OperationalError as exc:
        message = str(exc).lower()
        if "locked" in message or "busy" in message:
            raise PersonalOSWriteConflictError(
                "The Personal OS revision store is busy; retry the write."
            ) from exc
        raise


def latest_personal_os_revision(
    *, user, assessment_run: AssessmentRun
) -> PersonalOSRevision | None:
    _validate_scope(user=user, assessment_run=assessment_run)
    return _latest(user=user, assessment_run=assessment_run)


def _record_snapshot(record: PersonalOSRevision) -> CanonicalPersonalOSSnapshot:
    def values(section_ids):
        return {
            section_id: PersonalOSValue(
                state=getattr(record, f"{section_id}_state"),
                value=(
                    getattr(record, f"{section_id}_value")
                    if getattr(record, f"{section_id}_state") == "provided"
                    else None
                ),
            )
            for section_id in section_ids
        }

    return build_personal_os_snapshot(
        assessment_epoch_id=record.assessment_run_id,
        contract_version=record.contract_version,
        identity_sections=values(IDENTITY_SECTION_IDS),
        audit_responses=values(AUDIT_PROMPT_IDS),
    )


def verify_personal_os_readiness() -> PersonalOSReadinessSummary:
    """Read and verify every Personal OS revision without exposing authored values."""

    records = PersonalOSRevision.objects.select_related("assessment_run").order_by(
        "assessment_run_id", "revision"
    )
    revisions: dict[str, list[int]] = {}
    for position, record in enumerate(records, start=1):
        try:
            record.full_clean()
            rebuilt = _record_snapshot(record)
        except (ValidationError, ValueError, TypeError):
            raise PersonalOSReadinessError(
                f"Personal OS record {position} failed version, ownership, field, or snapshot "
                "validation."
            ) from None
        if canonical_personal_os_snapshot_size(record.canonical_snapshot) > (
            MAX_CANONICAL_SNAPSHOT_BYTES
        ):
            raise PersonalOSReadinessError(
                f"Personal OS record {position} exceeds the snapshot resource bound."
            )
        if record.canonical_snapshot != rebuilt.payload or record.content_hash != (
            rebuilt.content_hash
        ):
            raise PersonalOSReadinessError(
                f"Personal OS record {position} failed deterministic snapshot verification."
            )
        revisions.setdefault(record.assessment_run_id, []).append(record.revision)

    for actual in revisions.values():
        if sorted(actual) != list(range(1, len(actual) + 1)):
            raise PersonalOSReadinessError(
                "Personal OS revisions are not contiguous from 1 for an assessment epoch."
            )

    return PersonalOSReadinessSummary(
        contract_version=PERSONAL_OS_READINESS_CONTRACT_VERSION,
        personal_os_contract_version=PERSONAL_OS_CONTRACT_VERSION,
        identity_section_ids=IDENTITY_SECTION_IDS,
        audit_prompt_ids=AUDIT_PROMPT_IDS,
        records=records.count(),
        assessment_epochs_with_personal_os=len(revisions),
        maximum_snapshot_bytes=MAX_CANONICAL_SNAPSHOT_BYTES,
        software_ready=True,
        changes_recommendations=False,
        changes_score_state=False,
        changes_production_activation=False,
        ordinary_ui_changes=False,
    )
