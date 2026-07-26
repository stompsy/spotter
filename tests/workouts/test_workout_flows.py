from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.communities.models import Community, CommunityMembership, MembershipRole, MembershipStatus
from apps.workouts.models import (
    CurationStatus,
    Exercise,
    ExerciseBodyArea,
    ExerciseCandidate,
    ExerciseCategory,
    ExerciseDifficultyLevel,
    ExerciseDurationFit,
    ExerciseEquipmentRequirement,
    ExerciseMedia,
    ExerciseMovementType,
    ExerciseSource,
    ExerciseSourceType,
    WorkoutChallengeDay,
    WorkoutPlan,
    WorkoutPlanAssignment,
    WorkoutPlanItem,
    WorkoutPlanPhase,
)


@pytest.mark.django_db
def test_authenticated_user_can_create_workout_plan(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="plan_owner",
        email="plan_owner@example.com",
        password="pw",
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:list"),
        {
            "name": "Sprint Builder",
            "description": "Lower body and mobility focus",
            "is_template": "on",
            "is_published": "on",
        },
    )

    assert response.status_code == 302
    plan = WorkoutPlan.objects.get(name="Sprint Builder")
    assert plan.created_by_id == user.id
    assert plan.is_template is True


@pytest.mark.django_db
def test_user_can_create_challenge_workout_plan_with_semantics(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="challenge_plan_owner",
        email="challenge_plan_owner@example.com",
        password="pw",
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:list"),
        {
            "name": "Lunge Ladder",
            "description": "Challenge progression",
            "plan_type": "challenge",
            "duration_band": "medium",
            "challenge_duration_days": "30",
            "challenge_focus_area": "Lower body",
            "is_template": "on",
        },
    )

    assert response.status_code == 302
    plan = WorkoutPlan.objects.get(name="Lunge Ladder")
    assert plan.plan_type == "challenge"
    assert plan.duration_band == "medium"
    assert plan.challenge_duration_days == 30
    assert plan.challenge_focus_area == "Lower body"


@pytest.mark.django_db
def test_challenge_plan_requires_duration_and_focus(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="challenge_validation_owner",
        email="challenge_validation_owner@example.com",
        password="pw",
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:list"),
        {
            "name": "Broken Challenge",
            "description": "Missing challenge fields",
            "plan_type": "challenge",
            "duration_band": "short",
            "challenge_duration_days": "",
            "challenge_focus_area": "",
        },
    )

    assert response.status_code == 400
    content = response.content.decode("utf-8")
    assert "Challenge duration is required for challenge plans." in content
    assert "Challenge focus area is required for challenge plans." in content


@pytest.mark.django_db
def test_workout_plan_list_displays_challenge_preset_controls(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="preset_view_user",
        email="preset_view_user@example.com",
        password="pw",
    )

    client.force_login(user)
    response = client.get(reverse("workouts:list"))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Copy-safe starter challenges" in content
    assert "30-Day Core Challenge" in content
    assert "30-Day Lunge Challenge" in content


@pytest.mark.django_db
def test_workout_plan_list_displays_challenge_wizard_controls(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="wizard_view_user",
        email="wizard_view_user@example.com",
        password="pw",
    )

    client.force_login(user)
    response = client.get(reverse("workouts:list"))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Challenge wizard" in content
    assert "Build a custom challenge" in content
    assert "Progression style" in content


@pytest.mark.django_db
def test_user_can_create_challenge_plan_from_wizard(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="wizard_creator",
        email="wizard_creator@example.com",
        password="pw",
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:list"),
        {
            "action": "challenge_wizard",
            "focus_area": "Shoulders",
            "duration_days": "14",
            "progression_style": "step",
            "checkpoint_interval_days": "7",
        },
    )

    assert response.status_code == 302
    plan = WorkoutPlan.objects.get(name="14-Day Shoulders Challenge")
    assert plan.plan_type == "challenge"
    assert plan.duration_band == "short"
    assert plan.challenge_duration_days == 14
    assert plan.challenge_focus_area == "Shoulders"
    assert plan.challenge_days.count() == 14
    checkpoint_days = plan.challenge_days.filter(notes__icontains="Checkpoint").order_by(
        "day_number"
    )
    assert list(checkpoint_days.values_list("day_number", flat=True)) == [7, 14]


@pytest.mark.django_db
def test_challenge_wizard_rejects_invalid_duration_days(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="wizard_invalid_duration",
        email="wizard_invalid_duration@example.com",
        password="pw",
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:list"),
        {
            "action": "challenge_wizard",
            "focus_area": "Core",
            "duration_days": "4",
            "progression_style": "linear",
            "checkpoint_interval_days": "7",
        },
    )

    assert response.status_code == 400
    content = response.content.decode("utf-8")
    assert "Ensure this value is greater than or equal to 7." in content


@pytest.mark.django_db
def test_user_can_create_core_challenge_preset_from_plan_list(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="core_preset_owner",
        email="core_preset_owner@example.com",
        password="pw",
    )

    client.force_login(user)
    response = client.post(reverse("workouts:list"), {"preset_key": "abs_30_day"})

    assert response.status_code == 302
    plan = WorkoutPlan.objects.get(name="30-Day Core Challenge")
    assert plan.created_by_id == user.id
    assert plan.plan_type == "challenge"
    assert plan.challenge_duration_days == 30
    assert plan.challenge_focus_area == "Core"
    assert plan.is_template is True
    assert plan.challenge_days.count() == 30
    assert plan.items.count() == 30
    assert plan.items.filter(challenge_day__isnull=False).count() == 30
    assert Exercise.objects.filter(name="Hollow Hold").exists()


@pytest.mark.django_db
def test_user_can_create_lunge_challenge_preset_and_view_day_linked_items(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="lunge_preset_owner",
        email="lunge_preset_owner@example.com",
        password="pw",
    )

    client.force_login(user)
    create_response = client.post(reverse("workouts:list"), {"preset_key": "lunge_30_day"})

    assert create_response.status_code == 302
    plan = WorkoutPlan.objects.get(name="30-Day Lunge Challenge")
    assert plan.challenge_days.count() == 30
    assert plan.items.count() == 30

    detail_response = client.get(reverse("workouts:detail", kwargs={"slug": plan.slug}))

    assert detail_response.status_code == 200
    content = detail_response.content.decode("utf-8")
    assert "Day 1: Foundation 1" in content
    assert "Bodyweight Lunge" in content
    assert "Day 1 priority" in content


