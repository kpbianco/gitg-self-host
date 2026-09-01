from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

ALGORITHM_VERSION = "GG-COMPOSITE-CLOSEOUT-SCORING-1.0"
STATE_SCHEMA_VERSION = "composite-closeout-state-v1"
TWELVE_PLACES = Decimal("0.000000000001")
FOUR_PLACES = Decimal("0.0001")
WEIGHT_TOLERANCE = Decimal("0.000001")


class CompositeScoringError(ValueError):
    pass


@dataclass(frozen=True)
class CompositeScoringPolicy:
    algorithm_version: str
    state_schema_version: str
    expected_families: int
    expected_levers: int
    expected_domains: int
    expected_competencies: int
    expected_practices: int
    expected_actions: int
    canonical_relationship_weight: Decimal
    equal_relationship_weight: Decimal
    competency_lever_weight: Decimal
    competency_family_weight: Decimal
    competency_domain_weight: Decimal
    priority_lever_weight: Decimal
    priority_family_weight: Decimal
    priority_domain_weight: Decimal
    inherited_lever_confidence_multiplier: Decimal
    need_exponent: Decimal
    confidence_floor: Decimal
    confidence_weight: Decimal
    minimum_closeout_credit: Decimal
    full_closeout_credit: Decimal
    remaining_need_exponent: Decimal
    own_remaining_credit_exponent: Decimal


@dataclass(frozen=True)
class LeverAssessmentInput:
    lever_id: str
    family_id: str
    estimate: Decimal | None
    confidence: Decimal


@dataclass(frozen=True)
class CompetencyProjectionInput:
    competency_id: str
    domain_id: str
    canonical_weights: Mapping[str, Decimal]


def _decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:  # pragma: no cover - Decimal raises several input errors
        raise CompositeScoringError(f"{label} must be a decimal value.") from exc
    if not result.is_finite():
        raise CompositeScoringError(f"{label} must be finite.")
    return result


def _unit(value: Decimal, label: str) -> None:
    if not value.is_finite() or value < 0 or value > 1:
        raise CompositeScoringError(f"{label} must be in the closed unit interval.")


def _positive(value: Decimal, label: str) -> None:
    if not value.is_finite() or value <= 0:
        raise CompositeScoringError(f"{label} must be positive.")


def _require_sum(values: Sequence[Decimal], label: str) -> None:
    total = sum(values, Decimal("0"))
    if abs(total - Decimal("1")) > WEIGHT_TOLERANCE:
        raise CompositeScoringError(f"{label} sum to {total}; expected 1.0.")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(TWELVE_PLACES, rounding=ROUND_HALF_UP)


def _decimal_string(value: Decimal | None) -> str | None:
    return None if value is None else format(_quantize(value), "f")


