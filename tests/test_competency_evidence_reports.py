import csv
import io
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from django.core.management import call_command

from growth.domain.practice_content import load_practice_content_bundle
from growth.domain.typed_evidence import load_typed_evidence_spec
from growth.services import competency_evidence_reports
from growth.services.competency_evidence_reports import (
    COMPETENCY_EVIDENCE_READINESS_CONTRACT_VERSION,
    REPORT_PATHS,
    CompetencyEvidenceReportError,
    build_competency_evidence_report_outputs,
    write_or_check_competency_evidence_reports,
)
from growth.services.scoring import PRODUCTION_SCORE_MAPPING_FINGERPRINT


def test_competency_evidence_reports_are_deterministic_and_current(capsys):
    first = build_competency_evidence_report_outputs()
    second = build_competency_evidence_report_outputs()

    assert first == second
    assert set(first) == set(REPORT_PATHS.values())
    readiness = json.loads(first[REPORT_PATHS["readiness"]])
    assert readiness["contract_version"] == COMPETENCY_EVIDENCE_READINESS_CONTRACT_VERSION
    assert readiness["software_ready"] is True
    assert (
        readiness["contracts"]["production_score_eligibility_fingerprint"]
        == PRODUCTION_SCORE_MAPPING_FINGERPRINT
    )
    catalog = load_practice_content_bundle(Path(__file__).resolve().parents[1])
    assert readiness["catalog"] == {
        "canonical_protocol_packages": len(catalog.protocols),
        "competencies": 383,
        "practice_actions": sum(
            len(protocol["intervention"]["actions"]) for protocol in catalog.protocols
        ),
        "score_active_protocols": 383,
        "uncovered_competencies": 383 - len(catalog.protocols),
    }
    assert readiness["source_typed_protocols"] == 378
    assert readiness["typed_production_protocols"] == 378
    assert readiness["typed_score_active_protocols"] == 378
    assert readiness["governance"]["expert_review"]["review_id"] == "ER-M6A-003"
    assert (
        readiness["governance"]["expert_review"]["status"]
        == catalog.expert_reviews["ER-M6A-003"]["status"]
    )
    assert readiness["governance"]["research_gap"]["gap_id"] == "RG-M6A-002"
    assert (
        readiness["governance"]["research_gap"]["status"]
        == catalog.research_gaps["RG-M6A-002"]["status"]
    )

    m6d = json.loads(first[REPORT_PATHS["m6d_readiness"]])
    assert m6d["contract_version"] == "GG-M6D-01-AUTHORING-READINESS-1.0"
    assert [row["competency_id"] for row in m6d["cohort"]] == [
        "08.06",
        "09.12",
        "10.02",
        "13.02",
    ]
    assert [row["action_count"] for row in m6d["cohort"]] == [3, 3, 4, 4]
    assert {
        row["protocol_stable_id"]: (
            row["protocol_family_id"],
            row["recommendation_target_lever_ids"],
        )
        for row in m6d["cohort"]
    } == {
        "PRACTICE-MOTIVATION-INDEPENDENT-START-01": (
            "PF-BEHAVIORAL-EXPERIMENT",
            ["L10"],
        ),
        "PRACTICE-DECISION-RECORD-01": ("PF-ARTIFACT-PLAN", ["L14"]),
        "PRACTICE-DELIBERATE-PRACTICE-01": ("PF-SKILL-REHEARSAL", ["L15"]),
        "PRACTICE-HOME-UPKEEP-SYSTEM-01": ("PF-AUDIT-REDESIGN", ["L18"]),
    }
    assert m6d["fixture"]["action_count"] == 14
    assert m6d["fixture"]["duplicate_origin_rejected"] is True
    assert m6d["fixture"]["duplicate_event_rejected"] is True
    assert m6d["fixture"]["cross_epoch_rejected"] is True
    assert m6d["runtime"] == {
        "actions": sum(len(protocol["actions"]) for protocol in catalog.runtime_protocols),
        "protocols": len(catalog.runtime_protocols),
        "score_active_protocols": sum(
            protocol["score_active"] for protocol in catalog.runtime_protocols
        ),
        "typed_protocols": 378,
    }

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
    assert {row["typed_production_protocols"] for row in capability_rows} == {
        str(readiness["typed_production_protocols"])
    }
    assert {row["typed_score_active_protocols"] for row in capability_rows} == {
        str(readiness["typed_score_active_protocols"])
    }

    policy_rows = list(csv.DictReader(io.StringIO(first[REPORT_PATHS["scoring_policy"]].decode())))
    assert len(policy_rows) == 7
    assert {row["synthetic_execution"] for row in policy_rows} == {"passed"}
    assert {row["typed_execution_boundary"] for row in policy_rows} == {
        "runtime_replay_with_event_withholding"
    }
    assert {row["policy_id"] for row in policy_rows if row["production_status"] == "active"} == {
        "SP-STRUCTURED-EVIDENCE-ELIGIBLE"
    }

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


def test_m6d_fixture_scope_remains_fixed_when_later_typed_packages_are_added():
    root = Path(__file__).resolve().parents[1]
    catalog = load_practice_content_bundle(root)
    later_protocol = deepcopy(
        next(
            protocol
            for protocol in catalog.protocols
            if protocol["stable_id"] == "PRACTICE-MOTIVATION-INDEPENDENT-START-01"
        )
    )
    later_protocol["stable_id"] = "PRACTICE-FUTURE-TYPED-01"
    for sequence, action in enumerate(later_protocol["intervention"]["actions"], start=1):
        action_id = f"PRACTICE-FUTURE-TYPED-01-A{sequence}"
        action["stable_id"] = action_id
        action["typed_evidence_identity"]["protocol_stable_id"] = later_protocol["stable_id"]
        action["typed_evidence_identity"]["action_stable_id"] = action_id
    future_catalog = replace(catalog, protocols=(*catalog.protocols, later_protocol))

    summary = competency_evidence_reports._m6d_fixture_summary(
        root,
        future_catalog,
        load_typed_evidence_spec(root / "data" / "evidence"),
    )

    assert summary["action_count"] == 14
    assert not any("FUTURE" in action_id for action_id in summary["action_ids"])
