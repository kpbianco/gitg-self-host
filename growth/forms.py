from datetime import timedelta
from typing import ClassVar

from django import forms
from django.utils import timezone

from growth.models import PracticeAction, PracticeCheckIn


class PracticeApplicabilityForm(forms.Form):
    applicable = forms.ChoiceField(
        label="Is this practice currently applicable?",
        choices=(("yes", "Yes, this relationship is available"), ("no", "Not right now")),
        widget=forms.RadioSelect,
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


class PracticeBoundaryForm(forms.Form):
    boundaries_acknowledged = forms.BooleanField(
        label=(
            "I will choose welcome contact, respect the other person's privacy and "
            "autonomy, and treat reciprocity as freely given—not owed."
        ),
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

    def __init__(self, *args, sprint, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["action"].queryset = sprint.protocol.actions.all()

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("action_completed") and not cleaned_data.get("action_attempted"):
            self.add_error("action_attempted", "A completed action must also be attempted.")
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
