from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from django.conf import settings

from growth.domain.practice_content import (
    FROZEN_LEGACY_PROTOCOL_IDS,
    PracticeContentError,
    load_practice_content_bundle,
)
from growth.domain.typed_evidence import (
    TYPED_EVIDENCE_ALGORITHM_VERSION,
    TYPED_EVIDENCE_RULES_VERSION,
)
from growth.models import PracticeAction, PracticeProtocol
from growth.services.competency_evidence_readiness import (
    COMPETENCY_EVIDENCE_READINESS_CONTRACT_VERSION,
    CompetencyEvidenceReadinessError,
    verify_competency_evidence_readiness,
)
from growth.services.competency_evidence_reports import (
    CompetencyEvidenceReportError,
    build_competency_evidence_report_outputs,
)
from growth.services.expansion_readiness import (
    EXPANSION_READINESS_CONTRACT_VERSION,
    ExpansionReadinessError,
    verify_expansion_readiness,
)

M6D_AUTHORING_READINESS_CONTRACT_VERSION = "GG-M6D-01-AUTHORING-READINESS-1.0"
M6D_FIXTURE_SCHEMA_VERSION = "grounded-growth-m6d-01-protocol-fixture-v1"
M6D_REPORT_PATH = Path("reports/practice-content/m6d_01_cohort_readiness_v1.json")
M6D_FIXTURE_PATH = Path("tests/fixtures/evidence/m6d_01_protocols_v1.json")


class M6DAuthoringReadinessError(ValueError):
    pass


@dataclass(frozen=True)
class _CohortMember:
    competency_id: str
    domain_id: str
    protocol_stable_id: str
    protocol_family_id: str
    recommendation_target_lever_ids: tuple[str, ...]
    action_count: int


M6D_COHORT = (
    _CohortMember(
        "08.06",
        "08",
        "PRACTICE-MOTIVATION-INDEPENDENT-START-01",
        "PF-BEHAVIORAL-EXPERIMENT",
        ("L10",),
        3,
    ),
    _CohortMember(
        "09.12",
        "09",
        "PRACTICE-DECISION-RECORD-01",
        "PF-ARTIFACT-PLAN",
        ("L14",),
        3,
    ),
    _CohortMember(
        "10.02",
        "10",
        "PRACTICE-DELIBERATE-PRACTICE-01",
        "PF-SKILL-REHEARSAL",
        ("L15",),
        4,
    ),
    _CohortMember(
        "13.02",
        "13",
        "PRACTICE-HOME-UPKEEP-SYSTEM-01",
        "PF-AUDIT-REDESIGN",
        ("L18",),
        4,
    ),
)
_REQUIRED_SAFETY_PRIVACY_TERMS = {
    "PRACTICE-MOTIVATION-INDEPENDENT-START-01": {
        "fatigue",
        "disability",
        "caregiving",
        "sleep",
        "recovery",
        "coercive",
    },
    "PRACTICE-DECISION-RECORD-01": {
        "secrets",
        "legal privilege",
        "third-party",
        "hindsight",
        "rewrite",
    },
    "PRACTICE-DELIBERATE-PRACTICE-01": {
        "high-consequence",
        "clinical rehabilitation",
        "licensed",
        "observer identity",
        "public artifact",
        "coerced",
    },
    "PRACTICE-HOME-UPKEEP-SYSTEM-01": {
        "electrical",
        "gas",
        "mold",
        "tenancy",
        "tradesperson",
        "emergency service",
    },
}


@dataclass(frozen=True)
class M6DAuthoringReadinessSummary:
    contract_version: str
    preserved_expansion_contract_version: str
    preserved_competency_evidence_contract_version: str
    practice_catalog_content_hash: str
    legacy_projection_hash: str
    cohort_report_sha256: str
    fixture_sha256: str
    cohort_competency_ids: tuple[str, ...]
    cohort_protocol_ids: tuple[str, ...]
    cohort_action_count: int
    competencies: int
    source_protocol_packages: int
    source_practice_actions: int
    uncovered_competencies: int
    runtime_protocols: int
    runtime_actions: int
    score_active_protocols: int
    source_typed_protocols: int
    typed_production_protocols: int
    expert_review_id: str
    expert_review_status: str
    research_gap_id: str
    research_gap_status: str
    database_writes: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _require_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise M6DAuthoringReadinessError(f"{label}: expected {expected!r}, found {actual!r}.")


