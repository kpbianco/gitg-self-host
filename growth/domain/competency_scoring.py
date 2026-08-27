from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from growth.domain.scoring import (
    BaselineMass,
    LeverWeight,
    ScoreProjection,
    ScoringContractError,
    ScoringEvidence,
    project_scores,
)
from growth.domain.typed_evidence import (
    TYPED_EVIDENCE_ALGORITHM_VERSION,
    TypedEvidenceContractError,
    TypedEvidenceResult,
    replay_typed_evidence,
)

COMPETENCY_EVIDENCE_SHADOW_VERSION = "GG-COMPETENCY-EVIDENCE-SHADOW-1.0"
COMPETENCY_LEVER_SHADOW_VERSION = "GG-COMPETENCY-LEVER-SHADOW-1.0"
COMPETENCY_LEVER_MAPPING_VERSION = "GG-COMPETENCY-LEVER-MAPPING-1.0"

SUPPORTED_POLICY_IDS = frozenset(
    {
        "SP-SELF-REPORT-ELIGIBLE",
        "SP-CORROBORATION-REQUIRED",
        "SP-ARTIFACT-OBJECTIVE-PREFERRED",
        "SP-QUALIFIED-EVIDENCE-REQUIRED",
        "SP-SHADOW-ONLY",
        "SP-NON-SCORED-REFLECTION",
        "SP-STRUCTURED-EVIDENCE-ELIGIBLE",
    }
)
SUPPORTED_DIRECTIONS = frozenset({"supports", "mixed", "contradicts", "inconclusive", "unknown"})
SUPPORTED_MEASUREMENT_KINDS = frozenset(
    {
        "boolean",
        "count",
        "bounded_frequency",
        "ordinal",
        "duration",
        "artifact",
        "conceptual",
        "scenario",
        "objective",
        "attestation",
    }
)
SUPPORTED_PROVENANCE_KINDS = frozenset(
    {
        "firsthand_self_report",
        "reviewed_artifact",
        "objective_indicator",
        "consented_observer",
        "qualified_attestation",
    }
)
DIRECTION_MULTIPLIERS = {
    "supports": Decimal("1"),
    "mixed": Decimal("0.5"),
    "contradicts": Decimal("0"),
}
TRANSFER_RANK = {
    "protocol_only": 0,
    "context_bound": 1,
    "cross_context_candidate": 2,
    "cross_context_supported": 3,
}
SIX_PLACES = Decimal("0.000001")
FOUR_PLACES = Decimal("0.0001")
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
STABLE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class CompetencyScoringContractError(ValueError):
    pass


@dataclass(frozen=True)
class CompetencyEvidenceCandidate:
    event_key: str
    origin_key: str
    assessment_epoch_id: str
    protocol_stable_id: str
    action_stable_id: str
    competency_id: str
    policy_id: str
    competency_performance: Decimal | None
    base_evidence_mass: Decimal
    direction: str
    adverse: bool
    provenance_kinds: tuple[str, ...]
    measurement_kinds: tuple[str, ...]
    context_key: str
    transfer_disposition: str
    observed_on: str
    max_age_days: int | None
    upstream_withholding_reasons: tuple[str, ...] = ()
    qualified_attestation_valid: bool = False


@dataclass(frozen=True)
class CompetencyEvidenceContribution:
    event_key: str
    origin_key: str
    action_stable_id: str
    included: bool
    withholding_reason: str
    withholding_reasons: tuple[str, ...]
    direction: str
    adverse: bool
    transfer_disposition: str
    provenance_kinds: tuple[str, ...]
    measurement_kinds: tuple[str, ...]
    competency_performance: Decimal | None
    evidence_mass: Decimal
    success_mass: Decimal
    failure_mass: Decimal


@dataclass(frozen=True)
class CompetencyEvidenceShadow:
    algorithm_version: str
    assessment_epoch_id: str
    competency_id: str
    policy_id: str
    as_of_date: str
    evidence_state: str
    competency_estimate: None
    event_count: int
    included_event_count: int
    withheld_event_count: int
    reversed_event_count: int
    evidence_mass: Decimal
    success_mass: Decimal
    failure_mass: Decimal
    contributions: tuple[CompetencyEvidenceContribution, ...]


