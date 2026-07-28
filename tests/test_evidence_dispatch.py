from decimal import Decimal
from types import SimpleNamespace

import pytest

from growth.domain.evidence import (
    EVIDENCE_ALGORITHM_VERSION,
    EvidenceInput,
    evaluate_evidence,
    replay_evidence,
)
from growth.domain.evidence_dispatch import (
    EvidenceDispatchError,
    replay_evidence_by_version,
)
from growth.domain.typed_evidence import (
    TYPED_EVIDENCE_ALGORITHM_VERSION,
    TypedEvidenceInput,
    TypedObservationInput,
    evaluate_typed_evidence,
)
from growth.services.evidence import EvidenceWorkflowError, verify_evidence_event


class SnapshotThatMustNotBeRead(dict):
    def __getitem__(self, key):
        raise AssertionError(f"Unknown-version dispatch parsed snapshot key {key!r}.")

    def get(self, key, default=None):
        raise AssertionError(f"Unknown-version dispatch parsed snapshot key {key!r}.")


def _legacy_result():
    return evaluate_evidence(
        EvidenceInput(
            protocol_stable_id="PRACTICE-FRIENDSHIP-01",
            action_stable_id="PRACTICE-FRIENDSHIP-01-A1",
            action_attempted=True,
            action_completed=True,
            observations={
                "moved_beyond_transactional": True,
                "meaningful_information_shared": True,
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
            "schema_version": "practice-observation-v1",
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


def test_legacy_dispatch_preserves_the_frozen_api_and_outputs():
    result = _legacy_result()

    assert result.base_evidence_mass == Decimal("0.4675")
    assert replay_evidence(result.input_snapshot) == result
    assert (
        replay_evidence_by_version(
            EVIDENCE_ALGORITHM_VERSION,
            result.input_snapshot,
        )
        == result
    )


def test_unknown_version_fails_before_snapshot_parsing():
    with pytest.raises(
        EvidenceDispatchError,
        match="Unsupported evidence algorithm_version",
    ):
        replay_evidence_by_version(
            "GG-EVIDENCE-UNKNOWN-99.0",
            SnapshotThatMustNotBeRead(),
        )


def test_typed_dispatch_uses_the_additive_replay_contract():
    result = evaluate_typed_evidence(
        TypedEvidenceInput(
            event_key="EVENT-TYPED-01",
            origin_key="ORIGIN-TYPED-01",
            assessment_epoch_id="ASSESSMENT-EPOCH-01",
            protocol_stable_id="PRACTICE-TYPED-01",
            action_stable_id="PRACTICE-TYPED-01-A1",
            competency_stable_id="17.03",
            scoring_policy_id="SP-SHADOW-ONLY",
            action_attempted=True,
            action_completed=True,
            observations=(
                TypedObservationInput(
                    measurement_id="MEASURE-BOOLEAN-01",
                    kind="boolean",
                    state="observed",
                    provenance_kind="firsthand_self_report",
                    value=True,
                ),
            ),
            support_level="self_directed",
            context_comparison="first_record",
            context_key="CONTEXT-01",
            evidence_direction="supports",
            adverse_indicator_ids=(),
            repetition_index=1,
            observed_on="2026-07-27",
            as_of_date="2026-07-27",
        ),
        {
            "schema_version": "typed-evidence-rules-v1",
            "max_age_days": None,
            "competency_measurement_ids": ["MEASURE-BOOLEAN-01"],
            "transfer_disposition": "context_bound",
            "measurements": [
                {
                    "measurement_id": "MEASURE-BOOLEAN-01",
                    "kind": "boolean",
                    "role": "primary",
                    "weight": "1.0",
                    "allowed_provenance": ["firsthand_self_report"],
                    "expected": True,
                }
            ],
        },
    )

    assert (
        replay_evidence_by_version(
            TYPED_EVIDENCE_ALGORITHM_VERSION,
            result.input_snapshot,
        )
        == result
    )

    with pytest.raises(EvidenceDispatchError, match="incomplete or malformed"):
        replay_evidence_by_version(
            TYPED_EVIDENCE_ALGORITHM_VERSION,
            {},
        )


def test_service_verification_normalizes_malformed_typed_replay_errors():
    event = SimpleNamespace(
        pk="EVIDENCE-TYPED-MALFORMED",
        algorithm_version=TYPED_EVIDENCE_ALGORITHM_VERSION,
        input_snapshot={},
    )

    with pytest.raises(
        EvidenceWorkflowError,
        match="EVIDENCE-TYPED-MALFORMED: Typed evidence snapshot is incomplete or malformed",
    ):
        verify_evidence_event(event)
