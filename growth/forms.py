from datetime import timedelta
from typing import ClassVar

from django import forms
from django.utils import timezone

from growth.domain.evidence import (
    ALLOWED_OBSERVATION_FIELDS,
    observation_fields_for_rules,
)
from growth.models import PilotFeedback, PracticeAction, PracticeCheckIn, PracticeProtocol
from growth.services.pilot_feedback import (
    FEEDBACK_FIELD_STAGES,
    feedback_scope_errors,
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


class PracticeActionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"Action {obj.sequence}: {obj.title}"


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
        self.action_observation_map = {
            str(action.pk): sorted(
                observation_fields_for_rules(action.evidence_rules) & self.fields.keys()
            )
            for action in self.fields["action"].queryset
        }
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
