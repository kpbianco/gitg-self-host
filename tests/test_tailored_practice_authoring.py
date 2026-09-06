import copy
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from django.urls import reverse
from django.utils import timezone
from jsonschema import ValidationError

from growth.domain.practice_content import load_practice_content_bundle
from growth.models import (
    CompletionCreditEvent,
    CompositeScoreState,
    LeverBaseline,
    PracticeCheckIn,
    PracticeProtocol,
    PracticeSprint,
)
from growth.services.canonical_import import CanonicalDataError, _seed_protocols
from scripts.tailored_practice_authoring import (
    SCHEMA,
    UniqueKeyLoader,
    apply_exercise,
    coverage_report,
    load_exercises,
)

ROOT = Path(__file__).resolve().parents[1]


def test_tailored_coverage_keeps_unwritten_competencies_explicit():
    exercises = load_exercises(ROOT)
    report = coverage_report(exercises, ROOT)
    assert report["target"] == 383
    assert report["authored"] + report["remaining"] == 383
    assert report["human_review_complete"] == 0
    assert {
        row["competency_id"] for row in report["rows"] if row["status"] == "authored_pending_review"
    } == set(exercises)
    assert "01.04" in exercises


def test_tailored_source_rejects_missing_checks_and_duplicate_competency_keys():
    from jsonschema import Draft202012Validator

    document = yaml.safe_load((ROOT / "docs/authoring/exercises/01.yaml").read_text())
    del document["exercises"]["01.04"]["actions"][0]["checks"]
    with pytest.raises(ValidationError):
        Draft202012Validator(SCHEMA).validate(document)
    with pytest.raises(ValueError, match="Duplicate authoring key"):
        yaml.load("'01.04': first\n'01.04': second\n", Loader=UniqueKeyLoader)


def test_tailored_exercises_reach_runtime_with_checks_examples_and_fixed_ids():
    exercises = load_exercises(ROOT)
    bundle = load_practice_content_bundle(ROOT)
    canonical = {row["parent_competency_id"]: row for row in bundle.protocols}
    runtime = {row["parent_competency_id"]: row for row in bundle.runtime_protocols}
    for cid, exercise in exercises.items():
        protocol = canonical[cid]
        projection = runtime[cid]
        assert projection["name"] == exercise["title"]
        assert exercise["setup"] in projection["setup_prompt"]
        assert exercise["adaptation"] in projection["setup_prompt"]
        assert exercise["review"] in projection["actions"][-1]["instructions"]
        for example in exercise["examples"].values():
            assert example in projection["actions"][-1]["instructions"]
        for action, authored in zip(projection["actions"], exercise["actions"], strict=True):
            assert action["stable_id"] == f"{projection['stable_id']}-A{action['sequence']}"
            assert authored["instructions"] in action["instructions"]
            assert all(check in action["instructions"] for check in authored["checks"])
        before = copy.deepcopy(protocol)
        projected = apply_exercise(protocol, exercise)
        assert protocol == before
        assert (
            projected["completion_and_review"]["completion_rules"]
            == before["completion_and_review"]["completion_rules"]
        )
    assert len(runtime) == 383
    assert sum(len(row["actions"]) for row in runtime.values()) == 1151


@pytest.mark.django_db
@pytest.mark.parametrize("status", [PracticeSprint.Status.ACTIVE, PracticeSprint.Status.PAUSED])
def test_import_refuses_content_changes_to_ongoing_practice_without_partial_writes(
    user, seeded, status
):
    bundle = load_practice_content_bundle(ROOT)
    protocols = copy.deepcopy(bundle.runtime_protocols)
    chosen = next(row for row in protocols if row["parent_competency_id"] == "01.04")
    original = chosen["actions"][0]["instructions"]
    PracticeSprint.objects.create(
        user=user,
        protocol_id=chosen["stable_id"],
        start_date=date(2026, 9, 5),
        person_or_context="Synthetic tradeoff case",
        status=status,
    )
    # An unchanged catalog remains idempotent during a sprint.
    _seed_protocols(protocols)
    # A changed early catalog row must not be written before a later ongoing
    # practice is rejected. The preflight validates all active dependencies.
    first = protocols[0]
    old_name = PracticeProtocol.objects.get(pk=first["stable_id"]).name
    first["name"] = "A change that must roll back"
    chosen["actions"][0]["instructions"] = "A different task, incompatible with the current sprint."
    with pytest.raises(CanonicalDataError, match="active or paused practice"):
        _seed_protocols(protocols)
    assert PracticeProtocol.objects.get(pk=first["stable_id"]).name == old_name
    assert (
        PracticeProtocol.objects.get(pk=chosen["stable_id"]).actions.get(sequence=1).instructions
        == original
    )


