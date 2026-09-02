#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUNDLE = Path("data/assessment/v1.1_bundle/grounded_growth_assessment_v1_1")
SPEC_PATH = BUNDLE / "assessment_spec_v1_1.json"
MODEL_PATH = BUNDLE / "grounded_growth_model_v1.json"
SCORER_PATH = BUNDLE / "assessment_scoring_v1_1.js"
COVERAGE_PATH = BUNDLE / "assessment_coverage_v1_1.csv"
CONTRACT_PATH = Path("contracts/assessment-calibration-readiness.yaml")
SCHEMA_PATH = Path("contracts/assessment-calibration-readiness.schema.json")
REPORT_ROOT = Path("reports/assessment-calibration")
JSON_REPORT_PATH = REPORT_ROOT / "assessment_calibration_readiness_v1.json"
MARKDOWN_REPORT_PATH = REPORT_ROOT / "assessment_calibration_readiness_v1.md"
CONTRACT_VERSION = "GG-ASSESSMENT-CALIBRATION-READINESS-1.0"

AXIS_DETAILS = {
    "item_response_distribution": (
        "A consented multi-participant cohort with per-item response frequencies and enough "
        "observations to detect floor, ceiling, and sparse-category behavior.",
        "item calibration",
    ),
    "item_missingness_and_not_applicable": (
        "Consented completion records that distinguish skipped, explicit not-applicable, and "
        "answered items across relevant roles and pathways.",
        "missingness and applicability validity",
    ),
    "test_retest_reliability": (
        "Paired assessment administrations from the same consenting participants at a "
        "predeclared interval with stable matching and attrition accounting.",
        "temporal reliability",
    ),
    "convergent_and_discriminant_validity": (
        "Consented comparison measures selected and interpreted by a qualified measurement "
        "specialist before examining outcome correlations.",
        "construct validity",
    ),
    "differential_item_functioning_and_fairness": (
        "A sufficiently diverse consented cohort, protected-attribute governance, subgroup "
        "power analysis, and specialist-reviewed fairness methods.",
        "cross-population fairness",
    ),
    "completion_burden_and_abandonment": (
        "Consented pilot completion, abandonment, estimated burden, accessibility-friction, "
        "and missing-data records collected without covert telemetry.",
        "assessment burden and accessibility",
    ),
    "recommendation_fit": (
        "Consented participant ratings and qualitative review of whether initial recommended "
        "practices were understandable, applicable, safe, and useful.",
        "recommendation-fit validity",
    ),
    "longitudinal_outcome_association": (
        "Multi-cycle consented follow-up with predeclared outcomes, attrition handling, adverse "
        "event review, and no completion-equals-mastery assumption.",
        "longitudinal and intervention-effectiveness claims",
    ),
}


