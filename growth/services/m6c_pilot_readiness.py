from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from django.conf import settings
from django.urls import NoReverseMatch, Resolver404, resolve, reverse

from growth.domain.context import ASSESSMENT_FACTOR_IDS, PRACTICE_FACTOR_IDS
from growth.domain.personal_os import AUDIT_PROMPT_IDS, IDENTITY_SECTION_IDS
from growth.models import PracticeProtocol
from growth.services.competency_evidence_readiness import (
    CompetencyEvidenceReadinessError,
    verify_competency_evidence_readiness,
)
from growth.services.context import ContextReadinessError, verify_context_readiness
from growth.services.context_priority import (
    ContextPriorityReadinessError,
    verify_context_priority_readiness,
)
from growth.services.expansion_readiness import (
    ExpansionReadinessError,
    verify_expansion_readiness,
)
from growth.services.personal_os import (
    PersonalOSReadinessError,
    verify_personal_os_readiness,
)
from growth.services.pilot_readiness import PilotReadinessError, verify_pilot_readiness

M6C_PILOT_READINESS_CONTRACT_VERSION = "GG-M6C-PILOT-READINESS-1.0"

EXPECTED_IDENTITY_SECTION_IDS = (
    "mission",
    "principles",
    "anti_goals",
    "twelve_month_direction",
    "priority_stack",
)
EXPECTED_AUDIT_PROMPT_IDS = (
    "current_truth",
    "autopilot_pattern",
    "misalignment_or_fragmentation",
    "deliberate_next_step",
)
EXPECTED_ASSESSMENT_FACTOR_IDS = ("season", "capacity")
EXPECTED_PRACTICE_FACTOR_IDS = (
    "applicability",
    "importance",
    "readiness",
    "urgency",
    "opportunity_resources",
    "burden",
)
M6C04_BASELINE_PROTOCOL_IDS = (
    "PRACTICE-BOUNDARY-01",
    "PRACTICE-EMOTIONAL-CUES-01",
    "PRACTICE-FRIENDSHIP-01",
    "PRACTICE-PLAY-01",
    "PRACTICE-PRESENCE-01",
)
FRIENDSHIP_PROTOCOL_ID = "PRACTICE-FRIENDSHIP-01"
AUTHENTICATION_MIDDLEWARE = "grounded_growth.middleware.RequireApplicationLoginMiddleware"
ROUTE_EXPECTATIONS = (
    ("growth:personal-os", {}, "/personal-os/"),
    (
        "growth:practice-context",
        {"slug": "synthetic-protocol"},
        "/personal-os/practices/synthetic-protocol/context/",
    ),
)


class M6CPilotReadinessError(ValueError):
    pass


@dataclass(frozen=True)
class M6CPilotReadinessSummary:
    contract_version: str
    prerequisite_contract_versions: tuple[str, ...]
    identity_section_ids: tuple[str, ...]
    audit_prompt_ids: tuple[str, ...]
    assessment_factor_ids: tuple[str, ...]
    practice_factor_ids: tuple[str, ...]
    baseline_protocol_ids: tuple[str, ...]
    active_protocols: int
    score_active_protocol_ids: tuple[str, ...]
    authenticated_route_names: tuple[str, ...]
    personal_os_records: int
    assessment_context_records: int
    practice_context_records: int
    context_priority_synthetic_result_hash: str
    software_ready: bool
    m6b_specialist_review_complete: bool
    m6b_accepted: bool
    release_or_deployment_approved: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _require_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise M6CPilotReadinessError(f"{label}: expected {expected!r}, found {actual!r}.")


def _verify_prerequisite(label: str, verifier: Callable[[], Any], error_type):
    try:
        return verifier()
    except error_type:
        # Do not retain or repeat a nested diagnostic: context and Personal OS
        # failures may originate in private local state.
        raise M6CPilotReadinessError(
            f"{label} prerequisite readiness failed private-safe verification."
        ) from None


