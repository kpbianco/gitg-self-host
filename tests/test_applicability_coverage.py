from copy import deepcopy
from decimal import Decimal

import pytest
from django.db import connection
from django.urls import reverse

from growth.models import (
    AssessmentRun,
    CompositeScoreState,
    LeverBaseline,
    PracticeContext,
    PracticeProtocol,
)
from growth.services.applicability_coverage import (
    build_applicability_coverage_projection,
    calculate_personal_applicable_coverage,
)
from growth.services.composite_score_state import synchronize_all_composite_score_states
from growth.services.profile import build_profile_summary


def _context_post(run, *, mode="not_applicable", intent="save"):
    return {
        "assessment_epoch": run.pk,
        "mode": mode,
        "deferred_factor": "",
        "defer_reason": "",
        "review_horizon_days": "",
        "intent": intent,
        "applicability": "" if mode != "provide" else "4",
        "importance": "" if mode != "provide" else "2",
        "readiness": "" if mode != "provide" else "2",
        "urgency": "" if mode != "provide" else "2",
        "opportunity_resources": "" if mode != "provide" else "2",
        "burden": "" if mode != "provide" else "2",
    }


def test_empty_personal_denominator_is_unavailable_not_full_coverage():
    count, coverage = calculate_personal_applicable_coverage(
        {"COMP-1": Decimal("1"), "COMP-2": Decimal("0.75")},
        {"COMP-1", "COMP-2"},
    )

    assert count == 0
    assert coverage is None


@pytest.mark.django_db
def test_projection_excludes_only_explicit_not_applicable_from_personal_denominator(
    client, user, seeded
):
    run = user.assessment_runs.get()
    protocol = PracticeProtocol.objects.filter(availability="active").order_by("stable_id").first()
    client.force_login(user)
    url = reverse("growth:practice-context", kwargs={"slug": protocol.slug})
    assert client.post(url, _context_post(run)).status_code == 302

    persisted = CompositeScoreState.objects.get(assessment_run=run)
    state = deepcopy(persisted.state)
    state["competencies"][protocol.parent_competency_id]["completion_credit"] = "1.000000000000"
    state["canonical_coverage"] = format(Decimal(1) / Decimal(383), ".12f")
    projection = build_applicability_coverage_projection(
        user=user,
        assessment_run=run,
        composite_state=state,
    )

    assert projection.canonical_competency_count == 383
    assert projection.personally_not_applicable_competency_ids == (protocol.parent_competency_id,)
    assert projection.personal_applicable_competency_count == 382
    assert projection.canonical_completion_coverage == Decimal("0.002610966057")
    assert projection.personal_applicable_completion_coverage == Decimal("0.000000000000")
    assert CompositeScoreState.objects.get(pk=persisted.pk).state_hash == persisted.state_hash
    assert CompositeScoreState.objects.get(pk=persisted.pk).state == persisted.state


@pytest.mark.django_db
def test_direct_not_applicable_action_is_immediate_revisable_and_score_neutral(
    client, user, seeded
):
    run = user.assessment_runs.get()
    protocol = PracticeProtocol.objects.filter(availability="active").order_by("stable_id").first()
    state = CompositeScoreState.objects.get(assessment_run=run)
    before = (state.state_hash, deepcopy(state.state))
    client.force_login(user)

    recommendation = client.get(
        reverse("growth:practice-recommendation", kwargs={"slug": protocol.slug})
    )
    assert b"Not applicable to me" in recommendation.content
    response = client.post(
        reverse("growth:practice-context", kwargs={"slug": protocol.slug}),
        _context_post(run, intent="save_and_request_alternative"),
    )

    assert response.status_code == 200
    assert b"Ask for a distinct reviewed alternative" in response.content
    context = PracticeContext.objects.get(assessment_run=run, protocol=protocol)
    assert context.applicability_state == "not_applicable"
    state.refresh_from_db()
    assert (state.state_hash, state.state) == before

    profile = client.get(reverse("growth:profile"))
    body = profile.content.decode()
    assert "Personal-applicable coverage view" in body
    assert "382" in body
    assert "canonical all-competency coverage, unchanged" in body

    assert (
        client.post(
            reverse("growth:practice-context", kwargs={"slug": protocol.slug}),
            _context_post(run, mode="provide"),
        ).status_code
        == 302
    )
    summary = build_profile_summary(user)
    assert summary.personally_not_applicable_competencies == 0
    assert summary.personal_applicable_competency_count == 383


@pytest.mark.django_db
def test_personal_applicability_is_assessment_epoch_scoped(client, user, seeded):
    old_run = user.assessment_runs.get()
    protocol = PracticeProtocol.objects.filter(availability="active").order_by("stable_id").first()
    client.force_login(user)
    assert (
        client.post(
            reverse("growth:practice-context", kwargs={"slug": protocol.slug}),
            _context_post(old_run),
        ).status_code
        == 302
    )

    new_run = AssessmentRun.objects.create(
        stable_id="SYNTHETIC-M6I-02-REASSESSMENT",
        user=user,
        curriculum_version=old_run.curriculum_version,
        assessment_version=old_run.assessment_version,
        source=old_run.source,
        answers=old_run.answers,
        clarifier_answers=old_run.clarifier_answers,
        timing_data=old_run.timing_data,
        response_quality_result=old_run.response_quality_result,
        orientation_outputs=old_run.orientation_outputs,
        archetype_outputs=old_run.archetype_outputs,
        raw_lever_scores=old_run.raw_lever_scores,
        calibrated_lever_estimates=old_run.calibrated_lever_estimates,
        lever_confidence=old_run.lever_confidence,
    )
    LeverBaseline.objects.bulk_create(
        [
            LeverBaseline(
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
            for baseline in LeverBaseline.objects.filter(assessment_run=old_run)
        ]
    )
    synchronize_all_composite_score_states()
    summary = build_profile_summary(user)

    assert summary.assessment_run == new_run
    assert summary.personally_not_applicable_competencies == 0


@pytest.mark.django_db
def test_tampered_context_fails_closed_only_for_personal_coverage(client, user, seeded):
    run = user.assessment_runs.get()
    protocol = PracticeProtocol.objects.filter(availability="active").order_by("stable_id").first()
    client.force_login(user)
    assert (
        client.post(
            reverse("growth:practice-context", kwargs={"slug": protocol.slug}),
            _context_post(run),
        ).status_code
        == 302
    )
    context = PracticeContext.objects.get(assessment_run=run, protocol=protocol)
    table = connection.ops.quote_name(PracticeContext._meta.db_table)
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {table} SET content_hash = %s WHERE stable_id = %s",
            ["0" * 64, context.pk.hex],
        )

    summary = build_profile_summary(user)
    assert summary.composite_state_active is True
    assert summary.personal_applicability_active is False
    assert "Canonical coverage is unchanged" in summary.personal_coverage_error
    response = client.get(reverse("growth:profile"))
    assert b"Personal-applicable coverage is unavailable" in response.content
