from __future__ import annotations

import math
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

import yaml
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from growth.domain.assessment_calibration import (
    ASSESSMENT_CALIBRATION_CONSENT_VERSION,
    ASSESSMENT_CALIBRATION_DISCLOSURE_VERSION,
    ASSESSMENT_CALIBRATION_EXPORT_VERSION,
    CALIBRATION_EXPORT_FIELDS,
    CalibrationConsentState,
    build_calibration_consent_snapshot,
    calibration_hash,
    canonical_calibration_json,
)
from growth.models import AssessmentCalibrationConsent, AssessmentRun
from growth.services.assessment import load_assessment_assets

EXPECTED_TIMING_METHOD = "full interval from question display until Next/Back"
ALLOWED_RESPONSE_QUALITY_FLAGS = frozenset(
    {
        "Responses were exceptionally fast; confidence was modestly reduced.",
        "Responses were fast; confidence was slightly reduced.",
        "Nearly all capability responses were identical; possible straight-lining.",
        "Capability responses showed unusually little differentiation.",
        "Several core items were skipped; confidence was reduced.",
    }
)


class AssessmentCalibrationError(ValueError):
    pass


@dataclass(frozen=True)
class CalibrationConsentResult:
    consent: AssessmentCalibrationConsent
    created: bool


@dataclass(frozen=True)
class CalibrationReadinessSummary:
    contract_version: str
    export_schema_version: str
    consent_revisions: int
    active_participants: int
    active_assessment_runs: int
    software_ready: bool
    remote_telemetry_used: bool
    changes_assessment: bool
    changes_score_state: bool
    participant_evidence_axes_completed: int
    requires_qualified_analysis: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _finite_number(
    value: Any,
    label: str,
    *,
    nullable: bool = False,
) -> float | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise AssessmentCalibrationError(f"{label} is not a finite number.")
    number = float(value)
    if not math.isfinite(number) or number < 0 or number > 604800:
        raise AssessmentCalibrationError(f"{label} is outside the supported range.")
    return number