@dataclass(frozen=True)
class CompetencyLeverShadow:
    algorithm_version: str
    competency_evidence_version: str
    assessment_epoch_id: str
    competency_id: str
    as_of_date: str
    baseline_assessment_epoch_id: str
    canonical_mapping_fingerprint: str
    minimum_transfer_disposition: str
    allocated_event_keys: tuple[str, ...]
    projection: ScoreProjection


def _quantize(value: Decimal, places: Decimal = SIX_PLACES) -> Decimal:
    return value.quantize(places, rounding=ROUND_HALF_UP)


def _require_finite_unit(value: Decimal, label: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0 or value > 1:
        raise CompetencyScoringContractError(f"{label} must be a finite Decimal in [0, 1].")


def candidate_from_typed_evidence(
    result: TypedEvidenceResult,
) -> CompetencyEvidenceCandidate:
    """Create an explicit direct-competency candidate from typed protocol evidence.

    Competency performance and transfer are replayed from the hashed,
    materialized typed rule. Protocol completion or protocol performance is
    deliberately not substituted.
    """

    try:
        if result.algorithm_version != TYPED_EVIDENCE_ALGORITHM_VERSION:
            raise CompetencyScoringContractError("Typed protocol evidence version is unsupported.")
        verified = replay_typed_evidence(result.input_snapshot)
        if verified != result:
            raise CompetencyScoringContractError(
                "Typed protocol evidence does not match its replayed snapshot."
            )
        if verified.transfer_disposition == "protocol_only":
            raise CompetencyScoringContractError(
                "Protocol-only typed evidence cannot become a competency candidate."
            )
        snapshot = verified.input_snapshot
        competency_measurement_ids = frozenset(
            snapshot["materialized_rules"]["competency_measurement_ids"]
        )
        observed_competency_measurements = tuple(
            item
            for item in snapshot["observations"]
            if item["measurement_id"] in competency_measurement_ids and item["state"] == "observed"
        )
        max_age_days = snapshot["materialized_rules"]["max_age_days"]
        qualified_attestation_valid = any(
            item["kind"] == "attestation"
            and item["provenance_kind"] == "qualified_attestation"
            and Decimal(item["normalized_score"]) > 0
            for item in observed_competency_measurements
        )
        return CompetencyEvidenceCandidate(
            event_key=snapshot["event_key"],
            origin_key=snapshot["origin_key"],
            assessment_epoch_id=snapshot["assessment_epoch_id"],
            protocol_stable_id=snapshot["protocol_stable_id"],
            action_stable_id=snapshot["action_stable_id"],
            competency_id=snapshot["competency_stable_id"],
            policy_id=snapshot["scoring_policy_id"],
            competency_performance=verified.competency_performance,
            base_evidence_mass=verified.base_evidence_mass,
            direction=verified.direction,
            adverse=verified.adverse,
            provenance_kinds=tuple(
                sorted({item["provenance_kind"] for item in observed_competency_measurements})
            ),
            measurement_kinds=tuple(
                sorted({item["kind"] for item in observed_competency_measurements})
            ),
            context_key=snapshot["context_key"],
            transfer_disposition=verified.transfer_disposition,
            observed_on=snapshot["observed_on"],
            max_age_days=max_age_days,
            upstream_withholding_reasons=verified.withholding_reasons,
            qualified_attestation_valid=qualified_attestation_valid,
        )
    except TypedEvidenceContractError as exc:
        raise CompetencyScoringContractError(
            f"Typed protocol evidence snapshot did not replay: {exc}"
        ) from exc
    except (AttributeError, KeyError, TypeError) as exc:
        raise CompetencyScoringContractError(
            "Typed protocol evidence snapshot is incomplete."
        ) from exc


def _validate_candidate(candidate: CompetencyEvidenceCandidate) -> None:
    if not isinstance(candidate, CompetencyEvidenceCandidate):
        raise CompetencyScoringContractError(
            "Competency evidence candidates must use the accepted candidate contract."
        )
    for label, value in (
        ("event key", candidate.event_key),
        ("origin key", candidate.origin_key),
        ("assessment epoch", candidate.assessment_epoch_id),
        ("protocol stable ID", candidate.protocol_stable_id),
        ("action stable ID", candidate.action_stable_id),
        ("competency stable ID", candidate.competency_id),
        ("context key", candidate.context_key),
    ):
        if not isinstance(value, str) or not STABLE_TOKEN.fullmatch(value):
            raise CompetencyScoringContractError(
                f"Competency evidence requires a stable {label} token."
            )
    if not isinstance(candidate.policy_id, str) or candidate.policy_id not in SUPPORTED_POLICY_IDS:
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: scoring policy is unsupported."
        )
    if not isinstance(candidate.direction, str) or candidate.direction not in SUPPORTED_DIRECTIONS:
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: evidence direction is unsupported."
        )
    if (
        not isinstance(candidate.transfer_disposition, str)
        or candidate.transfer_disposition not in TRANSFER_RANK
    ):
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: transfer disposition is unsupported."
        )
    if not isinstance(candidate.adverse, bool):
        raise CompetencyScoringContractError(f"{candidate.event_key}: adverse must be Boolean.")
    if candidate.competency_performance is None:
        if not candidate.upstream_withholding_reasons:
            raise CompetencyScoringContractError(
                f"{candidate.event_key}: unknown competency performance must be withheld."
            )
    else:
        _require_finite_unit(
            candidate.competency_performance,
            f"{candidate.event_key} competency performance",
        )
    _require_finite_unit(
        candidate.base_evidence_mass,
        f"{candidate.event_key} base evidence mass",
    )
    if not isinstance(candidate.provenance_kinds, tuple):
        raise CompetencyScoringContractError(f"{candidate.event_key}: provenance must be a tuple.")
    if any(not isinstance(item, str) for item in candidate.provenance_kinds):
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: provenance entries must be strings."
        )
    if not candidate.provenance_kinds and not candidate.upstream_withholding_reasons:
        raise CompetencyScoringContractError(f"{candidate.event_key}: provenance cannot be empty.")
    if not set(candidate.provenance_kinds).issubset(SUPPORTED_PROVENANCE_KINDS):
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: provenance kind is unsupported."
        )
    if len(candidate.provenance_kinds) != len(set(candidate.provenance_kinds)):
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: provenance contains duplicates."
        )
    if not isinstance(candidate.measurement_kinds, tuple):
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: measurement kinds must be a tuple."
        )
    if any(not isinstance(item, str) for item in candidate.measurement_kinds):
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: measurement kind entries must be strings."
        )
    if not candidate.measurement_kinds and not candidate.upstream_withholding_reasons:
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: measurement kinds cannot be empty."
        )
    if not set(candidate.measurement_kinds).issubset(SUPPORTED_MEASUREMENT_KINDS):
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: measurement kind is unsupported."
        )
    if len(candidate.measurement_kinds) != len(set(candidate.measurement_kinds)):
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: measurement kinds contain duplicates."
        )
    if not isinstance(candidate.upstream_withholding_reasons, tuple) or any(
        not isinstance(reason, str) or not STABLE_TOKEN.fullmatch(reason)
        for reason in candidate.upstream_withholding_reasons
    ):
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: upstream withholding reasons must be stable tokens."
        )
    if len(candidate.upstream_withholding_reasons) != len(
        set(candidate.upstream_withholding_reasons)
    ):
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: upstream withholding reasons contain duplicates."
        )
    if not isinstance(candidate.qualified_attestation_valid, bool):
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: qualified attestation validity must be Boolean."
        )
    if candidate.qualified_attestation_valid and not (
        "attestation" in candidate.measurement_kinds
        and "qualified_attestation" in candidate.provenance_kinds
    ):
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: qualified attestation validity lacks its typed evidence."
        )
    try:
        date.fromisoformat(candidate.observed_on)
    except (TypeError, ValueError) as exc:
        raise CompetencyScoringContractError(
            f"{candidate.event_key}: observed_on must be an ISO date."
        ) from exc
    if candidate.max_age_days is not None and (
        not isinstance(candidate.max_age_days, int)
        or isinstance(candidate.max_age_days, bool)
        or candidate.max_age_days < 1
    ):
        raise CompetencyScoringContractError(f"{candidate.event_key}: max_age_days is invalid.")


