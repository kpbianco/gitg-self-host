import copy
import csv
import json
import shutil
from pathlib import Path

import pytest
import yaml

from growth.domain.practice_content import (
    FROZEN_LEGACY_CONFIGURATION_HASH,
    PracticeContentError,
    allowed_scoring_statuses_for_effect,
    configuration_hash,
    legacy_projection_payload,
    load_practice_content_bundle,
)
from growth.services.canonical_import import (
    CanonicalDataError,
    load_and_validate_bundle,
    validate_practice_content_mapping,
)
from growth.services.practice_content_reports import (
    PracticeReportError,
    build_practice_report_outputs,
    write_or_check_practice_reports,
)

ROOT = Path(__file__).resolve().parents[1]


def _copy_practice_tree(tmp_path: Path) -> Path:
    base = tmp_path / "repo"
    destination = base / "data" / "practices"
    destination.parent.mkdir(parents=True)
    shutil.copytree(ROOT / "data" / "practices", destination)
    source_registry = yaml.safe_load(
        (ROOT / "data" / "practices" / "registries" / "source_registry.yaml").read_text()
    )
    for source in source_registry["sources"]:
        if source["locator_kind"] != "repository_path":
            continue
        source_path = ROOT / source["locator"]
        target_path = base / source["locator"]
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source_path, target_path)
    return base


def test_canonical_practice_bundle_preserves_five_protocol_runtime_projection():
    bundle = load_practice_content_bundle(ROOT)
    runtime = bundle.runtime_protocols

    assert len(bundle.protocols) == len(runtime) == 5
    assert sum(len(protocol["actions"]) for protocol in runtime) == 15
    assert {protocol["stable_id"] for protocol in runtime if protocol["score_active"]} == {
        "PRACTICE-FRIENDSHIP-01"
    }
    assert (
        configuration_hash([legacy_projection_payload(protocol) for protocol in runtime])
        == FROZEN_LEGACY_CONFIGURATION_HASH
    )
    assert bundle.content_hash == (
        "77dfae7546824046045df919ff4970b28132e76a1580bba5b532fa185afb94b3"
    )
    assert load_and_validate_bundle().source_hash == (
        "6958ccfbe0c0d80b7485ac866a8418578850284b58956f59168429819447dfc5"
    )


def test_registries_cover_risk_scoring_source_family_and_activation_boundaries():
    bundle = load_practice_content_bundle(ROOT)

    assert set(bundle.risk_classes) == {
        "RISK-LOW",
        "RISK-MODERATE",
        "RISK-HIGH",
    }
    assert {
        "SP-SELF-REPORT-ELIGIBLE",
        "SP-CORROBORATION-REQUIRED",
        "SP-ARTIFACT-OBJECTIVE-PREFERRED",
        "SP-QUALIFIED-EVIDENCE-REQUIRED",
        "SP-SHADOW-ONLY",
        "SP-NON-SCORED-REFLECTION",
    } <= set(bundle.scoring_policies)
    assert len(bundle.protocol_families) == 12
    assert len(bundle.sources) == 5
    assert sum(activation["score_active"] for activation in bundle.activation_entries.values()) == 1


def test_schema_rejects_unknown_protocol_fields_and_unknown_versions(tmp_path):
    base = _copy_practice_tree(tmp_path)
    protocol_path = base / "data" / "practices" / "protocols" / "17" / "PRACTICE-FRIENDSHIP-01.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    protocol["unreviewed_extension"] = True
    protocol_path.write_text(yaml.safe_dump(protocol, sort_keys=False))

    with pytest.raises(PracticeContentError, match="Additional properties"):
        load_practice_content_bundle(base)

    base = _copy_practice_tree(tmp_path / "version")
    registry_path = base / "data" / "practices" / "registries" / "risk_taxonomy.yaml"
    registry = yaml.safe_load(registry_path.read_text())
    registry["schema_version"] = "GG-PROTOCOL-RISK-2.0"
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False))
    with pytest.raises(PracticeContentError, match="schema validation failed"):
        load_practice_content_bundle(base)


def test_manifest_rejects_unlisted_protocol_files(tmp_path):
    base = _copy_practice_tree(tmp_path)
    extra_path = base / "data" / "practices" / "protocols" / "17" / "PRACTICE-UNLISTED-01.yaml"
    shutil.copy(
        extra_path.with_name("PRACTICE-FRIENDSHIP-01.yaml"),
        extra_path,
    )
    with pytest.raises(PracticeContentError, match="manifest coverage drift"):
        load_practice_content_bundle(base)


