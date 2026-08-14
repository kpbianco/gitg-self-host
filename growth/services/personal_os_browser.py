from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError

from growth.domain.context import ASSESSMENT_FACTOR_IDS, PRACTICE_FACTOR_IDS
from growth.domain.context_priority import AlternativeRequest
from growth.domain.personal_os import AUDIT_PROMPT_IDS, IDENTITY_SECTION_IDS, LIST_SECTION_IDS
from growth.domain.practice_content import PracticeContentError, load_practice_content_bundle
from growth.models import (
    AssessmentContext,
    AssessmentRun,
    PersonalOSRevision,
    PracticeContext,
    PracticeProtocol,
)
from growth.services.context_priority import (
    ContextPriorityServiceError,
    build_context_priority_for_epoch,
)

EXPLANATION_COPY = {
    "context_complete": "All six practice factors and current capacity were explicitly provided.",
    "explicit_zero_factor": "At least one factor was explicitly 0; it was not treated as missing.",
    "applicability_not_applicable": (
        "You marked this practice not applicable right now; that creates no deficit."
    ),
    "candidate_deferred": "You deferred this practice for now.",
    "required_factor_deferred": (
        "A named context factor is intentionally deferred rather than scored as zero."
    ),
    "required_factor_missing": (
        "One or more required practice factors are still unknown or not applicable."
    ),
    "capacity_missing": "Current capacity is still unknown, not applicable, or deferred.",
    "alternative_after_not_applicable": (
        "The alternative is distinct from the practice marked not applicable."
    ),
    "alternative_after_deferred": "The alternative is distinct from the deferred practice.",
    "no_eligible_alternative": (
        "No other explicitly reviewed practice has complete eligible context."
    ),
}


@dataclass(frozen=True)
class BrowserCandidate:
    protocol: PracticeProtocol
    disposition: str
    explanation: tuple[str, ...]


@dataclass(frozen=True)
class BrowserPriorityPresentation:
    status: str
    recommendations: tuple[PracticeProtocol, ...]
    recommended_ids: frozenset[str]
    reviewed_protocols: tuple[PracticeProtocol, ...]
    candidates: tuple[BrowserCandidate, ...]
    reviewed_count: int
    active_count: int
    partial_cohort: bool
    context_aware: bool
    message: str
    alternative_protocol: PracticeProtocol | None = None
    alternative_message: str = ""


def personal_os_initial(
    record: PersonalOSRevision | None, *, assessment_epoch: str
) -> dict[str, Any]:
    initial: dict[str, Any] = {"assessment_epoch": assessment_epoch}
    if record is None:
        return initial
    for section_id in (*IDENTITY_SECTION_IDS, *AUDIT_PROMPT_IDS):
        state = getattr(record, f"{section_id}_state")
        value = getattr(record, f"{section_id}_value") if state == "provided" else ""
        initial[f"{section_id}_state"] = state
        initial[f"{section_id}_value"] = (
            "\n".join(value) if section_id in LIST_SECTION_IDS and value else value
        )
    return initial


def assessment_context_initial(
    record: AssessmentContext | None, *, assessment_epoch: str
) -> dict[str, Any]:
    initial: dict[str, Any] = {"assessment_epoch": assessment_epoch}
    if record is None:
        return initial
    for factor_id in ASSESSMENT_FACTOR_IDS:
        state = getattr(record, f"{factor_id}_state")
        initial[f"{factor_id}_state"] = state
        initial[f"{factor_id}_value"] = (
            getattr(record, f"{factor_id}_value") if state == "provided" else None
        )
    return initial


