from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from itertools import pairwise
from statistics import median
from typing import Any

import yaml
from django.conf import settings
from jsonschema import Draft202012Validator

from growth.domain.assessment_calibration import (
    ASSESSMENT_CALIBRATION_CONSENT_VERSION,
    ASSESSMENT_CALIBRATION_DISCLOSURE_VERSION,
    ASSESSMENT_CALIBRATION_EXPORT_VERSION,
    CALIBRATION_EXPORT_FIELDS,
    calibration_hash,
    canonical_calibration_json,
)
from growth.services.assessment import load_assessment_assets
from growth.services.assessment_calibration import (
    ALLOWED_RESPONSE_QUALITY_FLAGS,
    EXPECTED_TIMING_METHOD,
)

ASSESSMENT_CALIBRATION_ANALYSIS_VERSION = "GG-ASSESSMENT-CALIBRATION-ANALYSIS-READINESS-1.0"
ASSESSMENT_CALIBRATION_ANALYSIS_SCHEMA_VERSION = (
    "grounded-growth-assessment-calibration-analysis-v1"
)
SMALL_CELL_THRESHOLD = 5
MINIMUM_DESCRIPTIVE_PARTICIPANTS = 30
MINIMUM_RETEST_PARTICIPANTS = 30
MAX_DATASET_BYTES = 50 * 1024 * 1024
PARTICIPANT_REF_PATTERN = re.compile(r"^participant-[0-9a-f]{32}$")

PARTICIPANT_EVIDENCE_AXES = (
    "item_response_distribution",
    "item_missingness_and_not_applicable",
    "test_retest_reliability",
    "convergent_and_discriminant_validity",
    "differential_item_functioning_and_fairness",
    "completion_burden_and_abandonment",
    "recommendation_fit",
    "longitudinal_outcome_association",
)

EXPORT_PRIVACY_EXCLUSIONS = (
    "account identity and database keys",
    "exact dates and timestamps",
    "assessment share codes",
    "free text and Personal OS or context values",
    "evidence, score state, completion credit, and practice history",
    "orientation, archetype, lever, domain, and competency outputs",
)

ANALYSIS_CLAIM_BOUNDARY = (
    "This deterministic private aggregate is an analysis-readiness aid only. It does not "
    "complete any participant evidence axis or establish item calibration, temporal "
    "reliability, construct validity, fairness, accessibility-population validity, burden "
    "or abandonment validity, recommendation fit, longitudinal association, clinical "
    "validity, intervention effectiveness, release readiness, mastery, or human worth. "
    "Retained consented data, a prespecified study design, and qualified human analysis "
    "remain required."
)


class AssessmentCalibrationAnalysisError(ValueError):
    pass


@dataclass(frozen=True)
class CalibrationAnalysisReadinessSummary:
    contract_version: str
    input_schema_version: str
    analysis_schema_version: str
    software_ready: bool
    synthetic_participants: int
    synthetic_assessment_runs: int
    participant_evidence_axes_completed: int
    database_accessed: bool
    raw_values_in_report: bool
    requires_qualified_analysis: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _expect_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise AssessmentCalibrationAnalysisError(f"{label} does not match the exact allowlist.")
    return value


def _finite_number(
    value: Any,
    label: str,
    *,
    nullable: bool = False,
    maximum: float = 604800,
) -> float | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise AssessmentCalibrationAnalysisError(f"{label} is not a finite number.")
    result = float(value)
    if not math.isfinite(result) or result < 0 or result > maximum:
        raise AssessmentCalibrationAnalysisError(f"{label} is outside the supported range.")
    return result


def _validate_response(value: Any, item: dict[str, Any]) -> int | str:
    if value == "NA":
        if not item.get("allow_not_applicable"):
            raise AssessmentCalibrationAnalysisError(
                "A calibration response uses N/A for an unsupported item."
            )
        return value
    if isinstance(value, bool) or not isinstance(value, int) or value not in range(1, 6):
        raise AssessmentCalibrationAnalysisError(
            "A calibration response is outside the supported scale."
        )
    return value


