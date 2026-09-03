from __future__ import annotations

import json
import stat
import uuid
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, models
from django.db.migrations.executor import MigrationExecutor
from django.test import Client
from django.urls import reverse

from growth.domain.assessment_calibration import (
    ASSESSMENT_CALIBRATION_CONSENT_VERSION,
    ASSESSMENT_CALIBRATION_EXPORT_VERSION,
    build_calibration_consent_snapshot,
)
from growth.models import AssessmentCalibrationConsent, AssessmentRun
from growth.services.assessment import persist_assessment_run
from growth.services.assessment_calibration import (
    AssessmentCalibrationError,
    build_assessment_calibration_export,
    record_assessment_calibration_consent,
    verify_assessment_calibration_collection_readiness,
)
from growth.services.data_lifecycle import (
    build_deletion_preview,
    build_owner_archive,
    delete_owner_account,
)
from tests.test_assessment_integration import golden_payload


def _participant_run(user, *, source="application"):
    run, created = persist_assessment_run(user, golden_payload(source=source))
    assert created is True
    return run


@pytest.mark.django_db
def test_completed_assessment_is_never_enrolled_without_explicit_consent(user, seeded):
    run = _participant_run(user)
    demonstration = AssessmentRun.objects.get(user=user, source=AssessmentRun.Source.PILOT_SEED)

    exported = build_assessment_calibration_export()

    assert run.calibration_consents.count() == 0
    assert exported["participant_count"] == 0
    assert exported["assessment_run_count"] == 0
    assert exported["participant_evidence_axes_completed"] == 0
    with pytest.raises(AssessmentCalibrationError, match="demonstration"):
        record_assessment_calibration_consent(
            user=user,
            assessment_run=demonstration,
            state=AssessmentCalibrationConsent.State.CONSENTED,
        )


@pytest.mark.django_db
def test_consent_withdrawal_and_reconsent_are_append_only_and_idempotent(user, seeded):
    run = _participant_run(user)

    first = record_assessment_calibration_consent(
        user=user,
        assessment_run=run,
        state=AssessmentCalibrationConsent.State.CONSENTED,
    )
    retry = record_assessment_calibration_consent(
        user=user,
        assessment_run=run,
        state=AssessmentCalibrationConsent.State.CONSENTED,
    )
    withdrawn = record_assessment_calibration_consent(
        user=user,
        assessment_run=run,
        state=AssessmentCalibrationConsent.State.WITHDRAWN,
    )
    reconsented = record_assessment_calibration_consent(
        user=user,
        assessment_run=run,
        state=AssessmentCalibrationConsent.State.CONSENTED,
    )

    assert first.created is True
    assert retry.created is False
    assert retry.consent.pk == first.consent.pk
    assert [withdrawn.consent.revision, reconsented.consent.revision] == [2, 3]
    assert {
        first.consent.participant_token,
        withdrawn.consent.participant_token,
        reconsented.consent.participant_token,
    } == {first.consent.participant_token}
    assert build_assessment_calibration_export()["assessment_run_count"] == 1

    with pytest.raises(ValidationError, match="immutable"):
        reconsented.consent.save()
    with pytest.raises(ValidationError, match="immutable"):
        AssessmentCalibrationConsent.objects.filter(pk=first.consent.pk).update(
            state=AssessmentCalibrationConsent.State.WITHDRAWN
        )
    with pytest.raises(ValidationError, match="immutable"):
        first.consent.delete()


