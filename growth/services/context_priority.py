from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from growth.domain.composite_scoring import ALGORITHM_VERSION as COMPOSITE_SCORING_VERSION
from growth.domain.context import CONTEXT_CONTRACT_VERSION
from growth.domain.context_priority import (
    CONTEXT_PRIORITY_ALGORITHM_VERSION,
    CONTEXT_PRIORITY_READINESS_CONTRACT_VERSION,
    AlternativeRequest,
    ContextPriorityCandidateInput,
    ContextPriorityContractError,
    ContextPriorityResult,
    PriorityFactorValue,
    build_context_priority_result,
)
from growth.domain.practice_content import PracticeContentError, load_practice_content_bundle
from growth.domain.ranking import ProtocolWeight, RankingContractError, protocol_priority
from growth.models import (
    AssessmentContext,
    AssessmentRun,
    CompositeScoreState,
    LeverBaseline,
    LeverState,
    PracticeContext,
    PracticeProtocol,
)
from growth.services.canonical_import import (
    CanonicalDataError,
    load_and_validate_bundle,
    validate_practice_content_mapping,
)
from growth.services.composite_score_state import (
    CompositeScoreStateError,
    verify_composite_score_state_for_run,
)
from growth.services.context import ContextReadinessError, verify_context_readiness
from growth.services.score_state import ScoreStateError, verify_score_state_for_run


class ContextPriorityServiceError(ValueError):
    pass


class ContextPriorityReadinessError(ValueError):
    pass


M6C03_BASELINE_PROTOCOL_IDS = frozenset(
    {
        "PRACTICE-BOUNDARY-01",
        "PRACTICE-EMOTIONAL-CUES-01",
        "PRACTICE-FRIENDSHIP-01",
        "PRACTICE-PLAY-01",
        "PRACTICE-PRESENCE-01",
    }
)
FRIENDSHIP_PROTOCOL_ID = "PRACTICE-FRIENDSHIP-01"
GOLDEN_FIXTURE_PATH = Path("tests/fixtures/context_priority/context_priority_v1.json")


@dataclass(frozen=True)
class ContextPriorityReadinessSummary:
    contract_version: str
    algorithm_version: str
    context_contract_version: str
    need_ranking_algorithm_version: str
    synthetic_fixture_hash: str
    synthetic_result_hash: str
    projected_protocols: int
    m6c03_baseline_protocols_present: int
    score_active_protocols: int
    friendship_score_active: bool
    assessment_context_records: int
    practice_context_records: int
    software_ready: bool
    changes_recommendations: bool
    changes_score_state: bool
    changes_production_activation: bool
    ordinary_ui_changes: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EpochPriorityState:
    lever_needs: dict[str, Decimal | None]
    competency_priorities: dict[str, Decimal] | None


def _validate_scope(*, user, assessment_run: AssessmentRun) -> None:
    if not getattr(user, "is_authenticated", False) or user.pk is None:
        raise ContextPriorityServiceError(
            "Context-aware priority requires an authenticated assessment owner."
        )
    if assessment_run.user_id != user.pk:
        raise ContextPriorityServiceError(
            "Context-aware priority requires one user-owned assessment epoch."
        )


def _candidate_ids(protocol_stable_ids: Sequence[str]) -> tuple[str, ...]:
    if isinstance(protocol_stable_ids, (str, bytes)) or not isinstance(
        protocol_stable_ids, Sequence
    ):
        raise ContextPriorityServiceError("Candidate protocol stable IDs must be a sequence.")
    resolved = tuple(protocol_stable_ids)
    if not resolved:
        raise ContextPriorityServiceError("Context-aware priority requires supplied candidates.")
    if any(not isinstance(item, str) or not item or len(item) > 120 for item in resolved):
        raise ContextPriorityServiceError("Candidate protocol stable IDs are malformed.")
    if len(resolved) != len(set(resolved)):
        raise ContextPriorityServiceError("Candidate protocol stable IDs must be unique.")
    return resolved


