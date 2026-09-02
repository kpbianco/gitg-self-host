from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model

from growth.domain.ranking import (
    ProtocolWeight,
    RankingContractError,
    protocol_priority,
)
from growth.models import (
    AssessmentRun,
    CompositeScoreSnapshot,
    CompositeScoreState,
    LeverBaseline,
    LeverState,
    PracticeProtocol,
    ScoreSnapshot,
)
from growth.services.applicability_coverage import (
    ApplicabilityCoverageError,
    build_applicability_coverage_projection,
)
from growth.services.composite_score_state import (
    CompositeScoreStateError,
    verify_composite_score_state_for_run,
)
from growth.services.score_state import ScoreStateError, verify_score_state_for_run


class ProfileSummaryError(ValueError):
    pass


@dataclass(frozen=True)
class ProfileLever:
    baseline: LeverBaseline
    state: LeverState | None
    composite_row: dict[str, Any] | None = None
    composite_need_rank: int | None = None

    @property
    def lever(self):
        return self.baseline.lever

    @property
    def raw_self_report(self) -> Decimal | None:
        return self.baseline.raw_self_report

    @property
    def starting_estimate(self) -> Decimal | None:
        if self.composite_row is not None:
            return Decimal(self.composite_row["assessment_estimate"])
        return self.baseline.calibrated_estimate

    @property
    def starting_confidence(self) -> Decimal:
        if self.composite_row is not None:
            return Decimal(self.composite_row["assessment_confidence"])
        return self.baseline.evidence_confidence

    @property
    def estimate(self) -> Decimal | None:
        if self.composite_row is not None:
            return Decimal(self.composite_row["assessment_estimate"])
        return (
            self.state.current_estimate
            if self.state is not None
            else self.baseline.calibrated_estimate
        )

    @property
    def confidence(self) -> Decimal:
        if self.composite_row is not None:
            return Decimal(self.composite_row["assessment_confidence"])
        return (
            self.state.current_confidence
            if self.state is not None
            else self.baseline.evidence_confidence
        )

    @property
    def need_score(self) -> Decimal | None:
        if self.composite_row is not None:
            return Decimal(self.composite_row["remaining_need"])
        return self.state.current_need_score if self.state is not None else self.baseline.need_score

    @property
    def need_rank(self) -> int:
        if self.composite_need_rank is not None:
            return self.composite_need_rank
        return self.state.current_need_rank if self.state is not None else self.baseline.need_rank

    @property
    def included_evidence_events(self) -> int:
        return self.state.included_evidence_events if self.state is not None else 0

    @property
    def has_evidence_update(self) -> bool:
        if self.composite_row is not None:
            return Decimal(self.composite_row["coverage"]) > 0
        return bool(self.state is not None and self.state.cumulative_evidence_mass > 0)

    @property
    def completion_coverage(self) -> Decimal:
        if self.composite_row is None:
            return Decimal("0")
        return Decimal(self.composite_row["coverage"])

    @property
    def assessment_source(self) -> str:
        if self.composite_row is None:
            return "legacy"
        return str(self.composite_row["assessment_source"])


@dataclass(frozen=True)
class ProfileSummary:
    assessment_run: AssessmentRun | None
    highest_needs: list[ProfileLever]
    strongest_capacities: list[ProfileLever]
    evidence_updated_capacities: list[ProfileLever]
    recommendations: list[PracticeProtocol]
    recommendation_priorities: dict[str, Decimal]
    dynamic_state_active: bool
    score_snapshot_count: int
    state_verification_error: str
    composite_state_active: bool = False
    canonical_completion_coverage: Decimal = Decimal("0")
    full_credit_competencies: int = 0
    partial_credit_competencies: int = 0
    composite_snapshot_count: int = 0
    personal_applicability_active: bool = False
    personally_not_applicable_competencies: int = 0
    personal_applicable_competency_count: int = 0
    personal_applicable_completion_coverage: Decimal | None = None
    personal_coverage_error: str = ""


