from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model

from growth.domain.context import (
    ASSESSMENT_FACTOR_IDS,
    FACTOR_DEFINITIONS,
    PRACTICE_FACTOR_IDS,
    ContextContractError,
    ContextFactorValue,
    ContextValueState,
    DeferReason,
    PracticeDisposition,
    build_assessment_context_snapshot,
    build_practice_context_snapshot,
)
from growth.models import (
    AssessmentContext,
    AssessmentRun,
    Competency,
    CurriculumVersion,
    PracticeContext,
    PracticeProtocol,
)
from growth.services.context import (
    ContextServiceError,
    PracticeContextInput,
    latest_assessment_context,
    latest_practice_context,
    record_context_bundle,
)

FIXTURE = Path(__file__).parent / "fixtures" / "context" / "context_v1.json"


def assessment_factors(*, capacity=2, season="maintenance"):
    return {
        "season": ContextFactorValue(ContextValueState.PROVIDED, season),
        "capacity": ContextFactorValue(ContextValueState.PROVIDED, capacity),
    }


def practice_factors(*, state=ContextValueState.PROVIDED, values=None):
    values = values or {
        "applicability": 4,
        "importance": 3,
        "readiness": 2,
        "urgency": 1,
        "opportunity_resources": 2,
        "burden": 3,
    }
    return {
        factor_id: ContextFactorValue(state, values[factor_id] if state == "provided" else None)
        for factor_id in PRACTICE_FACTOR_IDS
    }


def deferred_practice_factors():
    factors = practice_factors()
    factors["readiness"] = ContextFactorValue(ContextValueState.DEFERRED)
    return factors


def clone_assessment(run: AssessmentRun, stable_id: str) -> AssessmentRun:
    return AssessmentRun.objects.create(
        stable_id=stable_id,
        user=run.user,
        curriculum_version=run.curriculum_version,
        assessment_version=run.assessment_version,
        source=AssessmentRun.Source.APPLICATION,
        answers={},
        clarifier_answers={},
        timing_data={},
        response_quality_result={},
        orientation_outputs={},
        archetype_outputs=[],
        raw_lever_scores={},
        calibrated_lever_estimates={},
        lever_confidence={},
    )


def test_factor_definitions_are_exact_bounded_and_nonjudgmental():
    assert tuple(FACTOR_DEFINITIONS) == (*ASSESSMENT_FACTOR_IDS, *PRACTICE_FACTOR_IDS)
    assert ASSESSMENT_FACTOR_IDS == ("season", "capacity")
    assert PRACTICE_FACTOR_IDS == (
        "applicability",
        "importance",
        "readiness",
        "urgency",
        "opportunity_resources",
        "burden",
    )
    for definition in FACTOR_DEFINITIONS.values():
        assert definition.definition
        if definition.value_kind == "ordinal":
            assert (definition.minimum, definition.maximum) == (0, 4)
        else:
            assert definition.allowed_values
    assert "no deficit" in FACTOR_DEFINITIONS["applicability"].definition
    assert "without judging" in FACTOR_DEFINITIONS["capacity"].definition
    assert "not a measure of moral worth" in FACTOR_DEFINITIONS["importance"].definition


@pytest.mark.parametrize("value", [0, 4])
def test_numeric_boundaries_are_accepted(value):
    factors = assessment_factors(capacity=value)
    snapshot = build_assessment_context_snapshot(
        assessment_epoch_id="ASSESSMENT-BOUNDARY",
        factors=factors,
    )
    assert snapshot.payload["factors"]["capacity"]["value"] == value


@pytest.mark.parametrize("value", [-1, 5, True, 2.0, "2"])
def test_numeric_malformed_and_out_of_range_values_fail_closed(value):
    with pytest.raises(ContextContractError, match="capacity value"):
        build_assessment_context_snapshot(
            assessment_epoch_id="ASSESSMENT-INVALID",
            factors=assessment_factors(capacity=value),
        )


@pytest.mark.parametrize("state", ["unknown", "not_applicable", "deferred"])
def test_nonprovided_states_reject_hidden_values(state):
    factors = assessment_factors()
    factors["capacity"] = ContextFactorValue(state, 0)
    with pytest.raises(ContextContractError, match="must be null"):
        build_assessment_context_snapshot(
            assessment_epoch_id="ASSESSMENT-NO-HIDDEN-DEFAULT",
            factors=factors,
        )