def _read_json_object(path: Path, *, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise M6DAuthoringReadinessError(f"{label} {path} is missing or malformed: {exc}") from exc
    if not isinstance(payload, dict):
        raise M6DAuthoringReadinessError(f"{label} {path} must contain one JSON object.")
    return payload, raw


def _verify_report(base_dir: Path, catalog_hash: str) -> tuple[dict[str, Any], str]:
    try:
        outputs = build_competency_evidence_report_outputs(base_dir)
    except (CompetencyEvidenceReportError, PracticeContentError, ValueError) as exc:
        raise M6DAuthoringReadinessError(
            f"Deterministic cohort-report generation failed: {exc}"
        ) from exc
    expected = outputs.get(M6D_REPORT_PATH)
    if expected is None:
        raise M6DAuthoringReadinessError(
            "Deterministic competency-evidence reports do not include the M6D-01 cohort report."
        )
    report_path = base_dir / M6D_REPORT_PATH
    report, actual = _read_json_object(report_path, label="M6D-01 cohort report")
    if actual != expected:
        raise M6DAuthoringReadinessError(
            f"M6D-01 cohort report is missing or stale: {M6D_REPORT_PATH.as_posix()}."
        )
    _require_equal(
        "M6D-01 cohort report contract",
        report.get("contract_version"),
        M6D_AUTHORING_READINESS_CONTRACT_VERSION,
    )
    _require_equal(
        "M6D-01 cohort report catalog hash",
        report.get("catalog_content_hash"),
        catalog_hash,
    )
    return report, hashlib.sha256(actual).hexdigest()


def _expected_action_ids() -> tuple[str, ...]:
    return tuple(
        f"{member.protocol_stable_id}-A{sequence}"
        for member in M6D_COHORT
        for sequence in range(1, member.action_count + 1)
    )


def _verify_fixture(base_dir: Path) -> tuple[str, tuple[str, ...]]:
    path = base_dir / M6D_FIXTURE_PATH
    fixture, raw = _read_json_object(path, label="M6D-01 synthetic fixture")
    _require_equal(
        "M6D-01 fixture schema",
        fixture.get("schema_version"),
        M6D_FIXTURE_SCHEMA_VERSION,
    )
    _require_equal(
        "M6D-01 fixture algorithm",
        fixture.get("algorithm_version"),
        TYPED_EVIDENCE_ALGORITHM_VERSION,
    )
    _require_equal(
        "M6D-01 fixture rules version",
        fixture.get("rules_schema_version"),
        TYPED_EVIDENCE_RULES_VERSION,
    )
    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        raise M6DAuthoringReadinessError(
            "M6D-01 synthetic fixture requires a non-empty cases list."
        )
    action_ids: list[str] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise M6DAuthoringReadinessError(
                f"M6D-01 synthetic fixture case {index} must be an object."
            )
        evidence_input = case.get("input")
        if not isinstance(evidence_input, dict):
            raise M6DAuthoringReadinessError(
                f"M6D-01 synthetic fixture case {index} is missing input."
            )
        action_id = evidence_input.get("action_stable_id")
        if not isinstance(action_id, str) or not action_id:
            raise M6DAuthoringReadinessError(
                f"M6D-01 synthetic fixture case {index} is missing action_stable_id."
            )
        if not isinstance(case.get("expected"), dict):
            raise M6DAuthoringReadinessError(
                f"M6D-01 synthetic fixture case {index} is missing expected output."
            )
        action_ids.append(action_id)
    expected_action_ids = _expected_action_ids()
    _require_equal("M6D-01 fixture case count", len(action_ids), len(expected_action_ids))
    if len(action_ids) != len(set(action_ids)):
        raise M6DAuthoringReadinessError(
            "M6D-01 synthetic fixture contains duplicate action_stable_id cases."
        )
    _require_equal(
        "M6D-01 fixture action coverage",
        tuple(sorted(action_ids)),
        tuple(sorted(expected_action_ids)),
    )
    return hashlib.sha256(raw).hexdigest(), tuple(sorted(action_ids))


def _verify_cohort(practices) -> None:
    protocols = {protocol["stable_id"]: protocol for protocol in practices.protocols}
    expected_ids = {member.protocol_stable_id for member in M6D_COHORT}
    typed_protocol_ids = {
        protocol["stable_id"]
        for protocol in practices.protocols
        if protocol["evidence_and_scoring"]["observation_contract_version"]
        == TYPED_EVIDENCE_RULES_VERSION
    }
    missing_typed_ids = expected_ids - typed_protocol_ids
    if missing_typed_ids:
        raise M6DAuthoringReadinessError(
            "M6D-01 typed protocol IDs are missing: " + ", ".join(sorted(missing_typed_ids)) + "."
        )
    for member in M6D_COHORT:
        protocol = protocols.get(member.protocol_stable_id)
        if protocol is None:
            raise M6DAuthoringReadinessError(
                f"M6D-01 protocol is missing: {member.protocol_stable_id}."
            )
        governance = protocol["governance"]
        actions = protocol["intervention"]["actions"]
        activation = practices.activation_entries.get(member.protocol_stable_id)
        _require_equal(
            f"{member.protocol_stable_id} parent competency",
            protocol["parent_competency_id"],
            member.competency_id,
        )
        _require_equal(
            f"{member.protocol_stable_id} domain", protocol["domain_id"], member.domain_id
        )
        _require_equal(
            f"{member.protocol_stable_id} family",
            protocol["intervention"]["protocol_class"],
            member.protocol_family_id,
        )
        _require_equal(
            f"{member.protocol_stable_id} recommendation targets",
            tuple(sorted(protocol["evidence_and_scoring"]["recommendation_target_lever_ids"])),
            member.recommendation_target_lever_ids,
        )
        _require_equal(
            f"{member.protocol_stable_id} action count", len(actions), member.action_count
        )
        expected_action_ids = tuple(
            f"{member.protocol_stable_id}-A{sequence}"
            for sequence in range(1, member.action_count + 1)
        )
        _require_equal(
            f"{member.protocol_stable_id} action IDs",
            tuple(action["stable_id"] for action in actions),
            expected_action_ids,
        )
        _require_equal(
            f"{member.protocol_stable_id} governance risk class",
            governance["risk_class_id"],
            "RISK-LOW",
        )
        _require_equal(
            f"{member.protocol_stable_id} owner-directed runtime governance",
            (
                governance["availability"],
                governance["editorial_status"],
                governance["runtime_projection"],
                governance["scoring_policy_id"],
                governance["scoring_status"],
            ),
            (
                "active",
                "draft",
                "GG-PRACTICE-RUNTIME-PROJECTION-2.0",
                "SP-STRUCTURED-EVIDENCE-ELIGIBLE",
                "active",
            ),
        )
        if activation is None:
            raise M6DAuthoringReadinessError(
                f"M6D-01 activation entry is missing: {member.protocol_stable_id}."
            )
        _require_equal(
            f"{member.protocol_stable_id} active activation",
            (
                activation["scoring_policy_id"],
                activation["score_active"],
                activation["activation_status"],
                activation["approved_contract"],
            ),
            (
                "SP-STRUCTURED-EVIDENCE-ELIGIBLE",
                True,
                "active",
                "GG-SCORE-STATE-1.0",
            ),
        )
        serialized_protocol = json.dumps(protocol, ensure_ascii=False).lower()
        missing_boundary_terms = sorted(
            term
            for term in _REQUIRED_SAFETY_PRIVACY_TERMS[member.protocol_stable_id]
            if term not in serialized_protocol
        )
        if missing_boundary_terms:
            raise M6DAuthoringReadinessError(
                f"{member.protocol_stable_id} safety/privacy boundary terms are missing: "
                + ", ".join(missing_boundary_terms)
                + "."
            )
        for action in actions:
            identity = action["typed_evidence_identity"]
            rules = action["evidence_rules"]
            _require_equal(
                f"{action['stable_id']} typed rules version",
                rules["schema_version"],
                TYPED_EVIDENCE_RULES_VERSION,
            )
            _require_equal(
                f"{action['stable_id']} typed protocol identity",
                identity["protocol_stable_id"],
                member.protocol_stable_id,
            )
            _require_equal(
                f"{action['stable_id']} typed action identity",
                identity["action_stable_id"],
                action["stable_id"],
            )
            _require_equal(
                f"{action['stable_id']} typed competency identity",
                identity["competency_stable_id"],
                member.competency_id,
            )
            _require_equal(
                f"{action['stable_id']} typed policy identity",
                identity["scoring_policy_id"],
                governance["scoring_policy_id"],
            )


def verify_m6d_authoring_readiness() -> M6DAuthoringReadinessSummary:
    """Verify the exact M6D-01 source cohort without writing application state."""

    try:
        expansion = verify_expansion_readiness()
        competency = verify_competency_evidence_readiness()
        practices = load_practice_content_bundle(settings.BASE_DIR.resolve())
    except (
        ExpansionReadinessError,
        CompetencyEvidenceReadinessError,
        PracticeContentError,
    ) as exc:
        raise M6DAuthoringReadinessError(
            f"Preserved readiness or canonical source verification failed: {exc}"
        ) from exc

    _require_equal(
        "Preserved expansion readiness contract",
        expansion.contract_version,
        EXPANSION_READINESS_CONTRACT_VERSION,
    )
    _require_equal(
        "Preserved competency-evidence readiness contract",
        competency.contract_version,
        COMPETENCY_EVIDENCE_READINESS_CONTRACT_VERSION,
    )
    _verify_cohort(practices)
    fixture_sha256, fixture_action_ids = _verify_fixture(settings.BASE_DIR.resolve())
    report, report_sha256 = _verify_report(settings.BASE_DIR.resolve(), practices.content_hash)
    _require_equal(
        "M6D-01 cohort report fixture hash",
        report.get("fixture_sha256"),
        fixture_sha256,
    )

    _require_equal("M6D-01 curriculum competency count", expansion.competencies, 383)
    _require_equal("M6F source protocol packages", expansion.canonical_protocol_packages, 383)
    _require_equal("M6F source actions", expansion.practice_actions, 1151)
    _require_equal("M6F uncovered competencies", expansion.uncovered_competencies, 0)
    _require_equal("M6F typed protocols", competency.source_typed_protocols, 378)
    _require_equal("M6F runtime protocols", expansion.runtime_protocols, 383)
    _require_equal("M6F runtime actions", expansion.runtime_actions, 1151)
    _require_equal("M6F score-active protocols", expansion.score_active_protocols, 383)
    _require_equal("M6D-01 fixture action count", len(fixture_action_ids), 14)
    _require_equal(
        "Legacy compatibility projection hash",
        expansion.legacy_projection_hash,
        practices.release_manifest["legacy_projection_hash"],
    )
    _require_equal("M6B specialist review ID", competency.expert_review_id, "ER-M6A-003")
    _require_equal("M6B research gap ID", competency.research_gap_id, "RG-M6A-002")

    runtime_protocols = tuple(PracticeProtocol.objects.order_by("stable_id"))
    runtime_protocol_ids = {protocol.stable_id for protocol in runtime_protocols}
    if not set(FROZEN_LEGACY_PROTOCOL_IDS).issubset(runtime_protocol_ids):
        raise M6DAuthoringReadinessError(
            "M6D-01 requires the five legacy runtime protocols to remain available."
        )
    _require_equal(
        "Seeded runtime action count",
        PracticeAction.objects.count(),
        expansion.runtime_actions,
    )
    score_active_protocol_ids = {
        protocol.stable_id for protocol in runtime_protocols if protocol.score_active
    }
    _require_equal(
        "M6F exact score-active protocol IDs",
        score_active_protocol_ids,
        runtime_protocol_ids,
    )
    cohort_protocol_ids = {member.protocol_stable_id for member in M6D_COHORT}
    cohort_typed_production_protocols = len(cohort_protocol_ids & runtime_protocol_ids)
    _require_equal(
        "M6D-01 cohort typed production protocols",
        cohort_typed_production_protocols,
        4,
    )

    return M6DAuthoringReadinessSummary(
        contract_version=M6D_AUTHORING_READINESS_CONTRACT_VERSION,
        preserved_expansion_contract_version=expansion.contract_version,
        preserved_competency_evidence_contract_version=competency.contract_version,
        practice_catalog_content_hash=practices.content_hash,
        legacy_projection_hash=expansion.legacy_projection_hash,
        cohort_report_sha256=report_sha256,
        fixture_sha256=fixture_sha256,
        cohort_competency_ids=tuple(member.competency_id for member in M6D_COHORT),
        cohort_protocol_ids=tuple(member.protocol_stable_id for member in M6D_COHORT),
        cohort_action_count=len(fixture_action_ids),
        competencies=expansion.competencies,
        source_protocol_packages=expansion.canonical_protocol_packages,
        source_practice_actions=expansion.practice_actions,
        uncovered_competencies=expansion.uncovered_competencies,
        runtime_protocols=expansion.runtime_protocols,
        runtime_actions=expansion.runtime_actions,
        score_active_protocols=expansion.score_active_protocols,
        source_typed_protocols=competency.source_typed_protocols,
        typed_production_protocols=cohort_typed_production_protocols,
        expert_review_id=competency.expert_review_id,
        expert_review_status=competency.expert_review_status,
        research_gap_id=competency.research_gap_id,
        research_gap_status=competency.research_gap_status,
        database_writes=0,
    )
