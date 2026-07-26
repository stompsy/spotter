import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.progress.models import WorkoutLog
from apps.workouts.models import WorkoutPlan, WorkoutPlanAssignment


@pytest.mark.django_db
def test_workout_logs_view_requires_authentication(client):
    response = client.get(reverse("progress:logs"))
    assert response.status_code == 302
    assert reverse("account_login") in response.url


@pytest.mark.django_db
def test_authenticated_user_can_create_workout_log_from_assigned_plan(client):
    user_model = get_user_model()
    coach = user_model.objects.create_user(
        username="log_coach",
        email="log_coach@example.com",
        password="pw",
    )
    athlete = user_model.objects.create_user(
        username="log_athlete",
        email="log_athlete@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Assigned Plan",
        slug="assigned-plan",
        created_by=coach,
        is_published=True,
    )
    WorkoutPlanAssignment.objects.create(
        plan=plan,
        assigned_to=athlete,
        is_active=True,
    )

    client.force_login(athlete)
    response = client.post(
        reverse("progress:logs"),
        {
            "plan": plan.id,
            "perceived_exertion": 8,
            "notes": "Felt strong throughout.",
        },
    )

    assert response.status_code == 302
    log = WorkoutLog.objects.get(performed_by=athlete)
    assert log.plan_id == plan.id
    assert log.perceived_exertion == 8
    assert log.notes == "Felt strong throughout."


@pytest.mark.django_db
def test_workout_logs_view_shows_only_current_users_logs(client):
    user_model = get_user_model()
    me = user_model.objects.create_user(
        username="log_me",
        email="log_me@example.com",
        password="pw",
    )
    other = user_model.objects.create_user(
        username="log_other",
        email="log_other@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Visibility Plan",
        slug="visibility-plan",
        created_by=me,
        is_published=True,
    )

    my_log = WorkoutLog.objects.create(
        plan=plan,
        performed_by=me,
        perceived_exertion=6,
        notes="Mine",
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=other,
        perceived_exertion=4,
        notes="Not mine",
    )

    client.force_login(me)
    response = client.get(reverse("progress:logs"))

    assert response.status_code == 200
    logs = list(response.context["logs"])
    assert logs == [my_log]
    content = response.content.decode()
    assert "Mine" in content
    assert "Not mine" not in content
