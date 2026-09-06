"""Compile explicitly authored exercises; never invent missing exercise content."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

VERSION = "GG-TAILORED-PRACTICE-AUTHORING-1.0"
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "domain_id", "exercises"],
    "properties": {
        "schema_version": {"const": VERSION},
        "domain_id": {"type": "string", "pattern": "^[0-9]{2}$"},
        "exercises": {
            "type": "object",
            "minProperties": 1,
            "patternProperties": {
                "^[0-9]{2}\\.[0-9]{2}$": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "title",
                        "goal",
                        "setup",
                        "scope_note",
                        "burden",
                        "actions",
                        "adaptation",
                        "review",
                        "examples",
                    ],
                    "properties": {
                        **{
                            key: {"type": "string", "minLength": 20}
                            for key in (
                                "title",
                                "goal",
                                "setup",
                                "scope_note",
                                "burden",
                                "adaptation",
                                "review",
                            )
                        },
                        "actions": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 5,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["title", "instructions", "checks"],
                                "properties": {
                                    "title": {"type": "string", "minLength": 10},
                                    "instructions": {"type": "string", "minLength": 120},
                                    "checks": {
                                        "type": "array",
                                        "minItems": 3,
                                        "maxItems": 5,
                                        "uniqueItems": True,
                                        "items": {"type": "string", "minLength": 10},
                                    },
                                },
                            },
                        },
                        "examples": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["supportive", "mixed", "contradictory", "inconclusive"],
                            "properties": {
                                key: {"type": "string", "minLength": 30}
                                for key in ("supportive", "mixed", "contradictory", "inconclusive")
                            },
                        },
                    },
                },
            },
            "additionalProperties": False,
        },
    },
}


class UniqueKeyLoader(yaml.SafeLoader):
    """Do not silently discard a competency or criterion under a duplicate key."""


def _mapping(loader: UniqueKeyLoader, node: yaml.MappingNode) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in result:
            raise ValueError(f"Duplicate authoring key: {key}")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_exercises(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    contract = yaml.safe_load((root / "contracts/tailored-practice-authoring.yaml").read_text())
    curriculum = yaml.safe_load(
        (root / "data/curriculum/ideal_person_curriculum_v2_pluralist_full_scope.yaml").read_text()
    )["curriculum"]
    expected_domains = contract["implemented_domains"]
    guide_ids = contract.get("source_only_legacy_guide_competency_ids", [])
    frozen_ids = {"08.02", "11.10", "16.03", "17.03", "26.01"}
    if len(set(guide_ids)) != len(guide_ids) or set(guide_ids) - frozen_ids:
        raise ValueError("Guide-only exclusions must be unique frozen legacy competencies.")
    if any(cid.split(".")[0] not in expected_domains for cid in guide_ids):
        raise ValueError("Legacy guides must belong to an implemented authoring domain.")
    if len(set(expected_domains)) != len(expected_domains):
        raise ValueError("Duplicate implemented authoring domain.")
    canonical_domains = {domain["id"]: domain for domain in curriculum["domains"]}
    if set(expected_domains) - set(canonical_domains):
        raise ValueError("Unknown implemented authoring domain.")
    paths = sorted((root / "docs/authoring/exercises").glob("*.yaml"))
    if {path.stem for path in paths} != set(expected_domains):
        raise ValueError("Authoring files must exactly match declared implemented domains.")
    exercises = {}
    for path in paths:
        document = yaml.load(path.read_text(), Loader=UniqueKeyLoader)
        Draft202012Validator(SCHEMA).validate(document)
        if document["domain_id"] != path.stem:
            raise ValueError(f"{path.name}: wrong domain ID.")
        expected = {row["id"] for row in canonical_domains[path.stem]["competencies"]} - set(
            guide_ids
        )
        if set(document["exercises"]) != expected:
            raise ValueError(f"{path.name}: missing or foreign canonical competency.")
        exercises.update(document["exercises"])
    guides = {}
    for path in sorted((root / "docs/authoring/legacy-guides").glob("*.yaml")):
        document = yaml.load(path.read_text(), Loader=UniqueKeyLoader)
        Draft202012Validator(SCHEMA).validate(document)
        if document["domain_id"] != path.stem:
            raise ValueError("Legacy guide filename must match its domain.")
        for cid, guide in document["exercises"].items():
            if cid in guides or cid.split(".")[0] != path.stem:
                raise ValueError("Duplicate or foreign legacy guide competency.")
            guides[cid] = guide
    if set(guides) != set(guide_ids):
        raise ValueError("Declared frozen legacy guides must exist exactly; no missing guides.")
    instructions = [
        re.sub(r"\W+", " ", action["instructions"]).lower().strip()
        for exercise in [*exercises.values(), *guides.values()]
        for action in exercise["actions"]
    ]
    if len(instructions) != len(set(instructions)):
        raise ValueError("Duplicate tailored action instructions.")
    families = contract["protocol_families"]
    if set(families) != set(exercises):
        raise ValueError("Every authored competency needs an explicit protocol family.")
    registered_families = yaml.safe_load(
        (root / "data/practices/registries/protocol_families.yaml").read_text()
    )
    allowed_families = {row["family_id"] for row in registered_families["families"]}
    if set(families.values()) - allowed_families:
        raise ValueError("An authored competency uses an unregistered protocol family.")
    for cid, exercise in exercises.items():
        exercise["protocol_family"] = families[cid]
        exercise["retain_evidence_rules"] = (
            cid in contract["retained_typed_evidence_competency_ids"]
        )
    return exercises


def apply_exercise(protocol: dict, exercise: dict) -> dict:
    """Pure content projection. ID allocation and scoring math are never inputs."""
    result = copy.deepcopy(protocol)
    intervention = result["intervention"]
    intervention["protocol_class"] = exercise["protocol_family"]
    if len(intervention["actions"]) != len(exercise["actions"]):
        raise ValueError(
            f"{result['stable_id']}: action identity/count changes need separate scope."
        )
    if result["evidence_and_scoring"]["observation_contract_version"] != "typed-evidence-rules-v1":
        raise ValueError(
            "Frozen legacy runtime instructions require a separate compatibility design."
        )
    result["protocol_version"] = "0.2.0"
    result["name"] = exercise["title"]
    authoring = result["governance"]["authoring"]
    authoring["provenance"] = (
        f"M6J individually authored exercise for {result['parent_competency_id']}; "
        "compiled from explicit instructions, observation checks, adaptations and worked examples. "
        "Editorial and specialist acceptance remain pending."
    )
    meaning = result["meaning_and_fit"]
    meaning["purpose"] = exercise["goal"]
    meaning["why_recommended"] = exercise["goal"]
    meaning["readiness_considerations"] = exercise["adaptation"]
    meaning["opportunity_considerations"] = exercise["setup"]
    meaning["prerequisites"] = [exercise["setup"]]
    meaning["safe_alternatives"] = [exercise["adaptation"]]
    for claim in meaning["claims"]:
        if claim["classification"] == "product_design_judgment":
            claim["statement"] = exercise["goal"]
            claim["limitations"] = (
                "Original educational practice design, not evidence of effectiveness, "
                "specialist acceptance or comprehensive competency coverage."
            )
    intervention["setup"] = " ".join(
        (
            exercise["setup"],
            "Goal:",
            exercise["goal"],
            "Scope:",
            exercise["scope_note"],
            "Time and effort:",
            exercise["burden"],
            "Adaptation:",
            exercise["adaptation"],
            "Keep personal working notes outside the check-in; "
            "record only the listed observations.",
        )
    )
    intervention["cadence"] = (
        "Work through the numbered actions at a sustainable pace. Preserve their order; "
        "use the review point specified in the instructions and defer if the context is unsuitable."
    )
    intervention["expected_burden"] = exercise["burden"]
    intervention["adaptations"]["accessibility"] = [exercise["adaptation"]]
    intervention["adaptations"]["resource_variants"] = [exercise["adaptation"]]
    if not exercise["retain_evidence_rules"]:
        intervention["exclusions"] = [
            "Follow the material, equipment, consent and scope limits "
            "in the setup and each action. " + exercise["adaptation"]
        ]
    intervention["privacy_and_boundaries"] = (
        "Keep working notes private. Record only the listed observation checks, not document "
        "contents, identifying details or another person's private information. "
        "Participation and any help must be voluntary. " + exercise["adaptation"]
    )
    presentation = result["presentation"]
    presentation["setup_copy"]["context_heading"] = exercise["title"]
    presentation["setup_copy"]["timing_hint"] = intervention["cadence"]
    labels = presentation["check_in_labels"]
    for action, authored in zip(intervention["actions"], exercise["actions"], strict=True):
        action["title"] = authored["title"]
        checks = authored["checks"]
        action["instructions"] = (
            authored["instructions"] + "\n\nObservation checks: " + "; ".join(checks) + ". "
            "Mark only what you observed. Missing, mixed and negative results are valid; "
            "a deferred action is not completed."
        )
        primary = action["evidence_rules"]["measurements"][0]
        # New events freeze these criteria in their own rules snapshot. Existing
        # events retain and replay their original criteria and provenance.
        if not exercise["retain_evidence_rules"]:
            action["evidence_rules"]["measurements"][0] = {
                "measurement_id": primary["measurement_id"],
                "kind": "artifact",
                "role": "primary",
                "weight": "1",
                "allowed_provenance": ["reviewed_artifact"],
                "criteria": [
                    re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") for text in checks
                ],
            }
        if not exercise["retain_evidence_rules"]:
            labels[primary["measurement_id"]] = f"Observed checks: {authored['title'].lower()}"
    review = result["completion_and_review"]
    minimum = review["completion_rules"]["minimum_completed"]
    total = len(exercise["actions"])
    review["completion_criteria"] = [
        f"Action {i}: {row['title']}. Observed checks: {'; '.join(row['checks'])}."
        for i, row in enumerate(exercise["actions"], 1)
    ] + [
        f"For minimum completion, finish at least {minimum} of these {total} actions and "
        "record a meaningful observation, then explicitly submit your final review. "
        "Finish every action for full completion. Deferral and N/A are not completed actions."
    ]
    review["reflection"] = {
        "before": f"What would count as doing this honestly? Goal: {exercise['goal']}",
        "during": f"Which checks have actually been observed? {exercise['examples']['mixed']}",
        "after": exercise["review"],
    }
    review["evidence_examples"] = exercise["examples"]
    review["progression_criteria"] = exercise["review"]
    review["transfer_limit"] = exercise["scope_note"]
    review["review_guidance"]["adapt"] = exercise["adaptation"]
    review["review_guidance"]["escalate"] = (
        "Obtain appropriate help if the next action exceeds the setup's limits, "
        "your authority or safe access."
    )
    evidence = result["evidence_and_scoring"]
    evidence["adverse_or_contradictory_indicators"] = [exercise["examples"]["contradictory"]]
    evidence["evidence_quality_rubric"] = (
        "Record the listed checks only after reviewing the actual work or a privately kept "
        "record of the attempt. A participant's checked criteria remain self-attested "
        "observations, not an independent assessment or proof of mastery. "
        + exercise["examples"]["inconclusive"]
    )
    evidence["performance_rubric"] = " ".join(review["completion_criteria"][:-1])
    evidence["scoring_eligibility"] = (
        "Check-ins capture immutable evidence only for composite-version practices. "
        "Completion credit requires an explicit human final closeout. "
        "Historical event-level scoring retains its own versioned contract."
    )
    evidence["minimum_evidence_before_state_update"] = (
        "Composite-version practices require the configured completed-action minimum, "
        "meaningful-attempt criterion and explicit final closeout; check-ins award no credit."
    )
    presentation["completion_copy"] = exercise["review"] + " Completion is not mastery."
    presentation["plain_language_evidence"] = exercise["examples"]["supportive"]
    # The examples and review must reach the actual runtime, whose existing
    # setup/check-in templates already display setup prompts and action text.
    intervention["actions"][-1]["instructions"] += (
        "\n\nFinal review: "
        + exercise["review"]
        + "\n\nExamples: "
        + "\n\n".join(f"{kind.capitalize()}: {text}" for kind, text in exercise["examples"].items())
    )
    return result


def coverage_report(exercises: dict[str, dict], root: Path = ROOT) -> dict:
    curriculum = yaml.safe_load(
        (root / "data/curriculum/ideal_person_curriculum_v2_pluralist_full_scope.yaml").read_text()
    )["curriculum"]
    rows = [
        {
            "competency_id": row["id"],
            "name": row["name"],
            "status": "authored_pending_review" if row["id"] in exercises else "rewrite_pending",
        }
        for domain in curriculum["domains"]
        for row in domain["competencies"]
    ]
    return {
        "schema_version": VERSION,
        "target": len(rows),
        "authored": len(exercises),
        "remaining": len(rows) - len(exercises),
        "human_review_complete": 0,
        "source_only_legacy_guides": yaml.safe_load(
            (root / "contracts/tailored-practice-authoring.yaml").read_text()
        ).get("source_only_legacy_guide_competency_ids", []),
        "rows": rows,
    }


def attach_sources(protocols: list[dict], registry: dict, root: Path = ROOT) -> None:
    sources = yaml.safe_load((root / "docs/authoring/sources.yaml").read_text())["sources"]
    by_parent = {protocol["parent_competency_id"]: protocol for protocol in protocols}
    existing_ids = {source["source_id"] for source in sources}
    if len(existing_ids) != len(sources):
        raise ValueError("Duplicate tailored source ID.")
    registry["sources"] = [
        source for source in registry["sources"] if source["source_id"] not in existing_ids
    ]
    for source in sources:
        source["applicable_protocol_ids"] = sorted(
            by_parent[cid]["stable_id"] for cid in source["applicable_competency_ids"]
        )
        registry["sources"].append(source)
        for cid in source["applicable_competency_ids"]:
            protocol = by_parent[cid]
            ids = protocol["governance"]["source_ids"]
            if source["source_id"] not in ids:
                ids.append(source["source_id"])
            protocol["meaning_and_fit"]["claims"] = [
                claim
                for claim in protocol["meaning_and_fit"]["claims"]
                if source["source_id"] not in claim["source_ids"]
            ]
            protocol["meaning_and_fit"]["claims"].append(
                {
                    "statement": source["supported_claim"],
                    "classification": source["claim_classification"],
                    "source_ids": [source["source_id"]],
                    "limitations": source["limitations"],
                }
            )
    # References reach the existing setup screen as plain text. Rebuild the
    # suffix so re-authoring a preserved protocol never duplicates it.
    for protocol in protocols:
        applicable = [
            source
            for source in sources
            if protocol["parent_competency_id"] in source["applicable_competency_ids"]
        ]
        if applicable:
            setup = protocol["intervention"]["setup"].split("\n\nReference support:")[0]
            protocol["intervention"]["setup"] = (
                setup
                + "\n\nReference support:\n"
                + "\n".join(f"{source['title']}: {source['locator']}" for source in applicable)
            )


if __name__ == "__main__":
    print(json.dumps(coverage_report(load_exercises()), indent=2))
