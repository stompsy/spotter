from django import forms
from django.contrib import admin

from .models import (
    CurationStatus,
    Exercise,
    ExerciseCandidate,
    ExerciseCandidateDecision,
    ExerciseExtractionPage,
    ExerciseExtractionRun,
    ExerciseSource,
    WorkoutPlan,
    WorkoutPlanAssignment,
    WorkoutPlanItem,
)


class ExerciseCandidateAdminForm(forms.ModelForm):
    class Meta:
        model = ExerciseCandidate
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["metadata"].help_text = (
            "Publish requires metadata keys: source_name, source_url, attribution_text, "
            "media_rights_confirmed=true, content_rewritten=true, safety_reviewed=true."
        )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("status") != CurationStatus.PUBLISHED:
            return cleaned_data

        source = cleaned_data.get("source")
        if source is None:
            return cleaned_data

        if not source.is_approved or not source.license_name.strip():
            raise forms.ValidationError(
                "Cannot publish candidate without an approved source and license metadata"
            )

        candidate = ExerciseCandidate(
            source=source,
            raw_name=cleaned_data.get("raw_name") or "",
            normalized_name=cleaned_data.get("normalized_name") or "",
            status=cleaned_data["status"],
            metadata=cleaned_data.get("metadata") or {},
        )
        try:
            candidate.validate_publish_metadata()
        except forms.ValidationError as exc:
            self.add_error("metadata", exc)

        return cleaned_data


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "slug", "description")


class WorkoutPlanItemInline(admin.TabularInline):
    model = WorkoutPlanItem
    extra = 0


@admin.register(WorkoutPlan)
class WorkoutPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "community", "created_by", "is_template", "is_published", "created_at")
    list_filter = ("is_template", "is_published")
    search_fields = ("name", "slug", "community__name", "created_by__username")
    inlines = [WorkoutPlanItemInline]


@admin.register(WorkoutPlanAssignment)
class WorkoutPlanAssignmentAdmin(admin.ModelAdmin):
    list_display = ("plan", "assigned_to", "assigned_community", "starts_on", "is_active")
    list_filter = ("is_active",)
    search_fields = ("plan__name", "assigned_to__username", "assigned_community__name")


@admin.register(ExerciseSource)
class ExerciseSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "source_type", "location", "is_approved", "updated_at")
    list_filter = ("source_type", "is_approved")
    search_fields = ("name", "location", "license_name")


@admin.register(ExerciseCandidate)
class ExerciseCandidateAdmin(admin.ModelAdmin):
    form = ExerciseCandidateAdminForm
    list_display = (
        "normalized_name",
        "raw_name",
        "source",
        "status",
        "confidence",
        "reviewed_by",
        "reviewed_at",
        "updated_at",
    )
    list_filter = ("status", "source__source_type")
    search_fields = ("normalized_name", "raw_name", "source__name")


@admin.register(ExerciseCandidateDecision)
class ExerciseCandidateDecisionAdmin(admin.ModelAdmin):
    list_display = (
        "candidate",
        "action",
        "from_status",
        "to_status",
        "decided_by",
        "decided_at",
    )
    list_filter = ("action", "from_status", "to_status")
    search_fields = ("candidate__normalized_name", "candidate__raw_name", "reason")


@admin.register(ExerciseExtractionRun)
class ExerciseExtractionRunAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "status", "started_at", "finished_at")
    list_filter = ("status", "source__source_type")
    search_fields = ("source__name", "source__location")


@admin.register(ExerciseExtractionPage)
class ExerciseExtractionPageAdmin(admin.ModelAdmin):
    list_display = ("run", "page_number", "extraction_method", "status", "char_count")
    list_filter = ("extraction_method", "status")
    search_fields = ("run__source__name",)
