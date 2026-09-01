from dataclasses import replace
from decimal import Decimal

import yaml
from django.conf import settings
from jsonschema import Draft202012Validator

from growth.domain.composite_scoring import (
    CompetencyProjectionInput,
    CompositeScoringError,
    LeverAssessmentInput,
    blended_relationship_weights,
    build_assessment_projection,
    build_completion_state,
    closeout_credit,
    policy_from_contract,
)


def _policy():
    contract = yaml.safe_load(
        (settings.BASE_DIR / "contracts" / "composite-closeout-scoring.yaml").read_text()
    )
    return policy_from_contract(contract)


def _small_policy():
    return replace(
        _policy(),
        expected_families=2,
        expected_levers=3,
        expected_domains=2,
        expected_competencies=3,
        expected_practices=3,
        expected_actions=9,
    )


def _small_projection():
    policy = _small_policy()
    projection = build_assessment_projection(
        levers=(
            LeverAssessmentInput("L1", "F1", Decimal("0.20"), Decimal("0.80")),
            LeverAssessmentInput("L2", "F2", Decimal("0.80"), Decimal("0.60")),
            LeverAssessmentInput("L3", "F2", None, Decimal("0")),
        ),
        competencies=(
            CompetencyProjectionInput("C1", "D1", {"L1": Decimal("0.60"), "L2": Decimal("0.40")}),
            CompetencyProjectionInput("C2", "D1", {"L2": Decimal("1.00")}),
            CompetencyProjectionInput("C3", "D2", {"L3": Decimal("1.00")}),
        ),
        policy=policy,
    )
    return policy, projection


def test_policy_and_relationship_blend_are_exact_middle_ground():
    policy = _policy()
    weights = blended_relationship_weights({"L1": Decimal("0.60"), "L2": Decimal("0.40")}, policy)

    assert weights == {"L1": Decimal("0.550"), "L2": Decimal("0.450")}
    assert sum(weights.values()) == Decimal("1.000")
    assert (
        policy.priority_lever_weight,
        policy.priority_family_weight,
        policy.priority_domain_weight,
    ) == (Decimal("0.50"), Decimal("0.25"), Decimal("0.25"))


def test_composite_scoring_contract_matches_its_fixed_schema():
    contract = yaml.safe_load(
        (settings.BASE_DIR / "contracts" / "composite-closeout-scoring.yaml").read_text()
    )
    schema = yaml.safe_load(
        (settings.BASE_DIR / "contracts" / "composite-closeout-scoring.schema.json").read_text()
    )

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(contract)


def test_closeout_credit_is_075_at_current_catalog_minimum_and_one_when_full():
    policy = _policy()

    assert closeout_credit(
        completed_actions=2,
        total_actions=3,
        minimum_completed=2,
        policy=policy,
    ) == Decimal("0.75")
    assert closeout_credit(
        completed_actions=3,
        total_actions=3,
        minimum_completed=2,
        policy=policy,
    ) == Decimal("1.00")
    assert closeout_credit(
        completed_actions=3,
        total_actions=4,
        minimum_completed=3,
        policy=policy,
    ) == Decimal("0.75")
    assert closeout_credit(
        completed_actions=4,
        total_actions=4,
        minimum_completed=3,
        policy=policy,
    ) == Decimal("1.00")


def test_closeout_rejects_below_threshold_counts():
    policy = _policy()

    try:
        closeout_credit(
            completed_actions=1,
            total_actions=3,
            minimum_completed=2,
            policy=policy,
        )
    except CompositeScoringError as exc:
        assert "satisfy the closeout minimum" in str(exc)
    else:  # pragma: no cover - assertion helper without pytest dependency
        raise AssertionError("Below-threshold closeout unexpectedly received credit.")


def test_assessment_projection_inherits_unassessed_lever_from_its_family():
    _policy_value, projection = _small_projection()

    assert projection["counts"] == {
        "families": 2,
        "levers": 3,
        "domains": 2,
        "competencies": 3,
    }
    assert projection["levers"]["L3"]["source"] == "family_inherited"
    assert projection["levers"]["L3"]["estimate"] == "0.800000000000"
    assert set(projection["competencies"]) == {"C1", "C2", "C3"}
    assert projection["projection_hash"]


def test_completion_state_propagates_shared_credit_and_full_requires_all_members():
    policy, projection = _small_projection()
    partial = build_completion_state(
        assessment_projection=projection,
        competency_credits={"C1": Decimal("0.75")},
        policy=policy,
    )

    assert partial["canonical_coverage"] == "0.250000000000"
    assert partial["domains"]["D1"]["coverage"] == "0.375000000000"
    assert Decimal(partial["levers"]["L1"]["coverage"]) == Decimal("0.75")
    assert Decimal(partial["levers"]["L2"]["coverage"]) < Decimal("0.75")
    assert Decimal(partial["competencies"]["C1"]["remaining_priority"]) > 0

    full = build_completion_state(
        assessment_projection=projection,
        competency_credits={
            "C1": Decimal("1"),
            "C2": Decimal("1"),
            "C3": Decimal("1"),
        },
        policy=policy,
    )
    assert full["canonical_coverage"] == "1.000000000000"
    assert all(Decimal(row["coverage"]) == 1 for row in full["families"].values())
    assert all(Decimal(row["coverage"]) == 1 for row in full["levers"].values())
    assert all(Decimal(row["coverage"]) == 1 for row in full["domains"].values())
    assert all(Decimal(row["remaining_priority"]) == 0 for row in full["competencies"].values())