def _policy_failure(
    policy_id: str,
    candidates: tuple[CompetencyEvidenceCandidate, ...],
    base_eligible: frozenset[str],
) -> str:
    eligible = [item for item in candidates if item.event_key in base_eligible]
    if policy_id == "SP-NON-SCORED-REFLECTION":
        return "policy_defines_no_score_update"
    if policy_id == "SP-CORROBORATION-REQUIRED":
        provenance = {kind for item in eligible for kind in item.provenance_kinds}
        if len(eligible) < 2 or len(provenance) < 2 or provenance == {"firsthand_self_report"}:
            return "corroboration_policy_not_satisfied"
    if policy_id == "SP-ARTIFACT-OBJECTIVE-PREFERRED" and not any(
        {"artifact", "objective"} & set(item.measurement_kinds)
        and {"reviewed_artifact", "objective_indicator"} & set(item.provenance_kinds)
        for item in eligible
    ):
        return "artifact_or_objective_policy_not_satisfied"
    if policy_id == "SP-QUALIFIED-EVIDENCE-REQUIRED" and not any(
        item.qualified_attestation_valid for item in eligible
    ):
        return "qualified_evidence_policy_not_satisfied"
    return ""


def project_competency_evidence(
    *,
    candidates: Iterable[CompetencyEvidenceCandidate],
    assessment_epoch_id: str,
    competency_id: str,
    as_of_date: str,
    policy_id: str | None = None,
    reversed_event_keys: Iterable[str] = (),
) -> CompetencyEvidenceShadow:
    for label, value in (
        ("assessment epoch", assessment_epoch_id),
        ("competency stable ID", competency_id),
    ):
        if not isinstance(value, str) or not STABLE_TOKEN.fullmatch(value):
            raise CompetencyScoringContractError(
                f"Competency projection {label} must be a stable non-narrative token."
            )
    try:
        resolved = tuple(candidates)
    except TypeError as exc:
        raise CompetencyScoringContractError(
            "Competency evidence candidates must be an iterable of candidate contracts."
        ) from exc
    for candidate in resolved:
        _validate_candidate(candidate)
    event_keys = [item.event_key for item in resolved]
    origin_keys = [item.origin_key for item in resolved]
    if len(event_keys) != len(set(event_keys)):
        raise CompetencyScoringContractError("Duplicate competency evidence event key.")
    if len(origin_keys) != len(set(origin_keys)):
        raise CompetencyScoringContractError(
            "Duplicate competency evidence origin would double count one observation."
        )
    if resolved and {item.assessment_epoch_id for item in resolved} != {assessment_epoch_id}:
        raise CompetencyScoringContractError("Competency evidence cannot cross assessment epochs.")
    if resolved and {item.competency_id for item in resolved} != {competency_id}:
        raise CompetencyScoringContractError(
            "A competency projection cannot mix competency stable IDs."
        )
    policies = {item.policy_id for item in resolved}
    if len(policies) > 1:
        raise CompetencyScoringContractError("A competency projection cannot mix scoring policies.")
    if policy_id is None:
        if not policies:
            raise CompetencyScoringContractError(
                "An empty competency projection requires an explicit scoring policy."
            )
        resolved_policy_id = next(iter(policies))
    else:
        if not isinstance(policy_id, str) or policy_id not in SUPPORTED_POLICY_IDS:
            raise CompetencyScoringContractError("Scoring policy is unsupported.")
        if policies and policies != {policy_id}:
            raise CompetencyScoringContractError(
                "Explicit scoring policy does not match the candidates."
            )
        resolved_policy_id = policy_id
    try:
        as_of = date.fromisoformat(as_of_date)
    except (TypeError, ValueError) as exc:
        raise CompetencyScoringContractError("as_of_date must be an ISO date.") from exc

    try:
        reversed_keys = frozenset(reversed_event_keys)
    except TypeError as exc:
        raise CompetencyScoringContractError(
            "Reversed event keys must be an iterable of stable tokens."
        ) from exc
    if any(not isinstance(item, str) or not STABLE_TOKEN.fullmatch(item) for item in reversed_keys):
        raise CompetencyScoringContractError(
            "Reversed event keys must be an iterable of stable tokens."
        )
    unknown_reversals = reversed_keys - set(event_keys)
    if unknown_reversals:
        raise CompetencyScoringContractError("A reversal references unknown competency evidence.")

    base_reasons: dict[str, tuple[str, ...]] = {}
    for candidate in resolved:
        observed = date.fromisoformat(candidate.observed_on)
        if observed > as_of:
            raise CompetencyScoringContractError(
                f"{candidate.event_key}: observed date is after the projection as-of date."
            )
        reasons: list[str] = []
        if candidate.event_key in reversed_keys:
            reasons.append("reversed_by_explicit_event_key")
        if candidate.adverse:
            reasons.append("adverse_outcome_withheld_for_review")
        reasons.extend(
            f"typed_protocol_evidence_withheld:{reason}"
            for reason in sorted(candidate.upstream_withholding_reasons)
        )
        if candidate.direction in {"inconclusive", "unknown"}:
            reasons.append(f"direction_{candidate.direction}")
        if candidate.transfer_disposition == "protocol_only":
            reasons.append("protocol_performance_is_not_competency_evidence")
        if candidate.max_age_days is not None and (as_of - observed).days > candidate.max_age_days:
            reasons.append("stale_at_explicit_as_of_date")
        if reasons:
            base_reasons[candidate.event_key] = tuple(dict.fromkeys(reasons))
    base_eligible = frozenset(set(event_keys) - set(base_reasons))
    policy_failure = _policy_failure(resolved_policy_id, resolved, base_eligible)
    policy_reasons: dict[str, str] = {}
    for candidate in resolved:
        if candidate.event_key in base_reasons:
            continue
        if policy_failure:
            policy_reasons[candidate.event_key] = policy_failure
        elif (
            resolved_policy_id == "SP-QUALIFIED-EVIDENCE-REQUIRED"
            and not candidate.qualified_attestation_valid
        ):
            policy_reasons[candidate.event_key] = "candidate_is_not_qualified_evidence"

    eligible_contexts = {
        item.context_key
        for item in resolved
        if item.event_key not in base_reasons and item.event_key not in policy_reasons
    }
    if len(eligible_contexts) < 2:
        for candidate in resolved:
            if (
                candidate.event_key not in base_reasons
                and candidate.event_key not in policy_reasons
                and candidate.transfer_disposition == "cross_context_supported"
            ):
                base_reasons[candidate.event_key] = ("cross_context_transfer_not_demonstrated",)

    contributions: list[CompetencyEvidenceContribution] = []
    for candidate in sorted(resolved, key=lambda item: item.event_key):
        reasons = base_reasons.get(candidate.event_key, ())
        if not reasons and candidate.event_key in policy_reasons:
            reasons = (policy_reasons[candidate.event_key],)
        reason = reasons[0] if reasons else ""
        included = not reason
        transfer_disposition = candidate.transfer_disposition
        if (
            included
            and transfer_disposition == "cross_context_candidate"
            and len(eligible_contexts) >= 2
        ):
            transfer_disposition = "cross_context_supported"
        evidence_mass = _quantize(candidate.base_evidence_mass) if included else Decimal("0.000000")
        if included:
            if candidate.competency_performance is None:
                raise CompetencyScoringContractError(
                    f"{candidate.event_key}: included evidence requires performance."
                )
            multiplier = DIRECTION_MULTIPLIERS[candidate.direction]
            success = _quantize(evidence_mass * candidate.competency_performance * multiplier)
            failure = _quantize(evidence_mass - success)
        else:
            success = Decimal("0.000000")
            failure = Decimal("0.000000")
        contributions.append(
            CompetencyEvidenceContribution(
                event_key=candidate.event_key,
                origin_key=candidate.origin_key,
                action_stable_id=candidate.action_stable_id,
                included=included,
                withholding_reason=reason,
                withholding_reasons=reasons,
                direction=candidate.direction,
                adverse=candidate.adverse,
                transfer_disposition=transfer_disposition,
                provenance_kinds=tuple(sorted(candidate.provenance_kinds)),
                measurement_kinds=tuple(sorted(candidate.measurement_kinds)),
                competency_performance=(
                    _quantize(candidate.competency_performance, FOUR_PLACES)
                    if candidate.competency_performance is not None
                    else None
                ),
                evidence_mass=evidence_mass,
                success_mass=success,
                failure_mass=failure,
            )
        )

    evidence_mass = _quantize(sum((item.evidence_mass for item in contributions), Decimal("0")))
    success_mass = _quantize(sum((item.success_mass for item in contributions), Decimal("0")))
    failure_mass = _quantize(sum((item.failure_mass for item in contributions), Decimal("0")))
    included_count = sum(item.included for item in contributions)
    return CompetencyEvidenceShadow(
        algorithm_version=COMPETENCY_EVIDENCE_SHADOW_VERSION,
        assessment_epoch_id=assessment_epoch_id,
        competency_id=competency_id,
        policy_id=resolved_policy_id,
        as_of_date=as_of.isoformat(),
        evidence_state=("evidence_observed" if included_count else "unknown"),
        competency_estimate=None,
        event_count=len(contributions),
        included_event_count=included_count,
        withheld_event_count=len(contributions) - included_count,
        reversed_event_count=len(reversed_keys),
        evidence_mass=evidence_mass,
        success_mass=success_mass,
        failure_mass=failure_mass,
        contributions=tuple(contributions),
    )