@pytest.mark.django_db
def test_export_is_deterministic_pseudonymous_allowlisted_and_linkable(user, seeded):
    first_run = _participant_run(user)
    second_run = _participant_run(user, source="share_code")
    for run in (first_run, second_run):
        record_assessment_calibration_consent(
            user=user,
            assessment_run=run,
            state=AssessmentCalibrationConsent.State.CONSENTED,
        )

    first = build_assessment_calibration_export()
    assert first == build_assessment_calibration_export()
    assert set(first) == {
        "assessment_run_count",
        "collection",
        "consent_contract_version",
        "dataset_sha256",
        "disclosure_version",
        "export_fields",
        "participant_count",
        "participant_evidence_axes_completed",
        "participants",
        "privacy",
        "schema_version",
        "validation_status",
    }
    assert first["schema_version"] == ASSESSMENT_CALIBRATION_EXPORT_VERSION
    assert first["consent_contract_version"] == ASSESSMENT_CALIBRATION_CONSENT_VERSION
    assert first["participant_count"] == 1
    assert first["assessment_run_count"] == 2
    participant = first["participants"][0]
    assert set(participant) == {"participant_ref", "runs"}
    assert participant["participant_ref"].startswith("participant-")
    assert [run["run_sequence"] for run in participant["runs"]] == [1, 2]
    assert [run["source"] for run in participant["runs"]] == ["application", "share_code"]
    for exported_run in participant["runs"]:
        assert set(exported_run) == {
            "assessment_version",
            "clarifier_responses",
            "consent_contract_version",
            "core_responses",
            "days_since_first_included_run",
            "response_quality",
            "run_sequence",
            "source",
            "timings_seconds",
            "total_seconds",
        }
        assert set(exported_run["response_quality"]) == {
            "flags",
            "median_seconds_per_item",
            "modifier",
            "timing_method",
            "total_timed_seconds",
        }
        assert len(exported_run["core_responses"]) == 50
        assert len(exported_run["clarifier_responses"]) == 8
    assert len(participant["runs"][0]["timings_seconds"]) == 58
    assert participant["runs"][1]["timings_seconds"] == {}

    serialized = json.dumps(first, sort_keys=True)
    for forbidden in (
        user.username,
        str(first_run.pk),
        str(second_run.pk),
        first_run.original_share_code,
        "orientation_outputs",
        "archetype_outputs",
        "raw_lever_scores",
        "calibrated_lever_estimates",
    ):
        assert forbidden not in serialized
    assert first["privacy"]["contains_item_responses"] is True
    assert first["privacy"]["contains_identity"] is False
    assert first["privacy"]["contains_share_codes"] is False
    assert first["validation_status"] == "data_collection_required"


@pytest.mark.django_db
def test_withdrawal_excludes_only_future_exports_and_other_users_are_isolated(user, seeded):
    run = _participant_run(user)
    record_assessment_calibration_consent(
        user=user,
        assessment_run=run,
        state=AssessmentCalibrationConsent.State.CONSENTED,
    )
    other = get_user_model().objects.create_user(
        username="other-calibration-owner", password="other-local-password-47!"
    )

    with pytest.raises(AssessmentCalibrationError, match="another user"):
        record_assessment_calibration_consent(
            user=other,
            assessment_run=run,
            state=AssessmentCalibrationConsent.State.CONSENTED,
        )
    assert build_assessment_calibration_export(users=[other])["assessment_run_count"] == 0

    record_assessment_calibration_consent(
        user=user,
        assessment_run=run,
        state=AssessmentCalibrationConsent.State.WITHDRAWN,
    )
    assert build_assessment_calibration_export(users=[user])["assessment_run_count"] == 0
    assert run.answers


@pytest.mark.django_db
def test_export_fails_closed_on_consent_or_assessment_tampering(user, seeded):
    run = _participant_run(user)
    consent = record_assessment_calibration_consent(
        user=user,
        assessment_run=run,
        state=AssessmentCalibrationConsent.State.CONSENTED,
    ).consent
    models.QuerySet.update(
        AssessmentCalibrationConsent.objects.filter(pk=consent.pk), content_hash="0" * 64
    )

    with pytest.raises(AssessmentCalibrationError, match="deterministic verification"):
        build_assessment_calibration_export()


