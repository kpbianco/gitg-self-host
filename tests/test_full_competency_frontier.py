import json
from pathlib import Path

import yaml

from growth.domain.practice_content import (
    FROZEN_LEGACY_PROTOCOL_IDS,
    load_practice_content_bundle,
)

ROOT = Path(__file__).resolve().parents[1]


def _canonical_competency_ids() -> set[str]:
    document = yaml.safe_load(
        (
            ROOT / "data" / "curriculum" / "ideal_person_curriculum_v2_pluralist_full_scope.yaml"
        ).read_text()
    )["curriculum"]
    return {
        competency["id"] for domain in document["domains"] for competency in domain["competencies"]
    }


def test_full_frontier_materializes_every_competency_in_the_active_runtime():
    bundle = load_practice_content_bundle(ROOT)
    canonical_ids = _canonical_competency_ids()
    protocol_ids = {protocol["stable_id"] for protocol in bundle.protocols}

    assert len(canonical_ids) == 383
    assert len(bundle.protocols) == 383
    assert {protocol["parent_competency_id"] for protocol in bundle.protocols} == canonical_ids
    assert len(protocol_ids) == 383
    assert len(bundle.activation_entries) == 383

    runtime = bundle.runtime_protocols
    assert {protocol["stable_id"] for protocol in runtime} == protocol_ids
    assert sum(len(protocol["actions"]) for protocol in runtime) == 1151
    assert all(protocol["score_active"] for protocol in runtime)
    assert set(FROZEN_LEGACY_PROTOCOL_IDS) <= protocol_ids

    generated = [
        protocol
        for protocol in bundle.protocols
        if protocol["stable_id"].startswith("PRACTICE-COMP-")
    ]
    assert len(generated) == 374
    assert {protocol["governance"]["availability"] for protocol in generated} == {"active"}
    assert {protocol["governance"]["editorial_status"] for protocol in generated} == {"draft"}
    assert {protocol["governance"]["runtime_projection"] for protocol in generated} == {
        "GG-PRACTICE-RUNTIME-PROJECTION-2.0"
    }
    assert {len(protocol["intervention"]["actions"]) for protocol in generated} == {3}

    generated_actions = [
        action for protocol in generated for action in protocol["intervention"]["actions"]
    ]
    assert len(generated_actions) == 1_122
    assert len({action["stable_id"] for action in generated_actions}) == 1_122
    assert len({action["title"] for action in generated_actions}) == 1_122
    assert len({action["instructions"] for action in generated_actions}) == 1_122

    for protocol in generated:
        governance = protocol["governance"]
        activation = bundle.activation_entries[protocol["stable_id"]]
        assert governance["scoring_policy_id"] == "SP-STRUCTURED-EVIDENCE-ELIGIBLE"
        assert governance["scoring_status"] == "active"
        assert activation["score_active"] is True
        assert activation["activation_status"] == "active"
        assert activation["approved_contract"] == "GG-SCORE-STATE-1.0"


def test_full_frontier_covers_every_grounded_growth_lever():
    bundle = load_practice_content_bundle(ROOT)
    model = json.loads((ROOT / "data" / "model" / "grounded_growth_model_v1.json").read_text())
    expected_levers = {lever["id"] for lever in model["developmental_levers"]}
    parent_links = {
        link["competency_id"]: set(link["lever_weights"])
        for link in model["competency_lever_links"]
    }
    recommendation_levers: set[str] = set()

    assert len(expected_levers) == 37
    for protocol in bundle.protocols:
        target_levers = set(protocol["evidence_and_scoring"]["recommendation_target_lever_ids"])
        assert target_levers
        assert target_levers <= parent_links[protocol["parent_competency_id"]]
        recommendation_levers.update(target_levers)

    assert recommendation_levers == expected_levers
