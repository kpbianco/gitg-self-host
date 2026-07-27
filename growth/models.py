import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

MASTERY_DISCLAIMER = "Completing this practice does not establish mastery."


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

    stable_id = models.CharField(max_length=80, primary_key=True)
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
            )
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
    protocol_stable_id = models.CharField(max_length=80)
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
