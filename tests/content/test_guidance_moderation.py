import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.communities.models import (
    Community,
    CommunityMembership,
    MembershipRole,
    MembershipStatus,
)
from apps.content.models import ContentStatus, GuidanceContent, GuidanceTopic
from apps.moderation.models import ModerationDecision, ModerationRecord
from apps.notifications.models import NotificationEvent, NotificationType


@pytest.mark.django_db
def test_author_can_submit_guidance_for_review(client):
    user_model = get_user_model()
    author = user_model.objects.create_user(
        username="guide_author",
        email="guide_author@example.com",
        password="pw",
    )
    community = Community.objects.create(
        name="Guidance Crew",
        slug="guidance-crew",
        created_by=author,
    )
    CommunityMembership.objects.create(
        community=community,
        user=author,
        role=MembershipRole.OWNER,
        status=MembershipStatus.ACTIVE,
    )

    guidance = GuidanceContent.objects.create(
        title="Hydration Basics",
        topic=GuidanceTopic.HYDRATION,
        body="Drink consistently.",
        community=community,
        author=author,
        status=ContentStatus.DRAFT,
    )

    client.force_login(author)
    response = client.post(
        reverse("guidance:submit", kwargs={"guidance_id": guidance.pk}),
    )

    assert response.status_code == 302
    guidance.refresh_from_db()
    assert guidance.status == ContentStatus.PENDING


@pytest.mark.django_db
def test_moderator_can_approve_then_publish_guidance(client):
    user_model = get_user_model()
    author = user_model.objects.create_user(
        username="author_mod",
        email="author_mod@example.com",
        password="pw",
    )
    moderator = user_model.objects.create_user(
        username="mod_guide",
        email="mod_guide@example.com",
        password="pw",
    )
    community = Community.objects.create(
        name="Review Team",
        slug="review-team",
        created_by=author,
    )
    CommunityMembership.objects.create(
        community=community,
        user=moderator,
        role=MembershipRole.MODERATOR,
        status=MembershipStatus.ACTIVE,
    )

    guidance = GuidanceContent.objects.create(
        title="Recovery Flow",
        topic=GuidanceTopic.RECOVERY,
        body="Stretch and walk.",
        community=community,
        author=author,
        status=ContentStatus.PENDING,
    )

    client.force_login(moderator)
    moderate_response = client.post(
        reverse("guidance:moderate", kwargs={"guidance_id": guidance.pk}),
        {"decision": ModerationDecision.APPROVED, "reason": "Clear and actionable"},
    )
    assert moderate_response.status_code == 302

    guidance.refresh_from_db()
    assert guidance.status == ContentStatus.APPROVED
    assert guidance.published_at is None

    moderation_record = ModerationRecord.objects.get(target_id=str(guidance.pk))
    assert moderation_record.decision == ModerationDecision.APPROVED
    assert moderation_record.decided_by == moderator

    event = NotificationEvent.objects.get(
        recipient=author,
        notification_type=NotificationType.MODERATION_DECISION,
    )
    assert event.payload["decision"] == ModerationDecision.APPROVED

    publish_response = client.post(
        reverse("guidance:publish", kwargs={"guidance_id": guidance.pk}),
    )
    assert publish_response.status_code == 302

    guidance.refresh_from_db()
    assert guidance.published_at is not None


@pytest.mark.django_db
def test_non_moderator_cannot_review_guidance(client):
    user_model = get_user_model()
    author = user_model.objects.create_user(
        username="author_nonmod",
        email="author_nonmod@example.com",
        password="pw",
    )
    member = user_model.objects.create_user(
        username="member_nonmod",
        email="member_nonmod@example.com",
        password="pw",
    )
    community = Community.objects.create(
        name="Member Team",
        slug="member-team",
        created_by=author,
    )
    CommunityMembership.objects.create(
        community=community,
        user=member,
        role=MembershipRole.MEMBER,
        status=MembershipStatus.ACTIVE,
    )
    guidance = GuidanceContent.objects.create(
        title="Foot Care",
        topic=GuidanceTopic.FOOT_CARE,
        body="Dry feet after runs.",
        community=community,
        author=author,
        status=ContentStatus.PENDING,
    )

    client.force_login(member)
    response = client.post(
        reverse("guidance:moderate", kwargs={"guidance_id": guidance.pk}),
        {"decision": ModerationDecision.REJECTED},
    )

    assert response.status_code == 404
    guidance.refresh_from_db()
    assert guidance.status == ContentStatus.PENDING
    assert ModerationRecord.objects.count() == 0
