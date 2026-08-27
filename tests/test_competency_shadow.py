import json
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from itertools import permutations
from pathlib import Path

import pytest

from growth.domain.competency_scoring import (
    COMPETENCY_EVIDENCE_SHADOW_VERSION,
    COMPETENCY_LEVER_SHADOW_VERSION,
    SUPPORTED_POLICY_IDS,
    CompetencyEvidenceCandidate,
    CompetencyScoringContractError,
    candidate_from_typed_evidence,
    competency_lever_mapping_fingerprint,
    project_competency_evidence,
    project_competency_to_levers,
)
from growth.domain.scoring import (
    SCORING_ALGORITHM_VERSION,
    BaselineMass,
    LeverWeight,
)
from growth.domain.typed_evidence import (
    TypedEvidenceInput,
    TypedObservationInput,
    evaluate_typed_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "scoring" / "competency_shadow_v1.json"
TYPED_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "evidence" / "typed_v1.json"


def _fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _candidate(raw):
    return CompetencyEvidenceCandidate(
        **{
            **raw,
            "competency_performance": (
                None
                if raw["competency_performance"] is None
                else Decimal(raw["competency_performance"])
            ),
            "base_evidence_mass": Decimal(raw["base_evidence_mass"]),
            "provenance_kinds": tuple(raw["provenance_kinds"]),
            "measurement_kinds": tuple(raw["measurement_kinds"]),
            "upstream_withholding_reasons": tuple(raw.get("upstream_withholding_reasons", ())),
        }
    )


def _fixture_candidates():
    return tuple(_candidate(item) for item in _fixture()["candidates"])


def _baselines(fixture=None):
    fixture = fixture or _fixture()
    return {
        lever_id: BaselineMass(
            lever_id=lever_id,
            alpha=Decimal(values["alpha"]),
            beta=Decimal(values["beta"]),
            confidence=Decimal(values["confidence"]),
        )
        for lever_id, values in fixture["baselines"].items()
    }


def _weights(fixture=None):
    fixture = fixture or _fixture()
    return tuple(
        LeverWeight(
            lever_id=item["lever_id"],
            weight=Decimal(item["weight"]),
            total_competency_weight=Decimal(item["total_competency_weight"]),
        )
        for item in fixture["weights"]
    )


def _competency_projection(candidates=None, **overrides):
    fixture = _fixture()
    values = {
        "candidates": _fixture_candidates() if candidates is None else candidates,
        "assessment_epoch_id": fixture["assessment_epoch_id"],
        "competency_id": fixture["competency_id"],
        "as_of_date": fixture["as_of_date"],
        "policy_id": fixture["policy_id"],
        "reversed_event_keys": tuple(fixture["reversed_event_keys"]),
    }
    values.update(overrides)
    return project_competency_evidence(**values)


def _lever_projection(competency_projection, **overrides):
    fixture = _fixture()
    values = {
        "competency_projection": competency_projection,
        "baselines": _baselines(fixture),
        "weights": _weights(fixture),
        "baseline_assessment_epoch_id": fixture["baseline_assessment_epoch_id"],
        "canonical_lever_ids": tuple(fixture["canonical_lever_ids"]),
        "canonical_mapping_fingerprint": fixture["canonical_mapping_fingerprint"],
        "minimum_transfer_disposition": fixture["minimum_transfer_disposition"],
    }
    values.update(overrides)
    return project_competency_to_levers(**values)


def _manual_candidate(
    event_key="E-MANUAL-1",
    *,
    policy_id="SP-SHADOW-ONLY",
    origin_key=None,
    context_key="CONTEXT-A",
    provenance_kinds=("firsthand_self_report",),
    measurement_kinds=("boolean",),
    transfer_disposition="context_bound",
    qualified_attestation_valid=False,
    upstream_withholding_reasons=(),
    competency_performance=Decimal("0.8"),
    adverse=False,
):
    return CompetencyEvidenceCandidate(
        event_key=event_key,
        origin_key=origin_key or f"ORIGIN-{event_key}",
        assessment_epoch_id="ASSESSMENT-EPOCH-001",
        protocol_stable_id="PRACTICE-SYNTHETIC-01",
        action_stable_id=f"ACTION-{event_key}",
        competency_id="01.01",
        policy_id=policy_id,
        competency_performance=competency_performance,
        base_evidence_mass=Decimal("0.4"),
        direction="supports",
        adverse=adverse,
        provenance_kinds=provenance_kinds,
        measurement_kinds=measurement_kinds,
        context_key=context_key,
        transfer_disposition=transfer_disposition,
        observed_on="2026-06-30",
        max_age_days=365,
        upstream_withholding_reasons=upstream_withholding_reasons,
        qualified_attestation_valid=qualified_attestation_valid,
    )


def _project_manual(candidates, policy_id):
    return project_competency_evidence(
        candidates=candidates,
        assessment_epoch_id="ASSESSMENT-EPOCH-001",
        competency_id="01.01",
        as_of_date="2026-07-01",
        policy_id=policy_id,
    )


def _typed_input(raw):
    return TypedEvidenceInput(
        **{
            **raw,
            "observations": tuple(TypedObservationInput(**item) for item in raw["observations"]),
            "adverse_indicator_ids": tuple(raw["adverse_indicator_ids"]),
        }
    )


def test_competency_and_lever_golden_fixture_are_exact():
    fixture = _fixture()
    competency = _competency_projection()
    expected = fixture["expected_competency"]

    assert competency.algorithm_version == fixture["competency_evidence_algorithm_version"]
    assert competency.algorithm_version == COMPETENCY_EVIDENCE_SHADOW_VERSION
    for field in (
        "evidence_state",
        "competency_estimate",
        "event_count",
        "included_event_count",
        "withheld_event_count",
        "reversed_event_count",
    ):
        assert getattr(competency, field) == expected[field]
    for field in ("evidence_mass", "success_mass", "failure_mass"):
        assert getattr(competency, field) == Decimal(expected[field])
    contributions = {item.event_key: item for item in competency.contributions}
    for event_key, contribution_expected in expected["contributions"].items():
        contribution = contributions[event_key]
        for field in (
            "included",
            "withholding_reason",
            "transfer_disposition",
        ):
            assert getattr(contribution, field) == contribution_expected[field]
        for field in (
            "competency_performance",
            "evidence_mass",
            "success_mass",
            "failure_mass",
        ):
            assert getattr(contribution, field) == Decimal(contribution_expected[field])
        if contribution.withholding_reason:
            assert contribution.withholding_reasons[0] == contribution.withholding_reason
        else:
            assert contribution.withholding_reasons == ()

    baselines = _baselines(fixture)
    baseline_copy = deepcopy(baselines)
    lever_shadow = _lever_projection(competency, baselines=baselines)
    expected_lever = fixture["expected_lever"]

    assert lever_shadow.algorithm_version == fixture["competency_lever_algorithm_version"]
    assert lever_shadow.algorithm_version == COMPETENCY_LEVER_SHADOW_VERSION
    assert lever_shadow.projection.algorithm_version == SCORING_ALGORITHM_VERSION
    assert lever_shadow.projection.algorithm_version == fixture["projection_algorithm_version"]
    assert lever_shadow.baseline_assessment_epoch_id == fixture["assessment_epoch_id"]
    assert lever_shadow.canonical_mapping_fingerprint == fixture["canonical_mapping_fingerprint"]
    assert lever_shadow.allocated_event_keys == tuple(expected_lever["allocated_event_keys"])
    for field in ("event_count", "scored_event_count", "withheld_event_count"):
        assert getattr(lever_shadow.projection, field) == expected_lever[field]
    for lever in lever_shadow.projection.levers:
        lever_expected = expected_lever["levers"][lever.lever_id]
        assert lever.contributions[0].task_coefficient == Decimal(
            lever_expected["task_coefficient"]
        )
        for field in (
            "evidence_mass",
            "success_mass",
            "failure_mass",
            "projected_alpha",
            "projected_beta",
            "projected_estimate",
            "projected_confidence",
        ):
            assert getattr(lever, field) == Decimal(lever_expected[field])
    assert baselines == baseline_copy


def test_empty_and_all_withheld_evidence_remain_unknown_without_a_synthetic_estimate():
    fixture = _fixture()
    empty = project_competency_evidence(
        candidates=(),
        assessment_epoch_id=fixture["assessment_epoch_id"],
        competency_id=fixture["competency_id"],
        as_of_date=fixture["as_of_date"],
        policy_id=fixture["policy_id"],
    )
    expected = fixture["empty_expected"]
    for field in (
        "evidence_state",
        "competency_estimate",
        "event_count",
        "included_event_count",
        "withheld_event_count",
        "reversed_event_count",
    ):
        assert getattr(empty, field) == expected[field]
    for field in ("evidence_mass", "success_mass", "failure_mass"):
        assert getattr(empty, field) == Decimal(expected[field])

    candidate = _manual_candidate(
        competency_performance=None,
        provenance_kinds=(),
        measurement_kinds=(),
        upstream_withholding_reasons=(
            "no_observed_measurement",
            "no_observed_competency_measurement",
        ),
        adverse=True,
    )
    all_withheld = _project_manual(
        (candidate,),
        policy_id="SP-SHADOW-ONLY",
    )
    contribution = all_withheld.contributions[0]
    assert all_withheld.evidence_state == "unknown"
    assert all_withheld.competency_estimate is None
    assert contribution.competency_performance is None
    assert contribution.withholding_reason == "adverse_outcome_withheld_for_review"
    assert contribution.withholding_reasons == (
        "adverse_outcome_withheld_for_review",
        "typed_protocol_evidence_withheld:no_observed_competency_measurement",
        "typed_protocol_evidence_withheld:no_observed_measurement",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("assessment_epoch_id", ""),
        ("competency_id", "private narrative value"),
    ],
)
def test_empty_projection_selectors_require_stable_non_narrative_tokens(field, value):
    arguments = {
        "candidates": (),
        "assessment_epoch_id": "ASSESSMENT-EPOCH-001",
        "competency_id": "01.01",
        "as_of_date": "2026-07-01",
        "policy_id": "SP-SHADOW-ONLY",
        field: value,
    }
    with pytest.raises(CompetencyScoringContractError, match="stable non-narrative token"):
        project_competency_evidence(**arguments)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("policy_id", [], "scoring policy"),
        ("direction", [], "evidence direction"),
        ("transfer_disposition", [], "transfer disposition"),
    ],
)
def test_unhashable_candidate_enums_raise_controlled_contract_errors(
    field,
    value,
    message,
):
    candidate = replace(_manual_candidate(), **{field: value})
    with pytest.raises(CompetencyScoringContractError, match=message):
        _project_manual((candidate,), policy_id="SP-SHADOW-ONLY")


