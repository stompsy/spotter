from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ExerciseCategory(models.TextChoices):
    MOVEMENT_PREPARATION = "movement_preparation", "Movement preparation"
    CALISTHENICS = "calisthenics", "Calisthenics"
    POST_WORKOUT_REGENERATION = "post_workout_regeneration", "Post-workout regeneration"


class ExerciseSourceType(models.TextChoices):
    DOCUMENT = "document", "Document"
    WEB = "web", "Web reference"
    DATASET = "dataset", "Dataset"


class CurationStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    NEEDS_REVIEW = "needs_review", "Needs review"
    APPROVED = "approved", "Approved"
    PUBLISHED = "published", "Published"
    DEPRECATED = "deprecated", "Deprecated"


class ExtractionRunStatus(models.TextChoices):
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors", "Completed with errors"
    FAILED = "failed", "Failed"


class ExtractionMethod(models.TextChoices):
    TEXT_FILE = "text_file", "Text file"
    PYPDF = "pypdf", "PyPDF"
    UNSUPPORTED = "unsupported", "Unsupported"


class ExtractionPageStatus(models.TextChoices):
    EXTRACTED = "extracted", "Extracted"
    PARTIAL = "partial", "Partial"
    FAILED = "failed", "Failed"


class Exercise(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=64, choices=ExerciseCategory.choices)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class ExerciseSource(models.Model):
    name = models.CharField(max_length=200)
    source_type = models.CharField(
        max_length=32,
        choices=ExerciseSourceType.choices,
        default=ExerciseSourceType.DOCUMENT,
    )
    location = models.CharField(max_length=500, unique=True)
    license_name = models.CharField(max_length=200, blank=True)
    is_approved = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class ExerciseCandidate(models.Model):
    source = models.ForeignKey(
        ExerciseSource,
        on_delete=models.CASCADE,
        related_name="candidates",
    )
    raw_name = models.CharField(max_length=200)
    normalized_name = models.CharField(max_length=200)
    status = models.CharField(
        max_length=32,
        choices=CurationStatus.choices,
        default=CurationStatus.DRAFT,
    )
    confidence = models.DecimalField(max_digits=4, decimal_places=3, default=0.0)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_exercise_candidates",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["normalized_name", "id"]
        permissions = [
            ("review_exercisecandidate", "Can review exercise candidates"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "normalized_name"],
                name="unique_candidate_name_per_source",
            )
        ]

    def __str__(self) -> str:
        return self.normalized_name

    def can_transition_to(self, new_status: str) -> bool:
        allowed_transitions = {
            CurationStatus.DRAFT: {
                CurationStatus.NEEDS_REVIEW,
                CurationStatus.DEPRECATED,
            },
            CurationStatus.NEEDS_REVIEW: {
                CurationStatus.DRAFT,
                CurationStatus.APPROVED,
                CurationStatus.DEPRECATED,
            },
            CurationStatus.APPROVED: {
                CurationStatus.PUBLISHED,
                CurationStatus.DEPRECATED,
            },
            CurationStatus.PUBLISHED: {
                CurationStatus.DEPRECATED,
            },
            CurationStatus.DEPRECATED: {
                CurationStatus.NEEDS_REVIEW,
            },
        }
        return new_status in allowed_transitions.get(self.status, set())

    def validate_publish_metadata(self) -> None:
        metadata = self.metadata if isinstance(self.metadata, dict) else {}
        required_text_fields = [
            "source_name",
            "source_url",
            "attribution_text",
        ]
        required_true_flags = [
            "media_rights_confirmed",
            "content_rewritten",
            "safety_reviewed",
        ]

        missing_text_fields = [
            key
            for key in required_text_fields
            if not str(metadata.get(key, "")).strip()
        ]
        missing_true_flags = [
            key
            for key in required_true_flags
            if metadata.get(key) is not True
        ]

        if missing_text_fields or missing_true_flags:
            missing_items = ", ".join(missing_text_fields + missing_true_flags)
            raise ValidationError(
                "Cannot publish candidate without required attribution and safety metadata: "
                f"{missing_items}"
            )

    def transition_to(self, new_status: str) -> None:
        valid_statuses = {choice[0] for choice in CurationStatus.choices}
        if new_status not in valid_statuses:
            raise ValidationError(f"Unknown curation status: {new_status}")
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"Invalid status transition from {self.status} to {new_status}"
            )
        if new_status == CurationStatus.PUBLISHED:
            if not self.source.is_approved or not self.source.license_name.strip():
                raise ValidationError(
                    "Cannot publish candidate without an approved source and license metadata"
                )
            self.validate_publish_metadata()
        self.status = new_status


class ExerciseCandidateDecision(models.Model):
    candidate = models.ForeignKey(
        ExerciseCandidate,
        on_delete=models.CASCADE,
        related_name="decisions",
    )
    action = models.CharField(max_length=32)
    from_status = models.CharField(max_length=32, choices=CurationStatus.choices)
    to_status = models.CharField(max_length=32, choices=CurationStatus.choices)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exercise_candidate_decisions",
    )
    reason = models.TextField(blank=True)
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-decided_at", "-id"]

    def __str__(self) -> str:
        return f"{self.candidate.normalized_name}: {self.from_status} -> {self.to_status}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("Exercise candidate decisions are immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Exercise candidate decisions are immutable")


class ExerciseExtractionRun(models.Model):
    source = models.ForeignKey(
        ExerciseSource,
        on_delete=models.CASCADE,
        related_name="extraction_runs",
    )
    status = models.CharField(
        max_length=32,
        choices=ExtractionRunStatus.choices,
        default=ExtractionRunStatus.RUNNING,
    )
    summary = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at", "-id"]

    def __str__(self) -> str:
        return f"Extraction run for {self.source.name}"


class ExerciseExtractionPage(models.Model):
    run = models.ForeignKey(
        ExerciseExtractionRun,
        on_delete=models.CASCADE,
        related_name="pages",
    )
    page_number = models.PositiveIntegerField()
    extraction_method = models.CharField(
        max_length=32,
        choices=ExtractionMethod.choices,
    )
    status = models.CharField(
        max_length=32,
        choices=ExtractionPageStatus.choices,
    )
    raw_text = models.TextField(blank=True)
    cleaned_text = models.TextField(blank=True)
    char_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["page_number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "page_number"],
                name="unique_page_number_per_extraction_run",
            )
        ]

    def __str__(self) -> str:
        return f"{self.run_id} page {self.page_number}"


class WorkoutPlan(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_workout_plans",
    )
    community = models.ForeignKey(
        "communities.Community",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workout_plans",
    )
    is_template = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class WorkoutPlanItem(models.Model):
    plan = models.ForeignKey(WorkoutPlan, on_delete=models.CASCADE, related_name="items")
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name="plan_items")
    order = models.PositiveIntegerField(default=0)
    repetitions = models.CharField(max_length=100, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "order"], name="unique_plan_item_order")
        ]

    def __str__(self) -> str:
        return f"{self.plan} - {self.exercise}"


class WorkoutPlanAssignment(models.Model):
    plan = models.ForeignKey(
        WorkoutPlan,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="assigned_workout_plans",
    )
    assigned_community = models.ForeignKey(
        "communities.Community",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="assigned_workout_plans",
    )
    starts_on = models.DateField(null=True, blank=True)
    recurs_every_days = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Assignment for {self.plan}"
