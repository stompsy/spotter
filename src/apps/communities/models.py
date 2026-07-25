import uuid

from django.conf import settings
from django.db import models


class CommunityVisibility(models.TextChoices):
    PUBLIC = "public", "Public"
    PRIVATE = "private", "Private"


class MembershipRole(models.TextChoices):
    OWNER = "owner", "Owner"
    MODERATOR = "moderator", "Moderator"
    MEMBER = "member", "Member"


class MembershipStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    REJECTED = "rejected", "Rejected"
    LEFT = "left", "Left"


class JoinRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class Community(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    visibility = models.CharField(
        max_length=20,
        choices=CommunityVisibility.choices,
        default=CommunityVisibility.PUBLIC,
    )
    is_archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_communities",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class CommunityMembership(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=MembershipRole.choices,
        default=MembershipRole.MEMBER,
    )
    status = models.CharField(
        max_length=20,
        choices=MembershipStatus.choices,
        default=MembershipStatus.PENDING,
    )
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["community", "user"], name="unique_membership")
        ]

    def __str__(self) -> str:
        return f"{self.user} in {self.community}"


class CommunityJoinRequest(models.Model):
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="join_requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_join_requests",
    )
    message = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=JoinRequestStatus.choices,
        default=JoinRequestStatus.PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_join_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Join request for {self.community} by {self.requested_by}"


class CommunityInvitation(models.Model):
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    invite_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    invited_email = models.EmailField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_invitations",
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Invitation for {self.community}"
