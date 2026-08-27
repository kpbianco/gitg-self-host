from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import OperationalError, connection
from django.test import Client
from django.urls import reverse

from growth.domain.personal_os import AUDIT_PROMPT_IDS, IDENTITY_SECTION_IDS
from growth.models import (
    AssessmentContext,
    AssessmentRun,
    EvidenceEvent,
    LeverBaseline,
    LeverState,
    PersonalOSRevision,
    PracticeContext,
    PracticeProtocol,
    PracticeSprint,
    ScoreSnapshot,
)
from growth.services.context_priority import build_context_priority_for_epoch
from growth.services.evidence import build_privacy_safe_evidence_export
from growth.services.pilot_feedback import build_privacy_safe_pilot_export
from growth.services.profile import build_profile_summary


def personal_os_post(*, epoch, state="unknown", mission=""):
    data = {"form_type": "personal_os", "assessment_epoch": epoch}
    for section_id in (*IDENTITY_SECTION_IDS, *AUDIT_PROMPT_IDS):
        data[f"{section_id}_state"] = state
        data[f"{section_id}_value"] = ""
    if mission:
        data["mission_state"] = "provided"
        data["mission_value"] = mission
    return data


def assessment_context_post(*, epoch, capacity="2"):
    return {
        "form_type": "assessment_context",
        "assessment_epoch": epoch,
        "season_state": "provided",
        "season_value": "transition",
        "capacity_state": "provided",
        "capacity_value": capacity,
    }


def practice_context_post(*, epoch, mode="provide", values=None, **extra):
    data = {
        "assessment_epoch": epoch,
        "mode": mode,
        "deferred_factor": "",
        "defer_reason": "",
        "review_horizon_days": "",
        "intent": "save",
    }
    for factor_id in (
        "applicability",
        "importance",
        "readiness",
        "urgency",
        "opportunity_resources",
        "burden",
    ):
        data[factor_id] = "" if values is None else str(values.get(factor_id, 2))
    data.update(extra)
    return data


@pytest.mark.django_db
def test_personal_os_routes_require_authentication_and_no_assessment_redirects(client, user):
    personal_url = reverse("growth:personal-os")
    assert client.get(personal_url).status_code == 302
    client.force_login(user)
    response = client.get(personal_url)
    assert response.status_code == 302
    assert response.url == reverse("growth:assessment")


@pytest.mark.django_db
def test_personal_os_page_has_exact_prompts_privacy_notice_and_no_context_defaults(
    client, user, seeded
):
    client.force_login(user)
    response = client.get(reverse("growth:personal-os"))
    body = response.content.decode()
    assert response.status_code == 200
    for text in (
        "What purpose or contribution do you choose to orient toward for now?",
        "Which one to five principles do you choose to guide decisions for now?",
        "Which one to five outcomes or patterns do you deliberately not want to optimize for?",
        "What direction would you choose to make more real over the next twelve months?",
        "Which one to five priorities deserve attention first in your present season?",
        "What feels most true about your current direction and situation?",
        "Where, if anywhere, have habit, momentum, or outside expectations been choosing for you?",
        "Where, if anywhere, do your actions or commitments feel out of step or fragmented?",
        "What one deliberate next step, if any, would make direction clearer?",
        "included in normal database backups",
        "no dedicated Personal OS or context export",
        "urgent-support monitoring",
    ):
        assert text in body
    assert '<option value="" selected>Choose a state</option>' in body
    assert '<option value="" selected>Choose 0 to 4</option>' in body
    assert "completion percentage" not in body.lower()


@pytest.mark.django_db
def test_personal_os_append_idempotent_prg_and_private_text_isolated(client, user, seeded):
    client.force_login(user)
    run = user.assessment_runs.first()
    sentinel = "PRIVATE-M6C04-SYNTHETIC-SENTINEL"
    url = reverse("growth:personal-os")
    first = client.post(url, personal_os_post(epoch=run.pk, mission=sentinel))
    assert first.status_code == 302
    assert first.url == url
    assert PersonalOSRevision.objects.filter(assessment_run=run).count() == 1
    second = client.post(url, personal_os_post(epoch=run.pk, mission=sentinel))
    assert second.status_code == 302
    assert PersonalOSRevision.objects.filter(assessment_run=run).count() == 1
    assert sentinel in client.get(url).content.decode()
    for page in (
        reverse("growth:home"),
        reverse("growth:practice-list"),
        reverse(
            "growth:practice-recommendation",
            kwargs={"slug": "deepen-one-existing-friendship"},
        ),
    ):
        assert sentinel not in client.get(page).content.decode()


