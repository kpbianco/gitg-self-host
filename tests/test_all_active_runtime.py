from datetime import date

import pytest

from growth.domain.typed_evidence import (
    TYPED_EVIDENCE_ALGORITHM_VERSION,
    load_typed_evidence_spec,
    materialize_typed_evidence_rules,
)
from growth.forms import PracticeCheckInForm, _typed_field_name
from growth.models import (
    CompositeScoreState,
    LeverBaseline,
    LeverState,
    PracticeCheckIn,
    PracticeProtocol,
    PracticeSprint,
)
from growth.services.evidence import build_privacy_safe_evidence_export, verify_evidence_event
from growth.services.practice import save_check_in, start_practice, transition_sprint
from growth.services.score_state import verify_score_state_for_run


def _observed_value(rule):
    kind = rule["kind"]
    if kind == "boolean":
        return rule["expected"]
    if kind == "count":
        return int(float(rule["target"]))
    if kind == "bounded_frequency":
        return {"numerator": 1, "denominator": 1}
    if kind == "ordinal":
        return rule["levels"][-1]["level_id"]
    if kind in {"duration", "objective"}:
        return {"amount": rule["target"], "unit": rule["unit"]}
    if kind in {"artifact", "conceptual", "scenario"}:
        return {"criteria_met": list(rule["criteria"])}
    if kind == "attestation":
        return {
            "attestation_id": rule["allowed_attestation_ids"][0],
            "consent_confirmed": True,
        }
    raise AssertionError(kind)


def _typed_observations(action):
    rules = materialize_typed_evidence_rules(action.evidence_rules, load_typed_evidence_spec())[
        "measurements"
    ]
    return [
        {
            "measurement_id": rule["measurement_id"],
            "kind": rule["kind"],
            "state": "not_observed" if rule["role"] == "adverse" else "observed",
            "provenance_kind": rule["allowed_provenance"][0],
            "value": None if rule["role"] == "adverse" else _observed_value(rule),
        }
        for rule in rules
    ]


@pytest.mark.django_db
def test_seed_projects_and_score_activates_every_canonical_protocol(user, seeded):
    protocols = PracticeProtocol.objects.all()

    assert protocols.count() == 383
    assert protocols.filter(availability="active").count() == 383
    assert protocols.filter(score_active=True).count() == 383
    assert sum(protocol.actions.count() for protocol in protocols) == 1151


@pytest.mark.django_db
def test_typed_form_collects_action_specific_structured_observations(user, seeded):
    protocol = PracticeProtocol.objects.get(
        stable_id="PRACTICE-COMP-0101-CONCEPTIONS-OF-FLOURISHING-01"
    )
    sprint = start_practice(
        user=user,
        protocol=protocol,
        person_or_context="Private context",
        start_date=date.today(),
    )
    action = protocol.actions.get(sequence=1)
    materialized = materialize_typed_evidence_rules(
        action.evidence_rules, load_typed_evidence_spec()
    )
    data = {
        "action": action.pk,
        "action_attempted": "on",
        "action_completed": "on",
        "support_level": PracticeCheckIn.SupportLevel.INDEPENDENT,
        "context_comparison": PracticeCheckIn.ContextComparison.FIRST_RECORD,
        "evidence_direction": PracticeCheckIn.EvidenceDirection.SUPPORTS,
        "contradictory_evidence": "",
        "note": "private text excluded from evidence",
    }
    for rule in materialized["measurements"]:
        measurement_id = rule["measurement_id"]
        data[_typed_field_name(measurement_id, "state")] = "observed"
        data[_typed_field_name(measurement_id, "provenance")] = rule["allowed_provenance"][0]
        value = _observed_value(rule)
        if rule["kind"] in {"artifact", "conceptual", "scenario"}:
            data[_typed_field_name(measurement_id, "value")] = value["criteria_met"]
        elif rule["kind"] == "boolean":
            data[_typed_field_name(measurement_id, "value")] = "true" if value else "false"
        else:
            raise AssertionError("Fixture intentionally uses artifact and Boolean values.")

    form = PracticeCheckInForm(data=data, sprint=sprint, require_evidence_metadata=True)

    assert form.is_valid(), form.errors
    assert {
        observation["measurement_id"] for observation in form.cleaned_data["typed_observations"]
    } == {rule["measurement_id"] for rule in materialized["measurements"]}


@pytest.mark.django_db
def test_typed_draft_restores_structured_observations(user, seeded):
    protocol = PracticeProtocol.objects.get(
        stable_id="PRACTICE-COMP-0101-CONCEPTIONS-OF-FLOURISHING-01"
    )
    sprint = start_practice(
        user=user,
        protocol=protocol,
        person_or_context="Private context",
        start_date=date.today(),
    )
    action = protocol.actions.get(sequence=1)
    observations = _typed_observations(action)
    draft = save_check_in(
        sprint=sprint,
        cleaned_data={
            "action": action,
            "action_attempted": True,
            "action_completed": True,
            "typed_observations": observations,
            "support_level": PracticeCheckIn.SupportLevel.INDEPENDENT,
            "context_comparison": PracticeCheckIn.ContextComparison.FIRST_RECORD,
            "evidence_direction": PracticeCheckIn.EvidenceDirection.SUPPORTS,
            "contradictory_evidence": "",
            "note": "",
        },
        submit=False,
    )

    form = PracticeCheckInForm(instance=draft, sprint=sprint)

    first = observations[0]
    measurement_id = first["measurement_id"]
    assert form.initial[_typed_field_name(measurement_id, "state")] == first["state"]
    assert form.initial[_typed_field_name(measurement_id, "provenance")] == first["provenance_kind"]


