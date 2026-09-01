#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "grounded_growth.settings_test")

import django  # noqa: E402

django.setup()

from growth.domain.composite_scoring import (  # noqa: E402
    CompositeScoringError,
    blended_relationship_weights,
    canonical_hash,
    closeout_credit,
    policy_from_contract,
)
from growth.domain.practice_content import load_practice_content_bundle  # noqa: E402
from growth.services.canonical_import import load_and_validate_bundle  # noqa: E402

CONTRACT_VERSION = "GG-COMPOSITE-SCORING-CATALOG-1.0"
SCORING_CONTRACT_PATH = Path("contracts/composite-closeout-scoring.yaml")
SCORING_CONTRACT_SCHEMA_PATH = Path("contracts/composite-closeout-scoring.schema.json")
SCHEMA_PATH = Path("contracts/composite-scoring-catalog.schema.json")
REPORT_PATH = Path("reports/practice-content/composite_scoring_catalog_v1.json")
TWELVE_PLACES = Decimal("0.000000000001")


class CompositeCatalogError(ValueError):
    pass


def _decimal_string(value: Decimal) -> str:
    return format(value.quantize(TWELVE_PLACES, rounding=ROUND_HALF_UP), "f")


def _allocation_strings(values: dict[str, Decimal]) -> dict[str, str]:
    ordered = sorted(values.items())
    rendered = {
        key: value.quantize(TWELVE_PLACES, rounding=ROUND_HALF_UP) for key, value in ordered
    }
    adjustment_key = max(ordered, key=lambda item: (item[1], item[0]))[0]
    rendered[adjustment_key] += Decimal("1") - sum(rendered.values(), Decimal("0"))
    if any(value <= 0 for value in rendered.values()):
        raise CompositeCatalogError("Serialized relationship allocation is not positive.")
    if sum(rendered.values(), Decimal("0")) != Decimal("1"):
        raise CompositeCatalogError("Serialized relationship allocation does not sum to one.")
    return {key: format(value, "f") for key, value in sorted(rendered.items())}


def _sha256(path: Path) -> str:
    return hashlib.sha256((PROJECT_ROOT / path).read_bytes()).hexdigest()


def _report_hash(payload: dict[str, Any]) -> str:
    body = dict(payload)
    body.pop("report_hash", None)
    return canonical_hash(body)


def _model_indexes(model: dict[str, Any]) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    family_by_slug = {row["slug"]: row["id"] for row in model["lever_families"]}
    lever_families = {
        row["id"]: family_by_slug[row["family"]] for row in model["developmental_levers"]
    }
    mappings = {row["competency_id"]: row for row in model["competency_lever_links"]}
    return lever_families, mappings


