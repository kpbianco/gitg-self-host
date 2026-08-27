from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from growth.domain.evidence import (
    ALLOWED_OBSERVATION_FIELDS,
    EvidenceContractError,
    validate_evidence_rules,
)
from growth.domain.practice_content import (
    PracticeContentBundle,
    PracticeContentError,
    load_practice_content_bundle,
)
from growth.domain.scoring import (
    ScoringContractError,
    reconstruct_published_baseline_mass,
)
from growth.domain.typed_evidence import (
    TYPED_EVIDENCE_RULES_VERSION,
    TypedEvidenceContractError,
    load_typed_evidence_spec,
    materialize_typed_evidence_rules,
)
from growth.models import (
    ArchetypeResult,
    AssessmentRun,
    Competency,
    CompetencyLeverLink,
    CurriculumVersion,
    Lever,
    LeverBaseline,
    OrientationResult,
    PracticeAction,
    PracticeProtocol,
)

CURRICULUM_PATH = Path("data/curriculum/ideal_person_curriculum_v2_pluralist_full_scope.yaml")
MODEL_PATH = Path("data/model/grounded_growth_model_v1.json")
MAPPING_PATH = Path("data/model/competency_lever_mapping_v1.csv")
PILOT_BASELINES_PATH = Path("data/notion/initial_mvp/01_lever_baselines_import.csv")
PILOT_ORIENTATIONS_PATH = Path("data/notion/initial_mvp/03_orientation_profile_import.csv")

WEIGHT_TOLERANCE = Decimal("0.000001")


class CanonicalDataError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalBundle:
    curriculum: dict
    model: dict
    mapping_rows: list[dict[str, str]]
    source_hash: str


@dataclass(frozen=True)
class ImportSummary:
    curriculum_versions: int
    levers: int
    competencies: int
    competency_lever_links: int
    practice_protocols: int
    pilot_assessment_runs: int
    pilot_lever_baselines: int


def _path(relative: Path) -> Path:
    return settings.BASE_DIR / relative


