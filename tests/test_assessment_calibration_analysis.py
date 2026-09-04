from __future__ import annotations

import json
import stat
from copy import deepcopy
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from growth.domain.assessment_calibration import calibration_hash, canonical_calibration_json
from growth.services.assessment import persist_assessment_run
from growth.services.assessment_calibration import (
    build_assessment_calibration_export,
    record_assessment_calibration_consent,
)
from growth.services.assessment_calibration_analysis import (
    ASSESSMENT_CALIBRATION_ANALYSIS_SCHEMA_VERSION,
    ASSESSMENT_CALIBRATION_ANALYSIS_VERSION,
    PARTICIPANT_EVIDENCE_AXES,
    AssessmentCalibrationAnalysisError,
    build_assessment_calibration_analysis,
    build_synthetic_assessment_calibration_export,
    verify_assessment_calibration_analysis_readiness,
)
from tests.test_assessment_integration import golden_payload


def _rehash(dataset):
    content = {key: value for key, value in dataset.items() if key != "dataset_sha256"}
    dataset["dataset_sha256"] = calibration_hash(content)
    return dataset


def _small_dataset(participants=4):
    dataset = deepcopy(build_synthetic_assessment_calibration_export())
    dataset["participants"] = dataset["participants"][:participants]
    dataset["participant_count"] = participants
    dataset["assessment_run_count"] = sum(
        len(participant["runs"]) for participant in dataset["participants"]
    )
    return _rehash(dataset)


def test_analysis_is_deterministic_aggregate_schema_valid_and_zero_claim():
    dataset = build_synthetic_assessment_calibration_export()

    first = build_assessment_calibration_analysis(dataset)

    assert first == build_assessment_calibration_analysis(dataset)
    assert first["analysis_contract_version"] == ASSESSMENT_CALIBRATION_ANALYSIS_VERSION
    assert first["analysis_schema_version"] == ASSESSMENT_CALIBRATION_ANALYSIS_SCHEMA_VERSION
    assert first["participant_count"] == 30
    assert first["assessment_run_count"] == 60
    assert len(first["item_summaries"]) == 93
    assert len(first["retest_summary"]["item_agreement"]) == 50
    assert first["participant_evidence"]["completed_axes"] == 0
    assert {row["axis_id"] for row in first["participant_evidence"]["axis_rows"]} == set(
        PARTICIPANT_EVIDENCE_AXES
    )
    assert all(not row["completed"] for row in first["participant_evidence"]["axis_rows"])
    content = {key: value for key, value in first.items() if key != "report_sha256"}
    assert first["report_sha256"] == calibration_hash(content)
    serialized = canonical_calibration_json(first)
    assert '"participant_ref":' not in serialized
    assert '"core_responses":' not in serialized
    assert dataset["participants"][0]["participant_ref"] not in serialized
    assert first["privacy"] == {
        "classification": "sensitive_aggregate_calibration_analysis",
        "contains_exact_timestamps": False,
        "contains_free_text": False,
        "contains_identity": False,
        "contains_item_level_rows": False,
        "contains_participant_references": False,
        "contains_raw_responses": False,
        "remote_telemetry_used": False,
        "safe_for_public_sharing": False,
        "small_cell_threshold": 5,
    }


def test_small_cells_are_suppressed_and_insufficient_cohort_stays_open():
    report = build_assessment_calibration_analysis(_small_dataset())

    assert report["cohort_sufficiency"] == {
        "descriptive_threshold_met": False,
        "minimum_descriptive_participants": 30,
        "minimum_retest_participants": 30,
        "retest_threshold_met": False,
    }
    assert report["retest_summary"]["participants_with_retests"] == 4
    assert report["retest_summary"]["item_agreement"] == []
    first_item = report["item_summaries"][0]
    assert any(
        cell["count"] is None and cell["suppressed"] for cell in first_item["distribution"].values()
    )
    axis_rows = {row["axis_id"]: row for row in report["participant_evidence"]["axis_rows"]}
    assert (
        axis_rows["item_response_distribution"]["software_data_status"]
        == "more_consented_data_required"
    )
    assert (
        axis_rows["test_retest_reliability"]["software_data_status"]
        == "more_consented_retests_required"
    )
    assert (
        axis_rows["completion_burden_and_abandonment"]["software_data_status"]
        == "partial_input_only"
    )
    assert (
        axis_rows["differential_item_functioning_and_fairness"]["software_data_status"]
        == "unsupported_input_required"
    )