@pytest.mark.django_db
def test_stale_and_conflict_writes_are_private_value_free(client, user, seeded):
    client.force_login(user)
    run = user.assessment_runs.first()
    url = reverse("growth:personal-os")
    sentinel = "PRIVATE-CONFLICT-SENTINEL"
    stale = client.post(url, personal_os_post(epoch="OLD-EPOCH", mission=sentinel))
    assert stale.status_code == 409
    assert sentinel not in stale.content.decode()
    assert PersonalOSRevision.objects.count() == 0
    with patch(
        "growth.views_personal_os.record_personal_os_revision",
        side_effect=OperationalError("database is locked " + sentinel),
    ):
        conflict = client.post(url, personal_os_post(epoch=run.pk, mission=sentinel))
    assert conflict.status_code == 409
    assert sentinel not in conflict.content.decode()
    assert PersonalOSRevision.objects.count() == 0


@pytest.mark.django_db
def test_csrf_is_required_for_personal_os_posts(user, seeded):
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)
    run = user.assessment_runs.first()
    response = csrf_client.post(
        reverse("growth:personal-os"),
        personal_os_post(epoch=run.pk),
    )
    assert response.status_code == 403
    assert PersonalOSRevision.objects.count() == 0


@pytest.mark.django_db
def test_csrf_is_required_for_practice_context_save_and_alternative(user, seeded):
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)
    run = user.assessment_runs.first()
    protocol = PracticeProtocol.objects.filter(availability="active").first()
    url = reverse("growth:practice-context", kwargs={"slug": protocol.slug})
    save = csrf_client.post(url, practice_context_post(epoch=run.pk, mode="not_applicable"))
    alternative = csrf_client.post(url, {"intent": "request_alternative"})
    assert save.status_code == 403
    assert alternative.status_code == 403
    assert PracticeContext.objects.count() == 0


@pytest.mark.django_db
def test_assessment_and_practice_context_modes_append_exact_states(client, user, seeded):
    client.force_login(user)
    run = user.assessment_runs.first()
    personal_url = reverse("growth:personal-os")
    assert client.post(personal_url, assessment_context_post(epoch=run.pk)).status_code == 302
    assert client.post(personal_url, assessment_context_post(epoch=run.pk)).status_code == 302
    assert AssessmentContext.objects.filter(assessment_run=run).count() == 1
    assessment = AssessmentContext.objects.get(assessment_run=run)
    assert assessment.season_value == "transition"
    assert assessment.capacity_value == 2

    friendship = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    context_url = reverse("growth:practice-context", kwargs={"slug": friendship.slug})
    get_response = client.get(context_url)
    assert get_response.status_code == 200
    assert b"Choose 0 to 4" in get_response.content
    assert b"Uncollected factors stay unknown" in get_response.content

    not_applicable = client.post(
        context_url,
        practice_context_post(epoch=run.pk, mode="not_applicable"),
    )
    assert not_applicable.status_code == 302
    first = PracticeContext.objects.get(assessment_run=run, protocol=friendship)
    assert first.applicability_state == "not_applicable"
    assert first.importance_state == "unknown"
    assert first.disposition == "considering"

    deferred = client.post(
        context_url,
        practice_context_post(
            epoch=run.pk,
            mode="defer",
            deferred_factor="readiness",
            defer_reason="timing",
            review_horizon_days="30",
        ),
    )
    assert deferred.status_code == 302
    latest = PracticeContext.objects.filter(assessment_run=run, protocol=friendship).last()
    assert latest.revision == 2
    assert latest.readiness_state == "deferred"
    assert latest.applicability_state == "unknown"
    assert latest.defer_reason == "timing"
    assert latest.review_horizon_days == 30


