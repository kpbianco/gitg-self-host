from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.utils import timezone

from growth.models import (
    ArchetypeResult,
    AssessmentContext,
    AssessmentRun,
    CompletionCreditEvent,
    CompositeAssessmentSnapshot,
    CompositeScoreSnapshot,
    CompositeScoreState,
    EvidenceEvent,
    LeverBaseline,
    LeverState,
    OrientationResult,
    PersonalOSRevision,
    PilotFeedback,
    PracticeCheckIn,
    PracticeContext,
    PracticeReview,
    PracticeSprint,
    ScoreSnapshot,
    WeeklyExecutionPlan,
    WeeklyExecutionReview,
)
from growth.services.evidence import build_privacy_safe_evidence_export

OWNER_ARCHIVE_SCHEMA_VERSION = "grounded-growth-owner-private-archive-v2"
DELETION_POLICY_VERSION = "GG-OWNER-DELETION-1.0"
RETENTION_POLICY_VERSION = "GG-OWNER-RETENTION-1.0"


class DataLifecycleError(ValueError):
    pass


@dataclass(frozen=True)
class DeletionPreview:
    policy_version: str
    record_counts: dict[str, int]
    total_records: int
    content_hash: str


@dataclass(frozen=True)
class RetentionPreview:
    policy_version: str
    enabled: bool
    retention_days: int
    as_of: date
    cutoff_date: date
    record_counts: dict[str, int]
    total_records: int
    content_hash: str


@dataclass(frozen=True)
class RetentionResult:
    deleted_draft_check_ins: int
    deleted_pilot_feedback: int

    @property
    def total_deleted(self) -> int:
        return self.deleted_draft_check_ins + self.deleted_pilot_feedback


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        cls=DjangoJSONEncoder,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _content_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _record(instance: models.Model, fields: Iterable[str], **references: Any) -> dict[str, Any]:
    return {**references, **{field: getattr(instance, field) for field in fields}}


def _references(instances: list[models.Model], prefix: str) -> dict[Any, str]:
    return {instance.pk: f"{prefix}-{index:04d}" for index, instance in enumerate(instances, 1)}


def _replace_internal_references(value: Any, references: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _replace_internal_references(item, references) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_internal_references(item, references) for item in value]
    if isinstance(value, tuple):
        return [_replace_internal_references(item, references) for item in value]
    if isinstance(value, str):
        return references.get(value, value)
    return value


def _owned_querysets(user) -> dict[str, models.QuerySet]:
    return {
        "assessment_runs": AssessmentRun.objects.filter(user=user),
        "composite_assessment_snapshots": CompositeAssessmentSnapshot.objects.filter(
            assessment_run__user=user
        ),
        "orientation_results": OrientationResult.objects.filter(assessment_run__user=user),
        "archetype_results": ArchetypeResult.objects.filter(assessment_run__user=user),
        "lever_baselines": LeverBaseline.objects.filter(user=user),
        "lever_states": LeverState.objects.filter(user=user),
        "practice_sprints": PracticeSprint.objects.filter(user=user),
        "practice_check_ins": PracticeCheckIn.objects.filter(sprint__user=user),
        "evidence_events": EvidenceEvent.objects.filter(check_in__sprint__user=user),
        "score_snapshots": ScoreSnapshot.objects.filter(assessment_run__user=user),
        "completion_credit_events": CompletionCreditEvent.objects.filter(assessment_run__user=user),
        "composite_score_states": CompositeScoreState.objects.filter(user=user),
        "composite_score_snapshots": CompositeScoreSnapshot.objects.filter(
            assessment_run__user=user
        ),
        "practice_reviews": PracticeReview.objects.filter(sprint__user=user),
        "pilot_feedback": PilotFeedback.objects.filter(user=user),
        "assessment_context": AssessmentContext.objects.filter(user=user),
        "practice_context": PracticeContext.objects.filter(user=user),
        "personal_os_revisions": PersonalOSRevision.objects.filter(user=user),
        "weekly_execution_plans": WeeklyExecutionPlan.objects.filter(user=user),
        "weekly_execution_reviews": WeeklyExecutionReview.objects.filter(user=user),
    }