def _read_csv(relative: Path) -> list[dict[str, str]]:
    with _path(relative).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _source_hash(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for relative in paths:
        digest.update(str(relative).encode())
        digest.update(b"\0")
        digest.update(_path(relative).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _mapping_weights(row: dict[str, str]) -> dict[str, Decimal]:
    weights: dict[str, Decimal] = {}
    competency_id = row.get("competency_id", "").strip()
    for slot in range(1, 6):
        lever_id = row.get(f"lever_{slot}_id", "").strip()
        raw_weight = row.get(f"lever_{slot}_weight", "").strip()
        if bool(lever_id) != bool(raw_weight):
            raise CanonicalDataError(
                f"{competency_id}: lever slot {slot} must contain both ID and weight."
            )
        if not lever_id:
            continue
        try:
            weight = Decimal(raw_weight)
        except InvalidOperation as exc:
            raise CanonicalDataError(
                f"{competency_id}: lever {lever_id} has invalid weight {raw_weight!r}."
            ) from exc
        if weight <= 0 or weight > 1:
            raise CanonicalDataError(
                f"{competency_id}: lever {lever_id} weight {weight} is outside (0, 1]."
            )
        if lever_id in weights:
            raise CanonicalDataError(f"{competency_id}: lever {lever_id} appears more than once.")
        weights[lever_id] = weight
    return weights


def _require_unique_ids(label: str, ids: list[str]) -> None:
    blanks = [index + 1 for index, value in enumerate(ids) if not value]
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in ids:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if blanks or duplicates:
        raise CanonicalDataError(
            f"{label}: blank ID rows={blanks}; duplicate IDs={sorted(duplicates)}"
        )


def load_and_validate_bundle() -> CanonicalBundle:
    curriculum = yaml.safe_load(_path(CURRICULUM_PATH).read_text())["curriculum"]
    model = json.loads(_path(MODEL_PATH).read_text())
    mapping_rows = _read_csv(MAPPING_PATH)

    domains = curriculum.get("domains", [])
    competency_rows = [
        (domain, competency) for domain in domains for competency in domain.get("competencies", [])
    ]
    domain_ids = [str(domain.get("id", "")).strip() for domain in domains]
    competency_ids = [str(competency.get("id", "")).strip() for _, competency in competency_rows]
    family_ids = [str(family.get("id", "")).strip() for family in model.get("lever_families", [])]
    lever_ids = [
        str(lever.get("id", "")).strip() for lever in model.get("developmental_levers", [])
    ]
    orientation_ids = [
        str(orientation.get("id", "")).strip() for orientation in model.get("orientation_modes", [])
    ]
    archetype_ids = [
        str(archetype.get("id", "")).strip() for archetype in model.get("archetypes", [])
    ]
    mapping_ids = [row.get("competency_id", "").strip() for row in mapping_rows]

    _require_unique_ids("Curriculum domains", domain_ids)
    _require_unique_ids("Curriculum competencies", competency_ids)
    _require_unique_ids("Lever families", family_ids)
    _require_unique_ids("Developmental levers", lever_ids)
    _require_unique_ids("Orientation modes", orientation_ids)
    _require_unique_ids("Archetypes", archetype_ids)
    _require_unique_ids("Competency mappings", mapping_ids)

    declared_counts = curriculum.get("counts", {})
    if declared_counts.get("domain_count") != len(domains):
        raise CanonicalDataError("Curriculum domain count does not match its declared count.")
    if declared_counts.get("master_competency_count") != len(competency_rows):
        raise CanonicalDataError("Curriculum competency count does not match its declared count.")
    for domain in domains:
        if domain.get("competency_count") != len(domain.get("competencies", [])):
            raise CanonicalDataError(f"Domain {domain.get('id')} competency count is inconsistent.")

    competency_set = set(competency_ids)
    mapping_set = set(mapping_ids)
    if competency_set != mapping_set:
        raise CanonicalDataError(
            "Competency mapping coverage mismatch: "
            f"missing={sorted(competency_set - mapping_set)}, "
            f"extra={sorted(mapping_set - competency_set)}"
        )

    lever_set = set(lever_ids)
    json_links = model.get("competency_lever_links", [])
    json_link_ids = [str(link.get("competency_id", "")).strip() for link in json_links]
    _require_unique_ids("Model competency links", json_link_ids)
    if set(json_link_ids) != competency_set:
        raise CanonicalDataError("Model JSON competency links do not match the curriculum.")
    json_links_by_id = {link["competency_id"]: link for link in json_links}

    for row in mapping_rows:
        competency_id = row["competency_id"].strip()
        weights = _mapping_weights(row)
        invalid_levers = sorted(set(weights) - lever_set)
        if invalid_levers:
            raise CanonicalDataError(f"{competency_id}: unknown lever IDs {invalid_levers}.")
        total = sum(weights.values(), Decimal("0"))
        if abs(total - Decimal("1")) > WEIGHT_TOLERANCE:
            raise CanonicalDataError(
                f"{competency_id}: lever weights sum to {total}, expected approximately 1.0."
            )
        json_weights = {
            lever_id: Decimal(str(weight))
            for lever_id, weight in json_links_by_id[competency_id]["lever_weights"].items()
        }
        if weights != json_weights:
            raise CanonicalDataError(
                f"{competency_id}: mapping CSV and model JSON weights disagree."
            )

    return CanonicalBundle(
        curriculum=curriculum,
        model=model,
        mapping_rows=mapping_rows,
        source_hash=_source_hash((CURRICULUM_PATH, MODEL_PATH, MAPPING_PATH)),
    )


def _competency_defaults(domain: dict, competency: dict, version: CurriculumVersion) -> dict:
    classification = competency.get("classification", {})
    measurement = competency.get("measurement", {})
    return {
        "curriculum_version": version,
        "domain_id": str(domain["id"]),
        "domain_name": domain["name"],
        "name": competency["name"],
        "scope": competency["scope"],
        "evidence_of_progress": competency["evidence_of_progress"],
        "applicability": classification.get(
            "applicability", domain.get("default_applicability", "")
        ),
        "normative_status": classification.get(
            "normative_status", domain.get("normative_status", "")
        ),
        "formation_modes": classification.get("formation_modes", domain.get("formation_modes", [])),
        "preferred_evidence_types": measurement.get(
            "preferred_evidence_types", domain.get("preferred_evidence_types", [])
        ),
        "professional_boundary": competency.get(
            "professional_boundary", domain.get("professional_boundary") or ""
        ),
    }


def validate_practice_content_mapping(
    practice_bundle: PracticeContentBundle,
    canonical_bundle: CanonicalBundle,
) -> None:
    competencies = {
        competency["id"]: (str(domain["id"]), competency)
        for domain in canonical_bundle.curriculum["domains"]
        for competency in domain["competencies"]
    }
    mapping_by_id = {
        row["competency_id"].strip(): _mapping_weights(row) for row in canonical_bundle.mapping_rows
    }
    protocol_ids = {protocol["stable_id"] for protocol in practice_bundle.protocols}
    competency_ids = set(competencies)
    for source_id, source in practice_bundle.sources.items():
        unknown_competencies = sorted(set(source["applicable_competency_ids"]) - competency_ids)
        unknown_protocols = sorted(set(source["applicable_protocol_ids"]) - protocol_ids)
        if unknown_competencies or unknown_protocols:
            raise CanonicalDataError(
                f"{source_id}: source applicability references unknown canonical "
                f"competencies={unknown_competencies}, protocols={unknown_protocols}."
            )
    for protocol in practice_bundle.protocols:
        stable_id = protocol["stable_id"]
        parent_id = protocol["parent_competency_id"]
        if parent_id not in competencies:
            raise CanonicalDataError(f"{stable_id}: unknown parent competency {parent_id}.")
        domain_id, _ = competencies[parent_id]
        if protocol["domain_id"] != domain_id:
            raise CanonicalDataError(
                f"{stable_id}: domain {protocol['domain_id']} does not match "
                f"parent competency domain {domain_id}."
            )
        weights = mapping_by_id[parent_id]
        target_ids = set(protocol["evidence_and_scoring"]["recommendation_target_lever_ids"])
        if not target_ids.issubset(weights):
            raise CanonicalDataError(
                f"{stable_id}: recommendation targets {sorted(target_ids)} must be a "
                f"subset of {parent_id}'s canonical structured mapping."
            )
        weight_sum = sum(weights.values(), Decimal("0"))
        if abs(weight_sum - Decimal("1")) > WEIGHT_TOLERANCE:
            raise CanonicalDataError(
                f"{stable_id}: parent mapping weights sum to {weight_sum}, "
                "expected approximately 1.0."
            )


def _seed_protocols(protocols: tuple[dict, ...]) -> None:
    for item in protocols:
        completion_rules = item.get("completion_rules", {})
        minimum_completed = completion_rules.get("minimum_completed", 2)
        substantive_markers = completion_rules.get("substantive_markers", [])
        marker_mode = completion_rules.get("marker_mode", "any")
        if completion_rules and (
            not isinstance(minimum_completed, int)
            or minimum_completed < 1
            or minimum_completed > len(item.get("actions", []))
        ):
            raise CanonicalDataError(
                f"{item['stable_id']}: completion minimum is invalid for its actions."
            )
        typed_protocol = any(
            action.get("evidence_rules", {}).get("schema_version") == TYPED_EVIDENCE_RULES_VERSION
            for action in item.get("actions", [])
        )
        if completion_rules and (
            not isinstance(substantive_markers, list)
            or not substantive_markers
            or (not typed_protocol and set(substantive_markers) - ALLOWED_OBSERVATION_FIELDS)
            or marker_mode not in {"any", "all"}
        ):
            raise CanonicalDataError(
                f"{item['stable_id']}: completion markers must use the reviewed "
                "evidence observation vocabulary and a supported marker mode."
            )
        parent_competency = None
        parent_competency_id = item.get("parent_competency_id")
        if parent_competency_id:
            parent_competency = (
                Competency.objects.filter(stable_id=parent_competency_id)
                .prefetch_related("lever_links")
                .first()
            )
            if parent_competency is None:
                raise CanonicalDataError(
                    f"{item['stable_id']}: unknown parent competency {parent_competency_id}."
                )
            links = tuple(parent_competency.lever_links.all())
            linked_lever_ids = {link.lever_id for link in links}
            target_lever_ids = set(item["target_levers"])
            if not target_lever_ids or not target_lever_ids.issubset(linked_lever_ids):
                raise CanonicalDataError(
                    f"{item['stable_id']}: recommendation targets must be a non-empty "
                    f"subset of {parent_competency_id}'s canonical structured mapping."
                )
            weight_sum = sum((link.weight for link in links), Decimal("0"))
            if abs(weight_sum - Decimal("1")) > Decimal("0.0001"):
                raise CanonicalDataError(
                    f"{item['stable_id']}: task-to-lever weights sum to {weight_sum}; "
                    "expected approximately 1.0."
                )
        defaults = {
            "slug": item["slug"],
            "name": item["name"],
            "parent_competency": parent_competency,
            "availability": item.get("availability", PracticeProtocol.Availability.INACTIVE),
            "duration_days": item.get("duration_days", 0),
            "recommendation_reason": item.get("recommendation_reason", ""),
            "applicability_prompt": item.get("applicability_prompt", ""),
            "setup_prompt": item.get("setup_prompt", ""),
            "privacy_and_boundaries": item.get("privacy_and_boundaries", ""),
            "completion_criteria": item.get("completion_criteria", []),
            "completion_rules": item.get("completion_rules", {}),
            "setup_copy": item.get("setup_copy", {}),
            "check_in_fields": item.get("check_in_fields", []),
            "score_active": item.get("score_active", False),
            "mastery_disclaimer": item["mastery_disclaimer"],
            "display_order": item["display_order"],
        }
        protocol, _ = PracticeProtocol.objects.update_or_create(
            stable_id=item["stable_id"], defaults=defaults
        )
        protocol.target_levers.set(Lever.objects.filter(stable_id__in=item["target_levers"]))
        desired_actions: set[str] = set()
        for action in item.get("actions", []):
            try:
                if action["evidence_rules"].get("schema_version") == TYPED_EVIDENCE_RULES_VERSION:
                    materialize_typed_evidence_rules(
                        action["evidence_rules"], load_typed_evidence_spec()
                    )
                else:
                    validate_evidence_rules(action["evidence_rules"])
            except (KeyError, EvidenceContractError, TypedEvidenceContractError) as exc:
                raise CanonicalDataError(
                    f"{action['stable_id']}: invalid evidence rules: {exc}"
                ) from exc
            desired_actions.add(action["stable_id"])
            PracticeAction.objects.update_or_create(
                stable_id=action["stable_id"],
                defaults={
                    "protocol": protocol,
                    "sequence": action["sequence"],
                    "title": action["title"],
                    "instructions": action["instructions"],
                    "due_within_days": action["due_within_days"],
                    "evidence_rules": action["evidence_rules"],
                },
            )
        protocol.actions.exclude(stable_id__in=desired_actions).delete()


def _seed_pilot(version: CurriculumVersion, model: dict) -> tuple[int, int]:
    user = get_user_model().objects.order_by("date_joined", "pk").first()
    if user is None:
        return 0, 0

    baseline_rows = _read_csv(PILOT_BASELINES_PATH)
    orientation_rows = _read_csv(PILOT_ORIENTATIONS_PATH)
    raw_scores = {row["Lever ID"]: float(row["Raw Self-Report"]) for row in baseline_rows}
    estimates = {row["Lever ID"]: float(row["Baseline Mastery"]) for row in baseline_rows}
    confidence = {row["Lever ID"]: float(row["Evidence Confidence"]) for row in baseline_rows}

    orientation_by_slug = {item["slug"]: item for item in model.get("orientation_modes", [])}
    archetype_by_id = {item["id"]: item for item in model.get("archetypes", [])}
    pilot_archetypes = (
        ("A05", "The Seeker", Decimal("0.78"), 1),
        ("A03", "The Systems Steward", Decimal("0.69"), 2),
        ("A04", "The Explorer", Decimal("0.69"), 3),
    )
    orientation_outputs = {
        row["Internal Slug"]: {
            "score": float(row["Preference Expression"]),
            "confidence": float(row["Confidence"]),
        }
        for row in orientation_rows
    }
    archetype_outputs = [
        {
            "stable_id": archetype_id,
            "name": published_name,
            "fit_index": float(fit_index),
            "rank": rank,
        }
        for archetype_id, published_name, fit_index, rank in pilot_archetypes
    ]

    stable_id = f"PILOT-002-USER-{user.pk}"
    run, created = AssessmentRun.objects.get_or_create(
        stable_id=stable_id,
        defaults={
            "user": user,
            "curriculum_version": version,
            "assessment_version": "1.1",
            "source": AssessmentRun.Source.PILOT_SEED,
            "answers": {},
            "clarifier_answers": {},
            "timing_data": {
                "total_timed_seconds": 344,
                "median_seconds_per_item": 4.7,
            },
            "response_quality_result": {"modifier": 0.96},
            "orientation_outputs": orientation_outputs,
            "archetype_outputs": archetype_outputs,
            "raw_lever_scores": raw_scores,
            "calibrated_lever_estimates": estimates,
            "lever_confidence": confidence,
            "original_share_code": "",
        },
    )
    if not created and run.user_id != user.pk:
        raise CanonicalDataError(f"{stable_id} belongs to an unexpected user.")

    for row in orientation_rows:
        slug = row["Internal Slug"]
        metadata = orientation_by_slug[slug]
        OrientationResult.objects.update_or_create(
            assessment_run=run,
            stable_id=metadata["id"],
            defaults={
                "slug": slug,
                "name": row["Orientation"],
                "score": Decimal(row["Preference Expression"]),
                "confidence": Decimal(row["Confidence"]),
            },
        )

    for archetype_id, published_name, fit_index, rank in pilot_archetypes:
        metadata = archetype_by_id[archetype_id]
        ArchetypeResult.objects.update_or_create(
            assessment_run=run,
            stable_id=archetype_id,
            defaults={
                "name": published_name,
                "orientation_slugs": metadata["orientations"],
                "fit_index": fit_index,
                "fit_confidence": None,
                "rank": rank,
            },
        )

    for row in baseline_rows:
        try:
            mass = reconstruct_published_baseline_mass(
                lever_id=row["Lever ID"],
                raw_self_report=Decimal(row["Raw Self-Report"]),
                calibrated_estimate=Decimal(row["Baseline Mastery"]),
                evidence_confidence=Decimal(row["Evidence Confidence"]),
            )
        except ScoringContractError as exc:
            raise CanonicalDataError(f"Pilot 002 {row['Lever ID']}: {exc}") from exc
        LeverBaseline.objects.update_or_create(
            assessment_run=run,
            lever_id=row["Lever ID"],
            defaults={
                "user": user,
                "raw_self_report": Decimal(row["Raw Self-Report"]),
                "calibrated_estimate": Decimal(row["Baseline Mastery"]),
                "evidence_confidence": Decimal(row["Evidence Confidence"]),
                "baseline_alpha": mass.alpha if mass is not None else None,
                "baseline_beta": mass.beta if mass is not None else None,
                "baseline_mass_source": (
                    LeverBaseline.BaselineMassSource.PUBLISHED_RECONSTRUCTION
                    if mass is not None
                    else ""
                ),
                "need_score": Decimal(row["Need Score"]),
                "need_rank": int(row["Need Rank"]),
                "notes": row["Notes"],
            },
        )

    return 1, len(baseline_rows)


@transaction.atomic
def seed_canonical_data() -> ImportSummary:
    bundle = load_and_validate_bundle()
    try:
        practice_bundle = load_practice_content_bundle(settings.BASE_DIR)
    except PracticeContentError as exc:
        raise CanonicalDataError(f"Canonical practice content validation failed: {exc}") from exc
    validate_practice_content_mapping(practice_bundle, bundle)
    curriculum = bundle.curriculum
    model = bundle.model
    model_metadata = model["model"]
    version_id = f"CURRICULUM-{curriculum['version']}-MODEL-{model_metadata['version']}"
    version, _ = CurriculumVersion.objects.update_or_create(
        stable_id=version_id,
        defaults={
            "curriculum_version": curriculum["version"],
            "model_version": model_metadata["version"],
            "assessment_version": "1.1",
            "source_hash": bundle.source_hash,
            "active": True,
        },
    )

    family_by_slug = {family["slug"]: family for family in model.get("lever_families", [])}
    for lever in model["developmental_levers"]:
        family = family_by_slug[lever["family"]]
        Lever.objects.update_or_create(
            stable_id=lever["id"],
            defaults={
                "curriculum_version": version,
                "slug": lever["slug"],
                "name": lever["name"],
                "family_id": family["id"],
                "family_slug": family["slug"],
                "family_name": family["name"],
                "definition": lever["definition"],
                "orientation_composition": lever["orientation_composition"],
                "competency_count": lever["coverage"]["competency_count"],
                "total_competency_weight": Decimal(str(lever["coverage"]["total_weight"])),
            },
        )

    for domain in curriculum["domains"]:
        for competency in domain["competencies"]:
            Competency.objects.update_or_create(
                stable_id=competency["id"],
                defaults=_competency_defaults(domain, competency, version),
            )

    desired_links: set[tuple[str, str]] = set()
    for row in bundle.mapping_rows:
        competency_id = row["competency_id"].strip()
        for lever_id, weight in _mapping_weights(row).items():
            desired_links.add((competency_id, lever_id))
            CompetencyLeverLink.objects.update_or_create(
                competency_id=competency_id,
                lever_id=lever_id,
                defaults={"weight": weight},
            )
    stale_link_ids = [
        link.pk
        for link in CompetencyLeverLink.objects.all()
        if (link.competency_id, link.lever_id) not in desired_links
    ]
    CompetencyLeverLink.objects.filter(pk__in=stale_link_ids).delete()

    _seed_protocols(practice_bundle.runtime_protocols)
    pilot_runs, pilot_baselines = _seed_pilot(version, model)

    return ImportSummary(
        curriculum_versions=CurriculumVersion.objects.count(),
        levers=Lever.objects.count(),
        competencies=Competency.objects.count(),
        competency_lever_links=CompetencyLeverLink.objects.count(),
        practice_protocols=PracticeProtocol.objects.count(),
        pilot_assessment_runs=pilot_runs,
        pilot_lever_baselines=pilot_baselines,
    )