def test_activation_ledger_rejects_second_score_active_protocol(tmp_path):
    base = _copy_practice_tree(tmp_path)
    play_path = base / "data" / "practices" / "protocols" / "26" / "PRACTICE-PLAY-01.yaml"
    play_protocol = yaml.safe_load(play_path.read_text())
    play_protocol["governance"]["scoring_policy_id"] = "SP-SELF-REPORT-ELIGIBLE"
    play_protocol["governance"]["scoring_status"] = "active"
    play_path.write_text(yaml.safe_dump(play_protocol, sort_keys=False))
    activation_path = base / "data" / "practices" / "registries" / "activation_ledger.yaml"
    ledger = yaml.safe_load(activation_path.read_text())
    play = next(
        item for item in ledger["activations"] if item["protocol_stable_id"] == "PRACTICE-PLAY-01"
    )
    play["score_active"] = True
    play["activation_status"] = "active"
    play["scoring_policy_id"] = "SP-SELF-REPORT-ELIGIBLE"
    play["approved_contract"] = "UNREVIEWED"
    activation_path.write_text(yaml.safe_dump(ledger, sort_keys=False))

    with pytest.raises(PracticeContentError, match="separately reviewed contract"):
        load_practice_content_bundle(base)


def test_eligible_scoring_policy_can_remain_inactive():
    assert "eligible_inactive" in allowed_scoring_statuses_for_effect("eligible_if_activated")
    assert "active" in allowed_scoring_statuses_for_effect("eligible_if_activated")


def test_frozen_active_contract_rejects_contract_substitution(tmp_path):
    base = _copy_practice_tree(tmp_path)
    activation_path = base / "data" / "practices" / "registries" / "activation_ledger.yaml"
    ledger = yaml.safe_load(activation_path.read_text())
    friendship = next(
        item
        for item in ledger["activations"]
        if item["protocol_stable_id"] == "PRACTICE-FRIENDSHIP-01"
    )
    friendship["approved_contract"] = "FAKE"
    activation_path.write_text(yaml.safe_dump(ledger, sort_keys=False))

    with pytest.raises(PracticeContentError, match="activation boundary changed"):
        load_practice_content_bundle(base)


def test_repository_source_hash_drift_fails_closed(tmp_path):
    base = _copy_practice_tree(tmp_path)
    source_path = base / "docs" / "protocol-library.md"
    source_path.write_text(source_path.read_text() + "\nUnreviewed drift.\n")

    with pytest.raises(PracticeContentError, match="repository source hash drift"):
        load_practice_content_bundle(base)


def test_release_candidate_cannot_self_certify_over_open_controls(tmp_path):
    base = _copy_practice_tree(tmp_path)
    protocol_path = base / "data" / "practices" / "protocols" / "11" / "PRACTICE-BOUNDARY-01.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    governance = protocol["governance"]
    governance["editorial_status"] = "release_candidate"
    authoring = governance["authoring"]
    for field in (
        "content_review_status",
        "research_review_status",
        "safety_review_status",
        "accessibility_review_status",
        "originality_review_status",
    ):
        authoring[field] = "complete"
    authoring["ui_test_status"] = "complete"
    authoring["last_reviewed"] = "2026-07-27"
    protocol_path.write_text(yaml.safe_dump(protocol, sort_keys=False))

    with pytest.raises(PracticeContentError, match="unresolved gates"):
        load_practice_content_bundle(base)


def test_full_catalog_controls_cannot_be_omitted(tmp_path):
    base = _copy_practice_tree(tmp_path)
    protocol_path = base / "data" / "practices" / "protocols" / "08" / "PRACTICE-PRESENCE-01.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    protocol["governance"]["authoring"]["known_gap_ids"].remove("RG-M6A-001")
    protocol_path.write_text(yaml.safe_dump(protocol, sort_keys=False))

    with pytest.raises(PracticeContentError, match="applicable research gaps"):
        load_practice_content_bundle(base)