def _validated_assessment_payload(run: AssessmentRun) -> dict[str, Any]:
    assets = load_assessment_assets()
    if run.assessment_version != assets.spec["assessment"]["version"]:
        raise AssessmentCalibrationError("A consented assessment version is unsupported.")
    if run.source not in {AssessmentRun.Source.APPLICATION, AssessmentRun.Source.SHARE_CODE}:
        raise AssessmentCalibrationError("Only participant-created assessment runs may be used.")

    assessment = assets.spec["assessment"]
    core_items = assessment["core_items"]
    capability_clarifiers = assessment["adaptive_capability_clarifiers"]
    orientation_clarifiers = assessment["adaptive_orientation_clarifiers"]
    items = core_items + capability_clarifiers + orientation_clarifiers
    item_map = {item["id"]: item for item in items}
    core_ids = [item["id"] for item in core_items]
    capability_ids = {item["id"] for item in capability_clarifiers}
    orientation_ids = {item["id"] for item in orientation_clarifiers}

    if not isinstance(run.answers, dict) or set(run.answers) != set(core_ids):
        raise AssessmentCalibrationError("A consented assessment has incomplete core responses.")
    if not isinstance(run.clarifier_answers, dict):
        raise AssessmentCalibrationError(
            "A consented assessment has malformed clarifier responses."
        )
    clarifier_ids = set(run.clarifier_answers)
    if not clarifier_ids.issubset(capability_ids | orientation_ids):
        raise AssessmentCalibrationError("A consented assessment has unknown clarifier responses.")
    if len(clarifier_ids & capability_ids) > 8 or len(clarifier_ids & orientation_ids) > 2:
        raise AssessmentCalibrationError("A consented assessment exceeds clarifier limits.")

    responses = {**run.answers, **run.clarifier_answers}
    for item_id, value in responses.items():
        item = item_map[item_id]
        if value == "NA":
            if not item.get("allow_not_applicable"):
                raise AssessmentCalibrationError(
                    "A consented assessment has an invalid not-applicable response."
                )
        elif isinstance(value, bool) or not isinstance(value, int) or value not in range(1, 6):
            raise AssessmentCalibrationError(
                "A consented assessment has a response outside the supported scale."
            )

    timing_data = run.timing_data
    if not isinstance(timing_data, dict) or not isinstance(
        timing_data.get("timings_seconds", {}), dict
    ):
        raise AssessmentCalibrationError("A consented assessment has malformed timing data.")
    timings = timing_data.get("timings_seconds", {})
    if not set(timings).issubset(responses):
        raise AssessmentCalibrationError("A consented assessment has timing for an unknown item.")
    normalized_timings = {
        item_id: _finite_number(value, "Item timing") for item_id, value in timings.items()
    }
    if run.source == AssessmentRun.Source.APPLICATION and set(normalized_timings) != set(responses):
        raise AssessmentCalibrationError(
            "A completed in-app assessment is missing item-level timing."
        )
    total_seconds = _finite_number(timing_data.get("total_seconds"), "Total timing", nullable=True)
    if run.source == AssessmentRun.Source.APPLICATION and (
        total_seconds is None or abs(sum(normalized_timings.values()) - total_seconds) > 0.01
    ):
        raise AssessmentCalibrationError("A completed in-app assessment timing does not replay.")

    quality = run.response_quality_result
    if not isinstance(quality, dict) or not isinstance(quality.get("flags", []), list):
        raise AssessmentCalibrationError("A consented assessment has malformed response quality.")
    flags = quality.get("flags", [])
    if any(not isinstance(flag, str) for flag in flags) or not set(flags).issubset(
        ALLOWED_RESPONSE_QUALITY_FLAGS
    ):
        raise AssessmentCalibrationError("A consented assessment has malformed quality flags.")
    modifier = quality.get("modifier")
    if isinstance(modifier, bool) or not isinstance(modifier, int | float):
        raise AssessmentCalibrationError("A consented assessment has no quality modifier.")
    modifier = float(modifier)
    if not math.isfinite(modifier) or modifier < 0 or modifier > 1:
        raise AssessmentCalibrationError("A consented assessment quality modifier is invalid.")
    quality_total = _finite_number(quality.get("total_timed_seconds"), "Quality total timing")
    quality_median = _finite_number(
        quality.get("median_seconds_per_item"), "Quality median timing", nullable=True
    )
    if run.source == AssessmentRun.Source.APPLICATION and abs(quality_total - total_seconds) > 0.01:
        raise AssessmentCalibrationError("Response-quality timing does not match the assessment.")
    timing_method = quality.get("timing_method")
    if timing_method != EXPECTED_TIMING_METHOD:
        raise AssessmentCalibrationError("A consented assessment timing method is unsupported.")

    return {
        "assessment_version": run.assessment_version,
        "source": run.source,
        "core_responses": {item_id: run.answers[item_id] for item_id in core_ids},
        "clarifier_responses": {
            item_id: run.clarifier_answers[item_id] for item_id in sorted(run.clarifier_answers)
        },
        "timings_seconds": {
            item_id: normalized_timings[item_id] for item_id in sorted(normalized_timings)
        },
        "total_seconds": total_seconds,
        "response_quality": {
            "flags": sorted(flags),
            "median_seconds_per_item": quality_median,
            "modifier": modifier,
            "timing_method": timing_method,
            "total_timed_seconds": quality_total,
        },
    }