def test_missing_extra_and_unknown_contract_inputs_fail_closed():
    factors = assessment_factors()
    del factors["season"]
    with pytest.raises(ContextContractError, match="missing season"):
        build_assessment_context_snapshot(assessment_epoch_id="A-1", factors=factors)
    factors["invented"] = ContextFactorValue("unknown")
    with pytest.raises(ContextContractError, match="unexpected invented"):
        build_assessment_context_snapshot(assessment_epoch_id="A-1", factors=factors)
    with pytest.raises(ContextContractError, match="Unsupported context contract"):
        build_assessment_context_snapshot(
            assessment_epoch_id="A-1",
            factors=assessment_factors(),
            contract_version="GG-CONTEXT-2.0",
        )


def test_snapshot_and_hash_are_deterministic_for_semantically_identical_input():
    forward = assessment_factors()
    reverse = OrderedDict(reversed(tuple(forward.items())))
    first = build_assessment_context_snapshot(
        assessment_epoch_id="ASSESSMENT-DETERMINISTIC",
        factors=forward,
    )
    second = build_assessment_context_snapshot(
        assessment_epoch_id="ASSESSMENT-DETERMINISTIC",
        factors=reverse,
    )
    assert first == second
    assert first.content_hash == "e6c925e15771ffcfc09448ffecaf520aec35862b0f749aa9722dab4a1446302c"


def test_golden_practice_snapshot_replays_exactly():
    fixture = json.loads(FIXTURE.read_text())
    case = fixture["practice_case"]
    snapshot = build_practice_context_snapshot(
        assessment_epoch_id=case["assessment_epoch_id"],
        protocol_stable_id=case["protocol_stable_id"],
        factors=case["factors"],
        disposition=case["disposition"],
        defer_reason=case["defer_reason"],
        review_horizon_days=case["review_horizon_days"],
        contract_version=fixture["contract_version"],
    )
    assert snapshot.content_hash == case["expected_hash"]


def test_unknown_not_applicable_and_deferred_have_distinct_hashes():
    hashes = set()
    for state in ContextValueState:
        if state is ContextValueState.PROVIDED:
            continue
        factors = assessment_factors()
        factors["capacity"] = ContextFactorValue(state)
        hashes.add(
            build_assessment_context_snapshot(
                assessment_epoch_id="ASSESSMENT-STATES",
                factors=factors,
            ).content_hash
        )
    assert len(hashes) == 3


def test_defer_requires_reason_deferred_factor_and_bounded_horizon():
    common = {
        "assessment_epoch_id": "ASSESSMENT-DEFER",
        "protocol_stable_id": "PRACTICE-FRIENDSHIP-01",
        "factors": deferred_practice_factors(),
        "disposition": PracticeDisposition.DEFERRED,
    }
    with pytest.raises(ContextContractError, match="requires a defer reason"):
        build_practice_context_snapshot(**common)
    for horizon in (1, 366):
        snapshot = build_practice_context_snapshot(
            **common,
            defer_reason=DeferReason.USER_CHOICE,
            review_horizon_days=horizon,
        )
        assert snapshot.payload["defer"]["review_horizon_days"] == horizon
    for horizon in (0, 367, True):
        with pytest.raises(ContextContractError, match="Review horizon"):
            build_practice_context_snapshot(
                **common,
                defer_reason=DeferReason.USER_CHOICE,
                review_horizon_days=horizon,
            )