@pytest.mark.parametrize("tamper", ["revision", "participant_token", "assessment"])
@pytest.mark.django_db
def test_export_fails_closed_on_structural_consent_and_assessment_drift(tamper, user, seeded):
    first_run = _participant_run(user)
    first = record_assessment_calibration_consent(
        user=user,
        assessment_run=first_run,
        state=AssessmentCalibrationConsent.State.CONSENTED,
    ).consent

    if tamper == "revision":
        snapshot = build_calibration_consent_snapshot(
            assessment_epoch_id=str(first_run.pk),
            assessment_version=first_run.assessment_version,
            participant_token=str(first.participant_token),
            revision=2,
            state=first.state,
        )
        models.QuerySet.update(
            AssessmentCalibrationConsent.objects.filter(pk=first.pk),
            revision=2,
            canonical_snapshot=snapshot.payload,
            content_hash=snapshot.content_hash,
        )
        expected = "not contiguous"
    elif tamper == "participant_token":
        second_run = _participant_run(user)
        second = record_assessment_calibration_consent(
            user=user,
            assessment_run=second_run,
            state=AssessmentCalibrationConsent.State.CONSENTED,
        ).consent
        changed_token = uuid.uuid4()
        snapshot = build_calibration_consent_snapshot(
            assessment_epoch_id=str(second_run.pk),
            assessment_version=second_run.assessment_version,
            participant_token=str(changed_token),
            revision=second.revision,
            state=second.state,
        )
        models.QuerySet.update(
            AssessmentCalibrationConsent.objects.filter(pk=second.pk),
            participant_token=changed_token,
            canonical_snapshot=snapshot.payload,
            content_hash=snapshot.content_hash,
        )
        expected = "inconsistent calibration pseudonyms"
    else:
        changed_answers = dict(first_run.answers)
        changed_answers.pop("Q01")
        models.QuerySet.update(
            type(first_run).objects.filter(pk=first_run.pk), answers=changed_answers
        )
        expected = "incomplete core responses"

    with pytest.raises(AssessmentCalibrationError, match=expected):
        build_assessment_calibration_export()


@pytest.mark.django_db
def test_data_management_requires_both_consent_acknowledgements(client, user, seeded):
    run = _participant_run(user)
    client.force_login(user)
    url = reverse("growth:data-management")

    incomplete = client.post(
        url,
        {
            "action": "grant_calibration_consent",
            "assessment_run": run.pk,
            "acknowledge_sensitive_data": "on",
        },
    )
    assert incomplete.status_code == 200
    assert b"This field is required" in incomplete.content
    assert AssessmentCalibrationConsent.objects.count() == 0

    response = client.post(
        url,
        {
            "action": "grant_calibration_consent",
            "assessment_run": run.pk,
            "acknowledge_sensitive_data": "on",
            "authorize_manual_export": "on",
        },
    )
    assert response.status_code == 302
    assert AssessmentCalibrationConsent.objects.get().state == "consented"

    page = client.get(url)
    assert b"Included completed assessments</dt><dd>1" in page.content
    assert b"Participant evidence axes completed</dt><dd>0 of 8" in page.content
    assert b"uploaded automatically" in page.content


@pytest.mark.django_db
def test_calibration_consent_post_is_csrf_protected(user, seeded):
    run = _participant_run(user)
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)

    response = client.post(
        reverse("growth:data-management"),
        {
            "action": "grant_calibration_consent",
            "assessment_run": run.pk,
            "acknowledge_sensitive_data": "on",
            "authorize_manual_export": "on",
        },
    )

    assert response.status_code == 403
    assert AssessmentCalibrationConsent.objects.count() == 0


@pytest.mark.django_db
def test_owner_preview_is_private_user_scoped_and_withdrawal_is_immediate(client, user, seeded):
    run = _participant_run(user)
    record_assessment_calibration_consent(
        user=user,
        assessment_run=run,
        state=AssessmentCalibrationConsent.State.CONSENTED,
    )
    client.force_login(user)
    url = reverse("growth:assessment-calibration-preview")

    response = client.get(url)
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]
    assert "private" in response["Cache-Control"]
    assert response["X-Content-Type-Options"] == "nosniff"
    assert json.loads(response.content)["assessment_run_count"] == 1

    client.post(
        reverse("growth:data-management"),
        {"action": "withdraw_calibration_consent", "assessment_run": run.pk},
    )
    assert json.loads(client.get(url).content)["assessment_run_count"] == 0