@pytest.mark.django_db
def test_partial_context_cohort_orders_only_verified_eligible_practices(client, user, seeded):
    client.force_login(user)
    run = user.assessment_runs.first()
    client.post(reverse("growth:personal-os"), assessment_context_post(epoch=run.pk))
    protocols = list(
        PracticeProtocol.objects.filter(availability="active").order_by("stable_id")[:10]
    )
    values = {
        "applicability": 4,
        "importance": 4,
        "readiness": 4,
        "urgency": 4,
        "opportunity_resources": 4,
        "burden": 0,
    }
    for protocol in protocols[:2]:
        response = client.post(
            reverse("growth:practice-context", kwargs={"slug": protocol.slug}),
            practice_context_post(epoch=run.pk, values=values),
        )
        assert response.status_code == 302
    home = client.get(reverse("growth:home"))
    priority = home.context["priority"]
    assert priority.context_aware is True
    assert priority.reviewed_count == 2
    assert priority.partial_cohort is True
    assert {item.stable_id for item in priority.recommendations} == {
        item.stable_id for item in protocols[:2]
    }
    assert b"only among the explicitly reviewed practices" in home.content


@pytest.mark.django_db
def test_alternative_is_distinct_or_explicitly_unavailable(client, user, seeded):
    client.force_login(user)
    run = user.assessment_runs.first()
    client.post(reverse("growth:personal-os"), assessment_context_post(epoch=run.pk))
    protocols = list(PracticeProtocol.objects.filter(availability="active").order_by("stable_id"))
    source, target = protocols[:2]
    source_url = reverse("growth:practice-context", kwargs={"slug": source.slug})
    client.post(source_url, practice_context_post(epoch=run.pk, mode="not_applicable"))
    values = dict.fromkeys(
        ("applicability", "importance", "readiness", "urgency", "opportunity_resources"),
        3,
    )
    values["burden"] = 1
    client.post(
        reverse("growth:practice-context", kwargs={"slug": target.slug}),
        practice_context_post(epoch=run.pk, values=values),
    )
    response = client.post(source_url, {"intent": "request_alternative"})
    assert response.status_code == 200
    assert target.name.encode() in response.content
    assert (
        b'data-context-mode="provide" aria-labelledby="factor-heading" hidden' in response.content
    )
    assert b'data-context-mode="not_applicable" class="inline-note" hidden' not in response.content
    assert b'data-context-mode="defer" aria-labelledby="defer-heading" hidden' in response.content
    assert response.context["priority"].alternative_protocol == target
    assert response.context["priority"].alternative_protocol != source


@pytest.mark.django_db
def test_personal_os_only_preserves_exact_legacy_recommendations(client, user, seeded):
    client.force_login(user)
    run = user.assessment_runs.first()
    before = build_profile_summary(user)
    permanent = (
        [item.stable_id for item in before.recommendations],
        before.recommendation_priorities,
        [item.recommendation_reason for item in before.recommendations],
    )
    client.post(
        reverse("growth:personal-os"),
        personal_os_post(epoch=run.pk, mission="SYNTHETIC-LEGACY-COMPATIBILITY"),
    )
    after = build_profile_summary(user)
    assert permanent == (
        [item.stable_id for item in after.recommendations],
        after.recommendation_priorities,
        [item.recommendation_reason for item in after.recommendations],
    )
    priority = client.get(reverse("growth:home")).context["priority"]
    assert priority.context_aware is False
    assert [item.stable_id for item in priority.recommendations] == permanent[0]


@pytest.mark.django_db
def test_missing_capacity_and_no_eligible_are_not_zero_or_context_aware(client, user, seeded):
    client.force_login(user)
    run = user.assessment_runs.first()
    personal_url = reverse("growth:personal-os")
    missing_capacity = assessment_context_post(epoch=run.pk)
    missing_capacity.update({"capacity_state": "unknown", "capacity_value": ""})
    client.post(personal_url, missing_capacity)
    protocol = PracticeProtocol.objects.filter(availability="active").first()
    context_url = reverse("growth:practice-context", kwargs={"slug": protocol.slug})
    values = dict.fromkeys(
        (
            "applicability",
            "importance",
            "readiness",
            "urgency",
            "opportunity_resources",
            "burden",
        ),
        2,
    )
    client.post(context_url, practice_context_post(epoch=run.pk, values=values))
    missing = client.get(reverse("growth:home")).context["priority"]
    assert missing.status == "missing_capacity"
    assert missing.context_aware is False
    assert "missing, not zero" in missing.message

    client.post(personal_url, assessment_context_post(epoch=run.pk))
    client.post(context_url, practice_context_post(epoch=run.pk, mode="not_applicable"))
    unavailable = client.get(reverse("growth:home")).context["priority"]
    assert unavailable.status == "no_eligible"
    assert unavailable.context_aware is False
    assert "not context-aware" in unavailable.message


