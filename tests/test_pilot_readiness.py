import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from growth.models import (
    AssessmentRun,
    CompetencyLeverLink,
    EvidenceEvent,
    LeverState,
    OrientationResult,
    PracticeAction,
    PracticeCheckIn,
    PracticeProtocol,
    ScoreSnapshot,
)
from growth.services.pilot_readiness import (
    PILOT_READINESS_CONTRACT_VERSION,
    PilotReadinessError,
    verify_pilot_readiness,
)


def database_inventory():
    return {
        "assessment_runs": AssessmentRun.objects.count(),
        "protocols": PracticeProtocol.objects.count(),
        "actions": PracticeAction.objects.count(),
        "check_ins": PracticeCheckIn.objects.count(),
        "events": EvidenceEvent.objects.count(),
        "states": LeverState.objects.count(),
        "snapshots": ScoreSnapshot.objects.count(),
    }


@pytest.mark.django_db
def test_readiness_contract_verifies_reviewed_inventory_without_writes(seeded):
    before = database_inventory()

    summary = verify_pilot_readiness()

    assert summary.contract_version == PILOT_READINESS_CONTRACT_VERSION
    assert summary.domains == 27
    assert summary.lever_families == 7
    assert summary.levers == 37
    assert summary.competencies == 383
    assert summary.orientations == 6
    assert summary.archetypes == 15
    assert summary.archetype_lever_affinities == 555
    assert summary.competency_lever_links == 1403
    assert summary.practice_protocols == 383
    assert summary.practice_actions == 1151
    assert summary.active_protocols == 383
    assert summary.score_active_protocols == 383
    assert summary.pilot_assessment_runs == 1
    assert summary.evidence_events == 0
    assert database_inventory() == before


@pytest.mark.django_db
def test_readiness_management_command_has_deterministic_json_output(seeded):
    output = StringIO()

    call_command("verify_pilot_readiness", json=True, stdout=output)

    payload = json.loads(output.getvalue())
    assert payload["contract_version"] == PILOT_READINESS_CONTRACT_VERSION
    assert payload["practice_protocols"] == 383
    assert payload["practice_actions"] == 1151
    assert payload["score_active_protocols"] == 383


@pytest.mark.django_db
def test_readiness_fails_closed_if_any_score_activation_is_removed(seeded):
    PracticeProtocol.objects.filter(stable_id="PRACTICE-PLAY-01").update(score_active=False)

    with pytest.raises(PilotReadinessError, match="PRACTICE-PLAY-01 score activation"):
        verify_pilot_readiness()


@pytest.mark.django_db
def test_readiness_fails_closed_on_reviewed_protocol_copy_drift(seeded):
    PracticeProtocol.objects.filter(stable_id="PRACTICE-PLAY-01").update(
        recommendation_reason="Unreviewed replacement recommendation."
    )

    with pytest.raises(PilotReadinessError, match="configuration fingerprint"):
        verify_pilot_readiness()


@pytest.mark.django_db
def test_readiness_fails_closed_on_seeded_mapping_drift(seeded):
    CompetencyLeverLink.objects.filter(
        competency_id="17.03",
        lever_id="L26",
    ).update(weight="0.6400")

    with pytest.raises(PilotReadinessError, match="Seeded competency mapping drift"):
        verify_pilot_readiness()


@pytest.mark.django_db
def test_readiness_fails_closed_if_pilot_profile_is_incomplete(seeded):
    pilot = AssessmentRun.objects.get(source=AssessmentRun.Source.PILOT_SEED)
    OrientationResult.objects.filter(assessment_run=pilot).first().delete()

    with pytest.raises(PilotReadinessError, match="orientation output"):
        verify_pilot_readiness()


@pytest.mark.django_db
def test_readiness_command_exits_nonzero_on_contract_drift(seeded):
    PracticeProtocol.objects.filter(stable_id="PRACTICE-PRESENCE-01").update(
        availability=PracticeProtocol.Availability.INACTIVE
    )

    with pytest.raises(CommandError, match="Pilot readiness verification failed"):
        call_command("verify_pilot_readiness")