@pytest.mark.django_db
def test_typed_submission_is_replayable_but_does_not_score_before_closeout(user, seeded):
    protocol = PracticeProtocol.objects.get(
        stable_id=(
            "PRACTICE-COMP-2713-APPLICABILITY-ROLE-CHOICE-AND-THE-RIGHT-TO-LEAVE-"
            "DOMAINS-UNCHOSEN-01"
        )
    )
    sprint = start_practice(
        user=user,
        protocol=protocol,
        person_or_context="Private context",
        start_date=date.today(),
    )
    action = protocol.actions.get(sequence=1)
    baseline_before = list(
        LeverBaseline.objects.filter(assessment_run=sprint.assessment_run)
        .order_by("lever_id")
        .values_list("lever_id", "baseline_alpha", "baseline_beta", "calibrated_estimate")
    )
    legacy_state_before = list(
        LeverState.objects.filter(assessment_run=sprint.assessment_run)
        .order_by("lever_id")
        .values_list(
            "lever_id",
            "current_estimate",
            "current_confidence",
            "cumulative_evidence_mass",
            "included_evidence_events",
        )
    )
    composite_hash_before = CompositeScoreState.objects.get(
        assessment_run=sprint.assessment_run
    ).state_hash
    check_in = save_check_in(
        sprint=sprint,
        cleaned_data={
            "action": action,
            "action_attempted": True,
            "action_completed": True,
            "typed_observations": _typed_observations(action),
            "support_level": PracticeCheckIn.SupportLevel.INDEPENDENT,
            "context_comparison": PracticeCheckIn.ContextComparison.FIRST_RECORD,
            "evidence_direction": PracticeCheckIn.EvidenceDirection.SUPPORTS,
            "contradictory_evidence": "",
            "note": "private narrative never enters the score event",
        },
        submit=True,
    )
    event = check_in.evidence_event

    assert event.algorithm_version == TYPED_EVIDENCE_ALGORITHM_VERSION
    assert event.protocol_stable_id == protocol.stable_id
    assert "private narrative" not in str(event.input_snapshot)
    verify_evidence_event(event)
    assert not LeverState.objects.filter(
        assessment_run=sprint.assessment_run,
        cumulative_evidence_mass__gt=0,
    ).exists()
    verify_score_state_for_run(sprint.assessment_run)
    exported = build_privacy_safe_evidence_export(user)
    assert exported["event_count"] == 1
    assert exported["profile_scores_modified"] is False
    assert "observed_on" not in exported["events"][0]["input"]
    assert "as_of_date" not in exported["events"][0]["input"]
    assert (
        CompositeScoreState.objects.get(assessment_run=sprint.assessment_run).state_hash
        == composite_hash_before
    )
    assert (
        list(
            LeverState.objects.filter(assessment_run=sprint.assessment_run)
            .order_by("lever_id")
            .values_list(
                "lever_id",
                "current_estimate",
                "current_confidence",
                "cumulative_evidence_mass",
                "included_evidence_events",
            )
        )
        == legacy_state_before
    )
    assert baseline_before == list(
        LeverBaseline.objects.filter(assessment_run=sprint.assessment_run)
        .order_by("lever_id")
        .values_list("lever_id", "baseline_alpha", "baseline_beta", "calibrated_estimate")
    )


@pytest.mark.django_db
def test_mixed_protocol_check_ins_remain_unscored_before_closeout(user, seeded):
    protocols = [
        PracticeProtocol.objects.get(stable_id="PRACTICE-COMP-0101-CONCEPTIONS-OF-FLOURISHING-01"),
        PracticeProtocol.objects.get(stable_id="PRACTICE-COMP-0102-A-PROVISIONAL-WORLDVIEW-01"),
    ]
    events = []
    assessment_run = None
    composite_hash_before = None
    for index, protocol in enumerate(protocols):
        sprint = start_practice(
            user=user,
            protocol=protocol,
            person_or_context=f"Private context {index}",
            start_date=date.today(),
        )
        assessment_run = sprint.assessment_run
        if composite_hash_before is None:
            composite_hash_before = CompositeScoreState.objects.get(
                assessment_run=assessment_run
            ).state_hash
        action = protocol.actions.get(sequence=1)
        check_in = save_check_in(
            sprint=sprint,
            cleaned_data={
                "action": action,
                "action_attempted": True,
                "action_completed": True,
                "typed_observations": _typed_observations(action),
                "support_level": PracticeCheckIn.SupportLevel.INDEPENDENT,
                "context_comparison": PracticeCheckIn.ContextComparison.FIRST_RECORD,
                "evidence_direction": PracticeCheckIn.EvidenceDirection.SUPPORTS,
                "contradictory_evidence": "",
                "note": "",
            },
            submit=True,
        )
        events.append(check_in.evidence_event)
        transition_sprint(sprint, PracticeSprint.Status.STOPPED)

    shared = LeverState.objects.get(assessment_run=assessment_run, lever_id="L01")
    assert shared.included_evidence_events == 0
    assert shared.cumulative_evidence_mass == 0
    verify_score_state_for_run(assessment_run)
    assert len({event.pk for event in events}) == 2
    assert (
        CompositeScoreState.objects.get(assessment_run=assessment_run).state_hash
        == composite_hash_before
    )
