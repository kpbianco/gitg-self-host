from __future__ import annotations

import json
import traceback
from io import StringIO

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import override_settings

from growth.domain.context import ContextFactorValue, build_assessment_context_snapshot
from growth.models import (
    AssessmentContext,
    AssessmentRun,
    PersonalOSRevision,
    PracticeContext,
    PracticeProtocol,
)
from growth.services.context import PracticeContextInput, record_context_bundle
from growth.services.context_priority import build_context_priority_for_epoch
from growth.services.m6c_pilot_readiness import (
    AUTHENTICATION_MIDDLEWARE,
    M6C_PILOT_READINESS_CONTRACT_VERSION,
    M6CPilotReadinessError,
    verify_m6c_pilot_readiness,
)
from growth.services.personal_os import record_personal_os_revision
from scripts.verify_http_login import validate_path
from tests.test_context_services import assessment_factors, practice_factors
from tests.test_personal_os_services import audit_values, identity_values

PRIVATE_SENTINEL = "PRIVATE-M6C04-SENTINEL-DO-NOT-PRINT"


def _database_state():
    return {
        model._meta.label: list(model.objects.order_by(model._meta.pk.name).values())
        for model in (
            AssessmentRun,
            PracticeProtocol,
            AssessmentContext,
            PracticeContext,
            PersonalOSRevision,
        )
    }


def _record_valid_optional_state(user, seeded):
    run = AssessmentRun.objects.get(user=user)
    protocol = PracticeProtocol.objects.get(stable_id="PRACTICE-FRIENDSHIP-01")
    personal = record_personal_os_revision(
        user=user,
        assessment_run=run,
        identity_sections=identity_values(mission="Synthetic M6C-04 direction."),
        audit_responses=audit_values(text="Synthetic M6C-04 descriptive response."),
    )
    context = record_context_bundle(
        user=user,
        assessment_run=run,
        assessment_factors=assessment_factors(capacity=3),
        practice_inputs=(PracticeContextInput(protocol=protocol, factors=practice_factors()),),
    )
    priority = build_context_priority_for_epoch(
        user=user,
        assessment_run=run,
        protocol_stable_ids=(protocol.stable_id,),
    )
    return personal, context, priority


@pytest.mark.django_db
def test_readiness_is_deterministic_read_only_and_accepts_empty_optional_state(seeded):
    before = _database_state()

    first = verify_m6c_pilot_readiness()
    second = verify_m6c_pilot_readiness()

    assert first == second
    assert _database_state() == before
    assert first.contract_version == M6C_PILOT_READINESS_CONTRACT_VERSION
    assert first.prerequisite_contract_versions == (
        "GG-PILOT-READINESS-1.0",
        "GG-CURRICULUM-EXPANSION-READINESS-1.0",
        "GG-COMPETENCY-EVIDENCE-READINESS-1.0",
        "GG-CONTEXT-READINESS-1.0",
        "GG-PERSONAL-OS-READINESS-1.0",
        "GG-CONTEXT-PRIORITY-READINESS-1.0",
    )
    assert first.identity_section_ids == (
        "mission",
        "principles",
        "anti_goals",
        "twelve_month_direction",
        "priority_stack",
    )
    assert first.audit_prompt_ids == (
        "current_truth",
        "autopilot_pattern",
        "misalignment_or_fragmentation",
        "deliberate_next_step",
    )
    assert first.assessment_factor_ids == ("season", "capacity")
    assert first.practice_factor_ids == (
        "applicability",
        "importance",
        "readiness",
        "urgency",
        "opportunity_resources",
        "burden",
    )
    assert len(first.baseline_protocol_ids) == 5
    assert first.active_protocols == 383
    assert len(first.score_active_protocol_ids) == 383
    assert set(first.score_active_protocol_ids) == set(
        PracticeProtocol.objects.values_list("stable_id", flat=True)
    )
    assert first.authenticated_route_names == (
        "growth:personal-os",
        "growth:practice-context",
    )
    assert first.personal_os_records == 0
    assert first.assessment_context_records == 0
    assert first.practice_context_records == 0
    assert first.software_ready is True
    assert first.release_or_deployment_approved is False


@pytest.mark.django_db
def test_readiness_accepts_valid_optional_state_and_reports_only_counts_and_hashes(user, seeded):
    personal, context, priority = _record_valid_optional_state(user, seeded)

    summary = verify_m6c_pilot_readiness()

    assert summary.personal_os_records == 1
    assert summary.assessment_context_records == 1
    assert summary.practice_context_records == 1
    assert personal.revision.content_hash not in json.dumps(summary.as_dict())
    assert context.assessment_context.content_hash not in json.dumps(summary.as_dict())
    assert context.practice_contexts[0].content_hash not in json.dumps(summary.as_dict())
    assert priority.content_hash not in json.dumps(summary.as_dict())


