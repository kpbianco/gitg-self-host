from __future__ import annotations

import json
import threading
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, OperationalError, close_old_connections

from growth.domain.personal_os import (
    AUDIT_PROMPT_DEFINITIONS,
    AUDIT_PROMPT_IDS,
    IDENTITY_SECTION_DEFINITIONS,
    IDENTITY_SECTION_IDS,
    MAX_CANONICAL_SNAPSHOT_BYTES,
    PersonalOSContractError,
    PersonalOSValue,
    PersonalOSValueState,
    build_personal_os_snapshot,
    canonical_personal_os_snapshot_size,
)
from growth.models import AssessmentRun, PersonalOSRevision
from growth.services.personal_os import (
    PersonalOSServiceError,
    PersonalOSWriteConflictError,
    _winner_after_integrity_conflict,
    latest_personal_os_revision,
    record_personal_os_revision,
)

FIXTURE = Path(__file__).parent / "fixtures" / "personal_os" / "personal_os_v1.json"


def identity_values(*, mission="Synthetic mission", state=PersonalOSValueState.PROVIDED):
    value = None if state != PersonalOSValueState.PROVIDED else mission
    list_value = None if state != PersonalOSValueState.PROVIDED else ["Synthetic first"]
    return {
        "mission": PersonalOSValue(state, value),
        "principles": PersonalOSValue(state, list_value),
        "anti_goals": PersonalOSValue(state, list_value),
        "twelve_month_direction": PersonalOSValue(state, value),
        "priority_stack": PersonalOSValue(state, list_value),
    }


def audit_values(*, text="Synthetic observation", state=PersonalOSValueState.PROVIDED):
    value = None if state != PersonalOSValueState.PROVIDED else text
    return {section_id: PersonalOSValue(state, value) for section_id in AUDIT_PROMPT_IDS}


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


def test_exact_sections_prompts_and_nonjudgmental_no_score_contract():
    assert IDENTITY_SECTION_IDS == (
        "mission",
        "principles",
        "anti_goals",
        "twelve_month_direction",
        "priority_stack",
    )
    assert AUDIT_PROMPT_IDS == (
        "current_truth",
        "autopilot_pattern",
        "misalignment_or_fragmentation",
        "deliberate_next_step",
    )
    all_copy = " ".join(
        f"{item.prompt} {item.help_text}"
        for item in (*IDENTITY_SECTION_DEFINITIONS.values(), *AUDIT_PROMPT_DEFINITIONS.values())
    ).lower()
    assert "user-authored" in all_copy
    assert "minimum private detail" in all_copy
    assert "not a diagnosis" in all_copy
    assert "moral ranking" in all_copy
    assert "diminished worth" in all_copy
    assert "destiny" in all_copy
    for forbidden_score in (
        "alignment_score",
        "autopilot_score",
        "personality_score",
        "virtue_score",
        "worth_score",
        "diagnostic_score",
    ):
        assert forbidden_score not in (*IDENTITY_SECTION_IDS, *AUDIT_PROMPT_IDS)


@pytest.mark.parametrize("state", list(PersonalOSValueState))
def test_all_explicit_states_preserve_no_hidden_values(state):
    snapshot = build_personal_os_snapshot(
        assessment_epoch_id="ASSESSMENT-STATES",
        identity_sections=identity_values(state=state),
        audit_responses=audit_values(state=state),
    )
    for group in ("identity_sections", "audit_responses"):
        for item in snapshot.payload[group].values():
            assert item["state"] == state.value
            assert (item["value"] is not None) is (state is PersonalOSValueState.PROVIDED)


@pytest.mark.parametrize("section_id", IDENTITY_SECTION_IDS)
def test_nonprovided_identity_sections_reject_hidden_values(section_id):
    values = identity_values(state=PersonalOSValueState.UNKNOWN)
    values[section_id] = PersonalOSValue(PersonalOSValueState.UNKNOWN, "hidden")
    with pytest.raises(PersonalOSContractError, match="must be null"):
        build_personal_os_snapshot(
            assessment_epoch_id="ASSESSMENT-HIDDEN",
            identity_sections=values,
            audit_responses=audit_values(),
        )


