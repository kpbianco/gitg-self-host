from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

EVIDENCE_ALGORITHM_VERSION = "GG-EVIDENCE-1.0"

ALLOWED_OBSERVATION_FIELDS = frozenset(
    {
        "user_initiated",
        "moved_beyond_transactional",
        "follow_up_question_asked",
        "meaningful_information_shared",
        "future_interaction_scheduled",
        "follow_up_within_seven_days",
    }
)

INDEPENDENCE_FACTORS = {
    "independent": (Decimal("1.00"), "Self-directed"),
    "planning_aid": (Decimal("0.85"), "Reminder or planning aid"),
    "guided": (Decimal("0.60"), "Real-time prompting or guidance"),
    "": (Decimal("0.70"), "Not recorded in M1"),
}

CONTEXT_FACTORS = {
    "first_record": (Decimal("0.55"), "First record in one relationship"),
    "same_context": (Decimal("0.55"), "Similar setting in one relationship"),
    "varied_context": (Decimal("0.75"), "Varied setting in one relationship"),
    "": (Decimal("0.55"), "Not recorded in M1"),
}

DIRECTION_LEVELS = {
    "supports": (Decimal("0.00"), "Supported the expected pattern"),
    "mixed": (Decimal("0.50"), "Mixed or unclear"),
    "contradicts": (Decimal("1.00"), "Contradicted the expected pattern"),
    "inconclusive": (Decimal("0.00"), "Not enough happened to tell"),
}

REPETITION_MULTIPLIERS = (
    Decimal("1.00"),
    Decimal("0.65"),
    Decimal("0.40"),
    Decimal("0.25"),
)

FOUR_PLACES = Decimal("0.0001")


class EvidenceContractError(ValueError):
    pass


@dataclass(frozen=True)
class EvidenceInput:
    protocol_stable_id: str
    action_stable_id: str
    action_attempted: bool
    action_completed: bool
    observations: Mapping[str, bool]
    internal_resistance: int | None
    expected_reciprocity: int | None
    observed_reciprocity: int | None
    support_level: str
    context_comparison: str
    evidence_direction: str
    contradiction_text_present: bool
    repetition_index: int


@dataclass(frozen=True)
class EvidenceResult:
    algorithm_version: str
    performance: Decimal
    quality: Decimal
    independence: Decimal
    context_breadth: Decimal
    repetition_index: int
    repetition_multiplier: Decimal
    contradiction_level: Decimal | None
    base_evidence_mass: Decimal
    input_snapshot: dict[str, Any]
    explanation: dict[str, Any]


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def _validated_markers(rules: Mapping[str, Any], key: str) -> tuple[str, ...]:
    markers = rules.get(key)
    if not isinstance(markers, list) or not markers:
        raise EvidenceContractError(f"Evidence rules require a non-empty {key} list.")
    if any(not isinstance(marker, str) for marker in markers):
        raise EvidenceContractError(f"Every {key} entry must be a field name.")
    unknown = set(markers) - ALLOWED_OBSERVATION_FIELDS
    if unknown:
        raise EvidenceContractError(
            f"Evidence rules reference unknown observation fields: {sorted(unknown)}."
        )
    if len(markers) != len(set(markers)):
        raise EvidenceContractError(f"Evidence rules contain duplicate {key} entries.")
    return tuple(markers)


def validate_evidence_rules(rules: Mapping[str, Any]) -> None:
    if not isinstance(rules, Mapping):
        raise EvidenceContractError("Evidence rules must be an object.")
    if rules.get("schema_version") != "practice-observation-v1":
        raise EvidenceContractError(
            "Evidence rules require schema_version practice-observation-v1."
        )
    primary = _validated_markers(rules, "primary_markers")
    supporting = _validated_markers(rules, "supporting_markers")
    overlap = set(primary) & set(supporting)
    if overlap:
        raise EvidenceContractError(
            f"Primary and supporting evidence markers overlap: {sorted(overlap)}."
        )


