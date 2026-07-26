import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.communities.models import Community, CommunityMembership, MembershipRole, MembershipStatus
from apps.workouts.models import (
    CurationStatus,
    Exercise,
    ExerciseBodyArea,
    ExerciseCandidate,
    ExerciseCategory,
    ExerciseDifficultyLevel,
    ExerciseEquipmentRequirement,
    ExerciseMovementType,
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
            "movement_type": ExerciseMovementType.LUNGE,
            "primary_body_area": ExerciseBodyArea.LOWER_BODY,
            "difficulty_level": ExerciseDifficultyLevel.BEGINNER,
            "equipment_requirement": ExerciseEquipmentRequirement.NONE,
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
    assert exercise.movement_type == ExerciseMovementType.LUNGE
    assert exercise.primary_body_area == ExerciseBodyArea.LOWER_BODY
    assert exercise.difficulty_level == ExerciseDifficultyLevel.BEGINNER
    assert exercise.equipment_requirement == ExerciseEquipmentRequirement.NONE
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
            "category": ExerciseCategory.CALISTHENICS,
            "movement_type": ExerciseMovementType.PUSH,
            "primary_body_area": ExerciseBodyArea.SHOULDERS,
            "difficulty_level": ExerciseDifficultyLevel.ADVANCED,
            "equipment_requirement": ExerciseEquipmentRequirement.SPECIALIZED,
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
    assert exercise.primary_body_area == ExerciseBodyArea.SHOULDERS
    assert exercise.difficulty_level == ExerciseDifficultyLevel.ADVANCED
    assert exercise.equipment_requirement == ExerciseEquipmentRequirement.SPECIALIZED
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
