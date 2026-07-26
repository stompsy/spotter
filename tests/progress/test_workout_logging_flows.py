from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.communities.models import Community
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


@pytest.mark.django_db
def test_progress_insights_show_recent_counts_rpe_average_and_communities(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="insights_user",
        email="insights_user@example.com",
        password="pw",
    )
    community_a = Community.objects.create(
        name="Insights A",
        slug="insights-a",
        created_by=user,
    )
    community_b = Community.objects.create(
        name="Insights B",
        slug="insights-b",
        created_by=user,
    )
    plan = WorkoutPlan.objects.create(
        name="Insights Plan",
        slug="insights-plan",
        created_by=user,
        is_published=True,
    )
    now = timezone.now()
    WorkoutLog.objects.create(
        plan=plan,
        community=community_a,
        performed_by=user,
        perceived_exertion=7,
        completed_at=now - timedelta(days=3),
    )
    WorkoutLog.objects.create(
        plan=plan,
        community=community_b,
        performed_by=user,
        perceived_exertion=9,
        completed_at=now - timedelta(days=8),
    )
    WorkoutLog.objects.create(
        plan=plan,
        community=community_a,
        performed_by=user,
        perceived_exertion=None,
        completed_at=now - timedelta(days=20),
    )
    WorkoutLog.objects.create(
        plan=plan,
        community=community_b,
        performed_by=user,
        perceived_exertion=5,
        completed_at=now - timedelta(days=45),
    )

    client.force_login(user)
    response = client.get(reverse("progress:logs"))

    assert response.status_code == 200
    insights = response.context["insights"]
    assert insights["total_logs"] == 4
    assert insights["recent_logs_7d"] == 1
    assert insights["active_communities_30d"] == 2
    assert insights["avg_rpe_14d"] == pytest.approx(8.0)


@pytest.mark.django_db
def test_progress_insights_show_none_when_recent_rpe_missing(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="insights_no_rpe",
        email="insights_no_rpe@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="No RPE Plan",
        slug="no-rpe-plan",
        created_by=user,
        is_published=True,
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=None,
        completed_at=timezone.now() - timedelta(days=2),
    )

    client.force_login(user)
    response = client.get(reverse("progress:logs"))

    assert response.status_code == 200
    insights = response.context["insights"]
    assert insights["avg_rpe_14d"] is None
    assert "No RPE yet" in response.content.decode()


@pytest.mark.django_db
def test_workout_logs_filter_by_date_window(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="filter_window",
        email="filter_window@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Window Plan",
        slug="window-plan",
        created_by=user,
        is_published=True,
    )
    recent_log = WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        notes="Recent",
        completed_at=timezone.now() - timedelta(days=3),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        notes="Older",
        completed_at=timezone.now() - timedelta(days=12),
    )

    client.force_login(user)
    response = client.get(reverse("progress:logs"), {"days": "7"})

    assert response.status_code == 200
    logs = list(response.context["logs"])
    assert logs == [recent_log]
    content = response.content.decode()
    assert "Recent" in content
    assert "Older" not in content


@pytest.mark.django_db
def test_workout_logs_filter_by_plan_and_community(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="filter_scope",
        email="filter_scope@example.com",
        password="pw",
    )
    community_a = Community.objects.create(
        name="Scope A",
        slug="scope-a",
        created_by=user,
    )
    community_b = Community.objects.create(
        name="Scope B",
        slug="scope-b",
        created_by=user,
    )
    plan_a = WorkoutPlan.objects.create(
        name="Scope Plan A",
        slug="scope-plan-a",
        created_by=user,
        community=community_a,
        is_published=True,
    )
    plan_b = WorkoutPlan.objects.create(
        name="Scope Plan B",
        slug="scope-plan-b",
        created_by=user,
        community=community_b,
        is_published=True,
    )
    match_log = WorkoutLog.objects.create(
        plan=plan_a,
        community=community_a,
        performed_by=user,
        notes="Match",
    )
    WorkoutLog.objects.create(
        plan=plan_b,
        community=community_b,
        performed_by=user,
        notes="Other",
    )

    client.force_login(user)
    response = client.get(
        reverse("progress:logs"),
        {
            "plan": str(plan_a.id),
            "community": str(community_a.id),
        },
    )

    assert response.status_code == 200
    logs = list(response.context["logs"])
    assert logs == [match_log]
    content = response.content.decode()
    assert "Match" in content
    assert "Other" not in content


@pytest.mark.django_db
def test_progress_rpe_trend_shows_daily_averages_within_window(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="trend_user",
        email="trend_user@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Trend Plan",
        slug="trend-plan",
        created_by=user,
        is_published=True,
    )
    now = timezone.now()

    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=6,
        completed_at=now - timedelta(days=1),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=8,
        completed_at=now - timedelta(days=1, hours=2),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=5,
        completed_at=now - timedelta(days=4),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=9,
        completed_at=now - timedelta(days=21),
    )

    client.force_login(user)
    response = client.get(reverse("progress:logs"), {"trend_days": "7"})

    assert response.status_code == 200
    rpe_trend = response.context["rpe_trend"]
    assert rpe_trend["window_days"] == 7
    points = rpe_trend["points"]
    assert len(points) == 2
    assert points[0]["avg_rpe"] == pytest.approx(5.0)
    assert points[1]["avg_rpe"] == pytest.approx(7.0)
    assert points[1]["entry_count"] == 2


@pytest.mark.django_db
def test_progress_rpe_trend_handles_no_recent_rpe_data(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="trend_empty",
        email="trend_empty@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Trend Empty Plan",
        slug="trend-empty-plan",
        created_by=user,
        is_published=True,
    )

    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=None,
        completed_at=timezone.now() - timedelta(days=2),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=7,
        completed_at=timezone.now() - timedelta(days=40),
    )

    client.force_login(user)
    response = client.get(reverse("progress:logs"), {"trend_days": "14"})

    assert response.status_code == 200
    rpe_trend = response.context["rpe_trend"]
    assert rpe_trend["window_days"] == 14
    assert rpe_trend["points"] == []
    assert "No recent trend data" in response.content.decode()