@pytest.mark.django_db
def test_challenge_day_can_be_created_for_challenge_plan():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="challenge_day_owner",
        email="challenge_day_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Challenge Day Plan",
        slug="challenge-day-plan",
        created_by=user,
        plan_type="challenge",
        duration_band="medium",
        challenge_duration_days=21,
        challenge_focus_area="Core",
    )

    day = WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=1,
        title="Foundation",
        focus_area="Core",
        target_duration_minutes=20,
    )

    assert day.plan_id == plan.id
    assert day.day_number == 1


@pytest.mark.django_db
def test_challenge_day_rejects_non_challenge_plan():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="non_challenge_day_owner",
        email="non_challenge_day_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Single Session Plan",
        slug="single-session-plan",
        created_by=user,
        plan_type="single_session",
        duration_band="short",
    )

    with pytest.raises(ValidationError, match="Challenge days can only be added"):
        WorkoutChallengeDay.objects.create(
            plan=plan,
            day_number=1,
            title="Invalid day",
        )


@pytest.mark.django_db
def test_challenge_day_rejects_day_number_beyond_challenge_duration():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="duration_limit_owner",
        email="duration_limit_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Two Day Challenge",
        slug="two-day-challenge",
        created_by=user,
        plan_type="challenge",
        duration_band="short",
        challenge_duration_days=2,
        challenge_focus_area="Lower body",
    )

    with pytest.raises(ValidationError, match="cannot exceed the plan challenge duration"):
        WorkoutChallengeDay.objects.create(
            plan=plan,
            day_number=3,
            title="Too far",
        )


@pytest.mark.django_db
def test_detail_view_shows_challenge_days_section(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="challenge_day_view_owner",
        email="challenge_day_view_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Visibility Challenge",
        slug="visibility-challenge",
        created_by=user,
        plan_type="challenge",
        duration_band="medium",
        challenge_duration_days=14,
        challenge_focus_area="Mobility",
    )
    WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=1,
        title="Start Strong",
        focus_area="Mobility",
        target_duration_minutes=15,
    )

    client.force_login(user)
    response = client.get(reverse("workouts:detail", kwargs={"slug": plan.slug}))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Challenge days" in content
    assert "Day 1: Start Strong" in content


@pytest.mark.django_db
def test_program_phase_can_be_created_for_program_plan():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="program_phase_owner",
        email="program_phase_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Tri Phase Plan",
        slug="tri-phase-plan",
        created_by=user,
        plan_type="program",
        duration_band="long",
    )

    phase = WorkoutPlanPhase.objects.create(
        plan=plan,
        phase_number=1,
        name="Base Build",
        focus_area="Capacity",
        week_start=1,
        week_end=4,
    )

    assert phase.plan_id == plan.id
    assert phase.phase_number == 1


@pytest.mark.django_db
def test_program_phase_rejects_non_program_plan():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="non_program_phase_owner",
        email="non_program_phase_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Single Session Builder",
        slug="single-session-builder",
        created_by=user,
        plan_type="single_session",
        duration_band="medium",
    )

    with pytest.raises(ValidationError, match="Phases can only be added to program plans"):
        WorkoutPlanPhase.objects.create(
            plan=plan,
            phase_number=1,
            name="Invalid Phase",
        )


@pytest.mark.django_db
def test_program_phase_rejects_invalid_week_range():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="phase_range_owner",
        email="phase_range_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Periodized Builder",
        slug="periodized-builder",
        created_by=user,
        plan_type="program",
        duration_band="long",
    )

    with pytest.raises(ValidationError, match="week end must be greater than or equal"):
        WorkoutPlanPhase.objects.create(
            plan=plan,
            phase_number=1,
            name="Backwards Phase",
            week_start=5,
            week_end=3,
        )


@pytest.mark.django_db
def test_detail_view_shows_program_phases_section(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="program_phase_view_owner",
        email="program_phase_view_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Program Visibility",
        slug="program-visibility",
        created_by=user,
        plan_type="program",
        duration_band="long",
    )
    WorkoutPlanPhase.objects.create(
        plan=plan,
        phase_number=1,
        name="Base Build",
        focus_area="Strength",
        week_start=1,
        week_end=4,
    )

    client.force_login(user)
    response = client.get(reverse("workouts:detail", kwargs={"slug": plan.slug}))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Program phases" in content
    assert "Phase 1: Base Build" in content


@pytest.mark.django_db
def test_plan_creator_can_add_item(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="item_owner",
        email="item_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Hill Prep",
        slug="hill-prep",
        description="",
        created_by=user,
    )
    exercise = Exercise.objects.create(
        name="Band Walk",
        slug="band-walk",
        category=ExerciseCategory.MOVEMENT_PREPARATION,
        is_active=True,
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:add_item", kwargs={"slug": plan.slug}),
        {
            "exercise": exercise.id,
            "repetitions": "3x12",
            "duration_minutes": "",
            "notes": "Control tempo",
        },
    )

    assert response.status_code == 302
    item = WorkoutPlanItem.objects.get(plan=plan)
    assert item.exercise_id == exercise.id
    assert item.order == 1


@pytest.mark.django_db
def test_plan_detail_shows_guided_composer_for_manager(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="composer_owner",
        email="composer_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Composer Plan",
        slug="composer-plan",
        description="",
        created_by=user,
    )

    client.force_login(user)
    response = client.get(reverse("workouts:detail", kwargs={"slug": plan.slug}))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Guided Composer" in content
    assert "Suggested Starter" in content
    assert "Short Session Starter" in content


@pytest.mark.django_db
def test_plan_manager_can_apply_guided_short_template(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="composer_apply_owner",
        email="composer_apply_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Composer Apply Plan",
        slug="composer-apply-plan",
        description="",
        created_by=user,
    )
    Exercise.objects.create(
        name="Short A",
        slug="short-a",
        category=ExerciseCategory.MOVEMENT_PREPARATION,
        duration_fit=ExerciseDurationFit.SHORT,
        is_active=True,
    )
    Exercise.objects.create(
        name="Short B",
        slug="short-b",
        category=ExerciseCategory.MOVEMENT_PREPARATION,
        duration_fit=ExerciseDurationFit.SHORT,
        is_active=True,
    )
    Exercise.objects.create(
        name="Short C",
        slug="short-c",
        category=ExerciseCategory.MOVEMENT_PREPARATION,
        duration_fit=ExerciseDurationFit.SHORT,
        is_active=True,
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:compose_template", kwargs={"slug": plan.slug}),
        {"template_key": "starter_short"},
    )

    assert response.status_code == 302
    items = list(plan.items.order_by("order"))
    assert len(items) == 3
    assert items[0].order == 1
    assert items[1].order == 2
    assert items[2].order == 3
    assert all(item.notes == "Guided composer template item." for item in items)