def test_none_projection_collections_raise_controlled_contract_errors():
    with pytest.raises(CompetencyScoringContractError, match="candidates must be an iterable"):
        _project_manual(None, policy_id="SP-SHADOW-ONLY")
    with pytest.raises(CompetencyScoringContractError, match="candidate contract"):
        _project_manual((None,), policy_id="SP-SHADOW-ONLY")
    with pytest.raises(CompetencyScoringContractError, match="Reversed event keys"):
        project_competency_evidence(
            candidates=(),
            assessment_epoch_id="ASSESSMENT-EPOCH-001",
            competency_id="01.01",
            as_of_date="2026-07-01",
            policy_id="SP-SHADOW-ONLY",
            reversed_event_keys=None,
        )
    with pytest.raises(CompetencyScoringContractError, match="weights must be an iterable"):
        competency_lever_mapping_fingerprint(
            competency_id="01.01",
            weights=None,
        )


def test_malformed_projection_policy_and_lever_boundary_raise_controlled_errors():
    with pytest.raises(CompetencyScoringContractError, match="Scoring policy"):
        project_competency_evidence(
            candidates=(),
            assessment_epoch_id="ASSESSMENT-EPOCH-001",
            competency_id="01.01",
            as_of_date="2026-07-01",
            policy_id=[],
        )
    with pytest.raises(CompetencyScoringContractError, match="projection contract"):
        _lever_projection(None)
    with pytest.raises(CompetencyScoringContractError, match="transfer disposition"):
        _lever_projection(
            _competency_projection(),
            minimum_transfer_disposition=[],
        )


