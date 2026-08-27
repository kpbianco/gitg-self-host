from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

SCORING_ALGORITHM_VERSION = "GG-SCORING-SHADOW-1.0"

ASSESSMENT_PRIOR_ALPHA = Decimal("0.35")
ASSESSMENT_PRIOR_BETA = Decimal("0.35")
ASSESSMENT_EVIDENCE_MASS_CAP = Decimal("3.2")
TASK_MASS_BUDGET_PER_LEVER = Decimal("24.0")
TASK_EVENT_MASS_CAP_PER_LEVER = Decimal("1.5")
CONFIDENCE_DENOMINATOR_OFFSET = Decimal("1.5")

DIRECTION_MULTIPLIERS = {
    "supports": Decimal("1.0"),
    "mixed": Decimal("0.5"),
    "contradicts": Decimal("0.0"),
}
UNSCORED_DIRECTIONS = frozenset({"", "inconclusive"})

FOUR_PLACES = Decimal("0.0001")
SIX_PLACES = Decimal("0.000001")
WEIGHT_TOLERANCE = Decimal("0.0001")


class ScoringContractError(ValueError):
    pass


@dataclass(frozen=True)
class BaselineMass:
    lever_id: str
    alpha: Decimal
    beta: Decimal
    confidence: Decimal


@dataclass(frozen=True)
class LeverWeight:
    lever_id: str
    weight: Decimal
    total_competency_weight: Decimal


@dataclass(frozen=True)
class ScoringEvidence:
    event_key: str
    action_stable_id: str
    performance: Decimal
    base_evidence_mass: Decimal
    direction: str


@dataclass(frozen=True)
class MappedScoringEvidence:
    evidence: ScoringEvidence
    weights: tuple[LeverWeight, ...]


@dataclass(frozen=True)
class LeverContribution:
    event_key: str
    action_stable_id: str
    lever_id: str
    direction: str
    included: bool
    exclusion_reason: str
    performance: Decimal
    direction_multiplier: Decimal | None
    effective_performance: Decimal | None
    task_coefficient: Decimal
    potential_evidence_mass: Decimal
    evidence_mass: Decimal
    success_mass: Decimal
    failure_mass: Decimal


@dataclass(frozen=True)
class ProjectedLever:
    lever_id: str
    baseline_alpha: Decimal
    baseline_beta: Decimal
    baseline_estimate: Decimal
    baseline_confidence: Decimal
    evidence_mass: Decimal
    success_mass: Decimal
    failure_mass: Decimal
    projected_alpha: Decimal
    projected_beta: Decimal
    projected_estimate: Decimal
    projected_confidence: Decimal
    contributions: tuple[LeverContribution, ...]


@dataclass(frozen=True)
class ScoreProjection:
    algorithm_version: str
    event_count: int
    scored_event_count: int
    withheld_event_count: int
    levers: tuple[ProjectedLever, ...]


def _quantize(value: Decimal, places: Decimal = SIX_PLACES) -> Decimal:
    return value.quantize(places, rounding=ROUND_HALF_UP)


def _clamp(value: Decimal, low: Decimal = Decimal("0"), high: Decimal = Decimal("1")):
    return min(high, max(low, value))


def _require_finite(value: Decimal, label: str) -> None:
    if not value.is_finite():
        raise ScoringContractError(f"{label} must be finite.")


def _estimate(alpha: Decimal, beta: Decimal) -> Decimal:
    total = alpha + beta
    if total <= 0:
        raise ScoringContractError("Baseline alpha and beta must have positive total mass.")
    return _quantize(alpha / total, FOUR_PLACES)


def _project_confidence(
    baseline_confidence: Decimal,
    evidence_mass: Decimal,
) -> Decimal:
    if evidence_mass == 0:
        return _quantize(baseline_confidence, FOUR_PLACES)
    gain_share = evidence_mass / (evidence_mass + CONFIDENCE_DENOMINATOR_OFFSET)
    value = baseline_confidence + (Decimal("1") - baseline_confidence) * gain_share
    return _quantize(_clamp(value), FOUR_PLACES)