def _canonical_protocols(candidate_ids: tuple[str, ...]):
    try:
        canonical = load_and_validate_bundle()
        practices = load_practice_content_bundle(settings.BASE_DIR)
        validate_practice_content_mapping(practices, canonical)
    except (CanonicalDataError, PracticeContentError):
        raise ContextPriorityServiceError(
            "Canonical practice source failed context-priority validation."
        ) from None

    active_source = {protocol["stable_id"]: protocol for protocol in practices.runtime_protocols}
    if any(protocol_id not in active_source for protocol_id in candidate_ids):
        raise ContextPriorityServiceError(
            "Every context-priority candidate must be an active manifest-projected protocol."
        )
    mapping_rows = {
        row["competency_id"]: row["lever_weights"]
        for row in canonical.model["competency_lever_links"]
    }
    return active_source, mapping_rows


def _runtime_protocols(
    candidate_ids: tuple[str, ...],
    *,
    active_source: dict[str, dict[str, Any]],
    mapping_rows: dict[str, dict[str, Any]],
) -> tuple[PracticeProtocol, ...]:
    protocols = tuple(
        PracticeProtocol.objects.filter(stable_id__in=candidate_ids)
        .select_related("parent_competency")
        .prefetch_related("target_levers", "parent_competency__lever_links")
        .order_by("stable_id")
    )
    if len(protocols) != len(candidate_ids):
        raise ContextPriorityServiceError(
            "A supplied context-priority candidate is unavailable in the runtime catalog."
        )
    for protocol in protocols:
        source = active_source[protocol.stable_id]
        if protocol.availability != PracticeProtocol.Availability.ACTIVE:
            raise ContextPriorityServiceError(
                "Every context-priority candidate must be active in the runtime catalog."
            )
        parent_id = protocol.parent_competency_id
        if parent_id is None or parent_id != source["parent_competency_id"]:
            raise ContextPriorityServiceError(
                "A context-priority candidate has invalid canonical parent ownership."
            )
        source_weights = mapping_rows.get(parent_id)
        if not isinstance(source_weights, dict) or not source_weights:
            raise ContextPriorityServiceError(
                "A context-priority candidate has no canonical parent weights."
            )
        runtime_weights = {
            link.lever_id: link.weight for link in protocol.parent_competency.lever_links.all()
        }
        expected_weights = {
            lever_id: Decimal(str(weight)) for lever_id, weight in source_weights.items()
        }
        if runtime_weights != expected_weights:
            raise ContextPriorityServiceError(
                "A context-priority candidate canonical parent mapping does not verify."
            )
        target_ids = {lever.stable_id for lever in protocol.target_levers.all()}
        source_target_ids = set(source["target_levers"])
        if (
            not target_ids
            or target_ids != source_target_ids
            or not target_ids.issubset(runtime_weights)
        ):
            raise ContextPriorityServiceError(
                "A context-priority candidate recommendation-target subset does not verify."
            )
    return protocols


def _needs_for_epoch(*, user, assessment_run: AssessmentRun) -> EpochPriorityState:
    baselines = tuple(
        LeverBaseline.objects.filter(assessment_run=assessment_run).order_by("lever_id")
    )
    if not baselines:
        raise ContextPriorityServiceError(
            "Context-aware priority requires assessment need baselines."
        )
    if any(baseline.user_id != user.pk for baseline in baselines):
        raise ContextPriorityServiceError(
            "Context-aware priority requires user-owned assessment need baselines."
        )
    composite_state = CompositeScoreState.objects.filter(assessment_run=assessment_run).first()
    if composite_state is not None:
        if composite_state.user_id != user.pk:
            raise ContextPriorityServiceError(
                "Context-aware priority requires user-owned composite score state."
            )
        try:
            verify_composite_score_state_for_run(assessment_run)
        except CompositeScoreStateError:
            raise ContextPriorityServiceError(
                "Context-aware priority requires verified composite score state."
            ) from None
        needs = {
            lever_id: Decimal(row["remaining_need"])
            for lever_id, row in composite_state.state["levers"].items()
        }
        competency_priorities = {
            competency_id: Decimal(row["remaining_priority"])
            for competency_id, row in composite_state.state["competencies"].items()
        }
    else:
        states = tuple(
            LeverState.objects.filter(assessment_run=assessment_run).order_by("lever_id")
        )
        competency_priorities = None
    if composite_state is None and states:
        if any(state.user_id != user.pk for state in states):
            raise ContextPriorityServiceError(
                "Context-aware priority requires user-owned current lever state."
            )
        if len(states) != len(baselines):
            raise ContextPriorityServiceError(
                "Context-aware priority requires complete current lever-state coverage."
            )
        try:
            verify_score_state_for_run(assessment_run)
        except ScoreStateError:
            raise ContextPriorityServiceError(
                "Context-aware priority requires verified current score state."
            ) from None
        needs = {state.lever_id: state.current_need_score for state in states}
    elif composite_state is None:
        needs = {baseline.lever_id: baseline.need_score for baseline in baselines}
    for value in needs.values():
        if value is not None and (
            not isinstance(value, Decimal) or not value.is_finite() or value < 0 or value > 1
        ):
            raise ContextPriorityServiceError(
                "Context-aware priority requires finite bounded need values."
            )
    for value in (competency_priorities or {}).values():
        if not value.is_finite() or value < 0 or value > 1:
            raise ContextPriorityServiceError(
                "Context-aware priority requires finite bounded competency priorities."
            )
    return EpochPriorityState(
        lever_needs=needs,
        competency_priorities=competency_priorities,
    )


