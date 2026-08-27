import json
from pathlib import Path

import pytest
from django.core.management import call_command

from growth.domain.practice_content import load_practice_content_bundle
from growth.models import PracticeAction, PracticeProtocol
from growth.services.canonical_import import seed_canonical_data
from growth.services.expansion_readiness import verify_expansion_readiness
from growth.services.score_state import synchronize_all_score_states


@pytest.mark.django_db
def test_expansion_readiness_is_additive_read_only_and_preserves_runtime(user):
    seed_canonical_data()
    synchronize_all_score_states()
    before = {
        "protocols": PracticeProtocol.objects.count(),
        "actions": PracticeAction.objects.count(),
        "friendship_name": PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01").name,
    }

    summary = verify_expansion_readiness()

    after = {
        "protocols": PracticeProtocol.objects.count(),
        "actions": PracticeAction.objects.count(),
        "friendship_name": PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01").name,
    }
    assert before == after
    assert summary.contract_version == "GG-CURRICULUM-EXPANSION-READINESS-1.0"
    assert summary.preserved_pilot_contract_version == "GG-PILOT-READINESS-1.0"
    catalog = load_practice_content_bundle(Path(__file__).resolve().parents[1])
    assert summary.canonical_protocol_packages == len(catalog.protocols)
    assert summary.practice_actions == sum(
        len(protocol["intervention"]["actions"]) for protocol in catalog.protocols
    )
    assert summary.runtime_protocols == before["protocols"]
    assert summary.runtime_actions == before["actions"]
    assert summary.uncovered_competencies == 383 - len(catalog.protocols)
    assert summary.score_active_protocols == 383


@pytest.mark.django_db
def test_expansion_readiness_command_emits_deterministic_json(user, capsys):
    seed_canonical_data()
    synchronize_all_score_states()
    call_command("verify_expansion_readiness", "--json")
    payload = json.loads(capsys.readouterr().out)
    assert payload["contract_version"] == "GG-CURRICULUM-EXPANSION-READINESS-1.0"
    assert (
        payload["legacy_projection_hash"]
        == load_practice_content_bundle(Path(__file__).resolve().parents[1]).release_manifest[
            "legacy_projection_hash"
        ]
    )