def test_candidate_conversion_replays_snapshot_and_uses_only_designated_observations():
    typed_fixture = json.loads(TYPED_FIXTURE_PATH.read_text(encoding="utf-8"))
    case = next(item for item in typed_fixture["cases"] if item["case_id"] == "TYPED-ALL-KINDS-01")
    result = evaluate_typed_evidence(_typed_input(case["input"]), case["rules"])
    candidate = candidate_from_typed_evidence(result)

    assert candidate.competency_performance == Decimal("0.8889")
    assert candidate.measurement_kinds == ("artifact", "boolean", "objective")
    assert candidate.provenance_kinds == (
        "firsthand_self_report",
        "objective_indicator",
        "reviewed_artifact",
    )
    assert not candidate.qualified_attestation_valid

    with pytest.raises(CompetencyScoringContractError, match="does not match"):
        candidate_from_typed_evidence(replace(result, competency_performance=Decimal("1.0000")))
    with pytest.raises(CompetencyScoringContractError, match="does not match"):
        candidate_from_typed_evidence(replace(result, transfer_disposition="context_bound"))


def test_all_deferred_direct_evidence_is_retained_but_protocol_only_is_rejected():
    typed_fixture = json.loads(TYPED_FIXTURE_PATH.read_text(encoding="utf-8"))
    case = next(
        item for item in typed_fixture["cases"] if item["case_id"] == "TYPED-DEFERRED-COMPETENCY-01"
    )
    raw = deepcopy(case["input"])
    for observation in raw["observations"]:
        observation["state"] = "deferred"
        observation["value"] = None
    result = evaluate_typed_evidence(_typed_input(raw), case["rules"])
    candidate = candidate_from_typed_evidence(result)
    projection = _project_manual((candidate,), policy_id="SP-SHADOW-ONLY")

    assert candidate.competency_performance is None
    assert candidate.provenance_kinds == ()
    assert candidate.measurement_kinds == ()
    assert projection.evidence_state == "unknown"
    assert projection.contributions[0].competency_performance is None
    assert projection.contributions[0].withholding_reasons == (
        "typed_protocol_evidence_withheld:no_observed_competency_measurement",
        "typed_protocol_evidence_withheld:no_observed_measurement",
    )

    protocol_rules = deepcopy(case["rules"])
    protocol_rules["competency_measurement_ids"] = []
    protocol_rules["transfer_disposition"] = "protocol_only"
    observed = evaluate_typed_evidence(_typed_input(case["input"]), protocol_rules)
    with pytest.raises(CompetencyScoringContractError, match="Protocol-only"):
        candidate_from_typed_evidence(observed)