def test_claim_class_and_risk_ceiling_drift_fail_closed(tmp_path):
    base = _copy_practice_tree(tmp_path)
    protocol_path = base / "data" / "practices" / "protocols" / "08" / "PRACTICE-PRESENCE-01.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    protocol["meaning_and_fit"]["claims"][0]["classification"] = "empirical_finding"
    protocol_path.write_text(yaml.safe_dump(protocol, sort_keys=False))
    with pytest.raises(PracticeContentError, match="classification does not match"):
        load_practice_content_bundle(base)

    base = _copy_practice_tree(tmp_path / "risk")
    risk_path = base / "data" / "practices" / "registries" / "risk_taxonomy.yaml"
    taxonomy = yaml.safe_load(risk_path.read_text())
    high = next(item for item in taxonomy["risk_classes"] if item["risk_class_id"] == "RISK-HIGH")
    high["pre_review_scoring_ceiling"] = "active_if_separately_approved"
    risk_path.write_text(yaml.safe_dump(taxonomy, sort_keys=False))
    with pytest.raises(PracticeContentError, match="reviewed risk boundary changed"):
        load_practice_content_bundle(base)


def test_action_identity_and_marker_collection_are_validated(tmp_path):
    base = _copy_practice_tree(tmp_path)
    protocol_path = base / "data" / "practices" / "protocols" / "08" / "PRACTICE-PRESENCE-01.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    protocol["intervention"]["actions"][0]["stable_id"] = "PRACTICE-PRESENCE-01-A99"
    protocol_path.write_text(yaml.safe_dump(protocol, sort_keys=False))
    with pytest.raises(PracticeContentError, match="must equal PRACTICE-PRESENCE-01-A1"):
        load_practice_content_bundle(base)

    base = _copy_practice_tree(tmp_path / "markers")
    protocol_path = base / "data" / "practices" / "protocols" / "08" / "PRACTICE-PRESENCE-01.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    protocol["evidence_and_scoring"]["check_in_fields"].remove("user_initiated")
    protocol["presentation"]["check_in_labels"].pop("user_initiated")
    protocol_path.write_text(yaml.safe_dump(protocol, sort_keys=False))
    with pytest.raises(PracticeContentError, match="outside check_in_fields"):
        load_practice_content_bundle(base)

    base = _copy_practice_tree(tmp_path / "due")
    protocol_path = base / "data" / "practices" / "protocols" / "08" / "PRACTICE-PRESENCE-01.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    protocol["intervention"]["actions"][0]["due_within_days"] = 999
    protocol_path.write_text(yaml.safe_dump(protocol, sort_keys=False))
    with pytest.raises(PracticeContentError, match="invalid due window"):
        load_practice_content_bundle(base)


def test_specialist_gate_rejects_unrelated_completed_review(tmp_path):
    base = _copy_practice_tree(tmp_path)
    protocol_path = base / "data" / "practices" / "protocols" / "11" / "PRACTICE-BOUNDARY-01.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    governance = protocol["governance"]
    governance["editorial_status"] = "release_candidate"
    authoring = governance["authoring"]
    for field in (
        "content_review_status",
        "research_review_status",
        "safety_review_status",
        "accessibility_review_status",
        "originality_review_status",
    ):
        authoring[field] = "complete"
    authoring["ui_test_status"] = "complete"
    authoring["last_reviewed"] = "2026-07-27"
    protocol_path.write_text(yaml.safe_dump(protocol, sort_keys=False))

    gaps_path = base / "data" / "practices" / "research_gaps.yaml"
    gaps = yaml.safe_load(gaps_path.read_text())
    for gap in gaps["gaps"]:
        if gap["gap_id"] in {"RG-M6A-001", "RG-M6A-006"}:
            gap["status"] = "resolved"
    gaps_path.write_text(yaml.safe_dump(gaps, sort_keys=False))

    reviews_path = base / "data" / "practices" / "expert_review_queue.yaml"
    reviews = yaml.safe_load(reviews_path.read_text())
    review = next(item for item in reviews["reviews"] if item["review_id"] == "ER-M6A-002")
    review["review_type"] = "content"
    review["status"] = "complete"
    review["completed_roles"] = review["required_roles"]
    review["completed_on"] = "2026-07-27"
    review["decision_reference"] = "docs/PRODUCT_DECISIONS.md#decision-046"
    reviews_path.write_text(yaml.safe_dump(reviews, sort_keys=False))

    with pytest.raises(PracticeContentError, match="specialist_review:missing"):
        load_practice_content_bundle(base)


