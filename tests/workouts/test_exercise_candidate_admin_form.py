import pytest
from django.contrib.auth import get_user_model

from apps.workouts.admin import ExerciseCandidateAdminForm
from apps.workouts.models import (
    CurationStatus,
    ExerciseCandidate,
    ExerciseSource,
    ExerciseSourceType,
)


def build_candidate_form_data(source_id: int, **overrides):
    data = {
        "source": source_id,
        "raw_name": "Forward Lunges",
        "normalized_name": "forward lunge",
        "status": CurationStatus.PUBLISHED,
        "confidence": "0.900",
        "source_name": "Approved source",
        "source_url": "https://example.com",
        "attribution_text": "Source",
        "media_rights_confirmed": "on",
        "content_rewritten": "on",
        "safety_reviewed": "on",
        "metadata": "{}",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_candidate_admin_form_blocks_publish_when_metadata_incomplete():
    source = ExerciseSource.objects.create(
        name="Admin source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/admin-source.txt",
        is_approved=True,
        license_name="CC BY 4.0",
    )

    form = ExerciseCandidateAdminForm(
        data=build_candidate_form_data(source.id, source_name=""),
    )

    assert form.is_valid() is False
    assert "metadata" in form.errors


@pytest.mark.django_db
def test_candidate_admin_form_blocks_publish_when_source_is_not_approved():
    source = ExerciseSource.objects.create(
        name="Unapproved source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/unapproved-source.txt",
        is_approved=False,
        license_name="",
    )

    form = ExerciseCandidateAdminForm(data=build_candidate_form_data(source.id))

    assert form.is_valid() is False
    assert "Cannot publish candidate without an approved source" in str(form.errors)


@pytest.mark.django_db
def test_candidate_admin_form_allows_publish_when_requirements_are_met():
    source = ExerciseSource.objects.create(
        name="Approved source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/approved-source.txt",
        is_approved=True,
        license_name="CC BY 4.0",
    )

    form = ExerciseCandidateAdminForm(data=build_candidate_form_data(source.id))

    assert form.is_valid() is True
    assert form.cleaned_data["metadata"]["source_name"] == "Approved source"
    assert form.cleaned_data["metadata"]["media_rights_confirmed"] is True


@pytest.mark.django_db
def test_candidate_admin_form_round_trips_structured_metadata_fields_from_instance():
    source = ExerciseSource.objects.create(
        name="Roundtrip source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/roundtrip-source.txt",
        is_approved=True,
        license_name="CC BY 4.0",
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Forward Lunges",
        normalized_name="forward lunge",
        status=CurationStatus.APPROVED,
        metadata={
            "source_name": "Roundtrip source",
            "source_url": "https://example.com/roundtrip",
            "attribution_text": "Roundtrip attribution",
            "media_rights_confirmed": True,
            "content_rewritten": True,
            "safety_reviewed": False,
        },
    )

    form = ExerciseCandidateAdminForm(instance=candidate)

    assert form.fields["source_name"].initial == "Roundtrip source"
    assert form.fields["source_url"].initial == "https://example.com/roundtrip"
    assert form.fields["attribution_text"].initial == "Roundtrip attribution"
    assert form.fields["media_rights_confirmed"].initial is True
    assert form.fields["content_rewritten"].initial is True
    assert form.fields["safety_reviewed"].initial is False


@pytest.mark.django_db
def test_candidate_admin_form_sets_publish_help_text_on_metadata_field():
    source = ExerciseSource.objects.create(
        name="Help source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/help-source.txt",
    )
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="help_user",
        email="help_user@example.com",
        password="pw",
    )
    form = ExerciseCandidateAdminForm(
        initial={
            "source": source.id,
            "raw_name": "Forward Lunges",
            "normalized_name": "forward lunge",
            "status": CurationStatus.DRAFT,
            "reviewed_by": user.id,
        }
    )

    assert "Optional extra metadata JSON" in form.fields["metadata"].help_text
    assert "Required when status is published" in form.fields["source_name"].help_text
