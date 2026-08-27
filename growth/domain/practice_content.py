from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from growth.domain.evidence import (
    ALLOWED_OBSERVATION_FIELDS,
    EvidenceContractError,
    validate_evidence_rules,
)
from growth.domain.typed_evidence import (
    TYPED_EVIDENCE_RULES_VERSION,
    TypedEvidenceContractError,
    load_typed_evidence_spec,
    materialize_typed_evidence_rules,
)

PRACTICE_CONTENT_SCHEMA_VERSION = "GG-PRACTICE-CONTENT-1.0"
SOURCE_REGISTRY_VERSION = "GG-PRACTICE-SOURCES-1.0"
RISK_TAXONOMY_VERSION = "GG-PROTOCOL-RISK-1.0"
SCORING_POLICY_REGISTRY_VERSION = "GG-SCORING-POLICY-1.0"
PROTOCOL_FAMILY_REGISTRY_VERSION = "GG-PROTOCOL-FAMILY-1.0"
ACTIVATION_LEDGER_VERSION = "GG-SCORE-ACTIVATION-1.0"
ACTIVE_SCORING_POLICY_ID = "SP-STRUCTURED-EVIDENCE-ELIGIBLE"
ACTIVE_SCORE_STATE_CONTRACT = "GG-SCORE-STATE-1.0"
ACTIVE_DECISION_REFERENCE = "docs/PRODUCT_DECISIONS.md#decision-052"
RESEARCH_GAP_REGISTRY_VERSION = "GG-PRACTICE-RESEARCH-GAPS-1.0"
EXPERT_REVIEW_REGISTRY_VERSION = "GG-PRACTICE-EXPERT-REVIEW-1.0"
RELEASE_MANIFEST_VERSION = "GG-PRACTICE-RELEASE-1.0"
LEGACY_PROJECTION_VERSION = "GG-PRACTICE-RUNTIME-PROJECTION-1.0"
TYPED_RUNTIME_PROJECTION_VERSION = "GG-PRACTICE-RUNTIME-PROJECTION-2.0"

FROZEN_LEGACY_PROTOCOL_IDS = (
    "PRACTICE-BOUNDARY-01",
    "PRACTICE-EMOTIONAL-CUES-01",
    "PRACTICE-FRIENDSHIP-01",
    "PRACTICE-PLAY-01",
    "PRACTICE-PRESENCE-01",
)
FROZEN_LEGACY_CONFIGURATION_HASH = (
    "274f7244630ed56d56a443a6a699399edade6c67fcf964237559e05b72368e35"
)
FROZEN_LEGACY_DUPLICATE_RULE_GROUPS = {
    (
        "PRACTICE-BOUNDARY-01-A1",
        "PRACTICE-EMOTIONAL-CUES-01-A2",
    ),
    (
        "PRACTICE-FRIENDSHIP-01-A2",
        "PRACTICE-PLAY-01-A1",
    ),
}
FROZEN_LEGACY_UNCOLLECTABLE_MARKERS = {
    ("PRACTICE-PLAY-01-A1", "user_initiated"),
}
REQUIRED_SCORING_POLICY_EFFECTS = {
    "SP-STRUCTURED-EVIDENCE-ELIGIBLE": "eligible_if_activated",
    "SP-SELF-REPORT-ELIGIBLE": "eligible_if_activated",
    "SP-CORROBORATION-REQUIRED": "eligible_if_activated",
    "SP-ARTIFACT-OBJECTIVE-PREFERRED": "eligible_if_activated",
    "SP-QUALIFIED-EVIDENCE-REQUIRED": "qualified_update_only",
    "SP-SHADOW-ONLY": "shadow_only",
    "SP-NON-SCORED-REFLECTION": "no_score_update",
}
REQUIRED_RISK_BOUNDARIES = {
    "RISK-LOW": {
        "ceiling": "active_if_separately_approved",
        "specialist_review_required": False,
        "sections": {
            "privacy_and_boundaries",
            "adaptations",
            "stop_conditions",
            "escalation_conditions",
        },
    },
    "RISK-MODERATE": {
        "ceiling": "shadow_only",
        "specialist_review_required": True,
        "sections": {
            "foreseeable_misuse",
            "exclusions",
            "privacy_and_boundaries",
            "adaptations",
            "stop_conditions",
            "escalation_conditions",
        },
    },
    "RISK-HIGH": {
        "ceiling": "qualified_only",
        "specialist_review_required": True,
        "sections": {
            "foreseeable_misuse",
            "exclusions",
            "privacy_and_boundaries",
            "adaptations",
            "stop_conditions",
            "escalation_conditions",
            "qualified_referral_boundary",
        },
    },
}
ALLOWED_CHECK_IN_FIELDS = ALLOWED_OBSERVATION_FIELDS | {
    "internal_resistance",
    "expected_reciprocity",
    "observed_reciprocity",
}


class PracticeContentError(ValueError):
    pass


@dataclass(frozen=True)
class PracticeContentBundle:
    protocols: tuple[dict[str, Any], ...]
    sources: dict[str, dict[str, Any]]
    risk_classes: dict[str, dict[str, Any]]
    scoring_policies: dict[str, dict[str, Any]]
    protocol_families: dict[str, dict[str, Any]]
    activation_entries: dict[str, dict[str, Any]]
    research_gaps: dict[str, dict[str, Any]]
    expert_reviews: dict[str, dict[str, Any]]
    release_manifest: dict[str, Any]
    content_hash: str

    @property
    def runtime_protocols(self) -> tuple[dict[str, Any], ...]:
        projected = [
            compile_runtime_protocol(protocol, self.activation_entries)
            for protocol in self.protocols
            if protocol["governance"]["runtime_projection"]
            in {LEGACY_PROJECTION_VERSION, TYPED_RUNTIME_PROJECTION_VERSION}
        ]
        return tuple(sorted(projected, key=lambda item: item["stable_id"]))


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise PracticeContentError(f"{path}: could not read valid YAML: {exc}") from exc
    if not isinstance(document, dict):
        raise PracticeContentError(f"{path}: expected one YAML mapping.")
    return document