def _validated_history(
    *, users: Iterable[Any] | None = None
) -> tuple[
    list[AssessmentCalibrationConsent],
    dict[tuple[Any, str], AssessmentCalibrationConsent],
]:
    queryset = AssessmentCalibrationConsent.objects.select_related("assessment_run", "user")
    if users is not None:
        user_ids = [user.pk for user in users]
        queryset = queryset.filter(user_id__in=user_ids)
    rows = list(queryset.order_by("user_id", "assessment_run_id", "revision"))
    tokens: dict[Any, uuid.UUID] = {}
    token_owners: dict[uuid.UUID, Any] = {}
    revisions: dict[tuple[Any, str], list[int]] = {}
    latest: dict[tuple[Any, str], AssessmentCalibrationConsent] = {}
    for row in rows:
        try:
            row.full_clean()
        except (ValidationError, ValueError, TypeError):
            raise AssessmentCalibrationError(
                "Stored assessment calibration consent failed deterministic verification."
            ) from None
        if row.assessment_run.source == AssessmentRun.Source.PILOT_SEED:
            raise AssessmentCalibrationError("Pilot seed data cannot enter a calibration export.")
        if row.user_id in tokens and tokens[row.user_id] != row.participant_token:
            raise AssessmentCalibrationError(
                "One participant has inconsistent calibration pseudonyms."
            )
        if (
            row.participant_token in token_owners
            and token_owners[row.participant_token] != row.user_id
        ):
            raise AssessmentCalibrationError(
                "A calibration pseudonym is assigned to more than one participant."
            )
        tokens[row.user_id] = row.participant_token
        token_owners[row.participant_token] = row.user_id
        key = (row.user_id, row.assessment_run_id)
        revisions.setdefault(key, []).append(row.revision)
        latest[key] = row
    if any(actual != list(range(1, len(actual) + 1)) for actual in revisions.values()):
        raise AssessmentCalibrationError(
            "Assessment calibration consent revisions are not contiguous from one."
        )
    return rows, latest


@transaction.atomic
def record_assessment_calibration_consent(
    *,
    user,
    assessment_run: AssessmentRun,
    state: str,
) -> CalibrationConsentResult:
    try:
        normalized_state = CalibrationConsentState(state).value
    except ValueError as exc:
        raise AssessmentCalibrationError(
            "Assessment calibration consent state is invalid."
        ) from exc
    user_model = get_user_model()
    try:
        locked_user = user_model.objects.select_for_update().get(pk=user.pk)
        locked_run = AssessmentRun.objects.select_for_update().get(pk=assessment_run.pk)
    except (user_model.DoesNotExist, AssessmentRun.DoesNotExist):
        raise AssessmentCalibrationError("The selected assessment no longer exists.") from None
    if locked_run.user_id != locked_user.pk:
        raise AssessmentCalibrationError("The selected assessment belongs to another user.")
    if locked_run.source == AssessmentRun.Source.PILOT_SEED:
        raise AssessmentCalibrationError("The demonstration assessment cannot be contributed.")
    if normalized_state == CalibrationConsentState.CONSENTED.value:
        _validated_assessment_payload(locked_run)

    all_rows, latest = _validated_history(users=[locked_user])
    key = (locked_user.pk, locked_run.pk)
    previous = latest.get(key)
    if previous is not None and previous.state == normalized_state:
        return CalibrationConsentResult(consent=previous, created=False)
    participant_token = all_rows[0].participant_token if all_rows else uuid.uuid4()
    run_rows = [row for row in all_rows if row.assessment_run_id == locked_run.pk]
    revision = len(run_rows) + 1
    snapshot = build_calibration_consent_snapshot(
        assessment_epoch_id=str(locked_run.pk),
        assessment_version=locked_run.assessment_version,
        participant_token=str(participant_token),
        revision=revision,
        state=normalized_state,
    )
    consent = AssessmentCalibrationConsent(
        user=locked_user,
        assessment_run=locked_run,
        contract_version=ASSESSMENT_CALIBRATION_CONSENT_VERSION,
        participant_token=participant_token,
        revision=revision,
        state=normalized_state,
        canonical_snapshot=snapshot.payload,
        content_hash=snapshot.content_hash,
    )
    consent.full_clean()
    consent.save(force_insert=True)
    return CalibrationConsentResult(consent=consent, created=True)


