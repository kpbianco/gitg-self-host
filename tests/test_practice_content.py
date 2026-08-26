import copy
import csv
import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from growth.domain.practice_content import (
    FROZEN_LEGACY_CONFIGURATION_HASH,
    PracticeContentError,
    allowed_scoring_statuses_for_effect,
    configuration_hash,
    legacy_projection_payload,
    load_practice_content_bundle,
)
from growth.services import practice_content_reports
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

    assert len(runtime) == 5
    assert len(bundle.protocols) == len(bundle.release_manifest["protocol_files"])
    assert sum(len(protocol["actions"]) for protocol in runtime) == 15
    assert {protocol["stable_id"] for protocol in runtime if protocol["score_active"]} == {
        "PRACTICE-FRIENDSHIP-01"
    }
    assert (
        configuration_hash([legacy_projection_payload(protocol) for protocol in runtime])
        == FROZEN_LEGACY_CONFIGURATION_HASH
    )
    assert bundle.content_hash == bundle.release_manifest["content_hash"]
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
    assert {
        "SRC-M6D-MOTIVATION-IMPLEMENTATION-INTENTIONS",
        "SRC-M6D-DECISION-OUTCOME-BIAS",
        "SRC-M6D-DELIBERATE-PRACTICE",
        "SRC-M6D-DELIBERATE-PRACTICE-LIMITS",
        "SRC-M6D-NCHH-HEALTHY-HOME",
    } <= set(bundle.sources)
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


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("mixed_version", "cannot mix evidence-rule versions"),
        ("unknown_version", "schema validation failed"),
        ("malformed_rule", "schema validation failed"),
        ("missing_kind_field", "schema validation failed"),
        ("cross_kind_field", "schema validation failed"),
        ("undeclared_check_in", "typed fields must exactly match"),
        ("identity_mismatch", "must exactly match"),
        ("runtime_projection", "cannot be projected"),
    ],
)
def test_source_only_typed_rules_fail_closed(tmp_path, mutation, error):
    base = _copy_practice_tree(tmp_path)
    protocol_path = (
        base
        / "data"
        / "practices"
        / "protocols"
        / "08"
        / "PRACTICE-MOTIVATION-INDEPENDENT-START-01.yaml"
    )
    protocol = yaml.safe_load(protocol_path.read_text())
    action = protocol["intervention"]["actions"][0]
    if mutation == "mixed_version":
        action["evidence_rules"] = {
            "schema_version": "practice-observation-v1",
            "primary_markers": ["user_initiated"],
            "supporting_markers": ["follow_up_question_asked"],
        }
        action.pop("typed_evidence_identity")
    elif mutation == "unknown_version":
        action["evidence_rules"]["schema_version"] = "typed-evidence-rules-v2"
    elif mutation == "malformed_rule":
        action["evidence_rules"]["measurements"][0]["implicit_more_is_better"] = True
    elif mutation == "missing_kind_field":
        action["evidence_rules"]["measurements"][0].pop("expected")
    elif mutation == "cross_kind_field":
        action["evidence_rules"]["measurements"][0]["unit"] = "minutes"
    elif mutation == "undeclared_check_in":
        protocol["evidence_and_scoring"]["check_in_fields"].append("private_narrative")
        protocol["presentation"]["check_in_labels"]["private_narrative"] = "Private narrative"
    elif mutation == "identity_mismatch":
        action["typed_evidence_identity"]["competency_stable_id"] = "08.05"
    else:
        protocol["governance"]["runtime_projection"] = "GG-PRACTICE-RUNTIME-PROJECTION-1.0"
        protocol["governance"]["availability"] = "active"
    protocol_path.write_text(yaml.safe_dump(protocol, sort_keys=False))

    with pytest.raises(PracticeContentError, match=error):
        load_practice_content_bundle(base)


def test_typed_measurement_schema_requires_exact_kind_fields():
    schema = json.loads(
        (ROOT / "data/practices/schema/practice_content_v1.schema.json").read_text()
    )
    validator = Draft202012Validator(schema)
    protocol = yaml.safe_load(
        (
            ROOT / "data/practices/protocols/08/PRACTICE-MOTIVATION-INDEPENDENT-START-01.yaml"
        ).read_text()
    )
    missing = copy.deepcopy(protocol)
    missing["intervention"]["actions"][0]["evidence_rules"]["measurements"][0].pop("expected")
    cross_kind = copy.deepcopy(protocol)
    cross_kind["intervention"]["actions"][0]["evidence_rules"]["measurements"][0]["unit"] = (
        "minutes"
    )

    assert list(validator.iter_errors(missing))
    assert list(validator.iter_errors(cross_kind))


