import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.workouts.models import Exercise, WorkoutPlan, WorkoutPlanType


@pytest.mark.django_db
def test_seed_curated_bundles_creates_expected_bundle_plans_and_challenge_days():
    user_model = get_user_model()
    creator = user_model.objects.create_user(
        username="bundle_creator",
        email="bundle_creator@example.com",
        password="pw",
    )

    call_command("seed_curated_bundles", created_by=creator.username)

    plan_slugs = {
        "bundle-warm-up-foundations",
        "bundle-calisthenics-base",
        "bundle-cooldown-reset",
        "bundle-30-day-abs",
        "bundle-30-day-lunge",
    }
    assert WorkoutPlan.objects.filter(slug__in=plan_slugs).count() == len(plan_slugs)

    abs_plan = WorkoutPlan.objects.get(slug="bundle-30-day-abs")
    lunge_plan = WorkoutPlan.objects.get(slug="bundle-30-day-lunge")
    assert abs_plan.plan_type == WorkoutPlanType.CHALLENGE
    assert lunge_plan.plan_type == WorkoutPlanType.CHALLENGE
    assert abs_plan.challenge_duration_days == 30
    assert lunge_plan.challenge_duration_days == 30
    assert abs_plan.challenge_days.count() == 30
    assert lunge_plan.challenge_days.count() == 30
    assert abs_plan.items.count() == 30
    assert lunge_plan.items.count() == 30

    checkpoint_count = abs_plan.challenge_days.filter(notes="Checkpoint").count()
    assert checkpoint_count == 6


@pytest.mark.django_db
def test_seed_curated_bundles_is_idempotent():
    user_model = get_user_model()
    creator = user_model.objects.create_user(
        username="bundle_idempotent_creator",
        email="bundle_idempotent_creator@example.com",
        password="pw",
    )

    call_command("seed_curated_bundles", created_by=creator.username)
    call_command("seed_curated_bundles", created_by=creator.username)

    assert WorkoutPlan.objects.filter(slug="bundle-30-day-abs").count() == 1
    assert WorkoutPlan.objects.filter(slug="bundle-30-day-lunge").count() == 1

    abs_plan = WorkoutPlan.objects.get(slug="bundle-30-day-abs")
    lunge_plan = WorkoutPlan.objects.get(slug="bundle-30-day-lunge")
    assert abs_plan.challenge_days.count() == 30
    assert lunge_plan.challenge_days.count() == 30
    assert abs_plan.items.count() == 30
    assert lunge_plan.items.count() == 30

    required_exercises = {
        "worlds-greatest-stretch",
        "inchworm-walkout",
        "scapular-push-up",
        "push-up",
        "bodyweight-squat",
        "hollow-hold",
        "child-pose-breathing",
        "supine-hamstring-stretch",
        "dead-bug",
        "plank",
        "forward-lunge",
        "reverse-lunge",
        "lateral-lunge",
    }
    assert Exercise.objects.filter(slug__in=required_exercises).count() == len(required_exercises)


@pytest.mark.django_db
def test_seed_curated_bundles_errors_for_unknown_creator():
    with pytest.raises(CommandError):
        call_command("seed_curated_bundles", created_by="missing-user")
