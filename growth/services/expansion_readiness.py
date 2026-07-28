from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from django.conf import settings

from growth.domain.practice_content import (
    FROZEN_LEGACY_CONFIGURATION_HASH,
    PracticeContentError,
    configuration_hash,
    legacy_projection_payload,
    load_practice_content_bundle,
)
from growth.models import PracticeProtocol
from growth.services.canonical_import import (
    CanonicalDataError,
    load_and_validate_bundle,
    validate_practice_content_mapping,
)
from growth.services.pilot_readiness import (
    PILOT_READINESS_CONTRACT_VERSION,
    PilotReadinessError,
    _protocol_payload,
    verify_pilot_readiness,
)
from growth.services.practice_content_reports import (
    PracticeReportError,
    write_or_check_practice_reports,
)

EXPANSION_READINESS_CONTRACT_VERSION = "GG-CURRICULUM-EXPANSION-READINESS-1.0"


class ExpansionReadinessError(ValueError):
    pass


@dataclass(frozen=True)
class ExpansionReadinessSummary:
    contract_version: str
    preserved_pilot_contract_version: str
    canonical_curriculum_source_hash: str
    practice_catalog_content_hash: str
    legacy_projection_hash: str
    competencies: int
    canonical_protocol_packages: int
    projected_legacy_protocols: int
    practice_actions: int
    uncovered_competencies: int
    domains_with_projected_protocols: int
    parent_mapped_levers: int
    recommendation_target_levers: int
    low_risk_protocols: int
    moderate_risk_protocols: int
    high_risk_protocols: int
    score_active_protocols: int
    sources_complete_protocols: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _require_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise ExpansionReadinessError(f"{label}: expected {expected!r}, found {actual!r}.")


def verify_expansion_readiness() -> ExpansionReadinessSummary:
    """Verify M6A additively while retaining the independent M4E gate."""

    try:
        pilot_summary = verify_pilot_readiness()
    except PilotReadinessError as exc:
        raise ExpansionReadinessError(
            f"Preserved pilot-readiness verification failed: {exc}"
        ) from exc
    _require_equal(
        "Preserved pilot contract",
        pilot_summary.contract_version,
        PILOT_READINESS_CONTRACT_VERSION,
    )

    try:
        canonical = load_and_validate_bundle()
        practices = load_practice_content_bundle(settings.BASE_DIR)
        validate_practice_content_mapping(practices, canonical)
        write_or_check_practice_reports(check=True)
    except (CanonicalDataError, PracticeContentError, PracticeReportError) as exc:
        raise ExpansionReadinessError(f"M6A source validation failed: {exc}") from exc

    projected = practices.runtime_protocols
    projected_payload = [legacy_projection_payload(protocol) for protocol in projected]
    projection_hash = configuration_hash(projected_payload)
    _require_equal(
        "Frozen legacy runtime projection",
        projection_hash,
        FROZEN_LEGACY_CONFIGURATION_HASH,
    )

    runtime_protocols = {
        protocol.stable_id: protocol
        for protocol in PracticeProtocol.objects.select_related("parent_competency")
        .prefetch_related("actions", "target_levers")
        .order_by("stable_id")
    }
    runtime_payload = [
        _protocol_payload(runtime_protocols[protocol["stable_id"]]) for protocol in projected
    ]
    _require_equal(
        "Seeded runtime projection",
        runtime_payload,
        projected_payload,
    )

    competency_count = sum(
        len(domain["competencies"]) for domain in canonical.curriculum["domains"]
    )
    mappings = {
        link["competency_id"]: set(link["lever_weights"])
        for link in canonical.model["competency_lever_links"]
    }
    parent_levers = {
        lever_id
        for protocol in practices.protocols
        for lever_id in mappings[protocol["parent_competency_id"]]
    }
    target_levers = {
        lever_id
        for protocol in practices.protocols
        for lever_id in protocol["evidence_and_scoring"]["recommendation_target_lever_ids"]
    }
    risk_counts = {
        risk_id: sum(
            protocol["governance"]["risk_class_id"] == risk_id for protocol in practices.protocols
        )
        for risk_id in ("RISK-LOW", "RISK-MODERATE", "RISK-HIGH")
    }
    domain_count = len({protocol["domain_id"] for protocol in practices.protocols})
    action_count = sum(len(protocol["intervention"]["actions"]) for protocol in practices.protocols)
    sources_complete = sum(
        protocol["governance"]["authoring"]["research_review_status"] == "complete"
        for protocol in practices.protocols
    )
    score_active = sum(
        activation["score_active"] for activation in practices.activation_entries.values()
    )

    expected = {
        "competencies": (competency_count, 383),
        "canonical protocol packages": (len(practices.protocols), 5),
        "projected legacy protocols": (len(projected), 5),
        "practice actions": (action_count, 15),
        "uncovered competencies": (competency_count - len(practices.protocols), 378),
        "domains with projected protocols": (domain_count, 5),
        "parent-mapped levers": (len(parent_levers), 13),
        "recommendation-target levers": (len(target_levers), 6),
        "low-risk protocols": (risk_counts["RISK-LOW"], 3),
        "moderate-risk protocols": (risk_counts["RISK-MODERATE"], 2),
        "high-risk protocols": (risk_counts["RISK-HIGH"], 0),
        "score-active protocols": (score_active, 1),
        "source-complete protocols": (sources_complete, 0),
    }
    for label, (actual, expected_value) in expected.items():
        _require_equal(label, actual, expected_value)

    return ExpansionReadinessSummary(
        contract_version=EXPANSION_READINESS_CONTRACT_VERSION,
        preserved_pilot_contract_version=pilot_summary.contract_version,
        canonical_curriculum_source_hash=canonical.source_hash,
        practice_catalog_content_hash=practices.content_hash,
        legacy_projection_hash=projection_hash,
        competencies=competency_count,
        canonical_protocol_packages=len(practices.protocols),
        projected_legacy_protocols=len(projected),
        practice_actions=action_count,
        uncovered_competencies=competency_count - len(practices.protocols),
        domains_with_projected_protocols=domain_count,
        parent_mapped_levers=len(parent_levers),
        recommendation_target_levers=len(target_levers),
        low_risk_protocols=risk_counts["RISK-LOW"],
        moderate_risk_protocols=risk_counts["RISK-MODERATE"],
        high_risk_protocols=risk_counts["RISK-HIGH"],
        score_active_protocols=score_active,
        sources_complete_protocols=sources_complete,
    )
