from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from django.conf import settings

from growth.domain.practice_content import (
    FROZEN_LEGACY_PROTOCOL_IDS,
    LEGACY_PROJECTION_VERSION,
    PracticeContentBundle,
    load_practice_content_bundle,
    protocol_release_blockers,
    protocol_sources_complete,
)
from growth.services.canonical_import import CanonicalBundle, load_and_validate_bundle

PRACTICE_REPORT_CONTRACT_VERSION = "GG-CURRICULUM-EXPANSION-REPORTS-1.0"
REPORT_ROOT = Path("reports/practice-content")
REPORT_PATHS = {
    "competency_coverage": REPORT_ROOT / "competency_coverage_v1.csv",
    "coverage_summary": REPORT_ROOT / "coverage_summary_v1.json",
    "domain_coverage": REPORT_ROOT / "domain_coverage_v1.csv",
    "lever_coverage": REPORT_ROOT / "lever_coverage_v1.csv",
    "risk_register": REPORT_ROOT / "risk_register_v1.csv",
    "content_originality": REPORT_ROOT / "content_originality_v1.json",
}
LEGACY_TASK_PATH = Path("data/notion/initial_mvp/02_development_tasks_ranked_import.csv")
NEAR_DUPLICATE_WARNING_LIMIT = 50


class PracticeReportError(ValueError):
    pass


