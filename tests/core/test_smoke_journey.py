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
from apps.notifications.models import NotificationEvent, NotificationType
from apps.progress.models import WorkoutLog
from apps.workouts.models import WorkoutPlan, WorkoutPlanAssignment


@pytest.mark.django_db
def test_smoke_signup_join_review_notifications_and_workout_logging(client):
    user_model = get_user_model()

    owner = user_model.objects.create_user(
        username="smoke_owner",
        email="smoke_owner@example.com",
        password="pw",
    )
    moderator = user_model.objects.create_user(
        username="smoke_mod",
        email="smoke_mod@example.com",
        password="pw",
    )

    signup_page = client.get(reverse("account_signup"))
    assert signup_page.status_code == 200

    signup_response = client.post(
        reverse("account_signup"),
        {
            "username": "smoke_requester",
            "email": "smoke_requester@example.com",
            "password1": "SmoketestPass123!",
            "password2": "SmoketestPass123!",
        },
    )
    assert signup_response.status_code == 302

    requester = user_model.objects.get(username="smoke_requester")
    rejected_requester = user_model.objects.create_user(
        username="smoke_reject",
        email="smoke_reject@example.com",
        password="pw",
    )

    community = Community.objects.create(
        name="Smoke Community",
        slug="smoke-community",
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
    join_response = client.post(
        reverse("communities:join", kwargs={"slug": community.slug}),
        {"message": "Please add me."},
    )
    assert join_response.status_code == 302

    client.force_login(rejected_requester)
    second_join_response = client.post(
        reverse("communities:join", kwargs={"slug": community.slug}),
        {"message": "I want to join too."},
    )
    assert second_join_response.status_code == 302

    join_request = CommunityJoinRequest.objects.get(requested_by=requester)
    rejected_join_request = CommunityJoinRequest.objects.get(requested_by=rejected_requester)

    client.force_login(moderator)
    approve_response = client.post(
        reverse(
            "communities:review",
            kwargs={"slug": community.slug, "join_request_id": join_request.id},
        ),
        {"decision": "approved"},
    )
    assert approve_response.status_code == 302

    reject_response = client.post(
        reverse(
            "communities:review",
            kwargs={"slug": community.slug, "join_request_id": rejected_join_request.id},
        ),
        {"decision": "rejected", "reason": "Capacity reached."},
    )
    assert reject_response.status_code == 302

    join_request.refresh_from_db()
    rejected_join_request.refresh_from_db()
    assert join_request.status == JoinRequestStatus.APPROVED
    assert rejected_join_request.status == JoinRequestStatus.REJECTED

    approved_membership = CommunityMembership.objects.get(community=community, user=requester)
    rejected_membership = CommunityMembership.objects.get(
        community=community,
        user=rejected_requester,
    )
    assert approved_membership.status == MembershipStatus.ACTIVE
    assert rejected_membership.status == MembershipStatus.REJECTED

    decision_events = NotificationEvent.objects.filter(
        notification_type=NotificationType.JOIN_DECISION
    )
    assert decision_events.count() == 2

    client.force_login(requester)
    inbox_response = client.get(reverse("notifications:inbox"))
    assert inbox_response.status_code == 200
    assert inbox_response.context["unread_notifications_count"] >= 1

    mark_all_response = client.post(reverse("notifications:mark_all_read"))
    assert mark_all_response.status_code == 302
    assert NotificationEvent.objects.filter(recipient=requester, read_at__isnull=True).count() == 0

    client.force_login(owner)
    create_plan_response = client.post(
        reverse("workouts:list"),
        {
            "name": "Smoke Plan",
            "description": "Plan used by smoke test",
            "community": community.id,
            "is_published": "on",
        },
    )
    assert create_plan_response.status_code == 302

    plan = WorkoutPlan.objects.get(name="Smoke Plan")

    assign_response = client.post(
        reverse("workouts:assign", kwargs={"slug": plan.slug}),
        {
            "assigned_to": requester.id,
            "assigned_community": "",
            "starts_on": "2026-07-25",
            "recurs_every_days": "7",
            "is_active": "on",
        },
    )
    assert assign_response.status_code == 302

    assignment = WorkoutPlanAssignment.objects.get(plan=plan, assigned_to=requester)
    assert assignment.is_active is True

    log = WorkoutLog.objects.create(
        plan=plan,
        community=community,
        performed_by=requester,
        perceived_exertion=7,
        notes="Completed all intervals",
        recovery_markers={"sleep": "good", "soreness": "low"},
    )
    assert WorkoutLog.objects.filter(id=log.id).exists()
