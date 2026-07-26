from __future__ import annotations

from django import forms
from django.db.models import QuerySet
from django.utils.text import slugify

from apps.communities.models import Community, MembershipStatus

from .models import Exercise, ExerciseMedia, WorkoutPlan, WorkoutPlanAssignment, WorkoutPlanItem


class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        fields = [
            "name",
            "category",
            "movement_type",
            "primary_body_area",
            "difficulty_level",
            "equipment_requirement",
            "duration_fit",
            "description",
            "instructions",
            "contraindications",
            "safety_notes",
            "setup_steps",
            "execution_steps",
            "common_mistakes",
            "coaching_cues",
            "prescription_strength",
            "prescription_hypertrophy",
            "prescription_endurance",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_class = (
            "mt-1 w-full rounded-lg border border-white/20 bg-black/30 px-3 py-2 "
            "text-sm text-zinc-100"
        )
        textarea_rows = {
            "description": 3,
            "instructions": 4,
            "contraindications": 3,
            "safety_notes": 3,
            "setup_steps": 3,
            "execution_steps": 4,
            "common_mistakes": 3,
            "coaching_cues": 3,
        }

        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "h-4 w-4 rounded border-white/20 bg-black/30")
                continue

            widget.attrs["class"] = base_class
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("rows", textarea_rows.get(name, 3))

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Exercise name is required.")
        return name

    def save(self, commit=True):
        exercise = super().save(commit=False)
        if not exercise.slug:
            exercise.slug = self._build_unique_slug(exercise.name)
        if commit:
            exercise.save()
        return exercise

    @staticmethod
    def _build_unique_slug(name: str) -> str:
        base_slug = slugify(name) or "exercise"
        slug = base_slug
        suffix = 1
        while Exercise.objects.filter(slug=slug).exists():
            suffix += 1
            slug = f"{base_slug}-{suffix}"
        return slug


class WorkoutPlanForm(forms.ModelForm):
    class Meta:
        model = WorkoutPlan
        fields = [
            "name",
            "description",
            "community",
            "plan_type",
            "duration_band",
            "challenge_duration_days",
            "challenge_focus_area",
            "is_template",
            "is_published",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["community"].required = False
        self.fields["community"].queryset = self._community_queryset(user)
        self.fields["plan_type"].required = False
        self.fields["duration_band"].required = False
        self.fields["challenge_duration_days"].required = False
        self.fields["challenge_focus_area"].required = False

    @staticmethod
    def _community_queryset(user) -> QuerySet[Community]:
        if not user or not user.is_authenticated:
            return Community.objects.none()
        return Community.objects.filter(
            memberships__user=user,
            memberships__status=MembershipStatus.ACTIVE,
            is_archived=False,
        ).distinct()

    def clean(self):
        cleaned_data = super().clean()
        plan_type = cleaned_data.get("plan_type")
        if not plan_type:
            plan_type = WorkoutPlan._meta.get_field("plan_type").default
            cleaned_data["plan_type"] = plan_type

        duration_band = cleaned_data.get("duration_band")
        if not duration_band:
            duration_band = WorkoutPlan._meta.get_field("duration_band").default
            cleaned_data["duration_band"] = duration_band

        challenge_duration_days = cleaned_data.get("challenge_duration_days")
        challenge_focus_area = (cleaned_data.get("challenge_focus_area") or "").strip()

        if plan_type == "challenge":
            if not challenge_duration_days:
                self.add_error(
                    "challenge_duration_days",
                    "Challenge duration is required for challenge plans.",
                )
            if not challenge_focus_area:
                self.add_error(
                    "challenge_focus_area",
                    "Challenge focus area is required for challenge plans.",
                )
        else:
            cleaned_data["challenge_duration_days"] = None
            cleaned_data["challenge_focus_area"] = ""

        return cleaned_data


class WorkoutPlanItemForm(forms.ModelForm):
    class Meta:
        model = WorkoutPlanItem
        fields = ["exercise", "order", "repetitions", "duration_minutes", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["order"].required = False
        self.fields["exercise"].queryset = Exercise.objects.filter(is_active=True).order_by("name")


class WorkoutPlanAssignmentForm(forms.ModelForm):
    class Meta:
        model = WorkoutPlanAssignment
        fields = [
            "assigned_to",
            "assigned_community",
            "starts_on",
            "recurs_every_days",
            "is_active",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].required = False
        self.fields["assigned_community"].required = False

        if user and user.is_authenticated:
            self.fields["assigned_community"].queryset = Community.objects.filter(
                memberships__user=user,
                memberships__status=MembershipStatus.ACTIVE,
                is_archived=False,
            ).distinct()
        else:
            self.fields["assigned_community"].queryset = Community.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        assigned_to = cleaned_data.get("assigned_to")
        assigned_community = cleaned_data.get("assigned_community")
        if not assigned_to and not assigned_community:
            raise forms.ValidationError(
                "Select a user or a community to assign this plan."
            )
        if assigned_to and assigned_community:
            raise forms.ValidationError(
                "Assign to either one user or one community, not both."
            )
        return cleaned_data


class ExerciseMediaForm(forms.ModelForm):
    external_url = forms.URLField(required=False, assume_scheme="https")

    class Meta:
        model = ExerciseMedia
        fields = [
            "media_type",
            "file",
            "external_url",
            "license_name",
            "attribution_text",
            "rights_notes",
        ]