@pytest.mark.django_db
def test_challenge_plan_manager_can_apply_challenge_day_template(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="challenge_composer_owner",
        email="challenge_composer_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Challenge Composer Plan",
        slug="challenge-composer-plan",
        description="",
        created_by=user,
        plan_type="challenge",
        duration_band="short",
        challenge_duration_days=7,
        challenge_focus_area="Core",
    )
    day = WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=1,
        title="Day One",
        focus_area="Core",
        target_duration_minutes=8,
    )
    Exercise.objects.create(
        name="Core Starter A",
        slug="core-starter-a",
        category=ExerciseCategory.CORE_STABILITY,
        movement_type=ExerciseMovementType.CORE,
        primary_body_area=ExerciseBodyArea.CORE,
        duration_fit=ExerciseDurationFit.SHORT,
        is_active=True,
    )
    Exercise.objects.create(
        name="Core Starter B",
        slug="core-starter-b",
        category=ExerciseCategory.CORE_STABILITY,
        movement_type=ExerciseMovementType.CORE,
        primary_body_area=ExerciseBodyArea.CORE,
        duration_fit=ExerciseDurationFit.SHORT,
        is_active=True,
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:compose_template", kwargs={"slug": plan.slug}),
        {"template_key": "challenge_day_starter"},
    )

    assert response.status_code == 302
    items = list(plan.items.order_by("order"))
    assert len(items) == 2
    assert all(item.challenge_day_id == day.id for item in items)
    assert all("Guided challenge day template" in item.notes for item in items)


@pytest.mark.django_db
def test_challenge_plan_detail_shows_validation_issues_when_structure_is_unbalanced(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="validation_issue_owner",
        email="validation_issue_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Validation Issue Challenge",
        slug="validation-issue-challenge",
        created_by=user,
        plan_type="challenge",
        duration_band="short",
        challenge_duration_days=3,
        challenge_focus_area="Core",
    )
    day = WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=1,
        title="Day One",
        focus_area="Core",
        target_duration_minutes=12,
    )
    exercise = Exercise.objects.create(
        name="Single Focus Move",
        slug="single-focus-move",
        category=ExerciseCategory.CORE_STABILITY,
        movement_type=ExerciseMovementType.CORE,
        primary_body_area=ExerciseBodyArea.CORE,
        is_active=True,
    )
    WorkoutPlanItem.objects.create(
        plan=plan,
        challenge_day=day,
        exercise=exercise,
        order=1,
        repetitions="3 x 10",
    )

    client.force_login(user)
    response = client.get(reverse("workouts:detail", kwargs={"slug": plan.slug}))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Resolve the following before publishing" in content
    assert "Warm-up coverage is required" in content
    assert "Cooldown coverage is required" in content


@pytest.mark.django_db
def test_challenge_plan_publish_is_blocked_until_validation_rules_pass(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="validation_publish_owner",
        email="validation_publish_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Validation Publish Challenge",
        slug="validation-publish-challenge",
        created_by=user,
        plan_type="challenge",
        duration_band="short",
        challenge_duration_days=2,
        challenge_focus_area="Full body",
        is_published=False,
    )
    day_1 = WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=1,
        title="Day One",
        focus_area="Core",
        target_duration_minutes=12,
    )
    day_2 = WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=2,
        title="Day Two",
        focus_area="Lower body",
        target_duration_minutes=12,
    )

    warmup = Exercise.objects.create(
        name="Prep Flow",
        slug="prep-flow",
        category=ExerciseCategory.MOVEMENT_PREPARATION,
        movement_type=ExerciseMovementType.MOBILITY,
        primary_body_area=ExerciseBodyArea.FULL_BODY,
        is_active=True,
    )
    core = Exercise.objects.create(
        name="Core Bracing",
        slug="core-bracing",
        category=ExerciseCategory.CORE_STABILITY,
        movement_type=ExerciseMovementType.CORE,
        primary_body_area=ExerciseBodyArea.CORE,
        is_active=True,
    )

    WorkoutPlanItem.objects.create(
        plan=plan,
        challenge_day=day_1,
        exercise=warmup,
        order=1,
        repetitions="3 x 8",
    )
    WorkoutPlanItem.objects.create(
        plan=plan,
        challenge_day=day_2,
        exercise=core,
        order=2,
        repetitions="3 x 8",
    )

    client.force_login(user)
    blocked_response = client.post(
        reverse("workouts:publish_toggle", kwargs={"slug": plan.slug}),
    )
    assert blocked_response.status_code == 302
    plan.refresh_from_db()
    assert plan.is_published is False

    cooldown = Exercise.objects.create(
        name="Cooldown Breath",
        slug="cooldown-breath",
        category=ExerciseCategory.POST_WORKOUT_REGENERATION,
        movement_type=ExerciseMovementType.MOBILITY,
        primary_body_area=ExerciseBodyArea.FULL_BODY,
        is_active=True,
    )
    WorkoutPlanItem.objects.create(
        plan=plan,
        challenge_day=day_2,
        exercise=cooldown,
        order=3,
        repetitions="2 x 5 breaths",
    )

    allowed_response = client.post(
        reverse("workouts:publish_toggle", kwargs={"slug": plan.slug}),
    )
    assert allowed_response.status_code == 302
    plan.refresh_from_db()
    assert plan.is_published is True


@pytest.mark.django_db
def test_challenge_detail_shows_split_completion_controls(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="split_controls_owner",
        email="split_controls_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Split Controls Challenge",
        slug="split-controls-challenge",
        description="",
        created_by=user,
        plan_type="challenge",
        duration_band="short",
        challenge_duration_days=7,
        challenge_focus_area="Core",
    )
    WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=1,
        title="Day One",
        focus_area="Core",
        target_duration_minutes=10,
    )

    client.force_login(user)
    response = client.get(reverse("workouts:detail", kwargs={"slug": plan.slug}))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Log Daily Completion" in content
    assert "Your progress: 0 / 10 min" in content
    assert "Status:" in content