def practice_context_initial(
    record: PracticeContext | None, *, assessment_epoch: str
) -> dict[str, Any]:
    initial: dict[str, Any] = {"assessment_epoch": assessment_epoch}
    if record is None:
        return initial
    if record.applicability_state == "not_applicable":
        initial["mode"] = "not_applicable"
    elif record.disposition == "deferred":
        initial.update(
            {
                "mode": "defer",
                "deferred_factor": next(
                    (
                        factor_id
                        for factor_id in PRACTICE_FACTOR_IDS
                        if getattr(record, f"{factor_id}_state") == "deferred"
                    ),
                    "",
                ),
                "defer_reason": record.defer_reason,
                "review_horizon_days": record.review_horizon_days,
            }
        )
    elif all(
        getattr(record, f"{factor_id}_state") == "provided" for factor_id in PRACTICE_FACTOR_IDS
    ):
        initial["mode"] = "provide"
        initial.update(
            {factor_id: getattr(record, f"{factor_id}_value") for factor_id in PRACTICE_FACTOR_IDS}
        )
    return initial


def assessment_factors_from_record(record: AssessmentContext | None) -> dict[str, dict[str, Any]]:
    if record is None:
        return {
            factor_id: {"state": "unknown", "value": None} for factor_id in ASSESSMENT_FACTOR_IDS
        }
    return {
        factor_id: {
            "state": getattr(record, f"{factor_id}_state"),
            "value": (
                getattr(record, f"{factor_id}_value")
                if getattr(record, f"{factor_id}_state") == "provided"
                else None
            ),
        }
        for factor_id in ASSESSMENT_FACTOR_IDS
    }


def active_projected_protocol_ids() -> tuple[str, ...]:
    bundle = load_practice_content_bundle(settings.BASE_DIR)
    return tuple(item["stable_id"] for item in bundle.runtime_protocols)


def _reviewed_protocols(user, assessment_run: AssessmentRun, active_ids: tuple[str, ...]):
    latest_by_protocol: dict[str, PracticeContext] = {}
    rows = (
        PracticeContext.objects.filter(
            assessment_run=assessment_run,
            protocol_id__in=active_ids,
            protocol__availability=PracticeProtocol.Availability.ACTIVE,
        )
        .select_related("protocol")
        .order_by("protocol_id", "revision")
    )
    revisions: dict[str, list[int]] = {}
    for row in rows:
        try:
            row.full_clean()
        except (ValidationError, ValueError, TypeError):
            raise ContextPriorityServiceError(
                "Saved practice context failed browser verification."
            ) from None
        revisions.setdefault(row.protocol_id, []).append(row.revision)
        latest_by_protocol[row.protocol_id] = row
    if any(actual != list(range(1, len(actual) + 1)) for actual in revisions.values()):
        raise ContextPriorityServiceError(
            "Saved practice context revisions failed browser verification."
        )
    protocols = tuple(
        PracticeProtocol.objects.filter(stable_id__in=latest_by_protocol)
        .select_related("parent_competency")
        .order_by("stable_id")
    )
    return protocols


def _verified_assessment_context(assessment_run: AssessmentRun) -> AssessmentContext | None:
    rows = tuple(
        AssessmentContext.objects.filter(assessment_run=assessment_run).order_by("revision")
    )
    try:
        for row in rows:
            row.full_clean()
    except (ValidationError, ValueError, TypeError):
        raise ContextPriorityServiceError(
            "Saved assessment context failed browser verification."
        ) from None
    if [row.revision for row in rows] != list(range(1, len(rows) + 1)):
        raise ContextPriorityServiceError(
            "Saved assessment context revisions failed browser verification."
        )
    return rows[-1] if rows else None


