from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse

from apps.workouts.models import (
    CurationStatus,
    ExerciseCandidate,
    ExerciseCandidateDecision,
    ExerciseExtractionPage,
    ExerciseExtractionRun,
    ExerciseSource,
    ExerciseSourceType,
    ExtractionMethod,
    ExtractionPageStatus,
    ExtractionRunStatus,
)


def grant_candidate_review_permission(user) -> None:
    permission = Permission.objects.get(codename="review_exercisecandidate")
    user.user_permissions.add(permission)


@pytest.mark.django_db
def test_ingest_exercise_candidates_creates_source_and_draft_candidates(tmp_path):
    source_file = tmp_path / "Lunges.txt"
    source_file.write_text(
        "\n".join(
            [
                "30 Forward Lunges (15 each leg)",
                "20 Right Side Lunges",
                "20 Left Side Lunges",
                "30 Reverse Lunges (15 each leg)",
                "Switch Lunges: Do as many you can",
                "http://beta.active.com/fitness/Articles/Master-the-Plank.htm",
            ]
        ),
        encoding="utf-8",
    )

    call_command("ingest_exercise_candidates", source_file=str(source_file))

    source = ExerciseSource.objects.get(location=str(source_file))
    assert source.source_type == ExerciseSourceType.DOCUMENT

    normalized = set(
        ExerciseCandidate.objects.filter(source=source).values_list(
            "normalized_name",
            flat=True,
        )
    )
    assert normalized == {
        "forward lunge",
        "side lunge",
        "reverse lunge",
        "switch lunge",
        "plank",
    }

    assert (
        ExerciseCandidate.objects.filter(
            source=source,
            status=CurationStatus.DRAFT,
        ).count()
        == 5
    )

    extraction_run = ExerciseExtractionRun.objects.get(source=source)
    assert extraction_run.status == ExtractionRunStatus.COMPLETED
    assert extraction_run.summary["method"] == ExtractionMethod.TEXT_FILE
    assert extraction_run.summary["pages_total"] == 1
    assert extraction_run.summary["pages_with_text"] == 1

    page = ExerciseExtractionPage.objects.get(run=extraction_run, page_number=1)
    assert page.extraction_method == ExtractionMethod.TEXT_FILE
    assert page.status == ExtractionPageStatus.EXTRACTED
    assert page.char_count > 0


@pytest.mark.django_db
def test_ingest_exercise_candidates_is_idempotent_for_normalized_names(tmp_path):
    source_file = tmp_path / "Lunges.txt"
    source_file.write_text(
        "\n".join(
            [
                "Forward Lunges",
                "Forward Lunges",
                "Left Side Lunges",
                "Right Side Lunges",
            ]
        ),
        encoding="utf-8",
    )

    call_command("ingest_exercise_candidates", source_file=str(source_file))
    call_command("ingest_exercise_candidates", source_file=str(source_file))

    source = ExerciseSource.objects.get(location=str(source_file))
    candidates = ExerciseCandidate.objects.filter(source=source)
    assert candidates.count() == 2
    assert set(candidates.values_list("normalized_name", flat=True)) == {
        "forward lunge",
        "side lunge",
    }


@pytest.mark.django_db
def test_ingest_exercise_candidates_records_pdf_page_logging_with_routing_stub(
    tmp_path,
    monkeypatch,
):
    from apps.workouts.management.commands import ingest_exercise_candidates as module

    source_file = tmp_path / "mock.pdf"
    source_file.write_bytes(b"%PDF-1.4\n")

    def fake_extract_text_pages(_path):
        return ["Forward Lunges", "", "Switch Lunges"], ExtractionMethod.PYPDF, None

    monkeypatch.setattr(module, "extract_text_pages", fake_extract_text_pages)

    call_command("ingest_exercise_candidates", source_file=str(source_file))

    source = ExerciseSource.objects.get(location=str(source_file))
    extraction_run = ExerciseExtractionRun.objects.get(source=source)
    assert extraction_run.status == ExtractionRunStatus.COMPLETED_WITH_ERRORS
    assert extraction_run.summary["method"] == ExtractionMethod.PYPDF
    assert extraction_run.summary["pages_total"] == 3
    assert extraction_run.summary["pages_with_text"] == 2
    assert extraction_run.summary["page_errors"] == 1

    pages = list(
        ExerciseExtractionPage.objects.filter(run=extraction_run).order_by("page_number")
    )
    assert [page.page_number for page in pages] == [1, 2, 3]
    assert pages[0].status == ExtractionPageStatus.EXTRACTED
    assert pages[1].status == ExtractionPageStatus.PARTIAL
    assert pages[2].status == ExtractionPageStatus.EXTRACTED


