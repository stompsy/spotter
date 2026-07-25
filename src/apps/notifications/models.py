from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationType(models.TextChoices):
    JOIN_REQUEST = "join_request", "Join request"
    JOIN_DECISION = "join_decision", "Join decision"
    PLAN_ASSIGNED = "plan_assigned", "Plan assigned"
    REMINDER = "reminder", "Reminder"
    MODERATION_DECISION = "moderation_decision", "Moderation decision"


class DeliveryStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


class NotificationEvent(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=64, choices=NotificationType.choices)
    subject = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    delivery_status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
    )
    payload = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.notification_type} for {self.recipient}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def mark_read(self) -> None:
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])
