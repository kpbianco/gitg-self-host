from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model

from growth.domain.evidence import EVIDENCE_ALGORITHM_VERSION
from growth.domain.practice_content import (
    PracticeContentError,
    load_practice_content_bundle,
)
from growth.domain.scoring import (
    SCORING_ALGORITHM_VERSION,
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

PRODUCTION_SCORE_ELIGIBILITY_CONTRACT_VERSION = "GG-PRODUCTION-SCORE-ELIGIBILITY-1.0"
PRODUCTION_EVIDENCE_RULES_VERSION = "practice-observation-v1"
PRODUCTION_SCORE_STATE_VERSION = "GG-SCORE-STATE-1.0"
FRIENDSHIP_PROTOCOL_ID = "PRACTICE-FRIENDSHIP-01"
FRIENDSHIP_COMPETENCY_ID = "17.03"
FRIENDSHIP_TARGET_LEVER_IDS = frozenset({"L23", "L24", "L26"})
FRIENDSHIP_ALLOCATION = {
    "L10": (Decimal("0.1500"), Decimal("17.8000")),
    "L23": (Decimal("0.1000"), Decimal("14.7500")),
    "L24": (Decimal("0.1000"), Decimal("13.3500")),
    "L26": (Decimal("0.6500"), Decimal("10.2500")),
}
PRODUCTION_SCORE_MAPPING_FINGERPRINT = (
    "f7639a0c623f1baac9469f34fe49ca9e2eb0be8fc1c616ab662996b2e90bf2bf"
)
FRIENDSHIP_ACTIONS = (
    {
        "action_stable_id": "PRACTICE-FRIENDSHIP-01-A1",
        "sequence": 1,
        "evidence_rules": {
            "schema_version": PRODUCTION_EVIDENCE_RULES_VERSION,
            "primary_markers": [
                "moved_beyond_transactional",
                "meaningful_information_shared",
            ],
            "supporting_markers": [
                "follow_up_question_asked",
                "user_initiated",
            ],
        },
    },
    {
        "action_stable_id": "PRACTICE-FRIENDSHIP-01-A2",
        "sequence": 2,
        "evidence_rules": {
            "schema_version": PRODUCTION_EVIDENCE_RULES_VERSION,
            "primary_markers": ["future_interaction_scheduled"],
            "supporting_markers": ["user_initiated"],
        },
    },
    {
        "action_stable_id": "PRACTICE-FRIENDSHIP-01-A3",
        "sequence": 3,
        "evidence_rules": {
            "schema_version": PRODUCTION_EVIDENCE_RULES_VERSION,
            "primary_markers": [
                "follow_up_within_seven_days",
                "follow_up_question_asked",
            ],
            "supporting_markers": [
                "meaningful_information_shared",
                "user_initiated",
            ],
        },
    },
)
_FRIENDSHIP_ACTIVATION_APPROVAL = (
    "SP-SELF-REPORT-ELIGIBLE",
    True,
    "active",
    PRODUCTION_SCORE_STATE_VERSION,
    "docs/PRODUCT_DECISIONS.md#decision-035",
    "accepted_and_activated",
)


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


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


@lru_cache(maxsize=1)
def _verify_canonical_friendship_activation() -> None:
    try:
        bundle = load_practice_content_bundle(settings.BASE_DIR)
    except PracticeContentError as exc:
        raise ScoringContractError(
            f"Canonical score activation could not be verified: {exc}"
        ) from exc
    try:
        activation = bundle.activation_entries[FRIENDSHIP_PROTOCOL_ID]
    except KeyError as exc:
        raise ScoringContractError("Canonical friendship score activation is unavailable.") from exc
    actual = (
        activation["scoring_policy_id"],
        activation["score_active"],
        activation["activation_status"],
        activation["approved_contract"],
        activation["decision_reference"],
        activation["shadow_test_status"],
    )
    if actual != _FRIENDSHIP_ACTIVATION_APPROVAL:
        raise ScoringContractError(
            "Canonical friendship score activation does not match the reviewed contract."
        )


def _production_contract_payload(
    protocol: PracticeProtocol,
    links,
) -> dict[str, Any]:
    actions = tuple(protocol.actions.order_by("sequence", "stable_id"))
    return {
        "contract_version": PRODUCTION_SCORE_ELIGIBILITY_CONTRACT_VERSION,
        "protocol_stable_id": protocol.stable_id,
        "competency_stable_id": protocol.parent_competency_id,
        "evidence_algorithm_version": EVIDENCE_ALGORITHM_VERSION,
        "evidence_schema_version": PRODUCTION_EVIDENCE_RULES_VERSION,
        "scoring_algorithm_version": SCORING_ALGORITHM_VERSION,
        "score_state_version": PRODUCTION_SCORE_STATE_VERSION,
        "target_lever_ids": sorted(lever.stable_id for lever in protocol.target_levers.all()),
        "actions": [
            {
                "action_stable_id": action.stable_id,
                "sequence": action.sequence,
                "evidence_rules": action.evidence_rules,
            }
            for action in actions
        ],
        "allocation": [
            {
                "lever_id": link.lever_id,
                "weight": f"{link.weight:.4f}",
                "total_competency_weight": (f"{link.lever.total_competency_weight:.4f}"),
            }
            for link in sorted(links, key=lambda item: item.lever_id)
        ],
    }


def validate_production_scoring_protocol(
    protocol: PracticeProtocol,
):
    """Return the exact reviewed friendship allocation or fail closed."""

    if protocol.stable_id != FRIENDSHIP_PROTOCOL_ID:
        raise ScoringContractError(
            f"{protocol.stable_id}: protocol is not production score eligible."
        )
    if not protocol.score_active:
        raise ScoringContractError(
            "Friendship score activation is disabled; production scoring stopped."
        )
    if protocol.parent_competency_id != FRIENDSHIP_COMPETENCY_ID:
        raise ScoringContractError(
            "The reviewed practice-to-competency scoring link is unavailable."
        )
    _verify_canonical_friendship_activation()

    target_ids = {lever.stable_id for lever in protocol.target_levers.all()}
    if target_ids != FRIENDSHIP_TARGET_LEVER_IDS:
        raise ScoringContractError(
            "Friendship recommendation targets do not match the reviewed scoring contract."
        )
    actions = tuple(protocol.actions.order_by("sequence", "stable_id"))
    actual_actions = tuple(
        {
            "action_stable_id": action.stable_id,
            "sequence": action.sequence,
            "evidence_rules": action.evidence_rules,
        }
        for action in actions
    )
    if actual_actions != FRIENDSHIP_ACTIONS:
        raise ScoringContractError(
            "Friendship actions or evidence rules do not match the reviewed scoring contract."
        )
    links = tuple(protocol.parent_competency.lever_links.all())
    actual_allocation = {
        link.lever_id: (link.weight, link.lever.total_competency_weight) for link in links
    }
    if actual_allocation != FRIENDSHIP_ALLOCATION:
        raise ScoringContractError(
            "Friendship allocation weights or lever totals do not match the reviewed contract."
        )
    fingerprint = _canonical_hash(_production_contract_payload(protocol, links))
    if fingerprint != PRODUCTION_SCORE_MAPPING_FINGERPRINT:
        raise ScoringContractError(
            "Friendship production score-eligibility fingerprint does not verify."
        )
    return tuple(sorted(links, key=lambda item: item.lever_id))


def protocol_requires_production_scoring(protocol: PracticeProtocol) -> bool:
    """Return false for all unapproved protocols; validate friendship exactly."""

    if protocol.stable_id != FRIENDSHIP_PROTOCOL_ID:
        return False
    validate_production_scoring_protocol(protocol)
    return True


def validate_production_scoring_event(
    event: EvidenceEvent,
    assessment_run: AssessmentRun,
) -> None:
    if event.algorithm_version != EVIDENCE_ALGORITHM_VERSION:
        raise ScoringContractError(
            f"{event.pk}: evidence algorithm is not production score eligible."
        )
    snapshot = event.input_snapshot
    if not isinstance(snapshot, dict):
        raise ScoringContractError(
            f"{event.pk}: evidence snapshot is not production score eligible."
        )
    if event.protocol_stable_id != FRIENDSHIP_PROTOCOL_ID:
        raise ScoringContractError(
            f"{event.pk}: evidence belongs to an unreviewed scoring protocol."
        )
    if snapshot.get("protocol_stable_id") != FRIENDSHIP_PROTOCOL_ID:
        raise ScoringContractError(
            f"{event.pk}: snapshotted protocol is not production score eligible."
        )
    expected_by_id = {action["action_stable_id"]: action for action in FRIENDSHIP_ACTIONS}
    expected_action = expected_by_id.get(event.action_stable_id)
    if expected_action is None:
        raise ScoringContractError(f"{event.pk}: evidence action is not production score eligible.")
    if (
        event.check_in.action_id != event.action_stable_id
        or snapshot.get("action_stable_id") != event.action_stable_id
    ):
        raise ScoringContractError(f"{event.pk}: evidence action stable IDs do not match.")
    action = event.check_in.action
    actual_action = {
        "action_stable_id": action.stable_id,
        "sequence": action.sequence,
        "evidence_rules": action.evidence_rules,
    }
    if actual_action != expected_action:
        raise ScoringContractError(
            f"{event.pk}: runtime action does not match the reviewed scoring contract."
        )
    if snapshot.get("evidence_rules") != expected_action["evidence_rules"]:
        raise ScoringContractError(
            f"{event.pk}: snapshotted evidence rules do not match the reviewed scoring contract."
        )
    if event.check_in.sprint.assessment_run_id != assessment_run.pk:
        raise ScoringContractError(f"{event.pk}: evidence and assessment stable IDs do not match.")
    if event.check_in.sprint.user_id != assessment_run.user_id:
        raise ScoringContractError(f"{event.pk}: evidence and assessment users do not match.")


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
    links = validate_production_scoring_protocol(protocol)
    link_ids = {link.lever_id for link in links}

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
        validate_production_scoring_event(event, assessment_run)
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

    try:
        links = validate_production_scoring_protocol(protocol)
    except ScoringContractError:
        return UserShadowProjection(
            run,
            protocol,
            None,
            (),
            "Scoring mapping verification must pass before a projection can be shown.",
            False,
        )
    link_ids = {link.lever_id for link in links}

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