def test_all_seven_scoring_policy_gates_are_executable():
    assert {
        "SP-SELF-REPORT-ELIGIBLE",
        "SP-CORROBORATION-REQUIRED",
        "SP-ARTIFACT-OBJECTIVE-PREFERRED",
        "SP-QUALIFIED-EVIDENCE-REQUIRED",
        "SP-SHADOW-ONLY",
        "SP-NON-SCORED-REFLECTION",
        "SP-STRUCTURED-EVIDENCE-ELIGIBLE",
    } == SUPPORTED_POLICY_IDS
    for policy_id in ("SP-SELF-REPORT-ELIGIBLE", "SP-SHADOW-ONLY"):
        projection = _project_manual(
            (_manual_candidate(policy_id=policy_id),),
            policy_id=policy_id,
        )
        assert projection.included_event_count == 1

    non_scored = _project_manual(
        (_manual_candidate(policy_id="SP-NON-SCORED-REFLECTION"),),
        policy_id="SP-NON-SCORED-REFLECTION",
    )
    assert non_scored.contributions[0].withholding_reason == ("policy_defines_no_score_update")

    corroboration_failed = _project_manual(
        (_manual_candidate(policy_id="SP-CORROBORATION-REQUIRED"),),
        policy_id="SP-CORROBORATION-REQUIRED",
    )
    assert corroboration_failed.included_event_count == 0
    corroborated = _project_manual(
        (
            _manual_candidate(
                "E-CORROBORATE-1",
                policy_id="SP-CORROBORATION-REQUIRED",
            ),
            _manual_candidate(
                "E-CORROBORATE-2",
                policy_id="SP-CORROBORATION-REQUIRED",
                context_key="CONTEXT-B",
                provenance_kinds=("reviewed_artifact",),
                measurement_kinds=("artifact",),
            ),
        ),
        policy_id="SP-CORROBORATION-REQUIRED",
    )
    assert corroborated.included_event_count == 2

    artifact_failed = _project_manual(
        (_manual_candidate(policy_id="SP-ARTIFACT-OBJECTIVE-PREFERRED"),),
        policy_id="SP-ARTIFACT-OBJECTIVE-PREFERRED",
    )
    assert artifact_failed.included_event_count == 0
    artifact_passed = _project_manual(
        (
            _manual_candidate(
                policy_id="SP-ARTIFACT-OBJECTIVE-PREFERRED",
                provenance_kinds=("reviewed_artifact",),
                measurement_kinds=("artifact",),
            ),
        ),
        policy_id="SP-ARTIFACT-OBJECTIVE-PREFERRED",
    )
    assert artifact_passed.included_event_count == 1

    invalid_qualified = _project_manual(
        (
            _manual_candidate(
                policy_id="SP-QUALIFIED-EVIDENCE-REQUIRED",
                provenance_kinds=("qualified_attestation",),
                measurement_kinds=("attestation",),
            ),
        ),
        policy_id="SP-QUALIFIED-EVIDENCE-REQUIRED",
    )
    assert invalid_qualified.included_event_count == 0
    valid_qualified = _project_manual(
        (
            _manual_candidate(
                "E-QUALIFIED",
                policy_id="SP-QUALIFIED-EVIDENCE-REQUIRED",
                provenance_kinds=("qualified_attestation",),
                measurement_kinds=("attestation",),
                qualified_attestation_valid=True,
            ),
            _manual_candidate(
                "E-UNQUALIFIED",
                policy_id="SP-QUALIFIED-EVIDENCE-REQUIRED",
                context_key="CONTEXT-B",
            ),
        ),
        policy_id="SP-QUALIFIED-EVIDENCE-REQUIRED",
    )
    assert valid_qualified.included_event_count == 1
    assert {item.event_key: item.withholding_reason for item in valid_qualified.contributions}[
        "E-UNQUALIFIED"
    ] == "candidate_is_not_qualified_evidence"


