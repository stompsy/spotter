import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.communities.models import Community, CommunityMembership, MembershipRole, MembershipStatus
from apps.workouts.models import (
    CurationStatus,
    Exercise,
    ExerciseCandidate,
    ExerciseCategory,
    ExerciseSource,
    ExerciseSourceType,
    WorkoutPlan,
    WorkoutPlanAssignment,
    WorkoutPlanItem,
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
            "category": ExerciseCategory.CALISTHENICS,
            "description": "Multi-direction lunge prep",
            "instructions": "2 sets each direction",
            "is_active": "on",
        },
    )

    assert create_response.status_code == 302
    exercise = Exercise.objects.get(name="Lunge Matrix")
    assert exercise.is_active is True

    archive_response = client.post(
        reverse("workouts:exercise_toggle_active", kwargs={"exercise_id": exercise.id}),
    )
    assert archive_response.status_code == 302
    exercise.refresh_from_db()
    assert exercise.is_active is False


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
        is_staff=True,
    )
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