def competency_lever_mapping_fingerprint(
    *,
    competency_id: str,
    weights: Iterable[LeverWeight],
) -> str:
    if not isinstance(competency_id, str) or not STABLE_TOKEN.fullmatch(competency_id):
        raise CompetencyScoringContractError("Canonical mapping requires a stable competency ID.")
    try:
        resolved = tuple(weights)
    except TypeError as exc:
        raise CompetencyScoringContractError(
            "Canonical mapping weights must be an iterable of lever-weight contracts."
        ) from exc
    if not resolved:
        raise CompetencyScoringContractError("Canonical mapping cannot be empty.")
    lever_ids: list[str] = []
    for item in resolved:
        if not isinstance(item, LeverWeight):
            raise CompetencyScoringContractError(
                "Canonical mapping entries must use the lever-weight contract."
            )
        if not isinstance(item.lever_id, str) or not STABLE_TOKEN.fullmatch(item.lever_id):
            raise CompetencyScoringContractError("Canonical mapping requires stable lever IDs.")
        lever_ids.append(item.lever_id)
        for value in (item.weight, item.total_competency_weight):
            if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                raise CompetencyScoringContractError(
                    "Canonical mapping weights must be positive finite Decimals."
                )
    if len(lever_ids) != len(set(lever_ids)):
        raise CompetencyScoringContractError("Canonical mapping contains duplicate lever IDs.")
    payload = {
        "schema_version": COMPETENCY_LEVER_MAPPING_VERSION,
        "competency_id": competency_id,
        "weights": [
            {
                "lever_id": item.lever_id,
                "weight": format(item.weight.normalize(), "f"),
                "total_competency_weight": format(
                    item.total_competency_weight.normalize(),
                    "f",
                ),
            }
            for item in sorted(resolved, key=lambda item: item.lever_id)
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def project_competency_to_levers(
    *,
    competency_projection: CompetencyEvidenceShadow,
    baselines: Mapping[str, BaselineMass],
    weights: Iterable[LeverWeight],
    baseline_assessment_epoch_id: str,
    canonical_lever_ids: Iterable[str],
    canonical_mapping_fingerprint: str,
    minimum_transfer_disposition: str = "cross_context_supported",
) -> CompetencyLeverShadow:
    if not isinstance(competency_projection, CompetencyEvidenceShadow):
        raise CompetencyScoringContractError(
            "Competency lever projection requires the accepted competency projection contract."
        )
    if competency_projection.algorithm_version != COMPETENCY_EVIDENCE_SHADOW_VERSION:
        raise CompetencyScoringContractError(
            "Competency evidence projection version is unsupported."
        )
    if (
        not isinstance(minimum_transfer_disposition, str)
        or minimum_transfer_disposition not in TRANSFER_RANK
    ):
        raise CompetencyScoringContractError("Minimum transfer disposition is unsupported.")
    if not isinstance(baseline_assessment_epoch_id, str) or not STABLE_TOKEN.fullmatch(
        baseline_assessment_epoch_id
    ):
        raise CompetencyScoringContractError("Baseline assessment epoch must be a stable token.")
    if baseline_assessment_epoch_id != competency_projection.assessment_epoch_id:
        raise CompetencyScoringContractError(
            "Lever baselines and competency evidence must use the same assessment epoch."
        )
    if not isinstance(baselines, Mapping):
        raise CompetencyScoringContractError("Lever baselines must be a mapping.")
    try:
        expected_lever_ids = tuple(canonical_lever_ids)
        resolved_weights = tuple(weights)
    except TypeError as exc:
        raise CompetencyScoringContractError(
            "Canonical lever IDs and weights must be iterable."
        ) from exc
    if not expected_lever_ids or any(
        not isinstance(item, str) or not STABLE_TOKEN.fullmatch(item) for item in expected_lever_ids
    ):
        raise CompetencyScoringContractError(
            "Canonical lever IDs must be a non-empty unique sequence."
        )
    if len(expected_lever_ids) != len(set(expected_lever_ids)):
        raise CompetencyScoringContractError(
            "Canonical lever IDs must be a non-empty unique sequence."
        )
    if any(not isinstance(item, LeverWeight) for item in resolved_weights):
        raise CompetencyScoringContractError(
            "Canonical mapping entries must use the lever-weight contract."
        )
    weight_lever_ids = {item.lever_id for item in resolved_weights}
    if set(expected_lever_ids) != set(baselines) or set(expected_lever_ids) != weight_lever_ids:
        raise CompetencyScoringContractError(
            "Projection inputs must cover the complete canonical competency mapping."
        )
    if not isinstance(canonical_mapping_fingerprint, str) or not SHA256_HEX.fullmatch(
        canonical_mapping_fingerprint
    ):
        raise CompetencyScoringContractError(
            "Canonical mapping fingerprint must be a SHA-256 hex digest."
        )
    calculated_fingerprint = competency_lever_mapping_fingerprint(
        competency_id=competency_projection.competency_id,
        weights=resolved_weights,
    )
    if canonical_mapping_fingerprint != calculated_fingerprint:
        raise CompetencyScoringContractError(
            "Canonical mapping fingerprint does not match the supplied mapping."
        )
    minimum_rank = TRANSFER_RANK[minimum_transfer_disposition]
    scoring_events = tuple(
        ScoringEvidence(
            event_key=item.event_key,
            action_stable_id=item.action_stable_id,
            performance=item.competency_performance,
            base_evidence_mass=item.evidence_mass,
            direction=item.direction,
        )
        for item in competency_projection.contributions
        if item.included and TRANSFER_RANK[item.transfer_disposition] >= minimum_rank
    )
    try:
        projection = project_scores(
            baselines=baselines,
            weights=resolved_weights,
            events=scoring_events,
        )
    except ScoringContractError as exc:
        raise CompetencyScoringContractError(str(exc)) from exc
    return CompetencyLeverShadow(
        algorithm_version=COMPETENCY_LEVER_SHADOW_VERSION,
        competency_evidence_version=COMPETENCY_EVIDENCE_SHADOW_VERSION,
        assessment_epoch_id=competency_projection.assessment_epoch_id,
        competency_id=competency_projection.competency_id,
        as_of_date=competency_projection.as_of_date,
        baseline_assessment_epoch_id=baseline_assessment_epoch_id,
        canonical_mapping_fingerprint=canonical_mapping_fingerprint,
        minimum_transfer_disposition=minimum_transfer_disposition,
        allocated_event_keys=tuple(item.event_key for item in scoring_events),
        projection=projection,
    )
