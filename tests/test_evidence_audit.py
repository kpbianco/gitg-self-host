import json
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.utils import timezone

from growth.domain.evidence import (
    EVIDENCE_ALGORITHM_VERSION,
    EvidenceInput,
    evaluate_evidence,
    replay_evidence,
)
from growth.models import (
    AssessmentRun,
    CurriculumVersion,
    EvidenceEvent,
    LeverBaseline,
    PracticeAction,
    PracticeCheckIn,
    PracticeProtocol,
)
from growth.services.evidence import (
    EVIDENCE_EXPORT_SCHEMA_VERSION,
    EvidenceWorkflowError,
    verify_evidence_event,
)
from growth.services.practice import save_check_in, start_practice
from growth.services.score_state import synchronize_score_state_for_run

ROOT = Path(__file__).resolve().parents[1]
CALIBRATION_PATH = ROOT / "tests" / "fixtures" / "evidence" / "calibration_v1.json"


def _protocol():
    return PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")


def _ensure_assessment(user):
    existing = AssessmentRun.objects.filter(user=user).first()
    if existing is not None:
        return existing
    source = AssessmentRun.objects.first()
    run = AssessmentRun.objects.create(
        stable_id=f"TEST-ASSESSMENT-{user.pk}",
        user=user,
        curriculum_version=CurriculumVersion.objects.get(active=True),
        assessment_version="1.1",
        source=AssessmentRun.Source.APPLICATION,
    )
    if source is not None:
        LeverBaseline.objects.bulk_create(
            LeverBaseline(
                user=user,
                assessment_run=run,
                lever=baseline.lever,
                raw_self_report=baseline.raw_self_report,
                calibrated_estimate=baseline.calibrated_estimate,
                evidence_confidence=baseline.evidence_confidence,
                baseline_alpha=baseline.baseline_alpha,
                baseline_beta=baseline.baseline_beta,
                baseline_mass_source=baseline.baseline_mass_source,
                need_score=baseline.need_score,
                need_rank=baseline.need_rank,
                notes="Synthetic copied baseline for user-scope verification.",
            )
            for baseline in source.lever_baselines.all()
        )
        synchronize_score_state_for_run(run)
    return run


def _sprint(user, *, private_context="PRIVATE-CONTEXT-TOKEN"):
    _ensure_assessment(user)
    return start_practice(
        user=user,
        protocol=_protocol(),
        person_or_context=private_context,
        start_date=date.today(),
    )


def _check_in_data(action, **overrides):
    data = {
        "action": action,
        "action_attempted": True,
        "action_completed": True,
        "user_initiated": True,
        "moved_beyond_transactional": False,
        "follow_up_question_asked": False,
        "meaningful_information_shared": False,
        "future_interaction_scheduled": False,
        "follow_up_within_seven_days": False,
        "internal_resistance": None,
        "expected_reciprocity": None,
        "observed_reciprocity": None,
        "support_level": PracticeCheckIn.SupportLevel.INDEPENDENT,
        "context_comparison": PracticeCheckIn.ContextComparison.FIRST_RECORD,
        "evidence_direction": PracticeCheckIn.EvidenceDirection.SUPPORTS,
        "contradictory_evidence": "",
        "note": "",
    }
    data.update(overrides)
    return data


def _baseline_snapshot(user):
    return list(
        LeverBaseline.objects.filter(user=user)
        .order_by("lever_id")
        .values_list(
            "lever_id",
            "raw_self_report",
            "calibrated_estimate",
            "evidence_confidence",
            "baseline_alpha",
            "baseline_beta",
            "baseline_mass_source",
            "need_score",
            "need_rank",
        )
    )