@pytest.mark.django_db
def test_user_can_log_split_completion_until_daily_target_is_complete(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="split_logger",
        email="split_logger@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Split Logging Challenge",
        slug="split-logging-challenge",
        description="",
        created_by=user,
        plan_type="challenge",
        duration_band="short",
        challenge_duration_days=7,
        challenge_focus_area="Core",
    )
    day = WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=1,
        title="Day One",
        focus_area="Core",
        target_duration_minutes=10,
    )

    client.force_login(user)
    first_response = client.post(
        reverse("workouts:challenge_completion_add", kwargs={"slug": plan.slug}),
        {
            "challenge_day": day.id,
            "completed_minutes": "4",
            "notes": "Morning split",
        },
    )
    assert first_response.status_code == 302

    second_response = client.post(
        reverse("workouts:challenge_completion_add", kwargs={"slug": plan.slug}),
        {
            "challenge_day": day.id,
            "completed_minutes": "6",
            "notes": "Evening split",
        },
    )
    assert second_response.status_code == 302

    detail_response = client.get(reverse("workouts:detail", kwargs={"slug": plan.slug}))
    assert detail_response.status_code == 200
    content = detail_response.content.decode("utf-8")
    assert "Your progress: 10 / 10 min" in content
    assert "2 splits" in content
    assert "Status:" in content
    assert "Complete" in content


@pytest.mark.django_db
def test_suggested_starter_uses_plan_duration_band_when_fit_inventory_exists(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="suggested_medium_owner",
        email="suggested_medium_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Suggested Medium Plan",
        slug="suggested-medium-plan",
        description="",
        created_by=user,
        duration_band="medium",
    )
    for index in range(1, 6):
        Exercise.objects.create(
            name=f"Medium Starter {index}",
            slug=f"medium-starter-{index}",
            category=ExerciseCategory.MOVEMENT_PREPARATION,
            duration_fit=ExerciseDurationFit.MEDIUM,
            is_active=True,
        )

    client.force_login(user)
    response = client.post(
        reverse("workouts:compose_template", kwargs={"slug": plan.slug}),
        {"template_key": "starter_suggested"},
    )

    assert response.status_code == 302
    items = list(plan.items.order_by("order"))
    assert len(items) == 5
    assert all(item.repetitions == "3 x 10" for item in items)


@pytest.mark.django_db
def test_suggested_starter_falls_back_to_short_when_inventory_is_limited(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="suggested_fallback_owner",
        email="suggested_fallback_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Suggested Fallback Plan",
        slug="suggested-fallback-plan",
        description="",
        created_by=user,
        duration_band="long",
    )
    for index in range(1, 4):
        Exercise.objects.create(
            name=f"Fallback Starter {index}",
            slug=f"fallback-starter-{index}",
            category=ExerciseCategory.MOVEMENT_PREPARATION,
            duration_fit=ExerciseDurationFit.SHORT,
            is_active=True,
        )

    client.force_login(user)
    response = client.post(
        reverse("workouts:compose_template", kwargs={"slug": plan.slug}),
        {"template_key": "starter_suggested"},
    )

    assert response.status_code == 302
    items = list(plan.items.order_by("order"))
    assert len(items) == 3
    assert all(item.repetitions == "3 x 8" for item in items)


@pytest.mark.django_db
def test_plan_creator_can_assign_to_community(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="assign_owner",
        email="assign_owner@example.com",
        password="pw",
    )
    community = Community.objects.create(
        name="Tempo Crew",
        slug="tempo-crew",
        created_by=user,
    )
    CommunityMembership.objects.create(
        community=community,
        user=user,
        role=MembershipRole.OWNER,
        status=MembershipStatus.ACTIVE,
    )
    plan = WorkoutPlan.objects.create(
        name="Tempo Plan",
        slug="tempo-plan",
        description="",
        created_by=user,
        community=community,
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:assign", kwargs={"slug": plan.slug}),
        {
            "assigned_to": "",
            "assigned_community": community.id,
            "starts_on": "2026-07-30",
            "recurs_every_days": "7",
            "is_active": "on",
        },
    )

    assert response.status_code == 302
    assignment = WorkoutPlanAssignment.objects.get(plan=plan)
    assert assignment.assigned_community_id == community.id
    assert assignment.recurs_every_days == 7


@pytest.mark.django_db
def test_detail_view_shows_schedule_preview_for_active_recurring_assignment(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="schedule_preview_owner",
        email="schedule_preview_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Schedule Preview Plan",
        slug="schedule-preview-plan",
        description="",
        created_by=user,
    )
    starts_on = timezone.localdate() + timedelta(days=1)
    WorkoutPlanAssignment.objects.create(
        plan=plan,
        assigned_to=user,
        starts_on=starts_on,
        recurs_every_days=7,
        is_active=True,
    )

    client.force_login(user)
    response = client.get(reverse("workouts:detail", kwargs={"slug": plan.slug}))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Schedule Preview" in content
    assert starts_on.isoformat() in content
    assert "Scheduled session" in content
    assert "every 7 days" in content


@pytest.mark.django_db
def test_challenge_assignment_expands_challenge_days_into_schedule_preview(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="challenge_schedule_owner",
        email="challenge_schedule_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Challenge Schedule Plan",
        slug="challenge-schedule-plan",
        description="",
        created_by=user,
        plan_type="challenge",
        duration_band="short",
        challenge_duration_days=3,
        challenge_focus_area="Core",
    )
    WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=1,
        title="Foundation",
        focus_area="Core",
        target_duration_minutes=10,
    )
    WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=2,
        title="Build",
        focus_area="Core",
        target_duration_minutes=12,
    )
    WorkoutChallengeDay.objects.create(
        plan=plan,
        day_number=3,
        title="Finish",
        focus_area="Core",
        target_duration_minutes=14,
    )
    starts_on = timezone.localdate() + timedelta(days=1)
    WorkoutPlanAssignment.objects.create(
        plan=plan,
        assigned_to=user,
        starts_on=starts_on,
        is_active=True,
    )

    client.force_login(user)
    response = client.get(reverse("workouts:detail", kwargs={"slug": plan.slug}))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Schedule Preview" in content
    assert "Challenge day 1" in content
    assert "Challenge day 3" in content
    assert starts_on.isoformat() in content
    assert (starts_on + timedelta(days=2)).isoformat() in content


