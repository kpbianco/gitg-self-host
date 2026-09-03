from datetime import timedelta
from typing import ClassVar

from django import forms
from django.utils import timezone

from growth.domain.context import (
    PRACTICE_FACTOR_IDS,
    DeferReason,
    SeasonCode,
)
from growth.domain.evidence import (
    ALLOWED_OBSERVATION_FIELDS,
    observation_fields_for_rules,
)
from growth.domain.personal_os import (
    AUDIT_PROMPT_DEFINITIONS,
    AUDIT_PROMPT_IDS,
    IDENTITY_SECTION_DEFINITIONS,
    IDENTITY_SECTION_IDS,
    LIST_ITEM_MAX_COUNT,
    LIST_ITEM_MAX_LENGTH,
    LIST_SECTION_IDS,
    SCALAR_VALUE_MAX_LENGTH,
)
from growth.domain.typed_evidence import (
    TYPED_EVIDENCE_RULES_VERSION,
    load_typed_evidence_spec,
    materialize_typed_evidence_rules,
)
from growth.domain.weekly_execution import (
    WeeklyAdjustment,
    WeeklyNextStep,
    week_end,
)
from growth.models import (
    AssessmentCalibrationConsent,
    AssessmentRun,
    PilotFeedback,
    PracticeAction,
    PracticeCheckIn,
    PracticeProtocol,
)
from growth.services.pilot_feedback import (
    FEEDBACK_FIELD_STAGES,
    feedback_scope_errors,
)

DELETE_ACCOUNT_CONFIRMATION = "DELETE MY ACCOUNT"
APPLY_RETENTION_CONFIRMATION = "APPLY RETENTION"


class AssessmentRunChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return (
            f"Assessment {obj.assessment_version} · {obj.created_at:%Y-%m-%d} · "
            f"{obj.get_source_display()}"
        )


class AssessmentCalibrationConsentForm(forms.Form):
    assessment_run = AssessmentRunChoiceField(
        label="Completed assessment",
        queryset=AssessmentRun.objects.none(),
        empty_label=None,
    )
    acknowledge_sensitive_data = forms.BooleanField(
        label=(
            "I understand the calibration contribution contains item-level answers, "
            "N/A choices, and timing and is sensitive pseudonymous data."
        )
    )
    authorize_manual_export = forms.BooleanField(
        label=(
            "I consent to this completed assessment being included in a manual local "
            "calibration export until I withdraw it."
        )
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assessment_run"].queryset = AssessmentRun.objects.filter(
            user=user,
            source__in=(AssessmentRun.Source.APPLICATION, AssessmentRun.Source.SHARE_CODE),
        ).order_by("-created_at", "stable_id")