def _rank_recommendations(
    needs: dict[str, Decimal | None],
) -> tuple[list[PracticeProtocol], dict[str, Decimal]]:
    protocols = list(
        PracticeProtocol.objects.filter(
            availability=PracticeProtocol.Availability.ACTIVE,
        )
        .select_related("parent_competency")
        .prefetch_related(
            "target_levers",
            "parent_competency__lever_links",
        )
    )
    ranked: list[tuple[PracticeProtocol, Decimal]] = []
    for protocol in protocols:
        if protocol.parent_competency_id is None:
            raise ProfileSummaryError(
                f"{protocol.stable_id}: active practice has no stable parent competency."
            )
        links = tuple(protocol.parent_competency.lever_links.all())
        link_ids = {link.lever_id for link in links}
        target_ids = {lever.stable_id for lever in protocol.target_levers.all()}
        if not target_ids or not target_ids.issubset(link_ids):
            raise ProfileSummaryError(
                f"{protocol.stable_id}: recommendation targets do not match its "
                "canonical scoring mapping."
            )
        try:
            priority = protocol_priority(
                needs,
                (
                    ProtocolWeight(
                        lever_id=link.lever_id,
                        weight=link.weight,
                    )
                    for link in links
                ),
            )
        except RankingContractError as exc:
            raise ProfileSummaryError(f"{protocol.stable_id}: {exc}") from exc
        ranked.append((protocol, priority))
    ranked.sort(
        key=lambda item: (
            -item[1],
            item[0].display_order,
            item[0].stable_id,
        )
    )
    return (
        [protocol for protocol, _priority in ranked[:3]],
        {protocol.stable_id: priority for protocol, priority in ranked},
    )


def _rank_composite_recommendations(
    state: dict[str, Any],
) -> tuple[list[PracticeProtocol], dict[str, Decimal]]:
    protocols = list(
        PracticeProtocol.objects.filter(availability=PracticeProtocol.Availability.ACTIVE)
        .select_related("parent_competency")
        .order_by("display_order", "stable_id")
    )
    competency_rows = state.get("competencies") or {}
    ranked: list[tuple[PracticeProtocol, Decimal]] = []
    for protocol in protocols:
        if protocol.parent_competency_id not in competency_rows:
            raise ProfileSummaryError(
                f"{protocol.stable_id}: composite priority is unavailable for its competency."
            )
        priority = Decimal(competency_rows[protocol.parent_competency_id]["remaining_priority"])
        ranked.append((protocol, priority))
    ranked.sort(key=lambda item: (-item[1], item[0].display_order, item[0].stable_id))
    return (
        [protocol for protocol, priority in ranked if priority > 0][:3],
        {protocol.stable_id: priority for protocol, priority in ranked},
    )