def _read_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PracticeContentError(f"{path}: could not read valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise PracticeContentError(f"{path}: expected one JSON object.")
    return document


@cache
def _compiled_schema_validator(
    schema_path: Path,
    _mtime_ns: int,
    _size: int,
) -> Draft202012Validator:
    schema = _read_json(schema_path)
    try:
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(
            schema,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
    except SchemaError as exc:
        raise PracticeContentError(f"{schema_path}: invalid JSON Schema: {exc.message}") from exc


def _validate_schema(document: dict[str, Any], schema_path: Path, document_path: Path) -> None:
    resolved_schema_path = schema_path.resolve()
    try:
        stat = resolved_schema_path.stat()
    except OSError as exc:
        raise PracticeContentError(f"{schema_path}: could not inspect JSON Schema: {exc}") from exc
    validator = _compiled_schema_validator(
        resolved_schema_path,
        stat.st_mtime_ns,
        stat.st_size,
    )
    try:
        validator.validate(document)
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path)
        suffix = f".{location}" if location else ""
        raise PracticeContentError(
            f"{document_path}{suffix}: schema validation failed: {exc.message}"
        ) from exc


def _require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PracticeContentError(f"{path}: expected a mapping.")
    return value


def _require_list(value: Any, path: str, *, allow_empty: bool = False) -> list[Any]:
    if not isinstance(value, list) or (not allow_empty and not value):
        qualifier = "" if allow_empty else " non-empty"
        raise PracticeContentError(f"{path}: expected a{qualifier} list.")
    return value


def _require_string(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        qualifier = "" if allow_empty else " non-empty"
        raise PracticeContentError(f"{path}: expected a{qualifier} string.")
    return value.strip()


def _require_keys(mapping: dict[str, Any], required: set[str], path: str) -> None:
    missing = sorted(required - set(mapping))
    if missing:
        raise PracticeContentError(f"{path}: missing required fields {missing}.")


def _index_registry(
    document: dict[str, Any],
    *,
    path: str,
    version: str,
    collection_key: str,
    id_key: str,
) -> dict[str, dict[str, Any]]:
    if document.get("schema_version") != version:
        raise PracticeContentError(
            f"{path}: unsupported schema version {document.get('schema_version')!r}; "
            f"expected {version!r}."
        )
    entries = _require_list(document.get(collection_key), f"{path}.{collection_key}")
    indexed: dict[str, dict[str, Any]] = {}
    for index, raw_entry in enumerate(entries):
        entry = _require_mapping(raw_entry, f"{path}.{collection_key}[{index}]")
        stable_id = _require_string(entry.get(id_key), f"{path}.{collection_key}[{index}].{id_key}")
        if stable_id in indexed:
            raise PracticeContentError(f"{path}: duplicate {id_key} {stable_id!r}.")
        indexed[stable_id] = entry
    return indexed


def _validate_unique_control_ids(
    document: dict[str, Any],
    *,
    path: Path,
    collection_key: str,
    id_key: str,
) -> None:
    entries = _require_list(document.get(collection_key), f"{path}.{collection_key}")
    ids = [entry[id_key] for entry in entries]
    if len(ids) != len(set(ids)):
        raise PracticeContentError(f"{path}: duplicate {id_key} values.")


def _canonical_content_hash(
    paths: list[Path],
    root: Path,
    manifest: dict[str, Any],
) -> str:
    digest = hashlib.sha256()
    manifest_projection = {key: value for key, value in manifest.items() if key != "content_hash"}
    digest.update(b"release_manifest.yaml\0")
    digest.update(
        json.dumps(
            manifest_projection,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )
    digest.update(b"\0")
    for path in sorted(paths):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _validate_protocol_shape(protocol: dict[str, Any], path: Path) -> None:
    required = {
        "schema_version",
        "protocol_version",
        "stable_id",
        "slug",
        "name",
        "parent_competency_id",
        "domain_id",
        "governance",
        "meaning_and_fit",
        "intervention",
        "evidence_and_scoring",
        "completion_and_review",
        "presentation",
    }
    _require_keys(protocol, required, str(path))
    if protocol["schema_version"] != PRACTICE_CONTENT_SCHEMA_VERSION:
        raise PracticeContentError(
            f"{path}: unsupported schema version {protocol['schema_version']!r}; "
            f"expected {PRACTICE_CONTENT_SCHEMA_VERSION!r}."
        )

    stable_id = _require_string(protocol["stable_id"], f"{path}.stable_id")
    if path.stem != stable_id:
        raise PracticeContentError(f"{path}: filename must equal its stable ID ({stable_id}.yaml).")
    for field in ("protocol_version", "slug", "name", "parent_competency_id", "domain_id"):
        _require_string(protocol[field], f"{path}.{field}")
    if path.parent.name != protocol["domain_id"]:
        raise PracticeContentError(
            f"{path}: protocol directory must match domain_id {protocol['domain_id']!r}."
        )

    governance = _require_mapping(protocol["governance"], f"{path}.governance")
    _require_keys(
        governance,
        {
            "availability",
            "editorial_status",
            "runtime_projection",
            "risk_class_id",
            "scoring_policy_id",
            "scoring_status",
            "source_ids",
            "authoring",
            "legacy_compatibility_exceptions",
            "deprecation",
        },
        f"{path}.governance",
    )
    if governance["availability"] not in {"active", "inactive"}:
        raise PracticeContentError(f"{path}.governance.availability: unsupported value.")
    if governance["runtime_projection"] not in {
        LEGACY_PROJECTION_VERSION,
        TYPED_RUNTIME_PROJECTION_VERSION,
        "none",
    }:
        raise PracticeContentError(f"{path}.governance.runtime_projection: unsupported value.")
    if governance["scoring_status"] not in {
        "eligible_inactive",
        "active",
        "shadow_only",
        "qualified_only",
        "non_scored",
    }:
        raise PracticeContentError(f"{path}.governance.scoring_status: unsupported value.")
    _require_list(governance["source_ids"], f"{path}.governance.source_ids")
    authoring = _require_mapping(governance["authoring"], f"{path}.governance.authoring")
    _require_keys(
        authoring,
        {
            "provenance",
            "content_review_status",
            "research_review_status",
            "safety_review_status",
            "accessibility_review_status",
            "originality_review_status",
            "ui_test_status",
            "last_reviewed",
            "known_gap_ids",
            "expert_review_ids",
        },
        f"{path}.governance.authoring",
    )
    _require_list(
        authoring["known_gap_ids"],
        f"{path}.governance.authoring.known_gap_ids",
        allow_empty=True,
    )
    _require_list(
        authoring["expert_review_ids"],
        f"{path}.governance.authoring.expert_review_ids",
        allow_empty=True,
    )
    _require_list(
        governance["legacy_compatibility_exceptions"],
        f"{path}.governance.legacy_compatibility_exceptions",
        allow_empty=True,
    )
    deprecation = _require_mapping(governance["deprecation"], f"{path}.governance.deprecation")
    _require_keys(deprecation, {"deprecated", "replaced_by"}, f"{path}.governance.deprecation")
    if not isinstance(deprecation["deprecated"], bool):
        raise PracticeContentError(f"{path}.governance.deprecation.deprecated: expected Boolean.")

    meaning = _require_mapping(protocol["meaning_and_fit"], f"{path}.meaning_and_fit")
    _require_keys(
        meaning,
        {
            "purpose",
            "why_recommended",
            "claims",
            "applicability_question",
            "not_applicable_behavior",
            "readiness_considerations",
            "opportunity_considerations",
            "prerequisites",
            "dependencies",
            "safe_alternatives",
            "role_conditions",
            "pathway_conditions",
            "worldview_conditions",
        },
        f"{path}.meaning_and_fit",
    )
    for field in (
        "purpose",
        "why_recommended",
        "applicability_question",
        "not_applicable_behavior",
        "readiness_considerations",
        "opportunity_considerations",
    ):
        _require_string(meaning[field], f"{path}.meaning_and_fit.{field}")
    for field in (
        "claims",
        "prerequisites",
        "dependencies",
        "safe_alternatives",
        "role_conditions",
        "pathway_conditions",
        "worldview_conditions",
    ):
        _require_list(
            meaning[field],
            f"{path}.meaning_and_fit.{field}",
            allow_empty=field in {"prerequisites", "dependencies", "role_conditions"},
        )

    intervention = _require_mapping(protocol["intervention"], f"{path}.intervention")
    _require_keys(
        intervention,
        {
            "protocol_class",
            "duration_days",
            "cadence",
            "setup",
            "privacy_and_boundaries",
            "expected_burden",
            "action_count_rationale",
            "foreseeable_misuse",
            "exclusions",
            "actions",
            "adaptations",
            "pause_conditions",
            "stop_conditions",
            "escalation_conditions",
            "professional_referral_conditions",
        },
        f"{path}.intervention",
    )
    for field in (
        "protocol_class",
        "cadence",
        "setup",
        "privacy_and_boundaries",
        "expected_burden",
    ):
        _require_string(intervention[field], f"{path}.intervention.{field}")
    duration_days = intervention["duration_days"]
    if not isinstance(duration_days, int) or not 1 <= duration_days <= 365:
        raise PracticeContentError(f"{path}.intervention.duration_days: expected 1..365.")
    _require_mapping(intervention["adaptations"], f"{path}.intervention.adaptations")
    action_count_rationale = intervention["action_count_rationale"]
    if action_count_rationale is not None:
        _require_string(
            action_count_rationale,
            f"{path}.intervention.action_count_rationale",
        )
    for field in (
        "foreseeable_misuse",
        "exclusions",
        "pause_conditions",
        "stop_conditions",
        "escalation_conditions",
        "professional_referral_conditions",
    ):
        _require_list(intervention[field], f"{path}.intervention.{field}")

    actions = _require_list(intervention["actions"], f"{path}.intervention.actions")
    if not 3 <= len(actions) <= 5 and action_count_rationale is None:
        raise PracticeContentError(
            f"{path}.intervention.action_count_rationale: required outside 3..5 actions."
        )
    if 3 <= len(actions) <= 5 and action_count_rationale is not None:
        raise PracticeContentError(
            f"{path}.intervention.action_count_rationale: omit for the normal 3..5 action range."
        )
    action_ids: set[str] = set()
    action_markers: set[str] = set()
    substantive_action_markers: set[str] = set()
    action_rule_versions: set[str] = set()
    sequences: list[int] = []
    for index, raw_action in enumerate(actions):
        action_path = f"{path}.intervention.actions[{index}]"
        action = _require_mapping(raw_action, action_path)
        _require_keys(
            action,
            {
                "stable_id",
                "sequence",
                "title",
                "instructions",
                "expected_time",
                "due_within_days",
                "evidence_rules",
            },
            action_path,
        )
        action_id = _require_string(action["stable_id"], f"{action_path}.stable_id")
        if action_id in action_ids:
            raise PracticeContentError(f"{path}: duplicate action stable ID {action_id!r}.")
        if not isinstance(action["sequence"], int):
            raise PracticeContentError(f"{action_path}.sequence: expected an integer.")
        if action_id != f"{stable_id}-A{action['sequence']}":
            raise PracticeContentError(
                f"{action_path}.stable_id: must equal {stable_id}-A{action['sequence']}."
            )
        action_ids.add(action_id)
        sequences.append(action["sequence"])
        for field in ("title", "instructions", "expected_time"):
            _require_string(action[field], f"{action_path}.{field}")
        due = action["due_within_days"]
        if due is not None and (not isinstance(due, int) or not 1 <= due <= duration_days):
            raise PracticeContentError(f"{action_path}.due_within_days: invalid due window.")
        rules = _require_mapping(action["evidence_rules"], f"{action_path}.evidence_rules")
        rule_version = rules.get("schema_version")
        action_rule_versions.add(rule_version)
        typed_identity = action.get("typed_evidence_identity")
        if rule_version == "practice-observation-v1":
            if typed_identity is not None:
                raise PracticeContentError(
                    f"{action_path}.typed_evidence_identity: legacy actions must not declare "
                    "a typed identity."
                )
            try:
                validate_evidence_rules(rules)
            except (EvidenceContractError, KeyError, TypeError) as exc:
                raise PracticeContentError(f"{action_path}.evidence_rules: {exc}") from exc
            action_markers.update(rules["primary_markers"])
            action_markers.update(rules["supporting_markers"])
            substantive_action_markers.update(rules["primary_markers"])
            substantive_action_markers.update(rules["supporting_markers"])
        elif rule_version == TYPED_EVIDENCE_RULES_VERSION:
            if (
                governance["runtime_projection"] != TYPED_RUNTIME_PROJECTION_VERSION
                or governance["availability"] != "active"
            ):
                raise PracticeContentError(
                    f"{action_path}.evidence_rules: typed rules require the active typed "
                    "runtime projection."
                )
            identity = _require_mapping(
                typed_identity,
                f"{action_path}.typed_evidence_identity",
            )
            expected_identity = {
                "protocol_stable_id": stable_id,
                "action_stable_id": action_id,
                "competency_stable_id": protocol["parent_competency_id"],
                "scoring_policy_id": governance["scoring_policy_id"],
            }
            if identity != expected_identity:
                raise PracticeContentError(
                    f"{action_path}.typed_evidence_identity: must exactly match "
                    f"{expected_identity}."
                )
            try:
                materialized = materialize_typed_evidence_rules(
                    rules,
                    load_typed_evidence_spec(),
                )
            except (TypedEvidenceContractError, KeyError, TypeError) as exc:
                raise PracticeContentError(f"{action_path}.evidence_rules: {exc}") from exc
            action_markers.update(
                measurement["measurement_id"] for measurement in materialized["measurements"]
            )
            substantive_action_markers.update(
                measurement["measurement_id"]
                for measurement in materialized["measurements"]
                if measurement["role"] in {"primary", "supporting"}
            )
        else:
            raise PracticeContentError(
                f"{action_path}.evidence_rules: unsupported schema version {rule_version!r}."
            )
    if sequences != list(range(1, len(actions) + 1)):
        raise PracticeContentError(f"{path}: action sequences must be contiguous from 1.")
    if len(action_rule_versions) != 1:
        raise PracticeContentError(f"{path}: one package cannot mix evidence-rule versions.")

    evidence = _require_mapping(protocol["evidence_and_scoring"], f"{path}.evidence_and_scoring")
    _require_keys(
        evidence,
        {
            "accepted_evidence_types",
            "observation_contract_version",
            "check_in_fields",
            "adverse_or_contradictory_indicators",
            "independence_rule",
            "context_transfer_rule",
            "repetition_rule",
            "recency_rule",
            "performance_rubric",
            "evidence_quality_rubric",
            "scoring_eligibility",
            "competency_contribution",
            "canonical_lever_allocation",
            "recommendation_target_lever_ids",
            "minimum_evidence_before_state_update",
            "withholding_conditions",
        },
        f"{path}.evidence_and_scoring",
    )
    observation_contract = evidence["observation_contract_version"]
    if observation_contract not in {"practice-observation-v1", TYPED_EVIDENCE_RULES_VERSION}:
        raise PracticeContentError(
            f"{path}.evidence_and_scoring.observation_contract_version: "
            "unsupported evidence-rule version."
        )
    if action_rule_versions != {observation_contract}:
        raise PracticeContentError(
            f"{path}: action evidence-rule version must match observation_contract_version."
        )
    if observation_contract == TYPED_EVIDENCE_RULES_VERSION and (
        governance["runtime_projection"] != TYPED_RUNTIME_PROJECTION_VERSION
        or governance["availability"] != "active"
    ):
        raise PracticeContentError(
            f"{path}: typed evidence must use the active typed runtime projection."
        )
    check_in_fields = _require_list(
        evidence["check_in_fields"], f"{path}.evidence_and_scoring.check_in_fields"
    )
    invalid_fields = (
        sorted(set(check_in_fields) - ALLOWED_CHECK_IN_FIELDS)
        if observation_contract == "practice-observation-v1"
        else []
    )
    if invalid_fields:
        raise PracticeContentError(
            f"{path}.evidence_and_scoring.check_in_fields: "
            f"unknown observation fields {invalid_fields}."
        )
    if (
        observation_contract == TYPED_EVIDENCE_RULES_VERSION
        and set(check_in_fields) != action_markers
    ):
        raise PracticeContentError(
            f"{path}.evidence_and_scoring.check_in_fields: typed fields must exactly "
            f"match action evidence markers; fields={sorted(check_in_fields)}, "
            f"markers={sorted(action_markers)}."
        )
    uncollectable_markers = action_markers - set(check_in_fields)
    declared_uncollectable: set[str] = set()
    for exception in governance["legacy_compatibility_exceptions"]:
        if exception["category"] == "uncollectable_action_marker":
            declared_uncollectable.update(exception["affected_markers"])
    if uncollectable_markers != declared_uncollectable:
        raise PracticeContentError(
            f"{path}: action markers outside check_in_fields must exactly match declared "
            f"legacy exceptions; markers={sorted(uncollectable_markers)}, "
            f"declared={sorted(declared_uncollectable)}."
        )
    for field in (
        "accepted_evidence_types",
        "adverse_or_contradictory_indicators",
        "recommendation_target_lever_ids",
        "withholding_conditions",
    ):
        _require_list(evidence[field], f"{path}.evidence_and_scoring.{field}")
    for field in (
        "independence_rule",
        "context_transfer_rule",
        "repetition_rule",
        "recency_rule",
        "performance_rubric",
        "evidence_quality_rubric",
        "scoring_eligibility",
        "competency_contribution",
        "canonical_lever_allocation",
        "minimum_evidence_before_state_update",
    ):
        _require_string(evidence[field], f"{path}.evidence_and_scoring.{field}")

    review = _require_mapping(protocol["completion_and_review"], f"{path}.completion_and_review")
    _require_keys(
        review,
        {
            "completion_criteria",
            "completion_rules",
            "mastery_disclaimer",
            "progression_criteria",
            "transfer_limit",
            "reflection",
            "review_guidance",
            "evidence_examples",
        },
        f"{path}.completion_and_review",
    )
    _require_list(
        review["completion_criteria"], f"{path}.completion_and_review.completion_criteria"
    )
    completion_rules = _require_mapping(
        review["completion_rules"], f"{path}.completion_and_review.completion_rules"
    )
    minimum_completed = completion_rules.get("minimum_completed")
    markers = completion_rules.get("substantive_markers")
    marker_mode = completion_rules.get("marker_mode", "any")
    if (
        not isinstance(minimum_completed, int)
        or not 1 <= minimum_completed <= len(actions)
        or not isinstance(markers, list)
        or not markers
        or (
            observation_contract == "practice-observation-v1"
            and set(markers) - ALLOWED_OBSERVATION_FIELDS
        )
        or marker_mode not in {"any", "all"}
    ):
        raise PracticeContentError(f"{path}.completion_and_review.completion_rules: invalid.")
    if not set(markers).issubset(substantive_action_markers):
        raise PracticeContentError(
            f"{path}.completion_and_review.completion_rules: substantive markers must "
            "appear in at least one action evidence rule."
        )
    for field in ("mastery_disclaimer", "progression_criteria", "transfer_limit"):
        _require_string(review[field], f"{path}.completion_and_review.{field}")
    reflection = _require_mapping(review["reflection"], f"{path}.completion_and_review.reflection")
    _require_keys(reflection, {"before", "during", "after"}, f"{path}.reflection")
    for field in ("before", "during", "after"):
        _require_string(reflection[field], f"{path}.completion_and_review.reflection.{field}")
    guidance = _require_mapping(
        review["review_guidance"], f"{path}.completion_and_review.review_guidance"
    )
    _require_keys(guidance, {"repeat", "adapt", "stop", "escalate"}, f"{path}.review_guidance")
    examples = _require_mapping(
        review["evidence_examples"], f"{path}.completion_and_review.evidence_examples"
    )
    _require_keys(
        examples,
        {"supportive", "mixed", "contradictory", "inconclusive"},
        f"{path}.evidence_examples",
    )

    presentation = _require_mapping(protocol["presentation"], f"{path}.presentation")
    _require_keys(
        presentation,
        {
            "setup_copy",
            "check_in_labels",
            "completion_copy",
            "plain_language_evidence",
            "display_order",
        },
        f"{path}.presentation",
    )
    setup_copy = _require_mapping(
        presentation["setup_copy"],
        f"{path}.presentation.setup_copy",
    )
    legacy_labels = setup_copy.get("check_in_labels")
    if legacy_labels is not None:
        legacy_labels = _require_mapping(
            legacy_labels,
            f"{path}.presentation.setup_copy.check_in_labels",
        )
        unknown_legacy_labels = sorted(set(legacy_labels) - set(check_in_fields))
        if unknown_legacy_labels:
            raise PracticeContentError(
                f"{path}.presentation.setup_copy.check_in_labels: unknown fields "
                f"{unknown_legacy_labels}."
            )
    check_in_labels = _require_mapping(
        presentation["check_in_labels"],
        f"{path}.presentation.check_in_labels",
    )
    if set(check_in_labels) != set(check_in_fields):
        raise PracticeContentError(
            f"{path}.presentation.check_in_labels: keys must exactly match check_in_fields."
        )
    for marker, label in check_in_labels.items():
        _require_string(label, f"{path}.presentation.check_in_labels.{marker}")
    for field in ("completion_copy", "plain_language_evidence"):
        _require_string(presentation[field], f"{path}.presentation.{field}")
    if not isinstance(presentation["display_order"], int):
        raise PracticeContentError(f"{path}.presentation.display_order: expected an integer.")


def _validate_source_locators(
    base_dir: Path,
    sources: dict[str, dict[str, Any]],
) -> None:
    resolved_base = base_dir.resolve()
    for source_id, source in sources.items():
        locator = source["locator"]
        locator_kind = source["locator_kind"]
        expected_hash = source["content_sha256"]
        if locator_kind == "repository_path":
            relative = Path(locator)
            if relative.is_absolute() or ".." in relative.parts:
                raise PracticeContentError(
                    f"{source_id}: repository source locator must be a safe relative path."
                )
            resolved_path = (resolved_base / relative).resolve()
            try:
                resolved_path.relative_to(resolved_base)
            except ValueError as exc:
                raise PracticeContentError(
                    f"{source_id}: repository source locator escapes the repository."
                ) from exc
            if not resolved_path.is_file():
                raise PracticeContentError(
                    f"{source_id}: repository source does not exist: {locator}."
                )
            actual_hash = hashlib.sha256(resolved_path.read_bytes()).hexdigest()
            if expected_hash != actual_hash:
                raise PracticeContentError(
                    f"{source_id}: repository source hash drift; expected "
                    f"{expected_hash!r}, calculated {actual_hash!r}."
                )
        elif locator_kind == "external_url":
            parsed = urlparse(locator)
            if parsed.scheme != "https" or not parsed.netloc:
                raise PracticeContentError(f"{source_id}: external sources require an HTTPS URL.")
            if source["date_accessed"] is None:
                raise PracticeContentError(f"{source_id}: external sources require date_accessed.")
        elif expected_hash is not None:
            raise PracticeContentError(
                f"{source_id}: bibliographic references must not claim a file hash."
            )


def _sources_complete(
    protocol: dict[str, Any],
    research_gaps: dict[str, dict[str, Any]],
) -> bool:
    authoring = protocol["governance"]["authoring"]
    if authoring["research_review_status"] != "complete":
        return False
    applicable_gaps = {
        gap_id
        for gap_id, gap in research_gaps.items()
        if gap["scope"] in {"full_catalog", protocol["stable_id"]}
    }
    return not any(
        research_gaps[gap_id]["status"] != "resolved"
        and "source_complete" in research_gaps[gap_id]["blocking_gates"]
        for gap_id in applicable_gaps
    )


def _release_blockers(
    protocol: dict[str, Any],
    *,
    sources: dict[str, dict[str, Any]],
    risk_classes: dict[str, dict[str, Any]],
    research_gaps: dict[str, dict[str, Any]],
    expert_reviews: dict[str, dict[str, Any]],
) -> list[str]:
    del sources  # Claim/source integrity is validated independently.
    stable_id = protocol["stable_id"]
    governance = protocol["governance"]
    authoring = governance["authoring"]
    review_fields = (
        "content_review_status",
        "research_review_status",
        "safety_review_status",
        "accessibility_review_status",
        "originality_review_status",
    )
    blockers = [
        f"{field}:{authoring[field]}" for field in review_fields if authoring[field] != "complete"
    ]
    if authoring["ui_test_status"] not in {"complete", "not_applicable"}:
        blockers.append(f"ui_test_status:{authoring['ui_test_status']}")
    if authoring["last_reviewed"] is None:
        blockers.append("last_reviewed:missing")
    applicable_gap_ids = {
        gap_id
        for gap_id, gap in research_gaps.items()
        if gap["scope"] in {"full_catalog", stable_id}
    }
    applicable_review_ids = {
        review_id
        for review_id, review in expert_reviews.items()
        if review["scope"] in {"full_catalog", stable_id}
    }
    for gap_id in applicable_gap_ids:
        gap = research_gaps[gap_id]
        if gap["status"] != "resolved" and {
            "source_complete",
            "release_candidate",
        }.intersection(gap["blocking_gates"]):
            blockers.append(f"research_gap:{gap_id}:{gap['status']}")
    for review_id in applicable_review_ids:
        review = expert_reviews[review_id]
        if review["status"] != "complete" and {
            "safety_review_complete",
            "release_candidate",
        }.intersection(review["blocking_gates"]):
            blockers.append(f"expert_review:{review_id}:{review['status']}")
    risk = risk_classes[governance["risk_class_id"]]
    if risk["specialist_review_required"]:
        completed_scoped_review = any(
            review["scope"] == stable_id
            and review["review_type"] == "specialist_safety"
            and review["status"] == "complete"
            for review in (expert_reviews[review_id] for review_id in applicable_review_ids)
        )
        if not completed_scoped_review:
            blockers.append("specialist_review:missing")
    if not _sources_complete(protocol, research_gaps):
        blockers.append("sources:incomplete")
    return sorted(set(blockers))


def protocol_release_blockers(
    bundle: PracticeContentBundle,
    protocol: dict[str, Any],
) -> tuple[str, ...]:
    return tuple(
        _release_blockers(
            protocol,
            sources=bundle.sources,
            risk_classes=bundle.risk_classes,
            research_gaps=bundle.research_gaps,
            expert_reviews=bundle.expert_reviews,
        )
    )


def protocol_sources_complete(
    bundle: PracticeContentBundle,
    protocol: dict[str, Any],
) -> bool:
    return _sources_complete(protocol, bundle.research_gaps)


def allowed_scoring_statuses_for_effect(state_effect: str) -> frozenset[str]:
    try:
        return {
            "eligible_if_activated": frozenset({"eligible_inactive", "active"}),
            "shadow_only": frozenset({"shadow_only"}),
            "qualified_update_only": frozenset({"qualified_only"}),
            "no_score_update": frozenset({"non_scored"}),
        }[state_effect]
    except KeyError as exc:
        raise PracticeContentError(
            f"Unsupported scoring policy state effect {state_effect!r}."
        ) from exc


def _validate_cross_references(
    protocols: tuple[dict[str, Any], ...],
    *,
    sources: dict[str, dict[str, Any]],
    risk_classes: dict[str, dict[str, Any]],
    scoring_policies: dict[str, dict[str, Any]],
    protocol_families: dict[str, dict[str, Any]],
    activation_entries: dict[str, dict[str, Any]],
    research_gaps: dict[str, dict[str, Any]],
    expert_reviews: dict[str, dict[str, Any]],
) -> None:
    protocol_ids = [protocol["stable_id"] for protocol in protocols]
    if len(protocol_ids) != len(set(protocol_ids)):
        raise PracticeContentError("Protocol stable IDs must be unique.")
    protocol_by_id = {protocol["stable_id"]: protocol for protocol in protocols}
    slugs = [protocol["slug"] for protocol in protocols]
    if len(slugs) != len(set(slugs)):
        raise PracticeContentError("Protocol slugs must be unique.")
    protocols_by_parent: dict[str, list[dict[str, Any]]] = {}
    for protocol in protocols:
        protocols_by_parent.setdefault(protocol["parent_competency_id"], []).append(protocol)
    for parent_id, parent_protocols in protocols_by_parent.items():
        current = [
            protocol
            for protocol in parent_protocols
            if not protocol["governance"]["deprecation"]["deprecated"]
        ]
        if len(current) != 1:
            raise PracticeContentError(
                f"{parent_id}: exactly one non-deprecated protocol is required."
            )
    display_orders = [
        protocol["presentation"]["display_order"]
        for protocol in protocols
        if not protocol["governance"]["deprecation"]["deprecated"]
    ]
    if len(display_orders) != len(set(display_orders)):
        raise PracticeContentError("Current protocol display orders must be unique.")
    if set(activation_entries) != set(protocol_ids):
        raise PracticeContentError(
            "Activation ledger coverage must exactly match the canonical protocol packages."
        )
    if set(REQUIRED_SCORING_POLICY_EFFECTS) - set(scoring_policies):
        raise PracticeContentError("Scoring policy registry is missing required policies.")
    for policy_id, expected_effect in REQUIRED_SCORING_POLICY_EFFECTS.items():
        if scoring_policies[policy_id]["state_effect"] != expected_effect:
            raise PracticeContentError(
                f"{policy_id}: reviewed scoring-policy state effect changed."
            )
    if set(risk_classes) != set(REQUIRED_RISK_BOUNDARIES):
        raise PracticeContentError("Risk taxonomy must contain exactly LOW, MODERATE, and HIGH.")
    for risk_id, boundary in REQUIRED_RISK_BOUNDARIES.items():
        risk = risk_classes[risk_id]
        if (
            risk["pre_review_scoring_ceiling"] != boundary["ceiling"]
            or risk["specialist_review_required"] is not boundary["specialist_review_required"]
            or not boundary["sections"].issubset(risk["required_safety_sections"])
        ):
            raise PracticeContentError(f"{risk_id}: reviewed risk boundary changed.")

    action_by_id: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    evidence_groups: dict[str, list[str]] = {}
    for protocol in protocols:
        for action in protocol["intervention"]["actions"]:
            action_by_id[action["stable_id"]] = (protocol, action)
            payload = json.dumps(
                action["evidence_rules"],
                sort_keys=True,
                separators=(",", ":"),
            )
            evidence_groups.setdefault(payload, []).append(action["stable_id"])
    exception_ids: set[str] = set()
    declared_duplicate_groups: set[tuple[str, ...]] = set()
    for protocol in protocols:
        for exception in protocol["governance"]["legacy_compatibility_exceptions"]:
            exception_id = exception["exception_id"]
            if exception_id in exception_ids:
                raise PracticeContentError(
                    f"Duplicate legacy compatibility exception {exception_id!r}."
                )
            exception_ids.add(exception_id)
            affected = tuple(sorted(exception["affected_action_ids"]))
            unknown_actions = sorted(set(affected) - set(action_by_id))
            if unknown_actions:
                raise PracticeContentError(
                    f"{exception_id}: unknown affected actions {unknown_actions}."
                )
            if not any(
                action_id.startswith(f"{protocol['stable_id']}-A") for action_id in affected
            ):
                raise PracticeContentError(
                    f"{exception_id}: declaration must be owned by an affected protocol."
                )
            if exception["category"] == "duplicate_evidence_rules":
                if len(affected) < 2 or exception["affected_markers"]:
                    raise PracticeContentError(
                        f"{exception_id}: duplicate-rule exceptions require at least two "
                        "actions and no affected markers."
                    )
                payloads = {
                    json.dumps(
                        action_by_id[action_id][1]["evidence_rules"],
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    for action_id in affected
                }
                if len(payloads) != 1:
                    raise PracticeContentError(
                        f"{exception_id}: affected actions do not have identical rules."
                    )
                declared_duplicate_groups.add(affected)
            else:
                if len(affected) != 1 or not exception["affected_markers"]:
                    raise PracticeContentError(
                        f"{exception_id}: uncollectable-marker exceptions require one "
                        "action and at least one marker."
                    )
                affected_protocol, affected_action = action_by_id[affected[0]]
                action_markers = {
                    *affected_action["evidence_rules"]["primary_markers"],
                    *affected_action["evidence_rules"]["supporting_markers"],
                }
                actual_uncollectable = action_markers - set(
                    affected_protocol["evidence_and_scoring"]["check_in_fields"]
                )
                if set(exception["affected_markers"]) != actual_uncollectable:
                    raise PracticeContentError(
                        f"{exception_id}: affected markers do not exactly match the "
                        "uncollectable legacy markers."
                    )
            if protocol["governance"]["runtime_projection"] != LEGACY_PROJECTION_VERSION:
                raise PracticeContentError(
                    f"{exception_id}: compatibility exceptions are limited to legacy projections."
                )
            if any(
                action_by_id[action_id][0]["stable_id"] not in FROZEN_LEGACY_PROTOCOL_IDS
                or action_by_id[action_id][0]["governance"]["runtime_projection"]
                != LEGACY_PROJECTION_VERSION
                for action_id in affected
            ):
                raise PracticeContentError(
                    f"{exception_id}: every affected action must belong to the frozen legacy slice."
                )
    actual_duplicate_groups = {
        tuple(sorted(action_ids)) for action_ids in evidence_groups.values() if len(action_ids) > 1
    }
    if actual_duplicate_groups != declared_duplicate_groups:
        raise PracticeContentError(
            "Duplicate evidence-rule groups must exactly match declared legacy exceptions."
        )
    if declared_duplicate_groups != FROZEN_LEGACY_DUPLICATE_RULE_GROUPS:
        raise PracticeContentError(
            "Legacy duplicate-rule exceptions changed from the reviewed frozen groups."
        )
    declared_uncollectable_markers = {
        (exception["affected_action_ids"][0], marker)
        for protocol in protocols
        for exception in protocol["governance"]["legacy_compatibility_exceptions"]
        if exception["category"] == "uncollectable_action_marker"
        for marker in exception["affected_markers"]
    }
    if declared_uncollectable_markers != FROZEN_LEGACY_UNCOLLECTABLE_MARKERS:
        raise PracticeContentError(
            "Legacy uncollectable-marker exceptions changed from the reviewed frozen case."
        )

    for gap in research_gaps.values():
        if gap["scope"] != "full_catalog" and gap["scope"] not in protocol_by_id:
            raise PracticeContentError(
                f"{gap['gap_id']}: research gap scope is not a canonical protocol."
            )
    for review in expert_reviews.values():
        if review["scope"] != "full_catalog" and review["scope"] not in protocol_by_id:
            raise PracticeContentError(
                f"{review['review_id']}: expert review scope is not a canonical protocol."
            )
        completed_roles = set(review["completed_roles"])
        required_roles = set(review["required_roles"])
        if review["status"] == "complete":
            if (
                not required_roles.issubset(completed_roles)
                or review["completed_on"] is None
                or review["decision_reference"] is None
            ):
                raise PracticeContentError(
                    f"{review['review_id']}: completed review lacks roles, date, or decision."
                )
        elif review["status"] in {"pending", "deferred"} and (
            completed_roles
            or review["completed_on"] is not None
            or review["decision_reference"] is not None
        ):
            raise PracticeContentError(
                f"{review['review_id']}: incomplete review claims completion evidence."
            )

    for source_id, source in sources.items():
        actual_protocols = {
            protocol["stable_id"]
            for protocol in protocols
            if source_id in protocol["governance"]["source_ids"]
        }
        if set(source["applicable_protocol_ids"]) != actual_protocols:
            raise PracticeContentError(
                f"{source_id}: applicable_protocol_ids must exactly match package references."
            )
        actual_competencies = {
            protocol_by_id[protocol_id]["parent_competency_id"] for protocol_id in actual_protocols
        }
        if set(source["applicable_competency_ids"]) != actual_competencies:
            raise PracticeContentError(
                f"{source_id}: applicable_competency_ids must exactly match package parents."
            )

    for protocol in protocols:
        stable_id = protocol["stable_id"]
        governance = protocol["governance"]
        authoring = governance["authoring"]
        evidence = protocol["evidence_and_scoring"]
        family_id = protocol["intervention"]["protocol_class"]
        missing_gaps = sorted(set(authoring["known_gap_ids"]) - set(research_gaps))
        missing_reviews = sorted(set(authoring["expert_review_ids"]) - set(expert_reviews))
        if missing_gaps or missing_reviews:
            raise PracticeContentError(
                f"{stable_id}: unknown governance controls; "
                f"gaps={missing_gaps}, reviews={missing_reviews}."
            )
        for gap_id in authoring["known_gap_ids"]:
            if research_gaps[gap_id]["scope"] not in {"full_catalog", stable_id}:
                raise PracticeContentError(
                    f"{stable_id}: research gap {gap_id} has incompatible scope."
                )
        for review_id in authoring["expert_review_ids"]:
            if expert_reviews[review_id]["scope"] not in {"full_catalog", stable_id}:
                raise PracticeContentError(
                    f"{stable_id}: expert review {review_id} has incompatible scope."
                )
        scoped_gap_ids = {
            gap["gap_id"] for gap in research_gaps.values() if gap["scope"] == stable_id
        }
        global_gap_ids = {
            gap["gap_id"] for gap in research_gaps.values() if gap["scope"] == "full_catalog"
        }
        scoped_review_ids = {
            review["review_id"]
            for review in expert_reviews.values()
            if review["scope"] == stable_id
        }
        global_review_ids = {
            review["review_id"]
            for review in expert_reviews.values()
            if review["scope"] == "full_catalog"
        }
        if not (scoped_gap_ids | global_gap_ids).issubset(authoring["known_gap_ids"]):
            raise PracticeContentError(
                f"{stable_id}: applicable research gaps must be linked from authoring."
            )
        if not (scoped_review_ids | global_review_ids).issubset(authoring["expert_review_ids"]):
            raise PracticeContentError(
                f"{stable_id}: applicable expert reviews must be linked from authoring."
            )

        missing_sources = sorted(set(governance["source_ids"]) - set(sources))
        if missing_sources:
            raise PracticeContentError(f"{stable_id}: unknown source IDs {missing_sources}.")
        for claim in protocol["meaning_and_fit"]["claims"]:
            claim_sources = set(claim["source_ids"])
            missing_claim_sources = sorted(claim_sources - set(sources))
            if missing_claim_sources:
                raise PracticeContentError(
                    f"{stable_id}: claim references unknown source IDs {missing_claim_sources}."
                )
            if not claim_sources.issubset(governance["source_ids"]):
                raise PracticeContentError(
                    f"{stable_id}: claim sources must be included in governance.source_ids."
                )
            incompatible_sources = sorted(
                source_id
                for source_id in claim_sources
                if sources[source_id]["claim_classification"] != claim["classification"]
            )
            if incompatible_sources:
                raise PracticeContentError(
                    f"{stable_id}: claim classification does not match sources "
                    f"{incompatible_sources}."
                )
        if governance["risk_class_id"] not in risk_classes:
            raise PracticeContentError(
                f"{stable_id}: unknown risk class {governance['risk_class_id']!r}."
            )
        if governance["scoring_policy_id"] not in scoring_policies:
            raise PracticeContentError(
                f"{stable_id}: unknown scoring policy {governance['scoring_policy_id']!r}."
            )
        if family_id not in protocol_families:
            raise PracticeContentError(f"{stable_id}: unknown protocol family {family_id!r}.")

        deprecation = governance["deprecation"]
        replacement_id = deprecation["replaced_by"]
        if deprecation["deprecated"]:
            if (
                replacement_id is None
                or replacement_id == stable_id
                or replacement_id not in protocol_by_id
            ):
                raise PracticeContentError(
                    f"{stable_id}: deprecated protocols require a known non-self replacement."
                )
            replacement = protocol_by_id[replacement_id]
            if (
                replacement["parent_competency_id"] != protocol["parent_competency_id"]
                or replacement["governance"]["deprecation"]["deprecated"]
            ):
                raise PracticeContentError(
                    f"{stable_id}: replacement must be the current protocol for the same parent."
                )
            if (
                governance["availability"] != "inactive"
                or governance["runtime_projection"] != "none"
            ):
                raise PracticeContentError(
                    f"{stable_id}: deprecated protocols must be inactive and unprojected."
                )
        elif replacement_id is not None:
            raise PracticeContentError(
                f"{stable_id}: current protocols must not declare replaced_by."
            )

        risk = risk_classes[governance["risk_class_id"]]
        intervention = protocol["intervention"]
        safety_fields = {
            "privacy_and_boundaries": intervention["privacy_and_boundaries"],
            "adaptations": intervention["adaptations"],
            "foreseeable_misuse": intervention["foreseeable_misuse"],
            "exclusions": intervention["exclusions"],
            "stop_conditions": intervention["stop_conditions"],
            "escalation_conditions": intervention["escalation_conditions"],
            "qualified_referral_boundary": intervention["professional_referral_conditions"],
        }
        missing_safety_sections = sorted(set(risk["required_safety_sections"]) - set(safety_fields))
        if missing_safety_sections:
            raise PracticeContentError(
                f"{stable_id}: risk class requires unknown safety sections "
                f"{missing_safety_sections}."
            )

        scoring_policy = scoring_policies[governance["scoring_policy_id"]]
        allowed_scoring_statuses = allowed_scoring_statuses_for_effect(
            scoring_policy["state_effect"]
        )
        if governance["scoring_status"] not in allowed_scoring_statuses:
            raise PracticeContentError(
                f"{stable_id}: package scoring status does not match its policy."
            )

        activation = activation_entries[stable_id]
        if activation.get("scoring_policy_id") != governance["scoring_policy_id"]:
            raise PracticeContentError(
                f"{stable_id}: activation and package scoring policy differ."
            )
        score_active = activation.get("score_active")
        if not isinstance(score_active, bool):
            raise PracticeContentError(f"{stable_id}: activation score_active must be Boolean.")
        activation_status = activation.get("activation_status")
        if score_active and (
            activation_status != "active" or governance["scoring_status"] != "active"
        ):
            raise PracticeContentError(f"{stable_id}: active scoring status is inconsistent.")
        if not score_active and (
            activation_status == "active" or governance["scoring_status"] == "active"
        ):
            raise PracticeContentError(f"{stable_id}: package claims unledgered score activation.")
        if (
            activation_status == "qualified_only"
            and governance["scoring_status"] != "qualified_only"
        ):
            raise PracticeContentError(
                f"{stable_id}: qualified-only ledger and package statuses differ."
            )
        if score_active and not activation.get("approved_contract"):
            raise PracticeContentError(f"{stable_id}: score activation lacks an approved contract.")
        if not score_active and activation.get("approved_contract"):
            raise PracticeContentError(
                f"{stable_id}: inactive scoring must not claim an approved contract."
            )
        if score_active and (
            activation["scoring_policy_id"] != ACTIVE_SCORING_POLICY_ID
            or activation["approved_contract"] != ACTIVE_SCORE_STATE_CONTRACT
            or activation["decision_reference"] != ACTIVE_DECISION_REFERENCE
            or activation["shadow_test_status"] != "accepted_and_activated"
        ):
            raise PracticeContentError(f"{stable_id}: active scoring contract does not match M6F.")
        if evidence["canonical_lever_allocation"] != "parent_competency_mapping":
            raise PracticeContentError(
                f"{stable_id}: canonical lever allocation must remain parent_competency_mapping."
            )
        if governance["editorial_status"] == "release_candidate":
            blockers = _release_blockers(
                protocol,
                sources=sources,
                risk_classes=risk_classes,
                research_gaps=research_gaps,
                expert_reviews=expert_reviews,
            )
            if blockers:
                raise PracticeContentError(
                    f"{stable_id}: release candidate has unresolved gates {blockers}."
                )


def _manifest_relative_path(root: Path, raw_path: Any, *, expected_prefix: str) -> Path:
    value = _require_string(raw_path, "release_manifest.content_files")
    relative = Path(value)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not relative.parts
        or relative.parts[0] != expected_prefix
    ):
        raise PracticeContentError(f"release_manifest: unsafe or misplaced content path {value!r}.")
    path = root / relative
    if not path.is_file():
        raise PracticeContentError(f"release_manifest: listed file does not exist: {value}.")
    return path


def _load_practice_content_bundle(base_dir: Path) -> PracticeContentBundle:
    root = base_dir / "data" / "practices"
    manifest_path = root / "release_manifest.yaml"
    manifest = _read_yaml(manifest_path)
    release_schema_path = root / "schema" / "release_manifest_v1.schema.json"
    _validate_schema(manifest, release_schema_path, manifest_path)
    if manifest.get("schema_version") != RELEASE_MANIFEST_VERSION:
        raise PracticeContentError(
            f"{manifest_path}: unsupported schema version {manifest.get('schema_version')!r}."
        )

    raw_protocol_files = _require_list(
        manifest.get("protocol_files"), f"{manifest_path}.protocol_files"
    )
    protocol_paths = sorted(
        _manifest_relative_path(root, item, expected_prefix="protocols")
        for item in raw_protocol_files
    )
    if len(protocol_paths) != len(set(protocol_paths)):
        raise PracticeContentError(f"{manifest_path}: protocol paths must be unique.")
    if not protocol_paths:
        raise PracticeContentError(f"{root / 'protocols'}: no canonical protocols found.")
    discovered_protocols = set((root / "protocols").rglob("*.yaml"))
    if discovered_protocols != set(protocol_paths):
        unlisted = sorted(
            str(path.relative_to(root)) for path in discovered_protocols - set(protocol_paths)
        )
        missing = sorted(
            str(path.relative_to(root)) for path in set(protocol_paths) - discovered_protocols
        )
        raise PracticeContentError(
            f"{manifest_path}: protocol manifest coverage drift; "
            f"unlisted={unlisted}, missing={missing}."
        )

    protocols: list[dict[str, Any]] = []
    protocol_schema_path = root / "schema" / "practice_content_v1.schema.json"
    for path in protocol_paths:
        protocol = _read_yaml(path)
        _validate_schema(protocol, protocol_schema_path, path)
        _validate_protocol_shape(protocol, path)
        protocols.append(protocol)

    source_path = root / "registries" / "source_registry.yaml"
    risk_path = root / "registries" / "risk_taxonomy.yaml"
    scoring_path = root / "registries" / "scoring_policy_registry.yaml"
    family_path = root / "registries" / "protocol_families.yaml"
    activation_path = root / "registries" / "activation_ledger.yaml"
    research_path = root / "research_gaps.yaml"
    expert_path = root / "expert_review_queue.yaml"
    registry_schemas = {
        source_path: root / "schema" / "source_registry_v1.schema.json",
        risk_path: root / "schema" / "risk_taxonomy_v1.schema.json",
        scoring_path: root / "schema" / "scoring_policy_registry_v1.schema.json",
        family_path: root / "schema" / "protocol_family_registry_v1.schema.json",
        activation_path: root / "schema" / "activation_ledger_v1.schema.json",
    }
    registry_documents = {path: _read_yaml(path) for path in registry_schemas}
    for document_path, schema_path in registry_schemas.items():
        _validate_schema(registry_documents[document_path], schema_path, document_path)
    research_schema_path = root / "schema" / "research_gaps_v1.schema.json"
    expert_schema_path = root / "schema" / "expert_review_queue_v1.schema.json"
    research_document = _read_yaml(research_path)
    expert_document = _read_yaml(expert_path)
    _validate_schema(research_document, research_schema_path, research_path)
    _validate_schema(expert_document, expert_schema_path, expert_path)
    _validate_unique_control_ids(
        research_document,
        path=research_path,
        collection_key="gaps",
        id_key="gap_id",
    )
    _validate_unique_control_ids(
        expert_document,
        path=expert_path,
        collection_key="reviews",
        id_key="review_id",
    )

    sources = _index_registry(
        registry_documents[source_path],
        path=str(source_path),
        version=SOURCE_REGISTRY_VERSION,
        collection_key="sources",
        id_key="source_id",
    )
    risk_classes = _index_registry(
        registry_documents[risk_path],
        path=str(risk_path),
        version=RISK_TAXONOMY_VERSION,
        collection_key="risk_classes",
        id_key="risk_class_id",
    )
    scoring_policies = _index_registry(
        registry_documents[scoring_path],
        path=str(scoring_path),
        version=SCORING_POLICY_REGISTRY_VERSION,
        collection_key="policies",
        id_key="policy_id",
    )
    protocol_families = _index_registry(
        registry_documents[family_path],
        path=str(family_path),
        version=PROTOCOL_FAMILY_REGISTRY_VERSION,
        collection_key="families",
        id_key="family_id",
    )
    activation_entries = _index_registry(
        registry_documents[activation_path],
        path=str(activation_path),
        version=ACTIVATION_LEDGER_VERSION,
        collection_key="activations",
        id_key="protocol_stable_id",
    )
    research_gaps = _index_registry(
        research_document,
        path=str(research_path),
        version=RESEARCH_GAP_REGISTRY_VERSION,
        collection_key="gaps",
        id_key="gap_id",
    )
    expert_reviews = _index_registry(
        expert_document,
        path=str(expert_path),
        version=EXPERT_REVIEW_REGISTRY_VERSION,
        collection_key="reviews",
        id_key="review_id",
    )
    _validate_source_locators(base_dir, sources)
    protocol_tuple = tuple(protocols)
    _validate_cross_references(
        protocol_tuple,
        sources=sources,
        risk_classes=risk_classes,
        scoring_policies=scoring_policies,
        protocol_families=protocol_families,
        activation_entries=activation_entries,
        research_gaps=research_gaps,
        expert_reviews=expert_reviews,
    )

    raw_content_files = _require_list(
        manifest.get("content_files"), f"{manifest_path}.content_files"
    )
    content_paths = [
        _manifest_relative_path(root, item, expected_prefix=Path(item).parts[0])
        for item in raw_content_files
    ]
    if len(content_paths) != len(set(content_paths)):
        raise PracticeContentError(f"{manifest_path}: content paths must be unique.")
    required_content_paths = {
        *protocol_paths,
        *registry_schemas,
        *registry_schemas.values(),
        protocol_schema_path,
        release_schema_path,
        research_schema_path,
        expert_schema_path,
        research_path,
        expert_path,
    }
    if set(content_paths) != required_content_paths:
        raise PracticeContentError(
            f"{manifest_path}: content_files must exactly enumerate canonical inputs."
        )
    discovered_content_paths = {
        path
        for path in root.rglob("*")
        if path.is_file() and path != manifest_path and path.suffix in {".yaml", ".json"}
    }
    if set(content_paths) != discovered_content_paths:
        unlisted = sorted(
            path.relative_to(root).as_posix()
            for path in discovered_content_paths - set(content_paths)
        )
        missing = sorted(
            path.relative_to(root).as_posix()
            for path in set(content_paths) - discovered_content_paths
        )
        raise PracticeContentError(
            f"{manifest_path}: canonical content manifest coverage drift; "
            f"unlisted={unlisted}, missing={missing}."
        )
    content_hash = _canonical_content_hash(content_paths, root, manifest)
    expected_hash = manifest.get("content_hash")
    if expected_hash != content_hash:
        raise PracticeContentError(
            f"{manifest_path}: content hash drift; expected {expected_hash!r}, "
            f"calculated {content_hash!r}."
        )

    bundle = PracticeContentBundle(
        protocols=protocol_tuple,
        sources=sources,
        risk_classes=risk_classes,
        scoring_policies=scoring_policies,
        protocol_families=protocol_families,
        activation_entries=activation_entries,
        research_gaps=research_gaps,
        expert_reviews=expert_reviews,
        release_manifest=manifest,
        content_hash=content_hash,
    )
    runtime_protocols = bundle.runtime_protocols
    if len(runtime_protocols) != len(bundle.protocols):
        raise PracticeContentError("Every canonical protocol must be runtime projected.")
    if not all(protocol["availability"] == "active" for protocol in runtime_protocols):
        raise PracticeContentError("Every runtime protocol must be available.")
    if not all(protocol["score_active"] for protocol in runtime_protocols):
        raise PracticeContentError("Every runtime protocol must be score active.")
    legacy_runtime = [
        protocol
        for protocol in runtime_protocols
        if protocol["stable_id"] in FROZEN_LEGACY_PROTOCOL_IDS
    ]
    projection_hash = configuration_hash(
        [legacy_projection_payload(protocol) for protocol in legacy_runtime]
    )
    if manifest.get("legacy_projection_hash") != projection_hash:
        raise PracticeContentError(f"{manifest_path}: legacy projection hash is inconsistent.")
    return bundle


def _practice_content_fingerprint(base_dir: Path) -> str:
    practice_root = base_dir / "data" / "practices"
    paths = {
        path.resolve()
        for path in practice_root.rglob("*")
        if path.is_file() and path.suffix in {".json", ".yaml"}
    }
    source_registry_path = practice_root / "registries" / "source_registry.yaml"
    source_registry = _read_yaml(source_registry_path)
    raw_sources = source_registry.get("sources")
    sources = raw_sources if isinstance(raw_sources, list) else []
    for source in sources:
        if isinstance(source, dict) and source.get("locator_kind") == "repository_path":
            paths.add((base_dir / source["locator"]).resolve())

    digest = hashlib.sha256()
    for path in sorted(paths):
        try:
            relative = path.relative_to(base_dir)
            content = path.read_bytes()
        except (OSError, ValueError) as exc:
            raise PracticeContentError(
                f"{path}: could not fingerprint canonical practice input: {exc}"
            ) from exc
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


@cache
def _cached_practice_content_bundle(
    base_dir: Path,
    _fingerprint: str,
) -> PracticeContentBundle:
    return _load_practice_content_bundle(base_dir)


def load_practice_content_bundle(base_dir: Path) -> PracticeContentBundle:
    resolved_base_dir = base_dir.resolve()
    fingerprint = _practice_content_fingerprint(resolved_base_dir)
    return deepcopy(_cached_practice_content_bundle(resolved_base_dir, fingerprint))


def compile_runtime_protocol(
    protocol: dict[str, Any],
    activation_entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    stable_id = protocol["stable_id"]
    governance = protocol["governance"]
    meaning = protocol["meaning_and_fit"]
    intervention = protocol["intervention"]
    evidence = protocol["evidence_and_scoring"]
    review = protocol["completion_and_review"]
    presentation = protocol["presentation"]
    activation = activation_entries[stable_id]
    return {
        "stable_id": stable_id,
        "slug": protocol["slug"],
        "name": protocol["name"],
        "parent_competency_id": protocol["parent_competency_id"],
        "availability": governance["availability"],
        "duration_days": intervention["duration_days"],
        "recommendation_reason": meaning["why_recommended"],
        "applicability_prompt": meaning["applicability_question"],
        "setup_prompt": intervention["setup"],
        "privacy_and_boundaries": intervention["privacy_and_boundaries"],
        "completion_criteria": review["completion_criteria"],
        "completion_rules": review["completion_rules"],
        "setup_copy": {
            **presentation["setup_copy"],
            "check_in_labels": presentation["check_in_labels"],
        },
        "check_in_fields": evidence["check_in_fields"],
        "score_active": activation["score_active"],
        "mastery_disclaimer": review["mastery_disclaimer"],
        "target_levers": evidence["recommendation_target_lever_ids"],
        "display_order": presentation["display_order"],
        "actions": [
            {
                "stable_id": action["stable_id"],
                "sequence": action["sequence"],
                "title": action["title"],
                "instructions": action["instructions"],
                "due_within_days": action["due_within_days"],
                "evidence_rules": action["evidence_rules"],
            }
            for action in intervention["actions"]
        ],
    }


def legacy_projection_payload(protocol: dict[str, Any]) -> dict[str, Any]:
    return {
        "stable_id": protocol["stable_id"],
        "slug": protocol["slug"],
        "name": protocol["name"],
        "parent_competency_id": protocol["parent_competency_id"],
        "availability": protocol["availability"],
        "duration_days": protocol["duration_days"],
        "recommendation_reason": protocol["recommendation_reason"],
        "applicability_prompt": protocol["applicability_prompt"],
        "setup_prompt": protocol["setup_prompt"],
        "privacy_and_boundaries": protocol["privacy_and_boundaries"],
        "completion_criteria": protocol["completion_criteria"],
        "completion_rules": protocol["completion_rules"],
        "setup_copy": protocol["setup_copy"],
        "check_in_fields": protocol["check_in_fields"],
        "score_active": protocol["score_active"],
        "mastery_disclaimer": protocol["mastery_disclaimer"],
        "target_lever_ids": sorted(protocol["target_levers"]),
        "display_order": protocol["display_order"],
        "actions": protocol["actions"],
    }


def configuration_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()
