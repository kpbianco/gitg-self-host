from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Sum

from growth.domain.practice_content import (
    configuration_hash,
    legacy_projection_payload,
    load_practice_content_bundle,
)
from growth.models import (
    ArchetypeResult,
    AssessmentRun,
    Competency,
    CompetencyLeverLink,
    CurriculumVersion,
    EvidenceEvent,
    Lever,
    LeverBaseline,
    OrientationResult,
    PracticeAction,
    PracticeCheckIn,
    PracticeProtocol,
    ScoreSnapshot,
)
from growth.services.canonical_import import (
    CanonicalBundle,
    CanonicalDataError,
    load_and_validate_bundle,
)
from growth.services.evidence import EvidenceWorkflowError, verify_all_evidence_events
from growth.services.score_state import ScoreStateError, verify_all_score_states

PILOT_READINESS_CONTRACT_VERSION = "GG-PILOT-READINESS-1.0"


@dataclass(frozen=True)
class ProtocolExpectation:
    parent_competency_id: str
    target_lever_ids: tuple[str, ...]
    action_ids: tuple[str, ...]
    score_active: bool = True


REVIEWED_PROTOCOLS = {
    "PRACTICE-FRIENDSHIP-01": ProtocolExpectation(
        parent_competency_id="17.03",
        target_lever_ids=("L23", "L24", "L26"),
        action_ids=(
            "PRACTICE-FRIENDSHIP-01-A1",
            "PRACTICE-FRIENDSHIP-01-A2",
            "PRACTICE-FRIENDSHIP-01-A3",
        ),
        score_active=True,
    ),
    "PRACTICE-PLAY-01": ProtocolExpectation(
        parent_competency_id="26.01",
        target_lever_ids=("L34",),
        action_ids=(
            "PRACTICE-PLAY-01-A1",
            "PRACTICE-PLAY-01-A2",
            "PRACTICE-PLAY-01-A3",
        ),
    ),
    "PRACTICE-EMOTIONAL-CUES-01": ProtocolExpectation(
        parent_competency_id="16.03",
        target_lever_ids=("L24",),
        action_ids=(
            "PRACTICE-EMOTIONAL-CUES-01-A1",
            "PRACTICE-EMOTIONAL-CUES-01-A2",
            "PRACTICE-EMOTIONAL-CUES-01-A3",
        ),
    ),
    "PRACTICE-BOUNDARY-01": ProtocolExpectation(
        parent_competency_id="11.10",
        target_lever_ids=("L25",),
        action_ids=(
            "PRACTICE-BOUNDARY-01-A1",
            "PRACTICE-BOUNDARY-01-A2",
            "PRACTICE-BOUNDARY-01-A3",
        ),
    ),
    "PRACTICE-PRESENCE-01": ProtocolExpectation(
        parent_competency_id="08.02",
        target_lever_ids=("L08",),
        action_ids=(
            "PRACTICE-PRESENCE-01-A1",
            "PRACTICE-PRESENCE-01-A2",
            "PRACTICE-PRESENCE-01-A3",
        ),
    ),
}
REVIEWED_PROTOCOL_CONFIGURATION_HASH = (
    "274f7244630ed56d56a443a6a699399edade6c67fcf964237559e05b72368e35"
)

EXPECTED_SOURCE_COUNTS = {
    "domains": 27,
    "lever_families": 7,
    "levers": 37,
    "competencies": 383,
    "orientations": 6,
    "archetypes": 15,
    "archetype_lever_affinities": 555,
    "competency_lever_links": 1403,
}


class PilotReadinessError(ValueError):
    pass


@dataclass(frozen=True)
class PilotReadinessSummary:
    contract_version: str
    domains: int
    lever_families: int
    levers: int
    competencies: int
    orientations: int
    archetypes: int
    archetype_lever_affinities: int
    competency_lever_links: int
    practice_protocols: int
    practice_actions: int
    active_protocols: int
    score_active_protocols: int
    users: int
    assessment_runs: int
    pilot_assessment_runs: int
    submitted_check_ins: int
    evidence_events: int
    score_state_runs: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _require_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise PilotReadinessError(f"{label}: expected {expected!r}, found {actual!r}.")