@pytest.mark.django_db
def test_browser_order_matches_direct_frozen_result_and_context_retry_is_idempotent(
    client, user, seeded
):
    client.force_login(user)
    run = user.assessment_runs.first()
    client.post(reverse("growth:personal-os"), assessment_context_post(epoch=run.pk, capacity="4"))
    protocols = list(
        PracticeProtocol.objects.filter(availability="active").order_by("stable_id")[:10]
    )
    values = {
        "applicability": 4,
        "importance": 3,
        "readiness": 4,
        "urgency": 2,
        "opportunity_resources": 3,
        "burden": 1,
    }
    for protocol in protocols:
        url = reverse("growth:practice-context", kwargs={"slug": protocol.slug})
        payload = practice_context_post(epoch=run.pk, values=values)
        assert client.post(url, payload).status_code == 302
        assert client.post(url, payload).status_code == 302
    assert PracticeContext.objects.filter(assessment_run=run).count() == len(protocols)
    direct = build_context_priority_for_epoch(
        user=user,
        assessment_run=run,
        protocol_stable_ids=tuple(item.stable_id for item in protocols),
    )
    browser = client.get(reverse("growth:home")).context["priority"]
    assert [item.stable_id for item in browser.recommendations] == list(
        direct.ranked_candidate_ids[:3]
    )
    library = client.get(reverse("growth:practice-list"))
    assert [item.stable_id for item in library.context["ranked_protocols"]] == list(
        direct.ranked_candidate_ids[:3]
    )
    expected_rest = [
        item.stable_id
        for item in PracticeProtocol.objects.order_by("display_order")
        if item.stable_id not in direct.ranked_candidate_ids[:3]
    ]
    assert [item.stable_id for item in library.context["not_context_ranked"]] == expected_rest
    assert b"Not ranked by current context" in library.content
    assert b"does not make them unfavorable" in library.content


@pytest.mark.django_db
def test_practice_context_malformed_stale_conflict_and_inactive_paths_fail_closed(
    client, user, seeded
):
    client.force_login(user)
    run = user.assessment_runs.first()
    protocol = PracticeProtocol.objects.filter(availability="active").first()
    url = reverse("growth:practice-context", kwargs={"slug": protocol.slug})
    for payload in (
        practice_context_post(epoch=run.pk, mode="not_applicable", values={"importance": 2}),
        practice_context_post(epoch=run.pk, values={"burden": 7}),
        practice_context_post(
            epoch=run.pk,
            mode="defer",
            deferred_factor="readiness",
            defer_reason="timing",
            review_horizon_days="367",
        ),
    ):
        assert client.post(url, payload).status_code == 400
        assert PracticeContext.objects.count() == 0
    assert (
        client.post(url, practice_context_post(epoch="STALE", mode="not_applicable")).status_code
        == 409
    )
    assert PracticeContext.objects.count() == 0
    with patch(
        "growth.views_practice.record_context_bundle",
        side_effect=OperationalError("database is locked PRIVATE-NOT-PRINTED"),
    ):
        conflict = client.post(url, practice_context_post(epoch=run.pk, mode="not_applicable"))
    assert conflict.status_code == 409
    assert b"PRIVATE-NOT-PRINTED" not in conflict.content
    assert PracticeContext.objects.count() == 0
    with patch(
        "growth.views_practice.active_projected_protocol_ids",
        side_effect=ValueError("PRIVATE-CANONICAL-FAILURE"),
    ):
        canonical_failure = client.get(url)
    assert canonical_failure.status_code == 404
    assert b"PRIVATE-CANONICAL-FAILURE" not in canonical_failure.content
    protocol.availability = PracticeProtocol.Availability.INACTIVE
    protocol.save(update_fields=["availability"])
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_tampered_or_cross_owned_context_fails_closed_without_becoming_legacy_context(
    client, user, seeded
):
    client.force_login(user)
    run = user.assessment_runs.first()
    client.post(reverse("growth:personal-os"), assessment_context_post(epoch=run.pk))
    protocol = PracticeProtocol.objects.filter(availability="active").first()
    url = reverse("growth:practice-context", kwargs={"slug": protocol.slug})
    client.post(url, practice_context_post(epoch=run.pk, mode="not_applicable"))
    other = get_user_model().objects.create_user(username="other-browser-owner")
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE growth_practicecontext SET user_id = %s WHERE assessment_run_id = %s",
            [other.pk, run.pk],
        )
    priority = client.get(reverse("growth:home")).context["priority"]
    assert priority.status == "unavailable"
    assert priority.context_aware is False
    assert priority.reviewed_count == 0


