from __future__ import annotations

import base64
import binascii
import json
import math
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import transaction

from growth.models import (
    ArchetypeResult,
    AssessmentRun,
    CurriculumVersion,
    Lever,
    LeverBaseline,
    OrientationResult,
)

ASSESSMENT_BUNDLE_DIR = (
    Path("data") / "assessment" / "v1.1_bundle" / "grounded_growth_assessment_v1_1"
)
ASSESSMENT_SPEC_PATH = ASSESSMENT_BUNDLE_DIR / "assessment_spec_v1_1.json"
ASSESSMENT_MODEL_PATH = ASSESSMENT_BUNDLE_DIR / "grounded_growth_model_v1.json"
ASSESSMENT_SCORER_PATH = ASSESSMENT_BUNDLE_DIR / "assessment_scoring_v1_1.js"
SHARE_CODE_PATTERN = re.compile(r"^GGA(11|1)\.([A-Za-z0-9+/=]+)$")


class AssessmentPayloadError(ValueError):
    pass


@dataclass(frozen=True)
class AssessmentAssets:
    spec: dict[str, Any]
    model: dict[str, Any]


@dataclass(frozen=True)
class ValidatedAssessment:
    submission_id: uuid.UUID
    source: str
    responses: dict[str, int | str]
    core_answers: dict[str, int | str]
    clarifier_answers: dict[str, int | str]
    timings_seconds: dict[str, float]
    total_seconds: float | None
    result: dict[str, Any]
    share_code: str


@lru_cache(maxsize=1)
def load_assessment_assets() -> AssessmentAssets:
    spec = json.loads((settings.BASE_DIR / ASSESSMENT_SPEC_PATH).read_text())
    model = json.loads((settings.BASE_DIR / ASSESSMENT_MODEL_PATH).read_text())
    return AssessmentAssets(spec=spec, model=model)


def assessment_scorer_path() -> Path:
    return settings.BASE_DIR / ASSESSMENT_SCORER_PATH