def _protocol_payload(protocol: PracticeProtocol) -> dict[str, Any]:
    return {
        "stable_id": protocol.stable_id,
        "slug": protocol.slug,
        "name": protocol.name,
        "parent_competency_id": protocol.parent_competency_id,
        "availability": protocol.availability,
        "duration_days": protocol.duration_days,
        "recommendation_reason": protocol.recommendation_reason,
        "applicability_prompt": protocol.applicability_prompt,
        "setup_prompt": protocol.setup_prompt,
        "privacy_and_boundaries": protocol.privacy_and_boundaries,
        "completion_criteria": protocol.completion_criteria,
        "completion_rules": protocol.completion_rules,
        "setup_copy": protocol.setup_copy,
        "check_in_fields": protocol.check_in_fields,
        "score_active": protocol.score_active,
        "mastery_disclaimer": protocol.mastery_disclaimer,
        "target_lever_ids": sorted(lever.stable_id for lever in protocol.target_levers.all()),
        "display_order": protocol.display_order,
        "actions": [
            {
                "stable_id": action.stable_id,
                "sequence": action.sequence,
                "title": action.title,
                "instructions": action.instructions,
                "due_within_days": action.due_within_days,
                "evidence_rules": action.evidence_rules,
            }
            for action in protocol.actions.all()
        ],
    }


def _configuration_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _source_counts() -> tuple[dict[str, int], CanonicalBundle]:
    try:
        bundle = load_and_validate_bundle()
    except CanonicalDataError as exc:
        raise PilotReadinessError(f"Canonical source validation failed: {exc}") from exc

    curriculum = bundle.curriculum
    model = bundle.model
    counts = {
        "domains": len(curriculum["domains"]),
        "lever_families": len(model["lever_families"]),
        "levers": len(model["developmental_levers"]),
        "competencies": sum(len(domain["competencies"]) for domain in curriculum["domains"]),
        "orientations": len(model["orientation_modes"]),
        "archetypes": len(model["archetypes"]),
        "archetype_lever_affinities": sum(
            len(archetype["lever_affinity"]) for archetype in model["archetypes"]
        ),
        "competency_lever_links": sum(
            len(link["lever_weights"]) for link in model["competency_lever_links"]
        ),
    }
    _require_equal("Canonical source counts", counts, EXPECTED_SOURCE_COUNTS)
    return counts, bundle


def _verify_seeded_curriculum(counts: dict[str, int], bundle: CanonicalBundle) -> None:
    curriculum = bundle.curriculum
    model = bundle.model
    version_id = f"CURRICULUM-{curriculum['version']}-MODEL-{model['model']['version']}"
    try:
        version = CurriculumVersion.objects.get(stable_id=version_id)
    except CurriculumVersion.DoesNotExist as exc:
        raise PilotReadinessError(f"Seeded curriculum version {version_id!r} is missing.") from exc
    if not version.active:
        raise PilotReadinessError(f"Seeded curriculum version {version_id!r} is inactive.")
    _require_equal("Seeded curriculum source hash", version.source_hash, bundle.source_hash)
    _require_equal("Seeded levers", Lever.objects.count(), counts["levers"])
    _require_equal(
        "Seeded competencies",
        Competency.objects.count(),
        counts["competencies"],
    )
    _require_equal(
        "Seeded competency-to-lever links",
        CompetencyLeverLink.objects.count(),
        counts["competency_lever_links"],
    )

    expected_links = {}
    for row in bundle.mapping_rows:
        competency_id = row["competency_id"].strip()
        for slot in range(1, 6):
            lever_id = row[f"lever_{slot}_id"].strip()
            if lever_id:
                expected_links[(competency_id, lever_id)] = Decimal(row[f"lever_{slot}_weight"])
    actual_links = {
        (competency_id, lever_id): weight
        for competency_id, lever_id, weight in CompetencyLeverLink.objects.values_list(
            "competency_id", "lever_id", "weight"
        )
    }
    missing = sorted(set(expected_links) - set(actual_links))
    extra = sorted(set(actual_links) - set(expected_links))
    changed = sorted(
        key
        for key in set(expected_links) & set(actual_links)
        if expected_links[key] != actual_links[key]
    )
    if missing or extra or changed:
        raise PilotReadinessError(
            "Seeded competency mapping drift: "
            f"missing={missing[:10]}, extra={extra[:10]}, changed={changed[:10]}."
        )

    malformed = []
    weight_totals = CompetencyLeverLink.objects.values("competency_id").annotate(
        total=Sum("weight")
    )
    for row in weight_totals:
        competency_id = row["competency_id"]
        total = row["total"] or Decimal("0")
        if abs(total - Decimal("1")) > Decimal("0.000001"):
            malformed.append(f"{competency_id}={total}")
    if malformed:
        raise PilotReadinessError(
            "Seeded competency-to-lever weights are malformed: " + ", ".join(malformed[:10])
        )


