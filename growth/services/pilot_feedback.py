from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError

from growth.models import (
    PILOT_FEEDBACK_CONTRACT_VERSION,
    PilotFeedback,
)

PILOT_EXPORT_SCHEMA_VERSION = "grounded-growth-private-pilot-export-v1"

PRACTICE_FEEDBACK_STAGES = frozenset(
    {
        PilotFeedback.JourneyStage.RECOMMENDATION,
        PilotFeedback.JourneyStage.SETUP,
        PilotFeedback.JourneyStage.ACTIVE_PRACTICE,
        PilotFeedback.JourneyStage.CHECK_IN,
        PilotFeedback.JourneyStage.REVIEW,
    }
)
FEEDBACK_FIELD_STAGES = {
    "protocol": PRACTICE_FEEDBACK_STAGES,
    "applicability": PRACTICE_FEEDBACK_STAGES,
    "time_to_start": frozenset(
        {
            PilotFeedback.JourneyStage.SETUP,
            PilotFeedback.JourneyStage.ACTIVE_PRACTICE,
            PilotFeedback.JourneyStage.CHECK_IN,
            PilotFeedback.JourneyStage.REVIEW,
        }
    ),
    "time_to_check_in": frozenset(
        {
            PilotFeedback.JourneyStage.CHECK_IN,
            PilotFeedback.JourneyStage.REVIEW,
        }
    ),
}


class PilotFeedbackError(ValueError):
    pass


@dataclass(frozen=True)
class PilotFeedbackSummary:
    total: int
    recent: tuple[PilotFeedback, ...]


def feedback_scope_errors(cleaned_data: dict[str, Any]) -> dict[str, str]:
    """Return participant-facing errors for answers outside the selected stage."""

    stage = cleaned_data.get("journey_stage")
    if stage not in PilotFeedback.JourneyStage.values:
        return {"journey_stage": "Choose the part of the experience you are commenting on."}

    errors = {}
    for field_name, allowed_stages in FEEDBACK_FIELD_STAGES.items():
        if cleaned_data.get(field_name) and stage not in allowed_stages:
            errors[field_name] = (
                "This question does not apply to the selected part of the experience. "
                "Choose a practice-related part or leave it unanswered."
            )
    return errors


def submit_pilot_feedback(*, user, cleaned_data: dict[str, Any]) -> PilotFeedback:
    """Create one immutable usability record without touching developmental state."""

    scope_errors = feedback_scope_errors(cleaned_data)
    if scope_errors:
        raise PilotFeedbackError("; ".join(scope_errors.values()))

    record = PilotFeedback(
        user=user,
        contract_version=PILOT_FEEDBACK_CONTRACT_VERSION,
        journey_stage=cleaned_data["journey_stage"],
        protocol=cleaned_data.get("protocol"),
        applicability=cleaned_data.get("applicability", ""),
        time_to_start=cleaned_data.get("time_to_start", ""),
        time_to_check_in=cleaned_data.get("time_to_check_in", ""),
        confusing_step=cleaned_data.get("confusing_step", ""),
        accessibility_friction=cleaned_data.get("accessibility_friction", ""),
        safety_friction=cleaned_data.get("safety_friction", ""),
        comment=cleaned_data.get("comment", "").strip(),
    )
    record.full_clean()
    record.save(force_insert=True)
    return record


def build_pilot_feedback_summary(user, *, recent_limit: int = 5) -> PilotFeedbackSummary:
    records = PilotFeedback.objects.filter(user=user).select_related("protocol")
    return PilotFeedbackSummary(
        total=records.count(),
        recent=tuple(records.order_by("-submitted_at", "-stable_id")[:recent_limit]),
    )


def _validate_export_record(record: PilotFeedback) -> None:
    try:
        record.full_clean(validate_unique=False)
    except ValidationError as exc:
        raise PilotFeedbackError("Stored pilot feedback failed contract validation.") from exc
    if record.contract_version != PILOT_FEEDBACK_CONTRACT_VERSION:
        raise PilotFeedbackError("Stored pilot feedback uses an unsupported contract.")


def build_privacy_safe_pilot_export(user) -> dict[str, Any]:
    """Build a deterministic, allowlisted export of one user's optional feedback."""

    records = list(
        PilotFeedback.objects.filter(user=user)
        .select_related("protocol")
        .order_by("submitted_at", "stable_id")
    )
    exported = []
    for sequence, record in enumerate(records, start=1):
        _validate_export_record(record)
        exported.append(
            {
                "sequence": sequence,
                "contract_version": record.contract_version,
                "journey_stage": record.journey_stage,
                "protocol_stable_id": record.protocol_id,
                "applicability": record.applicability or None,
                "time_to_start_band": record.time_to_start or None,
                "time_to_check_in_band": record.time_to_check_in or None,
                "confusing_step": record.confusing_step or None,
                "accessibility_friction": record.accessibility_friction or None,
                "safety_friction": record.safety_friction or None,
                "optional_comment_present": bool(record.comment),
            }
        )

    return {
        "schema_version": PILOT_EXPORT_SCHEMA_VERSION,
        "feedback_contract_version": PILOT_FEEDBACK_CONTRACT_VERSION,
        "source": "optional_participant_report",
        "collection_method": "participant_selected_categories",
        "remote_telemetry_used": False,
        "developmental_state_modified_by_feedback": False,
        "record_count": len(exported),
        "privacy": {
            "contains_user_identity": False,
            "contains_record_ids": False,
            "contains_exact_timestamps": False,
            "contains_free_text": False,
            "contains_assessment_or_evidence_values": False,
            "excluded": [
                "user identity",
                "feedback and database record IDs",
                "exact dates and times",
                "all free-text comments",
                "private practice context labels",
                "assessment answers and share codes",
                "developmental evidence and score state",
                "orientation and archetype outputs",
            ],
        },
        "records": exported,
    }
