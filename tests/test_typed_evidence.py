import json
import shutil
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from growth.domain.typed_evidence import (
    TYPED_EVIDENCE_ALGORITHM_VERSION,
    TYPED_EVIDENCE_RULES_VERSION,
    TypedEvidenceContractError,
    TypedEvidenceInput,
    TypedObservationInput,
    evaluate_typed_evidence,
    load_typed_evidence_spec,
    replay_typed_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "evidence" / "typed_v1.json"
DATA_ROOT = ROOT / "data" / "evidence"
DECIMAL_FIELDS = (
    "performance",
    "quality",
    "independence",
    "context_breadth",
    "repetition_multiplier",
    "contradiction_level",
    "base_evidence_mass",
    "competency_performance",
)


def _fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _typed_input(raw):
    return TypedEvidenceInput(
        **{
            **raw,
            "observations": tuple(TypedObservationInput(**item) for item in raw["observations"]),
            "adverse_indicator_ids": tuple(raw["adverse_indicator_ids"]),
        }
    )


def _case(case_id):
    return next(item for item in _fixture()["cases"] if item["case_id"] == case_id)


def _simple_rules(kind, *, direction="at_least"):
    rule = {
        "measurement_id": "metric",
        "kind": kind,
        "role": "primary",
        "weight": "1",
        "allowed_provenance": ["firsthand_self_report"],
    }
    if kind == "boolean":
        rule["expected"] = True
    elif kind == "count":
        rule.update(direction=direction, minimum="0", target="5", maximum="10")
    elif kind == "bounded_frequency":
        rule.update(direction=direction, minimum="0", target="0.5", maximum="1")
    elif kind in {"duration", "objective"}:
        rule.update(
            direction=direction,
            minimum="0",
            target="5",
            maximum="10",
            unit="units",
        )
    elif kind == "attestation":
        rule.update(
            allowed_attestation_ids=["qualified_scope"],
            consent_required=True,
        )
    else:
        raise AssertionError(kind)
    return {
        "schema_version": TYPED_EVIDENCE_RULES_VERSION,
        "max_age_days": None,
        "measurements": [rule],
        "competency_measurement_ids": ["metric"],
        "transfer_disposition": "context_bound",
    }


def _simple_input(kind, value, **overrides):
    values = {
        "event_key": "EVENT-SIMPLE-01",
        "origin_key": "ORIGIN-SIMPLE-01",
        "assessment_epoch_id": "ASSESSMENT-EPOCH-001",
        "protocol_stable_id": "PRACTICE-SIMPLE-01",
        "action_stable_id": "PRACTICE-SIMPLE-01-A1",
        "competency_stable_id": "01.01",
        "scoring_policy_id": "SP-SHADOW-ONLY",
        "action_attempted": True,
        "action_completed": False,
        "observations": (
            TypedObservationInput(
                measurement_id="metric",
                kind=kind,
                state="observed",
                provenance_kind="firsthand_self_report",
                value=value,
            ),
        ),
        "support_level": "self_directed",
        "context_comparison": "first_record",
        "context_key": "CONTEXT-SIMPLE",
        "evidence_direction": "supports",
        "adverse_indicator_ids": (),
        "repetition_index": 1,
        "observed_on": "2026-06-30",
        "as_of_date": "2026-07-01",
    }
    values.update(overrides)
    return TypedEvidenceInput(**values)


def test_typed_evidence_golden_fixture_replays_exactly():
    fixture = _fixture()
    assert fixture["algorithm_version"] == TYPED_EVIDENCE_ALGORITHM_VERSION
    assert fixture["rules_schema_version"] == TYPED_EVIDENCE_RULES_VERSION

    for case in fixture["cases"]:
        result = evaluate_typed_evidence(_typed_input(case["input"]), case["rules"])
        expected = case["expected"]
        for field in DECIMAL_FIELDS:
            expected_value = expected[field]
            assert getattr(result, field) == (
                None if expected_value is None else Decimal(expected_value)
            ), (case["case_id"], field)
        for field in (
            "direction",
            "adverse",
            "recency_status",
            "transfer_disposition",
        ):
            assert getattr(result, field) == expected[field], (case["case_id"], field)
        assert result.provenance_kinds == tuple(expected["provenance_kinds"])
        assert result.withholding_reasons == tuple(expected["withholding_reasons"])
        assert result.input_snapshot["materialized_spec_hash"] == expected["materialized_spec_hash"]
        assert (
            result.input_snapshot["materialized_rules_hash"] == expected["materialized_rules_hash"]
        )
        assert replay_typed_evidence(result.input_snapshot) == result


def test_spec_inventory_manifest_and_state_coverage_are_exact(tmp_path):
    spec = load_typed_evidence_spec()
    assert set(spec.measurement_kinds) == {
        "boolean",
        "count",
        "bounded_frequency",
        "ordinal",
        "duration",
        "artifact",
        "conceptual",
        "scenario",
        "objective",
        "attestation",
    }
    assert set(spec.observation_states) == {
        "observed",
        "unknown",
        "not_observed",
        "withheld",
        "not_applicable",
        "deferred",
    }
    all_kinds = {item["kind"] for item in _case("TYPED-ALL-KINDS-01")["input"]["observations"]}
    all_states = {item["state"] for item in _case("TYPED-ALL-KINDS-01")["input"]["observations"]}
    assert all_kinds == set(spec.measurement_kinds)
    assert all_states == set(spec.observation_states)

    copied = tmp_path / "evidence"
    shutil.copytree(DATA_ROOT, copied)
    (copied / "unlisted.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(TypedEvidenceContractError, match="coverage is not exact"):
        load_typed_evidence_spec(copied)


def test_snapshot_hashes_and_canonical_materialization_fail_closed():
    case = _case("TYPED-ALL-KINDS-01")
    result = evaluate_typed_evidence(_typed_input(case["input"]), case["rules"])

    tampered_rules = deepcopy(result.input_snapshot)
    tampered_rules["materialized_rules"]["transfer_disposition"] = "context_bound"
    with pytest.raises(TypedEvidenceContractError, match="rules hash does not verify"):
        replay_typed_evidence(tampered_rules)

    tampered_spec = deepcopy(result.input_snapshot)
    tampered_spec["materialized_spec_hash"] = "0" * 64
    with pytest.raises(TypedEvidenceContractError, match="spec hash does not verify"):
        replay_typed_evidence(tampered_spec)

    noncanonical = deepcopy(result.input_snapshot)
    noncanonical["observations"].reverse()
    with pytest.raises(TypedEvidenceContractError, match="not canonically materialized"):
        replay_typed_evidence(noncanonical)


def test_caller_supplied_spec_is_canonicalized_before_evaluation():
    evidence = _simple_input("boolean", True)
    rules = _simple_rules("boolean")
    spec = load_typed_evidence_spec()

    with pytest.raises(TypedEvidenceContractError, match="accepted spec contract"):
        evaluate_typed_evidence(evidence, rules, spec={})

    with pytest.raises(TypedEvidenceContractError, match="algorithm version is unsupported"):
        evaluate_typed_evidence(
            evidence,
            rules,
            spec=replace(spec, algorithm_version="EVIL"),
        )

    with pytest.raises(TypedEvidenceContractError, match="measurement kinds are incomplete"):
        evaluate_typed_evidence(
            evidence,
            rules,
            spec=replace(spec, measurement_kinds=(*spec.measurement_kinds, "drift")),
        )


def test_neutral_states_do_not_enter_competency_denominator_or_provenance():
    case = _case("TYPED-DEFERRED-COMPETENCY-01")
    rules = deepcopy(case["rules"])
    rules["measurements"][1]["allowed_provenance"] = ["reviewed_artifact"]
    raw = deepcopy(case["input"])
    raw["observations"][1]["provenance_kind"] = "reviewed_artifact"

    result = evaluate_typed_evidence(_typed_input(raw), rules)

    assert result.competency_performance == Decimal("1.0000")
    assert result.provenance_kinds == ("firsthand_self_report",)
    deferred = next(
        item
        for item in result.input_snapshot["observations"]
        if item["measurement_id"] == "deferred_signal"
    )
    assert deferred["state"] == "deferred"
    assert deferred["normalized_score"] == "0.0000"


def test_false_and_zero_are_observed_values_not_missing_values():
    false_rules = _simple_rules("boolean")
    false_rules["measurements"][0]["expected"] = False
    false_result = evaluate_typed_evidence(
        _simple_input("boolean", False),
        false_rules,
    )
    zero_rules = _simple_rules("count")
    zero_rules["measurements"][0]["target"] = "0"
    zero_result = evaluate_typed_evidence(_simple_input("count", 0), zero_rules)

    assert false_result.competency_performance == Decimal("1.0000")
    assert zero_result.competency_performance == Decimal("1.0000")
    assert false_result.withholding_reasons == ()
    assert zero_result.withholding_reasons == ()


def test_numeric_rules_are_monotone_with_explicit_bounds():
    values = {
        "count": (0, 5, 10),
        "bounded_frequency": (
            {"numerator": 0, "denominator": 4},
            {"numerator": 2, "denominator": 4},
            {"numerator": 4, "denominator": 4},
        ),
        "duration": (
            {"amount": "0", "unit": "units"},
            {"amount": "5", "unit": "units"},
            {"amount": "10", "unit": "units"},
        ),
        "objective": (
            {"amount": "0", "unit": "units"},
            {"amount": "5", "unit": "units"},
            {"amount": "10", "unit": "units"},
        ),
    }
    for kind, kind_values in values.items():
        increasing = [
            evaluate_typed_evidence(
                _simple_input(kind, value),
                _simple_rules(kind, direction="at_least"),
            ).competency_performance
            for value in kind_values
        ]
        decreasing = [
            evaluate_typed_evidence(
                _simple_input(kind, value),
                _simple_rules(kind, direction="at_most"),
            ).competency_performance
            for value in kind_values
        ]
        assert increasing == sorted(increasing), kind
        assert decreasing == sorted(decreasing, reverse=True), kind

    with pytest.raises(TypedEvidenceContractError, match="outside"):
        evaluate_typed_evidence(
            _simple_input("count", 11),
            _simple_rules("count"),
        )
    with pytest.raises(TypedEvidenceContractError):
        evaluate_typed_evidence(
            _simple_input(
                "bounded_frequency",
                {"numerator": 5, "denominator": 4},
            ),
            _simple_rules("bounded_frequency"),
        )


def test_invalid_attestation_is_explicitly_withheld():
    evidence = _simple_input(
        "attestation",
        {
            "attestation_id": "qualified_scope",
            "consent_confirmed": False,
        },
    )
    evidence = replace(
        evidence,
        observations=(
            replace(
                evidence.observations[0],
                provenance_kind="qualified_attestation",
            ),
        ),
        scoring_policy_id="SP-QUALIFIED-EVIDENCE-REQUIRED",
    )
    rules = _simple_rules("attestation")
    rules["measurements"][0]["allowed_provenance"] = ["qualified_attestation"]

    result = evaluate_typed_evidence(evidence, rules)

    assert result.competency_performance == Decimal("0.0000")
    assert result.withholding_reasons == ("invalid_or_unconsented_attestation:metric",)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("action_attempted", 1, "must be Boolean"),
        ("action_completed", "false", "must be Boolean"),
        ("repetition_index", True, "positive non-Boolean integer"),
        ("repetition_index", 0, "positive non-Boolean integer"),
        ("observations", None, "structured sequence"),
        ("observations", ({"measurement_id": "metric"},), "observation contract"),
        ("adverse_indicator_ids", None, "structured sequence"),
    ],
)
def test_malformed_runtime_types_raise_contract_errors(field, value, message):
    evidence = replace(_simple_input("boolean", True), **{field: value})
    with pytest.raises(TypedEvidenceContractError, match=message):
        evaluate_typed_evidence(evidence, _simple_rules("boolean"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("measurement_id", []),
        ("kind", {"boolean": True}),
        ("state", None),
        ("provenance_kind", ["firsthand_self_report"]),
    ],
)
def test_malformed_observation_tokens_raise_contract_errors(field, value):
    observation = replace(
        _simple_input("boolean", True).observations[0],
        **{field: value},
    )
    evidence = replace(
        _simple_input("boolean", True),
        observations=(observation,),
    )
    with pytest.raises(TypedEvidenceContractError, match="stable non-narrative token"):
        evaluate_typed_evidence(evidence, _simple_rules("boolean"))


def test_free_text_and_implicit_neutral_values_are_rejected():
    with pytest.raises(TypedEvidenceContractError, match="non-narrative token"):
        evaluate_typed_evidence(
            replace(_simple_input("boolean", True), event_key="a narrative key"),
            _simple_rules("boolean"),
        )

    deferred = replace(
        _simple_input("boolean", True),
        observations=(
            TypedObservationInput(
                measurement_id="metric",
                kind="boolean",
                state="deferred",
                provenance_kind="firsthand_self_report",
                value=True,
            ),
        ),
    )
    with pytest.raises(TypedEvidenceContractError, match="only observed values"):
        evaluate_typed_evidence(deferred, _simple_rules("boolean"))

    rules = _simple_rules("boolean")
    rules["narrative"] = "reinterpret this input"
    with pytest.raises(TypedEvidenceContractError, match="fields do not match"):
        evaluate_typed_evidence(_simple_input("boolean", True), rules)