@pytest.mark.django_db
def test_user_can_create_and_archive_exercise(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="exercise_owner",
        email="exercise_owner@example.com",
        password="pw",
    )

    client.force_login(user)
    create_response = client.post(
        reverse("workouts:exercises"),
        {
            "name": "Lunge Matrix",
            "category": ExerciseCategory.STRENGTH,
            "movement_type": ExerciseMovementType.LUNGE,
            "primary_body_area": ExerciseBodyArea.LOWER_BODY,
            "difficulty_level": ExerciseDifficultyLevel.BEGINNER,
            "equipment_requirement": ExerciseEquipmentRequirement.NONE,
            "duration_fit": ExerciseDurationFit.SHORT,
            "description": "Multi-direction lunge prep",
            "instructions": "2 sets each direction",
            "contraindications": "Acute knee pain",
            "safety_notes": "Keep knee tracking over toes",
            "setup_steps": "Stand tall and brace core",
            "execution_steps": "Step, lower, return",
            "common_mistakes": "Knee collapse",
            "coaching_cues": "Drive through midfoot",
            "prescription_strength": "5x3 each side",
            "prescription_hypertrophy": "4x10 each side",
            "prescription_endurance": "3x20 each side",
            "is_active": "on",
        },
    )

    assert create_response.status_code == 302
    exercise = Exercise.objects.get(name="Lunge Matrix")
    assert exercise.is_active is True
    assert exercise.category == ExerciseCategory.STRENGTH
    assert exercise.movement_type == ExerciseMovementType.LUNGE
    assert exercise.primary_body_area == ExerciseBodyArea.LOWER_BODY
    assert exercise.difficulty_level == ExerciseDifficultyLevel.BEGINNER
    assert exercise.equipment_requirement == ExerciseEquipmentRequirement.NONE
    assert exercise.duration_fit == ExerciseDurationFit.SHORT
    assert exercise.contraindications == "Acute knee pain"
    assert exercise.safety_notes == "Keep knee tracking over toes"
    assert exercise.setup_steps == "Stand tall and brace core"
    assert exercise.execution_steps == "Step, lower, return"
    assert exercise.common_mistakes == "Knee collapse"
    assert exercise.coaching_cues == "Drive through midfoot"
    assert exercise.prescription_strength == "5x3 each side"
    assert exercise.prescription_hypertrophy == "4x10 each side"
    assert exercise.prescription_endurance == "3x20 each side"

    archive_response = client.post(
        reverse("workouts:exercise_toggle_active", kwargs={"exercise_id": exercise.id}),
    )
    assert archive_response.status_code == 302
    exercise.refresh_from_db()
    assert exercise.is_active is False


@pytest.mark.django_db
def test_user_can_update_exercise_taxonomy_fields(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="exercise_editor",
        email="exercise_editor@example.com",
        password="pw",
    )
    exercise = Exercise.objects.create(
        name="Push Press",
        slug="push-press",
        category=ExerciseCategory.CALISTHENICS,
        movement_type=ExerciseMovementType.PUSH,
        primary_body_area=ExerciseBodyArea.UPPER_BODY,
        difficulty_level=ExerciseDifficultyLevel.INTERMEDIATE,
        equipment_requirement=ExerciseEquipmentRequirement.STANDARD_GYM,
        description="Original",
        instructions="Original",
        contraindications="Original contraindications",
        safety_notes="Original safety",
        setup_steps="Original setup",
        execution_steps="Original execution",
        common_mistakes="Original mistakes",
        coaching_cues="Original cues",
        prescription_strength="Original strength",
        prescription_hypertrophy="Original hypertrophy",
        prescription_endurance="Original endurance",
        is_active=True,
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:exercise_edit", kwargs={"exercise_id": exercise.id}),
        {
            "name": "Push Press",
            "category": ExerciseCategory.SKILL_PRACTICE,
            "movement_type": ExerciseMovementType.PUSH,
            "primary_body_area": ExerciseBodyArea.SHOULDERS,
            "difficulty_level": ExerciseDifficultyLevel.ADVANCED,
            "equipment_requirement": ExerciseEquipmentRequirement.SPECIALIZED,
            "duration_fit": ExerciseDurationFit.MEDIUM,
            "description": "Updated",
            "instructions": "Updated",
            "contraindications": "Updated contraindications",
            "safety_notes": "Updated safety",
            "setup_steps": "Updated setup",
            "execution_steps": "Updated execution",
            "common_mistakes": "Updated mistakes",
            "coaching_cues": "Updated cues",
            "prescription_strength": "5x5",
            "prescription_hypertrophy": "4x12",
            "prescription_endurance": "3x25",
            "is_active": "on",
        },
    )

    assert response.status_code == 302
    exercise.refresh_from_db()
    assert exercise.category == ExerciseCategory.SKILL_PRACTICE
    assert exercise.primary_body_area == ExerciseBodyArea.SHOULDERS
    assert exercise.difficulty_level == ExerciseDifficultyLevel.ADVANCED
    assert exercise.equipment_requirement == ExerciseEquipmentRequirement.SPECIALIZED
    assert exercise.duration_fit == ExerciseDurationFit.MEDIUM
    assert exercise.contraindications == "Updated contraindications"
    assert exercise.safety_notes == "Updated safety"
    assert exercise.setup_steps == "Updated setup"
    assert exercise.execution_steps == "Updated execution"
    assert exercise.common_mistakes == "Updated mistakes"
    assert exercise.coaching_cues == "Updated cues"
    assert exercise.prescription_strength == "5x5"
    assert exercise.prescription_hypertrophy == "4x12"
    assert exercise.prescription_endurance == "3x25"


@pytest.mark.django_db
def test_user_can_add_external_media_to_exercise(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="exercise_media_editor",
        email="exercise_media_editor@example.com",
        password="pw",
    )
    exercise = Exercise.objects.create(
        name="Plank",
        slug="plank",
        category=ExerciseCategory.CALISTHENICS,
        is_active=True,
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:exercise_media_add", kwargs={"exercise_id": exercise.id}),
        {
            "media_type": "image",
            "external_url": "https://example.com/plank-image.jpg",
            "license_name": "CC BY 4.0",
            "attribution_text": "Photo by Example",
            "rights_notes": "Verified on source page",
        },
    )

    assert response.status_code == 302
    media_item = ExerciseMedia.objects.get(exercise=exercise)
    assert media_item.external_url == "https://example.com/plank-image.jpg"
    assert media_item.license_name == "CC BY 4.0"


@pytest.mark.django_db
def test_user_can_add_uploaded_media_to_exercise(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="exercise_media_uploader",
        email="exercise_media_uploader@example.com",
        password="pw",
    )
    exercise = Exercise.objects.create(
        name="Dead Bug",
        slug="dead-bug",
        category=ExerciseCategory.CALISTHENICS,
        is_active=True,
    )
    uploaded_file = SimpleUploadedFile(
        "dead-bug.txt",
        b"demo media",
        content_type="text/plain",
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:exercise_media_add", kwargs={"exercise_id": exercise.id}),
        {
            "media_type": "diagram",
            "file": uploaded_file,
            "license_name": "Internal use",
            "attribution_text": "Created by Spotter",
            "rights_notes": "Internal asset",
        },
    )

    assert response.status_code == 302
    media_item = ExerciseMedia.objects.get(exercise=exercise)
    assert media_item.file.name
    assert media_item.license_name == "Internal use"


