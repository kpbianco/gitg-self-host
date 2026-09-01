import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from growth.domain.context import (
    CONTEXT_CONTRACT_VERSION,
    REVIEW_HORIZON_DAYS_MAX,
    REVIEW_HORIZON_DAYS_MIN,
    ContextValueState,
    DeferReason,
    PracticeDisposition,
    SeasonCode,
    build_assessment_context_snapshot,
    build_practice_context_snapshot,
)
from growth.domain.personal_os import (
    AUDIT_PROMPT_IDS,
    IDENTITY_SECTION_IDS,
    LIST_SECTION_IDS,
    PERSONAL_OS_CONTRACT_VERSION,
    SCALAR_SECTION_IDS,
    PersonalOSValueState,
    build_personal_os_snapshot,
)
from growth.domain.weekly_execution import (
    WEEKLY_EXECUTION_CONTRACT_VERSION,
    WeeklyAdjustment,
    WeeklyNextStep,
    WeeklyProofOutcome,
    build_weekly_plan_snapshot,
    build_weekly_review_snapshot,
)

MASTERY_DISCLAIMER = "Completing this practice does not establish mastery."
PILOT_FEEDBACK_CONTRACT_VERSION = "GG-PILOT-FEEDBACK-1.0"


class CurriculumVersion(models.Model):
    stable_id = models.CharField(max_length=80, primary_key=True)
    curriculum_version = models.CharField(max_length=80)
    model_version = models.CharField(max_length=40)
    assessment_version = models.CharField(max_length=40)
    source_hash = models.CharField(max_length=64)
    active = models.BooleanField(default=True)
    imported_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["stable_id"]

    def __str__(self) -> str:
        return self.stable_id


class Lever(models.Model):
    stable_id = models.CharField(max_length=8, primary_key=True)
    curriculum_version = models.ForeignKey(
        CurriculumVersion, on_delete=models.PROTECT, related_name="levers"
    )
    slug = models.SlugField(max_length=100)
    name = models.CharField(max_length=180)
    family_id = models.CharField(max_length=8)
    family_slug = models.SlugField(max_length=100)
    family_name = models.CharField(max_length=140)
    definition = models.TextField()
    orientation_composition = models.JSONField(default=dict)
    competency_count = models.PositiveSmallIntegerField()
    total_competency_weight = models.DecimalField(max_digits=8, decimal_places=4)

    class Meta:
        ordering = ["stable_id"]

    def __str__(self) -> str:
        return f"{self.stable_id} — {self.name}"


class Competency(models.Model):
    stable_id = models.CharField(max_length=8, primary_key=True)
    curriculum_version = models.ForeignKey(
        CurriculumVersion, on_delete=models.PROTECT, related_name="competencies"
    )
    domain_id = models.CharField(max_length=8)
    domain_name = models.CharField(max_length=180)
    name = models.CharField(max_length=220)
    scope = models.TextField()
    evidence_of_progress = models.TextField()
    applicability = models.CharField(max_length=80)
    normative_status = models.CharField(max_length=100)
    formation_modes = models.JSONField(default=list)
    preferred_evidence_types = models.JSONField(default=list)
    professional_boundary = models.TextField(blank=True)

    class Meta:
        ordering = ["stable_id"]

    def __str__(self) -> str:
        return f"{self.stable_id} — {self.name}"


class CompetencyLeverLink(models.Model):
    competency = models.ForeignKey(Competency, on_delete=models.CASCADE, related_name="lever_links")
    lever = models.ForeignKey(Lever, on_delete=models.PROTECT, related_name="competency_links")
    weight = models.DecimalField(max_digits=5, decimal_places=4)

    class Meta:
        ordering = ["competency_id", "-weight", "lever_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["competency", "lever"], name="unique_competency_lever_link"
            ),
            models.CheckConstraint(
                condition=Q(weight__gt=0) & Q(weight__lte=1),
                name="competency_lever_weight_in_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.competency_id} → {self.lever_id} ({self.weight})"


class ImmutableAssessmentRunQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Assessment runs are immutable after creation.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Assessment runs are immutable after creation.")


class AssessmentRun(models.Model):
    class Source(models.TextChoices):
        APPLICATION = "application", "Application"
        SHARE_CODE = "share_code", "Share code"
        PILOT_SEED = "pilot_seed", "Pilot seed"

    stable_id = models.CharField(max_length=80, primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assessment_runs"
    )
    curriculum_version = models.ForeignKey(
        CurriculumVersion, on_delete=models.PROTECT, related_name="assessment_runs"
    )
    assessment_version = models.CharField(max_length=40)
    source = models.CharField(max_length=20, choices=Source.choices)
    answers = models.JSONField(default=dict)
    clarifier_answers = models.JSONField(default=dict)
    timing_data = models.JSONField(default=dict)
    response_quality_result = models.JSONField(default=dict)
    orientation_outputs = models.JSONField(default=dict)
    archetype_outputs = models.JSONField(default=list)
    raw_lever_scores = models.JSONField(default=dict)
    calibrated_lever_estimates = models.JSONField(default=dict)
    lever_confidence = models.JSONField(default=dict)
    original_share_code = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableAssessmentRunQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.stable_id} ({self.assessment_version})"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Assessment runs are immutable after creation.")
        return super().save(*args, **kwargs)


class OrientationResult(models.Model):
    assessment_run = models.ForeignKey(
        AssessmentRun, on_delete=models.CASCADE, related_name="orientation_results"
    )
    stable_id = models.CharField(max_length=8)
    slug = models.SlugField(max_length=80)
    name = models.CharField(max_length=120)
    score = models.DecimalField(max_digits=6, decimal_places=4)
    confidence = models.DecimalField(max_digits=6, decimal_places=4)

    class Meta:
        ordering = ["-score", "stable_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment_run", "stable_id"],
                name="unique_orientation_per_assessment",
            )
        ]

    def __str__(self) -> str:
        return f"{self.assessment_run_id}: {self.name}"


class ArchetypeResult(models.Model):
    assessment_run = models.ForeignKey(
        AssessmentRun, on_delete=models.CASCADE, related_name="archetype_results"
    )
    stable_id = models.CharField(max_length=8)
    name = models.CharField(max_length=120)
    orientation_slugs = models.JSONField(default=list)
    fit_index = models.DecimalField(max_digits=6, decimal_places=4)
    fit_confidence = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    rank = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["rank", "stable_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment_run", "stable_id"],
                name="unique_archetype_per_assessment",
            )
        ]

    def __str__(self) -> str:
        return f"{self.assessment_run_id}: {self.name}"


