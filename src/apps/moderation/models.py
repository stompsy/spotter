from django.conf import settings
from django.db import models


class ModerationDecision(models.TextChoices):
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    NEEDS_CHANGES = "needs_changes", "Needs changes"


class ModerationRecord(models.Model):
    target_type = models.CharField(max_length=200)
    target_id = models.CharField(max_length=64)
    decision = models.CharField(max_length=32, choices=ModerationDecision.choices)
    reason = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="moderation_records",
    )
    decided_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"{self.target_type}:{self.target_id} -> {self.decision}"
