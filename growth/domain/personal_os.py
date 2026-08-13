from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

PERSONAL_OS_CONTRACT_VERSION = "GG-PERSONAL-OS-1.0"
PERSONAL_OS_READINESS_CONTRACT_VERSION = "GG-PERSONAL-OS-READINESS-1.0"
PERSONAL_OS_SCOPE = "personal_os"
SCALAR_VALUE_MAX_LENGTH = 500
LIST_ITEM_MIN_COUNT = 1
LIST_ITEM_MAX_COUNT = 5
LIST_ITEM_MAX_LENGTH = 160
MAX_CANONICAL_SNAPSHOT_BYTES = 65536


class PersonalOSContractError(ValueError):
    pass


class PersonalOSValueState(StrEnum):
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    DEFERRED = "deferred"
    PROVIDED = "provided"


class PersonalOSValueKind(StrEnum):
    SCALAR = "scalar"
    ORDERED_LIST = "ordered_list"


@dataclass(frozen=True)
class PersonalOSDefinition:
    stable_id: str
    value_kind: PersonalOSValueKind
    prompt: str
    help_text: str


@dataclass(frozen=True)
class PersonalOSValue:
    state: PersonalOSValueState | str
    value: str | Sequence[str] | None = None


@dataclass(frozen=True)
class CanonicalPersonalOSSnapshot:
    payload: dict[str, Any]
    canonical_json: str
    content_hash: str


_IDENTITY_DEFINITIONS = (
    PersonalOSDefinition(
        "mission",
        PersonalOSValueKind.SCALAR,
        "What purpose or contribution do you choose to orient toward for now?",
        "Use your own provisional words and only the private detail you want to store. "
        "This is a direction, not a fixed identity or destiny.",
    ),
    PersonalOSDefinition(
        "principles",
        PersonalOSValueKind.ORDERED_LIST,
        "Which one to five principles do you choose to guide decisions for now?",
        "Order them deliberately. They are user-authored guides, not a moral ranking or "
        "measure of character.",
    ),
    PersonalOSDefinition(
        "anti_goals",
        PersonalOSValueKind.ORDERED_LIST,
        "Which one to five outcomes or patterns do you deliberately not want to optimize for?",
        "Name only what is useful for your choices. Anti-goals do not diagnose or shame you "
        "or anyone else.",
    ),
    PersonalOSDefinition(
        "twelve_month_direction",
        PersonalOSValueKind.SCALAR,
        "What direction would you choose to make more real over the next twelve months?",
        "Keep it provisional and context-aware. It is not a prediction, promise, or measure "
        "of worth.",
    ),
    PersonalOSDefinition(
        "priority_stack",
        PersonalOSValueKind.ORDERED_LIST,
        "Which one to five priorities deserve attention first in your present season?",
        "Order competing goods without implying that deferred or unchosen goods have less "
        "human value.",
    ),
)

_AUDIT_DEFINITIONS = (
    PersonalOSDefinition(
        "current_truth",
        PersonalOSValueKind.SCALAR,
        "What feels most true about your current direction and situation?",
        "Describe only what you choose, with the minimum private detail needed. This is your "
        "account, not a diagnosis or judgment.",
    ),
    PersonalOSDefinition(
        "autopilot_pattern",
        PersonalOSValueKind.SCALAR,
        "Where, if anywhere, have habit, momentum, or outside expectations been choosing for you?",
        "Describe a pattern without assigning blame, shame, personality destiny, or a fixed "
        "identity.",
    ),
    PersonalOSDefinition(
        "misalignment_or_fragmentation",
        PersonalOSValueKind.SCALAR,
        "Where, if anywhere, do your actions or commitments feel out of step or fragmented?",
        "A reported mismatch is information for reflection, not evidence of failure, deficient "
        "character, or diminished worth.",
    ),
    PersonalOSDefinition(
        "deliberate_next_step",
        PersonalOSValueKind.SCALAR,
        "What one deliberate next step, if any, would make direction clearer?",
        "Keep it bounded and user-authored. This reflection creates no diagnosis, obligation, "
        "or moral ranking.",
    ),
)

IDENTITY_SECTION_DEFINITIONS: Mapping[str, PersonalOSDefinition] = MappingProxyType(
    {item.stable_id: item for item in _IDENTITY_DEFINITIONS}
)
AUDIT_PROMPT_DEFINITIONS: Mapping[str, PersonalOSDefinition] = MappingProxyType(
    {item.stable_id: item for item in _AUDIT_DEFINITIONS}
)
IDENTITY_SECTION_IDS = tuple(IDENTITY_SECTION_DEFINITIONS)
AUDIT_PROMPT_IDS = tuple(AUDIT_PROMPT_DEFINITIONS)
SCALAR_SECTION_IDS = tuple(
    item.stable_id
    for item in (*_IDENTITY_DEFINITIONS, *_AUDIT_DEFINITIONS)
    if item.value_kind is PersonalOSValueKind.SCALAR
)
LIST_SECTION_IDS = tuple(
    item.stable_id
    for item in _IDENTITY_DEFINITIONS
    if item.value_kind is PersonalOSValueKind.ORDERED_LIST
)


def _canonical_json(payload: Mapping[str, Any]) -> str:
    canonical_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    try:
        canonical_json.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise PersonalOSContractError(
            "Personal OS text must contain valid Unicode encodable as UTF-8."
        ) from exc
    return canonical_json


def canonical_personal_os_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def canonical_personal_os_snapshot_size(payload: Mapping[str, Any]) -> int:
    return len(_canonical_json(payload).encode("utf-8"))