def _validate_contract() -> None:
    contract_path = settings.BASE_DIR / "contracts" / "assessment-calibration-analysis.yaml"
    try:
        contract = yaml.safe_load(contract_path.read_text())
    except (OSError, yaml.YAMLError):
        raise AssessmentCalibrationAnalysisError(
            "The assessment calibration analysis contract could not be loaded."
        ) from None
    expected = {
        "small_cell_threshold": SMALL_CELL_THRESHOLD,
        "minimum_descriptive_participants": MINIMUM_DESCRIPTIVE_PARTICIPANTS,
        "minimum_retest_participants": MINIMUM_RETEST_PARTICIPANTS,
    }
    if contract.get("contract_version") != ASSESSMENT_CALIBRATION_ANALYSIS_VERSION:
        raise AssessmentCalibrationAnalysisError(
            "The assessment calibration analysis contract is unsupported."
        )
    if contract.get("input_schema_version") != ASSESSMENT_CALIBRATION_EXPORT_VERSION:
        raise AssessmentCalibrationAnalysisError(
            "The assessment calibration analysis input schema is unsupported."
        )
    if contract.get("report_schema_version") != ASSESSMENT_CALIBRATION_ANALYSIS_SCHEMA_VERSION:
        raise AssessmentCalibrationAnalysisError(
            "The assessment calibration analysis report schema is unsupported."
        )
    if contract.get("thresholds") != expected:
        raise AssessmentCalibrationAnalysisError(
            "The assessment calibration analysis thresholds do not match."
        )
    if tuple(contract.get("participant_evidence_axes", ())) != PARTICIPANT_EVIDENCE_AXES:
        raise AssessmentCalibrationAnalysisError(
            "The assessment calibration evidence-axis inventory does not match."
        )