def test_policy_withheld_context_cannot_promote_cross_context_transfer():
    projection = _project_manual(
        (
            _manual_candidate(
                "E-QUALIFIED",
                policy_id="SP-QUALIFIED-EVIDENCE-REQUIRED",
                provenance_kinds=("qualified_attestation",),
                measurement_kinds=("attestation",),
                transfer_disposition="cross_context_supported",
                qualified_attestation_valid=True,
            ),
            _manual_candidate(
                "E-UNQUALIFIED",
                policy_id="SP-QUALIFIED-EVIDENCE-REQUIRED",
                context_key="CONTEXT-B",
            ),
        ),
        policy_id="SP-QUALIFIED-EVIDENCE-REQUIRED",
    )
    reasons = {item.event_key: item.withholding_reason for item in projection.contributions}
    assert reasons == {
        "E-QUALIFIED": "cross_context_transfer_not_demonstrated",
        "E-UNQUALIFIED": "candidate_is_not_qualified_evidence",
    }
    assert projection.evidence_state == "unknown"


def test_duplicate_origin_epoch_and_reversal_guards_fail_closed():
    candidate = _manual_candidate()
    with pytest.raises(CompetencyScoringContractError, match=r"Duplicate.*event"):
        _project_manual((candidate, candidate), policy_id="SP-SHADOW-ONLY")
    with pytest.raises(CompetencyScoringContractError, match="origin"):
        _project_manual(
            (
                candidate,
                replace(candidate, event_key="E-MANUAL-2"),
            ),
            policy_id="SP-SHADOW-ONLY",
        )
    with pytest.raises(CompetencyScoringContractError, match="assessment epochs"):
        _project_manual(
            (replace(candidate, assessment_epoch_id="ASSESSMENT-EPOCH-002"),),
            policy_id="SP-SHADOW-ONLY",
        )
    with pytest.raises(CompetencyScoringContractError, match="unknown"):
        project_competency_evidence(
            candidates=(candidate,),
            assessment_epoch_id="ASSESSMENT-EPOCH-001",
            competency_id="01.01",
            as_of_date="2026-07-01",
            policy_id="SP-SHADOW-ONLY",
            reversed_event_keys=("E-UNKNOWN",),
        )