def _validate_epoch_id(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 80:
        raise PersonalOSContractError(
            "assessment epoch ID must be a non-empty string of at most 80 characters."
        )
    _validate_utf8_text(value, label="assessment epoch ID")
    return value


def _validate_utf8_text(value: str, *, label: str) -> None:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise PersonalOSContractError(
            f"{label} must contain valid Unicode encodable as UTF-8."
        ) from exc


def _state(value: object, *, section_id: str) -> str:
    if not isinstance(value, str):
        raise PersonalOSContractError(f"{section_id} state must be a string.")
    try:
        return PersonalOSValueState(value).value
    except ValueError as exc:
        allowed = ", ".join(item.value for item in PersonalOSValueState)
        raise PersonalOSContractError(f"{section_id} state must be one of: {allowed}.") from exc


def _raw_parts(
    section_id: str,
    raw: PersonalOSValue | Mapping[str, Any],
) -> tuple[object, object]:
    if isinstance(raw, PersonalOSValue):
        return raw.state, raw.value
    if isinstance(raw, Mapping) and set(raw) == {"state", "value"}:
        return raw["state"], raw["value"]
    raise PersonalOSContractError(f"{section_id} must contain exactly state and value.")


def _normalize_value(
    definition: PersonalOSDefinition,
    raw: PersonalOSValue | Mapping[str, Any],
) -> dict[str, Any]:
    state_raw, value = _raw_parts(definition.stable_id, raw)
    state = _state(state_raw, section_id=definition.stable_id)
    if state != PersonalOSValueState.PROVIDED.value:
        if value is not None:
            raise PersonalOSContractError(
                f"{definition.stable_id} value must be null when state is {state}."
            )
        return {"state": state, "value": None}

    if definition.value_kind is PersonalOSValueKind.SCALAR:
        if not isinstance(value, str):
            raise PersonalOSContractError(f"{definition.stable_id} value must be a string.")
        if not value.strip():
            raise PersonalOSContractError(f"{definition.stable_id} value must not be blank.")
        _validate_utf8_text(value, label=f"{definition.stable_id} value")
        if len(value) > SCALAR_VALUE_MAX_LENGTH:
            raise PersonalOSContractError(
                f"{definition.stable_id} value must be at most "
                f"{SCALAR_VALUE_MAX_LENGTH} characters."
            )
        return {"state": state, "value": value}

    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PersonalOSContractError(
            f"{definition.stable_id} value must be an ordered list of strings."
        )
    items = list(value)
    if not LIST_ITEM_MIN_COUNT <= len(items) <= LIST_ITEM_MAX_COUNT:
        raise PersonalOSContractError(
            f"{definition.stable_id} must contain {LIST_ITEM_MIN_COUNT} to "
            f"{LIST_ITEM_MAX_COUNT} items."
        )
    for item in items:
        if not isinstance(item, str):
            raise PersonalOSContractError(f"{definition.stable_id} items must all be strings.")
        if not item.strip():
            raise PersonalOSContractError(f"{definition.stable_id} items must not be blank.")
        _validate_utf8_text(item, label=f"{definition.stable_id} item")
        if len(item) > LIST_ITEM_MAX_LENGTH:
            raise PersonalOSContractError(
                f"{definition.stable_id} items must be at most {LIST_ITEM_MAX_LENGTH} characters."
            )
    if len(set(items)) != len(items):
        raise PersonalOSContractError(f"{definition.stable_id} items must be unique.")
    return {"state": state, "value": items}


def _normalize_group(
    *,
    label: str,
    definitions: Mapping[str, PersonalOSDefinition],
    supplied: Mapping[str, PersonalOSValue | Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    if not isinstance(supplied, Mapping):
        raise PersonalOSContractError(f"{label} must be a mapping.")
    if any(not isinstance(section_id, str) for section_id in supplied):
        raise PersonalOSContractError(f"{label} keys must all be strings.")
    expected = set(definitions)
    actual = set(supplied)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if extra:
            details.append(f"unexpected {', '.join(extra)}")
        raise PersonalOSContractError(f"{label} set is invalid: {'; '.join(details)}.")
    return {
        section_id: _normalize_value(definition, supplied[section_id])
        for section_id, definition in definitions.items()
    }


def build_personal_os_snapshot(
    *,
    assessment_epoch_id: str,
    identity_sections: Mapping[str, PersonalOSValue | Mapping[str, Any]],
    audit_responses: Mapping[str, PersonalOSValue | Mapping[str, Any]],
    contract_version: str = PERSONAL_OS_CONTRACT_VERSION,
) -> CanonicalPersonalOSSnapshot:
    """Build a deterministic snapshot without inferring, analyzing, or scoring text."""

    if contract_version != PERSONAL_OS_CONTRACT_VERSION:
        raise PersonalOSContractError(
            f"Unsupported Personal OS contract version: {contract_version!r}."
        )
    payload = {
        "assessment_epoch_id": _validate_epoch_id(assessment_epoch_id),
        "audit_responses": _normalize_group(
            label="Audit response",
            definitions=AUDIT_PROMPT_DEFINITIONS,
            supplied=audit_responses,
        ),
        "contract_version": contract_version,
        "identity_sections": _normalize_group(
            label="Identity section",
            definitions=IDENTITY_SECTION_DEFINITIONS,
            supplied=identity_sections,
        ),
        "scope": PERSONAL_OS_SCOPE,
    }
    canonical_json = _canonical_json(payload)
    if len(canonical_json.encode("utf-8")) > MAX_CANONICAL_SNAPSHOT_BYTES:
        raise PersonalOSContractError(
            f"Canonical Personal OS snapshot exceeds {MAX_CANONICAL_SNAPSHOT_BYTES} bytes."
        )
    return CanonicalPersonalOSSnapshot(
        payload=payload,
        canonical_json=canonical_json,
        content_hash=hashlib.sha256(canonical_json.encode("utf-8")).hexdigest(),
    )
