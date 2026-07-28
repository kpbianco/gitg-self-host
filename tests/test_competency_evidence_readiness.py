import json

import pytest
from django.core.management import call_command

from growth.models import (
    EvidenceEvent,
    PracticeAction,
    PracticeProtocol,
    ScoreSnapshot,
)
from growth.services.competency_evidence_readiness import (
    verify_competency_evidence_readiness,
)


def _runtime_counts():
    return {
        "protocols": PracticeProtocol.objects.count(),
        "actions": PracticeAction.objects.count(),
        "evidence_events": EvidenceEvent.objects.count(),
        "score_snapshots": ScoreSnapshot.objects.count(),
    }


@pytest.mark.django_db
def test_competency_evidence_readiness_is_additive_read_only_and_not_acceptance(
    seeded,
):
    before = _runtime_counts()

    summary = verify_competency_evidence_readiness()

    assert _runtime_counts() == before
    assert summary.contract_version == "GG-COMPETENCY-EVIDENCE-READINESS-1.0"
    assert summary.preserved_expansion_contract_version == "GG-CURRICULUM-EXPANSION-READINESS-1.0"
    assert (
        summary.production_score_eligibility_contract_version
        == "GG-PRODUCTION-SCORE-ELIGIBILITY-1.0"
    )
    assert summary.software_ready is True
    assert summary.specialist_review_complete is False
    assert summary.m6b_accepted is False
    assert summary.competencies == 383
    assert summary.canonical_protocol_packages == 5
    assert summary.practice_actions == 15
    assert summary.uncovered_competencies == 378
    assert summary.score_active_protocols == 1
    assert summary.typed_production_protocols == 0
    assert summary.typed_score_active_protocols == 0
    assert summary.expert_review_id == "ER-M6A-003"
    assert summary.expert_review_status == "pending"
    assert summary.research_gap_id == "RG-M6A-002"
    assert summary.research_gap_status == "open"


@pytest.mark.django_db
def test_competency_evidence_readiness_command_emits_deterministic_json(
    seeded,
    capsys,
):
    call_command("verify_competency_evidence_readiness", "--json")
    payload = json.loads(capsys.readouterr().out)

    assert payload["contract_version"] == ("GG-COMPETENCY-EVIDENCE-READINESS-1.0")
    assert payload["software_ready"] is True
    assert payload["specialist_review_complete"] is False
    assert payload["m6b_accepted"] is False
    assert payload["typed_production_protocols"] == 0
    assert payload["typed_score_active_protocols"] == 0