@pytest.mark.parametrize(
    "candidate",
    [
        _manual_candidate(provenance_kinds=("invented_provenance",)),
        _manual_candidate(measurement_kinds=("invented_measurement",)),
        _manual_candidate(event_key="narrative event key"),
        _manual_candidate(upstream_withholding_reasons=("a narrative reason",)),
        _manual_candidate(qualified_attestation_valid=True),
    ],
)
def test_manual_candidate_tokens_and_qualification_are_bounded(candidate):
    with pytest.raises(CompetencyScoringContractError):
        _project_manual((candidate,), policy_id=candidate.policy_id)


def test_projection_is_order_independent_and_reversal_is_pure():
    fixture = _fixture()
    candidates = _fixture_candidates()
    expected = _competency_projection(candidates)
    for ordered in permutations(candidates):
        assert _competency_projection(ordered) == expected

    without_reversed = tuple(
        item for item in candidates if item.event_key not in fixture["reversed_event_keys"]
    )
    clean = _competency_projection(without_reversed, reversed_event_keys=())
    assert clean.evidence_mass == expected.evidence_mass
    assert clean.success_mass == expected.success_mass
    assert clean.failure_mass == expected.failure_mass
    assert _lever_projection(clean).projection == _lever_projection(expected).projection

    fully_reversed = _competency_projection(
        candidates,
        reversed_event_keys=tuple(item.event_key for item in candidates),
    )
    baseline_projection = _lever_projection(fully_reversed)
    assert fully_reversed.evidence_state == "unknown"
    assert fully_reversed.competency_estimate is None
    assert baseline_projection.allocated_event_keys == ()
    for lever in baseline_projection.projection.levers:
        baseline = _baselines()[lever.lever_id]
        assert lever.evidence_mass == 0
        assert lever.projected_alpha == baseline.alpha
        assert lever.projected_beta == baseline.beta
    assert candidates == _fixture_candidates()


def test_canonical_mapping_fingerprint_coverage_and_baseline_epoch_are_required():
    fixture = _fixture()
    competency = _competency_projection()
    weights = _weights(fixture)
    fingerprint = competency_lever_mapping_fingerprint(
        competency_id=fixture["competency_id"],
        weights=reversed(weights),
    )
    assert fingerprint == fixture["canonical_mapping_fingerprint"]

    with pytest.raises(CompetencyScoringContractError, match="same assessment epoch"):
        _lever_projection(
            competency,
            baseline_assessment_epoch_id="ASSESSMENT-EPOCH-002",
        )
    with pytest.raises(CompetencyScoringContractError, match="complete canonical"):
        _lever_projection(
            competency,
            baselines={"L26": _baselines()["L26"]},
        )
    with pytest.raises(CompetencyScoringContractError, match="does not match"):
        _lever_projection(
            competency,
            canonical_mapping_fingerprint="0" * 64,
        )

    subset_weights = (next(item for item in weights if item.lever_id == "L26"),)
    with pytest.raises(CompetencyScoringContractError, match="complete canonical"):
        _lever_projection(
            competency,
            baselines={"L26": _baselines()["L26"]},
            weights=subset_weights,
            canonical_lever_ids=tuple(fixture["canonical_lever_ids"]),
        )
