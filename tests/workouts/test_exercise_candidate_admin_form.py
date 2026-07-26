import json

import pytest
from django.contrib.auth import get_user_model

from apps.workouts.admin import ExerciseCandidateAdminForm
from apps.workouts.models import CurationStatus, ExerciseSource, ExerciseSourceType


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
        data={
            "source": source.id,
            "raw_name": "Forward Lunges",
            "normalized_name": "forward lunge",
            "status": CurationStatus.PUBLISHED,
            "confidence": "0.900",
            "metadata": "{}",
        }
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

    metadata = json.dumps(
        {
            "source_name": "Unapproved source",
            "source_url": "https://example.com",
            "attribution_text": "Source",
            "media_rights_confirmed": True,
            "content_rewritten": True,
            "safety_reviewed": True,
        }
    )

    form = ExerciseCandidateAdminForm(
        data={
            "source": source.id,
            "raw_name": "Forward Lunges",
            "normalized_name": "forward lunge",
            "status": CurationStatus.PUBLISHED,
            "confidence": "0.900",
            "metadata": metadata,
        }
    )

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

    metadata = json.dumps(
        {
            "source_name": "Approved source",
            "source_url": "https://example.com",
            "attribution_text": "Source",
            "media_rights_confirmed": True,
            "content_rewritten": True,
            "safety_reviewed": True,
        }
    )

    form = ExerciseCandidateAdminForm(
        data={
            "source": source.id,
            "raw_name": "Forward Lunges",
            "normalized_name": "forward lunge",
            "status": CurationStatus.PUBLISHED,
            "confidence": "0.900",
            "metadata": metadata,
        }
    )

    assert form.is_valid() is True


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

    assert "Publish requires metadata keys" in form.fields["metadata"].help_text
