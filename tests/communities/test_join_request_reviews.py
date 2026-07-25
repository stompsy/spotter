import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.communities.models import (
    Community,
    CommunityJoinRequest,
    CommunityMembership,
    JoinRequestStatus,
    MembershipRole,
    MembershipStatus,
)
from apps.moderation.models import ModerationDecision, ModerationRecord
from apps.notifications.models import NotificationEvent, NotificationType


@pytest.mark.django_db
def test_moderator_can_approve_join_request(client):
    user_model = get_user_model()
    owner = user_model.objects.create_user(
        username="owner",
        email="owner@example.com",
        password="pw",
    )
    moderator = user_model.objects.create_user(
        username="mod",
        email="mod@example.com",
        password="pw",
    )
    requester = user_model.objects.create_user(
        username="requester",
        email="requester@example.com",
        password="pw",
    )

    community = Community.objects.create(
        name="Runners",
        slug="runners",
        created_by=owner,
    )
    CommunityMembership.objects.create(
        community=community,
        user=moderator,
        role=MembershipRole.MODERATOR,
        status=MembershipStatus.ACTIVE,
    )
    join_request = CommunityJoinRequest.objects.create(
        community=community,
        requested_by=requester,
        status=JoinRequestStatus.PENDING,
        message="I want in",
    )
    CommunityMembership.objects.create(
        community=community,
        user=requester,
        status=MembershipStatus.PENDING,
    )

    client.force_login(moderator)
    response = client.post(
        reverse(
            "communities:review",
            kwargs={"slug": community.slug, "join_request_id": join_request.id},
        ),
        {"decision": "approved"},
    )

    assert response.status_code == 302

    join_request.refresh_from_db()
    assert join_request.status == JoinRequestStatus.APPROVED
    assert join_request.reviewed_by_id == moderator.id

    membership = CommunityMembership.objects.get(community=community, user=requester)
    assert membership.status == MembershipStatus.ACTIVE
    assert membership.joined_at is not None

    moderation_record = ModerationRecord.objects.get(target_id=str(join_request.id))
    assert moderation_record.target_type == "community_join_request"
    assert moderation_record.decision == ModerationDecision.APPROVED
    assert moderation_record.decided_by_id == moderator.id

    decision_event = NotificationEvent.objects.get(
        recipient=requester,
        notification_type=NotificationType.JOIN_DECISION,
    )
    assert decision_event.payload["decision"] == JoinRequestStatus.APPROVED


@pytest.mark.django_db
def test_moderator_can_reject_join_request(client):
    user_model = get_user_model()
    owner = user_model.objects.create_user(
        username="owner2",
        email="owner2@example.com",
        password="pw",
    )
    moderator = user_model.objects.create_user(
        username="mod2",
        email="mod2@example.com",
        password="pw",
    )
    requester = user_model.objects.create_user(
        username="requester2",
        email="requester2@example.com",
        password="pw",
    )

    community = Community.objects.create(
        name="Cyclists",
        slug="cyclists",
        created_by=owner,
    )
    CommunityMembership.objects.create(
        community=community,
        user=moderator,
        role=MembershipRole.MODERATOR,
        status=MembershipStatus.ACTIVE,
    )
    join_request = CommunityJoinRequest.objects.create(
        community=community,
        requested_by=requester,
        status=JoinRequestStatus.PENDING,
    )
    CommunityMembership.objects.create(
        community=community,
        user=requester,
        status=MembershipStatus.PENDING,
    )

    client.force_login(moderator)
    response = client.post(
        reverse(
            "communities:review",
            kwargs={"slug": community.slug, "join_request_id": join_request.id},
        ),
        {"decision": "rejected", "reason": "Not a fit"},
    )

    assert response.status_code == 302

    join_request.refresh_from_db()
    assert join_request.status == JoinRequestStatus.REJECTED

    membership = CommunityMembership.objects.get(community=community, user=requester)
    assert membership.status == MembershipStatus.REJECTED

    moderation_record = ModerationRecord.objects.get(target_id=str(join_request.id))
    assert moderation_record.decision == ModerationDecision.REJECTED
    assert moderation_record.reason == "Not a fit"

    decision_event = NotificationEvent.objects.get(
        recipient=requester,
        notification_type=NotificationType.JOIN_DECISION,
    )
    assert decision_event.payload["decision"] == JoinRequestStatus.REJECTED


@pytest.mark.django_db
def test_non_moderator_cannot_review_join_request(client):
    user_model = get_user_model()
    owner = user_model.objects.create_user(
        username="owner3",
        email="owner3@example.com",
        password="pw",
    )
    regular_member = user_model.objects.create_user(
        username="member",
        email="member@example.com",
        password="pw",
    )
    requester = user_model.objects.create_user(
        username="requester3",
        email="requester3@example.com",
        password="pw",
    )

    community = Community.objects.create(
        name="Hikers",
        slug="hikers",
        created_by=owner,
    )
    CommunityMembership.objects.create(
        community=community,
        user=regular_member,
        role=MembershipRole.MEMBER,
        status=MembershipStatus.ACTIVE,
    )
    join_request = CommunityJoinRequest.objects.create(
        community=community,
        requested_by=requester,
        status=JoinRequestStatus.PENDING,
    )

    client.force_login(regular_member)
    response = client.post(
        reverse(
            "communities:review",
            kwargs={"slug": community.slug, "join_request_id": join_request.id},
        ),
        {"decision": "approved"},
    )

    assert response.status_code == 404

    join_request.refresh_from_db()
    assert join_request.status == JoinRequestStatus.PENDING
    assert ModerationRecord.objects.count() == 0
    assert NotificationEvent.objects.count() == 0


@pytest.mark.django_db
def test_join_request_submission_notifies_moderators(client):
    user_model = get_user_model()
    owner = user_model.objects.create_user(
        username="owner4",
        email="owner4@example.com",
        password="pw",
    )
    moderator = user_model.objects.create_user(
        username="mod4",
        email="mod4@example.com",
        password="pw",
    )
    requester = user_model.objects.create_user(
        username="requester4",
        email="requester4@example.com",
        password="pw",
    )

    community = Community.objects.create(
        name="Rowers",
        slug="rowers",
        created_by=owner,
    )
    CommunityMembership.objects.create(
        community=community,
        user=owner,
        role=MembershipRole.OWNER,
        status=MembershipStatus.ACTIVE,
    )
    CommunityMembership.objects.create(
        community=community,
        user=moderator,
        role=MembershipRole.MODERATOR,
        status=MembershipStatus.ACTIVE,
    )

    client.force_login(requester)
    response = client.post(
        reverse("communities:join", kwargs={"slug": community.slug}),
        {"message": "Can I join this group?"},
    )
    assert response.status_code == 302

    notifications = NotificationEvent.objects.filter(
        notification_type=NotificationType.JOIN_REQUEST,
    )
    assert notifications.count() == 2
    assert set(notifications.values_list("recipient__username", flat=True)) == {
        "owner4",
        "mod4",
    }
