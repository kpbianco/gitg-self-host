from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext
from enum import StrEnum
from typing import Any

from growth.domain.context import (
    CONTEXT_CONTRACT_VERSION,
    ContextValueState,
    PracticeDisposition,
    SeasonCode,
)
from growth.domain.ranking import RANKING_ALGORITHM_VERSION

CONTEXT_PRIORITY_ALGORITHM_VERSION = "GG-CONTEXT-PRIORITY-1.0"
CONTEXT_PRIORITY_READINESS_CONTRACT_VERSION = "GG-CONTEXT-PRIORITY-READINESS-1.0"
CONTEXT_PRIORITY_SCOPE = "context_priority"
FOUR_PLACES = Decimal("0.0001")
ORDINAL_DIVISOR = Decimal("4")
MAX_CONTEXT_PRIORITY_CANDIDATES = 383
MAX_CONTEXT_PRIORITY_JSON_BYTES = 524288
PRACTICE_PRIORITY_FACTOR_IDS = (
    "applicability",
    "importance",
    "readiness",
    "urgency",
    "opportunity_resources",
    "burden",
)
MULTIPLIER_FACTOR_IDS = (
    "applicability",
    "importance",
    "readiness",
    "urgency",
    "opportunity_resources",
    "capacity",
    "burden",
)
EXPLANATION_CODES = frozenset(
    {
        "context_complete",
        "explicit_zero_factor",
        "applicability_not_applicable",
        "candidate_deferred",
        "required_factor_deferred",
        "required_factor_missing",
        "capacity_missing",
        "alternative_after_not_applicable",
        "alternative_after_deferred",
        "no_eligible_alternative",
    }
)


class ContextPriorityContractError(ValueError):
    pass


class CandidatePriorityDisposition(StrEnum):
    ELIGIBLE = "eligible"
    NOT_APPLICABLE = "not_applicable"
    DEFERRED = "deferred"
    MISSING_CONTEXT = "missing_context"


class RankingDisposition(StrEnum):
    RANKED = "ranked"
    MISSING_CONTEXT = "missing_context"


class AlternativeReason(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    DEFERRED = "deferred"


class AlternativeStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    SELECTED = "selected"
    NO_ELIGIBLE_ALTERNATIVE = "no_eligible_alternative"


@dataclass(frozen=True)
class PriorityFactorValue:
    state: ContextValueState | str
    value: int | str | None = None


@dataclass(frozen=True)
class ContextPriorityCandidateInput:
    protocol_stable_id: str
    base_priority: Decimal
    practice_context_hash: str
    factors: Mapping[str, PriorityFactorValue | Mapping[str, Any]]
    disposition: PracticeDisposition | str
    context_contract_version: str = CONTEXT_CONTRACT_VERSION


@dataclass(frozen=True)
class AlternativeRequest:
    source_protocol_stable_id: str
    reason: AlternativeReason | str


@dataclass(frozen=True)
class FactorContribution:
    factor_id: str
    state: str
    value: int | None
    normalized_multiplier: Decimal | None
    inverted: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "factor_id": self.factor_id,
            "inverted": self.inverted,
            "normalized_multiplier": _decimal_string(self.normalized_multiplier),
            "state": self.state,
            "value": self.value,
        }


@dataclass(frozen=True)
class CandidatePriority:
    protocol_stable_id: str
    base_priority: Decimal
    context_priority: Decimal | None
    disposition: CandidatePriorityDisposition
    explanation_codes: tuple[str, ...]
    factor_contributions: tuple[FactorContribution, ...]
    practice_context_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "base_priority": _decimal_string(self.base_priority),
            "context_priority": _decimal_string(self.context_priority),
            "disposition": self.disposition.value,
            "explanation_codes": list(self.explanation_codes),
            "factor_contributions": [item.as_dict() for item in self.factor_contributions],
            "practice_context_hash": self.practice_context_hash,
            "protocol_stable_id": self.protocol_stable_id,
        }


@dataclass(frozen=True)
class AlternativeResult:
    status: AlternativeStatus
    source_protocol_stable_id: str | None
    source_disposition: str | None
    reason: str | None
    target_protocol_stable_id: str | None
    explanation_codes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "explanation_codes": list(self.explanation_codes),
            "reason": self.reason,
            "source_disposition": self.source_disposition,
            "source_protocol_stable_id": self.source_protocol_stable_id,
            "status": self.status.value,
            "target_protocol_stable_id": self.target_protocol_stable_id,
        }


