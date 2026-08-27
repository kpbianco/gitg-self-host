import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone

from growth.domain.scoring import (
    SCORING_ALGORITHM_VERSION,
    BaselineMass,
    LeverWeight,
    ScoringContractError,
    ScoringEvidence,
    project_scores,
    reconstruct_published_baseline_mass,
)
from growth.models import LeverBaseline, PracticeCheckIn, PracticeProtocol
from growth.services.assessment import AssessmentPayloadError, persist_assessment_run
from growth.services.practice import save_check_in, start_practice
from growth.services.scoring import (
    PRODUCTION_SCORE_ELIGIBILITY_CONTRACT_VERSION,
    PRODUCTION_SCORE_MAPPING_FINGERPRINT,
    build_user_shadow_projection,
    validate_production_scoring_protocol,
)
from tests.test_assessment_integration import golden_payload

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "scoring" / "shadow_v1.json"


def _decimal_rows(items, row_type):
    return tuple(
        row_type(
            **{
                key: Decimal(value) if key not in {"lever_id"} else value
                for key, value in item.items()
            }
        )
        for item in items
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
        "internal_resistance": 2,
        "expected_reciprocity": 2,
        "observed_reciprocity": 2,
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
        .order_by("assessment_run_id", "lever_id")
        .values_list(
            "assessment_run_id",
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


def test_shadow_scoring_golden_fixture_is_exact_and_direction_complete():
    fixture = json.loads(FIXTURE_PATH.read_text())
    baselines = {
        lever_id: BaselineMass(
            lever_id=lever_id,
            alpha=Decimal(values["alpha"]),
            beta=Decimal(values["beta"]),
            confidence=Decimal(values["confidence"]),
        )
        for lever_id, values in fixture["baselines"].items()
    }
    weights = _decimal_rows(fixture["weights"], LeverWeight)
    events = tuple(
        ScoringEvidence(
            event_key=item["event_key"],
            action_stable_id=item["action_stable_id"],
            performance=Decimal(item["performance"]),
            base_evidence_mass=Decimal(item["base_evidence_mass"]),
            direction=item["direction"],
        )
        for item in fixture["events"]
    )

    projection = project_scores(baselines=baselines, weights=weights, events=events)

    assert fixture["algorithm_version"] == projection.algorithm_version
    assert projection.algorithm_version == SCORING_ALGORITHM_VERSION
    assert projection.event_count == fixture["expected"]["event_count"]
    assert projection.scored_event_count == fixture["expected"]["scored_event_count"]
    assert projection.withheld_event_count == fixture["expected"]["withheld_event_count"]
    for lever in projection.levers:
        expected = fixture["expected"]["levers"][lever.lever_id]
        assert lever.contributions[0].task_coefficient == Decimal(expected["task_coefficient"])
        for field in (
            "evidence_mass",
            "success_mass",
            "failure_mass",
            "projected_alpha",
            "projected_beta",
            "projected_estimate",
            "projected_confidence",
        ):
            assert getattr(lever, field) == Decimal(expected[field]), (
                lever.lever_id,
                field,
            )
        assert lever.projected_confidence >= lever.baseline_confidence
        withheld = [item.event_key for item in lever.contributions if not item.included]
        assert withheld == fixture["expected"]["withheld_event_keys"]
        contradictory = next(
            item for item in lever.contributions if item.event_key == "E-CONTRADICTS"
        )
        assert contradictory.success_mass == 0
        assert contradictory.failure_mass == contradictory.evidence_mass


def test_shadow_scoring_rejects_malformed_weights_and_duplicate_events():
    baseline = {"L26": BaselineMass("L26", Decimal("1"), Decimal("1"), Decimal(".4"))}
    event = ScoringEvidence("E1", "A1", Decimal("1"), Decimal(".4"), "supports")

    with pytest.raises(ScoringContractError, match="sum to"):
        project_scores(
            baselines=baseline,
            weights=(LeverWeight("L26", Decimal(".9"), Decimal("10")),),
            events=(event,),
        )

    with pytest.raises(ScoringContractError, match="same evidence event twice"):
        project_scores(
            baselines=baseline,
            weights=(LeverWeight("L26", Decimal("1"), Decimal("10")),),
            events=(event, event),
        )

    with pytest.raises(ScoringContractError, match="must be finite"):
        project_scores(
            baselines=baseline,
            weights=(LeverWeight("L26", Decimal("1"), Decimal("10")),),
            events=(
                ScoringEvidence(
                    "E-NAN",
                    "A1",
                    Decimal("NaN"),
                    Decimal(".4"),
                    "supports",
                ),
            ),
        )

    withheld = project_scores(
        baselines=baseline,
        weights=(LeverWeight("L26", Decimal("1"), Decimal("10")),),
        events=(
            ScoringEvidence(
                "E2",
                "A1",
                Decimal("1"),
                Decimal(".4"),
                "inconclusive",
            ),
        ),
    )
    assert withheld.levers[0].evidence_mass == 0
    assert withheld.levers[0].projected_confidence == Decimal("0.4000")


def test_published_baseline_reconstruction_is_conservative():
    reconstructed = reconstruct_published_baseline_mass(
        lever_id="L26",
        raw_self_report=Decimal("0.2727"),
        calibrated_estimate=Decimal("0.3336"),
        evidence_confidence=Decimal("0.5028"),
    )

    assert reconstructed == BaselineMass(
        lever_id="L26",
        alpha=Decimal("0.871578"),
        beta=Decimal("1.741066"),
        confidence=Decimal("0.5028"),
    )
    assert (
        reconstruct_published_baseline_mass(
            lever_id="L32",
            raw_self_report=Decimal("0.5000"),
            calibrated_estimate=Decimal("0.5000"),
            evidence_confidence=Decimal("0.5351"),
        )
        is None
    )


@pytest.mark.django_db
def test_seed_links_friendship_protocol_to_canonical_weights_and_baseline_masses(user, seeded):
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    links = protocol.parent_competency.lever_links.order_by("-weight", "lever_id")
    reviewed_links = validate_production_scoring_protocol(protocol)

    assert PRODUCTION_SCORE_ELIGIBILITY_CONTRACT_VERSION == "GG-PRODUCTION-SCORE-ELIGIBILITY-2.0"
    assert len(PRODUCTION_SCORE_MAPPING_FINGERPRINT) == 64
    assert protocol.parent_competency_id == "17.03"
    assert {link.lever_id for link in reviewed_links} == {"L10", "L23", "L24", "L26"}
    assert list(links.values_list("lever_id", "weight")) == [
        ("L26", Decimal("0.6500")),
        ("L10", Decimal("0.1500")),
        ("L23", Decimal("0.1000")),
        ("L24", Decimal("0.1000")),
    ]
    assert set(protocol.target_levers.values_list("stable_id", flat=True)) == {
        "L23",
        "L24",
        "L26",
    }
    l26 = LeverBaseline.objects.get(
        assessment_run__source="pilot_seed",
        lever_id="L26",
    )
    assert l26.baseline_alpha == Decimal("0.871578")
    assert l26.baseline_beta == Decimal("1.741066")
    assert l26.baseline_mass_source == LeverBaseline.BaselineMassSource.PUBLISHED_RECONSTRUCTION
    neutral = LeverBaseline.objects.get(
        assessment_run__source="pilot_seed",
        lever_id="L32",
    )
    assert neutral.baseline_alpha is None
    assert neutral.baseline_beta is None
    assert neutral.baseline_mass_source == ""


@pytest.mark.django_db
def test_production_contract_requires_exact_recommendation_targets(user, seeded):
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    protocol.target_levers.remove(protocol.target_levers.get(stable_id="L23"))

    with pytest.raises(ScoringContractError, match="recommendation targets"):
        validate_production_scoring_protocol(protocol)


@pytest.mark.django_db
def test_canonical_assessment_persists_exact_baseline_masses_and_rejects_drift(user, seeded):
    payload = golden_payload()
    run, created = persist_assessment_run(user, payload)
    expected = payload["result"]["levers"]["L34"]
    baseline = run.lever_baselines.get(lever_id="L34")

    assert created is True
    assert baseline.baseline_alpha == Decimal(str(expected["alpha"]))
    assert baseline.baseline_beta == Decimal(str(expected["beta"]))
    assert baseline.baseline_mass_source == LeverBaseline.BaselineMassSource.CANONICAL_RESULT

    drifted = golden_payload()
    drifted["result"]["levers"]["L34"]["alpha"] += 0.1
    with pytest.raises(AssessmentPayloadError, match="baseline masses"):
        persist_assessment_run(user, drifted)

    missing_raw = golden_payload()
    missing_raw["result"]["levers"]["L34"]["raw_self_report"] = None
    with pytest.raises(AssessmentPayloadError, match="requires raw score"):
        persist_assessment_run(user, missing_raw)


@pytest.mark.django_db
def test_profile_shadow_projection_is_read_only_and_excludes_drafts(client, user, seeded):
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    sprint = start_practice(
        user=user,
        protocol=protocol,
        person_or_context="Private context",
        start_date=date.today(),
    )
    actions = list(protocol.actions.order_by("sequence"))
    save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(
            actions[0],
            moved_beyond_transactional=True,
            meaningful_information_shared=True,
            follow_up_question_asked=True,
        ),
        submit=True,
    )
    save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(
            actions[1],
            action_completed=False,
            context_comparison=PracticeCheckIn.ContextComparison.SAME_CONTEXT,
            evidence_direction=PracticeCheckIn.EvidenceDirection.MIXED,
            contradictory_evidence="The result was mixed.",
        ),
        submit=True,
    )
    save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(
            actions[2],
            action_completed=False,
            context_comparison=PracticeCheckIn.ContextComparison.SAME_CONTEXT,
            evidence_direction=PracticeCheckIn.EvidenceDirection.CONTRADICTS,
            contradictory_evidence="The expected pattern did not occur.",
        ),
        submit=True,
    )
    save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(
            actions[0],
            context_comparison=PracticeCheckIn.ContextComparison.SAME_CONTEXT,
            evidence_direction=PracticeCheckIn.EvidenceDirection.INCONCLUSIVE,
        ),
        submit=True,
    )
    save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(
            actions[0],
            context_comparison=PracticeCheckIn.ContextComparison.SAME_CONTEXT,
        ),
        submit=False,
    )
    before = _baseline_snapshot(user)
    recommendation_targets_before = set(protocol.target_levers.values_list("stable_id", flat=True))

    shadow = build_user_shadow_projection(user)
    client.force_login(user)
    response = client.get(reverse("growth:profile"))
    content = response.content.decode()

    assert shadow.projection.event_count == 4
    assert shadow.projection.scored_event_count == 3
    assert shadow.projection.withheld_event_count == 1
    assert len(shadow.rows) == 4
    assert shadow.uses_reconstructed_baseline is True
    assert response.status_code == 200
    assert "What submitted evidence has changed" in content
    assert "Current · versioned" in content
    assert "immutable before-and-after" in content
    assert "completing this practice does not establish mastery" in content
    assert "0.6500" not in content
    assert "1.500000" not in content
    assert SCORING_ALGORITHM_VERSION not in content
    assert _baseline_snapshot(user) == before
    assert set(protocol.target_levers.values_list("stable_id", flat=True)) == (
        recommendation_targets_before
    )


