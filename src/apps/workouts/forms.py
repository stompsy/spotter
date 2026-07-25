from __future__ import annotations

from django import forms
from django.db.models import QuerySet
from django.utils.text import slugify

from apps.communities.models import Community, MembershipStatus

from .models import Exercise, WorkoutPlan, WorkoutPlanAssignment, WorkoutPlanItem


class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        fields = ["name", "category", "description", "instructions", "is_active"]

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
        fields = ["name", "description", "community", "is_template", "is_published"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["community"].required = False
        self.fields["community"].queryset = self._community_queryset(user)

    @staticmethod
    def _community_queryset(user) -> QuerySet[Community]:
        if not user or not user.is_authenticated:
            return Community.objects.none()
        return Community.objects.filter(
            memberships__user=user,
            memberships__status=MembershipStatus.ACTIVE,
            is_archived=False,
        ).distinct()


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
