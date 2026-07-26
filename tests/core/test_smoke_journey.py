import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.communities.models import (
    Community,
    CommunityJoinRequest,
    CommunityMembership,
    JoinRequestStatus,
    MembershipRole,
    MembershipStatus,
)
from apps.notifications.models import (
    DeliveryStatus,
    NotificationEvent,
    NotificationType,
)
from apps.progress.models import WorkoutLog
from apps.workouts.models import WorkoutPlan, WorkoutPlanAssignment


@pytest.mark.django_db
def test_smoke_signup_flow_creates_account(client):
    signup_page = client.get(reverse("account_signup"))
    assert signup_page.status_code == 200

    signup_response = client.post(
        reverse("account_signup"),
        {
            "username": "smoke_signup",
            "email": "smoke_signup@example.com",
            "password1": "SmoketestPass123!",
            "password2": "SmoketestPass123!",
        },
    )
    assert signup_response.status_code == 302

    user_model = get_user_model()
    created = user_model.objects.get(username="smoke_signup")
    assert created.email == "smoke_signup@example.com"


@pytest.mark.django_db
def test_smoke_login_flow_can_access_protected_notifications(client):
    user_model = get_user_model()
    password = "SmokeloginPass123!"
    user = user_model.objects.create_user(
        username="smoke_login",
        email="smoke_login@example.com",
        password=password,
    )

    login_response = client.post(
        reverse("account_login"),
        {
            "login": user.username,
            "password": password,
        },
    )
    assert login_response.status_code == 302

    inbox_response = client.get(reverse("notifications:inbox"))
    assert inbox_response.status_code == 200


@pytest.fixture
def smoke_context():
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
    requester = user_model.objects.create_user(
        username="smoke_requester",
        email="smoke_requester@example.com",
        password="pw",
    )
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

    return {
        "owner": owner,
        "moderator": moderator,
        "requester": requester,
        "rejected_requester": rejected_requester,
        "community": community,
    }


@pytest.mark.django_db
def test_smoke_community_join_review_flow(smoke_context, client):
    community = smoke_context["community"]
    moderator = smoke_context["moderator"]
    requester = smoke_context["requester"]
    rejected_requester = smoke_context["rejected_requester"]

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


@pytest.mark.django_db
def test_smoke_notifications_flow_marks_inbox_read(smoke_context, client):
    requester = smoke_context["requester"]

    NotificationEvent.objects.create(
        recipient=requester,
        notification_type=NotificationType.JOIN_REQUEST,
        subject="Smoke notification",
        body="Smoke body",
    )

    client.force_login(requester)
    inbox_response = client.get(reverse("notifications:inbox"))
    assert inbox_response.status_code == 200
    assert inbox_response.context["unread_notifications_count"] >= 1

    mark_all_response = client.post(reverse("notifications:mark_all_read"))
    assert mark_all_response.status_code == 302
    assert NotificationEvent.objects.filter(recipient=requester, read_at__isnull=True).count() == 0


@pytest.mark.django_db
def test_smoke_workout_assignment_and_logging_persists(smoke_context, client):
    owner = smoke_context["owner"]
    requester = smoke_context["requester"]
    community = smoke_context["community"]

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


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_smoke_reminder_dispatch_dry_run_and_delivery(client):
    user_model = get_user_model()
    coach = user_model.objects.create_user(
        username="smoke_reminder_coach",
        email="smoke_reminder_coach@example.com",
        password="pw",
    )
    athlete = user_model.objects.create_user(
        username="smoke_reminder_athlete",
        email="smoke_reminder_athlete@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Smoke Reminder Plan",
        slug="smoke-reminder-plan",
        created_by=coach,
        is_published=True,
    )
    WorkoutPlanAssignment.objects.create(
        plan=plan,
        assigned_to=athlete,
        starts_on=timezone.localdate(),
        is_active=True,
    )

    call_command("send_reminders", dry_run=True)
    assert NotificationEvent.objects.filter(
        notification_type=NotificationType.REMINDER
    ).count() == 0

    call_command("send_reminders")
    event = NotificationEvent.objects.get(notification_type=NotificationType.REMINDER)
    assert event.delivery_status == DeliveryStatus.SENT
    assert event.sent_at is not None