@pytest.mark.parametrize("length", [1, 500])
def test_scalar_boundaries_are_accepted(length):
    value = "x" * length
    snapshot = build_personal_os_snapshot(
        assessment_epoch_id="ASSESSMENT-SCALAR",
        identity_sections=identity_values(mission=value),
        audit_responses=audit_values(text=value),
    )
    assert snapshot.payload["identity_sections"]["mission"]["value"] == value


@pytest.mark.parametrize("value", ["", "   ", "x" * 501, 3, True, ["wrong"]])
def test_scalar_blank_overbound_and_wrong_types_fail_closed(value):
    values = identity_values()
    values["mission"] = PersonalOSValue("provided", value)
    with pytest.raises(PersonalOSContractError, match="mission value"):
        build_personal_os_snapshot(
            assessment_epoch_id="ASSESSMENT-BAD-SCALAR",
            identity_sections=values,
            audit_responses=audit_values(),
        )


def test_unpaired_unicode_surrogate_fails_with_contract_diagnostic():
    values = identity_values(mission="\ud800")
    with pytest.raises(PersonalOSContractError, match="valid Unicode encodable as UTF-8"):
        build_personal_os_snapshot(
            assessment_epoch_id="ASSESSMENT-BAD-UNICODE",
            identity_sections=values,
            audit_responses=audit_values(),
        )


@pytest.mark.parametrize("count", [1, 5])
@pytest.mark.parametrize("item_length", [1, 160])
def test_list_count_and_item_boundaries_are_accepted(count, item_length):
    values = identity_values()
    values["principles"] = PersonalOSValue(
        "provided", [chr(65 + index) + "x" * (item_length - 1) for index in range(count)]
    )
    snapshot = build_personal_os_snapshot(
        assessment_epoch_id="ASSESSMENT-LIST-BOUNDARY",
        identity_sections=values,
        audit_responses=audit_values(),
    )
    assert len(snapshot.payload["identity_sections"]["principles"]["value"]) == count


@pytest.mark.parametrize(
    "value",
    [[], ["a"] * 6, [""], ["  "], ["x" * 161], ["same", "same"], "not-a-list", [3]],
)
def test_list_blank_count_duplicate_overbound_and_wrong_types_fail_closed(value):
    values = identity_values()
    values["priority_stack"] = PersonalOSValue("provided", value)
    with pytest.raises(PersonalOSContractError, match="priority_stack"):
        build_personal_os_snapshot(
            assessment_epoch_id="ASSESSMENT-BAD-LIST",
            identity_sections=values,
            audit_responses=audit_values(),
        )


def test_missing_extra_wrong_shape_and_unknown_version_fail_closed():
    identity = identity_values()
    del identity["mission"]
    with pytest.raises(PersonalOSContractError, match="missing mission"):
        build_personal_os_snapshot(
            assessment_epoch_id="A-1",
            identity_sections=identity,
            audit_responses=audit_values(),
        )
    identity["mission"] = PersonalOSValue("provided", "Synthetic")
    identity["invented"] = PersonalOSValue("unknown")
    with pytest.raises(PersonalOSContractError, match="unexpected invented"):
        build_personal_os_snapshot(
            assessment_epoch_id="A-1",
            identity_sections=identity,
            audit_responses=audit_values(),
        )
    identity.pop("invented")
    identity["mission"] = {"state": "provided", "value": "Synthetic", "extra": None}
    with pytest.raises(PersonalOSContractError, match="exactly state and value"):
        build_personal_os_snapshot(
            assessment_epoch_id="A-1",
            identity_sections=identity,
            audit_responses=audit_values(),
        )
    with pytest.raises(PersonalOSContractError, match="Unsupported Personal OS"):
        build_personal_os_snapshot(
            assessment_epoch_id="A-1",
            identity_sections=identity_values(),
            audit_responses=audit_values(),
            contract_version="GG-PERSONAL-OS-2.0",
        )


def test_non_string_section_key_fails_with_contract_diagnostic():
    identity = identity_values()
    identity[1] = PersonalOSValue("unknown")
    with pytest.raises(PersonalOSContractError, match="keys must all be strings"):
        build_personal_os_snapshot(
            assessment_epoch_id="A-KEY",
            identity_sections=identity,
            audit_responses=audit_values(),
        )