@pytest.mark.django_db
def test_plan_creator_can_clone_and_publish_toggle_plan(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="clone_owner",
        email="clone_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="Template Plan",
        slug="template-plan",
        description="Starter",
        created_by=user,
        is_template=True,
        is_published=False,
    )
    exercise = Exercise.objects.create(
        name="Step Up",
        slug="step-up",
        category=ExerciseCategory.CALISTHENICS,
        is_active=True,
    )
    WorkoutPlanItem.objects.create(plan=plan, exercise=exercise, order=1, repetitions="3x8")

    client.force_login(user)
    clone_response = client.post(
        reverse("workouts:clone", kwargs={"slug": plan.slug}),
        {"clone_name": "Template Plan Copy"},
    )
    assert clone_response.status_code == 302

    cloned = WorkoutPlan.objects.get(name="Template Plan Copy")
    assert cloned.created_by_id == user.id
    assert cloned.items.count() == 1

    publish_response = client.post(
        reverse("workouts:publish_toggle", kwargs={"slug": plan.slug}),
    )
    assert publish_response.status_code == 302
    plan.refresh_from_db()
    assert plan.is_published is True


@pytest.mark.django_db
def test_plan_creator_can_pause_resume_and_end_assignment(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="state_owner",
        email="state_owner@example.com",
        password="pw",
    )
    plan = WorkoutPlan.objects.create(
        name="State Plan",
        slug="state-plan",
        description="",
        created_by=user,
    )
    target_user = user_model.objects.create_user(
        username="target_user",
        email="target_user@example.com",
        password="pw",
    )
    assignment = WorkoutPlanAssignment.objects.create(
        plan=plan,
        assigned_to=target_user,
        is_active=True,
    )

    client.force_login(user)
    pause_response = client.post(
        reverse(
            "workouts:assignment_state",
            kwargs={"slug": plan.slug, "assignment_id": assignment.id},
        ),
        {"action": "pause"},
    )
    assert pause_response.status_code == 302
    assignment.refresh_from_db()
    assert assignment.is_active is False
    assert assignment.paused_at is not None
    assert assignment.ended_at is None

    resume_response = client.post(
        reverse(
            "workouts:assignment_state",
            kwargs={"slug": plan.slug, "assignment_id": assignment.id},
        ),
        {"action": "resume"},
    )
    assert resume_response.status_code == 302
    assignment.refresh_from_db()
    assert assignment.is_active is True
    assert assignment.paused_at is None

    end_response = client.post(
        reverse(
            "workouts:assignment_state",
            kwargs={"slug": plan.slug, "assignment_id": assignment.id},
        ),
        {"action": "end"},
    )
    assert end_response.status_code == 302
    assignment.refresh_from_db()
    assert assignment.is_active is False
    assert assignment.ended_at is not None


@pytest.mark.django_db
def test_exercise_queue_filters_candidates_by_status_and_confidence(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="queue_reviewer",
        email="queue_reviewer@example.com",
        password="pw",
    )
    source = ExerciseSource.objects.create(
        name="Queue source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/queue-source.txt",
    )
    ExerciseCandidate.objects.create(
        source=source,
        raw_name="High confidence candidate",
        normalized_name="high confidence candidate",
        status=CurationStatus.NEEDS_REVIEW,
        confidence=0.920,
    )
    ExerciseCandidate.objects.create(
        source=source,
        raw_name="Low confidence candidate",
        normalized_name="low confidence candidate",
        status=CurationStatus.NEEDS_REVIEW,
        confidence=0.310,
    )
    ExerciseCandidate.objects.create(
        source=source,
        raw_name="Approved candidate",
        normalized_name="approved candidate",
        status=CurationStatus.APPROVED,
        confidence=0.990,
    )

    client.force_login(user)
    response = client.get(
        reverse("workouts:exercises"),
        {"candidate_status": CurationStatus.NEEDS_REVIEW, "confidence_band": "high"},
    )
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "high confidence candidate" in content
    assert "low confidence candidate" not in content
    assert "approved candidate" not in content


@pytest.mark.django_db
def test_review_action_redirects_back_to_filtered_queue(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="queue_redirect_reviewer",
        email="queue_redirect_reviewer@example.com",
        password="pw",
    )
    permission = Permission.objects.get(codename="review_exercisecandidate")
    user.user_permissions.add(permission)
    source = ExerciseSource.objects.create(
        name="Queue redirect source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/queue-redirect-source.txt",
        is_approved=True,
        license_name="CC BY 4.0",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Publish me",
        normalized_name="publish me",
        status=CurationStatus.APPROVED,
        confidence=0.930,
        metadata={
            "source_name": "Queue redirect source",
            "source_url": "https://example.com/queue-redirect-source",
            "attribution_text": "Source: Queue redirect source",
            "media_rights_confirmed": True,
            "content_rewritten": True,
            "safety_reviewed": True,
        },
    )

    client.force_login(user)
    next_url = (
        reverse("workouts:exercises")
        + "?candidate_status=approved&confidence_band=high"
    )
    response = client.post(
        reverse("workouts:exercise_candidate_review", kwargs={"candidate_id": candidate.id}),
        {"action": "publish", "next": next_url, "reason": "Looks good"},
    )

    assert response.status_code == 302
    assert response["Location"] == next_url
    candidate.refresh_from_db()
    assert candidate.status == CurationStatus.PUBLISHED
    assert candidate.reviewed_by_id == user.id


@pytest.mark.django_db
def test_review_action_persists_structured_metadata_fields(client):
    user_model = get_user_model()
    reviewer = user_model.objects.create_user(username="reviewer_meta", password="pw")
    permission = Permission.objects.get(codename="review_exercisecandidate")
    reviewer.user_permissions.add(permission)

    source = ExerciseSource.objects.create(
        name="Structured metadata source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/structured-metadata-source.txt",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Weighted Pull-Up",
        normalized_name="weighted pull-up",
        confidence=0.85,
        status=CurationStatus.NEEDS_REVIEW,
        metadata={"existing_key": "preserved"},
    )

    client.force_login(reviewer)
    response = client.post(
        reverse("workouts:exercise_candidate_review", kwargs={"candidate_id": candidate.id}),
        {
            "action": "send_back",
            "reason": "Needs cleanup",
            "source_name": "ACE",
            "source_url": "https://example.com/exercises/weighted-pull-up",
            "attribution_text": "Adapted from ACE guide",
            "media_rights_confirmed": "on",
            "content_rewritten": "on",
        },
        follow=False,
    )

    assert response.status_code == 302
    candidate.refresh_from_db()
    assert candidate.status == CurationStatus.DRAFT
    assert candidate.metadata["existing_key"] == "preserved"
    assert candidate.metadata["source_name"] == "ACE"
    assert (
        candidate.metadata["source_url"]
        == "https://example.com/exercises/weighted-pull-up"
    )
    assert candidate.metadata["attribution_text"] == "Adapted from ACE guide"
    assert candidate.metadata["media_rights_confirmed"] is True
    assert candidate.metadata["content_rewritten"] is True
    assert candidate.metadata["safety_reviewed"] is False