@pytest.mark.django_db
def test_exercise_candidate_transition_guardrails_allow_and_reject_paths():
    source = ExerciseSource.objects.create(
        name="Candidate source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/candidate-source.txt",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Forward Lunges",
        normalized_name="forward lunge",
        status=CurationStatus.DRAFT,
    )

    candidate.transition_to(CurationStatus.NEEDS_REVIEW)
    candidate.save(update_fields=["status", "updated_at"])
    assert candidate.status == CurationStatus.NEEDS_REVIEW

    with pytest.raises(ValidationError):
        candidate.transition_to(CurationStatus.PUBLISHED)


@pytest.mark.django_db
def test_exercise_candidate_publish_requires_approved_source_and_license():
    source = ExerciseSource.objects.create(
        name="Publish gate source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/publish-gate-source.txt",
        is_approved=False,
        license_name="",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Forward Lunges",
        normalized_name="forward lunge",
        status=CurationStatus.APPROVED,
        metadata={
            "source_name": "Publish gate source",
            "source_url": "https://example.com/publish-gate-source",
            "attribution_text": "Source: Publish gate source",
            "media_rights_confirmed": True,
            "content_rewritten": True,
            "safety_reviewed": True,
        },
    )

    with pytest.raises(ValidationError):
        candidate.transition_to(CurationStatus.PUBLISHED)

    source.is_approved = True
    source.license_name = "CC BY 4.0"
    source.save(update_fields=["is_approved", "license_name", "updated_at"])

    candidate.transition_to(CurationStatus.PUBLISHED)
    candidate.save(update_fields=["status", "updated_at"])
    candidate.refresh_from_db()
    assert candidate.status == CurationStatus.PUBLISHED


@pytest.mark.django_db
def test_exercise_candidate_publish_requires_attribution_and_safety_metadata():
    source = ExerciseSource.objects.create(
        name="Metadata gate source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/metadata-gate-source.txt",
        is_approved=True,
        license_name="CC BY 4.0",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Forward Lunges",
        normalized_name="forward lunge",
        status=CurationStatus.APPROVED,
        metadata={},
    )

    with pytest.raises(ValidationError):
        candidate.transition_to(CurationStatus.PUBLISHED)

    candidate.metadata = {
        "source_name": "Metadata gate source",
        "source_url": "https://example.com/metadata-gate-source",
        "attribution_text": "Source: Metadata gate source",
        "media_rights_confirmed": True,
        "content_rewritten": True,
        "safety_reviewed": True,
    }
    candidate.transition_to(CurationStatus.PUBLISHED)
    candidate.save(update_fields=["status", "metadata", "updated_at"])
    candidate.refresh_from_db()
    assert candidate.status == CurationStatus.PUBLISHED


@pytest.mark.django_db
def test_exercise_candidate_review_action_endpoint_transitions_status(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="candidate_reviewer",
        email="candidate_reviewer@example.com",
        password="pw",
    )
    grant_candidate_review_permission(user)
    source = ExerciseSource.objects.create(
        name="Review source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/review-source.txt",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Forward Lunges",
        normalized_name="forward lunge",
        status=CurationStatus.DRAFT,
    )

    client.force_login(user)
    mark_review_response = client.post(
        reverse("workouts:exercise_candidate_review", kwargs={"candidate_id": candidate.id}),
        {"action": "mark_review"},
    )
    assert mark_review_response.status_code == 302
    candidate.refresh_from_db()
    assert candidate.status == CurationStatus.NEEDS_REVIEW

    approve_response = client.post(
        reverse("workouts:exercise_candidate_review", kwargs={"candidate_id": candidate.id}),
        {"action": "approve"},
    )
    assert approve_response.status_code == 302
    candidate.refresh_from_db()
    assert candidate.status == CurationStatus.APPROVED


