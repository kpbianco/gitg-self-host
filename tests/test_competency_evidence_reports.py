import csv
import io
import json
from pathlib import Path

import pytest
from django.core.management import call_command

from growth.services import competency_evidence_reports
from growth.services.competency_evidence_reports import (
    COMPETENCY_EVIDENCE_READINESS_CONTRACT_VERSION,
    REPORT_PATHS,
    CompetencyEvidenceReportError,
    build_competency_evidence_report_outputs,
    write_or_check_competency_evidence_reports,
)


def test_competency_evidence_reports_are_deterministic_and_current(capsys):
    first = build_competency_evidence_report_outputs()
    second = build_competency_evidence_report_outputs()

    assert first == second
    assert set(first) == set(REPORT_PATHS.values())
    readiness = json.loads(first[REPORT_PATHS["readiness"]])
    assert readiness["contract_version"] == COMPETENCY_EVIDENCE_READINESS_CONTRACT_VERSION
    assert readiness["software_ready"] is True
    assert readiness["specialist_review_complete"] is False
    assert readiness["m6b_accepted"] is False
    assert readiness["typed_production_protocols"] == 0
    assert readiness["typed_score_active_protocols"] == 0
    assert readiness["contracts"]["production_score_eligibility_fingerprint"] == (
        "f7639a0c623f1baac9469f34fe49ca9e2eb0be8fc1c616ab662996b2e90bf2bf"
    )
    assert readiness["catalog"] == {
        "canonical_protocol_packages": 5,
        "competencies": 383,
        "practice_actions": 15,
        "score_active_protocols": 1,
        "uncovered_competencies": 378,
    }
    assert readiness["governance"]["expert_review"]["review_id"] == "ER-M6A-003"
    assert readiness["governance"]["expert_review"]["status"] == "pending"
    assert readiness["governance"]["research_gap"]["gap_id"] == "RG-M6A-002"
    assert readiness["governance"]["research_gap"]["status"] == "open"

    capability_rows = list(
        csv.DictReader(io.StringIO(first[REPORT_PATHS["typed_capability"]].decode()))
    )
    assert len(capability_rows) == 10
    assert {row["measurement_kind"] for row in capability_rows} == {
        "artifact",
        "attestation",
        "boolean",
        "bounded_frequency",
        "conceptual",
        "count",
        "duration",
        "objective",
        "ordinal",
        "scenario",
    }
    assert {row["typed_production_protocols"] for row in capability_rows} == {"0"}
    assert {row["typed_score_active_protocols"] for row in capability_rows} == {"0"}

    policy_rows = list(csv.DictReader(io.StringIO(first[REPORT_PATHS["scoring_policy"]].decode())))
    assert len(policy_rows) == 6
    assert {row["synthetic_execution"] for row in policy_rows} == {"passed"}
    assert {row["typed_execution_boundary"] for row in policy_rows} == {"pure_shadow_only"}
    assert {
        row["policy_id"] for row in policy_rows if row["production_status"] == "legacy_v1_only"
    } == {"SP-SELF-REPORT-ELIGIBLE"}

    assert write_or_check_competency_evidence_reports(check=True) == ()
    call_command("generate_competency_evidence_reports", "--check")
    assert "Competency-evidence reports are current." in capsys.readouterr().out


def test_report_writer_detects_missing_and_stale_bytes(
    tmp_path: Path,
    monkeypatch,
):
    expected_path = Path("reports/practice-content/example.csv")

    def outputs(_base_dir):
        return {expected_path: b"header\nvalue\n"}

    monkeypatch.setattr(
        competency_evidence_reports,
        "build_competency_evidence_report_outputs",
        outputs,
    )
    assert write_or_check_competency_evidence_reports(
        base_dir=tmp_path,
        check=False,
    ) == (expected_path,)
    assert (
        write_or_check_competency_evidence_reports(
            base_dir=tmp_path,
            check=True,
        )
        == ()
    )

    (tmp_path / expected_path).write_bytes(b"stale\n")
    with pytest.raises(
        CompetencyEvidenceReportError,
        match="missing or stale",
    ):
        write_or_check_competency_evidence_reports(
            base_dir=tmp_path,
            check=True,
        )
