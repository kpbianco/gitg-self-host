#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "grounded_growth.settings_test")

import django  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402

django.setup()

from growth.domain.practice_content import (  # noqa: E402
    FROZEN_LEGACY_PROTOCOL_IDS,
    TYPED_RUNTIME_PROJECTION_VERSION,
    load_practice_content_bundle,
    protocol_sources_complete,
)
from growth.services.canonical_import import load_and_validate_bundle  # noqa: E402
from growth.services.practice_content_reports import (  # noqa: E402
    REPORT_PATHS,
    build_practice_report_outputs,
)

CONTRACT_VERSION = "GG-CATALOG-GOVERNANCE-AUDIT-1.0"
REPORT_ROOT = Path("reports/practice-content")
AUDIT_PATH = REPORT_ROOT / "catalog_governance_audit_v1.json"
FINDINGS_PATH = REPORT_ROOT / "catalog_governance_findings_v1.csv"
REVIEW_QUEUE_PATH = REPORT_ROOT / "catalog_governance_review_queue_v1.csv"
REVIEW_PACKET_PATH = REPORT_ROOT / "catalog_governance_review_packet_v1.md"
SCHEMA_PATH = Path("contracts/catalog-governance-audit.schema.json")
EXPECTED_PACKAGES = 383
EXPECTED_ACTIONS = 1151
EXPECTED_LEGACY_PACKAGES = 5
EXPECTED_TYPED_PACKAGES = 378
EXPECTED_GENERATED_ADDITIONS = 374
SEVERITY_PRIORITY = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
SENSITIVE_EVIDENCE_KEY_TOKENS = {
    "artifact_content",
    "credential",
    "diagnosis",
    "free_text",
    "identity",
    "narrative",
    "observer_name",
    "password",
    "private_prose",
    "secret",
}
FINDING_FIELDS = [
    "finding_id",
    "category",
    "severity",
    "status",
    "summary",
    "objective_evidence",
    "affected_stable_ids",
    "remediation_class",
    "remediation_dependency",
    "required_roles",
]
REVIEW_FIELDS = [
    "priority_rank",
    "finding_id",
    "severity",
    "required_roles",
    "risk_classes",
    "domain_ids",
    "protocol_families",
    "evidence_kinds",
    "remediation_dependency",
    "affected_stable_ids",
    "summary",
    "status",
]