def _verify_browser_routes() -> tuple[str, ...]:
    if AUTHENTICATION_MIDDLEWARE not in settings.MIDDLEWARE:
        raise M6CPilotReadinessError(
            "The application-wide authentication middleware is not configured."
        )

    route_names = []
    for route_name, kwargs, expected_path in ROUTE_EXPECTATIONS:
        try:
            path = reverse(route_name, kwargs=kwargs)
            match = resolve(path)
        except (NoReverseMatch, Resolver404):
            raise M6CPilotReadinessError(
                f"Required authenticated browser route {route_name!r} is not registered."
            ) from None
        _require_equal(f"{route_name} path", path, expected_path)
        _require_equal(f"{route_name} resolver name", match.view_name, route_name)
        if path in {settings.LOGIN_URL, "/health/"} or path.startswith(settings.STATIC_URL):
            raise M6CPilotReadinessError(
                f"Required browser route {route_name!r} is incorrectly public."
            )
        route_names.append(route_name)
    return tuple(route_names)


def verify_m6c_pilot_readiness() -> M6CPilotReadinessSummary:
    """Verify the additive M6C browser slice without writing application state."""

    pilot = _verify_prerequisite("Pilot", verify_pilot_readiness, PilotReadinessError)
    expansion = _verify_prerequisite(
        "Curriculum expansion", verify_expansion_readiness, ExpansionReadinessError
    )
    competency = _verify_prerequisite(
        "Competency evidence",
        verify_competency_evidence_readiness,
        CompetencyEvidenceReadinessError,
    )
    context = _verify_prerequisite("Context", verify_context_readiness, ContextReadinessError)
    personal_os = _verify_prerequisite(
        "Personal OS", verify_personal_os_readiness, PersonalOSReadinessError
    )
    context_priority = _verify_prerequisite(
        "Context priority",
        verify_context_priority_readiness,
        ContextPriorityReadinessError,
    )

    _require_equal(
        "Personal OS identity section IDs",
        IDENTITY_SECTION_IDS,
        EXPECTED_IDENTITY_SECTION_IDS,
    )
    _require_equal("Personal OS audit prompt IDs", AUDIT_PROMPT_IDS, EXPECTED_AUDIT_PROMPT_IDS)
    _require_equal(
        "Assessment context factor IDs",
        ASSESSMENT_FACTOR_IDS,
        EXPECTED_ASSESSMENT_FACTOR_IDS,
    )
    _require_equal("Practice context factor IDs", PRACTICE_FACTOR_IDS, EXPECTED_PRACTICE_FACTOR_IDS)

    active_protocol_ids = tuple(
        PracticeProtocol.objects.filter(availability=PracticeProtocol.Availability.ACTIVE)
        .order_by("stable_id")
        .values_list("stable_id", flat=True)
    )
    missing_baseline = tuple(
        protocol_id
        for protocol_id in M6C04_BASELINE_PROTOCOL_IDS
        if protocol_id not in active_protocol_ids
    )
    if missing_baseline:
        raise M6CPilotReadinessError("The five M6C-04 baseline protocols are not all active.")
    score_active_ids = tuple(
        PracticeProtocol.objects.filter(score_active=True)
        .order_by("stable_id")
        .values_list("stable_id", flat=True)
    )
    _require_equal(
        "M6C-04 production score activation",
        score_active_ids,
        active_protocol_ids,
    )
    authenticated_routes = _verify_browser_routes()

    return M6CPilotReadinessSummary(
        contract_version=M6C_PILOT_READINESS_CONTRACT_VERSION,
        prerequisite_contract_versions=(
            pilot.contract_version,
            expansion.contract_version,
            competency.contract_version,
            context.contract_version,
            personal_os.contract_version,
            context_priority.contract_version,
        ),
        identity_section_ids=IDENTITY_SECTION_IDS,
        audit_prompt_ids=AUDIT_PROMPT_IDS,
        assessment_factor_ids=ASSESSMENT_FACTOR_IDS,
        practice_factor_ids=PRACTICE_FACTOR_IDS,
        baseline_protocol_ids=M6C04_BASELINE_PROTOCOL_IDS,
        active_protocols=len(active_protocol_ids),
        score_active_protocol_ids=score_active_ids,
        authenticated_route_names=authenticated_routes,
        personal_os_records=personal_os.records,
        assessment_context_records=context.assessment_records,
        practice_context_records=context.practice_records,
        context_priority_synthetic_result_hash=(context_priority.synthetic_result_hash),
        software_ready=True,
        m6b_specialist_review_complete=competency.specialist_review_complete,
        m6b_accepted=competency.m6b_accepted,
        release_or_deployment_approved=False,
    )