class LeverBaseline(models.Model):
    class BaselineMassSource(models.TextChoices):
        CANONICAL_RESULT = "canonical_result", "Canonical assessment result"
        PUBLISHED_RECONSTRUCTION = (
            "published_reconstruction",
            "Reconstructed from published rounded values",
        )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lever_baselines"
    )
    assessment_run = models.ForeignKey(
        AssessmentRun, on_delete=models.CASCADE, related_name="lever_baselines"
    )
    lever = models.ForeignKey(Lever, on_delete=models.PROTECT, related_name="baselines")
    raw_self_report = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    calibrated_estimate = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    evidence_confidence = models.DecimalField(max_digits=6, decimal_places=4)
    baseline_alpha = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
    )
    baseline_beta = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
    )
    baseline_mass_source = models.CharField(
        max_length=32,
        choices=BaselineMassSource.choices,
        blank=True,
        default="",
    )
    need_score = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    need_rank = models.PositiveSmallIntegerField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["need_rank", "lever_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment_run", "lever"],
                name="unique_lever_baseline_per_assessment",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        baseline_alpha__isnull=True,
                        baseline_beta__isnull=True,
                        baseline_mass_source="",
                    )
                    | (
                        Q(baseline_alpha__isnull=False, baseline_beta__isnull=False)
                        & ~Q(baseline_mass_source="")
                    )
                ),
                name="lever_baseline_mass_state_complete",
            ),
            models.CheckConstraint(
                condition=Q(baseline_alpha__isnull=True) | Q(baseline_alpha__gte=0),
                name="lever_baseline_alpha_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(baseline_beta__isnull=True) | Q(baseline_beta__gte=0),
                name="lever_baseline_beta_nonnegative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.assessment_run_id}: {self.lever_id}"


class LeverState(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Evidence updates available"
        BASELINE_ONLY = "baseline_only", "Baseline only"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lever_states",
    )
    assessment_run = models.ForeignKey(
        AssessmentRun,
        on_delete=models.PROTECT,
        related_name="lever_states",
    )
    baseline = models.OneToOneField(
        LeverBaseline,
        on_delete=models.PROTECT,
        related_name="current_state",
    )
    lever = models.ForeignKey(Lever, on_delete=models.PROTECT, related_name="states")
    algorithm_version = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=Status.choices)
    current_alpha = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )
    current_beta = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )
    current_estimate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
    )
    current_confidence = models.DecimalField(max_digits=6, decimal_places=4)
    cumulative_evidence_mass = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=0,
    )
    included_evidence_events = models.PositiveIntegerField(default=0)
    current_need_score = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
    )
    current_need_rank = models.PositiveSmallIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["current_need_rank", "lever_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment_run", "lever"],
                name="unique_lever_state_per_assessment",
            ),
            models.CheckConstraint(
                condition=(
                    Q(current_alpha__isnull=True, current_beta__isnull=True)
                    | Q(current_alpha__isnull=False, current_beta__isnull=False)
                ),
                name="lever_state_mass_pair_complete",
            ),
            models.CheckConstraint(
                condition=Q(current_alpha__isnull=True) | Q(current_alpha__gte=0),
                name="lever_state_alpha_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(current_beta__isnull=True) | Q(current_beta__gte=0),
                name="lever_state_beta_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(cumulative_evidence_mass__gte=0),
                name="lever_state_evidence_mass_nonnegative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.assessment_run_id}: {self.lever_id} current state"


class PracticeProtocol(models.Model):
    class Availability(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    stable_id = models.CharField(max_length=120, primary_key=True)
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=180)
    parent_competency = models.ForeignKey(
        Competency,
        on_delete=models.PROTECT,
        related_name="practice_protocols",
        null=True,
        blank=True,
    )
    availability = models.CharField(
        max_length=10, choices=Availability.choices, default=Availability.INACTIVE
    )
    duration_days = models.PositiveSmallIntegerField()
    recommendation_reason = models.TextField()
    applicability_prompt = models.TextField()
    setup_prompt = models.TextField()
    privacy_and_boundaries = models.TextField()
    completion_criteria = models.JSONField(default=list)
    completion_rules = models.JSONField(default=dict)
    setup_copy = models.JSONField(default=dict)
    check_in_fields = models.JSONField(default=list)
    score_active = models.BooleanField(default=False)
    mastery_disclaimer = models.CharField(max_length=120, default=MASTERY_DISCLAIMER)
    target_levers = models.ManyToManyField(Lever, related_name="practice_protocols")
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "stable_id"]

    def __str__(self) -> str:
        return self.name


class PracticeAction(models.Model):
    stable_id = models.CharField(max_length=100, primary_key=True)
    protocol = models.ForeignKey(PracticeProtocol, on_delete=models.CASCADE, related_name="actions")
    sequence = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=180)
    instructions = models.TextField()
    due_within_days = models.PositiveSmallIntegerField(null=True, blank=True)
    evidence_rules = models.JSONField(default=dict)

    class Meta:
        ordering = ["protocol_id", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["protocol", "sequence"], name="unique_action_sequence_per_protocol"
            )
        ]

    def __str__(self) -> str:
        return f"{self.protocol_id} action {self.sequence}"


class PracticeSprint(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        STOPPED = "stopped", "Stopped"
        COMPLETED = "completed", "Completed"

    class ScoringContract(models.TextChoices):
        LEGACY = "GG-SCORE-STATE-1.0", "Historical event-level score state"
        COMPOSITE = (
            "GG-COMPOSITE-CLOSEOUT-SCORING-1.0",
            "Assessment composite and human closeout credit",
        )

    stable_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="practice_sprints"
    )
    protocol = models.ForeignKey(PracticeProtocol, on_delete=models.PROTECT, related_name="sprints")
    assessment_run = models.ForeignKey(
        AssessmentRun,
        on_delete=models.PROTECT,
        related_name="practice_sprints",
        null=True,
        blank=True,
    )
    scoring_contract_version = models.CharField(
        max_length=64,
        choices=ScoringContract.choices,
        default=ScoringContract.COMPOSITE,
    )
    person_or_context = models.CharField(max_length=200)
    start_date = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    setup_completed_at = models.DateTimeField(null=True, blank=True)
    boundaries_acknowledged_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status__in=["active", "paused"]),
                name="one_current_practice_per_user",
            ),
            models.CheckConstraint(
                condition=Q(
                    scoring_contract_version__in=[
                        "GG-SCORE-STATE-1.0",
                        "GG-COMPOSITE-CLOSEOUT-SCORING-1.0",
                    ]
                ),
                name="practice_sprint_scoring_contract_supported",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.protocol_id} for {self.user_id} ({self.status})"


class PracticeCheckInQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if kwargs.get("status") == "submitted" or self.filter(status="submitted").exists():
            raise ValidationError("Submitted check-ins are immutable.")
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        objects = list(objs)
        object_ids = [obj.pk for obj in objects if obj.pk]
        if (
            any(obj.status == "submitted" for obj in objects)
            or self.filter(
                pk__in=object_ids,
                status="submitted",
            ).exists()
        ):
            raise ValidationError("Submitted check-ins are immutable.")
        return super().bulk_update(objects, fields, batch_size=batch_size)


class PracticeCheckIn(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"

    class SupportLevel(models.TextChoices):
        INDEPENDENT = "independent", "Self-directed"
        PLANNING_AID = "planning_aid", "Used a reminder or planning aid"
        GUIDED = "guided", "Needed real-time prompting or guidance"

    class ContextComparison(models.TextChoices):
        FIRST_RECORD = "first_record", "First record for this practice"
        SAME_CONTEXT = "same_context", "Similar setting or situation"
        VARIED_CONTEXT = "varied_context", "Meaningfully different setting or situation"

    class EvidenceDirection(models.TextChoices):
        SUPPORTS = "supports", "Supported the expected pattern"
        MIXED = "mixed", "Mixed or unclear"
        CONTRADICTS = "contradicts", "Contradicted the expected pattern"
        INCONCLUSIVE = "inconclusive", "Not enough happened to tell"

    stable_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sprint = models.ForeignKey(PracticeSprint, on_delete=models.CASCADE, related_name="check_ins")
    action = models.ForeignKey(PracticeAction, on_delete=models.PROTECT, related_name="check_ins")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    action_attempted = models.BooleanField(default=False)
    action_completed = models.BooleanField(default=False)
    user_initiated = models.BooleanField(default=False)
    moved_beyond_transactional = models.BooleanField(default=False)
    follow_up_question_asked = models.BooleanField(default=False)
    meaningful_information_shared = models.BooleanField(default=False)
    future_interaction_scheduled = models.BooleanField(default=False)
    follow_up_within_seven_days = models.BooleanField(default=False)
    internal_resistance = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(4)]
    )
    expected_reciprocity = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(4)]
    )
    observed_reciprocity = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(4)]
    )
    typed_observations = models.JSONField(default=list, blank=True)
    support_level = models.CharField(
        max_length=20,
        choices=SupportLevel.choices,
        blank=True,
        default="",
    )
    context_comparison = models.CharField(
        max_length=20,
        choices=ContextComparison.choices,
        blank=True,
        default="",
    )
    evidence_direction = models.CharField(
        max_length=20,
        choices=EvidenceDirection.choices,
        blank=True,
        default="",
    )
    contradictory_evidence = models.TextField(blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    objects = PracticeCheckInQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(action_completed=False) | Q(action_attempted=True),
                name="completed_check_in_requires_attempt",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="draft", submitted_at__isnull=True)
                    | Q(status="submitted", submitted_at__isnull=False)
                ),
                name="check_in_submission_timestamp_matches_status",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(evidence_direction__in=["mixed", "contradicts"])
                    | ~Q(contradictory_evidence="")
                ),
                name="directed_contradiction_requires_detail",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.sprint_id}: {self.action_id} ({self.status})"

    def save(self, *args, **kwargs):
        if self.pk:
            stored_status = (
                type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            )
            if stored_status == self.Status.SUBMITTED:
                raise ValidationError("Submitted check-ins are immutable.")
        return super().save(*args, **kwargs)


class ImmutableEvidenceEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Evidence events are immutable after creation.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Evidence events are immutable after creation.")


class EvidenceEvent(models.Model):
    stable_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    check_in = models.OneToOneField(
        PracticeCheckIn,
        on_delete=models.CASCADE,
        related_name="evidence_event",
    )
    algorithm_version = models.CharField(max_length=40)
    protocol_stable_id = models.CharField(max_length=120)
    action_stable_id = models.CharField(max_length=100)
    input_snapshot = models.JSONField()
    performance = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    quality = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    independence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    context_breadth = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    repetition_index = models.PositiveSmallIntegerField()
    repetition_multiplier = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    contradiction_level = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    base_evidence_mass = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    explanation = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableEvidenceEventQuerySet.as_manager()

    class Meta:
        ordering = ["check_in__submitted_at", "stable_id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(repetition_index__gte=1),
                name="evidence_repetition_index_positive",
            ),
            models.CheckConstraint(
                condition=Q(performance__gte=0) & Q(performance__lte=1),
                name="evidence_performance_in_range",
            ),
            models.CheckConstraint(
                condition=Q(quality__gte=0) & Q(quality__lte=1),
                name="evidence_quality_in_range",
            ),
            models.CheckConstraint(
                condition=Q(independence__gte=0) & Q(independence__lte=1),
                name="evidence_independence_in_range",
            ),
            models.CheckConstraint(
                condition=Q(context_breadth__gte=0) & Q(context_breadth__lte=1),
                name="evidence_context_breadth_in_range",
            ),
            models.CheckConstraint(
                condition=Q(repetition_multiplier__gt=0) & Q(repetition_multiplier__lte=1),
                name="evidence_repetition_multiplier_in_range",
            ),
            models.CheckConstraint(
                condition=(
                    Q(contradiction_level__isnull=True)
                    | (Q(contradiction_level__gte=0) & Q(contradiction_level__lte=1))
                ),
                name="evidence_contradiction_level_in_range",
            ),
            models.CheckConstraint(
                condition=Q(base_evidence_mass__gte=0) & Q(base_evidence_mass__lte=1),
                name="evidence_base_mass_in_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.check_in_id}: {self.algorithm_version}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Evidence events are immutable after creation.")
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if not self.check_in_id:
            return
        if (
            self.check_in.status != PracticeCheckIn.Status.SUBMITTED
            or self.check_in.submitted_at is None
        ):
            raise ValidationError("Evidence events require a submitted check-in.")
        if self.protocol_stable_id != self.check_in.sprint.protocol_id:
            raise ValidationError("Evidence event protocol does not match its check-in.")
        if self.action_stable_id != self.check_in.action_id:
            raise ValidationError("Evidence event action does not match its check-in.")


class ImmutableScoreSnapshotQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Score snapshots are immutable after creation.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Score snapshots are immutable after creation.")

    def delete(self):
        raise ValidationError("Score snapshots are immutable after creation.")


class ScoreSnapshot(models.Model):
    class Operation(models.TextChoices):
        INITIALIZE = "initialize", "Initialize baseline state"
        PROCESS = "process", "Process evidence event"
        REVERSE = "reverse", "Reverse evidence event"
        REBUILD = "rebuild", "Repair current state from event history"

    stable_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment_run = models.ForeignKey(
        AssessmentRun,
        on_delete=models.PROTECT,
        related_name="score_snapshots",
    )
    evidence_event = models.ForeignKey(
        EvidenceEvent,
        on_delete=models.PROTECT,
        related_name="score_snapshots",
        null=True,
        blank=True,
    )
    operation = models.CharField(max_length=12, choices=Operation.choices)
    sequence = models.PositiveIntegerField()
    algorithm_version = models.CharField(max_length=40)
    state_schema_version = models.CharField(max_length=40)
    before_state = models.JSONField(default=list, blank=True)
    after_state = models.JSONField(default=list, blank=True)
    contribution_snapshot = models.JSONField(default=dict, blank=True)
    active_event_count = models.PositiveIntegerField(default=0)
    active_event_hash = models.CharField(max_length=64)
    before_state_hash = models.CharField(max_length=64)
    after_state_hash = models.CharField(max_length=64)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableScoreSnapshotQuerySet.as_manager()

    class Meta:
        ordering = ["assessment_run_id", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment_run", "sequence"],
                name="unique_score_snapshot_sequence",
            ),
            models.UniqueConstraint(
                fields=["assessment_run"],
                condition=Q(operation="initialize"),
                name="unique_score_state_initialization",
            ),
            models.UniqueConstraint(
                fields=["evidence_event"],
                condition=Q(operation="process"),
                name="unique_score_event_processing",
            ),
            models.UniqueConstraint(
                fields=["evidence_event"],
                condition=Q(operation="reverse"),
                name="unique_score_event_reversal",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        operation__in=["process", "reverse"],
                        evidence_event__isnull=False,
                    )
                    | Q(
                        operation__in=["initialize", "rebuild"],
                        evidence_event__isnull=True,
                    )
                ),
                name="score_snapshot_event_matches_operation",
            ),
            models.CheckConstraint(
                condition=~Q(operation="reverse") | ~Q(reason=""),
                name="score_reversal_requires_reason",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.assessment_run_id}: {self.sequence} {self.operation}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Score snapshots are immutable after creation.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Score snapshots are immutable after creation.")


class PracticeReview(models.Model):
    stable_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sprint = models.OneToOneField(PracticeSprint, on_delete=models.CASCADE, related_name="review")
    actions_attempted = models.PositiveSmallIntegerField(default=0)
    actions_completed = models.PositiveSmallIntegerField(default=0)
    substantive_interaction_occurred = models.BooleanField(default=False)
    reflection = models.TextField()
    contradictory_evidence = models.TextField(blank=True)
    static_score_impact_preview = models.JSONField(default=dict)
    mastery_disclaimer = models.CharField(max_length=120, default=MASTERY_DISCLAIMER)
    submitted_at = models.DateTimeField()

    def __str__(self) -> str:
        return f"Review for {self.sprint_id}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Submitted practice reviews are immutable.")
        return super().save(*args, **kwargs)


class ImmutableCompositeRecordQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Composite scoring history is immutable after creation.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Composite scoring history is immutable after creation.")

    def delete(self):
        raise ValidationError("Composite scoring history is immutable after creation.")


