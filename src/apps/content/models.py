from django.conf import settings
from django.db import models


class ContentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    ARCHIVED = "archived", "Archived"


class GuidanceTopic(models.TextChoices):
    NUTRITION = "nutrition", "Nutrition"
    HYDRATION = "hydration", "Hydration"
    FOOT_CARE = "foot_care", "Foot care"
    RECOVERY = "recovery", "Recovery"


class GuidanceContent(models.Model):
    title = models.CharField(max_length=200)
    topic = models.CharField(max_length=64, choices=GuidanceTopic.choices)
    body = models.TextField()
    community = models.ForeignKey(
        "communities.Community",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guidance_content",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="guidance_submissions",
    )
    status = models.CharField(
        max_length=20,
        choices=ContentStatus.choices,
        default=ContentStatus.DRAFT,
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.title
