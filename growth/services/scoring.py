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
from growth.domain.evidence_dispatch import replay_evidence_by_version
from growth.domain.practice_content import (
    PracticeContentError,
    load_practice_content_bundle,
)
from growth.domain.scoring import (
    SCORING_ALGORITHM_VERSION,
    BaselineMass,
    LeverWeight,
    MappedScoringEvidence,
    ProjectedLever,
    ScoreProjection,
    ScoringContractError,
    ScoringEvidence,
    project_mapped_scores,
    project_scores,
    reconstruct_published_baseline_mass,
)
from growth.domain.typed_evidence import (
    TYPED_EVIDENCE_ALGORITHM_VERSION,
    TYPED_EVIDENCE_RULES_VERSION,
)
from growth.models import AssessmentRun, EvidenceEvent, Lever, LeverBaseline, PracticeProtocol
from growth.services.evidence import (
    EvidenceWorkflowError,
    build_evidence_ledger,
    verify_evidence_event,
)

PRODUCTION_SCORE_ELIGIBILITY_CONTRACT_VERSION = "GG-PRODUCTION-SCORE-ELIGIBILITY-2.0"
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
PRODUCTION_SCORE_MAPPING_FINGERPRINT = hashlib.sha256(
    json.dumps(
        {
            "contract_version": PRODUCTION_SCORE_ELIGIBILITY_CONTRACT_VERSION,
            "activation_scope": "all_383_canonical_protocols",
            "allocation": "complete_parent_competency_mapping",
            "evidence": [EVIDENCE_ALGORITHM_VERSION, TYPED_EVIDENCE_ALGORITHM_VERSION],
            "state": PRODUCTION_SCORE_STATE_VERSION,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
).hexdigest()
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
    "SP-STRUCTURED-EVIDENCE-ELIGIBLE",
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
def _canonical_scoring_contract():
    try:
        bundle = load_practice_content_bundle(settings.BASE_DIR)
    except PracticeContentError as exc:
        raise ScoringContractError(
            f"Canonical score activation could not be verified: {exc}"
        ) from exc
    active = {
        stable_id
        for stable_id, activation in bundle.activation_entries.items()
        if activation["score_active"] and activation["activation_status"] == "active"
    }
    protocol_ids = {protocol["stable_id"] for protocol in bundle.protocols}
    if active != protocol_ids or len(active) != 383:
        raise ScoringContractError(
            "Canonical production score activation must exactly cover all 383 protocols."
        )
    model_path = settings.BASE_DIR / "data" / "model" / "grounded_growth_model_v1.json"
    try:
        model = json.loads(model_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoringContractError("Canonical competency mappings are unavailable.") from exc
    mappings = {
        item["competency_id"]: {
            lever_id: Decimal(str(weight)) for lever_id, weight in item["lever_weights"].items()
        }
        for item in model["competency_lever_links"]
    }
    totals = {
        item["id"]: Decimal(str(item["coverage"]["total_weight"])).quantize(Decimal("0.0001"))
        for item in model["developmental_levers"]
    }
    runtime = {protocol["stable_id"]: protocol for protocol in bundle.runtime_protocols}
    return bundle, runtime, mappings, totals


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
    """Return one protocol's exact canonical parent allocation or fail closed."""

    if not protocol.score_active:
        raise ScoringContractError(
            f"{protocol.stable_id}: production score activation is disabled."
        )
    if protocol.availability != PracticeProtocol.Availability.ACTIVE:
        raise ScoringContractError(
            f"{protocol.stable_id}: score-active protocol is not runtime available."
        )
    if protocol.parent_competency_id is None:
        raise ScoringContractError(
            f"{protocol.stable_id}: canonical parent competency is unavailable."
        )
    bundle, runtime, mappings, totals = _canonical_scoring_contract()
    canonical = runtime.get(protocol.stable_id)
    activation = bundle.activation_entries.get(protocol.stable_id)
    if canonical is None or activation is None:
        raise ScoringContractError(
            f"{protocol.stable_id}: canonical runtime activation is unavailable."
        )
    if (
        activation["scoring_policy_id"] != "SP-STRUCTURED-EVIDENCE-ELIGIBLE"
        or not activation["score_active"]
        or activation["activation_status"] != "active"
        or activation["approved_contract"] != PRODUCTION_SCORE_STATE_VERSION
    ):
        raise ScoringContractError(
            f"{protocol.stable_id}: canonical activation does not match the production contract."
        )
    if protocol.parent_competency_id != canonical["parent_competency_id"]:
        raise ScoringContractError(
            f"{protocol.stable_id}: runtime parent competency does not match canonical content."
        )
    target_ids = {lever.stable_id for lever in protocol.target_levers.all()}
    if target_ids != set(canonical["target_levers"]):
        raise ScoringContractError(
            f"{protocol.stable_id}: recommendation targets do not match canonical content."
        )
    actions = tuple(
        sorted(protocol.actions.all(), key=lambda item: (item.sequence, item.stable_id))
    )
    actual_actions = tuple(
        {
            "action_stable_id": action.stable_id,
            "sequence": action.sequence,
            "evidence_rules": action.evidence_rules,
        }
        for action in actions
    )
    canonical_actions = tuple(
        {
            "action_stable_id": action["stable_id"],
            "sequence": action["sequence"],
            "evidence_rules": action["evidence_rules"],
        }
        for action in canonical["actions"]
    )
    if actual_actions != canonical_actions:
        raise ScoringContractError(
            f"{protocol.stable_id}: runtime actions do not match canonical content."
        )
    links = tuple(protocol.parent_competency.lever_links.all())
    expected_weights = mappings.get(protocol.parent_competency_id)
    if expected_weights is None:
        raise ScoringContractError(
            f"{protocol.parent_competency_id}: canonical lever mapping is unavailable."
        )
    actual_weights = {link.lever_id: link.weight for link in links}
    if actual_weights != expected_weights:
        raise ScoringContractError(
            f"{protocol.stable_id}: parent allocation weights do not match canonical data."
        )
    if any(link.lever.total_competency_weight != totals[link.lever_id] for link in links):
        raise ScoringContractError(
            f"{protocol.stable_id}: canonical lever totals do not match runtime data."
        )
    return tuple(sorted(links, key=lambda item: item.lever_id))


def protocol_requires_production_scoring(protocol: PracticeProtocol) -> bool:
    """Return activation state and validate every activated protocol exactly."""

    bundle, runtime, _, _ = _canonical_scoring_contract()
    activation = bundle.activation_entries.get(protocol.stable_id)
    canonically_active = bool(
        protocol.stable_id in runtime and activation and activation["score_active"]
    )
    if not canonically_active and not protocol.score_active:
        return False
    validate_production_scoring_protocol(protocol)
    return canonically_active


def validate_production_scoring_event(
    event: EvidenceEvent,
    assessment_run: AssessmentRun,
) -> None:
    if event.algorithm_version not in {
        EVIDENCE_ALGORITHM_VERSION,
        TYPED_EVIDENCE_ALGORITHM_VERSION,
    }:
        raise ScoringContractError(
            f"{event.pk}: evidence algorithm is not production score eligible."
        )
    snapshot = event.input_snapshot
    if not isinstance(snapshot, dict):
        raise ScoringContractError(
            f"{event.pk}: evidence snapshot is not production score eligible."
        )
    protocol = event.check_in.sprint.protocol
    validate_production_scoring_protocol(protocol)
    if event.protocol_stable_id != protocol.stable_id:
        raise ScoringContractError(f"{event.pk}: evidence protocol stable IDs do not match.")
    if snapshot.get("protocol_stable_id") != protocol.stable_id:
        raise ScoringContractError(
            f"{event.pk}: snapshotted protocol is not production score eligible."
        )
    if (
        event.check_in.action_id != event.action_stable_id
        or snapshot.get("action_stable_id") != event.action_stable_id
    ):
        raise ScoringContractError(f"{event.pk}: evidence action stable IDs do not match.")
    action = event.check_in.action
    rule_version = action.evidence_rules.get("schema_version")
    expected_algorithm = (
        TYPED_EVIDENCE_ALGORITHM_VERSION
        if rule_version == TYPED_EVIDENCE_RULES_VERSION
        else EVIDENCE_ALGORITHM_VERSION
    )
    if event.algorithm_version != expected_algorithm:
        raise ScoringContractError(
            f"{event.pk}: evidence algorithm does not match the action rules."
        )
    if rule_version == TYPED_EVIDENCE_RULES_VERSION:
        activation = _canonical_scoring_contract()[0].activation_entries[protocol.stable_id]
        if (
            snapshot.get("competency_stable_id") != protocol.parent_competency_id
            or snapshot.get("scoring_policy_id") != activation["scoring_policy_id"]
        ):
            raise ScoringContractError(
                f"{event.pk}: typed evidence identity does not match canonical activation."
            )
    elif snapshot.get("evidence_rules") != action.evidence_rules:
        raise ScoringContractError(
            f"{event.pk}: snapshotted evidence rules do not match canonical action rules."
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
    """Project mixed-protocol evidence for one immutable assessment run."""

    resolved_events = tuple(events)
    if not resolved_events:
        raise ScoringContractError("A production score projection requires evidence events.")
    protocol_ids = {event.protocol_stable_id for event in resolved_events}
    protocols = {
        protocol.stable_id: protocol
        for protocol in PracticeProtocol.objects.filter(stable_id__in=protocol_ids)
        .select_related("parent_competency")
        .prefetch_related("target_levers", "parent_competency__lever_links__lever")
    }
    if set(protocols) != protocol_ids:
        raise ScoringContractError("One or more score-active protocols are unavailable.")
    links_by_protocol = {
        stable_id: validate_production_scoring_protocol(protocol)
        for stable_id, protocol in protocols.items()
    }
    link_ids = {link.lever_id for links in links_by_protocol.values() for link in links}

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
            "The assessment does not contain every required scoring baseline."
        )
    masses: dict[str, BaselineMass] = {}
    uses_reconstructed = False
    for lever_id in sorted(link_ids):
        mass, reconstructed = _baseline_mass(baseline_rows[lever_id])
        if mass is None:
            raise ScoringContractError(f"{lever_id}: scoring baseline mass is unavailable.")
        masses[lever_id] = mass
        uses_reconstructed = uses_reconstructed or reconstructed

    mapped_events = []
    for event in resolved_events:
        validate_production_scoring_event(event, assessment_run)
        try:
            verify_evidence_event(event)
            replayed = replay_evidence_by_version(event.algorithm_version, event.input_snapshot)
        except EvidenceWorkflowError as exc:
            raise ScoringContractError(str(exc)) from exc
        withholding = tuple(getattr(replayed, "withholding_reasons", ()))
        performance = getattr(replayed, "competency_performance", None)
        mapped_events.append(
            MappedScoringEvidence(
                evidence=ScoringEvidence(
                    event_key=str(event.pk),
                    action_stable_id=event.action_stable_id,
                    performance=event.performance if performance is None else performance,
                    base_evidence_mass=event.base_evidence_mass,
                    direction=(
                        "" if withholding else event.input_snapshot.get("evidence_direction") or ""
                    ),
                ),
                weights=tuple(
                    LeverWeight(
                        lever_id=link.lever_id,
                        weight=link.weight,
                        total_competency_weight=link.lever.total_competency_weight,
                    )
                    for link in links_by_protocol[event.protocol_stable_id]
                ),
            )
        )
    projection = project_mapped_scores(
        baselines=masses,
        events=mapped_events,
    )
    first_protocol = protocols[resolved_events[0].protocol_stable_id]
    return AssessmentScoreProjection(
        assessment_run=assessment_run,
        protocol=first_protocol,
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