def test_golden_utf8_snapshot_is_deterministic_private_and_allowlisted():
    fixture = json.loads(FIXTURE.read_text())
    first = build_personal_os_snapshot(
        assessment_epoch_id=fixture["assessment_epoch_id"],
        identity_sections=fixture["identity_sections"],
        audit_responses=fixture["audit_responses"],
        contract_version=fixture["contract_version"],
    )
    reverse_identity = OrderedDict(reversed(tuple(fixture["identity_sections"].items())))
    reverse_audit = OrderedDict(reversed(tuple(fixture["audit_responses"].items())))
    second = build_personal_os_snapshot(
        assessment_epoch_id=fixture["assessment_epoch_id"],
        identity_sections=reverse_identity,
        audit_responses=reverse_audit,
    )
    assert first == second
    assert first.content_hash == fixture["expected_hash"]
    assert set(first.payload) == {
        "assessment_epoch_id",
        "audit_responses",
        "contract_version",
        "identity_sections",
        "scope",
    }
    serialized = first.canonical_json
    for forbidden in (
        "user_id",
        "username",
        "email",
        "stable_id",
        "created_at",
        "answers",
        "orientations",
        "archetypes",
        "lever_state",
        "evidence",
        "score",
        "practice_history",
        "context_records",
        "pilot_feedback",
    ):
        assert forbidden not in serialized


def test_ordered_list_order_changes_hash_but_mapping_order_does_not():
    identity = identity_values()
    identity["principles"] = PersonalOSValue("provided", ["First", "Second"])
    first = build_personal_os_snapshot(
        assessment_epoch_id="ASSESSMENT-ORDER",
        identity_sections=identity,
        audit_responses=audit_values(),
    )
    identity["principles"] = PersonalOSValue("provided", ["Second", "First"])
    second = build_personal_os_snapshot(
        assessment_epoch_id="ASSESSMENT-ORDER",
        identity_sections=identity,
        audit_responses=audit_values(),
    )
    assert first.content_hash != second.content_hash


def test_maximum_legal_json_escaped_payload_fits_snapshot_resource_bound():
    scalar = "\x01" * 500
    items = [f"{index}" + "\x01" * 159 for index in range(5)]
    identity = identity_values(mission=scalar)
    identity["twelve_month_direction"] = PersonalOSValue("provided", scalar)
    for section_id in ("principles", "anti_goals", "priority_stack"):
        identity[section_id] = PersonalOSValue("provided", items)
    snapshot = build_personal_os_snapshot(
        assessment_epoch_id="A" * 80,
        identity_sections=identity,
        audit_responses=audit_values(text=scalar),
    )
    assert canonical_personal_os_snapshot_size(snapshot.payload) <= MAX_CANONICAL_SNAPSHOT_BYTES


