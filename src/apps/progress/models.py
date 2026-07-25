from django.conf import settings
from django.db import models
from django.utils import timezone


class WorkoutLog(models.Model):
    plan = models.ForeignKey(
        "workouts.WorkoutPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )
    community = models.ForeignKey(
        "communities.Community",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workout_logs",
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="workout_logs",
    )
    completed_at = models.DateTimeField(default=timezone.now)
    perceived_exertion = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    recovery_markers = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"Workout log by {self.performed_by}"