@pytest.mark.django_db
def test_review_action_without_helper_fields_does_not_mutate_metadata(client):
    user_model = get_user_model()
    reviewer = user_model.objects.create_user(username="reviewer_no_meta", password="pw")
    permission = Permission.objects.get(codename="review_exercisecandidate")
    reviewer.user_permissions.add(permission)

    source = ExerciseSource.objects.create(
        name="Legacy metadata source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/legacy-metadata-source.txt",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Band Pull-Apart",
        normalized_name="band pull-apart",
        confidence=0.9,
        status=CurationStatus.NEEDS_REVIEW,
        metadata={
            "source_name": "Legacy",
            "media_rights_confirmed": True,
            "custom": "value",
        },
    )

    client.force_login(reviewer)
    response = client.post(
        reverse("workouts:exercise_candidate_review", kwargs={"candidate_id": candidate.id}),
        {
            "action": "approve",
            "reason": "Looks good",
        },
        follow=False,
    )

    assert response.status_code == 302
    candidate.refresh_from_db()
    assert candidate.status == CurationStatus.APPROVED
    assert candidate.metadata == {
        "source_name": "Legacy",
        "media_rights_confirmed": True,
        "custom": "value",
    }


@pytest.mark.django_db
def test_exercise_queue_shows_missing_publish_requirements(client):
    user_model = get_user_model()
    reviewer = user_model.objects.create_user(
        username="publish_queue_reviewer",
        email="publish_queue_reviewer@example.com",
        password="pw",
    )
    source = ExerciseSource.objects.create(
        name="Missing publish requirements source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/missing-publish-requirements-source.txt",
        is_approved=False,
        license_name="",
    )
    ExerciseCandidate.objects.create(
        source=source,
        raw_name="Push-Up",
        normalized_name="push-up",
        confidence=0.91,
        status=CurationStatus.APPROVED,
        metadata={
            "source_name": "",
            "source_url": "",
            "attribution_text": "",
            "media_rights_confirmed": False,
            "content_rewritten": False,
            "safety_reviewed": False,
        },
    )

    client.force_login(reviewer)
    response = client.get(reverse("workouts:exercises"), {"candidate_status": "approved"})

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Publish requirements missing:" in content
    assert "approved source" in content
    assert "source license" in content
    assert "source URL" in content


@pytest.mark.django_db
def test_publish_guardrail_error_message_is_shown_to_reviewer(client):
    user_model = get_user_model()
    reviewer = user_model.objects.create_user(
        username="publish_guardrail_reviewer",
        email="publish_guardrail_reviewer@example.com",
        password="pw",
    )
    permission = Permission.objects.get(codename="review_exercisecandidate")
    reviewer.user_permissions.add(permission)

    source = ExerciseSource.objects.create(
        name="Guardrail source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/guardrail-source.txt",
        is_approved=True,
        license_name="CC BY 4.0",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Burpee",
        normalized_name="burpee",
        confidence=0.96,
        status=CurationStatus.APPROVED,
        metadata={
            "source_name": "Guardrail source",
            "source_url": "",
            "attribution_text": "Source: Guardrail source",
            "media_rights_confirmed": True,
            "content_rewritten": True,
            "safety_reviewed": True,
        },
    )

    client.force_login(reviewer)
    response = client.post(
        reverse("workouts:exercise_candidate_review", kwargs={"candidate_id": candidate.id}),
        {
            "action": "publish",
            "next": reverse("workouts:exercises"),
        },
        follow=True,
    )

    assert response.status_code == 200
    candidate.refresh_from_db()
    assert candidate.status == CurationStatus.APPROVED
    content = response.content.decode("utf-8")
    assert "Cannot publish candidate without required attribution and safety metadata" in content
    assert "source_url" in content


@pytest.mark.django_db
def test_exercise_queue_filters_candidates_by_publish_readiness(client):
    user_model = get_user_model()
    reviewer = user_model.objects.create_user(
        username="publish_ready_filter_reviewer",
        email="publish_ready_filter_reviewer@example.com",
        password="pw",
    )
    source = ExerciseSource.objects.create(
        name="Publish readiness filter source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/publish-readiness-filter-source.txt",
        is_approved=True,
        license_name="CC BY 4.0",
    )
    ExerciseCandidate.objects.create(
        source=source,
        raw_name="Ready Candidate",
        normalized_name="ready candidate",
        confidence=0.93,
        status=CurationStatus.APPROVED,
        metadata={
            "source_name": "Publish readiness filter source",
            "source_url": "https://example.com/ready-candidate",
            "attribution_text": "Source: Publish readiness filter source",
            "media_rights_confirmed": True,
            "content_rewritten": True,
            "safety_reviewed": True,
        },
    )
    ExerciseCandidate.objects.create(
        source=source,
        raw_name="Missing Candidate",
        normalized_name="missing candidate",
        confidence=0.93,
        status=CurationStatus.APPROVED,
        metadata={
            "source_name": "Publish readiness filter source",
            "source_url": "",
            "attribution_text": "Source: Publish readiness filter source",
            "media_rights_confirmed": True,
            "content_rewritten": True,
            "safety_reviewed": True,
        },
    )

    client.force_login(reviewer)
    response = client.get(
        reverse("workouts:exercises"),
        {
            "candidate_status": "approved",
            "publish_readiness": "ready",
        },
    )

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "ready candidate" in content
    assert "missing candidate" not in content