def test_manifest_rejects_unlisted_control_files(tmp_path):
    base = _copy_practice_tree(tmp_path)
    extra_path = base / "data" / "practices" / "registries" / "unlisted.yaml"
    extra_path.write_text("schema_version: UNLISTED\n")

    with pytest.raises(PracticeContentError, match="canonical content manifest coverage drift"):
        load_practice_content_bundle(base)


def test_content_hash_detects_governance_drift(tmp_path):
    base = _copy_practice_tree(tmp_path)
    gap_path = base / "data" / "practices" / "research_gaps.yaml"
    gaps = yaml.safe_load(gap_path.read_text())
    gaps["gaps"][0]["current_evidence"] += " Unreviewed drift."
    gap_path.write_text(yaml.safe_dump(gaps, sort_keys=False))

    with pytest.raises(PracticeContentError, match="content hash drift"):
        load_practice_content_bundle(base)


def test_mapping_validation_rejects_wrong_domain_and_target_lever():
    canonical = load_and_validate_bundle()
    practices = load_practice_content_bundle(ROOT)
    modified = copy.deepcopy(practices)
    modified.protocols[0]["domain_id"] = "99"
    with pytest.raises(CanonicalDataError, match="does not match"):
        validate_practice_content_mapping(modified, canonical)

    modified = copy.deepcopy(practices)
    modified.protocols[0]["evidence_and_scoring"]["recommendation_target_lever_ids"] = ["L37"]
    with pytest.raises(CanonicalDataError, match="must be a subset"):
        validate_practice_content_mapping(modified, canonical)


def test_generated_coverage_and_originality_reports_are_current_and_complete():
    outputs = build_practice_report_outputs(ROOT)
    write_or_check_practice_reports(base_dir=ROOT, check=True)

    coverage_bytes = outputs[Path("reports/practice-content/competency_coverage_v1.csv")]
    coverage = list(csv.DictReader(coverage_bytes.decode().splitlines()))
    assert len(coverage) == 383
    assert sum(row["content_status"] == "projected_legacy" for row in coverage) == 5
    assert sum(row["content_status"] == "uncovered" for row in coverage) == 378
    assert len({row["domain_id"] for row in coverage}) == 27

    summary = json.loads(outputs[Path("reports/practice-content/coverage_summary_v1.json")])
    assert summary["competencies"] == {
        "authored_packages": 5,
        "projected_legacy": 5,
        "total": 383,
        "uncovered": 378,
    }
    assert summary["levers"] == {
        "covered_through_parent_mapping": 13,
        "recommendation_targets": 6,
        "total": 37,
    }
    assert summary["protocols"]["risk_classes"] == {
        "RISK-LOW": 3,
        "RISK-MODERATE": 2,
    }

    lever_bytes = outputs[Path("reports/practice-content/lever_coverage_v1.csv")]
    lever_coverage = {
        row["lever_id"]: int(row["canonical_competency_count"])
        for row in csv.DictReader(lever_bytes.decode().splitlines())
    }
    canonical = load_and_validate_bundle()
    expected_lever_counts = {
        lever["id"]: lever["coverage"]["competency_count"]
        for lever in canonical.model["developmental_levers"]
    }
    assert lever_coverage == expected_lever_counts

    originality = json.loads(outputs[Path("reports/practice-content/content_originality_v1.json")])
    notion = originality["legacy_notion_source_audit"]
    assert notion["rows"] == notion["most_repeated_journal_prompt_count"] == 383
    assert notion["unique_journal_prompts"] == 1
    assert originality["exact_or_normalized_duplicates"]["action_instructions"] == []
    assert len(originality["exact_or_normalized_duplicates"]["evidence_rule_payloads"]) == 2
    assert originality["evidence_markers_that_only_restate_completion"] == []
    assert len(originality["parent_competency_operationalization_signals"]) == 5


def test_report_check_fails_closed_for_missing_output(tmp_path):
    base = _copy_practice_tree(tmp_path)
    notion_target = base / "data" / "notion" / "initial_mvp"
    notion_target.mkdir(parents=True)
    shutil.copy(
        ROOT / "data" / "notion" / "initial_mvp" / "02_development_tasks_ranked_import.csv",
        notion_target,
    )
    with pytest.raises(PracticeReportError, match="missing or stale"):
        write_or_check_practice_reports(base_dir=base, check=True)