def _verify_protocol_inventory() -> tuple[int, int, int, int]:
    canonical_runtime = load_practice_content_bundle(settings.BASE_DIR).runtime_protocols
    canonical_by_id = {protocol["stable_id"]: protocol for protocol in canonical_runtime}
    protocols = {
        protocol.stable_id: protocol
        for protocol in PracticeProtocol.objects.select_related(
            "parent_competency"
        ).prefetch_related(
            "actions",
            "target_levers",
            "parent_competency__lever_links",
        )
    }
    _require_equal(
        "Reviewed protocol stable IDs",
        set(protocols),
        set(canonical_by_id),
    )

    for stable_id, expected in REVIEWED_PROTOCOLS.items():
        protocol = protocols[stable_id]
        _require_equal(
            f"{stable_id} availability",
            protocol.availability,
            PracticeProtocol.Availability.ACTIVE,
        )
        _require_equal(
            f"{stable_id} parent competency",
            protocol.parent_competency_id,
            expected.parent_competency_id,
        )
        _require_equal(
            f"{stable_id} target levers",
            tuple(sorted(protocol.target_levers.values_list("stable_id", flat=True))),
            expected.target_lever_ids,
        )
        _require_equal(
            f"{stable_id} score activation",
            protocol.score_active,
            expected.score_active,
        )
        _require_equal(
            f"{stable_id} mastery disclaimer",
            protocol.mastery_disclaimer,
            "Completing this practice does not establish mastery.",
        )
        actions = tuple(protocol.actions.all())
        _require_equal(
            f"{stable_id} action stable IDs",
            tuple(action.stable_id for action in actions),
            expected.action_ids,
        )
        _require_equal(
            f"{stable_id} action sequence",
            tuple(action.sequence for action in actions),
            (1, 2, 3),
        )

        mapped_levers = {link.lever_id for link in protocol.parent_competency.lever_links.all()}
        if not set(expected.target_lever_ids).issubset(mapped_levers):
            raise PilotReadinessError(
                f"{stable_id}: recommendation targets are outside its canonical mapping."
            )

    score_active_ids = tuple(
        PracticeProtocol.objects.filter(score_active=True)
        .order_by("stable_id")
        .values_list("stable_id", flat=True)
    )
    _require_equal(
        "Score-active protocol boundary",
        score_active_ids,
        tuple(sorted(canonical_by_id)),
    )
    _require_equal(
        "Canonical runtime configuration fingerprint",
        _configuration_hash(
            [_protocol_payload(protocols[stable_id]) for stable_id in sorted(protocols)]
        ),
        configuration_hash(
            [
                legacy_projection_payload(canonical_by_id[stable_id])
                for stable_id in sorted(canonical_by_id)
            ]
        ),
    )
    return (
        len(protocols),
        PracticeAction.objects.count(),
        PracticeProtocol.objects.filter(availability=PracticeProtocol.Availability.ACTIVE).count(),
        len(score_active_ids),
    )


