from __future__ import annotations

import pytest

from apps.workouts.models import (
    CurationStatus,
    ExerciseCandidate,
    ExerciseExtractionPage,
    ExerciseExtractionRun,
    ExerciseSource,
    ExerciseSourceType,
    ExtractionMethod,
    ExtractionPageStatus,
    PlanSignalCandidate,
    SourceReference,
)


@pytest.mark.django_db
def test_plan_signal_candidate_persists_with_optional_page_link():
    source = ExerciseSource.objects.create(
        name="Schema source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/schema-source.txt",
    )
    run = ExerciseExtractionRun.objects.create(source=source)
    page = ExerciseExtractionPage.objects.create(
        run=run,
        page_number=1,
        extraction_method=ExtractionMethod.TEXT_FILE,
        status=ExtractionPageStatus.EXTRACTED,
        raw_text="Day 1: Core",
        cleaned_text="Day 1: Core",
        char_count=11,
    )

    signal_with_page = PlanSignalCandidate.objects.create(
        run=run,
        page=page,
        signal_type="challenge_day",
        signal_value="Day 1",
        confidence=0.91,
        metadata={"focus_area": "Core"},
    )
    signal_without_page = PlanSignalCandidate.objects.create(
        run=run,
        signal_type="phase_marker",
        signal_value="Week 1",
        confidence=0.88,
        metadata={"kind": "header"},
    )

    assert signal_with_page.page_id == page.id
    assert signal_without_page.page is None
    assert run.plan_signal_candidates.count() == 2


@pytest.mark.django_db
def test_source_reference_persists_against_candidate_with_source_metadata():
    source = ExerciseSource.objects.create(
        name="Reference source",
        source_type=ExerciseSourceType.WEB,
        location="https://example.com/reference-index",
        license_name="CC BY 4.0",
        is_approved=True,
    )
    candidate = ExerciseCandidate.objects.create(
        source=source,
        raw_name="Forward Lunge",
        normalized_name="forward lunge",
        status=CurationStatus.NEEDS_REVIEW,
        confidence=0.77,
    )

    reference = SourceReference.objects.create(
        candidate=candidate,
        source=source,
        title="Forward Lunge guide",
        reference_url="https://example.com/exercises/forward-lunge",
        license_name="CC BY 4.0",
        attribution_text="Example Fitness",
        metadata={"retrieval_method": "manual_lookup"},
    )

    candidate.refresh_from_db()
    assert candidate.source_references.count() == 1
    assert candidate.source_references.first() == reference
    assert reference.metadata["retrieval_method"] == "manual_lookup"
