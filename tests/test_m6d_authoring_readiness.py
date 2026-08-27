import json
from copy import deepcopy
from dataclasses import replace

import pytest
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from growth.domain.practice_content import load_practice_content_bundle
from growth.services.m6d_authoring_readiness import (
    M6D_REPORT_PATH,
    M6DAuthoringReadinessError,
    verify_m6d_authoring_readiness,
)


def _persisted_counts():
    return {model._meta.label_lower: model._default_manager.count() for model in apps.get_models()}


@pytest.mark.django_db
def test_m6d_authoring_readiness_is_exact_additive_and_read_only(seeded):
    before = _persisted_counts()

    summary = verify_m6d_authoring_readiness()

    assert _persisted_counts() == before
    assert summary.contract_version == "GG-M6D-01-AUTHORING-READINESS-1.0"
    assert summary.preserved_expansion_contract_version == ("GG-CURRICULUM-EXPANSION-READINESS-1.0")
    assert summary.preserved_competency_evidence_contract_version == (
        "GG-COMPETENCY-EVIDENCE-READINESS-1.0"
    )
    assert summary.cohort_competency_ids == ("08.06", "09.12", "10.02", "13.02")
    assert summary.cohort_protocol_ids == (
        "PRACTICE-MOTIVATION-INDEPENDENT-START-01",
        "PRACTICE-DECISION-RECORD-01",
        "PRACTICE-DELIBERATE-PRACTICE-01",
        "PRACTICE-HOME-UPKEEP-SYSTEM-01",
    )
    assert summary.cohort_action_count == 14
    catalog = load_practice_content_bundle(settings.BASE_DIR)
    assert summary.competencies == 383
    assert summary.source_protocol_packages == len(catalog.protocols)
    assert summary.source_practice_actions == sum(
        len(protocol["intervention"]["actions"]) for protocol in catalog.protocols
    )
    assert summary.source_protocol_packages == 383
    assert summary.source_practice_actions == 1151
    assert summary.uncovered_competencies == 0
    assert summary.runtime_protocols == 383
    assert summary.runtime_actions == 1151
    assert summary.source_typed_protocols == 378
    assert summary.typed_production_protocols == 4
    assert summary.score_active_protocols == 383
    assert summary.expert_review_id == "ER-M6A-003"
    assert summary.expert_review_status
    assert summary.research_gap_id == "RG-M6A-002"
    assert summary.research_gap_status
    assert summary.database_writes == 0
    assert len(summary.practice_catalog_content_hash) == 64
    assert len(summary.cohort_report_sha256) == 64
    assert len(summary.fixture_sha256) == 64


@pytest.mark.django_db
def test_m6d_authoring_readiness_executes_no_database_writes(seeded):
    with CaptureQueriesContext(connection) as queries:
        summary = verify_m6d_authoring_readiness()

    write_statements = {
        query["sql"].lstrip().partition(" ")[0].upper()
        for query in queries.captured_queries
        if query["sql"].strip()
    } & {"ALTER", "CREATE", "DELETE", "DROP", "INSERT", "REPLACE", "UPDATE"}

    assert write_statements == set()
    assert summary.database_writes == 0


@pytest.mark.django_db
def test_m6d_authoring_readiness_rejects_incomplete_catalog_frontier(seeded, monkeypatch):
    from growth.services import m6d_authoring_readiness as readiness

    expansion = readiness.verify_expansion_readiness()
    competency = readiness.verify_competency_evidence_readiness()
    monkeypatch.setattr(
        readiness,
        "verify_expansion_readiness",
        lambda: replace(
            expansion,
            canonical_protocol_packages=10,
            practice_actions=30,
            uncovered_competencies=373,
        ),
    )
    monkeypatch.setattr(
        readiness,
        "verify_competency_evidence_readiness",
        lambda: competency,
    )

    with pytest.raises(M6DAuthoringReadinessError, match="M6F source protocol packages"):
        readiness.verify_m6d_authoring_readiness()