@pytest.mark.django_db
def test_exercise_candidate_review_action_rejects_invalid_transition(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="candidate_reviewer_invalid",
        email="candidate_reviewer_invalid@example.com",
        password="pw",
    )
    grant_candidate_review_permission(user)
    source = ExerciseSource.objects.create(
        name="Invalid transition source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/invalid-transition-source.txt",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Forward Lunges",
        normalized_name="forward lunge",
        status=CurationStatus.DRAFT,
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:exercise_candidate_review", kwargs={"candidate_id": candidate.id}),
        {"action": "publish"},
    )

    assert response.status_code == 302
    candidate.refresh_from_db()
    assert candidate.status == CurationStatus.DRAFT


@pytest.mark.django_db
def test_exercise_candidate_review_action_publish_rejected_when_source_not_ready(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="candidate_reviewer_publish_blocked",
        email="candidate_reviewer_publish_blocked@example.com",
        password="pw",
    )
    grant_candidate_review_permission(user)
    source = ExerciseSource.objects.create(
        name="Publish blocked source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/publish-blocked-source.txt",
        is_approved=False,
        license_name="",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Forward Lunges",
        normalized_name="forward lunge",
        status=CurationStatus.APPROVED,
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:exercise_candidate_review", kwargs={"candidate_id": candidate.id}),
        {"action": "publish", "reason": "ready to publish"},
    )

    assert response.status_code == 302
    candidate.refresh_from_db()
    assert candidate.status == CurationStatus.APPROVED
    assert candidate.reviewed_by is None
    assert candidate.reviewed_at is None


@pytest.mark.django_db
def test_exercise_candidate_review_action_persists_reviewer_metadata(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="candidate_reviewer_publish_allowed",
        email="candidate_reviewer_publish_allowed@example.com",
        password="pw",
    )
    grant_candidate_review_permission(user)
    source = ExerciseSource.objects.create(
        name="Publish allowed source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/publish-allowed-source.txt",
        is_approved=True,
        license_name="CC BY 4.0",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Forward Lunges",
        normalized_name="forward lunge",
        status=CurationStatus.APPROVED,
        metadata={
            "source_name": "Publish allowed source",
            "source_url": "https://example.com/publish-allowed-source",
            "attribution_text": "Source: Publish allowed source",
            "media_rights_confirmed": True,
            "content_rewritten": True,
            "safety_reviewed": True,
        },
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:exercise_candidate_review", kwargs={"candidate_id": candidate.id}),
        {"action": "publish", "reason": "Validated source and license"},
    )

    assert response.status_code == 302
    candidate.refresh_from_db()
    assert candidate.status == CurationStatus.PUBLISHED
    assert candidate.reviewed_by == user
    assert candidate.reviewed_at is not None
    assert candidate.decision_reason == "Validated source and license"

    decisions = ExerciseCandidateDecision.objects.filter(candidate=candidate)
    assert decisions.count() == 1
    decision = decisions.first()
    assert decision is not None
    assert decision.action == "publish"
    assert decision.from_status == CurationStatus.APPROVED
    assert decision.to_status == CurationStatus.PUBLISHED
    assert decision.decided_by == user
    assert decision.reason == "Validated source and license"


@pytest.mark.django_db
def test_exercise_candidate_review_action_does_not_write_decision_when_transition_rejected(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="candidate_reviewer_no_decision",
        email="candidate_reviewer_no_decision@example.com",
        password="pw",
    )
    grant_candidate_review_permission(user)
    source = ExerciseSource.objects.create(
        name="No decision source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/no-decision-source.txt",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Forward Lunges",
        normalized_name="forward lunge",
        status=CurationStatus.DRAFT,
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:exercise_candidate_review", kwargs={"candidate_id": candidate.id}),
        {"action": "publish", "reason": "should fail"},
    )

    assert response.status_code == 302
    assert ExerciseCandidateDecision.objects.filter(candidate=candidate).count() == 0


@pytest.mark.django_db
def test_exercise_candidate_decision_is_immutable_after_creation():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="candidate_decision_owner",
        email="candidate_decision_owner@example.com",
        password="pw",
    )
    source = ExerciseSource.objects.create(
        name="Decision source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/decision-source.txt",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Forward Lunges",
        normalized_name="forward lunge",
        status=CurationStatus.NEEDS_REVIEW,
    )

    decision = ExerciseCandidateDecision.objects.create(
        candidate=candidate,
        action="approve",
        from_status=CurationStatus.NEEDS_REVIEW,
        to_status=CurationStatus.APPROVED,
        decided_by=user,
        reason="initial reason",
    )

    decision.reason = "modified reason"
    with pytest.raises(ValidationError):
        decision.save()

    with pytest.raises(ValidationError):
        decision.delete()