def test_calibration_fixture_covers_every_direction_and_replays_exactly():
    fixture = json.loads(CALIBRATION_PATH.read_text())
    assert fixture["schema_version"] == "grounded-growth-evidence-calibration-v1"
    assert fixture["algorithm_version"] == EVIDENCE_ALGORITHM_VERSION
    assert len({case["case_id"] for case in fixture["cases"]}) == len(fixture["cases"])

    covered = set()
    for case in fixture["cases"]:
        evidence = EvidenceInput(**case["input"])
        result = evaluate_evidence(evidence, case["evidence_rules"])
        expected = case["expected"]
        covered.add(case["input"]["evidence_direction"] or "not_recorded")

        assert result.algorithm_version == fixture["algorithm_version"], case["case_id"]
        assert result.repetition_index == case["input"]["repetition_index"], case["case_id"]
        for field in (
            "performance",
            "quality",
            "independence",
            "context_breadth",
            "repetition_multiplier",
            "base_evidence_mass",
        ):
            assert getattr(result, field) == Decimal(expected[field]), case["case_id"]
        contradiction = expected["contradiction_level"]
        assert result.contradiction_level == (
            None if contradiction is None else Decimal(contradiction)
        ), case["case_id"]
        assert result.explanation["direction"]["label"] == expected["direction_label"]
        assert result.explanation["base_evidence"]["label"] == expected["mass_label"]
        assert replay_evidence(result.input_snapshot) == result

    assert covered == {
        "supports",
        "inconclusive",
        "mixed",
        "contradicts",
        "not_recorded",
    }


@pytest.mark.django_db
def test_replay_verification_command_is_strict_read_only_and_score_static(user, seeded):
    sprint = _sprint(user)
    action = sprint.protocol.actions.get(sequence=1)
    save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(
            action,
            moved_beyond_transactional=True,
            meaningful_information_shared=True,
        ),
        submit=True,
    )
    before = _baseline_snapshot(user)
    output = StringIO()

    call_command("verify_evidence_events", stdout=output)

    assert "1 events replayed for 1 submitted check-ins" in output.getvalue()
    assert _baseline_snapshot(user) == before


@pytest.mark.django_db
def test_replay_verification_fails_on_missing_or_drifted_event(user, seeded):
    sprint = _sprint(user)
    action = sprint.protocol.actions.get(sequence=1)
    missing = PracticeCheckIn.objects.create(
        sprint=sprint,
        action=action,
        status=PracticeCheckIn.Status.SUBMITTED,
        action_attempted=True,
        submitted_at=timezone.now(),
    )

    with pytest.raises(CommandError, match=f"{missing.pk}.*has no evidence event"):
        call_command("verify_evidence_events")

    missing.delete()
    check_in = save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(action),
        submit=True,
    )
    event = check_in.evidence_event
    EvidenceEvent._base_manager.filter(pk=event.pk).update(algorithm_version="GG-EVIDENCE-BROKEN")

    with pytest.raises(CommandError, match="algorithm_version"):
        call_command("verify_evidence_events")