@pytest.mark.django_db
def test_review_action_persists_requirement_confirmation_audit_metadata(client):
    user_model = get_user_model()
    reviewer = user_model.objects.create_user(
        username="confirmation_audit_reviewer",
        email="confirmation_audit_reviewer@example.com",
        password="pw",
    )
    permission = Permission.objects.get(codename="review_exercisecandidate")
    reviewer.user_permissions.add(permission)

    source = ExerciseSource.objects.create(
        name="Audit metadata source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/audit-metadata-source.txt",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Step-Up",
        normalized_name="step-up",
        confidence=0.88,
        status=CurationStatus.NEEDS_REVIEW,
        metadata={},
    )

    client.force_login(reviewer)
    response = client.post(
        reverse("workouts:exercise_candidate_review", kwargs={"candidate_id": candidate.id}),
        {
            "action": "send_back",
            "source_name": "Audit metadata source",
            "source_url": "https://example.com/step-up",
            "attribution_text": "Source: Audit metadata source",
            "media_rights_confirmed": "on",
            "content_rewritten": "on",
            "safety_reviewed": "on",
        },
        follow=False,
    )

    assert response.status_code == 302
    candidate.refresh_from_db()
    assert candidate.metadata["media_rights_confirmed_confirmed_by"] == reviewer.username
    assert candidate.metadata["content_rewritten_confirmed_by"] == reviewer.username
    assert candidate.metadata["safety_reviewed_confirmed_by"] == reviewer.username
    assert candidate.metadata["source_name_confirmed_by"] == reviewer.username
    assert candidate.metadata["source_url_confirmed_by"] == reviewer.username
    assert candidate.metadata["attribution_text_confirmed_by"] == reviewer.username
    assert candidate.metadata["media_rights_confirmed_confirmed_at"]
    assert candidate.metadata["source_name_confirmed_at"]


@pytest.mark.django_db
def test_reviewer_queue_displays_policy_help_panel(client):
    user_model = get_user_model()
    reviewer = user_model.objects.create_user(
        username="policy_help_reviewer",
        email="policy_help_reviewer@example.com",
        password="pw",
    )
    permission = Permission.objects.get(codename="review_exercisecandidate")
    reviewer.user_permissions.add(permission)

    source = ExerciseSource.objects.create(
        name="Policy help source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/policy-help-source.txt",
    )
    ExerciseCandidate.objects.create(
        source=source,
        raw_name="Lateral Lunge",
        normalized_name="lateral lunge",
        confidence=0.72,
        status=CurationStatus.NEEDS_REVIEW,
        metadata={},
    )

    client.force_login(reviewer)
    response = client.get(reverse("workouts:exercises"))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Policy Help" in content
    assert "Content policy source: docs/content-policy.md" in content


@pytest.mark.django_db
def test_exercise_library_displays_rich_card_sections_and_authoring_form(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="exercise_library_viewer",
        email="exercise_library_viewer@example.com",
        password="pw",
    )
    exercise = Exercise.objects.create(
        name="Tempo Squat",
        slug="tempo-squat",
        category=ExerciseCategory.STRENGTH,
        movement_type=ExerciseMovementType.SQUAT,
        primary_body_area=ExerciseBodyArea.LOWER_BODY,
        difficulty_level=ExerciseDifficultyLevel.INTERMEDIATE,
        equipment_requirement=ExerciseEquipmentRequirement.MINIMAL,
        duration_fit=ExerciseDurationFit.MEDIUM,
        description="Controlled squat variation.",
        instructions="Lower with a three count and stand with intent.",
        safety_notes="Brace and keep heels grounded.",
        setup_steps="Stand at shoulder width.",
        execution_steps="Sit down and drive up.",
        coaching_cues="Spread the floor.",
        is_active=True,
    )
    ExerciseMedia.objects.create(
        exercise=exercise,
        media_type="image",
        external_url="https://example.com/tempo-squat.jpg",
        license_name="CC BY 4.0",
        attribution_text="Photo by Example Coach",
    )

    client.force_login(user)
    response = client.get(reverse("workouts:exercises"))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Movement profile" in content
    assert "Authoring notes" in content
    assert "Caution and coaching" in content
    assert "Default prescriptions" in content
    assert "Active library item" in content
    assert "1 media" in content
    assert "Classification" in content
    assert "Authoring" in content
    assert "Primary area: Lower body" in content
    assert "Level: Intermediate" in content
    assert "Duration fit: Medium session" in content
    assert "Safe-form instructions" in content
    assert "Open external media" in content
    assert "Photo by Example Coach" in content


@pytest.mark.django_db
def test_exercise_library_filters_searches_and_sorts_results(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="exercise_library_filter_user",
        email="exercise_library_filter_user@example.com",
        password="pw",
    )
    Exercise.objects.create(
        name="Sprint Step-Up",
        slug="sprint-step-up",
        category=ExerciseCategory.CONDITIONING,
        movement_type=ExerciseMovementType.LUNGE,
        primary_body_area=ExerciseBodyArea.LOWER_BODY,
        difficulty_level=ExerciseDifficultyLevel.BEGINNER,
        equipment_requirement=ExerciseEquipmentRequirement.NONE,
        duration_fit=ExerciseDurationFit.SHORT,
        description="Quick lower-body conditioning.",
        is_active=True,
    )
    Exercise.objects.create(
        name="Tempo Squat",
        slug="tempo-squat-filter",
        category=ExerciseCategory.STRENGTH,
        movement_type=ExerciseMovementType.SQUAT,
        primary_body_area=ExerciseBodyArea.LOWER_BODY,
        difficulty_level=ExerciseDifficultyLevel.INTERMEDIATE,
        equipment_requirement=ExerciseEquipmentRequirement.MINIMAL,
        duration_fit=ExerciseDurationFit.MEDIUM,
        description="Controlled squat work.",
        is_active=True,
    )
    Exercise.objects.create(
        name="Carry March",
        slug="carry-march",
        category=ExerciseCategory.CONDITIONING,
        movement_type=ExerciseMovementType.CARRY,
        primary_body_area=ExerciseBodyArea.FULL_BODY,
        difficulty_level=ExerciseDifficultyLevel.ADVANCED,
        equipment_requirement=ExerciseEquipmentRequirement.SPECIALIZED,
        duration_fit=ExerciseDurationFit.LONG,
        description="Loaded carry progression.",
        is_active=True,
    )

    client.force_login(user)
    response = client.get(
        reverse("workouts:exercises"),
        {
            "q": "squat",
            "primary_body_area": ExerciseBodyArea.LOWER_BODY,
            "difficulty_level": ExerciseDifficultyLevel.INTERMEDIATE,
            "duration_fit": ExerciseDurationFit.MEDIUM,
            "sort": "duration_fit",
        },
    )

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Tempo Squat" in content
    assert "Sprint Step-Up" not in content
    assert "Carry March" not in content
    assert "Apply library filters" in content