def _validate_export(dataset: Any) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    dataset = _expect_keys(
        dataset,
        {
            "assessment_run_count",
            "collection",
            "consent_contract_version",
            "dataset_sha256",
            "disclosure_version",
            "export_fields",
            "participant_count",
            "participant_evidence_axes_completed",
            "participants",
            "privacy",
            "schema_version",
            "validation_status",
        },
        "Calibration dataset",
    )
    if dataset["schema_version"] != ASSESSMENT_CALIBRATION_EXPORT_VERSION:
        raise AssessmentCalibrationAnalysisError("The calibration dataset schema is unsupported.")
    if dataset["consent_contract_version"] != ASSESSMENT_CALIBRATION_CONSENT_VERSION:
        raise AssessmentCalibrationAnalysisError(
            "The calibration dataset consent contract is unsupported."
        )
    if dataset["disclosure_version"] != ASSESSMENT_CALIBRATION_DISCLOSURE_VERSION:
        raise AssessmentCalibrationAnalysisError(
            "The calibration dataset disclosure is unsupported."
        )
    if dataset["export_fields"] != list(CALIBRATION_EXPORT_FIELDS):
        raise AssessmentCalibrationAnalysisError(
            "The calibration dataset export-field allowlist does not match."
        )
    if dataset["participant_evidence_axes_completed"] != 0:
        raise AssessmentCalibrationAnalysisError(
            "The input cannot claim completed participant evidence axes."
        )
    if dataset["validation_status"] != "data_collection_required":
        raise AssessmentCalibrationAnalysisError("The input calibration status is unsupported.")
    content = {key: value for key, value in dataset.items() if key != "dataset_sha256"}
    if dataset["dataset_sha256"] != calibration_hash(content):
        raise AssessmentCalibrationAnalysisError(
            "The calibration dataset hash failed deterministic verification."
        )

    collection = _expect_keys(
        dataset["collection"],
        {
            "abandonment_captured",
            "consent_required_per_completed_run",
            "remote_telemetry_used",
            "test_retest_linkable",
        },
        "Calibration collection metadata",
    )
    if collection != {
        "abandonment_captured": False,
        "consent_required_per_completed_run": True,
        "remote_telemetry_used": False,
        "test_retest_linkable": True,
    }:
        raise AssessmentCalibrationAnalysisError(
            "The calibration collection boundary does not match."
        )
    privacy = _expect_keys(
        dataset["privacy"],
        {
            "classification",
            "contains_exact_timestamps",
            "contains_free_text",
            "contains_identity",
            "contains_item_responses",
            "contains_item_timing",
            "contains_pseudonymous_linkage",
            "contains_share_codes",
            "excluded",
        },
        "Calibration privacy metadata",
    )
    if privacy != {
        "classification": "sensitive_pseudonymous_assessment_data",
        "contains_exact_timestamps": False,
        "contains_free_text": False,
        "contains_identity": False,
        "contains_item_responses": True,
        "contains_item_timing": True,
        "contains_pseudonymous_linkage": True,
        "contains_share_codes": False,
        "excluded": list(EXPORT_PRIVACY_EXCLUSIONS),
    }:
        raise AssessmentCalibrationAnalysisError(
            "The calibration dataset privacy boundary does not match."
        )

    assets = load_assessment_assets()
    assessment = assets.spec["assessment"]
    core_items = assessment["core_items"]
    capability_items = assessment["adaptive_capability_clarifiers"]
    orientation_items = assessment["adaptive_orientation_clarifiers"]
    item_map = {item["id"]: item for item in core_items + capability_items + orientation_items}
    core_ids = {item["id"] for item in core_items}
    capability_ids = {item["id"] for item in capability_items}
    orientation_ids = {item["id"] for item in orientation_items}

    participants = dataset["participants"]
    if not isinstance(participants, list):
        raise AssessmentCalibrationAnalysisError("Calibration participants must be a list.")
    if (
        isinstance(dataset["participant_count"], bool)
        or not isinstance(dataset["participant_count"], int)
        or dataset["participant_count"] != len(participants)
    ):
        raise AssessmentCalibrationAnalysisError("Calibration participant count does not match.")
    refs: set[str] = set()
    actual_run_count = 0
    for participant in participants:
        participant = _expect_keys(participant, {"participant_ref", "runs"}, "Participant row")
        participant_ref = participant["participant_ref"]
        if not isinstance(participant_ref, str) or not PARTICIPANT_REF_PATTERN.fullmatch(
            participant_ref
        ):
            raise AssessmentCalibrationAnalysisError("A participant reference is malformed.")
        if participant_ref in refs:
            raise AssessmentCalibrationAnalysisError("Participant references must be unique.")
        refs.add(participant_ref)
        runs = participant["runs"]
        if not isinstance(runs, list) or not runs:
            raise AssessmentCalibrationAnalysisError(
                "Each calibration participant must contain at least one run."
            )
        previous_day = -1
        for expected_sequence, run in enumerate(runs, start=1):
            actual_run_count += 1
            run = _expect_keys(
                run,
                {
                    "assessment_version",
                    "clarifier_responses",
                    "consent_contract_version",
                    "core_responses",
                    "days_since_first_included_run",
                    "response_quality",
                    "run_sequence",
                    "source",
                    "timings_seconds",
                    "total_seconds",
                },
                "Calibration run",
            )
            if run["assessment_version"] != "1.1":
                raise AssessmentCalibrationAnalysisError(
                    "A calibration run uses an unsupported assessment version."
                )
            if run["consent_contract_version"] != ASSESSMENT_CALIBRATION_CONSENT_VERSION:
                raise AssessmentCalibrationAnalysisError(
                    "A calibration run uses an unsupported consent contract."
                )
            if run["source"] not in {"application", "share_code"}:
                raise AssessmentCalibrationAnalysisError(
                    "A calibration run uses an unsupported source."
                )
            if run["run_sequence"] != expected_sequence:
                raise AssessmentCalibrationAnalysisError(
                    "Calibration run sequence is not contiguous from one."
                )
            day = run["days_since_first_included_run"]
            if isinstance(day, bool) or not isinstance(day, int) or day < 0 or day < previous_day:
                raise AssessmentCalibrationAnalysisError("Calibration run intervals are malformed.")
            if expected_sequence == 1 and day != 0:
                raise AssessmentCalibrationAnalysisError(
                    "A participant's first calibration run must start at day zero."
                )
            previous_day = day

            core = run["core_responses"]
            clarifiers = run["clarifier_responses"]
            if not isinstance(core, dict) or set(core) != core_ids:
                raise AssessmentCalibrationAnalysisError(
                    "A calibration run does not contain the exact core-item inventory."
                )
            if not isinstance(clarifiers, dict) or not set(clarifiers).issubset(
                capability_ids | orientation_ids
            ):
                raise AssessmentCalibrationAnalysisError(
                    "A calibration run has malformed clarifier responses."
                )
            clarifier_ids = set(clarifiers)
            if len(clarifier_ids & capability_ids) > 8 or len(clarifier_ids & orientation_ids) > 2:
                raise AssessmentCalibrationAnalysisError(
                    "A calibration run exceeds the clarifier limits."
                )
            responses = {**core, **clarifiers}
            for item_id, value in responses.items():
                _validate_response(value, item_map[item_id])

            timings = run["timings_seconds"]
            if not isinstance(timings, dict) or not set(timings).issubset(responses):
                raise AssessmentCalibrationAnalysisError(
                    "A calibration run has malformed item timing."
                )
            normalized_timings = {
                item_id: _finite_number(value, "Item timing") for item_id, value in timings.items()
            }
            total_seconds = _finite_number(run["total_seconds"], "Total timing", nullable=True)
            if run["source"] == "application":
                if set(normalized_timings) != set(responses) or total_seconds is None:
                    raise AssessmentCalibrationAnalysisError(
                        "An application run is missing complete timing."
                    )
                if abs(sum(normalized_timings.values()) - total_seconds) > 0.01:
                    raise AssessmentCalibrationAnalysisError(
                        "An application run timing does not replay."
                    )

            quality = _expect_keys(
                run["response_quality"],
                {
                    "flags",
                    "median_seconds_per_item",
                    "modifier",
                    "timing_method",
                    "total_timed_seconds",
                },
                "Response-quality summary",
            )
            flags = quality["flags"]
            if (
                not isinstance(flags, list)
                or any(not isinstance(flag, str) for flag in flags)
                or flags != sorted(set(flags))
                or not set(flags).issubset(ALLOWED_RESPONSE_QUALITY_FLAGS)
            ):
                raise AssessmentCalibrationAnalysisError(
                    "A response-quality flag inventory is malformed."
                )
            modifier = _finite_number(quality["modifier"], "Response-quality modifier", maximum=1)
            quality_total = _finite_number(
                quality["total_timed_seconds"], "Response-quality total timing"
            )
            _finite_number(
                quality["median_seconds_per_item"],
                "Response-quality median timing",
                nullable=True,
            )
            if quality["timing_method"] != EXPECTED_TIMING_METHOD:
                raise AssessmentCalibrationAnalysisError(
                    "A response-quality timing method is unsupported."
                )
            if modifier is None or quality_total is None:
                raise AssessmentCalibrationAnalysisError(
                    "A response-quality summary is incomplete."
                )
            if run["source"] == "application" and abs(quality_total - total_seconds) > 0.01:
                raise AssessmentCalibrationAnalysisError(
                    "Response-quality timing does not match the application run."
                )
    if (
        isinstance(dataset["assessment_run_count"], bool)
        or not isinstance(dataset["assessment_run_count"], int)
        or dataset["assessment_run_count"] != actual_run_count
    ):
        raise AssessmentCalibrationAnalysisError("Calibration assessment-run count does not match.")
    return dataset, item_map


