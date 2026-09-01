from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Q

from growth.domain.composite_scoring import ALGORITHM_VERSION
from growth.models import (
    AssessmentRun,
    CompletionCreditEvent,
    CompositeAssessmentSnapshot,
    CompositeScoreSnapshot,
    CompositeScoreState,
    PracticeAction,
    PracticeProtocol,
    ScoreSnapshot,
)
from growth.services.composite_score_state import (
    CompositeScoreStateError,
    load_composite_scoring_policy,
    verify_all_composite_score_states,
)

COMPOSITE_SCORING_READINESS_VERSION = "GG-COMPOSITE-SCORING-READINESS-1.0"


class CompositeScoringReadinessError(ValueError):
    pass


@dataclass(frozen=True)
class CompositeScoringReadinessSummary:
    contract_version: str
    scoring_algorithm_version: str
    assessment_runs: int
    assessment_snapshots: int
    current_states: int
    completion_credit_events: int
    history_snapshots: int
    families_per_epoch: int
    levers_per_epoch: int
    domains_per_epoch: int
    competencies_per_epoch: int
    practices: int
    actions: int
    specialist_review_status: str
    specialist_review_complete: bool
    research_gap_status: str
    m6b_accepted: bool
    software_ready: bool
    requires_human_gate: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _require(label: str, condition: bool) -> None:
    if not condition:
        raise CompositeScoringReadinessError(label)


def verify_composite_scoring_readiness() -> CompositeScoringReadinessSummary:
    """Verify the additive composite-scoring boundary without writing state."""

    policy = load_composite_scoring_policy()
    runs = list(AssessmentRun.objects.order_by("created_at", "stable_id"))
    _require("At least one assessment epoch is required.", bool(runs))
    try:
        verified = verify_all_composite_score_states()
    except CompositeScoreStateError as exc:
        raise CompositeScoringReadinessError(f"Composite score-state replay failed: {exc}") from exc
    _require(
        "Composite verification did not cover every assessment epoch.",
        verified.assessment_runs == len(runs),
    )
    assessment_snapshots = list(
        CompositeAssessmentSnapshot.objects.filter(assessment_run__in=runs).order_by(
            "assessment_run_id"
        )
    )
    states = list(
        CompositeScoreState.objects.filter(assessment_run__in=runs).order_by("assessment_run_id")
    )
    _require(
        "Every assessment epoch requires exactly one immutable composite projection.",
        len(assessment_snapshots) == len(runs),
    )
    _require(
        "Every assessment epoch requires exactly one current composite state.",
        len(states) == len(runs),
    )
    expected_counts = {
        "families": policy.expected_families,
        "levers": policy.expected_levers,
        "domains": policy.expected_domains,
        "competencies": policy.expected_competencies,
    }
    for snapshot, state in zip(assessment_snapshots, states, strict=True):
        _require(
            f"{snapshot.assessment_run_id}: projection entity counts are incomplete.",
            snapshot.projection.get("counts") == expected_counts,
        )
        _require(
            f"{state.assessment_run_id}: current-state entity counts are incomplete.",
            all(len(state.state.get(key, {})) == value for key, value in expected_counts.items()),
        )
        for competency_id, row in snapshot.projection["competencies"].items():
            _require(
                f"{competency_id}: serialized relationship weights do not sum to one.",
                sum(Decimal(value) for value in row["relationships"].values()) == Decimal("1"),
            )
    _require(
        "New closeout-version check-ins must not appear in legacy score snapshots.",
        not ScoreSnapshot.objects.filter(
            Q(evidence_event__check_in__sprint__scoring_contract_version=ALGORITHM_VERSION)
        ).exists(),
    )
    practice_count = PracticeProtocol.objects.filter(
        availability=PracticeProtocol.Availability.ACTIVE,
        score_active=True,
    ).count()
    action_count = PracticeAction.objects.filter(
        protocol__availability=PracticeProtocol.Availability.ACTIVE,
        protocol__score_active=True,
    ).count()
    _require(
        "The composite practice inventory is incomplete.",
        practice_count == policy.expected_practices,
    )
    _require(
        "The composite action inventory is incomplete.",
        action_count == policy.expected_actions,
    )
    return CompositeScoringReadinessSummary(
        contract_version=COMPOSITE_SCORING_READINESS_VERSION,
        scoring_algorithm_version=ALGORITHM_VERSION,
        assessment_runs=len(runs),
        assessment_snapshots=len(assessment_snapshots),
        current_states=len(states),
        completion_credit_events=CompletionCreditEvent.objects.count(),
        history_snapshots=CompositeScoreSnapshot.objects.count(),
        families_per_epoch=policy.expected_families,
        levers_per_epoch=policy.expected_levers,
        domains_per_epoch=policy.expected_domains,
        competencies_per_epoch=policy.expected_competencies,
        practices=practice_count,
        actions=action_count,
        specialist_review_status="pending",
        specialist_review_complete=False,
        research_gap_status="open",
        m6b_accepted=False,
        software_ready=True,
        requires_human_gate=True,
    )
