from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

import pytest

from growth.domain.context_priority import (
    MAX_CONTEXT_PRIORITY_CANDIDATES,
    AlternativeRequest,
    CandidatePriorityDisposition,
    ContextPriorityCandidateInput,
    ContextPriorityContractError,
    PriorityFactorValue,
    build_context_priority_result,
)


def assessment_factors(*, capacity=2, capacity_state="provided", season="maintenance"):
    return {
        "season": PriorityFactorValue("provided", season),
        "capacity": PriorityFactorValue(
            capacity_state,
            capacity if capacity_state == "provided" else None,
        ),
    }


def candidate_factors(*, values=None):
    resolved = values or {
        "applicability": 4,
        "importance": 3,
        "readiness": 2,
        "urgency": 1,
        "opportunity_resources": 2,
        "burden": 3,
    }
    return {
        factor_id: PriorityFactorValue("provided", value) for factor_id, value in resolved.items()
    }


def candidate(
    protocol_id="PRACTICE-FRIENDSHIP-01",
    *,
    base="0.8000",
    factors=None,
    disposition="considering",
    context_hash=None,
):
    return ContextPriorityCandidateInput(
        protocol_stable_id=protocol_id,
        base_priority=Decimal(base),
        practice_context_hash=context_hash or ("b" * 64),
        factors=factors or candidate_factors(),
        disposition=disposition,
    )


def build(*, candidates=None, assessment=None, alternative=None):
    return build_context_priority_result(
        assessment_epoch_id="ASSESSMENT-CONTEXT-PRIORITY",
        assessment_context_hash="a" * 64,
        assessment_factors=assessment or assessment_factors(),
        candidates=tuple(candidates or (candidate(),)),
        alternative_request=alternative,
    )


def test_exact_multiplicative_formula_normalization_and_burden_inversion():
    result = build()
    row = result.candidates[0]
    assert row.context_priority == Decimal("0.0047")
    multipliers = {item.factor_id: item.normalized_multiplier for item in row.factor_contributions}
    assert multipliers == {
        "applicability": Decimal("1"),
        "importance": Decimal("0.75"),
        "readiness": Decimal("0.5"),
        "urgency": Decimal("0.25"),
        "opportunity_resources": Decimal("0.5"),
        "burden": Decimal("0.25"),
    }
    assert result.capacity.normalized_multiplier == Decimal("0.5")


def test_formula_quantizes_half_up_once_and_explicit_zero_remains_eligible():
    all_high = candidate_factors(
        values={
            "applicability": 4,
            "importance": 4,
            "readiness": 4,
            "urgency": 4,
            "opportunity_resources": 4,
            "burden": 0,
        }
    )
    rounded = build(candidates=(candidate(base="0.0001", factors=all_high),))
    assert rounded.candidates[0].context_priority == Decimal("0.0001")

    zero_factors = dict(all_high)
    zero_factors["readiness"] = PriorityFactorValue("provided", 0)
    zero = build(candidates=(candidate(factors=zero_factors),))
    assert zero.candidates[0].disposition is CandidatePriorityDisposition.ELIGIBLE
    assert zero.candidates[0].context_priority == Decimal("0.0000")
    assert "explicit_zero_factor" in zero.candidates[0].explanation_codes


def test_not_applicable_deferred_unknown_and_missing_capacity_remain_distinct():
    not_applicable = candidate_factors()
    not_applicable["applicability"] = PriorityFactorValue("not_applicable")
    not_applicable["readiness"] = PriorityFactorValue("deferred")
    deferred = candidate_factors()
    deferred["readiness"] = PriorityFactorValue("deferred")
    unknown = candidate_factors()
    unknown["urgency"] = PriorityFactorValue("unknown")
    result = build(
        candidates=(
            candidate("PRACTICE-A", factors=not_applicable, disposition="deferred"),
            candidate("PRACTICE-B", factors=deferred, disposition="deferred"),
            candidate("PRACTICE-C", factors=unknown),
        )
    )
    dispositions = {item.protocol_stable_id: item.disposition.value for item in result.candidates}
    assert dispositions == {
        "PRACTICE-A": "not_applicable",
        "PRACTICE-B": "deferred",
        "PRACTICE-C": "missing_context",
    }
    assert result.ranked_candidate_ids == ()
    assert all(item.context_priority is None for item in result.candidates)

    missing_capacity = build(assessment=assessment_factors(capacity_state="unknown"))
    assert missing_capacity.ranking_disposition.value == "missing_context"
    assert missing_capacity.candidates[0].disposition.value == "missing_context"
    assert missing_capacity.candidates[0].context_priority is None


def test_ordering_uses_context_then_base_then_stable_id_and_withholds_noneligible():
    all_high = candidate_factors(
        values={key: (0 if key == "burden" else 4) for key in candidate_factors()}
    )
    not_applicable = dict(all_high)
    not_applicable["applicability"] = PriorityFactorValue("not_applicable")
    result = build(
        candidates=(
            candidate("PRACTICE-Z", base="0.5000", factors=all_high, context_hash="1" * 64),
            candidate("PRACTICE-A", base="0.5000", factors=all_high, context_hash="2" * 64),
            candidate("PRACTICE-HIGH-BASE", base="0.6000", factors=all_high, context_hash="3" * 64),
            candidate(
                "PRACTICE-WITHHELD", base="1.0000", factors=not_applicable, context_hash="4" * 64
            ),
        )
    )
    assert result.ranked_candidate_ids == (
        "PRACTICE-HIGH-BASE",
        "PRACTICE-A",
        "PRACTICE-Z",
    )
    assert result.primary_protocol_stable_id == "PRACTICE-HIGH-BASE"