@dataclass(frozen=True)
class ContextPriorityResult:
    assessment_epoch_id: str
    assessment_context_hash: str
    season_state: str
    season_value: str | None
    capacity: FactorContribution
    ranking_disposition: RankingDisposition
    candidates: tuple[CandidatePriority, ...]
    ranked_candidate_ids: tuple[str, ...]
    primary_protocol_stable_id: str | None
    alternative: AlternativeResult
    canonical_json: str
    content_hash: str

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "algorithm_version": CONTEXT_PRIORITY_ALGORITHM_VERSION,
            "assessment_context_hash": self.assessment_context_hash,
            "assessment_epoch_id": self.assessment_epoch_id,
            "alternative": self.alternative.as_dict(),
            "candidates": [item.as_dict() for item in self.candidates],
            "dependencies": {
                "context_contract_version": CONTEXT_CONTRACT_VERSION,
                "need_ranking_algorithm_version": RANKING_ALGORITHM_VERSION,
            },
            "primary_protocol_stable_id": self.primary_protocol_stable_id,
            "ranked_candidate_ids": list(self.ranked_candidate_ids),
            "ranking_context": {
                "capacity": self.capacity.as_dict(),
                "season": {"state": self.season_state, "value": self.season_value},
            },
            "ranking_disposition": self.ranking_disposition.value,
            "scope": CONTEXT_PRIORITY_SCOPE,
            "supplied_candidate_ids": [item.protocol_stable_id for item in self.candidates],
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.canonical_payload(),
            "canonical_json": self.canonical_json,
            "sha256": self.content_hash,
        }


