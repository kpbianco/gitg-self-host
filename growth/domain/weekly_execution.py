from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any

WEEKLY_EXECUTION_CONTRACT_VERSION = "GG-WEEKLY-EXECUTION-1.0"
WEEKLY_EXECUTION_READINESS_CONTRACT_VERSION = "GG-WEEKLY-EXECUTION-READINESS-1.0"
WEEKLY_WINDOW_DAYS = 7
MAX_WEEKLY_SNAPSHOT_BYTES = 65536


class WeeklyExecutionContractError(ValueError):
    pass


class WeeklyProofOutcome(StrEnum):
    NO_SUBMITTED_EVIDENCE = "no_submitted_evidence"
    ATTEMPTED = "attempted"
    COMPLETED = "completed"


class WeeklyNextStep(StrEnum):
    CONTINUE_CURRENT = "continue_current"
    PLAN_NEXT_ACTION = "plan_next_action"
    PAUSE_RECONSIDER = "pause_reconsider"
    CHOOSE_DIFFERENT_PRACTICE = "choose_different_practice"


class WeeklyAdjustment(StrEnum):
    NONE = "none"
    TIMING = "timing"
    SCOPE = "scope"
    SUPPORT = "support"
    CONTEXT = "context"
    RECOVERY = "recovery"


@dataclass(frozen=True)
class CanonicalWeeklySnapshot:
    payload: dict[str, Any]
    canonical_json: str
    content_hash: str


def current_week_start(today: date) -> date:
    if not isinstance(today, date) or isinstance(today, datetime):
        raise WeeklyExecutionContractError("today must be a date.")
    return today - timedelta(days=today.weekday())


def week_end(week_start: date) -> date:
    return week_start + timedelta(days=WEEKLY_WINDOW_DAYS - 1)


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _snapshot(payload: dict[str, Any]) -> CanonicalWeeklySnapshot:
    canonical_json = _canonical_json(payload)
    try:
        encoded = canonical_json.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise WeeklyExecutionContractError("Weekly execution state must be valid UTF-8.") from exc
    if len(encoded) > MAX_WEEKLY_SNAPSHOT_BYTES:
        raise WeeklyExecutionContractError(
            f"Weekly execution snapshot exceeds {MAX_WEEKLY_SNAPSHOT_BYTES} bytes."
        )
    return CanonicalWeeklySnapshot(
        payload=payload,
        canonical_json=canonical_json,
        content_hash=hashlib.sha256(encoded).hexdigest(),
    )


def _token(value: object, label: str, *, maximum: int = 160) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise WeeklyExecutionContractError(
            f"{label} must be a non-empty string of at most {maximum} characters."
        )
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise WeeklyExecutionContractError(f"{label} must be valid UTF-8.") from exc
    return value


def _date(value: date | str, label: str) -> date:
    if isinstance(value, datetime):
        raise WeeklyExecutionContractError(f"{label} must be a date, not a datetime.")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise WeeklyExecutionContractError(f"{label} must be an ISO date.") from exc
    raise WeeklyExecutionContractError(f"{label} must be an ISO date.")