def test_alternative_is_distinct_partial_cohort_only_and_explicit_when_none_exists():
    not_applicable = candidate_factors()
    not_applicable["applicability"] = PriorityFactorValue("not_applicable")
    source = candidate("PRACTICE-SOURCE", factors=not_applicable, context_hash="1" * 64)
    target = candidate("PRACTICE-TARGET", context_hash="2" * 64)
    selected = build(
        candidates=(source, target),
        alternative=AlternativeRequest("PRACTICE-SOURCE", "not_applicable"),
    )
    assert selected.alternative.status.value == "selected"
    assert selected.alternative.target_protocol_stable_id == "PRACTICE-TARGET"
    assert (
        selected.alternative.target_protocol_stable_id
        != selected.alternative.source_protocol_stable_id
    )

    none = build(
        candidates=(source,),
        alternative=AlternativeRequest("PRACTICE-SOURCE", "not_applicable"),
    )
    assert none.alternative.status.value == "no_eligible_alternative"
    assert none.alternative.target_protocol_stable_id is None
    with pytest.raises(ContextPriorityContractError, match="match"):
        build(
            candidates=(source, target),
            alternative=AlternativeRequest("PRACTICE-SOURCE", "deferred"),
        )


def test_deferred_alternative_selects_highest_ranked_distinct_eligible_candidate():
    deferred_factors = candidate_factors()
    deferred_factors["readiness"] = PriorityFactorValue("deferred")
    deferred_source = candidate(
        "PRACTICE-DEFERRED",
        factors=deferred_factors,
        disposition="deferred",
        context_hash="1" * 64,
    )
    lower = candidate("PRACTICE-LOWER", base="0.5000", context_hash="2" * 64)
    higher = candidate("PRACTICE-HIGHER", base="0.7000", context_hash="3" * 64)

    result = build(
        candidates=(lower, deferred_source, higher),
        alternative=AlternativeRequest("PRACTICE-DEFERRED", "deferred"),
    )

    assert result.alternative.status.value == "selected"
    assert result.alternative.source_disposition == "deferred"
    assert result.alternative.target_protocol_stable_id == "PRACTICE-HIGHER"
    assert result.alternative.explanation_codes == ("alternative_after_deferred",)


def test_mapping_order_and_candidate_order_do_not_change_canonical_result():
    first_candidate = candidate("PRACTICE-A", context_hash="1" * 64)
    reverse_factors = OrderedDict(reversed(tuple(first_candidate.factors.items())))
    reordered = candidate("PRACTICE-A", factors=reverse_factors, context_hash="1" * 64)
    second = candidate("PRACTICE-B", base="0.7000", context_hash="2" * 64)
    forward = build(candidates=(first_candidate, second))
    reverse = build(candidates=(second, reordered))
    assert forward.canonical_json == reverse.canonical_json
    assert forward.content_hash == reverse.content_hash


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ({"base_priority": Decimal("NaN")}, "finite Decimal"),
        ({"base_priority": Decimal("1.1")}, "finite Decimal"),
        ({"base_priority": 1}, "finite Decimal"),
        ({"practice_context_hash": "bad"}, "SHA-256"),
        ({"context_contract_version": "GG-CONTEXT-2.0"}, "unsupported"),
    ],
)
def test_malformed_candidate_values_fail_closed(mutation, match):
    row = candidate()
    values = {**row.__dict__, **mutation}
    with pytest.raises(ContextPriorityContractError, match=match):
        build(candidates=(ContextPriorityCandidateInput(**values),))


def test_bool_out_of_range_duplicate_and_resource_bound_fail_closed():
    factors = candidate_factors()
    factors["readiness"] = PriorityFactorValue("provided", True)
    with pytest.raises(ContextPriorityContractError, match="integer from 0 to 4"):
        build(candidates=(candidate(factors=factors),))
    with pytest.raises(ContextPriorityContractError, match="unique"):
        build(candidates=(candidate(), candidate()))
    oversized = tuple(
        candidate(f"PRACTICE-{index:03d}", context_hash=f"{index:064x}")
        for index in range(MAX_CONTEXT_PRIORITY_CANDIDATES + 1)
    )
    with pytest.raises(ContextPriorityContractError, match="at most 383"):
        build(candidates=oversized)

    invalid_assessment = assessment_factors(season="invented")
    with pytest.raises(ContextPriorityContractError, match="supported category"):
        build(assessment=invalid_assessment)


def test_result_snapshot_uses_only_allowlisted_structured_fields():
    result = build()
    payload = result.as_dict()
    assert payload["sha256"] == result.content_hash
    assert payload["canonical_json"] == result.canonical_json
    encoded = result.canonical_json.lower()
    for forbidden in (
        "username",
        "user_id",
        "record_id",
        "timestamp",
        "mission",
        "principles",
        "anti_goals",
        "audit",
        "assessment_answers",
        "evidence_payload",
        "private_narrative",
    ):
        assert forbidden not in encoded