@pytest.mark.django_db
def test_record_bundle_is_atomic_versioned_and_idempotent(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    item = PracticeContextInput(protocol=protocol, factors=practice_factors())

    first = record_context_bundle(
        user=user,
        assessment_run=run,
        assessment_factors=assessment_factors(),
        practice_inputs=(item,),
    )
    repeat = record_context_bundle(
        user=user,
        assessment_run=run,
        assessment_factors=assessment_factors(),
        practice_inputs=(item,),
    )
    assert first.assessment_created is True
    assert first.practice_created == (True,)
    assert repeat.assessment_created is False
    assert repeat.practice_created == (False,)
    assert repeat.assessment_context.pk == first.assessment_context.pk
    assert AssessmentContext.objects.filter(assessment_run=run).count() == 1
    assert PracticeContext.objects.filter(assessment_run=run, protocol=protocol).count() == 1

    changed = record_context_bundle(
        user=user,
        assessment_run=run,
        assessment_factors=assessment_factors(capacity=3),
        practice_inputs=(item,),
    )
    assert changed.assessment_context.revision == 2
    assert changed.practice_created == (False,)

    invalid = PracticeContextInput(
        protocol=protocol,
        factors={**practice_factors(), "readiness": ContextFactorValue("provided", 5)},
    )
    before = (AssessmentContext.objects.count(), PracticeContext.objects.count())
    with pytest.raises(ContextContractError):
        record_context_bundle(
            user=user,
            assessment_run=run,
            assessment_factors=assessment_factors(capacity=4),
            practice_inputs=(invalid,),
        )
    assert (AssessmentContext.objects.count(), PracticeContext.objects.count()) == before


@pytest.mark.django_db
def test_context_is_explicitly_user_and_assessment_epoch_scoped(user, seeded):
    first_run = AssessmentRun.objects.get(user=user)
    second_run = clone_assessment(first_run, "ASSESSMENT-SECOND-EPOCH")
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    item = PracticeContextInput(protocol=protocol, factors=practice_factors())
    first = record_context_bundle(
        user=user,
        assessment_run=first_run,
        assessment_factors=assessment_factors(),
        practice_inputs=(item,),
    )
    assert latest_assessment_context(user=user, assessment_run=second_run) is None
    assert latest_practice_context(user=user, assessment_run=second_run, protocol=protocol) is None

    second = record_context_bundle(
        user=user,
        assessment_run=second_run,
        assessment_factors=assessment_factors(),
        practice_inputs=(item,),
    )
    assert second.assessment_context.content_hash != first.assessment_context.content_hash
    assert second.practice_contexts[0].content_hash != first.practice_contexts[0].content_hash

    other = get_user_model().objects.create_user(username="other-context-user")
    with pytest.raises(ContextServiceError, match="must own"):
        latest_assessment_context(user=other, assessment_run=first_run)


@pytest.mark.django_db
def test_protocol_from_another_curriculum_epoch_fails_closed(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    version = CurriculumVersion.objects.create(
        stable_id="CURRICULUM-CONTEXT-OTHER",
        curriculum_version="other",
        model_version="other",
        assessment_version="other",
        source_hash="f" * 64,
        active=False,
    )
    competency = Competency.objects.create(
        stable_id="99.99",
        curriculum_version=version,
        domain_id="99",
        domain_name="Synthetic test domain",
        name="Synthetic test competency",
        scope="Test-only curriculum isolation.",
        evidence_of_progress="Not applicable outside this test.",
        applicability="test only",
        normative_status="elective",
    )
    protocol = PracticeProtocol.objects.create(
        stable_id="PRACTICE-CONTEXT-OTHER",
        slug="practice-context-other",
        name="Synthetic context isolation protocol",
        parent_competency=competency,
        duration_days=1,
        recommendation_reason="Test only.",
        applicability_prompt="Test only.",
        setup_prompt="Test only.",
        privacy_and_boundaries="Test only.",
    )
    with pytest.raises(ContextServiceError, match="assessment epoch curriculum"):
        record_context_bundle(
            user=user,
            assessment_run=run,
            assessment_factors=assessment_factors(),
            practice_inputs=(PracticeContextInput(protocol=protocol, factors=practice_factors()),),
        )
    assert not AssessmentContext.objects.filter(assessment_run=run).exists()


@pytest.mark.django_db
def test_duplicate_practice_inputs_fail_before_any_write(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    item = PracticeContextInput(protocol=protocol, factors=practice_factors())
    with pytest.raises(ContextServiceError, match="repeats protocol"):
        record_context_bundle(
            user=user,
            assessment_run=run,
            assessment_factors=assessment_factors(),
            practice_inputs=(item, item),
        )
    assert not AssessmentContext.objects.filter(assessment_run=run).exists()
    assert not PracticeContext.objects.filter(assessment_run=run).exists()
