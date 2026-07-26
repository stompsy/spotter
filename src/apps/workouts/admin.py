from django import forms
from django.contrib import admin

from .models import (
    CurationStatus,
    Exercise,
    ExerciseCandidate,
    ExerciseCandidateDecision,
    ExerciseExtractionPage,
    ExerciseExtractionRun,
    ExerciseMedia,
    ExerciseSource,
    WorkoutPlan,
    WorkoutPlanAssignment,
    WorkoutPlanItem,
)


class ExerciseCandidateAdminForm(forms.ModelForm):
    source_name = forms.CharField(required=False)
    source_url = forms.URLField(required=False, assume_scheme="https")
    attribution_text = forms.CharField(required=False)
    media_rights_confirmed = forms.BooleanField(required=False)
    content_rewritten = forms.BooleanField(required=False)
    safety_reviewed = forms.BooleanField(required=False)

    class Meta:
        model = ExerciseCandidate
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        metadata = self.instance.metadata if isinstance(self.instance.metadata, dict) else {}
        self.fields["source_name"].initial = metadata.get("source_name", "")
        self.fields["source_url"].initial = metadata.get("source_url", "")
        self.fields["attribution_text"].initial = metadata.get("attribution_text", "")
        self.fields["media_rights_confirmed"].initial = metadata.get(
            "media_rights_confirmed",
            False,
        )
        self.fields["content_rewritten"].initial = metadata.get("content_rewritten", False)
        self.fields["safety_reviewed"].initial = metadata.get("safety_reviewed", False)

        self.fields["source_name"].help_text = "Required when status is published."
        self.fields["source_url"].help_text = "Required when status is published."
        self.fields["attribution_text"].help_text = "Required when status is published."
        self.fields["media_rights_confirmed"].help_text = "Must be checked to publish."
        self.fields["content_rewritten"].help_text = "Must be checked to publish."
        self.fields["safety_reviewed"].help_text = "Must be checked to publish."
        self.fields["metadata"].help_text = (
            "Optional extra metadata JSON. Publish checks use the structured fields above."
        )

    def clean(self):
        cleaned_data = super().clean()
        metadata = cleaned_data.get("metadata") or {}
        metadata["source_name"] = (cleaned_data.get("source_name") or "").strip()
        metadata["source_url"] = (cleaned_data.get("source_url") or "").strip()
        metadata["attribution_text"] = (cleaned_data.get("attribution_text") or "").strip()
        metadata["media_rights_confirmed"] = bool(cleaned_data.get("media_rights_confirmed"))
        metadata["content_rewritten"] = bool(cleaned_data.get("content_rewritten"))
        metadata["safety_reviewed"] = bool(cleaned_data.get("safety_reviewed"))
        cleaned_data["metadata"] = metadata

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
            metadata=metadata,
        )
        try:
            candidate.validate_publish_metadata()
        except forms.ValidationError as exc:
            self.add_error("metadata", exc)

        return cleaned_data


class ExerciseMediaInline(admin.TabularInline):
    model = ExerciseMedia
    extra = 0


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "slug", "description")
    inlines = [ExerciseMediaInline]


@admin.register(ExerciseMedia)
class ExerciseMediaAdmin(admin.ModelAdmin):
    list_display = (
        "exercise",
        "media_type",
        "license_name",
        "external_url",
        "created_at",
    )
    list_filter = ("media_type",)
    search_fields = ("exercise__name", "license_name", "attribution_text", "external_url")


class WorkoutPlanItemInline(admin.TabularInline):
    model = WorkoutPlanItem
    extra = 0


@admin.register(WorkoutPlan)
class WorkoutPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "plan_type",
        "duration_band",
        "challenge_duration_days",
        "community",
        "created_by",
        "is_template",
        "is_published",
        "created_at",
    )
    list_filter = ("plan_type", "duration_band", "is_template", "is_published")
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
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "source",
                    "raw_name",
                    "normalized_name",
                    "status",
                    "confidence",
                )
            },
        ),
        (
            "Publish metadata",
            {
                "fields": (
                    "source_name",
                    "source_url",
                    "attribution_text",
                    "media_rights_confirmed",
                    "content_rewritten",
                    "safety_reviewed",
                ),
                "description": "Complete these fields before publishing candidates.",
            },
        ),
        (
            "Review metadata",
            {
                "fields": (
                    "reviewed_by",
                    "reviewed_at",
                    "decision_reason",
                )
            },
        ),
        (
            "Additional metadata",
            {"fields": ("metadata",), "classes": ("collapse",)},
        ),
    )
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