def _csv_bytes(rows: list[dict[str, Any]], fieldnames: list[str]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def _protocol_path_map(base_dir: Path, bundle: PracticeContentBundle) -> dict[str, Path]:
    root = base_dir / "data" / "practices"
    paths: dict[str, Path] = {}
    for relative in bundle.release_manifest["protocol_files"]:
        path = root / relative
        stable_id = path.stem
        paths[stable_id] = path
    return paths


def _canonical_indexes(canonical: CanonicalBundle) -> tuple[dict[str, dict], dict[str, dict]]:
    competencies: dict[str, dict] = {}
    domains: dict[str, dict] = {}
    for domain in canonical.curriculum["domains"]:
        domain_id = str(domain["id"])
        domains[domain_id] = domain
        for competency in domain["competencies"]:
            competencies[competency["id"]] = {
                **competency,
                "domain_id": domain_id,
                "domain_name": domain["name"],
            }
    return competencies, domains


def _mapping_by_competency(canonical: CanonicalBundle) -> dict[str, dict[str, float]]:
    return {
        link["competency_id"]: {
            lever_id: float(weight) for lever_id, weight in link["lever_weights"].items()
        }
        for link in canonical.model["competency_lever_links"]
    }


def _coverage_rows(
    base_dir: Path,
    canonical: CanonicalBundle,
    practices: PracticeContentBundle,
) -> list[dict[str, Any]]:
    competencies, _ = _canonical_indexes(canonical)
    mappings = _mapping_by_competency(canonical)
    protocols_by_parent = {
        protocol["parent_competency_id"]: protocol
        for protocol in practices.protocols
        if not protocol["governance"]["deprecation"]["deprecated"]
    }
    protocol_paths = _protocol_path_map(base_dir, practices)
    rows: list[dict[str, Any]] = []
    for competency_id in sorted(competencies):
        competency = competencies[competency_id]
        protocol = protocols_by_parent.get(competency_id)
        mapped_levers = sorted(mappings[competency_id])
        if protocol is None:
            row = {
                "competency_id": competency_id,
                "competency_name": competency["name"],
                "domain_id": competency["domain_id"],
                "domain_name": competency["domain_name"],
                "content_status": "uncovered",
                "protocol_stable_id": "",
                "protocol_version": "",
                "protocol_path": "",
                "protocol_sha256": "",
                "protocol_family": "",
                "risk_class": "",
                "runtime_projection": "",
                "sources_complete": "false",
                "safety_review_status": "not_started",
                "scoring_policy": "",
                "shadow_test_status": "not_started",
                "activation_status": "unassigned",
                "release_gate_status": "not_authored",
                "ui_test_status": "not_started",
                "parent_mapping_lever_ids": ";".join(mapped_levers),
                "recommendation_target_lever_ids": "",
                "blocking_issue": "Canonical protocol package not yet authored.",
            }
        else:
            stable_id = protocol["stable_id"]
            governance = protocol["governance"]
            authoring = governance["authoring"]
            activation = practices.activation_entries[stable_id]
            path = protocol_paths[stable_id]
            source_complete = protocol_sources_complete(practices, protocol)
            release_blockers = protocol_release_blockers(practices, protocol)
            runtime_projection = governance["runtime_projection"]
            row = {
                "competency_id": competency_id,
                "competency_name": competency["name"],
                "domain_id": competency["domain_id"],
                "domain_name": competency["domain_name"],
                "content_status": governance["editorial_status"],
                "protocol_stable_id": stable_id,
                "protocol_version": protocol["protocol_version"],
                "protocol_path": path.relative_to(base_dir).as_posix(),
                "protocol_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "protocol_family": protocol["intervention"]["protocol_class"],
                "risk_class": governance["risk_class_id"],
                "runtime_projection": runtime_projection,
                "sources_complete": str(source_complete).lower(),
                "safety_review_status": authoring["safety_review_status"],
                "scoring_policy": governance["scoring_policy_id"],
                "shadow_test_status": activation["shadow_test_status"],
                "activation_status": activation["activation_status"],
                "release_gate_status": (
                    "passed"
                    if governance["editorial_status"] == "release_candidate"
                    and not release_blockers
                    else "blocked"
                ),
                "ui_test_status": authoring["ui_test_status"],
                "parent_mapping_lever_ids": ";".join(mapped_levers),
                "recommendation_target_lever_ids": ";".join(
                    sorted(protocol["evidence_and_scoring"]["recommendation_target_lever_ids"])
                ),
                "blocking_issue": ";".join(release_blockers),
            }
        rows.append(row)
    return rows


def _domain_rows(
    coverage_rows: list[dict[str, Any]], canonical: CanonicalBundle
) -> list[dict[str, Any]]:
    _, domains = _canonical_indexes(canonical)
    rows_by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in coverage_rows:
        rows_by_domain[row["domain_id"]].append(row)
    rows = []
    for domain_id in sorted(domains):
        domain_rows = rows_by_domain[domain_id]
        authored = [row for row in domain_rows if row["protocol_stable_id"]]
        projected = [
            row for row in authored if row["runtime_projection"] == LEGACY_PROJECTION_VERSION
        ]
        risk_counts = Counter(row["risk_class"] for row in authored)
        rows.append(
            {
                "domain_id": domain_id,
                "domain_name": domains[domain_id]["name"],
                "competencies": len(domain_rows),
                "authored_packages": len(authored),
                "projected_legacy": len(projected),
                "uncovered": len(domain_rows) - len(authored),
                "low_risk": risk_counts["RISK-LOW"],
                "moderate_risk": risk_counts["RISK-MODERATE"],
                "high_risk": risk_counts["RISK-HIGH"],
                "score_active": sum(row["activation_status"] == "active" for row in authored),
                "shadow_only": sum(row["scoring_policy"] == "SP-SHADOW-ONLY" for row in authored),
            }
        )
    return rows


def _lever_rows(
    canonical: CanonicalBundle,
    practices: PracticeContentBundle,
) -> list[dict[str, Any]]:
    levers = {lever["id"]: lever for lever in canonical.model["developmental_levers"]}
    mappings = _mapping_by_competency(canonical)
    parent_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    active_counts: Counter[str] = Counter()
    for protocol in practices.protocols:
        parent_levers = set(mappings[protocol["parent_competency_id"]])
        targets = set(protocol["evidence_and_scoring"]["recommendation_target_lever_ids"])
        parent_counts.update(parent_levers)
        target_counts.update(targets)
        if practices.activation_entries[protocol["stable_id"]]["score_active"]:
            active_counts.update(parent_levers)
    canonical_counts: Counter[str] = Counter()
    for mapping in mappings.values():
        canonical_counts.update(mapping.keys())
    return [
        {
            "lever_id": lever_id,
            "lever_name": levers[lever_id]["name"],
            "canonical_competency_count": canonical_counts[lever_id],
            "protocol_parent_count": parent_counts[lever_id],
            "recommendation_target_count": target_counts[lever_id],
            "score_active_protocol_parent_count": active_counts[lever_id],
            "m6a_status": (
                "projected_parent_coverage" if parent_counts[lever_id] else "canonical_mapping_only"
            ),
        }
        for lever_id in sorted(levers)
    ]


def _risk_rows(practices: PracticeContentBundle) -> list[dict[str, Any]]:
    rows = []
    for protocol in sorted(practices.protocols, key=lambda item: item["stable_id"]):
        stable_id = protocol["stable_id"]
        governance = protocol["governance"]
        risk = practices.risk_classes[governance["risk_class_id"]]
        rows.append(
            {
                "protocol_stable_id": stable_id,
                "risk_class": governance["risk_class_id"],
                "editorial_status": governance["editorial_status"],
                "safety_review_status": governance["authoring"]["safety_review_status"],
                "required_reviewer_role": risk["required_reviewer_role"],
                "pre_review_scoring_ceiling": risk["pre_review_scoring_ceiling"],
                "scoring_policy": governance["scoring_policy_id"],
                "score_active": str(
                    practices.activation_entries[stable_id]["score_active"]
                ).lower(),
                "sensitive_data_limit": risk["sensitive_data_limit"],
                "foreseeable_misuse": " | ".join(protocol["intervention"]["foreseeable_misuse"]),
                "exclusions": " | ".join(protocol["intervention"]["exclusions"]),
                "pause_conditions": " | ".join(protocol["intervention"]["pause_conditions"]),
                "stop_conditions": " | ".join(protocol["intervention"]["stop_conditions"]),
                "professional_referral_conditions": " | ".join(
                    protocol["intervention"]["professional_referral_conditions"]
                ),
                "release_gate": " | ".join(risk["production_release_conditions"]),
            }
        )
    return rows


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", value.casefold())).strip()


FROZEN_APPROVED_SHARED_HASHES_BY_PATH = {
    "meaning_and_fit.not_applicable_behavior": {
        "d49493e3c2f482770f213bce35078e847671ff84a2062b40b10c52c301229f3b"
    },
    "meaning_and_fit.claims[0].limitations": {
        "0aff238eab0bb8fb5597830276f6941fac2d7d422d384427e05fa7ad2876491a"
    },
    "evidence_and_scoring.observation_contract_version": {
        "46528627219119f4d50f4d19faf4787388c7445ad4d613b7ae63032241f8ff99"
    },
    "evidence_and_scoring.independence_rule": {
        "96e9a839f297cf7587ce87b027ea57eb4e5abf99ec4af0942beb24457995ec81"
    },
    "evidence_and_scoring.context_transfer_rule": {
        "8258dbb80d1b4d5fa6b02d6f59747d88f3046212b49f1ee4f411da20752ade64"
    },
    "evidence_and_scoring.repetition_rule": {
        "10e4dfbc0bf1d22509137a1232d2f10792770076188ff51c1453a62bd4a8e084"
    },
    "evidence_and_scoring.recency_rule": {
        "d3eea9b5366c7cdb0640c017f26ba2761c10e8c5b8fb6015e976af9ac6f40503"
    },
    "evidence_and_scoring.competency_contribution": {
        "a3d548fa28140697498e66612410f7bca386c186e2da34ebdc4b63d9c8f8400f"
    },
    "evidence_and_scoring.canonical_lever_allocation": {
        "756009e8e959f5c29d220eab22da4ef60f8df0bc4ea3af71a2fa51cd26ae9dc5"
    },
    "evidence_and_scoring.minimum_evidence_before_state_update": {
        "7bc7a1850c739529c11130914881a1a05e262d8cc8857457939a9213689b7b38",
        "72a027c37eb5932c69a3265c6bfedf411cc7f067f7b0b987017deb66a31e9391",
    },
    "completion_and_review.mastery_disclaimer": {
        "7a4a41ff98c5e479f7acb9fc079ada0805408fd9bfc9d0aa2c451d93aba03733"
    },
}
FROZEN_APPROVED_SHARED_HASHES_BY_PREFIX = {
    "evidence_and_scoring.withholding_conditions[": {
        "7fa44656042c56606113d62c24c44592fbbab6c13a09f92dc46074c6fb67be87"
    }
}


def _field_path(location: str) -> str:
    parts = location.split(".", 1)
    return parts[1] if len(parts) == 2 else ""


def _approved_shared_location(location: str, normalized_hash: str) -> bool:
    protocol_id = location.split(".", 1)[0]
    if protocol_id not in FROZEN_LEGACY_PROTOCOL_IDS:
        return False
    field_path = _field_path(location)
    if normalized_hash in FROZEN_APPROVED_SHARED_HASHES_BY_PATH.get(field_path, set()):
        return True
    return any(
        field_path.startswith(prefix) and normalized_hash in approved_hashes
        for prefix, approved_hashes in FROZEN_APPROVED_SHARED_HASHES_BY_PREFIX.items()
    )


def _flatten_text(prefix: str, value: Any, output: dict[str, str]) -> None:
    if isinstance(value, str):
        output[prefix] = value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _flatten_text(f"{prefix}[{index}]", item, output)
    elif isinstance(value, dict):
        for key, item in value.items():
            _flatten_text(f"{prefix}.{key}", item, output)


def _content_terms(value: str) -> set[str]:
    stop_words = {
        "about",
        "after",
        "again",
        "another",
        "before",
        "between",
        "during",
        "from",
        "have",
        "into",
        "more",
        "rather",
        "that",
        "their",
        "there",
        "these",
        "this",
        "through",
        "under",
        "what",
        "when",
        "where",
        "which",
        "while",
        "with",
        "without",
    }
    return {
        token.rstrip("s")
        for token in _normalize_text(value).split()
        if len(token) >= 5 and token not in stop_words
    }


def _duplicate_groups(values: dict[str, str]) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for key, value in values.items():
        grouped[_normalize_text(value)].append(key)
    duplicates = []
    for text, locations in sorted(grouped.items()):
        if len(locations) <= 1:
            continue
        ordered_locations = sorted(locations)
        normalized_hash = hashlib.sha256(text.encode()).hexdigest()
        approved = all(
            _approved_shared_location(location, normalized_hash) for location in ordered_locations
        )
        duplicates.append(
            {
                "locations": ordered_locations,
                "normalized_sha256": normalized_hash,
                "classification": (
                    "approved_shared_architecture" if approved else "review_required"
                ),
            }
        )
    return duplicates


def _near_duplicate_pairs(
    values: dict[str, str], *, threshold: float = 0.8
) -> list[dict[str, Any]]:
    """Return a bounded deterministic review queue for similar authored copy.

    Exact duplicates are audited separately. Near-duplicate comparison is a
    reviewer-routing heuristic, so compare structurally equivalent locations,
    normalize each value once, and cap the queue. This keeps the report
    practical at the 383-package frontier instead of performing an unbounded
    all-fields Cartesian scan.
    """

    def bucket(key: str) -> str:
        field_path = _field_path(key)
        if field_path:
            return field_path
        action_match = re.search(r"-A([0-9]+)$", key)
        return f"action-{action_match.group(1)}" if action_match else "root"

    pairs: list[dict[str, Any]] = []
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for key, value in values.items():
        grouped[bucket(key)].append((key, _normalize_text(value)))
    for group_key in sorted(grouped):
        items = sorted(grouped[group_key])
        for index, (left_key, left_value) in enumerate(items):
            for right_key, right_value in items[index + 1 :]:
                matcher = SequenceMatcher(None, left_value, right_value)
                if matcher.real_quick_ratio() < threshold:
                    continue
                if matcher.quick_ratio() < threshold:
                    continue
                ratio = matcher.ratio()
                if ratio < threshold:
                    continue
                pairs.append(
                    {
                        "left": left_key,
                        "right": right_key,
                        "similarity": round(ratio, 4),
                    }
                )
                if len(pairs) >= NEAR_DUPLICATE_WARNING_LIMIT:
                    return pairs
    return pairs


def _legacy_notion_audit(base_dir: Path) -> dict[str, Any]:
    with (base_dir / LEGACY_TASK_PATH).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    journal_prompts = [row["Journal Prompt"] for row in rows]
    prompt_counts = Counter(journal_prompts)
    repeated_prompt, repeated_count = prompt_counts.most_common(1)[0]
    return {
        "source_path": LEGACY_TASK_PATH.as_posix(),
        "rows": len(rows),
        "unique_task_names": len({row["Task"] for row in rows}),
        "unique_scopes": len({row["Scope"] for row in rows}),
        "unique_evidence_of_progress": len({row["Evidence of Progress"] for row in rows}),
        "unique_journal_prompts": len(prompt_counts),
        "most_repeated_journal_prompt_count": repeated_count,
        "most_repeated_journal_prompt_sha256": hashlib.sha256(repeated_prompt.encode()).hexdigest(),
        "disposition": "known_source_defect_do_not_propagate",
    }


def _originality_report(
    base_dir: Path,
    practices: PracticeContentBundle,
    canonical: CanonicalBundle,
) -> dict[str, Any]:
    all_content_fields: dict[str, str] = {}
    meaning_fields: dict[str, str] = {}
    intervention_fields: dict[str, str] = {}
    evidence_fields: dict[str, str] = {}
    completion_fields: dict[str, str] = {}
    presentation_fields: dict[str, str] = {}
    reflection_fields: dict[str, str] = {}
    safety_fields: dict[str, str] = {}
    action_titles: dict[str, str] = {}
    action_instructions: dict[str, str] = {}
    action_expected_times: dict[str, str] = {}
    evidence_rules: dict[str, str] = {}
    setup_text: dict[str, str] = {}
    safety_composites: dict[str, str] = {}
    marker_restatement_warnings: list[dict[str, Any]] = []
    operationalization_signals: list[dict[str, Any]] = []
    action_counts: Counter[int] = Counter()
    durations: Counter[int] = Counter()
    competencies, _ = _canonical_indexes(canonical)
    for protocol in practices.protocols:
        stable_id = protocol["stable_id"]
        meaning = protocol["meaning_and_fit"]
        intervention = protocol["intervention"]
        evidence = protocol["evidence_and_scoring"]
        review = protocol["completion_and_review"]
        presentation = protocol["presentation"]
        meaning_text = {
            **{key: value for key, value in meaning.items() if key != "claims"},
            "claims": [
                {
                    "statement": claim["statement"],
                    "limitations": claim["limitations"],
                }
                for claim in meaning["claims"]
            ],
        }
        _flatten_text(
            f"{stable_id}.meaning_and_fit",
            meaning_text,
            meaning_fields,
        )
        intervention_text = {
            key: value
            for key, value in intervention.items()
            if key not in {"actions", "duration_days", "protocol_class"}
        }
        _flatten_text(
            f"{stable_id}.intervention",
            intervention_text,
            intervention_fields,
        )
        evidence_text = {
            key: value
            for key, value in evidence.items()
            if key
            not in {
                "check_in_fields",
                "recommendation_target_lever_ids",
            }
        }
        _flatten_text(
            f"{stable_id}.evidence_and_scoring",
            evidence_text,
            evidence_fields,
        )
        _flatten_text(
            f"{stable_id}.completion_and_review",
            {key: value for key, value in review.items() if key != "completion_rules"},
            completion_fields,
        )
        _flatten_text(
            f"{stable_id}.completion_and_review.reflection",
            review["reflection"],
            reflection_fields,
        )
        setup_copy = {
            key: value
            for key, value in presentation["setup_copy"].items()
            if key != "check_in_labels"
        }
        presentation_text = {
            **presentation,
            "setup_copy": setup_copy,
        }
        _flatten_text(
            f"{stable_id}.presentation",
            presentation_text,
            presentation_fields,
        )
        safety_payload = {
            key: intervention[key]
            for key in (
                "privacy_and_boundaries",
                "foreseeable_misuse",
                "exclusions",
                "adaptations",
                "pause_conditions",
                "stop_conditions",
                "escalation_conditions",
                "professional_referral_conditions",
            )
        }
        _flatten_text(f"{stable_id}.intervention", safety_payload, safety_fields)
        setup_text[stable_id] = intervention["setup"]
        safety_composites[stable_id] = json.dumps(
            safety_payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        action_counts[len(intervention["actions"])] += 1
        durations[intervention["duration_days"]] += 1
        for action in intervention["actions"]:
            action_id = action["stable_id"]
            action_titles[action_id] = action["title"]
            action_instructions[action_id] = action["instructions"]
            action_expected_times[action_id] = action["expected_time"]
            evidence_rules[action_id] = json.dumps(
                action["evidence_rules"], sort_keys=True, separators=(",", ":")
            )
            rules = action["evidence_rules"]
            if rules["schema_version"] == "practice-observation-v1":
                all_markers = {
                    *rules["primary_markers"],
                    *rules["supporting_markers"],
                }
            else:
                all_markers = {
                    measurement["measurement_id"]
                    for measurement in rules["measurements"]
                    if measurement["role"] in {"primary", "supporting"}
                }
            completion_only = sorted(
                marker
                for marker in all_markers
                if marker in {"action_attempted", "action_completed", "completed"}
                or "completion" in marker
            )
            if completion_only:
                marker_restatement_warnings.append(
                    {"action_id": action_id, "markers": completion_only}
                )
        competency = competencies[protocol["parent_competency_id"]]
        competency_terms = _content_terms(
            " ".join(
                (
                    competency["name"],
                    competency["scope"],
                    competency["evidence_of_progress"],
                )
            )
        )
        action_terms = _content_terms(
            " ".join(action["instructions"] for action in intervention["actions"])
        )
        shared_terms = sorted(competency_terms & action_terms)
        operationalization_signals.append(
            {
                "protocol_stable_id": stable_id,
                "parent_competency_id": protocol["parent_competency_id"],
                "lexical_overlap_terms": shared_terms,
                "automated_signal": (
                    "lexical_overlap_present"
                    if shared_terms
                    else "review_candidate_no_lexical_overlap"
                ),
                "human_review_status": protocol["governance"]["authoring"]["content_review_status"],
                "originality_review_status": protocol["governance"]["authoring"][
                    "originality_review_status"
                ],
                "release_candidate_gate": (
                    "complete"
                    if protocol["governance"]["authoring"]["content_review_status"] == "complete"
                    and protocol["governance"]["authoring"]["originality_review_status"]
                    == "complete"
                    else "review_required"
                ),
            }
        )
    for fields in (
        meaning_fields,
        intervention_fields,
        evidence_fields,
        completion_fields,
        presentation_fields,
        action_titles,
        action_instructions,
        action_expected_times,
    ):
        all_content_fields.update(fields)

    evidence_rule_groups: dict[str, list[str]] = defaultdict(list)
    for action_id, rules in evidence_rules.items():
        evidence_rule_groups[rules].append(action_id)
    declared_duplicate_exceptions = {
        tuple(sorted(exception["affected_action_ids"])): exception["exception_id"]
        for protocol in practices.protocols
        for exception in protocol["governance"]["legacy_compatibility_exceptions"]
        if exception["category"] == "duplicate_evidence_rules"
    }
    duplicated_evidence_rules = [
        {
            "action_ids": sorted(action_ids),
            "classification": (
                "legacy_compatibility_exception"
                if tuple(sorted(action_ids)) in declared_duplicate_exceptions
                else "review_required"
            ),
            "exception_id": declared_duplicate_exceptions.get(tuple(sorted(action_ids))),
        }
        for _, action_ids in sorted(evidence_rule_groups.items())
        if len(action_ids) > 1
    ]
    field_duplicate_audit = {
        "all_content": _duplicate_groups(all_content_fields),
        "meaning_and_fit": _duplicate_groups(meaning_fields),
        "intervention": _duplicate_groups(intervention_fields),
        "action_titles": _duplicate_groups(action_titles),
        "action_instructions": _duplicate_groups(action_instructions),
        "action_expected_times": _duplicate_groups(action_expected_times),
        "evidence_and_scoring": _duplicate_groups(evidence_fields),
        "reflection": _duplicate_groups(reflection_fields),
        "completion_and_review": _duplicate_groups(completion_fields),
        "safety": _duplicate_groups(safety_fields),
        "presentation": _duplicate_groups(presentation_fields),
    }
    return {
        "contract_version": PRACTICE_REPORT_CONTRACT_VERSION,
        "catalog_content_hash": practices.content_hash,
        "scope": {
            "protocols": len(practices.protocols),
            "actions": sum(
                len(protocol["intervention"]["actions"]) for protocol in practices.protocols
            ),
            "editorial_status": "projected_legacy_not_full_library_acceptance",
        },
        "approved_shared_content": [
            "schema labels and version identifiers",
            "the canonical completion-does-not-establish-mastery disclaimer",
            "the no-deficit not-applicable disposition",
            "the frozen legacy evidence architecture fields named in approved_shared_field_paths",
        ],
        "approved_shared_field_paths": sorted(
            set(FROZEN_APPROVED_SHARED_HASHES_BY_PATH)
            | set(FROZEN_APPROVED_SHARED_HASHES_BY_PREFIX)
        ),
        "field_duplicate_audit": field_duplicate_audit,
        "exact_or_normalized_duplicates": {
            "substantive_fields": _duplicate_groups(meaning_fields),
            "action_titles": _duplicate_groups(action_titles),
            "action_instructions": _duplicate_groups(action_instructions),
            "action_expected_times": _duplicate_groups(action_expected_times),
            "reflection_sets": _duplicate_groups(reflection_fields),
            "evidence_and_scoring": _duplicate_groups(evidence_fields),
            "completion_and_review": _duplicate_groups(completion_fields),
            "safety": _duplicate_groups(safety_fields),
            "presentation": _duplicate_groups(presentation_fields),
            "evidence_rule_payloads": duplicated_evidence_rules,
        },
        "near_duplicate_warnings": {
            "warning_limit_per_category": NEAR_DUPLICATE_WARNING_LIMIT,
            "substantive_fields_threshold": 0.8,
            "substantive_fields": _near_duplicate_pairs(meaning_fields),
            "action_titles_threshold": 0.8,
            "action_titles": _near_duplicate_pairs(action_titles),
            "action_instructions_threshold": 0.8,
            "action_instructions": _near_duplicate_pairs(action_instructions),
            "generic_setup_threshold": 0.75,
            "generic_setup_candidates": _near_duplicate_pairs(setup_text, threshold=0.75),
            "safety_copy_threshold": 0.8,
            "safety_copy_candidates": _near_duplicate_pairs(safety_composites),
        },
        "safety_copy_exact_duplicates": _duplicate_groups(safety_fields),
        "evidence_markers_that_only_restate_completion": marker_restatement_warnings,
        "parent_competency_operationalization_signals": operationalization_signals,
        "structure_warnings": {
            "action_count_distribution": {
                str(key): value for key, value in sorted(action_counts.items())
            },
            "duration_day_distribution": {
                str(key): value for key, value in sorted(durations.items())
            },
            "single_action_count_for_all_protocols": len(action_counts) == 1,
            "single_duration_for_all_protocols": len(durations) == 1,
            "disposition": (
                "Structural repetition is reported as a human-review routing signal. "
                "It is not automatically accepted and does not establish originality."
            ),
        },
        "semantic_review_boundary": (
            "Text similarity cannot prove that actions operationalize a competency or "
            "that markers measure more than completion; the lexical and marker checks "
            "only route candidates and every package still requires recorded human review."
        ),
        "legacy_notion_source_audit": _legacy_notion_audit(base_dir),
    }


def build_practice_report_outputs(
    base_dir: Path | None = None,
) -> dict[Path, bytes]:
    resolved_base = (base_dir or settings.BASE_DIR).resolve()
    canonical = load_and_validate_bundle()
    practices = load_practice_content_bundle(resolved_base)
    coverage = _coverage_rows(resolved_base, canonical, practices)
    domains = _domain_rows(coverage, canonical)
    levers = _lever_rows(canonical, practices)
    risks = _risk_rows(practices)
    authored = [row for row in coverage if row["protocol_stable_id"]]
    projected = [row for row in authored if row["runtime_projection"] == LEGACY_PROJECTION_VERSION]
    parent_levers = {
        lever_id
        for row in authored
        for lever_id in row["parent_mapping_lever_ids"].split(";")
        if lever_id
    }
    target_levers = {
        lever_id
        for row in authored
        for lever_id in row["recommendation_target_lever_ids"].split(";")
        if lever_id
    }
    summary = {
        "contract_version": PRACTICE_REPORT_CONTRACT_VERSION,
        "canonical_curriculum_source_hash": canonical.source_hash,
        "practice_catalog_content_hash": practices.content_hash,
        "competencies": {
            "total": len(coverage),
            "authored_packages": len(authored),
            "projected_legacy": len(projected),
            "uncovered": len(coverage) - len(authored),
        },
        "domains": {
            "total": len(domains),
            "with_authored_package": sum(row["authored_packages"] > 0 for row in domains),
            "without_authored_package": sum(row["authored_packages"] == 0 for row in domains),
            "with_projected_protocol": sum(row["projected_legacy"] > 0 for row in domains),
        },
        "levers": {
            "total": len(levers),
            "covered_through_parent_mapping": len(parent_levers),
            "recommendation_targets": len(target_levers),
        },
        "protocols": {
            "total": len(practices.protocols),
            "actions": sum(
                len(protocol["intervention"]["actions"]) for protocol in practices.protocols
            ),
            "risk_classes": dict(
                sorted(
                    Counter(
                        protocol["governance"]["risk_class_id"] for protocol in practices.protocols
                    ).items()
                )
            ),
            "scoring_policies": dict(
                sorted(
                    Counter(
                        protocol["governance"]["scoring_policy_id"]
                        for protocol in practices.protocols
                    ).items()
                )
            ),
            "score_active": sum(
                activation["score_active"] for activation in practices.activation_entries.values()
            ),
        },
        "release_candidates": sum(
            protocol["governance"]["editorial_status"] == "release_candidate"
            for protocol in practices.protocols
            if not protocol["governance"]["deprecation"]["deprecated"]
        ),
        "sources_complete": sum(row["sources_complete"] == "true" for row in authored),
    }
    coverage_fields = [
        "competency_id",
        "competency_name",
        "domain_id",
        "domain_name",
        "content_status",
        "protocol_stable_id",
        "protocol_version",
        "protocol_path",
        "protocol_sha256",
        "protocol_family",
        "risk_class",
        "runtime_projection",
        "sources_complete",
        "safety_review_status",
        "scoring_policy",
        "shadow_test_status",
        "activation_status",
        "release_gate_status",
        "ui_test_status",
        "parent_mapping_lever_ids",
        "recommendation_target_lever_ids",
        "blocking_issue",
    ]
    return {
        REPORT_PATHS["competency_coverage"]: _csv_bytes(coverage, coverage_fields),
        REPORT_PATHS["coverage_summary"]: _json_bytes(summary),
        REPORT_PATHS["domain_coverage"]: _csv_bytes(
            domains,
            [
                "domain_id",
                "domain_name",
                "competencies",
                "authored_packages",
                "projected_legacy",
                "uncovered",
                "low_risk",
                "moderate_risk",
                "high_risk",
                "score_active",
                "shadow_only",
            ],
        ),
        REPORT_PATHS["lever_coverage"]: _csv_bytes(
            levers,
            [
                "lever_id",
                "lever_name",
                "canonical_competency_count",
                "protocol_parent_count",
                "recommendation_target_count",
                "score_active_protocol_parent_count",
                "m6a_status",
            ],
        ),
        REPORT_PATHS["risk_register"]: _csv_bytes(
            risks,
            [
                "protocol_stable_id",
                "risk_class",
                "editorial_status",
                "safety_review_status",
                "required_reviewer_role",
                "pre_review_scoring_ceiling",
                "scoring_policy",
                "score_active",
                "sensitive_data_limit",
                "foreseeable_misuse",
                "exclusions",
                "pause_conditions",
                "stop_conditions",
                "professional_referral_conditions",
                "release_gate",
            ],
        ),
        REPORT_PATHS["content_originality"]: _json_bytes(
            _originality_report(resolved_base, practices, canonical)
        ),
    }


def write_or_check_practice_reports(
    *,
    base_dir: Path | None = None,
    check: bool,
) -> tuple[Path, ...]:
    resolved_base = (base_dir or settings.BASE_DIR).resolve()
    outputs = build_practice_report_outputs(resolved_base)
    changed: list[Path] = []
    for relative, expected in outputs.items():
        path = resolved_base / relative
        actual = path.read_bytes() if path.exists() else None
        if actual == expected:
            continue
        changed.append(relative)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
    if check and changed:
        raise PracticeReportError(
            "Generated practice-content reports are missing or stale: "
            + ", ".join(path.as_posix() for path in changed)
        )
    return tuple(changed)