@pytest.mark.django_db
def test_m6d_authoring_readiness_rejects_missing_typed_cohort_member(seeded, monkeypatch):
    from growth.services import m6d_authoring_readiness as readiness

    catalog = deepcopy(load_practice_content_bundle(settings.BASE_DIR))
    cohort_member = next(
        protocol
        for protocol in catalog.protocols
        if protocol["stable_id"] == "PRACTICE-DECISION-RECORD-01"
    )
    cohort_member["evidence_and_scoring"]["observation_contract_version"] = (
        "practice-observation-v1"
    )
    monkeypatch.setattr(readiness, "load_practice_content_bundle", lambda _base_dir: catalog)

    with pytest.raises(
        M6DAuthoringReadinessError,
        match="typed protocol IDs are missing",
    ):
        readiness.verify_m6d_authoring_readiness()


def test_m6d_cohort_safety_privacy_boundaries_are_permanent():
    from growth.services import m6d_authoring_readiness as readiness

    catalog = deepcopy(load_practice_content_bundle(settings.BASE_DIR))
    protocol = next(
        item for item in catalog.protocols if item["stable_id"] == "PRACTICE-HOME-UPKEEP-SYSTEM-01"
    )

    def remove_term(value):
        if isinstance(value, str):
            return value.replace("mold", "excluded hazard").replace("Mold", "Excluded hazard")
        if isinstance(value, list):
            return [remove_term(item) for item in value]
        if isinstance(value, dict):
            return {key: remove_term(item) for key, item in value.items()}
        return value

    protocol.update(remove_term(protocol))

    with pytest.raises(M6DAuthoringReadinessError, match="boundary terms are missing: mold"):
        readiness._verify_cohort(catalog)


@pytest.mark.django_db
def test_m6d_authoring_readiness_command_emits_deterministic_json(seeded, capsys):
    call_command("verify_m6d_authoring_readiness", "--json")
    output = capsys.readouterr().out

    payload = json.loads(output)
    assert output.rstrip("\n") == json.dumps(payload, sort_keys=True)
    assert payload["contract_version"] == "GG-M6D-01-AUTHORING-READINESS-1.0"
    assert payload["source_protocol_packages"] == 383
    assert payload["runtime_protocols"] == 383
    assert payload["typed_production_protocols"] == 4
    assert payload["database_writes"] == 0


@pytest.mark.django_db
def test_m6d_authoring_readiness_reports_stale_report_diagnostic(
    seeded,
    monkeypatch,
):
    from growth.services import m6d_authoring_readiness as readiness

    original = readiness.build_competency_evidence_report_outputs

    def tampered_outputs(base_dir):
        outputs = original(base_dir)
        outputs[M6D_REPORT_PATH] = b"{}\n"
        return outputs

    monkeypatch.setattr(
        readiness,
        "build_competency_evidence_report_outputs",
        tampered_outputs,
    )

    catalog_hash = load_practice_content_bundle(settings.BASE_DIR).content_hash
    with pytest.raises(M6DAuthoringReadinessError, match="cohort report is missing or stale"):
        readiness._verify_report(settings.BASE_DIR, catalog_hash)


@pytest.mark.django_db
def test_m6d_authoring_readiness_reports_fixture_tamper_diagnostic(
    seeded,
    monkeypatch,
):
    from growth.services import m6d_authoring_readiness as readiness

    original = readiness._read_json_object

    def tampered_fixture(path, *, label):
        payload, raw = original(path, label=label)
        if label == "M6D-01 synthetic fixture":
            payload["cases"][1]["input"]["action_stable_id"] = payload["cases"][0]["input"][
                "action_stable_id"
            ]
        return payload, raw

    monkeypatch.setattr(readiness, "_read_json_object", tampered_fixture)

    with pytest.raises(M6DAuthoringReadinessError, match="duplicate action_stable_id"):
        readiness._verify_fixture(settings.BASE_DIR)
