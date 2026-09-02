from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import yaml
from django.conf import settings
from django.core.exceptions import ValidationError

from growth.domain.composite_scoring import canonical_hash
from growth.models import AssessmentRun, CompositeScoreState, PracticeContext, PracticeProtocol
from growth.services.composite_score_state import (
    CompositeScoreStateError,
    verify_composite_score_state_for_run,
)

APPLICABILITY_COVERAGE_VERSION = "GG-PERSONAL-APPLICABLE-COVERAGE-1.0"
TWELVE_PLACES = Decimal("0.000000000001")


class ApplicabilityCoverageError(ValueError):
    pass


@dataclass(frozen=True)
class ApplicabilityCoverageProjection:
    contract_version: str
    assessment_epoch_id: str
    canonical_competency_count: int
    personally_not_applicable_competency_ids: tuple[str, ...]
    personal_applicable_competency_count: int
    canonical_completion_coverage: Decimal
    personal_applicable_completion_coverage: Decimal | None
    practice_context_revision_count: int
    projection_hash: str

    @property
    def personally_not_applicable_competency_count(self) -> int:
        return len(self.personally_not_applicable_competency_ids)


@dataclass(frozen=True)
class ApplicabilityCoverageReadinessSummary:
    contract_version: str
    assessment_epochs: int
    canonical_competencies: int
    context_revisions: int
    personally_not_applicable_competencies: int
    software_ready: bool
    writes_score_state: bool

    def as_dict(self) -> dict:
        return {
            "assessment_epochs": self.assessment_epochs,
            "canonical_competencies": self.canonical_competencies,
            "context_revisions": self.context_revisions,
            "contract_version": self.contract_version,
            "personally_not_applicable_competencies": (self.personally_not_applicable_competencies),
            "software_ready": self.software_ready,
            "writes_score_state": self.writes_score_state,
        }