class CompositeAssessmentSnapshot(models.Model):
    stable_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment_run = models.OneToOneField(
        AssessmentRun,
        on_delete=models.PROTECT,
        related_name="composite_assessment_snapshot",
    )
    algorithm_version = models.CharField(max_length=64)
    state_schema_version = models.CharField(max_length=64)
    projection = models.JSONField(default=dict)
    projection_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableCompositeRecordQuerySet.as_manager()

    class Meta:
        ordering = ["assessment_run_id"]

    def __str__(self) -> str:
        return f"{self.assessment_run_id}: composite assessment"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Composite assessment snapshots are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Composite assessment snapshots are immutable.")


class CompletionCreditEvent(models.Model):
    stable_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment_run = models.ForeignKey(
        AssessmentRun,
        on_delete=models.PROTECT,
        related_name="completion_credit_events",
    )
    sprint = models.OneToOneField(
        PracticeSprint,
        on_delete=models.PROTECT,
        related_name="completion_credit_event",
    )
    review = models.OneToOneField(
        PracticeReview,
        on_delete=models.PROTECT,
        related_name="completion_credit_event",
    )
    protocol = models.ForeignKey(
        PracticeProtocol,
        on_delete=models.PROTECT,
        related_name="completion_credit_events",
    )
    competency = models.ForeignKey(
        Competency,
        on_delete=models.PROTECT,
        related_name="completion_credit_events",
    )
    algorithm_version = models.CharField(max_length=64)
    completed_action_ids = models.JSONField(default=list)
    total_actions = models.PositiveSmallIntegerField()
    minimum_completed = models.PositiveSmallIntegerField()
    completion_credit = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    source_snapshot = models.JSONField(default=dict)
    source_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableCompositeRecordQuerySet.as_manager()

    class Meta:
        ordering = ["assessment_run_id", "created_at", "stable_id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(minimum_completed__gt=0)
                & Q(total_actions__gte=models.F("minimum_completed")),
                name="completion_credit_threshold_valid",
            ),
            models.CheckConstraint(
                condition=Q(completion_credit__gte=0) & Q(completion_credit__lte=1),
                name="completion_credit_in_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.competency_id}: {self.completion_credit}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Completion credit events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Completion credit events are immutable.")


class CompositeScoreState(models.Model):
    assessment_run = models.OneToOneField(
        AssessmentRun,
        on_delete=models.CASCADE,
        related_name="composite_score_state",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="composite_score_states",
    )
    algorithm_version = models.CharField(max_length=64)
    state_schema_version = models.CharField(max_length=64)
    state = models.JSONField(default=dict)
    state_hash = models.CharField(max_length=64)
    active_event_count = models.PositiveIntegerField(default=0)
    active_event_hash = models.CharField(max_length=64)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["assessment_run_id"]

    def __str__(self) -> str:
        return f"{self.assessment_run_id}: composite state"


class CompositeScoreSnapshot(models.Model):
    class Operation(models.TextChoices):
        INITIALIZE = "initialize", "Initialize composite state"
        PROCESS = "process", "Process completion closeout"
        REVERSE = "reverse", "Reverse completion closeout"
        REBUILD = "rebuild", "Repair composite state"

    stable_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment_run = models.ForeignKey(
        AssessmentRun,
        on_delete=models.PROTECT,
        related_name="composite_score_snapshots",
    )
    completion_credit_event = models.ForeignKey(
        CompletionCreditEvent,
        on_delete=models.PROTECT,
        related_name="score_snapshots",
        null=True,
        blank=True,
    )
    operation = models.CharField(max_length=12, choices=Operation.choices)
    sequence = models.PositiveIntegerField()
    algorithm_version = models.CharField(max_length=64)
    state_schema_version = models.CharField(max_length=64)
    before_state = models.JSONField(default=dict, blank=True)
    after_state = models.JSONField(default=dict, blank=True)
    active_event_count = models.PositiveIntegerField(default=0)
    active_event_hash = models.CharField(max_length=64)
    before_state_hash = models.CharField(max_length=64)
    after_state_hash = models.CharField(max_length=64)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableCompositeRecordQuerySet.as_manager()

    class Meta:
        ordering = ["assessment_run_id", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment_run", "sequence"],
                name="unique_composite_snapshot_sequence",
            ),
            models.UniqueConstraint(
                fields=["assessment_run"],
                condition=Q(operation="initialize"),
                name="unique_composite_state_initialization",
            ),
            models.UniqueConstraint(
                fields=["completion_credit_event"],
                condition=Q(operation="process"),
                name="unique_completion_credit_processing",
            ),
            models.UniqueConstraint(
                fields=["completion_credit_event"],
                condition=Q(operation="reverse"),
                name="unique_completion_credit_reversal",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        operation__in=["process", "reverse"],
                        completion_credit_event__isnull=False,
                    )
                    | Q(
                        operation__in=["initialize", "rebuild"],
                        completion_credit_event__isnull=True,
                    )
                ),
                name="composite_snapshot_event_matches_operation",
            ),
            models.CheckConstraint(
                condition=~Q(operation="reverse") | ~Q(reason=""),
                name="composite_reversal_requires_reason",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.assessment_run_id}: {self.sequence} {self.operation}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Composite score snapshots are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Composite score snapshots are immutable.")


class ImmutablePilotFeedbackQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Submitted pilot feedback is immutable.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Submitted pilot feedback is immutable.")