class AssessmentCalibrationWithdrawalForm(forms.Form):
    assessment_run = AssessmentRunChoiceField(
        label="Included assessment",
        queryset=AssessmentRun.objects.none(),
        empty_label=None,
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        latest = {}
        for row in AssessmentCalibrationConsent.objects.filter(user=user).order_by(
            "assessment_run_id", "revision"
        ):
            latest[row.assessment_run_id] = row
        active_ids = [
            assessment_run_id
            for assessment_run_id, row in latest.items()
            if row.state == AssessmentCalibrationConsent.State.CONSENTED
        ]
        self.fields["assessment_run"].queryset = AssessmentRun.objects.filter(
            user=user,
            stable_id__in=active_ids,
        ).order_by("-created_at", "stable_id")


class RetentionConfirmationForm(forms.Form):
    preview_token = forms.CharField(widget=forms.HiddenInput)
    confirmation = forms.CharField(
        label=f'Type "{APPLY_RETENTION_CONFIRMATION}" to apply this preview',
        max_length=len(APPLY_RETENTION_CONFIRMATION),
    )

    def clean_confirmation(self):
        value = self.cleaned_data["confirmation"].strip()
        if value != APPLY_RETENTION_CONFIRMATION:
            raise forms.ValidationError("The retention confirmation text does not match.")
        return value


class AccountDeletionForm(forms.Form):
    preview_token = forms.CharField(widget=forms.HiddenInput)
    current_password = forms.CharField(
        label="Current password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    confirmation = forms.CharField(
        label=f'Type "{DELETE_ACCOUNT_CONFIRMATION}" to permanently delete this account',
        max_length=len(DELETE_ACCOUNT_CONFIRMATION),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_current_password(self):
        password = self.cleaned_data["current_password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("The current password is incorrect.")
        return password

    def clean_confirmation(self):
        value = self.cleaned_data["confirmation"].strip()
        if value != DELETE_ACCOUNT_CONFIRMATION:
            raise forms.ValidationError("The account-deletion confirmation text does not match.")
        return value


EXPLICIT_STATE_CHOICES = (
    ("unknown", "Unknown / not collected"),
    ("not_applicable", "Not applicable"),
    ("deferred", "Deferred for now"),
    ("provided", "Provide a value"),
)


class PersonalOSForm(forms.Form):
    assessment_epoch = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        definitions = {
            **IDENTITY_SECTION_DEFINITIONS,
            **AUDIT_PROMPT_DEFINITIONS,
        }
        for section_id in (*IDENTITY_SECTION_IDS, *AUDIT_PROMPT_IDS):
            definition = definitions[section_id]
            self.fields[f"{section_id}_state"] = forms.ChoiceField(
                label=f"Response state for: {definition.prompt}",
                choices=EXPLICIT_STATE_CHOICES,
                initial="unknown",
            )
            if section_id in LIST_SECTION_IDS:
                help_text = (
                    f"{definition.help_text} Put one item on each line; use one to "
                    f"{LIST_ITEM_MAX_COUNT} items, up to {LIST_ITEM_MAX_LENGTH} characters each."
                )
            else:
                help_text = (
                    f"{definition.help_text} Use at most {SCALAR_VALUE_MAX_LENGTH} characters."
                )
            self.fields[f"{section_id}_value"] = forms.CharField(
                label=definition.prompt,
                help_text=help_text,
                required=False,
                strip=False,
                max_length=(
                    LIST_ITEM_MAX_COUNT * (LIST_ITEM_MAX_LENGTH + 1)
                    if section_id in LIST_SECTION_IDS
                    else SCALAR_VALUE_MAX_LENGTH
                ),
                widget=forms.Textarea(attrs={"rows": 3, "data-personal-os-value": section_id}),
            )

    def clean(self):
        cleaned = super().clean()
        for section_id in (*IDENTITY_SECTION_IDS, *AUDIT_PROMPT_IDS):
            state = cleaned.get(f"{section_id}_state")
            raw_value = cleaned.get(f"{section_id}_value", "")
            if state == "provided":
                if section_id in LIST_SECTION_IDS:
                    items = raw_value.splitlines()
                    if not 1 <= len(items) <= LIST_ITEM_MAX_COUNT:
                        self.add_error(
                            f"{section_id}_value",
                            f"Provide one to {LIST_ITEM_MAX_COUNT} nonblank items.",
                        )
                    elif any(not item.strip() for item in items):
                        self.add_error(
                            f"{section_id}_value",
                            "List items must not be blank.",
                        )
                    elif any(len(item) > LIST_ITEM_MAX_LENGTH for item in items):
                        self.add_error(
                            f"{section_id}_value",
                            f"Each item must be at most {LIST_ITEM_MAX_LENGTH} characters.",
                        )
                    elif len(items) != len(set(items)):
                        self.add_error(
                            f"{section_id}_value",
                            "Items must be unique while preserving your chosen order.",
                        )
                    cleaned[f"{section_id}_value"] = items
                elif not raw_value.strip():
                    self.add_error(
                        f"{section_id}_value", "Provide a response or choose another state."
                    )
            elif raw_value:
                self.add_error(
                    f"{section_id}_value",
                    "Clear the authored value when this response is not provided.",
                )
        return cleaned

    def contract_values(self, section_ids):
        return {
            section_id: {
                "state": self.cleaned_data[f"{section_id}_state"],
                "value": (
                    self.cleaned_data[f"{section_id}_value"]
                    if self.cleaned_data[f"{section_id}_state"] == "provided"
                    else None
                ),
            }
            for section_id in section_ids
        }


class AssessmentPriorityContextForm(forms.Form):
    assessment_epoch = forms.CharField(widget=forms.HiddenInput)
    season_state = forms.ChoiceField(
        label="Current season response state",
        choices=(("", "Choose a state"), *EXPLICIT_STATE_CHOICES),
    )
    season_value = forms.ChoiceField(
        label="Current season",
        choices=(
            ("", "Choose a season"),
            *[(item.value, item.value.title()) for item in SeasonCode],
        ),
        required=False,
        help_text="Descriptive context only; it does not change priority or measure performance.",
    )
    capacity_state = forms.ChoiceField(
        label="Capacity response state",
        choices=(("", "Choose a state"), *EXPLICIT_STATE_CHOICES),
    )
    capacity_value = forms.TypedChoiceField(
        label="Room for one additional bounded practice",
        choices=(("", "Choose 0 to 4"), *((str(value), str(value)) for value in range(5))),
        coerce=int,
        empty_value=None,
        required=False,
        help_text="0 to 4 is self-reported room right now, not effort, character, or potential.",
    )

    def clean(self):
        cleaned = super().clean()
        for factor_id in ("season", "capacity"):
            state = cleaned.get(f"{factor_id}_state")
            value = cleaned.get(f"{factor_id}_value")
            empty = value in (None, "")
            if state == "provided" and empty:
                self.add_error(f"{factor_id}_value", "Choose a value or choose another state.")
            elif state and state != "provided" and not empty:
                self.add_error(
                    f"{factor_id}_value",
                    "Clear the value when this response is not provided.",
                )
        return cleaned

    def contract_factors(self):
        return {
            factor_id: {
                "state": self.cleaned_data[f"{factor_id}_state"],
                "value": (
                    self.cleaned_data[f"{factor_id}_value"]
                    if self.cleaned_data[f"{factor_id}_state"] == "provided"
                    else None
                ),
            }
            for factor_id in ("season", "capacity")
        }


PRACTICE_FACTOR_LABELS = {
    "applicability": "Fit with your present role and situation",
    "importance": "Current importance among competing goods",
    "readiness": "Readiness to attempt this bounded practice",
    "urgency": "User-reported time sensitivity",
    "opportunity_resources": "Available opportunity, support, access, and resources",
    "burden": "Expected time, access, effort, emotional, relational, or material load",
}


class PracticePriorityContextForm(forms.Form):
    assessment_epoch = forms.CharField(widget=forms.HiddenInput)
    mode = forms.ChoiceField(
        label="How do you want to review this practice?",
        choices=(
            ("", "Choose one"),
            ("provide", "Provide all six context factors"),
            ("not_applicable", "Mark this practice not applicable"),
            ("defer", "Defer this practice for now"),
        ),
        widget=forms.RadioSelect,
    )
    deferred_factor = forms.ChoiceField(
        label="Which factor is deferred?",
        choices=(
            ("", "Choose one"),
            *((item, PRACTICE_FACTOR_LABELS[item]) for item in PRACTICE_FACTOR_IDS),
        ),
        required=False,
    )
    defer_reason = forms.ChoiceField(
        label="Reason for deferring",
        choices=(
            ("", "Choose one"),
            *((item.value, item.value.replace("_", " ").title()) for item in DeferReason),
        ),
        required=False,
    )
    review_horizon_days = forms.IntegerField(
        label="Optional review horizon in days",
        min_value=1,
        max_value=366,
        required=False,
        help_text="A review prompt only; it creates no timer, expiration, or negative observation.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = (("", "Choose 0 to 4"), *((str(value), str(value)) for value in range(5)))
        for factor_id in PRACTICE_FACTOR_IDS:
            self.fields[factor_id] = forms.TypedChoiceField(
                label=PRACTICE_FACTOR_LABELS[factor_id],
                choices=choices,
                coerce=int,
                empty_value=None,
                required=False,
            )

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")
        supplied = [
            factor_id for factor_id in PRACTICE_FACTOR_IDS if cleaned.get(factor_id) is not None
        ]
        if mode == "provide":
            for factor_id in PRACTICE_FACTOR_IDS:
                if cleaned.get(factor_id) is None:
                    self.add_error(factor_id, "Choose a value from 0 to 4.")
            if (
                cleaned.get("deferred_factor")
                or cleaned.get("defer_reason")
                or cleaned.get("review_horizon_days") is not None
            ):
                self.add_error("mode", "Clear defer details when providing all six factors.")
        elif mode == "not_applicable":
            if supplied:
                self.add_error("mode", "Clear numeric factors when marking this not applicable.")
            if (
                cleaned.get("deferred_factor")
                or cleaned.get("defer_reason")
                or cleaned.get("review_horizon_days") is not None
            ):
                self.add_error("mode", "Clear defer details when marking this not applicable.")
        elif mode == "defer":
            if supplied:
                self.add_error("mode", "Clear numeric factors when deferring this practice.")
            if not cleaned.get("deferred_factor"):
                self.add_error("deferred_factor", "Name the factor you are deferring.")
            if not cleaned.get("defer_reason"):
                self.add_error("defer_reason", "Choose a categorical reason for deferring.")
        return cleaned

    def context_input(self, protocol):
        mode = self.cleaned_data["mode"]
        if mode == "provide":
            factors = {
                factor_id: {"state": "provided", "value": self.cleaned_data[factor_id]}
                for factor_id in PRACTICE_FACTOR_IDS
            }
            return factors, "considering", None, None
        factors = {
            factor_id: {"state": "unknown", "value": None} for factor_id in PRACTICE_FACTOR_IDS
        }
        if mode == "not_applicable":
            factors["applicability"] = {"state": "not_applicable", "value": None}
            return factors, "considering", None, None
        factors[self.cleaned_data["deferred_factor"]] = {"state": "deferred", "value": None}
        return (
            factors,
            "deferred",
            self.cleaned_data["defer_reason"],
            self.cleaned_data["review_horizon_days"],
        )


class PracticeActionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"Action {obj.sequence}: {obj.title}"


class WeeklyExecutionPlanForm(forms.Form):
    assessment_epoch = forms.CharField(widget=forms.HiddenInput)
    sprint_id = forms.UUIDField(widget=forms.HiddenInput)
    week_start = forms.DateField(widget=forms.HiddenInput)
    action = PracticeActionChoiceField(
        label="One action to make concrete this week",
        queryset=PracticeAction.objects.none(),
        help_text="Choose one action from the current practice. Planning it is not evidence.",
    )
    intended_on = forms.DateField(
        label="Intended day",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Choose a day inside this Monday-to-Sunday window.",
    )

    def __init__(self, *args, sprint=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sprint = sprint
        if sprint is not None:
            self.fields["action"].queryset = sprint.protocol.actions.order_by("sequence")

    def clean(self):
        cleaned = super().clean()
        if self.sprint is None:
            raise forms.ValidationError("An active practice is required for weekly planning.")
        if cleaned.get("sprint_id") != self.sprint.pk:
            raise forms.ValidationError("The active practice changed. Reload before saving.")
        action = cleaned.get("action")
        if action is not None and action.protocol_id != self.sprint.protocol_id:
            self.add_error("action", "Choose an action from the current practice.")
        start = cleaned.get("week_start")
        intended = cleaned.get("intended_on")
        if start is not None and intended is not None and not start <= intended <= week_end(start):
            self.add_error("intended_on", "Choose a day inside this weekly window.")
        return cleaned


class WeeklyExecutionReviewForm(forms.Form):
    plan_id = forms.UUIDField(widget=forms.HiddenInput)
    next_step = forms.ChoiceField(
        label="What should happen next?",
        choices=(
            (WeeklyNextStep.CONTINUE_CURRENT.value, "Continue the current action"),
            (WeeklyNextStep.PLAN_NEXT_ACTION.value, "Plan the next action"),
            (WeeklyNextStep.PAUSE_RECONSIDER.value, "Pause and reconsider"),
            (
                WeeklyNextStep.CHOOSE_DIFFERENT_PRACTICE.value,
                "Choose a different practice",
            ),
        ),
        widget=forms.RadioSelect,
    )
    adjustment = forms.ChoiceField(
        label="What adjustment, if any, would make the next attempt more workable?",
        choices=(
            (WeeklyAdjustment.NONE.value, "No adjustment"),
            (WeeklyAdjustment.TIMING.value, "Change timing"),
            (WeeklyAdjustment.SCOPE.value, "Reduce or clarify scope"),
            (WeeklyAdjustment.SUPPORT.value, "Change support"),
            (WeeklyAdjustment.CONTEXT.value, "Change context"),
            (WeeklyAdjustment.RECOVERY.value, "Protect recovery or capacity"),
        ),
    )


class PracticeApplicabilityForm(forms.Form):
    applicable = forms.ChoiceField(
        label="Is this practice currently applicable?",
        choices=(("yes", "Yes, this relationship is available"), ("no", "Not right now")),
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, protocol=None, **kwargs):
        super().__init__(*args, **kwargs)
        if protocol and protocol.setup_copy.get("applicability_yes_label"):
            self.fields["applicable"].choices = (
                ("yes", protocol.setup_copy["applicability_yes_label"]),
                ("no", "Not right now"),
            )
        elif protocol and protocol.stable_id != "PRACTICE-FRIENDSHIP-01":
            self.fields["applicable"].choices = (
                ("yes", "Yes, this activity or context is available"),
                ("no", "Not right now"),
            )


class PracticeContextForm(forms.Form):
    person_or_context = forms.CharField(
        label="Private label for the person or context",
        max_length=200,
        help_text=(
            "Use a first name, initials, or another private label. Do not record "
            "sensitive details here."
        ),
    )

    def __init__(self, *args, protocol=None, **kwargs):
        super().__init__(*args, **kwargs)
        if protocol:
            self.fields["person_or_context"].help_text = protocol.setup_copy.get(
                "context_help", self.fields["person_or_context"].help_text
            )


class PracticeBoundaryForm(forms.Form):
    boundaries_acknowledged = forms.BooleanField(
        label=(
            "I will choose welcome contact, respect the other person's privacy and "
            "autonomy, and treat reciprocity as freely given—not owed."
        ),
    )

    def __init__(self, *args, protocol=None, **kwargs):
        super().__init__(*args, **kwargs)
        if protocol:
            self.fields["boundaries_acknowledged"].label = protocol.setup_copy.get(
                "boundary_acknowledgement",
                self.fields["boundaries_acknowledged"].label,
            )


class PracticeStartDateForm(forms.Form):
    start_date = forms.DateField(
        label="Start date",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Choose today or a date within the next two weeks.",
    )

    def clean_start_date(self):
        start_date = self.cleaned_data["start_date"]
        today = timezone.localdate()
        if start_date < today:
            raise forms.ValidationError("Choose today or a future date.")
        if start_date > today + timedelta(days=14):
            raise forms.ValidationError("Choose a start date within the next two weeks.")
        return start_date


SCALE_CHOICES = (
    ("", "Not recorded"),
    ("0", "0 — None"),
    ("1", "1 — Low"),
    ("2", "2 — Moderate"),
    ("3", "3 — High"),
    ("4", "4 — Very high"),
)

TYPED_OBSERVATION_STATE_CHOICES = (
    ("unknown", "Unknown / not collected"),
    ("observed", "Observed — provide a structured value"),
    ("not_observed", "Not observed"),
    ("withheld", "Withheld for privacy or safety"),
    ("not_applicable", "Not applicable"),
    ("deferred", "Deferred for now"),
)
TYPED_PROVENANCE_LABELS = {
    "firsthand_self_report": "Firsthand self-report",
    "reviewed_artifact": "Reviewed artifact criteria (no contents stored)",
    "objective_indicator": "Bounded objective indicator",
    "consented_observer": "Consented observer",
    "qualified_attestation": "Qualified attestation",
}


def _typed_field_name(measurement_id: str, part: str) -> str:
    return f"typed_{measurement_id}_{part}"


class PracticeCheckInForm(forms.ModelForm):
    action = PracticeActionChoiceField(
        label="Which action is this about?",
        queryset=PracticeAction.objects.none(),
    )
    internal_resistance = forms.TypedChoiceField(
        label="Internal resistance",
        choices=SCALE_CHOICES,
        coerce=int,
        empty_value=None,
        required=False,
    )
    expected_reciprocity = forms.TypedChoiceField(
        label="Expected reciprocity",
        choices=SCALE_CHOICES,
        coerce=int,
        empty_value=None,
        required=False,
    )
    observed_reciprocity = forms.TypedChoiceField(
        label="Observed reciprocity",
        choices=SCALE_CHOICES,
        coerce=int,
        empty_value=None,
        required=False,
    )
    support_level = forms.ChoiceField(
        label="How much support did you use?",
        choices=(("", "Choose one"), *PracticeCheckIn.SupportLevel.choices),
        required=False,
        help_text="A reminder or planning aid is different from real-time guidance.",
    )
    context_comparison = forms.ChoiceField(
        label="How does this setting compare with earlier check-ins?",
        choices=(),
        required=False,
        help_text="This describes context variation within the same relationship.",
    )
    evidence_direction = forms.ChoiceField(
        label="What direction did the observation point?",
        choices=(("", "Choose one"), *PracticeCheckIn.EvidenceDirection.choices),
        required=False,
        help_text="Mixed or contradictory evidence is useful and will not be hidden.",
    )

    class Meta:
        model = PracticeCheckIn
        fields = (
            "action",
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
            "support_level",
            "context_comparison",
            "evidence_direction",
            "contradictory_evidence",
            "note",
        )
        labels: ClassVar[dict[str, str]] = {
            "action_attempted": "Action attempted",
            "action_completed": "Action completed",
            "user_initiated": "I initiated",
            "moved_beyond_transactional": "The interaction moved beyond transactional content",
            "follow_up_question_asked": "I asked a follow-up question",
            "meaningful_information_shared": (
                "Personally meaningful information was voluntarily shared"
            ),
            "future_interaction_scheduled": "A specific future interaction was scheduled",
            "follow_up_within_seven_days": "Follow-up was completed within seven days",
            "contradictory_evidence": "Contradictory evidence",
            "note": "Optional note",
        }
        help_texts: ClassVar[dict[str, str]] = {
            "contradictory_evidence": (
                "Record signs that the practice was unwelcome, ineffective, or did not "
                "mean what you expected."
            ),
            "note": "Keep private details minimal.",
        }
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "contradictory_evidence": forms.Textarea(attrs={"rows": 3}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, sprint, require_evidence_metadata=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.sprint = sprint
        self.require_evidence_metadata = require_evidence_metadata
        self.fields["action"].queryset = sprint.protocol.actions.all()
        optional_observations = {
            "user_initiated",
            "moved_beyond_transactional",
            "follow_up_question_asked",
            "meaningful_information_shared",
            "future_interaction_scheduled",
            "follow_up_within_seven_days",
            "internal_resistance",
            "expected_reciprocity",
            "observed_reciprocity",
        }
        configured = set(sprint.protocol.check_in_fields)
        for field_name in optional_observations - configured:
            self.fields.pop(field_name, None)
        for field_name, label in sprint.protocol.setup_copy.get("check_in_labels", {}).items():
            if field_name in self.fields:
                self.fields[field_name].label = label
        self.fields["action"].widget.attrs["data-check-in-action-control"] = "true"
        for field_name in ALLOWED_OBSERVATION_FIELDS & self.fields.keys():
            self.fields[field_name].widget.attrs["data-check-in-observation"] = field_name
        self.typed_measurement_rules: dict[str, dict] = {}
        self.typed_action_measurements: dict[str, tuple[str, ...]] = {}
        typed_actions = [
            action
            for action in self.fields["action"].queryset
            if action.evidence_rules.get("schema_version") == TYPED_EVIDENCE_RULES_VERSION
        ]
        if typed_actions:
            spec = load_typed_evidence_spec()
            for action in typed_actions:
                materialized = materialize_typed_evidence_rules(action.evidence_rules, spec)
                measurement_ids = []
                for rule in materialized["measurements"]:
                    measurement_id = rule["measurement_id"]
                    self.typed_measurement_rules[measurement_id] = rule
                    measurement_ids.append(measurement_id)
                    self._add_typed_measurement_fields(rule)
                self.typed_action_measurements[str(action.pk)] = tuple(measurement_ids)
            if not self.is_bound and self.instance.pk:
                self._set_typed_observation_initials(self.instance.typed_observations)
        self.action_observation_map = {}
        for action in self.fields["action"].queryset:
            if action.evidence_rules.get("schema_version") == TYPED_EVIDENCE_RULES_VERSION:
                field_names = [
                    field_name
                    for measurement_id in self.typed_action_measurements[str(action.pk)]
                    for field_name in self._typed_fields_for_rule(
                        self.typed_measurement_rules[measurement_id]
                    )
                ]
            else:
                field_names = sorted(
                    observation_fields_for_rules(action.evidence_rules) & self.fields.keys()
                )
            self.action_observation_map[str(action.pk)] = field_names
        self.fields[
            "context_comparison"
        ].help_text = "This describes context variation within the same practice."
        has_prior = sprint.check_ins.filter(status=PracticeCheckIn.Status.SUBMITTED).exists()
        if has_prior:
            context_choices = (
                ("", "Choose one"),
                (
                    PracticeCheckIn.ContextComparison.SAME_CONTEXT,
                    PracticeCheckIn.ContextComparison.SAME_CONTEXT.label,
                ),
                (
                    PracticeCheckIn.ContextComparison.VARIED_CONTEXT,
                    PracticeCheckIn.ContextComparison.VARIED_CONTEXT.label,
                ),
            )
        else:
            context_choices = (
                (
                    PracticeCheckIn.ContextComparison.FIRST_RECORD,
                    PracticeCheckIn.ContextComparison.FIRST_RECORD.label,
                ),
            )
            if not self.is_bound and not self.instance.context_comparison:
                self.initial["context_comparison"] = PracticeCheckIn.ContextComparison.FIRST_RECORD
        self.fields["context_comparison"].choices = context_choices

    def _set_typed_observation_initials(self, observations: list[dict]) -> None:
        """Restore every structured value when an existing draft is reopened."""

        for observation in observations:
            measurement_id = observation.get("measurement_id")
            rule = self.typed_measurement_rules.get(measurement_id)
            if rule is None:
                continue
            self.initial[_typed_field_name(measurement_id, "state")] = observation.get(
                "state", "unknown"
            )
            self.initial[_typed_field_name(measurement_id, "provenance")] = observation.get(
                "provenance_kind", rule["allowed_provenance"][0]
            )
            value = observation.get("value")
            if value is None:
                continue
            kind = rule["kind"]
            if kind == "bounded_frequency":
                self.initial[_typed_field_name(measurement_id, "numerator")] = value.get(
                    "numerator"
                )
                self.initial[_typed_field_name(measurement_id, "denominator")] = value.get(
                    "denominator"
                )
            elif kind in {"duration", "objective"}:
                self.initial[_typed_field_name(measurement_id, "value")] = value.get("amount")
            elif kind in {"artifact", "conceptual", "scenario"}:
                self.initial[_typed_field_name(measurement_id, "value")] = value.get(
                    "criteria_met", []
                )
            elif kind == "attestation":
                self.initial[_typed_field_name(measurement_id, "value")] = value.get(
                    "attestation_id"
                )
                self.initial[_typed_field_name(measurement_id, "consent")] = value.get(
                    "consent_confirmed", False
                )
            else:
                self.initial[_typed_field_name(measurement_id, "value")] = value

    def _typed_fields_for_rule(self, rule: dict) -> tuple[str, ...]:
        measurement_id = rule["measurement_id"]
        names = [
            _typed_field_name(measurement_id, "state"),
            _typed_field_name(measurement_id, "provenance"),
        ]
        kind = rule["kind"]
        if kind == "bounded_frequency":
            names.extend(
                [
                    _typed_field_name(measurement_id, "numerator"),
                    _typed_field_name(measurement_id, "denominator"),
                ]
            )
        elif kind == "attestation":
            names.extend(
                [
                    _typed_field_name(measurement_id, "value"),
                    _typed_field_name(measurement_id, "consent"),
                ]
            )
        else:
            names.append(_typed_field_name(measurement_id, "value"))
        return tuple(names)

    def _add_typed_measurement_fields(self, rule: dict) -> None:
        measurement_id = rule["measurement_id"]
        label = self.sprint.protocol.setup_copy.get("check_in_labels", {}).get(
            measurement_id,
            measurement_id.replace("_", " ").capitalize(),
        )
        state_name = _typed_field_name(measurement_id, "state")
        provenance_name = _typed_field_name(measurement_id, "provenance")
        self.fields[state_name] = forms.ChoiceField(
            label=f"{label} — observation state",
            choices=TYPED_OBSERVATION_STATE_CHOICES,
            initial="unknown",
            required=False,
        )
        allowed_provenance = tuple(rule["allowed_provenance"])
        self.fields[provenance_name] = forms.ChoiceField(
            label=f"{label} — provenance",
            choices=tuple(
                (value, TYPED_PROVENANCE_LABELS.get(value, value.replace("_", " ").title()))
                for value in allowed_provenance
            ),
            initial=allowed_provenance[0],
            required=False,
            help_text="Record the evidence source category; private narrative is never scored.",
        )
        kind = rule["kind"]
        value_name = _typed_field_name(measurement_id, "value")
        if kind == "boolean":
            self.fields[value_name] = forms.TypedChoiceField(
                label=label,
                choices=(("", "Choose one"), ("true", "Yes"), ("false", "No")),
                coerce=lambda value: value == "true",
                empty_value=None,
                required=False,
            )
        elif kind == "count":
            self.fields[value_name] = forms.IntegerField(label=label, min_value=0, required=False)
        elif kind == "bounded_frequency":
            self.fields[_typed_field_name(measurement_id, "numerator")] = forms.IntegerField(
                label=f"{label} — times observed", min_value=0, required=False
            )
            self.fields[_typed_field_name(measurement_id, "denominator")] = forms.IntegerField(
                label=f"{label} — opportunities", min_value=1, required=False
            )
        elif kind == "ordinal":
            self.fields[value_name] = forms.ChoiceField(
                label=label,
                choices=(
                    ("", "Choose one"),
                    *((item["level_id"], item["label"]) for item in rule["levels"]),
                ),
                required=False,
            )
        elif kind in {"duration", "objective"}:
            self.fields[value_name] = forms.DecimalField(
                label=f"{label} ({rule['unit']})", min_value=0, required=False
            )
        elif kind in {"artifact", "conceptual", "scenario"}:
            self.fields[value_name] = forms.MultipleChoiceField(
                label=label,
                choices=tuple(
                    (criterion, criterion.replace("_", " ").capitalize())
                    for criterion in rule["criteria"]
                ),
                widget=forms.CheckboxSelectMultiple,
                required=False,
                help_text="Store only which criteria were met; do not paste artifact contents.",
            )
        elif kind == "attestation":
            self.fields[value_name] = forms.ChoiceField(
                label=label,
                choices=(
                    ("", "Choose one"),
                    *(
                        (value, value.replace("_", " ").title())
                        for value in rule["allowed_attestation_ids"]
                    ),
                ),
                required=False,
            )
            self.fields[_typed_field_name(measurement_id, "consent")] = forms.BooleanField(
                label="Required consent was confirmed", required=False
            )
        else:
            raise ValueError(f"Unsupported typed measurement kind: {kind}")
        for field_name in self._typed_fields_for_rule(rule):
            self.fields[field_name].widget.attrs["data-check-in-observation"] = field_name

    def _typed_value(self, cleaned_data: dict, rule: dict):
        measurement_id = rule["measurement_id"]
        kind = rule["kind"]
        value_name = _typed_field_name(measurement_id, "value")
        if kind == "bounded_frequency":
            numerator_name = _typed_field_name(measurement_id, "numerator")
            denominator_name = _typed_field_name(measurement_id, "denominator")
            numerator = cleaned_data.get(numerator_name)
            denominator = cleaned_data.get(denominator_name)
            if numerator is None or denominator is None:
                self.add_error(numerator_name, "Observed frequency requires both values.")
                return None
            if numerator > denominator:
                self.add_error(numerator_name, "Times observed cannot exceed opportunities.")
                return None
            return {"numerator": numerator, "denominator": denominator}
        value = cleaned_data.get(value_name)
        if kind in {"artifact", "conceptual", "scenario"}:
            return {"criteria_met": list(value or [])}
        if kind in {"duration", "objective"}:
            if value is None:
                self.add_error(value_name, "An observed measurement requires a value.")
                return None
            return {"amount": format(value, "f"), "unit": rule["unit"]}
        if kind == "attestation":
            if not value:
                self.add_error(value_name, "An observed attestation requires an identifier.")
                return None
            return {
                "attestation_id": value,
                "consent_confirmed": bool(
                    cleaned_data.get(_typed_field_name(measurement_id, "consent"))
                ),
            }
        if value is None or value == "":
            self.add_error(value_name, "An observed measurement requires a value.")
            return None
        return value

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("action_completed") and not cleaned_data.get("action_attempted"):
            self.add_error("action_attempted", "A completed action must also be attempted.")
        if self.require_evidence_metadata and not cleaned_data.get("action_attempted"):
            self.add_error(
                "action_attempted",
                (
                    "Submit evidence only after a real attempt. Save a draft if the "
                    "action has not occurred."
                ),
            )
        action = cleaned_data.get("action")
        if action is not None:
            if action.evidence_rules.get("schema_version") == TYPED_EVIDENCE_RULES_VERSION:
                observations = []
                for measurement_id in self.typed_action_measurements[str(action.pk)]:
                    rule = self.typed_measurement_rules[measurement_id]
                    state = cleaned_data.get(_typed_field_name(measurement_id, "state"), "unknown")
                    value = self._typed_value(cleaned_data, rule) if state == "observed" else None
                    observations.append(
                        {
                            "measurement_id": measurement_id,
                            "kind": rule["kind"],
                            "state": state,
                            "provenance_kind": cleaned_data.get(
                                _typed_field_name(measurement_id, "provenance")
                            )
                            or rule["allowed_provenance"][0],
                            "value": value,
                        }
                    )
                cleaned_data["typed_observations"] = observations
            else:
                cleaned_data["typed_observations"] = []
                relevant_fields = observation_fields_for_rules(action.evidence_rules)
                for field_name in ALLOWED_OBSERVATION_FIELDS:
                    if cleaned_data.get(field_name) and field_name not in relevant_fields:
                        self.add_error(
                            field_name,
                            (
                                "This observation belongs to another action. Choose the "
                                "matching action or clear this response."
                            ),
                        )
        if self.require_evidence_metadata:
            for field in ("support_level", "context_comparison", "evidence_direction"):
                if not cleaned_data.get(field):
                    self.add_error(field, "Choose one before submitting evidence.")
        if (
            cleaned_data.get("evidence_direction")
            in (
                PracticeCheckIn.EvidenceDirection.MIXED,
                PracticeCheckIn.EvidenceDirection.CONTRADICTS,
            )
            and not cleaned_data.get("contradictory_evidence", "").strip()
        ):
            self.add_error(
                "contradictory_evidence",
                "Briefly describe what was mixed or contradictory.",
            )
        return cleaned_data


class PracticeReviewForm(forms.Form):
    reflection = forms.CharField(
        label="What did this practice show you?",
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text=(
            "Describe what happened and what you would carry forward. Completion is "
            "not a mastery judgment."
        ),
    )
    contradictory_evidence = forms.CharField(
        label="What complicated or contradicted the expected pattern?",
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        help_text="Optional, but useful when the evidence was mixed or the practice did not fit.",
    )


class PilotFeedbackForm(forms.ModelForm):
    journey_stage = forms.ChoiceField(
        label="Which part are you commenting on?",
        choices=(("", "Choose one"), *PilotFeedback.JourneyStage.choices),
    )
    protocol = forms.ModelChoiceField(
        label="Practice, if relevant",
        queryset=PracticeProtocol.objects.none(),
        required=False,
        empty_label="Not about a specific practice",
    )
    applicability = forms.ChoiceField(
        label="Did the recommendation fit your current situation?",
        choices=(("", "Not answered"), *PilotFeedback.Applicability.choices),
        required=False,
    )
    time_to_start = forms.ChoiceField(
        label="Roughly how long did setup take before you could begin?",
        choices=(("", "Not answered"), *PilotFeedback.StartTimeBand.choices),
        required=False,
        help_text="Choose an estimate. The application does not time you.",
    )
    time_to_check_in = forms.ChoiceField(
        label="Roughly how long did a check-in take?",
        choices=(("", "Not answered"), *PilotFeedback.CheckInTimeBand.choices),
        required=False,
        help_text="Choose an estimate. The application does not time you.",
    )
    confusing_step = forms.ChoiceField(
        label="Which step was most confusing?",
        choices=(("", "Not answered"), *PilotFeedback.ConfusingStep.choices),
        required=False,
    )
    accessibility_friction = forms.ChoiceField(
        label="Did an accessibility need make the application harder to use?",
        choices=(("", "Not answered"), *PilotFeedback.Friction.choices),
        required=False,
    )
    safety_friction = forms.ChoiceField(
        label="Did any instruction or interaction feel unsafe or poorly bounded?",
        choices=(("", "Not answered"), *PilotFeedback.Friction.choices),
        required=False,
    )

    class Meta:
        model = PilotFeedback
        fields = (
            "journey_stage",
            "protocol",
            "applicability",
            "time_to_start",
            "time_to_check_in",
            "confusing_step",
            "accessibility_friction",
            "safety_friction",
            "comment",
        )
        labels: ClassVar[dict[str, str]] = {
            "comment": "Optional detail",
        }
        help_texts: ClassVar[dict[str, str]] = {
            "comment": (
                "Describe the product friction, not private life details. This local "
                "form is not monitored for urgent support."
            ),
        }
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "comment": forms.Textarea(attrs={"rows": 4, "maxlength": 1000}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["protocol"].queryset = PracticeProtocol.objects.filter(
            availability=PracticeProtocol.Availability.ACTIVE
        ).order_by("display_order", "stable_id")
        self.fields[
            "journey_stage"
        ].help_text = "Choose one part. The form will show only questions relevant to that part."
        self.fields["journey_stage"].widget.attrs["data-feedback-stage-control"] = "true"
        for field_name, allowed_stages in FEEDBACK_FIELD_STAGES.items():
            self.fields[field_name].widget.attrs["data-feedback-stages"] = " ".join(
                sorted(allowed_stages)
            )

    def clean(self):
        cleaned_data = super().clean()
        signal_fields = (
            "applicability",
            "time_to_start",
            "time_to_check_in",
            "confusing_step",
            "accessibility_friction",
            "safety_friction",
            "comment",
        )
        if not any(str(cleaned_data.get(field, "") or "").strip() for field in signal_fields):
            raise forms.ValidationError(
                "Answer at least one optional feedback question before submitting."
            )
        for field_name, message in feedback_scope_errors(cleaned_data).items():
            self.add_error(field_name, message)
        return cleaned_data
