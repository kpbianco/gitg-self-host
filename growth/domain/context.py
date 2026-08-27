from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

CONTEXT_CONTRACT_VERSION = "GG-CONTEXT-1.0"
CONTEXT_READINESS_CONTRACT_VERSION = "GG-CONTEXT-READINESS-1.0"
LEVEL_MIN = 0
LEVEL_MAX = 4
REVIEW_HORIZON_DAYS_MIN = 1
REVIEW_HORIZON_DAYS_MAX = 366


class ContextContractError(ValueError):
    pass


class ContextScope(StrEnum):
    ASSESSMENT = "assessment"
    PRACTICE = "practice"


class ContextValueState(StrEnum):
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    DEFERRED = "deferred"
    PROVIDED = "provided"


class PracticeDisposition(StrEnum):
    CONSIDERING = "considering"
    DEFERRED = "deferred"


class DeferReason(StrEnum):
    CAPACITY = "capacity"
    RESOURCES = "resources"
    TIMING = "timing"
    SAFETY_OR_ACCESS = "safety_or_access"
    ROLE_OR_FIT = "role_or_fit"
    COMPETING_PRIORITY = "competing_priority"
    NEEDS_SUPPORT = "needs_support"
    USER_CHOICE = "user_choice"


class SeasonCode(StrEnum):
    FOUNDATION = "foundation"
    EXPANSION = "expansion"
    MAINTENANCE = "maintenance"
    TRANSITION = "transition"
    RECOVERY = "recovery"
    CAREGIVING = "caregiving"
    CONSTRAINT = "constraint"
    OTHER = "other"


@dataclass(frozen=True)
class FactorDefinition:
    stable_id: str
    scope: ContextScope
    value_kind: str
    definition: str
    minimum: int | None = None
    maximum: int | None = None
    allowed_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextFactorValue:
    state: ContextValueState | str
    value: int | str | None = None


@dataclass(frozen=True)
class CanonicalContextSnapshot:
    payload: dict[str, Any]
    content_hash: str


_DEFINITIONS = (
    FactorDefinition(
        "season",
        ContextScope.ASSESSMENT,
        "category",
        "The broad kind of season the person says they are in; it describes context, "
        "not worth or performance.",
        allowed_values=tuple(item.value for item in SeasonCode),
    ),
    FactorDefinition(
        "capacity",
        ContextScope.ASSESSMENT,
        "ordinal",
        "Self-reported room for an additional bounded practice right now, without "
        "judging effort, character, or potential.",
        LEVEL_MIN,
        LEVEL_MAX,
    ),
    FactorDefinition(
        "applicability",
        ContextScope.PRACTICE,
        "ordinal",
        "How closely this candidate fits the person's present role and situation; "
        "not applicable creates no deficit.",
        LEVEL_MIN,
        LEVEL_MAX,
    ),
    FactorDefinition(
        "importance",
        ContextScope.PRACTICE,
        "ordinal",
        "How important the person currently considers this candidate among competing "
        "goods; it is not a measure of moral worth.",
        LEVEL_MIN,
        LEVEL_MAX,
    ),
    FactorDefinition(
        "readiness",
        ContextScope.PRACTICE,
        "ordinal",
        "How ready the person feels to attempt this bounded practice now; low readiness "
        "is context, not failure.",
        LEVEL_MIN,
        LEVEL_MAX,
    ),
    FactorDefinition(
        "urgency",
        ContextScope.PRACTICE,
        "ordinal",
        "How time-sensitive the person considers this candidate, without implying "
        "crisis, obligation, or greater worth.",
        LEVEL_MIN,
        LEVEL_MAX,
    ),
    FactorDefinition(
        "opportunity_resources",
        ContextScope.PRACTICE,
        "ordinal",
        "The currently available opportunity, support, access, and material resources "
        "for attempting the practice.",
        LEVEL_MIN,
        LEVEL_MAX,
    ),
    FactorDefinition(
        "burden",
        ContextScope.PRACTICE,
        "ordinal",
        "The effort, time, access, emotional, relational, or material load the person "
        "expects from the practice.",
        LEVEL_MIN,
        LEVEL_MAX,
    ),
)

FACTOR_DEFINITIONS: Mapping[str, FactorDefinition] = MappingProxyType(
    {item.stable_id: item for item in _DEFINITIONS}
)
ASSESSMENT_FACTOR_IDS = tuple(
    item.stable_id for item in _DEFINITIONS if item.scope is ContextScope.ASSESSMENT
)
PRACTICE_FACTOR_IDS = tuple(
    item.stable_id for item in _DEFINITIONS if item.scope is ContextScope.PRACTICE
)