def _verify_assessment_inventory(bundle: CanonicalBundle) -> tuple[int, int, int]:
    users = get_user_model().objects.count()
    if users < 1:
        raise PilotReadinessError("At least one application user is required.")

    lever_ids = tuple(sorted(item["id"] for item in bundle.model["developmental_levers"]))
    orientation_ids = tuple(sorted(item["id"] for item in bundle.model["orientation_modes"]))
    archetype_ids = tuple(sorted(item["id"] for item in bundle.model["archetypes"]))
    runs = list(AssessmentRun.objects.order_by("stable_id"))
    pilot_runs = [run for run in runs if run.source == AssessmentRun.Source.PILOT_SEED]
    _require_equal("Pilot 002 assessment-run count", len(pilot_runs), 1)

    for run in runs:
        _require_equal(f"{run.stable_id} assessment version", run.assessment_version, "1.1")
        if run.source == AssessmentRun.Source.PILOT_SEED and not run.stable_id.startswith(
            "PILOT-002-USER-"
        ):
            raise PilotReadinessError(
                f"{run.stable_id}: Pilot 002 stable ID has an unexpected shape."
            )
        _require_equal(
            f"{run.stable_id} lever baseline IDs",
            tuple(
                LeverBaseline.objects.filter(assessment_run=run)
                .order_by("lever_id")
                .values_list("lever_id", flat=True)
            ),
            lever_ids,
        )
        _require_equal(
            f"{run.stable_id} orientation output IDs",
            tuple(
                OrientationResult.objects.filter(assessment_run=run)
                .order_by("stable_id")
                .values_list("stable_id", flat=True)
            ),
            orientation_ids,
        )
        expected_archetypes = (
            ("A03", "A04", "A05")
            if run.source == AssessmentRun.Source.PILOT_SEED
            else archetype_ids
        )
        _require_equal(
            f"{run.stable_id} archetype output IDs",
            tuple(
                ArchetypeResult.objects.filter(assessment_run=run)
                .order_by("stable_id")
                .values_list("stable_id", flat=True)
            ),
            expected_archetypes,
        )

    return users, len(runs), len(pilot_runs)


def _verify_static_score_boundary() -> None:
    if EvidenceEvent.objects.filter(check_in__status=PracticeCheckIn.Status.DRAFT).exists():
        raise PilotReadinessError("A draft check-in is incorrectly present in the evidence ledger.")
    if ScoreSnapshot.objects.filter(
        evidence_event__check_in__sprint__protocol__score_active=False
    ).exists():
        raise PilotReadinessError(
            "A score-inactive protocol has an evidence-linked score snapshot."
        )


def verify_pilot_readiness() -> PilotReadinessSummary:
    """Verify the reviewed post-M4 pilot boundary without writing application state."""

    counts, bundle = _source_counts()
    _verify_seeded_curriculum(counts, bundle)
    protocol_count, action_count, active_count, score_active_count = _verify_protocol_inventory()
    users, assessment_runs, pilot_runs = _verify_assessment_inventory(bundle)
    _verify_static_score_boundary()

    try:
        evidence = verify_all_evidence_events()
    except EvidenceWorkflowError as exc:
        raise PilotReadinessError(f"Evidence replay failed: {exc}") from exc
    try:
        score_state = verify_all_score_states()
    except ScoreStateError as exc:
        raise PilotReadinessError(f"Score-state replay failed: {exc}") from exc

    return PilotReadinessSummary(
        contract_version=PILOT_READINESS_CONTRACT_VERSION,
        practice_protocols=protocol_count,
        practice_actions=action_count,
        active_protocols=active_count,
        score_active_protocols=score_active_count,
        users=users,
        assessment_runs=assessment_runs,
        pilot_assessment_runs=pilot_runs,
        submitted_check_ins=evidence.submitted_check_ins,
        evidence_events=evidence.events_verified,
        score_state_runs=score_state.assessment_runs,
        **counts,
    )