class AssessmentCalibrationReadinessError(ValueError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _rounded(value: Decimal, places: str) -> Decimal:
    return value.quantize(Decimal(places))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssessmentCalibrationReadinessError(message)


def _load_coverage(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    _require(len(rows) == 37, f"assessment coverage must contain 37 rows; found {len(rows)}")
    indexed = {row["lever_id"]: row for row in rows}
    _require(len(indexed) == len(rows), "assessment coverage contains duplicate lever IDs")
    return indexed


def _validate_item_references(
    *,
    core_items: list[dict[str, Any]],
    capability_clarifiers: list[dict[str, Any]],
    orientation_clarifiers: list[dict[str, Any]],
    lever_ids: set[str],
    orientation_slugs: set[str],
) -> bool:
    all_items = core_items + capability_clarifiers + orientation_clarifiers
    item_ids = [item.get("id") for item in all_items]
    _require(all(isinstance(item_id, str) and item_id for item_id in item_ids), "item ID missing")
    _require(len(item_ids) == len(set(item_ids)), "assessment item IDs must be globally unique")

    for item in all_items:
        lever_weights = item.get("lever_weights", {})
        orientation_weights = item.get("orientation_weights", {})
        _require(
            set(lever_weights) <= lever_ids,
            f"{item['id']} references an unknown lever ID",
        )
        _require(
            set(orientation_weights) <= orientation_slugs,
            f"{item['id']} references an unknown orientation slug",
        )
        _require(
            all(_decimal(weight) > 0 for weight in lever_weights.values()),
            f"{item['id']} contains a non-positive lever weight",
        )
        _require(
            all(_decimal(weight) > 0 for weight in orientation_weights.values()),
            f"{item['id']} contains a non-positive orientation weight",
        )
        primary = item.get("primary_lever_id")
        if primary is not None:
            _require(primary in lever_ids, f"{item['id']} has an unknown primary lever")
            _require(primary in lever_weights, f"{item['id']} primary lever has no weight")
    return True


def _lever_rows(
    assessment: dict[str, Any], coverage_rows: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    core_capability = [item for item in assessment["core_items"] if item["type"] == "capability"]
    clarifiers = assessment["adaptive_capability_clarifiers"]
    lever_catalog = {lever["id"]: lever for lever in assessment["lever_catalog"]}
    rows: list[dict[str, Any]] = []

    for lever_id in sorted(lever_catalog):
        lever = lever_catalog[lever_id]
        direct = sorted(
            item["id"] for item in core_capability if item.get("primary_lever_id") == lever_id
        )
        signals = sorted(
            item["id"] for item in core_capability if lever_id in item.get("lever_weights", {})
        )
        lever_clarifiers = sorted(
            item["id"] for item in clarifiers if item.get("primary_lever_id") == lever_id
        )
        _require(len(direct) == 1, f"{lever_id} must have exactly one direct core capability item")
        _require(
            len(lever_clarifiers) == 1,
            f"{lever_id} must have exactly one adaptive capability clarifier",
        )

        weights = [
            _decimal(item["lever_weights"][lever_id])
            for item in core_capability
            if lever_id in item.get("lever_weights", {})
        ]
        weight_sum = sum(weights, Decimal(0))
        effective_count = (weight_sum * weight_sum) / sum(
            (weight * weight for weight in weights), Decimal(0)
        )
        frozen = coverage_rows.get(lever_id)
        _require(frozen is not None, f"assessment coverage is missing {lever_id}")
        comparisons = {
            "lever name": frozen["lever_name"] == lever["name"],
            "direct core count": int(frozen["direct_core_items"]) == len(direct),
            "all core signal count": int(frozen["all_core_signals"]) == len(signals),
            "core weight sum": _decimal(frozen["core_weight_sum"]) == _rounded(weight_sum, "0.001"),
            "effective item count": _decimal(frozen["effective_core_item_count"])
            == _rounded(effective_count, "0.001"),
            "clarifier availability": frozen["clarifier_available"] == "yes",
            "mapped competency count": int(frozen["mapped_competencies"])
            == int(lever["mapped_competency_count"]),
            "task weight denominator": _decimal(frozen["task_weight_denominator"])
            == _rounded(_decimal(lever["task_weight_denominator"]), "0.001"),
        }
        mismatches = [label for label, matches in comparisons.items() if not matches]
        _require(not mismatches, f"{lever_id} coverage mismatch: {', '.join(mismatches)}")

        direct_item = next(item for item in core_capability if item["id"] == direct[0])
        clarifier = next(item for item in clarifiers if item["id"] == lever_clarifiers[0])
        rows.append(
            {
                "lever_id": lever_id,
                "direct_core_item_ids": direct,
                "all_core_signal_ids": signals,
                "capability_clarifier_id": lever_clarifiers[0],
                "core_weight_sum": float(_rounded(weight_sum, "0.001")),
                "effective_core_item_count": float(_rounded(effective_count, "0.001")),
                "allows_not_applicable": bool(
                    direct_item.get("allow_not_applicable")
                    and clarifier.get("allow_not_applicable")
                ),
            }
        )
    return rows


def build_assessment_calibration_readiness(base_dir: Path = PROJECT_ROOT) -> dict[str, Any]:
    contract = yaml.safe_load((base_dir / CONTRACT_PATH).read_text(encoding="utf-8"))
    _require(contract["contract_version"] == CONTRACT_VERSION, "contract version mismatch")
    spec = json.loads((base_dir / SPEC_PATH).read_text(encoding="utf-8"))
    assessment = spec["assessment"]
    core_items = assessment["core_items"]
    capability_clarifiers = assessment["adaptive_capability_clarifiers"]
    orientation_clarifiers = assessment["adaptive_orientation_clarifiers"]
    lever_ids = {lever["id"] for lever in assessment["lever_catalog"]}
    orientation_slugs = {orientation["slug"] for orientation in assessment["orientation_catalog"]}
    family_slugs = {family["slug"] for family in assessment["lever_families"]}

    counts = Counter(item["type"] for item in core_items)
    expected = contract["structural_expectations"]
    actual_counts = {
        "core_items": len(core_items),
        "capability_core_items": counts["capability"],
        "orientation_core_items": counts["orientation"],
        "response_quality_core_items": counts["response_quality"],
        "capability_clarifiers": len(capability_clarifiers),
        "orientation_clarifiers": len(orientation_clarifiers),
        "levers": len(lever_ids),
        "lever_families": len(family_slugs),
        "orientations": len(orientation_slugs),
    }
    for key, expected_count in expected.items():
        if key in actual_counts:
            _require(
                actual_counts[key] == expected_count,
                f"{key} must be {expected_count}; found {actual_counts[key]}",
            )

    family_levers = [
        lever_id for family in assessment["lever_families"] for lever_id in family["lever_ids"]
    ]
    _require(set(family_levers) == lever_ids, "lever-family membership must cover all levers")
    _require(len(family_levers) == len(set(family_levers)), "a lever belongs to multiple families")
    _require(
        all(lever["family"] in family_slugs for lever in assessment["lever_catalog"]),
        "lever catalog contains an unknown family slug",
    )
    valid_references = _validate_item_references(
        core_items=core_items,
        capability_clarifiers=capability_clarifiers,
        orientation_clarifiers=orientation_clarifiers,
        lever_ids=lever_ids,
        orientation_slugs=orientation_slugs,
    )
    coverage_rows = _load_coverage(base_dir / COVERAGE_PATH)
    lever_rows = _lever_rows(assessment, coverage_rows)

    axis_ids = contract["participant_evidence_axes"]
    _require(axis_ids == list(AXIS_DETAILS), "participant evidence axis order or inventory drifted")
    axis_rows = [
        {
            "axis_id": axis_id,
            "status": "data_collection_required",
            "required_evidence": AXIS_DETAILS[axis_id][0],
            "claim_blocked": AXIS_DETAILS[axis_id][1],
        }
        for axis_id in axis_ids
    ]

    all_items = core_items + capability_clarifiers + orientation_clarifiers
    report = {
        "contract_version": CONTRACT_VERSION,
        "assessment_version": assessment["version"],
        "source_hashes": {
            "assessment_spec": _sha256(base_dir / SPEC_PATH),
            "assessment_model": _sha256(base_dir / MODEL_PATH),
            "assessment_scorer": _sha256(base_dir / SCORER_PATH),
            "assessment_coverage": _sha256(base_dir / COVERAGE_PATH),
        },
        "inventory": {
            **actual_counts,
            "unique_item_ids": len({item["id"] for item in all_items}) == len(all_items),
        },
        "coverage": {
            "direct_capability_coverage_complete": all(
                len(row["direct_core_item_ids"]) == 1 for row in lever_rows
            ),
            "capability_clarifier_coverage_complete": all(
                row["capability_clarifier_id"] for row in lever_rows
            ),
            "coverage_artifact_matches": True,
            "positive_scoring_weights": True,
            "valid_references": valid_references,
            "lever_rows": lever_rows,
        },
        "participant_evidence": {
            "required_axes": len(axis_rows),
            "completed_axes": 0,
            "open_axes": len(axis_rows),
            "axis_rows": axis_rows,
        },
        "validation_state": {
            "structural_readiness": "pass",
            "golden_replay_required": True,
            "calibration_status": "data_collection_required",
            "psychometric_validation": False,
            "participant_validation": False,
            "release_authorized": False,
        },
        "privacy": {
            "source_only": True,
            "database_read": False,
            "database_write": False,
            "assessment_run_data_read": False,
            "participant_data_read": False,
            "owner_private_data_read": False,
            "private_values_in_report": False,
        },
        "claim_boundary": (
            "Deterministic source-only structural and scorer readiness for assessment v1.1; "
            "this report is not psychometric calibration, clinical or cultural validation, "
            "accessibility-population or fairness evidence, participant or longitudinal "
            "validation, release authorization, mastery evidence, or intervention-effectiveness "
            "evidence. All eight participant evidence axes remain open."
        ),
    }
    schema = json.loads((base_dir / SCHEMA_PATH).read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(report), key=lambda error: list(error.path)
    )
    if errors:
        rendered = "; ".join(f"{list(error.path)}: {error.message}" for error in errors[:10])
        raise AssessmentCalibrationReadinessError(f"generated report violates schema: {rendered}")
    return report


def _markdown_bytes(report: dict[str, Any]) -> bytes:
    inventory = report["inventory"]
    lines = [
        "# Assessment calibration readiness v1",
        "",
        "## Outcome",
        "",
        (
            "Assessment v1.1 is structurally complete and its frozen coverage artifact is "
            "internally consistent. Psychometric and participant calibration are not complete; "
            "all eight evidence axes require consented data collection and qualified analysis."
        ),
        "",
        "## Frozen inventory",
        "",
        "| Item | Count |",
        "| --- | ---: |",
        f"| Core items | {inventory['core_items']} |",
        f"| Capability core items | {inventory['capability_core_items']} |",
        f"| Orientation core items | {inventory['orientation_core_items']} |",
        f"| Response-quality core items | {inventory['response_quality_core_items']} |",
        f"| Capability clarifiers | {inventory['capability_clarifiers']} |",
        f"| Orientation clarifiers | {inventory['orientation_clarifiers']} |",
        (
            "| Levers / families / orientations | "
            f"{inventory['levers']} / {inventory['lever_families']} / "
            f"{inventory['orientations']} |"
        ),
        "",
        (
            "Every lever has exactly one direct core item and one adaptive capability clarifier. "
            "Recomputed signal counts, weight sums, effective item counts, mapped-competency "
            "counts, and task-weight denominators match all 37 frozen coverage rows."
        ),
        "",
        "## Participant evidence still required",
        "",
        "| Axis | Status | Blocked claim |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        f"| `{row['axis_id']}` | data collection required | {row['claim_blocked']} |"
        for row in report["participant_evidence"]["axis_rows"]
    )
    lines.extend(
        [
            "",
            "## Privacy and claim boundary",
            "",
            (
                "The generator reads only committed assessment source artifacts. It does not "
                "open the application database or read assessment runs, participant data, "
                "owner-private data, evidence, scores, context, Personal OS, or pilot feedback."
            ),
            "",
            report["claim_boundary"],
            "",
        ]
    )
    return "\n".join(lines).encode()


def build_outputs(base_dir: Path = PROJECT_ROOT) -> dict[Path, bytes]:
    report = build_assessment_calibration_readiness(base_dir)
    return {
        JSON_REPORT_PATH: _json_bytes(report),
        MARKDOWN_REPORT_PATH: _markdown_bytes(report),
    }


def write_or_check(*, base_dir: Path, check: bool) -> tuple[Path, ...]:
    changed: list[Path] = []
    for relative, expected in build_outputs(base_dir).items():
        path = base_dir / relative
        actual = path.read_bytes() if path.exists() else None
        if actual == expected:
            continue
        changed.append(relative)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
    if check and changed:
        raise AssessmentCalibrationReadinessError(
            "assessment-calibration reports are missing or stale: "
            + ", ".join(path.as_posix() for path in changed)
        )
    return tuple(changed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify the source-only assessment calibration readiness report."
    )
    parser.add_argument("--check", action="store_true", help="Fail when reports are stale.")
    parser.add_argument("--base-dir", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)
    try:
        changed = write_or_check(base_dir=args.base_dir.resolve(), check=args.check)
    except (AssessmentCalibrationReadinessError, OSError, ValueError) as exc:
        print(f"assessment_calibration_readiness=failed reason={exc}", file=sys.stderr)
        return 1
    mode = "verified" if args.check else "generated"
    print(
        "assessment_calibration_readiness="
        f"{mode} changed={len(changed)} participant_axes_completed=0 participant_axes_open=8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