@pytest.mark.django_db
def test_integrity_conflict_recovers_same_hash_and_rejects_different_hash(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    record = record_personal_os_revision(
        user=user,
        assessment_run=run,
        identity_sections=identity_values(),
        audit_responses=audit_values(),
    ).revision
    original = IntegrityError("synthetic unique race")
    recovered = _winner_after_integrity_conflict(
        user=user,
        assessment_run=run,
        attempted_revision=record.revision,
        content_hash=record.content_hash,
        original_error=original,
    )
    assert recovered.revision == record
    assert recovered.created is False
    with pytest.raises(PersonalOSWriteConflictError, match="concurrent") as conflict:
        _winner_after_integrity_conflict(
            user=user,
            assessment_run=run,
            attempted_revision=record.revision,
            content_hash="0" * 64,
            original_error=original,
        )
    assert conflict.value.retryable is True
    with pytest.raises(IntegrityError, match="synthetic unique race"):
        _winner_after_integrity_conflict(
            user=user,
            assessment_run=run,
            attempted_revision=record.revision + 1,
            content_hash=record.content_hash,
            original_error=original,
        )


@pytest.mark.django_db
def test_revision_write_is_append_only_idempotent_and_latest_only(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    first = record_personal_os_revision(
        user=user,
        assessment_run=run,
        identity_sections=identity_values(mission="Synthetic A"),
        audit_responses=audit_values(),
    )
    repeat = record_personal_os_revision(
        user=user,
        assessment_run=run,
        identity_sections=identity_values(mission="Synthetic A"),
        audit_responses=audit_values(),
    )
    second = record_personal_os_revision(
        user=user,
        assessment_run=run,
        identity_sections=identity_values(mission="Synthetic B"),
        audit_responses=audit_values(),
    )
    third = record_personal_os_revision(
        user=user,
        assessment_run=run,
        identity_sections=identity_values(mission="Synthetic A"),
        audit_responses=audit_values(),
    )
    assert first.created is True
    assert repeat.created is False
    assert repeat.revision.pk == first.revision.pk
    assert [second.revision.revision, third.revision.revision] == [2, 3]
    assert list(
        PersonalOSRevision.objects.filter(assessment_run=run).values_list("revision", flat=True)
    ) == [1, 2, 3]


@pytest.mark.django_db
def test_user_authentication_ownership_and_assessment_epoch_isolation(user, seeded):
    first_run = AssessmentRun.objects.get(user=user)
    second_run = clone_assessment(first_run, "ASSESSMENT-PERSONAL-OS-SECOND")
    other = get_user_model().objects.create_user(username="other-personal-os")
    common = {
        "identity_sections": identity_values(),
        "audit_responses": audit_values(),
    }
    with pytest.raises(PersonalOSServiceError, match="authenticated"):
        record_personal_os_revision(user=AnonymousUser(), assessment_run=first_run, **common)
    with pytest.raises(PersonalOSServiceError, match="must own"):
        record_personal_os_revision(user=other, assessment_run=first_run, **common)
    first = record_personal_os_revision(user=user, assessment_run=first_run, **common)
    assert latest_personal_os_revision(user=user, assessment_run=second_run) is None
    second = record_personal_os_revision(user=user, assessment_run=second_run, **common)
    assert second.revision.revision == 1
    assert first.revision.content_hash != second.revision.content_hash


@pytest.mark.django_db
def test_malformed_input_and_busy_conflict_write_nothing(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    bad = identity_values()
    bad["mission"] = PersonalOSValue("provided", "")
    with pytest.raises(PersonalOSContractError):
        record_personal_os_revision(
            user=user,
            assessment_run=run,
            identity_sections=bad,
            audit_responses=audit_values(),
        )
    assert PersonalOSRevision.objects.count() == 0
    with (
        patch.object(PersonalOSRevision, "save", side_effect=OperationalError("database locked")),
        pytest.raises(PersonalOSWriteConflictError) as exc_info,
    ):
        record_personal_os_revision(
            user=user,
            assessment_run=run,
            identity_sections=identity_values(),
            audit_responses=audit_values(),
        )
    assert exc_info.value.retryable is True
    assert PersonalOSRevision.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_sqlite_concurrent_writers_are_contiguous_or_explicitly_retryable(user, seeded):
    run_id = AssessmentRun.objects.get(user=user).pk
    user_id = user.pk
    barrier = threading.Barrier(2)
    results = []

    def writer(label):
        close_old_connections()
        try:
            thread_user = get_user_model().objects.get(pk=user_id)
            thread_run = AssessmentRun.objects.get(pk=run_id)
            barrier.wait(timeout=10)
            result = record_personal_os_revision(
                user=thread_user,
                assessment_run=thread_run,
                identity_sections=identity_values(mission=f"Synthetic concurrent {label}"),
                audit_responses=audit_values(),
            )
        except PersonalOSWriteConflictError as exc:
            results.append(("conflict", exc.retryable))
        else:
            results.append(("created", result.revision.revision))
        finally:
            close_old_connections()

    threads = [threading.Thread(target=writer, args=(label,)) for label in ("A", "B")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert all(not thread.is_alive() for thread in threads)
    assert len(results) == 2
    assert all(kind == "created" or value is True for kind, value in results)
    revisions = list(
        PersonalOSRevision.objects.order_by("revision").values_list("revision", flat=True)
    )
    assert revisions == list(range(1, len(revisions) + 1))
    assert len(revisions) == len(set(revisions))