class CatalogGovernanceAuditError(ValueError):
    pass


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def _csv_bytes(rows: list[dict[str, Any]], fieldnames: list[str]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def _sha256_json(payload: Any) -> str:
    rendered = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(rendered).hexdigest()


def _stable_token(location: str) -> str:
    return location.split(".", 1)[0]


def _protocol_token(location: str) -> str:
    return re.sub(r"-A\d+$", "", _stable_token(location))


def _stable_finding_id(
    category: str,
    affected_stable_ids: Iterable[str],
    objective_evidence: dict[str, Any],
) -> str:
    signature = {
        "category": category,
        "affected_stable_ids": sorted(set(affected_stable_ids)),
        "objective_evidence": objective_evidence,
    }
    digest = _sha256_json(signature)[:16].upper()
    category_token = re.sub(r"[^A-Z0-9]+", "-", category.upper()).strip("-")
    return f"CGA-{category_token}-{digest}"


def _finding(
    *,
    category: str,
    severity: str,
    summary: str,
    objective_evidence: dict[str, Any],
    affected_stable_ids: Iterable[str],
    remediation_class: str,
    remediation_dependency: str,
    required_roles: Iterable[str],
) -> dict[str, Any]:
    affected = sorted(set(affected_stable_ids))
    roles = sorted(set(required_roles))
    return {
        "finding_id": _stable_finding_id(category, affected, objective_evidence),
        "category": category,
        "severity": severity,
        "status": "open",
        "summary": summary,
        "objective_evidence": objective_evidence,
        "affected_stable_ids": affected,
        "remediation_class": remediation_class,
        "remediation_dependency": remediation_dependency,
        "required_roles": roles,
    }


def _canonical_indexes(canonical: Any) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    competencies: dict[str, dict[str, Any]] = {}
    for domain in canonical.curriculum["domains"]:
        domain_id = str(domain["id"])
        for competency in domain["competencies"]:
            competencies[competency["id"]] = {**competency, "domain_id": domain_id}
    mappings = {
        link["competency_id"]: {
            lever_id: str(weight) for lever_id, weight in link["lever_weights"].items()
        }
        for link in canonical.model["competency_lever_links"]
    }
    return competencies, mappings


def _protocol_paths(base_dir: Path, practices: Any) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    practice_root = base_dir / "data" / "practices"
    for relative in practices.release_manifest["protocol_files"]:
        path = practice_root / relative
        paths[path.stem] = path
    return paths


def _evidence_kinds(action: dict[str, Any]) -> tuple[str, ...]:
    rules = action["evidence_rules"]
    if rules["schema_version"] == "practice-observation-v1":
        return ("legacy_marker",)
    return tuple(sorted({measurement["kind"] for measurement in rules["measurements"]}))


def _measurement_ids(action: dict[str, Any]) -> tuple[str, ...]:
    rules = action["evidence_rules"]
    if rules["schema_version"] == "practice-observation-v1":
        return tuple(sorted(rules["primary_markers"] + rules["supporting_markers"]))
    return tuple(sorted(measurement["measurement_id"] for measurement in rules["measurements"]))


def _sensitive_rule_keys(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            path = f"{prefix}.{key}" if prefix else key
            normalized = key.casefold()
            if normalized in SENSITIVE_EVIDENCE_KEY_TOKENS or any(
                token in normalized for token in SENSITIVE_EVIDENCE_KEY_TOKENS
            ):
                findings.append(path)
            findings.extend(_sensitive_rule_keys(nested, path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_sensitive_rule_keys(nested, f"{prefix}[{index}]"))
    return findings


def _duplicate_findings(
    originality: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, set[str]], dict[str, set[str]]]:
    findings: list[dict[str, Any]] = []
    exact_by_protocol: dict[str, set[str]] = defaultdict(set)
    near_by_protocol: dict[str, set[str]] = defaultdict(set)
    exact = originality["exact_or_normalized_duplicates"]
    for category in sorted(exact):
        for group in exact[category]:
            locations = sorted(group.get("locations", []))
            if not locations:
                continue
            affected = sorted({_stable_token(location) for location in locations})
            protocol_ids = sorted({_protocol_token(location) for location in locations})
            evidence = {
                "category": category,
                "classification": group.get("classification", "review_required"),
                "locations": locations,
                "normalized_sha256": group.get("normalized_sha256"),
            }
            finding = _finding(
                category=f"exact_duplicate_{category}",
                severity="moderate",
                summary=f"Exact or normalized duplicate candidate in {category} requires review.",
                objective_evidence=evidence,
                affected_stable_ids=affected,
                remediation_class="human_semantic_review",
                remediation_dependency="trained_content_and_originality_review",
                required_roles=("trained content reviewer",),
            )
            findings.append(finding)
            for protocol_id in protocol_ids:
                exact_by_protocol[protocol_id].add(finding["finding_id"])

    near = originality["near_duplicate_warnings"]
    for category in sorted(near):
        candidates = near[category]
        if not isinstance(candidates, list):
            continue
        for pair in candidates:
            if not isinstance(pair, dict) or "left" not in pair or "right" not in pair:
                continue
            locations = [pair["left"], pair["right"]]
            affected = sorted({_stable_token(location) for location in locations})
            protocol_ids = sorted({_protocol_token(location) for location in locations})
            evidence = {
                "category": category,
                "left": pair["left"],
                "right": pair["right"],
                "similarity": pair["similarity"],
            }
            finding = _finding(
                category=f"near_duplicate_{category}",
                severity="low",
                summary=f"Near-duplicate candidate in {category} requires review.",
                objective_evidence=evidence,
                affected_stable_ids=affected,
                remediation_class="human_semantic_review",
                remediation_dependency="trained_content_and_originality_review",
                required_roles=("trained content reviewer",),
            )
            findings.append(finding)
            for protocol_id in protocol_ids:
                near_by_protocol[protocol_id].add(finding["finding_id"])

    for signal in originality["evidence_markers_that_only_restate_completion"]:
        stable_id = signal["protocol_stable_id"]
        findings.append(
            _finding(
                category="completion_marker_restatement",
                severity="moderate",
                summary=f"{stable_id} has an evidence marker that may only restate completion.",
                objective_evidence=signal,
                affected_stable_ids=(stable_id,),
                remediation_class="human_measurement_review",
                remediation_dependency="measurement_and_content_review",
                required_roles=("measurement specialist", "trained content reviewer"),
            )
        )

    operationalization_signals = originality["parent_competency_operationalization_signals"]
    for signal in operationalization_signals:
        stable_id = signal["protocol_stable_id"]
        findings.append(
            _finding(
                category="operationalization_review_pending",
                severity="moderate",
                summary=(
                    f"{stable_id} has an automated lexical signal but still requires human "
                    "operationalization review."
                ),
                objective_evidence=signal,
                affected_stable_ids=(stable_id,),
                remediation_class="human_semantic_and_measurement_review",
                remediation_dependency="trained_content_and_measurement_review",
                required_roles=("measurement specialist", "trained content reviewer"),
            )
        )

    structure = originality["structure_warnings"]
    findings.append(
        _finding(
            category="catalog_structural_repetition_signal",
            severity="low",
            summary="Catalog-wide action-count and duration repetition requires human review.",
            objective_evidence=structure,
            affected_stable_ids=sorted(
                signal["protocol_stable_id"] for signal in operationalization_signals
            ),
            remediation_class="human_originality_review",
            remediation_dependency="trained_content_and_originality_review",
            required_roles=("trained content reviewer",),
        )
    )
    legacy_source = originality["legacy_notion_source_audit"]
    findings.append(
        _finding(
            category="legacy_source_journal_prompt_duplication",
            severity="moderate",
            summary="The legacy Notion source repeats one journal prompt across all 383 rows.",
            objective_evidence=legacy_source,
            affected_stable_ids=sorted(
                signal["protocol_stable_id"] for signal in operationalization_signals
            ),
            remediation_class="source_defect_retention",
            remediation_dependency="do_not_propagate_legacy_source_defect",
            required_roles=("trained source reviewer", "trained content reviewer"),
        )
    )
    return findings, exact_by_protocol, near_by_protocol


def _review_findings(
    protocol: dict[str, Any],
    practices: Any,
    evidence_kinds: tuple[str, ...],
) -> list[dict[str, Any]]:
    stable_id = protocol["stable_id"]
    governance = protocol["governance"]
    authoring = governance["authoring"]
    risk = practices.risk_classes[governance["risk_class_id"]]
    findings: list[dict[str, Any]] = []
    fields = (
        (
            "content_review_status",
            "content_review_pending",
            "trained content reviewer",
            "human_semantic_review",
        ),
        (
            "research_review_status",
            "source_review_pending",
            "trained source reviewer",
            "human_source_review",
        ),
        (
            "originality_review_status",
            "originality_review_pending",
            "trained content reviewer",
            "human_originality_review",
        ),
        (
            "accessibility_review_status",
            "accessibility_review_pending",
            "accessibility reviewer",
            "human_accessibility_review",
        ),
        (
            "safety_review_status",
            "safety_review_pending",
            risk["required_reviewer_role"],
            "human_safety_review",
        ),
    )
    completed_statuses = {"complete", "completed", "approved", "reviewed"}
    for field, category, role, remediation_class in fields:
        status = str(authoring[field])
        if status in completed_statuses:
            continue
        findings.append(
            _finding(
                category=category,
                severity="high" if governance["risk_class_id"] == "RISK-HIGH" else "moderate",
                summary=f"{stable_id} retains {field.replace('_', ' ')}: {status}.",
                objective_evidence={
                    "authoring_field": field,
                    "recorded_status": status,
                    "risk_class": governance["risk_class_id"],
                },
                affected_stable_ids=(stable_id,),
                remediation_class=remediation_class,
                remediation_dependency=f"manual_{category}",
                required_roles=(role,),
            )
        )

    if not protocol_sources_complete(practices, protocol):
        findings.append(
            _finding(
                category="source_completeness_pending",
                severity="moderate",
                summary=(
                    f"{stable_id} has valid source metadata but does not meet release completeness."
                ),
                objective_evidence={
                    "source_ids": sorted(governance["source_ids"]),
                    "sources_complete": False,
                },
                affected_stable_ids=(stable_id,),
                remediation_class="human_source_review",
                remediation_dependency="claim_level_external_source_review",
                required_roles=("trained source reviewer",),
            )
        )

    activation = practices.activation_entries[stable_id]
    pending_fields = sorted(
        field
        for field in (
            "content_review_status",
            "research_review_status",
            "originality_review_status",
            "accessibility_review_status",
            "safety_review_status",
        )
        if str(authoring[field]) not in completed_statuses
    )
    if activation["score_active"] and pending_fields:
        findings.append(
            _finding(
                category="active_pending_governance",
                severity="high",
                summary=(
                    f"{stable_id} is owner-directed score active while required catalog review "
                    "remains pending."
                ),
                objective_evidence={
                    "activation_status": activation["activation_status"],
                    "score_active": True,
                    "pending_authoring_fields": pending_fields,
                    "evidence_kinds": list(evidence_kinds),
                },
                affected_stable_ids=(stable_id,),
                remediation_class="manual_governance",
                remediation_dependency="M6B-GOV",
                required_roles=(
                    "owner",
                    "measurement specialist",
                    "accessibility reviewer",
                    "privacy and safety reviewer",
                ),
            )
        )
    return findings


def _global_governance_findings(practices: Any) -> list[dict[str, Any]]:
    protocol_ids = sorted(protocol["stable_id"] for protocol in practices.protocols)
    expert = practices.expert_reviews["ER-M6A-003"]
    gap = practices.research_gaps["RG-M6A-002"]
    return [
        _finding(
            category="expert_review_gate_pending",
            severity="high",
            summary="ER-M6A-003 remains pending and blocks M6B governance acceptance.",
            objective_evidence={
                "review_id": expert["review_id"],
                "status": expert["status"],
                "required_roles": sorted(expert["required_roles"]),
                "completed_roles": sorted(expert["completed_roles"]),
                "completed_on": expert["completed_on"],
                "decision_reference": expert["decision_reference"],
            },
            affected_stable_ids=protocol_ids,
            remediation_class="manual_specialist_review",
            remediation_dependency="M6B-GOV",
            required_roles=expert["required_roles"],
        ),
        _finding(
            category="research_gap_open",
            severity="high",
            summary="RG-M6A-002 remains open and cannot be resolved by software audit output.",
            objective_evidence={
                "gap_id": gap["gap_id"],
                "status": gap["status"],
                "priority": gap["priority"],
            },
            affected_stable_ids=protocol_ids,
            remediation_class="manual_governance",
            remediation_dependency="ER-M6A-003_and_M6B-GOV",
            required_roles=(
                "measurement specialist",
                "accessibility reviewer",
                "privacy and safety reviewer",
                "owner",
            ),
        ),
    ]


def _status(
    status: str, evidence: dict[str, Any], finding_ids: Iterable[str] = ()
) -> dict[str, Any]:
    return {
        "status": status,
        "objective_evidence": evidence,
        "finding_ids": sorted(set(finding_ids)),
    }


def _audit_rows(
    base_dir: Path,
    canonical: Any,
    practices: Any,
    exact_by_protocol: dict[str, set[str]],
    near_by_protocol: dict[str, set[str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    competencies, mappings = _canonical_indexes(canonical)
    paths = _protocol_paths(base_dir, practices)
    package_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for protocol in sorted(practices.protocols, key=lambda item: item["stable_id"]):
        stable_id = protocol["stable_id"]
        governance = protocol["governance"]
        authoring = governance["authoring"]
        intervention = protocol["intervention"]
        evidence = protocol["evidence_and_scoring"]
        activation = practices.activation_entries[stable_id]
        actions = sorted(intervention["actions"], key=lambda item: item["sequence"])
        package_evidence_kinds = tuple(
            sorted({kind for action in actions for kind in _evidence_kinds(action)})
        )
        privacy_key_paths = sorted(
            {
                f"{action['stable_id']}.{key_path}"
                for action in actions
                for key_path in _sensitive_rule_keys(action["evidence_rules"])
            }
        )
        privacy_finding_ids: list[str] = []
        if privacy_key_paths:
            finding = _finding(
                category="privacy_allowlist_violation",
                severity="critical",
                summary=f"{stable_id} evidence rules contain sensitive or narrative field names.",
                objective_evidence={"field_paths": privacy_key_paths},
                affected_stable_ids=(stable_id,),
                remediation_class="objective_structural_repair",
                remediation_dependency="before_audit_acceptance",
                required_roles=("privacy and safety reviewer",),
            )
            findings.append(finding)
            privacy_finding_ids.append(finding["finding_id"])
        findings.extend(_review_findings(protocol, practices, package_evidence_kinds))

        # This is historical cohort membership, not a claim about current
        # editorial quality. Rewriting provenance must not move a frontier
        # package into the four original representative typed packages.
        generated_addition = stable_id.startswith("PRACTICE-COMP-")
        cohort = (
            "legacy"
            if stable_id in FROZEN_LEGACY_PROTOCOL_IDS
            else "generated_addition"
            if generated_addition
            else "representative_typed"
        )
        pending_review_fields = sorted(
            field
            for field in (
                "content_review_status",
                "research_review_status",
                "originality_review_status",
                "accessibility_review_status",
                "safety_review_status",
            )
            if "pending" in str(authoring[field])
            or str(authoring[field]) in {"internal_sources_only_external_review_required"}
        )
        exact_ids = exact_by_protocol.get(stable_id, set())
        near_ids = near_by_protocol.get(stable_id, set())
        source_ids = sorted(governance["source_ids"])
        source_metadata_valid = all(
            all(
                practices.sources[source_id].get(key) not in (None, "", [])
                for key in (
                    "title",
                    "authors_or_issuing_body",
                    "locator",
                    "source_class",
                    "evidence_strength",
                    "supported_claim",
                    "claim_classification",
                    "limitations",
                )
            )
            for source_id in source_ids
        )
        dispositions = {
            "schema_completeness": _status(
                "pass",
                {"schema_version": protocol["schema_version"], "validated_by_loader": True},
            ),
            "stable_id_uniqueness": _status(
                "pass", {"protocol_stable_id": stable_id, "action_ids_unique": True}
            ),
            "mapping_validity": _status(
                "pass",
                {
                    "parent_competency_id": protocol["parent_competency_id"],
                    "parent_lever_ids": sorted(mappings[protocol["parent_competency_id"]]),
                    "recommendation_target_lever_ids": sorted(
                        evidence["recommendation_target_lever_ids"]
                    ),
                },
            ),
            "evidence_rule_executability": _status(
                "pass",
                {
                    "action_count": len(actions),
                    "rule_versions": sorted(
                        {action["evidence_rules"]["schema_version"] for action in actions}
                    ),
                    "evidence_kinds": list(package_evidence_kinds),
                },
            ),
            "privacy_field_allowlist": _status(
                "blocker" if privacy_key_paths else "pass_structural_review_pending",
                {
                    "sensitive_rule_key_paths": privacy_key_paths,
                    "privacy_boundary_present": bool(
                        intervention["privacy_and_boundaries"].strip()
                    ),
                },
                privacy_finding_ids,
            ),
            "source_metadata": _status(
                "metadata_valid_review_incomplete",
                {
                    "source_ids": source_ids,
                    "metadata_valid": source_metadata_valid,
                    "sources_complete": protocol_sources_complete(practices, protocol),
                },
            ),
            "exact_duplicate_candidates": _status(
                "review_required" if exact_ids else "none_detected",
                {"candidate_count": len(exact_ids)},
                exact_ids,
            ),
            "near_duplicate_candidates": _status(
                "review_required" if near_ids else "none_detected",
                {"candidate_count": len(near_ids)},
                near_ids,
            ),
            "accessibility_adaptation_fields": _status(
                "present_review_pending",
                {
                    "adaptation_count": len(intervention["adaptations"]["accessibility"]),
                    "review_status": authoring["accessibility_review_status"],
                },
            ),
            "safety_stop_and_escalation_fields": _status(
                "present_review_pending",
                {
                    "stop_condition_count": len(intervention["stop_conditions"]),
                    "escalation_condition_count": len(intervention["escalation_conditions"]),
                    "professional_referral_count": len(
                        intervention["professional_referral_conditions"]
                    ),
                    "review_status": authoring["safety_review_status"],
                },
            ),
            "activation_review_consistency": _status(
                "owner_directed_active_review_pending",
                {
                    "activation_status": activation["activation_status"],
                    "score_active": activation["score_active"],
                    "pending_review_fields": pending_review_fields,
                },
            ),
        }
        path = paths[stable_id]
        package_rows.append(
            {
                "protocol_stable_id": stable_id,
                "parent_competency_id": protocol["parent_competency_id"],
                "domain_id": protocol["domain_id"],
                "protocol_path": path.relative_to(base_dir).as_posix(),
                "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "cohort": cohort,
                "runtime_projection": governance["runtime_projection"],
                "protocol_family_id": intervention["protocol_class"],
                "risk_class_id": governance["risk_class_id"],
                "evidence_kinds": list(package_evidence_kinds),
                "scoring_policy_id": governance["scoring_policy_id"],
                "activation_status": activation["activation_status"],
                "score_active": activation["score_active"],
                "source_ids": source_ids,
                "research_gap_ids": sorted(authoring["known_gap_ids"]),
                "expert_review_ids": sorted(authoring["expert_review_ids"]),
                "parent_mapping_lever_ids": sorted(mappings[protocol["parent_competency_id"]]),
                "recommendation_target_lever_ids": sorted(
                    evidence["recommendation_target_lever_ids"]
                ),
                "action_ids": [action["stable_id"] for action in actions],
                "dispositions": dispositions,
            }
        )
        action_rows.extend(
            {
                "action_stable_id": action["stable_id"],
                "protocol_stable_id": stable_id,
                "parent_competency_id": protocol["parent_competency_id"],
                "domain_id": protocol["domain_id"],
                "sequence": action["sequence"],
                "evidence_schema_version": action["evidence_rules"]["schema_version"],
                "evidence_kinds": list(_evidence_kinds(action)),
                "measurement_ids": list(_measurement_ids(action)),
                "scoring_policy_id": governance["scoring_policy_id"],
                "score_active": activation["score_active"],
                "content_sha256": _sha256_json(action),
                "schema_completeness": "pass",
                "stable_id_uniqueness": "pass",
                "evidence_rule_executability": "pass",
                "privacy_field_allowlist": (
                    "blocker"
                    if _sensitive_rule_keys(action["evidence_rules"])
                    else "pass_structural_review_pending"
                ),
            }
            for action in actions
        )
    if set(competencies) != {row["parent_competency_id"] for row in package_rows}:
        raise CatalogGovernanceAuditError(
            "Package audit does not have a one-to-one match with canonical competency IDs."
        )
    return package_rows, action_rows, findings


def _inventory(payloads: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(payload[key]) for payload in payloads).items()))


def _list_inventory(payloads: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(value for payload in payloads for value in payload[key]).items()))


def _review_rows(
    findings: list[dict[str, Any]], package_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    package_by_id = {row["protocol_stable_id"]: row for row in package_rows}
    rows: list[dict[str, Any]] = []
    ordered = sorted(
        findings,
        key=lambda item: (
            SEVERITY_PRIORITY[item["severity"]],
            item["remediation_dependency"],
            item["finding_id"],
        ),
    )
    for rank, finding in enumerate(ordered, start=1):
        protocols = sorted(
            {
                _protocol_token(stable_id)
                for stable_id in finding["affected_stable_ids"]
                if _protocol_token(stable_id) in package_by_id
            }
        )
        affected_rows = [package_by_id[protocol_id] for protocol_id in protocols]
        rows.append(
            {
                "priority_rank": rank,
                "finding_id": finding["finding_id"],
                "severity": finding["severity"],
                "required_roles": ";".join(finding["required_roles"]),
                "risk_classes": ";".join(sorted({row["risk_class_id"] for row in affected_rows})),
                "domain_ids": ";".join(sorted({row["domain_id"] for row in affected_rows})),
                "protocol_families": ";".join(
                    sorted({row["protocol_family_id"] for row in affected_rows})
                ),
                "evidence_kinds": ";".join(
                    sorted({kind for row in affected_rows for kind in row["evidence_kinds"]})
                ),
                "remediation_dependency": finding["remediation_dependency"],
                "affected_stable_ids": ";".join(finding["affected_stable_ids"]),
                "summary": finding["summary"],
                "status": finding["status"],
            }
        )
    return rows


def _finding_csv_rows(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **finding,
            "objective_evidence": json.dumps(
                finding["objective_evidence"], separators=(",", ":"), sort_keys=True
            ),
            "affected_stable_ids": ";".join(finding["affected_stable_ids"]),
            "required_roles": ";".join(finding["required_roles"]),
        }
        for finding in sorted(findings, key=lambda item: item["finding_id"])
    ]


def _review_packet(audit: dict[str, Any], findings: list[dict[str, Any]]) -> bytes:
    severity_counts = Counter(finding["severity"] for finding in findings)
    role_counts = Counter(role for finding in findings for role in finding["required_roles"])
    dependency_counts = Counter(finding["remediation_dependency"] for finding in findings)
    lines = [
        "# Catalog governance review packet v1",
        "",
        "## Boundary",
        "",
        audit["claim_boundary"],
        "",
        (
            "All 383 packages are owner-directed runtime and score active. This audit does not "
            "equate activation with source completeness, safety, accessibility, cultural fit, "
            "measurement validity, effectiveness, or specialist acceptance."
        ),
        "",
        "## Coverage",
        "",
        f"- Packages audited: {audit['counts']['packages']}",
        f"- Actions audited: {audit['counts']['actions']}",
        f"- Legacy packages: {audit['counts']['legacy_packages']}",
        f"- Typed packages: {audit['counts']['typed_packages']}",
        f"- Originally generated additions: {audit['counts']['generated_additions']}",
        f"- Open findings: {len(findings)}",
        "",
        "## Governance gates",
        "",
        (
            f"- ER-M6A-003: {audit['governance_gates']['expert_review']['status']} "
            "(completed roles: 0)"
        ),
        f"- RG-M6A-002: {audit['governance_gates']['research_gap']['status']}",
        "- Manual M6B-GOV acceptance remains required.",
        "",
        "## Findings by severity",
        "",
        "| Severity | Count |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {severity} | {severity_counts[severity]} |"
        for severity in ("critical", "high", "moderate", "low")
    )
    lines.extend(
        [
            "",
            "## Review routing by required role",
            "",
            "| Required role | Open findings |",
            "| --- | ---: |",
        ]
    )
    for role, count in sorted(role_counts.items()):
        lines.append(f"| {role} | {count} |")
    lines.extend(
        [
            "",
            "## Review routing by dependency",
            "",
            "| Dependency | Open findings |",
            "| --- | ---: |",
        ]
    )
    for dependency, count in sorted(dependency_counts.items()):
        lines.append(f"| {dependency} | {count} |")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "- `catalog_governance_audit_v1.json`: complete package/action rows and inventories.",
            "- `catalog_governance_findings_v1.csv`: every stable finding and objective evidence.",
            "- `catalog_governance_review_queue_v1.csv`: prioritized routing dimensions.",
            "",
            "No participant or owner-private data is read or written by this static catalog audit.",
            "",
        ]
    )
    return "\n".join(lines).encode()