def build_profile_summary(user: get_user_model()) -> ProfileSummary:
    run = (
        AssessmentRun.objects.filter(user=user)
        .prefetch_related("orientation_results", "archetype_results")
        .first()
    )
    if run is None:
        return ProfileSummary(None, [], [], [], [], {}, False, 0, "")

    baselines = list(
        LeverBaseline.objects.filter(
            user=user,
            assessment_run=run,
        )
        .select_related("lever")
        .order_by("lever_id")
    )
    states = {
        state.lever_id: state
        for state in LeverState.objects.filter(
            user=user,
            assessment_run=run,
        ).select_related("lever", "baseline")
    }
    dynamic_state_active = bool(states) and len(states) == len(baselines)
    if states and not dynamic_state_active:
        raise ProfileSummaryError("Current lever-state coverage is incomplete.")
    state_verification_error = ""
    verification_failed = False
    if dynamic_state_active:
        try:
            verify_score_state_for_run(run)
        except ScoreStateError:
            dynamic_state_active = False
            verification_failed = True
            state_verification_error = (
                "Evidence and score-state verification must pass before current "
                "updates can be trusted."
            )
            states = {}

    composite_state = CompositeScoreState.objects.filter(
        user=user,
        assessment_run=run,
    ).first()
    composite_state_active = composite_state is not None
    if composite_state is not None:
        try:
            verify_composite_score_state_for_run(run)
        except CompositeScoreStateError:
            composite_state_active = False
            composite_state = None
            dynamic_state_active = False
            verification_failed = True
            states = {}
            state_verification_error = (
                "Composite completion-credit verification must pass before current "
                "priorities can be trusted."
            )
    if verification_failed:
        dynamic_state_active = False
        composite_state_active = False
        states = {}
        composite_state = None
    composite_levers = composite_state.state["levers"] if composite_state is not None else {}
    composite_lever_ranks = {
        lever_id: rank
        for rank, (lever_id, _row) in enumerate(
            sorted(
                composite_levers.items(),
                key=lambda item: (-Decimal(item[1]["remaining_need"]), item[0]),
            ),
            start=1,
        )
    }
    rows = [
        ProfileLever(
            baseline=baseline,
            state=states.get(baseline.lever_id),
            composite_row=composite_levers.get(baseline.lever_id),
            composite_need_rank=composite_lever_ranks.get(baseline.lever_id),
        )
        for baseline in baselines
    ]
    highest_needs = sorted(rows, key=lambda item: (item.need_rank, item.lever.stable_id))[:5]
    strongest_capacities = sorted(
        (row for row in rows if row.estimate is not None),
        key=lambda item: (
            -(item.estimate or Decimal("0")),
            -item.confidence,
            item.lever.stable_id,
        ),
    )[:5]
    evidence_updated = sorted(
        (row for row in rows if row.has_evidence_update),
        key=(
            (lambda item: (-item.completion_coverage, item.lever.stable_id))
            if composite_state is not None
            else (lambda item: (-item.included_evidence_events, item.lever.stable_id))
        ),
    )
    if verification_failed:
        recommendations, priorities = [], {}
        full_credit_competencies = 0
        partial_credit_competencies = 0
        canonical_completion_coverage = Decimal("0")
    elif composite_state is not None:
        recommendations, priorities = _rank_composite_recommendations(composite_state.state)
        competency_rows = composite_state.state["competencies"]
        full_credit_competencies = sum(
            Decimal(row["completion_credit"]) == 1 for row in competency_rows.values()
        )
        partial_credit_competencies = sum(
            Decimal("0") < Decimal(row["completion_credit"]) < 1 for row in competency_rows.values()
        )
        canonical_completion_coverage = Decimal(composite_state.state["canonical_coverage"])
    else:
        recommendations, priorities = _rank_recommendations(
            {row.lever.stable_id: row.need_score for row in rows}
        )
        full_credit_competencies = 0
        partial_credit_competencies = 0
        canonical_completion_coverage = Decimal("0")
    personal_applicability_active = False
    personally_not_applicable_competencies = 0
    personal_applicable_competency_count = 0
    personal_applicable_completion_coverage = None
    personal_coverage_error = ""
    if composite_state is not None:
        try:
            applicability = build_applicability_coverage_projection(
                user=user,
                assessment_run=run,
                composite_state=composite_state.state,
            )
        except ApplicabilityCoverageError:
            personal_coverage_error = (
                "Personal applicability history must verify before a personal-applicable "
                "coverage view can be shown. Canonical coverage is unchanged."
            )
        else:
            personal_applicability_active = True
            personally_not_applicable_competencies = (
                applicability.personally_not_applicable_competency_count
            )
            personal_applicable_competency_count = (
                applicability.personal_applicable_competency_count
            )
            personal_applicable_completion_coverage = (
                applicability.personal_applicable_completion_coverage
            )
    return ProfileSummary(
        assessment_run=run,
        highest_needs=highest_needs,
        strongest_capacities=strongest_capacities,
        evidence_updated_capacities=evidence_updated,
        recommendations=recommendations,
        recommendation_priorities=priorities,
        dynamic_state_active=dynamic_state_active,
        score_snapshot_count=ScoreSnapshot.objects.filter(assessment_run=run).count(),
        state_verification_error=state_verification_error,
        composite_state_active=composite_state_active,
        canonical_completion_coverage=canonical_completion_coverage,
        full_credit_competencies=full_credit_competencies,
        partial_credit_competencies=partial_credit_competencies,
        composite_snapshot_count=CompositeScoreSnapshot.objects.filter(assessment_run=run).count(),
        personal_applicability_active=personal_applicability_active,
        personally_not_applicable_competencies=personally_not_applicable_competencies,
        personal_applicable_competency_count=personal_applicable_competency_count,
        personal_applicable_completion_coverage=personal_applicable_completion_coverage,
        personal_coverage_error=personal_coverage_error,
    )