class PilotFeedback(models.Model):
    class JourneyStage(models.TextChoices):
        LOGIN = "login", "Signing in"
        ASSESSMENT = "assessment", "Taking or importing the assessment"
        PROFILE = "profile", "Understanding the profile"
        RECOMMENDATION = "recommendation", "Choosing a recommended practice"
        SETUP = "setup", "Setting up a practice"
        ACTIVE_PRACTICE = "active_practice", "Using an active practice"
        CHECK_IN = "check_in", "Submitting a check-in"
        REVIEW = "review", "Completing the final review"
        ACCOUNT = "account", "Account settings"
        OTHER = "other", "Another part of the experience"

    class Applicability(models.TextChoices):
        YES = "yes", "It fit my current situation"
        PARTLY = "partly", "It partly fit"
        NO = "no", "It did not fit my current situation"
        UNSURE = "unsure", "I was unsure"

    class StartTimeBand(models.TextChoices):
        UNDER_TWO = "under_2_minutes", "Under 2 minutes"
        TWO_TO_FIVE = "2_to_5_minutes", "2-5 minutes"
        OVER_FIVE = "over_5_minutes", "More than 5 minutes"
        NOT_STARTED = "not_started", "I did not start"

    class CheckInTimeBand(models.TextChoices):
        UNDER_ONE = "under_1_minute", "Under 1 minute"
        ONE_TO_TWO = "1_to_2_minutes", "1-2 minutes"
        OVER_TWO = "over_2_minutes", "More than 2 minutes"
        NOT_COMPLETED = "not_completed", "I did not complete a check-in"

    class ConfusingStep(models.TextChoices):
        NONE = "none", "Nothing was confusing"
        LOGIN = "login", "Signing in"
        ASSESSMENT = "assessment", "Assessment questions or import"
        PROFILE = "profile", "Profile language"
        RECOMMENDATION = "recommendation", "Why a practice was recommended"
        SETUP = "setup", "Practice setup"
        ACTIONS = "actions", "Practice action instructions"
        CHECK_IN = "check_in", "Check-in questions"
        REVIEW = "review", "Final review or completion"
        ACCOUNT = "account", "Account settings"
        OTHER = "other", "Another step"

    class Friction(models.TextChoices):
        NONE = "none", "No"
        PRESENT = "present", "Yes"
        PREFER_NOT = "prefer_not_to_say", "Prefer not to say"

    stable_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pilot_feedback",
    )
    contract_version = models.CharField(
        max_length=40,
        default=PILOT_FEEDBACK_CONTRACT_VERSION,
        editable=False,
    )
    journey_stage = models.CharField(max_length=24, choices=JourneyStage.choices)
    protocol = models.ForeignKey(
        PracticeProtocol,
        on_delete=models.PROTECT,
        related_name="pilot_feedback",
        null=True,
        blank=True,
    )
    applicability = models.CharField(
        max_length=12,
        choices=Applicability.choices,
        blank=True,
        default="",
    )
    time_to_start = models.CharField(
        max_length=20,
        choices=StartTimeBand.choices,
        blank=True,
        default="",
    )
    time_to_check_in = models.CharField(
        max_length=20,
        choices=CheckInTimeBand.choices,
        blank=True,
        default="",
    )
    confusing_step = models.CharField(
        max_length=20,
        choices=ConfusingStep.choices,
        blank=True,
        default="",
    )
    accessibility_friction = models.CharField(
        max_length=20,
        choices=Friction.choices,
        blank=True,
        default="",
    )
    safety_friction = models.CharField(
        max_length=20,
        choices=Friction.choices,
        blank=True,
        default="",
    )
    comment = models.TextField(
        blank=True,
        validators=[MaxLengthValidator(1000)],
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutablePilotFeedbackQuerySet.as_manager()

    class Meta:
        ordering = ["submitted_at", "stable_id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(contract_version=PILOT_FEEDBACK_CONTRACT_VERSION),
                name="pilot_feedback_contract_version_v1",
            ),
            models.CheckConstraint(
                condition=~Q(
                    applicability="",
                    time_to_start="",
                    time_to_check_in="",
                    confusing_step="",
                    accessibility_friction="",
                    safety_friction="",
                    comment="",
                ),
                name="pilot_feedback_has_signal",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.journey_stage} feedback for user {self.user_id}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Submitted pilot feedback is immutable.")
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.contract_version != PILOT_FEEDBACK_CONTRACT_VERSION:
            raise ValidationError("Pilot feedback contract version is not supported.")
        if not any(
            (
                self.applicability,
                self.time_to_start,
                self.time_to_check_in,
                self.confusing_step,
                self.accessibility_friction,
                self.safety_friction,
                self.comment.strip(),
            )
        ):
            raise ValidationError("Provide at least one optional feedback response.")


class ImmutableContextQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Versioned context records are immutable.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Versioned context records are immutable.")

    def delete(self):
        raise ValidationError("Versioned context records are immutable.")


class AssessmentContext(models.Model):
    class ValueState(models.TextChoices):
        UNKNOWN = ContextValueState.UNKNOWN.value, "Unknown"
        NOT_APPLICABLE = ContextValueState.NOT_APPLICABLE.value, "Not applicable"
        DEFERRED = ContextValueState.DEFERRED.value, "Deferred"
        PROVIDED = ContextValueState.PROVIDED.value, "Provided"

    stable_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assessment_context_records",
    )
    assessment_run = models.ForeignKey(
        AssessmentRun,
        on_delete=models.PROTECT,
        related_name="context_records",
    )
    contract_version = models.CharField(
        max_length=40,
        default=CONTEXT_CONTRACT_VERSION,
        editable=False,
    )
    revision = models.PositiveIntegerField()
    season_state = models.CharField(max_length=20, choices=ValueState.choices)
    season_value = models.CharField(
        max_length=20,
        choices=[(item.value, item.value.replace("_", " ").title()) for item in SeasonCode],
        blank=True,
        default="",
    )
    capacity_state = models.CharField(max_length=20, choices=ValueState.choices)
    capacity_value = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(4)],
    )
    canonical_snapshot = models.JSONField()
    content_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableContextQuerySet.as_manager()

    class Meta:
        ordering = ["assessment_run_id", "revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment_run", "revision"],
                name="unique_assessment_context_revision",
            ),
            models.CheckConstraint(
                condition=Q(contract_version=CONTEXT_CONTRACT_VERSION),
                name="assessment_context_contract_v1",
            ),
            models.CheckConstraint(
                condition=Q(revision__gte=1),
                name="assessment_context_revision_positive",
            ),
            models.CheckConstraint(
                condition=Q(season_state__in=[item.value for item in ContextValueState]),
                name="assessment_context_season_state_valid",
            ),
            models.CheckConstraint(
                condition=Q(capacity_state__in=[item.value for item in ContextValueState]),
                name="assessment_context_capacity_state_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(season_state=ContextValueState.PROVIDED.value) & ~Q(season_value="")
                    | ~Q(season_state=ContextValueState.PROVIDED.value) & Q(season_value="")
                ),
                name="assessment_context_season_value_matches_state",
            ),
            models.CheckConstraint(
                condition=(
                    Q(capacity_state=ContextValueState.PROVIDED.value)
                    & Q(capacity_value__isnull=False)
                    | ~Q(capacity_state=ContextValueState.PROVIDED.value)
                    & Q(capacity_value__isnull=True)
                ),
                name="assessment_context_capacity_value_matches_state",
            ),
            models.CheckConstraint(
                condition=(
                    Q(capacity_value__isnull=True)
                    | Q(capacity_value__gte=0) & Q(capacity_value__lte=4)
                ),
                name="assessment_context_capacity_in_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.assessment_run_id}: context revision {self.revision}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Versioned context records are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Versioned context records are immutable.")

    def clean(self):
        super().clean()
        errors = {}
        if self.contract_version != CONTEXT_CONTRACT_VERSION:
            errors["contract_version"] = "Context contract version is not supported."
        if self.assessment_run_id and self.user_id != self.assessment_run.user_id:
            errors["user"] = "Context user must own the assessment epoch."
        try:
            expected = build_assessment_context_snapshot(
                assessment_epoch_id=self.assessment_run_id,
                contract_version=self.contract_version,
                factors={
                    "season": {"state": self.season_state, "value": self.season_value or None},
                    "capacity": {"state": self.capacity_state, "value": self.capacity_value},
                },
            )
        except (ValueError, TypeError) as exc:
            errors["canonical_snapshot"] = str(exc)
        else:
            if self.canonical_snapshot != expected.payload:
                errors["canonical_snapshot"] = "Canonical context snapshot does not match fields."
            if self.content_hash != expected.content_hash:
                errors["content_hash"] = "Context content hash does not verify."
        if errors:
            raise ValidationError(errors)


