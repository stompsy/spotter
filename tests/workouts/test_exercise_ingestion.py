from __future__ import annotations

import pytest
from django.core.management import call_command

from apps.workouts.models import (
    CurationStatus,
    ExerciseCandidate,
    ExerciseExtractionPage,
    ExerciseExtractionRun,
    ExerciseSource,
    ExerciseSourceType,
    ExtractionMethod,
    ExtractionPageStatus,
    ExtractionRunStatus,
)


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