@pytest.mark.django_db
def test_consent_is_in_owner_archive_and_account_deletion_scope(user, seeded):
    run = _participant_run(user)
    consent = record_assessment_calibration_consent(
        user=user,
        assessment_run=run,
        state=AssessmentCalibrationConsent.State.CONSENTED,
    ).consent

    archive = build_owner_archive(user)
    archived = archive["records"]["assessment_calibration_consents"]
    assert len(archived) == 1
    assert archived[0]["participant_token"] == consent.participant_token
    assert archived[0]["assessment_ref"].startswith("assessment-")
    preview = build_deletion_preview(user)
    assert preview.record_counts["assessment_calibration_consents"] == 1

    deleted = delete_owner_account(user=user, expected_preview_hash=preview.content_hash)
    assert deleted == preview.total_records
    assert not get_user_model().objects.filter(pk=user.pk).exists()
    assert not AssessmentCalibrationConsent.objects.filter(pk=consent.pk).exists()


@pytest.mark.django_db
def test_operator_export_requires_confirmation_refuses_overwrite_and_uses_0600(
    tmp_path, user, seeded
):
    run = _participant_run(user)
    record_assessment_calibration_consent(
        user=user,
        assessment_run=run,
        state=AssessmentCalibrationConsent.State.CONSENTED,
    )
    output = tmp_path / "calibration.json"

    with pytest.raises(CommandError, match="confirm-sensitive-export"):
        call_command("export_assessment_calibration_dataset", output=output)
    stdout = StringIO()
    call_command(
        "export_assessment_calibration_dataset",
        output=output,
        confirm_sensitive_export=True,
        stdout=stdout,
    )
    assert json.loads(output.read_text())["assessment_run_count"] == 1
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert "sensitive" in stdout.getvalue().lower()
    with pytest.raises(CommandError, match="overwrite"):
        call_command(
            "export_assessment_calibration_dataset",
            output=output,
            confirm_sensitive_export=True,
        )


@pytest.mark.django_db
def test_readiness_is_privacy_safe_and_keeps_all_empirical_axes_open(user, seeded):
    run = _participant_run(user)
    record_assessment_calibration_consent(
        user=user,
        assessment_run=run,
        state=AssessmentCalibrationConsent.State.CONSENTED,
    )

    summary = verify_assessment_calibration_collection_readiness()
    output = StringIO()
    call_command("verify_assessment_calibration_collection", json=True, stdout=output)
    command_payload = json.loads(output.getvalue())

    assert summary.software_ready is True
    assert summary.active_participants == 1
    assert summary.active_assessment_runs == 1
    assert summary.participant_evidence_axes_completed == 0
    assert summary.requires_qualified_analysis is True
    assert set(command_payload).isdisjoint({"participant_token", "answers", "timing_data"})


@pytest.mark.django_db(transaction=True)
def test_calibration_consent_migration_round_trip_preserves_existing_assessments(user, seeded):
    run_count = user.assessment_runs.count()
    executor = MigrationExecutor(connection)
    original_leaves = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate([("growth", "0012_composite_closeout_scoring")])
        old_apps = executor.loader.project_state(
            [("growth", "0012_composite_closeout_scoring")]
        ).apps
        assert old_apps.get_model("growth", "AssessmentRun").objects.count() == run_count

        executor = MigrationExecutor(connection)
        executor.migrate([("growth", "0013_assessmentcalibrationconsent")])
        new_apps = executor.loader.project_state(
            [("growth", "0013_assessmentcalibrationconsent")]
        ).apps
        assert new_apps.get_model("growth", "AssessmentCalibrationConsent").objects.count() == 0

        executor = MigrationExecutor(connection)
        executor.migrate([("growth", "0012_composite_closeout_scoring")])
        assert old_apps.get_model("growth", "AssessmentRun").objects.count() == run_count
    finally:
        MigrationExecutor(connection).migrate(original_leaves)