def _datetime(value: datetime | str, label: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise WeeklyExecutionContractError(f"{label} must be an ISO datetime.") from exc
    else:
        raise WeeklyExecutionContractError(f"{label} must be an ISO datetime.")
    if parsed.tzinfo is None:
        raise WeeklyExecutionContractError(f"{label} must include a timezone.")
    return parsed


def _choice(value: object, enum_type: type[StrEnum], label: str) -> str:
    if not isinstance(value, str):
        raise WeeklyExecutionContractError(f"{label} must be a string.")
    try:
        return enum_type(value).value
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise WeeklyExecutionContractError(f"{label} must be one of: {allowed}.") from exc


def build_weekly_plan_snapshot(
    *,
    assessment_epoch_id: str,
    sprint_id: str,
    protocol_stable_id: str,
    action_stable_id: str,
    week_start: date | str,
    intended_on: date | str,
    contract_version: str = WEEKLY_EXECUTION_CONTRACT_VERSION,
) -> CanonicalWeeklySnapshot:
    if contract_version != WEEKLY_EXECUTION_CONTRACT_VERSION:
        raise WeeklyExecutionContractError(
            f"Unsupported weekly execution contract: {contract_version!r}."
        )
    start = _date(week_start, "week_start")
    intended = _date(intended_on, "intended_on")
    if start.weekday() != 0:
        raise WeeklyExecutionContractError("week_start must be a Monday.")
    if not start <= intended <= week_end(start):
        raise WeeklyExecutionContractError("intended_on must fall inside the seven-day window.")
    return _snapshot(
        {
            "action_stable_id": _token(action_stable_id, "action_stable_id"),
            "assessment_epoch_id": _token(assessment_epoch_id, "assessment_epoch_id", maximum=80),
            "contract_version": contract_version,
            "intended_on": intended.isoformat(),
            "protocol_stable_id": _token(protocol_stable_id, "protocol_stable_id"),
            "scope": "weekly_execution_plan",
            "sprint_id": _token(sprint_id, "sprint_id"),
            "week_start": start.isoformat(),
        }
    )


def _normalize_proof_events(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise WeeklyExecutionContractError("proof_events must be a sequence.")
    normalized: list[dict[str, Any]] = []
    expected_keys = {
        "action_completed",
        "action_attempted",
        "adverse",
        "algorithm_version",
        "direction",
        "event_id",
        "submitted_at",
        "withholding_reasons",
    }
    for position, event in enumerate(events, start=1):
        if not isinstance(event, Mapping) or set(event) != expected_keys:
            raise WeeklyExecutionContractError(
                f"proof event {position} must contain exactly the supported fields."
            )
        submitted_at = event["submitted_at"]
        if not isinstance(submitted_at, str):
            raise WeeklyExecutionContractError(f"proof event {position} submitted_at is invalid.")
        try:
            parsed = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise WeeklyExecutionContractError(
                f"proof event {position} submitted_at must be an ISO datetime."
            ) from exc
        if parsed.tzinfo is None:
            raise WeeklyExecutionContractError(
                f"proof event {position} submitted_at must include a timezone."
            )
        for field in ("action_attempted", "action_completed", "adverse"):
            if not isinstance(event[field], bool):
                raise WeeklyExecutionContractError(
                    f"proof event {position} {field} must be Boolean."
                )
        reasons = event["withholding_reasons"]
        if isinstance(reasons, (str, bytes)) or not isinstance(reasons, Sequence):
            raise WeeklyExecutionContractError(
                f"proof event {position} withholding_reasons must be a sequence."
            )
        normalized_reasons = sorted(
            _token(item, f"proof event {position} withholding reason", maximum=120)
            for item in reasons
        )
        if len(normalized_reasons) != len(set(normalized_reasons)):
            raise WeeklyExecutionContractError(
                f"proof event {position} withholding reasons must be unique."
            )
        normalized.append(
            {
                "action_completed": event["action_completed"],
                "action_attempted": event["action_attempted"],
                "adverse": event["adverse"],
                "algorithm_version": _token(
                    event["algorithm_version"],
                    f"proof event {position} algorithm_version",
                    maximum=80,
                ),
                "direction": _token(
                    event["direction"], f"proof event {position} direction", maximum=40
                ),
                "event_id": _token(event["event_id"], f"proof event {position} event_id"),
                "submitted_at": parsed.isoformat(),
                "withholding_reasons": normalized_reasons,
            }
        )
    normalized.sort(key=lambda item: (item["submitted_at"], item["event_id"]))
    event_ids = [item["event_id"] for item in normalized]
    if len(event_ids) != len(set(event_ids)):
        raise WeeklyExecutionContractError("proof event IDs must be unique.")
    return normalized


def build_weekly_review_snapshot(
    *,
    plan_stable_id: str,
    plan_content_hash: str,
    proof_events: Sequence[Mapping[str, Any]],
    reviewed_at: datetime | str,
    next_step: WeeklyNextStep | str,
    adjustment: WeeklyAdjustment | str,
    contract_version: str = WEEKLY_EXECUTION_CONTRACT_VERSION,
) -> CanonicalWeeklySnapshot:
    if contract_version != WEEKLY_EXECUTION_CONTRACT_VERSION:
        raise WeeklyExecutionContractError(
            f"Unsupported weekly execution contract: {contract_version!r}."
        )
    events = _normalize_proof_events(proof_events)
    reviewed = _datetime(reviewed_at, "reviewed_at")
    if any(
        _datetime(item["submitted_at"], "proof event submitted_at") > reviewed for item in events
    ):
        raise WeeklyExecutionContractError(
            "proof events must not occur after the immutable review cutoff."
        )
    if any(item["action_completed"] for item in events):
        outcome = WeeklyProofOutcome.COMPLETED.value
    elif any(item["action_attempted"] for item in events):
        outcome = WeeklyProofOutcome.ATTEMPTED.value
    else:
        outcome = WeeklyProofOutcome.NO_SUBMITTED_EVIDENCE.value
    return _snapshot(
        {
            "adjustment": _choice(adjustment, WeeklyAdjustment, "adjustment"),
            "contract_version": contract_version,
            "next_step": _choice(next_step, WeeklyNextStep, "next_step"),
            "outcome": outcome,
            "plan_content_hash": _token(plan_content_hash, "plan_content_hash", maximum=64),
            "plan_stable_id": _token(plan_stable_id, "plan_stable_id"),
            "proof_events": events,
            "reviewed_at": reviewed.isoformat(),
            "scope": "weekly_execution_review",
        }
    )