def build_catalog_governance_audit_outputs(base_dir: Path) -> dict[Path, bytes]:
    resolved_base = base_dir.resolve()
    canonical = load_and_validate_bundle()
    practices = load_practice_content_bundle(resolved_base)
    practice_outputs = build_practice_report_outputs(resolved_base)
    originality = json.loads(practice_outputs[REPORT_PATHS["content_originality"]])
    duplicate_findings, exact_by_protocol, near_by_protocol = _duplicate_findings(originality)
    package_rows, action_rows, row_findings = _audit_rows(
        resolved_base, canonical, practices, exact_by_protocol, near_by_protocol
    )
    findings = duplicate_findings + row_findings + _global_governance_findings(practices)
    finding_ids = [finding["finding_id"] for finding in findings]
    if len(finding_ids) != len(set(finding_ids)):
        duplicates = sorted(
            finding_id for finding_id, count in Counter(finding_ids).items() if count > 1
        )
        raise CatalogGovernanceAuditError(f"Duplicate stable finding IDs: {duplicates}.")
    findings = sorted(findings, key=lambda item: item["finding_id"])
    counts = {
        "packages": len(package_rows),
        "actions": len(action_rows),
        "legacy_packages": sum(row["cohort"] == "legacy" for row in package_rows),
        "typed_packages": sum(
            row["runtime_projection"] == TYPED_RUNTIME_PROJECTION_VERSION for row in package_rows
        ),
        "generated_additions": sum(row["cohort"] == "generated_addition" for row in package_rows),
        "score_active_packages": sum(row["score_active"] for row in package_rows),
        "findings": len(findings),
        "open_findings": sum(finding["status"] == "open" for finding in findings),
    }
    expected_counts = {
        "packages": EXPECTED_PACKAGES,
        "actions": EXPECTED_ACTIONS,
        "legacy_packages": EXPECTED_LEGACY_PACKAGES,
        "typed_packages": EXPECTED_TYPED_PACKAGES,
        "generated_additions": EXPECTED_GENERATED_ADDITIONS,
        "score_active_packages": EXPECTED_PACKAGES,
    }
    mismatches = {
        key: {"expected": expected, "actual": counts[key]}
        for key, expected in expected_counts.items()
        if counts[key] != expected
    }
    if mismatches:
        raise CatalogGovernanceAuditError(f"Catalog audit coverage mismatch: {mismatches}.")
    expert = practices.expert_reviews["ER-M6A-003"]
    gap = practices.research_gaps["RG-M6A-002"]
    if (
        expert["status"] != "pending"
        or expert["completed_roles"]
        or expert["completed_on"] is not None
        or expert["decision_reference"] is not None
        or gap["status"] != "open"
    ):
        raise CatalogGovernanceAuditError(
            "Automated audit requires ER-M6A-003 pending with no completion evidence and "
            "RG-M6A-002 open."
        )
    audit = {
        "contract_version": CONTRACT_VERSION,
        "catalog_content_hash": practices.content_hash,
        "canonical_source_hash": canonical.source_hash,
        "counts": counts,
        "inventories": {
            "domains": _inventory(package_rows, "domain_id"),
            "parent_mapping_levers": _list_inventory(package_rows, "parent_mapping_lever_ids"),
            "recommendation_target_levers": _list_inventory(
                package_rows, "recommendation_target_lever_ids"
            ),
            "protocol_families": _inventory(package_rows, "protocol_family_id"),
            "risk_classes": _inventory(package_rows, "risk_class_id"),
            "evidence_kinds": _list_inventory(package_rows, "evidence_kinds"),
            "source_ids": _list_inventory(package_rows, "source_ids"),
            "research_gap_ids": _list_inventory(package_rows, "research_gap_ids"),
            "expert_review_ids": _list_inventory(package_rows, "expert_review_ids"),
            "activation_statuses": _inventory(package_rows, "activation_status"),
        },
        "governance_gates": {
            "expert_review": {
                "review_id": expert["review_id"],
                "status": expert["status"],
                "required_roles": sorted(expert["required_roles"]),
                "completed_roles": sorted(expert["completed_roles"]),
                "completed_on": expert["completed_on"],
                "decision_reference": expert["decision_reference"],
            },
            "research_gap": {"gap_id": gap["gap_id"], "status": gap["status"]},
            "m6b_accepted": False,
            "manual_contract": "M6B-GOV",
        },
        "activation_review_boundary": {
            "owner_directed_score_active_packages": EXPECTED_PACKAGES,
            "specialist_review_complete": False,
            "source_complete_packages": sum(
                protocol_sources_complete(practices, protocol) for protocol in practices.protocols
            ),
            "software_activation_is_not_governance_acceptance": True,
        },
        "package_rows": package_rows,
        "action_rows": action_rows,
        "findings": findings,
        "privacy": {
            "catalog_static_inputs_only": True,
            "participant_data_read": False,
            "owner_private_data_read": False,
            "participant_or_owner_values_in_reports": False,
        },
        "claim_boundary": (
            "Deterministic static and software governance audit only; no specialist, owner, "
            "participant, accessibility-population, cultural, clinical, psychometric, "
            "longitudinal, release, deployment, mastery, or intervention-effectiveness acceptance."
        ),
    }
    schema = json.loads((resolved_base / SCHEMA_PATH).read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(audit),
        key=lambda item: list(item.path),
    )
    if errors:
        rendered = "; ".join(f"{list(error.path)}: {error.message}" for error in errors[:10])
        raise CatalogGovernanceAuditError(f"Generated audit violates its schema: {rendered}")
    review_rows = _review_rows(findings, package_rows)
    return {
        AUDIT_PATH: _json_bytes(audit),
        FINDINGS_PATH: _csv_bytes(_finding_csv_rows(findings), FINDING_FIELDS),
        REVIEW_QUEUE_PATH: _csv_bytes(review_rows, REVIEW_FIELDS),
        REVIEW_PACKET_PATH: _review_packet(audit, findings),
    }


def write_or_check_catalog_governance_audit(*, base_dir: Path, check: bool) -> tuple[Path, ...]:
    outputs = build_catalog_governance_audit_outputs(base_dir)
    changed: list[Path] = []
    for relative, expected in outputs.items():
        path = base_dir / relative
        actual = path.read_bytes() if path.exists() else None
        if actual == expected:
            continue
        changed.append(relative)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
    if check and changed:
        raise CatalogGovernanceAuditError(
            "Generated catalog-governance reports are missing or stale: "
            + ", ".join(path.as_posix() for path in changed)
        )
    return tuple(changed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate or verify the M6B catalog audit.")
    parser.add_argument(
        "--check", action="store_true", help="Fail when outputs are missing or stale."
    )
    parser.add_argument("--base-dir", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)
    try:
        changed = write_or_check_catalog_governance_audit(
            base_dir=args.base_dir.resolve(), check=args.check
        )
    except (CatalogGovernanceAuditError, OSError, ValueError) as exc:
        print(f"catalog_governance_audit=failed reason={exc}", file=sys.stderr)
        return 1
    mode = "verified" if args.check else "generated"
    print(f"catalog_governance_audit={mode} changed={len(changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