def build_report() -> dict[str, Any]:
    scoring_contract = yaml.safe_load((PROJECT_ROOT / SCORING_CONTRACT_PATH).read_text())
    scoring_schema = json.loads((PROJECT_ROOT / SCORING_CONTRACT_SCHEMA_PATH).read_text())
    Draft202012Validator.check_schema(scoring_schema)
    scoring_errors = sorted(
        Draft202012Validator(scoring_schema).iter_errors(scoring_contract),
        key=lambda item: list(item.path),
    )
    if scoring_errors:
        raise CompositeCatalogError(
            "Composite scoring contract schema validation failed: "
            + "; ".join(error.message for error in scoring_errors[:8])
        )
    policy = policy_from_contract(scoring_contract)
    canonical = load_and_validate_bundle()
    practices = load_practice_content_bundle(PROJECT_ROOT)
    protocols = practices.runtime_protocols
    lever_families, mappings = _model_indexes(canonical.model)
    competencies = {
        competency["id"]: {
            "domain_id": str(domain["id"]),
            "name": competency["name"],
        }
        for domain in canonical.curriculum["domains"]
        for competency in domain["competencies"]
    }
    protocols_by_competency: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for protocol in protocols:
        protocols_by_competency[protocol["parent_competency_id"]].append(protocol)
    if set(competencies) != set(mappings) or set(competencies) != set(protocols_by_competency):
        raise CompositeCatalogError("Competency, relationship, and practice coverage disagree.")
    duplicate_protocols = {
        competency_id: rows
        for competency_id, rows in protocols_by_competency.items()
        if len(rows) != 1
    }
    if duplicate_protocols:
        raise CompositeCatalogError(
            f"Every competency requires exactly one runtime practice: {sorted(duplicate_protocols)}"
        )

    family_mass: dict[str, Decimal] = defaultdict(Decimal)
    lever_mass: dict[str, Decimal] = defaultdict(Decimal)
    lever_competencies: dict[str, set[str]] = defaultdict(set)
    family_competencies: dict[str, set[str]] = defaultdict(set)
    domain_members: dict[str, list[str]] = defaultdict(list)
    action_distribution: Counter[int] = Counter()
    threshold_distribution: Counter[tuple[int, int]] = Counter()
    relationship_distribution: Counter[int] = Counter()
    rows: list[dict[str, Any]] = []

    for competency_id in sorted(competencies):
        competency = competencies[competency_id]
        protocol = protocols_by_competency[competency_id][0]
        canonical_weights = {
            lever_id: Decimal(str(weight))
            for lever_id, weight in mappings[competency_id]["lever_weights"].items()
        }
        blended = blended_relationship_weights(canonical_weights, policy)
        serialized_blended = _allocation_strings(blended)
        equal_share = Decimal("1") / Decimal(len(canonical_weights))
        relationships = []
        maximum_canonical = max(canonical_weights.values())
        competency_family_mass: dict[str, Decimal] = defaultdict(Decimal)
        for lever_id in sorted(canonical_weights):
            family_id = lever_families[lever_id]
            weight = Decimal(serialized_blended[lever_id])
            relationships.append(
                {
                    "lever_id": lever_id,
                    "family_id": family_id,
                    "canonical_weight": _decimal_string(canonical_weights[lever_id]),
                    "equal_share_weight": _decimal_string(equal_share),
                    "blended_weight": serialized_blended[lever_id],
                    "relationship_role": (
                        "primary"
                        if canonical_weights[lever_id] == maximum_canonical
                        else "secondary"
                    ),
                }
            )
            competency_family_mass[family_id] += weight
            family_mass[family_id] += weight
            lever_mass[lever_id] += weight
            lever_competencies[lever_id].add(competency_id)
            family_competencies[family_id].add(competency_id)
        family_allocation = _allocation_strings(dict(competency_family_mass))

        actions = sorted(
            protocol["actions"], key=lambda item: (item["sequence"], item["stable_id"])
        )
        total_actions = len(actions)
        minimum_completed = int(protocol["completion_rules"]["minimum_completed"])
        credit_schedule = [
            {
                "completed_actions": completed,
                "completion_credit": _decimal_string(
                    closeout_credit(
                        completed_actions=completed,
                        total_actions=total_actions,
                        minimum_completed=minimum_completed,
                        policy=policy,
                    )
                ),
            }
            for completed in range(minimum_completed, total_actions + 1)
        ]
        action_distribution[total_actions] += 1
        threshold_distribution[(total_actions, minimum_completed)] += 1
        relationship_distribution[len(relationships)] += 1
        domain_members[competency["domain_id"]].append(competency_id)
        rows.append(
            {
                "competency_id": competency_id,
                "competency_name": competency["name"],
                "domain_id": competency["domain_id"],
                "protocol_id": protocol["stable_id"],
                "action_ids": [action["stable_id"] for action in actions],
                "action_dispositions": [
                    {
                        "action_id": action["stable_id"],
                        "completion_units": 1,
                        "score_effect_before_closeout": "none",
                    }
                    for action in actions
                ],
                "total_actions": total_actions,
                "minimum_completed": minimum_completed,
                "relationships": relationships,
                "family_allocation": family_allocation,
                "assessment_component_weights": {
                    "mapped_lever": _decimal_string(policy.competency_lever_weight),
                    "mapped_family": _decimal_string(policy.competency_family_weight),
                    "parent_domain": _decimal_string(policy.competency_domain_weight),
                },
                "priority_component_weights": {
                    "mapped_lever": _decimal_string(policy.priority_lever_weight),
                    "mapped_family": _decimal_string(policy.priority_family_weight),
                    "parent_domain": _decimal_string(policy.priority_domain_weight),
                },
                "credit_schedule": credit_schedule,
                "score_trigger": "explicit_human_final_closeout",
                "check_in_score_effect": "none",
                "repeated_closeout_aggregation": "maximum_active_credit",
                "completion_claim": "bounded_completion_credit_not_mastery",
            }
        )

    counts = {
        "families": len(canonical.model["lever_families"]),
        "levers": len(canonical.model["developmental_levers"]),
        "domains": len(canonical.curriculum["domains"]),
        "competencies": len(competencies),
        "practices": len(protocols),
        "actions": sum(len(protocol["actions"]) for protocol in protocols),
        "relationship_allocations": sum(len(row["relationships"]) for row in rows),
    }
    expected = {
        "families": policy.expected_families,
        "levers": policy.expected_levers,
        "domains": policy.expected_domains,
        "competencies": policy.expected_competencies,
        "practices": policy.expected_practices,
        "actions": policy.expected_actions,
    }
    if {key: counts[key] for key in expected} != expected:
        raise CompositeCatalogError(
            f"Catalog counts do not match the scoring contract: {counts} != {expected}."
        )
    if set(lever_mass) != set(lever_families):
        raise CompositeCatalogError("Every lever must receive positive relationship mass.")
    family_ids = {row["id"] for row in canonical.model["lever_families"]}
    if set(family_mass) != family_ids:
        raise CompositeCatalogError("Every family must receive positive relationship mass.")
    if len(domain_members) != policy.expected_domains:
        raise CompositeCatalogError("Every domain must receive competency coverage.")

    report: dict[str, Any] = {
        "schema_version": CONTRACT_VERSION,
        "scoring_contract_version": policy.algorithm_version,
        "source_hashes": {
            "canonical_model": canonical.source_hash,
            "practice_content": practices.content_hash,
            "scoring_contract": _sha256(SCORING_CONTRACT_PATH),
            "scoring_schema": _sha256(SCORING_CONTRACT_SCHEMA_PATH),
        },
        "counts": counts,
        "formulas": {
            "relationship_blend": "0.50 * canonical + 0.50 * equal share",
            "assessment_composite": (
                "0.50 * mapped lever + 0.25 * mapped family + 0.25 * parent domain"
            ),
            "minimum_closeout_credit": _decimal_string(policy.minimum_closeout_credit),
            "full_closeout_credit": _decimal_string(policy.full_closeout_credit),
            "between_minimum_and_full": "linear",
            "remaining_need": "assessment starting need * sqrt(1 - earned coverage)",
            "own_remaining_credit": "sqrt(1 - competency completion credit)",
        },
        "distributions": {
            "actions_per_practice": {
                str(key): value for key, value in sorted(action_distribution.items())
            },
            "completion_thresholds": {
                f"{total}_actions_min_{minimum}": value
                for (total, minimum), value in sorted(threshold_distribution.items())
            },
            "relationships_per_competency": {
                str(key): value for key, value in sorted(relationship_distribution.items())
            },
        },
        "lever_coverage": [
            {
                "lever_id": lever_id,
                "family_id": lever_families[lever_id],
                "competency_count": len(lever_competencies[lever_id]),
                "catalog_relationship_mass": _decimal_string(lever_mass[lever_id]),
            }
            for lever_id in sorted(lever_families)
        ],
        "family_coverage": [
            {
                "family_id": family_id,
                "competency_count": len(family_competencies[family_id]),
                "catalog_relationship_mass": _decimal_string(family_mass[family_id]),
            }
            for family_id in sorted(family_ids)
        ],
        "domain_coverage": [
            {
                "domain_id": domain_id,
                "competency_count": len(members),
                "coverage_rollup": "equal_member_mean",
            }
            for domain_id, members in sorted(domain_members.items())
        ],
        "competencies": rows,
        "disposition_summary": {
            "assessment_initializes_priority_only": len(rows),
            "check_ins_without_score_effect": len(rows),
            "human_closeout_scored_practices": len(rows),
            "maximum_not_sum_repetition_rule": len(rows),
            "actions_with_equal_completion_units": counts["actions"],
            "actions_with_pre_closeout_score_effect": 0,
            "missing_score_dispositions": 0,
            "mastery_claims": 0,
        },
        "governance": {
            "specialist_review_id": "ER-M6A-003",
            "specialist_review_status": "pending",
            "specialist_review_complete": False,
            "research_gap_id": "RG-M6A-002",
            "research_gap_status": "open",
            "m6b_accepted": False,
        },
        "claim_boundary": (
            "Deterministic owner-approved software allocation and closeout-credit disposition; "
            "not specialist validation, participant validation, mastery, diagnosis, qualification, "
            "or a measure of human worth."
        ),
    }
    report["report_hash"] = _report_hash(report)
    return report


