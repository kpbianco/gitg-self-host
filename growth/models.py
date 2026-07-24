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
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lever_baselines"
    )
    assessment_run = models.ForeignKey(
        AssessmentRun, on_delete=models.CASCADE, related_name="lever_baselines"
    )
    lever = models.ForeignKey(Lever, on_delete=models.PROTECT, related_name="baselines")
    raw_self_report = models.DecimalField(max_digits=6, decimal_places=4)
    calibrated_estimate = models.DecimalField(max_digits=6, decimal_places=4)
    evidence_confidence = models.DecimalField(max_digits=6, decimal_places=4)
    need_score = models.DecimalField(max_digits=6, decimal_places=4)
    need_rank = models.PositiveSmallIntegerField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["need_rank", "lever_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment_run", "lever"],
                name="unique_lever_baseline_per_assessment",
            )
        ]

    def __str__(self) -> str:
        return f"{self.assessment_run_id}: {self.lever_id}"


class PracticeProtocol(models.Model):
    class Availability(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    stable_id = models.CharField(max_length=80, primary_key=True)
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=180)
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
    paused_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.protocol_id} for {self.user_id} ({self.status})"


class PracticeCheckIn(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"

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
    contradictory_evidence = models.TextField(blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.sprint_id}: {self.action_id} ({self.status})"


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