def _owned_session_keys(user) -> tuple[str, ...]:
    user_id = str(user.pk)
    keys = []
    for session in Session.objects.all().only("session_key", "session_data"):
        try:
            session_user_id = session.get_decoded().get("_auth_user_id")
        except Exception:  # pragma: no cover - corrupt sessions are not attributable
            continue
        if str(session_user_id) == user_id:
            keys.append(session.session_key)
    return tuple(sorted(keys))


def build_owner_archive(user) -> dict[str, Any]:
    """Build one deterministic, explicit, owner-private archive without database keys."""

    build_privacy_safe_evidence_export(user)

    assessments = list(AssessmentRun.objects.filter(user=user).order_by("created_at", "stable_id"))
    sprints = list(PracticeSprint.objects.filter(user=user).order_by("created_at", "stable_id"))
    check_ins = list(
        PracticeCheckIn.objects.filter(sprint__user=user).order_by("created_at", "stable_id")
    )
    evidence_events = list(
        EvidenceEvent.objects.filter(check_in__sprint__user=user).order_by(
            "created_at", "stable_id"
        )
    )
    practice_reviews = list(
        PracticeReview.objects.filter(sprint__user=user).order_by("submitted_at", "stable_id")
    )
    completion_credit_events = list(
        CompletionCreditEvent.objects.filter(assessment_run__user=user).order_by(
            "assessment_run__created_at", "assessment_run_id", "created_at", "stable_id"
        )
    )
    weekly_plans = list(
        WeeklyExecutionPlan.objects.filter(user=user).order_by(
            "week_start", "revision", "stable_id"
        )
    )

    assessment_refs = _references(assessments, "assessment")
    sprint_refs = _references(sprints, "sprint")
    check_in_refs = _references(check_ins, "check-in")
    evidence_refs = _references(evidence_events, "evidence")
    practice_review_refs = _references(practice_reviews, "practice-review")
    completion_credit_refs = _references(completion_credit_events, "completion-credit")
    weekly_plan_refs = _references(weekly_plans, "weekly-plan")
    internal_references = {
        str(key): value
        for mapping in (
            assessment_refs,
            sprint_refs,
            check_in_refs,
            evidence_refs,
            practice_review_refs,
            completion_credit_refs,
            weekly_plan_refs,
        )
        for key, value in mapping.items()
    }

    records: dict[str, list[dict[str, Any]]] = {
        "assessment_runs": [
            _record(
                item,
                (
                    "assessment_version",
                    "source",
                    "answers",
                    "clarifier_answers",
                    "timing_data",
                    "response_quality_result",
                    "orientation_outputs",
                    "archetype_outputs",
                    "raw_lever_scores",
                    "calibrated_lever_estimates",
                    "lever_confidence",
                    "original_share_code",
                    "created_at",
                ),
                archive_ref=assessment_refs[item.pk],
                curriculum_version_stable_id=item.curriculum_version_id,
            )
            for item in assessments
        ],
        "composite_assessment_snapshots": [
            _record(
                item,
                (
                    "algorithm_version",
                    "state_schema_version",
                    "projection",
                    "projection_hash",
                    "created_at",
                ),
                assessment_ref=assessment_refs[item.assessment_run_id],
            )
            for item in CompositeAssessmentSnapshot.objects.filter(
                assessment_run__user=user
            ).order_by("assessment_run__created_at", "assessment_run_id")
        ],
        "orientation_results": [
            _record(
                item,
                ("stable_id", "slug", "name", "score", "confidence"),
                assessment_ref=assessment_refs[item.assessment_run_id],
            )
            for item in OrientationResult.objects.filter(assessment_run__user=user).order_by(
                "assessment_run__created_at", "assessment_run_id", "-score", "stable_id"
            )
        ],
        "archetype_results": [
            _record(
                item,
                ("stable_id", "name", "orientation_slugs", "fit_index", "fit_confidence", "rank"),
                assessment_ref=assessment_refs[item.assessment_run_id],
            )
            for item in ArchetypeResult.objects.filter(assessment_run__user=user).order_by(
                "assessment_run__created_at", "assessment_run_id", "rank", "stable_id"
            )
        ],
        "lever_baselines": [
            _record(
                item,
                (
                    "raw_self_report",
                    "calibrated_estimate",
                    "evidence_confidence",
                    "baseline_alpha",
                    "baseline_beta",
                    "baseline_mass_source",
                    "need_score",
                    "need_rank",
                    "notes",
                ),
                assessment_ref=assessment_refs[item.assessment_run_id],
                lever_stable_id=item.lever_id,
            )
            for item in LeverBaseline.objects.filter(user=user).order_by(
                "assessment_run__created_at", "assessment_run_id", "need_rank", "lever_id"
            )
        ],
        "lever_states": [
            _record(
                item,
                (
                    "algorithm_version",
                    "status",
                    "current_alpha",
                    "current_beta",
                    "current_estimate",
                    "current_confidence",
                    "cumulative_evidence_mass",
                    "included_evidence_events",
                    "current_need_score",
                    "current_need_rank",
                    "updated_at",
                ),
                assessment_ref=assessment_refs[item.assessment_run_id],
                baseline_ref=f"{assessment_refs[item.assessment_run_id]}:{item.lever_id}",
                lever_stable_id=item.lever_id,
            )
            for item in LeverState.objects.filter(user=user).order_by(
                "assessment_run__created_at", "assessment_run_id", "current_need_rank", "lever_id"
            )
        ],
        "practice_sprints": [
            _record(
                item,
                (
                    "person_or_context",
                    "scoring_contract_version",
                    "start_date",
                    "status",
                    "created_at",
                    "setup_completed_at",
                    "boundaries_acknowledged_at",
                    "paused_at",
                    "stopped_at",
                    "completed_at",
                ),
                archive_ref=sprint_refs[item.pk],
                protocol_stable_id=item.protocol_id,
                assessment_ref=(
                    assessment_refs[item.assessment_run_id]
                    if item.assessment_run_id is not None
                    else None
                ),
            )
            for item in sprints
        ],
        "practice_check_ins": [
            _record(
                item,
                (
                    "status",
                    "action_attempted",
                    "action_completed",
                    "user_initiated",
                    "moved_beyond_transactional",
                    "follow_up_question_asked",
                    "meaningful_information_shared",
                    "future_interaction_scheduled",
                    "follow_up_within_seven_days",
                    "internal_resistance",
                    "expected_reciprocity",
                    "observed_reciprocity",
                    "typed_observations",
                    "support_level",
                    "context_comparison",
                    "evidence_direction",
                    "contradictory_evidence",
                    "note",
                    "created_at",
                    "updated_at",
                    "submitted_at",
                ),
                archive_ref=check_in_refs[item.pk],
                sprint_ref=sprint_refs[item.sprint_id],
                action_stable_id=item.action_id,
            )
            for item in check_ins
        ],
        "evidence_events": [
            _record(
                item,
                (
                    "algorithm_version",
                    "protocol_stable_id",
                    "action_stable_id",
                    "input_snapshot",
                    "performance",
                    "quality",
                    "independence",
                    "context_breadth",
                    "repetition_index",
                    "repetition_multiplier",
                    "contradiction_level",
                    "base_evidence_mass",
                    "explanation",
                    "created_at",
                ),
                archive_ref=evidence_refs[item.pk],
                check_in_ref=check_in_refs[item.check_in_id],
            )
            for item in evidence_events
        ],
        "score_snapshots": [
            _record(
                item,
                (
                    "operation",
                    "sequence",
                    "algorithm_version",
                    "state_schema_version",
                    "before_state",
                    "after_state",
                    "contribution_snapshot",
                    "active_event_count",
                    "active_event_hash",
                    "before_state_hash",
                    "after_state_hash",
                    "reason",
                    "created_at",
                ),
                assessment_ref=assessment_refs[item.assessment_run_id],
                evidence_ref=(
                    evidence_refs[item.evidence_event_id]
                    if item.evidence_event_id is not None
                    else None
                ),
            )
            for item in ScoreSnapshot.objects.filter(assessment_run__user=user).order_by(
                "assessment_run__created_at", "assessment_run_id", "sequence"
            )
        ],
        "completion_credit_events": [
            _record(
                item,
                (
                    "algorithm_version",
                    "completed_action_ids",
                    "total_actions",
                    "minimum_completed",
                    "completion_credit",
                    "source_snapshot",
                    "source_hash",
                    "created_at",
                ),
                archive_ref=completion_credit_refs[item.pk],
                assessment_ref=assessment_refs[item.assessment_run_id],
                sprint_ref=sprint_refs[item.sprint_id],
                review_ref=practice_review_refs[item.review_id],
                protocol_stable_id=item.protocol_id,
                competency_stable_id=item.competency_id,
            )
            for item in completion_credit_events
        ],
        "composite_score_states": [
            _record(
                item,
                (
                    "algorithm_version",
                    "state_schema_version",
                    "state",
                    "state_hash",
                    "active_event_count",
                    "active_event_hash",
                    "updated_at",
                ),
                assessment_ref=assessment_refs[item.assessment_run_id],
            )
            for item in CompositeScoreState.objects.filter(user=user).order_by(
                "assessment_run__created_at", "assessment_run_id"
            )
        ],
        "composite_score_snapshots": [
            _record(
                item,
                (
                    "operation",
                    "sequence",
                    "algorithm_version",
                    "state_schema_version",
                    "before_state",
                    "after_state",
                    "active_event_count",
                    "active_event_hash",
                    "before_state_hash",
                    "after_state_hash",
                    "reason",
                    "created_at",
                ),
                assessment_ref=assessment_refs[item.assessment_run_id],
                completion_credit_ref=(
                    completion_credit_refs[item.completion_credit_event_id]
                    if item.completion_credit_event_id is not None
                    else None
                ),
            )
            for item in CompositeScoreSnapshot.objects.filter(assessment_run__user=user).order_by(
                "assessment_run__created_at", "assessment_run_id", "sequence"
            )
        ],
        "practice_reviews": [
            _record(
                item,
                (
                    "actions_attempted",
                    "actions_completed",
                    "substantive_interaction_occurred",
                    "reflection",
                    "contradictory_evidence",
                    "static_score_impact_preview",
                    "mastery_disclaimer",
                    "submitted_at",
                ),
                archive_ref=practice_review_refs[item.pk],
                sprint_ref=sprint_refs[item.sprint_id],
            )
            for item in practice_reviews
        ],
        "pilot_feedback": [
            _record(
                item,
                (
                    "contract_version",
                    "journey_stage",
                    "applicability",
                    "time_to_start",
                    "time_to_check_in",
                    "confusing_step",
                    "accessibility_friction",
                    "safety_friction",
                    "comment",
                    "submitted_at",
                ),
                protocol_stable_id=item.protocol_id,
            )
            for item in PilotFeedback.objects.filter(user=user).order_by(
                "submitted_at", "stable_id"
            )
        ],
        "assessment_context": [
            _record(
                item,
                (
                    "contract_version",
                    "revision",
                    "season_state",
                    "season_value",
                    "capacity_state",
                    "capacity_value",
                    "canonical_snapshot",
                    "content_hash",
                    "created_at",
                ),
                assessment_ref=assessment_refs[item.assessment_run_id],
            )
            for item in AssessmentContext.objects.filter(user=user).order_by(
                "assessment_run__created_at", "assessment_run_id", "revision"
            )
        ],
        "practice_context": [
            _record(
                item,
                (
                    "contract_version",
                    "revision",
                    "applicability_state",
                    "applicability_value",
                    "importance_state",
                    "importance_value",
                    "readiness_state",
                    "readiness_value",
                    "urgency_state",
                    "urgency_value",
                    "opportunity_resources_state",
                    "opportunity_resources_value",
                    "burden_state",
                    "burden_value",
                    "disposition",
                    "defer_reason",
                    "review_horizon_days",
                    "canonical_snapshot",
                    "content_hash",
                    "created_at",
                ),
                assessment_ref=assessment_refs[item.assessment_run_id],
                protocol_stable_id=item.protocol_id,
            )
            for item in PracticeContext.objects.filter(user=user).order_by(
                "assessment_run__created_at", "assessment_run_id", "protocol_id", "revision"
            )
        ],
        "personal_os_revisions": [
            _record(
                item,
                (
                    "contract_version",
                    "revision",
                    "mission_state",
                    "mission_value",
                    "twelve_month_direction_state",
                    "twelve_month_direction_value",
                    "current_truth_state",
                    "current_truth_value",
                    "autopilot_pattern_state",
                    "autopilot_pattern_value",
                    "misalignment_or_fragmentation_state",
                    "misalignment_or_fragmentation_value",
                    "deliberate_next_step_state",
                    "deliberate_next_step_value",
                    "principles_state",
                    "principles_value",
                    "anti_goals_state",
                    "anti_goals_value",
                    "priority_stack_state",
                    "priority_stack_value",
                    "canonical_snapshot",
                    "content_hash",
                    "created_at",
                ),
                assessment_ref=assessment_refs[item.assessment_run_id],
            )
            for item in PersonalOSRevision.objects.filter(user=user).order_by(
                "assessment_run__created_at", "assessment_run_id", "revision"
            )
        ],
        "weekly_execution_plans": [
            _record(
                item,
                (
                    "contract_version",
                    "week_start",
                    "revision",
                    "intended_on",
                    "canonical_snapshot",
                    "content_hash",
                    "created_at",
                ),
                archive_ref=weekly_plan_refs[item.pk],
                assessment_ref=assessment_refs[item.assessment_run_id],
                sprint_ref=sprint_refs[item.sprint_id],
                action_stable_id=item.action_id,
            )
            for item in weekly_plans
        ],
        "weekly_execution_reviews": [
            _record(
                item,
                (
                    "contract_version",
                    "outcome",
                    "next_step",
                    "adjustment",
                    "canonical_snapshot",
                    "content_hash",
                    "submitted_at",
                ),
                plan_ref=weekly_plan_refs[item.plan_id],
            )
            for item in WeeklyExecutionReview.objects.filter(user=user).order_by(
                "plan__week_start", "plan__revision", "stable_id"
            )
        ],
    }
    records = _replace_internal_references(records, internal_references)
    record_counts = {name: len(items) for name, items in records.items()}
    content = {
        "schema_version": OWNER_ARCHIVE_SCHEMA_VERSION,
        "privacy_class": "owner-private",
        "account": {
            "username": user.get_username(),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "date_joined": user.date_joined,
        },
        "privacy": {
            "contains_private_narrative": True,
            "safe_for_sharing": False,
            "contains_other_users": False,
            "contains_internal_database_keys": False,
            "excluded": [
                "password hash and password reset material",
                "sessions, CSRF state, and authentication tokens",
                "staff, permission, and group assignments",
                "other users and their records",
                "database primary keys and opaque UUID record identifiers",
                "server environment, secrets, logs, and deployment metadata",
            ],
        },
        "record_counts": record_counts,
        "records": records,
    }
    return {**content, "content_sha256": _content_hash(content)}