def _cell(count: int) -> dict[str, int | bool | None]:
    suppressed = 0 < count < SMALL_CELL_THRESHOLD
    return {"count": None if suppressed else count, "suppressed": suppressed}


def _quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return round(ordered[index], 3)


def _timing_summary(values: list[float]) -> dict[str, Any]:
    publish = len(values) >= SMALL_CELL_THRESHOLD
    return {
        "observations": _cell(len(values)),
        "median_seconds": round(median(values), 3) if publish else None,
        "p25_seconds": _quantile(values, 0.25) if publish else None,
        "p75_seconds": _quantile(values, 0.75) if publish else None,
    }


def _numeric_summary(values: list[float]) -> dict[str, Any]:
    publish = len(values) >= SMALL_CELL_THRESHOLD
    return {
        "observations": _cell(len(values)),
        "median": round(median(values), 4) if publish else None,
        "p25": _quantile(values, 0.25) if publish else None,
        "p75": _quantile(values, 0.75) if publish else None,
    }


def _validate_analysis_schema(report: dict[str, Any]) -> None:
    schema_path = settings.BASE_DIR / "contracts" / "assessment-calibration-analysis.schema.json"
    try:
        schema = json.loads(schema_path.read_text())
    except (OSError, json.JSONDecodeError):
        raise AssessmentCalibrationAnalysisError(
            "The assessment calibration analysis schema could not be loaded."
        ) from None
    errors = sorted(
        Draft202012Validator(schema).iter_errors(report), key=lambda error: list(error.path)
    )
    if errors:
        raise AssessmentCalibrationAnalysisError(
            "The assessment calibration analysis report failed schema validation."
        )


