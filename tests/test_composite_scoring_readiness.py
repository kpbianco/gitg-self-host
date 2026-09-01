import json
from io import StringIO

import pytest
from django.core.management import call_command

from growth.services.composite_scoring_readiness import (
    COMPOSITE_SCORING_READINESS_VERSION,
    verify_composite_scoring_readiness,
)


@pytest.mark.django_db
def test_composite_scoring_readiness_is_complete_read_only_and_keeps_human_gate(user, seeded):
    first = verify_composite_scoring_readiness()
    second = verify_composite_scoring_readiness()

    assert first == second
    assert first.contract_version == COMPOSITE_SCORING_READINESS_VERSION
    assert first.assessment_runs == 1
    assert first.assessment_snapshots == 1
    assert first.current_states == 1
    assert first.families_per_epoch == 7
    assert first.levers_per_epoch == 37
    assert first.domains_per_epoch == 27
    assert first.competencies_per_epoch == 383
    assert first.practices == 383
    assert first.actions == 1151
    assert first.software_ready is True
    assert first.requires_human_gate is True
    assert first.specialist_review_status == "pending"
    assert first.specialist_review_complete is False
    assert first.research_gap_status == "open"
    assert first.m6b_accepted is False

    output = StringIO()
    call_command("verify_composite_scoring_readiness", "--json", stdout=output)
    payload = json.loads(output.getvalue())
    assert payload == first.as_dict()