def _validate(report: dict[str, Any]) -> None:
    schema = json.loads((PROJECT_ROOT / SCHEMA_PATH).read_text())
    errors = sorted(
        Draft202012Validator(schema).iter_errors(report), key=lambda item: list(item.path)
    )
    if errors:
        raise CompositeCatalogError(
            "Composite catalog schema validation failed: "
            + "; ".join(error.message for error in errors[:8])
        )
    if report["report_hash"] != _report_hash(report):
        raise CompositeCatalogError("Composite catalog report hash does not verify.")


def _render(report: dict[str, Any]) -> bytes:
    return (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the deterministic composite scoring catalog."
    )
    parser.add_argument(
        "--check", action="store_true", help="Fail if the committed report is stale."
    )
    args = parser.parse_args()
    try:
        report = build_report()
        _validate(report)
    except (CompositeCatalogError, CompositeScoringError, OSError, ValueError) as exc:
        print(f"composite scoring catalog failed: {exc}", file=sys.stderr)
        return 1
    rendered = _render(report)
    output = PROJECT_ROOT / REPORT_PATH
    if args.check:
        if not output.exists() or output.read_bytes() != rendered:
            print(f"composite scoring catalog is stale: {REPORT_PATH}", file=sys.stderr)
            return 1
        print(
            "composite scoring catalog verified: "
            f"{report['counts']['competencies']} competencies, "
            f"{report['counts']['actions']} actions, no missing dispositions"
        )
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(rendered)
    print(f"wrote {REPORT_PATH} ({report['report_hash']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