def _axis_rows(participants: int, retest_participants: int) -> list[dict[str, Any]]:
    descriptive_ready = participants >= MINIMUM_DESCRIPTIVE_PARTICIPANTS
    retest_ready = retest_participants >= MINIMUM_RETEST_PARTICIPANTS
    rows = []
    for axis_id in PARTICIPANT_EVIDENCE_AXES:
        if axis_id in {"item_response_distribution", "item_missingness_and_not_applicable"}:
            status = (
                "candidate_for_qualified_analysis"
                if descriptive_ready
                else "more_consented_data_required"
            )
            reason = (
                "The consented cohort meets the software's descriptive sample threshold."
                if descriptive_ready
                else "The consented cohort is below the descriptive sample threshold."
            )
        elif axis_id == "test_retest_reliability":
            status = (
                "candidate_for_qualified_analysis"
                if retest_ready
                else "more_consented_retests_required"
            )
            reason = (
                "The cohort meets the software's linked-retest threshold."
                if retest_ready
                else "The cohort is below the linked-retest threshold."
            )
        elif axis_id == "completion_burden_and_abandonment":
            status = "partial_input_only"
            reason = (
                "Completed-run timing is present, but the export intentionally contains no "
                "abandoned assessments."
            )
        else:
            status = "unsupported_input_required"
            reasons = {
                "convergent_and_discriminant_validity": (
                    "The export contains no consented external reference measures."
                ),
                "differential_item_functioning_and_fairness": (
                    "The export contains no consented population-group variables."
                ),
                "recommendation_fit": (
                    "The export contains no linked participant recommendation-fit judgment."
                ),
                "longitudinal_outcome_association": (
                    "The export contains no linked longitudinal outcome measure."
                ),
            }
            reason = reasons[axis_id]
        rows.append(
            {
                "axis_id": axis_id,
                "software_data_status": status,
                "reason": reason,
                "completed": False,
                "claim_status": "not_established",
            }
        )
    return rows


