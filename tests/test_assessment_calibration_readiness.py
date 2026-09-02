from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/assessment_calibration_readiness.py"
REPORT_PATH = ROOT / "reports/assessment-calibration/assessment_calibration_readiness_v1.json"
PACKET_PATH = ROOT / "reports/assessment-calibration/assessment_calibration_readiness_v1.md"
SCHEMA_PATH = ROOT / "contracts/assessment-calibration-readiness.schema.json"
BUNDLE = ROOT / "data/assessment/v1.1_bundle/grounded_growth_assessment_v1_1"


def _load_generator():
    spec = importlib.util.spec_from_file_location("assessment_calibration_readiness", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def report() -> dict:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def _copy_inputs(destination: Path) -> None:
    (destination / "contracts").mkdir(parents=True)
    shutil.copy2(
        ROOT / "contracts/assessment-calibration-readiness.yaml",
        destination / "contracts/assessment-calibration-readiness.yaml",
    )
    shutil.copy2(
        ROOT / "contracts/assessment-calibration-readiness.schema.json",
        destination / "contracts/assessment-calibration-readiness.schema.json",
    )
    target = destination / "data/assessment/v1.1_bundle/grounded_growth_assessment_v1_1"
    target.parent.mkdir(parents=True)
    shutil.copytree(BUNDLE, target)


def test_report_schema_inventory_and_exact_source_hashes(report):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(report)
    assert report["inventory"] == {
        "capability_clarifiers": 37,
        "capability_core_items": 37,
        "core_items": 50,
        "lever_families": 7,
        "levers": 37,
        "orientation_clarifiers": 6,
        "orientation_core_items": 12,
        "orientations": 6,
        "response_quality_core_items": 1,
        "unique_item_ids": True,
    }
    expected_paths = {
        "assessment_spec": BUNDLE / "assessment_spec_v1_1.json",
        "assessment_model": BUNDLE / "grounded_growth_model_v1.json",
        "assessment_scorer": BUNDLE / "assessment_scoring_v1_1.js",
        "assessment_coverage": BUNDLE / "assessment_coverage_v1_1.csv",
    }
    assert report["source_hashes"] == {
        key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in expected_paths.items()
    }


def test_all_37_levers_have_direct_clarifier_and_frozen_coverage_parity(report):
    coverage = report["coverage"]
    rows = coverage["lever_rows"]
    assert coverage | {"lever_rows": rows} == {
        "direct_capability_coverage_complete": True,
        "capability_clarifier_coverage_complete": True,
        "coverage_artifact_matches": True,
        "positive_scoring_weights": True,
        "valid_references": True,
        "lever_rows": rows,
    }
    assert [row["lever_id"] for row in rows] == [f"L{index:02d}" for index in range(1, 38)]
    assert all(len(row["direct_core_item_ids"]) == 1 for row in rows)
    assert all(row["capability_clarifier_id"] == f"C_{row['lever_id']}" for row in rows)
    assert all(row["all_core_signal_ids"] for row in rows)
    assert all(row["core_weight_sum"] > 0 for row in rows)
    assert all(row["effective_core_item_count"] > 0 for row in rows)
    assert all(row["allows_not_applicable"] is True for row in rows)


def test_participant_axes_remain_explicitly_open_and_claims_blocked(report):
    evidence = report["participant_evidence"]
    assert evidence["required_axes"] == evidence["open_axes"] == 8
    assert evidence["completed_axes"] == 0
    assert len({row["axis_id"] for row in evidence["axis_rows"]}) == 8
    assert {row["status"] for row in evidence["axis_rows"]} == {"data_collection_required"}
    assert report["validation_state"] == {
        "calibration_status": "data_collection_required",
        "golden_replay_required": True,
        "participant_validation": False,
        "psychometric_validation": False,
        "release_authorized": False,
        "structural_readiness": "pass",
    }
    assert "not psychometric calibration" in report["claim_boundary"]


def test_reports_are_source_only_private_and_byte_stable(report):
    assert report["privacy"] == {
        "assessment_run_data_read": False,
        "database_read": False,
        "database_write": False,
        "owner_private_data_read": False,
        "participant_data_read": False,
        "private_values_in_report": False,
        "source_only": True,
    }
    generator = _load_generator()
    assert generator.build_outputs(ROOT) == generator.build_outputs(ROOT)
    for relative, expected in generator.build_outputs(ROOT).items():
        assert (ROOT / relative).read_bytes() == expected
    packet = PACKET_PATH.read_text(encoding="utf-8")
    assert "all eight evidence axes require consented data collection" in packet
    assert "does not open the application database" in packet


def test_generator_fails_closed_on_duplicate_ids_unknown_references_and_stale_reports(
    tmp_path,
):
    generator = _load_generator()
    duplicate_root = tmp_path / "duplicate"
    _copy_inputs(duplicate_root)
    duplicate_spec_path = duplicate_root / generator.SPEC_PATH
    duplicate_spec = json.loads(duplicate_spec_path.read_text(encoding="utf-8"))
    duplicate_spec["assessment"]["adaptive_orientation_clarifiers"][0]["id"] = "Q01"
    duplicate_spec_path.write_text(json.dumps(duplicate_spec), encoding="utf-8")
    with pytest.raises(generator.AssessmentCalibrationReadinessError, match="globally unique"):
        generator.build_assessment_calibration_readiness(duplicate_root)

    reference_root = tmp_path / "reference"
    _copy_inputs(reference_root)
    reference_spec_path = reference_root / generator.SPEC_PATH
    reference_spec = json.loads(reference_spec_path.read_text(encoding="utf-8"))
    reference_spec["assessment"]["core_items"][12]["lever_weights"]["L99"] = 0.2
    reference_spec_path.write_text(json.dumps(reference_spec), encoding="utf-8")
    with pytest.raises(generator.AssessmentCalibrationReadinessError, match="unknown lever"):
        generator.build_assessment_calibration_readiness(reference_root)

    stale_root = tmp_path / "stale"
    _copy_inputs(stale_root)
    with pytest.raises(generator.AssessmentCalibrationReadinessError, match="missing or stale"):
        generator.write_or_check(base_dir=stale_root, check=True)


def test_readiness_is_wired_into_make_local_full_and_hosted_ci():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    commands = (ROOT / "contracts/verification.commands").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/verification.yml").read_text(encoding="utf-8")
    assert "assessment-calibration-check:" in makefile
    assert "scripts/assessment_calibration_readiness.py --check" in makefile
    assert "scripts/verify_assessment_golden.js" in makefile
    assert "make assessment-calibration-check PYTHON=.venv/bin/python" in commands
    assert "make assessment-calibration-check PYTHON=python" in workflow