@pytest.mark.django_db
def test_profile_shadow_projection_fails_closed_on_incomplete_evidence(client, user, seeded):
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    sprint = start_practice(
        user=user,
        protocol=protocol,
        person_or_context="Private context",
        start_date=date.today(),
    )
    missing = PracticeCheckIn.objects.create(
        sprint=sprint,
        action=protocol.actions.get(sequence=1),
        status=PracticeCheckIn.Status.SUBMITTED,
        action_attempted=True,
        submitted_at=timezone.now(),
    )
    before = _baseline_snapshot(user)
    client.force_login(user)

    response = client.get(reverse("growth:profile"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Evidence and score-state verification must pass" in content
    assert "Current 33%" not in content
    assert str(missing.pk) not in content
    assert _baseline_snapshot(user) == before


@pytest.mark.django_db
def test_profile_shadow_projection_hides_internal_ids_when_baseline_is_unavailable(user, seeded):
    LeverBaseline.objects.filter(
        assessment_run__source="pilot_seed",
        lever_id="L10",
    ).update(
        baseline_alpha=None,
        baseline_beta=None,
        baseline_mass_source="",
        raw_self_report=Decimal("0.5000"),
        calibrated_estimate=Decimal("0.5000"),
    )

    shadow = build_user_shadow_projection(user)

    assert shadow.projection is None
    assert (
        shadow.unavailable_reason
        == "This assessment does not contain enough baseline information for the preview."
    )
    assert "L10" not in shadow.unavailable_reason


@pytest.mark.django_db
def test_profile_shadow_projection_fails_closed_on_stored_baseline_drift(user, seeded):
    baseline = LeverBaseline.objects.get(
        assessment_run__source="pilot_seed",
        lever_id="L26",
    )
    LeverBaseline.objects.filter(pk=baseline.pk).update(
        baseline_alpha=baseline.baseline_alpha + Decimal("0.100000"),
    )

    shadow = build_user_shadow_projection(user)

    assert shadow.projection is None
    assert shadow.unavailable_reason == (
        "Baseline verification must pass before a projection can be shown."
    )


@pytest.mark.django_db
def test_profile_shadow_projection_fails_closed_without_reviewed_parent_link(user, seeded):
    PracticeProtocol.objects.filter(stable_id="PRACTICE-FRIENDSHIP-01").update(
        parent_competency=None,
    )

    shadow = build_user_shadow_projection(user)

    assert shadow.projection is None
    assert shadow.unavailable_reason == (
        "The practice has no reviewed competency-to-lever scoring link."
    )


@pytest.mark.django_db
def test_shadow_projection_excludes_events_from_an_older_assessment(user, seeded):
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    sprint = start_practice(
        user=user,
        protocol=protocol,
        person_or_context="Private context",
        start_date=date.today(),
    )
    save_check_in(
        sprint=sprint,
        cleaned_data=_check_in_data(
            protocol.actions.get(sequence=1),
            moved_beyond_transactional=True,
            meaningful_information_shared=True,
        ),
        submit=True,
    )
    current_run, _ = persist_assessment_run(user, golden_payload())

    shadow = build_user_shadow_projection(user)

    assert shadow.assessment_run == current_run
    assert shadow.projection.event_count == 0
    assert shadow.projection.scored_event_count == 0