def _enum_value(enum_type, value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise ContextContractError(f"{label} must be a string.")
    try:
        return enum_type(value).value
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ContextContractError(f"{label} must be one of: {allowed}.") from exc


def _validate_stable_id(value: object, *, label: str, maximum: int = 100) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ContextContractError(
            f"{label} must be a non-empty string of at most {maximum} characters."
        )
    return value


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _normalize_factor(
    factor_id: str,
    raw: ContextFactorValue | Mapping[str, Any],
) -> dict[str, Any]:
    definition = FACTOR_DEFINITIONS[factor_id]
    if isinstance(raw, ContextFactorValue):
        state_value = raw.state
        value = raw.value
    elif isinstance(raw, Mapping) and set(raw) == {"state", "value"}:
        state_value = raw["state"]
        value = raw["value"]
    else:
        raise ContextContractError(f"{factor_id} must contain exactly state and value.")

    state = _enum_value(ContextValueState, state_value, label=f"{factor_id} state")
    if state != ContextValueState.PROVIDED.value:
        if value is not None:
            raise ContextContractError(f"{factor_id} value must be null when state is {state}.")
        return {"state": state, "value": None}

    if definition.value_kind == "ordinal":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ContextContractError(f"{factor_id} value must be an integer.")
        if value < LEVEL_MIN or value > LEVEL_MAX:
            raise ContextContractError(
                f"{factor_id} value must be between {LEVEL_MIN} and {LEVEL_MAX}."
            )
    elif definition.value_kind == "category":
        if not isinstance(value, str) or value not in definition.allowed_values:
            allowed = ", ".join(definition.allowed_values)
            raise ContextContractError(f"{factor_id} value must be one of: {allowed}.")
    else:
        raise ContextContractError(f"{factor_id} has an unsupported value contract.")
    return {"state": state, "value": value}


def _normalize_factors(
    scope: ContextScope,
    factors: Mapping[str, ContextFactorValue | Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    if not isinstance(factors, Mapping):
        raise ContextContractError("Context factors must be a mapping.")
    expected = ASSESSMENT_FACTOR_IDS if scope is ContextScope.ASSESSMENT else PRACTICE_FACTOR_IDS
    actual = set(factors)
    if actual != set(expected):
        missing = sorted(set(expected) - actual)
        extra = sorted(actual - set(expected))
        details = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if extra:
            details.append(f"unexpected {', '.join(extra)}")
        raise ContextContractError("Context factor set is invalid: " + "; ".join(details) + ".")
    return {factor_id: _normalize_factor(factor_id, factors[factor_id]) for factor_id in expected}


def build_assessment_context_snapshot(
    *,
    assessment_epoch_id: str,
    factors: Mapping[str, ContextFactorValue | Mapping[str, Any]],
    contract_version: str = CONTEXT_CONTRACT_VERSION,
) -> CanonicalContextSnapshot:
    if contract_version != CONTEXT_CONTRACT_VERSION:
        raise ContextContractError(f"Unsupported context contract version: {contract_version!r}.")
    epoch_id = _validate_stable_id(assessment_epoch_id, label="assessment epoch ID", maximum=80)
    payload = {
        "assessment_epoch_id": epoch_id,
        "contract_version": contract_version,
        "factors": _normalize_factors(ContextScope.ASSESSMENT, factors),
        "scope": ContextScope.ASSESSMENT.value,
    }
    return CanonicalContextSnapshot(payload=payload, content_hash=canonical_hash(payload))


def build_practice_context_snapshot(
    *,
    assessment_epoch_id: str,
    protocol_stable_id: str,
    factors: Mapping[str, ContextFactorValue | Mapping[str, Any]],
    disposition: PracticeDisposition | str = PracticeDisposition.CONSIDERING,
    defer_reason: DeferReason | str | None = None,
    review_horizon_days: int | None = None,
    contract_version: str = CONTEXT_CONTRACT_VERSION,
) -> CanonicalContextSnapshot:
    if contract_version != CONTEXT_CONTRACT_VERSION:
        raise ContextContractError(f"Unsupported context contract version: {contract_version!r}.")
    epoch_id = _validate_stable_id(assessment_epoch_id, label="assessment epoch ID", maximum=80)
    protocol_id = _validate_stable_id(protocol_stable_id, label="protocol stable ID", maximum=120)
    normalized_factors = _normalize_factors(ContextScope.PRACTICE, factors)
    disposition_value = _enum_value(PracticeDisposition, disposition, label="practice disposition")
    any_factor_deferred = any(
        item["state"] == ContextValueState.DEFERRED.value for item in normalized_factors.values()
    )

    if disposition_value == PracticeDisposition.DEFERRED.value:
        if defer_reason is None:
            raise ContextContractError("A deferred practice requires a defer reason.")
        reason_value = _enum_value(DeferReason, defer_reason, label="defer reason")
        if not any_factor_deferred:
            raise ContextContractError(
                "A deferred practice requires at least one factor in the deferred state."
            )
        if review_horizon_days is not None:
            if isinstance(review_horizon_days, bool) or not isinstance(review_horizon_days, int):
                raise ContextContractError("Review horizon must be an integer number of days.")
            if not REVIEW_HORIZON_DAYS_MIN <= review_horizon_days <= REVIEW_HORIZON_DAYS_MAX:
                raise ContextContractError(
                    "Review horizon must be between "
                    f"{REVIEW_HORIZON_DAYS_MIN} and {REVIEW_HORIZON_DAYS_MAX} days."
                )
    else:
        if any_factor_deferred:
            raise ContextContractError(
                "A deferred factor requires the practice disposition to be deferred."
            )
        if defer_reason is not None or review_horizon_days is not None:
            raise ContextContractError(
                "Defer reason and review horizon are allowed only for a deferred practice."
            )
        reason_value = None

    payload = {
        "assessment_epoch_id": epoch_id,
        "contract_version": contract_version,
        "defer": {
            "reason": reason_value,
            "review_horizon_days": review_horizon_days,
        },
        "disposition": disposition_value,
        "factors": normalized_factors,
        "protocol_stable_id": protocol_id,
        "scope": ContextScope.PRACTICE.value,
    }
    return CanonicalContextSnapshot(payload=payload, content_hash=canonical_hash(payload))