@pytest.mark.django_db
def test_deferred_alternative_no_eligible_and_browser_actions_do_not_mutate_other_state(
    client, user, seeded
):
    client.force_login(user)
    run = user.assessment_runs.first()
    before = {
        "sprints": PracticeSprint.objects.count(),
        "evidence": EvidenceEvent.objects.count(),
        "states": list(LeverState.objects.order_by("lever_id").values()),
        "snapshots": list(ScoreSnapshot.objects.order_by("created_at").values()),
        "activation": list(
            PracticeProtocol.objects.filter(score_active=True).values_list("stable_id", flat=True)
        ),
    }
    client.post(reverse("growth:personal-os"), assessment_context_post(epoch=run.pk))
    protocol = PracticeProtocol.objects.filter(availability="active").first()
    url = reverse("growth:practice-context", kwargs={"slug": protocol.slug})
    client.post(
        url,
        practice_context_post(
            epoch=run.pk,
            mode="defer",
            deferred_factor="readiness",
            defer_reason="timing",
        ),
    )
    response = client.post(url, {"intent": "request_alternative"})
    assert response.status_code == 200
    assert response.context["priority"].alternative_protocol is None
    assert (
        "No other explicitly reviewed practice" in response.context["priority"].alternative_message
    )
    assert before == {
        "sprints": PracticeSprint.objects.count(),
        "evidence": EvidenceEvent.objects.count(),
        "states": list(LeverState.objects.order_by("lever_id").values()),
        "snapshots": list(ScoreSnapshot.objects.order_by("created_at").values()),
        "activation": list(
            PracticeProtocol.objects.filter(score_active=True).values_list("stable_id", flat=True)
        ),
    }


@pytest.mark.django_db
def test_private_sentinel_absent_from_urls_messages_and_existing_exports(client, user, seeded):
    client.force_login(user)
    run = user.assessment_runs.first()
    sentinel = "PRIVATE-M6C04-EXPORT-LOG-SNAPSHOT-SENTINEL"
    response = client.post(
        reverse("growth:personal-os"),
        personal_os_post(epoch=run.pk, mission=sentinel),
        follow=True,
    )
    assert sentinel not in response.redirect_chain[0][0]
    assert all(sentinel not in str(message) for message in response.context["messages"])
    assert sentinel not in str(build_privacy_safe_evidence_export(user))
    assert sentinel not in str(build_privacy_safe_pilot_export(user))
    assert sentinel not in str(list(EvidenceEvent.objects.values()))
    assert sentinel not in str(list(ScoreSnapshot.objects.values()))
    assert sentinel not in str(list(LeverBaseline.objects.values()))