def test_frozen_legacy_package_bytes_remain_exact():
    expected = (
        (
            "protocols/08/PRACTICE-PRESENCE-01.yaml",
            "5d0c39a9fb36d816253fb231cc7d132b1a72583b71e364339749af37a0bdf366",
        ),
        (
            "protocols/11/PRACTICE-BOUNDARY-01.yaml",
            "c008291dd82b300bc8e216b8c4fab4f33982f86e8ec3a3c0a90c26b85ef4b4fc",
        ),
        (
            "protocols/16/PRACTICE-EMOTIONAL-CUES-01.yaml",
            "bca089dfacd413719aa89b1863d05b317f6d85ef3faf49eb72c18b675b3d6793",
        ),
        (
            "protocols/17/PRACTICE-FRIENDSHIP-01.yaml",
            "a924ff732696468c5dd5305ce0145bdbd483ab3c66390dd216b0ac31fa5d789a",
        ),
        (
            "protocols/26/PRACTICE-PLAY-01.yaml",
            "48810b2dd8e66e9e7ec33a9a7000b2f5bbffb6289c74f36d73d1eb1a830fd7a8",
        ),
    )

    for relative_path, digest in expected:
        assert (
            hashlib.sha256((ROOT / "data/practices" / relative_path).read_bytes()).hexdigest()
            == digest
        )


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


def test_validated_bundle_cache_is_defensive_and_invalidates_on_source_drift(tmp_path):
    first = load_practice_content_bundle(ROOT)
    first.protocols[0]["domain_id"] = "99"
    second = load_practice_content_bundle(ROOT)
    assert second.protocols[0]["domain_id"] != "99"

    base = _copy_practice_tree(tmp_path)
    load_practice_content_bundle(base)
    source_path = base / "docs" / "protocol-library.md"
    source_path.write_text(source_path.read_text() + "\nPost-cache drift.\n")
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
    authored_count = len(load_practice_content_bundle(ROOT).protocols)
    assert sum(row["content_status"] == "uncovered" for row in coverage) == 383 - authored_count
    assert len({row["domain_id"] for row in coverage}) == 27

    summary = json.loads(outputs[Path("reports/practice-content/coverage_summary_v1.json")])
    assert summary["competencies"] == {
        "authored_packages": authored_count,
        "projected_legacy": 5,
        "total": 383,
        "uncovered": 383 - authored_count,
    }
    authored_rows = [row for row in coverage if row["protocol_stable_id"]]
    assert summary["levers"] == {
        "covered_through_parent_mapping": len(
            {
                lever_id
                for row in authored_rows
                for lever_id in row["parent_mapping_lever_ids"].split(";")
                if lever_id
            }
        ),
        "recommendation_targets": len(
            {
                lever_id
                for row in authored_rows
                for lever_id in row["recommendation_target_lever_ids"].split(";")
                if lever_id
            }
        ),
        "total": 37,
    }
    assert sum(summary["protocols"]["risk_classes"].values()) == authored_count

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
    assert len(originality["parent_competency_operationalization_signals"]) == authored_count
    assert originality["structure_warnings"]["disposition"].startswith(
        "Structural repetition is reported"
    )


def test_originality_report_routes_duplicate_and_structural_mutations():
    catalog = copy.deepcopy(load_practice_content_bundle(ROOT))
    canonical = load_and_validate_bundle()
    baseline = practice_content_reports._originality_report(ROOT, catalog, canonical)
    first = next(
        protocol
        for protocol in catalog.protocols
        if protocol["stable_id"] == "PRACTICE-MOTIVATION-INDEPENDENT-START-01"
    )
    second = next(
        protocol
        for protocol in catalog.protocols
        if protocol["stable_id"] == "PRACTICE-DECISION-RECORD-01"
    )
    first_action = first["intervention"]["actions"][0]
    second_action = second["intervention"]["actions"][0]
    second_action["title"] = first_action["title"]
    second_action["instructions"] = first_action["instructions"]
    second_action["evidence_rules"] = copy.deepcopy(first_action["evidence_rules"])
    second["completion_and_review"]["reflection"] = copy.deepcopy(
        first["completion_and_review"]["reflection"]
    )
    for field in (
        "privacy_and_boundaries",
        "foreseeable_misuse",
        "exclusions",
        "adaptations",
        "pause_conditions",
        "stop_conditions",
        "escalation_conditions",
        "professional_referral_conditions",
    ):
        second["intervention"][field] = copy.deepcopy(first["intervention"][field])
    second["intervention"]["duration_days"] = first["intervention"]["duration_days"]
    second["intervention"]["actions"].append(copy.deepcopy(second_action))

    report = practice_content_reports._originality_report(
        ROOT,
        catalog,
        canonical,
    )

    duplicates = report["exact_or_normalized_duplicates"]
    assert duplicates["action_titles"]
    assert duplicates["action_instructions"]
    assert duplicates["reflection_sets"]
    assert duplicates["safety"]
    assert any(
        group["classification"] == "review_required"
        for group in duplicates["evidence_rule_payloads"]
    )
    assert (
        report["structure_warnings"]["action_count_distribution"]
        != baseline["structure_warnings"]["action_count_distribution"]
    )


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