def render_owner_archive(user) -> bytes:
    return (_canonical_json(build_owner_archive(user)) + "\n").encode("utf-8")


def build_deletion_preview(user) -> DeletionPreview:
    counts = {name: queryset.count() for name, queryset in _owned_querysets(user).items()}
    counts = {"account": 1, "sessions": len(_owned_session_keys(user)), **counts}
    body = {"policy_version": DELETION_POLICY_VERSION, "record_counts": counts}
    return DeletionPreview(
        policy_version=DELETION_POLICY_VERSION,
        record_counts=counts,
        total_records=sum(counts.values()),
        content_hash=_content_hash(body),
    )


def _force_delete(queryset: models.QuerySet) -> int:
    deleted, _ = models.QuerySet.delete(queryset)
    return deleted


@transaction.atomic
def delete_owner_account(*, user, expected_preview_hash: str) -> int:
    user_model = get_user_model()
    try:
        locked_user = user_model.objects.select_for_update().get(pk=user.pk)
    except user_model.DoesNotExist as exc:
        raise DataLifecycleError("The account no longer exists.") from exc
    preview = build_deletion_preview(locked_user)
    if preview.content_hash != expected_preview_hash:
        raise DataLifecycleError("The deletion preview changed. Review the current counts again.")

    ordered = (
        CompositeScoreSnapshot.objects.filter(assessment_run__user=locked_user),
        CompletionCreditEvent.objects.filter(assessment_run__user=locked_user),
        CompositeAssessmentSnapshot.objects.filter(assessment_run__user=locked_user),
        CompositeScoreState.objects.filter(user=locked_user),
        ScoreSnapshot.objects.filter(assessment_run__user=locked_user),
        WeeklyExecutionReview.objects.filter(user=locked_user),
        WeeklyExecutionPlan.objects.filter(user=locked_user),
        PracticeReview.objects.filter(sprint__user=locked_user),
        EvidenceEvent.objects.filter(check_in__sprint__user=locked_user),
        PracticeCheckIn.objects.filter(sprint__user=locked_user),
        PracticeSprint.objects.filter(user=locked_user),
        LeverState.objects.filter(user=locked_user),
        LeverBaseline.objects.filter(user=locked_user),
        PersonalOSRevision.objects.filter(user=locked_user),
        PracticeContext.objects.filter(user=locked_user),
        AssessmentContext.objects.filter(user=locked_user),
        OrientationResult.objects.filter(assessment_run__user=locked_user),
        ArchetypeResult.objects.filter(assessment_run__user=locked_user),
        AssessmentRun.objects.filter(user=locked_user),
        PilotFeedback.objects.filter(user=locked_user),
    )
    for queryset in ordered:
        _force_delete(queryset)
    Session.objects.filter(session_key__in=_owned_session_keys(locked_user)).delete()
    user_model.objects.filter(pk=locked_user.pk).delete()
    if user_model.objects.filter(pk=locked_user.pk).exists():
        raise DataLifecycleError("Account deletion did not finish exactly once.")
    return preview.total_records