@pytest.mark.django_db
def test_exercise_candidate_review_action_requires_reviewer_permission(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="candidate_non_reviewer",
        email="candidate_non_reviewer@example.com",
        password="pw",
    )
    source = ExerciseSource.objects.create(
        name="Staff gate source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/staff-gate-source.txt",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Forward Lunges",
        normalized_name="forward lunge",
        status=CurationStatus.DRAFT,
    )

    client.force_login(user)
    response = client.post(
        reverse("workouts:exercise_candidate_review", kwargs={"candidate_id": candidate.id}),
        {"action": "mark_review"},
    )

    assert response.status_code == 404
    candidate.refresh_from_db()
    assert candidate.status == CurationStatus.DRAFT
    assert ExerciseCandidateDecision.objects.filter(candidate=candidate).count() == 0


@pytest.mark.django_db
def test_ingest_exercise_candidates_dataset_adapter_csv(tmp_path):
    source_file = tmp_path / "bundle.csv"
    source_file.write_text(
        "name\nForward Lunges\nPlank\n",
        encoding="utf-8",
    )

    call_command(
        "ingest_exercise_candidates",
        source_file=str(source_file),
        adapter="dataset",
    )

    source = ExerciseSource.objects.get(location=str(source_file))
    assert source.source_type == ExerciseSourceType.DATASET
    normalized = set(
        ExerciseCandidate.objects.filter(source=source).values_list(
            "normalized_name",
            flat=True,
        )
    )
    assert "forward lunge" in normalized
    assert "plank" in normalized


@pytest.mark.django_db
def test_ingest_exercise_candidates_manual_adapter_without_source_file():
    call_command(
        "ingest_exercise_candidates",
        adapter="manual",
        candidate_name=["Reverse Lunges", "Plank"],
    )

    source = ExerciseSource.objects.get(location="manual://cli")
    assert source.source_type == ExerciseSourceType.DOCUMENT
    normalized = set(
        ExerciseCandidate.objects.filter(source=source).values_list(
            "normalized_name",
            flat=True,
        )
    )
    assert normalized == {"reverse lunge", "plank"}


@pytest.mark.django_db
def test_ingest_exercise_candidates_media_adapter_uses_filename_candidate(tmp_path):
    source_file = tmp_path / "lateral_lunge_demo.mp4"
    source_file.write_bytes(b"fake-media")

    call_command(
        "ingest_exercise_candidates",
        source_file=str(source_file),
        adapter="media",
    )

    source = ExerciseSource.objects.get(location=str(source_file))
    assert source.source_type == ExerciseSourceType.WEB
    candidates = list(
        ExerciseCandidate.objects.filter(source=source).values_list(
            "normalized_name",
            flat=True,
        )
    )
    assert "lateral lunge demo" in candidates


@pytest.mark.django_db
def test_ingest_exercise_candidates_sets_quality_checks_and_duplicate_metadata(tmp_path):
    existing_source = ExerciseSource.objects.create(
        name="existing",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/existing.txt",
    )
    ExerciseCandidate.objects.create(
        source=existing_source,
        raw_name="Forward Lunges",
        normalized_name="forward lunge",
        status=CurationStatus.DRAFT,
    )

    source_file = tmp_path / "quality.txt"
    source_file.write_text(
        "Forward Lunges\n3 sets of 10 reps\nWarm up first and stop if pain appears.",
        encoding="utf-8",
    )

    call_command("ingest_exercise_candidates", source_file=str(source_file))

    source = ExerciseSource.objects.get(location=str(source_file))
    candidate = ExerciseCandidate.objects.get(
        source=source,
        normalized_name="forward lunge",
    )
    quality_checks = candidate.metadata.get("quality_checks", {})
    assert quality_checks.get("duplicate_candidates") is True
    assert quality_checks.get("duplicate_count") == 2
    assert quality_checks.get("instruction_completeness_score", 0.0) > 0.0
    assert quality_checks.get("safety_completeness_score", 0.0) > 0.0
