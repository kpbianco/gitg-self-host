from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings

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
from growth.domain.evidence import (
    EVIDENCE_ALGORITHM_VERSION,
    EvidenceInput,
    evaluate_evidence,
)
from growth.domain.evidence_dispatch import replay_evidence_by_version
from growth.domain.practice_content import load_practice_content_bundle
from growth.domain.scoring import (
    SCORING_ALGORITHM_VERSION,
    BaselineMass,
    LeverWeight,
)
from growth.domain.typed_evidence import (
    SUPPORTED_SCORING_POLICY_IDS,
    TYPED_EVIDENCE_ALGORITHM_VERSION,
    TYPED_EVIDENCE_RULES_VERSION,
    TypedEvidenceInput,
    TypedObservationInput,
    evaluate_typed_evidence,
    load_typed_evidence_spec,
)
from growth.services.canonical_import import load_and_validate_bundle
from growth.services.expansion_readiness import EXPANSION_READINESS_CONTRACT_VERSION
from growth.services.scoring import (
    FRIENDSHIP_ACTIONS,
    FRIENDSHIP_ALLOCATION,
    FRIENDSHIP_COMPETENCY_ID,
    FRIENDSHIP_PROTOCOL_ID,
    FRIENDSHIP_TARGET_LEVER_IDS,
    PRODUCTION_EVIDENCE_RULES_VERSION,
    PRODUCTION_SCORE_ELIGIBILITY_CONTRACT_VERSION,
    PRODUCTION_SCORE_MAPPING_FINGERPRINT,
    PRODUCTION_SCORE_STATE_VERSION,
)

COMPETENCY_EVIDENCE_READINESS_CONTRACT_VERSION = "GG-COMPETENCY-EVIDENCE-READINESS-1.0"
REPORT_ROOT = Path("reports/practice-content")
REPORT_PATHS = {
    "typed_capability": REPORT_ROOT / "typed_evidence_capability_v1.csv",
    "scoring_policy": REPORT_ROOT / "scoring_policy_execution_v1.csv",
    "readiness": REPORT_ROOT / "competency_evidence_readiness_v1.json",
}

_EXPECTED_CATALOG_COUNTS = {
    "competencies": 383,
    "canonical_protocol_packages": 5,
    "practice_actions": 15,
    "uncovered_competencies": 378,
    "score_active_protocols": 1,
}
_MEASUREMENT_NORMALIZATION = {
    "artifact": "allowlisted_criteria_ids_only_no_artifact_content",
    "attestation": "allowlisted_attestation_id_and_explicit_consent",
    "boolean": "explicit_boolean_equality",
    "bounded_frequency": "explicit_numerator_denominator_and_direction",
    "conceptual": "allowlisted_criteria_ids_only",
    "count": "nonnegative_integer_with_explicit_bounds_and_direction",
    "duration": "decimal_amount_with_explicit_unit_bounds_and_direction",
    "objective": "decimal_amount_with_explicit_unit_bounds_and_direction",
    "ordinal": "allowlisted_level_id_with_explicit_score",
    "scenario": "allowlisted_criteria_ids_only",
}
_EXPECTED_POLICY_OUTCOMES = {
    "SP-ARTIFACT-OBJECTIVE-PREFERRED": (1, 0),
    "SP-CORROBORATION-REQUIRED": (2, 0),
    "SP-NON-SCORED-REFLECTION": (0, 1),
    "SP-QUALIFIED-EVIDENCE-REQUIRED": (1, 0),
    "SP-SELF-REPORT-ELIGIBLE": (1, 0),
    "SP-SHADOW-ONLY": (1, 0),
}


class CompetencyEvidenceReportError(ValueError):
    pass


@dataclass(frozen=True)
class _SoftwareContract:
    capability_rows: tuple[dict[str, Any], ...]
    policy_rows: tuple[dict[str, Any], ...]
    readiness: dict[str, Any]


