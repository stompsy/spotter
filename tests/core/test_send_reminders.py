from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from apps.notifications.models import DeliveryStatus, NotificationEvent, NotificationType
from apps.workouts.models import WorkoutPlan, WorkoutPlanAssignment


@pytest.mark.django_db
def test_send_reminders_creates_event_for_due_active_assignment():
    user_model = get_user_model()
    coach = user_model.objects.create_user(
        username="coach_reminder",
        email="coach_reminder@example.com",
        password="pw",
    )
    athlete = user_model.objects.create_user(
        username="athlete_reminder",
        email="athlete_reminder@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Reminder Plan",
        slug="reminder-plan",
        created_by=coach,
        is_published=True,
    )
    assignment = WorkoutPlanAssignment.objects.create(
        plan=plan,
        assigned_to=athlete,
        starts_on=timezone.localdate(),
        is_active=True,
    )

    call_command("send_reminders")

    event = NotificationEvent.objects.get(
        recipient=athlete,
        notification_type=NotificationType.REMINDER,
    )
    assert event.delivery_status == DeliveryStatus.PENDING
    assert event.payload["assignment_id"] == assignment.id


@pytest.mark.django_db
def test_send_reminders_skips_paused_or_ended_assignments():
    user_model = get_user_model()
    coach = user_model.objects.create_user(
        username="coach_skip",
        email="coach_skip@example.com",
        password="pw",
    )
    athlete = user_model.objects.create_user(
        username="athlete_skip",
        email="athlete_skip@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Skip Plan",
        slug="skip-plan",
        created_by=coach,
    )

    WorkoutPlanAssignment.objects.create(
        plan=plan,
        assigned_to=athlete,
        starts_on=timezone.localdate(),
        is_active=False,
        paused_at=timezone.now(),
    )
    WorkoutPlanAssignment.objects.create(
        plan=plan,
        assigned_to=athlete,
        starts_on=timezone.localdate(),
        is_active=True,
        ended_at=timezone.now(),
    )

    call_command("send_reminders")

    assert NotificationEvent.objects.filter(
        notification_type=NotificationType.REMINDER,
    ).count() == 0


@pytest.mark.django_db
def test_send_reminders_honors_days_ahead_and_avoids_duplicates_same_day():
    user_model = get_user_model()
    coach = user_model.objects.create_user(
        username="coach_future",
        email="coach_future@example.com",
        password="pw",
    )
    athlete = user_model.objects.create_user(
        username="athlete_future",
        email="athlete_future@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Future Plan",
        slug="future-plan",
        created_by=coach,
    )
    assignment = WorkoutPlanAssignment.objects.create(
        plan=plan,
        assigned_to=athlete,
        starts_on=timezone.localdate() + timedelta(days=2),
        is_active=True,
        recurs_every_days=7,
    )

    call_command("send_reminders", days_ahead=1)
    assert NotificationEvent.objects.filter(notification_type=NotificationType.REMINDER).count() == 0

    call_command("send_reminders", days_ahead=2)
    assert NotificationEvent.objects.filter(notification_type=NotificationType.REMINDER).count() == 1

    call_command("send_reminders", days_ahead=2)
    assert NotificationEvent.objects.filter(notification_type=NotificationType.REMINDER).count() == 1

    event = NotificationEvent.objects.get(notification_type=NotificationType.REMINDER)
    assert event.payload["assignment_id"] == assignment.id


@pytest.mark.django_db
def test_send_reminders_dry_run_creates_no_events():
    user_model = get_user_model()
    coach = user_model.objects.create_user(
        username="coach_dry",
        email="coach_dry@example.com",
        password="pw",
    )
    athlete = user_model.objects.create_user(
        username="athlete_dry",
        email="athlete_dry@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Dry Plan",
        slug="dry-plan",
        created_by=coach,
    )
    WorkoutPlanAssignment.objects.create(
        plan=plan,
        assigned_to=athlete,
        starts_on=timezone.localdate(),
        is_active=True,
    )

    call_command("send_reminders", dry_run=True)

    assert NotificationEvent.objects.filter(notification_type=NotificationType.REMINDER).count() == 0