@pytest.mark.parametrize(
    "mutation, expected",
    [
        (lambda value: value.update({"identity": "forbidden"}), "exact allowlist"),
        (
            lambda value: value["participants"][0].update(
                {"participant_ref": "participant-not-a-token"}
            ),
            "reference is malformed",
        ),
        (
            lambda value: value["participants"][0]["runs"][0]["core_responses"].update({"Q01": 9}),
            "outside the supported scale",
        ),
        (
            lambda value: value["participants"][0]["runs"][0].update({"run_sequence": 4}),
            "not contiguous",
        ),
        (
            lambda value: value["privacy"].update({"contains_identity": True}),
            "privacy boundary",
        ),
    ],
)
def test_analysis_fails_closed_on_allowlist_and_structural_drift(mutation, expected):
    dataset = _small_dataset()
    mutation(dataset)
    _rehash(dataset)

    with pytest.raises(AssessmentCalibrationAnalysisError, match=expected):
        build_assessment_calibration_analysis(dataset)


def test_analysis_fails_closed_on_dataset_hash_drift():
    dataset = _small_dataset()
    dataset["dataset_sha256"] = "0" * 64

    with pytest.raises(AssessmentCalibrationAnalysisError, match="hash"):
        build_assessment_calibration_analysis(dataset)


@pytest.mark.django_db
def test_m6i04_export_is_accepted_without_database_reads_during_analysis(
    user, seeded, django_assert_num_queries
):
    run, created = persist_assessment_run(user, golden_payload(source="application"))
    assert created is True
    record_assessment_calibration_consent(user=user, assessment_run=run, state="consented")
    dataset = build_assessment_calibration_export(users=[user])

    with django_assert_num_queries(0):
        report = build_assessment_calibration_analysis(dataset)

    assert report["participant_count"] == 1
    assert report["assessment_run_count"] == 1
    assert report["participant_evidence"]["completed_axes"] == 0


def test_operator_command_requires_confirmation_refuses_overwrite_and_uses_0600(tmp_path):
    input_path = tmp_path / "calibration.json"
    output_path = tmp_path / "analysis.json"
    input_path.write_text(
        json.dumps(build_synthetic_assessment_calibration_export()), encoding="utf-8"
    )

    with pytest.raises(CommandError, match="confirm-sensitive-input"):
        call_command(
            "analyze_assessment_calibration_dataset",
            input=input_path,
            output=output_path,
        )
    stdout = StringIO()
    call_command(
        "analyze_assessment_calibration_dataset",
        input=input_path,
        output=output_path,
        confirm_sensitive_input=True,
        stdout=stdout,
    )
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["participant_evidence"]["completed_axes"] == 0
    assert stat.S_IMODE(output_path.stat().st_mode) == 0o600
    assert "zero evidence axes completed" in stdout.getvalue()
    with pytest.raises(CommandError, match="overwrite"):
        call_command(
            "analyze_assessment_calibration_dataset",
            input=input_path,
            output=output_path,
            confirm_sensitive_input=True,
        )


def test_operator_command_rejects_duplicate_json_keys_without_output(tmp_path):
    input_path = tmp_path / "duplicate.json"
    output_path = tmp_path / "analysis.json"
    content = json.dumps(build_synthetic_assessment_calibration_export())
    input_path.write_text(
        content.replace(
            '"schema_version":',
            '"schema_version":"grounded-growth-assessment-calibration-export-v1","schema_version":',
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(CommandError, match="duplicate object key"):
        call_command(
            "analyze_assessment_calibration_dataset",
            input=input_path,
            output=output_path,
            confirm_sensitive_input=True,
        )

    assert not output_path.exists()


@pytest.mark.django_db
def test_readiness_is_deterministic_database_free_and_privacy_safe(django_assert_num_queries):
    with django_assert_num_queries(0):
        first = verify_assessment_calibration_analysis_readiness()
        second = verify_assessment_calibration_analysis_readiness()

    assert first == second
    assert first.software_ready is True
    assert first.synthetic_participants == 30
    assert first.synthetic_assessment_runs == 60
    assert first.participant_evidence_axes_completed == 0
    assert first.database_accessed is False
    assert first.raw_values_in_report is False
    assert first.requires_qualified_analysis is True