def build_assessment_calibration_analysis(dataset: Any) -> dict[str, Any]:
    _validate_contract()
    dataset, item_map = _validate_export(dataset)
    assets = load_assessment_assets()
    assessment = assets.spec["assessment"]
    ordered_items = (
        [(item, "core") for item in assessment["core_items"]]
        + [(item, "capability_clarifier") for item in assessment["adaptive_capability_clarifiers"]]
        + [
            (item, "orientation_clarifier")
            for item in assessment["adaptive_orientation_clarifiers"]
        ]
    )
    response_counts = {item_id: Counter() for item_id in item_map}
    timing_values: dict[str, list[float]] = {item_id: [] for item_id in item_map}
    source_counts: Counter[str] = Counter()
    total_timing_values: list[float] = []
    quality_modifiers: list[float] = []
    quality_flags: Counter[str] = Counter()
    retest_participants = 0
    consecutive_pairs = 0
    pair_values: dict[str, list[tuple[int | str, int | str]]] = {
        item["id"]: [] for item in assessment["core_items"]
    }
    for participant in dataset["participants"]:
        runs = participant["runs"]
        if len(runs) > 1:
            retest_participants += 1
        for run in runs:
            source_counts[run["source"]] += 1
            responses = {**run["core_responses"], **run["clarifier_responses"]}
            for item_id, value in responses.items():
                response_counts[item_id][str(value)] += 1
            for item_id, value in run["timings_seconds"].items():
                timing_values[item_id].append(float(value))
            if run["total_seconds"] is not None:
                total_timing_values.append(float(run["total_seconds"]))
            quality_modifiers.append(float(run["response_quality"]["modifier"]))
            quality_flags.update(run["response_quality"]["flags"])
        for previous, current in pairwise(runs):
            consecutive_pairs += 1
            for item_id in pair_values:
                pair_values[item_id].append(
                    (previous["core_responses"][item_id], current["core_responses"][item_id])
                )

    item_summaries = []
    for item, kind in ordered_items:
        item_id = item["id"]
        counts = response_counts[item_id]
        item_summaries.append(
            {
                "item_id": item_id,
                "item_kind": kind,
                "observed_responses": _cell(sum(counts.values())),
                "distribution": {
                    value: _cell(counts[value]) for value in ("1", "2", "3", "4", "5", "NA")
                },
                "timing": _timing_summary(timing_values[item_id]),
            }
        )

    publish_retest = retest_participants >= MINIMUM_RETEST_PARTICIPANTS
    retest_items = []
    if publish_retest:
        for item in assessment["core_items"]:
            item_id = item["id"]
            numeric_pairs = [
                (int(left), int(right))
                for left, right in pair_values[item_id]
                if left != "NA" and right != "NA"
            ]
            if len(numeric_pairs) < MINIMUM_RETEST_PARTICIPANTS:
                retest_items.append(
                    {
                        "item_id": item_id,
                        "paired_observations": _cell(len(numeric_pairs)),
                        "exact_agreement": None,
                        "mean_absolute_difference": None,
                    }
                )
                continue
            retest_items.append(
                {
                    "item_id": item_id,
                    "paired_observations": _cell(len(numeric_pairs)),
                    "exact_agreement": round(
                        sum(left == right for left, right in numeric_pairs) / len(numeric_pairs), 4
                    ),
                    "mean_absolute_difference": round(
                        sum(abs(left - right) for left, right in numeric_pairs)
                        / len(numeric_pairs),
                        4,
                    ),
                }
            )

    participant_count = dataset["participant_count"]
    axis_rows = _axis_rows(participant_count, retest_participants)
    content = {
        "analysis_contract_version": ASSESSMENT_CALIBRATION_ANALYSIS_VERSION,
        "analysis_schema_version": ASSESSMENT_CALIBRATION_ANALYSIS_SCHEMA_VERSION,
        "assessment_run_count": dataset["assessment_run_count"],
        "claim_boundary": ANALYSIS_CLAIM_BOUNDARY,
        "cohort_sufficiency": {
            "descriptive_threshold_met": (participant_count >= MINIMUM_DESCRIPTIVE_PARTICIPANTS),
            "minimum_descriptive_participants": MINIMUM_DESCRIPTIVE_PARTICIPANTS,
            "minimum_retest_participants": MINIMUM_RETEST_PARTICIPANTS,
            "retest_threshold_met": retest_participants >= MINIMUM_RETEST_PARTICIPANTS,
        },
        "input_dataset_sha256": dataset["dataset_sha256"],
        "input_schema_version": ASSESSMENT_CALIBRATION_EXPORT_VERSION,
        "item_summaries": item_summaries,
        "participant_count": participant_count,
        "participant_evidence": {
            "axis_rows": axis_rows,
            "completed_axes": 0,
            "open_axes": len(PARTICIPANT_EVIDENCE_AXES),
            "required_axes": len(PARTICIPANT_EVIDENCE_AXES),
        },
        "privacy": {
            "classification": "sensitive_aggregate_calibration_analysis",
            "contains_exact_timestamps": False,
            "contains_free_text": False,
            "contains_identity": False,
            "contains_item_level_rows": False,
            "contains_participant_references": False,
            "contains_raw_responses": False,
            "remote_telemetry_used": False,
            "safe_for_public_sharing": False,
            "small_cell_threshold": SMALL_CELL_THRESHOLD,
        },
        "response_quality": {
            "flag_counts": {
                flag: _cell(quality_flags[flag]) for flag in sorted(ALLOWED_RESPONSE_QUALITY_FLAGS)
            },
            "modifier": _numeric_summary(quality_modifiers),
        },
        "retest_summary": {
            "consecutive_pairs": consecutive_pairs,
            "exploratory_only": True,
            "item_agreement": retest_items,
            "participants_with_retests": retest_participants,
        },
        "source_counts": {
            source: source_counts[source] for source in ("application", "share_code")
        },
        "timing_summary": {
            "abandonment_captured": False,
            "completed_runs_only": True,
            "total_seconds": _timing_summary(total_timing_values),
        },
    }
    report = {**content, "report_sha256": calibration_hash(content)}
    _validate_analysis_schema(report)
    return report