def validate_baseline_mass(baseline: BaselineMass) -> None:
    if not baseline.lever_id:
        raise ScoringContractError("Baseline mass requires a stable lever ID.")
    _require_finite(baseline.alpha, f"{baseline.lever_id} baseline alpha")
    _require_finite(baseline.beta, f"{baseline.lever_id} baseline beta")
    _require_finite(baseline.confidence, f"{baseline.lever_id} baseline confidence")
    if baseline.alpha < 0 or baseline.beta < 0:
        raise ScoringContractError(f"{baseline.lever_id}: baseline mass cannot be negative.")
    if baseline.alpha + baseline.beta <= 0:
        raise ScoringContractError(f"{baseline.lever_id}: baseline mass must be positive.")
    if baseline.confidence < 0 or baseline.confidence > 1:
        raise ScoringContractError(f"{baseline.lever_id}: baseline confidence is outside 0 to 1.")


def reconstruct_published_baseline_mass(
    *,
    lever_id: str,
    raw_self_report: Decimal | None,
    calibrated_estimate: Decimal | None,
    evidence_confidence: Decimal,
) -> BaselineMass | None:
    """Recover assessment alpha/beta when rounded published values identify them.

    The assessment uses equal 0.35 priors and publishes raw and calibrated
    values to four decimals. A neutral raw/estimate pair does not identify the
    evidence mass and therefore fails closed.
    """

    if raw_self_report is None or calibrated_estimate is None:
        return None
    _require_finite(raw_self_report, f"{lever_id} raw self-report")
    _require_finite(calibrated_estimate, f"{lever_id} calibrated estimate")
    if not (Decimal("0") <= raw_self_report <= Decimal("1")):
        raise ScoringContractError(f"{lever_id}: raw self-report is outside 0 to 1.")
    if not (Decimal("0") <= calibrated_estimate <= Decimal("1")):
        raise ScoringContractError(f"{lever_id}: calibrated estimate is outside 0 to 1.")

    denominator = calibrated_estimate - raw_self_report
    if abs(denominator) <= Decimal("0.0000001"):
        return None
    prior_total = ASSESSMENT_PRIOR_ALPHA + ASSESSMENT_PRIOR_BETA
    evidence_mass = (ASSESSMENT_PRIOR_ALPHA - calibrated_estimate * prior_total) / denominator
    if evidence_mass < 0:
        raise ScoringContractError(
            f"{lever_id}: published values imply negative baseline evidence mass."
        )
    if evidence_mass > ASSESSMENT_EVIDENCE_MASS_CAP + Decimal("0.05"):
        raise ScoringContractError(
            f"{lever_id}: published values exceed the assessment evidence-mass cap."
        )

    alpha = _quantize(
        ASSESSMENT_PRIOR_ALPHA + evidence_mass * raw_self_report,
    )
    beta = _quantize(
        ASSESSMENT_PRIOR_BETA + evidence_mass * (Decimal("1") - raw_self_report),
    )
    reconstructed = BaselineMass(
        lever_id=lever_id,
        alpha=alpha,
        beta=beta,
        confidence=evidence_confidence,
    )
    validate_baseline_mass(reconstructed)
    if abs(_estimate(alpha, beta) - calibrated_estimate) > Decimal("0.0002"):
        raise ScoringContractError(
            f"{lever_id}: reconstructed baseline does not reproduce the published estimate."
        )
    return reconstructed


def _validated_weights(weights: Iterable[LeverWeight]) -> tuple[LeverWeight, ...]:
    resolved = tuple(weights)
    if not resolved:
        raise ScoringContractError("A scoring task requires at least one lever weight.")
    ids = [item.lever_id for item in resolved]
    if len(ids) != len(set(ids)):
        raise ScoringContractError("A scoring task contains duplicate stable lever IDs.")
    for item in resolved:
        if not item.lever_id:
            raise ScoringContractError("Every scoring weight requires a stable lever ID.")
        _require_finite(item.weight, f"{item.lever_id} task weight")
        _require_finite(
            item.total_competency_weight,
            f"{item.lever_id} total mapped competency weight",
        )
        if item.weight <= 0 or item.weight > 1:
            raise ScoringContractError(f"{item.lever_id}: task weight must be in (0, 1].")
        if item.total_competency_weight <= 0:
            raise ScoringContractError(
                f"{item.lever_id}: total mapped competency weight must be positive."
            )
    weight_sum = sum((item.weight for item in resolved), Decimal("0"))
    if abs(weight_sum - Decimal("1")) > WEIGHT_TOLERANCE:
        raise ScoringContractError(
            f"Task-to-lever weights sum to {weight_sum}; expected approximately 1.0."
        )
    return tuple(sorted(resolved, key=lambda item: item.lever_id))