class PracticeContext(models.Model):
    class ValueState(models.TextChoices):
        UNKNOWN = ContextValueState.UNKNOWN.value, "Unknown"
        NOT_APPLICABLE = ContextValueState.NOT_APPLICABLE.value, "Not applicable"
        DEFERRED = ContextValueState.DEFERRED.value, "Deferred"
        PROVIDED = ContextValueState.PROVIDED.value, "Provided"

    class Disposition(models.TextChoices):
        CONSIDERING = PracticeDisposition.CONSIDERING.value, "Considering"
        DEFERRED = PracticeDisposition.DEFERRED.value, "Deferred / not now"

    class DeferReasonCategory(models.TextChoices):
        CAPACITY = DeferReason.CAPACITY.value, "Capacity"
        RESOURCES = DeferReason.RESOURCES.value, "Resources"
        TIMING = DeferReason.TIMING.value, "Timing"
        SAFETY_OR_ACCESS = DeferReason.SAFETY_OR_ACCESS.value, "Safety or access"
        ROLE_OR_FIT = DeferReason.ROLE_OR_FIT.value, "Role or fit"
        COMPETING_PRIORITY = DeferReason.COMPETING_PRIORITY.value, "Competing priority"
        NEEDS_SUPPORT = DeferReason.NEEDS_SUPPORT.value, "Needs support"
        USER_CHOICE = DeferReason.USER_CHOICE.value, "User choice"

    stable_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="practice_context_records",
    )
    assessment_run = models.ForeignKey(
        AssessmentRun,
        on_delete=models.PROTECT,
        related_name="practice_context_records",
    )
    protocol = models.ForeignKey(
        PracticeProtocol,
        on_delete=models.PROTECT,
        related_name="context_records",
    )
    contract_version = models.CharField(
        max_length=40,
        default=CONTEXT_CONTRACT_VERSION,
        editable=False,
    )
    revision = models.PositiveIntegerField()
    applicability_state = models.CharField(max_length=20, choices=ValueState.choices)
    applicability_value = models.PositiveSmallIntegerField(null=True, blank=True)
    importance_state = models.CharField(max_length=20, choices=ValueState.choices)
    importance_value = models.PositiveSmallIntegerField(null=True, blank=True)
    readiness_state = models.CharField(max_length=20, choices=ValueState.choices)
    readiness_value = models.PositiveSmallIntegerField(null=True, blank=True)
    urgency_state = models.CharField(max_length=20, choices=ValueState.choices)
    urgency_value = models.PositiveSmallIntegerField(null=True, blank=True)
    opportunity_resources_state = models.CharField(max_length=20, choices=ValueState.choices)
    opportunity_resources_value = models.PositiveSmallIntegerField(null=True, blank=True)
    burden_state = models.CharField(max_length=20, choices=ValueState.choices)
    burden_value = models.PositiveSmallIntegerField(null=True, blank=True)
    disposition = models.CharField(
        max_length=20,
        choices=Disposition.choices,
        default=Disposition.CONSIDERING,
    )
    defer_reason = models.CharField(
        max_length=24,
        choices=DeferReasonCategory.choices,
        blank=True,
        default="",
    )
    review_horizon_days = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(REVIEW_HORIZON_DAYS_MIN),
            MaxValueValidator(REVIEW_HORIZON_DAYS_MAX),
        ],
    )
    canonical_snapshot = models.JSONField()
    content_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableContextQuerySet.as_manager()

    class Meta:
        ordering = ["assessment_run_id", "protocol_id", "revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment_run", "protocol", "revision"],
                name="unique_practice_context_revision",
            ),
            models.CheckConstraint(
                condition=Q(contract_version=CONTEXT_CONTRACT_VERSION),
                name="practice_context_contract_v1",
            ),
            models.CheckConstraint(
                condition=Q(revision__gte=1),
                name="practice_context_revision_positive",
            ),
            models.CheckConstraint(
                condition=Q(disposition__in=[item.value for item in PracticeDisposition]),
                name="practice_context_disposition_valid",
            ),
            models.CheckConstraint(
                condition=Q(defer_reason="")
                | Q(defer_reason__in=[item.value for item in DeferReason]),
                name="practice_context_defer_reason_valid",
            ),
            models.CheckConstraint(
                condition=Q(review_horizon_days__isnull=True)
                | Q(
                    review_horizon_days__gte=REVIEW_HORIZON_DAYS_MIN,
                    review_horizon_days__lte=REVIEW_HORIZON_DAYS_MAX,
                ),
                name="practice_context_review_horizon_in_range",
            ),
        ]
        for field_name in (
            "applicability",
            "importance",
            "readiness",
            "urgency",
            "opportunity_resources",
            "burden",
        ):
            constraints.extend(
                [
                    models.CheckConstraint(
                        condition=Q(
                            **{
                                f"{field_name}_state__in": [
                                    item.value for item in ContextValueState
                                ]
                            }
                        ),
                        name=f"practice_context_{field_name}_state_valid",
                    ),
                    models.CheckConstraint(
                        condition=(
                            Q(**{f"{field_name}_state": ContextValueState.PROVIDED.value})
                            & Q(**{f"{field_name}_value__isnull": False})
                            | ~Q(**{f"{field_name}_state": ContextValueState.PROVIDED.value})
                            & Q(**{f"{field_name}_value__isnull": True})
                        ),
                        name=f"practice_context_{field_name}_value_state",
                    ),
                    models.CheckConstraint(
                        condition=Q(**{f"{field_name}_value__isnull": True})
                        | Q(
                            **{
                                f"{field_name}_value__gte": 0,
                                f"{field_name}_value__lte": 4,
                            }
                        ),
                        name=f"practice_context_{field_name}_value_range",
                    ),
                ]
            )
        del field_name
        constraints.append(
            models.CheckConstraint(
                condition=(
                    Q(disposition=PracticeDisposition.DEFERRED.value)
                    & ~Q(defer_reason="")
                    & (
                        Q(applicability_state=ContextValueState.DEFERRED.value)
                        | Q(importance_state=ContextValueState.DEFERRED.value)
                        | Q(readiness_state=ContextValueState.DEFERRED.value)
                        | Q(urgency_state=ContextValueState.DEFERRED.value)
                        | Q(opportunity_resources_state=ContextValueState.DEFERRED.value)
                        | Q(burden_state=ContextValueState.DEFERRED.value)
                    )
                    | Q(disposition=PracticeDisposition.CONSIDERING.value)
                    & Q(defer_reason="")
                    & Q(review_horizon_days__isnull=True)
                    & ~Q(applicability_state=ContextValueState.DEFERRED.value)
                    & ~Q(importance_state=ContextValueState.DEFERRED.value)
                    & ~Q(readiness_state=ContextValueState.DEFERRED.value)
                    & ~Q(urgency_state=ContextValueState.DEFERRED.value)
                    & ~Q(opportunity_resources_state=ContextValueState.DEFERRED.value)
                    & ~Q(burden_state=ContextValueState.DEFERRED.value)
                ),
                name="practice_context_defer_metadata_consistent",
            )
        )

    def __str__(self) -> str:
        return f"{self.assessment_run_id}: {self.protocol_id} context revision {self.revision}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Versioned context records are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Versioned context records are immutable.")

    def clean(self):
        super().clean()
        errors = {}
        if self.contract_version != CONTEXT_CONTRACT_VERSION:
            errors["contract_version"] = "Context contract version is not supported."
        if self.assessment_run_id and self.user_id != self.assessment_run.user_id:
            errors["user"] = "Context user must own the assessment epoch."
        if self.protocol_id and self.assessment_run_id:
            parent = self.protocol.parent_competency
            if (
                parent is None
                or parent.curriculum_version_id != self.assessment_run.curriculum_version_id
            ):
                errors["protocol"] = (
                    "Context protocol must have a parent in the assessment epoch curriculum."
                )
        factors = {
            factor_id: {
                "state": getattr(self, f"{factor_id}_state"),
                "value": getattr(self, f"{factor_id}_value"),
            }
            for factor_id in (
                "applicability",
                "importance",
                "readiness",
                "urgency",
                "opportunity_resources",
                "burden",
            )
        }
        try:
            expected = build_practice_context_snapshot(
                assessment_epoch_id=self.assessment_run_id,
                protocol_stable_id=self.protocol_id,
                contract_version=self.contract_version,
                factors=factors,
                disposition=self.disposition,
                defer_reason=self.defer_reason or None,
                review_horizon_days=self.review_horizon_days,
            )
        except (ValueError, TypeError) as exc:
            errors["canonical_snapshot"] = str(exc)
        else:
            if self.canonical_snapshot != expected.payload:
                errors["canonical_snapshot"] = "Canonical context snapshot does not match fields."
            if self.content_hash != expected.content_hash:
                errors["content_hash"] = "Context content hash does not verify."
        if errors:
            raise ValidationError(errors)


class ImmutablePersonalOSQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Personal OS revisions are immutable.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Personal OS revisions are immutable.")

    def bulk_create(
        self,
        objs,
        batch_size=None,
        ignore_conflicts=False,
        update_conflicts=False,
        update_fields=None,
        unique_fields=None,
    ):
        raise ValidationError("Personal OS revisions require validated individual creation.")

    def delete(self):
        raise ValidationError("Personal OS revisions are immutable.")


class PersonalOSRevision(models.Model):
    class ValueState(models.TextChoices):
        UNKNOWN = PersonalOSValueState.UNKNOWN.value, "Unknown"
        NOT_APPLICABLE = PersonalOSValueState.NOT_APPLICABLE.value, "Not applicable"
        DEFERRED = PersonalOSValueState.DEFERRED.value, "Deferred"
        PROVIDED = PersonalOSValueState.PROVIDED.value, "Provided"

    stable_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="personal_os_revisions",
    )
    assessment_run = models.ForeignKey(
        AssessmentRun,
        on_delete=models.CASCADE,
        related_name="personal_os_revisions",
    )
    contract_version = models.CharField(
        max_length=40,
        default=PERSONAL_OS_CONTRACT_VERSION,
        editable=False,
    )
    revision = models.PositiveIntegerField()

    for _section_id in SCALAR_SECTION_IDS:
        locals()[f"{_section_id}_state"] = models.CharField(
            max_length=20,
            choices=ValueState.choices,
        )
        locals()[f"{_section_id}_value"] = models.CharField(
            max_length=500,
            blank=True,
            default="",
        )
    del _section_id

    for _section_id in LIST_SECTION_IDS:
        locals()[f"{_section_id}_state"] = models.CharField(
            max_length=20,
            choices=ValueState.choices,
        )
        locals()[f"{_section_id}_value"] = models.JSONField(
            null=True,
            blank=True,
            default=None,
        )
    del _section_id

    canonical_snapshot = models.JSONField()
    content_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutablePersonalOSQuerySet.as_manager()

    class Meta:
        db_table = "personal_os_revision"
        base_manager_name = "objects"
        ordering = ["assessment_run_id", "revision"]
        indexes = [
            models.Index(
                fields=["assessment_run", "-revision"],
                name="personal_os_latest_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment_run", "revision"],
                name="unique_personal_os_revision",
            ),
            models.CheckConstraint(
                condition=Q(contract_version=PERSONAL_OS_CONTRACT_VERSION),
                name="personal_os_contract_v1",
            ),
            models.CheckConstraint(
                condition=Q(revision__gte=1),
                name="personal_os_revision_positive",
            ),
        ]
        constraints.extend(
            [
                models.CheckConstraint(
                    condition=Q(
                        **{
                            f"{_field_name}_state__in": [
                                item.value for item in PersonalOSValueState
                            ]
                        }
                    ),
                    name=f"personal_os_{_field_name}_state_valid",
                )
                for _field_name in (*SCALAR_SECTION_IDS, *LIST_SECTION_IDS)
            ]
        )
        constraints.extend(
            [
                models.CheckConstraint(
                    condition=(
                        Q(**{f"{_field_name}_state": PersonalOSValueState.PROVIDED.value})
                        & ~Q(**{f"{_field_name}_value": ""})
                        | ~Q(**{f"{_field_name}_state": PersonalOSValueState.PROVIDED.value})
                        & Q(**{f"{_field_name}_value": ""})
                    ),
                    name=f"personal_os_{_field_name}_value_state",
                )
                for _field_name in SCALAR_SECTION_IDS
            ]
        )
        constraints.extend(
            [
                models.CheckConstraint(
                    condition=(
                        Q(**{f"{_field_name}_state": PersonalOSValueState.PROVIDED.value})
                        & Q(**{f"{_field_name}_value__isnull": False})
                        | ~Q(**{f"{_field_name}_state": PersonalOSValueState.PROVIDED.value})
                        & Q(**{f"{_field_name}_value__isnull": True})
                    ),
                    name=f"personal_os_{_field_name}_value_state",
                )
                for _field_name in LIST_SECTION_IDS
            ]
        )

    def __str__(self) -> str:
        return f"Personal OS revision {self.revision}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Personal OS revisions are immutable.")
        if kwargs.get("force_update"):
            raise ValidationError("Personal OS revisions are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Personal OS revisions are immutable.")

    def clean(self):
        super().clean()
        errors = {}
        if self.contract_version != PERSONAL_OS_CONTRACT_VERSION:
            errors["contract_version"] = "Personal OS contract version is not supported."
        if self.user_id and self.assessment_run_id and self.user_id != self.assessment_run.user_id:
            errors["user"] = "Personal OS user must own the assessment epoch."
        if self.assessment_run_id and self._state.adding:
            latest_revision = (
                type(self)
                .objects.filter(assessment_run_id=self.assessment_run_id)
                .order_by("-revision")
                .values_list("revision", flat=True)
                .first()
            )
            expected_revision = 1 if latest_revision is None else latest_revision + 1
            if self.revision != expected_revision:
                errors["revision"] = (
                    f"Personal OS revision must be the next contiguous value: {expected_revision}."
                )
        try:
            expected = build_personal_os_snapshot(
                assessment_epoch_id=self.assessment_run_id,
                contract_version=self.contract_version,
                identity_sections=self._snapshot_values(IDENTITY_SECTION_IDS),
                audit_responses=self._snapshot_values(AUDIT_PROMPT_IDS),
            )
        except (ValueError, TypeError):
            errors["canonical_snapshot"] = "Personal OS fields fail the supported contract."
        else:
            if self.canonical_snapshot != expected.payload:
                errors["canonical_snapshot"] = "Personal OS snapshot does not match fields."
            if self.content_hash != expected.content_hash:
                errors["content_hash"] = "Personal OS content hash does not verify."
        if errors:
            raise ValidationError(errors)

    def _snapshot_values(self, section_ids):
        return {
            section_id: {
                "state": getattr(self, f"{section_id}_state"),
                "value": (
                    getattr(self, f"{section_id}_value")
                    if getattr(self, f"{section_id}_state") == PersonalOSValueState.PROVIDED.value
                    else None
                ),
            }
            for section_id in section_ids
        }


class ImmutableWeeklyExecutionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Weekly execution records are immutable.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Weekly execution records are immutable.")

    def bulk_create(
        self,
        objs,
        batch_size=None,
        ignore_conflicts=False,
        update_conflicts=False,
        update_fields=None,
        unique_fields=None,
    ):
        raise ValidationError("Weekly execution records require validated individual creation.")

    def delete(self):
        raise ValidationError("Weekly execution records are immutable.")


