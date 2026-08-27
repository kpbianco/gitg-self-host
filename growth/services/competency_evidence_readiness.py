from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from growth.domain.scoring import ScoringContractError
from growth.domain.typed_evidence import TYPED_EVIDENCE_RULES_VERSION
from growth.models import PracticeAction, PracticeProtocol
from growth.services.competency_evidence_reports import (
    COMPETENCY_EVIDENCE_READINESS_CONTRACT_VERSION,
    REPORT_PATHS,
    CompetencyEvidenceReportError,
    build_competency_evidence_report_outputs,
    write_or_check_competency_evidence_reports,
)
from growth.services.expansion_readiness import (
    EXPANSION_READINESS_CONTRACT_VERSION,
    ExpansionReadinessError,
    verify_expansion_readiness,
)
from growth.services.scoring import (
    PRODUCTION_SCORE_ELIGIBILITY_CONTRACT_VERSION,
    PRODUCTION_SCORE_MAPPING_FINGERPRINT,
    validate_production_scoring_protocol,
)


class CompetencyEvidenceReadinessError(ValueError):
    pass


@dataclass(frozen=True)
class CompetencyEvidenceReadinessSummary:
    contract_version: str
    preserved_expansion_contract_version: str
    production_score_eligibility_contract_version: str
    production_mapping_fingerprint: str
    software_ready: bool
    specialist_review_complete: bool
    m6b_accepted: bool
    competencies: int
    canonical_protocol_packages: int
    practice_actions: int
    uncovered_competencies: int
    score_active_protocols: int
    source_typed_protocols: int
    typed_production_protocols: int
    typed_score_active_protocols: int
    expert_review_id: str
    expert_review_status: str
    research_gap_id: str
    research_gap_status: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _require_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise CompetencyEvidenceReadinessError(f"{label}: expected {expected!r}, found {actual!r}.")


def _load_expected_readiness_report() -> dict[str, Any]:
    outputs = build_competency_evidence_report_outputs()
    try:
        payload = json.loads(outputs[REPORT_PATHS["readiness"]])
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CompetencyEvidenceReadinessError(
            "The deterministic competency-evidence readiness report is malformed."
        ) from exc
    if not isinstance(payload, dict):
        raise CompetencyEvidenceReadinessError(
            "The deterministic competency-evidence readiness report must be an object."
        )
    return payload


