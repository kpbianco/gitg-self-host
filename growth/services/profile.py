from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.contrib.auth import get_user_model

from growth.domain.ranking import (
    ProtocolWeight,
    RankingContractError,
    protocol_priority,
)
from growth.models import (
    AssessmentRun,
    LeverBaseline,
    LeverState,
    PracticeProtocol,
    ScoreSnapshot,
)
from growth.services.score_state import ScoreStateError, verify_score_state_for_run


class ProfileSummaryError(ValueError):
    pass


@dataclass(frozen=True)
class ProfileLever:
    baseline: LeverBaseline
    state: LeverState | None

    @property
    def lever(self):
        return self.baseline.lever

    @property
    def raw_self_report(self) -> Decimal | None:
        return self.baseline.raw_self_report

    @property
    def starting_estimate(self) -> Decimal | None:
        return self.baseline.calibrated_estimate

    @property
    def starting_confidence(self) -> Decimal:
        return self.baseline.evidence_confidence

    @property
    def estimate(self) -> Decimal | None:
        return (
            self.state.current_estimate
            if self.state is not None
            else self.baseline.calibrated_estimate
        )

    @property
    def confidence(self) -> Decimal:
        return (
            self.state.current_confidence
            if self.state is not None
            else self.baseline.evidence_confidence
        )

    @property
    def need_score(self) -> Decimal | None:
        return self.state.current_need_score if self.state is not None else self.baseline.need_score

    @property
    def need_rank(self) -> int:
        return self.state.current_need_rank if self.state is not None else self.baseline.need_rank

    @property
    def included_evidence_events(self) -> int:
        return self.state.included_evidence_events if self.state is not None else 0

    @property
    def has_evidence_update(self) -> bool:
        return bool(self.state is not None and self.state.cumulative_evidence_mass > 0)


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
    if dynamic_state_active:
        try:
            verify_score_state_for_run(run)
        except ScoreStateError:
            dynamic_state_active = False
            state_verification_error = (
                "Evidence and score-state verification must pass before current "
                "updates can be trusted."
            )
            states = {}
    rows = [
        ProfileLever(
            baseline=baseline,
            state=states.get(baseline.lever_id),
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
        key=lambda item: (-item.included_evidence_events, item.lever.stable_id),
    )
    recommendations, priorities = _rank_recommendations(
        {row.lever.stable_id: row.need_score for row in rows}
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
    )