def render_assessment_calibration_analysis(dataset: Any) -> bytes:
    return (
        canonical_calibration_json(build_assessment_calibration_analysis(dataset)) + "\n"
    ).encode("utf-8")


def build_synthetic_assessment_calibration_export() -> dict[str, Any]:
    assets = load_assessment_assets()
    assessment = assets.spec["assessment"]
    core_items = assessment["core_items"]
    clarifier_items = (
        assessment["adaptive_capability_clarifiers"][:8]
        + assessment["adaptive_orientation_clarifiers"][:2]
    )
    participants = []
    for participant_index in range(MINIMUM_RETEST_PARTICIPANTS):
        runs = []
        for run_sequence in (1, 2):
            core = {
                item["id"]: ((participant_index + item_index + run_sequence) % 5) + 1
                for item_index, item in enumerate(core_items)
            }
            clarifiers = {
                item["id"]: ((participant_index + item_index + run_sequence) % 5) + 1
                for item_index, item in enumerate(clarifier_items)
            }
            timings = dict.fromkeys(core | clarifiers, 4.0)
            total_seconds = sum(timings.values())
            runs.append(
                {
                    "assessment_version": "1.1",
                    "clarifier_responses": clarifiers,
                    "consent_contract_version": ASSESSMENT_CALIBRATION_CONSENT_VERSION,
                    "core_responses": core,
                    "days_since_first_included_run": 14 * (run_sequence - 1),
                    "response_quality": {
                        "flags": [],
                        "median_seconds_per_item": 4.0,
                        "modifier": 1.0,
                        "timing_method": EXPECTED_TIMING_METHOD,
                        "total_timed_seconds": total_seconds,
                    },
                    "run_sequence": run_sequence,
                    "source": "application",
                    "timings_seconds": timings,
                    "total_seconds": total_seconds,
                }
            )
        participants.append(
            {
                "participant_ref": f"participant-{participant_index + 1:032x}",
                "runs": runs,
            }
        )
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
            "excluded": list(EXPORT_PRIVACY_EXCLUSIONS),
        },
        "schema_version": ASSESSMENT_CALIBRATION_EXPORT_VERSION,
        "validation_status": "data_collection_required",
    }
    return {**content, "dataset_sha256": calibration_hash(content)}


def verify_assessment_calibration_analysis_readiness() -> CalibrationAnalysisReadinessSummary:
    first = build_assessment_calibration_analysis(build_synthetic_assessment_calibration_export())
    second = build_assessment_calibration_analysis(build_synthetic_assessment_calibration_export())
    if first != second:
        raise AssessmentCalibrationAnalysisError(
            "Assessment calibration analysis is not deterministic."
        )
    if first["participant_evidence"]["completed_axes"] != 0:
        raise AssessmentCalibrationAnalysisError(
            "Assessment calibration analysis completed an evidence axis."
        )
    serialized = canonical_calibration_json(first)
    if '"participant_ref":' in serialized or '"core_responses":' in serialized:
        raise AssessmentCalibrationAnalysisError(
            "Assessment calibration analysis retained raw participant rows."
        )
    return CalibrationAnalysisReadinessSummary(
        contract_version=ASSESSMENT_CALIBRATION_ANALYSIS_VERSION,
        input_schema_version=ASSESSMENT_CALIBRATION_EXPORT_VERSION,
        analysis_schema_version=ASSESSMENT_CALIBRATION_ANALYSIS_SCHEMA_VERSION,
        software_ready=True,
        synthetic_participants=first["participant_count"],
        synthetic_assessment_runs=first["assessment_run_count"],
        participant_evidence_axes_completed=0,
        database_accessed=False,
        raw_values_in_report=False,
        requires_qualified_analysis=True,
    )