def verify_competency_evidence_readiness() -> CompetencyEvidenceReadinessSummary:
    """Verify additive competency-evidence readiness and canonical governance state."""

    try:
        expansion = verify_expansion_readiness()
        write_or_check_competency_evidence_reports(check=True)
        report = _load_expected_readiness_report()
    except (ExpansionReadinessError, CompetencyEvidenceReportError) as exc:
        raise CompetencyEvidenceReadinessError(
            f"Preserved readiness or deterministic report verification failed: {exc}"
        ) from exc

    _require_equal(
        "Preserved expansion contract",
        expansion.contract_version,
        EXPANSION_READINESS_CONTRACT_VERSION,
    )
    _require_equal(
        "Competency-evidence readiness contract",
        report.get("contract_version"),
        COMPETENCY_EVIDENCE_READINESS_CONTRACT_VERSION,
    )
    _require_equal("Software readiness", report.get("software_ready"), True)
    if not isinstance(report.get("specialist_review_complete"), bool) or not isinstance(
        report.get("m6b_accepted"), bool
    ):
        raise CompetencyEvidenceReadinessError(
            "Specialist review and M6B acceptance must be explicit Boolean values."
        )
    source_typed_protocols = report.get("source_typed_protocols")
    if not isinstance(source_typed_protocols, int) or source_typed_protocols < 4:
        raise CompetencyEvidenceReadinessError(
            "Source-only typed protocol count: the M6D-01 four-protocol cohort is incomplete."
        )
    for field in ("typed_production_protocols", "typed_score_active_protocols"):
        if not isinstance(report.get(field), int) or report[field] < 0:
            raise CompetencyEvidenceReadinessError(f"{field} must be a nonnegative integer.")

    catalog = report.get("catalog")
    governance = report.get("governance")
    if not isinstance(catalog, dict) or not isinstance(governance, dict):
        raise CompetencyEvidenceReadinessError(
            "The readiness report is missing catalog or governance controls."
        )
    expert_review = governance.get("expert_review")
    research_gap = governance.get("research_gap")
    if not isinstance(expert_review, dict) or not isinstance(research_gap, dict):
        raise CompetencyEvidenceReadinessError(
            "The readiness report is missing M6B review or research-gap state."
        )
    _require_equal("M6B expert review ID", expert_review.get("review_id"), "ER-M6A-003")
    _require_equal("M6B research gap ID", research_gap.get("gap_id"), "RG-M6A-002")
    if not isinstance(expert_review.get("status"), str) or not isinstance(
        research_gap.get("status"), str
    ):
        raise CompetencyEvidenceReadinessError(
            "M6B expert-review and research-gap status must be explicit strings."
        )

    runtime_protocols = tuple(
        PracticeProtocol.objects.select_related("parent_competency")
        .prefetch_related("actions", "target_levers", "parent_competency__lever_links__lever")
        .order_by("stable_id")
    )
    runtime_actions = PracticeAction.objects.count()
    runtime_typed = tuple(
        protocol
        for protocol in runtime_protocols
        if any(
            action.evidence_rules.get("schema_version") == TYPED_EVIDENCE_RULES_VERSION
            for action in protocol.actions.all()
        )
    )
    runtime_typed_active = sum(protocol.score_active for protocol in runtime_typed)
    _require_equal(
        "Seeded runtime protocol packages",
        len(runtime_protocols),
        expansion.runtime_protocols,
    )
    _require_equal(
        "Seeded runtime practice actions",
        runtime_actions,
        expansion.runtime_actions,
    )
    _require_equal(
        "Seeded score-active protocols",
        sum(protocol.score_active for protocol in runtime_protocols),
        catalog["score_active_protocols"],
    )
    _require_equal(
        "Seeded typed production protocols",
        len(runtime_typed),
        report["typed_production_protocols"],
    )
    _require_equal(
        "Seeded typed score-active protocols",
        runtime_typed_active,
        report["typed_score_active_protocols"],
    )

    for protocol in runtime_protocols:
        try:
            validate_production_scoring_protocol(protocol)
        except ScoringContractError as exc:
            raise CompetencyEvidenceReadinessError(
                f"{protocol.stable_id}: production score-eligibility verification failed: {exc}"
            ) from exc

    return CompetencyEvidenceReadinessSummary(
        contract_version=COMPETENCY_EVIDENCE_READINESS_CONTRACT_VERSION,
        preserved_expansion_contract_version=expansion.contract_version,
        production_score_eligibility_contract_version=(
            PRODUCTION_SCORE_ELIGIBILITY_CONTRACT_VERSION
        ),
        production_mapping_fingerprint=PRODUCTION_SCORE_MAPPING_FINGERPRINT,
        software_ready=True,
        specialist_review_complete=report["specialist_review_complete"],
        m6b_accepted=report["m6b_accepted"],
        competencies=catalog["competencies"],
        canonical_protocol_packages=catalog["canonical_protocol_packages"],
        practice_actions=catalog["practice_actions"],
        uncovered_competencies=catalog["uncovered_competencies"],
        score_active_protocols=catalog["score_active_protocols"],
        source_typed_protocols=report["source_typed_protocols"],
        typed_production_protocols=len(runtime_typed),
        typed_score_active_protocols=runtime_typed_active,
        expert_review_id=expert_review["review_id"],
        expert_review_status=expert_review["status"],
        research_gap_id=research_gap["gap_id"],
        research_gap_status=research_gap["status"],
    )