def _allocation_strings(values: Mapping[str, Decimal]) -> dict[str, str]:
    """Serialize an exact allocation while preserving an exact displayed unit sum."""

    ordered = sorted(values.items())
    serialized = {key: _quantize(value) for key, value in ordered}
    remainder = Decimal("1") - sum(serialized.values(), Decimal("0"))
    if remainder:
        adjustment_key = max(ordered, key=lambda item: (item[1], item[0]))[0]
        serialized[adjustment_key] += remainder
    if any(value <= 0 for value in serialized.values()):
        raise CompositeScoringError("Serialized relationship weights must remain positive.")
    _require_sum(tuple(serialized.values()), "Serialized relationship weights")
    return {key: format(value, "f") for key, value in sorted(serialized.items())}


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def policy_from_contract(contract: Mapping[str, Any]) -> CompositeScoringPolicy:
    if contract.get("schema_version") != ALGORITHM_VERSION:
        raise CompositeScoringError("Composite scoring contract version is unsupported.")
    catalog = contract.get("catalog") or {}
    relationship = contract.get("relationship_blend") or {}
    assessment = contract.get("assessment_projection") or {}
    completion = contract.get("completion_credit") or {}
    coverage = contract.get("coverage") or {}
    priority = contract.get("recommendation_priority") or {}
    policy = CompositeScoringPolicy(
        algorithm_version=str(contract.get("algorithm_version", "")),
        state_schema_version=str(contract.get("state_schema_version", "")),
        expected_families=int(catalog.get("families", 0)),
        expected_levers=int(catalog.get("levers", 0)),
        expected_domains=int(catalog.get("domains", 0)),
        expected_competencies=int(catalog.get("competencies", 0)),
        expected_practices=int(catalog.get("practices", 0)),
        expected_actions=int(catalog.get("actions", 0)),
        canonical_relationship_weight=_decimal(
            relationship.get("canonical_weight"), "Canonical relationship weight"
        ),
        equal_relationship_weight=_decimal(
            relationship.get("equal_share_weight"), "Equal relationship weight"
        ),
        competency_lever_weight=_decimal(
            assessment.get("mapped_lever_weight"), "Competency lever weight"
        ),
        competency_family_weight=_decimal(
            assessment.get("mapped_family_weight"), "Competency family weight"
        ),
        competency_domain_weight=_decimal(
            assessment.get("parent_domain_weight"), "Competency domain weight"
        ),
        priority_lever_weight=_decimal(
            priority.get("mapped_lever_weight"), "Priority lever weight"
        ),
        priority_family_weight=_decimal(
            priority.get("mapped_family_weight"), "Priority family weight"
        ),
        priority_domain_weight=_decimal(
            priority.get("parent_domain_weight"), "Priority domain weight"
        ),
        inherited_lever_confidence_multiplier=_decimal(
            assessment.get("unassessed_lever_confidence_multiplier"),
            "Inherited lever confidence multiplier",
        ),
        need_exponent=_decimal(assessment.get("need_exponent"), "Need exponent"),
        confidence_floor=_decimal(assessment.get("confidence_floor"), "Confidence floor"),
        confidence_weight=_decimal(assessment.get("confidence_weight"), "Confidence weight"),
        minimum_closeout_credit=_decimal(
            completion.get("minimum_closeout_credit"), "Minimum closeout credit"
        ),
        full_closeout_credit=_decimal(
            completion.get("full_closeout_credit"), "Full closeout credit"
        ),
        remaining_need_exponent=_decimal(
            coverage.get("remaining_need_exponent"), "Remaining-need exponent"
        ),
        own_remaining_credit_exponent=_decimal(
            priority.get("own_remaining_credit_exponent"),
            "Own remaining-credit exponent",
        ),
    )
    if (
        policy.algorithm_version != ALGORITHM_VERSION
        or policy.state_schema_version != STATE_SCHEMA_VERSION
    ):
        raise CompositeScoringError("Composite scoring algorithm metadata is unsupported.")
    for label, count in (
        ("families", policy.expected_families),
        ("levers", policy.expected_levers),
        ("domains", policy.expected_domains),
        ("competencies", policy.expected_competencies),
        ("practices", policy.expected_practices),
        ("actions", policy.expected_actions),
    ):
        if count <= 0:
            raise CompositeScoringError(f"Expected {label} must be positive.")
    relationship_weights = (
        policy.canonical_relationship_weight,
        policy.equal_relationship_weight,
    )
    component_weights = (
        policy.competency_lever_weight,
        policy.competency_family_weight,
        policy.competency_domain_weight,
    )
    priority_weights = (
        policy.priority_lever_weight,
        policy.priority_family_weight,
        policy.priority_domain_weight,
    )
    for label, values in (
        ("Relationship blend weights", relationship_weights),
        ("Competency component weights", component_weights),
        ("Priority component weights", priority_weights),
    ):
        for value in values:
            _unit(value, label)
        _require_sum(values, label)
    _unit(
        policy.inherited_lever_confidence_multiplier,
        "Inherited lever confidence multiplier",
    )
    _unit(policy.confidence_floor, "Confidence floor")
    _unit(policy.confidence_weight, "Confidence weight")
    _require_sum(
        (policy.confidence_floor, policy.confidence_weight),
        "Confidence factor weights",
    )
    _unit(policy.minimum_closeout_credit, "Minimum closeout credit")
    _unit(policy.full_closeout_credit, "Full closeout credit")
    if policy.minimum_closeout_credit > policy.full_closeout_credit:
        raise CompositeScoringError("Minimum closeout credit exceeds full credit.")
    for label, exponent in (
        ("Need exponent", policy.need_exponent),
        ("Remaining-need exponent", policy.remaining_need_exponent),
        ("Own remaining-credit exponent", policy.own_remaining_credit_exponent),
    ):
        _positive(exponent, label)
    return policy