def task_coefficient(weight: LeverWeight) -> Decimal:
    coefficient = TASK_MASS_BUDGET_PER_LEVER * weight.weight / weight.total_competency_weight
    return _quantize(min(TASK_EVENT_MASS_CAP_PER_LEVER, coefficient))


def _validate_event(event: ScoringEvidence) -> None:
    if not event.event_key:
        raise ScoringContractError("Scoring evidence requires an immutable event key.")
    if not event.action_stable_id:
        raise ScoringContractError("Scoring evidence requires a stable action ID.")
    _require_finite(event.performance, f"{event.event_key} performance")
    _require_finite(event.base_evidence_mass, f"{event.event_key} base evidence mass")
    if event.performance < 0 or event.performance > 1:
        raise ScoringContractError(f"{event.event_key}: performance is outside 0 to 1.")
    if event.base_evidence_mass < 0 or event.base_evidence_mass > 1:
        raise ScoringContractError(f"{event.event_key}: base evidence mass is outside 0 to 1.")
    if event.direction not in DIRECTION_MULTIPLIERS and event.direction not in UNSCORED_DIRECTIONS:
        raise ScoringContractError(
            f"{event.event_key}: evidence direction is not part of the scoring contract."
        )


def _contribution(event: ScoringEvidence, weight: LeverWeight) -> LeverContribution:
    coefficient = task_coefficient(weight)
    potential_mass = _quantize(event.base_evidence_mass * coefficient)
    if event.direction in UNSCORED_DIRECTIONS:
        reason = (
            "Direction was not recorded."
            if not event.direction
            else "Not enough happened to support a directional score."
        )
        return LeverContribution(
            event_key=event.event_key,
            action_stable_id=event.action_stable_id,
            lever_id=weight.lever_id,
            direction=event.direction,
            included=False,
            exclusion_reason=reason,
            performance=_quantize(event.performance, FOUR_PLACES),
            direction_multiplier=None,
            effective_performance=None,
            task_coefficient=coefficient,
            potential_evidence_mass=potential_mass,
            evidence_mass=Decimal("0.000000"),
            success_mass=Decimal("0.000000"),
            failure_mass=Decimal("0.000000"),
        )

    direction_multiplier = DIRECTION_MULTIPLIERS[event.direction]
    effective_performance = _quantize(
        event.performance * direction_multiplier,
    )
    success_mass = _quantize(potential_mass * effective_performance)
    failure_mass = _quantize(potential_mass - success_mass)
    return LeverContribution(
        event_key=event.event_key,
        action_stable_id=event.action_stable_id,
        lever_id=weight.lever_id,
        direction=event.direction,
        included=True,
        exclusion_reason="",
        performance=_quantize(event.performance, FOUR_PLACES),
        direction_multiplier=_quantize(direction_multiplier, FOUR_PLACES),
        effective_performance=effective_performance,
        task_coefficient=coefficient,
        potential_evidence_mass=potential_mass,
        evidence_mass=potential_mass,
        success_mass=success_mass,
        failure_mass=failure_mass,
    )


