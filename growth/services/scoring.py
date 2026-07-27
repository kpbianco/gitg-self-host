from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from django.contrib.auth import get_user_model

from growth.domain.scoring import (
    BaselineMass,
    LeverWeight,
    ProjectedLever,
    ScoreProjection,
    ScoringContractError,
    ScoringEvidence,
    project_scores,
    reconstruct_published_baseline_mass,
)
from growth.models import AssessmentRun, EvidenceEvent, Lever, LeverBaseline, PracticeProtocol
from growth.services.evidence import (
    EvidenceWorkflowError,
    build_evidence_ledger,
    verify_evidence_event,
)

FRIENDSHIP_PROTOCOL_ID = "PRACTICE-FRIENDSHIP-01"
FRIENDSHIP_COMPETENCY_ID = "17.03"


@dataclass(frozen=True)
class ShadowLeverRow:
    lever: Lever
    baseline: LeverBaseline
    weight: Decimal
    projection: ProjectedLever

    @property
    def estimate_delta(self) -> Decimal:
        return self.projection.projected_estimate - self.baseline.calibrated_estimate

    @property
    def confidence_delta(self) -> Decimal:
        return self.projection.projected_confidence - self.baseline.evidence_confidence


@dataclass(frozen=True)
class UserShadowProjection:
    assessment_run: AssessmentRun | None
    protocol: PracticeProtocol | None
    projection: ScoreProjection | None
    rows: tuple[ShadowLeverRow, ...]
    unavailable_reason: str
    uses_reconstructed_baseline: bool


@dataclass(frozen=True)
class AssessmentScoreProjection:
    assessment_run: AssessmentRun
    protocol: PracticeProtocol
    projection: ScoreProjection
    baselines: tuple[LeverBaseline, ...]
    uses_reconstructed_baseline: bool


def _baseline_mass(baseline: LeverBaseline) -> tuple[BaselineMass | None, bool]:
    if baseline.calibrated_estimate is None:
        return None, False
    if baseline.baseline_alpha is not None and baseline.baseline_beta is not None:
        valid_sources = {
            LeverBaseline.BaselineMassSource.CANONICAL_RESULT,
            LeverBaseline.BaselineMassSource.PUBLISHED_RECONSTRUCTION,
        }
        if baseline.baseline_mass_source not in valid_sources:
            raise ScoringContractError(
                f"{baseline.lever_id}: baseline mass provenance is not recognized."
            )
        total_mass = baseline.baseline_alpha + baseline.baseline_beta
        if total_mass <= 0 or abs(
            baseline.baseline_alpha / total_mass - baseline.calibrated_estimate
        ) > Decimal("0.0002"):
            raise ScoringContractError(
                f"{baseline.lever_id}: baseline mass does not reproduce its estimate."
            )
        return (
            BaselineMass(
                lever_id=baseline.lever_id,
                alpha=baseline.baseline_alpha,
                beta=baseline.baseline_beta,
                confidence=baseline.evidence_confidence,
            ),
            baseline.baseline_mass_source
            == LeverBaseline.BaselineMassSource.PUBLISHED_RECONSTRUCTION,
        )
    reconstructed = reconstruct_published_baseline_mass(
        lever_id=baseline.lever_id,
        raw_self_report=baseline.raw_self_report,
        calibrated_estimate=baseline.calibrated_estimate,
        evidence_confidence=baseline.evidence_confidence,
    )
    return reconstructed, reconstructed is not None


def project_assessment_events(
    assessment_run: AssessmentRun,
    events: Iterable[EvidenceEvent],
) -> AssessmentScoreProjection:
    """Project reviewed friendship evidence for one immutable assessment run."""

    protocol = (
        PracticeProtocol.objects.filter(stable_id=FRIENDSHIP_PROTOCOL_ID)
        .select_related("parent_competency")
        .prefetch_related("target_levers", "parent_competency__lever_links__lever")
        .first()
    )
    if protocol is None or protocol.parent_competency_id != FRIENDSHIP_COMPETENCY_ID:
        raise ScoringContractError(
            "The reviewed practice-to-competency scoring link is unavailable."
        )
    links = tuple(protocol.parent_competency.lever_links.all())
    link_ids = {link.lever_id for link in links}
    target_ids = {lever.stable_id for lever in protocol.target_levers.all()}
    if not target_ids or not target_ids.issubset(link_ids):
        raise ScoringContractError(
            "Recommendation targets do not match the reviewed scoring mapping."
        )

    baseline_rows = {
        baseline.lever_id: baseline
        for baseline in LeverBaseline.objects.filter(
            user=assessment_run.user,
            assessment_run=assessment_run,
            lever_id__in=link_ids,
        ).select_related("lever")
    }
    if set(baseline_rows) != link_ids:
        raise ScoringContractError(
            "The assessment does not contain every reviewed scoring baseline."
        )
    masses: dict[str, BaselineMass] = {}
    uses_reconstructed = False
    for lever_id in sorted(link_ids):
        mass, reconstructed = _baseline_mass(baseline_rows[lever_id])
        if mass is None:
            raise ScoringContractError(f"{lever_id}: scoring baseline mass is unavailable.")
        masses[lever_id] = mass
        uses_reconstructed = uses_reconstructed or reconstructed

    resolved_events = tuple(events)
    for event in resolved_events:
        if event.protocol_stable_id != protocol.stable_id:
            raise ScoringContractError(
                f"{event.pk}: evidence belongs to an unreviewed scoring protocol."
            )
        if event.check_in.sprint.assessment_run_id != assessment_run.pk:
            raise ScoringContractError(
                f"{event.pk}: evidence and assessment stable IDs do not match."
            )
        if event.check_in.sprint.user_id != assessment_run.user_id:
            raise ScoringContractError(f"{event.pk}: evidence and assessment users do not match.")
        try:
            verify_evidence_event(event)
        except EvidenceWorkflowError as exc:
            raise ScoringContractError(str(exc)) from exc

    weights = tuple(
        LeverWeight(
            lever_id=link.lever_id,
            weight=link.weight,
            total_competency_weight=link.lever.total_competency_weight,
        )
        for link in links
    )
    scoring_events = tuple(
        ScoringEvidence(
            event_key=str(event.pk),
            action_stable_id=event.action_stable_id,
            performance=event.performance,
            base_evidence_mass=event.base_evidence_mass,
            direction=event.input_snapshot.get("evidence_direction") or "",
        )
        for event in resolved_events
    )
    projection = project_scores(
        baselines=masses,
        weights=weights,
        events=scoring_events,
    )
    return AssessmentScoreProjection(
        assessment_run=assessment_run,
        protocol=protocol,
        projection=projection,
        baselines=tuple(baseline_rows[key] for key in sorted(baseline_rows)),
        uses_reconstructed_baseline=uses_reconstructed,
    )