def _stable_id(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 120:
        raise ContextPriorityContractError(
            f"{label} must be a non-empty string of at most 120 characters."
        )
    return value


def _context_hash(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ContextPriorityContractError(f"{label} must be a lowercase SHA-256 value.")
    return value


def _unit_decimal(value: object, *, label: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0 or value > 1:
        raise ContextPriorityContractError(f"{label} must be a finite Decimal from 0 to 1.")
    return value


def _enum_value(enum_type, value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise ContextPriorityContractError(f"{label} must be a string.")
    try:
        return enum_type(value).value
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ContextPriorityContractError(f"{label} must be one of: {allowed}.") from exc


def _factor_parts(
    factor_id: str,
    raw: PriorityFactorValue | Mapping[str, Any],
) -> tuple[str, int | str | None]:
    if isinstance(raw, PriorityFactorValue):
        state, value = raw.state, raw.value
    elif isinstance(raw, Mapping) and set(raw) == {"state", "value"}:
        state, value = raw["state"], raw["value"]
    else:
        raise ContextPriorityContractError(f"{factor_id} must contain exactly state and value.")
    state_value = _enum_value(ContextValueState, state, label=f"{factor_id} state")
    if state_value != ContextValueState.PROVIDED.value:
        if value is not None:
            raise ContextPriorityContractError(
                f"{factor_id} value must be null when state is {state_value}."
            )
        return state_value, None
    if factor_id == "season":
        if not isinstance(value, str) or value not in {item.value for item in SeasonCode}:
            raise ContextPriorityContractError("season value is not a supported category.")
        return state_value, value
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 4:
        raise ContextPriorityContractError(f"{factor_id} value must be an integer from 0 to 4.")
    return state_value, value


def _factor_contribution(
    factor_id: str,
    raw: PriorityFactorValue | Mapping[str, Any],
) -> FactorContribution:
    state, value = _factor_parts(factor_id, raw)
    normalized = None
    inverted = factor_id == "burden"
    if state == ContextValueState.PROVIDED.value:
        normalized = Decimal(value) / ORDINAL_DIVISOR
        if inverted:
            normalized = Decimal("1") - normalized
    return FactorContribution(
        factor_id=factor_id,
        state=state,
        value=value if isinstance(value, int) else None,
        normalized_multiplier=normalized,
        inverted=inverted,
    )


def _validate_explanation_codes(codes: Sequence[str]) -> tuple[str, ...]:
    resolved = tuple(codes)
    if any(code not in EXPLANATION_CODES for code in resolved):
        raise ContextPriorityContractError("Context-priority explanation code is unsupported.")
    return resolved


def _candidate_disposition(
    *,
    disposition: str,
    factors: Mapping[str, FactorContribution],
    capacity: FactorContribution,
) -> tuple[CandidatePriorityDisposition, tuple[str, ...]]:
    # Applicability N/A remains distinct even when another factor is deferred.
    if factors["applicability"].state == ContextValueState.NOT_APPLICABLE.value:
        return (
            CandidatePriorityDisposition.NOT_APPLICABLE,
            ("applicability_not_applicable",),
        )
    if disposition == PracticeDisposition.DEFERRED.value or any(
        item.state == ContextValueState.DEFERRED.value for item in factors.values()
    ):
        codes = ["candidate_deferred"]
        if any(item.state == ContextValueState.DEFERRED.value for item in factors.values()):
            codes.append("required_factor_deferred")
        return CandidatePriorityDisposition.DEFERRED, tuple(codes)
    if capacity.state != ContextValueState.PROVIDED.value:
        return CandidatePriorityDisposition.MISSING_CONTEXT, ("capacity_missing",)
    if any(item.state != ContextValueState.PROVIDED.value for item in factors.values()):
        return CandidatePriorityDisposition.MISSING_CONTEXT, ("required_factor_missing",)
    return CandidatePriorityDisposition.ELIGIBLE, ("context_complete",)


def _build_candidate(
    raw: ContextPriorityCandidateInput,
    *,
    capacity: FactorContribution,
) -> CandidatePriority:
    protocol_id = _stable_id(raw.protocol_stable_id, label="protocol stable ID")
    base_priority = _unit_decimal(raw.base_priority, label=f"{protocol_id} base priority")
    context_hash = _context_hash(
        raw.practice_context_hash,
        label=f"{protocol_id} practice context hash",
    )
    if raw.context_contract_version != CONTEXT_CONTRACT_VERSION:
        raise ContextPriorityContractError("Candidate context contract version is unsupported.")
    if not isinstance(raw.factors, Mapping) or set(raw.factors) != set(
        PRACTICE_PRIORITY_FACTOR_IDS
    ):
        raise ContextPriorityContractError(
            f"{protocol_id} must supply exactly the six required practice factors."
        )
    disposition = _enum_value(
        PracticeDisposition,
        raw.disposition,
        label=f"{protocol_id} practice disposition",
    )
    contributions = tuple(
        _factor_contribution(factor_id, raw.factors[factor_id])
        for factor_id in PRACTICE_PRIORITY_FACTOR_IDS
    )
    by_id = {item.factor_id: item for item in contributions}
    resolved_disposition, codes = _candidate_disposition(
        disposition=disposition,
        factors=by_id,
        capacity=capacity,
    )
    context_priority = None
    if resolved_disposition is CandidatePriorityDisposition.ELIGIBLE:
        multipliers = (
            by_id["applicability"].normalized_multiplier,
            by_id["importance"].normalized_multiplier,
            by_id["readiness"].normalized_multiplier,
            by_id["urgency"].normalized_multiplier,
            by_id["opportunity_resources"].normalized_multiplier,
            capacity.normalized_multiplier,
            by_id["burden"].normalized_multiplier,
        )
        with localcontext() as context:
            context.prec = 28
            product = base_priority
            for multiplier in multipliers:
                if multiplier is None:
                    raise ContextPriorityContractError(
                        "Eligible context-priority candidate has a missing multiplier."
                    )
                product *= multiplier
            context_priority = product.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
        if any(multiplier == 0 for multiplier in multipliers):
            codes = (*codes, "explicit_zero_factor")
    return CandidatePriority(
        protocol_stable_id=protocol_id,
        base_priority=base_priority,
        context_priority=context_priority,
        disposition=resolved_disposition,
        explanation_codes=_validate_explanation_codes(codes),
        factor_contributions=contributions,
        practice_context_hash=context_hash,
    )


def _alternative(
    request: AlternativeRequest | None,
    *,
    candidates: Mapping[str, CandidatePriority],
    ranked: Sequence[CandidatePriority],
) -> AlternativeResult:
    if request is None:
        return AlternativeResult(
            status=AlternativeStatus.NOT_REQUESTED,
            source_protocol_stable_id=None,
            source_disposition=None,
            reason=None,
            target_protocol_stable_id=None,
            explanation_codes=(),
        )
    source_id = _stable_id(
        request.source_protocol_stable_id,
        label="alternative source protocol stable ID",
    )
    reason = _enum_value(AlternativeReason, request.reason, label="alternative reason")
    if source_id not in candidates:
        raise ContextPriorityContractError("Alternative source must be a supplied candidate.")
    source = candidates[source_id]
    if source.disposition.value != reason:
        raise ContextPriorityContractError(
            "Alternative reason must match the source candidate disposition."
        )
    target = next((item for item in ranked if item.protocol_stable_id != source_id), None)
    reason_code = (
        "alternative_after_not_applicable"
        if reason == AlternativeReason.NOT_APPLICABLE.value
        else "alternative_after_deferred"
    )
    if target is None:
        codes = _validate_explanation_codes((reason_code, "no_eligible_alternative"))
        status = AlternativeStatus.NO_ELIGIBLE_ALTERNATIVE
    else:
        codes = _validate_explanation_codes((reason_code,))
        status = AlternativeStatus.SELECTED
    return AlternativeResult(
        status=status,
        source_protocol_stable_id=source_id,
        source_disposition=source.disposition.value,
        reason=reason,
        target_protocol_stable_id=target.protocol_stable_id if target is not None else None,
        explanation_codes=codes,
    )


def _decimal_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP), "f")


def _canonical_json(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    try:
        payload_bytes = encoded.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ContextPriorityContractError("Context-priority result must be valid UTF-8.") from exc
    if len(payload_bytes) > MAX_CONTEXT_PRIORITY_JSON_BYTES:
        raise ContextPriorityContractError(
            f"Context-priority result exceeds {MAX_CONTEXT_PRIORITY_JSON_BYTES} bytes."
        )
    return encoded


def build_context_priority_result(
    *,
    assessment_epoch_id: str,
    assessment_context_hash: str,
    assessment_factors: Mapping[str, PriorityFactorValue | Mapping[str, Any]],
    candidates: Sequence[ContextPriorityCandidateInput],
    alternative_request: AlternativeRequest | None = None,
    context_contract_version: str = CONTEXT_CONTRACT_VERSION,
    algorithm_version: str = CONTEXT_PRIORITY_ALGORITHM_VERSION,
    need_ranking_algorithm_version: str = RANKING_ALGORITHM_VERSION,
) -> ContextPriorityResult:
    """Rank explicitly complete context without imputation, text analysis, or mutation."""

    if algorithm_version != CONTEXT_PRIORITY_ALGORITHM_VERSION:
        raise ContextPriorityContractError("Context-priority algorithm version is unsupported.")
    if context_contract_version != CONTEXT_CONTRACT_VERSION:
        raise ContextPriorityContractError("Assessment context contract version is unsupported.")
    if need_ranking_algorithm_version != RANKING_ALGORITHM_VERSION:
        raise ContextPriorityContractError("Need-ranking dependency version is unsupported.")
    epoch_id = _stable_id(assessment_epoch_id, label="assessment epoch ID")
    context_hash = _context_hash(assessment_context_hash, label="assessment context hash")
    if not isinstance(assessment_factors, Mapping) or set(assessment_factors) != {
        "season",
        "capacity",
    }:
        raise ContextPriorityContractError(
            "Assessment context must supply exactly season and capacity."
        )
    season_state, season_value = _factor_parts("season", assessment_factors["season"])
    capacity = _factor_contribution("capacity", assessment_factors["capacity"])
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise ContextPriorityContractError("Context-priority candidates must be a sequence.")
    if not candidates:
        raise ContextPriorityContractError("Context-priority requires at least one candidate.")
    if len(candidates) > MAX_CONTEXT_PRIORITY_CANDIDATES:
        raise ContextPriorityContractError(
            f"Context-priority supports at most {MAX_CONTEXT_PRIORITY_CANDIDATES} candidates."
        )
    if any(not isinstance(item, ContextPriorityCandidateInput) for item in candidates):
        raise ContextPriorityContractError(
            "Every context-priority candidate must use the versioned candidate input."
        )
    candidate_ids = [
        _stable_id(item.protocol_stable_id, label="protocol stable ID") for item in candidates
    ]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ContextPriorityContractError("Context-priority candidate stable IDs must be unique.")
    built = tuple(_build_candidate(item, capacity=capacity) for item in candidates)
    ordered_candidates = tuple(sorted(built, key=lambda item: item.protocol_stable_id))
    by_id = {item.protocol_stable_id: item for item in ordered_candidates}
    ranked = tuple(
        sorted(
            (
                item
                for item in ordered_candidates
                if item.disposition is CandidatePriorityDisposition.ELIGIBLE
            ),
            key=lambda item: (
                -(item.context_priority or Decimal("0")),
                -item.base_priority,
                item.protocol_stable_id,
            ),
        )
    )
    ranking_disposition = (
        RankingDisposition.RANKED
        if capacity.state == ContextValueState.PROVIDED.value
        else RankingDisposition.MISSING_CONTEXT
    )
    alternative = _alternative(
        alternative_request,
        candidates=by_id,
        ranked=ranked,
    )
    provisional = ContextPriorityResult(
        assessment_epoch_id=epoch_id,
        assessment_context_hash=context_hash,
        season_state=season_state,
        season_value=season_value if isinstance(season_value, str) else None,
        capacity=capacity,
        ranking_disposition=ranking_disposition,
        candidates=ordered_candidates,
        ranked_candidate_ids=tuple(item.protocol_stable_id for item in ranked),
        primary_protocol_stable_id=(ranked[0].protocol_stable_id if ranked else None),
        alternative=alternative,
        canonical_json="",
        content_hash="",
    )
    canonical_json = _canonical_json(provisional.canonical_payload())
    content_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return ContextPriorityResult(
        **{
            **provisional.__dict__,
            "canonical_json": canonical_json,
            "content_hash": content_hash,
        }
    )