@pytest.mark.django_db
def test_tailored_setup_and_action_copy_are_visible_in_authenticated_journey(client, user, seeded):
    from growth.services.practice import start_practice

    protocol = PracticeProtocol.objects.get(parent_competency_id="01.04")
    client.force_login(user)
    response = client.get(reverse("growth:practice-recommendation", args=[protocol.slug]))
    assert response.status_code == 200
    assert protocol.name in response.content.decode()
    sprint = start_practice(
        user=user,
        protocol=protocol,
        person_or_context="Synthetic shared afternoon",
        start_date=timezone.localdate(),
    )
    response = client.get(reverse("growth:practice-sprint", args=[sprint.pk]))
    assert response.status_code == 200
    assert "reversal condition" in response.content.decode().lower()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "cid,full",
    [
        ("01.04", False),
        ("13.02", True),
        ("05.04", False),
        ("05.07", True),
        ("03.02", False),
        ("03.10", True),
        ("04.07", False),
        ("04.08", True),
        ("06.02", False),
        ("06.08", True),
        ("06.09", False),
        ("06.12", True),
        ("06.14", True),
        ("07.01", False),
        ("07.04", True),
        ("07.09", False),
        ("07.13", True),
        ("07.14", True),
    ],
)
def test_tailored_evidence_closeout_and_replay_survive_a_later_content_revision(
    user, seeded, cid, full
):
    from growth.services.composite_score_state import verify_composite_score_state_for_run
    from growth.services.evidence import verify_evidence_event
    from growth.services.practice import complete_with_review, save_check_in, start_practice

    protocol = PracticeProtocol.objects.get(parent_competency_id=cid)
    sprint = start_practice(
        user=user,
        protocol=protocol,
        person_or_context="Synthetic bounded exercise",
        start_date=timezone.localdate(),
    )
    state = CompositeScoreState.objects.get(assessment_run=sprint.assessment_run)
    baseline_hash = state.state_hash
    baselines = list(
        LeverBaseline.objects.filter(assessment_run=sprint.assessment_run)
        .order_by("lever_id")
        .values()
    )
    actions = list(protocol.actions.order_by("sequence"))
    count = len(actions) if full else protocol.completion_rules["minimum_completed"]
    events = []
    for index, action in enumerate(actions[:count]):
        observations = []
        for rule in action.evidence_rules["measurements"]:
            adverse = rule["role"] == "adverse"
            value = (
                {"criteria_met": rule["criteria"]}
                if rule["kind"] == "artifact"
                else {"numerator": 2, "denominator": 2}
                if rule["kind"] == "bounded_frequency"
                else rule["expected"]
            )
            observations.append(
                {
                    "measurement_id": rule["measurement_id"],
                    "kind": rule["kind"],
                    "state": "not_observed" if adverse else "observed",
                    "provenance_kind": rule["allowed_provenance"][0],
                    "value": None if adverse else value,
                }
            )
        check_in = save_check_in(
            sprint=sprint,
            cleaned_data={
                "action": action,
                "action_attempted": True,
                "action_completed": True,
                "typed_observations": observations,
                "support_level": PracticeCheckIn.SupportLevel.INDEPENDENT,
                "context_comparison": (
                    PracticeCheckIn.ContextComparison.FIRST_RECORD
                    if index == 0
                    else PracticeCheckIn.ContextComparison.SAME_CONTEXT
                ),
                "evidence_direction": PracticeCheckIn.EvidenceDirection.SUPPORTS,
                "contradictory_evidence": "",
                "note": "Private working notes remain outside the evidence event.",
            },
            submit=True,
        )
        events.append(check_in.evidence_event)
    state.refresh_from_db()
    assert state.state_hash == baseline_hash
    assert not CompletionCreditEvent.objects.filter(sprint=sprint).exists()
    complete_with_review(
        sprint=sprint,
        reflection="The bounded checks were observed; this does not establish mastery.",
        contradictory_evidence="",
    )
    credit = CompletionCreditEvent.objects.get(sprint=sprint)
    assert credit.completion_credit == Decimal("1" if full else "0.75")
    state.refresh_from_db()
    closed_hash = state.state_hash
    snapshots = [copy.deepcopy(event.input_snapshot) for event in events]

    # Once the practice is closed, a later catalog revision is permitted.
    # Already submitted observations still use their original frozen checks.
    protocols = copy.deepcopy(load_practice_content_bundle(ROOT).runtime_protocols)
    revised = next(row for row in protocols if row["parent_competency_id"] == cid)
    revised["actions"][0]["instructions"] = "A later, separately reviewed exercise revision."
    revised["actions"][0]["evidence_rules"]["measurements"][0]["criteria"] = [
        "a_different_future_criterion"
    ]
    _seed_protocols(protocols)
    for event, snapshot in zip(events, snapshots, strict=True):
        event.refresh_from_db()
        assert event.input_snapshot == snapshot
        verify_evidence_event(event)
    verify_composite_score_state_for_run(sprint.assessment_run)
    state.refresh_from_db()
    assert state.state_hash == closed_hash
    assert baselines == list(
        LeverBaseline.objects.filter(assessment_run=sprint.assessment_run)
        .order_by("lever_id")
        .values()
    )