@pytest.mark.django_db
def test_replay_verification_rejects_action_from_another_protocol(user, seeded):
    sprint = _sprint(user)
    friendship_action = sprint.protocol.actions.get(sequence=1)
    other_protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-PLAY-01")
    other_action = PracticeAction.objects.create(
        stable_id="TEST-OTHER-PROTOCOL-ACTION",
        protocol=other_protocol,
        sequence=1,
        title="Test action",
        instructions="Used only to verify cross-protocol corruption is rejected.",
        evidence_rules=friendship_action.evidence_rules,
    )
    check_in = PracticeCheckIn.objects.create(
        sprint=sprint,
        action=other_action,
        status=PracticeCheckIn.Status.SUBMITTED,
        action_attempted=True,
        action_completed=True,
        moved_beyond_transactional=True,
        meaningful_information_shared=True,
        support_level=PracticeCheckIn.SupportLevel.INDEPENDENT,
        context_comparison=PracticeCheckIn.ContextComparison.FIRST_RECORD,
        evidence_direction=PracticeCheckIn.EvidenceDirection.SUPPORTS,
        submitted_at=timezone.now(),
    )
    replayed = evaluate_evidence(
        EvidenceInput(
            protocol_stable_id=sprint.protocol_id,
            action_stable_id=other_action.pk,
            action_attempted=True,
            action_completed=True,
            observations={
                "user_initiated": False,
                "moved_beyond_transactional": True,
                "follow_up_question_asked": False,
                "meaningful_information_shared": True,
                "future_interaction_scheduled": False,
                "follow_up_within_seven_days": False,
            },
            internal_resistance=None,
            expected_reciprocity=None,
            observed_reciprocity=None,
            support_level=PracticeCheckIn.SupportLevel.INDEPENDENT,
            context_comparison=PracticeCheckIn.ContextComparison.FIRST_RECORD,
            evidence_direction=PracticeCheckIn.EvidenceDirection.SUPPORTS,
            contradiction_text_present=False,
            repetition_index=1,
        ),
        other_action.evidence_rules,
    )
    event = EvidenceEvent.objects.create(
        check_in=check_in,
        algorithm_version=replayed.algorithm_version,
        protocol_stable_id=replayed.input_snapshot["protocol_stable_id"],
        action_stable_id=replayed.input_snapshot["action_stable_id"],
        input_snapshot=replayed.input_snapshot,
        performance=replayed.performance,
        quality=replayed.quality,
        independence=replayed.independence,
        context_breadth=replayed.context_breadth,
        repetition_index=replayed.repetition_index,
        repetition_multiplier=replayed.repetition_multiplier,
        contradiction_level=replayed.contradiction_level,
        base_evidence_mass=replayed.base_evidence_mass,
        explanation=replayed.explanation,
    )

    with pytest.raises(EvidenceWorkflowError, match="does not belong"):
        verify_evidence_event(event)


@pytest.mark.django_db
def test_ledger_is_authenticated_filtered_user_scoped_and_score_static(client, user, seeded):
    sprint = _sprint(user)
    actions = list(sprint.protocol.actions.order_by("sequence"))
    supportive = save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(
            actions[0],
            moved_beyond_transactional=True,
            note="PRIVATE-NOTE-TOKEN",
        ),
        submit=True,
    )
    contradictory = save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(
            actions[1],
            context_comparison=PracticeCheckIn.ContextComparison.SAME_CONTEXT,
            evidence_direction=PracticeCheckIn.EvidenceDirection.CONTRADICTS,
            contradictory_evidence="PRIVATE-CONTRADICTION-TOKEN",
        ),
        submit=True,
    )
    save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(
            actions[2],
            context_comparison=PracticeCheckIn.ContextComparison.SAME_CONTEXT,
            note="PRIVATE-DRAFT-TOKEN",
        ),
        submit=False,
    )
    before = _baseline_snapshot(user)
    url = reverse("growth:evidence-ledger")

    assert client.get(url).status_code == 302
    client.force_login(user)
    response = client.get(url)
    content = response.content.decode()

    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]
    assert "private" in response["Cache-Control"]
    assert response.context["ledger"].summary.total == 2
    assert response.context["ledger"].summary.supports == 1
    assert response.context["ledger"].summary.contradicts == 1
    assert len(response.context["page"].object_list) == 2
    assert "Directional evidence may contribute to your working profile." in content
    assert "PRIVATE-CONTEXT-TOKEN" not in content
    assert "PRIVATE-NOTE-TOKEN" not in content
    assert "PRIVATE-CONTRADICTION-TOKEN" not in content
    assert "PRIVATE-DRAFT-TOKEN" not in content
    assert "0.4675" not in content

    filtered = client.get(url, {"direction": "contradicts"})
    rows = filtered.context["page"].object_list
    assert [row.event.pk for row in rows] == [contradictory.evidence_event.pk]
    assert supportive.action.title not in filtered.content.decode()
    assert client.get(url, {"direction": "invented"}).status_code == 404
    assert _baseline_snapshot(user) == before