@pytest.mark.django_db
def test_reassessment_uses_latest_empty_epoch_and_rejects_old_epoch_post(client, user, seeded):
    client.force_login(user)
    old_run = user.assessment_runs.first()
    client.post(
        reverse("growth:personal-os"),
        personal_os_post(epoch=old_run.pk, mission="SYNTHETIC-OLD-EPOCH-ONLY"),
    )
    client.post(reverse("growth:personal-os"), assessment_context_post(epoch=old_run.pk))
    protocol = PracticeProtocol.objects.filter(availability="active").first()
    client.post(
        reverse("growth:practice-context", kwargs={"slug": protocol.slug}),
        practice_context_post(epoch=old_run.pk, mode="not_applicable"),
    )
    new_run = AssessmentRun.objects.create(
        stable_id="SYNTHETIC-M6C04-REASSESSMENT",
        user=user,
        curriculum_version=old_run.curriculum_version,
        assessment_version=old_run.assessment_version,
        source=AssessmentRun.Source.APPLICATION,
        answers={},
        clarifier_answers={},
        timing_data={},
        response_quality_result={},
        orientation_outputs={},
        archetype_outputs=[],
        raw_lever_scores=old_run.raw_lever_scores,
        calibrated_lever_estimates=old_run.calibrated_lever_estimates,
        lever_confidence=old_run.lever_confidence,
    )
    for baseline in LeverBaseline.objects.filter(assessment_run=old_run):
        LeverBaseline.objects.create(
            user=user,
            assessment_run=new_run,
            lever=baseline.lever,
            raw_self_report=baseline.raw_self_report,
            calibrated_estimate=baseline.calibrated_estimate,
            evidence_confidence=baseline.evidence_confidence,
            baseline_alpha=baseline.baseline_alpha,
            baseline_beta=baseline.baseline_beta,
            baseline_mass_source=baseline.baseline_mass_source,
            need_score=baseline.need_score,
            need_rank=baseline.need_rank,
            notes=baseline.notes,
        )
    response = client.get(reverse("growth:personal-os"))
    body = response.content.decode()
    assert response.context["assessment_run"] == new_run
    assert "SYNTHETIC-OLD-EPOCH-ONLY" not in body
    assert not PersonalOSRevision.objects.filter(assessment_run=new_run).exists()
    assert not AssessmentContext.objects.filter(assessment_run=new_run).exists()
    assert not PracticeContext.objects.filter(assessment_run=new_run).exists()
    before = (PersonalOSRevision.objects.count(), AssessmentContext.objects.count())
    stale = client.post(
        reverse("growth:personal-os"),
        personal_os_post(epoch=old_run.pk, mission="SYNTHETIC-STALE-RETRY"),
    )
    assert stale.status_code == 409
    assert before == (PersonalOSRevision.objects.count(), AssessmentContext.objects.count())


@pytest.mark.django_db
def test_personal_os_hidden_overbound_list_and_form_type_inputs_write_nothing(client, user, seeded):
    client.force_login(user)
    run = user.assessment_runs.first()
    url = reverse("growth:personal-os")
    hidden = personal_os_post(epoch=run.pk)
    hidden["mission_value"] = "HIDDEN-WHILE-UNKNOWN"
    overbound = personal_os_post(epoch=run.pk, mission="x" * 501)
    too_many = personal_os_post(epoch=run.pk)
    too_many.update({"principles_state": "provided", "principles_value": "\n".join("abcdef")})
    interior_blank = personal_os_post(epoch=run.pk)
    interior_blank.update({"principles_state": "provided", "principles_value": " first \n\nsecond"})
    for payload in (hidden, overbound, too_many, interior_blank):
        assert client.post(url, payload).status_code == 400
        assert PersonalOSRevision.objects.count() == 0
    for payload in (
        {"assessment_epoch": run.pk, "mission_value": "PRIVATE-MISSING-TYPE"},
        {"form_type": "unsupported", "mission_value": "PRIVATE-UNSUPPORTED-TYPE"},
    ):
        response = client.post(url, payload)
        assert response.status_code == 400
        assert b"PRIVATE-" not in response.content
        assert PersonalOSRevision.objects.count() == 0
    spaced = personal_os_post(epoch=run.pk)
    spaced.update({"principles_state": "provided", "principles_value": " first \nsecond "})
    assert client.post(url, spaced).status_code == 302
    assert PersonalOSRevision.objects.get().principles_value == [" first ", "second "]


@pytest.mark.django_db
def test_private_sentinel_absent_from_logs_and_committed_reports(client, user, seeded, caplog):
    client.force_login(user)
    run = user.assessment_runs.first()
    sentinel = "PRIVATE-M6C04-CAPLOG-REPORT-SENTINEL"
    response = client.post(
        reverse("growth:personal-os"),
        personal_os_post(epoch=run.pk, mission=sentinel),
    )
    assert response.status_code == 302
    assert sentinel not in caplog.text
    reports = Path(__file__).resolve().parents[1] / "reports"
    for path in reports.rglob("*"):
        if path.is_file():
            assert sentinel.encode() not in path.read_bytes()
