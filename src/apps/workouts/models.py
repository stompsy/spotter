from django.conf import settings
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
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["normalized_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "normalized_name"],
                name="unique_candidate_name_per_source",
            )
        ]

    def __str__(self) -> str:
        return self.normalized_name


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