@pytest.mark.django_db
def test_export_stops_without_leaking_when_event_coverage_is_incomplete(client, user, seeded):
    sprint = _sprint(user)
    missing = PracticeCheckIn.objects.create(
        sprint=sprint,
        action=sprint.protocol.actions.get(sequence=1),
        status=PracticeCheckIn.Status.SUBMITTED,
        action_attempted=True,
        submitted_at=timezone.now(),
    )
    client.force_login(user)

    response = client.get(reverse("growth:evidence-export"))
    ledger = client.get(reverse("growth:evidence-ledger"))

    assert response.status_code == 409
    assert response.content == b"Evidence export stopped because replay verification failed."
    assert str(missing.pk).encode() not in response.content
    assert ledger.status_code == 409
    assert b"No partial history has been shown or exported." in ledger.content
    assert str(missing.pk).encode() not in ledger.content


@pytest.mark.django_db
def test_privacy_safe_export_is_deterministic_allowlisted_and_user_scoped(client, user, seeded):
    user.username = "PRIVATE-USERNAME-TOKEN"
    user.save(update_fields=["username"])
    sprint = _sprint(user)
    action = sprint.protocol.actions.get(sequence=1)
    check_in = save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(
            action,
            evidence_direction=PracticeCheckIn.EvidenceDirection.MIXED,
            contradictory_evidence="PRIVATE-CONTRADICTION-TOKEN",
            note="PRIVATE-NOTE-TOKEN",
        ),
        submit=True,
    )

    other_user = get_user_model().objects.create_user(
        username="OTHER-PRIVATE-USER-TOKEN",
        password="local-test-password-47!",
    )
    other_sprint = _sprint(other_user, private_context="OTHER-PRIVATE-CONTEXT-TOKEN")
    other_action = other_sprint.protocol.actions.get(sequence=1)
    other_check_in = save_check_in(
        sprint=other_sprint,
        cleaned_data=_check_in_data(
            other_action,
            note="OTHER-PRIVATE-NOTE-TOKEN",
        ),
        submit=True,
    )
    before = _baseline_snapshot(user)

    client.force_login(user)
    ledger = client.get(reverse("growth:evidence-ledger"))
    url = reverse("growth:evidence-export")
    first = client.get(url)
    second = client.get(url)
    body = first.content.decode()
    payload = json.loads(body)

    assert ledger.status_code == 200
    assert ledger.context["ledger"].summary.total == 1
    assert "OTHER-PRIVATE-USER-TOKEN" not in ledger.content.decode()
    assert first.status_code == 200
    assert first["Content-Type"].startswith("application/json")
    assert first["Content-Disposition"] == ('attachment; filename="grounded-growth-evidence.json"')
    assert "no-store" in first["Cache-Control"]
    assert "private" in first["Cache-Control"]
    assert first.content == second.content
    assert payload["schema_version"] == EVIDENCE_EXPORT_SCHEMA_VERSION
    assert payload["event_count"] == 1
    assert payload["profile_scores_modified"] is True
    assert payload["profile_scores_modified_by_export"] is False
    assert payload["events"][0]["protocol_stable_id"] == sprint.protocol_id
    assert payload["events"][0]["action_stable_id"] == action.pk
    assert payload["events"][0]["output"]["base_evidence_mass"] == "0.4675"
    assert payload["privacy"]["contains_free_text"] is False

    forbidden_values = {
        "PRIVATE-USERNAME-TOKEN",
        "PRIVATE-CONTEXT-TOKEN",
        "PRIVATE-CONTRADICTION-TOKEN",
        "PRIVATE-NOTE-TOKEN",
        "OTHER-PRIVATE-USER-TOKEN",
        "OTHER-PRIVATE-CONTEXT-TOKEN",
        "OTHER-PRIVATE-NOTE-TOKEN",
        str(check_in.pk),
        str(check_in.evidence_event.pk),
        str(sprint.pk),
        str(other_check_in.pk),
        str(other_check_in.evidence_event.pk),
        str(other_sprint.pk),
        check_in.submitted_at.isoformat(),
    }
    assert all(value not in body for value in forbidden_values)
    assert "contradictory_evidence" not in body
    assert "original_share_code" not in body
    assert '"answers"' not in body
    assert _baseline_snapshot(user) == before