def project_scores(
    *,
    baselines: Mapping[str, BaselineMass],
    weights: Iterable[LeverWeight],
    events: Iterable[ScoringEvidence],
) -> ScoreProjection:
    resolved_weights = _validated_weights(weights)
    resolved_events = tuple(events)
    event_keys = [event.event_key for event in resolved_events]
    if len(event_keys) != len(set(event_keys)):
        raise ScoringContractError("A projection cannot include the same evidence event twice.")
    for event in resolved_events:
        _validate_event(event)

    projected: list[ProjectedLever] = []
    for weight in resolved_weights:
        try:
            baseline = baselines[weight.lever_id]
        except KeyError as exc:
            raise ScoringContractError(
                f"{weight.lever_id}: scoring baseline mass is unavailable."
            ) from exc
        validate_baseline_mass(baseline)
        if baseline.lever_id != weight.lever_id:
            raise ScoringContractError(
                f"{weight.lever_id}: baseline stable ID does not match its mapping."
            )

        contributions = tuple(_contribution(event, weight) for event in resolved_events)
        evidence_mass = _quantize(sum((item.evidence_mass for item in contributions), Decimal("0")))
        success_mass = _quantize(sum((item.success_mass for item in contributions), Decimal("0")))
        failure_mass = _quantize(sum((item.failure_mass for item in contributions), Decimal("0")))
        projected_alpha = _quantize(baseline.alpha + success_mass)
        projected_beta = _quantize(baseline.beta + failure_mass)
        projected.append(
            ProjectedLever(
                lever_id=weight.lever_id,
                baseline_alpha=_quantize(baseline.alpha),
                baseline_beta=_quantize(baseline.beta),
                baseline_estimate=_estimate(baseline.alpha, baseline.beta),
                baseline_confidence=_quantize(baseline.confidence, FOUR_PLACES),
                evidence_mass=evidence_mass,
                success_mass=success_mass,
                failure_mass=failure_mass,
                projected_alpha=projected_alpha,
                projected_beta=projected_beta,
                projected_estimate=_estimate(projected_alpha, projected_beta),
                projected_confidence=_project_confidence(
                    baseline.confidence,
                    evidence_mass,
                ),
                contributions=contributions,
            )
        )

    scored_events = sum(event.direction in DIRECTION_MULTIPLIERS for event in resolved_events)
    return ScoreProjection(
        algorithm_version=SCORING_ALGORITHM_VERSION,
        event_count=len(resolved_events),
        scored_event_count=scored_events,
        withheld_event_count=len(resolved_events) - scored_events,
        levers=tuple(projected),
    )


def project_mapped_scores(
    *,
    baselines: Mapping[str, BaselineMass],
    events: Iterable[MappedScoringEvidence],
) -> ScoreProjection:
    """Project events that each carry their own canonical competency mapping."""

    resolved_events = tuple(events)
    event_keys = [item.evidence.event_key for item in resolved_events]
    if len(event_keys) != len(set(event_keys)):
        raise ScoringContractError("A projection cannot include the same evidence event twice.")
    contributions_by_lever: dict[str, list[LeverContribution]] = {}
    for mapped in resolved_events:
        _validate_event(mapped.evidence)
        for weight in _validated_weights(mapped.weights):
            baseline = baselines.get(weight.lever_id)
            if baseline is None:
                raise ScoringContractError(
                    f"{weight.lever_id}: scoring baseline mass is unavailable."
                )
            validate_baseline_mass(baseline)
            if baseline.lever_id != weight.lever_id:
                raise ScoringContractError(
                    f"{weight.lever_id}: baseline stable ID does not match its mapping."
                )
            contributions_by_lever.setdefault(weight.lever_id, []).append(
                _contribution(mapped.evidence, weight)
            )

    projected: list[ProjectedLever] = []
    for lever_id in sorted(contributions_by_lever):
        baseline = baselines[lever_id]
        contributions = tuple(contributions_by_lever[lever_id])
        evidence_mass = _quantize(sum((item.evidence_mass for item in contributions), Decimal("0")))
        success_mass = _quantize(sum((item.success_mass for item in contributions), Decimal("0")))
        failure_mass = _quantize(sum((item.failure_mass for item in contributions), Decimal("0")))
        projected_alpha = _quantize(baseline.alpha + success_mass)
        projected_beta = _quantize(baseline.beta + failure_mass)
        projected.append(
            ProjectedLever(
                lever_id=lever_id,
                baseline_alpha=_quantize(baseline.alpha),
                baseline_beta=_quantize(baseline.beta),
                baseline_estimate=_estimate(baseline.alpha, baseline.beta),
                baseline_confidence=_quantize(baseline.confidence, FOUR_PLACES),
                evidence_mass=evidence_mass,
                success_mass=success_mass,
                failure_mass=failure_mass,
                projected_alpha=projected_alpha,
                projected_beta=projected_beta,
                projected_estimate=_estimate(projected_alpha, projected_beta),
                projected_confidence=_project_confidence(baseline.confidence, evidence_mass),
                contributions=contributions,
            )
        )

    scored_events = sum(
        item.evidence.direction in DIRECTION_MULTIPLIERS for item in resolved_events
    )
    return ScoreProjection(
        algorithm_version=SCORING_ALGORITHM_VERSION,
        event_count=len(resolved_events),
        scored_event_count=scored_events,
        withheld_event_count=len(resolved_events) - scored_events,
        levers=tuple(projected),
    )
