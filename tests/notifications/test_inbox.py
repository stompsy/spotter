import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.notifications.models import NotificationEvent, NotificationType


@pytest.mark.django_db
def test_inbox_requires_authentication(client):
    response = client.get(reverse("notifications:inbox"))
    assert response.status_code == 302
    assert reverse("account_login") in response.url


@pytest.mark.django_db
def test_inbox_shows_only_current_user_events(client):
    user_model = get_user_model()
    me = user_model.objects.create_user(
        username="me",
        email="me@example.com",
        password="pw",
    )
    other = user_model.objects.create_user(
        username="other",
        email="other@example.com",
        password="pw",
    )

    mine = NotificationEvent.objects.create(
        recipient=me,
        notification_type=NotificationType.JOIN_REQUEST,
        subject="My event",
        body="Mine",
    )
    NotificationEvent.objects.create(
        recipient=other,
        notification_type=NotificationType.JOIN_REQUEST,
        subject="Other event",
        body="Not mine",
    )

    client.force_login(me)
    response = client.get(reverse("notifications:inbox"))

    assert response.status_code == 200
    events = list(response.context["notifications"])
    assert events == [mine]
    assert "My event" in response.content.decode()
    assert "Other event" not in response.content.decode()
    assert response.context["unread_notifications_count"] == 1


@pytest.mark.django_db
def test_mark_single_notification_read(client):
    user_model = get_user_model()
    me = user_model.objects.create_user(
        username="me2",
        email="me2@example.com",
        password="pw",
    )
    event = NotificationEvent.objects.create(
        recipient=me,
        notification_type=NotificationType.JOIN_REQUEST,
        subject="Unread event",
    )

    client.force_login(me)
    response = client.post(
        reverse("notifications:mark_read", kwargs={"event_id": event.id}),
    )

    assert response.status_code == 302
    event.refresh_from_db()
    assert event.read_at is not None


@pytest.mark.django_db
def test_mark_all_notifications_read(client):
    user_model = get_user_model()
    me = user_model.objects.create_user(
        username="me3",
        email="me3@example.com",
        password="pw",
    )
    NotificationEvent.objects.create(
        recipient=me,
        notification_type=NotificationType.JOIN_REQUEST,
        subject="Unread event 1",
    )
    NotificationEvent.objects.create(
        recipient=me,
        notification_type=NotificationType.JOIN_DECISION,
        subject="Unread event 2",
    )

    client.force_login(me)
    response = client.post(reverse("notifications:mark_all_read"))

    assert response.status_code == 302
    assert NotificationEvent.objects.filter(recipient=me, read_at__isnull=True).count() == 0


@pytest.mark.django_db
def test_mark_read_disallows_other_user_event(client):
    user_model = get_user_model()
    me = user_model.objects.create_user(
        username="me4",
        email="me4@example.com",
        password="pw",
    )
    other = user_model.objects.create_user(
        username="other4",
        email="other4@example.com",
        password="pw",
    )
    event = NotificationEvent.objects.create(
        recipient=other,
        notification_type=NotificationType.JOIN_REQUEST,
        subject="Other unread",
    )

    client.force_login(me)
    response = client.post(
        reverse("notifications:mark_read", kwargs={"event_id": event.id}),
    )

    assert response.status_code == 404
    event.refresh_from_db()
    assert event.read_at is None
