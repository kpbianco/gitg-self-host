from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

ASSESSMENT_CALIBRATION_CONSENT_VERSION = "GG-ASSESSMENT-CALIBRATION-CONSENT-1.0"
ASSESSMENT_CALIBRATION_EXPORT_VERSION = "grounded-growth-assessment-calibration-export-v1"
ASSESSMENT_CALIBRATION_DISCLOSURE_VERSION = "assessment-calibration-disclosure-v1"

CALIBRATION_EXPORT_FIELDS = (
    "assessment version and source",
    "item IDs and item-level 1-5 or not-applicable responses",
    "answered clarifier IDs and responses",
    "item-level and total timing when available",
    "response-quality flags and summary values",
    "pseudonymous participant token and within-participant run sequence",
    "whole-day interval from the participant's first included run",
)


class CalibrationConsentState(StrEnum):
    CONSENTED = "consented"
    WITHDRAWN = "withdrawn"


def canonical_calibration_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def calibration_hash(value: Any) -> str:
    return hashlib.sha256(canonical_calibration_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CalibrationConsentSnapshot:
    payload: dict[str, Any]
    content_hash: str


def build_calibration_consent_snapshot(
    *,
    assessment_epoch_id: str,
    assessment_version: str,
    participant_token: str,
    revision: int,
    state: str,
) -> CalibrationConsentSnapshot:
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise ValueError("Calibration-consent revision must be a positive integer.")
    try:
        normalized_state = CalibrationConsentState(state).value
    except ValueError as exc:
        raise ValueError("Calibration-consent state is unsupported.") from exc
    payload = {
        "assessment_epoch_id": assessment_epoch_id,
        "assessment_version": assessment_version,
        "consent_state": normalized_state,
        "contract_version": ASSESSMENT_CALIBRATION_CONSENT_VERSION,
        "disclosure_version": ASSESSMENT_CALIBRATION_DISCLOSURE_VERSION,
        "export_fields": list(CALIBRATION_EXPORT_FIELDS),
        "participant_token": participant_token,
        "revision": revision,
    }
    return CalibrationConsentSnapshot(payload=payload, content_hash=calibration_hash(payload))
