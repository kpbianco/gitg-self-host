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
from growth.domain.scoring import (
    ScoringContractError,
    reconstruct_published_baseline_mass,
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


PROTOCOLS = (
    {
        "stable_id": "PRACTICE-FRIENDSHIP-01",
        "slug": "deepen-one-existing-friendship",
        "name": "Deepen One Existing Friendship",
        "parent_competency_id": "17.03",
        "availability": PracticeProtocol.Availability.ACTIVE,
        "duration_days": 14,
        "recommendation_reason": (
            "Your provisional profile places friendship, belonging, and hospitality "
            "among the highest current developmental needs."
        ),
        "applicability_prompt": (
            "Is there an existing friend you genuinely value and would realistically "
            "like to know more deeply right now?"
        ),
        "setup_prompt": (
            "Choose one existing friend whom you genuinely value and would realistically "
            "like to know more deeply."
        ),
        "privacy_and_boundaries": (
            "Choose a relationship where contact is welcome. Do not pressure disclosure, "
            "treat reciprocity as owed, record private details unnecessarily, or use this "
            "practice in place of professional support."
        ),
        "completion_criteria": [
            "All three actions attempted",
            "At least two actions completed",
            "At least one substantive interaction",
            "Final review submitted",
        ],
        "completion_rules": {
            "minimum_completed": 2,
            "substantive_markers": [
                "moved_beyond_transactional",
                "meaningful_information_shared",
            ],
        },
        "setup_copy": {
            "context_heading": "Choose one existing relationship.",
            "boundary_heading": "Depth must remain freely chosen.",
            "timing_hint": "Choose a date when a real, welcome interaction is plausible.",
            "context_help": "Use a first name, initials, or another private label.",
            "applicability_heading": "A real relationship, not a hypothetical exercise",
            "completion_signal_label": "At least one substantive interaction",
            "boundary_acknowledgement": (
                "I will choose welcome contact, respect privacy and autonomy, "
                "and treat reciprocity as freely given—not owed."
            ),
        },
        "check_in_fields": [
            "user_initiated",
            "moved_beyond_transactional",
            "follow_up_question_asked",
            "meaningful_information_shared",
            "future_interaction_scheduled",
            "follow_up_within_seven_days",
            "internal_resistance",
            "expected_reciprocity",
            "observed_reciprocity",
        ],
        "score_active": True,
        "target_levers": ["L26", "L23", "L24"],
        "display_order": 1,
        "actions": [
            {
                "stable_id": "PRACTICE-FRIENDSHIP-01-A1",
                "sequence": 1,
                "title": "Listen to what matters now",
                "instructions": (
                    "Initiate a substantive conversation about something currently "
                    "meaningful in your friend's life. Spend at least ten minutes "
                    "primarily listening."
                ),
                "due_within_days": None,
                "evidence_rules": {
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
            },
            {
                "stable_id": "PRACTICE-FRIENDSHIP-01-A2",
                "sequence": 2,
                "title": "Make a specific invitation",
                "instructions": (
                    "Propose a specific shared activity and date rather than a vague "
                    "future intention."
                ),
                "due_within_days": None,
                "evidence_rules": {
                    "schema_version": "practice-observation-v1",
                    "primary_markers": ["future_interaction_scheduled"],
                    "supporting_markers": ["user_initiated"],
                },
            },
            {
                "stable_id": "PRACTICE-FRIENDSHIP-01-A3",
                "sequence": 3,
                "title": "Follow up",
                "instructions": (
                    "Within seven days, reference something the person shared and ask "
                    "how it developed."
                ),
                "due_within_days": 7,
                "evidence_rules": {
                    "schema_version": "practice-observation-v1",
                    "primary_markers": [
                        "follow_up_within_seven_days",
                        "follow_up_question_asked",
                    ],
                    "supporting_markers": [
                        "meaningful_information_shared",
                        "user_initiated",
                    ],
                },
            },
        ],
    },
    {
        "stable_id": "PRACTICE-PLAY-01",
        "slug": "schedule-non-instrumental-play",
        "name": "Schedule Non-Instrumental Play",
        "parent_competency_id": "26.01",
        "availability": PracticeProtocol.Availability.ACTIVE,
        "duration_days": 10,
        "recommendation_reason": (
            "Your current provisional profile identifies playfulness, recreation, "
            "and non-instrumental activity as a useful area for practice."
        ),
        "applicability_prompt": (
            "Is there a safe, accessible activity you can do primarily for enjoyment "
            "rather than productivity or improvement?"
        ),
        "setup_prompt": (
            "Choose one low-stakes form of play that is realistically available now. "
            "Examples may include a game, making something, movement, music, "
            "or playful exploration."
        ),
        "privacy_and_boundaries": (
            "Choose an activity that is physically, financially, and socially safe. "
            "Do not use the practice to pressure another person, ignore responsibilities, "
            "or turn rest into another performance target."
        ),
        "completion_criteria": [
            "All three actions attempted",
            "At least two actions completed",
            "At least one period of genuinely non-instrumental engagement",
            "Final review submitted",
        ],
        "completion_rules": {
            "minimum_completed": 2,
            "substantive_markers": [
                "moved_beyond_transactional",
                "meaningful_information_shared",
            ],
        },
        "setup_copy": {
            "context_heading": "Choose one form of play.",
            "boundary_heading": "Keep play safe and freely chosen.",
            "timing_hint": "Choose a date when an unhurried play window is realistic.",
            "context_help": "Use a short private label for the activity or setting.",
            "applicability_heading": "A real activity, not an abstract intention",
            "completion_signal_label": (
                "At least one period of genuinely non-instrumental engagement"
            ),
            "boundary_acknowledgement": (
                "I will keep this activity safe, voluntary, and proportionate "
                "to my responsibilities."
            ),
            "check_in_labels": {
                "future_interaction_scheduled": "A specific play window was reserved",
                "moved_beyond_transactional": "I engaged in the activity",
                "meaningful_information_shared": (
                    "I kept the activity free of output or optimization goals"
                ),
                "follow_up_within_seven_days": "I returned to play within seven days",
            },
        },
        "check_in_fields": [
            "future_interaction_scheduled",
            "moved_beyond_transactional",
            "meaningful_information_shared",
            "follow_up_within_seven_days",
            "internal_resistance",
        ],
        "target_levers": ["L34"],
        "display_order": 2,
        "actions": [
            {
                "stable_id": "PRACTICE-PLAY-01-A1",
                "sequence": 1,
                "title": "Reserve a play window",
                "instructions": (
                    "Choose a specific activity and reserve at least 30 minutes "
                    "for it within the next three days."
                ),
                "due_within_days": 3,
                "evidence_rules": {
                    "schema_version": "practice-observation-v1",
                    "primary_markers": ["future_interaction_scheduled"],
                    "supporting_markers": ["user_initiated"],
                },
            },
            {
                "stable_id": "PRACTICE-PLAY-01-A2",
                "sequence": 2,
                "title": "Play without an output goal",
                "instructions": (
                    "Use the reserved time for the activity. For that window, do not "
                    "optimize, publish, measure, or turn it into work."
                ),
                "due_within_days": None,
                "evidence_rules": {
                    "schema_version": "practice-observation-v1",
                    "primary_markers": [
                        "moved_beyond_transactional",
                        "meaningful_information_shared",
                    ],
                    "supporting_markers": ["user_initiated"],
                },
            },
            {
                "stable_id": "PRACTICE-PLAY-01-A3",
                "sequence": 3,
                "title": "Return once",
                "instructions": (
                    "Within seven days, return to the activity for another short period "
                    "or choose a second playful activity."
                ),
                "due_within_days": 7,
                "evidence_rules": {
                    "schema_version": "practice-observation-v1",
                    "primary_markers": ["follow_up_within_seven_days"],
                    "supporting_markers": ["moved_beyond_transactional"],
                },
            },
        ],
    },
    {
        "stable_id": "PRACTICE-EMOTIONAL-CUES-01",
        "slug": "practice-emotional-cue-detection",
        "name": "Practice Emotional Cue Detection",
        "parent_competency_id": "16.03",
        "availability": PracticeProtocol.Availability.ACTIVE,
        "duration_days": 10,
        "recommendation_reason": (
            "Your current provisional profile identifies empathy, social perception, "
            "and perspective-taking as a useful area for careful practice."
        ),
        "applicability_prompt": (
            "Is there a familiar, low-stakes interaction where contact is welcome and "
            "you can check your impressions directly rather than guessing?"
        ),
        "setup_prompt": (
            "Choose one familiar person or recurring low-stakes setting. Use this "
            "practice only where a neutral clarification question would be welcome."
        ),
        "privacy_and_boundaries": (
            "Treat every cue as uncertain and context-dependent. Do not diagnose, "
            "claim to know another person's feelings, test someone secretly, or infer "
            "intent from eye contact or body language alone. Culture, disability, "
            "neurotype, stress, and habit can all change how cues appear."
        ),
        "completion_criteria": [
            "All three actions attempted",
            "At least two actions completed",
            "At least one impression checked through direct clarification",
            "Final review submitted",
        ],
        "completion_rules": {
            "minimum_completed": 2,
            "substantive_markers": ["follow_up_question_asked"],
        },
        "setup_copy": {
            "context_heading": "Choose one low-stakes interaction context.",
            "boundary_heading": "Observation is not mind-reading.",
            "timing_hint": "Choose a date when a familiar, unhurried interaction is realistic.",
            "context_help": (
                "Use initials or a short private label. Do not record sensitive details."
            ),
            "applicability_heading": "A checkable interaction, not a personality judgment",
            "completion_signal_label": (
                "At least one impression checked through direct clarification"
            ),
            "boundary_acknowledgement": (
                "I will treat cues as uncertain, avoid diagnosis and stereotyping, "
                "and prefer direct clarification over assumption."
            ),
            "check_in_labels": {
                "user_initiated": "I deliberately paused to observe before interpreting",
                "moved_beyond_transactional": (
                    "I noticed a change in tone, pace, posture, expression, or distance"
                ),
                "follow_up_question_asked": "I asked a neutral question to check my impression",
                "meaningful_information_shared": (
                    "The person voluntarily clarified their experience"
                ),
                "follow_up_within_seven_days": (
                    "I compared my initial reading with later information within seven days"
                ),
            },
        },
        "check_in_fields": [
            "user_initiated",
            "moved_beyond_transactional",
            "follow_up_question_asked",
            "meaningful_information_shared",
            "follow_up_within_seven_days",
            "internal_resistance",
        ],
        "target_levers": ["L24"],
        "display_order": 3,
        "actions": [
            {
                "stable_id": "PRACTICE-EMOTIONAL-CUES-01-A1",
                "sequence": 1,
                "title": "Notice before interpreting",
                "instructions": (
                    "During one welcome, low-stakes interaction, notice one observable "
                    "change in tone, pace, posture, expression, gesture, or distance. "
                    "Describe only what changed; do not assign a feeling or motive yet."
                ),
                "due_within_days": 3,
                "evidence_rules": {
                    "schema_version": "practice-observation-v1",
                    "primary_markers": ["moved_beyond_transactional"],
                    "supporting_markers": ["user_initiated"],
                },
            },
            {
                "stable_id": "PRACTICE-EMOTIONAL-CUES-01-A2",
                "sequence": 2,
                "title": "Hold more than one explanation",
                "instructions": (
                    "Name at least two plausible explanations for the cue, including "
                    "one that does not concern you. Keep both tentative."
                ),
                "due_within_days": None,
                "evidence_rules": {
                    "schema_version": "practice-observation-v1",
                    "primary_markers": ["user_initiated"],
                    "supporting_markers": ["moved_beyond_transactional"],
                },
            },
            {
                "stable_id": "PRACTICE-EMOTIONAL-CUES-01-A3",
                "sequence": 3,
                "title": "Clarify without leading",
                "instructions": (
                    "When welcome, ask one neutral question such as “I may be reading "
                    "this wrong—how is this landing?” Within seven days, compare the "
                    "answer or later information with your initial impression."
                ),
                "due_within_days": 7,
                "evidence_rules": {
                    "schema_version": "practice-observation-v1",
                    "primary_markers": [
                        "follow_up_question_asked",
                        "follow_up_within_seven_days",
                    ],
                    "supporting_markers": ["meaningful_information_shared"],
                },
            },
        ],
    },
    {
        "stable_id": "PRACTICE-BOUNDARY-01",
        "slug": "state-and-maintain-one-boundary",
        "name": "State and Maintain One Boundary",
        "parent_competency_id": "11.10",
        "availability": PracticeProtocol.Availability.ACTIVE,
        "duration_days": 10,
        "recommendation_reason": (
            "Your current provisional profile identifies clear, proportionate limits "
            "as a useful area for careful practice."
        ),
        "applicability_prompt": (
            "Is there one low-stakes request, recurring expectation, or optional "
            "commitment likely to arise in the next ten days where you can safely "
            "state a limit and choose your own follow-through?"
        ),
        "setup_prompt": (
            "Choose one specific request, expectation, or commitment—not a person to "
            "fix. Use this practice only where direct communication is reasonably safe."
        ),
        "privacy_and_boundaries": (
            "A boundary states what you will or will not participate in and what you "
            "will do; it does not force another person to agree. Do not use threats, "
            "punishment, withdrawal of care, silent tests, or pressure to control "
            "someone. Do not use this protocol where abuse, coercive control, stalking, "
            "discrimination, unsafe dependency, or retaliation is present or likely. "
            "Prioritize safety planning and appropriate trusted, professional, legal, "
            "medical, or organizational support in those situations."
        ),
        "completion_criteria": [
            "All three actions attempted",
            "At least two actions completed",
            "One boundary stated directly",
            "One proportionate follow-through observed within seven days",
            "Final review submitted",
        ],
        "completion_rules": {
            "minimum_completed": 2,
            "substantive_markers": [
                "moved_beyond_transactional",
                "follow_up_within_seven_days",
            ],
            "marker_mode": "all",
        },
        "setup_copy": {
            "context_heading": "Choose one low-stakes limit you can control.",
            "boundary_heading": "A boundary is not coercion or punishment.",
            "timing_hint": (
                "Choose a date when this specific situation is likely to arise safely."
            ),
            "context_help": (
                "Use a short private label for the request, expectation, or commitment. "
                "Do not record identifying or sensitive details."
            ),
            "applicability_heading": ("A specific, likely situation—not a test of another person"),
            "applicability_yes_label": ("Yes, one safe, low-stakes situation is likely to arise"),
            "completion_signal_label": (
                "One boundary stated directly and one proportionate follow-through "
                "within seven days"
            ),
            "history_marker_label": "direct boundary statement",
            "boundary_acknowledgement": (
                "I will use a low-stakes context where direct communication is "
                "reasonably safe, state only what I control, and not use threats, "
                "punishment, silent tests, or pressure."
            ),
            "check_in_labels": {
                "user_initiated": ("I chose a specific limit and a response that I control"),
                "moved_beyond_transactional": ("I stated the boundary directly in specific words"),
                "follow_up_question_asked": (
                    "I checked understanding without bargaining or testing"
                ),
                "follow_up_within_seven_days": (
                    "I followed through proportionately or restated the boundary within seven days"
                ),
            },
        },
        "check_in_fields": [
            "user_initiated",
            "moved_beyond_transactional",
            "follow_up_question_asked",
            "follow_up_within_seven_days",
            "internal_resistance",
        ],
        "target_levers": ["L25"],
        "display_order": 4,
        "actions": [
            {
                "stable_id": "PRACTICE-BOUNDARY-01-A1",
                "sequence": 1,
                "title": "Define what you control",
                "instructions": (
                    "Identify one low-stakes limit. Write one sentence stating what "
                    "you will or will not participate in and the proportionate action "
                    "you will take if the limit is crossed. Do not make another "
                    "person's compliance the intervention."
                ),
                "due_within_days": 3,
                "evidence_rules": {
                    "schema_version": "practice-observation-v1",
                    "primary_markers": ["user_initiated"],
                    "supporting_markers": ["moved_beyond_transactional"],
                },
            },
            {
                "stable_id": "PRACTICE-BOUNDARY-01-A2",
                "sequence": 2,
                "title": "State the boundary directly",
                "instructions": (
                    "In a reasonably safe context, state the limit in plain, specific "
                    "words. You may make a request, but the boundary must not depend "
                    "on forcing agreement. Do not threaten, punish, or set a silent test."
                ),
                "due_within_days": None,
                "evidence_rules": {
                    "schema_version": "practice-observation-v1",
                    "primary_markers": ["moved_beyond_transactional"],
                    "supporting_markers": ["follow_up_question_asked"],
                },
            },
            {
                "stable_id": "PRACTICE-BOUNDARY-01-A3",
                "sequence": 3,
                "title": "Follow through once",
                "instructions": (
                    "Within seven days, when the situation arises, carry out the "
                    "proportionate action you named or calmly restate the limit. Stop "
                    "the protocol and seek appropriate support if safety or retaliation "
                    "becomes a concern."
                ),
                "due_within_days": 7,
                "evidence_rules": {
                    "schema_version": "practice-observation-v1",
                    "primary_markers": ["follow_up_within_seven_days"],
                    "supporting_markers": ["user_initiated"],
                },
            },
        ],
    },
    {
        "stable_id": "PRACTICE-PRESENCE-01",
        "slug": "complete-an-attention-presence-experiment",
        "name": "Complete an Attention-Presence Experiment",
        "parent_competency_id": "08.02",
        "availability": PracticeProtocol.Availability.ACTIVE,
        "duration_days": 10,
        "recommendation_reason": (
            "Your current provisional profile identifies deliberate attention and "
            "contact with the present as a useful area for a bounded experiment."
        ),
        "applicability_prompt": (
            "Is there one safe, low-stakes 15-minute activity you can repeat under "
            "usual conditions, with one changed condition, and once more within "
            "seven days?"
        ),
        "setup_prompt": (
            "Choose one repeatable activity such as reading, a routine desk task, "
            "making something, or attending to your surroundings. Compare conditions "
            "around the same activity rather than judging your productivity."
        ),
        "privacy_and_boundaries": (
            "Presence does not require stillness, silence, eye contact, or zero "
            "distraction. Keep movement, fidgets, assistive technology, reminders, "
            "and other supports that help you participate. Do not disable emergency, "
            "accessibility, or caregiving alerts. Do not run the experiment while "
            "driving, operating equipment, or supervising a hazard; install "
            "surveillance; or record another person. Treat disability, "
            "neurodiversity, pain, fatigue, "
            "and stress as design context—not failure. This protocol is not diagnosis "
            "or treatment; persistent or safety-affecting attention difficulty may "
            "need qualified support."
        ),
        "completion_criteria": [
            "All three actions attempted",
            "At least two actions completed",
            "Usual and changed conditions compared",
            "The more workable condition repeated within seven days",
            "Final review submitted",
        ],
        "completion_rules": {
            "minimum_completed": 2,
            "substantive_markers": [
                "meaningful_information_shared",
                "follow_up_within_seven_days",
            ],
            "marker_mode": "all",
        },
        "setup_copy": {
            "context_heading": "Choose one repeatable 15-minute activity.",
            "boundary_heading": "Presence is not stillness, perfection, or surveillance.",
            "timing_hint": "Choose a date when a safe, low-stakes attention window is realistic.",
            "context_help": (
                "Use a short private label for the activity. Do not record another "
                "person or the content of a private interaction."
            ),
            "applicability_heading": "One repeatable activity with one changeable condition",
            "applicability_yes_label": "Yes, I have a safe 15-minute activity I can repeat",
            "completion_signal_label": (
                "Usual and changed conditions compared, then the more workable "
                "condition repeated within seven days"
            ),
            "history_marker_label": "completed attention window",
            "boundary_acknowledgement": (
                "I will use a safe, low-stakes activity, keep supports and alerts "
                "needed for access or safety, and treat distraction as information—not "
                "failure."
            ),
            "check_in_labels": {
                "user_initiated": "I deliberately began the planned attention window",
                "moved_beyond_transactional": "I completed the full attention window",
                "follow_up_question_asked": "I noticed attention drift and deliberately returned",
                "meaningful_information_shared": "I compared the usual and changed condition",
                "follow_up_within_seven_days": (
                    "I repeated the more workable condition within seven days"
                ),
            },
        },
        "check_in_fields": [
            "user_initiated",
            "moved_beyond_transactional",
            "follow_up_question_asked",
            "meaningful_information_shared",
            "follow_up_within_seven_days",
            "internal_resistance",
        ],
        "target_levers": ["L08"],
        "display_order": 5,
        "actions": [
            {
                "stable_id": "PRACTICE-PRESENCE-01-A1",
                "sequence": 1,
                "title": "Run the usual-condition window",
                "instructions": (
                    "Spend 15 minutes on the chosen activity under your usual safe "
                    "conditions. When attention drifts, notice it and return without "
                    "counting every drift or treating distraction as failure. Keep "
                    "your normal accessibility supports."
                ),
                "due_within_days": 3,
                "evidence_rules": {
                    "schema_version": "practice-observation-v1",
                    "primary_markers": [
                        "user_initiated",
                        "moved_beyond_transactional",
                    ],
                    "supporting_markers": ["follow_up_question_asked"],
                },
            },
            {
                "stable_id": "PRACTICE-PRESENCE-01-A2",
                "sequence": 2,
                "title": "Change one condition and compare",
                "instructions": (
                    "Repeat a comparable 15-minute window after changing exactly one "
                    "condition you control—for example, silence nonessential alerts, "
                    "clear one competing item, or add a movement, fidget, or visual "
                    "cue. Compare how readily you noticed and returned attention, not "
                    "how much output you produced."
                ),
                "due_within_days": None,
                "evidence_rules": {
                    "schema_version": "practice-observation-v1",
                    "primary_markers": [
                        "meaningful_information_shared",
                        "moved_beyond_transactional",
                    ],
                    "supporting_markers": [
                        "user_initiated",
                        "follow_up_question_asked",
                    ],
                },
            },
            {
                "stable_id": "PRACTICE-PRESENCE-01-A3",
                "sequence": 3,
                "title": "Repeat the more workable condition",
                "instructions": (
                    "Within seven days, repeat the condition that made noticing and "
                    "returning more workable. Record what happened, including evidence "
                    "that the change made no difference or worked less well."
                ),
                "due_within_days": 7,
                "evidence_rules": {
                    "schema_version": "practice-observation-v1",
                    "primary_markers": ["follow_up_within_seven_days"],
                    "supporting_markers": [
                        "moved_beyond_transactional",
                        "meaningful_information_shared",
                    ],
                },
            },
        ],
    },
)


def _seed_protocols() -> None:
    for item in PROTOCOLS:
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
        if completion_rules and (
            not isinstance(substantive_markers, list)
            or not substantive_markers
            or set(substantive_markers) - ALLOWED_OBSERVATION_FIELDS
            or marker_mode not in {"any", "all"}
        ):
            raise CanonicalDataError(
                f"{item['stable_id']}: completion markers must use the reviewed "
                "evidence observation vocabulary and a supported marker mode."
            )
        if item.get("score_active", False) and item["stable_id"] != "PRACTICE-FRIENDSHIP-01":
            raise CanonicalDataError(
                f"{item['stable_id']}: score activation requires a separate reviewed contract."
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
            "display_order": item["display_order"],
        }
        protocol, _ = PracticeProtocol.objects.update_or_create(
            stable_id=item["stable_id"], defaults=defaults
        )
        protocol.target_levers.set(Lever.objects.filter(stable_id__in=item["target_levers"]))
        desired_actions: set[str] = set()
        for action in item.get("actions", []):
            try:
                validate_evidence_rules(action["evidence_rules"])
            except (KeyError, EvidenceContractError) as exc:
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

    _seed_protocols()
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