def _finite_number(
    value: Any,
    label: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    nullable: bool = False,
) -> float | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise AssessmentPayloadError(f"{label} must be a finite number.")
    number = float(value)
    if not math.isfinite(number):
        raise AssessmentPayloadError(f"{label} must be a finite number.")
    if minimum is not None and number < minimum:
        raise AssessmentPayloadError(f"{label} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise AssessmentPayloadError(f"{label} must be at most {maximum}.")
    return number


def _item_map(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    assessment = spec["assessment"]
    items = (
        assessment["core_items"]
        + assessment["adaptive_capability_clarifiers"]
        + assessment["adaptive_orientation_clarifiers"]
    )
    return {item["id"]: item for item in items}


def _normalize_answer(item: dict[str, Any], value: Any) -> int | str:
    if value == "NA":
        if not item.get("allow_not_applicable"):
            raise AssessmentPayloadError(f"{item['id']} does not allow N/A.")
        return "NA"
    if isinstance(value, bool) or not isinstance(value, int) or value not in range(1, 6):
        raise AssessmentPayloadError(f"{item['id']} must be an integer from 1 to 5.")
    return value


def _normalize_responses(
    spec: dict[str, Any], responses: Any, *, require_complete_core: bool
) -> dict[str, int | str]:
    if not isinstance(responses, dict):
        raise AssessmentPayloadError("responses must be an object.")
    items = _item_map(spec)
    unknown = sorted(set(responses) - set(items))
    if unknown:
        raise AssessmentPayloadError(f"Unknown assessment item IDs: {unknown}.")
    normalized = {
        item_id: _normalize_answer(items[item_id], value) for item_id, value in responses.items()
    }
    if require_complete_core:
        core_ids = {item["id"] for item in spec["assessment"]["core_items"]}
        missing = sorted(core_ids - set(normalized))
        if missing:
            raise AssessmentPayloadError(f"All 50 core questions are required; missing {missing}.")
    return normalized


def decode_share_code(spec: dict[str, Any], code: str) -> dict[str, Any]:
    normalized_code = code.strip()
    match = SHARE_CODE_PATTERN.fullmatch(normalized_code)
    if match is None:
        raise AssessmentPayloadError("Share code must begin with GGA11. or supported GGA1.")
    try:
        decoded = base64.b64decode(match.group(2), validate=True).decode("utf-8")
        payload = json.loads(decoded)
    except (UnicodeDecodeError, binascii.Error, json.JSONDecodeError) as exc:
        raise AssessmentPayloadError("Share code payload is malformed.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("r"), str):
        raise AssessmentPayloadError("Share code payload is missing its core response string.")

    core_items = spec["assessment"]["core_items"]
    if len(payload["r"]) > len(core_items):
        raise AssessmentPayloadError("Share code contains too many core responses.")
    responses: dict[str, Any] = {}
    for index, character in enumerate(payload["r"]):
        if character == "0":
            continue
        if character == "N":
            responses[core_items[index]["id"]] = "NA"
        elif character in {"1", "2", "3", "4", "5"}:
            responses[core_items[index]["id"]] = int(character)
        else:
            raise AssessmentPayloadError("Share code contains an invalid response value.")

    extras = payload.get("e") or {}
    if not isinstance(extras, dict):
        raise AssessmentPayloadError("Share code clarifier responses must be an object.")
    responses.update(extras)
    normalized_responses = _normalize_responses(spec, responses, require_complete_core=False)
    total_seconds = payload.get("t")
    if total_seconds is not None:
        total_seconds = _finite_number(
            total_seconds,
            "share-code total time",
            minimum=0,
            maximum=604800,
        )
    return {
        "prefix": f"GGA{match.group(1)}",
        "version": payload.get("v"),
        "responses": normalized_responses,
        "total_seconds": total_seconds,
    }


def encode_share_code(
    spec: dict[str, Any],
    responses: dict[str, int | str],
    *,
    total_seconds: float | None = None,
) -> str:
    normalized = _normalize_responses(spec, responses, require_complete_core=False)
    core_ids = [item["id"] for item in spec["assessment"]["core_items"]]
    core = "".join(
        "N" if normalized.get(item_id) == "NA" else str(normalized.get(item_id, 0))
        for item_id in core_ids
    )
    extras = {key: value for key, value in normalized.items() if key not in core_ids}
    payload = {
        "v": spec["assessment"]["version"],
        "r": core,
        "e": extras,
        "t": total_seconds,
    }
    encoded = base64.b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    ).decode()
    return f"GGA11.{encoded}"


def _validate_result(
    result: Any,
    assets: AssessmentAssets,
) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise AssessmentPayloadError("result must be an object.")
    if result.get("assessment_version") != assets.spec["assessment"]["version"]:
        raise AssessmentPayloadError("Assessment result version is not 1.1.")

    quality = result.get("response_quality")
    if not isinstance(quality, dict) or not isinstance(quality.get("flags", []), list):
        raise AssessmentPayloadError("Response-quality output is incomplete.")
    _finite_number(quality.get("modifier"), "response-quality modifier", minimum=0, maximum=1)
    _finite_number(
        quality.get("total_timed_seconds"),
        "response-quality timed duration",
        minimum=0,
        maximum=604800,
    )
    _finite_number(
        quality.get("median_seconds_per_item"),
        "response-quality median timing",
        minimum=0,
        maximum=604800,
        nullable=True,
    )

    orientation_scores = (result.get("orientations") or {}).get("scores")
    expected_orientation_slugs = {
        orientation["slug"] for orientation in assets.model["orientation_modes"]
    }
    if not isinstance(orientation_scores, dict) or set(orientation_scores) != (
        expected_orientation_slugs
    ):
        raise AssessmentPayloadError("All six orientation outputs are required.")
    for slug, orientation in orientation_scores.items():
        if not isinstance(orientation, dict):
            raise AssessmentPayloadError(f"Orientation {slug} output is malformed.")
        _finite_number(orientation.get("score"), f"{slug} score", minimum=0, maximum=1)
        _finite_number(
            orientation.get("confidence"),
            f"{slug} confidence",
            minimum=0,
            maximum=1,
        )

    archetypes = result.get("archetypes")
    expected_archetype_ids = {item["id"] for item in assets.model["archetypes"]}
    if not isinstance(archetypes, list) or len(archetypes) != len(expected_archetype_ids):
        raise AssessmentPayloadError("All 15 archetype outputs are required.")
    actual_archetype_ids = {item.get("id") for item in archetypes if isinstance(item, dict)}
    if actual_archetype_ids != expected_archetype_ids:
        raise AssessmentPayloadError("Archetype output IDs do not match the canonical model.")
    for archetype in archetypes:
        _finite_number(
            archetype.get("raw_fit"),
            f"{archetype['id']} fit",
            minimum=0,
            maximum=1,
        )
        _finite_number(
            archetype.get("fit_confidence"),
            f"{archetype['id']} fit confidence",
            minimum=0,
            maximum=1,
            nullable=True,
        )

    levers = result.get("levers")
    expected_lever_ids = {item["id"] for item in assets.model["developmental_levers"]}
    if not isinstance(levers, dict) or set(levers) != expected_lever_ids:
        raise AssessmentPayloadError("All 37 lever outputs are required.")
    for lever_id, lever in levers.items():
        if not isinstance(lever, dict):
            raise AssessmentPayloadError(f"Lever {lever_id} output is malformed.")
        raw = _finite_number(
            lever.get("raw_self_report"),
            f"{lever_id} raw_self_report",
            minimum=0,
            maximum=1,
            nullable=True,
        )
        estimate = _finite_number(
            lever.get("estimate"),
            f"{lever_id} estimate",
            minimum=0,
            maximum=1,
            nullable=True,
        )
        _finite_number(
            lever.get("confidence"),
            f"{lever_id} confidence",
            minimum=0,
            maximum=1,
        )
        alpha = _finite_number(
            lever.get("alpha"),
            f"{lever_id} alpha",
            minimum=0,
        )
        beta = _finite_number(
            lever.get("beta"),
            f"{lever_id} beta",
            minimum=0,
        )
        prior_alpha = float(assets.spec["assessment"]["scoring_constants"]["prior_alpha"])
        prior_beta = float(assets.spec["assessment"]["scoring_constants"]["prior_beta"])
        if estimate is None:
            if (
                raw is not None
                or abs(alpha - prior_alpha) > 0.000001
                or abs(beta - prior_beta) > 0.000001
            ):
                raise AssessmentPayloadError(
                    f"{lever_id} unassessed output must retain only the canonical prior."
                )
        else:
            if raw is None or alpha + beta <= 0:
                raise AssessmentPayloadError(
                    f"{lever_id} assessed output requires raw score and positive mass."
                )
            evidence_mass = _finite_number(
                lever.get("evidence_mass"),
                f"{lever_id} evidence mass",
                minimum=0,
                maximum=float(
                    assets.spec["assessment"]["scoring_constants"]["quiz_mass_cap_per_lever"]
                ),
            )
            expected_alpha = prior_alpha + evidence_mass * raw
            expected_beta = prior_beta + evidence_mass * (1 - raw)
            if (
                abs(alpha - expected_alpha) > 0.00025
                or abs(beta - expected_beta) > 0.00025
                or abs(alpha / (alpha + beta) - estimate) > 0.0002
            ):
                raise AssessmentPayloadError(
                    f"{lever_id} baseline masses do not match the canonical assessment output."
                )

    ranking = result.get("lever_need_ranking")
    if not isinstance(ranking, list) or len(ranking) != len(expected_lever_ids):
        raise AssessmentPayloadError("Lever need ranking must contain all 37 levers.")
    ranking_ids = [item.get("lever_id") for item in ranking if isinstance(item, dict)]
    if len(ranking_ids) != len(ranking) or set(ranking_ids) != expected_lever_ids:
        raise AssessmentPayloadError("Lever need ranking IDs do not match the canonical model.")
    for item in ranking:
        _finite_number(
            item.get("score"),
            f"{item['lever_id']} need score",
            minimum=0,
            maximum=1,
            nullable=True,
        )
    return result


def validate_assessment_payload(payload: Any) -> ValidatedAssessment:
    if not isinstance(payload, dict):
        raise AssessmentPayloadError("Request body must be a JSON object.")
    assets = load_assessment_assets()
    try:
        submission_id = uuid.UUID(str(payload.get("submission_id")))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AssessmentPayloadError("submission_id must be a UUID.") from exc

    source = payload.get("source")
    allowed_sources = {
        AssessmentRun.Source.APPLICATION,
        AssessmentRun.Source.SHARE_CODE,
    }
    if source not in allowed_sources:
        raise AssessmentPayloadError("source must be application or share_code.")
    if payload.get("assessment_version") != assets.spec["assessment"]["version"]:
        raise AssessmentPayloadError("assessment_version must be 1.1.")

    responses = _normalize_responses(
        assets.spec,
        payload.get("responses"),
        require_complete_core=True,
    )
    core_ids = {item["id"] for item in assets.spec["assessment"]["core_items"]}
    core_answers = {key: value for key, value in responses.items() if key in core_ids}
    clarifier_answers = {key: value for key, value in responses.items() if key not in core_ids}
    capability_clarifier_ids = {
        item["id"] for item in assets.spec["assessment"]["adaptive_capability_clarifiers"]
    }
    orientation_clarifier_ids = {
        item["id"] for item in assets.spec["assessment"]["adaptive_orientation_clarifiers"]
    }
    if len(set(clarifier_answers) & capability_clarifier_ids) > 8:
        raise AssessmentPayloadError("At most eight capability clarifiers may be submitted.")
    if len(set(clarifier_answers) & orientation_clarifier_ids) > 2:
        raise AssessmentPayloadError("At most two orientation clarifiers may be submitted.")

    timings = payload.get("timings_seconds") or {}
    if not isinstance(timings, dict):
        raise AssessmentPayloadError("timings_seconds must be an object.")
    unknown_timing_ids = sorted(set(timings) - set(responses))
    if unknown_timing_ids:
        raise AssessmentPayloadError(f"Timing contains unanswered IDs: {unknown_timing_ids}.")
    normalized_timings = {
        item_id: _finite_number(
            value,
            f"{item_id} timing",
            minimum=0,
            maximum=604800,
        )
        for item_id, value in timings.items()
    }
    if source == AssessmentRun.Source.APPLICATION and not set(responses).issubset(
        normalized_timings
    ):
        raise AssessmentPayloadError(
            "Completed in-app assessments require timing for every answered item."
        )

    total_seconds = payload.get("total_seconds")
    if total_seconds is not None:
        total_seconds = _finite_number(
            total_seconds,
            "total_seconds",
            minimum=0,
            maximum=604800,
        )

    share_code = str(payload.get("share_code", "")).strip()
    decoded = decode_share_code(assets.spec, share_code)
    if decoded["responses"] != responses:
        raise AssessmentPayloadError("Share code responses do not match the submitted answers.")
    if (
        decoded["total_seconds"] is not None
        and total_seconds is not None
        and abs(decoded["total_seconds"] - total_seconds) > 0.01
    ):
        raise AssessmentPayloadError("Share code timing does not match the submitted duration.")
    if source == AssessmentRun.Source.APPLICATION and decoded["prefix"] != "GGA11":
        raise AssessmentPayloadError("In-app assessment runs must generate a GGA11 share code.")

    result = _validate_result(payload.get("result"), assets)
    if source == AssessmentRun.Source.APPLICATION:
        calculated_total = sum(normalized_timings.values())
        if total_seconds is None or abs(calculated_total - total_seconds) > 0.01:
            raise AssessmentPayloadError("In-app total duration must match item timings.")
        quality_total = float(result["response_quality"]["total_timed_seconds"])
        if abs(quality_total - total_seconds) > 0.01:
            raise AssessmentPayloadError("Response-quality duration must match item timings.")
    return ValidatedAssessment(
        submission_id=submission_id,
        source=source,
        responses=responses,
        core_answers=core_answers,
        clarifier_answers=clarifier_answers,
        timings_seconds=normalized_timings,
        total_seconds=total_seconds,
        result=result,
        share_code=share_code,
    )


def _decimal(value: float | int | None) -> Decimal | None:
    return None if value is None else Decimal(str(value))


@transaction.atomic
def persist_assessment_run(user, payload: Any) -> tuple[AssessmentRun, bool]:
    validated = validate_assessment_payload(payload)
    stable_id = f"ASSESSMENT-{user.pk}-{validated.submission_id}"
    existing = AssessmentRun.objects.filter(stable_id=stable_id).first()
    if existing is not None:
        if existing.user_id != user.pk:
            raise AssessmentPayloadError("Assessment submission belongs to another user.")
        return existing, False

    assets = load_assessment_assets()
    version = CurriculumVersion.objects.filter(active=True).order_by("-imported_at").first()
    if version is None:
        raise AssessmentPayloadError("Canonical curriculum must be seeded before assessment.")

    result = validated.result
    lever_outputs = result["levers"]
    run = AssessmentRun.objects.create(
        stable_id=stable_id,
        user=user,
        curriculum_version=version,
        assessment_version=assets.spec["assessment"]["version"],
        source=validated.source,
        answers=validated.core_answers,
        clarifier_answers=validated.clarifier_answers,
        timing_data={
            "timings_seconds": validated.timings_seconds,
            "total_seconds": validated.total_seconds,
            "timing_method": result["response_quality"].get("timing_method"),
        },
        response_quality_result=result["response_quality"],
        orientation_outputs=result["orientations"],
        archetype_outputs=result["archetypes"],
        raw_lever_scores={
            lever_id: output["raw_self_report"] for lever_id, output in lever_outputs.items()
        },
        calibrated_lever_estimates={
            lever_id: output["estimate"] for lever_id, output in lever_outputs.items()
        },
        lever_confidence={
            lever_id: output["confidence"] for lever_id, output in lever_outputs.items()
        },
        original_share_code=validated.share_code,
    )

    orientation_metadata = {item["slug"]: item for item in assets.model["orientation_modes"]}
    for slug, output in result["orientations"]["scores"].items():
        metadata = orientation_metadata[slug]
        OrientationResult.objects.create(
            assessment_run=run,
            stable_id=metadata["id"],
            slug=slug,
            name=metadata["name"],
            score=_decimal(output["score"]),
            confidence=_decimal(output["confidence"]),
        )

    archetype_metadata = {item["id"]: item for item in assets.model["archetypes"]}
    for rank, output in enumerate(result["archetypes"], start=1):
        metadata = archetype_metadata[output["id"]]
        ArchetypeResult.objects.create(
            assessment_run=run,
            stable_id=metadata["id"],
            name=metadata["name"],
            orientation_slugs=metadata["orientations"],
            fit_index=_decimal(output["raw_fit"]),
            fit_confidence=_decimal(output.get("fit_confidence")),
            rank=rank,
        )

    ranking = {
        item["lever_id"]: (rank, item["score"])
        for rank, item in enumerate(result["lever_need_ranking"], start=1)
    }
    lever_rows = Lever.objects.in_bulk(lever_outputs)
    if set(lever_rows) != set(lever_outputs):
        raise AssessmentPayloadError("Seeded lever IDs do not match assessment outputs.")
    for lever_id, output in lever_outputs.items():
        rank, need_score = ranking[lever_id]
        LeverBaseline.objects.create(
            user=user,
            assessment_run=run,
            lever=lever_rows[lever_id],
            raw_self_report=_decimal(output["raw_self_report"]),
            calibrated_estimate=_decimal(output["estimate"]),
            evidence_confidence=_decimal(output["confidence"]),
            baseline_alpha=_decimal(output["alpha"]),
            baseline_beta=_decimal(output["beta"]),
            baseline_mass_source=LeverBaseline.BaselineMassSource.CANONICAL_RESULT,
            need_score=_decimal(need_score),
            need_rank=rank,
            notes="Assessment v1.1 provisional self-report baseline.",
        )
    return run, True