class WeeklyExecutionPlan(models.Model):
    stable_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weekly_execution_plans",
    )
    assessment_run = models.ForeignKey(
        AssessmentRun,
        on_delete=models.CASCADE,
        related_name="weekly_execution_plans",
    )
    sprint = models.ForeignKey(
        PracticeSprint,
        on_delete=models.CASCADE,
        related_name="weekly_execution_plans",
    )
    action = models.ForeignKey(
        PracticeAction,
        on_delete=models.PROTECT,
        related_name="weekly_execution_plans",
    )
    contract_version = models.CharField(
        max_length=40,
        default=WEEKLY_EXECUTION_CONTRACT_VERSION,
        editable=False,
    )
    week_start = models.DateField()
    revision = models.PositiveIntegerField()
    intended_on = models.DateField()
    canonical_snapshot = models.JSONField()
    content_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableWeeklyExecutionQuerySet.as_manager()

    class Meta:
        ordering = ["assessment_run_id", "week_start", "revision"]
        indexes = [
            models.Index(
                fields=["user", "-week_start", "-revision"],
                name="weekly_plan_latest_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment_run", "week_start", "revision"],
                name="unique_weekly_plan_revision",
            ),
            models.CheckConstraint(
                condition=Q(contract_version=WEEKLY_EXECUTION_CONTRACT_VERSION),
                name="weekly_plan_contract_v1",
            ),
            models.CheckConstraint(
                condition=Q(revision__gte=1),
                name="weekly_plan_revision_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.week_start}: plan revision {self.revision}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Weekly execution plans are immutable.")
        if kwargs.get("force_update"):
            raise ValidationError("Weekly execution plans are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Weekly execution plans are immutable.")

    def clean(self):
        super().clean()
        errors = {}
        if self.contract_version != WEEKLY_EXECUTION_CONTRACT_VERSION:
            errors["contract_version"] = "Weekly execution contract version is not supported."
        if self.user_id and self.assessment_run_id and self.user_id != self.assessment_run.user_id:
            errors["user"] = "Weekly plan user must own the assessment epoch."
        if self.user_id and self.sprint_id and self.user_id != self.sprint.user_id:
            errors["sprint"] = "Weekly plan user must own the practice sprint."
        if (
            self.assessment_run_id
            and self.sprint_id
            and self.sprint.assessment_run_id != self.assessment_run_id
        ):
            errors["sprint"] = "Weekly plan sprint must belong to the assessment epoch."
        if self.action_id and self.sprint_id and self.action.protocol_id != self.sprint.protocol_id:
            errors["action"] = "Weekly plan action must belong to the sprint protocol."
        if self.assessment_run_id and self.week_start and self._state.adding:
            latest_revision = (
                type(self)
                .objects.filter(
                    assessment_run_id=self.assessment_run_id,
                    week_start=self.week_start,
                )
                .order_by("-revision")
                .values_list("revision", flat=True)
                .first()
            )
            expected_revision = 1 if latest_revision is None else latest_revision + 1
            if self.revision != expected_revision:
                errors["revision"] = (
                    f"Weekly plan revision must be the next contiguous value: {expected_revision}."
                )
        try:
            expected = build_weekly_plan_snapshot(
                assessment_epoch_id=self.assessment_run_id,
                sprint_id=str(self.sprint_id),
                protocol_stable_id=self.sprint.protocol_id,
                action_stable_id=self.action_id,
                week_start=self.week_start,
                intended_on=self.intended_on,
                contract_version=self.contract_version,
            )
        except (ValueError, TypeError):
            errors["canonical_snapshot"] = "Weekly plan fields fail the supported contract."
        else:
            if self.canonical_snapshot != expected.payload:
                errors["canonical_snapshot"] = "Weekly plan snapshot does not match fields."
            if self.content_hash != expected.content_hash:
                errors["content_hash"] = "Weekly plan content hash does not verify."
        if errors:
            raise ValidationError(errors)


class WeeklyExecutionReview(models.Model):
    class NextStep(models.TextChoices):
        CONTINUE_CURRENT = WeeklyNextStep.CONTINUE_CURRENT.value, "Continue the current action"
        PLAN_NEXT_ACTION = WeeklyNextStep.PLAN_NEXT_ACTION.value, "Plan the next action"
        PAUSE_RECONSIDER = WeeklyNextStep.PAUSE_RECONSIDER.value, "Pause and reconsider"
        CHOOSE_DIFFERENT_PRACTICE = (
            WeeklyNextStep.CHOOSE_DIFFERENT_PRACTICE.value,
            "Choose a different practice",
        )

    class Adjustment(models.TextChoices):
        NONE = WeeklyAdjustment.NONE.value, "No adjustment"
        TIMING = WeeklyAdjustment.TIMING.value, "Change timing"
        SCOPE = WeeklyAdjustment.SCOPE.value, "Reduce or clarify scope"
        SUPPORT = WeeklyAdjustment.SUPPORT.value, "Change support"
        CONTEXT = WeeklyAdjustment.CONTEXT.value, "Change context"
        RECOVERY = WeeklyAdjustment.RECOVERY.value, "Protect recovery or capacity"

    class Outcome(models.TextChoices):
        NO_SUBMITTED_EVIDENCE = (
            WeeklyProofOutcome.NO_SUBMITTED_EVIDENCE.value,
            "No submitted evidence",
        )
        ATTEMPTED = WeeklyProofOutcome.ATTEMPTED.value, "Attempted"
        COMPLETED = WeeklyProofOutcome.COMPLETED.value, "Completed"

    stable_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weekly_execution_reviews",
    )
    plan = models.OneToOneField(
        WeeklyExecutionPlan,
        on_delete=models.CASCADE,
        related_name="review",
    )
    contract_version = models.CharField(
        max_length=40,
        default=WEEKLY_EXECUTION_CONTRACT_VERSION,
        editable=False,
    )
    outcome = models.CharField(max_length=32, choices=Outcome.choices)
    next_step = models.CharField(max_length=32, choices=NextStep.choices)
    adjustment = models.CharField(max_length=20, choices=Adjustment.choices)
    canonical_snapshot = models.JSONField()
    content_hash = models.CharField(max_length=64)
    submitted_at = models.DateTimeField()

    objects = ImmutableWeeklyExecutionQuerySet.as_manager()

    class Meta:
        ordering = ["plan__week_start", "plan__revision"]
        constraints = [
            models.CheckConstraint(
                condition=Q(contract_version=WEEKLY_EXECUTION_CONTRACT_VERSION),
                name="weekly_review_contract_v1",
            ),
            models.CheckConstraint(
                condition=Q(outcome__in=[item.value for item in WeeklyProofOutcome]),
                name="weekly_review_outcome_valid",
            ),
            models.CheckConstraint(
                condition=Q(next_step__in=[item.value for item in WeeklyNextStep]),
                name="weekly_review_next_step_valid",
            ),
            models.CheckConstraint(
                condition=Q(adjustment__in=[item.value for item in WeeklyAdjustment]),
                name="weekly_review_adjustment_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"Review for weekly plan {self.plan_id}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Weekly execution reviews are immutable.")
        if kwargs.get("force_update"):
            raise ValidationError("Weekly execution reviews are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Weekly execution reviews are immutable.")

    def clean(self):
        super().clean()
        errors = {}
        if self.contract_version != WEEKLY_EXECUTION_CONTRACT_VERSION:
            errors["contract_version"] = "Weekly execution contract version is not supported."
        if self.user_id and self.plan_id and self.user_id != self.plan.user_id:
            errors["user"] = "Weekly review user must own the weekly plan."
        proof_events = (
            self.canonical_snapshot.get("proof_events", [])
            if isinstance(self.canonical_snapshot, dict)
            else []
        )
        try:
            expected = build_weekly_review_snapshot(
                plan_stable_id=str(self.plan_id),
                plan_content_hash=self.plan.content_hash,
                proof_events=proof_events,
                reviewed_at=self.submitted_at,
                next_step=self.next_step,
                adjustment=self.adjustment,
                contract_version=self.contract_version,
            )
        except (ValueError, TypeError):
            errors["canonical_snapshot"] = "Weekly review fields fail the supported contract."
        else:
            if self.outcome != expected.payload["outcome"]:
                errors["outcome"] = "Weekly review outcome does not match submitted proof."
            if self.canonical_snapshot != expected.payload:
                errors["canonical_snapshot"] = "Weekly review snapshot does not match fields."
            if self.content_hash != expected.content_hash:
                errors["content_hash"] = "Weekly review content hash does not verify."
        if errors:
            raise ValidationError(errors)