def build_browser_priority_presentation(
    *,
    user,
    summary,
    alternative_request: AlternativeRequest | None = None,
) -> BrowserPriorityPresentation:
    legacy = tuple(summary.recommendations)
    legacy_ids = frozenset(protocol.stable_id for protocol in legacy)
    run = summary.assessment_run
    if run is None:
        return BrowserPriorityPresentation(
            "no_assessment", legacy, legacy_ids, (), (), 0, 0, False, False, ""
        )
    try:
        active_ids = active_projected_protocol_ids()
    except PracticeContentError:
        return BrowserPriorityPresentation(
            "unavailable",
            legacy,
            legacy_ids,
            (),
            (),
            0,
            0,
            False,
            False,
            "Context review is temporarily unavailable. Provisional need order is unchanged.",
        )
    active_count = PracticeProtocol.objects.filter(
        stable_id__in=active_ids,
        availability=PracticeProtocol.Availability.ACTIVE,
    ).count()
    try:
        assessment_context = _verified_assessment_context(run)
        reviewed = _reviewed_protocols(user, run, active_ids)
    except ContextPriorityServiceError:
        return BrowserPriorityPresentation(
            "unavailable",
            legacy,
            legacy_ids,
            (),
            (),
            0,
            active_count,
            False,
            False,
            "Saved context could not be verified. Provisional need order is unchanged.",
        )
    partial = bool(reviewed) and len(reviewed) < active_count
    if assessment_context is None:
        message = (
            "Add season and capacity before asking for context-aware ordering. "
            "The provisional need order remains unchanged."
            if reviewed
            else (
                "No current-epoch context has been reviewed; provisional need order "
                "remains unchanged."
            )
        )
        return BrowserPriorityPresentation(
            "no_context",
            legacy,
            legacy_ids,
            reviewed,
            (),
            len(reviewed),
            active_count,
            partial,
            False,
            message,
        )
    if not reviewed:
        return BrowserPriorityPresentation(
            "no_candidates",
            legacy,
            legacy_ids,
            (),
            (),
            0,
            active_count,
            False,
            False,
            "Review at least one practice before asking for context-aware ordering. "
            "Provisional need order remains unchanged.",
        )
    try:
        result = build_context_priority_for_epoch(
            user=user,
            assessment_run=run,
            protocol_stable_ids=tuple(protocol.stable_id for protocol in reviewed),
            alternative_request=alternative_request,
        )
    except ContextPriorityServiceError:
        return BrowserPriorityPresentation(
            "unavailable",
            legacy,
            legacy_ids,
            reviewed,
            (),
            len(reviewed),
            active_count,
            partial,
            False,
            "Verified context is temporarily unavailable. Provisional need order is unchanged.",
        )
    protocol_map = {protocol.stable_id: protocol for protocol in reviewed}
    candidates = tuple(
        BrowserCandidate(
            protocol=protocol_map[item.protocol_stable_id],
            disposition=item.disposition.value,
            explanation=tuple(EXPLANATION_COPY[code] for code in item.explanation_codes),
        )
        for item in result.candidates
    )
    ranked = tuple(protocol_map[item] for item in result.ranked_candidate_ids)[:3]
    alternative_protocol = (
        protocol_map.get(result.alternative.target_protocol_stable_id)
        if result.alternative.target_protocol_stable_id
        else None
    )
    alternative_message = " ".join(
        EXPLANATION_COPY[code] for code in result.alternative.explanation_codes
    )
    if result.capacity.state != "provided":
        return BrowserPriorityPresentation(
            "missing_capacity",
            legacy,
            legacy_ids,
            reviewed,
            candidates,
            len(reviewed),
            active_count,
            partial,
            False,
            "Capacity must be explicitly provided before context-aware ordering. "
            "It remains missing, not zero.",
            alternative_protocol,
            alternative_message,
        )
    if not ranked:
        return BrowserPriorityPresentation(
            "no_eligible",
            legacy,
            legacy_ids,
            reviewed,
            candidates,
            len(reviewed),
            active_count,
            partial,
            False,
            "No explicitly reviewed practice has all required context. Provisional "
            "need order remains unchanged and is not context-aware.",
            alternative_protocol,
            alternative_message,
        )
    return BrowserPriorityPresentation(
        "ranked",
        ranked,
        frozenset(protocol.stable_id for protocol in ranked),
        reviewed,
        candidates,
        len(reviewed),
        active_count,
        partial,
        True,
        "Ordered only among the explicitly reviewed practices with complete eligible "
        "context. This separates provisional need from current context fit.",
        alternative_protocol,
        alternative_message,
    )