def repetition_multiplier(repetition_index: int) -> Decimal:
    if repetition_index < 1:
        raise EvidenceContractError("Repetition index must be at least one.")
    position = min(repetition_index, len(REPETITION_MULTIPLIERS)) - 1
    return REPETITION_MULTIPLIERS[position]


def _coverage(markers: tuple[str, ...], observations: Mapping[str, bool]) -> Decimal:
    present = sum(bool(observations.get(marker, False)) for marker in markers)
    return Decimal(present) / Decimal(len(markers))


def _quality_label(quality: Decimal) -> str:
    if quality >= Decimal("0.75"):
        return "Well-specified structured self-report"
    if quality >= Decimal("0.60"):
        return "Structured self-report"
    return "Limited structured detail"


def _mass_label(mass: Decimal) -> str:
    if mass >= Decimal("0.55"):
        return "Substantial event evidence"
    if mass >= Decimal("0.35"):
        return "Moderate event evidence"
    if mass >= Decimal("0.20"):
        return "Limited event evidence"
    return "Very limited event evidence"


def evaluate_evidence(
    evidence: EvidenceInput,
    rules: Mapping[str, Any],
) -> EvidenceResult:
    validate_evidence_rules(rules)
    if evidence.action_completed and not evidence.action_attempted:
        raise EvidenceContractError("A completed action must also be attempted.")
    unknown_observations = set(evidence.observations) - ALLOWED_OBSERVATION_FIELDS
    if unknown_observations:
        raise EvidenceContractError(
            f"Evidence input contains unknown observations: {sorted(unknown_observations)}."
        )
    if evidence.support_level not in INDEPENDENCE_FACTORS:
        raise EvidenceContractError("Support level is not part of the evidence contract.")
    if evidence.context_comparison not in CONTEXT_FACTORS:
        raise EvidenceContractError("Context comparison is not part of the evidence contract.")

    primary = _validated_markers(rules, "primary_markers")
    supporting = _validated_markers(rules, "supporting_markers")
    primary_coverage = _coverage(primary, evidence.observations)
    supporting_coverage = _coverage(supporting, evidence.observations)

    performance = Decimal("0.00")
    if evidence.action_attempted:
        performance += Decimal("0.35")
    if evidence.action_completed:
        performance += Decimal("0.35")
    performance += Decimal("0.20") * primary_coverage
    performance += Decimal("0.10") * supporting_coverage
    performance = _quantize(min(performance, Decimal("1.00")))

    quality = Decimal("0.45")
    if evidence.action_attempted:
        quality += Decimal("0.10")
    if evidence.evidence_direction:
        quality += Decimal("0.10")
    if evidence.support_level:
        quality += Decimal("0.05")
    if evidence.context_comparison:
        quality += Decimal("0.05")
    if primary_coverage > 0 or supporting_coverage > 0 or evidence.contradiction_text_present:
        quality += Decimal("0.10")
    if evidence.expected_reciprocity is not None and evidence.observed_reciprocity is not None:
        quality += Decimal("0.05")
    quality = _quantize(min(quality, Decimal("0.85")))

    independence, independence_label = INDEPENDENCE_FACTORS[evidence.support_level]
    context_breadth, context_label = CONTEXT_FACTORS[evidence.context_comparison]
    repeat = repetition_multiplier(evidence.repetition_index)

    if evidence.evidence_direction:
        if evidence.evidence_direction not in DIRECTION_LEVELS:
            raise EvidenceContractError("Evidence direction is not part of the contract.")
        contradiction_level, direction_label = DIRECTION_LEVELS[evidence.evidence_direction]
    elif evidence.contradiction_text_present:
        contradiction_level = Decimal("0.50")
        direction_label = "Legacy contradiction text; direction not recorded"
    else:
        contradiction_level = None
        direction_label = "Direction not recorded in M1"

    base_mass = _quantize(quality * independence * context_breadth * repeat)
    observations = {
        field: bool(evidence.observations.get(field, False))
        for field in sorted(ALLOWED_OBSERVATION_FIELDS)
    }
    snapshot = {
        "protocol_stable_id": evidence.protocol_stable_id,
        "action_stable_id": evidence.action_stable_id,
        "action_attempted": evidence.action_attempted,
        "action_completed": evidence.action_completed,
        "observations": observations,
        "internal_resistance": evidence.internal_resistance,
        "expected_reciprocity": evidence.expected_reciprocity,
        "observed_reciprocity": evidence.observed_reciprocity,
        "support_level": evidence.support_level or None,
        "context_comparison": evidence.context_comparison or None,
        "evidence_direction": evidence.evidence_direction or None,
        "contradiction_text_present": evidence.contradiction_text_present,
        "repetition_index": evidence.repetition_index,
        "evidence_rules": {
            "schema_version": rules["schema_version"],
            "primary_markers": list(primary),
            "supporting_markers": list(supporting),
        },
    }
    explanation = {
        "quality": {
            "label": _quality_label(quality),
            "reason": (
                "Based on structured, firsthand fields and protocol-specific observable "
                "markers; free-text length is never rewarded."
            ),
        },
        "independence": {
            "label": independence_label,
            "reason": "Describes support used for this attempt, not personal worth.",
        },
        "context_breadth": {
            "label": context_label,
            "reason": (
                "This protocol concerns one relationship, so it cannot establish broad "
                "transfer across people."
            ),
        },
        "repetition": {
            "label": (
                "First record for this action"
                if evidence.repetition_index == 1
                else f"Record {evidence.repetition_index} for this action"
            ),
            "reason": "Repeated records add evidence with diminishing weight.",
        },
        "direction": {
            "label": direction_label,
            "reason": (
                "Contradiction is retained separately and does not silently become "
                "positive evidence."
            ),
        },
        "base_evidence": {
            "label": _mass_label(base_mass),
            "reason": (
                "Event-level evidence mass combines quality, independence, context, "
                "and repetition. It is not a mastery or score-impact calculation."
            ),
        },
    }
    return EvidenceResult(
        algorithm_version=EVIDENCE_ALGORITHM_VERSION,
        performance=performance,
        quality=quality,
        independence=_quantize(independence),
        context_breadth=_quantize(context_breadth),
        repetition_index=evidence.repetition_index,
        repetition_multiplier=_quantize(repeat),
        contradiction_level=(
            _quantize(contradiction_level) if contradiction_level is not None else None
        ),
        base_evidence_mass=base_mass,
        input_snapshot=snapshot,
        explanation=explanation,
    )


def replay_evidence(input_snapshot: Mapping[str, Any]) -> EvidenceResult:
    try:
        evidence = EvidenceInput(
            protocol_stable_id=input_snapshot["protocol_stable_id"],
            action_stable_id=input_snapshot["action_stable_id"],
            action_attempted=input_snapshot["action_attempted"],
            action_completed=input_snapshot["action_completed"],
            observations=input_snapshot["observations"],
            internal_resistance=input_snapshot["internal_resistance"],
            expected_reciprocity=input_snapshot["expected_reciprocity"],
            observed_reciprocity=input_snapshot["observed_reciprocity"],
            support_level=input_snapshot["support_level"] or "",
            context_comparison=input_snapshot["context_comparison"] or "",
            evidence_direction=input_snapshot["evidence_direction"] or "",
            contradiction_text_present=input_snapshot["contradiction_text_present"],
            repetition_index=input_snapshot["repetition_index"],
        )
        rules = input_snapshot["evidence_rules"]
    except (KeyError, TypeError) as exc:
        raise EvidenceContractError("Evidence snapshot is incomplete or malformed.") from exc
    return evaluate_evidence(evidence, rules)