def build_user_shadow_projection(
    user: get_user_model(),
) -> UserShadowProjection:
    """Build the M3A read-only projection for the first complete protocol."""

    run = AssessmentRun.objects.filter(user=user).first()
    protocol = (
        PracticeProtocol.objects.filter(stable_id=FRIENDSHIP_PROTOCOL_ID)
        .select_related("parent_competency")
        .prefetch_related("target_levers", "parent_competency__lever_links__lever")
        .first()
    )
    if run is None:
        return UserShadowProjection(None, protocol, None, (), "No assessment is available.", False)
    if protocol is None or protocol.parent_competency_id != FRIENDSHIP_COMPETENCY_ID:
        return UserShadowProjection(
            run,
            protocol,
            None,
            (),
            "The practice has no reviewed competency-to-lever scoring link.",
            False,
        )

    links = tuple(protocol.parent_competency.lever_links.all())
    link_ids = {link.lever_id for link in links}
    target_ids = {lever.stable_id for lever in protocol.target_levers.all()}
    if not target_ids or not target_ids.issubset(link_ids):
        return UserShadowProjection(
            run,
            protocol,
            None,
            (),
            "Scoring mapping verification must pass before a projection can be shown.",
            False,
        )

    baseline_rows = {
        baseline.lever_id: baseline
        for baseline in LeverBaseline.objects.filter(
            user=user,
            assessment_run=run,
            lever_id__in=link_ids,
        ).select_related("lever")
    }
    masses: dict[str, BaselineMass] = {}
    uses_reconstructed = False
    missing: list[str] = []
    for lever_id in sorted(link_ids):
        baseline = baseline_rows.get(lever_id)
        if baseline is None:
            missing.append(lever_id)
            continue
        try:
            mass, reconstructed = _baseline_mass(baseline)
        except ScoringContractError:
            return UserShadowProjection(
                run,
                protocol,
                None,
                (),
                "Baseline verification must pass before a projection can be shown.",
                uses_reconstructed,
            )
        if mass is None:
            missing.append(lever_id)
            continue
        masses[lever_id] = mass
        uses_reconstructed = uses_reconstructed or reconstructed
    if missing:
        return UserShadowProjection(
            run,
            protocol,
            None,
            (),
            "This assessment does not contain enough baseline information for the preview.",
            uses_reconstructed,
        )

    try:
        ledger = build_evidence_ledger(user)
    except EvidenceWorkflowError:
        return UserShadowProjection(
            run,
            protocol,
            None,
            (),
            "Evidence replay verification must pass before a projection can be shown.",
            uses_reconstructed,
        )
    events = tuple(
        ScoringEvidence(
            event_key=str(row.event.pk),
            action_stable_id=row.event.action_stable_id,
            performance=row.event.performance,
            base_evidence_mass=row.event.base_evidence_mass,
            direction=row.event.input_snapshot.get("evidence_direction") or "",
        )
        for row in reversed(ledger.rows)
        if row.event.protocol_stable_id == protocol.stable_id
        and row.event.check_in.sprint.assessment_run_id == run.pk
    )
    weights = tuple(
        LeverWeight(
            lever_id=link.lever_id,
            weight=link.weight,
            total_competency_weight=link.lever.total_competency_weight,
        )
        for link in links
    )
    try:
        projection = project_scores(
            baselines=masses,
            weights=weights,
            events=events,
        )
    except ScoringContractError:
        return UserShadowProjection(
            run,
            protocol,
            None,
            (),
            "Scoring verification must pass before a projection can be shown.",
            uses_reconstructed,
        )

    projected_by_id = {item.lever_id: item for item in projection.levers}
    rows = tuple(
        ShadowLeverRow(
            lever=link.lever,
            baseline=baseline_rows[link.lever_id],
            weight=link.weight,
            projection=projected_by_id[link.lever_id],
        )
        for link in sorted(links, key=lambda item: (-item.weight, item.lever_id))
    )
    return UserShadowProjection(
        assessment_run=run,
        protocol=protocol,
        projection=projection,
        rows=rows,
        unavailable_reason="",
        uses_reconstructed_baseline=uses_reconstructed,
    )