def blended_relationship_weights(
    canonical_weights: Mapping[str, Decimal],
    policy: CompositeScoringPolicy,
) -> dict[str, Decimal]:
    if not canonical_weights:
        raise CompositeScoringError("A competency requires at least one lever relationship.")
    normalized: dict[str, Decimal] = {}
    for lever_id, raw_weight in canonical_weights.items():
        if not lever_id:
            raise CompositeScoringError("A relationship requires a stable lever ID.")
        weight = _decimal(raw_weight, f"{lever_id} canonical relationship weight")
        _positive(weight, f"{lever_id} canonical relationship weight")
        normalized[lever_id] = weight
    _require_sum(tuple(normalized.values()), "Canonical relationship weights")
    equal = Decimal("1") / Decimal(len(normalized))
    blended = {
        lever_id: (
            policy.canonical_relationship_weight * weight + policy.equal_relationship_weight * equal
        )
        for lever_id, weight in normalized.items()
    }
    total = sum(blended.values(), Decimal("0"))
    return {lever_id: value / total for lever_id, value in blended.items()}


def closeout_credit(
    *,
    completed_actions: int,
    total_actions: int,
    minimum_completed: int,
    policy: CompositeScoringPolicy,
) -> Decimal:
    if total_actions <= 0:
        raise CompositeScoringError("A closeout requires at least one action.")
    if minimum_completed <= 0 or minimum_completed > total_actions:
        raise CompositeScoringError("Closeout minimum must be between one and total actions.")
    if completed_actions < minimum_completed or completed_actions > total_actions:
        raise CompositeScoringError(
            "Completed actions must satisfy the closeout minimum without exceeding total actions."
        )
    if completed_actions == total_actions or minimum_completed == total_actions:
        return policy.full_closeout_credit
    progress = Decimal(completed_actions - minimum_completed) / Decimal(
        total_actions - minimum_completed
    )
    return (
        policy.minimum_closeout_credit
        + (policy.full_closeout_credit - policy.minimum_closeout_credit) * progress
    ).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def _power(value: Decimal, exponent: Decimal) -> Decimal:
    _unit(value, "Power base")
    if exponent == Decimal("0.5"):
        return value.sqrt()
    if exponent == Decimal("1.5"):
        return value * value.sqrt()
    with localcontext() as context:
        context.prec = 28
        return context.power(value, exponent)


def starting_need(
    estimate: Decimal | None,
    confidence: Decimal,
    policy: CompositeScoringPolicy,
) -> Decimal | None:
    _unit(confidence, "Assessment confidence")
    if estimate is None:
        return None
    _unit(estimate, "Assessment estimate")
    gap = Decimal("1") - estimate
    factor = policy.confidence_floor + policy.confidence_weight * confidence
    return _quantize(_power(gap, policy.need_exponent) * factor)


def remaining_need(
    initial_need: Decimal | None,
    coverage: Decimal,
    policy: CompositeScoringPolicy,
) -> Decimal | None:
    _unit(coverage, "Completion coverage")
    if initial_need is None:
        return None
    _unit(initial_need, "Initial need")
    return _quantize(initial_need * _power(Decimal("1") - coverage, policy.remaining_need_exponent))


def _weighted_mean(
    values: Sequence[tuple[Decimal, Decimal]],
    label: str,
) -> Decimal:
    if not values:
        raise CompositeScoringError(f"{label} has no available values.")
    total = sum((weight for _value, weight in values), Decimal("0"))
    if total == 0:
        return sum((value for value, _weight in values), Decimal("0")) / Decimal(len(values))
    return sum((value * weight for value, weight in values), Decimal("0")) / total


def _mean(values: Sequence[Decimal], label: str) -> Decimal:
    if not values:
        raise CompositeScoringError(f"{label} has no values.")
    return sum(values, Decimal("0")) / Decimal(len(values))