def build_retention_preview(
    user,
    *,
    enabled: bool | None = None,
    retention_days: int | None = None,
    as_of: date | None = None,
) -> RetentionPreview:
    enabled = settings.OWNER_RETENTION_ENABLED if enabled is None else enabled
    retention_days = settings.OWNER_RETENTION_DAYS if retention_days is None else retention_days
    if not 30 <= retention_days <= 3650:
        raise DataLifecycleError("Retention days must be between 30 and 3650.")
    as_of = timezone.localdate() if as_of is None else as_of
    cutoff = as_of - timedelta(days=retention_days)
    counts = {"draft_check_ins": 0, "pilot_feedback": 0}
    if enabled:
        counts = {
            "draft_check_ins": PracticeCheckIn.objects.filter(
                sprint__user=user,
                status=PracticeCheckIn.Status.DRAFT,
                updated_at__date__lt=cutoff,
            ).count(),
            "pilot_feedback": PilotFeedback.objects.filter(
                user=user,
                submitted_at__date__lt=cutoff,
            ).count(),
        }
    body = {
        "policy_version": RETENTION_POLICY_VERSION,
        "enabled": enabled,
        "retention_days": retention_days,
        "as_of": as_of,
        "cutoff_date": cutoff,
        "record_counts": counts,
    }
    return RetentionPreview(
        policy_version=RETENTION_POLICY_VERSION,
        enabled=enabled,
        retention_days=retention_days,
        as_of=as_of,
        cutoff_date=cutoff,
        record_counts=counts,
        total_records=sum(counts.values()),
        content_hash=_content_hash(body),
    )


@transaction.atomic
def apply_retention(*, user, expected_preview_hash: str, as_of: date) -> RetentionResult:
    user_model = get_user_model()
    try:
        locked_user = user_model.objects.select_for_update().get(pk=user.pk)
    except user_model.DoesNotExist as exc:
        raise DataLifecycleError("The account no longer exists.") from exc
    preview = build_retention_preview(locked_user, as_of=as_of)
    if not preview.enabled:
        raise DataLifecycleError("Retention is disabled. No records were changed.")
    if preview.content_hash != expected_preview_hash:
        raise DataLifecycleError("The retention preview changed. Review it again before applying.")

    draft_count = _force_delete(
        PracticeCheckIn.objects.filter(
            sprint__user=locked_user,
            status=PracticeCheckIn.Status.DRAFT,
            updated_at__date__lt=preview.cutoff_date,
        )
    )
    feedback_count = _force_delete(
        PilotFeedback.objects.filter(
            user=locked_user,
            submitted_at__date__lt=preview.cutoff_date,
        )
    )
    return RetentionResult(
        deleted_draft_check_ins=draft_count,
        deleted_pilot_feedback=feedback_count,
    )
