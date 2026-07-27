import json
import uuid
from pathlib import Path

import pytest
from django.test import Client
from django.urls import reverse

from growth.models import AssessmentRun
from growth.services.assessment import (
    decode_share_code,
    encode_share_code,
    load_assessment_assets,
    persist_assessment_run,
)

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data" / "assessment" / "v1.1_bundle" / "grounded_growth_assessment_v1_1"
LEGACY_GGA1_CODE = (
    "GGA1.eyJ2IjoiMS4wIiwiciI6IjU1MzQ0MzQyNDI0NDQ0MzMyMzQzMjQzNTQ0NDQzNDU0"
    "NDQzMjIyMzQ0NDMzMzE0NDM0IiwiZSI6eyJDX0wzNCI6MiwiQ19MMzUiOjMsIkNfTDA1"
    "Ijo0LCJDX0wwOSI6MywiQ19MMTkiOjQsIkNfTDI2IjoyLCJDX0wwOCI6MywiQ19MMTciOj"
    "R9LCJ0Ijo0MC43ODc5OTk5OTk5OTk5OH0="
)


def golden_payload(*, source="application", share_code=None):
    input_data = json.loads((BUNDLE / "pilot_001_responses_v1_compatible.json").read_text())
    result = json.loads((BUNDLE / "pilot_001_rescore_v1_1.json").read_text())
    total_seconds = sum(input_data["timings_seconds"].values())
    if share_code is None:
        share_code = encode_share_code(
            load_assessment_assets().spec,
            input_data["responses"],
            total_seconds=total_seconds,
        )
    return {
        "submission_id": str(uuid.uuid4()),
        "source": source,
        "assessment_version": "1.1",
        "responses": input_data["responses"],
        "timings_seconds": (input_data["timings_seconds"] if source == "application" else {}),
        "total_seconds": total_seconds,
        "result": result,
        "share_code": share_code,
    }


@pytest.mark.django_db
def test_golden_assessment_persists_complete_immutable_outputs(user, seeded):
    payload = golden_payload()
    run, created = persist_assessment_run(user, payload)

    assert created is True
    assert run.source == AssessmentRun.Source.APPLICATION
    assert run.assessment_version == "1.1"
    assert len(run.answers) == 50
    assert len(run.clarifier_answers) == 8
    assert len(run.timing_data["timings_seconds"]) == 58
    assert run.original_share_code.startswith("GGA11.")
    assert run.orientation_results.count() == 6
    assert run.archetype_results.count() == 15
    assert run.lever_baselines.count() == 37

    expected = payload["result"]
    l34 = run.lever_baselines.get(lever_id="L34")
    assert float(l34.raw_self_report) == expected["levers"]["L34"]["raw_self_report"]
    assert float(l34.calibrated_estimate) == expected["levers"]["L34"]["estimate"]
    assert float(l34.evidence_confidence) == expected["levers"]["L34"]["confidence"]
    assert float(l34.need_score) == expected["lever_need_ranking"][0]["score"]
    assert l34.need_rank == 1

    same_run, created_again = persist_assessment_run(user, payload)
    assert created_again is False
    assert same_run.pk == run.pk
    assert AssessmentRun.objects.filter(user=user).count() == 2


@pytest.mark.django_db
def test_assessment_page_uses_canonical_wording_and_exact_scorer(client, user, seeded):
    client.force_login(user)
    page = client.get(reverse("growth:assessment"))
    assert page.status_code == 200
    assert b"Fifty required questions" in page.content
    first_prompt = load_assessment_assets().spec["assessment"]["core_items"][0]["prompt"]
    assert first_prompt.encode() in page.content

    scorer = client.get(reverse("growth:assessment-scorer"))
    assert scorer.status_code == 200
    assert b"GroundedGrowthAssessment" in b"".join(scorer.streaming_content)


@pytest.mark.django_db
def test_assessment_save_endpoint_is_csrf_protected_and_idempotent(user, seeded):
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    payload = golden_payload()
    url = reverse("growth:assessment-save")

    assert (
        client.post(url, data=json.dumps(payload), content_type="application/json").status_code
        == 403
    )

    page = client.get(reverse("growth:assessment"))
    csrf_token = page.cookies["csrftoken"].value
    first = client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert first.status_code == 201
    assert first.json()["created"] is True
    second = client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["run_id"] == first.json()["run_id"]


@pytest.mark.django_db
def test_assessment_rejects_mismatched_share_code_and_result_ids(client, user, seeded):
    client.force_login(user)
    url = reverse("growth:assessment-save")

    mismatched_code = golden_payload()
    changed_responses = dict(mismatched_code["responses"])
    changed_responses["Q01"] = 1
    mismatched_code["share_code"] = encode_share_code(
        load_assessment_assets().spec,
        changed_responses,
    )
    response = client.post(
        url,
        data=json.dumps(mismatched_code),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "do not match" in response.json()["error"]

    missing_lever = golden_payload()
    del missing_lever["result"]["levers"]["L37"]
    response = client.post(
        url,
        data=json.dumps(missing_lever),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "All 37 lever outputs" in response.json()["error"]


def test_supported_gga1_and_gga11_share_codes_decode():
    assets = load_assessment_assets()
    legacy = decode_share_code(assets.spec, LEGACY_GGA1_CODE)
    assert legacy["prefix"] == "GGA1"
    assert len(legacy["responses"]) == 58
    assert legacy["responses"]["Q01"] == 5
    assert legacy["responses"]["C_L34"] == 2

    payload = golden_payload()
    current = decode_share_code(assets.spec, payload["share_code"])
    assert current["prefix"] == "GGA11"
    assert current["responses"] == payload["responses"]


@pytest.mark.django_db
def test_valid_nullable_lever_outputs_can_be_persisted(user, seeded):
    payload = golden_payload()
    payload["result"]["levers"]["L37"]["raw_self_report"] = None
    payload["result"]["levers"]["L37"]["estimate"] = None
    payload["result"]["levers"]["L37"]["confidence"] = 0
    payload["result"]["levers"]["L37"]["alpha"] = 0.35
    payload["result"]["levers"]["L37"]["beta"] = 0.35
    payload["result"]["levers"]["L37"].pop("evidence_mass", None)
    for ranked in payload["result"]["lever_need_ranking"]:
        if ranked["lever_id"] == "L37":
            ranked["score"] = None
            break

    run, created = persist_assessment_run(user, payload)
    baseline = run.lever_baselines.get(lever_id="L37")
    assert created is True
    assert baseline.raw_self_report is None
    assert baseline.calibrated_estimate is None
    assert baseline.need_score is None