def _verified_latest_assessment_context(
    *, user, assessment_run: AssessmentRun
) -> AssessmentContext:
    records = tuple(
        AssessmentContext.objects.filter(assessment_run=assessment_run).order_by("revision")
    )
    if not records:
        raise ContextPriorityServiceError(
            "Context-aware priority requires a persisted assessment-context revision."
        )
    if [record.revision for record in records] != list(range(1, len(records) + 1)):
        raise ContextPriorityServiceError(
            "Assessment-context revisions are not latest and contiguous."
        )
    try:
        for record in records:
            if record.user_id != user.pk:
                raise ValidationError("ownership")
            record.full_clean()
    except (ValidationError, ValueError, TypeError):
        raise ContextPriorityServiceError(
            "Assessment context failed version, ownership, scope, snapshot, or hash validation."
        ) from None
    return records[-1]


def _verified_latest_practice_context(
    *,
    user,
    assessment_run: AssessmentRun,
    protocol: PracticeProtocol,
) -> PracticeContext:
    records = tuple(
        PracticeContext.objects.filter(
            assessment_run=assessment_run,
            protocol=protocol,
        ).order_by("revision")
    )
    if not records:
        raise ContextPriorityServiceError(
            "Every supplied candidate requires a persisted practice-context revision."
        )
    if [record.revision for record in records] != list(range(1, len(records) + 1)):
        raise ContextPriorityServiceError(
            "Practice-context revisions are not latest and contiguous."
        )
    try:
        for record in records:
            if record.user_id != user.pk:
                raise ValidationError("ownership")
            record.full_clean()
    except (ValidationError, ValueError, TypeError):
        raise ContextPriorityServiceError(
            "Practice context failed version, ownership, scope, snapshot, or hash validation."
        ) from None
    return records[-1]


def _base_priority(protocol: PracticeProtocol, priority_state: EpochPriorityState) -> Decimal:
    if priority_state.competency_priorities is not None:
        try:
            return priority_state.competency_priorities[protocol.parent_competency_id]
        except KeyError:
            raise ContextPriorityServiceError(
                "A context-priority candidate has no composite competency priority."
            ) from None
    try:
        return protocol_priority(
            priority_state.lever_needs,
            tuple(
                ProtocolWeight(lever_id=link.lever_id, weight=link.weight)
                for link in protocol.parent_competency.lever_links.all()
            ),
        )
    except RankingContractError:
        raise ContextPriorityServiceError(
            "Existing need-ranking input failed context-priority validation."
        ) from None