@pytest.mark.django_db
def test_management_command_json_is_deterministic_and_private_safe(user, seeded):
    _record_valid_optional_state(user, seeded)
    first = StringIO()
    second = StringIO()

    call_command("verify_m6c_pilot_readiness", json=True, stdout=first)
    call_command("verify_m6c_pilot_readiness", json=True, stdout=second)

    assert first.getvalue() == second.getvalue()
    payload = json.loads(first.getvalue())
    assert payload["contract_version"] == M6C_PILOT_READINESS_CONTRACT_VERSION
    assert payload["personal_os_records"] == 1
    for forbidden in (
        "canonical_snapshot",
        "username",
        "record_id",
        "assessment_epoch_id",
        PRIVATE_SENTINEL.lower(),
    ):
        assert forbidden not in first.getvalue().lower()


@pytest.mark.django_db
def test_private_optional_state_tamper_fails_without_repeating_values(user, seeded):
    personal, _, _ = _record_valid_optional_state(user, seeded)
    corrupted = dict(personal.revision.canonical_snapshot)
    corrupted["private_extra"] = PRIVATE_SENTINEL
    with connection.cursor() as cursor:
        cursor.execute(
            'UPDATE "personal_os_revision" SET canonical_snapshot = %s WHERE stable_id = %s',
            [json.dumps(corrupted), personal.revision.pk.hex],
        )

    with pytest.raises(M6CPilotReadinessError) as service_exc:
        verify_m6c_pilot_readiness()
    assert str(service_exc.value) == (
        "Personal OS prerequisite readiness failed private-safe verification."
    )
    service_traceback = "".join(traceback.format_exception(service_exc.value))
    assert PRIVATE_SENTINEL not in service_traceback
    assert personal.revision.content_hash not in service_traceback

    with pytest.raises(CommandError) as command_exc:
        call_command("verify_m6c_pilot_readiness")
    command_traceback = "".join(traceback.format_exception(command_exc.value))
    assert PRIVATE_SENTINEL not in command_traceback
    assert personal.revision.content_hash not in command_traceback


@pytest.mark.django_db
def test_readiness_fails_closed_on_baseline_protocol_or_activation_drift(seeded):
    PracticeProtocol.objects.filter(stable_id="PRACTICE-PRESENCE-01").update(
        availability=PracticeProtocol.Availability.INACTIVE
    )
    with pytest.raises(M6CPilotReadinessError):
        verify_m6c_pilot_readiness()

    PracticeProtocol.objects.filter(stable_id="PRACTICE-PRESENCE-01").update(
        availability=PracticeProtocol.Availability.ACTIVE,
        score_active=False,
    )
    with pytest.raises(M6CPilotReadinessError):
        verify_m6c_pilot_readiness()


@pytest.mark.django_db
def test_readiness_fails_if_browser_routes_are_not_globally_authenticated(seeded):
    middleware = tuple(item for item in settings.MIDDLEWARE if item != AUTHENTICATION_MIDDLEWARE)
    with (
        override_settings(MIDDLEWARE=middleware),
        pytest.raises(
            M6CPilotReadinessError,
            match="authentication middleware is not configured",
        ),
    ):
        verify_m6c_pilot_readiness()


@pytest.mark.django_db
def test_readiness_rejects_malformed_context_without_printing_private_state(user, seeded):
    _, context, _ = _record_valid_optional_state(user, seeded)
    record = context.practice_contexts[0]
    corrupted = dict(record.canonical_snapshot)
    corrupted["private_extra"] = PRIVATE_SENTINEL
    with connection.cursor() as cursor:
        cursor.execute(
            'UPDATE "growth_practicecontext" SET canonical_snapshot = %s WHERE stable_id = %s',
            [json.dumps(corrupted), record.pk.hex],
        )

    with pytest.raises(M6CPilotReadinessError) as service_exc:
        verify_m6c_pilot_readiness()
    service_traceback = "".join(traceback.format_exception(service_exc.value))
    assert "private-safe verification" in service_traceback
    assert PRIVATE_SENTINEL not in service_traceback

    with pytest.raises(CommandError) as command_exc:
        call_command("verify_m6c_pilot_readiness")
    command_traceback = "".join(traceback.format_exception(command_exc.value))
    assert PRIVATE_SENTINEL not in command_traceback


def test_context_factor_value_boolean_remains_malformed_input():
    with pytest.raises(ValueError, match="must be an integer"):
        build_assessment_context_snapshot(
            assessment_epoch_id="SYNTHETIC-M6C04-EPOCH",
            factors={
                "season": ContextFactorValue("unknown"),
                "capacity": ContextFactorValue("provided", True),
            },
        )


@pytest.mark.parametrize(
    "path",
    (
        "https://example.invalid/personal-os/",
        "//example.invalid/personal-os/",
        "/personal-os/?private=value",
        "/personal-os/#private",
        "/personal-os/../private/",
        "/personal-os/%2e%2e/private/",
    ),
)
def test_http_probe_rejects_nonlocal_or_ambiguous_authenticated_paths(path):
    with pytest.raises(RuntimeError, match="Authenticated path"):
        validate_path(path)


def test_http_probe_accepts_the_registered_personal_os_path():
    assert validate_path("/personal-os/") == "/personal-os/"