def _assert_unique(values: Sequence[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise CompositeScoringError(f"{label} contain duplicate stable IDs.")


def build_assessment_projection(
    *,
    levers: Sequence[LeverAssessmentInput],
    competencies: Sequence[CompetencyProjectionInput],
    policy: CompositeScoringPolicy,
) -> dict[str, Any]:
    lever_ids = [item.lever_id for item in levers]
    competency_ids = [item.competency_id for item in competencies]
    _assert_unique(lever_ids, "Levers")
    _assert_unique(competency_ids, "Competencies")
    if len(levers) != policy.expected_levers:
        raise CompositeScoringError(
            f"Expected {policy.expected_levers} levers, found {len(levers)}."
        )
    if len(competencies) != policy.expected_competencies:
        raise CompositeScoringError(
            f"Expected {policy.expected_competencies} competencies, found {len(competencies)}."
        )

    lever_by_id = {item.lever_id: item for item in levers}
    family_members: dict[str, list[LeverAssessmentInput]] = defaultdict(list)
    for lever in levers:
        if not lever.lever_id or not lever.family_id:
            raise CompositeScoringError("Every lever requires stable lever and family IDs.")
        if lever.estimate is not None:
            _unit(lever.estimate, f"{lever.lever_id} estimate")
        _unit(lever.confidence, f"{lever.lever_id} confidence")
        family_members[lever.family_id].append(lever)
    if len(family_members) != policy.expected_families:
        raise CompositeScoringError(
            f"Expected {policy.expected_families} families, found {len(family_members)}."
        )

    families: dict[str, dict[str, Decimal]] = {}
    for family_id, members in sorted(family_members.items()):
        available = [item for item in members if item.estimate is not None]
        if not available:
            raise CompositeScoringError(f"{family_id} has no assessed lever estimate.")
        estimate = _weighted_mean(
            [(item.estimate, item.confidence) for item in available if item.estimate is not None],
            f"{family_id} family estimate",
        )
        confidence = _mean(
            [item.confidence for item in available], f"{family_id} family confidence"
        )
        families[family_id] = {
            "estimate": estimate,
            "confidence": confidence,
        }

    resolved_levers: dict[str, dict[str, Any]] = {}
    for lever in sorted(levers, key=lambda item: item.lever_id):
        family = families[lever.family_id]
        inherited = lever.estimate is None
        estimate = family["estimate"] if inherited else lever.estimate
        if estimate is None:  # guarded by family availability, retained for type narrowing
            raise CompositeScoringError(f"{lever.lever_id} estimate could not be resolved.")
        confidence = (
            family["confidence"] * policy.inherited_lever_confidence_multiplier
            if inherited
            else lever.confidence
        )
        resolved_levers[lever.lever_id] = {
            "family_id": lever.family_id,
            "estimate": estimate,
            "confidence": confidence,
            "source": "family_inherited" if inherited else "direct_assessment",
        }

    preliminary: dict[str, dict[str, Any]] = {}
    domain_members: dict[str, list[str]] = defaultdict(list)
    for competency in sorted(competencies, key=lambda item: item.competency_id):
        if not competency.competency_id or not competency.domain_id:
            raise CompositeScoringError(
                "Every competency requires stable competency and domain IDs."
            )
        weights = blended_relationship_weights(competency.canonical_weights, policy)
        unknown = sorted(set(weights) - set(lever_by_id))
        if unknown:
            raise CompositeScoringError(
                f"{competency.competency_id} maps unknown levers: {unknown}."
            )
        mapped_lever = sum(
            (weights[lever_id] * resolved_levers[lever_id]["estimate"] for lever_id in weights),
            Decimal("0"),
        )
        mapped_lever_confidence = sum(
            (weights[lever_id] * resolved_levers[lever_id]["confidence"] for lever_id in weights),
            Decimal("0"),
        )
        mapped_family = sum(
            (
                weights[lever_id] * families[resolved_levers[lever_id]["family_id"]]["estimate"]
                for lever_id in weights
            ),
            Decimal("0"),
        )
        mapped_family_confidence = sum(
            (
                weights[lever_id] * families[resolved_levers[lever_id]["family_id"]]["confidence"]
                for lever_id in weights
            ),
            Decimal("0"),
        )
        preliminary[competency.competency_id] = {
            "domain_id": competency.domain_id,
            "relationships": weights,
            "mapped_lever": mapped_lever,
            "mapped_lever_confidence": mapped_lever_confidence,
            "mapped_family": mapped_family,
            "mapped_family_confidence": mapped_family_confidence,
        }
        domain_members[competency.domain_id].append(competency.competency_id)
    if len(domain_members) != policy.expected_domains:
        raise CompositeScoringError(
            f"Expected {policy.expected_domains} domains, found {len(domain_members)}."
        )

    domains: dict[str, dict[str, Decimal]] = {}
    for domain_id, members in sorted(domain_members.items()):
        domains[domain_id] = {
            "estimate": _mean(
                [preliminary[item]["mapped_lever"] for item in members],
                f"{domain_id} estimate",
            ),
            "confidence": _mean(
                [preliminary[item]["mapped_lever_confidence"] for item in members],
                f"{domain_id} confidence",
            ),
        }

    competency_rows: dict[str, Any] = {}
    for competency_id, values in sorted(preliminary.items()):
        domain = domains[values["domain_id"]]
        estimate = (
            policy.competency_lever_weight * values["mapped_lever"]
            + policy.competency_family_weight * values["mapped_family"]
            + policy.competency_domain_weight * domain["estimate"]
        )
        confidence = (
            policy.competency_lever_weight * values["mapped_lever_confidence"]
            + policy.competency_family_weight * values["mapped_family_confidence"]
            + policy.competency_domain_weight * domain["confidence"]
        )
        competency_rows[competency_id] = {
            "domain_id": values["domain_id"],
            "relationships": _allocation_strings(values["relationships"]),
            "mapped_lever_estimate": _decimal_string(values["mapped_lever"]),
            "mapped_family_estimate": _decimal_string(values["mapped_family"]),
            "estimate": _decimal_string(estimate),
            "confidence": _decimal_string(confidence),
            "starting_need": _decimal_string(starting_need(estimate, confidence, policy)),
        }

    family_rows = {
        family_id: {
            "estimate": _decimal_string(values["estimate"]),
            "confidence": _decimal_string(values["confidence"]),
            "starting_need": _decimal_string(
                starting_need(values["estimate"], values["confidence"], policy)
            ),
            "lever_ids": sorted(item.lever_id for item in family_members[family_id]),
        }
        for family_id, values in sorted(families.items())
    }
    lever_rows = {
        lever_id: {
            "family_id": values["family_id"],
            "estimate": _decimal_string(values["estimate"]),
            "confidence": _decimal_string(values["confidence"]),
            "starting_need": _decimal_string(
                starting_need(values["estimate"], values["confidence"], policy)
            ),
            "source": values["source"],
        }
        for lever_id, values in sorted(resolved_levers.items())
    }
    domain_rows = {
        domain_id: {
            "estimate": _decimal_string(values["estimate"]),
            "confidence": _decimal_string(values["confidence"]),
            "starting_need": _decimal_string(
                starting_need(values["estimate"], values["confidence"], policy)
            ),
            "competency_ids": sorted(domain_members[domain_id]),
        }
        for domain_id, values in sorted(domains.items())
    }
    payload = {
        "algorithm_version": policy.algorithm_version,
        "state_schema_version": policy.state_schema_version,
        "counts": {
            "families": len(family_rows),
            "levers": len(lever_rows),
            "domains": len(domain_rows),
            "competencies": len(competency_rows),
        },
        "families": family_rows,
        "levers": lever_rows,
        "domains": domain_rows,
        "competencies": competency_rows,
    }
    payload["projection_hash"] = canonical_hash(payload)
    return payload


def _payload_decimal(value: Any, label: str) -> Decimal:
    if value is None:
        raise CompositeScoringError(f"{label} is unavailable.")
    return _decimal(value, label)


def build_completion_state(
    *,
    assessment_projection: Mapping[str, Any],
    competency_credits: Mapping[str, Decimal],
    policy: CompositeScoringPolicy,
) -> dict[str, Any]:
    if assessment_projection.get("algorithm_version") != policy.algorithm_version:
        raise CompositeScoringError("Assessment projection algorithm version is unsupported.")
    projection_competencies = assessment_projection.get("competencies") or {}
    projection_levers = assessment_projection.get("levers") or {}
    projection_families = assessment_projection.get("families") or {}
    projection_domains = assessment_projection.get("domains") or {}
    expected_ids = set(projection_competencies)
    unknown = sorted(set(competency_credits) - expected_ids)
    if unknown:
        raise CompositeScoringError(f"Completion credit has unknown competencies: {unknown}.")
    credits = {competency_id: Decimal("0") for competency_id in expected_ids}
    for competency_id, raw_credit in competency_credits.items():
        credit = _decimal(raw_credit, f"{competency_id} completion credit")
        _unit(credit, f"{competency_id} completion credit")
        credits[competency_id] = credit

    lever_numerator = {lever_id: Decimal("0") for lever_id in projection_levers}
    lever_denominator = {lever_id: Decimal("0") for lever_id in projection_levers}
    family_numerator = {family_id: Decimal("0") for family_id in projection_families}
    family_denominator = {family_id: Decimal("0") for family_id in projection_families}
    domain_members: dict[str, list[Decimal]] = defaultdict(list)
    for competency_id, row in projection_competencies.items():
        credit = credits[competency_id]
        domain_members[row["domain_id"]].append(credit)
        for lever_id, raw_weight in row["relationships"].items():
            weight = _payload_decimal(raw_weight, f"{competency_id}/{lever_id} relationship")
            family_id = projection_levers[lever_id]["family_id"]
            lever_numerator[lever_id] += weight * credit
            lever_denominator[lever_id] += weight
            family_numerator[family_id] += weight * credit
            family_denominator[family_id] += weight

    lever_rows: dict[str, Any] = {}
    for lever_id, projection in sorted(projection_levers.items()):
        _positive(lever_denominator[lever_id], f"{lever_id} relationship denominator")
        coverage = lever_numerator[lever_id] / lever_denominator[lever_id]
        initial = _payload_decimal(projection["starting_need"], f"{lever_id} starting need")
        lever_rows[lever_id] = {
            "family_id": projection["family_id"],
            "assessment_estimate": projection["estimate"],
            "assessment_confidence": projection["confidence"],
            "assessment_source": projection["source"],
            "starting_need": projection["starting_need"],
            "coverage": _decimal_string(coverage),
            "remaining_need": _decimal_string(remaining_need(initial, coverage, policy)),
        }

    family_rows: dict[str, Any] = {}
    for family_id, projection in sorted(projection_families.items()):
        _positive(family_denominator[family_id], f"{family_id} relationship denominator")
        coverage = family_numerator[family_id] / family_denominator[family_id]
        initial = _payload_decimal(projection["starting_need"], f"{family_id} starting need")
        family_rows[family_id] = {
            "assessment_estimate": projection["estimate"],
            "assessment_confidence": projection["confidence"],
            "starting_need": projection["starting_need"],
            "coverage": _decimal_string(coverage),
            "remaining_need": _decimal_string(remaining_need(initial, coverage, policy)),
        }

    domain_rows: dict[str, Any] = {}
    for domain_id, projection in sorted(projection_domains.items()):
        coverage = _mean(domain_members[domain_id], f"{domain_id} completion coverage")
        initial = _payload_decimal(projection["starting_need"], f"{domain_id} starting need")
        domain_rows[domain_id] = {
            "assessment_estimate": projection["estimate"],
            "assessment_confidence": projection["confidence"],
            "starting_need": projection["starting_need"],
            "coverage": _decimal_string(coverage),
            "remaining_need": _decimal_string(remaining_need(initial, coverage, policy)),
        }

    competency_rows: dict[str, Any] = {}
    priorities: list[tuple[str, Decimal]] = []
    for competency_id, projection in sorted(projection_competencies.items()):
        relationships = {
            lever_id: _payload_decimal(weight, f"{competency_id}/{lever_id} relationship")
            for lever_id, weight in projection["relationships"].items()
        }
        lever_need = sum(
            (
                weight
                * _payload_decimal(
                    lever_rows[lever_id]["remaining_need"],
                    f"{lever_id} remaining need",
                )
                for lever_id, weight in relationships.items()
            ),
            Decimal("0"),
        )
        family_need = sum(
            (
                weight
                * _payload_decimal(
                    family_rows[projection_levers[lever_id]["family_id"]]["remaining_need"],
                    f"{projection_levers[lever_id]['family_id']} remaining need",
                )
                for lever_id, weight in relationships.items()
            ),
            Decimal("0"),
        )
        domain_need = _payload_decimal(
            domain_rows[projection["domain_id"]]["remaining_need"],
            f"{projection['domain_id']} remaining need",
        )
        shared_priority = (
            policy.priority_lever_weight * lever_need
            + policy.priority_family_weight * family_need
            + policy.priority_domain_weight * domain_need
        )
        own_factor = _power(
            Decimal("1") - credits[competency_id],
            policy.own_remaining_credit_exponent,
        )
        priority = _quantize(shared_priority * own_factor)
        priorities.append((competency_id, priority))
        competency_rows[competency_id] = {
            "domain_id": projection["domain_id"],
            "assessment_estimate": projection["estimate"],
            "assessment_confidence": projection["confidence"],
            "completion_credit": _decimal_string(credits[competency_id]),
            "remaining_priority": _decimal_string(priority),
        }
    priorities.sort(key=lambda item: (-item[1], item[0]))
    for rank, (competency_id, _priority) in enumerate(priorities, start=1):
        competency_rows[competency_id]["rank"] = rank

    canonical_coverage = _mean(list(credits.values()), "Canonical completion coverage")
    payload = {
        "algorithm_version": policy.algorithm_version,
        "state_schema_version": policy.state_schema_version,
        "assessment_projection_hash": assessment_projection.get("projection_hash"),
        "canonical_coverage": _decimal_string(canonical_coverage),
        "families": family_rows,
        "levers": lever_rows,
        "domains": domain_rows,
        "competencies": competency_rows,
    }
    payload["state_hash"] = canonical_hash(payload)
    return payload