def build_context_priority_for_epoch(
    *,
    user,
    assessment_run: AssessmentRun,
    protocol_stable_ids: Sequence[str],
    alternative_request: AlternativeRequest | None = None,
) -> ContextPriorityResult:
    """Build an explicit backend-only priority result from latest verified context."""

    candidate_ids = _candidate_ids(protocol_stable_ids)
    active_source, mapping_rows = _canonical_protocols(candidate_ids)
    with transaction.atomic():
        try:
            locked_run = AssessmentRun.objects.select_for_update().get(pk=assessment_run.pk)
        except (AssessmentRun.DoesNotExist, TypeError, ValueError):
            raise ContextPriorityServiceError(
                "Context-aware priority requires an available assessment epoch."
            ) from None
        _validate_scope(user=user, assessment_run=locked_run)
        protocols = _runtime_protocols(
            candidate_ids,
            active_source=active_source,
            mapping_rows=mapping_rows,
        )
        priority_state = _needs_for_epoch(user=user, assessment_run=locked_run)
        assessment_context = _verified_latest_assessment_context(
            user=user,
            assessment_run=locked_run,
        )
        candidates = []
        for protocol in protocols:
            practice_context = _verified_latest_practice_context(
                user=user,
                assessment_run=locked_run,
                protocol=protocol,
            )
            candidates.append(
                ContextPriorityCandidateInput(
                    protocol_stable_id=protocol.stable_id,
                    base_priority=_base_priority(protocol, priority_state),
                    practice_context_hash=practice_context.content_hash,
                    factors={
                        factor_id: PriorityFactorValue(
                            state=getattr(practice_context, f"{factor_id}_state"),
                            value=getattr(practice_context, f"{factor_id}_value"),
                        )
                        for factor_id in (
                            "applicability",
                            "importance",
                            "readiness",
                            "urgency",
                            "opportunity_resources",
                            "burden",
                        )
                    },
                    disposition=practice_context.disposition,
                    context_contract_version=practice_context.contract_version,
                )
            )
        try:
            return build_context_priority_result(
                assessment_epoch_id=locked_run.pk,
                assessment_context_hash=assessment_context.content_hash,
                assessment_factors={
                    "season": PriorityFactorValue(
                        state=assessment_context.season_state,
                        value=assessment_context.season_value or None,
                    ),
                    "capacity": PriorityFactorValue(
                        state=assessment_context.capacity_state,
                        value=assessment_context.capacity_value,
                    ),
                },
                candidates=tuple(candidates),
                alternative_request=alternative_request,
                context_contract_version=assessment_context.contract_version,
                need_ranking_algorithm_version=(
                    COMPOSITE_SCORING_VERSION
                    if priority_state.competency_priorities is not None
                    else "GG-NEED-RANKING-1.0"
                ),
            )
        except ContextPriorityContractError:
            raise ContextPriorityServiceError(
                "Verified context failed deterministic context-priority evaluation."
            ) from None


def _load_golden_fixture() -> tuple[dict[str, Any], str]:
    path = settings.BASE_DIR / GOLDEN_FIXTURE_PATH
    try:
        raw = path.read_bytes()
        fixture = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise ContextPriorityReadinessError(
            "The committed context-priority golden fixture is unavailable or malformed."
        ) from None
    if not isinstance(fixture, dict):
        raise ContextPriorityReadinessError(
            "The committed context-priority golden fixture must be an object."
        )
    import hashlib

    return fixture, hashlib.sha256(raw).hexdigest()


def _replay_golden_fixture(fixture: dict[str, Any]) -> ContextPriorityResult:
    try:
        candidate_rows = fixture["candidates"]
        if not isinstance(candidate_rows, list):
            raise TypeError
        alternative_row = fixture.get("alternative_request")
        alternative = (
            AlternativeRequest(
                source_protocol_stable_id=alternative_row["source_protocol_stable_id"],
                reason=alternative_row["reason"],
            )
            if isinstance(alternative_row, dict)
            else None
        )
        result = build_context_priority_result(
            assessment_epoch_id=fixture["assessment_epoch_id"],
            assessment_context_hash=fixture["assessment_context_hash"],
            assessment_factors=fixture["assessment_factors"],
            candidates=tuple(
                ContextPriorityCandidateInput(
                    protocol_stable_id=row["protocol_stable_id"],
                    base_priority=Decimal(row["base_priority"]),
                    practice_context_hash=row["practice_context_hash"],
                    factors=row["factors"],
                    disposition=row["disposition"],
                    context_contract_version=row["context_contract_version"],
                )
                for row in candidate_rows
            ),
            alternative_request=alternative,
            context_contract_version=fixture["context_contract_version"],
            algorithm_version=fixture["algorithm_version"],
            need_ranking_algorithm_version=fixture["need_ranking_algorithm_version"],
        )
    except (KeyError, TypeError, ValueError, ContextPriorityContractError):
        raise ContextPriorityReadinessError(
            "The committed context-priority golden fixture failed deterministic replay."
        ) from None
    if result.content_hash != fixture.get("expected_result_hash"):
        raise ContextPriorityReadinessError(
            "The committed context-priority golden result hash does not verify."
        )
    if list(result.ranked_candidate_ids) != fixture.get("expected_ranked_candidate_ids"):
        raise ContextPriorityReadinessError(
            "The committed context-priority golden ordering does not verify."
        )
    if result.primary_protocol_stable_id != fixture.get("expected_primary_protocol_stable_id"):
        raise ContextPriorityReadinessError(
            "The committed context-priority golden primary recommendation does not verify."
        )
    return result


