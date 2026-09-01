from __future__ import annotations

import csv
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "reports/practice-content/catalog_governance_audit_v1.json"
FINDINGS_PATH = ROOT / "reports/practice-content/catalog_governance_findings_v1.csv"
REVIEW_QUEUE_PATH = ROOT / "reports/practice-content/catalog_governance_review_queue_v1.csv"
REVIEW_PACKET_PATH = ROOT / "reports/practice-content/catalog_governance_review_packet_v1.md"
SCHEMA_PATH = ROOT / "contracts/catalog-governance-audit.schema.json"
SCRIPT_PATH = ROOT / "scripts/catalog_governance_audit.py"
DISPOSITIONS = {
    "schema_completeness",
    "stable_id_uniqueness",
    "mapping_validity",
    "evidence_rule_executability",
    "privacy_field_allowlist",
    "source_metadata",
    "exact_duplicate_candidates",
    "near_duplicate_candidates",
    "accessibility_adaptation_fields",
    "safety_stop_and_escalation_fields",
    "activation_review_consistency",
}


@pytest.fixture(scope="module")
def audit() -> dict:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def findings() -> list[dict[str, str]]:
    with FINDINGS_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_auditor():
    spec = importlib.util.spec_from_file_location("catalog_governance_audit", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_catalog_audit_schema_and_exact_package_action_coverage(audit):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(audit)
    assert audit["counts"] | {
        "findings": audit["counts"]["findings"],
        "open_findings": audit["counts"]["open_findings"],
    } == {
        "packages": 383,
        "actions": 1151,
        "legacy_packages": 5,
        "typed_packages": 378,
        "generated_additions": 374,
        "score_active_packages": 383,
        "findings": audit["counts"]["findings"],
        "open_findings": audit["counts"]["open_findings"],
    }
    package_ids = [row["protocol_stable_id"] for row in audit["package_rows"]]
    action_ids = [row["action_stable_id"] for row in audit["action_rows"]]
    parent_ids = [row["parent_competency_id"] for row in audit["package_rows"]]
    assert len(package_ids) == len(set(package_ids)) == 383
    assert len(action_ids) == len(set(action_ids)) == 1151
    assert len(parent_ids) == len(set(parent_ids)) == 383
    assert package_ids == sorted(package_ids)
    assert action_ids == sorted(action_ids)


def test_every_package_has_complete_inventories_and_automated_dispositions(audit):
    inventories = audit["inventories"]
    assert len(inventories["domains"]) == 27
    assert len(inventories["parent_mapping_levers"]) == 37
    assert len(inventories["recommendation_target_levers"]) == 37
    assert set(inventories["risk_classes"]) == {
        "RISK-HIGH",
        "RISK-LOW",
        "RISK-MODERATE",
    }
    assert set(inventories["protocol_families"]) == {
        row["protocol_family_id"] for row in audit["package_rows"]
    }
    assert set(inventories["evidence_kinds"]) == {
        kind for row in audit["package_rows"] for kind in row["evidence_kinds"]
    }
    for row in audit["package_rows"]:
        assert set(row["dispositions"]) == DISPOSITIONS
        assert row["source_ids"]
        assert row["research_gap_ids"]
        assert row["expert_review_ids"]
        assert row["parent_mapping_lever_ids"]
        assert row["recommendation_target_lever_ids"]
        assert row["action_ids"]
        assert row["score_active"] is True
        assert row["dispositions"]["schema_completeness"]["status"] == "pass"
        assert row["dispositions"]["stable_id_uniqueness"]["status"] == "pass"
        assert row["dispositions"]["mapping_validity"]["status"] == "pass"
        assert row["dispositions"]["evidence_rule_executability"]["status"] == "pass"
        assert (
            row["dispositions"]["privacy_field_allowlist"]["status"]
            == "pass_structural_review_pending"
        )
        assert (
            row["dispositions"]["activation_review_consistency"]["status"]
            == "owner_directed_active_review_pending"
        )


def test_findings_are_stable_complete_and_prioritized(audit, findings):
    finding_ids = [row["finding_id"] for row in findings]
    assert len(finding_ids) == len(set(finding_ids)) == audit["counts"]["findings"]
    assert finding_ids == sorted(finding_ids)
    assert all(re.fullmatch(r"CGA-[A-Z0-9-]+-[0-9A-F]{16}", value) for value in finding_ids)
    assert all(row["status"] == "open" for row in findings)
    assert all(json.loads(row["objective_evidence"]) for row in findings)
    assert all(row["affected_stable_ids"] for row in findings)
    assert all(row["remediation_class"] for row in findings)
    assert all(row["remediation_dependency"] for row in findings)
    assert all(row["required_roles"] for row in findings)
    assert {"critical", "high", "moderate", "low"} >= {row["severity"] for row in findings}
    categories = Counter(row["category"] for row in findings)
    for category in (
        "operationalization_review_pending",
        "source_review_pending",
        "source_completeness_pending",
        "originality_review_pending",
        "accessibility_review_pending",
        "safety_review_pending",
        "active_pending_governance",
    ):
        assert categories[category] == 383
    assert categories["catalog_structural_repetition_signal"] == 1
    assert categories["legacy_source_journal_prompt_duplication"] == 1
    assert categories["expert_review_gate_pending"] == 1
    assert categories["research_gap_open"] == 1
    with REVIEW_QUEUE_PATH.open(encoding="utf-8", newline="") as handle:
        review_rows = list(csv.DictReader(handle))
    assert len(review_rows) == len(findings)
    assert [int(row["priority_rank"]) for row in review_rows] == list(
        range(1, len(review_rows) + 1)
    )
    assert {row["finding_id"] for row in review_rows} == set(finding_ids)


def test_automated_audit_does_not_complete_manual_governance(audit):
    expert_source = yaml.safe_load(
        (ROOT / "data/practices/expert_review_queue.yaml").read_text(encoding="utf-8")
    )
    gap_source = yaml.safe_load(
        (ROOT / "data/practices/research_gaps.yaml").read_text(encoding="utf-8")
    )
    expert = next(
        review for review in expert_source["reviews"] if review["review_id"] == "ER-M6A-003"
    )
    gap = next(gap for gap in gap_source["gaps"] if gap["gap_id"] == "RG-M6A-002")
    assert expert["status"] == audit["governance_gates"]["expert_review"]["status"] == "pending"
    assert expert["completed_roles"] == []
    assert expert["completed_on"] is None
    assert expert["decision_reference"] is None
    assert gap["status"] == audit["governance_gates"]["research_gap"]["status"] == "open"
    assert audit["governance_gates"]["m6b_accepted"] is False
    assert audit["activation_review_boundary"] == {
        "owner_directed_score_active_packages": 383,
        "software_activation_is_not_governance_acceptance": True,
        "source_complete_packages": 0,
        "specialist_review_complete": False,
    }


def test_reports_are_static_privacy_safe_and_byte_stable(audit):
    assert audit["privacy"] == {
        "catalog_static_inputs_only": True,
        "owner_private_data_read": False,
        "participant_data_read": False,
        "participant_or_owner_values_in_reports": False,
    }
    packet = REVIEW_PACKET_PATH.read_text(encoding="utf-8")
    assert "No participant or owner-private data is read or written" in packet
    assert "Manual M6B-GOV acceptance remains required" in packet
    auditor = _load_auditor()
    first = auditor.build_catalog_governance_audit_outputs(ROOT)
    second = auditor.build_catalog_governance_audit_outputs(ROOT)
    assert first == second
    for relative, expected in first.items():
        assert (ROOT / relative).read_bytes() == expected


def test_catalog_audit_is_wired_into_make_local_full_and_hosted_ci():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    commands = (ROOT / "contracts/verification.commands").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/verification.yml").read_text(encoding="utf-8")
    assert "catalog-governance-audit-check:" in makefile
    assert "scripts/catalog_governance_audit.py --check" in makefile
    assert "make catalog-governance-audit-check PYTHON=.venv/bin/python" in commands
    assert "make catalog-governance-audit-check PYTHON=python" in workflow
