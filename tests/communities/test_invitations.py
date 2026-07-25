from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.communities.models import (
    Community,
    CommunityInvitation,
    CommunityMembership,
    CommunityVisibility,
    MembershipRole,
    MembershipStatus,
)


@pytest.mark.django_db
def test_moderator_can_create_private_invitation(client):
    user_model = get_user_model()
    owner = user_model.objects.create_user(
        username="owner_inv",
        email="owner_inv@example.com",
        password="pw",
    )
    moderator = user_model.objects.create_user(
        username="mod_inv",
        email="mod_inv@example.com",
        password="pw",
    )
    community = Community.objects.create(
        name="Private Team",
        slug="private-team",
        visibility=CommunityVisibility.PRIVATE,
        created_by=owner,
    )
    CommunityMembership.objects.create(
        community=community,
        user=moderator,
        role=MembershipRole.MODERATOR,
        status=MembershipStatus.ACTIVE,
    )

    client.force_login(moderator)
    response = client.post(
        reverse("communities:create_invitation", kwargs={"slug": community.slug}),
        {"invited_email": "invitee@example.com", "expires_days": "5"},
    )

    assert response.status_code == 302
    invitation = CommunityInvitation.objects.get(community=community)
    assert invitation.invited_email == "invitee@example.com"
    assert invitation.created_by_id == moderator.id


@pytest.mark.django_db
def test_member_cannot_create_invitation(client):
    user_model = get_user_model()
    owner = user_model.objects.create_user(
        username="owner_mem",
        email="owner_mem@example.com",
        password="pw",
    )
    member = user_model.objects.create_user(
        username="member_inv",
        email="member_inv@example.com",
        password="pw",
    )
    community = Community.objects.create(
        name="Private Squad",
        slug="private-squad",
        visibility=CommunityVisibility.PRIVATE,
        created_by=owner,
    )
    CommunityMembership.objects.create(
        community=community,
        user=member,
        role=MembershipRole.MEMBER,
        status=MembershipStatus.ACTIVE,
    )

    client.force_login(member)
    response = client.post(
        reverse("communities:create_invitation", kwargs={"slug": community.slug}),
    )

    assert response.status_code == 404
    assert CommunityInvitation.objects.count() == 0


@pytest.mark.django_db
def test_user_can_accept_valid_invitation(client):
    user_model = get_user_model()
    owner = user_model.objects.create_user(
        username="owner_acc",
        email="owner_acc@example.com",
        password="pw",
    )
    invitee = user_model.objects.create_user(
        username="invitee",
        email="invitee@example.com",
        password="pw",
    )
    community = Community.objects.create(
        name="Invite Community",
        slug="invite-community",
        visibility=CommunityVisibility.PRIVATE,
        created_by=owner,
    )
    invitation = CommunityInvitation.objects.create(
        community=community,
        invited_email="invitee@example.com",
        created_by=owner,
        expires_at=timezone.now() + timedelta(days=3),
    )

    client.force_login(invitee)
    response = client.get(
        reverse("communities:accept_invitation", kwargs={"invite_code": invitation.invite_code}),
    )

    assert response.status_code == 302
    invitation.refresh_from_db()
    assert invitation.accepted_at is not None

    membership = CommunityMembership.objects.get(community=community, user=invitee)
    assert membership.status == MembershipStatus.ACTIVE


@pytest.mark.django_db
def test_invitation_rejects_wrong_email_and_expired(client):
    user_model = get_user_model()
    owner = user_model.objects.create_user(
        username="owner_exp",
        email="owner_exp@example.com",
        password="pw",
    )
    wrong_user = user_model.objects.create_user(
        username="wrong_user",
        email="wrong_user@example.com",
        password="pw",
    )
    community = Community.objects.create(
        name="Strict Community",
        slug="strict-community",
        visibility=CommunityVisibility.PRIVATE,
        created_by=owner,
    )
    email_scoped_invitation = CommunityInvitation.objects.create(
        community=community,
        invited_email="target@example.com",
        created_by=owner,
        expires_at=timezone.now() + timedelta(days=2),
    )
    expired_invitation = CommunityInvitation.objects.create(
        community=community,
        invited_email="wrong_user@example.com",
        created_by=owner,
        expires_at=timezone.now() - timedelta(hours=1),
    )

    client.force_login(wrong_user)
    wrong_email_response = client.get(
        reverse(
            "communities:accept_invitation",
            kwargs={"invite_code": email_scoped_invitation.invite_code},
        ),
    )
    expired_response = client.get(
        reverse(
            "communities:accept_invitation",
            kwargs={"invite_code": expired_invitation.invite_code},
        ),
    )

    assert wrong_email_response.status_code == 404
    assert expired_response.status_code == 404
    assert CommunityMembership.objects.filter(community=community, user=wrong_user).count() == 0