def verify_context_priority_readiness() -> ContextPriorityReadinessSummary:
    """Replay M6C-03 and validate persisted context/catalog state without writing."""

    fixture, fixture_hash = _load_golden_fixture()
    result = _replay_golden_fixture(fixture)
    try:
        context_summary = verify_context_readiness()
    except ContextReadinessError:
        raise ContextPriorityReadinessError(
            "Persisted context failed private version, ownership, scope, factor, snapshot, "
            "hash, or revision verification."
        ) from None

    try:
        canonical = load_and_validate_bundle()
        practices = load_practice_content_bundle(settings.BASE_DIR)
        validate_practice_content_mapping(practices, canonical)
        projected_ids = tuple(
            sorted(protocol["stable_id"] for protocol in practices.runtime_protocols)
        )
        if not M6C03_BASELINE_PROTOCOL_IDS.issubset(projected_ids):
            raise ContextPriorityReadinessError(
                "The M6C-03 baseline protocol cohort is absent from the canonical projection."
            )
        mapping_rows = {
            row["competency_id"]: row["lever_weights"]
            for row in canonical.model["competency_lever_links"]
        }
        source_by_id = {protocol["stable_id"]: protocol for protocol in practices.runtime_protocols}
        runtime = _runtime_protocols(
            projected_ids,
            active_source=source_by_id,
            mapping_rows=mapping_rows,
        )
    except ContextPriorityReadinessError:
        raise
    except (
        CanonicalDataError,
        PracticeContentError,
        ContextPriorityServiceError,
        KeyError,
        TypeError,
        ValueError,
    ):
        raise ContextPriorityReadinessError(
            "Canonical context-priority catalog mapping failed validation."
        ) from None

    activation_entries = practices.activation_entries
    runtime_activation = {protocol.stable_id: protocol.score_active for protocol in runtime}
    expected_activation = {
        protocol_id: bool(activation_entries[protocol_id]["score_active"])
        for protocol_id in projected_ids
    }
    if runtime_activation != expected_activation:
        raise ContextPriorityReadinessError(
            "Runtime score activation does not match the canonical activation ledger."
        )
    if not runtime_activation.get(FRIENDSHIP_PROTOCOL_ID, False):
        raise ContextPriorityReadinessError(
            "The reviewed friendship production activation boundary is unavailable."
        )
    return ContextPriorityReadinessSummary(
        contract_version=CONTEXT_PRIORITY_READINESS_CONTRACT_VERSION,
        algorithm_version=CONTEXT_PRIORITY_ALGORITHM_VERSION,
        context_contract_version=CONTEXT_CONTRACT_VERSION,
        need_ranking_algorithm_version=result.canonical_payload()["dependencies"][
            "need_ranking_algorithm_version"
        ],
        synthetic_fixture_hash=fixture_hash,
        synthetic_result_hash=result.content_hash,
        projected_protocols=len(projected_ids),
        m6c03_baseline_protocols_present=len(M6C03_BASELINE_PROTOCOL_IDS),
        score_active_protocols=sum(runtime_activation.values()),
        friendship_score_active=True,
        assessment_context_records=context_summary.assessment_records,
        practice_context_records=context_summary.practice_records,
        software_ready=True,
        changes_recommendations=False,
        changes_score_state=False,
        changes_production_activation=False,
        ordinary_ui_changes=False,
    )