def _csv_bytes(rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def _require_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise CompetencyEvidenceReportError(f"{label}: expected {expected!r}, found {actual!r}.")


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _verify_legacy_dispatch() -> None:
    result = evaluate_evidence(
        EvidenceInput(
            protocol_stable_id=FRIENDSHIP_PROTOCOL_ID,
            action_stable_id=f"{FRIENDSHIP_PROTOCOL_ID}-A1",
            action_attempted=True,
            action_completed=True,
            observations={
                "moved_beyond_transactional": True,
                "meaningful_information_shared": True,
                "follow_up_question_asked": True,
                "user_initiated": True,
            },
            internal_resistance=2,
            expected_reciprocity=3,
            observed_reciprocity=3,
            support_level="independent",
            context_comparison="first_record",
            evidence_direction="supports",
            contradiction_text_present=False,
            repetition_index=1,
        ),
        {
            "schema_version": PRODUCTION_EVIDENCE_RULES_VERSION,
            "primary_markers": [
                "moved_beyond_transactional",
                "meaningful_information_shared",
            ],
            "supporting_markers": [
                "follow_up_question_asked",
                "user_initiated",
            ],
        },
    )
    _require_equal("Frozen v1 evidence mass", result.base_evidence_mass, Decimal("0.4675"))
    _require_equal(
        "Version-dispatched v1 replay",
        replay_evidence_by_version(EVIDENCE_ALGORITHM_VERSION, result.input_snapshot),
        result,
    )


def _typed_rules_and_input() -> tuple[dict[str, Any], TypedEvidenceInput]:
    measurements = [
        {
            "measurement_id": "M-BOOLEAN",
            "kind": "boolean",
            "role": "primary",
            "weight": "0.10",
            "allowed_provenance": ["firsthand_self_report"],
            "expected": True,
        },
        {
            "measurement_id": "M-COUNT",
            "kind": "count",
            "role": "primary",
            "weight": "0.10",
            "allowed_provenance": ["firsthand_self_report"],
            "direction": "at_least",
            "minimum": "0",
            "target": "3",
            "maximum": "5",
        },
        {
            "measurement_id": "M-FREQUENCY",
            "kind": "bounded_frequency",
            "role": "primary",
            "weight": "0.10",
            "allowed_provenance": ["firsthand_self_report"],
            "direction": "at_least",
            "minimum": "0",
            "target": "0.75",
            "maximum": "1",
        },
        {
            "measurement_id": "M-ORDINAL",
            "kind": "ordinal",
            "role": "primary",
            "weight": "0.10",
            "allowed_provenance": ["firsthand_self_report"],
            "levels": [
                {"level_id": "LOW", "score": "0"},
                {"level_id": "HIGH", "score": "1"},
            ],
        },
        {
            "measurement_id": "M-DURATION",
            "kind": "duration",
            "role": "primary",
            "weight": "0.10",
            "allowed_provenance": ["firsthand_self_report"],
            "direction": "at_least",
            "minimum": "0",
            "target": "10",
            "maximum": "30",
            "unit": "minutes",
        },
        {
            "measurement_id": "M-ARTIFACT",
            "kind": "artifact",
            "role": "primary",
            "weight": "0.10",
            "allowed_provenance": ["reviewed_artifact"],
            "criteria": ["CRITERION-A", "CRITERION-B"],
        },
        {
            "measurement_id": "M-CONCEPTUAL",
            "kind": "conceptual",
            "role": "primary",
            "weight": "0.10",
            "allowed_provenance": ["firsthand_self_report"],
            "criteria": ["CONCEPT-A"],
        },
        {
            "measurement_id": "M-SCENARIO",
            "kind": "scenario",
            "role": "primary",
            "weight": "0.10",
            "allowed_provenance": ["firsthand_self_report"],
            "criteria": ["SCENARIO-A"],
        },
        {
            "measurement_id": "M-OBJECTIVE",
            "kind": "objective",
            "role": "primary",
            "weight": "0.10",
            "allowed_provenance": ["objective_indicator"],
            "direction": "at_least",
            "minimum": "0",
            "target": "2",
            "maximum": "4",
            "unit": "records",
        },
        {
            "measurement_id": "M-ATTESTATION",
            "kind": "attestation",
            "role": "primary",
            "weight": "0.10",
            "allowed_provenance": ["qualified_attestation"],
            "allowed_attestation_ids": ["QUALIFIED-REVIEW-PASS"],
            "consent_required": True,
        },
    ]
    observations = (
        TypedObservationInput("M-BOOLEAN", "boolean", "observed", "firsthand_self_report", True),
        TypedObservationInput("M-COUNT", "count", "observed", "firsthand_self_report", 3),
        TypedObservationInput(
            "M-FREQUENCY",
            "bounded_frequency",
            "observed",
            "firsthand_self_report",
            {"numerator": 3, "denominator": 4},
        ),
        TypedObservationInput("M-ORDINAL", "ordinal", "observed", "firsthand_self_report", "HIGH"),
        TypedObservationInput(
            "M-DURATION",
            "duration",
            "observed",
            "firsthand_self_report",
            {"amount": "10", "unit": "minutes"},
        ),
        TypedObservationInput(
            "M-ARTIFACT",
            "artifact",
            "observed",
            "reviewed_artifact",
            {"criteria_met": ["CRITERION-A", "CRITERION-B"]},
        ),
        TypedObservationInput(
            "M-CONCEPTUAL",
            "conceptual",
            "observed",
            "firsthand_self_report",
            {"criteria_met": ["CONCEPT-A"]},
        ),
        TypedObservationInput(
            "M-SCENARIO",
            "scenario",
            "observed",
            "firsthand_self_report",
            {"criteria_met": ["SCENARIO-A"]},
        ),
        TypedObservationInput(
            "M-OBJECTIVE",
            "objective",
            "observed",
            "objective_indicator",
            {"amount": "2", "unit": "records"},
        ),
        TypedObservationInput(
            "M-ATTESTATION",
            "attestation",
            "observed",
            "qualified_attestation",
            {
                "attestation_id": "QUALIFIED-REVIEW-PASS",
                "consent_confirmed": True,
            },
        ),
    )
    return (
        {
            "schema_version": TYPED_EVIDENCE_RULES_VERSION,
            "max_age_days": 365,
            "measurements": measurements,
            "competency_measurement_ids": [
                measurement["measurement_id"] for measurement in measurements
            ],
            "transfer_disposition": "context_bound",
        },
        TypedEvidenceInput(
            event_key="M6B-CAPABILITY-EVENT",
            origin_key="M6B-CAPABILITY-ORIGIN",
            assessment_epoch_id="M6B-ASSESSMENT-EPOCH",
            protocol_stable_id="M6B-SYNTHETIC-PROTOCOL",
            action_stable_id="M6B-SYNTHETIC-ACTION",
            competency_stable_id=FRIENDSHIP_COMPETENCY_ID,
            scoring_policy_id="SP-SHADOW-ONLY",
            action_attempted=True,
            action_completed=True,
            observations=observations,
            support_level="self_directed",
            context_comparison="first_record",
            context_key="M6B-SYNTHETIC-CONTEXT",
            evidence_direction="supports",
            adverse_indicator_ids=(),
            repetition_index=1,
            observed_on="2026-07-27",
            as_of_date="2026-07-27",
        ),
    )


def _verify_typed_dispatch(spec) -> None:
    rules, evidence = _typed_rules_and_input()
    result = evaluate_typed_evidence(evidence, rules, spec=spec)
    _require_equal(
        "Typed fixture replay",
        replay_evidence_by_version(
            TYPED_EVIDENCE_ALGORITHM_VERSION,
            result.input_snapshot,
        ),
        result,
    )
    observed_kinds = {item["kind"] for item in result.input_snapshot["observations"]}
    _require_equal(
        "Typed fixture measurement coverage",
        observed_kinds,
        set(spec.measurement_kinds),
    )


def _typed_input_from_mapping(raw: dict[str, Any]) -> TypedEvidenceInput:
    try:
        observations = tuple(
            TypedObservationInput(**observation) for observation in raw["observations"]
        )
        return TypedEvidenceInput(
            **{key: value for key, value in raw.items() if key != "observations"},
            observations=observations,
        )
    except (KeyError, TypeError) as exc:
        raise CompetencyEvidenceReportError(
            "The committed typed evidence fixture input is malformed."
        ) from exc


def _verify_committed_typed_fixture_pipeline(
    base_dir: Path,
    spec,
    canonical,
) -> None:
    fixture_path = base_dir / "tests" / "fixtures" / "evidence" / "typed_v1.json"
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompetencyEvidenceReportError(
            f"{fixture_path}: could not read the typed evidence fixture."
        ) from exc
    _require_equal(
        "Typed fixture schema",
        fixture.get("schema_version"),
        "grounded-growth-typed-evidence-fixture-v1",
    )
    _require_equal(
        "Typed fixture algorithm",
        fixture.get("algorithm_version"),
        TYPED_EVIDENCE_ALGORITHM_VERSION,
    )
    _require_equal(
        "Typed fixture rules",
        fixture.get("rules_schema_version"),
        TYPED_EVIDENCE_RULES_VERSION,
    )
    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        raise CompetencyEvidenceReportError("The committed typed evidence fixture requires cases.")

    results: dict[str, tuple[TypedEvidenceInput, dict[str, Any], Any]] = {}
    decimal_fields = {
        "performance",
        "quality",
        "independence",
        "context_breadth",
        "repetition_multiplier",
        "contradiction_level",
        "base_evidence_mass",
        "competency_performance",
    }
    for case in cases:
        if not isinstance(case, dict):
            raise CompetencyEvidenceReportError(
                "The committed typed evidence fixture case is malformed."
            )
        evidence = _typed_input_from_mapping(case["input"])
        result = evaluate_typed_evidence(evidence, case["rules"], spec=spec)
        _require_equal(
            f"{case['case_id']} version-dispatched replay",
            replay_evidence_by_version(
                TYPED_EVIDENCE_ALGORITHM_VERSION,
                result.input_snapshot,
            ),
            result,
        )
        expected = case["expected"]
        for field, expected_value in expected.items():
            if field == "materialized_spec_hash" or field == "materialized_rules_hash":
                actual = result.input_snapshot[field]
            else:
                actual = getattr(result, field)
                if field in decimal_fields and actual is not None:
                    actual = f"{actual:.4f}"
                elif isinstance(actual, tuple):
                    actual = list(actual)
            _require_equal(
                f"{case['case_id']} expected {field}",
                actual,
                expected_value,
            )
        results[case["case_id"]] = (evidence, case["rules"], result)

    try:
        first_input, first_rules, first_result = results["TYPED-ALL-KINDS-01"]
    except KeyError as exc:
        raise CompetencyEvidenceReportError(
            "The all-kinds typed evidence fixture is required."
        ) from exc
    second_input = replace(
        first_input,
        event_key="EVENT-TYPED-001-CONTEXT-B",
        origin_key="ORIGIN-TYPED-001-CONTEXT-B",
        context_key="CONTEXT-B",
    )
    second_result = evaluate_typed_evidence(
        second_input,
        first_rules,
        spec=spec,
    )
    candidates = (
        candidate_from_typed_evidence(first_result),
        candidate_from_typed_evidence(second_result),
    )
    _require_equal(
        "Derived competency provenance is observed-only",
        set(candidates[0].provenance_kinds),
        {
            "firsthand_self_report",
            "objective_indicator",
            "reviewed_artifact",
        },
    )
    _require_equal(
        "Derived competency measurement kinds are rubric-bounded",
        set(candidates[0].measurement_kinds),
        {"artifact", "boolean", "objective"},
    )
    projection = project_competency_evidence(
        candidates=candidates,
        assessment_epoch_id=first_input.assessment_epoch_id,
        competency_id=first_input.competency_stable_id,
        as_of_date=first_input.as_of_date,
    )
    _require_equal(
        "Typed-to-competency shadow version",
        projection.algorithm_version,
        COMPETENCY_EVIDENCE_SHADOW_VERSION,
    )
    _require_equal(
        "Typed-to-competency included events",
        projection.included_event_count,
        2,
    )
    _require_equal(
        "Direct competency baseline boundary",
        (projection.evidence_state, projection.competency_estimate),
        ("evidence_observed", None),
    )
    _require_equal(
        "Cross-context transfer promotion",
        {contribution.transfer_disposition for contribution in projection.contributions},
        {"cross_context_supported"},
    )

    reversed_projection = project_competency_evidence(
        candidates=candidates,
        assessment_epoch_id=first_input.assessment_epoch_id,
        competency_id=first_input.competency_stable_id,
        as_of_date=first_input.as_of_date,
        reversed_event_keys=(first_input.event_key,),
    )
    _require_equal(
        "Competency reversal",
        (
            reversed_projection.included_event_count,
            reversed_projection.reversed_event_count,
        ),
        (1, 1),
    )
    fully_reversed = project_competency_evidence(
        candidates=candidates,
        assessment_epoch_id=first_input.assessment_epoch_id,
        competency_id=first_input.competency_stable_id,
        as_of_date=first_input.as_of_date,
        reversed_event_keys=(
            first_input.event_key,
            second_input.event_key,
        ),
    )
    _require_equal(
        "Fully reversed competency state",
        (
            fully_reversed.evidence_state,
            fully_reversed.included_event_count,
            fully_reversed.evidence_mass,
        ),
        ("unknown", 0, Decimal("0.000000")),
    )
    empty_projection = project_competency_evidence(
        candidates=(),
        assessment_epoch_id=first_input.assessment_epoch_id,
        competency_id=first_input.competency_stable_id,
        policy_id=first_input.scoring_policy_id,
        as_of_date=first_input.as_of_date,
    )
    _require_equal(
        "Evidence-only unknown state",
        (
            empty_projection.evidence_state,
            empty_projection.competency_estimate,
            empty_projection.event_count,
        ),
        ("unknown", None, 0),
    )

    mapping = next(
        item
        for item in canonical.model["competency_lever_links"]
        if item["competency_id"] == first_input.competency_stable_id
    )
    totals: dict[str, Decimal] = {}
    for item in canonical.model["competency_lever_links"]:
        for lever_id, weight in item["lever_weights"].items():
            totals[lever_id] = totals.get(lever_id, Decimal("0")) + Decimal(str(weight))
    weights = tuple(
        LeverWeight(
            lever_id=lever_id,
            weight=Decimal(str(weight)),
            total_competency_weight=totals[lever_id],
        )
        for lever_id, weight in sorted(mapping["lever_weights"].items())
    )
    baselines = {
        weight.lever_id: BaselineMass(
            lever_id=weight.lever_id,
            alpha=Decimal("1"),
            beta=Decimal("1"),
            confidence=Decimal("0.4000"),
        )
        for weight in weights
    }
    lever_shadow = project_competency_to_levers(
        competency_projection=projection,
        baselines=baselines,
        weights=weights,
        baseline_assessment_epoch_id=first_input.assessment_epoch_id,
        canonical_lever_ids=tuple(mapping["lever_weights"]),
        canonical_mapping_fingerprint=competency_lever_mapping_fingerprint(
            competency_id=first_input.competency_stable_id,
            weights=weights,
        ),
    )
    _require_equal(
        "Competency-to-lever shadow version",
        lever_shadow.algorithm_version,
        COMPETENCY_LEVER_SHADOW_VERSION,
    )
    _require_equal(
        "Full canonical parent mapping",
        {lever.lever_id for lever in lever_shadow.projection.levers},
        set(mapping["lever_weights"]),
    )
    _require_equal(
        "One allocation per typed event",
        set(lever_shadow.allocated_event_keys),
        {first_input.event_key, second_input.event_key},
    )


def _expect_competency_contract_error(
    label: str,
    action: Callable[[], Any],
    expected_message: str,
) -> None:
    try:
        action()
    except CompetencyScoringContractError as exc:
        if expected_message not in str(exc):
            raise CompetencyEvidenceReportError(f"{label}: unexpected rejection: {exc}") from exc
        return
    raise CompetencyEvidenceReportError(f"{label}: malformed projection was not rejected.")


def _verify_competency_shadow_fixture(base_dir: Path) -> None:
    fixture_path = base_dir / "tests" / "fixtures" / "scoring" / "competency_shadow_v1.json"
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompetencyEvidenceReportError(
            f"{fixture_path}: could not read the competency shadow fixture."
        ) from exc
    _require_equal(
        "Competency shadow fixture version",
        fixture.get("competency_evidence_algorithm_version"),
        COMPETENCY_EVIDENCE_SHADOW_VERSION,
    )
    _require_equal(
        "Competency lever fixture version",
        fixture.get("competency_lever_algorithm_version"),
        COMPETENCY_LEVER_SHADOW_VERSION,
    )
    _require_equal(
        "Lever projection fixture version",
        fixture.get("projection_algorithm_version"),
        SCORING_ALGORITHM_VERSION,
    )

    candidates = tuple(
        CompetencyEvidenceCandidate(
            **{
                **raw,
                "competency_performance": Decimal(raw["competency_performance"]),
                "base_evidence_mass": Decimal(raw["base_evidence_mass"]),
                "provenance_kinds": tuple(raw["provenance_kinds"]),
                "measurement_kinds": tuple(raw["measurement_kinds"]),
                "upstream_withholding_reasons": tuple(raw["upstream_withholding_reasons"]),
            }
        )
        for raw in fixture["candidates"]
    )
    projection = project_competency_evidence(
        candidates=candidates,
        assessment_epoch_id=fixture["assessment_epoch_id"],
        competency_id=fixture["competency_id"],
        policy_id=fixture["policy_id"],
        as_of_date=fixture["as_of_date"],
        reversed_event_keys=fixture["reversed_event_keys"],
    )
    expected = fixture["expected_competency"]
    for field in (
        "evidence_state",
        "competency_estimate",
        "event_count",
        "included_event_count",
        "withheld_event_count",
        "reversed_event_count",
    ):
        _require_equal(
            f"Competency shadow fixture {field}",
            getattr(projection, field),
            expected[field],
        )
    for field in ("evidence_mass", "success_mass", "failure_mass"):
        _require_equal(
            f"Competency shadow fixture {field}",
            format(getattr(projection, field), "f"),
            expected[field],
        )
    contributions = {
        contribution.event_key: contribution for contribution in projection.contributions
    }
    _require_equal(
        "Competency shadow fixture contribution keys",
        set(contributions),
        set(expected["contributions"]),
    )
    for event_key, expected_contribution in expected["contributions"].items():
        contribution = contributions[event_key]
        for field in (
            "included",
            "withholding_reason",
            "transfer_disposition",
        ):
            _require_equal(
                f"{event_key} competency contribution {field}",
                getattr(contribution, field),
                expected_contribution[field],
            )
        _require_equal(
            f"{event_key} competency contribution withholding reasons",
            contribution.withholding_reasons,
            (
                (expected_contribution["withholding_reason"],)
                if expected_contribution["withholding_reason"]
                else ()
            ),
        )
        for field in (
            "competency_performance",
            "evidence_mass",
            "success_mass",
            "failure_mass",
        ):
            _require_equal(
                f"{event_key} competency contribution {field}",
                format(getattr(contribution, field), "f"),
                expected_contribution[field],
            )

    empty = project_competency_evidence(
        candidates=(),
        assessment_epoch_id=fixture["assessment_epoch_id"],
        competency_id=fixture["competency_id"],
        policy_id=fixture["policy_id"],
        as_of_date=fixture["as_of_date"],
    )
    for field, expected_value in fixture["empty_expected"].items():
        actual = getattr(empty, field)
        if isinstance(actual, Decimal):
            actual = format(actual, "f")
        _require_equal(
            f"Empty competency fixture {field}",
            actual,
            expected_value,
        )

    baselines = {
        lever_id: BaselineMass(
            lever_id=lever_id,
            alpha=Decimal(values["alpha"]),
            beta=Decimal(values["beta"]),
            confidence=Decimal(values["confidence"]),
        )
        for lever_id, values in fixture["baselines"].items()
    }
    weights = tuple(
        LeverWeight(
            lever_id=raw["lever_id"],
            weight=Decimal(raw["weight"]),
            total_competency_weight=Decimal(raw["total_competency_weight"]),
        )
        for raw in fixture["weights"]
    )
    canonical_lever_ids = tuple(fixture["canonical_lever_ids"])
    _require_equal(
        "Competency shadow fixture canonical lever envelope",
        set(canonical_lever_ids),
        set(baselines),
    )
    calculated_mapping_fingerprint = competency_lever_mapping_fingerprint(
        competency_id=fixture["competency_id"],
        weights=weights,
    )
    _require_equal(
        "Competency shadow fixture canonical mapping fingerprint",
        calculated_mapping_fingerprint,
        fixture["canonical_mapping_fingerprint"],
    )
    lever_shadow = project_competency_to_levers(
        competency_projection=projection,
        baselines=baselines,
        weights=weights,
        baseline_assessment_epoch_id=fixture["baseline_assessment_epoch_id"],
        canonical_lever_ids=canonical_lever_ids,
        canonical_mapping_fingerprint=fixture["canonical_mapping_fingerprint"],
        minimum_transfer_disposition=fixture["minimum_transfer_disposition"],
    )
    _require_equal(
        "Competency shadow golden allocated events",
        list(lever_shadow.allocated_event_keys),
        fixture["expected_lever"]["allocated_event_keys"],
    )
    _require_equal(
        "Competency shadow golden baseline epoch",
        lever_shadow.baseline_assessment_epoch_id,
        fixture["baseline_assessment_epoch_id"],
    )
    _require_equal(
        "Competency shadow golden mapping fingerprint",
        lever_shadow.canonical_mapping_fingerprint,
        fixture["canonical_mapping_fingerprint"],
    )
    score_projection = lever_shadow.projection
    for field in (
        "event_count",
        "scored_event_count",
        "withheld_event_count",
    ):
        _require_equal(
            f"Competency lever fixture {field}",
            getattr(score_projection, field),
            fixture["expected_lever"][field],
        )
    projected_levers = {lever.lever_id: lever for lever in score_projection.levers}
    _require_equal(
        "Competency lever fixture full mapping",
        set(projected_levers),
        set(fixture["expected_lever"]["levers"]),
    )
    for lever_id, expected_lever in fixture["expected_lever"]["levers"].items():
        lever = projected_levers[lever_id]
        _require_equal(
            f"{lever_id} task coefficient",
            format(lever.contributions[0].task_coefficient, "f"),
            expected_lever["task_coefficient"],
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
            _require_equal(
                f"{lever_id} {field}",
                format(getattr(lever, field), "f"),
                expected_lever[field],
            )

    projection_kwargs = {
        "competency_projection": projection,
        "baselines": baselines,
        "weights": weights,
        "canonical_lever_ids": canonical_lever_ids,
        "canonical_mapping_fingerprint": fixture["canonical_mapping_fingerprint"],
        "minimum_transfer_disposition": fixture["minimum_transfer_disposition"],
    }
    _expect_competency_contract_error(
        "Assessment-epoch isolation",
        lambda: project_competency_to_levers(
            **projection_kwargs,
            baseline_assessment_epoch_id="DIFFERENT-ASSESSMENT-EPOCH",
        ),
        "same assessment epoch",
    )
    incomplete_baselines = dict(baselines)
    incomplete_baselines.pop(canonical_lever_ids[0])
    _expect_competency_contract_error(
        "Full canonical mapping envelope",
        lambda: project_competency_to_levers(
            **{
                **projection_kwargs,
                "baselines": incomplete_baselines,
            },
            baseline_assessment_epoch_id=fixture["baseline_assessment_epoch_id"],
        ),
        "complete canonical competency mapping",
    )
    _expect_competency_contract_error(
        "Canonical mapping fingerprint",
        lambda: project_competency_to_levers(
            **{
                **projection_kwargs,
                "canonical_mapping_fingerprint": "0" * 64,
            },
            baseline_assessment_epoch_id=fixture["baseline_assessment_epoch_id"],
        ),
        "does not match",
    )


def _policy_candidates(policy_id: str) -> tuple[CompetencyEvidenceCandidate, ...]:
    def candidate(
        suffix: str,
        *,
        provenance: tuple[str, ...],
        measurements: tuple[str, ...],
        qualified_attestation_valid: bool = False,
    ) -> CompetencyEvidenceCandidate:
        return CompetencyEvidenceCandidate(
            event_key=f"M6B-{policy_id}-{suffix}",
            origin_key=f"M6B-ORIGIN-{policy_id}-{suffix}",
            assessment_epoch_id="M6B-POLICY-EPOCH",
            protocol_stable_id="M6B-SYNTHETIC-PROTOCOL",
            action_stable_id=f"M6B-SYNTHETIC-ACTION-{suffix}",
            competency_id=FRIENDSHIP_COMPETENCY_ID,
            policy_id=policy_id,
            competency_performance=Decimal("0.8000"),
            base_evidence_mass=Decimal("0.2500"),
            direction="supports",
            adverse=False,
            provenance_kinds=provenance,
            measurement_kinds=measurements,
            context_key=f"M6B-CONTEXT-{suffix}",
            transfer_disposition="context_bound",
            observed_on="2026-07-27",
            max_age_days=365,
            upstream_withholding_reasons=(),
            qualified_attestation_valid=qualified_attestation_valid,
        )

    if policy_id == "SP-CORROBORATION-REQUIRED":
        return (
            candidate(
                "SELF",
                provenance=("firsthand_self_report",),
                measurements=("boolean",),
            ),
            candidate(
                "OBSERVER",
                provenance=("consented_observer",),
                measurements=("attestation",),
            ),
        )
    if policy_id == "SP-ARTIFACT-OBJECTIVE-PREFERRED":
        return (
            candidate(
                "ARTIFACT",
                provenance=("reviewed_artifact",),
                measurements=("artifact",),
            ),
        )
    if policy_id == "SP-QUALIFIED-EVIDENCE-REQUIRED":
        return (
            candidate(
                "QUALIFIED",
                provenance=("qualified_attestation",),
                measurements=("attestation",),
                qualified_attestation_valid=True,
            ),
        )
    return (
        candidate(
            "SELF",
            provenance=("firsthand_self_report",),
            measurements=("boolean",),
        ),
    )


def _policy_rows(practices) -> tuple[dict[str, Any], ...]:
    registry_ids = set(practices.scoring_policies)
    _require_equal("Canonical scoring-policy IDs", registry_ids, set(SUPPORTED_POLICY_IDS))
    _require_equal(
        "Typed scoring-policy IDs",
        set(SUPPORTED_SCORING_POLICY_IDS),
        set(SUPPORTED_POLICY_IDS),
    )
    legacy_production_counts: dict[str, int] = dict.fromkeys(registry_ids, 0)
    for activation in practices.activation_entries.values():
        if activation["score_active"]:
            legacy_production_counts[activation["scoring_policy_id"]] += 1

    rows = []
    for policy_id in sorted(registry_ids):
        projection = project_competency_evidence(
            candidates=_policy_candidates(policy_id),
            assessment_epoch_id="M6B-POLICY-EPOCH",
            competency_id=FRIENDSHIP_COMPETENCY_ID,
            as_of_date="2026-07-27",
        )
        outcome = (
            projection.included_event_count,
            projection.withheld_event_count,
        )
        _require_equal(
            f"{policy_id} synthetic execution outcome",
            outcome,
            _EXPECTED_POLICY_OUTCOMES[policy_id],
        )
        if policy_id == "SP-QUALIFIED-EVIDENCE-REQUIRED":
            invalid = replace(
                _policy_candidates(policy_id)[0],
                event_key="M6B-QUALIFIED-INVALID",
                origin_key="M6B-QUALIFIED-INVALID-ORIGIN",
                qualified_attestation_valid=False,
            )
            invalid_projection = project_competency_evidence(
                candidates=(invalid,),
                assessment_epoch_id="M6B-POLICY-EPOCH",
                competency_id=FRIENDSHIP_COMPETENCY_ID,
                as_of_date="2026-07-27",
            )
            _require_equal(
                "Invalid qualified attestation is withheld",
                (
                    invalid_projection.included_event_count,
                    invalid_projection.contributions[0].withholding_reason,
                ),
                (0, "qualified_evidence_policy_not_satisfied"),
            )
        policy = practices.scoring_policies[policy_id]
        rows.append(
            {
                "contract_version": COMPETENCY_EVIDENCE_READINESS_CONTRACT_VERSION,
                "policy_id": policy_id,
                "policy_name": policy["name"],
                "registry_state_effect": policy["state_effect"],
                "competency_shadow_version": COMPETENCY_EVIDENCE_SHADOW_VERSION,
                "synthetic_execution": "passed",
                "included_events": projection.included_event_count,
                "withheld_events": projection.withheld_event_count,
                "legacy_v1_score_active_protocols": legacy_production_counts[policy_id],
                "typed_production_protocols": 0,
                "typed_score_active_protocols": 0,
                "typed_execution_boundary": "pure_shadow_only",
                "production_status": (
                    "legacy_v1_only" if legacy_production_counts[policy_id] else "not_authorized"
                ),
            }
        )
    return tuple(rows)


def _verify_production_source_contract(canonical, practices) -> None:
    _require_equal(
        "Production score-eligibility version",
        PRODUCTION_SCORE_ELIGIBILITY_CONTRACT_VERSION,
        "GG-PRODUCTION-SCORE-ELIGIBILITY-1.0",
    )
    protocol = next(
        (item for item in practices.protocols if item["stable_id"] == FRIENDSHIP_PROTOCOL_ID),
        None,
    )
    if protocol is None:
        raise CompetencyEvidenceReportError(
            "The canonical friendship production protocol is missing."
        )
    _require_equal(
        "Friendship parent competency",
        protocol["parent_competency_id"],
        FRIENDSHIP_COMPETENCY_ID,
    )
    _require_equal(
        "Friendship evidence rules",
        protocol["evidence_and_scoring"]["observation_contract_version"],
        PRODUCTION_EVIDENCE_RULES_VERSION,
    )
    _require_equal(
        "Friendship recommendation targets",
        set(protocol["evidence_and_scoring"]["recommendation_target_lever_ids"]),
        set(FRIENDSHIP_TARGET_LEVER_IDS),
    )
    source_actions = tuple(
        {
            "action_stable_id": action["stable_id"],
            "sequence": action["sequence"],
            "evidence_rules": action["evidence_rules"],
        }
        for action in sorted(
            protocol["intervention"]["actions"],
            key=lambda item: (item["sequence"], item["stable_id"]),
        )
    )
    _require_equal(
        "Friendship actions and evidence rules",
        source_actions,
        FRIENDSHIP_ACTIONS,
    )

    activation = practices.activation_entries[FRIENDSHIP_PROTOCOL_ID]
    _require_equal(
        "Friendship production activation",
        (
            activation["scoring_policy_id"],
            activation["score_active"],
            activation["activation_status"],
            activation["approved_contract"],
            activation["shadow_test_status"],
        ),
        (
            "SP-SELF-REPORT-ELIGIBLE",
            True,
            "active",
            PRODUCTION_SCORE_STATE_VERSION,
            "accepted_and_activated",
        ),
    )

    mapping = next(
        item
        for item in canonical.model["competency_lever_links"]
        if item["competency_id"] == FRIENDSHIP_COMPETENCY_ID
    )
    weights = {
        lever_id: Decimal(str(weight)) for lever_id, weight in mapping["lever_weights"].items()
    }
    totals: dict[str, Decimal] = {}
    for item in canonical.model["competency_lever_links"]:
        for lever_id, weight in item["lever_weights"].items():
            totals[lever_id] = totals.get(lever_id, Decimal("0")) + Decimal(str(weight))
    actual_allocation = {
        lever_id: (weight, totals[lever_id]) for lever_id, weight in weights.items()
    }
    _require_equal(
        "Friendship canonical allocation",
        actual_allocation,
        FRIENDSHIP_ALLOCATION,
    )
    payload = {
        "contract_version": PRODUCTION_SCORE_ELIGIBILITY_CONTRACT_VERSION,
        "protocol_stable_id": FRIENDSHIP_PROTOCOL_ID,
        "competency_stable_id": FRIENDSHIP_COMPETENCY_ID,
        "evidence_algorithm_version": EVIDENCE_ALGORITHM_VERSION,
        "evidence_schema_version": PRODUCTION_EVIDENCE_RULES_VERSION,
        "scoring_algorithm_version": SCORING_ALGORITHM_VERSION,
        "score_state_version": PRODUCTION_SCORE_STATE_VERSION,
        "target_lever_ids": sorted(FRIENDSHIP_TARGET_LEVER_IDS),
        "actions": list(source_actions),
        "allocation": [
            {
                "lever_id": lever_id,
                "weight": f"{weights[lever_id]:.4f}",
                "total_competency_weight": f"{totals[lever_id]:.4f}",
            }
            for lever_id in sorted(weights)
        ],
    }
    _require_equal(
        "Friendship production mapping fingerprint",
        _canonical_hash(payload),
        PRODUCTION_SCORE_MAPPING_FINGERPRINT,
    )


def _build_software_contract(base_dir: Path) -> _SoftwareContract:
    canonical = load_and_validate_bundle()
    practices = load_practice_content_bundle(base_dir)
    spec = load_typed_evidence_spec(base_dir / "data" / "evidence")

    _require_equal(
        "Typed evidence algorithm",
        spec.algorithm_version,
        TYPED_EVIDENCE_ALGORITHM_VERSION,
    )
    _require_equal(
        "Typed evidence rules",
        spec.rules_schema_version,
        TYPED_EVIDENCE_RULES_VERSION,
    )
    _require_equal(
        "Typed measurement normalization coverage",
        set(_MEASUREMENT_NORMALIZATION),
        set(spec.measurement_kinds),
    )
    _verify_legacy_dispatch()
    _verify_typed_dispatch(spec)
    _verify_committed_typed_fixture_pipeline(
        base_dir,
        spec,
        canonical,
    )
    _verify_competency_shadow_fixture(base_dir)
    policy_rows = _policy_rows(practices)
    _verify_production_source_contract(canonical, practices)

    competency_count = sum(
        len(domain["competencies"]) for domain in canonical.curriculum["domains"]
    )
    action_count = sum(len(protocol["intervention"]["actions"]) for protocol in practices.protocols)
    typed_protocols = [
        protocol
        for protocol in practices.protocols
        if protocol["evidence_and_scoring"]["observation_contract_version"]
        == TYPED_EVIDENCE_RULES_VERSION
    ]
    typed_protocol_ids = {protocol["stable_id"] for protocol in typed_protocols}
    typed_score_active = sum(
        activation["score_active"]
        for stable_id, activation in practices.activation_entries.items()
        if stable_id in typed_protocol_ids
    )
    catalog_counts = {
        "competencies": competency_count,
        "canonical_protocol_packages": len(practices.protocols),
        "practice_actions": action_count,
        "uncovered_competencies": competency_count - len(practices.protocols),
        "score_active_protocols": sum(
            activation["score_active"] for activation in practices.activation_entries.values()
        ),
    }
    _require_equal(
        "Frozen M6A catalog counts",
        catalog_counts,
        _EXPECTED_CATALOG_COUNTS,
    )
    _require_equal("Typed production protocol count", len(typed_protocols), 0)
    _require_equal("Typed score-active protocol count", typed_score_active, 0)

    review = practices.expert_reviews.get("ER-M6A-003")
    gap = practices.research_gaps.get("RG-M6A-002")
    if review is None or gap is None:
        raise CompetencyEvidenceReportError(
            "The M6B specialist-review and research-gap controls are required."
        )
    _require_equal("ER-M6A-003 status", review["status"], "pending")
    _require_equal("RG-M6A-002 status", gap["status"], "open")
    _require_equal(
        "ER-M6A-003 blocking gates",
        set(review["blocking_gates"]),
        {"m6b_acceptance", "mass_authoring", "score_activation"},
    )
    _require_equal(
        "RG-M6A-002 blocking gates",
        set(gap["blocking_gates"]),
        {"m6b_acceptance", "mass_authoring", "score_activation"},
    )
    specialist_review_complete = review["status"] == "complete" and set(
        review["completed_roles"]
    ) == set(review["required_roles"])
    research_gap_resolved = gap["status"] == "resolved"

    checks = {
        "canonical_catalog_exact": True,
        "canonical_mapping_envelope_rejection_exact": True,
        "competency_shadow_golden_fixture_exact": True,
        "competency_reversal_and_unknown_state_exact": True,
        "competency_to_full_parent_mapping_shadow_exact": True,
        "evidence_v1_dispatch_replay_exact": True,
        "assessment_epoch_isolation_exact": True,
        "production_score_eligibility_source_exact": True,
        "scoring_policy_registry_and_execution_exact": True,
        "typed_evidence_manifest_and_hash_exact": True,
        "typed_fixture_dispatch_replay_exact": True,
        "typed_production_boundary_exact": True,
        "typed_to_competency_shadow_exact": True,
    }
    software_ready = all(checks.values())
    capability_rows = tuple(
        {
            "contract_version": COMPETENCY_EVIDENCE_READINESS_CONTRACT_VERSION,
            "algorithm_version": spec.algorithm_version,
            "rules_version": spec.rules_schema_version,
            "measurement_kind": kind,
            "normalization_contract": _MEASUREMENT_NORMALIZATION[kind],
            "observation_states": ";".join(sorted(spec.observation_states)),
            "provenance_kinds": ";".join(sorted(spec.provenance_kinds)),
            "pure_engine_executable": "true",
            "historical_v1_unchanged": "true",
            "typed_production_protocols": len(typed_protocols),
            "typed_score_active_protocols": typed_score_active,
            "production_state_effect": "none",
            "privacy_boundary": ("structured_tokens_only_no_free_text_or_artifact_contents"),
        }
        for kind in sorted(spec.measurement_kinds)
    )
    readiness = {
        "contract_version": COMPETENCY_EVIDENCE_READINESS_CONTRACT_VERSION,
        "software_ready": software_ready,
        "specialist_review_complete": specialist_review_complete,
        "m6b_accepted": (software_ready and specialist_review_complete and research_gap_resolved),
        "deterministic_checks": checks,
        "contracts": {
            "preserved_curriculum_expansion": (EXPANSION_READINESS_CONTRACT_VERSION),
            "preserved_evidence": EVIDENCE_ALGORITHM_VERSION,
            "typed_evidence": TYPED_EVIDENCE_ALGORITHM_VERSION,
            "typed_evidence_rules": TYPED_EVIDENCE_RULES_VERSION,
            "competency_evidence_shadow": (COMPETENCY_EVIDENCE_SHADOW_VERSION),
            "competency_lever_shadow": COMPETENCY_LEVER_SHADOW_VERSION,
            "production_score_eligibility": (PRODUCTION_SCORE_ELIGIBILITY_CONTRACT_VERSION),
            "production_score_eligibility_fingerprint": (PRODUCTION_SCORE_MAPPING_FINGERPRINT),
        },
        "catalog": catalog_counts,
        "scoring_policies": {
            "canonical": len(policy_rows),
            "synthetically_executed": len(policy_rows),
        },
        "typed_production_protocols": len(typed_protocols),
        "typed_score_active_protocols": typed_score_active,
        "governance": {
            "expert_review": {
                "review_id": "ER-M6A-003",
                "status": review["status"],
                "required_roles": review["required_roles"],
                "completed_roles": review["completed_roles"],
                "blocking_gates": review["blocking_gates"],
            },
            "research_gap": {
                "gap_id": "RG-M6A-002",
                "status": gap["status"],
                "blocking_gates": gap["blocking_gates"],
            },
        },
        "boundary": (
            "Software readiness is additive and shadow-only. Pending specialist "
            "review and the open research gap block M6B acceptance, mass "
            "authoring, and typed production score activation."
        ),
    }
    return _SoftwareContract(
        capability_rows=capability_rows,
        policy_rows=policy_rows,
        readiness=readiness,
    )


def build_competency_evidence_report_outputs(
    base_dir: Path | None = None,
) -> dict[Path, bytes]:
    resolved_base = (base_dir or settings.BASE_DIR).resolve()
    contract = _build_software_contract(resolved_base)
    return {
        REPORT_PATHS["typed_capability"]: _csv_bytes(
            contract.capability_rows,
            [
                "contract_version",
                "algorithm_version",
                "rules_version",
                "measurement_kind",
                "normalization_contract",
                "observation_states",
                "provenance_kinds",
                "pure_engine_executable",
                "historical_v1_unchanged",
                "typed_production_protocols",
                "typed_score_active_protocols",
                "production_state_effect",
                "privacy_boundary",
            ],
        ),
        REPORT_PATHS["scoring_policy"]: _csv_bytes(
            contract.policy_rows,
            [
                "contract_version",
                "policy_id",
                "policy_name",
                "registry_state_effect",
                "competency_shadow_version",
                "synthetic_execution",
                "included_events",
                "withheld_events",
                "legacy_v1_score_active_protocols",
                "typed_production_protocols",
                "typed_score_active_protocols",
                "typed_execution_boundary",
                "production_status",
            ],
        ),
        REPORT_PATHS["readiness"]: _json_bytes(contract.readiness),
    }


def write_or_check_competency_evidence_reports(
    *,
    base_dir: Path | None = None,
    check: bool,
) -> tuple[Path, ...]:
    resolved_base = (base_dir or settings.BASE_DIR).resolve()
    outputs = build_competency_evidence_report_outputs(resolved_base)
    changed: list[Path] = []
    for relative, expected in outputs.items():
        path = resolved_base / relative
        actual = path.read_bytes() if path.exists() else None
        if actual == expected:
            continue
        changed.append(relative)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
    if check and changed:
        raise CompetencyEvidenceReportError(
            "Generated competency-evidence reports are missing or stale: "
            + ", ".join(path.as_posix() for path in changed)
        )
    return tuple(changed)