def _unit_decimal(value, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:  # pragma: no cover - Decimal has several input exceptions
        raise ApplicabilityCoverageError(f"{label} must be a decimal value.") from exc
    if not result.is_finite() or result < 0 or result > 1:
        raise ApplicabilityCoverageError(f"{label} must be in the closed unit interval.")
    return result


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(TWELVE_PLACES, rounding=ROUND_HALF_UP)


def calculate_personal_applicable_coverage(
    credits: dict[str, Decimal], excluded_competency_ids: set[str]
) -> tuple[int, Decimal | None]:
    unknown_ids = excluded_competency_ids - set(credits)
    if unknown_ids:
        raise ApplicabilityCoverageError(
            "Personal exclusions contain a competency outside composite state."
        )
    applicable_ids = tuple(sorted(set(credits) - excluded_competency_ids))
    if not applicable_ids:
        return 0, None
    coverage = _quantize(
        sum((credits[competency_id] for competency_id in applicable_ids), Decimal("0"))
        / Decimal(len(applicable_ids))
    )
    return len(applicable_ids), coverage


def build_applicability_coverage_projection(
    *,
    user,
    assessment_run: AssessmentRun,
    composite_state: dict,
) -> ApplicabilityCoverageProjection:
    """Project a personal denominator without mutating canonical score state."""

    if assessment_run.user_id != user.pk:
        raise ApplicabilityCoverageError("Assessment epoch ownership does not match the user.")
    competency_rows = composite_state.get("competencies") or {}
    if not competency_rows:
        raise ApplicabilityCoverageError("Composite competency state is unavailable.")

    canonical_coverage = _unit_decimal(
        composite_state.get("canonical_coverage"), "Canonical coverage"
    )
    credits = {
        competency_id: _unit_decimal(row.get("completion_credit"), competency_id)
        for competency_id, row in competency_rows.items()
    }
    protocols = tuple(
        PracticeProtocol.objects.filter(
            availability=PracticeProtocol.Availability.ACTIVE,
            parent_competency_id__in=credits,
        )
        .select_related("parent_competency")
        .order_by("stable_id")
    )
    protocol_competencies = [protocol.parent_competency_id for protocol in protocols]
    if len(protocols) != len(credits) or set(protocol_competencies) != set(credits):
        raise ApplicabilityCoverageError(
            "Every composite competency must have exactly one active practice protocol."
        )
    if len(protocol_competencies) != len(set(protocol_competencies)):
        raise ApplicabilityCoverageError(
            "A composite competency has more than one active practice protocol."
        )

    protocol_to_competency = {
        protocol.stable_id: protocol.parent_competency_id for protocol in protocols
    }
    rows = tuple(
        PracticeContext.objects.filter(
            assessment_run=assessment_run,
            protocol_id__in=protocol_to_competency,
        ).order_by("protocol_id", "revision")
    )
    revisions: dict[str, list[int]] = {}
    latest: dict[str, PracticeContext] = {}
    try:
        for row in rows:
            if row.user_id != user.pk:
                raise ValidationError("ownership")
            row.full_clean()
            revisions.setdefault(row.protocol_id, []).append(row.revision)
            latest[row.protocol_id] = row
    except (ValidationError, ValueError, TypeError):
        raise ApplicabilityCoverageError(
            "Practice applicability history failed ownership, scope, snapshot, or hash validation."
        ) from None
    if any(actual != list(range(1, len(actual) + 1)) for actual in revisions.values()):
        raise ApplicabilityCoverageError(
            "Practice applicability revisions are not contiguous from one."
        )

    excluded_ids = tuple(
        sorted(
            protocol_to_competency[protocol_id]
            for protocol_id, row in latest.items()
            if row.applicability_state == "not_applicable"
        )
    )
    excluded = set(excluded_ids)
    applicable_count, personal_coverage = calculate_personal_applicable_coverage(credits, excluded)

    payload = {
        "contract_version": APPLICABILITY_COVERAGE_VERSION,
        "assessment_epoch_id": str(assessment_run.pk),
        "canonical_competency_count": len(credits),
        "personally_not_applicable_competency_ids": list(excluded_ids),
        "personal_applicable_competency_count": applicable_count,
        "canonical_completion_coverage": format(_quantize(canonical_coverage), "f"),
        "personal_applicable_completion_coverage": (
            None if personal_coverage is None else format(personal_coverage, "f")
        ),
        "practice_context_hashes": {
            protocol_id: row.content_hash for protocol_id, row in sorted(latest.items())
        },
    }
    return ApplicabilityCoverageProjection(
        contract_version=APPLICABILITY_COVERAGE_VERSION,
        assessment_epoch_id=str(assessment_run.pk),
        canonical_competency_count=len(credits),
        personally_not_applicable_competency_ids=excluded_ids,
        personal_applicable_competency_count=applicable_count,
        canonical_completion_coverage=_quantize(canonical_coverage),
        personal_applicable_completion_coverage=personal_coverage,
        practice_context_revision_count=len(rows),
        projection_hash=canonical_hash(payload),
    )


def verify_applicability_coverage_readiness() -> ApplicabilityCoverageReadinessSummary:
    contract_path = settings.BASE_DIR / "contracts" / "personal-applicable-coverage.yaml"
    try:
        contract = yaml.safe_load(contract_path.read_text())
    except (OSError, yaml.YAMLError):
        raise ApplicabilityCoverageError(
            "Personal-applicable coverage contract could not be loaded."
        ) from None
    if contract.get("schema_version") != APPLICABILITY_COVERAGE_VERSION:
        raise ApplicabilityCoverageError(
            "Personal-applicable coverage contract version is unsupported."
        )
    invariants = contract.get("invariants") or {}
    expected_invariants = {
        "writes_score_state": False,
        "awards_completion_credit": False,
        "changes_canonical_coverage": False,
        "changes_recommendation_math": False,
        "completion_is_mastery": False,
        "cross_epoch_carryover": False,
    }
    if invariants != expected_invariants:
        raise ApplicabilityCoverageError(
            "Personal-applicable coverage mutation and mastery invariants do not verify."
        )
    projections = []
    states = CompositeScoreState.objects.select_related("assessment_run__user").order_by(
        "assessment_run_id"
    )
    for state in states:
        try:
            verify_composite_score_state_for_run(state.assessment_run)
        except CompositeScoreStateError:
            raise ApplicabilityCoverageError(
                "Composite score state must verify before applicability coverage."
            ) from None
        projection = build_applicability_coverage_projection(
            user=state.assessment_run.user,
            assessment_run=state.assessment_run,
            composite_state=state.state,
        )
        if projection.canonical_completion_coverage != _quantize(
            Decimal(state.state["canonical_coverage"])
        ):
            raise ApplicabilityCoverageError(
                "Personal projection does not preserve canonical completion coverage."
            )
        projections.append(projection)
    counts = {projection.canonical_competency_count for projection in projections}
    if len(counts) > 1:
        raise ApplicabilityCoverageError(
            "Canonical competency coverage differs across assessment epochs."
        )
    return ApplicabilityCoverageReadinessSummary(
        contract_version=APPLICABILITY_COVERAGE_VERSION,
        assessment_epochs=len(projections),
        canonical_competencies=next(iter(counts), 0),
        context_revisions=sum(
            projection.practice_context_revision_count for projection in projections
        ),
        personally_not_applicable_competencies=sum(
            projection.personally_not_applicable_competency_count for projection in projections
        ),
        software_ready=True,
        writes_score_state=False,
    )
