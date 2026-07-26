import csv
from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.communities.models import Community
from apps.progress.models import WorkoutLog
from apps.workouts.models import (
    Exercise,
    ExerciseBodyArea,
    ExerciseCategory,
    ExerciseMovementType,
    WorkoutChallengeDay,
    WorkoutChallengeDayCompletion,
    WorkoutPlan,
    WorkoutPlanAssignment,
    WorkoutPlanItem,
)


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


@pytest.mark.django_db
def test_progress_rpe_trend_compare_period_increases(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="trend_compare_up",
        email="trend_compare_up@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Trend Compare Up",
        slug="trend-compare-up",
        created_by=user,
        is_published=True,
    )
    now = timezone.now()

    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=8,
        completed_at=now - timedelta(days=3),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=7,
        completed_at=now - timedelta(days=6),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=5,
        completed_at=now - timedelta(days=10),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=4,
        completed_at=now - timedelta(days=13),
    )

    client.force_login(user)
    response = client.get(reverse("progress:logs"), {"trend_days": "7"})

    assert response.status_code == 200
    rpe_trend = response.context["rpe_trend"]
    compare = rpe_trend["compare"]
    assert compare["current_avg"] == pytest.approx(7.5)
    assert compare["previous_avg"] == pytest.approx(4.5)
    assert compare["delta"] == pytest.approx(3.0)
    assert compare["direction"] == "up"
    assert "Up vs previous" in response.content.decode()


@pytest.mark.django_db
def test_progress_rpe_trend_points_include_chart_heights(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="trend_chart_points",
        email="trend_chart_points@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Trend Chart",
        slug="trend-chart",
        created_by=user,
        is_published=True,
    )
    now = timezone.now()

    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=2,
        completed_at=now - timedelta(days=2),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=10,
        completed_at=now - timedelta(days=1),
    )

    client.force_login(user)
    response = client.get(reverse("progress:logs"), {"trend_days": "7"})

    assert response.status_code == 200
    points = response.context["rpe_trend"]["points"]
    assert points[0]["height_pct"] == 20
    assert points[1]["height_pct"] == 100
    content = response.content.decode()
    assert "height: 20%" in content
    assert "height: 100%" in content


@pytest.mark.django_db
def test_progress_logs_export_csv_respects_active_filters(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="export_logs_user",
        email="export_logs_user@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Export Logs Plan",
        slug="export-logs-plan",
        created_by=user,
        is_published=True,
    )

    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=8,
        notes="Recent export log",
        completed_at=timezone.now() - timedelta(days=2),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=5,
        notes="Older export log",
        completed_at=timezone.now() - timedelta(days=20),
    )

    client.force_login(user)
    response = client.get(reverse("progress:logs_export_csv"), {"days": "7"})

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment;" in response["Content-Disposition"]
    body = response.content.decode()
    assert "Recent export log" in body
    assert "Older export log" not in body


@pytest.mark.django_db
def test_progress_trend_export_csv_uses_trend_window(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="export_trend_user",
        email="export_trend_user@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Export Trend Plan",
        slug="export-trend-plan",
        created_by=user,
        is_published=True,
    )
    now = timezone.now()

    recent_log = WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=7,
        completed_at=now - timedelta(days=1),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=4,
        completed_at=now - timedelta(days=12),
    )

    client.force_login(user)
    response = client.get(reverse("progress:trend_export_csv"), {"trend_days": "7"})

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    rows = list(csv.DictReader(StringIO(response.content.decode())))
    assert len(rows) == 1
    assert rows[0]["day"] == str(recent_log.completed_at.date())
    assert float(rows[0]["avg_rpe"]) == pytest.approx(7.0)
    assert int(rows[0]["entry_count"]) == 1
    assert int(rows[0]["height_pct"]) == 70
    assert int(rows[0]["window_days"]) == 7