def build_assessment_calibration_export(*, users: Iterable[Any] | None = None) -> dict[str, Any]:
    selected_users = None if users is None else list(users)
    _, latest = _validated_history(users=selected_users)
    active = [
        row for row in latest.values() if row.state == CalibrationConsentState.CONSENTED.value
    ]
    grouped: dict[Any, list[AssessmentCalibrationConsent]] = {}
    for row in active:
        grouped.setdefault(row.user_id, []).append(row)

    participants = []
    for participant_rows in grouped.values():
        participant_rows.sort(
            key=lambda row: (row.assessment_run.created_at, row.assessment_run_id)
        )
        first_date = participant_rows[0].assessment_run.created_at.date()
        exported_runs = []
        for sequence, consent in enumerate(participant_rows, start=1):
            run_payload = _validated_assessment_payload(consent.assessment_run)
            exported_runs.append(
                {
                    **run_payload,
                    "consent_contract_version": consent.contract_version,
                    "days_since_first_included_run": (
                        consent.assessment_run.created_at.date() - first_date
                    ).days,
                    "run_sequence": sequence,
                }
            )
        token = participant_rows[0].participant_token
        participants.append(
            {
                "participant_ref": f"participant-{token.hex}",
                "runs": exported_runs,
            }
        )
    participants.sort(key=lambda participant: participant["participant_ref"])
    content = {
        "assessment_run_count": sum(len(item["runs"]) for item in participants),
        "collection": {
            "abandonment_captured": False,
            "consent_required_per_completed_run": True,
            "remote_telemetry_used": False,
            "test_retest_linkable": True,
        },
        "consent_contract_version": ASSESSMENT_CALIBRATION_CONSENT_VERSION,
        "disclosure_version": ASSESSMENT_CALIBRATION_DISCLOSURE_VERSION,
        "export_fields": list(CALIBRATION_EXPORT_FIELDS),
        "participant_count": len(participants),
        "participant_evidence_axes_completed": 0,
        "participants": participants,
        "privacy": {
            "classification": "sensitive_pseudonymous_assessment_data",
            "contains_exact_timestamps": False,
            "contains_free_text": False,
            "contains_identity": False,
            "contains_item_responses": True,
            "contains_item_timing": True,
            "contains_pseudonymous_linkage": True,
            "contains_share_codes": False,
            "excluded": [
                "account identity and database keys",
                "exact dates and timestamps",
                "assessment share codes",
                "free text and Personal OS or context values",
                "evidence, score state, completion credit, and practice history",
                "orientation, archetype, lever, domain, and competency outputs",
            ],
        },
        "schema_version": ASSESSMENT_CALIBRATION_EXPORT_VERSION,
        "validation_status": "data_collection_required",
    }
    return {**content, "dataset_sha256": calibration_hash(content)}


def render_assessment_calibration_export(*, users: Iterable[Any] | None = None) -> bytes:
    return (
        canonical_calibration_json(build_assessment_calibration_export(users=users)) + "\n"
    ).encode("utf-8")


def verify_assessment_calibration_collection_readiness() -> CalibrationReadinessSummary:
    contract_path = settings.BASE_DIR / "contracts" / "assessment-calibration-consent.yaml"
    try:
        contract = yaml.safe_load(contract_path.read_text())
    except (OSError, yaml.YAMLError):
        raise AssessmentCalibrationError(
            "Assessment calibration consent contract could not be loaded."
        ) from None
    expected_invariants = {
        "automatic_enrollment": False,
        "changes_assessment": False,
        "changes_recommendations": False,
        "changes_score_state": False,
        "exports_exact_timestamps": False,
        "exports_identity": False,
        "exports_share_codes": False,
        "remote_telemetry": False,
    }
    if contract.get("contract_version") != ASSESSMENT_CALIBRATION_CONSENT_VERSION:
        raise AssessmentCalibrationError("Assessment calibration consent contract is unsupported.")
    if contract.get("export_schema_version") != ASSESSMENT_CALIBRATION_EXPORT_VERSION:
        raise AssessmentCalibrationError("Assessment calibration export schema is unsupported.")
    if contract.get("invariants") != expected_invariants:
        raise AssessmentCalibrationError("Assessment calibration consent invariants do not match.")
    first = build_assessment_calibration_export()
    second = build_assessment_calibration_export()
    if first != second:
        raise AssessmentCalibrationError("Assessment calibration export is not deterministic.")
    rows, _ = _validated_history()
    return CalibrationReadinessSummary(
        contract_version=ASSESSMENT_CALIBRATION_CONSENT_VERSION,
        export_schema_version=ASSESSMENT_CALIBRATION_EXPORT_VERSION,
        consent_revisions=len(rows),
        active_participants=first["participant_count"],
        active_assessment_runs=first["assessment_run_count"],
        software_ready=True,
        remote_telemetry_used=False,
        changes_assessment=False,
        changes_score_state=False,
        participant_evidence_axes_completed=0,
        requires_qualified_analysis=True,
    )