@pytest.mark.django_db
def test_progress_logs_show_challenge_kpis_with_adherence_streak_and_checkpoints(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="challenge_kpi_user",
        email="challenge_kpi_user@example.com",
        password="pw",
    )
    coach = user_model.objects.create_user(
        username="challenge_kpi_coach",
        email="challenge_kpi_coach@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Challenge KPI Plan",
        slug="challenge-kpi-plan",
        created_by=coach,
        plan_type="challenge",
        challenge_duration_days=5,
        challenge_focus_area="Core",
    )
    day_1 = WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=1,
        title="Day 1",
        target_duration_minutes=10,
    )
    day_2 = WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=2,
        title="Day 2",
        target_duration_minutes=10,
        notes="Checkpoint",
    )
    WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=3,
        title="Day 3",
        target_duration_minutes=10,
        notes="Checkpoint",
    )
    WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=4,
        title="Day 4",
        target_duration_minutes=10,
    )
    WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=5,
        title="Day 5",
        target_duration_minutes=10,
    )
    WorkoutPlanAssignment.objects.create(
        plan=plan,
        assigned_to=user,
        starts_on=timezone.localdate() - timedelta(days=2),
        is_active=True,
    )
    WorkoutChallengeDayCompletion.objects.create(
        challenge_day=day_1,
        completed_by=user,
        completed_minutes=10,
    )
    WorkoutChallengeDayCompletion.objects.create(
        challenge_day=day_2,
        completed_by=user,
        completed_minutes=10,
    )

    client.force_login(user)
    response = client.get(reverse("progress:logs"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Challenge KPIs" in content
    assert "66.7% (2/3 days)" in content
    assert "Current 0 • Best 2" in content
    assert "Baseline 100.0%" in content
    assert "Current 0.0%" in content
    assert "Delta -100.0%" in content
    assert "Checkpoint Deltas" in content
    assert "Challenge KPI Plan • Day 2" in content
    assert "100.0%" in content
    assert "Day 3" in content
    assert "Delta -100.0%" in content


@pytest.mark.django_db
def test_progress_logs_show_empty_challenge_kpi_state_without_assignments(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="challenge_kpi_empty_user",
        email="challenge_kpi_empty_user@example.com",
        password="pw",
    )

    client.force_login(user)
    response = client.get(reverse("progress:logs"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Challenge KPIs" in content
    assert "No active challenge assignments yet for KPI tracking." in content


@pytest.mark.django_db
def test_progress_logs_show_body_area_and_movement_type_volume_summaries(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="volume_summary_user",
        email="volume_summary_user@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Volume Summary Plan",
        slug="volume-summary-plan",
        created_by=user,
        is_published=True,
    )
    push = Exercise.objects.create(
        name="Push Move",
        slug="push-move",
        category=ExerciseCategory.STRENGTH,
        movement_type=ExerciseMovementType.PUSH,
        primary_body_area=ExerciseBodyArea.UPPER_BODY,
        is_active=True,
    )
    pull = Exercise.objects.create(
        name="Pull Move",
        slug="pull-move",
        category=ExerciseCategory.STRENGTH,
        movement_type=ExerciseMovementType.PULL,
        primary_body_area=ExerciseBodyArea.BACK,
        is_active=True,
    )
    WorkoutPlanItem.objects.create(
        plan=plan,
        exercise=push,
        order=1,
        duration_minutes=5,
    )
    WorkoutPlanItem.objects.create(
        plan=plan,
        exercise=pull,
        order=2,
        duration_minutes=2,
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        completed_at=timezone.now() - timedelta(days=1),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        completed_at=timezone.now() - timedelta(days=2),
    )

    client.force_login(user)
    response = client.get(reverse("progress:logs"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Volume Summaries" in content
    assert "Movement Type Volume" in content
    assert "Body Area Volume" in content
    assert "Push • 10 pts" in content
    assert "Pull • 4 pts" in content
    assert "Upper body • 10 pts" in content
    assert "Back • 4 pts" in content


@pytest.mark.django_db
def test_progress_logs_show_empty_volume_summary_state_for_unplanned_logs(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="volume_summary_empty_user",
        email="volume_summary_empty_user@example.com",
        password="pw",
    )
    WorkoutLog.objects.create(
        performed_by=user,
        notes="Unplanned session",
        completed_at=timezone.now() - timedelta(days=1),
    )

    client.force_login(user)
    response = client.get(reverse("progress:logs"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Volume Summaries" in content
    assert "No logged plan volume yet for movement-type or body-area summaries." in content


@pytest.mark.django_db
def test_progress_logs_show_load_safety_alerts_for_spike_and_high_rpe_streak(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="load_alerts_user",
        email="load_alerts_user@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Load Alerts Plan",
        slug="load-alerts-plan",
        created_by=user,
        is_published=True,
    )
    now = timezone.now()

    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=5,
        completed_at=now - timedelta(days=12),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=5,
        completed_at=now - timedelta(days=10),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=9,
        completed_at=now - timedelta(days=3),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=8,
        completed_at=now - timedelta(days=2),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=9,
        completed_at=now - timedelta(days=1),
    )

    client.force_login(user)
    response = client.get(reverse("progress:logs"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Load-Safety Alerts" in content
    assert "Abrupt load spike" in content
    assert "Sustained high RPE streak" in content
    assert "3 consecutive logs at RPE 8+" in content
    assert "Educational signal only, not medical advice." in content


@pytest.mark.django_db
def test_progress_logs_show_no_load_safety_alert_message_when_signals_absent(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="load_alerts_empty_user",
        email="load_alerts_empty_user@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Load Alerts Empty Plan",
        slug="load-alerts-empty-plan",
        created_by=user,
        is_published=True,
    )
    now = timezone.now()

    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=6,
        completed_at=now - timedelta(days=5),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=6,
        completed_at=now - timedelta(days=3),
    )
    WorkoutLog.objects.create(
        plan=plan,
        performed_by=user,
        perceived_exertion=7,
        completed_at=now - timedelta(days=1),
    )

    client.force_login(user)
    response = client.get(reverse("progress:logs"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Load-Safety Alerts" in content
    assert "No load-safety alerts in the selected window." in content
    assert "Educational only and non-diagnostic." in content
    assert "Trend patterns are educational signals and not a diagnosis." in content
